# v28 (PLAN_PROJ_V6 Phase 136, Agent P2): Notizen über alle Phasen –
# Vorgangs-Notizen-Chat als einzige Spur (Modul app/notizen.py, Makro
# notizen_chat, Schreibroute POST /vorgaenge/{id}/notiz mit JSON), Rechte-Matrix
# (Montage nur lesen), Migration der Projektakten-Kommentare (zweimal = 0 Kopien),
# Galerie-Datei-Route inline/attachment, Lightbox-Markup.
import unittest
import warnings
from datetime import datetime, timedelta
from unittest import mock

warnings.filterwarnings("ignore")

from app import galerie as galerie_modul
from app import notizen
from app.models import Benutzer, GalerieDatei, Projekt, ProjektVerlauf, VorgangsNotiz
from app.templating import templates
from tests.proj_v6_p2_basis import Basis, PRAEFIX, client_fuer, jpg_bytes


class Kennzeichen(unittest.TestCase):
    def test_kennzeichen_aus_herkunft(self):
        self.assertEqual(notizen.kennzeichen("projektierung"), ("Projektierung", "nc-projektierung"))
        self.assertEqual(notizen.kennzeichen("projektierung (migriert)"),
                         ("Projektierung", "nc-projektierung"))
        self.assertEqual(notizen.kennzeichen("lead"), ("Lead", "nc-lead"))
        self.assertEqual(notizen.kennzeichen("Anruf: nicht erreicht"), ("Lead", "nc-lead"))
        self.assertEqual(notizen.kennzeichen("vertrieb"), ("Vertrieb", "nc-vertrieb"))
        self.assertEqual(notizen.kennzeichen("montage"), ("Montage", "nc-montage"))
        self.assertEqual(notizen.kennzeichen(""), ("", ""))
        self.assertEqual(notizen.kennzeichen(None), ("", ""))
        # bestehende freie Herkunftstexte bleiben als gekürzter Badge lesbar
        self.assertEqual(notizen.kennzeichen("Galerie"), ("Galerie", "nc-sonstige"))
        self.assertEqual(notizen.kennzeichen("Kombi-Versand"), ("Vertrieb", "nc-vertrieb"))

    def test_herkunft_fuer_rolle(self):
        class B:
            def __init__(self, rolle):
                self.rolle = rolle
        self.assertEqual(notizen.herkunft_fuer(B("projektierung")), "projektierung")
        self.assertEqual(notizen.herkunft_fuer(B("leadmanagement")), "lead")
        self.assertEqual(notizen.herkunft_fuer(B("innendienst")), "vertrieb")
        self.assertEqual(notizen.herkunft_fuer(B("aussendienst"), "lead"), "lead")
        self.assertEqual(notizen.herkunft_fuer(B("aussendienst"), "unsinn"), "vertrieb")


class NotizenChat(Basis):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.gewerk = cls.gewerk_neu()
        cls.vorgang = cls.vorgang_von(cls.gewerk)
        cls.monteur = cls.benutzer_neu("Monteur N", rolle="montage")
        cls.ad = cls.benutzer_neu("AD N", rolle="aussendienst")
        cls.pj = cls.benutzer_neu("Projektierer N", rolle="projektierung")
        cls.lm = cls.benutzer_neu("Leadmanager N", rolle="leadmanagement")

    def test_vorgangsakte_schreibt_mit_json(self):
        r = self.admin.post(f"/vorgaenge/{self.vorgang.id}/notiz",
                            data={"text": "V28P2 erste Notiz"},
                            headers={"Accept": "application/json"})
        self.assertEqual(r.status_code, 200)
        daten = r.json()
        self.assertTrue(daten["ok"])
        eintrag = daten["eintrag"]
        self.assertEqual(set(eintrag), {"id", "benutzer_name", "zeit", "text",
                                        "kennzeichen", "kennzeichen_klasse"})
        self.assertEqual(eintrag["text"], "V28P2 erste Notiz")
        self.assertEqual(eintrag["kennzeichen"], "Vertrieb")
        self.assertRegex(eintrag["zeit"], r"^\d\d\.\d\d\.\d\d \d\d:\d\d$")
        # Fallback ohne JSON: Redirect in die Akte, Anker #notizen
        r = self.admin.post(f"/vorgaenge/{self.vorgang.id}/notiz",
                            data={"text": "V28P2 zweite Notiz", "herkunft": "lead"},
                            follow_redirects=False)
        self.assertEqual(r.status_code, 303)
        self.assertTrue(r.headers["location"].endswith(f"/vorgaenge/{self.vorgang.id}#notizen"))
        self.s.expire_all()
        texte = {n.text: n.herkunft for n in self.s.query(VorgangsNotiz)
                 .filter_by(vorgang_id=self.vorgang.id)}
        self.assertEqual(texte["V28P2 erste Notiz"], "vertrieb")
        self.assertEqual(texte["V28P2 zweite Notiz"], "lead")
        # Akte zeigt das Makro mit beiden Einträgen und Kennzeichen
        r = self.admin.get(f"/vorgaenge/{self.vorgang.id}")
        self.assertEqual(r.status_code, 200)
        self.assertIn(f'id="nc-{self.vorgang.id}"', r.text)
        self.assertIn("V28P2 erste Notiz", r.text)
        self.assertIn("nc-herkunft nc-lead", r.text)
        self.assertIn('class="notiz-eingabe chat-eingabe nc-eingabe"', r.text)
        self.assertIn('rows="4"', r.text)
        # leerer Text → 400 (JSON)
        r = self.admin.post(f"/vorgaenge/{self.vorgang.id}/notiz", data={"text": "  "},
                            headers={"Accept": "application/json"})
        self.assertEqual(r.status_code, 400)
        self.assertFalse(r.json()["ok"])

    def test_montage_kann_nicht_schreiben(self):
        vorher = self.s.query(VorgangsNotiz).filter_by(vorgang_id=self.vorgang.id).count()
        c = client_fuer(self.monteur.id)
        r = c.post(f"/vorgaenge/{self.vorgang.id}/notiz", data={"text": "V28P2 verboten"},
                   follow_redirects=False)
        self.assertIn(r.status_code, (303, 403))
        r = c.post(f"/vorgaenge/{self.vorgang.id}/notiz", data={"text": "V28P2 verboten"},
                   headers={"Accept": "application/json"}, follow_redirects=False)
        self.assertIn(r.status_code, (303, 403))
        self.s.expire_all()
        self.assertEqual(self.s.query(VorgangsNotiz).filter_by(vorgang_id=self.vorgang.id).count(),
                         vorher)
        self.assertFalse(notizen.schreiben_erlaubt(self.s, self.vorgang, self.monteur))

    def test_rechte_matrix(self):
        admin = self.s.get(Benutzer, 1)
        self.assertTrue(notizen.schreiben_erlaubt(self.s, self.vorgang, admin))
        # Außendienst nur an eigenen Vorgängen (ad_id / Lead / Erfassung)
        self.assertFalse(notizen.schreiben_erlaubt(self.s, self.vorgang, self.ad))
        self.vorgang.ad_id = self.ad.id
        self.s.commit()
        self.assertTrue(notizen.schreiben_erlaubt(self.s, self.vorgang, self.ad))
        self.vorgang.ad_id = None
        self.s.commit()
        # Projektierung: Vorgang hat ein Projekt (Modul für die Hauptrolle sichtbar)
        self.assertTrue(notizen.schreiben_erlaubt(self.s, self.vorgang, self.pj))
        projekt = self.s.get(Projekt, self.gewerk.projekt_id)
        projekt.vorgang_id = None
        self.s.commit()
        try:
            self.assertFalse(notizen.schreiben_erlaubt(self.s, self.vorgang, self.pj))
        finally:
            projekt.vorgang_id = self.vorgang.id
            self.s.commit()
        # Leadmanagement: nur wenn das Lead-Modul für den Benutzer sichtbar ist
        with mock.patch("app.leadmanagement.lead_modul_sichtbar", return_value=True):
            self.assertTrue(notizen.schreiben_erlaubt(self.s, self.vorgang, self.lm))
        with mock.patch("app.leadmanagement.lead_modul_sichtbar", return_value=False):
            self.assertFalse(notizen.schreiben_erlaubt(self.s, self.vorgang, self.lm))
        self.assertFalse(notizen.schreiben_erlaubt(self.s, None, admin))
        self.assertFalse(notizen.schreiben_erlaubt(self.s, self.vorgang, None))

    def test_kommentar_speichern_projektakte(self):
        projekt = self.s.get(Projekt, self.gewerk.projekt_id)
        admin = self.s.get(Benutzer, 1)
        vorher_verlauf = self.s.query(ProjektVerlauf).filter_by(
            projekt_id=projekt.id, art="kommentar").count()
        ok, meldung = notizen.kommentar_speichern(self.s, projekt, admin, " V28P2 Kommentar ")
        self.s.commit()
        self.assertTrue(ok, meldung)
        notiz = (self.s.query(VorgangsNotiz)
                 .filter_by(vorgang_id=self.vorgang.id, text="V28P2 Kommentar").one())
        self.assertEqual(notiz.herkunft, "projektierung")
        self.assertEqual(notiz.benutzer_name, admin.name)
        # kein neuer ProjektVerlauf mit art = kommentar durch das Modul
        self.assertEqual(self.s.query(ProjektVerlauf).filter_by(
            projekt_id=projekt.id, art="kommentar").count(), vorher_verlauf)
        self.assertEqual(notizen.kommentar_speichern(self.s, projekt, admin, "   "),
                         (False, "Bitte einen Text eingeben."))
        # Projekt ohne Vorgang (Altbestand): bisheriger Weg
        projekt.vorgang_id = None
        try:
            ok, meldung = notizen.kommentar_speichern(self.s, projekt, admin, "x")
            self.assertFalse(ok)
            self.assertEqual(meldung, "Kein Vorgang – Kommentar nur im Projektverlauf")
            self.assertIsNone(notizen.kontext_projekt(self.s, projekt, admin))
        finally:
            projekt.vorgang_id = self.vorgang.id
            self.s.commit()
        ctx = notizen.kontext_projekt(self.s, projekt, admin)
        self.assertEqual(ctx["post_url"], f"/projektierung/projekt/{projekt.id}/kommentar")

    def test_kontext_limit_und_makro(self):
        admin = self.s.get(Benutzer, 1)
        for i in range(7):
            notizen.notiz_anlegen(self.s, self.vorgang.id, admin, f"V28P2 Limit {i}",
                                  herkunft="projektierung")
        self.s.commit()
        ctx = notizen.kontext(self.s, self.vorgang.id, self.monteur, limit=5,
                              nur_lesen=True, hinweis="Bemerkungen bitte im Montagebericht eintragen.")
        self.assertGreaterEqual(ctx["anzahl"], 7)
        self.assertEqual(ctx["limit"], 5)
        self.assertFalse(ctx["schreiben_erlaubt"])
        self.assertEqual(ctx["hinweis"], "Bemerkungen bitte im Montagebericht eintragen.")
        html = templates.env.get_template("_komponenten.html").module.notizen_chat(ctx)
        self.assertIn("alle anzeigen · ", html)
        self.assertIn("V28P2 Limit 6", html)
        self.assertNotIn("<form", html)
        self.assertIn("Bemerkungen bitte im Montagebericht eintragen.", html)
        # Schreibfähiger Kontext: Formular mit Textarea 4 Zeilen, kein Hinweis
        ctx2 = notizen.kontext(self.s, self.vorgang.id, admin, hinweis="x")
        self.assertTrue(ctx2["schreiben_erlaubt"])
        self.assertEqual(ctx2["hinweis"], "")
        self.assertEqual(ctx2["limit"], 0)
        html2 = templates.env.get_template("_komponenten.html").module.notizen_chat(ctx2)
        self.assertIn('rows="4"', html2)
        self.assertNotIn("alle anzeigen", html2)
        self.assertIn('nc-herkunft nc-projektierung', html2)

    def test_eintrag_json_format(self):
        admin = self.s.get(Benutzer, 1)
        n = notizen.notiz_anlegen(self.s, self.vorgang.id, admin, "V28P2 JSON", herkunft="montage")
        self.s.commit()
        daten = notizen.eintrag_json(n)
        self.assertEqual(daten["kennzeichen"], "Montage")
        self.assertEqual(daten["kennzeichen_klasse"], "nc-montage")
        self.assertEqual(daten["zeit"], n.zeit.strftime("%d.%m.%y %H:%M"))


class Migration(Basis):
    def test_migration_zweimal(self):
        gewerk = self.gewerk_neu()
        vorgang = self.vorgang_von(gewerk)
        projekt = self.s.get(Projekt, gewerk.projekt_id)
        zeit = datetime(2026, 10, 1, 9, 15, 30)
        self.s.add(ProjektVerlauf(projekt_id=projekt.id, gewerk_id=gewerk.id, art="kommentar",
                                  text="V28P2 alter Kommentar 1", benutzer_id=1,
                                  erstellt_am=zeit))
        self.s.add(ProjektVerlauf(projekt_id=projekt.id, art="kommentar",
                                  text="V28P2 alter Kommentar 2", benutzer_id=None,
                                  erstellt_am=zeit + timedelta(minutes=5)))
        self.s.add(ProjektVerlauf(projekt_id=projekt.id, art="system",
                                  text="V28P2 Systemeintrag", erstellt_am=zeit))
        # Projekt ohne Vorgang (Altbestand) wird übersprungen
        kunde_id = projekt.kunde_id
        alt = Projekt(nummer=f"{PRAEFIX}-ALT-{projekt.id}", vorgang_id=None, kunde_id=kunde_id,
                      projektleiter_id=1)
        self.s.add(alt)
        self.s.flush()
        self.s.add(ProjektVerlauf(projekt_id=alt.id, art="kommentar",
                                  text="V28P2 ohne Vorgang", erstellt_am=zeit))
        self.s.commit()
        vorher = self.s.query(VorgangsNotiz).filter_by(vorgang_id=vorgang.id).count()
        meldungen = notizen.migration_v28_notizen(self.s)
        self.s.commit()
        self.assertEqual(len(meldungen), 1)
        self.assertIn("Projektakten-Kommentar", meldungen[0])
        self.assertIn("ohne Vorgang übersprungen", meldungen[0])
        kopien = (self.s.query(VorgangsNotiz)
                  .filter(VorgangsNotiz.vorgang_id == vorgang.id,
                          VorgangsNotiz.herkunft == notizen.MIGRIERT_HERKUNFT)
                  .order_by(VorgangsNotiz.zeit).all())
        self.assertEqual(len(kopien), 2)
        self.assertEqual(self.s.query(VorgangsNotiz).filter_by(vorgang_id=vorgang.id).count(),
                         vorher + 2)
        self.assertEqual(kopien[0].zeit, zeit)
        self.assertEqual(kopien[0].benutzer_id, 1)
        self.assertEqual(kopien[0].benutzer_name, "Admin")
        self.assertEqual(kopien[1].benutzer_name, "System")
        self.assertEqual(notizen.kennzeichen(kopien[0].herkunft)[0], "Projektierung")
        # Original bleibt
        self.assertEqual(self.s.query(ProjektVerlauf).filter_by(
            projekt_id=projekt.id, art="kommentar").count(), 2)
        # zweiter Lauf: 0 Kopien, keine Meldung
        self.assertEqual(notizen.migration_v28_notizen(self.s), [])
        self.s.commit()
        self.assertEqual(self.s.query(VorgangsNotiz).filter_by(vorgang_id=vorgang.id).count(),
                         vorher + 2)
        self.s.query(ProjektVerlauf).filter_by(projekt_id=alt.id).delete()
        self.s.delete(alt)
        self.s.commit()


class GalerieLightbox(Basis):
    def test_datei_inline_und_download(self):
        gewerk = self.gewerk_neu()
        vorgang = self.vorgang_von(gewerk)
        admin = self.s.get(Benutzer, 1)
        bild = galerie_modul.speichern(self.s, vorgang.id, "Außengerät", "V28P2-test.jpg",
                                       jpg_bytes(), benutzer=admin, bemerkung="V28P2 Test",
                                       sparte="WP")
        pdf = galerie_modul.speichern(self.s, vorgang.id, "Allgemein", "V28P2-test.pdf",
                                      b"%PDF-1.4\n%V28P2\n", benutzer=admin, sparte="WP")
        tabelle = galerie_modul.speichern(self.s, vorgang.id, "Allgemein", "V28P2-test.ugl",
                                          b"UGL", benutzer=admin, sparte="WP")
        self.s.commit()
        r = self.admin.get(f"/vorgaenge/galerie/datei/{bild.id}")
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.headers["content-disposition"].startswith("inline"))
        self.assertIn("image/jpeg", r.headers["content-type"])
        r = self.admin.get(f"/vorgaenge/galerie/datei/{bild.id}?download=1")
        self.assertTrue(r.headers["content-disposition"].startswith("attachment"))
        r = self.admin.get(f"/vorgaenge/galerie/datei/{pdf.id}")
        self.assertTrue(r.headers["content-disposition"].startswith("inline"))
        r = self.admin.get(f"/vorgaenge/galerie/datei/{tabelle.id}")
        self.assertTrue(r.headers["content-disposition"].startswith("attachment"))
        self.assertTrue(galerie_modul.inline_anzeige("x.JPG"))
        self.assertTrue(galerie_modul.inline_anzeige("x.pdf"))
        self.assertFalse(galerie_modul.inline_anzeige("x.ugl"))
        self.assertEqual(galerie_modul.datei_url(5, True), "/vorgaenge/galerie/datei/5?download=1")
        # Lightbox-Markup in der Vorgangsakte: Gruppe je Ordner, Download-Knopf, Dialog
        r = self.admin.get(f"/vorgaenge/{vorgang.id}")
        self.assertEqual(r.status_code, 200)
        self.assertIn(f'data-lb-gruppe="{vorgang.id}/WP/Außengerät"', r.text)
        self.assertIn('data-lb-bemerkung="V28P2 Test"', r.text)
        self.assertIn('onclick="return pjLightbox(event, this)"', r.text)
        self.assertIn('id="pj-lightbox"', r.text)
        self.assertIn('class="pj-lb-nav zurueck"', r.text)
        self.assertIn("pjLightboxSchritt(1)", r.text)
        self.assertIn(f'href="/vorgaenge/galerie/datei/{pdf.id}?download=1" download', r.text)
        self.assertEqual(r.text.count('id="pj-lightbox"'), 1)
        self.assertEqual(self.s.query(GalerieDatei).filter_by(vorgang_id=vorgang.id).count(), 3)


if __name__ == "__main__":
    unittest.main()
