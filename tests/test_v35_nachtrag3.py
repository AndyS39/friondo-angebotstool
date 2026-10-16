# Tests v35-Nachtrag 3 (16.10.2026, PLAN_LEAD_V6_1 – Screenshot-Review Claudia Castro, Agent N6):
#  (1) Kundenkartei ohne Knopf „An TAIFUN übergeben“ und ohne Feld „TAIFUN-Kundennummer“; das Badge
#      „TAIFUN <Datum>“ bleibt – ohne Nummer, auch wenn die (ungelesene) Spalte gefüllt ist
#  (2) Übergabeliste: „Erneut übergeben“ je Zeile mit Rückfrage (Datum der letzten Übergabe, Doppelte
#      vermeiden); POST ohne bestaetigt → 409 (JSON) bzw. Rückfrage-Balken in der Liste (Formular);
#      mit bestaetigt=1 → neue Übergabe, Redirect zurück auf die Liste
#  (3) Dubletten-Hinweis ignoriert kunden.taifun_kundennr (nur TAIFUN-Angebot / Bestandsimport);
#      Terminierung mit Dublette → Zeile „übersprungen (Rückfrage)“ mit „Trotzdem übergeben“
#  (4) Kartei, Erfassungs-Sparten-Start, Prüfen-Seite und Projektakte ohne Objektfoto-Markup;
#      POST /lead-management/lead/{id}/objekt/{oid}/fotos → 404
#  (5) galerie.ordner_liste(..., vorgang=…) ohne „Objekt“-Ordner; eine Datei im Alt-Ordner „Objekt 1“
#      bleibt in galerie.uebersicht (und in der Vorgangsakte) sichtbar
#  (6) HEIC-Upload über den Galerie-Upload wird weiter JPG
#  (7) lead_kartei.feld_speichern(…, "taifun_kundennr", …) wird abgewiesen
#  (8) Bausteine/Wächter: gelöschte Dateien, No-op-Migration, Kontext ohne Knopf-Felder, Tokens
# Läuft gegen die DB-Kopie (DB_PFAD_OVERRIDE/DATA_ORDNER), nie gegen data/angebotstool.db; Testdaten
# tragen die E-Mail-Domäne „v35n3.test“ bzw. den Benutzer-Präfix „V35N3 “ und werden aufgeräumt;
# der Import-Ordner ist ein Temp-Ordner; kein Netz, kein Graph, kein Outlook.
import io
import shutil
import tempfile
import unittest
import warnings
from datetime import datetime, timedelta
from pathlib import Path
from urllib.parse import unquote_plus

warnings.filterwarnings("ignore")

from fastapi.testclient import TestClient

from app import angebot_aufbau, auth, config, lead_kartei, taifun_export
from app import galerie as galerie_modul
from app import leadmanagement as kern
from app import objekte as objekte_modul
from app import projektierung as kern_proj
from app.db import SessionLocal, init_db
from app.main import app
from app.models import (AdProfil, Angebot, AngebotsPosition, Aufgabe, AufgabenpaketInstanz,
                        Benachrichtigung, Benutzer, Erfassung, GalerieDatei, Gewerk,
                        KommunikationLog, Kunde, LeadAktivitaet, LeadParameter, LeadQuelle,
                        Projekt, ProjektTermin, ProjektVerlauf, SteckbriefWert, TaifunUebergabe,
                        TerminBesetzung, Todo, Vorgang, VorgangNotizGelesen, VorgangObjekt,
                        VorgangsNotiz, VotTermin, angebot_status_setzen)

PROJEKT = Path(__file__).resolve().parent.parent
DOMAENE = "v35n3.test"
BENUTZER_PRAEFIX = "V35N3 "
LISTE = "/lead-management/taifun-uebergaben"
PARAMETER = ("terminierung_aktiv", "mail_versand_aktiv", "taifun_export_aktiv", "taifun_import_ordner",
             "taifun_export_encoding", "pflichtfelder", "kalender_sync", "glocke_lead_arten")
PFLICHT = "anrede; nachname; telefon; strasse; plz; ort; vertriebskanal; interesse; objektart; ad_id"


def heic_bytes(groesse=(64, 48)) -> bytes:
    """HEIC-Attrappe über pillow_heif (wie der frühere Objektfoto-Test)."""
    import pillow_heif
    from PIL import Image
    pillow_heif.register_heif_opener()
    puffer = io.BytesIO()
    Image.new("RGB", groesse, (10, 200, 30)).save(puffer, format="HEIF", quality=80)
    return puffer.getvalue()


def jpg_bytes(groesse=(120, 80)) -> bytes:
    from PIL import Image
    puffer = io.BytesIO()
    Image.new("RGB", groesse, (200, 40, 40)).save(puffer, format="JPEG")
    return puffer.getvalue()


def meldung_aus(r) -> str:
    ort = r.headers.get("location", "")
    return unquote_plus(ort.split("meldung=", 1)[1].split("&", 1)[0]) if "meldung=" in ort else ""


def tag(seite: str, element_id: str) -> str:
    """Das vollständige öffnende Tag des Elements mit dieser id."""
    vorher, nachher = seite.split(f'id="{element_id}"', 1)
    return "<" + vorher.rsplit("<", 1)[1] + f'id="{element_id}"' + nachher.split(">", 1)[0] + ">"


def client_fuer(benutzer_id: int) -> TestClient:
    c = TestClient(app, follow_redirects=False)
    c.cookies.set(auth.COOKIE_NAME, auth.cookie_wert(benutzer_id))
    return c


def _vorgangsordner_entfernen(vorgang_id: int) -> None:
    ordner = config.DATA_ORDNER / "vorgaenge" / str(vorgang_id)
    if ordner.exists():
        shutil.rmtree(ordner, ignore_errors=True)


def aufraeumen(s) -> None:
    s.rollback()
    for k in s.query(Kunde).filter(Kunde.email.like(f"%@{DOMAENE}")):
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
            s.query(LeadAktivitaet).filter_by(vorgang_id=v.id).delete()
            s.query(KommunikationLog).filter_by(vorgang_id=v.id).delete()
            s.query(VotTermin).filter_by(vorgang_id=v.id).delete()
            s.query(VorgangsNotiz).filter_by(vorgang_id=v.id).delete()
            s.query(VorgangNotizGelesen).filter_by(vorgang_id=v.id).delete()
            s.query(VorgangObjekt).filter_by(vorgang_id=v.id).delete()
            s.query(Todo).filter_by(vorgang_id=v.id).delete()
            s.query(TaifunUebergabe).filter_by(vorgang_id=v.id).delete()
            s.query(Benachrichtigung).filter(Benachrichtigung.link == f"/lead-management/lead/{v.id}").delete()
            _vorgangsordner_entfernen(v.id)
            s.delete(v)
        s.delete(k)
    for b in s.query(Benutzer).filter(Benutzer.name.like(f"{BENUTZER_PRAEFIX}%")):
        s.query(AdProfil).filter_by(benutzer_id=b.id).delete()
        s.query(Benachrichtigung).filter_by(benutzer_id=b.id).delete()
        s.query(VorgangNotizGelesen).filter_by(benutzer_id=b.id).delete()
        s.delete(b)
    s.commit()


class Basis(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        init_db()
        cls.s = SessionLocal()
        aufraeumen(cls.s)
        cls.client = client_fuer(1)
        cls.admin = cls.s.get(Benutzer, 1)
        cls.gesichert = {n: (z.wert if (z := cls.s.query(LeadParameter).filter_by(name=n).first()) is not None
                             else None) for n in PARAMETER}
        cls.ordner = Path(tempfile.mkdtemp(prefix="v35n3_taifun_"))
        for name, wert in (("terminierung_aktiv", "aus"), ("mail_versand_aktiv", "aus"),
                           ("taifun_export_aktiv", "an"), ("taifun_import_ordner", str(cls.ordner)),
                           ("taifun_export_encoding", "windows-1252"), ("pflichtfelder", PFLICHT),
                           ("kalender_sync", "aus"), ("glocke_lead_arten", "")):
            kern.parameter_setzen(cls.s, name, wert)
        cls.s.commit()
        cls.ad = Benutzer(name=f"{BENUTZER_PRAEFIX}Horst Beispiel", rolle="aussendienst",
                          pin_hash=auth.pin_hash("4321"), email=f"horst@{DOMAENE}")
        cls.lm = Benutzer(name=f"{BENUTZER_PRAEFIX}Leadmanagerin", vorname="Anna", rolle="innendienst",
                          pin_hash=auth.pin_hash("4321"), email=f"anna@{DOMAENE}", leadmanager=True)
        cls.s.add_all([cls.ad, cls.lm])
        cls.s.flush()
        cls.s.add(AdProfil(benutzer_id=cls.ad.id, aktiv_terminierung=True, termin_dauer_min=90,
                           puffer_min=30, max_termine_tag=3))
        cls.s.commit()
        cls.nr = 0

    @classmethod
    def tearDownClass(cls):
        aufraeumen(cls.s)
        for name, wert in cls.gesichert.items():
            zeile = cls.s.query(LeadParameter).filter_by(name=name).first()
            if wert is None:
                if zeile is not None:
                    cls.s.delete(zeile)
            else:
                kern.parameter_setzen(cls.s, name, wert)
        cls.s.commit()
        cls.s.close()
        shutil.rmtree(cls.ordner, ignore_errors=True)

    def setUp(self):
        self.s.rollback()
        for name, wert in (("terminierung_aktiv", "aus"), ("taifun_export_aktiv", "an"),
                           ("taifun_import_ordner", str(self.ordner))):
            kern.parameter_setzen(self.s, name, wert)
        self.s.commit()

    # --- Helfer -----------------------------------------------------------------------------

    def lead(self, nachname="Schliwa", vorname="Helmut", termin=True):
        """Demo-Lead wie in test_lead_v6_taifun: Herr Helmut Schliwa, Im Knick 36, 47269 Duisburg,
        Mobilnummer, Interesse WP, Vertriebler Horst, Termin vorgemerkt +7 Tage 10:00."""
        type(self).nr += 1
        quelle = (self.s.query(LeadQuelle).filter_by(key="website").first()
                  or self.s.query(LeadQuelle).order_by(LeadQuelle.id).first())
        daten = {"anrede": "Herr", "vorname": vorname, "nachname": nachname, "strasse": "Im Knick 36",
                 "plz": "47269", "ort": "Duisburg", "telefon": "0171 1234567", "sparten": ["WP"],
                 "email": f"lead{self.nr}@{DOMAENE}"}
        vorgang, _ = kern.lead_anlegen(self.s, daten, quelle, "api", entscheidung="neu")
        kunde = self.s.get(Kunde, vorgang.kunde_id)
        kunde.email = daten["email"]
        kunde.vertriebskanal = "Website"
        kunde.objektart = "EFH"
        vorgang.ad_id = self.ad.id
        vorgang.demo = True
        self.s.commit()
        self.s.query(VorgangObjekt).filter_by(vorgang_id=vorgang.id).delete()
        objekte_modul.hauptobjekt(self.s, vorgang.id, anlegen=True)
        self.s.commit()
        if termin:
            haupt = objekte_modul.hauptobjekt(self.s, vorgang.id)
            t = VotTermin(vorgang_id=vorgang.id, ad_id=self.ad.id, objekt_id=haupt.id if haupt else None,
                          beginn=(datetime.now() + timedelta(days=7)).replace(hour=10, minute=0, second=0,
                                                                              microsecond=0),
                          status="vorgemerkt", quelle="assistent", demo=True, typ="vot", medium="vor_ort")
            t.ende = t.beginn + timedelta(minutes=90)
            self.s.add(t)
            self.s.commit()
        return vorgang

    def frisch(self, vorgang):
        self.s.expire_all()
        return self.s.get(Vorgang, vorgang.id)

    def kunde(self, vorgang):
        self.s.expire_all()
        return self.s.get(Kunde, vorgang.kunde_id)

    def uebergaben(self, vorgang):
        self.s.expire_all()
        return self.s.query(TaifunUebergabe).filter_by(vorgang_id=vorgang.id).order_by(TaifunUebergabe.id).all()

    def dateien(self, vorgang):
        return sorted(self.ordner.glob(f"LM_V{vorgang.id}_*.xml"))

    def kartei(self, vorgang, client=None):
        r = (client or self.client).get(f"/lead-management/lead/{vorgang.id}")
        self.assertEqual(r.status_code, 200, r.text[:300])
        return r.text

    def liste(self, status=""):
        r = self.client.get(LISTE + (f"?status={status}" if status else ""))
        self.assertEqual(r.status_code, 200, r.text[:300])
        return r.text

    def zeile(self, html: str, vorgang) -> str:
        self.assertIn(f'data-vorgang="{vorgang.id}"', html)
        return html.split(f'data-vorgang="{vorgang.id}"', 1)[1].split("</tr>", 1)[0]


# --- (1) Kartei ohne Knopf und ohne Kundennummer-Feld ------------------------------------------------------

class A_Kartei(Basis):
    def test_kein_knopf_kein_feld_badge_ohne_nummer(self):
        v = self.lead()
        seite = self.kartei(v)
        self.assertNotIn('id="lk-taifun-knopf"', seite)
        self.assertNotIn('data-rolle="taifun-form"', seite)
        self.assertNotIn("An TAIFUN übergeben", seite)
        self.assertNotIn("Erneut an TAIFUN übergeben", seite)
        self.assertNotIn('name="taifun_kundennr"', seite)
        self.assertNotIn("TAIFUN-Kundennummer", seite)
        self.assertNotIn('data-rolle="taifun-badge"', seite)
        # Terminierung in der Testphase bleibt der einzige Auslöser (Knopf aktiv mit TAIFUN-Tooltip)
        knopf = tag(seite, "lk-terminierung-knopf")
        self.assertIn('data-taifun-testphase="1"', knopf)
        # Spalte gefüllt (ungelesen) → Badge trotzdem ohne Nummer
        k = self.kunde(v)
        k.taifun_kundennr = "10815"
        self.s.commit()
        ok, meldung, _u = taifun_export.exportieren(self.s, v.id, 1, "manuell")
        self.assertTrue(ok, meldung)
        seite = self.kartei(v)
        self.assertIn('data-rolle="taifun-badge"', seite)
        self.assertIn(f"TAIFUN {self.frisch(v).taifun_export_am.strftime('%d.%m.%Y')}", seite)
        self.assertNotIn("Nr. 10815", seite)
        self.assertNotIn("10815", seite.split('data-rolle="taifun-badge"', 1)[1].split("</span>", 1)[0])
        self.assertNotIn('id="lk-taifun-knopf"', seite)
        self.assertNotIn("Erneut an TAIFUN übergeben", seite)
        kontext = taifun_export.kartei_kontext(self.s, self.frisch(v), self.kunde(v), self.admin)
        for feld in ("knopf_text", "knopf_tooltip", "knopf_gesperrt", "url", "kundennr", "rueckfrage", "erlaubt"):
            self.assertNotIn(feld, kontext, feld)
        self.assertEqual(kontext["badge"], f"TAIFUN {self.frisch(v).taifun_export_am.strftime('%d.%m.%Y')}")
        self.assertNotIn("Kundennummer", kontext["badge_titel"])
        # Leadmanagerin: gleiche Kartei, ebenfalls ohne Knopf; Außendienst: kein Feld, kein Knopf
        for b in (self.lm, self.ad):
            seite = self.kartei(v, client_fuer(b.id))
            self.assertNotIn('id="lk-taifun-knopf"', seite)
            self.assertNotIn('name="taifun_kundennr"', seite)


# --- (2) Übergabeliste: „Erneut übergeben“ je Zeile --------------------------------------------------------

class B_Uebergabeliste(Basis):
    def test_erneut_uebergeben_mit_rueckfrage(self):
        v = self.lead()
        ok, meldung, u1 = taifun_export.exportieren(self.s, v.id, 1, "manuell")
        self.assertTrue(ok, meldung)
        liste = self.liste()
        zeile = self.zeile(liste, v)
        self.assertIn('data-rolle="taifun-erneut"', zeile)
        self.assertIn("Erneut übergeben", zeile)
        knopf = tag(liste, f"taifun-erneut-{u1.id}")
        self.assertIn("window.confirm(&#34;", knopf)   # tojson|forceescape
        self.assertNotIn('confirm("', knopf)
        # derselbe Text steht als title (ungeescaped) am Knopf
        self.assertIn(f"Letzte Übergabe am {self.frisch(v).taifun_export_am.strftime('%d.%m.%Y %H:%M')}", knopf)
        self.assertIn("trotzdem erneut übergeben?", knopf)
        self.assertIn("Doppelte Kunden in TAIFUN vermeiden.", knopf)
        self.assertIn('name="zurueck"', zeile)
        # JSON ohne Bestätigung → 409 mit Rückfrage
        r = self.client.post(f"/lead-management/lead/{v.id}/taifun", json={}, headers={"accept": "application/json"})
        self.assertEqual(r.status_code, 409, r.text)
        self.assertIn("bereits an TAIFUN übergeben", r.json()["rueckfrage"])
        self.assertEqual(len(self.dateien(v)), 1)
        # Formular ohne JavaScript → zurück auf die Liste mit Rückfrage-Balken „Trotzdem übergeben“
        r = self.client.post(f"/lead-management/lead/{v.id}/taifun", data={"zurueck": LISTE + "?status=geschrieben"})
        self.assertEqual(r.status_code, 303, r.text)
        ort = r.headers["location"]
        self.assertTrue(ort.startswith(LISTE + "?status=geschrieben"), ort)
        self.assertIn(f"taifun_rueckfrage={v.id}", ort)
        seite = self.client.get(ort).text
        self.assertIn('data-rolle="taifun-trotzdem"', seite)
        self.assertIn("TAIFUN-Übergabe – Rückfrage", seite)
        self.assertIn(f"V{v.id}", seite)
        self.assertEqual(len(self.dateien(v)), 1)
        # mit Bestätigung → neue Übergabe, Redirect zurück auf die Liste (mit Filter)
        r = self.client.post(f"/lead-management/lead/{v.id}/taifun",
                             data={"bestaetigt": "1", "zurueck": LISTE + "?status=geschrieben"})
        self.assertEqual(r.status_code, 303, r.text)
        self.assertTrue(r.headers["location"].startswith(LISTE + "?status=geschrieben"), r.headers["location"])
        self.assertNotIn("fehler=1", r.headers["location"])
        self.assertIn("An TAIFUN übergeben: LM_", meldung_aus(r))
        self.assertEqual(len(self.dateien(v)), 2)
        u = self.uebergaben(v)
        self.assertEqual([x.status for x in u], ["geschrieben", "geschrieben"])
        self.assertEqual(u[1].grund, "manuell")
        self.assertIn("Übergabeliste (erneut)", self.zeile(self.liste(), v))
        # Schalter aus → kein Knopf in der Liste; Kanal „?“ → Hinweis statt Knopf
        kern.parameter_setzen(self.s, "taifun_export_aktiv", "aus")
        self.s.commit()
        self.assertNotIn('data-rolle="taifun-erneut"', self.liste())
        kern.parameter_setzen(self.s, "taifun_export_aktiv", "an")
        self.s.commit()   # vor expire_all (self.kunde) – sonst ginge die ungeflushte Änderung verloren
        k = self.kunde(v)
        k.vertriebskanal = "?"
        self.s.commit()
        zeile = self.zeile(self.liste(), v)
        self.assertNotIn('data-rolle="taifun-erneut"', zeile)
        self.assertIn("Vertriebskanal klären", zeile)
        r = self.client.post(f"/lead-management/lead/{v.id}/taifun", json={"bestaetigt": "1"},
                             headers={"accept": "application/json"})
        self.assertEqual(r.status_code, 409)

    def test_fehlerzeile_erneut_und_kartei_link(self):
        v = self.lead()
        kaputt = self.ordner / "weg" / "LM Datenimport"
        kern.parameter_setzen(self.s, "taifun_import_ordner", str(kaputt))
        self.s.commit()
        ok, meldung, u = taifun_export.exportieren(self.s, v.id, 1, "terminierung")
        self.assertFalse(ok)
        self.assertEqual(self.frisch(v).taifun_export_status, "fehler")
        seite = self.kartei(v)
        self.assertIn('id="lm-taifun-hinweis"', seite)
        self.assertIn('data-rolle="taifun-liste-link"', seite)
        self.assertIn(LISTE + "?status=fehler", seite)
        self.assertNotIn('data-rolle="taifun-erneut"', seite)
        self.assertNotIn('data-rolle="taifun-trotzdem"', seite)
        # Außendienst: Balken ohne Link (Wiederholung durch den Innendienst)
        seite_ad = self.kartei(v, client_fuer(self.ad.id))
        self.assertIn('id="lm-taifun-hinweis"', seite_ad)
        self.assertNotIn('data-rolle="taifun-liste-link"', seite_ad)
        zeile = self.zeile(self.liste("fehler"), v)
        self.assertIn("Erneut übergeben", zeile)
        knopf = tag(self.liste("fehler"), f"taifun-erneut-{u.id}")
        self.assertIn("erneut versuchen?", unquote_plus(knopf))
        # Reparatur + „Erneut übergeben“ → Erfolg, Label weg
        kern.parameter_setzen(self.s, "taifun_import_ordner", str(self.ordner))
        self.s.commit()
        r = self.client.post(f"/lead-management/lead/{v.id}/taifun",
                             data={"bestaetigt": "1", "zurueck": LISTE + "?status=fehler"})
        self.assertEqual(r.status_code, 303, r.text)
        self.assertNotIn("fehler=1", r.headers["location"])
        self.assertEqual(self.frisch(v).taifun_export_status, "geschrieben")
        self.assertNotIn('id="lm-taifun-hinweis"', self.kartei(v))


# --- (3) Dubletten-Hinweis ohne Kundennummer, Terminierung → übersprungen --------------------------------------

class C_Dubletten(Basis):
    def test_kundennummer_kein_beleg_terminierung_uebersprungen(self):
        v = self.lead()
        k = self.kunde(v)
        k.taifun_kundennr = "10815"
        self.s.commit()
        self.assertEqual(taifun_export.dubletten_hinweis(self.s, v, self.kunde(v)), "")
        self.assertEqual(taifun_export.rueckfrage_text(self.s, v, self.kunde(v)), "")
        self.assertEqual(taifun_export.dubletten_belege(self.s, [k.id]), {})
        self.s.add(Angebot(nummer=f"V35N3-{v.id}", kunde_id=k.id, vorgang_id=v.id, status="Versendet (extern)",
                           extern=True, taifun_nummer="AN654321", konfigurator_typ="WP"))
        self.s.commit()
        beleg = taifun_export.dubletten_hinweis(self.s, v, self.kunde(v))
        self.assertEqual(beleg, "TAIFUN-Angebot AN654321")
        self.assertNotIn("Kundennummer", beleg)
        # Terminierung (Testphase) → Export übersprungen, Zeile „übersprungen (Rückfrage)“, kein rotes Label
        r = self.client.post(f"/lead-management/lead/{v.id}/terminierung", data={"bestaetigung": "auto"})
        self.assertEqual(r.status_code, 303, r.text)
        self.assertIn("übersprungen", meldung_aus(r))
        self.assertIn("Übergabeliste", meldung_aus(r))
        self.assertNotIn("Knopf", meldung_aus(r))
        self.assertEqual(self.dateien(v), [])
        u = self.uebergaben(v)
        self.assertEqual([x.status for x in u], ["uebersprungen"])
        self.assertEqual(u[0].grund, "terminierung")
        self.assertIn("AN654321", u[0].fehler_text)
        self.assertEqual(self.frisch(v).taifun_export_status, "")
        self.assertEqual(taifun_export.fehler_anzahl(self.s),
                         self.s.query(Vorgang).filter(Vorgang.taifun_export_status == "fehler").count())
        # zweiter Klick → keine zweite Zeile
        self.client.post(f"/lead-management/lead/{v.id}/terminierung", data={"bestaetigung": "auto"})
        self.assertEqual(len(self.uebergaben(v)), 1)
        liste = self.liste("uebersprungen")
        zeile = self.zeile(liste, v)
        self.assertIn("übersprungen (Rückfrage)", zeile)
        self.assertIn("Trotzdem übergeben", zeile)
        self.assertNotIn("Als importiert markieren", zeile)
        knopf = tag(liste, f"taifun-erneut-{u[0].id}")
        self.assertIn("AN654321", unquote_plus(knopf))
        self.assertFalse(taifun_export.als_importiert(self.s, u[0])[0])
        self.s.rollback()
        # Scheduler-Lauf fasst übersprungene Zeilen nicht an
        taifun_export.abholung_pruefen()
        self.assertEqual(self.uebergaben(v)[0].status, "uebersprungen")
        # „Trotzdem übergeben“ aus der Liste → Export
        r = self.client.post(f"/lead-management/lead/{v.id}/taifun",
                             data={"bestaetigt": "1", "zurueck": LISTE + "?status=uebersprungen"})
        self.assertEqual(r.status_code, 303, r.text)
        self.assertNotIn("fehler=1", r.headers["location"])
        self.assertEqual([x.status for x in self.uebergaben(v)], ["uebersprungen", "geschrieben"])
        self.assertEqual(len(self.dateien(v)), 1)
        self.assertEqual(self.frisch(v).taifun_export_status, "geschrieben")


# --- (4)/(5)/(6) Objektfotos entfallen, Galerie bleibt -----------------------------------------------------------

class D_Objektfotos(Basis):
    def test_kein_markup_und_route_404(self):
        v = self.lead()
        haupt = objekte_modul.hauptobjekt(self.s, v.id)
        zweites = objekte_modul.objekt_anlegen(self.s, v, "Nebenweg 2", "47269", "Duisburg",
                                               bezeichnung="Scheune", objektart="EFH", interessen=["PV"])
        self.s.commit()
        seite = self.kartei(v)
        for muster in ('data-rolle="objektfotos"', 'data-rolle="objektfotos-einzel"', 'id="objektfotos-',
                       "objektfotos_v35.js", "lm_v35_g.css", "lk-objektfotos", "Fotos zum Objekt",
                       "Galerie-Ordner „Objekt"):
            self.assertNotIn(muster, seite, muster)
        self.assertIn(f'id="objekt-{zweites.id}"', seite)   # Objektkarten bleiben
        # Außendienst (eigener Lead) ebenfalls ohne Foto-Block
        self.assertNotIn('data-rolle="objektfotos"', self.kartei(v, client_fuer(self.ad.id)))
        # Erfassung: Sparten-Start mit Objekt und Prüfen-Seite
        ad = client_fuer(self.ad.id)
        kunde = self.kunde(v)
        r = ad.get(f"/erfassung/sparten?kunde_id={kunde.id}&objekt_id={zweites.id}")
        self.assertEqual(r.status_code, 200, r.text[:300])
        self.assertIn("Scheune", r.text)
        self.assertNotIn('data-rolle="objektfotos"', r.text)
        self.assertNotIn("Fotos zum Objekt", r.text)
        erfassung = Erfassung(kunde_id=kunde.id, benutzer_id=self.ad.id, sparte="WP", konfigurator_typ="WP",
                              vorgang_id=v.id, objekt_id=zweites.id, status="Entwurf", antworten_json="{}")
        self.s.add(erfassung)
        self.s.commit()
        r = ad.get(f"/erfassung/{erfassung.id}/pruefen")
        self.assertEqual(r.status_code, 200, r.text[:300])
        self.assertNotIn('data-rolle="objektfotos"', r.text)
        self.assertNotIn("Fotos zum Objekt", r.text)
        # Projektakte
        angebot = angebot_aufbau.angebot_anlegen(self.s, kunde.id, sparte="PV")
        angebot.positionen.append(AngebotsPosition(sort=1, pos_nr="PV001", bezeichnung="Pos",
                                                   beschreibung="Pos", menge=1, e_preis_cent=10000))
        angebot.vorgang_id = v.id
        angebot.objekt_id = zweites.id
        angebot_status_setzen(angebot, "Angenommen")
        self.s.commit()
        projekt = kern_proj.projekt_anlegen(self.s, angebot, projektleiter_id=1)
        gewerk = kern_proj.gewerk_anlegen(self.s, projekt, angebot, "PV")
        gewerk.objekt_id = zweites.id
        self.s.commit()
        r = self.client.get(f"/projektierung/projekt/{projekt.id}")
        self.assertEqual(r.status_code, 200, r.text[:300])
        self.assertNotIn('data-rolle="objektfotos"', r.text)
        self.assertNotIn("Objektfotos ·", r.text)
        self.assertNotIn('<option value="Objekt Scheune">', r.text)
        # Upload-Route der Objektfotos existiert nicht mehr
        for client in (self.client, ad):
            r = client.post(f"/lead-management/lead/{v.id}/objekt/{haupt.id}/fotos",
                            data={"zurueck": f"/lead-management/lead/{v.id}"},
                            files=[("dateien", ("haus.jpg", io.BytesIO(jpg_bytes()), "image/jpeg"))],
                            headers={"Accept": "application/json"})
            self.assertEqual(r.status_code, 404, r.text[:200])
            r = client.post(f"/lead-management/lead/{v.id}/objekt/{haupt.id}/fotos/1/loeschen",
                            headers={"Accept": "application/json"})
            self.assertEqual(r.status_code, 404)
        self.assertEqual(self.s.query(GalerieDatei).filter_by(vorgang_id=v.id).count(), 0)
        # Umbenennen eines Objekts läuft ohne Galerie-Hook
        objekt = self.s.get(VorgangObjekt, zweites.id)
        ergebnis = lead_kartei.objekt_feld_speichern(self.s, v, kunde, objekt, "bezeichnung", "Halle",
                                                     benutzer=self.admin)
        self.assertTrue(ergebnis["ok"], ergebnis)
        self.s.commit()

    def test_ordner_liste_ohne_objekt_altbestand_sichtbar(self):
        v = self.lead()
        objekte_modul.objekt_anlegen(self.s, v, "Nebenweg 2", "47269", "Duisburg", bezeichnung="Scheune")
        self.s.commit()
        standard = galerie_modul.ordner_liste(self.s, "WP")
        self.assertEqual(galerie_modul.ordner_liste(self.s, "WP", vorgang=v), standard)
        self.assertEqual(galerie_modul.ordner_liste(self.s, "WP", vorgang=v.id), standard)
        self.assertFalse(any(o.startswith("Objekt") for o in standard), standard)
        self.assertEqual(standard[:len(galerie_modul.SPARTEN_ORDNER["WP"])], galerie_modul.SPARTEN_ORDNER["WP"])
        for attr in ("objekt_ordner", "objektfotos", "objektfotos_speichern", "objektfotos_kontext",
                     "objekt_umbenannt", "aktueller_objekt_ordner", "objektfotos_je_gewerk", "OBJEKTFOTO_MAX_BYTES"):
            self.assertFalse(hasattr(galerie_modul, attr), attr)
        # Altbestand: Datei im Ordner „Objekt 1“ (vor dem Nachtrag hochgeladen) bleibt sichtbar
        alt = GalerieDatei(vorgang_id=v.id, sparte="WP", ordner="Objekt 1", dateiname="alt.jpg",
                           pfad=f"vorgaenge/{v.id}/galerie/WP/Objekt 1/alt.jpg", bild=True,
                           quelle="upload", hochgeladen_von=1)
        self.s.add(alt)
        self.s.commit()
        uebersicht = galerie_modul.uebersicht(self.s, v.id, "WP")
        self.assertEqual([d.id for d in uebersicht["Objekt 1"]["eintraege"]], [alt.id])
        self.assertNotIn("Objekt", uebersicht)
        self.assertNotIn("Objekt Scheune", uebersicht)
        r = self.client.get(f"/vorgaenge/{v.id}")
        self.assertEqual(r.status_code, 200)
        self.assertIn("Objekt 1", r.text)
        self.assertIn("alt.jpg", r.text)
        self.assertNotIn('<option value="Objekt 1">', r.text)   # kein Einsortieren in Objekt-Ordner mehr
        # Upload in einen Objekt-Ordner fällt auf „Allgemein“ zurück; Verschieben dorthin geht nicht
        r = self.client.post(f"/vorgaenge/{v.id}/galerie/upload",
                             data={"ordner": "Objekt Scheune", "sparte": "WP", "zurueck": f"/vorgaenge/{v.id}"},
                             files=[("dateien", ("neu.jpg", io.BytesIO(jpg_bytes()), "image/jpeg"))],
                             headers={"Accept": "application/json"})
        self.assertEqual(r.status_code, 200, r.text)
        self.assertEqual(r.json()["abgelegt"][0]["ordner"], "Allgemein")
        neu = self.s.get(GalerieDatei, r.json()["abgelegt"][0]["id"])
        self.assertFalse(galerie_modul.verschieben(self.s, neu, "Objekt 1"))
        self.s.rollback()
        # No-op-Migration bleibt für den Hook in migrate.py
        self.assertEqual(galerie_modul.migration_v35_objektfotos(self.s), [])
        self.assertEqual(galerie_modul.migration_v35_objektfotos(self.s), [])

    def test_heic_upload_wird_jpg(self):
        v = self.lead(termin=False)
        r = self.client.post(f"/vorgaenge/{v.id}/galerie/upload",
                             data={"ordner": "Allgemein", "sparte": "WP", "zurueck": f"/vorgaenge/{v.id}"},
                             files=[("dateien", ("iphone.heic", io.BytesIO(heic_bytes()), "image/heic")),
                                    ("dateien", ("getarnt.jpg", io.BytesIO(heic_bytes((40, 30))), "image/jpeg"))],
                             headers={"Accept": "application/json"})
        self.assertEqual(r.status_code, 200, r.text)
        self.assertTrue(r.json()["ok"], r.json())
        self.s.expire_all()
        dateien = self.s.query(GalerieDatei).filter_by(vorgang_id=v.id).order_by(GalerieDatei.id).all()
        self.assertEqual(len(dateien), 2)
        from PIL import Image
        for d in dateien:
            self.assertTrue(d.dateiname.lower().endswith(".jpg"), d.dateiname)
            self.assertEqual(d.ordner, "Allgemein")
            pfad = config.DATA_ORDNER / d.pfad
            with Image.open(pfad) as bild:
                self.assertEqual(bild.format, "JPEG")
            self.assertFalse(galerie_modul.ist_heic(pfad))
        ordner = (config.DATA_ORDNER / dateien[0].pfad).parent
        self.assertEqual([p.name for p in ordner.glob("*.heic")], [])


# --- (7) Autospeichern weist taifun_kundennr ab --------------------------------------------------------------

class E_Feld(Basis):
    def test_feld_speichern_abgewiesen(self):
        v = self.lead(termin=False)
        k = self.kunde(v)
        ergebnis = lead_kartei.feld_speichern(self.s, v, k, "taifun_kundennr", "10815", benutzer=self.admin)
        self.assertFalse(ergebnis["ok"])
        self.assertEqual(ergebnis["meldung"], "Feld unbekannt.")
        self.assertNotIn("taifun_kundennr", lead_kartei.FELD_LABELS)
        self.assertNotIn("taifun_kundennr", lead_kartei.AUTOSPEICHER_FELDER)
        r = self.client.post(f"/lead-management/lead/{v.id}/feld", json={"feld": "taifun_kundennr", "wert": "10815"})
        self.assertEqual(r.status_code, 400, r.text)
        self.assertEqual(self.kunde(v).taifun_kundennr, "")
        # Boards-Inline nutzt dieselbe Funktion → ebenfalls abgewiesen
        r = self.client.post(f"/lead-management/boards/zeile/{v.id}", json={"feld": "taifun_kundennr", "wert": "10815"})
        self.assertIn(r.status_code, (400, 404, 422))
        self.assertEqual(self.kunde(v).taifun_kundennr, "")


# --- (8) Bausteine und Wächter ---------------------------------------------------------------------------------

class F_Bausteine(unittest.TestCase):
    def test_dateien_entfernt_und_reste(self):
        for pfad in ("app/routers/lm_objektfotos.py", "app/templates/_objektfotos.html",
                     "app/static/objektfotos_v35.js", "app/static/lm_v35_g.css",
                     "tests/test_lead_v6_objektfotos.py"):
            self.assertFalse((PROJEKT / pfad).exists(), pfad)
        main = (PROJEKT / "app" / "main.py").read_text(encoding="utf-8")
        self.assertNotIn("lm_objektfotos", main)
        for pfad in ("app/templates/leadmanagement/kartei_objekte.html", "app/templates/erfassung/sparten.html",
                     "app/templates/erfassung/pruefen.html", "app/templates/projektierung/akte.html",
                     "app/lead_kartei.py", "app/routers/erfassung.py", "app/routers/projektierung.py",
                     "app/routers/vorgaenge.py", "app/routers/montage.py"):
            quelle = (PROJEKT / pfad).read_text(encoding="utf-8")
            self.assertNotIn("objektfotos_", quelle, pfad)
            self.assertNotIn("_objektfotos.html", quelle, pfad)
            self.assertNotIn("objekt_umbenannt", quelle, pfad)
            self.assertNotIn("vorgang=vorgang", quelle.split("ordner_liste(")[-1][:120] if "ordner_liste(" in quelle else "", pfad)
        galerie_quelle = (PROJEKT / "app" / "galerie.py").read_text(encoding="utf-8")
        self.assertIn("def ist_heic", galerie_quelle)
        self.assertIn("def _heic_nach_jpg", galerie_quelle)
        self.assertIn("def migration_v35_objektfotos", galerie_quelle)
        self.assertNotIn("def objektfotos_speichern", galerie_quelle)
        self.assertIn("objekt_id", (PROJEKT / "app" / "models.py").read_text(encoding="utf-8"))   # Spalte bleibt
        self.assertIn('("app.galerie", "migration_v35_objektfotos")',
                      (PROJEKT / "migrate.py").read_text(encoding="utf-8"))   # Hook unverändert

    def test_taifun_templates_und_tokens(self):
        kartei = (PROJEKT / "app/templates/leadmanagement/kartei.html").read_text(encoding="utf-8")
        self.assertNotIn("lk-taifun-knopf", kartei)
        self.assertNotIn("taifun.url", kartei)
        info = (PROJEKT / "app/templates/leadmanagement/kartei_info.html").read_text(encoding="utf-8")
        self.assertNotIn('name="taifun_kundennr"', info)
        hinweis = (PROJEKT / "app/templates/leadmanagement/_taifun_hinweis.html").read_text(encoding="utf-8")
        self.assertIn("taifun-liste-link", hinweis)
        self.assertNotIn("taifun-erneut", hinweis)
        self.assertNotIn("taifun-trotzdem", hinweis)
        liste = (PROJEKT / "app/templates/leadmanagement/taifun_uebergaben.html").read_text(encoding="utf-8")
        self.assertIn("z.erneut_text | tojson | forceescape", liste)
        self.assertIn('data-rolle="taifun-trotzdem"', liste)
        css = (PROJEKT / "app/static/lm_v35_t.css").read_text(encoding="utf-8")
        self.assertNotRegex(css, r"#[0-9a-fA-F]{3,6}\b")   # nur Tokens
        self.assertNotIn("#lk-taifun", css)
        self.assertIn("lm-taifun-status-uebersprungen", css)
        einst = (PROJEKT / "app/templates/konfiguration/lead_einstellungen.html").read_text(encoding="utf-8")
        self.assertNotIn("Kartei-Knopf", einst)
        self.assertNotIn("An TAIFUN übergeben", einst)
        doku = (PROJEKT / "docs" / "taifun-kundenexport.md").read_text(encoding="utf-8")
        self.assertIn("Übergabeliste", doku)
        self.assertNotIn("Feld „TAIFUN-Kundennummer“ im Kundeninfo-Block", doku)
        self.assertEqual(taifun_export.STATUS_NAMEN["uebersprungen"], "übersprungen (Rückfrage)")
        self.assertNotIn("uebersprungen", taifun_export.ERFOLG_STATUS)


if __name__ == "__main__":
    unittest.main()
