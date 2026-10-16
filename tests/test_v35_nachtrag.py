# v35-Nachtrag 16.10.2026 (Andreas): „Der AD muss auf die Vorgangsakte seiner Kunden kommen, unabhängig
# welchen Status sie haben.“ Die Vorgangsakte prüft seit v10/v23 `vorgaenge.gehoert_benutzer` (Zuständigkeit,
# monday-Lead, eigene Erfassung, eigener VOT-Termin, eigenes Angebot – ohne Status); die Kundensuche (v32)
# kannte als „eigene Kunden“ aber nur Vorgänge mit `vorgaenge.ad_id` und verglich `rolle == "aussendienst"`
# statt der Basisrolle. Jetzt: dieselben fünf Verknüpfungen, jeder Status (auch archiviert/verloren), der
# Treffer-Link führt immer auf eine Akte, die der Außendienst öffnen darf; Rollen-Varianten (Handelsvertreter)
# werden über die Basisrolle wie der Außendienst gefiltert.
import unittest
from datetime import date, datetime

from fastapi.testclient import TestClient

from app import auth
from app import vorgaenge as vorgaenge_modul
from app.db import SessionLocal
from app.main import app
from app.models import Angebot, Benutzer, Erfassung, Kunde, Lead, Vorgang, VotTermin

PRAEFIX = "V35N"


def _client(benutzer_id: int) -> TestClient:
    c = TestClient(app, follow_redirects=False)
    c.cookies.set(auth.COOKIE_NAME, auth.cookie_wert(benutzer_id))
    return c


class AdVorgangsakteJederStatus(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        s = SessionLocal()
        try:
            cls._aufraeumen(s)

            def benutzer(name, rolle):
                b = Benutzer(name=f"{PRAEFIX} {name}", rolle=rolle, aktiv=True,
                             email=f"{name.lower()}@v35n.local", pin_hash=auth.pin_hash("4321"))
                s.add(b)
                s.flush()
                return b.id

            cls.ad_id = benutzer("Vertrieb", "aussendienst")
            cls.fremd_id = benutzer("Fremd", "aussendienst")
            cls.hv_id = benutzer("Vertreter", "handelsvertreter")   # Rollen-Variante (v33), Basisrolle aussendienst

            def kunde(nachname):
                k = Kunde(anrede="Herr", vorname="Kurt", nachname=f"{nachname}{PRAEFIX}",
                          strasse="Testweg 3", plz="47051", ort="Duisburg", telefon="", interesse="WP")
                s.add(k)
                s.flush()
                return k

            # 1) nur über ein eigenes Angebot verknüpft – Vorgang archiviert, Lead-Phase verloren,
            #    Zuständigkeit (ad_id) bei einem anderen Vertriebler
            k1 = kunde("Angebotskunde")
            v1 = Vorgang(kunde_id=k1.id, lead_phase="verloren", ad_id=cls.fremd_id,
                         archiviert_am=datetime(2026, 9, 1, 8, 0))
            s.add(v1)
            s.flush()
            s.add(Angebot(nummer=f"AN-{PRAEFIX}-0001", kunde_id=k1.id, vorgang_id=v1.id,
                          vertriebler_id=cls.ad_id, status="Abgelehnt", datum=date(2026, 8, 20)))
            # 2) nur über eine eigene Erfassung (Vorgang gewonnen)
            k2 = kunde("Erfassungskunde")
            v2 = Vorgang(kunde_id=k2.id, lead_phase="gewonnen")
            s.add(v2)
            s.flush()
            s.add(Erfassung(kunde_id=k2.id, benutzer_id=cls.ad_id, vorgang_id=v2.id,
                            status="Abgesendet", sparte="WP"))
            # 3) nur über einen erledigten VOT-Termin
            k3 = kunde("Terminkunde")
            v3 = Vorgang(kunde_id=k3.id, lead_phase="erfasst")
            s.add(v3)
            s.flush()
            s.add(VotTermin(vorgang_id=v3.id, ad_id=cls.ad_id, beginn=datetime(2026, 9, 2, 10, 0),
                            status="erfolgt", typ="vot"))
            # 4) nur über den monday-Lead (Verantwortlicher)
            k4 = kunde("Mondaykunde")
            lead = Lead(monday_item_id=935000004711, benutzer_id=cls.ad_id, kunde_id=k4.id,
                        nachname=k4.nachname, vorname="Kurt")
            s.add(lead)
            s.flush()
            # Ein Vorgang je Lead (UNIQUE vorgaenge.lead_id): SQLite vergibt Lead-IDs neu – ein verwaister
            # Vorgang anderer Tests mit derselben lead_id gibt den Platz frei (nur Fremd-/Junkzeilen)
            s.query(Vorgang).filter(Vorgang.lead_id == lead.id, Vorgang.kunde_id != k4.id) \
                .update({"lead_id": None}, synchronize_session=False)
            v4 = Vorgang(kunde_id=k4.id, lead_id=lead.id, lead_phase="angebot")
            s.add(v4)
            s.flush()
            # 5) fremder Kunde (Zuständigkeit bei einem anderen Vertriebler)
            k5 = kunde("Fremdkunde")
            v5 = Vorgang(kunde_id=k5.id, lead_phase="neu", ad_id=cls.fremd_id)
            s.add(v5)
            s.flush()
            cls.faelle = {"angebot": (k1.id, v1.id), "erfassung": (k2.id, v2.id),
                          "termin": (k3.id, v3.id), "monday": (k4.id, v4.id)}
            cls.fremd = (k5.id, v5.id)
            s.commit()
        finally:
            s.close()

    @classmethod
    def _aufraeumen(cls, s):
        kunden = s.query(Kunde).filter(Kunde.nachname.like(f"%{PRAEFIX}")).all()
        for k in kunden:
            vorgang_ids = [v.id for v in s.query(Vorgang).filter(Vorgang.kunde_id == k.id)]
            for tabelle in (Angebot, Erfassung):
                s.query(tabelle).filter(tabelle.kunde_id == k.id).delete(synchronize_session=False)
            if vorgang_ids:
                s.query(VotTermin).filter(VotTermin.vorgang_id.in_(vorgang_ids)).delete(synchronize_session=False)
            s.query(Lead).filter(Lead.kunde_id == k.id).delete(synchronize_session=False)
            s.query(Vorgang).filter(Vorgang.kunde_id == k.id).delete(synchronize_session=False)
            s.delete(k)
        s.query(Benutzer).filter(Benutzer.name.like(f"{PRAEFIX} %")).delete(synchronize_session=False)
        s.commit()

    @classmethod
    def tearDownClass(cls):
        s = SessionLocal()
        try:
            cls._aufraeumen(s)
        finally:
            s.close()

    def _treffer(self, client, q):
        antwort = client.get("/suche.json", params={"q": q}, headers={"Accept": "application/json"})
        self.assertEqual(antwort.status_code, 200, antwort.text[:200])
        return {t["kunde_id"]: t for t in antwort.json()["treffer"]}

    def test_eigene_vorgang_ids_alle_verknuepfungen(self):
        s = SessionLocal()
        try:
            eigene = vorgaenge_modul.eigene_vorgang_ids(s, self.ad_id)
            for name, (_, vid) in self.faelle.items():
                self.assertIn(vid, eigene, name)
            self.assertNotIn(self.fremd[1], eigene)
            # Einschränkung auf Kunden
            nur = vorgaenge_modul.eigene_vorgang_ids(s, self.ad_id, [self.faelle["termin"][0]])
            self.assertEqual(nur, {self.faelle["termin"][1]})
            self.assertEqual(vorgaenge_modul.eigene_vorgang_ids(s, self.ad_id, []), set())
            # deckungsgleich mit gehoert_benutzer
            for _, vid in list(self.faelle.values()) + [self.fremd]:
                v = s.get(Vorgang, vid)
                self.assertEqual(vorgaenge_modul.gehoert_benutzer(s, v, self.ad_id), vid in eigene)
        finally:
            s.close()

    def test_suche_findet_eigene_kunden_jeder_status_und_akte_oeffnet(self):
        ad = _client(self.ad_id)
        suchwort = {"angebot": "Angebotskunde", "erfassung": "Erfassungskunde",
                    "termin": "Terminkunde", "monday": "Mondaykunde"}
        for name, (kunde_id, vorgang_id) in self.faelle.items():
            treffer = self._treffer(ad, suchwort[name])
            self.assertIn(kunde_id, treffer, f"{name}: Kunde nicht gefunden")
            self.assertEqual(treffer[kunde_id]["link"], f"/vorgaenge/{vorgang_id}", name)
            akte = ad.get(f"/vorgaenge/{vorgang_id}")
            self.assertEqual(akte.status_code, 200, f"{name}: Akte {akte.status_code}")
            self.assertIn(suchwort[name], akte.text)
        # archivierter, verlorener Vorgang (Fall Angebot) ist erreichbar – kein Status-Filter
        self.assertEqual(ad.get(f"/vorgaenge/{self.faelle['angebot'][1]}").status_code, 200)
        # fremder Kunde: nicht in der Suche, Akte verweigert
        self.assertNotIn(self.fremd[0], self._treffer(ad, "Fremdkunde"))
        akte = ad.get(f"/vorgaenge/{self.fremd[1]}")
        self.assertEqual(akte.status_code, 303)
        self.assertIn("Kein+Zugriff", akte.headers["location"])

    def test_handelsvertreter_variante_wie_aussendienst(self):
        s = SessionLocal()
        try:
            hv = s.get(Benutzer, self.hv_id)
            self.assertEqual(hv.basisrolle, "aussendienst")
        finally:
            s.close()
        client = _client(self.hv_id)
        self.assertEqual(self._treffer(client, "Fremdkunde"), {})
        self.assertEqual(self._treffer(client, "Angebotskunde"), {})

    def test_innendienst_unveraendert(self):
        admin = _client(1)
        treffer = self._treffer(admin, "Fremdkunde")
        self.assertIn(self.fremd[0], treffer)
        self.assertEqual(treffer[self.fremd[0]]["link"], f"/vorgaenge/{self.fremd[1]}")


if __name__ == "__main__":
    unittest.main()
