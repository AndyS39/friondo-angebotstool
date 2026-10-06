# Tests PLAN_V16 Phase 116 (v24, Klimakonfigurator Bosch Climate): Kontrollfälle
# A–H über die ECHTEN Wege – Erfassung per Route anlegen (/erfassung/sparten-start),
# vollständigen Bogen hinterlegen, absenden (Ampel/Validierung), Angebot erzeugen
# (Route /erfassungen/<id>/angebot-erzeugen bzw. angebot_aufbau.angebot_anlegen),
# Positionen/Preise/EP/Gruppe/Auslegungszeile/Summen prüfen, Ampel-Gründe wörtlich,
# PDF/Lieferschein/Protokoll/Projektierung/Freitext (Regression Phase 116).
# Läuft gegen die Entwicklungs-DB (Muster tests/test_pv_v13.py); Testkunde mit
# eigener E-Mail, Aufräumen am Ende (Angebote, Erfassungen, Vorgänge, Projekte).
import copy
import io
import json
import unittest
import warnings

warnings.filterwarnings("ignore")

from fastapi.testclient import TestClient

from app import angebot_aufbau, import_klima, kl_auslegung, pdf_export
from app import konfigurator as engine
from app import logik as logik_modul
from app import projektierung as kern
from app.db import SessionLocal, init_db
from app.main import app
from app.models import (Angebot, Artikel, Erfassung, Gewerk, Kunde, Projekt, QUELLE_KL,
                        Vorgang, angebot_status_setzen)

TEST_EMAIL = "kl-v24@test.local"
GRUPPE = "Klimaanlage Bosch"
AUSLEGUNGSZEILE = "Auslegung der Klimaanlage"
STARK = "stark (Süd-/Westseite, große Fenster, Dachgeschoss)"

# Ampel-Gründe / Meldungen wörtlich (PLAN_V16 Phase 114 / 116)
G1_E = "Kühllast über 7,0 kW: Raum 1 Studio (10,80 kW) – Raum teilen oder Sonderlösung"
G2_D3 = "Klasse 18 in Serie Climate 7000i nicht verfügbar – Serie wechseln"
G3_D1 = "Multi-Split in Serie Climate 8000i nicht verfügbar"
G4_F = "Multi-Split-Kombination 24+24 an Außengerät 1 nicht freigegeben (Bosch Tab. 7)"
G6_C = "Montagekombination 5 Innengeräte / 2 Außengeräte nicht hinterlegt"
MELDUNG_G = ("Außengerät 2 hat keinen zugeordneten Raum – Zuordnung (KR07) prüfen oder "
             "Anzahl Außengeräte anpassen.")


# --- Bogen (Werte exakt wie die Antwortmöglichkeiten des Blatts „Fragen KL“) ---------

def raum(name: str, flaeche, hoehe="bis 2,5 m", last="normal", lage="Erdgeschoss",
         zweck="hauptsächlich kühlen", ort="Außenwand", entfernung="bis 5 m", pumpe="Nein",
         durchbruch="Außenwand bis 32 cm (in Pauschale)", zuordnung="1") -> dict:
    """Raumblock in der Reihenfolge des Blatts: KR01, KR08, KR09, KR10, KR02, KR03,
    KR04, KR05, KR06, KR11, KR07 (Klone KRxx#i entstehen in bogen())."""
    return {"KR01": name, "KR08": flaeche, "KR09": hoehe, "KR10": last, "KR02": lage,
            "KR03": zweck, "KR04": ort, "KR05": entfernung, "KR06": pumpe,
            "KR11": durchbruch, "KR07": zuordnung}


def bogen(raeume: list[dict], **zusatz) -> dict:
    """Vollständiger KL-Bogen: KO01 EFH, KO02 1995, KO03 Ja, Climate 3200i (Standard),
    KO04 1, KO07 Nein, KO08 als Eventualposition, KA01 an der Außenwand, KA02 unter 2 m,
    KE01 Nein / KE02 0–5 m / KE03 Ja, KZ01 vom Boden/Leiter; Räume als Klone KRxx#i."""
    antworten = {"KO01": "EFH", "KO02": 1995, "KO03": "Ja",
                 "KO06": "Climate 3200i (Standard)", "KO04": "1",
                 "KO05": float(len(raeume)), "KO07": "Nein",
                 "KO08": "als Eventualposition", "KO09": "",
                 "KA01": "an der Außenwand", "KA02": "unter 2 m",
                 "KE01": "Nein", "KE02": "0–5 m", "KE03": "Ja",
                 "KZ01": "vom Boden/Leiter", "S01": "warm", "S02": ""}
    for i, r in enumerate(raeume, 1):
        for key, wert in r.items():
            antworten[f"{key}#{i}"] = wert
    antworten.update(zusatz)
    if antworten.get("KE01") == "Ja":        # KE02/KE03 nur bei KE01 = Nein oder Unklar
        antworten.pop("KE02", None)
        antworten.pop("KE03", None)
    return antworten


def fall_a() -> dict:
    """Musterangebot nachgestellt: 3 Räume, 1 Außengerät, 9+9+9 → CL5000M 79/3 E."""
    return bogen([raum("Wohnzimmer", 25), raum("Schlafzimmer", 18), raum("Büro", 28)])


def fall_b() -> dict:
    """Single-Split voll bestückt (Wohnküche 30 m², 2,5–3 m, stark → 2,97 kW → 12)."""
    return bogen([raum("Wohnküche", 30, "2,5–3 m", STARK, entfernung="6–10 m", pumpe="Ja",
                       durchbruch="Beton oder dicker als 32 cm")],
                 KO07="Ja", KO08="Nein", KA02="2–4 m", KE01="Ja",
                 KZ01="Gerüst erforderlich")


def fall_c() -> dict:
    """Montagematrix-Ampel: 5 Innengeräte an 2 Außengeräten (12+18 / 9+9+9)."""
    return bogen([raum("Wohnen", 50), raum("Essen", 55, last=STARK),
                  raum("Kind 1", 20, zuordnung="2"), raum("Kind 2", 20, zuordnung="2"),
                  raum("Büro", 20, zuordnung="2")], KO04="2")


def fall_d1() -> dict:
    return bogen([raum("Schlafen", 20), raum("Kind", 20)], KO06="Climate 8000i")


def fall_d2() -> dict:
    return bogen([raum("Wohnen", 50)], KO06="Climate 7000i", KO08="Ja")


def fall_d3() -> dict:
    return bogen([raum("Wohnen", 70)], KO06="Climate 7000i")


def fall_e() -> dict:
    return bogen([raum("Studio", 100, "über 3 m", STARK)])


def fall_f() -> dict:
    return bogen([raum("Wohnen", 60, last=STARK), raum("Essen", 60, last=STARK)])


def fall_g() -> dict:
    """KO04 2, alle Räume KR07 = 1 → Außengerät 2 ohne Raum."""
    return bogen([raum("A", 20), raum("B", 20), raum("C", 20)], KO04="2")


def fall_h() -> dict:
    """Schrägdach & §14a: 4 Räume je 40 m² → 9+9+9+9 → CL5000M 105/4 E."""
    return bogen([raum(f"Raum {i}", 40) for i in range(1, 5)],
                 KA01="auf einem Schrägdach", KZ01="Gerüst erforderlich")


# --- Hilfen ------------------------------------------------------------------------

def mengen(positionen) -> dict:
    ergebnis: dict = {}
    for p in positionen:
        nr = p["pos_nr"] if isinstance(p, dict) else p.pos_nr
        menge = p["menge"] if isinstance(p, dict) else p.menge
        if nr:
            ergebnis[nr] = ergebnis.get(nr, 0) + menge
    return ergebnis


def pdf_text_aus_bytes(daten: bytes) -> str:
    import pypdf
    return "\n".join(s.extract_text() for s in pypdf.PdfReader(io.BytesIO(daten)).pages)


def aufraeumen(s):
    from app.models import (Aufgabe, AufgabenpaketInstanz, GalerieDatei, ProjektDokument,
                            ProjektMail, ProjektTermin, ProjektVerlauf, SteckbriefWert)
    for k in s.query(Kunde).filter(Kunde.email == TEST_EMAIL):
        for p in s.query(Projekt).filter_by(kunde_id=k.id):
            for g in s.query(Gewerk).filter_by(projekt_id=p.id):
                s.query(Aufgabe).filter_by(gewerk_id=g.id).delete()
                s.query(AufgabenpaketInstanz).filter_by(gewerk_id=g.id).delete()
                s.query(SteckbriefWert).filter_by(gewerk_id=g.id).delete()
                s.delete(g)
            s.query(ProjektTermin).filter_by(projekt_id=p.id).delete()
            s.query(ProjektVerlauf).filter_by(projekt_id=p.id).delete()
            s.query(ProjektMail).filter_by(projekt_id=p.id).delete()
            s.query(ProjektDokument).filter_by(projekt_id=p.id).delete()
            s.delete(p)
        for a in s.query(Angebot).filter_by(kunde_id=k.id):
            s.delete(a)
        for e in s.query(Erfassung).filter_by(kunde_id=k.id):
            s.delete(e)
        for v in s.query(Vorgang).filter_by(kunde_id=k.id):
            s.query(GalerieDatei).filter_by(vorgang_id=v.id).delete()
            s.delete(v)
        s.delete(k)
    s.commit()


class Basis(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        init_db()
        cls.s = SessionLocal()
        if cls.s.query(Artikel).filter(Artikel.quelle == QUELLE_KL,
                                       Artikel.aktiv.is_(True)).count() < 50:
            import_klima.import_ausfuehren(cls.s)
        cls.logik_voll, cls.bericht = logik_modul.neu_einlesen(cls.s)
        cls.logik = logik_modul.logik_fuer_sparte(cls.logik_voll, "KL")
        aufraeumen(cls.s)
        cls.kunde = Kunde(anrede="Frau", vorname="Klara", nachname="KL-Test v24",
                          strasse="Teststr. 3", plz="47139", ort="Duisburg",
                          email=TEST_EMAIL)
        cls.s.add(cls.kunde)
        cls.s.commit()
        cls.client = TestClient(app)
        cls.client.post("/login", data={"benutzer_id": "1", "pin": "1234"})

    @classmethod
    def tearDownClass(cls):
        aufraeumen(cls.s)
        cls.s.close()

    # -- echte Wege ---------------------------------------------------------------
    def erfassung_anlegen(self, antworten: dict) -> Erfassung:
        """Erfassung über die Sparten-Startseite anlegen (wie der Außendienst) und
        den vollständigen Bogen hinterlegen."""
        r = self.client.post("/erfassung/sparten-start",
                             data={"kunde_id": str(self.kunde.id), "sparte_KL": "on"},
                             follow_redirects=False)
        self.assertEqual(r.status_code, 303)
        self.s.expire_all()
        e = (self.s.query(Erfassung)
             .filter(Erfassung.kunde_id == self.kunde.id, Erfassung.sparte == "KL")
             .order_by(Erfassung.id.desc()).first())
        self.assertIsNotNone(e)
        self.assertEqual((e.konfigurator_typ, e.status), ("KL", "Entwurf"))
        e.antworten_json = json.dumps(antworten, ensure_ascii=False)
        self.s.commit()
        return e

    def absenden(self, e: Erfassung):
        r = self.client.post(f"/erfassung/{e.id}/absenden", follow_redirects=False)
        self.s.refresh(e)
        return r

    def angebot_erzeugen(self, e: Erfassung) -> Angebot:
        r = self.client.get(f"/erfassungen/{e.id}/angebot-erzeugen", follow_redirects=False)
        self.assertEqual(r.status_code, 303, r.headers.get("location"))
        self.assertTrue(r.headers["location"].startswith("/angebote/"),
                        r.headers["location"])
        self.s.refresh(e)
        self.assertIsNotNone(e.angebot_id)
        return self.s.get(Angebot, e.angebot_id)

    def angebot_direkt(self, antworten: dict, logik=None) -> Angebot:
        return angebot_aufbau.angebot_anlegen(self.s, self.kunde.id, antworten=antworten,
                                              logik=logik or self.logik, sparte="KL")

    def pdf_text(self, angebot: Angebot) -> str:
        import pypdf
        pfad = pdf_export.pdf_fuer_angebot(self.s, angebot)
        text = "\n".join(s.extract_text() for s in pypdf.PdfReader(str(pfad)).pages)
        pfad.unlink(missing_ok=True)
        return text


# --- Voraussetzungen --------------------------------------------------------------

class Voraussetzungen(Basis):
    def test_logik_gruen_und_kl_sicht(self):
        self.assertTrue(self.bericht.ok, self.bericht.fehler)
        self.assertEqual(self.logik.sparte, "KL")
        self.assertEqual(len(self.logik.kl_aktionen), 45)
        self.assertEqual([b.nr for b in self.logik.kl_bloecke], [1, 2, 3])
        self.assertEqual(self.logik.kl_montage,
                         {(1, 1): "KL020", (2, 1): "KL021", (2, 2): "KL022",
                          (3, 1): "KL023", (3, 2): "KL024", (4, 1): "KL025"})
        self.assertEqual(sum(len(v) for d in self.logik.kl_kombis.values()
                             for v in d.values()), 215)
        for antworten in (fall_a(), fall_b(), fall_c(), fall_d1(), fall_d2(), fall_d3(),
                          fall_e(), fall_f(), fall_g(), fall_h()):
            self.assertIsNone(engine.naechste_frage(self.logik, antworten))
        # Bogenwerte sind gültige Optionen des Blatts „Fragen KL“
        for frage in engine.sichtbare_fragen(self.logik, fall_b()):
            if frage.typ == "Auswahl" and frage.id in fall_b():
                self.assertIn(fall_b()[frage.id], frage.antworten, frage.id)

    def test_kl_artikel_importiert(self):
        kl = {a.pos_nr: a for a in self.s.query(Artikel)
              .filter(Artikel.quelle == QUELLE_KL, Artikel.aktiv.is_(True))}
        self.assertEqual(len(kl), 50)
        self.assertEqual((kl["KL023"].e_preis_cent, kl["KL023"].einheit), (317800, "psl."))
        self.assertEqual((kl["KL038"].e_preis_cent, kl["KL038"].einheit), (196624, "Stück"))
        self.assertEqual((kl["KL034"].e_preis_cent, kl["KL034"].einheit), (134160, "Set"))
        self.assertEqual(kl["KL049"].e_preis_cent, 0)
        self.assertEqual((kl["KL050"].e_preis_cent, kl["KL050"].guid, kl["KL050"].ek_cent),
                         (49900, None, None))
        self.assertFalse(any(a.ep_flag for a in kl.values()))     # EP nur über die Aktion


# --- Fall A -----------------------------------------------------------------------

class FallA(Basis):
    ERWARTET = [("KL023", 1.0, 317800, False), ("KL008", 1.0, 49800, False),
                ("KL038", 1.0, 196624, False), ("KL026", 3.0, 29214, False),
                ("KL013", 3.0, 8250, True), ("KL049", 1.0, 0, False),
                ("", 1.0, 0, False)]

    def pruefe_angebot(self, angebot: Angebot):
        self.assertEqual((angebot.konfigurator_typ, angebot.ust_satz, angebot.kfw_json),
                         ("KL", 19.0, "{}"))
        pos = angebot.positionen
        self.assertEqual([(p.pos_nr, p.menge, p.e_preis_cent, bool(p.ep_flag)) for p in pos],
                         self.ERWARTET)
        self.assertEqual(pos[3].gesamt_cent, 87642)                       # 3 × 292,14
        self.assertEqual([p.gruppe for p in pos], ["", ""] + [GRUPPE] * 5)
        self.assertEqual([p.block_nr for p in pos], [1, 2, 3, 3, 3, 3, 3])
        letzte = pos[-1]
        self.assertEqual((letzte.bezeichnung, letzte.einheit, letzte.e_preis_cent, letzte.menge),
                         (AUSLEGUNGSZEILE, "psl.", 0, 1.0))
        self.assertTrue(letzte.beschreibung.startswith(
            "Auslegung Klimaanlage – Serie Bosch Climate 3200i"))
        self.assertIn("Raum 1 „Wohnzimmer“: 25,0 m² × 1,0 × 60 W/m² = 1,50 kW → Innengerät "
                      "2,6 kW (Klasse 9), Außengerät 1", letzte.beschreibung)
        # Gerätename = 1. Zeile des Artikels KL038 (nicht die 2. Zeile „Multisplit Außeneinh. …“)
        self.assertIn("Außengerät 1: BOSCH Klimagerät CL5000M 79/3 E, Multi-Split, "
                      "Kombination 9+9+9, 3 Innengeräte", letzte.beschreibung)
        self.assertIn("Montage: 3 Innengeräte / 1 Außengerät (Pauschale). Leitungslänge bis "
                      "5 m je Innengerät enthalten.", letzte.beschreibung)
        su = angebot.summen()
        self.assertEqual(su["netto"], 651866)                              # 6.518,66 €
        self.assertAlmostEqual(su["ust"], 123855, delta=1)                 # 1.238,55 € ± 0,01
        self.assertAlmostEqual(su["brutto"], 775721, delta=1)              # 7.757,21 € ± 0,01
        self.assertEqual(su["endbetrag"], su["brutto"])
        self.assertEqual(angebot.ust_bezeichnung, "19,00 % USt.")
        kl = json.loads(angebot.kl_json)
        self.assertEqual(kl["aussengeraete"][0]["kombination"], "9+9+9")
        self.assertEqual(kl["aussengeraete"][0]["geraet"], "CL5000M 79/3 E")
        self.assertEqual([r["kuehllast_kw"] for r in kl["raeume"]], [1.5, 1.08, 1.68])
        self.assertEqual([r["klasse"] for r in kl["raeume"]], ["9", "9", "9"])
        self.assertEqual((kl["montage_ref"], kl["ampeln"]), ("KL023", []))
        # kein Friondo Fit for Future, keine WP-Artikel
        self.assertFalse({"014", "015", "016", "017", "162"} & {p.pos_nr for p in pos})

    def test_fall_a_erfassung_absenden_angebot(self):
        e = self.erfassung_anlegen(fall_a())
        r = self.absenden(e)
        self.assertEqual(r.status_code, 200)
        self.assertEqual((e.ampel, e.status, e.gruende_text), ("gruen", "Neu", ""))
        self.assertEqual(engine.ampel_gruende(self.logik, fall_a()), [])
        self.assertEqual(engine.fachliche_hinweise(fall_a(), self.logik), [])
        angebot = self.angebot_erzeugen(e)
        self.pruefe_angebot(angebot)
        self.assertEqual((e.angebot_id, e.status), (angebot.id, "In Bearbeitung"))
        # Editor öffnet das Klima-Angebot mit 19-%-Zeile und Gruppe
        r = self.client.get(f"/angebote/{angebot.id}")
        self.assertEqual(r.status_code, 200)
        self.assertIn("19,00 % USt.", r.text)
        self.assertIn(GRUPPE, r.text)
        self.assertNotIn("KfW-Förderblock", r.text.replace("kein KfW-Förderblock", ""))
        # Erfassungsdetail und Prüfseite rendern (Seite „Auslegung“)
        self.assertEqual(self.client.get(f"/erfassungen/{e.id}").status_code, 200)
        self.assertLess(self.client.get(f"/erfassung/{e.id}/pruefen").status_code, 500)

    def test_fall_a_angebot_anlegen_direkt(self):
        self.pruefe_angebot(self.angebot_direkt(fall_a()))

    def test_fall_a_pdf(self):
        angebot = self.angebot_direkt(fall_a())
        text = self.pdf_text(angebot)
        self.assertIn("Ihr individuelles Klimaanlagen-Angebot zum Festpreis", text)
        self.assertIn(GRUPPE, text)
        self.assertIn("EP.", text)
        self.assertIn("19,00 % USt.", text)
        self.assertIn("6.518,66", text)
        self.assertIn(AUSLEGUNGSZEILE, text)
        # Auslegungszeile am Blockende: nach der Systemgarantie, vor der Netto-Summe
        i_garantie = text.index("Systemgarantie")
        i_auslegung = text.index(AUSLEGUNGSZEILE)
        i_netto = text.index("Netto-Summe")
        self.assertLess(i_garantie, i_auslegung)
        self.assertLess(i_auslegung, i_netto)
        self.assertIn("Hinweis zur Kältetechnik", text)
        for verboten in ("KfW", "Förderung", "Zuschuss", "Eigenanteil", "Wirtschaftlichkeit",
                         "So rechnet sich", "Vollmacht", "Beispielrate",
                         "Ihr individuelles PV-Angebot", "Aufschiebende Bedingung"):
            self.assertNotIn(verboten, text, verboten)

    def test_fall_a_lieferschein(self):
        angebot = self.angebot_direkt(fall_a())
        r = self.client.get(f"/angebote/{angebot.id}/lieferschein.pdf", follow_redirects=False)
        self.assertEqual(r.status_code, 303)                    # nur „Angenommen“
        angebot_status_setzen(angebot, "Angenommen")
        self.s.commit()
        r = self.client.get(f"/angebote/{angebot.id}/lieferschein.pdf")
        self.assertEqual(r.status_code, 200)
        self.assertIn(f"LS-{angebot.nummer}.pdf", r.headers.get("content-disposition", ""))
        text = pdf_text_aus_bytes(r.content)
        self.assertIn("L I E F E R S C H E I N", text)
        self.assertIn(GRUPPE, text)
        self.assertIn("Montagepauschale", text)
        self.assertIn("3,00", text)                               # Menge Innengeräte
        for verboten in ("€", "Netto", "Summe", "Rabatt", AUSLEGUNGSZEILE,
                         "Internet-Gateway"):                      # EP-Position entfällt
            self.assertNotIn(verboten, text, verboten)

    def test_fall_a_projektierung_gewerk_kl(self):
        """Annehmen von Fall A → Projekt + Gewerk KL (Dialog „Angebot → Projekt“)."""
        angebot = self.angebot_direkt(fall_a())
        angebot_status_setzen(angebot, "Angenommen")
        self.s.commit()
        r = self.client.get(f"/projektierung/angebot/{angebot.id}/projekt")
        self.assertEqual(r.status_code, 200)
        self.assertRegex(r.text, r'name="sparte_KL"\s+checked')
        r = self.client.post(f"/projektierung/angebot/{angebot.id}/projekt",
                             data={"sparte_KL": "on", "projektleiter_id": "1",
                                   "projekt_wahl": "neu"}, follow_redirects=False)
        self.assertEqual(r.status_code, 303, r.headers.get("location"))
        self.assertIn("/projektierung/projekt/", r.headers["location"])
        self.s.expire_all()
        gewerk = (self.s.query(Gewerk).filter(Gewerk.angebot_id == angebot.id)
                  .order_by(Gewerk.id.desc()).first())
        self.assertIsNotNone(gewerk)
        self.assertEqual((gewerk.sparte, gewerk.phase), ("KL", "auftragseingang"))
        self.assertEqual(gewerk.auftragswert_original, angebot.summen()["endbetrag"])
        self.assertEqual(self.s.get(Angebot, angebot.id).projekt_gewerk_id, gewerk.id)
        self.assertEqual(self.client.get(r.headers["location"]).status_code, 200)
        # Steckbrief-Felder der Sparte KL (feste Felder + Auftragsdaten-Felder des
        # Blatts Steckbrief; „Besonderheiten“ bleibt letzte Zeile)
        felder = [k for k, _ in kern.steckbrief_felder("KL")]
        self.assertEqual((felder[0], felder[-1]), ("geraete", "besonderheiten"))

    def test_versionen_und_kopien_behalten_kl_json(self):
        angebot = self.angebot_direkt(fall_a())
        angebot_status_setzen(angebot, "Versendet")
        self.s.commit()
        version = angebot_aufbau.version_erzeugen(self.s, angebot)
        self.assertEqual((version.konfigurator_typ, version.ust_satz), ("KL", 19.0))
        self.assertEqual(json.loads(version.kl_json)["aussengeraete"][0]["kombination"],
                         "9+9+9")
        self.assertEqual(version.summen()["netto"], 651866)


# --- Fall B -----------------------------------------------------------------------

class FallB(Basis):
    ERWARTET = [("KL020", 1.0, 158700), ("KL019", 1.0, 52900), ("KL016", 1.0, 35600),
                ("KL014", 1.0, 16900), ("KL017", 5.0, 6800), ("KL050", 1.0, 49900),
                ("KL001", 1.0, 22900), ("KL035", 1.0, 178600), ("KL049", 1.0, 0),
                ("", 1.0, 0)]

    def test_fall_b(self):
        antworten = fall_b()
        sichtbar = {f.id for f in engine.sichtbare_fragen(self.logik, antworten)}
        self.assertNotIn("KE02", sichtbar)                       # KE01 = Ja
        self.assertNotIn("KE03", sichtbar)
        e = self.erfassung_anlegen(antworten)
        self.assertEqual(self.absenden(e).status_code, 200)
        self.assertEqual((e.ampel, e.status), ("gruen", "Neu"))
        angebot = self.angebot_erzeugen(e)
        pos = angebot.positionen
        self.assertEqual([(p.pos_nr, p.menge, p.e_preis_cent) for p in pos], self.ERWARTET)
        self.assertFalse(any(p.ep_flag for p in pos))
        self.assertEqual(mengen(pos)["KL017"], 5)                 # 6–10 m → +5 m
        self.assertNotIn("KL013", mengen(pos))                    # KO08 = Nein
        self.assertNotIn("KL008", mengen(pos))                    # KE01 = Ja → KL001
        self.assertEqual([p.gruppe for p in pos], [""] * 7 + [GRUPPE] * 3)
        self.assertEqual(pos[-1].bezeichnung, AUSLEGUNGSZEILE)
        self.assertIn("Raum 1 „Wohnküche“: 30,0 m² × 1,1 × 90 W/m² = 2,97 kW → Innengerät "
                      "3,5 kW (Klasse 12), Außengerät 1", pos[-1].beschreibung)
        self.assertIn("Außengerät 1: Klimaanlage Bosch Single-Split, Single-Split, 1 Innengerät",
                      pos[-1].beschreibung)                        # 1. Zeile des Artikels KL035
        su = angebot.summen()
        self.assertEqual((su["netto"], su["ust"], su["brutto"]), (549500, 104405, 653905))
        kl = json.loads(angebot.kl_json)
        self.assertEqual((kl["aussengeraete"][0]["typ"], kl["aussengeraete"][0]["artikel"],
                          kl["montage_ref"]), ("single", ["KL035"], "KL020"))

    def test_fall_b_pdf(self):
        text = self.pdf_text(self.angebot_direkt(fall_b()))
        self.assertIn(GRUPPE, text)
        self.assertIn("19,00 % USt.", text)
        self.assertIn("5.495,00", text)
        self.assertIn("1.044,05", text)
        self.assertIn("6.539,05", text)
        self.assertIn("Rollgerüst", text)
        self.assertLess(text.index("Systemgarantie"), text.index(AUSLEGUNGSZEILE))
        self.assertLess(text.index(AUSLEGUNGSZEILE), text.index("Netto-Summe"))
        self.assertNotIn("EP.", text)                             # Fall B ohne EP-Zeile
        for verboten in ("KfW", "Wirtschaftlichkeit", "Vollmacht"):
            self.assertNotIn(verboten, text)


# --- Fall C -----------------------------------------------------------------------

class FallC(Basis):
    def test_fall_c_montagematrix_ampel(self):
        self.assertEqual(engine.ampel_gruende(self.logik, fall_c()), [G6_C])
        e = self.erfassung_anlegen(fall_c())
        self.assertEqual(self.absenden(e).status_code, 200)
        self.assertEqual((e.ampel, e.status, e.gruende_text),
                         ("orange", "Individuell – zu prüfen", G6_C))
        # Protokoll zeigt beide Kombinationen (Seite „Auslegung“)
        prot = engine.protokoll(self.logik, fall_c())
        auslegung = [z for z in prot if z["seite"] == "Auslegung"]
        texte = " | ".join(z["antwort"] for z in auslegung)
        self.assertIn("CL5000M 53/2 E", texte)
        self.assertIn("Kombination 12+18", texte)
        self.assertIn("CL5000M 79/3 E", texte)
        self.assertIn("Kombination 9+9+9", texte)
        montage = [z for z in auslegung if z["frage"] == "Montage"][0]
        self.assertEqual(montage["ampel_grund"], G6_C)
        # Protokoll-PDF (Erfassung) und Vorgangsakte/Erfassungsliste
        r = self.client.get(f"/erfassungen/{e.id}/protokoll.pdf")
        self.assertEqual(r.status_code, 200)
        text = pdf_text_aus_bytes(r.content)
        self.assertIn("Kombination 12+18", text)
        self.assertIn("Kombination 9+9+9", text)
        self.assertIn(G6_C, text.replace("\n", " "))
        r = self.client.get(f"/erfassungen/{e.id}")
        self.assertEqual(r.status_code, 200)
        self.assertIn(G6_C, r.text)
        # „Erneut prüfen“ bleibt orange mit demselben Grund
        r = self.client.post(f"/erfassungen/{e.id}/erneut-pruefen", follow_redirects=False)
        self.assertEqual(r.status_code, 303)
        self.s.refresh(e)
        self.assertEqual((e.ampel, e.gruende_text), ("orange", G6_C))


# --- Fall D -----------------------------------------------------------------------

class FallD(Basis):
    def test_d1_serie_8000i_multi(self):
        self.assertEqual(engine.ampel_gruende(self.logik, fall_d1()), [G3_D1])
        e = self.erfassung_anlegen(fall_d1())
        self.absenden(e)
        self.assertEqual((e.ampel, e.gruende_text), ("orange", G3_D1))

    def test_d2_serie_7000i_gruen(self):
        self.assertEqual(engine.ampel_gruende(self.logik, fall_d2()), [])
        e = self.erfassung_anlegen(fall_d2())
        self.absenden(e)
        self.assertEqual((e.ampel, e.status), ("gruen", "Neu"))
        angebot = self.angebot_erzeugen(e)
        pos = angebot.positionen
        self.assertEqual([p.pos_nr for p in pos],
                         ["KL020", "KL008", "KL044", "KL042", "KL013", "KL049", ""])
        self.assertEqual(mengen(pos), {"KL020": 1, "KL008": 1, "KL044": 1, "KL042": 1,
                                       "KL013": 1, "KL049": 1})
        gateway = pos[4]
        self.assertEqual((gateway.pos_nr, gateway.menge, gateway.e_preis_cent,
                          bool(gateway.ep_flag)), ("KL013", 1.0, 8250, False))
        kl = json.loads(angebot.kl_json)
        self.assertEqual((kl["raeume"][0]["kuehllast_kw"], kl["raeume"][0]["klasse"]),
                         (3.0, "12"))
        self.assertEqual(kl["aussengeraete"][0]["artikel"], ["KL044", "KL042"])
        self.assertEqual(angebot.summen()["netto"],
                         158700 + 49800 + 131419 + 63590 + 8250)

    def test_d3_klasse_18_in_7000i(self):
        self.assertEqual(engine.ampel_gruende(self.logik, fall_d3()), [G2_D3])
        e = self.erfassung_anlegen(fall_d3())
        self.absenden(e)
        self.assertEqual((e.ampel, e.status, e.gruende_text),
                         ("orange", "Individuell – zu prüfen", G2_D3))
        kl = kl_auslegung.auslegen(self.logik, fall_d3())
        self.assertEqual((kl.raeume[0].kuehllast_kw, kl.raeume[0].klasse), (4.2, "18"))


# --- Fall E / F -------------------------------------------------------------------

class FallEF(Basis):
    def test_e_kuehllast(self):
        self.assertEqual(engine.ampel_gruende(self.logik, fall_e()), [G1_E])
        e = self.erfassung_anlegen(fall_e())
        self.absenden(e)
        self.assertEqual((e.ampel, e.gruende_text), ("orange", G1_E))
        a = kl_auslegung.auslegen(self.logik, fall_e())
        self.assertEqual((a.raeume[0].kuehllast_kw, a.raeume[0].klasse), (10.8, None))

    def test_f_kombination(self):
        self.assertEqual(engine.ampel_gruende(self.logik, fall_f()), [G4_F])
        e = self.erfassung_anlegen(fall_f())
        self.absenden(e)
        self.assertEqual((e.ampel, e.gruende_text), ("orange", G4_F))
        a = kl_auslegung.auslegen(self.logik, fall_f())
        self.assertEqual(([r.klasse for r in a.raeume], a.aussengeraete[0].kombination),
                         (["24", "24"], "24+24"))


# --- Fall G -----------------------------------------------------------------------

class FallG(Basis):
    def test_g_validierung_und_korrektur(self):
        antworten = fall_g()
        self.assertEqual(kl_auslegung.validierung(self.logik, antworten), [MELDUNG_G])
        e = self.erfassung_anlegen(antworten)
        r = self.absenden(e)
        self.assertEqual(r.status_code, 200)                      # Prüfseite mit Meldung
        self.assertIn(MELDUNG_G, r.text)
        self.assertIn("Bitte vor dem Absenden korrigieren", r.text)
        self.assertEqual((e.status, e.gruende_text), ("Entwurf", ""))   # nicht abgesendet
        self.assertIsNone(e.abgesendet_am)
        # Prüfseite zeigt die Meldung ebenfalls (vor dem Absenden)
        self.assertIn(MELDUNG_G, self.client.get(f"/erfassung/{e.id}/pruefen").text)
        # Korrektur: Raum 3 ans Außengerät 2 → grün (Montage 3/2 → KL024)
        antworten["KR07#3"] = "2"
        e.antworten_json = json.dumps(antworten, ensure_ascii=False)
        self.s.commit()
        r = self.absenden(e)
        self.assertEqual(r.status_code, 200)
        self.assertNotIn(MELDUNG_G, r.text)
        self.assertEqual((e.ampel, e.status), ("gruen", "Neu"))
        angebot = self.angebot_erzeugen(e)
        m = mengen(angebot.positionen)
        # Außengerät 1: Räume A+B (9+9 → CL5000M 53/2 E + 2 × KL026), Außengerät 2:
        # Raum C Single (KL034-Set); KL008 × Außengeräte; Montage 3/2 → KL024
        self.assertEqual((m.get("KL024"), m.get("KL037"), m.get("KL034"), m.get("KL026"),
                          m.get("KL008")), (1, 1, 1, 2, 2))
        kl = json.loads(angebot.kl_json)
        self.assertEqual(kl["montage_ref"], "KL024")
        self.assertEqual([(g["typ"], g["kombination"]) for g in kl["aussengeraete"]],
                         [("multi", "9+9"), ("single", "")])

    def test_g_raumflaeche_fehlt(self):
        antworten = fall_a()
        antworten["KR08#2"] = 0
        self.assertEqual(kl_auslegung.validierung(self.logik, antworten),
                         ["Raum 2: Raumfläche fehlt"])
        e = self.erfassung_anlegen(antworten)
        r = self.absenden(e)
        self.assertEqual(r.status_code, 200)
        self.assertIn("Raum 2: Raumfläche fehlt", r.text)
        self.assertEqual(e.status, "Entwurf")


# --- Fall H -----------------------------------------------------------------------

class FallH(Basis):
    def test_h_schraegdach_und_14a(self):
        self.assertEqual(engine.ampel_gruende(self.logik, fall_h()), [])
        e = self.erfassung_anlegen(fall_h())
        self.absenden(e)
        self.assertEqual((e.ampel, e.status), ("gruen", "Neu"))
        angebot = self.angebot_erzeugen(e)
        pos = angebot.positionen
        m = mengen(pos)
        self.assertEqual((m.get("KL004"), m.get("KL005"), m.get("KL006")), (1, 1, 1))
        self.assertNotIn("KL050", m)                              # Gerüst in den Dacharbeiten
        self.assertEqual((m.get("KL003"), m.get("KL025"), m.get("KL039"), m.get("KL026"),
                          m.get("KL013"), m.get("KL049"), m.get("KL008")),
                         (1, 1, 1, 4, 4, 1, 1))
        # Reihenfolge laut „Angebotsaufbau KL“: Block 1 Montage/Dach, Block 2 Elektro/§14a,
        # Block 3 Gruppe mit Außengerät, Innengeräten, Gateway, Garantie, Auslegungszeile
        self.assertEqual([p.pos_nr for p in pos],
                         ["KL025", "KL004", "KL005", "KL006", "KL008", "KL003",
                          "KL039", "KL026", "KL013", "KL049", ""])
        self.assertEqual([p.block_nr for p in pos], [1, 1, 1, 1, 2, 2, 3, 3, 3, 3, 3])
        kl = json.loads(angebot.kl_json)
        g = kl["aussengeraete"][0]
        self.assertEqual((g["kombination"], g["geraet"], g["p14a"]),
                         ("9+9+9+9", "CL5000M 105/4 E", True))

    def test_h_ohne_14a_parameter_kein_kl003(self):
        """Parameter „§14a-Außengeräte“ ohne „CL5000M 105/4 E“ → kein KL003 (Logik-Kopie,
        nicht die Excel)."""
        logik2 = copy.copy(self.logik)
        logik2.kl_parameter = dict(self.logik.kl_parameter)
        logik2.kl_parameter["§14a-Außengeräte"] = ("CL5000M 125/5 E", "")
        self.assertEqual(kl_auslegung.parameter(logik2)["p14a_geraete"], ["CL5000M 125/5 E"])
        pos = kl_auslegung.positionen_zusammenstellen(logik2, fall_h(), self.s)
        m = mengen(pos)
        self.assertNotIn("KL003", m)
        self.assertEqual((m.get("KL039"), m.get("KL025"), m.get("KL004")), (1, 1, 1))
        angebot = self.angebot_direkt(fall_h(), logik=logik2)
        self.assertNotIn("KL003", {p.pos_nr for p in angebot.positionen})
        self.assertFalse(json.loads(angebot.kl_json)["aussengeraete"][0]["p14a"])
        # Gegenprobe mit der Live-Logik: KL003 vorhanden
        self.assertEqual(mengen(kl_auslegung.positionen_zusammenstellen(
            self.logik, fall_h(), self.s)).get("KL003"), 1)

    def test_h_ohne_schraegdach_rollgeruest(self):
        antworten = bogen([raum(f"Raum {i}", 40) for i in range(1, 5)],
                          KZ01="Gerüst erforderlich")
        m = mengen(kl_auslegung.positionen_zusammenstellen(self.logik, antworten, self.s))
        self.assertEqual(m.get("KL050"), 1)
        self.assertNotIn("KL004", m)


# --- Regression Phase 116: Freitext-Schiene, Anhänge, Profile ------------------------

class Regression(Basis):
    def test_freitext_kl_bleibt_taifun_schiene(self):
        r = self.client.post("/erfassung/sparten-start",
                             data={"kunde_id": str(self.kunde.id), "sparte_KL": "on"},
                             follow_redirects=False)
        self.assertEqual(r.status_code, 303)
        self.s.expire_all()
        e = (self.s.query(Erfassung)
             .filter(Erfassung.kunde_id == self.kunde.id, Erfassung.sparte == "KL")
             .order_by(Erfassung.id.desc()).first())
        self.assertEqual(self.client.get(f"/erfassung/{e.id}/freitext").status_code, 200)
        r = self.client.post(f"/erfassung/{e.id}/freitext",
                             data={"freitext": "Sonderfall: Kanalgerät im Büro, "
                                               "Außengerät auf dem Garagendach."},
                             follow_redirects=False)
        self.assertEqual(r.status_code, 200)
        self.s.refresh(e)
        self.assertEqual((e.typ, e.ampel, e.status),
                         ("freitext", "orange", "In TAIFUN zu schreiben"))
        self.assertEqual(self.client.get(f"/erfassungen/{e.id}").status_code, 200)
        self.assertEqual(self.client.get(f"/erfassungen/{e.id}/protokoll.pdf").status_code,
                         200)

    def test_anhaenge_und_vollmacht(self):
        """Anhänge: „immer“-Regeln greifen; der Platzhalter „(Bosch Climate Broschüre –
        Zulieferung)“ wird wie der PV-Platzhalter übersprungen, bis die Datei in
        anlagen/ liegt – die Regel „wenn Sparte = KL“ greift dann nur für KL-Angebote."""
        from app import anhaenge
        from app.logik import Anhang
        angebot = self.angebot_direkt(fall_a())
        dateien = [x.datei for x in anhaenge.fuer_angebot(self.logik_voll, angebot)]
        self.assertIn("Friondo Unternehmenspräsentation.pdf", dateien)
        self.assertIn("Broschüre Ratenkauf.pdf", dateien)
        self.assertNotIn("Friondo HEMS.pdf", dateien)
        self.assertFalse([d for d in dateien if d.startswith("(")])
        logik2 = copy.copy(self.logik_voll)
        logik2.anhaenge = list(self.logik_voll.anhaenge) + [
            Anhang("Bosch Climate Broschüre.pdf", "wenn Sparte = KL", "sparte", antwort="KL")]
        self.assertIn("Bosch Climate Broschüre.pdf",
                      [x.datei for x in anhaenge.fuer_angebot(logik2, angebot)])
        wp = angebot_aufbau.angebot_anlegen(self.s, self.kunde.id)
        self.assertNotIn("Bosch Climate Broschüre.pdf",
                         [x.datei for x in anhaenge.fuer_angebot(logik2, wp)])
        # Ratenkauf nicht bei Enni/SWD (unverändert)
        self.assertNotIn("Broschüre Ratenkauf.pdf",
                         [x.datei for x in anhaenge.fuer_angebot(self.logik_voll, angebot,
                                                                  profil_name="Enni")])
        self.assertFalse(anhaenge.vollmacht_erforderlich(angebot))
        self.assertFalse(pdf_export.foerderblock_moeglich(angebot))
        self.assertIsNone(pdf_export.wirtschaftlichkeit_fuer(self.s, angebot))

    def test_enni_profil_ohne_positionsregeln(self):
        from app import angebotsprofile
        kunde = Kunde(nachname="KL-Test v24 Enni", email=TEST_EMAIL,
                      vertriebskanal="Enni Energie")
        self.s.add(kunde)
        self.s.commit()
        angebot = angebot_aufbau.angebot_anlegen(self.s, kunde.id, antworten=fall_a(),
                                                 logik=self.logik, sparte="KL")
        nummern = {p.pos_nr for p in angebot.positionen}
        self.assertFalse({"014", "015", "016", "017", "162"} & nummern)
        self.assertEqual(angebot.summen()["netto"], 651866)
        text = angebotsprofile.nachtext_fuer_angebot(self.s, angebot)
        self.assertIn("Enni Contracting", text)
        self.assertIn("Hinweis zur Kältetechnik", text)
        self.assertNotIn("KfW", text)
        self.assertNotIn("[WIRTSCHAFTLICHKEIT]", text)

    def test_statistik_und_meine_angebote_rendern(self):
        angebot = self.angebot_direkt(fall_a())
        angebot_status_setzen(angebot, "Versendet")
        self.s.commit()
        for pfad in ("/statistik", "/meine-angebote", "/angebote", "/erfassungen",
                     f"/angebote/{angebot.id}/protokoll.pdf", "/parametrierung/kl-logik"):
            r = self.client.get(pfad)
            self.assertEqual(r.status_code, 200, pfad)


# --- Prüfer F (Phase 116/117): Texte Zeichen für Zeichen, Excel-Steuerung, Reihenfolge,
# Rechenweg-Grenzen, Mengenregeln, Oberfläche --------------------------------------------

G5_TEXT = "Mehr als 5 Innengeräte an Außengerät 1"
G7_TEXT = "Leitungslänge über 15 m: Raum 2 Schlafzimmer – max. Leitungslänge der Serie prüfen"
G8_TEXT = "Elektrozuleitung über 15 m"
HINWEISE_PLAN = {
    ("KO03", "Nein, Zustimmung noch nicht vorhanden"): "Zustimmung des Eigentümers einholen",
    ("KO01", "Gewerbe"): "Gewerbeobjekt – Auslegung prüfen",
    ("KR04", "Innenwand"): ("Raum <Nr> <Name>: Innengerät an Innenwand – Leitungsführung und "
                           "Kondensatablauf prüfen"),
    ("KR03", "regelmäßig heizen und kühlen"): ("Raum <Nr> <Name>: Heizbetrieb als Hauptzweck – "
                                               "Serie 7000i/8000i empfohlen"),
    ("KA01", "auf einem Flachdach"): ("Flachdach – keine Dachdurchführung, Leitungsführung über "
                                      "Attika/Fassade prüfen"),
    ("KA01", "noch unklar"): "Montageort Außengerät klären",
    ("KA02", "über 4 m"): "Montagehöhe über 4 m ohne Gerüst/Bühne prüfen",
    ("KE01", "Unklar"): "Stromversorgung am Außengerät prüfen",
}
FRAGEN_HINWEISE_PLAN = {
    "KO05": "öffnet je Raum einen eigenen Fragenblock (höchstens 12 Räume)",
    "KO06": ("Vorbelegung Climate 3200i. Climate 7000i: nur bis 3,4 kW je Raum · Climate 8000i: "
             "nur Single-Split bis 3,5 kW"),
    "KO08": "Vorbelegung „als Eventualposition“ – Gateway je Innengerät",
    "KO09": "z. B. abweichende Montageorte bei mehreren Außengeräten",
    "KR01": "z. B. Wohnzimmer",
    "KR08": "Grundfläche des Raums (Dezimalzahl möglich, z. B. 22,5)",
    "KR05": "bis 5 m je Innengerät in der Montagepauschale enthalten",
    "KR07": "es erscheinen nur so viele Optionen wie Außengeräte (KO04)",
    "KA01": "gilt für alle Außengeräte – abweichende Orte in der Bemerkung (KO09)",
    "KZ01": "bei Montage auf dem Schrägdach ist das Gerüst in den Dacharbeiten enthalten",
    "S01": "Startwert der Angebotsverfolgung (Hot-Ampel)",
    "S02": "optional – leer lassen, wenn keine Wiedervorlage nötig",
}
FRAGEN_REIHENFOLGE_PLAN = ["KO01", "KO02", "KO03", "KO06", "KO04", "KO05", "KO07", "KO08", "KO09",
                           "KR01", "KR08", "KR09", "KR10", "KR02", "KR03", "KR04", "KR05", "KR06",
                           "KR11", "KR07", "KA01", "KA02", "KE01", "KE02", "KE03", "KZ01",
                           "S01", "S02"]


def hinweis_bogen() -> dict:
    """Bogen mit allen Hinweis-Auslösern: Eigentümer, Gewerbe, Innenwand (Raum 1),
    Heizbetrieb (Raum 2), Flachdach, Strom unklar."""
    return bogen([raum("Wohnen", 20, ort="Innenwand"),
                  raum("Schlafen", 20, zweck="regelmäßig heizen und kühlen")],
                 KO01="Gewerbe", KO03="Nein, Zustimmung noch nicht vorhanden",
                 KA01="auf einem Flachdach", KE01="Unklar")


HINWEISE_ERWARTET = [
    "Zustimmung des Eigentümers einholen",
    "Gewerbeobjekt – Auslegung prüfen",
    "Raum 1 Wohnen: Innengerät an Innenwand – Leitungsführung und Kondensatablauf prüfen",
    "Raum 2 Schlafen: Heizbetrieb als Hauptzweck – Serie 7000i/8000i empfohlen",
    "Flachdach – keine Dachdurchführung, Leitungsführung über Attika/Fassade prüfen",
    "Stromversorgung am Außengerät prüfen",
]


class PrueferF(Basis):
    """Adversariale Nachprüfung (Agent F): Texte Zeichen für Zeichen gegen PLAN_V16
    Phase 113/114, Prozesswissen aus der Excel (Hinweis-Zeilen, Paketmatrix-Ampeltexte),
    Außengerät-Reihenfolge in Block 3, Rechenweg-Grenzen, Mengenregeln, Oberfläche."""

    def positionen(self, antworten: dict, logik=None) -> list[dict]:
        return kl_auslegung.positionen_zusammenstellen(logik or self.logik, antworten, self.s)

    def test_texte_woertlich_phase_114(self):
        # Ampel-Gründe G1–G8 + Gewerbe-Ampel (Konstanten mit Platzhaltern gefüllt)
        self.assertEqual(kl_auslegung.G1.format(max="7,0", raum="Raum 1 Studio", kw="10,80"), G1_E)
        self.assertEqual(kl_auslegung.G2.format(code="18", serie="Climate 7000i"), G2_D3)
        self.assertEqual(kl_auslegung.G3.format(serie="Climate 8000i"), G3_D1)
        self.assertEqual(kl_auslegung.G4.format(codes="24+24", n=1), G4_F)
        self.assertEqual(kl_auslegung.G5.format(max=5, n=1), G5_TEXT)
        self.assertEqual(kl_auslegung.G6.format(innen=5, aussen=2), G6_C)
        self.assertEqual(kl_auslegung.G7.format(raum="Raum 2 Schlafzimmer"), G7_TEXT)
        self.assertEqual(kl_auslegung.G8, G8_TEXT)
        self.assertEqual(kl_auslegung.GEWERBE_AMPEL, "Gewerbeobjekt – individuelle Auslegung")
        # Validierungsmeldungen (Absenden)
        self.assertEqual(kl_auslegung.MELDUNG_AUSSEN_OHNE_RAUM.format(n=2), MELDUNG_G)
        self.assertEqual(kl_auslegung.MELDUNG_FLAECHE_FEHLT.format(nr=3), "Raum 3: Raumfläche fehlt")
        self.assertEqual(kl_auslegung.AUSLEGUNGSZEILE, "Auslegung der Klimaanlage")
        # Hinweis-Konstanten (Fallback im Code) = Plan
        self.assertEqual(
            [kl_auslegung.HINWEIS_EIGENTUEMER, kl_auslegung.HINWEIS_GEWERBE,
             kl_auslegung.HINWEIS_INNENWAND.format(raum="Raum 1 Wohnen"),
             kl_auslegung.HINWEIS_HEIZEN.format(raum="Raum 2 Schlafen"),
             kl_auslegung.HINWEIS_FLACHDACH, kl_auslegung.HINWEIS_STROM],
            HINWEISE_ERWARTET)
        self.assertEqual((kl_auslegung.HINWEIS_UNKLAR, kl_auslegung.HINWEIS_HOEHE,
                          kl_auslegung.HINWEIS_RAEUME),
                         ("Montageort Außengerät klären",
                          "Montagehöhe über 4 m ohne Gerüst/Bühne prüfen",
                          "Mehr als 12 Räume – Rest händisch"))
        # Blatt „Aktionen KL“: Hinweis-Zeilen (typ hinweis) und AMPEL-Zeilen der Fragen
        # tragen die Plan-Texte (Platzhalter <Nr> <Name> je Raum-Klon), Zusatzbedingung KA02
        hinweise = {(a.frage, a.antwort): a.ampel_grund for a in self.logik.kl_aktionen
                    if a.typ == "hinweis"}
        self.assertEqual(hinweise, HINWEISE_PLAN)
        ka02 = [a for a in self.logik.kl_aktionen if a.frage == "KA02" and a.typ == "hinweis"][0]
        self.assertEqual(ka02.zusatz_bedingung.roh, "nur wenn KZ01 = vom Boden/Leiter")
        ampeln = {(a.frage, a.antwort): a.ampel_grund for a in self.logik.kl_aktionen
                  if a.typ == "ampel" and a.frage not in logik_modul.KL_SPEZIAL}
        self.assertEqual(ampeln, {
            ("KR05", "über 15 m"): ("Leitungslänge über 15 m: Raum <Nr> <Name> – max. "
                                    "Leitungslänge der Serie prüfen"),
            ("KE02", "über 15 m"): G8_TEXT})
        # Paketmatrix-Bemerkungen „→ AMPEL: …“ = G2/G3 mit Platzhaltern
        self.assertEqual({z.ampel_grund for z in self.logik.kl_paket if z.nicht_im_sortiment},
                         {"Klasse <Code> in Serie <Serie> nicht verfügbar – Serie wechseln",
                          "Multi-Split in Serie Climate 8000i nicht verfügbar"})
        # Hinweis-Zeilen erzeugen nie Positionen, AMPEL-Zeilen keine Artikel
        for a in self.logik.kl_aktionen:
            if a.typ in ("hinweis", "ampel"):
                self.assertEqual(a.artikel, [], (a.frage, a.antwort))

    def test_fragen_kl_woertlich_und_zusatzbedingungen_ohne_ungleich(self):
        f = self.logik.fragen
        self.assertEqual(list(f), FRAGEN_REIHENFOLGE_PLAN)
        for fid, frage in f.items():
            self.assertEqual(frage.hinweis, FRAGEN_HINWEISE_PLAN.get(fid, ""), fid)
        self.assertEqual(f["KE02"].bedingung.roh, "nur wenn KE01 = Nein oder Unklar")
        self.assertEqual(f["KE03"].bedingung.roh, "nur wenn KE01 = Nein oder Unklar")
        self.assertEqual(f["KR05"].antworten, ["bis 5 m", "6–10 m", "11–15 m", "über 15 m"])
        self.assertEqual(f["KA02"].antworten, ["unter 2 m", "2–4 m", "über 4 m"])
        self.assertEqual(f["KE02"].antworten, ["0–5 m", "6–10 m", "11–15 m", "über 15 m"])
        self.assertEqual(f["KR11"].antworten, ["Außenwand bis 32 cm (in Pauschale)",
                                               "Beton oder dicker als 32 cm", "kein Durchbruch nötig"])
        # Seiten: KO06 vor KO04 auf „Objekt & Anlage“, Raumfragen als Wiederholgruppe
        self.assertLess(f["KO06"].reihenfolge, f["KO04"].reihenfolge)
        self.assertEqual(self.logik.seiten, ["Objekt & Anlage", "Räume", "Außengerät",
                                             "Elektroinstallation", "Zugänglichkeit",
                                             "Einschätzung"])
        # Zusatzbedingungen ohne „≠“ – alle parsebar (Lader meldet sonst Fehler)
        zusatz = [a for a in self.logik.kl_aktionen if a.zusatz_bedingung is not None]
        self.assertTrue(zusatz)
        for a in self.logik.kl_aktionen:
            self.assertNotIn("≠", a.antwort + a.aktion_roh + (a.zusatz_bedingung.roh
                                                               if a.zusatz_bedingung else ""))
        kl050 = [a for a in self.logik.kl_aktionen
                 if a.frage == "KZ01" and a.antwort == "Gerüst erforderlich"][0]
        self.assertEqual(kl050.zusatz_bedingung.roh,
                         "nur wenn KA01 = auf dem Boden oder an der Außenwand oder auf einer "
                         "Terrasse oder auf einem Balkon oder auf einem Flachdach oder noch unklar")
        self.assertEqual([r.ref for r in kl050.artikel], ["KL050"])
        # „Beton“ (Präfix-Alias) trifft die Option „Beton oder dicker als 32 cm“ – Raum-Klon
        klon = engine._wiederhol_klone(f["KR11"], {"KO05": 1}, f)[0]
        treffer = engine.aktion_finden(self.logik, klon, "Beton oder dicker als 32 cm", {})
        self.assertEqual([r.ref for r in treffer[0].artikel], ["KL014"])
        for option in ("kein Durchbruch nötig", "Außenwand bis 32 cm (in Pauschale)"):
            treffer = engine.aktion_finden(self.logik, klon, option, {})
            self.assertEqual((treffer[0].aktion_roh, treffer[0].artikel), ("–", []), option)

    def test_auslegungs_text_woertlich(self):
        namen = kl_auslegung.artikel_namen(self.s)
        a = kl_auslegung.auslegen(self.logik, fall_a(), namen)
        self.assertEqual(kl_auslegung.auslegungs_text(a).split("\n"), [
            "Auslegung Klimaanlage – Serie Bosch Climate 3200i",
            "Raum 1 „Wohnzimmer“: 25,0 m² × 1,0 × 60 W/m² = 1,50 kW → Innengerät 2,6 kW "
            "(Klasse 9), Außengerät 1",
            "Raum 2 „Schlafzimmer“: 18,0 m² × 1,0 × 60 W/m² = 1,08 kW → Innengerät 2,6 kW "
            "(Klasse 9), Außengerät 1",
            "Raum 3 „Büro“: 28,0 m² × 1,0 × 60 W/m² = 1,68 kW → Innengerät 2,6 kW (Klasse 9), "
            "Außengerät 1",
            "Außengerät 1: BOSCH Klimagerät CL5000M 79/3 E, Multi-Split, Kombination 9+9+9, "
            "3 Innengeräte",
            "Montage: 3 Innengeräte / 1 Außengerät (Pauschale). Leitungslänge bis 5 m je "
            "Innengerät enthalten.",
            "Auslegung nach Raumfläche; verbindliche Festlegung in der technischen Feinplanung "
            "vor Ort."])
        b = kl_auslegung.auslegungs_text(kl_auslegung.auslegen(self.logik, fall_b(), namen))
        self.assertEqual(b.split("\n")[1:4], [
            "Raum 1 „Wohnküche“: 30,0 m² × 1,1 × 90 W/m² = 2,97 kW → Innengerät 3,5 kW "
            "(Klasse 12), Außengerät 1",
            "Außengerät 1: Klimaanlage Bosch Single-Split, Single-Split, 1 Innengerät",
            "Montage: 1 Innengerät / 1 Außengerät (Pauschale). Leitungslänge bis 5 m je "
            "Innengerät enthalten."])
        # Protokoll-Seite „Auslegung“ (Fall C: beide Außengeräte mit Gerät und Kombination)
        prot = kl_auslegung.protokoll_zeilen(self.logik, fall_c())
        self.assertEqual([z["antwort"] for z in prot if z["frage"].startswith("Außengerät")], [
            "CL5000M 53/2 E · Multi-Split, Kombination 12+18 · 2 Innengeräte (Raum 1, 2)",
            "CL5000M 79/3 E · Multi-Split, Kombination 9+9+9 · 3 Innengeräte (Raum 3, 4, 5)"])
        self.assertEqual(prot[-1]["antwort"], "5 Innengeräte / 2 Außengeräte – nicht hinterlegt")

    def test_hinweise_aus_excel_zeilen(self):
        """Fachliche Hinweise kommen aus den Zeilen „Hinweis: <Text>“ des Blatts
        „Aktionen KL“ (Regel 3: Prozesswissen in der Excel); ohne solche Zeilen gelten
        die Konstanten im Code – beide identisch mit PLAN_V16 Phase 114."""
        antworten = hinweis_bogen()
        self.assertIsNotNone(kl_auslegung._hinweise_aus_aktionen(self.logik, antworten))
        self.assertEqual(kl_auslegung.fachliche_hinweise(self.logik, antworten), HINWEISE_ERWARTET)
        self.assertEqual(engine.fachliche_hinweise(antworten, self.logik), HINWEISE_ERWARTET)
        # aus dem gespeicherten Protokoll (Anzeige-Strings, Logik aus dem Cache)
        self.assertEqual(engine.hinweise_aus_protokoll(engine.protokoll(self.logik, antworten)),
                         HINWEISE_ERWARTET)
        self.assertEqual(kl_auslegung.auslegen(self.logik, antworten).hinweise, HINWEISE_ERWARTET)
        # Zusatzbedingung der KA02-Zeile: nur bei KZ01 = vom Boden/Leiter
        self.assertEqual(kl_auslegung.fachliche_hinweise(
            self.logik, bogen([raum("R", 20)], KA01="noch unklar", KA02="über 4 m")),
            ["Montageort Außengerät klären", "Montagehöhe über 4 m ohne Gerüst/Bühne prüfen"])
        self.assertEqual(kl_auslegung.fachliche_hinweise(
            self.logik, bogen([raum("R", 20)], KA02="über 4 m", KZ01="Gerüst erforderlich")), [])
        self.assertEqual(kl_auslegung.fachliche_hinweise(self.logik, bogen([raum("R", 20)], KO05=13)),
                         ["Mehr als 12 Räume – Rest händisch"])
        # Text in der Excel geändert → der Hinweis folgt der Excel (Logik-Kopie)
        logik2 = copy.copy(self.logik)
        logik2.kl_aktionen = [copy.copy(a) for a in self.logik.kl_aktionen]
        for a in logik2.kl_aktionen:
            if a.typ == "hinweis" and a.frage == "KO03":
                a.ampel_grund = "Eigentümer-Zustimmung nachreichen (Test)"
        self.assertEqual(kl_auslegung.fachliche_hinweise(logik2, antworten),
                         ["Eigentümer-Zustimmung nachreichen (Test)"] + HINWEISE_ERWARTET[1:])
        # ohne Hinweis-Zeilen: Fallback auf die Konstanten – gleiche Texte
        logik3 = copy.copy(self.logik)
        logik3.kl_aktionen = [a for a in self.logik.kl_aktionen if a.typ != "hinweis"]
        self.assertIsNone(kl_auslegung._hinweise_aus_aktionen(logik3, antworten))
        self.assertEqual(kl_auslegung.fachliche_hinweise(logik3, antworten), HINWEISE_ERWARTET)
        # Gewerbe-Verhalten AMPEL: Ampel statt Hinweis (Excel-Zeile KO01 wird übersprungen)
        logik4 = copy.copy(self.logik)
        logik4.kl_parameter = dict(self.logik.kl_parameter)
        logik4.kl_parameter["Gewerbe-Verhalten"] = ("AMPEL", "")
        gewerbe = bogen([raum("R", 20)], KO01="Gewerbe")
        self.assertEqual(kl_auslegung.fachliche_hinweise(logik4, gewerbe), [])
        self.assertEqual(engine.ampel_gruende(logik4, gewerbe),
                         ["Gewerbeobjekt – individuelle Auslegung"])
        self.assertEqual(kl_auslegung.fachliche_hinweise(self.logik, gewerbe),
                         ["Gewerbeobjekt – Auslegung prüfen"])
        self.assertEqual(engine.ampel_gruende(self.logik, gewerbe), [])

    def test_paketmatrix_ampeltext_aus_bemerkung(self):
        """G2/G3: Text aus der Bemerkung der Paketmatrix nach „→ AMPEL: “ (Platzhalter
        <Code>/<Serie>); ohne Bemerkung die wörtlichen Standardtexte."""
        logik2 = copy.copy(self.logik)
        logik2.kl_paket = [copy.copy(z) for z in self.logik.kl_paket]
        for z in logik2.kl_paket:
            if z.nicht_im_sortiment:
                z.ampel_grund = "Test: <Code> in <Serie> fehlt"
        self.assertEqual(kl_auslegung.ampel_gruende(logik2, fall_d3()),
                         ["Test: 18 in Climate 7000i fehlt"])
        self.assertEqual(kl_auslegung.ampel_gruende(logik2, fall_d1()),
                         ["Test: <Code> in Climate 8000i fehlt"])
        for z in logik2.kl_paket:
            z.ampel_grund = ""
        self.assertEqual(kl_auslegung.ampel_gruende(logik2, fall_d3()), [G2_D3])
        self.assertEqual(kl_auslegung.ampel_gruende(logik2, fall_d1()), [G3_D1])
        # 8000i Single Klasse 18 (Zelle „nicht im Sortiment“) → G2 mit Serie 8000i
        self.assertEqual(engine.ampel_gruende(self.logik, bogen([raum("R", 70)], KO06="Climate 8000i")),
                         ["Klasse 18 in Serie Climate 8000i nicht verfügbar – Serie wechseln"])
        # 7000i Multi mit Klasse 18 (keine Multi-Innengerät-Zeile) → G2
        zwei = bogen([raum("A", 70), raum("B", 20)], KO06="Climate 7000i")
        self.assertEqual(engine.ampel_gruende(self.logik, zwei), [G2_D3])

    def test_block3_aussengeraete_in_aussengeraet_reihenfolge(self):
        """Phase 114: Außengeräte/Sets in Außengerät-Reihenfolge, dann Innengeräte je
        Klasse gebündelt – auch wenn das Set von Außengerät 2 im Blatt vor dem
        Multi-Außengerät von Außengerät 1 steht."""
        g = fall_g()
        g["KR07#3"] = "2"
        self.assertEqual([(p["pos_nr"], p["menge"]) for p in self.positionen(g)],
                         [("KL024", 1.0), ("KL008", 2.0), ("KL037", 1.0), ("KL034", 1.0),
                          ("KL026", 2.0), ("KL013", 3.0), ("KL049", 1.0), ("", 1.0)])
        # zwei 7000i-Singles (Klasse 9 an AG 1, Klasse 12 an AG 2): Außengeräte zuerst,
        # danach die Innengeräte je Klasse, Montage 2/2
        z = bogen([raum("A", 30, zuordnung="1"), raum("B", 50, zuordnung="2")],
                  KO04="2", KO06="Climate 7000i")
        self.assertEqual(engine.ampel_gruende(self.logik, z), [])
        self.assertEqual([p["pos_nr"] for p in self.positionen(z)],
                         ["KL022", "KL008", "KL043", "KL044", "KL041", "KL042", "KL013", "KL049", ""])
        # zwei gleiche Single-Sets werden im Block addiert
        z2 = bogen([raum("A", 20, zuordnung="1"), raum("B", 20, zuordnung="2")], KO04="2")
        m = mengen(self.positionen(z2))
        self.assertEqual((m.get("KL034"), m.get("KL022"), m.get("KL008"), m.get("KL013")),
                         (2, 1, 2, 2))
        # Fälle A/B/H unverändert
        self.assertEqual([p["pos_nr"] for p in self.positionen(fall_a())],
                         ["KL023", "KL008", "KL038", "KL026", "KL013", "KL049", ""])
        self.assertEqual([p["pos_nr"] for p in self.positionen(fall_h())],
                         ["KL025", "KL004", "KL005", "KL006", "KL008", "KL003", "KL039", "KL026",
                          "KL013", "KL049", ""])
        # Auslegungszeile ist immer die letzte Zeile des Gruppen-Blocks (Gruppe gesetzt)
        letzte = self.positionen(g)[-1]
        self.assertEqual((letzte["bezeichnung"], letzte["gruppe"], letzte["block_nr"],
                          letzte["einheit"], letzte["e_preis_cent"], letzte["ep_flag"]),
                         (AUSLEGUNGSZEILE, GRUPPE, 3, "psl.", 0, False))

    def test_rechenweg_grenzen_rundung_kombinationssuche(self):
        p = kl_auslegung.parameter(self.logik)
        self.assertEqual(p["fehlende"], [])
        self.assertEqual(p["klassen"], [("9", 2.6), ("12", 3.5), ("18", 5.3), ("24", 7.0)])
        self.assertEqual((p["w_qm_normal"], p["w_qm_stark"], p["leitung_inklusive_m"],
                          p["max_innen_je_aussen"], p["max_aussen"], p["p14a_geraete"]),
                         (60.0, 90.0, 5.0, 5, 3, ["CL5000M 105/4 E", "CL5000M 125/5 E"]))
        self.assertEqual(p["hoehenfaktor"], {"bis 2,5 m": 1.0, "2,5–3 m": 1.1, "über 3 m": 1.2})
        # Rundung kaufmännisch auf 2 Stellen (Decimal): 30 × 1,1 × 90 = 2,97 (kein 2,9699…)
        self.assertEqual(kl_auslegung.kuehllast(30, 1.1, 90), 2.97)
        self.assertEqual(kl_auslegung.kuehllast(43.33, 1.0, 60), 2.6)     # 2,5998 → 2,60
        self.assertEqual(kl_auslegung.kuehllast(43.34, 1.0, 60), 2.6)     # 2,6004 → 2,60
        self.assertEqual(kl_auslegung.kuehllast(43.42, 1.0, 60), 2.61)
        self.assertEqual(kl_auslegung.kuehllast(20.875, 1.0, 60), 1.25)   # 1,2525 → 1,25
        self.assertEqual(kl_auslegung.kuehllast(20.9, 1.0, 60), 1.25)     # 1,254 → 1,25
        self.assertEqual(kl_auslegung.kuehllast(20.92, 1.0, 60), 1.26)    # 1,2552 → 1,26
        # Klasse = kleinste Grenze ≥ Kühllast (Grenze eingeschlossen), darüber None (G1)
        self.assertEqual([kl_auslegung.klasse_fuer(kw, p["klassen"]) for kw in
                          (0.1, 2.6, 2.61, 3.5, 3.51, 5.3, 5.31, 7.0)],
                         ["9", "9", "12", "12", "18", "18", "24", "24"])
        self.assertIsNone(kl_auslegung.klasse_fuer(7.01, p["klassen"]))
        # Grenzfälle über den Bogen: 43,33 m² → 2,60 kW → Klasse 9 (KL034); 43,42 → 12 (KL035);
        # 116,66 m² normal → 7,00 kW → Klasse 24 (KL033 + KL029, A1); 117 m² → 7,02 kW → G1
        a = kl_auslegung.auslegen(self.logik, bogen([raum("Grenze", 43.33)]))
        self.assertEqual((a.raeume[0].kuehllast_kw, a.raeume[0].klasse, a.aussengeraete[0].artikel),
                         (2.6, "9", ["KL034"]))
        a = kl_auslegung.auslegen(self.logik, bogen([raum("Grenze", 43.42)]))
        self.assertEqual((a.raeume[0].kuehllast_kw, a.raeume[0].klasse, a.aussengeraete[0].artikel),
                         (2.61, "12", ["KL035"]))
        a = kl_auslegung.auslegen(self.logik, bogen([raum("Halle", 116.66)]))
        self.assertEqual((a.raeume[0].kuehllast_kw, a.raeume[0].klasse, a.aussengeraete[0].artikel,
                          a.ampeln), (7.0, "24", ["KL033", "KL029"], []))
        a = kl_auslegung.auslegen(self.logik, bogen([raum("Halle", 117)]))
        self.assertEqual(a.ampeln, ["Kühllast über 7,0 kW: Raum 1 Halle (7,02 kW) – Raum teilen "
                                    "oder Sonderlösung"])
        self.assertEqual(engine.ampel_gruende(self.logik, bogen([raum("Halle", 117)])), a.ampeln)
        # Dezimalkomma im Bogen („22,5“) wie Zahl
        a = kl_auslegung.auslegen(self.logik, bogen([raum("Komma", "22,5")]))
        self.assertEqual((a.raeume[0].flaeche, a.raeume[0].kuehllast_kw), (22.5, 1.35))
        # Kombinationssuche klein → groß: 9+24 fehlt bei 53/2 und 79/3 → 105/4 (§14a → KL003);
        # 9+9+18 → 79/3 (nicht 53/2); 18+18 → kein Außengerät → G4
        a = kl_auslegung.auslegen(self.logik, bogen([raum("Klein", 20), raum("Groß", 110)]))
        self.assertEqual((a.aussengeraete[0].kombination, a.aussengeraete[0].geraet,
                          a.aussengeraete[0].artikel, a.aussengeraete[0].p14a, a.montage_ref),
                         ("9+24", "CL5000M 105/4 E", ["KL039"], True, "KL021"))
        m = mengen(self.positionen(bogen([raum("Klein", 20), raum("Groß", 110)])))
        self.assertEqual((m.get("KL039"), m.get("KL026"), m.get("KL029"), m.get("KL003"),
                          m.get("KL021")), (1, 1, 1, 1, 1))
        a = kl_auslegung.auslegen(self.logik, bogen([raum("A", 20), raum("B", 20), raum("C", 80)]))
        self.assertEqual((a.aussengeraete[0].kombination, a.aussengeraete[0].geraet),
                         ("9+9+18", "CL5000M 79/3 E"))
        a = kl_auslegung.auslegen(self.logik, bogen([raum("A", 80), raum("B", 80)]))
        self.assertEqual(a.ampeln, ["Multi-Split-Kombination 18+18 an Außengerät 1 nicht "
                                    "freigegeben (Bosch Tab. 7)"])
        # Reihenfolge der Codes unabhängig von der Raumreihenfolge („24+9“ → „9+24“)
        a = kl_auslegung.auslegen(self.logik, bogen([raum("Groß", 110), raum("Klein", 20)]))
        self.assertEqual((a.aussengeraete[0].kombination, a.aussengeraete[0].geraet),
                         ("9+24", "CL5000M 105/4 E"))

    def test_mengenregeln_kl017_14a_kl050_ep(self):
        # KL017 je Raum (6–10 m → 5, 11–15 m → 10) + Elektrozuleitung (11–15 m → 10): eine
        # Position in Block 1, Menge addiert (5 + 10 + 10 = 25 m)
        antworten = fall_a()
        antworten.update({"KR05#1": "6–10 m", "KR05#2": "11–15 m", "KE02": "11–15 m"})
        pos = self.positionen(antworten)
        kl017 = [p for p in pos if p["pos_nr"] == "KL017"]
        self.assertEqual((len(kl017), kl017[0]["menge"], kl017[0]["block_nr"], kl017[0]["einheit"],
                          kl017[0]["e_preis_cent"]), (1, 25.0, 1, "m", 6800))
        self.assertEqual(engine.ampel_gruende(self.logik, antworten), [])
        # KE01 = Ja: KE02 unsichtbar → kein Zuleitungs-Zuschlag, KL001 statt KL008
        antworten["KE01"] = "Ja"
        m = mengen(self.positionen(antworten))
        self.assertEqual((m.get("KL017"), m.get("KL001"), m.get("KL008")), (15, 1, None))
        # §14a: KL003 ×1 je betroffenem Außengerät (zwei CL5000M 105/4 E; Montage 8/2 → G6)
        acht = bogen([raum(f"R{i}", 40, zuordnung="1" if i <= 4 else "2") for i in range(1, 9)],
                     KO04="2")
        a = kl_auslegung.auslegen(self.logik, acht)
        self.assertEqual([g.geraet for g in a.aussengeraete], ["CL5000M 105/4 E"] * 2)
        self.assertEqual(a.ampeln, ["Montagekombination 8 Innengeräte / 2 Außengeräte nicht "
                                    "hinterlegt"])
        m = mengen(self.positionen(acht))
        self.assertEqual((m.get("KL003"), m.get("KL039"), m.get("KL026"), m.get("KL013"),
                          m.get("KL008")), (2, 2, 8, 8, 2))
        self.assertFalse({"KL020", "KL021", "KL022", "KL023", "KL024", "KL025"} & set(m))
        # KL050 nur bei KZ01 = Gerüst erforderlich und KA01 ≠ Schrägdach (Flachdach → ja,
        # KL007 nie); Hubsteiger → KL015; Schrägdach → Dacharbeiten je Außengerät
        m = mengen(self.positionen(bogen([raum("R", 20)], KA01="auf einem Flachdach",
                                         KZ01="Gerüst erforderlich")))
        self.assertEqual((m.get("KL050"), m.get("KL004"), m.get("KL007")), (1, None, None))
        m = mengen(self.positionen(bogen([raum("R", 20)], KZ01="Hubsteiger erforderlich")))
        self.assertEqual((m.get("KL015"), m.get("KL050")), (1, None))
        m = mengen(self.positionen(bogen([raum("A", 20, zuordnung="1"), raum("B", 20, zuordnung="2")],
                                         KO04="2", KA01="auf einem Schrägdach",
                                         KZ01="Gerüst erforderlich")))
        self.assertEqual((m.get("KL004"), m.get("KL005"), m.get("KL006"), m.get("KL050"),
                          m.get("KL001"), m.get("KL008")), (2, 2, 2, None, None, 2))
        # KO07 Ja → KL019; KE03 Nein → KL009; KR06 Ja je Raum addiert; KR11 Beton je Raum
        m = mengen(self.positionen(bogen([raum("A", 20, pumpe="Ja",
                                               durchbruch="Beton oder dicker als 32 cm"),
                                          raum("B", 20, pumpe="Ja")], KO07="Ja", KE03="Nein")))
        self.assertEqual((m.get("KL019"), m.get("KL009"), m.get("KL016"), m.get("KL014"),
                          m.get("KL021")), (1, 1, 2, 1, 1))
        # EP nur über die Aktion: KO08 Ja → ohne EP, „als Eventualposition“ → EP, Nein → keins
        for ko08, ep in (("Ja", False), ("als Eventualposition", True)):
            gw = [p for p in self.positionen(bogen([raum("R", 20)], KO08=ko08))
                  if p["pos_nr"] == "KL013"][0]
            self.assertEqual((gw["menge"], gw["ep_flag"], gw["block_nr"], gw["gruppe"]),
                             (1.0, ep, 3, GRUPPE))
        self.assertNotIn("KL013", mengen(self.positionen(bogen([raum("R", 20)], KO08="Nein"))))
        # Händische Artikel nie automatisch
        for antworten in (fall_a(), fall_b(), fall_h(), acht):
            self.assertFalse({"KL002", "KL007", "KL010", "KL011", "KL012", "KL018", "KL030",
                              "KL031", "KL032"} & set(mengen(self.positionen(antworten))))

    def test_ampel_texte_g5_g7_g8_in_liste_und_protokoll(self):
        sechs = bogen([raum(f"R{i}", 20) for i in range(1, 7)])
        self.assertEqual(engine.ampel_gruende(self.logik, sechs),
                         [G5_TEXT, "Montagekombination 6 Innengeräte / 1 Außengeräte nicht "
                                   "hinterlegt"])
        antworten = fall_a()
        antworten.update({"KR05#2": "über 15 m", "KE02": "über 15 m"})
        gruende = engine.ampel_gruende(self.logik, antworten)
        self.assertCountEqual(gruende, [G7_TEXT, G8_TEXT])
        self.assertFalse([g for g in gruende if "<" in g])          # keine rohen Platzhalter
        je_frage = engine.ampel_je_frage(self.logik, antworten)
        self.assertEqual((je_frage.get("KR05#2"), je_frage.get("KE02")), (G7_TEXT, G8_TEXT))
        prot = engine.protokoll(self.logik, antworten)
        self.assertEqual([z["ampel_grund"] for z in prot if z["frage_id"] in ("KR05#2", "KE02")],
                         [G7_TEXT, G8_TEXT])
        # Erfassung über die Route: beide Gründe in gruende_text, Liste/Detail zeigen sie
        e = self.erfassung_anlegen(antworten)
        self.absenden(e)
        self.assertEqual(e.ampel, "orange")
        self.assertCountEqual(e.gruende_text.split("\n"), [G7_TEXT, G8_TEXT])
        r = self.client.get(f"/erfassungen/{e.id}")
        self.assertIn(G7_TEXT, r.text)
        self.assertIn("Raum 2 Schlafzimmer", r.text)

    def test_parametrierung_und_artikel_oberflaeche(self):
        # v26 (PLAN_PROJ_V5 Phase 125): die Übersicht ist eine Verteilerseite –
        # Klima-Import und KL-Parameter liegen auf /parametrierung/logik, die
        # DB-Ampel je Sparte auf /parametrierung/angebotstool
        r = self.client.get("/parametrierung")
        self.assertEqual(r.status_code, 200)
        self.assertIn('href="/parametrierung/logik"', r.text)
        self.assertIn('href="/parametrierung/kl-logik"', r.text)
        r = self.client.get("/parametrierung/logik")
        self.assertEqual(r.status_code, 200)
        self.assertIn("Artikel → Klima-Positionslisten importieren", r.text)
        self.assertIn("/parametrierung/kl-logik", r.text)
        for name in ("W/m² normal", "Klasse 24 bis", "§14a-Außengeräte", "Rollgerüst VK"):
            self.assertIn(name, r.text)
        self.assertIn("€ netto", r.text)                          # Einheit-Spalte
        self.assertNotIn("Fehlende KL-Parameter", r.text)
        r = self.client.get("/parametrierung/angebotstool")
        self.assertEqual(r.status_code, 200)
        self.assertIn('name="db_ampel_rot_unter_KL"', r.text)
        # Artikelliste: Klima-Import neben dem PV-Import, Filter Sparte KL (pos_nr KL*)
        r = self.client.get("/artikel")
        self.assertEqual(r.status_code, 200)
        self.assertIn("PV-Positionslisten importieren", r.text)
        self.assertIn("Klima-Positionslisten importieren", r.text)
        self.assertIn("/parametrierung/artikel/kl-import", r.text)
        r = self.client.get("/artikel?q=KL0")
        self.assertEqual(r.status_code, 200)
        for nr in ("KL001", "KL023", "KL049", "KL050"):
            self.assertIn(nr, r.text)
        r = self.client.get("/parametrierung/artikel/kl-import")
        self.assertEqual(r.status_code, 200)
        self.assertIn("Import ausführen", r.text)
        self.assertIn("KL050", r.text)                             # EK-Hinweis Rollgerüst
        r = self.client.get("/parametrierung/kl-logik")
        self.assertEqual(r.status_code, 200)
        for text in ("Paketmatrix KL", "Montagematrix KL", "Kombinationen KL", "CL5000M 79/3 E",
                     "KL023"):
            self.assertIn(text, r.text)


if __name__ == "__main__":
    unittest.main()
