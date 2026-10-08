# v28 (PLAN_PROJ_V6 Phase 138, Agent P2): Formulare – Blatt „Formulare“ auf dem
# v28-Stand (Montagebericht 19 Felder ohne mb_beginn/mb_regie, Inbetriebnahme
# 5 Seiten / 31 Felder, Abnahme 9), Lader (wiederhol, gross, pflicht_wenn, „Logik
# prüfen“), Renderer/Speichern (Fotos mehrfach, Wiederholfeld), offene_pflicht,
# Restarbeiten aus Frage 10, PDF (multi_cell, Frage 7, Tabellen, Unterschriften).
import io
import json
import shutil
import unittest
import warnings
from pathlib import Path

warnings.filterwarnings("ignore")

import openpyxl
import pypdf

from app import montage_formulare, projektierung_logik
from app.models import Benutzer, GalerieDatei, Restarbeit
from tests.proj_v6_p2_basis import Basis, jpg_bytes, png_daten_url

TMP = Path(__file__).resolve().parent.parent / "diagnose" / "v28_patches" / "p2_test_tmp"


def pdf_text(daten: bytes) -> str:
    leser = pypdf.PdfReader(io.BytesIO(daten))
    return "\n".join((seite.extract_text() or "") for seite in leser.pages)


def feld(logik, formular, key):
    return next(f for f in logik.formulare[formular] if f.feld_key == key)


class Blatt(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.logik = projektierung_logik.einlesen()

    def test_blatt_laedt_ohne_fehler(self):
        self.assertEqual(self.logik.fehler, [])
        self.assertFalse([w for w in self.logik.warnungen if "Formular" in w], self.logik.warnungen)

    def test_inbetriebnahme_5_seiten_31_felder(self):
        seiten = self.logik.formular_seiten("inbetriebnahme")
        self.assertEqual(len(seiten), 5)
        self.assertEqual([s for s, _ in seiten],
                         ["Gerät", "Prüfungen", "Betriebswerte im stabilen Betrieb",
                          "Einstellungen", "Unterschriften"])
        self.assertEqual(len(self.logik.formulare["inbetriebnahme"]), 31)
        keys = [f.feld_key for f in self.logik.formulare["inbetriebnahme"]]
        for alt in ("ib_dichtheit", "ib_spuelung", "ib_rcd", "ib_hems", "ib_einweisung",
                    "ib_bemerkung", "ib_unterschrift_monteur"):
            self.assertNotIn(alt, keys)
        self.assertEqual(keys[:5], ["ib_sn_aussen", "ib_sn_innen", "ib_sn_puffer",
                                    "ib_sn_komponenten", "ib_kaeltemittel"])
        self.assertEqual(feld(self.logik, "inbetriebnahme", "ib_sn_komponenten").typ, "wiederhol")
        self.assertEqual(feld(self.logik, "inbetriebnahme", "ib_sn_komponenten").einzelfeld, "Seriennummer")
        self.assertTrue(feld(self.logik, "inbetriebnahme", "ib_f10").gross)
        self.assertEqual(feld(self.logik, "inbetriebnahme", "ib_f11_text").pflicht_wenn,
                         ("ib_f11", "≠", "Ja"))
        self.assertEqual(feld(self.logik, "inbetriebnahme", "ib_f11").optionen_liste(),
                         ["Ja", "Mit dokumentierten Einschränkungen", "Nein"])
        self.assertEqual(feld(self.logik, "inbetriebnahme", "ib_f07_kuehlen").optionen_liste(),
                         ["OK", "nicht OK", "nicht vorhanden"])
        pflicht = [f.feld_key for f in self.logik.formulare["inbetriebnahme"] if f.pflicht]
        for key in ("ib_f01", "ib_f02", "ib_f03", "ib_f04", "ib_f05", "ib_f06", "ib_f08", "ib_f09",
                    "ib_f10", "ib_f11", "ib_unterschrift_techniker", "ib_unterschrift_betreiber"):
            self.assertIn(key, pflicht)
        self.assertNotIn("ib_f11_text", pflicht)
        self.assertNotIn("ib_kaeltemittel", pflicht)

    def test_montagebericht_felder(self):
        keys = [f.feld_key for f in self.logik.formulare["montagebericht"]]
        self.assertEqual(len(keys), 19)
        for alt in ("mb_beginn", "mb_ende", "mb_nachbestellung", "mb_regie"):
            self.assertNotIn(alt, keys)
        self.assertIn("mb_bemerkung", keys)
        self.assertTrue(feld(self.logik, "montagebericht", "mb_bemerkung").gross)
        self.assertEqual(feld(self.logik, "montagebericht", "mb_bemerkung").seite,
                         "Abweichungen & Bemerkungen")
        self.assertEqual(keys[-4:], ["mb_foto_zaehlerschrank", "mb_foto_aussengeraet",
                                     "mb_foto_innengeraet", "mb_foto_anlage"])
        self.assertEqual(feld(self.logik, "montagebericht", "mb_foto_zaehlerschrank").optionen, "Elektro")
        self.assertEqual(len(self.logik.formulare["abnahme"]), 9)

    def test_pflicht_wenn_auswertung(self):
        f = feld(self.logik, "inbetriebnahme", "ib_f11_text")
        self.assertFalse(f.pflicht_erfuellt({"ib_f11": "Ja"}))
        self.assertTrue(f.pflicht_erfuellt({"ib_f11": "Nein"}))
        self.assertTrue(f.pflicht_erfuellt({"ib_f11": "Mit dokumentierten Einschränkungen"}))
        self.assertTrue(f.pflicht_erfuellt({}))      # unbeantwortet zählt als ≠ Ja
        self.assertIn("Pflicht, wenn", f.pflicht_wenn_text({"ib_f11": "11. Freigabe"}))
        self.assertEqual(projektierung_logik.pflicht_wenn_parsen("pflicht_wenn:a=b"), ("a", "=", "b"))
        self.assertEqual(projektierung_logik.pflicht_wenn_parsen("pflicht_wenn:a!=b"), ("a", "≠", "b"))
        self.assertIsNone(projektierung_logik.pflicht_wenn_parsen("pflicht_wenn:ab"))
        self.assertIsNone(projektierung_logik.pflicht_wenn_parsen("gross"))

    def test_logik_pruefen_meldet_unbekanntes(self):
        TMP.mkdir(parents=True, exist_ok=True)
        ziel = TMP / "formulare_test.xlsx"
        wb = openpyxl.load_workbook(projektierung_logik.LOGIK_PFAD)
        ws = wb["Formulare"]
        ws.append(["inbetriebnahme", "Test", "tx_1", "Schieber", "schieberegler", "N", ""])
        ws.append(["inbetriebnahme", "Test", "tx_2", "Riesig", "text", "N", "riesig"])
        ws.append(["inbetriebnahme", "Test", "tx_3", "Bezug", "text", "N", "pflicht_wenn:gibt_es_nicht≠Ja"])
        ws.append(["inbetriebnahme", "Test", "tx_4", "Kaputt", "zahl", "N", "pflicht_wenn:kaputt"])
        ws.append(["inbetriebnahme", "Test", "tx_5", "Gross", "zahl", "N", "gross"])
        ws.append(["inbetriebnahme", "Test", "tx_6", "Mehr SN", "wiederhol", "N", ""])
        wb.save(ziel)
        try:
            logik = projektierung_logik.einlesen(ziel)
        finally:
            shutil.rmtree(TMP, ignore_errors=True)
        fehler = "\n".join(logik.fehler)
        self.assertIn("tx_1: unbekannter Typ „schieberegler“", fehler)
        self.assertIn("tx_2: unbekannte Optionsform „riesig“", fehler)
        self.assertIn("tx_3: pflicht_wenn verweist auf unbekanntes Feld „gibt_es_nicht“", fehler)
        self.assertIn("tx_4: Optionsform „pflicht_wenn:kaputt“ nicht lesbar", fehler)
        self.assertIn("tx_5: Option „gross“ gilt nur für Typ text", fehler)
        self.assertNotIn("tx_6", fehler)
        self.assertTrue(any("tx_6" in w and "Einzelfeld" in w for w in logik.warnungen))
        self.assertEqual(len(logik.formulare["inbetriebnahme"]), 37)


class Wertformen(unittest.TestCase):
    def test_foto_werte(self):
        self.assertEqual(montage_formulare.foto_werte("galerie:5:a.jpg"), [(5, "a.jpg")])
        self.assertEqual(montage_formulare.foto_werte("galerie:5:a.jpg|galerie:7:b.jpg"),
                         [(5, "a.jpg"), (7, "b.jpg")])
        self.assertEqual(montage_formulare.foto_werte(""), [])
        self.assertEqual(montage_formulare.foto_werte(None), [])
        self.assertEqual(montage_formulare.foto_wert_bauen([(5, "a.jpg"), (7, "b.jpg")]),
                         "galerie:5:a.jpg|galerie:7:b.jpg")

    def test_wiederhol_werte(self):
        self.assertEqual(montage_formulare.wiederhol_werte(["A1", " ", "B2"]), ["A1", "B2"])
        self.assertEqual(montage_formulare.wiederhol_werte('["A1", "B2"]'), ["A1", "B2"])
        self.assertEqual(montage_formulare.wiederhol_werte("A1\nB2\n"), ["A1", "B2"])
        self.assertEqual(montage_formulare.wiederhol_werte(None), [])

    def test_restarbeiten_zeilen(self):
        self.assertEqual(montage_formulare.restarbeiten_zeilen("keine"), [])
        self.assertEqual(montage_formulare.restarbeiten_zeilen("Keine\n-\n–\n"), [])
        self.assertEqual(montage_formulare.restarbeiten_zeilen(
            "Dämmung Rohr Keller – Müller – 20.11.\nKondensatablauf prüfen\n\nkeine"),
            ["Dämmung Rohr Keller – Müller – 20.11.", "Kondensatablauf prüfen"])


class Formulare(Basis):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.logik = projektierung_logik.hole_logik(cls.s)
        cls.adminb = cls.s.get(Benutzer, 1)

    def inbetriebnahme_vollstaendig(self, **extra) -> dict:
        daten = {"ib_sn_aussen": "AG-1", "ib_sn_innen": "IG-1", "ib_sn_komponenten": ["A1", "B2"],
                 "ib_f01": "Ja", "ib_f02": "Ja", "ib_f03": "Ja", "ib_f04": "Ja", "ib_f05": "Ja",
                 "ib_f06": "Ja", "ib_f07_heizen": "OK", "ib_f07_warmwasser": "OK",
                 "ib_f07_kuehlen": "nicht vorhanden", "ib_f07_zusatzheizung": "nicht OK",
                 "ib_f08": "Ja", "ib_f09": "Ja", "ib_f10": "keine", "ib_f11": "Ja",
                 "ib_bw_betriebsart": "Heizen", "ib_bw_aussen": "7.5", "ib_bw_vorlauf": "35",
                 "ib_e_heizkurve": "0,6", "ib_e_raumsoll": "21",
                 "ib_unterschrift_techniker": png_daten_url(),
                 "ib_unterschrift_betreiber": png_daten_url()}
        daten.update(extra)
        return daten

    def test_offene_pflicht_mit_pflicht_wenn(self):
        g = self.gewerk_neu()
        eintrag = montage_formulare.formular_holen(self.s, g, "inbetriebnahme", self.adminb)
        eintrag.antworten_json = json.dumps(self.inbetriebnahme_vollstaendig(ib_f11="Nein"))
        offen = montage_formulare.offene_pflicht(self.logik, eintrag)
        self.assertEqual(offen, ["Einschränkungen / Begründung"])
        eintrag.antworten_json = json.dumps(self.inbetriebnahme_vollstaendig(
            ib_f11="Nein", ib_f11_text="Druck zu niedrig"))
        self.assertEqual(montage_formulare.offene_pflicht(self.logik, eintrag), [])
        eintrag.antworten_json = json.dumps(self.inbetriebnahme_vollstaendig(ib_f11="Ja"))
        self.assertEqual(montage_formulare.offene_pflicht(self.logik, eintrag), [])
        # leere Pflicht-Wiederholliste wäre offen, falls Pflicht – hier nicht Pflicht
        eintrag.antworten_json = json.dumps(self.inbetriebnahme_vollstaendig(ib_sn_komponenten=[]))
        self.assertEqual(montage_formulare.offene_pflicht(self.logik, eintrag), [])
        eintrag.antworten_json = json.dumps(self.inbetriebnahme_vollstaendig(ib_f01=""))
        self.assertIn("1. Entsprechen Aufstellung", montage_formulare.offene_pflicht(self.logik, eintrag)[0])
        self.s.rollback()

    def test_restarbeiten_aus_frage_10(self):
        g = self.gewerk_neu()
        eintrag = montage_formulare.formular_holen(self.s, g, "inbetriebnahme", self.adminb)
        eintrag.antworten_json = json.dumps(self.inbetriebnahme_vollstaendig(ib_f10="keine"))
        ok, meldung = montage_formulare.abschliessen(self.s, self.logik, eintrag, g, self.adminb)
        self.s.commit()
        self.assertTrue(ok, meldung)
        self.assertEqual(self.s.query(Restarbeit).filter_by(gewerk_id=g.id).count(), 0)
        texte = self.verlauf_texte(g)
        self.assertTrue(any(x.endswith("abgeschlossen (PDF in Galerie Inbetrieb-/Abnahme)") for x in texte), texte)
        g2 = self.gewerk_neu()
        eintrag2 = montage_formulare.formular_holen(self.s, g2, "inbetriebnahme", self.adminb)
        zeilen = "Dämmung Rohr Keller – Müller – 20.11.\nKondensatablauf prüfen"
        eintrag2.antworten_json = json.dumps(self.inbetriebnahme_vollstaendig(ib_f10=zeilen))
        ok, meldung = montage_formulare.abschliessen(self.s, self.logik, eintrag2, g2, self.adminb)
        self.s.commit()
        self.assertTrue(ok, meldung)
        rest = self.s.query(Restarbeit).filter_by(gewerk_id=g2.id).order_by(Restarbeit.id).all()
        self.assertEqual([r.text for r in rest], ["Dämmung Rohr Keller – Müller – 20.11.",
                                                   "Kondensatablauf prüfen"])
        self.assertTrue(all(r.galerie_datei_id is None for r in rest))
        self.assertTrue(any(x.endswith("– 2 Restarbeiten übernommen") for x in self.verlauf_texte(g2)))
        # erneutes Abschließen: keine Dubletten
        ok, _ = montage_formulare.abschliessen(self.s, self.logik, eintrag2, g2, self.adminb)
        self.s.commit()
        self.assertEqual(self.s.query(Restarbeit).filter_by(gewerk_id=g2.id).count(), 2)
        # PDF liegt in der Galerie „Inbetrieb-/Abnahme“ unter dem bisherigen Namen
        pdfs = self.s.query(GalerieDatei).filter_by(vorgang_id=self.vorgang_von(g2).id,
                                                    ordner="Inbetrieb-/Abnahme").all()
        self.assertTrue(any(d.dateiname.startswith("Inbetriebnahmeprotokoll_PR-") for d in pdfs), [d.dateiname for d in pdfs])

    def test_pdf_inhalt(self):
        g = self.gewerk_neu()
        eintrag = montage_formulare.formular_holen(self.s, g, "inbetriebnahme", self.adminb)
        eintrag.antworten_json = json.dumps(self.inbetriebnahme_vollstaendig(
            ib_f11="Mit dokumentierten Einschränkungen", ib_f11_text="V28P2 Einschränkung"))
        daten = montage_formulare.pdf_bytes(self.s, self.logik, eintrag, g)
        self.assertTrue(daten.startswith(b"%PDF"))
        text = " ".join(pdf_text(daten).split())   # Blocksatz-Extraktion: Mehrfach-Leerzeichen
        self.assertIn("Seriennummer 1: A1", text)
        self.assertIn("Seriennummer 2: B2", text)
        self.assertIn("Wurden die vorgesehenen Betriebsarten erfolgreich getestet?", text)
        for zeile in ("Heizen", "Warmwasser", "Kühlen", "Zusatzheizung"):
            self.assertIn(zeile, text)
        self.assertIn("nicht vorhanden", text)
        # lange Frage in voller Länge (kein Abschneiden nach 52 Zeichen)
        self.assertIn("Kondensatablauf?", text.replace("\n", " "))
        self.assertIn("Betriebswerte im stabilen Betrieb", text)
        self.assertIn("Außen-/Quellentemperatur", text)
        self.assertIn("V28P2 Einschränkung", text)
        self.assertIn("Techniker", text)
        self.assertIn("Betreiber – Einweisung und Unterlagenerhalt bestätigt", text.replace("\n", " "))
        self.assertIn("Inbetriebnahmeprotokoll", text)
        self.s.rollback()

    def test_speichern_wiederhol_und_fotos(self):
        g = self.gewerk_neu()
        vorgang = self.vorgang_von(g)
        from app.models import Team
        team = self.team_neu("Team F", [])
        termin = self.termin_neu(g, team, tage=1)
        basis = f"/montage/einsatz/{termin.id}/formular"
        # Wiederholfeld: Felder ib_sn_komponenten[] → JSON-Liste ohne Leerzeilen
        r = self.admin.post(f"{basis}/inbetriebnahme",
                            data={"seite": "0", "aktion": "bleiben", "ib_sn_aussen": "AG",
                                  "ib_sn_innen": "IG", "ib_sn_komponenten[]": ["A1", "  ", "B2"]},
                            follow_redirects=False)
        self.assertEqual(r.status_code, 303)
        self.assertTrue(r.headers["location"].endswith("?seite=0"))
        eintrag = montage_formulare.formular_holen(self.s, g, "inbetriebnahme")
        self.s.refresh(eintrag)
        self.assertEqual(montage_formulare.antworten(eintrag)["ib_sn_komponenten"], ["A1", "B2"])
        r = self.admin.get(f"{basis}/inbetriebnahme?seite=0")
        self.assertIn('name="ib_sn_komponenten[]" value="A1"', r.text)
        self.assertIn("+ weitere Seriennummer", r.text)
        self.assertIn('data-pflicht-wenn="ib_f11"', self.admin.get(f"{basis}/inbetriebnahme?seite=1").text)
        self.assertIn('rows="6"', self.admin.get(f"{basis}/inbetriebnahme?seite=1").text)
        # Foto-Feld mit zwei Dateien → zwei Galerie-Dateien im Ordner Elektro, Wert mit |
        seiten = self.logik.formular_seiten("montagebericht")
        foto_seite = next(i for i, (name, _) in enumerate(seiten) if name == "Fotos")
        r = self.admin.post(f"{basis}/montagebericht",
                            data={"seite": str(foto_seite), "aktion": "bleiben"},
                            files=[("mb_foto_zaehlerschrank", ("V28P2-z1.jpg", jpg_bytes(), "image/jpeg")),
                                   ("mb_foto_zaehlerschrank", ("V28P2-z2.jpg", jpg_bytes((40, 200, 40)), "image/jpeg"))],
                            follow_redirects=False)
        self.assertEqual(r.status_code, 303)
        dateien = (self.s.query(GalerieDatei)
                   .filter_by(vorgang_id=vorgang.id, ordner="Elektro").order_by(GalerieDatei.id).all())
        self.assertEqual([d.dateiname for d in dateien], ["V28P2-z1.jpg", "V28P2-z2.jpg"])
        self.assertTrue(all(d.sparte == "WP" and d.bild for d in dateien))
        mb = montage_formulare.formular_holen(self.s, g, "montagebericht")
        self.s.refresh(mb)
        wert = montage_formulare.antworten(mb)["mb_foto_zaehlerschrank"]
        self.assertEqual(wert, f"galerie:{dateien[0].id}:V28P2-z1.jpg|galerie:{dateien[1].id}:V28P2-z2.jpg")
        self.assertEqual(montage_formulare._wert_anzeige(
            feld(self.logik, "montagebericht", "mb_foto_zaehlerschrank"), wert),
            "Fotos in Galerie: V28P2-z1.jpg, V28P2-z2.jpg")
        # drittes Foto wird ergänzt, Seite zeigt die vorhandenen mit Links
        r = self.admin.post(f"{basis}/montagebericht",
                            data={"seite": str(foto_seite), "aktion": "bleiben"},
                            files=[("mb_foto_zaehlerschrank", ("V28P2-z3.jpg", jpg_bytes(), "image/jpeg"))],
                            follow_redirects=False)
        self.s.refresh(mb)
        self.assertEqual(len(montage_formulare.foto_werte(montage_formulare.antworten(mb)["mb_foto_zaehlerschrank"])), 3)
        r = self.admin.get(f"{basis}/montagebericht?seite={foto_seite}")
        self.assertIn("3 Fotos in der Galerie", r.text)
        self.assertIn('multiple hidden class="sammel"', r.text)
        # Bestandswert mit einem Foto (v15-Form) bleibt lesbar
        self.assertEqual(montage_formulare._wert_anzeige(
            feld(self.logik, "montagebericht", "mb_foto_anlage"), "galerie:9:alt.jpg"),
            "Foto in Galerie: alt.jpg")


if __name__ == "__main__":
    unittest.main()
