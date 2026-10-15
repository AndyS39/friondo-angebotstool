# v33 (PLAN_V20) – Fundament des Orchestrators: Rollen-Varianten (Tabelle `rollen`,
# Basisrolle/Kennzeichen am Benutzer, Migration idempotent, Rechte erben), Graph-Modus
# (delegiert ohne Geheimnis, /users/-Basis im Modus anwendung, 403 → Fehlerprotokoll einmal je
# Stunde), neue Tabellen/Spalten, Terminart service, Parameter.
import unittest
from unittest import mock

from fastapi.testclient import TestClient
from sqlalchemy import inspect

from app import auth, config, graph_versand, projektierung, rollen
from app.db import SessionLocal, engine, init_db
from app.main import app
from app.models import AdProfil, Benutzer, Rolle, Team, einstellung_holen, einstellung_setzen

PRAEFIX = "V33F"


def _aufraeumen(s):
    for b in s.query(Benutzer).filter(Benutzer.name.like(f"{PRAEFIX}%")):
        s.query(AdProfil).filter(AdProfil.benutzer_id == b.id).delete()
        s.delete(b)
    s.commit()


class Rollen(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        init_db()
        cls.s = SessionLocal()
        _aufraeumen(cls.s)
        rollen.migration_v33_rollen(cls.s)
        cls.s.commit()
        rollen.cache_leeren()

    @classmethod
    def tearDownClass(cls):
        _aufraeumen(cls.s)
        cls.s.close()

    def test_tabellen_und_spalten(self):
        tabellen = set(inspect(engine).get_table_names())
        for t in ("rollen", "outlook_ereignisse", "outlook_auftraege", "outlook_belegt",
                  "einwaende", "vorgang_einwaende"):
            self.assertIn(t, tabellen)
        spalten = {c["name"] for c in inspect(engine).get_columns("projekt_termine")}
        self.assertTrue({"vorgang_id", "service_gewerk", "anlass", "service_status"} <= spalten)
        self.assertIn("gewerk", {c["name"] for c in inspect(engine).get_columns("teams")})
        self.assertIn("phase_auto", {c["name"] for c in inspect(engine).get_columns("gewerke")})
        self.assertIn("nachfass_versuche", {c["name"] for c in inspect(engine).get_columns("vorgaenge")})

    def test_migration_idempotent_und_systemzeilen(self):
        vorher = self.s.query(Rolle).count()
        meldungen = rollen.migration_v33_rollen(self.s)
        self.s.commit()
        self.assertEqual(self.s.query(Rolle).count(), vorher)
        self.assertEqual(meldungen, [], meldungen)
        keys = {r.key: r for r in self.s.query(Rolle)}
        for basis in rollen.BASISROLLEN:
            self.assertTrue(keys[basis].system)
            self.assertEqual(keys[basis].basisrolle, basis)
        self.assertEqual(keys["service_elektro"].basisrolle, "montage")
        self.assertTrue(keys["service_elektro"].service)
        self.assertEqual(keys["service_elektro"].gewerk, "elektro")
        self.assertTrue(keys["handelsvertreter"].handelsvertreter)
        self.assertEqual(keys["handelsvertreter"].basisrolle, "aussendienst")

    def test_basisrolle_kennzeichen_gewerk(self):
        b = Benutzer(name=f"{PRAEFIX} Service", rolle="service_elektro", aktiv=True,
                     pin_hash=auth.pin_hash("4321"))
        self.assertEqual(b.basisrolle, "montage")
        self.assertTrue(b.hat_rolle("montage"))
        self.assertTrue(b.hat_kennzeichen("service"))
        self.assertFalse(b.hat_kennzeichen("handelsvertreter"))
        self.assertEqual(b.gewerk, "elektro")
        self.assertEqual(b.rollen_name, "Service Elektro")
        hv = Benutzer(name=f"{PRAEFIX} HV", rolle="handelsvertreter", aktiv=True)
        self.assertEqual(hv.basisrolle, "aussendienst")
        self.assertEqual(hv.basisrollen, ["aussendienst"])
        self.assertTrue(hv.hat_kennzeichen("handelsvertreter"))
        self.assertEqual(rollen.basisrolle_von("admin"), "admin")
        self.assertEqual(rollen.basisrolle_von("unbekannt_xy"), "unbekannt_xy")
        self.assertEqual(rollen.keys_fuer_basis("montage")[0], "montage")
        self.assertTrue({"montage_heizung", "service_heizung"} <= set(rollen.keys_fuer_basis("montage")))

    def test_hv_rolle_ueber_kennzeichen_und_spiegel(self):
        from app import lead_v2
        hv = Benutzer(name=f"{PRAEFIX} HV2", rolle="handelsvertreter", aktiv=True,
                      pin_hash=auth.pin_hash("4321"))
        self.s.add(hv)
        self.s.flush()
        self.assertTrue(lead_v2.ist_handelsvertreter(self.s, hv))
        rollen.hv_spiegeln(self.s, hv)
        self.s.flush()
        profil = self.s.query(AdProfil).filter(AdProfil.benutzer_id == hv.id).first()
        self.assertTrue(profil is not None and profil.terminiert_selbst)
        # Rolle zurück auf Außendienst → Kennzeichen aus
        hv.rolle = "aussendienst"
        rollen.hv_spiegeln(self.s, hv)
        self.s.flush()
        self.assertFalse(profil.terminiert_selbst)
        self.assertFalse(lead_v2.ist_handelsvertreter(self.s, hv))
        self.s.rollback()

    def test_variante_erbt_pfadrechte(self):
        b = Benutzer(name=f"{PRAEFIX} MontageHeizung", rolle="montage_heizung", aktiv=True,
                     pin_hash=auth.pin_hash("4321"))
        self.s.add(b)
        self.s.commit()
        client = TestClient(app, follow_redirects=False)
        client.cookies.set(auth.COOKIE_NAME, auth.cookie_wert(b.id))
        r = client.get("/angebote")
        self.assertEqual(r.status_code, 303)
        self.assertEqual(r.headers["location"], "/montage")
        self.assertEqual(client.get("/montage").status_code, 200)
        self.assertEqual(client.get("/kalender/daten.json").status_code in (200, 404, 500), True)

    def test_rolle_anlegen_deaktivieren(self):
        ok, meldung, rolle = rollen.anlegen(self.s, "v33f_test", "V33F Testrolle", "montage",
                                            gewerk="heizung", service=True)
        self.assertTrue(ok, meldung)
        self.s.flush()
        ok, meldung = rollen.deaktivieren(self.s, "admin")
        self.assertFalse(ok)
        b = Benutzer(name=f"{PRAEFIX} Traeger", rolle="v33f_test", aktiv=True)
        self.s.add(b)
        self.s.flush()
        ok, meldung = rollen.deaktivieren(self.s, "v33f_test")
        self.assertFalse(ok, meldung)
        self.assertIn("aktive Benutzer", meldung)
        b.aktiv = False
        self.s.flush()
        ok, meldung = rollen.deaktivieren(self.s, "v33f_test")
        self.assertTrue(ok, meldung)
        self.s.rollback()
        rollen.cache_leeren()

    def test_terminart_service_und_parameter(self):
        self.assertIn("service", projektierung.TERMIN_ARTEN)
        self.assertEqual(projektierung.TERMIN_ARTEN["service"][0], "service")
        from app import leadmanagement as kern
        self.assertEqual(kern.PARAMETER_START["inaktiv_tage"], "14")
        self.assertEqual(kern.PARAMETER_START["inaktiv_tage_mfh"], "20")
        self.assertEqual(kern.PARAMETER_START["kalender_tagesbeginn"], "07:00")


class GraphModus(unittest.TestCase):
    def setUp(self):
        graph_versand.modus_cache_leeren()
        graph_versand.zugriff_verweigert_leeren()

    def tearDown(self):
        graph_versand.modus_cache_leeren()
        graph_versand.zugriff_verweigert_leeren()

    def test_ohne_geheimnis_delegiert(self):
        with mock.patch.object(config, "GRAPH_CLIENT_SECRET", ""), \
                mock.patch.object(config, "GRAPH_ZERTIFIKAT_PFAD", ""):
            self.assertFalse(graph_versand.anwendung_konfiguriert())
            self.assertEqual(graph_versand.modus(), "delegiert")
            self.assertEqual(graph_versand.basis_pfad(""), "/me")
            self.assertEqual(graph_versand.basis_pfad("termin@friondo.de"), "/users/termin%40friondo.de")

    def test_mit_geheimnis_erst_nach_verbindungstest(self):
        s = SessionLocal()
        try:
            alt = einstellung_holen(s, graph_versand.EINSTELLUNG_MODUS, "")
            with mock.patch.object(config, "GRAPH_CLIENT_ID", "id"), \
                    mock.patch.object(config, "GRAPH_TENANT_ID", "tenant"), \
                    mock.patch.object(config, "GRAPH_CLIENT_SECRET", "nur-im-test-gemockt"):
                self.assertTrue(graph_versand.anwendung_konfiguriert())
                graph_versand.modus_setzen(s, "delegiert")
                s.commit()
                self.assertEqual(graph_versand.modus(s), "delegiert")
                graph_versand.modus_setzen(s, "anwendung")
                s.commit()
                self.assertEqual(graph_versand.modus(s), "anwendung")
                self.assertTrue(graph_versand.basis_pfad("").startswith("/users/"))
                self.assertEqual(graph_versand.basis_pfad("monteur@friondo.de"),
                                 "/users/monteur%40friondo.de")
                with mock.patch.object(graph_versand, "_token_anwendung", return_value="tok-test"):
                    self.assertEqual(graph_versand._token(), "tok-test")
            einstellung_setzen(s, graph_versand.EINSTELLUNG_MODUS, alt or "delegiert")
            s.commit()
        finally:
            s.close()

    def test_403_einmal_je_stunde(self):
        import io
        import urllib.error
        fehler = urllib.error.HTTPError("https://graph.microsoft.com/v1.0/users/x%40friondo.de/events",
                                        403, "Forbidden", {}, io.BytesIO(b""))
        with mock.patch("urllib.request.urlopen", side_effect=fehler), \
                mock.patch("app.fehlerprotokoll.eintragen_text", return_value="F-1") as protokoll:
            for _ in range(3):
                with self.assertRaises(graph_versand.GraphZugriffVerweigert) as cm:
                    graph_versand._graph_aufruf("GET", "/users/x%40friondo.de/events", "tok")
            self.assertEqual(cm.exception.postfach, "x@friondo.de")
            self.assertIn("nicht in der Zugriffsgruppe", str(cm.exception))
            self.assertEqual(protokoll.call_count, 1)
            self.assertEqual([p for p, _ in graph_versand.zugriff_verweigert_liste()], ["x@friondo.de"])

    def test_postfach_aus_pfad(self):
        self.assertEqual(graph_versand.postfach_aus_pfad("/users/termin%40friondo.de/sendMail"),
                         "termin@friondo.de")
        self.assertEqual(graph_versand.postfach_aus_pfad("/me/messages"), "")


if __name__ == "__main__":
    unittest.main()


class ServiceberichtTerminId(unittest.TestCase):
    """v33 (PLAN_V20 Phase 168, Vorschlag S 4.3): Spalte montage_formulare.termin_id ist
    nachträglich angelegt; der Hook migration_v33_termin_id übernimmt den Übergangsschlüssel
    `_termin_id` aus antworten_json – idempotent."""

    def test_spalte_und_backfill(self):
        from app import montage_formulare
        from app.models import MontageFormular
        self.assertIn("termin_id", {c["name"] for c in inspect(engine).get_columns("montage_formulare")})
        s = SessionLocal()
        try:
            eintrag = MontageFormular(gewerk_id=0, projekt_id=0, formular="servicebericht",
                                      antworten_json='{"_termin_id": 424242, "sb_arbeiten": "Test"}')
            s.add(eintrag)
            s.commit()
            meldungen = montage_formulare.migration_v33_termin_id(s)
            self.assertTrue(meldungen and "termin_id" in meldungen[0], meldungen)
            s.expire_all()
            self.assertEqual(s.get(MontageFormular, eintrag.id).termin_id, 424242)
            # zweiter Lauf: nichts mehr zu tun
            self.assertEqual(montage_formulare.migration_v33_termin_id(s), [])
        finally:
            s.query(MontageFormular).filter_by(formular="servicebericht",
                                               antworten_json='{"_termin_id": 424242, "sb_arbeiten": "Test"}').delete()
            s.commit()
            s.close()


class UploadRoutenOhneSchreibsperre(unittest.TestCase):
    """v33 (PLAN_V20 Phase 172, Befund 15.10.2026): Mit BEGIN IMMEDIATE für Schreibsitzungen darf
    keine Upload-Route die SQLite-Schreibsperre während der Übertragung des Request-Bodys halten –
    jede Route mit Datei-Upload liest das Formular VOR dem ersten Sitzungszugriff oder ruft davor
    `verbindung_freigeben(session)` auf (Körper lesen = Netz-I/O, v27-Regel)."""

    def test_formular_vor_sitzung_oder_freigabe(self):
        import re
        from pathlib import Path
        befunde = []
        for datei in sorted((Path(__file__).resolve().parents[1] / "app" / "routers").glob("*.py")):
            zeilen = datei.read_text(encoding="utf-8").split("\n")
            i = 0
            while i < len(zeilen):
                m = re.match(r"^(async )?def (\w+)\(", zeilen[i])
                if not m:
                    i += 1
                    continue
                start, name = i, m.group(2)
                i += 1
                while i < len(zeilen) and not re.match(r"^(async )?def |^@router", zeilen[i]):
                    i += 1
                rumpf = zeilen[start:i]
                if not re.search(r"\.file\b|getlist\(\"datei|UploadFile|\.filename", "\n".join(rumpf)):
                    continue
                erste_db = next((k for k, z in enumerate(rumpf)
                                 if re.search(r"\bsession\.(get|query|execute|add|commit)|\bkurz\(", z)), None)
                formular = next((k for k, z in enumerate(rumpf) if "anfrage.formular(" in z), None)
                frei = next((k for k, z in enumerate(rumpf) if "verbindung_freigeben(" in z), None)
                if (formular is not None and erste_db is not None and erste_db < formular
                        and (frei is None or frei > formular)):
                    befunde.append(f"{datei.name}:{start + 1} {name}")
        self.assertEqual(befunde, [], "Upload-Routen mit Sitzungszugriff vor dem Formular: " + ", ".join(befunde))
