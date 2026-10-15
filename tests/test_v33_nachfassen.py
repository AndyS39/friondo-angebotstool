# v33 (PLAN_V20 Phase 176, Agent N): Angebotsverfolgung / Nachfassen.
# Inaktivitäts-Kennzeichen ab Tag 14 (EFH) bzw. 20 (MFH) mit gemocktem „heute“, Parameter
# geändert → Grenze folgt, Wiedervorlage in der Zukunft schützt nicht, alle Kontaktarten;
# Zähler nach zwei „Nochmal anrufen“ = 2, Chip „Nachgefasst (2)“ (Makro + Akte), Rückgängig
# senkt; Einwand gespeichert und beim nächsten Anruf oben, unbekannter Einwand 400,
# Parametrierungs-Liste (anlegen/umbenennen/umschalten/Reihenfolge, inaktiv_tage), Statistik;
# Nachfass-Mail aus dem AD-Postfach (Graph gemockt: mail_senden_als mit der AD-Adresse), im
# Mail-Verlauf und Chat, PDF-Anhang, Vorschau, im Modus delegiert gesperrt (Knopf disabled +
# Route 409), AD fremder Vorgang 403; Vorlagen-Editor Nachfassen 1/2; eigene Signatur des AD;
# Migration zweimal. Läuft gegen die DB-Kopie (DB_PFAD_OVERRIDE); Testdaten mit Präfix V33N,
# am Ende entfernt. Kein Netz: graph_versand.modus und mail_senden_als sind gemockt.
import tempfile
import unittest
from datetime import date, datetime, timedelta
from pathlib import Path
from unittest import mock

from fastapi.testclient import TestClient

from app import auth, graph_versand, leadmanagement, mail_vorlagen, nachfassen, signaturen, verfolgung
from app.db import SessionLocal
from app.main import app
from app.models import (Angebot, AngebotsMail, AngebotsNotiz, Benachrichtigung, Benutzer, Einwand,
                        Erfassung, KommunikationLog, Kunde, LeadAktivitaet, LeadParameter,
                        Vorgang, VorgangEinwand, VorgangsNotiz, einstellung_holen,
                        einstellung_setzen)
from app.templating import templates

PRAEFIX = "V33N"
JSON = {"Accept": "application/json"}
# Orchestrator 15.10.2026: HEUTE = heutiges Datum - die Helfer setzen versendet_am ueber datetime.now(),
# ein festes Datum (14.10.) war ab Mitternacht um einen Tag versetzt (3 Tests rot)
HEUTE = date.today()


def _client(benutzer_id: int) -> TestClient:
    c = TestClient(app, follow_redirects=False)
    c.cookies.set(auth.COOKIE_NAME, auth.cookie_wert(benutzer_id))
    return c


def _aufraeumen(s) -> None:
    for v in s.query(Vorgang).join(Kunde, Kunde.id == Vorgang.kunde_id).filter(
            Kunde.nachname.like(f"{PRAEFIX}%")).all():
        for a in s.query(Angebot).filter(Angebot.vorgang_id == v.id):
            s.query(AngebotsNotiz).filter(AngebotsNotiz.angebot_id == a.id).delete(synchronize_session=False)
            s.query(AngebotsMail).filter(AngebotsMail.angebot_id == a.id).delete(synchronize_session=False)
            s.delete(a)
        for tabelle in (Erfassung, VorgangsNotiz, LeadAktivitaet, VorgangEinwand, KommunikationLog):
            s.query(tabelle).filter(tabelle.vorgang_id == v.id).delete(synchronize_session=False)
        s.delete(v)
    s.query(Kunde).filter(Kunde.nachname.like(f"{PRAEFIX}%")).delete(synchronize_session=False)
    s.query(Benachrichtigung).filter(Benachrichtigung.text.like(f"%{PRAEFIX}%")).delete(synchronize_session=False)
    s.query(Einwand).filter(Einwand.name.like(f"{PRAEFIX}%")).delete(synchronize_session=False)
    for b in s.query(Benutzer).filter(Benutzer.name.like(f"{PRAEFIX} %")).all():
        signaturen.entfernen(b.id)
        s.delete(b)
    for name, wert in (("inaktiv_tage", "14"), ("inaktiv_tage_mfh", "20")):
        leadmanagement.parameter_setzen(s, name, wert)
    for nr in mail_vorlagen.NACHFASS_NUMMERN:
        mail_vorlagen.nachfass_vorlage_speichern(s, nr, "", "")
    s.commit()


class Basis(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        s = SessionLocal()
        try:
            _aufraeumen(s)
            verfolgung.migration_v32_verfolgung(s)
            verfolgung.migration_v33_nachfassen(s)
            s.commit()

            def benutzer(name, rolle, email):
                b = Benutzer(name=f"{PRAEFIX} {name}", rolle=rolle, aktiv=True, email=email,
                             pin_hash=auth.pin_hash("4321"))
                s.add(b)
                s.flush()
                return b.id

            cls.admin_id = benutzer("Admin", "admin", "admin@v33n.local")
            cls.ad_id = benutzer("AD Eins", "aussendienst", "ad.eins@v33n.local")
            cls.ad2_id = benutzer("AD Zwei", "aussendienst", "ad.zwei@v33n.local")
            cls.ad_ohne_mail_id = benutzer("AD Drei", "aussendienst", "")
            cls.id_id = benutzer("Innendienst", "innendienst", "innen@v33n.local")
            cls.montage_id = benutzer("Monteur", "montage", "")
            kunde = Kunde(anrede="Frau", vorname="Karla", nachname=f"{PRAEFIX} Kundin",
                          strasse="Testweg 3", plz="47798", ort="Krefeld", telefon="0203 4711",
                          email="karla@kunde.v33n.local", interesse="WP")
            mfh = Kunde(anrede="Herr", vorname="Max", nachname=f"{PRAEFIX} Mehrfamilie",
                        strasse="Hofweg 1", plz="47051", ort="Duisburg", telefon="0203 4712",
                        email="max@kunde.v33n.local", interesse="WP", objektart="MFH")
            ohne = Kunde(anrede="Herr", vorname="Olaf", nachname=f"{PRAEFIX} OhneMail",
                         strasse="Leerweg 1", plz="47051", ort="Duisburg", telefon="", interesse="WP")
            s.add_all([kunde, mfh, ohne])
            s.flush()
            cls.kunde_id, cls.mfh_id, cls.ohne_mail_id = kunde.id, mfh.id, ohne.id
            cls.zaehler = 0
            s.commit()
        finally:
            s.close()
        cls.admin = _client(cls.admin_id)
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
    def _vorgang(cls, s, kunde_id=None, status="versendet", ad_id=None, lead_phase="angebot",
                 versendet_vor_tagen=30, extern=False):
        """Vorgang mit EINEM versendeten Angebot (versendet vor n Tagen) und dem AD."""
        v = Vorgang(kunde_id=kunde_id or cls.kunde_id, lead_phase=lead_phase,
                    ad_id=ad_id if ad_id is not None else cls.ad_id, verfolgung_status=status,
                    angelegt_am=datetime.now() - timedelta(days=versendet_vor_tagen + 5))
        s.add(v)
        s.flush()
        cls.zaehler += 1
        a = Angebot(nummer=f"{PRAEFIX}-{v.id}-{cls.zaehler}", kunde_id=v.kunde_id, vorgang_id=v.id,
                    status="Versendet", vertriebler_id=v.ad_id, extern=extern,
                    taifun_nummer=f"T-{cls.zaehler}" if extern else "",
                    versendet_am=datetime.now() - timedelta(days=versendet_vor_tagen))
        s.add(a)
        s.flush()
        return v


# --- 1) Inaktivitäts-Kennzeichen --------------------------------------------------------
class Inaktiv(Basis):
    def test_kennzeichen_ab_14_tagen_efh(self):
        s = SessionLocal()
        try:
            v = self._vorgang(s, versendet_vor_tagen=40)
            # letzter Kontakt = Notiz vor 13 Tagen → kein Kennzeichen; vor 15 Tagen → 15
            notiz = VorgangsNotiz(vorgang_id=v.id, benutzer_name="AD", text="angerufen",
                                  zeit=datetime.combine(HEUTE, datetime.min.time()) - timedelta(days=13))
            s.add(notiz)
            s.flush()
            self.assertIsNone(nachfassen.inaktiv_tage_fuer(s, v, HEUTE))
            notiz.zeit = datetime.combine(HEUTE, datetime.min.time()) - timedelta(days=15)
            s.flush()
            self.assertEqual(nachfassen.inaktiv_tage_fuer(s, v, HEUTE), 15)
            self.assertEqual(nachfassen.inaktiv_text(15), "ohne Kontakt seit 15 Tagen")
            # genau 14 Tage = Schwelle erreicht
            notiz.zeit = datetime.combine(HEUTE, datetime.min.time()) - timedelta(days=14)
            s.flush()
            self.assertEqual(nachfassen.inaktiv_tage_fuer(s, v, HEUTE), 14)
            # nur Versendet/Nachgefasst – andere Stufen nie
            for status in ("angenommen", "abgelehnt", "bestellung_angekuendigt", ""):
                v.verfolgung_status = status
                s.flush()
                self.assertIsNone(nachfassen.inaktiv_tage_fuer(s, v, HEUTE), status)
            v.verfolgung_status = "nachgefasst"
            s.flush()
            self.assertEqual(nachfassen.inaktiv_tage_fuer(s, v, HEUTE), 14)
            s.rollback()
        finally:
            s.close()

    def test_mfh_erst_ab_20_und_parameter_folgt(self):
        s = SessionLocal()
        try:
            v = self._vorgang(s, kunde_id=self.mfh_id, versendet_vor_tagen=15)
            self.assertIsNone(nachfassen.inaktiv_tage_fuer(s, v, HEUTE))      # MFH: 15 < 20
            a = s.query(Angebot).filter(Angebot.vorgang_id == v.id).first()
            a.versendet_am = datetime.combine(HEUTE, datetime.min.time()) - timedelta(days=20)
            s.flush()
            self.assertEqual(nachfassen.inaktiv_tage_fuer(s, v, HEUTE), 20)
            # Parameter geändert → Grenze folgt (MFH 25, EFH 10)
            leadmanagement.parameter_setzen(s, "inaktiv_tage_mfh", "25")
            leadmanagement.parameter_setzen(s, "inaktiv_tage", "10")
            self.assertIsNone(nachfassen.inaktiv_tage_fuer(s, v, HEUTE))
            efh = self._vorgang(s, versendet_vor_tagen=12)
            self.assertEqual(nachfassen.inaktiv_tage_fuer(s, efh, HEUTE), 12)
            self.assertEqual(nachfassen.inaktiv_parameter(s, True), 25)
            self.assertEqual(nachfassen.inaktiv_parameter(s, False), 10)
            s.rollback()
        finally:
            s.close()

    def test_wiedervorlage_in_der_zukunft_schuetzt_nicht(self):
        s = SessionLocal()
        try:
            v = self._vorgang(s, versendet_vor_tagen=15)
            v.wiedervorlage_am = datetime.combine(HEUTE, datetime.min.time()) + timedelta(days=60)
            v.wiedervorlage_benutzer_id = self.ad_id
            s.flush()
            self.assertEqual(nachfassen.inaktiv_tage_fuer(s, v, HEUTE), 15)
            s.rollback()
        finally:
            s.close()

    def test_alle_kontaktarten_setzen_zurueck(self):
        """Anruf-Ergebnis, Lead-Mail, Mail-Verlauf (ein- und ausgehend) zählen als Kontakt."""
        s = SessionLocal()
        try:
            jetzt = datetime.combine(HEUTE, datetime.min.time())
            v = self._vorgang(s, versendet_vor_tagen=30)
            self.assertEqual(nachfassen.inaktiv_tage_fuer(s, v, HEUTE), 30)
            s.add(LeadAktivitaet(vorgang_id=v.id, typ="anruf", ergebnis="nicht_erreicht",
                                 text="x", zeitpunkt=jetzt - timedelta(days=9)))
            s.flush()
            self.assertIsNone(nachfassen.inaktiv_tage_fuer(s, v, HEUTE))
            v2 = self._vorgang(s, versendet_vor_tagen=30)
            s.add(KommunikationLog(vorgang_id=v2.id, an="k@x", betreff="b", status="gesendet",
                                   gesendet_am=jetzt - timedelta(days=3)))
            s.flush()
            self.assertIsNone(nachfassen.inaktiv_tage_fuer(s, v2, HEUTE))
            v3 = self._vorgang(s, versendet_vor_tagen=30)
            a3 = s.query(Angebot).filter(Angebot.vorgang_id == v3.id).first()
            s.add(AngebotsMail(angebot_id=a3.id, graph_id=f"{PRAEFIX}-mail-{v3.id}", von_email="k@x",
                               empfangen_am=jetzt - timedelta(days=2), betreff="Re", eingehend=True))
            s.flush()
            self.assertIsNone(nachfassen.inaktiv_tage_fuer(s, v3, HEUTE))
            # Mengenabfrage: nur Vorgänge mit Kennzeichen
            v4 = self._vorgang(s, versendet_vor_tagen=21)
            werte = nachfassen.inaktiv_kennzeichen(s, [v, v2, v3, v4], HEUTE)
            self.assertEqual(werte, {v4.id: 21})
            # Notizen-Chat als Kontakt (Systemnotiz zählt mit)
            s.add(VorgangsNotiz(vorgang_id=v4.id, benutzer_name="System", text="Wiedervorlage",
                                zeit=jetzt - timedelta(days=1)))
            s.flush()
            self.assertEqual(nachfassen.inaktiv_kennzeichen(s, [v4], HEUTE), {})
            s.rollback()
        finally:
            s.close()


# --- 2) Zähler der Telefonversuche + 3) Einwand-Chips -----------------------------------
class ZaehlerUndEinwand(Basis):
    def _einwand_id(self, s, name="Förderung unklar") -> int:
        e = s.query(Einwand).filter(Einwand.name == name).first()
        self.assertIsNotNone(e, "Start-Einwand fehlt – Migration nicht gelaufen?")
        return e.id

    def test_zwei_nochmal_anrufen_zaehlen_2_und_chip(self):
        s = SessionLocal()
        try:
            v = self._vorgang(s)
            s.commit()
            vid = v.id
        finally:
            s.close()
        for erwartet in (1, 2):
            r = self.ad.post(f"/vorgaenge/{vid}/naechster-schritt",
                             data={"schritt": "nochmal", "wann": "3wt"}, headers=JSON)
            self.assertEqual(r.status_code, 200, r.text)
            antwort = r.json()
            self.assertTrue(antwort["ok"])
            self.assertEqual(antwort["versuche"], erwartet)
            self.assertEqual(antwort["status_text"], f"Nachgefasst ({erwartet})")
            self.assertEqual(antwort["einwand"], "")
        s = SessionLocal()
        try:
            v = s.get(Vorgang, vid)
            self.assertEqual(v.nachfass_versuche, 2)
            self.assertEqual(v.verfolgung_status, "nachgefasst")
            self.assertEqual(verfolgung.status_text(v.verfolgung_status, v.nachfass_versuche), "Nachgefasst (2)")
            self.assertEqual(verfolgung.status_text("nachgefasst"), "Nachgefasst")      # rückwärtskompatibel
            self.assertEqual(verfolgung.status_text("versendet", 3), "Versendet")         # Zähler nur bei nachgefasst
            notizen = [n.text for n in s.query(VorgangsNotiz).filter(VorgangsNotiz.vorgang_id == vid)]
            self.assertTrue(any("Nachfass-Anruf 2" in t for t in notizen), notizen)
        finally:
            s.close()
        # Makro: „Nachgefasst (2)“ + data-versuche; ohne Zähler unverändert
        vorlage = templates.env.from_string(
            '{% from "_komponenten.html" import verfolgung_chip %}'
            '{{ verfolgung_chip(s, klein=True, vorgang_id=vid, versuche=n) }}')
        html = vorlage.render(s="nachgefasst", vid=vid, n=2)
        self.assertIn("Nachgefasst (2)", html)
        self.assertIn('data-versuche="2"', html)
        self.assertIn("vf-nachgefasst klein", html)
        self.assertNotIn("(", vorlage.render(s="nachgefasst", vid=vid, n=0).split("</i>")[1])
        self.assertNotIn("(3)", vorlage.render(s="versendet", vid=vid, n=3))
        # Akte (ID und AD) zeigt Chip mit Zähler und „2 Nachfass-Anrufe“
        for client in (self.innen, self.ad):
            seite = client.get(f"/vorgaenge/{vid}").text
            self.assertIn("Nachgefasst (2)", seite)
            self.assertIn("2 Nachfass-Anrufe", seite)
            self.assertIn('name="einwand_id"', seite)
            for name in verfolgung.EINWAENDE_START:
                self.assertIn(name, seite)
        # Meine Angebote (Liste + Detail) tragen den Zähler
        self.assertIn("Nachgefasst (2)", self.ad.get("/meine-angebote").text)

    def test_einwand_gespeichert_beim_naechsten_anruf_oben_und_rueckgaengig(self):
        s = SessionLocal()
        try:
            v = self._vorgang(s)
            s.commit()
            vid = v.id
            eid = self._einwand_id(s)
        finally:
            s.close()
        r = self.ad.post(f"/vorgaenge/{vid}/naechster-schritt",
                         data={"schritt": "nochmal", "wann": "3wt", "einwand_id": str(eid),
                               "notiz": "Kunde wartet auf KfW-Zusage"}, headers=JSON)
        self.assertEqual(r.status_code, 200, r.text)
        antwort = r.json()
        self.assertEqual(antwort["einwand"], "Förderung unklar")
        self.assertEqual(antwort["versuche"], 1)
        self.assertIn("Einwand „Förderung unklar“ vermerkt", antwort["meldung"])
        s = SessionLocal()
        try:
            v = s.get(Vorgang, vid)
            self.assertEqual(v.letzter_einwand_id, eid)
            eintraege = s.query(VorgangEinwand).filter(VorgangEinwand.vorgang_id == vid).all()
            self.assertEqual(len(eintraege), 1)
            self.assertEqual(eintraege[0].einwand_id, eid)
            self.assertEqual(eintraege[0].benutzer_id, self.ad_id)
            self.assertEqual(verfolgung.letzter_einwand(s, v).name, "Förderung unklar")
            ctx = verfolgung.dialog_kontext(s, v)
            self.assertEqual(ctx["letzter_einwand"], "Förderung unklar")
            self.assertEqual(ctx["nachfass_versuche"], 1)
            self.assertTrue(ctx["einwaende"])
        finally:
            s.close()
        # beim nächsten Anruf steht der Chip oben auf der Anruf-Karte (Partial in der Akte)
        seite = self.ad.get(f"/vorgaenge/{vid}").text
        self.assertIn("Letzter Einwand: <strong>Förderung unklar</strong>", seite)
        self.assertIn(f'data-ns-einwand="{vid}"', seite)
        # Rückgängig senkt den Zähler und nimmt den Einwand zurück
        r2 = self.ad.post(f"/vorgaenge/{vid}/naechster-schritt",
                          data={"schritt": "rueckgaengig", "token": antwort["rueckgaengig"]["token"]},
                          headers=JSON)
        self.assertEqual(r2.status_code, 200, r2.text)
        self.assertTrue(r2.json()["ok"])
        self.assertEqual(r2.json()["versuche"], 0)
        s = SessionLocal()
        try:
            v = s.get(Vorgang, vid)
            self.assertEqual(v.nachfass_versuche, 0)
            self.assertIsNone(v.letzter_einwand_id)
            self.assertEqual(s.query(VorgangEinwand).filter(VorgangEinwand.vorgang_id == vid).count(), 0)
            self.assertEqual(v.verfolgung_status, "versendet")
        finally:
            s.close()

    def test_unbekannter_einwand_400_kein_chip_ok(self):
        s = SessionLocal()
        try:
            v = self._vorgang(s)
            s.commit()
            vid = v.id
        finally:
            s.close()
        r = self.innen.post(f"/vorgaenge/{vid}/naechster-schritt",
                            data={"schritt": "nochmal", "wann": "3wt", "einwand_id": "999999"},
                            headers=JSON)
        self.assertEqual(r.status_code, 400)
        self.assertIn("Einwand", r.json()["meldung"])
        r = self.innen.post(f"/vorgaenge/{vid}/naechster-schritt",
                            data={"schritt": "nochmal", "wann": "3wt", "einwand_id": ""}, headers=JSON)
        self.assertEqual(r.status_code, 200, r.text)
        s = SessionLocal()
        try:
            self.assertEqual(s.get(Vorgang, vid).nachfass_versuche, 1)
            self.assertEqual(s.query(VorgangEinwand).filter(VorgangEinwand.vorgang_id == vid).count(), 0)
        finally:
            s.close()

    def test_parametrierung_liste_und_inaktiv_parameter(self):
        seite = self.admin.get("/parametrierung/angebotstool").text
        for text in ('action="/parametrierung/einwaende"', 'name="inaktiv_tage"', 'name="inaktiv_tage_mfh"',
                     "Einwände beim Nachfassen", 'value="umbenennen"', 'value="umschalten"'):
            self.assertIn(text, seite, text)
        for name in verfolgung.EINWAENDE_START:
            self.assertIn(name, seite)
        kopf = {"Referer": "http://testserver/parametrierung/angebotstool"}
        # anlegen, umbenennen, deaktivieren, Reihenfolge
        r = self.admin.post("/parametrierung/einwaende",
                            data={"aktion": "hinzufuegen", "name": f"{PRAEFIX} Dachstatik"}, headers=kopf)
        self.assertEqual(r.status_code, 303)
        self.assertIn("/parametrierung/angebotstool", r.headers["location"])
        s = SessionLocal()
        try:
            neu = s.query(Einwand).filter(Einwand.name == f"{PRAEFIX} Dachstatik").first()
            self.assertIsNotNone(neu)
            self.assertTrue(neu.aktiv)
            self.assertEqual(neu.sortierung, s.query(Einwand).count())
            nid = neu.id
            # Dublette (ohne Groß-/Kleinschreibung) wird nicht angelegt
            self.admin.post("/parametrierung/einwaende",
                            data={"aktion": "hinzufuegen", "name": f"{PRAEFIX} dachstatik"}, headers=kopf)
            self.assertEqual(s.query(Einwand).filter(Einwand.name.ilike(f"{PRAEFIX} dachstatik")).count(), 1)
        finally:
            s.close()
        self.admin.post("/parametrierung/einwaende",
                        data={"aktion": "umbenennen", "id": str(nid), "name": f"{PRAEFIX} Statik"}, headers=kopf)
        self.admin.post("/parametrierung/einwaende", data={"aktion": "hoch", "id": str(nid)}, headers=kopf)
        self.admin.post("/parametrierung/einwaende", data={"aktion": "umschalten", "id": str(nid)}, headers=kopf)
        s = SessionLocal()
        try:
            e = s.get(Einwand, nid)
            self.assertEqual(e.name, f"{PRAEFIX} Statik")
            self.assertFalse(e.aktiv)
            self.assertEqual(e.sortierung, s.query(Einwand).count() - 1)
            self.assertNotIn(nid, [x.id for x in verfolgung.aktive_einwaende(s)])
        finally:
            s.close()
        # Schwellen des Kennzeichens über das Nachfass-Formular (0–365, ungültig ignoriert)
        r = self.admin.post("/parametrierung/einstellungen",
                            data={"nachfass_formular": "1", "nachfass_werktage": "3",
                                  "nachfass_werktage_mfh": "5", "inaktiv_tage": "21",
                                  "inaktiv_tage_mfh": "x"}, headers=kopf)
        self.assertEqual(r.status_code, 303)
        s = SessionLocal()
        try:
            self.assertEqual(leadmanagement.parameter_holen(s, "inaktiv_tage", ""), "21")
            self.assertEqual(leadmanagement.parameter_holen(s, "inaktiv_tage_mfh", ""), "20")
            self.assertEqual(nachfassen.inaktiv_parameter(s), 21)
            leadmanagement.parameter_setzen(s, "inaktiv_tage", "14")
            s.commit()
        finally:
            s.close()

    def test_statistik_einwaende_neben_den_gruenden(self):
        s = SessionLocal()
        try:
            v = self._vorgang(s)
            eid = self._einwand_id(s, "Finanzierung offen")
            s.add(VorgangEinwand(vorgang_id=v.id, einwand_id=eid, zeit=datetime.now(), benutzer_id=self.ad_id))
            s.add(VorgangEinwand(vorgang_id=v.id, einwand_id=eid, zeit=datetime.now(), benutzer_id=self.ad_id))
            s.commit()
            von = datetime.now() - timedelta(days=1)
            bis = datetime.now() + timedelta(days=1)
            zeilen = dict(verfolgung.einwaende_verteilung(s, von, bis))
            self.assertEqual(zeilen.get("Finanzierung offen"), 2)
            self.assertEqual(dict(verfolgung.einwaende_verteilung(s, von, bis, ad_id=self.ad2_id)), {})
            self.assertEqual(dict(verfolgung.einwaende_verteilung(s, von, bis, nur_benutzer_id=self.ad_id)).get("Finanzierung offen"), 2)
            self.assertEqual(dict(verfolgung.einwaende_verteilung(s, von, bis, sparte="PV")), {})
            self.assertEqual(dict(verfolgung.einwaende_verteilung(s, von, bis, sparte="WP")).get("Finanzierung offen"), 2)
        finally:
            s.close()
        seite = self.admin.get("/statistik?zeitraum=monat").text
        self.assertIn("Einwände beim Nachfassen", seite)
        self.assertIn("Finanzierung offen", seite)
        self.assertIn("Ablehnungsgründe", seite)
        # AD sieht nur eigene
        self.assertIn("Finanzierung offen", self.ad.get("/statistik?zeitraum=monat").text)
        self.assertNotIn("Finanzierung offen</td>", self.ad2.get("/statistik?zeitraum=monat").text)

    def test_migration_zweimal(self):
        s = SessionLocal()
        try:
            einstellung_setzen(s, verfolgung.MIGRATION_MARKER_V33, "")
            s.commit()
            meldungen = verfolgung.migration_v33_nachfassen(s)
            s.commit()
            self.assertEqual(len(meldungen), 1)
            self.assertIn("bereits vorhanden", meldungen[0])    # Startwerte sind schon da
            self.assertEqual(verfolgung.migration_v33_nachfassen(s), [])
            namen = {e.name for e in s.query(Einwand)}
            for name in verfolgung.EINWAENDE_START:
                self.assertIn(name, namen)
            self.assertEqual(einstellung_holen(s, verfolgung.MIGRATION_MARKER_V33, ""), "erledigt")
        finally:
            s.close()


# --- 4) Nachfass-Mail aus dem Postfach des AD -------------------------------------------
class NachfassMail(Basis):
    def _mit_graph(self, modus="anwendung", ok=True, fehler="", conv="AAMk-conv-1"):
        """Graph ausschließlich gemockt: Modus + mail_senden_als."""
        senden = mock.MagicMock(return_value=(ok, fehler, conv))
        stapel = [mock.patch.object(graph_versand, "modus", return_value=modus),
                  mock.patch.object(graph_versand, "mail_senden_als", senden)]
        return stapel, senden

    def test_mail_aus_dem_ad_postfach_im_verlauf_und_chat(self):
        s = SessionLocal()
        try:
            v = self._vorgang(s)
            s.commit()
            vid = v.id
            aid = s.query(Angebot).filter(Angebot.vorgang_id == vid).first().id
            nummer = s.get(Angebot, aid).nummer
        finally:
            s.close()
        stapel, senden = self._mit_graph()
        with stapel[0], stapel[1]:
            # Vorschau (JSON) – Platzhalter gefüllt, Signatur dran
            r = self.ad.get(f"/vorgaenge/{vid}/nachfass-mail/vorschau?vorlage=2", headers=JSON)
            self.assertEqual(r.status_code, 200, r.text)
            vorschau = r.json()
            self.assertTrue(vorschau["ok"])
            self.assertEqual(vorschau["vorlage"], 2)
            self.assertIn(nummer, vorschau["betreff"])
            self.assertIn("Sehr geehrte Frau V33N Kundin,", vorschau["html"])
            self.assertIn("Arnold-Overbeck-Str. 63-65", vorschau["html"])   # Firmenblock ohne Upload
            self.assertNotIn("Ihr Friondo-Team", vorschau["html"])         # keine doppelte Grußformel
            self.assertEqual(vorschau["absender"], "ad.eins@v33n.local")
            self.assertEqual(vorschau["empfaenger"], "karla@kunde.v33n.local")
            self.assertEqual(vorschau["fehlende"], [])
            # Akte: Knopf aktiv, Vorlagen-Chips, Hinweis auf eigenes Postfach
            seite = self.ad.get(f"/vorgaenge/{vid}").text
            self.assertIn('data-ns-schritt="mail"', seite)
            self.assertNotIn('data-ns-schritt="mail"\n                    aria-controls="ns-form-mail-%d" aria-expanded="false"\n                    disabled' % vid, seite)
            self.assertIn("Nachfassen 1", seite)
            self.assertIn("Nachfassen 2", seite)
            self.assertIn("aus ad.eins@v33n.local", seite)
            # Senden
            r = self.ad.post(f"/vorgaenge/{vid}/nachfass-mail", data={"vorlage": "1"}, headers=JSON)
            self.assertEqual(r.status_code, 200, r.text)
            antwort = r.json()
            self.assertTrue(antwort["ok"])
            self.assertEqual(antwort["conversation_id"], "AAMk-conv-1")
            self.assertEqual(antwort["vorlage"], 1)
            self.assertIn("ad.eins@v33n.local", antwort["meldung"])
        senden.assert_called_once()
        args, kwargs = senden.call_args
        self.assertEqual(args[0], "ad.eins@v33n.local")              # Postfach des AD
        self.assertEqual(args[1], "karla@kunde.v33n.local")
        self.assertIn(nummer, args[2])
        self.assertIn("Sehr geehrte Frau V33N Kundin,", args[3])
        self.assertIn("V33N AD Eins", args[3])                        # {absender} = AD
        self.assertEqual(kwargs.get("anhaenge"), [])
        s = SessionLocal()
        try:
            mails = s.query(AngebotsMail).filter(AngebotsMail.angebot_id == aid).all()
            self.assertEqual(len(mails), 1)
            self.assertFalse(mails[0].eingehend)
            self.assertEqual(mails[0].von_email, "ad.eins@v33n.local")
            self.assertIn(nummer, mails[0].betreff)
            self.assertTrue(mails[0].graph_id.startswith(nachfassen.MAIL_GRAPH_ID_PRAEFIX + "AAMk-conv-1"))
            notizen = [n for n in s.query(VorgangsNotiz).filter(VorgangsNotiz.vorgang_id == vid)]
            self.assertTrue(any("Nachfass-Mail 1 an karla@kunde.v33n.local gesendet" in n.text for n in notizen),
                            [n.text for n in notizen])
            self.assertTrue(any(n.herkunft == nachfassen.NACHFASS_HERKUNFT for n in notizen))
            akt = s.query(LeadAktivitaet).filter(LeadAktivitaet.vorgang_id == vid, LeadAktivitaet.typ == "mail").all()
            self.assertEqual(len(akt), 1)
            # die Mail zählt als Kontakt → kein Inaktivitäts-Kennzeichen mehr
            self.assertIsNone(nachfassen.inaktiv_tage_fuer(s, s.get(Vorgang, vid)))
            # Letzte Aktivitäten der Anruf-Karte zeigen die gesendete Mail
            texte = [e["text"] for e in nachfassen.letzte_aktivitaeten(s, s.get(Vorgang, vid))]
            self.assertTrue(any(t.startswith("Gesendet: ") for t in texte), texte)
        finally:
            s.close()
        # Akte zeigt die Mail im Verlauf (ID-Sicht)
        self.assertIn(nummer, self.innen.get(f"/vorgaenge/{vid}").text)

    def test_pdf_anhang_und_zweite_vorlage(self):
        s = SessionLocal()
        try:
            v = self._vorgang(s, extern=True)
            a = s.query(Angebot).filter(Angebot.vorgang_id == v.id).first()
            ordner = Path(tempfile.mkdtemp(prefix="v33n_"))
            pdf = ordner / "Angebot-T.pdf"
            pdf.write_bytes(b"%PDF-1.4\n%V33N Testdatei\n%%EOF\n")
            a.extern_pdf_pfad = str(pdf)
            s.commit()
            vid = v.id
        finally:
            s.close()
        stapel, senden = self._mit_graph(conv="AAMk-conv-2")
        with stapel[0], stapel[1]:
            r = self.innen.post(f"/vorgaenge/{vid}/nachfass-mail", data={"vorlage": "2", "pdf": "1"}, headers=JSON)
            self.assertEqual(r.status_code, 200, r.text)
        args, kwargs = senden.call_args
        self.assertEqual(args[0], "innen@v33n.local")                 # Innendienst: eigenes Postfach [ANNAHME]
        anhaenge = kwargs.get("anhaenge")
        self.assertEqual(len(anhaenge), 1)
        self.assertEqual(anhaenge[0][0], "Angebot-T.pdf")
        self.assertTrue(anhaenge[0][1].startswith(b"%PDF"))
        self.assertEqual(anhaenge[0][2], "application/pdf")
        self.assertIn("kurze Nachfrage", args[2])                      # Betreff Nachfassen 2
        s = SessionLocal()
        try:
            notizen = [n.text for n in s.query(VorgangsNotiz).filter(VorgangsNotiz.vorgang_id == vid)]
            self.assertTrue(any("Nachfass-Mail 2" in t and "mit Angebots-PDF" in t for t in notizen), notizen)
        finally:
            s.close()

    def test_modus_delegiert_gesperrt_knopf_und_route_409(self):
        s = SessionLocal()
        try:
            v = self._vorgang(s)
            s.commit()
            vid = v.id
        finally:
            s.close()
        stapel, senden = self._mit_graph(modus="delegiert")
        with stapel[0], stapel[1]:
            seite = self.ad.get(f"/vorgaenge/{vid}").text
            self.assertIn(nachfassen.MAIL_GESPERRT_HINWEIS, seite)
            knopf = seite[seite.index('data-ns-schritt="mail"'):seite.index("Nachfass-Mail</button>")]
            self.assertIn("disabled", knopf)
            self.assertNotIn('id="ns-form-mail-%d"' % vid, seite)
            r = self.ad.post(f"/vorgaenge/{vid}/nachfass-mail", data={"vorlage": "1"}, headers=JSON)
            self.assertEqual(r.status_code, 409, r.text)
            self.assertFalse(r.json()["ok"])
            self.assertIn("Graph als Anwendung", r.json()["meldung"])
            # ohne JavaScript: Redirect mit Meldung
            r = self.ad.post(f"/vorgaenge/{vid}/nachfass-mail", data={"vorlage": "1", "zurueck": f"/vorgaenge/{vid}"})
            self.assertEqual(r.status_code, 303)
            self.assertIn("meldung=", r.headers["location"])
        senden.assert_not_called()
        s = SessionLocal()
        try:
            self.assertEqual(s.query(AngebotsMail).join(Angebot, Angebot.id == AngebotsMail.angebot_id)
                             .filter(Angebot.vorgang_id == vid).count(), 0)
        finally:
            s.close()

    def test_rechte_und_fehlende_angaben(self):
        s = SessionLocal()
        try:
            v = self._vorgang(s)                                   # AD Eins
            ohne = self._vorgang(s, kunde_id=self.ohne_mail_id)    # Kunde ohne E-Mail
            drei = self._vorgang(s, ad_id=self.ad_ohne_mail_id)    # AD ohne eigene E-Mail
            s.commit()
            vid, oid, did = v.id, ohne.id, drei.id
        finally:
            s.close()
        stapel, senden = self._mit_graph()
        with stapel[0], stapel[1]:
            r = self.ad2.post(f"/vorgaenge/{vid}/nachfass-mail", data={"vorlage": "1"}, headers=JSON)
            self.assertEqual(r.status_code, 403)
            self.assertEqual(self.ad2.get(f"/vorgaenge/{vid}/nachfass-mail/vorschau", headers=JSON).status_code, 403)
            r = self.innen.post(f"/vorgaenge/{oid}/nachfass-mail", data={"vorlage": "1"}, headers=JSON)
            self.assertEqual(r.status_code, 400)
            self.assertIn("keine E-Mail-Adresse", r.json()["meldung"])
            drei_client = _client(self.ad_ohne_mail_id)
            r = drei_client.post(f"/vorgaenge/{did}/nachfass-mail", data={"vorlage": "1"}, headers=JSON)
            self.assertEqual(r.status_code, 400)
            self.assertIn("Absender", r.json()["meldung"])
            seite = drei_client.get(f"/vorgaenge/{did}").text
            self.assertIn("Keine E-Mail-Adresse des Absenders", seite)
            # Graph-Fehler → 502, nichts verbucht
            senden.return_value = (False, "HTTP 403 ErrorAccessDenied", "")
            r = self.ad.post(f"/vorgaenge/{vid}/nachfass-mail", data={"vorlage": "1"}, headers=JSON)
            self.assertEqual(r.status_code, 502)
            self.assertIn("ErrorAccessDenied", r.json()["meldung"])
        s = SessionLocal()
        try:
            self.assertEqual(s.query(AngebotsMail).join(Angebot, Angebot.id == AngebotsMail.angebot_id)
                             .filter(Angebot.vorgang_id == vid).count(), 0)
            self.assertEqual(s.query(VorgangsNotiz).filter(VorgangsNotiz.vorgang_id == vid,
                                                           VorgangsNotiz.text.like("Nachfass-Mail%")).count(), 0)
        finally:
            s.close()

    def test_vorlagen_editor_nachfassen_1_und_2(self):
        seite = self.admin.get("/parametrierung/vorlagen?vorlage=nachfassen_1").text
        self.assertIn("Nachfassen 1", seite)
        self.assertIn("Nachfassen 2", seite)
        self.assertIn('value="nachfassen_1"', seite)
        self.assertIn("haben Sie noch Fragen", seite)             # Standard-Betreff als Ausgangspunkt
        self.assertIn("Standardtext (Entwurf v33", seite)
        r = self.admin.post("/parametrierung/vorlagen",
                            data={"vorlage": "nachfassen_1", "betreff": f"{PRAEFIX} Betreff {{angebotsnummer}}",
                                  "text": "{briefanrede}\n\nkurz nachgefragt.\n\n{absender}"})
        self.assertEqual(r.status_code, 303)
        self.assertIn("vorlage=nachfassen_1", r.headers["location"])
        s = SessionLocal()
        try:
            betreff, text, eigene = mail_vorlagen.nachfass_vorlage_laden(s, 1)
            self.assertTrue(eigene)
            self.assertEqual(betreff, f"{PRAEFIX} Betreff {{angebotsnummer}}")
            self.assertEqual(mail_vorlagen.nachfass_status(s), {1: True, 2: False})
            # Rendern für ein Angebot: Platzhalter gefüllt, Klartext als Alternativkörper
            v = self._vorgang(s)
            a = s.query(Angebot).filter(Angebot.vorgang_id == v.id).first()
            k = s.get(Kunde, v.kunde_id)
            b, html, klartext = mail_vorlagen.nachfass_mail_fuer_vorgang(s, a, k, 1, "V33N AD Eins")
            self.assertEqual(b, f"{PRAEFIX} Betreff {a.nummer}")
            self.assertIn("<p>Sehr geehrte Frau V33N Kundin,</p>", html)
            self.assertIn("V33N AD Eins", html)
            self.assertNotIn("<", klartext)
            self.assertIn("kurz nachgefragt.", klartext)
            s.rollback()
        finally:
            s.close()
        self.assertIn("Standardtext wiederherstellen", self.admin.get("/parametrierung/vorlagen?vorlage=nachfassen_1").text)
        r = self.admin.post("/parametrierung/vorlagen", data={"vorlage": "nachfassen_1", "aktion": "entfernen"})
        self.assertEqual(r.status_code, 303)
        s = SessionLocal()
        try:
            self.assertFalse(mail_vorlagen.nachfass_vorlage_laden(s, 1)[2])
            self.assertEqual(mail_vorlagen.nachfass_nummer("nachfassen_2"), 2)
            self.assertEqual(mail_vorlagen.nachfass_nummer("7"), 1)
        finally:
            s.close()
        # Außendienst kommt nicht an den Editor (Parametrierung bleibt Büro-Rollen vorbehalten)
        self.assertEqual(self.ad.get("/parametrierung/vorlagen?vorlage=nachfassen_1").status_code, 303)

    def test_eigene_signatur_des_ad_unter_der_mail(self):
        # Seite erreichbar für AD, Upload der eigenen Signatur, Montage 403
        r = self.ad.get("/einstellungen/signatur")
        self.assertEqual(r.status_code, 200, r.text[:300])
        self.assertIn("Meine E-Mail-Signatur", r.text)
        self.assertEqual(_client(self.montage_id).get("/einstellungen/signatur").status_code, 403)
        html = ("<html><body><p>Viele Grüße<br><b>V33N AD Eins</b><br>Außendienst Friondo</p>"
                "<img src=\"sig-Dateien/logo.png\"></body></html>")
        r = self.ad.post("/einstellungen/signatur",
                         files=[("dateien", ("signatur.htm", html.encode("utf-8"), "text/html")),
                                ("dateien", ("logo.png", b"\x89PNG\r\n\x1a\n" + b"0" * 20, "image/png"))])
        self.assertEqual(r.status_code, 303, r.text)
        self.assertTrue(signaturen.vorhanden(self.ad_id))
        self.assertIn("logo.png", self.ad.get("/einstellungen/signatur").text)
        # Bild der Vorschau
        _html, bilder = signaturen.fuer_versand(self.ad_id)
        self.assertEqual(len(bilder), 1)
        self.assertEqual(self.ad.get(f"/einstellungen/signatur/bild/{bilder[0][0]}").status_code, 200)
        s = SessionLocal()
        try:
            v = self._vorgang(s)
            s.commit()
            vid = v.id
        finally:
            s.close()
        stapel, senden = self._mit_graph()
        with stapel[0], stapel[1]:
            r = self.ad.post(f"/vorgaenge/{vid}/nachfass-mail", data={"vorlage": "1"}, headers=JSON)
            self.assertEqual(r.status_code, 200, r.text)
        args, _kwargs = senden.call_args
        self.assertIn("Außendienst Friondo", args[3])                 # eigene Signatur statt Standard
        self.assertNotIn("Ihr Friondo-Team", args[3])
        # Übergang ohne Inline-Anhänge: Bild als data:-URI eingebettet (kein offener cid:-Verweis)
        self.assertIn("data:image/png;base64,", args[3])
        self.assertNotIn("cid:", args[3])
        # Entfernen → Standard-Signatur gilt wieder
        r = self.ad.post("/einstellungen/signatur", data={"aktion": "entfernen"})
        self.assertEqual(r.status_code, 303)
        self.assertFalse(signaturen.vorhanden(self.ad_id))
        # fremde Signatur bleibt unerreichbar: die Parametrierungs-Seite ist für den AD gesperrt
        self.assertEqual(self.ad.get(f"/parametrierung/signaturen?benutzer_id={self.id_id}").status_code, 303)

    def test_wiederholung_sendet_nie_zweimal(self):
        """Die Verbuchung läuft im _speichern-Muster; der Graph-Aufruf liegt davor – eine
        Wiederholung (Schreibsperre) darf keinen zweiten Versand auslösen."""
        s = SessionLocal()
        try:
            v = self._vorgang(s)
            s.commit()
            vid = v.id
        finally:
            s.close()
        from app.routers import angebote as angebote_router
        original = angebote_router._speichern
        aufrufe = {"n": 0}

        def speichern_mit_wiederholung(session, aktion, wiederholungen=1):
            aufrufe["n"] += 1
            aktion()            # erster Versuch „scheitert“ simuliert: Rollback + Wiederholung
            session.rollback()
            return original(session, aktion, wiederholungen)

        stapel, senden = self._mit_graph(conv="AAMk-conv-3")
        with stapel[0], stapel[1], mock.patch.object(angebote_router, "_speichern", speichern_mit_wiederholung):
            r = self.ad.post(f"/vorgaenge/{vid}/nachfass-mail", data={"vorlage": "1"}, headers=JSON)
            self.assertEqual(r.status_code, 200, r.text)
        self.assertEqual(aufrufe["n"], 1)
        senden.assert_called_once()
        s = SessionLocal()
        try:
            self.assertEqual(s.query(AngebotsMail).join(Angebot, Angebot.id == AngebotsMail.angebot_id)
                             .filter(Angebot.vorgang_id == vid).count(), 1)
        finally:
            s.close()


if __name__ == "__main__":
    unittest.main()
