# v38 (PLAN_V23 Phase 202 + Phase 204 „Erfassungsliste mobil mit Objekt“, Agent E):
# Erfassung zwischenspeichern (Entwurf nach Abbruch sichtbar und an der richtigen Frage
# fortsetzbar, „Später fortsetzen“, beforeunload-Markup), Korrektur nach „Senden“ (Rechte:
# Außendienst nur eigene → fremde 403, Innendienst/Admin alle; Sperre bei „Versand vorbereitet“
# auch über Versionen; Notizen-Chat-Eintrag mit altem und neuem Wert; Badge „nachträglich
# geändert“; Hinweis „Angebot neu berechnen“ bei Angebotsentwurf; Freitext-Editor schreibt
# denselben Eintrag) und die Objektzeile der Erfassungslisten (Plan-Kontrollwert „Halle Nord“/
# „Verwaltung“). Läuft gegen die DB-Kopie (DB_PFAD_OVERRIDE), Fixtures mit Präfix V38E.
import json
import re
import unittest
from datetime import date, datetime, timedelta

from fastapi.testclient import TestClient

from app import auth, erfassung_korrektur, lead_boards, objekte
from app import logik as logik_modul
from app.db import SessionLocal
from app.logik import logik_fuer_sparte
from app.main import app
from app.models import (Angebot, Benutzer, Erfassung, Kunde, Vorgang, VorgangNotizGelesen,
                        VorgangObjekt, VorgangsNotiz)

PRAEFIX = "V38E"


def _client(benutzer_id: int) -> TestClient:
    c = TestClient(app, follow_redirects=False)
    c.cookies.set(auth.COOKIE_NAME, auth.cookie_wert(benutzer_id))
    return c


def _wp_logik(session):
    logik, bericht = logik_modul.hole_logik(session)
    assert bericht.ok, bericht
    return logik_fuer_sparte(logik, "WP")


def _option(logik, frage_id: str, wunsch: str) -> str:
    """Antwortoption einer Auswahlfrage – `wunsch`, wenn vorhanden, sonst die erste Option."""
    antworten = logik.fragen[frage_id].antworten
    return wunsch if wunsch in antworten else antworten[0]


def _seite_form(logik, nr: int, antworten: dict, richtung: str = "weiter") -> dict:
    """Formulardaten einer Bogenseite aus Frage-ID → Wert (f_<ID>)."""
    daten = {"richtung": richtung}
    for frage_id, wert in antworten.items():
        daten[f"f_{frage_id}"] = str(wert)
    return daten


class Basis(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        s = SessionLocal()
        try:
            cls._aufraeumen(s)

            def benutzer(name, rolle):
                b = Benutzer(name=f"{PRAEFIX} {name}", rolle=rolle, aktiv=True,
                             email=f"{name.lower()}@v38e.local", pin_hash=auth.pin_hash("4321"))
                s.add(b)
                s.flush()
                return b.id

            cls.ad_id = benutzer("Vertrieb", "aussendienst")
            cls.fremd_id = benutzer("Fremd", "aussendienst")
            cls.innen_id = benutzer("Innen", "innendienst")
            # Kunde mit einem Objekt (Hauptobjekt = Kundenadresse)
            kunde = Kunde(anrede="Herr", vorname="Emil", nachname=f"Entwurf{PRAEFIX}", strasse="Bogenweg 3",
                          plz="47051", ort="Duisburg", telefon="0203 123", interesse="WP", objektart="EFH")
            s.add(kunde)
            s.flush()
            cls.kunde_id = kunde.id
            vorgang = Vorgang(kunde_id=kunde.id, lead_phase="erfasst", ad_id=cls.ad_id)
            s.add(vorgang)
            s.flush()
            cls.vorgang_id = vorgang.id
            haupt = objekte.hauptobjekt(s, vorgang.id, anlegen=True, kunde=kunde)
            cls.haupt_id = haupt.id
            # Großkunde mit zwei Objekten „Verwaltung“ (Hauptobjekt) und „Halle Nord“
            gross = Kunde(anrede="Firma", firma=f"Werk {PRAEFIX} GmbH", nachname=f"Gross{PRAEFIX}",
                          strasse="Zentralallee 1", plz="47059", ort="Duisburg", interesse="WP,PV",
                          grosskunde=True)
            s.add(gross)
            s.flush()
            cls.gross_id = gross.id
            v2 = Vorgang(kunde_id=gross.id, lead_phase="erfasst", ad_id=cls.ad_id)
            s.add(v2)
            s.flush()
            cls.vorgang2_id = v2.id
            verwaltung = objekte.hauptobjekt(s, v2.id, anlegen=True, kunde=gross)
            verwaltung.bezeichnung = "Verwaltung"
            halle = objekte.objekt_anlegen(s, v2, strasse="Nordring 12", plz="47167", ort="Duisburg",
                                           bezeichnung="Halle Nord", interessen=["WP"])
            cls.verwaltung_id, cls.halle_id = verwaltung.id, halle.id
            logik = _wp_logik(s)
            cls.seiten = logik.seiten
            cls.alte_anlage_nr = logik.seiten.index("Alte Anlage")
            # vollständige Antworten der Seiten Objektdaten + Alte Anlage (KG, Gas) für Korrektur-Tests
            cls.basis_antworten = {
                "O01": "EFH", "O02": 1992.0, "O04": "Nein", "O05": 150.0, "O06": "Ja", "O13": "", "O08": "",
                "A01": "Gas", "A02": 2001.0, "A03": 22000.0, "A14": "Nein", "A04": "KG", "A05": 12.0,
                "A13": 8.0, "A10": _option(logik, "A10", "Nein"), "A11": _option(logik, "A11", "Nein"),
                "A12": "",
            }

            def erfassung(status, benutzer_id, vorgang, objekt_id, **felder):
                werte = dict(kunde_id=vorgang.kunde_id, benutzer_id=benutzer_id, vorgang_id=vorgang.id,
                             objekt_id=objekt_id, status=status, sparte="WP", konfigurator_typ="WP",
                             antworten_json=json.dumps(cls.basis_antworten), typ="katalog",
                             abgesendet_am=None if status == "Entwurf" else datetime.now())
                werte.update(felder)
                e = Erfassung(**werte)
                s.add(e)
                s.flush()
                return e

            # abgesendete Erfassung des AD ohne Angebot (korrigierbar)
            cls.gesendet_id = erfassung("Neu", cls.ad_id, vorgang, haupt.id).id
            # abgesendet mit Angebot „Versand vorbereitet“ → gesperrt
            e2 = erfassung("In Bearbeitung", cls.ad_id, vorgang, haupt.id)
            a2 = Angebot(nummer=f"AN-{PRAEFIX}-0002", kunde_id=kunde.id, vorgang_id=vorgang.id,
                         vertriebler_id=cls.ad_id, status="Versand vorbereitet", datum=datetime.now(),
                         konfiguration_id=e2.id)
            s.add(a2)
            s.flush()
            e2.angebot_id = a2.id
            cls.gesperrt_id = e2.id
            # abgesendet mit Versionskette: alte Version „Versendet“, neue Version Entwurf → gesperrt
            e3 = erfassung("In Bearbeitung", cls.ad_id, vorgang, haupt.id)
            a_alt = Angebot(nummer=f"AN-{PRAEFIX}-0003", kunde_id=kunde.id, vorgang_id=vorgang.id,
                            vertriebler_id=cls.ad_id, status="Überholt", datum=datetime.now())
            s.add(a_alt)
            s.flush()
            a_neu = Angebot(nummer=f"AN-{PRAEFIX}-0003.2", kunde_id=kunde.id, vorgang_id=vorgang.id,
                            vertriebler_id=cls.ad_id, status="Entwurf", datum=datetime.now(),
                            vorgaenger_id=a_alt.id)
            s.add(a_neu)
            s.flush()
            e3.angebot_id = a_neu.id
            cls.version_id = e3.id
            # abgesendet mit Angebotsentwurf → Hinweis „Angebot neu berechnen“
            e4 = erfassung("In Bearbeitung", cls.ad_id, vorgang, haupt.id)
            a4 = Angebot(nummer=f"AN-{PRAEFIX}-0004", kunde_id=kunde.id, vorgang_id=vorgang.id,
                         vertriebler_id=cls.ad_id, status="Entwurf", datum=datetime.now())
            s.add(a4)
            s.flush()
            e4.angebot_id = a4.id
            cls.mit_entwurf_id, cls.angebot_entwurf_id = e4.id, a4.id
            # Freitext-Erfassung in der TAIFUN-Warteschlange (Editor v13)
            cls.freitext_id = erfassung("In TAIFUN zu schreiben", cls.ad_id, vorgang, haupt.id,
                                        typ="freitext", freitext="Alte Ölheizung im Keller, 1998.").id
            # Großkunde: je Objekt eine Erfassung (Kontrollwert Phase 204)
            cls.halle_erf_id = erfassung("Neu", cls.ad_id, v2, halle.id).id
            cls.verw_erf_id = erfassung("Neu", cls.ad_id, v2, verwaltung.id).id
            # Erfassung ohne Objektzuordnung → Kundenadresse „(Kunde)“
            cls.ohne_objekt_id = erfassung("Neu", cls.ad_id, v2, None).id
            # alter Entwurf (31 Tage) und frischer Entwurf (Warnfarbe)
            alt = erfassung("Entwurf", cls.ad_id, vorgang, haupt.id)
            alt.angelegt_am = datetime.now() - timedelta(days=31)
            alt.antworten_json = "{}"
            cls.alt_entwurf_id = alt.id
            frisch = erfassung("Entwurf", cls.ad_id, vorgang, haupt.id)
            frisch.antworten_json = "{}"
            cls.frisch_entwurf_id = frisch.id
            s.commit()
        finally:
            s.close()

    @classmethod
    def _aufraeumen(cls, s):
        benutzer_ids = [b.id for b in s.query(Benutzer).filter(Benutzer.name.like(f"{PRAEFIX} %"))]
        kunden = s.query(Kunde).filter((Kunde.nachname.like(f"%{PRAEFIX}")) | (Kunde.firma.like(f"%{PRAEFIX}%"))).all()
        for k in kunden:
            vorgang_ids = [v.id for v in s.query(Vorgang).filter(Vorgang.kunde_id == k.id)]
            if vorgang_ids:
                s.query(VorgangsNotiz).filter(VorgangsNotiz.vorgang_id.in_(vorgang_ids)).delete(synchronize_session=False)
                s.query(VorgangNotizGelesen).filter(VorgangNotizGelesen.vorgang_id.in_(vorgang_ids)).delete(synchronize_session=False)
                s.query(VorgangObjekt).filter(VorgangObjekt.vorgang_id.in_(vorgang_ids)).delete(synchronize_session=False)
            s.query(Erfassung).filter(Erfassung.kunde_id == k.id).delete(synchronize_session=False)
            s.query(Angebot).filter(Angebot.kunde_id == k.id).delete(synchronize_session=False)
            s.query(Vorgang).filter(Vorgang.kunde_id == k.id).delete(synchronize_session=False)
            s.delete(k)
        if benutzer_ids:
            s.query(Erfassung).filter(Erfassung.benutzer_id.in_(benutzer_ids)).delete(synchronize_session=False)
            s.query(Benutzer).filter(Benutzer.id.in_(benutzer_ids)).delete(synchronize_session=False)
        s.commit()

    @classmethod
    def tearDownClass(cls):
        s = SessionLocal()
        try:
            cls._aufraeumen(s)
        finally:
            s.close()

    def _erfassung(self, erfassung_id: int) -> Erfassung:
        s = SessionLocal()
        try:
            e = s.get(Erfassung, erfassung_id)
            s.expunge(e)
            return e
        finally:
            s.close()

    def _notizen(self, vorgang_id: int) -> list[VorgangsNotiz]:
        s = SessionLocal()
        try:
            liste = (s.query(VorgangsNotiz).filter(VorgangsNotiz.vorgang_id == vorgang_id)
                     .order_by(VorgangsNotiz.id).all())
            for n in liste:
                s.expunge(n)
            return liste
        finally:
            s.close()


class Zwischenspeichern(Basis):
    """Phase 202: Entwurf nach Abbruch, „Später fortsetzen“, Wiedereinstieg, beforeunload."""

    def _entwurf_starten(self, client) -> int:
        r = client.post("/erfassung/sparten-start", data={"kunde_id": str(self.kunde_id), "sparte_WP": "on"})
        self.assertEqual(r.status_code, 303, r.text[:200])
        self.assertRegex(r.headers["location"], r"^/erfassung/\d+/weiche$")
        return int(r.headers["location"].split("/")[2])

    def test_entwurf_nach_abbruch_sichtbar_und_fortsetzbar(self):
        ad = _client(self.ad_id)
        eid = self._entwurf_starten(ad)
        # fünf Fragen der ersten Seite, „Weiter“ → Seite 2; danach „Abbruch“ (keine weitere Anfrage)
        r = ad.post(f"/erfassung/{eid}/seite/0", data=_seite_form(
            None, 0, {"O01": "EFH", "O02": "1990", "O04": "Nein", "O05": "140", "O06": "Ja"}))
        self.assertEqual(r.status_code, 303, r.text[:300])
        self.assertEqual(r.headers["location"], f"/erfassung/{eid}/seite/1")
        e = self._erfassung(eid)
        antworten = json.loads(e.antworten_json)
        self.assertEqual(antworten["O01"], "EFH")
        self.assertEqual(antworten["O05"], 140)
        self.assertEqual(e.status, "Entwurf")
        self.assertEqual(e.aktuelle_frage, "A01")           # erste unbeantwortete Frage gemerkt
        # Liste des Außendienstes: Badge „Entwurf · Frage 8 von n“ (7 Fragen der ersten Seite sind belegt)
        html = ad.get("/erfassung").text
        badges = re.findall(rf'data-erfassung="{eid}".*?data-rolle="entwurf-badge"[^>]*>([^<]+)<', html, re.S)
        self.assertTrue(badges, html[:500])
        self.assertRegex(badges[0], r"^Entwurf · Frage 8 von \d+$")
        self.assertIn(f'href="/erfassung/{eid}/fortsetzen"', html)
        # Innendienst-Liste: Reiter „Entwürfe“ und „Alle“ zeigen den Entwurf mit Badge
        innen = _client(self.innen_id)
        liste = innen.get("/erfassungen?status=entwuerfe").text
        self.assertIn(f'data-zeile="{eid}"', liste)
        self.assertRegex(liste, r"Entwurf · Frage 8 von \d+")
        self.assertIn(f'data-zeile="{eid}"', innen.get("/erfassungen").text)
        self.assertNotIn(f'data-zeile="{eid}"', innen.get("/erfassungen?status=offen").text)
        # Wiedereinstieg: /fortsetzen springt auf die Seite der ersten offenen Frage mit Hinweis
        r = ad.get(f"/erfassung/{eid}/fortsetzen")
        self.assertEqual(r.status_code, 303)
        self.assertEqual(r.headers["location"], f"/erfassung/{eid}/seite/1?fortgesetzt=A01#frage-A01")
        seite = ad.get(f"/erfassung/{eid}/seite/1?fortgesetzt=A01").text
        self.assertRegex(seite, r'data-rolle="fortgesetzt">Fortgesetzt bei Frage 8 von \d+<')
        self.assertIn('id="frage-A01"', seite)
        self.assertIn("fragefeld fortgesetzt", seite)
        seite0 = ad.get(f"/erfassung/{eid}/seite/0").text                     # Antworten vorbelegt
        self.assertIn('name="f_O01"', seite0)
        self.assertRegex(seite0, r'value="EFH"\s+checked')

    def test_spaeter_fortsetzen(self):
        ad = _client(self.ad_id)
        eid = self._entwurf_starten(ad)
        # fünf Fragen beantwortet, „Später fortsetzen“ (ohne Pflichtprüfung, leere optionale Felder bleiben offen)
        r = ad.post(f"/erfassung/{eid}/seite/0", data=_seite_form(
            None, 0, {"O01": "EFH", "O02": "1990", "O04": "Nein", "O05": "140", "O06": "Ja"}, richtung="spaeter"))
        self.assertEqual(r.status_code, 303, r.text[:300])
        self.assertEqual(r.headers["location"],
                         "/erfassung?meldung=Erfassung+gespeichert.+Sie+k%C3%B6nnen+jederzeit+weitermachen.")
        e = self._erfassung(eid)
        antworten = json.loads(e.antworten_json)
        self.assertEqual(antworten["O01"], "EFH")
        self.assertNotIn("O13", antworten)                   # leere optionale Felder nicht als „beantwortet“
        self.assertEqual(e.status, "Entwurf")
        self.assertEqual(e.aktuelle_frage, "O13")
        html = ad.get(r.headers["location"]).text
        self.assertIn("Erfassung gespeichert. Sie können jederzeit weitermachen.", html)
        badges = re.findall(rf'data-erfassung="{eid}".*?data-rolle="entwurf-badge"[^>]*>([^<]+)<', html, re.S)
        self.assertRegex(badges[0], r"^Entwurf · Frage 6 von \d+$")   # Plan-Kontrollwert
        r = ad.get(f"/erfassung/{eid}/fortsetzen")
        self.assertEqual(r.headers["location"], f"/erfassung/{eid}/seite/0?fortgesetzt=O13#frage-O13")
        self.assertIn("Fortgesetzt bei Frage 6 von", ad.get(r.headers["location"].split("#")[0]).text)
        # unvollständige/ungültige Eingaben blockieren „Später fortsetzen“ nicht, werden aber nicht gespeichert
        r = ad.post(f"/erfassung/{eid}/seite/1", data={"richtung": "spaeter", "f_A01": "Gas", "f_A02": "abc"})
        self.assertEqual(r.status_code, 303)
        antworten = json.loads(self._erfassung(eid).antworten_json)
        self.assertEqual(antworten.get("A01"), "Gas")
        self.assertNotIn("A02", antworten)
        # Innendienst landet in der Erfassungsliste
        innen = _client(self.innen_id)
        r = innen.post(f"/erfassung/{eid}/seite/1", data={"richtung": "spaeter", "f_A02": "1999"})
        self.assertEqual(r.status_code, 303)
        self.assertTrue(r.headers["location"].startswith("/erfassungen?meldung="))

    def test_bogen_markup_spaeter_und_beforeunload(self):
        ad = _client(self.ad_id)
        html = ad.get(f"/erfassung/{self.frisch_entwurf_id}/seite/0").text
        self.assertIn('data-rolle="spaeter-fortsetzen"', html)
        self.assertRegex(html, r'form="seitenform"\s+name="richtung" value="spaeter" formnovalidate')
        self.assertIn("addEventListener('beforeunload'", html)
        self.assertIn("form.addEventListener('submit', function () { geaendert = false; })", html)
        self.assertNotIn('data-rolle="korrektur-leiste"', html)
        self.assertIn("In Freitext wechseln", html)
        # Prüfseite ohne Formularfelder → kein beforeunload
        pruefen = ad.get(f"/erfassung/{self.frisch_entwurf_id}/pruefen").text
        self.assertNotIn("beforeunload", pruefen)
        self.assertIn('data-rolle="fortsetzen-link"', pruefen)

    def test_entwurf_warnfarbe_ab_30_tagen(self):
        ad = _client(self.ad_id)
        html = ad.get("/erfassung").text
        alt = re.search(rf'<li class="([^"]*)" data-rolle="erfassung-eintrag" data-erfassung="{self.alt_entwurf_id}"', html)
        frisch = re.search(rf'<li class="([^"]*)" data-rolle="erfassung-eintrag" data-erfassung="{self.frisch_entwurf_id}"', html)
        self.assertIsNotNone(alt)
        self.assertIn("entwurf-alt", alt.group(1))
        self.assertNotIn("entwurf-alt", frisch.group(1))
        self.assertTrue(erfassung_korrektur.entwurf_alt(self._erfassung(self.alt_entwurf_id)))
        self.assertFalse(erfassung_korrektur.entwurf_alt(self._erfassung(self.frisch_entwurf_id)))
        # Innendienst: Entwurf-Detail ohne Angebotsknöpfe, Angebot erzeugen abgewiesen
        innen = _client(self.innen_id)
        detail = innen.get(f"/erfassungen/{self.alt_entwurf_id}").text
        self.assertIn('data-rolle="entwurf-hinweis"', detail)
        self.assertNotIn("angebot-erzeugen", detail)
        r = innen.get(f"/erfassungen/{self.alt_entwurf_id}/angebot-erzeugen")
        self.assertEqual(r.status_code, 303)
        self.assertIn("Entwurf", r.headers["location"])


class Korrektur(Basis):
    """Phase 202: Korrektur nach „Senden“ – Rechte, Sperre, Notiz, Badge, Angebots-Hinweis."""

    def _seite1(self, **aenderung) -> dict:
        s = SessionLocal()
        try:
            logik = _wp_logik(s)
        finally:
            s.close()
        werte = {k: v for k, v in self.basis_antworten.items()
                 if logik.fragen[k].seite == "Alte Anlage"}
        werte.update(aenderung)
        return _seite_form(logik, self.alte_anlage_nr, werte, richtung="korrektur")

    def test_rechte_ad_eigene_fremde_innendienst(self):
        ad, fremd, innen = _client(self.ad_id), _client(self.fremd_id), _client(self.innen_id)
        r = ad.get(f"/erfassung/{self.gesendet_id}/korrektur?frage=A04")
        self.assertEqual(r.status_code, 303)
        self.assertEqual(r.headers["location"], f"/erfassung/{self.gesendet_id}/seite/{self.alte_anlage_nr}#frage-A04")
        self.assertEqual(fremd.get(f"/erfassung/{self.gesendet_id}/korrektur").status_code, 403)
        self.assertEqual(fremd.post(f"/erfassung/{self.gesendet_id}/seite/{self.alte_anlage_nr}",
                                    data=self._seite1(A04="EG")).status_code, 403)
        self.assertEqual(innen.get(f"/erfassung/{self.gesendet_id}/korrektur").status_code, 303)
        self.assertEqual(_client(1).get(f"/erfassung/{self.gesendet_id}/korrektur").status_code, 303)
        # Knopf nur mit Recht sichtbar (Prüfseite, Innendienst-Detail, Vorgangsakte)
        self.assertIn('data-rolle="korrektur-knopf"', ad.get(f"/erfassung/{self.gesendet_id}/pruefen").text)
        self.assertIn('data-rolle="korrektur-knopf"', innen.get(f"/erfassungen/{self.gesendet_id}").text)
        akte = ad.get(f"/vorgaenge/{self.vorgang_id}").text
        self.assertIn(f'href="/erfassung/{self.gesendet_id}/korrektur"', akte)
        # fremde Erfassung: Prüfseite leitet um (kein Knopf), Detailseite ohne Knopf
        self.assertEqual(fremd.get(f"/erfassung/{self.gesendet_id}/pruefen").status_code, 303)
        self.assertNotIn('data-rolle="korrektur-knopf"', fremd.get(f"/erfassungen/{self.gesendet_id}").text)
        # Korrekturmodus-Markup: Leiste, „Korrektur speichern“, kein Freitext-Wechsel, kein „Später fortsetzen“
        seite = ad.get(f"/erfassung/{self.gesendet_id}/seite/{self.alte_anlage_nr}").text
        self.assertIn('data-rolle="korrektur-leiste"', seite)
        self.assertIn('data-rolle="korrektur-speichern"', seite)
        self.assertNotIn("In Freitext wechseln", seite)
        self.assertNotIn('data-rolle="spaeter-fortsetzen"', seite)
        aktuell = json.loads(self._erfassung(self.gesendet_id).antworten_json)["A04"]   # Antworten vorbelegt
        self.assertRegex(seite, rf'value="{aktuell}"\s+checked')

    def test_korrektur_speichern_notiz_badge_status(self):
        ad = _client(self.ad_id)
        vorher = len(self._notizen(self.vorgang_id))
        r = ad.post(f"/erfassung/{self.gesendet_id}/seite/{self.alte_anlage_nr}", data=self._seite1(A04="EG", A05="15"))
        self.assertEqual(r.status_code, 303, r.text[:300])
        self.assertTrue(r.headers["location"].startswith(f"/erfassung/{self.gesendet_id}/pruefen?meldung="))
        self.assertIn("Korrektur+gespeichert", r.headers["location"])
        e = self._erfassung(self.gesendet_id)
        self.assertEqual(e.status, "Neu")                                    # Status unverändert
        self.assertEqual(json.loads(e.antworten_json)["A04"], "EG")
        self.assertIsNotNone(e.geaendert_am)
        self.assertEqual(e.geaendert_von, self.ad_id)
        notizen = self._notizen(self.vorgang_id)
        self.assertEqual(len(notizen), vorher + 1)
        notiz = notizen[-1]
        self.assertEqual(notiz.benutzer_name, "System")
        self.assertEqual(notiz.herkunft, "Erfassung (Korrektur)")
        self.assertRegex(notiz.text, rf"^Erfassung nachträglich geändert von {PRAEFIX} Vertrieb am \d\d\.\d\d\.\d{{4}} \d\d:\d\d: ")
        self.assertIn("A04 Lage des Heizraums: KG → EG", notiz.text)
        self.assertIn("A05", notiz.text)
        self.assertIn("12 → 15", notiz.text)
        self.assertNotIn("Alle Änderungen:", notiz.text)                      # nur zwei Änderungen
        # Badge auf Prüfseite, in den Listen und in der Vorgangsakte
        badge = f"nachträglich geändert ({date.today().strftime('%d.%m.')})"
        self.assertIn(badge, ad.get(f"/erfassung/{self.gesendet_id}/pruefen").text)
        self.assertIn(badge, ad.get("/erfassung").text)
        self.assertIn(badge, _client(self.innen_id).get("/erfassungen").text)
        self.assertIn(badge, _client(self.innen_id).get(f"/erfassungen/{self.gesendet_id}").text)
        akte = ad.get(f"/vorgaenge/{self.vorgang_id}").text
        self.assertIn(badge, akte)
        self.assertIn("A04 Lage des Heizraums: KG → EG", akte)               # Notiz im Chat der Akte
        # Prüfseite nennt das Änderungsdatum im Tooltip und zeigt die geänderte Antwort
        self.assertIn("Zuletzt korrigiert am", ad.get(f"/erfassung/{self.gesendet_id}/pruefen").text)
        # Korrektur ohne Änderung erzeugt keinen zweiten Eintrag
        r = ad.post(f"/erfassung/{self.gesendet_id}/seite/{self.alte_anlage_nr}", data=self._seite1(A04="EG", A05="15"))
        self.assertIn("Keine+%C3%84nderung", r.headers["location"])
        self.assertEqual(len(self._notizen(self.vorgang_id)), vorher + 1)

    def test_notiz_text_kurz_und_aufklappbar(self):
        zeit = datetime(2026, 10, 16, 14, 5)
        liste = [{"id": f"X0{i}", "titel": f"Frage {i}", "alt": "a", "neu": "b"} for i in range(1, 9)]
        text = erfassung_korrektur.notiz_text("Max Muster", zeit, liste)
        self.assertTrue(text.startswith("Erfassung nachträglich geändert von Max Muster am 16.10.2026 14:05: X01 Frage 1: a → b; "))
        self.assertIn("X05 Frage 5: a → b … und 3 weitere", text)
        self.assertNotIn("X06 Frage 6: a → b … und", text)
        self.assertIn("\nAlle Änderungen:\n– X01 Frage 1: a → b\n", text)
        self.assertIn("– X08 Frage 8: a → b", text)
        kurz = erfassung_korrektur.notiz_text("Max", zeit, liste[:5])
        self.assertNotIn("weitere", kurz)
        self.assertNotIn("Alle Änderungen", kurz)
        # Makro _nc_eintrag zeigt den Block aufklappbar (<details class="nc-mehr">)
        s = SessionLocal()
        try:
            from app import notizen
            n = notizen.notiz_anlegen(s, self.vorgang_id, None, text, herkunft=erfassung_korrektur.NOTIZ_HERKUNFT)
            s.commit()
            nid = n.id
        finally:
            s.close()
        akte = _client(self.innen_id).get(f"/vorgaenge/{self.vorgang_id}").text
        self.assertIn('<details class="nc-mehr"><summary>Alle Änderungen anzeigen</summary>', akte)
        self.assertIn("… und 3 weitere", akte)
        s = SessionLocal()
        try:
            s.query(VorgangsNotiz).filter(VorgangsNotiz.id == nid).delete()
            s.commit()
        finally:
            s.close()

    def test_sperre_versand_vorbereitet_und_versionen(self):
        ad = _client(self.ad_id)
        for eid in (self.gesperrt_id, self.version_id):
            pruefen = ad.get(f"/erfassung/{eid}/pruefen").text
            self.assertIn('data-rolle="korrektur-gesperrt"', pruefen, eid)
            self.assertIn('title="Angebot ist bereits versandfertig"', pruefen)
            self.assertNotIn('data-rolle="korrektur-knopf"', pruefen)
            r = ad.get(f"/erfassung/{eid}/korrektur")
            self.assertEqual(r.status_code, 303)
            self.assertIn("versandfertig", r.headers["location"])
            r = ad.get(f"/erfassung/{eid}/seite/{self.alte_anlage_nr}")
            self.assertEqual(r.status_code, 303)
            r = ad.post(f"/erfassung/{eid}/seite/{self.alte_anlage_nr}", data=self._seite1(A04="DG"))
            self.assertEqual(r.status_code, 303)
            self.assertIn("versandfertig", r.headers["location"])
            self.assertEqual(json.loads(self._erfassung(eid).antworten_json)["A04"], "KG")   # unverändert
            self.assertIsNone(self._erfassung(eid).geaendert_am)
        # Vorgangsakte: Knopf deaktiviert mit Tooltip
        akte = ad.get(f"/vorgaenge/{self.vorgang_id}").text
        self.assertIn('data-rolle="korrektur-gesperrt"', akte)
        detail = _client(self.innen_id).get(f"/erfassungen/{self.gesperrt_id}").text
        self.assertIn('data-rolle="korrektur-gesperrt"', detail)
        s = SessionLocal()
        try:
            e = s.get(Erfassung, self.version_id)
            kette = erfassung_korrektur.verknuepfte_angebote(s, e)
            self.assertEqual({a.nummer for a in kette}, {f"AN-{PRAEFIX}-0003", f"AN-{PRAEFIX}-0003.2"})
            self.assertEqual(erfassung_korrektur.sperre(kette), (True, "Angebot ist bereits versandfertig"))
        finally:
            s.close()

    def test_hinweis_angebot_neu_berechnen(self):
        ad = _client(self.ad_id)
        vorher = ad.get(f"/erfassung/{self.mit_entwurf_id}/pruefen").text
        self.assertIn('data-rolle="korrektur-knopf"', vorher)
        self.assertNotIn('data-rolle="angebot-hinweis"', vorher)
        r = ad.post(f"/erfassung/{self.mit_entwurf_id}/seite/{self.alte_anlage_nr}", data=self._seite1(A02="1995"))
        self.assertEqual(r.status_code, 303)
        self.assertIn("Bitte+das+Angebot+neu+berechnen", r.headers["location"])
        pruefen = ad.get(r.headers["location"]).text
        self.assertIn("Antworten geändert. Bitte das Angebot neu berechnen.", pruefen)
        self.assertIn('data-rolle="angebot-hinweis"', pruefen)
        self.assertIn(f'href="/angebote/{self.angebot_entwurf_id}"', pruefen)
        detail = _client(self.innen_id).get(f"/erfassungen/{self.mit_entwurf_id}").text
        self.assertIn('data-rolle="angebot-hinweis"', detail)
        self.assertEqual(self._erfassung(self.mit_entwurf_id).status, "In Bearbeitung")

    def test_freitext_editor_schreibt_denselben_eintrag(self):
        innen = _client(self.innen_id)
        vorher = len(self._notizen(self.vorgang_id))
        r = innen.post(f"/erfassungen/{self.freitext_id}/freitext",
                       data={"freitext": "Alte Ölheizung im Keller, 1998. Tank 3.000 l."})
        self.assertEqual(r.status_code, 303)
        notiz = self._notizen(self.vorgang_id)[-1]
        self.assertEqual(len(self._notizen(self.vorgang_id)), vorher + 1)
        self.assertIn(f"Erfassung nachträglich geändert von {PRAEFIX} Innen am", notiz.text)
        self.assertIn("Freitext Beschreibung des Vorhabens: „Alte Ölheizung im Keller, 1998.“ → „Alte Ölheizung im Keller, 1998. Tank 3.000 l.“", notiz.text)
        e = self._erfassung(self.freitext_id)
        self.assertEqual(e.geaendert_von, self.innen_id)
        self.assertIn("nachträglich geändert", innen.get(f"/erfassungen/{self.freitext_id}").text)
        # Außendienst an fremder Freitext-Erfassung: abgewiesen (v13-Regel), kein Eintrag
        r = _client(self.fremd_id).post(f"/erfassungen/{self.freitext_id}/freitext", data={"freitext": "x"})
        self.assertEqual(r.status_code, 303)
        self.assertEqual(len(self._notizen(self.vorgang_id)), vorher + 1)


class ErfassungslisteObjekt(Basis):
    """Phase 204: Objektzeile mobil (/erfassung) und Spalte „Objekt“ (/erfassungen)."""

    def test_katalog_spalte_objekt(self):
        self.assertIn(("objekt", "Objekt", True), lead_boards.KATALOGE["erfassungen"])
        s = SessionLocal()
        try:
            spalten = lead_boards.spalten_fuer(s, 1, "erfassungen")
        finally:
            s.close()
        objekt = next(sp for sp in spalten if sp["key"] == "objekt")
        self.assertTrue(objekt["sichtbar"])

    def test_grosskunde_zwei_objekte_je_erfassung(self):
        ad = _client(self.ad_id)
        html = ad.get("/erfassung").text
        halle = re.search(rf'data-erfassung="{self.halle_erf_id}".*?data-rolle="objekt-zeile">(.*?)</span>\s*<span class="dezent">', html, re.S)
        verw = re.search(rf'data-erfassung="{self.verw_erf_id}".*?data-rolle="objekt-zeile">(.*?)</span>\s*<span class="dezent">', html, re.S)
        self.assertIsNotNone(halle, html[:300])
        self.assertIn("Halle Nord", halle.group(1))
        self.assertIn("Nordring 12, 47167 Duisburg", halle.group(1))
        self.assertIn("Verwaltung", verw.group(1))
        self.assertIn("Zentralallee 1, 47059 Duisburg", verw.group(1))      # Hauptobjekt = Kundenadresse
        # Ein-Objekt-Vorgang: nur die Adresse; ohne Zuordnung: Kundenadresse „(Kunde)“
        einzel = re.search(rf'data-erfassung="{self.gesendet_id}".*?data-rolle="objekt-zeile">(.*?)</span>\s*<span class="dezent">', html, re.S)
        self.assertNotIn("objekt-name", einzel.group(1))
        self.assertIn("Bogenweg 3, 47051 Duisburg", einzel.group(1))
        ohne = re.search(rf'data-erfassung="{self.ohne_objekt_id}".*?data-rolle="objekt-zeile">(.*?)</span>\s*<span class="dezent">', html, re.S)
        self.assertIn("(Kunde)", ohne.group(1))
        self.assertIn("Zentralallee 1", ohne.group(1))
        # Desktop-Tabelle: Spalte „Objekt“ mit demselben Inhalt, Suche findet die Objektbezeichnung
        innen = _client(self.innen_id)
        liste = innen.get("/erfassungen").text
        self.assertIn('data-key="objekt"', liste)
        zeile = re.search(rf'<tr data-zeile="{self.halle_erf_id}".*?</tr>', liste, re.S).group(0)
        self.assertIn('<td class="sp-objekt">', zeile)
        self.assertIn("Halle Nord", zeile)
        self.assertIn("halle nord", zeile)                                      # data-suche (Schnellfilter)
        suche = innen.get("/erfassungen?q=Halle+Nord").text
        self.assertIn(f'data-zeile="{self.halle_erf_id}"', suche)
        self.assertNotIn(f'data-zeile="{self.verw_erf_id}"', suche)
        # Helfer direkt
        s = SessionLocal()
        try:
            zeilen = erfassung_korrektur.objekt_zeilen(s, s.query(Erfassung).filter(
                Erfassung.id.in_([self.halle_erf_id, self.verw_erf_id, self.ohne_objekt_id])).all())
        finally:
            s.close()
        self.assertEqual(zeilen[self.halle_erf_id]["text"], "Halle Nord · Nordring 12, 47167 Duisburg")
        self.assertEqual(zeilen[self.verw_erf_id]["text"], "Verwaltung · Zentralallee 1, 47059 Duisburg")
        self.assertTrue(zeilen[self.ohne_objekt_id]["kunde"])


if __name__ == "__main__":
    unittest.main()
