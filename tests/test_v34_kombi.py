# v34 (PLAN_V21 Phase 180, Agent V): Kombi-Versand verständlich – Kasten „Gemeinsam versenden“
# in der Vorgangsakte (Häkchen an allen versandfähigen Angeboten: Entwurf, Versand vorbereitet,
# TAIFUN-Eintrag mit PDF; nicht wählbare ausgegraut mit Grund, Vorauswahl ?kombi=<id>), Knopf
# „Kombi-Versand vorbereiten (n Angebote)“: Entwürfe werden automatisch auf „Versand
# vorbereitet“ gesetzt (Verlaufsnotiz „durch Kombi-Versand“), dann EINE Mail mit mehreren PDFs.
# Kontrollwert des Plans: WP-Entwurf + PV „Versand vorbereitet“ + TAIFUN-Eintrag mit PDF → drei
# Häkchen; alle drei → WP automatisch „Versand vorbereitet“, eine Mail mit drei PDFs.
# Graph und PDF-Erzeugung sind gemockt – es wird nie eine echte Mail erzeugt.
import datetime
import re
import unittest
import warnings
from pathlib import Path
from unittest import mock
from urllib.parse import unquote_plus

warnings.filterwarnings("ignore")

from fastapi.testclient import TestClient
from sqlalchemy import func

from app import angebot_aufbau, auth, config, graph_versand, kombi_versand
from app import vorgaenge as vorgaenge_modul
from app.db import SessionLocal, init_db
from app.main import app
from app.models import (Angebot, AngebotsNotiz, Benutzer, Erfassung, Kunde, Vorgang,
                        VorgangsNotiz)

TEST_EMAIL = "v34v-kombi@test.local"
PRAEFIX = "V34V "


def _aufraeumen(s):
    s.rollback()
    for k in s.query(Kunde).filter(Kunde.email == TEST_EMAIL):
        for a in s.query(Angebot).filter_by(kunde_id=k.id):
            s.query(AngebotsNotiz).filter(AngebotsNotiz.angebot_id == a.id).delete()
            if a.extern_pdf_pfad:
                Path(a.extern_pdf_pfad).unlink(missing_ok=True)
            s.delete(a)
        for e in s.query(Erfassung).filter_by(kunde_id=k.id):
            s.delete(e)
        for v in s.query(Vorgang).filter_by(kunde_id=k.id):
            s.query(VorgangsNotiz).filter(VorgangsNotiz.vorgang_id == v.id).delete()
            s.delete(v)
        s.delete(k)
    for b in s.query(Benutzer).filter(Benutzer.name.like(f"{PRAEFIX}%")):
        s.delete(b)
    s.commit()


def _transient(status, extern=False, pdf=""):
    return Angebot(nummer="AN-C-TEST", status=status, extern=extern, extern_pdf_pfad=pdf,
                   konfigurator_typ="WP")


class Waehlbar(unittest.TestCase):
    """kombi_versand.waehlbar / auswahl ohne Datenbank."""

    def test_status_matrix(self):
        self.assertEqual(kombi_versand.waehlbar(_transient("Entwurf")), (True, ""))
        self.assertEqual(kombi_versand.waehlbar(_transient("Versand vorbereitet")), (True, ""))
        for status in ("Versendet", "Angenommen", "Abgelehnt", "Überholt", "Individuell"):
            ok, grund = kombi_versand.waehlbar(_transient(status))
            self.assertFalse(ok, status)
            self.assertTrue(grund, status)
        # TAIFUN: nur Versendet (extern) mit vorhandenem PDF
        ok, grund = kombi_versand.waehlbar(_transient("Versendet (extern)", extern=True))
        self.assertEqual((ok, grund), (False, kombi_versand.GRUND_PDF_FEHLT))
        self.assertIn("PDF fehlt", grund)
        ok, grund = kombi_versand.waehlbar(_transient("Versendet (extern)", extern=True,
                                                      pdf="C:/gibt/es/nicht.pdf"))
        self.assertEqual((ok, grund), (False, kombi_versand.GRUND_PDF_FEHLT))
        ok, grund = kombi_versand.waehlbar(_transient("Angenommen", extern=True, pdf=__file__))
        self.assertFalse(ok)
        self.assertIn("Angenommen", grund)
        self.assertEqual(kombi_versand.waehlbar(_transient("Versendet (extern)", extern=True,
                                                           pdf=__file__)), (True, ""))

    def test_auswahl_vorauswahl_und_kennzeichen(self):
        entwurf = _transient("Entwurf")
        entwurf.id = 7
        taifun = _transient("Versendet (extern)", extern=True)
        taifun.id = 8
        taifun.taifun_nummer = "AN261737"
        zeilen = kombi_versand.auswahl([entwurf, taifun], vorauswahl_id=7)
        self.assertEqual([z["id"] for z in zeilen], [7, 8])
        self.assertTrue(zeilen[0]["waehlbar"] and zeilen[0]["vorgewaehlt"] and zeilen[0]["entwurf"])
        self.assertEqual(zeilen[1]["nummer"], "AN261737")
        self.assertTrue(zeilen[1]["pdf_fehlt"] and zeilen[1]["extern"] and not zeilen[1]["waehlbar"])
        # Vorauswahl eines nicht wählbaren Angebots wird ignoriert
        self.assertFalse(kombi_versand.auswahl([taifun], vorauswahl_id=8)[0]["vorgewaehlt"])


class KastenUndRoute(unittest.TestCase):
    """Vorgangsakte: Kasten „Gemeinsam versenden“ + POST /vorgaenge/{id}/kombi-versand."""

    @classmethod
    def setUpClass(cls):
        init_db()
        cls.s = SessionLocal()
        _aufraeumen(cls.s)
        s = cls.s
        cls.kunde = Kunde(anrede="Frau", vorname="Karla", nachname=f"{PRAEFIX}Kombi",
                          strasse="Testweg 3", plz="47139", ort="Duisburg", email=TEST_EMAIL)
        s.add(cls.kunde)
        s.commit()
        cls.vorgang = vorgaenge_modul.vorgang_fuer_kunde(s, cls.kunde.id)
        s.commit()
        cls.wp = angebot_aufbau.angebot_anlegen(s, cls.kunde.id, sparte="WP")      # Entwurf
        cls.pv = angebot_aufbau.angebot_anlegen(s, cls.kunde.id, sparte="PV")
        cls.pv.status = "Versand vorbereitet"
        cls.alt = angebot_aufbau.angebot_anlegen(s, cls.kunde.id, sparte="KL")
        cls.alt.status = "Versendet"
        for a in (cls.wp, cls.pv, cls.alt):
            a.vorgang_id = cls.vorgang.id
        # TAIFUN-Einträge: einer mit PDF, einer ohne
        ordner = config.ANGEBOTE_PDF_ORDNER / "extern"
        ordner.mkdir(parents=True, exist_ok=True)
        cls.pdf_pfad = ordner / "V34V-KOMBI.pdf"
        cls.pdf_pfad.write_bytes(b"%PDF-1.4 v34v kombi")
        cls.taifun = Angebot(nummer="EXT-V34V-1", kunde_id=cls.kunde.id, extern=True,
                             status="Versendet (extern)", datum=datetime.datetime.now(),
                             konfigurator_typ="WB", extern_endbetrag_cent=266048,
                             taifun_nummer="AN261737", extern_pdf_pfad=str(cls.pdf_pfad),
                             extern_pdf_am=datetime.datetime.now(), vorgang_id=cls.vorgang.id)
        cls.taifun_ohne = Angebot(nummer="EXT-V34V-2", kunde_id=cls.kunde.id, extern=True,
                                  status="Versendet (extern)", datum=datetime.datetime.now(),
                                  konfigurator_typ="KL", extern_endbetrag_cent=100000,
                                  taifun_nummer="AN261738", vorgang_id=cls.vorgang.id)
        s.add_all([cls.taifun, cls.taifun_ohne])
        s.commit()
        cls.client = TestClient(app)
        cls.client.cookies.set(auth.COOKIE_NAME, auth.cookie_wert(1))

    @classmethod
    def tearDownClass(cls):
        _aufraeumen(cls.s)
        cls.pdf_pfad.unlink(missing_ok=True)
        cls.s.close()

    def _kasten(self, query=""):
        seite = self.client.get(f"/vorgaenge/{self.vorgang.id}{query}")
        self.assertEqual(seite.status_code, 200)
        html = seite.text
        start = html.index('id="gemeinsam-versenden"')
        return html, html[start:html.index("</section>", start)]

    def _zeile(self, kasten, angebot_id):
        for stueck in kasten.split("<li ")[1:]:
            if f'value="{angebot_id}"' in stueck:
                return "<li " + stueck[:stueck.index("</li>")]
        self.fail(f"Zeile für Angebot {angebot_id} fehlt im Kasten")

    def test_kasten_zeigt_drei_haekchen_und_gruende(self):
        html, kasten = self._kasten()
        self.assertIn("Gemeinsam versenden", kasten)
        self.assertIn("Alle angehakten Angebote gehen als separate PDFs in einer Mail an den Kunden;",
                      kasten)
        self.assertIn("Entwürfe werden dabei automatisch versandfertig gemacht.", kasten)
        self.assertIn("Kombi-Versand vorbereiten (", kasten)
        aktiv = [int(w) for w in re.findall(
            r'<input type="checkbox" name="angebot_ids" value="(\d+)"(?![^>]*disabled)', kasten)]
        self.assertEqual(sorted(aktiv), sorted([self.wp.id, self.pv.id, self.taifun.id]))
        # Entwurf trägt den Hinweis, der versendete KL-Eintrag und der TAIFUN ohne PDF sind gesperrt
        self.assertIn("wird automatisch versandfertig gemacht", self._zeile(kasten, self.wp.id))
        self.assertNotIn("wird automatisch versandfertig gemacht", self._zeile(kasten, self.pv.id))
        alt = self._zeile(kasten, self.alt.id)
        self.assertIn("disabled", alt)
        self.assertIn("Bereits versendet", alt)
        ohne = self._zeile(kasten, self.taifun_ohne.id)
        self.assertIn("disabled", ohne)
        self.assertIn("PDF fehlt", ohne)
        # keine Häkchen mehr an den Angebots-Karten (nur im Kasten)
        karten = html[:html.index('id="gemeinsam-versenden"')]
        self.assertNotIn('name="angebot_ids"', karten)
        # Drop-Zone am TAIFUN-Eintrag in der Akte
        self.assertIn('data-modus="eintrag"', html)
        self.assertIn("/static/vorgang_v34.css", html)

    def test_vorauswahl_aus_dem_editor(self):
        _, kasten = self._kasten(f"?kombi={self.pv.id}")
        self.assertIn("checked", self._zeile(kasten, self.pv.id))
        self.assertNotIn("checked", self._zeile(kasten, self.wp.id))
        # nicht wählbares Angebot wird nicht vorgehakt
        _, kasten = self._kasten(f"?kombi={self.alt.id}")
        self.assertNotIn("checked", self._zeile(kasten, self.alt.id))

    def _kombi(self, ids, erfolg=True, pdf_fehlt=False):
        aufrufe = {}

        def fake_entwurf(kunde, angebot_, pdf_pfad, betreff, text, **kw):
            aufrufe.update(kw, betreff=betreff, text=text, pdf=pdf_pfad, angebot=angebot_)
            if not erfolg:
                return False, "Graph-Fehler (Test).", "", ""
            return True, "Entwurf im Postfach abgelegt – Test.", "https://outlook/x", "konv-v34-kombi"

        erzeugt = []

        def fake_pdf(session, angebot, **kw):     # v36: pdf_fuer_angebot(..., benutzer=)
            pfad = config.ANGEBOTE_PDF_ORDNER / f"{angebot.nummer}.pdf"
            pfad.write_bytes(b"%PDF-1.4 " + angebot.nummer.encode())
            erzeugt.append(pfad)
            return pfad

        self.s.commit()
        with mock.patch.object(graph_versand, "konfiguriert", return_value=True), \
                mock.patch.object(graph_versand, "angemeldeter_benutzer", return_value="ida@friondo.de"), \
                mock.patch.object(graph_versand, "entwurf_erstellen", side_effect=fake_entwurf), \
                mock.patch("app.pdf_export.pdf_fuer_angebot", side_effect=fake_pdf), \
                mock.patch("app.anhaenge.fuer_angebot", return_value=[]):
            antwort = self.client.post(f"/vorgaenge/{self.vorgang.id}/kombi-versand",
                                       data={"angebot_ids": [str(i) for i in ids]},
                                       follow_redirects=False)
        for pfad in erzeugt:
            pfad.unlink(missing_ok=True)
        self.s.expire_all()
        return antwort, aufrufe

    def test_drei_angebote_eine_mail_entwurf_automatisch_vorbereitet(self):
        antwort, aufrufe = self._kombi([self.wp.id, self.pv.id, self.taifun.id])
        self.assertEqual(antwort.status_code, 303)
        ziel = unquote_plus(antwort.headers["location"])
        self.assertIn("Kombi-Entwurf für", ziel)
        self.assertIn(f"Automatisch auf „Versand vorbereitet“ gesetzt: {self.wp.nummer}", ziel)
        # eine Mail mit drei Angebots-PDFs (erstes als Hauptanhang, zwei weitere)
        anhaenge = [aufrufe["pdf"].name] + [p.name for p in aufrufe["weitere_anhaenge"]]
        self.assertEqual(sorted(anhaenge),
                         sorted([f"{self.wp.nummer}.pdf", f"{self.pv.nummer}.pdf", self.pdf_pfad.name]))
        self.assertIn("Ihre Angebote", aufrufe["betreff"])
        self.assertIn("WB-Angebot AN261737", aufrufe["text"])
        wp = self.s.get(Angebot, self.wp.id)
        pv = self.s.get(Angebot, self.pv.id)
        self.assertEqual((wp.status, pv.status), ("Versand vorbereitet", "Versand vorbereitet"))
        self.assertEqual(wp.graph_conversation_id, "konv-v34-kombi")
        self.assertEqual(self.s.get(Angebot, self.taifun.id).status, "Versendet (extern)")
        # Verlaufsnotiz „durch Kombi-Versand“ nur am umgestellten Entwurf
        notizen_wp = [n.text for n in self.s.query(AngebotsNotiz).filter_by(angebot_id=wp.id)]
        self.assertTrue(any("durch Kombi-Versand" in t for t in notizen_wp), notizen_wp)
        notizen_pv = [n.text for n in self.s.query(AngebotsNotiz).filter_by(angebot_id=pv.id)]
        self.assertFalse(any("durch Kombi-Versand" in t for t in notizen_pv), notizen_pv)
        # Vorgangs-Chat: Kombi-Notiz mit den automatisch vorbereiteten Angeboten
        chat = [n.text for n in self.s.query(VorgangsNotiz).filter_by(vorgang_id=self.vorgang.id)]
        self.assertTrue(any("Kombi-Versand vorbereitet" in t and self.wp.nummer in t
                            and "Automatisch auf „Versand vorbereitet“ gesetzt" in t for t in chat), chat)
        # zurück auf Entwurf für die folgenden Tests
        wp.status = "Entwurf"
        wp.graph_conversation_id = None
        self.s.commit()

    def test_graph_fehler_laesst_entwurf_entwurf(self):
        vorher = self.s.query(AngebotsNotiz).filter_by(angebot_id=self.wp.id).count()
        antwort, _ = self._kombi([self.wp.id, self.pv.id], erfolg=False)
        self.assertEqual(antwort.status_code, 303)
        self.assertIn("Graph-Fehler", unquote_plus(antwort.headers["location"]))
        wp = self.s.get(Angebot, self.wp.id)
        self.assertEqual(wp.status, "Entwurf")
        self.assertIsNone(wp.graph_conversation_id)
        # keine neue Verlaufsnotiz „durch Kombi-Versand“ (Zahl unverändert)
        self.assertEqual(self.s.query(AngebotsNotiz).filter_by(angebot_id=wp.id).count(), vorher)

    def test_nicht_waehlbare_werden_abgewiesen(self):
        antwort, aufrufe = self._kombi([self.wp.id, self.taifun_ohne.id])
        ziel = unquote_plus(antwort.headers["location"])
        self.assertIn("PDF fehlt", ziel)
        self.assertEqual(aufrufe, {})          # kein Graph-Aufruf
        antwort, aufrufe = self._kombi([self.wp.id, self.alt.id])
        self.assertIn("Bereits versendet", unquote_plus(antwort.headers["location"]))
        self.assertEqual(aufrufe, {})
        antwort, aufrufe = self._kombi([self.wp.id])
        self.assertIn("mindestens zwei", unquote_plus(antwort.headers["location"]))
        self.assertEqual(self.s.get(Angebot, self.wp.id).status, "Entwurf")

    def test_aussendienst_sieht_keinen_kasten(self):
        s = self.s
        ad = Benutzer(id=(s.query(func.max(Benutzer.id)).scalar() or 0) + 1000,
                      name=f"{PRAEFIX}Aussendienst", rolle="aussendienst", aktiv=True,
                      email="v34v-kombi-ad@test.local", pin_hash=auth.pin_hash("4321"))
        s.add(ad)
        vorgang = s.get(Vorgang, self.vorgang.id)
        vorgang.ad_id = ad.id
        s.commit()
        try:
            client = TestClient(app)
            client.cookies.set(auth.COOKIE_NAME, auth.cookie_wert(ad.id))
            seite = client.get(f"/vorgaenge/{self.vorgang.id}")
            self.assertEqual(seite.status_code, 200)
            self.assertNotIn('id="gemeinsam-versenden"', seite.text)
            self.assertNotIn('data-modus="eintrag"', seite.text)
            # Kombi-Route für den Außendienst gesperrt
            antwort = client.post(f"/vorgaenge/{self.vorgang.id}/kombi-versand",
                                  data={"angebot_ids": [str(self.wp.id), str(self.pv.id)]},
                                  follow_redirects=False)
            self.assertEqual(antwort.status_code, 303)
            self.assertEqual(antwort.headers["location"], "/vorgaenge")
        finally:
            vorgang.ad_id = None
            s.delete(ad)
            s.commit()


if __name__ == "__main__":
    unittest.main()
