# Outlook-Signaturen + HTML-Versand (v6, Phase 42) – mit Dateisystem-Fixture
# und gemocktem Graph (kein echtes Token nötig).
import datetime
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from app import config, graph_versand, signaturen
from app.models import Angebot, Kunde

OUTLOOK_HTM = """<html><head><meta charset="windows-1252"></head><body>
<p>Mit freundlichen Grüßen</p>
<p><b>Dimitrios Chatzis</b><br>Technischer Innendienst</p>
<p><img width="120" src="Signatur-Dateien/image001.png"></p>
<p><img src="Signatur-Dateien/image002.jpg"> <img src="https://extern.de/logo.png"></p>
</body></html>"""


class TestSignaturen(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self._alt = config.DATA_ORDNER
        config.DATA_ORDNER = Path(self._tmp.name)

    def tearDown(self):
        config.DATA_ORDNER = self._alt
        self._tmp.cleanup()

    def _hochladen(self, benutzer_id=7):
        ok, meldung = signaturen.speichern(benutzer_id, [
            ("Signatur.htm", OUTLOOK_HTM.encode("windows-1252")),
            ("image001.png", b"PNG-DATEN"),
            ("image002.jpg", b"JPG-DATEN"),
        ])
        self.assertTrue(ok, meldung)

    def test_ohne_upload_standard_signatur(self):
        html, bilder = signaturen.fuer_versand(99)
        self.assertIn("Friondo GmbH", html)
        self.assertEqual(bilder, [])

    def test_upload_und_cid_umschreibung(self):
        self._hochladen()
        html, bilder = signaturen.fuer_versand(7)
        # Umlaute aus windows-1252 korrekt dekodiert, nur Body übernommen
        self.assertIn("Mit freundlichen Grüßen", html)
        self.assertNotIn("<html", html)
        # lokale Bilder → cid, externes Bild bleibt URL
        self.assertIn('src="cid:sig7-0"', html)
        self.assertIn('src="cid:sig7-1"', html)
        self.assertIn('src="https://extern.de/logo.png"', html)
        self.assertEqual([(c, p.name, m) for c, p, m in bilder],
                         [("sig7-0", "image001.png", "image/png"),
                          ("sig7-1", "image002.jpg", "image/jpeg")])

    def test_upload_verlangt_genau_eine_htm(self):
        ok, meldung = signaturen.speichern(7, [("bild.png", b"x")])
        self.assertFalse(ok)
        self.assertIn(".htm", meldung)

    def test_entfernen(self):
        self._hochladen()
        self.assertTrue(signaturen.vorhanden(7))
        signaturen.entfernen(7)
        self.assertFalse(signaturen.vorhanden(7))

    def test_html_entwurf_mit_inline_bildern(self):
        self._hochladen()
        html, bilder = signaturen.fuer_versand(7)
        kunde = Kunde(email="k@x.de")
        angebot = Angebot(nummer="AN-C-1", datum=datetime.datetime(2026, 8, 22))
        aufrufe = []

        def fake(methode, pfad, token, daten=None):
            aufrufe.append((pfad, daten))
            return {"id": "m1", "webLink": "w", "conversationId": "c"}

        with tempfile.TemporaryDirectory() as ordner:
            pdf = Path(ordner) / "a.pdf"; pdf.write_bytes(b"%PDF")
            with mock.patch.object(graph_versand, "_token", return_value="tok"), \
                    mock.patch.object(graph_versand, "_graph_aufruf", side_effect=fake):
                erfolg, *_ = graph_versand.entwurf_erstellen(
                    kunde, angebot, pdf, "Betreff", "<p>Haupttext</p>" + html,
                    inline_bilder=bilder)
        self.assertTrue(erfolg)
        nachricht = aufrufe[0][1]
        self.assertEqual(nachricht["body"]["contentType"], "html")   # v6: HTML-Mail
        self.assertIn("cid:sig7-0", nachricht["body"]["content"])
        inline = [d for _, d in aufrufe[1:] if d and d.get("isInline")]
        self.assertEqual([(d["contentId"], d["contentType"]) for d in inline],
                         [("sig7-0", "image/png"), ("sig7-1", "image/jpeg")])
        normal = [d for _, d in aufrufe[1:] if d and not d.get("isInline")]
        self.assertEqual([d["name"] for d in normal], ["a.pdf"])


if __name__ == "__main__":
    unittest.main()
