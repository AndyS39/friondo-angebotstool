# Entwurf-Erstellung (Phase 31) mit gemocktem Graph: Absender „Senden als“,
# CC/BCC, Betreff/Text aus Vorlage, Anhänge, conversationId.
import datetime
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from app import graph_versand
from app.models import Angebot, Kunde


class TestEntwurfPayload(unittest.TestCase):
    def test_entwurf_mit_absender_cc_bcc(self):
        kunde = Kunde(anrede="Frau", vorname="Erika", nachname="Beispiel",
                      email="erika@beispiel.de")
        angebot = Angebot(nummer="AN-C-260099", datum=datetime.datetime(2026, 8, 1))
        aufrufe = []

        def fake_graph(methode, pfad, token, daten=None):
            aufrufe.append((methode, pfad, daten))
            if pfad == "/me/messages":
                return {"id": "msg-1", "webLink": "https://outlook/x",
                        "conversationId": "konv-99"}
            return {}

        with tempfile.TemporaryDirectory() as ordner:
            pdf = Path(ordner) / "AN-C-260099.pdf"
            pdf.write_bytes(b"%PDF-1.4 test")
            with mock.patch.object(graph_versand, "_token", return_value="tok"), \
                    mock.patch.object(graph_versand, "_graph_aufruf", side_effect=fake_graph):
                erfolg, meldung, weblink, konv = graph_versand.entwurf_erstellen(
                    kunde, angebot, pdf, "Betreff X", "Text Y",
                    cc=["rene@friondo.de"], bcc=["info@friondo.de"],
                    absender="angebot@friondo.de")
        self.assertTrue(erfolg, meldung)
        self.assertEqual((weblink, konv), ("https://outlook/x", "konv-99"))
        methode, pfad, nachricht = aufrufe[0]
        self.assertEqual((methode, pfad), ("POST", "/me/messages"))
        self.assertEqual(nachricht["subject"], "Betreff X")
        self.assertEqual(nachricht["body"]["content"], "Text Y")
        self.assertEqual(nachricht["from"]["emailAddress"]["address"], "angebot@friondo.de")
        self.assertEqual(nachricht["toRecipients"][0]["emailAddress"]["address"], "erika@beispiel.de")
        self.assertEqual(nachricht["ccRecipients"][0]["emailAddress"]["address"], "rene@friondo.de")
        self.assertEqual(nachricht["bccRecipients"][0]["emailAddress"]["address"], "info@friondo.de")
        # Anhang folgt als zweiter Aufruf
        self.assertEqual(aufrufe[1][1], "/me/messages/msg-1/attachments")
        self.assertEqual(aufrufe[1][2]["name"], "AN-C-260099.pdf")

    def test_ohne_cc_kein_feld(self):
        kunde = Kunde(email="k@x.de")
        angebot = Angebot(nummer="AN-C-1", datum=datetime.datetime(2026, 8, 1))
        aufrufe = []
        with tempfile.TemporaryDirectory() as ordner:
            pdf = Path(ordner) / "a.pdf"; pdf.write_bytes(b"x")
            with mock.patch.object(graph_versand, "_token", return_value="tok"), \
                    mock.patch.object(graph_versand, "_graph_aufruf",
                                      side_effect=lambda m, p, t, d=None: (aufrufe.append(d), {"id": "1"})[1]):
                graph_versand.entwurf_erstellen(kunde, angebot, pdf, "B", "T", cc=[], bcc=[], absender="")
        self.assertNotIn("ccRecipients", aufrufe[0])
        self.assertNotIn("bccRecipients", aufrufe[0])
        self.assertNotIn("from", aufrufe[0])

    def test_ohne_kunden_email(self):
        erfolg, meldung, _, _ = graph_versand.entwurf_erstellen(
            Kunde(email=""), Angebot(nummer="AN-C-1"), Path("x.pdf"), "B", "T")
        self.assertFalse(erfolg)
        self.assertIn("keine E-Mail-Adresse", meldung)


if __name__ == "__main__":
    unittest.main()
