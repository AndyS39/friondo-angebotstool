# Tests PLAN_LEAD_V6 (v35, Agent G) – Phase 186 „Fotos je Objekt“ und Phase 187 Test (q):
# Galerie-Ordner je Objekt („Objekt“ bei einem Objekt, sonst „Objekt <Bezeichnung>“), Upload
# direkt an der Objektkarte der Kundenkartei (POST /lead-management/lead/{id}/objekt/{oid}/fotos:
# mehrere Dateien, JPG/PNG/HEIC → JPG, max. 10 MB je Bild), Löschen durch Hochladenden/ID/Admin,
# Zuordnung „Objekt“ beim Galerie-Upload und beim Einsortieren, Anzeige in Erfassung
# (Sparten-Start, Übersicht) und Projektakte, Umbenennung/Alt-Namen, Rechte (AD eigener Lead ja,
# fremder 403). Läuft gegen die DB-Kopie (DB_PFAD_OVERRIDE/DATA_ORDNER); Testdaten tragen die
# E-Mail v35g-objektfotos@test.local bzw. den Benutzer-Präfix „V35G“ und werden aufgeräumt.
import io
import json
import re
import unittest
import warnings
from pathlib import Path
from unittest import mock

warnings.filterwarnings("ignore")

from fastapi.testclient import TestClient

from app import angebot_aufbau, auth, config, lead_kartei, lead_v2
from app import galerie as galerie_modul
from app import objekte as objekte_modul
from app import projektierung as kern
from app import vorgaenge as vorgaenge_modul
from app.db import SessionLocal, init_db
from app.main import app
from app.models import (Angebot, AngebotsPosition, Aufgabe, AufgabenpaketInstanz, Benutzer,
                        Erfassung, GalerieDatei, Gewerk, Kunde, LeadAktivitaet, Projekt,
                        ProjektTermin, ProjektVerlauf, SteckbriefWert, TerminBesetzung, Vorgang,
                        VorgangNotizGelesen, VorgangObjekt, VorgangsNotiz, angebot_status_setzen)

PROJEKT = Path(__file__).resolve().parents[1]
PRAEFIX = "V35G"
TEST_EMAIL = "v35g-objektfotos@test.local"


def jpg_bytes(groesse=(120, 80), farbe=(200, 40, 40)) -> bytes:
    from PIL import Image
    puffer = io.BytesIO()
    Image.new("RGB", groesse, farbe).save(puffer, format="JPEG")
    return puffer.getvalue()


def png_bytes(groesse=(60, 40)) -> bytes:
    from PIL import Image
    puffer = io.BytesIO()
    Image.new("RGB", groesse, (20, 120, 220)).save(puffer, format="PNG")
    return puffer.getvalue()


def heic_bytes(groesse=(64, 48)) -> bytes:
    """HEIC-Attrappe über pillow_heif (Phase 187 Test q)."""
    import pillow_heif
    from PIL import Image
    pillow_heif.register_heif_opener()
    puffer = io.BytesIO()
    Image.new("RGB", groesse, (10, 200, 30)).save(puffer, format="HEIF", quality=80)
    return puffer.getvalue()


def client_fuer(benutzer_id: int) -> TestClient:
    c = TestClient(app, follow_redirects=False)
    c.cookies.set(auth.COOKIE_NAME, auth.cookie_wert(benutzer_id))
    return c


def aufraeumen(s) -> None:
    for k in s.query(Kunde).filter(Kunde.email == TEST_EMAIL):
        for p in s.query(Projekt).filter_by(kunde_id=k.id):
            for g in s.query(Gewerk).filter_by(projekt_id=p.id):
                s.query(Aufgabe).filter_by(gewerk_id=g.id).delete()
                s.query(AufgabenpaketInstanz).filter_by(gewerk_id=g.id).delete()
                s.query(SteckbriefWert).filter_by(gewerk_id=g.id).delete()
                s.delete(g)
            for t in s.query(ProjektTermin).filter_by(projekt_id=p.id):
                s.query(TerminBesetzung).filter_by(termin_id=t.id).delete()
                s.delete(t)
            s.query(ProjektVerlauf).filter_by(projekt_id=p.id).delete()
            s.delete(p)
        for a in s.query(Angebot).filter_by(kunde_id=k.id):
            s.delete(a)
        for e in s.query(Erfassung).filter_by(kunde_id=k.id):
            s.delete(e)
        for v in s.query(Vorgang).filter_by(kunde_id=k.id):
            for d in s.query(GalerieDatei).filter_by(vorgang_id=v.id):
                (config.DATA_ORDNER / d.pfad).unlink(missing_ok=True)
                s.delete(d)
            s.query(VorgangsNotiz).filter_by(vorgang_id=v.id).delete()
            s.query(VorgangNotizGelesen).filter_by(vorgang_id=v.id).delete()
            s.query(LeadAktivitaet).filter_by(vorgang_id=v.id).delete()
            s.query(VorgangObjekt).filter_by(vorgang_id=v.id).delete()
            ordner = config.DATA_ORDNER / "vorgaenge" / str(v.id)
            if ordner.exists():
                for datei in ordner.rglob("*"):
                    if datei.is_file():
                        datei.unlink(missing_ok=True)
                for leer in sorted((p for p in ordner.rglob("*") if p.is_dir()), reverse=True):
                    try:
                        leer.rmdir()
                    except OSError:
                        pass
                try:
                    ordner.rmdir()
                except OSError:
                    pass
            s.delete(v)
        s.delete(k)
    for b in s.query(Benutzer).filter(Benutzer.name.like(f"{PRAEFIX}%")):
        s.query(VorgangNotizGelesen).filter_by(benutzer_id=b.id).delete()
        s.delete(b)
    s.commit()


class Basis(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        init_db()
        cls.s = SessionLocal()
        aufraeumen(cls.s)
        cls.admin = client_fuer(1)
        cls.admin_benutzer = cls.s.get(Benutzer, 1)
        cls.ad = cls.benutzer_neu("AD", "aussendienst")
        cls.ad_fremd = cls.benutzer_neu("AD fremd", "aussendienst")
        cls.innendienst = cls.benutzer_neu("Innendienst", "innendienst")
        cls.leadmanager = cls.benutzer_neu("Leadmanager", "leadmanagement")
        # Vorgang 1: ein Objekt (Hauptobjekt = Kundenadresse), AD zuständig
        cls.kunde1, cls.vorgang1 = cls.vorgang_neu("Ein-Objekt")
        cls.haupt1 = objekte_modul.hauptobjekt(cls.s, cls.vorgang1.id, anlegen=True, kunde=cls.kunde1)
        # Vorgang 2: zwei Objekte („Objekt 1“ = Kundenadresse, „Scheune“), AD zuständig
        cls.kunde2, cls.vorgang2 = cls.vorgang_neu("Zwei-Objekte")
        cls.haupt2 = objekte_modul.hauptobjekt(cls.s, cls.vorgang2.id, anlegen=True, kunde=cls.kunde2)
        cls.objekt2 = objekte_modul.objekt_anlegen(cls.s, cls.vorgang2, "Nebenweg 2", "47269",
                                                   "Duisburg", bezeichnung="Scheune",
                                                   objektart="EFH", interessen=["PV"])
        cls.s.commit()

    @classmethod
    def tearDownClass(cls):
        aufraeumen(cls.s)
        cls.s.close()

    @classmethod
    def benutzer_neu(cls, name: str, rolle: str) -> Benutzer:
        b = Benutzer(name=f"{PRAEFIX} {name}", rolle=rolle, aktiv=True,
                     pin_hash=auth.pin_hash("1234"),
                     email=f"{name.lower().replace(' ', '')}@v35g.test")
        cls.s.add(b)
        cls.s.commit()
        return b

    @classmethod
    def vorgang_neu(cls, nachname: str):
        kunde = Kunde(anrede="Herr", vorname="Olaf", nachname=f"{PRAEFIX} {nachname}",
                      strasse="Im Knick 36", plz="47269", ort="Duisburg", email=TEST_EMAIL,
                      interesse="WP")
        cls.s.add(kunde)
        cls.s.flush()
        vorgang = vorgaenge_modul.vorgang_fuer_kunde(cls.s, kunde.id)
        vorgang.ad_id = cls.ad.id
        cls.s.commit()
        return kunde, vorgang

    # --- Helfer ----------------------------------------------------------------------
    def frisch(self):
        self.s.expire_all()

    def dateien(self, vorgang_id: int) -> list[GalerieDatei]:
        self.frisch()
        return (self.s.query(GalerieDatei).filter_by(vorgang_id=vorgang_id)
                .order_by(GalerieDatei.id).all())

    def leeren(self, vorgang_id: int) -> None:
        for d in self.dateien(vorgang_id):
            (config.DATA_ORDNER / d.pfad).unlink(missing_ok=True)
            self.s.delete(d)
        self.s.commit()

    def upload(self, client, vorgang_id, objekt_id, teile, json_antwort=True, **felder):
        """teile = [(name, bytes, content_type), …] → POST …/objekt/{oid}/fotos."""
        files = [("dateien", (name, io.BytesIO(inhalt), typ)) for name, inhalt, typ in teile]
        daten = {"zurueck": f"/lead-management/lead/{vorgang_id}"}
        daten.update(felder)
        headers = {"Accept": "application/json"} if json_antwort else {}
        return client.post(f"/lead-management/lead/{vorgang_id}/objekt/{objekt_id}/fotos",
                           data=daten, files=files, headers=headers)


class OrdnerJeObjekt(Basis):
    def test_ein_objekt_ordner_heisst_objekt(self):
        liste = galerie_modul.ordner_liste(self.s, "WP", vorgang=self.vorgang1)
        self.assertIn("Objekt", liste)
        self.assertNotIn("Objekt 1", liste)
        # hinter den Sparten-Ordnern, ersetzt nichts Bestehendes
        self.assertEqual(liste[:len(galerie_modul.SPARTEN_ORDNER["WP"])], galerie_modul.SPARTEN_ORDNER["WP"])
        self.assertEqual(galerie_modul.ordner_liste(self.s, "WP"), galerie_modul.ordner_liste(self.s, "WP", vorgang=None))
        self.assertNotIn("Objekt", galerie_modul.ordner_liste(self.s, "WP"))

    def test_mehrere_objekte_ordner_mit_bezeichnung(self):
        liste = galerie_modul.ordner_liste(self.s, "PV", vorgang=self.vorgang2.id)
        self.assertIn("Objekt 1", liste)        # Bezeichnung „Objekt 1“ wird nicht verdoppelt
        self.assertIn("Objekt Scheune", liste)
        self.assertNotIn("Objekt", liste)
        namen = [n for n, _o in galerie_modul.objekt_ordner(self.s, self.vorgang2.id)]
        self.assertEqual(namen, ["Objekt 1", "Objekt Scheune"])

    def test_ordnername_regeln(self):
        from types import SimpleNamespace
        self.assertEqual(galerie_modul.objekt_ordner_name(SimpleNamespace(bezeichnung="Objekt 2", reihenfolge=2, id=9), True), "Objekt 2")
        self.assertEqual(galerie_modul.objekt_ordner_name(SimpleNamespace(bezeichnung="Objektstraße 5", reihenfolge=2, id=9), True), "Objekt Objektstraße 5")
        self.assertEqual(galerie_modul.objekt_ordner_name(SimpleNamespace(bezeichnung='Halle: "A"/B', reihenfolge=3, id=9), True), "Objekt Halle- -A--B")
        self.assertEqual(galerie_modul.objekt_ordner_name(SimpleNamespace(bezeichnung="", reihenfolge=4, id=9), True), "Objekt 4")
        self.assertEqual(galerie_modul.objekt_ordner_name(SimpleNamespace(bezeichnung="Egal", reihenfolge=1, id=9), False), "Objekt")
        lang = galerie_modul.objekt_ordner_name(SimpleNamespace(bezeichnung="x" * 150, reihenfolge=2, id=9), True)
        self.assertLessEqual(len(lang), 100)

    def test_objekt_fuer_ordner_und_altnamen(self):
        self.assertEqual(galerie_modul.objekt_fuer_ordner(self.s, self.vorgang2.id, "Objekt Scheune").id, self.objekt2.id)
        self.assertEqual(galerie_modul.objekt_fuer_ordner(self.s, self.vorgang2.id, "Objekt 1").id, self.haupt2.id)
        # Alt-Name „Objekt“ (Ein-Objekt-Zeit) gehört dem Hauptobjekt; „Objekt 2“ (Standardname) der Scheune
        self.assertEqual(galerie_modul.objekt_fuer_ordner(self.s, self.vorgang2.id, "Objekt").id, self.haupt2.id)
        self.assertEqual(galerie_modul.objekt_fuer_ordner(self.s, self.vorgang2.id, "Objekt 2").id, self.objekt2.id)
        self.assertIsNone(galerie_modul.objekt_fuer_ordner(self.s, self.vorgang2.id, "Allgemein"))
        self.assertIsNone(galerie_modul.objekt_fuer_ordner(self.s, self.vorgang2.id, "Objekt Unbekannt"))
        self.assertEqual(galerie_modul.aktueller_objekt_ordner(self.s, self.vorgang2.id, "Objekt"), "Objekt 1")


class UploadKartei(Basis):
    """Phase 187 Test (q): Objektfoto landet im Objekt-Ordner und ist in der Erfassung sichtbar."""

    def test_q_objektfoto_im_objektordner_und_in_der_erfassung_sichtbar(self):
        ad = client_fuer(self.ad.id)
        self.leeren(self.vorgang2.id)
        r = self.upload(ad, self.vorgang2.id, self.objekt2.id,
                        [("scheune_1.jpg", jpg_bytes(), "image/jpeg"), ("scheune_2.png", png_bytes(), "image/png")])
        self.assertEqual(r.status_code, 200, r.text)
        antwort = r.json()
        self.assertTrue(antwort["ok"], antwort)
        self.assertEqual(antwort["anzahl"], 2)
        self.assertEqual(antwort["ordner"], "Objekt Scheune")
        self.assertEqual(antwort["objekt_id"], self.objekt2.id)
        self.assertEqual(len(antwort["fotos"]), 2)
        for f in antwort["fotos"]:
            self.assertTrue(f["url"].startswith("/vorgaenge/galerie/datei/"))
            self.assertTrue(f["loeschbar"])          # der Hochladende darf löschen
            self.assertIn("/fotos/", f["loeschen_url"])
        dateien = self.dateien(self.vorgang2.id)
        self.assertEqual({d.ordner for d in dateien}, {"Objekt Scheune"})
        self.assertEqual({d.sparte for d in dateien}, {"PV"})    # Sparte = Interesse des Objekts
        self.assertEqual({d.hochgeladen_von for d in dateien}, {self.ad.id})
        for d in dateien:
            pfad = config.DATA_ORDNER / d.pfad
            self.assertTrue(pfad.exists(), d.pfad)
            self.assertIn("Objekt Scheune", d.pfad)
            self.assertTrue(d.bild)
        self.assertEqual([d.id for d in galerie_modul.objektfotos(self.s, self.vorgang2.id, self.objekt2)],
                         sorted((d.id for d in dateien), reverse=True))
        self.assertEqual(galerie_modul.objektfotos(self.s, self.vorgang2.id, self.haupt2), [])
        # Erfassung: Sparten-Start mit übergebenem Objekt zeigt die Fotos (nur Anzeige)
        r = ad.get(f"/erfassung/sparten?kunde_id={self.kunde2.id}&objekt_id={self.objekt2.id}")
        self.assertEqual(r.status_code, 200)
        self.assertIn('data-rolle="objektfotos"', r.text)
        self.assertIn("Fotos zum Objekt", r.text)
        for d in dateien:
            self.assertIn(f"/vorgaenge/galerie/datei/{d.id}", r.text)
        self.assertIn('id="pj-lightbox"', r.text)       # Lightbox v28 auf der Seite
        self.assertNotIn("lk-objektfotos-form", r.text)  # kein Upload in der Erfassung
        # Erfassung: Übersicht (pruefen) der Erfassung dieses Objekts
        erfassung = Erfassung(kunde_id=self.kunde2.id, benutzer_id=self.ad.id, sparte="WP",
                              konfigurator_typ="WP", vorgang_id=self.vorgang2.id,
                              objekt_id=self.objekt2.id, status="Entwurf", antworten_json="{}")
        self.s.add(erfassung)
        self.s.commit()
        r = ad.get(f"/erfassung/{erfassung.id}/pruefen")
        self.assertEqual(r.status_code, 200)
        self.assertIn('data-rolle="objektfotos"', r.text)
        self.assertIn(f"/vorgaenge/galerie/datei/{dateien[0].id}", r.text)
        # Hauptobjekt ohne Fotos: kein Abschnitt (nur Anzeige, wenn Fotos vorliegen)
        r = ad.get(f"/erfassung/sparten?kunde_id={self.kunde2.id}&objekt_id={self.haupt2.id}")
        self.assertEqual(r.status_code, 200)
        self.assertNotIn('data-rolle="objektfotos"', r.text)
        # Kartei (Admin): Block an der Objektkarte mit Kachel, Lightbox-Daten und Upload-Formular
        r = self.admin.get(f"/lead-management/lead/{self.vorgang2.id}")
        self.assertEqual(r.status_code, 200)
        self.assertIn(f'id="objektfotos-{self.objekt2.id}"', r.text)
        self.assertIn(f'id="objektfotos-{self.haupt2.id}"', r.text)
        self.assertIn('data-lb-ordner="Objekt Scheune"', r.text)
        self.assertIn('onclick="return pjLightbox(event, this)"', r.text)
        self.assertIn('capture="environment"', r.text)
        self.assertIn("objektfotos_v35.js", r.text)
        self.assertIn("lm_v35_g.css", r.text)
        self.assertIn("Galerie-Ordner „Objekt Scheune“", r.text)
        self.assertNotIn('data-rolle="objektfotos-einzel"', r.text)
        # Vorgangsakte: Galerie zeigt den Objekt-Ordner mit den Fotos (Sparte PV)
        r = self.admin.get(f"/vorgaenge/{self.vorgang2.id}")
        self.assertEqual(r.status_code, 200)
        self.assertIn('<span class="t">Objekt Scheune</span>', r.text)
        self.assertIn('<option value="Objekt Scheune">', r.text)
        self.leeren(self.vorgang2.id)

    def test_ein_objekt_vorgang_block_und_ordner_objekt(self):
        self.leeren(self.vorgang1.id)
        r = self.upload(self.admin, self.vorgang1.id, self.haupt1.id, [("haus.jpg", jpg_bytes(), "image/jpeg")])
        self.assertEqual(r.status_code, 200, r.text)
        self.assertEqual(r.json()["ordner"], "Objekt")
        dateien = self.dateien(self.vorgang1.id)
        self.assertEqual([d.ordner for d in dateien], ["Objekt"])
        self.assertEqual(dateien[0].sparte, "WP")
        r = self.admin.get(f"/lead-management/lead/{self.vorgang1.id}")
        self.assertEqual(r.status_code, 200)
        self.assertIn('data-rolle="objektfotos-einzel"', r.text)
        self.assertIn("Fotos zum Objekt", r.text)
        self.assertIn(f"/vorgaenge/galerie/datei/{dateien[0].id}", r.text)
        self.assertIn("Galerie-Ordner „Objekt“", r.text)
        # Vorgangsakte: Ordner „Objekt“ in der Galerie
        r = self.admin.get(f"/vorgaenge/{self.vorgang1.id}")
        self.assertIn('<span class="t">Objekt</span>', r.text)
        self.leeren(self.vorgang1.id)

    def test_heic_wird_jpg(self):
        self.leeren(self.vorgang1.id)
        r = self.upload(self.admin, self.vorgang1.id, self.haupt1.id,
                        [("iphone.heic", heic_bytes(), "image/heic"),
                         ("getarnt.jpg", heic_bytes((40, 30)), "image/jpeg")])   # HEIC mit falscher Endung
        self.assertEqual(r.status_code, 200, r.text)
        self.assertTrue(r.json()["ok"], r.json())
        dateien = self.dateien(self.vorgang1.id)
        self.assertEqual(len(dateien), 2)
        from PIL import Image
        for d in dateien:
            self.assertTrue(d.dateiname.lower().endswith(".jpg"), d.dateiname)
            pfad = config.DATA_ORDNER / d.pfad
            with Image.open(pfad) as bild:
                self.assertEqual(bild.format, "JPEG")
            self.assertFalse(galerie_modul.ist_heic(pfad))
        ordner = (config.DATA_ORDNER / dateien[0].pfad).parent
        self.assertEqual([p.name for p in ordner.glob("*.heic")], [])   # Original entfernt
        self.leeren(self.vorgang1.id)

    def test_heic_auch_im_galerie_upload(self):
        """HEIC → JPG gilt für jeden Galerie-Upload (galerie.speichern)."""
        self.leeren(self.vorgang1.id)
        r = self.admin.post(f"/vorgaenge/{self.vorgang1.id}/galerie/upload",
                            data={"ordner": "Allgemein", "sparte": "WP", "zurueck": f"/vorgaenge/{self.vorgang1.id}"},
                            files=[("dateien", ("bild.heic", io.BytesIO(heic_bytes()), "image/heic"))],
                            headers={"Accept": "application/json"})
        self.assertEqual(r.status_code, 200, r.text)
        d = self.dateien(self.vorgang1.id)[0]
        self.assertTrue(d.dateiname.endswith(".jpg"))
        self.assertEqual(d.ordner, "Allgemein")
        self.leeren(self.vorgang1.id)

    def test_grenze_10_mb_und_falsche_dateien(self):
        self.leeren(self.vorgang1.id)
        zu_gross = b"\xff\xd8" + b"0" * (galerie_modul.OBJEKTFOTO_MAX_BYTES - 1)
        r = self.upload(self.admin, self.vorgang1.id, self.haupt1.id,
                        [("riesig.jpg", zu_gross, "image/jpeg"),
                         ("notiz.txt", b"kein Bild", "text/plain"),
                         ("kaputt.jpg", b"das ist kein JPEG", "image/jpeg"),
                         ("leer.jpg", b"", "image/jpeg"),
                         ("ok.jpg", jpg_bytes(), "image/jpeg")])
        self.assertEqual(r.status_code, 200, r.text)
        antwort = r.json()
        self.assertFalse(antwort["ok"])
        self.assertEqual(antwort["anzahl"], 1)
        gruende = {f["name"]: f["grund"] for f in antwort["fehler"]}
        self.assertIn("größer als 10 MB", gruende["riesig.jpg"])
        self.assertIn("nur JPG, PNG oder HEIC", gruende["notiz.txt"])
        self.assertIn("kein lesbares Bild", gruende["kaputt.jpg"])
        self.assertIn("leer", gruende["leer.jpg"])
        self.assertIn("1 von 5 Dateien abgelegt", antwort["meldung"])
        dateien = self.dateien(self.vorgang1.id)
        self.assertEqual([d.dateiname for d in dateien], ["ok.jpg"])
        ordner = (config.DATA_ORDNER / dateien[0].pfad).parent
        self.assertEqual(sorted(p.name for p in ordner.iterdir()), ["ok.jpg"])   # keine Reste auf der Platte
        self.leeren(self.vorgang1.id)

    def test_grosse_bilder_werden_verkleinert(self):
        self.leeren(self.vorgang1.id)
        r = self.upload(self.admin, self.vorgang1.id, self.haupt1.id,
                        [("gross.jpg", jpg_bytes((2600, 1800)), "image/jpeg")])
        self.assertEqual(r.status_code, 200, r.text)
        from PIL import Image
        with Image.open(config.DATA_ORDNER / self.dateien(self.vorgang1.id)[0].pfad) as bild:
            self.assertLessEqual(max(bild.size), galerie_modul.MAX_KANTE)
        self.leeren(self.vorgang1.id)

    def test_ohne_javascript_redirect(self):
        self.leeren(self.vorgang1.id)
        r = self.upload(self.admin, self.vorgang1.id, self.haupt1.id,
                        [("haus.jpg", jpg_bytes(), "image/jpeg")], json_antwort=False)
        self.assertEqual(r.status_code, 303)
        ziel = r.headers["location"]
        self.assertTrue(ziel.startswith(f"/lead-management/lead/{self.vorgang1.id}?meldung="), ziel)
        self.assertTrue(ziel.endswith(f"#objekt-{self.haupt1.id}"), ziel)
        # zurueck nur relativ; fremde Adressen fallen auf die Kartei zurück
        r = self.upload(self.admin, self.vorgang1.id, self.haupt1.id,
                        [("haus2.jpg", jpg_bytes(), "image/jpeg")], json_antwort=False,
                        zurueck="https://boese.example/x")
        self.assertTrue(r.headers["location"].startswith(f"/lead-management/lead/{self.vorgang1.id}?"))
        r = self.upload(self.admin, self.vorgang1.id, self.haupt1.id, [], json_antwort=True)
        self.assertEqual(r.status_code, 200)
        self.assertFalse(r.json()["ok"])
        self.assertIn("Keine Datei", r.json()["meldung"])
        self.leeren(self.vorgang1.id)


class Rechte(Basis):
    def test_ad_eigener_lead_ja_fremder_403(self):
        self.leeren(self.vorgang1.id)
        fremd = client_fuer(self.ad_fremd.id)
        r = self.upload(fremd, self.vorgang1.id, self.haupt1.id, [("x.jpg", jpg_bytes(), "image/jpeg")])
        self.assertEqual(r.status_code, 403, r.text)
        self.assertFalse(r.json()["ok"])
        self.assertEqual(self.dateien(self.vorgang1.id), [])
        r = self.upload(fremd, self.vorgang1.id, self.haupt1.id, [("x.jpg", jpg_bytes(), "image/jpeg")], json_antwort=False)
        self.assertEqual(r.status_code, 303)
        eigen = client_fuer(self.ad.id)
        r = self.upload(eigen, self.vorgang1.id, self.haupt1.id, [("x.jpg", jpg_bytes(), "image/jpeg")])
        self.assertEqual(r.status_code, 200, r.text)
        self.assertTrue(r.json()["ok"])
        for b in (self.innendienst, self.leadmanager):
            r = self.upload(client_fuer(b.id), self.vorgang1.id, self.haupt1.id, [("y.jpg", jpg_bytes(), "image/jpeg")])
            self.assertEqual(r.status_code, 200, (b.rolle, r.text))
        self.assertEqual(len(self.dateien(self.vorgang1.id)), 3)
        self.leeren(self.vorgang1.id)

    def test_objekt_muss_zum_vorgang_gehoeren(self):
        r = self.upload(self.admin, self.vorgang1.id, self.objekt2.id, [("x.jpg", jpg_bytes(), "image/jpeg")])
        self.assertEqual(r.status_code, 404)
        r = self.upload(self.admin, self.vorgang1.id, 99999999, [("x.jpg", jpg_bytes(), "image/jpeg")])
        self.assertEqual(r.status_code, 404)
        r = self.upload(self.admin, 99999999, self.haupt1.id, [("x.jpg", jpg_bytes(), "image/jpeg")])
        self.assertEqual(r.status_code, 404)

    def test_vertrag_r_bearbeiten_erlaubt(self):
        """Sobald Agent R lead_v2.bearbeiten_erlaubt liefert, entscheidet es über Benutzer ohne
        Galerie-Recht (hier: fremder AD) – bis dahin die Übergangsprüfung zugriff_erlaubt."""
        with mock.patch.object(lead_v2, "bearbeiten_erlaubt", create=True,
                               side_effect=lambda s, b, v: b.id == self.ad_fremd.id):
            self.assertTrue(galerie_modul.objektfotos_erlaubt(self.s, self.vorgang1, self.ad_fremd))
        with mock.patch.object(lead_v2, "bearbeiten_erlaubt", create=True, side_effect=lambda s, b, v: False):
            self.assertFalse(galerie_modul.objektfotos_erlaubt(self.s, self.vorgang1, self.ad_fremd))
            self.assertTrue(galerie_modul.objektfotos_erlaubt(self.s, self.vorgang1, self.ad))   # Galerie-Recht
        # Übergangsprüfung ohne R: Modul-Sichtbare ja, fremder AD nein
        self.assertTrue(galerie_modul.objektfotos_erlaubt(self.s, self.vorgang1, self.leadmanager))
        if not hasattr(lead_v2, "bearbeiten_erlaubt"):
            self.assertFalse(galerie_modul.objektfotos_erlaubt(self.s, self.vorgang1, self.ad_fremd))

    def test_loeschen_hochladender_innendienst_admin(self):
        self.leeren(self.vorgang1.id)
        eigen = client_fuer(self.ad.id)
        r = self.upload(eigen, self.vorgang1.id, self.haupt1.id, [("ad.jpg", jpg_bytes(), "image/jpeg")])
        self.assertEqual(r.status_code, 200, r.text)
        ad_datei = r.json()["fotos"][0]
        r = self.upload(client_fuer(self.innendienst.id), self.vorgang1.id, self.haupt1.id,
                        [("id.jpg", jpg_bytes(), "image/jpeg")])
        id_datei = next(f for f in r.json()["fotos"] if f["name"] == "id.jpg")
        self.assertTrue(id_datei["loeschbar"])   # Antwort an den Innendienst: darf immer löschen
        ad_sicht = next(f for f in r.json()["fotos"] if f["name"] == "ad.jpg")
        self.assertTrue(ad_sicht["loeschbar"])   # … auch fremde Fotos
        self.assertFalse(galerie_modul.objektfoto_loeschen_erlaubt(self.s.get(GalerieDatei, id_datei["id"]), self.ad))
        # fremder AD: kein Zugriff auf den Vorgang → 403
        r = client_fuer(self.ad_fremd.id).post(ad_datei["loeschen_url"], headers={"Accept": "application/json"})
        self.assertEqual(r.status_code, 403)
        # eigener AD darf das Foto des Innendiensts nicht löschen (nicht Hochladender) → 403
        r = eigen.post(id_datei["loeschen_url"], headers={"Accept": "application/json"})
        self.assertEqual(r.status_code, 403, r.text)
        self.assertIn("Hochladenden", r.json()["meldung"])
        # eigener AD löscht sein Foto
        pfad = config.DATA_ORDNER / self.s.get(GalerieDatei, ad_datei["id"]).pfad
        r = eigen.post(ad_datei["loeschen_url"], headers={"Accept": "application/json"})
        self.assertEqual(r.status_code, 200, r.text)
        self.assertTrue(r.json()["ok"])
        self.assertEqual([f["name"] for f in r.json()["fotos"]], ["id.jpg"])
        self.assertFalse(pfad.exists())
        self.frisch()
        self.assertIsNone(self.s.get(GalerieDatei, ad_datei["id"]))
        notiz = (self.s.query(VorgangsNotiz).filter_by(vorgang_id=self.vorgang1.id)
                 .order_by(VorgangsNotiz.id.desc()).first())
        self.assertIn("ad.jpg", notiz.text)
        self.assertIn("gelöscht", notiz.text)
        # Admin löscht das Foto des Innendiensts (ohne JSON → Redirect)
        r = self.admin.post(id_datei["loeschen_url"], data={"zurueck": f"/lead-management/lead/{self.vorgang1.id}"})
        self.assertEqual(r.status_code, 303)
        self.assertEqual(self.dateien(self.vorgang1.id), [])
        # unbekanntes Foto → 404
        r = self.admin.post(id_datei["loeschen_url"], headers={"Accept": "application/json"})
        self.assertEqual(r.status_code, 404)


class GalerieZuordnung(Basis):
    """Zuordnung „Objekt“ beim Upload in der Galerie und beim Einsortieren aus der Sammelbox."""

    def test_galerie_upload_in_objektordner_und_einsortieren(self):
        self.leeren(self.vorgang2.id)
        r = self.admin.post(f"/vorgaenge/{self.vorgang2.id}/galerie/upload",
                            data={"ordner": "Allgemein", "sparte": "WP", "zurueck": f"/vorgaenge/{self.vorgang2.id}",
                                  "datei_ordner": ["Objekt Scheune", "Allgemein"]},
                            files=[("dateien", ("a.jpg", io.BytesIO(jpg_bytes()), "image/jpeg")),
                                   ("dateien", ("b.jpg", io.BytesIO(jpg_bytes()), "image/jpeg"))],
                            headers={"Accept": "application/json"})
        self.assertEqual(r.status_code, 200, r.text)
        self.assertTrue(r.json()["ok"], r.json())
        dateien = {d.dateiname: d for d in self.dateien(self.vorgang2.id)}
        self.assertEqual(dateien["a.jpg"].ordner, "Objekt Scheune")
        self.assertEqual(dateien["b.jpg"].ordner, "Allgemein")
        self.assertEqual([d.id for d in galerie_modul.objektfotos(self.s, self.vorgang2.id, self.objekt2)], [dateien["a.jpg"].id])
        # Einsortieren (verschieben) aus „Allgemein“ in den Objekt-Ordner des Hauptobjekts
        r = self.admin.post(f"/vorgaenge/galerie/datei/{dateien['b.jpg'].id}/verschieben", data={"ordner": "Objekt 1"})
        self.assertEqual(r.status_code, 303)
        self.frisch()
        b = self.s.get(GalerieDatei, dateien["b.jpg"].id)
        self.assertEqual(b.ordner, "Objekt 1")
        self.assertIn("Objekt 1", b.pfad)
        self.assertEqual([d.id for d in galerie_modul.objektfotos(self.s, self.vorgang2.id, self.haupt2)], [b.id])
        # unbekannter Objekt-Ordner fällt auf „Allgemein“ zurück
        r = self.admin.post(f"/vorgaenge/{self.vorgang2.id}/galerie/upload",
                            data={"ordner": "Objekt Gibtsnicht", "sparte": "WP", "zurueck": f"/vorgaenge/{self.vorgang2.id}"},
                            files=[("dateien", ("c.jpg", io.BytesIO(jpg_bytes()), "image/jpeg"))],
                            headers={"Accept": "application/json"})
        self.assertEqual(r.json()["abgelegt"][0]["ordner"], "Allgemein")
        # Übersicht: Ordner-Schlüssel enthalten die Objekt-Ordner
        uebersicht = galerie_modul.uebersicht(self.s, self.vorgang2.id, "WP")
        self.assertEqual(len(uebersicht["Objekt Scheune"]["eintraege"]), 1)
        self.assertEqual(len(uebersicht["Objekt 1"]["eintraege"]), 1)
        self.leeren(self.vorgang2.id)

    def test_umbenennung_zieht_ordner_nach(self):
        self.leeren(self.vorgang2.id)
        r = self.upload(self.admin, self.vorgang2.id, self.objekt2.id, [("s.jpg", jpg_bytes(), "image/jpeg")])
        self.assertEqual(r.status_code, 200, r.text)
        objekt = self.s.get(VorgangObjekt, self.objekt2.id)
        ergebnis = lead_kartei.objekt_feld_speichern(self.s, self.vorgang2, self.kunde2, objekt,
                                                     "bezeichnung", "Halle", benutzer=self.admin_benutzer)
        self.assertTrue(ergebnis["ok"], ergebnis)
        self.s.commit()
        self.frisch()
        self.assertEqual([d.ordner for d in self.dateien(self.vorgang2.id)], ["Objekt Halle"])
        self.assertIn("Objekt Halle", galerie_modul.ordner_liste(self.s, "PV", vorgang=self.vorgang2.id))
        self.assertEqual(len(galerie_modul.objektfotos(self.s, self.vorgang2.id, objekt)), 1)
        # Datei liegt physisch weiter im alten Ordner – die Datei-Route liest pfad
        d = self.dateien(self.vorgang2.id)[0]
        self.assertIn("Objekt Scheune", d.pfad)
        self.assertEqual(self.admin.get(f"/vorgaenge/galerie/datei/{d.id}").status_code, 200)
        # zurück auf „Scheune“ (Basis für die anderen Tests)
        lead_kartei.objekt_feld_speichern(self.s, self.vorgang2, self.kunde2, objekt, "bezeichnung", "Scheune",
                                          benutzer=self.admin_benutzer)
        self.s.commit()
        self.frisch()
        self.assertEqual([d.ordner for d in self.dateien(self.vorgang2.id)], ["Objekt Scheune"])
        self.leeren(self.vorgang2.id)

    def test_altname_objekt_nach_zweitem_objekt(self):
        """Foto aus der Ein-Objekt-Zeit (Ordner „Objekt“) bleibt dem Hauptobjekt zugeordnet,
        wenn ein zweites Objekt hinzukommt; der nächste Objekt-Upload zieht den Namen nach."""
        kunde, vorgang = self.vorgang_neu("Spaeter-zwei")
        haupt = objekte_modul.hauptobjekt(self.s, vorgang.id, anlegen=True, kunde=kunde)
        self.s.commit()
        r = self.upload(self.admin, vorgang.id, haupt.id, [("alt.jpg", jpg_bytes(), "image/jpeg")])
        self.assertEqual(r.json()["ordner"], "Objekt")
        zweites = objekte_modul.objekt_anlegen(self.s, vorgang, "Weg 9", "47269", "Duisburg")
        self.s.commit()
        self.assertEqual([d.id for d in galerie_modul.objektfotos(self.s, vorgang.id, haupt)],
                         [self.dateien(vorgang.id)[0].id])
        self.assertEqual(galerie_modul.objektfotos(self.s, vorgang.id, zweites), [])
        # Galerie-Übersicht zeigt das Alt-Foto unter dem heutigen Ordner „Objekt 1“
        uebersicht = galerie_modul.uebersicht(self.s, vorgang.id, "WP")
        self.assertEqual(len(uebersicht["Objekt 1"]["eintraege"]), 1)
        self.assertNotIn("Objekt", uebersicht)
        r = self.admin.get(f"/vorgaenge/{vorgang.id}")
        self.assertIn('<span class="t">Objekt 1</span>', r.text)
        # Kartei: beide Karten, das Alt-Foto in der Karte des Hauptobjekts
        r = self.admin.get(f"/lead-management/lead/{vorgang.id}")
        self.assertEqual(r.status_code, 200)
        self.assertIn(f'id="objektfotos-{haupt.id}"', r.text)
        self.assertIn(f'id="objektfotos-{zweites.id}"', r.text)
        # nächster Upload ans Hauptobjekt: Alt-Name wird nachgezogen
        r = self.upload(self.admin, vorgang.id, haupt.id, [("neu.jpg", jpg_bytes(), "image/jpeg")])
        self.assertEqual(r.json()["ordner"], "Objekt 1")
        self.assertEqual({d.ordner for d in self.dateien(vorgang.id)}, {"Objekt 1"})
        self.assertEqual(len(galerie_modul.objektfotos(self.s, vorgang.id, haupt)), 2)


class Projektakte(Basis):
    def test_projektakte_zeigt_objektfotos_des_gewerk_objekts(self):
        self.leeren(self.vorgang2.id)
        r = self.upload(self.admin, self.vorgang2.id, self.objekt2.id, [("pv.jpg", jpg_bytes(), "image/jpeg")])
        self.assertEqual(r.status_code, 200, r.text)
        foto_id = r.json()["fotos"][0]["id"]
        angebot = angebot_aufbau.angebot_anlegen(self.s, self.kunde2.id, sparte="PV")
        angebot.positionen.append(AngebotsPosition(sort=1, pos_nr="PV001", bezeichnung="Pos",
                                                   beschreibung="Pos", menge=1, e_preis_cent=10000))
        angebot.vorgang_id = self.vorgang2.id
        angebot.objekt_id = self.objekt2.id
        angebot_status_setzen(angebot, "Angenommen")
        self.s.commit()
        projekt = kern.projekt_anlegen(self.s, angebot, projektleiter_id=1)
        gewerk = kern.gewerk_anlegen(self.s, projekt, angebot, "PV")
        gewerk.objekt_id = self.objekt2.id
        self.s.commit()
        daten = galerie_modul.objektfotos_je_gewerk(self.s, projekt, [gewerk])
        self.assertEqual(len(daten), 1)
        self.assertEqual(daten[0]["objekt_id"], self.objekt2.id)
        self.assertEqual([f["id"] for f in daten[0]["fotos"]], [foto_id])
        self.assertEqual(daten[0]["sparten"], ["PV"])
        r = self.admin.get(f"/projektierung/projekt/{projekt.id}")
        self.assertEqual(r.status_code, 200)
        self.assertIn('data-rolle="objektfotos"', r.text)
        self.assertIn("Objektfotos · Scheune", r.text)
        self.assertIn(f"/vorgaenge/galerie/datei/{foto_id}", r.text)
        self.assertIn('<option value="Objekt Scheune">', r.text)   # Einsortieren in der Projekt-Galerie
        self.leeren(self.vorgang2.id)
        r = self.admin.get(f"/projektierung/projekt/{projekt.id}")
        self.assertNotIn('data-rolle="objektfotos"', r.text)       # ohne Fotos kein Abschnitt


class Bausteine(Basis):
    def test_skripte_styles_und_waechter(self):
        js = (PROJEKT / "app/static/objektfotos_v35.js").read_text(encoding="utf-8")
        for erwartet in ("bilderVerkleinern", "XMLHttpRequest", "pjLightbox", "setRequestHeader('Accept', 'application/json')",
                         "confirm('Foto löschen?')", "data-max-mb"):
            self.assertIn(erwartet, js, erwartet)
        self.assertNotRegex(js, r"\.innerHTML\s*[+]?=")   # DOM-Aufbau ohne innerHTML
        css = (PROJEKT / "app/static/lm_v35_g.css").read_text(encoding="utf-8")
        self.assertNotRegex(css, r"#[0-9a-fA-F]{3,6}\b")   # nur Tokens
        self.assertIn("--status-rot", css)
        vorlage = (PROJEKT / "app/templates/leadmanagement/kartei_objekte.html").read_text(encoding="utf-8")
        self.assertIn("macro objekt_fotos(", vorlage)
        self.assertIn('accept="image/*" capture="environment"', vorlage)
        self.assertIn("multiple", vorlage)
        router = (PROJEKT / "app/routers/lm_objektfotos.py").read_text(encoding="utf-8")
        # v33-Wächter: Verbindung freigeben, bevor das Formular (der Upload) gelesen wird
        rumpf = router[router.index("def objektfotos_hochladen"):]
        self.assertLess(rumpf.index("verbindung_freigeben(session)"), rumpf.index("anfrage.formular(request)"))
        quelle = (PROJEKT / "app/galerie.py").read_text(encoding="utf-8")
        self.assertIn("OBJEKTFOTO_MAX_BYTES = 10 * 1024 * 1024", quelle)

    def test_foto_daten_und_kontext(self):
        self.leeren(self.vorgang1.id)
        r = self.upload(self.admin, self.vorgang1.id, self.haupt1.id, [("k.jpg", jpg_bytes(), "image/jpeg")])
        self.assertEqual(r.status_code, 200)
        kontext = galerie_modul.objektfotos_kontext(self.s, self.vorgang1, self.ad)
        self.assertTrue(kontext["darf_hochladen"])
        self.assertEqual(kontext["max_mb"], 10)
        self.assertIsNotNone(kontext["einzel"])
        eintrag = kontext["je_objekt"][self.haupt1.id]
        self.assertEqual(eintrag["ordner"], "Objekt")
        self.assertEqual(eintrag["anzahl"], 1)
        foto = eintrag["fotos"][0]
        self.assertFalse(foto["loeschbar"])    # AD ist nicht der Hochladende (Admin war es)
        self.assertEqual(foto["loeschen_url"], f"/lead-management/lead/{self.vorgang1.id}/objekt/{self.haupt1.id}/fotos/{foto['id']}/loeschen")
        self.assertEqual(json.loads(json.dumps(foto))["id"], foto["id"])   # JSON-fähig
        kontext_fremd = galerie_modul.objektfotos_kontext(self.s, self.vorgang1, self.ad_fremd)
        self.assertFalse(kontext_fremd["darf_hochladen"])
        kontext2 = galerie_modul.objektfotos_kontext(self.s, self.vorgang2, self.innendienst)
        self.assertIsNone(kontext2["einzel"])
        self.assertEqual(set(kontext2["je_objekt"]), {self.haupt2.id, self.objekt2.id})
        self.leeren(self.vorgang1.id)


if __name__ == "__main__":
    unittest.main()
