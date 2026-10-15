# v33-Nachtrag 15.10.2026 – Entscheidungen zu den Rückfragen des Durchlaufs (Auftrag Andreas:
# „alle offenen Fragen selbst im Interesse des Projekts beantworten“). Geprüft werden die
# Entscheidungen mit Code: Foto-Upload (P7), Kalender-Rückschau und Vertrieblerwechsel (K-R3/R6),
# Admins in der Postfach-Liste (G-R4), SWD-Kanalwerte (R-R4), HV-Dashboard-Block (R-R5),
# monday-Basis netto nach Rabatt (A-R1), Glocke bei Verschiebung aus Outlook (O-R5),
# Handlauf Bestandstermine (O-R7). Service ohne Besetzung (S-R5) prüft test_v33_service.
import os
import subprocess
import sys
import unittest
from datetime import datetime, timedelta
from pathlib import Path
from types import SimpleNamespace

from fastapi.testclient import TestClient

from app import auth, graph_versand, lead_handelsvertreter, lead_v2, monday_rueckspielung, outlook_sync
from app import leadmanagement as lead_kern
from app.db import SessionLocal
from app.main import app
from app.models import Benachrichtigung, Benutzer, Kunde, OutlookEreignis, Profil, Vorgang, VotTermin
from tests.test_v33_kalender import Basis as KalenderBasis, _dt

PROJEKT = Path(__file__).resolve().parents[1]
PRAEFIX = "V33NT"


class FotoUpload(unittest.TestCase):
    """P7: Fotos werden auf dem Gerät verkleinert, die Sammelbox lädt Foto für Foto hoch."""

    def test_skript_eingebunden_und_sammelbox_umgestellt(self):
        js = (PROJEKT / "app/static/bild_verkleinern.js").read_text(encoding="utf-8")
        for erwartet in ("MAX_KANTE = 2000", "QUALITAET = 0.85", "requestSubmit", "DataTransfer",
                         "window.bildVerkleinern", "addEventListener('submit'"):
            self.assertIn(erwartet, js, erwartet)
        base = (PROJEKT / "app/templates/base.html").read_text(encoding="utf-8")
        self.assertIn("/static/bild_verkleinern.js", base)
        galerie = (PROJEKT / "app/templates/_galerie.html").read_text(encoding="utf-8")
        self.assertIn("window.bildVerkleinern(datei)", galerie)
        self.assertIn("'Lade ' + (nr + 1) + ' von ' + gesamt", galerie)
        self.assertIn("form.requestSubmit()", galerie)
        c = TestClient(app)
        c.cookies.set(auth.COOKIE_NAME, auth.cookie_wert(1))
        self.assertIn("bild_verkleinern.js", c.get("/angebotstool").text)


class KalenderEntscheidungen(KalenderBasis):
    """K-R6: Drag in die Zeile eines anderen Vertrieblers verlangt eine Bestätigung."""

    def test_vertrieblerwechsel_braucht_bestaetigung(self):
        ziel = _dt(self.montag + timedelta(days=3), 10)
        r = self.admin.post("/kalender/verschieben", json={"quelle": "vot", "id": self.vot.id,
                                                            "beginn": ziel.strftime("%Y-%m-%dT%H:%M"),
                                                            "person_id": self.hv.id})
        self.assertEqual(r.status_code, 200, r.text)
        antwort = r.json()
        self.assertFalse(antwort["ok"], antwort)
        self.assertTrue(antwort.get("bestaetigung_noetig"), antwort)
        self.assertIn("Vertriebler wechseln", antwort["meldung"])
        self.frisch()
        self.assertEqual(self.s.get(VotTermin, self.vot.id).ad_id, self.ad.id)   # unverändert


class PostfachListe(unittest.TestCase):
    """G-R4: Admins mit E-Mail stehen in der Postfach-Liste der Verbindungs-Seite."""

    def test_admin_in_der_liste(self):
        self.assertIn("admin", graph_versand.MITARBEITER_BASISROLLEN)
        s = SessionLocal()
        admin = s.get(Benutzer, 1)
        alt = admin.email
        try:
            if "@" not in (admin.email or ""):
                admin.email = "v33nt-admin@friondo.de"
                s.commit()
            liste = graph_versand.benoetigte_postfaecher(s)
            self.assertTrue(any(e["benutzer_id"] == 1 and e["art"] == graph_versand.ART_MITARBEITER
                                for e in liste), [e["name"] for e in liste])
        finally:
            admin.email = alt
            s.commit()
            s.close()


class SwdProfil(unittest.TestCase):
    """R-R4: das SWD-Profil bekommt per Migration die Kanalwerte, wenn sie fehlen."""

    def test_migration_setzt_kanalwerte_idempotent(self):
        s = SessionLocal()
        profil = Profil(name=f"{PRAEFIX} SWD", regel_kennung="swd", kanalwerte="")
        s.add(profil)
        s.commit()
        try:
            meldungen = lead_kern.migration_v33_swd_profil(s)
            self.assertTrue(any("Kanalwerte" in m for m in meldungen), meldungen)
            s.expire_all()
            self.assertEqual(s.get(Profil, profil.id).kanalwerte, "SWD, Stadtwerke Düsseldorf")
            self.assertEqual(lead_kern.migration_v33_swd_profil(s), [])
        finally:
            s.delete(profil)
            s.commit()
            s.close()


class HvDashboardGruppe(unittest.TestCase):
    """R-R5: HV-Dashboard zeigt „Simons Gruppe – noch nicht verteilt“."""

    def test_block_mit_offenem_lead(self):
        s = SessionLocal()
        alt_simon = lead_kern.parameter_holen(s, "hv_gruppe_simon", "")
        leiter = Benutzer(name=f"{PRAEFIX} Leiter", rolle="handelsvertreter", aktiv=True)
        auth.pin_setzen(leiter, "4711")
        s.add(leiter)
        s.flush()
        kunde = Kunde(vorname=PRAEFIX, nachname="Gruppe", plz="47139", ort="Duisburg")
        s.add(kunde)
        s.flush()
        vorgang = Vorgang(kunde_id=kunde.id, lead_phase="neu", ad_id=leiter.id, leadmanager_id=1)
        s.add(vorgang)
        s.flush()
        try:
            lead_kern.parameter_setzen(s, "hv_gruppe_simon", str(leiter.id))
            s.commit()
            self.assertTrue(lead_v2.hv_gruppe_offen_setzen(s, vorgang, benutzer=s.get(Benutzer, 1)))
            s.commit()
            daten = lead_handelsvertreter.dashboard_daten(s, leiter)
            self.assertEqual([e["vorgang"].id for e in daten["gruppe_offen"]], [vorgang.id])
            self.assertEqual(daten["kacheln"]["gruppe_offen"], 1)
            c = TestClient(app)
            c.cookies.set(auth.COOKIE_NAME, auth.cookie_wert(leiter.id))
            seite = c.get("/lead-management/handelsvertreter/dashboard")
            self.assertEqual(seite.status_code, 200)
            self.assertIn("noch nicht verteilt", seite.text)
            self.assertIn(f'data-hv-gruppe-offen="{vorgang.id}"', seite.text)
        finally:
            lead_kern.parameter_setzen(s, "hv_gruppe_simon", alt_simon)
            s.commit()
            from app.models import LeadAktivitaet
            s.query(LeadAktivitaet).filter(LeadAktivitaet.vorgang_id == vorgang.id).delete()
            s.query(Benachrichtigung).filter(Benachrichtigung.link == f"/lead-management/lead/{vorgang.id}").delete()
            s.delete(vorgang)
            s.delete(kunde)
            s.delete(leiter)
            s.commit()
            s.close()


class MondayNetto(unittest.TestCase):
    """A-R1: monday-Deal-Wert bei Basis „netto“ = Netto nach Rabatt."""

    def test_basis_netto_nach_rabatt(self):
        angebot = SimpleNamespace(extern=False, status="Versendet", vorgang_id=None,
                                  summen=lambda: {"netto": 2_000_000, "netto_nach_rabatt": 1_900_000,
                                                  "endbetrag": 1_900_000})
        self.assertEqual(monday_rueckspielung._betrag(angebot, "netto"), "19000.00")
        self.assertEqual(monday_rueckspielung._betrag(angebot, "brutto"), "19000.00")
        alt = SimpleNamespace(extern=False, status="Versendet", vorgang_id=None,
                              summen=lambda: {"netto": 2_000_000, "endbetrag": 2_380_000})
        self.assertEqual(monday_rueckspielung._betrag(alt, "netto"), "20000.00")   # Rückfall ohne Schlüssel


class OutlookVerschiebung(unittest.TestCase):
    """O-R5: Verschiebung eines VOT aus Outlook → Glocke an den Leadmanager, keine Kundenmail."""

    def test_glocke_an_leadmanager(self):
        s = SessionLocal()
        alt_arten = lead_kern.parameter_holen(s, "glocke_lead_arten", "")
        # Parameter zuerst committen – die Testdaten unten bleiben ungespeichert (Rollback am Ende)
        lead_kern.parameter_setzen(s, "glocke_lead_arten", "todo_zugewiesen,todo_aktualisiert,terminaenderung")
        s.commit()
        kunde = Kunde(vorname=PRAEFIX, nachname="Outlook", plz="47139", ort="Duisburg")
        s.add(kunde)
        s.flush()
        vorgang = Vorgang(kunde_id=kunde.id, lead_phase="terminiert", ad_id=1, leadmanager_id=1)
        s.add(vorgang)
        s.flush()
        beginn = datetime.now().replace(minute=0, second=0, microsecond=0) + timedelta(days=5)
        termin = VotTermin(vorgang_id=vorgang.id, ad_id=1, beginn=beginn, ende=beginn + timedelta(hours=1),
                           status="geplant", typ="vot")
        s.add(termin)
        s.flush()
        ereignis = OutlookEreignis(termin_art=outlook_sync.ART_VOT, termin_id=termin.id, benutzer_id=1,
                                   postfach="v33nt@friondo.de", event_id=f"{PRAEFIX}-ev", stand="ok",
                                   beginn=beginn, ende=termin.ende)
        s.add(ereignis)
        s.flush()
        try:
            # Lead-Glocken werden mit art="lead" gespeichert (leadmanagement.benachrichtigen → projektierung)
            vorher = s.query(Benachrichtigung).filter(Benachrichtigung.benutzer_id == 1,
                                                      Benachrichtigung.art == "lead").count()
            ok = outlook_sync._termin_nachziehen(s, ereignis, beginn + timedelta(hours=2),
                                                 beginn + timedelta(hours=3), False, "Max Muster", set())
            self.assertTrue(ok)
            s.flush()
            self.assertEqual(s.get(VotTermin, termin.id).beginn, beginn + timedelta(hours=2))
            glocken = (s.query(Benachrichtigung).filter(Benachrichtigung.benutzer_id == 1,
                                                        Benachrichtigung.art == "lead")
                       .order_by(Benachrichtigung.id.desc()).all())
            self.assertEqual(len(glocken), vorher + 1)
            self.assertIn("Terminänderung informieren", glocken[0].text)
            self.assertEqual(glocken[0].link, f"/lead-management/lead/{vorgang.id}")
        finally:
            s.rollback()
            lead_kern.parameter_setzen(s, "glocke_lead_arten", alt_arten)
            s.commit()
            s.close()


class BestandSkript(unittest.TestCase):
    """O-R7: Handlauf zählt im Trockenlauf und endet mit Exit 0 (ohne Netz, ohne Schreiben)."""

    def test_trockenlauf(self):
        env = dict(os.environ, PYTHONIOENCODING="utf-8", PYTHONPATH=str(PROJEKT))
        r = subprocess.run([sys.executable, str(PROJEKT / "scripts" / "outlook_bestand_einreihen.py"),
                            "--trocken", "--wochen", "2"], cwd=str(PROJEKT), env=env,
                           capture_output=True, text=True, timeout=180)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("Zeitraum bis", r.stdout)
        self.assertIn("kalender_sync", r.stdout)
