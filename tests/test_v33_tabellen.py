# v33 (PLAN_V20 Phase 174, Protokoll Claudia Castro 14.10.2026 Teil A.4, Agent T):
# Lead-Board-Layout für die Tabellen des Angebotstools – Spaltenkataloge je Board
# (lead_boards.KATALOGE), Rollenregel (Außendienst ohne EK/DB/DB-Ampel, auch gespeicherte
# Keys werden beim Lesen verworfen), Sortierung per Spaltenkopf (gemerkt je Nutzer, server-
# seitig vor dem Rendern), Umbenennen nur für den eigenen Nutzer, Zurücksetzen = heutige
# Spaltenfolge, Summenzeile folgt Filter + Sortierung, alle Tabellen je Rolle hell/dunkel,
# Alias /einstellungen/spalten (Projektierung), Spalte „Endbetrag“ nach Rabatt (Phase 172,
# Vorschlag A 4b), Badge „Simons Gruppe (noch nicht verteilt)“ (Phase 175, Vorschlag R 4c),
# Migration idempotent, Vertrag für M (Katalog leads_vot, zeilen_sortieren mit wert).
import json
import re
import unittest
from datetime import datetime

from fastapi.testclient import TestClient
from sqlalchemy import text

from app import auth, lead_boards, lead_v2, rollen
from app import leadmanagement as kern
from app.db import SessionLocal
from app.main import app
from app.models import (Angebot, AngebotsPosition, Benutzer, BenutzerEinstellung, Erfassung,
                        Kunde, LeadAktivitaet, Vorgang)

PRAEFIX = "V33T"
JS = "app/static/lm_boards.js"
CSS = "app/static/lead_v2.css"


def _client(benutzer_id: int) -> TestClient:
    c = TestClient(app, follow_redirects=False)
    c.cookies.set(auth.COOKIE_NAME, auth.cookie_wert(benutzer_id))
    return c


def _theme(html: str):
    m = re.search(r'<html lang="de"(?: data-theme="(\w+)")?>', html)
    return m.group(1) if m else None


def _kopf_keys(html: str) -> list[str]:
    """Spalten-Keys der Kopfzeile in Reihenfolge (nur Spalten mit Werkzeugen)."""
    return re.findall(r'<th class="sp-([a-z_]+)" data-sort="[a-z_]+"', html)


def _kopf_titel(html: str, key: str) -> str:
    m = re.search(rf'<th class="sp-{key}" data-sort="{key}"[^>]*><span class="lm-th-text">([^<]*)</span>', html)
    return m.group(1) if m else ""


def _zellen(html: str, key: str) -> list[str]:
    """data-wert der Zellen einer Spalte in Zeilenreihenfolge (nur Testzeilen)."""
    werte = []
    for zeile in re.findall(r'<tr data-zeile="\d+" data-suche="[^"]*' + PRAEFIX.lower() + r'[^"]*">.*?</tr>', html, re.S):
        m = re.search(rf'<td class="sp-{key}[^"]*" data-wert="([^"]*)"', zeile)
        werte.append(m.group(1) if m else "")
    return werte


def _lm_daten(html: str) -> dict:
    m = re.search(r'<script type="application/json" id="lm-daten">(.*?)</script>', html, re.S)
    return json.loads(m.group(1)) if m else {}


class Basis(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        s = SessionLocal()
        try:
            cls._aufraeumen(s)
            cls.admin_alt = lead_v2.einstellung_holen(s, 1, lead_boards.EINSTELLUNG_KEY, None)

            def benutzer(name, rolle, **extra):
                b = Benutzer(name=f"{PRAEFIX} {name}", rolle=rolle, aktiv=True,
                             email=f"{name.lower()}@v33t.local", pin_hash=auth.pin_hash("4321"), **extra)
                s.add(b)
                s.flush()
                return b.id

            cls.ad_id = benutzer("Aussendienst", "aussendienst")
            cls.innen_id = benutzer("Innendienst", "innendienst")
            cls.proj_id = benutzer("Projektierung", "projektierung")
            cls.lm_id = benutzer("Leadmanagement", "leadmanagement")
            hv_rolle = "handelsvertreter" if "handelsvertreter" in rollen.katalog() else "aussendienst"
            cls.hv_id = benutzer("Simon Leiter", hv_rolle)
            cls.kunde_ids = []
            for i, (name, objektart) in enumerate((("Alpha", "EFH"), ("Beta", "MFH"), ("Gamma", None))):
                k = Kunde(anrede="Herr", vorname=name, nachname=f"{name}{PRAEFIX}", strasse="Testweg 1",
                          plz="47051", ort="Duisburg", telefon=f"0203 55 {i}00", interesse="WP",
                          objektart=objektart, parteien=6 if objektart == "MFH" else None,
                          vertriebskanal="Enni" if i == 0 else "")
                s.add(k)
                s.flush()
                cls.kunde_ids.append(k.id)
            cls.angebot_ids = {}
            # drei WP-Angebote (19 %) mit 10.000 / 30.000 / 20.000 € netto, ein PV-Angebot
            # (0 % USt) mit 20.000 € netto und 5 % Rabatt → Endbetrag 19.000,00 € (Phase 172)
            for nummer, (kid, netto, typ, ust, rabatt) in enumerate((
                    (cls.kunde_ids[0], 1_000_000, "WP", 19.0, None),
                    (cls.kunde_ids[1], 3_000_000, "WP", 19.0, None),
                    (cls.kunde_ids[2], 2_000_000, "WP", 19.0, None),
                    (cls.kunde_ids[0], 2_000_000, "PV", 0.0, 5.0)), start=1):
                v = Vorgang(kunde_id=kid, lead_phase=None, ad_id=cls.ad_id,
                            verfolgung_status="versendet" if nummer == 1 else "")
                s.add(v)
                s.flush()
                a = Angebot(nummer=f"{PRAEFIX}-{nummer:02d}", kunde_id=kid, vorgang_id=v.id,
                            status="Entwurf", konfigurator_typ=typ, ust_satz=ust,
                            rabatt_prozent=rabatt, vertriebler_id=cls.ad_id,
                            datum=datetime(2026, 10, nummer, 9, 0))
                s.add(a)
                s.flush()
                s.add(AngebotsPosition(angebot_id=a.id, sort=1, block_nr=1, pos_nr="001",
                                       bezeichnung=f"{PRAEFIX} Position", menge=1.0, einheit="psl.",
                                       e_preis_cent=netto, ek_cent=netto // 2))
                cls.angebot_ids[nummer] = a.id
            # Erfassung des AD (Warteschlange) → Angebot 1 gehört dem AD („Meine Angebote“)
            e = Erfassung(kunde_id=cls.kunde_ids[0], benutzer_id=cls.ad_id, status="In TAIFUN zu schreiben",
                          typ="freitext", sparte="WP", angebot_id=cls.angebot_ids[1],
                          abgesendet_am=datetime(2026, 10, 1, 8, 0), ampel="orange",
                          gruende_text="vom Außendienst als individuell erfasst")
            s.add(e)
            s.commit()
        finally:
            s.close()
        cls.admin = _client(1)

    @classmethod
    def _aufraeumen(cls, s):
        kunden = s.query(Kunde).filter(Kunde.nachname.like(f"%{PRAEFIX}")).all()
        for k in kunden:
            for a in s.query(Angebot).filter(Angebot.kunde_id == k.id):
                s.query(AngebotsPosition).filter(AngebotsPosition.angebot_id == a.id).delete(synchronize_session=False)
                s.delete(a)
            s.query(Erfassung).filter(Erfassung.kunde_id == k.id).delete(synchronize_session=False)
            for v in s.query(Vorgang).filter(Vorgang.kunde_id == k.id):
                s.query(LeadAktivitaet).filter(LeadAktivitaet.vorgang_id == v.id).delete(synchronize_session=False)
                s.delete(v)
            s.delete(k)
        for b in s.query(Benutzer).filter(Benutzer.name.like(f"{PRAEFIX} %")):
            s.query(BenutzerEinstellung).filter(BenutzerEinstellung.benutzer_id == b.id).delete(synchronize_session=False)
            s.delete(b)
        s.commit()

    @classmethod
    def tearDownClass(cls):
        s = SessionLocal()
        try:
            cls._aufraeumen(s)
            if cls.admin_alt is None:
                s.execute(text("DELETE FROM benutzer_einstellungen WHERE benutzer_id = 1 AND key = :k"),
                          {"k": lead_boards.EINSTELLUNG_KEY})
            else:
                lead_v2.einstellung_setzen(s, 1, lead_boards.EINSTELLUNG_KEY, cls.admin_alt)
            s.commit()
        finally:
            s.close()

    def spalten_post(self, client, daten: dict):
        return client.post("/lead-management/boards/spalten", json=daten,
                           headers={"Accept": "application/json"})

    def setUp(self):
        # jeder Test startet mit Standard-Spalten des Admins für das Board angebote
        self.spalten_post(self.admin, {"board": "angebote", "zuruecksetzen": True})


class Sortierung(Basis):
    def test_endbetrag_klick_auf_ab_gemerkt(self):
        """Kontrollwert (1): Klick auf „Endbetrag“ → aufsteigend, zweiter Klick absteigend,
        nach Neuladen gemerkt (POST …/spalten + GET der Liste)."""
        r = self.spalten_post(self.admin, {"board": "angebote", "sort": {"key": "endbetrag", "richtung": "auf"}})
        self.assertEqual(r.status_code, 200, r.text)
        self.assertEqual(r.json()["sort"], {"key": "endbetrag", "richtung": "auf"})
        html = self.admin.get(f"/angebote?q={PRAEFIX}").text
        werte = [int(w) for w in _zellen(html, "endbetrag")]
        self.assertEqual(len(werte), 4)
        self.assertEqual(werte, sorted(werte))
        self.assertIn('data-sort="endbetrag" data-key="endbetrag" data-standard="Endbetrag" data-name="" aria-sort="ascending"', html)
        # zweiter Klick: absteigend
        self.spalten_post(self.admin, {"board": "angebote", "sort": {"key": "endbetrag", "richtung": "ab"}})
        html = self.admin.get(f"/angebote?q={PRAEFIX}").text
        werte = [int(w) for w in _zellen(html, "endbetrag")]
        self.assertEqual(werte, sorted(werte, reverse=True))
        self.assertIn('aria-sort="descending"', html)
        # nach „Neuladen“ gemerkt
        geladen = self.admin.get("/lead-management/boards/spalten?board=angebote").json()
        self.assertEqual(geladen["sort"], {"key": "endbetrag", "richtung": "ab"})
        self.assertEqual(_lm_daten(self.admin.get("/angebote").text)["sort"], {"key": "endbetrag", "richtung": "ab"})

    def test_summenzeile_folgt_filter_und_sortierung(self):
        """Summenzeile (v6) über die gefilterte UND sortierte Liste; Endbetrag = nach Rabatt."""
        s = SessionLocal()
        try:
            angebote = s.query(Angebot).filter(Angebot.nummer.like(f"{PRAEFIX}-%")).all()
            erwartet = sum(a.summen()["endbetrag"] for a in angebote)
            netto = sum(a.summen()["netto"] for a in angebote)
            db = sum(a.deckungsbeitrag()["db"] for a in angebote)
        finally:
            s.close()
        from app.templating import euro
        self.spalten_post(self.admin, {"board": "angebote", "sort": {"key": "lead", "richtung": "ab"}})
        html = self.admin.get(f"/angebote?q={PRAEFIX}").text
        summe = re.search(r'<tr class="summenzeile">.*?</tr>', html, re.S).group(0)
        self.assertIn("Summe (4 Angebote)", summe)
        self.assertIn(f"Endbetrag: <strong>{euro(erwartet)}</strong>", summe)
        self.assertIn(f"Netto: <strong>{euro(netto)}</strong>", summe)
        self.assertIn(f"DB: <strong>{euro(db)}</strong>", summe)
        # Filter Sparte PV → nur das PV-Angebot, Summe folgt
        html = self.admin.get(f"/angebote?q={PRAEFIX}&sparte=PV").text
        summe = re.search(r'<tr class="summenzeile">.*?</tr>', html, re.S).group(0)
        self.assertIn("Summe (1 Angebot)", summe)
        self.assertIn("Endbetrag: <strong>19.000,00 €</strong>", summe)

    def test_rabatt_null_prozent_in_liste(self):
        """Phase 172 (Vorschlag A 4b): Spalte „Endbetrag“ zeigt den Betrag nach Rabatt –
        PV 20.000,00 € netto, 0 % USt, 5 % Rabatt → 19.000,00 € in Zeile und Summe."""
        html = self.admin.get(f"/angebote?q={PRAEFIX}&sparte=PV").text
        zeile = re.search(r'<tr data-zeile="\d+" data-suche="[^"]*' + PRAEFIX.lower() + r'-04[^"]*">.*?</tr>', html, re.S).group(0)
        self.assertIn('class="sp-endbetrag" data-wert="1900000"', zeile)
        self.assertIn("19.000,00 €", zeile)
        self.assertNotIn("20.000,00 €", zeile)
        self.assertIn(">Endbetrag</span>", html)
        self.assertNotIn(">Brutto</", html)

    def test_zeilen_sortieren_generisch(self):
        """Vertrag T: zeilen_sortieren mit wert-Callback, leere Werte immer ans Ende, ohne
        Sortierung bleibt die Reihenfolge; Modelle und Dicts."""
        zeilen = [{"n": "b", "w": 2}, {"n": None, "w": None}, {"n": "a", "w": 1}, {"n": "c", "w": None}]
        auf = lead_boards.zeilen_sortieren(list(zeilen), {"key": "n", "richtung": "auf"},
                                           wert=lambda z, k: lead_boards.sort_text(z[k]))
        self.assertEqual([z["n"] for z in auf], ["a", "b", "c", None])
        ab = lead_boards.zeilen_sortieren(list(zeilen), {"key": "w", "richtung": "ab"},
                                          wert=lambda z, k: lead_boards.sort_zahl(z[k]))
        self.assertEqual([z["w"] for z in ab], [2, 1, None, None])
        gleich = lead_boards.zeilen_sortieren(list(zeilen), None, wert=lambda z, k: z[k])
        self.assertEqual(gleich, zeilen)


class Rollen(Basis):
    def test_ad_katalog_ohne_ek_db(self):
        """Kontrollwert (2): AD → GET /lead-management/boards/spalten?board=meine_angebote
        ohne ek/db/db_ampel; ein gespeicherter Satz mit db wird beim Lesen verworfen."""
        ad = _client(self.ad_id)
        for board in ("meine_angebote", "angebote"):
            r = ad.get(f"/lead-management/boards/spalten?board={board}")
            self.assertEqual(r.status_code, 200, r.text)
            keys = [sp["key"] for sp in r.json()["spalten"]]
            for verboten in lead_boards.INTERNE_SPALTEN:
                self.assertNotIn(verboten, keys, board)
            self.assertEqual(keys[0], "lead")
        s = SessionLocal()
        try:
            lead_v2.einstellung_setzen(s, self.ad_id, lead_boards.EINSTELLUNG_KEY, {
                "angebote": {"spalten": [{"key": "db", "sichtbar": True}, {"key": "lead", "sichtbar": True},
                                         {"key": "endbetrag", "sichtbar": True}],
                             "sort": {"key": "db", "richtung": "ab"}}})
            s.commit()
            ad_obj = s.get(Benutzer, self.ad_id)
            self.assertNotIn("db", [sp["key"] for sp in lead_boards.spalten_fuer(s, ad_obj, "angebote")])
            self.assertIsNone(lead_boards.sortierung_fuer(s, ad_obj, "angebote"))
            # der Katalog selbst (serverseitig nach Basisrolle gebaut)
            self.assertNotIn("db", [k for k, _, _ in lead_boards.katalog_fuer("angebote", ad_obj, s)])
            self.assertIn("db", [k for k, _, _ in lead_boards.katalog_fuer("angebote", s.get(Benutzer, 1), s)])
            self.assertIn("db", [k for k, _, _ in lead_boards.katalog_fuer("angebote", self.innen_id, s)])
            # Projektierung ohne Häkchen kalkulation_sichtbar: ebenfalls ohne DB
            self.assertNotIn("db", [k for k, _, _ in lead_boards.katalog_fuer("angebote", self.proj_id, s)])
        finally:
            s.close()
        r = ad.get("/lead-management/boards/spalten?board=angebote")
        self.assertNotIn("db", [sp["key"] for sp in r.json()["spalten"]])
        self.assertIsNone(r.json()["sort"])
        # der AD kann db auch nicht speichern
        r = self.spalten_post(ad, {"board": "meine_angebote", "spalten": [{"key": "db", "sichtbar": True}, {"key": "lead", "sichtbar": True}]})
        self.assertEqual(r.status_code, 200, r.text)
        self.assertNotIn("db", [sp["key"] for sp in r.json()["spalten"]])

    def test_meine_angebote_filter_ohne_db(self):
        ad = _client(self.ad_id)
        html = ad.get("/meine-angebote").text
        self.assertIn('data-lm-spalten-board="meine_angebote"', html)
        self.assertIn(f"{PRAEFIX}-01", html)
        self.assertNotIn('class="sp-db"', html)
        self.assertNotIn("DB:", html)
        self.assertNotIn("db", [sp["key"] for sp in _lm_daten(html)["spalten"]])
        self.assertIn('data-sort="endbetrag"', html)
        self.assertEqual(_kopf_keys(html)[0], "lead")
        self.assertEqual(ad.get("/meine-angebote?status=Entwurf&sparte=WP").status_code, 200)
        leer = ad.get("/meine-angebote?status=Versendet").text
        self.assertNotIn(f"{PRAEFIX}-01", leer)
        self.assertIn("Keine Angebote zu diesem Filter", leer)

    def test_projektierung_alias_route(self):
        """Die Projektierung erreicht /lead-management nicht (Pfadtabelle) – sie speichert
        über den Alias /einstellungen/spalten; der Katalog kommt ohne DB (keine Kalkulationssicht)."""
        proj = _client(self.proj_id)
        r = proj.get("/lead-management/boards/spalten?board=angebote")
        self.assertEqual(r.status_code, 303)
        r = proj.get("/einstellungen/spalten?board=angebote")
        self.assertEqual(r.status_code, 200, r.text)
        self.assertNotIn("db", [sp["key"] for sp in r.json()["spalten"]])
        r = proj.post("/einstellungen/spalten", json={"board": "angebote", "sort": {"key": "datum", "richtung": "ab"}},
                      headers={"Accept": "application/json"})
        self.assertEqual(r.status_code, 200, r.text)
        self.assertEqual(r.json()["sort"], {"key": "datum", "richtung": "ab"})
        html = proj.get(f"/angebote?q={PRAEFIX}").text
        self.assertIn('data-lm-spalten-url="/einstellungen/spalten"', html)
        daten = [d for d in _zellen(html, "datum") if d]
        self.assertEqual(daten, sorted(daten, reverse=True))
        self.assertNotIn('class="sp-db', html)
        self.assertNotIn("DB: <strong>", html)
        self.assertEqual(lead_boards.spalten_url(SessionLocal().get(Benutzer, self.proj_id)), "/einstellungen/spalten")
        self.assertEqual(lead_boards.spalten_url(SessionLocal().get(Benutzer, 1)), "/lead-management/boards/spalten")
        # Admin erreicht den Alias ebenfalls (gleiche Antwort)
        self.assertEqual(self.admin.get("/einstellungen/spalten?board=kunden").json()["board"], "kunden")

    def test_alle_tabellen_je_rolle_hell_dunkel(self):
        """Kontrollwert (6, TestClient-Variante): alle sechs Tabellen je Rolle in beiden Modi."""
        seiten = {
            1: ["/angebote", "/angebote?status=archiv", "/angebote?inaktiv=1", "/erfassungen",
                "/erfassungen?status=In+TAIFUN+zu+schreiben", "/erfassungen?status=individuell-offen",
                "/kunden", "/kunden?inaktive=true&objektart=MFH", "/meine-angebote", "/leads"],
            self.innen_id: ["/angebote", "/erfassungen", "/kunden", "/meine-angebote", "/leads"],
            self.ad_id: ["/meine-angebote", "/meine-angebote?status=Entwurf", "/leads"],
            self.proj_id: ["/angebote", "/erfassungen", "/kunden"],
            self.lm_id: ["/angebote", "/erfassungen", "/kunden"],
        }
        for uid, pfade in seiten.items():
            c = _client(uid)
            try:
                for modus in ("hell", "dunkel"):
                    self.assertEqual(c.post("/einstellungen/darstellung", json={"wert": modus}).status_code, 200)
                    for pfad in pfade:
                        r = c.get(pfad)
                        self.assertEqual(r.status_code, 200, f"{uid} {modus} {pfad}: {r.status_code} {r.headers.get('location', '')}")
                        self.assertEqual(_theme(r.text), modus, f"{uid} {pfad}")
                        if pfad != "/leads":
                            self.assertIn("data-lm-spalten-board=", r.text, pfad)
                            self.assertIn('id="lm-filterblock"', r.text, pfad)
            finally:
                c.post("/einstellungen/darstellung", json={"wert": "geraet"})


class Spalten(Basis):
    def test_umbenennen_nur_fuer_diesen_nutzer(self):
        """Kontrollwert (4): „Vertriebler“ → „AD“ nur für diesen Nutzer."""
        r = self.spalten_post(self.admin, {"board": "angebote", "umbenennen": {"key": "vertriebler", "name": "AD"}})
        self.assertEqual(r.status_code, 200, r.text)
        sp = next(x for x in r.json()["spalten"] if x["key"] == "vertriebler")
        self.assertEqual((sp["titel"], sp["name"], sp["standard"]), ("AD", "AD", "Vertriebler"))
        self.assertEqual(_kopf_titel(self.admin.get("/angebote").text, "vertriebler"), "AD")
        innen = _client(self.innen_id)
        self.assertEqual(_kopf_titel(innen.get("/angebote").text, "vertriebler"), "Vertriebler")
        self.assertEqual(next(x for x in innen.get("/lead-management/boards/spalten?board=angebote").json()["spalten"]
                              if x["key"] == "vertriebler")["titel"], "Vertriebler")
        # leer = Standard
        self.spalten_post(self.admin, {"board": "angebote", "umbenennen": {"key": "vertriebler", "name": ""}})
        self.assertEqual(_kopf_titel(self.admin.get("/angebote").text, "vertriebler"), "Vertriebler")

    def test_zuruecksetzen_heutige_spaltenfolge(self):
        """Kontrollwert (5): Zurücksetzen stellt die heutige Spaltenfolge her (Reihenfolge,
        Sichtbarkeit, Namen, Sortierung)."""
        standard = [k for k, _, _ in lead_boards.KATALOGE["angebote"]]
        liste = [{"key": k, "sichtbar": k not in ("kanal", "datum")} for k in reversed(standard)]
        r = self.spalten_post(self.admin, {"board": "angebote", "spalten": liste})
        self.assertEqual(r.status_code, 200, r.text)
        keys = [sp["key"] for sp in r.json()["spalten"]]
        self.assertEqual(keys[0], "lead")                       # feste Spalte bleibt vorn
        self.assertEqual(keys[1:], list(reversed(standard))[:-1])
        self.spalten_post(self.admin, {"board": "angebote", "umbenennen": {"key": "status", "name": "Stand"}})
        self.spalten_post(self.admin, {"board": "angebote", "sort": {"key": "datum", "richtung": "ab"}})
        html = self.admin.get("/angebote").text
        self.assertNotIn('class="sp-kanal" data-sort', html)
        r = self.spalten_post(self.admin, {"board": "angebote", "zuruecksetzen": True})
        self.assertEqual([sp["key"] for sp in r.json()["spalten"]], standard)
        self.assertTrue(all(sp["name"] == "" for sp in r.json()["spalten"]))
        self.assertIsNone(r.json()["sort"])
        sichtbar = [k for k, _, s in lead_boards.KATALOGE["angebote"] if s]
        self.assertEqual(_kopf_keys(self.admin.get("/angebote").text), sichtbar)
        self.assertEqual(_kopf_titel(self.admin.get("/angebote").text, "status"), "Status")

    def test_warteschlange_feste_spalte_und_kunden_filter(self):
        html = self.admin.get("/erfassungen?status=In+TAIFUN+zu+schreiben").text
        self.assertIn('data-lm-spalten-board="taifun_warteschlange"', html)
        self.assertEqual(_kopf_keys(html)[:2], ["erfassung", "lead"])
        self.assertRegex(html, r'data-key="erfassung"[^>]*draggable="false"')
        self.assertIn('data-key="erfassung" ' , html)
        self.assertIn(f"{PRAEFIX}", html)
        normal = self.admin.get("/erfassungen").text
        self.assertIn('data-lm-spalten-board="erfassungen"', normal)
        self.assertEqual(_kopf_keys(normal)[0], "lead")
        self.assertEqual(lead_boards.spalten_fest("taifun_warteschlange"), ("erfassung",))
        self.assertEqual(lead_boards.spalten_fest("erfassungen"), ("lead",))
        # Kunden: Filter Objektart MFH zeigt nur Beta, Kanal Enni nur Alpha
        mfh = self.admin.get("/kunden?objektart=MFH").text
        self.assertIn(f"Beta{PRAEFIX}", mfh)
        self.assertNotIn(f"Alpha{PRAEFIX}", mfh)
        enni = self.admin.get("/kunden?kanal=Enni").text
        self.assertIn(f"Alpha{PRAEFIX}", enni)
        self.assertNotIn(f"Beta{PRAEFIX}", enni)
        self.assertIn('name="objektart"', enni)
        self.assertIn('data-lm-spalten-board="kunden"', enni)

    def test_vertrag_leads_vot_und_kataloge(self):
        """Vertrag für M: Katalog leads_vot mit den Keys der Rückfallliste in mein_tag.py,
        spalten_fuer/sortierung_fuer je Board; alle sechs Boards bekannt, Lead-Boards unverändert."""
        from app import mein_tag
        self.assertEqual(lead_boards.TABELLEN_BOARDS,
                         ("leads_vot", "erfassungen", "angebote", "meine_angebote", "taifun_warteschlange", "kunden"))
        self.assertEqual(lead_boards.KONFIG_BOARDS, ("hauptboard", "terminiert", "info", "handelsvertreter"))
        self.assertEqual(lead_boards.KATALOGE["leads_vot"], mein_tag.SPALTEN_RUECKFALL)
        for board in lead_boards.TABELLEN_BOARDS:
            self.assertTrue(lead_boards.board_bekannt(board))
            self.assertEqual(lead_boards.KATALOGE[board][0][0], lead_boards.spalten_fest(board)[0])
        s = SessionLocal()
        try:
            ad = s.get(Benutzer, self.ad_id)
            spalten = lead_boards.spalten_fuer(s, ad, "leads_vot")
            self.assertEqual([sp["key"] for sp in spalten], [k for k, _, _ in mein_tag.SPALTEN_RUECKFALL])
            self.assertEqual(spalten[0]["titel"], "Kundenname")
            self.assertIsNone(lead_boards.sortierung_fuer(s, ad, "leads_vot"))
            lead_boards.spalten_speichern(s, ad, "leads_vot", sort={"key": "termin", "richtung": "ab"})
            s.commit()
            self.assertEqual(lead_boards.sortierung_fuer(s, ad, "leads_vot"), {"key": "termin", "richtung": "ab"})
            self.assertEqual(mein_tag.sortierung_fuer(s, ad), {"key": "termin", "richtung": "ab"})
        finally:
            s.close()

    def test_migration_idempotent(self):
        s = SessionLocal()
        try:
            lead_v2.einstellung_setzen(s, self.innen_id, lead_boards.EINSTELLUNG_KEY, {
                "angebote": {"spalten": [{"key": "lead", "sichtbar": True}, {"key": "brutto_alt", "sichtbar": True}],
                             "sort": {"key": "brutto_alt", "richtung": "auf"}},
                "hauptboard": {"spalten": [{"key": "irgendwas", "sichtbar": True}], "sort": None}})
            s.commit()
            meldungen = lead_boards.migration_v33_tabellen(s)
            s.commit()
            self.assertEqual(len(meldungen), 1, meldungen)
            self.assertEqual(lead_boards.migration_v33_tabellen(s), [])
            konfig = lead_v2.einstellung_holen(s, self.innen_id, lead_boards.EINSTELLUNG_KEY, {})
            self.assertEqual([sp["key"] for sp in konfig["angebote"]["spalten"]], ["lead"])
            self.assertIsNone(konfig["angebote"]["sort"])
            self.assertEqual(konfig["hauptboard"]["spalten"][0]["key"], "irgendwas")   # Lead-Boards unangetastet
        finally:
            s.close()

    def test_js_css_markup(self):
        js = open(JS, encoding="utf-8").read()
        for teil in ("data-lm-spalten-board", "lmSpaltenUrl", "'/lead-management/boards/spalten'",
                     "tr[data-zeile]", "lmSuche", "box.disabled", "sort: { key: key", "umbenennen:", "zuruecksetzen: true"):
            self.assertIn(teil, js, teil)
        self.assertNotIn("th.dataset.key === 'lead'", js)
        css = open(CSS, encoding="utf-8").read()
        self.assertIn("Phase 174", css)
        self.assertIn(".lm-tabellen-at", css)
        # v37 (PLAN_LEAD_V7 Phase 197): der Design-v3-Token-Block (Marker wie beim v30-Wächter) darf Hex-Werte
        # tragen und liegt hinter dem v33-Block – nur der Rest bleibt token-rein
        rest = css.split("Phase 174", 1)[1]
        if "/* v3-tokens-anfang */" in rest and "/* v3-tokens-ende */" in rest:
            vor, nach = rest.split("/* v3-tokens-anfang */", 1)
            rest = vor + nach.split("/* v3-tokens-ende */", 1)[1]
        self.assertNotRegex(rest, r"#[0-9a-fA-F]{3,8}\b")
        # Makros generisch: Spaltenwähler + Datenblock einmal je Seite, Script eingebunden
        html = self.admin.get("/kunden").text
        self.assertEqual(html.count('id="lm-spaltenliste"'), 1)
        self.assertEqual(html.count('id="lm-daten"'), 1)
        self.assertIn("/static/lm_boards.js", html)
        self.assertIn('id="lm-tabellen"', html)
        # on*-Attribute vollständig (v30-Regel)
        for wert in re.findall(r'\son[a-z]+="([^"]*)"', html):
            self.assertEqual(wert.count("("), wert.count(")"), wert)


class SimonsGruppe(Basis):
    def test_hv_gruppe_offen_badge(self):
        """Phase 175 (Vorschlag R 4c): Lead an Simons Gruppe ohne gewähltes Mitglied → Zeile
        trägt hv_gruppe_offen, Hauptboard zeigt das Badge in der AD-Zelle."""
        s = SessionLocal()
        alt = kern.parameter_holen(s, "hv_gruppe_simon", "")
        try:
            kern.parameter_setzen(s, "hv_gruppe_simon", str(self.hv_id))
            v = Vorgang(kunde_id=self.kunde_ids[2], lead_phase="neu", ad_id=self.hv_id)
            s.add(v)
            s.flush()
            self.assertTrue(lead_v2.hv_gruppe_offen_setzen(s, v, s.get(Benutzer, 1)))
            s.commit()
            admin = s.get(Benutzer, 1)
            daten = lead_boards.board_zeilen(s, admin, "hauptboard", {"ids": [v.id]})
            zeilen = [z for g in daten["gruppen"] for z in g["zeilen"]]
            self.assertEqual(len(zeilen), 1)
            self.assertTrue(zeilen[0]["hv_gruppe_offen"])
            html = self.admin.get(f"/lead-management/hauptboard?q=Gamma{PRAEFIX}").text
            self.assertIn("Simons Gruppe (noch nicht verteilt)", html)
            self.assertIn(f'data-hv-gruppe-offen="{v.id}"', html)
            # Mitglied gewählt (Marker erledigt) → Kennzeichen weg
            kern.aktivitaet(s, v.id, lead_v2.HV_GRUPPE_MARKER, "verteilt", benutzer=admin, ergebnis="erledigt")
            s.commit()
            daten = lead_boards.board_zeilen(s, admin, "hauptboard", {"ids": [v.id]})
            self.assertFalse([z for g in daten["gruppen"] for z in g["zeilen"]][0]["hv_gruppe_offen"])
        finally:
            kern.parameter_setzen(s, "hv_gruppe_simon", alt)
            s.commit()
            s.close()


if __name__ == "__main__":
    unittest.main()
