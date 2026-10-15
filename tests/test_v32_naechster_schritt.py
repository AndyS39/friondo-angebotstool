# v32 (PLAN_V19 Phase 163): Dialog „Nächster Schritt“, Bestellung angekündigt,
# Verfolgungs-Chip, Ablehnungsgründe. Abgelehnt „Zu teuer“ → beide versendeten Angebote
# abgelehnt, Grund gespeichert, Statistik zählt; Sonstiges ohne Freitext → 400;
# Bestellung → Status, Ampel heiß, heisse_vorgaenge, ID-Kachel, Innendienst-Glocke ohne
# Mail; Nochmal 3wt am Fr 09.10. → Mi 14.10. (der Plan nennt Fr 10.10. = Samstag);
# Nochmal Datum 20.10.2026 ohne Uhrzeit; AD fremder Vorgang 403; 90-Tage-Lauf respektiert
# die Wiedervorlage; Migration zweimal; Chip-Makro rendert fünf Stufen; Rückgängig;
# Parametrierung (Freitext-Pflicht, Reihenfolge, nachfass_werktage).
# Läuft gegen die DB-Kopie (DB_PFAD_OVERRIDE); Testdaten mit Präfix V32N, am Ende entfernt.
import unittest
from datetime import date, datetime, timedelta

from fastapi.testclient import TestClient

from app import ablauf_pruefung, auth, verfolgung, werktage
from app.db import SessionLocal
from app.main import app, _start_kontext
from app.models import (AblehnungsGrund, Angebot, AngebotsNotiz, Benachrichtigung, Benutzer,
                        Erfassung, Kunde, LeadAktivitaet, LeadParameter, MailAusgang, Vorgang,
                        VorgangsNotiz, einstellung_holen, einstellung_setzen)
from app.templating import templates

PRAEFIX = "V32N"
JSON = {"Accept": "application/json"}


def _client(benutzer_id: int) -> TestClient:
    c = TestClient(app, follow_redirects=False)
    c.cookies.set(auth.COOKIE_NAME, auth.cookie_wert(benutzer_id))
    return c


def _aufraeumen(s) -> None:
    for v in s.query(Vorgang).join(Kunde, Kunde.id == Vorgang.kunde_id).filter(
            Kunde.nachname.like(f"{PRAEFIX}%")).all():
        for a in s.query(Angebot).filter(Angebot.vorgang_id == v.id):
            s.query(AngebotsNotiz).filter(AngebotsNotiz.angebot_id == a.id).delete(synchronize_session=False)
            s.delete(a)
        s.query(Erfassung).filter(Erfassung.vorgang_id == v.id).delete(synchronize_session=False)
        s.query(VorgangsNotiz).filter(VorgangsNotiz.vorgang_id == v.id).delete(synchronize_session=False)
        s.query(LeadAktivitaet).filter(LeadAktivitaet.vorgang_id == v.id).delete(synchronize_session=False)
        s.delete(v)
    s.query(Kunde).filter(Kunde.nachname.like(f"{PRAEFIX}%")).delete(synchronize_session=False)
    s.query(Benachrichtigung).filter(Benachrichtigung.text.like(f"%{PRAEFIX}%")).delete(synchronize_session=False)
    s.query(MailAusgang).filter(MailAusgang.text.like(f"%{PRAEFIX}%")).delete(synchronize_session=False)
    s.query(AblehnungsGrund).filter(AblehnungsGrund.name.like(f"{PRAEFIX}%")).delete(synchronize_session=False)
    s.query(Benutzer).filter(Benutzer.name.like(f"{PRAEFIX} %")).delete(synchronize_session=False)
    s.commit()


def _grund_id(s, name: str) -> int:
    g = s.query(AblehnungsGrund).filter(AblehnungsGrund.name == name).first()
    assert g is not None, f"Grund {name} fehlt – Migration nicht gelaufen?"
    return g.id


class Basis(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        s = SessionLocal()
        try:
            _aufraeumen(s)
            # Migration ist auf der Kopie gelaufen; sicherheitshalber idempotent nachziehen
            verfolgung.migration_v32_verfolgung(s)
            s.commit()

            def benutzer(name, rolle):
                b = Benutzer(name=f"{PRAEFIX} {name}", rolle=rolle, aktiv=True,
                             email=f"{name.lower().replace(' ', '')}@v32n.local",
                             pin_hash=auth.pin_hash("4321"), benachrichtigung_mail="sofort")
                s.add(b)
                s.flush()
                return b.id

            cls.ad_id = benutzer("AD Eins", "aussendienst")
            cls.ad2_id = benutzer("AD Zwei", "aussendienst")
            cls.id_id = benutzer("Innendienst", "innendienst")
            kunde = Kunde(anrede="Herr", vorname="Karl", nachname=f"{PRAEFIX} Kunde",
                          strasse="Testweg 3", plz="47798", ort="Krefeld", telefon="0203 4711",
                          interesse="WP")
            s.add(kunde)
            s.flush()
            cls.kunde_id = kunde.id
            cls.zaehler = 0
            s.commit()
        finally:
            s.close()
        cls.admin = _client(1)
        cls.ad = _client(cls.ad_id)
        cls.ad2 = _client(cls.ad2_id)
        cls.innen = _client(cls.id_id)

    @classmethod
    def tearDownClass(cls):
        s = SessionLocal()
        try:
            _aufraeumen(s)
        finally:
            s.close()

    @classmethod
    def _vorgang(cls, s, lead_phase="angebot", ad_id=None, angebote=("Versendet", "Versendet"),
                 status=""):
        """Vorgang mit Angeboten (Versendet, 100 Tage alt) für den Testkunden."""
        v = Vorgang(kunde_id=cls.kunde_id, lead_phase=lead_phase,
                    ad_id=ad_id if ad_id is not None else cls.ad_id, verfolgung_status=status)
        s.add(v)
        s.flush()
        for st in angebote:
            cls.zaehler += 1
            a = Angebot(nummer=f"{PRAEFIX}-{v.id}-{cls.zaehler}", kunde_id=cls.kunde_id,
                        vorgang_id=v.id, status=st, vertriebler_id=v.ad_id,
                        versendet_am=(datetime.now() - timedelta(days=100)
                                      if st.startswith("Versendet") else None))
            s.add(a)
        s.flush()
        return v


class Migration(Basis):
    def test_gruende_und_status_zweimal(self):
        s = SessionLocal()
        try:
            # Erstlauf simulieren: Marker weg, ein fremder aktiver Grund, ein Vorgang ohne Stufe
            einstellung_setzen(s, verfolgung.MIGRATION_MARKER, "")
            alt = AblehnungsGrund(name=f"{PRAEFIX} Altgrund", aktiv=True, sort=99)
            s.add(alt)
            v = self._vorgang(s, angebote=("Angenommen", "Versendet"))
            s.commit()
            meldungen = verfolgung.migration_v32_verfolgung(s)
            s.commit()
            self.assertTrue(any("Ablehnungsgründe (v32)" in m for m in meldungen), meldungen)
            self.assertTrue(any("Verfolgungsstatus (v32)" in m for m in meldungen), meldungen)
            self.assertEqual(verfolgung.migration_v32_verfolgung(s), [])   # zweiter Lauf
            s.expire_all()
            gruende = {g.name: g for g in s.query(AblehnungsGrund)}
            for nr, name in enumerate(verfolgung.GRUENDE_V32, start=1):
                self.assertIn(name, gruende)
                self.assertTrue(gruende[name].aktiv, name)
                self.assertEqual(gruende[name].sort, nr, name)
            self.assertTrue(gruende["Sonstiges"].freitext_pflicht)
            self.assertFalse(gruende["Zu teuer"].freitext_pflicht)
            self.assertFalse(gruende[f"{PRAEFIX} Altgrund"].aktiv)
            self.assertFalse(gruende["Preis zu hoch"].aktiv)
            if "90 Tage Ablauf" in gruende:
                self.assertTrue(gruende["90 Tage Ablauf"].aktiv)
            aktive = [g.name for g in verfolgung.aktive_gruende(s)]
            self.assertEqual(aktive[:5], list(verfolgung.GRUENDE_V32))
            self.assertEqual(s.get(Vorgang, v.id).verfolgung_status, "angenommen")
            self.assertEqual(einstellung_holen(s, verfolgung.MIGRATION_MARKER, ""), "erledigt")
            # Excel-Pflegeort trägt dieselben fünf Texte (Groß-/Kleinschreibung der Excel)
            from app import leadmanagement_logik
            excel = [g.grund for g in leadmanagement_logik.hole_logik().gruende_der_phase("verloren")]
            self.assertEqual(excel, list(verfolgung.GRUENDE_V32))
        finally:
            s.close()

    def test_status_ableiten(self):
        s = SessionLocal()
        try:
            v1 = self._vorgang(s, angebote=("Entwurf",))
            v2 = self._vorgang(s, angebote=("Abgelehnt", "Entwurf"))
            v3 = self._vorgang(s, angebote=("Versendet", "Abgelehnt"), status="nachgefasst")
            v4 = self._vorgang(s, angebote=("Versendet",), status="bestellung_angekuendigt")
            s.commit()
            self.assertEqual(verfolgung.ableiten(s, v1), "")
            self.assertEqual(verfolgung.ableiten(s, v2), "abgelehnt")
            self.assertEqual(verfolgung.ableiten(s, v3), "nachgefasst")
            self.assertEqual(verfolgung.ableiten(s, v4), "bestellung_angekuendigt")
            # Annahme-/Signaturweg: nach_angebotsstatus setzt angenommen
            a = s.query(Angebot).filter(Angebot.vorgang_id == v4.id).first()
            a.status = "Angenommen"
            self.assertEqual(verfolgung.nach_angebotsstatus(s, a), "angenommen")
            self.assertEqual(v4.verfolgung_status, "angenommen")
            s.commit()
        finally:
            s.close()


class Abgelehnt(Basis):
    def test_zu_teuer_lehnt_beide_angebote_ab(self):
        s = SessionLocal()
        try:
            v = self._vorgang(s, status="versendet")
            v.wiedervorlage_am = datetime.now() + timedelta(days=3)
            v.wiedervorlage_benutzer_id = self.ad_id
            v.verfolgung_ampel = "warm"
            s.commit()
            vid, grund_id = v.id, _grund_id(s, "Zu teuer")
        finally:
            s.close()
        r = self.ad.post(f"/vorgaenge/{vid}/naechster-schritt", headers=JSON,
                         data={"schritt": "abgelehnt", "grund_id": str(grund_id),
                               "notiz": "Kunde fand den Preis zu hoch", "zurueck": f"/vorgaenge/{vid}"})
        self.assertEqual(r.status_code, 200, r.text)
        antwort = r.json()
        self.assertTrue(antwort["ok"])
        self.assertEqual(antwort["status"], "abgelehnt")
        self.assertEqual(antwort["wiedervorlage_am"], "")
        self.assertIn("token", antwort["rueckgaengig"])
        s = SessionLocal()
        try:
            v = s.get(Vorgang, vid)
            angebote = s.query(Angebot).filter(Angebot.vorgang_id == vid).all()
            self.assertEqual(len(angebote), 2)
            for a in angebote:
                self.assertEqual(a.status, "Abgelehnt", a.nummer)
                self.assertEqual(a.ablehnungsgrund, "Zu teuer")
                self.assertIsNotNone(a.abgelehnt_am)
            self.assertEqual(v.verfolgung_status, "abgelehnt")
            self.assertEqual(v.verfolgung_ampel, "kalt")
            self.assertIsNone(v.wiedervorlage_am)
            self.assertIsNone(v.wiedervorlage_benutzer_id)
            self.assertEqual(v.lead_phase, "verloren")   # Ablehnung über EINEN Weg (lead_verloren)
            notizen = (s.query(VorgangsNotiz).filter(VorgangsNotiz.vorgang_id == vid)
                       .order_by(VorgangsNotiz.id).all())
            texte = [n.text for n in notizen]
            self.assertEqual(texte[0], "Kunde fand den Preis zu hoch")      # Notiz vor der Aktivität
            self.assertTrue(texte[1].startswith("Kunde hat abgelehnt: Zu teuer"), texte)
            self.assertEqual(notizen[0].benutzer_id, self.ad_id)
            self.assertEqual(notizen[1].benutzer_name, "System")
            self.assertEqual(notizen[1].herkunft, verfolgung.HERKUNFT)
            # Statistik „Ablehnungsgründe“ zählt den Grund
            from app.routers.statistik import ablehnungsgruende_verteilung
            zeilen = dict(ablehnungsgruende_verteilung(
                s, datetime.now() - timedelta(days=1), datetime.now() + timedelta(days=1)))
            self.assertGreaterEqual(zeilen.get("Zu teuer", 0), 2)
        finally:
            s.close()

    def test_sonstiges_ohne_freitext_400(self):
        s = SessionLocal()
        try:
            v = self._vorgang(s)
            s.commit()
            vid, grund_id = v.id, _grund_id(s, "Sonstiges")
        finally:
            s.close()
        r = self.innen.post(f"/vorgaenge/{vid}/naechster-schritt", headers=JSON,
                            data={"schritt": "abgelehnt", "grund_id": str(grund_id)})
        self.assertEqual(r.status_code, 400)
        self.assertFalse(r.json()["ok"])
        self.assertIn("Freitext", r.json()["meldung"])
        # mit Freitext geht es
        r = self.innen.post(f"/vorgaenge/{vid}/naechster-schritt", headers=JSON,
                            data={"schritt": "abgelehnt", "grund_id": str(grund_id),
                                  "freitext": "zieht um"})
        self.assertEqual(r.status_code, 200, r.text)
        s = SessionLocal()
        try:
            a = s.query(Angebot).filter(Angebot.vorgang_id == vid).first()
            self.assertEqual(a.ablehnungsgrund_text, "zieht um")
            # inaktiver Grund wird abgewiesen
            alt = s.query(AblehnungsGrund).filter(AblehnungsGrund.aktiv.is_(False)).first()
            alt_id = alt.id if alt else 0
        finally:
            s.close()
        if alt_id:
            r = self.innen.post(f"/vorgaenge/{vid}/naechster-schritt", headers=JSON,
                                data={"schritt": "abgelehnt", "grund_id": str(alt_id)})
            self.assertEqual(r.status_code, 400)

    def test_vorgang_ohne_lead_phase_nur_v8_weg(self):
        s = SessionLocal()
        try:
            v = self._vorgang(s, lead_phase=None, angebote=("Versendet", "Entwurf"))
            s.commit()
            vid, grund_id = v.id, _grund_id(s, "Kein Interesse mehr")
        finally:
            s.close()
        r = self.innen.post(f"/vorgaenge/{vid}/naechster-schritt", headers=JSON,
                            data={"schritt": "abgelehnt", "grund_id": str(grund_id)})
        self.assertEqual(r.status_code, 200, r.text)
        s = SessionLocal()
        try:
            v = s.get(Vorgang, vid)
            self.assertIsNone(v.lead_phase)        # kein Lead-Weg
            status = {a.status for a in s.query(Angebot).filter(Angebot.vorgang_id == vid)}
            self.assertEqual(status, {"Abgelehnt", "Entwurf"})   # nur Versendete
            self.assertEqual(v.verfolgung_status, "abgelehnt")
            self.assertEqual(s.query(LeadAktivitaet).filter(LeadAktivitaet.vorgang_id == vid).count(), 0)
        finally:
            s.close()

    def test_ohne_javascript_redirect(self):
        s = SessionLocal()
        try:
            v = self._vorgang(s)
            s.commit()
            vid, grund_id = v.id, _grund_id(s, "Zu teuer")
        finally:
            s.close()
        r = self.innen.post(f"/vorgaenge/{vid}/naechster-schritt",
                            data={"schritt": "abgelehnt", "grund_id": str(grund_id),
                                  "zurueck": "/leads?x=1"})
        self.assertEqual(r.status_code, 303)
        self.assertTrue(r.headers["location"].startswith("/leads?x=1&meldung="), r.headers["location"])
        # fremdes Ziel wird verworfen
        r = self.innen.post(f"/vorgaenge/{vid}/naechster-schritt",
                            data={"schritt": "nochmal", "wann": "3wt", "zurueck": "//boese.example"})
        self.assertEqual(r.status_code, 303)
        self.assertTrue(r.headers["location"].startswith(f"/vorgaenge/{vid}?meldung="))


class Bestellung(Basis):
    def test_bestellung_kommt(self):
        s = SessionLocal()
        try:
            v = self._vorgang(s, status="versendet")
            s.commit()
            vid = v.id
            mails_vorher = s.query(MailAusgang).count()
        finally:
            s.close()
        r = self.ad.post(f"/vorgaenge/{vid}/naechster-schritt", headers=JSON,
                         data={"schritt": "bestellung", "notiz": "Unterschrift kommt Montag"})
        self.assertEqual(r.status_code, 200, r.text)
        antwort = r.json()
        self.assertEqual(antwort["status"], "bestellung_angekuendigt")
        self.assertEqual(antwort["status_text"], "Bestellung angekündigt")
        self.assertEqual(antwort["ampel"], "heiss")
        erwartet = werktage.plus_werktage(date.today(), verfolgung.BESTELLUNG_WERKTAGE)
        self.assertEqual(antwort["wiedervorlage_am"], erwartet.strftime("%d.%m.%Y"))
        s = SessionLocal()
        try:
            v = s.get(Vorgang, vid)
            self.assertEqual(v.verfolgung_status, "bestellung_angekuendigt")
            self.assertEqual(v.verfolgung_ampel, "heiss")
            self.assertEqual(v.wiedervorlage_am, datetime(erwartet.year, erwartet.month, erwartet.day))
            self.assertEqual(v.wiedervorlage_benutzer_id, self.ad_id)
            self.assertEqual(v.wiedervorlage_art, verfolgung.WIEDERVORLAGE_ART_BESTELLUNG)
            self.assertIn(vid, [x.id for x in verfolgung.heisse_vorgaenge(s, self.ad_id)])
            self.assertNotIn(vid, [x.id for x in verfolgung.heisse_vorgaenge(s, self.ad2_id)])
            self.assertGreaterEqual(verfolgung.bestellung_angekuendigt_anzahl(s), 1)
            texte = [n.text for n in s.query(VorgangsNotiz).filter(VorgangsNotiz.vorgang_id == vid)
                     .order_by(VorgangsNotiz.id)]
            self.assertEqual(texte[0], "Unterschrift kommt Montag")
            self.assertTrue(texte[1].startswith("Bestellung angekündigt"), texte)
            # Glocke an den Innendienst, ohne Mail (keine Warteschlangen-Zeile)
            glocken = (s.query(Benachrichtigung)
                       .filter(Benachrichtigung.benutzer_id == self.id_id,
                               Benachrichtigung.art == verfolgung.GLOCKE_ART).all())
            self.assertTrue(any(g.text.startswith("Bestellung angekündigt: ") and PRAEFIX in g.text
                                and g.link == f"/vorgaenge/{vid}" for g in glocken), [g.text for g in glocken])
            self.assertEqual(s.query(MailAusgang).count(), mails_vorher)
            self.assertFalse(s.query(Benachrichtigung)
                             .filter(Benachrichtigung.benutzer_id == self.ad2_id,
                                     Benachrichtigung.art == verfolgung.GLOCKE_ART).count())
        finally:
            s.close()
        # ID-Kachel zählt den Vorgang, Klick = Angebotsliste mit Filter
        self.assertGreaterEqual(_start_kontext()["bestellungen"], 1)
        start = self.admin.get("/angebotstool").text
        self.assertIn("Bestellung angekündigt", start)
        self.assertIn('href="/angebote?verfolgung=bestellung_angekuendigt"', start)
        self.assertIn("Bestellung angekündigt", self.admin.get("/").text)
        # v33 (PLAN_V20 Phase 173, Protokoll A.5): Kontrollwert „Vorgang in Heiße Kunden“ ersetzt durch
        # „Vorgang in Wiedervorlage mit Badge Hoch, an erster Stelle bei Sortierung Priorität“
        mein_tag = self.ad.get("/leads").text
        wv = mein_tag[mein_tag.index('id="wiedervorlage"'):mein_tag.index('id="kommende-tage"')]
        self.assertIn(f'id="faellig-{vid}"', wv)
        karte = wv[wv.index(f'id="faellig-{vid}"'):]
        self.assertIn('data-prio="hoch"', karte[:300])
        erste = wv[wv.index('<article class="mt-wv-karte"'):]
        self.assertIn('data-prio="hoch"', erste[:300])          # Sortierung Priorität: Hoch zuerst
        self.assertIn("Bestellung angekündigt", karte[:karte.index("</article>")])
        self.assertNotIn("Heiße Kunden", mein_tag)
        liste = self.admin.get("/angebote?verfolgung=bestellung_angekuendigt").text
        self.assertIn("<th", liste)
        # v33 (PLAN_V20 Phase 174): Spaltenköpfe tragen Werkzeuge – der Titel steht im
        # <span class="lm-th-text">, die Spalte ist über data-sort erkennbar
        self.assertIn('data-sort="verfolgung"', liste)
        self.assertIn(">Verfolgung</span>", liste)
        self.assertIn('value="bestellung_angekuendigt" selected', liste)

    def test_rueckgaengig(self):
        s = SessionLocal()
        try:
            v = self._vorgang(s, status="versendet")
            v.wiedervorlage_am = datetime(2030, 1, 7)
            v.wiedervorlage_benutzer_id = self.ad_id
            s.commit()
            vid = v.id
        finally:
            s.close()
        r = self.ad.post(f"/vorgaenge/{vid}/naechster-schritt", headers=JSON,
                         data={"schritt": "bestellung"})
        token = r.json()["rueckgaengig"]["token"]
        r = self.ad.post(f"/vorgaenge/{vid}/naechster-schritt", headers=JSON,
                         data={"schritt": "rueckgaengig", "token": token})
        self.assertEqual(r.status_code, 200, r.text)
        self.assertEqual(r.json()["status"], "versendet")
        s = SessionLocal()
        try:
            v = s.get(Vorgang, vid)
            self.assertEqual(v.verfolgung_status, "versendet")
            self.assertEqual(v.wiedervorlage_am, datetime(2030, 1, 7))
            self.assertEqual(v.verfolgung_ampel, "")
            self.assertFalse(s.query(Benachrichtigung)
                             .filter(Benachrichtigung.link == f"/vorgaenge/{vid}",
                                     Benachrichtigung.art == verfolgung.GLOCKE_ART).count())
            texte = [n.text for n in s.query(VorgangsNotiz).filter(VorgangsNotiz.vorgang_id == vid)]
            self.assertTrue(any(t.startswith("Rückgängig:") for t in texte), texte)
        finally:
            s.close()
        # zweites Mal: Token verbraucht
        r = self.ad.post(f"/vorgaenge/{vid}/naechster-schritt", headers=JSON,
                         data={"schritt": "rueckgaengig", "token": token})
        self.assertEqual(r.status_code, 400)
        # Abgelehnt rückgängig stellt die Angebote wieder her
        s = SessionLocal()
        try:
            grund_id = _grund_id(s, "Zu teuer")
        finally:
            s.close()
        r = self.ad.post(f"/vorgaenge/{vid}/naechster-schritt", headers=JSON,
                         data={"schritt": "abgelehnt", "grund_id": str(grund_id)})
        token = r.json()["rueckgaengig"]["token"]
        r = self.ad.post(f"/vorgaenge/{vid}/naechster-schritt", headers=JSON,
                         data={"schritt": "rueckgaengig", "token": token})
        self.assertEqual(r.status_code, 200, r.text)
        s = SessionLocal()
        try:
            v = s.get(Vorgang, vid)
            self.assertEqual(v.lead_phase, "angebot")
            self.assertEqual({a.status for a in s.query(Angebot).filter(Angebot.vorgang_id == vid)},
                             {"Versendet"})
            self.assertEqual(v.verfolgung_status, "versendet")
        finally:
            s.close()


class Nochmal(Basis):
    def test_3wt_am_freitag_09_10(self):
        # Plan-Kontrollwert „Fr 10.10. → Mi 15.10.“ – der 10.10.2026 ist ein Samstag;
        # Fr 09.10. + 3 Werktage = Mi 14.10., Sa 10.10. + 3 Werktage ebenfalls Mi 14.10.
        s = SessionLocal()
        try:
            v = self._vorgang(s, status="versendet")
            s.commit()
            benutzer = s.get(Benutzer, self.ad_id)
            ok, meldung, daten = verfolgung.naechster_schritt(
                s, v, "nochmal", benutzer, wann="3wt", heute=date(2026, 10, 9))
            s.commit()
            self.assertTrue(ok, meldung)
            self.assertEqual(v.wiedervorlage_am, datetime(2026, 10, 14, 0, 0))
            self.assertEqual(daten["wiedervorlage_am"], "14.10.2026")
            self.assertEqual(v.verfolgung_status, "nachgefasst")
            self.assertEqual(v.wiedervorlage_benutzer_id, self.ad_id)
            self.assertEqual(v.wiedervorlage_art, verfolgung.WIEDERVORLAGE_ART_NOCHMAL)
            self.assertIn("Mi 14.10.", meldung)
            self.assertEqual(verfolgung.naechster_3wt(date(2026, 10, 10)), date(2026, 10, 14))
            self.assertEqual(verfolgung.datum_text(date(2026, 10, 14)), "Mi 14.10.")
            texte = [n.text for n in s.query(VorgangsNotiz).filter(VorgangsNotiz.vorgang_id == v.id)]
            self.assertTrue(any(t.startswith("Nochmal anrufen am 14.10.2026") for t in texte), texte)
            # manuelles Datum ohne Uhrzeit
            ok, meldung, daten = verfolgung.naechster_schritt(
                s, v, "nochmal", benutzer, wann="datum", datum="20.10.2026", heute=date(2026, 10, 13))
            s.commit()
            self.assertTrue(ok, meldung)
            self.assertEqual(v.wiedervorlage_am, datetime(2026, 10, 20, 0, 0))
            # Vergangenheit und fehlendes Datum werden abgewiesen
            ok, meldung, _ = verfolgung.naechster_schritt(
                s, v, "nochmal", benutzer, wann="datum", datum="01.10.2026", heute=date(2026, 10, 13))
            self.assertFalse(ok)
            ok, meldung, _ = verfolgung.naechster_schritt(
                s, v, "nochmal", benutzer, wann="datum", datum="", heute=date(2026, 10, 13))
            self.assertFalse(ok)
            s.rollback()
        finally:
            s.close()

    def test_route_3wt_und_datum(self):
        s = SessionLocal()
        try:
            v = self._vorgang(s, status="versendet")
            s.commit()
            vid = v.id
        finally:
            s.close()
        r = self.ad.post(f"/vorgaenge/{vid}/naechster-schritt", headers=JSON,
                         data={"schritt": "nochmal", "wann": "3wt"})
        self.assertEqual(r.status_code, 200, r.text)
        erwartet = werktage.plus_werktage(date.today(), 3)
        self.assertEqual(r.json()["wiedervorlage_am"], erwartet.strftime("%d.%m.%Y"))
        ziel = date.today() + timedelta(days=12)
        r = self.ad.post(f"/vorgaenge/{vid}/naechster-schritt", headers=JSON,
                         data={"schritt": "nochmal", "wann": "datum", "datum": ziel.isoformat()})
        self.assertEqual(r.status_code, 200, r.text)
        s = SessionLocal()
        try:
            v = s.get(Vorgang, vid)
            self.assertEqual(v.wiedervorlage_am, datetime(ziel.year, ziel.month, ziel.day))
            self.assertEqual(v.wiedervorlage_am.hour, 0)
            self.assertEqual(v.verfolgung_status, "nachgefasst")
            # 90-Tage-Lauf respektiert die gesetzte Wiedervorlage (Bestandslogik v10)
            kandidaten, _tage = ablauf_pruefung.kandidaten(s)
            self.assertFalse(any(a.vorgang_id == vid for a in kandidaten))
        finally:
            s.close()


class Rechte(Basis):
    def test_ad_fremder_vorgang_403(self):
        s = SessionLocal()
        try:
            v = self._vorgang(s, ad_id=self.ad2_id)
            s.commit()
            vid = v.id
        finally:
            s.close()
        r = self.ad.post(f"/vorgaenge/{vid}/naechster-schritt", headers=JSON,
                         data={"schritt": "bestellung"})
        self.assertEqual(r.status_code, 403)
        self.assertFalse(r.json()["ok"])
        r = self.ad.post(f"/vorgaenge/{vid}/naechster-schritt", data={"schritt": "bestellung"})
        self.assertEqual(r.status_code, 303)
        s = SessionLocal()
        try:
            self.assertEqual(s.get(Vorgang, vid).verfolgung_status, "")
        finally:
            s.close()
        # ID darf, unbekannter Schritt → 400, unbekannter Vorgang → 404
        r = self.innen.post(f"/vorgaenge/{vid}/naechster-schritt", headers=JSON,
                            data={"schritt": "tanzen"})
        self.assertEqual(r.status_code, 400)
        r = self.innen.post("/vorgaenge/99999999/naechster-schritt", headers=JSON,
                            data={"schritt": "bestellung"})
        self.assertEqual(r.status_code, 404)


class Oberflaeche(Basis):
    def test_chip_makro_fuenf_stufen(self):
        vorlage = templates.env.from_string(
            '{% from "_komponenten.html" import verfolgung_chip %}'
            '{{ verfolgung_chip(s, klein=klein, vorgang_id=vid) }}')
        for status in verfolgung.STATUS:
            html = vorlage.render(s=status, klein=False, vid=None)
            self.assertIn(f"verfolgung-chip vf-{status}", html)
            self.assertIn(verfolgung.status_text(status), html)
            self.assertIn("abzeichen-punkt", html)
            self.assertNotIn(" klein", html)
        html = vorlage.render(s="abgelehnt", klein=True, vid=42)
        self.assertIn("vf-abgelehnt klein", html)
        self.assertIn('data-verfolgung-chip="42"', html)
        self.assertEqual(vorlage.render(s="", klein=False, vid=None).strip(), "")
        self.assertEqual(vorlage.render(s="unbekannt", klein=False, vid=None).strip(), "")
        self.assertIn("hidden", vorlage.render(s="", klein=False, vid=7))
        # Texte des Makros = STATUS_TEXTE; CSS nur mit Tokens
        css = open("app/static/verfolgung.css", encoding="utf-8").read()
        for status in verfolgung.STATUS:
            self.assertIn(f".vf-{status}", css)
            self.assertIn(f"--status-{verfolgung.STATUS_FARBEN[status]}", css)
        self.assertNotIn("#", css)   # keine festen Hex-Farben (v30-Wächter)

    def test_akte_zeigt_chip_und_dialog(self):
        s = SessionLocal()
        try:
            v = self._vorgang(s, status="versendet")
            s.commit()
            vid = v.id
        finally:
            s.close()
        for client in (self.innen, self.ad):
            html = client.get(f"/vorgaenge/{vid}").text
            self.assertIn(f'data-verfolgung-chip="{vid}"', html)
            self.assertIn("vf-versendet", html)
            self.assertIn('id="naechster-schritt"', html)
            self.assertIn(f'data-url="/vorgaenge/{vid}/naechster-schritt"', html)
            for text in ("Abgelehnt", "Bestellung kommt", "Nochmal anrufen", "In 3 Werktagen",
                         "verfolgung.css", "verfolgung.js", 'data-ns-notiz="%d"' % vid):
                self.assertIn(text, html, text)
            for name in verfolgung.GRUENDE_V32:
                self.assertIn(name, html)
            self.assertNotIn("Preis zu hoch", html)       # deaktivierte Gründe fehlen
        self.assertIn(verfolgung.datum_text(verfolgung.naechster_3wt()), html)
        # fremder AD sieht die Akte nicht
        r = self.ad2.get(f"/vorgaenge/{vid}")
        self.assertEqual(r.status_code, 303)

    def test_meine_angebote_chip_und_freitext_pflicht(self):
        s = SessionLocal()
        try:
            v = self._vorgang(s, status="bestellung_angekuendigt", angebote=("Versendet",))
            s.commit()
            vid = v.id
            aid = s.query(Angebot).filter(Angebot.vorgang_id == vid).first().id
        finally:
            s.close()
        liste = self.ad.get("/meine-angebote").text
        self.assertIn("vf-bestellung_angekuendigt", liste)
        detail = self.ad.get(f"/meine-angebote/{aid}").text
        self.assertIn("vf-bestellung_angekuendigt", detail)
        self.assertIn('data-freitext-pflicht="1"', detail)
        self.assertIn('data-freitext-pflicht="0"', detail)
        self.assertNotIn("Preis zu hoch", detail)
        # AD-Dialog: Sonstiges ohne Ergänzung wird abgewiesen, mit Ergänzung gesetzt
        r = self.ad.post(f"/meine-angebote/{aid}/status",
                         data={"status": "Abgelehnt", "ablehnungsgrund": "Sonstiges"})
        self.assertEqual(r.status_code, 303)
        self.assertIn("Pflicht", r.headers["location"])
        s = SessionLocal()
        try:
            self.assertEqual(s.get(Angebot, aid).status, "Versendet")
        finally:
            s.close()
        r = self.ad.post(f"/meine-angebote/{aid}/status",
                         data={"status": "Abgelehnt", "ablehnungsgrund": "Sonstiges",
                               "ablehnungsgrund_text": "Haus verkauft"})
        self.assertEqual(r.status_code, 303)
        s = SessionLocal()
        try:
            self.assertEqual(s.get(Angebot, aid).status, "Abgelehnt")
            self.assertEqual(s.get(Vorgang, vid).verfolgung_status, "abgelehnt")   # Chip folgt dem Ablehnungsweg
        finally:
            s.close()

    def test_id_dialog_markiert_freitext_pflicht(self):
        s = SessionLocal()
        try:
            v = self._vorgang(s, angebote=("Versendet",))
            s.commit()
            aid = s.query(Angebot).filter(Angebot.vorgang_id == v.id).first().id
        finally:
            s.close()
        html = self.admin.get(f"/angebote/{aid}").text
        self.assertIn('data-freitext-pflicht="1">Sonstiges', html)
        self.assertIn("idFreitextPflicht", html)
        self.assertNotIn("Preis zu hoch", html)

    def test_angebotsliste_spalte_und_filter(self):
        html = self.admin.get("/angebote").text
        # v33 (PLAN_V20 Phase 174): Spaltenkopf mit Werkzeugen (Titel im <span class="lm-th-text">)
        self.assertIn('data-sort="verfolgung"', html)
        self.assertIn(">Verfolgung</span>", html)
        self.assertIn('<optgroup label="Verfolgungsstatus (v32)">', html)
        for status in verfolgung.STATUS:
            self.assertIn(f'value="{status}"', html)

    def test_filter_anwenden(self):
        s = SessionLocal()
        try:
            v1 = self._vorgang(s, status="bestellung_angekuendigt", angebote=("Versendet",))
            v2 = self._vorgang(s, status="versendet", angebote=("Versendet",))
            s.commit()
            q = verfolgung.filter_anwenden(s.query(Vorgang), "bestellung_angekuendigt").all()
            self.assertIn(v1.id, [v.id for v in q])
            self.assertNotIn(v2.id, [v.id for v in q])
            q = verfolgung.filter_anwenden(s.query(Angebot), "versendet").all()
            self.assertIn(v2.id, [a.vorgang_id for a in q])
            self.assertNotIn(v1.id, [a.vorgang_id for a in q])
            angebote = s.query(Angebot).filter(Angebot.vorgang_id.in_((v1.id, v2.id))).all()
            vmap = {v1.id: v1, v2.id: v2}
            liste = verfolgung.filter_anwenden(angebote, "bestellung_angekuendigt", vmap)
            self.assertEqual([a.vorgang_id for a in liste], [v1.id])
            self.assertEqual(len(verfolgung.filter_anwenden(angebote, "quatsch", vmap)), 2)
            abfrage = s.query(Angebot)
            self.assertIs(verfolgung.filter_anwenden(abfrage, ""), abfrage)   # unbekannt → unverändert
        finally:
            s.close()


class Parametrierung(Basis):
    def test_gruende_pflege_und_nachfass_werktage(self):
        html = self.admin.get("/parametrierung/angebotstool").text
        for text in ('name="nachfass_werktage"', 'name="nachfass_werktage_mfh"',
                     'name="nachfass_formular" value="1"', "Freitext Pflicht", 'value="hoch"',
                     'value="runter"', 'value="freitext"', 'id="nachfassen"'):
            self.assertIn(text, html, text)
        s = SessionLocal()
        try:
            vorher = {p.name: p.wert for p in s.query(LeadParameter)
                      .filter(LeadParameter.name.in_(("nachfass_werktage", "nachfass_werktage_mfh")))}
            neu = AblehnungsGrund(name=f"{PRAEFIX} Testgrund", aktiv=True, sort=50)
            s.add(neu)
            s.commit()
            neu_id = neu.id
        finally:
            s.close()
        kopf = {"referer": "http://testserver/parametrierung/angebotstool"}
        try:
            r = self.admin.post("/parametrierung/einstellungen", headers=kopf,
                                data={"nachfass_formular": "1", "nachfass_werktage": "4",
                                      "nachfass_werktage_mfh": "6"})
            self.assertEqual(r.status_code, 303)
            s = SessionLocal()
            try:
                from app import leadmanagement
                self.assertEqual(leadmanagement.parameter_holen(s, "nachfass_werktage", ""), "4")
                self.assertEqual(leadmanagement.parameter_holen(s, "nachfass_werktage_mfh", ""), "6")
            finally:
                s.close()
            # Pflicht-Freitext umschalten, Reihenfolge nach oben
            r = self.admin.post("/parametrierung/ablehnungsgruende", headers=kopf,
                                data={"aktion": "freitext", "id": str(neu_id)})
            self.assertEqual(r.headers["location"], "/parametrierung/angebotstool#ablehnung")
            s = SessionLocal()
            try:
                self.assertTrue(s.get(AblehnungsGrund, neu_id).freitext_pflicht)
                reihenfolge = [g.id for g in s.query(AblehnungsGrund)
                               .order_by(AblehnungsGrund.sort, AblehnungsGrund.id)]
                position = reihenfolge.index(neu_id)
            finally:
                s.close()
            self.admin.post("/parametrierung/ablehnungsgruende", headers=kopf,
                            data={"aktion": "hoch", "id": str(neu_id)})
            s = SessionLocal()
            try:
                reihenfolge = [g.id for g in s.query(AblehnungsGrund)
                               .order_by(AblehnungsGrund.sort, AblehnungsGrund.id)]
                self.assertEqual(reihenfolge.index(neu_id), position - 1)
                sorts = [g.sort for g in s.query(AblehnungsGrund).order_by(AblehnungsGrund.sort)]
                self.assertEqual(sorts, list(range(1, len(sorts) + 1)))   # lückenlos 1 … n
            finally:
                s.close()
            self.admin.post("/parametrierung/ablehnungsgruende", headers=kopf,
                            data={"aktion": "runter", "id": str(neu_id)})
            # Ungültige Werte werden ignoriert
            self.admin.post("/parametrierung/einstellungen", headers=kopf,
                            data={"nachfass_formular": "1", "nachfass_werktage": "99",
                                  "nachfass_werktage_mfh": "x"})
            s = SessionLocal()
            try:
                from app import leadmanagement
                self.assertEqual(leadmanagement.parameter_holen(s, "nachfass_werktage", ""), "4")
            finally:
                s.close()
        finally:
            s = SessionLocal()
            try:
                from app import leadmanagement
                for name, wert in vorher.items():
                    leadmanagement.parameter_setzen(s, name, wert)
                # die fünf Gründe wieder auf 1–5 (Test hat nur den Testgrund verschoben)
                s.commit()
            finally:
                s.close()
