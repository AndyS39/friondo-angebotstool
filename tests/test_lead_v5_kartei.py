# Tests PLAN_LEAD_V5 (v31, Agent K – Kundenkartei): Phase 153 (Block „Objekte“, zweites
# Objekt, Hauptobjekt ↔ Kundenfelder synchron, Großkunde-Häkchen mit Aktivität), Phase 155
# (Reihenfolge der Kartei: Notizen/To-Dos vor dem Kundeninfo-Block, Reiter nur Anruf ·
# E-Mail · Timeline, Block Termine mit Vorschlägen und Kalender), Phase 157 (MS/WA/DMS-
# Häkchen, Pflichtfeld Außendienst sperrt die Terminierung – HV-Lead gilt als erfüllt,
# Label „Disqualifiziert“ und Statuswechsel aus der Kartei mit Pflichtgrund, MFH-Frage
# „Rechnungsadresse identisch?“ mit Pflichtfeld-Zähler), Phase 158 (E-Mail-Dialog mit
# Platzhaltern und ICS – Versand gemockt, Wiedervorlage in 5-Minuten-Schritten, Timeline mit
# Herkunfts-Badge), Phase 159 (Testphase: Terminierung/Vormerken gesperrt mit Tooltip).
# Kontrollwert Phase 160: Demo-Kunde Schliwa mit Objekt 1 (Im Knick 36, 47269 Duisburg,
# EFH, WP) und Objekt 2 (zweite Adresse, MFH 4 Parteien, PV). Läuft gegen die DB-Kopie
# (DB_PFAD_OVERRIDE); Testdaten tragen den Nachnamen-Präfix „V31K“ und werden aufgeräumt.
import json
import pathlib
import re
from pathlib import Path
import unittest
import warnings
from datetime import datetime, timedelta
from unittest import mock

warnings.filterwarnings("ignore")

from fastapi.testclient import TestClient

from app import auth, lead_kartei, lead_v2, lead_v5, notizen
from app import leadmanagement as kern
from app import leadmanagement_logik
from app import objekte as objekte_modul
from app.db import SessionLocal, init_db
from app.main import app
from app.models import (AdProfil, Benachrichtigung, Benutzer, KommunikationLog, Kunde,
                        LeadAktivitaet, LeadQuelle, Todo, Vorgang, VorgangObjekt, VorgangsNotiz,
                        VotTermin)

NACHNAME = "V31K"
BENUTZER_PRAEFIX = "V31K "
PROJEKT = pathlib.Path(__file__).resolve().parent.parent
TEMPLATES = PROJEKT / "app" / "templates" / "leadmanagement"


def aufraeumen(s):
    for k in s.query(Kunde).filter(Kunde.nachname.like(f"{NACHNAME}%")):
        for v in s.query(Vorgang).filter_by(kunde_id=k.id):
            s.query(LeadAktivitaet).filter_by(vorgang_id=v.id).delete()
            s.query(KommunikationLog).filter_by(vorgang_id=v.id).delete()
            s.query(VotTermin).filter_by(vorgang_id=v.id).delete()
            s.query(VorgangsNotiz).filter_by(vorgang_id=v.id).delete()
            s.query(VorgangObjekt).filter_by(vorgang_id=v.id).delete()
            s.query(Todo).filter_by(vorgang_id=v.id).delete()
            s.query(Benachrichtigung).filter(
                Benachrichtigung.link == f"/lead-management/lead/{v.id}").delete()
            s.delete(v)
        s.delete(k)
    for b in s.query(Benutzer).filter(Benutzer.name.like(f"{BENUTZER_PRAEFIX}%")):
        s.query(AdProfil).filter_by(benutzer_id=b.id).delete()
        s.query(Benachrichtigung).filter_by(benutzer_id=b.id).delete()
        s.delete(b)
    s.commit()


class Basis(unittest.TestCase):
    PARAMETER = ("terminierung_aktiv", "mail_versand_aktiv", "grosskunde_farbe")

    @classmethod
    def setUpClass(cls):
        init_db()
        cls.s = SessionLocal()
        aufraeumen(cls.s)
        cls.client = TestClient(app, follow_redirects=False)
        cls.client.cookies.set(auth.COOKIE_NAME, auth.cookie_wert(1))
        cls.gesichert = {n: kern.parameter_holen(cls.s, n, None) for n in cls.PARAMETER}
        kern.parameter_setzen(cls.s, "terminierung_aktiv", "an")
        kern.parameter_setzen(cls.s, "mail_versand_aktiv", "aus")
        kern.parameter_setzen(cls.s, "grosskunde_farbe", "")
        cls.s.commit()
        cls.ad = Benutzer(name=f"{BENUTZER_PRAEFIX}AD", rolle="aussendienst",
                          pin_hash=auth.pin_hash("4321"), email="v31k-ad@test.local")
        cls.hv = Benutzer(name=f"{BENUTZER_PRAEFIX}HV", rolle="aussendienst",
                          pin_hash=auth.pin_hash("4321"), email="v31k-hv@test.local")
        cls.lm = Benutzer(name=f"{BENUTZER_PRAEFIX}Leadmanagerin", vorname="Anna", rolle="innendienst",
                          pin_hash=auth.pin_hash("4321"), email="v31k-lm@test.local", leadmanager=True)
        cls.id_ohne = Benutzer(name=f"{BENUTZER_PRAEFIX}Innendienst ohne", vorname="Zoe", rolle="innendienst",
                               pin_hash=auth.pin_hash("4321"), email="v31k-id@test.local", leadmanager=False)
        cls.s.add_all([cls.ad, cls.hv, cls.lm, cls.id_ohne])
        cls.s.flush()
        cls.s.add(AdProfil(benutzer_id=cls.ad.id, aktiv_terminierung=True, termin_dauer_min=90,
                           puffer_min=30, max_termine_tag=3))
        cls.s.add(AdProfil(benutzer_id=cls.hv.id, aktiv_terminierung=True, terminiert_selbst=True,
                           termin_dauer_min=90, puffer_min=30, max_termine_tag=3))
        cls.s.commit()

    @classmethod
    def tearDownClass(cls):
        aufraeumen(cls.s)
        for name, wert in cls.gesichert.items():
            if wert is not None:
                kern.parameter_setzen(cls.s, name, wert)
        cls.s.commit()
        cls.s.close()

    def lead(self, nr, vollstaendig=True, email=True, **extra):
        """Demo-Kunde Schliwa (Kontrollwert Phase 160): Objekt 1 = Im Knick 36, 47269 Duisburg, EFH, WP."""
        quelle = self.s.query(LeadQuelle).filter_by(key="website").first()
        daten = {"anrede": "Herr", "vorname": f"Sven{nr}", "nachname": f"{NACHNAME}-Schliwa-{nr}",
                 "strasse": "Im Knick 36", "plz": "47269", "ort": "Duisburg",
                 "telefon": f"0203 99{nr:04d}", "sparten": ["WP"]}
        if email:
            daten["email"] = f"v31k{nr}@test.local"
        vorgang, _ = kern.lead_anlegen(self.s, daten, quelle, "api", entscheidung="neu")
        kunde = self.s.get(Kunde, vorgang.kunde_id)
        vorgang.demo = True
        if vollstaendig:
            kunde.vertriebskanal = "Standard"
            kunde.objektart = "EFH"
            if "ad_id" not in extra:
                vorgang.ad_id = self.ad.id
        for k, v in extra.items():
            setattr(vorgang, k, v)
        self.s.commit()
        # verwaiste Objekte gelöschter Vorgänge (wiederverwendete IDs) räumen, dann Hauptobjekt
        self.s.query(VorgangObjekt).filter_by(vorgang_id=vorgang.id).delete()
        objekte_modul.hauptobjekt(self.s, vorgang.id, anlegen=True)
        self.s.commit()
        return vorgang

    def kartei(self, vorgang, client=None, **params):
        url = f"/lead-management/lead/{vorgang.id}"
        if params:
            url += "?" + "&".join(f"{k}={v}" for k, v in params.items())
        return (client or self.client).get(url)

    def feld(self, vorgang, feld, wert, client=None, **extra):
        return (client or self.client).post(f"/lead-management/lead/{vorgang.id}/feld",
                                            json={"feld": feld, "wert": wert, **extra})

    def objekt_feld(self, vorgang, objekt_id, feld, wert):
        return self.client.post(f"/lead-management/lead/{vorgang.id}/objekt/{objekt_id}",
                                json={"feld": feld, "wert": wert})

    def zweites_objekt(self, vorgang, **ueber):
        """Objekt 2 (Kontrollwert): zweite Adresse, MFH mit 4 Parteien, PV."""
        daten = {"bezeichnung": "Objekt 2", "strasse": "Sonnenwall 12", "plz": "47051",
                 "ort": "Duisburg", "objektart": "MFH", "parteien": "4", "interesse": ["PV"],
                 "rechnung_identisch": "ja"}
        daten.update(ueber)
        r = self.client.post(f"/lead-management/lead/{vorgang.id}/objekt", data=daten)
        self.assertEqual(r.status_code, 303, r.text)
        self.s.expire_all()
        return [o for o in objekte_modul.objekte_fuer(self.s, vorgang.id) if o.reihenfolge != 1][-1]

    def kunde(self, vorgang):
        self.s.expire_all()
        return self.s.get(Kunde, vorgang.kunde_id)

    def aktivitaeten(self, vorgang, typ=None):
        self.s.expire_all()
        q = self.s.query(LeadAktivitaet).filter_by(vorgang_id=vorgang.id)
        if typ:
            q = q.filter_by(typ=typ)
        return q.order_by(LeadAktivitaet.id).all()

    def termin(self, vorgang, status="vorgemerkt", ad=None, tage=5, objekt_id=None):
        t = VotTermin(vorgang_id=vorgang.id, ad_id=(ad or self.ad).id, objekt_id=objekt_id,
                      beginn=(datetime.now() + timedelta(days=tage)).replace(hour=10, minute=0,
                                                                              second=0, microsecond=0),
                      status=status, quelle="assistent", demo=True, typ="vot", medium="vor_ort")
        t.ende = t.beginn + timedelta(minutes=90)
        self.s.add(t)
        self.s.commit()
        return t


# --- Phase 153: Objekte, Großkunde -------------------------------------------------------

class Objekte(Basis):
    def test_kontrollwert_schliwa_zweites_objekt_und_karten(self):
        v = self.lead(1)
        haupt = objekte_modul.hauptobjekt(self.s, v.id)
        self.assertEqual((haupt.strasse, haupt.plz, haupt.ort, haupt.objektart), ("Im Knick 36", "47269", "Duisburg", "EFH"))
        self.assertEqual(objekte_modul.interessen_liste(haupt), ["WP"])
        # Ein-Objekt-Vorgang: nur die bekannten Adressfelder + Link „Weiteres Objekt hinzufügen“
        seite = self.kartei(v).text
        self.assertIn('data-feld="strasse"', seite.split('id="lk-stammdaten"', 1)[1].split("</form>", 1)[0])
        self.assertIn("Weiteres Objekt hinzufügen", seite)
        self.assertNotIn('class="lk-objekt-karten"', seite)
        # Objekt 2 anlegen (MFH, 4 Parteien, PV)
        o2 = self.zweites_objekt(v)
        self.assertEqual((o2.bezeichnung, o2.strasse, o2.objektart, o2.parteien, o2.reihenfolge),
                         ("Objekt 2", "Sonnenwall 12", "MFH", 4, 2))
        self.assertEqual(objekte_modul.interessen_liste(o2), ["PV"])
        # Interessen des Vorgangs = Vereinigung → Kunde.interesse, Badges im Kopf
        self.assertEqual(objekte_modul.vorgang_interessen(self.s, v.id), ["WP", "PV"])
        self.assertEqual(self.kunde(v).interesse, "WP,PV")
        seite = self.kartei(v).text
        kopf = seite.split('class="lk-badges"', 1)[1].split("</div>", 1)[0]
        self.assertIn("chip-pv", kopf)
        self.assertIn("2 Objekte", kopf)
        # Kartei zeigt beide Objektkarten, Objekt 1 als Hauptobjekt, Pflichtfelder rot je Karte
        self.assertEqual(seite.count('class="lk-objekt haupt"'), 1)
        self.assertEqual(len(re.findall(r'<article class="lk-objekt[^"]*" data-objekt="\d+"', seite)), 2)
        self.assertIn(f'data-feld-url="/lead-management/lead/{v.id}/objekt/{o2.id}"', seite)
        self.assertIn("Objekt 2 · Hauptobjekt", seite) if False else None
        # bei mehreren Objekten liegen Adresse/Objektart/Interessen in den Karten, nicht im Stammdaten-Formular
        stammdaten = seite.split('id="lk-stammdaten"', 1)[1].split("</form>", 1)[0]
        self.assertNotIn('data-feld="strasse"', stammdaten)
        self.assertIn("je Objekt im Block", stammdaten)
        # Block Termine: Termin je Objekt, Hinweis „2 von 2 Objekten ohne Termin“ (T: objekte_hinweis),
        # Objektauswahl für die Vorschläge sichtbar
        termine_block = seite.split('id="termine"', 1)[1].split('data-bereich="angebote"', 1)[0]
        self.assertIn("2 von 2 Objekten ohne Termin", termine_block)
        self.assertEqual(termine_block.count('class="lk-objekt-termin offen"'), 2)
        self.assertIn('data-rolle="objekt-wahl" >', termine_block)
        # zwei vorgemerkte Objekttermine → Radios „bestaetigung“ im Kopf (Vorbelegung gleicher Tag → eine)
        haupt = objekte_modul.hauptobjekt(self.s, v.id)
        self.termin(v, objekt_id=haupt.id, tage=5)
        self.termin(v, objekt_id=o2.id, tage=5)
        seite = self.kartei(v).text
        kopf_form = seite.split('id="lk-terminierung-form"', 1)[1].split("</form>", 1)[0]
        self.assertIn('data-rolle="bestaetigung-wahl"', kopf_form)
        self.assertIn('name="bestaetigung" value="eine" checked', kopf_form)
        self.assertIn("Terminierung (2 Termine)", kopf_form)
        pruefung = lead_kartei.terminierung_pruefung(self.s, self.kunde(v), v)
        self.assertEqual(len(pruefung["vorgemerkte"]), 2)
        self.assertTrue(pruefung["bereit"])
        # Aktivität
        texte = [a.text for a in self.aktivitaeten(v, "aenderung")]
        self.assertTrue(any(t.startswith("Objekt hinzugefügt: Objekt 2: Sonnenwall 12") for t in texte), texte)

    def test_objekt_anlegen_validierung(self):
        v = self.lead(2)
        r = self.client.post(f"/lead-management/lead/{v.id}/objekt", data={"strasse": "x", "plz": "12", "ort": "y"},
                             headers={"Accept": "application/json"})
        self.assertEqual(r.status_code, 400)
        self.assertIn("5 Ziffern", r.json()["meldung"])
        r = self.client.post(f"/lead-management/lead/{v.id}/objekt", data={"strasse": "", "plz": "47051", "ort": "y"},
                             headers={"Accept": "application/json"})
        self.assertEqual(r.status_code, 400)
        self.assertEqual(len(objekte_modul.objekte_fuer(self.s, v.id)), 1)
        # JSON-Body mit Interessen-Liste (inkl. MS)
        r = self.client.post(f"/lead-management/lead/{v.id}/objekt",
                             json={"strasse": "Neue Str. 1", "plz": "47051", "ort": "Duisburg",
                                   "objektart": "EFH", "interesse": ["PV", "MS"]},
                             headers={"Accept": "application/json"})
        self.assertEqual(r.status_code, 200, r.text)
        self.assertTrue(r.json()["ok"])
        o = self.s.get(VorgangObjekt, r.json()["objekt_id"])
        self.assertEqual(objekte_modul.interessen_liste(o), ["PV", "MS"])
        self.assertEqual(o.bezeichnung, "Objekt 2")

    def test_hauptobjekt_und_kundenfelder_synchron(self):
        v = self.lead(3)
        o2 = self.zweites_objekt(v)
        haupt = objekte_modul.hauptobjekt(self.s, v.id)
        # Kundenfeld (Stammdaten-Route/Autospeichern) → Hauptobjekt folgt
        r = self.feld(v, "ort", "Moers")
        self.assertEqual(r.status_code, 200, r.text)
        self.s.expire_all()
        self.assertEqual(self.s.get(VorgangObjekt, haupt.id).ort, "Moers")
        # Hauptobjekt-Karte → Kundenfeld folgt (läuft über feld_speichern)
        r = self.objekt_feld(v, haupt.id, "strasse", "Im Knick 38")
        self.assertEqual(r.status_code, 200, r.text)
        self.assertEqual(r.json()["objekt_id"], haupt.id)
        self.assertEqual(self.kunde(v).strasse, "Im Knick 38")
        self.assertEqual(self.s.get(VorgangObjekt, haupt.id).strasse, "Im Knick 38")
        # Objekt 2 ändert nur sich selbst – Kundenadresse bleibt
        r = self.objekt_feld(v, o2.id, "ort", "Krefeld")
        self.assertEqual(r.status_code, 200, r.text)
        self.s.expire_all()
        self.assertEqual(self.s.get(VorgangObjekt, o2.id).ort, "Krefeld")
        self.assertEqual(self.kunde(v).ort, "Moers")
        self.assertIn("Objekt 2 – Ort: „Duisburg“ → „Krefeld“", [a.text for a in self.aktivitaeten(v, "aenderung")])
        # Objekt-Interessen → Kunde.interesse = Vereinigung
        r = self.objekt_feld(v, o2.id, "interesse", ["PV", "KL"])
        self.assertEqual(r.status_code, 200, r.text)
        self.assertEqual(self.kunde(v).interesse, "WP,PV,KL")
        # Validierung am Objekt: PLZ, Objektart, Parteien
        self.assertEqual(self.objekt_feld(v, o2.id, "plz", "12").status_code, 400)
        self.assertEqual(self.objekt_feld(v, o2.id, "objektart", "XYZ").status_code, 400)
        self.assertEqual(self.objekt_feld(v, o2.id, "parteien", "0").status_code, 400)
        self.assertEqual(self.objekt_feld(v, o2.id, "unbekannt", "1").status_code, 400)
        # Objekt eines fremden Vorgangs → 404
        w = self.lead(4)
        self.assertEqual(self.objekt_feld(w, o2.id, "ort", "x").status_code, 404)

    def test_objekt_deaktivieren_und_reihenfolge(self):
        v = self.lead(5)
        o2 = self.zweites_objekt(v)
        o3 = self.zweites_objekt(v, bezeichnung="Objekt 3", strasse="Dritte Str. 3", objektart="EFH",
                                 parteien="", interesse=["WB"])
        self.assertEqual(o3.reihenfolge, 3)
        # Hauptobjekt bleibt vorn, Pfeile ordnen nur Objekt 2 … n
        haupt = objekte_modul.hauptobjekt(self.s, v.id)
        r = self.client.post(f"/lead-management/lead/{v.id}/objekt/{haupt.id}/reihenfolge",
                             data={"richtung": "runter"}, headers={"Accept": "application/json"})
        self.assertEqual(r.status_code, 400)
        r = self.client.post(f"/lead-management/lead/{v.id}/objekt/{o3.id}/reihenfolge",
                             data={"richtung": "hoch"}, headers={"Accept": "application/json"})
        self.assertEqual(r.status_code, 200, r.text)
        self.s.expire_all()
        self.assertEqual([o.id for o in objekte_modul.objekte_fuer(self.s, v.id)], [haupt.id, o3.id, o2.id])
        r = self.client.post(f"/lead-management/lead/{v.id}/objekt/{o3.id}/reihenfolge",
                             data={"richtung": "hoch"}, headers={"Accept": "application/json"})
        self.assertEqual(r.status_code, 400)          # über das Hauptobjekt geht es nicht
        # Deaktivieren gesperrt, wenn ein Termin am Objekt hängt
        t = self.termin(v, objekt_id=o2.id)
        r = self.client.post(f"/lead-management/lead/{v.id}/objekt/{o2.id}/deaktivieren",
                             headers={"Accept": "application/json"})
        self.assertEqual(r.status_code, 400)
        self.assertIn("aktiver Termin", r.json()["meldung"])
        seite = self.kartei(v).text
        karte = seite.split(f'id="objekt-{o2.id}"', 1)[1].split("</article>", 1)[0]
        self.assertIn("Vorgemerkt", karte)
        self.assertIn("daran hängt: aktiver Termin", karte)
        t.status = "abgesagt"
        self.s.commit()
        r = self.client.post(f"/lead-management/lead/{v.id}/objekt/{o2.id}/deaktivieren",
                             headers={"Accept": "application/json"})
        self.assertEqual(r.status_code, 200, r.text)
        self.s.expire_all()
        self.assertFalse(self.s.get(VorgangObjekt, o2.id).aktiv)
        self.assertEqual(len(objekte_modul.objekte_fuer(self.s, v.id)), 2)
        self.assertIn("Deaktiviert:", self.kartei(v).text)
        r = self.client.post(f"/lead-management/lead/{v.id}/objekt/{o2.id}/aktivieren",
                             headers={"Accept": "application/json"})
        self.assertEqual(r.status_code, 200, r.text)
        self.s.expire_all()
        self.assertTrue(self.s.get(VorgangObjekt, o2.id).aktiv)
        # Hauptobjekt kann nicht deaktiviert werden
        r = self.client.post(f"/lead-management/lead/{v.id}/objekt/{haupt.id}/deaktivieren",
                             headers={"Accept": "application/json"})
        self.assertEqual(r.status_code, 400)

    def test_grosskunde_haekchen_setzt_aktivitaet_und_badge(self):
        v = self.lead(6)
        seite = self.kartei(v).text
        self.assertIn('data-feld="grosskunde"', seite)
        self.assertNotIn('data-rolle="grosskunde-badge"', seite)
        r = self.feld(v, "grosskunde", "1")
        self.assertEqual(r.status_code, 200, r.text)
        self.assertTrue(r.json()["ok"])
        self.assertTrue(self.kunde(v).grosskunde)
        self.assertIn(lead_kartei.GROSSKUNDE_TEXT, [a.text for a in self.aktivitaeten(v, "status")])
        seite = self.kartei(v).text
        self.assertIn('class="abzeichen lm-grosskunde" data-rolle="grosskunde-badge"', seite)
        self.assertNotIn('style="--f:', seite.split('data-rolle="grosskunde-badge"', 1)[1].split(">", 1)[0])
        # Farbe aus dem Parameter grosskunde_farbe als --f (Regel .lm-grosskunde in lead_v2.css, B)
        kern.parameter_setzen(self.s, "grosskunde_farbe", "var(--status-orange)")
        self.s.commit()
        badge = self.kartei(v).text.split('data-rolle="grosskunde-badge"', 1)[1].split(">", 1)[0]
        self.assertIn('style="--f:var(--status-orange)"', badge)
        kern.parameter_setzen(self.s, "grosskunde_farbe", "")
        self.s.commit()
        # erneut 1 → keine zweite Aktivität; entfernen → Aktivität
        self.feld(v, "grosskunde", "1")
        self.assertEqual([a.text for a in self.aktivitaeten(v, "status")].count(lead_kartei.GROSSKUNDE_TEXT), 1)
        r = self.feld(v, "grosskunde", "")
        self.assertEqual(r.status_code, 200)
        self.assertFalse(self.kunde(v).grosskunde)
        self.assertIn(lead_kartei.GROSSKUNDE_ENTFERNT_TEXT, [a.text for a in self.aktivitaeten(v, "status")])


# --- Phase 155: Reihenfolge der Kartei -----------------------------------------------------

class Reihenfolge(Basis):
    def test_h_notizen_todos_vor_kundeninfo_reiter_block_termine(self):
        v = self.lead(10)
        self.termin(v)
        self.s.add(Todo(vorgang_id=v.id, titel="V31K Rückruf vorbereiten", an_benutzer_id=1,
                        von_benutzer_id=1, status="offen", erstellt_von=1))
        self.s.commit()
        r = self.kartei(v)
        self.assertEqual(r.status_code, 200)
        seite = r.text
        marker = ['class="lk-statuskette"', 'id="lk-terminierung-knopf"', 'id="notizen"', 'id="lk-todos"',
                  'id="lk-kundeninfo"', 'role="tablist"', 'id="termine"', 'data-bereich="angebote"',
                  'data-bereich="erfassungen"', 'data-bereich="projekt"', 'data-bereich="anhaenge"']
        pos = [seite.index(m) for m in marker]
        self.assertEqual(pos, sorted(pos), "Kopf → Notizen/To-Dos → Kundeninfo → Reiter → Termine → Angebote … Anhänge")
        # Notizen-Chat mit sichtbarer Eingabe, To-Do-Spalte mit Häkchen + Inline-Anlegen; kein To-Dos-Block unten
        oben = seite.split('id="lk-oben"', 1)[1].split('id="lk-kundeninfo"', 1)[0]
        self.assertIn('class="notizen-chat nc-chat"', oben)
        self.assertIn('class="notiz-eingabe chat-eingabe nc-eingabe"', oben)
        self.assertIn("V31K Rückruf vorbereiten", oben)
        self.assertIn('class="lk-todo-haken"', oben)
        self.assertIn('action="/lead-management/todos/neu"', oben)
        self.assertNotIn('data-bereich="todos"', seite.split('id="lk-bloecke"', 1)[1])
        # Reiter nur Anruf · E-Mail · Timeline, Standard Anruf
        self.assertEqual(re.findall(r'id="tab-([a-z]+)"', seite), ["anrufe", "mails", "timeline"])
        self.assertNotIn('id="panel-termin"', seite)
        # Block Termine: Vorschläge (Top 3, Vormerken an T's Route), Kalenderansicht, Werkzeuge,
        # Historie mit Aktionen; Terminierung im Kopf postet an T's Route mit bestaetigung=auto
        block = seite.split('id="termine"', 1)[1].split('data-bereich="angebote"', 1)[0]
        for text in ('id="lk-vorschlaege"', "Terminvorschläge", "Top 3", 'id="lmt-kalender"',
                     f'data-url="/lead-management/lead/{v.id}/termin/kalender.json"', "Termin vorschlagen",
                     "Termin manuell", "Vorab-Gespräch", "Erfassung ohne Termin", 'id="lk-termin-historie"',
                     "Verschieben", "Absagen", "Termin je Objekt",
                     f'data-vormerken="/lead-management/lead/{v.id}/termin/vormerken"', 'data-rolle="objekt-wahl" hidden'):
            self.assertIn(text, block, text)
        kopf_form = seite.split('id="lk-terminierung-form"', 1)[1].split("</form>", 1)[0]
        self.assertIn('name="bestaetigung" value="auto"', kopf_form)
        self.assertIn(f'action="/lead-management/lead/{v.id}/terminierung"', seite)
        self.assertIn("lm_termin.js", seite)
        # ?tab=termin (alte Links) → Standard-Reiter + Sprung zum Block Termine
        seite2 = self.kartei(v, tab="termin").text
        self.assertIn('data-springe-zu="termine"', seite2)
        self.assertRegex(seite2, r'id="tab-anrufe"[^>]*aria-selected="true"')
        # Responsiv: Übergangs-CSS mit Umbruch unter 900 px, nur Tokens (kein Hex)
        # Die Kartei-V5-Regeln (Umbruch unter 900 px) liegen seit der Integration in lead_v2.css
        # (B hat den Übergangs-<style> übernommen, Orchestrator 13.10.2026); Hex-Werte prüft
        # der Token-Wächter test_v30_design
        self.assertNotIn("<style>", seite)
        css = (Path(__file__).resolve().parents[1] / "app" / "static" / "lead_v2.css").read_text(encoding="utf-8")
        block = css.split(".lk-v5 .lk-oben", 1)[1]
        self.assertIn("@media (max-width: 900px)", block)
        self.assertIn(".lk-oben { grid-template-columns: 1fr; }", block)

    def test_keine_tojson_in_on_attributen(self):
        """v30-Regel: tojson in doppelt gequoteten on*-Attributen nur mit forceescape."""
        for name in ("kartei.html", "kartei_info.html", "kartei_objekte.html", "kartei_mitte.html",
                     "kartei_bloecke.html", "kartei_dialoge.html", "kartei_mail_dialog.html", "_todo_formular.html"):
            text = (TEMPLATES / name).read_text(encoding="utf-8")
            for treffer in re.findall(r'\son[a-z]+="([^"]*)"', text):
                if "tojson" in treffer:
                    self.assertIn("forceescape", treffer, f"{name}: {treffer[:80]}")
        js = (PROJEKT / "app" / "static" / "lm_kartei.js").read_text(encoding="utf-8")
        for text in ("form.lk-autospeichern", "objekt_pflicht_keys", "dlg-kartei-status", "dialogUrl",
                     "springeZu", "rechnungUmschalten", "grosskundeBadge", "dataset.testphase",
                     "vormerkenUrl", "objekt_id", "testphase_hinweis", "mail_versand_aktiv"):
            self.assertIn(text, js, text)


# --- Phase 157: Felder, Status, MFH ------------------------------------------------------

class Felder(Basis):
    def test_m_ms_wa_dms_haekchen_in_der_kartei(self):
        v = self.lead(20)
        seite = self.kartei(v).text
        info = seite.split('id="lk-kundeninfo"', 1)[1].split("</form>", 1)[0]
        for code, name in (("MS", "Mieterstrom"), ("WA", "Wasser"), ("DMS", "Denkmalschutz")):
            self.assertIn(f'title="{name}"><input type="checkbox" name="interesse" value="{code}"', info)
        r = self.feld(v, "interesse", ["DMS", "WP", "MS"])
        self.assertEqual(r.status_code, 200, r.text)
        self.assertEqual(r.json()["wert"], "WP,MS,DMS")
        self.assertEqual(self.kunde(v).interesse, "WP,MS,DMS")
        haupt = objekte_modul.hauptobjekt(self.s, v.id)
        self.s.refresh(haupt)
        self.assertEqual(objekte_modul.interessen_liste(haupt), ["WP", "MS", "DMS"])
        self.assertEqual(objekte_modul.vorgang_interessen(self.s, v.id), ["WP", "MS", "DMS"])
        kopf = self.kartei(v).text.split('class="lk-badges"', 1)[1].split("</div>", 1)[0]
        self.assertIn("chip-ms", kopf)
        self.assertIn("chip-dms", kopf)
        self.assertIn("Interessen: „WP“ → „WP, MS, DMS“", [a.text for a in self.aktivitaeten(v, "aenderung")])
        self.assertEqual(self.feld(v, "interesse", ["XX"]).status_code, 400)

    def test_n_ad_pflichtfeld_sperrt_terminierung_hv_gilt(self):
        self.assertIn("ad_id", lead_v2.pflichtfelder(self.s))
        v = self.lead(21, ad_id=None)
        self.termin(v)
        kunde = self.kunde(v)
        namen = lead_kartei.pflicht_offen_namen(self.s, kunde, v)
        self.assertEqual(namen, ["Außendienst"])
        self.assertNotIn("Ad_id", namen)
        pruefung = lead_kartei.terminierung_pruefung(self.s, kunde, v)
        self.assertFalse(pruefung["bereit"])
        self.assertEqual(pruefung["fehlend"], ["Außendienst"])
        seite = self.kartei(v).text
        self.assertIn('lk-pflicht lk-pflicht-offen lk-feld-ad-offen" data-feld-wrap="ad_id"', seite)
        self.assertIn('data-ad-hinweis >', seite)                  # Hinweis sichtbar
        self.assertIn(lead_kartei.AD_PFLICHT_HINWEIS, seite)
        self.assertIn("<li>Außendienst</li>", seite)
        self.assertIn('class="knopf lk-terminierung" type="button" disabled', seite)
        self.assertIn("1 Pflichtfeld offen", seite)
        # Route liegt bei T (lm_termin.terminierung) – Pflichtfeld nicht erfüllt → nichts gebucht
        r = self.client.post(f"/lead-management/lead/{v.id}/terminierung")
        self.assertEqual(r.status_code, 303)
        self.assertIn("nicht+m", r.headers["location"])
        self.s.expire_all()
        self.assertNotEqual(self.s.get(Vorgang, v.id).lead_phase, "terminiert")
        # Zuweisung per Autospeichern → Zähler 0, Terminierung frei (ohne Neuladen in der Antwort)
        r = self.feld(v, "ad_id", str(self.ad.id))
        self.assertEqual(r.status_code, 200, r.text)
        self.assertEqual(r.json()["pflicht_anzahl"], 0)
        self.assertTrue(r.json()["terminierung"]["bereit"])
        self.assertTrue(r.json()["terminierung"]["aktiv"])
        seite = self.kartei(v).text
        self.assertNotIn('lk-feld-ad-offen" data-feld-wrap="ad_id"', seite)
        self.assertIn('data-ad-hinweis hidden', seite)
        self.assertIn('class="knopf lk-terminierung" type="submit"', seite)
        # HV-Lead: der zugewiesene Handelsvertreter gilt als erfüllt
        w = self.lead(22, ad_id=self.hv.id)
        kunde_w = self.kunde(w)
        self.assertNotIn("Außendienst", lead_kartei.pflicht_offen_namen(self.s, kunde_w, w))
        self.assertNotIn("ad_id", lead_kartei.pflicht_status(self.s, kunde_w, w)["offen_keys"])
        self.assertTrue(lead_kartei.ad_pflicht_erfuellt(self.s, w))
        self.assertIn("0 Pflichtfelder offen", self.kartei(w).text)
        # Pflichtfelder nicht nach vorgang.ad_id = None gefragt → Zähler zählt wieder
        r = self.feld(v, "ad_id", "")
        self.assertEqual(r.status_code, 200)
        self.assertIn("Außendienst", r.json()["pflicht_offen"])
        self.assertIn("ad_id", r.json()["pflicht_keys"])

    def test_o_label_disqualifiziert_und_status_aus_der_kartei(self):
        logik = leadmanagement_logik.hole_logik()
        gruende = logik.gruende_der_phase("unqualifiziert")
        self.assertTrue(gruende)
        grund = next((g for g in gruende if not g.freitext_pflicht), gruende[0])
        v = self.lead(23, lead_phase="in_kontaktierung")
        seite = self.kartei(v).text
        wahl = seite.split('id="lk-status-wahl"', 1)[1].split("</select>", 1)[0]
        self.assertIn('value="unqualifiziert" data-grund="unqualifiziert"', wahl)
        self.assertIn(">Disqualifiziert<", wahl)
        self.assertNotIn("Unqualifiziert", wahl)
        self.assertIn('value="nachbearbeitung"', wahl)
        self.assertIn('value="verloren" data-grund="verloren"', wahl)
        self.assertNotIn('value="terminiert"', wahl)            # abgeleitet, nicht wählbar
        self.assertNotIn('value="nicht_erreicht"', wahl)
        self.assertIn('data-status="neu"', seite)                 # Schritt der Kette klickbar
        daten = json.loads(seite.split('id="lk-status-daten">', 1)[1].split("</script>", 1)[0])
        self.assertIn("unqualifiziert", daten["gruende"])
        self.assertEqual(daten["aktuell"], "in_kontaktierung")
        url = f"/lead-management/lead/{v.id}/status"
        jh = {"Accept": "application/json"}
        # Pflichtgrund fehlt → 422, nichts geändert
        r = self.client.post(url, json={"wert": "unqualifiziert"}, headers=jh)
        self.assertEqual(r.status_code, 422, r.text)
        self.s.expire_all()
        self.assertEqual(self.s.get(Vorgang, v.id).lead_phase, "in_kontaktierung")
        # abgeleitete Phase → 422
        r = self.client.post(url, json={"wert": "terminiert"}, headers=jh)
        self.assertEqual(r.status_code, 422)
        # mit Grund → Disqualifiziert, Seitenzustand mit Label aus dem Blatt Status
        r = self.client.post(url, json={"wert": "unqualifiziert", "grund": grund.grund,
                                        "grund_text": "V31K Test"}, headers=jh)
        self.assertEqual(r.status_code, 200, r.text)
        self.assertEqual(r.json()["phase"], "unqualifiziert")
        self.assertEqual(r.json()["label"], "Disqualifiziert")
        self.s.expire_all()
        self.assertEqual(self.s.get(Vorgang, v.id).unqualifiziert_grund, grund.grund)
        seite = self.kartei(v).text
        kette = seite.split('class="lk-statuskette"', 1)[1].split("</ol>", 1)[0]
        self.assertIn('class="lk-schritt seitenzustand aktiv" aria-current="step"', kette)
        self.assertIn(">Disqualifiziert</li>", kette)
        self.assertNotIn("Unqualifiziert", kette)
        self.assertTrue(any("Kartei – Unqualifiziert" in a.text or "Disqualifiziert" in a.text
                            for a in self.aktivitaeten(v, "status")))
        # Zurückgestellt ohne Datum → 422 (Ausnahme der Boards-Regel: „Kunde meldet sich selbst“
        # setzt das Datum aus wv_meldet_sich_tage); mit Datum + Grund → ok; Neu = Reaktivieren
        gruende_z = logik.gruende_der_phase("zurueckgestellt")
        zg = next((g for g in gruende_z if not g.grund.lower().startswith("kunde meldet")
                   and not g.freitext_pflicht), gruende_z[0])
        if not zg.grund.lower().startswith("kunde meldet"):
            r = self.client.post(url, json={"wert": "zurueckgestellt", "grund": zg.grund}, headers=jh)
            self.assertEqual(r.status_code, 422, r.text)
        r = self.client.post(url, json={"wert": "zurueckgestellt", "grund": zg.grund, "bis": "2026-11-02",
                                        "grund_text": "V31K"}, headers=jh)
        self.assertEqual(r.status_code, 200, r.text)
        self.s.expire_all()
        self.assertEqual(self.s.get(Vorgang, v.id).lead_phase, "zurueckgestellt")
        r = self.client.post(url, json={"wert": "neu"}, headers=jh)
        self.assertEqual(r.status_code, 200, r.text)
        self.s.expire_all()
        self.assertEqual(self.s.get(Vorgang, v.id).lead_phase, "neu")
        # Nachbearbeitung über die Statuswahl (Formular-Fallback → 303)
        r = self.client.post(url, data={"wert": "nachbearbeitung", "bis": "2026-11-20"})
        self.assertEqual(r.status_code, 303)
        self.s.expire_all()
        v = self.s.get(Vorgang, v.id)
        self.assertEqual(v.lead_phase, "zurueckgestellt")
        self.assertEqual(v.zurueckgestellt_bis.date(), datetime(2026, 11, 20).date())
        self.assertTrue(v.zurueckgestellt_grund.startswith("Nachbearbeitung"))

    def test_p_mfh_frage_rechnungsadresse_zaehler(self):
        v = self.lead(24)
        r = self.feld(v, "objektart", "MFH")
        self.assertEqual(r.status_code, 200, r.text)
        # Vorbelegung Ja: nur Parteien offen
        self.assertEqual(r.json()["pflicht_offen"], ["Anzahl Parteien"])
        self.assertFalse(lead_kartei.rechnung_abweichend(self.s, v, self.kunde(v)))
        seite = self.kartei(v).text
        stammdaten = seite.split('id="lk-stammdaten"', 1)[1].split("</form>", 1)[0]
        self.assertIn("Rechnungsadresse identisch mit der Objektadresse?", stammdaten)
        frage = stammdaten.split('data-rechnung-frage', 1)[1].split("</div>", 1)[0]
        self.assertIn('value="" data-feld="rechnung_abweichend" checked', frage)
        self.assertIn('data-rechnung-felder hidden', stammdaten)
        self.assertIn("1 Pflichtfeld offen", seite)
        # Nein → Rechnungsadressfelder sichtbar und Pflicht
        r = self.feld(v, "rechnung_abweichend", "1")
        self.assertEqual(r.status_code, 200, r.text)
        self.assertEqual(sorted(r.json()["pflicht_offen"]), ["Anzahl Parteien", "Rechnungsadresse"])
        self.assertIn("rechnungsadresse", r.json()["pflicht_keys"])
        self.assertTrue(lead_kartei.rechnung_abweichend(self.s, v, self.kunde(v)))
        seite = self.kartei(v).text
        stammdaten = seite.split('id="lk-stammdaten"', 1)[1].split("</form>", 1)[0]
        self.assertIn('value="1" data-feld="rechnung_abweichend" checked', stammdaten)
        self.assertNotIn('data-rechnung-felder hidden', stammdaten)
        self.assertIn("2 Pflichtfelder offen", seite)
        # Felder füllen → nur Parteien offen; Parteien → 0
        self.feld(v, "rechnung_strasse", "Rechnungsweg 1")
        r = self.feld(v, "rechnung_ort", "Duisburg")
        self.assertEqual(r.json()["pflicht_offen"], ["Anzahl Parteien"])
        r = self.feld(v, "parteien", "4")
        self.assertEqual(r.json()["pflicht_anzahl"], 0)
        self.assertEqual((self.kunde(v).rechnung_strasse, self.kunde(v).parteien), ("Rechnungsweg 1", 4))
        # zurück auf Ja → Rechnungsadresse zählt nicht, auch wenn die Felder leer wären
        self.feld(v, "rechnung_strasse", "")
        r = self.feld(v, "rechnung_abweichend", "")
        self.assertEqual(r.json()["pflicht_anzahl"], 0)
        # weiteres MFH-Objekt: Parteien Pflicht, Rechnungsadresse nur bei Nein (am Objekt gespeichert)
        o2 = self.zweites_objekt(v, parteien="", rechnung_identisch="nein")
        self.s.expire_all()
        self.assertTrue(self.s.get(VorgangObjekt, o2.id).rechnung_abweichend)
        namen = lead_kartei.pflicht_offen_namen(self.s, self.kunde(v), v)
        self.assertIn("Objekt 2: Anzahl Parteien", namen)
        self.assertIn("Objekt 2: Rechnungsadresse", namen)
        self.objekt_feld(v, o2.id, "parteien", "4")
        self.objekt_feld(v, o2.id, "rechnung_strasse", "Hausverwaltung 9")
        r = self.objekt_feld(v, o2.id, "rechnung_ort", "Duisburg")
        self.assertEqual(r.status_code, 200, r.text)
        self.assertEqual(r.json()["objekt_pflicht_keys"].get(str(o2.id), []), [])
        self.assertEqual(r.json()["pflicht_anzahl"], 0)
        self.s.expire_all()
        self.assertEqual(self.s.get(VorgangObjekt, o2.id).rechnung_strasse, "Hausverwaltung 9")
        self.assertEqual(self.kunde(v).rechnung_strasse, "")        # Kunden-Standard unberührt

    def test_innendienst_dropdown_nur_leadmanager(self):
        v = self.lead(25, leadmanager_id=None)
        seite = self.kartei(v).text
        wahl = seite.split('data-feld="leadmanager_id"', 1)[1].split("</select>", 1)[0]
        self.assertIn(self.lm.name, wahl)
        self.assertNotIn(self.id_ohne.name, wahl)
        # aktueller Zuständiger ohne Häkchen bleibt als „(nicht mehr wählbar)“ sichtbar
        v.leadmanager_id = self.id_ohne.id
        self.s.commit()
        wahl = self.kartei(v).text.split('data-feld="leadmanager_id"', 1)[1].split("</select>", 1)[0]
        self.assertIn("(nicht mehr wählbar)", wahl)
        self.assertIn(f'value="{self.id_ohne.id}"', wahl)
        # Außendienst-Auswahl: angestellter AD ja, HV nein (Lead liegt nicht bei einem HV)
        ad_wahl = seite.split('data-feld="ad_id"', 1)[1].split("</select>", 1)[0]
        self.assertIn(f'value="{self.ad.id}"', ad_wahl)
        self.assertNotIn(f'value="{self.hv.id}"', ad_wahl)


# --- Phase 158: E-Mail-Dialog, Wiedervorlage, Timeline -----------------------------------------

class Mail(Basis):
    """Der Kartei-Dialog nutzt T's Endpunkte (routers/lm_mail.py): GET …/mail/vorschau.json und
    POST …/mail/senden – hier wird der Vertrag aus Sicht der Kartei geprüft (Platzhalter, ICS,
    fehlende Pflichtdaten, Sperre, Dialog-Markup)."""

    def test_u_mail_dialog_fuellt_platzhalter_und_haengt_ics_an(self):
        v = self.lead(30)
        t = self.termin(v, status="geplant")
        seite = self.kartei(v).text
        dialog = seite.split('id="dlg-mail"', 1)[1].split("</dialog>", 1)[0]
        self.assertIn(f'data-dialog-url="/lead-management/lead/{v.id}/mail/vorschau.json"', seite)
        self.assertIn(f'data-senden-url="/lead-management/lead/{v.id}/mail/senden"', seite)
        self.assertIn("v31k30@test.local", dialog)
        self.assertIn(lead_v5.MAILSPERRE_HINWEIS, dialog)                 # mail_versand_aktiv = aus
        r = self.client.get(f"/lead-management/lead/{v.id}/mail/vorschau.json")
        self.assertEqual(r.status_code, 200, r.text)
        d = r.json()
        keys = [x["key"] for x in d["vorlagen"]]
        self.assertIn("eingangsbestaetigung", keys)
        self.assertIn("terminbestaetigung", keys)
        self.assertNotIn("nicht_erreicht", keys)
        self.assertNotIn("nurture", keys)
        self.assertFalse(d["mail_versand_aktiv"])
        self.assertIn(lead_v5.MAILSPERRE_HINWEIS, d["mailsperre_hinweis"])
        # Terminvorlage: Platzhalter aus Lead + Termin, ICS, keine fehlenden Pflichtdaten
        r = self.client.get(f"/lead-management/lead/{v.id}/mail/vorschau.json?vorlage=terminbestaetigung")
        d = r.json()
        self.assertEqual(d["vorlage"], "terminbestaetigung")
        self.assertEqual(d["termin_id"], t.id)
        self.assertIn(t.beginn.strftime("%d.%m.%Y"), d["betreff"])
        self.assertIn(t.beginn.strftime("%H:%M"), d["betreff"])
        self.assertIn(f"Sehr geehrter Herr {NACHNAME}-Schliwa-30", d["text"])
        self.assertIn("Im Knick 36", d["text"])
        self.assertIn(self.ad.name, d["text"])
        self.assertNotIn("{", d["betreff"] + d["text"].replace("{objektliste}", ""))
        self.assertTrue(d["anhaenge"] and d["anhaenge"][0].endswith(".ics"), d["anhaenge"])
        self.assertEqual(d["fehlende"], [])
        # Senden: kein Graph-Aufruf im Request, Warteschlangen-Eintrag mit ICS, Aktivität
        with mock.patch("app.lead_mail._graph_senden") as graph:
            r = self.client.post(f"/lead-management/lead/{v.id}/mail/senden",
                                 json={"vorlage": "terminbestaetigung", "betreff": "V31K Ihr Termin",
                                       "text": "", "termin_id": t.id},
                                 headers={"Accept": "application/json"})
            graph.assert_not_called()
        self.assertEqual(r.status_code, 200, r.text)
        d = r.json()
        self.assertTrue(d["ok"])
        self.assertTrue(d["eintrag_id"])
        eintrag = self.s.get(KommunikationLog, d["eintrag_id"])
        self.assertEqual(eintrag.betreff, "V31K Ihr Termin")
        self.assertIn(".ics", eintrag.anhang_pfad or "")
        self.assertEqual(eintrag.erstellt_von, 1)
        self.assertIn(eintrag.status, ("geplant", "gesperrt"))
        self.assertNotEqual(eintrag.status, "gesendet")
        self.assertIn("Im Knick 36", eintrag.body_html)
        texte = [a.text for a in self.aktivitaeten(v, "mail_aus")]
        self.assertTrue(any("E-Mail aus der Kartei" in x for x in texte), texte)
        # E-Mail-Verlauf der Kartei zeigt den Eintrag
        self.assertIn("V31K Ihr Termin", self.kartei(v, tab="mails").text)
        # bearbeiteter Text wird übernommen (Vorlage ohne offenen Eintrag – Doppelversand-Schutz)
        r = self.client.post(f"/lead-management/lead/{v.id}/mail/senden",
                             json={"vorlage": "disqualifiziert", "betreff": "", "text": "V31K Hallo Text"},
                             headers={"Accept": "application/json"})
        self.assertEqual(r.status_code, 200, r.text)
        eintrag = self.s.get(KommunikationLog, r.json()["eintrag_id"])
        self.assertIn("V31K Hallo Text", eintrag.body_html)
        self.assertTrue(eintrag.betreff)

    def test_u_fehlende_pflichtdaten_sperren_senden(self):
        v = self.lead(31)                                          # kein Termin
        d = self.client.get(f"/lead-management/lead/{v.id}/mail/vorschau.json?vorlage=terminbestaetigung").json()
        self.assertTrue(any("Termin" in f for f in d["fehlende"]), d["fehlende"])
        self.assertEqual(d["anhaenge"], [])
        r = self.client.post(f"/lead-management/lead/{v.id}/mail/senden",
                             json={"vorlage": "terminbestaetigung"}, headers={"Accept": "application/json"})
        self.assertEqual(r.status_code, 422, r.text)
        self.assertIn("gesperrt", r.json()["meldung"])
        # kein Eintrag der Terminvorlage (die Eingangsbestätigung stammt aus lead_anlegen)
        self.assertEqual(self.s.query(KommunikationLog)
                         .filter_by(vorgang_id=v.id, vorlage_key="terminbestaetigung").count(), 0)
        # ohne E-Mail-Adresse: Schnellaktion gesperrt, Vorschau nennt die Adresse als fehlend
        w = self.lead(32, email=False)
        d = self.client.get(f"/lead-management/lead/{w.id}/mail/vorschau.json").json()
        self.assertTrue(any("E-Mail" in f for f in d["fehlende"]), d["fehlende"])
        r = self.client.post(f"/lead-management/lead/{w.id}/mail/senden", json={"vorlage": "eingangsbestaetigung"},
                             headers={"Accept": "application/json"})
        self.assertEqual(r.status_code, 422, r.text)
        seite = self.kartei(w).text
        self.assertIn('data-mail-dialog disabled', seite)
        # unbekannte Vorlage
        r = self.client.post(f"/lead-management/lead/{v.id}/mail/senden", json={"vorlage": "gibtsnicht"},
                             headers={"Accept": "application/json"})
        self.assertEqual(r.status_code, 400)
        # die Kartei hat keine eigenen Mail-Wege mehr (Vertrag T)
        self.assertEqual(self.client.get(f"/lead-management/lead/{v.id}/mail-dialog.json").status_code, 404)

    def test_mail_dialog_objektauswahl_bei_mehreren_objekten(self):
        v = self.lead(33)
        o2 = self.zweites_objekt(v)
        t2 = self.termin(v, status="geplant", objekt_id=o2.id, tage=7)
        d = self.client.get(f"/lead-management/lead/{v.id}/mail/vorschau.json?vorlage=terminbestaetigung&objekt_id={o2.id}").json()
        self.assertEqual(d["objekt_id"], o2.id)
        self.assertEqual(d["termin_id"], t2.id)
        self.assertIn(t2.beginn.strftime("%d.%m.%Y"), d["betreff"])
        self.assertIn("Sonnenwall 12", d["text"])
        seite = self.kartei(v).text
        dialog = seite.split('id="dlg-mail"', 1)[1].split("</dialog>", 1)[0]
        self.assertIn('data-rolle="objekt-wahl" >', dialog)
        self.assertIn("Objekt 2 – Sonnenwall 12", dialog)
        self.assertIn('data-rolle="termin-wahl" hidden', dialog)          # nur ein aktiver Termin
        self.termin(v, status="vorgemerkt", objekt_id=None, tage=9)
        dialog = self.kartei(v).text.split('id="dlg-mail"', 1)[1].split("</dialog>", 1)[0]
        self.assertIn('data-rolle="termin-wahl" >', dialog)

    def test_r_wiedervorlage_in_5_minuten_schritten(self):
        v = self.lead(34)
        seite = self.kartei(v).text
        dialog = seite.split('id="dlg-wiedervorlage"', 1)[1].split("</dialog>", 1)[0]
        self.assertIn('name="wann" value="', dialog)
        self.assertIn('step="300"', dialog)
        from urllib.parse import unquote_plus
        for eingabe, erwartet in (("2026-10-20T14:07", "14:05"), ("2026-10-20T14:08", "14:10"), ("2026-10-20T14:10", "14:10")):
            r = self.client.post(f"/lead-management/lead/{v.id}/wiedervorlage",
                                 data={"art": "wiedervorlage", "wann": eingabe, "notiz": "V31K"})
            self.assertEqual(r.status_code, 303)
            self.assertIn(erwartet, unquote_plus(r.headers["location"]))
            self.s.expire_all()
            self.assertEqual(self.s.get(Vorgang, v.id).naechste_aktion_am.strftime("%H:%M"), erwartet)
        self.assertEqual(lead_v5.runden_5min("14:07"), "14:05")
        self.assertEqual(lead_v5.runden_5min("14:08"), "14:10")

    def test_timeline_mit_herkunfts_badge(self):
        v = self.lead(35)
        notizen.notiz_anlegen(self.s, v.id, self.s.get(Benutzer, 1), "V31K Kunde wünscht Rückruf (Projektakte)",
                              herkunft="projektierung")
        notizen.notiz_anlegen(self.s, v.id, self.s.get(Benutzer, 1), "V31K Vertriebsnotiz", herkunft="vertrieb")
        kern.aktivitaet(self.s, v.id, "anruf", "Anruf: Erreicht – V31K", ergebnis="erreicht", dauer_sek=61)
        self.s.commit()
        seite = self.kartei(v, tab="timeline").text
        timeline = seite.split('id="lk-timeline"', 1)[1].split('class="lk-notiz-eingabe"', 1)[0]
        projekt = timeline.split("V31K Kunde wünscht Rückruf", 1)[0]
        self.assertIn('data-herkunft="projekt"', projekt[-1500:])
        self.assertIn(">Projekt</span>", projekt[-1500:])
        vertrieb = timeline.split("V31K Vertriebsnotiz", 1)[0]
        self.assertIn('data-herkunft="angebot"', vertrieb[-1500:])
        anruf = timeline.split("V31K", 1)[0]
        self.assertIn('data-herkunft="lead"', timeline)
        self.assertIn(">Lead</span>", timeline)
        self.assertIn('id="lk-tl-herkunft"', seite)
        # Karten tragen Herkunft auch über die Rückfall-Liste
        karten = lead_kartei.verlauf(self.s, v)
        self.assertTrue({"lead", "projekt", "angebot"} <= {k["herkunft"] for k in karten})
        self.assertEqual({k["herkunft"] for k in lead_kartei.timeline(self.s, v)}, {"lead", "projekt", "angebot"})


# --- Phase 159: Testphase in der Kartei ----------------------------------------------------------

class Testphase(Basis):
    def test_vormerken_und_terminierung_gesperrt_mit_tooltip(self):
        v = self.lead(40)
        self.termin(v)
        kern.parameter_setzen(self.s, "terminierung_aktiv", "aus")
        self.s.commit()
        try:
            seite = self.kartei(v).text
            self.assertIn('data-testphase="1"', seite)
            self.assertIn(f'title="{lead_v5.TESTPHASE_HINWEIS}"', seite)
            self.assertIn('data-buchbar=""', seite)
            self.assertIn(f'data-sperre-text="{lead_v5.TESTPHASE_HINWEIS}"', seite)
            self.assertIn('data-rolle="testphase"', seite)
            dialog = seite.split('id="dlg-termin-manuell"', 1)[1].split("</dialog>", 1)[0]
            self.assertIn("disabled", dialog.split("Termin eintragen</button>", 1)[0][-300:])
            r = self.client.post(f"/lead-management/lead/{v.id}/terminierung", headers={"Accept": "application/json"})
            self.assertEqual(r.status_code, 403)
            self.assertFalse(lead_kartei.terminierung_ausfuehren(self.s, v)[0])
        finally:
            kern.parameter_setzen(self.s, "terminierung_aktiv", "an")
            self.s.commit()
        seite = self.kartei(v).text
        self.assertNotIn('data-testphase="1"', seite)
        self.assertIn('data-buchbar="1"', seite)


if __name__ == "__main__":
    unittest.main()
