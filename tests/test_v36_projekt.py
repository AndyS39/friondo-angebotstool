# v36 (PLAN_V22 Phase 194, Agent B3): Cloover-Projekt (persönlicher Abschluss-Link), PDF-Ablage, Token-Route,
# Status-Lauf cloover-status, Badges, Glocke, Statistik, Parametrierung „PDF-Ablage“.
# Alles ohne Netz: cloover_api.projekt_anlegen/projekt_status/rate_berechnen, Graph (_token, _graph_aufruf,
# _graph_bytes), cloover_pdf_ablage.pruefen, pdf_export.pdf_fuer_angebot und der Graph-Entwurf sind gemockt;
# _roh_anfrage wirft bei jedem echten Aufruf. Läuft gegen die DB-Kopie (DB_PFAD_OVERRIDE + DATA_ORDNER),
# Testdaten tragen das Präfix „V36B3“ und werden am Ende entfernt.
import datetime
import json
import re
import tempfile
import unittest
import urllib.error
import warnings
from contextlib import ExitStack
from pathlib import Path
from unittest import mock
from urllib.parse import unquote_plus

warnings.filterwarnings("ignore")

from fastapi.testclient import TestClient

from app import (angebot_aufbau, auth, cloover, cloover_api, cloover_pdf_ablage, cloover_projekt, config,
                 graph_versand, lead_boards, scheduler)
from app import vorgaenge as vorgaenge_modul
from app.db import SessionLocal, init_db
from app.main import app
from app.models import (Angebot, AngebotsNotiz, AngebotsPosition, Benachrichtigung, Benutzer, ClooverPdfToken,
                        Einstellung, Erfassung, Fehlerprotokoll, Kunde, Vorgang, VorgangsNotiz,
                        angebot_status_setzen, einstellung_holen, einstellung_setzen)
from tests.v34_e_basis import PV_MODULE, WP_ELEKTRO, WP_PAKET

EMAIL = "v36b3-projekt@test.local"
PRAEFIX = "V36B3"
KEY = "V36B3-TESTKEY-NIE-IM-PROTOKOLL-4711"
BASIS = "https://tool-test.friondo.example"
EINSTELLUNGEN = ("cloover_pdf_ablage", "cloover_sharepoint_site", "cloover_sharepoint_ordner",
                 "cloover_ablage_letzter_test", "cloover_modus")


def _aufraeumen(s):
    s.rollback()
    for k in s.query(Kunde).filter(Kunde.email == EMAIL):
        for a in s.query(Angebot).filter_by(kunde_id=k.id):
            s.query(AngebotsNotiz).filter(AngebotsNotiz.angebot_id == a.id).delete(synchronize_session=False)
            s.query(Fehlerprotokoll).filter(Fehlerprotokoll.pfad.like(f"/angebote/{a.id}/%")).delete(
                synchronize_session=False)
            for t in s.query(ClooverPdfToken).filter(ClooverPdfToken.angebot_id == a.id):
                (cloover_pdf_ablage.TOKEN_ORDNER / t.datei).unlink(missing_ok=True)
                s.delete(t)
            (config.ANGEBOTE_PDF_ORDNER / f"{a.nummer}.pdf").unlink(missing_ok=True)
            s.delete(a)
        for e in s.query(Erfassung).filter_by(kunde_id=k.id):
            s.delete(e)
        for v in s.query(Vorgang).filter_by(kunde_id=k.id):
            s.query(VorgangsNotiz).filter(VorgangsNotiz.vorgang_id == v.id).delete(synchronize_session=False)
            s.delete(v)
        s.delete(k)
    s.query(Benachrichtigung).filter(Benachrichtigung.art == "cloover",
                                     Benachrichtigung.text.like("%AN-C-%")).delete(synchronize_session=False)
    for b in s.query(Benutzer).filter(Benutzer.name.like(f"{PRAEFIX}%")):
        s.delete(b)
    for t in s.query(ClooverPdfToken).filter(ClooverPdfToken.name.like(f"{PRAEFIX}%")
                                             | (ClooverPdfToken.name.like("TEST-%")
                                                & ClooverPdfToken.angebot_id.is_(None))):
        (cloover_pdf_ablage.TOKEN_ORDNER / t.datei).unlink(missing_ok=True)
        s.delete(t)
    s.commit()


class Basis(unittest.TestCase):
    """Testkunde (Privatperson mit E-Mail, Telefon, Adresse), AD-Benutzer, Vorgang, Admin-Client."""

    @classmethod
    def setUpClass(cls):
        init_db()
        cls.s = SessionLocal()
        _aufraeumen(cls.s)
        s = cls.s
        cls.einstellungen_vorher = {n: einstellung_holen(s, n, "") for n in EINSTELLUNGEN}
        einstellung_setzen(s, "cloover_pdf_ablage", "basis_url")
        einstellung_setzen(s, "cloover_modus", "test")
        cls.kunde = Kunde(anrede="Herr", vorname="Max", nachname=f"{PRAEFIX} Projekt", strasse="Teststr. 1",
                          plz="47139", ort="Duisburg", email=EMAIL, telefon="0203 3965710")
        cls.ad = Benutzer(name=f"{PRAEFIX} Vertriebler", rolle="aussendienst", aktiv=True,
                          email="v36b3-ad@test.local", pin_hash=auth.pin_hash("4321"))
        s.add_all([cls.kunde, cls.ad])
        s.commit()
        cls.vorgang = vorgaenge_modul.vorgang_fuer_kunde(s, cls.kunde.id)
        s.commit()
        cloover_api.cache_leeren()
        cls.client = TestClient(app, raise_server_exceptions=False)
        cls.client.cookies.set(auth.COOKIE_NAME, auth.cookie_wert(1))

    @classmethod
    def tearDownClass(cls):
        _aufraeumen(cls.s)
        for name, wert in cls.einstellungen_vorher.items():
            einstellung_setzen(cls.s, name, wert)
        cls.s.commit()
        cls.s.close()
        cloover_api.cache_leeren()

    def setUp(self):
        s = self.s
        s.rollback()
        for a in s.query(Angebot).filter_by(kunde_id=self.kunde.id):
            s.query(AngebotsNotiz).filter(AngebotsNotiz.angebot_id == a.id).delete(synchronize_session=False)
            for t in s.query(ClooverPdfToken).filter(ClooverPdfToken.angebot_id == a.id):
                (cloover_pdf_ablage.TOKEN_ORDNER / t.datei).unlink(missing_ok=True)
                s.delete(t)
            (config.ANGEBOTE_PDF_ORDNER / f"{a.nummer}.pdf").unlink(missing_ok=True)
            s.delete(a)
        s.query(VorgangsNotiz).filter_by(vorgang_id=self.vorgang.id).delete(synchronize_session=False)
        s.query(Benachrichtigung).filter(Benachrichtigung.art == "cloover").delete(synchronize_session=False)
        kunde = s.get(Kunde, self.kunde.id)
        kunde.telefon, kunde.email, kunde.firma, kunde.anrede, kunde.grosskunde = "0203 3965710", EMAIL, "", "Herr", False
        einstellung_setzen(s, "cloover_pdf_ablage", "basis_url")
        einstellung_setzen(s, "cloover_modus", "test")
        s.commit()
        s.expire_all()
        cloover_api.cache_leeren()

    # --- Angebote -----------------------------------------------------------------------------
    def angebot(self, sparte="WP", positionen=None, status="Entwurf") -> Angebot:
        a = angebot_aufbau.angebot_anlegen(self.s, self.kunde.id, sparte=sparte)
        a.vorgang_id = self.vorgang.id
        a.vertriebler_id = self.ad.id
        for p in (positionen if positionen is not None else [WP_PAKET] + WP_ELEKTRO):
            a.positionen.append(AngebotsPosition(**dict(p)))
        if status != "Entwurf":
            angebot_status_setzen(a, status)
        self.s.commit()
        return a

    def neu(self, angebot_id: int) -> Angebot:
        self.s.expire_all()
        return self.s.get(Angebot, angebot_id)

    def daten(self, angebot_id: int) -> dict:
        return cloover.json_lesen(self.neu(angebot_id))

    def token_datei(self, angebot_id: int) -> Path:
        zeile = (self.s.query(ClooverPdfToken).filter(ClooverPdfToken.angebot_id == angebot_id)
                 .order_by(ClooverPdfToken.id.desc()).first())
        self.assertIsNotNone(zeile, "kein Token-Eintrag")
        return cloover_pdf_ablage.TOKEN_ORDNER / zeile.datei

    # --- Mocks --------------------------------------------------------------------------------
    def mocks(self, projekt_fehler=None, status_antwort=None, status_fehler=None):
        """Alle Netz-Nahtstellen gemockt; liefert (ExitStack, Protokoll-Dict)."""
        protokoll = {"projekte": [], "status": [], "pdfs": [], "entwuerfe": [], "raten": []}
        zaehler = {"n": 0}

        def fake_projekt(kunde, adresse, assets, laufzeit_von_bis, optionen, pdf_urls, user_email):
            protokoll["projekte"].append(dict(kunde=dict(kunde), adresse=dict(adresse), assets=list(assets),
                                              laufzeit=tuple(laufzeit_von_bis), optionen=list(optionen),
                                              pdf_urls=list(pdf_urls), user_email=user_email))
            if projekt_fehler is not None:
                raise projekt_fehler
            zaehler["n"] += 1
            pid = f"P-{zaehler['n']}"
            return {"projekt_id": pid, "checkout_link": f"https://app.cloover.test/checkout/{pid}",
                    "financial_offer": f"https://app.cloover.test/offer/{pid}", "antwort": {}}

        def fake_status(projekt_id):
            protokoll["status"].append(projekt_id)
            if status_fehler is not None:
                raise status_fehler
            antwort = dict(status_antwort or {"status": "created", "primary_signed_contract": False,
                                               "secondary_signed_contract": False, "contract_signed_date": None,
                                               "financing_option_chosen": None})
            antwort.setdefault("id", projekt_id)
            antwort.setdefault("antwort", {})
            return antwort

        def fake_rate(assets, laufzeit_jahre, anzahlung_cent, user_email, **kw):
            protokoll["raten"].append(dict(assets=list(assets), laufzeit=laufzeit_jahre, anzahlung=anzahlung_cent))
            return {"rate_ohne_cent": 38999, "rate_mit_cent": 24270, "quelle": "v2", "antwort": {},
                    "laufzeit_jahre": laufzeit_jahre, "anzahlung_cent": anzahlung_cent}

        def fake_pdf(session, angebot, benutzer=None, **kw):
            link = cloover.json_lesen(angebot).get("checkout_link") or ""
            pfad = config.ANGEBOTE_PDF_ORDNER / f"{angebot.nummer}.pdf"
            pfad.parent.mkdir(parents=True, exist_ok=True)
            inhalt = f"%PDF-1.4 {angebot.nummer} " + (f"FASSUNG-B LINK+QR {link}" if link else "FASSUNG-A")
            pfad.write_bytes(inhalt.encode("utf-8"))
            protokoll["pdfs"].append((angebot.nummer, bool(link)))
            return pfad

        def fake_entwurf(kunde, angebot_, pdf_pfad, betreff, text, **kw):
            protokoll["entwuerfe"].append(dict(kw, pdf=pdf_pfad, angebot=angebot_.nummer,
                                               pdf_inhalt=Path(pdf_pfad).read_bytes()))
            return True, "Entwurf im Postfach abgelegt – Test.", "https://outlook/x", "konv-v36b3"

        stack = ExitStack()
        stack.enter_context(mock.patch.object(config, "CLOOVER_API_KEY", KEY))
        stack.enter_context(mock.patch.object(config, "BASIS_URL_AUS_ENV", True))
        stack.enter_context(mock.patch.object(config, "BASIS_URL", BASIS))
        stack.enter_context(mock.patch.object(cloover_api, "_roh_anfrage",
                                              side_effect=AssertionError("echter Cloover-Aufruf im Test")))
        stack.enter_context(mock.patch.object(cloover_api, "projekt_anlegen", side_effect=fake_projekt))
        stack.enter_context(mock.patch.object(cloover_api, "projekt_status", side_effect=fake_status))
        stack.enter_context(mock.patch.object(cloover_api, "rate_berechnen", side_effect=fake_rate))
        stack.enter_context(mock.patch.object(cloover, "rate_aktualisieren", return_value={}))
        stack.enter_context(mock.patch.object(cloover_pdf_ablage, "pruefen",
                                              return_value=(True, "HEAD ohne Anmeldung: application/pdf (Test)")))
        stack.enter_context(mock.patch("app.pdf_export.pdf_fuer_angebot", side_effect=fake_pdf))
        stack.enter_context(mock.patch.object(graph_versand, "konfiguriert", return_value=True))
        stack.enter_context(mock.patch.object(graph_versand, "angemeldeter_benutzer", return_value="ida@friondo.de"))
        stack.enter_context(mock.patch.object(graph_versand, "entwurf_erstellen", side_effect=fake_entwurf))
        stack.enter_context(mock.patch("app.anhaenge.fuer_angebot", return_value=[]))
        cloover_api.cache_leeren()
        return stack, protokoll

    def versand(self, angebot_id: int, **mock_kw):
        stack, protokoll = self.mocks(**mock_kw)
        with stack:
            antwort = self.client.post(f"/angebote/{angebot_id}/email", follow_redirects=False)
        self.s.expire_all()
        return unquote_plus(antwort.headers.get("location", "")), protokoll, antwort


class Voraussetzungen(Basis):
    def test_telefon_fehlt_kein_projekt_rate_bleibt(self):
        a = self.angebot()
        cloover.json_schreiben(a, rate_ohne_cent=38999, stand="16.10.2026 10:00", quelle="v2")
        kunde = self.s.get(Kunde, self.kunde.id)
        kunde.telefon = ""
        self.s.commit()
        ziel, protokoll, antwort = self.versand(a.id)
        self.assertEqual(antwort.status_code, 303)
        self.assertIn("Cloover-Link nicht möglich: Telefon fehlt", ziel)
        self.assertEqual(protokoll["projekte"], [])
        daten = self.daten(a.id)
        self.assertNotIn("projekt_id", daten)
        self.assertEqual(daten["rate_ohne_cent"], 38999)           # Rate bleibt
        self.assertIn("Telefon fehlt", daten["projekt_fehler"])
        self.assertEqual(self.neu(a.id).status, "Versand vorbereitet")   # der Versand selbst läuft weiter
        # Versand-PDF ohne Link (nur eine Fassung, keine Ablage)
        self.assertEqual(protokoll["pdfs"], [(a.nummer, False)])

    def test_firmenkunde_und_email(self):
        a = self.angebot()
        kunde = self.s.get(Kunde, self.kunde.id)
        kunde.firma, kunde.email = "Muster GmbH", ""
        self.s.commit()
        ziel, protokoll, _ = self.versand(a.id)
        self.assertIn("Cloover-Link nicht möglich:", ziel)
        self.assertIn("Firmenkunde – Cloover nur für Privatkunden", ziel)
        self.assertIn("E-Mail des Kunden fehlt", ziel)
        self.assertEqual(protokoll["projekte"], [])

    def test_ablage_keine_und_modus_aus(self):
        a = self.angebot()
        einstellung_setzen(self.s, "cloover_pdf_ablage", "keine")
        self.s.commit()
        ziel, protokoll, _ = self.versand(a.id)
        self.assertIn("Cloover-Link nicht möglich: PDF-Ablage nicht eingerichtet", ziel)
        self.assertEqual(protokoll["projekte"], [])
        # Modus aus: kein Projekt und keine Cloover-Meldung (nicht relevant)
        einstellung_setzen(self.s, "cloover_pdf_ablage", "basis_url")
        einstellung_setzen(self.s, "cloover_modus", "aus")
        self.s.commit()
        cloover_api.cache_leeren()
        b = self.angebot()
        ziel, protokoll, _ = self.versand(b.id)
        self.assertNotIn("Cloover", ziel)
        self.assertEqual(protokoll["projekte"], [])

    def test_voraussetzungen_liste(self):
        a = self.angebot()
        with self.mocks()[0]:
            self.assertEqual(cloover_projekt.voraussetzungen(self.s, a), [])
            kunde = self.s.get(Kunde, self.kunde.id)
            kunde.telefon, kunde.strasse, kunde.grosskunde = "123", "", True
            self.s.flush()
            gruende = cloover_projekt.voraussetzungen(self.s, a, kunde)
            self.s.rollback()
        self.assertIn("Großkunde – Cloover nur für Privatkunden", gruende)
        self.assertIn("Ausführungsort unvollständig (Straße, PLZ, Ort)", gruende)
        self.assertTrue(any("Telefon unvollständig" in g for g in gruende), gruende)
        # E.164 wie das Lead-Modul
        self.assertEqual(cloover_projekt.telefon_e164("0203 3965710"), "+492033965710")
        self.assertEqual(cloover_projekt.telefon_e164("+49 171 1234567"), "+491711234567")
        self.assertEqual(cloover_projekt.telefon_e164("123"), "")


class ProjektBeimVersand(Basis):
    def test_body_woertlich_fassung_a_und_b(self):
        a = self.angebot()
        ziel, protokoll, antwort = self.versand(a.id)
        self.assertEqual(antwort.status_code, 303, antwort.text)
        self.assertIn("Cloover-Projekt P-1 angelegt", ziel)
        self.assertEqual(len(protokoll["projekte"]), 1)
        aufruf = protokoll["projekte"][0]
        self.assertEqual(aufruf["kunde"], {"vorname": "Max", "nachname": f"{PRAEFIX} Projekt", "email": EMAIL,
                                           "telefon": "+492033965710"})
        self.assertEqual(aufruf["adresse"], {"strasse": "Teststr. 1", "plz": "47139", "ort": "Duisburg"})
        self.assertEqual(len(aufruf["assets"]), 1)
        asset = aufruf["assets"][0]
        self.assertEqual(asset["type"], "Heat pump")
        self.assertEqual(asset["priceInfo"], {"price": 12400, "vatPercentage": 19, "subsidy": 0, "currency": "EUR"})
        self.assertEqual(aufruf["laufzeit"], (1, 20))
        self.assertEqual(aufruf["optionen"], ["Cash", "Financing"])
        self.assertEqual(aufruf["user_email"], "c.castro@friondo.de")
        self.assertEqual(len(aufruf["pdf_urls"]), 1)
        url = aufruf["pdf_urls"][0]
        m = re.fullmatch(re.escape(BASIS) + r"/oeffentlich/cloover/([A-Za-z0-9_-]{32})\.pdf", url)
        self.assertIsNotNone(m, url)
        self.assertNotIn("Projekt", url)                     # kein Kundenname in der URL
        # cloover_json
        daten = self.daten(a.id)
        self.assertEqual(daten["projekt_id"], "P-1")
        self.assertEqual(daten["checkout_link"], "https://app.cloover.test/checkout/P-1")
        self.assertEqual(daten["financial_offer"], "https://app.cloover.test/offer/P-1")
        self.assertEqual(daten["pdf_url"], url)
        self.assertEqual(daten["pdf_ablage"]["anbieter"], "basis_url")
        self.assertEqual(daten["projekt_von"], 1)
        self.assertNotIn("projekt_fehler", daten)
        # Fassung A (ohne Link) vor dem Projekt, Fassung B (mit Link + QR) danach = Versand-PDF
        self.assertEqual(protokoll["pdfs"], [(a.nummer, False), (a.nummer, True)])
        self.assertIn(b"FASSUNG-B LINK+QR https://app.cloover.test/checkout/P-1", protokoll["entwuerfe"][0]["pdf_inhalt"])
        # abgelegte Datei = Fassung B (ersetzt)
        self.assertIn(b"FASSUNG-B", self.token_datei(a.id).read_bytes())
        # Verlauf, Vorgangs-Chat, Status
        notizen = [n.text for n in self.s.query(AngebotsNotiz).filter_by(angebot_id=a.id)]
        self.assertTrue(any("Cloover-Projekt P-1 angelegt" in t for t in notizen), notizen)
        chat = [n.text for n in self.s.query(VorgangsNotiz).filter_by(vorgang_id=self.vorgang.id)]
        self.assertTrue(any("Cloover-Projekt P-1 angelegt" in t and a.nummer in t for t in chat), chat)
        self.assertEqual(self.neu(a.id).status, "Versand vorbereitet")

    def test_kein_doppelprojekt_beim_zweiten_versand(self):
        a = self.angebot()
        self.versand(a.id)
        ziel, protokoll, _ = self.versand(a.id)
        self.assertEqual(protokoll["projekte"], [])               # kein zweites POST /api/projects
        self.assertNotIn("angelegt", ziel)
        self.assertEqual(self.daten(a.id)["projekt_id"], "P-1")
        self.assertEqual(protokoll["pdfs"], [(a.nummer, True)])    # nur Fassung B neu
        self.assertIn(b"FASSUNG-B", self.token_datei(a.id).read_bytes())
        self.assertEqual(self.s.query(ClooverPdfToken).filter_by(angebot_id=a.id).count(), 1)

    def test_ueberarbeiten_legt_neues_projekt_an(self):
        a = self.angebot()
        self.versand(a.id)
        a = self.neu(a.id)
        angebot_status_setzen(a, "Versendet")
        self.s.commit()
        antwort = self.client.post(f"/angebote/{a.id}/ueberarbeiten", follow_redirects=False)
        self.assertEqual(antwort.status_code, 303)
        version_id = int(re.search(r"/angebote/(\d+)", antwort.headers["location"]).group(1))
        self.assertNotEqual(version_id, a.id)
        self.assertNotIn("projekt_id", self.daten(version_id))     # neue Version ohne Projektfelder
        ziel, protokoll, _ = self.versand(version_id)
        self.assertIn("Cloover-Projekt P-1 angelegt", ziel)         # neuer Zähler je Mock → neues Projekt
        self.assertEqual(len(protokoll["projekte"]), 1)
        self.assertEqual(self.daten(a.id)["projekt_id"], "P-1")
        self.assertEqual(self.daten(version_id)["projekt_id"], "P-1")
        self.assertEqual(self.neu(a.id).status, "Überholt")

    def test_projekt_anlegen_knopf_nachholen(self):
        a = self.angebot()
        kunde = self.s.get(Kunde, self.kunde.id)
        kunde.telefon = ""
        self.s.commit()
        ziel, protokoll, _ = self.versand(a.id)
        self.assertIn("Telefon fehlt", ziel)
        kunde = self.s.get(Kunde, self.kunde.id)
        kunde.telefon = "0203 3965710"
        self.s.commit()
        stack, protokoll = self.mocks()
        with stack:
            antwort = self.client.post(f"/angebote/{a.id}/cloover/projekt", follow_redirects=False)
        self.assertEqual(antwort.status_code, 303)
        self.assertIn("Cloover-Projekt P-1 angelegt", unquote_plus(antwort.headers["location"]))
        self.assertEqual(len(protokoll["projekte"]), 1)
        self.assertEqual(protokoll["pdfs"], [(a.nummer, False), (a.nummer, True)])   # A + B über den Knopf
        self.assertIn(b"FASSUNG-B", self.token_datei(a.id).read_bytes())
        self.assertEqual(self.daten(a.id)["projekt_id"], "P-1")
        # JSON-Antwort bei Accept application/json, zweiter Klick legt kein Projekt mehr an
        stack, protokoll = self.mocks()
        with stack:
            antwort = self.client.post(f"/angebote/{a.id}/cloover/projekt", headers={"accept": "application/json"})
        self.assertEqual(antwort.status_code, 200)
        self.assertTrue(antwort.json()["ok"])
        self.assertIn("vorhanden", antwort.json()["meldung"])
        self.assertEqual(protokoll["projekte"], [])

    def test_cloover_fehler_versand_laeuft_weiter(self):
        a = self.angebot()
        fehler = cloover_api.ClooverFehler("Cloover: Eingabe abgelehnt (phone)", 422)
        ziel, protokoll, _ = self.versand(a.id, projekt_fehler=fehler)
        self.assertIn("Cloover-Link nicht möglich: Cloover: Eingabe abgelehnt (phone)", ziel)
        self.assertEqual(len(protokoll["projekte"]), 1)
        daten = self.daten(a.id)
        self.assertNotIn("projekt_id", daten)
        self.assertIn("Eingabe abgelehnt", daten["projekt_fehler"])
        self.assertEqual(self.neu(a.id).status, "Versand vorbereitet")
        self.assertEqual(len(protokoll["entwuerfe"]), 1)        # Graph-Entwurf trotzdem
        # Editor zeigt den Fehler und den Knopf „Projekt anlegen“
        with self.mocks()[0]:
            seite = self.client.get(f"/angebote/{a.id}")
        self.assertEqual(seite.status_code, 200)
        self.assertIn("Eingabe abgelehnt (phone)", seite.text)
        self.assertIn(f"/angebote/{a.id}/cloover/projekt", seite.text)

    def test_aussendienst_darf_nicht(self):
        a = self.angebot()
        client = TestClient(app, raise_server_exceptions=False)
        client.cookies.set(auth.COOKIE_NAME, auth.cookie_wert(self.ad.id))
        antwort = client.post(f"/angebote/{a.id}/cloover/projekt", headers={"accept": "application/json"},
                              follow_redirects=False)
        self.assertIn(antwort.status_code, (303, 403))
        self.assertNotIn("projekt_id", self.daten(a.id))


class Kombi(Basis):
    def test_ein_projekt_mit_zwei_assets(self):
        wp = self.angebot("WP")
        pv = self.angebot("PV", [PV_MODULE])
        stack, protokoll = self.mocks()
        with stack:
            antwort = self.client.post(f"/vorgaenge/{self.vorgang.id}/kombi-versand",
                                       data={"angebot_ids": [str(wp.id), str(pv.id)]}, follow_redirects=False)
        self.assertEqual(antwort.status_code, 303)
        ziel = unquote_plus(antwort.headers["location"])
        self.assertIn("Kombi-Entwurf für", ziel)
        self.assertIn("Cloover-Projekt P-1 für 2 Angebote angelegt", ziel)
        self.assertIn("Gesamtrate ab 389,99 €/Monat", ziel)
        self.assertEqual(len(protokoll["projekte"]), 1)
        aufruf = protokoll["projekte"][0]
        self.assertEqual([x["type"] for x in aufruf["assets"]], ["Heat pump", "Solar"])
        self.assertEqual(aufruf["assets"][1]["priceInfo"]["vatPercentage"], 0)
        self.assertEqual(len(aufruf["pdf_urls"]), 2)
        self.assertEqual(len(set(aufruf["pdf_urls"])), 2)
        # Gesamtrate über alle Assets (eine v2-Anfrage)
        self.assertEqual(len(protokoll["raten"]), 1)
        self.assertEqual(len(protokoll["raten"][0]["assets"]), 2)
        d_wp, d_pv = self.daten(wp.id), self.daten(pv.id)
        self.assertEqual((d_wp["projekt_id"], d_pv["projekt_id"]), ("P-1", "P-1"))
        self.assertEqual(d_wp["checkout_link"], d_pv["checkout_link"])      # derselbe Link in beiden PDFs
        self.assertNotEqual(d_wp["pdf_url"], d_pv["pdf_url"])
        self.assertEqual(d_wp["kombi_gesamtrate_cent"], 38999)
        self.assertEqual(sorted(d_wp["kombi_angebote"]), sorted([wp.nummer, pv.nummer]))
        # beide Versand-PDFs sind Fassung B mit demselben Link
        for e in protokoll["entwuerfe"]:
            self.assertIn(b"FASSUNG-B LINK+QR https://app.cloover.test/checkout/P-1", e["pdf_inhalt"])
            for p in e["weitere_anhaenge"]:
                self.assertIn(b"FASSUNG-B LINK+QR https://app.cloover.test/checkout/P-1", Path(p).read_bytes())
        self.assertIn(b"FASSUNG-B", self.token_datei(wp.id).read_bytes())
        self.assertIn(b"FASSUNG-B", self.token_datei(pv.id).read_bytes())
        # zweiter Kombi-Versand: kein neues Projekt
        stack, protokoll = self.mocks()
        with stack:
            self.client.post(f"/vorgaenge/{self.vorgang.id}/kombi-versand",
                             data={"angebot_ids": [str(wp.id), str(pv.id)]}, follow_redirects=False)
        self.assertEqual(protokoll["projekte"], [])
        self.assertEqual(self.daten(wp.id)["projekt_id"], "P-1")


def _mit_projekt(test: Basis, status="Versendet", **json_werte) -> Angebot:
    a = test.angebot(status=status)
    werte = dict(projekt_id="P-9", checkout_link="https://app.cloover.test/checkout/P-9",
                 projekt_am=datetime.datetime.now().strftime("%d.%m.%Y %H:%M"), projekt_von=1,
                 pdf_url=f"{BASIS}/oeffentlich/cloover/x.pdf")
    werte.update(json_werte)
    cloover.json_schreiben(a, **werte)
    test.s.commit()
    return a


VERTRAG = {"status": "signed", "primary_signed_contract": True, "secondary_signed_contract": False,
           "contract_signed_date": "2026-10-16T10:00:00Z", "financing_option_chosen": "Financing"}


class StatusLauf(Basis):
    def test_vertrag_badge_glocke_notiz_kein_statuswechsel(self):
        a = _mit_projekt(self)
        stack, protokoll = self.mocks(status_antwort=VERTRAG)
        with stack:
            text = cloover_projekt.status_lauf()
        self.assertEqual(text, "1 geprüft, 1 geändert, 1 Verträge, 0 Fehler")
        self.assertEqual(protokoll["status"], ["P-9"])
        daten = self.daten(a.id)
        self.assertTrue(daten["primary_signed_contract"])
        self.assertEqual(daten["vertrag_am"], "16.10.2026")
        self.assertEqual(daten["status"], "signed")
        self.assertEqual(daten["financing_option_chosen"], "Financing")
        self.assertEqual(cloover_projekt.badge_fuer(daten)["text"], "Cloover: Vertrag unterschrieben (16.10.2026)")
        self.assertEqual(self.neu(a.id).status, "Versendet")        # kein Statuswechsel am Angebot
        notizen = [n.text for n in self.s.query(AngebotsNotiz).filter_by(angebot_id=a.id)]
        self.assertTrue(any("Vertrag unterschrieben (16.10.2026)" in t and "signed" in t for t in notizen), notizen)
        chat = [n.text for n in self.s.query(VorgangsNotiz).filter_by(vorgang_id=self.vorgang.id)]
        self.assertTrue(any("Angebot auf Angenommen setzen?" in t for t in chat), chat)
        glocken = self.s.query(Benachrichtigung).filter(Benachrichtigung.art == "cloover").all()
        self.assertEqual(sorted(g.benutzer_id for g in glocken), sorted([1, self.ad.id]))
        self.assertTrue(all("Vertrag unterschrieben (16.10.2026)" in g.text for g in glocken))
        self.assertTrue(all(g.gelesen_am is None for g in glocken))
        # zweiter Lauf: unverändert, keine neue Glocke/Notiz
        stack, protokoll = self.mocks(status_antwort=VERTRAG)
        with stack:
            text = cloover_projekt.status_lauf()
        self.assertEqual(text, "1 geprüft, 0 geändert, 0 Verträge, 0 Fehler")
        self.assertEqual(self.s.query(Benachrichtigung).filter(Benachrichtigung.art == "cloover").count(), 2)
        self.assertEqual(len([t for t in [n.text for n in self.s.query(AngebotsNotiz).filter_by(angebot_id=a.id)]
                              if "Vertrag unterschrieben" in t]), 1)

    def test_barzahlung(self):
        a = _mit_projekt(self)
        antwort = dict(VERTRAG, primary_signed_contract=False, status="cash", financing_option_chosen="Cash")
        with self.mocks(status_antwort=antwort)[0]:
            cloover_projekt.status_lauf()
        daten = self.daten(a.id)
        self.assertEqual(cloover_projekt.badge_fuer(daten)["text"], "Cloover: Barzahlung gewählt")
        self.assertEqual(cloover_projekt.status_text(daten), "Barzahlung gewählt · cash")
        self.assertEqual(self.s.query(Benachrichtigung).filter(Benachrichtigung.art == "cloover").count(), 0)

    def test_status_knopf(self):
        a = _mit_projekt(self)
        with self.mocks(status_antwort=VERTRAG)[0]:
            antwort = self.client.post(f"/angebote/{a.id}/cloover/status", follow_redirects=False)
            self.assertEqual(antwort.status_code, 303)
            self.assertIn("Vertrag unterschrieben (16.10.2026)", unquote_plus(antwort.headers["location"]))
            antwort = self.client.post(f"/angebote/{a.id}/cloover/status", headers={"accept": "application/json"})
        self.assertEqual(antwort.status_code, 200)
        self.assertEqual(antwort.json()["status"], "signed")
        self.assertFalse(antwort.json()["geaendert"])

    def test_fehler_und_kandidaten(self):
        a = _mit_projekt(self)
        with self.mocks(status_fehler=cloover_api.ClooverFehler("Cloover nicht erreichbar – später erneut versuchen"))[0]:
            text = cloover_projekt.status_lauf()
        self.assertEqual(text, "1 geprüft, 0 geändert, 0 Verträge, 1 Fehler")
        self.assertIn("nicht erreichbar", self.daten(a.id)["status_fehler"])
        # Kandidaten: nur prüfbare Status, Projekt jünger als 180 Tage
        alt = _mit_projekt(self, projekt_am=(datetime.datetime.now() - datetime.timedelta(days=200)).strftime("%d.%m.%Y %H:%M"))
        abgelehnt = _mit_projekt(self, status="Abgelehnt")
        entwurf = _mit_projekt(self, status="Entwurf")
        ohne = self.angebot(status="Versendet")
        ids = cloover_projekt.kandidaten(self.s)
        self.assertIn(a.id, ids)
        for x in (alt, abgelehnt, entwurf, ohne):
            self.assertNotIn(x.id, ids)

    def test_lauf_ohne_key_inaktiv(self):
        with mock.patch.object(config, "CLOOVER_API_KEY", ""):
            self.assertEqual(cloover_projekt.status_lauf(), "inaktiv (kein Cloover-Key)")
            self.assertIn("kein Cloover-Key", cloover_projekt._lauf_aktiv())
        with mock.patch.object(config, "CLOOVER_API_KEY", KEY):
            self.assertIs(cloover_projekt._lauf_aktiv(), True)


class Anzeige(Basis):
    def test_badges_akte_editor_liste_statistik(self):
        # Kettenende 17.10.2026: Vertragsdatum = heute statt des festen Schreibdatums 16.10.2026 – die
        # Statistik unten zählt im Fenster jetzt ± 1 Tag, ein festes Datum fiel nach Mitternacht heraus
        heute = datetime.date.today().strftime("%d.%m.%Y")
        a = _mit_projekt(self, primary_signed_contract=True, vertrag_am=heute, status="signed")
        with self.mocks()[0]:
            akte = self.client.get(f"/vorgaenge/{self.vorgang.id}")
            editor = self.client.get(f"/angebote/{a.id}")
            liste = self.client.get("/angebote")
            statistik = self.client.get("/statistik?zeitraum=monat")
        self.assertEqual(akte.status_code, 200)
        self.assertIn(f"Cloover: Vertrag unterschrieben ({heute})", akte.text)
        self.assertEqual(editor.status_code, 200)
        self.assertIn(f"Cloover: Vertrag unterschrieben ({heute})", editor.text)
        self.assertIn("Angebot auf Angenommen setzen?", editor.text)
        self.assertIn("Status jetzt abrufen", editor.text)
        self.assertIn("Link kopieren", editor.text)
        self.assertEqual(liste.status_code, 200)
        self.assertIn("cloover", liste.text)                     # Spalte im Spaltenwähler (Standard aus)
        self.assertEqual(lead_boards.angebot_sortwert(self.neu(a.id), "cloover"), 0)
        self.assertIn(("cloover", "Cloover", False), lead_boards.KATALOGE["angebote"])
        self.assertEqual(statistik.status_code, 200)
        self.assertIn("Cloover-Verträge", statistik.text)
        jetzt = datetime.datetime.now()
        werte = cloover_projekt.statistik(self.s, jetzt - datetime.timedelta(days=1), jetzt + datetime.timedelta(days=1))
        self.assertEqual(werte["anzahl"], 1)
        self.assertEqual(werte["summe_cent"], self.neu(a.id).summen()["endbetrag"])
        self.assertEqual(cloover_projekt.statistik(self.s, jetzt + datetime.timedelta(days=2),
                                                   jetzt + datetime.timedelta(days=3))["anzahl"], 0)

    def test_editor_block_ohne_projekt(self):
        a = self.angebot()
        with self.mocks()[0]:
            seite = self.client.get(f"/angebote/{a.id}")
            ctx = cloover_projekt.editor_kontext(self.s, self.neu(a.id), None, self.s.get(Benutzer, 1))
        self.assertEqual(seite.status_code, 200)
        self.assertIn("Cloover-Projekt", seite.text)
        self.assertIn(f"/angebote/{a.id}/cloover/projekt", seite.text)
        self.assertTrue(ctx["kann_anlegen"] and ctx["aktiv"] and not ctx["projekt_id"])
        kunde = self.s.get(Kunde, self.kunde.id)
        kunde.telefon = ""
        self.s.commit()
        with self.mocks()[0]:
            ctx = cloover_projekt.editor_kontext(self.s, self.neu(a.id), None, self.s.get(Benutzer, 1))
            seite = self.client.get(f"/angebote/{a.id}")
        self.assertIn("Telefon fehlt", ctx["gruende"])
        self.assertFalse(ctx["kann_anlegen"])
        self.assertIn("Telefon fehlt", seite.text)
        self.assertNotIn(f'action="/angebote/{a.id}/cloover/projekt"', seite.text)


class TokenRoute(Basis):
    def _token(self) -> tuple[str, str]:
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
            f.write(b"%PDF-1.4 token-test")
            tmp = Path(f.name)
        try:
            with mock.patch.object(config, "BASIS_URL_AUS_ENV", True), mock.patch.object(config, "BASIS_URL", BASIS):
                konf = cloover_pdf_ablage.konfig(self.s)
                self.assertTrue(konf["bereit"], konf)
                ablage = cloover_pdf_ablage.ablegen(tmp, f"{PRAEFIX}-AN-C-TEST.pdf", konf)
        finally:
            tmp.unlink(missing_ok=True)
        return ablage["token"], ablage["url"]

    def test_ohne_login_nur_mit_gueltigem_token(self):
        token, url = self._token()
        self.assertEqual(len(token), 32)
        self.assertEqual(url, f"{BASIS}/oeffentlich/cloover/{token}.pdf")
        anonym = TestClient(app, raise_server_exceptions=False)   # kein Cookie
        antwort = anonym.get(f"/oeffentlich/cloover/{token}.pdf")
        self.assertEqual(antwort.status_code, 200)
        self.assertEqual(antwort.headers["content-type"].split(";")[0], "application/pdf")
        self.assertTrue(antwort.content.startswith(b"%PDF"))
        self.assertIn("no-store", antwort.headers.get("cache-control", ""))
        kopf = anonym.head(f"/oeffentlich/cloover/{token}.pdf")
        self.assertEqual(kopf.status_code, 200)
        self.assertEqual(kopf.headers["content-type"].split(";")[0], "application/pdf")
        self.assertEqual(anonym.get("/oeffentlich/cloover/gibtesnicht0000000000000000000.pdf").status_code, 404)
        self.assertEqual(anonym.get("/oeffentlich/cloover/").status_code, 404)
        self.assertEqual(anonym.get("/oeffentlich/cloover").status_code, 404)
        # abgelaufen → 404; Ersetzen über die URL schreibt die Datei neu
        self.s.commit()                      # neue Lesetransaktion – die Token-Zeile kam über db.kurz()
        zeile = self.s.query(ClooverPdfToken).filter_by(token=token).one()
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
            f.write(b"%PDF-1.4 ersetzt")
            tmp = Path(f.name)
        try:
            cloover_pdf_ablage.ersetzen(url, tmp)
        finally:
            tmp.unlink(missing_ok=True)
        self.assertEqual(anonym.get(f"/oeffentlich/cloover/{token}.pdf").content, b"%PDF-1.4 ersetzt")
        zeile.gueltig_bis = datetime.datetime.now() - datetime.timedelta(days=1)
        self.s.commit()
        self.assertEqual(anonym.get(f"/oeffentlich/cloover/{token}.pdf").status_code, 404)
        # Aufräumen abgelaufener Token-Dateien (Karenz 30 Tage)
        zeile.gueltig_bis = datetime.datetime.now() - datetime.timedelta(days=40)
        self.s.commit()
        self.assertGreaterEqual(cloover_pdf_ablage.abgelaufene_tokens_raeumen(), 1)
        self.assertFalse((cloover_pdf_ablage.TOKEN_ORDNER / zeile.datei).exists())

    def test_dateiname_ohne_kundennamen(self):
        name = cloover_pdf_ablage.dateiname("AN-C-261021")
        self.assertRegex(name, r"^AN-C-261021-[A-Za-z0-9-]{8}\.pdf$")
        self.assertRegex(cloover_pdf_ablage.dateiname("AN-C-261021.2"), r"^AN-C-261021-2-[A-Za-z0-9-]{8}\.pdf$")
        self.assertNotEqual(name, cloover_pdf_ablage.dateiname("AN-C-261021"))


class SharePointAblage(unittest.TestCase):
    """Anbieter sharepoint mit gemocktem Graph: Upload, Ordner anlegen bei 404, anonymer Link, Ersetzen."""

    def _graph(self, aufrufe, erster_put_404=False):
        zustand = {"puts": 0}

        def graph_bytes(methode, pfad, token, daten=None, content_type="application/pdf", timeout=60,
                        absolut=False, zusatz_kopf=None):
            aufrufe.append((methode, pfad, content_type, len(daten or b"")))
            self.assertEqual(token, "tok")
            if methode == "PUT":
                zustand["puts"] += 1
                if erster_put_404 and zustand["puts"] == 1:
                    return 404, {"error": {"code": "itemNotFound", "message": "nicht da"}}
                return 201, {"id": "ITEM1", "name": pfad.split("/")[-1].split(":")[0],
                             "webUrl": "https://friondo.sharepoint.com/sites/x/Cloover-Angebote/datei.pdf",
                             "parentReference": {"driveId": "DRIVE1"}}
            if methode == "POST" and pfad.endswith("/children"):
                return 201, {"id": "ORDNER1"}
            return 500, {}

        def graph_aufruf(methode, pfad, token, daten=None, timeout=60):
            aufrufe.append((methode, pfad, "json", daten))
            if pfad.startswith("/sites/friondo.sharepoint.com:/sites/cloover"):
                return {"id": "friondo.sharepoint.com,guid-a,guid-b"}
            if pfad.endswith("/createLink"):
                self.assertEqual(daten["type"], "view")
                self.assertEqual(daten["scope"], "anonymous")
                self.assertIn("expirationDateTime", daten)
                return {"link": {"webUrl": "https://friondo.sharepoint.com/:b:/s/cloover/ABC123"}}
            if pfad.startswith("/shares/u!"):
                return {"id": "ITEM1", "parentReference": {"driveId": "DRIVE1"}}
            raise AssertionError(pfad)

        return ExitStack(), graph_bytes, graph_aufruf

    def _konfig(self):
        return {"anbieter": "sharepoint", "site": "friondo.sharepoint.com:/sites/cloover", "ordner": "Cloover-Angebote",
                "graph_modus": "anwendung", "basis_url": BASIS, "basis_url_aus_env": False, "link_tage": 180,
                "bereit": True, "grund": ""}

    def test_upload_link_und_ersetzen(self):
        aufrufe = []
        _stack, graph_bytes, graph_aufruf = self._graph(aufrufe, erster_put_404=True)
        cloover_pdf_ablage._site_cache.clear()
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
            f.write(b"%PDF-1.4 sharepoint-test")
            tmp = Path(f.name)
        try:
            with mock.patch.object(graph_versand, "modus", return_value="anwendung"), \
                    mock.patch.object(graph_versand, "_token", return_value="tok"), \
                    mock.patch.object(cloover_pdf_ablage, "_graph_bytes", side_effect=graph_bytes), \
                    mock.patch.object(graph_versand, "_graph_aufruf", side_effect=graph_aufruf):
                name = cloover_pdf_ablage.dateiname("AN-C-261021")
                ablage = cloover_pdf_ablage.ablegen(tmp, name, self._konfig())
                neu = cloover_pdf_ablage.ersetzen(ablage, tmp)
                per_url = cloover_pdf_ablage.ersetzen(ablage["url"], tmp)
        finally:
            tmp.unlink(missing_ok=True)
        self.assertEqual(ablage["url"], "https://friondo.sharepoint.com/:b:/s/cloover/ABC123?download=1")
        self.assertEqual(ablage["item_id"], "ITEM1")
        self.assertEqual(ablage["drive_id"], "DRIVE1")
        self.assertEqual(ablage["anbieter"], "sharepoint")
        self.assertTrue(ablage["ablauf"])
        puts = [a for a in aufrufe if a[0] == "PUT"]
        # 1. PUT 404 → Ordner anlegen → 2. PUT ok → Ersetzen (Dict) → Ersetzen (URL über /shares)
        self.assertEqual(len(puts), 4)
        self.assertIn("/sites/friondo.sharepoint.com,guid-a,guid-b/drive/root:/Cloover-Angebote/" + name + ":/content",
                      puts[0][1])
        self.assertNotIn("Max", puts[0][1])
        self.assertTrue(any(a[0] == "POST" and a[1].endswith("/drive/root/children") for a in aufrufe))
        self.assertEqual(puts[2][1], "/drives/DRIVE1/items/ITEM1/content")
        self.assertEqual(puts[3][1], "/drives/DRIVE1/items/ITEM1/content")
        self.assertTrue(any(a[1].startswith("/shares/u!") for a in aufrufe))
        self.assertTrue(neu["ersetzt_am"] and per_url["ersetzt_am"])

    def test_delegiert_und_keine(self):
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
            f.write(b"%PDF-1.4")
            tmp = Path(f.name)
        try:
            konf = dict(self._konfig(), graph_modus="delegiert")
            konf["bereit"], konf["grund"] = cloover_pdf_ablage._bereitschaft(konf)
            self.assertFalse(konf["bereit"])
            with self.assertRaises(cloover_pdf_ablage.AblageFehler) as cm:
                cloover_pdf_ablage.ablegen(tmp, "x.pdf", konf)
            self.assertIn("Graph als Anwendung", cm.exception.meldung)
            konf = dict(self._konfig(), anbieter="keine")
            konf["bereit"], konf["grund"] = cloover_pdf_ablage._bereitschaft(konf)
            self.assertEqual(konf["grund"], "PDF-Ablage nicht eingerichtet")
            with mock.patch.object(graph_versand, "modus", return_value="anwendung"), \
                    mock.patch.object(graph_versand, "_token", return_value=None):
                with self.assertRaises(cloover_pdf_ablage.AblageFehler):
                    cloover_pdf_ablage.ablegen(tmp, "x.pdf", self._konfig())
        finally:
            tmp.unlink(missing_ok=True)

    def test_pruefen_head(self):
        class Antwort:
            def __init__(self, status, typ, inhalt=b""):
                self.status, self.headers, self._inhalt = status, {"Content-Type": typ}, inhalt

            def read(self, n=-1):
                return self._inhalt[:n] if n and n > 0 else self._inhalt

            def __enter__(self):
                return self

            def __exit__(self, *a):
                return False

        def urlopen_pdf(anfrage, timeout=0):
            self.assertEqual(anfrage.get_method(), "HEAD")
            return Antwort(200, "application/pdf")

        with mock.patch("urllib.request.urlopen", side_effect=urlopen_pdf):
            self.assertEqual(cloover_pdf_ablage.pruefen("https://x.test/a.pdf")[0], True)

        def urlopen_405(anfrage, timeout=0):
            if anfrage.get_method() == "HEAD":
                raise urllib.error.HTTPError(anfrage.full_url, 405, "nope", {}, None)
            return Antwort(206, "application/octet-stream", b"%PDF-1.7 abc")

        with mock.patch("urllib.request.urlopen", side_effect=urlopen_405):
            ok, text = cloover_pdf_ablage.pruefen("https://x.test/b.pdf")
            self.assertTrue(ok, text)

        def urlopen_html(anfrage, timeout=0):
            return Antwort(200, "text/html", b"<html>Anmelden</html>")

        with mock.patch("urllib.request.urlopen", side_effect=urlopen_html):
            ok, text = cloover_pdf_ablage.pruefen("https://x.test/c.pdf")
            self.assertFalse(ok)
            self.assertIn("kein PDF", text)
        self.assertEqual(cloover_pdf_ablage.pruefen("ftp://x")[0], False)


class Parametrierung(Basis):
    def test_seite_speichern_und_test_pdf(self):
        seite = self.client.get("/parametrierung/cloover")
        self.assertEqual(seite.status_code, 200)
        self.assertIn('id="ablage"', seite.text)
        self.assertIn("Test-PDF ablegen und prüfen", seite.text)
        self.assertIn("basis_url", seite.text)
        antwort = self.client.post("/parametrierung/cloover/ablage",
                                   data={"cloover_pdf_ablage": "keine", "cloover_sharepoint_site": "x:/sites/y",
                                         "cloover_sharepoint_ordner": "Cloover-Angebote"}, follow_redirects=False)
        self.assertEqual(antwort.status_code, 303)
        self.assertIn("#ablage", antwort.headers["location"])
        self.s.expire_all()
        self.assertEqual(einstellung_holen(self.s, "cloover_pdf_ablage", ""), "keine")
        self.assertEqual(einstellung_holen(self.s, "cloover_sharepoint_site", ""), "x:/sites/y")
        self.assertIn("cloover_pdf_ablage: basis_url → keine", cloover_api.protokoll(self.s))
        # Test-PDF über die Token-Ablage (HEAD gemockt)
        with mock.patch.object(config, "BASIS_URL_AUS_ENV", True), mock.patch.object(config, "BASIS_URL", BASIS), \
                mock.patch.object(cloover_pdf_ablage, "pruefen", return_value=(True, "HEAD ohne Anmeldung: application/pdf")):
            antwort = self.client.post("/parametrierung/cloover/ablage-test",
                                       data={"cloover_pdf_ablage": "basis_url"}, follow_redirects=False)
        self.assertEqual(antwort.status_code, 303)
        ziel = unquote_plus(antwort.headers["location"])
        self.assertIn("Ablage OK", ziel)
        self.assertIn("Ersetzen geprüft", ziel)
        self.s.expire_all()
        letzter = cloover_pdf_ablage.letzter_test(self.s)
        self.assertTrue(letzter["ok"], letzter)
        self.assertIn("/oeffentlich/cloover/", letzter["url"])
        # Test-PDF ist ein echtes PDF ohne Kundendaten
        pdf = cloover_pdf_ablage.test_pdf_bytes()
        self.assertTrue(pdf.startswith(b"%PDF"))
        # Innendienst: 403 wie die übrige Cloover-Seite
        innendienst = self.s.query(Benutzer).filter(Benutzer.rolle == "innendienst", Benutzer.aktiv.is_(True)).first()
        if innendienst is not None:
            client = TestClient(app, raise_server_exceptions=False)
            client.cookies.set(auth.COOKIE_NAME, auth.cookie_wert(innendienst.id))
            self.assertEqual(client.post("/parametrierung/cloover/ablage", data={"cloover_pdf_ablage": "keine"},
                                         follow_redirects=False).status_code, 403)

    def test_ablage_nicht_bereit(self):
        einstellung_setzen(self.s, "cloover_pdf_ablage", "keine")
        self.s.commit()
        ok, text = cloover_pdf_ablage.test_ablage(self.s)
        self.s.commit()
        self.assertFalse(ok)
        self.assertIn("PDF-Ablage nicht eingerichtet", text)
        self.assertFalse(cloover_pdf_ablage.letzter_test(self.s)["ok"])


class KeyNieImProtokoll(unittest.TestCase):
    def test_fehlerprotokoll_und_log_ohne_key(self):
        init_db()
        vorher = datetime.datetime.now() - datetime.timedelta(seconds=2)
        with mock.patch.object(config, "CLOOVER_API_KEY", KEY), \
                mock.patch.object(cloover_api, "_roh_anfrage", return_value=(422, {"message": "phone invalid " + KEY})):
            cloover_api.cache_leeren()
            with mock.patch.object(cloover_api, "_modus_aktuell", return_value="test"):
                status, antwort = cloover_api._anfrage("POST", "/api/projects", {"customer": {"phone": "x"}})
        self.assertEqual(status, 422)
        s = SessionLocal()
        try:
            zeilen = s.query(Fehlerprotokoll).filter(Fehlerprotokoll.zeit >= vorher,
                                                     Fehlerprotokoll.fehlertyp == "Cloover").all()
            self.assertTrue(zeilen)
            for z in zeilen:
                self.assertNotIn(KEY, (z.meldung or "") + (z.traceback or ""))
                self.assertIn("customer.phone", z.traceback)                     # nur Feldnamen, nie Werte
        finally:
            s.close()
        log = Path(config.DATA_ORDNER) / "fehler.log"
        if log.exists():
            self.assertNotIn(KEY, log.read_text(encoding="utf-8", errors="replace"))
        # eigene Meldungen des Projektmoduls enthalten den Key ebenfalls nie (Maskierung von B1 greift,
        # solange der Key gesetzt ist – wie im Betrieb)
        with mock.patch.object(config, "CLOOVER_API_KEY", KEY):
            meldung = cloover_projekt.MELDUNG_PREFIX + cloover_api.fehler_meldung(422, {"message": "x " + KEY})
        self.assertNotIn(KEY, meldung)


class Scheduler(unittest.TestCase):
    def test_registrierung(self):
        vorher = {lauf.name for lauf in scheduler.alle()}
        scheduler.zuruecksetzen_fuer_tests()
        try:
            cloover_projekt.scheduler_starten()
            lauf = scheduler.holen("cloover-status")
            self.assertIsNotNone(lauf)
            self.assertEqual((lauf.intervall_s, lauf.start_verzoegerung_s), (3600, 400))
            self.assertIn("Cloover", lauf.beschreibung)
            self.assertIsNone(lauf.thread)
            with mock.patch.object(config, "CLOOVER_API_KEY", ""):
                aktiv, grund = lauf.ist_aktiv()
                self.assertFalse(aktiv)
                self.assertIn("kein Cloover-Key", grund)
            with mock.patch.object(config, "CLOOVER_API_KEY", KEY):
                self.assertEqual(lauf.ist_aktiv(), (True, ""))
            cloover_projekt.scheduler_starten()        # idempotent
            self.assertEqual(scheduler.anzahl(), 1)
        finally:
            scheduler.zuruecksetzen_fuer_tests()
            if vorher:
                from app import betrieb
                from tests import test_v27_scheduler as t
                t.alle_registrieren()
                betrieb.scheduler_registrieren()

    def test_pool_invariante_mit_18_laeufen(self):
        from app import db
        ok, text = db.pool_invariante(18)
        self.assertTrue(ok, text)
        self.assertIn("Scheduler 18", text)


if __name__ == "__main__":
    unittest.main()
