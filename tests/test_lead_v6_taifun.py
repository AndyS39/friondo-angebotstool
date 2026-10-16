# Tests PLAN_LEAD_V6 (v35, Agent T) – Phase 183 TAIFUN-Kundenexport, Phase 187 (a)–(j):
#  (a) XML eines Demo-Leads validiert gegen docs/taifun/ADRESSEN.xsd, Elementreihenfolge und
#      Namensraum korrekt, Encoding-Deklaration windows-1252, Umlaut im Namen korrekt kodiert
#  (b) Kontrollwert Helmut Schliwa: Name3 „Helmut Schliwa“, Straße „Im Knick“, Hausnummer „36“,
#      PLZ/Ort, Briefanrede „Sehr geehrter Herr Schliwa,“, Kartei mit Vorgang, Kanal, „Wärmepumpe“,
#      Objekt, Vertriebler, „vorgemerkt: <Datum> 10:00“
#  (c) Mobilnummer → Funk, Festnetz → Telefon (national formatiert), zwei Nummern → beide
#  (d) MFH mit abweichender Rechnungsadresse → Rechnungsadresse im Ad, Objektadresse in der Kartei
#  (e) Terminierung in der Testphase schreibt die Datei, bucht nicht, sendet nicht (Phase bleibt);
#      bei freigeschalteter Terminierung Export + Buchung in einem Klick
#  (f) Ordner nicht beschreibbar → Status fehler, rotes Label (Kartei + Hauptboard Rang 0), Zähler,
#      „Erneut übergeben“ nach Reparatur → Erfolg, Label weg
#  (g) zweite Übergabe fragt nach (bereits übergeben), Dubletten-Hinweis bei TAIFUN-Angebotsnummer /
#      Kundennummer; Terminierung überspringt den Export dann mit Aktivität
#  (h) Scheduler-Lauf taifun-uebergaben setzt „abgeholt“, wenn die Datei fehlt; nicht erreichbarer
#      Ordner markiert nichts; Lauf registriert (900 s)
#  (i) Längen über 60 Zeichen werden gekürzt und in Kartei + Aktivität vermerkt
#  (j) kein Export bei taifun_export_aktiv = aus (Standard!) – Kartei-Knopf ausgegraut, Terminierung
#      nur Aktivität „nicht aktiv“; „Testdatei schreiben“ funktioniert trotzdem
#  dazu: Übergabeliste, „Als importiert markieren“, XML-Download, Rechte (AD 403), Lead-Einstellungen
#  (Abschnitt, Speichern, Ordner prüfen), Boards (Spalte/Chip), Migration idempotent, Wächter-Regeln.
# Läuft gegen die DB-Kopie (DB_PFAD_OVERRIDE); Testdaten tragen die E-Mail-Domäne „v35t.test“
# und werden aufgeräumt; der Import-Ordner ist ein Temp-Ordner (Parameter taifun_import_ordner);
# kein Netz, kein Graph, kein Outlook.
import json
import re
import shutil
import tempfile
import unittest
import warnings
from datetime import datetime, timedelta
from pathlib import Path
from unittest import mock
from urllib.parse import unquote_plus

warnings.filterwarnings("ignore")

from fastapi.testclient import TestClient
from lxml import etree

from app import auth, kalender, lead_v5, scheduler, taifun_export
from app import leadmanagement as kern
from app import objekte as objekte_modul
from app.db import SessionLocal, init_db
from app.main import app
from app.models import (AdProfil, Angebot, Benachrichtigung, Benutzer, KommunikationLog, Kunde,
                        LeadAktivitaet, LeadParameter, LeadQuelle, TaifunUebergabe, Todo, Vorgang,
                        VorgangObjekt, VorgangsNotiz, VotTermin)

PROJEKT = Path(__file__).resolve().parent.parent
DOMAENE = "v35t.test"
BENUTZER_PRAEFIX = "V35T "
NS = taifun_export.NAMENSRAUM
PARAMETER = ("terminierung_aktiv", "mail_versand_aktiv", "taifun_export_aktiv", "taifun_import_ordner",
             "taifun_export_encoding", "taifun_testdatei_ok", "taifun_encoding_ok", "taifun_ordner_geprueft",
             "pflichtfelder", "kalender_sync", "glocke_lead_arten")
PFLICHT = "anrede; nachname; telefon; strasse; plz; ort; vertriebskanal; interesse; objektart; ad_id"


def aufraeumen(s):
    s.rollback()
    for k in s.query(Kunde).filter(Kunde.email.like(f"%@{DOMAENE}")):
        for v in s.query(Vorgang).filter_by(kunde_id=k.id):
            s.query(LeadAktivitaet).filter_by(vorgang_id=v.id).delete()
            s.query(KommunikationLog).filter_by(vorgang_id=v.id).delete()
            s.query(VotTermin).filter_by(vorgang_id=v.id).delete()
            s.query(VorgangsNotiz).filter_by(vorgang_id=v.id).delete()
            s.query(VorgangObjekt).filter_by(vorgang_id=v.id).delete()
            s.query(Todo).filter_by(vorgang_id=v.id).delete()
            s.query(TaifunUebergabe).filter_by(vorgang_id=v.id).delete()
            s.query(Benachrichtigung).filter(
                Benachrichtigung.link == f"/lead-management/lead/{v.id}").delete()
            s.query(Angebot).filter_by(vorgang_id=v.id).delete()
            s.delete(v)
        s.query(Angebot).filter_by(kunde_id=k.id).delete()
        s.delete(k)
    s.query(TaifunUebergabe).filter(TaifunUebergabe.vorgang_id == 0,
                                    TaifunUebergabe.pfad.like("%v35t%")).delete(synchronize_session=False)
    for b in s.query(Benutzer).filter(Benutzer.name.like(f"{BENUTZER_PRAEFIX}%")):
        s.query(AdProfil).filter_by(benutzer_id=b.id).delete()
        s.query(Benachrichtigung).filter_by(benutzer_id=b.id).delete()
        s.delete(b)
    s.commit()


def meldung_aus(r) -> str:
    ort = r.headers.get("location", "")
    return unquote_plus(ort.split("meldung=", 1)[1].split("&", 1)[0]) if "meldung=" in ort else ""


def tag(seite: str, element_id: str) -> str:
    """Das vollständige öffnende Tag des Elements mit dieser id (Attribute vor und nach der id)."""
    vorher, nachher = seite.split(f'id="{element_id}"', 1)
    return "<" + vorher.rsplit("<", 1)[1] + f'id="{element_id}"' + nachher.split(">", 1)[0] + ">"


def ad_elemente(xml: bytes) -> dict:
    """{Elementname: Text} des (einzigen) Ad-Eintrags in Dokumentreihenfolge."""
    root = etree.fromstring(xml)
    ads = root.findall(f"{{{NS}}}Ad")
    assert len(ads) == 1, "genau ein Ad je Datei"
    return {etree.QName(e).localname: (e.text or "") for e in ads[0]}


class Basis(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        init_db()
        cls.s = SessionLocal()
        aufraeumen(cls.s)
        cls.client = TestClient(app, follow_redirects=False)
        cls.client.cookies.set(auth.COOKIE_NAME, auth.cookie_wert(1))
        cls.admin = cls.s.get(Benutzer, 1)
        cls.gesichert = {n: (z.wert if (z := cls.s.query(LeadParameter).filter_by(name=n).first()) is not None
                             else None) for n in PARAMETER}
        cls.ordner = Path(tempfile.mkdtemp(prefix="v35t_taifun_"))
        for name, wert in (("terminierung_aktiv", "aus"), ("mail_versand_aktiv", "aus"),
                           ("taifun_export_aktiv", "an"), ("taifun_import_ordner", str(cls.ordner)),
                           ("taifun_export_encoding", "windows-1252"), ("taifun_testdatei_ok", ""),
                           ("taifun_encoding_ok", ""), ("taifun_ordner_geprueft", ""),
                           ("pflichtfelder", PFLICHT), ("kalender_sync", "aus"), ("glocke_lead_arten", "")):
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
                           ("taifun_import_ordner", str(self.ordner)), ("taifun_export_encoding", "windows-1252")):
            kern.parameter_setzen(self.s, name, wert)
        self.s.commit()

    # --- Helfer -----------------------------------------------------------------------------

    def lead(self, nachname="Schliwa", vorname="Helmut", anrede="Herr", telefon="0171 1234567",
             strasse="Im Knick 36", plz="47269", ort="Duisburg", kanal="Website", sparten=("WP",),
             termin=True, email=None, firma="", **extra):
        """Demo-Lead (Kontrollwert Phase 187): Herr Helmut Schliwa, Im Knick 36, 47269 Duisburg,
        Mobilnummer, Interesse WP, Vertriebler Horst, Termin vorgemerkt +7 Tage 10:00."""
        type(self).nr += 1
        quelle = self.s.query(LeadQuelle).filter_by(key="website").first()
        daten = {"anrede": anrede, "vorname": vorname, "nachname": nachname, "strasse": strasse, "plz": plz,
                 "ort": ort, "telefon": telefon, "sparten": list(sparten),
                 "email": email or f"lead{self.nr}@{DOMAENE}"}
        vorgang, _ = kern.lead_anlegen(self.s, daten, quelle, "api", entscheidung="neu")
        kunde = self.s.get(Kunde, vorgang.kunde_id)
        kunde.email = daten["email"]
        kunde.vertriebskanal = kanal
        kunde.objektart = "EFH"
        kunde.firma = firma
        vorgang.ad_id = self.ad.id
        vorgang.demo = True
        for k, v in extra.items():
            setattr(vorgang, k, v)
        self.s.commit()
        self.s.query(VorgangObjekt).filter_by(vorgang_id=vorgang.id).delete()
        objekte_modul.hauptobjekt(self.s, vorgang.id, anlegen=True)
        self.s.commit()
        if termin:
            self.termin(vorgang)
        return vorgang

    def termin(self, vorgang, status="vorgemerkt", tage=7):
        haupt = objekte_modul.hauptobjekt(self.s, vorgang.id)
        t = VotTermin(vorgang_id=vorgang.id, ad_id=self.ad.id, objekt_id=haupt.id if haupt else None,
                      beginn=(datetime.now() + timedelta(days=tage)).replace(hour=10, minute=0, second=0,
                                                                              microsecond=0),
                      status=status, quelle="assistent", demo=True, typ="vot", medium="vor_ort")
        t.ende = t.beginn + timedelta(minutes=90)
        self.s.add(t)
        self.s.commit()
        return t

    def frisch(self, vorgang):
        self.s.expire_all()
        return self.s.get(Vorgang, vorgang.id)

    def kunde(self, vorgang):
        self.s.expire_all()
        return self.s.get(Kunde, vorgang.kunde_id)

    def aktivitaeten(self, vorgang):
        self.s.expire_all()
        return [a.text for a in self.s.query(LeadAktivitaet).filter_by(vorgang_id=vorgang.id)
                .order_by(LeadAktivitaet.id)]

    def uebergaben(self, vorgang):
        self.s.expire_all()
        return self.s.query(TaifunUebergabe).filter_by(vorgang_id=vorgang.id).order_by(TaifunUebergabe.id).all()

    def dateien(self, vorgang=None):
        muster = f"LM_V{vorgang.id}_*.xml" if vorgang is not None else "LM_*.xml"
        return sorted(self.ordner.glob(muster))

    def kartei(self, vorgang):
        r = self.client.get(f"/lead-management/lead/{vorgang.id}")
        self.assertEqual(r.status_code, 200, r.text[:300])
        return r.text

    def felder(self, vorgang, benutzer=None):
        xml, hinweise = taifun_export.xml_fuer_vorgang(self.s, vorgang.id, benutzer or self.admin)
        self.assertEqual(taifun_export.validieren(xml), [])
        return ad_elemente(xml), hinweise, xml


# --- (a) Schema, Reihenfolge, Namensraum, Encoding, Umlaut ----------------------------------------

class A_Schema(Basis):
    def test_xml_validiert_reihenfolge_namensraum_encoding_umlaut(self):
        v = self.lead(nachname="Müller-Lüdenscheidt", vorname="Jürgen")
        felder, hinweise, xml = self.felder(v)
        self.assertTrue(xml.startswith(b'<?xml version="1.0" encoding="windows-1252"?>'), xml[:60])
        self.assertIn("J\xfcrgen M\xfcller-L\xfcdenscheidt".encode("cp1252"), xml)   # Umlaute als Zeichen
        self.assertNotIn(b"&#252;", xml)
        self.assertNotIn(b"&uuml;", xml)
        root = etree.fromstring(xml)
        self.assertEqual(root.tag, f"{{{NS}}}AdList")
        self.assertEqual(root.nsmap.get("TAIFUN"), NS)
        self.assertEqual(xml.count(b"<TAIFUN:Ad>"), 1)
        reihenfolge = list(felder)
        erwartet = [f for f in taifun_export.FELDER if f in reihenfolge]
        self.assertEqual(reihenfolge, erwartet)
        self.assertNotIn("Telefon", felder)   # leer → weggelassen (Mobilnummer steht in Funk)
        self.assertEqual(felder["KdUse"], "true")
        self.assertEqual(taifun_export.validieren(b"<?xml version='1.0'?><AdList/>")[0][:5], "Zeile")
        # Schema kommt immer aus docs/taifun/ADRESSEN.xsd (Original ersetzbar)
        self.assertTrue((PROJEKT / "docs" / "taifun" / "ADRESSEN.xsd").exists())
        self.assertIn("rekonstruiert", (PROJEKT / "docs" / "taifun" / "ADRESSEN.xsd").read_text("cp1252").lower())

    def test_utf8_encoding_per_parameter(self):
        kern.parameter_setzen(self.s, "taifun_export_encoding", "utf-8")
        self.s.commit()
        v = self.lead(nachname="Öztürk", vorname="Zoë")
        _f, _h, xml = self.felder(v)
        self.assertTrue(xml.startswith(b'<?xml version="1.0" encoding="utf-8"?>'))
        self.assertIn("Zoë Öztürk".encode("utf-8"), xml)


# --- (b) Kontrollwert Helmut Schliwa ---------------------------------------------------------------

class B_Kontrollwert(Basis):
    def test_schliwa_felder_und_kartei(self):
        v = self.lead()
        felder, hinweise, _xml = self.felder(v, self.lm)
        self.assertEqual(felder["Name3"], "Helmut Schliwa")
        self.assertEqual((felder["AnschriftStr"], felder["AnschriftHNr"]), ("Im Knick", "36"))
        self.assertEqual((felder["AnschriftPLZ"], felder["AnschriftOrt"]), ("47269", "Duisburg"))
        self.assertEqual(felder["Anrede"], "Sehr geehrter Herr Schliwa,")
        self.assertEqual(felder["Funk"], "0171 1234567")
        self.assertNotIn("Telefon", felder)
        self.assertEqual(felder["EMail"], self.kunde(v).email)
        kartei = felder["Kartei"].split("\n")
        self.assertTrue(kartei[0].startswith("Übergabe aus dem Friondo-Tool am "))
        self.assertTrue(kartei[0].endswith(f"durch {self.lm.name}"))
        self.assertEqual(kartei[1], f"Lead/Vorgang: V{v.id}")
        self.assertEqual(kartei[2], "Vertriebskanal: Website")
        self.assertEqual(kartei[3], "Interessen: Wärmepumpe")
        self.assertEqual(kartei[4], "Objekt: Einfamilienhaus, Im Knick 36, 47269 Duisburg")
        self.assertEqual(kartei[5], f"Vertriebler: {self.ad.name}")
        termin = self.s.query(VotTermin).filter_by(vorgang_id=v.id).first()
        self.assertEqual(kartei[6], f"Vor-Ort-Termin: vorgemerkt: {termin.beginn.strftime('%d.%m.%Y')} 10:00")
        self.assertIn("vorgemerkt: ", felder["Kartei"])
        self.assertTrue(kartei[7].startswith("Quelle: Website"))
        self.assertEqual(hinweise, [])
        # Vorname fehlt → nur Nachname; Firma → Firmenname; Großkunde-Zeile
        k = self.kunde(v)
        k.vorname = ""
        self.s.commit()
        self.assertEqual(self.felder(v)[0]["Name3"], "Schliwa")
        k.firma = "Schliwa Haustechnik GmbH"
        k.grosskunde = True
        self.s.commit()
        felder = self.felder(v)[0]
        self.assertEqual(felder["Name3"], "Schliwa Haustechnik GmbH")
        self.assertIn("Großkunde: ja", felder["Kartei"])

    def test_hausnummer_unsicher_und_email_ungueltig(self):
        v = self.lead(strasse="Hauptstr.12")
        felder, hinweise, _ = self.felder(v)
        self.assertEqual(felder["AnschriftStr"], "Hauptstr.12")
        self.assertNotIn("AnschriftHNr", felder)
        self.assertTrue(any("Hausnummer nicht sicher erkannt" in h for h in hinweise))
        self.assertIn("Hinweis: Hausnummer nicht sicher erkannt", felder["Kartei"])
        v.email_status = "ungueltig"
        self.s.commit()
        felder, hinweise, _ = self.felder(v)
        self.assertNotIn("EMail", felder)
        self.assertTrue(any("unzustellbar" in h for h in hinweise))
        self.assertEqual(taifun_export.strasse_hausnummer("Arnold-Overbeck-Str. 63-65")[:2],
                         ("Arnold-Overbeck-Str.", "63-65"))
        self.assertEqual(taifun_export.strasse_hausnummer("Musterstraße 12 a")[:2], ("Musterstraße", "12a"))


# --- (c) Telefon / Funk -------------------------------------------------------------------------------

class C_Telefon(Basis):
    def test_mobil_funk_festnetz_telefon(self):
        v = self.lead(telefon="0203 3965710")
        felder = self.felder(v)[0]
        self.assertEqual(felder["Telefon"], "0203 3965710")
        self.assertNotIn("Funk", felder)
        k = self.kunde(v)
        k.telefon = "+49 171 1234567"
        self.s.commit()
        felder = self.felder(v)[0]
        self.assertEqual(felder["Funk"], "0171 1234567")
        self.assertNotIn("Telefon", felder)
        k.telefon = "02033965710, 0160-5551234"
        self.s.commit()
        felder = self.felder(v)[0]
        self.assertEqual((felder["Telefon"], felder["Funk"]), ("0203 3965710", "0160 5551234"))
        for roh, erwartet in (("0203/3965710", "0203 3965710"), ("030 123456", "030 123456"),
                              ("02151 123456", "02151 123456"), ("0049 (0) 2841 12345", "02841 12345"),
                              ("+43 1 2345678", "+4312345678"), ("015112345678", "0151 12345678")):
            self.assertEqual(taifun_export.telefon_national(roh), erwartet, roh)
        self.assertTrue(taifun_export.ist_mobil("0176 123456"))
        self.assertFalse(taifun_export.ist_mobil("0203 123456"))


# --- (d) MFH mit abweichender Rechnungsadresse --------------------------------------------------------

class D_Rechnungsadresse(Basis):
    def test_mfh_rechnungsadresse_im_ad_objekt_in_kartei(self):
        v = self.lead()
        k = self.kunde(v)
        k.objektart = "MFH"
        k.parteien = 6
        k.rechnung_name = "Hausverwaltung Schliwa"
        k.rechnung_strasse = "Rechnungsweg 7"
        k.rechnung_plz = "40210"
        k.rechnung_ort = "Düsseldorf"
        haupt = objekte_modul.hauptobjekt(self.s, v.id)
        haupt.objektart = "MFH"
        haupt.parteien = 6
        haupt.rechnung_abweichend = True
        self.s.commit()
        felder, hinweise, _ = self.felder(v)
        self.assertEqual((felder["AnschriftStr"], felder["AnschriftHNr"]), ("Rechnungsweg", "7"))
        self.assertEqual((felder["AnschriftPLZ"], felder["AnschriftOrt"]), ("40210", "Düsseldorf"))
        self.assertIn("Objekt: Mehrfamilienhaus (6 Parteien), Im Knick 36, 47269 Duisburg", felder["Kartei"])
        self.assertTrue(any("Rechnungsadresse" in h for h in hinweise))
        # „Rechnungsadresse identisch? = Ja“ → wieder Objektadresse
        haupt.rechnung_abweichend = False
        self.s.commit()
        felder = self.felder(v)[0]
        self.assertEqual((felder["AnschriftStr"], felder["AnschriftHNr"]), ("Im Knick", "36"))


# --- (e) Terminierung: Testphase schreibt nur die Datei --------------------------------------------------

class E_Terminierung(Basis):
    def test_testphase_schreibt_datei_bucht_nicht_sendet_nicht(self):
        self.assertFalse(lead_v5.terminierung_aktiv(self.s))
        v = self.lead()
        seite = self.kartei(v)
        knopf = tag(seite, "lk-terminierung-knopf")
        self.assertIn('type="submit"', knopf)
        self.assertIn('data-taifun-testphase="1"', knopf)
        self.assertIn("Testphase: nur Übergabe an TAIFUN, keine Buchung, keine Mail", seite)
        with mock.patch.object(kalender, "termin_schreiben", side_effect=AssertionError("kein Outlook")), \
                mock.patch.object(kern, "mail_planen", side_effect=AssertionError("keine Mail")):
            r = self.client.post(f"/lead-management/lead/{v.id}/terminierung", data={"bestaetigung": "auto"})
        self.assertEqual(r.status_code, 303, r.text)
        self.assertIn("Testphase: nur Übergabe an TAIFUN, keine Buchung, keine Mail", meldung_aus(r))
        dateien = self.dateien(v)
        self.assertEqual(len(dateien), 1, dateien)
        self.assertRegex(dateien[0].name, rf"^LM_V{v.id}_\d{{8}}-\d{{6}}\.xml$")
        self.assertEqual(taifun_export.validieren(dateien[0].read_bytes()), [])
        v = self.frisch(v)
        self.assertEqual(v.taifun_export_status, "geschrieben")
        self.assertEqual(v.taifun_export_datei, dateien[0].name)
        self.assertEqual(v.taifun_export_von, 1)
        self.assertIsNone(v.lead_phase if v.lead_phase == "terminiert" else None)
        self.assertNotEqual(v.lead_phase, "terminiert")
        termin = self.s.query(VotTermin).filter_by(vorgang_id=v.id).one()
        self.assertEqual(termin.status, "vorgemerkt")
        # keine Termin-Mail (die Eingangsbestätigung stammt aus lead_anlegen)
        self.assertEqual(self.s.query(KommunikationLog).filter(
            KommunikationLog.vorgang_id == v.id, KommunikationLog.vorlage_key.like("termin%")).count(), 0)
        self.assertEqual(self.s.query(Benachrichtigung).filter(
            Benachrichtigung.link == f"/lead-management/lead/{v.id}").count(), 0)   # keine Glocke
        self.assertTrue(any(a.startswith("An TAIFUN übergeben: LM_") for a in self.aktivitaeten(v)))
        u = self.uebergaben(v)
        self.assertEqual((len(u), u[0].grund, u[0].status), (1, "terminierung", "geschrieben"))
        self.assertTrue((taifun_export.KOPIE_ORDNER / dateien[0].name).exists())   # Protokoll-Kopie
        seite = self.kartei(v)
        self.assertIn('data-rolle="taifun-badge"', seite)
        self.assertIn(f"TAIFUN {v.taifun_export_am.strftime('%d.%m.%Y')}", seite)
        self.assertIn("Erneut an TAIFUN übergeben", seite)
        # JSON-Variante
        v2 = self.lead()
        r = self.client.post(f"/lead-management/lead/{v2.id}/terminierung", json={"bestaetigung": "auto"},
                             headers={"accept": "application/json"})
        self.assertEqual(r.status_code, 200, r.text)
        self.assertTrue(r.json()["testphase"])
        self.assertTrue(r.json()["taifun"]["datei"].startswith(f"LM_V{v2.id}_"))

    def test_testphase_pflicht_offen_kein_export(self):
        v = self.lead()
        k = self.kunde(v)
        k.telefon = ""
        self.s.commit()
        r = self.client.post(f"/lead-management/lead/{v.id}/terminierung", data={"bestaetigung": "auto"})
        self.assertEqual(r.status_code, 303)
        self.assertIn("Telefon", meldung_aus(r))
        self.assertEqual(self.dateien(v), [])
        self.assertEqual(self.frisch(v).taifun_export_status, "")
        # Kanal „?“ sperrt den Export (Vertrag K)
        k = self.kunde(v)
        k.telefon = "0171 1234567"
        k.vertriebskanal = "?"
        self.s.commit()
        r = self.client.post(f"/lead-management/lead/{v.id}/terminierung", data={"bestaetigung": "auto"})
        self.assertEqual(r.status_code, 303)
        self.assertEqual(self.dateien(v), [])
        self.assertTrue(taifun_export.kanal_unklar(self.s, self.frisch(v)))

    def test_freigeschaltet_export_und_buchung(self):
        kern.parameter_setzen(self.s, "terminierung_aktiv", "an")
        self.s.commit()
        v = self.lead()
        with mock.patch.object(kalender, "termin_schreiben", return_value=False):
            r = self.client.post(f"/lead-management/lead/{v.id}/terminierung", data={"bestaetigung": "auto"})
        self.assertEqual(r.status_code, 303, r.text)
        meldung = meldung_aus(r)
        self.assertIn("An TAIFUN übergeben: LM_", meldung)
        self.assertEqual(len(self.dateien(v)), 1)
        v = self.frisch(v)
        self.assertEqual(v.lead_phase, "terminiert")
        self.assertEqual(self.s.query(VotTermin).filter_by(vorgang_id=v.id).one().status, "geplant")
        self.assertEqual(v.taifun_export_status, "geschrieben")


# --- (f) Ordner nicht beschreibbar → fehler, Label, Erneut ------------------------------------------------

class F_Fehler(Basis):
    def test_ordner_fehlt_label_zaehler_erneut(self):
        basis = taifun_export.fehler_anzahl(self.s)   # andere Tests dieser Klasse hinterlassen Fehler-Vorgänge
        v = self.lead()
        kaputt = self.ordner / "gibt-es-nicht" / "LM Datenimport"
        kern.parameter_setzen(self.s, "taifun_import_ordner", str(kaputt))
        self.s.commit()
        r = self.client.post(f"/lead-management/lead/{v.id}/taifun", data={})
        self.assertEqual(r.status_code, 303, r.text)
        self.assertIn("fehler=1", r.headers["location"])
        self.assertIn("TAIFUN-Übergabe fehlgeschlagen", meldung_aus(r))
        self.assertIn("SYSTEM", meldung_aus(r))   # Dienstkonto-Hinweis
        v = self.frisch(v)
        self.assertEqual(v.taifun_export_status, "fehler")
        self.assertIn("Ordner nicht gefunden", v.taifun_export_grund)
        self.assertEqual(self.dateien(v), [])
        self.assertEqual(taifun_export.fehler_anzahl(self.s), basis + 1)
        u = self.uebergaben(v)
        self.assertEqual((len(u), u[0].status, u[0].grund), (1, "fehler", "manuell"))
        self.assertTrue(any(a.startswith("TAIFUN-Übergabe fehlgeschlagen:") for a in self.aktivitaeten(v)))
        seite = self.kartei(v)
        self.assertIn('id="lm-taifun-hinweis"', seite)
        self.assertIn("TAIFUN-Übergabe fehlgeschlagen", seite)
        self.assertIn('data-rolle="taifun-erneut"', seite)
        self.assertNotIn('data-rolle="taifun-badge"', seite)
        board = self.client.get("/lead-management/hauptboard").text
        zeile = board.split(f'data-vorgang="{v.id}"', 1)[0].rsplit("<tr ", 1)[1] \
            + board.split(f'data-vorgang="{v.id}"', 1)[1].split("</tr>", 1)[0]
        self.assertIn("lm-rang0", zeile)
        self.assertIn("TAIFUN-Übergabe fehlgeschlagen", zeile)
        gruppe = board.split('data-gruppe="neu"', 1)[1].split("</details>", 1)[0]
        # Rang 0 steht oben – andere Fehler-/Mailfehler-Leads (Bestand, weitere Tests) stehen gleichberechtigt
        # davor: alle Zeilen VOR dem Testlead muessen ebenfalls Rang-0-Zeilen sein (Orchestrator 16.10.2026)
        ids = re.findall(r'data-vorgang="(\d+)"', gruppe)
        self.assertIn(str(v.id), ids)
        for vid in ids[:ids.index(str(v.id))]:
            zeile_vor = gruppe.split(f'data-vorgang="{vid}"', 1)[0].rsplit("<tr ", 1)[1] \
                + gruppe.split(f'data-vorgang="{vid}"', 1)[1].split("</tr>", 1)[0]
            self.assertIn("lm-rang0", zeile_vor, f"Zeile {vid} ohne Rang 0 vor dem Testlead")
        einst = self.client.get("/parametrierung/lead-einstellungen").text
        self.assertIn(f"{basis + 1} TAIFUN-Übergabe(n) mit Fehler", einst)
        # Reparatur: Ordner wieder erreichbar → „Erneut übergeben“ (bestaetigt=1) → Erfolg, Label weg
        kern.parameter_setzen(self.s, "taifun_import_ordner", str(self.ordner))
        self.s.commit()
        r = self.client.post(f"/lead-management/lead/{v.id}/taifun", data={"bestaetigt": "1"})
        self.assertEqual(r.status_code, 303, r.text)
        self.assertNotIn("fehler=1", r.headers["location"])
        v = self.frisch(v)
        self.assertEqual(v.taifun_export_status, "geschrieben")
        self.assertEqual(v.taifun_export_grund, "")
        self.assertEqual(len(self.dateien(v)), 1)
        self.assertEqual(taifun_export.fehler_anzahl(self.s), basis)
        seite = self.kartei(v)
        self.assertNotIn('id="lm-taifun-hinweis"', seite)
        self.assertIn('data-rolle="taifun-badge"', seite)
        self.assertEqual([u.status for u in self.uebergaben(v)], ["fehler", "geschrieben"])

    def test_keine_schreibrechte_und_validierung(self):
        v = self.lead()
        with mock.patch.object(taifun_export, "datei_schreiben", side_effect=PermissionError("verweigert")):
            ok, meldung, u = taifun_export.exportieren(self.s, v.id, 1, "manuell")
        self.assertFalse(ok)
        self.assertIn("Keine Schreibrechte", meldung)
        self.assertIn("FriondoAngebotstool", meldung)
        self.assertEqual(u.status, "fehler")
        self.assertEqual(self.frisch(v).taifun_export_status, "fehler")
        # Validierungsfehler verhindern das Schreiben
        with mock.patch.object(taifun_export, "validieren", return_value=["Zeile 5: kaputt"]):
            ok, meldung, u = taifun_export.exportieren(self.s, v.id, 1, "manuell")
        self.assertFalse(ok)
        self.assertIn("Validierung gegen ADRESSEN.xsd fehlgeschlagen", meldung)
        self.assertEqual(self.dateien(v), [])
        ok_, text = taifun_export.ordner_pruefen(str(self.ordner / "fehlt"))
        self.assertFalse(ok_)
        self.assertIn("SYSTEM", text)
        self.assertEqual(taifun_export.ordner_pruefen(str(self.ordner))[0], True)
        self.assertEqual(list(self.ordner.glob("LM_PRUEF_*")), [])   # Prüfdatei wieder entfernt


# --- (g) zweite Übergabe fragt nach, Dubletten-Hinweis --------------------------------------------------

class G_Rueckfrage(Basis):
    def test_zweite_uebergabe_fragt_nach(self):
        v = self.lead()
        self.assertEqual(taifun_export.rueckfrage_text(self.s, v, self.kunde(v)), "")
        r = self.client.post(f"/lead-management/lead/{v.id}/taifun", json={}, headers={"accept": "application/json"})
        self.assertEqual(r.status_code, 200, r.text)
        self.assertTrue(r.json()["datei"].startswith(f"LM_V{v.id}_"))
        # zweiter Klick ohne Bestätigung → 409 mit Rückfrage (Datum der letzten Übergabe)
        r = self.client.post(f"/lead-management/lead/{v.id}/taifun", json={}, headers={"accept": "application/json"})
        self.assertEqual(r.status_code, 409, r.text)
        self.assertIn("Erneut übergeben?", r.json()["rueckfrage"])
        self.assertIn(datetime.now().strftime("%d.%m.%Y"), r.json()["rueckfrage"])
        self.assertEqual(len(self.dateien(v)), 1)
        # Formular ohne JavaScript → Kartei mit Rückfrage-Balken „Trotzdem übergeben“
        r = self.client.post(f"/lead-management/lead/{v.id}/taifun", data={})
        self.assertEqual(r.status_code, 303)
        self.assertIn("taifun_rueckfrage=1", r.headers["location"])
        seite = self.client.get(r.headers["location"]).text
        self.assertIn('data-rolle="taifun-trotzdem"', seite)
        # Kartei-Knopf trägt die Rückfrage als confirm (tojson|forceescape)
        knopf = tag(self.kartei(v), "lk-taifun-knopf")
        self.assertIn("window.confirm(&#34;", knopf)   # forceescape: keine rohen Anführungszeichen im Attribut
        self.assertNotIn('confirm("', knopf)
        self.assertIn("bereits an TAIFUN übergeben", unquote_plus(knopf.encode("ascii", "backslashreplace").decode()
                                                                .replace("\\u00fc", "ü")))
        r = self.client.post(f"/lead-management/lead/{v.id}/taifun", json={"bestaetigt": 1},
                             headers={"accept": "application/json"})
        self.assertEqual(r.status_code, 200, r.text)
        self.assertEqual(len(self.dateien(v)), 2)
        self.assertEqual(len(self.uebergaben(v)), 2)
        # zweite Übergabe in derselben Sekunde → Laufnummer „-2“, nie überschrieben
        jetzt = datetime.now().replace(microsecond=0)
        name_1 = taifun_export.freier_dateiname(str(self.ordner), v, jetzt)
        (self.ordner / name_1).write_bytes(b"belegt")
        name_2 = taifun_export.freier_dateiname(str(self.ordner), v, jetzt)
        self.assertNotEqual(name_1, name_2)
        # Laufnummer „-2“ (bzw. höher, wenn die Exporte oben in derselben Sekunde lagen)
        self.assertRegex(name_2, r"-\d+\.xml$")
        self.assertRegex(name_2, r"^[A-Z0-9_\-]+\.xml$")
        (self.ordner / name_1).unlink()

    def test_dubletten_hinweis_angebotsnummer_kundennummer(self):
        v = self.lead()
        k = self.kunde(v)
        self.s.add(Angebot(nummer=f"V35T-{v.id}", kunde_id=k.id, vorgang_id=v.id, status="Versendet (extern)",
                           extern=True, taifun_nummer="AN123456", konfigurator_typ="WP"))
        self.s.commit()
        text = taifun_export.rueckfrage_text(self.s, v, k)
        self.assertIn("Kunde ist vermutlich schon in TAIFUN angelegt (TAIFUN-Angebot AN123456). Trotzdem übergeben?", text)
        r = self.client.post(f"/lead-management/lead/{v.id}/taifun", json={}, headers={"accept": "application/json"})
        self.assertEqual(r.status_code, 409)
        self.assertIn("AN123456", r.json()["rueckfrage"])
        # Terminierung überspringt den automatischen Export, Aktivität statt Datei
        r = self.client.post(f"/lead-management/lead/{v.id}/terminierung", data={"bestaetigung": "auto"})
        self.assertEqual(r.status_code, 303)   # Testphase: Formular → Redirect mit Meldung (JSON wäre 403)
        self.assertIn("übersprungen", meldung_aus(r))
        self.assertEqual(self.dateien(v), [])
        self.assertTrue(any("TAIFUN-Übergabe bei der Terminierung übersprungen" in a for a in self.aktivitaeten(v)))
        r = self.client.post(f"/lead-management/lead/{v.id}/terminierung", json={"bestaetigung": "auto"},
                             headers={"accept": "application/json"})
        self.assertEqual(r.status_code, 403)
        self.assertTrue(r.json()["testphase"])
        # Kundennummer (manuell nachgetragen, Autospeichern) als Beleg + im Badge
        r = self.client.post(f"/lead-management/lead/{v.id}/feld", json={"feld": "taifun_kundennr", "wert": " 10815 "})
        self.assertEqual(r.status_code, 200, r.text)
        self.assertEqual(r.json()["wert"], "10815")
        self.assertEqual(self.kunde(v).taifun_kundennr, "10815")
        self.assertIn("TAIFUN-Kundennummer 10815", taifun_export.dubletten_hinweis(self.s, v, self.kunde(v)))
        r = self.client.post(f"/lead-management/lead/{v.id}/taifun", json={"bestaetigt": "1"},
                             headers={"accept": "application/json"})
        self.assertEqual(r.status_code, 200, r.text)
        seite = self.kartei(v)
        self.assertIn("Nr. 10815", seite)
        self.assertIn('name="taifun_kundennr"', seite)


# --- (h) Scheduler: abgeholt --------------------------------------------------------------------------------

class H_Scheduler(Basis):
    def test_lauf_setzt_abgeholt(self):
        v = self.lead()
        ok, _m, u = taifun_export.exportieren(self.s, v.id, 1, "manuell")
        self.assertTrue(ok)
        datei = self.dateien(v)[0]
        ergebnis = taifun_export.abholung_pruefen()
        self.assertGreaterEqual(ergebnis["geprueft"], 1)
        self.assertEqual(self.uebergaben(v)[0].status, "geschrieben")   # Datei liegt noch
        datei.unlink()
        ergebnis = taifun_export.abholung_pruefen()
        self.assertGreaterEqual(ergebnis["abgeholt"], 1)
        u = self.uebergaben(v)[0]
        self.assertEqual(u.status, "abgeholt")
        self.assertIsNotNone(u.abgeholt_am)
        self.assertEqual(self.frisch(v).taifun_export_status, "abgeholt")
        self.assertIn("TAIFUN", self.kartei(v).split('data-rolle="taifun-badge"', 1)[1][:200])
        # nicht erreichbarer Ordner markiert nichts
        v2 = self.lead()
        taifun_export.exportieren(self.s, v2.id, 1, "manuell")
        u2 = self.uebergaben(v2)[0]
        u2.pfad = str(self.ordner / "weg" / u2.datei)
        self.s.commit()
        ergebnis = taifun_export.abholung_pruefen()
        self.assertIn(str(self.ordner / "weg"), ergebnis["ordner_fehlt"])
        self.assertEqual(self.uebergaben(v2)[0].status, "geschrieben")
        # Lauf registriert (900 s) und über den Scheduler ausführbar
        taifun_export.scheduler_starten()
        lauf = scheduler.holen("taifun-uebergaben")
        self.assertIsNotNone(lauf)
        self.assertEqual(lauf.intervall_s, 900)
        ergebnis = scheduler.ausfuehren("taifun-uebergaben", ausloeser="manuell")
        self.assertTrue(ergebnis["ok"], ergebnis)
        self.assertIn("abgeholt", ergebnis["ergebnis"])
        # „Als importiert markieren“ über die Übergabeliste
        r = self.client.post(f"/lead-management/taifun-uebergaben/{u2.id}/importiert", data={})
        self.assertEqual(r.status_code, 303)
        self.assertEqual(self.uebergaben(v2)[0].status, "importiert")
        self.assertEqual(self.frisch(v2).taifun_export_status, "importiert")
        liste = self.client.get("/lead-management/taifun-uebergaben?status=importiert").text
        self.assertIn(u2.datei, liste)
        self.assertIn("manuell importiert", liste)
        # XML-Download der Kopie
        r = self.client.get(f"/lead-management/lead/{v2.id}/taifun/{u2.id}/xml")
        self.assertEqual(r.status_code, 200)
        self.assertIn("application/xml", r.headers["content-type"])
        self.assertIn(b"<TAIFUN:Ad>", r.content)


# --- (i) Kürzung > 60 Zeichen ------------------------------------------------------------------------------

class I_Kuerzung(Basis):
    def test_laengen_gekuerzt_und_vermerkt(self):
        lang = "Schliwa-" + "x" * 70
        v = self.lead(nachname=lang, strasse=("Sehr lange Straße " * 4).strip() + " 12")
        felder, hinweise, xml = self.felder(v)
        self.assertEqual(len(felder["Name3"]), 60)
        self.assertEqual(len(felder["AnschriftStr"]), 60)
        self.assertEqual(felder["AnschriftHNr"], "12")
        self.assertTrue(any(h.startswith("Name auf 60 Zeichen gekürzt") for h in hinweise))
        self.assertTrue(any(h.startswith("Straße auf 60 Zeichen gekürzt") for h in hinweise))
        self.assertIn("Hinweis: Name auf 60 Zeichen gekürzt", felder["Kartei"])
        self.assertEqual(taifun_export.validieren(xml), [])
        ok, meldung, _u = taifun_export.exportieren(self.s, v.id, 1, "manuell")
        self.assertTrue(ok, meldung)
        self.assertIn("2 Hinweise in der Karteikarte", meldung)
        self.assertTrue(any("Name auf 60 Zeichen gekürzt" in a for a in self.aktivitaeten(v)))


# --- (j) Schalter aus (Standard) --------------------------------------------------------------------------

class J_SchalterAus(Basis):
    def test_standard_aus_kein_export_testdatei_geht(self):
        self.assertEqual(kern.PARAMETER_START["taifun_export_aktiv"], "aus")
        self.assertEqual(taifun_export.PARAMETER["taifun_export_aktiv"], "aus")
        kern.parameter_setzen(self.s, "taifun_export_aktiv", "aus")
        self.s.commit()
        self.assertFalse(taifun_export.aktiv(self.s))
        v = self.lead()
        seite = self.kartei(v)
        self.assertIn("disabled", tag(seite, "lk-taifun-knopf"))
        self.assertIn("nicht aktiv", seite)
        terminierung = tag(seite, "lk-terminierung-knopf")
        self.assertIn('data-testphase="1"', terminierung)
        self.assertIn("disabled", terminierung)
        self.assertNotIn('data-taifun-testphase="1"', seite)   # Testphase-Knopf wie v31 ausgegraut
        r = self.client.post(f"/lead-management/lead/{v.id}/taifun", json={}, headers={"accept": "application/json"})
        self.assertEqual(r.status_code, 409, r.text)
        self.assertIn("nicht aktiv", r.json()["meldung"])
        r = self.client.post(f"/lead-management/lead/{v.id}/terminierung", data={"bestaetigung": "auto"})
        self.assertEqual(r.status_code, 303)
        self.assertIn(lead_v5.TESTPHASE_HINWEIS, meldung_aus(r))
        self.assertEqual(self.dateien(v), [])
        self.assertEqual(self.frisch(v).taifun_export_status, "")
        self.assertIn("TAIFUN-Übergabe nicht aktiv (Parameter taifun_export_aktiv)", self.aktivitaeten(v))
        self.assertEqual(self.uebergaben(v), [])
        # Testdatei schreiben funktioniert immer (Admin, Lead-Einstellungen)
        vorher = len(list(self.ordner.glob("LM_TEST_*.xml")))
        r = self.client.post("/lead-management/taifun/testdatei", data={})
        self.assertEqual(r.status_code, 303, r.text)
        self.assertIn("Testdatei LM_TEST_", meldung_aus(r))
        self.assertEqual(r.headers["location"].split("?")[0], "/parametrierung/lead-einstellungen")
        tests = sorted(self.ordner.glob("LM_TEST_*.xml"))
        self.assertEqual(len(tests), vorher + 1)
        xml = tests[-1].read_bytes()
        self.assertEqual(taifun_export.validieren(xml), [])
        felder = ad_elemente(xml)
        self.assertEqual(felder["Name3"], "Max Mustermann")
        self.assertIn("TESTDATEI", felder["Kartei"])
        eintrag = self.s.query(TaifunUebergabe).filter_by(datei=tests[-1].name).one()
        self.assertEqual((eintrag.vorgang_id, eintrag.grund, eintrag.status), (0, "testdatei", "geschrieben"))
        liste = self.client.get("/lead-management/taifun-uebergaben").text
        self.assertIn("Testdatei", liste)
        self.assertIn(tests[-1].name, liste)


# --- weitere: Rechte, Einstellungen, Boards, Migration, Wächter ---------------------------------------------

class K_Rechte(Basis):
    def test_aussendienst_darf_nicht_uebergeben(self):
        v = self.lead()
        ad_client = TestClient(app, follow_redirects=False)
        ad_client.cookies.set(auth.COOKIE_NAME, auth.cookie_wert(self.ad.id))
        seite = ad_client.get(f"/lead-management/lead/{v.id}").text
        self.assertNotIn('id="lk-taifun-knopf"', seite)
        r = ad_client.post(f"/lead-management/lead/{v.id}/taifun", json={}, headers={"accept": "application/json"})
        self.assertIn(r.status_code, (403, 404))
        self.assertEqual(self.dateien(v), [])
        r = ad_client.get("/lead-management/taifun-uebergaben")
        self.assertIn(r.status_code, (303, 404))
        r = ad_client.post("/lead-management/taifun/testdatei", data={})
        self.assertIn(r.status_code, (303, 404))
        # Leadmanagerin (Innendienst) darf
        lm_client = TestClient(app, follow_redirects=False)
        lm_client.cookies.set(auth.COOKIE_NAME, auth.cookie_wert(self.lm.id))
        self.assertIn('id="lk-taifun-knopf"', lm_client.get(f"/lead-management/lead/{v.id}").text)
        r = lm_client.post(f"/lead-management/lead/{v.id}/taifun", json={}, headers={"accept": "application/json"})
        self.assertEqual(r.status_code, 200, r.text)
        self.assertEqual(self.frisch(v).taifun_export_von, self.lm.id)
        self.assertEqual(lm_client.get("/lead-management/taifun-uebergaben").status_code, 200)


class L_Einstellungen(Basis):
    def test_abschnitt_speichern_ordner_pruefen(self):
        seite = self.client.get("/parametrierung/lead-einstellungen").text
        self.assertIn('id="taifun-uebergabe"', seite)
        self.assertIn('name="taifun_export_aktiv"', seite)
        self.assertIn('name="taifun_import_ordner"', seite)
        self.assertIn('name="taifun_export_encoding"', seite)
        self.assertIn("Testdatei schreiben", seite)
        self.assertIn("Ordner prüfen", seite)
        self.assertIn("FriondoAngebotstool", seite)
        self.assertIn("Ordner erreichbar", seite)
        neu = self.ordner / "neu"
        neu.mkdir(exist_ok=True)
        form = {"taifun_dabei": "1", "taifun_export_aktiv": "aus", "taifun_import_ordner": str(neu),
                "taifun_export_encoding": "utf-8", "taifun_testdatei_ok": "1", "taifun_encoding_ok": "1",
                "terminierung_aktiv": "aus", "mail_versand_aktiv": "aus"}
        r = self.client.post("/parametrierung/lead-einstellungen", data=form)
        self.assertEqual(r.status_code, 303, r.text)
        self.assertIn("Ordner erreichbar und beschreibbar", meldung_aus(r))
        self.s.expire_all()
        self.assertFalse(taifun_export.aktiv(self.s))
        self.assertEqual(taifun_export.import_ordner(self.s), str(neu))
        self.assertEqual(taifun_export.encoding(self.s), "utf-8")
        self.assertTrue(taifun_export.haekchen(self.s, "taifun_testdatei_ok"))
        self.assertTrue(taifun_export.haekchen(self.s, "taifun_encoding_ok"))
        self.assertTrue(kern.parameter_holen(self.s, "taifun_ordner_geprueft", "").startswith("ok"))
        self.assertIn("taifun_export_aktiv an → aus", kern.parameter_holen(self.s, "einstellungs_protokoll", ""))
        kontext = taifun_export.einstellungen_kontext(self.s)
        self.assertTrue(all(p["ok"] for p in kontext["pruefpunkte"]))
        # „Ordner prüfen“ mit nicht erreichbarem Ordner → Prüfpunkt rot
        r = self.client.post("/lead-management/taifun/ordner-pruefen", data={"taifun_import_ordner": str(neu / "fehlt")})
        self.assertEqual(r.status_code, 303)
        self.assertIn("fehler=1", r.headers["location"])
        self.s.expire_all()
        self.assertTrue(kern.parameter_holen(self.s, "taifun_ordner_geprueft", "").startswith("fehler"))
        self.assertFalse(taifun_export.einstellungen_kontext(self.s)["pruefpunkte"][0]["ok"])


class M_Boards(Basis):
    def test_spalte_und_filterchip(self):
        from app import lead_boards
        self.assertIn(("taifun", "TAIFUN-Übergabe", False), lead_boards.SPALTEN)
        v = self.lead()
        v2 = self.lead()
        taifun_export.exportieren(self.s, v.id, 1, "manuell")
        board = self.client.get("/lead-management/hauptboard?taifun=1").text
        self.assertIn(f'data-vorgang="{v.id}"', board)
        self.assertNotIn(f'data-vorgang="{v2.id}"', board)
        self.assertIn('name="taifun"', board)
        f = lead_boards.filter_aus_query({"taifun": "1"})
        self.assertTrue(f["taifun"])
        daten = lead_boards.board_zeilen(self.s, self.admin, "hauptboard", {"ids": [v.id], "taifun": True})
        zeile = daten["gruppen"][0]["zeilen"][0]
        self.assertEqual(zeile["taifun_status"], "geschrieben")
        self.assertIn("An TAIFUN übergeben am", zeile["taifun_text"])
        self.assertEqual(lead_boards.mail_labels(self.frisch(v)), [])
        v.taifun_export_status = "fehler"
        v.taifun_export_grund = "Ordner weg (Test)"
        self.s.commit()
        self.assertEqual(lead_boards.mail_labels(self.frisch(v)), ["TAIFUN-Übergabe fehlgeschlagen"])
        self.assertEqual(lead_boards.label_titel(self.frisch(v))["TAIFUN-Übergabe fehlgeschlagen"], "Ordner weg (Test)")
        # Spalte einblenden → Zelle sp-taifun mit rotem Badge
        r = self.client.post("/lead-management/boards/spalten",
                             json={"board": "hauptboard", "spalten": [{"key": "taifun", "sichtbar": True}]})
        self.assertIn(r.status_code, (200, 303))
        board = self.client.get("/lead-management/hauptboard").text
        zeile = board.split(f'data-vorgang="{v.id}"', 1)[1].split("</tr>", 1)[0]
        if 'class="sp-taifun"' in zeile:
            self.assertIn("TAIFUN-Übergabe fehlgeschlagen", zeile.split('class="sp-taifun"', 1)[1].split("</td>", 1)[0])
        self.client.post("/lead-management/boards/spalten", json={"board": "hauptboard", "zuruecksetzen": True})


class N_Migration(Basis):
    def test_migration_idempotent(self):
        gesichert = {z.name: z.wert for z in self.s.query(LeadParameter)
                     .filter(LeadParameter.name.in_(tuple(taifun_export.PARAMETER)))}
        self.s.query(LeadParameter).filter(LeadParameter.name.in_(tuple(taifun_export.PARAMETER))).delete(
            synchronize_session=False)
        self.s.commit()
        try:
            meldungen = taifun_export.migration_v35_taifun(self.s)
            self.s.commit()
            self.assertEqual(len(meldungen), len(taifun_export.PARAMETER))
            self.assertIn("v35: Parameter taifun_export_aktiv = aus angelegt", meldungen)
            self.assertEqual(taifun_export.migration_v35_taifun(self.s), [])
            self.assertFalse(taifun_export.aktiv(self.s))
            self.assertEqual(taifun_export.import_ordner(self.s), r"C:\Users\kdadmin\Desktop\LM Datenimport")
        finally:
            for name, wert in gesichert.items():
                kern.parameter_setzen(self.s, name, wert)
            self.s.commit()
        self.assertTrue(taifun_export.KOPIE_ORDNER.is_dir())


class O_Waechter(unittest.TestCase):
    def test_dateiio_nach_freigabe_und_def_routen(self):
        quelle = (PROJEKT / "app" / "taifun_export.py").read_text(encoding="utf-8")
        for funktion in ("def exportieren", "def testdatei_schreiben"):
            rumpf = quelle.split(funktion, 1)[1].split("\ndef ", 1)[0]
            self.assertLess(rumpf.index("verbindung_freigeben(session)"), rumpf.index("datei_schreiben("), funktion)
        router = (PROJEKT / "app" / "routers" / "lm_taifun.py").read_text(encoding="utf-8")
        self.assertNotIn("async def", router)
        self.assertNotIn("await ", router)
        self.assertLess(router.index("verbindung_freigeben(session)\n    ok, text = taifun_export.ordner_pruefen"),
                        router.index("taifun_export.ordner_pruefung_speichern"))
        css = (PROJEKT / "app" / "static" / "lm_v35_t.css").read_text(encoding="utf-8")
        self.assertNotRegex(css, r"#[0-9a-fA-F]{3,6}\b")   # nur Tokens
        kartei = (PROJEKT / "app" / "templates" / "leadmanagement" / "kartei.html").read_text(encoding="utf-8")
        self.assertIn("taifun.rueckfrage | tojson | forceescape", kartei)
        self.assertIn("leadmanagement/_taifun_hinweis.html", kartei)
        self.assertTrue((PROJEKT / "docs" / "taifun" / "beispiel_LM.xml").exists())
        self.assertEqual(taifun_export.validieren((PROJEKT / "docs" / "taifun" / "beispiel_LM.xml").read_bytes()), [])
        self.assertTrue((PROJEKT / "docs" / "taifun-kundenexport.md").exists())


if __name__ == "__main__":
    unittest.main()
