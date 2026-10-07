# Hotfix 06.10.2026 (Verbindungspool) – Teil Hintergrundläufe und Mail-/Graph-
# Aufrufe: während eines Netzaufrufs (Graph, msal-Token, monday-GraphQL) hält
# keine Sitzung eine Pool-Verbindung. Die Netzaufrufe sind gemockt und messen
# app.db.engine.pool.checkedout() im Moment des Aufrufs – erwartet wird 0.
# Läuft gegen die Entwicklungs-DB, aber nur lesend: transiente Objekte, die
# Testsession ist vor jeder Messung entlastet (verbindung_freigeben speichert
# also nichts), Rollback nach jedem Aufruf, keine Testreste. Kein echter
# Netzzugriff. Schleifen der Hintergrundläufe werden nur gemessen, wenn die
# Dev-DB passende Zeilen hat – sonst endet der Test als „übersprungen“, nie
# vakuum-grün (die datenunabhängigen Prüfungen laufen davor).
import contextlib
import types
import unittest
from datetime import datetime
from unittest import mock

from app import (benachrichtigungen, db, golive, graph_versand, lead_mail,
                 lead_parser, leadmanagement, mail_sync, monday_sync,
                 outlook_kalender, sub_mail, terminmail)
from app.db import SessionLocal, init_db
from app.models import (Angebot, Benutzer, MondayQuelle, Projekt, ProjektSub,
                        ProjektTermin)


def belegt() -> int:
    """Aktuell aus dem Pool entnommene Verbindungen (prozessweit)."""
    return db.engine.pool.checkedout()


class Basis(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        init_db()
        cls.s = SessionLocal()

    @classmethod
    def tearDownClass(cls):
        cls.s.rollback()
        cls.s.close()

    def setUp(self):
        self.entlasten()

    def tearDown(self):
        self.s.rollback()

    def entlasten(self):
        """Testsession ohne anstehende Änderungen und ohne Verbindung."""
        self.s.rollback()
        db.verbindung_freigeben(self.s)
        self.assertEqual(belegt(), 0, "Vorbedingung: Pool frei")

    def belegen(self):
        """Lesezugriff → die Testsession hält eine Pool-Verbindung (wie ein
        Request-Handler vor dem Netzaufruf)."""
        self.s.query(Benutzer).first()
        self.assertGreaterEqual(belegt(), 1)

    @staticmethod
    def lesen(session):
        session.query(Benutzer).first()


class SitzungUebergeben(Basis):
    """Funktionen mit übergebener Session (Request-Handler, Scheduler)."""

    def test_benachrichtigungen_mail_senden_beide_versuche(self):
        messungen, protokoll = [], []

        def text_mail(empfaenger, betreff, text, absender=""):
            messungen.append((absender, belegt()))
            if len(messungen) == 1:
                return False, "Senden als verweigert (Test)"
            return True, ""

        def protokollieren(session, zeile):
            self.lesen(session)          # Protokollzeile → Verbindung wieder belegt
            protokoll.append(zeile)

        def absender(session):
            self.lesen(session)
            return "projektierung@test.local"     # ≠ Fallback → zweiter Versuch

        self.belegen()
        with mock.patch.object(graph_versand, "text_mail_senden", side_effect=text_mail), \
                mock.patch.object(benachrichtigungen, "_absender", side_effect=absender), \
                mock.patch.object(benachrichtigungen, "_protokollieren",
                                  side_effect=protokollieren):
            ok = benachrichtigungen.mail_senden(self.s, "x@test.local", "B", "T")
        self.assertTrue(ok)
        self.assertEqual([m[0] for m in messungen],
                         ["projektierung@test.local", benachrichtigungen.ABSENDER_FALLBACK])
        self.assertEqual([m[1] for m in messungen], [0, 0], messungen)
        self.assertEqual(len(protokoll), 1)

    def test_golive_testmail_senden(self):
        messungen = []

        def text_mail(*a, **k):
            messungen.append(belegt())
            return False, "Test"            # kein Erfolg → golive_testmail bleibt unberührt

        self.belegen()
        with mock.patch.object(graph_versand, "text_mail_senden", side_effect=text_mail):
            ok, _meldung = golive.testmail_senden(
                self.s, types.SimpleNamespace(email="x@test.local"))
        self.assertFalse(ok)
        self.assertEqual(messungen, [0])

    def test_lead_mail_graph_senden_mit_fallback(self):
        messungen = []

        def token():
            messungen.append(("token", belegt()))
            return "tok"

        def graph(methode, pfad, tok, daten=None):
            von = daten["message"]["from"]["emailAddress"]["address"]
            messungen.append((von, belegt()))
            if len(messungen) == 2:         # erster Versand scheitert → Fallback angebot@
                raise RuntimeError("Senden als verweigert (Test)")
            return {}

        def absender(session):
            self.lesen(session)
            return "leads@test.local"

        self.belegen()
        with mock.patch.object(graph_versand, "_token", side_effect=token), \
                mock.patch.object(graph_versand, "_graph_aufruf", side_effect=graph), \
                mock.patch.object(lead_mail, "_absender", side_effect=absender):
            ok, fehler = lead_mail._graph_senden(self.s, "x@test.local", "B", "<p>T</p>", None)
        self.assertTrue(ok, fehler)
        self.assertEqual([m[0] for m in messungen],
                         ["token", "leads@test.local", lead_mail.ABSENDER_FALLBACK])
        self.assertEqual([m[1] for m in messungen], [0, 0, 0], messungen)

    def test_lead_parser_postfach_abrufen_get_und_patch(self):
        messungen = []

        def parameter(session, name, standard=""):
            self.lesen(session)
            return "an" if name == "parser_modus" else "leads@test.local"

        def token():
            messungen.append(("token", belegt()))
            return "tok"

        def graph(methode, pfad, tok, daten=None):
            messungen.append((methode, belegt()))
            if methode == "GET":
                return {"value": [{"id": "pool-test-1", "subject": "Test",
                                   "from": {"emailAddress": {"address": "kunde@test.local"}},
                                   "body": {"content": "Test"}}]}
            return {}

        def verarbeiten(session, graph_id, absender, betreff, body, empfangen_am=None):
            self.lesen(session)          # DB-Arbeit je Mail → Verbindung wieder belegt
            return "bekannt"

        self.belegen()
        with mock.patch.object(leadmanagement, "parameter_holen", side_effect=parameter), \
                mock.patch.object(lead_parser, "mail_verarbeiten", side_effect=verarbeiten), \
                mock.patch.object(graph_versand, "_token", side_effect=token), \
                mock.patch.object(graph_versand, "_graph_aufruf", side_effect=graph):
            ergebnis = lead_parser.postfach_abrufen(self.s)
        self.assertNotIn("fehler", ergebnis)
        self.assertEqual([m[0] for m in messungen], ["token", "GET", "PATCH"])
        self.assertEqual([m[1] for m in messungen], [0, 0, 0], messungen)

    def test_monday_quelle_syncen(self):
        messungen = []

        def items(board_id, gruppen_titel):
            messungen.append((board_id, gruppen_titel, belegt()))
            return "Pool-Test", []

        quelle = MondayQuelle(board_id="pool-test", board_name="",
                              gruppen_titel="Terminiert", aktiv=True)      # transient
        self.belegen()
        with mock.patch.object(monday_sync, "_items_der_gruppe", side_effect=items), \
                mock.patch.object(monday_sync, "_api",
                                  side_effect=AssertionError("echter monday-Aufruf")):
            anzahl = monday_sync._quelle_syncen(self.s, quelle, {})
        self.assertEqual(anzahl, 0)
        self.assertEqual(messungen, [("pool-test", "Terminiert", 0)])
        self.assertNotIn(quelle, self.s)            # nichts gespeichert
        self.assertEqual(quelle.board_name, "Pool-Test")

    def test_outlook_event_senden_post_patch_und_loeschen(self):
        messungen = []
        projekt = self.s.query(Projekt).order_by(Projekt.id).first()
        termin = ProjektTermin(typ="montage", beginn=datetime(2026, 10, 6, 8, 0), ende=None,
                               team_id=None, projekt_id=projekt.id if projekt else None,
                               gewerk_id=None, outlook_event_id="")            # transient

        def ziel(session, _termin):
            self.lesen(session)          # Team/Parameter → Verbindung belegt
            return "kalender@test.local", [], ""

        def token():
            messungen.append(("token", belegt()))
            return "tok"

        def graph(methode, pfad, tok, daten=None):
            messungen.append((methode, belegt()))
            return {"id": "ev-pool-test"}

        patches = [mock.patch.object(outlook_kalender, "_kalender_ziel", side_effect=ziel),
                   mock.patch.object(graph_versand, "_token", side_effect=token),
                   mock.patch.object(graph_versand, "_graph_aufruf", side_effect=graph)]
        if projekt is None:                 # Dev-DB ohne Projekt: Ereignisdaten nur lesen
            def daten(session, _termin, _kategorien):
                self.lesen(session)
                return {"subject": "Test"}
            patches.append(mock.patch.object(outlook_kalender, "_event_daten",
                                             side_effect=daten))
        self.belegen()
        with contextlib.ExitStack() as stapel:
            for patch in patches:
                stapel.enter_context(patch)
            ok, fehler = outlook_kalender.event_senden(self.s, termin)        # POST
            ok2, fehler2 = outlook_kalender.event_senden(self.s, termin)      # PATCH
            geloescht = outlook_kalender.event_loeschen(self.s, termin)       # DELETE
        self.assertEqual((ok, fehler, ok2, fehler2, geloescht), (True, "", True, "", True))
        self.assertEqual([m[0] for m in messungen],
                         ["token", "POST", "token", "PATCH", "token", "DELETE"])
        self.assertEqual([m[1] for m in messungen], [0] * 6, messungen)
        self.assertNotIn(termin, self.s)            # transient geblieben
        self.assertEqual(termin.outlook_event_id, "")


class EigeneSitzung(Basis):
    """Hintergrundläufe mit eigener SessionLocal()-Session: Token und Konto
    vor der Sitzung, Freigabe vor JEDEM Graph-Abruf der Schleife."""

    def mocks(self, konto, abrufe):
        def token():
            konto.append(("token", belegt()))
            return "tok"

        def angemeldet():
            konto.append(("konto", belegt()))
            return "t@test.local"

        def nachrichten(_token, _schluessel, postfach=""):
            abrufe.append(belegt())
            return []
        return [mock.patch.object(graph_versand, "_token", side_effect=token),
                mock.patch.object(graph_versand, "angemeldeter_benutzer",
                                  side_effect=angemeldet),
                mock.patch.object(mail_sync, "nachrichten_je_konversation",
                                  side_effect=nachrichten),
                mock.patch.object(mail_sync, "nachrichten_je_betreff",
                                  side_effect=nachrichten)]

    def lauf(self, funktion, patches):
        self.entlasten()
        with contextlib.ExitStack() as stapel:
            for patch in patches:
                stapel.enter_context(patch)
            return funktion()

    def test_mail_sync_sync(self):
        # v27-Nachtrag: der Abgleich betrachtet nur „Versand vorbereitet“/„Versendet“
        # der letzten mail_sync.ABGLEICH_TAGE Tage
        from datetime import datetime, timedelta
        from sqlalchemy import and_, or_
        grenze = datetime.now() - timedelta(days=mail_sync.ABGLEICH_TAGE)
        anzahl = (self.s.query(Angebot)
                  .filter(Angebot.status.in_(["Versand vorbereitet", "Versendet"]),
                          Angebot.archiviert.is_(False),
                          or_(Angebot.versendet_am >= grenze,
                              and_(Angebot.versendet_am.is_(None),
                                   Angebot.angelegt_am >= grenze))).count())
        konto, abrufe = [], []
        neu = self.lauf(mail_sync.sync, self.mocks(konto, abrufe) + [
            mock.patch.object(mail_sync, "_protokoll_sichern"),   # kein Schreiben
            mock.patch.object(mail_sync, "_nach_versand")])
        self.assertEqual(neu, 0)
        self.assertEqual(konto, [("token", 0), ("konto", 0)])   # vor der Sitzung
        self.assertEqual(abrufe, [0] * anzahl, abrufe)
        if not anzahl:
            self.skipTest("Dev-DB ohne offene Angebote – Schleife nicht gemessen")

    def test_terminmail_antworten_abgleichen(self):
        anzahl = (self.s.query(ProjektTermin)
                  .filter(ProjektTermin.graph_conversation_id.isnot(None),
                          ProjektTermin.kunde_bestaetigt.is_(False)).count())
        konto, abrufe = [], []
        neu = self.lauf(terminmail.antworten_abgleichen, self.mocks(konto, abrufe))
        self.assertEqual(neu, 0)
        self.assertEqual(konto, [("token", 0), ("konto", 0)])   # Konto VOR SessionLocal()
        self.assertEqual(abrufe, [0] * anzahl, abrufe)
        if not anzahl:
            self.skipTest("Dev-DB ohne offene Terminmail-Konversationen – Schleife nicht gemessen")

    def test_sub_mail_antworten_abgleichen(self):
        anzahl = (self.s.query(ProjektSub)
                  .filter(ProjektSub.graph_conversation_id.isnot(None),
                          ProjektSub.status.in_(["angefragt", "beauftragt"])).count())
        konto, abrufe = [], []
        neu = self.lauf(sub_mail.antworten_abgleichen, self.mocks(konto, abrufe))
        self.assertEqual(neu, 0)
        self.assertEqual(konto, [("token", 0), ("konto", 0)])   # Konto VOR SessionLocal()
        self.assertEqual(abrufe, [0] * anzahl, abrufe)
        if not anzahl:
            self.skipTest("Dev-DB ohne offene Sub-Konversationen – Schleife nicht gemessen")

    def test_outlook_ruecklesen(self):
        anzahl = (self.s.query(ProjektTermin)
                  .filter(ProjektTermin.outlook_event_id != "",
                          ProjektTermin.beginn.isnot(None)).count())
        konto, abrufe = [], []

        def ziel(session, _termin):
            self.lesen(session)
            return "kalender@test.local", [], ""

        def graph(methode, pfad, tok, daten=None):
            abrufe.append((methode, belegt()))
            return {}                          # kein start → keine Änderung
        geaendert = self.lauf(outlook_kalender.ruecklesen, self.mocks(konto, []) + [
            mock.patch.object(outlook_kalender, "_kalender_ziel", side_effect=ziel),
            mock.patch.object(graph_versand, "_graph_aufruf", side_effect=graph)])
        self.assertEqual(geaendert, 0)
        self.assertEqual(konto, [("token", 0)])                  # Token vor der Sitzung
        self.assertEqual(abrufe, [("GET", 0)] * anzahl, abrufe)
        if not anzahl:
            self.skipTest("Dev-DB ohne Outlook-Termine – Schleife nicht gemessen")


if __name__ == "__main__":
    unittest.main()
