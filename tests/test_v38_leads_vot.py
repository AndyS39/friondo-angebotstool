# v38 (PLAN_V23 Phase 203, Agent V): Leads VOT Desktop – Kanalzelle = Badge + Pfeil mit Menü
# (POST /leads/{id}/kanal liefert bei Accept: application/json das neue Badge), Gruppe
# „Vergangene Termine · n“ unten (zugeklappt, vot_termine der letzten 180 Tage ohne
# abgeschlossene Erfassung, neueste zuerst, „vor n Tagen“), „überfällig“ gestrichen (kein Label,
# keine Einsortierung in „Heute“, kein v15-Banner, keine Ansicht „nur überfällige“), AD nur eigene.
# Läuft gegen die DB-Kopie (DB_PFAD_OVERRIDE), räumt alles mit Präfix V38LV auf.
import re
import unittest
from datetime import date, datetime, timedelta

from fastapi.testclient import TestClient

from app import auth, mein_tag, objekte
from app.db import SessionLocal
from app.main import app
from app.models import (Angebot, Benutzer, BenutzerEinstellung, Erfassung, Kunde, Lead, LeadAktivitaet,
                        Vorgang, VorgangObjekt, VorgangsNotiz, VotTermin)
from app.routers import leads as leads_router

PRAEFIX = "V38LV"
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
             s.query(func.max(Lead.benutzer_id)).scalar(), s.query(func.max(VotTermin.ad_id)).scalar(),
             s.query(func.max(Erfassung.benutzer_id)).scalar()]
    return max([int(w or 0) for w in werte]) + 1


def _gruppe(html: str, key: str) -> str:
    start = html.index(f'data-gruppe="{key}"')
    start = html.rindex("<details", 0, start)
    return html[start:html.index("</details>", start)]


class LeadsVotV38(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.heute = date.today()
        s = SessionLocal()
        try:
            cls._aufraeumen(s)
            naechste_id = [_freie_benutzer_id(s)]

            def benutzer(name, rolle):
                naechste_id[0] += 1
                b = Benutzer(id=naechste_id[0], name=f"{PRAEFIX} {name}", rolle=rolle, aktiv=True,
                             email=f"{name.lower()}@v38lv.local", pin_hash=auth.pin_hash("4321"))
                s.add(b)
                s.flush()
                return b.id

            cls.ad1_id = benutzer("Rene", "aussendienst")
            cls.ad2_id = benutzer("Fremd", "aussendienst")
            cls.id_id = benutzer("Innendienst", "innendienst")

            def kunde(nachname, interesse="WP", **extra):
                k = Kunde(anrede="Herr", vorname="Peter", nachname=f"{PRAEFIX} {nachname}", strasse="Testweg 1",
                          plz="47798", ort="Krefeld", telefon="0203 555 4711", interesse=interesse, **extra)
                s.add(k)
                s.flush()
                return k

            def lead(nachname, k, ad_id, vot, interesse="WP", kanal=""):
                l = Lead(monday_item_id=f"{PRAEFIX}-{nachname}", vorname="Peter", nachname=f"{PRAEFIX} {nachname}",
                         kunde_id=k.id, benutzer_id=ad_id, vot_datum=vot, status_text="Terminiert",
                         interesse=interesse, plz="47798", ort="Krefeld", vertriebskanal=kanal)
                s.add(l)
                s.flush()
                s.query(Vorgang).filter(Vorgang.lead_id == l.id).delete(synchronize_session=False)
                return l

            def vorgang(k, ad_id, lead_id=None, **extra):
                v = Vorgang(kunde_id=k.id, ad_id=ad_id, lead_id=lead_id, **extra)
                s.add(v)
                s.flush()
                objekte.hauptobjekt(s, v.id, anlegen=True, kunde=k)
                return v

            def termin(v, beginn, ad_id, status="geplant", quelle="monday", typ="vot"):
                haupt = objekte.hauptobjekt(s, v.id)
                t = VotTermin(vorgang_id=v.id, ad_id=ad_id, beginn=beginn, ende=beginn + timedelta(minutes=90),
                              status=status, quelle=quelle, typ=typ, medium="vor_ort",
                              objekt_id=haupt.id if haupt else None, adresse="")
                s.add(t)
                s.flush()
                return t

            heute = cls.heute
            # Lead heute (Gruppe Heute), gestern (Vergangene), vor 180 Tagen (Grenze, drin), vor 181 (weg)
            k = kunde("Heute", interesse="WP,PV")
            cls.l_heute = lead("Heute", k, cls.ad1_id, _um(heute, 12), interesse="WP,PV", kanal="Enni")
            cls.v_heute = vorgang(k, cls.ad1_id, lead_id=cls.l_heute.id, verfolgung_ampel="heiss")
            cls.t_heute = termin(cls.v_heute, _um(heute, 12), cls.ad1_id)
            k = kunde("Gestern")
            cls.l_gestern = lead("Gestern", k, cls.ad1_id, _um(heute - timedelta(days=1), 9))
            cls.v_gestern = vorgang(k, cls.ad1_id, lead_id=cls.l_gestern.id, verfolgung_ampel="warm")
            cls.t_gestern = termin(cls.v_gestern, _um(heute - timedelta(days=1), 9), cls.ad1_id)
            k = kunde("Grenze")
            cls.l_grenze = lead("Grenze", k, cls.ad1_id, _um(heute - timedelta(days=180), 10))
            cls.v_grenze = vorgang(k, cls.ad1_id, lead_id=cls.l_grenze.id)
            cls.t_grenze = termin(cls.v_grenze, _um(heute - timedelta(days=180), 10), cls.ad1_id)
            k = kunde("Uralt")
            cls.l_alt = lead("Uralt", k, cls.ad1_id, _um(heute - timedelta(days=181), 10))
            cls.v_alt = vorgang(k, cls.ad1_id, lead_id=cls.l_alt.id)
            cls.t_alt = termin(cls.v_alt, _um(heute - timedelta(days=181), 10), cls.ad1_id)
            # gestern mit abgeschlossener Erfassung → nirgends
            k = kunde("Erfasst")
            cls.l_erfasst = lead("Erfasst", k, cls.ad1_id, _um(heute - timedelta(days=1), 14))
            cls.v_erfasst = vorgang(k, cls.ad1_id, lead_id=cls.l_erfasst.id)
            cls.t_erfasst = termin(cls.v_erfasst, _um(heute - timedelta(days=1), 14), cls.ad1_id)
            s.add(Erfassung(kunde_id=k.id, vorgang_id=cls.v_erfasst.id, lead_id=cls.l_erfasst.id, benutzer_id=cls.ad1_id,
                            status="Neu", sparte="WP", abgesendet_am=_um(heute - timedelta(days=1), 15),
                            objekt_id=objekte.hauptobjekt(s, cls.v_erfasst.id).id))
            # fremder Vertriebler (gestern) – nur für Innendienst/Admin
            k = kunde("Fremd")
            cls.l_fremd = lead("Fremd", k, cls.ad2_id, _um(heute - timedelta(days=2), 9), kanal="Enni")
            cls.v_fremd = vorgang(k, cls.ad2_id, lead_id=cls.l_fremd.id, verfolgung_ampel="kalt")
            cls.t_fremd = termin(cls.v_fremd, _um(heute - timedelta(days=2), 9), cls.ad2_id)
            # Tool-Termin ohne monday-Lead (vor 5 Tagen) – Zeile ohne Lead
            k = kunde("Tool", interesse="PV")
            cls.v_tool = vorgang(k, cls.ad1_id)
            cls.t_tool = termin(cls.v_tool, _um(heute - timedelta(days=5), 11), cls.ad1_id, quelle="assistent")
            # Lead gestern, dessen Termin bereits gemeldet ist (no_show) → nicht mehr in der Tabelle
            k = kunde("Gemeldet")
            cls.l_gemeldet = lead("Gemeldet", k, cls.ad1_id, _um(heute - timedelta(days=1), 16))
            cls.v_gemeldet = vorgang(k, cls.ad1_id, lead_id=cls.l_gemeldet.id)
            termin(cls.v_gemeldet, _um(heute - timedelta(days=1), 16), cls.ad1_id, status="no_show")
            # Telefontermin gestern ohne Erfassung → nicht in „Vergangene Termine“ [ANNAHME v33]
            k = kunde("Telefon")
            cls.v_tel = vorgang(k, cls.ad1_id)
            cls.t_tel = termin(cls.v_tel, _um(heute - timedelta(days=1), 17), cls.ad1_id, typ="telefon", quelle="assistent")
            s.commit()
            cls.ids = {"heute": cls.v_heute.id, "gestern": cls.v_gestern.id, "tool": cls.v_tool.id,
                       "fremd": cls.v_fremd.id, "grenze": cls.v_grenze.id}
            cls.tids = {"heute": cls.t_heute.id, "gestern": cls.t_gestern.id, "tool": cls.t_tool.id,
                        "grenze": cls.t_grenze.id, "alt": cls.t_alt.id, "erfasst": cls.t_erfasst.id,
                        "fremd": cls.t_fremd.id, "tel": cls.t_tel.id}
            cls.lids = {"heute": cls.l_heute.id, "gestern": cls.l_gestern.id, "fremd": cls.l_fremd.id,
                        "gemeldet": cls.l_gemeldet.id, "alt": cls.l_alt.id, "erfasst": cls.l_erfasst.id}
        finally:
            s.close()
        cls.ad1 = _client(cls.ad1_id)
        cls.ad2 = _client(cls.ad2_id)
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
                for tabelle in (VotTermin, VorgangsNotiz, Erfassung, VorgangObjekt, LeadAktivitaet):
                    s.query(tabelle).filter(tabelle.vorgang_id.in_(vids)).delete(synchronize_session=False)
                s.query(Vorgang).filter(Vorgang.id.in_(vids)).delete(synchronize_session=False)
            s.query(Erfassung).filter(Erfassung.kunde_id.in_(ids)).delete(synchronize_session=False)
            s.query(Kunde).filter(Kunde.id.in_(ids)).delete(synchronize_session=False)
        s.query(Lead).filter(Lead.monday_item_id.like(f"{PRAEFIX}-%")).delete(synchronize_session=False)
        bids = [b.id for b in s.query(Benutzer).filter(Benutzer.name.like(f"{PRAEFIX} %"))]
        if bids:
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

    # --- Gruppe „Vergangene Termine“ (Datenbasis) --------------------------------------------
    def test_gruppe_vergangene_termine_datenbasis(self):
        s = SessionLocal()
        try:
            ad1 = s.get(Benutzer, self.ad1_id)
            kontext = leads_router._tabelle_kontext(s, ad1, "", "", 0, "", "", "", "")
            titel = [g["titel"] for g in kontext["gruppen"]]
            self.assertEqual(titel, ["Heute", "Vergangene Termine"])          # keine Gruppe „Überfällig“
            self.assertNotIn("Überfällig", titel)
            heute = kontext["gruppen"][0]
            self.assertEqual([z["name"] for z in heute["zeilen"]], [f"Peter {PRAEFIX} Heute"])
            self.assertFalse(heute["zu"])
            vergangen = kontext["gruppen"][-1]
            self.assertTrue(vergangen["vergangen"])
            self.assertTrue(vergangen["zu"])                                   # standardmäßig zugeklappt
            self.assertEqual(vergangen["key"], mein_tag.GRUPPE_VERGANGEN)
            tids = [z["termin_id"] for z in vergangen["zeilen"]]
            # neueste zuerst: gestern, vor 5 Tagen (Tool), vor 180 Tagen (Grenze drin)
            self.assertEqual(tids, [self.tids["gestern"], self.tids["tool"], self.tids["grenze"]])
            self.assertNotIn(self.tids["alt"], tids)                           # 181 Tage → nirgends
            self.assertNotIn(self.tids["erfasst"], tids)                       # Erfassung abgeschlossen → nirgends
            self.assertNotIn(self.tids["fremd"], tids)                         # AD nur eigene
            self.assertNotIn(self.tids["tel"], tids)                           # Telefontermin [ANNAHME]
            je_id = {z["termin_id"]: z for z in vergangen["zeilen"]}
            self.assertEqual(je_id[self.tids["gestern"]]["vor_text"], "gestern")
            self.assertEqual(je_id[self.tids["tool"]]["vor_text"], "vor 5 Tagen")
            self.assertEqual(je_id[self.tids["grenze"]]["vor_text"], "vor 180 Tagen")
            self.assertIsNone(je_id[self.tids["tool"]]["lead"])                # Tool-Termin ohne monday-Lead
            self.assertEqual(je_id[self.tids["tool"]]["akte_url"], f"/vorgaenge/{self.ids['tool']}")
            self.assertEqual(je_id[self.tids["gestern"]]["akte_url"], f"/vorgaenge/{self.ids['gestern']}")
            self.assertTrue(all(z["ausfall"] for z in vergangen["zeilen"]))
            self.assertEqual(vergangen["zaehler"], "3 Termine")
            self.assertEqual(kontext["vergangene_anzahl"], 3)
            self.assertEqual(kontext["gruppen"][0]["zeilen"][0]["termin_id"], self.tids["heute"])
            # kein Lead mehr in der Tabelle, dessen Termine alle gemeldet sind (no_show)
            alle_namen = [z["name"] for g in kontext["gruppen"] for z in g["zeilen"]]
            self.assertNotIn(f"Peter {PRAEFIX} Gemeldet", alle_namen)
            self.assertNotIn(f"Peter {PRAEFIX} Uralt", alle_namen)
            for g in kontext["gruppen"]:
                for z in g["zeilen"]:
                    self.assertNotIn("ueberfaellig", z)
            self.assertNotIn("ueberfaellig_anzahl", kontext)
            # Innendienst: fremder Vertriebler dabei; Chip-Filter Vertriebler/Priorität/Kanal wirken
            innen = s.get(Benutzer, self.id_id)
            alle = leads_router._tabelle_kontext(s, innen, "", "", 0, "", "", "", "")
            vg = alle["gruppen"][-1]
            self.assertIn(self.tids["fremd"], [z["termin_id"] for z in vg["zeilen"]])
            nur_ad1 = leads_router._tabelle_kontext(s, innen, "", "", self.ad1_id, "", "", "", "")
            self.assertNotIn(self.tids["fremd"], [z["termin_id"] for z in nur_ad1["gruppen"][-1]["zeilen"]])
            niedrig = leads_router._tabelle_kontext(s, innen, "", "", 0, "", "", "", "", prioritaet="niedrig")
            vg_n = [z["termin_id"] for g in niedrig["gruppen"] if g["vergangen"] for z in g["zeilen"]]
            self.assertIn(self.tids["fremd"], vg_n)                            # kalt = niedrig
            self.assertNotIn(self.tids["gestern"], vg_n)                       # warm = mittel
            enni = leads_router._tabelle_kontext(s, innen, "", "", 0, "", "", "", "Enni")
            vg_e = [z["termin_id"] for g in enni["gruppen"] if g["vergangen"] for z in g["zeilen"]]
            self.assertEqual(vg_e, [self.tids["fremd"]])
            suche = leads_router._tabelle_kontext(s, innen, f"{PRAEFIX} Tool", "", 0, "", "", "", "")
            self.assertEqual([z["termin_id"] for g in suche["gruppen"] for z in g["zeilen"]], [self.tids["tool"]])
            # Ansicht „Ausgeblendete“ ohne Vergangen-Gruppe
            ausgebl = leads_router._tabelle_kontext(s, innen, "", "", 0, "", "", "ausgeblendet", "")
            self.assertFalse(any(g["vergangen"] for g in ausgebl["gruppen"]))
            # mein_tag.termine: „Heute“ nur heutiger Tag, vergangene getrennt, 180-Tage-Grenze
            daten = mein_tag.termine(s, ad1, heute=_um(self.heute, 8))
            self.assertEqual([k["termin"].id for k in daten["heute"]], [self.tids["heute"]])
            self.assertEqual([k["termin"].id for k in daten["vergangene"]],
                             [self.tids["gestern"], self.tids["tool"], self.tids["grenze"]])
            self.assertEqual(daten["vergangene_anzahl"], 3)
            self.assertNotIn("ueberfaellig", daten)
            self.assertNotIn("ueberfaellige", daten)
            self.assertEqual([len(t["termine"]) for t in daten["vergangene_tage"]], [1, 1, 1])
            self.assertEqual(daten["vergangene_tage"][0]["vor_text"], "gestern")
            self.assertEqual(mein_tag.VERGANGEN_TAGE, 180)
            self.assertEqual(mein_tag.vor_text(self.heute - timedelta(days=12), self.heute), "vor 12 Tagen")
            self.assertEqual(mein_tag.vor_text(self.heute, self.heute), "heute")
        finally:
            s.close()

    # --- HTML der Tabelle ----------------------------------------------------------------------
    def test_html_gruppe_zu_kein_ueberfaellig(self):
        for client in (self.ad1, self.innen):
            html = client.get("/leads").text
            tabelle = html[html.index('class="mt-desktop'):]
            gruppe = _gruppe(tabelle, "vergangen")
            self.assertIn('id="vergangene"', gruppe)
            self.assertIn("data-lv-zu", gruppe)
            self.assertNotRegex(gruppe.split(">", 1)[0], r"\bopen\b")           # zugeklappt
            self.assertIn("Vergangene Termine", gruppe)
            self.assertIn("ohne Erfassung · letzte 180 Tage", gruppe)
            self.assertIn(f'data-termin="{self.tids["gestern"]}"', gruppe)
            self.assertIn(">gestern<", gruppe)
            self.assertIn(">vor 5 Tagen<", gruppe)
            self.assertIn('class="sp-termin lv-vergangen"', gruppe)
            self.assertIn("Termin nicht stattgefunden", gruppe)
            self.assertIn(f'href="/vorgaenge/{self.ids["tool"]}"', gruppe)        # Tool-Termin ohne Lead
            heute = _gruppe(tabelle, "heute")
            self.assertIn(f"{PRAEFIX} Heute", heute)
            self.assertNotIn(f"{PRAEFIX} Gestern", heute)
            self.assertIn('data-ta-oeffnen', heute)                           # Zeilenaktion in allen Gruppen
            self.assertLess(tabelle.index('data-gruppe="heute"'), tabelle.index('data-gruppe="vergangen"'))
            for alt in ("überfällig", "ueberfaellig-rot", 'value="ueberfaellig"', "Nur überfällige",
                        "Termine in der Vergangenheit ohne Erfassung", "Überfällig"):
                self.assertNotIn(alt, html)
            self.assertEqual(html.count('id="termin-ausgefallen"'), 1)
            self.assertNotIn(f"{PRAEFIX} Uralt", html)
            self.assertNotIn(f"{PRAEFIX} Erfasst", html)
            self.assertNotIn(f"{PRAEFIX} Gemeldet", html)
        # AD sieht die fremde Zeile nicht, Innendienst schon
        self.assertNotIn(f"{PRAEFIX} Fremd", self.ad1.get("/leads").text)
        self.assertIn(f"{PRAEFIX} Fremd", self.innen.get("/leads").text)
        # Klappzustand je Benutzer (localStorage) in mein_tag.js
        js = open(JS, encoding="utf-8").read()
        for teil in ("lv_gruppen_", "localStorage", "data-lv-gruppen", "'toggle'"):
            self.assertIn(teil, js)
        self.assertNotIn("data-mt-leiste-kunden", js)

    # --- Kanalzelle: Badge + Pfeil, Menü, JSON-Antwort -------------------------------------
    def test_kanal_pfeil_und_json(self):
        html = self.innen.get("/leads").text
        tabelle = html[html.index('class="mt-desktop'):]
        self.assertIn('aria-label="Vertriebskanal ändern"', tabelle)
        self.assertIn("data-lv-kanal-pfeil", tabelle)
        self.assertIn('aria-haspopup="menu"', tabelle)
        self.assertNotIn('<select name="kanal" onchange', tabelle)              # kein Dropdown mehr
        self.assertEqual(tabelle.count("<template data-lv-kanal-optionen>"), 1)
        self.assertEqual(tabelle.count("data-lv-kanal-menue"), 1)
        self.assertEqual(tabelle.count('<datalist id="lv-kanal-liste">'), 1)
        zelle = tabelle[tabelle.index(f'data-lead="{self.lids["heute"]}"'):]
        zelle = zelle[:zelle.index("</td>")]
        self.assertIn('class="lm-kanal mit-farbe"', zelle)                       # Badge (Farbe aus den Stammdaten)
        self.assertIn('data-aktuell="Enni"', zelle)
        self.assertIn(f'data-url="/leads/{self.lids["heute"]}/kanal"', zelle)
        self.assertIn("<noscript>", zelle)
        self.assertIn("symbol-svg", zelle)
        # Außendienst: nur Badge, kein Pfeil
        ad_html = self.ad1.get("/leads").text
        self.assertNotIn("data-lv-kanal-pfeil", ad_html)
        self.assertNotIn("data-lv-kanal-menue", ad_html)
        # Auswahl speichert über die bestehende Route – JSON-Antwort mit neuem Badge
        antwort = self.innen.post(f"/leads/{self.lids['heute']}/kanal", data={"kanal": "Sparkasse"},
                                  headers={"Accept": "application/json"})
        self.assertEqual(antwort.status_code, 200, antwort.text)
        daten = antwort.json()
        self.assertTrue(daten["ok"])
        self.assertEqual(daten["kanal"], "Sparkasse")
        self.assertTrue(daten["manuell"])
        self.assertIn('class="lm-kanal', daten["badge_html"])
        self.assertIn(">Sparkasse<", daten["badge_html"])
        self.assertIn("Sparkasse", daten["meldung"])
        s = SessionLocal()
        try:
            lead = s.get(Lead, self.lids["heute"])
            self.assertEqual(lead.vertriebskanal, "Sparkasse")
            self.assertTrue(lead.kanal_manuell)
            self.assertEqual(s.get(Kunde, lead.kunde_id).vertriebskanal, "Sparkasse")
        finally:
            s.close()
        # leer = zurück zur Sync-Automatik (Badge leer)
        antwort = self.innen.post(f"/leads/{self.lids['heute']}/kanal", data={"kanal": ""},
                                  headers={"Accept": "application/json"})
        self.assertEqual(antwort.status_code, 200)
        self.assertFalse(antwort.json()["manuell"])
        self.assertEqual(antwort.json()["badge_html"].strip(), "")
        # ohne Accept wie bisher Redirect; Außendienst 403 (JSON) bzw. 303
        self.assertEqual(self.innen.post(f"/leads/{self.lids['heute']}/kanal", data={"kanal": "Enni"}).status_code, 303)
        self.assertEqual(self.ad1.post(f"/leads/{self.lids['heute']}/kanal", data={"kanal": "Enni"},
                                       headers={"Accept": "application/json"}).status_code, 403)
        self.assertEqual(self.ad1.post(f"/leads/{self.lids['heute']}/kanal", data={"kanal": "Enni"}).status_code, 303)
        # Kanal-Menü nur in Leads VOT: Kundenliste und Kartei unverändert (kein Pfeil-Markup)
        self.assertNotIn("data-lv-kanal-pfeil", self.admin.get("/kunden").text)
        # JS: Menü mit Tastatur, Escape, Klick außerhalb; CSS: Pfeil 16 px, nur Tokens
        js = open(JS, encoding="utf-8").read()
        for teil in ("data-lv-kanal-pfeil", "menuitemradio", "'Escape'", "'ArrowDown'", "badge_html", "Accept"):
            self.assertIn(teil, js)
        css = open(CSS, encoding="utf-8").read()
        self.assertIn(".lv-kanal-pfeil .symbol-svg { width: 16px; height: 16px; }", css)
        self.assertNotRegex(css.replace("rgba(7, 13, 26, 0.55)", ""), r"#[0-9a-fA-F]{3,6}\b")

    # --- Symbole (v38) ----------------------------------------------------------------------
    def test_symbole_verlauf_und_pfeil(self):
        from app.templating import templates
        vorlage = templates.env.from_string('{% from "_symbole.html" import symbol %}{{ symbol(n) }}')
        verlauf = vorlage.render(n="verlauf")
        self.assertIn("<path", verlauf)
        self.assertNotIn('<circle cx="12" cy="12" r="9"/>', verlauf)             # kein Rückfall-Kreis
        pfeil = vorlage.render(n="pfeil-unten")
        self.assertIn('<path d="m6 9 6 6 6-6"/>', pfeil)
        self.assertNotIn("fill=\"#", verlauf + pfeil)

    # --- on*-Attribute (v30-Regel) -------------------------------------------------------------
    def test_keine_json_in_on_attributen(self):
        html = self.innen.get("/leads").text
        for m in re.finditer(r'\son\w+="([^"]*)"', html):
            self.assertEqual(m.group(1).count("("), m.group(1).count(")"), m.group(0)[:120])
            self.assertNotIn("[", m.group(1))
        self.assertIn("data-ta-vorbelegung=\"{&#34;", html)                  # tojson | forceescape


if __name__ == "__main__":
    unittest.main()
