# v34 (PLAN_V21 Phase 181, Agent M): Galerie – mehrere Fotos, verschiedene Ordner, EIN Upload
# (Route POST /vorgaenge/<id>/galerie/upload mit dateien / datei_ordner / datei_bemerkung
# positionsgleich, JSON bei Accept: application/json, Teilerfolg je Datei), Kamera-Serie und
# Sammelbox-Markup (Vorgangsakte, Montage-Backend, mobile Erfassung im Formular-Modus),
# Rechte je Rolle unverändert (Außendienst eigener Vorgang, Montage nur Besetzung, Fremde 403),
# Diktat-Knopf (Makro _diktat.html, static/diktat.js, Symbol mikrofon), docs/https-intern.md.
import asyncio
import base64
import io
import json
import shutil
import tempfile
import threading
import time
import unittest
import warnings
from datetime import datetime, timedelta
from pathlib import Path

warnings.filterwarnings("ignore")

from fastapi.testclient import TestClient

from app import angebot_aufbau, auth, config
from app import galerie as galerie_modul
from app import projektierung as kern
from app import vorgaenge as vorgaenge_modul
from app.db import SessionLocal, init_db
from app.main import app
from app.models import (Angebot, AngebotsPosition, Aufgabe, AufgabenpaketInstanz, Benutzer,
                        Erfassung, GalerieDatei, Gewerk, Kunde, Projekt, ProjektTermin,
                        ProjektVerlauf, SteckbriefWert, TerminBesetzung, Vorgang,
                        VorgangNotizGelesen, VorgangsNotiz, angebot_status_setzen)

PROJEKT = Path(__file__).resolve().parents[1]
PRAEFIX = "V34M-Gal"
TEST_EMAIL = "v34m-galerie@test.local"


def jpg_bytes(groesse=(120, 80), farbe=(200, 40, 40)) -> bytes:
    from PIL import Image
    puffer = io.BytesIO()
    Image.new("RGB", groesse, farbe).save(puffer, format="JPEG")
    return puffer.getvalue()


def client_fuer(benutzer_id: int) -> TestClient:
    c = TestClient(app)
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
            ordner = config.DATA_ORDNER / "vorgaenge" / str(v.id)
            if ordner.exists():
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
        s.query(TerminBesetzung).filter_by(benutzer_id=b.id).delete()
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
        cls.ad = cls.benutzer_neu("AD", "aussendienst")
        cls.ad_fremd = cls.benutzer_neu("AD fremd", "aussendienst")
        cls.monteur = cls.benutzer_neu("Monteur", "montage")
        cls.monteur_fremd = cls.benutzer_neu("Monteur fremd", "montage")
        cls.projektierer = cls.benutzer_neu("Projektierer", "projektierung")
        cls.leadmanager = cls.benutzer_neu("Leadmanager", "leadmanagement")
        # Vorgang mit Projekt (PV) – AD ist zuständig, Monteur ist in der Besetzung eines Termins
        cls.gewerk = cls.gewerk_neu(sparte="PV")
        cls.vorgang = cls.vorgang_von(cls.gewerk)
        cls.vorgang.ad_id = cls.ad.id
        cls.s.commit()
        cls.termin = cls.termin_neu(cls.gewerk, besetzung=(cls.monteur,))
        # zweiter Vorgang ohne Projekt (nur Kunde) – gehört niemandem
        kunde2 = Kunde(anrede="Frau", vorname="Fremd", nachname=f"{PRAEFIX} Kundin",
                       strasse="Weg 2", plz="47051", ort="Duisburg", email=TEST_EMAIL)
        cls.s.add(kunde2)
        cls.s.flush()
        cls.vorgang_fremd = vorgaenge_modul.vorgang_fuer_kunde(cls.s, kunde2.id)
        cls.s.commit()

    @classmethod
    def tearDownClass(cls):
        aufraeumen(cls.s)
        cls.s.close()

    @classmethod
    def benutzer_neu(cls, name: str, rolle: str) -> Benutzer:
        b = Benutzer(name=f"{PRAEFIX} {name}", rolle=rolle, aktiv=True,
                     pin_hash=auth.pin_hash("1234"),
                     email=f"{name.lower().replace(' ', '')}@v34m.test")
        cls.s.add(b)
        cls.s.commit()
        return b

    @classmethod
    def gewerk_neu(cls, sparte="PV", phase="montagevorbereitung") -> Gewerk:
        kunde = Kunde(anrede="Herr", vorname="Paul", nachname=f"{PRAEFIX} Kunde",
                      strasse="Teststr. 5", plz="47139", ort="Duisburg",
                      email=TEST_EMAIL, telefon="0203 1")
        cls.s.add(kunde)
        cls.s.flush()
        angebot = angebot_aufbau.angebot_anlegen(cls.s, kunde.id, sparte=sparte)
        angebot.positionen.append(AngebotsPosition(
            sort=1, pos_nr="PV001", bezeichnung="Pos", beschreibung="Pos", menge=1,
            e_preis_cent=10000))
        angebot_status_setzen(angebot, "Angenommen")
        cls.s.commit()
        if not angebot.vorgang_id:
            vorgang = vorgaenge_modul.vorgang_fuer_angebot(cls.s, angebot)
            angebot.vorgang_id = vorgang.id
            cls.s.commit()
        projekt = kern.projekt_anlegen(cls.s, angebot, projektleiter_id=1)
        gewerk = kern.gewerk_anlegen(cls.s, projekt, angebot, sparte)
        gewerk.phase = phase
        cls.s.commit()
        return gewerk

    @classmethod
    def termin_neu(cls, gewerk: Gewerk, besetzung=()) -> ProjektTermin:
        beginn = (datetime.now() + timedelta(days=1)).replace(hour=7, minute=30, second=0,
                                                              microsecond=0)
        t = ProjektTermin(gewerk_id=gewerk.id, projekt_id=gewerk.projekt_id, typ="montage",
                          beginn=beginn, ende=beginn + timedelta(days=1), zweck="wp",
                          kunde_bestaetigt=True)
        cls.s.add(t)
        cls.s.flush()
        for b in besetzung:
            cls.s.add(TerminBesetzung(termin_id=t.id, benutzer_id=b.id))
        cls.s.commit()
        return t

    @classmethod
    def vorgang_von(cls, gewerk: Gewerk) -> Vorgang:
        angebot = cls.s.get(Angebot, gewerk.angebot_id)
        return cls.s.get(Vorgang, angebot.vorgang_id)

    # --- Helfer ----------------------------------------------------------------------
    def dateien(self, vorgang_id: int) -> list[GalerieDatei]:
        self.s.expire_all()
        return (self.s.query(GalerieDatei).filter_by(vorgang_id=vorgang_id)
                .order_by(GalerieDatei.id).all())

    def loeschen(self, vorgang_id: int) -> None:
        for d in self.dateien(vorgang_id):
            (config.DATA_ORDNER / d.pfad).unlink(missing_ok=True)
            self.s.delete(d)
        self.s.commit()

    def upload(self, client, vorgang_id, teile, je_ordner, je_bemerkung=None, json_antwort=True,
               sparte="PV", **felder):
        """teile = [(name, bytes), …]; je_ordner / je_bemerkung positionsgleich
        (datei_ordner / datei_bemerkung); weitere Formularfelder über felder (ordner, bemerkung …)."""
        files = [("dateien", (name, io.BytesIO(inhalt), "image/jpeg" if name.endswith(".jpg")
                              else "application/pdf")) for name, inhalt in teile]
        daten = {"sparte": sparte, "zurueck": f"/vorgaenge/{vorgang_id}"}
        if je_ordner:
            daten["datei_ordner"] = list(je_ordner)
        if je_bemerkung:
            daten["datei_bemerkung"] = list(je_bemerkung)
        daten.update(felder)
        headers = {"Accept": "application/json"} if json_antwort else {}
        return client.post(f"/vorgaenge/{vorgang_id}/galerie/upload", data=daten, files=files,
                           headers=headers, follow_redirects=False)


class MehrfachUpload(Basis):
    def test_drei_dateien_zwei_ordner_ein_request(self):
        """Kontrollwert: drei Fotos, Ordner Zählerschrank, Zählerschrank, Dachfläche → ein Upload,
        drei Dateien in zwei Ordnern, Bemerkung je Datei."""
        self.loeschen(self.vorgang.id)
        r = self.upload(self.admin, self.vorgang.id,
                        [("a.jpg", jpg_bytes()), ("b.jpg", jpg_bytes()), ("c.jpg", jpg_bytes())],
                        ["Zählerschrank", "Zählerschrank", "Dachfläche"],
                        ["erste", "", "dritte"], bemerkung="Standardtext")
        self.assertEqual(r.status_code, 200, r.text)
        antwort = r.json()
        self.assertTrue(antwort["ok"], antwort)
        self.assertEqual(antwort["anzahl"], 3)
        self.assertEqual([a["nr"] for a in antwort["abgelegt"]], [0, 1, 2])
        self.assertEqual(antwort["fehler"], [])
        self.assertEqual(antwort["meldung"], "3 Datei(en) abgelegt (Dachfläche, Zählerschrank).")
        self.assertTrue(antwort["ziel"].startswith(f"/vorgaenge/{self.vorgang.id}?meldung="))
        self.assertTrue(antwort["ziel"].endswith("#galerie"))
        dateien = self.dateien(self.vorgang.id)
        self.assertEqual([(d.ordner, d.bemerkung, d.sparte, d.quelle) for d in dateien],
                         [("Zählerschrank", "erste", "PV", "upload"),
                          ("Zählerschrank", "Standardtext", "PV", "upload"),
                          ("Dachfläche", "dritte", "PV", "upload")])
        for d in dateien:
            self.assertTrue((config.DATA_ORDNER / d.pfad).exists(), d.pfad)
            self.assertEqual(d.hochgeladen_von, 1)
        # zweiter Aufruf ohne Accept: Redirect mit Meldung wie bisher
        r = self.upload(self.admin, self.vorgang.id, [("d.jpg", jpg_bytes())], ["Dachfläche"],
                        json_antwort=False)
        self.assertEqual(r.status_code, 303)
        self.assertIn("1+Datei%28en%29+abgelegt+%28Dachfl", r.headers["location"])
        self.assertTrue(r.headers["location"].endswith("#galerie"))
        self.assertEqual(len(self.dateien(self.vorgang.id)), 4)

    def test_teilerfolg_leere_datei(self):
        """Eine ungültige (leere) Datei: die beiden anderen werden abgelegt, Fehler je Datei."""
        self.loeschen(self.vorgang.id)
        r = self.upload(self.admin, self.vorgang.id,
                        [("gut1.jpg", jpg_bytes()), ("leer.jpg", b""), ("gut2.jpg", jpg_bytes())],
                        ["Zählerschrank", "Zählerschrank", "Dachfläche"])
        self.assertEqual(r.status_code, 200, r.text)
        antwort = r.json()
        self.assertFalse(antwort["ok"])
        self.assertEqual(antwort["anzahl"], 2)
        self.assertEqual([a["nr"] for a in antwort["abgelegt"]], [0, 2])
        self.assertEqual(antwort["fehler"], [{"nr": 1, "name": "leer.jpg", "grund": "Datei ist leer"}])
        self.assertEqual(antwort["meldung"],
                         "2 von 3 Dateien abgelegt (Dachfläche, Zählerschrank) – nicht abgelegt: "
                         "leer.jpg (Datei ist leer).")
        self.assertEqual([d.dateiname for d in self.dateien(self.vorgang.id)], ["gut1.jpg", "gut2.jpg"])
        # nur leere Dateien → keine abgelegt, Meldung sagt es
        r = self.upload(self.admin, self.vorgang.id, [("nix.jpg", b"")], ["Dachfläche"])
        self.assertEqual(r.json()["meldung"], "Keine Datei abgelegt – nicht abgelegt: nix.jpg (Datei ist leer).")
        self.assertEqual(len(self.dateien(self.vorgang.id)), 2)

    def test_ordner_rueckfall_und_standard(self):
        """Ohne datei_ordner gilt `ordner`; unbekannte Ordner landen in Allgemein; die
        Schreibweisen dateien[] / ordner[] des Plans werden ebenfalls verstanden."""
        self.loeschen(self.vorgang.id)
        r = self.upload(self.admin, self.vorgang.id, [("x.jpg", jpg_bytes()), ("y.jpg", jpg_bytes())],
                        [], ordner="Speicher-Standort")
        self.assertTrue(r.json()["ok"], r.text)
        self.assertEqual([d.ordner for d in self.dateien(self.vorgang.id)],
                         ["Speicher-Standort", "Speicher-Standort"])
        r = self.upload(self.admin, self.vorgang.id, [("z.jpg", jpg_bytes())], ["Gibt es nicht"])
        self.assertEqual(self.dateien(self.vorgang.id)[-1].ordner, "Allgemein")
        files = [("dateien[]", ("p.jpg", io.BytesIO(jpg_bytes()), "image/jpeg"))]
        r = self.admin.post(f"/vorgaenge/{self.vorgang.id}/galerie/upload",
                            data={"sparte": "PV", "ordner[]": ["Dachfläche"], "bemerkung[]": ["Plan"]},
                            files=files, headers={"Accept": "application/json"})
        self.assertEqual(r.status_code, 200, r.text)
        letzte = self.dateien(self.vorgang.id)[-1]
        self.assertEqual((letzte.ordner, letzte.bemerkung), ("Dachfläche", "Plan"))

    def test_bild_wird_auf_2000_px_verkleinert(self):
        """Server-Grenze wie bild_verkleinern.js: längste Kante 2000 px."""
        from PIL import Image
        self.loeschen(self.vorgang.id)
        r = self.upload(self.admin, self.vorgang.id, [("gross.jpg", jpg_bytes((2600, 1200)))],
                        ["Dachfläche"])
        self.assertTrue(r.json()["ok"], r.text)
        datei = self.dateien(self.vorgang.id)[0]
        with Image.open(config.DATA_ORDNER / datei.pfad) as bild:
            self.assertLessEqual(max(bild.size), galerie_modul.MAX_KANTE)
        self.assertTrue(datei.bild)

    def test_zurueck_nur_relative_pfade(self):
        r = self.upload(self.admin, self.vorgang.id, [("r.jpg", jpg_bytes())], ["Dachfläche"],
                        zurueck="https://boese.example/")
        self.assertTrue(r.json()["ziel"].startswith(f"/vorgaenge/{self.vorgang.id}?"))
        self.loeschen(self.vorgang.id)


class Rechte(Basis):
    def test_aussendienst_eigener_vorgang(self):
        c = client_fuer(self.ad.id)
        r = self.upload(c, self.vorgang.id, [("ad.jpg", jpg_bytes())], ["Dachfläche"])
        self.assertEqual(r.status_code, 200, r.text)
        self.assertTrue(r.json()["ok"])
        self.assertEqual(self.dateien(self.vorgang.id)[-1].hochgeladen_von, self.ad.id)
        self.loeschen(self.vorgang.id)
        # fremder Vorgang: JSON 403, Formular-Redirect mit Meldung – nichts abgelegt
        r = self.upload(c, self.vorgang_fremd.id, [("ad.jpg", jpg_bytes())], ["Dachfläche"])
        self.assertEqual(r.status_code, 403)
        self.assertFalse(r.json()["ok"])
        self.assertIn("Kein Upload-Recht", r.json()["meldung"])
        r = self.upload(c, self.vorgang_fremd.id, [("ad.jpg", jpg_bytes())], ["Dachfläche"],
                        json_antwort=False)
        self.assertEqual(r.status_code, 303)
        self.assertIn("Kein+Upload-Recht", r.headers["location"])
        self.assertEqual(self.dateien(self.vorgang_fremd.id), [])
        # anderer Außendienstler ohne Bezug zum Vorgang
        r = self.upload(client_fuer(self.ad_fremd.id), self.vorgang.id, [("f.jpg", jpg_bytes())],
                        ["Dachfläche"])
        self.assertEqual(r.status_code, 403)

    def test_montage_nur_besetzung(self):
        r = self.upload(client_fuer(self.monteur.id), self.vorgang.id, [("m.jpg", jpg_bytes())],
                        ["Zählerschrank"])
        self.assertEqual(r.status_code, 200, r.text)
        self.assertTrue(r.json()["ok"])
        self.loeschen(self.vorgang.id)
        r = self.upload(client_fuer(self.monteur_fremd.id), self.vorgang.id, [("m.jpg", jpg_bytes())],
                        ["Zählerschrank"])
        self.assertEqual(r.status_code, 403)
        self.assertEqual(self.dateien(self.vorgang.id), [])

    def test_projektierung_ja_leadmanagement_nein_unbekannter_vorgang(self):
        r = self.upload(client_fuer(self.projektierer.id), self.vorgang.id, [("p.jpg", jpg_bytes())],
                        ["Dachfläche"])
        self.assertEqual(r.status_code, 200, r.text)
        self.loeschen(self.vorgang.id)
        r = self.upload(client_fuer(self.leadmanager.id), self.vorgang.id, [("l.jpg", jpg_bytes())],
                        ["Dachfläche"])
        self.assertEqual(r.status_code, 403)
        r = self.upload(self.admin, 99_999_999, [("x.jpg", jpg_bytes())], ["Dachfläche"])
        self.assertEqual(r.status_code, 404)
        r = self.upload(self.admin, 99_999_999, [("x.jpg", jpg_bytes())], ["Dachfläche"],
                        json_antwort=False)
        self.assertEqual(r.status_code, 303)
        self.assertEqual(r.headers["location"], "/vorgaenge")


class SammelboxMarkup(Basis):
    def test_vorgangsakte_sammelbox_kamera_serie(self):
        html = self.admin.get(f"/vorgaenge/{self.vorgang.id}").text
        for erwartet in ('class="pj-gal-sammel gal34"', 'data-modus="upload"',
                         f'data-upload-url="/vorgaenge/{self.vorgang.id}/galerie/upload"',
                         'capture="environment" hidden data-gal34="kamera"',
                         'multiple hidden data-gal34="dateien"',
                         'data-start="Fotos aufnehmen" data-weiter="Weiteres Foto"',
                         'class="gal34-vorlage"', 'class="gal34-bemerkung"', "Für alle übernehmen",
                         'class="gal34-fortschritt"', "Fotos hochladen", 'class="pj-btn gal34-abbrechen"',
                         "/static/galerie_v34.js", "/static/galerie_v34.css",
                         'class="haupt-ordner"'):
            self.assertIn(erwartet, html, erwartet)
        self.assertNotIn("pjSammelHochladen", html)
        # Ordner-Dropdown je Datei trägt die Sparten-Ordner der ersten Galerie-Sparte
        # (WP-Rückfall ohne Interessen/Dateien, sonst die Sparte der Dateien)
        vorlage = html[html.index('class="gal34-vorlage"'):html.index("</template>")]
        wp, pv = galerie_modul.ordner_liste(self.s, "WP"), galerie_modul.ordner_liste(self.s, "PV")
        self.assertTrue(f'<option value="{wp[0]}">' in vorlage or f'<option value="{pv[0]}">' in vorlage,
                        vorlage)
        self.assertIn('<option value="Allgemein">', vorlage)

    def test_montage_backend_und_projektakte(self):
        html = client_fuer(self.monteur.id).get(f"/montage/einsatz/{self.termin.id}").text
        self.assertIn('class="pj-gal-sammel gal34"', html)
        self.assertIn('data-gal34="kamera"', html)
        self.assertIn("/static/galerie_v34.js", html)
        html = self.admin.get(f"/projektierung/projekt/{self.gewerk.projekt_id}").text
        self.assertIn('class="pj-gal-sammel gal34"', html)
        self.assertIn("/static/galerie_v34.js", html)

    def test_mobile_erfassung_formular_modus(self):
        """Seite Einschätzung: Sammelbox im Formular-Modus mit galerie_<i> je Ordner;
        die unveränderte Route seite_speichern legt die Dateien in der Galerie ab."""
        from app import logik as logik_modul
        from app.logik import logik_fuer_sparte
        logik = logik_fuer_sparte(logik_modul.hole_logik(self.s)[0], "WP")
        nr = logik.seiten.index("Einschätzung")
        erfassung = Erfassung(kunde_id=self.vorgang.kunde_id, benutzer_id=self.ad.id, sparte="WP",
                              vorgang_id=self.vorgang.id, antworten_json="{}")
        self.s.add(erfassung)
        self.s.commit()
        try:
            c = client_fuer(self.ad.id)
            html = c.get(f"/erfassung/{erfassung.id}/seite/{nr}").text
            ordner = galerie_modul.ordner_liste(self.s, "WP")
            for erwartet in ('data-modus="formular"', 'name="galerie_0" multiple hidden class="gal34-ziel"',
                             f'data-ordner="{ordner[0]}"', 'name="galerie_ordner_0"',
                             'data-gal34="kamera"', "/static/galerie_v34.js", "Fotos aufnehmen",
                             "werden mit „Weiter“ gespeichert"):
                self.assertIn(erwartet, html, erwartet)
            self.assertNotIn("gal34-hochladen", html)
            # Vertrag des Formular-Modus: Dateien je Ordner in galerie_<i> → Galerie des Vorgangs
            self.loeschen(self.vorgang.id)
            files = [("galerie_0", ("e1.jpg", io.BytesIO(jpg_bytes()), "image/jpeg")),
                     ("galerie_0", ("e2.jpg", io.BytesIO(jpg_bytes()), "image/jpeg")),
                     ("galerie_1", ("e3.jpg", io.BytesIO(jpg_bytes()), "image/jpeg"))]
            daten = {"richtung": "zurueck", "galerie_ordner_0": ordner[0],
                     "galerie_ordner_1": ordner[1]}
            r = c.post(f"/erfassung/{erfassung.id}/seite/{nr}", data=daten, files=files,
                       follow_redirects=False)
            self.assertEqual(r.status_code, 303, r.text[:300])
            self.assertEqual([(d.ordner, d.quelle) for d in self.dateien(self.vorgang.id)],
                             [(ordner[0], "erfassung"), (ordner[0], "erfassung"), (ordner[1], "erfassung")])
        finally:
            self.loeschen(self.vorgang.id)
            self.s.delete(erfassung)
            self.s.commit()

    def test_skript_und_styles(self):
        js = (PROJEKT / "app/static/galerie_v34.js").read_text(encoding="utf-8")
        for erwartet in ("XMLHttpRequest", "upload.addEventListener('progress'", "beforeunload",
                         "'datei_ordner'", "'datei_bemerkung'", "window.bildVerkleinern",
                         "'Accept', 'application/json'", "Weiteres Foto", "DataTransfer",
                         "gal34-ziel", "xhr.abort()"):
            self.assertIn(erwartet, js, erwartet)
        css = (PROJEKT / "app/static/galerie_v34.css").read_text(encoding="utf-8")
        self.assertNotRegex(css, r"#[0-9a-fA-F]{3,6}\b")
        self.assertIn("var(--akzent)", css)
        galerie = (PROJEKT / "app/templates/_galerie.html").read_text(encoding="utf-8")
        self.assertNotIn("pjSammelHochladen", galerie)
        self.assertNotIn("'Lade ' + (nr + 1)", galerie)
        self.assertIn("macro sammelbox(", galerie)
        self.assertIn("macro galerie_einbindung()", galerie)
        c = TestClient(app)
        self.assertEqual(c.get("/static/galerie_v34.js").status_code, 200)
        self.assertEqual(c.get("/static/galerie_v34.css").status_code, 200)


class Diktat(Basis):
    def test_knopf_in_erfassung_notizen_montage(self):
        erfassung = Erfassung(kunde_id=self.vorgang.kunde_id, benutzer_id=self.ad.id, sparte="WB",
                              vorgang_id=self.vorgang.id, antworten_json="{}")
        self.s.add(erfassung)
        self.s.commit()
        try:
            html = client_fuer(self.ad.id).get(f"/erfassung/{erfassung.id}/freitext").text
            self.assertIn('id="freitext-feld"', html)
            self.assertIn('class="diktat-knopf knopf klein zweitrangig" data-ziel="freitext-feld"', html)
            self.assertIn("Diktat: bitte das Mikrofon Ihrer Handy-Tastatur verwenden", html)
            self.assertIn("/static/diktat.js", html)
        finally:
            self.s.delete(erfassung)
            self.s.commit()
        html = self.admin.get(f"/vorgaenge/{self.vorgang.id}").text
        self.assertIn(f'id="nc-text-{self.vorgang.id}"', html)
        self.assertIn(f'data-ziel="nc-text-{self.vorgang.id}"', html)
        html = client_fuer(self.monteur.id).get(f"/montage/einsatz/{self.termin.id}").text
        self.assertIn('class="diktat-knopf pj-btn" data-ziel="restarbeit-text"', html)
        formular = (PROJEKT / "app/templates/montage/formular.html").read_text(encoding="utf-8")
        self.assertIn("diktat_knopf('feld-' ~ f.feld_key, 'pj-btn')", formular)
        seite = (PROJEKT / "app/templates/erfassung/seite.html").read_text(encoding="utf-8")
        self.assertIn("diktat_knopf('f_' ~ frage.id)", seite)
        self.assertIn('id="f_{{ frage.id }}"', seite)

    def test_skript_symbol_und_doku(self):
        js = (PROJEKT / "app/static/diktat.js").read_text(encoding="utf-8")
        for erwartet in ("window.isSecureContext", "webkitSpeechRecognition", "'de-DE'",
                         "interimResults = true", "selectionStart",
                         "Diktat: bitte das Mikrofon Ihrer Handy-Tastatur verwenden",
                         "knopf.hidden = true", "var(--status-rot)"):
            self.assertIn(erwartet, js, erwartet)
        self.assertNotRegex(js, r"#[0-9a-fA-F]{3,6}\b")
        symbole = (PROJEKT / "app/templates/_symbole.html").read_text(encoding="utf-8")
        self.assertIn("name == 'mikrofon'", symbole)
        makro = (PROJEKT / "app/templates/_diktat.html").read_text(encoding="utf-8")
        self.assertIn("macro diktat_knopf(feld_id", makro)
        self.assertIn("symbol('mikrofon')", makro)
        self.assertEqual(TestClient(app).get("/static/diktat.js").status_code, 200)
        doku = (PROJEKT / "docs/https-intern.md").read_text(encoding="utf-8")
        for erwartet in ("HTTPS_AKTIV", "BASIS_URL", "PROXY_IPS", "DNS-01", "Geräteprofil",
                         "isSecureContext"):
            self.assertIn(erwartet, doku, erwartet)


CHROME = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
PORT, CDP = 8139, 9349


@unittest.skipUnless(Path(CHROME).exists(), "Chrome nicht installiert")
class SammelboxImBrowser(Basis):
    """Echter Browser (Chrome headless + DevTools, Muster test_v30_navigation): Kamera-Serie
    (zweimal „Fotos aufnehmen“ → „Weiteres Foto“) + Mehrfachauswahl, Ordner je Datei im
    Dropdown, EIN Request für drei Dateien in zwei Ordnern, Seite landet mit Meldung in der
    Akte; Formular-Modus der mobilen Erfassung füllt galerie_<i>; diktat.js initialisiert."""

    @classmethod
    def setUpClass(cls):
        import subprocess
        import urllib.request
        import uvicorn
        super().setUpClass()
        cls.server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=PORT,
                                                   log_level="warning", lifespan="off"))
        cls.thread = threading.Thread(target=cls.server.run, daemon=True)
        cls.thread.start()
        for _ in range(60):
            try:
                urllib.request.urlopen(f"http://127.0.0.1:{PORT}/login", timeout=1)
                break
            except Exception:   # noqa: BLE001
                time.sleep(0.5)
        cls.profil = Path(tempfile.mkdtemp(prefix="chrome_v34_gal_"))
        cls.chrome = subprocess.Popen(
            [CHROME, "--headless=new", f"--remote-debugging-port={CDP}",
             f"--user-data-dir={cls.profil}", "--window-size=390,844", "--no-first-run",
             "--disable-gpu", "about:blank"],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        cls.ws_url = ""
        for _ in range(40):
            try:
                with urllib.request.urlopen(f"http://127.0.0.1:{CDP}/json", timeout=2) as a:
                    seiten = json.loads(a.read().decode("utf-8"))
                cls.ws_url = next(s["webSocketDebuggerUrl"] for s in seiten if s.get("type") == "page")
                break
            except Exception:   # noqa: BLE001
                time.sleep(0.5)
        if not cls.ws_url:
            cls.tearDownClass()
            raise unittest.SkipTest("Chrome DevTools nicht erreichbar")

    @classmethod
    def tearDownClass(cls):
        try:
            cls.chrome.kill()
        except Exception:   # noqa: BLE001
            pass
        cls.server.should_exit = True
        cls.thread.join(timeout=10)
        shutil.rmtree(cls.profil, ignore_errors=True)
        super().tearDownClass()

    def _lauf(self, schritte):
        """schritte(oeffnen, js, warten) als Coroutine; sammelt JS-Ausnahmen der Seite."""
        import websockets
        basis = f"http://127.0.0.1:{PORT}"
        fehler: list[str] = []

        async def lauf():
            async with websockets.connect(self.ws_url, max_size=20_000_000) as ws:
                nr = [0]

                async def senden(methode, **params):
                    nr[0] += 1
                    await ws.send(json.dumps({"id": nr[0], "method": methode, "params": params}))
                    while True:
                        antwort = json.loads(await ws.recv())
                        if antwort.get("method") == "Runtime.exceptionThrown":
                            fehler.append(json.dumps(antwort["params"].get("exceptionDetails", {}))[:400])
                        if antwort.get("id") == nr[0]:
                            return antwort.get("result", {})

                async def oeffnen(pfad, cookie_id=1):
                    await senden("Network.setCookie", name=auth.COOKIE_NAME,
                                 value=auth.cookie_wert(cookie_id), url=basis)
                    await senden("Page.navigate", url=basis + pfad)
                    await asyncio.sleep(1.5)

                async def js(ausdruck):
                    r = await senden("Runtime.evaluate", expression=ausdruck, returnByValue=True,
                                     awaitPromise=True)
                    if "exceptionDetails" in r:
                        fehler.append(json.dumps(r["exceptionDetails"])[:400])
                    return r.get("result", {}).get("value")

                async def warten(sekunden):
                    await asyncio.sleep(sekunden)

                await senden("Network.enable")
                await senden("Runtime.enable")
                await schritte(oeffnen, js, warten)

        asyncio.run(lauf())
        return fehler

    @staticmethod
    def _datei_js(name: str, inhalt: bytes) -> str:
        b64 = base64.b64encode(inhalt).decode("ascii")
        return (f"new File([Uint8Array.from(atob('{b64}'), function (c) {{ return c.charCodeAt(0); }})], "
                f"'{name}', {{type: 'image/jpeg'}})")

    def _hinzufuegen_js(self, selektor: str, dateien) -> str:
        teile = ", ".join(self._datei_js(n, i) for n, i in dateien)
        return (f"(function () {{ var inp = document.querySelector('{selektor}');"
                f" var dt = new DataTransfer(); [{teile}].forEach(function (d) {{ dt.items.add(d); }});"
                f" inp.files = dt.files; inp.dispatchEvent(new Event('change', {{bubbles: true}})); return inp.files.length; }})()")

    def test_kamera_serie_und_ein_upload(self):
        from unittest import mock
        self.loeschen(self.vorgang.id)
        ergebnis = {}
        aufrufe = []
        original = galerie_modul.mehrfach_speichern

        def gezaehlt(*a, **kw):
            aufrufe.append(1)
            return original(*a, **kw)

        async def schritte(oeffnen, js, warten):
            await oeffnen(f"/vorgaenge/{self.vorgang.id}")
            box = "document.querySelector('.pj-gal-sammel.gal34')"
            ergebnis["init"] = await js(f"!!{box} && !!window.gal34")
            # Kamera-Serie: zweimal ein Foto aufnehmen
            await js(self._hinzufuegen_js(".pj-gal-sammel.gal34 input[data-gal34=kamera]",
                                          [("kamera1.jpg", jpg_bytes((60, 40)))]))
            await warten(0.5)
            ergebnis["knopf_nach_1"] = await js(f"{box}.querySelector('.gal34-kamera-text').textContent")
            await js(self._hinzufuegen_js(".pj-gal-sammel.gal34 input[data-gal34=kamera]",
                                          [("kamera2.jpg", jpg_bytes((60, 40), (20, 200, 40)))]))
            # Mehrfachauswahl: eine weitere Datei
            await js(self._hinzufuegen_js(".pj-gal-sammel.gal34 input[data-gal34=dateien]",
                                          [("auswahl.jpg", jpg_bytes((60, 40), (20, 40, 200)))]))
            await warten(0.8)
            ergebnis["zeilen"] = await js(f"{box}.querySelectorAll('.gal34-zeile').length")
            ergebnis["zahl"] = await js(f"{box}.querySelector('.zahl').textContent")
            ergebnis["fuss_sichtbar"] = await js(f"!{box}.querySelector('.fuss').hidden")
            ergebnis["vorschau"] = await js(f"{box}.querySelector('.gal34-zeile img').src.indexOf('blob:') === 0")
            # Ordner je Datei: Zeile 1+2 Standard, Zeile 3 anderer Ordner; Bemerkung an Zeile 1
            await js(f"(function () {{ var s = {box}.querySelectorAll('.gal34-zeile select')[2];"
                     " s.value = 'Allgemein'; s.dispatchEvent(new Event('change', {bubbles: true})); })()")
            await js(f"(function () {{ var b = {box}.querySelector('.gal34-zeile input.gal34-bemerkung');"
                     " b.value = 'aus dem Browser'; b.dispatchEvent(new Event('input', {bubbles: true})); })()")
            ergebnis["standard_ordner"] = await js(f"{box}.querySelector('.haupt-ordner').value")
            # ungesendete Fotos: beforeunload-Warnung hängt am Fenster
            ergebnis["warnung"] = await js(
                "(function () { var ev = new Event('beforeunload', {cancelable: true});"
                " window.dispatchEvent(ev); return ev.defaultPrevented; })()")
            await js(f"{box}.querySelector('.gal34-hochladen').click()")
            await warten(3.0)
            ergebnis["url"] = await js("location.pathname + location.search")
            ergebnis["meldung"] = await js("decodeURIComponent(location.search)")

        with mock.patch.object(galerie_modul, "mehrfach_speichern", side_effect=gezaehlt):
            fehler = self._lauf(schritte)
        self.assertEqual(fehler, [], fehler)
        self.assertTrue(ergebnis["init"], ergebnis)
        self.assertEqual(ergebnis["knopf_nach_1"], "Weiteres Foto", ergebnis)
        self.assertEqual(ergebnis["zeilen"], 3, ergebnis)
        self.assertEqual(ergebnis["zahl"], "3", ergebnis)
        self.assertTrue(ergebnis["fuss_sichtbar"], ergebnis)
        self.assertTrue(ergebnis["vorschau"], ergebnis)
        self.assertTrue(ergebnis["warnung"], ergebnis)
        self.assertEqual(len(aufrufe), 1, "genau EIN Upload-Request")
        self.assertEqual(ergebnis["url"].split("?")[0], f"/vorgaenge/{self.vorgang.id}", ergebnis)
        self.assertIn("3 Datei(en) abgelegt", ergebnis["meldung"].replace("+", " "), ergebnis)
        dateien = self.dateien(self.vorgang.id)
        self.assertEqual([(d.dateiname, d.ordner, d.bemerkung) for d in dateien],
                         [("kamera1.jpg", ergebnis["standard_ordner"], "aus dem Browser"),
                          ("kamera2.jpg", ergebnis["standard_ordner"], ""),
                          ("auswahl.jpg", "Allgemein", "")])
        self.assertEqual(len({d.ordner for d in dateien}), 2)
        self.loeschen(self.vorgang.id)

    def test_formular_modus_und_diktat_init(self):
        from app import logik as logik_modul
        from app.logik import logik_fuer_sparte
        logik = logik_fuer_sparte(logik_modul.hole_logik(self.s)[0], "WP")
        nr = logik.seiten.index("Einschätzung")
        erfassung = Erfassung(kunde_id=self.vorgang.kunde_id, benutzer_id=self.ad.id, sparte="WP",
                              vorgang_id=self.vorgang.id, antworten_json="{}")
        self.s.add(erfassung)
        self.s.commit()
        self.loeschen(self.vorgang.id)
        ergebnis = {}
        try:
            async def schritte(oeffnen, js, warten):
                await oeffnen(f"/erfassung/{erfassung.id}/seite/{nr}", cookie_id=self.ad.id)
                box = "document.querySelector('.pj-gal-sammel.gal34')"
                ergebnis["modus"] = await js(f"{box}.getAttribute('data-modus')")
                await js(self._hinzufuegen_js(".pj-gal-sammel.gal34 input[data-gal34=dateien]",
                                              [("f1.jpg", jpg_bytes((60, 40))), ("f2.jpg", jpg_bytes((60, 40)))]))
                await warten(0.8)
                ergebnis["ziel0"] = await js("document.querySelector('input[name=galerie_0]').files.length")
                ergebnis["ziel1"] = await js("document.querySelector('input[name=galerie_1]').files.length")
                # zweite Datei in den zweiten Ordner
                await js(f"(function () {{ var s = {box}.querySelectorAll('.gal34-zeile select')[1];"
                         " s.selectedIndex = 1; s.dispatchEvent(new Event('change', {bubbles: true})); })()")
                ergebnis["ziel0_danach"] = await js("document.querySelector('input[name=galerie_0]').files.length")
                ergebnis["ziel1_danach"] = await js("document.querySelector('input[name=galerie_1]').files.length")
                ergebnis["verkleinert_markiert"] = await js(
                    "document.getElementById('seitenform').dataset.bilderVerkleinert")
                # Formular mit „Zurück“ absenden → Route speichert die Dateien je Ordner
                await js("document.querySelector('#seitenform button[value=zurueck]').click()")
                await warten(2.5)
                ergebnis["url"] = await js("location.pathname")
                # Diktat-Knopf der Freitext-Erfassung: diktat.js hat initialisiert
                # (Chrome über 127.0.0.1 = sicherer Kontext → „an“; ohne Erkennung „aus“ + Hinweis)
                await oeffnen(f"/erfassung/{erfassung.id}/freitext", cookie_id=self.ad.id)
                ergebnis["diktat"] = await js(
                    "(function () { var k = document.querySelector('.diktat-knopf');"
                    " return k ? (k.getAttribute('data-diktat') || 'ohne') : 'kein Knopf'; })()")
                ergebnis["diktat_hinweis"] = await js(
                    "(function () { var h = document.querySelector('.diktat-hinweis');"
                    " return h ? (h.hidden ? 'versteckt' : h.textContent) : 'kein Hinweis'; })()")
                ergebnis["diktat_api"] = await js("typeof window.friondoDiktat.verfuegbar")

            fehler = self._lauf(schritte)
            self.assertEqual(fehler, [], fehler)
            self.assertEqual(ergebnis["modus"], "formular", ergebnis)
            self.assertEqual((ergebnis["ziel0"], ergebnis["ziel1"]), (2, 0), ergebnis)
            self.assertEqual((ergebnis["ziel0_danach"], ergebnis["ziel1_danach"]), (1, 1), ergebnis)
            self.assertEqual(ergebnis["verkleinert_markiert"], "1", ergebnis)
            self.assertTrue(ergebnis["url"].startswith(f"/erfassung/{erfassung.id}/seite/"), ergebnis)
            self.assertIn(ergebnis["diktat"], ("an", "aus"), ergebnis)
            if ergebnis["diktat"] == "aus":
                self.assertIn("Mikrofon Ihrer Handy-Tastatur", ergebnis["diktat_hinweis"], ergebnis)
            else:
                self.assertEqual(ergebnis["diktat_hinweis"], "versteckt", ergebnis)
            self.assertEqual(ergebnis["diktat_api"], "function", ergebnis)
            ordner = galerie_modul.ordner_liste(self.s, "WP")
            self.assertEqual(sorted((d.dateiname, d.ordner) for d in self.dateien(self.vorgang.id)),
                             [("f1.jpg", ordner[0]), ("f2.jpg", ordner[1])])
        finally:
            self.loeschen(self.vorgang.id)
            self.s.delete(erfassung)
            self.s.commit()


if __name__ == "__main__":
    unittest.main()
