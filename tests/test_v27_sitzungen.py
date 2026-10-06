# v27 (PLAN_V17 Phase 128): Sitzungsdisziplin, Pool und Threadpool.
# (a) Wächter-Test: AST-Prüfung über app/ – kein Netzaufruf innerhalb einer
#     offenen Datenbanksitzung ohne vorherige Freigabe (verbindung_freigeben /
#     close / commit), markierte Ausnahmen über den Kommentar „netz-ohne-sitzung-ok“.
# (b) 40 parallele Anfragen auf Kundenkartei + Terminvorschläge mit 3 s
#     Routing-Mock ohne TimeoutError (def-Routen im Threadpool).
# (d) Pool-Invariante und Pool-/Thread-Werte aus der .env.
# (c) – Scheduler-Lauf mit 1.000 Geocoding-Adressen – steht in tests/test_v27_scheduler.py.
import ast
import threading
import time
import unittest
import warnings
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest import mock

warnings.filterwarnings("ignore")

from app import config, db

APP = Path(__file__).resolve().parent.parent / "app"
MARKER = "netz-ohne-sitzung-ok"
# Primitive Netzaufrufe (Attributnamen bzw. Modulwurzeln)
NETZ_ATTRIBUTE = {"urlopen", "acquire_token_silent", "acquire_token_by_device_flow",
                  "acquire_token_for_client", "acquire_token_interactive"}
NETZ_MODULE = {"httpx", "requests", "smtplib", "socket"}
# Freigabe-Aufrufe
FREIGABE_FUNKTIONEN = {"verbindung_freigeben"}
FREIGABE_METHODEN = {"close", "commit", "rollback"}
DB_METHODEN = {"query", "get", "add", "add_all", "execute", "flush", "scalars", "scalar",
               "delete", "merge", "refresh", "expire", "expire_all", "expunge", "begin"}
SESSION_PARAMETER = {"session", "sitzung"}


class _Funktion:
    def __init__(self, modul: str, name: str, knoten, quelltext: list[str]):
        self.modul = modul
        self.name = name
        self.knoten = knoten
        self.schluessel = f"{modul}.{name}"
        self.zeilen = quelltext
        self.sitzungen: list[tuple[str, int, int]] = []      # (Variable, von, bis)
        self.aufrufe: list[tuple[int, int, str, str]] = []   # (Zeile, Spalte, Ziel, Text)
        self.freigaben: list[tuple[int, int, str | None]] = []   # (Zeile, Spalte, Variable|None=alle)
        self.db_nutzung: list[tuple[int, int, str]] = []     # (Zeile, Spalte, Variable)
        self.primitiv: list[tuple[int, int, str]] = []
        self.unsicher = False


def _modulname(pfad: Path) -> str:
    rel = pfad.relative_to(APP).with_suffix("")
    return ".".join(rel.parts)


def _importe(baum) -> dict[str, str]:
    """Alias → Modulschlüssel (app.x → „x“, app.routers.y → „routers.y“)."""
    aliase = {}
    for kn in ast.walk(baum):
        if isinstance(kn, ast.ImportFrom) and kn.module and kn.module.startswith("app"):
            basis = kn.module.split(".", 1)[1] if "." in kn.module else ""
            for a in kn.names:
                ziel = f"{basis}.{a.name}" if basis else a.name
                aliase[a.asname or a.name] = ziel
        elif isinstance(kn, ast.Import):
            for a in kn.names:
                if a.name.startswith("app."):
                    aliase[a.asname or a.name.split(".")[-1]] = a.name.split(".", 1)[1]
    return aliase


def _funktionen_sammeln() -> dict[str, _Funktion]:
    funktionen: dict[str, _Funktion] = {}
    for pfad in sorted(APP.rglob("*.py")):
        if "__pycache__" in pfad.parts:
            continue
        text = pfad.read_text(encoding="utf-8")
        zeilen = text.splitlines()
        baum = ast.parse(text)
        modul = _modulname(pfad)
        aliase = _importe(baum)
        kandidaten = []
        for kn in baum.body:
            if isinstance(kn, (ast.FunctionDef, ast.AsyncFunctionDef)):
                kandidaten.append((kn.name, kn))
            elif isinstance(kn, ast.ClassDef):
                for m in kn.body:
                    if isinstance(m, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        kandidaten.append((f"{kn.name}.{m.name}", m))
        for name, kn in kandidaten:
            f = _Funktion(modul, name, kn, zeilen)
            _funktion_analysieren(f, aliase)
            funktionen[f.schluessel] = f
    return funktionen


def _funktion_analysieren(f: _Funktion, aliase: dict[str, str]) -> None:
    kn = f.knoten
    ende = kn.end_lineno
    for arg in kn.args.args + kn.args.kwonlyargs:
        ann = ast.unparse(arg.annotation) if arg.annotation is not None else ""
        if arg.arg in SESSION_PARAMETER or ann.endswith("Session"):
            f.sitzungen.append((arg.arg, kn.lineno, ende))
    for a in ast.walk(kn):
        if isinstance(a, ast.Assign) and isinstance(a.value, ast.Call):
            ziel = ast.unparse(a.value.func)
            if ziel.endswith("SessionLocal"):
                for t in a.targets:
                    if isinstance(t, ast.Name):
                        f.sitzungen.append((t.id, a.lineno, ende))
        if isinstance(a, ast.With):
            for item in a.items:
                if isinstance(item.context_expr, ast.Call):
                    ziel = ast.unparse(item.context_expr.func)
                    if ziel.endswith("kurz") and isinstance(item.optional_vars, ast.Name):
                        f.sitzungen.append((item.optional_vars.id, a.lineno, a.end_lineno))
                        # Blockende = Freigabe dieser Variablen
                        f.freigaben.append((a.end_lineno, 10_000, item.optional_vars.id))
        if isinstance(a, ast.Call):
            text = ast.unparse(a.func)
            zeile, spalte = a.lineno, a.col_offset
            kommentar = f.zeilen[zeile - 1] if zeile - 1 < len(f.zeilen) else ""
            if isinstance(a.func, ast.Name):
                if a.func.id in FREIGABE_FUNKTIONEN:
                    var = ast.unparse(a.args[0]) if a.args else None
                    f.freigaben.append((zeile, spalte, var))
                    continue
                ziel = aliase.get(a.func.id, f"{f.modul}.{a.func.id}")
                f.aufrufe.append((zeile, spalte, ziel, text))
            elif isinstance(a.func, ast.Attribute):
                attr = a.func.attr
                wurzel = a.func.value
                if attr in FREIGABE_FUNKTIONEN:
                    var = ast.unparse(a.args[0]) if a.args else None
                    f.freigaben.append((zeile, spalte, var))
                    continue
                if isinstance(wurzel, ast.Name):
                    if attr in FREIGABE_METHODEN:
                        f.freigaben.append((zeile, spalte, wurzel.id))
                        continue
                    if attr in DB_METHODEN:
                        f.db_nutzung.append((zeile, spalte, wurzel.id))
                    if wurzel.id in NETZ_MODULE or attr in NETZ_ATTRIBUTE:
                        if MARKER not in kommentar:
                            f.primitiv.append((zeile, spalte, text))
                        continue
                    ziel = aliase.get(wurzel.id)
                    if ziel is not None:
                        f.aufrufe.append((zeile, spalte, f"{ziel}.{attr}", text))
                    elif wurzel.id == "self":
                        klasse = f.name.split(".")[0] if "." in f.name else ""
                        f.aufrufe.append((zeile, spalte, f"{f.modul}.{klasse}.{attr}", text))
                else:
                    wurzel_text = ast.unparse(wurzel)
                    if (wurzel_text.split(".")[0] in NETZ_MODULE or attr in NETZ_ATTRIBUTE) \
                            and MARKER not in kommentar:
                        f.primitiv.append((zeile, spalte, text))


def _netzaufrufe(f: _Funktion, unsicher: set[str]) -> list[tuple[int, int, str]]:
    treffer = list(f.primitiv)
    for zeile, spalte, ziel, text in f.aufrufe:
        if ziel in unsicher and ziel != f.schluessel:
            kommentar = f.zeilen[zeile - 1] if zeile - 1 < len(f.zeilen) else ""
            if MARKER not in kommentar:
                treffer.append((zeile, spalte, text))
    return treffer


def _offen_bei(f: _Funktion, zeile: int, spalte: int) -> list[str]:
    """Sitzungsvariablen, die beim Aufruf (zeile, spalte) noch eine Verbindung
    halten können: im Gültigkeitsbereich, nach der letzten Freigabe wieder
    benutzt oder nie freigegeben."""
    offen = []
    for var, von, bis in f.sitzungen:
        if not (von <= zeile <= bis):
            continue
        letzte_freigabe = None
        for fz, fs, fvar in f.freigaben:
            if (fz, fs) < (zeile, spalte) and (fvar is None or fvar == var):
                if letzte_freigabe is None or (fz, fs) > letzte_freigabe:
                    letzte_freigabe = (fz, fs)
        if letzte_freigabe is None:
            offen.append(var)
            continue
        wieder_benutzt = any(letzte_freigabe < (dz, ds) < (zeile, spalte) and dvar == var
                             for dz, ds, dvar in f.db_nutzung)
        if wieder_benutzt:
            offen.append(var)
    return offen


def verstoesse_suchen() -> tuple[list[str], set[str]]:
    funktionen = _funktionen_sammeln()
    # Fixpunkt: „unsicher“ = führt Netz-I/O aus (primitiv oder über eine unsichere
    # Funktion), ohne eine übergebene Sitzung vorher freizugeben. Eine Funktion
    # ohne Sitzungs-Parameter mit Netzaufruf ist immer unsicher (der Aufrufer muss
    # vorher freigeben); eine mit Parameter ist sicher, wenn der Parameter vor dem
    # Netzaufruf freigegeben und danach nicht wieder benutzt wird.
    unsicher: set[str] = set()
    while True:
        neu = set(unsicher)
        for s, f in funktionen.items():
            if s in neu:
                continue
            parameter = {v for v, _, _ in f.sitzungen
                         if v in {a.arg for a in f.knoten.args.args + f.knoten.args.kwonlyargs}}
            for zeile, spalte, _ in _netzaufrufe(f, unsicher):
                offen = set(_offen_bei(f, zeile, spalte))
                if not parameter or parameter & offen:
                    neu.add(s)
                    break
        if neu == unsicher:
            break
        unsicher = neu
    verstoesse = []
    for s, f in sorted(funktionen.items()):
        for zeile, spalte, text in _netzaufrufe(f, unsicher):
            offen = _offen_bei(f, zeile, spalte)
            if offen:
                verstoesse.append(f"{f.modul}.py:{zeile} {f.name}: {text[:70]} "
                                  f"– offene Sitzung {', '.join(offen)}")
    return verstoesse, unsicher


class Waechter(unittest.TestCase):
    def test_kein_netzaufruf_in_offener_sitzung(self):
        verstoesse, unsicher = verstoesse_suchen()
        self.assertTrue(unsicher, "keine Netzfunktionen erkannt – Prüfung defekt")
        self.assertIn("graph_versand._graph_aufruf", unsicher)
        self.assertIn("monday_sync._api", unsicher)
        self.assertEqual(verstoesse, [], "Netzaufruf in offener Sitzung:\n" + "\n".join(verstoesse))

    def test_waechter_erkennt_verstoss(self):
        """Selbsttest: ein Beispiel mit Netzaufruf ohne Freigabe wird gefunden."""
        quelle = (
            "from app import graph_versand\n"
            "from app.db import SessionLocal, verbindung_freigeben\n"
            "def schlecht(session):\n"
            "    x = session.query(1).all()\n"
            "    graph_versand._graph_aufruf('GET', '/x', 't')\n"
            "def gut(session):\n"
            "    x = session.query(1).all()\n"
            "    verbindung_freigeben(session)\n"
            "    graph_versand._graph_aufruf('GET', '/x', 't')\n"
            "def gut2():\n"
            "    s = SessionLocal()\n"
            "    s.query(1).all()\n"
            "    s.close()\n"
            "    graph_versand._graph_aufruf('GET', '/x', 't')\n"
            "def schlecht2(session):\n"
            "    verbindung_freigeben(session)\n"
            "    session.query(2).all()\n"
            "    graph_versand._graph_aufruf('GET', '/x', 't')\n")
        baum = ast.parse(quelle)
        aliase = _importe(baum)
        ergebnisse = {}
        for kn in baum.body:
            if isinstance(kn, ast.FunctionDef):
                f = _Funktion("probe", kn.name, kn, quelle.splitlines())
                _funktion_analysieren(f, aliase)
                treffer = _netzaufrufe(f, {"graph_versand._graph_aufruf"})
                ergebnisse[kn.name] = [bool(_offen_bei(f, z, s)) for z, s, _ in treffer]
        self.assertEqual(ergebnisse, {"schlecht": [True], "gut": [False],
                                      "gut2": [False], "schlecht2": [True]})


class PoolInvariante(unittest.TestCase):
    def test_pool_und_threads_aus_der_env(self):
        self.assertEqual((db.POOL_SIZE, db.MAX_OVERFLOW, db.POOL_TIMEOUT),
                         (config.DB_POOL_SIZE, config.DB_POOL_OVERFLOW, config.DB_POOL_TIMEOUT))
        self.assertEqual((db.engine.pool.size(), db.engine.pool._max_overflow,
                          db.engine.pool._timeout),
                         (db.POOL_SIZE, db.MAX_OVERFLOW, db.POOL_TIMEOUT))
        self.assertGreaterEqual(config.WORKER_THREADS, 40)

    def test_invariante_mit_standardwerten(self):
        # Standard: Pool 20 + 70 = 90 ≥ 64 Threads + 12 Scheduler + 5 = 81
        ok, text = db.pool_invariante(12)
        self.assertTrue(ok, text)
        self.assertIn("Scheduler 12", text)
        ok, text = db.pool_invariante(db.POOL_SIZE + db.MAX_OVERFLOW)   # absichtlich zu viele
        self.assertFalse(ok)
        self.assertIn("<", text)

    def test_pool_kennzahlen(self):
        k = db.pool_kennzahlen()
        self.assertEqual(k["maximum"], db.POOL_SIZE + db.MAX_OVERFLOW)
        self.assertGreaterEqual(k["checked_out"], 0)
        self.assertLessEqual(k["prozent"], 100.0)

    def test_kurz_commit_und_rollback(self):
        from app.models import Einstellung, einstellung_setzen
        name = "v27_test_kurz"
        basis = db.engine.pool.checkedout()   # fremde Sitzungen anderer Tests
        with db.kurz() as s:
            einstellung_setzen(s, name, "1")
        with db.kurz() as s:
            self.assertEqual(s.query(Einstellung).filter_by(name=name).one().wert, "1")
        with self.assertRaises(RuntimeError):
            with db.kurz() as s:
                einstellung_setzen(s, name, "2")
                raise RuntimeError("abbruch")
        with db.kurz() as s:
            self.assertEqual(s.query(Einstellung).filter_by(name=name).one().wert, "1")
            s.query(Einstellung).filter_by(name=name).delete()
        self.assertEqual(db.engine.pool.checkedout(), basis)


class ParalleleAnfragen(unittest.TestCase):
    """(b) 40 parallele Anfragen (Kundenkartei + Terminvorschläge) mit 3 s
    Routing-Mock – keine TimeoutError, während des Netzaufrufs hält keine
    Anfrage eine Verbindung. Nutzt die Testdaten des Hotfix-Tests."""

    @classmethod
    def setUpClass(cls):
        from tests import test_pool_hotfix as hotfix
        cls.hotfix = hotfix
        hotfix.Basis.setUpClass()
        cls.basis = hotfix.Basis

    @classmethod
    def tearDownClass(cls):
        cls.hotfix.Basis.tearDownClass()

    def test_40_parallele_anfragen_def_routen(self):
        from app import lead_termin, routing
        hotfix = self.hotfix
        belegt: list[int] = []
        sperre = threading.Lock()

        def langsame_matrix(quellen, ziele, schluessel):
            with sperre:
                belegt.append(db.engine.pool.checkedout())
            time.sleep(3.0)
            raise RuntimeError("Routing-Dienst nicht erreichbar (Test)")

        def anfrage(i: int):
            c = hotfix.Basis.admin_client()
            if i % 2 == 0:   # 20 × Kundenkartei (liest nur) + 20 × Terminvorschläge
                r = c.get(f"/lead-management/lead/{self.basis.vorgang_id}")
            else:
                r = c.get(f"/lead-management/lead/{self.basis.vorgang_id}"
                          "/termin/vorschlaege.json?neu=1")
            return r.status_code, r.text[:200]

        db.verbindung_freigeben(self.basis.s)
        basis_belegt = db.engine.pool.checkedout()
        hotfix.routing_cache_leeren()
        lead_termin.vorschlaege_cache_leeren()
        # vorher einmal die Kartei laden (Glocke/Module warm) – dann 40 × Vorschläge
        hotfix.Basis.admin_client().get(f"/lead-management/lead/{self.basis.vorgang_id}")
        start = time.monotonic()
        with mock.patch.object(routing, "_ors_matrix", side_effect=langsame_matrix):
            with ThreadPoolExecutor(max_workers=40) as pool:
                ergebnisse = list(pool.map(anfrage, range(40)))
        dauer = time.monotonic() - start
        self.assertEqual([e[0] for e in ergebnisse], [200] * 40, ergebnisse[:3])
        for _, text in ergebnisse:
            self.assertNotIn("TimeoutError", text)
            self.assertNotIn("QueuePool", text)
        self.assertGreaterEqual(len(belegt), 18, "Routing-Mock kaum getroffen")
        self.assertLess(dauer, 3.0 * 10, f"Anfragen liefen nicht parallel ({dauer:.1f} s)")
        # Vorschläge geben ihre Verbindung vor dem Routing frei: während des
        # Netzaufrufs halten höchstens die 20 Kartei-Anfragen (+ fremde) Verbindungen
        self.assertLessEqual(min(belegt), 20 + basis_belegt,
                             f"Verbindungen während Netz-I/O gehalten: {belegt}")
        self.assertLess(max(belegt), db.POOL_SIZE + db.MAX_OVERFLOW)
        hotfix.routing_cache_leeren()
        lead_termin.vorschlaege_cache_leeren()


if __name__ == "__main__":
    unittest.main()
