# Gemeinsame Testbasis Agent E (v34, PLAN_V21 Phase 180): Testkunde mit eigener E-Mail,
# Sammel-Vorgang, Angebote mit handgebauten Positions-Snapshots (WP mit Block 7
# „Elektroarbeiten“, PV mit 0 % USt, KL mit Block 2 „Elektro“), Admin-Client per Cookie
# (ID 1), Außendienst-Testbenutzer (Präfix V34E). Läuft gegen DB_PFAD_OVERRIDE (Kopie),
# räumt alle eigenen Daten am Ende auf. Kein Netzzugriff.
import unittest
import warnings
from pathlib import Path

warnings.filterwarnings("ignore")

from fastapi.testclient import TestClient
from pypdf import PdfReader

from app import angebot_aufbau, auth
from app import vorgaenge as vorgaenge_modul
from app.db import SessionLocal, init_db
from app.main import app
from app.models import (Angebot, AngebotsPosition, Benutzer, Erfassung, Fehlerprotokoll, Kunde,
                        Vorgang, VorgangsNotiz, angebot_status_setzen)

AD_PRAEFIX = "V34E"
PROJEKT = Path(__file__).resolve().parents[1]

# Positions-Snapshots: Block 7 „Elektroarbeiten“ eines WP-Angebots – netto 2.400,00 €
# (Kontrollwert PLAN_V21 Phase 180); dazu Block 1 mit dem Paket (10.000,00 €)
WP_PAKET = dict(sort=1, block_nr=1, gruppe="Bosch Monoblock Wärmepumpe CS3800i AW Paket",
                pos_nr="045", bezeichnung="Bosch CS3800i AW 7 OR-S Paket", beschreibung="Paket",
                menge=1.0, einheit="psl.", e_preis_cent=1_000_000, ek_cent=600_000)
WP_ELEKTRO = [
    dict(sort=2, block_nr=7, gruppe="Elektroarbeiten", pos_nr="011",
         bezeichnung="Elektroinstallation Wärmepumpe", beschreibung="Elektroinstallation inkl. SLS/ÜSS",
         menge=1.0, einheit="psl.", e_preis_cent=150_000, ek_cent=90_000),
    dict(sort=3, block_nr=7, gruppe="Elektroarbeiten", pos_nr="104",
         bezeichnung="Zähler-Komplettschrank 2-Feld inkl. Anbindung",
         beschreibung="Zählerschrank 2-Feld", menge=1.0, einheit="Stück",
         e_preis_cent=90_000, ek_cent=50_000),
]
WP_ELEKTRO_EP = dict(sort=4, block_nr=7, gruppe="Elektroarbeiten", pos_nr="152",
                     bezeichnung="Unterverteilung", beschreibung="(optionale Position)",
                     menge=1.0, einheit="Stück", e_preis_cent=40_000, ek_cent=20_000, ep_flag=True)
WP_ELEKTRO_BAUSEITS = dict(sort=5, block_nr=7, gruppe="Elektroarbeiten", pos_nr="Z22",
                           bezeichnung="Zählerschrank-Ertüchtigung", beschreibung="bauseits",
                           menge=1.0, einheit="psl.", e_preis_cent=30_000, ek_cent=10_000,
                           bauseits=True)
PV_MODULE = dict(sort=1, block_nr=1, gruppe="Komplettpaket 4,55 kWp PV-Anlage", pos_nr="PV001",
                 bezeichnung="Solar Fabrik Mono S4 455 Wp", beschreibung="PV-Modul",
                 menge=10.0, einheit="Stück", e_preis_cent=10_000, ek_cent=6_000)
KL_GERAET = dict(sort=1, block_nr=3, gruppe="Klimaanlage Bosch", pos_nr="KL035",
                 bezeichnung="Bosch CL3200i-Set 35 WE Single-Split", beschreibung="Set",
                 menge=1.0, einheit="Set", e_preis_cent=178_600, ek_cent=100_000)
KL_ELEKTRO = dict(sort=2, block_nr=2, gruppe="", pos_nr="KL008",
                  bezeichnung="Elektroinstallation Außengerät mit Einzelabsicherung",
                  beschreibung="Elektro", menge=1.0, einheit="psl.", e_preis_cent=49_800,
                  ek_cent=23_000)


def aufraeumen(s, email: str, ad_name: str | None = None) -> None:
    for k in s.query(Kunde).filter(Kunde.email == email):
        for a in s.query(Angebot).filter_by(kunde_id=k.id):
            s.query(Fehlerprotokoll).filter(
                Fehlerprotokoll.pfad.like(f"/angebote/{a.id}/%")).delete(synchronize_session=False)
            s.delete(a)
        for e in s.query(Erfassung).filter_by(kunde_id=k.id):
            s.delete(e)
        for v in s.query(Vorgang).filter_by(kunde_id=k.id):
            s.query(VorgangsNotiz).filter_by(vorgang_id=v.id).delete(synchronize_session=False)
            s.delete(v)
        s.delete(k)
    if ad_name:
        s.query(Benutzer).filter(Benutzer.name == ad_name).delete(synchronize_session=False)
    s.commit()


def pdf_text(pfad) -> str:
    return "\n".join((seite.extract_text() or "") for seite in PdfReader(str(pfad)).pages)


class Basis(unittest.TestCase):
    EMAIL = "v34e-basis@test.local"
    NACHNAME = "V34E Basis"
    AD_NAME = f"{AD_PRAEFIX} Basis-AD"

    @classmethod
    def setUpClass(cls):
        init_db()
        cls.s = SessionLocal()
        aufraeumen(cls.s, cls.EMAIL, cls.AD_NAME)
        cls.kunde = Kunde(anrede="Herr", vorname="Max", nachname=cls.NACHNAME,
                          strasse="Teststr. 1", plz="47139", ort="Duisburg", email=cls.EMAIL)
        cls.ad = Benutzer(name=cls.AD_NAME, rolle="aussendienst", aktiv=True,
                          email=f"{cls.EMAIL.split('@')[0]}-ad@test.local",
                          pin_hash=auth.pin_hash("4321"))
        cls.s.add_all([cls.kunde, cls.ad])
        cls.s.commit()
        cls.vorgang = vorgaenge_modul.vorgang_fuer_kunde(cls.s, cls.kunde.id)
        cls.s.commit()
        cls.client = TestClient(app, raise_server_exceptions=False)
        cls.client.cookies.set(auth.COOKIE_NAME, auth.cookie_wert(1))   # Admin (Dev-ID 1)

    @classmethod
    def tearDownClass(cls):
        aufraeumen(cls.s, cls.EMAIL, cls.AD_NAME)
        cls.s.close()

    def setUp(self):
        # jeder Test startet ohne Angebote im (gemeinsamen) Sammel-Vorgang des Testkunden
        for a in self.s.query(Angebot).filter_by(kunde_id=self.kunde.id):
            self.s.delete(a)
        self.s.query(VorgangsNotiz).filter_by(vorgang_id=self.vorgang.id).delete(
            synchronize_session=False)
        self.s.commit()
        self.s.expire_all()

    def ad_client(self) -> TestClient:
        c = TestClient(app, raise_server_exceptions=False)
        c.cookies.set(auth.COOKIE_NAME, auth.cookie_wert(self.ad.id))
        return c

    # --- Angebote ------------------------------------------------------------------------
    def angebot(self, sparte: str, positionen: list[dict], status: str = "Entwurf",
                vertriebler=True) -> Angebot:
        a = angebot_aufbau.angebot_anlegen(self.s, self.kunde.id, sparte=sparte)
        a.vorgang_id = self.vorgang.id
        if vertriebler:
            a.vertriebler_id = self.ad.id
        for p in positionen:
            a.positionen.append(AngebotsPosition(**dict(p)))
        if status != "Entwurf":
            angebot_status_setzen(a, status)
        self.s.commit()
        return a

    def wp_entwurf(self, status: str = "Entwurf", mit_ep_bauseits: bool = True) -> Angebot:
        positionen = [WP_PAKET] + WP_ELEKTRO
        if mit_ep_bauseits:
            positionen += [WP_ELEKTRO_EP, WP_ELEKTRO_BAUSEITS]
        return self.angebot("WP", positionen, status)

    def pv_entwurf(self, status: str = "Entwurf", zusatz: list[dict] | None = None) -> Angebot:
        return self.angebot("PV", [PV_MODULE] + list(zusatz or []), status)

    def kl_entwurf(self, status: str = "Entwurf") -> Angebot:
        return self.angebot("KL", [KL_GERAET, KL_ELEKTRO], status)

    def neu(self, angebot_id: int) -> Angebot:
        self.s.expire_all()
        return self.s.get(Angebot, angebot_id)

    def post_json(self, client: TestClient, pfad: str, **daten):
        return client.post(pfad, data=daten, headers={"accept": "application/json"})
