# v32 (PLAN_V19 Phase 161): Vertriebler-Ansicht „Mein Tag“ (GET /leads) – Außendienst
# sieht nur eigene Termine aus vot_termine; Termin heute 14:00 in „Heute“, morgen in
# „Kommende Tage“, gestern ohne Erfassung in „Heute“ mit „überfällig“ (v38: auf der Seite
# /leads/vergangene – PLAN_V23 Phase 203/204 streicht „überfällig“); Termin-Zeile mit
# Datum, Uhrzeit, Name, Straße, Ort, tel:-Link, Maps-Link, „Erfassung starten“; Vorgang mit
# verknüpftem Angebot erscheint nicht; ID sieht die Tabelle „Leads VOT“ und filtert nach
# Vertriebler; Leerzustände; Objektadresse bei mehreren Objekten; Wiedervorlage.
# v33 (PLAN_V20 Phase 173, Protokoll Claudia Castro 14.10.2026 A.5): angepasst – „Mein Tag“
# nur mobil (Karten .mt-mobil nur für den Außendienst, Tabelle .mt-desktop für alle), der
# Umschalter „Karten | Tabelle“ und die Einstellung leads_darstellung entfallen, die Blöcke
# heißen Heute · Wiedervorlage · Kommende Tage (statt Fällig heute · Termine heute · Heiße
# Kunden · Weitere Termine), die mobile Filterkarte (Termin von/bis, Status) entfällt
# (Entwurf ohne Filter – die Datenfunktion mein_tag.termine filtert weiterhin).
import unittest
from datetime import date, datetime, timedelta

from fastapi.testclient import TestClient

from app import auth, lead_v2, mein_tag, nachfassen, objekte
from app.db import SessionLocal
from app.main import app
from app.models import (Angebot, Benutzer, BenutzerEinstellung, Erfassung, Kunde, Lead, Vorgang,
                        VorgangObjekt, VotTermin)

PRAEFIX = "V32MT"


def _client(benutzer_id: int) -> TestClient:
    c = TestClient(app, follow_redirects=False)
    c.cookies.set(auth.COOKIE_NAME, auth.cookie_wert(benutzer_id))
    return c


def _um(tag: date, stunde: int, minute: int = 0) -> datetime:
    return datetime(tag.year, tag.month, tag.day, stunde, minute)


def _block(html: str, anker: str) -> str:
    """HTML-Ausschnitt eines Blocks (section id=…) bis zur nächsten section."""
    start = html.index(f'id="{anker}"')
    ende = html.find("<section", start + 10)
    return html[start:ende if ende > 0 else None]


def _mobil(html: str) -> str:
    """Nur der Kartenteil (.mt-mobil) – die Tabelle (.mt-desktop) steht im selben HTML."""
    return html[:html.index('class="mt-desktop"')]


def _freie_benutzer_id(s) -> int:
    """SQLite vergibt gelöschte IDs neu – DB-Kopien tragen verwaiste Verweise (vorgaenge.ad_id,
    leads.benutzer_id, vot_termine.ad_id, wiedervorlage_benutzer_id) auf gelöschte Benutzer, die
    ein neuer Testbenutzer sonst „erbt“; Testbenutzer bekommen deshalb IDs oberhalb aller Verweise."""
    from sqlalchemy import func
    werte = [s.query(func.max(Benutzer.id)).scalar(), s.query(func.max(Vorgang.ad_id)).scalar(),
             s.query(func.max(Vorgang.wiedervorlage_benutzer_id)).scalar(),
             s.query(func.max(Lead.benutzer_id)).scalar(), s.query(func.max(VotTermin.ad_id)).scalar(),
             s.query(func.max(Erfassung.benutzer_id)).scalar()]
    return max([int(w or 0) for w in werte]) + 1


class MeinTagTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.heute = date.today()
        s = SessionLocal()
        try:
            cls._aufraeumen(s)

            naechste_id = [_freie_benutzer_id(s)]   # v33: keine geerbten Verweise aus DB-Kopien

            def benutzer(name, rolle):
                naechste_id[0] += 1
                b = Benutzer(id=naechste_id[0], name=f"{PRAEFIX} {name}", rolle=rolle, aktiv=True,
                             email=f"{name.lower().replace(' ', '')}@v32mt.local",
                             pin_hash=auth.pin_hash("4321"))
                s.add(b)
                s.flush()
                return b.id

            cls.ad1_id = benutzer("Rene", "aussendienst")
            cls.ad2_id = benutzer("Simon", "aussendienst")
            cls.ad3_id = benutzer("Leer", "aussendienst")
            cls.id_id = benutzer("Innendienst", "innendienst")

            def kunde(nachname, **extra):
                k = Kunde(anrede="Herr", vorname="Peter", nachname=f"{PRAEFIX} {nachname}", strasse="Testweg 1",
                          plz="47798", ort="Krefeld", telefon="0203 555 4711", interesse="WP,PV", **extra)
                s.add(k)
                s.flush()
                return k

            def vorgang(k, ad_id, lead_id=None):
                v = Vorgang(kunde_id=k.id, ad_id=ad_id, lead_id=lead_id)
                s.add(v)
                s.flush()
                objekte.hauptobjekt(s, v.id, anlegen=True, kunde=k)
                return v

            def termin(v, beginn, ad_id, status="geplant", quelle="assistent", objekt_id=None):
                haupt = objekte.hauptobjekt(s, v.id)
                t = VotTermin(vorgang_id=v.id, ad_id=ad_id, beginn=beginn, ende=beginn + timedelta(minutes=90),
                              status=status, quelle=quelle, typ="vot", medium="vor_ort",
                              objekt_id=objekt_id or (haupt.id if haupt else None), adresse="")
                s.add(t)
                s.flush()
                return t

            heute = cls.heute
            k1 = kunde("Mueller")
            cls.v1 = vorgang(k1, cls.ad1_id)
            cls.t_heute = termin(cls.v1, _um(heute, 14), cls.ad1_id, quelle="monday")
            k2 = kunde("Morgen")
            cls.v2 = vorgang(k2, cls.ad1_id)
            cls.t_morgen = termin(cls.v2, _um(heute + timedelta(days=1), 10), cls.ad1_id)
            k3 = kunde("Gestern")
            cls.v3 = vorgang(k3, cls.ad1_id)
            cls.t_gestern = termin(cls.v3, _um(heute - timedelta(days=1), 9), cls.ad1_id)
            k4 = kunde("Schmidt")
            cls.v4 = vorgang(k4, cls.ad2_id)
            cls.t_fremd = termin(cls.v4, _um(heute, 11), cls.ad2_id)
            k5 = kunde("MitAngebot")
            cls.v5 = vorgang(k5, cls.ad1_id)
            termin(cls.v5, _um(heute, 16), cls.ad1_id)
            s.add(Angebot(nummer=f"AN-{PRAEFIX}-1", kunde_id=k5.id, vorgang_id=cls.v5.id, status="Entwurf"))
            # zwei Objekte: Termin am zweiten Objekt zeigt die Objektbezeichnung
            k6 = kunde("ZweiObjekte")
            cls.v6 = vorgang(k6, cls.ad1_id)
            objekt2 = objekte.objekt_anlegen(s, cls.v6, strasse="Nebenweg 7", plz="47798", ort="Krefeld",
                                             bezeichnung="Garage", interessen=["PV"])
            cls.t_objekt = termin(cls.v6, _um(heute + timedelta(days=2), 9), cls.ad1_id, objekt_id=objekt2.id)
            # Termin eines anderen Vertrieblers (ad_id am Termin) bei einem Lead von AD2 –
            # „Erfassung starten“ muss für AD1 trotzdem gehen
            k7 = kunde("LeadFremd")
            lead = Lead(monday_item_id=f"{PRAEFIX}-lead-1", vorname="Peter", nachname=f"{PRAEFIX} LeadFremd",
                        kunde_id=k7.id, benutzer_id=cls.ad2_id, vot_datum=_um(heute + timedelta(days=3), 12),
                        status_text="Terminiert", interesse="WP")
            s.add(lead)
            s.flush()
            cls.lead_id = lead.id
            # SQLite vergibt Lead-IDs neu – ein verwaister Vorgang (z. B. aus tests/abnahme.py)
            # mit derselben lead_id darf den Aufbau nicht blockieren
            s.query(Vorgang).filter(Vorgang.lead_id == lead.id).delete(synchronize_session=False)
            cls.v7 = vorgang(k7, None, lead_id=lead.id)
            cls.t_lead = termin(cls.v7, _um(heute + timedelta(days=3), 12), cls.ad1_id, quelle="monday")
            # abgesagter Termin fällt heraus
            k8 = kunde("Abgesagt")
            cls.v8 = vorgang(k8, cls.ad1_id)
            termin(cls.v8, _um(heute, 17), cls.ad1_id, status="abgesagt")
            # Wiedervorlage (v33: statt „Heiße Kunden“): Bestellung angekündigt am Vorgang 1
            cls.v1.verfolgung_status = "bestellung_angekuendigt"
            cls.v1.verfolgung_ampel = "heiss"
            s.commit()
            cls.ids = {"v1": cls.v1.id, "v2": cls.v2.id, "v3": cls.v3.id, "v4": cls.v4.id, "v5": cls.v5.id,
                       "v6": cls.v6.id, "v7": cls.v7.id, "v8": cls.v8.id}
        finally:
            s.close()
        cls.ad1 = _client(cls.ad1_id)
        cls.ad2 = _client(cls.ad2_id)
        cls.ad3 = _client(cls.ad3_id)
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
                s.query(VotTermin).filter(VotTermin.vorgang_id.in_(vids)).delete(synchronize_session=False)
                s.query(Erfassung).filter(Erfassung.vorgang_id.in_(vids)).delete(synchronize_session=False)
                s.query(VorgangObjekt).filter(VorgangObjekt.vorgang_id.in_(vids)).delete(synchronize_session=False)
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

    # --- Außendienst ---------------------------------------------------------------------
    def test_ad_sieht_nur_eigene_termine_in_den_richtigen_bloecken(self):
        seite = self.ad1.get("/leads")
        self.assertEqual(seite.status_code, 200)
        html = _mobil(seite.text)
        # v33: Blöcke Heute · Wiedervorlage · Kommende Tage
        for ueberschrift in ("<h2>Heute</h2>", "<h2>Wiedervorlage</h2>", "<h2>Kommende Tage</h2>"):
            self.assertIn(ueberschrift, html)
        for alt in ("Fällig heute", "Heiße Kunden", "Weitere Termine"):
            self.assertNotIn(alt, html)
        self.assertIn("<h1>Mein Tag</h1>", html)
        heute = _block(html, "termine-heute")
        kommende = _block(html, "kommende-tage")
        self.assertIn(f"{PRAEFIX} Mueller", heute)
        self.assertIn(f"{PRAEFIX} Morgen", kommende)
        self.assertNotIn(f"{PRAEFIX} Morgen", heute)
        self.assertNotIn(f"{PRAEFIX} Mueller", kommende)
        # v38 (PLAN_V23 Phase 203/204): „überfällig“ gestrichen – der gestrige Termin ohne Erfassung
        # steht nicht mehr in „Heute“, sondern auf der Seite „Vergangene Termine“
        self.assertNotIn(f"{PRAEFIX} Gestern", heute)
        self.assertNotIn("überfällig", html)
        self.assertIn(f"{PRAEFIX} Gestern", self.ad1.get("/leads/vergangene").text)
        self.assertNotIn(f"{PRAEFIX} Schmidt", html)        # fremder Vertriebler
        self.assertNotIn(f"{PRAEFIX} MitAngebot", html)     # Vorgang mit verknüpftem Angebot
        self.assertNotIn(f"{PRAEFIX} Abgesagt", html)       # abgesagter Termin
        self.assertNotIn("ueberfaellig-rot", html)          # Überfällig-Banner (v15) nur in der Tabelle
        self.assertNotIn("Termine in der Vergangenheit ohne Erfassung", html)

    def test_termin_karte_pflichtinhalt(self):
        html = _block(_mobil(self.ad1.get("/leads").text), "termine-heute")
        karte = html[html.index(f'data-termin="{self.t_heute.id}"'):]
        karte = karte[:karte.find("</article>")]
        tag = self.heute
        self.assertIn(f"{mein_tag.WOCHENTAGE[tag.weekday()]}, {tag.strftime('%d.%m.')}", karte)   # „Mo, 13.10.“
        self.assertIn("14:00 Uhr", karte)
        self.assertIn('<span class="mt-uhr">14:00</span>', karte)                    # v33: Uhrzeit links
        self.assertIn(f"Herr Peter {PRAEFIX} Mueller", karte)
        self.assertIn("Testweg 1", karte)
        self.assertIn("47798 Krefeld", karte)
        self.assertIn('href="tel:+492035554711"', karte)
        self.assertIn('href="https://www.google.com/maps/search/?api=1&amp;query=Testweg%201%2C%2047798%20Krefeld"', karte)
        self.assertIn('target="_blank"', karte)
        self.assertIn("Erfassung starten", karte)
        self.assertIn(f'href="/erfassung/sparten?kunde_id=', karte)
        self.assertIn("objekt_id=", karte)
        self.assertIn(f'href="/vorgaenge/{self.ids["v1"]}"', karte)       # Zweitlink „Akte“
        self.assertIn("chip chip-wp chip-offen", karte)                      # Sparten-Badges/Status-Chips
        self.assertIn("chip chip-pv chip-offen", karte)
        self.assertIn('class="mt-herkunft" title="Herkunft des Termins">monday', karte)
        self.assertIn('class="knopf mt-haupt"', karte)
        self.assertIn("Wärmepumpe und Photovoltaik, Vor-Ort-Termin", karte)   # v33: Sparte, Termintyp

    def test_objektadresse_bei_mehreren_objekten(self):
        html = _block(_mobil(self.ad1.get("/leads").text), "kommende-tage")
        karte = html[html.index(f'data-termin="{self.t_objekt.id}"'):]
        karte = karte[:karte.find("</article>")]
        self.assertIn('<span class="mt-objekt">Garage:</span>', karte)
        self.assertIn("Nebenweg 7", karte)
        self.assertNotIn("Testweg 1", karte)
        self.assertIn("query=Nebenweg%207", karte)
        self.assertIn('class="mt-herkunft" title="Herkunft des Termins">Tool', karte)

    def test_erfassung_starten_fuer_termin_vertriebler_trotz_fremdem_lead(self):
        antwort = self.ad1.get(f"/leads/{self.lead_id}/erfassen?objekt_id=0")
        self.assertEqual(antwort.status_code, 303)
        self.assertTrue(antwort.headers["location"].startswith("/erfassung/sparten?lead_id="), antwort.headers["location"])
        # ein Dritter ohne Termin/Lead/Vorgang bleibt draußen
        dritter = self.ad3.get(f"/leads/{self.lead_id}/erfassen")
        self.assertEqual(dritter.headers["location"], "/leads")
        # Karte des Lead-Termins verlinkt die Lead-Übergabe mit objekt_id
        html = _mobil(self.ad1.get("/leads").text)
        self.assertIn(f'href="/leads/{self.lead_id}/erfassen?objekt_id=', html)

    def test_leerzustaende(self):
        html = _mobil(self.ad3.get("/leads").text)
        self.assertIn("Heute keine Termine.", html)
        self.assertIn("Keine Vorgänge, die auf Rückmeldung warten.", html)
        self.assertIn("Keine Termine in den nächsten 14 Tagen.", html)
        self.assertIn('class="leer-zustand"', html)

    def test_wiedervorlage_statt_heisse_kunden(self):
        """v33 (Protokoll A.5, Phase 163): „Heiße Kunden“ entfällt – der Vorgang mit Bestellung
        angekündigt steht im Abschnitt „Wiedervorlage“ mit Badge Hoch (Hot-Ampel heiß)."""
        html = _block(_mobil(self.ad1.get("/leads").text), "wiedervorlage")
        self.assertIn(f"{PRAEFIX} Mueller", html)
        self.assertIn("Bestellung angekündigt", html)
        self.assertIn(f'data-vorgang="{self.ids["v1"]}"', html)
        self.assertIn('data-prio="hoch"', html)
        self.assertIn(">Hoch</span>", html)
        self.assertIn(f'href="/vorgaenge/{self.ids["v1"]}"', html)
        self.assertNotIn(f"{PRAEFIX} Schmidt", html)
        self.assertNotIn(f"{PRAEFIX} Mueller", _block(_mobil(self.ad2.get("/leads").text), "wiedervorlage"))

    def test_filter_von_bis_und_status_in_der_datenfunktion(self):
        """v33: die mobile Filterkarte entfällt (Entwurf ohne Filter) – die Filter der
        Datenfunktion mein_tag.termine bleiben (Termin von/bis, Status)."""
        s = SessionLocal()
        try:
            ad1 = s.get(Benutzer, self.ad1_id)
            morgen = self.heute + timedelta(days=1)
            daten = mein_tag.termine(s, ad1, von=morgen.isoformat(), bis=morgen.isoformat())
            self.assertEqual([k["termin"].id for k in daten["alle"]], [self.t_morgen.id])
            daten = mein_tag.termine(s, ad1, status="Terminiert")
            self.assertEqual([k["termin"].id for k in daten["alle"]], [self.t_lead.id])
            self.assertEqual(daten["status_werte"], ["Terminiert"])
        finally:
            s.close()
        self.assertNotIn("mt-filter-form", _mobil(self.ad1.get("/leads").text))

    def test_ad_sieht_immer_karten(self):
        """v33: ?darstellung=… wird nicht mehr gelesen – der Außendienst bekommt Karten (mobil)
        und Tabelle (ab 600 px) im selben HTML, nichts wird gespeichert."""
        html = self.ad1.get("/leads?darstellung=tabelle").text
        self.assertIn("mein_tag.css", html)
        self.assertIn('class="mt-mobil"', html)
        self.assertIn('class="mt-desktop"', html)
        self.assertNotIn("mt-umschalter", html)
        s = SessionLocal()
        try:
            self.assertIsNone(lead_v2.einstellung_holen(s, self.ad1_id, "leads_darstellung"))
        finally:
            s.close()

    # --- Innendienst / Admin ----------------------------------------------------------------
    def test_id_sieht_tabelle_und_filtert_nach_vertriebler(self):
        """v33: Innendienst/Admin sehen nur die Tabelle „Leads VOT“ (Lead-basiert) – der
        Lead von AD2 (Termin in drei Tagen) mit Vertriebler-Filter."""
        html = self.innen.get("/leads").text
        self.assertIn("<h1>Leads VOT</h1>", html)
        self.assertIn(f"{PRAEFIX} LeadFremd", html)
        self.assertNotIn('class="mt-mobil', html)
        self.assertNotIn("mt-umschalter", html)
        self.assertIn("Vertriebler", html)
        self.assertIn(f"{PRAEFIX} Simon", html)   # Name des Vertrieblers im Dropdown der Zeile
        gefiltert = self.innen.get(f"/leads?vertriebler_id={self.ad2_id}").text
        self.assertIn(f"{PRAEFIX} LeadFremd", gefiltert)
        self.assertIn(f'<option value="{self.ad2_id}" selected>', gefiltert)
        leer = self.innen.get(f"/leads?vertriebler_id={self.ad1_id}").text
        self.assertNotIn(f"{PRAEFIX} LeadFremd", leer)

    def test_id_nur_tabelle_kein_umschalter(self):
        """v33: der v32-Umschalter „Karten | Tabelle“ entfällt; die Einstellung
        leads_darstellung wird weder gelesen noch geschrieben."""
        tabelle = self.innen.get("/leads?darstellung=tabelle")
        self.assertEqual(tabelle.status_code, 200)
        self.assertIn('class="tabelle lm-tabelle', tabelle.text)
        self.assertIn("<h1>Leads VOT</h1>", tabelle.text)
        self.assertNotIn('href="/leads?darstellung=tabelle"', tabelle.text)
        s = SessionLocal()
        try:
            self.assertIsNone(lead_v2.einstellung_holen(s, self.id_id, "leads_darstellung"))
        finally:
            s.close()
        karten = self.innen.get("/leads?darstellung=karten").text
        self.assertNotIn('id="termine-heute"', karten)
        self.assertIn('class="tabelle lm-tabelle', karten)
        # Admin: Tabelle mit Legende der Sparten-Chips (Abnahme v9)
        admin = self.admin.get("/leads").text
        self.assertNotIn('id="termine-heute"', admin)
        self.assertIn("chip-legende", admin)

    def test_meine_termine_link_zur_tagesansicht(self):
        seite = self.ad1.get("/lead-management/meine-termine")
        self.assertEqual(seite.status_code, 200)
        self.assertIn('href="/leads"', seite.text)
        self.assertIn("Zur Tagesansicht", seite.text)

    def test_mobil_feinheiten_und_design_regeln(self):
        html = self.ad1.get("/leads").text
        self.assertIn("/static/mein_tag.js", html)
        self.assertIn("/static/mein_tag.css", html)
        css = (self.ad1.get("/static/mein_tag.css")).text
        js = (self.ad1.get("/static/mein_tag.js")).text
        self.assertIn("env(safe-area-inset-bottom)", css)
        self.assertIn("min-height: 44px", css)
        self.assertIn("max-width: 720px", css)
        self.assertIn("@media (max-width: 600px)", css)
        self.assertIn("viewport-fit=cover", js)
        self.assertNotRegex(css, r"#[0-9a-fA-F]{3,6}\b")   # nur Tokens
        self.assertNotIn("tojson", html.split('id="wiedervorlage"')[0])

    # --- Datenaufbereitung direkt -------------------------------------------------------------
    def test_datenfunktionen(self):
        s = SessionLocal()
        try:
            ad1 = s.get(Benutzer, self.ad1_id)
            daten = mein_tag.termine(s, ad1)
            ids_heute = [k["termin"].id for k in daten["heute"]]
            # v38 (PLAN_V23 Phase 203): „Heute“ nur der heutige Tag, gestern unter „vergangene“
            self.assertEqual(ids_heute[:1], [self.t_heute.id])
            self.assertNotIn(self.t_gestern.id, ids_heute)
            self.assertEqual([k["termin"].id for k in daten["vergangene"]], [self.t_gestern.id])
            self.assertIn(self.t_morgen.id, [k["termin"].id for k in daten["weitere"]])
            self.assertEqual(daten["vergangene_anzahl"], 1)
            self.assertNotIn("ueberfaellig", daten)
            karte = next(k for k in daten["heute"] if k["termin"].id == self.t_heute.id)
            self.assertEqual(karte["uhr_text"], "14:00 Uhr")
            self.assertEqual(karte["herkunft"], "monday")
            self.assertEqual(karte["chips"], [("WP", "offen"), ("PV", "offen")])
            self.assertFalse(karte["erledigt"])
            # erfolgter Termin bleibt nur mit offener Sparte sichtbar (v8-Regel)
            s.add(Erfassung(kunde_id=self.v3.kunde_id, vorgang_id=self.ids["v3"], benutzer_id=self.ad1_id,
                            status="Neu", sparte="WP"))
            s.flush()
            daten = mein_tag.termine(s, ad1)
            k3 = next(k for k in daten["vergangene"] if k["termin"].id == self.t_gestern.id)   # v38
            self.assertTrue(k3["teilweise"])
            self.assertNotIn("ueberfaellig", k3)
            self.assertEqual(k3["chips"], [("WP", "erfasst"), ("PV", "offen")])
            s.add(Erfassung(kunde_id=self.v3.kunde_id, vorgang_id=self.ids["v3"], benutzer_id=self.ad1_id,
                            status="Neu", sparte="PV"))
            s.flush()
            daten = mein_tag.termine(s, ad1)
            self.assertNotIn(self.t_gestern.id, [k["termin"].id for k in daten["heute"]])
            self.assertNotIn(self.t_gestern.id, [k["termin"].id for k in daten["vergangene"]])   # v38: erledigt → nirgends
            # v33: Wiedervorlage-Liste statt heisse_kunden
            wv = nachfassen.wiedervorlage_liste(s, self.ad1_id)
            self.assertEqual([k["vorgang"].id for k in wv], [self.ids["v1"]])
            self.assertEqual(wv[0]["grund"], "bestellung")
            self.assertEqual(wv[0]["prioritaet"], "hoch")
            self.assertEqual(wv[0]["verfolgung_status"], "bestellung_angekuendigt")
            self.assertFalse(hasattr(mein_tag, "heisse_kunden"))
            s.rollback()
        finally:
            s.close()


if __name__ == "__main__":
    unittest.main()
