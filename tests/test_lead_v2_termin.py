# Tests PLAN_LEAD_V2 Phase 108 (CLAUDE v23): Terminassistent V2 – Kandidaten-
# filter (Kompetenz, Kanal-Regel, Handelsvertreter, Gebiet), Puffer = max(30,
# Fahrzeit), vorgemerkt vs. gebucht, manuelle Buchung mit Konfliktwarnung,
# Vorab-Gespräch Telefon/Teams (Mail nur mit Buchungslink), Absage mit
# CANCEL-ICS + Ersatzkandidaten, Terminbestätigung erneut (SEQUENCE), Umbuchung
# mit gleicher UID, AD-Profil speichert Kompetenzen, Kalender.
# Laufen im Demo-Modus gegen die Entwicklungs-DB; Testleads tragen den
# Nachnamen „LeadV2T-Test“, Testbenutzer das Präfix „LeadV2T “ – alles wird
# aufgeräumt.
import json
import unittest
import warnings
from datetime import datetime, timedelta
from pathlib import Path

warnings.filterwarnings("ignore")

from fastapi.testclient import TestClient

from app import lead_mail, lead_termin, lead_v2
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
from app.models import (AdProfil, Benachrichtigung, Benutzer, KommunikationLog, Kunde,
                        LeadAktivitaet, LeadQuelle, Vorgang, VotTermin)

NACHNAME = "LeadV2T-Test"
BENUTZER_PRAEFIX = "LeadV2T "
# Bezugspunkt abseits aller echten/Demo-Leads (Nordsee vor Helgoland), damit
# Ersatzkunden-Radien nur die Testleads sehen; 0.01° Breite ≈ 1,11 km
# (v24: vorher Duisburg Innenstadt – Demo-Leads der Dev-DB verfälschten den Radius)
BASIS = (54.3, 7.6)


def _versatz(km_nord: float) -> tuple[float, float]:
    return (BASIS[0] + km_nord / 111.0, BASIS[1])


def aufraeumen(s):
    for k in s.query(Kunde).filter(Kunde.nachname.like(f"{NACHNAME}%")):
        for v in s.query(Vorgang).filter_by(kunde_id=k.id):
            s.query(LeadAktivitaet).filter_by(vorgang_id=v.id).delete()
            s.query(KommunikationLog).filter_by(vorgang_id=v.id).delete()
            s.query(VotTermin).filter_by(vorgang_id=v.id).delete()
            s.delete(v)
        s.delete(k)
    for b in s.query(Benutzer).filter(Benutzer.name.like(f"{BENUTZER_PRAEFIX}%")):
        s.query(AdProfil).filter_by(benutzer_id=b.id).delete()
        s.query(VotTermin).filter_by(ad_id=b.id).delete()
        s.query(Benachrichtigung).filter_by(benutzer_id=b.id).delete()
        s.delete(b)
    s.commit()


def naechster_werktag(tage_voraus: int = 3) -> datetime:
    """Ein Werktag (Mo–Fr) mindestens tage_voraus Tage in der Zukunft, 00:00."""
    tag = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    tag += timedelta(days=tage_voraus)
    while tag.weekday() >= 5:
        tag += timedelta(days=1)
    return tag


class Basis(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        init_db()
        cls.s = SessionLocal()
        aufraeumen(cls.s)
        cls.client = TestClient(app)
        cls.client.post("/login", data={"benutzer_id": "1", "pin": "1234"})
        cls.gesichert = {n: kern.parameter_holen(cls.s, n, "")
                         for n in ("lead_freigabe_modus", "kalender_sync", "mail_modus",
                                   "kanal_ad_regel", "routing_anbieter")}
        kern.parameter_setzen(cls.s, "lead_freigabe_modus", "admin")
        kern.parameter_setzen(cls.s, "kalender_sync", "aus")
        kern.parameter_setzen(cls.s, "mail_modus", "protokoll")
        kern.parameter_setzen(cls.s, "kanal_ad_regel", "")
        kern.parameter_setzen(cls.s, "routing_anbieter", "luftlinie")
        cls.s.commit()
        cls.ads = {}
        cls.ads["horst"] = cls.ad("Horst", ["WP", "WB"], kombi=True, gebiet=["47"])
        cls.ads["rudi"] = cls.ad("Rudi", ["WP", "PV", "KL"], kombi=False, gebiet=["45"])
        cls.ads["hv"] = cls.ad("Hv", ["WP", "PV", "KL", "WB"], kombi=True, mfh=True,
                               terminiert_selbst=True, gebiet=["47"])
        cls.ads["inaktiv"] = cls.ad("Inaktiv", ["WP"], aktiv_terminierung=False)
        cls.kollege = cls.benutzer("Kollege", rolle="innendienst",
                                   buchungslink="https://outlook.office.com/bookwithme/test")
        cls.kollege_ohne = cls.benutzer("KollegeOhne", rolle="innendienst")
        cls.s.commit()

    @classmethod
    def tearDownClass(cls):
        aufraeumen(cls.s)
        for n, w in cls.gesichert.items():
            kern.parameter_setzen(cls.s, n, w)
        cls.s.commit()
        cls.s.close()

    @classmethod
    def benutzer(cls, name, rolle="aussendienst", **extra):
        b = Benutzer(name=f"{BENUTZER_PRAEFIX}{name}", rolle=rolle, aktiv=True,
                     email=f"{name.lower()}@lv2t.local", telefon="0203 1", **extra)
        cls.s.add(b)
        cls.s.flush()
        return b

    @classmethod
    def ad(cls, name, sparten, kombi=False, mfh=False, gewerbe=False,
           terminiert_selbst=False, aktiv_terminierung=True, gebiet=None):
        b = cls.benutzer(name)
        profil = AdProfil(
            benutzer_id=b.id, start_adresse="Duisburg",
            start_lat=BASIS[0], start_lon=BASIS[1],
            arbeitszeiten=json.dumps({t: ["08:00", "18:00"] for t in ("mo", "di", "mi", "do", "fr")}),
            termin_dauer_min=90, puffer_min=30, max_termine_tag=3,
            gebiet_plz_praefixe=json.dumps(gebiet or []), aktiv_terminierung=aktiv_terminierung,
            terminiert_selbst=terminiert_selbst, kompetenz_sparten=json.dumps(sparten),
            kompetenz_kombi=kombi, kompetenz_mfh=mfh, kompetenz_gewerbe=gewerbe)
        cls.s.add(profil)
        cls.s.flush()
        return b

    def lead(self, nr, sparten=("WP",), plz="47139", ort=BASIS, objektart="EFH",
             komplett=True, phase="qualifiziert", eingang_tage=0, **extra):
        quelle = self.s.query(LeadQuelle).filter_by(key="website").first()
        daten = {"anrede": "Herr", "vorname": f"V{nr}", "nachname": f"{NACHNAME}-{nr}",
                 "plz": plz, "ort": "Duisburg", "telefon": f"0203 44{nr:04d}",
                 "sparten": list(sparten), "email": f"v2t{nr}@test.local",
                 "strasse": f"Teststraße {nr}" if komplett else ""}
        vorgang, _ = kern.lead_anlegen(self.s, daten, quelle, "api", entscheidung="neu")
        kunde = self.s.get(Kunde, vorgang.kunde_id)
        kunde.vertriebskanal = "Standard" if komplett else ""
        kunde.objektart = objektart
        vorgang.demo = True
        vorgang.lead_phase = phase
        vorgang.lat, vorgang.lon, vorgang.geocode_status = ort[0], ort[1], "ok"
        vorgang.eingang_am = datetime.now() - timedelta(days=eingang_tage)
        for k, v in extra.items():
            setattr(vorgang, k, v)
        self.s.commit()
        return vorgang

    def termin(self, vorgang, ad, beginn, dauer=90, status="geplant", typ="vot",
               ort=BASIS):
        t = VotTermin(vorgang_id=vorgang.id, ad_id=ad.id, beginn=beginn,
                      ende=beginn + timedelta(minutes=dauer), adresse="Teststraße, 47139 Duisburg",
                      lat=ort[0], lon=ort[1], status=status, quelle="manuell", typ=typ,
                      medium={"vot": "vor_ort", "telefon": "telefon", "online": "teams"}[typ],
                      demo=True)
        self.s.add(t)
        self.s.commit()
        return t

    def mails(self, vorgang, key):
        return (self.s.query(KommunikationLog)
                .filter_by(vorgang_id=vorgang.id, vorlage_key=key).all())

    def namen(self, liste):
        """Nur die Testbenutzer – die Dev-DB enthält weitere AD ohne Profil."""
        return [k["ad"].name.replace(BENUTZER_PRAEFIX, "") for k in liste
                if k["ad"].name.startswith(BENUTZER_PRAEFIX)]


class Kandidatenfilter(Basis):
    def test_kompetenz_schliesst_aus(self):
        v = self.lead(1, sparten=("WP", "PV"))
        ergebnis = lead_termin.kandidaten(self.s, v)
        namen = self.namen(ergebnis["kandidaten"])
        self.assertIn("Horst", namen)            # Kombi WP+PV erlaubt
        self.assertNotIn("Rudi", namen)          # keine Kombi-Kompetenz
        self.assertNotIn("Hv", namen)            # Handelsvertreter – fremder Lead
        self.assertNotIn("Inaktiv", namen)
        gruende = {a["ad"].name.replace(BENUTZER_PRAEFIX, ""): a["grund"]
                   for a in ergebnis["ausgeschlossen"]}
        self.assertIn("Kombi", gruende["Rudi"])
        self.assertIn("Handelsvertreter", gruende["Hv"])
        self.assertIn("nicht aktiv", gruende["Inaktiv"])
        horst = next(k for k in ergebnis["kandidaten"] if "Horst" in k["ad"].name)
        self.assertIn("Kompetenz WP+PV ✓", horst["gruende"])
        self.assertIn("Gebiet 47 ✓", horst["gruende"])
        self.assertTrue(horst["gebiet"])
        # PV allein: Horst raus, Rudi rein, Rudi außerhalb Gebiet (Abwertung)
        v2 = self.lead(2, sparten=("PV",))
        ergebnis = lead_termin.kandidaten(self.s, v2)
        namen = self.namen(ergebnis["kandidaten"])
        self.assertNotIn("Horst", namen)
        self.assertIn("Rudi", namen)
        rudi = next(k for k in ergebnis["kandidaten"] if "Rudi" in k["ad"].name)
        self.assertFalse(rudi["gebiet"])
        self.assertEqual(rudi["abwertung"], 20)
        self.assertTrue(any("außerhalb Gebiet" in g for g in rudi["gruende"]))
        # MFH ohne Objektkompetenz
        v3 = self.lead(3, sparten=("WP",), objektart="MFH")
        ergebnis = lead_termin.kandidaten(self.s, v3)
        self.assertEqual(self.namen(ergebnis["kandidaten"]), [])
        self.assertTrue(any("MFH" in a["grund"] for a in ergebnis["ausgeschlossen"]))
        # v25 (PLAN_LEAD_V3 Phase 120): Handelsvertreter werden NUR vorgeschlagen,
        # wenn der anfragende Benutzer selbst dieser HV ist – auch bei eigenem Lead
        # sieht der Innendienst (bzw. ein Aufruf ohne Benutzer) ihn nicht, dafür den
        # Hinweis „Lead liegt bei … (Handelsvertreter), Terminierung durch den Vertreter“;
        # der HV selbst bekommt nur sich (eigener Kalender). Vorher (v23): HV bei
        # eigenem Lead immer Kandidat.
        v3.ad_id = self.ads["hv"].id
        self.s.commit()
        ergebnis = lead_termin.kandidaten(self.s, v3)
        self.assertNotIn("Hv", self.namen(ergebnis["kandidaten"]))
        self.assertEqual(ergebnis["hv_lead"].id, self.ads["hv"].id)
        self.assertIn("Terminierung durch den Vertreter", ergebnis["hv_hinweis"])
        self.assertIn(self.ads["hv"].id, [a.id for a in ergebnis["hv_manuell"]])
        ergebnis = lead_termin.kandidaten(self.s, v3, benutzer=self.ads["hv"])
        self.assertEqual(self.namen(ergebnis["kandidaten"]), ["Hv"])
        self.assertIsNone(ergebnis["hv_lead"])

    def test_kanal_regel(self):
        v = self.lead(4, sparten=("WP",))
        kunde = self.s.get(Kunde, v.kunde_id)
        kunde.vertriebskanal = "Sparkasse Duisburg"
        self.s.commit()
        try:
            lead_termin.kanal_regel_setzen(self.s, {"Sparkasse Duisburg": [self.ads["rudi"].id]})
            self.s.commit()
            ergebnis = lead_termin.kandidaten(self.s, v)
            self.assertEqual(self.namen(ergebnis["kandidaten"]), ["Rudi"])
            self.assertEqual(len(ergebnis["kandidaten"]), 1)   # Kanal-Regel = Ausschluss aller anderen
            grund = next(a["grund"] for a in ergebnis["ausgeschlossen"] if "Horst" in a["ad"].name)
            self.assertIn("Kanal Sparkasse Duisburg", grund)
            # Pflege aus dem AD-Profil: Horst zusätzlich eintragen, Rudi austragen
            lead_termin.kanal_regel_ad_setzen(self.s, self.ads["horst"].id, ["Sparkasse Duisburg"])
            lead_termin.kanal_regel_ad_setzen(self.s, self.ads["rudi"].id, [])
            self.s.commit()
            self.assertEqual(lead_termin.kanal_regel(self.s),
                             {"sparkasse duisburg": [self.ads["horst"].id]})
            self.assertEqual(lead_termin.kanal_regel_fuer_ad(self.s, self.ads["horst"].id),
                             ["sparkasse duisburg"])
        finally:
            kern.parameter_setzen(self.s, "kanal_ad_regel", "")
            self.s.commit()


class PufferUndVorschlaege(Basis):
    def test_puffer_ist_max_aus_mindestpuffer_und_fahrzeit(self):
        horst = self.ads["horst"]
        tag = naechster_werktag(3)
        # bestehender Termin 10:00–11:30, 20 km nördlich → Fahrzeit ≈ 35 Min > 30
        fremd = self.lead(10, sparten=("WP",), ort=_versatz(20))
        self.termin(fremd, horst, tag + timedelta(hours=10), ort=_versatz(20))
        v = self.lead(11, sparten=("WP",))
        ergebnis = lead_termin.vorschlaege(self.s, v, nur_ad_id=horst.id, anzahl=200)
        self.s.commit()
        slots = sorted(x["beginn"] for x in ergebnis["vorschlaege"]
                       if x["beginn"].date() == tag.date())
        self.assertTrue(slots, "keine Slots am Testtag")
        # 12:00 wäre mit festem 30-Min-Puffer frei, scheitert aber an der Fahrzeit
        self.assertNotIn(tag + timedelta(hours=12), slots)
        self.assertIn(tag + timedelta(hours=12, minutes=30), slots)
        # vor dem Termin: Ende + Puffer ≤ 10:00 → 08:00 (Ende 09:30, 35 Min → 10:05 > 10:00: nein)
        self.assertNotIn(tag + timedelta(hours=8), slots)
        # Begründung in Klartext
        bsp = ergebnis["vorschlaege"][0]
        self.assertIn("Kompetenz WP ✓", bsp["begruendung"])
        self.assertIn("Gebiet 47 ✓", bsp["begruendung"])
        self.assertIn("Umweg", bsp["begruendung"])
        self.assertEqual(bsp["puffer"], 30)
        # Konfliktprüfung: Überlappung = Sperre, Pufferverletzung = Warnung
        k = lead_termin.konflikte(self.s, horst.id, tag + timedelta(hours=10, minutes=30),
                                  lead_ort=BASIS)
        self.assertTrue(k["sperren"])
        k = lead_termin.konflikte(self.s, horst.id, tag + timedelta(hours=11, minutes=45),
                                  lead_ort=BASIS)
        self.assertFalse(k["sperren"])
        self.assertTrue(k["warnen"])
        self.assertTrue(any("Puffer" in t for t in k["texte"]))
        k = lead_termin.konflikte(self.s, horst.id, tag + timedelta(hours=13), lead_ort=BASIS)
        self.assertFalse(k["warnen"], k["texte"])

    def test_kapazitaet_zaehlt_nur_vot_vorab_zaehlt_in_kollision(self):
        rudi = self.ads["rudi"]
        tag = naechster_werktag(4)
        v = self.lead(12, sparten=("PV",))
        # drei Telefongespräche am Tag – Kapazität (max 3) darf nicht voll sein
        for h in (8, 9, 10):
            self.termin(v, rudi, tag + timedelta(hours=h), dauer=30, typ="telefon")
        ergebnis = lead_termin.vorschlaege(self.s, v, nur_ad_id=rudi.id, anzahl=200)
        self.s.commit()
        slots = [x["beginn"] for x in ergebnis["vorschlaege"] if x["beginn"].date() == tag.date()]
        self.assertTrue(slots)
        # 09:00 kollidiert mit dem Telefongespräch 09:00–09:30
        self.assertNotIn(tag + timedelta(hours=9), slots)
        # drei VOT → Tag voll
        for h in (12, 14, 16):
            self.termin(v, rudi, tag + timedelta(hours=h), typ="vot")
        ergebnis = lead_termin.vorschlaege(self.s, v, nur_ad_id=rudi.id, anzahl=200)
        self.s.commit()
        self.assertEqual([x for x in ergebnis["vorschlaege"] if x["beginn"].date() == tag.date()], [])
        k = lead_termin.konflikte(self.s, rudi.id, tag + timedelta(hours=11))
        self.assertTrue(k["kapazitaet_voll"])


class BuchenVorgemerkt(Basis):
    def test_vorgemerkt_ohne_pflichtfelder_gebucht_mit(self):
        horst = self.ads["horst"]
        beginn = naechster_werktag(5) + timedelta(hours=14)
        offen = self.lead(20, sparten=("WP",), komplett=False)
        self.assertTrue(lead_v2.pflichtfelder_offen(self.s, self.s.get(Kunde, offen.kunde_id), offen))
        r = self.client.post(f"/lead-management/lead/{offen.id}/termin",
                             data={"beginn": beginn.strftime("%Y-%m-%dT%H:%M"),
                                   "ad_id": str(horst.id), "umweg": "5"}, follow_redirects=False)
        self.assertEqual(r.status_code, 303, r.text)
        self.assertIn("vorgemerkt", r.headers["location"].lower())
        self.s.expire_all()
        t = self.s.query(VotTermin).filter_by(vorgang_id=offen.id).one()
        self.assertEqual((t.status, t.typ), ("vorgemerkt", "vot"))
        self.assertEqual(self.mails(offen, "terminbestaetigung"), [])
        self.assertNotEqual(self.s.get(Vorgang, offen.id).lead_phase, "terminiert")
        self.assertTrue(any("vorgemerkt" in a.text for a in
                            self.s.query(LeadAktivitaet).filter_by(vorgang_id=offen.id)))
        # Kartei-Vertrag: der vorgemerkte Termin blockt den Slot im Assistenten
        k = lead_termin.konflikte(self.s, horst.id, beginn)
        self.assertTrue(k["sperren"])
        # vollständiger Lead → direkt gebucht
        voll = self.lead(21, sparten=("WP",))
        beginn2 = beginn + timedelta(days=1)
        while beginn2.weekday() >= 5:
            beginn2 += timedelta(days=1)
        r = self.client.post(f"/lead-management/lead/{voll.id}/termin",
                             data={"beginn": beginn2.strftime("%Y-%m-%dT%H:%M"),
                                   "ad_id": str(horst.id)}, follow_redirects=False)
        self.assertEqual(r.status_code, 303, r.text)
        self.s.expire_all()
        t2 = self.s.query(VotTermin).filter_by(vorgang_id=voll.id).one()
        self.assertEqual(t2.status, "geplant")
        self.assertEqual(len(self.mails(voll, "terminbestaetigung")), 1)
        self.assertEqual(len(self.mails(voll, "terminerinnerung")), 1)
        voll = self.s.get(Vorgang, voll.id)
        self.assertEqual(voll.lead_phase, "terminiert")
        self.assertEqual(voll.ad_id, horst.id)          # A-7 über lead_v2.ad_zuweisen

    def test_manuell_konflikt_warnen_und_sperren(self):
        rudi = self.ads["rudi"]
        tag = naechster_werktag(6)
        a = self.lead(22, sparten=("PV",))
        self.termin(a, rudi, tag + timedelta(hours=10))            # 10:00–11:30
        b = self.lead(23, sparten=("PV",))
        url = f"/lead-management/lead/{b.id}/termin/manuell"
        # volle Überlappung → gesperrt
        r = self.client.post(url, data={"datum": tag.strftime("%Y-%m-%d"), "uhrzeit": "10:30",
                                        "ad_id": str(rudi.id)}, follow_redirects=False)
        self.assertIn("Nicht+m", r.headers["location"])
        self.assertEqual(self.s.query(VotTermin).filter_by(vorgang_id=b.id).count(), 0)
        # Pufferverletzung ohne Bestätigung → Warnung, kein Termin
        r = self.client.post(url, data={"datum": tag.strftime("%Y-%m-%d"), "uhrzeit": "11:52",
                                        "ad_id": str(rudi.id)}, follow_redirects=False)
        self.assertIn("warnung=", r.headers["location"])
        self.assertIn("uhrzeit=11%3A45", r.headers["location"])    # 15-Min-Raster
        self.assertEqual(self.s.query(VotTermin).filter_by(vorgang_id=b.id).count(), 0)
        seite = self.client.get(r.headers["location"]).text
        self.assertIn("Konflikte", seite)
        # mit Bestätigung → gebucht (Beginn gerundet)
        r = self.client.post(url, data={"datum": tag.strftime("%Y-%m-%d"), "uhrzeit": "11:52",
                                        "ad_id": str(rudi.id), "bestaetigt": "1"},
                             follow_redirects=False)
        self.assertEqual(r.status_code, 303)
        self.s.expire_all()
        t = self.s.query(VotTermin).filter_by(vorgang_id=b.id).one()
        self.assertEqual(t.beginn, tag + timedelta(hours=11, minutes=45))
        self.assertEqual(t.quelle, "manuell")
        # AD außerhalb der Vorauswahl (Horst kann kein PV)
        c = self.lead(24, sparten=("PV",))
        r = self.client.post(f"/lead-management/lead/{c.id}/termin/manuell",
                             data={"datum": tag.strftime("%Y-%m-%d"), "uhrzeit": "15:00",
                                   "ad_id": str(self.ads["horst"].id)}, follow_redirects=False)
        self.assertIn("nicht+w", r.headers["location"])
        # JSON-Konfliktprüfung
        r = self.client.get(f"/lead-management/termin/konflikt?ad_id={rudi.id}&vorgang_id={c.id}"
                            f"&beginn={tag.strftime('%Y-%m-%d')}T10:15")
        self.assertTrue(r.json()["sperren"])


class VorabGespraech(Basis):
    def test_telefon_und_online(self):
        horst = self.ads["horst"]
        v = self.lead(30, sparten=("WP",))
        tag = naechster_werktag(7)
        r = self.client.post(f"/lead-management/lead/{v.id}/termin/vorab",
                             data={"typ": "telefon", "person_id": str(horst.id),
                                   "datum": tag.strftime("%Y-%m-%d"), "uhrzeit": "09:00",
                                   "dauer": "30"}, follow_redirects=False)
        self.assertEqual(r.status_code, 303, r.text)
        self.s.expire_all()
        t = self.s.query(VotTermin).filter_by(vorgang_id=v.id, typ="telefon").one()
        self.assertEqual((t.status, t.medium, t.ad_id), ("geplant", "telefon", horst.id))
        self.assertEqual(t.ende, t.beginn + timedelta(minutes=30))
        self.assertEqual(self.s.get(Vorgang, v.id).lead_phase, "qualifiziert")   # keine Phase
        self.assertEqual(self.mails(v, "terminbestaetigung"), [])
        self.assertTrue(any("Telefongespräch" in a.text for a in
                            self.s.query(LeadAktivitaet).filter_by(vorgang_id=v.id)))
        # zählt in der Kollision
        self.assertTrue(lead_termin.konflikte(self.s, horst.id, tag + timedelta(hours=9))["sperren"])
        # online ohne Buchungslink → Hinweis, keine Mail
        r = self.client.post(f"/lead-management/lead/{v.id}/termin/vorab",
                             data={"typ": "online", "person_id": str(self.kollege_ohne.id),
                                   "buchungslink_senden": "1"}, follow_redirects=False)
        self.assertIn("Kein+Buchungslink", r.headers["location"])
        self.assertEqual(self.mails(v, "online_termin_einladung"), [])
        # online mit Buchungslink → Mail geplant (Sendesperre: protokoll), Termin vorgemerkt
        r = self.client.post(f"/lead-management/lead/{v.id}/termin/vorab",
                             data={"typ": "online", "person_id": str(self.kollege.id),
                                   "buchungslink_senden": "1"}, follow_redirects=False)
        self.assertEqual(r.status_code, 303)
        self.s.expire_all()
        einladung = self.mails(v, "online_termin_einladung")
        self.assertEqual(len(einladung), 1)
        self.assertEqual(einladung[0].modus, "protokoll")
        online = self.s.query(VotTermin).filter_by(vorgang_id=v.id, typ="online").one()
        self.assertEqual((online.status, online.medium, online.ad_id),
                         ("vorgemerkt", "teams", self.kollege.id))
        self.assertIsNone(online.beginn)
        self.assertTrue(lead_mail.rendern(self.s, einladung[0]))
        self.assertIn("bookwithme", einladung[0].body_html)
        self.assertIn(self.kollege.name, einladung[0].body_html)
        # Formularseite
        self.assertEqual(self.client.get(f"/lead-management/lead/{v.id}/termin/vorab?typ=online").status_code, 200)


class AbsageUndErsatz(Basis):
    def test_absage_cancel_ics_und_ersatzkandidaten(self):
        horst = self.ads["horst"]
        tag = naechster_werktag(8)
        a = self.lead(40, sparten=("WP",))
        termin, meldung, vorgemerkt = lead_termin.termin_anlegen(
            self.s, a, horst.id, tag + timedelta(hours=10), quelle="assistent")
        self.s.commit()
        self.assertIsNotNone(termin, meldung)
        self.assertFalse(vorgemerkt)
        # Erst-ICS: UID gesetzt, SEQUENCE 0, Inhalt E4
        pfad = lead_mail.ics_erstellen(self.s, termin, a)
        self.s.commit()
        inhalt = Path(pfad).read_text(encoding="utf-8")
        uid = termin.ics_uid
        self.assertEqual(uid, f"friondo-vot-{termin.id}@friondo.de")
        self.assertIn(f"UID:{uid}", inhalt)
        self.assertIn("SEQUENCE:0", inhalt)
        self.assertIn("METHOD:REQUEST", inhalt)
        self.assertIn("SUMMARY:Vor-Ort-Termin Friondo – WP", inhalt)
        self.assertIn("LOCATION:Teststraße 40\\, 47139 Duisburg", inhalt)
        self.assertIn("Ihr Berater: LeadV2T Horst\\, Telefon 0203 1", inhalt)
        self.assertIn("TRIGGER:-PT24H", inhalt)
        self.assertIn("rechtzeitig ab", inhalt)
        # Ersatzkandidaten: B alt+nah, D in_kontaktierung erreicht, C neu 9 km,
        # E Phase neu (raus), F 50 km (raus), G mit aktivem VOT (raus)
        b = self.lead(41, ort=_versatz(2), eingang_tage=30)
        c = self.lead(42, ort=_versatz(9), eingang_tage=1)
        d = self.lead(43, ort=_versatz(3), phase="in_kontaktierung",
                      erreicht_am=datetime.now())
        self.lead(44, ort=_versatz(1), phase="neu")
        self.lead(45, ort=_versatz(50), eingang_tage=40)
        g = self.lead(46, ort=_versatz(1))
        self.termin(g, self.ads["rudi"], tag + timedelta(days=1, hours=9))
        self.lead(47, ort=_versatz(4), phase="in_kontaktierung")   # nie erreicht → raus
        glocken_vorher = self.s.query(Benachrichtigung).filter(
            Benachrichtigung.link == f"/lead-management/termin/{termin.id}/ersatz").count()
        with glocken_arten(self.s, "terminaenderung"):   # v29: Glocke nur mit eingeschalteter Art
            r = self.client.post(f"/lead-management/termin/{termin.id}/absagen",
                                 data={"grund": "", "grund_text": "Kunde hat kurzfristig abgesagt"},
                                 follow_redirects=False)
        self.assertEqual(r.status_code, 303, r.text)
        self.assertIn(f"/lead-management/termin/{termin.id}/ersatz", r.headers["location"])
        self.s.expire_all()
        termin = self.s.get(VotTermin, termin.id)
        self.assertEqual(termin.status, "abgesagt")
        self.assertEqual(self.s.get(Vorgang, a.id).lead_phase, "qualifiziert")
        self.assertEqual(termin.ics_uid, uid)
        self.assertEqual(termin.ics_sequence, 1)
        # Bestätigung/Erinnerung storniert, Absage mit Storno-ICS geplant
        for m in self.mails(a, "terminerinnerung") + self.mails(a, "terminbestaetigung"):
            self.assertEqual(m.status, "storniert")
        absage = self.mails(a, "terminabsage")
        self.assertEqual(len(absage), 1)
        self.assertEqual(absage[0].status, "geplant")
        storno = Path(absage[0].anhang_pfad).read_text(encoding="utf-8")
        self.assertIn("METHOD:CANCEL", storno)
        self.assertIn("STATUS:CANCELLED", storno)
        self.assertIn(f"UID:{uid}", storno)
        self.assertIn("SEQUENCE:1", storno)
        self.assertNotIn("VALARM", storno)
        # Rendern der Absage ersetzt den Storno-Anhang nicht
        self.assertTrue(lead_mail.rendern(self.s, absage[0]))
        self.assertTrue(absage[0].anhang_pfad.endswith("_storno.ics"))
        self.assertIn("abgesagt", absage[0].betreff.lower())
        # Glocke mit Link auf den Ersatz-Dialog (Leitung = Admin 1)
        glocken = self.s.query(Benachrichtigung).filter(
            Benachrichtigung.link == f"/lead-management/termin/{termin.id}/ersatz").count()
        self.assertGreater(glocken, glocken_vorher)
        # Ersatzkandidaten: Radius 5 km liefert nur B und D (< 3) → Stufe 10 km
        daten = lead_termin.ersatz_kandidaten(self.s, termin)
        ids = [k["vorgang"].id for k in daten["kandidaten"]]
        self.assertEqual(daten["radius"], 10.0)
        self.assertEqual(ids[:3], [b.id, d.id, c.id])
        self.assertTrue(daten["kandidaten"][0]["bevorzugt"])
        self.assertIn("30 Tage alt (bevorzugt)", daten["kandidaten"][0]["begruendung"])
        self.assertIn("km Luftlinie", daten["kandidaten"][0]["begruendung"])
        # v25 (Phase 120): Score ist abgeschaltet (score_aktiv = aus) – keine
        # Klassen-Angabe mehr in der Begründung; beide Kontakt-Phasen tragen das
        # Label „Kontaktiert“ (Blatt Status), die interne Phase steht als Zusatz
        if lead_v2.score_aktiv(self.s):
            self.assertIn("Klasse", daten["kandidaten"][0]["begruendung"])
        else:
            self.assertNotIn("Klasse", daten["kandidaten"][0]["begruendung"])
        self.assertIn("Phase Kontaktiert (erreicht)", daten["kandidaten"][1]["begruendung"])
        self.assertIn("Phase Kontaktiert (qualifiziert)", daten["kandidaten"][0]["begruendung"])
        seite = self.client.get(f"/lead-management/termin/{termin.id}/ersatz")
        self.assertEqual(seite.status_code, 200)
        self.assertIn("Termin für Ersatzkunden vorschlagen", seite.text)
        self.assertIn(f"ersatz_fuer={termin.id}", seite.text)
        # Assistent mit Vorauswahl AD/Slot
        slot = (tag + timedelta(hours=10)).strftime("%Y-%m-%dT%H:%M")
        seite = self.client.get(f"/lead-management/lead/{b.id}/termin?ad_id={horst.id}"
                                f"&slot={slot}&ersatz_fuer={termin.id}")
        self.assertEqual(seite.status_code, 200)
        self.assertIn("Ersatz für den abgesagten Termin", seite.text)
        self.assertIn(f'value="{tag.strftime("%Y-%m-%d")}"', seite.text)
        self.assertIn('value="10:00"', seite.text)

    def test_absage_vorab_ohne_kundenmail(self):
        v = self.lead(48)
        tag = naechster_werktag(9)
        t = self.termin(v, self.ads["horst"], tag + timedelta(hours=9), dauer=30, typ="telefon")
        r = self.client.post(f"/lead-management/termin/{t.id}/absagen",
                             data={"grund": "Kunde nicht angetroffen"}, follow_redirects=False)
        self.assertEqual(r.status_code, 303)
        self.assertNotIn("/ersatz", r.headers["location"])
        self.s.expire_all()
        self.assertEqual(self.s.get(VotTermin, t.id).status, "abgesagt")
        self.assertEqual(self.mails(v, "terminabsage"), [])
        self.assertEqual(self.s.get(Vorgang, v.id).lead_phase, "qualifiziert")


class BestaetigungUndUmbuchung(Basis):
    def test_bestaetigung_erneut_erhoeht_sequence(self):
        horst = self.ads["horst"]
        tag = naechster_werktag(10)
        v = self.lead(50)
        termin, _, _ = lead_termin.termin_anlegen(self.s, v, horst.id, tag + timedelta(hours=9))
        self.s.commit()
        pfad = lead_mail.ics_erstellen(self.s, termin, v)
        self.s.commit()
        uid = termin.ics_uid
        self.assertIn("SEQUENCE:0", Path(pfad).read_text(encoding="utf-8"))
        r = self.client.post(f"/lead-management/termin/{termin.id}/bestaetigung-erneut",
                             follow_redirects=False)
        self.assertEqual(r.status_code, 303)
        self.s.expire_all()
        termin = self.s.get(VotTermin, termin.id)
        self.assertEqual(termin.ics_uid, uid)
        self.assertEqual(termin.ics_sequence, 1)
        self.assertEqual(len(self.mails(v, "terminbestaetigung")), 2)
        neu = self.mails(v, "terminbestaetigung")[-1]
        self.assertTrue(lead_mail.rendern(self.s, neu))
        inhalt = Path(neu.anhang_pfad).read_text(encoding="utf-8")
        self.assertIn(f"UID:{uid}", inhalt)
        self.assertIn("SEQUENCE:1", inhalt)
        self.assertTrue(any("SEQUENCE 1" in a.text for a in
                            self.s.query(LeadAktivitaet).filter_by(vorgang_id=v.id)))

    def test_umbuchung_traegt_uid_weiter(self):
        horst = self.ads["horst"]
        tag = naechster_werktag(11)
        v = self.lead(51)
        alt, _, _ = lead_termin.termin_anlegen(self.s, v, horst.id, tag + timedelta(hours=9))
        self.s.commit()
        lead_mail.ics_erstellen(self.s, alt, v)
        self.s.commit()
        uid = alt.ics_uid
        neu_beginn = tag + timedelta(hours=14)
        r = self.client.post(f"/lead-management/termin/{alt.id}/verschieben",
                             data={"beginn": neu_beginn.strftime("%Y-%m-%dT%H:%M"),
                                   "ad_id": str(horst.id)}, follow_redirects=False)
        self.assertEqual(r.status_code, 303)
        self.assertIn("umgebucht", r.headers["location"])
        self.s.expire_all()
        alt = self.s.get(VotTermin, alt.id)
        self.assertEqual(alt.status, "verschoben")
        neu = (self.s.query(VotTermin).filter_by(vorgang_id=v.id, status="geplant").one())
        self.assertEqual(neu.beginn, neu_beginn)
        self.assertEqual(neu.ics_uid, uid)
        self.assertEqual(neu.ics_sequence, 1)
        aenderung = self.mails(v, "terminaenderung")
        self.assertEqual(len(aenderung), 1)
        self.assertTrue(lead_mail.rendern(self.s, aenderung[0]))
        inhalt = Path(aenderung[0].anhang_pfad).read_text(encoding="utf-8")
        self.assertIn(f"UID:{uid}", inhalt)
        self.assertIn("SEQUENCE:1", inhalt)
        # Assistent mit ?umbuchen= rendert
        self.assertEqual(self.client.get(f"/lead-management/lead/{v.id}/termin?umbuchen={neu.id}").status_code, 200)


class AdProfilUndSeiten(Basis):
    def test_ad_profil_speichert_kompetenzen(self):
        b = self.benutzer("ProfilNeu")
        self.s.commit()
        seite = self.client.get(f"/benutzer/{b.id}/ad-profil")
        self.assertEqual(seite.status_code, 200)
        self.assertIn("Produktkompetenz", seite.text)
        self.assertIn("Handelsvertreter – terminiert selbst", seite.text)
        self.assertIn("max(30 Min, Fahrzeit)", seite.text)
        r = self.client.post(f"/benutzer/{b.id}/ad-profil",
                             data={"start_adresse": "", "mo_von": "08:00", "mo_bis": "17:00",
                                   "termin_dauer_min": "90", "puffer_min": "", "max_termine_tag": "",
                                   "gebiet": "47, 46", "kompetenz_WP": "on", "kompetenz_PV": "on",
                                   "kompetenz_kombi": "on", "kompetenz_mfh": "on",
                                   "kompetenz_gewerbe": "on", "terminiert_selbst": "on",
                                   "aktiv_terminierung": "on",
                                   "buchungslink": "https://outlook.office.com/bookwithme/neu"},
                             follow_redirects=False)
        self.assertEqual(r.status_code, 303)
        self.s.expire_all()
        profil = self.s.query(AdProfil).filter_by(benutzer_id=b.id).one()
        self.assertEqual(sorted(lead_v2.kompetenz_sparten(profil)), ["GW", "PV", "WP"])
        self.assertTrue(profil.kompetenz_kombi and profil.kompetenz_mfh and profil.kompetenz_gewerbe)
        self.assertTrue(profil.terminiert_selbst)
        self.assertEqual(profil.puffer_min, 30)          # Parameter puffer_min
        self.assertEqual(profil.max_termine_tag, 3)      # Parameter max_termine_tag_start
        self.assertEqual(self.s.get(Benutzer, b.id).buchungslink,
                         "https://outlook.office.com/bookwithme/neu")
        self.assertTrue(lead_v2.ist_handelsvertreter(self.s, self.s.get(Benutzer, b.id)))
        ok, _ = lead_v2.kompetenz_passt(profil, ["WP", "PV"], "MFH")
        self.assertTrue(ok)
        seite = self.client.get(f"/benutzer/{b.id}/ad-profil")
        self.assertIn('name="kompetenz_WP" checked', seite.text)

    def test_assistent_und_kalender_seiten(self):
        horst = self.ads["horst"]
        offen = self.lead(60, komplett=False)
        seite = self.client.get(f"/lead-management/lead/{offen.id}/termin")
        self.assertEqual(seite.status_code, 200)
        self.assertIn("Terminierung in der Kartei abschließen", seite.text)
        self.assertIn("Vormerken", seite.text)
        self.assertIn("lm_termin.js", seite.text)
        self.assertIn("Kompetenz WP ✓", seite.text)
        self.assertIn("lmt-karte", seite.text)
        tag = naechster_werktag(2)
        self.termin(offen, horst, tag + timedelta(hours=9), dauer=30, typ="telefon")
        self.termin(offen, horst, tag + timedelta(hours=11), status="vorgemerkt")
        heute = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        woche = ((tag - timedelta(days=tag.weekday()))
                 - (heute - timedelta(days=heute.weekday()))).days // 7
        seite = self.client.get(f"/lead-management/kalender?ad_id={horst.id}&woche={woche}")
        self.assertEqual(seite.status_code, 200)
        self.assertIn("typ-telefon", seite.text)
        self.assertIn("typ-vot vorgemerkt", seite.text)
        self.assertIn("lmt-absage-knopf", seite.text)
        # Alle-AD-Sicht enthält die Testprofile (Basis = AD-Profil, nicht nur Hauptrolle)
        seite = self.client.get(f"/lead-management/kalender?woche={woche}")
        self.assertIn("LeadV2T Horst", seite.text)
        # neue Vorlage vorhanden
        self.assertIn("terminabsage", lead_mail.VORLAGEN_START)
        betreff, text = lead_mail.vorlage_laden(self.s, "terminabsage")
        self.assertIn("{termin_datum}", betreff)
        self.assertIn("{rueckruf_telefon}", text)


class Pruefung108(Basis):
    """Nachtests der Prüfung: Kartei-Dialog mit typ=telefon, Umbuchung →
    Ersatzkunden-Dialog + Glocke, Online-Termin Zeit eintragen, ICS-Methode."""

    def test_manuell_mit_typ_telefon_wird_vorab_gespraech(self):
        horst = self.ads["horst"]
        tag = naechster_werktag(12)
        v = self.lead(70, sparten=("WP",))
        # Kartei-Dialog (Phase 106) schickt beginn, typ, ad_id, quelle=manuell
        r = self.client.post(f"/lead-management/lead/{v.id}/termin/manuell",
                             data={"beginn": (tag + timedelta(hours=9)).strftime("%Y-%m-%dT%H:%M"),
                                   "typ": "telefon", "ad_id": str(horst.id), "quelle": "manuell"},
                             follow_redirects=False)
        self.assertEqual(r.status_code, 303, r.text)
        self.assertTrue(r.headers["location"].startswith(f"/lead-management/lead/{v.id}?"))
        self.s.expire_all()
        t = self.s.query(VotTermin).filter_by(vorgang_id=v.id).one()
        self.assertEqual((t.typ, t.medium, t.status), ("telefon", "telefon", "geplant"))
        self.assertEqual(t.ende, t.beginn + timedelta(minutes=30))
        self.assertEqual(self.s.get(Vorgang, v.id).lead_phase, "qualifiziert")
        self.assertEqual(self.mails(v, "terminbestaetigung"), [])
        # typ=vot (oder ohne typ) bleibt der Vor-Ort-Weg mit Konfliktprüfung
        r = self.client.post(f"/lead-management/lead/{v.id}/termin/manuell",
                             data={"beginn": (tag + timedelta(hours=9)).strftime("%Y-%m-%dT%H:%M"),
                                   "typ": "vot", "ad_id": str(horst.id)}, follow_redirects=False)
        self.assertIn("Nicht+m", r.headers["location"])      # Überschneidung mit dem Telefonat

    def test_umbuchung_bietet_ersatzkunden_und_glocke(self):
        horst = self.ads["horst"]
        tag = naechster_werktag(13)
        v = self.lead(71)
        alt, _, _ = lead_termin.termin_anlegen(self.s, v, horst.id, tag + timedelta(hours=9))
        self.s.commit()
        link = f"/lead-management/termin/{alt.id}/ersatz"
        glocken_vorher = self.s.query(Benachrichtigung).filter(Benachrichtigung.link == link).count()
        r = self.client.post(f"/lead-management/termin/{alt.id}/verschieben",
                             data={"beginn": (tag + timedelta(hours=15)).strftime("%Y-%m-%dT%H:%M"),
                                   "ad_id": str(horst.id)},
                             headers={"referer": f"http://testserver/lead-management/lead/{v.id}"},
                             follow_redirects=False)
        self.assertEqual(r.status_code, 303, r.text)
        self.assertTrue(r.headers["location"].startswith(link), r.headers["location"])
        self.assertIn("umgebucht", r.headers["location"])
        self.s.expire_all()
        self.assertEqual(self.s.get(VotTermin, alt.id).status, "verschoben")
        # Glocke an die Leitung (Admin 1 ist der Handelnde → ausgenommen) bzw. Leadmanager
        glocken = self.s.query(Benachrichtigung).filter(Benachrichtigung.link == link).all()
        self.assertGreaterEqual(len(glocken), glocken_vorher)
        self.assertTrue(all(g.benutzer_id != 1 for g in glocken[glocken_vorher:]))
        self.assertEqual(self.client.get(link).status_code, 200)
        # Terminliste des Assistenten zeigt den Ersatzkunden-Link am alten Termin
        seite = self.client.get(f"/lead-management/lead/{v.id}/termin").text
        self.assertIn(f'href="{link}"', seite)
        # Umbuchung eines nur vorgemerkten Termins → kein Ersatz-Dialog, Rücksprung zum Referer
        offen = self.lead(72, komplett=False)
        vm, _, vorgemerkt = lead_termin.termin_anlegen(self.s, offen, horst.id, tag + timedelta(hours=11))
        self.s.commit()
        self.assertTrue(vorgemerkt)
        r = self.client.post(f"/lead-management/termin/{vm.id}/verschieben",
                             data={"beginn": (tag + timedelta(hours=13)).strftime("%Y-%m-%dT%H:%M"),
                                   "ad_id": str(horst.id)},
                             headers={"referer": f"http://testserver/lead-management/lead/{offen.id}"},
                             follow_redirects=False)
        self.assertTrue(r.headers["location"].startswith(f"/lead-management/lead/{offen.id}?"),
                        r.headers["location"])

    def test_online_termin_zeit_eintragen(self):
        v = self.lead(73)
        tag = naechster_werktag(14)
        r = self.client.post(f"/lead-management/lead/{v.id}/termin/vorab",
                             data={"typ": "online", "person_id": str(self.kollege.id),
                                   "buchungslink_senden": "1"}, follow_redirects=False)
        self.assertEqual(r.status_code, 303)
        self.s.expire_all()
        online = self.s.query(VotTermin).filter_by(vorgang_id=v.id, typ="online").one()
        self.assertEqual((online.status, online.beginn), ("vorgemerkt", None))
        seite = self.client.get(f"/lead-management/lead/{v.id}/termin").text
        self.assertIn("Zeit eintragen", seite)
        beginn = tag + timedelta(hours=10)
        r = self.client.post(f"/lead-management/termin/{online.id}/verschieben",
                             data={"beginn": beginn.strftime("%Y-%m-%dT%H:%M"),
                                   "ad_id": str(self.kollege.id)}, follow_redirects=False)
        self.assertEqual(r.status_code, 303)
        self.assertIn("eingetragen", r.headers["location"])
        self.s.expire_all()
        online = self.s.get(VotTermin, online.id)
        self.assertEqual((online.status, online.beginn), ("geplant", beginn))
        self.assertEqual(online.ende, beginn + timedelta(minutes=30))
        self.assertEqual(self.s.get(Vorgang, v.id).lead_phase, "qualifiziert")

    def test_ics_methode_fuer_graph_anhang(self):
        self.assertEqual(lead_mail.ics_methode(b"BEGIN:VCALENDAR\r\nMETHOD:CANCEL\r\n"), "CANCEL")
        self.assertEqual(lead_mail.ics_methode("BEGIN:VCALENDAR\r\nMETHOD:REQUEST\r\n"), "REQUEST")
        self.assertEqual(lead_mail.ics_methode(b""), "REQUEST")


if __name__ == "__main__":
    unittest.main()
