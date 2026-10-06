# v26 (PLAN_PROJ_V5 Phase 125): Parametrierung neu gegliedert – Übersicht mit
# Suchfeld und fünf Bereichskarten, neue Seiten /parametrierung/angebotstool
# (Angebotstool-Einstellungen) und /parametrierung/logik (Logik & Importe),
# Referer-Rücksprung der POST-Routen, gegliederte Projektierung-Einstellungen
# (Heizreport-Block umgezogen). Läuft gegen die Entwicklungs-DB: Login Benutzer 1
# (Admin, PIN 1234); der Innendienst-Testbenutzer und alle geänderten Werte
# werden wieder zurückgesetzt.
import re
import unittest
import warnings

warnings.filterwarnings("ignore")

from fastapi.testclient import TestClient

from app import auth
from app import leadmanagement as lead_kern
from app import projektierung as kern
from app.db import SessionLocal, init_db
from app.main import app
from app.models import Benutzer, einstellung_holen, einstellung_setzen

# Die 22 Links der Button-Reihe der alten Übersicht (v25) – jeder genau einmal
ALTE_BUTTON_REIHE = [
    "/parametrierung/monday", "/parametrierung/vorlagen", "/parametrierung/signaturen",
    "/parametrierung/profile", "/parametrierung/bza-ersteller",
    "/parametrierung/projektierung-logik", "/parametrierung/stuecklisten",
    "/parametrierung/kl-logik", "/parametrierung/teams", "/parametrierung/subunternehmer",
    "/parametrierung/fehlerprotokoll", "/parametrierung/projektierung-einstellungen",
    "/parametrierung/bestandsimport", "/parametrierung/golive",
    "/parametrierung/kunden-dubletten", "/parametrierung/lead-quellen",
    "/parametrierung/lead-parser", "/parametrierung/lead-routing",
    "/parametrierung/lead-vorlagen", "/parametrierung/lead-logik",
    "/parametrierung/lead-einstellungen", "/parametrierung/lead-demo",
]
# Einträge nur für Admins (inkl. der neuen Heizreport-Seite und des Anker-Links)
ADMIN_EINTRAEGE = [
    "/benutzer", "/parametrierung/projektierung-einstellungen", "/parametrierung/heizreport",
    "/parametrierung/bestandsimport", "/parametrierung/golive",
    "/parametrierung/kunden-dubletten", "/parametrierung/lead-einstellungen",
    "/parametrierung/lead-demo", "/parametrierung/projektierung-einstellungen#mailprotokoll",
]
LEAD_EINTRAEGE = ["/parametrierung/lead-quellen", "/parametrierung/lead-parser",
                  "/parametrierung/lead-routing", "/parametrierung/lead-vorlagen",
                  "/parametrierung/lead-logik"]
NEUE_SEITEN = ["/parametrierung/angebotstool", "/parametrierung/logik"]
TESTNAME = "v26-Test Innendienst"


def hrefs(html: str) -> list[str]:
    return re.findall(r'href="(/[^"]*)"', html)


class Basis(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        init_db()
        cls.s = SessionLocal()
        cls.client = TestClient(app)
        cls.client.post("/login", data={"benutzer_id": "1", "pin": "1234"})
        # Innendienst-Testbenutzer (Nicht-Admin) mit eigenem Client (Cookie-Login)
        alt = cls.s.query(Benutzer).filter(Benutzer.name == TESTNAME).all()
        for b in alt:
            cls.s.delete(b)
        cls.innen = Benutzer(name=TESTNAME, rolle="innendienst", aktiv=True,
                             email="v26-innen@test.local", pin_hash=auth.pin_hash("4321"))
        cls.s.add(cls.innen)
        cls.s.commit()
        cls.innen_client = TestClient(app)
        cls.innen_client.cookies.set(auth.COOKIE_NAME, auth.cookie_wert(cls.innen.id))

    @classmethod
    def tearDownClass(cls):
        for b in cls.s.query(Benutzer).filter(Benutzer.name == TESTNAME).all():
            cls.s.delete(b)
        cls.s.commit()
        cls.s.close()


class Uebersicht(Basis):
    def test_alle_links_der_alten_button_reihe_genau_einmal(self):
        r = self.client.get("/parametrierung")
        self.assertEqual(r.status_code, 200)
        for pfad in ALTE_BUTTON_REIHE:
            self.assertEqual(r.text.count(f'href="{pfad}"'), 1, pfad)
        # „Neu einlesen“ (bestehende POST-Route) und die beiden neuen Seiten
        self.assertEqual(r.text.count('action="/parametrierung/neu-einlesen"'), 1)
        # Zusatz-Einträge genau einmal im Karten-Raster (/benutzer und /artikel
        # stehen zusätzlich im Hauptmenü der Kopfzeile)
        raster = r.text.split('id="param-raster"')[1].split('id="param-leer"')[0]
        for pfad in NEUE_SEITEN + ["/benutzer", "/artikel", "/parametrierung/heizreport",
                                   "/parametrierung/artikel/kl-import"]:
            self.assertEqual(raster.count(f'href="{pfad}"'), 1, pfad)
        # Anker-Einträge der Protokolle
        for anker in ("/parametrierung/angebotstool#loeschprotokoll",
                      "/parametrierung/angebotstool#versand",
                      "/parametrierung/angebotstool#ablehnung",
                      "/parametrierung/projektierung-einstellungen#mailprotokoll"):
            self.assertIn(f'href="{anker}"', r.text, anker)
        # fünf Bereichskarten, Suchfeld, Go-live-Badge „<n>/11 grün“
        for bereich in ("bereich-allgemein", "bereich-angebotstool", "bereich-projektierung",
                        "bereich-lead", "bereich-system"):
            self.assertIn(f'id="{bereich}"', r.text, bereich)
        self.assertIn('id="param-suche"', r.text)
        self.assertRegex(r.text, r"\d+/11 grün")
        # keine Inline-Formulare mehr auf der Übersicht
        self.assertNotIn('action="/parametrierung/einstellungen"', r.text)
        self.assertNotIn("Eingelesene Logik", r.text)

    def test_meldung_wird_angezeigt(self):
        r = self.client.get("/parametrierung?meldung=Einstellungen+gespeichert")
        self.assertIn("Einstellungen gespeichert", r.text)

    def test_nicht_admin_sieht_keine_admin_eintraege(self):
        r = self.innen_client.get("/parametrierung")
        self.assertEqual(r.status_code, 200)
        for pfad in ADMIN_EINTRAEGE:
            self.assertNotIn(f'href="{pfad}"', r.text, pfad)
        self.assertNotIn("/11 grün", r.text)
        # Nicht-Admin-Einträge bleiben
        for pfad in ("/parametrierung/vorlagen", "/parametrierung/teams",
                     "/parametrierung/fehlerprotokoll", "/parametrierung/angebotstool",
                     "/parametrierung/logik"):
            self.assertEqual(r.text.count(f'href="{pfad}"'), 1, pfad)
        self.assertNotIn("Zur Parametrierung", r.text)

    def test_ohne_lead_modul_keine_lead_karte(self):
        # lead_modul_sichtbar: Admin immer; Innendienst nur bei lead_freigabe_modus „alle“
        vorher = lead_kern.parameter_holen(self.s, "lead_freigabe_modus", "")
        try:
            lead_kern.parameter_setzen(self.s, "lead_freigabe_modus", "admin")
            self.s.commit()
            r = self.innen_client.get("/parametrierung")
            self.assertEqual(r.status_code, 200)
            self.assertNotIn('id="bereich-lead"', r.text)
            for pfad in LEAD_EINTRAEGE:
                self.assertNotIn(f'href="{pfad}"', r.text, pfad)
            # mit Lead-Modul: Lead-Karte da, Admin-Einträge der Karte weiterhin nicht
            lead_kern.parameter_setzen(self.s, "lead_freigabe_modus", "alle")
            self.s.commit()
            r = self.innen_client.get("/parametrierung")
            self.assertIn('id="bereich-lead"', r.text)
            for pfad in LEAD_EINTRAEGE:
                self.assertEqual(r.text.count(f'href="{pfad}"'), 1, pfad)
            self.assertNotIn('href="/parametrierung/lead-einstellungen"', r.text)
            self.assertNotIn('href="/parametrierung/lead-demo"', r.text)
        finally:
            lead_kern.parameter_setzen(self.s, "lead_freigabe_modus", vorher)
            self.s.commit()


class NeueSeiten(Basis):
    def test_angebotstool_seite(self):
        r = self.client.get("/parametrierung/angebotstool")
        self.assertEqual(r.status_code, 200)
        self.assertIn("Deckungsbeitrags-Ampel", r.text)
        # Formulare unverändert: action, Feldnamen, Hidden-Felder
        self.assertGreaterEqual(r.text.count('action="/parametrierung/einstellungen"'), 7)
        for name in ("db_ampel_rot_unter", "db_ampel_gruen_ueber", "db_ampel_rot_unter_WP",
                     "mail_absender", "mail_postfach", "mail_bcc", "kombi_vorlage_betreff",
                     "kombi_vorlage_text", "gewerke_artikel", "signatur_fern_aktiv",
                     "signatur_fern_gueltig_tage", "signatur_fern_basis_url",
                     "ablehnung_auto_tage"):
            self.assertIn(f'name="{name}"', r.text, name)
        for hidden in ("db_sparten_formular", "mail_formular", "kombi_formular",
                       "gewerke_formular", "fern_formular", "ablehnung_formular"):
            self.assertIn(f'name="{hidden}" value="1"', r.text, hidden)
        self.assertIn('action="/parametrierung/ablehnungsgruende"', r.text)
        for anker in ("versand", "ablehnung", "loeschprotokoll"):
            self.assertIn(f'id="{anker}"', r.text, anker)
        self.assertNotIn("Eingelesene Logik", r.text)

    def test_logik_seite(self):
        r = self.client.get("/parametrierung/logik")
        self.assertEqual(r.status_code, 200)
        for text in ("Eingelesene Logik", "zuletzt eingelesen", "Angebotsaufbau",
                     "KfW-Parameter", "Klimakonfigurator",
                     'action="/parametrierung/neu-einlesen"',
                     'action="/parametrierung/artikel/kl-import"',
                     'href="/parametrierung/artikel/kl-import"'):
            self.assertIn(text, r.text, text)
        self.assertNotIn("Deckungsbeitrags-Ampel", r.text)
        self.assertNotIn('action="/parametrierung/einstellungen"', r.text)

    def test_neue_seiten_auch_fuer_innendienst(self):
        for pfad in NEUE_SEITEN:
            r = self.innen_client.get(pfad)
            self.assertEqual(r.status_code, 200, pfad)


class Rueckkehr(Basis):
    """POST-Routen kehren per Referer auf die Seite zurück, von der sie kamen –
    nur Pfade unter /parametrierung, Fallback Übersicht."""

    def test_einstellungen_speichern_von_angebotstool_seite(self):
        vorher = einstellung_holen(self.s, "db_ampel_rot_unter", "9000")
        try:
            r = self.client.post("/parametrierung/einstellungen",
                                 data={"db_ampel_rot_unter": "9123",
                                       "db_ampel_gruen_ueber": "10000"},
                                 headers={"referer": "http://testserver/parametrierung/angebotstool"},
                                 follow_redirects=False)
            self.assertEqual(r.status_code, 303)
            self.assertTrue(r.headers["location"].startswith("/parametrierung/angebotstool"),
                            r.headers["location"])
            self.assertIn("meldung=Einstellungen+gespeichert", r.headers["location"])
            self.s.expire_all()
            self.assertEqual(einstellung_holen(self.s, "db_ampel_rot_unter", ""), "9123")
            # Seite zeigt den Wert und die Meldung
            seite = self.client.get(r.headers["location"]).text
            self.assertIn('value="9123"', seite)
            self.assertIn("Einstellungen gespeichert", seite)
        finally:
            einstellung_setzen(self.s, "db_ampel_rot_unter", vorher)
            self.s.commit()

    def test_fallback_und_fremde_referer(self):
        daten = {"aktion": "umschalten", "id": "0"}            # ändert nichts
        # ohne Referer → Übersicht
        r = self.client.post("/parametrierung/ablehnungsgruende", data=daten,
                             follow_redirects=False)
        self.assertEqual(r.headers["location"], "/parametrierung")
        # fremder Pfad → Übersicht
        r = self.client.post("/parametrierung/ablehnungsgruende", data=daten,
                             headers={"referer": "http://testserver/angebote/1"},
                             follow_redirects=False)
        self.assertEqual(r.headers["location"], "/parametrierung")
        # Pfad mit Query → nur der Pfad, dazu der Anker des Abschnitts
        r = self.client.post("/parametrierung/ablehnungsgruende", data=daten,
                             headers={"referer": "http://testserver/parametrierung/angebotstool?meldung=x"},
                             follow_redirects=False)
        self.assertEqual(r.headers["location"], "/parametrierung/angebotstool#ablehnung")
        # kein offener Redirect: Host wird verworfen, nur der Pfad zählt
        r = self.client.post("/parametrierung/ablehnungsgruende", data=daten,
                             headers={"referer": "https://fremd.example//evil"},
                             follow_redirects=False)
        self.assertEqual(r.headers["location"], "/parametrierung")

    def test_neu_einlesen_kehrt_auf_logik_seite_zurueck(self):
        r = self.client.post("/parametrierung/neu-einlesen",
                             headers={"referer": "http://testserver/parametrierung/logik"},
                             follow_redirects=False)
        self.assertEqual(r.status_code, 303)
        self.assertTrue(r.headers["location"].startswith("/parametrierung/logik?meldung="),
                        r.headers["location"])
        # von der Übersicht aus zurück zur Übersicht (Meldung wie bisher)
        r = self.client.post("/parametrierung/neu-einlesen",
                             headers={"referer": "http://testserver/parametrierung"},
                             follow_redirects=False)
        self.assertTrue(r.headers["location"].startswith("/parametrierung?meldung="),
                        r.headers["location"])


class ProjektierungEinstellungen(Basis):
    def test_gegliedert_ohne_heizreport_block(self):
        r = self.client.get("/parametrierung/projektierung-einstellungen")
        self.assertEqual(r.status_code, 200)
        for anker in ("freigabe", "vorlauf", "verantwortliche", "mails", "storno", "galerie",
                      "portale", "ugl", "kalender", "terminmail", "bza-mail", "mailprotokoll"):
            self.assertIn(f'id="{anker}"', r.text, anker)
        self.assertIn('class="pe-nav"', r.text)
        self.assertIn("aktionsleiste-unten", r.text)
        # Heizreport-Block und Portal-Feld umgezogen – nur der Hinweis-Link bleibt
        self.assertIn('href="/parametrierung/heizreport"', r.text)
        for alt in ('name="heizreport_api_url"', 'name="url_heizreport"',
                    "heizreport-test", 'id="heizreport"'):
            self.assertNotIn(alt, r.text, alt)
        # Feldnamen des Formulars unverändert
        for name in ("freigabe_modus", "pilot_dabei", "pilot_benutzer", "vorlauf_gruen_ab_wochen",
                     "vorlauf_gelb_ab_wochen", "standard_pl", "standard_fp", "standard_ep",
                     "buchhaltung", "absender", "gruende", "galerie_zusatzordner",
                     "galerie_original", "url_bza_portal", "url_kfw_zuschussportal",
                     "url_spotmyenergy", "url_gc_online", "collin_kundennummer",
                     "collin_lieferantennummer", "stueckliste_standard_lieferant",
                     "ugl_lieferadresse", "lager_adresse", "bza_fachunternehmer",
                     "outlook_kalender_modus", "outlook_kalender_adresse", "basis_url",
                     "terminmail_betreff", "terminmail_text", "terminmail_vorbereitung",
                     "bza_mail_dabei", "bza_mail_aktiv", "bza_mail_betreff", "bza_mail_text",
                     "projekt_testadresse"):
            self.assertIn(f'name="{name}"', r.text, name)
        self.assertEqual(r.text.count('action="/parametrierung/projektierung-einstellungen"'), 1)

    def test_speichern_laesst_url_heizreport_unberuehrt(self):
        vorher = kern.parameter_holen(self.s, "url_heizreport", "")
        bza_vorher = kern.parameter_holen(self.s, "url_bza_portal", "")
        try:
            kern.parameter_setzen(self.s, "url_heizreport", "https://heizreport.test/v26")
            self.s.commit()
            r = self.client.post("/parametrierung/projektierung-einstellungen",
                                 data={"freigabe_modus": kern.freigabe_modus(self.s),
                                       "url_bza_portal": bza_vorher},
                                 follow_redirects=False)
            self.assertEqual(r.status_code, 303)
            self.s.expire_all()
            self.assertEqual(kern.parameter_holen(self.s, "url_heizreport", ""),
                             "https://heizreport.test/v26")
            self.assertEqual(kern.parameter_holen(self.s, "url_bza_portal", ""), bza_vorher)
        finally:
            kern.parameter_setzen(self.s, "url_heizreport", vorher)
            self.s.commit()

    def test_nicht_admin_wird_umgeleitet(self):
        r = self.innen_client.get("/parametrierung/projektierung-einstellungen",
                                  follow_redirects=False)
        self.assertEqual(r.status_code, 303)
        self.assertEqual(r.headers["location"], "/parametrierung")


if __name__ == "__main__":
    unittest.main()
