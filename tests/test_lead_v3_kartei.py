# Tests PLAN_LEAD_V3 Phase 119 (CLAUDE v25): Kundenkartei neu aufgeteilt –
# Layout-Reihenfolge (Statuskette → Kundeninfo → Reiter → Blöcke), kein Score/
# Quelle/Einwilligung/Qualifizierung im HTML, Statuskette mit Label „Kontaktiert“,
# Reiter-Reihenfolge Termin · Anrufnotizen · E-Mail-Verlauf · Timeline,
# Autospeichern POST /lead/{id}/feld (Wert + Aktivität aenderung, ungültige PLZ →
# Fehler und alter Wert, doppelter Wert → keine neue Aktivität, Validierungen,
# Zuweisungen über lead_v2), Rechte (HV fremder Lead 404, AD read-only),
# Terminvorschläge im Block Termine (adresse_fehlt / hv_lead / laden, Kontrollwert
# „Demo-Lead ohne Adresse → Block Termine zeigt Adresse fehlt“), Terminierung-
# Button-Zustand, Lead-Kopf der Vorgangsakte ohne Score. Laufen im Demo-Modus
# gegen die Entwicklungs-DB; Testleads tragen den Nachnamen „LeadV3K-Test“.
import pathlib
import unittest
import warnings
from datetime import datetime, timedelta
from unittest import mock

warnings.filterwarnings("ignore")

from fastapi.testclient import TestClient

from app import auth, lead_kartei, lead_v2
from app import leadmanagement as kern
from app.db import SessionLocal, init_db
from app.main import app
from app.models import (AdProfil, Benachrichtigung, Benutzer, KommunikationLog,
                        Kunde, LeadAktivitaet, LeadQuelle, Todo, Vorgang,
                        VorgangsNotiz, VotTermin)

NACHNAME = "LeadV3K-Test"
BENUTZER_PRAEFIX = "LeadV3K "
JS = pathlib.Path(__file__).resolve().parent.parent / "app" / "static" / "lm_kartei.js"


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
        cls.ad = Benutzer(name=f"{BENUTZER_PRAEFIX}AD", rolle="aussendienst",
                          pin_hash=auth.pin_hash("4321"), email="lv3k-ad@test.local")
        cls.hv = Benutzer(name=f"{BENUTZER_PRAEFIX}HV", rolle="aussendienst",
                          pin_hash=auth.pin_hash("4321"), email="lv3k-hv@test.local")
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
                 "email": f"v3k{nr}@test.local"}
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

    def kartei(self, vorgang, client=None, **params):
        url = f"/lead-management/lead/{vorgang.id}"
        if params:
            url += "?" + "&".join(f"{k}={v}" for k, v in params.items())
        return (client or self.client).get(url)

    def eigen(self, seite):
        """Nur das eigene Markup der Kartei (Kopf bis vor die Dialoge/Makros)."""
        start = seite.index('<header class="karte lk-kopf')
        ende = seite.index("<dialog", start)
        return seite[start:ende]

    def feld(self, vorgang, feld, wert, client=None, **extra):
        daten = {"feld": feld, "wert": wert, **extra}
        return (client or self.client).post(f"/lead-management/lead/{vorgang.id}/feld", json=daten)

    def aktivitaeten(self, vorgang, typ=None):
        self.s.expire_all()
        q = self.s.query(LeadAktivitaet).filter_by(vorgang_id=vorgang.id)
        if typ:
            q = q.filter_by(typ=typ)
        return q.order_by(LeadAktivitaet.id).all()

    def kunde(self, vorgang):
        self.s.expire_all()
        return self.s.get(Kunde, vorgang.kunde_id)

    def termin(self, vorgang, status="vorgemerkt", ad=None, tage=5):
        t = VotTermin(vorgang_id=vorgang.id, ad_id=(ad or self.ad).id,
                      beginn=(datetime.now() + timedelta(days=tage)).replace(hour=10, minute=0,
                                                                              second=0, microsecond=0),
                      status=status, quelle="assistent", demo=True, typ="vot", medium="vor_ort")
        t.ende = t.beginn + timedelta(minutes=90)
        self.s.add(t)
        self.s.commit()
        return t


class Layout(Basis):
    def test_reihenfolge_statuskette_kundeninfo_reiter_bloecke(self):
        v = self.lead(1)
        r = self.kartei(v)
        self.assertEqual(r.status_code, 200)
        seite = r.text
        marker = ['class="lk-statuskette"', 'id="lk-terminierung-knopf"', 'class="lk-schnell"',
                  'id="lk-kundeninfo"', 'role="tablist"', 'id="lk-bloecke"']
        positionen = [seite.index(m) for m in marker]
        self.assertEqual(positionen, sorted(positionen), "Statuskette → Terminierung → Kundeninfo → Reiter → Blöcke")
        # Blöcke in voller Breite in der Reihenfolge Termine · Angebote · Erfassungen · Projekt · Anhänge · To-Dos
        bloecke = ["termine", "angebote", "erfassungen", "projekt", "anhaenge", "todos"]
        pos = [seite.index(f'data-bereich="{b}"') for b in bloecke]
        self.assertEqual(pos, sorted(pos))
        self.assertTrue(all(p > positionen[-1] for p in pos))
        # keine Spalten mehr
        for alt in ('class="karte lk-links"', 'class="lk-rechts"', 'class="lk-spalten"'):
            self.assertNotIn(alt, seite)
        # Schnellaktionen Anrufen · E-Mail · Notiz · Wiedervorlage als runde Icon-Buttons
        schnell = seite.split('class="lk-schnell"', 1)[1].split("</div>", 1)[0]
        for label in ("Anrufen", "E-Mail", "Notiz", "Wiedervorlage"):
            self.assertIn(label, schnell, label)
        self.assertEqual(schnell.count('class="lk-rund"'), 4)
        self.assertIn('href="tel:+49203880001"', schnell)   # E.164 Click-to-Call („0203 880001“)
        # Kundenname, Kanal-/Interessen-Badge im Kopf, Stoppuhr-Vertrag, Dialoge
        for text in (f"{NACHNAME}-1, V1", 'class="chip chip-wp', 'class="lm-anruf-form', 'name="dauer_sek"',
                     f'name="zurueck" value="/lead-management/lead/{v.id}?tab=anrufe"',
                     "lm_kartei.js", "lm_anruf.js", 'id="dlg-rueckruf"', 'id="dlg-keininteresse"',
                     "Nachbearbeitung", "Vorab-Gespräch", "Erfassung ohne Termin", "Termin manuell",
                     'action="/lead-management/todos/neu"', 'class="demo-badge"'):
            self.assertIn(text, seite, text)

    def test_kein_score_quelle_einwilligung_qualifizierung(self):
        v = self.lead(2, vollstaendig=True)
        v.score_punkte, v.score_klasse = 42, "B"
        v.einwilligung_werbung = True
        self.s.commit()
        eigen = self.eigen(self.kartei(v).text)
        for verboten in ("Score", "Einwilligung", "Qualifizierung", "Quelle", "Kampagne",
                         'name="quelle_id"', 'id="tab-qualifizierung"', 'id="tab-vorgang"',
                         "42 · B", 'name="einwilligung_werbung"'):
            self.assertNotIn(verboten, eigen, verboten)
        # Pflichtfeld-Zähler, rote Umrandung und Stern bleiben
        unvoll = self.lead(3)
        seite = self.kartei(unvoll).text
        self.assertIn("lk-pflicht-offen", seite)
        self.assertIn('<abbr title="Pflichtfeld">*</abbr>', seite)
        offen = lead_v2.pflichtfelder_offen(self.s, self.s.get(Kunde, unvoll.kunde_id), unvoll)
        self.assertEqual(seite.count(f'<span data-pflicht-text>{len(offen)} Pflichtfelder offen</span>'), 2,
                         "Zähler im Kopf und über dem Kundeninfo-Block")

    def test_statuskette_label_kontaktiert_fuer_beide_phasen(self):
        for phase in ("in_kontaktierung", "qualifiziert"):
            v = self.lead(4 if phase == "in_kontaktierung" else 5, lead_phase=phase)
            seite = self.kartei(v).text
            kette = seite.split('class="lk-statuskette"', 1)[1].split("</ol>", 1)[0]
            aktiv = kette.split('aria-current="step"', 1)
            self.assertEqual(len(aktiv), 2, "genau ein aktiver Schritt")
            self.assertIn(">Kontaktiert</li>", aktiv[1].split("</li>", 1)[0] + "</li>")
            self.assertIn('data-phasen="in_kontaktierung,qualifiziert"', kette)
            self.assertEqual(kette.count(">Kontaktiert</li>"), 1)
            self.assertNotIn("Qualifiziert", kette)
            self.assertNotIn("In Kontaktierung", kette)
        # Seitenzustand hängt als eigener Schritt an
        z = self.lead(6, lead_phase="zurueckgestellt")
        kette = self.kartei(z).text.split('class="lk-statuskette"', 1)[1].split("</ol>", 1)[0]
        self.assertIn('class="lk-schritt seitenzustand aktiv"', kette)

    def test_phasen_kette_helfer(self):
        class Z:
            def __init__(self, label, farbe=""):
                self.label, self.farbe = label, farbe

        class Logik:
            def __init__(self, labels):
                self.labels = labels

            def status_zeile(self, phase):
                return Z(self.labels[phase]) if phase in self.labels else None

        zusammen = Logik({"in_kontaktierung": "Kontaktiert", "qualifiziert": "Kontaktiert"})
        kette = lead_kartei.phasen_kette(zusammen, "qualifiziert")
        self.assertEqual([s["label"] for s in kette],
                         ["Neu", "Kontaktiert", "Terminiert", "Erfasst", "Angebot", "Gewonnen"])
        self.assertEqual(kette[1]["phasen"], ["in_kontaktierung", "qualifiziert"])
        self.assertTrue(kette[1]["aktiv"] and kette[0]["fertig"] and not kette[2]["fertig"])
        getrennt = lead_kartei.phasen_kette(Logik({}), "neu")
        self.assertEqual(len(getrennt), 7)
        self.assertTrue(getrennt[0]["aktiv"])
        self.assertEqual(lead_kartei.phasen_label(zusammen, "qualifiziert"), "Kontaktiert")
        self.assertEqual(lead_kartei.phasen_label(Logik({}), "nicht_erreicht"), "Nicht erreicht")

    def test_reiter_reihenfolge_und_standard_termin(self):
        v = self.lead(7)
        seite = self.kartei(v).text
        ids = ['id="tab-termin"', 'id="tab-anrufe"', 'id="tab-mails"', 'id="tab-timeline"']
        pos = [seite.index(i) for i in ids]
        self.assertEqual(pos, sorted(pos))
        self.assertNotIn('id="tab-qualifizierung"', seite)
        self.assertNotIn('id="tab-vorgang"', seite)
        self.assertEqual(seite.count('role="tab"'), 4)
        self.assertIn('data-tab="termin"\n                aria-controls="panel-termin" aria-selected="true"', seite)
        self.assertIn('id="panel-termin" aria-labelledby="tab-termin" class="lk-panel" >', seite)
        self.assertIn('id="panel-timeline" aria-labelledby="tab-timeline" class="lk-panel" hidden', seite)
        # Icons mit Tooltip bleiben
        self.assertIn('aria-label="E-Mail-Verlauf" title="E-Mail-Verlauf"', seite)
        # ?tab=anrufe öffnet Anrufnotizen, alte Werte fallen auf Termin zurück
        self.assertIn('data-tab="anrufe"\n                aria-controls="panel-anrufe" aria-selected="true"',
                      self.kartei(v, tab="anrufe").text)
        for alt in ("qualifizierung", "vorgang", "xyz"):
            self.assertIn('id="panel-termin" aria-labelledby="tab-termin" class="lk-panel" >',
                          self.kartei(v, tab=alt).text)
        # Anruf-Buttons: Nicht erreicht/Besetzt/Mailbox ohne Dialog, Rückruf/Kein Interesse mit Dialog
        anruf = seite.split('class="lk-anruf"', 1)[1].split("</section>", 1)[0]
        self.assertIn('name="ergebnis" value="nicht_erreicht"', anruf)
        self.assertIn('name="ergebnis" value="besetzt"', anruf)
        self.assertIn('name="ergebnis" value="mailbox"', anruf)
        self.assertNotIn("dialogOeffnen('nichterreicht'", anruf)
        self.assertIn(f"dialogOeffnen('rueckruf', {v.id})", anruf)
        self.assertIn(f"dialogOeffnen('keininteresse', {v.id})", anruf)
        self.assertIn('action="/lead-management/anruf/%d"' % v.id, anruf)

    def test_kundeninfo_felder_und_kein_speichern_button(self):
        v = self.lead(8, vollstaendig=True)
        seite = self.kartei(v).text
        info = seite.split('id="lk-kundeninfo"', 1)[1].split("</form>", 1)[0]
        for feld in ("anrede", "vorname", "nachname", "telefon", "email", "strasse", "plz", "ort",
                     "vertriebskanal", "objektart", "parteien", "rechnung_strasse",
                     "leadmanager_id", "ad_id"):
            self.assertIn(f'data-feld="{feld}"', info, feld)
        self.assertIn('data-feld-gruppe="interesse"', info)
        self.assertIn(f'data-feld-url="/lead-management/lead/{v.id}/feld"', info)
        self.assertIn("Eingangsdatum", info)
        self.assertIn("Wunschzeiten", info)
        self.assertIn('href="tel:', info)
        self.assertIn(f'href="mailto:v3k8@test.local"', info)
        # kein Speichern-Button außer im <noscript>-Fallback
        self.assertNotIn('class="lk-dirty"', info)
        ohne_noscript = info.split("<noscript>")[0]
        self.assertNotIn("Speichern</button>", ohne_noscript)
        self.assertIn("<noscript>", info)
        self.assertIn('action="/lead-management/lead/%d/stammdaten"' % v.id, info)

    def test_terminierung_button_zustand(self):
        unvoll = self.lead(9)
        seite = self.kartei(unvoll).text
        self.assertIn('class="knopf lk-terminierung" type="button" disabled', seite)
        knopf = seite.split('id="lk-terminierung-knopf"', 1)[1].split(">", 1)[0]
        self.assertIn("Gesperrt – es fehlt:", knopf)
        self.assertIn("Anrede", knopf)
        self.assertIn("Termin (vorgemerkt/geplant)", knopf)
        self.assertIn("<li>Termin (vorgemerkt/geplant)</li>", seite)
        # Pflichtfelder voll + vorgemerkter Termin → aktiv (Logik B8 unverändert)
        voll = self.lead(10, vollstaendig=True, lead_phase="qualifiziert")
        self.termin(voll)
        seite = self.kartei(voll).text
        self.assertIn('class="knopf lk-terminierung" type="submit"', seite)
        # frei: kein „gesperrt“-Text mehr auf der Seite, nur der leere JS-Platzhalter
        self.assertNotIn("Terminierung gesperrt", seite)
        self.assertIn('<details class="lk-fehlliste" id="lk-fehlliste" hidden>', seite)
        # Button steht im Kopf (vor dem Kundeninfo-Block), auch unter 900 px (CSS order)
        self.assertLess(seite.index('id="lk-terminierung-knopf"'), seite.index('id="lk-kundeninfo"'))

    def test_lead_kopf_der_akte_ohne_score_mit_kontaktiert(self):
        v = self.lead(11, lead_phase="in_kontaktierung")
        akte = self.client.get(f"/vorgaenge/{v.id}").text
        self.assertIn("Zur Kundenkartei", akte)
        self.assertNotIn("Score:", akte)
        kopf = akte.split('class="karte lead-kopf"', 1)[1].split("</div>\n</div>", 1)[0]
        stepper = kopf.split('class="lead-stepper"', 1)[1].split("</div>", 1)[0]
        self.assertIn('class="schritt aktiv">Kontaktiert</span>', stepper)
        self.assertEqual(stepper.count("Kontaktiert"), 1)
        self.assertNotIn("Qualifiziert", stepper)
        self.assertIn("Kontaktstatus:", akte)
        self.assertIn("Quelle:", kopf)          # Quelle bleibt in der Akte (nur Kartei ohne)

    def test_css_und_js_vertrag(self):
        css = (JS.parent / "lead_v2.css").read_text(encoding="utf-8")
        self.assertIn("Phase 119", css)
        for regel in (".lk-statuskette", ".lk-rund", ".lk-info-raster", "@media (min-width: 1200px)",
                      "@media (min-width: 900px)", "@media (max-width: 900px)", ".lk-vorschlaege-liste",
                      ".lk-feld-status.ok", ".lk-feld-status.fehler"):
            self.assertIn(regel, css, regel)
        js = JS.read_text(encoding="utf-8")
        for text in ("feldSpeichern", "'blur'", "'change'", "dataset.letzter", "2000", "Vormerken",
                     "'assistent'", "vorschlaegeLaden", "adresse_fehlt", "hv_lead", "404",
                     "window.dialogOeffnen", "'2': 'nicht_erreicht'", "application/json",
                     "neu=1", "data-pflicht-text", "fehlliste-titel"):
            self.assertIn(text, js, text)
        self.assertNotIn("'nichterreicht'", js.split("Fallback dialogOeffnen")[0])


class Vorschlaege(Basis):
    def block(self, seite):
        return seite.split('id="lk-vorschlaege"', 1)[1].split("</div>\n        </div>", 1)[0]

    def test_kontrollwert_demo_lead_ohne_adresse_zeigt_adresse_fehlt(self):
        v = self.lead(20)                     # Straße fehlt
        seite = self.kartei(v).text
        block = self.block(seite)
        self.assertIn('data-zustand="adresse_fehlt"', block)
        self.assertIn("Adresse fehlt – Straße, PLZ und Ort eintragen", block)
        self.assertIn(f'data-url="/lead-management/lead/{v.id}/termin/vorschlaege.json"', block)
        self.assertIn(f'data-buchen="/lead-management/lead/{v.id}/termin"', block)
        self.assertIn('data-text-laden="Vorschläge werden berechnet …"', block)
        self.assertIn('data-text-fehler="Vorschläge derzeit nicht verfügbar"', block)
        self.assertIn("Alle Vorschläge / manuell", block)
        self.assertIn(f'href="/lead-management/lead/{v.id}/termin"', block)
        # Adresse per Autospeichern nachtragen → Zustand laden (Nachladen ohne Neuladen über JS)
        r = self.feld(v, "strasse", "Sonnenwall 1")
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.json()["adresse_vollstaendig"])
        block = self.block(self.kartei(v).text)
        self.assertIn('data-zustand="laden"', block)
        self.assertIn("Vorschläge werden berechnet …", block)
        # PLZ leeren → wieder Adresse fehlt
        kunde = self.kunde(v)
        kunde.plz = ""
        self.s.commit()
        self.assertIn('data-zustand="adresse_fehlt"', self.block(self.kartei(v).text))
        self.assertFalse(lead_kartei.adresse_vollstaendig(kunde))

    def test_hv_lead_hinweis_fuer_innendienst_nicht_fuer_hv(self):
        v = self.lead(21, vollstaendig=True, ad_id=self.hv.id)
        block = self.block(self.kartei(v).text)
        self.assertIn('data-zustand="hv_lead"', block)
        self.assertIn(f"Lead liegt bei {self.hv.name} (Handelsvertreter), Terminierung durch den Vertreter", block)
        self.assertIn(f'data-hv-name="{self.hv.name}"', block)
        zustand = lead_kartei.vorschlaege_zustand(self.s, v, self.s.get(Kunde, v.kunde_id), self.s.get(Benutzer, 1))
        self.assertEqual(zustand["status"], "hv_lead")
        # der Handelsvertreter selbst bekommt Vorschläge (nur für sich – Agent D)
        hv_client = TestClient(app)
        hv_client.post("/login", data={"benutzer_id": str(self.hv.id), "pin": "4321"})
        r = self.kartei(v, client=hv_client)
        self.assertEqual(r.status_code, 200)
        self.assertIn('data-zustand="laden"', self.block(r.text))
        # angestellter AD als Zuständiger → kein HV-Hinweis
        v2 = self.lead(22, vollstaendig=True, ad_id=self.ad.id)
        self.assertIn('data-zustand="laden"', self.block(self.kartei(v2).text))
        # HV-Lead OHNE Adresse: HV-Hinweis geht vor (gleiche Reihenfolge wie
        # lead_termin.vorschlaege_json – der Innendienst terminiert hier ohnehin nicht)
        v3 = self.lead(26, ad_id=self.hv.id)
        block = self.block(self.kartei(v3).text)
        self.assertIn('data-zustand="hv_lead"', block)
        hinweis = block.split('data-rolle="hinweis"', 1)[1].split("</p>", 1)[0]
        self.assertIn(f"Lead liegt bei {self.hv.name} (Handelsvertreter)", hinweis)
        self.assertNotIn("Adresse fehlt", hinweis)
        # der HV selbst sieht an seinem Lead ohne Adresse den Adresshinweis
        self.assertIn('data-zustand="adresse_fehlt"', self.block(self.kartei(v3, client=hv_client).text))

    def test_vorschlaege_block_nicht_in_lesesicht(self):
        v = self.lead(23, vollstaendig=True)
        self.s.add(VotTermin(vorgang_id=v.id, ad_id=self.ad.id, status="geplant", demo=True,
                             beginn=datetime.now() + timedelta(days=3)))
        self.s.commit()
        ad_client = TestClient(app)
        ad_client.post("/login", data={"benutzer_id": str(self.ad.id), "pin": "4321"})
        with mock.patch.object(kern, "freigabe_modus", return_value="alle"):
            seite = ad_client.get(f"/lead-management/lead/{v.id}").text
        self.assertIn("Lesesicht", seite)
        self.assertNotIn('id="lk-vorschlaege"', seite)
        self.assertIn('data-bereich="termine"', seite)

    def test_vorschlaege_route_antwortform(self):
        """Vertrag mit Agent D (lm_termin): GET …/termin/vorschlaege.json → {status, hinweis,
        vorschlaege}. Fehlt die Route noch, zeigt die Kartei den 404-Hinweis (JS) –
        der Test wird dann übersprungen."""
        v = self.lead(24, vollstaendig=True)
        r = self.client.get(f"/lead-management/lead/{v.id}/termin/vorschlaege.json",
                            headers={"Accept": "application/json"})
        if r.status_code == 404:
            self.skipTest("Route vorschlaege.json (Agent D) noch nicht vorhanden")
        self.assertEqual(r.status_code, 200)
        d = r.json()
        self.assertIn(d.get("status"), ("ok", "adresse_fehlt", "hv_lead", "keine"))
        self.assertIsInstance(d.get("vorschlaege", []), list)
        for e in d.get("vorschlaege", [])[:5]:
            for key in ("ad_id", "ad_name", "beginn", "beginn_text", "begruendung"):
                self.assertIn(key, e)
        ohne = self.lead(25)
        r = self.client.get(f"/lead-management/lead/{ohne.id}/termin/vorschlaege.json")
        if r.status_code == 200:
            self.assertEqual(r.json().get("status"), "adresse_fehlt")


class Autospeichern(Basis):
    def test_feld_aendern_wert_und_aktivitaet(self):
        v = self.lead(30)
        r = self.feld(v, "telefon", "  0203 / 55 66 77 ")
        self.assertEqual(r.status_code, 200, r.text)
        d = r.json()
        self.assertTrue(d["ok"])
        self.assertEqual(d["wert"], "0203 / 55 66 77")        # normalisiert (getrimmt)
        self.assertEqual(d["feld"], "telefon")
        self.assertIsInstance(d["pflicht_offen"], list)
        self.assertEqual(d["pflicht_anzahl"], len(d["pflicht_offen"]))
        self.assertIn("terminierung", d)
        self.assertEqual(self.kunde(v).telefon, "0203 / 55 66 77")
        akt = self.aktivitaeten(v, "aenderung")
        self.assertEqual(len(akt), 1)
        self.assertEqual(akt[0].text, "Telefon: „0203 880030“ → „0203 / 55 66 77“")
        self.assertEqual(akt[0].benutzer_id, 1)
        # Timeline zeigt die Änderung als eigene Gruppe „Änderungen“ (Filter-Chip) mit Titel
        timeline = self.kartei(v, tab="timeline").text
        self.assertIn("Telefon: „0203 880030“ → „0203 / 55 66 77“", timeline)
        self.assertIn('data-typ="aenderung"', timeline)
        self.assertIn('<span class="lk-karte-titel">Änderung: Telefon</span>', timeline)
        self.assertIn('<input type="checkbox" value="aenderung" checked> Änderungen', timeline)
        # Straße setzen → Pflichtfeld-Zähler sinkt in der Antwort
        vorher = d["pflicht_anzahl"]
        d = self.feld(v, "strasse", "Königstraße 5").json()
        self.assertEqual(d["pflicht_anzahl"], vorher - 1)
        self.assertNotIn("strasse", d["pflicht_keys"])

    def test_ungueltige_plz_fehler_und_alter_wert(self):
        v = self.lead(31, vollstaendig=True)
        vorher = len(self.aktivitaeten(v))
        r = self.feld(v, "plz", "12")
        self.assertEqual(r.status_code, 400)
        d = r.json()
        self.assertFalse(d["ok"])
        self.assertEqual(d["meldung"], "PLZ muss aus 5 Ziffern bestehen.")
        self.assertEqual(d["wert"], "47139")                    # alter Wert bleibt
        self.assertEqual(self.kunde(v).plz, "47139")
        self.assertEqual(len(self.aktivitaeten(v)), vorher)
        self.assertEqual(self.feld(v, "plz", "4713a").status_code, 400)
        # gültig: Leerzeichen werden entfernt
        d = self.feld(v, "plz", "47 051").json()
        self.assertTrue(d["ok"])
        self.assertEqual((d["wert"], self.kunde(v).plz), ("47051", "47051"))
        self.assertEqual(self.aktivitaeten(v, "aenderung")[-1].text, "PLZ: „47139“ → „47051“")

    def test_doppelter_wert_keine_neue_aktivitaet(self):
        v = self.lead(32)
        d = self.feld(v, "vorname", "V32").json()
        self.assertTrue(d["ok"])
        self.assertFalse(d["geaendert"])
        self.assertEqual(d["meldung"], "Keine Änderung.")
        self.assertEqual(self.aktivitaeten(v, "aenderung"), [])
        self.feld(v, "vorname", "Vera")
        self.assertEqual(len(self.aktivitaeten(v, "aenderung")), 1)
        d = self.feld(v, "vorname", " Vera ").json()
        self.assertFalse(d["geaendert"])
        self.assertEqual(len(self.aktivitaeten(v, "aenderung")), 1)
        # leer → leer ebenfalls keine Aktivität
        d = self.feld(v, "firma", "").json()
        self.assertFalse(d["geaendert"])
        self.assertEqual(len(self.aktivitaeten(v, "aenderung")), 1)

    def test_validierungen(self):
        v = self.lead(33, vollstaendig=True)
        kanaele = kern.kanal_werte(self.s)
        faelle = [("email", "kaputt", 400), ("email", "neu@test.local", 200),
                  ("anrede", "Dr.", 400), ("anrede", "Frau", 200),
                  ("telefon", "abc", 400), ("telefon", "12", 400), ("telefon", "+49 203 123456", 200),
                  ("objektart", "XYZ", 400), ("objektart", "mfh", 200),
                  ("parteien", "abc", 400), ("parteien", "0", 400), ("parteien", "4", 200),
                  ("vertriebskanal", "Gibtsnicht", 400), ("vertriebskanal", kanaele[-1], 200),
                  ("interesse", ["WP", "XX"], 400), ("interesse", ["PV", "WP"], 200),
                  ("nachname", "", 400)]
        for feld, wert, status in faelle:
            r = self.feld(v, feld, wert)
            self.assertEqual(r.status_code, status, f"{feld}={wert!r}: {r.text}")
        kunde = self.kunde(v)
        self.assertEqual((kunde.email, kunde.anrede, kunde.telefon), ("neu@test.local", "Frau", "+49 203 123456"))
        self.assertEqual((kunde.objektart, kunde.parteien), ("MFH", 4))
        self.assertEqual(kunde.vertriebskanal, kanaele[-1])
        self.assertTrue(kunde.kanal_manuell)
        self.assertEqual(kunde.interesse, "WP,PV")                 # Reihenfolge der Codes
        self.assertEqual(kunde.nachname, f"{NACHNAME}-33")
        texte = [a.text for a in self.aktivitaeten(v, "aenderung")]
        self.assertIn("Interessen: „WP“ → „WP, PV“", texte)
        self.assertIn("Objektart: „EFH“ → „MFH“", texte)
        # MFH → Pflichtfelder Parteien/Rechnungsadresse in der Antwort
        d = self.feld(v, "rechnung_strasse", "Königstraße 5").json()
        self.assertIn("Rechnungsadresse", d["pflicht_offen"])
        d = self.feld(v, "rechnung_ort", "Duisburg").json()
        self.assertNotIn("Rechnungsadresse", d["pflicht_offen"])
        # Interessen als Komma-String (Form-Fallback)
        r = self.client.post(f"/lead-management/lead/{v.id}/feld",
                             data={"feld": "interesse", "wert": "KL,WP"})
        self.assertEqual(r.status_code, 200, r.text)
        self.assertEqual(self.kunde(v).interesse, "WP,KL")
        # unbekannte / entfernte Felder
        for feld in ("score_punkte", "quelle_id", "einwilligung_werbung", "eingang_am", "id"):
            r = self.feld(v, feld, "1")
            self.assertEqual(r.status_code, 400, feld)
            self.assertEqual(r.json()["meldung"], "Feld unbekannt.")

    def test_zuweisungen_ueber_lead_v2(self):
        v = self.lead(34)
        d = self.feld(v, "leadmanager_id", "1").json()
        self.assertTrue(d["ok"])
        self.assertEqual(d["wert"], "1")
        self.s.expire_all()
        self.assertEqual(self.s.get(Vorgang, v.id).leadmanager_id, 1)
        self.assertIn("Leadmanager: Admin", [a.text for a in self.aktivitaeten(v, "status")])
        self.assertEqual(self.aktivitaeten(v, "aenderung"), [])     # eigene Aktivität des Helfers
        d = self.feld(v, "leadmanager_id", "1").json()
        self.assertFalse(d["geaendert"])
        vorher = self.s.query(Benachrichtigung).filter_by(benutzer_id=self.ad.id).count()
        d = self.feld(v, "ad_id", str(self.ad.id)).json()
        self.assertTrue(d["ok"])
        self.assertEqual(d["meldung"], f"Zugewiesen an {self.ad.name}.")
        self.s.expire_all()
        self.assertEqual(self.s.get(Vorgang, v.id).ad_id, self.ad.id)
        self.assertEqual(self.s.query(Benachrichtigung).filter_by(benutzer_id=self.ad.id).count(), vorher + 1)
        self.assertEqual(self.feld(v, "ad_id", "x1").status_code, 400)
        self.assertEqual(self.feld(v, "ad_id", "999999").status_code, 400)
        self.s.expire_all()
        self.assertEqual(self.s.get(Vorgang, v.id).ad_id, self.ad.id)
        # Ausschluss F14: Handelsvertreter bei Ausschlusskanal nur mit erzwingen
        kunde = self.kunde(v)
        kunde.vertriebskanal = "Enni"
        self.s.commit()
        r = self.feld(v, "ad_id", str(self.hv.id))
        self.assertEqual(r.status_code, 400)
        self.assertIn("Nicht möglich", r.json()["meldung"])
        self.assertEqual(r.json()["wert"], str(self.ad.id))
        r = self.feld(v, "ad_id", str(self.hv.id), erzwingen="1")
        self.assertEqual(r.status_code, 200, r.text)
        self.s.expire_all()
        self.assertEqual(self.s.get(Vorgang, v.id).ad_id, self.hv.id)
        # leer = Zuweisung entfernen
        d = self.feld(v, "ad_id", "").json()
        self.assertTrue(d["ok"])
        self.s.expire_all()
        self.assertIsNone(self.s.get(Vorgang, v.id).ad_id)

    def test_adresse_leert_vorschlaege_cache(self):
        v = self.lead(35, vollstaendig=True)
        with mock.patch.object(lead_kartei, "vorschlaege_cache_leeren") as leeren:
            self.feld(v, "vorname", "Vicky")
            leeren.assert_not_called()
            self.feld(v, "ort", "Moers")
            leeren.assert_called_once_with(v.id)
            leeren.reset_mock()
            self.feld(v, "ort", "Moers")          # unverändert → kein Leeren
            leeren.assert_not_called()
            self.feld(v, "plz", "1")              # Fehler → kein Leeren
            leeren.assert_not_called()
        # defensiver Helfer gegen die konkrete Cache-Form von Agent D
        lead_kartei.vorschlaege_cache_leeren(v.id)
        lead_kartei.vorschlaege_cache_leeren(-1)

    def test_fallback_stammdaten_route_bleibt(self):
        v = self.lead(36, vollstaendig=True)
        r = self.client.post(f"/lead-management/lead/{v.id}/stammdaten",
                             data={"telefon": "0203 999999", "tab": "timeline"}, follow_redirects=False)
        self.assertEqual(r.status_code, 303)
        self.assertIn("Gespeichert", r.headers["location"])
        self.assertIn("tab=timeline", r.headers["location"])
        self.assertEqual(self.kunde(v).telefon, "0203 999999")


class Rechte(Basis):
    def test_hv_fremder_lead_404_eigener_lead_ok(self):
        v = self.lead(40)
        hv_client = TestClient(app)
        hv_client.post("/login", data={"benutzer_id": str(self.hv.id), "pin": "4321"})
        self.assertEqual(self.kartei(v, client=hv_client).status_code, 404)
        self.assertEqual(self.feld(v, "ort", "Moers", client=hv_client).status_code, 404)
        self.assertEqual(self.kunde(v).ort, "Duisburg")
        v.ad_id = self.hv.id
        self.s.commit()
        r = self.kartei(v, client=hv_client)
        self.assertEqual(r.status_code, 200)
        self.assertNotIn("Lesesicht", r.text)
        self.assertIn('data-readonly=""', r.text)
        r = self.feld(v, "ort", "Moers", client=hv_client)
        self.assertEqual(r.status_code, 200, r.text)
        self.assertEqual(self.kunde(v).ort, "Moers")
        self.assertEqual(self.aktivitaeten(v, "aenderung")[-1].benutzer_id, self.hv.id)
        # unbekannter Vorgang
        self.assertEqual(self.client.post("/lead-management/lead/99999999/feld",
                                          json={"feld": "ort", "wert": "x"}).status_code, 404)

    def test_ad_read_only(self):
        v = self.lead(41, vollstaendig=True)
        ad_client = TestClient(app)
        ad_client.post("/login", data={"benutzer_id": str(self.ad.id), "pin": "4321"})
        # Demo-Modus: Modul für angestellte AD unsichtbar → 404 ohne Formular
        self.assertEqual(self.kartei(v, client=ad_client).status_code, 404)
        self.assertEqual(self.feld(v, "ort", "Moers", client=ad_client).status_code, 404)
        # Lesesicht (lead_freigabe_modus = alle, eigener Termin): Formular gesperrt, kein Autospeichern
        self.s.add(VotTermin(vorgang_id=v.id, ad_id=self.ad.id, status="geplant", demo=True,
                             beginn=datetime.now() + timedelta(days=3)))
        self.s.commit()
        with mock.patch.object(kern, "freigabe_modus", return_value="alle"):
            r = self.kartei(v, client=ad_client)
            self.assertEqual(r.status_code, 200)
            self.assertIn("Lesesicht", r.text)
            self.assertIn('data-readonly="1"', r.text)
            self.assertIn("<fieldset disabled>", r.text)
            self.assertNotIn('data-feld="ad_id"', r.text)
            self.assertNotIn('id="lk-terminierung-knopf"', r.text)
            self.assertEqual(self.feld(v, "ort", "Moers", client=ad_client).status_code, 404)
        self.assertEqual(self.kunde(v).ort, "Duisburg")


if __name__ == "__main__":
    unittest.main()
