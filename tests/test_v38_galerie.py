# v38 (PLAN_V23 Phase 201, Agent G): Foto-Upload mit Bestätigung (Knopf „Hochladen (n)“, Pop-up mit
# Restdauer und Erfolgs-/Fehlermeldung), Teilerfolgs-Antwort mit Grund je Datei (+ bild/datum für die
# Kacheln ohne Neuladen), Offline-Zwischenspeicher (IndexedDB friondo_galerie_puffer/wartend,
# Hinweiskasten „n Fotos warten auf Upload“, Zeile „Wartende Fotos“ auf /erfassung), Mehrfach-Löschen
# (Auswählen-Modus, Route POST /vorgaenge/<id>/galerie/loeschen, Rechte je Datei: Admin/Innendienst/
# Projektierung alle, Außendienst eigene Uploads, Montage nie). Nur gegen eine DB-Kopie
# (DB_PFAD_OVERRIDE/DATA_ORDNER); Browser-Tests über Chrome headless + DevTools (Muster
# tests/test_v34_galerie.py / test_v30_navigation.py).
import asyncio
import base64
import io
import json
import re
import shutil
import tempfile
import threading
import time
import unittest
import warnings
from datetime import datetime
from pathlib import Path

warnings.filterwarnings("ignore")

from fastapi.testclient import TestClient

from app import auth, config
from app import galerie as galerie_modul
from app import vorgaenge as vorgaenge_modul
from app.db import SessionLocal, init_db
from app.main import app
from app.models import Benutzer, Erfassung, GalerieDatei, Kunde, Vorgang, VorgangNotizGelesen, VorgangsNotiz

PROJEKT = Path(__file__).resolve().parents[1]
PRAEFIX = "V38G-Gal"
TEST_EMAIL = "v38g-galerie@test.local"


def jpg_bytes(groesse=(120, 80), farbe=(200, 40, 40), rauschen=False) -> bytes:
    from PIL import Image
    puffer = io.BytesIO()
    if rauschen:
        import random
        bild = Image.effect_noise(groesse, 64).convert("RGB")
        random.seed(groesse[0])
        bild.save(puffer, format="JPEG", quality=80)
    else:
        Image.new("RGB", groesse, farbe).save(puffer, format="JPEG")
    return puffer.getvalue()


def client_fuer(benutzer_id: int) -> TestClient:
    c = TestClient(app)
    c.cookies.set(auth.COOKIE_NAME, auth.cookie_wert(benutzer_id))
    return c


def aufraeumen(s) -> None:
    for k in s.query(Kunde).filter(Kunde.email == TEST_EMAIL):
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
                shutil.rmtree(ordner, ignore_errors=True)
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
        cls.ad = cls.benutzer_neu("AD", "aussendienst")
        cls.ad_fremd = cls.benutzer_neu("AD fremd", "aussendienst")
        cls.innen = cls.benutzer_neu("Innendienst", "innendienst")
        cls.monteur = cls.benutzer_neu("Monteur", "montage")
        cls.projektierer = cls.benutzer_neu("Projektierer", "projektierung")
        cls.leadmanager = cls.benutzer_neu("Leadmanager", "leadmanagement")
        kunde = Kunde(anrede="Herr", vorname="Paul", nachname=f"{PRAEFIX} Kunde",
                      strasse="Teststr. 5", plz="47139", ort="Duisburg", email=TEST_EMAIL,
                      telefon="0203 1")
        cls.s.add(kunde)
        cls.s.flush()
        cls.vorgang = vorgaenge_modul.vorgang_fuer_kunde(cls.s, kunde.id)
        cls.vorgang.ad_id = cls.ad.id
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
                     email=f"{name.lower().replace(' ', '')}@v38g.test")
        cls.s.add(b)
        cls.s.commit()
        return b

    # --- Helfer ----------------------------------------------------------------------
    def dateien(self, vorgang_id: int) -> list[GalerieDatei]:
        self.s.expire_all()
        return (self.s.query(GalerieDatei).filter_by(vorgang_id=vorgang_id)
                .order_by(GalerieDatei.id).all())

    def leeren(self, vorgang_id: int) -> None:
        for d in self.dateien(vorgang_id):
            (config.DATA_ORDNER / d.pfad).unlink(missing_ok=True)
            self.s.delete(d)
        self.s.query(VorgangsNotiz).filter_by(vorgang_id=vorgang_id).delete()
        self.s.commit()

    def datei_anlegen(self, vorgang_id: int, name: str, ordner: str, benutzer, sparte="PV",
                      inhalt: bytes | None = None) -> GalerieDatei:
        eintrag = galerie_modul.speichern(self.s, vorgang_id, ordner, name, inhalt or jpg_bytes(),
                                          benutzer=benutzer, sparte=sparte)
        self.s.commit()
        return eintrag

    def upload(self, client, vorgang_id, teile, je_ordner, sparte="PV", **felder):
        files = [("dateien", (name, io.BytesIO(inhalt), "image/jpeg" if name.endswith(".jpg")
                              else "application/pdf")) for name, inhalt in teile]
        daten = {"sparte": sparte, "zurueck": f"/vorgaenge/{vorgang_id}"}
        if je_ordner:
            daten["datei_ordner"] = list(je_ordner)
        daten.update(felder)
        return client.post(f"/vorgaenge/{vorgang_id}/galerie/upload", data=daten, files=files,
                           headers={"Accept": "application/json"}, follow_redirects=False)

    def loeschen_post(self, client, vorgang_id, ids, json_antwort=True, **felder):
        daten = {"datei_ids": [str(i) for i in ids]}
        daten.update(felder)
        headers = {"Accept": "application/json"} if json_antwort else {}
        return client.post(f"/vorgaenge/{vorgang_id}/galerie/loeschen", data=daten,
                           headers=headers, follow_redirects=False)

    def notizen(self, vorgang_id: int) -> list[str]:
        self.s.expire_all()
        return [n.text for n in self.s.query(VorgangsNotiz).filter_by(vorgang_id=vorgang_id)
                .order_by(VorgangsNotiz.id)]


class TeilerfolgAntwort(Basis):
    def test_grund_je_datei_und_felder_fuer_kacheln(self):
        """Teilerfolg: fehler[] trägt Name + Grund je Datei; abgelegt[] zusätzlich bild und Datum
        (TT.MM.), damit galerie_v38.js die Kacheln ohne Seitenneuladen anhängen kann."""
        self.leeren(self.vorgang.id)
        r = self.upload(self.admin, self.vorgang.id,
                        [("gut1.jpg", jpg_bytes()), ("leer.jpg", b""), ("gut2.jpg", jpg_bytes()),
                         ("plan.pdf", b"%PDF-1.4 demo")],
                        ["Zählerschrank", "Zählerschrank", "Dachfläche", "Allgemein"])
        self.assertEqual(r.status_code, 200, r.text)
        antwort = r.json()
        self.assertFalse(antwort["ok"])
        self.assertEqual(antwort["fehler"], [{"nr": 1, "name": "leer.jpg", "grund": "Datei ist leer"}])
        heute = datetime.now().strftime("%d.%m.")
        self.assertEqual([(a["nr"], a["name"], a["ordner"], a["bild"], a["datum"]) for a in antwort["abgelegt"]],
                         [(0, "gut1.jpg", "Zählerschrank", True, heute),
                          (2, "gut2.jpg", "Dachfläche", True, heute),
                          (3, "plan.pdf", "Allgemein", False, heute)])
        self.assertTrue(all(re.match(r"\d\d\.\d\d\.\d{4} \d\d:\d\d", a["datum_lang"]) for a in antwort["abgelegt"]))
        self.assertIn("nicht abgelegt: leer.jpg (Datei ist leer)", antwort["meldung"])
        self.leeren(self.vorgang.id)


class MehrfachLoeschen(Basis):
    def test_drei_ids_zwei_erlaubt_eine_fremd(self):
        """Kontrollwert des Plans: Außendienst wählt drei Dateien – zwei eigene, eine vom Innendienst
        → zwei gelöscht (Datei + Datensatz weg), eine abgelehnt; Eintrag im Notizen-Chat."""
        self.leeren(self.vorgang.id)
        a = self.datei_anlegen(self.vorgang.id, "a.jpg", "Zählerschrank", self.ad)
        b = self.datei_anlegen(self.vorgang.id, "b.jpg", "Zählerschrank", self.ad)
        c = self.datei_anlegen(self.vorgang.id, "c.jpg", "Zählerschrank", self.innen)
        pfade = {d.id: config.DATA_ORDNER / d.pfad for d in (a, b, c)}
        self.assertTrue(all(p.exists() for p in pfade.values()))
        r = self.loeschen_post(client_fuer(self.ad.id), self.vorgang.id, [a.id, b.id, c.id])
        self.assertEqual(r.status_code, 200, r.text)
        antwort = r.json()
        self.assertFalse(antwort["ok"])
        self.assertEqual(antwort["geloescht"], [a.id, b.id])
        self.assertEqual(antwort["abgelehnt"], [c.id])
        self.assertEqual(antwort["meldung"],
                         "2 von 3 Fotos gelöscht – 1 ohne Löschrecht oder nicht (mehr) in diesem Vorgang.")
        self.assertFalse(pfade[a.id].exists())
        self.assertFalse(pfade[b.id].exists())
        self.assertTrue(pfade[c.id].exists())
        self.assertEqual([d.id for d in self.dateien(self.vorgang.id)], [c.id])
        notizen = self.notizen(self.vorgang.id)
        self.assertTrue(any(n.startswith("Galerie: 2 Fotos gelöscht (Ordner Zählerschrank): a.jpg, b.jpg")
                            for n in notizen), notizen)
        # Innendienst darf die dritte: volle Erfolgsantwort
        r = self.loeschen_post(client_fuer(self.innen.id), self.vorgang.id, [c.id])
        self.assertEqual(r.status_code, 200, r.text)
        self.assertEqual(r.json(), {"ok": True, "geloescht": [c.id], "abgelehnt": [],
                                    "meldung": "1 Foto gelöscht."})
        self.assertFalse(pfade[c.id].exists())
        self.assertEqual(self.dateien(self.vorgang.id), [])

    def test_formular_redirect_fremde_ids_leer_unbekannt(self):
        self.leeren(self.vorgang.id)
        eigene = self.datei_anlegen(self.vorgang.id, "e.jpg", "Dachfläche", self.ad)
        fremde = self.datei_anlegen(self.vorgang_fremd.id, "f.jpg", "Dachfläche", self.innen)
        # Formular ohne Accept: Redirect mit Meldung ans Ziel (nur relative Pfade)
        r = self.loeschen_post(self.admin, self.vorgang.id, [eigene.id, fremde.id, "x", eigene.id],
                               json_antwort=False, zurueck="https://boese.example/")
        self.assertEqual(r.status_code, 303)
        self.assertTrue(r.headers["location"].startswith(f"/vorgaenge/{self.vorgang.id}?meldung="))
        self.assertIn("1+von+2+Fotos+gel", r.headers["location"])
        self.assertTrue(r.headers["location"].endswith("#galerie"))
        self.assertEqual(self.dateien(self.vorgang.id), [])
        self.assertEqual([d.id for d in self.dateien(self.vorgang_fremd.id)], [fremde.id])   # fremder Vorgang unberührt
        # keine IDs → 400; unbekannter Vorgang → 404 (JSON) bzw. Redirect /vorgaenge
        r = self.loeschen_post(self.admin, self.vorgang.id, [])
        self.assertEqual(r.status_code, 400)
        self.assertEqual(r.json()["meldung"], "Keine Dateien ausgewählt.")
        r = self.loeschen_post(self.admin, 99_999_999, [fremde.id])
        self.assertEqual(r.status_code, 404)
        r = self.loeschen_post(self.admin, 99_999_999, [fremde.id], json_antwort=False)
        self.assertEqual((r.status_code, r.headers["location"]), (303, "/vorgaenge"))
        self.leeren(self.vorgang_fremd.id)

    def test_rechte_je_rolle(self):
        """Admin/Innendienst/Projektierung alle Dateien, Außendienst nur eigene im eigenen Vorgang,
        Montage und Leadmanagement nie (Pfadtabelle auth.py bzw. Rolle), fremder AD ohne Zugriff 403."""
        self.leeren(self.vorgang.id)
        von_ad = self.datei_anlegen(self.vorgang.id, "ad.jpg", "Zählerschrank", self.ad)
        von_innen = self.datei_anlegen(self.vorgang.id, "id.jpg", "Zählerschrank", self.innen)
        # Rechtefunktion je Datei
        self.assertTrue(galerie_modul.darf_datei_loeschen(self.s.get(Benutzer, 1), von_ad))
        self.assertTrue(galerie_modul.darf_datei_loeschen(self.innen, von_ad))
        self.assertTrue(galerie_modul.darf_datei_loeschen(self.projektierer, von_ad))
        self.assertTrue(galerie_modul.darf_datei_loeschen(self.ad, von_ad))
        self.assertFalse(galerie_modul.darf_datei_loeschen(self.ad, von_innen))
        self.assertFalse(galerie_modul.darf_datei_loeschen(self.ad_fremd, von_ad))
        self.assertFalse(galerie_modul.darf_datei_loeschen(self.leadmanager, von_ad))
        self.assertFalse(galerie_modul.darf_datei_loeschen(None, von_ad))
        # Montage: auch der eigene Upload ist nicht löschbar (heutige Regel, Plan: nicht darüber hinaus)
        von_monteur = GalerieDatei(vorgang_id=self.vorgang.id, sparte="PV", ordner="Zählerschrank",
                                   dateiname="m.jpg", pfad="", bild=True, hochgeladen_von=self.monteur.id)
        self.assertFalse(galerie_modul.darf_datei_loeschen(self.monteur, von_monteur))
        self.assertEqual(galerie_modul.loeschrecht(self.ad),
                         {"benutzer_id": self.ad.id, "eigene": True, "alle": False})
        self.assertEqual(galerie_modul.loeschrecht(self.innen)["alle"], True)
        self.assertEqual(galerie_modul.loeschrecht(None), {"benutzer_id": None, "eigene": False, "alle": False})
        # Routen: fremder AD → 403 (kein Zugriff auf den Vorgang), Montage/Leadmanagement → Umleitung
        r = self.loeschen_post(client_fuer(self.ad_fremd.id), self.vorgang.id, [von_ad.id])
        self.assertEqual(r.status_code, 403)
        self.assertEqual(r.json()["abgelehnt"], [von_ad.id])
        r = self.loeschen_post(client_fuer(self.monteur.id), self.vorgang.id, [von_ad.id])
        self.assertEqual((r.status_code, r.headers["location"]), (303, "/montage"))
        # Leadmanagement darf unter /vorgaenge schreiben (Notizen-Chat), hat aber kein Galerie-Recht → 403
        r = self.loeschen_post(client_fuer(self.leadmanager.id), self.vorgang.id, [von_ad.id])
        self.assertEqual(r.status_code, 403)
        self.assertFalse(r.json()["ok"])
        self.assertEqual(len(self.dateien(self.vorgang.id)), 2)
        # AD: eigene ja, fremde abgelehnt – Projektierung (Pfadtabelle _GALERIE_SCHREIBEN) darf alle
        r = self.loeschen_post(client_fuer(self.ad.id), self.vorgang.id, [von_innen.id])
        self.assertEqual(r.status_code, 200, r.text)
        self.assertEqual((r.json()["geloescht"], r.json()["abgelehnt"]), ([], [von_innen.id]))
        r = self.loeschen_post(client_fuer(self.projektierer.id), self.vorgang.id, [von_ad.id, von_innen.id])
        self.assertEqual(r.status_code, 200, r.text)
        self.assertEqual(r.json()["geloescht"], [von_ad.id, von_innen.id])
        self.assertEqual(self.dateien(self.vorgang.id), [])
        self.assertTrue(auth._GALERIE_SCHREIBEN.match(f"/vorgaenge/{self.vorgang.id}/galerie/loeschen"))
        self.assertFalse(auth._MONTAGE_GALERIE.match(f"/vorgaenge/{self.vorgang.id}/galerie/loeschen"))

    def test_pfade_erst_nach_commit_entfernt(self):
        """Datei-I/O liegt außerhalb der Schreibtransaktion: mehrfach_loeschen sammelt die Pfade,
        dateien_entfernen löscht sie danach; ohne Sammelliste löscht die Funktion sofort."""
        self.leeren(self.vorgang.id)
        d1 = self.datei_anlegen(self.vorgang.id, "p1.jpg", "Dachfläche", self.ad)
        d2 = self.datei_anlegen(self.vorgang.id, "p2.jpg", "Dachfläche", self.ad)
        pfad1, pfad2 = config.DATA_ORDNER / d1.pfad, config.DATA_ORDNER / d2.pfad
        pfade: list = []
        geloescht, abgelehnt = galerie_modul.mehrfach_loeschen(self.s, self.vorgang, [d1.id], self.ad,
                                                              pfade_sammeln=pfade)
        self.assertEqual((geloescht, abgelehnt), ([d1.id], []))
        self.assertTrue(pfad1.exists())   # noch da – erst nach dem Commit
        self.s.commit()
        self.assertEqual(galerie_modul.dateien_entfernen(pfade), 1)
        self.assertFalse(pfad1.exists())
        geloescht, _ = galerie_modul.mehrfach_loeschen(self.s, self.vorgang, [d2.id], self.ad)
        self.s.commit()
        self.assertEqual(geloescht, [d2.id])
        self.assertFalse(pfad2.exists())
        self.assertEqual(galerie_modul.loesch_meldung([], [], True), "Keine Dateien ausgewählt.")
        self.assertEqual(galerie_modul.loesch_meldung([1, 2, 3], [], True), "3 Fotos gelöscht.")
        self.assertEqual(galerie_modul.loesch_meldung([1], [], False), "1 Datei gelöscht.")
        self.assertIn("Keine Datei gelöscht", galerie_modul.loesch_meldung([], [7], True))


class Markup(Basis):
    def test_vorgangsakte_kaestchen_nur_mit_loeschrecht(self):
        self.leeren(self.vorgang.id)
        self.datei_anlegen(self.vorgang.id, "k1.jpg", "Zählerschrank", self.ad)
        self.datei_anlegen(self.vorgang.id, "k2.jpg", "Zählerschrank", self.ad)
        self.datei_anlegen(self.vorgang.id, "k3.jpg", "Zählerschrank", self.innen)
        self.datei_anlegen(self.vorgang.id, "k4.jpg", "Zählerschrank", self.innen)
        html = client_fuer(self.ad.id).get(f"/vorgaenge/{self.vorgang.id}").text
        for erwartet in ('data-gal38', 'data-loeschen-eigene="1"', f'data-benutzer="{self.ad.id}"',
                         'data-loeschen-alle="0"', f'data-loeschen-url="/vorgaenge/{self.vorgang.id}/galerie/loeschen"',
                         'data-gal38-wartend', 'class="pj-btn primary gal38-wartend-hochladen"', 'Jetzt hochladen',
                         'class="pj-btn gal38-wartend-verwerfen"', 'Verwerfen',
                         'class="pj-btn primary gal34-hochladen" type="button" disabled>⬆ Hochladen (<span class="zahl">0</span>)',
                         'dialog class="pj-dlg gal38-dialog"', 'Fotos werden hochgeladen', 'gal38-dlg-dauer',
                         'class="pj-btn primary gal38-dlg-erneut"', 'data-gal38-leiste="ordner" data-ordner="Zählerschrank"',
                         'data-gal38-leiste="liste"', 'class="pj-btn danger gal38-loeschen"', 'gal38-auswahl-ende',
                         '/static/galerie_v38.js', '/static/galerie_v38.css', '/static/galerie_puffer.js'):
            self.assertIn(erwartet, html, erwartet)
        self.assertNotIn("Fotos hochladen</button>", html)
        self.assertEqual(html.count('data-loeschbar="1"'), 2)          # nur die eigenen zwei
        self.assertEqual(html.count('class="gal38-kasten" hidden><input type="checkbox" class="gal38-wahl" value='), 2)
        # Ordner mit löschbaren Dateien zeigt „Auswählen“, Ordner ohne nicht (Knopf versteckt)
        knopf = re.compile(r'<button type="button" class="pj-btn gal38-auswaehlen" data-gal38-ziel="ordner"\s*(hidden)?>Auswählen')
        block = html[html.index('data-ordner="Zählerschrank"'):html.index('data-ordner="Speicher-Standort"')]
        self.assertIsNone(knopf.search(block).group(1), block[:400])
        leer = html[html.index('data-ordner="Speicher-Standort"'):]
        self.assertEqual(knopf.search(leer).group(1), "hidden")
        # Admin: alle vier löschbar; fremder AD ohne Zugriff: keine Akte
        html = self.admin.get(f"/vorgaenge/{self.vorgang.id}").text
        self.assertEqual(html.count('data-loeschbar="1"'), 4)
        self.assertIn('data-loeschen-alle="1"', html)
        self.assertNotIn('data-loeschen-eigene="1"', html)
        self.leeren(self.vorgang.id)

    def test_erfassung_startseite_zeile_und_skripte(self):
        html = client_fuer(self.ad.id).get("/erfassung").text
        self.assertIn('data-gal38-puffer-zeile', html)
        self.assertIn('class="gal38-puffer-liste"', html)
        self.assertIn("Wartende Fotos:", html)
        self.assertIn("/static/galerie_puffer.js", html)
        self.assertIn("/static/galerie_v38.js", html)
        partial = (PROJEKT / "app/templates/erfassung/_galerie_puffer.html").read_text(encoding="utf-8")
        self.assertIn("data-gal38-puffer-zeile", partial)
        uebersicht = (PROJEKT / "app/templates/erfassung/uebersicht.html").read_text(encoding="utf-8")
        self.assertEqual(uebersicht.count('{% include "erfassung/_galerie_puffer.html" %}'), 1)

    def test_skripte_styles_und_tokens(self):
        js34 = (PROJEKT / "app/static/galerie_v34.js").read_text(encoding="utf-8")
        for erwartet in ("START_BYTES_JE_S = 500 * 1024", "Voraussichtlich noch ca. ", "Gleich fertig",
                         "DAUER_TAKT_MS = 2000", "GLEICH_FERTIG_S = 5", "SCHLIESSEN_NACH_MS = 3000",
                         "Kein Netz. Die Fotos bleiben gespeichert und werden später hochgeladen.",
                         "Zwischenspeicher voll, bitte zuerst hochladen", "dialogStart(box, gesendet)",
                         "window.galPuffer.hinzufuegen", "markierenVorgangFehlt", "ev.preventDefault()",
                         "gal34:hochgeladen", "dateienHinzufuegen", "xhr.ontimeout", "xhr.abort()",
                         "upload.addEventListener('progress'", "window.bildVerkleinern(datei)"):
            self.assertIn(erwartet, js34, erwartet)
        self.assertNotIn("window.location = antwort.ziel", js34)   # keine Navigation mehr nach dem Upload
        puffer = (PROJEKT / "app/static/galerie_puffer.js").read_text(encoding="utf-8")
        for erwartet in ("'friondo_galerie_puffer'", "'wartend'", "MAX_ANZAHL = 50", "MAX_BYTES = 100 * 1024 * 1024",
                         "indexedDB.open", "createIndex('vorgang'", "Vorgang nicht mehr vorhanden",
                         "window.galPuffer"):
            self.assertIn(erwartet, puffer, erwartet)
        js38 = (PROJEKT / "app/static/galerie_v38.js").read_text(encoding="utf-8")
        for erwartet in ("endgültig löschen? Das lässt sich nicht rückgängig machen.", "/galerie/loeschen",
                         "'datei_ids'", "warten auf Upload", "Wartende Fotos", "gal34:hochgeladen",
                         "data-gal38-puffer-zeile", "jetztHochladen", "verwerfen", "kachelBauen"):
            self.assertIn(erwartet, js38, erwartet)
        for datei in ("galerie_v34.js", "galerie_v38.js", "galerie_puffer.js"):
            text = (PROJEKT / "app/static" / datei).read_text(encoding="utf-8")
            self.assertNotRegex(text, r"#[0-9a-fA-F]{3,6}\b", datei)
            self.assertNotIn("=>", text, f"{datei}: ES5 ohne Pfeilfunktionen")
            self.assertNotRegex(text, r"\b(let|const)\s+\w+\s*=", f"{datei}: ES5 ohne let/const")
        css = (PROJEKT / "app/static/galerie_v38.css").read_text(encoding="utf-8")
        for zeile in css.splitlines():
            if re.search(r"#[0-9a-fA-F]{3,6}\b", zeile):
                self.assertIn("fest:", zeile, zeile)
        for token in ("var(--status-gruen)", "var(--status-orange)", "var(--status-rot)", "var(--akzent)",
                      "var(--flaeche-karte)", "var(--status-orange-bg)"):
            self.assertIn(token, css, token)
        c = TestClient(app)
        for pfad in ("/static/galerie_v38.js", "/static/galerie_v38.css", "/static/galerie_puffer.js"):
            self.assertEqual(c.get(pfad).status_code, 200, pfad)
        galerie = (PROJEKT / "app/templates/_galerie.html").read_text(encoding="utf-8")
        self.assertIn("macro galerie_upload_dialog()", galerie)
        self.assertIn("galerie_loeschrecht()", galerie)
        self.assertNotIn("tojson", galerie.split("macro galerie_upload_dialog()")[1].split("endmacro")[0])


CHROME = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
PORT, CDP = 8141, 9351


@unittest.skipUnless(Path(CHROME).exists(), "Chrome nicht installiert")
class GalerieImBrowser(Basis):
    """Echter Browser (Chrome headless + DevTools): Pop-up mit Restdauer und Erfolgsmeldung, Kacheln
    ohne Neuladen, simulierter Netzfehler → IndexedDB-Puffer, Hinweiskasten nach Neuladen, Zeile auf
    /erfassung, „Jetzt hochladen“ leert den Puffer, Auswählen-Modus mit Mehrfach-Löschen."""

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
        cls.profil = Path(tempfile.mkdtemp(prefix="chrome_v38_gal_"))
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
        import websockets
        basis = f"http://127.0.0.1:{PORT}"
        fehler: list[str] = []

        async def lauf():
            async with websockets.connect(self.ws_url, max_size=40_000_000) as ws:
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

    PUFFER_LEEREN = ("window.galPuffer.alle().then(function (l) { return window.galPuffer.entfernen("
                     "l.map(function (e) { return e.id; })); })")

    def test_popup_dauer_erfolg_und_kacheln_ohne_neuladen(self):
        """Kontrollwert: drei Fotos → „Hochladen (3)“ → Pop-up mit Restdauer → „3 Fotos hochgeladen“,
        Liste leer, drei neue Kacheln im Ordner ohne Seitenneuladen; Pop-up schließt von selbst."""
        self.leeren(self.vorgang.id)
        ergebnis = {}
        gross = jpg_bytes((1400, 1400), rauschen=True)   # ~ 1,1 MB je Datei → Schätzung (3,3 MB / 500 KB/s) über 5 s

        async def schritte(oeffnen, js, warten):
            await oeffnen(f"/vorgaenge/{self.vorgang.id}", cookie_id=self.ad.id)
            await js(self.PUFFER_LEEREN)
            box = "document.querySelector('.pj-gal-sammel.gal34')"
            ergebnis["init"] = await js("!!window.gal34 && !!window.gal38 && !!window.galPuffer && window.galPuffer.verfuegbar()")
            ergebnis["knopf_leer"] = await js(f"{box}.querySelector('.gal34-hochladen').disabled")
            ergebnis["dauer_fn"] = await js("window.gal34.dauerText(20) + '|' + window.gal34.dauerText(3)")
            await js(self._hinzufuegen_js(".pj-gal-sammel.gal34 input[data-gal34=dateien]",
                                          [("eins.jpg", gross), ("zwei.jpg", gross), ("drei.jpg", gross)]))
            await warten(1.5)
            ergebnis["knopf"] = await js(f"{box}.querySelector('.gal34-hochladen').textContent.replace(/\\s+/g, ' ').trim()")
            ergebnis["knopf_aktiv"] = await js(f"!{box}.querySelector('.gal34-hochladen').disabled")
            ergebnis["url_vorher"] = await js("location.pathname + location.search")
            # Klick + sofortige Werte aus dem Pop-up (synchron im selben Ausdruck)
            ergebnis["start"] = await js(
                f"(function () {{ var b = {box}; b.querySelector('.gal34-hochladen').click();"
                " var d = b.querySelector('dialog.gal38-dialog');"
                " return { offen: d.open, titel: d.querySelector('.gal38-dlg-titel').textContent,"
                " dauer: d.querySelector('.gal38-dlg-dauer').textContent,"
                " zeilen: d.querySelectorAll('.gal38-dlg-zeile').length,"
                " abbrechen: !d.querySelector('.gal38-dlg-abbrechen').hidden,"
                " schliessen: d.querySelector('.gal38-dlg-schliessen').hidden }; })()")
            await warten(2.5)
            ergebnis["fertig"] = await js(
                f"(function () {{ var d = {box}.querySelector('dialog.gal38-dialog');"
                " return { titel: d.querySelector('.gal38-dlg-titel').textContent, klasse: d.className,"
                " offen: d.open, schliessen: !d.querySelector('.gal38-dlg-schliessen').hidden,"
                " erneut: d.querySelector('.gal38-dlg-erneut').hidden,"
                " balken: d.querySelector('.gal38-dlg-gesamt').value }; })()")
            ergebnis["liste"] = await js(f"{box}.querySelectorAll('.gal34-zeile').length")
            ergebnis["kacheln"] = await js(
                "document.querySelectorAll('details.pj-gal-ordner[data-ordner] figure[data-datei]').length")
            ergebnis["neu"] = await js("document.querySelectorAll('figure.gal38-neu').length")
            ergebnis["kasten_neu"] = await js("document.querySelectorAll('figure.gal38-neu .gal38-kasten').length")
            ergebnis["zaehler"] = await js(
                "(function () { var d = document.querySelector('details.pj-gal-ordner[open]');"
                " return d ? d.querySelector('summary .n').textContent : ''; })()")
            ergebnis["auswaehlen_sichtbar"] = await js(
                "(function () { var d = document.querySelector('details.pj-gal-ordner[open]');"
                " return d ? !d.querySelector('.gal38-auswaehlen').hidden : null; })()")
            await warten(2.0)
            ergebnis["zu"] = await js(f"!{box}.querySelector('dialog.gal38-dialog').open")
            ergebnis["url_nachher"] = await js("location.pathname + location.search")

        fehler = self._lauf(schritte)
        self.assertEqual(fehler, [], fehler)
        self.assertTrue(ergebnis["init"], ergebnis)
        self.assertEqual(ergebnis["dauer_fn"], "Voraussichtlich noch ca. 20 Sekunden|Gleich fertig …")
        self.assertEqual(ergebnis["knopf"], "⬆ Hochladen (3)", ergebnis)
        self.assertTrue(ergebnis["knopf_aktiv"], ergebnis)
        start = ergebnis["start"]
        self.assertTrue(start["offen"], start)
        self.assertEqual(start["titel"], "Fotos werden hochgeladen")
        self.assertTrue(start["dauer"].startswith("Voraussichtlich noch ca.") and start["dauer"].endswith("Sekunden"), start)
        self.assertEqual(start["zeilen"], 3)
        self.assertTrue(start["abbrechen"] and start["schliessen"], start)   # nur Abbrechen während des Uploads
        fertig = ergebnis["fertig"]
        self.assertEqual(fertig["titel"], "3 Fotos hochgeladen", fertig)
        self.assertIn("erfolg", fertig["klasse"])
        self.assertTrue(fertig["schliessen"] and fertig["erneut"], fertig)
        self.assertEqual(fertig["balken"], 100)
        self.assertEqual(ergebnis["liste"], 0)
        self.assertEqual(ergebnis["kacheln"], 3, ergebnis)
        self.assertEqual(ergebnis["neu"], 3)
        self.assertEqual(ergebnis["kasten_neu"], 3)          # eigener Upload → Kästchen (versteckt) vorhanden
        self.assertEqual(ergebnis["zaehler"], "3")
        self.assertTrue(ergebnis["auswaehlen_sichtbar"])
        self.assertTrue(ergebnis["zu"], "Pop-up schließt nach 3 Sekunden von selbst")
        self.assertEqual(ergebnis["url_vorher"], ergebnis["url_nachher"])   # kein Seitenneuladen
        self.assertEqual(sorted(d.dateiname for d in self.dateien(self.vorgang.id)), ["drei.jpg", "eins.jpg", "zwei.jpg"])
        self.assertEqual(ergebnis["knopf_leer"], True)
        self.leeren(self.vorgang.id)

    def test_kein_netz_puffer_hinweiskasten_jetzt_hochladen(self):
        """Simulierter Netzfehler (Upload-Adresse ohne Server) → „Kein Netz …“, Einträge in IndexedDB,
        Liste leer; nach Neuladen Hinweiskasten „2 Fotos warten auf Upload (seit …)“, Zeile auf
        /erfassung; „Jetzt hochladen“ legt die Dateien im richtigen Ordner ab und leert den Puffer."""
        self.leeren(self.vorgang.id)
        ergebnis = {}

        async def schritte(oeffnen, js, warten):
            await oeffnen(f"/vorgaenge/{self.vorgang.id}", cookie_id=self.ad.id)
            await js(self.PUFFER_LEEREN)
            box = "document.querySelector('.pj-gal-sammel.gal34')"
            # erste Galerie-Sparte der Akte (ohne Interessen/Dateien WP) – Ordnerliste dieser Sparte
            ergebnis["sparte"] = await js(f"{box}.getAttribute('data-sparte')")
            await js(f"{box}.setAttribute('data-upload-url', 'http://127.0.0.1:1/galerie/upload')")
            await js(self._hinzufuegen_js(".pj-gal-sammel.gal34 input[data-gal34=dateien]",
                                          [("o1.jpg", jpg_bytes((60, 40))), ("o2.jpg", jpg_bytes((60, 40), (20, 200, 40)))]))
            await warten(1.0)
            # beide Zeilen in den zweiten Ordner der Sparte
            await js(f"(function () {{ Array.prototype.forEach.call({box}.querySelectorAll('.gal34-zeile select'), function (s) {{"
                     " s.selectedIndex = 1; s.dispatchEvent(new Event('change', {bubbles: true})); }); })()")
            ergebnis["ordner"] = await js(f"{box}.querySelector('.gal34-zeile select').value")
            await js(f"{box}.querySelector('.gal34-hochladen').click()")
            await warten(2.5)
            ergebnis["dialog"] = await js(
                f"(function () {{ var d = {box}.querySelector('dialog.gal38-dialog');"
                " return { titel: d.querySelector('.gal38-dlg-titel').textContent,"
                " meldung: d.querySelector('.gal38-dlg-meldung').textContent, klasse: d.className,"
                " schliessen: !d.querySelector('.gal38-dlg-schliessen').hidden }; })()")
            ergebnis["liste"] = await js(f"{box}.querySelectorAll('.gal34-zeile').length")
            ergebnis["puffer"] = await js(
                "window.galPuffer.alle().then(function (l) { return l.map(function (e) {"
                " return [e.vorgang_id, e.sparte, e.ordner, e.name, e.groesse > 0, !!e.blob]; }); })")
            ergebnis["kasten_sofort"] = await js(
                "(function () { var k = document.querySelector('[data-gal38-wartend]');"
                " return k ? [!k.hidden, k.querySelector('.gal38-wartend-text').textContent] : null; })()")
            # Neu laden: Hinweiskasten aus dem Puffer
            await oeffnen(f"/vorgaenge/{self.vorgang.id}", cookie_id=self.ad.id)
            await warten(0.5)
            ergebnis["kasten"] = await js(
                "(function () { var k = document.querySelector('[data-gal38-wartend]');"
                " return k ? [!k.hidden, k.querySelector('.gal38-wartend-text').textContent,"
                " !k.querySelector('.gal38-wartend-hochladen').hidden] : null; })()")
            # Startseite der mobilen Erfassung zeigt die Zeile
            await oeffnen("/erfassung", cookie_id=self.ad.id)
            await warten(0.5)
            ergebnis["zeile"] = await js(
                "(function () { var z = document.querySelector('[data-gal38-puffer-zeile]');"
                " return z ? [!z.hidden, z.textContent.replace(/\\s+/g, ' ').trim(),"
                " z.querySelector('a') ? z.querySelector('a').getAttribute('href') : ''] : null; })()")
            # zurück zur Akte, „Jetzt hochladen“
            await oeffnen(f"/vorgaenge/{self.vorgang.id}", cookie_id=self.ad.id)
            await warten(0.5)
            await js("document.querySelector('.gal38-wartend-hochladen').click()")
            await warten(3.0)
            ergebnis["nach_upload"] = await js(
                "(function () { var d = document.querySelector('dialog.gal38-dialog');"
                " return { titel: d.querySelector('.gal38-dlg-titel').textContent,"
                " kasten: document.querySelector('[data-gal38-wartend]').hidden,"
                " liste: document.querySelectorAll('.gal34-zeile').length }; })()")
            ergebnis["puffer_danach"] = await js("window.galPuffer.alle().then(function (l) { return l.length; })")
            await warten(0.3)
            ergebnis["zeile_danach"] = await js(
                "window.galPuffer.zusammenfassung().then(function (g) { return g.length; })")

        fehler = self._lauf(schritte)
        self.assertEqual(fehler, [], fehler)
        ordner = galerie_modul.ordner_liste(self.s, ergebnis["sparte"])
        self.assertEqual(ergebnis["ordner"], ordner[1], ergebnis)
        dialog = ergebnis["dialog"]
        self.assertEqual(dialog["meldung"], "Kein Netz. Die Fotos bleiben gespeichert und werden später hochgeladen.", dialog)
        self.assertIn("fehler", dialog["klasse"])
        self.assertTrue(dialog["schliessen"], dialog)
        self.assertEqual(ergebnis["liste"], 0, "Liste geleert – Fotos liegen im Zwischenspeicher")
        self.assertEqual(ergebnis["puffer"], [[self.vorgang.id, ergebnis["sparte"], ordner[1], "o1.jpg", True, True],
                                              [self.vorgang.id, ergebnis["sparte"], ordner[1], "o2.jpg", True, True]])
        self.assertTrue(ergebnis["kasten_sofort"] and ergebnis["kasten_sofort"][0], ergebnis)
        kasten = ergebnis["kasten"]
        self.assertTrue(kasten and kasten[0] and kasten[2], kasten)
        self.assertRegex(kasten[1], r"^2 Fotos warten auf Upload \(seit \d\d\.\d\d\., \d\d:\d\d\)$")
        zeile = ergebnis["zeile"]
        self.assertTrue(zeile and zeile[0], zeile)
        self.assertRegex(zeile[1], r"^Wartende Fotos: Vorgang .* \(2\)$")
        self.assertEqual(zeile[2], f"/vorgaenge/{self.vorgang.id}#galerie")
        self.assertEqual(ergebnis["nach_upload"]["titel"], "2 Fotos hochgeladen", ergebnis["nach_upload"])
        self.assertTrue(ergebnis["nach_upload"]["kasten"])
        self.assertEqual(ergebnis["nach_upload"]["liste"], 0)
        self.assertEqual(ergebnis["puffer_danach"], 0, "Puffer leer nach erfolgreichem Upload")
        self.assertEqual(ergebnis["zeile_danach"], 0)
        self.assertEqual(sorted((d.dateiname, d.ordner, d.hochgeladen_von) for d in self.dateien(self.vorgang.id)),
                         [("o1.jpg", ordner[1], self.ad.id), ("o2.jpg", ordner[1], self.ad.id)])
        self.leeren(self.vorgang.id)

    def test_auswaehlen_und_mehrfach_loeschen(self):
        """Kontrollwert: Ordner mit vier Fotos (zwei eigene, zwei vom Innendienst), Rolle Außendienst:
        „Auswählen“ zeigt zwei Kästchen, „2 Fotos löschen“ nach Abfrage → zwei Kacheln weg, zwei bleiben."""
        self.leeren(self.vorgang.id)
        eigene = [self.datei_anlegen(self.vorgang.id, f"eig{i}.jpg", "Zählerschrank", self.ad) for i in (1, 2)]
        fremde = [self.datei_anlegen(self.vorgang.id, f"id{i}.jpg", "Zählerschrank", self.innen) for i in (1, 2)]
        pfade_eigene = [config.DATA_ORDNER / d.pfad for d in eigene]
        fremde_ids = sorted(d.id for d in fremde)
        ergebnis = {}

        async def schritte(oeffnen, js, warten):
            await oeffnen(f"/vorgaenge/{self.vorgang.id}", cookie_id=self.ad.id)
            await js(self.PUFFER_LEEREN)
            d = "document.querySelector('details.pj-gal-ordner[data-ordner=\"Zählerschrank\"]')"
            await js(f"{d}.open = true")
            ergebnis["vorher"] = await js(f"{d}.querySelectorAll('figure[data-datei]').length")
            ergebnis["kaesten_versteckt"] = await js(f"{d}.querySelectorAll('.gal38-kasten[hidden]').length")
            await js(f"{d}.querySelector('.gal38-auswaehlen').click()")
            ergebnis["kaesten_sichtbar"] = await js(f"{d}.querySelectorAll('.gal38-kasten:not([hidden])').length")
            ergebnis["leiste"] = await js(f"!{d}.querySelector('.gal38-auswahl-leiste').hidden")
            ergebnis["knopf_vorher"] = await js(f"{d}.querySelector('.gal38-loeschen').textContent + '|' + {d}.querySelector('.gal38-loeschen').disabled")
            await js(f"{d}.querySelector('.gal38-alle').click()")
            ergebnis["zahl"] = await js(f"{d}.querySelector('.gal38-auswahl-zahl').textContent")
            ergebnis["knopf"] = await js(f"{d}.querySelector('.gal38-loeschen').textContent")
            ergebnis["frage"] = await js(
                "(function () { window._frage = ''; window.confirm = function (t) { window._frage = t; return true; }; return 1; })()")
            await js(f"{d}.querySelector('.gal38-loeschen').click()")
            await warten(2.0)
            ergebnis["frage_text"] = await js("window._frage")
            ergebnis["nachher"] = await js(f"{d}.querySelectorAll('figure[data-datei]').length")
            ergebnis["uebrig"] = await js(
                f"Array.prototype.map.call({d}.querySelectorAll('figure[data-datei]'), function (f) {{ return f.getAttribute('data-name'); }})")
            ergebnis["zaehler"] = await js(f"{d}.querySelector('summary .n').textContent")
            ergebnis["modus_aus"] = await js(f"{d}.querySelector('.gal38-auswahl-leiste').hidden")
            ergebnis["auswaehlen"] = await js(f"{d}.querySelector('.gal38-auswaehlen').hidden")
            ergebnis["url"] = await js("location.pathname + location.search")

        fehler = self._lauf(schritte)
        self.assertEqual(fehler, [], fehler)
        self.assertEqual(ergebnis["vorher"], 4)
        self.assertEqual(ergebnis["kaesten_versteckt"], 2)
        self.assertEqual(ergebnis["kaesten_sichtbar"], 2, ergebnis)
        self.assertTrue(ergebnis["leiste"])
        self.assertEqual(ergebnis["knopf_vorher"], "0 Fotos löschen|true")
        self.assertEqual(ergebnis["zahl"], "2 ausgewählt")
        self.assertEqual(ergebnis["knopf"], "2 Fotos löschen")
        self.assertEqual(ergebnis["frage_text"], "2 Fotos endgültig löschen? Das lässt sich nicht rückgängig machen.")
        self.assertEqual(ergebnis["nachher"], 2)
        self.assertEqual(sorted(ergebnis["uebrig"]), ["id1.jpg", "id2.jpg"])
        self.assertEqual(ergebnis["zaehler"], "2")
        self.assertTrue(ergebnis["modus_aus"])
        self.assertTrue(ergebnis["auswaehlen"], "ohne löschbare Dateien kein „Auswählen“ mehr")
        self.assertEqual(ergebnis["url"], f"/vorgaenge/{self.vorgang.id}")
        self.assertEqual(sorted(d.id for d in self.dateien(self.vorgang.id)), fremde_ids)
        self.assertFalse(any(p.exists() for p in pfade_eigene))
        self.assertTrue(any(n.startswith("Galerie: 2 Fotos gelöscht (Ordner Zählerschrank)") for n in self.notizen(self.vorgang.id)))
        self.leeren(self.vorgang.id)


if __name__ == "__main__":
    unittest.main()
