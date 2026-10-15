# v34 (PLAN_V21 Phase 180): Alternativ-Kennzeichen „in anderem Angebot enthalten“ (v10) klar
# abgegrenzt. PDF: farbig hinterlegter Hinweiskasten vor der ersten Alternativ-Position eines
# Blocks („Die folgenden Positionen sind bereits in Ihrem Angebot <Nr> (<Sparte>) enthalten und
# werden dort berechnet.“), G-Preis-Spalte „im PV-Angebot“ statt „Altern.“, Einzelpreis bleibt,
# Zeile grau hinterlegt, v10-Vermerk unter der Position bleibt. Editor: Zeile mit farbigem
# linken Balken (Token --alternativ) und Badge „Alternativ · im PV-Angebot AN-C-…“ mit Link,
# EP-Badge unverändert; Hinweis „Geschwister-Angebot nicht mehr gültig“. Lieferschein ohne
# Alternativ-Positionen. Abnahme-PDF docs/wallbox/abnahme-alternativ-<Nr>.pdf (Demo-Kunde).
# Läuft gegen DB_PFAD_OVERRIDE (Kopie), räumt eigene Daten auf.
import unittest
import warnings
from pathlib import Path
from unittest import mock

warnings.filterwarnings("ignore")

from app import elektro_pv, lieferschein_pdf, pdf_export
from app.models import AngebotsPosition
from tests.v34_e_basis import (PROJEKT, WP_ELEKTRO, WP_ELEKTRO_EP, WP_PAKET, Basis, pdf_text)


class Parsen(unittest.TestCase):
    def test_ziel_parsen(self):
        self.assertEqual(elektro_pv.ziel_parsen("PV-Angebot AN-C-261021"), ("PV", "AN-C-261021"))
        self.assertEqual(elektro_pv.ziel_parsen("WP-Angebot AN-C-261021.2"), ("WP", "AN-C-261021.2"))
        self.assertEqual(elektro_pv.ziel_parsen("PV-Angebot"), ("PV", ""))         # Z26 (v13)
        self.assertEqual(elektro_pv.ziel_parsen("Parallel-Angebot"), ("", ""))
        self.assertEqual(elektro_pv.ziel_parsen("irgendein Text"), ("", ""))
        self.assertEqual(elektro_pv.ziel_parsen(""), ("", ""))
        self.assertEqual(elektro_pv.ziel_parsen(None), ("", ""))

    def test_label_und_hinweis(self):
        self.assertEqual(elektro_pv.alternativ_label("PV"), "im PV-Angebot")
        self.assertEqual(elektro_pv.alternativ_label("WP"), "im WP-Angebot")
        self.assertEqual(elektro_pv.alternativ_label(""), "in anderem Angebot")
        self.assertEqual(elektro_pv.hinweis_text("PV", "AN-C-261021"),
                         "Die folgenden Positionen sind bereits in Ihrem Angebot AN-C-261021 (PV) "
                         "enthalten und werden dort berechnet.")
        self.assertEqual(elektro_pv.hinweis_text("PV", ""),
                         "Die folgenden Positionen sind bereits in Ihrem PV-Angebot enthalten und "
                         "werden dort berechnet.")
        self.assertIn("einem anderen Angebot", elektro_pv.hinweis_text("", ""))


class PdfDarstellung(Basis):
    EMAIL = "v34e-alternativ@test.local"
    NACHNAME = "V34E Alternativ"
    AD_NAME = "V34E Alternativ-AD"

    def wp_mit_alternativ(self, ziel_text: str | None = None):
        pv = self.pv_entwurf()
        wp = self.wp_entwurf()
        for p in wp.positionen:
            if p.pos_nr in ("011", "104"):
                p.alternativ = True
                p.alternativ_zu = ziel_text if ziel_text is not None else f"PV-Angebot {pv.nummer}"
        self.s.commit()
        return wp, pv

    def test_pdf_kasten_label_und_summe(self):
        wp, pv = self.wp_mit_alternativ()
        original = pdf_export._alternativ_kasten
        with mock.patch.object(pdf_export, "_alternativ_kasten", side_effect=original) as spy:
            pfad = pdf_export.pdf_fuer_angebot(self.s, wp)
        self.assertEqual(spy.call_count, 1)                          # ein Kasten je Block
        text = pdf_text(pfad)
        flach = " ".join(text.split())
        self.assertIn(f"Die folgenden Positionen sind bereits in Ihrem Angebot {pv.nummer} (PV) "
                      "enthalten und werden dort berechnet.", flach)
        self.assertEqual(text.count("im PV-Angebot"), 2)
        self.assertNotIn("Altern.", text)
        self.assertIn("1.500,00", text)                              # Einzelpreis bleibt sichtbar
        self.assertIn("900,00", text)
        self.assertIn("EP.", text)                                   # Eventualposition unverändert
        # v10-Vermerk unter der Position bleibt
        self.assertIn(f"Diese Position ist im parallel vorliegenden PV-Angebot {pv.nummer} enthalten",
                      flach)
        # Netto ohne Alternativ-Positionen (10.000,00 statt 12.400,00)
        self.assertIn("10.000,00", text)
        self.assertNotIn("12.400,00", text)
        self.assertEqual(wp.summen()["netto"], 1_000_000)

    def test_pdf_generisch_ohne_nummer(self):
        # Entscheidung Orchestrator 15.10.2026 (Rückfrage 3): ohne erkennbare Sparte steht
        # „anderes Angebot“ (kleinere Schrift) in der G-Preis-Spalte statt „Altern.“
        wp, _pv = self.wp_mit_alternativ("Parallel-Angebot")
        text = pdf_text(pdf_export.pdf_fuer_angebot(self.s, wp))
        flach = " ".join(text.split())
        self.assertIn("bereits in einem anderen Angebot zu diesem Vorgang enthalten", flach)
        self.assertEqual(text.count("anderes Angebot"), 2)
        self.assertNotIn("Altern.", text)
        wp2, _pv = self.wp_mit_alternativ("PV-Angebot")             # Z26-Form ohne Nummer
        text = pdf_text(pdf_export.pdf_fuer_angebot(self.s, wp2))
        self.assertIn("bereits in Ihrem PV-Angebot enthalten", " ".join(text.split()))
        self.assertEqual(text.count("im PV-Angebot"), 2)

    def test_kasten_je_block(self):
        wp, pv = self.wp_mit_alternativ()
        # zusätzliche Alternativ-Position in Block 1 → zweiter Kasten
        wp.positionen.append(AngebotsPosition(
            sort=9, block_nr=1, gruppe=WP_PAKET["gruppe"], pos_nr="067",
            bezeichnung="Warmwasser-Zubehör", beschreibung="", menge=1.0, einheit="Stück",
            e_preis_cent=61_606, ek_cent=30_000, alternativ=True,
            alternativ_zu=f"PV-Angebot {pv.nummer}"))
        self.s.commit()
        original = pdf_export._alternativ_kasten
        with mock.patch.object(pdf_export, "_alternativ_kasten", side_effect=original) as spy:
            pdf_export.pdf_fuer_angebot(self.s, self.neu(wp.id))
        self.assertEqual(spy.call_count, 2)

    def test_gpreis_label_passt_in_spalte(self):
        pdf = pdf_export.AngebotsPdf("AN-C-TEST")
        pdf.add_page()
        for label in ("im PV-Angebot", "im DMS-Angebot", elektro_pv.PDF_LABEL_GENERISCH):
            groesse = pdf_export._gpreis_schrift(pdf, label)
            # Schrift wurde so verkleinert, dass das Wort in die Spalte passt
            self.assertLessEqual(pdf.get_string_width(label), pdf_export.SPALTEN["g_preis"] - 0.8)
            self.assertGreaterEqual(groesse, 5.5)
        self.assertEqual(pdf_export._gpreis_schrift(pdf, "im PV-Angebot"), 8.0)
        self.assertEqual(elektro_pv.pdf_label(""), "anderes Angebot")
        self.assertEqual(elektro_pv.pdf_label("PV"), "im PV-Angebot")
        self.assertLess(pdf_export._gpreis_schrift(pdf, "anderes Angebot"), 8.0)   # kleinere Schrift
        pdf.set_xy(100, 100)
        pdf_export._gpreis_label(pdf, "im DMS-Angebot", 3.7)
        self.assertEqual(pdf.font_size_pt, 8)                       # Schrift danach zurückgesetzt


class EditorDarstellung(Basis):
    EMAIL = "v34e-alternativ-editor@test.local"
    NACHNAME = "V34E Alternativ-Editor"
    AD_NAME = "V34E Alternativ-Editor-AD"

    def test_badge_balken_link_und_ep(self):
        pv = self.pv_entwurf()
        wp = self.wp_entwurf()
        for p in wp.positionen:
            if p.pos_nr == "011":
                p.alternativ = True
                p.alternativ_zu = f"PV-Angebot {pv.nummer}"
        self.s.commit()
        html = self.client.get(f"/angebote/{wp.id}").text
        self.assertIn("angebot_v34.css", html)
        self.assertIn('class=" alternativ"', html)                  # Zeile mit linkem Balken (CSS)
        self.assertIn("Alternativ · im PV-Angebot", html)
        self.assertIn(f'href="/angebote/{pv.id}">{pv.nummer}</a>', html)
        self.assertIn('class="alternativ-gpreis"', html)
        self.assertNotIn(">Altern.<", html)
        self.assertIn("EP.", html)                                  # EP-Zelle unverändert
        self.assertNotIn("nicht mehr gültig", html)
        # CSS nutzt die neuen Tokens
        css = (PROJEKT / "app" / "static" / "angebot_v34.css").read_text(encoding="utf-8")
        self.assertIn("var(--alternativ)", css)
        self.assertIn("var(--alternativ-flaeche)", css)
        self.assertNotIn("#", css.split("*/", 1)[1])                 # keine Hex-Farben

    def test_geschwister_nicht_mehr_gueltig(self):
        pv = self.pv_entwurf()
        wp = self.wp_entwurf()
        for p in wp.positionen:
            if p.pos_nr == "104":
                p.alternativ = True
                p.alternativ_zu = f"PV-Angebot {pv.nummer}"
        pv.status = "Überholt"
        self.s.commit()
        html = self.client.get(f"/angebote/{wp.id}").text
        self.assertIn("Geschwister-Angebot nicht mehr gültig", html)
        self.assertIn("nicht mehr gültig</span>", html)
        self.assertIn("alternativ-badge ungueltig", html)
        info = elektro_pv.alternativ_info(self.s, self.neu(wp.id))
        self.assertEqual([i["gueltig"] for i in info.values()], [False])
        # Alternativ-Position zählt weiterhin nicht
        self.assertEqual(self.neu(wp.id).summen()["netto"], 1_000_000 + 150_000)

    def test_freitext_verknuepfung_gilt_als_gueltig(self):
        wp = self.wp_entwurf()
        wp.positionen[1].alternativ = True
        wp.positionen[1].alternativ_zu = "Parallel-Angebot"
        self.s.commit()
        info = elektro_pv.alternativ_info(self.s, self.neu(wp.id))
        self.assertEqual(list(info.values())[0]["label"], "in anderem Angebot")
        self.assertTrue(list(info.values())[0]["gueltig"])
        html = self.client.get(f"/angebote/{wp.id}").text
        self.assertIn("Alternativ · in anderem Angebot", html)
        self.assertNotIn("Geschwister-Angebot nicht mehr gültig", html)


class Lieferschein(Basis):
    EMAIL = "v34e-alternativ-ls@test.local"
    NACHNAME = "V34E Alternativ-LS"
    AD_NAME = "V34E Alternativ-LS-AD"

    def test_alternativ_bleibt_draussen(self):
        wp = self.angebot("WP", [WP_PAKET] + WP_ELEKTRO + [WP_ELEKTRO_EP], status="Angenommen")
        wp.positionen[1].alternativ = True
        wp.positionen[1].alternativ_zu = "PV-Angebot AN-C-999999"
        self.s.commit()
        nummern = [p.pos_nr for _n, p in lieferschein_pdf.lieferschein_positionen(self.neu(wp.id))]
        self.assertEqual(nummern, ["045", "104"])


class AbnahmePdf(unittest.TestCase):
    def test_abnahme_pdf_vorhanden(self):
        dateien = sorted((PROJEKT / "docs" / "wallbox").glob("abnahme-alternativ-AN-*.pdf"))
        self.assertTrue(dateien, "docs/wallbox/abnahme-alternativ-<Nr>.pdf fehlt "
                                 "(diagnose/v34/E_patches/abnahme_alternativ.py)")
        text = " ".join(pdf_text(dateien[-1]).split())
        self.assertIn("enthalten und werden dort berechnet.", text)
        self.assertIn("im PV-Angebot", text)
        self.assertIn("Muster", text)                                # Demo-Kunde, keine Kundendaten


if __name__ == "__main__":
    unittest.main()
