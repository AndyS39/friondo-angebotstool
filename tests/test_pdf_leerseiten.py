# Regressionstest für den Leerseiten-Bug (Phase 26): endete eine Position
# näher als eine Zeilenhöhe an der Umbruchgrenze, erzeugte die Übertrag-Zeile
# per Auto-Umbruch eine Seite und das folgende add_page() eine (fast) leere.
import datetime
import tempfile
import unittest
from pathlib import Path

import pypdf

from app import pdf_export
from app.models import Angebot, AngebotsPosition, Kunde


def _test_angebot(filler_zeilen: int) -> Angebot:
    angebot = Angebot(nummer=f"LEER-{filler_zeilen:02d}")
    angebot.datum = datetime.date(2026, 8, 14)
    angebot.rabatt_cent = 0
    angebot.rabatt_prozent = None
    text = ("Zeile Fülltext für den Test.\n" * filler_zeilen).strip() or "x"
    positionen = [AngebotsPosition(sort=1, bezeichnung="Füllposition",
                                   beschreibung=text, menge=1, einheit="psl.",
                                   e_preis_cent=10000, ep_flag=False, gruppe="")]
    for i in range(2, 30):
        positionen.append(AngebotsPosition(
            sort=i, bezeichnung=f"Position {i}",
            beschreibung="Beschreibungstext mit etwas Inhalt.\nZweite Zeile.",
            menge=1, einheit="Stck", e_preis_cent=25000, ep_flag=False,
            gruppe="Gruppe B" if i == 15 else ""))
    angebot.positionen = positionen
    return angebot


class TestLeerseiten(unittest.TestCase):
    def test_keine_fast_leeren_seiten(self):
        kunde = Kunde(anrede="Frau", vorname="Erika", nachname="Beispiel",
                      strasse="Beispielweg 2", plz="47441", ort="Moers")
        with tempfile.TemporaryDirectory() as ordner:
            # Baseline: Folgeseite nur mit Kopf- und Fußzeile
            basis = pdf_export.AngebotsPdf("BASIS")
            basis.add_page()
            basis.add_page()
            basis_pfad = Path(ordner) / "basis.pdf"
            basis.output(str(basis_pfad))
            basis_text = pypdf.PdfReader(str(basis_pfad)).pages[1].extract_text() or ""
            schwelle = len(basis_text.strip()) + 40

            # Vor dem Fix erzeugten u. a. 0, 6 und 43 Füllzeilen leere Seiten
            for filler in (0, 6, 9, 43):
                angebot = _test_angebot(filler)
                ziel = Path(ordner) / f"{angebot.nummer}.pdf"
                pdf_export.erzeuge_pdf(angebot, kunde, kfw_ergebnis=None,
                                       mit_vollmacht=False, ziel=ziel)
                leser = pypdf.PdfReader(str(ziel))
                for nr, seite in enumerate(leser.pages, 1):
                    text = (seite.extract_text() or "").strip()
                    if nr > 1:
                        self.assertGreaterEqual(
                            len(text), schwelle,
                            f"{angebot.nummer}: Seite {nr} ist fast leer "
                            f"({len(text)} Zeichen)")


if __name__ == "__main__":
    unittest.main()
