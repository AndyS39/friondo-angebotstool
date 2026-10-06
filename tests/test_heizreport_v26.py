# Tests PLAN_PROJ_V5 (v26, Phasen 122–124): Heizreport-Kunden-API v2.
# Teil 1 (Phase 122): Warteschlange 600 ms (gemockte Uhr), 429 mit Retry-After
# genau einmal wiederholt, Verbindungstest wörtlich, Fehlerprotokoll ohne Token.
# Teil 2 (Phase 123): Body projectData wörtlich (Demo-Gewerk mit Erfassung),
# Kennzahlen-Parameter, Anlage 201 → Schlüssel, Timeout → Suche in GET /reports,
# zweiter Klick → 409, Schlüssel von Hand, Verknüpfung lösen.
# Teil 3 (Phase 124): Heizlast aus results (Pfad / Raumsumme), Abgleich mit der
# verkauften Leistungsklasse (Paketmatrix-Heizlastspalte), 422
# calculation_unavailable, PDF-Ablage in der Galerie mit Rückfrage.
# HTTP ist komplett gemockt (heizreport_api._roh_anfrage) – kein Netzzugriff.
# Laufen gegen die Entwicklungs-DB; Testdaten (Kunde heizreport-v26@test.local)
# werden wieder aufgeräumt.
import json
import shutil
import unittest
import warnings
from datetime import datetime
from unittest import mock

warnings.filterwarnings("ignore")

from fastapi.testclient import TestClient

from app import angebot_aufbau, config
from app import heizreport_api as hr
from app import projektierung as kern
from app.db import SessionLocal, init_db
from app.main import app
from app.models import (Angebot, AngebotsPosition, Aufgabe, AufgabenpaketInstanz,
                        Erfassung, Fehlerprotokoll, GalerieDatei, Gewerk, Kunde, Projekt,
                        ProjektTermin, ProjektVerlauf, SteckbriefWert, Vorgang,
                        angebot_status_setzen)

TEST_EMAIL = "heizreport-v26@test.local"
TOKEN = "v26-test-token-GEHEIM-xyz123"
PARAMETER = ("heizreport_modus", "heizreport_api_key", "heizreport_kennzahlen",
             "heizreport_pdf_ordner", "heizreport_pfad_heizlast", "url_heizreport",
             "heizreport_api_url", "heizreport_protokoll")
ERFASSUNG = {"O02": "1995", "A01": "Öl", "A02": "2003", "A03": "25000", "A10": "Nein",
             "N02": "Ja", "A14": "Nein"}
PR_NUMMER = "PR-260012"
AN_NUMMER = "AN-C-260099"
KEY = "abcdefghi"


def aufraeumen(s):
    from app.models import ProjektMail, UglBestellung
    for k in s.query(Kunde).filter(Kunde.email == TEST_EMAIL):
        for p in s.query(Projekt).filter_by(kunde_id=k.id):
            for g in s.query(Gewerk).filter_by(projekt_id=p.id):
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
            shutil.rmtree(config.DATA_ORDNER / "vorgaenge" / str(v.id), ignore_errors=True)
            s.delete(v)
        s.delete(k)
    # Fehlerprotokoll-Einträge der gemockten Aufrufe (Quelle Heizreport, Pfad /api/v2…)
    s.query(Fehlerprotokoll).filter(Fehlerprotokoll.fehlertyp == "Heizreport",
                                    Fehlerprotokoll.pfad.like("/api/v2%")).delete(
        synchronize_session=False)
    s.commit()


class Uhr:
    """Gemockte monotone Uhr: _schlafen rückt die Zeit vor und merkt sich die Dauer."""

    def __init__(self):
        self.t = 1000.0
        self.schlaf: list[float] = []

    def jetzt(self) -> float:
        return self.t

    def schlafen(self, sekunden: float) -> None:
        self.schlaf.append(sekunden)
        self.t += sekunden


class Server:
    """Ersatz für heizreport_api._roh_anfrage: Antworten je (METHODE, Pfad)."""

    def __init__(self, uhr: Uhr | None = None):
        self.aufrufe: list[dict] = []
        self.antworten: dict = {}
        self.uhr = uhr

    def setze(self, methode: str, pfad: str, *antworten):
        """Jede Antwort: (status, body) oder (status, body, headers); die letzte
        Antwort wiederholt sich."""
        self.antworten[(methode.upper(), pfad)] = list(antworten)

    def __call__(self, methode, url, kopf, koerper, timeout):
        pfad = url
        if url.startswith(hr.BASIS_V2):
            pfad = url[len(hr.BASIS_V2):] or "/"
        pfad = pfad.split("?", 1)[0]
        self.aufrufe.append({"methode": methode.upper(), "url": url, "pfad": pfad,
                             "kopf": dict(kopf), "koerper": koerper,
                             "zeit": self.uhr.jetzt() if self.uhr else None})
        liste = self.antworten.get((methode.upper(), pfad))
        if not liste:
            return 404, json.dumps({"status": 404, "error": "nicht gemockt " + pfad,
                                    "details": {}}).encode(), {}
        antwort = liste.pop(0) if len(liste) > 1 else liste[0]
        status, body = antwort[0], antwort[1]
        headers = antwort[2] if len(antwort) > 2 else {}
        if isinstance(body, bytes):
            return status, body, headers
        return status, json.dumps(body, ensure_ascii=False).encode("utf-8"), headers


def param_setzen(name: str, wert) -> None:
    """Parameter in einer eigenen Session schreiben (die Routen schreiben über
    eigene Sessions – die Testsession darf keine veralteten Objekte behalten).
    wert None = Zeile entfernen."""
    from app.models import ProjektierungParameter
    s = SessionLocal()
    try:
        if wert is None:
            s.query(ProjektierungParameter).filter_by(name=name).delete()
        else:
            kern.parameter_setzen(s, name, wert)
        s.commit()
    finally:
        s.close()


def param_holen(name: str) -> str:
    s = SessionLocal()
    try:
        return kern.parameter_holen(s, name, "")
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
        cls.alt = {n: kern.parameter_holen(cls.s, n, None) for n in PARAMETER}
        for name, wert in (("heizreport_modus", "v2"), ("heizreport_api_key", TOKEN),
                           ("heizreport_kennzahlen", ""),
                           ("heizreport_pdf_ordner", "Montagedokumente"),
                           ("heizreport_pfad_heizlast", hr.PFAD_HEIZLAST_STANDARD),
                           ("url_heizreport", "https://heizreport.net/pro"),
                           ("heizreport_protokoll", "")):
            param_setzen(name, wert)
        cls.s.expire_all()

    @classmethod
    def tearDownClass(cls):
        aufraeumen(cls.s)
        for name, wert in cls.alt.items():
            param_setzen(name, wert)
        cls.s.close()

    zaehler = 0

    def setUp(self):
        aufraeumen(self.s)              # jeder Test startet ohne Testprojekte (Nummern eindeutig)
        hr._letzter_aufruf[0] = 0.0
        param_setzen("heizreport_modus", "v2")
        param_setzen("heizreport_api_key", TOKEN)
        param_setzen("heizreport_kennzahlen", "")
        self.s.expire_all()

    def param(self, name: str, wert: str) -> None:
        param_setzen(name, wert)
        self.s.expire_all()

    def server(self, uhr=None) -> Server:
        return Server(uhr)

    def gewerk_neu(self, erfassung=None, klasse="7 kW (CS3800i)", telefon="", nummern=None):
        """Projekt + Gewerk; nummern=(PR, AN) für die wörtlichen Plan-Werte, sonst
        eindeutige Testnummern (die Spalten nummer sind unique)."""
        Basis.zaehler += 1
        pr, an = nummern or (f"PR-26V{Basis.zaehler:03d}", f"AN-C-26V{Basis.zaehler:03d}")
        kunde = Kunde(anrede="Herr", vorname="Max", nachname="Mustermann",
                      strasse="Musterstraße 12a", plz="47139", ort="Duisburg",
                      email=TEST_EMAIL, telefon=telefon)
        self.s.add(kunde)
        self.s.flush()
        angebot = angebot_aufbau.angebot_anlegen(self.s, kunde.id, sparte="WP")
        angebot.positionen.append(AngebotsPosition(
            sort=1, pos_nr="047", bezeichnung="Pos 047", beschreibung="Pos 047",
            menge=1, e_preis_cent=10000))
        angebot.nummer = an
        angebot_status_setzen(angebot, "Angenommen")
        self.s.commit()
        if erfassung is not None:
            self.s.add(Erfassung(kunde_id=kunde.id, benutzer_id=1, sparte="WP",
                                 angebot_id=angebot.id, status="Erledigt",
                                 antworten_json=json.dumps(erfassung, ensure_ascii=False)))
            self.s.commit()
        projekt = kern.projekt_anlegen(self.s, angebot, projektleiter_id=1)
        projekt.nummer = pr
        projekt.ausfuehrung_strasse = "Musterstraße 12a"
        projekt.ausfuehrung_plz = "47139"
        projekt.ausfuehrung_ort = "Duisburg"
        gewerk = kern.gewerk_anlegen(self.s, projekt, angebot, "WP")
        self.s.commit()
        zeile = (self.s.query(SteckbriefWert)
                 .filter_by(gewerk_id=gewerk.id, feld="leistungsklasse").first())
        if klasse:
            if zeile is None:
                self.s.add(SteckbriefWert(gewerk_id=gewerk.id, feld="leistungsklasse",
                                          wert=klasse, manuell=True))
            else:
                zeile.wert, zeile.manuell = klasse, True
        elif zeile is not None:
            zeile.wert = ""
        self.s.commit()
        return gewerk

    def heizlast_aufgabe(self, gewerk) -> Aufgabe:
        return (self.s.query(Aufgabe)
                .filter(Aufgabe.gewerk_id == gewerk.id, Aufgabe.aktion_typ == "api",
                        Aufgabe.aktion_wert == "heizreport").first())

    def verlauf_texte(self, gewerk) -> list[str]:
        return [e.text for e in self.s.query(ProjektVerlauf)
                .filter(ProjektVerlauf.gewerk_id == gewerk.id).order_by(ProjektVerlauf.id)]

    def zeile_html(self, aufgabe) -> str:
        from app.routers.projektierung import _aufgabe_zeile_html
        self.s.expire_all()
        return _aufgabe_zeile_html(self.s, self.s.get(Aufgabe, aufgabe.id))


# --- Teil 1: Client, Ratenlimit, Verbindungstest, Fehlerprotokoll --------------------------

class Teil1Client(Basis):
    def test_warteschlange_haelt_600_ms(self):
        uhr = Uhr()
        server = self.server(uhr)
        server.setze("GET", "/reports", (200, {"projekte": [], "leads": [], "api": [], "archiv": []}))
        with mock.patch.object(hr, "_roh_anfrage", server), \
                mock.patch.object(hr, "_uhr", uhr.jetzt), \
                mock.patch.object(hr, "_schlafen", uhr.schlafen):
            for _ in range(5):
                status, _antwort = hr._anfrage_v2(self.s, "GET", "/reports")
                self.assertEqual(status, 200)
        zeiten = [a["zeit"] for a in server.aufrufe]
        self.assertEqual(len(zeiten), 5)
        for frueher, spaeter in zip(zeiten, zeiten[1:]):
            self.assertGreaterEqual(spaeter - frueher, hr.ABSTAND_S - 1e-9)
        self.assertEqual(len(uhr.schlaf), 4)
        self.assertTrue(all(abs(s - hr.ABSTAND_S) < 1e-9 for s in uhr.schlaf), uhr.schlaf)

    def test_429_wird_genau_einmal_wiederholt(self):
        uhr = Uhr()
        server = self.server(uhr)
        fehler = {"status": 429, "error": "Maximal zwei Zugriffe pro Sekunde und Kunde",
                  "details": {"type": "rate_limit", "retryAfter": 1}}
        server.setze("GET", "/reports", (429, fehler, {"Retry-After": "1"}),
                     (200, {"projekte": [], "leads": [], "api": [], "archiv": []}))
        with mock.patch.object(hr, "_roh_anfrage", server), \
                mock.patch.object(hr, "_uhr", uhr.jetzt), \
                mock.patch.object(hr, "_schlafen", uhr.schlafen):
            status, antwort = hr._anfrage_v2(self.s, "GET", "/reports")
        self.assertEqual(status, 200)
        self.assertEqual(len(server.aufrufe), 2)
        self.assertGreaterEqual(max(uhr.schlaf), 1.0)
        self.assertGreaterEqual(server.aufrufe[1]["zeit"] - server.aufrufe[0]["zeit"], 1.0)
        # zweimal 429 → Meldung, keine dritte Wiederholung
        server2 = self.server(uhr)
        server2.setze("GET", "/reports", (429, fehler, {"Retry-After": "1"}))
        with mock.patch.object(hr, "_roh_anfrage", server2), \
                mock.patch.object(hr, "_uhr", uhr.jetzt), \
                mock.patch.object(hr, "_schlafen", uhr.schlafen):
            status, antwort = hr._anfrage_v2(self.s, "GET", "/reports")
        self.assertEqual(status, 429)
        self.assertEqual(len(server2.aufrufe), 2)
        self.assertEqual(hr.fehler_meldung(status, antwort), hr.MELDUNG_429)

    def test_verbindungstest_wortlaut(self):
        server = self.server()
        server.setze("GET", "/health", (200, {"status": "ok", "api": "heizreport-customer-v2",
                                              "version": "2.4.0", "timestamp": "2026-10-01T12:00:00Z"}))
        server.setze("GET", "/", (200, {"name": "Heizreport Customer API", "version": "2.4.0"}))
        eintrag = {"projektKey": KEY, "projektTime": 1, "projektEmail": "", "projektName": "x",
                   "projektStatus": 1}
        server.setze("GET", "/reports", (200, {"status": 200, "action": "getReports",
                                               "projekte": [eintrag] * 3, "leads": [eintrag],
                                               "api": [eintrag] * 2, "archiv": []}))
        with mock.patch.object(hr, "_roh_anfrage", server), \
                mock.patch.object(hr, "_schlafen", lambda s: None):
            ok, text = hr.verbindung_testen(self.s)
        self.assertTrue(ok)
        self.assertEqual(text, "Verbindung OK · API-Version 2.4.0 · 6 eigene Projekte "
                               "(Gruppen: projekte 3, leads 1, api 2, archiv 0)")
        pfade = [a["pfad"] for a in server.aufrufe]
        self.assertEqual(pfade, ["/health", "/", "/reports"])
        self.assertNotIn("Authorization", server.aufrufe[0]["kopf"])
        self.assertEqual(server.aufrufe[2]["kopf"]["Authorization"], f"Bearer {TOKEN}")
        self.assertEqual(server.aufrufe[2]["kopf"]["Accept"], "application/json")
        # Token abgelehnt
        server.setze("GET", "/reports", (401, {"status": 401, "error": "Token ungültig",
                                               "details": {"type": "auth"}}))
        with mock.patch.object(hr, "_roh_anfrage", server), \
                mock.patch.object(hr, "_schlafen", lambda s: None):
            ok, text = hr.verbindung_testen(self.s)
        self.assertFalse(ok)
        self.assertEqual(text, hr.MELDUNG_TOKEN_ABGELEHNT)
        # Health nicht erreichbar (Timeout = Status 0)
        server.setze("GET", "/health", (0, b"timed out"))
        with mock.patch.object(hr, "_roh_anfrage", server), \
                mock.patch.object(hr, "_schlafen", lambda s: None):
            ok, text = hr.verbindung_testen(self.s)
        self.assertFalse(ok)
        self.assertEqual(text, hr.MELDUNG_NICHT_ERREICHBAR)

    def test_verbindungstest_route_und_seite(self):
        server = self.server()
        server.setze("GET", "/health", (200, {"status": "ok", "version": "2.4.0"}))
        server.setze("GET", "/", (200, {"name": "x", "version": "2.4.0"}))
        server.setze("GET", "/reports", (200, {"projekte": [], "leads": [], "api": [], "archiv": []}))
        with mock.patch.object(hr, "_roh_anfrage", server), \
                mock.patch.object(hr, "_schlafen", lambda s: None):
            r = self.client.post("/parametrierung/heizreport/test",
                                 data={"heizreport_modus": "v2", "heizreport_api_key": ""})
        self.assertEqual(r.status_code, 200)
        self.assertIn("Verbindung OK · API-Version 2.4.0 · 0 eigene Projekte", r.text)
        self.assertNotIn(TOKEN, r.text)                       # Token nie auf der Seite
        self.assertEqual(param_holen("heizreport_api_key"), TOKEN)

    def test_fehlermeldungen(self):
        self.assertEqual(hr.fehler_meldung(401, {}), "Heizreport: " + hr.MELDUNG_401)
        self.assertEqual(hr.fehler_meldung(403, {}), "Heizreport: " + hr.MELDUNG_403)
        self.assertEqual(hr.fehler_meldung(404, {}), "Heizreport: " + hr.MELDUNG_404)
        self.assertEqual(hr.fehler_meldung(503, {"error": "x"}), hr.MELDUNG_NICHT_ERREICHBAR)
        self.assertEqual(hr.fehler_meldung(0, "timed out"), hr.MELDUNG_NICHT_ERREICHBAR)
        self.assertEqual(hr.fehler_meldung(422, {"status": 422, "error": "Ungültige Postleitzahl",
                                                 "details": {"type": "validation",
                                                             "field": "projektPostleitzahl"}}),
                         "Heizreport: Ungültige Postleitzahl (Feld projektPostleitzahl)")
        self.assertEqual(hr.fehler_meldung(413, {"status": 413, "error": "Body zu groß",
                                                 "details": {}}),
                         "Heizreport: Body zu groß")

    def test_fehlerprotokoll_ohne_token(self):
        server = self.server()
        server.setze("GET", "/reports", (500, {"status": 500, "error": "Serverfehler",
                                               "details": {"type": "server"}}))
        vorher = self.s.query(Fehlerprotokoll).count()
        with mock.patch.object(hr, "_roh_anfrage", server), \
                mock.patch.object(hr, "_schlafen", lambda s: None):
            status, _antwort = hr._anfrage_v2(self.s, "GET", "/reports")
        self.assertEqual(status, 500)
        self.s.expire_all()
        eintraege = (self.s.query(Fehlerprotokoll)
                     .filter(Fehlerprotokoll.fehlertyp == "Heizreport")
                     .order_by(Fehlerprotokoll.id.desc()).all())
        self.assertGreaterEqual(self.s.query(Fehlerprotokoll).count(), vorher + 1)
        eintrag = eintraege[0]
        self.assertIn("GET https://heizreport.net/api/v2/reports → HTTP 500", eintrag.meldung)
        self.assertIn("Serverfehler", eintrag.traceback)
        for text in (eintrag.meldung, eintrag.traceback, eintrag.formdaten, eintrag.query,
                     eintrag.pfad):
            self.assertNotIn("Bearer", text or "")
            self.assertNotIn(TOKEN, text or "")
        # auch die Datei-Protokollzeile enthält den Token nicht
        from app import fehlerprotokoll
        log = fehlerprotokoll.log_pfad()
        if log.exists():
            zeilen = [z for z in log.read_text(encoding="utf-8", errors="replace").splitlines()
                      if "Heizreport" in z]
            self.assertTrue(zeilen)
            for zeile in zeilen:
                self.assertNotIn(TOKEN, zeile)
                self.assertNotIn("Bearer", zeile)

    def test_parametrierung_seite_und_speichern(self):
        r = self.client.get("/parametrierung/heizreport")
        self.assertEqual(r.status_code, 200)
        for text in ("Zugang", "Kennzahlen", "Ablage", "Portal-Link", "Generischer Client",
                     'name="heizreport_pdf_ordner"', "Verbindung testen",
                     "gesetzt – leer lassen = unverändert"):
            self.assertIn(text, r.text, text)
        self.assertNotIn(TOKEN, r.text)
        # ungültige Kennzahlen werden nicht gespeichert
        r = self.client.post("/parametrierung/heizreport",
                             data={"heizreport_modus": "v2", "heizreport_api_key": "",
                                   "heizreport_kennzahlen": "{kaputt",
                                   "heizreport_pdf_ordner": "Montagedokumente",
                                   "url_heizreport": "https://heizreport.net/pro",
                                   "heizreport_pfad_heizlast": hr.PFAD_HEIZLAST_STANDARD})
        self.assertIn("kein gültiges JSON", r.text)
        self.assertEqual(param_holen("heizreport_kennzahlen"), "")
        self.assertEqual(param_holen("heizreport_api_key"), TOKEN)
        # gültige Kennzahlen + Ordner + Pfad; Token bleibt bei leerem Feld
        kz = json.dumps({"art_heizung": {"Öl": 2}, "verbrauch_einheit": {"Öl": "kWh"}})
        r = self.client.post("/parametrierung/heizreport",
                             data={"heizreport_modus": "v2", "heizreport_api_key": "",
                                   "heizreport_kennzahlen": kz,
                                   "heizreport_pdf_ordner": "Förderung",
                                   "url_heizreport": "https://heizreport.net/pro",
                                   "heizreport_pfad_heizlast": "results.summary.x"})
        self.assertEqual(r.status_code, 200)
        self.s.expire_all()
        self.assertEqual(param_holen("heizreport_kennzahlen"), kz)
        self.assertEqual(param_holen("heizreport_pdf_ordner"), "Förderung")
        self.assertEqual(param_holen("heizreport_pfad_heizlast"), "results.summary.x")
        self.assertEqual(param_holen("heizreport_api_key"), TOKEN)
        self.assertIn("projektArtHeizung", r.text)
        self.assertIn("Öl → 2", r.text)
        protokoll = param_holen("heizreport_protokoll")
        self.assertIn("heizreport_kennzahlen geändert", protokoll)
        self.assertNotIn(TOKEN, protokoll)
        # Token entfernen → nicht konfiguriert; neu setzen → Protokoll „Token gesetzt“
        self.client.post("/parametrierung/heizreport",
                         data={"heizreport_modus": "v2", "heizreport_token_entfernen": "on"})
        self.s.expire_all()
        self.assertEqual(param_holen("heizreport_api_key"), "")
        self.assertFalse(hr.konfiguriert(self.s))
        self.client.post("/parametrierung/heizreport",
                         data={"heizreport_modus": "v2", "heizreport_api_key": TOKEN})
        self.s.expire_all()
        self.assertTrue(hr.konfiguriert(self.s))
        protokoll = param_holen("heizreport_protokoll")
        self.assertIn("Token entfernt", protokoll)
        self.assertIn("Token gesetzt", protokoll)
        self.assertNotIn(TOKEN, protokoll)
        self.param("heizreport_pdf_ordner", "Montagedokumente")
        self.param("heizreport_pfad_heizlast", hr.PFAD_HEIZLAST_STANDARD)
        self.s.commit()

    def test_ohne_token_link_und_upload(self):
        self.param("heizreport_api_key", "")
        self.s.commit()
        self.assertFalse(hr.konfiguriert(self.s))
        g = self.gewerk_neu()
        zeile = self.zeile_html(self.heizlast_aufgabe(g))
        self.assertIn("API nicht konfiguriert", zeile)
        self.assertNotIn("Heizreport-Projekt anlegen", zeile)
        self.assertIn("Öffnen", zeile)                      # Link url_heizreport
        self.assertIn("Ablage", zeile)


# --- Teil 2: Projekt anlegen und vorbelegen ------------------------------------------------

class Teil2Anlegen(Basis):
    ERWARTET = {
        "projektName": "Mustermann, Max – PR-260012",
        "projektPostleitzahl": "47139",
        "projektBaujahr": 1995,
        "anrede": "Herr", "vorname": "Max", "name": "Mustermann",
        "email": TEST_EMAIL,
        "strasse": "Musterstraße", "hausnummer": "12a", "plz": "47139", "ort": "Duisburg",
        "bemerkungen": ("Friondo PR-260012 · Angebot AN-C-260099 · verkauft: 7 kW (CS3800i) · "
                        "Energieträger alt: Öl, Baujahr Heizung 2003, Verbrauch 25000 kWh · "
                        "Warmwasser über WP: Ja · Solarthermie: Nein"),
    }

    def test_body_wortlaut_und_kennzahlen(self):
        g = self.gewerk_neu(ERFASSUNG, nummern=(PR_NUMMER, AN_NUMMER))
        body = hr.projektdaten_v2(self.s, g)
        self.assertEqual(list(body.keys()), ["projectData"])
        self.assertEqual(body["projectData"], self.ERWARTET)
        for wert in body["projectData"].values():
            self.assertIsInstance(wert, (str, int, float, bool))
        # Kennzahlen bestätigt → zusätzlich projektArtHeizung und projektJahresverbrauch
        self.param("heizreport_kennzahlen", json.dumps(
            {"art_heizung": {"Öl": 2}, "verbrauch_einheit": {"Öl": "kWh"}}))
        self.s.commit()
        daten = hr.projektdaten_v2(self.s, g)["projectData"]
        self.assertEqual(daten["projektArtHeizung"], 2)
        self.assertEqual(daten["projektJahresverbrauch"], 25000)
        self.assertEqual({k: v for k, v in daten.items()
                          if k not in ("projektArtHeizung", "projektJahresverbrauch")},
                         self.ERWARTET)
        # Einheit l → A03 wird NICHT umgerechnet, sondern weggelassen [A-3]
        self.param("heizreport_kennzahlen", json.dumps(
            {"art_heizung": {"Öl": 2}, "verbrauch_einheit": {"Öl": "l"},
             "alter_heizung": [{"bis_jahr": 1990, "code": 1}, {"bis_jahr": 2010, "code": 2},
                               {"bis_jahr": None, "code": 3}],
             "trinkwasser": {"Ja": 2, "Nein": 1},
             "solar_art": {"Ja, soll übernommen werden": 1}}))
        self.s.commit()
        daten = hr.projektdaten_v2(self.s, g)["projectData"]
        self.assertNotIn("projektJahresverbrauch", daten)
        self.assertEqual(daten["projektAlterHeizung"], 2)       # 2003 ≤ 2010
        self.assertEqual(daten["projektTrinkwasser"], 2)        # N02 = Ja
        self.assertNotIn("projektWaermeerzeugerSolarStatus", daten)   # A10 = Nein
        self.assertIn("Verbrauch 25000 kWh", daten["bemerkungen"])

    def test_bestandsgewerk_ohne_erfassung(self):
        g = self.gewerk_neu(None, nummern=(PR_NUMMER, AN_NUMMER))
        daten = hr.projektdaten_v2(self.s, g)["projectData"]
        self.assertEqual(daten["projektName"], "Mustermann, Max – PR-260012")
        self.assertNotIn("projektBaujahr", daten)
        self.assertEqual(daten["bemerkungen"],
                         "Friondo PR-260012 · Angebot AN-C-260099 · verkauft: 7 kW (CS3800i)")

    def test_strasse_trennen(self):
        self.assertEqual(hr.strasse_trennen("Musterstraße 12a"), ("Musterstraße", "12a"))
        self.assertEqual(hr.strasse_trennen("Am Markt 12-14"), ("Am Markt", "12-14"))
        self.assertEqual(hr.strasse_trennen("Straße 1 7"), ("Straße 1", "7"))
        self.assertEqual(hr.strasse_trennen("Hauptstraße"), ("Hauptstraße", ""))
        self.assertEqual(hr.strasse_trennen(""), ("", ""))

    def test_anlegen_201_und_zweiter_klick_409(self):
        g = self.gewerk_neu(ERFASSUNG, nummern=(PR_NUMMER, AN_NUMMER))
        aufgabe = self.heizlast_aufgabe(g)
        zeile = self.zeile_html(aufgabe)
        self.assertIn("Heizreport-Projekt anlegen", zeile)
        self.assertIn("Schlüssel von Hand eintragen", zeile)
        self.assertNotIn("Heizlast abrufen", zeile)
        akte = self.client.get(f"/projektierung/projekt/{g.projekt_id}").text
        self.assertIn("Heizreport-Projekt anlegen", akte)
        self.assertNotIn("Projekt im Heizreport anlegen", akte)      # alter v17-Knopf
        server = self.server()
        server.setze("POST", "/reports/with-data",
                     (201, {"status": 200, "action": "createReportWithData",
                            "projektHeader": {"key": KEY, "id": 1, "link": "", "status": 1},
                            "projektData": {}}))
        with mock.patch.object(hr, "_roh_anfrage", server), \
                mock.patch.object(hr, "_schlafen", lambda s: None):
            r = self.client.post(f"/projektierung/gewerk/{g.id}/heizreport/anlegen",
                                 data={"aufgabe_id": str(aufgabe.id)},
                                 headers={"Accept": "application/json"})
        self.assertEqual(r.status_code, 200, r.text)
        self.assertIn(KEY, r.json()["meldung"])
        aufruf = server.aufrufe[0]
        self.assertEqual((aufruf["methode"], aufruf["url"]),
                         ("POST", hr.BASIS_V2 + "/reports/with-data"))
        self.assertEqual(aufruf["kopf"]["Authorization"], f"Bearer {TOKEN}")
        self.assertEqual(aufruf["kopf"]["Content-Type"], "application/json")
        gesendet = json.loads(aufruf["koerper"].decode("utf-8"))
        self.assertEqual(list(gesendet.keys()), ["projectData"])
        self.assertEqual(gesendet["projectData"], self.ERWARTET)
        self.s.expire_all()
        g = self.s.get(Gewerk, g.id)
        self.assertEqual(g.heizreport_projekt_key, KEY)
        self.assertIsNotNone(g.heizreport_angelegt_am)
        self.assertEqual(self.s.get(Aufgabe, aufgabe.id).status, "offen")
        verlauf = self.verlauf_texte(g)
        self.assertTrue(any(t.startswith(f"Heizreport-Projekt {KEY} angelegt (vorbelegt: ")
                            and "projektName" in t and "bemerkungen" in t for t in verlauf), verlauf)
        zeile = self.zeile_html(aufgabe)
        self.assertNotIn("Heizreport-Projekt anlegen", zeile)
        for text in ("Heizreport öffnen ↗", "Heizlast abrufen", "Heizreport-PDF ablegen",
                     "Verknüpfung lösen", KEY):
            self.assertIn(text, zeile, text)
        # zweiter Klick ohne Lösen → 409, kein weiterer POST
        with mock.patch.object(hr, "_roh_anfrage", server), \
                mock.patch.object(hr, "_schlafen", lambda s: None):
            r = self.client.post(f"/projektierung/gewerk/{g.id}/heizreport/anlegen",
                                 data={"aufgabe_id": str(aufgabe.id)},
                                 headers={"Accept": "application/json"})
        self.assertEqual(r.status_code, 409)
        self.assertIn("bereits verknüpft", r.json()["meldung"])
        self.assertEqual(len(server.aufrufe), 1)

    def test_timeout_suche_und_schluessel_von_hand(self):
        g = self.gewerk_neu(ERFASSUNG, nummern=(PR_NUMMER, AN_NUMMER))
        server = self.server()
        server.setze("POST", "/reports/with-data", (0, b"timed out"))
        eintrag = {"projektKey": "zyxwvutsr", "projektTime": 1, "projektEmail": "",
                   "projektName": "Mustermann, Max – PR-260012", "projektStatus": 1}
        server.setze("GET", "/reports", (200, {"projekte": [], "leads": [], "api": [eintrag],
                                               "archiv": []}))
        with mock.patch.object(hr, "_roh_anfrage", server), \
                mock.patch.object(hr, "_schlafen", lambda s: None):
            ok, meldung = hr.projekt_anlegen(self.s, g)
        self.assertTrue(ok, meldung)
        self.assertEqual([a["methode"] for a in server.aufrufe], ["POST", "GET"])
        self.assertEqual(g.heizreport_projekt_key, "zyxwvutsr")
        self.assertIn("nach Timeout gefunden", " ".join(self.verlauf_texte(g)))
        # kein Treffer → Meldung „Anlage unklar …“, Schlüssel bleibt leer
        g2 = self.gewerk_neu(ERFASSUNG)
        server.setze("GET", "/reports", (200, {"projekte": [], "leads": [], "api": [], "archiv": []}))
        with mock.patch.object(hr, "_roh_anfrage", server), \
                mock.patch.object(hr, "_schlafen", lambda s: None):
            ok, meldung = hr.projekt_anlegen(self.s, g2)
        self.assertFalse(ok)
        self.assertEqual(meldung, hr.MELDUNG_ANLAGE_UNKLAR)
        self.assertIsNone(g2.heizreport_projekt_key)
        # Schlüssel von Hand: 404 → abgelehnt, 200 → übernommen
        aufgabe = self.heizlast_aufgabe(g2)
        server.setze("GET", "/reports/qwertzuio", (404, {"status": 404, "error": "nicht gefunden",
                                                         "details": {}}))
        with mock.patch.object(hr, "_roh_anfrage", server), \
                mock.patch.object(hr, "_schlafen", lambda s: None):
            r = self.client.post(f"/projektierung/gewerk/{g2.id}/heizreport/schluessel",
                                 data={"aufgabe_id": str(aufgabe.id), "schluessel": "qwertzuio"},
                                 headers={"Accept": "application/json"})
            self.assertEqual(r.status_code, 200)
            self.assertIn("Schlüssel abgelehnt", r.json()["meldung"])
            r = self.client.post(f"/projektierung/gewerk/{g2.id}/heizreport/schluessel",
                                 data={"aufgabe_id": str(aufgabe.id), "schluessel": "12345"},
                                 headers={"Accept": "application/json"})
            self.assertIn("genau 9 Buchstaben", r.json()["meldung"])
            server.setze("GET", "/reports/qwertzuio",
                         (200, {"status": 200, "action": "getReport",
                                "projektHeader": {"key": "qwertzuio"}, "projektData": {}}))
            r = self.client.post(f"/projektierung/gewerk/{g2.id}/heizreport/schluessel",
                                 data={"aufgabe_id": str(aufgabe.id), "schluessel": "qwertzuio"},
                                 headers={"Accept": "application/json"})
        self.assertEqual(r.status_code, 200)
        self.s.expire_all()
        self.assertEqual(self.s.get(Gewerk, g2.id).heizreport_projekt_key, "qwertzuio")

    def test_ohne_plz_und_verknuepfung_loesen(self):
        g = self.gewerk_neu(ERFASSUNG)
        projekt = self.s.get(Projekt, g.projekt_id)
        projekt.ausfuehrung_plz = ""
        self.s.commit()
        server = self.server()
        with mock.patch.object(hr, "_roh_anfrage", server):
            ok, meldung = hr.projekt_anlegen(self.s, g)
        self.assertFalse(ok)
        self.assertEqual(meldung, hr.MELDUNG_OHNE_PLZ)
        self.assertEqual(server.aufrufe, [])
        projekt.ausfuehrung_plz = "47139"
        g.heizreport_projekt_key = KEY
        g.heizreport_angelegt_am = datetime.now()
        g.heizlast_kw = 9.2
        self.s.commit()
        aufgabe = self.heizlast_aufgabe(g)
        r = self.client.post(f"/projektierung/gewerk/{g.id}/heizreport/loesen",
                             data={"aufgabe_id": str(aufgabe.id), "begruendung": "  "},
                             headers={"Accept": "application/json"})
        self.assertIn("Begründung ist Pflicht", r.json()["meldung"])
        self.s.expire_all()
        self.assertEqual(self.s.get(Gewerk, g.id).heizreport_projekt_key, KEY)
        r = self.client.post(f"/projektierung/gewerk/{g.id}/heizreport/loesen",
                             data={"aufgabe_id": str(aufgabe.id),
                                   "begruendung": "Testprojekt im Portal gelöscht"},
                             headers={"Accept": "application/json"})
        self.assertEqual(r.status_code, 200)
        self.s.expire_all()
        g = self.s.get(Gewerk, g.id)
        self.assertIsNone(g.heizreport_projekt_key)
        self.assertIsNone(g.heizreport_angelegt_am)
        self.assertAlmostEqual(g.heizlast_kw, 9.2)              # Heizlast-Felder bleiben
        self.assertIn("Heizreport-Verknüpfung gelöst: Testprojekt im Portal gelöscht",
                      " ".join(self.verlauf_texte(g)))
        self.assertIn("Heizreport-Projekt anlegen", self.zeile_html(aufgabe))


# --- Teil 3: Heizlast, Abgleich, PDF -------------------------------------------------------

def results_antwort(watt=None, raeume=None):
    results = {"available": True, "status": "ok", "source": "api-v2-core"}
    if watt is not None:
        results["summary"] = {"heatLoad": watt}
    if raeume is not None:
        results["roomHeatLoads"] = raeume
    return {"status": 200, "action": "getResults", "project": {"key": KEY},
            "results": results, "projekt": {"abgleichFBH": []}}


class Teil3Ergebnis(Basis):
    def verknuepft(self, klasse="7 kW (CS3800i)"):
        g = self.gewerk_neu(ERFASSUNG, klasse=klasse)
        g.heizreport_projekt_key = KEY
        g.heizreport_angelegt_am = datetime.now()
        self.s.commit()
        return g

    def test_heizlast_abweichung_hinweis(self):
        # Paketmatrix-Heizlastspalte (= Unterdimensionierungs-Matrix v8):
        # 10,0–12,9 kW → Leistungsklasse 10 kW; verkauft 7 kW → Hinweis wörtlich
        g = self.verknuepft()
        aufgabe = self.heizlast_aufgabe(g)
        server = self.server()
        server.setze("GET", f"/reports/{KEY}/results", (200, results_antwort(11200)))
        with mock.patch.object(hr, "_roh_anfrage", server), \
                mock.patch.object(hr, "_schlafen", lambda s: None):
            r = self.client.post(f"/projektierung/gewerk/{g.id}/heizreport/ergebnis",
                                 data={"aufgabe_id": str(aufgabe.id)},
                                 headers={"Accept": "application/json"})
        self.assertEqual(r.status_code, 200, r.text)
        self.assertNotIn("?", server.aufrufe[0]["url"])          # keine Zusatzparameter
        self.s.expire_all()
        g = self.s.get(Gewerk, g.id)
        self.assertAlmostEqual(g.heizlast_kw, 11.2)
        self.assertEqual(g.heizlast_quelle, "Heizreport API")
        self.assertIsNotNone(g.heizlast_datum)
        self.assertEqual(self.s.get(Aufgabe, aufgabe.id).status, "erledigt")
        verlauf = self.verlauf_texte(g)
        self.assertIn("Heizlast aus Heizreport übernommen: 11,2 kW", verlauf)
        hinweis = ("Heizlast 11,2 kW laut Heizreport → Leistungsklasse 10 kW; verkauft: "
                   "7 kW (CS3800i) – Auslegung prüfen (Nachtrag oder Freigabe)")
        self.assertIn(hinweis, verlauf)
        self.assertEqual(hr.letzter_hinweis(self.s, g), hinweis)
        self.assertIn(hinweis, r.json()["meldung"])
        self.assertIn(hinweis, self.zeile_html(aufgabe))
        akte = self.client.get(f"/projektierung/projekt/{g.projekt_id}").text
        self.assertIn(hinweis, akte)
        # die v2-Knöpfe stehen auch in der vollständigen Akte (nicht nur in der fetch-Zeile)
        for text in ("Heizlast abrufen", "Heizreport-PDF ablegen", "Verknüpfung lösen"):
            self.assertIn(text, akte, text)
        self.assertNotIn("Projekt im Heizreport anlegen", akte)
        # FP-L01/L02 vorbelegt [A-6]
        antworten = kern.fp_antworten(g)
        self.assertEqual(antworten["FP-L01"], "11.2")
        self.assertEqual(antworten["FP-L02"], "Heizreport")
        self.assertEqual(json.loads(g.fp_vorbelegt_json)["FP-L01"], "aus Heizreport")
        from app import projektierung_logik
        seiten = projektierung_logik.hole_logik(self.s).fp_seiten()
        index = next(i for i, (_name, fragen) in enumerate(seiten)
                     if any(f.key == "FP-L01" for f in fragen))
        seite = self.client.get(f"/projektierung/gewerk/{g.id}/feinplanung?seite={index}").text
        self.assertIn("aus Heizreport", seite)
        self.assertIn('value="Heizreport"', seite)
        self.assertIn('value="11.2"', seite)

    def test_heizlast_passt(self):
        # 9 200 W → 9,2 kW → Spalte „8,0 – 9,9 kW“ = Leistungsklasse 7 kW → passt
        g = self.verknuepft()
        server = self.server()
        server.setze("GET", f"/reports/{KEY}/results", (200, results_antwort(9200)))
        with mock.patch.object(hr, "_roh_anfrage", server), \
                mock.patch.object(hr, "_schlafen", lambda s: None):
            ok, meldung, kw = hr.ergebnis_holen(self.s, g)
        self.assertTrue(ok, meldung)
        self.assertEqual(kw, 9.2)
        self.assertEqual(hr.klasse_fuer_heizlast(self.s, 9.2), "7 kW")
        self.assertEqual(hr.klasse_fuer_heizlast(self.s, 6.5), "6 kW")
        verlauf = self.verlauf_texte(g)
        self.assertIn("Heizlast passt zur verkauften Klasse", verlauf)
        self.assertFalse(any("Auslegung prüfen" in t for t in verlauf))
        self.assertEqual(hr.letzter_hinweis(self.s, g), "")
        # kaufmännische Rundung auf eine Nachkommastelle
        self.assertEqual(hr.kw_runden(9250), 9.3)
        self.assertEqual(hr.kw_runden(9249), 9.2)

    def test_raumsumme_als_ersatz(self):
        g = self.verknuepft()
        server = self.server()
        server.setze("GET", f"/reports/{KEY}/results",
                     (200, results_antwort(raeume=[{"roomName": "Wohnen", "heatLoad": 5000},
                                                   {"roomName": "Bad", "heatLoad": 4200}])))
        with mock.patch.object(hr, "_roh_anfrage", server), \
                mock.patch.object(hr, "_schlafen", lambda s: None):
            ok, meldung, kw = hr.ergebnis_holen(self.s, g)
        self.assertTrue(ok, meldung)
        self.assertEqual(kw, 9.2)
        self.assertIn("Summe der Raumheizlasten", meldung)
        # gar keine Heizlast → Meldung mit Ergebnisschlüsseln, Gewerk unverändert
        g2 = self.verknuepft()
        server.setze("GET", f"/reports/{KEY}/results", (200, results_antwort()))
        with mock.patch.object(hr, "_roh_anfrage", server), \
                mock.patch.object(hr, "_schlafen", lambda s: None):
            ok, meldung, kw = hr.ergebnis_holen(self.s, g2)
        self.assertFalse(ok)
        self.assertIn("heizreport_pfad_heizlast", meldung)
        self.assertIsNone(g2.heizlast_kw)

    def test_422_nicht_berechenbar(self):
        g = self.verknuepft()
        aufgabe = self.heizlast_aufgabe(g)
        server = self.server()
        server.setze("GET", f"/reports/{KEY}/results",
                     (422, {"status": 422, "error": "Ergebnisse sind noch nicht verfügbar",
                            "details": {"type": "calculation_unavailable",
                                        "calculationStatus": "unavailable"}}))
        with mock.patch.object(hr, "_roh_anfrage", server), \
                mock.patch.object(hr, "_schlafen", lambda s: None):
            ok, meldung, kw = hr.ergebnis_holen(self.s, g)
        self.assertFalse(ok)
        self.assertEqual(meldung, hr.MELDUNG_NICHT_BERECHENBAR)
        self.assertIsNone(kw)
        self.s.expire_all()
        g = self.s.get(Gewerk, g.id)
        self.assertIsNone(g.heizlast_kw)
        self.assertIsNone(g.heizlast_quelle)
        self.assertEqual(self.s.get(Aufgabe, aufgabe.id).status, "offen")

    def test_pdf_ablage_mit_rueckfrage(self):
        g = self.verknuepft()
        aufgabe = self.heizlast_aufgabe(g)
        projekt = self.s.get(Projekt, g.projekt_id)
        pdf_url = "https://heizreport.net/x.pdf"
        server = self.server()
        server.setze("GET", f"/reports/{KEY}/pdf",
                     (200, {"status": 200, "action": "getPdf", "type": "heizreport",
                            "projektKey": KEY, "linkToDocument": pdf_url,
                            "file": {"url": pdf_url, "name": "x.pdf", "temporary": True}}))
        server.setze("GET", pdf_url, (200, b"%PDF-1.4 Heizreport Test"))
        with mock.patch.object(hr, "_roh_anfrage", server), \
                mock.patch.object(hr, "_schlafen", lambda s: None):
            r = self.client.post(f"/projektierung/gewerk/{g.id}/heizreport/pdf",
                                 data={"aufgabe_id": str(aufgabe.id)},
                                 headers={"Accept": "application/json"})
        self.assertEqual(r.status_code, 200, r.text)
        api_aufruf, download = server.aufrufe
        self.assertEqual(api_aufruf["url"], f"{hr.BASIS_V2}/reports/{KEY}/pdf?type=heizreport")
        self.assertEqual(download["url"], pdf_url)
        self.assertNotIn("Authorization", download["kopf"])          # kein Token an den Link
        self.s.expire_all()
        g = self.s.get(Gewerk, g.id)
        self.assertIsNotNone(g.heizreport_pdf_am)
        self.assertEqual(self.s.get(Aufgabe, aufgabe.id).status, "erledigt")
        name = f"Heizreport-{projekt.nummer}-WP-{datetime.now():%Y%m%d}.pdf"
        dateien = (self.s.query(GalerieDatei)
                   .filter_by(vorgang_id=projekt.vorgang_id, sparte="WP").all())
        self.assertEqual([d.dateiname for d in dateien], [name])
        self.assertEqual(dateien[0].ordner, "Montagedokumente")
        self.assertEqual(dateien[0].quelle, "heizreport")
        self.assertEqual((config.DATA_ORDNER / dateien[0].pfad).read_bytes(),
                         b"%PDF-1.4 Heizreport Test")
        self.assertIn("Heizreport-PDF abgelegt", " ".join(self.verlauf_texte(g)))
        self.assertNotIn(pdf_url, " ".join(self.verlauf_texte(g)))      # Link nicht gespeichert
        # zweiter Abruf ohne Bestätigung → 409 mit Rückfrage, kein API-Aufruf
        with mock.patch.object(hr, "_roh_anfrage", server), \
                mock.patch.object(hr, "_schlafen", lambda s: None):
            r = self.client.post(f"/projektierung/gewerk/{g.id}/heizreport/pdf",
                                 data={"aufgabe_id": str(aufgabe.id)},
                                 headers={"Accept": "application/json"})
            self.assertEqual(r.status_code, 409)
            self.assertEqual(r.json()["meldung"], hr.MELDUNG_PDF_RUECKFRAGE)
            self.assertTrue(r.json()["rueckfrage"])
            self.assertEqual(len(server.aufrufe), 2)
            # mit Bestätigung → zweite Datei …-2.pdf
            r = self.client.post(f"/projektierung/gewerk/{g.id}/heizreport/pdf",
                                 data={"aufgabe_id": str(aufgabe.id), "bestaetigt": "1"},
                                 headers={"Accept": "application/json"})
        self.assertEqual(r.status_code, 200, r.text)
        self.s.expire_all()
        namen = {d.dateiname for d in self.s.query(GalerieDatei)
                 .filter_by(vorgang_id=projekt.vorgang_id, sparte="WP")}
        self.assertEqual(namen, {name, name.replace(".pdf", "-2.pdf")})
        zeile = self.zeile_html(aufgabe)
        self.assertIn("confirm('Bei Heizreport wird ein weiteres Dokument erzeugt", zeile)
        # fremder Host im Link → abgelehnt
        server.setze("GET", f"/reports/{KEY}/pdf",
                     (200, {"status": 200, "action": "getPdf", "type": "heizreport",
                            "projektKey": KEY, "linkToDocument": "https://boese.example/x.pdf",
                            "file": None}))
        with mock.patch.object(hr, "_roh_anfrage", server), \
                mock.patch.object(hr, "_schlafen", lambda s: None):
            ok, meldung, zustand = hr.pdf_ablegen(self.s, g, bestaetigt=True)
        self.assertFalse(ok)
        self.assertIn("PDF-Link", meldung)


if __name__ == "__main__":
    unittest.main()
