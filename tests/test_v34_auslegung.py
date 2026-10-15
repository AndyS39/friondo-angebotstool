# v34 (PLAN_V21 Phase 180): Auslegungs-Position aus dem Angebot entfernen. WP „Auslegung der
# Wärmepumpe“ (Block 1, v11), KL „Auslegung der Klimaanlage“ (Block 3, v24) und die
# PV-Auslegungszeile (Block 1, v16) werden nicht mehr als 0,00-€-Position angelegt; der Text
# steht in angebote.auslegung_text (Editor „Auslegung (intern)“, nur Innendienst/Admin) und
# bleibt im Konfigurationsprotokoll. Bestand: migration_v34_auslegung (nur Entwürfe, R5);
# Versionen/Duplikate lassen die Zeile weg. Kontrollwerte unverändert (WP netto 30.245,43 €,
# KL-Fall A 6.518,66 €). Läuft gegen DB_PFAD_OVERRIDE (Kopie), räumt eigene Daten auf.
import json
import unittest
import warnings

warnings.filterwarnings("ignore")

from app import angebot_aufbau, import_klima, import_pv, kl_auslegung, pdf_export, pv_auslegung
from app import logik as logik_modul
from app.models import Angebot, AngebotsPosition, Artikel, QUELLE_KL, QUELLE_PV
from tests.test_kl_v24 import fall_a
from tests.test_pv_v13 import pv_basis
from tests.test_regression import KONTROLL_SZENARIO
from tests.v34_e_basis import WP_PAKET, Basis, pdf_text

WP_ZEILE = "Auslegung der Wärmepumpe"
KL_ZEILE = "Auslegung der Klimaanlage"
PV_ZEILE = "Auslegung der PV-Anlage"


def auslegungs_snapshot(bezeichnung: str, text: str, block_nr: int = 1, sort: int = 9) -> dict:
    """0,00-€-Auslegungszeile wie bis v33 angelegt (Altbestand)."""
    return dict(sort=sort, block_nr=block_nr, gruppe="", pos_nr="", bezeichnung=bezeichnung,
                beschreibung=text, menge=1.0, einheit="psl.", e_preis_cent=0, ek_cent=0, guid="")


class LogikBasis(Basis):
    EMAIL = "v34e-auslegung@test.local"
    NACHNAME = "V34E Auslegung"
    AD_NAME = "V34E Auslegung-AD"

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        if cls.s.query(Artikel).filter(Artikel.quelle == QUELLE_PV).count() == 0:
            import_pv.import_ausfuehren(cls.s)
        if cls.s.query(Artikel).filter(Artikel.quelle == QUELLE_KL).count() == 0:
            import_klima.import_ausfuehren(cls.s)
        cls.logik_voll, bericht = logik_modul.neu_einlesen(cls.s)
        assert bericht.ok, bericht.fehler
        cls.logik_kl = logik_modul.logik_fuer_sparte(cls.logik_voll, "KL")
        cls.logik_pv = logik_modul.logik_fuer_sparte(cls.logik_voll, "PV")


class KeinePositionMehr(LogikBasis):
    def test_wp_positionen_ohne_auslegungszeile(self):
        pos = angebot_aufbau.positionen_zusammenstellen(self.logik_voll, KONTROLL_SZENARIO, self.s)
        self.assertFalse([p for p in pos if p["bezeichnung"] == WP_ZEILE])
        self.assertFalse([p for p in pos if angebot_aufbau.ist_auslegungs_position(p)])
        netto = sum(round(p["menge"] * p["e_preis_cent"]) for p in pos if not p["ep_flag"])
        self.assertEqual(netto, 3024543)                         # Kontrollwert unverändert
        self.assertEqual([p["sort"] for p in pos], list(range(1, len(pos) + 1)))

    def test_wp_angebot_text_und_summen(self):
        a = angebot_aufbau.angebot_anlegen(self.s, self.kunde.id, antworten=dict(KONTROLL_SZENARIO),
                                           logik=self.logik_voll)
        self.assertFalse([p for p in a.positionen if p.bezeichnung == WP_ZEILE])
        self.assertTrue(a.auslegung_text.startswith(
            "Auslegung auf Basis des Jahresverbrauchs: 15.000 kWh/Jahr"), a.auslegung_text)
        self.assertIn("Leistungsklasse", a.auslegung_text)
        su = a.summen()
        self.assertEqual((su["netto"], su["ust"], su["brutto"]), (3024543, 574663, 3599206))
        # Protokoll unverändert (Verbrauch im Protokoll, Herleitung über A03)
        protokoll = json.loads(a.protokoll_json)
        self.assertTrue(any(z.get("frage_id") == "A03" for z in protokoll))

    def test_kl_fall_a(self):
        a = angebot_aufbau.angebot_anlegen(self.s, self.kunde.id, antworten=fall_a(),
                                           logik=self.logik_kl, sparte="KL")
        self.assertEqual([p.pos_nr for p in a.positionen],
                         ["KL023", "KL008", "KL038", "KL026", "KL013", "KL049"])
        self.assertFalse([p for p in a.positionen if p.bezeichnung == KL_ZEILE])
        su = a.summen()
        self.assertEqual((su["netto"], su["ust"], su["brutto"]), (651866, 123855, 775721))
        zeilen = a.auslegung_text.splitlines()
        self.assertEqual(zeilen[0], "Auslegung Klimaanlage – Serie Bosch Climate 3200i")
        self.assertIn("Kombination 9+9+9", a.auslegung_text)
        self.assertIn("Raum 1 „Wohnzimmer“", a.auslegung_text)
        kl = json.loads(a.kl_json)
        self.assertEqual(kl["aussengeraete"][0]["kombination"], "9+9+9")   # kl_json unverändert
        self.assertEqual({p.gruppe for p in a.positionen if p.block_nr == 3}, {"Klimaanlage Bosch"})
        # Protokollseite „Auslegung“ bleibt
        seite = kl_auslegung.protokoll_zeilen(self.logik_kl, fall_a())
        self.assertTrue(seite and all(z["seite"] == "Auslegung" for z in seite))

    def test_kl_positionen_bauen_ohne_zeile(self):
        pos = kl_auslegung.positionen_zusammenstellen(self.logik_kl, fall_a(), self.s)
        self.assertEqual([p["pos_nr"] for p in pos],
                         ["KL023", "KL008", "KL038", "KL026", "KL013", "KL049"])
        self.assertEqual([p["sort"] for p in pos], [1, 2, 3, 4, 5, 6])
        self.assertEqual(kl_auslegung.AUSLEGUNGSZEILE, KL_ZEILE)   # Kennung für Bestand bleibt

    def test_pv(self):
        pos = pv_auslegung.positionen_zusammenstellen(self.logik_pv, pv_basis(), self.s)
        self.assertFalse([p for p in pos if p["bezeichnung"] == PV_ZEILE])
        self.assertFalse([p for p in pos if (p.get("beschreibung") or "").startswith("Auslegung: ")])
        a = angebot_aufbau.angebot_anlegen(self.s, self.kunde.id, antworten=pv_basis(),
                                           logik=self.logik_pv, sparte="PV")
        self.assertTrue(a.auslegung_text.startswith("Auslegung: 30 Module"), a.auslegung_text)
        self.assertIn("Belegungsart: Maximalbelegung", a.auslegung_text)
        self.assertEqual(json.loads(a.pv_json)["module"], 30)
        self.assertEqual(a.summen()["ust"], 0)
        zeilen = pv_auslegung.protokoll_zeilen(self.logik_pv, pv_basis())
        self.assertEqual(zeilen[0]["frage"], "Auslegung PV")
        self.assertEqual(pv_auslegung.AUSLEGUNGSZEILE, PV_ZEILE)

    def test_auslegungs_text_fuer_robust(self):
        self.assertEqual(angebot_aufbau.auslegungs_text_fuer(None, None, "WP"), "")
        self.assertEqual(angebot_aufbau.auslegungs_text_fuer(self.logik_voll, {}, "WP"), "")
        self.assertEqual(angebot_aufbau.auslegungs_text_fuer(self.logik_voll, {}, "GW"), "")

    def test_pdf_ohne_auslegungszeile(self):
        wp = angebot_aufbau.angebot_anlegen(self.s, self.kunde.id, antworten=dict(KONTROLL_SZENARIO),
                                            logik=self.logik_voll)
        text = pdf_text(pdf_export.pdf_fuer_angebot(self.s, wp))
        self.assertNotIn(WP_ZEILE, text)
        self.assertNotIn("Leistungsklasse", text)                  # Herleitung bleibt intern
        self.assertIn("30.245,43", text)
        kl = angebot_aufbau.angebot_anlegen(self.s, self.kunde.id, antworten=fall_a(),
                                            logik=self.logik_kl, sparte="KL")
        text = pdf_text(pdf_export.pdf_fuer_angebot(self.s, kl))
        self.assertNotIn(KL_ZEILE, text)
        self.assertIn("6.518,66", text)
        self.assertIn("1.238,55", text)


class EditorHinweis(LogikBasis):
    def test_innendienst_sieht_hinweis_aussendienst_nicht(self):
        a = angebot_aufbau.angebot_anlegen(self.s, self.kunde.id, antworten=dict(KONTROLL_SZENARIO),
                                           logik=self.logik_voll)
        a.vertriebler_id = self.ad.id
        a.vorgang_id = self.vorgang.id
        self.s.commit()
        html = self.client.get(f"/angebote/{a.id}").text
        self.assertIn('id="auslegung-intern"', html)
        self.assertIn("Auslegung (intern)", html)
        self.assertIn("Auslegung auf Basis des Jahresverbrauchs", html)
        # Außendienst: Meine Angebote ohne den Block, Editor nicht erreichbar
        ad = self.ad_client()
        r = ad.get(f"/meine-angebote/{a.id}")
        self.assertEqual(r.status_code, 200)
        self.assertNotIn("Auslegung (intern)", r.text)
        self.assertNotIn("Auslegung auf Basis des Jahresverbrauchs", r.text)
        r = ad.get(f"/angebote/{a.id}", follow_redirects=False)
        self.assertNotEqual(r.status_code, 200)

    def test_ohne_text_kein_block(self):
        a = self.angebot("WP", [WP_PAKET])
        self.assertEqual(a.auslegung_text, "")
        html = self.client.get(f"/angebote/{a.id}").text
        self.assertNotIn('id="auslegung-intern"', html)


class Migration(Basis):
    EMAIL = "v34e-migration@test.local"
    NACHNAME = "V34E Migration"
    AD_NAME = "V34E Migration-AD"

    def test_entwuerfe_bereinigt_versendete_bleiben(self):
        text_wp = "Auslegung auf Basis des Jahresverbrauchs: 15.000 kWh/Jahr → Leistungsklasse 7 kW"
        entwurf = self.angebot("WP", [
            dict(WP_PAKET, anzeige_nr="A9"),
            auslegungs_snapshot(WP_ZEILE, text_wp, sort=2),
            dict(sort=3, block_nr=7, gruppe="Elektroarbeiten", pos_nr="011",
                 bezeichnung="Elektroinstallation", beschreibung="", menge=1.0, einheit="psl.",
                 e_preis_cent=150_000, ek_cent=90_000)])
        pv_text = "Auslegung: 30 Module à 455 Wp = 13,65 kWp · 2 Strings\nBelegungsart: Maximalbelegung"
        entwurf_pv = self.angebot("PV", [dict(WP_PAKET, pos_nr="PV001", gruppe="Komplettpaket"),
                                         auslegungs_snapshot(PV_ZEILE, pv_text, sort=2)])
        versendet = self.angebot("WP", [WP_PAKET, auslegungs_snapshot(WP_ZEILE, text_wp, sort=2)],
                                 status="Versendet")
        meldungen = angebot_aufbau.migration_v34_auslegung(self.s)
        self.s.commit()
        self.assertTrue(any(m.startswith(entwurf.nummer) for m in meldungen), meldungen)
        self.assertTrue(any(m.startswith(entwurf_pv.nummer) for m in meldungen), meldungen)
        self.assertFalse(any(m.startswith(versendet.nummer) for m in meldungen), meldungen)
        e = self.neu(entwurf.id)
        self.assertEqual([p.pos_nr for p in e.positionen], ["045", "011"])
        self.assertEqual([p.sort for p in e.positionen], [1, 2])
        self.assertEqual([p.anzeige_nr for p in e.positionen], ["", ""])   # wie „Neu durchnummerieren“
        self.assertEqual(e.auslegung_text, text_wp)
        self.assertEqual(e.summen()["netto"], 1_150_000)
        pv = self.neu(entwurf_pv.id)
        self.assertEqual([p.pos_nr for p in pv.positionen], ["PV001"])
        self.assertEqual(pv.auslegung_text, pv_text)
        v = self.neu(versendet.id)
        self.assertEqual([p.bezeichnung for p in v.positionen][1], WP_ZEILE)   # unverändert
        self.assertEqual(v.auslegung_text, "")
        # idempotent: zweiter Lauf meldet nichts
        self.assertEqual(angebot_aufbau.migration_v34_auslegung(self.s), [])
        self.s.commit()

    def test_vorhandener_text_bleibt(self):
        a = self.angebot("WP", [WP_PAKET, auslegungs_snapshot(WP_ZEILE, "alt", sort=2)])
        a.auslegung_text = "bereits gefüllt"
        self.s.commit()
        angebot_aufbau.migration_v34_auslegung(self.s)
        self.s.commit()
        self.assertEqual(self.neu(a.id).auslegung_text, "bereits gefüllt")
        self.assertEqual(len(self.neu(a.id).positionen), 1)

    def test_ist_auslegungs_position(self):
        self.assertTrue(angebot_aufbau.ist_auslegungs_position(auslegungs_snapshot(WP_ZEILE, "x")))
        self.assertTrue(angebot_aufbau.ist_auslegungs_position(
            auslegungs_snapshot("Irgendwas", "Auslegung: 20 Module")))
        self.assertFalse(angebot_aufbau.ist_auslegungs_position(dict(WP_PAKET)))
        # 0,00-€-Zeile mit Artikelnummer (z. B. KL049 Systemgarantie) ist KEINE Auslegungszeile
        self.assertFalse(angebot_aufbau.ist_auslegungs_position(
            dict(pos_nr="KL049", bezeichnung="Systemgarantie", beschreibung="", e_preis_cent=0)))


class VersionenUndKopien(Basis):
    EMAIL = "v34e-versionen@test.local"
    NACHNAME = "V34E Versionen"
    AD_NAME = "V34E Versionen-AD"

    def test_ueberarbeiten_laesst_zeile_weg(self):
        text = "Auslegung nach angegebener Heizlast: 9,0 kW → Leistungsklasse 10 kW"
        original = self.angebot("WP", [WP_PAKET, auslegungs_snapshot(WP_ZEILE, text, sort=2)],
                                status="Versendet")
        r = self.client.post(f"/angebote/{original.id}/ueberarbeiten", follow_redirects=False)
        self.assertEqual(r.status_code, 303)
        version_id = int(r.headers["location"].split("/angebote/")[1].split("?")[0])
        version = self.neu(version_id)
        self.assertEqual(version.nummer, f"{original.stamm_nummer}.2")
        self.assertEqual([p.pos_nr for p in version.positionen], ["045"])
        self.assertEqual(version.auslegung_text, text)
        self.assertEqual(self.neu(original.id).status, "Überholt")
        self.assertEqual(len(self.neu(original.id).positionen), 2)      # Original unverändert

    def test_duplizieren_laesst_zeile_weg(self):
        text = "Auslegung Klimaanlage – Serie Bosch Climate 3200i\nRaum 1 „Büro“: …"
        quelle = self.angebot("KL", [dict(WP_PAKET, pos_nr="KL038", gruppe="Klimaanlage Bosch",
                                          block_nr=3),
                                     auslegungs_snapshot(KL_ZEILE, text, block_nr=3, sort=2)])
        r = self.client.post(f"/angebote/{quelle.id}/duplizieren", follow_redirects=False)
        self.assertEqual(r.status_code, 303)
        kopie_id = int(r.headers["location"].split("/angebote/")[1].split("?")[0])
        kopie = self.neu(kopie_id)
        self.assertEqual([p.pos_nr for p in kopie.positionen], ["KL038"])
        self.assertEqual(kopie.auslegung_text, text)
        self.assertEqual(kopie.summen()["netto"], 1_000_000)


if __name__ == "__main__":
    unittest.main()
