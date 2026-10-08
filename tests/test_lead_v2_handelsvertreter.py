# Tests PLAN_LEAD_V2 Phase 109 (CLAUDE v23): Handelsvertreter – Rechte
# (Kennzeichen, eigene Leads, 404 für fremde), Ansicht (Gesamtsicht ID/Admin,
# eigene Leads HV, Filter), Zuweisung/Umverteilung (Aktivität + Glocke),
# Ausschlussliste F14, Sonderregel „Deals - Rene“ / Standard Simon (F13),
# Kanalwechsel auf Ausschlusskanal (G4), HV-Dashboard (F16).
# Laufen im Demo-Modus gegen die Entwicklungs-DB; Testleads tragen den
# Nachnamen „LeadV2H-Test“, Testbenutzer das Präfix „LeadV2H “ – alles wird
# aufgeräumt. HV-Anmeldung per Cookie (auth.cookie_wert), Admin per /login.
import unittest
import warnings
from datetime import datetime, timedelta
from urllib.parse import quote_plus

warnings.filterwarnings("ignore")

from fastapi.testclient import TestClient

from app import auth, lead_v2
from app import lead_handelsvertreter as hv_modul
from app import leadmanagement as kern


# v29 (PLAN_LEAD_V4 Phase 141): Lead-Glocken sind standardmäßig nur für To-Dos
# (Parameter glocke_lead_arten) – Tests, die eine Glocke einer anderen Art prüfen,
# schalten die Art für den Testabschnitt ein (zeigt zugleich die Wiedereinschaltbarkeit).
from contextlib import contextmanager


@contextmanager
def glocken_arten(s, *arten):
    from app import lead_glocken
    alt = kern.parameter_holen(s, lead_glocken.PARAMETER, "")
    kern.parameter_setzen(s, lead_glocken.PARAMETER, ",".join(lead_glocken.STANDARD_ARTEN + tuple(arten)))
    s.commit()
    try:
        yield
    finally:
        kern.parameter_setzen(s, lead_glocken.PARAMETER, alt)
        s.commit()
from app.db import SessionLocal, init_db
from app.main import app
from app.models import (AdProfil, Benachrichtigung, Benutzer, KommunikationLog,
                        Kunde, Lead, LeadAktivitaet, LeadQuelle, Todo, Vorgang,
                        VotTermin)

NACHNAME = "LeadV2H-Test"
PRAEFIX = "LeadV2H "
BASIS = "/lead-management/handelsvertreter"
BOARD_RENE = ("5092657267", "Deals - Rene (Pool Working Space)")
BOARD_SIMON = ("5089971526", "Deals - Simon (Pool Working Space)")
BOARD_DEALS = ("5080725439", "Deals (Blinno Working Space)")


def aufraeumen(s):
    s.rollback()
    benutzer_ids =[b.id for b in s.query(Benutzer).filter(Benutzer.name.like(f"{PRAEFIX}%"))]
    for k in s.query(Kunde).filter(Kunde.nachname.like(f"{NACHNAME}%")):
        for v in s.query(Vorgang).filter_by(kunde_id=k.id):
            s.query(LeadAktivitaet).filter_by(vorgang_id=v.id).delete()
            s.query(KommunikationLog).filter_by(vorgang_id=v.id).delete()
            s.query(VotTermin).filter_by(vorgang_id=v.id).delete()
            s.query(Todo).filter_by(vorgang_id=v.id).delete()
            s.delete(v)
        s.delete(k)
    s.query(Lead).filter(Lead.monday_item_id.like("lv2h-%")).delete(synchronize_session=False)
    s.query(Benachrichtigung).filter(Benachrichtigung.text.like(f"%{NACHNAME}%")).delete(
        synchronize_session=False)
    if benutzer_ids:
        s.query(Benachrichtigung).filter(Benachrichtigung.benutzer_id.in_(benutzer_ids)).delete(
            synchronize_session=False)
        s.query(Todo).filter(Todo.an_benutzer_id.in_(benutzer_ids)).delete(synchronize_session=False)
        s.query(AdProfil).filter(AdProfil.benutzer_id.in_(benutzer_ids)).delete(synchronize_session=False)
        for b in s.query(Benutzer).filter(Benutzer.id.in_(benutzer_ids)):
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
        cls.standard_param = kern.parameter_holen(cls.s, "hv_standard_benutzer", "")
        cls.hv_a = cls.benutzer_anlegen("LeadV2H Vertreter A", hv=True)
        cls.hv_b = cls.benutzer_anlegen("LeadV2H Simon Standard", hv=True)
        cls.ad = cls.benutzer_anlegen("LeadV2H Angestellter AD", hv=False)
        kern.parameter_setzen(cls.s, "hv_standard_benutzer", str(cls.hv_b.id))
        cls.s.commit()
        cls.admin = TestClient(app)
        cls.admin.post("/login", data={"benutzer_id": "1", "pin": "1234"})
        cls.client_a = cls.hv_client(cls.hv_a)
        cls.client_b = cls.hv_client(cls.hv_b)

    @classmethod
    def tearDownClass(cls):
        kern.parameter_setzen(cls.s, "hv_standard_benutzer", cls.standard_param)
        kern.parameter_setzen(cls.s, "lead_freigabe_modus", cls.modus)
        cls.s.commit()
        aufraeumen(cls.s)
        cls.s.close()

    @classmethod
    def benutzer_anlegen(cls, name, hv: bool):
        b = Benutzer(name=name, rolle="aussendienst", aktiv=True,
                     email=f"{name.replace(' ', '.').lower()}@test.local",
                     pin_hash=auth.pin_hash("1234"))
        cls.s.add(b)
        cls.s.flush()
        cls.s.add(AdProfil(benutzer_id=b.id, terminiert_selbst=hv, aktiv_terminierung=True))
        cls.s.commit()
        return b

    @staticmethod
    def hv_client(benutzer):
        c = TestClient(app)
        c.cookies.set(auth.COOKIE_NAME, auth.cookie_wert(benutzer.id))
        return c

    def lead(self, nr, ad_id=None, kanal="", **extra):
        quelle = self.s.query(LeadQuelle).filter_by(key="website").first()
        daten = {"vorname": f"V{nr}", "nachname": f"{NACHNAME}-{nr}", "plz": "47139",
                 "ort": "Duisburg", "strasse": "Testweg 1", "telefon": f"0203 66{nr:04d}",
                 "sparten": ["WP"], "email": f"v2h{nr}@test.local"}
        vorgang, _ = kern.lead_anlegen(self.s, daten, quelle, "api", entscheidung="neu")
        vorgang.demo = True
        if ad_id:
            vorgang.ad_id = ad_id
        if kanal:
            self.s.get(Kunde, vorgang.kunde_id).vertriebskanal = kanal
        for k, v in extra.items():
            setattr(vorgang, k, v)
        self.s.commit()
        return vorgang

    def monday_lead(self, nr, board, benutzer_id=None):
        kunde = Kunde(vorname=f"M{nr}", nachname=f"{NACHNAME}-M{nr}", plz="47051",
                      ort="Duisburg", telefon=f"0203 55{nr:04d}")
        self.s.add(kunde)
        self.s.flush()
        # feste hohe ID: SQLite vergibt sonst freigewordene Lead-IDs neu, auf die
        # verwaiste Bestandsvorgänge (vorgaenge.lead_id unique) noch zeigen
        lead = Lead(id=900000 + nr, monday_item_id=f"lv2h-{nr}", board_id=board[0], board_name=board[1],
                    vorname=kunde.vorname, nachname=kunde.nachname, plz=kunde.plz,
                    ort=kunde.ort, kunde_id=kunde.id, benutzer_id=benutzer_id)
        self.s.add(lead)
        self.s.flush()
        vorgang = Vorgang(kunde_id=kunde.id, lead_id=lead.id, lead_phase="neu",
                          eingang_art="monday", eingang_am=datetime.now(), demo=True)
        self.s.add(vorgang)
        self.s.commit()
        return vorgang, lead

    def name(self, vorgang):
        return self.s.get(Kunde, vorgang.kunde_id).anzeige_name

    @staticmethod
    def marke(vorgang):
        """Zeilen-Marker in der Tabelle (Kundennamen stehen auch in der
        Glocke der Kopfzeile – daher nicht über den Namen prüfen)."""
        return f'data-vorgang="{vorgang.id}"'

    def frisch(self, vorgang):
        self.s.expire_all()
        return self.s.get(Vorgang, vorgang.id)

    def zeile(self, html, vorgang):
        start = html.find(f'data-vorgang="{vorgang.id}"')
        self.assertGreater(start, -1, "Zeile fehlt in der Ansicht")
        ende = html.find("</tr>", start)
        return html[start:ende]


class Rechte(Basis):
    def test_kennzeichen_und_matrix(self):
        admin = self.s.get(Benutzer, 1)
        self.assertFalse(hv_modul.ist_hv(self.s, admin))
        self.assertFalse(hv_modul.ist_hv(self.s, self.ad))
        self.assertTrue(hv_modul.ist_hv(self.s, self.hv_a))
        self.assertTrue({self.hv_a.id, self.hv_b.id} <= hv_modul.hv_ids(self.s))
        self.assertTrue(hv_modul.gesamtsicht(self.s, admin))
        self.assertFalse(hv_modul.gesamtsicht(self.s, self.hv_a))
        erlaubt = [z for z in hv_modul.RECHTE_MATRIX if z[1]]
        gesperrt = [z for z in hv_modul.RECHTE_MATRIX if not z[1]]
        self.assertGreaterEqual(len(erlaubt), 7)
        self.assertGreaterEqual(len(gesperrt), 5)

    def test_eigene_vorgaenge_und_darf(self):
        eigen = self.lead(1, ad_id=self.hv_a.id)
        fremd = self.lead(2, ad_id=self.hv_b.id)
        aus_monday, _ = self.monday_lead(1, BOARD_SIMON, benutzer_id=self.hv_a.id)
        ids = {v.id for v in hv_modul.eigene_vorgaenge(self.s, self.hv_a)}
        self.assertIn(eigen.id, ids)
        self.assertIn(aus_monday.id, ids)
        self.assertNotIn(fremd.id, ids)
        self.assertTrue(hv_modul.darf_vorgang(self.s, self.hv_a, eigen))
        self.assertTrue(hv_modul.darf_vorgang(self.s, self.hv_a, aus_monday))
        self.assertFalse(hv_modul.darf_vorgang(self.s, self.hv_a, fremd))
        self.assertFalse(lead_v2.zugriff_erlaubt(self.s, self.hv_a, fremd))
        self.assertTrue(lead_v2.zugriff_erlaubt(self.s, self.hv_a, eigen))
        self.assertTrue(hv_modul.darf_vorgang(self.s, self.s.get(Benutzer, 1), fremd))
        self.assertFalse(hv_modul.darf_vorgang(self.s, self.ad, eigen))


class Ansicht(Basis):
    def test_hv_sieht_nur_eigene_leads(self):
        eigen = self.lead(10, ad_id=self.hv_a.id)
        fremd = self.lead(11, ad_id=self.hv_b.id)
        r = self.client_a.get(BASIS)
        self.assertEqual(r.status_code, 200)
        self.assertIn(self.name(eigen), r.text)
        self.assertNotIn(self.marke(fremd), r.text)
        self.assertIn("Mein Dashboard", r.text)
        self.assertIn("Wiedervorlagen fällig", r.text)      # F16-Block oben
        # Filter „vertreter“ wird server-seitig ignoriert
        r2 = self.client_a.get(f"{BASIS}?vertreter={self.hv_b.id}")
        self.assertNotIn(self.marke(fremd), r2.text)
        self.assertIn(self.marke(eigen), r2.text)
        # Dropdown: HV sieht alle Vertreter, aber keine Option „nicht zugewiesen“
        zeile = self.zeile(r.text, eigen)
        self.assertIn(self.hv_b.name, zeile)
        self.assertNotIn("nicht zugewiesen", zeile)
        d = self.client_a.get(f"{BASIS}/dashboard")
        self.assertEqual(d.status_code, 200)
        self.assertIn(self.name(eigen), d.text)

    def test_fremde_kartei_und_gesperrte_bereiche_404(self):
        fremd = self.lead(12, ad_id=self.hv_b.id)
        self.assertEqual(self.client_a.get(f"/lead-management/lead/{fremd.id}").status_code, 404)
        for pfad in ("/lead-management/neu", "/lead-management/import",
                     "/lead-management/posteingang", "/lead-management/uebersicht"):
            self.assertEqual(self.client_a.get(pfad).status_code, 404, pfad)
        r = self.client_a.post(f"{BASIS}/{fremd.id}/zuweisen", data={"ad_id": str(self.hv_a.id)})
        self.assertEqual(r.status_code, 404)
        self.assertEqual(self.frisch(fremd).ad_id, self.hv_b.id)
        self.assertEqual(self.client_a.post(f"{BASIS}/standard-nachziehen").status_code, 404)
        self.assertEqual(self.client_a.post(f"{BASIS}/{fremd.id}/standard").status_code, 404)
        # Angestellter AD ohne Kennzeichen: Ansicht 404
        self.assertEqual(self.hv_client(self.ad).get(BASIS).status_code, 404)
        # Innendienst im Demo-Modus: 404
        innen = self.s.query(Benutzer).filter_by(rolle="innendienst", aktiv=True).first()
        if innen is not None:
            self.assertEqual(self.hv_client(innen).get(BASIS).status_code, 404)

    def test_admin_gesamtsicht_gruppen_filter_hinweise(self):
        a = self.lead(13, ad_id=self.hv_a.id)
        b = self.lead(14, ad_id=self.hv_b.id, kanal="Testkanal")
        r = self.admin.get(BASIS)
        self.assertEqual(r.status_code, 200)
        # v29: Kundennamen über die Zeilen-Marker prüfen (keine Lead-Glocke „Neuer Lead“ mehr,
        # die den Namen in der Kopfzeile wiederholt hätte)
        for text in (self.hv_a.name, self.hv_b.name, self.marke(a), self.marke(b),
                     "Standard nachziehen", "nicht zugewiesen"):
            self.assertIn(text, r.text)
        abgleich = hv_modul.benutzer_abgleich(self.s)
        if abgleich["fehlen"]:
            self.assertIn("Noch nicht als Benutzer angelegt", r.text)
            self.assertIn(abgleich["fehlen"][0], r.text)
        # Gruppenzähler je Vertreter
        start = r.text.find(f'data-hv="{self.hv_a.id}"')
        self.assertGreater(start, -1)
        kopf = r.text[start:r.text.find("</summary>", start)]
        self.assertIn('<span class="n ">1</span>', kopf.replace('class="n rot"', 'class="n "'))
        # Filter Vertreter / Status / Kanal / Suche
        f1 = self.admin.get(f"{BASIS}?vertreter={self.hv_a.id}").text
        self.assertIn(self.marke(a), f1)
        self.assertNotIn(self.marke(b), f1)
        f2 = self.admin.get(f"{BASIS}?kanal=Testkanal").text
        self.assertIn(self.marke(b), f2)
        self.assertNotIn(self.marke(a), f2)
        f3 = self.admin.get(f"{BASIS}?q=0203+660013").text
        self.assertIn(self.marke(a), f3)
        self.assertNotIn(self.marke(b), f3)
        f4 = self.admin.get(f"{BASIS}?status=terminiert").text
        self.assertNotIn(self.marke(a), f4)
        f5 = self.admin.get(f"{BASIS}?status=neu&offen=1").text
        self.assertIn(self.marke(a), f5)
        # Dashboard-Vorschau eines Vertreters
        d = self.admin.get(f"{BASIS}/dashboard?hv={self.hv_a.id}")
        self.assertEqual(d.status_code, 200)
        self.assertIn(self.hv_a.name, d.text)
        self.assertIn(self.name(a), d.text)


class Tabelle(Basis):
    def test_phase105_makro_und_rueckfall(self):
        v = self.lead(15, ad_id=self.hv_a.id)
        admin = self.s.get(Benutzer, 1)
        f = hv_modul.filter_aus_query({}, True)
        mit = hv_modul.ansicht(self.s, admin, f)
        ohne = hv_modul.ansicht(self.s, admin, f, mit_phase105=False)
        self.assertFalse(ohne["phase105"])
        eigene = [z for z in ohne["zeilen"] if z["vorgang"].id == v.id][0]
        self.assertEqual(eigene["hv"].id, self.hv_a.id)
        self.assertEqual(eigene["status_label"], "Neu")
        self.assertTrue(eigene["offen"])
        if hv_modul.tabelle_makro_vorhanden():
            self.assertTrue(mit["phase105"])
            zeile = [z for z in mit["zeilen"] if z["vorgang"].id == v.id][0]
            self.assertTrue(zeile.get("phase105"))
            self.assertEqual(zeile["hv"].id, self.hv_a.id)      # HV-Felder obendrauf
            self.assertIn("punkte", zeile)                      # Hauptboard-Felder
            html = self.admin.get(BASIS).text
            self.assertIn('class="sp-lead"', self.zeile(html, v))
        # Rückfall-Rendering erzwingen (Makro „fehlt“)
        original = hv_modul.tabelle_makro_vorhanden
        hv_modul.tabelle_makro_vorhanden = lambda: False
        try:
            html = self.admin.get(BASIS).text
        finally:
            hv_modul.tabelle_makro_vorhanden = original
        zeile = self.zeile(html, v)
        self.assertIn('class="hv-kunde"', zeile)
        self.assertIn("hv-status", zeile)
        self.assertIn(f"tel:", zeile)
        self.assertIn(self.hv_a.name, zeile)


class Zuweisung(Basis):
    def test_umverteilung_schreibt_aktivitaet_und_glocke(self):
        v = self.lead(20, ad_id=self.hv_a.id)
        # v29 (Phase 141): Glocke „zuweisung“ ist standardmäßig aus – nur Aktivität
        r = self.client_a.post(f"{BASIS}/{v.id}/zuweisen",
                               data={"ad_id": str(self.hv_a.id), "zurueck": BASIS},
                               follow_redirects=False)
        self.assertEqual(self.s.query(Benachrichtigung)
                         .filter(Benachrichtigung.benutzer_id == self.hv_b.id,
                                 Benachrichtigung.text.like(f"Lead zugewiesen: {NACHNAME}-20%")).count(), 0)
        with glocken_arten(self.s, "zuweisung"):
            r = self.client_a.post(f"{BASIS}/{v.id}/zuweisen",
                                   data={"ad_id": str(self.hv_b.id), "zurueck": BASIS},
                                   follow_redirects=False)
        self.assertEqual(r.status_code, 303)
        self.assertTrue(r.headers["location"].startswith(BASIS + "?meldung="))
        self.assertEqual(self.frisch(v).ad_id, self.hv_b.id)
        akt = (self.s.query(LeadAktivitaet)
               .filter(LeadAktivitaet.vorgang_id == v.id,
                       LeadAktivitaet.text.like(f"Zugewiesen an {self.hv_b.name}%")).all())
        self.assertEqual(len(akt), 1)
        self.assertEqual(akt[0].benutzer_id, self.hv_a.id)
        self.assertIn(f"(vorher {self.hv_a.name})", akt[0].text)
        glocke = (self.s.query(Benachrichtigung)
                  .filter(Benachrichtigung.benutzer_id == self.hv_b.id,
                          Benachrichtigung.art == "lead",
                          Benachrichtigung.text.like(f"Lead zugewiesen: {NACHNAME}-20%")).count())
        self.assertEqual(glocke, 1)
        # der abgebende Vertreter sieht den Lead nicht mehr und darf ihn nicht mehr anfassen
        self.assertNotIn(self.marke(v), self.client_a.get(BASIS).text)
        self.assertEqual(self.client_a.post(f"{BASIS}/{v.id}/zuweisen",
                                            data={"ad_id": str(self.hv_a.id)}).status_code, 404)
        self.assertIn(self.marke(v), self.client_b.get(BASIS).text)

    def test_hv_nur_an_handelsvertreter_kein_entziehen(self):
        v = self.lead(21, ad_id=self.hv_a.id)
        r = self.client_a.post(f"{BASIS}/{v.id}/zuweisen", data={"ad_id": str(self.ad.id)},
                               follow_redirects=False)
        self.assertIn(quote_plus("Nicht möglich"), r.headers["location"])
        self.assertEqual(self.frisch(v).ad_id, self.hv_a.id)
        self.client_a.post(f"{BASIS}/{v.id}/zuweisen", data={"ad_id": ""}, follow_redirects=False)
        self.assertEqual(self.frisch(v).ad_id, self.hv_a.id)
        # offener Redirect wird abgefangen
        r2 = self.client_a.post(f"{BASIS}/{v.id}/zuweisen",
                                data={"ad_id": str(self.hv_b.id), "zurueck": "https://boese.example/"},
                                follow_redirects=False)
        self.assertTrue(r2.headers["location"].startswith(BASIS))

    def test_ausschluss_blockiert_dropdown_und_server(self):
        v = self.lead(22, kanal="Enni")
        self.assertIn("Innendienst", lead_v2.hv_ausgeschlossen(self.s, v))
        r = self.admin.post(f"{BASIS}/{v.id}/zuweisen", data={"ad_id": str(self.hv_a.id)},
                            follow_redirects=False)
        self.assertIn(quote_plus("Nicht möglich"), r.headers["location"])
        self.assertIsNone(self.frisch(v).ad_id)
        self.assertTrue(hv_modul.zuweisen(self.s, v, self.hv_a.id).startswith("Nicht möglich"))
        self.assertIsNone(self.frisch(v).ad_id)
        # in der Gesamtsicht: Dropdown deaktiviert + Hinweis – Lead ist noch keinem HV
        # zugeordnet, daher über einen zugewiesenen Lead mit Ausschlusskanal prüfen
        w = self.lead(23, ad_id=self.hv_a.id, kanal="Enni")
        html = self.admin.get(BASIS).text
        zeile = self.zeile(html, w)
        self.assertIn("disabled", zeile)
        self.assertIn("nur Innendienst", zeile)
        self.assertIn("Ausschlusskanal", zeile)
        self.assertIn("hv-warn-zeile", zeile)

    def test_admin_zuweisen_entfernen_standardbutton(self):
        v = self.lead(24)
        self.assertEqual(hv_modul.standard_zuweisung(self.s, v), "")   # Tool-Lead: keine Automatik
        r = self.admin.post(f"{BASIS}/{v.id}/zuweisen", data={"ad_id": str(self.hv_a.id)},
                            follow_redirects=False)
        self.assertEqual(r.status_code, 303)
        self.assertEqual(self.frisch(v).ad_id, self.hv_a.id)
        self.admin.post(f"{BASIS}/{v.id}/zuweisen", data={"ad_id": ""}, follow_redirects=False)
        self.assertIsNone(self.frisch(v).ad_id)
        self.assertTrue(self.s.query(LeadAktivitaet)
                        .filter(LeadAktivitaet.vorgang_id == v.id,
                                LeadAktivitaet.text == "Außendienst-Zuweisung entfernt").count())
        # Gesamtsicht: monday-Bestandslead ohne Vertreter steht in der Gruppe
        # „Ohne Vertreter“ mit Button „An Standard (Simon) geben“
        m, _ = self.monday_lead(2, BOARD_DEALS, benutzer_id=None)
        html = self.admin.get(BASIS).text
        self.assertIn("Ohne Vertreter (monday-Bestand)", html)
        zeile = self.zeile(html, m)
        self.assertIn(f"An Standard ({self.hv_b.name}) geben", zeile)
        self.assertIn(f"/handelsvertreter/{m.id}/standard", zeile)
        r2 = self.admin.post(f"{BASIS}/{m.id}/standard", data={"zurueck": BASIS},
                             follow_redirects=False)
        self.assertEqual(r2.status_code, 303)
        self.assertEqual(self.frisch(m).ad_id, self.hv_b.id)
        self.assertNotIn(f'data-vorgang="{m.id}"',
                         self.admin.get(f"{BASIS}?vertreter={self.hv_a.id}").text)
        # HV darf eigenen Lead an den Standard geben
        x = self.lead(26, ad_id=self.hv_a.id)
        r3 = self.client_a.post(f"{BASIS}/{x.id}/standard", follow_redirects=False)
        self.assertEqual(r3.status_code, 303)
        self.assertEqual(self.frisch(x).ad_id, self.hv_b.id)

    def test_monday_abgleich_bei_zuweisung(self):
        v, lead = self.monday_lead(3, BOARD_SIMON, benutzer_id=None)
        meldung = hv_modul.zuweisen(self.s, v, self.hv_a.id, benutzer=self.s.get(Benutzer, 1))
        self.s.commit()
        self.assertTrue(meldung.startswith("Zugewiesen an"))
        self.s.expire_all()
        lead = self.s.get(Lead, lead.id)
        self.assertEqual(lead.benutzer_id, self.hv_a.id)
        self.assertTrue(lead.benutzer_manuell)


class Standard(Basis):
    def test_deals_rene_sonderregel(self):
        rene = hv_modul.rene_benutzer(self.s)
        if rene is None:
            self.skipTest("Kein Benutzer René Golaschewski in dieser DB")
        v, _ = self.monday_lead(4, BOARD_RENE, benutzer_id=None)
        self.assertIn("Sonderregel monday", hv_modul.sonderregel_rene(self.s, v))
        meldung = hv_modul.standard_zuweisung(self.s, v)
        self.s.commit()
        self.assertTrue(meldung.startswith("Zugewiesen an"), meldung)
        self.assertEqual(self.frisch(v).ad_id, rene.id)
        # Umverteilung gesperrt – Dropdown und Server
        self.assertTrue(hv_modul.zuweisen(self.s, v, self.hv_a.id).startswith("Nicht möglich: Sonderregel"))
        r = self.admin.post(f"{BASIS}/{v.id}/zuweisen", data={"ad_id": str(self.hv_a.id)},
                            follow_redirects=False)
        self.assertIn(quote_plus("Sonderregel"), r.headers["location"])
        self.assertEqual(self.frisch(v).ad_id, rene.id)
        zeile = self.zeile(self.admin.get(BASIS).text, v)
        self.assertIn("Sonderregel monday", zeile)
        self.assertIn("disabled", zeile)

    def test_deals_simon_ohne_person_standard_nachziehen(self):
        v, lead = self.monday_lead(5, BOARD_SIMON, benutzer_id=None)
        ziel, erzwingen = hv_modul.standard_ziel(self.s, v)
        self.assertEqual((ziel.id, erzwingen), (self.hv_b.id, False))
        self.assertIn(v.id, [k.id for k in hv_modul.standard_kandidaten(self.s)])
        anzahl = hv_modul.standard_nachziehen(self.s, benutzer=self.s.get(Benutzer, 1))
        self.s.commit()
        self.assertGreaterEqual(anzahl, 1)
        self.assertEqual(self.frisch(v).ad_id, self.hv_b.id)
        self.s.expire_all()
        self.assertEqual(self.s.get(Lead, lead.id).benutzer_id, self.hv_b.id)
        # Route (Admin) – idempotent
        r = self.admin.post(f"{BASIS}/standard-nachziehen", data={"zurueck": BASIS},
                            follow_redirects=False)
        self.assertEqual(r.status_code, 303)
        self.assertIn("Standard+nachgezogen", r.headers["location"])

    def test_monday_person_hv_und_angestellter(self):
        v, _ = self.monday_lead(6, BOARD_SIMON, benutzer_id=self.hv_a.id)
        ziel, erzwingen = hv_modul.standard_ziel(self.s, v)
        self.assertEqual((ziel.id, erzwingen), (self.hv_a.id, True))
        hv_modul.standard_zuweisung(self.s, v)
        self.s.commit()
        self.assertEqual(self.frisch(v).ad_id, self.hv_a.id)
        # Deals (Blinno) mit angestelltem AD: keine HV-Automatik
        w, _ = self.monday_lead(7, BOARD_DEALS, benutzer_id=self.ad.id)
        self.assertEqual(hv_modul.standard_ziel(self.s, w), (None, False))
        self.assertEqual(hv_modul.standard_zuweisung(self.s, w), "")
        self.assertIsNone(self.frisch(w).ad_id)
        # Ausschluss greift bei Standard (nicht erzwungen)
        x, _ = self.monday_lead(8, BOARD_SIMON, benutzer_id=None)
        self.s.get(Kunde, x.kunde_id).vertriebskanal = "Enni"
        self.s.commit()
        self.assertTrue(hv_modul.standard_zuweisung(self.s, x).startswith("Nicht möglich"))
        self.assertIsNone(self.frisch(x).ad_id)


class Kanalwechsel(Basis):
    def test_kanalwechsel_hinweis_glocke_einmalig(self):
        v = self.lead(30, ad_id=self.hv_a.id, leadmanager_id=1)
        self.assertEqual(hv_modul.kanalwechsel_pruefen(self.s, v), "")
        kunde = self.s.get(Kunde, v.kunde_id)
        kunde.vertriebskanal = "Enni"
        self.s.commit()
        with glocken_arten(self.s, "kanalwechsel"):      # v29: Art für den Test eingeschaltet
            hinweis = hv_modul.kanalwechsel_pruefen(self.s, v, benutzer=self.s.get(Benutzer, 1))
            self.s.commit()
        self.assertIn("Ausschlusskanal", hinweis)
        self.assertIn(self.hv_a.name, hinweis)
        self.assertEqual(self.frisch(v).ad_id, self.hv_a.id)   # Zuweisung bleibt (OF-G5)
        akt = lambda: (self.s.query(LeadAktivitaet)
                       .filter(LeadAktivitaet.vorgang_id == v.id,
                               LeadAktivitaet.text.like("Ausschlusskanal:%")).count())
        glocke = lambda: (self.s.query(Benachrichtigung)
                          .filter(Benachrichtigung.benutzer_id == 1,
                                  Benachrichtigung.text.like(
                                      f"Ausschlusskanal bei Handelsvertreter-Lead: {NACHNAME}-30%")).count())
        self.assertEqual((akt(), glocke()), (1, 1))
        # zweiter Aufruf: Hinweis bleibt, kein Doppelalarm
        self.assertIn("Ausschlusskanal", hv_modul.kanalwechsel_pruefen(self.s, v))
        self.s.commit()
        self.assertEqual((akt(), glocke()), (1, 1))
        # Gesamtsicht zeigt den roten Hinweis
        zeile = self.zeile(self.admin.get(BASIS).text, v)
        self.assertIn("Ausschlusskanal", zeile)
        # manuelle Rücknahme durch Innendienst/Admin → Hinweis weg
        self.admin.post(f"{BASIS}/{v.id}/zuweisen", data={"ad_id": ""}, follow_redirects=False)
        self.assertIsNone(self.frisch(v).ad_id)
        self.assertEqual(hv_modul.kanal_hinweis(self.s, self.frisch(v)), "")
        # neue Zuweisung an HV bei Ausschlusskanal bleibt gesperrt
        self.assertTrue(hv_modul.zuweisen(self.s, v, self.hv_a.id).startswith("Nicht möglich"))


class Dashboard(Basis):
    def test_dashboard_daten_und_seite(self):
        jetzt = datetime.now()
        faellig = self.lead(40, ad_id=self.hv_a.id, naechste_aktion_am=jetzt - timedelta(hours=1))
        kommend = self.lead(41, ad_id=self.hv_a.id, wiedervorlage_am=jetzt + timedelta(days=2))
        fremd = self.lead(42, ad_id=self.hv_b.id, naechste_aktion_am=jetzt - timedelta(hours=1))
        termin = VotTermin(vorgang_id=kommend.id, ad_id=self.hv_a.id,
                           beginn=jetzt + timedelta(days=1), ende=jetzt + timedelta(days=1, hours=1),
                           status="geplant", typ="vot", demo=True, adresse="Testweg 1, Duisburg")
        self.s.add(termin)
        self.s.add(Todo(vorgang_id=faellig.id, titel="LeadV2H-Test To-Do", an_benutzer_id=self.hv_a.id,
                        von_benutzer_id=1, status="offen", faellig_am=jetzt + timedelta(days=1)))
        self.s.commit()
        d = hv_modul.dashboard_daten(self.s, self.hv_a)
        self.assertEqual(d["kacheln"]["faellig"], 1)
        self.assertEqual(d["kacheln"]["kommend"], 1)
        self.assertEqual(d["kacheln"]["termine"], 1)
        self.assertGreaterEqual(d["kacheln"]["offen"], 2)
        self.assertEqual(d["kacheln"]["todos"], 1)
        self.assertEqual(d["faellig"][0]["vorgang"].id, faellig.id)
        self.assertEqual(d["termine"][0]["kunde"].id, kommend.kunde_id)
        r = self.client_a.get(f"{BASIS}/dashboard")
        self.assertEqual(r.status_code, 200)
        self.assertIn(self.name(faellig), r.text)
        self.assertIn(self.name(kommend), r.text)
        self.assertNotIn(f"/lead-management/lead/{fremd.id}", r.text)
        self.assertIn("LeadV2H-Test To-Do", r.text)
        self.assertIn("Testweg 1, Duisburg", r.text)


class Robustheit(Basis):
    """Prüfer-Nachtrag: manipulierte Formulare/Query-Parameter → 303 mit
    Meldung bzw. 200, nie 500; Rücksprungziel ohne alte Meldung."""

    def test_ungueltige_eingaben_ohne_500(self):
        v = self.lead(50, ad_id=self.hv_a.id)
        for ad in ("abc", "1.5", "-1", "999999"):
            r = self.admin.post(f"{BASIS}/{v.id}/zuweisen", data={"ad_id": ad, "zurueck": BASIS},
                                follow_redirects=False)
            self.assertEqual(r.status_code, 303, ad)
            self.assertIn("meldung=", r.headers["location"], ad)
            self.assertEqual(self.frisch(v).ad_id, self.hv_a.id, ad)
        self.assertTrue(hv_modul.zuweisen(self.s, v, "abc").startswith("Nicht möglich"))
        # Filter mit Unsinn → 200 (ungültige Werte werden ignoriert), Telefonsuche trifft
        r = self.admin.get(f"{BASIS}?vertreter=abc&status=&kanal=%20&q=%27&offen=0")
        self.assertEqual(r.status_code, 200)
        r = self.admin.get(f"{BASIS}?vertreter=abc&q=0203+660050")
        self.assertIn(self.marke(v), r.text)
        # Leerwert (auch nur Leerzeichen) = Entziehen durch Innendienst/Admin
        r = self.admin.post(f"{BASIS}/{v.id}/zuweisen", data={"ad_id": " ", "zurueck": BASIS},
                            follow_redirects=False)
        self.assertEqual(r.status_code, 303)
        self.assertIsNone(self.frisch(v).ad_id)
        # alte Meldung wird nicht ins Rücksprungziel verschleppt
        r = self.admin.get(f"{BASIS}?offen=1&meldung=alt")
        self.assertEqual(r.status_code, 200)
        self.assertIn('name="zurueck" value="/lead-management/handelsvertreter?offen=1"', r.text)
        self.assertNotIn("meldung=alt", r.text)

    def test_dashboard_auswahl_nur_hv_kreis(self):
        eigen = self.lead(51, ad_id=self.hv_a.id)
        # Admin: fremde/ungültige ?hv= fällt auf einen Vertreter zurück, nie auf den Admin selbst
        for wert in ("abc", "1", "999999"):
            d = self.admin.get(f"{BASIS}/dashboard?hv={wert}")
            self.assertEqual(d.status_code, 200, wert)
            self.assertNotIn('value="1" selected', d.text)
        d = self.admin.get(f"{BASIS}/dashboard?hv={self.hv_a.id}")
        self.assertIn(f'value="{self.hv_a.id}" selected', d.text)
        self.assertIn(self.name(eigen), d.text)
        # Handelsvertreter: ?hv= eines anderen wird ignoriert (immer eigenes Dashboard)
        fremd = self.lead(52, ad_id=self.hv_b.id)
        d = self.client_a.get(f"{BASIS}/dashboard?hv={self.hv_b.id}")
        self.assertEqual(d.status_code, 200)
        self.assertIn(self.hv_a.name, d.text)
        self.assertIn(self.name(eigen), d.text)
        self.assertNotIn(f"/lead-management/lead/{fremd.id}", d.text)


if __name__ == "__main__":
    unittest.main()
