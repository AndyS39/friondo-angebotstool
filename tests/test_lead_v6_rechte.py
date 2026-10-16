# Tests PLAN_LEAD_V6 (v35, Phase 185 – Agent R) und Phase 187 (l), (m), (n):
# (l) der angestellte Außendienst ändert Status und Kanal (und alle weiteren Felder,
#     Objekte, Notiz, To-Do, Wiedervorlage, Anruf-Ergebnis) am EIGENEN Lead wie der
#     Innendienst – jede Änderung als Aktivität mit Autor; ein fremder Lead bleibt
#     read-only (Lesesicht der Kartei, POST 404), Boards/Sammelaktionen bleiben zu;
# (m) HV-Gruppensicht: Paolo (Simons Gruppe) sieht und bearbeitet Simons und Hartmuts
#     Leads, René nicht – und umgekehrt (Ansicht, Kartei-Gate, Dashboard, Karte, To-Dos,
#     Terminassistent, Umverteilung nur innerhalb der Gruppe, Filter „Vertreter“);
# (n) Profilbild über „Mein Profil“ erscheint als Avatar (Boards, HV-Ansicht, Kartei,
#     Benutzerverwaltung) und in der Terminbestätigung ({vertriebler_block}).
# Läuft gegen die DB-Kopie (DB_PFAD_OVERRIDE); Testdaten tragen das Präfix „V35R“ und
# werden aufgeräumt; HV-Gruppen-Parameter werden gesetzt und zurückgestellt (commit vor
# jeder Anfrage – v33 Schreibtransaktionen). Kein Netz (Routing luftlinie, Kalender aus).
import io
import re
import unittest
import warnings
from datetime import datetime, timedelta
from pathlib import Path

warnings.filterwarnings("ignore")

from fastapi.testclient import TestClient
from PIL import Image

from app import auth, lead_mail, lead_termin, lead_v2, profilbild
from app import lead_handelsvertreter as hv_modul
from app import leadmanagement as kern
from app import leadmanagement_logik
from app import objekte as objekte_modul
from app.db import SessionLocal, init_db
from app.main import app
from app.models import (AdProfil, Benachrichtigung, Benutzer, KommunikationLog, Kunde,
                        LeadAktivitaet, LeadQuelle, Todo, Vorgang, VorgangObjekt, VorgangsNotiz,
                        VotTermin)

PRAEFIX = "V35R"
NACHNAME = "V35R-Lead"
PROJEKT = Path(__file__).resolve().parents[1]
NORDSEE = (54.31, 7.61)   # Koordinaten abseits aller echten Leads (Karte)


def png_bytes(breite=640, hoehe=400) -> bytes:
    puffer = io.BytesIO()
    Image.new("RGB", (breite, hoehe), (20, 110, 190)).save(puffer, format="PNG")
    return puffer.getvalue()


def aufraeumen(s):
    s.rollback()
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
    s.query(Todo).filter(Todo.titel.like(f"{PRAEFIX}%")).delete(synchronize_session=False)
    for b in s.query(Benutzer).filter(Benutzer.name.like(f"{PRAEFIX}%")):
        s.query(AdProfil).filter_by(benutzer_id=b.id).delete()
        s.query(Benachrichtigung).filter_by(benutzer_id=b.id).delete()
        s.query(VotTermin).filter_by(ad_id=b.id).delete()
        s.query(Todo).filter((Todo.an_benutzer_id == b.id) | (Todo.von_benutzer_id == b.id)).delete(
            synchronize_session=False)
        profilbild.entfernen(b.id)
        s.delete(b)
    s.commit()


class Basis(unittest.TestCase):
    PARAMETER = ("hv_gruppe_rene", "hv_gruppe_simon", "hv_gruppe_simon_mitglieder",
                 "hv_standard_benutzer", "terminierung_aktiv", "mail_versand_aktiv",
                 "hv_ausschluss", "kanal_ad_regel", "routing_anbieter", "kalender_sync",
                 "lead_freigabe_modus")

    @classmethod
    def setUpClass(cls):
        init_db()
        cls.s = SessionLocal()
        aufraeumen(cls.s)
        cls.gesichert = {n: kern.parameter_holen(cls.s, n, "") for n in cls.PARAMETER}
        cls.admin = cls.s.get(Benutzer, 1)
        cls.innen = cls.benutzer("Innen", rolle="innendienst", leadmanager=True)
        cls.ad = cls.benutzer("AD Eins")
        cls.ad2 = cls.benutzer("AD Zwei")
        cls.rene = cls.benutzer("Rene HV", rolle="handelsvertreter")
        cls.simon = cls.benutzer("Simon HV", rolle="handelsvertreter")
        cls.paolo = cls.benutzer("Paolo HV", rolle="handelsvertreter", vorname="Paolo")
        cls.hartmut = cls.benutzer("Hartmut HV", rolle="handelsvertreter", vorname="Hartmut",
                                   telefon="0203 123456")
        for b in (cls.ad, cls.ad2):
            cls.s.add(cls.profil(b, hv=False))
        for b in (cls.rene, cls.simon, cls.paolo, cls.hartmut):
            cls.s.add(cls.profil(b, hv=True))
        kern.parameter_setzen(cls.s, "hv_gruppe_rene", str(cls.rene.id))
        kern.parameter_setzen(cls.s, "hv_gruppe_simon", str(cls.simon.id))
        kern.parameter_setzen(cls.s, "hv_gruppe_simon_mitglieder", f"{cls.paolo.id},{cls.hartmut.id}")
        kern.parameter_setzen(cls.s, "hv_standard_benutzer", str(cls.simon.id))
        kern.parameter_setzen(cls.s, "terminierung_aktiv", "aus")     # Testphase bleibt (v31)
        kern.parameter_setzen(cls.s, "mail_versand_aktiv", "aus")
        kern.parameter_setzen(cls.s, "hv_ausschluss", "")
        kern.parameter_setzen(cls.s, "kanal_ad_regel", "")
        kern.parameter_setzen(cls.s, "routing_anbieter", "luftlinie")
        kern.parameter_setzen(cls.s, "kalender_sync", "aus")
        kern.parameter_setzen(cls.s, "lead_freigabe_modus", "alle")
        cls.s.commit()
        lead_termin.vorschlaege_cache_leeren()
        cls.client_admin = cls.client(cls.admin)
        cls.client_innen = cls.client(cls.innen)
        cls.client_ad = cls.client(cls.ad)
        cls.client_paolo = cls.client(cls.paolo)
        cls.client_rene = cls.client(cls.rene)

    @classmethod
    def tearDownClass(cls):
        aufraeumen(cls.s)
        for n, w in cls.gesichert.items():
            kern.parameter_setzen(cls.s, n, w)
        cls.s.commit()
        lead_termin.vorschlaege_cache_leeren()
        cls.s.close()

    @classmethod
    def benutzer(cls, name, rolle="aussendienst", **extra):
        b = Benutzer(name=f"{PRAEFIX} {name}", rolle=rolle, aktiv=True,
                     email=f"{name.lower().replace(' ', '.')}@v35r.local",
                     pin_hash=auth.pin_hash("4321"), **extra)
        cls.s.add(b)
        cls.s.flush()
        return b

    @staticmethod
    def profil(b, hv: bool) -> AdProfil:
        import json
        return AdProfil(benutzer_id=b.id, start_adresse="Duisburg", start_lat=NORDSEE[0], start_lon=NORDSEE[1],
                        arbeitszeiten=json.dumps({t: ["08:00", "18:00"] for t in ("mo", "di", "mi", "do", "fr")}),
                        termin_dauer_min=90, puffer_min=30, max_termine_tag=3,
                        gebiet_plz_praefixe=json.dumps([]), aktiv_terminierung=True,
                        terminiert_selbst=hv, kompetenz_sparten=json.dumps(["WP", "PV", "KL", "WB"]),
                        kompetenz_kombi=True, kompetenz_mfh=True, kompetenz_gewerbe=False)

    @staticmethod
    def client(benutzer):
        c = TestClient(app, follow_redirects=False)
        c.cookies.set(auth.COOKIE_NAME, auth.cookie_wert(benutzer.id))
        return c

    def lead(self, nr, ad_id=None, geo=False, **extra):
        quelle = self.s.query(LeadQuelle).filter_by(key="website").first()
        daten = {"anrede": "Herr", "vorname": f"Vorname{nr}", "nachname": f"{NACHNAME}-{nr}",
                 "strasse": "Im Knick 36", "plz": "47269", "ort": "Duisburg",
                 "telefon": f"0203 77{nr:04d}", "sparten": ["WP"], "email": f"v35r-{nr}@test.local"}
        vorgang, _ = kern.lead_anlegen(self.s, daten, quelle, "api", entscheidung="neu")
        kunde = self.s.get(Kunde, vorgang.kunde_id)
        kunde.objektart = "EFH"
        vorgang.demo = True
        vorgang.lead_phase = "neu"
        vorgang.naechste_aktion_am = None
        vorgang.ad_id = ad_id
        if geo:
            vorgang.lat, vorgang.lon, vorgang.geocode_status = NORDSEE[0], NORDSEE[1], "ok"
        for k, v in extra.items():
            setattr(vorgang, k, v)
        self.s.commit()
        self.s.query(VorgangObjekt).filter_by(vorgang_id=vorgang.id).delete()
        objekte_modul.hauptobjekt(self.s, vorgang.id, anlegen=True)
        self.s.commit()
        return vorgang

    def frisch(self, vorgang):
        self.s.expire_all()
        return self.s.get(Vorgang, vorgang.id)

    def aktivitaeten(self, vorgang):
        return [(a.typ, a.text, a.benutzer_id) for a in self.s.query(LeadAktivitaet)
                .filter_by(vorgang_id=vorgang.id).order_by(LeadAktivitaet.id)]

    @staticmethod
    def marke(vorgang) -> str:
        return f'data-vorgang="{vorgang.id}"'


# --- Gruppen und Rechte-Matrix (Fundament) -------------------------------------------------

class A_GruppenUndRechte(Basis):
    def test_hv_gruppe_fuer(self):
        self.assertEqual(lead_v2.hv_gruppe_fuer(self.s, self.rene.id), {self.rene.id})
        simons = {self.simon.id, self.paolo.id, self.hartmut.id}
        for b in (self.simon, self.paolo, self.hartmut):
            self.assertEqual(lead_v2.hv_gruppe_fuer(self.s, b.id), simons, b.name)
        self.assertEqual(lead_v2.hv_gruppe_fuer(self.s, self.ad.id), {self.ad.id})
        self.assertEqual(lead_v2.hv_gruppe_fuer(self.s, None), set())
        self.assertIsNone(lead_v2.hv_gruppe_sicht(self.s, self.innen))
        self.assertIsNone(lead_v2.hv_gruppe_sicht(self.s, self.ad))
        self.assertEqual(lead_v2.hv_gruppe_sicht(self.s, self.paolo), simons)
        self.assertEqual(hv_modul.gruppe_ids(self.s, self.hartmut), simons)
        # Rückfall v31: ohne Mitgliederliste = alle Handelsvertreter außer der René-Gruppe
        kern.parameter_setzen(self.s, "hv_gruppe_simon_mitglieder", "")
        self.s.commit()
        try:
            gruppe = lead_v2.hv_gruppe_fuer(self.s, self.paolo.id)
            self.assertTrue(simons <= gruppe)
            self.assertNotIn(self.rene.id, gruppe)
            self.assertEqual(lead_v2.hv_gruppe_fuer(self.s, self.rene.id), {self.rene.id})
        finally:
            kern.parameter_setzen(self.s, "hv_gruppe_simon_mitglieder", f"{self.paolo.id},{self.hartmut.id}")
            self.s.commit()

    def test_bearbeiten_erlaubt_matrix(self):
        l_ad, l_ad2 = self.lead(1, ad_id=self.ad.id), self.lead(2, ad_id=self.ad2.id)
        l_simon, l_hartmut, l_rene, l_frei = (self.lead(3, ad_id=self.simon.id), self.lead(4, ad_id=self.hartmut.id),
                                              self.lead(5, ad_id=self.rene.id), self.lead(6))
        alle = (l_ad, l_ad2, l_simon, l_hartmut, l_rene, l_frei)
        for b in (self.admin, self.innen):
            for v in alle:
                self.assertTrue(lead_v2.bearbeiten_erlaubt(self.s, b, v), b.name)
            self.assertTrue(lead_v2.zugriff_erlaubt(self.s, b))
        # angestellter Außendienst: nur der eigene Lead, nie ohne Vorgang
        self.assertTrue(lead_v2.bearbeiten_erlaubt(self.s, self.ad, l_ad))
        for v in (l_ad2, l_simon, l_frei):
            self.assertFalse(lead_v2.bearbeiten_erlaubt(self.s, self.ad, v))
        self.assertFalse(lead_v2.zugriff_erlaubt(self.s, self.ad))
        self.assertTrue(lead_v2.zugriff_erlaubt(self.s, self.ad, l_ad))
        # Handelsvertreter: die Gruppe, nie die andere Gruppe
        for v in (l_simon, l_hartmut):
            self.assertTrue(lead_v2.bearbeiten_erlaubt(self.s, self.paolo, v))
        for v in (l_rene, l_ad, l_frei):
            self.assertFalse(lead_v2.bearbeiten_erlaubt(self.s, self.paolo, v))
        self.assertTrue(lead_v2.bearbeiten_erlaubt(self.s, self.rene, l_rene))
        self.assertFalse(lead_v2.bearbeiten_erlaubt(self.s, self.rene, l_simon))
        self.assertTrue(lead_v2.zugriff_erlaubt(self.s, self.paolo))
        self.assertTrue(hv_modul.darf_vorgang(self.s, self.paolo, l_hartmut))
        self.assertFalse(hv_modul.darf_vorgang(self.s, self.paolo, l_rene))
        self.assertFalse(lead_v2.bearbeiten_erlaubt(self.s, None, l_ad))
        self.assertFalse(lead_v2.bearbeiten_erlaubt(self.s, self.ad, None))
        eigene = {v.id for v in hv_modul.eigene_vorgaenge(self.s, self.paolo)}
        self.assertTrue({l_simon.id, l_hartmut.id} <= eigene)
        self.assertNotIn(l_rene.id, eigene)
        self.assertNotIn(l_ad.id, eigene)

    def test_ad_zuweisen_nur_innerhalb_der_gruppe(self):
        v = self.lead(7, ad_id=self.hartmut.id)
        self.assertTrue(lead_v2.ad_zuweisen(self.s, v, self.rene.id, benutzer=self.paolo).startswith("Nicht möglich"))
        self.assertEqual(self.frisch(v).ad_id, self.hartmut.id)
        self.assertTrue(lead_v2.ad_zuweisen(self.s, v, None, benutzer=self.paolo).startswith("Nicht möglich"))
        self.assertEqual(self.frisch(v).ad_id, self.hartmut.id)
        self.assertTrue(lead_v2.ad_zuweisen(self.s, v, self.ad.id, benutzer=self.paolo).startswith("Nicht möglich"))
        self.assertTrue(lead_v2.ad_zuweisen(self.s, v, self.simon.id, benutzer=self.paolo).startswith("Zugewiesen an"))
        self.s.commit()
        self.assertEqual(self.frisch(v).ad_id, self.simon.id)
        # Innendienst wechselt die Gruppe (Sammelaktion/Dropdown bleibt ihm erlaubt)
        self.assertTrue(lead_v2.ad_zuweisen(self.s, v, self.rene.id, benutzer=self.innen).startswith("Zugewiesen an"))
        self.s.commit()
        self.assertEqual(self.frisch(v).ad_id, self.rene.id)


# --- (l) Außendienst bearbeitet eigene Leads wie der Innendienst -------------------------------

class L_AussendienstEigenerLead(Basis):
    def test_status_kanal_und_alle_bausteine_am_eigenen_lead(self):
        v = self.lead(10, ad_id=self.ad.id)
        kartei = self.client_ad.get(f"/lead-management/lead/{v.id}")
        self.assertEqual(kartei.status_code, 200)
        self.assertNotIn("Lesesicht", kartei.text)
        for feld in ('name="vertriebskanal"', 'name="ad_id"', 'name="leadmanager_id"', 'id="lk-status-wahl"',
                     'data-readonly=""'):
            self.assertIn(feld, kartei.text, feld)
        self.assertNotIn('name="grosskunde"', kartei.text)     # Großkunde bleibt ID/LM/Admin [ANNAHME]
        # Kanal: erster echter Dropdown-Wert, der noch nicht gesetzt ist
        kunde = self.s.get(Kunde, v.kunde_id)
        werte = [w for w in kern.kanal_werte(self.s) if w and w != "?" and w != (kunde.vertriebskanal or "")]
        self.assertTrue(werte, "kein Vertriebskanal in der DB-Kopie")
        r = self.client_ad.post(f"/lead-management/lead/{v.id}/feld", json={"feld": "vertriebskanal", "wert": werte[0]})
        self.assertEqual(r.status_code, 200, r.text)
        self.assertTrue(r.json()["ok"])
        self.s.expire_all()
        self.assertEqual(self.s.get(Kunde, v.kunde_id).vertriebskanal, werte[0])
        # Status: Zurückgestellt mit Datum + Pflichtgrund (dieselben Regeln wie der Innendienst)
        gruende = leadmanagement_logik.hole_logik().gruende_der_phase("zurueckgestellt")
        self.assertTrue(gruende)
        bis = (datetime.now() + timedelta(days=5)).strftime("%Y-%m-%d")
        r = self.client_ad.post(f"/lead-management/lead/{v.id}/status",
                                json={"wert": "zurueckgestellt", "bis": bis, "grund": gruende[0].grund},
                                headers={"Accept": "application/json"})
        self.assertEqual(r.status_code, 200, r.text)
        self.assertEqual(r.json()["phase"], "zurueckgestellt")
        self.assertEqual(self.frisch(v).lead_phase, "zurueckgestellt")
        # Interessen, Innendienst (Leadmanager-Dropdown), Wiedervorlage, Notiz, Objekt, To-Do, Anruf
        r = self.client_ad.post(f"/lead-management/lead/{v.id}/feld", json={"feld": "interesse", "wert": ["WP", "PV"]})
        self.assertEqual(r.status_code, 200, r.text)
        r = self.client_ad.post(f"/lead-management/lead/{v.id}/feld", json={"feld": "leadmanager_id", "wert": str(self.innen.id)})
        self.assertEqual(r.status_code, 200, r.text)
        self.assertEqual(self.frisch(v).leadmanager_id, self.innen.id)
        wann = (datetime.now() + timedelta(days=2)).replace(hour=10, minute=5, second=0, microsecond=0)
        r = self.client_ad.post(f"/lead-management/lead/{v.id}/wiedervorlage",
                                data={"art": "wiedervorlage", "wann": wann.strftime("%Y-%m-%dT%H:%M"), "notiz": "Rückruf"})
        self.assertEqual(r.status_code, 303, r.text)
        self.assertEqual(self.frisch(v).naechste_aktion_am, wann)
        r = self.client_ad.post(f"/lead-management/lead/{v.id}/notiz", data={"text": "V35R Notiz vom AD"})
        self.assertEqual(r.status_code, 303)
        self.assertTrue(self.s.query(VorgangsNotiz).filter_by(vorgang_id=v.id).filter(
            VorgangsNotiz.text.like("V35R Notiz%")).count())
        r = self.client_ad.post(f"/lead-management/lead/{v.id}/objekt",
                                json={"bezeichnung": "Objekt 2", "strasse": "Nebenweg 2", "plz": "47269",
                                      "ort": "Duisburg", "objektart": "EFH", "interesse": ["PV"],
                                      "rechnung_identisch": "ja"},
                                headers={"Accept": "application/json"})
        self.assertEqual(r.status_code, 200, r.text)
        self.assertEqual(len(objekte_modul.objekte_fuer(self.s, v.id)), 2)
        r = self.client_ad.post("/lead-management/todos/neu",
                                data={"vorgang_id": str(v.id), "titel": "V35R To-Do vom AD",
                                      "an_benutzer_id": str(self.ad.id), "zurueck": f"/lead-management/lead/{v.id}"})
        self.assertEqual(r.status_code, 303, r.text)
        self.assertTrue(self.s.query(Todo).filter_by(vorgang_id=v.id, titel="V35R To-Do vom AD").count())
        r = self.client_ad.post(f"/lead-management/anruf/{v.id}",
                                data={"ergebnis": "nicht_erreicht", "zurueck": f"/lead-management/lead/{v.id}"})
        self.assertEqual(r.status_code, 303, r.text)
        self.assertEqual(self.frisch(v).versuch_nr, 1)
        # jede Änderung protokolliert mit dem Außendienstler als Autor
        akt = self.aktivitaeten(v)
        texte = [t for _, t, _ in akt]
        self.assertTrue(any(t.startswith("Vertriebskanal:") for t in texte), texte)
        self.assertTrue(any(t.startswith("Interessen:") for t in texte), texte)
        self.assertTrue(any("Zurückgestellt bis" in t for t in texte), texte)
        self.assertTrue(any(t.startswith("Leadmanager:") for t in texte), texte)
        autoren = {b for typ, _, b in akt if typ in ("aenderung", "status", "anruf")}
        self.assertEqual(autoren, {self.ad.id})
        # Außendienst-Dropdown wie v31 (angestellte AD) + Innendienst-Dropdown = nur Leadmanager
        auswahl = kartei.text.split('name="ad_id"', 1)[1].split("</select>", 1)[0]
        self.assertIn(f'value="{self.ad2.id}"', auswahl)
        self.assertNotIn(f'value="{self.rene.id}"', auswahl)
        innen_auswahl = kartei.text.split('name="leadmanager_id"', 1)[1].split("</select>", 1)[0]
        self.assertIn(f'value="{self.innen.id}"', innen_auswahl)

    def test_fremder_lead_bleibt_read_only_und_keine_boards(self):
        fremd = self.lead(11, ad_id=self.ad2.id)
        # Lesesicht über einen eigenen Termin (gehoert_benutzer) – nur ansehen
        termin = VotTermin(vorgang_id=fremd.id, ad_id=self.ad.id, beginn=datetime.now() + timedelta(days=1),
                           ende=datetime.now() + timedelta(days=1, hours=1), status="geplant", typ="vot",
                           demo=True, adresse="Im Knick 36, Duisburg")
        self.s.add(termin)
        self.s.commit()
        r = self.client_ad.get(f"/lead-management/lead/{fremd.id}")
        self.assertEqual(r.status_code, 200)
        self.assertIn("Lesesicht", r.text)
        self.assertIn('data-readonly="1"', r.text)
        self.assertNotIn('id="lk-status-wahl"', r.text)
        werte = [w for w in kern.kanal_werte(self.s) if w and w != "?"]
        r = self.client_ad.post(f"/lead-management/lead/{fremd.id}/feld",
                                json={"feld": "vertriebskanal", "wert": werte[0] if werte else "Enni"})
        self.assertEqual(r.status_code, 404)
        r = self.client_ad.post(f"/lead-management/lead/{fremd.id}/status", json={"wert": "unqualifiziert", "grund": "x"},
                                headers={"Accept": "application/json"})
        self.assertEqual(r.status_code, 404)
        self.assertEqual(self.client_ad.post(f"/lead-management/lead/{fremd.id}/notiz", data={"text": "x"}).status_code, 404)
        # völlig fremder Lead: 404
        ganz_fremd = self.lead(12, ad_id=self.hartmut.id)
        self.assertEqual(self.client_ad.get(f"/lead-management/lead/{ganz_fremd.id}").status_code, 404)
        # Boards, Sammelaktionen (Archivieren/Duplizieren) bleiben dem Außendienst verschlossen
        eigen = self.lead(13, ad_id=self.ad.id)
        for pfad in ("/lead-management/hauptboard", "/lead-management/terminiert", "/lead-management/kontaktiert"):
            self.assertEqual(self.client_ad.get(pfad).status_code, 404, pfad)
        r = self.client_ad.post("/lead-management/boards/sammelaktion",
                                data={"board": "hauptboard", "aktion": "archivieren", "ids": [str(eigen.id)]})
        self.assertEqual(r.status_code, 404)
        self.assertIsNone(self.frisch(eigen).archiviert_am)
        self.assertEqual(self.client_ad.get("/parametrierung/lead-einstellungen").status_code, 303)   # Middleware

    def test_kartei_markup_mobil(self):
        """Mobile Darstellung bei 390 px (v25 responsiv): Viewport-Meta, Kartei-Container ohne
        feste Breiten, Media-Queries für die Kartei-Blöcke in lead_v2.css."""
        v = self.lead(14, ad_id=self.ad.id)
        html = self.client_ad.get(f"/lead-management/lead/{v.id}").text
        self.assertIn('<meta name="viewport" content="width=device-width', html)
        self.assertIn("lk-seite", html)
        inhalt = html.split("<main", 1)[1]
        for breit in re.findall(r'style="[^"]*(?:min-)?width:\s*(\d+)px', inhalt):
            self.assertLessEqual(int(breit), 390, "feste Breite über 390 px in der Kartei")
        css = (PROJEKT / "app" / "static" / "lead_v2.css").read_text(encoding="utf-8")
        # v25: Kundeninfo-Raster 1 Spalte unter 900 px, 2 ab 900 px, 4 ab 1200 px (mobile first)
        self.assertRegex(css, r"@media\s*\(max-width:\s*900px\)[\s\S]*?\.lk-")
        self.assertRegex(css, r"@media\s*\(min-width:\s*900px\)")
        self.assertRegex(css, r"@media\s*\(min-width:\s*1200px\)")


# --- (m) HV-Gruppensicht ----------------------------------------------------------------

class M_Gruppensicht(Basis):
    def test_paolo_sieht_simons_und_hartmuts_leads_rene_nicht(self):
        l_simon = self.lead(20, ad_id=self.simon.id, geo=True)
        l_hartmut = self.lead(21, ad_id=self.hartmut.id, geo=True)
        l_paolo = self.lead(22, ad_id=self.paolo.id, geo=True)
        l_rene = self.lead(23, ad_id=self.rene.id, geo=True)
        # Ansicht „Leads meiner Gruppe“ mit Filter „Vertreter“ (nur die Gruppe)
        r = self.client_paolo.get("/lead-management/handelsvertreter")
        self.assertEqual(r.status_code, 200, r.text[:300])
        for v in (l_simon, l_hartmut, l_paolo):
            self.assertIn(self.marke(v), r.text, v.id)
        self.assertNotIn(self.marke(l_rene), r.text)
        self.assertIn("Leads meiner Gruppe", r.text)
        wahl = r.text.split('name="vertreter"', 1)[1].split("</select>", 1)[0]
        for b in (self.simon, self.paolo, self.hartmut):
            self.assertIn(f'value="{b.id}"', wahl)
        self.assertNotIn(f'value="{self.rene.id}"', wahl)
        r2 = self.client_paolo.get(f"/lead-management/handelsvertreter?vertreter={self.hartmut.id}")
        self.assertIn(self.marke(l_hartmut), r2.text)
        self.assertNotIn(self.marke(l_simon), r2.text)
        r3 = self.client_paolo.get(f"/lead-management/handelsvertreter?vertreter={self.rene.id}")
        self.assertIn(self.marke(l_simon), r3.text)          # fremde ID wird verworfen
        self.assertNotIn(self.marke(l_rene), r3.text)
        # Zuweisungs-Dropdown der Zeile: nur die eigene Gruppe
        zeile = r.text[r.text.find(self.marke(l_hartmut)):]
        zeile = zeile[:zeile.find("</tr>")]
        self.assertIn(f'value="{self.simon.id}"', zeile)
        self.assertNotIn(f'value="{self.rene.id}"', zeile)
        # René: nur seine Leads, Titel „Meine Leads“, kein Vertreter-Filter
        rr = self.client_rene.get("/lead-management/handelsvertreter")
        self.assertEqual(rr.status_code, 200)
        self.assertIn(self.marke(l_rene), rr.text)
        for v in (l_simon, l_hartmut, l_paolo):
            self.assertNotIn(self.marke(v), rr.text, v.id)
        self.assertIn("Meine Leads", rr.text)
        self.assertNotIn('name="vertreter"', rr.text)
        # Kartei-Gate: Gruppe bearbeitbar, andere Gruppe 404
        k = self.client_paolo.get(f"/lead-management/lead/{l_hartmut.id}")
        self.assertEqual(k.status_code, 200)
        self.assertNotIn("Lesesicht", k.text)
        self.assertIn('name="ad_id"', k.text)
        self.assertEqual(self.client_paolo.get(f"/lead-management/lead/{l_rene.id}").status_code, 404)
        self.assertEqual(self.client_rene.get(f"/lead-management/lead/{l_simon.id}").status_code, 404)
        self.assertEqual(self.client_rene.get(f"/lead-management/lead/{l_rene.id}").status_code, 200)
        # Dashboard und Kacheln je Gruppe
        d = self.client_paolo.get("/lead-management/handelsvertreter/dashboard")
        self.assertEqual(d.status_code, 200)
        for v in (l_simon, l_hartmut, l_paolo):
            self.assertIn(f"/lead-management/lead/{v.id}", d.text)
        self.assertNotIn(f"/lead-management/lead/{l_rene.id}", d.text)
        daten = hv_modul.dashboard_daten(self.s, self.paolo)
        self.assertGreaterEqual(daten["kacheln"]["offen"], 3)
        self.assertEqual(daten["gruppe_groesse"], 3)
        self.assertEqual(hv_modul.dashboard_daten(self.s, self.rene)["gruppe_groesse"], 1)
        # Karte: Pins der Gruppe, nicht Renés
        pins = self.client_paolo.get("/lead-management/karte/daten").json()["pins"]
        ids = {p["vorgang_id"] for p in pins if p.get("art") == "lead"}
        self.assertTrue({l_simon.id, l_hartmut.id, l_paolo.id} <= ids)
        self.assertNotIn(l_rene.id, ids)
        start = {p["ad"] for p in pins if p.get("art") == "start"}
        self.assertIn(self.hartmut.name, start)
        self.assertNotIn(self.rene.name, start)
        # To-Dos mit Vorgangsbezug: Gruppe ja, andere Gruppe nein
        t = self.client_paolo.get(f"/lead-management/todos?vorgang_id={l_hartmut.id}")
        self.assertEqual(t.status_code, 200)
        self.assertNotIn("Kein Zugriff auf diesen Vorgang", t.text)
        t2 = self.client_paolo.get(f"/lead-management/todos?vorgang_id={l_rene.id}")
        self.assertIn("Kein Zugriff auf diesen Vorgang", t2.text)
        # Mein Dashboard (Lead-Modul): Wiedervorlagen der Gruppe
        l_hartmut.naechste_aktion_am = datetime.now() - timedelta(hours=1)
        l_rene.naechste_aktion_am = datetime.now() - timedelta(hours=1)
        self.s.commit()
        dash = self.client_paolo.get("/lead-management/dashboard")
        self.assertEqual(dash.status_code, 200)
        self.assertIn(f"/lead-management/lead/{l_hartmut.id}", dash.text)
        self.assertNotIn(f"/lead-management/lead/{l_rene.id}", dash.text)
        # gesperrte Seiten bleiben gesperrt (303 auf die HV-Ansicht)
        r = self.client_paolo.get("/lead-management/hauptboard")
        self.assertEqual(r.status_code, 303)
        self.assertTrue(r.headers["location"].startswith("/lead-management/handelsvertreter?meldung="))

    def test_terminassistent_und_umverteilung_in_der_gruppe(self):
        l_hartmut = self.lead(24, ad_id=self.hartmut.id, geo=True)
        l_rene = self.lead(25, ad_id=self.rene.id, geo=True)
        lead_termin.vorschlaege_cache_leeren()
        # Paolo: normale Vorschläge für Hartmuts Lead (kein Hinweis „liegt bei …“), Kandidaten = Gruppe
        a = self.client_paolo.get(f"/lead-management/lead/{l_hartmut.id}/termin")
        self.assertEqual(a.status_code, 200, a.text[:300])
        j = self.client_paolo.get(f"/lead-management/lead/{l_hartmut.id}/termin/vorschlaege.json").json()
        self.assertNotEqual(j["status"], "hv_lead", j)
        vorfilter = lead_termin.kandidaten(self.s, l_hartmut, benutzer=self.paolo)
        kandidaten = {k["ad"].id for k in vorfilter["kandidaten"]}
        self.assertTrue(kandidaten <= {self.simon.id, self.paolo.id, self.hartmut.id})
        self.assertIn(self.hartmut.id, kandidaten)
        self.assertNotIn(self.rene.id, kandidaten)
        self.assertNotIn(self.ad.id, kandidaten)
        self.assertIsNone(vorfilter["hv_lead"])
        # Innendienst sieht weiterhin den HV-Hinweis
        vorfilter_id = lead_termin.kandidaten(self.s, l_hartmut, benutzer=self.innen)
        self.assertIsNotNone(vorfilter_id["hv_lead"])
        j_id = self.client_innen.get(f"/lead-management/lead/{l_hartmut.id}/termin/vorschlaege.json?neu=1").json()
        self.assertEqual(j_id["status"], "hv_lead")
        # René: eigene Gruppe = nur er (Kandidat René)
        vorfilter_rene = lead_termin.kandidaten(self.s, l_rene, benutzer=self.rene)
        self.assertEqual({k["ad"].id for k in vorfilter_rene["kandidaten"]}, {self.rene.id})
        self.assertTrue(lead_termin.hv_ad_erlaubt(self.s, self.paolo, self.simon.id))
        self.assertFalse(lead_termin.hv_ad_erlaubt(self.s, self.paolo, self.rene.id))
        self.assertTrue(lead_termin.hv_ad_erlaubt(self.s, self.innen, self.rene.id))
        # Umverteilung per Dropdown (Autospeichern) nur innerhalb der Gruppe
        r = self.client_paolo.post(f"/lead-management/lead/{l_hartmut.id}/feld",
                                   json={"feld": "ad_id", "wert": str(self.rene.id)})
        self.assertEqual(r.status_code, 400, r.text)
        self.assertIn("Nicht möglich", r.json()["meldung"])
        self.assertEqual(self.frisch(l_hartmut).ad_id, self.hartmut.id)
        r = self.client_paolo.post(f"/lead-management/lead/{l_hartmut.id}/feld", json={"feld": "ad_id", "wert": ""})
        self.assertEqual(r.status_code, 400, r.text)
        r = self.client_paolo.post(f"/lead-management/lead/{l_hartmut.id}/feld",
                                   json={"feld": "ad_id", "wert": str(self.simon.id)})
        self.assertEqual(r.status_code, 200, r.text)
        self.assertEqual(self.frisch(l_hartmut).ad_id, self.simon.id)
        # HV-Ansicht: Dropdown „Vertreter“ – andere Gruppe abgewiesen
        r = self.client_paolo.post(f"/lead-management/handelsvertreter/{l_hartmut.id}/zuweisen",
                                   data={"ad_id": str(self.rene.id), "zurueck": "/lead-management/handelsvertreter"})
        self.assertEqual(r.status_code, 303)
        self.assertIn("Nicht+m", r.headers["location"])
        self.assertEqual(self.frisch(l_hartmut).ad_id, self.simon.id)
        r = self.client_paolo.post(f"/lead-management/handelsvertreter/{l_hartmut.id}/zuweisen",
                                   data={"ad_id": str(self.hartmut.id), "zurueck": "/lead-management/handelsvertreter"})
        self.assertEqual(r.status_code, 303)
        self.assertEqual(self.frisch(l_hartmut).ad_id, self.hartmut.id)
        # Lead der anderen Gruppe: 404 auch für die Zuweisungsroute
        r = self.client_paolo.post(f"/lead-management/handelsvertreter/{l_rene.id}/zuweisen",
                                   data={"ad_id": str(self.paolo.id)})
        self.assertEqual(r.status_code, 404)
        # Innendienst wechselt die Gruppe über die Sammelaktion (v33) – weiter erlaubt
        r = self.client_innen.post("/lead-management/boards/sammelaktion",
                                   json={"board": "hauptboard", "aktion": "hv_verschieben", "ziel": "rene",
                                         "ids": [l_hartmut.id]}, headers={"Accept": "application/json"})
        self.assertEqual(r.status_code, 200, r.text)
        self.assertEqual(self.frisch(l_hartmut).ad_id, self.rene.id)
        self.assertEqual(self.client_paolo.get(f"/lead-management/lead/{l_hartmut.id}").status_code, 404)


# --- (n) Profilbild -------------------------------------------------------------------------

class N_Profilbild(Basis):
    def test_upload_avatar_und_terminbestaetigung(self):
        client_hartmut = self.client(self.hartmut)
        r = client_hartmut.get("/einstellungen/profil")
        self.assertEqual(r.status_code, 200, r.text[:300])
        self.assertIn("Mein Profil", r.text)
        self.assertIn('action="/einstellungen/profil/bild"', r.text)
        self.assertIn("profil_v35.js", r.text)
        self.assertEqual(profilbild.url_fuer(self.hartmut.id), "")
        # Upload PNG 640×400 → quadratisch 400×400 JPEG unter data/benutzerbilder/<id>.jpg
        r = client_hartmut.post("/einstellungen/profil/bild", files={"bild": ("foto.png", png_bytes(), "image/png")})
        self.assertEqual(r.status_code, 303, r.text)
        self.assertIn("Profilbild+gespeichert", r.headers["location"])
        self.s.expire_all()
        person = self.s.get(Benutzer, self.hartmut.id)
        self.assertEqual(person.bild_datei, f"benutzerbilder/{self.hartmut.id}.jpg")
        pfad = lead_mail.bild_pfad(person)
        self.assertIsNotNone(pfad)
        with Image.open(pfad) as bild:
            self.assertEqual(bild.format, "JPEG")
            self.assertEqual(bild.size, (400, 400))
        url = profilbild.url_fuer(self.hartmut.id)
        self.assertTrue(url.startswith(f"/einstellungen/profil/bild/{self.hartmut.id}?v="), url)
        b = client_hartmut.get(url)
        self.assertEqual(b.status_code, 200)
        self.assertEqual(b.headers["content-type"], "image/jpeg")
        self.assertIn("private", b.headers.get("cache-control", ""))
        self.assertEqual(TestClient(app, follow_redirects=False).get(url).status_code, 303)   # ohne Anmeldung
        # Avatare: Benutzerverwaltung (Makro avatar), HV-Ansicht (Gruppenkopf), Kartei (Zuständige),
        # Board-Tabelle (_tabelle.avatar)
        v = self.lead(30, ad_id=self.hartmut.id)
        self.assertIn(f'src="{url}"', self.client_admin.get("/benutzer").text)
        hv_seite = self.client_admin.get("/lead-management/handelsvertreter").text
        self.assertIn("hv-avatar-bild", hv_seite)
        self.assertIn(f'src="{url}"', hv_seite)
        kartei = self.client_admin.get(f"/lead-management/lead/{v.id}").text
        self.assertIn("lk-avatar-bild", kartei)
        self.assertIn(f'src="{url}"', kartei)
        board = self.client_admin.get("/lead-management/hauptboard").text
        self.assertIn("lm-avatar-bild", board)
        self.assertIn(f'src="{url}"', board)
        # Initialen bleiben bei Benutzern ohne Bild (Makro-Rückfall)
        self.assertNotIn(f'/einstellungen/profil/bild/{self.rene.id}', hv_seite)
        # Terminbestätigung: {vertriebler_block} mit Inline-Bild (cid) – Vorschau mit Bild-URL
        termin = VotTermin(vorgang_id=v.id, ad_id=self.hartmut.id, beginn=datetime.now() + timedelta(days=3),
                           ende=datetime.now() + timedelta(days=3, hours=1), status="geplant", typ="vot",
                           demo=True, adresse="Im Knick 36, 47269 Duisburg")
        self.s.add(termin)
        self.s.commit()
        block = lead_mail.vertriebler_block_html(person)
        self.assertIn(f"cid:{lead_mail.CID_PRAEFIX}{self.hartmut.id}", block)
        self.assertIn(self.hartmut.name, block)
        bilder = lead_mail.inline_bilder_aus_html(self.s, block)
        self.assertEqual([(b[0], b[2]) for b in bilder], [(f"{lead_mail.CID_PRAEFIX}{self.hartmut.id}", "image/jpeg")])
        self.assertEqual(bilder[0][1].resolve(), pfad.resolve())
        betreff, html, _fehlend = lead_mail.vorlage_rendern(self.s, "terminbestaetigung", v, termin, vorschau=True)
        self.assertTrue(f"/lead-management/benutzer/{self.hartmut.id}/bild" in html
                        or f"cid:{lead_mail.CID_PRAEFIX}{self.hartmut.id}" in html, html[:400])
        self.s.rollback()
        # Entfernen → Initialen, Datei weg
        r = client_hartmut.post("/einstellungen/profil/bild", data={"aktion": "entfernen"})
        self.assertEqual(r.status_code, 303)
        self.s.expire_all()
        self.assertEqual(self.s.get(Benutzer, self.hartmut.id).bild_datei, "")
        self.assertEqual(profilbild.url_fuer(self.hartmut.id), "")
        self.assertFalse(pfad.exists())
        self.assertEqual(client_hartmut.get(f"/einstellungen/profil/bild/{self.hartmut.id}").status_code, 404)

    def test_pruefungen_und_profildaten(self):
        client_ad = self.client(self.ad)
        r = client_ad.post("/einstellungen/profil/bild", files={"bild": ("text.png", b"kein bild", "image/png")})
        self.assertEqual(r.status_code, 303)
        self.assertIn("nicht+lesbar", r.headers["location"])
        r = client_ad.post("/einstellungen/profil/bild",
                           files={"bild": ("gross.png", png_bytes(10, 10) + b"\0" * (profilbild.MAX_BYTES + 10), "image/png")})
        self.assertIn("2+MB", r.headers["location"])
        r = client_ad.post("/einstellungen/profil/bild", files={"bild": ("x.gif", b"GIF89a", "image/gif")})
        self.assertIn("nicht", r.headers["location"])
        self.assertEqual(profilbild.url_fuer(self.ad.id), "")
        # Vorname und Telefon selbst pflegen [ANNAHME]; Name/E-Mail bleiben
        r = client_ad.post("/einstellungen/profil", data={"vorname": "Erik", "telefon": "0203 99 88"})
        self.assertEqual(r.status_code, 303)
        self.s.expire_all()
        person = self.s.get(Benutzer, self.ad.id)
        self.assertEqual((person.vorname, person.telefon), ("Erik", "0203 99 88"))
        self.assertEqual(person.name, f"{PRAEFIX} AD Eins")
        # jede Rolle erreicht die Seite (Montage/Projektierung über /einstellungen in den Pfadtabellen)
        montage = self.s.query(Benutzer).filter(Benutzer.rolle == "montage", Benutzer.aktiv.is_(True)).first()
        if montage is not None:
            self.assertEqual(self.client(montage).get("/einstellungen/profil").status_code, 200)
        # Wächter: Upload-Route liest das Formular vor dem ersten Datenbankzugriff
        quelle = (PROJEKT / "app" / "routers" / "einstellungen.py").read_text(encoding="utf-8")
        rumpf = quelle.split("def profil_bild_speichern", 1)[1].split("\n@router", 1)[0]
        self.assertLess(rumpf.index("anfrage.formular("), rumpf.index("session.get("))


if __name__ == "__main__":
    unittest.main()
