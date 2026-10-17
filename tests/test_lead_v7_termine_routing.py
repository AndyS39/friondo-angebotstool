# Tests PLAN_LEAD_V7 (v37, Agent L2) – Phase 198: Termine anpassbar, Route in Kilometern,
# Objekte einklappbar, Dashboard ohne Routenplaner, Login-Vorbelegung.
#  (c) Termin anpassen (Datum/AD/Bemerkung) mit Aktivität „Termin angepasst: alt → neu“,
#      monday-Termin mit Hinweis „ursprünglich aus monday: …“ (Sync setzt ihn nicht zurück,
#      solange monday das alte Datum trägt; neues monday-Datum gewinnt), in der Testphase keine
#      Outlook-Aufträge und keine Kundenmail, Konfliktmodus sperren → 409 (Puffer), harte
#      Überschneidung → 409 immer, warnen → 409 bestaetigung_noetig dann 200 mit bestaetigt=1,
#      fremder Außendienst → 403, eigener Außendienst → 200, manuelle Neuanlage weiter gesperrt,
#      Kartei zeigt „Anpassen“-Knöpfe und Dialoge.
#  (d) Routing: Vorschläge/Kalender/Mein Tag/Ersatzkunde zeigen km und Minuten vom (gemockten)
#      Dienst, bei Ausfall „geschätzt“; Zähler zählt; Prüfpunkt-Texte (ohne Key „ORS_API_KEY
#      fehlt“, mit Mock „Duisburg → Bochum 28,0 km · 31 Min“); Key aus der .env hat Vorrang und
#      erscheint nirgends; Kontingent (80 % Hinweis, 100 % kein Netzaufruf); Migration idempotent.
#  (e) Objekte-Akkordeon: zu bei Großkunde/mehr als drei Objekten, Kopfzeile „5 Objekte · 2 mit
#      Termin“, Zustand je Nutzer bleibt nach Neuladen; zwei Objekte ohne Großkunde offen.
#  (f) Dashboard ohne Routenplaner, alte gespeicherte Reihenfolge ohne Fehler.
#  (g) Login-Vorbelegung über das Cookie angebotstool_benutzer (nur die ID, nie die PIN),
#      „Anderer Benutzer“ leert das Cookie, Abmelden behält es.
# Läuft gegen die DB-Kopie (DB_PFAD_OVERRIDE diagnose/v37/data_L2); Testdaten tragen das Präfix
# „V37L2“ und werden aufgeräumt; ORS ist über routing._ors_matrix/ors_schluessel gemockt – kein
# echter Netzaufruf. Kontrollwerte des Plans (22.10. 10:00 → 23.10. 14:00 + Horst; Duisburg →
# Bochum; Großkunde mit 5 Objekten) laufen mit Terminen relativ zum heutigen Datum.
import json
import re
import unittest
import warnings
from datetime import datetime, timedelta
from http.cookies import SimpleCookie
from unittest import mock

warnings.filterwarnings("ignore")

from fastapi.testclient import TestClient

from app import auth, config, lead_dashboard, lead_kartei, lead_termin, lead_v2, mein_tag, monday_sync, routing
from app import leadmanagement as kern
from app import objekte as objekte_modul
from app.db import SessionLocal, init_db
from app.main import app
from app.models import (AdProfil, Benachrichtigung, Benutzer, BenutzerEinstellung, KommunikationLog,
                        Kunde, Lead, LeadAktivitaet, LeadQuelle, OutlookAuftrag, Todo, Vorgang,
                        VorgangObjekt, VotTermin)
from app.routers import anmeldung

PRAEFIX = "V37L2"
NACHNAME = f"{PRAEFIX}-Test"
BASIS = (54.3, 7.6)          # abseits aller echten Leads (Nordsee), 0.01° Breite ≈ 1,11 km
PIN = "482913"
PARAMETER = ("terminierung_aktiv", "mail_versand_aktiv", "kalender_sync", "routing_anbieter",
             "ors_api_key", "termin_konflikt_modus", "vorschlaege_anzahl", "score_aktiv",
             "kanal_ad_regel", "puffer_min", routing.KONTINGENT_PARAMETER, routing.PRUEFUNG_PARAMETER)


def _zaehler_name() -> str:
    return f"aufrufe_{routing.ZAEHLER_DIENST}_{datetime.now().date().isoformat()}"


def matrix_mock(quellen, ziele, schluessel):
    """Gemockter openrouteservice: Straßenkilometer = Luftlinie × 1,4, 50 km/h."""
    dauern, strecken = [], []
    for q in quellen:
        zeile_d, zeile_s = [], []
        for z in ziele:
            km = routing.luftlinie_km(q, z) * 1.4
            zeile_s.append(km * 1000)
            zeile_d.append(km / 50 * 3600)
        dauern.append(zeile_d)
        strecken.append(zeile_s)
    return dauern, strecken


def naechster_werktag(tage: int = 3, stunde: int = 10) -> datetime:
    tag = datetime.now().replace(hour=stunde, minute=0, second=0, microsecond=0) + timedelta(days=tage)
    while tag.weekday() >= 5:
        tag += timedelta(days=1)
    return tag


def meldung_aus(r) -> str:
    from urllib.parse import unquote_plus
    ort = r.headers.get("location", "")
    return unquote_plus(ort.split("meldung=", 1)[1].split("&", 1)[0].split("#", 1)[0]) if "meldung=" in ort else ""


def cookies_aus(antwort) -> dict:
    kopf = antwort.headers
    alle = kopf.get_list("set-cookie") if hasattr(kopf, "get_list") else kopf.getlist("set-cookie")
    ergebnis = {}
    for zeile in alle:
        c = SimpleCookie()
        c.load(zeile)
        for name, morsel in c.items():
            ergebnis[name] = morsel
    return ergebnis


def aufraeumen(s):
    s.rollback()
    for k in s.query(Kunde).filter(Kunde.nachname.like(f"{NACHNAME}%")):
        for v in s.query(Vorgang).filter_by(kunde_id=k.id):
            s.query(LeadAktivitaet).filter_by(vorgang_id=v.id).delete()
            s.query(KommunikationLog).filter_by(vorgang_id=v.id).delete()
            for t in s.query(VotTermin).filter_by(vorgang_id=v.id):
                s.query(OutlookAuftrag).filter_by(termin_id=t.id, termin_art="vot").delete()
                s.delete(t)
            s.query(VorgangObjekt).filter_by(vorgang_id=v.id).delete()
            s.query(Todo).filter_by(vorgang_id=v.id).delete()
            s.query(Benachrichtigung).filter(
                Benachrichtigung.link == f"/lead-management/lead/{v.id}").delete()
            lead_termin.vorschlaege_cache_leeren(v.id)
            lead_termin._PROTOKOLL_ZEITEN.pop(v.id, None)
            s.delete(v)
        s.delete(k)
    s.query(Lead).filter(Lead.monday_item_id.like(f"{PRAEFIX}%")).delete(synchronize_session=False)
    for b in s.query(Benutzer).filter(Benutzer.name.like(f"{PRAEFIX}%")):
        s.query(AdProfil).filter_by(benutzer_id=b.id).delete()
        s.query(VotTermin).filter_by(ad_id=b.id).delete()
        s.query(Benachrichtigung).filter_by(benutzer_id=b.id).delete()
        s.query(BenutzerEinstellung).filter_by(benutzer_id=b.id).delete()
        s.delete(b)
    s.commit()
    lead_termin.vorschlaege_cache_leeren()


class Basis(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        init_db()
        cls.s = SessionLocal()
        aufraeumen(cls.s)
        cls.gesichert = {n: (z.wert if (z := cls.s.query(kern.LeadParameter).filter_by(name=n).first()) is not None
                             else None) for n in PARAMETER + (_zaehler_name(),)}
        for name, wert in (("terminierung_aktiv", "aus"), ("mail_versand_aktiv", "aus"),
                           ("kalender_sync", "aus"), ("routing_anbieter", "ors"), ("ors_api_key", ""),
                           ("termin_konflikt_modus", "warnen"), ("vorschlaege_anzahl", "3"),
                           ("score_aktiv", "aus"), ("kanal_ad_regel", ""), ("puffer_min", "30"),
                           (routing.KONTINGENT_PARAMETER, str(routing.KONTINGENT_STANDARD))):
            kern.parameter_setzen(cls.s, name, wert)
        cls.s.commit()
        cls.admin = cls.s.get(Benutzer, 1)
        cls.innen = cls.benutzer("Innen", "innendienst")
        cls.horst = cls.ad("Horst", gebiet=["47"])
        cls.rudi = cls.ad("Rudi", gebiet=["47"])
        cls.fremd = cls.ad("Fremd", gebiet=["47"])
        cls.s.commit()
        cls.client = cls.client_fuer(cls.admin.id)
        cls.client_innen = cls.client_fuer(cls.innen.id)
        cls.client_horst = cls.client_fuer(cls.horst.id)
        cls.client_fremd = cls.client_fuer(cls.fremd.id)

    @classmethod
    def tearDownClass(cls):
        cls.s.rollback()
        for name, wert in cls.gesichert.items():
            if wert is None:
                cls.s.query(kern.LeadParameter).filter_by(name=name).delete(synchronize_session=False)
            else:
                kern.parameter_setzen(cls.s, name, wert)
        cls.s.commit()
        aufraeumen(cls.s)
        cls.s.close()

    @staticmethod
    def client_fuer(benutzer_id: int) -> TestClient:
        c = TestClient(app, follow_redirects=False)
        c.cookies.set(auth.COOKIE_NAME, auth.cookie_wert(benutzer_id))
        return c

    @classmethod
    def benutzer(cls, name, rolle):
        b = Benutzer(name=f"{PRAEFIX} {name}", rolle=rolle, pin_hash=auth.pin_hash(PIN),
                     vorname=name, email=f"v37l2.{name.lower()}@test.invalid", aktiv=True)
        cls.s.add(b)
        cls.s.flush()
        return b

    @classmethod
    def ad(cls, name, gebiet=None):
        b = cls.benutzer(name, "aussendienst")
        cls.s.add(AdProfil(
            benutzer_id=b.id, start_adresse="Duisburg", start_lat=BASIS[0], start_lon=BASIS[1],
            arbeitszeiten=json.dumps({t: ["08:00", "18:00"] for t in ("mo", "di", "mi", "do", "fr")}),
            termin_dauer_min=90, puffer_min=30, max_termine_tag=4,
            gebiet_plz_praefixe=json.dumps(gebiet or []), aktiv_terminierung=True,
            terminiert_selbst=False, kompetenz_sparten=json.dumps(["WP", "PV", "KL", "WB", "GW"]),
            kompetenz_kombi=True, kompetenz_mfh=True, kompetenz_gewerbe=True))
        cls.s.flush()
        return b

    def setUp(self):
        self.s.rollback()
        lead_termin.vorschlaege_cache_leeren()
        # Termine der Test-Vertriebler aus früheren Fällen räumen (sonst Konflikte am selben Tag)
        ad_ids = [self.horst.id, self.rudi.id, self.fremd.id]
        for t in self.s.query(VotTermin).filter(VotTermin.ad_id.in_(ad_ids)):
            self.s.query(OutlookAuftrag).filter_by(termin_id=t.id, termin_art="vot").delete()
            self.s.query(KommunikationLog).filter_by(termin_id=t.id).delete()
            self.s.delete(t)
        self.s.commit()
        self.schalter("terminierung_aktiv", "aus")
        self.schalter("mail_versand_aktiv", "aus")
        self.schalter("termin_konflikt_modus", "warnen")

    def schalter(self, name, wert):
        kern.parameter_setzen(self.s, name, wert)
        self.s.commit()

    def lead(self, nr, sparten=("WP",), phase="qualifiziert", ad_id=None, grosskunde=False, **extra):
        quelle = (self.s.query(LeadQuelle).filter_by(key="website").first()
                  or self.s.query(LeadQuelle).first())
        daten = {"anrede": "Herr", "vorname": f"V{nr}", "nachname": f"{NACHNAME}-{nr}",
                 "strasse": f"Teststraße {nr}", "plz": "47139", "ort": "Duisburg",
                 "telefon": f"0203 88{nr:04d}", "email": f"v37l2-{nr}@test.invalid",
                 "sparten": list(sparten)}
        vorgang, _ = kern.lead_anlegen(self.s, daten, quelle, "api", entscheidung="neu")
        kunde = self.s.get(Kunde, vorgang.kunde_id)
        kunde.vertriebskanal = "Empfehlung"
        kunde.objektart = "EFH"
        kunde.grosskunde = grosskunde
        vorgang.lead_phase = phase
        vorgang.ad_id = ad_id
        vorgang.lat, vorgang.lon, vorgang.geocode_status = BASIS[0], BASIS[1], "ok"
        for k, v in extra.items():
            setattr(vorgang, k, v)
        self.s.query(VorgangObjekt).filter_by(vorgang_id=vorgang.id).delete()
        haupt = objekte_modul.hauptobjekt(self.s, vorgang.id, anlegen=True, kunde=kunde)
        haupt.lat, haupt.lon, haupt.geocode_status = BASIS[0], BASIS[1], "ok"
        self.s.commit()
        return vorgang

    def objekt(self, vorgang, nr, km_nord=2.0):
        o = objekte_modul.objekt_anlegen(self.s, vorgang, strasse=f"Objektweg {nr}", plz="47051",
                                         ort="Duisburg", bezeichnung=f"Objekt {nr}", objektart="EFH",
                                         interessen=["PV"])
        o.lat, o.lon, o.geocode_status = BASIS[0] + km_nord / 111.0, BASIS[1], "ok"
        self.s.commit()
        return o

    def termin(self, vorgang, ad, beginn, status="geplant", quelle="manuell", objekt=None, km_nord=0.0):
        haupt = objekte_modul.hauptobjekt(self.s, vorgang.id)
        t = VotTermin(vorgang_id=vorgang.id, ad_id=ad.id, beginn=beginn, ende=beginn + timedelta(minutes=90),
                      adresse="Teststraße, 47139 Duisburg", lat=BASIS[0] + km_nord / 111.0, lon=BASIS[1],
                      status=status, quelle=quelle, typ="vot", medium="vor_ort", demo=False,
                      objekt_id=(objekt.id if objekt is not None else (haupt.id if haupt else None)))
        self.s.add(t)
        self.s.commit()
        return t

    def monday_termin(self, vorgang, ad, beginn):
        # SQLite vergibt gelöschte IDs neu – die DB-Kopie trägt verwaiste vorgaenge.lead_id anderer
        # Tests (UNIQUE); die Test-Lead-Zeile bekommt deshalb eine ID oberhalb aller Verweise
        from sqlalchemy import func
        frei = max(self.s.query(func.max(Lead.id)).scalar() or 0,
                   self.s.query(func.max(Vorgang.lead_id)).scalar() or 0) + 1
        lead = Lead(id=frei, monday_item_id=f"{PRAEFIX}-{vorgang.id}", board_id="t", board_name="Deals",
                    vot_datum=beginn, nachname=f"{NACHNAME}-m", plz="47139", ort="Duisburg",
                    benutzer_id=ad.id, kunde_id=vorgang.kunde_id)
        self.s.add(lead)
        self.s.flush()
        vorgang.lead_id = lead.id
        t = self.termin(vorgang, ad, beginn, quelle="monday")
        t.monday_beginn = beginn
        self.s.commit()
        return lead, t

    def aktivitaeten(self, vorgang_id):
        return [a.text for a in self.s.query(LeadAktivitaet).filter_by(vorgang_id=vorgang_id)
                .order_by(LeadAktivitaet.id)]

    def frisch(self, obj):
        self.s.expire_all()
        return self.s.get(type(obj), obj.id)

    def anpassen(self, client, vorgang, termin, **daten):
        return client.post(f"/lead-management/lead/{vorgang.id}/termin/{termin.id}/anpassen",
                           json=daten, headers={"Accept": "application/json"})


# --- (c) Termine anpassen -------------------------------------------------------------------------

class TermineAnpassen(Basis):
    def test_c1_datum_und_vertriebler_mit_aktivitaet_ohne_folgen_in_der_testphase(self):
        v = self.lead(1, ad_id=self.rudi.id)
        alt = naechster_werktag(4, 10)
        t = self.termin(v, self.rudi, alt)
        neu = naechster_werktag(5, 14)
        auftraege = self.s.query(OutlookAuftrag).count()
        mails = self.s.query(KommunikationLog).filter_by(vorgang_id=v.id).count()
        r = self.anpassen(self.client_innen, v, t, datum=neu.strftime("%Y-%m-%d"), uhrzeit="14:00",
                          ad_id=self.horst.id, bemerkung="Kunde wünscht Nachmittag")
        self.assertEqual(r.status_code, 200, r.text)
        d = r.json()
        self.assertTrue(d["ok"])
        self.assertIn("Testphase: nur im Tool geändert", d["meldung"])
        t = self.frisch(t)
        self.assertEqual(t.beginn, neu)
        self.assertEqual(t.ende, neu + timedelta(minutes=90))
        self.assertEqual(t.ad_id, self.horst.id)
        self.assertEqual(t.grund_text, "Kunde wünscht Nachmittag")
        self.assertIsNotNone(t.angepasst_am)
        self.assertEqual(t.angepasst_von, self.innen.id)
        texte = self.aktivitaeten(v.id)
        angepasst = [x for x in texte if x.startswith("Termin angepasst:")]
        self.assertEqual(len(angepasst), 1, texte)
        self.assertIn(f"Datum/Zeit {alt:%d.%m.%Y %H:%M} → {neu:%d.%m.%Y %H:%M}", angepasst[0])
        self.assertIn(f"Vertriebler {self.rudi.name} → {self.horst.name}", angepasst[0])
        self.assertIn("Testphase: nur im Tool geändert", angepasst[0])
        # keine Outlook-Aufträge, keine Kundenmail (Testphase), kein monday-Hinweis (kein monday-Termin)
        self.assertEqual(self.s.query(OutlookAuftrag).count(), auftraege)
        self.assertEqual(self.s.query(KommunikationLog).filter_by(vorgang_id=v.id).count(), mails)
        self.assertNotIn("monday", angepasst[0])
        # Zuständiger des Vorgangs folgt dem Vertriebler des aktiven Termins [ANNAHME]
        self.assertEqual(self.frisch(v).ad_id, self.horst.id)
        # keine Änderung → ok ohne neue Aktivität
        r = self.anpassen(self.client_innen, v, t, datum=neu.strftime("%Y-%m-%d"), uhrzeit="14:00",
                          ad_id=self.horst.id, bemerkung="Kunde wünscht Nachmittag")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()["meldung"], "Keine Änderung.")
        self.assertEqual(len([x for x in self.aktivitaeten(v.id) if x.startswith("Termin angepasst:")]), 1)

    def test_c2_monday_termin_mit_ursprungshinweis_und_sync_setzt_nicht_zurueck(self):
        v = self.lead(2, ad_id=self.rudi.id)
        alt = naechster_werktag(4, 10)
        lead, t = self.monday_termin(v, self.rudi, alt)
        neu = naechster_werktag(5, 14)
        r = self.anpassen(self.client_innen, v, t, datum=neu.strftime("%Y-%m-%d"), uhrzeit="14:00",
                          ad_id=self.horst.id)
        self.assertEqual(r.status_code, 200, r.text)
        hinweis = f"ursprünglich aus monday: {alt:%d.%m.%Y %H:%M}"
        self.assertEqual(r.json()["termin"]["monday_hinweis"], hinweis)
        t = self.frisch(t)
        self.assertEqual(lead_termin.monday_hinweis(t), hinweis)
        self.assertEqual(t.monday_beginn, alt)
        self.assertEqual(t.beginn, neu)
        self.assertEqual(t.quelle, "monday")
        angepasst = [x for x in self.aktivitaeten(v.id) if x.startswith("Termin angepasst:")]
        self.assertEqual(len(angepasst), 1)
        self.assertIn(hinweis, angepasst[0])
        # Kartei: Hinweis sichtbar, Knopf „Anpassen“ auch am monday-Termin, Dialog vorhanden
        seite = self.client_innen.get(f"/lead-management/lead/{v.id}").text
        self.assertIn(hinweis, seite)
        self.assertIn(f'data-termin-anpassen="{t.id}"', seite)
        self.assertIn(f'id="dlg-anpassen-{t.id}"', seite)
        self.assertIn("monday wird nicht zurückgeschrieben", seite)
        # Sync: monday trägt noch das alte Datum → der Termin bleibt wie angepasst
        z = monday_sync.vot_termine_nachfuehren(self.s, nur_vorgang_ids=[v.id])
        self.s.commit()
        t = self.frisch(t)
        self.assertEqual((t.beginn, t.ad_id), (neu, self.horst.id))
        self.assertEqual(z["aktualisiert"], 0)
        # monday ändert das Datum → monday gewinnt, Anpassung endet (Aktivität)
        lead = self.frisch(lead)
        neu_monday = naechster_werktag(8, 9)
        lead.vot_datum = neu_monday
        self.s.commit()
        z = monday_sync.vot_termine_nachfuehren(self.s, nur_vorgang_ids=[v.id])
        self.s.commit()
        t = self.frisch(t)
        self.assertEqual((t.beginn, t.ad_id, t.monday_beginn), (neu_monday, self.rudi.id, neu_monday))
        self.assertIsNone(t.angepasst_am)
        self.assertEqual(z["aktualisiert"], 1)
        self.assertTrue(any(x.startswith("monday-Termin neu gesetzt") for x in self.aktivitaeten(v.id)))
        self.assertEqual(lead_termin.monday_hinweis(t), "")

    def test_c3_konflikte_sperren_und_warnen(self):
        v = self.lead(3, ad_id=self.horst.id)
        tag = naechster_werktag(4, 10)
        t = self.termin(v, self.horst, tag)
        # anderer Termin von Horst 09:00–10:30 am selben Tag (anderer Lead)
        v2 = self.lead(4, ad_id=self.horst.id)
        self.termin(v2, self.horst, tag.replace(hour=9, minute=0), km_nord=1.0)
        # harte Überschneidung sperrt immer (auch im Modus warnen)
        r = self.anpassen(self.client_innen, v, t, datum=tag.strftime("%Y-%m-%d"), uhrzeit="09:30")
        self.assertEqual(r.status_code, 409, r.text)
        self.assertFalse(r.json()["bestaetigung_noetig"])
        self.assertIn("Überschneidung", r.json()["meldung"])
        # Pufferverletzung: Modus warnen → 409 mit bestaetigung_noetig, dann 200 mit bestaetigt
        r = self.anpassen(self.client_innen, v, t, datum=tag.strftime("%Y-%m-%d"), uhrzeit="10:45")
        self.assertEqual(r.status_code, 409, r.text)
        self.assertTrue(r.json()["bestaetigung_noetig"])
        self.assertTrue(any("Puffer" in k for k in r.json()["konflikte"]), r.json())
        self.assertEqual(self.frisch(t).beginn, tag)
        r = self.anpassen(self.client_innen, v, t, datum=tag.strftime("%Y-%m-%d"), uhrzeit="10:45", bestaetigt="1")
        self.assertEqual(r.status_code, 200, r.text)
        self.assertEqual(self.frisch(t).beginn, tag.replace(hour=10, minute=45))
        # Modus sperren → 409 ohne Bestätigungsmöglichkeit
        self.schalter("termin_konflikt_modus", "sperren")
        r = self.anpassen(self.client_innen, v, t, datum=tag.strftime("%Y-%m-%d"), uhrzeit="10:30", bestaetigt="1")
        self.assertEqual(r.status_code, 409, r.text)
        self.assertFalse(r.json()["bestaetigung_noetig"])
        self.assertEqual(self.frisch(t).beginn, tag.replace(hour=10, minute=45))

    def test_c4_rechte_fremder_ad_403_eigener_ad_200_und_neuanlage_gesperrt(self):
        v = self.lead(5, ad_id=self.horst.id)
        tag = naechster_werktag(4, 10)
        t = self.termin(v, self.horst, tag)
        r = self.anpassen(self.client_fremd, v, t, datum=tag.strftime("%Y-%m-%d"), uhrzeit="11:00")
        self.assertEqual(r.status_code, 403, r.text)
        self.assertEqual(self.frisch(t).beginn, tag)
        r = self.anpassen(self.client_horst, v, t, datum=tag.strftime("%Y-%m-%d"), uhrzeit="11:00")
        self.assertEqual(r.status_code, 200, r.text)
        self.assertEqual(self.frisch(t).beginn, tag.replace(hour=11))
        # Formular ohne JSON: 303 in die Kartei mit Meldung
        r = self.client_innen.post(f"/lead-management/lead/{v.id}/termin/{t.id}/anpassen",
                                   data={"datum": tag.strftime("%Y-%m-%d"), "uhrzeit": "11:15",
                                         "ad_id": str(self.horst.id), "bemerkung": ""})
        self.assertEqual(r.status_code, 303, r.text)
        self.assertIn("Termin angepasst", meldung_aus(r))
        self.assertTrue(r.headers["location"].endswith("#termine"))
        # manuelle Neuanlage bleibt in der Testphase gesperrt [OFFEN 1]
        r = self.client_innen.post(f"/lead-management/lead/{v.id}/termin/manuell",
                                   data={"datum": naechster_werktag(6).strftime("%Y-%m-%d"), "uhrzeit": "10:00",
                                         "ad_id": str(self.horst.id), "quelle": "manuell"},
                                   headers={"Accept": "application/json"})
        self.assertEqual(r.status_code, 403)
        self.assertTrue(r.json().get("testphase"))
        # Vergangenheit und fremder Termin
        r = self.anpassen(self.client_innen, v, t, datum="2020-01-06", uhrzeit="10:00")
        self.assertEqual(r.status_code, 400)
        r = self.client_innen.post(f"/lead-management/lead/{v.id}/termin/999999/anpassen", json={},
                                   headers={"Accept": "application/json"})
        self.assertEqual(r.status_code, 404)

    def test_c5_folgen_nach_freischaltung_outlook_und_terminaenderung(self):
        v = self.lead(6, ad_id=self.horst.id)
        tag = naechster_werktag(4, 10)
        t = self.termin(v, self.horst, tag)
        self.schalter("terminierung_aktiv", "an")
        self.schalter("mail_versand_aktiv", "an")
        self.schalter("kalender_sync", "an")
        with mock.patch("app.graph_versand.eingerichtet", return_value=True, create=True):
            r = self.anpassen(self.client_innen, v, t, datum=tag.strftime("%Y-%m-%d"), uhrzeit="12:00")
        self.assertEqual(r.status_code, 200, r.text)
        self.assertNotIn("Testphase", r.json()["meldung"])
        vorlagen = [(m.vorlage_key, m.status) for m in self.s.query(KommunikationLog).filter_by(vorgang_id=v.id)]
        self.assertIn(("terminaenderung", "geplant"), vorlagen)
        self.assertIn(("terminerinnerung", "geplant"), vorlagen)
        auftraege = self.s.query(OutlookAuftrag).filter_by(termin_art="vot", termin_id=t.id).all()
        self.assertTrue(auftraege, "Outlook-Auftrag (aendern/anlegen) erwartet")
        self.assertEqual(self.frisch(t).ics_sequence, 1)


# --- (d) Routing ----------------------------------------------------------------------------------

class Routing(Basis):
    def setUp(self):
        super().setUp()
        self.schalter("routing_anbieter", "ors")
        self.s.query(routing.RoutingCache).delete(synchronize_session=False)
        self.s.commit()

    def test_d1_pruefpunkt_ohne_key_und_mit_mock(self):
        with mock.patch.object(config, "ORS_API_KEY", ""):
            self.schalter("ors_api_key", "")
            ok, text = routing.dienst_pruefen(self.s)
            self.assertFalse(ok)
            self.assertIn("ORS_API_KEY fehlt", text)
            self.assertEqual(routing.ors_schluessel_quelle(self.s), "")
            # Route (Admin): Meldung landet auf der aufrufenden Seite
            r = self.client.post("/parametrierung/lead-routing/test",
                                 data={"zurueck": "/parametrierung/lead-einstellungen"})
            self.assertEqual(r.status_code, 303)
            self.assertIn("ORS_API_KEY fehlt", meldung_aus(r))
            self.assertTrue(r.headers["location"].startswith("/parametrierung/lead-einstellungen"))
        vorher = routing.aufrufe_heute(self.s)
        with mock.patch.object(routing, "ors_schluessel", return_value="mock"), \
                mock.patch.object(routing, "_ors_matrix", return_value=([[1860.0]], [[28000.0]])) as m:
            ok, text = routing.dienst_pruefen(self.s)
        self.assertTrue(ok, text)
        self.assertEqual(text, "Routing-Dienst antwortet (ors): Duisburg → Bochum 28,0 km · 31 Min")
        self.assertEqual(m.call_count, 1)
        self.assertEqual(routing.aufrufe_heute(self.s), vorher + 1)
        self.assertIn("28,0 km · 31 Min", routing.letzte_pruefung(self.s))
        # Fehlertext bei Ausfall, Nicht-Admin darf nicht
        with mock.patch.object(routing, "ors_schluessel", return_value="mock"), \
                mock.patch.object(routing, "_ors_matrix", side_effect=OSError("timeout")):
            ok, text = routing.dienst_pruefen(self.s)
        self.assertFalse(ok)
        self.assertIn("antwortet nicht", text)
        r = self.client_innen.post("/parametrierung/lead-routing/test", data={})
        self.assertEqual(r.status_code, 303)
        self.assertEqual(r.headers["location"], "/parametrierung")

    def test_d2_vorschlaege_und_kalender_zeigen_km_vom_dienst_sonst_geschaetzt(self):
        v = self.lead(10, ad_id=self.horst.id)
        self.termin(v, self.rudi, naechster_werktag(4, 9), km_nord=3.0)   # Nachbartermin für Umweg
        with mock.patch.object(routing, "ors_schluessel", return_value="mock"), \
                mock.patch.object(routing, "_ors_matrix", side_effect=matrix_mock) as m:
            d = lead_termin.vorschlaege_json(self.s, v, benutzer=self.innen)
            self.s.commit()
        self.assertEqual(d["status"], "ok", d)
        self.assertTrue(d["vorschlaege"])
        self.assertGreaterEqual(m.call_count, 1)
        erster = d["vorschlaege"][0]
        self.assertRegex(erster["anfahrt_text"], r"^\d+,\d km · \d+ Min$")
        self.assertNotIn("geschätzt", erster["anfahrt_text"])
        self.assertIn("Anfahrt " + erster["anfahrt_text"], erster["begruendung"])
        self.assertIn("umweg_km", erster)
        self.assertNotIn("Luftlinie", erster["begruendung"])
        # Kalenderansicht trägt die Strecke im Vorschlags-Slot
        with mock.patch.object(routing, "ors_schluessel", return_value="mock"), \
                mock.patch.object(routing, "_ors_matrix", side_effect=matrix_mock):
            k = lead_termin.kalender_json(self.s, v, benutzer=self.innen, neu=True)
        self.assertEqual(k["vorschlaege"][0]["anfahrt_text"], erster["anfahrt_text"])
        # Assistentenseite: Strecke je Vorschlag
        seite = self.client_innen.get(f"/lead-management/lead/{v.id}/termin").text
        self.assertIn('data-rolle="strecke"', seite)
        self.assertIn("Anfahrt <strong>" + erster["anfahrt_text"], seite)
        # Ausfall des Dienstes → Luftlinie × 1,3 mit Kennzeichen „geschätzt“
        self.s.query(routing.RoutingCache).delete(synchronize_session=False)
        self.s.commit()
        lead_termin.vorschlaege_cache_leeren()
        with mock.patch.object(routing, "ors_schluessel", return_value="mock"), \
                mock.patch.object(routing, "_ors_matrix", side_effect=OSError("down")):
            d = lead_termin.vorschlaege_json(self.s, v, benutzer=self.innen)
            self.s.commit()
        self.assertRegex(d["vorschlaege"][0]["anfahrt_text"], r"^ca\. \d+ km · \d+ Min \(geschätzt\)$")
        self.assertTrue(d["vorschlaege"][0]["geschaetzt"])
        # ohne Key: kein Netzaufruf, geschätzt
        self.s.query(routing.RoutingCache).delete(synchronize_session=False)
        self.s.commit()
        lead_termin.vorschlaege_cache_leeren()
        with mock.patch.object(config, "ORS_API_KEY", ""), \
                mock.patch.object(routing, "_ors_matrix", side_effect=AssertionError("kein Netz erwartet")) as m:
            d = lead_termin.vorschlaege_json(self.s, v, benutzer=self.innen)
            self.s.commit()
        self.assertEqual(m.call_count, 0)
        self.assertIn("geschätzt", d["vorschlaege"][0]["anfahrt_text"])

    def test_d3_mein_tag_zeigt_strecke_vom_start_und_vom_vortermin(self):
        v = self.lead(11, ad_id=self.horst.id)
        heute = datetime.now().replace(hour=23, minute=0, second=0, microsecond=0)
        t1 = self.termin(v, self.horst, heute - timedelta(hours=13), km_nord=2.0)     # 10:00
        v2 = self.lead(12, ad_id=self.horst.id)
        t2 = self.termin(v2, self.horst, heute - timedelta(hours=9), km_nord=6.0)      # 14:00
        jetzt = heute - timedelta(hours=14)   # 09:00 – beide Termine liegen noch vor uns
        with mock.patch.object(routing, "ors_schluessel", return_value="mock"), \
                mock.patch.object(routing, "_ors_matrix", side_effect=matrix_mock) as m:
            daten = mein_tag.termine(self.s, self.horst, heute=jetzt)
            self.s.commit()
        self.assertEqual(m.call_count, 1, "ein gebündelter Matrix-Aufruf")
        karten = {k["termin"].id: k for k in daten["heute"]}
        self.assertIn(t1.id, karten)
        self.assertIn(t2.id, karten)
        self.assertRegex(karten[t1.id]["strecke_text"], r"^\d+,\d km · \d+ Min$")
        self.assertEqual(karten[t1.id]["strecke_von"], mein_tag.STRECKE_VON_START)
        self.assertEqual(karten[t2.id]["strecke_von"], "vom Termin " + karten[t1.id]["uhr"])
        self.assertEqual(daten["naechster"]["termin"].id, t1.id)
        self.assertEqual(daten["naechster"]["strecke_text"], karten[t1.id]["strecke_text"])
        # Seite des Außendienstlers zeigt die Strecke (Karte „Als Nächstes“ und Zeile „Heute“)
        with mock.patch.object(routing, "ors_schluessel", return_value="mock"), \
                mock.patch.object(routing, "_ors_matrix", side_effect=matrix_mock):
            seite = self.client_horst.get("/leads").text
        self.assertIn("data-mt-strecke", seite)
        self.assertIn("km · ", seite)
        self.assertIn(mein_tag.STRECKE_VON_START, seite)

    def test_d4_ersatzkunde_und_karte_mit_strecke(self):
        v = self.lead(13, ad_id=self.horst.id)
        tag = naechster_werktag(4, 10)
        t = self.termin(v, self.horst, tag)
        kandidat = self.lead(14, phase="qualifiziert")
        kandidat.lat, kandidat.lon = BASIS[0] + 0.02, BASIS[1]
        kandidat.eingang_am = datetime.now() - timedelta(days=20)
        self.s.commit()
        with mock.patch.object(routing, "ors_schluessel", return_value="mock"), \
                mock.patch.object(routing, "_ors_matrix", side_effect=matrix_mock):
            daten = lead_termin.ersatz_kandidaten(self.s, t)
            self.s.commit()
        treffer = [k for k in daten["kandidaten"] if k["vorgang"].id == kandidat.id]
        self.assertTrue(treffer, daten["kandidaten"])
        self.assertRegex(treffer[0]["strecke_text"], r"^\d+,\d km · \d+ Min$")
        self.assertIn("Strecke " + treffer[0]["strecke_text"], treffer[0]["begruendung"])
        with mock.patch.object(routing, "ors_schluessel", return_value="mock"), \
                mock.patch.object(routing, "_ors_matrix", side_effect=matrix_mock):
            seite = self.client_innen.get(f"/lead-management/termin/{t.id}/ersatz").text
        self.assertIn(treffer[0]["strecke_text"], seite)
        # Karte: Termin-Pin mit Strecke von der Startadresse des Vertrieblers
        with mock.patch.object(routing, "ors_schluessel", return_value="mock"), \
                mock.patch.object(routing, "_ors_matrix", side_effect=matrix_mock):
            r = self.client_innen.get(f"/lead-management/karte/daten?ad_id={self.horst.id}&tage=30")
        pins = [p for p in r.json()["pins"] if p["art"] == "termin" and p["vorgang_id"] == v.id]
        self.assertTrue(pins)
        self.assertRegex(pins[0]["strecke"], r"^\d+,\d km · \d+ Min$")

    def test_d5_key_aus_env_hat_vorrang_und_erscheint_nirgends(self):
        self.schalter("ors_api_key", "parameter-schluessel")
        with mock.patch.object(config, "ORS_API_KEY", "env-schluessel"):
            self.assertEqual(routing.ors_schluessel(self.s), "env-schluessel")
            self.assertEqual(routing.ors_schluessel_quelle(self.s), "env")
            self.assertTrue(routing.dienst_aktiv(self.s))
            for url in ("/parametrierung/lead-einstellungen", "/parametrierung/lead-routing"):
                seite = self.client.get(url).text
                self.assertNotIn("env-schluessel", seite, url)
                self.assertIn("ORS_API_KEY in der .env vorhanden", seite, url)
            pruef = [p for p in lead_v2.freischaltung_pruefpunkte(self.s) if p["name"].startswith("Routing")]
            self.assertTrue(pruef[0]["ok"])
            self.assertIn(".env", pruef[0]["text"])
        with mock.patch.object(config, "ORS_API_KEY", ""):
            self.assertEqual(routing.ors_schluessel(self.s), "parameter-schluessel")
            self.assertEqual(routing.ors_schluessel_quelle(self.s), "parameter")
            self.schalter("ors_api_key", "")
            self.assertEqual(routing.ors_schluessel_quelle(self.s), "")
            seite = self.client.get("/parametrierung/lead-einstellungen").text
            self.assertIn("ORS_API_KEY fehlt", seite)
            self.assertNotIn("parameter-schluessel", seite)

    def test_d6_kontingent_hinweis_und_stopp(self):
        self.schalter(routing.KONTINGENT_PARAMETER, "10")
        self.schalter(_zaehler_name(), "8")
        status = routing.kontingent_status(self.s)
        self.assertEqual((status["aufrufe"], status["kontingent"], status["prozent"]), (8, 10, 80))
        self.assertTrue(status["warnung"])
        self.assertFalse(status["erschoepft"])
        seite = self.client.get("/parametrierung/lead-einstellungen").text
        self.assertIn('data-rolle="routing-warnung"', seite)
        self.assertIn("80 % des Tageskontingents", seite)
        # 100 % erreicht: kein Matrix-Aufruf mehr, Fahrzeiten geschätzt
        self.schalter(_zaehler_name(), "10")
        self.assertTrue(routing.kontingent_status(self.s)["erschoepft"])
        with mock.patch.object(routing, "ors_schluessel", return_value="mock"), \
                mock.patch.object(routing, "_ors_matrix", side_effect=AssertionError("kein Netz erwartet")) as m:
            routing.matrix_fuellen(self.s, [BASIS], [(BASIS[0] + 0.05, BASIS[1])])
            self.s.commit()
        self.assertEqual(m.call_count, 0)
        self.assertTrue(routing.strecke(self.s, BASIS, (BASIS[0] + 0.05, BASIS[1]))["geschaetzt"])
        self.schalter(_zaehler_name(), "0")
        self.schalter(routing.KONTINGENT_PARAMETER, str(routing.KONTINGENT_STANDARD))

    def test_d7_migration_setzt_anbieter_idempotent(self):
        self.schalter("routing_anbieter", "luftlinie")
        with mock.patch.object(config, "ORS_API_KEY", ""):
            self.schalter("ors_api_key", "")
            meldungen = routing.migration_v37_routing(self.s)
            self.s.commit()
            self.assertEqual(routing.anbieter(self.s), "luftlinie")
            self.assertTrue(any("ORS_API_KEY fehlt" in m for m in meldungen), meldungen)
        with mock.patch.object(config, "ORS_API_KEY", "env-schluessel"):
            meldungen = routing.migration_v37_routing(self.s)
            self.s.commit()
            self.assertEqual(routing.anbieter(self.s), "ors")
            self.assertTrue(any("luftlinie -> ors" in m for m in meldungen), meldungen)
            meldungen = routing.migration_v37_routing(self.s)
            self.s.commit()
            self.assertEqual(meldungen, [])
        self.assertEqual(routing.kontingent(self.s), routing.KONTINGENT_STANDARD)

    def test_d7b_kontingent_2000_wird_einmalig_500(self):
        """Nachtrag 17.10.2026 (Rückfrage 12): Standard 500 (ORS Free-Plan); der alte v37-Standard 2000 wird
        einmalig nachgezogen, von Hand gesetzte Werte und ein später bewusst eingetragenes 2000 bleiben."""
        from app.models import Einstellung, einstellung_holen, einstellung_setzen
        self.assertEqual(routing.KONTINGENT_STANDARD, 500)
        marker_alt = einstellung_holen(self.s, routing.MARKER_KONTINGENT, "")
        try:
            self.s.query(Einstellung).filter(Einstellung.name == routing.MARKER_KONTINGENT).delete(synchronize_session=False)
            self.schalter(routing.KONTINGENT_PARAMETER, "2000")
            meldungen = routing.migration_v37_routing(self.s)
            self.s.commit()
            self.assertEqual(routing.kontingent(self.s), 500)
            self.assertTrue(any("2000 -> 500" in m for m in meldungen), meldungen)
            self.assertEqual(einstellung_holen(self.s, routing.MARKER_KONTINGENT, ""), "erledigt")
            # bewusst wieder 2000 (bezahlter Plan): bleibt, keine Meldung
            self.schalter(routing.KONTINGENT_PARAMETER, "2000")
            meldungen = routing.migration_v37_routing(self.s)
            self.s.commit()
            self.assertEqual(routing.kontingent(self.s), 2000)
            self.assertFalse(any("2000 -> 500" in m for m in meldungen), meldungen)
            # von Hand gesetzter Wert ohne Marker: bleibt (nur der alte Standard wird nachgezogen)
            self.s.query(Einstellung).filter(Einstellung.name == routing.MARKER_KONTINGENT).delete(synchronize_session=False)
            self.schalter(routing.KONTINGENT_PARAMETER, "1500")
            routing.migration_v37_routing(self.s)
            self.s.commit()
            self.assertEqual(routing.kontingent(self.s), 1500)
        finally:
            self.schalter(routing.KONTINGENT_PARAMETER, str(routing.KONTINGENT_STANDARD))
            if marker_alt:
                einstellung_setzen(self.s, routing.MARKER_KONTINGENT, marker_alt)
            else:
                self.s.query(Einstellung).filter(Einstellung.name == routing.MARKER_KONTINGENT).delete(synchronize_session=False)
            self.s.commit()

    def test_d8_textformat(self):
        self.assertEqual(routing.strecke_text({"km": 18.44, "minuten": 24.4, "geschaetzt": False}), "18,4 km · 24 Min")
        self.assertEqual(routing.strecke_text({"km": 23.6, "minuten": 31.2, "geschaetzt": True}), "ca. 24 km · 31 Min (geschätzt)")
        self.assertEqual(routing.strecke_text(None), "")
        self.assertEqual(lead_termin.umweg_strecke_text(0.0, 0, False), "kein Umweg")
        self.assertEqual(lead_termin.umweg_strecke_text(3.24, 5.4, False), "+3,2 km · 5 Min")
        self.assertEqual(lead_termin.umweg_strecke_text(3.24, 5.4, True), "ca. +3 km · 5 Min (geschätzt)")


# --- (e) Objekte-Akkordeon -------------------------------------------------------------------------

class ObjekteAkkordeon(Basis):
    def test_e1_grosskunde_fuenf_objekte_zu_kopfzeile_und_zustand_je_nutzer(self):
        v = self.lead(20, ad_id=self.horst.id, grosskunde=True)
        objekte = [self.objekt(v, nr, km_nord=nr) for nr in range(2, 6)]
        tag = naechster_werktag(4, 10)
        self.termin(v, self.horst, tag)                                   # Hauptobjekt
        self.termin(v, self.horst, tag + timedelta(hours=3), objekt=objekte[0], km_nord=2.0)
        seite = self.client_innen.get(f"/lead-management/lead/{v.id}").text
        self.assertIn('id="lk-objekte-akkordeon"', seite)
        kopf = re.search(r'<details class="lk-objekte-akkordeon"[^>]*>', seite).group(0)
        self.assertNotIn(" open", kopf)
        self.assertEqual(kopf.count('data-zu-standard="1"'), 1)
        self.assertIn("5 Objekte · 2 mit Termin · 0 mit Angebot", seite)
        ctx = lead_kartei.objekte_kontext(self.s, v, self.s.get(Kunde, v.kunde_id), {}, benutzer=self.innen)
        self.assertTrue(ctx["zu"])
        self.assertEqual(ctx["kopfzeile"], "5 Objekte · 2 mit Termin · 0 mit Angebot")
        # Aufklappen merken → nach Neuladen offen (nur für diesen Nutzer)
        r = self.client_innen.post(f"/lead-management/lead/{v.id}/objekte/zustand", json={"zu": False},
                                   headers={"Accept": "application/json"})
        self.assertEqual(r.status_code, 200, r.text)
        self.assertEqual(r.json(), {"ok": True, "zu": False, "vorgang_id": v.id})
        seite = self.client_innen.get(f"/lead-management/lead/{v.id}").text
        kopf = re.search(r'<details class="lk-objekte-akkordeon"[^>]*>', seite).group(0)
        self.assertIn(" open", kopf)
        seite_horst = self.client_horst.get(f"/lead-management/lead/{v.id}").text
        kopf = re.search(r'<details class="lk-objekte-akkordeon"[^>]*>', seite_horst).group(0)
        self.assertNotIn(" open", kopf)
        self.assertEqual(lead_kartei.objekte_zustand_holen(self.s, self.innen).get(str(v.id)), False)
        # wieder zuklappen
        r = self.client_innen.post(f"/lead-management/lead/{v.id}/objekte/zustand", json={"zu": True},
                                   headers={"Accept": "application/json"})
        self.assertEqual(r.json()["zu"], True)
        kopf = re.search(r'<details class="lk-objekte-akkordeon"[^>]*>',
                         self.client_innen.get(f"/lead-management/lead/{v.id}").text).group(0)
        self.assertNotIn(" open", kopf)

    def test_e2_zwei_objekte_ohne_grosskunde_offen_vier_objekte_zu_ein_objekt_ohne_akkordeon(self):
        v = self.lead(21, ad_id=self.horst.id)
        seite = self.client_innen.get(f"/lead-management/lead/{v.id}").text
        self.assertNotIn("lk-objekte-akkordeon", seite)
        self.objekt(v, 2)
        seite = self.client_innen.get(f"/lead-management/lead/{v.id}").text
        kopf = re.search(r'<details class="lk-objekte-akkordeon"[^>]*>', seite).group(0)
        self.assertIn(" open", kopf)
        self.assertIn("2 Objekte · 0 mit Termin · 0 mit Angebot", seite)
        for nr in (3, 4, 5):
            self.objekt(v, nr, km_nord=nr)
        seite = self.client_innen.get(f"/lead-management/lead/{v.id}").text
        kopf = re.search(r'<details class="lk-objekte-akkordeon"[^>]*>', seite).group(0)
        self.assertNotIn(" open", kopf)
        self.assertIn("5 Objekte · 0 mit Termin · 0 mit Angebot", seite)
        # Pflichtfeld-Zähler und Autospeichern-Formulare bleiben im (zugeklappten) Akkordeon
        self.assertEqual(seite.count('class="lk-autospeichern lk-objekt-form"'), 5)
        self.assertIn('id="lk-pflicht-zaehler"', seite)


# --- (f) Dashboard ---------------------------------------------------------------------------------

class Dashboard(Basis):
    def test_f1_ohne_routenplaner_alte_reihenfolge_ohne_fehler(self):
        self.assertNotIn("routenplaner", lead_dashboard.KACHEL_KEYS)
        self.assertIn("routenplaner", lead_dashboard.KACHELN_ENTFALLEN)
        lead_v2.einstellung_setzen(self.s, self.innen.id, lead_dashboard.KACHELN_EINSTELLUNG,
                                   ["routenplaner", "termine", "faellig"])
        self.s.commit()
        reihenfolge = lead_dashboard.kachel_reihenfolge(self.s, self.innen)
        self.assertNotIn("routenplaner", reihenfolge)
        self.assertEqual(reihenfolge[:2], ["termine", "faellig"])
        self.assertEqual(sorted(reihenfolge), sorted(lead_dashboard.KACHEL_KEYS))
        r = self.client_innen.get("/lead-management/dashboard")
        self.assertEqual(r.status_code, 200)
        self.assertNotIn("Routenplaner", r.text)
        self.assertNotIn('data-kachel="routenplaner"', r.text)
        self.assertNotIn("lm-routen-link", r.text)
        self.assertIn('data-kachel="termine"', r.text)
        # Parameter routen_start bleibt (Startpunkt für Mein Tag/Kalender)
        self.assertTrue(lead_dashboard.routen_start(self.s))


# --- (g) Login -------------------------------------------------------------------------------------

class Login(Basis):
    def test_g1_vorbelegung_ueber_cookie_anderer_benutzer_leert_abmelden_behaelt(self):
        c = TestClient(app, follow_redirects=False)
        seite = c.get("/login")
        self.assertEqual(seite.status_code, 200)
        self.assertIn('data-vorgewaehlt=""', seite.text)
        self.assertNotIn('id="login-anderer"', seite.text)
        self.assertNotIn(f'value="{self.innen.id}" selected', seite.text)
        r = c.post("/login", data={"benutzer_id": str(self.innen.id), "pin": PIN})
        self.assertEqual(r.status_code, 303, r.text)
        gesetzt = cookies_aus(r)
        self.assertIn(anmeldung.BENUTZER_COOKIE, gesetzt)
        morsel = gesetzt[anmeldung.BENUTZER_COOKIE]
        self.assertEqual(morsel.value, str(self.innen.id))
        self.assertEqual(int(morsel["max-age"]), anmeldung.BENUTZER_COOKIE_TAGE * 86400)
        self.assertTrue(morsel["httponly"])
        self.assertEqual(morsel["samesite"].lower(), "lax")
        for zeile in r.headers.get_list("set-cookie"):
            self.assertNotIn(PIN, zeile)
        # Login-Seite mit Cookie: Benutzer vorbelegt, Fokus in der PIN, Link „Anderer Benutzer“
        c.cookies.delete(auth.COOKIE_NAME)
        seite = c.get("/login").text
        self.assertRegex(seite, rf'<option value="{self.innen.id}"[^>]*selected')
        self.assertIn(f'data-vorgewaehlt="{self.innen.id}"', seite)
        self.assertIn('id="login-anderer"', seite)
        self.assertIn('href="/login?anderer=1"', seite)
        self.assertRegex(seite, r'id="login-pin"[^>]*autofocus')
        self.assertNotRegex(seite, r'id="login-benutzer"[^>]*autofocus')
        # Abmelden behält das Cookie
        r = c.post("/login", data={"benutzer_id": str(self.innen.id), "pin": PIN})
        r = c.get("/logout")
        self.assertEqual(r.status_code, 303)
        geloescht = cookies_aus(r)
        self.assertIn(auth.COOKIE_NAME, geloescht)
        self.assertNotIn(anmeldung.BENUTZER_COOKIE, geloescht)
        self.assertEqual(c.cookies.get(anmeldung.BENUTZER_COOKIE), str(self.innen.id))
        # „Anderer Benutzer“ leert das Cookie, Fokus auf der Benutzerwahl
        r = c.get("/login?anderer=1")
        self.assertEqual(r.status_code, 200)
        geloescht = cookies_aus(r)
        self.assertIn(anmeldung.BENUTZER_COOKIE, geloescht)
        self.assertEqual(geloescht[anmeldung.BENUTZER_COOKIE].value, "")
        self.assertIn('data-vorgewaehlt=""', r.text)
        self.assertRegex(r.text, r'id="login-benutzer"[^>]*autofocus')
        self.assertNotIn('id="login-anderer"', r.text)
        self.assertFalse(c.cookies.get(anmeldung.BENUTZER_COOKIE))
        # fremde/ungültige Cookie-Werte werden ignoriert
        c.cookies.set(anmeldung.BENUTZER_COOKIE, "abc")
        self.assertIn('data-vorgewaehlt=""', c.get("/login").text)
        c.cookies.set(anmeldung.BENUTZER_COOKIE, "999999")
        self.assertIn('data-vorgewaehlt=""', c.get("/login").text)

    def test_g2_fehlversuch_behaelt_die_auswahl(self):
        c = TestClient(app, follow_redirects=False)
        r = c.post("/login", data={"benutzer_id": str(self.innen.id), "pin": "000000"})
        self.assertEqual(r.status_code, 200)
        self.assertIn(f'data-vorgewaehlt="{self.innen.id}"', r.text)
        self.assertNotIn(anmeldung.BENUTZER_COOKIE, cookies_aus(r))


if __name__ == "__main__":
    unittest.main()
