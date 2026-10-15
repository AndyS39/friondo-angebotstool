# Tests v33 (PLAN_V20 Phase 175, Agent R): Lead-Management-Nachträge Claudia Castro
# 14.10.2026 – (1) Kanal-Regel „Stadtwerke Düsseldorf“ (monday-Kanal „SWD“ und Angebots-
# profil SWD bilden auf denselben Kanalwert ab; AD mit Regel „nur Stadtwerke Düsseldorf“
# ist bei SWD-Leads der einzige Kandidat, alle anderen AD („außer“) nie; Sammelaktion
# meldet „übersprungen: Kanal Stadtwerke Düsseldorf“), (2) Infotext zum AD entfällt in
# AD-Profil und Benutzerverwaltung (Spalte bleibt, wird nicht mehr geschrieben – den
# Vertriebler-Block der Terminbestätigung prüft Agent G), (3) Sammelaktion „An
# Handelsvertreter verschieben“ mit Ziel „Simons Gruppe“: drei Leads → „3 verschoben“,
# alle bei Simon mit Kennzeichen „noch nicht verteilt“; Simon wählt Paolo → Kennzeichen
# weg, ad_id = Paolo, Aktivität „Zuständiger: Paolo Di Blasi“.
# Läuft gegen die DB-Kopie (DB_PFAD_OVERRIDE); Daten mit Präfix V33N, Parameter werden
# gesichert und zurückgesetzt.
import json
import re
import time
import unittest
from urllib.parse import unquote_plus

from fastapi.testclient import TestClient
from sqlalchemy.exc import OperationalError

from app import auth, lead_boards, lead_termin, lead_v2, rollen
from app import leadmanagement as kern
from app.db import SessionLocal, init_db
from app.main import app
from app.models import (AdProfil, Benachrichtigung, Benutzer, BenutzerEinstellung,
                        KommunikationLog, Kunde, LeadAktivitaet, LeadQuelle, Profil, Todo,
                        Vorgang, VorgangObjekt, VotTermin)

PRAEFIX = "V33N"
NACHNAME = "V33N-Kunde"
BASIS = (54.3, 7.6)          # Bezugspunkt abseits echter Leads (Nordsee)
PIN = "4321"
PARAMETER = ("hv_ausschluss", "hv_gruppe_rene", "hv_gruppe_simon", "hv_gruppe_simon_mitglieder",
             "hv_standard_benutzer", "kanal_ad_regel", "terminierung_aktiv", "lead_freigabe_modus")


def mit_wiederholung(funktion, versuche=12, pause=0.5):
    for n in range(versuche):
        try:
            return funktion()
        except OperationalError as fehler:
            if "locked" not in str(fehler).lower() or n == versuche - 1:
                raise
            time.sleep(pause * (n + 1))


def aufraeumen(s):
    s.rollback()
    for k in s.query(Kunde).filter(Kunde.nachname.like(f"{NACHNAME}%")):
        for v in s.query(Vorgang).filter_by(kunde_id=k.id):
            s.query(LeadAktivitaet).filter_by(vorgang_id=v.id).delete()
            s.query(KommunikationLog).filter_by(vorgang_id=v.id).delete()
            s.query(VotTermin).filter_by(vorgang_id=v.id).delete()
            s.query(VorgangObjekt).filter_by(vorgang_id=v.id).delete()
            s.query(Todo).filter_by(vorgang_id=v.id).delete()
            s.query(Benachrichtigung).filter(
                Benachrichtigung.link == f"/lead-management/lead/{v.id}").delete()
            s.delete(v)
        s.delete(k)
    for b in s.query(Benutzer).filter(Benutzer.name.like(f"{PRAEFIX}%")):
        s.query(AdProfil).filter_by(benutzer_id=b.id).delete()
        s.query(BenutzerEinstellung).filter_by(benutzer_id=b.id).delete()
        s.query(Benachrichtigung).filter_by(benutzer_id=b.id).delete()
        s.query(VotTermin).filter_by(ad_id=b.id).delete()
        lead_termin.kanal_regel_ad_setzen(s, b.id, [])
        s.delete(b)
    s.commit()


class Basis(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        init_db()
        cls.s = SessionLocal()
        mit_wiederholung(lambda: aufraeumen(cls.s))
        rollen.migration_v33_rollen(cls.s)
        cls.s.commit()
        rollen.cache_leeren()
        cls.gesichert = {n: kern.parameter_holen(cls.s, n, "") for n in PARAMETER}
        # Angebotsprofil SWD (v9) – auf der Entwicklungs-DB vorhanden; fehlt es, wird eines
        # mit regel_kennung swd angelegt und am Ende wieder entfernt
        cls.swd_profil_neu = None
        if cls.s.query(Profil).filter(Profil.regel_kennung == "swd").first() is None:
            cls.swd_profil_neu = Profil(name=f"{PRAEFIX} SWD", regel_kennung="swd", kanalwerte="")
            cls.s.add(cls.swd_profil_neu)
            cls.s.commit()

        def _vorbereiten():
            cls.admin_benutzer = cls.s.get(Benutzer, 1)
            cls.horst = cls.ad("Horst")                      # angestellter AD, Kanal-Regel SWD
            cls.rudi = cls.ad("Rudi")                        # angestellter AD ohne Regel
            cls.rene = cls.ad("Rene Golaschewski", hv=True)
            cls.simon = cls.ad("Simon O Grady", hv=True)
            cls.paolo = cls.ad("Paolo Di Blasi", hv=True)
            kern.parameter_setzen(cls.s, "lead_freigabe_modus", "alle")
            kern.parameter_setzen(cls.s, "kanal_ad_regel", "")
            kern.parameter_setzen(cls.s, "hv_ausschluss",
                                  "Empfehlung; Messe; Sparkasse Duisburg; Stadtwerke Düsseldorf; SWD; Enni")
            kern.parameter_setzen(cls.s, "hv_gruppe_rene", str(cls.rene.id))
            kern.parameter_setzen(cls.s, "hv_gruppe_simon", f"{cls.simon.id},{cls.paolo.id}")
            kern.parameter_setzen(cls.s, "hv_gruppe_simon_mitglieder", str(cls.paolo.id))
            kern.parameter_setzen(cls.s, "hv_standard_benutzer", str(cls.simon.id))
            kern.parameter_setzen(cls.s, "terminierung_aktiv", "an")
            cls.s.commit()
        mit_wiederholung(_vorbereiten)
        cls.admin = cls.client(1)
        lead_termin.vorschlaege_cache_leeren()

    @classmethod
    def tearDownClass(cls):
        def _zurueck():
            aufraeumen(cls.s)
            for n, w in cls.gesichert.items():
                kern.parameter_setzen(cls.s, n, w)
            if cls.swd_profil_neu is not None:
                p = cls.s.get(Profil, cls.swd_profil_neu.id)
                if p is not None:
                    cls.s.delete(p)
            cls.s.commit()
        try:
            mit_wiederholung(_zurueck)
        finally:
            lead_termin.vorschlaege_cache_leeren()
            cls.s.close()

    # --- Helfer -----------------------------------------------------------------------

    @classmethod
    def ad(cls, name, hv=False):
        b = Benutzer(name=f"{PRAEFIX} {name}", rolle="handelsvertreter" if hv else "aussendienst",
                     aktiv=True, email=f"{name.lower().replace(' ', '')}@v33n.local",
                     telefon="0203 1", pin_hash=auth.pin_hash(PIN))
        cls.s.add(b)
        cls.s.flush()
        cls.s.add(AdProfil(
            benutzer_id=b.id, start_adresse="Duisburg", start_lat=BASIS[0], start_lon=BASIS[1],
            arbeitszeiten=json.dumps({t: ["08:00", "18:00"] for t in ("mo", "di", "mi", "do", "fr")}),
            termin_dauer_min=90, puffer_min=30, max_termine_tag=3, gebiet_plz_praefixe="[]",
            aktiv_terminierung=True, terminiert_selbst=hv, kompetenz_sparten=json.dumps([]),
            kompetenz_kombi=False, kompetenz_mfh=False, kompetenz_gewerbe=False))
        cls.s.flush()
        return b

    @staticmethod
    def client(benutzer_id):
        c = TestClient(app)
        c.cookies.set(auth.COOKIE_NAME, auth.cookie_wert(benutzer_id))
        return c

    def setUp(self):
        self.sync()

    def sync(self):
        """WAL-Lese-Schnappschuss der Testsitzung beenden (v33 Phase 172, BEGIN IMMEDIATE)
        und die Identitätskarte leeren (expire_on_commit=False): nach Schreibzugriffen über
        den TestClient vor dem nächsten Lesen/Schreiben mit self.s – alle eigenen
        Schreibzugriffe sind zu diesem Zeitpunkt committet."""
        self.s.rollback()
        self.s.expire_all()

    def lead(self, nr, kanal=None, ad_id=None):
        self.sync()
        quelle = self.s.query(LeadQuelle).filter_by(key="website").first()
        daten = {"anrede": "Herr", "vorname": f"V{nr}", "nachname": f"{NACHNAME}-{nr}",
                 "plz": "47139", "ort": "Duisburg", "telefon": f"0203 77{nr:04d}",
                 "sparten": ["WP"], "strasse": "Teststraße 1", "email": f"v33n-{nr}@test.local"}
        vorgang, _ = kern.lead_anlegen(self.s, daten, quelle, "api", entscheidung="neu")
        kunde = self.s.get(Kunde, vorgang.kunde_id)
        kunde.objektart = "EFH"
        if kanal is not None:
            kunde.vertriebskanal = kanal
        vorgang.demo = True
        vorgang.lead_phase = "neu"
        vorgang.naechste_aktion_am = None
        vorgang.leadmanager_id = None
        vorgang.ad_id = ad_id
        vorgang.lat, vorgang.lon, vorgang.geocode_status = BASIS[0], BASIS[1], "ok"
        self.s.commit()
        return vorgang

    def frisch(self, vorgang):
        self.sync()
        return self.s.get(Vorgang, vorgang.id)

    def aktivitaeten(self, vorgang):
        self.sync()
        return [(a.typ, a.ergebnis, a.text) for a in
                self.s.query(LeadAktivitaet).filter_by(vorgang_id=vorgang.id).order_by(LeadAktivitaet.id)]


# --- (1) Kanal-Regel „Stadtwerke Düsseldorf“ -----------------------------------------------

class A_KanalSWD(Basis):
    def test_kanalwerte_und_aliase(self):
        werte = kern.kanal_werte(self.s)
        self.assertIn("Stadtwerke Düsseldorf", werte)
        self.assertNotIn("SWD", werte)
        self.assertEqual(kern.kanal_anzeige("SWD"), "Stadtwerke Düsseldorf")
        self.assertEqual(kern.kanal_anzeige("stadtwerke düsseldorf"), "Stadtwerke Düsseldorf")
        self.assertEqual(kern.kanal_anzeige("Enni"), "Enni")
        self.assertEqual(kern.kanal_schluessel("SWD"), "stadtwerke düsseldorf")
        self.assertEqual(kern.kanal_aliase("Stadtwerke Düsseldorf"), ["Stadtwerke Düsseldorf", "SWD"])
        self.assertEqual(kern.kanal_aliase("swd"), ["Stadtwerke Düsseldorf", "SWD"])
        self.assertEqual(kern.kanal_aliase("Enni"), ["Enni"])
        self.assertTrue(kern.kanal_gleich("SWD", "Stadtwerke Düsseldorf"))
        self.assertFalse(kern.kanal_gleich("SWD", "Enni"))
        # AD-Profil bietet den Kanal wie Enni; der CSV-Import kennt beide Schreibweisen
        seite = self.admin.get(f"/benutzer/{self.horst.id}/ad-profil").text
        self.assertIn('name="kanal_fest" value="Stadtwerke Düsseldorf"', seite)
        from app import benutzer_import
        zeilen, _ = benutzer_import.csv_lesen("Name;Rolle;E-Mail;Team;Vertriebskanal\n"
                                              f"{PRAEFIX} Import SWD;Außendienst;swd@v33n.local;;SWD\n")
        zeilen = benutzer_import.pruefen(self.s, zeilen)
        self.assertEqual(zeilen[0].fehler, [])
        self.assertEqual(zeilen[0].kanal, "Stadtwerke Düsseldorf")

    def test_regel_nur_und_ausser_im_terminassistenten(self):
        # Horst: Kanal-Regel „nur Stadtwerke Düsseldorf“ über das AD-Profil (Häkchen Kanal)
        daten = {"start_adresse": "Duisburg", "termin_dauer_min": "90", "puffer_min": "30",
                 "max_termine_tag": "3", "gebiet": "", "aktiv_terminierung": "on",
                 "mo_von": "08:00", "mo_bis": "18:00", "di_von": "08:00", "di_bis": "18:00",
                 "mi_von": "08:00", "mi_bis": "18:00", "do_von": "08:00", "do_bis": "18:00",
                 "fr_von": "08:00", "fr_bis": "18:00", "kanal_fest": "Stadtwerke Düsseldorf"}
        r = self.admin.post(f"/benutzer/{self.horst.id}/ad-profil", data=daten, follow_redirects=False)
        self.assertEqual(r.status_code, 303, r.text)
        self.sync()
        regel = lead_termin.kanal_regel_fuer_ad(self.s, self.horst.id)
        self.assertIn("stadtwerke düsseldorf", regel)
        self.assertIn("swd", regel)                     # monday-Schreibweise mit hinterlegt
        seite = self.admin.get(f"/benutzer/{self.horst.id}/ad-profil").text
        self.assertRegex(seite, r'name="kanal_fest" value="Stadtwerke Düsseldorf"\s+checked')
        try:
            for kanal in ("SWD", "Stadtwerke Düsseldorf"):
                v = self.lead(10 if kanal == "SWD" else 11, kanal=kanal)
                ergebnis = lead_termin.kandidaten(self.s, v, benutzer=self.admin_benutzer)
                namen = {k["ad"].name for k in ergebnis["kandidaten"]}
                self.assertEqual(namen, {self.horst.name}, kanal)        # „nur“: einziger Kandidat
                gruende = {a["ad"].name: a["grund"] for a in ergebnis["ausgeschlossen"]}
                self.assertIn(self.rudi.name, gruende)                    # „außer“: Rudi nie bei SWD
                self.assertIn("nur", gruende[self.rudi.name])
                self.assertIn(self.horst.name, gruende[self.rudi.name])
            # Enni-Lead und Lead ohne Kanal: beide angestellten AD
            for nr, kanal in ((12, "Enni"), (13, None)):
                v = self.lead(nr, kanal=kanal)
                ergebnis = lead_termin.kandidaten(self.s, v, benutzer=self.admin_benutzer)
                namen = {k["ad"].name for k in ergebnis["kandidaten"]}
                self.assertTrue({self.horst.name, self.rudi.name} <= namen, (kanal, namen))
        finally:
            self.sync()
            lead_termin.kanal_regel_ad_setzen(self.s, self.horst.id, [])
            self.s.commit()

    def test_sammelaktion_ueberspringt_swd(self):
        swd = self.lead(14, kanal="SWD")
        lang = self.lead(15, kanal="Stadtwerke Düsseldorf")
        frei = self.lead(16)
        r = self.admin.post("/lead-management/boards/sammelaktion",
                            data={"board": "hauptboard", "aktion": "hv_verschieben", "ziel": "simon",
                                  "ids": [str(swd.id), str(lang.id), str(frei.id)]}, follow_redirects=False)
        self.assertEqual(r.status_code, 303, r.text)
        meldung = unquote_plus(r.headers["location"].split("meldung=", 1)[1])
        self.assertIn("1 verschoben, 2 übersprungen: Kanal Stadtwerke Düsseldorf", meldung)
        self.assertIsNone(self.frisch(swd).ad_id)
        self.assertIsNone(self.frisch(lang).ad_id)
        self.assertEqual(self.frisch(frei).ad_id, self.simon.id)
        self.assertIn("Stadtwerke Düsseldorf", lead_v2.hv_ausgeschlossen(self.s, swd))
        self.assertEqual(lead_v2.hv_ausgeschlossen(self.s, frei), "")


# --- (2) Infotext entfällt -----------------------------------------------------------------

class B_Infotext(Basis):
    def test_kein_infotext_in_profil_und_benutzerliste(self):
        self.horst.infotext = "Alter Infotext aus v29"
        self.s.commit()
        seite = self.admin.get(f"/benutzer/{self.horst.id}/ad-profil").text
        self.assertNotIn('name="infotext"', seite)
        self.assertNotIn("Alter Infotext aus v29", seite)
        liste = self.admin.get("/benutzer").text
        self.assertNotIn('name="infotext"', liste)
        self.assertNotIn("Alter Infotext aus v29", liste)
        # Formulare schreiben die Spalte nicht mehr (auch wenn ein Altformular sie mitschickt)
        daten = {"start_adresse": "Duisburg", "termin_dauer_min": "90", "puffer_min": "30",
                 "max_termine_tag": "3", "gebiet": "", "vorname": "Horst", "infotext": "Neuer Text"}
        r = self.admin.post(f"/benutzer/{self.horst.id}/ad-profil", data=daten, follow_redirects=False)
        self.assertEqual(r.status_code, 303)
        r = self.admin.post(f"/benutzer/{self.horst.id}/aendern",
                            data={"name": self.horst.name, "rolle": "aussendienst", "email": self.horst.email,
                                  "aktiv": "on", "infotext": "Neuer Text 2"}, follow_redirects=False)
        self.assertEqual(r.status_code, 303)
        self.sync()
        self.assertEqual(self.s.get(Benutzer, self.horst.id).infotext, "Alter Infotext aus v29")
        self.assertEqual(self.s.get(Benutzer, self.horst.id).vorname, "Horst")


# --- (3) „Simons Gruppe“ -------------------------------------------------------------------

class C_SimonsGruppe(Basis):
    def test_drei_leads_an_simons_gruppe_und_verteilung(self):
        a, b, c = self.lead(20), self.lead(21, ad_id=self.horst.id), self.lead(22, ad_id=self.rene.id)
        board = self.admin.get("/lead-management/hauptboard").text
        self.assertIn('id="lm-sammel-hv"', board)
        self.assertEqual(re.findall(r'data-ziel="([^"]+)"', board), ["rene", "simon"])
        self.assertIn("Simons Gruppe", board)
        self.assertNotIn("verteilt an sein Team", board)
        wahl = lead_v2.hv_gruppen_wahl(self.s)
        self.assertEqual([w["name"] for w in wahl], [self.rene.name, "Simons Gruppe"])
        self.assertEqual(wahl[1]["ziel_name"], self.simon.name)
        r = self.admin.post("/lead-management/boards/sammelaktion",
                            data={"board": "hauptboard", "aktion": "hv_verschieben", "ziel": "simon",
                                  "ids": [str(a.id), str(b.id), str(c.id)]}, follow_redirects=False)
        self.assertEqual(r.status_code, 303, r.text)
        meldung = unquote_plus(r.headers["location"].split("meldung=", 1)[1])
        self.assertIn("3 verschoben", meldung)
        self.assertIn("Ziel Simons Gruppe", meldung)
        for v in (a, b, c):
            self.assertEqual(self.frisch(v).ad_id, self.simon.id, v.id)
            self.assertTrue(lead_v2.hv_gruppe_offen(self.s, self.frisch(v)), v.id)
            texte = [t for _, _, t in self.aktivitaeten(v)]
            self.assertIn("An Simons Gruppe verschoben – noch nicht verteilt", texte)
        self.assertEqual(lead_v2.hv_gruppe_offen_ids(self.s, [self.frisch(a), self.frisch(b), self.frisch(c)]),
                         {a.id, b.id, c.id})
        # Kennzeichen in HV-Ansicht (Gesamtsicht und Simons Sicht) und Kartei
        hv_seite = self.admin.get("/lead-management/handelsvertreter?gruppe=simon").text
        for v in (a, b, c):
            self.assertIn(f'data-hv-gruppe-offen="{v.id}"', hv_seite)
        simon_client = self.client(self.simon.id)
        meine = simon_client.get("/lead-management/handelsvertreter").text
        self.assertIn(f'data-hv-gruppe-offen="{a.id}"', meine)
        kartei = simon_client.get(f"/lead-management/lead/{a.id}").text
        self.assertIn('data-rolle="hv-gruppe-badge"', kartei)
        self.assertIn("Simons Gruppe (noch nicht verteilt)", kartei)
        # Zuständigen-Dropdown zeigt nur die Gruppe (Simon + Paolo), kein angestellter AD
        auswahl = kartei.split('name="ad_id"', 1)[1].split("</select>", 1)[0]
        self.assertIn(f'value="{self.paolo.id}"', auswahl)
        self.assertIn(f'value="{self.simon.id}"', auswahl)
        self.assertNotIn(f'value="{self.horst.id}"', auswahl)
        self.assertNotIn(f'value="{self.rene.id}"', auswahl)
        # Simon wählt Paolo → Kennzeichen weg, ad_id = Paolo, Aktivität „Zuständiger: Paolo Di Blasi“
        r = simon_client.post(f"/lead-management/lead/{a.id}/feld",
                              json={"feld": "ad_id", "wert": str(self.paolo.id)})
        self.assertEqual(r.status_code, 200, r.text)
        self.assertTrue(r.json()["ok"])
        self.assertEqual(self.frisch(a).ad_id, self.paolo.id)
        self.assertFalse(lead_v2.hv_gruppe_offen(self.s, self.frisch(a)))
        texte = [t for _, _, t in self.aktivitaeten(a)]
        self.assertIn(f"Zuständiger: {self.paolo.name}", texte)
        self.assertTrue(any(t.startswith(f"Zugewiesen an {self.paolo.name}") for t in texte), texte)
        marker = [erg for typ, erg, _ in self.aktivitaeten(a) if typ == lead_v2.HV_GRUPPE_MARKER]
        self.assertEqual(marker, ["verteilt"])
        kartei = simon_client.get(f"/lead-management/lead/{a.id}").text
        self.assertNotIn('data-rolle="hv-gruppe-badge"', kartei)
        hv_seite = self.admin.get("/lead-management/handelsvertreter?gruppe=simon").text
        self.assertNotIn(f'data-hv-gruppe-offen="{a.id}"', hv_seite)
        self.assertIn(f'data-hv-gruppe-offen="{b.id}"', hv_seite)
        # Simon wählt sich selbst → er behält den Lead, Kennzeichen weg [ANNAHME]
        r = simon_client.post(f"/lead-management/lead/{b.id}/feld",
                              json={"feld": "ad_id", "wert": str(self.simon.id)})
        self.assertEqual(r.status_code, 200, r.text)
        self.assertIn("behält den Lead", r.json()["meldung"])
        self.assertEqual(self.frisch(b).ad_id, self.simon.id)
        self.assertFalse(lead_v2.hv_gruppe_offen(self.s, self.frisch(b)))
        # Innendienst verteilt über die HV-Ansicht (Dropdown „Vertreter“) → ebenfalls aufgelöst
        r = self.admin.post(f"/lead-management/handelsvertreter/{c.id}/zuweisen",
                            data={"ad_id": str(self.paolo.id), "zurueck": "/lead-management/handelsvertreter"},
                            follow_redirects=False)
        self.assertEqual(r.status_code, 303, r.text)
        self.assertEqual(self.frisch(c).ad_id, self.paolo.id)
        self.assertFalse(lead_v2.hv_gruppe_offen(self.s, self.frisch(c)))
        # erneut an Simons Gruppe: Lead liegt bereits bei Simon → Kennzeichen wird gesetzt
        self.sync()
        ok, text = lead_boards.sammelaktion_ausfuehren(self.s, self.admin_benutzer, "hauptboard",
                                                       "hv_verschieben", [b.id], {"ziel": "simon"})
        self.assertTrue(ok, text)
        self.assertIn("1 verschoben", text)
        self.s.commit()
        self.assertTrue(lead_v2.hv_gruppe_offen(self.s, self.frisch(b)))
        # Ziel René: kein Kennzeichen, bestehendes wird aufgelöst
        ok, text = lead_boards.sammelaktion_ausfuehren(self.s, self.admin_benutzer, "hauptboard",
                                                       "hv_verschieben", [b.id], {"ziel": "rene"})
        self.assertTrue(ok, text)
        self.assertIn(f"Ziel {self.rene.name}", text)
        self.s.commit()
        self.assertEqual(self.frisch(b).ad_id, self.rene.id)
        self.assertFalse(lead_v2.hv_gruppe_offen(self.s, self.frisch(b)))

    def test_gruppenlogik_mit_rolle_handelsvertreter(self):
        """Mit der Rolle Handelsvertreter (Phase 167) bleibt die Gruppenlogik unverändert –
        auch ohne Profil-Kennzeichen zählt die Rolle."""
        from app import lead_dropdowns
        self.sync()
        for b in (self.rene, self.simon, self.paolo):
            self.assertEqual(self.s.get(Benutzer, b.id).rolle, "handelsvertreter")
        profil = self.s.query(AdProfil).filter_by(benutzer_id=self.paolo.id).first()
        profil.terminiert_selbst = False          # nur noch die Rolle trägt das Kennzeichen
        self.s.commit()
        try:
            self.assertIn(self.paolo.id, lead_dropdowns._hv_ids(self.s))
            self.assertIn(self.paolo.id, lead_v2.handelsvertreter_ids(self.s))
            self.assertEqual(lead_dropdowns.hv_gruppe_fuer(self.s, self.paolo.id), "simon")
            v = self.lead(30, ad_id=self.simon.id)
            ids = [i for i, _ in lead_dropdowns.ad_auswahl(self.s, v)]
            self.assertEqual(ids, [self.simon.id, self.paolo.id])
            self.assertNotIn(self.paolo.id, [b.id for b in lead_dropdowns.angestellte_ad(self.s)])
        finally:
            self.sync()
            profil = self.s.query(AdProfil).filter_by(benutzer_id=self.paolo.id).first()
            profil.terminiert_selbst = True
            self.s.commit()


if __name__ == "__main__":
    unittest.main()
