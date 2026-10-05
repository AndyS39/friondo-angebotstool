# Tests PLAN_LEAD_V2 Phase 105 (CLAUDE v23): Icon-Leiste, Hauptboard, Board
# Terminiert, Kanban je Board, Inline-Bearbeitung (JSON), Sammelaktionen,
# Spaltenkonfiguration je Nutzer, Reiter Kontaktiert mit Rufnummernsuche,
# E-Mail-Vorlagen im Modul, Demo-/Handelsvertreter-Gate.
# Laufen im Demo-Modus gegen die Entwicklungs-DB; Testleads tragen den
# Nachnamen „LeadV2B-Test“, Testbenutzer das Präfix „LeadV2B “ – alles wird
# aufgeräumt.
import json
import unittest
import warnings
from datetime import datetime, timedelta

warnings.filterwarnings("ignore")

from fastapi.testclient import TestClient
from sqlalchemy import text

from app import auth, lead_boards, lead_v2
from app import leadmanagement as kern
from app.db import SessionLocal, init_db
from app.main import app
from app.models import (AdProfil, Angebot, AngebotsNotiz, Benutzer, BenutzerEinstellung,
                        KommunikationLog, Kunde, LeadAktivitaet, LeadQuelle, Vorgang,
                        VotTermin, LEAD_PHASEN, einstellung_holen, einstellung_setzen)

NACHNAME = "LeadV2B-Test"


def mit_wiederholung(funktion, versuche=12, pause=0.5):
    """SQLite kennt nur einen Schreiber: laufen andere Tests/Agenten parallel
    gegen die Entwicklungs-DB, kommt „database is locked“ – kurz warten und
    erneut versuchen statt mit Fehler abzubrechen."""
    import time
    from sqlalchemy.exc import OperationalError
    for n in range(versuche):
        try:
            return funktion()
        except OperationalError as fehler:
            if "locked" not in str(fehler).lower() or n == versuche - 1:
                raise
            time.sleep(pause * (n + 1))


def aufraeumen(s):
    for k in s.query(Kunde).filter(Kunde.nachname.like(f"{NACHNAME}%")):
        for v in s.query(Vorgang).filter_by(kunde_id=k.id):
            s.query(LeadAktivitaet).filter_by(vorgang_id=v.id).delete()
            s.query(KommunikationLog).filter_by(vorgang_id=v.id).delete()
            s.query(VotTermin).filter_by(vorgang_id=v.id).delete()
            for a in s.query(Angebot).filter_by(vorgang_id=v.id):
                s.query(AngebotsNotiz).filter_by(angebot_id=a.id).delete()
                s.delete(a)
            s.delete(v)
        s.delete(k)
    for b in s.query(Benutzer).filter(Benutzer.name.like("LeadV2B %")):
        s.query(AdProfil).filter_by(benutzer_id=b.id).delete()
        s.query(BenutzerEinstellung).filter_by(benutzer_id=b.id).delete()
        s.delete(b)
    s.commit()


class Basis(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        init_db()
        cls.s = SessionLocal()

        def _aufraeumen():
            cls.s.rollback()
            aufraeumen(cls.s)
        mit_wiederholung(_aufraeumen)
        cls.client = TestClient(app)
        cls.client.post("/login", data={"benutzer_id": "1", "pin": "1234"})
        cls.modus = kern.parameter_holen(cls.s, "lead_freigabe_modus", "admin")

        def _anlegen():
            cls.s.rollback()
            kern.parameter_setzen(cls.s, "lead_freigabe_modus", "admin")
            # Testbenutzer: Handelsvertreter (AD + terminiert_selbst) und Innendienst
            cls.hv = Benutzer(name="LeadV2B HV", rolle="aussendienst", aktiv=True,
                              pin_hash=auth.pin_hash("1234"))
            cls.innen = Benutzer(name="LeadV2B Innen", rolle="innendienst", aktiv=True,
                                 pin_hash=auth.pin_hash("1234"))
            cls.s.add_all([cls.hv, cls.innen])
            cls.s.flush()
            cls.s.add(AdProfil(benutzer_id=cls.hv.id, terminiert_selbst=True, aktiv_terminierung=True))
            cls.s.commit()
        mit_wiederholung(_anlegen)

    @classmethod
    def tearDownClass(cls):
        def _aufraeumen():
            cls.s.rollback()
            aufraeumen(cls.s)
            kern.parameter_setzen(cls.s, "lead_freigabe_modus", cls.modus)
            cls.s.commit()
        try:
            mit_wiederholung(_aufraeumen)
        finally:
            cls.s.close()

    def lead(self, nr, phase="neu", **extra):
        quelle = self.s.query(LeadQuelle).filter_by(key="website").first()
        daten = {"vorname": f"V{nr}", "nachname": f"{NACHNAME}-{nr}", "plz": "47139",
                 "ort": "Duisburg", "telefon": f"0203 77{nr:04d}", "sparten": ["WP"],
                 "email": f"v2b{nr}@test.local"}
        vorgang, _ = kern.lead_anlegen(self.s, daten, quelle, "api", entscheidung="neu")
        vorgang.demo = True
        vorgang.lead_phase = phase
        for k, v in extra.items():
            setattr(vorgang, k, v)
        self.s.commit()
        return vorgang

    def termin(self, vorgang, typ="vot", status="geplant", tage=3):
        t = VotTermin(vorgang_id=vorgang.id, ad_id=4, beginn=datetime.now() + timedelta(days=tage),
                      ende=datetime.now() + timedelta(days=tage, hours=1), status=status,
                      typ=typ, medium={"vot": "vor_ort", "telefon": "telefon", "online": "teams"}[typ],
                      demo=True)
        self.s.add(t)
        self.s.commit()
        return t

    def zeile(self, vorgang):
        return lead_boards.zeile_fuer(self.s, self.s.get(Benutzer, 1), vorgang)

    def json_post(self, url, daten):
        return self.client.post(url, json=daten, headers={"Accept": "application/json"})


class Seiten(Basis):
    def test_boards_rendern_mit_leiste(self):
        for pfad in ("/lead-management/hauptboard", "/lead-management/terminiert",
                     "/lead-management/kontaktiert", "/lead-management/vorlagen",
                     "/lead-management/board?board=terminiert", "/lead-management/board"):
            r = self.client.get(pfad)
            self.assertEqual(r.status_code, 200, pfad)
            seite = r.text
            self.assertIn('class="lm-leiste"', seite, pfad)
            # v25 (PLAN_LEAD_V3 Phase 118): Hauptleiste Mein Dashboard · Hauptboard ·
            # Deals · Kontaktiert · Karte · Infoabend · To-Dos · Handelsvertreter;
            # E-Mail-Vorlagen stehen jetzt unter „Mehr …“ (vorher: Terminiert,
            # Info-Veranstaltung und E-Mail-Vorlagen als Hauptleisten-Einträge).
            for name in ("Mein Dashboard", "Hauptboard", "Deals", "Kontaktiert", "Karte",
                         "Infoabend", "To-Dos", "Handelsvertreter"):
                self.assertIn(f'aria-label="{name}"', seite, pfad)
            self.assertNotIn('aria-label="Terminiert"', seite, pfad)
            # (die Quelle „Info-Veranstaltung“ darf als Datensatz weiter so heißen – nur die Leiste prüft)
            self.assertNotIn("Info-Veranstaltung", seite.split('<nav class="lm-leiste"', 1)[1].split("</nav>", 1)[0], pfad)
            self.assertIn('aria-label="Mehr"', seite, pfad)
            self.assertIn("/lead-management/vorlagen", seite, pfad)
            self.assertIn("/lead-management/handelsvertreter", seite, pfad)
            self.assertIn("/static/lm_boards.js", seite, pfad)
        # Demo-Badge zentral in der Leiste (Parametertext im Tooltip)
        seite = self.client.get("/lead-management/hauptboard").text
        self.assertIn("lm-leiste-demo", seite)
        self.assertIn(kern.parameter_holen(self.s, "demo_badge_text", ""), seite)
        # Umschalter Tabelle | Anrufliste | Kanban
        self.assertIn('class="lm-umschalter"', seite)
        self.assertIn("/lead-management/anrufliste", seite)
        self.assertIn("/lead-management/board?board=hauptboard", seite)
        # bestehende Seiten laufen automatisch über die neue Leiste
        alt = self.client.get("/lead-management/anrufliste?meine=0").text
        self.assertIn('class="lm-leiste"', alt)
        self.assertIn('data-key="hauptboard"', alt)

    def test_kanban_nur_aktives_board(self):
        haupt = self.client.get("/lead-management/board?board=hauptboard").text
        self.assertIn('data-phase="neu"', haupt)
        self.assertNotIn('data-phase="terminiert"', haupt)
        self.assertNotIn('data-phase="verloren"', haupt)
        term = self.client.get("/lead-management/board?board=terminiert").text
        self.assertIn('data-phase="terminiert"', term)
        self.assertIn('data-phase="verloren"', term)
        self.assertNotIn('data-phase="neu"', term)


class Gruppen(Basis):
    def test_zuordnung_alle_phasen(self):
        tabelle = {z["phase"]: (z["board"], z["gruppe"]) for z in lead_boards.zuordnung_tabelle()}
        self.assertEqual(set(tabelle), set(LEAD_PHASEN))
        self.assertEqual(tabelle["neu"], ("hauptboard", "neu"))
        self.assertEqual(tabelle["in_kontaktierung"], ("hauptboard", "neu"))
        self.assertEqual(tabelle["qualifiziert"], ("hauptboard", "neu"))
        self.assertEqual(tabelle["zurueckgestellt"], ("hauptboard", "pausiert"))
        self.assertEqual(tabelle["nicht_erreicht"], ("hauptboard", "disqualifiziert"))
        self.assertEqual(tabelle["unqualifiziert"], ("hauptboard", "disqualifiziert"))
        self.assertEqual(tabelle["terminiert"], ("terminiert", "angebotserstellung"))
        self.assertEqual(tabelle["erfasst"], ("terminiert", "angebotserstellung"))
        self.assertEqual(tabelle["angebot"], ("terminiert", "angebotsversand"))
        self.assertEqual(tabelle["gewonnen"], ("terminiert", "gewonnen"))
        self.assertEqual(tabelle["verloren"], ("terminiert", "verloren"))

    def test_gruppen_der_boards(self):
        jetzt = datetime.now()
        neu = self.lead(101)
        pausiert = self.lead(102, "zurueckgestellt", zurueckgestellt_bis=jetzt + timedelta(days=5),
                             zurueckgestellt_grund="Kunde meldet sich selbst")
        disq = self.lead(103, "unqualifiziert", unqualifiziert_grund="Doppelter")
        nicht = self.lead(104, "nicht_erreicht")
        termin = self.lead(105, "terminiert")
        self.termin(termin)
        angebot = self.lead(106, "angebot")
        gewonnen = self.lead(107, "gewonnen")
        verloren = self.lead(108, "verloren")          # nie ein VOT → „vor Termin“
        qual_mit_termin = self.lead(109, "qualifiziert")
        self.termin(qual_mit_termin)                   # aktiver VOT zieht ins Board Terminiert
        telefon = self.lead(110, "qualifiziert")
        self.termin(telefon, typ="telefon")            # Vorab-Gespräch: bleibt in Neu, Label
        admin = self.s.get(Benutzer, 1)
        haupt = lead_boards.board_zeilen(self.s, admin, "hauptboard", {})
        term = lead_boards.board_zeilen(self.s, admin, "terminiert", {})
        gh = {g["key"]: {z["vorgang"].id: z for z in g["zeilen"]} for g in haupt["gruppen"]}
        gt = {g["key"]: {z["vorgang"].id: z for z in g["zeilen"]} for g in term["gruppen"]}
        self.assertEqual([g["key"] for g in haupt["gruppen"]], ["neu", "pausiert", "disqualifiziert"])
        self.assertEqual([g["key"] for g in term["gruppen"]],
                         ["angebotserstellung", "angebotsversand", "gewonnen", "verloren"])
        self.assertIn(neu.id, gh["neu"])
        self.assertIn(telefon.id, gh["neu"])
        self.assertTrue(gh["neu"][telefon.id]["telefongespraech"])
        self.assertIn(pausiert.id, gh["pausiert"])
        self.assertIn(disq.id, gh["disqualifiziert"])
        self.assertIn(nicht.id, gh["disqualifiziert"])
        self.assertNotIn(qual_mit_termin.id, gh["neu"])
        self.assertIn(qual_mit_termin.id, gt["angebotserstellung"])
        self.assertIn(termin.id, gt["angebotserstellung"])
        self.assertIn(angebot.id, gt["angebotsversand"])
        self.assertIn(gewonnen.id, gt["gewonnen"])
        self.assertIn(verloren.id, gt["verloren"])
        self.assertTrue(gt["verloren"][verloren.id]["vor_termin"])
        # Status-Label + Farbe aus dem Blatt Status
        self.assertEqual(gh["pausiert"][pausiert.id]["status_label"], "Zurückgestellt")
        self.assertTrue(gh["pausiert"][pausiert.id]["status_farbe"].startswith("#"))
        # Endzustände älter als 30 Tage nur mit Archiv
        alt = self.lead(111, "verloren", eingang_am=jetzt - timedelta(days=40))
        self.s.query(LeadAktivitaet).filter_by(vorgang_id=alt.id).update(
            {"zeitpunkt": jetzt - timedelta(days=40)})
        self.s.commit()
        ohne = lead_boards.board_zeilen(self.s, admin, "terminiert", {})
        mit = lead_boards.board_zeilen(self.s, admin, "terminiert", {"archiv": True})
        ids_ohne = {z["vorgang"].id for g in ohne["gruppen"] for z in g["zeilen"]}
        ids_mit = {z["vorgang"].id for g in mit["gruppen"] for z in g["zeilen"]}
        self.assertNotIn(alt.id, ids_ohne)
        self.assertIn(alt.id, ids_mit)
        # Seite zeigt die Gruppen, Labels, Avatare, Links zur Kartei
        seite = self.client.get("/lead-management/hauptboard").text
        for t in ('data-gruppe="neu"', 'data-gruppe="pausiert"', 'data-gruppe="disqualifiziert"',
                  f'/lead-management/lead/{neu.id}', "Telefongespräch", 'class="lm-status"',
                  'class="lm-wahl-alle"', 'data-feld="notiz"', 'data-feld="status"'):
            self.assertIn(t, seite, t)
        term_seite = self.client.get("/lead-management/terminiert").text
        self.assertIn("Erfassung starten", term_seite)
        self.assertIn(f"/erfassung/sparten?kunde_id={termin.kunde_id}", term_seite)
        self.assertIn("vor Termin", term_seite)


class InlineEdit(Basis):
    def test_notiz_status_wiedervorlage(self):
        v = self.lead(201)
        r = self.json_post(f"/lead-management/boards/zeile/{v.id}", {"feld": "notiz", "wert": "Rückruf abends", "board": "hauptboard"})
        self.assertEqual(r.status_code, 200)
        j = r.json()
        self.assertTrue(j["ok"])
        self.assertIn("zeile_html", j)
        self.assertIn("Rückruf abends", j["zeile_html"])
        self.s.expire_all()
        self.assertEqual(self.s.get(Kunde, v.kunde_id).notizen, "Rückruf abends")
        # Zurückgestellt ohne Datum → Fehler, mit Datum + Grund → Gruppe Pausiert
        r = self.json_post(f"/lead-management/boards/zeile/{v.id}", {"feld": "status", "wert": "zurueckgestellt", "grund": "Bauphase später"})
        self.assertEqual(r.status_code, 422)
        self.assertFalse(r.json()["ok"])
        bis = (datetime.now() + timedelta(days=10)).strftime("%Y-%m-%d")
        r = self.json_post(f"/lead-management/boards/zeile/{v.id}", {"feld": "status", "wert": "zurueckgestellt", "grund": "Bauphase später", "bis": bis, "board": "hauptboard"})
        self.assertEqual(r.status_code, 200, r.text)
        j = r.json()
        self.assertEqual(j["gruppe"], "pausiert")
        self.s.expire_all()
        v = self.s.get(Vorgang, v.id)
        self.assertEqual(v.lead_phase, "zurueckgestellt")
        self.assertEqual(v.zurueckgestellt_bis.strftime("%Y-%m-%d"), bis)
        # „meldet sich selbst“ ohne Datum → Vorbelegung aus wv_meldet_sich_tage
        v2 = self.lead(202)
        r = self.json_post(f"/lead-management/boards/zeile/{v2.id}", {"feld": "status", "wert": "zurueckgestellt", "grund": "Kunde meldet sich selbst"})
        self.assertEqual(r.status_code, 200, r.text)
        self.s.expire_all()
        tage = int(kern.parameter_holen(self.s, "wv_meldet_sich_tage", "14"))
        self.assertEqual(self.s.get(Vorgang, v2.id).zurueckgestellt_bis.date(),
                         (datetime.now() + timedelta(days=tage)).date())
        # Sonstiges ohne Freitext → Fehler
        r = self.json_post(f"/lead-management/boards/zeile/{v2.id}", {"feld": "status", "wert": "unqualifiziert", "grund": "Sonstiges"})
        self.assertEqual(r.status_code, 422)
        # abgeleitete Phase nicht setzbar
        r = self.json_post(f"/lead-management/boards/zeile/{v2.id}", {"feld": "status", "wert": "terminiert"})
        self.assertEqual(r.status_code, 422)
        self.assertIn("abgeleitet", r.json()["meldung"])
        # Wiedervorlage
        r = self.json_post(f"/lead-management/boards/zeile/{v.id}", {"feld": "wiedervorlage", "wert": "2030-01-15"})
        self.assertTrue(r.json()["ok"], r.text)
        self.s.expire_all()
        self.assertEqual(self.s.get(Vorgang, v.id).zurueckgestellt_bis.strftime("%d.%m.%Y"), "15.01.2030")
        # Reaktivieren → Neu mit Aktivität
        r = self.json_post(f"/lead-management/boards/zeile/{v.id}", {"feld": "status", "wert": "neu", "grund_text": "Kunde hat angerufen", "board": "hauptboard"})
        self.assertEqual(r.status_code, 200, r.text)
        self.assertEqual(r.json()["gruppe"], "neu")
        texte = [a.text for a in self.s.query(LeadAktivitaet).filter_by(vorgang_id=v.id, typ="status")]
        self.assertTrue(any("Zurückgestellt → Neu" in t for t in texte), texte)

    def test_zuweisung_ad_und_innendienst(self):
        v = self.lead(203)
        # Innendienst (Leadmanager) über lead_v2.leadmanager_zuweisen
        r = self.json_post(f"/lead-management/boards/zeile/{v.id}", {"feld": "leadmanager_id", "wert": str(self.innen.id)})
        self.assertTrue(r.json()["ok"], r.text)
        self.s.expire_all()
        self.assertEqual(self.s.get(Vorgang, v.id).leadmanager_id, self.innen.id)
        # Handelsvertreter: Ausschlusskanal → deaktiviert / Fehler
        kunde = self.s.get(Kunde, v.kunde_id)
        kunde.vertriebskanal = "Enni"
        self.s.commit()
        seite = self.client.get("/lead-management/hauptboard").text
        self.assertIn("lm-hv-hinweis", seite)
        r = self.json_post(f"/lead-management/boards/zeile/{v.id}", {"feld": "ad_id", "wert": str(self.hv.id)})
        self.assertEqual(r.status_code, 422)
        self.assertIn("Innendienst", r.json()["meldung"])
        kunde.vertriebskanal = ""
        self.s.commit()
        r = self.json_post(f"/lead-management/boards/zeile/{v.id}", {"feld": "ad_id", "wert": str(self.hv.id)})
        self.assertTrue(r.json()["ok"], r.text)
        self.s.expire_all()
        self.assertEqual(self.s.get(Vorgang, v.id).ad_id, self.hv.id)
        texte = [a.text for a in self.s.query(LeadAktivitaet).filter_by(vorgang_id=v.id, typ="status")]
        self.assertTrue(any(t.startswith("Zugewiesen an LeadV2B HV") for t in texte), texte)
        # Avatar mit Initialen in der Zeile
        z = self.zeile(self.s.get(Vorgang, v.id))
        self.assertEqual(z["ad"].id, self.hv.id)
        self.assertEqual(lead_boards.initialen("LeadV2B HV"), "LH")
        self.assertEqual(lead_boards.initialen("Simon O Grady"), "SG")
        self.assertEqual(lead_boards.initialen("D. Jobelius"), "DJ")

    def test_verloren_setzt_angebote_abgelehnt(self):
        v = self.lead(204, "terminiert")
        self.termin(v)
        a1 = Angebot(nummer=f"LV2B-{v.id}-1", kunde_id=v.kunde_id, vorgang_id=v.id, status="Versendet")
        a2 = Angebot(nummer=f"LV2B-{v.id}-2", kunde_id=v.kunde_id, vorgang_id=v.id, status="Entwurf")
        a3 = Angebot(nummer=f"LV2B-{v.id}-3", kunde_id=v.kunde_id, vorgang_id=v.id, status="Angenommen",
                     archiviert=True)
        self.s.add_all([a1, a2, a3])
        self.s.commit()
        # Sonstiges ohne Freitext → Pflicht
        r = self.json_post(f"/lead-management/boards/zeile/{v.id}", {"feld": "status", "wert": "verloren", "grund": "Sonstiges"})
        self.assertEqual(r.status_code, 422)
        r = self.json_post(f"/lead-management/boards/zeile/{v.id}",
                           {"feld": "status", "wert": "verloren", "grund": "Zu teuer", "board": "terminiert"})
        self.assertEqual(r.status_code, 200, r.text)
        j = r.json()
        self.assertIn("2 Angebot(e)", j["meldung"])
        self.assertEqual(j["gruppe"], "verloren")
        self.s.expire_all()
        v = self.s.get(Vorgang, v.id)
        self.assertEqual(v.lead_phase, "verloren")
        for a in (self.s.get(Angebot, a1.id), self.s.get(Angebot, a2.id)):
            self.assertEqual(a.status, "Abgelehnt")
            self.assertEqual(a.ablehnungsgrund, "Zu teuer")
            self.assertIsNotNone(a.abgelehnt_am)
        self.assertEqual(self.s.get(Angebot, a3.id).status, "Angenommen")   # archiviert bleibt
        notizen = self.s.query(AngebotsNotiz).filter_by(angebot_id=a1.id).all()
        self.assertTrue(any("Zu teuer" in n.text for n in notizen))
        # aktiver Termin storniert (kern.lead_verloren)
        self.assertEqual({t.status for t in self.s.query(VotTermin).filter_by(vorgang_id=v.id)}, {"abgesagt"})
        # Ableitung bleibt konsistent: alle Angebote abgelehnt → verloren
        self.assertEqual(kern.lead_phase_berechnen(self.s, v), "verloren")
        z = self.zeile(v)
        self.assertEqual((z["board"], z["gruppe"]), ("terminiert", "verloren"))
        self.assertFalse(z["vor_termin"])


class Sammelaktionen(Basis):
    def test_status_aendern_schreibt_aktivitaet_je_lead(self):
        a = self.lead(301)
        b = self.lead(302)
        self.assertEqual([x["key"] for x in lead_boards.sammelaktionen_fuer("hauptboard")], ["status"])
        self.assertEqual(lead_boards.sammelaktionen_fuer("terminiert"), [])
        r = self.client.post("/lead-management/boards/sammelaktion",
                             data={"ids": [str(a.id), str(b.id)], "aktion": "status",
                                   "board": "hauptboard", "status": "qualifiziert"},
                             follow_redirects=False)
        self.assertEqual(r.status_code, 303)
        self.assertIn("/lead-management/hauptboard?meldung=", r.headers["location"])
        self.assertIn("2+von+2", r.headers["location"])
        self.s.expire_all()
        for v in (a, b):
            self.assertEqual(self.s.get(Vorgang, v.id).lead_phase, "qualifiziert")
            texte = [x.text for x in self.s.query(LeadAktivitaet).filter_by(vorgang_id=v.id, typ="status")]
            self.assertTrue(any(t.startswith("Sammelaktion – Status: Neu → Qualifiziert") for t in texte), texte)
        # Pflichtgrund gemeinsam für alle; Fehler je Lead werden gezählt
        r = self.json_post("/lead-management/boards/sammelaktion",
                           {"ids": [a.id, b.id], "aktion": "status", "board": "hauptboard",
                            "status": "unqualifiziert", "grund": "Doppelter"})
        self.assertEqual(r.status_code, 200, r.text)
        self.assertIn("2 von 2", r.json()["meldung"])
        self.s.expire_all()
        self.assertEqual(self.s.get(Vorgang, a.id).unqualifiziert_grund, "Doppelter")
        r = self.json_post("/lead-management/boards/sammelaktion",
                           {"ids": [a.id], "aktion": "status", "board": "hauptboard", "status": "terminiert"})
        self.assertEqual(r.status_code, 422)
        self.assertIn("übersprungen", r.json()["meldung"])
        # unbekannte Aktion / Board Terminiert ohne Aktionen
        r = self.json_post("/lead-management/boards/sammelaktion",
                           {"ids": [a.id], "aktion": "status", "board": "terminiert", "status": "neu"})
        self.assertEqual(r.status_code, 422)
        # Registry ist erweiterbar (Phase 111 registriert eigene Aktionen)
        lead_boards.sammelaktion_registrieren("terminiert", "test_lv2b", "Test",
                                              lambda s, vs, p, b: (len(vs), []))
        try:
            self.assertEqual(lead_boards.sammelaktionen_fuer("terminiert")[0]["key"], "test_lv2b")
        finally:
            lead_boards.SAMMELAKTIONEN["terminiert"] = []


class Spalten(Basis):
    def test_konfiguration_speichern_und_laden(self):
        alt = lead_v2.einstellung_holen(self.s, 1, lead_boards.EINSTELLUNG_KEY, None)
        try:
            r = self.json_post("/lead-management/boards/spalten",
                               {"board": "hauptboard",
                                "spalten": [{"key": "status", "sichtbar": True}, {"key": "lead", "sichtbar": True},
                                            {"key": "telefon", "sichtbar": False}, {"key": "unsinn", "sichtbar": True},
                                            {"key": "ort", "sichtbar": True}]})
            self.assertEqual(r.status_code, 200, r.text)
            keys = [sp["key"] for sp in r.json()["spalten"]]
            self.assertEqual(keys[:4], ["lead", "status", "telefon", "ort"])   # lead bleibt vorn
            self.assertEqual(len(keys), len(lead_boards.SPALTEN))             # Rest hängt hinten
            self.assertNotIn("unsinn", keys)
            r = self.client.get("/lead-management/boards/spalten?board=hauptboard")
            geladen = r.json()["spalten"]
            self.assertEqual([sp["key"] for sp in geladen][:3], ["lead", "status", "telefon"])
            self.assertFalse(next(sp for sp in geladen if sp["key"] == "telefon")["sichtbar"])
            # Seite rendert in dieser Reihenfolge, Telefon ausgeblendet
            self.lead(401)
            seite = self.client.get("/lead-management/hauptboard").text
            self.assertLess(seite.index('<th class="sp-status"'), seite.index('<th class="sp-ort"'))
            self.assertNotIn('<th class="sp-telefon"', seite)
            self.assertNotIn('class="sp-telefon"', seite.split('<tbody>', 1)[1].split('</tbody>', 1)[0])
            # Board Terminiert unabhängig konfiguriert (Spalte Erfassung / Angebot)
            t = lead_boards.spalten_fuer(self.s, 1, "terminiert")
            self.assertIn("angebot", [sp["key"] for sp in t])
            self.assertTrue(next(sp for sp in t if sp["key"] == "telefon")["sichtbar"])
            # Standard zurücksetzen
            r = self.json_post("/lead-management/boards/spalten", {"board": "hauptboard", "zuruecksetzen": True})
            self.assertEqual([sp["key"] for sp in r.json()["spalten"]], [k for k, _, _ in lead_boards.SPALTEN])
        finally:
            if alt is None:
                self.s.execute(text("DELETE FROM benutzer_einstellungen WHERE benutzer_id = 1 AND key = :k"),
                               {"k": lead_boards.EINSTELLUNG_KEY})
            else:
                lead_v2.einstellung_setzen(self.s, 1, lead_boards.EINSTELLUNG_KEY, alt)
            self.s.commit()


class Kontaktiert(Basis):
    def test_liste_und_rufnummernsuche(self):
        v = self.lead(501)                          # Telefon 0203 770501
        kern.aktivitaet(self.s, v.id, "anruf", "Anruf: Mailbox – Band besprochen",
                        benutzer=self.s.get(Benutzer, 1), ergebnis="mailbox")
        kern.aktivitaet(self.s, v.id, "anruf", "Anruf: Erreicht",
                        benutzer=self.s.get(Benutzer, 1), ergebnis="erreicht")
        self.s.commit()
        seite = self.client.get("/lead-management/kontaktiert?q=" + NACHNAME + "-501").text
        self.assertIn(f"/lead-management/lead/{v.id}", seite)
        self.assertLess(seite.index("Erreicht"), seite.index("Mailbox"))       # neueste zuerst
        self.assertIn("Band besprochen", seite)
        # Rufnummernsuche E.164 – zwei Schreibweisen, Treffer → Kartei
        for schreibweise in ("+49 203 770501", "0203-770501", "0203770501"):
            r = self.client.get("/lead-management/kontaktiert", params={"telefon": schreibweise})
            self.assertEqual(r.status_code, 200)
            self.assertIn(f"/lead-management/lead/{v.id}", r.text, schreibweise)
            self.assertIn("normalisiert +49203770501", r.text)
        treffer = lead_boards.telefon_treffer(self.s, "+49 (0) 203 / 770501".replace("(0) ", ""))
        self.assertEqual([t["vorgang"].id for t in treffer], [v.id])
        # Nummer im Suchfeld erkennt sich selbst
        self.assertIn(f"/lead-management/lead/{v.id}",
                      self.client.get("/lead-management/kontaktiert?q=0203+770501").text)
        # unbekannte Nummer → Hinweis
        self.assertIn("Kein Lead mit dieser Nummer",
                      self.client.get("/lead-management/kontaktiert?telefon=0203+0000009").text)
        d = lead_boards.kontaktiert_daten(self.s, self.s.get(Benutzer, 1), q=NACHNAME + "-501")
        self.assertEqual([z["ergebnis"] for z in d["zeilen"]], ["Erreicht", "Mailbox"])


class Vorlagen(Basis):
    def test_editor_im_modul(self):
        seite = self.client.get("/lead-management/vorlagen?vorlage=disqualifiziert").text
        self.assertIn('name="vorlage" value="disqualifiziert"', seite)
        self.assertIn("{rueckruf_telefon}", seite)
        self.assertIn('action="/lead-management/vorlagen"', seite)
        alt_b = einstellung_holen(self.s, "lead_vorlage_nurture_KL_betreff", "")
        alt_t = einstellung_holen(self.s, "lead_vorlage_nurture_KL_text", "")
        try:
            r = self.client.post("/lead-management/vorlagen",
                                 data={"vorlage": "nurture", "sparte": "KL", "betreff": "LV2B Betreff",
                                       "text": "LV2B Text"}, follow_redirects=False)
            self.assertEqual(r.status_code, 303)
            self.assertIn("Gespeichert", r.headers["location"])
            self.s.expire_all()
            self.assertEqual(einstellung_holen(self.s, "lead_vorlage_nurture_KL_betreff", ""), "LV2B Betreff")
            self.assertIn("LV2B Text", self.client.get("/lead-management/vorlagen?vorlage=nurture&sparte=KL").text)
            r = self.client.post("/lead-management/vorlagen",
                                 data={"vorlage": "nurture", "sparte": "KL", "aktion": "entfernen"},
                                 follow_redirects=False)
            self.assertIn("entfernt", r.headers["location"])
        finally:
            einstellung_setzen(self.s, "lead_vorlage_nurture_KL_betreff", alt_b)
            einstellung_setzen(self.s, "lead_vorlage_nurture_KL_text", alt_t)
            self.s.commit()
        from types import SimpleNamespace
        from app.routers import lm_boards as router
        self.assertTrue(router._vorlagen_pflege_erlaubt(SimpleNamespace(rolle="innendienst")))
        self.assertFalse(router._vorlagen_pflege_erlaubt(SimpleNamespace(rolle="leadmanagement")))


class Gate(Basis):
    def test_demo_404_und_handelsvertreter_sicht(self):
        eigen = self.lead(601, ad_id=self.hv.id)
        fremd = self.lead(602)
        # Innendienst im Demo-Modus: 404 auf allen neuen Routen
        c_innen = TestClient(app)
        c_innen.post("/login", data={"benutzer_id": str(self.innen.id), "pin": "1234"})
        for pfad in ("/lead-management/hauptboard", "/lead-management/terminiert",
                     "/lead-management/kontaktiert", "/lead-management/vorlagen",
                     "/lead-management/board", "/lead-management/boards/spalten"):
            self.assertEqual(c_innen.get(pfad).status_code, 404, pfad)
        r = c_innen.post(f"/lead-management/boards/zeile/{eigen.id}", json={"feld": "notiz", "wert": "x"})
        self.assertEqual(r.status_code, 404)
        # Handelsvertreter: nur eigene Vorgänge, keine Sammelaktionen, keine Vorlagen
        c_hv = TestClient(app)
        c_hv.post("/login", data={"benutzer_id": str(self.hv.id), "pin": "1234"})
        r = c_hv.get("/lead-management/hauptboard")
        self.assertEqual(r.status_code, 200)
        self.assertIn(f"/lead-management/lead/{eigen.id}", r.text)
        self.assertNotIn(f"/lead-management/lead/{fremd.id}", r.text)
        self.assertNotIn('id="lm-sammelform"', r.text)
        self.assertEqual(c_hv.get("/lead-management/vorlagen").status_code, 404)
        self.assertEqual(c_hv.get("/lead-management/terminiert").status_code, 200)
        self.assertEqual(c_hv.get("/lead-management/kontaktiert").status_code, 200)
        # eigener Lead bearbeitbar, fremder nicht
        r = c_hv.post(f"/lead-management/boards/zeile/{eigen.id}", json={"feld": "notiz", "wert": "HV-Notiz"})
        self.assertEqual(r.status_code, 200, r.text)
        r = c_hv.post(f"/lead-management/boards/zeile/{fremd.id}", json={"feld": "notiz", "wert": "x"})
        self.assertEqual(r.status_code, 404)
        r = c_hv.post("/lead-management/boards/sammelaktion",
                      json={"ids": [eigen.id], "aktion": "status", "board": "hauptboard", "status": "qualifiziert"},
                      headers={"Accept": "application/json"})
        self.assertEqual(r.status_code, 422)
        self.assertIn("Außendienst", r.json()["meldung"])
        # Kontaktiert: HV sieht nur Treffer eigener Leads
        self.assertIn("Kein Lead mit dieser Nummer",
                      c_hv.get("/lead-management/kontaktiert?telefon=0203+770602").text)
        self.assertIn(f"/lead-management/lead/{eigen.id}",
                      c_hv.get("/lead-management/kontaktiert?telefon=0203+770601").text)


class Pruefung(Basis):
    """Nachträge aus der Prüfung der Phase 105."""

    def test_ungueltige_ids_und_spaltenanfragen(self):
        v = self.lead(701)
        # Dropdown-Wert, der keine Zahl ist → 422 statt 500
        for feld in ("ad_id", "leadmanager_id"):
            r = self.json_post(f"/lead-management/boards/zeile/{v.id}", {"feld": feld, "wert": "abc"})
            self.assertEqual(r.status_code, 422, r.text)
            self.assertIn("Ungültige", r.json()["meldung"])
        # kaputte Spaltenanfragen setzen die Nutzerkonfiguration nicht still zurück
        alt = lead_v2.einstellung_holen(self.s, 1, lead_boards.EINSTELLUNG_KEY, None)
        try:
            r = self.json_post("/lead-management/boards/spalten",
                               {"board": "hauptboard", "spalten": [{"key": "telefon", "sichtbar": False}]})
            self.assertEqual(r.status_code, 200)
            for kaputt in (["x"], {"board": "hauptboard", "spalten": "kein-array"},
                           {"board": "hauptboard"}):
                r = self.json_post("/lead-management/boards/spalten", kaputt)
                self.assertEqual(r.status_code, 400, r.text)
            geladen = self.client.get("/lead-management/boards/spalten?board=hauptboard").json()["spalten"]
            self.assertFalse(next(sp for sp in geladen if sp["key"] == "telefon")["sichtbar"])
        finally:
            if alt is None:
                self.s.execute(text("DELETE FROM benutzer_einstellungen WHERE benutzer_id = 1 AND key = :k"),
                               {"k": lead_boards.EINSTELLUNG_KEY})
            else:
                lead_v2.einstellung_setzen(self.s, 1, lead_boards.EINSTELLUNG_KEY, alt)
            self.s.commit()

    def test_suche_teilnummer_und_sortierkoepfe(self):
        v = self.lead(702)                          # Telefon 0203 770702
        admin = self.s.get(Benutzer, 1)
        for suche in ("770 702", "0203-770702", "+49 203 770702", "203770702"):
            daten = lead_boards.board_zeilen(self.s, admin, "hauptboard", {"q": suche})
            ids = {z["vorgang"].id for g in daten["gruppen"] for z in g["zeilen"]}
            self.assertIn(v.id, ids, suche)
        daten = lead_boards.board_zeilen(self.s, admin, "hauptboard", {"q": "770 999"})
        self.assertNotIn(v.id, {z["vorgang"].id for g in daten["gruppen"] for z in g["zeilen"]})
        seite = self.client.get("/lead-management/hauptboard").text
        self.assertIn('data-sort="eingang"', seite)
        self.assertIn('class="sp-eingang" data-wert="', seite)
        self.assertNotIn("none ", seite.split('data-suche="', 1)[1].split('"', 1)[0])

    def test_terminiert_bestaetigung_erneut_knopf(self):
        v = self.lead(703, "terminiert")
        t = self.termin(v)
        seite = self.client.get("/lead-management/terminiert").text
        self.assertIn(f"/lead-management/termin/{t.id}/bestaetigung-erneut", seite)
        self.assertIn("Bestätigung erneut", seite)
        # im Hauptboard (ohne aktiven VOT) gibt es den Knopf nicht
        haupt = self.client.get("/lead-management/hauptboard").text
        self.assertNotIn("bestaetigung-erneut", haupt)
        # Zeile nach Inline-Änderung wird gezielt nachgeladen (nur dieser Vorgang)
        z = lead_boards.zeile_fuer(self.s, self.s.get(Benutzer, 1), v)
        self.assertEqual((z["board"], z["gruppe"]), ("terminiert", "angebotserstellung"))


if __name__ == "__main__":
    unittest.main()
