# Tests PLAN_V22 Phase 193 (v36, Agent B2 – Cloover-Rate im Angebot): app/cloover.py (relevant,
# voraussetzungen, rate_aktualisieren außerhalb der Sitzung, kontext_fuer_pdf, Platzhalter), Editor-Karte
# „Finanzierung (Cloover)“ (Routen angebote_cloover.py), PDF-Karte/Box/Fußnote im Layout v3 (Kontext + HTML
# ohne Browser), fpdf2-Rückfall mit [CLOOVER] (pypdf-Text), Mail-Platzhalter, AD-Lesesicht, Kopie/Version,
# Migration migriere_cloover_platzhalter (idempotent).
# Kontrollwerte des Plans: WP Endbetrag 42.830,55 € (Netto 35.992,06 €, 19 %), Förderung 16.500,00 €,
# Laufzeit 15 Jahre → 389,99 € ohne / 242,70 € mit Förderung (Antwort der Test-Umgebung, hier gemockt).
# Kein Netzzugriff: cloover_api.modus/assets_fuer/rate_berechnen (und foerderung_cent für „mit Förderung“)
# sind gemockt, _roh_anfrage ist als Sicherheitsnetz gesperrt. Läuft gegen DB_PFAD_OVERRIDE (Kopie),
# Testbasis tests/v34_e_basis.py (Testkunde mit eigener E-Mail, Admin-Cookie ID 1, Aufräumen am Ende).
import io
import json
import re
import unittest
from pathlib import Path
import warnings
from contextlib import ExitStack
from datetime import date
from unittest import mock

warnings.filterwarnings("ignore")

from app import (angebot_aufbau, angebotsprofile, auth, cloover, cloover_api, db, mail_vorlagen, pdf_export,
                 pdf_html, pdf_kontext)
from app import logik as logik_modul
from app.models import Angebot, AngebotsPosition, Einstellung, Kunde, Profil, Textblock, einstellung_holen, \
    einstellung_setzen
from tests.test_regression import KONTROLL_SZENARIO
from tests.v34_e_basis import KL_GERAET, Basis, pdf_text

FIXTURES_V36 = Path(__file__).resolve().parent / "fixtures" / "v36"

# Positions-Snapshots: Netto 35.992,06 € → 19 % USt 6.838,49 € → Endbetrag 42.830,55 € (Plan-Kontrollwert)
WP_PLAN = dict(sort=1, block_nr=1, gruppe="Bosch Monoblock Wärmepumpe CS3800i AW Paket", pos_nr="045",
               bezeichnung="Bosch CS3800i AW 7 OR-S Paket", beschreibung="Paket", menge=1.0, einheit="psl.",
               e_preis_cent=3_599_206, ek_cent=2_000_000)
PV_PLAN = dict(sort=1, block_nr=1, gruppe="Komplettpaket PV-Anlage", pos_nr="PV001",
               bezeichnung="PV-Anlage 10 kWp", beschreibung="Module, Wechselrichter, Speicher", menge=1.0,
               einheit="psl.", e_preis_cent=2_000_000, ek_cent=1_200_000)
WB_PLAN = dict(sort=1, block_nr=1, gruppe="Wallbox", pos_nr="WB001", bezeichnung="Mennekes AMTRON 4You 310",
               beschreibung="Wallbox", menge=1.0, einheit="Stück", e_preis_cent=223_570, ek_cent=150_000)
FOERDERUNG = 1_650_000
ENDBETRAG_WP = 4_283_055
HEUTE = date.today().strftime("%d.%m.%Y")


def _fehler(meldung: str):
    def wirft(*_a, **_k):
        raise cloover_api.ClooverFehler(meldung, 503)
    return wirft


class _Rate(Basis):
    EMAIL = "v36b2-rate@test.local"
    NACHNAME = "V36B2 Rate"
    AD_NAME = "V36B2 Rate-AD"

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.kunde.telefon = "0203 1234567"
        cls.s.commit()
        # Sicherheitsnetz: nie ein echter Cloover-Aufruf in den Tests
        netz = mock.patch.object(cloover_api, "_roh_anfrage",
                                 side_effect=AssertionError("Netzaufruf in Tests nicht erlaubt"))
        netz.start()
        cls.addClassCleanup(netz.stop)
        with db.kurz(schreibend=False) as s:
            cls.engine_vorher = einstellung_holen(s, pdf_html.EINSTELLUNG_ENGINE, "")
            cls.sparten_vorher = einstellung_holen(s, "cloover_sparten", "")

    @classmethod
    def tearDownClass(cls):
        with db.kurz() as s:
            einstellung_setzen(s, pdf_html.EINSTELLUNG_ENGINE, cls.engine_vorher)
            einstellung_setzen(s, "cloover_sparten", cls.sparten_vorher)
        super().tearDownClass()

    def setUp(self):
        super().setUp()
        cloover_api.cache_leeren()

    # --- Mocks ---------------------------------------------------------------------------------
    def mocks(self, rate_ohne=38999, rate_mit=24270, foerderung=None, modus="test", fehler=None, quelle="v2"):
        """ExitStack mit gemocktem Client: modus, assets_fuer, rate_berechnen (Mock, prüfbar), optional
        foerderung_cent (WP mit Förderung). Liefert (stack, rate_berechnen-Mock)."""
        stack = ExitStack()
        stack.enter_context(mock.patch.object(cloover_api, "modus", return_value=modus))
        stack.enter_context(mock.patch.object(
            cloover_api, "assets_fuer",
            side_effect=lambda session, angebot: [{"type": "Heat pump", "priceInfo": {
                "price": 35992.06, "vatPercentage": 19, "subsidy": 16500, "currency": "EUR"}}]))
        if foerderung is not None:
            stack.enter_context(mock.patch.object(cloover_api, "foerderung_cent", return_value=foerderung))
        if fehler:
            rate = mock.Mock(side_effect=_fehler(fehler))
        else:
            rate = mock.Mock(return_value={"rate_ohne_cent": rate_ohne, "rate_mit_cent": rate_mit,
                                           "quelle": quelle, "antwort": {"monthlyPayment": rate_ohne / 100}})
        stack.enter_context(mock.patch.object(cloover_api, "rate_berechnen", rate))
        return stack, rate

    def wp(self, **json_werte) -> Angebot:
        a = self.angebot("WP", [WP_PLAN])
        if json_werte:
            cloover.json_schreiben(a, **json_werte)
            self.s.commit()
        self.assertEqual(a.summen()["endbetrag"], ENDBETRAG_WP)
        return a

    def daten(self, angebot) -> dict:
        return cloover.json_lesen(self.frisch(angebot))

    def frisch(self, angebot) -> Angebot:
        """Angebot neu aus der Datenbank (rate_aktualisieren schreibt über eine eigene kurze Sitzung)."""
        self.s.expire_all()
        return self.s.get(Angebot, angebot.id)

    def engine(self, wert: str) -> None:
        with db.kurz() as s:
            einstellung_setzen(s, pdf_html.EINSTELLUNG_ENGINE, wert)

    def profil(self, kennung: str) -> Profil:
        profil = self.s.query(Profil).filter(Profil.regel_kennung == kennung).first()
        self.assertIsNotNone(profil, f"Profil {kennung} fehlt in der DB-Kopie")
        return profil


# ======================================================================================================
class Relevanz(_Rate):
    def test_modus_aus(self):
        a = self.wp()
        with mock.patch.object(cloover_api, "modus", return_value="aus"):
            ok, grund = cloover.relevant(self.s, a)
        self.assertFalse(ok)
        self.assertEqual(grund, cloover.GRUND_MODUS_AUS)
        self.assertIsNone(cloover.kontext_fuer_pdf(self.s, a) if not ok else {})
        # rate_aktualisieren rührt nichts an – kein Netz, kein Schreibzugriff
        with mock.patch.object(cloover_api, "modus", return_value="aus"), \
                mock.patch.object(cloover_api, "rate_berechnen") as rb:
            self.assertEqual(cloover.rate_aktualisieren(a.id), {})
        rb.assert_not_called()
        self.assertEqual(self.daten(a), {})

    def test_profile_enni_swd_sparkasse_ohne_cloover(self):
        a = self.wp()
        stack, _ = self.mocks()
        with stack:
            for kennung in ("enni", "swd", "sparkasse"):
                a.profil_id = self.profil(kennung).id
                self.s.commit()
                ok, grund = cloover.relevant(self.s, a)
                self.assertFalse(ok, kennung)
                self.assertIn("ohne Cloover", grund)
                self.assertIsNone(cloover.kontext_fuer_pdf(self.s, a))
                self.assertEqual(cloover.mail_platzhalter(self.s, a)["cloover_rate"], "")
            a.profil_id = self.profil("standard").id
            self.s.commit()
            self.assertEqual(cloover.relevant(self.s, a), (True, ""))

    def test_sparte_ausgeblendet_extern(self):
        pv = self.angebot("PV", [PV_PLAN])
        stack, _ = self.mocks()
        with stack:
            with db.kurz() as s:
                einstellung_setzen(s, "cloover_sparten", "WP")
            try:
                ok, grund = cloover.relevant(self.s, pv)
                self.assertFalse(ok)
                self.assertIn("Sparte PV", grund)
            finally:
                with db.kurz() as s:
                    einstellung_setzen(s, "cloover_sparten", self.sparten_vorher)
            self.assertTrue(cloover.relevant(self.s, pv)[0])
            cloover.json_schreiben(pv, ausgeblendet=True)
            self.s.commit()
            ok, grund = cloover.relevant(self.s, pv)
            self.assertFalse(ok)
            self.assertEqual(grund, cloover.GRUND_AUSGEBLENDET)
            self.assertIsNone(cloover.kontext_fuer_pdf(self.s, pv))
            # Editor-Karte bleibt sichtbar (Häkchen muss erreichbar sein), aber nicht relevant
            karte = cloover.editor_kontext(self.s, pv)
            self.assertTrue(karte["sichtbar"])
            self.assertFalse(karte["relevant"])
            self.assertTrue(karte["ausgeblendet"])
            extern = Angebot(nummer="AN-EXT-V36B2", kunde_id=self.kunde.id, extern=True,
                             extern_endbetrag_cent=1_000_000, status="Versendet (extern)")
            self.s.add(extern)
            self.s.commit()
            ok, grund = cloover.relevant(self.s, extern)
            self.assertFalse(ok)
            self.assertEqual(grund, cloover.GRUND_EXTERN)

    def test_voraussetzungen(self):
        a = self.wp()
        self.assertEqual(cloover.voraussetzungen(self.s, a), [])
        self.kunde.telefon = ""
        self.kunde.email = ""
        self.kunde.firma = "Muster GmbH"
        self.s.commit()
        try:
            hinweise = cloover.voraussetzungen(self.s, a)
            self.assertEqual(hinweise, [cloover.HINWEIS_EMAIL, cloover.HINWEIS_TELEFON, cloover.HINWEIS_FIRMA])
        finally:
            self.kunde.telefon = "0203 1234567"
            self.kunde.email = self.EMAIL
            self.kunde.firma = ""
            self.s.commit()
        self.kunde.grosskunde = True
        self.s.commit()
        try:
            self.assertEqual(cloover.voraussetzungen(self.s, a), [cloover.HINWEIS_GROSSKUNDE])
        finally:
            self.kunde.grosskunde = False
            self.s.commit()


# ======================================================================================================
class Rate(_Rate):
    def test_wp_mit_foerderung_kontrollwerte(self):
        a = self.wp(laufzeit_jahre=15)
        stack, rb = self.mocks(foerderung=FOERDERUNG)
        with stack:
            daten = cloover.rate_aktualisieren(a.id)
            rb.assert_called_once()
            args, kwargs = rb.call_args
            self.assertEqual(args[0][0]["type"], "Heat pump")
            self.assertEqual(args[1:4], (15, 0, cloover_api.standard_email(self.s)))
            self.assertEqual(kwargs["brutto_cent"], ENDBETRAG_WP)
            self.assertEqual(daten["rate_ohne_cent"], 38999)
            self.assertEqual(daten["rate_mit_cent"], 24270)
            self.assertEqual(daten["endbetrag_cent"], ENDBETRAG_WP)
            self.assertEqual(daten["foerderung_cent"], FOERDERUNG)
            self.assertEqual(daten["ust_satz"], 19.0)
            self.assertEqual(daten["laufzeit_jahre"], 15)
            self.assertEqual(daten["anzahlung_cent"], 0)
            self.assertEqual(daten["quelle"], "v2")
            self.assertNotIn("fehler", daten)
            self.assertRegex(daten["stand"], r"^\d{2}\.\d{2}\.\d{4} \d{2}:\d{2}$")
            self.assertEqual(self.daten(a), daten)   # geschrieben
            self.s.expire_all()
            kontext = cloover.kontext_fuer_pdf(self.s, self.frisch(a))
        self.assertEqual(kontext["rate_text"], "389,99 €")
        self.assertEqual(kontext["rate_mit_text"], "242,70 €")
        self.assertEqual(kontext["laufzeit"], 15)
        self.assertTrue(kontext["mit_foerderung"])
        self.assertEqual(kontext["fussnote"], (
            "*Unverbindliche Beispielrechnung unseres Finanzierungspartners Cloover auf Basis des Endbetrags "
            "dieses Angebots von 42.830,55 €, einer Laufzeit von 15 Jahren und 0,00 € Anzahlung; ‚mit Förderung‘ "
            "berücksichtigt die voraussichtliche Förderung von 16.500,00 € als Sondertilgung nach Auszahlung. "
            f"Stand {HEUTE}. Verbindliche Konditionen, Sollzins und effektiver Jahreszins ergeben sich aus dem "
            "Finanzierungsangebot von Cloover."))
        self.assertEqual(kontext["hinweis_link"], cloover.HINWEIS_LINK)
        self.assertEqual(kontext["checkout_link"], "")
        self.assertEqual(kontext["qr_svg"], "")
        self.assertEqual(kontext["datenschutz"], "")

    def test_wp_ohne_foerderung(self):
        a = self.wp()
        stack, _ = self.mocks()   # foerderung_cent echt → 0 (kein KfW-Block am Angebot)
        with stack:
            daten = cloover.rate_aktualisieren(a.id)
            self.assertEqual(daten["rate_ohne_cent"], 38999)
            self.assertNotIn("rate_mit_cent", daten)       # API-Wert ohne Förderung verworfen
            self.assertEqual(daten["foerderung_cent"], 0)
            self.assertEqual(daten["laufzeit_jahre"], cloover_api.laufzeit_jahre(self.s))
            kontext = cloover.kontext_fuer_pdf(self.s, self.frisch(a))
        self.assertEqual(kontext["rate_text"], "389,99 €")
        self.assertEqual(kontext["rate_mit_text"], "")
        self.assertFalse(kontext["mit_foerderung"])
        self.assertNotIn("mit Förderung", kontext["fussnote"])
        self.assertIn("von 42.830,55 €, einer Laufzeit von 20 Jahren und 0,00 € Anzahlung. Stand",
                      kontext["fussnote"])

    def test_pv_kl_wb_eine_zeile(self):
        faelle = (("PV", PV_PLAN, 0.0, 2_000_000), ("KL", KL_GERAET, 19.0, 212_534), ("WB", WB_PLAN, 19.0, 266_048))
        for sparte, position, ust, endbetrag in faelle:
            with self.subTest(sparte=sparte):
                a = self.angebot(sparte, [position])
                self.assertEqual(a.summen()["endbetrag"], endbetrag)
                stack, rb = self.mocks(rate_ohne=9900, rate_mit=9900)
                with stack:
                    daten = cloover.rate_aktualisieren(a.id)
                    self.assertEqual(rb.call_args.kwargs["brutto_cent"], endbetrag)
                    self.assertEqual(daten["ust_satz"], ust)
                    self.assertEqual(daten["rate_ohne_cent"], 9900)
                    self.assertNotIn("rate_mit_cent", daten)
                    kontext = cloover.kontext_fuer_pdf(self.s, self.frisch(a))
                self.assertEqual(kontext["rate_text"], "99,00 €")
                self.assertEqual(kontext["rate_mit_text"], "")
                self.assertNotIn("Förderung", kontext["fussnote"])
                self.assertIn(cloover.eur(endbetrag), kontext["fussnote"])

    def test_fehlerfall_ohne_zahlen_und_letzte_rate_bleibt(self):
        a = self.wp()
        stack, _ = self.mocks(fehler="Cloover nicht erreichbar – später erneut versuchen")
        with stack:
            daten = cloover.rate_aktualisieren(a.id)
            self.assertEqual(daten["fehler"], "Cloover nicht erreichbar – später erneut versuchen")
            self.assertNotIn("rate_ohne_cent", daten)
            self.assertNotIn("stand", daten)
            kontext = cloover.kontext_fuer_pdf(self.s, self.frisch(a))
            self.assertEqual((kontext["rate_text"], kontext["rate_mit_text"], kontext["fussnote"]), ("", "", ""))
            self.assertEqual(cloover.mail_platzhalter(self.s, a)["cloover_rate"], "")
            karte = cloover.editor_kontext(self.s, self.frisch(a))
            self.assertEqual(karte["rate_ohne"], "")
            self.assertIn("nicht erreichbar", karte["fehler"])
        # Erfolg → Rate, Fehler weg
        stack, _ = self.mocks()
        with stack:
            daten = cloover.rate_aktualisieren(a.id)
        self.assertEqual(daten["rate_ohne_cent"], 38999)
        self.assertNotIn("fehler", daten)
        stand = daten["stand"]
        # erneuter Fehler nach Änderung des Endbetrags → letzte Rate mit Stand bleibt, Fehler steht dabei
        a = self.frisch(a)
        a.positionen[0].e_preis_cent = 3_000_000
        self.s.commit()
        stack, _ = self.mocks(fehler="Cloover: API-Key abgelehnt")
        with stack:
            daten = cloover.rate_aktualisieren(a.id)
            self.assertEqual(daten["rate_ohne_cent"], 38999)
            self.assertEqual(daten["stand"], stand)
            self.assertEqual(daten["endbetrag_cent"], ENDBETRAG_WP)   # Basis der alten Rate
            self.assertEqual(daten["fehler"], "Cloover: API-Key abgelehnt")
            kontext = cloover.kontext_fuer_pdf(self.s, self.frisch(a))
            self.assertEqual(kontext["rate_text"], "389,99 €")
            self.assertIn("42.830,55 €", kontext["fussnote"])   # Fußnote nennt die Basis der Rate
            karte = cloover.editor_kontext(self.s, self.frisch(a))
            self.assertTrue(karte["veraltet"])

    def test_neuberechnung_nur_bei_aenderung(self):
        a = self.wp()
        stack, rb = self.mocks()
        with stack:
            cloover.rate_aktualisieren(a.id)
            cloover.rate_aktualisieren(a.id)
            self.assertEqual(rb.call_count, 1, "ohne Änderung keine zweite Anfrage")
            a = self.frisch(a)
            a.positionen[0].e_preis_cent = 3_000_000       # Endbetrag ändert sich
            self.s.commit()
            daten = cloover.rate_aktualisieren(a.id)
            self.assertEqual(rb.call_count, 2)
            self.assertEqual(daten["endbetrag_cent"], 3_570_000)
            cloover.rate_aktualisieren(a.id, erzwingen=True)
            self.assertEqual(rb.call_count, 3)
            # Laufzeit/Anzahlung aus cloover_json ändern → neue Anfrage mit den Werten
            a = self.frisch(a)
            cloover.json_schreiben(a, laufzeit_jahre=10, anzahlung_cent=100_000)
            self.s.commit()
            daten = cloover.rate_aktualisieren(a.id)
            self.assertEqual(rb.call_count, 4)
            self.assertEqual(rb.call_args.args[1:3], (10, 100_000))
            self.assertEqual((daten["laufzeit_jahre"], daten["anzahlung_cent"]), (10, 100_000))
            self.assertEqual((daten["rate_laufzeit_jahre"], daten["rate_anzahlung_cent"]), (10, 100_000))
            kontext = cloover.kontext_fuer_pdf(self.s, self.frisch(a))
            self.assertIn("einer Laufzeit von 10 Jahren und 1.000,00 € Anzahlung", kontext["fussnote"])
            self.assertEqual(kontext["laufzeit"], 10)
            # USt-Wechsel (PV 0 %) zählt als Änderung
            a = self.frisch(a)
            a.ust_satz = 0.0
            self.s.commit()
            cloover.rate_aktualisieren(a.id)
            self.assertEqual(rb.call_count, 5)

    def test_benutzer_email_fuer_anfrage(self):
        a = self.wp()
        from app.models import Benutzer
        admin = self.s.get(Benutzer, 1)
        vorher = admin.cloover_email
        admin.cloover_email = "id-test@friondo.de"
        self.s.commit()
        try:
            stack, rb = self.mocks()
            with stack:
                cloover.rate_aktualisieren(a.id, benutzer_id=1)
                self.assertEqual(rb.call_args.args[3], "id-test@friondo.de")
                cloover.rate_aktualisieren(a.id, erzwingen=True, benutzer_id=self.ad.id)   # AD → Standard-Konto
                self.assertEqual(rb.call_args.args[3], cloover_api.standard_email(self.s))
        finally:
            admin.cloover_email = vorher
            self.s.commit()

    def test_kontrollangebot_mit_echter_foerderung(self):
        """WP aus dem Kontrollszenario (KfW-Block): Förderung > 0 aus kfw_json (cloover_api.foerderung_cent
        echt, assets_fuer echt – kein Netz), Rate mit Förderung wird gespeichert."""
        logik, _ = logik_modul.hole_logik(self.s)
        a = angebot_aufbau.angebot_anlegen(self.s, self.kunde.id, antworten=dict(KONTROLL_SZENARIO), logik=logik)
        a.vorgang_id = self.vorgang.id
        self.s.commit()
        self.assertEqual(a.summen()["netto"], 3024543)
        foerderung = cloover_api.foerderung_cent(self.s, a)
        self.assertGreater(foerderung, 0)
        assets = cloover_api.assets_fuer(self.s, a)
        self.assertEqual(assets[0]["priceInfo"]["subsidy"], foerderung / 100)
        rate = mock.Mock(return_value={"rate_ohne_cent": 32000, "rate_mit_cent": 20000, "quelle": "v2",
                                       "antwort": {}})
        with mock.patch.object(cloover_api, "modus", return_value="test"), \
                mock.patch.object(cloover_api, "rate_berechnen", rate):
            daten = cloover.rate_aktualisieren(a.id)
        self.assertEqual(rate.call_args.args[0], assets)
        self.assertEqual((daten["rate_ohne_cent"], daten["rate_mit_cent"], daten["foerderung_cent"]),
                         (32000, 20000, foerderung))


# ======================================================================================================
class PdfLayout(_Rate):
    def _kontext(self, angebot) -> dict:
        self.s.expire_all()
        return pdf_kontext.fuer_angebot(self.s, self.s.get(Angebot, angebot.id))

    def _html(self, angebot) -> str:
        kontext = self._kontext(angebot)
        return pdf_html.html_rendern(pdf_html.vorlage_fuer(kontext["sparte"]), kontext)

    def test_karte_box_fussnote_wp_mit_foerderung(self):
        a = self.wp(laufzeit_jahre=15)
        stack, _ = self.mocks(foerderung=FOERDERUNG)
        with stack:
            cloover.rate_aktualisieren(a.id)
            kontext = self._kontext(a)
            self.assertTrue(kontext["auftrag"]["cloover_block"])
            c = kontext["auftrag"]["cloover"]
            self.assertEqual((c["rate_text"], c["rate_mit_text"], c["laufzeit"]), ("389,99 €", "242,70 €", 15))
            self.assertEqual(kontext["auftrag"]["karte2"]["art"], "cloover")
            self.assertEqual(kontext["auftrag"]["karte2"]["knopf_text"], "")      # ohne Link kein Knopf
            html = self._html(a)
        # Karte 2: Rate mit Förderung groß, darunter „ohne Förderung ab …“, Laufzeit ohne zweiten Halbsatz
        self.assertIn("FINANZIERUNG MIT CLOOVER", html)
        self.assertIn('class="pdf-auftrag-rate-betrag">242,70 €', html)
        self.assertIn("ohne Förderung ab 389,99 €", html)
        self.assertIn("Laufzeit 15 Jahre", html)
        self.assertNotIn("bereits angelegt", html)
        self.assertIn(cloover.HINWEIS_LINK, html)
        self.assertNotIn("Finanzierung abschließen", html)
        # Box „Planbare Monatsraten“ wörtlich + Fußnote
        self.assertIn("Planbare Monatsraten – Ihre Rate für dieses Angebot:", html)
        self.assertIn("ab 242,70 € pro Monat mit Förderung*", html)
        self.assertIn("ab 389,99 € pro Monat ohne Förderung", html)
        self.assertIn("*Unverbindliche Beispielrechnung unseres Finanzierungspartners Cloover auf Basis des Endbetrags "
                      "dieses Angebots von 42.830,55 €, einer Laufzeit von 15 Jahren und 0,00 € Anzahlung; ‚mit "
                      "Förderung‘ berücksichtigt die voraussichtliche Förderung von 16.500,00 € als Sondertilgung "
                      f"nach Auszahlung. Stand {HEUTE}.", html)
        self.assertNotIn("Monatsrate auf Anfrage", html)
        self.assertNotIn(cloover.RUECKMELDUNG, html)   # nur mit Link
        for verboten in ("EK", "Deckungsbeitrag", "ek_cent", "[CLOOVER]"):
            self.assertNotIn(verboten, html)

    def test_link_qr_und_datenschutz(self):
        a = self.wp()
        link = "https://app.cloover.com/apply?partner=friondo&project=p-1234567890"
        stack, _ = self.mocks()
        with stack:
            cloover.rate_aktualisieren(a.id)
            cloover.json_schreiben(self.frisch(a), checkout_link=link, projekt_id="p-1234567890")
            self.s.commit()
            kontext = self._kontext(a)
            c = kontext["auftrag"]["cloover"]
            self.assertEqual(c["checkout_link"], link)
            self.assertEqual(c["link_kurz"], "app.cloover.com/apply?partner=friondo&project=p-1234567890")
            self.assertTrue(c["qr_svg"].startswith("<svg"))
            self.assertIn('width="22mm"', c["qr_svg"])
            self.assertIn('height="22mm"', c["qr_svg"])
            self.assertEqual(kontext["auftrag"]["karte2"]["knopf_url"], link)
            self.assertEqual(kontext["auftrag"]["karte2"]["knopf_text"], "Finanzierung abschließen ›")
            html = self._html(a)
        self.assertIn('href="' + link.replace("&", "&amp;") + '"', html)   # Jinja escapet &
        self.assertIn("Finanzierung abschließen ›", html)
        self.assertIn("Laufzeit 20 Jahre · Ihre Finanzierungsanfrage ist bereits angelegt – nur noch bestätigen.", html)
        self.assertIn("<svg", html)
        self.assertIn("app.cloover.com/apply?partner=friondo&amp;project=p-1234567890", html)
        self.assertIn(cloover.RUECKMELDUNG, html)
        self.assertIn("Hinweise zum Datenschutz: https://friondo.de/Datenschutz", html)
        self.assertNotIn(cloover.HINWEIS_LINK, html)
        self.assertNotIn("Monatsrate auf Anfrage", html)
        # QR-Matrix für den fpdf2-Rückfall: quadratisch, Ruhezone außen hell
        matrix = cloover.qr_matrix(link)
        self.assertEqual(len(matrix), len(matrix[0]))
        self.assertFalse(any(matrix[0]))

    def test_kombi_gesamtrate(self):
        """Kombi-Versand (Agent B3 legt kombi_gesamtrate_cent ab): zusätzliche Zeile in der Box, {cloover_rate}
        bleibt die Einzelrate [ANNAHME Plan, Rückfrage B6]."""
        a = self.wp()
        stack, _ = self.mocks()
        with stack:
            cloover.rate_aktualisieren(a.id)
            cloover.json_schreiben(self.frisch(a), kombi_gesamtrate_cent=48899,
                                   checkout_link="https://app.cloover.com/apply?project=kombi")
            self.s.commit()
            kontext = self._kontext(a)
            self.assertEqual(kontext["auftrag"]["cloover"]["kombi_gesamtrate_text"], "488,99 €")
            html = self._html(a)
            self.assertIn("ab 389,99 € pro Monat ohne Förderung", html)
            self.assertIn("Gesamtrate für alle Angebote dieser Mail: ab 488,99 € pro Monat", html)
            self.assertEqual(mail_vorlagen.werte_fuer_angebot(self.s, self.frisch(a), self.kunde)["cloover_rate"],
                             "ab 389,99 € pro Monat")
            # ohne Rate keine Gesamtrate-Zeile
            cloover.json_schreiben(self.frisch(a), rate_ohne_cent=None, stand=None)
            self.s.commit()
            self.assertEqual(self._kontext(a)["auftrag"]["cloover"]["kombi_gesamtrate_text"], "")
            self.assertNotIn("Gesamtrate", self._html(a))

    def test_ohne_rate_und_ausgeblendet_und_enni(self):
        a = self.wp()
        stack, _ = self.mocks(fehler="Cloover nicht erreichbar – später erneut versuchen")
        with stack:
            cloover.rate_aktualisieren(a.id)
            html = self._html(a)
            self.assertIn("Monatsrate auf Anfrage", html)
            self.assertNotIn("pro Monat", html)
            self.assertNotIn("Unverbindliche Beispielrechnung", html)
            self.assertNotIn("Finanzierung abschließen", html)
        stack, _ = self.mocks()
        with stack:
            cloover.rate_aktualisieren(a.id)
            cloover.json_schreiben(self.frisch(a), ausgeblendet=True)
            self.s.commit()
            kontext = self._kontext(a)
            self.assertIsNone(kontext["auftrag"]["cloover"])
            self.assertIn("Monatsrate auf Anfrage", self._html(a))
            # Enni: keine Cloover-Karte, kein Cloover-Block
            b = self.wp()
            b.profil_id = self.profil("enni").id
            self.s.commit()
            kontext = self._kontext(b)
            self.assertIsNone(kontext["auftrag"]["cloover"])
            self.assertFalse(kontext["auftrag"]["cloover_block"])
            self.assertEqual(kontext["auftrag"]["karte2"]["art"], "enni")
            html = self._html(b)
            self.assertIn("ENNI CONTRACTING", html)
            self.assertNotIn("Cloover", html)


# ======================================================================================================
class Fpdf2Rueckfall(_Rate):
    """fpdf2-Rückfall: Platzhalter [CLOOVER] im Nachtext – Seed-Konstanten tragen ihn seit v36; die
    DB-Kopie wird nicht migriert (Migrationstest unten stellt alles zurück), daher Nachtext aus der
    Konstanten über einen Textblock-Override des Standard-Profils."""

    def setUp(self):
        super().setUp()
        self.engine("fpdf2")
        self.block = self.s.query(Textblock).filter_by(art="nachtext", name="Friondo Standard").first()
        self.block_text = self.block.text
        self.block.text = angebotsprofile.STANDARD_NACHTEXT
        self.s.commit()

    def tearDown(self):
        self.block = self.s.query(Textblock).filter_by(art="nachtext", name="Friondo Standard").first()
        self.block.text = self.block_text
        self.s.commit()
        self.engine(self.engine_vorher)
        super().tearDown()

    def test_platzhalter_gerendert(self):
        self.assertIn("[CLOOVER]", angebotsprofile.STANDARD_NACHTEXT)
        a = self.wp(laufzeit_jahre=15)
        stack, _ = self.mocks(foerderung=FOERDERUNG)
        with stack:
            pfad = pdf_export.pdf_fuer_angebot(self.s, self.frisch(a))
            text = " ".join(pdf_text(pfad).split())
        self.assertNotIn("[CLOOVER]", text)
        self.assertIn("Planbare Monatsraten – Ihre Rate für dieses Angebot:", text)
        self.assertIn("ab 242,70 € pro Monat mit Förderung*", text)
        self.assertIn("ab 389,99 € pro Monat ohne Förderung", text)
        self.assertIn("Laufzeit 15 Jahre", text)
        self.assertIn(cloover.HINWEIS_LINK, text)
        self.assertIn("*Unverbindliche Beispielrechnung unseres Finanzierungspartners Cloover", text)
        self.assertIn("von 42.830,55 €, einer Laufzeit von 15 Jahren und 0,00 € Anzahlung; ‚mit Förderung‘", text)
        self.assertNotIn("Beispielrate auf Basis einer Angebotssumme", text)
        self.assertNotIn("ab 129 €", text)
        self.assertNotIn("Finanzierung abschließen", text)

    def test_platzhalter_mit_link_und_ohne_rate(self):
        a = self.wp()
        link = "https://app.cloover.com/apply?partner=friondo&project=p-1"
        stack, _ = self.mocks()
        with stack:
            cloover.rate_aktualisieren(a.id)
            cloover.json_schreiben(self.frisch(a), checkout_link=link)
            self.s.commit()
            pfad = pdf_export.pdf_fuer_angebot(self.s, self.frisch(a))
            text = " ".join(pdf_text(pfad).split())
            self.assertIn("Finanzierung abschließen ›", text)
            self.assertIn("app.cloover.com/apply?partner=friondo&project=p-1", text)
            self.assertIn("Ihre Finanzierungsanfrage ist bereits angelegt – nur noch bestätigen.", text)
            self.assertIn(cloover.RUECKMELDUNG, text)
            self.assertNotIn("mit Förderung", text)
            self.assertNotIn("Gesamtrate", text)
            # Kombi-Gesamtrate (B3) auch im Rückfall
            cloover.json_schreiben(self.frisch(a), kombi_gesamtrate_cent=48899)
            self.s.commit()
            text = " ".join(pdf_text(pdf_export.pdf_fuer_angebot(self.s, self.frisch(a))).split())
            self.assertIn("• Gesamtrate für alle Angebote dieser Mail: ab 488,99 € pro Monat", text)
            # QR-Code als Rechtecke: deutlich mehr Pfadoperationen als ohne Link
            import pypdf
            roh = pypdf.PdfReader(str(pfad))
            inhalte = b"".join(s.get_contents().get_data() for s in roh.pages)
            self.assertGreater(inhalte.count(b" re"), 400)
        # ohne Rate (Fehler beim ersten Aufruf): „Monatsrate auf Anfrage“, keine Fußnote
        b = self.wp()
        stack, _ = self.mocks(fehler="Cloover nicht erreichbar – später erneut versuchen")
        with stack:
            pfad = pdf_export.pdf_fuer_angebot(self.s, self.frisch(b))
            text = " ".join(pdf_text(pfad).split())
        self.assertIn("Planbare Monatsraten – Ihre Rate für dieses Angebot: • Monatsrate auf Anfrage", text)
        self.assertNotIn("Unverbindliche Beispielrechnung", text)
        self.assertNotIn("pro Monat", text)

    def test_rate_vor_pdf_und_archiv_unberuehrt(self):
        a = self.wp()
        stack, rb = self.mocks()
        with stack, mock.patch.object(cloover, "rate_aktualisieren", wraps=cloover.rate_aktualisieren) as spion:
            pdf_export.pdf_fuer_angebot(self.s, self.frisch(a))
            self.assertEqual(spion.call_count, 1)
            self.assertEqual(rb.call_count, 1)
            self.assertEqual(self.daten(a)["rate_ohne_cent"], 38999)
            # ORM-Objekt der Aufrufer-Sitzung trägt den neuen Stand (refresh)
            pdf_export.pdf_fuer_angebot(self.s, self.frisch(a))
            self.assertEqual(rb.call_count, 1, "unverändert → keine zweite Anfrage")
            # eingefrorenes Archiv-PDF (Versendet, Datei vorhanden) → kein Aufruf, Datei byteidentisch
            a = self.frisch(a)
            a.status = "Versendet"
            a.positionen[0].e_preis_cent = 3_000_000
            self.s.commit()
            pfad = pdf_export.pdf_zielpfad(a)
            vorher = pfad.read_bytes()
            self.assertEqual(pdf_export.pdf_fuer_angebot(self.s, a).read_bytes(), vorher)
            self.assertEqual(spion.call_count, 2)
            self.assertEqual(rb.call_count, 1)
            # Fehler in der Rate blockiert das PDF nie
            a.status = "Entwurf"
            self.s.commit()
            with mock.patch.object(cloover, "rate_aktualisieren", side_effect=RuntimeError("kaputt")):
                self.assertTrue(pdf_export.pdf_fuer_angebot(self.s, a).is_file())


# ======================================================================================================
class Editor(_Rate):
    def test_karte_innendienst(self):
        a = self.wp(laufzeit_jahre=15)
        stack, _ = self.mocks(foerderung=FOERDERUNG)
        with stack:
            cloover.rate_aktualisieren(a.id)
            r = self.client.get(f"/angebote/{a.id}")
            self.assertEqual(r.status_code, 200)
            seite = r.text
            self.assertIn("Finanzierung (Cloover)", seite)
            self.assertIn("ab 242,70 € / Monat*", seite)
            self.assertIn("ab 389,99 € / Monat", seite)
            self.assertIn("Test-Umgebung", seite)
            self.assertIn('name="laufzeit"', seite)
            self.assertIn('value="15"', seite)
            self.assertIn('name="anzahlung"', seite)
            self.assertIn("Finanzierung im PDF ausblenden", seite)
            self.assertIn("Rate neu berechnen", seite)
            self.assertIn("Quelle v2", seite)
            self.assertNotIn("Telefon fehlt", seite)
            # Hinweise rot
            self.kunde.telefon = ""
            self.s.commit()
            try:
                seite = self.client.get(f"/angebote/{a.id}").text
                self.assertIn("Telefon fehlt", seite)
            finally:
                self.kunde.telefon = "0203 1234567"
                self.s.commit()
            # Karte nur Innendienst/Admin – nie EK/DB in der Karte
            karte = re.search(r'<details class="cloover-karte".*?</details>', seite, re.S).group(0)
            for verboten in ("EK", "Deckungsbeitrag"):
                self.assertNotIn(verboten, karte)

    def test_speichern_und_rate(self):
        a = self.wp()
        stack, rb = self.mocks()
        with stack:
            r = self.client.post(f"/angebote/{a.id}/cloover",
                                 data={"laufzeit": "15", "anzahlung": "1.000,00"}, follow_redirects=False)
            self.assertEqual(r.status_code, 303)
            self.assertIn("Finanzierung+gespeichert", r.headers["location"])
            daten = self.daten(a)
            self.assertEqual((daten["laufzeit_jahre"], daten["anzahlung_cent"], daten.get("ausgeblendet")),
                             (15, 100_000, False))
            self.assertEqual(rb.call_count, 1, "geänderte Laufzeit/Anzahlung → Rate sofort nachgezogen")
            self.assertEqual(rb.call_args.args[1:3], (15, 100_000))
            self.assertEqual(daten["rate_ohne_cent"], 38999)
            # ausblenden
            r = self.client.post(f"/angebote/{a.id}/cloover",
                                 data={"laufzeit": "15", "anzahlung": "1.000,00", "ausblenden": "on"},
                                 follow_redirects=False)
            self.assertEqual(r.status_code, 303)
            self.assertTrue(self.daten(a)["ausgeblendet"])
            self.assertEqual(rb.call_count, 1)
            seite = self.client.get(f"/angebote/{a.id}").text
            self.assertIn("im PDF ausgeblendet", seite)
            # Rate neu berechnen (ausgeblendet → nicht relevant → Meldung)
            r = self.client.post(f"/angebote/{a.id}/cloover/rate", follow_redirects=False,
                                 headers={"accept": "application/json"})
            self.assertEqual(r.status_code, 400)
            self.assertIn("Cloover-Rate nicht verfügbar: Finanzierung im PDF ausgeblendet", r.json()["meldung"])
            r = self.client.post(f"/angebote/{a.id}/cloover", data={"laufzeit": "15", "anzahlung": "1.000,00"},
                                 follow_redirects=False)
            r = self.client.post(f"/angebote/{a.id}/cloover/rate", follow_redirects=False,
                                 headers={"accept": "application/json"})
            self.assertEqual(r.status_code, 200)
            self.assertTrue(r.json()["ok"])
            self.assertIn("Rate berechnet: ab 389,99 € pro Monat", r.json()["meldung"])
            self.assertEqual(rb.call_count, 2)
            # ungültige Laufzeit / Anzahlung
            r = self.client.post(f"/angebote/{a.id}/cloover", data={"laufzeit": "40", "anzahlung": "0"},
                                 follow_redirects=False)
            self.assertIn("Laufzeit", r.headers["location"])
            r = self.client.post(f"/angebote/{a.id}/cloover", data={"laufzeit": "15", "anzahlung": "abc"},
                                 follow_redirects=False)
            self.assertIn("Anzahlung", r.headers["location"])
            self.assertEqual(self.daten(a)["laufzeit_jahre"], 15)
            # Fehler der API in der Meldung
        stack, _ = self.mocks(fehler="Cloover nicht erreichbar – später erneut versuchen")
        with stack:
            r = self.client.post(f"/angebote/{a.id}/cloover/rate", follow_redirects=False,
                                 headers={"accept": "application/json"})
            self.assertEqual(r.status_code, 200)
            self.assertFalse(r.json()["ok"])
            self.assertIn("Cloover-Rate nicht verfügbar: Cloover nicht erreichbar", r.json()["meldung"])
            self.assertIn("letzte Rate ab 389,99 € pro Monat", r.json()["meldung"])
        # versendet → nicht mehr änderbar
        a = self.frisch(a)
        a.status = "Versendet"
        self.s.commit()
        stack, _ = self.mocks()
        with stack:
            r = self.client.post(f"/angebote/{a.id}/cloover", data={"laufzeit": "10", "anzahlung": "0"},
                                 follow_redirects=False, headers={"accept": "application/json"})
            self.assertEqual(r.status_code, 400)
            self.assertEqual(self.daten(a)["laufzeit_jahre"], 15)

    def test_nicht_relevant_hinweiszeile(self):
        a = self.wp()
        with mock.patch.object(cloover_api, "modus", return_value="aus"):
            seite = self.client.get(f"/angebote/{a.id}").text
        self.assertIn("Finanzierung (Cloover): Cloover ist aus", seite)
        self.assertNotIn("Rate neu berechnen", seite)
        stack, _ = self.mocks()
        with stack:
            a.profil_id = self.profil("sparkasse").id
            self.s.commit()
            seite = self.client.get(f"/angebote/{a.id}").text
        self.assertIn("Finanzierung (Cloover): Profil Sparkasse DU – ohne Cloover", seite)

    def test_ad_lesesicht_ohne_knoepfe(self):
        a = self.wp(laufzeit_jahre=15)
        stack, rb = self.mocks(foerderung=FOERDERUNG)
        with stack:
            cloover.rate_aktualisieren(a.id)
            ad = self.ad_client()
            r = ad.get(f"/meine-angebote/{a.id}")
            self.assertEqual(r.status_code, 200)
            seite = r.text
            self.assertIn("Finanzierung (Cloover):", seite)
            self.assertIn("ab 242,70 € pro Monat mit Förderung", seite)
            self.assertIn("ab 389,99 € pro Monat ohne Förderung", seite)
            self.assertIn("Laufzeit 15 Jahre", seite)
            for verboten in ("Rate neu berechnen", "cloover-form", "Finanzierung im PDF ausblenden",
                             "Deckungsbeitrag", "EK "):
                self.assertNotIn(verboten, seite)
            # AD darf nichts ändern (Middleware leitet um bzw. Route lehnt ab)
            r = ad.post(f"/angebote/{a.id}/cloover", data={"laufzeit": "5", "anzahlung": "0"},
                        follow_redirects=False)
            self.assertIn(r.status_code, (303, 403))
            self.assertEqual(self.daten(a)["laufzeit_jahre"], 15)
            r = ad.post(f"/angebote/{a.id}/cloover/rate", follow_redirects=False)
            self.assertIn(r.status_code, (303, 403))
            self.assertEqual(rb.call_count, 1)


# ======================================================================================================
class Platzhalter(_Rate):
    def test_werte_einzel_und_kombi(self):
        for name in ("{cloover_rate}", "{cloover_link}", "{cloover_finanzierungsangebot}"):
            self.assertIn(name, [p for p, _ in mail_vorlagen.PLATZHALTER])
        self.assertEqual(mail_vorlagen.unbekannte_platzhalter("{cloover_rate} {cloover_link} {endbetrag}"), [])
        a = self.wp()
        pv = self.angebot("PV", [PV_PLAN])
        stack, _ = self.mocks()
        with stack:
            werte = mail_vorlagen.werte_fuer_angebot(self.s, a, self.kunde)
            self.assertEqual((werte["cloover_rate"], werte["cloover_link"], werte["cloover_finanzierungsangebot"]),
                             ("", "", ""))
            cloover.rate_aktualisieren(a.id)
            cloover.json_schreiben(self.frisch(a), checkout_link="https://app.cloover.com/x",
                                   financial_offer={"url": "https://app.cloover.com/offer/1"})
            self.s.commit()
            self.s.expire_all()
            werte = mail_vorlagen.werte_fuer_angebot(self.s, self.frisch(a), self.kunde)
            self.assertEqual(werte["cloover_rate"], "ab 389,99 € pro Monat")
            self.assertEqual(werte["cloover_link"], "https://app.cloover.com/x")
            self.assertEqual(werte["cloover_finanzierungsangebot"], "https://app.cloover.com/offer/1")
            self.assertEqual(mail_vorlagen.einsetzen("Rate: {cloover_rate} · {cloover_link}", werte),
                             "Rate: ab 389,99 € pro Monat · https://app.cloover.com/x")
            # Kombi: eine Zeile je Angebot mit Rate, gemeinsamer Link
            cloover.rate_aktualisieren(pv.id)
            with mock.patch.object(mail_vorlagen, "kombi_vorlage_laden",
                                   return_value=("Angebote {angebotsnummern}", "{cloover_rate}\n{cloover_link}")):
                betreff, text = mail_vorlagen.kombi_mail_fuer_vorgang(
                    self.s, [self.frisch(a), self.frisch(pv)], self.kunde)
            self.assertIn(f"• WP-Angebot {a.nummer}: ab 389,99 € pro Monat", text)
            self.assertIn(f"• PV-Angebot {pv.nummer}: ab 389,99 € pro Monat", text)
            self.assertIn("https://app.cloover.com/x", text)
            # Enni → leer
            b = self.wp()
            b.profil_id = self.profil("enni").id
            self.s.commit()
            cloover.json_schreiben(b, rate_ohne_cent=10000, stand="01.01.2026 10:00")
            self.s.commit()
            self.assertEqual(mail_vorlagen.werte_fuer_angebot(self.s, b, self.kunde)["cloover_rate"], "")


# ======================================================================================================
class KopieUndVersion(_Rate):
    VOLL = dict(laufzeit_jahre=15, anzahlung_cent=50_000, ausgeblendet=True, rate_ohne_cent=38999,
                rate_mit_cent=24270, endbetrag_cent=ENDBETRAG_WP, foerderung_cent=FOERDERUNG, ust_satz=19.0,
                stand="01.10.2026 10:00", quelle="v2", projekt_id="p-1", checkout_link="https://x",
                financial_offer="f", pdf_url="https://y", status="open")
    NUR_KOPIE = {"laufzeit_jahre": 15, "anzahlung_cent": 50_000, "ausgeblendet": True}

    def test_version_duplikat_kopie(self):
        a = self.wp(**self.VOLL)
        self.assertEqual(self.daten(a), self.VOLL)
        a = self.frisch(a)
        a.status = "Versendet"
        self.s.commit()
        version = angebot_aufbau.version_erzeugen(self.s, a)
        self.s.commit()
        self.assertEqual(cloover.json_lesen(version), self.NUR_KOPIE)
        self.assertEqual(self.daten(a), self.VOLL, "Original unverändert")
        # Duplizieren (Route)
        r = self.client.post(f"/angebote/{version.id}/duplizieren", follow_redirects=False)
        self.assertEqual(r.status_code, 303)
        kopie_id = int(re.search(r"/angebote/(\d+)", r.headers["location"]).group(1))
        self.assertEqual(cloover.json_lesen(self.s.get(Angebot, kopie_id)), self.NUR_KOPIE)
        # Für anderen Kunden kopieren (Route, Zielkunde = derselbe Testkunde über „#<id>“)
        r = self.client.post(f"/angebote/{version.id}/kopieren",
                             data={"kunde_suche": f"#{self.kunde.id} · {self.kunde.nachname}"},
                             follow_redirects=False)
        self.assertEqual(r.status_code, 303)
        kopie_id = int(re.search(r"/angebote/(\d+)", r.headers["location"]).group(1))
        self.assertEqual(cloover.json_lesen(self.s.get(Angebot, kopie_id)), self.NUR_KOPIE)
        self.assertEqual(cloover.editor_kontext(self.s, self.s.get(Angebot, kopie_id))["rate_ohne"], "")


# ======================================================================================================
class Migration(_Rate):
    NAMEN = ("Friondo Standard", "Friondo PV Standard", "Friondo KL Standard", "Friondo WB Standard",
             "Friondo Enni", "Friondo SWD", "Friondo Sparkasse DU", "Friondo PV Enni", "Friondo KL Enni",
             "Friondo WB Enni")

    def _texte(self) -> dict:
        self.s.expire_all()
        return {b.name: b.text for b in self.s.query(Textblock).filter(Textblock.art == "nachtext")}

    def test_migration_idempotent(self):
        vorher = self._texte()
        marker_vorher = einstellung_holen(self.s, angebotsprofile.MARKER_V36_CLOOVER, "")
        # Integration v36 (Orchestrator): der Test muss auch auf einer bereits migrierten Datenbank laufen –
        # Ausgangslage sind deshalb die v35-Seed-Texte (Fixture aus dem v35-Stand von app/angebotsprofile.py)
        alt = json.loads(FIXTURES_V36.joinpath("nachtexte_v35.json").read_text(encoding="utf-8"))
        try:
            for block in self.s.query(Textblock).filter(Textblock.art == "nachtext"):
                if block.name in alt:
                    block.text = alt[block.name]
            einstellung_setzen(self.s, angebotsprofile.MARKER_V36_CLOOVER, "")
            self.s.commit()
            vorher_alt = self._texte()
            meldungen = angebotsprofile.migriere_cloover_platzhalter(self.s)
            self.s.commit()
            nachher = self._texte()
            self.assertTrue(any("Friondo Standard" in m and "Raten-Absatz" in m for m in meldungen), meldungen)
            self.assertTrue(any("Friondo WB Standard" in m and "Nachtext A" in m for m in meldungen), meldungen)
            for name in ("Friondo Standard", "Friondo PV Standard", "Friondo KL Standard", "Friondo WB Standard"):
                self.assertIn("[CLOOVER]", nachher[name], name)
                self.assertNotIn("Beispielrate", nachher[name], name)
                self.assertNotIn("ab 129 €", nachher[name], name)
                self.assertNotIn("ab 250 €", nachher[name], name)
                self.assertNotIn("ab 119 €", nachher[name], name)
            self.assertEqual(nachher["Friondo Standard"], angebotsprofile.STANDARD_NACHTEXT)
            self.assertEqual(nachher["Friondo KL Standard"], angebotsprofile.KL_STANDARD_NACHTEXT)
            self.assertEqual(nachher["Friondo PV Standard"], angebotsprofile.PV_STANDARD_NACHTEXT)
            self.assertIn("Ihre Wallbox-Lösung", nachher["Friondo WB Standard"])
            self.assertTrue(nachher["Friondo WB Standard"].endswith(vorher_alt["Friondo WB Standard"]))
            for name in ("Friondo Enni", "Friondo SWD", "Friondo Sparkasse DU", "Friondo PV Enni",
                         "Friondo KL Enni", "Friondo WB Enni"):
                self.assertEqual(nachher[name], vorher_alt[name], name)
            # Layout v3 (Vertragsbedingungen/Auftrag) bleibt gleich – der Parser überliest [CLOOVER]
            for name in ("Friondo Standard", "Friondo PV Standard", "Friondo KL Standard", "Friondo WB Standard"):
                geparst_alt = pdf_kontext.nachtext_parsen(vorher_alt[name])
                geparst_neu = pdf_kontext.nachtext_parsen(nachher[name])
                self.assertEqual(pdf_kontext.bedingungen_aus(geparst_alt), pdf_kontext.bedingungen_aus(geparst_neu), name)
                self.assertEqual((geparst_alt["aufschiebende_bedingung"], geparst_alt["umsetzungsdatum"],
                                  geparst_alt["ausfuehrungszeitraum"]),
                                 (geparst_neu["aufschiebende_bedingung"], geparst_neu["umsetzungsdatum"],
                                  geparst_neu["ausfuehrungszeitraum"]))
            # zweiter Lauf: nichts
            self.assertEqual(angebotsprofile.migriere_cloover_platzhalter(self.s), [])
            # reine Textfunktion ebenfalls idempotent
            for name in ("Friondo Standard", "Friondo KL Standard"):
                self.assertEqual(angebotsprofile.cloover_platzhalter_einsetzen(nachher[name])[1], [])
        finally:
            self.s.rollback()
            for block in self.s.query(Textblock).filter(Textblock.art == "nachtext"):
                if block.name in vorher:
                    block.text = vorher[block.name]
            einstellung_setzen(self.s, angebotsprofile.MARKER_V36_CLOOVER, marker_vorher)
            self.s.commit()
        self.assertEqual(self._texte(), vorher)


if __name__ == "__main__":
    unittest.main()
