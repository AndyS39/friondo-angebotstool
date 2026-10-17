# v38 (PLAN_V23 Phase 204, Agent V): Mobil – untere Leiste mit „Vergangene Termine“ statt
# „Kunden“, Seite /leads/vergangene (Außendienst; ID/Admin → /leads#vergangene), Dialog
# „Termin nicht stattgefunden“ (POST /leads/termin/{id}/ausgefallen): Folge 1 → no_show, Phase
# Kontaktiert, To-Do fällig heute + Glocke beim Leadmanager, Wiedervorlage heute, Chat-Eintrag,
# Termin aus den Listen, keine Kundenmail; Folge 2 mit Pflichtgrund → abgesagt, Phase
# Disqualifiziert, Chat-Eintrag mit AD-Name, keine Mail (Warteschlange leer); AD an fremdem
# Termin 403; Prüfungen ohne Nebenwirkung. Läuft gegen die DB-Kopie, Präfix V38MB.
import unittest
from datetime import date, datetime, timedelta
from unittest import mock

from fastapi.testclient import TestClient

from app import auth, kalender, lead_boards, lead_termin_ausfall, mein_tag, objekte
from app.db import SessionLocal
from app.main import app
from app.models import (Angebot, Benachrichtigung, Benutzer, BenutzerEinstellung, Erfassung, KommunikationLog,
                        Kunde, Lead, LeadAktivitaet, Todo, Vorgang, VorgangObjekt, VorgangsNotiz, VotTermin)

PRAEFIX = "V38MB"
CSS = "app/static/mein_tag.css"
JS = "app/static/mein_tag.js"


def _client(benutzer_id: int) -> TestClient:
    c = TestClient(app, follow_redirects=False)
    c.cookies.set(auth.COOKIE_NAME, auth.cookie_wert(benutzer_id))
    return c


def _um(tag: date, stunde: int, minute: int = 0) -> datetime:
    return datetime(tag.year, tag.month, tag.day, stunde, minute)


def _freie_benutzer_id(s) -> int:
    from sqlalchemy import func
    werte = [s.query(func.max(Benutzer.id)).scalar(), s.query(func.max(Vorgang.ad_id)).scalar(),
             s.query(func.max(Vorgang.wiedervorlage_benutzer_id)).scalar(),
             s.query(func.max(Vorgang.leadmanager_id)).scalar(),
             s.query(func.max(Lead.benutzer_id)).scalar(), s.query(func.max(VotTermin.ad_id)).scalar(),
             s.query(func.max(Erfassung.benutzer_id)).scalar(), s.query(func.max(Todo.an_benutzer_id)).scalar()]
    return max([int(w or 0) for w in werte]) + 1


class MobilV38(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.heute = date.today()
        s = SessionLocal()
        try:
            cls._aufraeumen(s)
            naechste_id = [_freie_benutzer_id(s)]

            def benutzer(name, rolle, **extra):
                naechste_id[0] += 1
                b = Benutzer(id=naechste_id[0], name=f"{PRAEFIX} {name}", rolle=rolle, aktiv=True,
                             email=f"{name.lower()}@v38mb.local", pin_hash=auth.pin_hash("4321"), **extra)
                s.add(b)
                s.flush()
                return b.id

            cls.ad1_id = benutzer("Rene", "aussendienst", vorname="Rene")
            cls.ad2_id = benutzer("Fremd", "aussendienst")
            cls.lm_id = benutzer("Leadmanager", "innendienst", leadmanager=True)
            cls.id_id = benutzer("Innendienst", "innendienst")

            def kunde(nachname, interesse="WP", **extra):
                k = Kunde(anrede="Herr", vorname="Peter", nachname=f"{PRAEFIX} {nachname}", strasse="Testweg 1",
                          plz="47798", ort="Krefeld", telefon="0203 555 4711", email=f"{nachname.lower()}@kunde.example",
                          interesse=interesse, **extra)
                s.add(k)
                s.flush()
                return k

            def vorgang(k, ad_id, **extra):
                v = Vorgang(kunde_id=k.id, ad_id=ad_id, lead_phase="terminiert", leadmanager_id=cls.lm_id, **extra)
                s.add(v)
                s.flush()
                # SQLite vergibt IDs neu: verwaiste Zeilen abgebrochener Testläufe anderer Dateien (Mails,
                # To-Dos, Aktivitäten, Notizen) würden sonst für diesen Vorgang zählen (Befund 17.10.2026)
                for tabelle in (KommunikationLog, Todo, LeadAktivitaet, VorgangsNotiz):
                    s.query(tabelle).filter(tabelle.vorgang_id == v.id).delete(synchronize_session=False)
                objekte.hauptobjekt(s, v.id, anlegen=True, kunde=k)
                return v

            def termin(v, beginn, ad_id, objekt_id=None, status="geplant", typ="vot"):
                haupt = objekte.hauptobjekt(s, v.id)
                t = VotTermin(vorgang_id=v.id, ad_id=ad_id, beginn=beginn, ende=beginn + timedelta(minutes=90),
                              status=status, quelle="assistent", typ=typ, medium="vor_ort",
                              objekt_id=objekt_id or (haupt.id if haupt else None), adresse="")
                s.add(t)
                s.flush()
                return t

            heute = cls.heute
            k = kunde("Mueller")
            cls.v_heute = vorgang(k, cls.ad1_id)
            cls.t_heute = termin(cls.v_heute, _um(heute, 9, 30), cls.ad1_id)
            k = kunde("Schmidt", interesse="WP,PV")
            cls.v_gestern = vorgang(k, cls.ad1_id)
            cls.objekt2 = objekte.objekt_anlegen(s, cls.v_gestern, strasse="Nebenweg 7", plz="47798", ort="Krefeld",
                                                 bezeichnung="Halle Nord", interessen=["PV"])
            cls.t_gestern = termin(cls.v_gestern, _um(heute - timedelta(days=1), 14), cls.ad1_id, objekt_id=cls.objekt2.id)
            k = kunde("Fremd")
            cls.v_fremd = vorgang(k, cls.ad2_id)
            cls.t_fremd = termin(cls.v_fremd, _um(heute - timedelta(days=3), 10), cls.ad2_id)
            k = kunde("OhneLM")
            cls.v_ohne_lm = vorgang(k, cls.ad1_id)
            cls.v_ohne_lm.leadmanager_id = None
            cls.t_ohne_lm = termin(cls.v_ohne_lm, _um(heute - timedelta(days=2), 11), cls.ad1_id)
            k = kunde("Pruefung")
            cls.v_pruef = vorgang(k, cls.ad1_id)
            cls.t_pruef = termin(cls.v_pruef, _um(heute - timedelta(days=4), 15), cls.ad1_id)
            k = kunde("Innen")
            cls.v_innen = vorgang(k, cls.ad2_id)
            cls.t_innen = termin(cls.v_innen, _um(heute, 16), cls.ad2_id)
            # Nachtrag 17.10.2026 (Rückfrage 18 R6): bestehende Wiedervorlagen – überfällig bleibt, künftige wird vorgezogen
            k = kunde("WvAlt")
            cls.v_wv_alt = vorgang(k, cls.ad1_id, wiedervorlage_am=_um(heute - timedelta(days=3), 0),
                                   wiedervorlage_benutzer_id=cls.ad1_id, wiedervorlage_art="nochmal_anrufen")
            cls.t_wv_alt = termin(cls.v_wv_alt, _um(heute - timedelta(days=1), 10), cls.ad1_id)
            k = kunde("WvNeu")
            cls.v_wv_neu = vorgang(k, cls.ad1_id, wiedervorlage_am=_um(heute + timedelta(days=5), 0),
                                   wiedervorlage_benutzer_id=cls.ad1_id, wiedervorlage_art="nochmal_anrufen")
            cls.t_wv_neu = termin(cls.v_wv_neu, _um(heute - timedelta(days=1), 11), cls.ad1_id)
            s.commit()
            cls.ids = {"heute": cls.v_heute.id, "gestern": cls.v_gestern.id, "fremd": cls.v_fremd.id,
                       "ohne_lm": cls.v_ohne_lm.id, "pruef": cls.v_pruef.id, "innen": cls.v_innen.id,
                       "wv_alt": cls.v_wv_alt.id, "wv_neu": cls.v_wv_neu.id}
            cls.tids = {"heute": cls.t_heute.id, "gestern": cls.t_gestern.id, "fremd": cls.t_fremd.id,
                        "ohne_lm": cls.t_ohne_lm.id, "pruef": cls.t_pruef.id, "innen": cls.t_innen.id,
                        "wv_alt": cls.t_wv_alt.id, "wv_neu": cls.t_wv_neu.id}
        finally:
            s.close()
        cls.ad1 = _client(cls.ad1_id)
        cls.ad2 = _client(cls.ad2_id)
        cls.lm = _client(cls.lm_id)
        cls.innen = _client(cls.id_id)
        cls.admin = _client(1)

    @classmethod
    def _aufraeumen(cls, s):
        ids = [k.id for k in s.query(Kunde).filter(Kunde.nachname.like(f"{PRAEFIX} %"))]
        if ids:
            vids = [v.id for v in s.query(Vorgang).filter(Vorgang.kunde_id.in_(ids))]
            if vids:
                for a in s.query(Angebot).filter(Angebot.vorgang_id.in_(vids)):
                    s.delete(a)
                for tabelle in (VotTermin, VorgangsNotiz, Erfassung, VorgangObjekt, LeadAktivitaet,
                                KommunikationLog, Todo):
                    s.query(tabelle).filter(tabelle.vorgang_id.in_(vids)).delete(synchronize_session=False)
                s.query(Vorgang).filter(Vorgang.id.in_(vids)).delete(synchronize_session=False)
            s.query(Kunde).filter(Kunde.id.in_(ids)).delete(synchronize_session=False)
        bids = [b.id for b in s.query(Benutzer).filter(Benutzer.name.like(f"{PRAEFIX} %"))]
        if bids:
            for tabelle in (Benachrichtigung,):
                s.query(tabelle).filter(tabelle.benutzer_id.in_(bids)).delete(synchronize_session=False)
            s.query(Todo).filter(Todo.an_benutzer_id.in_(bids)).delete(synchronize_session=False)
            s.query(BenutzerEinstellung).filter(BenutzerEinstellung.benutzer_id.in_(bids)).delete(synchronize_session=False)
            s.query(Benutzer).filter(Benutzer.id.in_(bids)).delete(synchronize_session=False)
        s.commit()

    @classmethod
    def tearDownClass(cls):
        s = SessionLocal()
        try:
            cls._aufraeumen(s)
        finally:
            s.close()

    def _mails(self, s, vorgang_id) -> int:
        return s.query(KommunikationLog).filter(KommunikationLog.vorgang_id == vorgang_id).count()

    # --- untere Leiste --------------------------------------------------------------------------
    def test_a_leiste_vergangene_statt_kunden(self):
        html = self.ad1.get("/leads").text
        leiste = html[html.index('class="mt-leiste"'):html.index("</nav>", html.index('class="mt-leiste"'))]
        for href, text in (("/leads", "Mein Tag"), ("/lead-management/meine-termine", "Kalender"),
                           ("/leads/wiedervorlagen", "Wiedervorlage"), ("/leads/vergangene", "Vergangene Termine")):
            self.assertIn(f'href="{href}"', leiste)
            self.assertIn(text, leiste)
        self.assertEqual(leiste.count("mt-leiste-eintrag"), 4)
        self.assertNotIn('href="/suche"', leiste)
        self.assertNotIn("Kunden</a>", leiste)
        self.assertNotIn("data-mt-leiste-kunden", html)
        self.assertIn('class="mt-leiste-kurz" aria-hidden="true">Vergangen</span>', leiste)
        self.assertIn("data-mt-leiste-vergangene", leiste)
        self.assertIn('href="/leads" class="mt-leiste-eintrag aktiv" aria-current="page"', leiste)
        seite = self.ad1.get("/leads/vergangene").text
        self.assertIn('href="/leads/vergangene" class="mt-leiste-eintrag aktiv" aria-current="page"', seite)
        # Suche bleibt über die Lupe der Kopfzeile erreichbar
        self.assertIn('class="kopf-suche"', html)
        css = open(CSS, encoding="utf-8").read()
        self.assertIn(".mt-leiste-kurz { display: none; }", css)
        self.assertIn("@media (max-width: 360px)", css)
        mobil = css[css.index("@media (max-width: 360px)"):]
        self.assertIn(".mt-leiste-lang { display: none; }", mobil)
        self.assertNotRegex(css.replace("rgba(7, 13, 26, 0.55)", ""), r"#[0-9a-fA-F]{3,6}\b")
        # kein Überfällig-Block mehr in Mein Tag; Hinweis-Link auf die Seite
        self.assertNotIn('id="termine-ueberfaellig"', html)
        self.assertNotIn("überfällig", html)
        self.assertIn('class="mt-vg-hinweis-link" href="/leads/vergangene"', html)

    # --- Seite „Vergangene Termine“ --------------------------------------------------------------
    def test_b_seite_vergangene(self):
        seite = self.ad1.get("/leads/vergangene")
        self.assertEqual(seite.status_code, 200)
        html = seite.text
        self.assertIn('class="mt-zurueck" href="/leads"', html)
        self.assertIn("Mein Tag</a>", html)
        self.assertNotIn("zurueck-knopf", html)
        self.assertIn("<h1>Vergangene Termine</h1>", html)
        self.assertIn('placeholder="Nach Name suchen"', html)
        self.assertIn("data-mt-vergangene", html)
        self.assertIn("ohne Erfassung", html)
        gestern = self.heute - timedelta(days=1)
        self.assertIn(f'data-tag="{gestern.isoformat()}"', html)
        self.assertIn(f'<span class="mt-wd">{mein_tag.wochentag_kurz(gestern)}</span><span class="mt-nr">{gestern.day}</span>', html)
        self.assertIn(mein_tag.datum_lang(gestern), html)
        karte = html[html.index(f'data-termin="{self.tids["gestern"]}"'):]
        karte = karte[:karte.index("</article>")]
        self.assertIn('<span class="mt-uhr">14:00</span>', karte)
        self.assertIn(f"Herr Peter {PRAEFIX} Schmidt", karte)
        self.assertIn("Photovoltaik, Vor-Ort-Termin", karte)                  # Sparte des Objekts, Termintyp
        self.assertIn('<span class="mt-objekt">Halle Nord</span>', karte)       # Objektbezeichnung
        self.assertIn("Nebenweg 7, 47798 Krefeld", karte)                       # Objektadresse
        self.assertIn(f'href="/erfassung/sparten?kunde_id={self.v_gestern.kunde_id}&amp;objekt_id={self.objekt2.id}"', karte)
        self.assertIn("Erfassung starten", karte)
        self.assertIn(f'href="/vorgaenge/{self.ids["gestern"]}">Akte</a>', karte)
        self.assertIn("Termin nicht stattgefunden", karte)
        self.assertIn(f'data-ta-url="/leads/termin/{self.tids["gestern"]}/ausgefallen"', karte)
        self.assertIn("· gestern", karte)
        # nicht enthalten: heutiger Termin, fremder Vertriebler
        self.assertNotIn(f'data-termin="{self.tids["heute"]}"', html)
        self.assertNotIn(f"{PRAEFIX} Fremd", html)
        # neueste zuerst: gestern vor „vor 2 Tagen“ (OhneLM) vor „vor 4 Tagen“ (Pruefung)
        self.assertLess(html.index(f'data-termin="{self.tids["gestern"]}"'), html.index(f'data-termin="{self.tids["ohne_lm"]}"'))
        self.assertLess(html.index(f'data-termin="{self.tids["ohne_lm"]}"'), html.index(f'data-termin="{self.tids["pruef"]}"'))
        self.assertIn("Keine vergangenen Termine ohne Erfassung", html)
        self.assertIn("Alles erfasst.", html)
        self.assertIn("data-mt-vg-leer hidden", html)
        self.assertEqual(html.count('id="termin-ausgefallen"'), 1)
        # Leerzustand sichtbar beim Vertriebler ohne vergangene Termine
        leer = self.ad2.get("/leads/vergangene").text
        self.assertIn("<span data-mt-vg-zahl>1</span> ohne Erfassung", leer)   # AD2: nur sein eigener (Fremd)
        # Innendienst/Admin: Desktop-Gruppe
        for client in (self.innen, self.admin):
            antwort = client.get("/leads/vergangene")
            self.assertEqual(antwort.status_code, 303)
            self.assertEqual(antwort.headers["location"], "/leads#vergangene")
        js = open(JS, encoding="utf-8").read()
        for teil in ("data-mt-vergangene", "data-mt-vg-tag", "data-mt-vg-zahl", "data-ta-dialog", "showModal", "ta:gespeichert"):
            self.assertIn(teil, js)

    # --- Dialog: Markup und Prüfungen -------------------------------------------------------------
    def test_c_dialog_markup_und_pruefungen(self):
        html = self.ad1.get("/leads").text
        dialog = html[html.index('id="termin-ausgefallen"'):html.index("</dialog>")]
        for text in ("Termin nicht stattgefunden", "Kunde nicht angetroffen", "Kunde hat sich anders entschieden",
                     "Sonstiges", "Neuen Termin vereinbaren lassen", "Kunde möchte keinen neuen Termin",
                     "Kunden disqualifizieren?", 'name="dq_grund"', 'name="bemerkung"', "diktat-knopf",
                     "data-ta-vorbelegung", "Abbrechen"):
            self.assertIn(text, dialog)
        self.assertIn('value="kein Bedarf, nur Information"', dialog)        # Gründe aus dem Logik-Blatt
        self.assertIn('data-freitext-pflicht="1">Sonstiges', dialog)
        self.assertNotIn("Zurückstellen", dialog)                             # keine dritte Option
        # Karten tragen den Knopf (Als Nächstes/Heute); Vorbelegung laut Plan
        self.assertIn(f'data-ta-url="/leads/termin/{self.tids["heute"]}/ausgefallen"', html)
        self.assertEqual(lead_termin_ausfall.FOLGE_VORBELEGUNG["nicht_angetroffen"], "neuer_termin")
        self.assertEqual(lead_termin_ausfall.FOLGE_VORBELEGUNG["anders_entschieden"], "kein_termin")
        # Prüfungen ohne Nebenwirkung
        url = f"/leads/termin/{self.tids['pruef']}/ausgefallen"
        kopf = {"Accept": "application/json"}
        self.assertEqual(self.ad1.post(url, data={"grund": "sonstiges", "folge": "neuer_termin"}, headers=kopf).status_code, 400)
        self.assertEqual(self.ad1.post(url, data={"grund": "unsinn", "folge": "neuer_termin"}, headers=kopf).status_code, 400)
        self.assertEqual(self.ad1.post(url, data={"grund": "nicht_angetroffen", "folge": "kein_termin"}, headers=kopf).status_code, 400)
        r = self.ad1.post(url, data={"grund": "nicht_angetroffen", "folge": "kein_termin", "dq_grund": "Sonstiges"}, headers=kopf)
        self.assertEqual(r.status_code, 400)
        self.assertIn("Freitext", r.json()["meldung"])
        self.assertEqual(self.ad1.post(url, data={"grund": "nicht_angetroffen", "folge": "egal"}, headers=kopf).status_code, 400)
        s = SessionLocal()
        try:
            t = s.get(VotTermin, self.tids["pruef"])
            self.assertEqual(t.status, "geplant")
            self.assertIsNone(t.ausfall_grund)
            self.assertEqual(s.get(Vorgang, self.ids["pruef"]).lead_phase, "terminiert")
            self.assertEqual(s.query(Todo).filter(Todo.vorgang_id == self.ids["pruef"]).count(), 0)
            self.assertEqual(s.query(VorgangsNotiz).filter(VorgangsNotiz.vorgang_id == self.ids["pruef"]).count(), 0)
        finally:
            s.close()
        # Rechte: AD an fremdem Termin 403 (JSON) bzw. 303 mit Meldung; unbekannter Termin 404
        self.assertEqual(self.ad2.post(f"/leads/termin/{self.tids['pruef']}/ausgefallen",
                                       data={"grund": "nicht_angetroffen", "folge": "neuer_termin"}, headers=kopf).status_code, 403)
        r = self.ad2.post(f"/leads/termin/{self.tids['pruef']}/ausgefallen",
                          data={"grund": "nicht_angetroffen", "folge": "neuer_termin", "zurueck": "/leads/vergangene"})
        self.assertEqual(r.status_code, 303)
        self.assertIn("/leads/vergangene?meldung=", r.headers["location"])
        self.assertEqual(self.ad1.post("/leads/termin/999999999/ausgefallen", data={"grund": "nicht_angetroffen"}, headers=kopf).status_code, 404)
        s = SessionLocal()
        try:
            self.assertEqual(s.get(VotTermin, self.tids["pruef"]).status, "geplant")
            # Rechte-Funktion direkt: Innendienst/Leadmanager alle, AD nur eigene
            t = s.get(VotTermin, self.tids["pruef"])
            self.assertTrue(lead_termin_ausfall.erlaubt(s, s.get(Benutzer, self.id_id), t))
            self.assertTrue(lead_termin_ausfall.erlaubt(s, s.get(Benutzer, self.lm_id), t))
            self.assertTrue(lead_termin_ausfall.erlaubt(s, s.get(Benutzer, self.ad1_id), t))
            self.assertFalse(lead_termin_ausfall.erlaubt(s, s.get(Benutzer, self.ad2_id), t))
        finally:
            s.close()

    # --- Folge 1: Neuen Termin vereinbaren lassen -------------------------------------------------
    def test_d_folge_neuer_termin(self):
        s = SessionLocal()
        try:
            mails_vorher = self._mails(s, self.ids["heute"])
            glocken_vorher = s.query(Benachrichtigung).filter(Benachrichtigung.benutzer_id == self.lm_id).count()
        finally:
            s.close()
        with mock.patch.object(kalender, "termin_loeschen", wraps=kalender.termin_loeschen) as storno:
            antwort = self.ad1.post(f"/leads/termin/{self.tids['heute']}/ausgefallen",
                                    data={"grund": "nicht_angetroffen", "bemerkung": "Niemand da, Nachbar sagt Urlaub",
                                          "folge": "neuer_termin", "zurueck": "/leads"},
                                    headers={"Accept": "application/json"})
        self.assertEqual(antwort.status_code, 200, antwort.text)
        daten = antwort.json()
        self.assertTrue(daten["ok"])
        self.assertEqual(daten["meldung"], "Weitergegeben an das Leadmanagement")
        self.assertEqual(daten["folge"], "neuer_termin")
        self.assertEqual(daten["status"], "no_show")
        self.assertEqual(daten["todo_an"], self.lm_id)
        self.assertEqual(storno.call_count, 1)                                  # Outlook-Storno über den Bestandsweg
        s = SessionLocal()
        try:
            t = s.get(VotTermin, self.tids["heute"])
            v = s.get(Vorgang, self.ids["heute"])
            self.assertEqual(t.status, "no_show")
            self.assertEqual(t.ausfall_grund, "nicht_angetroffen")
            self.assertEqual(t.ausfall_bemerkung, "Niemand da, Nachbar sagt Urlaub")
            self.assertIn("Kunde nicht angetroffen", t.grund_text)
            self.assertEqual(v.lead_phase, "qualifiziert")                          # Label „Kontaktiert“ (v25)
            from app import leadmanagement_logik
            self.assertEqual(lead_boards.status_label(leadmanagement_logik.hole_logik(), "qualifiziert")[0], "Kontaktiert")
            # To-Do an den Leadmanager, fällig heute, Glocke art=todo
            todo = s.query(Todo).filter(Todo.vorgang_id == v.id).one()
            self.assertEqual(todo.titel, f"Neuen Termin vereinbaren: {s.get(Kunde, v.kunde_id).anzeige_name}")
            self.assertIn(f"{PRAEFIX} Mueller", todo.titel)
            self.assertEqual(todo.an_benutzer_id, self.lm_id)
            self.assertEqual(todo.von_benutzer_id, self.ad1_id)
            self.assertEqual(todo.status, "offen")
            self.assertEqual(todo.faellig_am.date(), self.heute)
            self.assertLessEqual(todo.faellig_am, datetime.now())
            zeit = t.beginn.strftime("%d.%m. %H:%M")
            self.assertIn(f"Termin am {zeit} nicht stattgefunden (Grund: Kunde nicht angetroffen).", todo.text)
            self.assertIn("Bemerkung: Niemand da, Nachbar sagt Urlaub", todo.text)
            glocken = (s.query(Benachrichtigung).filter(Benachrichtigung.benutzer_id == self.lm_id)
                       .order_by(Benachrichtigung.id.desc()).all())
            self.assertEqual(len(glocken), glocken_vorher + 1)
            self.assertEqual(glocken[0].art, "todo")
            self.assertIn("Neuen Termin vereinbaren", glocken[0].text)
            # Wiedervorlage des Vorgangs auf heute [ANNAHME], Verantwortlicher = Leadmanager
            self.assertEqual(v.wiedervorlage_am.date(), self.heute)
            self.assertEqual(v.wiedervorlage_benutzer_id, self.lm_id)
            self.assertEqual(v.wiedervorlage_art, lead_termin_ausfall.WIEDERVORLAGE_ART)
            # Chat-Eintrag, Aktivität, keine Kundenmail (Warteschlange unverändert)
            notiz = s.query(VorgangsNotiz).filter(VorgangsNotiz.vorgang_id == v.id).order_by(VorgangsNotiz.id.desc()).first()
            self.assertEqual(notiz.text, f"Termin am {t.beginn.strftime('%d.%m.')} nicht stattgefunden "
                                         "(Kunde nicht angetroffen) · neue Terminfindung durch Leadmanagement")
            self.assertEqual(notiz.benutzer_id, self.ad1_id)
            self.assertTrue(any("No-Show" in a.text for a in s.query(LeadAktivitaet).filter(LeadAktivitaet.vorgang_id == v.id)))
            self.assertEqual(self._mails(s, v.id), mails_vorher)
            self.assertEqual(s.query(KommunikationLog).filter(KommunikationLog.vorgang_id == v.id,
                                                              KommunikationLog.status == "geplant").count(), 0)
            # Termin verschwindet aus allen Listen
            daten = mein_tag.termine(s, s.get(Benutzer, self.ad1_id))
            self.assertNotIn(t.id, [k["termin"].id for k in daten["heute"]])
            self.assertNotIn(t.id, [k["termin"].id for k in daten["vergangene"]])
        finally:
            s.close()
        html = self.ad1.get("/leads").text
        self.assertNotIn(f'data-termin="{self.tids["heute"]}"', html)
        self.assertNotIn(f'data-ta-url="/leads/termin/{self.tids["heute"]}/ausgefallen"', html)
        # zweite Meldung am selben Termin: nicht mehr offen
        r = self.ad1.post(f"/leads/termin/{self.tids['heute']}/ausgefallen",
                          data={"grund": "nicht_angetroffen", "folge": "neuer_termin"}, headers={"Accept": "application/json"})
        self.assertEqual(r.status_code, 400)
        self.assertIn("nicht mehr offen", r.json()["meldung"])

    # --- Folge 1 ohne zugewiesenen Leadmanager [ANNAHME V-1] ----------------------------------------
    def test_e_folge_ohne_leadmanager(self):
        antwort = self.ad1.post(f"/leads/termin/{self.tids['ohne_lm']}/ausgefallen",
                                data={"grund": "sonstiges", "grund_text": "Straße gesperrt", "folge": "neuer_termin"},
                                headers={"Accept": "application/json"})
        self.assertEqual(antwort.status_code, 200, antwort.text)
        daten = antwort.json()
        self.assertEqual(daten["hinweis"], lead_termin_ausfall.HINWEIS_OHNE_LEADMANAGER)
        s = SessionLocal()
        try:
            todo = s.query(Todo).filter(Todo.vorgang_id == self.ids["ohne_lm"]).one()
            self.assertIn("kein Leadmanager zugewiesen", todo.text)
            self.assertIn("(Grund: Sonstiges: Straße gesperrt)", todo.text)
            self.assertEqual(todo.an_benutzer_id, daten["todo_an"])
            self.assertTrue(todo.an_benutzer_id)                                   # nie ohne Person (Schema)
            self.assertIsNone(s.get(Vorgang, self.ids["ohne_lm"]).leadmanager_id)  # keine Zuweisung am Vorgang
            self.assertEqual(s.get(VotTermin, self.tids["ohne_lm"]).ausfall_grund, "sonstiges")
            notiz = s.query(VorgangsNotiz).filter(VorgangsNotiz.vorgang_id == self.ids["ohne_lm"]).first()
            self.assertIn("(Sonstiges: Straße gesperrt) · neue Terminfindung durch Leadmanagement (kein Leadmanager zugewiesen)", notiz.text)
        finally:
            s.close()

    # --- Folge 2: Kunde möchte keinen neuen Termin → disqualifizieren, keine Mail -------------------
    def test_f_folge_disqualifizieren_ohne_mail(self):
        s = SessionLocal()
        try:
            mails_vorher = s.query(KommunikationLog).count()
        finally:
            s.close()
        antwort = self.ad1.post(f"/leads/termin/{self.tids['gestern']}/ausgefallen",
                                data={"grund": "anders_entschieden", "folge": "kein_termin",
                                      "dq_grund": "kein Bedarf, nur Information", "zurueck": "/leads/vergangene"},
                                headers={"Accept": "application/json"})
        self.assertEqual(antwort.status_code, 200, antwort.text)
        daten = antwort.json()
        self.assertTrue(daten["ok"])
        self.assertEqual(daten["status"], "abgesagt")
        self.assertEqual(daten["phase"], "unqualifiziert")
        self.assertIn("disqualifiziert", daten["meldung"])
        s = SessionLocal()
        try:
            t = s.get(VotTermin, self.tids["gestern"])
            v = s.get(Vorgang, self.ids["gestern"])
            self.assertEqual(t.status, "abgesagt")
            self.assertEqual(t.ausfall_grund, "anders_entschieden")
            self.assertEqual(v.lead_phase, "unqualifiziert")
            from app import leadmanagement_logik
            self.assertEqual(lead_boards.status_label(leadmanagement_logik.hole_logik(), v.lead_phase)[0], "Disqualifiziert")
            self.assertEqual(v.unqualifiziert_grund, "kein Bedarf, nur Information")
            notiz = s.query(VorgangsNotiz).filter(VorgangsNotiz.vorgang_id == v.id).order_by(VorgangsNotiz.id.desc()).first()
            self.assertEqual(notiz.text, f"Termin am {t.beginn.strftime('%d.%m.')} nicht stattgefunden "
                                         f"(Kunde hat sich anders entschieden) · Kunde disqualifiziert durch {PRAEFIX} Rene: "
                                         "kein Bedarf, nur Information")
            self.assertTrue(any("Disqualifiziert" in a.text for a in s.query(LeadAktivitaet).filter(LeadAktivitaet.vorgang_id == v.id)))
            # keine E-Mail: Warteschlange insgesamt unverändert, kein Eintrag am Vorgang
            self.assertEqual(s.query(KommunikationLog).count(), mails_vorher)
            self.assertEqual(s.query(KommunikationLog).filter(KommunikationLog.vorgang_id == v.id).count(), 0)
            self.assertEqual(s.query(Todo).filter(Todo.vorgang_id == v.id).count(), 0)   # kein To-Do bei Folge 2
            # Hauptboard-Zuordnung: unqualifiziert gehört zum Hauptboard (Disqualifiziert)
            self.assertIn(leadmanagement_logik.hole_logik().board_fuer("unqualifiziert")[0], ("haupt", "hauptboard"))
        finally:
            s.close()
        self.assertNotIn(f'data-termin="{self.tids["gestern"]}"', self.ad1.get("/leads/vergangene").text)

    # --- Innendienst/Admin dürfen jeden Termin melden; Formular-Variante mit Redirect ------------------
    def test_g_innendienst_und_redirect(self):
        r = self.innen.post(f"/leads/termin/{self.tids['innen']}/ausgefallen",
                            data={"grund": "nicht_angetroffen", "folge": "neuer_termin", "zurueck": "/leads"})
        self.assertEqual(r.status_code, 303)
        self.assertTrue(r.headers["location"].startswith("/leads?meldung="))
        self.assertIn("Leadmanagement", r.headers["location"])
        s = SessionLocal()
        try:
            self.assertEqual(s.get(VotTermin, self.tids["innen"]).status, "no_show")
        finally:
            s.close()
        # Rücksprung nur auf eigene Pfade
        self.assertEqual(leads_router_sicher("https://fremd.example/x"), "/leads")

    def test_i_wiedervorlage_nur_vorziehen(self):
        """Nachtrag 17.10.2026 (Rückfrage 18 R6): „Neuen Termin vereinbaren lassen“ zieht eine leere oder
        künftige Wiedervorlage auf heute vor; eine bereits fällige/überfällige bleibt (Datum, Person, Art)."""
        from types import SimpleNamespace
        self.assertTrue(lead_termin_ausfall.wiedervorlage_vorziehen(SimpleNamespace(wiedervorlage_am=None), self.heute))
        self.assertTrue(lead_termin_ausfall.wiedervorlage_vorziehen(
            SimpleNamespace(wiedervorlage_am=_um(self.heute + timedelta(days=1), 0)), self.heute))
        self.assertFalse(lead_termin_ausfall.wiedervorlage_vorziehen(
            SimpleNamespace(wiedervorlage_am=_um(self.heute, 0)), self.heute))
        self.assertFalse(lead_termin_ausfall.wiedervorlage_vorziehen(
            SimpleNamespace(wiedervorlage_am=self.heute - timedelta(days=2)), self.heute))
        for key in ("wv_alt", "wv_neu"):
            r = self.ad1.post(f"/leads/termin/{self.tids[key]}/ausgefallen",
                              data={"grund": "nicht_angetroffen", "folge": "neuer_termin"},
                              headers={"Accept": "application/json"})
            self.assertEqual(r.status_code, 200, r.text)
        s = SessionLocal()
        try:
            alt = s.get(Vorgang, self.ids["wv_alt"])
            self.assertEqual(alt.wiedervorlage_am.date(), self.heute - timedelta(days=3))   # überfällig bleibt
            self.assertEqual(alt.wiedervorlage_benutzer_id, self.ad1_id)
            self.assertEqual(alt.wiedervorlage_art, "nochmal_anrufen")
            self.assertEqual(s.query(Todo).filter(Todo.vorgang_id == alt.id).count(), 1)     # To-Do trotzdem
            neu = s.get(Vorgang, self.ids["wv_neu"])
            self.assertEqual(neu.wiedervorlage_am.date(), self.heute)                        # vorgezogen
            self.assertEqual(neu.wiedervorlage_benutzer_id, self.lm_id)
            self.assertEqual(neu.wiedervorlage_art, lead_termin_ausfall.WIEDERVORLAGE_ART)
        finally:
            s.close()

    def test_h_testphase_sperrt_das_melden_nicht(self):
        """Der Testphase-Schalter terminierung_aktiv (v31) sperrt nur Neubuchungen – die Kopie
        läuft mit „aus“, und die Meldungen oben sind trotzdem durchgegangen."""
        from app import lead_v5, leadmanagement as kern
        s = SessionLocal()
        try:
            self.assertEqual((kern.parameter_holen(s, "terminierung_aktiv", "aus") or "aus").strip(), "aus")
            self.assertFalse(lead_v5.terminierung_aktiv(s))
        finally:
            s.close()


def leads_router_sicher(wert: str) -> str:
    from app.routers import leads
    return leads._sicheres_ziel(wert, "/leads")


if __name__ == "__main__":
    unittest.main()
