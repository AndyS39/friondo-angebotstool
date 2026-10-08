# Tests PLAN_LEAD_V4 Phase 142 (v29, Agent L2) – Teile (g1), (g2), (g3), (i), (j),
# (k), (l), (n) aus Phase 144:
#  (g1) Absender termin@ für alle Lead-Mails, kein Fallback: ohne Senderecht nach
#       VERSUCHE_MAX Läufen Status fehler, Vorgang mail_fehler*, Kartei-Hinweis,
#       Zähler, „Erneut senden“ → geplant, Lauf lead-mail (scheduler.ausfuehren)
#       räumt nach Freigabe auf; Testmail-Route mit geschlossener Sitzung
#  (g2) HV-Lead terminieren → keine Mail, Aktivität „Versandweg … offen“, To-Do
#       mit Vorschau (Route liefert Text + ICS); AD-Lead → Mail wie gewohnt
#  (g3) HV-Sperrzeit (nur, wenn Agent L1 den Eintragstyp gebaut hat – sonst skip)
#  (i)  Vorlagenbaum links, Terminbestätigung je Vertriebler, Versand wählt die
#       Vorlage des zugewiesenen Vertrieblers, Fallback Standard, „Rahmen für alle
#       übernehmen“ lässt individuelle Blöcke unverändert, Zulieferung einspielen
#  (j)  Sparten-Baustein {sparten_hinweise} für WP, WP+PV, GW
#  (k)  keine Nurture-Mail mehr, letzte Stufe = disqualifiziert (nach_letztem)
#  (l)  Bounce-Fixtures (Exchange DE/EN) über scheduler.ausfuehren("lead-mail-abruf")
#       → E-Mail falsch, wartet_adresse, Adressänderung gibt frei; Kundenantwort
#  (n)  14 Scheduler-Läufe inkl. lead-mail-abruf (120 s), Pool-Invariante
# Läuft gegen die DB-Kopie (DB_PFAD_OVERRIDE) im Demo-Modus; Testdaten tragen das
# Präfix „V29L2“ und werden aufgeräumt; Graph und Netz sind gemockt, kein
# Request sendet eine Mail (Ausnahme: Testmail-Route, gemockt).
import email
import email.policy
import json
import shutil
import tempfile
import unittest
import warnings
from datetime import datetime, timedelta
from pathlib import Path
from unittest import mock
from urllib.parse import unquote_plus

warnings.filterwarnings("ignore")

from fastapi.testclient import TestClient

from app import (ablauf_pruefung, auth, benachrichtigungen, betrieb, db, geocoding,
                 graph_versand, lead_anrufliste, lead_mail, lead_mail_abruf, lead_parser,
                 lead_termin, leadmanagement_logik, mail_sync, monday_sync, scheduler)
from app import leadmanagement as kern
from app.db import SessionLocal, init_db
from app.main import app
from app.models import (AdProfil, Benachrichtigung, Benutzer, Einstellung, KommunikationLog,
                        Kunde, LeadAktivitaet, LeadPosteingang, LeadQuelle, Todo, Vorgang,
                        VotTermin, einstellung_holen)

PRAEFIX = "V29L2"
NACHNAME = f"{PRAEFIX}-Test"
FIXTURES = Path(__file__).resolve().parent / "fixtures"
# 1×1-Pixel-PNG (transparent) als Benutzerbild
PNG = bytes.fromhex(
    "89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c4890000000d4944415478"
    "9c636000020000050001e9fa4c0d0000000049454e44ae426082")
PARAMETER = ("lead_freigabe_modus", "mail_modus", "mail_testadresse", "absender_lead_mails",
             "hv_versandweg", "kalender_sync", "routing_anbieter", "score_aktiv",
             "glocke_lead_arten", "parser_modus", "versuche_max")


def aufraeumen(s):
    s.rollback()
    for k in s.query(Kunde).filter(Kunde.nachname.like(f"{NACHNAME}%")):
        for v in s.query(Vorgang).filter_by(kunde_id=k.id):
            s.query(LeadAktivitaet).filter_by(vorgang_id=v.id).delete()
            s.query(KommunikationLog).filter_by(vorgang_id=v.id).delete()
            s.query(VotTermin).filter_by(vorgang_id=v.id).delete()
            s.query(Todo).filter_by(vorgang_id=v.id).delete()
            s.query(LeadPosteingang).filter_by(vorgang_id=v.id).delete()
            s.query(Benachrichtigung).filter(
                Benachrichtigung.link == f"/lead-management/lead/{v.id}").delete()
            lead_termin.vorschlaege_cache_leeren(v.id)
            s.delete(v)
        s.delete(k)
    s.query(LeadPosteingang).filter(LeadPosteingang.graph_id.like(f"{PRAEFIX}%")).delete(
        synchronize_session=False)
    for b in s.query(Benutzer).filter(Benutzer.name.like(f"{PRAEFIX}%")):
        s.query(AdProfil).filter_by(benutzer_id=b.id).delete()
        s.query(VotTermin).filter_by(ad_id=b.id).delete()
        s.query(Todo).filter_by(an_benutzer_id=b.id).delete()
        s.query(Benachrichtigung).filter_by(benutzer_id=b.id).delete()
        s.query(Einstellung).filter(Einstellung.name.like(
            f"lead_vorlage_{lead_mail.vertriebler_key(b.id)}%")).delete(synchronize_session=False)
        for pfad in lead_mail.BENUTZERBILDER_ORDNER.glob(f"{b.id}.*") if lead_mail.BENUTZERBILDER_ORDNER.exists() else []:
            pfad.unlink(missing_ok=True)
        s.delete(b)
    s.commit()


def meldung_aus(r) -> str:
    ort = r.headers.get("location", "")
    return unquote_plus(ort.split("meldung=", 1)[1].split("&", 1)[0]) if "meldung=" in ort else ""


class Basis(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        init_db()
        cls.s = SessionLocal()
        aufraeumen(cls.s)
        cls.client = TestClient(app)
        cls.client.cookies.set(auth.COOKIE_NAME, auth.cookie_wert(1))
        cls.admin = cls.s.get(Benutzer, 1)
        cls.gesichert = {n: cls.s.query(kern.LeadParameter).filter_by(name=n).first()
                         for n in PARAMETER}
        cls.gesichert = {n: (z.wert if z is not None else None) for n, z in cls.gesichert.items()}
        for name, wert in (("lead_freigabe_modus", "admin"), ("mail_modus", "protokoll"),
                           ("mail_testadresse", ""), ("absender_lead_mails", "termin@friondo.de"),
                           ("hv_versandweg", "offen"), ("kalender_sync", "aus"),
                           ("routing_anbieter", "luftlinie"), ("score_aktiv", "aus"),
                           ("glocke_lead_arten", "todo_zugewiesen,todo_aktualisiert"),
                           ("parser_modus", "aus"), ("versuche_max", "5")):
            kern.parameter_setzen(cls.s, name, wert)
        cls.s.commit()
        # Vertriebler: angestellter AD „Horst“ mit Bild/Infotext, Handelsvertreter „Paolo“
        cls.horst = cls.benutzer_anlegen("Horst", telefon="0203 111", email="horst@test.invalid",
                                         vorname="Horst", infotext="Ich berate seit 2015.")
        cls.hv = cls.benutzer_anlegen("HV Paolo", telefon="0170 222", email="paolo@test.invalid",
                                      vorname="Paolo", hv=True)
        cls.neu_ad = cls.benutzer_anlegen("Neu Ohne Vorlage", telefon="", email="neu@test.invalid")
        lead_mail.BENUTZERBILDER_ORDNER.mkdir(parents=True, exist_ok=True)
        lead_mail.benutzerbild_speichern(cls.horst, PNG, ".png")
        cls.s.commit()
        # Terminbestätigungs-Vorlagen der DB sichern („Rahmen für alle“ schreibt in
        # alle Vorlagen der Oberkategorie – am Ende wird der Stand wiederhergestellt)
        cls.vorlagen_vorher = {z.name: z.wert for z in cls.s.query(Einstellung)
                               .filter(Einstellung.name.like("lead_vorlage_terminbestaetigung%"))}
        # Scheduler-Registrierung ohne Threads (main.lifespan läuft im TestClient nicht)
        lead_mail.scheduler_starten()
        lead_mail_abruf.scheduler_starten()
        # andere fällige Einträge der DB-Kopie während der Läufe aus dem Weg räumen
        cls.verschoben = {}
        for e in cls.s.query(KommunikationLog).filter(KommunikationLog.status == "geplant"):
            cls.verschoben[e.id] = e.geplant_am
            e.geplant_am = (e.geplant_am or datetime.now()) + timedelta(days=3650)
        cls.s.commit()

    @classmethod
    def tearDownClass(cls):
        cls.s.rollback()
        for z in (cls.s.query(Einstellung)
                  .filter(Einstellung.name.like("lead_vorlage_terminbestaetigung%"))):
            if z.name in cls.vorlagen_vorher:
                z.wert = cls.vorlagen_vorher[z.name]
            else:
                cls.s.delete(z)
        cls.s.flush()
        vorhanden = {z.name for z in cls.s.query(Einstellung)
                     .filter(Einstellung.name.like("lead_vorlage_terminbestaetigung%"))}
        for name, wert in cls.vorlagen_vorher.items():
            if name not in vorhanden:
                cls.s.add(Einstellung(name=name, wert=wert))
        for eid, geplant in cls.verschoben.items():
            e = cls.s.get(KommunikationLog, eid)
            if e is not None:
                e.geplant_am = geplant
        for name, wert in cls.gesichert.items():
            if wert is None:
                cls.s.query(kern.LeadParameter).filter_by(name=name).delete(synchronize_session=False)
            else:
                kern.parameter_setzen(cls.s, name, wert)
        cls.s.commit()
        aufraeumen(cls.s)
        cls.s.close()

    @classmethod
    def benutzer_anlegen(cls, name, telefon="", email="", vorname="", infotext="", hv=False):
        b = Benutzer(name=f"{PRAEFIX} {name}", rolle="aussendienst", pin_hash=auth.pin_hash("482913"),
                     email=email, telefon=telefon, vorname=vorname, infotext=infotext, aktiv=True)
        cls.s.add(b)
        cls.s.flush()
        cls.s.add(AdProfil(benutzer_id=b.id, start_adresse="Duisburg", aktiv_terminierung=not hv,
                           terminiert_selbst=hv, arbeitszeiten="{}", gebiet_plz_praefixe="[]",
                           kompetenz_sparten="[]"))
        cls.s.commit()
        return b

    def setUp(self):
        self.s.rollback()   # kein Folgefehler aus einem vorherigen Test

    def lead(self, nr, email=None, sparten=("WP",), ad_id=None, phase="qualifiziert", **extra):
        quelle = self.s.query(LeadQuelle).filter_by(key="website").first()
        daten = {"anrede": "Frau", "vorname": f"V{nr}", "nachname": f"{NACHNAME}-{nr}",
                 "strasse": "Teststraße 1", "plz": "47139", "ort": "Duisburg",
                 "telefon": f"0203 99{nr:04d}", "sparten": list(sparten)}
        if email:
            daten["email"] = email
        vorgang, _ = kern.lead_anlegen(self.s, daten, quelle, "api", entscheidung="neu")
        vorgang.demo = True
        vorgang.lead_phase = phase
        vorgang.ad_id = ad_id
        for k, v in extra.items():
            setattr(vorgang, k, v)
        self.s.commit()
        return vorgang

    def termin(self, vorgang, ad_id, tage=3):
        beginn = datetime.now().replace(hour=10, minute=0, second=0, microsecond=0) + timedelta(days=tage)
        while beginn.weekday() >= 5:
            beginn += timedelta(days=1)
        t = VotTermin(vorgang_id=vorgang.id, ad_id=ad_id, beginn=beginn,
                      ende=beginn + timedelta(minutes=90), adresse="Teststraße 1, 47139 Duisburg",
                      status="geplant", quelle="manuell", typ="vot", demo=True)
        self.s.add(t)
        self.s.commit()
        return t

    def mails(self, vorgang_id):
        return [(m.vorlage_key, m.status) for m in
                self.s.query(KommunikationLog).filter_by(vorgang_id=vorgang_id)
                .order_by(KommunikationLog.id)]

    def aktivitaeten(self, vorgang_id):
        return [a.text for a in self.s.query(LeadAktivitaet).filter_by(vorgang_id=vorgang_id)
                .order_by(LeadAktivitaet.id)]


# --- (i) Vorlagen-Editor, Terminbestätigung je Vertriebler ----------------------------------

class Editor(Basis):
    def test_baum_links_und_kategorien(self):
        r = self.client.get("/lead-management/vorlagen")
        self.assertEqual(r.status_code, 200)
        html = r.text
        self.assertIn('class="lmv-baum', html)
        for kat in ("eingang", "kontakt", "terminbestaetigung", "termin"):
            self.assertIn(f'data-kategorie="{kat}"', html)
        self.assertLess(html.index('class="lmv-baum'), html.index('class="lmv-editor"'))   # Baum links
        self.assertIn(f"Terminbestätigung – {self.horst.name}", html)
        self.assertIn(f"Terminbestätigung – {self.hv.name}", html)
        baum = html.split('class="lmv-baum', 1)[1].split("</nav>", 1)[0]
        self.assertNotIn("vorlage=nurture", baum)        # ausgeblendet (Datensatz bleibt)
        self.assertEqual(self.client.get("/lead-management/vorlagen?vorlage=nurture").status_code, 200)
        self.assertIn('name="vorlage" value="eingangsbestaetigung"',
                      self.client.get("/lead-management/vorlagen?vorlage=nurture").text)
        self.assertNotIn('class="reiter lm-reiter"', html)  # keine Reiterleiste oben mehr
        self.assertIn('id="lmv-suche"', html)
        self.assertIn('id="lmv-vorschau-html"', html)
        # Vertreter-Vorlage: Kasten mit Bild, Rahmen-Häkchen, Platzhalterliste
        r = self.client.get(f"/lead-management/vorlagen?vorlage={lead_mail.vertriebler_key(self.horst.id)}")
        self.assertEqual(r.status_code, 200)
        self.assertIn(f"/lead-management/benutzer/{self.horst.id}/bild", r.text)
        self.assertIn('name="rahmen_alle"', r.text)
        self.assertIn("{vertriebler_block}", r.text)
        self.assertIn("Ich berate seit 2015.", r.text)
        # Suche (GET-Fallback) blendet andere aus
        r = self.client.get("/lead-management/vorlagen?q=horst")
        self.assertIn("lmv-ausgeblendet", r.text)

    def test_katalog_und_standard_kopien(self):
        katalog = lead_mail.vorlagen_katalog(self.s)
        termin = next(k for k in katalog if k["key"] == "terminbestaetigung")
        keys = [e["key"] for e in termin["eintraege"]]
        self.assertEqual(keys[0], "terminbestaetigung")
        self.assertIn(lead_mail.vertriebler_key(self.horst.id), keys)
        self.assertIn(lead_mail.vertriebler_key(self.hv.id), keys)
        hv = next(e for e in termin["eintraege"] if e["key"] == lead_mail.vertriebler_key(self.hv.id))
        self.assertTrue(hv["hv"])
        # Zulieferung ohne Ordner: Standard-Kopien für alle drei Testvertriebler
        with mock.patch.object(lead_mail, "ZULIEFERUNG_ORDNER", Path(tempfile.gettempdir()) / "v29l2-gibt-es-nicht"):
            ergebnis = lead_mail.zulieferung_einspielen(self.s, protokoll=False)
        self.assertFalse(ergebnis["ordner"])
        self.assertGreaterEqual(ergebnis["kopien"], 1)
        for person in (self.horst, self.hv, self.neu_ad):
            self.assertTrue(lead_mail.vorlage_vorhanden(self.s, lead_mail.vertriebler_key(person.id)))
            self.assertEqual(lead_mail.vorlage_quelle(self.s, lead_mail.vertriebler_key(person.id)), "standard_kopie")
        self.s.commit()

    def test_versand_waehlt_vorlage_des_vertrieblers_und_fallback(self):
        key = lead_mail.vertriebler_key(self.horst.id)
        lead_mail.vorlage_speichern(self.s, key, "Termin bei Horst am {termin_datum}",
                                    "Hallo {briefanrede},\n\nHORST-INDIVIDUELL\n\n{adresse}\n\n{sparten_hinweise}\n\n{vertriebler_block}\n\nGruß",
                                    quelle="editor")
        # „Neu ohne Vorlage“: Kopie entfernen → Fallback Standard mit Hinweis
        self.s.query(Einstellung).filter(Einstellung.name.like(
            f"lead_vorlage_{lead_mail.vertriebler_key(self.neu_ad.id)}%")).delete(synchronize_session=False)
        self.s.commit()
        v = self.lead(1, email="v29l2-1@test.invalid", sparten=("WP", "PV"))
        t = self.termin(v, self.horst.id)
        eintrag = kern.mail_planen(self.s, v, "terminbestaetigung", termin=t)
        self.assertIsNotNone(eintrag)
        self.assertEqual(eintrag.absender, "termin@friondo.de")
        self.assertEqual(eintrag.vorlage_key, "terminbestaetigung")   # Key bleibt, Variante beim Rendern
        self.assertTrue(lead_mail.rendern(self.s, eintrag))
        self.assertIn("HORST-INDIVIDUELL", eintrag.body_html)
        self.assertIn(f"cid:{lead_mail.CID_PRAEFIX}{self.horst.id}", eintrag.body_html)
        self.assertIn("Ich berate seit 2015.", eintrag.body_html)
        self.assertIn("0203 111", eintrag.body_html)
        self.assertIn("Teststraße 1", eintrag.body_html)
        self.assertIn("Termin bei Horst am", eintrag.betreff)
        self.assertTrue(eintrag.anhang_pfad and eintrag.anhang_pfad.endswith(".ics"))
        ics = Path(eintrag.anhang_pfad).read_text(encoding="utf-8")
        self.assertIn("ORGANIZER;CN=Friondo:mailto:termin@friondo.de", ics)
        bilder = lead_mail.inline_bilder_aus_html(self.s, eintrag.body_html)
        self.assertEqual([b[0] for b in bilder], [f"{lead_mail.CID_PRAEFIX}{self.horst.id}"])
        self.assertEqual(bilder[0][2], "image/png")
        # Fallback Standard + Aktivität
        v2 = self.lead(2, email="v29l2-2@test.invalid")
        t2 = self.termin(v2, self.neu_ad.id)
        e2 = kern.mail_planen(self.s, v2, "terminbestaetigung", termin=t2)
        self.assertIsNotNone(e2)
        lead_mail.rendern(self.s, e2)
        self.assertNotIn("HORST-INDIVIDUELL", e2.body_html)
        standard_text = lead_mail.vorlage_laden(self.s, "terminbestaetigung")[1]
        erste_zeile = lead_mail.html_zu_text(lead_mail.html_aus_vorlage(standard_text, {})).splitlines()[0]
        self.assertIn(erste_zeile.replace("{briefanrede}", "").strip(" ,")[:12] or "Vor-Ort", e2.body_html)
        self.assertTrue(any("Standard-Vorlage verwendet" in a for a in self.aktivitaeten(v2.id)))
        self.s.commit()

    def test_rahmen_fuer_alle_laesst_bloecke_unveraendert(self):
        standard_vorher = lead_mail.vorlage_laden(self.s, "terminbestaetigung")
        self.addCleanup(self._standard_wiederherstellen, standard_vorher)
        key_h = lead_mail.vertriebler_key(self.horst.id)
        block = f"{lead_mail.BLOCK_START}Persönlicher Text von Horst{lead_mail.BLOCK_ENDE}"
        lead_mail.vorlage_speichern(self.s, key_h, "Alt", f"Alter Rahmen oben\n\n{block}\n\nAlter Rahmen unten", quelle="editor")
        key_hv = lead_mail.vertriebler_key(self.hv.id)
        lead_mail.vorlage_speichern(self.s, key_hv, "Alt HV", "Nur Rahmen ohne Block", quelle="standard_kopie")
        self.s.commit()
        anzahl = lead_mail.ziel_anzahl(self.s, "terminbestaetigung")
        # ohne Bestätigung: gespeichert, aber nicht übernommen
        r = self.client.post("/lead-management/vorlagen",
                             data={"vorlage": "terminbestaetigung", "betreff": "NEU {termin_datum}",
                                   "text": "Neuer Rahmen oben\n\n{vertriebler_block}\n\nNeuer Rahmen unten",
                                   "rahmen_alle": "on", "aktion": "speichern"}, follow_redirects=False)
        self.assertEqual(r.status_code, 303)
        self.assertIn("NICHT übernommen", meldung_aus(r))
        self.s.expire_all()
        self.assertEqual(lead_mail.vorlage_laden(self.s, key_h)[0], "Alt")
        # mit Bestätigung
        r = self.client.post("/lead-management/vorlagen",
                             data={"vorlage": "terminbestaetigung", "betreff": "NEU {termin_datum}",
                                   "text": "Neuer Rahmen oben\n\n{vertriebler_block}\n\nNeuer Rahmen unten",
                                   "rahmen_alle": "on", "bestaetigt": "1", "aktion": "speichern"},
                             follow_redirects=False)
        self.assertIn(f"Rahmen für {anzahl} weitere", meldung_aus(r))
        self.s.expire_all()
        betreff, text = lead_mail.vorlage_laden(self.s, key_h)
        self.assertEqual(betreff, "NEU {termin_datum}")
        self.assertEqual(text, f"Neuer Rahmen oben\n\n{block}\n\nNeuer Rahmen unten")
        betreff_hv, text_hv = lead_mail.vorlage_laden(self.s, key_hv)
        self.assertEqual(text_hv, "Neuer Rahmen oben\n\n{vertriebler_block}\n\nNeuer Rahmen unten")
        self.assertEqual(lead_mail.vorlage_quelle(self.s, key_h), "editor")
        self.assertIn("Rahmen der Vorlage", kern.parameter_holen(self.s, "einstellungs_protokoll", ""))
        # Standard-Vorlage selbst trägt den neuen Text
        self.assertEqual(lead_mail.vorlage_laden(self.s, "terminbestaetigung")[0], "NEU {termin_datum}")

    def _standard_wiederherstellen(self, vorher):
        self.s.rollback()
        lead_mail.vorlage_speichern(self.s, "terminbestaetigung", vorher[0], vorher[1], quelle="")
        self.s.commit()

    def test_vorschau_json_und_html_erkennung(self):
        r = self.client.post("/lead-management/vorlagen/vorschau",
                             json={"vorlage": lead_mail.vertriebler_key(self.horst.id),
                                   "betreff": "B {termin_datum}", "text": "<p>Hallo {briefanrede}</p>{vertriebler_block}"},
                             headers={"Accept": "application/json"})
        self.assertEqual(r.status_code, 200)
        d = r.json()
        self.assertTrue(d["ok"])
        self.assertIn("<p>Hallo Sehr geehrte", d["html"])
        self.assertIn(f"/lead-management/benutzer/{self.horst.id}/bild", d["html"])   # Vorschau statt cid
        self.assertTrue(lead_mail.ist_html("<p>x</p>"))
        self.assertFalse(lead_mail.ist_html("Nur Text\n\nAbsatz"))
        html = lead_mail.html_aus_vorlage("Hallo {name}", {"name": "<b>x</b>"})
        self.assertIn("&lt;b&gt;x&lt;/b&gt;", html)

    def test_zulieferung_ordner_einspielen(self):
        ordner = Path(tempfile.mkdtemp(prefix="v29l2_zulieferung_"))
        try:
            (ordner / "horst.html").write_text(
                "<html><head><title>Ihr Termin bei Horst am {termin_datum}</title></head>"
                "<body><p>ZULIEFERUNG {briefanrede}</p><!-- vertriebler_block --><p>Horst persönlich</p>"
                "<!-- /vertriebler_block --></body></html>", encoding="utf-8")
            (ordner / "horst.png").write_bytes(PNG)
            (ordner / "unbekannt.html").write_text("<p>x</p>", encoding="utf-8")
            key = lead_mail.vertriebler_key(self.horst.id)
            lead_mail.vorlage_speichern(self.s, key, "Alt", "Alt", quelle="standard_kopie")
            # Bild wurde in setUpClass „manuell“ gesetzt → nicht überschreiben
            self.s.commit()
            with mock.patch.object(lead_mail, "ZULIEFERUNG_ORDNER", ordner):
                e1 = lead_mail.zulieferung_einspielen(self.s, protokoll=True)
                self.s.commit()
                betreff, text = lead_mail.vorlage_laden(self.s, key)
                quelle = lead_mail.vorlage_quelle(self.s, key)
                e2 = lead_mail.zulieferung_einspielen(self.s, protokoll=False)
                self.s.commit()
                lead_mail.vorlage_speichern(self.s, key, "Im Editor", "<p>Editor</p>", quelle="editor")
                self.s.commit()
                (ordner / "horst.html").write_text("<p>GEAENDERT</p>", encoding="utf-8")
                e3 = lead_mail.zulieferung_einspielen(self.s, protokoll=False)
            self.assertTrue(e1["ordner"])
            self.assertEqual(len(e1["eingespielt"]), 1)
            self.assertTrue(any("unbekannt.html" in u for u in e1["uebersprungen"]))
            self.assertTrue(any("manuell hochgeladen" in u for u in e1["uebersprungen"]))
            self.assertEqual(betreff, "Ihr Termin bei Horst am {termin_datum}")
            self.assertIn("ZULIEFERUNG", text)
            self.assertEqual(quelle, "zulieferung")
            self.assertEqual(e2["unveraendert"], 1)
            self.assertEqual(len(e2["eingespielt"]), 0)
            self.assertTrue(any("im Editor geändert" in u for u in e3["uebersprungen"]))
            self.assertIn("Terminbestätigungen einspielen", kern.parameter_holen(self.s, "einstellungs_protokoll", ""))
            # Route (Admin)
            with mock.patch.object(lead_mail, "ZULIEFERUNG_ORDNER", ordner):
                r = self.client.post("/lead-management/vorlagen/einspielen", follow_redirects=False)
            self.assertEqual(r.status_code, 303)
            self.assertIn("Terminbestätigungen einspielen", meldung_aus(r))
            # Rahmen übernehmen hält den markierten Block der Zulieferung
            lead_mail.vorlage_speichern(self.s, key, betreff, text, quelle="zulieferung")
            lead_mail.vorlage_speichern(self.s, "terminbestaetigung", "R", "Rahmen A\n\n{vertriebler_block}\n\nRahmen B")
            lead_mail.rahmen_uebernehmen(self.s, "terminbestaetigung")
            _, neu = lead_mail.vorlage_laden(self.s, key)
            self.assertEqual(neu, f"Rahmen A\n\n{lead_mail.BLOCK_START}<p>Horst persönlich</p>{lead_mail.BLOCK_ENDE}\n\nRahmen B")
            self.s.commit()
        finally:
            shutil.rmtree(ordner, ignore_errors=True)

    def test_benutzerverwaltung_bild_und_infotext(self):
        r = self.client.post(f"/benutzer/{self.neu_ad.id}/ad-profil",
                             data={"start_adresse": "", "termin_dauer_min": "90", "puffer_min": "30",
                                   "max_termine_tag": "3", "gebiet": "", "vorname": "Nico",
                                   "infotext": "Neu im Team.", "aktiv_terminierung": "on"},
                             files={"bild": ("foto.png", PNG, "image/png")}, follow_redirects=False)
        self.assertEqual(r.status_code, 303)
        self.assertIn("Bild gespeichert", meldung_aus(r))
        self.s.expire_all()
        person = self.s.get(Benutzer, self.neu_ad.id)
        self.assertEqual((person.vorname, person.infotext), ("Nico", "Neu im Team."))
        self.assertEqual(person.bild_datei, f"benutzerbilder/{person.id}.png")
        self.assertTrue(lead_mail.bild_pfad(person).exists())
        self.assertTrue(lead_mail.vorlage_vorhanden(self.s, lead_mail.vertriebler_key(person.id)))
        r = self.client.get(f"/lead-management/benutzer/{person.id}/bild")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.headers["content-type"], "image/png")
        # zu groß / falsche Endung
        r = self.client.post(f"/benutzer/{self.neu_ad.id}/ad-profil", data={"start_adresse": ""},
                             files={"bild": ("foto.gif", PNG, "image/gif")}, follow_redirects=False)
        self.assertIn("nur JPG oder PNG", meldung_aus(r))
        r = self.client.post(f"/benutzer/{self.neu_ad.id}/ad-profil", data={"start_adresse": ""},
                             files={"bild": ("gross.png", b"\x89" * (lead_mail.BILD_MAX_BYTES + 1), "image/png")},
                             follow_redirects=False)
        self.assertIn("größer als 2 MB", meldung_aus(r))
        r = self.client.get(f"/benutzer/{self.neu_ad.id}/ad-profil")
        self.assertIn('name="infotext"', r.text)
        self.assertIn(f"/lead-management/benutzer/{person.id}/bild", r.text)
        # Vorname in der Benutzerliste
        r = self.client.post(f"/benutzer/{self.neu_ad.id}/aendern",
                             data={"name": person.name, "rolle": "aussendienst", "email": person.email,
                                   "aktiv": "on", "vorname": "Nikolaus"}, follow_redirects=False)
        self.s.expire_all()
        self.assertEqual(self.s.get(Benutzer, self.neu_ad.id).vorname, "Nikolaus")
        self.assertIn('name="vorname"', self.client.get("/benutzer").text)
        block = lead_mail.vertriebler_block_html(self.s.get(Benutzer, self.neu_ad.id))
        self.assertIn("Neu im Team.", block)
        self.assertIn(f"cid:{lead_mail.CID_PRAEFIX}{person.id}", block)
        self.assertIn("Neu im Team.", lead_mail.vertriebler_block_text(person))


# --- (j) Sparten-Baustein -----------------------------------------------------------------

class SpartenBaustein(Basis):
    def test_wp_wp_pv_gw(self):
        logik = leadmanagement_logik.hole_logik()
        original = list(logik.terminhinweise)
        T = leadmanagement_logik.Terminhinweis
        logik.terminhinweise = [T("WP", 2, "Heizkostenabrechnung"), T("WP", 1, "Grundriss"),
                                T("WP", 3, "Grundriss"),              # Dublette innerhalb WP
                                T("PV", 1, "Stromrechnung"), T("PV", 2, "Grundriss"),   # Dublette über Sparten
                                T("GW", 1, "(Punkte folgen)")]
        try:
            html_wp = lead_mail.sparten_hinweise_html(["WP"])
            self.assertIn(lead_mail.SPARTEN_EINLEITUNG, html_wp)
            self.assertEqual(html_wp.count("<li>"), 2)
            self.assertLess(html_wp.index("Grundriss"), html_wp.index("Heizkostenabrechnung"))
            self.assertNotIn("<strong>", html_wp)                      # eine Sparte: keine Zwischenüberschrift
            html_wp_pv = lead_mail.sparten_hinweise_html(["WP", "PV"])
            self.assertIn("<strong>Wärmepumpe</strong>", html_wp_pv)
            self.assertIn("<strong>Photovoltaik</strong>", html_wp_pv)
            self.assertEqual(html_wp_pv.count("Grundriss"), 1)        # Dubletten entfernt
            self.assertEqual(html_wp_pv.count("<li>"), 3)
            self.assertEqual(html_wp_pv.count(lead_mail.SPARTEN_EINLEITUNG), 1)
            html_gw = lead_mail.sparten_hinweise_html(["GW"])
            self.assertIn("(Punkte folgen)", html_gw)
            self.assertEqual(lead_mail.sparten_hinweise_html(["WB"]), "")
            text = lead_mail.sparten_hinweise_text(["WP", "PV"])
            self.assertIn("- Grundriss", text)
            self.assertIn("Photovoltaik", text)
            # in der Mail (Textvorlage): Baustein steht nicht in einem <p>
            v = self.lead(10, email="v29l2-10@test.invalid", sparten=("WP", "PV"))
            t = self.termin(v, self.horst.id)
            betreff, html, _ = lead_mail.vorlage_rendern(self.s, "terminbestaetigung", v, t,
                                                         text_vorgabe=("B", "Oben\n\n{sparten_hinweise}\n\nUnten"))
            self.assertIn("</p><p>" + lead_mail.SPARTEN_EINLEITUNG, html.replace("<p>Oben</p>", "</p>"))
            self.assertNotIn("<p><p>", html)
        finally:
            logik.terminhinweise = original
        # Live-Steuerdatei: Blatt vorhanden, Platzhalter je Sparte, nach_letztem
        frisch = leadmanagement_logik.einlesen()
        self.assertFalse(any("Terminhinweise“ fehlt" in w for w in frisch.warnungen))
        for s in leadmanagement_logik.SPARTEN:
            self.assertTrue(frisch.hinweise_der_sparte(s))
        self.assertEqual(frisch.nach_letztem(), "mail_disqualifiziert")


# --- (k) Nurture entfernt -----------------------------------------------------------------

class Nurture(Basis):
    def test_keine_nurture_mehr_letzte_stufe_disqualifiziert(self):
        self.assertNotIn("nurture", lead_mail.VORLAGEN_START)
        self.assertEqual(lead_anrufliste.VORGANGS_MAILS, ("nicht_erreicht", "disqualifiziert"))
        maximal = kern.versuche_max(self.s)
        v = self.lead(20, email="v29l2-20@test.invalid", phase="in_kontaktierung")
        v.versuch_nr = maximal
        self.s.commit()
        meldung = kern.kaskade_anwenden(self.s, v, self.admin)
        self.s.commit()
        self.assertIn("Nicht erreicht", meldung)
        self.s.expire_all()
        v = self.s.get(Vorgang, v.id)
        self.assertEqual(v.lead_phase, "nicht_erreicht")
        self.assertIsNone(v.naechste_aktion_am)
        keys = [k for k, _ in self.mails(v.id) if k != "eingangsbestaetigung"]
        self.assertEqual(keys, ["disqualifiziert"])           # genau einmal, keine nurture
        self.assertTrue(any("Vorlage disqualifiziert" in a for a in self.aktivitaeten(v.id)))
        self.assertIsNone(kern.mail_planen(self.s, v, "nurture"))
        # Auskunft: keine Wiedervorlage +30 Tage mehr
        d = lead_anrufliste.anruf_vorschlag(self.s, v)
        self.assertTrue(d["gesperrt"])
        self.assertIsNone(d["zeitpunkt"])
        # Altbestand: ein geplanter Nurture-Eintrag wird vom Lauf storniert
        alt = KommunikationLog(vorgang_id=v.id, kanal="mail", vorlage_key="nurture",
                               an="v29l2-20@test.invalid", status="geplant", modus="protokoll",
                               geplant_am=datetime.now() - timedelta(minutes=1))
        self.s.add(alt)
        self.s.commit()
        ergebnis = scheduler.ausfuehren("lead-mail")
        self.assertTrue(ergebnis["ok"], ergebnis)
        self.s.expire_all()
        self.assertEqual(self.s.get(KommunikationLog, alt.id).status, "storniert")
        # Migration idempotent: zweiter Lauf ohne Meldungen
        lead_mail.migration_v29_mails(self.s)
        self.s.commit()
        self.assertEqual(lead_mail.migration_v29_mails(self.s), [])


# --- (g1) Absender termin@, kein Fallback, Status fehler, Erneut senden ---------------------

class AbsenderUndFehler(Basis):
    def graph_mocks(self, aufrufe, fehler=None):
        def graph(methode, pfad, tok, daten=None):
            aufrufe.append((pfad, daten["message"]["from"]["emailAddress"]["address"],
                            db.engine.pool.checkedout()))
            if fehler is not None:
                raise RuntimeError(fehler)
            return {}
        return [mock.patch.object(graph_versand, "_token", return_value="tok"),
                mock.patch.object(graph_versand, "_graph_aufruf", side_effect=graph),
                mock.patch.object(lead_mail, "WIEDERHOLUNG_PAUSE_S", 0)]

    def test_alle_vorlagen_termin_ohne_fallback_fehler_und_erneut(self):
        v = self.lead(30, email="v29l2-30@test.invalid")
        t = self.termin(v, self.horst.id)
        for key in ("nicht_erreicht", "disqualifiziert"):
            kern.mail_planen(self.s, v, key)
        for key in ("terminbestaetigung", "terminerinnerung", "terminaenderung", "terminabsage",
                    "online_termin_einladung"):
            kern.mail_planen(self.s, v, key, termin=t)
        self.s.commit()
        eintraege = self.s.query(KommunikationLog).filter_by(vorgang_id=v.id).all()
        self.assertEqual({e.vorlage_key for e in eintraege},
                         {"eingangsbestaetigung", "nicht_erreicht", "disqualifiziert", "terminbestaetigung",
                          "terminerinnerung", "terminaenderung", "terminabsage", "online_termin_einladung"})
        self.assertTrue(all(e.absender == "termin@friondo.de" for e in eintraege))
        for e in eintraege:
            lead_mail.rendern(self.s, e)
            self.assertNotIn("leads@", e.body_html)
            self.assertNotIn("angebot@", e.body_html)
            if "{link_rueckruf}" in lead_mail.VORLAGEN_START[e.vorlage_key][2]:
                self.assertIn("mailto:termin@friondo.de", e.body_html)
        # nur die Eingangsbestätigung bleibt fällig; Rest weit in die Zukunft
        eb = next(e for e in eintraege if e.vorlage_key == "eingangsbestaetigung")
        for e in eintraege:
            if e.id != eb.id:
                e.geplant_am = datetime.now() + timedelta(days=30)
        kern.parameter_setzen(self.s, "mail_modus", "test")
        kern.parameter_setzen(self.s, "mail_testadresse", "lead-test@test.invalid")
        self.s.commit()
        aufrufe = []

        def verweigert(methode, pfad, tok, daten=None):
            aufrufe.append((daten["message"]["from"]["emailAddress"]["address"],
                            db.engine.pool.checkedout()))
            raise RuntimeError("ErrorSendAsDenied")
        try:
            with mock.patch.object(graph_versand, "_token", return_value="tok"), \
                    mock.patch.object(graph_versand, "_graph_aufruf", side_effect=verweigert), \
                    mock.patch.object(lead_mail, "WIEDERHOLUNG_PAUSE_S", 0):
                for n in range(lead_mail.VERSUCHE_MAX):
                    db.verbindung_freigeben(self.s)   # Testsitzung hält keine Verbindung
                    erg = scheduler.ausfuehren("lead-mail")
                    self.assertTrue(erg["ok"], erg)
                    self.s.expire_all()
                    eb = self.s.get(KommunikationLog, eb.id)
                    self.assertEqual(eb.versuche, n + 1)
                    if n + 1 < lead_mail.VERSUCHE_MAX:
                        self.assertEqual(eb.status, "geplant")
            # kein Fallback: jeder Versuch als termin@, nie angebot@/leads@; Pool frei beim Netzaufruf
            self.assertEqual([a[0] for a in aufrufe], ["termin@friondo.de"] * lead_mail.VERSUCHE_MAX)
            self.assertEqual([a[1] for a in aufrufe], [0] * lead_mail.VERSUCHE_MAX, aufrufe)
            self.s.expire_all()
            eb = self.s.get(KommunikationLog, eb.id)
            v = self.s.get(Vorgang, v.id)
            self.assertEqual(eb.status, "fehler")
            self.assertIn("ErrorSendAsDenied", eb.fehler_text)
            self.assertTrue(v.mail_fehler)
            self.assertEqual(v.mail_fehler_vorlage, "eingangsbestaetigung")
            self.assertIsNotNone(v.mail_fehler_am)
            self.assertTrue(any(a.startswith("Mail nicht gesendet: Eingangsbestätigung") for a in self.aktivitaeten(v.id)))
            hinweis = lead_mail.kartei_hinweis(self.s, v)
            self.assertEqual(hinweis["art"], "fehler")
            self.assertEqual(hinweis["titel"], "Mail nicht gesendet")
            self.assertEqual(hinweis["erneut_url"], f"/lead-management/mail/{eb.id}/erneut")
            self.assertEqual(hinweis["warteschlange_url"], "/lead-management/kommunikation?status=fehler")
            # Kachel/Zähler: Lead-Einstellungen und Betriebs-Seite zählen ≥ 1
            from app.routers import betrieb as betrieb_router
            self.assertGreaterEqual(betrieb_router._lead_mail_fehler(self.s), 1)
            r = self.client.get("/parametrierung/lead-einstellungen")
            self.assertIn("Lead-Mail(s) mit Fehler", r.text)
            # Hauptboard: Lead ganz oben mit rotem Label (Vertrag L1)
            r = self.client.get("/lead-management/hauptboard")
            self.assertEqual(r.status_code, 200)
            if "Mail nicht gesendet" in r.text and f'data-vorgang="{v.id}"' in r.text:
                erste = r.text.index('data-vorgang="')
                self.assertEqual(r.text[erste:].split('"', 2)[1], str(v.id), "Lead mit Mail-Fehler nicht ganz oben")
            # Kartei rendert den Hinweisbalken (Einbindung durch L1) – mindestens die Route läuft
            r = self.client.get(f"/lead-management/lead/{v.id}")
            self.assertEqual(r.status_code, 200)
            # Erneut senden → geplant, sofort fällig, Versuche 0 (kein Versand im Request)
            with mock.patch.object(graph_versand, "_graph_aufruf",
                                   side_effect=AssertionError("Request darf nicht senden")):
                r = self.client.post(f"/lead-management/mail/{eb.id}/erneut", follow_redirects=False,
                                     headers={"Referer": f"http://testserver/lead-management/lead/{v.id}"})
            self.assertEqual(r.status_code, 303)
            self.assertTrue(r.headers["location"].startswith(f"/lead-management/lead/{v.id}?meldung="))
            self.assertIn("Erneuter Versand angestoßen – Ergebnis in etwa einer Minute", meldung_aus(r))
            self.s.expire_all()
            eb = self.s.get(KommunikationLog, eb.id)
            self.assertEqual((eb.status, eb.versuche, eb.fehler_text), ("geplant", 0, ""))
            self.assertLessEqual(eb.geplant_am, datetime.now())
            # JSON-Variante und Referer-Fallback
            r = self.client.post(f"/lead-management/mail/{eb.id}/erneut", headers={"Accept": "application/json"})
            self.assertEqual(r.status_code, 200)
            self.assertTrue(r.json()["ok"])
            # Freigabe: Lauf lead-mail sendet erfolgreich → gesendet, Kennzeichen zurück
            gesendet = []
            with mock.patch.object(graph_versand, "_token", return_value="tok"), \
                    mock.patch.object(graph_versand, "_graph_aufruf",
                                      side_effect=lambda m, p, t_, d=None: gesendet.append(d) or {}):
                erg = scheduler.ausfuehren("lead-mail")
            self.assertTrue(erg["ok"], erg)
            self.assertEqual(len(gesendet), 1)
            nachricht = gesendet[0]["message"]
            self.assertEqual(nachricht["from"]["emailAddress"]["address"], "termin@friondo.de")
            self.assertEqual(nachricht["toRecipients"][0]["emailAddress"]["address"], "lead-test@test.invalid")
            self.assertTrue(nachricht["subject"].startswith("[TEST an v29l2-30@test.invalid]"))
            self.s.expire_all()
            eb = self.s.get(KommunikationLog, eb.id)
            v = self.s.get(Vorgang, v.id)
            self.assertEqual(eb.status, "gesendet")
            self.assertFalse(v.mail_fehler)
            self.assertEqual(v.mail_fehler_vorlage, "")
            self.assertIsNone(lead_mail.kartei_hinweis(self.s, v))
        finally:
            kern.parameter_setzen(self.s, "mail_modus", "protokoll")
            kern.parameter_setzen(self.s, "mail_testadresse", "")
            self.s.commit()

    def test_inline_bild_als_cid_anhang_beim_versand(self):
        v = self.lead(31, email="v29l2-31@test.invalid")
        t = self.termin(v, self.horst.id)
        e = kern.mail_planen(self.s, v, "terminbestaetigung", termin=t)
        kern.parameter_setzen(self.s, "mail_modus", "test")
        kern.parameter_setzen(self.s, "mail_testadresse", "lead-test@test.invalid")
        self.s.commit()
        gesendet = []
        try:
            with mock.patch.object(graph_versand, "_token", return_value="tok"), \
                    mock.patch.object(graph_versand, "_graph_aufruf",
                                      side_effect=lambda m, p, t_, d=None: gesendet.append(d) or {}):
                self.assertEqual(lead_mail.eintrag_verarbeiten(self.s, e), "gesendet")
            anhaenge = gesendet[0]["message"]["attachments"]
            inline = [a for a in anhaenge if a.get("isInline")]
            self.assertEqual(len(inline), 1)
            self.assertEqual(inline[0]["contentId"], f"{lead_mail.CID_PRAEFIX}{self.horst.id}")
            self.assertEqual(inline[0]["contentType"], "image/png")
            self.assertTrue(any(a["name"].endswith(".ics") for a in anhaenge))
        finally:
            self.s.rollback()
            kern.parameter_setzen(self.s, "mail_modus", "protokoll")
            kern.parameter_setzen(self.s, "mail_testadresse", "")
            self.s.commit()

    def test_testmail_route_mit_geschlossener_sitzung(self):
        kern.parameter_setzen(self.s, "mail_testadresse", "lead-test@test.invalid")
        self.s.commit()
        aufrufe = []

        def graph(methode, pfad, tok, daten=None):
            aufrufe.append((daten["message"]["from"]["emailAddress"]["address"],
                            daten["message"]["toRecipients"][0]["emailAddress"]["address"],
                            db.engine.pool.checkedout()))
            return {}
        try:
            with mock.patch.object(graph_versand, "konfiguriert", return_value=True), \
                    mock.patch.object(graph_versand, "_token", return_value="tok"), \
                    mock.patch.object(graph_versand, "_graph_aufruf", side_effect=graph):
                r = self.client.post("/lead-management/testmail", data={"an": "fremd@test.invalid"},
                                     follow_redirects=False)
            self.assertEqual(r.status_code, 303)
            self.assertIn("gesendet", meldung_aus(r))
            # Demo-Modus: nur Testpostfach, Absender termin@, Sitzung während des Netzaufrufs frei
            self.assertEqual(aufrufe, [("termin@friondo.de", "lead-test@test.invalid", 0)])
            self.assertIn("Testmail aus termin@friondo.de", kern.parameter_holen(self.s, "einstellungs_protokoll", ""))
            # Fehler ohne Fallback
            with mock.patch.object(graph_versand, "konfiguriert", return_value=True), \
                    mock.patch.object(graph_versand, "_token", return_value="tok"), \
                    mock.patch.object(graph_versand, "_graph_aufruf", side_effect=RuntimeError("SendAsDenied")):
                r = self.client.post("/lead-management/testmail", follow_redirects=False)
            self.assertIn("kein Fallback", meldung_aus(r))
            # Demo ohne Testadresse → Hinweis, kein Versand
            kern.parameter_setzen(self.s, "mail_testadresse", "")
            self.s.commit()
            with mock.patch.object(graph_versand, "_graph_aufruf", side_effect=AssertionError("kein Versand")):
                r = self.client.post("/lead-management/testmail", follow_redirects=False)
            self.assertIn("Testpostfach", meldung_aus(r))
        finally:
            kern.parameter_setzen(self.s, "mail_testadresse", "")
            self.s.commit()


# --- (g2) Handelsvertreter-Lead: Versandweg offen -------------------------------------------

class Handelsvertreter(Basis):
    def test_hv_lead_keine_mail_todo_mit_vorschau_ad_lead_mail(self):
        v = self.lead(40, email="v29l2-40@test.invalid", ad_id=self.hv.id)
        t = self.termin(v, self.hv.id)
        self.assertIsNone(kern.mail_planen(self.s, v, "terminbestaetigung", termin=t))
        self.assertIsNone(kern.mail_planen(self.s, v, "terminerinnerung", termin=t,
                                           geplant_am=t.beginn - timedelta(hours=24)))
        self.s.commit()
        self.assertEqual([k for k, _ in self.mails(v.id)], ["eingangsbestaetigung"])   # Eingang bleibt termin@
        akt = self.aktivitaeten(v.id)
        self.assertTrue(any("Terminbestätigung nicht gesendet: Versandweg für Handelsvertreter offen" in a for a in akt))
        self.assertTrue(any("Terminerinnerung nicht gesendet" in a for a in akt))
        todos = self.s.query(Todo).filter_by(vorgang_id=v.id, an_benutzer_id=self.hv.id).all()
        self.assertEqual([x.titel for x in todos], ["Terminbestätigung selbst senden"])
        vorschau = f"/lead-management/lead/{v.id}/termin/{t.id}/vorschau"
        self.assertIn(vorschau, todos[0].text)
        # Vorschau: Text + ICS (Admin und der HV selbst, Fremd-HV 404)
        r = self.client.get(vorschau)
        self.assertEqual(r.status_code, 200)
        self.assertIn("Versandweg für Handelsvertreter offen", r.text)
        self.assertIn("v29l2-40@test.invalid", r.text)
        self.assertIn(t.beginn.strftime("%d.%m.%Y"), r.text)
        r = self.client.get(vorschau + "?ics=1")
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.headers["content-type"].startswith("text/calendar"))
        self.assertIn("BEGIN:VCALENDAR", r.text)
        r = self.client.get(vorschau + "?txt=1")
        self.assertIn("Betreff:", r.text)
        hv_client = TestClient(app)
        hv_client.cookies.set(auth.COOKIE_NAME, auth.cookie_wert(self.hv.id))
        self.assertEqual(hv_client.get(vorschau).status_code, 200)
        fremd = TestClient(app)
        fremd.cookies.set(auth.COOKIE_NAME, auth.cookie_wert(self.horst.id))
        self.assertEqual(fremd.get(vorschau).status_code, 404)
        # Andere Versandwege: Erweiterungspunkte verhalten sich wie offen (Hinweis-Aktivität)
        kern.parameter_setzen(self.s, "hv_versandweg", "smtp")
        self.s.commit()
        try:
            self.assertIsNone(kern.mail_planen(self.s, v, "terminabsage", termin=t))
            self.assertTrue(any("smtp noch nicht umgesetzt" in a for a in self.aktivitaeten(v.id)))
        finally:
            kern.parameter_setzen(self.s, "hv_versandweg", "offen")
            self.s.commit()
        # AD-Lead: Mail wie gewohnt (termin_buchen plant Bestätigung + Erinnerung)
        v2 = self.lead(41, email="v29l2-41@test.invalid")
        termin, meldung = kern.termin_buchen(self.s, v2, self.horst.id,
                                             datetime.now().replace(hour=9, minute=0, second=0, microsecond=0) + timedelta(days=4),
                                             benutzer=self.admin)
        self.s.commit()
        self.assertIsNotNone(termin, meldung)
        keys = [k for k, _ in self.mails(v2.id)]
        self.assertIn("terminbestaetigung", keys)
        self.assertIn("terminerinnerung", keys)
        # HV über termin_buchen: beides entfällt, To-Do vorhanden
        v3 = self.lead(42, email="v29l2-42@test.invalid", ad_id=self.hv.id)
        termin3, _ = kern.termin_buchen(self.s, v3, self.hv.id,
                                        datetime.now().replace(hour=14, minute=0, second=0, microsecond=0) + timedelta(days=4),
                                        benutzer=self.admin)
        self.s.commit()
        self.assertIsNotNone(termin3)
        self.assertEqual([k for k, _ in self.mails(v3.id)], ["eingangsbestaetigung"])
        self.assertEqual(self.s.query(Todo).filter_by(vorgang_id=v3.id).count(), 1)

    def test_g3_hv_sperrzeit(self):
        """(g3) HV-Sperrzeit blockiert einen Vorschlags-Slot – Eintragstyp
        `sperrzeit` an vot_termine baut Agent L1 (Phase 143)."""
        if not any(hasattr(lead_termin, n) for n in ("sperrzeit_anlegen", "sperrzeiten", "STATUS_SPERRZEIT")) \
                and "sperrzeit" not in Path(lead_termin.__file__).read_text(encoding="utf-8"):
            self.skipTest("Sperrzeit (L1, Phase 143) noch nicht vorhanden – Test (g3) übersprungen")
        self.skipTest("Sperrzeit vorhanden – Vorschlags-Test liegt in tests/test_lead_v4.py (L1, Teil m)")


# --- (l) Bounce und Kundenantwort über lead-mail-abruf --------------------------------------

def ndr_aus_fixture(name: str, graph_id: str, **werte) -> dict:
    roh = (FIXTURES / name).read_text(encoding="utf-8")
    for k, v in werte.items():
        roh = roh.replace("{" + k + "}", str(v))
    msg = email.message_from_string(roh, policy=email.policy.default)
    inhalt = msg.get_content()
    return {"id": graph_id, "subject": msg["Subject"],
            "from": {"emailAddress": {"address": email.utils.parseaddr(msg["From"])[1]}},
            "toRecipients": [{"emailAddress": {"address": msg["To"]}}],
            "receivedDateTime": "2026-10-08T07:15:02Z",
            "body": {"contentType": "html" if msg.get_content_type() == "text/html" else "text",
                     "content": inhalt},
            "_headers": {k.lower(): v for k, v in msg.items()}}


class Bounce(Basis):
    def lauf(self, nachrichten):
        gelesen = []
        with mock.patch.object(graph_versand, "konfiguriert", return_value=True), \
                mock.patch.object(graph_versand, "_token", return_value="tok"), \
                mock.patch.object(graph_versand, "postfach_ungelesen", return_value=nachrichten), \
                mock.patch.object(graph_versand, "nachricht_gelesen_markieren",
                                  side_effect=lambda t, p, i: gelesen.append(i) or True), \
                mock.patch.object(graph_versand, "_graph_aufruf", side_effect=AssertionError("echter Graph")):
            ergebnis = scheduler.ausfuehren("lead-mail-abruf")
        self.assertTrue(ergebnis["ok"], ergebnis)
        self.assertFalse(ergebnis["uebersprungen"], ergebnis)
        return ergebnis, gelesen

    def test_ndr_de_eingangsbestaetigung(self):
        adresse = "v29l2-bounce-de@test.invalid"
        v = self.lead(50, email=adresse, phase="neu")
        eb = self.s.query(KommunikationLog).filter_by(vorgang_id=v.id, vorlage_key="eingangsbestaetigung").one()
        lead_mail.rendern(self.s, eb)
        eb.status = "gesendet"
        eb.gesendet_am = datetime.now()
        # Kaskaden-Mail 2 bereits geplant (Zukunft) → muss angehalten werden
        zweite = kern.mail_planen(self.s, v, "nicht_erreicht", geplant_am=datetime.now() + timedelta(days=1))
        self.s.commit()
        n = ndr_aus_fixture("ndr_exchange_de.eml", f"{PRAEFIX}-ndr-de-{v.id}", kundenadresse=adresse, eintrag_id=eb.id)
        self.assertTrue(lead_mail_abruf.ist_ndr(n["from"]["emailAddress"]["address"], n["subject"]))
        ergebnis, gelesen = self.lauf([n])
        self.assertIn("bounce=1", ergebnis["ergebnis"])
        self.assertEqual(gelesen, [n["id"]])
        self.s.expire_all()
        v = self.s.get(Vorgang, v.id)
        self.assertEqual(v.email_status, "ungueltig")
        self.assertIsNotNone(v.email_status_am)
        self.assertIn("Unzustellbar", v.email_status_grund)
        self.assertTrue(any(a.startswith("E-Mail unzustellbar: " + adresse) for a in self.aktivitaeten(v.id)))
        self.assertEqual(self.s.get(KommunikationLog, zweite.id).status, "wartet_adresse")
        self.assertEqual(self.s.get(KommunikationLog, eb.id).status, "gesendet")    # bleibt, Hinweis im fehler_text
        self.assertIn("Unzustellbar", self.s.get(KommunikationLog, eb.id).fehler_text)
        hinweis = lead_mail.kartei_hinweis(self.s, v)
        self.assertEqual((hinweis["art"], hinweis["titel"]), ("ungueltig", "E-Mail falsch"))
        self.assertIsNone(hinweis["erneut_url"])
        # „Erneut senden“ ist bis zur Adressänderung gesperrt
        ok, meldung = lead_mail.erneut_senden(self.s, self.s.get(KommunikationLog, eb.id))
        self.assertFalse(ok)
        self.assertIn("unzustellbar", meldung)
        # neue Mails in der Zwischenzeit warten ebenfalls
        dritte = kern.mail_planen(self.s, v, "disqualifiziert")
        self.assertEqual(dritte.status, "wartet_adresse")
        # Hauptboard: Lead ganz oben mit „E-Mail falsch“ (Vertrag L1)
        r = self.client.get("/lead-management/hauptboard")
        self.assertEqual(r.status_code, 200)
        if "E-Mail falsch" in r.text and f'data-vorgang="{v.id}"' in r.text:
            erste = r.text.index('data-vorgang="')
            self.assertEqual(r.text[erste:].split('"', 2)[1], str(v.id), "Bounce-Lead nicht ganz oben")
        # derselbe Bericht noch einmal → bekannt (Dedup über graph_id)
        ergebnis, gelesen = self.lauf([n])
        self.assertIn("bekannt=1", ergebnis["ergebnis"])
        # Adressänderung gibt frei
        kunde = self.s.get(Kunde, v.kunde_id)
        kunde.email = "v29l2-neu-de@test.invalid"
        self.s.flush()
        self.assertEqual(lead_mail.adresse_geaendert(self.s, v), 2)
        self.s.commit()
        self.s.expire_all()
        v = self.s.get(Vorgang, v.id)
        self.assertIsNone(v.email_status)
        self.assertEqual(v.email_status_grund, "")
        z = self.s.get(KommunikationLog, zweite.id)
        self.assertEqual((z.status, z.an, z.versuche), ("geplant", "v29l2-neu-de@test.invalid", 0))
        # ursprüngliche Fälligkeit (morgen) bleibt – keine vorgezogene Kaskaden-Mail [ANNAHME]
        self.assertGreater(z.geplant_am, datetime.now() + timedelta(hours=20))
        self.assertIsNone(lead_mail.kartei_hinweis(self.s, v))
        self.assertTrue(any("E-Mail-Adresse geändert" in a for a in self.aktivitaeten(v.id)))

    def test_ndr_en_terminbestaetigung_html(self):
        adresse = "v29l2-bounce-en@test.invalid"
        v = self.lead(51, email=adresse, phase="terminiert")
        t = self.termin(v, self.horst.id)
        e = kern.mail_planen(self.s, v, "terminbestaetigung", termin=t)
        lead_mail.rendern(self.s, e)
        e.status = "gesendet"
        self.s.commit()
        n = ndr_aus_fixture("ndr_exchange_en.eml", f"{PRAEFIX}-ndr-en-{v.id}", kundenadresse=adresse, eintrag_id=e.id,
                            termin_datum=t.beginn.strftime("%d.%m.%Y"), termin_uhrzeit=t.beginn.strftime("%H:%M"))
        self.assertEqual(n["body"]["contentType"], "html")
        text = lead_mail_abruf.html_zu_text(n["body"]["content"])
        self.assertEqual(lead_mail_abruf.ndr_empfaenger(text, {}, {"termin@friondo.invalid"}), adresse)
        ergebnis, _ = self.lauf([n])
        self.assertIn("bounce=1", ergebnis["ergebnis"])
        self.s.expire_all()
        v = self.s.get(Vorgang, v.id)
        self.assertEqual(v.email_status, "ungueltig")
        self.assertEqual(v.lead_phase, "terminiert")      # kein Phasenrückfall [ANNAHME]
        self.assertIn("Unzustellbar", self.s.get(KommunikationLog, e.id).fehler_text)

    def test_kundenantwort_und_unklar(self):
        adresse = "v29l2-antwort@test.invalid"
        v = self.lead(52, email=adresse, phase="nicht_erreicht")
        eb = self.s.query(KommunikationLog).filter_by(vorgang_id=v.id).first()
        lead_mail.rendern(self.s, eb)
        eb.status = "gesendet"
        self.s.commit()
        antwort = {"id": f"{PRAEFIX}-antwort-{v.id}", "subject": "AW: " + eb.betreff,
                   "from": {"emailAddress": {"address": adresse}},
                   "receivedDateTime": "2026-10-08T08:00:00Z",
                   "body": {"contentType": "text", "content": "Bitte rufen Sie mich nachmittags an."}}
        unklar = {"id": f"{PRAEFIX}-unklar-1", "subject": "Newsletter",
                  "from": {"emailAddress": {"address": "werbung@fremd.invalid"}},
                  "body": {"contentType": "text", "content": "Angebot der Woche"}}
        ergebnis, gelesen = self.lauf([antwort, unklar])
        self.assertIn("antwort=1", ergebnis["ergebnis"])
        self.s.expire_all()
        v = self.s.get(Vorgang, v.id)
        self.assertTrue(any(a.startswith(f"Antwort von {adresse}") for a in self.aktivitaeten(v.id)))
        self.assertIsNotNone(v.naechste_aktion_am)
        self.assertEqual(v.lead_phase, "nicht_erreicht")     # kein Wecken mehr [ANNAHME]
        self.assertFalse(self.s.query(Benachrichtigung).filter(
            Benachrichtigung.link == f"/lead-management/lead/{v.id}",
            Benachrichtigung.text.like("Antwort-Mail%")).count())   # Glocke kundenantwort gesperrt
        self.assertEqual(self.s.query(LeadPosteingang).filter_by(graph_id=antwort["id"]).one().vorgang_id, v.id)
        # Demo-Modus: nicht zuordenbare Fremdmail bleibt ungelesen liegen (uebersprungen),
        # außerhalb des Demo-Modus landet sie in „Posteingang unklar“
        self.assertEqual(ergebnis["ergebnis"].count("unklar=1"), 0)
        self.assertNotIn(unklar["id"], gelesen)
        with db.kurz() as s:
            self.assertEqual(lead_mail_abruf.nachricht_verarbeiten(s, dict(unklar), demo=False, eigene=set()), "unklar")
            s.query(LeadPosteingang).filter_by(graph_id=unklar["id"]).delete()
        # lead_parser (leads@) nutzt dieselbe Verbuchung – mit Betreff „Rückruf V<Nr>“
        self.assertEqual(lead_parser.mail_verarbeiten(self.s, f"{PRAEFIX}-parser-{v.id}", adresse,
                                                      f"Rückruf V{v.id}", "Gern morgen"), "antwort")
        self.s.expire_all()
        self.assertEqual(self.s.get(Vorgang, v.id).lead_phase, "nicht_erreicht")


# --- (n) Scheduler: 14 Läufe, Pool-Invariante ---------------------------------------------

class SchedulerLaeufe(unittest.TestCase):
    def test_vierzehn_laeufe_und_invariante(self):
        with db.kurz() as s:
            from app.models import SchedulerStatus
            vorher = {z.name for z in s.query(SchedulerStatus)}
        scheduler.zuruecksetzen_fuer_tests()
        try:
            for modul in (monday_sync, mail_sync, ablauf_pruefung, benachrichtigungen, lead_parser,
                          kern, geocoding, lead_mail, lead_mail_abruf):
                modul.scheduler_starten()
            betrieb.scheduler_registrieren()
            namen = {lauf.name for lauf in scheduler.alle()}
            self.assertEqual(len(namen), 14, namen)
            self.assertIn("lead-mail-abruf", namen)
            lauf = scheduler.holen("lead-mail-abruf")
            self.assertEqual((lauf.intervall_s, lauf.start_verzoegerung_s), (120, 270))
            self.assertTrue(lauf.beschreibung)
            self.assertIsNone(lauf.thread)
            ok, text = db.pool_invariante(scheduler.anzahl())
            self.assertTrue(ok, text)
            self.assertIn("Scheduler 14", text)
            with mock.patch.object(graph_versand, "konfiguriert", return_value=False):
                self.assertIn("inaktiv (Graph nicht eingerichtet)", lauf.als_dict()["zustand"])
                erg = scheduler.ausfuehren("lead-mail-abruf")
            self.assertTrue(erg["uebersprungen"])
            with mock.patch.object(graph_versand, "konfiguriert", return_value=True), \
                    mock.patch.object(graph_versand, "_token", return_value=None):
                erg = scheduler.ausfuehren("lead-mail-abruf")
            self.assertTrue(erg["ok"], erg)
            self.assertIn(lead_mail_abruf.NICHT_ANGEMELDET, erg["ergebnis"])
            quelle = Path(lead_mail_abruf.__file__).read_text(encoding="utf-8")
            self.assertNotIn("threading.Thread(", quelle)
        finally:
            scheduler.zuruecksetzen_fuer_tests()
            for modul in (monday_sync, mail_sync, ablauf_pruefung, benachrichtigungen, lead_parser,
                          kern, geocoding, lead_mail, lead_mail_abruf):
                modul.scheduler_starten()
            betrieb.scheduler_registrieren()
            with db.kurz() as s:
                from app.models import SchedulerStatus
                for zeile in s.query(SchedulerStatus):
                    if zeile.name == "lead-mail-abruf" and zeile.name not in vorher:
                        s.delete(zeile)


if __name__ == "__main__":
    unittest.main()
