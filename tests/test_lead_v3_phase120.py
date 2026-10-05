# Tests PLAN_LEAD_V3 Phase 120 (CLAUDE v25, Agent D): Score zentral abgeschaltet
# (Parameter score_aktiv, Standard aus – Eingang ohne score_punkte/score_klasse,
# score_berechnen/qualifizierung_abschliessen ohne Score, erfassungs_vorbelegung
# leer, Pipeline-Wert nur nach Phasen-Quote, Qualifizierungsroute zeigt die
# Hinweisseite „Qualifizierung ist abgeschaltet“, Parametrierung speichert
# score_aktiv/ohne_schritt_tage, Logik-Import-Hinweise), Terminassistent ohne
# Handelsvertreter (Innendienst bekommt keinen HV-Kandidaten, der HV selbst
# schon – Kontrollwert René Golaschewski; HV-Lead → Hinweis; manuelle Buchung
# auf einen HV bleibt möglich), GET /lead/{id}/termin/vorschlaege.json
# (Zustände ok|adresse_fehlt|hv_lead|keine, Cache 10 Minuten je Lead mit
# Invalidierung), Dashboard „Ohne nächsten Schritt“ (Parameter
# ohne_schritt_tage), Trichter-Stufe „Kontaktiert“ = in_kontaktierung +
# qualifiziert, HV-Ansicht/Übersicht/Statistik/Kanal-Report ohne Score, Score
# nirgends im HTML der eigenen Seiten. Laufen im Demo-Modus gegen die
# Entwicklungs-DB; Testleads tragen den Nachnamen „LeadV3P-Test“, Testbenutzer
# das Präfix „LeadV3P “ – alles wird aufgeräumt.
import json
import re
import unittest
import warnings
from datetime import datetime, timedelta
from urllib.parse import unquote_plus

warnings.filterwarnings("ignore")

from fastapi.testclient import TestClient

from app import auth, lead_dashboard, lead_termin, lead_v2, leadmanagement_logik
from app import lead_handelsvertreter as hv_modul
from app import leadmanagement as kern
from app.db import SessionLocal, init_db
from app.main import app
from app.models import (ANRUF_ERGEBNIS_NAMEN, AdProfil, Benachrichtigung, Benutzer,
                        KommunikationLog, Kunde, LeadAktivitaet, LeadQualifizierung,
                        LeadQuelle, Todo, Vorgang, VotTermin)

NACHNAME = "LeadV3P-Test"
PRAEFIX = "LeadV3P "
KANAL = "LeadV3P-Kanal"
# Bezugspunkt abseits aller echten/Demo-Leads (Nordsee, wie test_lead_v2_termin)
BASIS = (54.3, 7.6)
SCORE_MUSTER = re.compile(r"\bScore\b|\bKlasse [ABC]\b|score_klasse|Score-Klasse")


def inhalt(text: str) -> str:
    """Nur der Seiteninhalt – Kopfzeile/Glocke bleiben außen vor."""
    return text.split("<main", 1)[-1]


def aufraeumen(s):
    s.rollback()
    for k in s.query(Kunde).filter(Kunde.nachname.like(f"{NACHNAME}%")):
        for v in s.query(Vorgang).filter_by(kunde_id=k.id):
            s.query(LeadAktivitaet).filter_by(vorgang_id=v.id).delete()
            s.query(KommunikationLog).filter_by(vorgang_id=v.id).delete()
            s.query(VotTermin).filter_by(vorgang_id=v.id).delete()
            s.query(LeadQualifizierung).filter_by(vorgang_id=v.id).delete()
            s.query(Todo).filter_by(vorgang_id=v.id).delete()
            s.query(Benachrichtigung).filter(
                Benachrichtigung.link == f"/lead-management/lead/{v.id}").delete()
            lead_termin.vorschlaege_cache_leeren(v.id)
            s.delete(v)
        s.delete(k)
    for b in s.query(Benutzer).filter(Benutzer.name.like(f"{PRAEFIX}%")):
        s.query(AdProfil).filter_by(benutzer_id=b.id).delete()
        s.query(VotTermin).filter_by(ad_id=b.id).delete()
        s.query(Benachrichtigung).filter_by(benutzer_id=b.id).delete()
        s.delete(b)
    s.commit()


def naechster_werktag(tage_voraus: int = 3) -> datetime:
    tag = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    tag += timedelta(days=tage_voraus)
    while tag.weekday() >= 5:
        tag += timedelta(days=1)
    return tag


class Basis(unittest.TestCase):
    PARAMETER = ("lead_freigabe_modus", "score_aktiv", "ohne_schritt_tage",
                 "kanal_ad_regel", "routing_anbieter", "kalender_sync", "mail_modus")

    @classmethod
    def setUpClass(cls):
        init_db()
        cls.s = SessionLocal()
        aufraeumen(cls.s)
        cls.client = TestClient(app)
        cls.client.post("/login", data={"benutzer_id": "1", "pin": "1234"})
        cls.gesichert = {n: kern.parameter_holen(cls.s, n, "") for n in cls.PARAMETER}
        kern.parameter_setzen(cls.s, "lead_freigabe_modus", "admin")
        kern.parameter_setzen(cls.s, "score_aktiv", "aus")
        kern.parameter_setzen(cls.s, "ohne_schritt_tage", "2")
        kern.parameter_setzen(cls.s, "kanal_ad_regel", "")
        kern.parameter_setzen(cls.s, "routing_anbieter", "luftlinie")
        kern.parameter_setzen(cls.s, "kalender_sync", "aus")
        kern.parameter_setzen(cls.s, "mail_modus", "protokoll")
        cls.s.commit()
        cls.admin = cls.s.get(Benutzer, 1)
        cls.innen = cls.benutzer("Innen", rolle="innendienst")
        cls.horst = cls.ad("Horst", ["WP", "PV", "KL", "WB"], kombi=True, mfh=True)
        cls.hv = cls.ad("Hv", ["WP", "PV", "KL", "WB"], kombi=True, mfh=True,
                        terminiert_selbst=True)
        cls.inaktiv = cls.ad("Inaktiv", ["WP"], aktiv_terminierung=False)
        cls.s.commit()
        lead_termin.vorschlaege_cache_leeren()

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
        b = Benutzer(name=f"{PRAEFIX}{name}", rolle=rolle, aktiv=True,
                     email=f"{name.lower()}@lv3p.local", telefon="0203 1",
                     pin_hash=auth.pin_hash("4321"), **extra)
        cls.s.add(b)
        cls.s.flush()
        return b

    @classmethod
    def ad(cls, name, sparten, kombi=False, mfh=False, terminiert_selbst=False,
           aktiv_terminierung=True):
        b = cls.benutzer(name)
        cls.s.add(AdProfil(
            benutzer_id=b.id, start_adresse="Duisburg",
            start_lat=BASIS[0], start_lon=BASIS[1],
            arbeitszeiten=json.dumps({t: ["08:00", "18:00"] for t in ("mo", "di", "mi", "do", "fr")}),
            termin_dauer_min=90, puffer_min=30, max_termine_tag=3,
            gebiet_plz_praefixe=json.dumps([]), aktiv_terminierung=aktiv_terminierung,
            terminiert_selbst=terminiert_selbst, kompetenz_sparten=json.dumps(sparten),
            kompetenz_kombi=kombi, kompetenz_mfh=mfh, kompetenz_gewerbe=False))
        cls.s.flush()
        return b

    @staticmethod
    def cookie_client(benutzer):
        c = TestClient(app)
        c.cookies.set(auth.COOKIE_NAME, auth.cookie_wert(benutzer.id))
        return c

    def lead(self, nr, sparten=("WP",), komplett=True, phase="neu", kanal=KANAL,
             leadmanager_id=None, **extra):
        quelle = self.s.query(LeadQuelle).filter_by(key="website").first()
        daten = {"anrede": "Herr", "vorname": f"V{nr}", "nachname": f"{NACHNAME}-{nr}",
                 "plz": "47139", "ort": "Duisburg", "telefon": f"0203 33{nr:04d}",
                 "sparten": list(sparten), "email": f"v3p{nr}@test.local",
                 "strasse": f"Teststraße {nr}" if komplett else ""}
        vorgang, _ = kern.lead_anlegen(self.s, daten, quelle, "api", entscheidung="neu")
        kunde = self.s.get(Kunde, vorgang.kunde_id)
        kunde.vertriebskanal = kanal
        kunde.objektart = "EFH"
        vorgang.demo = True
        vorgang.lead_phase = phase
        vorgang.leadmanager_id = leadmanager_id
        vorgang.naechste_aktion_am = None
        vorgang.lat, vorgang.lon, vorgang.geocode_status = BASIS[0], BASIS[1], "ok"
        for k, v in extra.items():
            setattr(vorgang, k, v)
        self.s.commit()
        return vorgang

    def kunde(self, vorgang):
        return self.s.get(Kunde, vorgang.kunde_id)

    def anruf(self, vorgang, tage: float, ergebnis="nicht_erreicht"):
        akt = kern.aktivitaet(self.s, vorgang.id, "anruf",
                              ANRUF_ERGEBNIS_NAMEN.get(ergebnis, ergebnis),
                              benutzer=self.admin, ergebnis=ergebnis)
        akt.zeitpunkt = datetime.now() - timedelta(days=tage)
        self.s.commit()
        return akt

    def termin(self, vorgang, ad, beginn, status="geplant"):
        t = VotTermin(vorgang_id=vorgang.id, ad_id=ad.id, beginn=beginn,
                      ende=beginn + timedelta(minutes=90), adresse="Teststraße, 47139 Duisburg",
                      lat=BASIS[0], lon=BASIS[1], status=status, quelle="manuell", typ="vot",
                      medium="vor_ort", demo=True)
        self.s.add(t)
        self.s.commit()
        return t

    def json_vorschlaege(self, vorgang, client=None, neu=False):
        r = (client or self.client).get(
            f"/lead-management/lead/{vorgang.id}/termin/vorschlaege.json" + ("?neu=1" if neu else ""))
        self.assertEqual(r.status_code, 200, r.text)
        return r.json()


# --- 1. Score aus -------------------------------------------------------------------

class ScoreAus(Basis):
    def test_schalter_standard_aus(self):
        self.assertEqual(kern.PARAMETER_START["score_aktiv"], "aus")
        self.assertEqual(kern.PARAMETER_START["ohne_schritt_tage"], "2")
        self.assertFalse(lead_v2.score_aktiv(self.s))
        self.assertFalse(kern.score_aktiv(self.s))

    def test_eingang_ohne_score(self):
        v = self.lead(1)
        self.assertIsNone(v.score_punkte)
        self.assertIsNone(v.score_klasse)
        self.assertEqual(self.s.query(LeadQualifizierung).filter_by(vorgang_id=v.id).count(), 0)
        # score_vorlaeufig ist bei aus ohne Wirkung
        kern.score_vorlaeufig(self.s, v)
        self.assertIsNone(v.score_punkte)
        # Gegenprobe: mit score_aktiv = an rechnet der Eingang wie in V2
        kern.parameter_setzen(self.s, "score_aktiv", "an")
        self.s.commit()
        try:
            v2 = self.lead(2)
            self.assertIsNotNone(v2.score_punkte)
            self.assertIn(v2.score_klasse, ("A", "B", "C"))
        finally:
            kern.parameter_setzen(self.s, "score_aktiv", "aus")
            self.s.commit()

    def test_score_berechnen_qualifizierung_und_vorbelegung_ohne_score(self):
        v = self.lead(3)
        self.assertEqual(kern.score_berechnen(self.s, v), (0, ""))
        self.assertIsNone(v.score_punkte)
        zeile = kern.qualifizierung_abschliessen(self.s, v, "WP", {}, benutzer=self.admin)
        self.s.commit()
        self.assertFalse(zeile.score_punkte)
        self.assertIsNone(v.score_klasse)
        self.assertEqual(v.lead_phase, "qualifiziert")
        texte = [a.text for a in self.s.query(LeadAktivitaet)
                 .filter_by(vorgang_id=v.id, typ="status")]
        self.assertIn("Qualifiziert WP", texte)
        self.assertFalse(any("Punkte" in t for t in texte))
        # Vorbelegung des Erfassungsbogens aus der Qualifizierung entfällt
        self.assertEqual(kern.erfassungs_vorbelegung(self.s, v), {})

    def _pipeline_anteil(self, vorgang, phase: str) -> int:
        """Beitrag EINES Leads zum (globalen) Pipeline-Wert: Differenz zwischen
        „nicht gezählt“ (Phase unqualifiziert) und der gewünschten Phase. Die
        Dev-DB wird parallel von anderen Testläufen beschrieben – bei einer
        Störung zwischen den beiden Messungen wird kurz wiederholt."""
        try:
            for _ in range(5):
                vorgang.lead_phase = "unqualifiziert"
                self.s.commit()
                ohne = kern.pipeline_wert(self.s)
                vorgang.lead_phase = phase
                self.s.commit()
                mit = kern.pipeline_wert(self.s)
                vorgang.lead_phase = "unqualifiziert"
                self.s.commit()
                if kern.pipeline_wert(self.s) == ohne:     # Umgebung unverändert
                    return mit - ohne
            self.fail("Pipeline-Wert nicht stabil messbar (parallele Schreibzugriffe)")
        finally:
            vorgang.lead_phase = phase
            self.s.commit()

    def test_pipeline_wert_ohne_score(self):
        v = self.lead(4, phase="neu")
        quote = int(kern.parameter_holen(self.s, "quote_neu", "0"))
        erwartung = kern.erwartungswert(self.s, self.kunde(v)) * quote // 100
        self.assertGreater(erwartung, 0)
        self.assertEqual(self._pipeline_anteil(v, "neu"), erwartung)
        # Score/Klasse ändern nichts am Pipeline-Wert (nur Phasen-Quote)
        v.score_klasse, v.score_punkte = "A", 95
        self.s.commit()
        self.assertEqual(self._pipeline_anteil(v, "neu"), erwartung)
        v.score_klasse, v.score_punkte = "C", 1
        self.s.commit()
        self.assertEqual(self._pipeline_anteil(v, "neu"), erwartung)
        quote_q = int(kern.parameter_holen(self.s, "quote_qualifiziert", "0"))
        self.assertEqual(self._pipeline_anteil(v, "qualifiziert"),
                         kern.erwartungswert(self.s, self.kunde(v)) * quote_q // 100)
        # Erwartungswert selbst kennt keine Score-Gewichtung (nur Sparten-Parameter)
        self.assertEqual(kern.erwartungswert(self.s, self.kunde(v)),
                         int(kern.parameter_holen(self.s, "erwartungswert_WP", "0")))

    def test_qualifizierungsroute_hinweisseite(self):
        v = self.lead(5)
        url = f"/lead-management/lead/{v.id}/qualifizierung/WP"
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)
        seite = inhalt(r.text)
        self.assertIn("<h1>Qualifizierung ist abgeschaltet</h1>", seite)
        self.assertIn("lm-quali-aus", seite)
        self.assertIn(f'href="/lead-management/lead/{v.id}?tab=termin"', seite)
        self.assertNotIn('name="antwort', seite)
        # POST: kein Bogen – zurück in die Kartei (Reiter Termin), nichts gespeichert
        r = self.client.post(url, data={"abschliessen": "1"}, follow_redirects=False)
        self.assertEqual(r.status_code, 303)
        ziel = unquote_plus(r.headers["location"])
        self.assertTrue(ziel.startswith(f"/lead-management/lead/{v.id}?tab=termin"), ziel)
        self.assertIn("Qualifizierung ist abgeschaltet", ziel)
        self.s.expire_all()
        self.assertEqual(self.s.query(LeadQualifizierung).filter_by(vorgang_id=v.id).count(), 0)
        self.assertEqual(self.s.get(Vorgang, v.id).lead_phase, "neu")
        # Gegenprobe: bei an erscheint der Bogen
        kern.parameter_setzen(self.s, "score_aktiv", "an")
        self.s.commit()
        try:
            r = self.client.get(url)
            self.assertEqual(r.status_code, 200)
            self.assertNotIn("lm-quali-aus", r.text)
        finally:
            kern.parameter_setzen(self.s, "score_aktiv", "aus")
            self.s.commit()

    def test_parametrierung_speichert_score_und_tage(self):
        r = self.client.get("/parametrierung/lead-einstellungen")
        self.assertEqual(r.status_code, 200)
        self.assertIn('name="score_aktiv"', r.text)
        self.assertIn('<option value="aus" selected', r.text)
        self.assertIn('name="ohne_schritt_tage"', r.text)
        self.assertIn("Ohne nächsten Schritt", r.text)
        protokoll_vorher = kern.parameter_holen(self.s, "einstellungs_protokoll", "")
        try:
            r = self.client.post("/parametrierung/lead-einstellungen",
                                 data={"score_aktiv": "an", "ohne_schritt_tage": "4"},
                                 follow_redirects=False)
            self.assertEqual(r.status_code, 303)
            self.s.expire_all()
            self.assertEqual(kern.parameter_holen(self.s, "score_aktiv"), "an")
            self.assertEqual(kern.parameter_holen(self.s, "ohne_schritt_tage"), "4")
            self.assertTrue(lead_v2.score_aktiv(self.s))
            self.assertEqual(lead_dashboard.ohne_schritt_tage(self.s), 4)
            self.assertIn("score_aktiv aus → an",
                          kern.parameter_holen(self.s, "einstellungs_protokoll", ""))
            seite = self.client.get("/parametrierung/lead-einstellungen").text
            self.assertIn('<option value="an" selected', seite)
            self.assertIn('name="ohne_schritt_tage" min="0" max="365" value="4"', seite)
            # ungültige Werte werden nicht übernommen
            self.client.post("/parametrierung/lead-einstellungen",
                             data={"score_aktiv": "vielleicht", "ohne_schritt_tage": "-3"},
                             follow_redirects=False)
            self.s.expire_all()
            self.assertEqual(kern.parameter_holen(self.s, "score_aktiv"), "an")
            self.assertEqual(kern.parameter_holen(self.s, "ohne_schritt_tage"), "4")
        finally:
            r = self.client.post("/parametrierung/lead-einstellungen",
                                 data={"score_aktiv": "aus", "ohne_schritt_tage": "2"},
                                 follow_redirects=False)
            self.assertEqual(r.status_code, 303)
            kern.parameter_setzen(self.s, "einstellungs_protokoll", protokoll_vorher)
            self.s.commit()
            self.s.expire_all()
        self.assertEqual(kern.parameter_holen(self.s, "score_aktiv"), "aus")
        self.assertEqual(kern.parameter_holen(self.s, "ohne_schritt_tage"), "2")

    def test_logik_seite_meldet_blaetter_nicht_aktiv_und_label_hinweis(self):
        r = self.client.get("/parametrierung/lead-logik")
        self.assertEqual(r.status_code, 200)
        self.assertIn("Blätter Qualifizierung/Scoring/Klassen vorhanden, nicht aktiv", r.text)
        self.assertIn("zwei Phasen dürfen dasselbe Label tragen", r.text)
        self.assertIn("<code>in_kontaktierung</code>", r.text)
        # Blatt Status: beide Kontakt-Phasen tragen dasselbe Label (Steuerdatei)
        logik = leadmanagement_logik.hole_logik()
        self.assertEqual(logik.status_zeile("in_kontaktierung").label, "Kontaktiert")
        self.assertEqual(logik.status_zeile("qualifiziert").label, "Kontaktiert")
        self.assertEqual(logik.board_label("terminiert"), "Deals")
        self.assertEqual(logik.board_label("hauptboard"), "Hauptboard")


# --- 2. Terminassistent ohne Handelsvertreter -----------------------------------------

class Assistent(Basis):
    def namen(self, liste):
        return [k["ad"].name.replace(PRAEFIX, "") for k in liste
                if k["ad"].name.startswith(PRAEFIX)]

    def test_innendienst_kein_hv_kandidat_hv_selbst_schon(self):
        v = self.lead(10)
        # Innendienst (und Aufruf ohne Benutzer): HV ausgeschlossen, Begründung wörtlich
        for benutzer in (self.innen, self.admin, None):
            erg = lead_termin.kandidaten(self.s, v, benutzer=benutzer)
            self.assertIn("Horst", self.namen(erg["kandidaten"]))
            self.assertNotIn("Hv", self.namen(erg["kandidaten"]))
            hv_eintrag = next(a for a in erg["ausgeschlossen"] if a["ad"].id == self.hv.id)
            self.assertEqual(hv_eintrag["grund"], "Handelsvertreter terminieren ihre Leads selbst")
            self.assertTrue(hv_eintrag["manuell_erlaubt"])
            self.assertIn(self.hv.id, [a.id for a in erg["hv_manuell"]])
            self.assertIsNone(erg["hv_lead"])
            self.assertEqual(erg["hv_hinweis"], "")
            # „Terminierung nicht aktiv“ bleibt ein harter Ausschluss (nicht manuell)
            inaktiv = next(a for a in erg["ausgeschlossen"] if a["ad"].id == self.inaktiv.id)
            self.assertFalse(inaktiv["manuell_erlaubt"])
        # der Handelsvertreter selbst: nur er (eigener Kalender)
        erg = lead_termin.kandidaten(self.s, v, benutzer=self.hv)
        self.assertEqual([k["ad"].id for k in erg["kandidaten"]], [self.hv.id])
        self.assertIsNone(erg["hv_lead"])
        # Vorschläge des Innendienstes enthalten nie den HV
        ergebnis = lead_termin.vorschlaege(self.s, v, benutzer=self.innen)
        self.assertTrue(ergebnis["vorschlaege"])
        self.assertNotIn(self.hv.id, {x["ad"].id for x in ergebnis["vorschlaege"]})
        self.assertIn(self.hv.id, {a.id for a in ergebnis["hv_manuell"]})

    def test_hv_lead_hinweis_fuer_innendienst(self):
        v = self.lead(11, ad_id=self.hv.id)
        erg = lead_termin.kandidaten(self.s, v, benutzer=self.innen)
        self.assertEqual(erg["hv_lead"].id, self.hv.id)
        self.assertEqual(erg["hv_hinweis"],
                         f"Lead liegt bei {self.hv.name} (Handelsvertreter), Terminierung durch den Vertreter")
        self.assertNotIn("Hv", self.namen(erg["kandidaten"]))
        erg = lead_termin.kandidaten(self.s, v, benutzer=self.hv)
        self.assertIsNone(erg["hv_lead"])
        self.assertEqual([k["ad"].id for k in erg["kandidaten"]], [self.hv.id])
        # Assistent-Seite (Innendienst = Admin im Demo): Hinweis, HV nur manuell, kein Score
        seite = inhalt(self.client.get(f"/lead-management/lead/{v.id}/termin").text)
        self.assertIn("lmt-hv-hinweis", seite)
        self.assertIn(f"Lead liegt bei {self.hv.name} (Handelsvertreter), Terminierung durch den Vertreter", seite)
        self.assertIn("Handelsvertreter terminieren ihre Leads selbst", seite)
        self.assertIn('<optgroup label="Handelsvertreter (nur manuell)">', seite)
        self.assertIsNone(SCORE_MUSTER.search(seite), SCORE_MUSTER.search(seite))

    def test_kontrollwert_rene_golaschewski(self):
        rene = next((b for b in self.s.query(Benutzer).filter(Benutzer.aktiv.is_(True))
                     if "golaschewski" in b.name.lower()), None)
        if rene is None or not lead_v2.ist_handelsvertreter(self.s, rene):
            self.skipTest("René Golaschewski ist in dieser DB kein gekennzeichneter Handelsvertreter")
        v = self.lead(12, ad_id=rene.id)
        # Innendienst: Hinweis, René kein Kandidat
        erg = lead_termin.kandidaten(self.s, v, benutzer=self.innen)
        self.assertEqual(erg["hv_lead"].id, rene.id)
        self.assertEqual(erg["hv_hinweis"],
                         f"Lead liegt bei {rene.name} (Handelsvertreter), Terminierung durch den Vertreter")
        self.assertNotIn(rene.id, {k["ad"].id for k in erg["kandidaten"]})
        d = self.json_vorschlaege(v)
        self.assertEqual(d["status"], "hv_lead")
        self.assertEqual(d["hv_name"], rene.name)
        self.assertEqual(d["vorschlaege"], [])
        # René selbst: Vorschläge nur für sich
        erg = lead_termin.kandidaten(self.s, v, benutzer=rene)
        self.assertEqual([k["ad"].id for k in erg["kandidaten"]], [rene.id])
        self.assertIsNone(erg["hv_lead"])
        d = self.json_vorschlaege(v, client=self.cookie_client(rene))
        self.assertIn(d["status"], ("ok", "keine"))
        self.assertEqual([k["ad_id"] for k in d.get("kandidaten", [])], [rene.id])
        self.assertTrue(all(e["ad_id"] == rene.id for e in d["vorschlaege"]))

    def test_termin_seite_label_kontaktiert_ohne_score(self):
        v = self.lead(13, phase="in_kontaktierung", score_klasse="C", score_punkte=12)
        r = self.client.get(f"/lead-management/lead/{v.id}/termin")
        self.assertEqual(r.status_code, 200)
        seite = inhalt(r.text)
        self.assertIn('title="Phase laut Blatt Status">Kontaktiert</span>', seite)
        self.assertNotIn("Klasse C", seite)
        self.assertNotIn("Score C – Termin trotzdem buchen?", seite)
        self.assertIsNone(SCORE_MUSTER.search(seite), SCORE_MUSTER.search(seite))
        self.assertIn("Handelsvertreter · Abwertung", seite)

    def test_manuelle_buchung_auf_hv_bleibt_moeglich(self):
        v = self.lead(14)
        tag = naechster_werktag(5)
        r = self.client.post(f"/lead-management/lead/{v.id}/termin/manuell",
                             data={"datum": tag.strftime("%Y-%m-%d"), "uhrzeit": "10:00",
                                   "ad_id": str(self.hv.id)}, follow_redirects=False)
        self.assertEqual(r.status_code, 303, r.text)
        self.assertNotIn("nicht+w", r.headers["location"])
        self.s.expire_all()
        t = self.s.query(VotTermin).filter_by(vorgang_id=v.id).one()
        self.assertEqual(t.ad_id, self.hv.id)
        self.assertEqual(t.quelle, "manuell")
        self.assertEqual(self.s.get(Vorgang, v.id).ad_id, self.hv.id)
        # ein AD mit hartem Ausschluss (Terminierung nicht aktiv) bleibt auch manuell gesperrt
        w = self.lead(15)
        r = self.client.post(f"/lead-management/lead/{w.id}/termin/manuell",
                             data={"datum": tag.strftime("%Y-%m-%d"), "uhrzeit": "14:00",
                                   "ad_id": str(self.inaktiv.id)}, follow_redirects=False)
        self.assertEqual(r.status_code, 303)
        self.assertIn("nicht+w", r.headers["location"])
        self.s.expire_all()
        self.assertEqual(self.s.query(VotTermin).filter_by(vorgang_id=w.id).count(), 0)


# --- vorschlaege.json ----------------------------------------------------------------

class VorschlaegeJson(Basis):
    def test_zustaende(self):
        # adresse_fehlt
        ohne = self.lead(20, komplett=False)
        d = self.json_vorschlaege(ohne)
        self.assertEqual(d["status"], "adresse_fehlt")
        self.assertEqual(d["hinweis"], lead_termin.ADRESSE_HINWEIS)
        self.assertEqual(d["fehlt"], ["Straße"])
        self.assertEqual(d["vorschlaege"], [])
        self.assertEqual(d["vorgang_id"], ohne.id)
        self.assertEqual(d["buchen_url"], f"/lead-management/lead/{ohne.id}/termin")
        # hv_lead
        hv_lead = self.lead(21, ad_id=self.hv.id)
        d = self.json_vorschlaege(hv_lead)
        self.assertEqual(d["status"], "hv_lead")
        self.assertEqual(d["hinweis"],
                         f"Lead liegt bei {self.hv.name} (Handelsvertreter), Terminierung durch den Vertreter")
        self.assertEqual(d["hv_id"], self.hv.id)
        self.assertEqual(d["vorschlaege"], [])
        # ok – Top 5 mit Vertragsfeldern, nie der HV
        ok = self.lead(22)
        d = self.json_vorschlaege(ok)
        self.assertEqual(d["status"], "ok", d)
        self.assertTrue(1 <= len(d["vorschlaege"]) <= 5)
        for e in d["vorschlaege"]:
            for key in ("ad_id", "ad_name", "beginn", "beginn_text", "begruendung", "umweg_min"):
                self.assertIn(key, e)
            self.assertRegex(e["beginn"], r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}$")
            self.assertRegex(e["beginn_text"], r"\d{2}\.\d{2}\.\d{4} · \d{2}:\d{2} Uhr$")
            self.assertIsInstance(e["umweg_min"], int)
            self.assertNotEqual(e["ad_id"], self.hv.id)
        self.assertIn(self.horst.id, {e["ad_id"] for e in d["vorschlaege"]})
        self.assertNotIn(self.hv.id, {k["ad_id"] for k in d["kandidaten"]})
        self.assertTrue(d["buchbar"])
        self.assertFalse(d["aus_cache"])
        # keine – Kanal-Regel lässt nur einen AD zu, der nicht terminiert
        lead_termin.kanal_regel_setzen(self.s, {"LeadV3P-Keine": [self.inaktiv.id]})
        self.s.commit()
        try:
            keine = self.lead(23, kanal="LeadV3P-Keine")
            d = self.json_vorschlaege(keine)
            self.assertEqual(d["status"], "keine", d)
            self.assertIn("manuell setzen", d["hinweis"])
            self.assertEqual(d["vorschlaege"], [])
            self.assertEqual(d["kandidaten"], [])
        finally:
            kern.parameter_setzen(self.s, "kanal_ad_regel", "")
            self.s.commit()

    def test_cache_je_lead_mit_invalidierung(self):
        a = self.lead(24, komplett=False)
        b = self.lead(25)
        d1 = self.json_vorschlaege(a)
        self.assertEqual(d1["status"], "adresse_fehlt")
        self.assertFalse(d1["aus_cache"])
        d2 = self.json_vorschlaege(a)
        self.assertTrue(d2["aus_cache"])
        self.assertEqual(d2["berechnet_um"], d1["berechnet_um"])
        self.assertIn(a.id, lead_termin.vorschlaege_cache)
        db = self.json_vorschlaege(b)
        self.assertEqual(db["status"], "ok")
        self.assertTrue(self.json_vorschlaege(b)["aus_cache"])
        # Adresse nachgetragen: ohne Invalidierung bleibt der Cache stehen …
        self.kunde(a).strasse = "Sonnenwall 1"
        self.s.commit()
        self.assertEqual(self.json_vorschlaege(a)["status"], "adresse_fehlt")
        # … der Helfer für Agent C (Autospeichern) leert nur diesen Lead
        lead_termin.vorschlaege_cache_leeren(a.id)
        self.assertNotIn(a.id, lead_termin.vorschlaege_cache)
        self.assertIn(b.id, lead_termin.vorschlaege_cache)
        d3 = self.json_vorschlaege(a)
        self.assertEqual(d3["status"], "ok", d3)
        self.assertFalse(d3["aus_cache"])
        self.assertTrue(self.json_vorschlaege(b)["aus_cache"])
        # ?neu=1 erzwingt die Neuberechnung
        self.assertFalse(self.json_vorschlaege(b, neu=True)["aus_cache"])
        # Laufzeit 10 Minuten: danach wird neu gerechnet
        vorgang = self.s.get(Vorgang, b.id)
        spaeter = datetime.now() + timedelta(seconds=lead_termin.VORSCHLAEGE_CACHE_SEKUNDEN + 5)
        d4 = lead_termin.vorschlaege_json(self.s, vorgang, benutzer=self.admin, jetzt=spaeter)
        self.assertFalse(d4["aus_cache"])
        self.assertEqual(lead_termin.VORSCHLAEGE_CACHE_SEKUNDEN, 600)
        # Sichten getrennt: der HV bekommt seine eigene Berechnung
        c = self.lead(26, ad_id=self.hv.id)
        self.assertEqual(self.json_vorschlaege(c)["status"], "hv_lead")
        d_hv = self.json_vorschlaege(c, client=self.cookie_client(self.hv))
        self.assertIn(d_hv["status"], ("ok", "keine"))
        self.assertFalse(d_hv["aus_cache"])
        self.assertEqual([k["ad_id"] for k in d_hv["kandidaten"]], [self.hv.id])
        # Buchung leert den Cache komplett (Kalender geändert)
        termin, meldung, _ = lead_termin.termin_anlegen(
            self.s, b, self.horst.id, naechster_werktag(6) + timedelta(hours=9), benutzer=self.admin)
        self.s.commit()
        self.assertIsNotNone(termin, meldung)
        self.assertEqual(lead_termin.vorschlaege_cache, {})

    def test_fremder_lead_fuer_hv_404(self):
        v = self.lead(27)
        r = self.cookie_client(self.hv).get(f"/lead-management/lead/{v.id}/termin/vorschlaege.json")
        self.assertEqual(r.status_code, 404)
        self.assertEqual(self.client.get("/lead-management/lead/99999999/termin/vorschlaege.json").status_code, 404)


# --- 3. Dashboard „Ohne nächsten Schritt“ -------------------------------------------

class DashboardOhneSchritt(Basis):
    def test_liste_mit_parameter(self):
        jetzt = datetime.now()
        a = self.lead(30, phase="in_kontaktierung", versuch_nr=2)
        self.anruf(a, 3)
        wv = self.lead(31, phase="in_kontaktierung", versuch_nr=1,
                       naechste_aktion_am=jetzt + timedelta(days=1))
        self.anruf(wv, 3)
        zur = self.lead(32, phase="in_kontaktierung", versuch_nr=1,
                        zurueckgestellt_bis=jetzt + timedelta(days=3))
        self.anruf(zur, 3)
        mit_termin = self.lead(33, phase="in_kontaktierung", versuch_nr=1)
        self.anruf(mit_termin, 3)
        self.termin(mit_termin, self.horst, naechster_werktag(4) + timedelta(hours=10))
        frisch = self.lead(34, phase="in_kontaktierung", versuch_nr=1)
        self.anruf(frisch, 1)
        self.lead(35, phase="neu", versuch_nr=0)
        terminiert = self.lead(36, phase="terminiert", versuch_nr=2)
        self.anruf(terminiert, 3)
        q = self.lead(37, phase="qualifiziert", versuch_nr=1)
        self.anruf(q, 5, ergebnis="erreicht")
        fremd = self.lead(38, phase="in_kontaktierung", versuch_nr=1, leadmanager_id=self.innen.id)
        self.anruf(fremd, 3)
        abgesagt = self.lead(39, phase="in_kontaktierung", versuch_nr=1)
        self.anruf(abgesagt, 3)
        self.termin(abgesagt, self.horst, naechster_werktag(4) + timedelta(hours=14), status="abgesagt")

        jetzt = datetime.now()   # nach dem Anlegen – die Anrufe liegen exakt n Tage zurück
        liste = lead_dashboard.ohne_naechsten_schritt(self.s, self.admin, jetzt, hv=False)
        ids = [z["vorgang"].id for z in liste if z["vorgang"].id in
               {a.id, wv.id, zur.id, mit_termin.id, frisch.id, terminiert.id, q.id, fremd.id, abgesagt.id}]
        self.assertEqual(ids, [q.id, a.id, abgesagt.id])      # älteste zuerst
        z_a = next(z for z in liste if z["vorgang"].id == a.id)
        self.assertEqual(z_a["tage"], 3)
        self.assertEqual(z_a["versuche"], 2)
        self.assertEqual(z_a["ergebnis"], "Nicht erreicht")
        self.assertEqual(z_a["phase"], "Kontaktiert")
        self.assertTrue(z_a["frei"])
        z_q = next(z for z in liste if z["vorgang"].id == q.id)
        self.assertEqual(z_q["phase"], "Kontaktiert")          # Label aus dem Blatt Status
        self.assertEqual(z_q["ergebnis"], "Erreicht")
        # Parameter: 0 Tage → auch der frische Anruf steht in der Liste
        liste0 = lead_dashboard.ohne_naechsten_schritt(self.s, self.admin, jetzt, hv=False, tage=0)
        self.assertIn(frisch.id, [z["vorgang"].id for z in liste0])
        # Parameter aus den Lead-Einstellungen wirkt in daten()/Kachel
        kern.parameter_setzen(self.s, "ohne_schritt_tage", "0")
        self.s.commit()
        try:
            daten = lead_dashboard.daten(self.s, self.admin)
            self.assertEqual(daten["ohne_schritt_tage"], 0)
            self.assertIn(frisch.id, [z["vorgang"].id for z in daten["ohne_schritt"]])
            self.assertEqual(daten["kacheln"]["ohne_schritt"], len(daten["ohne_schritt"]))
        finally:
            kern.parameter_setzen(self.s, "ohne_schritt_tage", "2")
            self.s.commit()
        daten = lead_dashboard.daten(self.s, self.admin)
        self.assertEqual(daten["ohne_schritt_tage"], 2)
        self.assertNotIn(frisch.id, [z["vorgang"].id for z in daten["ohne_schritt"]])
        # Wiedervorlagen-Liste enthält nur die manuell gesetzte (wv), nicht a
        wv_ids = {z["vorgang"].id for z in daten["lead_wv"]}
        self.assertIn(wv.id, wv_ids)
        self.assertNotIn(a.id, wv_ids)
        # HV-Variante: eigene Leads über ad_id
        h = self.lead(40, phase="in_kontaktierung", versuch_nr=1, ad_id=self.hv.id)
        self.anruf(h, 3)
        liste_hv = lead_dashboard.ohne_naechsten_schritt(self.s, self.hv, jetzt, hv=True)
        self.assertEqual([z["vorgang"].id for z in liste_hv
                          if z["vorgang"].id in {h.id, a.id, q.id}], [h.id])
        # Seite: Kachel + Liste, Wiedervorlage-Formular, keine Kaskaden-Wiedervorlage
        r = self.client.get("/lead-management/dashboard")
        self.assertEqual(r.status_code, 200)
        seite = inhalt(r.text)
        self.assertIn("Ohne nächsten Schritt", seite)
        self.assertIn('href="#ohne-schritt"', seite)
        start = seite.index('id="ohne-schritt"')
        karte = seite[start:seite.index("Angebots-Wiedervorlagen", start)]
        self.assertIn(self.kunde(a).anzeige_name, karte)
        self.assertIn(self.kunde(q).anzeige_name, karte)
        self.assertNotIn(self.kunde(wv).anzeige_name, karte)
        self.assertNotIn(self.kunde(frisch).anzeige_name, karte)
        self.assertIn(f'action="/lead-management/dashboard/wiedervorlage/{a.id}"', karte)
        self.assertIn(f'href="/lead-management/lead/{a.id}/termin"', karte)
        self.assertIn("mehr als 2 Tagen", karte)
        self.assertNotIn("Kaskade", seite)

    def test_kaskade_setzt_keine_wiedervorlage_mehr(self):
        v = self.lead(41, phase="in_kontaktierung", versuch_nr=2)
        meldung = kern.kaskade_anwenden(self.s, v, benutzer=self.admin)
        self.s.commit()
        self.assertTrue(meldung.startswith("Versuch 2 protokolliert"))
        self.assertIsNone(v.naechste_aktion_am)
        jetzt = datetime.now()
        wv_ids = {z["vorgang"].id for z in lead_dashboard.lead_wiedervorlagen(
            self.s, self.admin, jetzt, 7, False)}
        self.assertNotIn(v.id, wv_ids)
        # manuell gesetzt → erscheint als Wiedervorlage
        v.naechste_aktion_am = jetzt + timedelta(hours=2)
        self.s.commit()
        zeilen = lead_dashboard.lead_wiedervorlagen(self.s, self.admin, jetzt, 7, False)
        z = next(z for z in zeilen if z["vorgang"].id == v.id)
        self.assertIn("Wiedervorlage", z["grund"])
        self.assertNotIn("Kaskade", z["grund"])

    def test_dashboard_links_und_board_namen(self):
        seite = inhalt(self.client.get("/lead-management/dashboard").text)
        for text in ("gruppe=", "quelle_typ=", "quelle_id=", "Info-Veranstaltung"):
            self.assertNotIn(text, seite, text)
        self.assertIn('<a href="/lead-management/terminiert">Deals</a>', seite)
        self.assertIn('<a href="/lead-management/hauptboard">Hauptboard</a>', seite)
        self.assertIn(">Infoabend<", seite)
        self.assertIsNone(SCORE_MUSTER.search(seite), SCORE_MUSTER.search(seite))
        # Phasen-Gruppe „Kontaktiert“ fasst beide Phasen zusammen
        self.lead(42, phase="in_kontaktierung", versuch_nr=1, leadmanager_id=1)
        self.lead(43, phase="qualifiziert", versuch_nr=1, leadmanager_id=1)
        gruppen = lead_dashboard.zugeteilte(self.s, self.admin, False)["gruppen"]
        kontakt = [g for g in gruppen if g["name"] == "Kontaktiert"]
        self.assertEqual(len(kontakt), 1)
        self.assertEqual(sorted(kontakt[0]["phasen"]), ["in_kontaktierung", "qualifiziert"])
        self.assertFalse(any(g["name"] == "Qualifiziert" for g in gruppen))


# --- 4. Trichter, Statistik, Übersicht, HV-Ansicht ------------------------------------

class StatistikTrichter(Basis):
    def test_kontaktiert_summe_beider_phasen(self):
        kanal = "LeadV3P-Trichter"
        jetzt = datetime.now()
        self.lead(50, kanal=kanal, phase="in_kontaktierung", versuch_nr=1, erstkontakt_am=jetzt)
        self.lead(51, kanal=kanal, phase="in_kontaktierung", versuch_nr=2, erstkontakt_am=jetzt,
                  erreicht_am=jetzt)
        self.lead(52, kanal=kanal, phase="qualifiziert", versuch_nr=1, erstkontakt_am=jetzt,
                  erreicht_am=jetzt)
        self.lead(53, kanal=kanal, phase="neu")
        d = kern.statistik_leads(self.s, jetzt - timedelta(days=1), jetzt + timedelta(days=1),
                                 {"kanal": kanal, "demo": True})
        stufen = {t["name"]: t["anzahl"] for t in d["trichter"]}
        namen = [t["name"] for t in d["trichter"]]
        self.assertEqual(stufen["Eingang"], 4)
        self.assertEqual(d["kontaktiert_label"], "Kontaktiert")
        self.assertEqual(stufen["Kontaktiert"], 3)
        self.assertEqual(d["kontaktiert"], 3)
        self.assertEqual(d["kontaktiert_phasen"], {"in_kontaktierung": 2, "qualifiziert": 1})
        self.assertEqual(namen[:2], ["Eingang", "Kontaktiert"])
        self.assertNotIn("qualifiziert", namen)
        self.assertNotIn("erreicht", namen)
        self.assertFalse(d["score_aktiv"])
        self.assertEqual(d["terminquote_kontaktiert"], 0)      # 0 Termine ÷ 3 Kontaktierte
        # Seite
        r = self.client.get(f"/lead-management/statistik?kanal={kanal}&demo=1")
        self.assertEqual(r.status_code, 200)
        seite = inhalt(r.text)
        self.assertIn("Terminquote (÷ Kontaktiert)", seite)
        self.assertIn("aktuell in Kontaktierung: 2 · qualifiziert: 1", seite)
        self.assertNotIn("Score-Verteilung", seite)
        self.assertIsNone(SCORE_MUSTER.search(seite), SCORE_MUSTER.search(seite))

    def test_uebersicht_und_kanal_report_ohne_score(self):
        r = self.client.get("/lead-management/uebersicht")
        self.assertEqual(r.status_code, 200)
        seite = inhalt(r.text)
        self.assertIsNone(SCORE_MUSTER.search(seite), SCORE_MUSTER.search(seite))
        self.assertNotIn("<th>qualifiziert</th>", seite)
        self.assertIn("Phasen-Quote", seite)
        for text in ("anrufliste?gruppe=", "quelle_typ=", "quelle_id="):
            self.assertNotIn(text, seite, text)
        self.assertNotIn("Kaskade:", seite.replace("Kaskade: Mail", ""))
        r = self.client.get("/lead-management/statistik/kanal")
        self.assertEqual(r.status_code, 200)
        self.assertIsNone(SCORE_MUSTER.search(inhalt(r.text)))


class HvAnsicht(Basis):
    def test_status_optionen_labels_und_kein_score(self):
        v = self.lead(60, phase="in_kontaktierung", versuch_nr=1, ad_id=self.hv.id,
                      score_klasse="B", score_punkte=55)
        q = self.lead(61, phase="qualifiziert", versuch_nr=1, ad_id=self.hv.id)
        daten = hv_modul.ansicht(self.s, self.admin, hv_modul.filter_aus_query({}, True))
        self.assertFalse(daten["score_aktiv"])
        self.assertEqual(daten["deals_label"], "Deals")
        self.assertEqual(daten["hauptboard_label"], "Hauptboard")
        self.assertEqual(daten["offen_labels"], "Neu · Kontaktiert · Zurückgestellt")
        optionen = dict(daten["status_optionen"])
        self.assertEqual(optionen.get("in_kontaktierung,qualifiziert"), "Kontaktiert")
        self.assertNotIn("qualifiziert", optionen)
        self.assertEqual([n for n in optionen.values()].count("Kontaktiert"), 1)
        # der zusammengefasste Filter trifft beide Phasen
        f = hv_modul.filter_aus_query({"status": "in_kontaktierung,qualifiziert"}, True)
        ids = {z["vorgang"].id for z in hv_modul.ansicht(self.s, self.admin, f)["zeilen"]}
        self.assertTrue({v.id, q.id} <= ids)
        f = hv_modul.filter_aus_query({"status": "neu"}, True)
        ids = {z["vorgang"].id for z in hv_modul.ansicht(self.s, self.admin, f)["zeilen"]}
        self.assertFalse({v.id, q.id} & ids)
        # Seiten ohne Score, mit Label
        r = self.client.get("/lead-management/handelsvertreter")
        self.assertEqual(r.status_code, 200)
        seite = inhalt(r.text)
        self.assertIn('<option value="in_kontaktierung,qualifiziert" >Kontaktiert</option>', seite)
        self.assertIsNone(SCORE_MUSTER.search(seite), SCORE_MUSTER.search(seite))
        self.assertNotIn("Qualifiziert<", seite)
        r = self.client.get(f"/lead-management/handelsvertreter/dashboard?hv={self.hv.id}")
        self.assertEqual(r.status_code, 200)
        seite = inhalt(r.text)
        self.assertIn("Neu · Kontaktiert · Zurückgestellt", seite)
        self.assertIn("manuell gesetzt", seite)
        self.assertIsNone(SCORE_MUSTER.search(seite), SCORE_MUSTER.search(seite))
        dash = hv_modul.dashboard_daten(self.s, self.hv)
        self.assertEqual(dash["offen_labels"], "Neu · Kontaktiert · Zurückgestellt")
        self.assertEqual(dash["kacheln"]["offen"], 2)


# --- 5. Score nirgends im HTML der eigenen Seiten -------------------------------------

class KeinScoreImHtml(Basis):
    def test_eigene_seiten(self):
        v = self.lead(70, phase="qualifiziert", versuch_nr=1, score_klasse="A", score_punkte=90)
        termin, meldung, _ = lead_termin.termin_anlegen(
            self.s, v, self.horst.id, naechster_werktag(7) + timedelta(hours=11), benutzer=self.admin)
        self.s.commit()
        self.assertIsNotNone(termin, meldung)
        seiten = ["/lead-management/dashboard",
                  f"/lead-management/lead/{v.id}/termin",
                  f"/lead-management/termin/{termin.id}/ersatz",
                  "/lead-management/kalender",
                  "/lead-management/handelsvertreter",
                  f"/lead-management/handelsvertreter/dashboard?hv={self.hv.id}",
                  "/lead-management/uebersicht",
                  "/lead-management/statistik?demo=1",
                  "/lead-management/statistik/kanal"]
        for url in seiten:
            r = self.client.get(url)
            self.assertEqual(r.status_code, 200, url)
            treffer = SCORE_MUSTER.search(inhalt(r.text))
            self.assertIsNone(treffer, f"{url}: {treffer.group(0) if treffer else ''}")
        # Ersatzkandidaten-Seite nennt das Label „Kontaktiert“ statt der Klassen
        seite = inhalt(self.client.get(f"/lead-management/termin/{termin.id}/ersatz").text)
        self.assertIn("Status „Kontaktiert“", seite)
        self.assertNotIn("Score-Klasse berücksichtigt", seite)


if __name__ == "__main__":
    unittest.main()
