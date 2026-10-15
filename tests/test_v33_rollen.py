# Tests v33 (PLAN_V20 Phase 167, Agent R): Rollen als Varianten einer Basisrolle –
# Varianten erben Pfadrechte (Montage Heizung erreicht /montage, nicht /angebote;
# Handelsvertreter-Variante = HV-Sicht ohne manuelles terminiert_selbst), HV-Migration
# (AD-Profil mit Kennzeichen → Rolle), Benutzerverwaltung zeigt/speichert Varianten
# (Dropdown, Zusatzrollen, Filter, Badges, Rolle ↔ terminiert_selbst in beide
# Richtungen), CSV-Import mit Keys und Namen, Parametrierung → Rollen (Anlegen,
# Umbenennen, Deaktivieren nur ohne aktive Benutzer, Systemrollen gesperrt, nur Admin),
# Teams-Gewerk, Einstellung phase_auto, Login-Ziel/Cookie-Dauer über die Basisrolle.
# Läuft gegen die DB-Kopie (DB_PFAD_OVERRIDE); alle Daten tragen den Präfix V33R.
import re
import unittest

from fastapi.testclient import TestClient

from app import auth, benutzer_import, lead_termin, lead_v2, rollen
from app import projektierung as proj
from app.db import SessionLocal, init_db
from app.main import app
from app.models import (AdProfil, Benutzer, Rolle, Team, TeamMitglied, einstellung_holen,
                        einstellung_setzen)

PRAEFIX = "V33R"
PIN = "4321"


def _aufraeumen(s):
    s.rollback()
    for b in s.query(Benutzer).filter(Benutzer.name.like(f"{PRAEFIX}%")):
        s.query(AdProfil).filter(AdProfil.benutzer_id == b.id).delete()
        s.query(TeamMitglied).filter(TeamMitglied.benutzer_id == b.id).delete()
        lead_termin.kanal_regel_ad_setzen(s, b.id, [])
        s.delete(b)
    for r in s.query(Rolle).filter(Rolle.key.like("v33r_%")):
        s.delete(r)
    for t in s.query(Team).filter(Team.name.like(f"{PRAEFIX}%")):
        s.delete(t)
    s.commit()
    rollen.cache_leeren()


def _client(benutzer_id: int) -> TestClient:
    c = TestClient(app, follow_redirects=False)
    c.cookies.set(auth.COOKIE_NAME, auth.cookie_wert(benutzer_id))
    return c


class Basis(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        init_db()
        cls.s = SessionLocal()
        _aufraeumen(cls.s)
        rollen.migration_v33_rollen(cls.s)
        cls.s.commit()
        rollen.cache_leeren()
        cls.admin = _client(1)

    @classmethod
    def tearDownClass(cls):
        _aufraeumen(cls.s)
        cls.s.close()

    def setUp(self):
        self.sync()

    def sync(self):
        """WAL-Lese-Schnappschuss der Testsitzung beenden (v33 Phase 172, BEGIN IMMEDIATE)
        und die Identitätskarte leeren (expire_on_commit=False): nach Schreibzugriffen über
        den TestClient vor dem nächsten Lesen/Schreiben mit self.s – alle eigenen
        Schreibzugriffe sind zu diesem Zeitpunkt committet."""
        self.s.rollback()
        self.s.expire_all()

    def benutzer(self, name, rolle, **felder):
        self.sync()
        b = Benutzer(name=f"{PRAEFIX} {name}", rolle=rolle, aktiv=True,
                     email=felder.pop("email", f"{name.lower().replace(' ', '')}@v33r.local"),
                     pin_hash=auth.pin_hash(PIN), **felder)
        auth.pin_setzen(b, PIN)
        self.s.add(b)
        self.s.commit()
        return b

    def frisch(self, b):
        self.sync()
        return self.s.get(Benutzer, b.id)

    def profil(self, b):
        self.sync()
        return self.s.query(AdProfil).filter(AdProfil.benutzer_id == b.id).first()


class Pfadrechte(Basis):
    def test_montage_heizung_erreicht_montage_nicht_angebote(self):
        b = self.benutzer("Monteur Heizung", "montage_heizung")
        c = _client(b.id)
        r = c.get("/angebote")
        self.assertEqual(r.status_code, 303)
        self.assertEqual(r.headers["location"], "/montage")
        self.assertEqual(c.get("/montage").status_code, 200)
        self.assertEqual(c.get("/benutzer").status_code, 303)
        self.assertEqual(b.basisrolle, "montage")
        self.assertEqual(b.gewerk, "heizung")
        self.assertFalse(b.hat_kennzeichen("service"))

    def test_service_elektro_erreicht_montage(self):
        b = self.benutzer("Service Elektro", "service_elektro")
        c = _client(b.id)
        self.assertEqual(c.get("/montage").status_code, 200)
        self.assertEqual(c.get("/projektierung").headers.get("location"), "/montage")
        self.assertTrue(b.hat_kennzeichen("service"))
        self.assertEqual(b.gewerk, "elektro")

    def test_handelsvertreter_variante_ist_hv_sicht_ohne_haekchen(self):
        hv = self.benutzer("HV Horst", "handelsvertreter")
        self.assertIsNone(self.profil(hv))              # kein AD-Profil von Hand
        self.assertTrue(lead_v2.ist_handelsvertreter(self.s, hv))
        self.assertTrue(lead_v2.hv_sicht(self.s, hv))
        self.assertIn(hv.id, lead_v2.handelsvertreter_ids(self.s))
        self.assertIn(hv.id, [b.id for b in lead_v2.handelsvertreter_liste(self.s)])
        from app import lead_dropdowns
        self.assertNotIn(hv.id, [b.id for b in lead_dropdowns.angestellte_ad(self.s)])
        c = _client(hv.id)
        r = c.get("/lead-management/hauptboard")
        self.assertEqual(r.status_code, 303)
        self.assertIn("/lead-management/handelsvertreter", r.headers["location"])
        r = c.get("/lead-management/handelsvertreter")
        self.assertEqual(r.status_code, 200)
        self.assertIn("Meine Leads", r.text)

    def test_projektierung_erreicht_vorgangsakte(self):
        """Orchestrator (Vorschlag S 4.4, PLAN_V20 Phase 168): die Rolle Projektierung erreicht
        die Vorgangsakte lesend (Knopf „Service-Einsatz planen“); Schreiben unter /vorgaenge
        bleibt gesperrt (PROJEKTIERUNG_SCHREIBEN), der Service-Termin läuft über /projektierung."""
        self.assertIn("/vorgaenge", auth.PROJEKTIERUNG_PFADE)
        self.assertFalse(any(p.startswith("/vorgaenge") for p in auth.PROJEKTIERUNG_SCHREIBEN))
        b = self.benutzer("Projektierung Vorgang", "projektierung")
        c = _client(b.id)
        r = c.get("/vorgaenge", follow_redirects=False)
        self.assertEqual(r.status_code, 200, (r.status_code, r.headers.get("location")))
        r = c.post("/vorgaenge/1/anschriften", data={"x": "1"}, follow_redirects=False)
        self.assertEqual(r.status_code, 303)
        self.assertEqual(r.headers["location"], "/projektierung")

    def test_aussendienst_und_hv_erreichen_kalender(self):
        """Zusatz Orchestrator (Phase 169, Rückfrage R4 Agent K): Außendienst und
        Handelsvertreter (Basisrolle aussendienst) erreichen den zentralen Kalender über
        auth.AUSSENDIENST_PFADE (reine Präfix-Liste: GET und POST unter /kalender) – Seite,
        daten.json und das Merken der eigenen Auswahl (POST /kalender/einstellung, kein 403);
        die Schreibrechte je Termin prüft kalender_zentral selbst (tests/test_v33_kalender.py)."""
        self.assertIn("/kalender", auth.AUSSENDIENST_PFADE)
        ad = self.benutzer("AD Kalender", "aussendienst")
        hv = self.benutzer("HV Kalender", "handelsvertreter")
        for person in (ad, hv):
            c = _client(person.id)
            r = c.get("/kalender")
            self.assertEqual(r.status_code, 200, (person.rolle, r.status_code, r.headers.get("location")))
            r = c.get("/kalender/daten.json")
            self.assertEqual(r.status_code, 200, person.rolle)
            self.assertTrue(r.json().get("ok"))
            r = c.post("/kalender/einstellung", json={"einstieg": "vertrieb", "gruppen": ["aussendienst"],
                                                      "wochenende": False, "ansicht": "woche"})
            self.assertNotEqual(r.status_code, 403, person.rolle)
            self.assertEqual(r.status_code, 200, (person.rolle, r.text[:200]))
            self.assertTrue(r.json().get("ok"))
        # Montage bleibt unverändert auf /montage beschränkt? Nein – /kalender steht in
        # MONTAGE_PFADE (eigene Zeile, read-only); Projektierung/Lead-Management ebenso
        for liste in (auth.MONTAGE_PFADE, auth.PROJEKTIERUNG_PFADE, auth.LEADMANAGEMENT_PFADE):
            self.assertIn("/kalender", liste)

    def test_login_ziel_und_cookie_dauer_ueber_basisrolle(self):
        b = self.benutzer("Monteur Login", "montage_elektro")
        # Cookie-Dauer: Variante der Basisrolle montage zählt als mobil
        tage = int(einstellung_holen(self.s, "sitzung_tage_mobil", str(auth.SITZUNG_TAGE_MOBIL)))
        self.assertEqual(auth.sitzungsdauer_s(self.s, b, True), tage * 86400)
        innen = self.benutzer("Innen Login", "innendienst")
        self.assertLess(auth.sitzungsdauer_s(self.s, innen, True), 2 * 86400)
        # Login-Seite markiert die Variante als mobil (data-mobil aus der Basisrolle)
        seite = TestClient(app).get("/login").text
        self.assertRegex(seite, rf'value="{b.id}"[^>]*data-mobil="1"')
        self.assertNotRegex(seite, rf'value="{innen.id}"[^>]*data-mobil="1"')
        # Login → Startseite der Basisrolle (über Redirect der Middleware)
        c = TestClient(app, follow_redirects=False)
        r = c.post("/login", data={"benutzer_id": str(b.id), "pin": PIN})
        self.assertEqual(r.status_code, 303, r.text)
        ziel = r.headers["location"]
        for _ in range(3):
            if ziel == "/montage":
                break
            r = c.get(ziel)
            if r.status_code != 303:
                break
            ziel = r.headers["location"]
        self.assertEqual(ziel, "/montage")
        self.assertEqual(c.get("/montage").status_code, 200)


class Migration(Basis):
    def test_ad_profil_mit_kennzeichen_bekommt_rolle(self):
        b = self.benutzer("Alt HV", "aussendienst")
        self.s.add(AdProfil(benutzer_id=b.id, terminiert_selbst=True, aktiv_terminierung=True))
        self.s.commit()
        rolle_only = self.benutzer("Rolle HV", "handelsvertreter")
        marker = einstellung_holen(self.s, rollen.MARKER_HV, "")
        try:
            einstellung_setzen(self.s, rollen.MARKER_HV, "")
            self.s.commit()
            meldungen = rollen.migration_v33_rollen(self.s)
            self.s.commit()
            self.assertTrue(any("Handelsvertreter-Rolle gesetzt" in m for m in meldungen), meldungen)
            self.assertEqual(self.frisch(b).rolle, "handelsvertreter")
            self.assertTrue(self.frisch(b).hat_kennzeichen("handelsvertreter"))
            # Kennzeichen bleibt gespiegelt – auch für Benutzer, die nur die Rolle tragen
            self.assertTrue(self.profil(rolle_only) is not None and self.profil(rolle_only).terminiert_selbst)
            # zweiter Lauf: still
            self.assertEqual(rollen.migration_v33_rollen(self.s), [])
        finally:
            einstellung_setzen(self.s, rollen.MARKER_HV, marker or "erledigt")
            self.s.commit()


class Benutzerverwaltung(Basis):
    def test_dropdown_filter_badges(self):
        b = self.benutzer("Liste Heizung", "montage_heizung")
        hv = self.benutzer("Liste HV", "handelsvertreter")
        html = self.admin.get("/benutzer").text
        self.assertIn('value="montage_heizung" data-basis="montage"', html)
        self.assertIn('value="service_elektro" data-basis="montage"', html)
        self.assertIn('value="handelsvertreter" data-basis="aussendienst"', html)
        self.assertIn('name="zusatz_montage_heizung"', html)
        self.assertIn('name="zusatz_montage"', html)
        self.assertNotIn('name="zusatz_admin"', html)
        zeile = html.split(f'id="zeile-{b.id}"', 1)[1].split("</tr>", 1)[0]
        self.assertIn('value="montage_heizung" data-basis="montage" selected', zeile)
        self.assertIn(f'data-rolle-kz="{b.id}"', zeile)
        self.assertIn(">Heizung<", zeile)
        self.assertIn('name="team_ids"', zeile)                 # Team-Dropdown bei Montage-Variante
        zeile_hv = html.split(f'id="zeile-{hv.id}"', 1)[1].split("</tr>", 1)[0]
        self.assertIn(">HV<", zeile_hv)
        self.assertIn(f'href="/benutzer/{hv.id}/ad-profil"', zeile_hv)
        self.assertNotIn("infotext", html.lower())
        # Filter: Basisrolle schließt Varianten ein, Variante nur sich selbst
        html = self.admin.get("/benutzer?rolle=montage").text
        self.assertIn(b.name, html)
        self.assertNotIn(hv.name, html)
        html = self.admin.get("/benutzer?rolle=montage_heizung").text
        self.assertIn(b.name, html)
        self.assertIn('value="montage_heizung" data-basis="montage" selected', html)
        html = self.admin.get("/benutzer?rolle=aussendienst").text
        self.assertIn(hv.name, html)
        self.assertNotIn(b.name, html)
        html = self.admin.get("/benutzer?rolle=handelsvertreter").text
        self.assertIn(hv.name, html)
        self.assertIn("Parametrierung → Rollen", html)

    def test_anlegen_und_aendern_mit_varianten(self):
        name = f"{PRAEFIX} Neu Service"
        r = self.admin.post("/benutzer/neu", data={"name": name, "rolle": "service_heizung",
                                                   "email": "", "pin": "482913"})
        self.assertEqual(r.status_code, 303, r.text)
        self.sync()
        b = self.s.query(Benutzer).filter_by(name=name).first()
        self.assertIsNotNone(b)
        self.assertEqual(b.rolle, "service_heizung")
        self.assertEqual(b.basisrolle, "montage")
        # unbekannter Key → Standard Außendienst
        r = self.admin.post("/benutzer/neu", data={"name": name + " 2", "rolle": "chef", "email": "x@v33r.local",
                                                   "pin": "482913"})
        self.assertEqual(r.status_code, 303)
        self.sync()
        b2 = self.s.query(Benutzer).filter_by(name=name + " 2").first()
        self.assertEqual(b2.rolle, "aussendienst")
        # Ändern: Rolle Handelsvertreter → Kennzeichen terminiert_selbst gespiegelt
        r = self.admin.post(f"/benutzer/{b2.id}/aendern",
                            data={"name": b2.name, "rolle": "handelsvertreter", "email": "x@v33r.local",
                                  "aktiv": "on", "zusatz_montage_heizung": "on"})
        self.assertEqual(r.status_code, 303, r.text)
        b2 = self.frisch(b2)
        self.assertEqual(b2.rolle, "handelsvertreter")
        self.assertIn("montage_heizung", b2.rollen_liste)
        self.assertTrue(b2.hat_rolle("montage"))
        self.assertTrue(self.profil(b2) is not None and self.profil(b2).terminiert_selbst)
        self.assertTrue(lead_v2.ist_handelsvertreter(self.s, b2))
        # zurück auf Außendienst → Kennzeichen aus, Zusatzrolle bleibt
        r = self.admin.post(f"/benutzer/{b2.id}/aendern",
                            data={"name": b2.name, "rolle": "aussendienst", "email": "x@v33r.local",
                                  "aktiv": "on", "zusatz_montage_heizung": "on"})
        self.assertEqual(r.status_code, 303)
        b2 = self.frisch(b2)
        self.assertEqual(b2.rolle, "aussendienst")
        self.assertFalse(self.profil(b2).terminiert_selbst)
        self.assertIn("montage_heizung", b2.rollen_liste)

    def test_ad_profil_haekchen_setzt_rolle(self):
        b = self.benutzer("AD Profil", "aussendienst")
        daten = {"start_adresse": "", "termin_dauer_min": "90", "puffer_min": "30",
                 "max_termine_tag": "3", "gebiet": "", "vorname": "Test"}
        r = self.admin.post(f"/benutzer/{b.id}/ad-profil", data={**daten, "terminiert_selbst": "on"})
        self.assertEqual(r.status_code, 303, r.text)
        b = self.frisch(b)
        self.assertEqual(b.rolle, "handelsvertreter")
        self.assertTrue(self.profil(b).terminiert_selbst)
        seite = self.admin.get(f"/benutzer/{b.id}/ad-profil").text
        self.assertIn('name="terminiert_selbst"', seite)
        self.assertIn("Kennzeichen Handelsvertreter", seite)
        self.assertNotIn('name="infotext"', seite)
        r = self.admin.post(f"/benutzer/{b.id}/ad-profil", data=daten)
        self.assertEqual(r.status_code, 303)
        b = self.frisch(b)
        self.assertEqual(b.rolle, "aussendienst")
        self.assertFalse(self.profil(b).terminiert_selbst)
        self.assertFalse(lead_v2.ist_handelsvertreter(self.s, b))


class CsvImport(Basis):
    def test_rolle_zuordnen_keys_und_namen(self):
        self.assertEqual(benutzer_import.rolle_zuordnen("montage_heizung"), "montage_heizung")
        self.assertEqual(benutzer_import.rolle_zuordnen("Montage Elektro"), "montage_elektro")
        self.assertEqual(benutzer_import.rolle_zuordnen("service heizung"), "service_heizung")
        self.assertEqual(benutzer_import.rolle_zuordnen("Handelsvertreter"), "handelsvertreter")
        self.assertEqual(benutzer_import.rolle_zuordnen("Außendienst"), "aussendienst")
        self.assertEqual(benutzer_import.rolle_zuordnen("Lead Management"), "leadmanagement")
        self.assertIsNone(benutzer_import.rolle_zuordnen("Chef"))
        self.assertIn("Montage Heizung", benutzer_import.rollen_namen_text())
        seite = self.admin.get("/benutzer/import").text
        self.assertIn("Service Elektro", seite)

    def test_import_mit_variante_und_hv(self):
        team = self.s.query(Team).filter(Team.aktiv.is_(True)).first()
        csv_text = ("Name;Rolle;E-Mail;Team;Vertriebskanal\n"
                    f"{PRAEFIX} Import Elektro;montage_elektro;;{team.name if team else ''};\n"
                    f"{PRAEFIX} Import HV;Handelsvertreter;hv.import@v33r.local;;\n")
        r = self.admin.post("/benutzer/import", data={"aktion": "vorschau", "csv_text": csv_text})
        self.assertEqual(r.status_code, 200)
        self.assertIn("alle Zeilen fehlerfrei", r.text)
        r = self.admin.post("/benutzer/import", data={"aktion": "ausfuehren", "csv_text": csv_text})
        self.assertEqual(r.status_code, 200, r.text)
        self.assertIn("2 Benutzer angelegt", r.text)
        self.sync()
        elektro = self.s.query(Benutzer).filter_by(name=f"{PRAEFIX} Import Elektro").first()
        hv = self.s.query(Benutzer).filter_by(name=f"{PRAEFIX} Import HV").first()
        self.assertEqual(elektro.rolle, "montage_elektro")
        self.assertEqual(elektro.basisrolle, "montage")
        self.assertEqual(hv.rolle, "handelsvertreter")
        self.assertTrue(self.profil(hv) is not None and self.profil(hv).terminiert_selbst)
        # Variante ohne E-Mail mit Kanal → Fehler „nur für Außendienst“ bleibt für Montage
        zeilen, _ = benutzer_import.csv_lesen("Name;Rolle;E-Mail;Team;Vertriebskanal\n"
                                              f"{PRAEFIX} Import Falsch;Montage Heizung;;;Enni\n")
        zeilen = benutzer_import.pruefen(self.s, zeilen)
        self.assertTrue(any("nur für Außendienst" in f for f in zeilen[0].fehler), zeilen[0].fehler)


class Parametrierung(Basis):
    def test_rollen_seite_anlegen_umbenennen_deaktivieren(self):
        r = self.admin.get("/parametrierung/rollen")
        self.assertEqual(r.status_code, 200)
        for key in ("montage_heizung", "service_elektro", "handelsvertreter"):
            self.assertIn(f'data-rolle="{key}"', r.text)
        self.assertIn("Montage Heizung", r.text)
        self.assertIn(">System<", r.text)
        # Verteilerseite: Eintrag nur für Admin
        self.assertIn('href="/parametrierung/rollen"', self.admin.get("/parametrierung").text)
        innen = self.benutzer("Innen Rollen", "innendienst")
        c = _client(innen.id)
        self.assertNotIn('href="/parametrierung/rollen"', c.get("/parametrierung").text)
        self.assertEqual(c.get("/parametrierung/rollen").status_code, 303)
        self.assertEqual(c.post("/parametrierung/rollen", data={"name": "V33R Fremd", "basisrolle": "montage"}).status_code, 303)
        self.sync()
        self.assertIsNone(self.s.query(Rolle).filter_by(key="v33r_fremd").first())
        # Anlegen (Key aus dem Namen)
        r = self.admin.post("/parametrierung/rollen", data={"name": "V33R Service Klima", "basisrolle": "montage",
                                                             "gewerk": "elektro", "service": "on"})
        self.assertEqual(r.status_code, 303, r.text)
        self.assertIn("angelegt", r.headers["location"])
        self.sync()
        rolle = self.s.query(Rolle).filter_by(key="v33r_service_klima").first()
        self.assertIsNotNone(rolle)
        self.assertTrue(rolle.service and rolle.gewerk == "elektro" and rolle.basisrolle == "montage")
        rollen.cache_leeren()
        self.assertEqual(rollen.basisrolle_von("v33r_service_klima"), "montage")
        self.assertIn("v33r_service_klima", rollen.keys_fuer_basis("montage"))
        seite = self.admin.get("/parametrierung/rollen").text
        self.assertIn('data-rolle="v33r_service_klima"', seite)
        # doppelt → Fehler
        r = self.admin.post("/parametrierung/rollen", data={"name": "V33R Service Klima", "basisrolle": "montage"})
        self.assertIn("fehler=1", r.headers["location"])
        # Benutzerverwaltung bietet die neue Rolle
        self.assertIn('value="v33r_service_klima" data-basis="montage"', self.admin.get("/benutzer").text)
        # Umbenennen
        r = self.admin.post("/parametrierung/rollen/v33r_service_klima/umbenennen", data={"name": "V33R Klima-Service"})
        self.assertEqual(r.status_code, 303)
        self.sync()
        self.assertEqual(self.s.get(Rolle, rolle.id).name, "V33R Klima-Service")
        rollen.cache_leeren()
        self.assertEqual(rollen.name_von("v33r_service_klima"), "V33R Klima-Service")
        # Deaktivieren mit aktivem Benutzer → Meldung mit Namen
        traeger = self.benutzer("Traeger Klima", "v33r_service_klima")
        r = self.admin.post("/parametrierung/rollen/v33r_service_klima/aktiv", data={"aktiv": "0"})
        self.assertIn("fehler=1", r.headers["location"])
        self.assertIn("Traeger", r.headers["location"].replace("+", " "))
        self.sync()
        self.assertTrue(self.s.get(Rolle, rolle.id).aktiv)
        # Benutzer inaktiv → deaktivierbar; der Benutzer behält die Rolle im Dropdown
        traeger = self.frisch(traeger)
        traeger.aktiv = False
        self.s.commit()
        r = self.admin.post("/parametrierung/rollen/v33r_service_klima/aktiv", data={"aktiv": "0"})
        self.assertNotIn("fehler=1", r.headers["location"])
        self.sync()
        self.assertFalse(self.s.get(Rolle, rolle.id).aktiv)
        rollen.cache_leeren()
        html = self.admin.get("/benutzer?aktiv=0").text
        zeile = html.split(f'id="zeile-{traeger.id}"', 1)[1].split("</tr>", 1)[0]
        self.assertIn('value="v33r_service_klima" data-basis="montage" selected', zeile)
        self.assertNotIn('value="v33r_service_klima"', html.split('<h2>Neuer Benutzer</h2>', 1)[1])
        self.assertIsNone(benutzer_import.rolle_zuordnen("v33r_service_klima"))
        # wieder aktivieren
        r = self.admin.post("/parametrierung/rollen/v33r_service_klima/aktiv", data={"aktiv": "1"})
        self.assertNotIn("fehler=1", r.headers["location"])
        self.sync()
        self.assertTrue(self.s.get(Rolle, rolle.id).aktiv)
        # Systemrollen gesperrt
        r = self.admin.post("/parametrierung/rollen/montage/aktiv", data={"aktiv": "0"})
        self.assertIn("fehler=1", r.headers["location"])
        r = self.admin.post("/parametrierung/rollen/montage/umbenennen", data={"name": "Monteure"})
        self.assertIn("fehler=1", r.headers["location"])
        rollen.cache_leeren()
        self.assertEqual(rollen.name_von("montage"), "Montage")

    def test_teams_gewerk(self):
        seite = self.admin.get("/parametrierung/teams").text
        self.assertIn('name="gewerk"', seite)
        r = self.admin.post("/parametrierung/teams", data={"name": f"{PRAEFIX} Elektro-Team", "typ": "montage",
                                                           "gewerk": "elektro", "farbe": "#2d6bd6"})
        self.assertEqual(r.status_code, 303)
        self.sync()
        team = self.s.query(Team).filter_by(name=f"{PRAEFIX} Elektro-Team").first()
        self.assertEqual(team.gewerk, "elektro")
        team_id, team_name = team.id, team.name
        # Ändern ohne Gewerk-Feld → bleibt; mit heizung → heizung
        r = self.admin.post("/parametrierung/teams", data={"team_id": str(team_id), "name": team_name,
                                                           "typ": "montage", "aktiv": "on"})
        self.sync()
        self.assertEqual(self.s.get(Team, team_id).gewerk, "elektro")
        r = self.admin.post("/parametrierung/teams", data={"team_id": str(team_id), "name": team_name,
                                                           "typ": "montage", "aktiv": "on", "gewerk": "heizung"})
        self.sync()
        self.assertEqual(self.s.get(Team, team_id).gewerk, "heizung")
        seite = self.admin.get("/parametrierung/teams").text
        self.assertRegex(seite, r'name="gewerk"[^>]*>\s*<option value=""[^>]*>–</option>')

    def test_phase_auto_einstellung(self):
        alt = proj.parameter_holen(self.s, "phase_auto", "an")
        protokoll_alt = proj.parameter_holen(self.s, "einstellungs_protokoll", "")
        try:
            seite = self.admin.get("/parametrierung/projektierung-einstellungen").text
            self.assertIn('name="phase_auto"', seite)
            self.assertIn('name="phase_auto_dabei"', seite)
            if alt != "aus":
                self.assertRegex(seite, r'name="phase_auto" checked')
            r = self.admin.post("/parametrierung/projektierung-einstellungen",
                                data={"phase_auto_dabei": "1", "waechter_modus": "warnen"})
            self.assertEqual(r.status_code, 303)
            self.sync()
            self.assertEqual(proj.parameter_holen(self.s, "phase_auto", "an"), "aus")
            self.assertIn("phase_auto", proj.parameter_holen(self.s, "einstellungs_protokoll", ""))
            r = self.admin.post("/parametrierung/projektierung-einstellungen",
                                data={"phase_auto_dabei": "1", "phase_auto": "on", "waechter_modus": "warnen"})
            self.sync()
            self.assertEqual(proj.parameter_holen(self.s, "phase_auto", "an"), "an")
            # Formular ohne phase_auto_dabei lässt den Wert stehen
            self.admin.post("/parametrierung/projektierung-einstellungen", data={"waechter_modus": "warnen"})
            self.sync()
            self.assertEqual(proj.parameter_holen(self.s, "phase_auto", "an"), "an")
        finally:
            self.sync()
            proj.parameter_setzen(self.s, "phase_auto", alt)
            proj.parameter_setzen(self.s, "einstellungs_protokoll", protokoll_alt)
            self.s.commit()


class Katalog(Basis):
    def test_helfer(self):
        liste = rollen.katalog_liste()
        self.assertEqual([e["key"] for e in liste][:6], list(rollen.BASISROLLEN))
        self.assertTrue(all(not e["variante"] for e in liste[:6]))
        self.assertTrue(rollen.key_gueltig("montage_heizung"))
        self.assertFalse(rollen.key_gueltig("chef"))
        self.assertTrue(rollen.key_gueltig("chef", zusaetzlich=("chef",)))
        self.assertEqual([k for k, _ in rollen.kennzeichen_badges("service_elektro")], ["Elektro", "Service"])
        self.assertEqual([k for k, _ in rollen.kennzeichen_badges("handelsvertreter")], ["HV"])
        self.assertEqual(rollen.kennzeichen_badges("montage"), [])
        self.assertIn("handelsvertreter", rollen.hv_keys())
        b = Benutzer(name=f"{PRAEFIX} Katalog", rolle="aussendienst", rollen="aussendienst,service_heizung")
        self.assertEqual([k for k, _ in rollen.benutzer_badges(b)], ["Heizung", "Service"])
        # hv_rolle_setzen in beide Richtungen
        self.assertTrue(rollen.hv_rolle_setzen(self.s, b, True))
        self.assertEqual(b.rolle, "handelsvertreter")
        self.assertIn("service_heizung", b.rollen_liste)
        self.assertFalse(rollen.hv_rolle_setzen(self.s, b, True))
        self.assertTrue(rollen.hv_rolle_setzen(self.s, b, False))
        self.assertEqual(b.rolle, "aussendienst")
        self.assertEqual(b.rollen_liste, ["aussendienst", "service_heizung"])
        m = Benutzer(name=f"{PRAEFIX} Katalog 2", rolle="montage")
        self.assertFalse(rollen.hv_rolle_setzen(self.s, m, True))
        self.assertEqual(m.rolle, "montage")
        anzahl = rollen.benutzer_anzahl(self.s)
        self.assertGreaterEqual(anzahl.get("admin", 0), 1)


if __name__ == "__main__":
    unittest.main()
