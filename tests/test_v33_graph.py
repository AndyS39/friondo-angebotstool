# v33 (PLAN_V20 Phase 166, Agent G): Graph als Anwendung – Token-Flow (MSAL gemockt),
# /users/-Pfade aller Aufrufe im Modus anwendung (Versand angebot@/termin@/projektierung@,
# Abruf, Entwurf in angebot@ mit Signatur des Vorbereiters), 403 → Fehlerprotokoll einmal je
# Stunde, Modus-Umschaltung durch den Verbindungstest, Ergebnisse je Postfach, Postfach-
# Liste der Verbindungs-Seite, mail_senden_als (Vertrag G → N), Go-live-Punkt, /health-
# Warnung, Kachel Betrieb; Phase 175: {vertriebler_block} ohne Infotext.
# KEIN Netz, KEIN echtes Geheimnis: config.GRAPH_CLIENT_SECRET wird nur mit einem
# Fantasiewert gemockt, urllib/_graph_aufruf/MSAL sind durchgehend gemockt.
import contextlib
import io
import json
import sys
import tempfile
import time
import types
import unittest
import urllib.error
import warnings
from datetime import date, datetime, timedelta
from pathlib import Path
from unittest import mock

warnings.filterwarnings("ignore")

from fastapi.testclient import TestClient

from app import auth, benachrichtigungen, betrieb, config, golive, graph_versand, lead_mail
from app import lead_mail_abruf, mail_sync
from app import projektierung as projekt_kern
from app import leadmanagement as lead_kern
from app.db import SessionLocal, init_db
from app.main import app
from app.models import (AdProfil, Angebot, Benutzer, Einstellung, Kunde, LeadAktivitaet, Team,
                        Vorgang, VotTermin, einstellung_holen, einstellung_setzen)
from app.routers import versand as versand_router

PRAEFIX = "V33G"
GEHEIMNIS_TEST = "nur-im-test-gemockt-kein-echtes-geheimnis"
CLIENT_ID_TEST = "00000000-0000-4000-8000-000000000001"
TENANT_ID_TEST = "11111111-2222-4333-8444-555555555555"
PNG = bytes.fromhex(
    "89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c489"
    "0000000d4944415478da63f8ffff3f0300050001e9fa4c0d0000000049454e44ae426082")


def anwendung_mocks() -> list:
    """config so gemockt, dass der Modus anwendung möglich ist (nur Fantasiewerte)."""
    return [mock.patch.object(config, "GRAPH_CLIENT_ID", CLIENT_ID_TEST),
            mock.patch.object(config, "GRAPH_TENANT_ID", TENANT_ID_TEST),
            mock.patch.object(config, "GRAPH_CLIENT_SECRET", GEHEIMNIS_TEST),
            mock.patch.object(config, "GRAPH_ZERTIFIKAT_PFAD", ""),
            mock.patch.object(config, "GRAPH_ZERTIFIKAT_THUMBPRINT", "")]


def http_fehler(code: int, pfad: str = "/x") -> urllib.error.HTTPError:
    return urllib.error.HTTPError(graph_versand.GRAPH + pfad, code, "Fehler", {}, io.BytesIO(b""))


def aufraeumen(s) -> None:
    s.rollback()
    for k in s.query(Kunde).filter(Kunde.nachname.like(f"{PRAEFIX}%")):
        for v in s.query(Vorgang).filter_by(kunde_id=k.id):
            s.query(LeadAktivitaet).filter_by(vorgang_id=v.id).delete()
            s.query(VotTermin).filter_by(vorgang_id=v.id).delete()
            s.delete(v)
        s.delete(k)
    for b in s.query(Benutzer).filter(Benutzer.name.like(f"{PRAEFIX}%")):
        s.query(AdProfil).filter_by(benutzer_id=b.id).delete()
        s.query(VotTermin).filter_by(ad_id=b.id).delete()
        s.query(Einstellung).filter(Einstellung.name.like(
            f"lead_vorlage_{lead_mail.vertriebler_key(b.id)}%")).delete(synchronize_session=False)
        for pfad in (lead_mail.BENUTZERBILDER_ORDNER.glob(f"{b.id}.*")
                     if lead_mail.BENUTZERBILDER_ORDNER.exists() else []):
            pfad.unlink(missing_ok=True)
        s.delete(b)
    s.query(Team).filter(Team.name.like(f"{PRAEFIX}%")).delete(synchronize_session=False)
    s.commit()


class Basis(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        init_db()
        cls.s = SessionLocal()
        aufraeumen(cls.s)
        cls.modus_alt = einstellung_holen(cls.s, graph_versand.EINSTELLUNG_MODUS, "")
        cls.test_alt = einstellung_holen(cls.s, graph_versand.EINSTELLUNG_LETZTER_TEST, "")
        cls.client = TestClient(app)
        cls.client.cookies.set(auth.COOKIE_NAME, auth.cookie_wert(1))
        cls.admin = cls.s.get(Benutzer, 1)

    @classmethod
    def tearDownClass(cls):
        cls.s.rollback()
        einstellung_setzen(cls.s, graph_versand.EINSTELLUNG_MODUS, cls.modus_alt or "delegiert")
        einstellung_setzen(cls.s, graph_versand.EINSTELLUNG_LETZTER_TEST, cls.test_alt)
        cls.s.commit()
        aufraeumen(cls.s)
        cls.s.close()
        graph_versand.modus_cache_leeren()
        graph_versand.zugriff_verweigert_leeren()
        graph_versand.erfolge_leeren()

    def setUp(self):
        self.s.rollback()
        graph_versand.modus_cache_leeren()
        graph_versand.zugriff_verweigert_leeren()
        graph_versand.erfolge_leeren()

    def modus_setzen(self, wert: str) -> None:
        graph_versand.modus_setzen(self.s, wert)
        self.s.commit()

    @contextlib.contextmanager
    def anwendung(self, graph=None, token="tok"):
        """Modus anwendung mit gemocktem Token und Graph-Aufruf; liefert die Aufrufliste."""
        aufrufe: list = []

        def standard(methode, pfad, tok, daten=None, timeout=60):
            aufrufe.append((methode, pfad, daten))
            if pfad.endswith("/messages") and methode == "POST":
                return {"id": "msg-1", "webLink": "https://outlook/x", "conversationId": "konv-1"}
            return {}

        with contextlib.ExitStack() as stapel:
            for p in anwendung_mocks():
                stapel.enter_context(p)
            self.modus_setzen("anwendung")
            stapel.enter_context(mock.patch.object(graph_versand, "_token", return_value=token))
            stapel.enter_context(mock.patch.object(graph_versand, "_graph_aufruf",
                                                   side_effect=graph or standard))
            yield aufrufe

    def benutzer(self, name, **felder) -> Benutzer:
        return benutzer_anlegen(self.s, name, **felder)


def benutzer_anlegen(s, name, rolle="aussendienst", email="", aktiv=True, profil=True,
                     terminiert_selbst=False, kalender_postfach=None, **extra) -> Benutzer:
    """Testbenutzer mit Präfix; Außendienst bekommt ein AD-Profil (HV über terminiert_selbst)."""
    b = Benutzer(name=f"{PRAEFIX} {name}", rolle=rolle, pin_hash=auth.pin_hash("482913"),
                 email=email, aktiv=aktiv, **extra)
    s.add(b)
    s.flush()
    if profil and rolle in ("aussendienst", "handelsvertreter"):
        s.add(AdProfil(benutzer_id=b.id, start_adresse="Duisburg",
                       aktiv_terminierung=not terminiert_selbst,
                       terminiert_selbst=terminiert_selbst, arbeitszeiten="{}",
                       gebiet_plz_praefixe="[]", kompetenz_sparten="[]",
                       kalender_postfach=kalender_postfach))
    s.commit()
    return b


# --- Token-Flow (MSAL gemockt) ---------------------------------------------------------------

class TokenFlow(unittest.TestCase):
    def setUp(self):
        graph_versand.modus_cache_leeren()

    def tearDown(self):
        graph_versand.modus_cache_leeren()

    def test_confidential_client_mit_geheimnis_und_mandant(self):
        fake_msal = types.SimpleNamespace(ConfidentialClientApplication=mock.Mock(return_value="app"))
        with contextlib.ExitStack() as stapel:
            for p in anwendung_mocks():
                stapel.enter_context(p)
            stapel.enter_context(mock.patch.dict(sys.modules, {"msal": fake_msal}))
            self.assertEqual(graph_versand._confidential_app(), "app")
        args, kwargs = fake_msal.ConfidentialClientApplication.call_args
        self.assertEqual(args[0], CLIENT_ID_TEST)
        self.assertTrue(kwargs["authority"].endswith("/" + TENANT_ID_TEST))
        self.assertEqual(kwargs["client_credential"], GEHEIMNIS_TEST)   # Fantasiewert, nie echt

    def test_token_cache_erneuerung_vor_ablauf_und_fehler(self):
        app_mock = mock.Mock()
        app_mock.acquire_token_for_client.return_value = {"access_token": "tok-1", "expires_in": 3600}
        with mock.patch.object(graph_versand, "_confidential_app", return_value=app_mock):
            self.assertEqual(graph_versand._token_anwendung(), "tok-1")
            self.assertEqual(graph_versand._token_anwendung(), "tok-1")   # aus dem Cache
            self.assertEqual(app_mock.acquire_token_for_client.call_count, 1)
            self.assertEqual(app_mock.acquire_token_for_client.call_args.kwargs["scopes"],
                             ["https://graph.microsoft.com/.default"])
            # Erneuerung VOR Ablauf: Restlaufzeit kleiner als die Reserve (300 s) → neues Token
            with graph_versand._app_sperre:
                graph_versand._app_token["ablauf"] = time.time() + graph_versand.TOKEN_RESERVE_S - 10
            app_mock.acquire_token_for_client.return_value = {"access_token": "tok-2", "expires_in": 3600}
            self.assertEqual(graph_versand._token_anwendung(), "tok-2")
            self.assertEqual(app_mock.acquire_token_for_client.call_count, 2)
            self.assertEqual(graph_versand.token_fehler(), "")
            # Fehlerantwort → None + Grund
            graph_versand.app_token_verwerfen()
            app_mock.acquire_token_for_client.return_value = {"error": "invalid_client",
                                                              "error_description": "AADSTS7000215 Geheimnis ungültig"}
            self.assertIsNone(graph_versand._token_anwendung())
            self.assertIn("AADSTS7000215", graph_versand.token_fehler())
            # Ausnahme (kein Netz) → None + Grund
            app_mock.acquire_token_for_client.side_effect = OSError("kein Netz")
            self.assertIsNone(graph_versand._token_anwendung())
            self.assertIn("kein Netz", graph_versand.token_fehler())

    def test_token_und_texte_je_modus(self):
        s = SessionLocal()
        try:
            alt = einstellung_holen(s, graph_versand.EINSTELLUNG_MODUS, "")
            with contextlib.ExitStack() as stapel:
                for p in anwendung_mocks():
                    stapel.enter_context(p)
                graph_versand.modus_setzen(s, "anwendung")
                s.commit()
                with mock.patch.object(graph_versand, "_token_anwendung", return_value="app-tok") as app_tok, \
                        mock.patch.object(graph_versand, "_app", side_effect=AssertionError("kein Device-Flow")):
                    self.assertEqual(graph_versand._token(), "app-tok")
                    self.assertTrue(app_tok.called)
                    self.assertEqual(graph_versand.angemeldeter_benutzer(), graph_versand.KONTO_ANWENDUNG)
                    self.assertTrue(graph_versand.verbunden(s))
                    self.assertEqual(graph_versand.modus_grund(s), "")
                with mock.patch.object(graph_versand, "_token_anwendung", return_value=None):
                    with graph_versand._app_sperre:
                        graph_versand._app_token["fehler"] = "invalid_client"
                    self.assertIn("Anmeldung der Anwendung fehlgeschlagen: invalid_client",
                                  graph_versand.nicht_verbunden_text())
                # delegiert: Token des angemeldeten Kontos (hier keins)
                graph_versand.modus_setzen(s, "delegiert")
                s.commit()
                app_mock = mock.Mock()
                app_mock.get_accounts.return_value = []
                with mock.patch.object(graph_versand, "_app", return_value=app_mock), \
                        mock.patch.object(graph_versand, "_token_anwendung", side_effect=AssertionError("kein App-Token")):
                    self.assertIsNone(graph_versand._token())
                    self.assertIsNone(graph_versand.angemeldeter_benutzer())
                    self.assertFalse(graph_versand.verbunden(s))
                self.assertIn("Verbindungstest offen", graph_versand.modus_grund(s))
                self.assertTrue(graph_versand.nicht_verbunden_text().startswith("Nicht bei Microsoft angemeldet"))
            # ohne Geheimnis: immer delegiert, Grund „Geheimnis fehlt“
            with mock.patch.object(config, "GRAPH_CLIENT_ID", CLIENT_ID_TEST), \
                    mock.patch.object(config, "GRAPH_TENANT_ID", TENANT_ID_TEST), \
                    mock.patch.object(config, "GRAPH_CLIENT_SECRET", ""), \
                    mock.patch.object(config, "GRAPH_ZERTIFIKAT_PFAD", ""):
                graph_versand.modus_cache_leeren()
                self.assertEqual(graph_versand.modus(s), "delegiert")
                self.assertIn("Geheimnis fehlt", graph_versand.modus_grund(s))
            einstellung_setzen(s, graph_versand.EINSTELLUNG_MODUS, alt or "delegiert")
            s.commit()
        finally:
            s.close()
        self.assertEqual(graph_versand.mandant_maskiert(), (config.GRAPH_TENANT_ID[:8] + "…")
                         if len(config.GRAPH_TENANT_ID) > 8 else (config.GRAPH_TENANT_ID or "–"))
        with mock.patch.object(config, "GRAPH_TENANT_ID", TENANT_ID_TEST):
            self.assertEqual(graph_versand.mandant_maskiert(), "11111111…")


# --- /users/-Pfade im Modus anwendung ------------------------------------------------------

class PfadeAnwendung(Basis):
    def test_text_mail_funktionspostfach_ohne_from(self):
        with self.anwendung() as aufrufe:
            ok, fehler = graph_versand.text_mail_senden("k@test.invalid", "B", "T",
                                                        absender="projektierung@friondo.de")
            self.assertTrue(ok, fehler)
            self.assertEqual(aufrufe[-1][:2], ("POST", "/users/projektierung%40friondo.de/sendMail"))
            self.assertNotIn("from", aufrufe[-1][2]["message"])
            self.assertEqual(aufrufe[-1][2]["message"]["toRecipients"][0]["emailAddress"]["address"],
                             "k@test.invalid")
            # ohne Absender: Funktionspostfach des Versands (Einstellung mail_absender)
            graph_versand.text_mail_senden("k@test.invalid", "B", "T")
            standard = graph_versand.standard_postfach(self.s).replace("@", "%40")
            self.assertEqual(aufrufe[-1][1], f"/users/{standard}/sendMail")
            self.assertTrue(graph_versand.basis_pfad("").startswith("/users/"))
            self.assertEqual(graph_versand.versand_pfad("termin@friondo.de"),
                             ("/users/termin%40friondo.de", ""))

    def test_delegiert_unveraendert_me_mit_from(self):
        self.modus_setzen("delegiert")
        aufrufe = []
        with mock.patch.object(graph_versand, "_token", return_value="tok"), \
                mock.patch.object(graph_versand, "_graph_aufruf",
                                  side_effect=lambda m, p, t, d=None, timeout=60: aufrufe.append((m, p, d)) or {}):
            graph_versand.text_mail_senden("k@test.invalid", "B", "T", absender="projektierung@friondo.de")
        self.assertEqual(aufrufe[-1][:2], ("POST", "/me/sendMail"))
        self.assertEqual(aufrufe[-1][2]["message"]["from"]["emailAddress"]["address"],
                         "projektierung@friondo.de")
        self.assertEqual(graph_versand.versand_pfad("termin@friondo.de"), ("/me", "termin@friondo.de"))
        self.assertEqual(graph_versand.basis_pfad(""), "/me")

    def test_mail_mit_anhaengen_entwurf_anhang_send_und_rueckfall(self):
        with self.anwendung() as aufrufe:
            ok, fehler, konv = graph_versand.mail_mit_anhaengen_senden(
                "sub@test.invalid", "B", "T", [("Steckbrief.pdf", b"%PDF", "application/pdf")],
                cc=["leiter@friondo.de"], absender="projektierung@friondo.de")
            self.assertTrue(ok, fehler)
            self.assertEqual(konv, "konv-1")
            self.assertEqual([(m, p) for m, p, _ in aufrufe], [
                ("POST", "/users/projektierung%40friondo.de/messages"),
                ("POST", "/users/projektierung%40friondo.de/messages/msg-1/attachments"),
                ("POST", "/users/projektierung%40friondo.de/messages/msg-1/send")])
            self.assertNotIn("from", aufrufe[0][2])
            self.assertEqual(aufrufe[0][2]["ccRecipients"][0]["emailAddress"]["address"], "leiter@friondo.de")
            self.assertEqual(aufrufe[1][2]["name"], "Steckbrief.pdf")
        # Rückfall: projektierung@ scheitert → zweiter Versuch am Funktionspostfach angebot@
        standard = graph_versand.standard_postfach(self.s).replace("@", "%40")
        versuche = []

        def graph(methode, pfad, tok, daten=None, timeout=60):
            versuche.append(pfad)
            if "projektierung%40" in pfad:
                raise RuntimeError("Postfach projektierung@ ist nicht in der Zugriffsgruppe")
            return {"id": "m2", "conversationId": "konv-2"}
        with self.anwendung(graph=graph):
            ok, fehler, konv = graph_versand.mail_mit_anhaengen_senden(
                "x@test.invalid", "B", "T", absender="projektierung@friondo.de")
            self.assertTrue(ok, fehler)
            self.assertEqual(konv, "konv-2")
            self.assertEqual(versuche[0], "/users/projektierung%40friondo.de/messages")
            self.assertEqual(versuche[1], f"/users/{standard}/messages")
        # kein zweiter Versuch, wenn der gescheiterte Absender schon das Funktionspostfach ist
        versuche.clear()

        def graph_alles_rot(methode, pfad, tok, daten=None, timeout=60):
            versuche.append(pfad)
            raise RuntimeError("rot")
        with self.anwendung(graph=graph_alles_rot):
            ok, fehler, _ = graph_versand.mail_mit_anhaengen_senden(
                "x@test.invalid", "B", "T", absender=graph_versand.standard_postfach(self.s))
            self.assertFalse(ok)
            self.assertIn("Versand fehlgeschlagen", fehler)
            self.assertEqual(len(versuche), 1)

    def test_lead_mail_termin_sendmail_ohne_from_mit_replyto(self):
        absender = lead_mail.absender(self.s)
        with self.anwendung() as aufrufe:
            ok, fehler = lead_mail._graph_senden(self.s, "kunde@test.invalid", "Termin", "<p>Hallo</p>",
                                                 None, vorgang=None)
            self.assertTrue(ok, fehler)
            methode, pfad, daten = aufrufe[-1]
            self.assertEqual((methode, pfad), ("POST", f"/users/{absender.replace('@', '%40')}/sendMail"))
            self.assertNotIn("from", daten["message"])
            self.assertEqual([r["emailAddress"]["address"] for r in daten["message"]["replyTo"]], [absender])
            self.assertFalse(daten["saveToSentItems"])
            ok, fehler = lead_mail.testmail_senden(absender, "test@test.invalid")
            self.assertTrue(ok, fehler)
            self.assertEqual(aufrufe[-1][1], f"/users/{absender.replace('@', '%40')}/sendMail")
            self.assertNotIn("from", aufrufe[-1][2]["message"])
        # ohne Token: Text je Modus
        with contextlib.ExitStack() as stapel:
            for p in anwendung_mocks():
                stapel.enter_context(p)
            self.modus_setzen("anwendung")
            with mock.patch.object(graph_versand, "_token", return_value=None):
                ok, fehler = lead_mail.testmail_senden(absender, "test@test.invalid")
                self.assertFalse(ok)
                self.assertIn("Anmeldung der Anwendung fehlgeschlagen", fehler)
        self.modus_setzen("delegiert")
        with mock.patch.object(graph_versand, "_token", return_value=None):
            ok, fehler = lead_mail.testmail_senden(absender, "test@test.invalid")
            self.assertIn(lead_mail_abruf.NICHT_ANGEMELDET, fehler)

    def test_postfach_abruf_termin_und_mail_sync_angebot(self):
        with self.anwendung() as aufrufe:
            graph_versand.postfach_ungelesen("tok", "termin@friondo.de", top=10)
            self.assertTrue(aufrufe[-1][1].startswith("/users/termin%40friondo.de/mailFolders/inbox/messages?$top=10"))
            graph_versand.nachricht_kopfzeilen("tok", "termin@friondo.de", "abc")
            self.assertEqual(aufrufe[-1][1], "/users/termin%40friondo.de/messages/abc?$select=internetMessageHeaders")
            self.assertTrue(graph_versand.nachricht_gelesen_markieren("tok", "termin@friondo.de", "abc"))
            self.assertEqual(aufrufe[-1][:2], ("PATCH", "/users/termin%40friondo.de/messages/abc"))
            # Versand-Erkennung/Mail-Verlauf: Konversation in angebot@ (auch ohne Angabe)
            standard = graph_versand.standard_postfach(self.s).replace("@", "%40")
            self.assertEqual(mail_sync._basis(""), f"/users/{standard}")
            self.assertEqual(mail_sync._basis("angebot@friondo.de"), "/users/angebot%40friondo.de")
            mail_sync.nachrichten_je_konversation("tok", "konv-9", "angebot@friondo.de")
            self.assertTrue(aufrufe[-1][1].startswith("/users/angebot%40friondo.de/messages?$filter="))
            mail_sync.nachrichten_je_betreff("tok", "AN-C-260001", "")
            self.assertTrue(aufrufe[-1][1].startswith(f"/users/{standard}/messages?$search="))
        # Lauf lead-mail-abruf ohne Token: Zustand je Modus
        with contextlib.ExitStack() as stapel:
            for p in anwendung_mocks():
                stapel.enter_context(p)
            self.modus_setzen("anwendung")
            with mock.patch.object(graph_versand, "_token", return_value=None):
                erg = lead_mail_abruf.scheduler_lauf()
            self.assertIn("Anmeldung der Anwendung fehlgeschlagen", erg["ergebnis"])

    def test_benachrichtigungen_golive_und_info_mail(self):
        absender = benachrichtigungen._absender(self.s).replace("@", "%40")
        testmail_vorher = projekt_kern.parameter_holen(self.s, "golive_testmail", "")
        try:
            with self.anwendung() as aufrufe:
                self.assertTrue(benachrichtigungen.mail_senden(self.s, "x@test.invalid", "B", "T"))
                self.assertEqual(aufrufe[-1][:2], ("POST", f"/users/{absender}/sendMail"))
                self.assertNotIn("from", aufrufe[-1][2]["message"])
                ok, meldung = golive.testmail_senden(self.s, self.admin)
                self.assertTrue(ok, meldung)
                self.assertEqual(aufrufe[-1][1], f"/users/{absender}/sendMail")
                # Info-Mail nach Fern-Signatur: vom Funktionspostfach an dasselbe Postfach
                self.assertTrue(graph_versand.info_mail_senden("Signiert", "Text"))
                standard = graph_versand.standard_postfach(self.s)
                self.assertEqual(aufrufe[-1][1], f"/users/{standard.replace('@', '%40')}/sendMail")
                self.assertEqual(aufrufe[-1][2]["message"]["toRecipients"][0]["emailAddress"]["address"], standard)
        finally:
            projekt_kern.parameter_setzen(self.s, "golive_testmail", testmail_vorher)
            self.s.commit()


# --- Entwurf in angebot@ mit Signatur des Vorbereiters ---------------------------------------

class EntwurfAngebot(Basis):
    def test_entwurf_landet_in_angebot_mit_signatur_cc_bcc(self):
        kunde = Kunde(anrede="Frau", vorname="Erika", nachname=f"{PRAEFIX}-Entwurf", email="erika@test.invalid")
        angebot = Angebot(nummer="AN-C-269999", datum=datetime(2026, 10, 14))
        signatur = '<div class="signatur">Claudia Castro · Innendienst</div>'
        with tempfile.TemporaryDirectory() as ordner:
            pdf = Path(ordner) / "AN-C-269999.pdf"
            pdf.write_bytes(b"%PDF-1.4 test")
            bild = Path(ordner) / "logo.png"
            bild.write_bytes(PNG)
            with self.anwendung() as aufrufe:
                erfolg, meldung, weblink, konv = graph_versand.entwurf_erstellen(
                    kunde, angebot, pdf, "Ihr Angebot AN-C-269999", "<p>Text</p>" + signatur,
                    cc=["horst@friondo.de"], bcc=["info@friondo.de"], absender="angebot@friondo.de",
                    inline_bilder=[("sig-1", bild, "image/png")])
        self.assertTrue(erfolg, meldung)
        self.assertEqual((weblink, konv), ("https://outlook/x", "konv-1"))
        self.assertIn("angebot@friondo.de", meldung)
        self.assertIn("Entwürfe", meldung)
        methode, pfad, nachricht = aufrufe[0]
        self.assertEqual((methode, pfad), ("POST", "/users/angebot%40friondo.de/messages"))
        self.assertNotIn("from", nachricht)   # kein „Senden als“ mehr
        self.assertIn("Claudia Castro", nachricht["body"]["content"])
        self.assertEqual(nachricht["body"]["contentType"], "html")
        self.assertEqual(nachricht["ccRecipients"][0]["emailAddress"]["address"], "horst@friondo.de")
        self.assertEqual(nachricht["bccRecipients"][0]["emailAddress"]["address"], "info@friondo.de")
        self.assertEqual([p for _, p, _ in aufrufe[1:]],
                         ["/users/angebot%40friondo.de/messages/msg-1/attachments"] * 2)
        self.assertTrue(aufrufe[1][2]["isInline"])
        self.assertEqual(aufrufe[2][2]["name"], "AN-C-269999.pdf")

    def test_entwurf_delegiert_bleibt_me_mit_senden_als(self):
        self.modus_setzen("delegiert")
        aufrufe = []
        with tempfile.TemporaryDirectory() as ordner:
            pdf = Path(ordner) / "a.pdf"
            pdf.write_bytes(b"%PDF")
            with mock.patch.object(graph_versand, "_token", return_value="tok"), \
                    mock.patch.object(graph_versand, "_graph_aufruf",
                                      side_effect=lambda m, p, t, d=None, timeout=60: aufrufe.append((p, d)) or {"id": "1"}):
                erfolg, meldung, _, _ = graph_versand.entwurf_erstellen(
                    Kunde(email="k@x.de"), Angebot(nummer="AN-C-1", datum=datetime(2026, 10, 14)),
                    pdf, "B", "T", absender="angebot@friondo.de")
        self.assertTrue(erfolg, meldung)
        self.assertEqual(aufrufe[0][0], "/me/messages")
        self.assertEqual(aufrufe[0][1]["from"]["emailAddress"]["address"], "angebot@friondo.de")
        self.assertNotIn("angebot@friondo.de (Ordner", meldung)

    def test_kombi_versand_nutzt_dieselbe_funktion(self):
        wurzel = Path(__file__).resolve().parent.parent / "app" / "routers"
        for datei in ("angebote.py", "vorgaenge.py"):
            quelle = (wurzel / datei).read_text(encoding="utf-8")
            self.assertIn("graph_versand.entwurf_erstellen(", quelle, datei)
            self.assertIn("absender=absender", quelle, datei)
            self.assertNotIn("/me/", quelle, datei)


# --- 403 → Fehlerprotokoll einmal je Stunde, Erfolg je Postfach -----------------------------

class Zugriff403(Basis):
    def test_403_ueber_text_mail_einmal_je_stunde(self):
        fehler = http_fehler(403, "/users/termin%40friondo.de/sendMail")
        with contextlib.ExitStack() as stapel:
            for p in anwendung_mocks():
                stapel.enter_context(p)
            self.modus_setzen("anwendung")
            stapel.enter_context(mock.patch.object(graph_versand, "_token", return_value="tok"))
            stapel.enter_context(mock.patch("urllib.request.urlopen", side_effect=fehler))
            protokoll = stapel.enter_context(mock.patch("app.fehlerprotokoll.eintragen_text", return_value="F-1"))
            for _ in range(3):
                ok, text = graph_versand.text_mail_senden("k@test.invalid", "B", "T",
                                                          absender="termin@friondo.de")
                self.assertFalse(ok)
                self.assertIn("nicht in der Zugriffsgruppe Friondo-Tool-Zugriff", text)
            self.assertEqual(protokoll.call_count, 1)
            self.assertEqual(protokoll.call_args.args[0], "Graph")
            self.assertIn("termin@friondo.de", protokoll.call_args.args[1])
        self.assertEqual([p for p, _ in graph_versand.zugriff_verweigert_liste()], ["termin@friondo.de"])

    def test_erfolg_je_postfach_gemerkt_und_403_zurueckgesetzt(self):
        graph_versand.zugriff_verweigert_merken("angebot@friondo.de", "/users/angebot%40friondo.de/messages")
        antwort = mock.MagicMock()
        antwort.__enter__.return_value.read.return_value = b'{"value": []}'
        with mock.patch("urllib.request.urlopen", return_value=antwort):
            daten = graph_versand._graph_aufruf("GET", "/users/angebot%40friondo.de/messages", "tok")
        self.assertEqual(daten, {"value": []})
        self.assertIn("angebot@friondo.de", graph_versand.letzte_erfolge())
        self.assertEqual(graph_versand.zugriff_verweigert_liste(), [])
        # /me zählt als angemeldetes Konto
        with mock.patch("urllib.request.urlopen", return_value=antwort):
            graph_versand._graph_aufruf("GET", "/me/messages", "tok")
        self.assertIn("(angemeldetes Konto)", graph_versand.letzte_erfolge())


# --- Postfach-Liste, Verbindungstest, Modus-Umschaltung, Verbindungs-Seite ------------------

class Verbindung(Basis):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.domain = graph_versand.standard_postfach(cls.s).split("@")[-1]
        d = cls.domain
        s = cls.s
        cls.horst = benutzer_anlegen(s, "Horst", email=f"v33g.horst@{d}")
        cls.max = benutzer_anlegen(s, "Max", rolle="montage", email=f"v33g.max@{d}", profil=False)
        cls.ida = benutzer_anlegen(s, "Ida", rolle="innendienst", email=f"v33g.ida@{d}", profil=False)
        cls.pia = benutzer_anlegen(s, "Pia", rolle="projektierung", email=f"v33g.pia@{d}", profil=False)
        cls.paolo = benutzer_anlegen(s, "Paolo HV extern", email="v33g.paolo@extern.invalid", terminiert_selbst=True)
        cls.rene = benutzer_anlegen(s, "Rene HV intern", email=f"v33g.rene@{d}", terminiert_selbst=True)
        cls.alt = benutzer_anlegen(s, "Alt inaktiv", email=f"v33g.alt@{d}", aktiv=False)
        cls.lea = benutzer_anlegen(s, "Lea LM", rolle="leadmanagement", email=f"v33g.lea@{d}", profil=False)
        cls.ohne = benutzer_anlegen(s, "Ohne Mail", email="")
        cls.kal = benutzer_anlegen(s, "Kal", email=f"v33g.kal@{d}", kalender_postfach=f"v33g.kal-kalender@{d}")
        cls.team = Team(name=f"{PRAEFIX} Team Nord", typ="montage", aktiv=True,
                        outlook_adresse=f"v33g-team-nord@{d}")
        cls.s.add(cls.team)
        cls.s.commit()

    def test_benoetigte_postfaecher(self):
        liste = graph_versand.benoetigte_postfaecher(self.s)
        je = {e["postfach"].lower(): e for e in liste}
        d = self.domain
        for adresse in (f"v33g.horst@{d}", f"v33g.max@{d}", f"v33g.ida@{d}", f"v33g.pia@{d}",
                        f"v33g.rene@{d}", f"v33g.kal-kalender@{d}", f"v33g-team-nord@{d}"):
            self.assertIn(adresse, je, adresse)
        for adresse in ("v33g.paolo@extern.invalid", f"v33g.alt@{d}", f"v33g.lea@{d}", f"v33g.kal@{d}"):
            self.assertNotIn(adresse, je, adresse)
        self.assertEqual(je[f"v33g.max@{d}"]["art"], graph_versand.ART_MITARBEITER)
        self.assertEqual(je[f"v33g.max@{d}"]["pruefung"], "kalender")
        self.assertEqual(je[f"v33g.max@{d}"]["benutzer_id"], self.max.id)
        self.assertIn("Handelsvertreter", je[f"v33g.rene@{d}"]["name"])
        self.assertEqual(je[f"v33g-team-nord@{d}"]["art"], graph_versand.ART_FUNKTIONSPOSTFACH)
        self.assertEqual(je[f"v33g-team-nord@{d}"]["pruefung"], "kalender")
        # Funktionspostfächer aus Einstellungen/Parametern, dedupliziert (angebot@ für zwei Zwecke)
        funktion = [e for e in liste if e["art"] == graph_versand.ART_FUNKTIONSPOSTFACH]
        self.assertEqual(funktion[0]["postfach"].lower(), graph_versand.standard_postfach(self.s).lower())
        self.assertIn("Versand-Erkennung", funktion[0]["name"])
        self.assertIn("Entwürfe", funktion[0]["name"])
        self.assertEqual(funktion[0]["pruefung"], "inbox")
        self.assertIn(lead_mail.absender(self.s).lower(), je)
        self.assertIn(lead_kern.parameter_holen(self.s, "absender_postfach", "leads@friondo.de").lower(), je)
        self.assertIn(benachrichtigungen._absender(self.s).lower(), je)
        self.assertEqual(len(je), len(liste))   # keine Doppelten
        # Funktionspostfächer stehen vor den Mitarbeitern
        arten = [e["art"] for e in liste]
        self.assertEqual(arten, sorted(arten, key=lambda a: a != graph_versand.ART_FUNKTIONSPOSTFACH))

    def _test(self, graph=None, token="tok", token_fehler=""):
        """Verbindungstest mit gemocktem Anwendungs-Token/Graph – liefert (ergebnisse, pfade)."""
        pfade = []

        def standard(methode, pfad, tok, daten=None, timeout=60):
            pfade.append((methode, pfad, timeout))
            return {"id": "x"}

        def token_holen():
            with graph_versand._app_sperre:
                graph_versand._app_token["fehler"] = token_fehler
            return token
        with contextlib.ExitStack() as stapel:
            for p in anwendung_mocks():
                stapel.enter_context(p)
            stapel.enter_context(mock.patch.object(graph_versand, "_token_anwendung", side_effect=token_holen))
            stapel.enter_context(mock.patch.object(graph_versand, "_graph_aufruf", side_effect=graph or standard))
            stapel.enter_context(mock.patch.object(graph_versand, "_confidential_app",
                                                   side_effect=AssertionError("MSAL darf nicht aufgerufen werden")))
            ergebnisse = graph_versand.verbindungstest(self.s)
            modus = graph_versand.modus(self.s)
        return ergebnisse, pfade, modus

    def test_gruen_schaltet_auf_anwendung(self):
        self.modus_setzen("delegiert")
        ergebnisse, pfade, modus = self._test()
        self.assertTrue(all(e["ok"] for e in ergebnisse))
        self.assertEqual(modus, "anwendung")
        self.assertEqual(einstellung_holen(self.s, graph_versand.EINSTELLUNG_MODUS, ""), "anwendung")
        d = self.domain
        self.assertIn(("GET", f"/users/v33g.max%40{d}/calendar?$select=id", graph_versand.VERBINDUNGSTEST_TIMEOUT_S), pfade)
        self.assertIn(("GET", f"/users/{lead_mail.absender(self.s).replace('@', '%40')}/mailFolders/inbox?$select=id",
                       graph_versand.VERBINDUNGSTEST_TIMEOUT_S), pfade)
        letzter = graph_versand.letzter_test(self.s)
        self.assertTrue(letzter["gruen"])
        self.assertEqual(letzter["modus"], "anwendung")
        self.assertIsInstance(letzter["zeit_dt"], datetime)
        self.assertTrue(letzter["je_postfach"][f"v33g.max@{d}"]["ok"])
        self.assertTrue({"postfach", "ok", "grund", "art"} <= set(ergebnisse[0]))

    def test_rotes_funktionspostfach_schaltet_auf_delegiert(self):
        self.modus_setzen("anwendung")
        termin = lead_mail.absender(self.s).replace("@", "%40")
        leads = lead_kern.parameter_holen(self.s, "absender_postfach", "leads@friondo.de").replace("@", "%40")

        def graph(methode, pfad, tok, daten=None, timeout=60):
            if pfad.startswith(f"/users/{termin}/"):
                raise graph_versand.GraphZugriffVerweigert(lead_mail.absender(self.s), pfad)
            if pfad.startswith(f"/users/{leads}/"):
                raise http_fehler(404, pfad)
            return {}
        ergebnisse, _, modus = self._test(graph=graph)
        self.assertEqual(modus, "delegiert")
        je = {e["postfach"].lower(): e for e in ergebnisse}
        self.assertFalse(je[lead_mail.absender(self.s).lower()]["ok"])
        self.assertIn("nicht in der Zugriffsgruppe", je[lead_mail.absender(self.s).lower()]["grund"])
        self.assertIn("Postfach unbekannt", je[leads.replace("%40", "@").lower()]["grund"])
        self.assertTrue(je[f"v33g.max@{self.domain}"]["ok"])
        self.assertFalse(graph_versand.letzter_test(self.s)["gruen"])

    def test_roter_mitarbeiter_bleibt_anwendung_und_steht_in_der_fehlliste(self):
        self.modus_setzen("delegiert")
        d = self.domain

        def graph(methode, pfad, tok, daten=None, timeout=60):
            if f"v33g.max%40{d}" in pfad:
                raise graph_versand.GraphZugriffVerweigert(f"v33g.max@{d}", pfad)
            return {}
        ergebnisse, _, modus = self._test(graph=graph)
        self.assertEqual(modus, "anwendung")   # [eigene Annahme] nur Funktionspostfächer schalten
        je = {e["postfach"].lower(): e for e in ergebnisse}
        self.assertFalse(je[f"v33g.max@{d}"]["ok"])
        self.assertEqual(je[f"v33g.max@{d}"]["art"], graph_versand.ART_MITARBEITER)
        with contextlib.ExitStack() as stapel:
            for p in anwendung_mocks():
                stapel.enter_context(p)
            graph_versand.modus_cache_leeren()
            daten = versand_router.seite_daten(self.s)
        self.assertEqual(daten["modus"], "anwendung")
        self.assertEqual(daten["modus_grund"], "")
        self.assertIn(f"v33g.max@{d}", [f["postfach"] for f in daten["fehlend"]])
        self.assertIn(f"v33g.max@{d}", daten["fehlend_liste"].splitlines())
        self.assertIn(f"v33g.max@{d}", daten["kopierliste"].splitlines())

    def test_token_fehler_und_ohne_geheimnis(self):
        self.modus_setzen("anwendung")
        ergebnisse, pfade, modus = self._test(token=None, token_fehler="AADSTS7000215 invalid_client")
        self.assertEqual(modus, "delegiert")
        self.assertEqual(pfade, [])
        self.assertTrue(all(not e["ok"] for e in ergebnisse))
        self.assertTrue(ergebnisse[0]["grund"].startswith("Anmeldung der Anwendung fehlgeschlagen: AADSTS7000215"))
        # ohne Geheimnis: kein Token-Versuch, Grund „Geheimnis fehlt“
        with mock.patch.object(config, "GRAPH_CLIENT_ID", CLIENT_ID_TEST), \
                mock.patch.object(config, "GRAPH_TENANT_ID", TENANT_ID_TEST), \
                mock.patch.object(config, "GRAPH_CLIENT_SECRET", ""), \
                mock.patch.object(config, "GRAPH_ZERTIFIKAT_PFAD", ""), \
                mock.patch.object(graph_versand, "_token_anwendung", side_effect=AssertionError("kein Token-Versuch")):
            graph_versand.modus_cache_leeren()
            ergebnisse = graph_versand.verbindungstest(self.s)
        self.assertTrue(all("Geheimnis fehlt" in e["grund"] for e in ergebnisse))
        self.assertEqual(einstellung_holen(self.s, graph_versand.EINSTELLUNG_MODUS, ""), "delegiert")

    def test_vertrag_outlook_sync_postfaecher_ohne_zugriff(self):
        from app import outlook_sync
        d = self.domain
        # Ergebnis eines früheren Verbindungstests (alles rot) würde den Grund überdecken
        einstellung_setzen(self.s, graph_versand.EINSTELLUNG_LETZTER_TEST, "")
        self.s.commit()
        with mock.patch.object(outlook_sync, "postfaecher_ohne_zugriff", create=True,
                               return_value=[{"benutzer_id": self.pia.id, "name": self.pia.name,
                                              "postfach": f"v33g.pia@{d}", "zeit": datetime.now()}]):
            daten = versand_router.seite_daten(self.s)
        fehlend = {f["postfach"]: f["grund"] for f in daten["fehlend"]}
        self.assertIn(f"v33g.pia@{d}", fehlend)
        self.assertIn("Outlook-Lauf", fehlend[f"v33g.pia@{d}"])
        self.assertEqual(daten["ohne_zugriff"][0]["benutzer_id"], self.pia.id)
        # ohne die Funktion (Rückfall) rendert die Seite trotzdem
        with mock.patch.object(outlook_sync, "postfaecher_ohne_zugriff", create=True, side_effect=RuntimeError("kaputt")):
            self.assertEqual(versand_router._ohne_zugriff(self.s), [])

    def test_seite_und_knopf(self):
        d = self.domain
        with contextlib.ExitStack() as stapel:
            for p in anwendung_mocks():
                stapel.enter_context(p)
            stapel.enter_context(mock.patch.object(graph_versand, "delegiertes_konto", return_value=None))
            stapel.enter_context(mock.patch.object(config, "GRAPH_GEHEIMNIS_ABLAUF",
                                                   (date.today() + timedelta(days=200)).isoformat()))
            self.modus_setzen("delegiert")
            r = self.client.get("/versand")
            self.assertEqual(r.status_code, 200)
            html = r.text
            self.assertIn('id="verbindung-modus-wert"', html)
            self.assertIn("Delegiert", html)
            self.assertIn("11111111…", html)
            self.assertNotIn(TENANT_ID_TEST, html)        # Mandant nur maskiert
            self.assertNotIn(GEHEIMNIS_TEST, html)         # nie ein Geheimnis auf der Seite
            self.assertIn('id="tabelle-postfaecher"', html)
            self.assertIn(f"v33g.max@{d}", html)
            self.assertIn('id="kopierliste"', html)
            self.assertIn("Verbindung testen", html)
            self.assertIn("Mit Microsoft anmelden", html)
            self.assertIn("gültig bis", html)
            # Knopf: alles grün → Umleitung mit Meldung, Seite zeigt Modus Anwendung
            stapel.enter_context(mock.patch.object(graph_versand, "_token_anwendung", return_value="tok"))
            stapel.enter_context(mock.patch.object(graph_versand, "_graph_aufruf",
                                                   side_effect=lambda m, p, t, d_=None, timeout=60: {}))
            r = self.client.post("/versand/test", follow_redirects=False)
            self.assertEqual(r.status_code, 303)
            self.assertIn("Verbindungstest", r.headers["location"])
            self.assertIn("Anwendung", r.headers["location"])
            graph_versand.modus_cache_leeren()
            html = self.client.get("/versand").text
            self.assertIn('id="verbindung-modus-wert">Anwendung<', html)
            self.assertIn("nicht mehr nötig", html)
            self.assertIn("erreichbar", html)
            self.assertIn('id="liste-fehlend-leer"', html)
        # ohne GRAPH_CLIENT_ID: Hinweis, Postfach-Liste trotzdem (Kopierliste für die IT), kein Testknopf
        with mock.patch.object(config, "GRAPH_CLIENT_ID", ""), mock.patch.object(config, "GRAPH_CLIENT_SECRET", ""):
            graph_versand.modus_cache_leeren()
            html = self.client.get("/versand").text
            self.assertIn("noch nicht eingerichtet", html)
            self.assertIn('id="kopierliste"', html)
            self.assertNotIn('id="form-verbindungstest"', html)
            r = self.client.post("/versand/test", follow_redirects=False)
            self.assertIn("nicht+eingerichtet", r.headers["location"])


# --- mail_senden_als (Vertrag G → N, Nachfass-Mail aus dem AD-Postfach) ----------------------

class MailSendenAls(Basis):
    def test_anwendung_entwurf_anhang_send_am_postfach(self):
        with self.anwendung() as aufrufe:
            ok, fehler, konv = graph_versand.mail_senden_als(
                "horst@friondo.de", "kunde@test.invalid", "Nachfassen", "<p>Hallo</p>",
                anhaenge=[("AN-C-1.pdf", b"%PDF", "application/pdf")], cc=["lm@friondo.de"])
            self.assertTrue(ok, fehler)
            self.assertEqual(konv, "konv-1")
            self.assertEqual([(m, p) for m, p, _ in aufrufe], [
                ("POST", "/users/horst%40friondo.de/messages"),
                ("POST", "/users/horst%40friondo.de/messages/msg-1/attachments"),
                ("POST", "/users/horst%40friondo.de/messages/msg-1/send")])
            self.assertEqual(aufrufe[0][2]["body"]["contentType"], "html")
            self.assertNotIn("from", aufrufe[0][2])
            self.assertEqual(aufrufe[0][2]["ccRecipients"][0]["emailAddress"]["address"], "lm@friondo.de")
            # Empfängerliste + Text statt HTML
            ok, _, _ = graph_versand.mail_senden_als("horst@friondo.de", ["a@test.invalid", "b@test.invalid"],
                                                     "B", "", text_alternativ="nur Text")
            self.assertTrue(ok)
            self.assertEqual(len(aufrufe), 5)   # Entwurf + /send ohne Anhänge
            self.assertEqual(aufrufe[-2][2]["body"], {"contentType": "text", "content": "nur Text"})
            self.assertEqual(len(aufrufe[-2][2]["toRecipients"]), 2)
            self.assertFalse(graph_versand.mail_senden_als("horst@friondo.de", "", "B", "x")[0])
        # Fehler → (False, Grund, "")
        with self.anwendung(graph=mock.Mock(side_effect=RuntimeError("Postfach gesperrt"))):
            ok, fehler, konv = graph_versand.mail_senden_als("horst@friondo.de", "k@test.invalid", "B", "<p>x</p>")
            self.assertEqual((ok, konv), (False, ""))
            self.assertIn("Versand aus horst@friondo.de fehlgeschlagen", fehler)

    def test_delegiert_nur_eigenes_konto(self):
        self.modus_setzen("delegiert")
        with mock.patch.object(graph_versand, "delegiertes_konto", return_value="ida@friondo.de"), \
                mock.patch.object(graph_versand, "_graph_aufruf", side_effect=AssertionError("kein Graph")), \
                mock.patch.object(graph_versand, "_token", return_value="tok"):
            ok, fehler, konv = graph_versand.mail_senden_als("horst@friondo.de", "k@test.invalid", "B", "<p>x</p>")
            self.assertEqual((ok, konv), (False, ""))
            self.assertTrue(fehler.startswith("Nur im Modus Anwendung"))
        aufrufe = []
        with mock.patch.object(graph_versand, "delegiertes_konto", return_value="ida@friondo.de"), \
                mock.patch.object(graph_versand, "_token", return_value="tok"), \
                mock.patch.object(graph_versand, "_graph_aufruf",
                                  side_effect=lambda m, p, t, d=None, timeout=60: aufrufe.append(p) or {"id": "m", "conversationId": "c"}):
            for postfach in ("", "IDA@friondo.de"):
                ok, fehler, konv = graph_versand.mail_senden_als(postfach, "k@test.invalid", "B", "<p>x</p>")
                self.assertTrue(ok, fehler)
                self.assertEqual(konv, "c")
        self.assertEqual(aufrufe, ["/me/messages", "/me/messages/m/send"] * 2)


# --- Go-live-Punkt, /health, Betriebs-Kachel ---------------------------------------------

class GoLiveUndHealth(Basis):
    def test_golive_zwoelf_punkte_und_graph_punkt(self):
        punkte = golive.pruefen(self.s)
        # v36 (PLAN_V22 Phase 188): 13 Punkte – Punkt 13 „Angebots-PDF: Browser-Druck grün“ (A3);
        # der Graph-Punkt wird deshalb über seinen Titel gesucht
        self.assertEqual(len(punkte), 13)
        graph = next(p for p in punkte if p.titel == "Graph als Anwendung verbunden")
        self.assertEqual(graph.link, "/versand")
        self.modus_setzen("delegiert")
        with contextlib.ExitStack() as stapel:
            for p in anwendung_mocks():
                stapel.enter_context(p)
            punkt = golive.graph_punkt(self.s)
            self.assertFalse(punkt.ok)
            self.assertIn("Delegiert", punkt.detail)
            self.modus_setzen("anwendung")
            in_90 = date.today() + timedelta(days=90)
            with mock.patch.object(config, "GRAPH_GEHEIMNIS_ABLAUF", in_90.isoformat()):
                punkt = golive.graph_punkt(self.s)
                self.assertTrue(punkt.ok, punkt.detail)
                self.assertIn(in_90.strftime("%d.%m.%Y"), punkt.detail)
                self.assertIn("noch 90 Tage", punkt.detail)
            in_10 = date.today() + timedelta(days=10)
            with mock.patch.object(config, "GRAPH_GEHEIMNIS_ABLAUF", in_10.isoformat()):
                punkt = golive.graph_punkt(self.s)
                self.assertFalse(punkt.ok)
                self.assertIn(in_10.strftime("%d.%m.%Y"), punkt.detail)
                self.assertIn("erneuern", punkt.detail)
            with mock.patch.object(config, "GRAPH_GEHEIMNIS_ABLAUF", ""):
                punkt = golive.graph_punkt(self.s)
                self.assertTrue(punkt.ok)
                self.assertIn("nicht hinterlegt", punkt.detail)
        # Einstellung anwendung, aber Geheimnis aus der .env entfernt → rot
        with mock.patch.object(config, "GRAPH_CLIENT_SECRET", ""), mock.patch.object(config, "GRAPH_ZERTIFIKAT_PFAD", ""):
            self.assertFalse(golive.graph_punkt(self.s).ok)

    def test_health_warnung_und_feld_graph_modus(self):
        in_10 = date.today() + timedelta(days=10)
        with mock.patch.object(config, "GRAPH_GEHEIMNIS_ABLAUF", in_10.isoformat()):
            daten = betrieb.health()
            self.assertIn("Graph-Geheimnis läuft in 10 Tagen ab", daten["gruende"])
            self.assertEqual(daten["status"], "warn")
            self.assertEqual(daten["graph_geheimnis_tage"], 10)
            self.assertIn(daten["graph_modus"], ("anwendung", "delegiert"))
            r = self.client.get("/health")
            self.assertIn(r.status_code, (200, 503))
            self.assertEqual(r.json()["graph_geheimnis_tage"], 10)
            self.assertIn("graph_modus", r.json())
            self.assertIn("Graph-Geheimnis läuft in 10 Tagen ab", r.json()["gruende"])
        with mock.patch.object(config, "GRAPH_GEHEIMNIS_ABLAUF", (date.today() + timedelta(days=90)).isoformat()):
            self.assertFalse([g for g in betrieb.health()["gruende"] if "Graph-Geheimnis" in g])
        with mock.patch.object(config, "GRAPH_GEHEIMNIS_ABLAUF", (date.today() - timedelta(days=3)).isoformat()):
            self.assertIn("Graph-Geheimnis ist seit 3 Tagen abgelaufen", betrieb.health()["gruende"])
        with mock.patch.object(config, "GRAPH_GEHEIMNIS_ABLAUF", "kein-datum"):
            self.assertIsNone(graph_versand.geheimnis_ablauf_tage())
            self.assertEqual(graph_versand.geheimnis_warnung(), "")

    def test_betriebsseite_kachel(self):
        with mock.patch.object(config, "GRAPH_GEHEIMNIS_ABLAUF", (date.today() + timedelta(days=10)).isoformat()):
            html = self.client.get("/parametrierung/betrieb").text
        self.assertIn('id="kachel-graph"', html)
        self.assertIn("Graph-Geheimnis läuft in 10 Tagen ab", html)
        self.assertIn('href="/versand"', html)


# --- Phase 175: {vertriebler_block} ohne Infotext -----------------------------------------

class VertrieblerBlockOhneInfotext(Basis):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.horst = benutzer_anlegen(cls.s, "Horst Infotext", email="v33g.horst.info@test.invalid",
                                     telefon="0203 111", vorname="Horst",
                                     infotext="Ich berate seit 2015 Familien in Duisburg.")
        lead_mail.BENUTZERBILDER_ORDNER.mkdir(parents=True, exist_ok=True)
        lead_mail.benutzerbild_speichern(cls.horst, PNG, ".png")
        cls.s.commit()
        cls.kunde = Kunde(anrede="Frau", vorname="Erika", nachname=f"{PRAEFIX}-Termin", strasse="Teststraße 1",
                          plz="47139", ort="Duisburg", email="v33g.erika@test.invalid", interesse="WP")
        cls.s.add(cls.kunde)
        cls.s.flush()
        cls.vorgang = Vorgang(kunde_id=cls.kunde.id, ad_id=cls.horst.id, lead_phase="qualifiziert", demo=True)
        cls.s.add(cls.vorgang)
        cls.s.flush()
        beginn = datetime.now().replace(hour=10, minute=0, second=0, microsecond=0) + timedelta(days=3)
        while beginn.weekday() >= 5:
            beginn += timedelta(days=1)
        cls.termin = VotTermin(vorgang_id=cls.vorgang.id, ad_id=cls.horst.id, beginn=beginn,
                               ende=beginn + timedelta(minutes=90), adresse="Teststraße 1, 47139 Duisburg",
                               status="geplant", quelle="manuell", typ="vot", demo=True)
        cls.s.add(cls.termin)
        cls.s.commit()

    def test_block_nur_bild_name_telefon_email(self):
        person = self.s.get(Benutzer, self.horst.id)
        self.assertTrue(person.infotext)   # alter Infotext steht noch in der DB (Spalte bleibt)
        block = lead_mail.vertriebler_block_html(person)
        for teil in (person.name, "0203 111", "v33g.horst.info@test.invalid", f"cid:{lead_mail.CID_PRAEFIX}{person.id}"):
            self.assertIn(teil, block)
        self.assertNotIn("Ich berate seit 2015", block)
        text = lead_mail.vertriebler_block_text(person)
        self.assertIn("Telefon: 0203 111", text)
        self.assertNotIn("Ich berate seit 2015", text)

    def test_terminbestaetigung_ohne_infotext(self):
        betreff, html, fehlende = lead_mail.vorlage_rendern(self.s, "terminbestaetigung", self.vorgang, self.termin)
        self.assertTrue(betreff)
        self.assertEqual(fehlende, [])
        self.assertIn(self.horst.name, html)
        self.assertIn("0203 111", html)
        self.assertNotIn("Ich berate seit 2015", html)
        # Vorlagen-Vorschau (Editor): Demo-Lead mit dem Block des Vertrieblers, ohne Infotext
        key = lead_mail.vertriebler_key(self.horst.id)
        betreff, html, _ = lead_mail.vorlage_rendern(
            self.s, key, self.vorgang, self.termin, vorschau=True,
            text_vorgabe=("Termin {termin_datum}", "{briefanrede},\n\n{vertriebler_block}\n\nGruß"))
        self.assertIn(f"/lead-management/benutzer/{self.horst.id}/bild", html)
        self.assertNotIn("Ich berate seit 2015", html)
        r = self.client.post("/lead-management/vorlagen/vorschau",
                             json={"vorlage": key, "betreff": "B {termin_datum}",
                                   "text": "{briefanrede},\n\n{vertriebler_block}\n\nGruß"})
        self.assertEqual(r.status_code, 200, r.text[:200])
        daten = r.json()
        self.assertTrue(daten.get("ok"))
        self.assertIn(self.horst.name, daten["html"])
        self.assertNotIn("Ich berate seit 2015", daten["html"])
        self.assertNotIn("Ich berate seit 2015", json.dumps(daten, ensure_ascii=False))


if __name__ == "__main__":
    unittest.main()
