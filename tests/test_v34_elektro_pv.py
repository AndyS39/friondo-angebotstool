# v34 (PLAN_V21 Phase 180): Knopf „Elektroarbeiten ins PV-Angebot (0 % USt)“ / „zurückholen“.
# Kontrollwert: WP-Entwurf mit Block Elektroarbeiten netto 2.400,00 € + PV-Entwurf → WP netto
# −2.400,00 (Positionen Alternativ „im PV-Angebot enthalten“), PV netto +2.400,00 zu 0 % USt in
# eigener Gruppe „Elektroarbeiten Wärmepumpe (aus Angebot AN-C-…)“, Meldung nennt die
# Kundenersparnis 456,00 €; Zurückholen stellt beide her; wiederholter Klick → „Nichts zu
# übernehmen“; PV abgelehnt/überholt → Hinweis + Zurückholen; Kombi-Warnung „doppelt“ entfällt;
# DB folgt den Positionen; mehrere Sparten → je Ursprungsangebot eigene Gruppe; Außendienst
# darf nicht. Routen in routers/angebote_elektro.py, Logik in app/elektro_pv.py.
import json
import unittest
import warnings

warnings.filterwarnings("ignore")

from app import elektro_pv, kombi_versand, pdf_export
from app.models import AngebotsPosition, VorgangsNotiz
from tests.v34_e_basis import KL_ELEKTRO, PV_MODULE, WP_ELEKTRO, WP_PAKET, Basis, pdf_text

WP_NETTO = 1_000_000 + 240_000          # Paket 10.000,00 + Elektro 2.400,00
PV_NETTO = 100_000                      # 10 Module à 100,00
ELEKTRO_NETTO = 240_000
ELEKTRO_EK = 90_000 + 50_000


class Uebernahme(Basis):
    EMAIL = "v34e-elektro@test.local"
    NACHNAME = "V34E Elektro"
    AD_NAME = "V34E Elektro-AD"

    def uebernehmen(self, wp_id: int):
        return self.post_json(self.client, f"/angebote/{wp_id}/elektro-ins-pv")

    def zurueckholen(self, wp_id: int):
        return self.post_json(self.client, f"/angebote/{wp_id}/elektro-zurueckholen")

    def test_kontrollwert_und_zurueckholen(self):
        wp = self.wp_entwurf()
        pv = self.pv_entwurf()
        self.assertEqual(wp.summen()["netto"], WP_NETTO)
        db_wp_vorher, db_pv_vorher = wp.deckungsbeitrag()["db"], pv.deckungsbeitrag()["db"]
        self.assertEqual(elektro_pv.knopf_sichtbar(self.s, wp).id, pv.id)
        r = self.uebernehmen(wp.id)
        self.assertEqual(r.status_code, 200, r.text)
        daten = r.json()
        self.assertEqual((daten["ok"], daten["anzahl"], daten["netto_cent"], daten["ersparnis_cent"]),
                         (True, 2, ELEKTRO_NETTO, 45_600))
        self.assertEqual(daten["meldung"], f"2 Positionen (netto 2.400,00 €) in {pv.nummer} "
                                           "übernommen – Kundenersparnis 456,00 €")
        wp, pv = self.neu(wp.id), self.neu(pv.id)
        # Ursprung: Alternativ mit Verknüpfung, Netto um 2.400,00 € niedriger
        alt = {p.pos_nr: (p.alternativ, p.alternativ_zu) for p in wp.positionen}
        self.assertEqual(alt["011"], (True, f"PV-Angebot {pv.nummer}"))
        self.assertEqual(alt["104"], (True, f"PV-Angebot {pv.nummer}"))
        self.assertEqual(alt["045"], (False, ""))
        self.assertEqual(alt["152"][0], False)                    # EP bleibt EP
        self.assertEqual(alt["Z22"][0], False)                    # bauseits bleibt
        self.assertEqual(wp.summen()["netto"], WP_NETTO - ELEKTRO_NETTO)
        # PV: voll berechnete Kopien, 0 % USt, eigene Gruppe am Ende, Herkunft
        su = pv.summen()
        self.assertEqual((su["netto"], su["ust"], su["brutto"]),
                         (PV_NETTO + ELEKTRO_NETTO, 0, PV_NETTO + ELEKTRO_NETTO))
        kopien = [p for p in pv.positionen if p.uebernommen_von_angebot_id == wp.id]
        self.assertEqual([(p.pos_nr, p.menge, p.e_preis_cent, p.ek_cent, p.ep_flag) for p in kopien],
                         [("011", 1.0, 150_000, 90_000, False), ("104", 1.0, 90_000, 50_000, False)])
        gruppe = f"Elektroarbeiten Wärmepumpe (aus Angebot {wp.nummer})"
        self.assertEqual({p.gruppe for p in kopien}, {gruppe})
        self.assertEqual(pv.positionen[-2:], kopien)
        self.assertGreater(kopien[0].block_nr, PV_MODULE["block_nr"])
        ursprung_ids = {p.id for p in wp.positionen if p.pos_nr in ("011", "104")}
        self.assertEqual({p.uebernommen_von_position_id for p in kopien}, ursprung_ids)
        self.assertEqual(json.loads(pv.vermerke_json),
                         [f"Enthält die Elektroarbeiten aus Angebot {wp.nummer} (Wärmepumpe)."])
        # DB folgt den Positionen
        self.assertEqual(wp.deckungsbeitrag()["db"], db_wp_vorher - (ELEKTRO_NETTO - ELEKTRO_EK))
        self.assertEqual(pv.deckungsbeitrag()["db"], db_pv_vorher + (ELEKTRO_NETTO - ELEKTRO_EK))
        # Notiz im Vorgangs-Chat (Autor System)
        notizen = (self.s.query(VorgangsNotiz)
                   .filter_by(vorgang_id=self.vorgang.id, herkunft=elektro_pv.HERKUNFT_NOTIZ).all())
        self.assertTrue(any("ins PV-Angebot" in n.text and n.benutzer_name == "System"
                            for n in notizen))
        # Editor: Herkunfts-Hinweis im PV, Badge im WP, Zurückholen-Knopf
        html_pv = self.client.get(f"/angebote/{pv.id}").text
        self.assertIn(f"übernommen aus Angebot", html_pv)
        self.assertIn(wp.nummer, html_pv)
        self.assertIn(gruppe, html_pv)
        html_wp = self.client.get(f"/angebote/{wp.id}").text
        self.assertIn("Alternativ · im PV-Angebot", html_wp)
        self.assertIn("Elektroarbeiten zurückholen", html_wp)
        # wiederholter Klick ohne neue Elektro-Positionen
        r = self.uebernehmen(wp.id)
        self.assertEqual(r.status_code, 409)
        self.assertFalse(r.json()["ok"])
        self.assertTrue(r.json()["meldung"].startswith("Nichts zu übernehmen"))
        # Zurückholen stellt beide her
        r = self.zurueckholen(wp.id)
        self.assertEqual(r.status_code, 200, r.text)
        self.assertEqual(r.json()["anzahl"], 2)
        wp, pv = self.neu(wp.id), self.neu(pv.id)
        self.assertFalse(any(p.alternativ for p in wp.positionen))
        self.assertEqual(wp.summen()["netto"], WP_NETTO)
        self.assertEqual([p.pos_nr for p in pv.positionen], ["PV001"])
        self.assertEqual(pv.summen()["netto"], PV_NETTO)
        self.assertEqual(json.loads(pv.vermerke_json), [])
        self.assertEqual(wp.deckungsbeitrag()["db"], db_wp_vorher)
        r = self.zurueckholen(wp.id)
        self.assertEqual(r.status_code, 409)

    def test_neue_elektro_position_nach_uebernahme(self):
        wp = self.wp_entwurf(mit_ep_bauseits=False)
        pv = self.pv_entwurf()
        self.assertEqual(self.uebernehmen(wp.id).json()["anzahl"], 2)
        wp = self.neu(wp.id)
        wp.positionen.append(AngebotsPosition(
            sort=9, block_nr=7, gruppe="Elektroarbeiten", pos_nr="Z23",
            bezeichnung="MID-Zwischenzähler", beschreibung="", menge=1.0, einheit="Stück",
            e_preis_cent=20_000, ek_cent=8_000))
        self.s.commit()
        r = self.uebernehmen(wp.id)
        self.assertEqual((r.status_code, r.json()["anzahl"], r.json()["netto_cent"]), (200, 1, 20_000))
        pv = self.neu(pv.id)
        kopien = [p for p in pv.positionen if p.uebernommen_von_angebot_id == wp.id]
        self.assertEqual([p.pos_nr for p in kopien], ["011", "104", "Z23"])
        self.assertEqual(len({(p.block_nr, p.gruppe) for p in kopien}), 1)   # dieselbe Gruppe
        self.assertEqual(len(json.loads(pv.vermerke_json)), 1)             # Vermerk nur einmal

    def test_gewerkeuebergreifende_artikel(self):
        # Pos. 015 (Fit for Future, Block 10) steht in der Parametrierungsliste (v10) → mit
        wp = self.angebot("WP", [WP_PAKET, dict(sort=2, block_nr=10, gruppe="", pos_nr="015",
                                                 bezeichnung="HEMS", beschreibung="",
                                                 menge=1.0, einheit="psl.", e_preis_cent=59_900,
                                                 ek_cent=30_000)])
        self.pv_entwurf()
        self.assertEqual([p.pos_nr for p in elektro_pv.elektro_positionen(self.s, wp)], ["015"])
        r = self.uebernehmen(wp.id)
        self.assertEqual((r.status_code, r.json()["anzahl"], r.json()["netto_cent"]), (200, 1, 59_900))
        self.assertEqual(r.json()["ersparnis_cent"], 11_381)          # 19 % von 599,00 € (kaufm.)

    def test_kombi_warnung_entfaellt(self):
        wp = self.wp_entwurf()
        pv = self.pv_entwurf(zusatz=[dict(sort=2, block_nr=1, gruppe="Komplettpaket", pos_nr="PV123",
                                          bezeichnung="Zähler-Komplettschrank 2-Feld inkl. Anbindung",
                                          beschreibung="", menge=1.0, einheit="Stück",
                                          e_preis_cent=90_000, ek_cent=50_000)])
        self.assertEqual(kombi_versand.doppelte_artikel([wp, pv]), ["104/PV123"])
        vorher = kombi_versand.gewerke_hinweise(self.s, self.vorgang, [wp, pv])
        self.assertTrue(any(h.startswith(f"{wp.nummer} (WP): Pos. 104") for h in vorher), vorher)
        self.uebernehmen(wp.id)
        wp, pv = self.neu(wp.id), self.neu(pv.id)
        self.assertEqual(kombi_versand.doppelte_artikel([wp, pv]), [])
        # v10-Hinweis am Vorgang: die WP-Position ist Alternativ, die Kopie im PV bewusst
        # verlagert – nur das PV-eigene PV123 bleibt ein Hinweis (wie vor der Übernahme)
        nachher = kombi_versand.gewerke_hinweise(self.s, self.vorgang, [wp, pv])
        self.assertFalse(any(h.startswith(f"{wp.nummer}") for h in nachher), nachher)
        self.assertFalse(any("104" in h for h in nachher), nachher)
        self.assertEqual(nachher, [f"{pv.nummer} (PV): Pos. PV123 voll berechnet – prüfen: ggf. ins "
                                   "WP-Angebot verlagern oder Alternativ-Kennzeichen setzen "
                                   "(Förder-/USt-Optimierung)."])
        # Dublette (Entscheidung 15.10.2026): PV123 = „Zähler-Komplettschrank“ → 104 nicht kopiert
        self.assertEqual([p.pos_nr for p in pv.positionen], ["PV001", "PV123", "011"])

    def test_dubletten_nicht_kopiert(self):
        """Entscheidung Orchestrator 15.10.2026 (Rückfrage 1): hat das PV-Angebot bereits eine
        aktive Position mit derselben Artikelnummer oder derselben normalisierten Bezeichnung,
        wird die Ursprungsposition Alternativ (Verknüpfung), aber NICHT kopiert; Meldung nennt
        es; Zurückholen entfernt nur Kopien, die vorhandene PV-Position bleibt."""
        wp = self.wp_entwurf(mit_ep_bauseits=False)
        pv = self.pv_entwurf(zusatz=[
            dict(sort=2, block_nr=1, gruppe="Komplettpaket", pos_nr="PV123",
                 bezeichnung="ZÄHLER-Komplettschrank  2-Feld inkl. Anbindung (PV-Variante)",
                 beschreibung="", menge=1.0, einheit="Stück", e_preis_cent=95_000, ek_cent=50_000),
            dict(sort=3, block_nr=1, gruppe="Komplettpaket", pos_nr="011",
                 bezeichnung="Elektroinstallation PV", beschreibung="", menge=1.0,
                 einheit="psl.", e_preis_cent=120_000, ek_cent=70_000)])
        self.assertIsNotNone(elektro_pv.dublette_im_ziel(wp.positionen[1], pv))   # 011 = Artikelnr.
        self.assertIsNotNone(elektro_pv.dublette_im_ziel(wp.positionen[2], pv))   # 104 = Bezeichnung
        self.assertEqual(elektro_pv.titel_schluessel(wp.positionen[2]),
                         "zähler-komplettschrank 2-feld ")
        r = self.uebernehmen(wp.id)
        self.assertEqual(r.status_code, 200, r.text)
        daten = r.json()
        self.assertEqual((daten["anzahl"], daten["netto_cent"], daten["ersparnis_cent"]),
                         (2, ELEKTRO_NETTO, 45_600))
        self.assertEqual(daten["meldung"],
                         f"2 Positionen (netto 2.400,00 €) in {pv.nummer} übernommen – davon 2 bereits "
                         "im PV-Angebot vorhanden (011, 104) – nicht kopiert – Kundenersparnis 456,00 €")
        wp, pv = self.neu(wp.id), self.neu(pv.id)
        self.assertEqual([(p.pos_nr, p.alternativ, p.alternativ_zu) for p in wp.positionen],
                         [("045", False, ""), ("011", True, f"PV-Angebot {pv.nummer}"),
                          ("104", True, f"PV-Angebot {pv.nummer}")])
        self.assertEqual(wp.summen()["netto"], WP_NETTO - ELEKTRO_NETTO)
        self.assertEqual([p.pos_nr for p in pv.positionen], ["PV001", "PV123", "011"])   # keine Kopie
        self.assertFalse(any(p.uebernommen_von_angebot_id for p in pv.positionen))
        self.assertEqual(pv.summen()["netto"], PV_NETTO + 95_000 + 120_000)
        self.assertEqual(json.loads(pv.vermerke_json),
                         [f"Enthält die Elektroarbeiten aus Angebot {wp.nummer} (Wärmepumpe)."])
        html = self.client.get(f"/angebote/{wp.id}").text
        self.assertIn("Alternativ · im PV-Angebot", html)
        self.assertIn("Elektroarbeiten zurückholen", html)
        self.assertTrue(elektro_pv.rueckholbar(self.s, wp)[0])
        # wiederholter Klick: nichts mehr offen
        self.assertEqual(self.uebernehmen(wp.id).status_code, 409)
        # Zurückholen: Kennzeichen weg, PV-Positionen unverändert, Vermerk entfernt
        r = self.zurueckholen(wp.id)
        self.assertEqual((r.status_code, r.json()["anzahl"]), (200, 2))
        wp, pv = self.neu(wp.id), self.neu(pv.id)
        self.assertFalse(any(p.alternativ for p in wp.positionen))
        self.assertEqual(wp.summen()["netto"], WP_NETTO)
        self.assertEqual([p.pos_nr for p in pv.positionen], ["PV001", "PV123", "011"])
        self.assertEqual(json.loads(pv.vermerke_json), [])

    def test_dublette_gemischt(self):
        """Eine Position wird kopiert, die andere ist Dublette – Meldung und Zurückholen."""
        wp = self.wp_entwurf(mit_ep_bauseits=False)
        pv = self.pv_entwurf(zusatz=[dict(sort=2, block_nr=1, gruppe="Komplettpaket", pos_nr="PV123",
                                          bezeichnung="Zähler-Komplettschrank 2-Feld inkl. Anbindung",
                                          beschreibung="", menge=1.0, einheit="Stück",
                                          e_preis_cent=90_000, ek_cent=50_000)])
        daten = self.uebernehmen(wp.id).json()
        self.assertEqual(daten["anzahl"], 2)
        self.assertIn("davon 1 bereits im PV-Angebot vorhanden (104) – nicht kopiert", daten["meldung"])
        pv = self.neu(pv.id)
        self.assertEqual([p.pos_nr for p in pv.positionen], ["PV001", "PV123", "011"])
        self.assertEqual([p.uebernommen_von_angebot_id for p in pv.positionen], [None, None, wp.id])
        self.assertEqual(pv.summen()["netto"], PV_NETTO + 90_000 + 150_000)
        r = self.zurueckholen(wp.id)
        self.assertEqual((r.status_code, r.json()["anzahl"]), (200, 2))
        self.assertIn("1 Kopie aus", r.json()["meldung"])
        self.assertEqual([p.pos_nr for p in self.neu(pv.id).positionen], ["PV001", "PV123"])
        self.assertEqual(self.neu(wp.id).summen()["netto"], WP_NETTO)

    def test_pv_nicht_mehr_gueltig(self):
        wp = self.wp_entwurf()
        pv = self.pv_entwurf()
        self.uebernehmen(wp.id)
        pv = self.neu(pv.id)
        pv.status = "Abgelehnt"
        self.s.commit()
        wp = self.neu(wp.id)
        self.assertIsNone(elektro_pv.knopf_sichtbar(self.s, wp))      # kein gültiges PV-Ziel
        self.assertTrue(elektro_pv.rueckholbar(self.s, wp)[0])
        html = self.client.get(f"/angebote/{wp.id}").text
        self.assertIn("Geschwister-Angebot nicht mehr gültig", html)
        self.assertIn("Elektroarbeiten zurückholen", html)
        self.assertNotIn("Elektroarbeiten ins PV-Angebot (0 % USt)", html)
        r = self.zurueckholen(wp.id)
        self.assertEqual((r.status_code, r.json()["anzahl"]), (200, 2))
        wp, pv = self.neu(wp.id), self.neu(pv.id)
        self.assertFalse(any(p.alternativ for p in wp.positionen))
        self.assertEqual(wp.summen()["netto"], WP_NETTO)
        self.assertEqual(len(pv.positionen), 3)                       # abgelehntes PV unverändert

    def test_pv_versendet_nicht_rueckholbar(self):
        wp = self.wp_entwurf()
        pv = self.pv_entwurf()
        self.uebernehmen(wp.id)
        pv = self.neu(pv.id)
        pv.status = "Versendet"
        self.s.commit()
        ok, grund = elektro_pv.rueckholbar(self.s, self.neu(wp.id))
        self.assertFalse(ok)
        self.assertIn("Versendet", grund)
        self.assertEqual(self.zurueckholen(wp.id).status_code, 409)

    def test_knopf_sichtbarkeit(self):
        wp = self.wp_entwurf()
        html = self.client.get(f"/angebote/{wp.id}").text
        self.assertNotIn("Elektroarbeiten ins PV-Angebot (0 % USt)", html)   # noch kein PV
        pv = self.pv_entwurf(status="Versendet")
        self.assertIsNone(elektro_pv.knopf_sichtbar(self.s, self.neu(wp.id)))
        pv2 = self.pv_entwurf(status="Versand vorbereitet")
        self.assertEqual(elektro_pv.knopf_sichtbar(self.s, self.neu(wp.id)).id, pv2.id)
        html = self.client.get(f"/angebote/{wp.id}").text
        self.assertIn("Elektroarbeiten ins PV-Angebot (0 % USt)", html)
        self.assertIn(f"PV-Angebot {pv2.nummer}", html)
        # PV selbst, WP „Versand vorbereitet“, KL-/WB-Entwurf
        self.assertIsNone(elektro_pv.knopf_sichtbar(self.s, self.neu(pv2.id)))
        self.assertNotIn("Elektroarbeiten ins PV-Angebot", self.client.get(f"/angebote/{pv2.id}").text)
        wp_vv = self.wp_entwurf(status="Versand vorbereitet")
        self.assertIsNone(elektro_pv.knopf_sichtbar(self.s, wp_vv))
        kl = self.kl_entwurf()
        self.assertEqual(elektro_pv.knopf_sichtbar(self.s, kl).id, pv2.id)
        wb = self.angebot("WB", [dict(sort=1, block_nr=1, gruppe="", pos_nr="WB003",
                                       bezeichnung="Anschlussvorbereitung Ladestation",
                                       beschreibung="", menge=1.0, einheit="psl.",
                                       e_preis_cent=129_720, ek_cent=80_000)])
        self.assertEqual(elektro_pv.knopf_sichtbar(self.s, wb).id, pv2.id)
        self.assertEqual([p.pos_nr for p in elektro_pv.elektro_positionen(self.s, wb)], ["WB003"])
        self.assertEqual(pv.status, "Versendet")

    def test_mehrere_sparten_eigene_gruppen(self):
        wp = self.wp_entwurf(mit_ep_bauseits=False)
        kl = self.kl_entwurf()
        pv = self.pv_entwurf()
        self.assertEqual([p.pos_nr for p in elektro_pv.elektro_positionen(self.s, kl)], ["KL008"])
        self.assertEqual(self.uebernehmen(wp.id).status_code, 200)
        r = self.post_json(self.client, f"/angebote/{kl.id}/elektro-ins-pv")
        self.assertEqual((r.status_code, r.json()["anzahl"], r.json()["netto_cent"]), (200, 1, 49_800))
        pv = self.neu(pv.id)
        gruppen = [p.gruppe for p in pv.positionen if p.uebernommen_von_angebot_id]
        self.assertEqual(gruppen, [f"Elektroarbeiten Wärmepumpe (aus Angebot {wp.nummer})"] * 2
                         + [f"Elektroarbeiten Klimaanlage (aus Angebot {kl.nummer})"])
        self.assertEqual(len({p.block_nr for p in pv.positionen if p.uebernommen_von_angebot_id}), 2)
        self.assertEqual(json.loads(pv.vermerke_json), [
            f"Enthält die Elektroarbeiten aus Angebot {wp.nummer} (Wärmepumpe).",
            f"Enthält die Elektroarbeiten aus Angebot {kl.nummer} (Klimaanlage)."])
        self.assertEqual(pv.summen()["netto"], PV_NETTO + ELEKTRO_NETTO + 49_800)
        text = pdf_text(pdf_export.pdf_fuer_angebot(self.s, pv))
        flach = " ".join(text.split())
        self.assertIn(f"Enthält die Elektroarbeiten aus Angebot {wp.nummer} (Wärmepumpe).", flach)
        self.assertIn(f"Elektroarbeiten Klimaanlage (aus Angebot {kl.nummer})", flach)
        self.assertIn("Umsatzsteuer 0 %", flach)
        # KL-Angebot: Position Alternativ „im PV-Angebot“ im PDF
        text_kl = " ".join(pdf_text(pdf_export.pdf_fuer_angebot(self.s, self.neu(kl.id))).split())
        self.assertIn("im PV-Angebot", text_kl)
        self.assertIn(f"bereits in Ihrem Angebot {pv.nummer} (PV) enthalten", text_kl)

    def test_aussendienst_darf_nicht(self):
        wp = self.wp_entwurf()
        self.pv_entwurf()
        r = self.ad_client().post(f"/angebote/{wp.id}/elektro-ins-pv",
                                  headers={"accept": "application/json"}, follow_redirects=False)
        self.assertIn(r.status_code, (303, 403))
        self.assertFalse(any(p.alternativ for p in self.neu(wp.id).positionen))

    def test_ohne_pv_meldung(self):
        wp = self.wp_entwurf()
        r = self.uebernehmen(wp.id)
        self.assertEqual(r.status_code, 409)
        self.assertIn("Kein PV-Angebot", r.json()["meldung"])
        # Redirect-Variante ohne Accept-Header
        r = self.client.post(f"/angebote/{wp.id}/elektro-ins-pv", follow_redirects=False)
        self.assertEqual(r.status_code, 303)
        self.assertIn("meldung=", r.headers["location"])

    def test_zurueckholen_bei_geloeschtem_pv(self):
        wp = self.wp_entwurf(mit_ep_bauseits=False)
        pv = self.pv_entwurf()
        self.uebernehmen(wp.id)
        pv = self.neu(pv.id)
        self.s.delete(pv)
        self.s.commit()
        wp = self.neu(wp.id)
        self.assertEqual(len(elektro_pv.ungueltige_verknuepfungen(self.s, wp)), 2)
        self.assertTrue(elektro_pv.rueckholbar(self.s, wp)[0])
        r = self.zurueckholen(wp.id)
        self.assertEqual((r.status_code, r.json()["anzahl"]), (200, 2))
        self.assertEqual(self.neu(wp.id).summen()["netto"], WP_NETTO)


if __name__ == "__main__":
    unittest.main()
