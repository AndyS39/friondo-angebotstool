# v31 (PLAN_LEAD_V5 Phasen 153/154/156/157/158, Agent AT): Ausführungsort über
# objekte.ausfuehrungsort (PDF, Lieferschein, BzA, Heizreport, Projektanlage), Erfassung
# aus einem Objekt, Vorgangsakte (Objekt-Gruppen, Archiv-Banner, Verlauf), vorgang_verlauf,
# Sparten MS/WA/DMS, Benutzerverwaltung (Leadmanager, Abwesenheiten, kein Samstag) und
# Objekt-Geocoding. Testdaten tragen das Präfix „V31AT“ und werden aufgeräumt; kein Netz.
import io
import json
import re
import shutil
import sys
import tempfile
import types
import unittest
import warnings
from datetime import date, datetime, timedelta
from pathlib import Path

warnings.filterwarnings("ignore")

import pypdf
from fastapi.testclient import TestClient

from app import (abwesenheiten, angebot_aufbau, anschriften, bza_datenblatt, geocoding,
                 heizreport_api, lieferschein_pdf, notizen, objekte, pdf_export,
                 sparten, vorgang_verlauf)
from app import auth
from app import projektierung as kern
from app.db import SessionLocal, init_db
from app.main import app
from app.models import (Angebot, AngebotsPosition, Aufgabe, AufgabenpaketInstanz, Benutzer,
                        BenutzerAbwesenheit, Erfassung, Gewerk, KommunikationLog, Kunde,
                        LeadAktivitaet, Projekt, ProjektDokument, ProjektTermin, ProjektVerlauf,
                        Vorgang, VorgangNotizGelesen, VorgangObjekt, VorgangsNotiz, AdProfil)

TEST_EMAIL = "v31at-schliwa@test.local"
PRAEFIX = "V31AT "
OBJEKT2 = {"strasse": "Musterweg 7", "plz": "47051", "ort": "Duisburg"}
KONTROLLE = Path("diagnose/v31/pdf_kontrolle_AT.pdf")


def pdf_text(pfad_oder_bytes) -> str:
    daten = pfad_oder_bytes if isinstance(pfad_oder_bytes, bytes) else Path(pfad_oder_bytes).read_bytes()
    text = "\n".join(p.extract_text() for p in pypdf.PdfReader(io.BytesIO(daten)).pages)
    return " ".join(text.split())


def pdf_normalisiert(daten: bytes) -> bytes:
    daten = re.sub(rb"/CreationDate\s*\([^)]*\)", b"", daten)
    daten = re.sub(rb"/ModDate\s*\([^)]*\)", b"", daten)
    daten = re.sub(rb"/ID\s*\[[^\]]*\]", b"", daten)
    return daten


def aufraeumen(s):
    # Verwaiste Objekte (Vorgang von Alt-Tests ohne Objekte gelöscht) entfernen – sonst
    # erbt ein neuer Vorgang mit wiederverwendeter ID fremde Objekte
    from sqlalchemy import text as _sql
    s.execute(_sql("DELETE FROM vorgang_objekte WHERE vorgang_id NOT IN (SELECT id FROM vorgaenge)"))
    for k in s.query(Kunde).filter(Kunde.email == TEST_EMAIL):
        vorgaenge = s.query(Vorgang).filter(Vorgang.kunde_id == k.id).all()
        for v in vorgaenge:
            for projekt in s.query(Projekt).filter(Projekt.vorgang_id == v.id):
                ordner = kern.projekt_ordner(projekt)
                if ordner.exists() and ordner.is_relative_to(kern.PROJEKTE_ORDNER):
                    shutil.rmtree(ordner, ignore_errors=True)
                gewerk_ids = [g.id for g in s.query(Gewerk).filter(Gewerk.projekt_id == projekt.id)]
                s.query(Aufgabe).filter(Aufgabe.projekt_id == projekt.id).delete()
                if gewerk_ids:
                    # Paket-Instanzen mit löschen – sonst blockiert ein wiederverwendeter
                    # Gewerk-Schlüssel die Paketaktivierung („bereits aktiv“)
                    (s.query(AufgabenpaketInstanz)
                     .filter(AufgabenpaketInstanz.gewerk_id.in_(gewerk_ids))
                     .delete(synchronize_session=False))
                    (s.query(ProjektTermin).filter(ProjektTermin.projekt_id == projekt.id)
                     .delete(synchronize_session=False))
                    (s.query(ProjektDokument).filter(ProjektDokument.projekt_id == projekt.id)
                     .delete(synchronize_session=False))
                s.query(ProjektVerlauf).filter(ProjektVerlauf.projekt_id == projekt.id).delete()
                s.query(Gewerk).filter(Gewerk.projekt_id == projekt.id).delete()
                s.delete(projekt)
            for modell in (VorgangObjekt, VorgangsNotiz, LeadAktivitaet, KommunikationLog,
                           VorgangNotizGelesen):
                s.query(modell).filter(modell.vorgang_id == v.id).delete()
        for a in s.query(Angebot).filter(Angebot.kunde_id == k.id):
            # erzeugte PDFs der Testangebote (Angebots-PDF, Lieferschein) mit entfernen
            (pdf_export.config.ANGEBOTE_PDF_ORDNER / f"{a.nummer}.pdf").unlink(missing_ok=True)
            (pdf_export.config.ANGEBOTE_PDF_ORDNER / "lieferscheine"
             / f"LS-{a.nummer}.pdf").unlink(missing_ok=True)
            s.delete(a)
        s.query(Erfassung).filter(Erfassung.kunde_id == k.id).delete()
        for v in vorgaenge:
            s.delete(v)
        s.delete(k)
    for b in s.query(Benutzer).filter(Benutzer.name.like(f"{PRAEFIX}%")):
        s.query(BenutzerAbwesenheit).filter(BenutzerAbwesenheit.benutzer_id == b.id).delete()
        s.query(AdProfil).filter(AdProfil.benutzer_id == b.id).delete()
        s.delete(b)
    s.commit()


class Basis(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        init_db()
        cls.s = SessionLocal()
        aufraeumen(cls.s)
        cls.client = TestClient(app)
        cls.client.cookies.set(auth.COOKIE_NAME, auth.cookie_wert(1))
        cls.kunde = Kunde(anrede="Herr", vorname="Max", nachname="V31AT Schliwa",
                          strasse="Im Knick 36", plz="47269", ort="Duisburg", email=TEST_EMAIL,
                          telefon="0203 123456", objektart="EFH", interesse="WP")
        cls.s.add(cls.kunde)
        cls.s.flush()
        cls.vorgang = Vorgang(kunde_id=cls.kunde.id, lead_phase="neu")
        cls.s.add(cls.vorgang)
        cls.s.flush()
        cls.haupt = objekte.hauptobjekt(cls.s, cls.vorgang.id, anlegen=True, kunde=cls.kunde)
        cls.objekt2 = objekte.objekt_anlegen(
            cls.s, cls.vorgang, strasse=OBJEKT2["strasse"], plz=OBJEKT2["plz"], ort=OBJEKT2["ort"],
            bezeichnung="Objekt 2", objektart="MFH", parteien=4, interessen=["PV", "WP"])
        cls.s.commit()

    @classmethod
    def tearDownClass(cls):
        aufraeumen(cls.s)
        cls.s.close()

    def _angebot(self, objekt=None, sparte="WP", status="Entwurf", extern=False):
        s = self.s
        erfassung = None
        if objekt is not None:
            erfassung = Erfassung(kunde_id=self.kunde.id, benutzer_id=1, sparte=sparte,
                                  konfigurator_typ=sparte, vorgang_id=self.vorgang.id,
                                  objekt_id=objekt.id, status="Neu",
                                  antworten_json=json.dumps({"O01": "MFH", "O03": "4", "A01": "Öl",
                                                             "A02": 1990, "O02": 1965}))
            s.add(erfassung)
            s.flush()
        angebot = angebot_aufbau.angebot_anlegen(s, self.kunde.id, sparte=sparte,
                                                 erfassung=erfassung)
        angebot.vorgang_id = self.vorgang.id
        angebot.status = status
        angebot.extern = extern
        if erfassung is not None:
            erfassung.angebot_id = angebot.id
        if not extern:
            angebot.positionen.append(AngebotsPosition(
                sort=1, block_nr=1, pos_nr="001", bezeichnung="Wärmepumpe Testgerät",
                beschreibung="Testposition v31", menge=1, einheit="Stk",
                e_preis_cent=2382353, ek_cent=1500000))
        s.commit()
        return angebot


# --- (a) Migration / Hauptobjekt-Sync ---------------------------------------------------
class MigrationUndSync(Basis):
    def test_migration_legt_je_vorgang_ein_hauptobjekt_an_und_ist_idempotent(self):
        s = self.s
        vorgang = Vorgang(kunde_id=self.kunde.id, lead_phase="neu")
        s.add(vorgang)
        s.flush()
        # Schutz gegen verwaiste Objekte eines früher gelöschten Vorgangs mit gleicher ID
        # (Alt-Tests löschen Vorgänge ohne ihre Objekte; SQLite vergibt IDs neu)
        s.query(VorgangObjekt).filter(VorgangObjekt.vorgang_id == vorgang.id).delete()
        meldungen = objekte.migration_v31_objekte(s)
        self.assertTrue(any("Hauptobjekt" in m for m in meldungen))
        haupt = objekte.hauptobjekt(s, vorgang.id)
        self.assertIsNotNone(haupt)
        self.assertEqual((haupt.strasse, haupt.plz, haupt.ort), ("Im Knick 36", "47269", "Duisburg"))
        self.assertEqual(haupt.reihenfolge, 1)
        self.assertEqual(objekte.migration_v31_objekte(s), [])   # zweiter Lauf: nichts
        s.commit()

    def test_hauptobjekt_sync_in_beide_richtungen(self):
        s = self.s
        kunde = s.get(Kunde, self.kunde.id)
        haupt = objekte.hauptobjekt(s, self.vorgang.id)
        haupt.strasse = "Im Knick 36a"
        objekte.hauptobjekt_sync(s, haupt)
        self.assertEqual(kunde.strasse, "Im Knick 36a")
        kunde.ort = "Duisburg-Süd"
        objekte.hauptobjekt_sync(s, kunde)
        self.assertEqual(objekte.hauptobjekt(s, self.vorgang.id).ort, "Duisburg-Süd")
        haupt.strasse, haupt.ort = "Im Knick 36", "Duisburg"
        objekte.hauptobjekt_sync(s, haupt)   # zurück auf den Ausgangsstand (Hauptobjekt → Kunde)
        s.commit()
        self.assertEqual(kunde.strasse, "Im Knick 36")
        self.assertEqual(objekte.hauptobjekt(s, self.vorgang.id).ort, "Duisburg")


# --- Ausführungsort (Einfügung Phase 153) ---------------------------------------------
class Ausfuehrungsort(Basis):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.angebot2 = cls._angebot(cls, cls.objekt2)
        cls.angebot1 = cls._angebot(cls, cls.haupt)

    def test_anschriften_ausfuehrungsort_fuer(self):
        ort2 = anschriften.ausfuehrungsort_fuer(self.s, angebot=self.angebot2, kunde=self.kunde)
        self.assertEqual((ort2["strasse"], ort2["plz"], ort2["ort"]),
                         (OBJEKT2["strasse"], OBJEKT2["plz"], OBJEKT2["ort"]))
        self.assertFalse(ort2["haupt"])
        self.assertTrue(ort2["mehrere_objekte"])
        self.assertEqual(ort2["objekt_id"], self.objekt2.id)
        ort1 = anschriften.ausfuehrungsort_fuer(self.s, angebot=self.angebot1, kunde=self.kunde)
        self.assertEqual(ort1["strasse"], "Im Knick 36")
        self.assertTrue(ort1["haupt"])
        # ohne Sitzung wie bisher die Kundenadresse
        self.assertEqual(anschriften.ausfuehrungsort(self.kunde)["strasse"], "Im Knick 36")
        # Empfänger bleibt der Kunde, die Ausführungsort-Zeile wird ausgewiesen
        zeilen, abweichend = anschriften.empfaenger(self.angebot2, self.kunde, ort2)
        self.assertTrue(abweichend)
        self.assertIn("Im Knick 36", zeilen)
        self.assertEqual(anschriften.lieferzeile(self.angebot2, self.kunde, ort2), "")
        lieferung = anschriften.lieferung(self.angebot2, self.kunde, ort2)
        self.assertEqual(lieferung["strasse"], OBJEKT2["strasse"])

    def test_angebots_pdf_objekt2_zeigt_objektadresse(self):
        pfad = pdf_export.pdf_fuer_angebot(self.s, self.angebot2)
        text = pdf_text(pfad)
        self.assertIn("Ausführungsort: Musterweg 7, 47051 Duisburg", text)
        self.assertIn("Im Knick 36", text)   # Empfänger = Kunde
        pfad1 = pdf_export.pdf_fuer_angebot(self.s, self.angebot1)
        self.assertNotIn("Ausführungsort:", pdf_text(pfad1))
        self.assertNotIn("Musterweg", pdf_text(pfad1))
        Path(pfad).unlink(missing_ok=True)
        Path(pfad1).unlink(missing_ok=True)

    def test_lieferschein_objekt2(self):
        self.angebot2.status = "Angenommen"
        self.s.commit()
        r = self.client.get(f"/angebote/{self.angebot2.id}/lieferschein.pdf")
        self.assertEqual(r.status_code, 200)
        text = pdf_text(r.content)
        self.assertIn("Ausführungsort: Musterweg 7, 47051 Duisburg", text)
        self.assertNotIn("Lieferanschrift:", text)   # Lieferung = Ausführungsort (Objekt)
        self.assertIn("Musterweg 7", text.split("L I E F E R S C H E I N")[0])   # Empfängerblock
        self.angebot2.status = "Entwurf"
        self.s.commit()
        Path(lieferschein_pdf.config.ANGEBOTE_PDF_ORDNER / "lieferscheine"
             / f"LS-{self.angebot2.nummer}.pdf").unlink(missing_ok=True)

    def test_bza_abschnitt1_objekt2(self):
        blatt = bza_datenblatt.erstellen(self.s, self.angebot2)
        felder = {f.schluessel: f.wert for f in blatt.abschnitte[0][1]}
        self.assertEqual(felder["strasse"], "Musterweg")
        self.assertEqual(felder["hausnummer"], "7")
        self.assertEqual(felder["plz"], "47051")
        self.assertEqual(felder["ort"], "Duisburg")
        blatt1 = bza_datenblatt.erstellen(self.s, self.angebot1)
        felder1 = {f.schluessel: f.wert for f in blatt1.abschnitte[0][1]}
        self.assertEqual(felder1["strasse"], "Im Knick")

    def test_projektanlage_heizreport_und_gewerk_objekt(self):
        s = self.s
        self.angebot2.status = "Angenommen"
        s.commit()
        projekt = kern.projekt_anlegen(s, self.angebot2, projektleiter_id=1)
        self.assertEqual((projekt.ausfuehrung_strasse, projekt.ausfuehrung_plz, projekt.ausfuehrung_ort),
                         (OBJEKT2["strasse"], OBJEKT2["plz"], OBJEKT2["ort"]))
        gewerk = kern.gewerk_anlegen(s, projekt, self.angebot2, "WP", benachrichtigen_an=False)
        s.commit()
        self.assertEqual(gewerk.objekt_id, self.objekt2.id)
        ort = kern.projekt_ausfuehrungsort(s, projekt, gewerk)
        self.assertEqual(ort["einzeilig"], "Musterweg 7, 47051 Duisburg")
        self.assertEqual(ort["zeile"], "Musterweg 7 47051 Duisburg")
        daten = heizreport_api.projektdaten_v2(s, gewerk)["projectData"]
        self.assertEqual(daten["projektPostleitzahl"], "47051")
        self.assertEqual(daten["strasse"], "Musterweg")
        self.assertEqual(daten["hausnummer"], "7")
        self.assertEqual(daten["ort"], "Duisburg")
        # BzA am Gewerk nimmt die Projektadresse
        blatt = bza_datenblatt.erstellen(s, self.angebot2, gewerk=gewerk)
        felder = {f.schluessel: f.wert for f in blatt.abschnitte[0][1]}
        self.assertEqual(felder["plz"], "47051")
        # Projekt ohne gespeicherte Adresse fällt auf das Objekt des Gewerks zurück
        projekt.ausfuehrung_strasse = projekt.ausfuehrung_plz = projekt.ausfuehrung_ort = ""
        s.flush()
        self.assertEqual(kern.projekt_ausfuehrungsort(s, projekt, gewerk)["strasse"], "Musterweg 7")
        projekt.ausfuehrung_strasse, projekt.ausfuehrung_plz, projekt.ausfuehrung_ort = (
            OBJEKT2["strasse"], OBJEKT2["plz"], OBJEKT2["ort"])
        self.angebot2.status = "Entwurf"
        s.commit()

    def test_projekt_dialog_belegt_objektadresse_vor(self):
        self.angebot2.status = "Angenommen"
        self.s.commit()
        try:
            r = self.client.get(f"/projektierung/angebot/{self.angebot2.id}/projekt")
            self.assertEqual(r.status_code, 200)
            self.assertIn('value="Musterweg 7"', r.text)
            self.assertIn('value="47051"', r.text)
            self.assertIn("Objekt des Angebots", r.text)
        finally:
            self.angebot2.status = "Entwurf"
            self.s.commit()

    def test_version_und_duplikat_behalten_objekt(self):
        version = angebot_aufbau.version_erzeugen(self.s, self.angebot2)
        self.s.commit()
        self.assertEqual(version.objekt_id, self.objekt2.id)
        r = self.client.post(f"/angebote/{version.id}/duplizieren", follow_redirects=False)
        self.assertEqual(r.status_code, 303)
        kopie_id = int(r.headers["location"].split("/angebote/")[1].split("?")[0])
        self.assertEqual(self.s.get(Angebot, kopie_id).objekt_id, self.objekt2.id)
        self.angebot2.status = "Entwurf"
        self.s.commit()

    def test_ein_objekt_angebot_pdf_byteidentisch_zur_kontrolle(self):
        sidecar = KONTROLLE.with_suffix(".txt")
        if not KONTROLLE.exists() or not sidecar.exists():
            self.skipTest("kein Kontroll-PDF diagnose/v31/pdf_kontrolle_AT.pdf")
        angebot_id, nummer, _datum = sidecar.read_text(encoding="utf-8").strip().split(";")
        angebot = self.s.get(Angebot, int(angebot_id))
        if angebot is None or angebot.nummer != nummer:
            self.skipTest("Kontrollangebot liegt in dieser Datenbank nicht vor")
        sys.path.insert(0, str(Path("diagnose/v31").resolve()))
        try:
            import pdf_kontrolle_AT
        finally:
            sys.path.pop(0)
        with tempfile.TemporaryDirectory() as ordner:
            neu = pdf_kontrolle_AT.erzeugen(self.s, angebot, Path(ordner) / "neu.pdf")
        self.assertEqual(pdf_normalisiert(KONTROLLE.read_bytes()), pdf_normalisiert(neu),
                         "Angebots-PDF eines Ein-Objekt-Vorgangs hat sich verändert")


# --- Erfassung übergibt das Objekt (Phase 153) / Freitext-Sparten (Phase 157) ---------
class ErfassungAusObjekt(Basis):
    def test_sparten_seite_zeigt_objekt_und_objektwahl(self):
        r = self.client.get(f"/erfassung/sparten?kunde_id={self.kunde.id}&objekt_id={self.objekt2.id}")
        self.assertEqual(r.status_code, 200)
        self.assertIn("Objekt 2", r.text)
        self.assertIn("Musterweg 7", r.text)
        self.assertIn(f'name="objekt_id" value="{self.objekt2.id}"', r.text)
        self.assertRegex(r.text, r'name="sparte_PV"\s+checked')   # Interessen des Objekts
        self.assertIn("MS – Mieterstrom", r.text)
        r = self.client.get(f"/erfassung/sparten?kunde_id={self.kunde.id}")
        self.assertIn("Welches Objekt?", r.text)
        self.assertIn('type="radio" name="objekt_id"', r.text)

    def test_erfassung_traegt_objekt_und_objektart_aus_dem_objekt(self):
        r = self.client.post("/erfassung/sparten-start",
                             data={"kunde_id": str(self.kunde.id), "objekt_id": str(self.objekt2.id),
                                   "sparte_WP": "on"}, follow_redirects=False)
        self.assertEqual(r.status_code, 303)
        erf_id = int(r.headers["location"].split("/erfassung/")[1].split("/")[0])
        erfassung = self.s.get(Erfassung, erf_id)
        self.s.refresh(erfassung)
        self.assertEqual(erfassung.objekt_id, self.objekt2.id)
        antworten = json.loads(erfassung.antworten_json)
        self.assertEqual(antworten["O01"], "MFH")
        self.assertEqual(antworten["O03"], "4")
        self.assertIn("Objekt", json.loads(erfassung.vorbelegt_json)["O01"])
        # Ausführungsort der Erfassung = Objektadresse
        ort = anschriften.ausfuehrungsort_fuer(self.s, erfassung=erfassung)
        self.assertEqual(ort["strasse"], "Musterweg 7")
        # ohne Objekt: Hauptobjekt (Kundenadresse, EFH)
        r = self.client.post("/erfassung/sparten-start",
                             data={"kunde_id": str(self.kunde.id), "sparte_WP": "on"},
                             follow_redirects=False)
        erf2 = self.s.get(Erfassung, int(r.headers["location"].split("/erfassung/")[1].split("/")[0]))
        self.s.refresh(erf2)
        self.assertEqual(erf2.objekt_id, self.haupt.id)
        self.assertEqual(json.loads(erf2.antworten_json)["O01"], "EFH")

    def test_ms_erfassung_startet_als_freitext(self):
        self.assertTrue(sparten.ist_freitext_sparte("MS"))
        r = self.client.post("/erfassung/sparten-start",
                             data={"kunde_id": str(self.kunde.id), "sparte_MS": "on"},
                             follow_redirects=False)
        self.assertEqual(r.status_code, 303)
        self.assertTrue(r.headers["location"].endswith("/freitext"), r.headers["location"])
        erf_id = int(r.headers["location"].split("/erfassung/")[1].split("/")[0])
        erfassung = self.s.get(Erfassung, erf_id)
        self.s.refresh(erfassung)
        self.assertEqual(erfassung.sparte, "MS")
        r = self.client.get(f"/erfassung/{erf_id}/freitext")
        self.assertEqual(r.status_code, 200)

    def test_leads_erfassen_reicht_objekt_durch(self):
        from app.routers import leads as leads_router
        import inspect
        self.assertIn("objekt_id", inspect.signature(leads_router.erfassen).parameters)


# --- Vorgangsakte: Objekt-Gruppen, Archiv-Banner, Verlauf (Phasen 153/154/158) ----------
class Vorgangsakte(Basis):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.angebot2 = cls._angebot(cls, cls.objekt2)
        cls.angebot1 = cls._angebot(cls, cls.haupt)

    def test_objekt_gruppen(self):
        gruppen = vorgang_verlauf.objekt_gruppen(self.s, self.vorgang)
        self.assertEqual(len(gruppen), 2)
        self.assertTrue(gruppen[0]["haupt"])
        self.assertEqual(gruppen[1]["ueberschrift"], "Objekt 2: Musterweg 7, 47051 Duisburg")
        self.assertIn(self.angebot2.id, [a.id for a in gruppen[1]["angebote"]])
        self.assertIn(self.angebot1.id, [a.id for a in gruppen[0]["angebote"]])
        self.assertTrue(all(g["mehrere"] for g in gruppen))
        self.assertEqual(len(gruppen[1]["erfassungen"]), 1)

    def test_akte_gruppiert_je_objekt_und_zeigt_archiv_banner(self):
        r = self.client.get(f"/vorgaenge/{self.vorgang.id}")
        self.assertEqual(r.status_code, 200)
        self.assertIn("Angebote und Erfassungen je Objekt", r.text)
        self.assertIn("Objekt 2: Musterweg 7, 47051 Duisburg", r.text)
        self.assertIn(f"objekt_id={self.objekt2.id}", r.text)   # Erfassung für dieses Objekt
        self.assertNotIn("Im Lead-Management archiviert", r.text)
        vorgang = self.s.get(Vorgang, self.vorgang.id)
        vorgang.archiviert_am = datetime(2026, 10, 13, 9, 30)
        vorgang.archiviert_von = 1
        self.s.commit()
        r = self.client.get(f"/vorgaenge/{self.vorgang.id}")
        self.assertIn("Im Lead-Management archiviert am 13.10.2026 09:30", r.text)
        self.assertIn("Wiederherstellen", r.text)
        # Angebotsliste und Erfassungsliste zeigen den archivierten Vorgang unverändert
        r = self.client.get("/angebote?status=Entwurf")
        self.assertIn(self.angebot2.nummer, r.text)
        r = self.client.get("/erfassungen?status=Neu")
        self.assertIn("V31AT Schliwa", r.text)
        vorgang.archiviert_am = None
        vorgang.archiviert_von = None
        self.s.commit()

    def test_wiederherstellen_ueber_lead_archiv_vertrag(self):
        vorgang = self.s.get(Vorgang, self.vorgang.id)
        vorgang.archiviert_am = datetime.now()
        vorgang.archiviert_von = 1
        self.s.commit()
        aufrufe = []

        def wiederherstellen(session, v, benutzer):
            aufrufe.append((v.id, benutzer.id))
            v.archiviert_am = None
            v.archiviert_von = None
            return True, ""

        import app as app_paket
        fake = types.ModuleType("app.lead_archiv")
        fake.wiederherstellen = wiederherstellen
        echtes = sys.modules.get("app.lead_archiv")
        echtes_attr = getattr(app_paket, "lead_archiv", None)

        def einhaengen():
            sys.modules["app.lead_archiv"] = fake
            app_paket.lead_archiv = fake

        def aushaengen():
            if echtes is not None:
                sys.modules["app.lead_archiv"] = echtes
            else:
                sys.modules.pop("app.lead_archiv", None)
            if echtes_attr is not None:
                app_paket.lead_archiv = echtes_attr
            elif hasattr(app_paket, "lead_archiv"):
                delattr(app_paket, "lead_archiv")

        einhaengen()
        try:
            r = self.client.post(f"/vorgaenge/{self.vorgang.id}/archiv-wiederherstellen",
                                 follow_redirects=False)
        finally:
            aushaengen()
        self.assertEqual(r.status_code, 303)
        self.assertIn("wiederhergestellt", r.headers["location"])
        self.assertEqual(aufrufe, [(self.vorgang.id, 1)])
        self.s.refresh(vorgang)
        self.assertIsNone(vorgang.archiviert_am)
        # Sperre durch den Vertrag (z. B. aktiver Termin) → Meldung, Kennzeichen bleibt
        vorgang.archiviert_am = datetime.now()
        self.s.commit()
        fake.wiederherstellen = lambda session, v, benutzer: (False, "aktiver Termin")
        einhaengen()
        try:
            r = self.client.post(f"/vorgaenge/{self.vorgang.id}/archiv-wiederherstellen",
                                 follow_redirects=False)
        finally:
            aushaengen()
        self.assertIn("aktiver+Termin", r.headers["location"])
        self.s.refresh(vorgang)
        self.assertIsNotNone(vorgang.archiviert_am)
        vorgang.archiviert_am = None
        self.s.commit()

    def test_wiederherstellen_rueckfall_ohne_modul(self):
        vorgang = self.s.get(Vorgang, self.vorgang.id)
        vorgang.archiviert_am = datetime.now()
        vorgang.archiviert_von = 1
        self.s.flush()
        import app as app_paket
        from app.routers import vorgaenge as vorgaenge_router
        echtes = sys.modules.get("app.lead_archiv")
        echtes_attr = getattr(app_paket, "lead_archiv", None)
        sys.modules["app.lead_archiv"] = None   # erzwingt ImportError
        if echtes_attr is not None:
            delattr(app_paket, "lead_archiv")
        try:
            ok, grund = vorgaenge_router.archiv_wiederherstellen_ausfuehren(
                self.s, vorgang, self.s.get(Benutzer, 1))
        finally:
            if echtes is not None:
                sys.modules["app.lead_archiv"] = echtes
            else:
                sys.modules.pop("app.lead_archiv", None)
            if echtes_attr is not None:
                app_paket.lead_archiv = echtes_attr
        self.assertTrue(ok)
        self.assertIsNone(vorgang.archiviert_am)
        self.assertTrue(self.s.query(LeadAktivitaet)
                        .filter(LeadAktivitaet.vorgang_id == vorgang.id,
                                LeadAktivitaet.text.like("%wiederhergestellt%")).count())
        self.s.commit()

    def test_wiederherstellen_rechte(self):
        ad = Benutzer(name=f"{PRAEFIX}AD", rolle="aussendienst", email="v31at-ad@test.local")
        auth.pin_setzen(ad, "4711")
        self.s.add(ad)
        self.s.commit()
        client = TestClient(app)
        client.cookies.set(auth.COOKIE_NAME, auth.cookie_wert(ad.id))
        r = client.post(f"/vorgaenge/{self.vorgang.id}/archiv-wiederherstellen", follow_redirects=False)
        self.assertEqual(r.status_code, 303)
        self.assertNotIn("wiederhergestellt", r.headers["location"])


class Verlauf(Basis):
    def test_eintraege_aus_allen_quellen(self):
        s = self.s
        benutzer = s.get(Benutzer, 1)
        n_projekt = notizen.notiz_anlegen(s, self.vorgang.id, benutzer, "Kunde wünscht Rückruf",
                                          herkunft="projektierung")
        n_lead = notizen.notiz_anlegen(s, self.vorgang.id, benutzer, "Notiz aus der Kartei",
                                       herkunft="lead")
        s.add(LeadAktivitaet(vorgang_id=self.vorgang.id, typ="anruf", ergebnis="erreicht",
                             text="Kunde erreicht, Termin gewünscht", benutzer_id=1,
                             zeitpunkt=datetime.now() - timedelta(hours=2)))
        s.add(LeadAktivitaet(vorgang_id=self.vorgang.id, typ="status",
                             text="Status: Neu → Kontaktiert", benutzer_id=1,
                             zeitpunkt=datetime.now() - timedelta(hours=1)))
        s.add(KommunikationLog(vorgang_id=self.vorgang.id, vorlage_key="eingangsbestaetigung",
                               an=TEST_EMAIL, betreff="Ihre Anfrage", status="gesperrt",
                               geplant_am=datetime.now() - timedelta(minutes=30)))
        projekt = Projekt(nummer="PR-V31AT1", vorgang_id=self.vorgang.id, kunde_id=self.kunde.id,
                          ausfuehrung_strasse="Musterweg 7", ausfuehrung_plz="47051",
                          ausfuehrung_ort="Duisburg", status_cache="planung")
        s.add(projekt)
        s.flush()
        gewerk = Gewerk(projekt_id=projekt.id, sparte="WP", phase="planung")
        s.add(gewerk)
        s.flush()
        s.add(ProjektVerlauf(projekt_id=projekt.id, gewerk_id=gewerk.id, art="system",
                             text="Phase Feinplanung VOT → Planung", benutzer_id=1,
                             erstellt_am=datetime.now() - timedelta(minutes=10)))
        # migrierter Kommentar: gleicher Zeitpunkt + Text wie die Notiz → keine Dublette
        s.add(ProjektVerlauf(projekt_id=projekt.id, art="kommentar", text="Kunde wünscht Rückruf",
                             benutzer_id=1, erstellt_am=n_projekt.zeit))
        s.add(Aufgabe(projekt_id=projekt.id, gewerk_id=gewerk.id, titel="Heizlast prüfen",
                      status="offen", pflicht=True))
        s.commit()
        eintraege = vorgang_verlauf.eintraege(s, self.vorgang.id)
        self.assertEqual([e["zeit"] for e in eintraege], sorted(e["zeit"] for e in eintraege))
        je_art = {(e["quelle"], e["art"], e["text"]) for e in eintraege}
        self.assertIn(("projekt", "notiz", "Kunde wünscht Rückruf"), je_art)
        self.assertIn(("lead", "notiz", "Notiz aus der Kartei"), je_art)
        self.assertIn(("lead", "anruf", "Kunde erreicht, Termin gewünscht"), je_art)
        self.assertIn(("lead", "status", "Status: Neu → Kontaktiert"), je_art)
        self.assertIn(("projekt", "verlauf", "Phase Feinplanung VOT → Planung"), je_art)
        self.assertEqual(sum(1 for e in eintraege if e["text"] == "Kunde wünscht Rückruf"), 1)
        anruf = next(e for e in eintraege if e["art"] == "anruf")
        self.assertEqual(anruf["titel"], "Anruf: Erreicht")
        self.assertEqual(anruf["link"], f"/lead-management/lead/{self.vorgang.id}")
        mail = next(e for e in eintraege if e["art"] == "mail")
        self.assertIn("eingangsbestaetigung", mail["titel"])
        self.assertIn("gesperrt", mail["titel"])
        for e in eintraege:
            for schluessel in ("zeit", "quelle", "art", "text", "autor", "link"):
                self.assertIn(schluessel, e)
        # Quellenfilter und Limit
        nur_lead = vorgang_verlauf.eintraege(s, self.vorgang.id, quellen=("lead",))
        self.assertTrue(nur_lead and all(e["quelle"] == "lead" for e in nur_lead))
        self.assertEqual(len(vorgang_verlauf.eintraege(s, self.vorgang.id, limit=2)), 2)
        # Projekt-Block
        block = vorgang_verlauf.projekt_block(s, self.vorgang.id)
        self.assertEqual(block["nummer"], "PR-V31AT1")
        self.assertEqual(block["phase_text"], "WP: Planung")
        self.assertEqual(block["todos_offen"], 1)
        self.assertEqual(block["todos"][0]["titel"], "Heizlast prüfen")
        self.assertEqual(block["montagetermin_text"], "noch nicht terminiert")
        # Vorgangsakte: Notizen im Chat, Aktivitäten im Verlauf „alles“
        r = self.client.get(f"/vorgaenge/{self.vorgang.id}")
        self.assertEqual(r.status_code, 200)
        self.assertIn("nur Notizen (", r.text)
        self.assertIn('data-ziel="alles"', r.text)
        self.assertIn("Kunde wünscht Rückruf", r.text)
        self.assertIn("Notiz aus der Kartei", r.text)
        verlauf_html = r.text.split(f'id="nc-alles-{self.vorgang.id}"')[1].split(f'id="nc-{self.vorgang.id}"')[0]
        self.assertIn("Kunde erreicht, Termin gewünscht", verlauf_html)
        self.assertIn("Anruf: Erreicht", verlauf_html)
        self.assertIn("vl-quelle-projekt", verlauf_html)
        self.assertIn("Phase Feinplanung VOT → Planung", verlauf_html)
        self.assertIsNone(vorgang_verlauf.projekt_block(s, 999999999))
        self.assertIsNone(s.get(Vorgang, 999999999))
        del n_lead


# --- Sparten MS/WA/DMS in der Projektierung (Phase 157) ----------------------------------
class SpartenProjektierung(Basis):
    def test_ms_gewerk_wie_wb_ohne_sparten_pakete(self):
        from app import projektierung_logik
        self.assertIn("MS", projektierung_logik.SPARTEN)
        self.assertEqual(sparten.SPARTEN, ("WP", "PV", "KL", "WB", "GW", "MS", "WA", "DMS"))
        felder = [f for f, _ in kern.steckbrief_felder("MS")]
        self.assertIn("auftrag", felder)
        self.assertIn("besonderheiten", felder)
        angebot = self._angebot(sparte="MS", status="Angenommen", extern=True)
        angebot.extern_endbetrag_cent = 500000
        self.s.commit()
        projekt = kern.projekt_anlegen(self.s, angebot, projektleiter_id=1)
        gewerk = kern.gewerk_anlegen(self.s, projekt, angebot, "MS", benachrichtigen_an=False)
        self.s.commit()
        self.assertEqual(gewerk.sparte, "MS")
        self.assertEqual(gewerk.phase, "auftragseingang")
        logik = projektierung_logik.hole_logik(self.s)
        # wie WB: keine eigenen Sparten-Pakete, nur die ALLE-Pakete des Blatts
        # (IMMER-Regeln mit Sparte ALLE; sparten-spezifische Regeln wie planung_elektro
        # für WP/WB greifen bei MS nicht)
        self.assertTrue(all(p.sparte == "ALLE" for p in logik.immer_pakete("MS")))
        erwartet = {r.paket_key for r in logik.regeln
                    if r.bedingung.strip().upper() == "IMMER" and r.sparte == "ALLE"
                    and r.paket_key in logik.pakete and logik.pakete[r.paket_key].sparte == "ALLE"}
        self.assertEqual({p.key for p in logik.immer_pakete("MS")}, erwartet)
        self.assertTrue({p.key for p in logik.immer_pakete("MS")}
                        <= {p.key for p in logik.immer_pakete("WB")})
        aufgaben = self.s.query(Aufgabe).filter(Aufgabe.gewerk_id == gewerk.id).all()
        self.assertTrue(aufgaben)   # ALLE-Pakete aktiviert (Freitext-Auftrag, keine MS-Pakete)
        r = self.client.get(f"/projektierung/projekt/{projekt.id}")
        self.assertIn(r.status_code, (200, 303))

    def test_statistik_und_listen_kennen_neue_sparten(self):
        r = self.client.get("/statistik")
        self.assertEqual(r.status_code, 200)
        self.assertIn('value="MS"', r.text)
        r = self.client.get("/erfassungen")
        self.assertIn('value="DMS"', r.text)
        r = self.client.get("/angebote")
        self.assertEqual(r.status_code, 200)


# --- Benutzerverwaltung (Phasen 156/158) ---------------------------------------------------
class Benutzerverwaltung(Basis):
    def test_leadmanager_haekchen(self):
        r = self.client.post("/benutzer/neu", data={"name": f"{PRAEFIX}Leadmanagerin",
                                                    "rolle": "innendienst", "pin": "48153",
                                                    "leadmanager": "on"}, follow_redirects=False)
        self.assertEqual(r.status_code, 303)
        b = self.s.query(Benutzer).filter(Benutzer.name == f"{PRAEFIX}Leadmanagerin").first()
        self.assertTrue(b.leadmanager)
        r = self.client.get("/benutzer")
        self.assertIn("Leadmanager (Innendienst-Auswahl)", r.text)
        self.assertIn("ben-lm-badge", r.text)
        # Formular ohne den Block lässt das Kennzeichen stehen
        self.client.post(f"/benutzer/{b.id}/aendern", data={"name": b.name, "rolle": "innendienst",
                                                            "aktiv": "on"}, follow_redirects=False)
        self.s.refresh(b)
        self.assertTrue(b.leadmanager)
        self.client.post(f"/benutzer/{b.id}/aendern", data={"name": b.name, "rolle": "innendienst",
                                                            "aktiv": "on", "leadmanager_dabei": "1"},
                         follow_redirects=False)
        self.s.refresh(b)
        self.assertFalse(b.leadmanager)

    def test_abwesenheit_anlegen_und_beenden(self):
        ad = Benutzer(name=f"{PRAEFIX}Krank", rolle="aussendienst", email="v31at-krank@test.local")
        auth.pin_setzen(ad, "4711")
        self.s.add(ad)
        self.s.commit()
        heute = date.today()
        r = self.client.post(f"/benutzer/{ad.id}/abwesenheit",
                             data={"art": "krankheit", "von": heute.isoformat(),
                                   "bis": (heute + timedelta(days=2)).isoformat(),
                                   "bemerkung": "Grippe"}, follow_redirects=False)
        self.assertEqual(r.status_code, 303)
        eintrag = abwesenheiten.ist_abwesend(self.s, ad.id, heute + timedelta(days=1))
        self.assertIsNotNone(eintrag)
        self.assertEqual(abwesenheiten.hinweis_text(eintrag, ad.name), f"Krankheit: {ad.name}")
        r = self.client.get("/benutzer")
        self.assertIn("Abwesenheiten (Krankheit/Urlaub)", r.text)
        self.assertIn("Grippe", r.text)
        r = self.client.post(f"/benutzer/abwesenheit/{eintrag.id}/beenden",
                             data={"bis": (heute - timedelta(days=1)).isoformat()},
                             follow_redirects=False)
        self.assertEqual(r.status_code, 303)
        self.s.refresh(eintrag)
        self.assertEqual(eintrag.bis, heute - timedelta(days=1))
        self.assertIsNone(abwesenheiten.ist_abwesend(self.s, ad.id, heute))
        # Fehlerfall: Bis vor Von
        r = self.client.post(f"/benutzer/{ad.id}/abwesenheit",
                             data={"art": "urlaub", "von": heute.isoformat(),
                                   "bis": (heute - timedelta(days=3)).isoformat()},
                             follow_redirects=False)
        self.assertIn("Bis-Datum", r.headers["location"].replace("+", " "))

    def test_ad_profil_ohne_samstag(self):
        ad = Benutzer(name=f"{PRAEFIX}MoFr", rolle="aussendienst", email="v31at-mofr@test.local")
        auth.pin_setzen(ad, "4711")
        self.s.add(ad)
        self.s.commit()
        r = self.client.get(f"/benutzer/{ad.id}/ad-profil")
        self.assertEqual(r.status_code, 200)
        self.assertIn('name="fr_von"', r.text)
        self.assertNotIn('name="sa_von"', r.text)
        self.assertIn('name="kompetenz_MS"', r.text)
        r = self.client.post(f"/benutzer/{ad.id}/ad-profil",
                             data={"mo_von": "08:00", "mo_bis": "17:00", "sa_von": "09:00",
                                   "sa_bis": "12:00", "termin_dauer_min": "90", "puffer_min": "30",
                                   "max_termine_tag": "3", "kompetenz_MS": "on"},
                             follow_redirects=False)
        self.assertEqual(r.status_code, 303)
        profil = self.s.query(AdProfil).filter(AdProfil.benutzer_id == ad.id).first()
        zeiten = json.loads(profil.arbeitszeiten)
        self.assertEqual(set(zeiten), {"mo"})
        self.assertIn("MS", json.loads(profil.kompetenz_sparten))


# --- Objekt-Geocoding (Phase 153) ---------------------------------------------------------
class ObjektGeocoding(Basis):
    def test_weitere_objekte_werden_geokodiert(self):
        s = self.s
        objekt = s.get(VorgangObjekt, self.objekt2.id)
        objekt.lat = objekt.lon = None
        objekt.geocode_status = None
        s.commit()
        offen = geocoding._offene_objekte(s, 25)
        self.assertIn((self.objekt2.id, "Musterweg 7, 47051 Duisburg"), offen)
        aufrufe = []
        original = geocoding.anbieter_aufrufen
        original_profile = geocoding._offene_profile
        original_leads = geocoding._offene_leads
        original_termine = geocoding._offene_termine

        def fake_anbieter(auftrag):
            aufrufe.append(auftrag["adresse"])
            return (51.43, 6.76)

        geocoding.anbieter_aufrufen = fake_anbieter
        geocoding._offene_profile = lambda session: []
        geocoding._offene_leads = lambda session, limit: []
        geocoding._offene_termine = lambda session, limit: []
        try:
            zaehler = geocoding.hintergrund_lauf(limit=25)
        finally:
            geocoding.anbieter_aufrufen = original
            geocoding._offene_profile = original_profile
            geocoding._offene_leads = original_leads
            geocoding._offene_termine = original_termine
        self.assertIn("objekte", zaehler)
        self.assertGreaterEqual(zaehler["objekte"], 1)
        s.expire_all()
        objekt = s.get(VorgangObjekt, self.objekt2.id)
        self.assertEqual(objekt.geocode_status, "ok")
        self.assertAlmostEqual(objekt.lat, 51.43)
        self.assertNotIn((self.objekt2.id, "Musterweg 7, 47051 Duisburg"),
                         geocoding._offene_objekte(s, 25))
        # lead_adresse liefert mit objekt_id die Objektadresse
        self.assertEqual(geocoding.lead_adresse(s, self.vorgang, objekt_id=self.objekt2.id),
                         "Musterweg 7, 47051 Duisburg")
        self.assertEqual(geocoding.lead_adresse(s, self.vorgang), "Im Knick 36, 47269 Duisburg")
        # Cache-Zeile aufräumen, damit der Lauf wiederholbar bleibt
        from app.models import GeocodeCache
        s.query(GeocodeCache).filter(
            GeocodeCache.adresse_norm == geocoding.adresse_normalisieren("Musterweg 7, 47051 Duisburg")
        ).delete()
        s.commit()


if __name__ == "__main__":
    unittest.main()
