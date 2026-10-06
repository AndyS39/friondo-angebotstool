# Tests PLAN_PROJ_V5 Phase 125 (v26): Montageteam am Benutzer als Dropdown
# statt Chip-Reihe (templates/benutzer/liste.html). Geprüft wird über die
# bestehenden Routen POST /benutzer/neu und /benutzer/{id}/aendern: ein
# Dropdown-Wert → genau eine TeamMitglied-Zeile, zwei Dropdowns → zwei, leere
# und doppelte Werte werden ignoriert bzw. dedupliziert; Rolle Innendienst →
# kein team_ids-Dropdown in der Benutzerzeile; Chips (ben-chip, class="chips")
# kommen im HTML nicht mehr vor; Dropdown-Reihenfolge Typ montage vor sub.
# Läuft gegen die Entwicklungs-DB; Testbenutzer und -teams tragen das
# Präfix „V26T “ und werden wieder aufgeräumt.
import re
import unittest
import warnings

warnings.filterwarnings("ignore")

from fastapi.testclient import TestClient

from app.db import SessionLocal, init_db
from app.main import app
from app.models import Benutzer, Team, TeamMitglied

PRAEFIX = "V26T "
# liefert je Team-Dropdown den Inhalt (die Optionen)
SELECT_MUSTER = re.compile(r'<select[^>]*name="team_ids"[^>]*>(.*?)</select>', re.S)


def aufraeumen(s):
    s.rollback()
    for b in s.query(Benutzer).filter(Benutzer.name.like(f"{PRAEFIX}%")):
        s.query(TeamMitglied).filter_by(benutzer_id=b.id).delete()
        s.delete(b)
    for t in s.query(Team).filter(Team.name.like(f"{PRAEFIX}%")):
        s.query(TeamMitglied).filter_by(team_id=t.id).delete()
        s.delete(t)
    s.commit()


def zeile(html: str, benutzer_id: int) -> str:
    """Nur die Hauptzeile eines Benutzers (bis zu seiner Detailzeile)."""
    start = html.index(f'id="zeile-{benutzer_id}"')
    ende = html.index(f'id="details-{benutzer_id}"', start)
    return html[start:ende]


def block(html: str, anfang: str, ende: str) -> str:
    start = html.index(anfang)
    return html[start:html.index(ende, start)]


class Basis(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        init_db()
        cls.s = SessionLocal()
        aufraeumen(cls.s)
        cls.client = TestClient(app)
        cls.client.post("/login", data={"benutzer_id": "1", "pin": "1234"})
        # Namen bewusst gegen die Alphabetik gewählt: Alphabetisch käme der
        # Sub vor dem Montageteam – im Dropdown muss trotzdem montage zuerst stehen.
        cls.montage = Team(name=f"{PRAEFIX}Zeta-Montage", typ="montage", aktiv=True,
                           erstellt_von=1)
        cls.sub = Team(name=f"{PRAEFIX}Alpha-Sub", typ="sub", aktiv=True, erstellt_von=1)
        cls.s.add_all([cls.montage, cls.sub])
        cls.s.commit()

    @classmethod
    def tearDownClass(cls):
        aufraeumen(cls.s)
        cls.s.close()

    def anlegen(self, name, rolle, team_ids=()):
        daten = {"name": f"{PRAEFIX}{name}", "rolle": rolle, "pin": "4321", "email": ""}
        if team_ids:
            daten["team_ids"] = [str(t) for t in team_ids]
        r = self.client.post("/benutzer/neu", data=daten, follow_redirects=False)
        self.assertEqual(r.status_code, 303)
        self.assertIn("Benutzer+angelegt", r.headers["location"])
        self.s.expire_all()
        return self.s.query(Benutzer).filter(Benutzer.name == f"{PRAEFIX}{name}").one()

    def aendern(self, benutzer, team_ids, rolle="montage"):
        daten = {"name": benutzer.name, "rolle": rolle, "email": "", "aktiv": "on",
                 "teams_dabei": "1", "team_ids": [str(t) for t in team_ids]}
        r = self.client.post(f"/benutzer/{benutzer.id}/aendern", data=daten,
                             follow_redirects=False)
        self.assertEqual(r.status_code, 303)
        self.assertIn("Gespeichert", r.headers["location"])
        self.s.expire_all()

    def mitglied_teams(self, benutzer_id):
        return sorted(m.team_id for m in
                      self.s.query(TeamMitglied).filter_by(benutzer_id=benutzer_id))

    def seite(self):
        r = self.client.get("/benutzer")
        self.assertEqual(r.status_code, 200)
        return r.text


class Dropdowns(Basis):
    def test_ein_dropdown_eine_mitgliedszeile(self):
        b = self.anlegen("Eins", "montage", [self.montage.id])
        self.assertEqual(self.mitglied_teams(b.id), [self.montage.id])
        z = zeile(self.seite(), b.id)
        selects = SELECT_MUSTER.findall(z)
        self.assertEqual(len(selects), 1)
        self.assertIn("– kein Team –", selects[0])
        self.assertIn(f'value="{self.montage.id}" selected', selects[0])
        self.assertEqual(selects[0].count(" selected"), 1)
        self.assertIn(f'form="f{b.id}" name="team_ids"', z)
        self.assertIn('name="teams_dabei" value="1"', z)
        self.assertIn("+ weiteres Team", z)

    def test_zwei_dropdowns_zwei_mitgliedszeilen(self):
        b = self.anlegen("Zwei", "montage", [self.montage.id, self.sub.id])
        self.assertEqual(self.mitglied_teams(b.id),
                         sorted([self.montage.id, self.sub.id]))
        z = zeile(self.seite(), b.id)
        selects = SELECT_MUSTER.findall(z)
        self.assertEqual(len(selects), 2)
        self.assertEqual(sum(s.count(" selected") for s in selects), 2)
        # Dropdown-Reihenfolge wie die Optionsliste: Montageteam vor Sub
        self.assertIn(f'value="{self.montage.id}" selected', selects[0])
        self.assertIn(f'value="{self.sub.id}" selected', selects[1])

    def test_leere_und_doppelte_werte(self):
        # Anlegen: leerer Wert („– kein Team –“) und Dublette → genau eine Zeile
        b = self.anlegen("Dublette", "montage", ["", self.montage.id, self.montage.id])
        self.assertEqual(self.mitglied_teams(b.id), [self.montage.id])
        # Ändern: Dublette + Sub → zwei Zeilen, keine doppelte
        self.aendern(b, [self.montage.id, "", self.sub.id, self.montage.id])
        self.assertEqual(self.mitglied_teams(b.id),
                         sorted([self.montage.id, self.sub.id]))
        # Ändern: nur „– kein Team –“ → keine Zuordnung mehr
        self.aendern(b, [""])
        self.assertEqual(self.mitglied_teams(b.id), [])
        selects = SELECT_MUSTER.findall(zeile(self.seite(), b.id))
        self.assertEqual(len(selects), 1)   # Rolle Montage: ein leeres Dropdown
        self.assertNotIn(" selected", selects[0])

    def test_innendienst_ohne_teamfelder(self):
        b = self.anlegen("Innen", "innendienst")
        self.assertEqual(self.mitglied_teams(b.id), [])
        z = zeile(self.seite(), b.id)
        self.assertNotIn('name="team_ids"', z)
        self.assertNotIn("– kein Team –", z)
        # leerer Team-Block versteckt (JS hängt beim Umschalten auf Montage ein
        # Dropdown ein), Platzhalter „–“ sichtbar
        teams_block = re.search(rf'<div class="ben-teams" id="teams-{b.id}"[^>]*>', z).group(0)
        self.assertIn("hidden", teams_block)
        self.assertIn(f'data-form="f{b.id}"', teams_block)
        kein = re.search(rf'<span class="dezent" id="keinteam-{b.id}"[^>]*>–</span>', z).group(0)
        self.assertNotIn("hidden", kein)
        # team_ids aus dem Formular eines Nicht-Montage-Benutzers wirken trotzdem
        # (Zusatzrolle Montage o. ä.) – Route unverändert
        self.aendern(b, [self.sub.id], rolle="innendienst")
        self.assertEqual(self.mitglied_teams(b.id), [self.sub.id])
        z = zeile(self.seite(), b.id)
        self.assertEqual(len(SELECT_MUSTER.findall(z)), 1)


class Seite(Basis):
    def test_keine_chips_mehr(self):
        html = self.seite()
        self.assertNotIn("ben-chip", html)
        self.assertNotIn('class="chips"', html)
        # Zusatzrollen bleiben als Kontrollfelder in der Detailzeile
        self.assertIn('<label class="kontrollfeld">', html)
        self.assertIn('name="zusatz_montage"', html)

    def test_neuer_benutzer_dropdown_und_vorlage(self):
        html = self.seite()
        neu = block(html, 'id="teams-neu"', "</form>")
        self.assertEqual(len(SELECT_MUSTER.findall(neu)), 1)
        self.assertIn('<option value="">– kein Team –</option>', neu)
        self.assertIn("+ weiteres Team", neu)
        self.assertNotIn("form=", block(neu, "<select", "</select>"))
        vorlage = block(html, '<template id="ben-team-vorlage">', "</template>")
        self.assertEqual(len(SELECT_MUSTER.findall(vorlage)), 1)
        for funktion in ("benTeamsUmschalten", "benTeamHinzu", "benTeamWeg"):
            self.assertIn(f"function {funktion}(", html)

    def test_reihenfolge_montage_vor_sub(self):
        html = self.seite()
        optionen = block(html, 'id="teams-neu"', "</select>")
        self.assertLess(optionen.index(f"{PRAEFIX}Zeta-Montage"),
                        optionen.index(f"{PRAEFIX}Alpha-Sub"))
        # alle Montage-Optionen vor allen Sub-Optionen
        typ_je_id = {t.id: t.typ for t in self.s.query(Team)}
        typen = [typ_je_id[int(w)] for w in re.findall(r'<option value="(\d+)"', optionen)
                 if int(w) in typ_je_id]
        self.assertIn("montage", typen)
        self.assertIn("sub", typen)
        self.assertEqual(typen, sorted(typen, key=lambda t: 0 if t == "montage" else 1))

    def test_hilfetext_montage(self):
        html = self.seite()
        self.assertIn("Team hier zuordnen – die Teams selbst werden unter", html)
        self.assertIn('href="/parametrierung/teams">Parametrierung → Teams</a> angelegt.', html)


if __name__ == "__main__":
    unittest.main()
