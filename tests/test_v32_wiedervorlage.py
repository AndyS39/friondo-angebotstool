# v32 (PLAN_V19 Phase 162): automatische Wiedervorlage nach Angebotsversand, Block
# „Fällig heute“, Glocke art nachfassen, monday-Sync nachführen, vot_abgleich.py.
# Kalender: der Plan nennt „Fr 10.10.2026“ (tatsächlich ein Samstag) – gerechnet wird mit
# Fr 09.10.2026: +3 Werktage = Mi 14.10., MFH +5 = Fr 16.10., Parameter 6 = Mo 19.10.
# (Rückfrage im Bericht M). Kein Netzzugriff: Graph, monday und Rückspielung sind gemockt.
import os
import subprocess
import sys
import unittest
from datetime import date, datetime, timedelta
from pathlib import Path
from unittest import mock

from fastapi.testclient import TestClient

from app import auth, benachrichtigungen, mail_sync, monday_sync, nachfassen
from app.db import SessionLocal
from app.main import app
from app.models import (Angebot, AngebotsPosition, Benachrichtigung, Benutzer, Erfassung, Kunde,
                        Lead, MailAusgang, Vorgang, VorgangObjekt, VorgangsNotiz, VotTermin,
                        angebot_status_setzen)

PRAEFIX = "V32M"
PROJEKT = Path(__file__).resolve().parent.parent
FREITAG = date(2026, 10, 9)


def _client(benutzer_id: int) -> TestClient:
    c = TestClient(app, follow_redirects=False)
    c.cookies.set(auth.COOKIE_NAME, auth.cookie_wert(benutzer_id))
    return c


def _angebot(s, kunde, vorgang, nummer, status="Versand vorbereitet", konversation=None,
             netto_cent=2726891, extern=False):
    a = Angebot(nummer=nummer, kunde_id=kunde.id, vorgang_id=vorgang.id, status=status,
                konfigurator_typ="WP", ust_satz=19.0, graph_conversation_id=konversation,
                extern=extern, extern_endbetrag_cent=(netto_cent if extern else None))
    if not extern:
        a.positionen.append(AngebotsPosition(sort=1, pos_nr="047", bezeichnung="Wärmepumpe",
                                             menge=1, e_preis_cent=netto_cent))
    s.add(a)
    s.flush()
    return a


class WiedervorlageTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        s = SessionLocal()
        try:
            cls._aufraeumen(s)

            def benutzer(name, rolle, **extra):
                b = Benutzer(name=f"{PRAEFIX} {name}", rolle=rolle, aktiv=True,
                             email=f"{name.lower().replace(' ', '')}@v32m.local",
                             pin_hash=auth.pin_hash("4321"), **extra)
                s.add(b)
                s.flush()
                return b.id

            cls.ad_id = benutzer("Rene", "aussendienst", benachrichtigung_mail="sofort")
            cls.ad2_id = benutzer("Zweiter AD", "aussendienst")
            cls.id_id = benutzer("Innendienst", "innendienst")
            s.commit()
        finally:
            s.close()
        cls.admin = _client(1)
        cls.ad = _client(cls.ad_id)
        cls.id_client = _client(cls.id_id)

    @classmethod
    def _aufraeumen(cls, s):
        ids = [k.id for k in s.query(Kunde).filter(Kunde.nachname.like(f"{PRAEFIX}%"))]
        if ids:
            vids = [v.id for v in s.query(Vorgang).filter(Vorgang.kunde_id.in_(ids))]
            if vids:
                for a in s.query(Angebot).filter(Angebot.vorgang_id.in_(vids)):
                    s.delete(a)
                s.query(VotTermin).filter(VotTermin.vorgang_id.in_(vids)).delete(synchronize_session=False)
                s.query(VorgangsNotiz).filter(VorgangsNotiz.vorgang_id.in_(vids)).delete(synchronize_session=False)
                s.query(Erfassung).filter(Erfassung.vorgang_id.in_(vids)).delete(synchronize_session=False)
                s.query(VorgangObjekt).filter(VorgangObjekt.vorgang_id.in_(vids)).delete(synchronize_session=False)
                s.query(Vorgang).filter(Vorgang.id.in_(vids)).delete(synchronize_session=False)
            s.query(Kunde).filter(Kunde.id.in_(ids)).delete(synchronize_session=False)
        s.query(Lead).filter(Lead.monday_item_id.like(f"{PRAEFIX}%")).delete(synchronize_session=False)
        bids = [b.id for b in s.query(Benutzer).filter(Benutzer.name.like(f"{PRAEFIX} %"))]
        if bids:
            s.query(Benachrichtigung).filter(Benachrichtigung.benutzer_id.in_(bids)).delete(synchronize_session=False)
            s.query(Benutzer).filter(Benutzer.id.in_(bids)).delete(synchronize_session=False)
        s.query(MailAusgang).filter(MailAusgang.empfaenger.like("%@v32m.local")).delete(synchronize_session=False)
        s.commit()

    @classmethod
    def tearDownClass(cls):
        s = SessionLocal()
        try:
            cls._aufraeumen(s)
        finally:
            s.close()

    def _vorgang(self, s, name, objektart=None, ad_id=None, telefon="0203 555 4711"):
        kunde = Kunde(anrede="Herr", vorname="Peter", nachname=f"{PRAEFIX} {name}", strasse="Testweg 1",
                      plz="47798", ort="Krefeld", telefon=telefon, interesse="WP", objektart=objektart)
        s.add(kunde)
        s.flush()
        vorgang = Vorgang(kunde_id=kunde.id, ad_id=self.ad_id if ad_id is None else ad_id)
        s.add(vorgang)
        s.flush()
        return kunde, vorgang

    # --- Hook ------------------------------------------------------------------------
    def test_versand_freitag_setzt_mittwoch_verantwortlicher_ad_aktivitaet(self):
        s = SessionLocal()
        try:
            kunde, vorgang = self._vorgang(s, "Hook")
            angebot = _angebot(s, kunde, vorgang, f"AN-{PRAEFIX}-H1")
            angebot_status_setzen(angebot, "Versendet")
            angebot.versendet_am = datetime(2026, 10, 9, 10, 0)
            self.assertTrue(nachfassen.nach_versand(s, angebot))
            s.commit()
            self.assertEqual(vorgang.wiedervorlage_am, datetime(2026, 10, 14))
            self.assertEqual(vorgang.wiedervorlage_benutzer_id, self.ad_id)
            self.assertEqual(vorgang.wiedervorlage_art, "angebot_nachfassen")
            self.assertEqual(vorgang.verfolgung_status, "versendet")
            notizen = s.query(VorgangsNotiz).filter(VorgangsNotiz.vorgang_id == vorgang.id).all()
            self.assertEqual(len(notizen), 1)
            self.assertEqual(notizen[0].benutzer_name, "System")
            self.assertEqual(notizen[0].text, "Wiedervorlage automatisch gesetzt: Angebot nachfassen am 14.10.2026")
            # Plan-Datum Fr „10.10.“ (= Samstag) führt ebenfalls auf Mi 14.10.
            vorgang.wiedervorlage_am = None
            self.assertTrue(nachfassen.nach_versand(s, angebot, versandtag=date(2026, 10, 10)))
            self.assertEqual(vorgang.wiedervorlage_am, datetime(2026, 10, 14))
            s.commit()
        finally:
            s.close()

    def test_mfh_und_parameter_sechs(self):
        from app import leadmanagement
        s = SessionLocal()
        try:
            kunde, vorgang = self._vorgang(s, "MFH", objektart="MFH")
            angebot = _angebot(s, kunde, vorgang, f"AN-{PRAEFIX}-M1")
            self.assertTrue(nachfassen.nach_versand(s, angebot, versandtag=FREITAG))
            self.assertEqual(vorgang.wiedervorlage_am, datetime(2026, 10, 16))
            s.commit()
            p = SessionLocal()
            try:
                leadmanagement.parameter_setzen(p, "nachfass_werktage_mfh", "6")
                p.commit()
                vorgang.wiedervorlage_am = None
                self.assertTrue(nachfassen.nach_versand(s, angebot, versandtag=FREITAG))
                self.assertEqual(vorgang.wiedervorlage_am, datetime(2026, 10, 19))
                s.commit()
            finally:
                leadmanagement.parameter_setzen(p, "nachfass_werktage_mfh", "5")
                p.commit()
                p.close()
        finally:
            s.close()

    def test_kombi_setzt_einmal(self):
        s = SessionLocal()
        try:
            kunde, vorgang = self._vorgang(s, "Kombi")
            a1 = _angebot(s, kunde, vorgang, f"AN-{PRAEFIX}-K1", konversation="V32M-kombi")
            a2 = _angebot(s, kunde, vorgang, f"AN-{PRAEFIX}-K2", konversation="V32M-kombi")
            self.assertTrue(nachfassen.nach_versand(s, a1, versandtag=FREITAG))
            self.assertFalse(nachfassen.nach_versand(s, a2, versandtag=FREITAG))
            s.commit()
            self.assertEqual(vorgang.wiedervorlage_am, datetime(2026, 10, 14))
            self.assertEqual(s.query(VorgangsNotiz).filter(VorgangsNotiz.vorgang_id == vorgang.id).count(), 1)
        finally:
            s.close()

    def test_spaetere_wiedervorlage_bleibt_fruehere_wird_ueberschrieben(self):
        s = SessionLocal()
        try:
            kunde, vorgang = self._vorgang(s, "Spaeter")
            angebot = _angebot(s, kunde, vorgang, f"AN-{PRAEFIX}-S1")
            vorgang.wiedervorlage_am = datetime(2026, 10, 30)
            vorgang.wiedervorlage_benutzer_id = self.id_id
            self.assertFalse(nachfassen.nach_versand(s, angebot, versandtag=FREITAG))
            self.assertEqual(vorgang.wiedervorlage_am, datetime(2026, 10, 30))
            self.assertEqual(vorgang.wiedervorlage_benutzer_id, self.id_id)
            self.assertEqual(s.query(VorgangsNotiz).filter(VorgangsNotiz.vorgang_id == vorgang.id).count(), 0)
            vorgang.wiedervorlage_am = datetime(2026, 10, 12)
            self.assertTrue(nachfassen.nach_versand(s, angebot, versandtag=FREITAG))
            self.assertEqual(vorgang.wiedervorlage_am, datetime(2026, 10, 14))
            self.assertEqual(vorgang.wiedervorlage_benutzer_id, self.ad_id)
            s.commit()
        finally:
            s.close()

    def test_ohne_ad_am_vorgang_versendender_benutzer(self):
        s = SessionLocal()
        try:
            kunde, vorgang = self._vorgang(s, "OhneAD", ad_id=0)
            vorgang.ad_id = None
            angebot = _angebot(s, kunde, vorgang, f"AN-{PRAEFIX}-O1")
            innendienst = s.get(Benutzer, self.id_id)
            self.assertTrue(nachfassen.nach_versand(s, angebot, benutzer=innendienst, versandtag=FREITAG))
            self.assertEqual(vorgang.wiedervorlage_benutzer_id, self.id_id)
            # Außendienstler der Erfassung gewinnt vor dem versendenden Innendienst
            kunde2, vorgang2 = self._vorgang(s, "OhneAD2", ad_id=0)
            vorgang2.ad_id = None
            angebot2 = _angebot(s, kunde2, vorgang2, f"AN-{PRAEFIX}-O2")
            s.add(Erfassung(kunde_id=kunde2.id, vorgang_id=vorgang2.id, angebot_id=angebot2.id,
                            benutzer_id=self.ad2_id, status="Erledigt", sparte="WP"))
            s.flush()
            self.assertTrue(nachfassen.nach_versand(s, angebot2, benutzer=innendienst, versandtag=FREITAG))
            self.assertEqual(vorgang2.wiedervorlage_benutzer_id, self.ad2_id)
            s.commit()
        finally:
            s.close()

    def test_externer_eintrag_versand_am_datum_des_eintrags(self):
        s = SessionLocal()
        try:
            kunde, vorgang = self._vorgang(s, "Extern")
            angebot = _angebot(s, kunde, vorgang, f"EXT-{PRAEFIX}-1", status="Versendet (extern)", extern=True)
            angebot.versendet_am = datetime(2026, 10, 9)   # Dialog-Datum „Extern erledigt“
            self.assertTrue(nachfassen.nach_versand(s, angebot))
            self.assertEqual(vorgang.wiedervorlage_am, datetime(2026, 10, 14))
            info = nachfassen.angebots_kurzinfo(s, vorgang)
            self.assertEqual(info["text"], "WP-Angebot vom 09.10.2026, Endbetrag 27.268,91 €")
            s.commit()
        finally:
            s.close()

    def test_wiedervorlage_setzen_vertrag(self):
        s = SessionLocal()
        try:
            kunde, vorgang = self._vorgang(s, "Vertrag")
            nachfassen.wiedervorlage_setzen(s, vorgang, "20.10.2026", self.ad_id, "nochmal_anrufen")
            self.assertEqual(vorgang.wiedervorlage_am, datetime(2026, 10, 20))
            self.assertEqual((vorgang.wiedervorlage_benutzer_id, vorgang.wiedervorlage_art),
                             (self.ad_id, "nochmal_anrufen"))
            nachfassen.wiedervorlage_setzen(s, vorgang, datetime(2026, 10, 21, 14, 30), self.ad_id, "x")
            self.assertEqual(vorgang.wiedervorlage_am, datetime(2026, 10, 21))   # ohne Uhrzeit
            nachfassen.wiedervorlage_setzen(s, vorgang, None, None, "")
            self.assertIsNone(vorgang.wiedervorlage_am)
            self.assertIsNone(vorgang.wiedervorlage_benutzer_id)
            self.assertEqual(vorgang.wiedervorlage_art, "")
            s.rollback()
        finally:
            s.close()

    # --- Versandwege ----------------------------------------------------------------
    def test_route_als_versendet_markieren(self):
        s = SessionLocal()
        try:
            kunde, vorgang = self._vorgang(s, "Route")
            angebot = _angebot(s, kunde, vorgang, f"AN-{PRAEFIX}-R1")
            s.commit()
            angebot_id, vorgang_id = angebot.id, vorgang.id
        finally:
            s.close()
        from app import monday_rueckspielung
        with mock.patch.object(monday_rueckspielung, "bei_versand", return_value=None):
            antwort = self.id_client.post(f"/angebote/{angebot_id}/status", data={"status": "Versendet"})
        self.assertEqual(antwort.status_code, 303)
        s = SessionLocal()
        try:
            vorgang = s.get(Vorgang, vorgang_id)
            erwartet = nachfassen.nachfass_datum(s, s.get(Kunde, vorgang.kunde_id), date.today())
            self.assertEqual(vorgang.wiedervorlage_am, datetime(erwartet.year, erwartet.month, erwartet.day))
            self.assertEqual(vorgang.wiedervorlage_benutzer_id, self.ad_id)
            self.assertEqual(vorgang.wiedervorlage_art, "angebot_nachfassen")
            self.assertEqual(s.get(Angebot, angebot_id).status, "Versendet")
        finally:
            s.close()

    def test_versand_erkennung_mail_sync_setzt_wiedervorlage(self):
        s = SessionLocal()
        try:
            kunde, vorgang = self._vorgang(s, "MailSync")
            angebot = _angebot(s, kunde, vorgang, f"AN-{PRAEFIX}-G1", konversation="V32M-conv")
            s.commit()
            angebot_id, vorgang_id = angebot.id, vorgang.id
        finally:
            s.close()
        nachricht = {"id": "V32M-msg-1", "conversationId": "V32M-conv", "isDraft": False,
                     "sentDateTime": "2026-10-13T09:00:00Z", "receivedDateTime": "2026-10-13T09:00:00Z",
                     "subject": "Ihr Angebot", "bodyPreview": "…",
                     "from": {"emailAddress": {"address": "angebot@friondo.de", "name": "Friondo"}}}

        def je_konversation(token, conversation_id, postfach=""):
            return [nachricht] if conversation_id == "V32M-conv" else []

        from app import graph_versand, monday_rueckspielung
        with mock.patch.object(graph_versand, "_token", return_value="tok"), \
                mock.patch.object(graph_versand, "angemeldeter_benutzer", return_value="id@friondo.de"), \
                mock.patch.object(mail_sync, "nachrichten_je_konversation", side_effect=je_konversation), \
                mock.patch.object(mail_sync, "nachrichten_je_betreff", return_value=[]), \
                mock.patch.object(monday_rueckspielung, "bei_versand", return_value=None):
            mail_sync.sync()
        s = SessionLocal()
        try:
            angebot = s.get(Angebot, angebot_id)
            vorgang = s.get(Vorgang, vorgang_id)
            self.assertEqual(angebot.status, "Versendet")
            self.assertIsNotNone(vorgang.wiedervorlage_am)
            self.assertEqual(vorgang.wiedervorlage_art, "angebot_nachfassen")
            self.assertEqual(vorgang.wiedervorlage_benutzer_id, self.ad_id)
            texte = [n.text for n in s.query(VorgangsNotiz).filter(VorgangsNotiz.vorgang_id == vorgang_id)]
            self.assertTrue(any(t.startswith("Wiedervorlage automatisch gesetzt") for t in texte), texte)
            # „Letzte Aktivitäten“ zeigt den Versand (Mail-Verlauf + Notiz)
            aktivitaeten = nachfassen.letzte_aktivitaeten(s, vorgang)
            self.assertTrue(any("versendet" in a["text"] for a in aktivitaeten), aktivitaeten)
        finally:
            s.close()

    # --- Fällig heute --------------------------------------------------------------------
    def test_faellig_heute_beim_ad_nicht_in_id_kachel(self):
        from app.main import _start_kontext
        heute = date.today()
        vorher = _start_kontext()["faellige"]
        s = SessionLocal()
        try:
            kunde, vorgang = self._vorgang(s, "Faellig")
            angebot = _angebot(s, kunde, vorgang, f"AN-{PRAEFIX}-F1", status="Versendet")
            angebot.versendet_am = datetime(2026, 10, 9, 9, 0)
            nachfassen.wiedervorlage_setzen(s, vorgang, heute, self.ad_id, "angebot_nachfassen")
            kunde2, vorgang2 = self._vorgang(s, "Ueberfaellig")
            nachfassen.wiedervorlage_setzen(s, vorgang2, heute - timedelta(days=1), self.ad_id, "angebot_nachfassen")
            kunde3, vorgang3 = self._vorgang(s, "Morgen")
            nachfassen.wiedervorlage_setzen(s, vorgang3, heute + timedelta(days=1), self.ad_id, "angebot_nachfassen")
            kunde4, vorgang4 = self._vorgang(s, "Fremd", ad_id=self.ad2_id)
            nachfassen.wiedervorlage_setzen(s, vorgang4, heute, self.ad2_id, "angebot_nachfassen")
            s.commit()
            karten = nachfassen.faellig_heute(s, self.ad_id)
            ids = [k["vorgang"].id for k in karten]
            self.assertEqual(ids[:2], [vorgang2.id, vorgang.id])   # überfällig zuerst
            self.assertNotIn(vorgang3.id, ids)
            self.assertNotIn(vorgang4.id, ids)
            karte = next(k for k in karten if k["vorgang"].id == vorgang.id)
            self.assertEqual(karte["angebot"]["text"], "WP-Angebot vom 09.10.2026, Endbetrag 32.450,00 €")
            self.assertEqual(karte["tel_href"], "tel:+492035554711")
            self.assertFalse(karte["ueberfaellig"])
            ueber = next(k for k in karten if k["vorgang"].id == vorgang2.id)
            self.assertTrue(ueber["ueberfaellig"])
            self.assertEqual(ueber["seit_text"], (heute - timedelta(days=1)).strftime("%d.%m."))
            for k in karten:
                self.assertFalse(any(x in str(k["angebot"]) for x in ("ek_cent", "deckungsbeitrag")))
            vorgang_id = vorgang.id
        finally:
            s.close()
        self.assertEqual(_start_kontext()["faellige"], vorher, "ID-Kachel zählt AD-Wiedervorlagen nicht")
        # Seite des Außendienstes
        seite = self.ad.get("/leads")
        self.assertEqual(seite.status_code, 200)
        self.assertIn("Fällig heute", seite.text)
        self.assertIn(f"{PRAEFIX} Faellig", seite.text)
        self.assertIn("WP-Angebot vom 09.10.2026, Endbetrag 32.450,00 €", seite.text)
        self.assertIn(f'id="faellig-{vorgang_id}"', seite.text)
        self.assertIn("Letzte Aktivitäten", seite.text)
        self.assertIn("Notiz zum Gespräch", seite.text)
        self.assertIn(f"seit {(heute - timedelta(days=1)).strftime('%d.%m.')}", seite.text)
        self.assertNotIn(f"{PRAEFIX} Fremd", seite.text)
        self.assertNotIn(f"{PRAEFIX} Morgen", seite.text.split('id="termine-heute"')[0])
        # Dialog „Nächster Schritt“ (Partial von N) hängt an der Karte
        self.assertIn(f"/vorgaenge/{vorgang_id}/naechster-schritt", seite.text)
        self.assertIn(f'data-ns-notiz="{vorgang_id}"', seite.text)
        # ID mit Vertriebler-Filter sieht die Karten des gewählten Vertrieblers
        id_seite = self.id_client.get(f"/leads?vertriebler_id={self.ad_id}")
        self.assertEqual(id_seite.status_code, 200)
        self.assertIn(f"{PRAEFIX} Faellig", id_seite.text)
        self.assertNotIn(f"{PRAEFIX} Fremd", id_seite.text)

    def test_notiz_aus_dem_feld_landet_im_chat_mit_autor_ad(self):
        s = SessionLocal()
        try:
            kunde, vorgang = self._vorgang(s, "Notiz")
            s.commit()
            vorgang_id = vorgang.id
        finally:
            s.close()
        antwort = self.ad.post(f"/leads/notiz/{vorgang_id}", data={"text": "Kunde will Rückruf am Freitag"},
                               headers={"Accept": "application/json"})
        self.assertEqual(antwort.status_code, 200, antwort.text)
        daten = antwort.json()
        self.assertTrue(daten["ok"])
        self.assertEqual(daten["eintrag"]["benutzer_name"], f"{PRAEFIX} Rene")
        umleitung = self.ad.post(f"/leads/notiz/{vorgang_id}", data={"text": "Zweite Notiz", "zurueck": "/leads#faellig"})
        self.assertEqual(umleitung.status_code, 303)
        self.assertTrue(umleitung.headers["location"].startswith("/leads?meldung="))
        self.assertTrue(umleitung.headers["location"].endswith("#faellig"))
        s = SessionLocal()
        try:
            notizen = (s.query(VorgangsNotiz).filter(VorgangsNotiz.vorgang_id == vorgang_id)
                       .order_by(VorgangsNotiz.id).all())
            self.assertEqual([n.text for n in notizen], ["Kunde will Rückruf am Freitag", "Zweite Notiz"])
            self.assertEqual(notizen[0].benutzer_name, f"{PRAEFIX} Rene")
            self.assertEqual(notizen[0].benutzer_id, self.ad_id)
        finally:
            s.close()
        # fremder Vorgang: 403
        fremd = _client(self.ad2_id).post(f"/leads/notiz/{vorgang_id}", data={"text": "x"},
                                          headers={"Accept": "application/json"})
        self.assertEqual(fremd.status_code, 403)
        leer = self.ad.post(f"/leads/notiz/{vorgang_id}", data={"text": "  "}, headers={"Accept": "application/json"})
        self.assertEqual(leer.status_code, 400)

    # --- Glocke -----------------------------------------------------------------------
    def test_glocke_faellig_heute_ohne_mail(self):
        from app import projektierung as kern
        s = SessionLocal()
        try:
            kunde, vorgang = self._vorgang(s, "Glocke")
            nachfassen.wiedervorlage_setzen(s, vorgang, date.today(), self.ad_id, "angebot_nachfassen")
            s.query(Benachrichtigung).filter(Benachrichtigung.benutzer_id == self.ad_id).delete(synchronize_session=False)
            alt = kern.parameter_holen(s, "faellig_lauf_datum", "")
            s.commit()
            mails_vorher = s.query(MailAusgang).filter(MailAusgang.empfaenger == "rene@v32m.local").count()
            ergebnis = benachrichtigungen.taeglicher_lauf(s, erzwingen=True)
            self.assertNotIn("uebersprungen", ergebnis)
            glocken = (s.query(Benachrichtigung)
                       .filter(Benachrichtigung.benutzer_id == self.ad_id, Benachrichtigung.art == "nachfassen").all())
            self.assertEqual(len(glocken), 1)
            self.assertTrue(glocken[0].text.startswith("Fällig heute: "), glocken[0].text)
            self.assertIn("Anruf", glocken[0].text)
            self.assertEqual(glocken[0].link, "/leads#faellig")
            self.assertEqual(s.query(MailAusgang).filter(MailAusgang.empfaenger == "rene@v32m.local").count(),
                             mails_vorher, "art nachfassen: keine Sofort-Mail")
            # zweiter Lauf am selben Tag legt keine zweite Glocke an
            self.assertEqual(nachfassen.glocke_faellig_heute(s), 0)
            self.assertEqual(benachrichtigungen.ungelesen_anzahl(s, s.get(Benutzer, self.ad_id)), 1)
            kern.parameter_setzen(s, "faellig_lauf_datum", alt)
            s.commit()
        finally:
            s.close()
        # Glocken-Dropdown zeigt den Eintrag (Anzahl = alle fälligen Vorgänge des AD aus
        # dieser Testklasse), Klick springt nach Mein Tag
        seite = self.ad.get("/leads")
        self.assertIn("Fällig heute: ", seite.text)
        self.assertIn("zum Nachfassen – Mein Tag", seite.text)
        self.assertIn("/benachrichtigungen/", seite.text)

    # --- monday-Sync nachführen -------------------------------------------------------
    def test_monday_sync_aktualisiert_und_sagt_ab(self):
        from app import vorgaenge as vorgaenge_modul
        s = SessionLocal()
        try:
            kunde = Kunde(anrede="Frau", vorname="Anna", nachname=f"{PRAEFIX} Monday", strasse="Sync-Str. 2",
                          plz="47051", ort="Duisburg", telefon="0203 1", interesse="WP")
            s.add(kunde)
            s.flush()
            morgen = datetime.combine(date.today() + timedelta(days=1), datetime.min.time()).replace(hour=10)
            lead = Lead(monday_item_id=f"{PRAEFIX}-sync-1", vorname="Anna", nachname=f"{PRAEFIX} Monday",
                        kunde_id=kunde.id, benutzer_id=self.ad_id, vot_datum=morgen, strasse="Sync-Str. 2",
                        plz="47051", ort="Duisburg")
            s.add(lead)
            s.flush()
            vorgang = vorgaenge_modul.vorgang_fuer_lead(s, lead)
            s.commit()
            z = monday_sync.vot_termine_nachfuehren(s, nur_vorgang_ids=[vorgang.id])
            s.commit()
            self.assertEqual(z["angelegt"], 1)
            termine = s.query(VotTermin).filter(VotTermin.vorgang_id == vorgang.id).all()
            self.assertEqual(len(termine), 1)
            t = termine[0]
            self.assertEqual((t.quelle, t.status, t.beginn, t.ad_id), ("monday", "geplant", morgen, self.ad_id))
            self.assertIsNotNone(t.objekt_id, "objekt_id = Hauptobjekt (v31)")
            self.assertIn("Sync-Str. 2", t.adresse)
            # geändertes Datum → derselbe Eintrag, nicht dupliziert
            lead.vot_datum = morgen + timedelta(days=2)
            z = monday_sync.vot_termine_nachfuehren(s, nur_vorgang_ids=[vorgang.id])
            s.commit()
            self.assertEqual((z["aktualisiert"], z["angelegt"]), (1, 0))
            termine = s.query(VotTermin).filter(VotTermin.vorgang_id == vorgang.id).all()
            self.assertEqual(len(termine), 1)
            self.assertEqual(termine[0].id, t.id)
            self.assertEqual(termine[0].beginn, morgen + timedelta(days=2))
            # gelöschtes Datum → abgesagt
            lead.vot_datum = None
            z = monday_sync.vot_termine_nachfuehren(s, nur_vorgang_ids=[vorgang.id])
            s.commit()
            self.assertEqual(z["abgesagt"], 1)
            self.assertEqual(s.get(VotTermin, t.id).status, "abgesagt")
            self.assertEqual(s.get(VotTermin, t.id).grund_text, monday_sync.ABGESAGT_GRUND_SYNC)
            # Datum wieder da → derselbe Eintrag wieder geplant
            lead.vot_datum = morgen
            z = monday_sync.vot_termine_nachfuehren(s, nur_vorgang_ids=[vorgang.id])
            s.commit()
            self.assertEqual(z["reaktiviert"], 1)
            self.assertEqual(s.query(VotTermin).filter(VotTermin.vorgang_id == vorgang.id).count(), 1)
            self.assertEqual(s.get(VotTermin, t.id).status, "geplant")
            # zweiter Lauf ohne Änderung: alles 0
            z = monday_sync.vot_termine_nachfuehren(s, nur_vorgang_ids=[vorgang.id])
            self.assertEqual(sum(z.values()), 0, z)
            # Nachlauf des Syncs ruft die Nachführung (Fehler landen in der Hinweisliste)
            fehler: list = []
            with mock.patch.object(monday_sync, "vot_termine_nachfuehren", side_effect=RuntimeError("kaputt")):
                monday_sync._nachlauf(s, fehler)
            self.assertTrue(any("VOT-Termine" in f for f in fehler), fehler)
            s.commit()
        finally:
            s.close()

    def test_vot_abgleich_skript_gegen_kopie(self):
        """scripts/vot_abgleich.py gegen eine kleine Test-Kopie (eigene Datei, danach gelöscht)."""
        import sqlite3

        from sqlalchemy import create_engine
        from sqlalchemy.orm import sessionmaker

        from app.db import Base
        ziel = PROJEKT / "diagnose" / "v31" / f"tmp_vot_abgleich_{PRAEFIX}.db"
        for alt in (ziel, Path(str(ziel) + "-wal"), Path(str(ziel) + "-shm")):
            alt.unlink(missing_ok=True)
        engine = create_engine(f"sqlite:///{ziel}")
        Base.metadata.create_all(engine)
        Sitzung = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
        s = Sitzung()
        try:
            kunde = Kunde(vorname="Max", nachname="Abgleich", plz="47798", ort="Krefeld")
            s.add(kunde)
            s.flush()
            lead = Lead(monday_item_id="abgleich-1", vorname="Max", nachname="Abgleich", kunde_id=kunde.id,
                        vot_datum=datetime(2026, 10, 20, 10, 0), plz="47798", ort="Krefeld")
            s.add(lead)
            s.flush()
            s.add(Vorgang(kunde_id=kunde.id, lead_id=lead.id))
            s.commit()
        finally:
            s.close()
            engine.dispose()
        umgebung = dict(os.environ, PYTHONIOENCODING="utf-8")
        umgebung.pop("DB_PFAD_OVERRIDE", None)
        befehl = [sys.executable, str(PROJEKT / "scripts" / "vot_abgleich.py"), "--data", str(ziel)]
        try:
            bericht = subprocess.run(befehl, capture_output=True, text=True, cwd=str(PROJEKT),
                                     env=umgebung, timeout=120, encoding="utf-8", errors="replace")
            self.assertEqual(bericht.returncode, 0, bericht.stderr[-2000:])
            self.assertIn("ohne offene Termin-Zeile: 1", bericht.stdout)
            self.assertIn("Reparatur mit --anlegen", bericht.stdout)
            reparatur = subprocess.run(befehl + ["--anlegen"], capture_output=True, text=True, cwd=str(PROJEKT),
                                       env=umgebung, timeout=120, encoding="utf-8", errors="replace")
            self.assertEqual(reparatur.returncode, 0, reparatur.stderr[-2000:])
            self.assertIn("angelegt = 1", reparatur.stdout)
            self.assertIn("Ergebnis: keine Abweichungen", reparatur.stdout)
            c = sqlite3.connect(ziel)   # kein `with`: das schließt die Verbindung nicht (Windows-Sperre)
            try:
                zeilen = c.execute("select status, quelle, beginn from vot_termine").fetchall()
            finally:
                c.close()
            self.assertEqual(len(zeilen), 1)
            self.assertEqual(zeilen[0][:2], ("geplant", "monday"))
            # Schutz: Live-Verzeichnis wird abgewiesen
            live = subprocess.run([sys.executable, str(PROJEKT / "scripts" / "vot_abgleich.py"), "--data",
                                   str(PROJEKT / "data")], capture_output=True, text=True, cwd=str(PROJEKT),
                                  env=umgebung, timeout=60, encoding="utf-8", errors="replace")
            self.assertNotEqual(live.returncode, 0)
            self.assertIn("Live-Verzeichnis", live.stdout + live.stderr)
        finally:
            for alt in (ziel, Path(str(ziel) + "-wal"), Path(str(ziel) + "-shm")):
                try:
                    alt.unlink(missing_ok=True)
                except PermissionError:
                    pass


if __name__ == "__main__":
    unittest.main()
