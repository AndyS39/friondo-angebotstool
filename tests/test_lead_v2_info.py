# Tests PLAN_LEAD_V2 Phase 111 (CLAUDE v23): Reiter „Info-Veranstaltung“ –
# Board mit Gruppen je Veranstaltung (I2/I3), Archiv, Teilgenommen,
# Veranstaltung je Lead, Sammelaktionen (H3), API-Zuordnung (I4, A-8),
# Abgleich „Kunde bereits im System“ (I5), Termine-Pflege, Gate 404.
# Laufen im Demo-Modus gegen die Entwicklungs-DB; Testleads tragen den
# Nachnamen „LeadV2I-Test“ und werden aufgeräumt.
import json
import unittest
import warnings
from datetime import date, datetime, timedelta

warnings.filterwarnings("ignore")

from fastapi.testclient import TestClient

from app import auth, lead_info
from app import leadmanagement as kern
from app.db import SessionLocal, init_db
from app.main import app
from app.models import (Benachrichtigung, Benutzer, InfoVeranstaltung, KommunikationLog, Kunde,
                        LeadAktivitaet, LeadQuelle, Vorgang, VotTermin)

NACHNAME = "LeadV2I-Test"
API_KEY = "lv2i-test-schluessel-0123456789abcdef"
API_KEY_WEB = "lv2i-test-web-0123456789abcdef"
BOARD = "/lead-management/info-veranstaltung"


def aufraeumen(s):
    # Glocken-Einträge „Neuer Lead: LeadV2I-Test-…“ (lead_anlegen → benachrichtigen)
    s.query(Benachrichtigung).filter(Benachrichtigung.text.like(f"%{NACHNAME}%")).delete(
        synchronize_session=False)
    for k in s.query(Kunde).filter(Kunde.nachname.like(f"{NACHNAME}%")):
        for v in s.query(Vorgang).filter_by(kunde_id=k.id):
            s.query(LeadAktivitaet).filter_by(vorgang_id=v.id).delete()
            s.query(KommunikationLog).filter_by(vorgang_id=v.id).delete()
            s.query(VotTermin).filter_by(vorgang_id=v.id).delete()
            s.delete(v)
        s.delete(k)
    for b in s.query(Benutzer).filter(Benutzer.name.like("LeadV2I %")):
        s.delete(b)
    for q in s.query(LeadQuelle).filter(LeadQuelle.key.like("lv2i-%")):
        s.delete(q)
    # manuell angelegte Test-Veranstaltungen (Jahr 2031)
    for v in s.query(InfoVeranstaltung).filter(InfoVeranstaltung.beginn >= datetime(2031, 1, 1)):
        s.delete(v)
    s.commit()


class Basis(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        init_db()
        cls.s = SessionLocal()
        aufraeumen(cls.s)
        cls.modus = kern.parameter_holen(cls.s, "lead_freigabe_modus", "admin")
        kern.parameter_setzen(cls.s, "lead_freigabe_modus", "admin")
        kern.quellen_vorbelegen(cls.s)
        lead_info.veranstaltungen_anlegen(cls.s)
        cls.quelle = cls.s.query(LeadQuelle).filter_by(key="info_veranstaltung").one()
        cls.api_key_alt = cls.quelle.api_key
        cls.standard_alt = cls.quelle.standard_sparten
        cls.quelle.api_key = API_KEY
        cls.quelle.standard_sparten = "[]"
        cls.quelle.aktiv = True
        cls.web = LeadQuelle(key="lv2i-web", name="LeadV2I Web", typ="website", aktiv=True,
                             api_key=API_KEY_WEB)
        cls.s.add(cls.web)
        cls.s.commit()
        cls.client = TestClient(app)
        cls.client.post("/login", data={"benutzer_id": "1", "pin": "1234"})
        cls.admin = cls.s.get(Benutzer, 1)

    @classmethod
    def tearDownClass(cls):
        q = cls.s.query(LeadQuelle).filter_by(key="info_veranstaltung").first()
        if q is not None:
            q.api_key = cls.api_key_alt
            q.standard_sparten = cls.standard_alt
        aufraeumen(cls.s)
        kern.parameter_setzen(cls.s, "lead_freigabe_modus", cls.modus)
        cls.s.commit()
        cls.s.close()

    # --- Helfer -------------------------------------------------------------------

    def veranstaltung(self, tag: str) -> InfoVeranstaltung:
        """„05.11.2026“ → Veranstaltung (nach veranstaltungen_anlegen vorhanden)."""
        d = datetime.strptime(tag, "%d.%m.%Y").date()
        v = lead_info.veranstaltung_am_tag(self.s, d)
        self.assertIsNotNone(v, f"Veranstaltung {tag} fehlt")
        return v

    def lead(self, nr, veranstaltung=None, quelle_key="info_veranstaltung", **extra):
        quelle = self.s.query(LeadQuelle).filter_by(key=quelle_key).first()
        daten = {"vorname": f"V{nr}", "nachname": f"{NACHNAME}-{nr}", "plz": "47798",
                 "ort": "Krefeld", "telefon": f"02151 55{nr:04d}", "sparten": ["WP"],
                 "email": f"v2i{nr}@test.local"}
        vorgang, _ = kern.lead_anlegen(self.s, daten, quelle, "api", entscheidung="neu")
        vorgang.demo = True
        if veranstaltung is not None:
            vorgang.veranstaltung_id = veranstaltung.id
        for k, v in extra.items():
            setattr(vorgang, k, v)
        self.s.commit()
        return vorgang

    def api(self, daten: dict, key: str = API_KEY):
        return self.client.post("/api/leads", json=daten, headers={"X-Api-Key": key})

    def frisch(self, vorgang: Vorgang) -> Vorgang:
        self.s.expire_all()
        return self.s.get(Vorgang, vorgang.id)

    def aktivitaeten(self, vorgang: Vorgang, typ=None) -> list:
        self.s.expire_all()
        q = self.s.query(LeadAktivitaet).filter_by(vorgang_id=vorgang.id)
        if typ:
            q = q.filter_by(typ=typ)
        return q.order_by(LeadAktivitaet.zeitpunkt, LeadAktivitaet.id).all()

    def benutzer(self, name, rolle):
        b = Benutzer(name=name, rolle=rolle, aktiv=True, pin_hash=auth.pin_hash("1234"))
        self.s.add(b)
        self.s.commit()
        c = TestClient(app)
        c.post("/login", data={"benutzer_id": str(b.id), "pin": "1234"})
        return b, c


# =====================================================================================
class Board(Basis):
    def test_gruppen_kennzeichen_spalten_und_buttons(self):
        v = self.lead(1, self.veranstaltung("05.11.2026"))
        r = self.client.get(BOARD)
        self.assertEqual(r.status_code, 200)
        text = r.text
        # Gruppen je Veranstaltung mit Datum/Uhrzeit/Ort, Kennzeichen Feiertag, Zähler
        for tag in lead_info.KONTROLLTERMINE[1:]:        # 01.10.2026 ist vorbei → Archiv
            self.assertIn(tag, text)
        self.assertIn("Do 05.11.2026 18:00", text)
        self.assertIn("verschoben (Feiertag)", text)
        self.assertIn('data-gruppe="v%d"' % self.veranstaltung("13.05.2027").id, text)
        self.assertIn(lead_info.STANDARD_ORT, text)
        # Zeile: Name mit Link Kartei, Status-Label, Ergebnis-Buttons (Vertrag 107),
        # Teilgenommen, Veranstaltungs-Dropdown, Spaltenkopf wie Hauptboard
        self.assertIn(f'href="/lead-management/lead/{v.id}"', text)
        self.assertIn(f'action="/lead-management/anruf/{v.id}"', text)
        self.assertIn('name="zurueck" value="/lead-management/info-veranstaltung"', text)
        for knopf in ('value="erreicht"', 'value="mailbox"', "Nicht erreicht", "Kein Interesse"):
            self.assertIn(knopf, text)
        self.assertIn(f'action="{BOARD}/{v.id}/teilgenommen"', text)
        self.assertIn(f'action="{BOARD}/{v.id}/veranstaltung"', text)
        for kopf in ("<th class=\"sp-status\">", "<th class=\"sp-teilgenommen\">",
                     "<th class=\"sp-veranstaltung\">", "<th class=\"sp-ergebnis\">",
                     "<th class=\"sp-telefon\">", "<th class=\"sp-interessen\">"):
            self.assertIn(kopf, text)
        self.assertIn("tel:", text)
        self.assertIn("li-sammelform", text)        # Sammelaktionen für Admin
        for aktion in ("Status ändern", "In die nächste Veranstaltung verschieben"):
            self.assertIn(aktion, text)

    def test_archiv_filter(self):
        alt = self.veranstaltung("01.10.2026")
        self.assertTrue(alt.beginn < datetime.now())
        v = self.lead(2, alt)
        r = self.client.get(BOARD)
        self.assertEqual(r.status_code, 200)
        self.assertTrue(self.s.get(InfoVeranstaltung, alt.id).archiviert)   # beim Rendern archiviert
        self.assertNotIn(f'data-vorgang="{v.id}"', r.text)
        r = self.client.get(BOARD + "?archiv=1")
        self.assertEqual(r.status_code, 200)
        self.assertIn(f'data-vorgang="{v.id}"', r.text)
        self.assertIn("01.10.2026", r.text)
        self.assertNotIn("05.11.2026 18:00</span>", r.text)   # kommende Gruppen nicht im Archiv
        self.assertEqual(self.frisch(v).veranstaltung_id, alt.id)   # Lead bleibt zugeordnet

    def test_gruppe_ohne_veranstaltung_und_filter(self):
        v = self.lead(3)       # Quelle info_veranstaltung, keine veranstaltung_id
        r = self.client.get(BOARD)
        self.assertIn("Ohne Veranstaltung", r.text)
        self.assertIn(f'data-vorgang="{v.id}"', r.text)
        v4 = self.lead(4, self.veranstaltung("03.12.2026"))
        r = self.client.get(BOARD + f"?veranstaltung_id={v4.veranstaltung_id}")
        self.assertIn(f'data-vorgang="{v4.id}"', r.text)
        self.assertNotIn(f'data-vorgang="{v.id}"', r.text)
        r = self.client.get(BOARD + "?teilgenommen=ja")
        self.assertNotIn(f'data-vorgang="{v4.id}"', r.text)
        r = self.client.get(BOARD + f"?q={NACHNAME}-4")
        self.assertIn(f'data-vorgang="{v4.id}"', r.text)
        self.assertNotIn(f'data-vorgang="{v.id}"', r.text)

    def test_gate_404_innendienst_im_demo(self):
        innen, c = self.benutzer("LeadV2I Innen", "innendienst")
        v = self.lead(5, self.veranstaltung("05.11.2026"))
        self.assertEqual(c.get(BOARD).status_code, 404)
        self.assertEqual(c.get(BOARD + "/termine").status_code, 404)
        self.assertEqual(c.post(f"{BOARD}/{v.id}/teilgenommen", data={"wert": "ja"}).status_code, 404)
        self.assertEqual(c.post(f"{BOARD}/sammelaktion", data={"aktion": "naechste", "ids": [str(v.id)]}).status_code, 404)
        self.assertIsNone(self.frisch(v).teilgenommen)
        # Admin: unbekannter Vorgang → 404
        self.assertEqual(self.client.post(f"{BOARD}/99999999/teilgenommen", data={"wert": "ja"}).status_code, 404)

    def test_spalten_reihenfolge(self):
        spalten = lead_info.spalten_fuer(self.s, 1, True)
        keys = [sp["key"] for sp in spalten]
        self.assertEqual(keys[:4], ["lead", "status", "ergebnis", "teilgenommen"])
        self.assertEqual(keys[-1], "veranstaltung")
        self.assertIn("telefon", keys)
        rueckfall = [sp["key"] for sp in lead_info.spalten_fuer(self.s, 1, False)]
        self.assertEqual(rueckfall[:4], ["lead", "status", "ergebnis", "teilgenommen"])
        self.assertIn("interessen", rueckfall)

    def test_rueckfall_tabelle_ohne_phase_105_makros(self):
        """Eigene Tabelle/Dialoge, falls _tabelle.html / anruf_dialoge.html fehlen."""
        from app.templating import templates
        v = self.lead(6, self.veranstaltung("05.11.2026"))
        self.s.get(Kunde, v.kunde_id).vertriebskanal = "Enni"
        self.s.commit()
        z = lead_info.zeile_fuer(self.s, self.admin, v)
        self.assertIsNotNone(z)
        self.assertEqual(z["gruppe"], f"v{v.veranstaltung_id}")
        ctx = lead_info.tabellen_kontext(self.s, self.admin)
        ctx.update({"zurueck": BOARD, "tabelle_makro": False, "dialoge_makro": False})
        spalten = lead_info.spalten_fuer(self.s, 1, False)
        modul = templates.env.get_template("leadmanagement/info_tabelle.html").module
        html = str(modul.info_zeile(z, spalten, ctx))
        for teil in (f'data-vorgang="{v.id}"', "lm-status", "Enni", "lm-dots", "tel:",
                     'value="nicht_erreicht"', "li-kein-interesse", "li-teil", "li-veranst-wahl",
                     "WP"):
            self.assertIn(teil, html)
        tabelle = str(modul.info_tabelle([z], spalten, ctx, z["gruppe"]))
        self.assertIn("<thead>", tabelle)
        self.assertIn("li-wahl-alle", tabelle)
        # mit Phase-105-Makro: Inline-Status-Auswahl aus _tabelle.html
        ctx["tabelle_makro"] = True
        html = str(modul.info_zeile(z, lead_info.spalten_fuer(self.s, 1, True), ctx))
        self.assertIn('data-feld="status"', html)
        self.assertIn(f'data-vorgang="{v.id}"', html)

    def test_suchtext_ohne_none_und_vorab_badge(self):
        """Prüfung: leere Kundenfelder dürfen im data-suche nicht als „none“
        landen (Makro rendert mit `or ''` wie _tabelle.html); Kennzeichen
        Vorab-Angebot wie im Hauptboard."""
        v = self.lead(7, self.veranstaltung("05.11.2026"), vorab_angebot=True)
        kunde = self.s.get(Kunde, v.kunde_id)
        kunde.firma = ""
        kunde.ort = ""
        self.s.commit()
        r = self.client.get(BOARD + f"?q={NACHNAME}-7")
        self.assertEqual(r.status_code, 200)
        zeile = r.text[r.text.index(f'data-vorgang="{v.id}"'):]
        zeile = zeile[:zeile.index("</tr>")]
        suche = zeile[zeile.index('data-suche="') + 12:]
        suche = suche[:suche.index('"')]
        self.assertNotIn("none", suche)
        self.assertIn(NACHNAME.lower() + "-7", suche)
        self.assertIn("Vorab-Angebot", zeile)

    def test_statistik_quellen_typ_veranstaltung(self):
        self.assertIn(("veranstaltung", "Info-Veranstaltung"), kern.QUELLEN_GRUPPEN)
        self.assertEqual(kern.quelle_gruppe(self.quelle), "veranstaltung")
        r = self.client.get("/lead-management/uebersicht")
        self.assertEqual(r.status_code, 200)
        self.assertIn("q-veranstaltung", r.text)
        r = self.client.get("/lead-management/statistik")
        self.assertEqual(r.status_code, 200)
        self.assertIn("q-veranstaltung", r.text)


# =====================================================================================
class ApiEingang(Basis):
    def daten(self, nr, **extra):
        d = {"anrede": "Frau", "vorname": f"A{nr}", "nachname": f"{NACHNAME}-API{nr}",
             "plz": "47798", "ort": "Krefeld", "telefon": f"02151 66{nr:04d}",
             "email": f"api{nr}@test.local", "sparten": ["WP"]}
        d.update(extra)
        return d

    def test_zuordnung_naechste_veranstaltung_a8(self):
        r = self.api(self.daten(1))
        self.assertEqual(r.status_code, 201, r.text)
        antwort = r.json()
        v = self.s.get(Vorgang, antwort["vorgang_id"])
        self.assertIsNotNone(v.veranstaltung_id)
        erwartet = lead_info.naechste_veranstaltung(self.s, ab=v.eingang_am)
        self.assertEqual(v.veranstaltung_id, erwartet.id)
        self.assertEqual(antwort["veranstaltung"], erwartet.beginn.strftime("%Y-%m-%d"))
        self.assertIsNone(antwort["hinweis_bestand"])
        self.assertEqual(antwort["status"], "neu")
        texte = [a.text for a in self.aktivitaeten(v, "status")]
        self.assertTrue(any(t.startswith("Veranstaltung: ") and "Vorlauf" in t for t in texte), texte)
        self.assertTrue(v.demo)     # Demo-Modus: API-Leads bleiben Demo-Leads
        # Standardregel direkt: Eingang 30.09.2026 + 3 Tage Vorlauf → 05.11.2026
        v2 = self.lead(10)
        self.assertIsNone(v2.veranstaltung_id)
        z = lead_info.zuordnen_bei_eingang(self.s, v2, self.quelle, eingang=datetime(2026, 9, 30, 12, 0))
        self.s.commit()
        self.assertEqual(z.beginn, datetime(2026, 11, 5, 18, 0))
        self.assertEqual(self.frisch(v2).veranstaltung_id, z.id)
        # keine Info-Quelle → keine Zuordnung
        web = self.lead(11, quelle_key="lv2i-web")
        self.assertIsNone(lead_info.zuordnen_bei_eingang(self.s, web, self.web))
        self.assertIsNone(self.frisch(web).veranstaltung_id)

    def test_feld_veranstaltung_uebersteuert(self):
        r = self.api(self.daten(2, veranstaltung="2026-12-03"))
        self.assertEqual(r.status_code, 201, r.text)
        self.assertEqual(r.json()["veranstaltung"], "2026-12-03")
        v = self.s.get(Vorgang, r.json()["vorgang_id"])
        self.assertEqual(v.veranstaltung_id, self.veranstaltung("03.12.2026").id)
        # auch für eine Nicht-Info-Quelle: Feld ordnet zu (Annahme)
        r = self.api(self.daten(3, veranstaltung="2027-05-13"), key=API_KEY_WEB)
        self.assertEqual(r.status_code, 201, r.text)
        self.assertEqual(r.json()["veranstaltung"], "2027-05-13")
        # unlesbar / ohne Veranstaltung → 422 mit Hinweis
        r = self.api(self.daten(4, veranstaltung="2026-13-45"))
        self.assertEqual(r.status_code, 422)
        self.assertIn("veranstaltung", r.json()["felder"])
        r = self.api(self.daten(5, veranstaltung="2026-11-06"))
        self.assertEqual(r.status_code, 422)
        self.assertIn("naechste_termine", r.json())
        self.assertIn("2026-11-05", r.json()["naechste_termine"])
        self.assertIn("06.11.2026", r.json()["fehler"])

    def test_standard_sparten_und_gw(self):
        d = self.daten(6)
        d.pop("sparten")
        r = self.api(d)
        self.assertEqual(r.status_code, 422)
        self.assertIn("sparten (WP/PV/KL/WB/GW)", r.json()["felder"])
        self.quelle.standard_sparten = json.dumps(["WP", "GW"])
        self.s.commit()
        try:
            r = self.api(d)
            self.assertEqual(r.status_code, 201, r.text)
            self.assertEqual(r.json()["sparten"], ["WP", "GW"])
            kunde = self.s.get(Kunde, self.s.get(Vorgang, r.json()["vorgang_id"]).kunde_id)
            self.assertEqual(kunde.interesse, "WP,GW")
        finally:
            self.quelle.standard_sparten = "[]"
            self.s.commit()
        # Sparte GW direkt und als Klartext-Alias
        r = self.api(self.daten(7, sparten=["Gewerbe", "PV"]))
        self.assertEqual(r.status_code, 201, r.text)
        kunde = self.s.get(Kunde, self.s.get(Vorgang, r.json()["vorgang_id"]).kunde_id)
        self.assertEqual(sorted(kunde.interesse.split(",")), ["GW", "PV"])

    def test_abgleich_email_und_nachname(self):
        bestand = self.lead(20, quelle_key="lv2i-web", lead_phase="terminiert")
        kunde = self.s.get(Kunde, bestand.kunde_id)
        r = self.api(self.daten(21, nachname=kunde.nachname, email=kunde.email.upper(),
                                telefon="02151 999999"))
        self.assertEqual(r.status_code, 201, r.text)       # kein 409 für Info-Leads
        antwort = r.json()
        self.assertEqual(antwort["status"], "neu")
        self.assertEqual(antwort["hinweis_bestand"]["vorgang_id"], bestand.id)
        self.assertEqual(antwort["hinweis_bestand"]["phase"], "terminiert")
        neu = self.s.get(Vorgang, antwort["vorgang_id"])
        self.assertNotEqual(neu.id, bestand.id)
        self.assertNotEqual(neu.kunde_id, bestand.kunde_id)   # eigener Vorgang, kein Zusammenführen
        hinweise = self.aktivitaeten(neu, "hinweis")
        self.assertEqual(len(hinweise), 1)
        self.assertIn(f"Kunde bereits im System: Vorgang #{bestand.id} (Phase Terminiert)", hinweise[0].text)
        self.assertEqual(lead_info.bestand_hinweis(self.s, neu)["vorgang_id"], bestand.id)
        # roter Hinweis mit Link im Board
        r = self.client.get(BOARD)
        self.assertIn("Kunde bereits im System", r.text)
        self.assertIn(f'href="/lead-management/lead/{bestand.id}"', r.text)
        self.assertIn("li-hinweis", r.text)
        # Nachname gleich, aber weder E-Mail noch Telefon → kein Treffer
        r = self.api(self.daten(22, nachname=kunde.nachname, email="anders22@test.local",
                                telefon="02151 888888"))
        self.assertEqual(r.status_code, 201)
        self.assertIsNone(r.json()["hinweis_bestand"])
        # E-Mail gleich, Nachname anders → kein Treffer
        r = self.api(self.daten(23, nachname=f"{NACHNAME}-Anders", email=kunde.email))
        self.assertEqual(r.status_code, 201)
        self.assertIsNone(r.json()["hinweis_bestand"])

    def test_abgleich_telefon_schreibweisen(self):
        bestand = self.lead(30, quelle_key="lv2i-web")
        kunde = self.s.get(Kunde, bestand.kunde_id)
        self.assertEqual(kunde.telefon, "02151 550030")
        for schreibweise in ("+49 2151 550030", "+49 (2151) 55 00 30", "0049 2151 550030",
                             "02151/550030", "02151-55 00 30"):
            treffer = lead_info.bestand_abgleich(self.s, telefon=schreibweise, email="x@y.z",
                                                 nachname=f" {NACHNAME.lower()}-30 ")
            self.assertIsNotNone(treffer, schreibweise)
            self.assertEqual(treffer["vorgang"].id, bestand.id, schreibweise)
        self.assertIsNone(lead_info.bestand_abgleich(self.s, telefon="02151 550031", nachname=kunde.nachname))
        self.assertIsNone(lead_info.bestand_abgleich(self.s, telefon=kunde.telefon, nachname=""))
        self.assertIsNone(lead_info.bestand_abgleich(self.s, telefon="", email="", nachname=kunde.nachname))
        # Nachname-Normalisierung: Umlaute, Bindestrich, Groß/Klein
        self.assertEqual(lead_info._nachname_normal(" Müller-Lüdenscheidt "), lead_info._nachname_normal("MUELLER LUDENSCHEIDT".replace("UE", "Ü")))
        self.assertEqual(lead_info._nachname_normal("Straß"), "strass")
        # API: Telefon in anderer Schreibweise → Hinweis
        r = self.api(self.daten(31, nachname=kunde.nachname, telefon="+49 2151 55 00 30",
                                email="anders31@test.local"))
        self.assertEqual(r.status_code, 201, r.text)
        self.assertEqual(r.json()["hinweis_bestand"]["vorgang_id"], bestand.id)

    def test_demo_vorgaenge_ignoriert_bei_modus_alle(self):
        bestand = self.lead(40, quelle_key="lv2i-web")      # demo = True
        kunde = self.s.get(Kunde, bestand.kunde_id)
        self.assertIsNotNone(lead_info.bestand_abgleich(self.s, telefon=kunde.telefon, nachname=kunde.nachname))
        kern.parameter_setzen(self.s, "lead_freigabe_modus", "alle")
        self.s.commit()
        try:
            self.assertIsNone(lead_info.bestand_abgleich(self.s, telefon=kunde.telefon, nachname=kunde.nachname))
        finally:
            kern.parameter_setzen(self.s, "lead_freigabe_modus", "admin")
            self.s.commit()

    def test_duplikat_409_fuer_andere_quellen_unveraendert(self):
        d = self.daten(50)
        r1 = self.api(d, key=API_KEY_WEB)
        self.assertEqual(r1.status_code, 201, r1.text)
        self.assertIsNone(r1.json()["veranstaltung"])
        r2 = self.api(d, key=API_KEY_WEB)
        self.assertEqual(r2.status_code, 409)
        self.assertEqual(r2.json()["status"], "angehaengt")
        # Info-Quelle: zweimal dieselbe Anmeldung → zwei Vorgänge + Hinweis
        d = self.daten(51)
        r1 = self.api(d)
        r2 = self.api(d)
        self.assertEqual((r1.status_code, r2.status_code), (201, 201))
        self.assertNotEqual(r1.json()["vorgang_id"], r2.json()["vorgang_id"])
        self.assertEqual(r2.json()["hinweis_bestand"]["vorgang_id"], r1.json()["vorgang_id"])


# =====================================================================================
class Aktionen(Basis):
    def test_teilgenommen_toggle(self):
        v = self.lead(60, self.veranstaltung("05.11.2026"))
        r = self.client.post(f"{BOARD}/{v.id}/teilgenommen", data={"wert": "ja"}, follow_redirects=False)
        self.assertEqual(r.status_code, 303)
        self.assertTrue(r.headers["location"].startswith(BOARD))
        self.assertIn("meldung=", r.headers["location"])
        self.assertTrue(self.frisch(v).teilgenommen)
        self.assertIn("Teilgenommen: Ja", [a.text for a in self.aktivitaeten(v, "status")])
        # JSON (fetch): Zeile kommt neu gerendert zurück
        r = self.client.post(f"{BOARD}/{v.id}/teilgenommen", json={"wert": "nein"},
                             headers={"Accept": "application/json"})
        self.assertEqual(r.status_code, 200, r.text)
        antwort = r.json()
        self.assertTrue(antwort["ok"])
        self.assertEqual(antwort["teilgenommen"], "nein")
        self.assertIn("li-teil nein", antwort["zeile_html"])
        self.assertIn(f'data-vorgang="{v.id}"', antwort["zeile_html"])
        self.assertEqual(antwort["gruppe"], f"v{v.veranstaltung_id}")
        self.assertIs(self.frisch(v).teilgenommen, False)
        r = self.client.post(f"{BOARD}/{v.id}/teilgenommen", json={"wert": "leer"},
                             headers={"Accept": "application/json"})
        self.assertEqual(r.json()["teilgenommen"], "")
        self.assertIsNone(self.frisch(v).teilgenommen)
        r = self.client.post(f"{BOARD}/{v.id}/teilgenommen", json={"wert": "vielleicht"},
                             headers={"Accept": "application/json"})
        self.assertEqual(r.status_code, 422)
        # Zurück-Pfad nur relativ
        r = self.client.post(f"{BOARD}/{v.id}/teilgenommen",
                             data={"wert": "ja", "zurueck": "https://boese.example/"}, follow_redirects=False)
        self.assertTrue(r.headers["location"].startswith(BOARD))

    def test_veranstaltung_dropdown(self):
        v = self.lead(61, self.veranstaltung("05.11.2026"))
        ziel = self.veranstaltung("04.02.2027")
        r = self.client.post(f"{BOARD}/{v.id}/veranstaltung", json={"veranstaltung_id": ziel.id},
                             headers={"Accept": "application/json"})
        self.assertEqual(r.status_code, 200, r.text)
        self.assertEqual(r.json()["gruppe"], f"v{ziel.id}")
        self.assertEqual(self.frisch(v).veranstaltung_id, ziel.id)
        texte = [a.text for a in self.aktivitaeten(v, "status")]
        self.assertTrue(any("Veranstaltung geändert: Do 05.11.2026 18:00 → Do 04.02.2027 18:00" in t for t in texte), texte)
        # aufheben
        r = self.client.post(f"{BOARD}/{v.id}/veranstaltung", data={"veranstaltung_id": ""}, follow_redirects=False)
        self.assertEqual(r.status_code, 303)
        self.assertIsNone(self.frisch(v).veranstaltung_id)
        self.assertEqual(self.client.post(f"{BOARD}/{v.id}/veranstaltung", json={"veranstaltung_id": 99999999},
                                          headers={"Accept": "application/json"}).status_code, 422)

    def test_sammelaktion_naechste_veranstaltung(self):
        nov = self.veranstaltung("05.11.2026")
        dez = self.veranstaltung("03.12.2026")
        v1, v2 = self.lead(62, nov), self.lead(63, nov)
        mai = self.lead(64, self.veranstaltung("13.05.2027"))
        ohne = self.lead(65)
        r = self.client.post(f"{BOARD}/sammelaktion",
                             data={"aktion": "naechste", "ids": [str(v1.id), str(v2.id), str(mai.id), str(ohne.id)]},
                             follow_redirects=False)
        self.assertEqual(r.status_code, 303)
        self.assertIn("4+von+4", r.headers["location"])
        self.assertNotIn("fehler=1", r.headers["location"])
        self.assertEqual(self.frisch(v1).veranstaltung_id, dez.id)
        self.assertEqual(self.frisch(v2).veranstaltung_id, dez.id)
        self.assertEqual(self.frisch(mai).veranstaltung_id, self.veranstaltung("03.06.2027").id)
        self.assertEqual(self.frisch(ohne).veranstaltung_id,
                         lead_info.naechste_veranstaltung(self.s).id)
        for v in (v1, v2, mai):
            texte = [a.text for a in self.aktivitaeten(v, "status")]
            self.assertTrue(any("in die nächste Veranstaltung verschoben" in t for t in texte), texte)
        # Registry von Phase 105: Board „info“ mit drei Aktionen
        try:
            from app import lead_boards
            keys = [a["key"] for a in lead_boards.sammelaktionen_fuer("info")]
            self.assertEqual(keys, ["status", "naechste", "teilgenommen"])
        except ImportError:
            pass
        # ohne Auswahl / unbekannte Aktion
        r = self.client.post(f"{BOARD}/sammelaktion", data={"aktion": "naechste"}, follow_redirects=False)
        self.assertIn("fehler=1", r.headers["location"])
        r = self.client.post(f"{BOARD}/sammelaktion", data={"aktion": "x", "ids": [str(v1.id)]},
                             headers={"Accept": "application/json"})
        self.assertEqual(r.status_code, 422)

    def test_sammelaktion_status_mit_pflichtgruenden(self):
        nov = self.veranstaltung("05.11.2026")
        v1, v2 = self.lead(66, nov), self.lead(67, nov)
        bis = (date.today() + timedelta(days=10)).strftime("%Y-%m-%d")
        r = self.client.post(f"{BOARD}/sammelaktion",
                             data={"aktion": "status", "status": "zurueckgestellt",
                                   "grund": "Kunde meldet sich selbst", "bis": bis,
                                   "ids": [str(v1.id), str(v2.id)]}, follow_redirects=False)
        self.assertEqual(r.status_code, 303, r.text)
        self.assertNotIn("fehler=1", r.headers["location"])
        for v in (v1, v2):
            f = self.frisch(v)
            self.assertEqual(f.lead_phase, "zurueckgestellt")
            self.assertEqual(f.zurueckgestellt_bis.date().strftime("%Y-%m-%d"), bis)
            texte = [a.text for a in self.aktivitaeten(v, "status")]
            self.assertTrue(any(t.startswith("Sammelaktion – Zurückgestellt") for t in texte), texte)
        # Unqualifiziert ohne Grund → Fehler, Phase bleibt
        r = self.client.post(f"{BOARD}/sammelaktion",
                             data={"aktion": "status", "status": "unqualifiziert", "ids": [str(v1.id)]},
                             follow_redirects=False)
        self.assertIn("fehler=1", r.headers["location"])
        self.assertEqual(self.frisch(v1).lead_phase, "zurueckgestellt")
        # Verloren mit Grund aus dem Blatt Gruende
        r = self.client.post(f"{BOARD}/sammelaktion",
                             data={"aktion": "status", "status": "verloren", "grund": "Zu teuer",
                                   "ids": [str(v2.id)]}, follow_redirects=False)
        self.assertNotIn("fehler=1", r.headers["location"])
        self.assertEqual(self.frisch(v2).lead_phase, "verloren")

    def test_sammelaktion_teilgenommen(self):
        nov = self.veranstaltung("05.11.2026")
        v1, v2 = self.lead(68, nov), self.lead(69, nov)
        r = self.client.post(f"{BOARD}/sammelaktion",
                             json={"aktion": "teilgenommen", "teilgenommen": "ja", "ids": [v1.id, v2.id]},
                             headers={"Accept": "application/json"})
        self.assertEqual(r.status_code, 200, r.text)
        self.assertTrue(self.frisch(v1).teilgenommen)
        self.assertTrue(self.frisch(v2).teilgenommen)

    def test_inline_zeile_und_ergebnis_button(self):
        v = self.lead(70, self.veranstaltung("05.11.2026"))
        r = self.client.post(f"{BOARD}/{v.id}/zeile", json={"feld": "notiz", "wert": "Rückruf abends"},
                             headers={"Accept": "application/json"})
        self.assertEqual(r.status_code, 200, r.text)
        self.assertTrue(r.json()["ok"])
        self.assertIn("Rückruf abends", r.json().get("zeile_html", ""))
        self.assertEqual(self.s.get(Kunde, v.kunde_id).notizen, "Rückruf abends")
        # Ergebnis-Button (Vertrag Phase 107): Mailbox mit zurueck = Board
        r = self.client.post(f"/lead-management/anruf/{v.id}",
                             data={"ergebnis": "mailbox", "zurueck": BOARD, "dauer_sek": "45"},
                             follow_redirects=False)
        self.assertEqual(r.status_code, 303)
        self.assertTrue(r.headers["location"].startswith(BOARD))
        f = self.frisch(v)
        self.assertEqual(f.versuch_nr, 1)
        self.assertEqual(f.lead_phase, "in_kontaktierung")
        # Lead bleibt auf dem Info-Board (normale Phase, gleiche Veranstaltung)
        r = self.client.get(BOARD)
        self.assertIn(f'data-vorgang="{v.id}"', r.text)


# =====================================================================================
class Termine(Basis):
    def test_pflegeseite_und_aktionen(self):
        r = self.client.get(BOARD + "/termine")
        self.assertEqual(r.status_code, 200)
        for tag in lead_info.KONTROLLTERMINE:
            self.assertIn(tag, r.text)
        self.assertIn("Christi Himmelfahrt", r.text)
        self.assertIn("/parametrierung/lead-einstellungen", r.text)
        self.assertIn("info_*", r.text)
        # anlegen (außerhalb der Regel, Jahr 2031 → aufräumen löscht)
        r = self.client.post(BOARD + "/termine", data={"aktion": "anlegen", "beginn": "2031-01-10T18:00",
                                                       "ort": "Testhalle"}, follow_redirects=False)
        self.assertNotIn("fehler=1", r.headers["location"])
        self.s.expire_all()
        v = self.s.query(InfoVeranstaltung).filter_by(beginn=datetime(2031, 1, 10, 18, 0)).one()
        self.assertEqual(v.ort, "Testhalle")
        # doppelt → Fehler
        r = self.client.post(BOARD + "/termine", data={"aktion": "anlegen", "beginn": "2031-01-10T18:00"},
                             follow_redirects=False)
        self.assertIn("fehler=1", r.headers["location"])
        # Notiz
        r = self.client.post(BOARD + "/termine", data={"aktion": "notiz", "id": str(v.id), "notiz": "Beamer mitbringen"},
                             follow_redirects=False)
        self.s.expire_all()
        self.assertEqual(self.s.get(InfoVeranstaltung, v.id).notiz, "Beamer mitbringen")
        # verschieben: Leads bleiben zugeordnet, Regel legt den Monat nicht erneut an
        lead = self.lead(80, v)
        r = self.client.post(BOARD + "/termine", data={"aktion": "verschieben", "id": str(v.id),
                                                       "beginn": "2031-01-17T19:00"}, follow_redirects=False)
        self.assertNotIn("fehler=1", r.headers["location"])
        self.s.expire_all()
        v = self.s.get(InfoVeranstaltung, v.id)
        self.assertEqual(v.beginn, datetime(2031, 1, 17, 19, 0))
        self.assertIn("Manuell verschoben", v.notiz)
        self.assertEqual(self.frisch(lead).veranstaltung_id, v.id)
        self.assertEqual(lead_info.veranstaltungen_anlegen(self.s, ab=date(2031, 1, 1), monate=1), 0)
        # archivieren / reaktivieren
        r = self.client.post(BOARD + "/termine", data={"aktion": "archiv", "id": str(v.id), "archiviert": "1"},
                             follow_redirects=False)
        self.s.expire_all()
        self.assertTrue(self.s.get(InfoVeranstaltung, v.id).archiviert)
        r = self.client.get(BOARD + "?archiv=1")
        self.assertIn(f'data-vorgang="{lead.id}"', r.text)
        r = self.client.post(BOARD + "/termine", data={"aktion": "archiv", "id": str(v.id), "archiviert": "0"},
                             follow_redirects=False)
        self.s.expire_all()
        self.assertFalse(self.s.get(InfoVeranstaltung, v.id).archiviert)
        # Board zeigt die Veranstaltung mit Notiz
        r = self.client.get(BOARD)
        self.assertIn("Fr 17.01.2031 19:00", r.text)
        self.assertIn("Beamer mitbringen", r.text)

    def test_naechste_nach_und_titel(self):
        nov = self.veranstaltung("05.11.2026")
        self.assertEqual(lead_info.naechste_nach(self.s, nov).beginn, datetime(2026, 12, 3, 18, 0))
        self.assertEqual(lead_info.titel(nov), "Do 05.11.2026 18:00")
        letzte = (self.s.query(InfoVeranstaltung).filter(InfoVeranstaltung.beginn < datetime(2031, 1, 1))
                  .order_by(InfoVeranstaltung.beginn.desc()).first())
        folge = lead_info.naechste_nach(self.s, letzte)      # legt rollierend nach
        self.s.commit()      # Schreibsperre der Testsitzung freigeben (WAL: ein Schreiber)
        self.assertIsNotNone(folge)
        self.assertGreater(folge.beginn, letzte.beginn)
        self.assertEqual(lead_info.datum_lesen("05.11.2026"), date(2026, 11, 5))
        self.assertEqual(lead_info.datum_lesen("2026-11-05T10:00"), date(2026, 11, 5))
        self.assertIsNone(lead_info.datum_lesen("Donnerstag"))
        self.assertTrue(lead_info.ist_info_quelle(self.quelle))
        self.assertFalse(lead_info.ist_info_quelle(self.web))
        self.assertFalse(lead_info.ist_info_quelle(None))


if __name__ == "__main__":
    unittest.main()
