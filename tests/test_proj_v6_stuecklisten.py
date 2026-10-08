# v28 (PLAN_PROJ_V6 Phase 139): Stücklisten-Nachträge – Konvention Lieferant
# (Collin = bestellen · Lager · – = Leistung · Fremdname), UGL nur Standard-
# Lieferant, Fortschritt/Go-live-Quote, Spalte „Art“, CSV docs/stuecklisten_v26.csv.
# Schreibende Tests arbeiten auf einer Kopie der Logik-Excel (LOGIK_PFAD gemockt).
import shutil
import tempfile
import unittest
import warnings
from pathlib import Path
from unittest import mock

warnings.filterwarnings("ignore")

from fastapi.testclient import TestClient

from app import angebot_aufbau, config, projektierung_logik, stuecklisten, ugl
from app import projektierung as kern
from app.db import SessionLocal, init_db
from app.main import app
from app.models import (Angebot, AngebotsPosition, Aufgabe, AufgabenpaketInstanz, Gewerk,
                        Kunde, Projekt, ProjektTermin, ProjektVerlauf, SteckbriefWert,
                        Vorgang, angebot_status_setzen)

TEST_EMAIL = "v28p1-stueckliste@test.local"
CSV = Path(__file__).resolve().parent.parent / "docs" / "stuecklisten_v26.csv"


def aufraeumen(s):
    from app.models import Erfassung, GalerieDatei, UglBestellung, VorgangsNotiz
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
            s.delete(p)
        for a in s.query(Angebot).filter_by(kunde_id=k.id):
            s.delete(a)
        for e in s.query(Erfassung).filter_by(kunde_id=k.id):
            s.delete(e)
        for v in s.query(Vorgang).filter_by(kunde_id=k.id):
            s.query(GalerieDatei).filter_by(vorgang_id=v.id).delete()
            s.query(VorgangsNotiz).filter_by(vorgang_id=v.id).delete()
            s.delete(v)
        s.delete(k)
    s.commit()


class Basis(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        init_db()
        cls.s = SessionLocal()
        aufraeumen(cls.s)
        cls.client = TestClient(app)
        cls.client.post("/login", data={"benutzer_id": "1", "pin": "1234"})
        cls.ordner = Path(tempfile.mkdtemp())
        cls.kopie = cls.ordner / "logik.xlsx"
        shutil.copyfile(projektierung_logik.LOGIK_PFAD, cls.kopie)
        cls.patches = [mock.patch.object(projektierung_logik, "LOGIK_PFAD", cls.kopie),
                       mock.patch.object(config, "BACKUP_ORDNER", cls.ordner / "backup")]
        for p in cls.patches:
            p.start()
        projektierung_logik.hole_logik(cls.s, erzwingen=True)

    @classmethod
    def tearDownClass(cls):
        for p in cls.patches:
            p.stop()
        projektierung_logik.hole_logik(cls.s, erzwingen=True)
        aufraeumen(cls.s)
        cls.s.close()
        shutil.rmtree(cls.ordner, ignore_errors=True)

    def gewerk_neu(self, positionen):
        kunde = Kunde(anrede="Herr", vorname="Stefan", nachname="V28P1-Stueckliste",
                      strasse="Teststr. 9", plz="47139", ort="Duisburg",
                      email=TEST_EMAIL, telefon="0203 9")
        self.s.add(kunde)
        self.s.flush()
        angebot = angebot_aufbau.angebot_anlegen(self.s, kunde.id, sparte="WP")
        for i, (nr, menge) in enumerate(positionen, 1):
            angebot.positionen.append(AngebotsPosition(
                sort=i, pos_nr=nr, bezeichnung=f"Pos {nr}", beschreibung=f"Pos {nr}",
                menge=menge, e_preis_cent=10000))
        angebot_status_setzen(angebot, "Angenommen")
        self.s.commit()
        projekt = kern.projekt_anlegen(self.s, angebot, projektleiter_id=1)
        gewerk = kern.gewerk_anlegen(self.s, projekt, angebot, "WP")
        self.s.commit()
        return gewerk


class Konvention(Basis):
    def test_art_fuer_lieferant(self):
        art = stuecklisten.art_fuer_lieferant
        self.assertEqual(art("Collin"), "bestellen")
        self.assertEqual(art("collin", "Collin"), "bestellen")
        self.assertEqual(art("", "Collin"), "bestellen")
        self.assertEqual(art("Lager"), "lager")
        self.assertEqual(art("LAGER"), "lager")
        self.assertEqual(art("–"), "leistung")
        self.assertEqual(art("-"), "leistung")
        self.assertEqual(art("KEIN-MATERIAL"), "leistung")
        self.assertEqual(art("Bosch direkt"), "fremd")
        self.assertEqual(art("Collin", "Reisser"), "fremd")
        self.assertEqual(stuecklisten.standard_lieferant(self.s), "Collin")

    def test_ugl_nur_standard_lieferant(self):
        stuecklisten.position_speichern(self.s, "901", [
            {"artnr": "COL-1", "menge": "2", "bezeichnung": "Rohr", "lieferant": "Collin", "einheit": "M"},
            {"artnr": "LAG-1", "menge": "1", "bezeichnung": "Schellen", "lieferant": "Lager", "einheit": "ST"},
            {"artnr": "LEIST", "menge": "1", "bezeichnung": "Inbetriebnahme", "lieferant": "–", "einheit": "ST"},
            {"artnr": "BOS-9", "menge": "1", "bezeichnung": "Fühler", "lieferant": "Bosch direkt", "einheit": "ST"}])
        stuecklisten.position_speichern(self.s, "902", [
            {"artnr": "LAG-2", "menge": "3", "bezeichnung": "Kleinteile", "lieferant": "LAGER", "einheit": "ST"}])
        g = self.gewerk_neu([("901", 2), ("902", 1), ("903", 1)])
        zeilen, fehlend, uebrige = ugl.material_fuer_gewerk(self.s, g, mit_uebrigen=True)
        self.assertEqual([z["artnr"] for z in zeilen], ["COL-1"])
        self.assertEqual(zeilen[0]["menge"], 4.0)
        self.assertEqual(sorted(z["artnr"] for z in uebrige), ["BOS-9", "LAG-1", "LAG-2", "LEIST"])
        arten = {z["artnr"]: z["art"] for z in uebrige}
        self.assertEqual(arten, {"BOS-9": "fremd", "LAG-1": "lager", "LAG-2": "lager", "LEIST": "leistung"})
        self.assertEqual(fehlend, ["903 · Pos 903"])            # 902 (nur Lager) ist zugeordnet
        # Zweiergebnis bleibt (Aufrufer ohne mit_uebrigen)
        zeilen2, fehlend2 = ugl.material_fuer_gewerk(self.s, g)
        self.assertEqual(([z["artnr"] for z in zeilen2], fehlend2), (["COL-1"], fehlend))
        # UGL-Datei enthält nur die Collin-Zeile
        alt = kern.parameter_holen(self.s, "collin_kundennummer", "")
        kern.parameter_setzen(self.s, "collin_kundennummer", "12345")
        self.s.commit()
        try:
            inhalt, name, fehlend3, fehler = ugl.ugl_erzeugen(self.s, g, nr=1)
            self.assertIsNotNone(inhalt, fehler)
            text = inhalt.decode("cp850")
            self.assertIn("COL-1", text)
            self.assertNotIn("LAG-1", text)
            self.assertNotIn("BOS-9", text)
        finally:
            kern.parameter_setzen(self.s, "collin_kundennummer", alt)
            self.s.commit()
        # Vorschau zeigt den Block „nicht bestellt“
        r = self.client.get(f"/projektierung/gewerk/{g.id}/ugl")
        self.assertEqual(r.status_code, 200)
        self.assertIn("nicht bestellt (Lager / Leistung / Fremdlieferant)", r.text)
        self.assertIn("LAG-1", r.text)
        self.assertIn("Bosch direkt", r.text)

    def test_fortschritt_und_seite(self):
        stuecklisten.position_speichern(self.s, "PV901", [
            {"artnr": "PVX", "menge": "1", "bezeichnung": "Modul", "lieferant": "Fremd", "einheit": "ST"}])
        pos = {p["pos_nr"]: p for p in stuecklisten.positionen(self.s)}
        self.assertEqual([a for _, a in pos["PV901"]["arten"]], ["fremd"])
        # PV-/KL-Positionen ohne Zeile zählen nicht im Nenner
        from app.models import Artikel
        pv_ohne = [p for p in stuecklisten.positionen(self.s)
                   if p["pos_nr"].upper().startswith(("PV", "KL")) and not p["zeilen"]
                   and p["titel"] != "(nicht im Artikelstamm)"]
        zugeordnet, gesamt = stuecklisten.fortschritt(self.s)
        alle_stamm = [p for p in stuecklisten.positionen(self.s)
                      if p["titel"] != "(nicht im Artikelstamm)"]
        self.assertEqual(gesamt, len(alle_stamm) - len(pv_ohne))
        self.assertEqual(zugeordnet, sum(1 for p in alle_stamm if p["zeilen"] and
                                         not (p["pos_nr"].upper().startswith(("PV", "KL"))
                                              and not p["zeilen"])))
        r = self.client.get("/parametrierung/stuecklisten")
        self.assertEqual(r.status_code, 200)
        self.assertIn("Konvention Lieferant", r.text)
        self.assertIn("<th style=\"width:90px\">Art</th>", r.text)
        self.assertIn("pj-art-fremd", r.text)
        r = self.client.get("/parametrierung/stuecklisten?ohne=1")
        self.assertNotIn('id="pos-PV901"', r.text)          # Fremd-Zeile = zugeordnet


class CsvV26(Basis):
    def test_csv_einspielen_logik_gruen(self):
        self.assertTrue(CSV.exists(), "docs/stuecklisten_v26.csv fehlt (private Datei)")
        meldung = stuecklisten.csv_import(self.s, CSV.read_bytes())
        self.assertIn("121 Stücklisten-Zeilen importiert", meldung)
        self.assertNotIn("Fehler", meldung)
        logik = projektierung_logik.hole_logik(self.s)
        self.assertFalse(logik.fehler, logik.fehler)
        self.assertEqual(sum(len(z) for z in logik.stuecklisten.values()), 121)
        self.assertEqual(len(logik.stuecklisten), 80)
        arten = {stuecklisten.art_fuer_lieferant(z.lieferant)
                 for zeilen in logik.stuecklisten.values() for z in zeilen}
        self.assertIn("bestellen", arten)
        zugeordnet, gesamt = stuecklisten.fortschritt(self.s)
        self.assertGreaterEqual(zugeordnet, 60)


if __name__ == "__main__":
    unittest.main()
