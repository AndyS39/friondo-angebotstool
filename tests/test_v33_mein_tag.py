# v33 (PLAN_V20 Phase 173, Protokoll Claudia Castro 14.10.2026 Teil A): „Mein Tag“ nur mobil –
# Karten (.mt-mobil) nur für die Basisrolle Außendienst (auch Handelsvertreter) unter 600 px,
# Tabelle „Leads VOT“ (.mt-desktop) ab 600 px und für alle anderen Rollen; Kopf ohne
# Kennzahlen; Karte „Als Nächstes“ („in 25 Min“, „jetzt“, fehlt ohne Termin heute);
# Zeitstrahl-Zustände erledigt/nächster/offen; Abschnitt „Wiedervorlage“ (vier Karten,
# Chip Hoch = heiß zuerst, „seit X Tagen“ ab 14 in Warnfarbe, „heute“/„seit gestern“);
# Seite /leads/wiedervorlagen (Suche, Leerzustand, 303 für Innendienst); Erledigt über die
# abgeschlossene Erfassung des Termin-Objekts; Telefontermin ohne Erfassung am Folgetag weg;
# Leads VOT Desktop mit Gruppen „Heute“, „Donnerstag, 15. Oktober“, „Montag, 19. Oktober“
# (gemocktes heute 14.10.2026); untere Leiste mit vier Einträgen und aktivem Eintrag.
import re
import unittest
from datetime import date, datetime, timedelta

from fastapi.testclient import TestClient

from app import auth, mein_tag, nachfassen, objekte
from app.db import SessionLocal
from app.main import app
from app.models import (Angebot, Benutzer, BenutzerEinstellung, Erfassung, Kunde, Lead, Vorgang,
                        VorgangObjekt, VorgangsNotiz, VotTermin)
from app.routers import leads as leads_router

PRAEFIX = "V33MT"
CSS = "app/static/mein_tag.css"
JS = "app/static/mein_tag.js"


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


def _karte(html: str, marke: str) -> str:
    """Die <article>-Karte, die den Marker enthält (ab dem Tag-Anfang, damit die Klassen dabei sind)."""
    treffer = html.index(marke)
    start = html.rindex("<article", 0, treffer)
    return html[start:html.index("</article>", treffer)]


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


class MeinTagV33Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.heute = date.today()
        s = SessionLocal()
        try:
            cls._aufraeumen(s)

            naechste_id = [_freie_benutzer_id(s)]

            def benutzer(name, rolle, vorname=""):
                naechste_id[0] += 1
                b = Benutzer(id=naechste_id[0], name=f"{PRAEFIX} {name}", rolle=rolle, aktiv=True, vorname=vorname,
                             email=f"{name.lower().replace(' ', '')}@v33mt.local",
                             pin_hash=auth.pin_hash("4321"))
                s.add(b)
                s.flush()
                return b.id

            cls.ad1_id = benutzer("Golaschewski", "aussendienst", vorname="Rene")
            cls.ad2_id = benutzer("Fremd", "aussendienst")
            cls.ad_leer_id = benutzer("Leer", "aussendienst")
            cls.ad_gruppen_id = benutzer("Gruppen", "aussendienst")
            cls.hv_id = benutzer("Vertreter", "handelsvertreter")
            cls.id_id = benutzer("Innendienst", "innendienst")

            def kunde(nachname, interesse="WP,PV", **extra):
                k = Kunde(anrede="Herr", vorname="Peter", nachname=f"{PRAEFIX} {nachname}", strasse="Testweg 1",
                          plz="47798", ort="Krefeld", telefon="0203 555 4711", interesse=interesse, **extra)
                s.add(k)
                s.flush()
                return k

            def vorgang(k, ad_id, lead_id=None, **extra):
                v = Vorgang(kunde_id=k.id, ad_id=ad_id, lead_id=lead_id, **extra)
                s.add(v)
                s.flush()
                objekte.hauptobjekt(s, v.id, anlegen=True, kunde=k)
                return v

            def termin(v, beginn, ad_id, typ="vot", dauer=60, status="geplant", quelle="assistent", objekt_id=None):
                haupt = objekte.hauptobjekt(s, v.id)
                t = VotTermin(vorgang_id=v.id, ad_id=ad_id, beginn=beginn, ende=beginn + timedelta(minutes=dauer),
                              status=status, quelle=quelle, typ=typ, medium="vor_ort" if typ == "vot" else typ,
                              objekt_id=objekt_id or (haupt.id if haupt else None), adresse="")
                s.add(t)
                s.flush()
                return t

            heute = cls.heute
            # --- Termine heute: 08:00 Telefon (erledigt), 09:30 (nächster), 11:45, 14:00, 16:30
            k = kunde("Lange", interesse="WP")
            cls.v_erledigt = vorgang(k, cls.ad1_id)
            cls.t_erledigt = termin(cls.v_erledigt, _um(heute, 8), cls.ad1_id, typ="telefon", dauer=30)
            cls.e_erledigt = Erfassung(kunde_id=k.id, vorgang_id=cls.v_erledigt.id, benutzer_id=cls.ad1_id,
                                       status="Neu", sparte="WP", abgesendet_am=_um(heute, 8, 40),
                                       objekt_id=objekte.hauptobjekt(s, cls.v_erledigt.id).id)
            s.add(cls.e_erledigt)
            s.flush()
            k = kunde("Brandt", interesse="WP")
            cls.v_naechster = vorgang(k, cls.ad1_id)
            cls.t_naechster = termin(cls.v_naechster, _um(heute, 9, 30), cls.ad1_id)
            k = kunde("Yilmaz", interesse="PV")
            cls.v_11 = vorgang(k, cls.ad1_id)
            cls.t_11 = termin(cls.v_11, _um(heute, 11, 45), cls.ad1_id, dauer=90)
            k = kunde("Kessler")
            cls.v_14 = vorgang(k, cls.ad1_id)
            cls.t_14 = termin(cls.v_14, _um(heute, 14), cls.ad1_id, typ="online")
            k = kunde("Hoven", interesse="PV")
            cls.v_16 = vorgang(k, cls.ad1_id)
            cls.t_16 = termin(cls.v_16, _um(heute, 16, 30), cls.ad1_id)
            # --- gestern: Vor-Ort ohne Erfassung (überfällig) und Telefon ohne Erfassung (weg)
            k = kunde("Gestern", interesse="WP")
            cls.v_gestern = vorgang(k, cls.ad1_id)
            cls.t_gestern = termin(cls.v_gestern, _um(heute - timedelta(days=1), 9), cls.ad1_id)
            k = kunde("TelefonGestern", interesse="WP")
            cls.v_tel_gestern = vorgang(k, cls.ad1_id)
            cls.t_tel_gestern = termin(cls.v_tel_gestern, _um(heute - timedelta(days=1), 15), cls.ad1_id, typ="telefon")
            # --- kommende Tage: morgen, +5 Tage (zwei), +20 Tage (jenseits der 14 Tage)
            k = kunde("Morgen", interesse="WP")
            cls.v_morgen = vorgang(k, cls.ad1_id)
            cls.t_morgen = termin(cls.v_morgen, _um(heute + timedelta(days=1), 10), cls.ad1_id, quelle="monday")
            k = kunde("FuenfA", interesse="PV")
            cls.v_5a = vorgang(k, cls.ad1_id)
            cls.t_5a = termin(cls.v_5a, _um(heute + timedelta(days=5), 13), cls.ad1_id)
            k = kunde("FuenfB", interesse="WP")
            cls.v_5b = vorgang(k, cls.ad1_id)
            cls.t_5b = termin(cls.v_5b, _um(heute + timedelta(days=5), 9), cls.ad1_id)
            k = kunde("Spaeter", interesse="KL")
            cls.v_spaeter = vorgang(k, cls.ad1_id)
            cls.t_spaeter = termin(cls.v_spaeter, _um(heute + timedelta(days=20), 9), cls.ad1_id)
            # --- fremd / mit Angebot / abgesagt
            k = kunde("Schmidt")
            cls.v_fremd = vorgang(k, cls.ad2_id)
            termin(cls.v_fremd, _um(heute, 11), cls.ad2_id)
            k = kunde("MitAngebot")
            cls.v_angebot = vorgang(k, cls.ad1_id)
            termin(cls.v_angebot, _um(heute, 17), cls.ad1_id)
            s.add(Angebot(nummer=f"AN-{PRAEFIX}-1", kunde_id=k.id, vorgang_id=cls.v_angebot.id, status="Entwurf"))
            k = kunde("Abgesagt")
            cls.v_abgesagt = vorgang(k, cls.ad1_id)
            termin(cls.v_abgesagt, _um(heute, 18), cls.ad1_id, status="abgesagt")
            # --- Erledigt je Objekt: Termin am Hauptobjekt, Erfassung am zweiten Objekt zählt nicht
            k = kunde("ZweiObjekte")
            cls.v_zwei = vorgang(k, cls.ad1_id)
            cls.objekt2 = objekte.objekt_anlegen(s, cls.v_zwei, strasse="Nebenweg 7", plz="47798", ort="Krefeld",
                                                 bezeichnung="Garage", interessen=["PV"])
            cls.t_zwei = termin(cls.v_zwei, _um(heute, 19), cls.ad1_id)
            cls.t_zwei_garage = termin(cls.v_zwei, _um(heute, 20), cls.ad1_id, objekt_id=cls.objekt2.id)
            # --- Wiedervorlage: fällige/überfällige + heiße Vorgänge mit letztem Kontakt
            def wv(nachname, ampel, faellig_vor, kontakt_vor, ad_id=None, status="versendet", interesse="WP"):
                kk = kunde(nachname, interesse=interesse)
                vv = vorgang(kk, ad_id or cls.ad1_id, verfolgung_ampel=ampel, verfolgung_status=status)
                if faellig_vor is not None:
                    nachfassen.wiedervorlage_setzen(s, vv, heute - timedelta(days=faellig_vor), ad_id or cls.ad1_id,
                                                    "angebot_nachfassen")
                if kontakt_vor is not None:
                    s.add(VorgangsNotiz(vorgang_id=vv.id, benutzer_id=cls.ad1_id, benutzer_name="Test",
                                        zeit=_um(heute - timedelta(days=kontakt_vor), 10), text="Kontakt"))
                s.add(Angebot(nummer=f"AN-{PRAEFIX}-{nachname}", kunde_id=kk.id, vorgang_id=vv.id,
                              status="Versendet", konfigurator_typ="WP",
                              versendet_am=_um(heute - timedelta(days=(kontakt_vor or 0) + 1), 9),
                              datum=heute - timedelta(days=(kontakt_vor or 0) + 1)))
                s.flush()
                return vv

            cls.w_heiss14 = wv("WvHeissAlt", "heiss", 0, 14)              # Hoch, seit 14 Tagen (Warnfarbe)
            cls.w_heiss3 = wv("WvHeissNeu", "heiss", None, 3)             # Hoch, nur über die Ampel (nicht fällig)
            cls.w_bestellung = wv("WvBestellung", "heiss", None, None, status="bestellung_angekuendigt")
            cls.w_warm = wv("WvWarm", "warm", 1, 1)                        # Mittel, überfällig, seit gestern
            cls.w_kalt = wv("WvKalt", "kalt", 0, 0)                        # Niedrig, heute
            cls.w_kalt_ohne = wv("WvKaltOhne", "kalt", 2, None)            # Niedrig, noch kein Kontakt
            cls.w_fremd = wv("WvFremd", "heiss", 0, 1, ad_id=cls.ad2_id)   # anderer Vertriebler
            cls.w_zukunft = wv("WvZukunft", "warm", -3, 1)                 # Wiedervorlage in 3 Tagen → nicht fällig
            # --- Leads VOT Desktop: Gruppen mit festem Datum (14./15./19.10.2026) für ad_gruppen
            for i, (tag, stunde) in enumerate(((date(2026, 10, 14), 10), (date(2026, 10, 15), 9), (date(2026, 10, 19), 11))):
                kk = kunde(f"Gruppe{i}")
                lead = Lead(monday_item_id=f"{PRAEFIX}-grp-{i}", vorname="Peter", nachname=f"{PRAEFIX} Gruppe{i}",
                            kunde_id=kk.id, benutzer_id=cls.ad_gruppen_id, vot_datum=_um(tag, stunde),
                            status_text="Terminiert", interesse="WP", plz="47798", ort="Krefeld")
                s.add(lead)
                s.flush()
                s.query(Vorgang).filter(Vorgang.lead_id == lead.id).delete(synchronize_session=False)
                vorgang(kk, cls.ad_gruppen_id, lead_id=lead.id, verfolgung_ampel=("heiss", "", "kalt")[i])
            # Lead heute für ad1 (Tabelle am echten Datum) und ein ausgeblendeter Lead
            kk = kunde("LeadHeute")
            lead = Lead(monday_item_id=f"{PRAEFIX}-heute", vorname="Peter", nachname=f"{PRAEFIX} LeadHeute",
                        kunde_id=kk.id, benutzer_id=cls.ad1_id, vot_datum=_um(heute, 12),
                        status_text="Terminiert", interesse="WP,PV", plz="47798", ort="Krefeld")
            s.add(lead)
            s.flush()
            s.query(Vorgang).filter(Vorgang.lead_id == lead.id).delete(synchronize_session=False)
            cls.lead_heute = vorgang(kk, cls.ad1_id, lead_id=lead.id, verfolgung_ampel="warm")
            cls.lead_heute_id = lead.id
            s.commit()
            cls.ids = {"erledigt": cls.v_erledigt.id, "naechster": cls.v_naechster.id, "gestern": cls.v_gestern.id,
                       "zwei": cls.v_zwei.id, "w_heiss14": cls.w_heiss14.id, "w_heiss3": cls.w_heiss3.id,
                       "w_bestellung": cls.w_bestellung.id, "w_warm": cls.w_warm.id, "w_kalt": cls.w_kalt.id,
                       "w_kalt_ohne": cls.w_kalt_ohne.id, "w_fremd": cls.w_fremd.id, "w_zukunft": cls.w_zukunft.id}
        finally:
            s.close()
        cls.ad1 = _client(cls.ad1_id)
        cls.ad2 = _client(cls.ad2_id)
        cls.ad_leer = _client(cls.ad_leer_id)
        cls.hv = _client(cls.hv_id)
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
                for tabelle in (VotTermin, VorgangsNotiz, Erfassung, VorgangObjekt):
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

    # --- Karten nur bei AD + mobil, Tabelle ab 600 px und für alle anderen Rollen ------------
    def test_karten_nur_aussendienst_mobil_tabelle_sonst(self):
        html = self.ad1.get("/leads").text
        self.assertIn('class="mt-mobil"', html)
        self.assertIn('class="mt-desktop"', html)
        self.assertIn("<h1>Mein Tag</h1>", html)
        self.assertIn("<h1>Leads VOT</h1>", html)          # Tabelle im selben HTML (ab 600 px)
        self.assertNotIn("mt-umschalter", html)              # v32-Umschalter entfällt
        self.assertNotIn("darstellung=tabelle", html)
        # Handelsvertreter (Variante der Basisrolle Außendienst) ebenfalls Karten
        self.assertIn('class="mt-mobil"', self.hv.get("/leads").text)
        # Innendienst/Admin: nur die Tabelle, keine Karten, kein Umschalter
        for client in (self.innen, self.admin):
            seite = client.get("/leads")
            self.assertEqual(seite.status_code, 200)
            self.assertIn('class="mt-desktop', seite.text)
            self.assertNotIn('class="mt-mobil', seite.text)
            self.assertNotIn("mt-umschalter", seite.text)
            self.assertNotIn('id="wiedervorlage"', seite.text)
        # ?darstellung=… wird nicht mehr gelesen und nichts gespeichert
        self.assertIn('class="mt-mobil"', self.ad1.get("/leads?darstellung=tabelle").text)
        self.assertIn('class="mt-desktop', self.innen.get("/leads?darstellung=karten").text)
        s = SessionLocal()
        try:
            self.assertFalse(s.query(BenutzerEinstellung)
                             .filter(BenutzerEinstellung.benutzer_id.in_([self.ad1_id, self.id_id]),
                                     BenutzerEinstellung.key == "leads_darstellung").count())
        finally:
            s.close()
        # Media-Query: Karten unter 600 px, Tabelle darüber (CSS, nur Tokens)
        css = open(CSS, encoding="utf-8").read()
        mobil = css[css.index("@media (max-width: 600px)"):]
        self.assertIn(".mt-mobil { display: block", mobil)
        self.assertIn(".mt-desktop { display: none", mobil)
        self.assertIn(".mt-mobil { display: none", css[:css.index("@media (max-width: 600px)")])
        self.assertNotRegex(css, r"#[0-9a-fA-F]{3,6}\b")
        self.assertFalse(hasattr(mein_tag, "darstellung_lesen"))
        self.assertFalse(hasattr(mein_tag, "DARSTELLUNGEN"))

    # --- Kopf ohne Kennzahlen -------------------------------------------------------------
    def test_kopf_datum_titel_initialen_ohne_kennzahlen(self):
        html = self.ad1.get("/leads").text
        start = html.index('class="mt-kopf"')
        kopf = html[start:html.index("</header>", start)]
        self.assertIn(mein_tag.datum_lang(self.heute), kopf)        # „Mittwoch, 14. Oktober“
        self.assertIn("<h1>Mein Tag</h1>", kopf)
        self.assertIn(">RG</span>", kopf)                              # Initialen aus Vor- und Nachname
        self.assertIn("mt-avatar", kopf)
        for text in ("Termine offen", "Route heute", "Wiedervorlagen</span>", "mt-kennzahl", "kachel stat"):
            self.assertNotIn(text, kopf)
        self.assertNotIn("Fällig heute", html)
        self.assertNotIn("Heiße Kunden", html)
        self.assertNotIn("Weitere Termine", html)
        self.assertEqual(mein_tag.datum_lang(date(2026, 10, 14)), "Mittwoch, 14. Oktober")
        self.assertEqual(mein_tag.wochentag_kurz(date(2026, 10, 15)), "DO")

    # --- Karte „Als Nächstes“ ----------------------------------------------------------------
    def test_als_naechstes_minuten_jetzt_und_fehlt(self):
        s = SessionLocal()
        try:
            ad1 = s.get(Benutzer, self.ad1_id)
            daten = mein_tag.termine(s, ad1, heute=_um(self.heute, 9, 5))
            self.assertEqual(daten["naechster"]["termin"].id, self.t_naechster.id)   # 08:00 ist erledigt
            self.assertEqual(daten["naechster"]["hinweis"], "in 25 Min")
            self.assertEqual(daten["naechster"]["ende_uhr"], "10:30")
            self.assertEqual(daten["naechster"]["uhr"], "09:30")
            self.assertEqual(daten["naechster"]["beschreibung"], "Wärmepumpe, Vor-Ort-Termin")
            self.assertTrue(any(k["naechster"] for k in daten["heute"] if k["termin"].id == self.t_naechster.id))
            daten = mein_tag.termine(s, ad1, heute=_um(self.heute, 9, 35))
            self.assertEqual(daten["naechster"]["hinweis"], "jetzt")
            daten = mein_tag.termine(s, ad1, heute=_um(self.heute, 7, 0))
            self.assertEqual(daten["naechster"]["hinweis"], "in 2 Std 30 Min")
            daten = mein_tag.termine(s, ad1, heute=_um(self.heute, 11, 0))
            self.assertEqual(daten["naechster"]["termin"].id, self.t_11.id)        # 09:30 ist vorbei
            daten = mein_tag.termine(s, ad1, heute=_um(self.heute, 23, 0))
            self.assertIsNone(daten["naechster"])                                   # alle vorbei
            leer = s.get(Benutzer, self.ad_leer_id)
            self.assertIsNone(mein_tag.termine(s, leer, heute=_um(self.heute, 9))["naechster"])
        finally:
            s.close()
        self.assertEqual(mein_tag.minuten_text(_um(self.heute, 9, 30), _um(self.heute, 9, 5)), "in 25 Min")
        self.assertEqual(mein_tag.minuten_text(_um(self.heute, 9, 30), _um(self.heute, 9, 30)), "jetzt")
        self.assertEqual(mein_tag.minuten_text(_um(self.heute, 11, 0), _um(self.heute, 9, 0)), "in 2 Std")
        # HTML (echte Uhrzeit): Karte nur, solange ein heutiger Termin noch nicht zu Ende ist
        html = self.ad1.get("/leads").text
        if datetime.now() < _um(self.heute, 21, 0):
            karte = html[html.index('id="als-naechstes"'):html.index("</section>", html.index('id="als-naechstes"'))]
            self.assertIn("Als Nächstes", karte)
            self.assertRegex(karte, r'data-mt-hinweis>(in \d+ (Min|Std)|jetzt)')
            self.assertIn("Route starten", karte)
            self.assertIn('href="https://www.google.com/maps/dir/?api=1&amp;destination=Testweg%201%2C%2047798%20Krefeld', karte)
            self.assertIn('href="tel:+492035554711"', karte)
            self.assertIn("bis ", karte)
            self.assertIn("Vor-Ort-Termin", karte)
        else:
            self.assertNotIn('id="als-naechstes"', html)
        self.assertNotIn('id="als-naechstes"', self.ad_leer.get("/leads").text)

    # --- Liste „Heute“ mit Zeitstrahl --------------------------------------------------------
    def test_zeitstrahl_zustaende_und_zaehler(self):
        html = self.ad1.get("/leads").text
        heute = _block(html, "termine-heute")
        self.assertIn("<h2>Heute</h2>", heute)
        # 5 heutige Termine + Termin am Hauptobjekt + Garage = 7; der überfällige von gestern
        # steht zuoberst im aufklappbaren Block „überfällige Termine“ (offen bei höchstens drei)
        self.assertIn("7 Termine", heute)
        self.assertIn('id="termine-ueberfaellig" open', heute)
        self.assertIn("1 überfälliger Termin", heute)
        self.assertIn("ohne Erfassung – bitte nachfassen", heute)
        erledigt = _karte(heute, f'data-termin="{self.t_erledigt.id}"')
        self.assertIn('data-zustand="erledigt"', erledigt)
        self.assertIn("mt-termin-erledigt", erledigt)
        self.assertIn(f'href="/erfassung/{self.e_erledigt.id}/pruefen"', erledigt)   # Link zur Erfassung
        self.assertNotIn("Erfassung starten", erledigt)
        self.assertIn("Telefontermin", erledigt)
        offen = _karte(heute, f'data-termin="{self.t_11.id}"')
        self.assertIn("Erfassung starten", offen)
        self.assertIn('class="knopf mt-haupt"', offen)
        self.assertIn("Photovoltaik, Vor-Ort-Termin", offen)
        self.assertIn('data-zustand="', offen)
        self.assertIn("mt-punkt", offen)
        teams = _karte(heute, f'data-termin="{self.t_14.id}"')
        self.assertIn("Teams", teams)
        gestern = _karte(heute, f'data-termin="{self.t_gestern.id}"')
        self.assertIn('class="mt-label mt-label-rot" title="Termin liegt in der Vergangenheit – Erfassung fehlt">überfällig', gestern)
        self.assertLess(heute.index(f'data-termin="{self.t_gestern.id}"'), heute.index(f'data-termin="{self.t_erledigt.id}"'))
        # Uhrzeit links, Name, Typ, Ort
        self.assertIn('<span class="mt-uhr">11:45</span>', offen)
        self.assertIn("Krefeld", offen)
        # fremd / mit Angebot / abgesagt nicht enthalten
        for name in ("Schmidt", "MitAngebot", "Abgesagt"):
            self.assertNotIn(f"{PRAEFIX} {name}", html)
        # Zustände als Daten: genau ein nächster Termin, erledigt markiert
        s = SessionLocal()
        try:
            daten = mein_tag.termine(s, s.get(Benutzer, self.ad1_id), heute=_um(self.heute, 9, 0))
            zustaende = {k["termin"].id: ("erledigt" if k["erledigt"] else ("naechster" if k["naechster"] else "offen"))
                         for k in daten["heute"]}
            self.assertEqual(zustaende[self.t_erledigt.id], "erledigt")
            self.assertEqual(zustaende[self.t_naechster.id], "naechster")
            self.assertEqual(zustaende[self.t_11.id], "offen")
            self.assertEqual(list(zustaende.values()).count("naechster"), 1)
        finally:
            s.close()

    def test_telefontermin_ohne_erfassung_am_folgetag_weg(self):
        html = self.ad1.get("/leads").text
        self.assertNotIn(f'data-termin="{self.t_tel_gestern.id}"', html)
        self.assertNotIn(f"{PRAEFIX} TelefonGestern", html)
        self.assertIn(f'data-termin="{self.t_gestern.id}"', html)   # Vor-Ort bleibt als überfällig
        s = SessionLocal()
        try:
            ad1 = s.get(Benutzer, self.ad1_id)
            # am Tag selbst steht der Telefontermin offen in „Heute“ (bis Tagesende)
            daten = mein_tag.termine(s, ad1, heute=_um(self.heute - timedelta(days=1), 16))
            ids = [k["termin"].id for k in daten["heute"]]
            self.assertIn(self.t_tel_gestern.id, ids)
            self.assertFalse(next(k for k in daten["heute"] if k["termin"].id == self.t_tel_gestern.id)["erledigt"])
            daten = mein_tag.termine(s, ad1, heute=_um(self.heute, 8))
            self.assertNotIn(self.t_tel_gestern.id, [k["termin"].id for k in daten["heute"]])
        finally:
            s.close()

    # --- Erledigt über die abgeschlossene Erfassung (je Objekt) ------------------------------
    def test_erledigt_ueber_abgeschlossene_erfassung(self):
        s = SessionLocal()
        try:
            ad1 = s.get(Benutzer, self.ad1_id)

            def zustand(termin_id):
                daten = mein_tag.termine(s, ad1, heute=_um(self.heute, 7))
                return next(k for k in daten["heute"] if k["termin"].id == termin_id)

            self.assertFalse(zustand(self.t_zwei.id)["erledigt"])
            self.assertFalse(zustand(self.t_zwei_garage.id)["erledigt"])
            kunde_id = self.v_zwei.kunde_id
            haupt = objekte.hauptobjekt(s, self.ids["zwei"])
            # Entwurf zählt nicht
            e = Erfassung(kunde_id=kunde_id, vorgang_id=self.ids["zwei"], benutzer_id=self.ad1_id,
                          status="Entwurf", sparte="WP", objekt_id=haupt.id)
            s.add(e)
            s.flush()
            self.assertFalse(zustand(self.t_zwei.id)["erledigt"])
            # WP abgesendet, PV noch offen → nicht erledigt
            e.status = "Neu"
            e.abgesendet_am = datetime.now()
            s.flush()
            self.assertFalse(zustand(self.t_zwei.id)["erledigt"])
            self.assertEqual(zustand(self.t_zwei.id)["chips"], [("WP", "erfasst"), ("PV", "offen")])
            # PV am Hauptobjekt abgesendet → Termin am Hauptobjekt erledigt, Garage-Termin nicht
            s.add(Erfassung(kunde_id=kunde_id, vorgang_id=self.ids["zwei"], benutzer_id=self.ad1_id,
                            status="Neu", sparte="PV", objekt_id=haupt.id, abgesendet_am=datetime.now()))
            s.flush()
            self.assertTrue(zustand(self.t_zwei.id)["erledigt"])
            self.assertFalse(zustand(self.t_zwei_garage.id)["erledigt"])
            url = zustand(self.t_zwei.id)["erfassung_url"]            # jüngste abgesendete Erfassung des Objekts
            self.assertRegex(url, r"^/erfassung/\d+/pruefen$")
            self.assertNotEqual(url, f"/erfassung/{e.id}/pruefen")
            # Erfassung PV am zweiten Objekt → auch die Garage erledigt
            s.add(Erfassung(kunde_id=kunde_id, vorgang_id=self.ids["zwei"], benutzer_id=self.ad1_id,
                            status="Neu", sparte="PV", objekt_id=self.objekt2.id, abgesendet_am=datetime.now()))
            s.flush()
            self.assertTrue(zustand(self.t_zwei_garage.id)["erledigt"])
            s.rollback()
        finally:
            s.close()

    # --- Abschnitt „Wiedervorlage“ -----------------------------------------------------------
    def test_wiedervorlage_abschnitt_vier_karten_hoch_zuerst(self):
        html = self.ad1.get("/leads").text
        block = _block(html, "wiedervorlage")
        self.assertIn("<h2>Wiedervorlage</h2>", block)
        self.assertIn("Vorgänge, die auf Rückmeldung warten", block)
        # Zähler = alle Vorgänge (6 eigene: 3 heiß/Bestellung, warm, kalt, kalt ohne Kontakt)
        self.assertIn('data-mt-wv-gesamt>6</span>', block)
        self.assertIn('data-mt-prio-zahl="alle">6<', block)
        self.assertIn('data-mt-prio-zahl="hoch">3<', block)
        self.assertIn('data-mt-prio-zahl="mittel">1<', block)
        self.assertIn('data-mt-prio-zahl="niedrig">2<', block)
        for chip in ("Alle", "Hoch", "Mittel", "Niedrig"):
            self.assertIn(f'data-mt-prio="{chip.lower()}"', block)
        self.assertIn('class="mt-chip aktiv" data-mt-prio="alle"', block)
        for sort in ("prio", "name", "datum"):
            self.assertIn(f'data-mt-sort="{sort}"', block)
        self.assertIn("Priorität<span", block)
        self.assertIn(">↓</span>", block)                       # gewählter Eintrag trägt den Pfeil
        # höchstens vier sichtbare Karten, die übrigen versteckt (hidden)
        karten = re.findall(r'<article class="mt-wv-karte"[^>]*>', block)
        self.assertEqual(len(karten), 6)
        sichtbar = [k for k in karten if " hidden" not in k]
        self.assertEqual(len(sichtbar), 4)
        self.assertTrue(all("data-mt-ueberzahl" in k for k in karten if " hidden" in k))
        # Chip Hoch = heiß an erster Stelle (Sortierung Priorität), ältester Kontakt zuerst
        self.assertIn(f'data-vorgang="{self.ids["w_heiss14"]}"', sichtbar[0])
        self.assertIn('data-prio="hoch"', sichtbar[0])
        self.assertIn('data-prio="hoch"', sichtbar[1])
        self.assertIn('data-prio="hoch"', sichtbar[2])
        self.assertIn('data-prio="mittel"', sichtbar[3])
        erste = _karte(block, f'data-vorgang="{self.ids["w_heiss14"]}"')
        self.assertIn('class="mt-prio mt-prio-hoch"', erste)
        self.assertIn(">Hoch</span>", erste)
        self.assertIn("Wärmepumpe", erste)                       # Sparte ausgeschrieben
        self.assertIn(">PW</span>", erste)                       # Initialen des Kunden (Peter … WvHeissAlt)
        # „Letzter Kontakt TT.MM. · seit X Tagen“ – ab 14 Tagen in der Warnfarbe
        tag14 = (self.heute - timedelta(days=14)).strftime("%d.%m.")
        self.assertIn(f"Letzter Kontakt {tag14}", erste)
        self.assertIn('class="mt-wv-tage warn" data-mt-tage>· seit 14 Tagen</span>', erste)
        warm = _karte(block, f'data-vorgang="{self.ids["w_warm"]}"')
        self.assertIn('class="mt-wv-tage" data-mt-tage>· seit gestern</span>', warm)
        self.assertIn(">Mittel</span>", warm)
        kalt = _karte(block, f'data-vorgang="{self.ids["w_kalt"]}"')
        self.assertIn('data-mt-tage>· heute</span>', kalt)
        self.assertIn(">Niedrig</span>", kalt)
        ohne = _karte(block, f'data-vorgang="{self.ids["w_kalt_ohne"]}"')
        self.assertIn("noch kein Kontakt", ohne)
        bestellung = _karte(block, f'data-vorgang="{self.ids["w_bestellung"]}"')
        self.assertIn("Bestellung angekündigt", bestellung)
        # Tippen öffnet die Anruf-Karte: Dialog „Nächster Schritt“, Notizfeld, letzte Aktivitäten
        self.assertIn('data-mt-aufklappen', erste)
        self.assertIn(f"/vorgaenge/{self.ids['w_heiss14']}/naechster-schritt", erste)
        self.assertIn(f'data-ns-notiz="{self.ids["w_heiss14"]}"', erste)
        self.assertIn("Letzte Aktivitäten", erste)
        self.assertIn("Notiz zum Gespräch", erste)
        self.assertIn("WP-Angebot vom", erste)
        # nicht enthalten: fremder Vertriebler, Wiedervorlage in der Zukunft ohne heiße Ampel
        self.assertNotIn(f"{PRAEFIX} WvFremd", html)
        self.assertNotIn(f"{PRAEFIX} WvZukunft", html)
        self.assertIn('href="/leads/wiedervorlagen">Alle <span data-mt-wv-gesamt>6</span> Wiedervorlagen anzeigen', block)
        # Leerzustand beim Vertriebler ohne Vorgänge
        leer = _block(self.ad_leer.get("/leads").text, "wiedervorlage")
        self.assertIn("Keine Vorgänge, die auf Rückmeldung warten.", leer)

    def test_wiedervorlage_liste_datenbasis(self):
        s = SessionLocal()
        try:
            karten = nachfassen.wiedervorlage_liste(s, self.ad1_id, self.heute)
            ids = [k["vorgang"].id for k in karten]
            self.assertEqual(ids[0], self.ids["w_heiss14"])
            self.assertEqual([k["prioritaet"] for k in karten], ["hoch", "hoch", "hoch", "mittel", "niedrig", "niedrig"])
            self.assertEqual(ids[1:3], [self.ids["w_heiss3"], self.ids["w_bestellung"]])   # ohne Kontakt zuletzt
            self.assertNotIn(self.ids["w_fremd"], ids)
            self.assertNotIn(self.ids["w_zukunft"], ids)
            je_id = {k["vorgang"].id: k for k in karten}
            self.assertEqual(je_id[self.ids["w_heiss14"]]["tage_seit"], 14)
            self.assertTrue(je_id[self.ids["w_heiss14"]]["warn"])
            self.assertEqual(je_id[self.ids["w_warm"]]["tage_text"], "seit gestern")
            self.assertFalse(je_id[self.ids["w_warm"]]["warn"])
            self.assertEqual(je_id[self.ids["w_kalt"]]["tage_text"], "heute")
            self.assertIsNone(je_id[self.ids["w_kalt_ohne"]]["letzter_kontakt"])
            self.assertEqual(je_id[self.ids["w_bestellung"]]["grund"], "bestellung")
            self.assertEqual(je_id[self.ids["w_heiss3"]]["grund"], "heiss")
            self.assertEqual(je_id[self.ids["w_warm"]]["grund"], "faellig")
            self.assertTrue(je_id[self.ids["w_warm"]]["ueberfaellig"])
            self.assertEqual(je_id[self.ids["w_heiss14"]]["sparten"], ["WP"])
            self.assertIn("inaktiv", je_id[self.ids["w_heiss14"]])
            for k in karten:
                self.assertFalse(any(x in str(k["angebot"]) for x in ("ek_cent", "deckungsbeitrag")))
            zaehler = nachfassen.wiedervorlage_zaehler(karten)
            self.assertEqual(zaehler, {"alle": 6, "hoch": 3, "mittel": 1, "niedrig": 2})
            # faellig_heute trägt dieselben Zusatzfelder
            faellig = nachfassen.faellig_heute(s, self.ad1_id, self.heute)
            self.assertIn(self.ids["w_heiss14"], [k["vorgang"].id for k in faellig])
            self.assertNotIn(self.ids["w_heiss3"], [k["vorgang"].id for k in faellig])
            self.assertEqual(next(k for k in faellig if k["vorgang"].id == self.ids["w_heiss14"])["prioritaet"], "hoch")
            self.assertEqual(nachfassen.tage_text(None), "noch kein Kontakt")
            self.assertEqual(nachfassen.tage_text(0), "heute")
            self.assertEqual(nachfassen.tage_text(1), "seit gestern")
            self.assertEqual(nachfassen.tage_text(14), "seit 14 Tagen")
            self.assertEqual(nachfassen.initialen("Herr Peter Müller"), "PM")
            self.assertEqual(nachfassen.initialen("Familie Brandt"), "BR")
            self.assertEqual(mein_tag.prioritaet_von("heiss"), "hoch")
            self.assertEqual(mein_tag.prioritaet_von(""), "niedrig")
        finally:
            s.close()

    def test_notiz_setzt_letzten_kontakt_auf_heute(self):
        vid = self.ids["w_kalt_ohne"]
        antwort = self.ad1.post(f"/leads/notiz/{vid}", data={"text": "Kunde erreicht, ruft zurück"},
                                headers={"Accept": "application/json"})
        self.assertEqual(antwort.status_code, 200, antwort.text)
        s = SessionLocal()
        try:
            karte = next(k for k in nachfassen.wiedervorlage_liste(s, self.ad1_id, self.heute) if k["vorgang"].id == vid)
            self.assertEqual(karte["tage_text"], "heute")
            s.query(VorgangsNotiz).filter(VorgangsNotiz.vorgang_id == vid).delete(synchronize_session=False)
            s.commit()
        finally:
            s.close()

    # --- Seite „Wiedervorlage“ ------------------------------------------------------------------
    def test_seite_wiedervorlage(self):
        seite = self.ad1.get("/leads/wiedervorlagen")
        self.assertEqual(seite.status_code, 200)
        html = seite.text
        self.assertIn('class="mt-zurueck" href="/leads"', html)
        self.assertIn("Mein Tag</a>", html)
        self.assertNotIn("zurueck-knopf", html)                    # eigener Pfeil statt Zurück-Leiste
        self.assertIn("<h1>Wiedervorlage</h1>", html)
        self.assertIn('<span data-mt-wv-zahl>6</span> offen', html)
        self.assertIn('placeholder="Nach Name suchen"', html)
        self.assertIn("data-mt-suche", html)
        self.assertIn('data-mt-prio-zahl="hoch">3<', html)
        self.assertIn('data-mt-sort="datum"', html)
        karten = re.findall(r'<article class="mt-wv-karte"[^>]*>', html)
        self.assertEqual(len(karten), 6)                          # alle, ohne Begrenzung
        self.assertFalse(any(" hidden" in k for k in karten))
        self.assertIn('data-prio="hoch"', karten[0])
        self.assertIn('class="mt-rund mt-wv-tel" href="tel:+492035554711"', html)   # Telefon-Knopf rechts
        self.assertIn("Keine Vorgänge gefunden", html)
        self.assertIn("Filter oder Suche anpassen.", html)
        self.assertIn('data-mt-wv-leer hidden', html)              # Leerzustand erst per Filter/Suche
        self.assertIn('class="mt-leiste"', html)
        self.assertIn('href="/leads/wiedervorlagen" class="mt-leiste-eintrag aktiv" aria-current="page"', html)
        self.assertIn('class="mt-mobil mt-mobil-immer"', html)
        # ohne Vorgänge: Leerzustand sichtbar, Zähler 0
        leer = self.ad_leer.get("/leads/wiedervorlagen").text
        self.assertIn('<span data-mt-wv-zahl>0</span> offen', leer)
        self.assertIn('data-mt-wv-leer >', leer)
        # Innendienst/Admin: Angebotsliste mit Verfolgungsfilter
        for client in (self.innen, self.admin):
            antwort = client.get("/leads/wiedervorlagen")
            self.assertEqual(antwort.status_code, 303)
            self.assertEqual(antwort.headers["location"], "/angebote?verfolgung=versendet")
        # Suche/Sortierung/Filter sind clientseitig (mein_tag.js)
        js = open(JS, encoding="utf-8").read()
        for text in ("data-mt-suche", "mt_wv_sort", "mt_wv_prio", "sessionStorage", "data-mt-max", "localeCompare"):
            self.assertIn(text, js)

    # --- Kommende Tage ------------------------------------------------------------------------
    def test_kommende_tage_gruppen(self):
        html = self.ad1.get("/leads").text
        block = _block(html, "kommende-tage")
        self.assertIn("<h2>Kommende Tage</h2>", block)
        morgen = self.heute + timedelta(days=1)
        fuenf = self.heute + timedelta(days=5)
        self.assertIn(f'data-tag="{morgen.isoformat()}"', block)
        self.assertIn(mein_tag.datum_lang(morgen), block)
        self.assertIn(f'<span class="mt-wd">{mein_tag.wochentag_kurz(fuenf)}</span><span class="mt-nr">{fuenf.day}</span>', block)
        self.assertIn(">2 Termine<", block)
        self.assertIn(">1 Termin<", block)
        self.assertLess(block.index(f'data-termin="{self.t_5b.id}"'), block.index(f'data-termin="{self.t_5a.id}"'))
        self.assertNotIn(f"{PRAEFIX} Spaeter", block)              # jenseits der 14 Tage
        self.assertIn("1 weiterer Termin nach dem", block)
        self.assertIn('href="/lead-management/meine-termine"', block)
        klein = _karte(block, f'data-termin="{self.t_morgen.id}"')
        self.assertIn("Wärmepumpe, Vor-Ort-Termin · Krefeld", klein)
        s = SessionLocal()
        try:
            daten = mein_tag.termine(s, s.get(Benutzer, self.ad1_id), heute=_um(self.heute, 9))
            self.assertEqual([len(g["termine"]) for g in daten["kommende"]], [1, 2])
            self.assertEqual(daten["spaeter"], 1)
            self.assertEqual(daten["kommende"][0]["titel"], mein_tag.datum_lang(morgen))
        finally:
            s.close()

    # --- Leads VOT Desktop mit Gruppen -------------------------------------------------------
    def test_leads_vot_desktop_gruppen(self):
        s = SessionLocal()
        try:
            ad = s.get(Benutzer, self.ad_gruppen_id)
            kontext = leads_router._tabelle_kontext(s, ad, "", "", 0, "", "", "", "", heute=datetime(2026, 10, 14, 8))
            self.assertEqual([g["titel"] for g in kontext["gruppen"]],
                             ["Heute", "Donnerstag, 15. Oktober", "Montag, 19. Oktober"])
            self.assertEqual([g["zaehler"] for g in kontext["gruppen"]], ["1 Termin", "1 Termin", "1 Termin"])
            self.assertEqual(kontext["gruppen"][0]["erkl"], "Mittwoch, 14. Oktober")
            self.assertEqual([sp["key"] for sp in kontext["spalten"]][0], "lead")
            self.assertIn("prioritaet", [sp["key"] for sp in kontext["spalten"]])
            # Priorität = Hot-Ampel, Filter
            self.assertEqual(kontext["gruppen"][0]["zeilen"][0]["prioritaet"], "hoch")
            gefiltert = leads_router._tabelle_kontext(s, ad, "", "", 0, "", "", "", "", prioritaet="niedrig",
                                                      heute=datetime(2026, 10, 14, 8))
            # leere Ampel = niedrig [ANNAHME] → Donnerstag (ohne Einstufung) und Montag (kalt)
            self.assertEqual([g["titel"] for g in gefiltert["gruppen"]], ["Donnerstag, 15. Oktober", "Montag, 19. Oktober"])
            hoch = leads_router._tabelle_kontext(s, ad, "", "", 0, "", "", "", "", prioritaet="hoch",
                                                 heute=datetime(2026, 10, 14, 8))
            self.assertEqual([g["titel"] for g in hoch["gruppen"]], ["Heute"])
            # am 20.10. sind die drei Leads überfällig
            spaeter = leads_router._tabelle_kontext(s, ad, "", "", 0, "", "", "", "", heute=datetime(2026, 10, 20, 8))
            self.assertEqual([g["titel"] for g in spaeter["gruppen"]], ["Überfällig"])
            self.assertEqual(spaeter["gruppen"][0]["zaehler"], "3 Termine")
            # Spaltensortierung innerhalb der Gruppe: Kundenname absteigend
            gruppen = mein_tag.gruppen_sortieren(mein_tag.gruppen_bilden(spaeter["zeilen"], datetime(2026, 10, 20)),
                                                 {"key": "lead", "richtung": "ab"})
            namen = [z["name"] for z in gruppen[0]["zeilen"]]
            self.assertEqual(namen, sorted(namen, reverse=True))
        finally:
            s.close()
        # HTML (echtes Datum): Gruppe „Heute“ mit dem heutigen Lead, Filterleiste, Spaltenwerkzeuge
        html = self.ad1.get("/leads").text
        tabelle = html[html.index('class="mt-desktop"'):]
        self.assertIn('data-lm-spalten-board="leads_vot"', tabelle)
        self.assertIn('class="lm-filterblock"', tabelle)
        self.assertIn('data-gruppe="heute"', tabelle)
        self.assertIn(">Heute ", tabelle)
        self.assertIn(f"{PRAEFIX} LeadHeute", tabelle)
        self.assertIn('data-sort="lead"', tabelle)
        self.assertIn('data-sort="prioritaet"', tabelle)
        self.assertIn('name="prioritaet"', tabelle)
        self.assertIn('id="lm-spaltenliste"', tabelle)
        self.assertIn("/static/lm_boards.js", tabelle)
        self.assertIn('id="lm-daten"', tabelle)
        self.assertIn("chip chip-wp chip-offen", tabelle)
        self.assertIn("chip-legende", tabelle)
        self.assertNotIn(f"{PRAEFIX} Gruppe0", tabelle)           # Leads des anderen Vertrieblers nicht
        self.assertIn('<span class="mt-prio mt-prio-mittel"', tabelle)
        # Innendienst sieht alle Vertriebler, Filter Vertriebler + Priorität
        innen = self.innen.get(f"/leads?vertriebler_id={self.ad_gruppen_id}&prioritaet=hoch").text
        self.assertIn(f"{PRAEFIX} Gruppe0", innen)
        self.assertNotIn(f"{PRAEFIX} Gruppe2", innen)
        self.assertIn(f'<option value="{self.ad_gruppen_id}" selected>', innen)
        self.assertIn('<option value="hoch" selected>', innen)
        self.assertIn("Filter zurücksetzen", innen)

    # --- Untere Leiste ----------------------------------------------------------------------
    def test_untere_leiste_vier_eintraege(self):
        html = self.ad1.get("/leads").text
        leiste = html[html.index('class="mt-leiste"'):html.index("</nav>", html.index('class="mt-leiste"'))]
        for href, text in (("/leads", "Mein Tag"), ("/lead-management/meine-termine", "Kalender"),
                           ("/leads/wiedervorlagen", "Wiedervorlage"), ("/suche", "Kunden")):
            self.assertIn(f'href="{href}"', leiste)
            self.assertIn(text + "</a>", leiste)
        self.assertEqual(leiste.count("mt-leiste-eintrag"), 4)
        self.assertIn('href="/leads" class="mt-leiste-eintrag aktiv" aria-current="page"', leiste)
        self.assertEqual(leiste.count('aria-current="page"'), 1)
        self.assertIn("data-mt-leiste-kunden", leiste)
        # auch auf anderen Außendienst-Seiten (Erfassungsstart), nicht für den Innendienst
        self.assertIn('class="mt-leiste"', self.ad1.get("/erfassung").text)
        self.assertIn('class="mt-leiste"', self.hv.get("/leads").text)
        self.assertNotIn("mt-leiste", self.innen.get("/leads").text)
        self.assertNotIn("mt-leiste", self.admin.get("/").text)
        self.assertNotIn("mt-leiste", TestClient(app, follow_redirects=False).get("/login").text)
        css = open(CSS, encoding="utf-8").read()
        mobil = css[css.index("@media (max-width: 600px)"):]
        self.assertIn(".mt-leiste { display: grid", mobil)
        self.assertIn("env(safe-area-inset-bottom)", mobil)
        self.assertIn(".mt-leiste { display: none; }", css)
        self.assertIn("min-height: 44px", css)
        js = open(JS, encoding="utf-8").read()
        self.assertIn("viewport-fit=cover", js)
        self.assertIn("data-mt-leiste-kunden", js)

    # --- Design-Regeln (v30) -----------------------------------------------------------------
    def test_design_regeln_keine_json_in_attributen(self):
        html = self.ad1.get("/leads").text
        for m in re.finditer(r'\son\w+="([^"]*)"', html):
            self.assertNotIn("[", m.group(1), m.group(0)[:120])    # kein tojson in on*-Attributen
        self.assertIn("/static/mein_tag.css", html)
        self.assertIn("/static/mein_tag.js", html)
        css = open(CSS, encoding="utf-8").read()
        self.assertNotRegex(css, r"#[0-9a-fA-F]{3,6}\b")
        for token in ("--akzent", "--akzent-text", "--flaeche-karte", "--flaeche-abgesetzt", "--status-rot",
                      "--status-orange", "--status-gruen", "--status-grau", "--text-dezent"):
            self.assertIn(f"var({token})", css)


if __name__ == "__main__":
    unittest.main()
