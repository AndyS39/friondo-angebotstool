# v36 (PLAN_V22 Phase 192, Agent B1): Cloover-Client, Parametrierung → Cloover, Anlagen je Angebot.
# HTTP ist komplett gemockt (cloover_api._roh_anfrage bzw. urllib.request.urlopen für die Nahtstelle
# selbst) – kein Netzzugriff. Der API-Key kommt nur über mock.patch.object(config, "CLOOVER_API_KEY", …)
# und darf danach in keiner Log-/Protokolldatei stehen (Test). Läuft gegen DB_PFAD_OVERRIDE (Kopie);
# eigene Daten (Testkunde cloover-v36@test.local, Benutzer mit Präfix V36B1, Parameter cloover_*,
# Fehlerprotokoll-Einträge „Cloover“) werden wieder aufgeräumt.
import io
import json
import unittest
import urllib.error
import warnings
from unittest import mock

warnings.filterwarnings("ignore")

from fastapi.testclient import TestClient

from app import angebot_aufbau, auth, cloover_api, cloover_texte, config, fehlerprotokoll
from app import vorgaenge as vorgaenge_modul
from app.db import SessionLocal, init_db
from app.main import app
from app.models import (Angebot, AngebotsPosition, Benutzer, Einstellung, Erfassung, Fehlerprotokoll,
                        Kunde, SteckbriefWert, Vorgang, VorgangsNotiz, einstellung_holen,
                        einstellung_setzen)

KEY = "test-key-v36-B1-GEHEIM-4711"
EMAIL = "cloover-v36@test.local"
NACHNAME = "V36B1 Cloover"
ID_NAME = "V36B1 Innendienst"
AD_NAME = "V36B1 Aussendienst"
STANDARD_EMAIL = "c.castro@friondo.de"
GEWERK_ID_FAKE = 987_654          # Steckbrief-Zeile ohne echtes Gewerk (nur SteckbriefWert)
PARAMETER = tuple(cloover_api.PARAMETER_START) + (cloover_api.EINSTELLUNG_LETZTER_TEST,
                                                   cloover_api.EINSTELLUNG_PROTOKOLL,
                                                   cloover_texte.KEY_FUSSNOTE, cloover_texte.KEY_DATENSCHUTZ)
# WP-Kontrollwerte (Plan Phase 192): 36.412,23 € netto + 19 % = 43.330,55 € − 500,00 € Rabatt
# = 42.830,55 € Endbetrag; Netto nach Rabatt 35.992,06 €; Förderung 16.500,00 €
WP_PAKET = dict(sort=1, block_nr=1, gruppe="Bosch Monoblock Wärmepumpe CS3800i AW Paket", pos_nr="047",
                bezeichnung="Bosch CS3800i AW 7 OR-S Paket", beschreibung="Paket", menge=1.0,
                einheit="psl.", e_preis_cent=3_641_223, ek_cent=2_000_000)
PV_MODULE = dict(sort=1, block_nr=1, gruppe="Komplettpaket PV-Anlage", pos_nr="PV001",
                 bezeichnung="PV-Module", beschreibung="PV-Modul", menge=1.0, einheit="psl.",
                 e_preis_cent=2_000_000, ek_cent=1_200_000)
KL_GERAET = dict(sort=1, block_nr=3, gruppe="Klimaanlage Bosch", pos_nr="KL035",
                 bezeichnung="Bosch CL3200i-Set", beschreibung="Set", menge=1.0, einheit="Set",
                 e_preis_cent=651_866, ek_cent=400_000)
WB_PAKET = dict(sort=1, block_nr=1, gruppe="Wallbox", pos_nr="WB001", bezeichnung="Mennekes AMTRON 4You 310",
                beschreibung="Wallbox", menge=1.0, einheit="Stück", e_preis_cent=223_570, ek_cent=150_000)
KFW_JSON = {"O01": "EFH", "O03": "1", "K01": "Ja", "K02": "Öl", "K03": "", "K04": "Nein"}
ANTWORTEN_WP = {"O02": "1995", "A01": "Öl", "A02": "2003", "A03": "25000", "A14": "Nein", "N02": "Ja"}
V1_ANTWORT = {"monthlyPayment": 93.3582, "currency": "EUR"}
V2_ANTWORT = {"monthlyPayment": 389.99, "monthlyPaymentAfterSubsidies": 242.70, "currency": "EUR"}
V2_TYP_FEHLER = {"message": "projectAssets.0.type must be one of the following values: Heat pump, Solar, "
                            "Battery, Wallbox", "error": "Bad Request"}


class Server:
    """Ersatz für cloover_api._roh_anfrage(methode, pfad, body): Antworten je (METHODE, Pfad); die letzte
    Antwort wiederholt sich. `antwort_fuer` (optional) entscheidet je Aufruf anhand des Bodys."""

    def __init__(self, antwort_fuer=None):
        self.aufrufe: list[dict] = []
        self.antworten: dict = {}
        self.antwort_fuer = antwort_fuer

    def setze(self, methode: str, pfad: str, *antworten):
        self.antworten[(methode.upper(), pfad)] = list(antworten)

    def __call__(self, methode, pfad, body=None):
        # JSON-Rundreise: der Body wird so festgehalten, wie er gesendet würde (35992.06 / 16500)
        self.aufrufe.append({"methode": methode.upper(), "pfad": pfad,
                             "body": json.loads(json.dumps(body)) if body is not None else None})
        if self.antwort_fuer is not None:
            ergebnis = self.antwort_fuer(methode.upper(), pfad, body)
            if ergebnis is not None:
                return ergebnis
        liste = self.antworten.get((methode.upper(), pfad))
        if not liste:
            return 404, {"message": "nicht gemockt " + pfad}
        antwort = liste.pop(0) if len(liste) > 1 else liste[0]
        return antwort[0], antwort[1]


def aufraeumen(s) -> None:
    for k in s.query(Kunde).filter(Kunde.email == EMAIL):
        for a in s.query(Angebot).filter_by(kunde_id=k.id):
            s.query(Erfassung).filter_by(angebot_id=a.id).delete(synchronize_session=False)
            s.delete(a)
        for e in s.query(Erfassung).filter_by(kunde_id=k.id):
            s.delete(e)
        for v in s.query(Vorgang).filter_by(kunde_id=k.id):
            s.query(VorgangsNotiz).filter_by(vorgang_id=v.id).delete(synchronize_session=False)
            s.delete(v)
        s.delete(k)
    s.query(Benutzer).filter(Benutzer.name.in_((ID_NAME, AD_NAME))).delete(synchronize_session=False)
    s.query(SteckbriefWert).filter_by(gewerk_id=GEWERK_ID_FAKE).delete(synchronize_session=False)
    s.query(Fehlerprotokoll).filter(Fehlerprotokoll.fehlertyp == "Cloover",
                                    Fehlerprotokoll.pfad.like("/api/%")).delete(synchronize_session=False)
    s.commit()


class Basis(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        init_db()
        cls.s = SessionLocal()
        aufraeumen(cls.s)
        cls.kunde = Kunde(anrede="Herr", vorname="Max", nachname=NACHNAME, strasse="Teststr. 1",
                          plz="47139", ort="Duisburg", email=EMAIL, telefon="0203 123456")
        cls.innen = Benutzer(name=ID_NAME, rolle="innendienst", aktiv=True, email="v36b1-innen@test.local",
                             pin_hash=auth.pin_hash("4321"))
        cls.ad = Benutzer(name=AD_NAME, rolle="aussendienst", aktiv=True, email="v36b1-ad@test.local",
                          pin_hash=auth.pin_hash("4321"))
        cls.s.add_all([cls.kunde, cls.innen, cls.ad])
        cls.s.commit()
        cls.vorgang = vorgaenge_modul.vorgang_fuer_kunde(cls.s, cls.kunde.id)
        cls.s.commit()
        # bisherige Parameterwerte merken (None = Zeile gab es nicht)
        cls.alt = {}
        for name in PARAMETER:
            zeile = cls.s.query(Einstellung).filter(Einstellung.name == name).first()
            cls.alt[name] = None if zeile is None else zeile.wert
        cls.client = TestClient(app, raise_server_exceptions=False)
        cls.client.cookies.set(auth.COOKIE_NAME, auth.cookie_wert(1))          # Admin (Dev-ID 1)
        cls.innen_client = TestClient(app, raise_server_exceptions=False)
        cls.innen_client.cookies.set(auth.COOKIE_NAME, auth.cookie_wert(cls.innen.id))
        cls.ad_client = TestClient(app, raise_server_exceptions=False)
        cls.ad_client.cookies.set(auth.COOKIE_NAME, auth.cookie_wert(cls.ad.id))

    @classmethod
    def tearDownClass(cls):
        # offene Änderungen der Testsitzung verwerfen (z. B. letzten_test_merken ohne Commit) – sonst
        # trifft ein ausstehendes UPDATE auf die gleich gelöschte Zeile (StaleDataError)
        cls.s.rollback()
        cls.s.expire_all()
        for name, wert in cls.alt.items():
            if wert is None:
                cls.s.query(Einstellung).filter(Einstellung.name == name).delete(synchronize_session=False)
            else:
                einstellung_setzen(cls.s, name, wert)
        cls.s.commit()
        aufraeumen(cls.s)
        cls.s.close()
        cloover_api.cache_leeren()

    def setUp(self):
        for a in self.s.query(Angebot).filter_by(kunde_id=self.kunde.id):
            self.s.query(Erfassung).filter_by(angebot_id=a.id).delete(synchronize_session=False)
            self.s.delete(a)
        self.s.query(SteckbriefWert).filter_by(gewerk_id=GEWERK_ID_FAKE).delete(synchronize_session=False)
        for name in PARAMETER:
            einstellung_setzen(self.s, name, cloover_api.PARAMETER_START.get(name, ""))
        self.s.commit()
        self.s.expire_all()
        cloover_api.cache_leeren()
        patcher = mock.patch.object(config, "CLOOVER_API_KEY", KEY)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.addCleanup(cloover_api.cache_leeren)

    # --- Helfer ----------------------------------------------------------------------------
    def einstellung(self, name: str, wert: str) -> None:
        einstellung_setzen(self.s, name, wert)
        self.s.commit()
        self.s.expire_all()
        cloover_api.cache_leeren()

    def angebot(self, sparte: str, positionen: list[dict], **felder) -> Angebot:
        a = angebot_aufbau.angebot_anlegen(self.s, self.kunde.id, sparte=sparte)
        a.vorgang_id = self.vorgang.id
        for p in positionen:
            a.positionen.append(AngebotsPosition(**dict(p)))
        for name, wert in felder.items():
            setattr(a, name, wert)
        self.s.commit()
        self.s.expire_all()
        return self.s.get(Angebot, a.id)

    def wp_kontroll(self, **felder) -> Angebot:
        return self.angebot("WP", [WP_PAKET], rabatt_cent=50_000, foerderung_manuell_cent=1_650_000,
                            kfw_json=json.dumps(KFW_JSON), **felder)

    def fehlerprotokoll_cloover(self) -> list[Fehlerprotokoll]:
        self.s.commit()
        return (self.s.query(Fehlerprotokoll).filter(Fehlerprotokoll.fehlertyp == "Cloover")
                .order_by(Fehlerprotokoll.id.desc()).all())


# --- Client: Body, Rundung, Rückfall, Fehler --------------------------------------------------

class Client(Basis):
    def test_body_v2_woertlich_mit_wp_kontrollwerten(self):
        angebot = self.wp_kontroll()
        self.assertEqual(angebot.summen()["endbetrag"], 4_283_055)
        assets = cloover_api.assets_fuer(self.s, angebot)
        server = Server()
        server.setze("POST", cloover_api.PFAD_RATE_V2, (200, V2_ANTWORT))
        with mock.patch.object(cloover_api, "_roh_anfrage", server):
            ergebnis = cloover_api.rate_berechnen(assets, 15, 0, STANDARD_EMAIL,
                                                  brutto_cent=angebot.summen()["endbetrag"])
        self.assertEqual(len(server.aufrufe), 1)
        self.assertEqual(server.aufrufe[0]["pfad"], "/api/price-calculator/v2")
        self.assertEqual(server.aufrufe[0]["body"], {
            "userEmail": STANDARD_EMAIL, "country": "Germany",
            "projectAssets": [{"type": "Heat pump",
                               "priceInfo": {"price": 35992.06, "vatPercentage": 19, "subsidy": 16500,
                                             "currency": "EUR"},
                               "capacity": 8}],
            "durationInYears": 15, "downPayment": 0, "inflateTransactionFee": False})
        self.assertEqual(ergebnis["quelle"], "v2")
        self.assertEqual(ergebnis["rate_ohne_cent"], 38_999)
        self.assertEqual(ergebnis["rate_mit_cent"], 24_270)
        self.assertEqual(ergebnis["laufzeit_jahre"], 15)
        self.assertEqual(ergebnis["antwort"], V2_ANTWORT)
        # Anzahlung in EUR mit 2 Stellen, Laufzeit außerhalb 1–25 wird vor dem Netz abgewiesen
        with mock.patch.object(cloover_api, "_roh_anfrage", server):
            cloover_api.rate_berechnen(assets, 20, 150_050, STANDARD_EMAIL)
            with self.assertRaises(cloover_api.ClooverFehler):
                cloover_api.rate_berechnen(assets, 26, 0, STANDARD_EMAIL)
        self.assertEqual(server.aufrufe[-1]["body"]["downPayment"], 1500.5)
        self.assertEqual(len(server.aufrufe), 2)

    def test_rundung_kaufmaennisch_auf_cent(self):
        self.assertEqual(cloover_api._rate_cent(93.3582), 9336)
        self.assertEqual(cloover_api._rate_cent(93.355), 9336)
        self.assertEqual(cloover_api._rate_cent(93.354), 9335)
        self.assertEqual(cloover_api._rate_cent("273.16"), 27316)
        self.assertEqual(cloover_api._rate_cent(389.99), 38999)
        self.assertIsNone(cloover_api._rate_cent(None))
        self.assertIsNone(cloover_api._rate_cent("abc"))
        # Rate aus der Antwort in der Rückgabe
        server = Server()
        server.setze("POST", cloover_api.PFAD_RATE_V2, (200, {"monthlyPayment": 93.3582}))
        with mock.patch.object(cloover_api, "_roh_anfrage", server):
            ergebnis = cloover_api.rate_berechnen([{"type": "Solar"}], 10, 200_000, STANDARD_EMAIL)
        self.assertEqual(ergebnis["rate_ohne_cent"], 9336)
        self.assertIsNone(ergebnis["rate_mit_cent"])
        self.assertEqual(server.aufrufe[0]["body"]["downPayment"], 2000)

    def test_v1_rueckfall_bei_abgelehntem_anlagentyp(self):
        server = Server()
        server.setze("POST", cloover_api.PFAD_RATE_V2, (422, V2_TYP_FEHLER))
        server.setze("POST", cloover_api.PFAD_RATE_V1, (200, {"monthlyPayment": 273.16, "currency": "EUR"}))
        asset = {"type": "Energetic Renovation", "priceInfo": {"price": 6518.66, "vatPercentage": 19,
                                                                "subsidy": 0, "currency": "EUR"}}
        with mock.patch.object(cloover_api, "_roh_anfrage", server):
            ergebnis = cloover_api.rate_berechnen([asset], 15, 0, STANDARD_EMAIL, brutto_cent=4_283_055)
        self.assertEqual([a["pfad"] for a in server.aufrufe],
                         ["/api/price-calculator/v2", "/api/price-calculator"])
        self.assertEqual(server.aufrufe[1]["body"], {
            "totalCostOfInstallation": 42830.55, "userEmail": STANDARD_EMAIL, "durationInYears": 15,
            "downPayment": 0, "currency": "EUR"})
        self.assertEqual(ergebnis["quelle"], "v1")
        self.assertEqual(ergebnis["rate_ohne_cent"], 27316)
        self.assertIsNone(ergebnis["rate_mit_cent"])
        self.assertIn("projectAssets.0.type", ergebnis["v2_fehler"])
        # ohne brutto_cent oder mit rueckfall=False: kein v1, Meldung der v2-Antwort
        server2 = Server()
        server2.setze("POST", cloover_api.PFAD_RATE_V2, (422, V2_TYP_FEHLER))
        with mock.patch.object(cloover_api, "_roh_anfrage", server2):
            with self.assertRaises(cloover_api.ClooverFehler) as cm:
                cloover_api.rate_berechnen([asset], 15, 0, STANDARD_EMAIL)
            with self.assertRaises(cloover_api.ClooverFehler):
                cloover_api.rate_berechnen([asset], 15, 0, STANDARD_EMAIL, brutto_cent=1, rueckfall=False)
        self.assertEqual(cm.exception.status, 422)
        self.assertTrue(cm.exception.meldung.startswith("Cloover: Eingabe abgelehnt (projectAssets.0.type"))
        self.assertEqual([a["pfad"] for a in server2.aufrufe], ["/api/price-calculator/v2"] * 2)
        # 401 löst keinen Rückfall aus
        server3 = Server()
        server3.setze("POST", cloover_api.PFAD_RATE_V2, (401, {"message": "Invalid API key"}))
        with mock.patch.object(cloover_api, "_roh_anfrage", server3):
            with self.assertRaises(cloover_api.ClooverFehler) as cm:
                cloover_api.rate_berechnen([asset], 15, 0, STANDARD_EMAIL, brutto_cent=1_000_000)
        self.assertEqual(cm.exception.meldung, cloover_api.MELDUNG_KEY_ABGELEHNT)
        self.assertEqual(len(server3.aufrufe), 1)

    def test_fehlerbloecke_und_texte(self):
        faelle = [
            (401, {"message": "Invalid API key"}, "Cloover: API-Key abgelehnt"),
            (422, {"message": "durationInYears must not be greater than 25", "error": "Unprocessable Entity"},
             "Cloover: Eingabe abgelehnt (durationInYears must not be greater than 25)"),
            (400, {"message": "inflateTransactionFee cannot be set to true for this organization",
                   "error": "Bad Request"},
             "Cloover: inflateTransactionFee cannot be set to true for this organization"),
            (400, {"message": ["userEmail must be an email", "country should not be empty"]},
             "Cloover: userEmail must be an email; country should not be empty"),
            (500, {"message": "Internal server error"}, cloover_api.MELDUNG_NICHT_ERREICHBAR),
            (503, {}, cloover_api.MELDUNG_NICHT_ERREICHBAR),
            (0, {"error": "timed out"}, cloover_api.MELDUNG_NICHT_ERREICHBAR),
            (429, {"message": "Too Many Requests"}, "Cloover: zu viele Anfragen (HTTP 429) – später erneut versuchen"),
            (403, {"message": "Forbidden"}, "Cloover: Zugriff verweigert (HTTP 403): Forbidden"),
            (418, {}, "Cloover: HTTP 418"),
        ]
        for status, antwort, erwartet in faelle:
            self.assertEqual(cloover_api.fehler_meldung(status, antwort), erwartet, (status, antwort))
            server = Server()
            server.setze("POST", cloover_api.PFAD_RATE_V2, (status, antwort))
            with mock.patch.object(cloover_api, "_roh_anfrage", server):
                with self.assertRaises(cloover_api.ClooverFehler) as cm:
                    cloover_api.rate_berechnen([{"type": "Solar"}], 10, 0, STANDARD_EMAIL)
            self.assertEqual(cm.exception.meldung, erwartet)
            self.assertEqual(cm.exception.status, status)

    def test_fehlerprotokoll_ohne_key_und_ohne_kundendaten(self):
        angebot = self.wp_kontroll()
        assets = cloover_api.assets_fuer(self.s, angebot)
        server = Server()
        server.setze("POST", cloover_api.PFAD_RATE_V2, (422, {"message": "projectAssets.0.capacity must be a number"}))
        with mock.patch.object(cloover_api, "_roh_anfrage", server):
            with self.assertRaises(cloover_api.ClooverFehler):
                cloover_api.rate_berechnen(assets, 15, 0, EMAIL)
        eintraege = self.fehlerprotokoll_cloover()
        self.assertTrue(eintraege, "kein Fehlerprotokoll-Eintrag „Cloover“")
        eintrag = eintraege[0]
        self.assertEqual(eintrag.pfad, "/api/price-calculator/v2")
        self.assertEqual(eintrag.methode, "EXTERN")
        self.assertEqual(eintrag.meldung, "POST /api/price-calculator/v2 → HTTP 422")
        self.assertIn("Felder: userEmail, country, projectAssets, projectAssets[].type, "
                      "projectAssets[].priceInfo, projectAssets[].priceInfo.price", eintrag.traceback)
        self.assertIn("Antwort: projectAssets.0.capacity must be a number", eintrag.traceback)
        for geheim in (KEY, EMAIL, "35992.06", "16500"):
            self.assertNotIn(geheim, eintrag.traceback, geheim)
            self.assertNotIn(geheim, eintrag.meldung, geheim)
        # Datei-Log ohne Key
        pfad = fehlerprotokoll.log_pfad()
        if pfad.exists():
            self.assertNotIn(KEY, pfad.read_text(encoding="utf-8", errors="replace"))
        # Netzfehler (Status 0) ebenfalls protokolliert, Antwortzeile ohne Key
        server.setze("POST", cloover_api.PFAD_RATE_V2, (0, {"error": f"URLError key={KEY}"}))
        with mock.patch.object(cloover_api, "_roh_anfrage", server):
            with self.assertRaises(cloover_api.ClooverFehler) as cm:
                cloover_api.rate_berechnen(assets, 15, 0, EMAIL)
        self.assertEqual(cm.exception.meldung, cloover_api.MELDUNG_NICHT_ERREICHBAR)
        eintrag = self.fehlerprotokoll_cloover()[0]
        self.assertEqual(eintrag.meldung, "POST /api/price-calculator/v2 → HTTP 0")
        self.assertNotIn(KEY, eintrag.traceback)
        self.assertIn("***", eintrag.traceback)

    def test_modus_aus_und_ohne_key_keine_aufrufe(self):
        server = Server()
        server.setze("POST", cloover_api.PFAD_RATE_V2, (200, V2_ANTWORT))
        self.einstellung(cloover_api.EINSTELLUNG_MODUS, "aus")
        self.assertEqual(cloover_api.modus(self.s), "aus")
        cloover_api.cache_leeren()        # der Client liest den Modus ohne Sitzung nach
        with mock.patch.object(cloover_api, "_roh_anfrage", server):
            for aufruf in (lambda: cloover_api.rate_berechnen([{"type": "Solar"}], 10, 0, STANDARD_EMAIL),
                           lambda: cloover_api.projekt_status("prj_1"),
                           lambda: cloover_api.projekt_anlegen(
                               {"vorname": "Max", "nachname": "M", "email": EMAIL, "telefon": "1"},
                               {"strasse": "A 1", "plz": "47139", "ort": "Duisburg"}, [{"type": "Solar"}],
                               (1, 20), ["Cash"], ["https://x/y.pdf"], STANDARD_EMAIL)):
                with self.assertRaises(cloover_api.ClooverFehler) as cm:
                    aufruf()
                self.assertEqual(cm.exception.meldung, cloover_api.MELDUNG_MODUS_AUS)
            self.assertEqual(server.aufrufe, [])
            # Nachtrag 17.10.2026 (Rückfrage 8): der Verbindungstest läuft auch im Modus „aus“ – mit Zusatz
            server.setze("POST", cloover_api.PFAD_RATE_V1, (200, V1_ANTWORT))
            ok, text = cloover_api.verbindung_testen(self.s)
        self.assertTrue(ok, text)
        self.assertEqual(text, "Verbindung OK · Beispielrate 93,36 €/Monat (Test-Umgebung) · "
                               "Wärmepumpe: Typ Heat pump akzeptiert · Photovoltaik: Typ Solar akzeptiert · "
                               "Klima: Typ Energetic Renovation akzeptiert · Wallbox: Typ Wallbox akzeptiert · "
                               + cloover_api.ZUSATZ_TEST_MODUS_AUS)
        self.assertEqual([a["pfad"] for a in server.aufrufe],
                         [cloover_api.PFAD_RATE_V1] + [cloover_api.PFAD_RATE_V2] * 4)
        self.assertTrue(cloover_api.letzter_test(self.s)["ok"])
        self.assertEqual(cloover_api.modus(self.s), "aus")                 # der Test schaltet den Modus nicht um
        server.aufrufe.clear()
        # ohne Key: Modul aus, egal was gespeichert ist
        self.einstellung(cloover_api.EINSTELLUNG_MODUS, "test")
        with mock.patch.object(config, "CLOOVER_API_KEY", ""), \
                mock.patch.object(cloover_api, "_roh_anfrage", server):
            self.assertFalse(cloover_api.konfiguriert())
            self.assertEqual(cloover_api.modus(self.s), "aus")
            with self.assertRaises(cloover_api.ClooverFehler) as cm:
                cloover_api.rate_berechnen([{"type": "Solar"}], 10, 0, STANDARD_EMAIL)
            self.assertEqual(cm.exception.meldung, cloover_api.MELDUNG_KEY_FEHLT)
            ok, text = cloover_api.verbindung_testen(self.s)
        self.assertEqual((ok, text), (False, cloover_api.MELDUNG_KEY_FEHLT))
        self.assertEqual(server.aufrufe, [])
        # Modus test mit Key: Aufruf läuft
        with mock.patch.object(cloover_api, "_roh_anfrage", server):
            cloover_api.rate_berechnen([{"type": "Solar"}], 10, 0, STANDARD_EMAIL)
        self.assertEqual(len(server.aufrufe), 1)

    def test_live_nur_mit_live_url(self):
        self.einstellung(cloover_api.EINSTELLUNG_MODUS, "live")
        self.assertEqual(cloover_api.modus_gespeichert(self.s), "live")
        self.assertEqual(cloover_api.modus(self.s), "test")          # Test-URL → wirksam test
        with mock.patch.object(config, "CLOOVER_BASIS_URL", "https://partners-api.cloover.com"):
            self.assertFalse(cloover_api.ist_test_url())
            self.assertEqual(cloover_api.modus(self.s), "live")
            self.assertEqual(cloover_api.basis_url(), "https://partners-api.cloover.com")

    def test_roh_anfrage_header_body_timeout(self):
        gesehen = {}

        class Antwort(io.BytesIO):
            status = 200

            def __enter__(self):
                return self

            def __exit__(self, *_):
                return False

        def urlopen(anfrage, timeout=None):
            gesehen["anfrage"] = anfrage
            gesehen["timeout"] = timeout
            return Antwort(b'{"monthlyPayment": 93.3582, "currency": "EUR"}')

        with mock.patch.object(cloover_api.urllib.request, "urlopen", urlopen):
            status, antwort = cloover_api._roh_anfrage("post", "/api/price-calculator",
                                                       {"totalCostOfInstallation": 10000, "userEmail": STANDARD_EMAIL})
        self.assertEqual((status, antwort), (200, {"monthlyPayment": 93.3582, "currency": "EUR"}))
        anfrage = gesehen["anfrage"]
        self.assertEqual(anfrage.get_method(), "POST")
        self.assertEqual(anfrage.full_url, cloover_api.TEST_URL + "/api/price-calculator")
        kopf = {k.lower(): v for k, v in anfrage.header_items()}
        self.assertEqual(kopf["x-api-key"], KEY)
        self.assertEqual(kopf["content-type"], "application/json")
        self.assertEqual(kopf["accept"], "application/json")
        self.assertEqual(json.loads(anfrage.data.decode("utf-8")),
                         {"totalCostOfInstallation": 10000, "userEmail": STANDARD_EMAIL})
        self.assertEqual(gesehen["timeout"], 20)
        self.assertEqual(cloover_api.TIMEOUT_S, 20)
        # HTTPError → (Status, Fehlerblock); URLError/Timeout → (0, {"error": …}); leerer Body → {}
        fehler = urllib.error.HTTPError(anfrage.full_url, 401, "Unauthorized", {},
                                        io.BytesIO(b'{"message": "Invalid API key", "error": "Unauthorized"}'))
        with mock.patch.object(cloover_api.urllib.request, "urlopen", mock.Mock(side_effect=fehler)):
            self.assertEqual(cloover_api._roh_anfrage("GET", "/api/projects/x"),
                             (401, {"message": "Invalid API key", "error": "Unauthorized"}))
        with mock.patch.object(cloover_api.urllib.request, "urlopen",
                               mock.Mock(side_effect=urllib.error.URLError("timed out"))):
            status, antwort = cloover_api._roh_anfrage("GET", "/api/projects/x")
        self.assertEqual(status, 0)
        self.assertIn("timed out", antwort["error"])
        with mock.patch.object(cloover_api.urllib.request, "urlopen", lambda *a, **k: Antwort(b"")):
            self.assertEqual(cloover_api._roh_anfrage("GET", "/api/projects/x"), (200, {}))
        with mock.patch.object(cloover_api.urllib.request, "urlopen", lambda *a, **k: Antwort(b"<html>")):
            self.assertEqual(cloover_api._roh_anfrage("GET", "/api/projects/x"), (200, {"text": "<html>"}))


# --- Projekt anlegen / Status ------------------------------------------------------------------

class Projekt(Basis):
    def test_projekt_anlegen_body_und_antwort(self):
        server = Server()
        server.setze("POST", cloover_api.PFAD_PROJEKTE,
                     (201, {"project_id": "prj_123", "checkout_link": "https://app.cloover.com/checkout/abc",
                            "financial_offer": "https://app.cloover.com/offer/abc"}))
        asset = {"type": "Heat pump", "priceInfo": {"price": 35992.06, "vatPercentage": 19, "subsidy": 16500,
                                                    "currency": "EUR"}, "capacity": 7}
        with mock.patch.object(cloover_api, "_roh_anfrage", server):
            ergebnis = cloover_api.projekt_anlegen(
                {"vorname": "Max", "nachname": "Mustermann", "email": EMAIL, "telefon": "+49 203 123456"},
                {"strasse": "Teststr. 1", "plz": "47139", "ort": "Duisburg"}, [asset], (1, 20),
                ["Financing", "Cash", "Unbekannt"], ["https://ablage.example/AN-C-261001-abc.pdf"], STANDARD_EMAIL)
        self.assertEqual(server.aufrufe[0]["body"], {
            "userEmail": STANDARD_EMAIL,
            "customer": {"firstName": "Max", "lastName": "Mustermann", "email": EMAIL,
                         "phone": "+49 203 123456", "type": "Individual"},
            "projectAddress": {"street": "Teststr. 1", "city": "Duisburg", "postalCode": "47139",
                               "country": "Germany"},
            "projectAssets": [asset], "financingDuration": {"start": 1, "end": 20},
            "financingOption": ["Cash", "Financing"],
            "offerPDF": ["https://ablage.example/AN-C-261001-abc.pdf"], "inflateTransactionFee": False})
        self.assertEqual(ergebnis["projekt_id"], "prj_123")
        self.assertEqual(ergebnis["checkout_link"], "https://app.cloover.com/checkout/abc")
        self.assertEqual(ergebnis["financial_offer"], "https://app.cloover.com/offer/abc")
        # API-Schlüssel der Eingabe-Dicts werden ebenfalls verstanden
        with mock.patch.object(cloover_api, "_roh_anfrage", server):
            cloover_api.projekt_anlegen(
                {"firstName": "Max", "lastName": "M", "email": EMAIL, "phone": "1"},
                {"street": "A 1", "postalCode": "47139", "city": "Duisburg"}, [asset], (5, 3), ["Cash"],
                ["https://x/y.pdf"], STANDARD_EMAIL)
        self.assertEqual(server.aufrufe[1]["body"]["financingDuration"], {"start": 3, "end": 5})

    def test_projekt_anlegen_voraussetzungen_und_fehler(self):
        server = Server()
        server.setze("POST", cloover_api.PFAD_PROJEKTE, (422, {"message": "customer.phone must be a valid phone number"}))
        asset = {"type": "Solar"}
        kunde = {"vorname": "Max", "nachname": "M", "email": EMAIL, "telefon": ""}
        adresse = {"strasse": "A 1", "plz": "47139", "ort": "Duisburg"}
        with mock.patch.object(cloover_api, "_roh_anfrage", server):
            with self.assertRaises(cloover_api.ClooverFehler) as cm:
                cloover_api.projekt_anlegen(kunde, adresse, [asset], (1, 20), ["Cash"], ["https://x/y.pdf"], STANDARD_EMAIL)
            self.assertEqual(cm.exception.meldung, "Cloover: Kundendaten unvollständig (fehlt: phone)")
            kunde["telefon"] = "0203 1"
            with self.assertRaises(cloover_api.ClooverFehler) as cm:
                cloover_api.projekt_anlegen(kunde, adresse, [asset], (1, 20), ["Cash"], [], STANDARD_EMAIL)
            self.assertIn("offerPDF fehlt", cm.exception.meldung)
            with self.assertRaises(cloover_api.ClooverFehler) as cm:
                cloover_api.projekt_anlegen(kunde, adresse, [asset], (1, 20), [], ["https://x/y.pdf"], STANDARD_EMAIL)
            self.assertIn("keine Finanzierungsoption", cm.exception.meldung)
            with self.assertRaises(cloover_api.ClooverFehler) as cm:
                cloover_api.projekt_anlegen(kunde, {"strasse": "", "plz": "47139", "ort": ""}, [asset], (1, 20),
                                            ["Cash"], ["https://x/y.pdf"], STANDARD_EMAIL)
            self.assertEqual(cm.exception.meldung, "Cloover: Adresse unvollständig (fehlt: street, city)")
            self.assertEqual(server.aufrufe, [])          # alles vor dem Netz abgewiesen
            with self.assertRaises(cloover_api.ClooverFehler) as cm:
                cloover_api.projekt_anlegen(kunde, adresse, [asset], (1, 20), ["Cash"], ["https://x/y.pdf"], STANDARD_EMAIL)
        self.assertEqual(cm.exception.status, 422)
        self.assertEqual(cm.exception.meldung,
                         "Cloover: Eingabe abgelehnt (customer.phone must be a valid phone number)")
        eintrag = self.fehlerprotokoll_cloover()[0]
        self.assertEqual(eintrag.pfad, "/api/projects")
        self.assertIn("customer.phone", eintrag.traceback)
        for geheim in (KEY, EMAIL, "Max", "47139"):
            self.assertNotIn(geheim, eintrag.traceback, geheim)
        # Antwort ohne project_id/checkout_link
        server.setze("POST", cloover_api.PFAD_PROJEKTE, (201, {"status": "created"}))
        with mock.patch.object(cloover_api, "_roh_anfrage", server):
            with self.assertRaises(cloover_api.ClooverFehler) as cm:
                cloover_api.projekt_anlegen(kunde, adresse, [asset], (1, 20), ["Cash"], ["https://x/y.pdf"], STANDARD_EMAIL)
        self.assertEqual(cm.exception.meldung, "Cloover: Antwort ohne project_id/checkout_link")

    def test_projekt_status(self):
        server = Server()
        server.setze("GET", "/api/projects/prj_123",
                     (200, {"id": "prj_123", "status": "contract_signed", "primary_signed_contract": True,
                            "secondary_signed_contract": False, "contract_signed_date": "2026-10-20",
                            "financing_option_chosen": "Financing"}))
        with mock.patch.object(cloover_api, "_roh_anfrage", server):
            daten = cloover_api.projekt_status("prj_123")
            with self.assertRaises(cloover_api.ClooverFehler) as cm:
                cloover_api.projekt_status("prj_999")
        self.assertEqual(daten["id"], "prj_123")
        self.assertEqual(daten["status"], "contract_signed")          # unbekannte Werte roh (Rückfrage B8)
        self.assertIs(daten["primary_signed_contract"], True)
        self.assertIs(daten["secondary_signed_contract"], False)
        self.assertEqual(daten["contract_signed_date"], "2026-10-20")
        self.assertEqual(daten["financing_option_chosen"], "Financing")
        self.assertEqual(daten["antwort"]["status"], "contract_signed")
        self.assertEqual(server.aufrufe[0]["methode"], "GET")
        self.assertIsNone(server.aufrufe[0]["body"])
        self.assertEqual(cm.exception.status, 404)
        self.assertEqual(cm.exception.meldung, "Cloover: Projekt prj_999 nicht gefunden (HTTP 404)")
        with self.assertRaises(cloover_api.ClooverFehler):
            cloover_api.projekt_status("")


# --- Anlagen aus dem Angebot ---------------------------------------------------------------------

class Assets(Basis):
    def test_wp_mit_foerderung_kontrollwerte(self):
        angebot = self.wp_kontroll()
        summen = angebot.summen()
        self.assertEqual((summen["endbetrag"], summen["netto_nach_rabatt"]), (4_283_055, 3_599_206))
        self.assertEqual(cloover_api.foerderung_cent(self.s, angebot), 1_650_000)
        assets = cloover_api.assets_fuer(self.s, angebot)
        self.assertEqual(len(assets), 1)
        self.assertEqual(assets[0]["type"], "Heat pump")
        self.assertEqual(assets[0]["priceInfo"], {"price": 35992.06, "vatPercentage": 19, "subsidy": 16500,
                                                   "currency": "EUR"})
        # capacity: ohne Steckbrief/Erfassung die Nennleistung der BAFA-Anlage zur Paket-Position 047 (8 kW)
        self.assertEqual(cloover_api.kapazitaet_fuer(self.s, angebot), (8.0, "bafa"))
        self.assertEqual(assets[0]["capacity"], 8)
        # Erfassung am Angebot: Leistungsklasse aus der Paketmatrix (25.000 kWh → „10 kW“)
        self.s.add(Erfassung(kunde_id=self.kunde.id, benutzer_id=1, sparte="WP", angebot_id=angebot.id,
                             status="Erledigt", antworten_json=json.dumps(ANTWORTEN_WP)))
        self.s.commit()
        self.assertEqual(cloover_api.kapazitaet_fuer(self.s, angebot), (10.0, "erfassung"))
        # Steckbrief des verknüpften Gewerks hat Vorrang („7 kW (CS3800i)“, auch manuell korrigiert)
        self.s.add(SteckbriefWert(gewerk_id=GEWERK_ID_FAKE, feld="leistungsklasse", wert="7 kW (CS3800i)",
                                  manuell=True))
        angebot.projekt_gewerk_id = GEWERK_ID_FAKE
        self.s.commit()
        self.assertEqual(cloover_api.kapazitaet_fuer(self.s, angebot), (7.0, "steckbrief"))
        self.assertEqual(cloover_api.assets_fuer(self.s, angebot)[0]["capacity"], 7)
        # Förderblock ausgeblendet → subsidy 0; Förderung ohne Rabatt → price = Netto
        angebot.foerderung_ausblenden = True
        angebot.rabatt_cent = None
        self.s.commit()
        asset = cloover_api.assets_fuer(self.s, angebot)[0]
        self.assertEqual(asset["priceInfo"]["subsidy"], 0)
        self.assertEqual(asset["priceInfo"]["price"], 36412.23)

    def test_pv_null_prozent(self):
        angebot = self.angebot("PV", [PV_MODULE], pv_json=json.dumps({"kwp": 11.375, "module": 25}))
        self.assertEqual(angebot.ust_satz, 0.0)
        self.assertEqual(angebot.summen()["endbetrag"], 2_000_000)
        assets = cloover_api.assets_fuer(self.s, angebot)
        self.assertEqual(assets, [{"type": "Solar",
                                   "priceInfo": {"price": 20000, "vatPercentage": 0, "subsidy": 0,
                                                 "currency": "EUR"},
                                   "capacity": 11.375}])
        self.assertEqual(cloover_api.foerderung_cent(self.s, angebot), 0)
        # PV mit Gesamtrabatt 5 % (v33 Phase 172: Rabatt vom Netto bei 0 %) → price 19000
        angebot.rabatt_prozent = 5.0
        self.s.commit()
        self.assertEqual(cloover_api.assets_fuer(self.s, angebot)[0]["priceInfo"]["price"], 19000)
        # ohne pv_json keine capacity (Schlüssel entfällt)
        angebot.pv_json = ""
        self.s.commit()
        self.assertNotIn("capacity", cloover_api.assets_fuer(self.s, angebot)[0])

    def test_kl_typ_aus_parameter_und_kuehllast(self):
        kl_json = {"serie": "3200i", "raeume": [{"nr": 1, "kuehllast_kw": 1.98}, {"nr": 2, "kuehllast_kw": 2.52}]}
        angebot = self.angebot("KL", [KL_GERAET], kl_json=json.dumps(kl_json))
        assets = cloover_api.assets_fuer(self.s, angebot)
        self.assertEqual(assets, [{"type": "Energetic Renovation",
                                   "priceInfo": {"price": 6518.66, "vatPercentage": 19, "subsidy": 0,
                                                 "currency": "EUR"},
                                   "capacity": 4.5}])
        self.einstellung("cloover_kl_typ", "Battery")
        self.assertEqual(cloover_api.assets_fuer(self.s, angebot)[0]["type"], "Battery")
        self.einstellung("cloover_kl_typ", "Unsinn")            # unbekannt → Standard
        self.assertEqual(cloover_api.kl_typ(self.s), "Energetic Renovation")

    def test_wb_wallbox_11(self):
        angebot = self.angebot("WB", [WB_PAKET])
        self.assertEqual(cloover_api.assets_fuer(self.s, angebot), [
            {"type": "Wallbox", "priceInfo": {"price": 2235.7, "vatPercentage": 19, "subsidy": 0,
                                              "currency": "EUR"}, "capacity": 11}])
        # Sparten ohne Cloover-Typ und TAIFUN-Einträge liefern kein Asset
        gw = self.angebot("GW", [WB_PAKET])
        self.assertEqual(cloover_api.assets_fuer(self.s, gw), [])
        extern = self.angebot("WP", [], extern=True, extern_endbetrag_cent=1_000_000)
        self.assertEqual(cloover_api.assets_fuer(self.s, extern), [])


# --- Verbindungstest ------------------------------------------------------------------------------

class Verbindungstest(Basis):
    def test_wortlaut_und_v2_probe(self):
        server = Server()
        server.setze("POST", cloover_api.PFAD_RATE_V1, (200, V1_ANTWORT))
        server.setze("POST", cloover_api.PFAD_RATE_V2, (200, V2_ANTWORT))
        with mock.patch.object(cloover_api, "_roh_anfrage", server):
            ok, text = cloover_api.verbindung_testen(self.s)
        self.assertTrue(ok)
        self.assertEqual(text, "Verbindung OK · Beispielrate 93,36 €/Monat (Test-Umgebung) · "
                               "Wärmepumpe: Typ Heat pump akzeptiert · Photovoltaik: Typ Solar akzeptiert · "
                               "Klima: Typ Energetic Renovation akzeptiert · Wallbox: Typ Wallbox akzeptiert")
        self.assertEqual(server.aufrufe[0]["pfad"], "/api/price-calculator")
        self.assertEqual(server.aufrufe[0]["body"], {"totalCostOfInstallation": 10000, "userEmail": STANDARD_EMAIL,
                                                     "durationInYears": 10, "downPayment": 2000, "currency": "EUR"})
        proben = server.aufrufe[1:]
        self.assertEqual([a["pfad"] for a in proben], ["/api/price-calculator/v2"] * 4)
        self.assertEqual([a["body"]["projectAssets"][0]["type"] for a in proben],
                         ["Heat pump", "Solar", "Energetic Renovation", "Wallbox"])
        for a in proben:
            self.assertEqual((a["body"]["durationInYears"], a["body"]["downPayment"], a["body"]["inflateTransactionFee"]),
                             (20, 0, False))
            self.assertEqual(a["body"]["userEmail"], STANDARD_EMAIL)
        letzter = cloover_api.letzter_test(self.s)
        self.assertTrue(letzter["ok"])
        self.assertEqual(letzter["text"], text)
        self.assertRegex(letzter["zeit"], r"\d\d\.\d\d\.\d{4} \d\d:\d\d")

    def test_key_abgelehnt_und_typ_abgelehnt(self):
        server = Server()
        server.setze("POST", cloover_api.PFAD_RATE_V1, (401, {"message": "Invalid API key"}))
        with mock.patch.object(cloover_api, "_roh_anfrage", server):
            ok, text = cloover_api.verbindung_testen(self.s)
        self.assertEqual((ok, text), (False, "Cloover erreichbar, aber Key abgelehnt (HTTP 401)"))
        self.assertEqual(len(server.aufrufe), 1)                  # keine v2-Probe nach 401
        self.assertFalse(cloover_api.letzter_test(self.s)["ok"])

        def antwort_fuer(methode, pfad, body):
            if pfad == cloover_api.PFAD_RATE_V2 and body["projectAssets"][0]["type"] == "Energetic Renovation":
                return 422, V2_TYP_FEHLER
            return None

        server2 = Server(antwort_fuer)
        server2.setze("POST", cloover_api.PFAD_RATE_V1, (200, V1_ANTWORT))
        server2.setze("POST", cloover_api.PFAD_RATE_V2, (200, V2_ANTWORT))
        self.einstellung("cloover_sparten", "WP,KL")
        with mock.patch.object(cloover_api, "_roh_anfrage", server2):
            ok, text = cloover_api.verbindung_testen(self.s)
        self.assertTrue(ok)
        self.assertEqual(text, "Verbindung OK · Beispielrate 93,36 €/Monat (Test-Umgebung) · "
                               "Wärmepumpe: Typ Heat pump akzeptiert · Klima: Typ Energetic Renovation abgelehnt: "
                               "Eingabe abgelehnt (projectAssets.0.type must be one of the following values: "
                               "Heat pump, Solar, Battery, Wallbox)")
        # nicht erreichbar; Live-URL ohne Zusatz „(Test-Umgebung)“
        server3 = Server()
        server3.setze("POST", cloover_api.PFAD_RATE_V1, (0, {"error": "timed out"}))
        with mock.patch.object(cloover_api, "_roh_anfrage", server3):
            ok, text = cloover_api.verbindung_testen(self.s)
        self.assertEqual((ok, text), (False, cloover_api.MELDUNG_NICHT_ERREICHBAR))
        server4 = Server()
        server4.setze("POST", cloover_api.PFAD_RATE_V1, (200, V1_ANTWORT))
        server4.setze("POST", cloover_api.PFAD_RATE_V2, (200, V2_ANTWORT))
        self.einstellung("cloover_sparten", cloover_api.KEINE_SPARTEN)
        self.assertEqual(cloover_api.sparten(self.s), [])
        with mock.patch.object(config, "CLOOVER_BASIS_URL", "https://partners-api.cloover.com"), \
                mock.patch.object(cloover_api, "_roh_anfrage", server4):
            ok, text = cloover_api.verbindung_testen(self.s)
        self.assertEqual((ok, text), (True, "Verbindung OK · Beispielrate 93,36 €/Monat"))

    def test_route_und_seite(self):
        server = Server()
        server.setze("POST", cloover_api.PFAD_RATE_V1, (200, V1_ANTWORT))
        server.setze("POST", cloover_api.PFAD_RATE_V2, (200, V2_ANTWORT))
        with mock.patch.object(cloover_api, "_roh_anfrage", server):
            r = self.client.post("/parametrierung/cloover/test",
                                 data={"cloover_modus": "test", "cloover_standard_email": STANDARD_EMAIL},
                                 follow_redirects=False)
        self.assertEqual(r.status_code, 303)
        self.assertTrue(r.headers["location"].startswith("/parametrierung/cloover?test="), r.headers["location"])
        seite = self.client.get(r.headers["location"]).text
        self.assertIn("Verbindungstest: Verbindung OK · Beispielrate 93,36 €/Monat (Test-Umgebung)", seite)
        self.assertIn("Letzter Verbindungstest: <strong class=\"ampel gruen\">ok</strong>", seite)
        self.assertNotIn(KEY, seite)
        # Innendienst darf nicht testen
        r = self.innen_client.post("/parametrierung/cloover/test", data={}, follow_redirects=False)
        self.assertEqual(r.status_code, 403)


# --- Parametrierung → Cloover -----------------------------------------------------------------------

class Parametrierung(Basis):
    def test_seite_admin_ohne_key_wert_innendienst_403(self):
        r = self.client.get("/parametrierung/cloover")
        self.assertEqual(r.status_code, 200)
        self.assertIn("Angebotstool → Cloover", r.text)
        self.assertIn("Key gesetzt", r.text)
        self.assertNotIn(KEY, r.text)
        self.assertNotIn("•••", r.text)                  # auch nicht maskiert
        self.assertIn(cloover_api.TEST_URL, r.text)
        self.assertIn("Test-Umgebung", r.text)
        for name in ("cloover_modus", "cloover_standard_email", "cloover_laufzeit_jahre", "cloover_anzahlung_eur",
                     "cloover_optionen", "cloover_laufzeit_min", "cloover_laufzeit_max", "cloover_sparten",
                     "cloover_kl_typ", "cloover_fussnote", "cloover_datenschutz"):
            self.assertIn(f'name="{name}"', r.text, name)
        self.assertIn('action="/parametrierung/cloover/test"', r.text)
        self.assertIn("Entwurf – Rückfrage B1", r.text)
        self.assertIn(cloover_texte.FUSSNOTE_STANDARD[:60], r.text)
        self.assertIn("Standardtext", r.text)
        # Phase 194 (B3): Abschnitt „PDF-Ablage“ mit dem aktuellen Anbieter – der Kontext kommt aus der Route
        # (ablage=seiten_kontext(session)), nicht über den Jinja-Global-Rückfall des Partials
        from app import cloover_pdf_ablage
        from app.templating import templates

        def rueckfall_verboten():
            raise RuntimeError("Partial nutzt den Jinja-Global-Rückfall statt des Routen-Kontexts")

        with mock.patch.dict(templates.env.globals, {"cloover_ablage_kontext": rueckfall_verboten}):
            r = self.client.get("/parametrierung/cloover")
        self.assertEqual(r.status_code, 200)
        self.assertIn('id="ablage"', r.text)
        self.assertIn('name="cloover_pdf_ablage"', r.text)
        anbieter = cloover_pdf_ablage.seiten_kontext(self.s)["anbieter"]
        self.assertIn(f'<option value="{anbieter}" selected>', r.text)
        self.assertIn('action="/parametrierung/cloover/ablage"', r.text)
        # nach Speichern/Test (Umleitung auf die Seite) ebenfalls mit Ablage-Abschnitt
        with mock.patch.dict(templates.env.globals, {"cloover_ablage_kontext": rueckfall_verboten}):
            r = self.client.post("/parametrierung/cloover", data={"cloover_modus": "test"}, follow_redirects=True)
        self.assertEqual(r.status_code, 200)
        self.assertIn('id="ablage"', r.text)
        # Innendienst: 403; Außendienst: die Middleware leitet schon vor der Route um (303) – nie 200
        for client, erlaubt in ((self.innen_client, (403,)), (self.ad_client, (303, 403))):
            r = client.get("/parametrierung/cloover", follow_redirects=False)
            self.assertIn(r.status_code, erlaubt)
            self.assertNotIn(KEY, r.text)
            self.assertIn(client.post("/parametrierung/cloover", data={"cloover_modus": "aus"},
                                      follow_redirects=False).status_code, erlaubt)
        self.assertEqual(cloover_api.modus_gespeichert(self.s), "test")
        # ohne Key: Hinweis „Key fehlt – Modul aus“, Test-Knopf gesperrt
        with mock.patch.object(config, "CLOOVER_API_KEY", ""):
            r = self.client.get("/parametrierung/cloover")
        self.assertEqual(r.status_code, 200)
        self.assertIn("Key fehlt – Modul aus", r.text)
        # Verteilerseite: Eintrag nur für Admins
        self.assertEqual(self.client.get("/parametrierung").text.count('href="/parametrierung/cloover"'), 1)
        self.assertNotIn('href="/parametrierung/cloover"', self.innen_client.get("/parametrierung").text)

    def test_live_ohne_live_url_abgelehnt(self):
        r = self.client.post("/parametrierung/cloover", data={"cloover_modus": "live"}, follow_redirects=False)
        self.assertEqual(r.status_code, 303)
        seite = self.client.get(r.headers["location"]).text
        self.assertIn("nur mit Live-URL", seite)
        self.s.expire_all()
        self.assertEqual(cloover_api.modus_gespeichert(self.s), "test")
        self.assertNotIn("cloover_modus", cloover_api.protokoll(self.s))
        with mock.patch.object(config, "CLOOVER_BASIS_URL", "https://partners-api.cloover.com"):
            r = self.client.post("/parametrierung/cloover", data={"cloover_modus": "live"}, follow_redirects=False)
            seite = self.client.get(r.headers["location"]).text
            self.assertIn("Cloover-Einstellungen gespeichert", seite)
            self.assertIn("Live-URL", seite)
            self.s.expire_all()
            self.assertEqual(cloover_api.modus(self.s), "live")
        self.assertIn("cloover_modus: test → live", cloover_api.protokoll(self.s))
        # zurück auf Test-URL: gespeichert live, wirksam test – die Seite zeigt beides
        seite = self.client.get("/parametrierung/cloover").text
        self.assertIn("gespeichert „live“", seite)

    def test_parameter_speichern_validierung_und_protokoll(self):
        daten = {"cloover_formular": "1", "cloover_modus": "test", "cloover_standard_email": "finanzierung@friondo.de",
                 "cloover_laufzeit_jahre": "15", "cloover_anzahlung_eur": "1.500,00",
                 "cloover_optionen": ["Cash"], "cloover_laufzeit_min": "2", "cloover_laufzeit_max": "15",
                 "cloover_sparten": ["WP", "PV"], "cloover_kl_typ": "Battery",
                 "cloover_fussnote": "Eigene Fußnote {endbetrag} {laufzeit}", "cloover_datenschutz": ""}
        r = self.client.post("/parametrierung/cloover", data=daten, follow_redirects=False)
        self.assertEqual(r.status_code, 303)
        self.s.expire_all()
        self.assertEqual(cloover_api.standard_email(self.s), "finanzierung@friondo.de")
        self.assertEqual(cloover_api.laufzeit_jahre(self.s), 15)
        self.assertEqual(cloover_api.anzahlung_cent(self.s), 150_000)
        self.assertEqual(cloover_api.optionen(self.s), ["Cash"])
        self.assertEqual(cloover_api.laufzeit_von_bis(self.s), (2, 15))
        self.assertEqual(cloover_api.sparten(self.s), ["WP", "PV"])
        self.assertEqual(cloover_api.kl_typ(self.s), "Battery")
        self.assertEqual(cloover_texte.text_holen(self.s, "cloover_fussnote"), "Eigene Fußnote {endbetrag} {laufzeit}")
        self.assertTrue(cloover_texte.ist_standard(self.s, "cloover_datenschutz"))
        protokoll = cloover_api.protokoll(self.s)
        for text in ("cloover_standard_email: c.castro@friondo.de → finanzierung@friondo.de",
                     "cloover_laufzeit_jahre: 20 → 15", "cloover_anzahlung_eur: 0,00 → 1.500,00",
                     "cloover_optionen: Cash, Financing → Cash", "cloover_laufzeit_min/_max: 1–20 → 2–15",
                     "cloover_sparten: WP, PV, KL, WB → WP, PV", "cloover_kl_typ: Energetic Renovation → Battery",
                     "cloover_fussnote: Standard → eigener Text"):
            self.assertIn(text, protokoll, text)
        self.assertNotIn(KEY, protokoll)
        seite = self.client.get("/parametrierung/cloover").text
        self.assertIn('value="finanzierung@friondo.de"', seite)
        self.assertIn('value="1.500,00"', seite)
        self.assertIn("Eigene Fußnote {endbetrag} {laufzeit}", seite)
        # ungültige Werte: Meldung, nichts geändert; gültige Teile desselben Formulars werden gespeichert
        r = self.client.post("/parametrierung/cloover",
                             data={"cloover_laufzeit_jahre": "30", "cloover_anzahlung_eur": "abc",
                                   "cloover_standard_email": "kein-mail", "cloover_laufzeit_min": "10",
                                   "cloover_laufzeit_max": "5", "cloover_kl_typ": "Unsinn",
                                   "cloover_fussnote": ""},
                             follow_redirects=False)
        seite = self.client.get(r.headers["location"]).text
        for text in ("Laufzeit: ganze Zahl zwischen 1 und 25", "Anzahlung: Betrag in Euro erwartet",
                     "keine E-Mail-Adresse", "financingDuration: 1 ≤ von ≤ bis ≤ 25", "kein Cloover-Anlagentyp",
                     "Übrige Änderungen gespeichert"):
            self.assertIn(text, seite, text)
        self.s.expire_all()
        self.assertEqual(cloover_api.laufzeit_jahre(self.s), 15)
        self.assertEqual(cloover_api.anzahlung_cent(self.s), 150_000)
        self.assertEqual(cloover_api.standard_email(self.s), "finanzierung@friondo.de")
        self.assertEqual(cloover_api.laufzeit_von_bis(self.s), (2, 15))
        self.assertEqual(cloover_api.kl_typ(self.s), "Battery")
        self.assertTrue(cloover_texte.ist_standard(self.s, "cloover_fussnote"))     # leer = Standard
        self.assertIn("cloover_fussnote: eigener Text → Standard", cloover_api.protokoll(self.s))
        # Teil-POST ohne das vollständige Formular lässt Optionen/Sparten unverändert
        self.client.post("/parametrierung/cloover", data={"cloover_modus": "test"}, follow_redirects=False)
        self.s.expire_all()
        self.assertEqual(cloover_api.optionen(self.s), ["Cash"])
        self.assertEqual(cloover_api.sparten(self.s), ["WP", "PV"])
        # leere Optionen im vollständigen Formular werden abgewiesen
        r = self.client.post("/parametrierung/cloover", data={"cloover_formular": "1", "cloover_sparten": ["KL"]},
                             follow_redirects=False)
        self.assertIn("mindestens+eine+Option", r.headers["location"])
        self.s.expire_all()
        self.assertEqual(cloover_api.optionen(self.s), ["Cash"])
        self.assertEqual(cloover_api.sparten(self.s), ["KL"])
        # keine Sparte gewählt → gespeichert als KEINE_SPARTEN (leer hieße Standard = alle vier)
        self.client.post("/parametrierung/cloover", data={"cloover_formular": "1", "cloover_optionen": ["Cash"]},
                         follow_redirects=False)
        self.s.expire_all()
        self.assertEqual(cloover_api.sparten(self.s), [])
        self.assertEqual(einstellung_holen(self.s, "cloover_sparten", ""), cloover_api.KEINE_SPARTEN)
        self.assertIn("cloover_sparten: KL → –", cloover_api.protokoll(self.s))


# --- Benutzerfeld, Texte ------------------------------------------------------------------------------

class BenutzerfeldUndTexte(Basis):
    def test_benutzerfeld_cloover_konto(self):
        seite = self.client.get("/benutzer").text
        details_innen = seite.split(f'id="details-{self.innen.id}"')[1].split("</tr>")[0]
        details_ad = seite.split(f'id="details-{self.ad.id}"')[1].split("</tr>")[0]
        self.assertIn('name="cloover_email"', details_innen)
        self.assertIn("Cloover-Konto (E-Mail)", details_innen)
        self.assertNotIn('name="cloover_email"', details_ad)
        grund = {"name": ID_NAME, "rolle": "innendienst", "email": "v36b1-innen@test.local", "aktiv": "on",
                 "benachrichtigung_mail": "aus", "cloover_dabei": "1"}
        r = self.client.post(f"/benutzer/{self.innen.id}/aendern", data=dict(grund, cloover_email="C.Test@friondo.de"),
                             follow_redirects=False)
        self.assertEqual(r.status_code, 303)
        self.s.expire_all()
        innen = self.s.get(Benutzer, self.innen.id)
        self.assertEqual(innen.cloover_email, "c.test@friondo.de")
        self.assertEqual(cloover_api.user_email_fuer(self.s, innen), "c.test@friondo.de")
        self.assertIn('value="c.test@friondo.de"', self.client.get("/benutzer").text)
        # ungültig → Meldung, unverändert; ohne cloover_dabei unverändert; leer = Standard-Konto
        r = self.client.post(f"/benutzer/{self.innen.id}/aendern", data=dict(grund, cloover_email="kein-mail"),
                             follow_redirects=False)
        self.assertIn("Cloover-Konto", r.headers["location"])
        self.client.post(f"/benutzer/{self.innen.id}/aendern",
                         data={k: v for k, v in grund.items() if k != "cloover_dabei"}, follow_redirects=False)
        self.s.expire_all()
        self.assertEqual(self.s.get(Benutzer, self.innen.id).cloover_email, "c.test@friondo.de")
        self.client.post(f"/benutzer/{self.innen.id}/aendern", data=dict(grund, cloover_email=""),
                         follow_redirects=False)
        self.s.expire_all()
        innen = self.s.get(Benutzer, self.innen.id)
        self.assertEqual(innen.cloover_email, "")
        self.assertEqual(cloover_api.user_email_fuer(self.s, innen), STANDARD_EMAIL)
        self.assertEqual(cloover_api.user_email_fuer(self.s, None), STANDARD_EMAIL)
        # Außendienst: auch mit gesetztem Feld nie das eigene Konto (Projekte nur über Innendienst/Admin)
        ad = self.s.get(Benutzer, self.ad.id)
        ad.cloover_email = "ad@friondo.de"
        self.s.commit()
        self.assertEqual(cloover_api.user_email_fuer(self.s, ad), STANDARD_EMAIL)

    def test_textbausteine_standard_und_rendern(self):
        self.assertEqual(cloover_texte.text_holen(self.s, "cloover_fussnote"), cloover_texte.FUSSNOTE_STANDARD)
        self.assertEqual(cloover_texte.text_holen(self.s, "cloover_datenschutz"), cloover_texte.DATENSCHUTZ_STANDARD)
        self.assertIn("https://friondo.de/Datenschutz", cloover_texte.datenschutz_text(self.s))
        mit = cloover_texte.fussnote_rendern(self.s, endbetrag="42.830,55 €", laufzeit=20, anzahlung="0,00 €",
                                              foerderung="16.500,00 €", stand="15.10.2026")
        self.assertEqual(mit, "*Unverbindliche Beispielrechnung unseres Finanzierungspartners Cloover auf Basis des "
                              "Endbetrags dieses Angebots von 42.830,55 €, einer Laufzeit von 20 Jahren und 0,00 € "
                              "Anzahlung; ‚mit Förderung‘ berücksichtigt die voraussichtliche Förderung von "
                              "16.500,00 € als Sondertilgung nach Auszahlung. Stand 15.10.2026. Verbindliche "
                              "Konditionen, Sollzins und effektiver Jahreszins ergeben sich aus dem "
                              "Finanzierungsangebot von Cloover.")
        ohne = cloover_texte.fussnote_rendern(self.s, endbetrag="20.000,00 €", laufzeit=15, anzahlung="1.500,00 €",
                                               stand="16.10.2026")
        self.assertEqual(ohne, "*Unverbindliche Beispielrechnung unseres Finanzierungspartners Cloover auf Basis des "
                               "Endbetrags dieses Angebots von 20.000,00 €, einer Laufzeit von 15 Jahren und "
                               "1.500,00 € Anzahlung. Stand 16.10.2026. Verbindliche Konditionen, Sollzins und "
                               "effektiver Jahreszins ergeben sich aus dem Finanzierungsangebot von Cloover.")
        # eigener Text: Platzhalter ersetzt, Förder-Halbsatz entfällt ohne Förderung; Standard wiederherstellen
        cloover_texte.text_setzen(self.s, "cloover_fussnote",
                                  "Rate für {endbetrag}; mit Förderung von {foerderung} nach Auszahlung. {stand}")
        self.s.commit()
        self.assertEqual(cloover_texte.fussnote_rendern(self.s, endbetrag="1 €", laufzeit=1, anzahlung="0 €",
                                                         stand="heute"), "Rate für 1 €. heute")
        self.assertEqual(cloover_texte.fussnote_rendern(self.s, endbetrag="1 €", laufzeit=1, anzahlung="0 €",
                                                         stand="heute", foerderung="2 €"),
                         "Rate für 1 €; mit Förderung von 2 € nach Auszahlung. heute")
        self.assertEqual(cloover_texte.text_setzen(self.s, "cloover_fussnote", cloover_texte.FUSSNOTE_STANDARD), "")
        self.s.commit()
        self.assertTrue(cloover_texte.ist_standard(self.s, "cloover_fussnote"))
        with self.assertRaises(KeyError):
            cloover_texte.text_setzen(self.s, "cloover_unbekannt", "x")

    def test_eur_helfer(self):
        self.assertEqual(cloover_api.eur_parsen("1.500,00"), 150_000)
        self.assertEqual(cloover_api.eur_parsen("1500"), 150_000)
        self.assertEqual(cloover_api.eur_parsen("1500.5"), 150_050)
        self.assertEqual(cloover_api.eur_parsen("2.000"), 200_000)
        self.assertEqual(cloover_api.eur_parsen("0,005"), 1)
        self.assertIsNone(cloover_api.eur_parsen("abc"))
        self.assertIsNone(cloover_api.eur_parsen(""))
        self.assertEqual(cloover_api.eur_text(4_283_055), "42.830,55")
        self.assertEqual(cloover_api.eur_text(0), "0,00")
        self.assertEqual(cloover_api._eur(3_599_206), 35992.06)
        self.assertEqual(cloover_api._eur(2_000_000), 20000)
        self.assertIsInstance(cloover_api._eur(2_000_000), int)


if __name__ == "__main__":
    unittest.main()
