# Hotfix 29.09.2026: Vorgangsakte mit Wiedervorlage warf Internal Server Error
# (Makro wiedervorlage_chip verglich date mit datetime). Prüft alle Typ-
# Kombinationen und die echte Akte-Route.
import unittest
import warnings
from datetime import date, datetime, timedelta

warnings.filterwarnings("ignore")

from fastapi.testclient import TestClient

from app.db import SessionLocal, init_db
from app.main import app
from app.templating import templates

MAKRO = templates.env.from_string(
    '{% from "_symbole.html" import symbol %}'
    '{% from "_komponenten.html" import wiedervorlage_chip %}'
    "{{ wiedervorlage_chip(datum, heute) }}")


class WiedervorlageChip(unittest.TestCase):
    def test_alle_typkombinationen(self):
        jetzt = datetime(2026, 9, 29, 15, 0)
        for heute in (jetzt, jetzt.date()):
            for datum, erwartet in ((datetime(2026, 9, 14), "faellig"),
                                    (datetime(2026, 9, 29, 18, 0), "faellig"),
                                    (date(2026, 10, 5), "geplant"),
                                    (datetime(2026, 10, 5), "geplant")):
                html = MAKRO.render(datum=datum, heute=heute)
                self.assertIn(f"wv-chip {erwartet}", html, (datum, heute))
        self.assertEqual(MAKRO.render(datum=None, heute=jetzt).strip(), "")

    def test_vorgangsakte_mit_wiedervorlage(self):
        from app.models import Vorgang
        init_db()
        s = SessionLocal()
        try:
            vorgang = s.query(Vorgang).first()
            if vorgang is None:
                self.skipTest("kein Vorgang in der Test-DB")
            alt = vorgang.wiedervorlage_am
            client = TestClient(app)
            client.post("/login", data={"benutzer_id": "1", "pin": "1234"})
            try:
                for tage in (-5, 7):
                    vorgang.wiedervorlage_am = datetime.now() + timedelta(days=tage)
                    s.commit()
                    r = client.get(f"/vorgaenge/{vorgang.id}")
                    self.assertEqual(r.status_code, 200)
                    self.assertIn("wv-chip", r.text)
            finally:
                vorgang.wiedervorlage_am = alt
                s.commit()
        finally:
            s.close()
