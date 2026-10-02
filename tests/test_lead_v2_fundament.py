# Tests PLAN_LEAD_V2 Phase 104 (CLAUDE v23): Fundament – Datenmodell,
# Steuerdatei (Kaskade 5 Stufen, Gründe, Objektarten, Status), Parameter,
# Mail-Vorlagen, Info-Veranstaltungs-Terminregel, Handelsvertreter-Helfer.
# Laufen im Demo-Modus gegen die Entwicklungs-DB; Testleads tragen den
# Nachnamen „LeadV2F-Test“ und werden aufgeräumt.
import json
import unittest
import warnings
from datetime import date, datetime, timedelta

warnings.filterwarnings("ignore")

from sqlalchemy import text

from app import lead_info, lead_mail, lead_v2, leadmanagement_logik
from app import leadmanagement as kern
from app.db import SessionLocal, engine, init_db
from app.models import (AdProfil, Benutzer, InfoVeranstaltung, KommunikationLog,
                        Kunde, LeadAktivitaet, LeadQuelle, Vorgang, INTERESSE_CODES,
                        OBJEKTART_CODES, TERMIN_TYPEN)

NACHNAME = "LeadV2F-Test"


def aufraeumen(s):
    for k in s.query(Kunde).filter(Kunde.nachname.like(f"{NACHNAME}%")):
        for v in s.query(Vorgang).filter_by(kunde_id=k.id):
            s.query(LeadAktivitaet).filter_by(vorgang_id=v.id).delete()
            s.query(KommunikationLog).filter_by(vorgang_id=v.id).delete()
            s.delete(v)
        s.delete(k)
    for b in s.query(Benutzer).filter(Benutzer.name.like("LeadV2F %")):
        s.query(AdProfil).filter_by(benutzer_id=b.id).delete()
        s.delete(b)
    s.commit()


class Basis(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        init_db()
        cls.s = SessionLocal()
        aufraeumen(cls.s)
        cls.modus = kern.parameter_holen(cls.s, "lead_freigabe_modus", "admin")
        kern.parameter_setzen(cls.s, "lead_freigabe_modus", "admin")
        cls.s.commit()

    @classmethod
    def tearDownClass(cls):
        aufraeumen(cls.s)
        kern.parameter_setzen(cls.s, "lead_freigabe_modus", cls.modus)
        cls.s.commit()
        cls.s.close()

    def lead(self, nr, versuche=0, **extra):
        quelle = self.s.query(LeadQuelle).filter_by(key="website").first()
        daten = {"vorname": f"V{nr}", "nachname": f"{NACHNAME}-{nr}", "plz": "47139",
                 "ort": "Duisburg", "telefon": f"0203 77{nr:04d}", "sparten": ["WP"],
                 "email": f"v2f{nr}@test.local"}
        vorgang, _ = kern.lead_anlegen(self.s, daten, quelle, "api", entscheidung="neu")
        vorgang.demo = True
        vorgang.versuch_nr = versuche
        if versuche:
            vorgang.lead_phase = "in_kontaktierung"
        for k, v in extra.items():
            setattr(vorgang, k, v)
        self.s.commit()
        return vorgang


class Datenmodell(Basis):
    def test_neue_spalten_und_tabellen(self):
        with engine.begin() as v:
            def spalten(t):
                return {z[1] for z in v.execute(text(f"PRAGMA table_info({t})"))}
            self.assertTrue({"objektart", "parteien"} <= spalten("kunden"))
            self.assertTrue({"ad_id", "vorab_angebot", "veranstaltung_id",
                             "teilgenommen"} <= spalten("vorgaenge"))
            self.assertTrue({"typ", "medium", "ics_uid", "ics_sequence"} <= spalten("vot_termine"))
            self.assertTrue({"buchungslink", "nebenstelle"} <= spalten("benutzer"))
            self.assertTrue({"terminiert_selbst", "kompetenz_sparten", "kompetenz_kombi",
                             "kompetenz_mfh", "kompetenz_gewerbe"} <= spalten("ad_profile"))
            self.assertTrue({"call_id", "richtung", "nebenstelle"} <= spalten("lead_aktivitaeten"))
            tabellen = {z[0] for z in v.execute(text(
                "SELECT name FROM sqlite_master WHERE type='table'"))}
            self.assertTrue({"todos", "info_veranstaltungen",
                             "benutzer_einstellungen"} <= tabellen)

    def test_sparte_gewerbe_und_konstanten(self):
        self.assertIn("GW", INTERESSE_CODES)
        self.assertIn("GW", leadmanagement_logik.SPARTEN)
        self.assertEqual(OBJEKTART_CODES, ["EFH", "RH", "REH", "MFH"])
        self.assertEqual(TERMIN_TYPEN, ["vot", "telefon", "online"])

    def test_benutzereinstellung(self):
        lead_v2.einstellung_setzen(self.s, 1, "lv2f_test", {"spalten": ["a", "b"]})
        self.assertEqual(lead_v2.einstellung_holen(self.s, 1, "lv2f_test")["spalten"], ["a", "b"])
        lead_v2.einstellung_setzen(self.s, 1, "lv2f_test", [1])
        self.assertEqual(lead_v2.einstellung_holen(self.s, 1, "lv2f_test"), [1])
        self.s.execute(text("DELETE FROM benutzer_einstellungen WHERE key='lv2f_test'"))
        self.s.commit()


class Steuerdatei(Basis):
    def test_kaskade_fuenf_stufen(self):
        logik = leadmanagement_logik.hole_logik(erzwingen=True)
        self.assertEqual(logik.letzte_stufe(), 5)
        self.assertFalse(logik.stufe(4).letzter)
        s5 = logik.stufe(5)
        self.assertTrue(s5.letzter)
        self.assertEqual((s5.wiedervorlage_nach, s5.aktion), ("+14d", "mail_disqualifiziert"))
        self.assertEqual([s.wiedervorlage_nach for s in logik.kaskade],
                         ["+2h", "+1d 18:00", "+3d", "+7d", "+14d"])

    def test_gruende_verloren_und_nachbearbeitung(self):
        logik = leadmanagement_logik.hole_logik()
        verloren = [g.grund for g in logik.gruende_der_phase("verloren")]
        self.assertEqual(verloren, ["Zu teuer", "Kein Interesse mehr", "Bleibt bei Öl/Gas",
                                    "Woanders unterschrieben", "Sonstiges"])
        self.assertTrue(next(g for g in logik.gruende_der_phase("verloren")
                             if g.grund == "Sonstiges").freitext_pflicht)
        zurueck = [g.grund for g in logik.gruende_der_phase("zurueckgestellt")]
        self.assertIn("Nachbearbeitung, noch nicht bereit für VOT", zurueck)

    def test_objektarten_und_status(self):
        logik = leadmanagement_logik.hole_logik()
        self.assertEqual([o.code for o in logik.objektarten], ["EFH", "RH", "REH", "MFH"])
        self.assertTrue(logik.objektart("MFH").parteien_pflicht)
        self.assertFalse(logik.objektart("EFH").parteien_pflicht)
        phasen = {z.phase for z in logik.status_zeilen}
        from app.models import LEAD_PHASEN
        self.assertEqual(phasen, set(LEAD_PHASEN))
        self.assertEqual(logik.board_fuer("neu"), ("hauptboard", "neu"))
        self.assertEqual(logik.board_fuer("zurueckgestellt"), ("hauptboard", "pausiert"))
        self.assertEqual(logik.board_fuer("nicht_erreicht"), ("hauptboard", "disqualifiziert"))
        self.assertEqual(logik.board_fuer("terminiert"), ("terminiert", "angebotserstellung"))
        self.assertEqual(logik.board_fuer("angebot"), ("terminiert", "angebotsversand"))
        self.assertEqual(logik.phase_fuer_monday("Standby"), "zurueckgestellt")
        self.assertEqual(logik.phase_fuer_monday("3. Kontaktversuch"), "in_kontaktierung")
        self.assertEqual(logik.phase_fuer_monday("Vorab Angebot"), "erfasst")
        self.assertFalse(logik.fehler, logik.fehler)


class Parameter(Basis):
    def test_startwerte(self):
        self.assertEqual(kern.parameter_holen(self.s, "versuche_max"), "5")
        self.assertEqual(kern.versuche_max(self.s), 5)
        self.assertEqual(kern.parameter_holen(self.s, "info_uhrzeit"), "18:00")
        self.assertEqual(kern.parameter_holen(self.s, "ersatz_radius_stufen"), "5; 10")
        self.assertIn("objektart", lead_v2.pflichtfelder(self.s))
        self.assertIn("enni", lead_v2.hv_ausschluss_liste(self.s))
        self.assertTrue(self.s.query(LeadQuelle).filter_by(key="info_veranstaltung").first()
                        or kern.quellen_vorbelegen(self.s) >= 0)

    def test_quelle_info_veranstaltung(self):
        kern.quellen_vorbelegen(self.s)
        q = self.s.query(LeadQuelle).filter_by(key="info_veranstaltung").one()
        self.assertEqual(kern.quelle_gruppe(q), "veranstaltung")


class Kaskade(Basis):
    def test_stufe_vier_wiedervorlage_und_mail(self):
        v = self.lead(1, versuche=4)
        meldung = kern.kaskade_anwenden(self.s, v)
        self.s.commit()
        self.assertTrue(meldung.startswith("Wiedervorlage"))
        self.assertEqual(v.lead_phase, "in_kontaktierung")
        self.assertGreater(v.naechste_aktion_am, datetime.now() + timedelta(days=5))
        mails = [m.vorlage_key for m in self.s.query(KommunikationLog)
                 .filter_by(vorgang_id=v.id) if m.vorlage_key != "eingangsbestaetigung"]
        self.assertEqual(mails, ["nicht_erreicht"])

    def test_stufe_fuenf_disqualifiziert(self):
        v = self.lead(2, versuche=5)
        meldung = kern.kaskade_anwenden(self.s, v)
        self.s.commit()
        self.assertIn("Nicht erreicht", meldung)
        self.assertEqual(v.lead_phase, "nicht_erreicht")
        self.assertTrue(kern.versuche_gesperrt(self.s, v))
        mails = sorted(m.vorlage_key for m in self.s.query(KommunikationLog)
                       .filter_by(vorgang_id=v.id) if m.vorlage_key != "eingangsbestaetigung")
        self.assertEqual(mails, ["disqualifiziert", "nurture"])
        nurture = (self.s.query(KommunikationLog)
                   .filter_by(vorgang_id=v.id, vorlage_key="nurture").one())
        self.assertGreater(nurture.geplant_am, datetime.now() + timedelta(days=29))
        # Sendesperre: Demo → Modus protokoll
        self.assertEqual(nurture.modus, "protokoll")

    def test_versuche_max_parameter_greift(self):
        kern.parameter_setzen(self.s, "versuche_max", "3")
        self.s.commit()
        try:
            v = self.lead(3, versuche=3)
            kern.kaskade_anwenden(self.s, v)
            self.assertEqual(v.lead_phase, "nicht_erreicht")
        finally:
            kern.parameter_setzen(self.s, "versuche_max", "5")
            self.s.commit()


class Vorlagen(Basis):
    def test_neue_vorlagen(self):
        self.assertIn("disqualifiziert", lead_mail.VORLAGEN_START)
        self.assertIn("online_termin_einladung", lead_mail.VORLAGEN_START)
        text_dq = lead_mail.VORLAGEN_START["disqualifiziert"][2]
        for ph in ("{briefanrede}", "{vertriebler}", "{rueckruf_telefon}", "{sparten}"):
            self.assertIn(ph, text_dq)
        text_ot = lead_mail.VORLAGEN_START["online_termin_einladung"][2]
        self.assertIn("{buchungslink}", text_ot)
        self.assertIn("{kollege}", text_ot)
        lead_mail.vorlagen_vorbelegen(self.s)
        betreff, text_ = lead_mail.vorlage_laden(self.s, "disqualifiziert")
        self.assertTrue(betreff and text_)

    def test_werte_mit_rueckruf_telefon(self):
        v = self.lead(4)
        kern.parameter_setzen(self.s, "rueckruf_telefon", "0203 123456")
        self.s.commit()
        werte = lead_mail.werte_fuer(self.s, v)
        self.assertIn("rueckruf_telefon", werte)
        self.assertIn("buchungslink", werte)
        self.assertEqual(werte["rueckruf_telefon"], "0203 123456")
        kern.parameter_setzen(self.s, "rueckruf_telefon", "")
        self.s.commit()


class InfoTermine(unittest.TestCase):
    def test_ostern_und_feiertage(self):
        self.assertEqual(lead_info.ostersonntag(2026), date(2026, 4, 5))
        self.assertEqual(lead_info.ostersonntag(2027), date(2027, 3, 28))
        ft = lead_info.feiertage_nrw(2027)
        self.assertEqual(ft[date(2027, 5, 6)], "Christi Himmelfahrt")
        self.assertEqual(ft[date(2027, 5, 17)], "Pfingstmontag")
        self.assertEqual(ft[date(2027, 5, 27)], "Fronleichnam")

    def test_kontrollliste_oktober_2026_bis_august_2027(self):
        termine = lead_info.termine_ab(date(2026, 10, 1), 11)
        self.assertEqual([t.strftime("%d.%m.%Y") for t, _ in termine],
                         lead_info.KONTROLLTERMINE)
        self.assertTrue(all(t.hour == 18 and t.minute == 0 for t, _ in termine))
        verschoben = [t.strftime("%d.%m.%Y") for t, v in termine if v]
        self.assertEqual(verschoben, ["13.05.2027"])


class InfoVeranstaltungen(Basis):
    def test_anlegen_idempotent(self):
        lead_info.veranstaltungen_anlegen(self.s)
        self.s.commit()
        vorher = self.s.query(InfoVeranstaltung).count()
        self.assertGreaterEqual(vorher, 11)
        self.assertEqual(lead_info.veranstaltungen_anlegen(self.s), 0)
        beginne = {v.beginn.strftime("%d.%m.%Y") for v in self.s.query(InfoVeranstaltung)}
        self.assertTrue(set(lead_info.KONTROLLTERMINE) <= beginne)
        mai = self.s.query(InfoVeranstaltung).filter(
            InfoVeranstaltung.beginn == datetime(2027, 5, 13, 18, 0)).one()
        self.assertTrue(mai.verschoben)
        self.assertEqual(mai.ort, lead_info.STANDARD_ORT)

    def test_naechste_mit_vorlauf(self):
        lead_info.veranstaltungen_anlegen(self.s)
        self.s.commit()
        # Eingang 30.09.2026 + 3 Tage Vorlauf → 01.10. fällt raus → 05.11.
        n = lead_info.naechste_veranstaltung(self.s, ab=datetime(2026, 9, 30, 12, 0))
        self.assertEqual(n.beginn, datetime(2026, 11, 5, 18, 0))
        n2 = lead_info.naechste_veranstaltung(self.s, ab=datetime(2026, 9, 27, 12, 0))
        self.assertEqual(n2.beginn, datetime(2026, 10, 1, 18, 0))


class Handelsvertreter(Basis):
    def test_kennzeichen_und_kompetenz(self):
        b = Benutzer(name="LeadV2F Kyriakos Testmann", rolle="aussendienst", aktiv=True)
        self.s.add(b)
        self.s.flush()
        self.assertFalse(lead_v2.ist_handelsvertreter(self.s, b))
        profil = AdProfil(benutzer_id=b.id, terminiert_selbst=True,
                          kompetenz_sparten=json.dumps(["WP", "KL", "WB"]),
                          kompetenz_kombi=True, kompetenz_mfh=True)
        self.s.add(profil)
        self.s.commit()
        self.assertTrue(lead_v2.ist_handelsvertreter(self.s, b))
        self.assertIn(b.id, [h.id for h in lead_v2.handelsvertreter_liste(self.s)])
        ok, _ = lead_v2.kompetenz_passt(profil, ["WP", "PV"])
        self.assertTrue(ok)                       # Kombi erlaubt WP+PV
        ok, grund = lead_v2.kompetenz_passt(profil, ["PV"])
        self.assertFalse(ok)                      # PV einzeln nicht hinterlegt
        ok, _ = lead_v2.kompetenz_passt(profil, ["WP"], objektart="MFH")
        self.assertTrue(ok)
        profil.kompetenz_mfh = False
        ok, grund = lead_v2.kompetenz_passt(profil, ["WP"], objektart="MFH")
        self.assertFalse(ok)
        self.assertIn("MFH", grund)

    def test_startwerte_namensabgleich(self):
        self.assertEqual(lead_v2.kompetenz_startwerte("Kyriakos Sarigiannis"),
                         (["WP", "KL", "WB"], True, True, True))
        self.assertEqual(lead_v2.kompetenz_startwerte("H. Becker")[0], ["WP", "WB"])
        self.assertEqual(lead_v2.kompetenz_startwerte("R. Wilhelm"), (["WP", "PV", "KL"], False, False, False))
        self.assertIsNone(lead_v2.kompetenz_startwerte("Niko Goritsas"))
        self.assertTrue(lead_v2.ist_handelsvertreter_name("Simon O Grady"))
        self.assertTrue(lead_v2.ist_handelsvertreter_name("Rene Golaschewski"))
        self.assertTrue(lead_v2.ist_handelsvertreter_name("André Lind"))
        self.assertFalse(lead_v2.ist_handelsvertreter_name("D. Jobelius"))

    def test_ausschluss_und_objektart(self):
        v = self.lead(5)
        self.assertEqual(lead_v2.hv_ausgeschlossen(self.s, v), "")
        kunde = self.s.get(Kunde, v.kunde_id)
        kunde.vertriebskanal = "Enni"
        self.s.commit()
        self.assertIn("Innendienst", lead_v2.hv_ausgeschlossen(self.s, v))
        kunde.vertriebskanal = ""
        kunde.objektart = "MFH"
        self.s.commit()
        offen = lead_v2.pflichtfelder_offen(self.s, kunde, v)
        self.assertIn("Anzahl Parteien", offen)
        self.assertIn("Rechnungsadresse", offen)
        self.assertIn("Vertriebskanal", offen)
        self.assertEqual(lead_v2.objektart_aus_text("Mehrfamilienhaus"), "MFH")
        self.assertEqual(lead_v2.objektart_aus_text("Doppelhaushälfte"), "EFH")
        self.assertIsNone(lead_v2.objektart_aus_text("Gewerbe"))


if __name__ == "__main__":
    unittest.main()
