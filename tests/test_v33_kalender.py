# v33 (PLAN_V20 Phase 169, Agent K): zentraler Planungskalender /kalender.
# Vorbelegung je Einstieg (Projektierung → Monteure + Projektierer, Lead → AD + HV,
# Admin → alle), Gruppen-Zuordnung über Basisrolle/Kennzeichen/Gewerk, Gruppenfilter/Suche/
# gemerkte Auswahl (kalender_gruppen je Einstieg), alle Terminarten (VOT, Telefon, Sperrzeit,
# Montage, Elektro, Sub, Feinplanung, Abnahme, Sonstiges, Service) + Abwesenheit + Outlook-
# Belegt im JSON (Montagetermin mit zwei Monteuren in beiden Zeilen), kein Betreff fremder
# Einträge, Drag verschiebt VOT (lead_termin-Kern, Umbuchung) und Projekt-Termin
# (projektierung.termin_verschieben bzw. Rückfall) mit Protokoll, Konfliktbestätigung,
# Rechte (Montage nur eigene + Team, read-only), Einbindung (Menü, Icon-Leiste, Team-Kalender,
# v12-Umleitung), JSON-Zeit für 60 Personen × 1 Woche (großzügige Grenze, Messwert im Bericht).
# Läuft gegen die DB-Kopie (DB_PFAD_OVERRIDE); alle Testdaten tragen das Präfix V33K und
# werden am Ende entfernt; terminierung_aktiv wird nur für die Dauer der Tests eingeschaltet.
import json
import re
import statistics
import time
import unittest
import warnings
from datetime import date, datetime, timedelta

warnings.filterwarnings("ignore")

from fastapi.testclient import TestClient
from starlette.requests import Request

from app import auth, kalender_zentral as kz
from app import leadmanagement as lead_kern
from app.db import SessionLocal, init_db
from app.main import app
from app.models import (AdProfil, Benachrichtigung, Benutzer, BenutzerAbwesenheit,
                        BenutzerEinstellung, Gewerk, KommunikationLog, Kunde, LeadAktivitaet,
                        OutlookBelegt, Projekt, ProjektTermin, ProjektVerlauf, Team, TeamMitglied,
                        TerminBesetzung, Vorgang, VorgangObjekt, VorgangsNotiz, VotTermin)

PRAEFIX = "V33K"
KONTEXT_RE = re.compile(r'id="kz-kontext">(.*?)</script>', re.S)
ERLAUBTE_FELDER = {"key", "id", "quelle", "art", "art_name", "beginn", "ende", "ganztaegig",
                   "kunde", "ort", "text", "link", "personen", "farbe_klasse", "verschiebbar",
                   "status", "vorgang_id", "monday", "projekt_id", "gewerk_id", "von", "bis"}


def _client(benutzer_id: int) -> TestClient:
    c = TestClient(app, follow_redirects=False)
    c.cookies.set(auth.COOKIE_NAME, auth.cookie_wert(benutzer_id))
    return c


def _kontext(html: str) -> dict:
    m = KONTEXT_RE.search(html)
    assert m, "Kontext-Block kz-kontext fehlt"
    return json.loads(m.group(1))


def _naechster_montag() -> date:
    heute = date.today()
    return heute + timedelta(days=(7 - heute.weekday()) % 7 or 7)


def _dt(tag: date, stunde: int, minute: int = 0) -> datetime:
    return datetime.combine(tag, datetime.min.time()).replace(hour=stunde, minute=minute)


def _aufraeumen(s) -> None:
    benutzer = s.query(Benutzer).filter(Benutzer.name.like(f"{PRAEFIX} %")).all()
    ids = [b.id for b in benutzer]
    if ids:
        s.query(AdProfil).filter(AdProfil.benutzer_id.in_(ids)).delete(synchronize_session=False)
        s.query(BenutzerAbwesenheit).filter(BenutzerAbwesenheit.benutzer_id.in_(ids)).delete(synchronize_session=False)
        s.query(OutlookBelegt).filter(OutlookBelegt.benutzer_id.in_(ids)).delete(synchronize_session=False)
        s.query(BenutzerEinstellung).filter(BenutzerEinstellung.benutzer_id.in_(ids)).delete(synchronize_session=False)
        s.query(TeamMitglied).filter(TeamMitglied.benutzer_id.in_(ids)).delete(synchronize_session=False)
        s.query(TerminBesetzung).filter(TerminBesetzung.benutzer_id.in_(ids)).delete(synchronize_session=False)
        s.query(Benachrichtigung).filter(Benachrichtigung.benutzer_id.in_(ids)).delete(synchronize_session=False)
        s.query(VotTermin).filter(VotTermin.ad_id.in_(ids)).delete(synchronize_session=False)
    for team in s.query(Team).filter(Team.name.like(f"{PRAEFIX} %")):
        s.query(TeamMitglied).filter(TeamMitglied.team_id == team.id).delete(synchronize_session=False)
        s.delete(team)
    for projekt in s.query(Projekt).filter(Projekt.nummer.like(f"{PRAEFIX}-%")):
        termin_ids = [t.id for t in s.query(ProjektTermin).filter(ProjektTermin.projekt_id == projekt.id)]
        if termin_ids:
            s.query(TerminBesetzung).filter(TerminBesetzung.termin_id.in_(termin_ids)).delete(synchronize_session=False)
        s.query(ProjektTermin).filter(ProjektTermin.projekt_id == projekt.id).delete(synchronize_session=False)
        s.query(ProjektVerlauf).filter(ProjektVerlauf.projekt_id == projekt.id).delete(synchronize_session=False)
        s.query(Gewerk).filter(Gewerk.projekt_id == projekt.id).delete(synchronize_session=False)
        s.delete(projekt)
    for kunde in s.query(Kunde).filter(Kunde.nachname.like(f"{PRAEFIX}%")):
        for v in s.query(Vorgang).filter(Vorgang.kunde_id == kunde.id):
            termin_ids = [t.id for t in s.query(ProjektTermin).filter(ProjektTermin.vorgang_id == v.id)]
            if termin_ids:
                s.query(TerminBesetzung).filter(TerminBesetzung.termin_id.in_(termin_ids)).delete(synchronize_session=False)
            s.query(ProjektTermin).filter(ProjektTermin.vorgang_id == v.id).delete(synchronize_session=False)
            s.query(VotTermin).filter(VotTermin.vorgang_id == v.id).delete(synchronize_session=False)
            s.query(LeadAktivitaet).filter(LeadAktivitaet.vorgang_id == v.id).delete(synchronize_session=False)
            s.query(KommunikationLog).filter(KommunikationLog.vorgang_id == v.id).delete(synchronize_session=False)
            s.query(VorgangsNotiz).filter(VorgangsNotiz.vorgang_id == v.id).delete(synchronize_session=False)
            s.query(VorgangObjekt).filter(VorgangObjekt.vorgang_id == v.id).delete(synchronize_session=False)
            s.delete(v)
        s.delete(kunde)
    for b in benutzer:
        s.delete(b)
    s.commit()


class Basis(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        init_db()
        cls.s = SessionLocal()
        _aufraeumen(cls.s)
        s = cls.s
        cls.montag = _naechster_montag()
        cls.terminierung_vorher = lead_kern.parameter_holen(s, "terminierung_aktiv", "aus")
        lead_kern.parameter_setzen(s, "terminierung_aktiv", "an")

        def benutzer(name, rolle, **felder):
            b = Benutzer(name=f"{PRAEFIX} {name}", rolle=rolle, aktiv=True,
                         pin_hash=auth.pin_hash("4321"),
                         email=f"{name.lower().replace(' ', '')}@v33k.local", **felder)
            s.add(b)
            s.flush()
            return b

        cls.ad = benutzer("AD", "aussendienst")
        cls.hv = benutzer("HV", "handelsvertreter")
        cls.pj = benutzer("PJ", "projektierung")
        cls.mh = benutzer("MH", "montage_heizung")
        cls.mh2 = benutzer("MH2", "montage")                 # Basisrolle ohne Gewerk → Heizung [ANNAHME]
        cls.me = benutzer("ME", "montage_elektro")
        cls.sh = benutzer("SH", "service_heizung")
        cls.id_ = benutzer("ID", "innendienst")
        cls.lm = benutzer("LM", "leadmanagement")
        cls.fremd = benutzer("Fremd", "montage_heizung")   # Monteur ohne Team-Bezug zu MH
        s.add(AdProfil(benutzer_id=cls.hv.id, terminiert_selbst=True))
        cls.team = Team(name=f"{PRAEFIX} Team", typ="montage", aktiv=True, gewerk="heizung")
        s.add(cls.team)
        s.flush()
        s.add_all([TeamMitglied(team_id=cls.team.id, benutzer_id=cls.mh.id),
                   TeamMitglied(team_id=cls.team.id, benutzer_id=cls.mh2.id)])
        # Kunde, Vorgang (Lead), VOT + Telefon + Sperrzeit
        cls.kunde = Kunde(anrede="Herr", vorname="Kalle", nachname=f"{PRAEFIX}-Kunde",
                          strasse="Testweg 7", plz="47139", ort="Duisburg", telefon="0203 5551234",
                          email="kalle@v33k.local", interesse="WP")
        s.add(cls.kunde)
        s.flush()
        cls.vorgang = Vorgang(kunde_id=cls.kunde.id, lead_phase="terminiert", ad_id=cls.ad.id)
        s.add(cls.vorgang)
        s.flush()
        mo = cls.montag
        cls.vot = VotTermin(vorgang_id=cls.vorgang.id, ad_id=cls.ad.id, beginn=_dt(mo, 9),
                            ende=_dt(mo, 10, 30), status="geplant", typ="vot", quelle="manuell",
                            adresse="Testweg 7, 47139 Duisburg")
        cls.telefon = VotTermin(vorgang_id=cls.vorgang.id, ad_id=cls.ad.id, beginn=_dt(mo + timedelta(days=2), 15),
                                ende=_dt(mo + timedelta(days=2), 15, 30), status="geplant", typ="telefon",
                                medium="telefon", quelle="manuell")
        cls.sperrzeit = VotTermin(vorgang_id=0, ad_id=cls.hv.id, beginn=_dt(mo + timedelta(days=1), 8),
                                  ende=_dt(mo + timedelta(days=1), 12), status="geplant", typ="sperrzeit",
                                  quelle="manuell", grund_text="Messe")
        cls.monday = VotTermin(vorgang_id=cls.vorgang.id, ad_id=cls.ad.id, beginn=_dt(mo + timedelta(days=3), 9),
                               ende=_dt(mo + timedelta(days=3), 10, 30), status="geplant", typ="vot",
                               quelle="monday")
        # Nachtrag 15.10.2026 (K-R3): erfolgte Termine bleiben als Rueckschau sichtbar, abgesagte nicht
        cls.erledigt = VotTermin(vorgang_id=cls.vorgang.id, ad_id=cls.ad.id, beginn=_dt(mo + timedelta(days=4), 9),
                                 ende=_dt(mo + timedelta(days=4), 10), status="erfolgt", typ="vot",
                                 quelle="manuell")
        cls.abgesagt = VotTermin(vorgang_id=cls.vorgang.id, ad_id=cls.ad.id, beginn=_dt(mo + timedelta(days=4), 11),
                                 ende=_dt(mo + timedelta(days=4), 12), status="abgesagt", typ="vot",
                                 quelle="manuell")
        s.add_all([cls.vot, cls.telefon, cls.sperrzeit, cls.monday, cls.erledigt, cls.abgesagt])
        # Projekt mit Gewerk und allen Terminarten
        cls.projekt = Projekt(nummer=f"{PRAEFIX}-1", kunde_id=cls.kunde.id, vorgang_id=cls.vorgang.id,
                              ausfuehrung_strasse="Testweg 7", ausfuehrung_plz="47139",
                              ausfuehrung_ort="Duisburg")
        s.add(cls.projekt)
        s.flush()
        cls.gewerk = Gewerk(projekt_id=cls.projekt.id, sparte="WP", phase="planung")
        s.add(cls.gewerk)
        s.flush()

        def pt(typ, beginn, ende=None, **felder):
            t = ProjektTermin(projekt_id=cls.projekt.id, gewerk_id=cls.gewerk.id, typ=typ,
                              beginn=beginn, ende=ende, **felder)
            s.add(t)
            s.flush()
            return t

        cls.montage = pt("montage", _dt(mo, 0), _dt(mo + timedelta(days=2), 0), zweck="wp",
                         team_id=cls.team.id, ganztaegig=True, kunde_bestaetigt=True)
        cls.elektro = pt("montage", _dt(mo + timedelta(days=3), 0), _dt(mo + timedelta(days=3), 0),
                         zweck="elektro", team_id=cls.team.id, ganztaegig=True)
        cls.sub = pt("sub", _dt(mo + timedelta(days=4), 0), _dt(mo + timedelta(days=4), 0),
                     zweck="sub", team_id=cls.team.id, ganztaegig=True)
        cls.feinplanung = pt("feinplanung", _dt(mo + timedelta(days=1), 10), None,
                             person_id=cls.pj.id, ganztaegig=False)
        cls.abnahme = pt("abnahme", _dt(mo + timedelta(days=4), 14), None, person_id=cls.pj.id,
                         ganztaegig=False)
        cls.sonstige = pt("sonstige", _dt(mo + timedelta(days=2), 11), None, person_id=cls.id_.id,
                          ganztaegig=False)
        cls.service = ProjektTermin(projekt_id=0, gewerk_id=None, vorgang_id=cls.vorgang.id, typ="service",
                                    beginn=_dt(mo + timedelta(days=1), 13), ende=_dt(mo + timedelta(days=1), 15),
                                    ganztaegig=False, service_gewerk="heizung", anlass="wartung",
                                    service_status="geplant")
        s.add(cls.service)
        s.flush()
        s.add_all([TerminBesetzung(termin_id=cls.montage.id, benutzer_id=cls.mh.id),
                   TerminBesetzung(termin_id=cls.montage.id, benutzer_id=cls.mh2.id),
                   TerminBesetzung(termin_id=cls.elektro.id, benutzer_id=cls.me.id),
                   TerminBesetzung(termin_id=cls.sub.id, benutzer_id=cls.mh.id),
                   TerminBesetzung(termin_id=cls.service.id, benutzer_id=cls.sh.id)])
        # Krankheit (AD, Di–Mi) und fremder Outlook-Eintrag (AD, Do 10–11)
        s.add(BenutzerAbwesenheit(benutzer_id=cls.ad.id, art="krankheit", von=mo + timedelta(days=1),
                                  bis=mo + timedelta(days=2), bemerkung="Grippe"))
        s.add(OutlookBelegt(benutzer_id=cls.ad.id, von=_dt(mo + timedelta(days=3), 10),
                            bis=_dt(mo + timedelta(days=3), 11), event_id="AAMkGeheimerBetreffXYZ"))
        s.commit()
        cls.admin = _client(1)
        cls.ids = [b.id for b in (cls.ad, cls.hv, cls.pj, cls.mh, cls.mh2, cls.me, cls.sh, cls.id_, cls.lm)]

    @classmethod
    def tearDownClass(cls):
        try:
            lead_kern.parameter_setzen(cls.s, "terminierung_aktiv", cls.terminierung_vorher)
            cls.s.commit()
            _aufraeumen(cls.s)
        finally:
            cls.s.close()

    def frisch(self) -> None:
        """Nach einem Schreibzugriff über den TestClient neu lesen: die Lesetransaktion der
        Test-Sitzung beenden (WAL-Schnappschuss) UND die Objekte der Identity-Map verwerfen
        (rollback ohne offene Transaktion ist ein No-op und verwirft nichts)."""
        self.s.rollback()
        self.s.expire_all()

    def woche_json(self, client=None, ids=None, von=None, bis=None):
        client = client or self.admin
        von = von or self.montag
        bis = bis or (von + timedelta(days=6))
        ids = ids if ids is not None else self.ids
        r = client.get(f"/kalender/daten.json?von={von.isoformat()}&bis={bis.isoformat()}"
                       f"&personen={','.join(str(i) for i in ids)}&ansicht=woche")
        self.assertEqual(r.status_code, 200, r.text[:300])
        return r.json()


class Vorbelegung(Basis):
    def test_einstieg_projektierung_lead_admin(self):
        k = _kontext(self.admin.get("/kalender?gruppe=projektierung").text)
        self.assertEqual(k["einstieg"], "projektierung")
        self.assertEqual(set(k["auswahl"]["gruppen"]),
                         {"projektierung", "montage_heizung", "montage_elektro", "service_heizung", "service_elektro"})
        k = _kontext(self.admin.get("/kalender?gruppe=vertrieb").text)
        self.assertEqual(set(k["auswahl"]["gruppen"]), {"aussendienst", "handelsvertreter"})
        k = _kontext(self.admin.get("/kalender").text)
        self.assertEqual(k["einstieg"], "alle")
        self.assertEqual(set(k["auswahl"]["gruppen"]), {g for g, _ in kz.GRUPPEN})
        # Projektierer und Leadmanager ohne Parameter: Einstieg aus der Basisrolle
        k = _kontext(_client(self.pj.id).get("/kalender").text)
        self.assertEqual(k["einstieg"], "projektierung")
        k = _kontext(_client(self.lm.id).get("/kalender").text)
        self.assertEqual(k["einstieg"], "vertrieb")
        self.assertFalse(k["nur_lesen"])

    def test_gruppen_zuordnung(self):
        katalog = {p["name"]: p["gruppe"] for p in kz.personen_katalog(self.s)}
        self.assertEqual(katalog[f"{PRAEFIX} AD"], "aussendienst")
        self.assertEqual(katalog[f"{PRAEFIX} HV"], "handelsvertreter")
        self.assertEqual(katalog[f"{PRAEFIX} PJ"], "projektierung")
        self.assertEqual(katalog[f"{PRAEFIX} MH"], "montage_heizung")
        self.assertEqual(katalog[f"{PRAEFIX} MH2"], "montage_heizung")   # [ANNAHME] ohne Gewerk
        self.assertEqual(katalog[f"{PRAEFIX} ME"], "montage_elektro")
        self.assertEqual(katalog[f"{PRAEFIX} SH"], "service_heizung")
        self.assertEqual(katalog[f"{PRAEFIX} ID"], "innendienst")
        self.assertEqual(katalog[f"{PRAEFIX} LM"], "innendienst")       # eigene Annahme (Rückfrage)
        seite = self.admin.get("/kalender").text
        for name in ("Außendienst", "Handelsvertreter", "Projektierung", "Montage Heizung", "Montage Elektro",
                     "Service Heizung", "Service Elektro", "Innendienst"):
            self.assertIn(name, seite)

    def test_gruppenfilter_suche_person_und_gemerkte_auswahl(self):
        c = _client(self.id_.id)
        r = c.post("/kalender/einstellung", json={"einstieg": "vertrieb", "gruppen": ["aussendienst"],
                                                  "wochenende": True, "ansicht": "tag"})
        self.assertEqual(r.status_code, 200, r.text)
        k = _kontext(c.get("/kalender?gruppe=vertrieb").text)
        self.assertEqual(k["auswahl"]["gruppen"], ["aussendienst"])
        self.assertTrue(k["auswahl"]["wochenende"])
        self.assertEqual(k["auswahl"]["ansicht"], "tag")
        self.assertTrue(k["auswahl"]["gemerkt"])
        # anderer Einstieg unberührt (Standard), Datum/Ansicht per URL übersteuerbar
        k = _kontext(c.get("/kalender?gruppe=projektierung&ansicht=monat&datum=2026-11-03").text)
        self.assertFalse(k["auswahl"]["gemerkt"])
        self.assertEqual(k["auswahl"]["ansicht"], "monat")
        self.assertEqual(k["auswahl"]["datum"], "2026-11-03")
        # Suche nach Name und Einzelperson (?person=) – Gruppe der Person wird ergänzt
        seite = c.get(f"/kalender?gruppe=projektierung&person={self.ad.id}&q=V33K").text
        k = _kontext(seite)
        self.assertEqual(k["auswahl"]["person"], self.ad.id)
        self.assertEqual(k["auswahl"]["q"], "V33K")
        self.assertIn("aussendienst", k["auswahl"]["gruppen"])
        self.assertIn('id="kz-nur-person"', seite)
        self.frisch()
        gespeichert = json.loads(self.s.query(BenutzerEinstellung)
                                 .filter(BenutzerEinstellung.benutzer_id == self.id_.id,
                                         BenutzerEinstellung.key == "kalender_gruppen").one().wert)
        self.assertEqual(gespeichert["vertrieb"]["gruppen"], ["aussendienst"])


class Eintraege(Basis):
    def test_alle_terminarten_abwesenheit_belegt(self):
        daten = self.woche_json()
        arten = {e["art"] for e in daten["eintraege"]}
        for art in ("vot", "telefon", "sperrzeit", "montage", "elektro", "sub", "feinplanung", "abnahme",
                    "sonstige", "service", "krankheit", "belegt"):
            self.assertIn(art, arten, art)
        je_key = {e["key"]: e for e in daten["eintraege"]}
        montage = je_key[f"projekt-{self.montage.id}"]
        self.assertEqual(sorted(montage["personen"]), sorted([self.mh.id, self.mh2.id]))   # beide Zeilen
        self.assertTrue(montage["ganztaegig"])
        self.assertEqual(montage["kunde"], self.kunde.anzeige_name)
        self.assertIn("Duisburg", montage["ort"])
        self.assertTrue(montage["link"].startswith(f"/projektierung/projekt/{self.projekt.id}"))
        vot = je_key[f"vot-{self.vot.id}"]
        self.assertEqual(vot["personen"], [self.ad.id])
        self.assertEqual(vot["link"], f"/lead-management/lead/{self.vorgang.id}?tab=termin")
        self.assertEqual(vot["kunde"], self.kunde.anzeige_name)
        self.assertTrue(vot["verschiebbar"])
        self.assertFalse(je_key[f"vot-{self.monday.id}"]["verschiebbar"])   # monday-Termin gesperrt
        # Nachtrag 15.10.2026 (Entscheidung K-R3): erfolgte Termine bleiben als Rueckschau sichtbar (gedaempft)
        self.assertIn(f"vot-{self.erledigt.id}", je_key)
        self.assertIn("kz-erfolgt", je_key[f"vot-{self.erledigt.id}"]["farbe_klasse"])
        self.assertFalse(je_key[f"vot-{self.erledigt.id}"]["verschiebbar"])
        self.assertNotIn(f"vot-{self.abgesagt.id}", je_key)   # abgesagte Termine bleiben unsichtbar
        sperr = je_key[f"vot-{self.sperrzeit.id}"]
        self.assertEqual(sperr["personen"], [self.hv.id])
        self.assertFalse(sperr["verschiebbar"])
        service = je_key[f"service-{self.service.id}"]
        self.assertEqual(service["quelle"], "service")
        self.assertEqual(service["personen"], [self.sh.id])
        self.assertIn("Wartung", service["text"])
        self.assertTrue(service["link"].startswith(f"/vorgaenge/{self.vorgang.id}"))
        krank = [e for e in daten["eintraege"] if e["quelle"] == "abwesenheit"]
        self.assertEqual(len(krank), 1)
        self.assertEqual(krank[0]["personen"], [self.ad.id])
        self.assertTrue(krank[0]["ganztaegig"])
        self.assertEqual(krank[0]["farbe_klasse"], "kz-krankheit")
        belegt = [e for e in daten["eintraege"] if e["quelle"] == "belegt"]
        self.assertEqual(len(belegt), 1)
        self.assertEqual(belegt[0]["text"], "belegt")
        self.assertEqual((belegt[0]["kunde"], belegt[0]["ort"], belegt[0]["link"]), ("", "", ""))
        self.assertEqual(belegt[0]["beginn"], _dt(self.montag + timedelta(days=3), 10).strftime("%Y-%m-%dT%H:%M"))
        self.assertEqual(daten["raster"], {"von": 7 * 60, "bis": 18 * 60, "schritt": 15})
        self.assertEqual(len(daten["tage"]), 7)
        self.assertTrue(daten["tage"][5]["wochenende"])

    def test_kein_betreff_fremder_eintraege_und_feldsatz(self):
        r = self.admin.get(f"/kalender/daten.json?von={self.montag}&bis={self.montag + timedelta(days=6)}"
                           f"&personen={self.ad.id}")
        self.assertNotIn("Geheim", r.text)
        self.assertNotIn("AAMk", r.text)
        for e in r.json()["eintraege"]:
            self.assertTrue(set(e) <= ERLAUBTE_FELDER, set(e) - ERLAUBTE_FELDER)

    def test_tag_und_monat_zeitraum(self):
        daten = self.woche_json(von=self.montag, bis=self.montag)
        self.assertEqual(len(daten["tage"]), 1)
        keys = {e["key"] for e in daten["eintraege"]}
        self.assertIn(f"vot-{self.vot.id}", keys)
        self.assertIn(f"projekt-{self.montage.id}", keys)
        self.assertNotIn(f"vot-{self.telefon.id}", keys)
        erster = self.montag.replace(day=1)
        letzter = (erster.replace(month=erster.month % 12 + 1, day=1, year=erster.year + (erster.month == 12))
                   - timedelta(days=1))
        daten = self.woche_json(von=erster, bis=letzter)
        self.assertEqual(len(daten["tage"]), (letzter - erster).days + 1)


class Verschieben(Basis):
    def test_drag_vot_umbuchung_protokolliert(self):
        ziel = _dt(self.montag + timedelta(days=4), 14)
        r = self.admin.post("/kalender/verschieben", json={"quelle": "vot", "id": self.vot.id,
                                                            "beginn": ziel.strftime("%Y-%m-%dT%H:%M"),
                                                            "person_id": self.ad.id})
        self.assertEqual(r.status_code, 200, r.text)
        antwort = r.json()
        self.assertTrue(antwort["ok"], antwort)
        self.frisch()
        alt = self.s.get(VotTermin, self.vot.id)
        self.assertEqual(alt.status, "verschoben")
        neu = self.s.get(VotTermin, antwort["neu_id"])
        self.assertEqual((neu.beginn, neu.ad_id, neu.status), (ziel, self.ad.id, "geplant"))
        texte = [a.text for a in self.s.query(LeadAktivitaet).filter(LeadAktivitaet.vorgang_id == self.vorgang.id)]
        self.assertTrue(any("im Mitarbeiter-Kalender verschoben" in t for t in texte), texte)
        self.assertTrue(any("umgebucht" in t for t in texte), texte)
        # neuer Termin steht im JSON, der alte nicht mehr
        keys = {e["key"] for e in self.woche_json()["eintraege"]}
        self.assertIn(f"vot-{neu.id}", keys)
        self.assertNotIn(f"vot-{self.vot.id}", keys)
        # Sperrzeit und monday-Termin bleiben gesperrt
        r = self.admin.post("/kalender/verschieben", json={"quelle": "vot", "id": self.sperrzeit.id,
                                                            "beginn": ziel.strftime("%Y-%m-%dT%H:%M")})
        self.assertFalse(r.json()["ok"])
        r = self.admin.post("/kalender/verschieben", json={"quelle": "vot", "id": self.monday.id,
                                                            "beginn": ziel.strftime("%Y-%m-%dT%H:%M")})
        self.assertIn("monday", r.json()["meldung"])

    def test_drag_vorab_gespraech(self):
        ziel = _dt(self.montag + timedelta(days=4), 16)
        r = self.admin.post("/kalender/verschieben", json={"quelle": "vot", "id": self.telefon.id,
                                                            "beginn": ziel.strftime("%Y-%m-%dT%H:%M")})
        self.assertTrue(r.json()["ok"], r.text)
        self.frisch()
        t = self.s.get(VotTermin, self.telefon.id)
        self.assertEqual((t.beginn, t.ende), (ziel, ziel + timedelta(minutes=30)))

    def test_drag_projekt_termin_protokolliert_und_konflikt(self):
        ziel = _dt(self.montag + timedelta(days=2), 9, 30)
        r = self.admin.post("/kalender/verschieben", json={"quelle": "projekt", "id": self.feinplanung.id,
                                                            "beginn": ziel.strftime("%Y-%m-%dT%H:%M"),
                                                            "person_id": self.pj.id})
        self.assertEqual(r.status_code, 200, r.text)
        self.assertTrue(r.json()["ok"], r.text)
        self.frisch()
        self.assertEqual(self.s.get(ProjektTermin, self.feinplanung.id).beginn, ziel)
        texte = [v.text for v in self.s.query(ProjektVerlauf).filter(ProjektVerlauf.projekt_id == self.projekt.id)]
        self.assertTrue(any("verschoben" in t for t in texte), texte)
        # Montage (MH + MH2, ganztägig) auf den Sub-Tag von MH → Personenkonflikt → Bestätigung nötig
        sub_tag = self.sub.beginn
        r = self.admin.post("/kalender/verschieben", json={"quelle": "projekt", "id": self.montage.id,
                                                            "beginn": sub_tag.strftime("%Y-%m-%dT%H:%M"),
                                                            "person_id": self.mh.id})
        self.assertEqual(r.status_code, 200, r.text)
        antwort = r.json()
        self.assertFalse(antwort["ok"])
        self.assertTrue(antwort.get("bestaetigung_noetig"), antwort)
        self.assertTrue(any(f"{PRAEFIX} MH" in k for k in antwort["konflikte"]), antwort["konflikte"])
        self.frisch()
        self.assertEqual(self.s.get(ProjektTermin, self.montage.id).beginn, _dt(self.montag, 0))   # unverändert
        r = self.admin.post("/kalender/verschieben", json={"quelle": "projekt", "id": self.montage.id,
                                                            "beginn": sub_tag.strftime("%Y-%m-%dT%H:%M"),
                                                            "person_id": self.mh.id, "bestaetigt": True})
        self.assertTrue(r.json()["ok"], r.text)
        self.frisch()
        t = self.s.get(ProjektTermin, self.montage.id)
        self.assertEqual(t.beginn, sub_tag)
        self.assertEqual(t.ende, sub_tag + timedelta(days=2))      # Dauer bleibt
        self.assertTrue(t.ganztaegig)
        # Zeile einer anderen Person: Besetzung ändert der Kalender nicht
        r = self.admin.post("/kalender/verschieben", json={"quelle": "projekt", "id": self.montage.id,
                                                            "beginn": sub_tag.strftime("%Y-%m-%dT%H:%M"),
                                                            "person_id": self.me.id})
        self.assertFalse(r.json()["ok"])
        self.assertIn("Projektakte", r.json()["meldung"])
        # Abwesenheit/Belegt nie verschiebbar
        r = self.admin.post("/kalender/verschieben", json={"quelle": "belegt", "id": 1, "beginn": "2026-10-19T08:00"})
        self.assertFalse(r.json()["ok"])


class Rechte(Basis):
    def test_montage_nur_eigene_und_team_read_only(self):
        c = _client(self.mh.id)
        seite = c.get("/kalender")
        self.assertEqual(seite.status_code, 200)
        k = _kontext(seite.text)
        self.assertTrue(k["nur_lesen"])
        self.assertEqual({p["id"] for p in k["personen"]}, {self.mh.id, self.mh2.id})
        self.assertIn("nur lesend", seite.text)
        # Fremde Personen werden aus der Anfrage gefiltert
        daten = self.woche_json(client=c, ids=[self.mh.id, self.ad.id, self.fremd.id])
        self.assertEqual(daten["personen"], [self.mh.id])
        self.assertTrue(all(e["personen"] == [self.mh.id] or self.mh.id in e["personen"] for e in daten["eintraege"]))
        self.assertTrue(all(not e["verschiebbar"] for e in daten["eintraege"]))
        self.assertTrue(daten["nur_lesen"])
        # Verschieben verweigert
        r = c.post("/kalender/verschieben", json={"quelle": "projekt", "id": self.sub.id,
                                                   "beginn": _dt(self.montag, 8).strftime("%Y-%m-%dT%H:%M")})
        self.assertEqual(r.status_code, 403)
        self.assertEqual(self.admin.get(f"/kalender/suche.json?q=V33K&art=projekt").status_code, 200)
        self.assertEqual(c.get("/kalender/suche.json?q=V33K&art=projekt").json()["treffer"], [])
        # v33 (K-Rückfrage R4, umgesetzt von Agent R in auth.py): Außendienst erreicht die Seite
        # (Einstieg Vertrieb), darf aber Projekt-Termine nicht verschieben
        ad = _client(self.ad.id)
        seite = ad.get("/kalender")
        self.assertEqual(seite.status_code, 200)
        self.assertFalse(_kontext(seite.text)["nur_lesen"])
        r = ad.post("/kalender/verschieben", json={"quelle": "projekt", "id": self.sub.id,
                                                    "beginn": _dt(self.montag, 8).strftime("%Y-%m-%dT%H:%M")})
        self.assertEqual(r.status_code, 403)

    def test_projektierung_sieht_keine_lead_rechte(self):
        daten = self.woche_json(client=_client(self.pj.id))
        self.assertTrue(daten["rechte"]["projekt"])
        self.assertFalse(daten["rechte"]["lead"])
        vot = [e for e in daten["eintraege"] if e["art"] == "vot"]
        self.assertTrue(vot and all(not e["verschiebbar"] for e in vot))
        r = _client(self.pj.id).post("/kalender/verschieben", json={"quelle": "vot", "id": self.monday.id,
                                                                     "beginn": "2026-10-19T08:00"})
        self.assertFalse(r.json()["ok"])


class Einbindung(Basis):
    def test_menue_icon_leiste_team_kalender(self):
        self.assertIn('href="/kalender"', self.admin.get("/").text)
        self.assertIn("/kalender?gruppe=projektierung", _client(self.pj.id).get("/projektierung").text)
        self.assertIn("/kalender?gruppe=vertrieb", _client(self.lm.id).get("/lead-management/dashboard").text)
        self.assertIn("/kalender?gruppe=vertrieb", self.admin.get("/lead-management/hauptboard").text)
        pk = self.admin.get("/projektierung/kalender")
        self.assertEqual(pk.status_code, 200)
        self.assertIn("Mitarbeiter-Kalender", pk.text)
        self.assertIn("/kalender?gruppe=projektierung", pk.text)
        seite = self.admin.get("/kalender?gruppe=projektierung").text
        self.assertIn("zurueck-leiste", seite)                       # Zurück-Leiste aus base.html
        self.assertIn("kalender_zentral.js", seite)
        self.assertIn("kalender_zentral.css", seite)
        self.assertNotIn("tojson", seite)

    def test_v12_terminkalender_leitet_um(self):
        """[ANNAHME] GET /lead-management/kalender → /kalender?gruppe=vertrieb&person=<id>. Der
        V2-Router (lm_termin) bedient denselben Pfad zuerst – die Funktion wird direkt geprüft."""
        from app.routers import leadmanagement as v1
        anfrage = Request({"type": "http", "method": "GET", "path": "/lead-management/kalender",
                           "query_string": f"ad_id={self.ad.id}&woche=1".encode(), "headers": [],
                           "scheme": "http", "server": ("testserver", 80), "root_path": ""})
        anfrage.state.benutzer = self.s.get(Benutzer, 1)
        antwort = v1.terminkalender(anfrage, self.s)
        self.assertEqual(antwort.status_code, 303)
        ziel = antwort.headers["location"]
        self.assertTrue(ziel.startswith("/kalender?gruppe=vertrieb"), ziel)
        self.assertIn(f"person={self.ad.id}", ziel)
        erwartet = (datetime.now() + timedelta(weeks=1)).strftime("%Y-%m-%d")
        self.assertIn(f"datum={erwartet}", ziel)

    def test_v12_terminkalender_route_leitet_um(self):
        """Orchestrator (K 4.1): die echte Route /lead-management/kalender (V2-Router lm_termin)
        leitet um; ?alt=1 und ?meldung= zeigen weiter die alte Wochenansicht."""
        r = self.admin.get(f"/lead-management/kalender?ad_id={self.ad.id}&woche=1", follow_redirects=False)
        self.assertEqual(r.status_code, 303)
        ziel = r.headers["location"]
        self.assertTrue(ziel.startswith("/kalender?gruppe=vertrieb&ansicht=woche&datum="), ziel)
        self.assertIn(f"person={self.ad.id}", ziel)
        self.assertEqual(self.admin.get("/lead-management/kalender?alt=1", follow_redirects=False).status_code, 200)
        self.assertEqual(self.admin.get("/lead-management/kalender?meldung=Termin+abgesagt",
                                        follow_redirects=False).status_code, 200)
        # die Lead-Seiten verlinken den zentralen Kalender
        self.assertIn('href="/kalender?gruppe=vertrieb"', self.admin.get("/lead-management/dashboard").text)

    def test_doppelklick_suche(self):
        beginn = _dt(self.montag, 9).strftime("%Y-%m-%dT%H:%M")
        r = self.admin.get(f"/kalender/suche.json?q={PRAEFIX}-Kunde&art=lead&person={self.ad.id}&beginn={beginn}")
        treffer = r.json()["treffer"]
        self.assertTrue(treffer)
        self.assertTrue(treffer[0]["link"].startswith(f"/lead-management/lead/{self.vorgang.id}/termin?ad_id={self.ad.id}"))
        r = self.admin.get(f"/kalender/suche.json?q={PRAEFIX}-1&art=projekt&person={self.mh.id}&beginn={beginn}")
        treffer = r.json()["treffer"]
        self.assertTrue(treffer)
        self.assertIn(f"/projektierung/projekt/{self.projekt.id}?termin_neu=1", treffer[0]["link"])
        self.assertIn(f"person={self.mh.id}", treffer[0]["link"])
        r = self.admin.get(f"/kalender/suche.json?q={PRAEFIX}-Kunde&art=vorgang&person={self.sh.id}&beginn={beginn}")
        self.assertIn(f"/vorgaenge/{self.vorgang.id}?termin_neu=service", r.json()["treffer"][0]["link"])
        self.assertEqual(kz.neu_art("aussendienst"), "lead")
        self.assertEqual(kz.neu_art("service_elektro"), "vorgang")
        self.assertEqual(kz.neu_art("montage_heizung"), "projekt")

    def test_seite_in_beiden_modi(self):
        for modus in ("hell", "dunkel"):
            c = TestClient(app, follow_redirects=False)
            c.cookies.set(auth.COOKIE_NAME, auth.cookie_wert(self.id_.id))
            c.cookies.set("darstellung", modus)
            r = c.get("/kalender?gruppe=vertrieb")
            self.assertEqual(r.status_code, 200)
            self.assertIn(f'data-theme="{modus}"', r.text)
        css = open("app/static/kalender_zentral.css", encoding="utf-8").read()
        self.assertNotIn("#", css.replace("#kz", ""))      # keine Hex-Farben, nur Tokens


class Leistung(Basis):
    """JSON-Zeit für 60 Personen × 1 Woche – großzügige Grenze im Test, der Messwert geht in
    den Bericht (Ziel laut Plan < 1,5 s auf der DB-Kopie)."""
    ANZAHL = 60
    GRENZE_SEKUNDEN = 3.0

    def test_json_zeit_60_personen(self):
        s = self.s
        personen = []
        for n in range(self.ANZAHL):
            b = Benutzer(name=f"{PRAEFIX} Last {n:02d}", rolle="aussendienst", aktiv=True,
                         pin_hash=auth.pin_hash("4321"), email=f"last{n}@v33k.local")
            s.add(b)
            personen.append(b)
        s.flush()
        for i, b in enumerate(personen):
            for tag in range(5):
                s.add(VotTermin(vorgang_id=self.vorgang.id, ad_id=b.id,
                                beginn=_dt(self.montag + timedelta(days=tag), 8 + (i % 3) * 3),
                                ende=_dt(self.montag + timedelta(days=tag), 9 + (i % 3) * 3, 30),
                                status="geplant", typ="vot", quelle="manuell"))
            s.add(OutlookBelegt(benutzer_id=b.id, von=_dt(self.montag + timedelta(days=i % 5), 13),
                                bis=_dt(self.montag + timedelta(days=i % 5), 14), event_id=f"x{i}"))
            if i % 6 == 0:
                s.add(BenutzerAbwesenheit(benutzer_id=b.id, art="urlaub", von=self.montag + timedelta(days=3),
                                          bis=self.montag + timedelta(days=4)))
        s.commit()
        ids = [b.id for b in personen]
        zeiten = []
        for _ in range(3):
            start = time.perf_counter()
            daten = self.woche_json(ids=ids)
            zeiten.append(time.perf_counter() - start)
        self.assertEqual(len(daten["personen"]), self.ANZAHL)
        self.assertGreaterEqual(len(daten["eintraege"]), self.ANZAHL * 5 + self.ANZAHL)
        print(f"\n[K] daten.json 60 Personen × 1 Woche: {len(daten['eintraege'])} Einträge, "
              f"min {min(zeiten):.3f} s, median {statistics.median(zeiten):.3f} s, "
              f"intern {daten['dauer_ms']} ms")
        self.assertLess(min(zeiten), self.GRENZE_SEKUNDEN)


if __name__ == "__main__":
    unittest.main()
