# Vollmacht-Seite (v5-Nachtrag): komplett auf EINER Seite (kein Waisenblock
# mit den Unterschriften) und automatisch vorbelegte Ankreuzfelder.
import datetime
import tempfile
import unittest
from pathlib import Path

import pypdf

from app import anhaenge, pdf_export
from app.models import Angebot, AngebotsPosition, Kunde


def _angebot(positionen_zusatz=(), protokoll="[]"):
    a = Angebot(nummer="AN-C-VOLLM", datum=datetime.datetime(2026, 8, 20))
    a.rabatt_cent = 0
    a.rabatt_prozent = None
    a.protokoll_json = protokoll
    a.positionen = [AngebotsPosition(sort=i, bezeichnung=f"Position {i}",
                                     beschreibung="Beschreibungstext.\nZweite Zeile.",
                                     menge=1, einheit="Stck", e_preis_cent=10000,
                                     ep_flag=False, gruppe="")
                    for i in range(1, 31)]           # langes Angebot → Vollmacht ist Folgeseite
    for nr in positionen_zusatz:
        a.positionen.append(AngebotsPosition(sort=90 + len(a.positionen), pos_nr=nr,
                                             bezeichnung=f"Pos {nr}", menge=1, einheit="Stck",
                                             e_preis_cent=1000, ep_flag=False, gruppe=""))
    return a


KUNDE = Kunde(anrede="Frau", vorname="Erika", nachname="Beispiel-Langenachname",
              strasse="Sehr lange Straße mit Hausnummer 123b", plz="47441",
              ort="Moers am Niederrhein", telefon="0203-123456", email="erika@beispiel.de")


def _vollmacht_seite(pfad):
    leser = pypdf.PdfReader(str(pfad))
    seiten = [(i, p.extract_text() or "") for i, p in enumerate(leser.pages, 1)]
    treffer = [(i, t) for i, t in seiten if "Vollmacht zur Beauftragung" in t]
    return leser, seiten, treffer


class TestVollmachtSeite(unittest.TestCase):
    def test_komplett_auf_einer_seite_kein_waisenblock(self):
        angebot = _angebot(positionen_zusatz=("016", "017"))
        with tempfile.TemporaryDirectory() as ordner:
            pfad = Path(ordner) / "v.pdf"
            pdf_export.erzeuge_pdf(angebot, KUNDE, kfw_ergebnis=None,
                                   mit_vollmacht=True, ziel=pfad)
            leser, seiten, treffer = _vollmacht_seite(pfad)
        self.assertEqual(len(treffer), 1)
        nr, text = treffer[0]
        # alles inkl. Ort/Datum + beider Unterschriften auf derselben Seite
        for teil in ("Bitte ankreuzen", "SEPA-Lastschriftmandat", "Ort, Datum",
                     "Unterschrift Vollmachtgeber", "Unterschrift Kontoinhaber"):
            self.assertIn(teil, text, teil)
        # keine Seite danach trägt einen Rest der Vollmacht
        self.assertEqual(nr, len(seiten), "Vollmacht muss die letzte Seite sein")
        for i, t in seiten:
            if i != nr:
                self.assertNotIn("Unterschrift Kontoinhaber", t)

    def test_kreuze_bleiben_leer(self):
        # v8: die automatische Vorbelegung entfällt – der Kunde kreuzt selbst an
        for zusatz in (("016", "017"), ("016",), ("017",)):
            with tempfile.TemporaryDirectory() as ordner:
                pfad = Path(ordner) / "v.pdf"
                pdf_export.erzeuge_pdf(_angebot(positionen_zusatz=zusatz), KUNDE,
                                       kfw_ergebnis=None, mit_vollmacht=True, ziel=pfad)
                _, _, treffer = _vollmacht_seite(pfad)
            self.assertIn("[  ] Messstellenbetreiber und [  ] Stromlieferant",
                          treffer[0][1], zusatz)
            self.assertIn("[  ] Anmeldung/Inbetriebnahme/Änderung/Erweiterung/Abmeldung",
                          treffer[0][1])
            self.assertNotIn("[X]", treffer[0][1])


if __name__ == "__main__":
    unittest.main()
