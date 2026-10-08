# Tests PLAN_LEAD_V2 Phase 106 (CLAUDE v23): Kundenkartei dreispaltig –
# Rendern (drei Spalten, Reiter, Pflichtfeld-Zähler), Stammdaten speichern
# (inkl. MFH-Zusatzfelder, Kanal-Sync-Schutz, Einwilligung), Zuweisungen
# (Aktivität + Glocke, HV-Ausschluss), Terminierung B8 (gesperrt/frei),
# Vorab-Angebot (F10), Nachbearbeitung (F11), Wiedervorlage, Gate 404,
# Lead-Kopf der Vorgangsakte mit Link zur Kartei. Laufen im Demo-Modus gegen
# die Entwicklungs-DB; Testleads tragen den Nachnamen „LeadV2K-Test“.
import unittest
import warnings
from datetime import datetime, timedelta

warnings.filterwarnings("ignore")

from fastapi.testclient import TestClient

from app import auth, lead_kartei, lead_v2
from app import leadmanagement as kern


# v29 (PLAN_LEAD_V4 Phase 141): Lead-Glocken sind standardmäßig nur für To-Dos
# (Parameter glocke_lead_arten) – Tests, die eine Glocke einer anderen Art prüfen,
# schalten die Art für den Testabschnitt ein (zeigt zugleich die Wiedereinschaltbarkeit).
from contextlib import contextmanager


@contextmanager
def glocken_arten(s, *arten):
    from app import lead_glocken
    alt = kern.parameter_holen(s, lead_glocken.PARAMETER, "")
    kern.parameter_setzen(s, lead_glocken.PARAMETER, ",".join(lead_glocken.STANDARD_ARTEN + tuple(arten)))
    s.commit()
    try:
        yield
    finally:
        kern.parameter_setzen(s, lead_glocken.PARAMETER, alt)
        s.commit()
from app.db import SessionLocal, init_db
from app.main import app
from app.models import (AdProfil, Benachrichtigung, Benutzer, KommunikationLog,
                        Kunde, LeadAktivitaet, LeadQuelle, Todo, Vorgang,
                        VorgangsNotiz, VotTermin)

NACHNAME = "LeadV2K-Test"
BENUTZER_PRAEFIX = "LeadV2K "


def aufraeumen(s):
    for k in s.query(Kunde).filter(Kunde.nachname.like(f"{NACHNAME}%")):
        for v in s.query(Vorgang).filter_by(kunde_id=k.id):
            s.query(LeadAktivitaet).filter_by(vorgang_id=v.id).delete()
            s.query(KommunikationLog).filter_by(vorgang_id=v.id).delete()
            s.query(VotTermin).filter_by(vorgang_id=v.id).delete()
            s.query(VorgangsNotiz).filter_by(vorgang_id=v.id).delete()
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
    @classmethod
    def setUpClass(cls):
        init_db()
        cls.s = SessionLocal()
        aufraeumen(cls.s)
        cls.client = TestClient(app)
        cls.client.post("/login", data={"benutzer_id": "1", "pin": "1234"})
        cls.modus = kern.parameter_holen(cls.s, "lead_freigabe_modus", "admin")
        kern.parameter_setzen(cls.s, "lead_freigabe_modus", "admin")
        cls.s.commit()
        # Test-Außendienstler: ein angestellter AD, ein Handelsvertreter (A-1)
        cls.ad = Benutzer(name=f"{BENUTZER_PRAEFIX}AD", rolle="aussendienst",
                          pin_hash=auth.pin_hash("4321"), email="lv2k-ad@test.local")
        cls.hv = Benutzer(name=f"{BENUTZER_PRAEFIX}HV", rolle="aussendienst",
                          pin_hash=auth.pin_hash("4321"), email="lv2k-hv@test.local")
        cls.s.add_all([cls.ad, cls.hv])
        cls.s.flush()
        cls.s.add(AdProfil(benutzer_id=cls.ad.id, aktiv_terminierung=True,
                           termin_dauer_min=90, puffer_min=30, max_termine_tag=3))
        cls.s.add(AdProfil(benutzer_id=cls.hv.id, aktiv_terminierung=True,
                           terminiert_selbst=True, termin_dauer_min=90,
                           puffer_min=30, max_termine_tag=3))
        cls.s.commit()

    @classmethod
    def tearDownClass(cls):
        aufraeumen(cls.s)
        kern.parameter_setzen(cls.s, "lead_freigabe_modus", cls.modus)
        cls.s.commit()
        cls.s.close()

    def lead(self, nr, vollstaendig=False, **extra):
        quelle = self.s.query(LeadQuelle).filter_by(key="website").first()
        daten = {"vorname": f"V{nr}", "nachname": f"{NACHNAME}-{nr}", "plz": "47139",
                 "ort": "Duisburg", "telefon": f"0203 88{nr:04d}", "sparten": ["WP"],
                 "email": f"v2k{nr}@test.local"}
        vorgang, _ = kern.lead_anlegen(self.s, daten, quelle, "api", entscheidung="neu")
        vorgang.demo = True
        kunde = self.s.get(Kunde, vorgang.kunde_id)
        if vollstaendig:
            kunde.anrede = "Herr"
            kunde.strasse = "Sonnenwall 1"
            kunde.vertriebskanal = "Standard"
            kunde.objektart = "EFH"
        for k, v in extra.items():
            setattr(vorgang, k, v)
        self.s.commit()
        return vorgang

    def kartei(self, vorgang, **params):
        url = f"/lead-management/lead/{vorgang.id}"
        if params:
            url += "?" + "&".join(f"{k}={v}" for k, v in params.items())
        return self.client.get(url)

    def aktivitaeten(self, vorgang, typ=None):
        self.s.expire_all()
        q = self.s.query(LeadAktivitaet).filter_by(vorgang_id=vorgang.id)
        if typ:
            q = q.filter_by(typ=typ)
        return q.order_by(LeadAktivitaet.id).all()


class Rendern(Basis):
    def test_kartei_rendert_v3_layout(self):
        """v25 (PLAN_LEAD_V3 Phase 119): statt drei Spalten jetzt Kopf (Statuskette)
        → Kundeninfo-Block → Reiter Termin · Anrufnotizen · E-Mail-Verlauf ·
        Timeline → Blöcke; Reiter Qualifizierung/Vorgang und der Dialog
        „Nicht erreicht“ (Phase 120: ohne Dialog) existieren nicht mehr."""
        v = self.lead(1)
        r = self.kartei(v)
        self.assertEqual(r.status_code, 200)
        seite = r.text
        for text in ('class="lk-statuskette"', 'id="lk-kundeninfo"', 'class="karte lk-mitte"',
                     'id="lk-bloecke"',
                     'role="tablist"', 'id="tab-timeline"', 'id="tab-mails"', 'id="tab-anrufe"',
                     'id="tab-termin"',
                     'aria-label="E-Mail-Verlauf"', 'class="lm-anruf-form', 'name="dauer_sek"',
                     'href="tel:', 'href="mailto:v2k1@test.local"', "lm_kartei.js", "lm_anruf.js",
                     "Pflichtfeld", 'id="lk-stammdaten"', "Innendienst", "To-Dos",
                     "Anhänge", 'action="/lead-management/todos/neu"', "Terminierung",
                     "Nachbearbeitung", "Vorab-Gespräch", "Erfassung ohne Termin",
                     'class="demo-badge"', 'data-bereich="termine"', "Termin manuell",
                     "Wiedervorlage",
                     # C1/C2/C3: Ergebnis-Buttons 1–7 + Folgedialoge aus Phase 107
                     f'class="lk-anruf" aria-label="Anruf protokollieren" data-vorgang="{v.id}"',
                     'value="falsche_nummer"', "Kein Interesse", 'name="ergebnis" value="nicht_erreicht"',
                     'id="dlg-rueckruf"', 'id="dlg-keininteresse"', 'id="dlg-reaktivieren"',
                     f'name="zurueck" value="/lead-management/lead/{v.id}?tab=anrufe"'):
            self.assertIn(text, seite, text)
        for weg in ('class="karte lk-links"', 'class="lk-rechts"', 'id="tab-qualifizierung"',
                    'id="tab-vorgang"', f"dialogOeffnen('nichterreicht', {v.id})"):
            self.assertNotIn(weg, seite, weg)
        # V1-Weiterleitung übernommen: kein Redirect mehr auf die Vorgangsakte
        self.assertEqual(self.client.get(f"/lead-management/lead/{v.id}",
                                         follow_redirects=False).status_code, 200)

    def test_pflichtfeld_zaehler_und_rote_umrandung(self):
        v = self.lead(2)
        kunde = self.s.get(Kunde, v.kunde_id)
        offen = lead_v2.pflichtfelder_offen(self.s, kunde, v)
        self.assertTrue(offen)                         # Anrede, Straße, Kanal, Objektart …
        seite = self.kartei(v).text
        self.assertIn(f"{len(offen)} Pflichtfelder offen", seite)
        self.assertIn("lk-pflicht-offen", seite)
        # Terminierung gesperrt + Fehlliste nennt die offenen Felder (lesbare
        # Namen: „Straße“ statt „Strasse“, gleiche Anzahl wie lead_v2)
        self.assertIn("Terminierung gesperrt", seite)
        namen = lead_kartei.pflicht_offen_namen(self.s, kunde, v)
        self.assertEqual(len(namen), len(offen))
        self.assertIn("Straße", namen)
        self.assertNotIn("Strasse", namen)
        for feld in namen:
            self.assertIn(f"<li>{feld}</li>", seite)
        # vollständiger Lead: Zähler 0, keine rote Umrandung der Pflichtfelder
        voll = self.lead(3, vollstaendig=True)
        seite = self.kartei(voll).text
        self.assertIn("0 Pflichtfelder offen", seite)
        self.assertNotIn("lk-feld lk-pflicht-offen", seite)

    def test_mfh_zusatzfelder_pflicht(self):
        v = self.lead(4, vollstaendig=True)
        kunde = self.s.get(Kunde, v.kunde_id)
        kunde.objektart = "MFH"
        self.s.commit()
        seite = self.kartei(v).text
        self.assertIn("Anzahl Parteien", seite)
        self.assertIn("Rechnungsadresse", seite)
        self.assertIn("2 Pflichtfelder offen", seite)
        self.assertIn('id="lk-mfh" class="lk-mfh" ', seite)   # sichtbar (nicht hidden)

    def test_lead_kopf_der_akte_verlinkt_kartei(self):
        v = self.lead(5)
        akte = self.client.get(f"/vorgaenge/{v.id}").text
        self.assertIn("Zur Kundenkartei", akte)
        self.assertIn(f"/lead-management/lead/{v.id}", akte)
        self.assertIn("Kontaktstatus:", akte)      # v21-Test erwartet den Satz weiter
        self.assertIn('class="lm-dots', akte)

    def test_tab_parameter_und_timeline_karten(self):
        v = self.lead(6)
        kern.aktivitaet(self.s, v.id, "anruf", "Anruf: Nicht erreicht – Mailbox voll",
                        ergebnis="nicht_erreicht", dauer_sek=95)
        self.s.commit()
        seite = self.kartei(v, tab="anrufe").text
        self.assertIn('id="tab-anrufe" class="lk-tab" data-tab="anrufe"\n'
                      '                aria-controls="panel-anrufe" aria-selected="true"', seite)
        self.assertIn("1:35 Min", seite)
        self.assertIn('data-typ="anruf"', seite)
        self.assertIn("Mailbox voll", seite)


class Stammdaten(Basis):
    def test_speichern_inkl_mfh_kanal_einwilligung(self):
        v = self.lead(10)
        r = self.client.post(f"/lead-management/lead/{v.id}/stammdaten", data={
            "anrede": "Frau", "vorname": "Vera", "nachname": f"{NACHNAME}-10",
            "telefon": "0203 880010", "email": "v2k10@test.local",
            "strasse": "Königstraße 5", "plz": "47051", "ort": "Duisburg",
            "vertriebskanal": "Enni", "interesse_feld": "1", "interesse": ["WP", "PV"],
            "objektart": "MFH", "parteien": "6",
            "rechnung_name": "WEG Königstraße", "rechnung_strasse": "Königstraße 5",
            "rechnung_plz": "47051", "rechnung_ort": "Duisburg",
            "einwilligung_feld": "1", "einwilligung_werbung": "1",
            "einwilligung_am": "2026-10-01", "einwilligung_quelle": "telefonisch",
            "tab": "timeline"}, follow_redirects=False)
        self.assertEqual(r.status_code, 303)
        self.assertIn("Gespeichert", r.headers["location"])
        self.assertIn("tab=timeline", r.headers["location"])
        self.s.expire_all()
        kunde = self.s.get(Kunde, v.kunde_id)
        v = self.s.get(Vorgang, v.id)
        self.assertEqual((kunde.anrede, kunde.vorname, kunde.strasse, kunde.plz),
                         ("Frau", "Vera", "Königstraße 5", "47051"))
        self.assertEqual(kunde.vertriebskanal, "Enni")
        self.assertTrue(kunde.kanal_manuell)
        self.assertEqual(kunde.interesse, "WP,PV")
        self.assertEqual((kunde.objektart, kunde.parteien), ("MFH", 6))
        self.assertEqual((kunde.rechnung_strasse, kunde.rechnung_ort), ("Königstraße 5", "Duisburg"))
        self.assertTrue(v.einwilligung_werbung)
        self.assertEqual(v.einwilligung_werbung_am.date(), datetime(2026, 10, 1).date())
        self.assertEqual(v.einwilligung_quelle, "telefonisch")
        texte = [a.text for a in self.aktivitaeten(v, "status")]
        self.assertTrue(any(t.startswith("Stammdaten geändert") and "Vertriebskanal" in t
                            and "Objektart" in t for t in texte), texte)
        self.assertTrue(any(t.startswith("Einwilligung Werbung: ja") for t in texte), texte)
        # alle Pflichtfelder (inkl. MFH-Zusatz) gefüllt
        self.assertEqual(lead_v2.pflichtfelder_offen(self.s, kunde, v), [])
        self.assertIn("0 Pflichtfelder offen", self.kartei(v).text)

    def test_fehler_rollt_zurueck(self):
        v = self.lead(11, vollstaendig=True)
        r = self.client.post(f"/lead-management/lead/{v.id}/stammdaten", data={
            "anrede": "Herr", "vorname": "X", "nachname": "", "firma": "",
            "telefon": "1", "email": "kaputt", "strasse": "a", "plz": "1", "ort": "b"},
            follow_redirects=False)
        self.assertIn("Nicht+gespeichert", r.headers["location"])
        self.s.expire_all()
        kunde = self.s.get(Kunde, v.kunde_id)
        self.assertEqual(kunde.nachname, f"{NACHNAME}-11")
        self.assertEqual(kunde.email, "v2k11@test.local")

    def test_teilformular_loescht_nichts(self):
        """Nur mitgeschickte Felder ändern sich (Inline-Bearbeitung aus Boards)."""
        v = self.lead(12, vollstaendig=True)
        r = self.client.post(f"/lead-management/lead/{v.id}/stammdaten",
                             data={"telefon": "0203 999999"}, follow_redirects=False)
        self.assertIn("Gespeichert+%281", r.headers["location"])
        self.s.expire_all()
        kunde = self.s.get(Kunde, v.kunde_id)
        self.assertEqual(kunde.telefon, "0203 999999")
        self.assertEqual((kunde.nachname, kunde.anrede, kunde.strasse, kunde.objektart,
                          kunde.vertriebskanal, kunde.interesse),
                         (f"{NACHNAME}-12", "Herr", "Sonnenwall 1", "EFH", "Standard", "WP"))


class Zuweisung(Basis):
    def test_aussendienst_schreibt_aktivitaet_und_glocke(self):
        v = self.lead(20)
        vorher = self.s.query(Benachrichtigung).filter_by(benutzer_id=self.ad.id).count()
        with glocken_arten(self.s, "zuweisung"):         # v29: Glocke nur mit eingeschalteter Art
            r = self.client.post(f"/lead-management/lead/{v.id}/aussendienst",
                                 data={"ad_id": str(self.ad.id)}, follow_redirects=False)
        self.assertEqual(r.status_code, 303)
        self.s.expire_all()
        self.assertEqual(self.s.get(Vorgang, v.id).ad_id, self.ad.id)
        texte = [a.text for a in self.aktivitaeten(v, "status")]
        self.assertTrue(any(t.startswith(f"Zugewiesen an {self.ad.name}") for t in texte), texte)
        glocken = (self.s.query(Benachrichtigung).filter_by(benutzer_id=self.ad.id)
                   .order_by(Benachrichtigung.id.desc()).all())
        self.assertEqual(len(glocken), vorher + 1)
        self.assertTrue(glocken[0].text.startswith("Lead zugewiesen"))
        self.assertEqual(glocken[0].link, f"/lead-management/lead/{v.id}")
        # Kartei zeigt den Zuständigen mit Initialen
        seite = self.kartei(v).text
        self.assertIn(f'value="{self.ad.id}"\n                                selected', seite)

    def test_innendienst_dropdown(self):
        v = self.lead(21)
        r = self.client.post(f"/lead-management/lead/{v.id}/innendienst",
                             data={"leadmanager_id": "1"}, follow_redirects=False)
        self.assertEqual(r.status_code, 303)
        self.s.expire_all()
        self.assertEqual(self.s.get(Vorgang, v.id).leadmanager_id, 1)
        texte = [a.text for a in self.aktivitaeten(v, "status")]
        self.assertIn("Leadmanager: Admin", texte)

    def test_ungueltige_ids_loeschen_keine_zuweisung(self):
        v = self.lead(23, leadmanager_id=1, ad_id=self.ad.id)
        vorher = len(self.aktivitaeten(v))
        r = self.client.post(f"/lead-management/lead/{v.id}/innendienst",
                             data={"leadmanager_id": "abc"}, follow_redirects=False)
        self.assertIn("ung%C3%BCltig", r.headers["location"])
        r = self.client.post(f"/lead-management/lead/{v.id}/aussendienst",
                             data={"ad_id": "x1"}, follow_redirects=False)
        self.assertIn("ung%C3%BCltig", r.headers["location"])
        self.s.expire_all()
        v = self.s.get(Vorgang, v.id)
        self.assertEqual((v.leadmanager_id, v.ad_id), (1, self.ad.id))
        self.assertEqual(len(self.aktivitaeten(v)), vorher)
        # leer = bewusst entfernen
        self.client.post(f"/lead-management/lead/{v.id}/aussendienst", data={"ad_id": ""},
                         follow_redirects=False)
        self.s.expire_all()
        self.assertIsNone(self.s.get(Vorgang, v.id).ad_id)

    def test_hv_ausschluss_deaktiviert_und_sperrt(self):
        v = self.lead(22)
        kunde = self.s.get(Kunde, v.kunde_id)
        kunde.vertriebskanal = "Enni"          # F14: nur Innendienst
        self.s.commit()
        seite = self.kartei(v).text
        self.assertIn("Handelsvertreter sind deshalb deaktiviert", seite)
        # HV-Option ist disabled, der angestellte AD nicht
        hv_pos = seite.index(f'value="{self.hv.id}"')
        self.assertIn("disabled", seite[hv_pos:hv_pos + 300])
        r = self.client.post(f"/lead-management/lead/{v.id}/aussendienst",
                             data={"ad_id": str(self.hv.id)}, follow_redirects=False)
        self.assertIn("Nicht+m", r.headers["location"])
        self.s.expire_all()
        self.assertIsNone(self.s.get(Vorgang, v.id).ad_id)
        # Admin darf übergehen (erzwingen)
        r = self.client.post(f"/lead-management/lead/{v.id}/aussendienst",
                             data={"ad_id": str(self.hv.id), "erzwingen": "1"},
                             follow_redirects=False)
        self.s.expire_all()
        self.assertEqual(self.s.get(Vorgang, v.id).ad_id, self.hv.id)


class Terminierung(Basis):
    def termin(self, vorgang, status="vorgemerkt", ad=None, tage=5):
        t = VotTermin(vorgang_id=vorgang.id, ad_id=(ad or self.ad).id,
                      beginn=(datetime.now() + timedelta(days=tage)).replace(hour=10, minute=0,
                                                                              second=0, microsecond=0),
                      status=status, quelle="assistent", demo=True, typ="vot", medium="vor_ort")
        t.ende = t.beginn + timedelta(minutes=90)
        self.s.add(t)
        self.s.commit()
        return t

    def test_button_gesperrt_ohne_termin_und_bei_pflichtfeldern(self):
        v = self.lead(30, vollstaendig=True)
        pruefung = lead_kartei.terminierung_pruefung(self.s, self.s.get(Kunde, v.kunde_id), v)
        self.assertFalse(pruefung["bereit"])
        self.assertEqual(pruefung["fehlend"], ["Termin (vorgemerkt/geplant)"])
        seite = self.kartei(v).text
        self.assertIn('class="knopf lk-terminierung" type="button" disabled', seite)
        self.assertIn("<li>Termin (vorgemerkt/geplant)</li>", seite)
        # POST trotzdem → abgewiesen, nichts verändert
        r = self.client.post(f"/lead-management/lead/{v.id}/terminierung", follow_redirects=False)
        self.assertIn("nicht+m", r.headers["location"])
        self.s.expire_all()
        self.assertNotEqual(self.s.get(Vorgang, v.id).lead_phase, "terminiert")
        # Termin da, aber Pflichtfeld offen → weiter gesperrt, Liste nennt beides nicht mehr nur Termin
        unvoll = self.lead(31)
        self.termin(unvoll)
        pruefung = lead_kartei.terminierung_pruefung(self.s, self.s.get(Kunde, unvoll.kunde_id), unvoll)
        self.assertFalse(pruefung["bereit"])
        self.assertIn("Anrede", pruefung["fehlend"])
        self.assertNotIn("Termin (vorgemerkt/geplant)", pruefung["fehlend"])

    def test_terminierung_freigegeben_und_ausgefuehrt(self):
        v = self.lead(32, vollstaendig=True, lead_phase="qualifiziert")
        t = self.termin(v, status="vorgemerkt")
        seite = self.kartei(v).text
        self.assertIn('class="knopf lk-terminierung" type="submit"', seite)
        self.assertNotIn("Terminierung gesperrt", seite)
        self.assertIn("Vorgemerkt", seite)
        vorher = self.s.query(Benachrichtigung).filter_by(benutzer_id=self.ad.id).count()
        with glocken_arten(self.s, "terminaenderung"):   # v29: Glocke nur mit eingeschalteter Art
            r = self.client.post(f"/lead-management/lead/{v.id}/terminierung", follow_redirects=False)
        self.assertEqual(r.status_code, 303)
        self.assertIn("Terminiert", r.headers["location"])
        self.s.expire_all()
        v = self.s.get(Vorgang, v.id)
        t = self.s.get(VotTermin, t.id)
        self.assertEqual(t.status, "geplant")
        self.assertEqual(v.lead_phase, "terminiert")
        self.assertIsNotNone(v.terminiert_am)
        self.assertEqual(v.ad_id, self.ad.id)
        mails = {m.vorlage_key: m for m in self.s.query(KommunikationLog)
                 .filter_by(vorgang_id=v.id, termin_id=t.id)}
        self.assertIn("terminbestaetigung", mails)
        self.assertIn("terminerinnerung", mails)
        self.assertEqual(mails["terminbestaetigung"].modus, "protokoll")   # Sendesperre Demo
        texte = [a.text for a in self.aktivitaeten(v, "termin")]
        self.assertTrue(any(x.startswith("Terminierung:") for x in texte), texte)
        glocken = (self.s.query(Benachrichtigung).filter_by(benutzer_id=self.ad.id)
                   .order_by(Benachrichtigung.id.desc()).all())
        self.assertEqual(len(glocken), vorher + 1)
        self.assertIn("terminiert", glocken[0].text)
        # zweiter Klick: bereits terminiert, keine zweite Bestätigung
        r = self.client.post(f"/lead-management/lead/{v.id}/terminierung", follow_redirects=False)
        self.assertIn("Bereits+terminiert", r.headers["location"])
        self.assertEqual(self.s.query(KommunikationLog)
                         .filter_by(termin_id=t.id, vorlage_key="terminbestaetigung").count(), 1)
        seite = self.kartei(v).text
        self.assertIn("Terminiert</button>", seite)

    def test_terminierung_nur_demo_leads(self):
        v = self.lead(33, vollstaendig=True)
        v.demo = False
        self.s.commit()
        self.termin(v)
        ok, meldung = lead_kartei.terminierung_ausfuehren(self.s, v)
        self.s.rollback()
        self.assertFalse(ok)
        self.assertIn("Demo-Modus", meldung)


class Aktionen(Basis):
    def test_vorab_angebot_kennzeichen_demo(self):
        v = self.lead(40, vollstaendig=True)
        r = self.client.post(f"/lead-management/lead/{v.id}/vorab-angebot", follow_redirects=False)
        self.assertEqual(r.status_code, 303)
        # Demo-Lead: zurück in die Kartei mit Hinweis statt in die Erfassung
        self.assertTrue(r.headers["location"].startswith(f"/lead-management/lead/{v.id}?meldung="))
        self.assertIn("Demo-Lead", r.headers["location"].replace("+", " "))
        self.s.expire_all()
        self.assertTrue(self.s.get(Vorgang, v.id).vorab_angebot)
        texte = [a.text for a in self.aktivitaeten(v, "status")]
        self.assertTrue(any(t.startswith("Vorab-Angebot") for t in texte), texte)
        seite = self.kartei(v).text
        self.assertIn(">Vorab-Angebot</span>", seite)
        # Nicht-Demo-Lead → Weiterleitung in die Erfassung (Pfad ohne VOT)
        meldung, ziel = lead_kartei.vorab_angebot_setzen(
            self.s, type("V", (), {"id": v.id, "kunde_id": v.kunde_id, "demo": False,
                                   "vorab_angebot": True, "lead_id": None})())
        self.assertEqual(ziel, f"/erfassung/sparten?kunde_id={v.kunde_id}")
        self.s.rollback()

    def test_nachbearbeitung_zurueckgestellt_mit_wiedervorlage(self):
        v = self.lead(41, vollstaendig=True, lead_phase="qualifiziert")
        r = self.client.post(f"/lead-management/lead/{v.id}/nachbearbeitung",
                             data={"notiz": "Finanzierung offen"}, follow_redirects=False)
        self.assertEqual(r.status_code, 303)
        self.s.expire_all()
        v = self.s.get(Vorgang, v.id)
        self.assertEqual(v.lead_phase, "zurueckgestellt")
        self.assertEqual(v.zurueckgestellt_grund, "Nachbearbeitung, noch nicht bereit für VOT")
        erwartet = (datetime.now() + timedelta(days=lead_kartei.wv_tage(self.s))).date()
        self.assertEqual(v.zurueckgestellt_bis.date(), erwartet)
        texte = [a.text for a in self.aktivitaeten(v, "status")]
        self.assertTrue(any("Nachbearbeitung" in t and "Finanzierung offen" in t for t in texte), texte)
        seite = self.kartei(v).text
        self.assertIn("Zurückgestellt", seite)
        self.assertIn("Nachbearbeitung, noch nicht bereit für VOT", seite)
        # Seitenzustand: Kopf bietet „Reaktivieren“ (Dialog Phase 107) statt Nachbearbeitung
        self.assertIn(f"dialogOeffnen('reaktivieren', {v.id})", seite)
        self.assertNotIn("dlg-nachbearbeitung').showModal()", seite)
        # Datum in der Vergangenheit wird abgewiesen
        r = self.client.post(f"/lead-management/lead/{v.id}/nachbearbeitung",
                             data={"bis": "2020-01-01"}, follow_redirects=False)
        self.assertIn("Vergangenheit", r.headers["location"])

    def test_wiedervorlage_und_zurueckstellen_dialog(self):
        v = self.lead(42)
        r = self.client.post(f"/lead-management/lead/{v.id}/wiedervorlage",
                             data={"art": "wiedervorlage", "wann": "2026-12-01T09:30",
                                   "notiz": "Rückruf nach Urlaub"}, follow_redirects=False)
        self.assertEqual(r.status_code, 303)
        self.s.expire_all()
        self.assertEqual(self.s.get(Vorgang, v.id).naechste_aktion_am, datetime(2026, 12, 1, 9, 30))
        self.assertTrue(any("Rückruf nach Urlaub" in a.text for a in self.aktivitaeten(v, "status")))
        r = self.client.post(f"/lead-management/lead/{v.id}/wiedervorlage",
                             data={"art": "zurueckstellen", "bis": "2026-11-15",
                                   "grund": "Bauphase später"}, follow_redirects=False)
        self.s.expire_all()
        v = self.s.get(Vorgang, v.id)
        self.assertEqual((v.lead_phase, v.zurueckgestellt_grund), ("zurueckgestellt", "Bauphase später"))
        # Sonstiges ohne Freitext → Fehler
        r = self.client.post(f"/lead-management/lead/{v.id}/wiedervorlage",
                             data={"art": "zurueckstellen", "bis": "2026-11-15",
                                   "grund": "Sonstiges"}, follow_redirects=False)
        self.assertIn("Freitext", r.headers["location"])

    def test_notiz_landet_im_chat(self):
        v = self.lead(43)
        r = self.client.post(f"/lead-management/lead/{v.id}/notiz",
                             data={"text": "Kartei-Notiz 43"}, follow_redirects=False)
        self.assertEqual(r.status_code, 303)
        self.assertTrue(self.s.query(VorgangsNotiz).filter_by(vorgang_id=v.id, text="Kartei-Notiz 43").count())
        seite = self.kartei(v).text
        self.assertIn("Kartei-Notiz 43", seite)
        self.assertIn('data-typ="notiz"', seite)

    def test_mail_verlauf_herkunft(self):
        v = self.lead(44)
        self.s.add(KommunikationLog(vorgang_id=v.id, kanal="mail", vorlage_key="nicht_erreicht",
                                    an="x@test.local", betreff="Automatik", status="protokolliert"))
        self.s.add(KommunikationLog(vorgang_id=v.id, kanal="mail", vorlage_key="eingangsbestaetigung",
                                    an="x@test.local", betreff="Eigene", status="protokolliert",
                                    erstellt_von=1))
        self.s.add(KommunikationLog(vorgang_id=v.id, kanal="mail", vorlage_key="nurture",
                                    an="x@test.local", betreff="Kollege", status="protokolliert",
                                    erstellt_von=self.ad.id))
        self.s.commit()
        mails = lead_kartei.mail_verlauf(self.s, v, self.s.get(Benutzer, 1),
                                         {b.id: b for b in self.s.query(Benutzer)})
        herkunft = {m["betreff"]: m["herkunft"] for m in mails}
        self.assertEqual(herkunft["Automatik"], "automatisiert")
        self.assertEqual(herkunft["Eigene"], "eigene")
        self.assertEqual(herkunft["Kollege"], "kollegen")
        seite = self.kartei(v, tab="mails").text
        self.assertIn('data-herkunft="kollegen"', seite)
        self.assertIn('id="lk-mail-richtung"', seite)

    def test_objektart_vorbelegung_wp_bogen(self):
        v = self.lead(45, vollstaendig=True)
        kunde = self.s.get(Kunde, v.kunde_id)
        kunde.objektart = "RH"
        self.s.commit()
        self.assertEqual(lead_kartei.objektart_vorbelegung(self.s, v)["O01"]["wert"], "RMH")
        kunde.objektart, kunde.parteien = "MFH", 4
        self.s.commit()
        vb = lead_kartei.objektart_vorbelegung(self.s, v)
        self.assertEqual((vb["O01"]["wert"], vb["O03"]["wert"]), ("MFH", "4"))
        kunde.objektart = None
        self.s.commit()
        self.assertEqual(lead_kartei.objektart_vorbelegung(self.s, v), {})


class Gate(Basis):
    def test_404_fuer_fremde_und_hv_nur_eigene(self):
        v = self.lead(50)
        # angestellter AD im Demo-Modus: Modul unsichtbar → 404
        ad_client = TestClient(app)
        ad_client.post("/login", data={"benutzer_id": str(self.ad.id), "pin": "4321"})
        self.assertEqual(ad_client.get(f"/lead-management/lead/{v.id}").status_code, 404)
        self.assertEqual(ad_client.post(f"/lead-management/lead/{v.id}/stammdaten",
                                        data={"nachname": "x"}).status_code, 404)
        # Handelsvertreter ohne Zuweisung → 404, mit Zuweisung → 200 und voll bearbeitbar
        hv_client = TestClient(app)
        hv_client.post("/login", data={"benutzer_id": str(self.hv.id), "pin": "4321"})
        self.assertEqual(hv_client.get(f"/lead-management/lead/{v.id}").status_code, 404)
        v.ad_id = self.hv.id
        self.s.commit()
        r = hv_client.get(f"/lead-management/lead/{v.id}")
        self.assertEqual(r.status_code, 200)
        self.assertNotIn("Lesesicht", r.text)
        self.assertIn('id="lk-stammdaten"', r.text)
        r = hv_client.post(f"/lead-management/lead/{v.id}/wiedervorlage",
                           data={"art": "wiedervorlage", "wann": "2026-12-02T10:00"},
                           follow_redirects=False)
        self.assertEqual(r.status_code, 303)
        # unbekannter Vorgang → 404
        self.assertEqual(self.client.get("/lead-management/lead/99999999").status_code, 404)

    def test_ad_lesesicht_read_only(self):
        """kern.lead_ad_sicht (nur bei lead_freigabe_modus = alle): angestellter AD
        sieht die Kartei seines Termins read-only; Schreibrouten bleiben 404."""
        v = self.lead(51, vollstaendig=True)
        t = VotTermin(vorgang_id=v.id, ad_id=self.ad.id, status="geplant", demo=True,
                      beginn=datetime.now() + timedelta(days=3))
        self.s.add(t)
        self.s.commit()
        ad_client = TestClient(app)
        ad_client.post("/login", data={"benutzer_id": str(self.ad.id), "pin": "4321"})
        # Freigabe „alle“ nur im Testprozess simulieren (kein Umstellen des
        # DB-Parameters – parallel laufende Tests setzen ihn sonst zurück)
        from unittest import mock
        with mock.patch.object(kern, "freigabe_modus", return_value="alle"):
            r = ad_client.get(f"/lead-management/lead/{v.id}")
            self.assertEqual(r.status_code, 200)
            self.assertIn("Lesesicht", r.text)
            self.assertIn("<fieldset disabled>", r.text)
            self.assertNotIn('action="/lead-management/lead/%d/aussendienst"' % v.id, r.text)
            self.assertIn("No-Show melden", r.text)           # eigener Termin
            self.assertIn(f'action="/vorgaenge/{v.id}/notiz"', r.text)   # Notiz über die Akte-Route
            self.assertEqual(ad_client.post(f"/lead-management/lead/{v.id}/stammdaten",
                                            data={"nachname": "x"}).status_code, 404)
            # fremder Vorgang bleibt unsichtbar
            fremd = self.lead(52)
            self.assertEqual(ad_client.get(f"/lead-management/lead/{fremd.id}").status_code, 404)


if __name__ == "__main__":
    unittest.main()
