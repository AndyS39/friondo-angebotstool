# v30 (PLAN_V18 Phase 151): „Projekt löschen“ (nur Admin) in Projektakte und
# Projektliste (Mehrfachauswahl), Demo-Kennzeichen/-Filter, Lösch-Protokoll.
# Testdaten mit Präfix „V30P“ (Kunden-E-Mail v30p-loeschen@test.local, Projekt-
# nummern PR-V30P…, damit die Ordner unter data/projekte/ keinem anderen Testlauf
# gehören); Anmeldung über das signierte Cookie (auth.cookie_wert); Outlook-Storno
# über gemockte Graph-Nahtstelle (kein Netz). Aufräumen inkl. Ordner _geloescht.
import shutil
import unittest
import warnings
from datetime import datetime, timedelta
from unittest import mock

warnings.filterwarnings("ignore")

from fastapi.testclient import TestClient

from app import angebot_aufbau, auth, config
from app import projektierung as kern
from app import vorgaenge as vorgaenge_modul
from app.db import SessionLocal, init_db
from app.main import app
from app.models import (Angebot, AngebotsLoeschung, AngebotsPosition, Aufgabe,
                        AufgabenpaketInstanz, Benachrichtigung, Benutzer, Erfassung,
                        GalerieDatei, Gewerk, Kunde, MontageFormular, Projekt,
                        ProjektDokument, ProjektMail, ProjektSub, ProjektTermin,
                        ProjektVerlauf, Restarbeit, SteckbriefWert, Team, TeamMitglied,
                        TerminBesetzung, UglBestellung, Vorgang, VorgangNotizGelesen,
                        VorgangsNotiz, angebot_status_setzen)

TEST_EMAIL = "v30p-loeschen@test.local"
PRAEFIX = "V30P"
NUMMER_PRAEFIX = "PR-V30P"
PROJEKTE = config.DATA_ORDNER / "projekte"


def aufraeumen(s):
    """Alles mit Präfix V30P entfernen (idempotent) – DB-Zeilen und Ordner."""
    for k in s.query(Kunde).filter(Kunde.email == TEST_EMAIL):
        for p in s.query(Projekt).filter_by(kunde_id=k.id):
            for g in s.query(Gewerk).filter_by(projekt_id=p.id):
                for modell in (Aufgabe, AufgabenpaketInstanz, SteckbriefWert,
                               MontageFormular, Restarbeit, UglBestellung):
                    s.query(modell).filter_by(gewerk_id=g.id).delete()
                s.delete(g)
            for t in s.query(ProjektTermin).filter_by(projekt_id=p.id):
                s.query(TerminBesetzung).filter_by(termin_id=t.id).delete()
                s.delete(t)
            for modell in (ProjektVerlauf, ProjektDokument, ProjektSub, ProjektMail):
                s.query(modell).filter_by(projekt_id=p.id).delete()
            s.query(Benachrichtigung).filter(
                Benachrichtigung.link.like(f"/projektierung/projekt/{p.id}%")).delete(
                synchronize_session=False)
            s.delete(p)
        for a in s.query(Angebot).filter_by(kunde_id=k.id):
            s.delete(a)
        for e in s.query(Erfassung).filter_by(kunde_id=k.id):
            s.delete(e)
        for v in s.query(Vorgang).filter_by(kunde_id=k.id):
            for d in s.query(GalerieDatei).filter_by(vorgang_id=v.id):
                (config.DATA_ORDNER / d.pfad).unlink(missing_ok=True)
                s.delete(d)
            s.query(VorgangsNotiz).filter_by(vorgang_id=v.id).delete()
            s.query(VorgangNotizGelesen).filter_by(vorgang_id=v.id).delete()
            s.delete(v)
        s.delete(k)
    s.query(AngebotsLoeschung).filter(
        AngebotsLoeschung.nummer.like(NUMMER_PRAEFIX + "%")).delete(synchronize_session=False)
    for te in s.query(Team).filter(Team.name.like(f"{PRAEFIX}%")):
        s.query(TeamMitglied).filter_by(team_id=te.id).delete()
        s.delete(te)
    for b in s.query(Benutzer).filter(Benutzer.name.like(f"{PRAEFIX}%")):
        s.query(TerminBesetzung).filter_by(benutzer_id=b.id).delete()
        s.query(TeamMitglied).filter_by(benutzer_id=b.id).delete()
        s.query(Benachrichtigung).filter_by(benutzer_id=b.id).delete()
        s.delete(b)
    s.commit()
    # Ordner der Testprojekte (aktiv und verschoben)
    for basis in (PROJEKTE, PROJEKTE / kern.GELOESCHT_ORDNER):
        if basis.exists():
            for ordner in basis.glob(NUMMER_PRAEFIX + "*"):
                shutil.rmtree(ordner, ignore_errors=True)


def client_fuer(benutzer_id: int) -> TestClient:
    c = TestClient(app)
    c.cookies.set(auth.COOKIE_NAME, auth.cookie_wert(benutzer_id))
    return c


class Basis(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        init_db()
        cls.s = SessionLocal()
        aufraeumen(cls.s)
        cls.admin = client_fuer(1)
        cls.innendienst = Benutzer(name=f"{PRAEFIX} Innendienst", rolle="innendienst",
                                   rollen="innendienst", aktiv=True,
                                   pin_hash=auth.pin_hash("1234"),
                                   email="v30p-id@p.test")
        cls.s.add(cls.innendienst)
        cls.s.commit()
        cls.id_client = client_fuer(cls.innendienst.id)

    @classmethod
    def tearDownClass(cls):
        aufraeumen(cls.s)
        cls.s.close()

    def setUp(self):
        # Identity-Map leeren: Objekte, die ein Test über die Routen gelöscht hat,
        # dürfen in der Testsitzung nicht nachgeladen werden (ObjectDeletedError)
        self.s.expunge_all()

    # --- Stammdaten --------------------------------------------------------------
    def projekt_neu(self, nachname: str = "V30P Echt", sparten=("WP",),
                    phase: str = "planung") -> Projekt:
        """Kunde + Vorgang + je Sparte ein angenommenes Angebot + Projekt mit Gewerk
        je Sparte; Projektnummer PR-V30P<id> (eigener Ordner unter data/projekte/)."""
        kunde = Kunde(anrede="Herr", vorname="Paul", nachname=nachname,
                      strasse="Teststr. 5", plz="47139", ort="Duisburg",
                      email=TEST_EMAIL, telefon="0203 1")
        self.s.add(kunde)
        self.s.flush()
        angebote = []
        for sparte in sparten:
            angebot = angebot_aufbau.angebot_anlegen(self.s, kunde.id, sparte=sparte)
            angebot.positionen.append(AngebotsPosition(
                sort=1, pos_nr="047", bezeichnung="Pos 047", beschreibung="Pos 047",
                menge=1, e_preis_cent=10000))
            angebot_status_setzen(angebot, "Angenommen")
            self.s.commit()
            if not angebot.vorgang_id:
                vorgang = vorgaenge_modul.vorgang_fuer_angebot(self.s, angebot)
                angebot.vorgang_id = vorgang.id
                self.s.commit()
            angebote.append(angebot)
        projekt = kern.projekt_anlegen(self.s, angebote[0], projektleiter_id=1)
        projekt.nummer = f"{NUMMER_PRAEFIX}{projekt.id:04d}"
        self.s.commit()
        for angebot, sparte in zip(angebote, sparten):
            gewerk = kern.gewerk_anlegen(self.s, projekt, angebot, sparte)
            gewerk.phase = phase
        kern.projektstatus_berechnen(self.s, projekt)
        self.s.commit()
        return projekt

    def gewerke_von(self, projekt: Projekt) -> list[Gewerk]:
        return (self.s.query(Gewerk).filter_by(projekt_id=projekt.id)
                .order_by(Gewerk.id).all())

    def termin_neu(self, gewerk: Gewerk, team: Team | None = None,
                   outlook_id: str = "", besetzung=()) -> ProjektTermin:
        beginn = (datetime.now() + timedelta(days=7)).replace(hour=7, minute=30,
                                                              second=0, microsecond=0)
        t = ProjektTermin(gewerk_id=gewerk.id, projekt_id=gewerk.projekt_id, typ="montage",
                          beginn=beginn, ende=beginn + timedelta(days=1),
                          team_id=team.id if team else None, kunde_bestaetigt=True,
                          zweck="wp", outlook_event_id=outlook_id)
        self.s.add(t)
        self.s.flush()
        for b in besetzung:
            self.s.add(TerminBesetzung(termin_id=t.id, benutzer_id=b.id))
        self.s.commit()
        return t

    def anzahl(self, modell, **filter_) -> int:
        return self.s.query(modell).filter_by(**filter_).count()

    def projekt_existiert(self, projekt_id: int) -> bool:
        """Abfrage statt session.get – das gelöschte Objekt liegt noch in der
        Identity-Map der Testsitzung (ObjectDeletedError beim Nachladen)."""
        return self.s.query(Projekt.id).filter_by(id=projekt_id).first() is not None

    @staticmethod
    def tabelle(html: str) -> str:
        """Nur der Tabellenkörper der Liste (ohne Glocke/Menü im Seitenkopf)."""
        return html.split("<tbody>", 1)[1].split("</tbody>", 1)[0] if "<tbody>" in html else ""


class ProjektLoeschenAkte(Basis):
    """Checkbox 1 + Tests laut Plan: Admin löscht Projekt mit zwei Gewerken."""

    def test_admin_loescht_projekt_mit_zwei_gewerken(self):
        projekt = self.projekt_neu(sparten=("WP", "PV"))
        pid, nummer, vorgang_id = projekt.id, projekt.nummer, projekt.vorgang_id
        gewerke = self.gewerke_von(projekt)
        self.assertEqual(len(gewerke), 2)
        angebot_ids = [g.angebot_id for g in gewerke]
        gewerk_ids = [g.id for g in gewerke]
        auftragswert = sum(g.auftragswert_aktuell for g in gewerke)   # WP 19 % + PV 0 % USt
        self.assertGreater(auftragswert, 0)
        # Team mit Outlook-Adresse, Monteur, zwei Termine (einer in Outlook) + Besetzung
        monteur = Benutzer(name=f"{PRAEFIX} Monteur", rolle="montage", aktiv=True,
                           pin_hash=auth.pin_hash("4711"))
        self.s.add(monteur)
        self.s.flush()
        team = Team(name=f"{PRAEFIX} Team", typ="montage", aktiv=True,
                    outlook_adresse="montage-v30p@friondo.test")
        self.s.add(team)
        self.s.flush()
        self.s.add(TeamMitglied(team_id=team.id, benutzer_id=monteur.id))
        self.s.commit()
        t1 = self.termin_neu(gewerke[0], team, outlook_id="AAMk-v30p-1", besetzung=[monteur])
        t2 = self.termin_neu(gewerke[1], team, besetzung=[monteur])
        termin_ids = [t1.id, t2.id]
        # weitere Projektdaten: Steckbrief, Verlauf, Dokument + Ordner mit Datei,
        # Benachrichtigung mit Link auf die Akte, Sub, Restarbeit, Formular-Entwurf
        self.s.add(SteckbriefWert(gewerk_id=gewerk_ids[0], feld="hersteller", wert="Bosch"))
        self.s.add(ProjektSub(projekt_id=pid, gewerk_id=gewerk_ids[0], sub_id=0,
                              leistung="Erdarbeiten"))
        self.s.add(Restarbeit(projekt_id=pid, gewerk_id=gewerk_ids[0], text="Nacharbeit"))
        self.s.add(MontageFormular(projekt_id=pid, gewerk_id=gewerk_ids[0],
                                   formular="montagebericht", status="entwurf"))
        self.s.add(Benachrichtigung(benutzer_id=1, text="V30P Test",
                                    link=f"/projektierung/projekt/{pid}#subs", art="aufgabe"))
        ordner = kern.projekt_ordner(projekt)
        ordner.mkdir(parents=True, exist_ok=True)
        datei = ordner / "06 Rechnungen" / "v30p-test.txt"
        datei.parent.mkdir(parents=True, exist_ok=True)
        datei.write_text("Testdatei", encoding="utf-8")
        self.s.add(ProjektDokument(projekt_id=pid, gewerk_id=gewerk_ids[0],
                                   ordner="06 Rechnungen", dateiname=datei.name,
                                   pfad=str(datei)))
        self.s.commit()
        self.assertGreater(self.anzahl(Aufgabe, projekt_id=pid), 0)
        self.assertGreater(self.anzahl(ProjektVerlauf, projekt_id=pid), 0)
        # (>= 1: ältere Testläufe hinterlassen verwaiste Besetzungszeilen zu
        # wiederverwendeten Termin-IDs – die räumt das Löschen gleich mit ab)
        self.assertGreaterEqual(self.anzahl(TerminBesetzung, termin_id=t1.id), 1)

        aufrufe = []

        def graph(methode, pfad, token, daten=None, *a, **kw):
            aufrufe.append((methode, pfad))
            return {}

        vorher_geloescht = (PROJEKTE / kern.GELOESCHT_ORDNER)
        with mock.patch("app.graph_versand._token", return_value="tok"), \
                mock.patch("app.graph_versand._graph_aufruf", side_effect=graph):
            antwort = self.admin.post(f"/projektierung/projekt/{pid}/loeschen",
                                      data={"grund": "Testprojekt der Pilotphase",
                                            "nummer": nummer},
                                      follow_redirects=False)
        self.assertEqual(antwort.status_code, 303, antwort.text[:300])
        self.assertTrue(antwort.headers["location"].startswith("/projektierung/liste?meldung="))
        self.assertIn("gel%C3%B6scht", antwort.headers["location"])
        # Outlook-Storno genau für den Termin mit Ereignis (DELETE am Team-Postfach)
        self.assertEqual(len(aufrufe), 1)
        self.assertEqual(aufrufe[0][0], "DELETE")
        self.assertIn("AAMk-v30p-1", aufrufe[0][1])
        self.assertIn("montage-v30p%40friondo.test", aufrufe[0][1])
        self.s.expunge_all()
        # keine Zeilen mehr in Projekt/Gewerk/Aufgaben/Termine/Besetzung …
        self.assertIsNone(self.s.get(Projekt, pid))
        self.assertEqual(self.s.query(Gewerk).filter(Gewerk.id.in_(gewerk_ids)).count(), 0)
        for modell in (Aufgabe, ProjektVerlauf, ProjektDokument, ProjektSub, ProjektTermin):
            self.assertEqual(self.anzahl(modell, projekt_id=pid), 0, modell.__name__)
        self.assertEqual(self.s.query(TerminBesetzung)
                         .filter(TerminBesetzung.termin_id.in_(termin_ids)).count(), 0)
        for modell in (AufgabenpaketInstanz, SteckbriefWert, Restarbeit, MontageFormular):
            self.assertEqual(self.s.query(modell)
                             .filter(modell.gewerk_id.in_(gewerk_ids)).count(), 0,
                             modell.__name__)
        self.assertEqual(self.s.query(Benachrichtigung)
                         .filter(Benachrichtigung.link.like(f"/projektierung/projekt/{pid}%"))
                         .count(), 0)
        # Angebote: Status „Angenommen“, Verknüpfung leer
        for aid in angebot_ids:
            angebot = self.s.get(Angebot, aid)
            self.assertEqual(angebot.status, "Angenommen")
            self.assertIsNone(angebot.projekt_gewerk_id)
        # Ordner verschoben nach _geloescht/<PR>_<JJJJMMTT-HHMM>/ – mit Inhalt
        self.assertFalse(ordner.exists())
        verschoben = sorted(vorher_geloescht.glob(nummer + "_*"))
        self.assertEqual(len(verschoben), 1, verschoben)
        self.assertRegex(verschoben[0].name, rf"^{nummer}_\d{{8}}-\d{{4}}(-\d+)?$")
        self.assertTrue((verschoben[0] / "06 Rechnungen" / "v30p-test.txt").exists())
        # Lösch-Protokoll mit Art/Grund, Vorgangsnotiz im Chat
        eintrag = (self.s.query(AngebotsLoeschung)
                   .filter(AngebotsLoeschung.nummer == nummer).one())
        self.assertEqual(eintrag.art, "projekt")
        self.assertEqual(eintrag.grund, "Testprojekt der Pilotphase")
        self.assertEqual(eintrag.benutzer_name, self.s.get(Benutzer, 1).name)
        self.assertEqual(eintrag.status_vorher, "Planung")
        self.assertEqual(eintrag.endbetrag_cent, auftragswert)
        self.assertIn("V30P Echt", eintrag.kunde_name)
        notiz = (self.s.query(VorgangsNotiz)
                 .filter(VorgangsNotiz.vorgang_id == vorgang_id,
                         VorgangsNotiz.text == f"Projekt {nummer} gelöscht: "
                                               "Testprojekt der Pilotphase").one())
        self.assertEqual(notiz.herkunft, "projektierung")
        # Akte weg, Liste ohne die Nummer, Vorgangsakte mit „Angebot → Projekt“
        self.assertEqual(self.admin.get(f"/projektierung/projekt/{pid}",
                                        follow_redirects=False).status_code, 303)
        self.assertNotIn(nummer, self.tabelle(self.admin.get("/projektierung/liste").text))
        self.assertNotIn(f"/projektierung/projekt/{pid}\"",
                         self.admin.get("/projektierung").text)
        vorgangsakte = self.admin.get(f"/vorgaenge/{vorgang_id}").text
        self.assertIn("Angebot → Projekt", vorgangsakte)
        self.assertNotIn(f"/projektierung/projekt/{pid}\"", vorgangsakte)

    def test_innendienst_403(self):
        projekt = self.projekt_neu()
        antwort = self.id_client.post(f"/projektierung/projekt/{projekt.id}/loeschen",
                                      data={"grund": "x", "nummer": projekt.nummer},
                                      follow_redirects=False)
        self.assertEqual(antwort.status_code, 403)
        self.s.expunge_all()
        self.assertTrue(self.projekt_existiert(projekt.id))
        antwort = self.id_client.post("/projektierung/liste/loeschen",
                                      data={"projekt_id": str(projekt.id), "grund": "x",
                                            "bestaetigung": "LÖSCHEN"},
                                      follow_redirects=False)
        self.assertEqual(antwort.status_code, 403)

    def test_ohne_grund_meldung(self):
        projekt = self.projekt_neu()
        antwort = self.admin.post(f"/projektierung/projekt/{projekt.id}/loeschen",
                                  data={"grund": "   ", "nummer": projekt.nummer},
                                  follow_redirects=False)
        self.assertEqual(antwort.status_code, 303)
        self.assertIn(f"/projektierung/projekt/{projekt.id}?meldung=Bitte+einen+Grund",
                      antwort.headers["location"])
        self.s.expunge_all()
        self.assertTrue(self.projekt_existiert(projekt.id))
        self.assertEqual(self.s.query(AngebotsLoeschung)
                         .filter(AngebotsLoeschung.nummer == projekt.nummer).count(), 0)
        # JSON-Variante (fetch) → 400 mit Meldung
        antwort = self.admin.post(f"/projektierung/projekt/{projekt.id}/loeschen",
                                  data={"grund": "", "nummer": projekt.nummer},
                                  headers={"accept": "application/json"})
        self.assertEqual(antwort.status_code, 400)
        self.assertFalse(antwort.json()["ok"])
        self.assertIn("Grund", antwort.json()["meldung"])

    def test_falsche_projektnummer_meldung(self):
        projekt = self.projekt_neu()
        antwort = self.admin.post(f"/projektierung/projekt/{projekt.id}/loeschen",
                                  data={"grund": "Test", "nummer": "PR-999999"},
                                  follow_redirects=False)
        self.assertEqual(antwort.status_code, 303)
        self.assertIn("Projektnummer+stimmt+nicht", antwort.headers["location"])
        self.s.expunge_all()
        self.assertTrue(self.projekt_existiert(projekt.id))
        self.assertTrue(kern.projekt_ordner(projekt).exists())

    def test_gewerk_in_montage_mit_bericht_abgelehnt(self):
        projekt = self.projekt_neu(phase="montage")
        gewerk = self.gewerke_von(projekt)[0]
        self.s.add(MontageFormular(projekt_id=projekt.id, gewerk_id=gewerk.id,
                                   formular="montagebericht", status="abgeschlossen",
                                   abgeschlossen_am=datetime.now()))
        self.s.commit()
        sperre = kern.loeschen_gesperrt(self.s, projekt)
        self.assertIn("stornieren", sperre)
        self.assertIn("Montage", sperre)
        antwort = self.admin.post(f"/projektierung/projekt/{projekt.id}/loeschen",
                                  data={"grund": "Test", "nummer": projekt.nummer},
                                  follow_redirects=False)
        self.assertEqual(antwort.status_code, 303)
        self.assertIn("stornieren", antwort.headers["location"])
        self.s.expunge_all()
        self.assertTrue(self.projekt_existiert(projekt.id))
        self.assertEqual(self.anzahl(Gewerk, projekt_id=projekt.id), 1)
        # Akte: Knopf vorhanden, Dialog zeigt nur den Storno-Hinweis
        seite = self.admin.get(f"/projektierung/projekt/{projekt.id}").text
        self.assertIn("Projekt löschen", seite)
        self.assertIn("Bitte stattdessen das Gewerk stornieren", seite)
        self.assertNotIn('name="nummer"', seite)
        # Montage ohne Bericht (nur Entwurf) ist löschbar
        self.s.query(MontageFormular).filter_by(gewerk_id=gewerk.id).update(
            {"status": "entwurf"})
        self.s.commit()
        self.assertEqual(kern.loeschen_gesperrt(self.s, projekt), "")

    def test_akte_knopf_und_dialog_nur_admin(self):
        projekt = self.projekt_neu()
        seite = self.admin.get(f"/projektierung/projekt/{projekt.id}").text
        self.assertIn("Projekt löschen", seite)
        self.assertIn('id="dlg-projekt-loeschen"', seite)
        self.assertIn(kern.LOESCH_HINWEIS, seite)
        self.assertIn(f'action="/projektierung/projekt/{projekt.id}/loeschen"', seite)
        # Innendienst sieht die Akte nur bei freigabe_modus = alle – und dort keinen Knopf
        s2 = SessionLocal()
        vorher = kern.parameter_holen(s2, "freigabe_modus", "admin")
        kern.parameter_setzen(s2, "freigabe_modus", "alle")
        s2.commit()
        try:
            seite = self.id_client.get(f"/projektierung/projekt/{projekt.id}").text
            self.assertIn(projekt.nummer, seite)
            self.assertNotIn("Projekt löschen", seite)
            self.assertNotIn("dlg-projekt-loeschen", seite)
            liste = self.id_client.get("/projektierung/liste").text
            self.assertNotIn("Ausgewählte löschen", liste)
            self.assertNotIn('class="pj-auswahl"', liste)
        finally:
            kern.parameter_setzen(s2, "freigabe_modus", vorher)
            s2.commit()
            s2.close()


class ProjektLoeschenListe(Basis):
    """Checkbox 2: Demo-Projekte – Filter „Demo“, Badge, Mehrfachauswahl (Admin)."""

    def test_ist_demo_projekt(self):
        kunde = Kunde(nachname="Demo Planung", email="petra@demo.example")
        self.assertTrue(kern.ist_demo_projekt(None, kunde, None))
        self.assertTrue(kern.ist_demo_projekt(None, Kunde(nachname="Demo Montage",
                                                          email="x@web.de"), None))
        self.assertTrue(kern.ist_demo_projekt(None, Kunde(nachname="Weber",
                                                          email="bernd@demo.example"), None))
        self.assertTrue(kern.ist_demo_projekt(None, Kunde(nachname="Weber", email="w@web.de"),
                                              Vorgang(kunde_id=0, demo=True)))
        self.assertFalse(kern.ist_demo_projekt(None, Kunde(nachname="Weber", email="w@web.de"),
                                               Vorgang(kunde_id=0, demo=False)))
        self.assertFalse(kern.ist_demo_projekt(None, Kunde(nachname="Demoliere",
                                                           email="d@web.de"), None))
        self.assertFalse(kern.ist_demo_projekt(None, None, None))

    def test_liste_filter_demo_und_badge(self):
        demo = self.projekt_neu(nachname="Demo V30P")
        echt = self.projekt_neu(nachname="V30P Echt")
        alles = self.admin.get("/projektierung/liste").text
        zeilen = self.tabelle(alles)
        self.assertIn(demo.nummer, zeilen)
        self.assertIn(echt.nummer, zeilen)
        self.assertIn('class="demo-badge"', zeilen)
        self.assertIn('name="demo" value="1"', alles)
        nur_demo = self.tabelle(self.admin.get("/projektierung/liste?demo=1").text)
        self.assertIn(demo.nummer, nur_demo)
        self.assertNotIn(echt.nummer, nur_demo)
        # Zeile des Demo-Projekts trägt das Badge, die echte nicht
        zeile_demo = nur_demo.split(f'projekt/{demo.id}" class="pj-mono"', 1)[1][:600]
        self.assertIn(">Demo</span>", zeile_demo)
        zeile_echt = zeilen.split(f'projekt/{echt.id}" class="pj-mono"', 1)[1][:600]
        self.assertNotIn(">Demo</span>", zeile_echt)
        # Admin: Auswahl-Häkchen je Zeile, Sammelknopf, Dialog mit Bestätigungswort
        self.assertIn('class="pj-auswahl" name="projekt_id" form="pj-sammel-form"', alles)
        self.assertIn(f'data-nummer="{demo.nummer}"', alles)
        self.assertIn("Ausgewählte löschen", alles)
        self.assertIn('id="dlg-sammel-loeschen"', alles)
        self.assertIn("LÖSCHEN", alles)
        self.assertIn(kern.LOESCH_HINWEIS, alles)
        # Akte des Demo-Projekts zeigt das Badge im Kopf
        self.assertIn('class="demo-badge"', self.admin.get(f"/projektierung/projekt/{demo.id}").text)
        self.assertNotIn('class="demo-badge"', self.admin.get(f"/projektierung/projekt/{echt.id}").text)

    def test_mehrfachauswahl_loescht_mit_bestaetigung(self):
        p1 = self.projekt_neu(nachname="Demo V30P A")
        p2 = self.projekt_neu(nachname="Demo V30P B", sparten=("WP", "PV"))
        gesperrt = self.projekt_neu(nachname="Demo V30P C", phase="montage")
        g = self.gewerke_von(gesperrt)[0]
        self.s.add(MontageFormular(projekt_id=gesperrt.id, gewerk_id=g.id,
                                   formular="abnahme", status="abgeschlossen"))
        self.s.commit()
        ids = [p1.id, p2.id, gesperrt.id]
        nummern = [p1.nummer, p2.nummer, gesperrt.nummer]
        # falsche Bestätigung → nichts gelöscht
        antwort = self.admin.post("/projektierung/liste/loeschen",
                                  data={"projekt_id": [str(i) for i in ids],
                                        "grund": "Demo raus", "bestaetigung": "ja"},
                                  follow_redirects=False)
        self.assertEqual(antwort.status_code, 303)
        self.assertIn("Best%C3%A4tigung+fehlt", antwort.headers["location"])
        self.s.expunge_all()
        self.assertEqual(self.s.query(Projekt.id).filter(Projekt.id.in_(ids)).count(), 3)
        # ohne Grund → Meldung
        antwort = self.admin.post("/projektierung/liste/loeschen",
                                  data={"projekt_id": [str(i) for i in ids],
                                        "grund": "", "bestaetigung": "LÖSCHEN"},
                                  follow_redirects=False)
        self.assertIn("Bitte+einen+Grund", antwort.headers["location"])
        # mit Bestätigung: zwei gelöscht, das gesperrte übersprungen (Storno-Hinweis)
        antwort = self.admin.post("/projektierung/liste/loeschen",
                                  data={"projekt_id": [str(i) for i in ids],
                                        "grund": "Demo-Projekte vor dem Go-live",
                                        "bestaetigung": "löschen",
                                        "zurueck": "/projektierung/liste?demo=1"},
                                  follow_redirects=False)
        self.assertEqual(antwort.status_code, 303)
        ziel = antwort.headers["location"]
        self.assertTrue(ziel.startswith("/projektierung/liste?demo=1&meldung="), ziel)
        self.assertIn("2+Projekt%28e%29+gel%C3%B6scht", ziel)
        self.assertIn("stornieren", ziel)
        self.s.expunge_all()
        self.assertFalse(self.projekt_existiert(p1.id))
        self.assertFalse(self.projekt_existiert(p2.id))
        self.assertTrue(self.projekt_existiert(gesperrt.id))
        protokoll = {e.nummer: e for e in self.s.query(AngebotsLoeschung)
                     .filter(AngebotsLoeschung.nummer.in_(nummern))}
        self.assertEqual(set(protokoll), {p1.nummer, p2.nummer})
        self.assertTrue(all(e.art == "projekt" and e.grund == "Demo-Projekte vor dem Go-live"
                            for e in protokoll.values()))
        geloescht = PROJEKTE / kern.GELOESCHT_ORDNER
        self.assertEqual(len(list(geloescht.glob(p1.nummer + "_*"))), 1)
        self.assertEqual(len(list(geloescht.glob(p2.nummer + "_*"))), 1)
        self.assertTrue(kern.projekt_ordner(gesperrt).exists())
        # Angebote beider gelöschten Projekte wieder ohne Projekt, Status unverändert
        for a in self.s.query(Angebot).filter(Angebot.kunde_id.in_(
                [p.kunde_id for p in (p1, p2)])):
            self.assertIsNone(a.projekt_gewerk_id)
            self.assertEqual(a.status, "Angenommen")
        # Sammelformular ohne Auswahl → Meldung
        antwort = self.admin.post("/projektierung/liste/loeschen",
                                  data={"grund": "x", "bestaetigung": "LÖSCHEN"},
                                  follow_redirects=False)
        self.assertIn("Kein+Projekt+ausgew", antwort.headers["location"])


if __name__ == "__main__":
    unittest.main()
