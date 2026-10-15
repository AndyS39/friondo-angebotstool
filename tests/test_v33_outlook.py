# v33 (PLAN_V20 Phase 170, Agent O): Outlook-Sync je Mitarbeiter – Graph vollständig gemockt
# (graph_versand._token und _graph_aufruf), kein Netz. Prüft die Warteschlange
# (outlook_auftraege), den Lauf outlook-sync (POST/PATCH/DELETE je Kopie, Kennzeichen,
# Betreff-Regel, 3 Versuche, 403), den Lauf outlook-ruecklesen (Verschieben/Löschen in
# Outlook, fremde Einträge nur als Belegtzeit), den Belegt-Cache (kalender.frei_belegt),
# VOT-Demo → Testpostfach, HV ohne Postfach, Läufe/Pool-Invariante, Migration zweimal, das
# Makro _outlook_status.html und die Seiten (Projektierung → Termine, Meine Termine,
# Deals-Board). Sitzungsdisziplin: im Moment jedes gemockten Graph-Aufrufs hält keine
# Sitzung eine Pool-Verbindung. Läuft gegen die DB (DB_PFAD_OVERRIDE), räumt alles auf.
import unittest
import urllib.parse
from datetime import datetime, timedelta, timezone
from unittest import mock

from fastapi.testclient import TestClient

from app import auth, config, db, graph_versand, kalender, lead_glocken, outlook_kalender, outlook_sync, rollen, scheduler
from app import leadmanagement as kern
from app import projektierung as pj
from app.db import SessionLocal, init_db
from app.main import app
from app.models import (AdProfil, Benachrichtigung, Benutzer, Gewerk, Kunde, LeadAktivitaet,
                        OutlookAuftrag, OutlookBelegt, OutlookEreignis, Projekt, ProjektTermin,
                        ProjektVerlauf, Team, TeamMitglied, TerminBesetzung, Vorgang, VotTermin)

PRAEFIX = "V33O"
DOMAIN = "v33o.local"


def aufraeumen(s) -> None:
    ids = [b.id for b in s.query(Benutzer).filter(Benutzer.name.like(f"{PRAEFIX}%"))]
    for k in s.query(Kunde).filter(Kunde.nachname.like(f"{PRAEFIX}%")):
        for v in s.query(Vorgang).filter_by(kunde_id=k.id):
            for t in s.query(VotTermin).filter_by(vorgang_id=v.id):
                s.query(OutlookEreignis).filter_by(termin_art="vot", termin_id=t.id).delete()
                s.query(OutlookAuftrag).filter_by(termin_art="vot", termin_id=t.id).delete()
                s.delete(t)
            for t in s.query(ProjektTermin).filter_by(vorgang_id=v.id):   # Service ohne Projekt
                s.query(OutlookEreignis).filter_by(termin_art="projekt", termin_id=t.id).delete()
                s.query(OutlookAuftrag).filter_by(termin_art="projekt", termin_id=t.id).delete()
                s.query(TerminBesetzung).filter_by(termin_id=t.id).delete()
                s.delete(t)
            s.query(LeadAktivitaet).filter_by(vorgang_id=v.id).delete()
            s.query(Benachrichtigung).filter(
                Benachrichtigung.link == f"/lead-management/lead/{v.id}").delete()
            s.delete(v)
        for p in s.query(Projekt).filter_by(kunde_id=k.id):
            for t in s.query(ProjektTermin).filter_by(projekt_id=p.id):
                s.query(OutlookEreignis).filter_by(termin_art="projekt", termin_id=t.id).delete()
                s.query(OutlookAuftrag).filter_by(termin_art="projekt", termin_id=t.id).delete()
                s.query(TerminBesetzung).filter_by(termin_id=t.id).delete()
                s.delete(t)
            s.query(ProjektVerlauf).filter_by(projekt_id=p.id).delete()
            s.query(Benachrichtigung).filter(
                Benachrichtigung.link.like(f"/projektierung/projekt/{p.id}%")).delete(
                synchronize_session=False)
            s.query(Gewerk).filter_by(projekt_id=p.id).delete()
            s.delete(p)
        s.delete(k)
    s.flush()
    s.query(OutlookAuftrag).filter(OutlookAuftrag.postfach.like(f"%{DOMAIN}")).delete(
        synchronize_session=False)
    s.query(OutlookEreignis).filter(OutlookEreignis.postfach.like(f"%{DOMAIN}")).delete(
        synchronize_session=False)
    if ids:
        for modell in (OutlookEreignis, OutlookAuftrag, OutlookBelegt, Benachrichtigung,
                       TerminBesetzung, AdProfil, TeamMitglied):
            s.query(modell).filter(modell.benutzer_id.in_(ids)).delete(synchronize_session=False)
        s.query(Benutzer).filter(Benutzer.id.in_(ids)).delete(synchronize_session=False)
    s.query(Team).filter(Team.name.like(f"{PRAEFIX}%")).delete(synchronize_session=False)
    s.query(Projekt).filter(Projekt.nummer.like(f"PR-{PRAEFIX}%")).delete(synchronize_session=False)
    s.commit()


def belegt() -> int:
    return db.engine.pool.checkedout()


def lokal(utc_wert: datetime) -> datetime:
    """UTC → lokale Zeit wie outlook_sync._zeit_aus_graph (DST-sicher)."""
    return utc_wert.replace(tzinfo=timezone.utc).astimezone().replace(tzinfo=None)


class Basis(unittest.TestCase):
    PARAMETER = ("kalender_sync", "kalender_testpostfach", lead_glocken.PARAMETER)

    @classmethod
    def setUpClass(cls):
        init_db()
        cls.s = SessionLocal()
        aufraeumen(cls.s)
        rollen.migration_v33_rollen(cls.s)
        cls.s.commit()
        rollen.cache_leeren()
        cls.gesichert = {n: kern.parameter_holen(cls.s, n, "") for n in cls.PARAMETER}
        kern.parameter_setzen(cls.s, "kalender_sync", "aus")
        kern.parameter_setzen(cls.s, "kalender_testpostfach", "")
        cls.m1 = cls.benutzer("M1", "montage")
        cls.m2 = cls.benutzer("M2", "montage")
        cls.m3 = cls.benutzer("M3", "montage")
        cls.pl = cls.benutzer("PL", "projektierung")
        cls.ad = cls.benutzer("AD", "aussendienst")
        cls.hv = cls.benutzer("HV", "handelsvertreter", email="hv@extern.example")
        rollen.hv_spiegeln(cls.s, cls.hv)
        cls.team = Team(name=f"{PRAEFIX} Team", typ="montage", aktiv=True)
        cls.s.add(cls.team)
        cls.s.flush()
        cls.kunde = Kunde(anrede="Herr", vorname="Max", nachname=f"{PRAEFIX} Kunde", strasse="Weg 1",
                          plz="47139", ort="Duisburg", telefon="0203 1", kunden_nr="K-33")
        cls.s.add(cls.kunde)
        cls.s.flush()
        cls.vorgang = Vorgang(kunde_id=cls.kunde.id, lead_phase="terminiert", ad_id=cls.ad.id,
                              leadmanager_id=1)
        cls.s.add(cls.vorgang)
        cls.s.flush()
        cls.projekt = Projekt(nummer=f"PR-{PRAEFIX}", kunde_id=cls.kunde.id, vorgang_id=cls.vorgang.id,
                              projektleiter_id=cls.pl.id)
        cls.s.add(cls.projekt)
        cls.s.flush()
        cls.gewerk = Gewerk(projekt_id=cls.projekt.id, sparte="WP", phase="planung")
        cls.s.add(cls.gewerk)
        cls.s.commit()
        cls.ids = {"m1": cls.m1.id, "m2": cls.m2.id, "m3": cls.m3.id, "pl": cls.pl.id, "ad": cls.ad.id,
                   "hv": cls.hv.id, "team": cls.team.id, "kunde": cls.kunde.id,
                   "vorgang": cls.vorgang.id, "projekt": cls.projekt.id, "gewerk": cls.gewerk.id}
        cls.postfach = {"m1": f"m1@{DOMAIN}", "m2": f"m2@{DOMAIN}", "m3": f"m3@{DOMAIN}",
                        "ad": f"ad@{DOMAIN}", "test": f"test@{DOMAIN}"}
        cls.zaehler = 0

    @classmethod
    def tearDownClass(cls):
        cls.s.rollback()
        for n, w in cls.gesichert.items():
            kern.parameter_setzen(cls.s, n, w)
        cls.s.commit()
        aufraeumen(cls.s)
        cls.s.close()
        graph_versand.zugriff_verweigert_leeren()
        outlook_sync.ohne_zugriff_leeren()

    @classmethod
    def benutzer(cls, name, rolle, email=None):
        b = Benutzer(name=f"{PRAEFIX} {name}", rolle=rolle, aktiv=True,
                     email=email if email is not None else f"{name.lower()}@{DOMAIN}",
                     pin_hash=auth.pin_hash("4321"))
        cls.s.add(b)
        cls.s.flush()
        return b

    def setUp(self):
        """Jeder Test beginnt ohne Termine/Kopien/Aufträge der Vortests (die Personen werden
        geteilt – ein gemockter Kalender würde sonst fremde Kopien als gelöscht melden)."""
        self.s.rollback()
        for t in self.s.query(ProjektTermin).filter(
                (ProjektTermin.projekt_id == self.ids["projekt"])
                | (ProjektTermin.vorgang_id == self.ids["vorgang"])):
            for modell in (OutlookAuftrag, OutlookEreignis):
                self.s.query(modell).filter_by(termin_art="projekt", termin_id=t.id).delete(
                    synchronize_session=False)
            self.s.query(TerminBesetzung).filter_by(termin_id=t.id).delete(synchronize_session=False)
            self.s.delete(t)
        for vt in self.s.query(VotTermin).filter_by(vorgang_id=self.ids["vorgang"]):
            for modell in (OutlookAuftrag, OutlookEreignis):
                self.s.query(modell).filter_by(termin_art="vot", termin_id=vt.id).delete(
                    synchronize_session=False)
            self.s.delete(vt)
        personen = [self.ids[k] for k in ("m1", "m2", "m3", "pl", "ad", "hv")]
        self.s.query(OutlookBelegt).filter(OutlookBelegt.benutzer_id.in_(personen)).delete(
            synchronize_session=False)
        # offene Aufträge anderer Testmodule (Termine über Routen, Warteschlange nie aufgeräumt)
        # würden sonst im gemessenen Lauf mitlaufen
        outlook_sync.fremde_auftraege_abschliessen(self.s)
        self.s.commit()
        graph_versand.zugriff_verweigert_leeren()
        outlook_sync.ohne_zugriff_leeren()

    def tearDown(self):
        self.s.rollback()

    # --- Helfer ----------------------------------------------------------------------
    def entlasten(self) -> int:
        """Testsitzung ohne Verbindung; liefert die Pool-Basis (andere Module)."""
        self.s.rollback()
        db.verbindung_freigeben(self.s)
        return belegt()

    def termin_neu(self, besetzung, tage=7, typ="montage"):
        beginn = (datetime.now() + timedelta(days=tage)).replace(hour=0, minute=0, second=0,
                                                                   microsecond=0)
        t = ProjektTermin(projekt_id=self.ids["projekt"], gewerk_id=self.ids["gewerk"], typ=typ,
                          zweck="wp" if typ == "montage" else "", beginn=beginn,
                          ende=beginn + timedelta(days=1), ganztaegig=True, dauer_tage=2,
                          team_id=self.ids["team"], erstellt_von=self.ids["pl"])
        self.s.add(t)
        self.s.flush()
        # SQLite vergibt die ID eines gelöschten Termins neu – Reste eines Vortests entfernen
        for modell in (OutlookAuftrag, OutlookEreignis):
            self.s.query(modell).filter_by(termin_art="projekt", termin_id=t.id).delete(
                synchronize_session=False)
        pj.besetzung_setzen(self.s, t, [b.id for b in besetzung], benutzer=self.pl)
        self.s.commit()
        return t

    def senden(self, t):
        ok, fehler = outlook_kalender.event_senden(self.s, t)
        self.s.commit()
        self.assertTrue(ok, fehler)
        return ok

    def offene(self, art, tid):
        return (self.s.query(OutlookAuftrag)
                .filter_by(termin_art=art, termin_id=tid, status="offen").order_by(OutlookAuftrag.id).all())

    def ereignisse(self, art, tid):
        self.s.expire_all()
        return (self.s.query(OutlookEreignis)
                .filter_by(termin_art=art, termin_id=tid).order_by(OutlookEreignis.id).all())

    def lauf_sync(self, graph=None):
        """Lauf outlook-sync mit gemocktem Graph; misst die Pool-Belegung je Aufruf."""
        aufrufe = []
        basis = self.entlasten()

        def standard(methode, pfad, token, daten=None):
            aufrufe.append((methode, pfad, daten, belegt() - basis))
            if methode == "POST":
                type(self).zaehler += 1
                return {"id": f"EV-{type(self).zaehler}"}
            return {}
        with mock.patch.object(graph_versand, "_token", return_value="tok"), \
                mock.patch.object(graph_versand, "_graph_aufruf", side_effect=graph or standard):
            ergebnis = outlook_sync.sync_lauf()
        self.s.expire_all()
        return ergebnis, aufrufe

    def lauf_ruecklesen(self, je_postfach, graph=None):
        """Lauf outlook-ruecklesen; `je_postfach` = {postfach: [calendarView-Einträge]}."""
        aufrufe = []
        basis = self.entlasten()

        def standard(methode, pfad, token, daten=None):
            aufrufe.append((methode, pfad, daten, belegt() - basis))
            if methode != "GET":
                raise AssertionError(f"Schreibender Graph-Aufruf im Rücklesen: {methode} {pfad}")
            for postfach, liste in je_postfach.items():
                if f"/users/{urllib.parse.quote(postfach)}/" in pfad:
                    return {"value": liste}
            return {"value": []}
        with mock.patch.object(graph_versand, "_token", return_value="tok"), \
                mock.patch.object(graph_versand, "_graph_aufruf", side_effect=graph or standard):
            ergebnis = outlook_sync.ruecklesen_lauf()
        self.s.expire_all()
        return ergebnis, aufrufe

    @staticmethod
    def ev(event_id, start, end, tid=None, bid=None, all_day=True, show_as="busy", cancelled=False,
           art="projekt"):
        e = {"id": event_id, "isAllDay": all_day, "showAs": show_as, "isCancelled": cancelled,
             "subject": "Eintrag",
             "start": {"dateTime": start.strftime("%Y-%m-%dT%H:%M:%S.0000000"), "timeZone": "UTC"},
             "end": {"dateTime": end.strftime("%Y-%m-%dT%H:%M:%S.0000000"), "timeZone": "UTC"}}
        if tid is not None:
            e["singleValueExtendedProperties"] = [
                {"id": outlook_sync.PROPERTY_ID, "value": f"{art}:{tid}:{bid}"}]
        return e

    def verlauf_texte(self):
        return [z.text for z in self.s.query(ProjektVerlauf)
                .filter_by(projekt_id=self.ids["projekt"]).order_by(ProjektVerlauf.id)]


# --- Schreiben: Warteschlange + Lauf outlook-sync ---------------------------------------

class Schreiben(Basis):
    def test_zwei_monteure_zwei_kopien_mit_kennzeichen(self):
        t = self.termin_neu([self.m1, self.m2])
        tid = t.id
        self.senden(t)
        auftraege = self.offene("projekt", tid)
        self.assertEqual([(a.aktion, a.benutzer_id, a.postfach) for a in auftraege],
                         [("anlegen", self.ids["m1"], self.postfach["m1"]),
                          ("anlegen", self.ids["m2"], self.postfach["m2"])])
        status = outlook_sync.status_fuer(self.s, "projekt", tid)
        self.assertEqual(status["stand"], "ausstehend")
        self.assertEqual(len(status["kopien"]), 2)
        ergebnis, aufrufe = self.lauf_sync()
        self.assertEqual((ergebnis["erledigt"], ergebnis["fehler"]), (2, 0), ergebnis)
        self.assertEqual([a[0] for a in aufrufe], ["POST", "POST"])
        self.assertEqual({a[1] for a in aufrufe},
                         {f"/users/{urllib.parse.quote(self.postfach['m1'])}/events",
                          f"/users/{urllib.parse.quote(self.postfach['m2'])}/events"})
        self.assertEqual([a[3] for a in aufrufe], [0, 0], "Pool-Verbindung während des Graph-Aufrufs")
        for methode, pfad, daten, _ in aufrufe:
            self.assertEqual(daten["categories"], [outlook_sync.KATEGORIE])
            self.assertEqual(daten["showAs"], "busy")
            self.assertTrue(daten["isAllDay"])
            self.assertTrue(daten["subject"].startswith("Montage (WP): "), daten["subject"])
            self.assertIn(f"{PRAEFIX} Kunde", daten["subject"])
            self.assertIn("47139 Duisburg", daten["subject"])
            self.assertTrue(daten["subject"].endswith(f"(PR-{PRAEFIX})"), daten["subject"])
            self.assertIn("Projektakte:", daten["body"]["content"])
            self.assertEqual(daten["start"]["timeZone"], outlook_sync.ZEITZONE)
            marke = daten["singleValueExtendedProperties"][0]
            self.assertEqual(marke["id"], outlook_sync.PROPERTY_ID)
            bid = self.ids["m1"] if "m1%40" in pfad else self.ids["m2"]
            self.assertEqual(marke["value"], f"projekt:{tid}:{bid}")
        er = self.ereignisse("projekt", tid)
        self.assertEqual([(e.benutzer_id, e.stand) for e in er],
                         [(self.ids["m1"], "ok"), (self.ids["m2"], "ok")])
        self.assertTrue(all(e.event_id.startswith("EV-") for e in er))
        self.assertEqual(self.s.get(ProjektTermin, tid).outlook_event_id, er[0].event_id)
        status = outlook_sync.status_fuer(self.s, "projekt", tid)
        self.assertEqual((status["stand"], status["text"]), ("ok", "Outlook: ok (2 Kopien)"))
        self.assertEqual(self.s.query(OutlookAuftrag).filter_by(termin_art="projekt", termin_id=tid,
                                                                status="offen").count(), 0)

    def test_monteur_getauscht_eine_kopie_geloescht_eine_neu(self):
        t = self.termin_neu([self.m1, self.m2])
        tid = t.id
        self.senden(t)
        self.lauf_sync()
        ev_m2 = next(e.event_id for e in self.ereignisse("projekt", tid) if e.benutzer_id == self.ids["m2"])
        ev_m1 = next(e.event_id for e in self.ereignisse("projekt", tid) if e.benutzer_id == self.ids["m1"])
        t = self.s.get(ProjektTermin, tid)
        pj.besetzung_setzen(self.s, t, [self.ids["m1"], self.ids["m3"]], benutzer=self.pl)
        self.senden(t)
        self.assertEqual(sorted((a.aktion, a.benutzer_id) for a in self.offene("projekt", tid)),
                         sorted([("aendern", self.ids["m1"]), ("loeschen", self.ids["m2"]),
                                 ("anlegen", self.ids["m3"])]))
        ergebnis, aufrufe = self.lauf_sync()
        self.assertEqual(ergebnis["erledigt"], 3, ergebnis)
        methoden = {(a[0], a[1]) for a in aufrufe}
        self.assertIn(("DELETE", f"/users/{urllib.parse.quote(self.postfach['m2'])}/events/{ev_m2}"), methoden)
        self.assertIn(("PATCH", f"/users/{urllib.parse.quote(self.postfach['m1'])}/events/{ev_m1}"), methoden)
        self.assertIn(("POST", f"/users/{urllib.parse.quote(self.postfach['m3'])}/events"), methoden)
        staende = {e.benutzer_id: e.stand for e in self.ereignisse("projekt", tid)}
        self.assertEqual(staende, {self.ids["m1"]: "ok", self.ids["m2"]: "geloescht", self.ids["m3"]: "ok"})
        status = outlook_sync.status_fuer(self.s, "projekt", tid)
        self.assertEqual(status["stand"], "ok")
        self.assertEqual({k["name"] for k in status["kopien"]}, {self.m1.name, self.m3.name})

    def test_verschieben_im_tool_patcht_alle_kopien(self):
        t = self.termin_neu([self.m1, self.m2])
        tid = t.id
        self.senden(t)
        self.lauf_sync()
        t = self.s.get(ProjektTermin, tid)
        neu = t.beginn + timedelta(days=1)
        t.beginn, t.ende = neu, neu + timedelta(days=1)
        self.senden(t)
        self.assertEqual([a.aktion for a in self.offene("projekt", tid)], ["aendern", "aendern"])
        ergebnis, aufrufe = self.lauf_sync()
        self.assertEqual(ergebnis["erledigt"], 2, ergebnis)
        self.assertEqual([a[0] for a in aufrufe], ["PATCH", "PATCH"])
        for _, _, daten, pool in aufrufe:
            self.assertEqual(daten["start"]["dateTime"], neu.strftime("%Y-%m-%dT%H:%M:%S"))
            self.assertEqual(daten["end"]["dateTime"], (neu + timedelta(days=2)).strftime("%Y-%m-%dT%H:%M:%S"))
            self.assertEqual(pool, 0)
        self.assertTrue(all(e.beginn == neu for e in self.ereignisse("projekt", tid)))

    def test_event_loeschen_vor_termin_loeschen_entfernt_alle_kopien(self):
        t = self.termin_neu([self.m1, self.m2])
        tid = t.id
        self.senden(t)
        self.lauf_sync()
        ids = {e.event_id for e in self.ereignisse("projekt", tid)}
        t = self.s.get(ProjektTermin, tid)
        self.assertTrue(outlook_kalender.event_loeschen(self.s, t))
        ok, _meldung = pj.termin_loeschen(self.s, t, "Test – Termin entfällt", benutzer=self.pl)
        self.assertTrue(ok)
        self.s.commit()
        self.assertIsNone(self.s.get(ProjektTermin, tid))
        ergebnis, aufrufe = self.lauf_sync()
        self.assertEqual(ergebnis["erledigt"], 2, ergebnis)
        self.assertEqual([a[0] for a in aufrufe], ["DELETE", "DELETE"])
        self.assertEqual({a[1].rsplit("/", 1)[1] for a in aufrufe}, ids)
        # Termin weg → Ereigniszeilen entfernt (eine neu vergebene Termin-ID erbt nichts)
        self.assertEqual(self.ereignisse("projekt", tid), [])
        self.assertEqual({a.status for a in self.s.query(OutlookAuftrag)
                          .filter_by(termin_art="projekt", termin_id=tid)}, {"erledigt"})

    def test_auftrag_fuer_geloeschten_termin_gilt_als_erledigt(self):
        t = self.termin_neu([self.m1])
        tid = t.id
        self.senden(t)                                   # anlegen offen, noch nicht übertragen
        self.s.query(TerminBesetzung).filter_by(termin_id=tid).delete()
        self.s.delete(self.s.get(ProjektTermin, tid))
        self.s.commit()
        ergebnis, aufrufe = self.lauf_sync()
        self.assertEqual((ergebnis["erledigt"], ergebnis["fehler"], aufrufe), (1, 0, []))
        auftrag = self.s.query(OutlookAuftrag).filter_by(termin_art="projekt", termin_id=tid).one()
        self.assertEqual((auftrag.status, auftrag.fehler_text), ("erledigt", outlook_sync.TERMIN_WEG))
        self.assertEqual(self.ereignisse("projekt", tid), [])

    def test_drei_versuche_dann_fehler_und_protokoll(self):
        t = self.termin_neu([self.m1])
        tid = t.id
        self.senden(t)

        def kaputt(methode, pfad, token, daten=None):
            raise RuntimeError("Graph nicht erreichbar (Test)")
        with mock.patch("app.fehlerprotokoll.eintragen_text", return_value="F-1") as protokoll:
            for versuch in (1, 2, 3):
                ergebnis, _ = self.lauf_sync(kaputt)
                auftrag = self.s.query(OutlookAuftrag).filter_by(termin_art="projekt", termin_id=tid).one()
                self.assertEqual(auftrag.versuche, versuch)
                if versuch < 3:
                    self.assertEqual((auftrag.status, ergebnis["wiederholen"]), ("offen", 1))
                    self.assertEqual(outlook_sync.status_fuer(self.s, "projekt", tid)["stand"], "ausstehend")
        self.assertEqual((auftrag.status, ergebnis["fehler"]), ("fehler", 1))
        self.assertIn("Graph nicht erreichbar", auftrag.fehler_text)
        self.assertEqual(protokoll.call_count, 1)
        status = outlook_sync.status_fuer(self.s, "projekt", tid)
        self.assertEqual(status["stand"], "fehler")
        self.assertIn("Graph nicht erreichbar", status["text"])
        self.assertTrue(self.s.get(ProjektTermin, tid).outlook_fehler.startswith("Outlook-Sync fehlgeschlagen"))
        # erneutes Speichern reiht neu ein und setzt den Stand zurück
        t = self.s.get(ProjektTermin, tid)
        self.senden(t)
        self.assertEqual([a.aktion for a in self.offene("projekt", tid)], ["anlegen"])
        self.assertEqual(outlook_sync.status_fuer(self.s, "projekt", tid)["stand"], "ausstehend")
        self.assertEqual(t.outlook_fehler, "")

    def test_ohne_token_bleiben_auftraege_offen(self):
        t = self.termin_neu([self.m1])
        tid = t.id
        self.senden(t)
        self.entlasten()
        with mock.patch.object(graph_versand, "_token", return_value=None), \
                mock.patch.object(graph_versand, "_graph_aufruf",
                                  side_effect=AssertionError("Graph ohne Token aufgerufen")):
            ergebnis = outlook_sync.sync_lauf()
        self.assertTrue(ergebnis.get("ergebnis"), ergebnis)      # Zustandstext je Modus (G), kein Fehler
        self.assertEqual(ergebnis.get("offen"), 1)
        auftrag = self.s.query(OutlookAuftrag).filter_by(termin_art="projekt", termin_id=tid).one()
        self.assertEqual((auftrag.status, auftrag.versuche), ("offen", 0))

    def test_kein_graph_im_request(self):
        """event_senden/event_loeschen/termin_schreiben rufen Graph nie direkt auf."""
        t = self.termin_neu([self.m1])
        with mock.patch.object(graph_versand, "_token", side_effect=AssertionError("Token im Request")), \
                mock.patch.object(graph_versand, "_graph_aufruf", side_effect=AssertionError("Graph im Request")):
            self.assertEqual(outlook_kalender.event_senden(self.s, t), (True, ""))
            self.assertTrue(outlook_kalender.event_loeschen(self.s, t))
            kern.parameter_setzen(self.s, "kalender_sync", "an")
            vt = VotTermin(vorgang_id=self.ids["vorgang"], ad_id=self.ids["ad"],
                           beginn=datetime.now() + timedelta(days=3), status="geplant", typ="vot")
            self.s.add(vt)
            self.s.flush()
            self.assertTrue(kalender.termin_schreiben(self.s, vt, self.vorgang, self.kunde, self.ad))
            self.assertTrue(kalender.termin_aendern(self.s, vt, self.vorgang, self.kunde, self.ad))
            self.assertIsNotNone(kalender.frei_belegt(self.s, self.ad, datetime.now(),
                                                      datetime.now() + timedelta(days=7)))
        self.s.rollback()
        kern.parameter_setzen(self.s, "kalender_sync", "aus")
        self.s.commit()


    def test_service_ohne_projekt_betreff_und_link(self):
        """Vorschlag S (4.2): Service-Einsatz am Vorgang ohne Projekt (projekt_id 0 + vorgang_id)
        – Kunde/Ort über projektierung.termin_kunde/termin_adresse, Betreff
        „Service <Anlass>: <Kunde>, <PLZ Ort>“, Link in die Vorgangsakte, Kopie je Besetzung."""
        beginn = (datetime.now() + timedelta(days=6)).replace(hour=9, minute=0, second=0, microsecond=0)
        t = ProjektTermin(projekt_id=0, gewerk_id=None, typ="service", vorgang_id=self.ids["vorgang"],
                          service_gewerk="heizung", anlass="wartung", beginn=beginn,
                          ende=beginn + timedelta(hours=2), ganztaegig=False, dauer_tage=1,
                          erstellt_von=self.ids["pl"])
        self.s.add(t)
        self.s.flush()
        for modell in (OutlookAuftrag, OutlookEreignis):
            self.s.query(modell).filter_by(termin_art="projekt", termin_id=t.id).delete(
                synchronize_session=False)
        pj.besetzung_setzen(self.s, t, [self.ids["m1"]], benutzer=self.pl)
        self.s.commit()
        tid = t.id
        self.senden(t)
        ergebnis, aufrufe = self.lauf_sync()
        self.assertEqual((ergebnis["erledigt"], [a[0] for a in aufrufe]), (1, ["POST"]), ergebnis)
        daten = aufrufe[0][2]
        self.assertEqual(daten["subject"], f"Service Wartung: {self.kunde.anzeige_name}, 47139 Duisburg")
        self.assertIn(f"/vorgaenge/{self.ids['vorgang']}#termine", daten["body"]["content"])
        self.assertIn("Anlass: Wartung", daten["body"]["content"])
        self.assertIn("Adresse: Weg 1, 47139 Duisburg", daten["body"]["content"])
        self.assertFalse(daten["isAllDay"])
        self.assertEqual(daten["start"]["dateTime"], beginn.strftime("%Y-%m-%dT%H:%M:%S"))
        self.assertEqual(daten["end"]["dateTime"], (beginn + timedelta(hours=2)).strftime("%Y-%m-%dT%H:%M:%S"))
        self.assertEqual(daten["singleValueExtendedProperties"][0]["value"], f"projekt:{tid}:{self.ids['m1']}")
        self.assertEqual(outlook_sync.status_fuer(self.s, "projekt", tid)["stand"], "ok")


# --- Rücklesen: Lauf outlook-ruecklesen ---------------------------------------------------

class Ruecklesen(Basis):
    def test_verschieben_in_outlook_zieht_termin_nach_und_gleicht_zweite_kopie_an(self):
        t = self.termin_neu([self.m1, self.m3])
        tid, beginn = t.id, t.beginn
        self.senden(t)
        self.lauf_sync()
        ev = {e.benutzer_id: e.event_id for e in self.ereignisse("projekt", tid)}
        neu = beginn + timedelta(days=1)
        ergebnis, aufrufe = self.lauf_ruecklesen({
            self.postfach["m1"]: [self.ev(ev[self.ids["m1"]], neu, neu + timedelta(days=2), tid, self.ids["m1"])],
            self.postfach["m3"]: [self.ev(ev[self.ids["m3"]], beginn, beginn + timedelta(days=2), tid, self.ids["m3"])],
        })
        self.assertEqual((ergebnis["geaendert"], ergebnis["geloescht"], ergebnis["fehler"]), (1, 0, 0), ergebnis)
        self.assertEqual([a[0] for a in aufrufe], ["GET", "GET"])
        self.assertEqual([a[3] for a in aufrufe], [0, 0], "Pool-Verbindung während calendarView")
        for _, pfad, _, _ in aufrufe:
            self.assertIn("calendarView?startDateTime=", pfad)
            self.assertIn("$expand=singleValueExtendedProperties", pfad)
        t = self.s.get(ProjektTermin, tid)
        self.assertEqual((t.beginn, t.ende, t.dauer_tage), (neu, neu + timedelta(days=1), 2))
        self.assertTrue(any("aus Outlook übernommen von " + self.m1.name in z for z in self.verlauf_texte()),
                        self.verlauf_texte())
        offen = self.offene("projekt", tid)
        self.assertEqual({a.aktion for a in offen}, {"aendern"})
        self.assertIn(self.ids["m3"], {a.benutzer_id for a in offen})
        ergebnis, aufrufe = self.lauf_sync()
        patch_m3 = [a for a in aufrufe if a[0] == "PATCH" and a[1].endswith(ev[self.ids["m3"]])]
        self.assertEqual(len(patch_m3), 1, aufrufe)
        self.assertEqual(patch_m3[0][2]["start"]["dateTime"], neu.strftime("%Y-%m-%dT%H:%M:%S"))
        self.assertTrue(all(e.beginn == neu for e in self.ereignisse("projekt", tid)))

    def test_loeschen_in_outlook_markiert_termin_und_glocke(self):
        t = self.termin_neu([self.m1, self.m3])
        tid, beginn = t.id, t.beginn
        self.senden(t)
        self.lauf_sync()
        ev = {e.benutzer_id: e.event_id for e in self.ereignisse("projekt", tid)}
        vorher = self.s.query(Benachrichtigung).filter_by(benutzer_id=self.ids["pl"]).count()
        ergebnis, _ = self.lauf_ruecklesen({
            self.postfach["m1"]: [self.ev(ev[self.ids["m1"]], beginn, beginn + timedelta(days=2), tid, self.ids["m1"])],
            self.postfach["m3"]: [],
        })
        self.assertEqual((ergebnis["geaendert"], ergebnis["geloescht"]), (0, 1), ergebnis)
        staende = {e.benutzer_id: e.stand for e in self.ereignisse("projekt", tid)}
        self.assertEqual(staende, {self.ids["m1"]: "ok", self.ids["m3"]: "in_outlook_geloescht"})
        t = self.s.get(ProjektTermin, tid)
        self.assertEqual(t.outlook_fehler, "in Outlook gelöscht")
        self.assertEqual((t.beginn, t.ende), (beginn, beginn + timedelta(days=1)))   # kein stilles Löschen
        self.assertTrue(any("in Outlook" in z and self.m3.name in z for z in self.verlauf_texte()))
        glocken = (self.s.query(Benachrichtigung).filter_by(benutzer_id=self.ids["pl"])
                   .order_by(Benachrichtigung.id).all())
        self.assertEqual(len(glocken), vorher + 1)
        self.assertEqual(glocken[-1].art, "kommentar")
        self.assertIn("in Outlook", glocken[-1].text)
        self.assertIn(f"/projektierung/projekt/{self.ids['projekt']}", glocken[-1].link)
        status = outlook_sync.status_fuer(self.s, "projekt", tid)
        self.assertEqual(status["stand"], "in_outlook_geloescht")
        self.assertIn(self.m3.name, status["text"])
        # kein offener Auftrag, kein zweiter Hinweis beim nächsten Lauf
        self.assertEqual(self.offene("projekt", tid), [])
        ergebnis, _ = self.lauf_ruecklesen({self.postfach["m1"]: [
            self.ev(ev[self.ids["m1"]], beginn, beginn + timedelta(days=2), tid, self.ids["m1"])]})
        self.assertEqual(ergebnis["geloescht"], 0)
        self.assertEqual(self.s.query(Benachrichtigung).filter_by(benutzer_id=self.ids["pl"]).count(), vorher + 1)
        # erneutes Speichern legt die Kopie neu an
        self.senden(self.s.get(ProjektTermin, tid))
        self.assertEqual([(a.aktion, a.benutzer_id) for a in self.offene("projekt", tid)
                          if a.benutzer_id == self.ids["m3"]], [("anlegen", self.ids["m3"])])
        self.assertEqual(self.s.get(ProjektTermin, tid).outlook_fehler, "")
        ergebnis, aufrufe = self.lauf_sync()
        self.assertIn("POST", [a[0] for a in aufrufe])
        self.assertEqual(outlook_sync.status_fuer(self.s, "projekt", tid)["stand"], "ok")

    def test_fremder_termin_nur_belegtzeit_nie_veraendert(self):
        t = self.termin_neu([self.m1])
        tid, beginn = t.id, t.beginn
        self.senden(t)
        self.lauf_sync()
        ev_m1 = self.ereignisse("projekt", tid)[0].event_id
        fremd_von = beginn.replace(hour=8) - timedelta(days=1)
        fremd_bis = fremd_von + timedelta(hours=1)
        ergebnis, _ = self.lauf_ruecklesen({self.postfach["m1"]: [
            self.ev(ev_m1, beginn, beginn + timedelta(days=2), tid, self.ids["m1"]),
            self.ev("FREMD-TAIFUN", fremd_von, fremd_bis, all_day=False),
            self.ev("FREMD-FREI", fremd_von, fremd_bis, all_day=False, show_as="free"),
            self.ev("FREMD-ABGESAGT", fremd_von, fremd_bis, all_day=False, cancelled=True),
            self.ev("FREMD-MARKE", fremd_von, fremd_bis, all_day=False, tid=999999, bid=1),
        ]})
        self.assertEqual((ergebnis["belegt"], ergebnis["geaendert"], ergebnis["geloescht"]), (1, 0, 0), ergebnis)
        zeilen = self.s.query(OutlookBelegt).filter_by(benutzer_id=self.ids["m1"]).all()
        self.assertEqual([(z.von, z.bis, z.event_id) for z in zeilen],
                         [(lokal(fremd_von), lokal(fremd_bis), "FREMD-TAIFUN")])
        fenster = (beginn - timedelta(days=3), beginn + timedelta(days=3))
        self.assertEqual(outlook_sync.belegt(self.s, [self.ids["m1"]], *fenster),
                         {self.ids["m1"]: [(lokal(fremd_von), lokal(fremd_bis))]})
        self.assertEqual(outlook_sync.belegt(self.s, [self.ids["m2"]], *fenster), {self.ids["m2"]: []})
        self.assertEqual(self.s.query(OutlookEreignis).filter(OutlookEreignis.event_id.like("FREMD%")).count(), 0)
        # kalender.frei_belegt liest den Cache: nur bei kalender_sync = an, nie für HV ohne Postfach
        kern.parameter_setzen(self.s, "kalender_sync", "an")
        self.assertEqual(kalender.frei_belegt(self.s, self.m1, *fenster), [(lokal(fremd_von), lokal(fremd_bis))])
        self.assertEqual(kalender.frei_belegt(self.s, self.m2, *fenster), [])
        self.assertIsNone(kalender.frei_belegt(self.s, self.hv, *fenster))
        kern.parameter_setzen(self.s, "kalender_sync", "aus")
        self.assertIsNone(kalender.frei_belegt(self.s, self.m1, *fenster))
        self.s.commit()
        # zweiter Lauf ersetzt den Block je Person; fremde IDs werden nie geschrieben
        ergebnis, _ = self.lauf_ruecklesen({self.postfach["m1"]: [
            self.ev(ev_m1, beginn, beginn + timedelta(days=2), tid, self.ids["m1"])]})
        self.assertEqual(self.s.query(OutlookBelegt).filter_by(benutzer_id=self.ids["m1"]).count(), 0)
        ergebnis, aufrufe = self.lauf_sync()
        self.assertEqual([a for a in aufrufe if "FREMD" in a[1]], [])

    def test_403_liste_fuer_die_verbindungsseite(self):
        t = self.termin_neu([self.m1])
        tid = t.id
        self.senden(t)

        def verweigert(methode, pfad, token, daten=None):
            raise graph_versand.GraphZugriffVerweigert(graph_versand.postfach_aus_pfad(pfad), pfad)
        ergebnis, _ = self.lauf_ruecklesen({}, graph=verweigert)
        self.assertGreaterEqual(ergebnis["ohne_zugriff"], 1)
        liste = outlook_sync.postfaecher_ohne_zugriff(self.s)
        treffer = [z for z in liste if z["postfach"] == self.postfach["m1"]]
        self.assertEqual(len(treffer), 1, liste)
        self.assertEqual((treffer[0]["benutzer_id"], treffer[0]["name"]), (self.ids["m1"], self.m1.name))
        self.assertIsInstance(treffer[0]["zeit"], datetime)
        # Schreiben (Vertrag G): 403 → Auftrag sofort „fehler“ mit dem Postfach der Ausnahme,
        # ohne eigene Protokollzeile (graph_versand protokolliert einmal je Stunde)
        with mock.patch("app.fehlerprotokoll.eintragen_text", return_value="F-1") as protokoll:
            ergebnis, _ = self.lauf_sync(verweigert)
        auftrag = self.s.query(OutlookAuftrag).filter_by(termin_art="projekt", termin_id=tid).one()
        self.assertEqual((auftrag.status, auftrag.versuche, ergebnis["fehler"]), ("fehler", 1, 1))
        self.assertIn("nicht in der Zugriffsgruppe", auftrag.fehler_text)
        self.assertEqual(protokoll.call_count, 0)
        self.assertEqual(outlook_sync.status_fuer(self.s, "projekt", tid)["stand"], "fehler")
        # die Liste kommt auch ohne Speicherstand aus den Aufträgen (Neustart-fest)
        outlook_sync.ohne_zugriff_leeren()
        graph_versand.zugriff_verweigert_leeren()
        liste = [z for z in outlook_sync.postfaecher_ohne_zugriff(self.s) if z["postfach"] == self.postfach["m1"]]
        self.assertEqual([(z["benutzer_id"], z["name"]) for z in liste], [(self.ids["m1"], self.m1.name)])
        self.assertIsInstance(liste[0]["zeit"], datetime)
        # erneutes Speichern überholt den Fehler-Auftrag (kein Doppel), Erfolg nimmt das Postfach aus der Liste
        self.senden(self.s.get(ProjektTermin, tid))
        auftraege = (self.s.query(OutlookAuftrag).filter_by(termin_art="projekt", termin_id=tid)
                     .order_by(OutlookAuftrag.id).all())
        self.assertEqual([(a.status, a.aktion) for a in auftraege], [("erledigt", "anlegen"), ("offen", "anlegen")])
        self.assertIn("überholt", auftraege[0].fehler_text)
        ergebnis, aufrufe = self.lauf_sync()
        self.assertEqual((ergebnis["erledigt"], [a[0] for a in aufrufe]), (1, ["POST"]))
        self.assertEqual([z for z in outlook_sync.postfaecher_ohne_zugriff(self.s)
                          if z["postfach"] == self.postfach["m1"]], [])
        # stündliche Wiederholung: nach Aufnahme in die Gruppe läuft der Auftrag ohne neues Speichern durch
        t2 = self.termin_neu([self.m3], tage=9)
        tid2 = t2.id
        self.senden(t2)
        self.lauf_sync(verweigert)
        auftrag = self.s.query(OutlookAuftrag).filter_by(termin_art="projekt", termin_id=tid2).one()
        self.assertEqual(auftrag.status, "fehler")
        ergebnis, aufrufe = self.lauf_sync()                     # noch keine Stunde vergangen
        self.assertEqual((ergebnis["offen"], aufrufe), (0, []))
        auftrag.erledigt_am = datetime.now() - timedelta(hours=2)
        self.s.commit()
        ergebnis, aufrufe = self.lauf_sync()
        self.assertEqual((ergebnis["erledigt"], [a[0] for a in aufrufe]), (1, ["POST"]))
        self.assertEqual(outlook_sync.status_fuer(self.s, "projekt", tid2)["stand"], "ok")
        self.assertEqual(self.s.query(OutlookAuftrag).filter_by(termin_art="projekt", termin_id=tid2).count(), 1)


# --- VOT: Demo → Testpostfach, HV ohne Postfach --------------------------------------------

class Vot(Basis):
    def vot(self, ad, demo=False, tage=3):
        beginn = (datetime.now() + timedelta(days=tage)).replace(hour=10, minute=0, second=0, microsecond=0)
        vt = VotTermin(vorgang_id=self.ids["vorgang"], ad_id=ad.id, beginn=beginn,
                       ende=beginn + timedelta(minutes=90), status="geplant", typ="vot",
                       adresse="Weg 1, 47139 Duisburg", demo=demo)
        self.s.add(vt)
        self.s.flush()
        return vt

    def test_vot_demo_ins_testpostfach(self):
        kern.parameter_setzen(self.s, "kalender_sync", "an")
        kern.parameter_setzen(self.s, "kalender_testpostfach", "")
        vt = self.vot(self.ad, demo=True)
        self.assertFalse(kalender.termin_schreiben(self.s, vt, self.vorgang, self.kunde, self.ad))
        self.assertIn("Testpostfach fehlt", outlook_sync.status_fuer(self.s, "vot", vt.id)["text"])
        self.assertEqual(self.offene("vot", vt.id), [])
        kern.parameter_setzen(self.s, "kalender_testpostfach", self.postfach["test"])
        self.assertTrue(kalender.termin_schreiben(self.s, vt, self.vorgang, self.kunde, self.ad))
        self.s.commit()
        vid = vt.id
        auftraege = self.offene("vot", vid)
        self.assertEqual([(a.aktion, a.postfach, a.benutzer_id) for a in auftraege],
                         [("anlegen", self.postfach["test"], self.ids["ad"])])
        ergebnis, aufrufe = self.lauf_sync()
        self.assertEqual(ergebnis["erledigt"], 1, ergebnis)
        methode, pfad, daten, pool = aufrufe[0]
        self.assertEqual((methode, pfad, pool), ("POST", f"/users/{urllib.parse.quote(self.postfach['test'])}/events", 0))
        self.assertTrue(daten["subject"].startswith("VOT"), daten["subject"])
        self.assertIn(f"{PRAEFIX} Kunde", daten["subject"])
        self.assertTrue(daten["subject"].endswith("(K-33)"), daten["subject"])
        self.assertFalse(daten["isAllDay"])
        self.assertEqual(daten["singleValueExtendedProperties"][0]["value"], f"vot:{vid}:{self.ids['ad']}")
        self.assertIn("Lead-Akte:", daten["body"]["content"])
        vt = self.s.get(VotTermin, vid)
        self.assertTrue(vt.outlook_event_id.startswith(self.postfach["test"] + "|EV-"))
        # Absage → Auftrag loeschen → DELETE, Spiegel leer
        self.assertTrue(kalender.termin_loeschen(self.s, vt))
        self.s.commit()
        ergebnis, aufrufe = self.lauf_sync()
        self.assertEqual([a[0] for a in aufrufe], ["DELETE"])
        self.assertEqual({e.stand for e in self.ereignisse("vot", vid)}, {"geloescht"})
        self.assertIsNone(self.s.get(VotTermin, vid).outlook_event_id)
        kern.parameter_setzen(self.s, "kalender_testpostfach", "")
        kern.parameter_setzen(self.s, "kalender_sync", "aus")
        self.s.commit()

    def test_hv_ohne_postfach_kein_auftrag_mit_hinweis(self):
        kern.parameter_setzen(self.s, "kalender_sync", "an")
        vt = self.vot(self.hv)
        self.assertFalse(kalender.termin_schreiben(self.s, vt, self.vorgang, self.kunde, self.hv))
        self.assertEqual(self.offene("vot", vt.id), [])
        status = outlook_sync.status_fuer(self.s, "vot", vt.id)
        self.assertEqual((status["stand"], status["text"]), ("leer", outlook_sync.HV_OHNE_POSTFACH))
        self.assertEqual([(k["stand"], k["fehler"]) for k in status["kopien"]],
                         [("leer", outlook_sync.HV_OHNE_POSTFACH)])
        self.assertEqual(outlook_sync.hinweis_person(self.s, self.ids["hv"]), outlook_sync.HV_OHNE_POSTFACH)
        self.assertEqual(outlook_sync.hinweis_person(self.s, self.ids["ad"]), "")
        self.assertFalse(kalender.termin_loeschen(self.s, vt))
        # mit Friondo-Postfach im AD-Profil (rollen.hv_spiegeln hat es angelegt) bekommt der HV eine Kopie
        profil = self.s.query(AdProfil).filter_by(benutzer_id=self.ids["hv"]).first()
        if profil is None:
            profil = AdProfil(benutzer_id=self.ids["hv"], terminiert_selbst=True)
            self.s.add(profil)
        profil.kalender_postfach = f"hv@{DOMAIN}"
        self.s.flush()
        vt2 = self.vot(self.hv, tage=4)
        self.assertTrue(kalender.termin_schreiben(self.s, vt2, self.vorgang, self.kunde, self.hv))
        self.assertEqual([a.postfach for a in self.offene("vot", vt2.id)], [f"hv@{DOMAIN}"])
        self.s.rollback()
        kern.parameter_setzen(self.s, "kalender_sync", "aus")
        self.s.commit()

    def test_kalender_sync_aus_kein_vot_auftrag(self):
        kern.parameter_setzen(self.s, "kalender_sync", "aus")
        vt = self.vot(self.ad)
        self.assertFalse(kalender.termin_schreiben(self.s, vt, self.vorgang, self.kunde, self.ad))
        self.assertEqual(self.offene("vot", vt.id), [])
        self.s.rollback()


# --- Läufe, Migration, Makro, Seiten --------------------------------------------------------

class Rahmen(Basis):
    def test_laeufe_registriert_und_pool_invariante(self):
        from app import (ablauf_pruefung, benachrichtigungen, betrieb, geocoding, lead_mail,
                         lead_mail_abruf, lead_parser, mail_sync, monday_sync)
        scheduler.zuruecksetzen_fuer_tests()
        try:
            outlook_sync.scheduler_starten()
            laeufe = {l.name: l for l in scheduler.alle()}
            self.assertEqual(set(laeufe), {"outlook-sync", "outlook-ruecklesen"})
            self.assertEqual((laeufe["outlook-sync"].intervall_s, laeufe["outlook-sync"].start_verzoegerung_s), (60, 60))
            self.assertEqual((laeufe["outlook-ruecklesen"].intervall_s,
                              laeufe["outlook-ruecklesen"].start_verzoegerung_s), (300, 330))
            self.assertTrue(all(l.beschreibung for l in laeufe.values()))
            with mock.patch.object(config, "GRAPH_CLIENT_ID", ""):
                self.assertEqual(laeufe["outlook-sync"].ist_aktiv(), (False, "Graph nicht eingerichtet"))
            with mock.patch.object(config, "GRAPH_CLIENT_ID", "test-id"):
                self.assertEqual(laeufe["outlook-ruecklesen"].ist_aktiv(), (True, ""))
                self.entlasten()
                with mock.patch.object(graph_versand, "_token", return_value="tok"), \
                        mock.patch.object(graph_versand, "_graph_aufruf", return_value={"value": []}):
                    ergebnis = scheduler.jetzt_ausfuehren("outlook-ruecklesen")
            self.assertTrue(ergebnis["ok"], ergebnis)
            # Pool-Invariante mit 16 Läufen (14 bisherige + 2 neue): 64 + 16 + 5 = 85 ≤ 90
            ok, text = db.pool_invariante(16)
            self.assertTrue(ok, text)
            self.assertIn("Scheduler 16", text)
        finally:
            scheduler.zuruecksetzen_fuer_tests()
            for modul in (monday_sync, mail_sync, ablauf_pruefung, benachrichtigungen, lead_parser,
                          kern, geocoding, lead_mail, lead_mail_abruf, outlook_sync):
                modul.scheduler_starten()
            betrieb.scheduler_registrieren()

    def test_ruecklesen_alt_ruft_neuen_lauf(self):
        self.entlasten()
        with mock.patch.object(outlook_sync, "ruecklesen_lauf", return_value={"geaendert": 2, "fehler": 0}) as lauf:
            self.assertEqual(outlook_kalender.ruecklesen(), 2)
        self.assertEqual(lauf.call_count, 1)
        self.assertEqual(outlook_kalender.status["geaendert"], 2)

    def test_migration_spiegelt_altbestand_zweimal(self):
        team = self.s.get(Team, self.ids["team"])
        team.outlook_adresse = f"team@{DOMAIN}"
        alt_modus = pj.parameter_holen(self.s, "outlook_kalender_modus", "")
        pj.parameter_setzen(self.s, "outlook_kalender_modus", "postfach")
        t = self.termin_neu([self.m1])
        tid = t.id
        t.outlook_event_id = "ALT-PROJEKT-1"
        beginn = (datetime.now() + timedelta(days=5)).replace(hour=9, minute=0, second=0, microsecond=0)
        vt = VotTermin(vorgang_id=self.ids["vorgang"], ad_id=self.ids["ad"], beginn=beginn,
                       ende=beginn + timedelta(hours=1), status="geplant", typ="vot",
                       outlook_event_id=f"{self.postfach['ad']}|ALT-VOT-1")
        self.s.add(vt)
        self.s.commit()
        vid = vt.id
        vorher = self.s.query(OutlookEreignis).count()
        try:
            meldungen = outlook_sync.migration_v33_outlook(self.s)
            self.s.commit()
            self.assertEqual(len(meldungen), 1, meldungen)
            self.assertIn("1 VOT-Termine, 1 Projekt-Termine", meldungen[0])
            self.assertEqual(self.s.query(OutlookEreignis).count(), vorher + 2)
            p = self.ereignisse("projekt", tid)
            self.assertEqual([(e.benutzer_id, e.postfach, e.event_id, e.stand) for e in p],
                             [(0, f"team@{DOMAIN}", "ALT-PROJEKT-1", "ok")])
            v = self.ereignisse("vot", vid)
            self.assertEqual([(e.benutzer_id, e.postfach, e.event_id, e.stand) for e in v],
                             [(self.ids["ad"], self.postfach["ad"], "ALT-VOT-1", "ok")])
            self.assertEqual(outlook_sync.migration_v33_outlook(self.s), [])
            self.s.commit()
            self.assertEqual(self.s.query(OutlookEreignis).count(), vorher + 2)
            # Rücklesen kennt den Altbestand: Team-Kalender wird gelesen, VOT-Kopie der Person;
            # beide Kopien sind in Outlook unverändert vorhanden → nichts geändert/gelöscht
            t_beginn = self.s.get(ProjektTermin, tid).beginn
            vot_utc = beginn.astimezone(timezone.utc).replace(tzinfo=None)
            ergebnis, aufrufe = self.lauf_ruecklesen({
                f"team@{DOMAIN}": [self.ev("ALT-PROJEKT-1", t_beginn, t_beginn + timedelta(days=2), tid, 0)],
                self.postfach["ad"]: [self.ev("ALT-VOT-1", vot_utc, vot_utc + timedelta(hours=1), vid,
                                              self.ids["ad"], all_day=False, art="vot")],
            })
            self.assertEqual((ergebnis["geaendert"], ergebnis["geloescht"]), (0, 0), ergebnis)
            pfade = " ".join(a[1] for a in aufrufe)
            self.assertIn(urllib.parse.quote(f"team@{DOMAIN}"), pfade)
            self.assertIn(urllib.parse.quote(self.postfach["ad"]), pfade)
            self.assertEqual({e.stand for e in self.ereignisse("projekt", tid)}, {"ok"})
            self.assertEqual({e.stand for e in self.ereignisse("vot", vid)}, {"ok"})
            # Löschen des alten Projekt-Termins storniert die Team-Kopie
            self.senden(self.s.get(ProjektTermin, tid))
            self.assertTrue(outlook_kalender.event_loeschen(self.s, self.s.get(ProjektTermin, tid)))
            self.s.commit()
            loeschen = [a for a in self.offene("projekt", tid) if a.aktion == "loeschen"]
            self.assertEqual([(a.postfach, a.event_id) for a in loeschen], [(f"team@{DOMAIN}", "ALT-PROJEKT-1")])
        finally:
            self.s.rollback()
            team = self.s.get(Team, self.ids["team"])
            team.outlook_adresse = ""
            pj.parameter_setzen(self.s, "outlook_kalender_modus", alt_modus or "postfach")
            self.s.commit()

    def test_makro_outlook_status(self):
        from app.templating import templates
        vorlage = templates.env.from_string(
            '{% from "_outlook_status.html" import outlook_status, outlook_status_zeile %}'
            '{{ outlook_status("ok") }}|{{ outlook_status_zeile({"stand": "fehler", "text": "Outlook: Fehler – x",'
            ' "kopien": [{"name": "Anna", "stand": "fehler", "fehler": "x"}]}) }}|{{ outlook_status("unbekannt") }}'
            '|{{ outlook_status("in_outlook_geloescht") }}|{{ outlook_status_zeile(none) }}')
        html = vorlage.render()
        teile = html.split("|")
        self.assertIn('os-ok', teile[0])
        self.assertIn('Outlook: ok', teile[0])
        self.assertIn('data-outlook-stand="ok"', teile[0])
        self.assertIn('os-fehler', teile[1])
        self.assertIn('Anna: Fehler (x)', teile[1])
        self.assertIn('os-leer', teile[2])
        self.assertIn('in Outlook gelöscht', teile[3])
        self.assertIn('os-leer', teile[4])
        self.assertNotIn('#', html.split('title=')[0])     # keine Hex-Farben im Makro

    def test_seiten_zeigen_outlook_stand(self):
        admin = TestClient(app, follow_redirects=False)
        admin.cookies.set(auth.COOKIE_NAME, auth.cookie_wert(1))
        t = self.termin_neu([self.m1])
        tid = t.id
        start = t.beginn
        self.senden(t)
        self.lauf_sync()
        r = admin.get(f"/projektierung/termine?start={start:%Y-%m-%d}")
        self.assertEqual(r.status_code, 200, r.text[:300])
        self.assertIn('outlook-status os-ok', r.text)
        self.assertIn(f'id="termin-{tid}"' if f'id="termin-{tid}"' in r.text else 'Outlook: ok', r.text)
        # Meine Termine des Außendienstes: Kopie im eigenen Kalender „ausstehend“
        kern.parameter_setzen(self.s, "kalender_sync", "an")
        beginn = datetime.now().replace(hour=23, minute=30, second=0, microsecond=0)
        vt = VotTermin(vorgang_id=self.ids["vorgang"], ad_id=self.ids["ad"], beginn=beginn,
                       ende=beginn + timedelta(minutes=20), status="geplant", typ="vot",
                       adresse="Weg 1, 47139 Duisburg")
        self.s.add(vt)
        self.s.flush()
        self.assertTrue(kalender.termin_schreiben(self.s, vt, self.vorgang, self.kunde, self.ad))
        self.s.commit()
        ad_client = TestClient(app, follow_redirects=False)
        ad_client.cookies.set(auth.COOKIE_NAME, auth.cookie_wert(self.ids["ad"]))
        r = ad_client.get("/lead-management/meine-termine")
        self.assertEqual(r.status_code, 200, r.text[:300])
        self.assertIn('data-rolle="outlook-stand"', r.text)
        self.assertIn("Outlook: ausstehend", r.text)
        # Deals-Board: Fußzeile mit dem Sync-Stand
        r = admin.get("/lead-management/terminiert")
        self.assertEqual(r.status_code, 200, r.text[:300])
        self.assertIn('data-rolle="outlook-zusammenfassung"', r.text)
        self.assertIn("Outlook-Sync je Mitarbeiter", r.text)
        kern.parameter_setzen(self.s, "kalender_sync", "aus")
        self.s.commit()


if __name__ == "__main__":
    unittest.main()
