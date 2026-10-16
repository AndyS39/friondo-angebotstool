# v36 (PLAN_V22 Phase 191, Agent A4): Laufzeit des Browser-Drucks (Engine html, app/pdf_html.py).
# (1) 20 WP-PDFs mit 25 Positionen nacheinander – Zielwert Mittelwert ≤ 3 s (pdf_html.ZIELZEIT_S) als WEICHE
#     Prüfung mit Protokoll, harter Fehler erst bei einem Mittelwert über 6 s; (2) vier parallele Drucke
#     (Threads) ohne Fehler, höchstens zwei gleichzeitig im Browser (Semaphore PARALLEL = 2, gemessen über
#     einen zählenden Semaphore im Drucker); (3) Browser-Prozess nach einem Absturz neu gestartet: der
#     Edge-/Chromium-Prozess dieses Testprozesses wird WÄHREND eines Drucks hart beendet (taskkill /F, Rückfall
#     browser.close() aus dem Drucker-Thread) → der laufende Druck scheitert mit PdfDruckFehler, `neustarts`
#     steigt um eins, der nächste Druck läuft wieder.
# Läuft nur mit Browser (Edge/Chromium auf dem Dev-PC), sonst übersprungen. Der Kontext kommt aus einem
# WP-Kontrollangebot (tests.test_regression.KONTROLL_SZENARIO + iMSys), das in der Datenbank des Testaufrufs
# (DB-Kopie über DB_PFAD_OVERRIDE/DATA_ORDNER) angelegt und am Ende gelöscht wird; auf 25 Positionen aufgefüllt
# (Kontext-Kopien, keine Datenbankzeilen); ohne Logik/Artikel in der Kopie dient der Demo-Kontext. Gedruckt wird
# ohne Datenbanksitzung (pdf_html.pdf_aus_kontext). Protokoll: data\log\pdf-laufzeit.txt (DATA_ORDNER) und
# Testausgabe. Kein Netzzugriff.
import asyncio
import copy
import io
import json
import os
import statistics
import subprocess
import threading
import time
import unittest
import warnings
from datetime import datetime

warnings.filterwarnings("ignore")

from pypdf import PdfReader

from app import config, pdf_html, pdf_kontext
from app.db import SessionLocal, init_db
from app.models import Angebot, Kunde, Vorgang

BROWSER = pdf_html.browser_test()        # einmal je Modul (startet den Browser-Prozess)
BROWSER_OK = BROWSER["ok"]
ANZAHL_NACHEINANDER = 20
POSITIONEN = 25
PARALLEL_DRUCKE = 4
ZIEL_S = pdf_html.ZIELZEIT_S             # 3,0 s (weich)
HART_S = 6.0                             # harter Fehler
MAX_BYTES = int(2.5 * 1024 * 1024)
TEST_EMAIL = "v36-laufzeit@test.local"
PROTOKOLL = config.LOG_ORDNER / "pdf-laufzeit.txt"


def protokoll(zeile: str) -> None:
    """Messwerte in die Testausgabe und nach data\\log\\pdf-laufzeit.txt (DATA_ORDNER)."""
    text = f"{datetime.now().strftime('%d.%m.%Y %H:%M:%S')} · {zeile}"
    print(text)
    try:
        PROTOKOLL.parent.mkdir(parents=True, exist_ok=True)
        with PROTOKOLL.open("a", encoding="utf-8") as f:
            f.write(text + "\n")
    except OSError:
        pass


def kontext_auffuellen(kontext: dict, anzahl: int) -> dict:
    """Kontext auf `anzahl` Positionen bringen (Kopien bestehender Positionen, fortlaufend nummeriert)."""
    kontext = copy.deepcopy(kontext)
    gruppen = kontext["gruppen"]
    vorhanden = [p for g in gruppen for p in g["positionen"]]
    if not vorhanden:
        raise ValueError("Kontext ohne Positionen")
    quelle = [p for p in vorhanden if p.get("kennzeichen") == "" and not p.get("hinweiskasten")] or vorhanden
    n = len(vorhanden)
    i = 0
    while n < anzahl:
        kopie = copy.deepcopy(quelle[i % len(quelle)])
        n += 1
        kopie["nr"] = f"{n:03d}"
        kopie["hinweiskasten"] = None
        gruppen[-1]["positionen"].append(kopie)
        i += 1
    return kontext


def _seiten(daten: bytes) -> int:
    return len(PdfReader(io.BytesIO(daten)).pages)


class _ZaehlSemaphore(asyncio.Semaphore):
    """Semaphore des Druckers mit Zähler: wie viele Drucke liegen gleichzeitig im Browser?"""

    def __init__(self, wert: int) -> None:
        super().__init__(wert)
        self.aktiv = 0
        self.maximum = 0
        self._zaehler_lock = threading.Lock()

    async def __aenter__(self):
        await self.acquire()
        with self._zaehler_lock:
            self.aktiv += 1
            self.maximum = max(self.maximum, self.aktiv)
        return None

    async def __aexit__(self, exc_type, exc, tb):
        with self._zaehler_lock:
            self.aktiv -= 1
        self.release()


def _prozesse() -> list[dict]:
    """Prozessliste (PID, Eltern-PID, Name, Kommandozeile) über PowerShell/CIM – nur Windows."""
    if os.name != "nt":
        return []
    befehl = ("Get-CimInstance Win32_Process -Filter \"Name='msedge.exe' OR Name='chrome.exe' OR Name='node.exe'\" "
              "| Select-Object ProcessId,ParentProcessId,Name,CommandLine | ConvertTo-Json -Compress")
    try:
        roh = subprocess.run(["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", befehl],
                             capture_output=True, text=True, timeout=30, encoding="utf-8", errors="replace").stdout
        daten = json.loads(roh or "[]")
    except (OSError, ValueError, subprocess.SubprocessError):
        return []
    return daten if isinstance(daten, list) else [daten]


def browser_pid() -> int | None:
    """PID des Browser-Hauptprozesses, den Playwright AUS DIESEM Prozess gestartet hat (Kette python → node
    (Playwright-Treiber) → msedge/chrome ohne --type=); None, wenn nicht ermittelbar."""
    prozesse = _prozesse()
    eigene = os.getpid()
    treiber = {p["ProcessId"] for p in prozesse if p.get("Name", "").lower() == "node.exe"
               and p.get("ParentProcessId") == eigene}
    for p in prozesse:
        name = (p.get("Name") or "").lower()
        if name in ("msedge.exe", "chrome.exe") and p.get("ParentProcessId") in treiber \
                and "--type=" not in (p.get("CommandLine") or ""):
            return int(p["ProcessId"])
    return None


@unittest.skipUnless(BROWSER_OK, f"Browser-Druck nicht verfügbar: {BROWSER.get('fehler')}")
class Laufzeit(unittest.TestCase):
    """Messungen am echten Browser; Reihenfolge: nacheinander → parallel → Absturz."""

    @classmethod
    def setUpClass(cls):
        init_db()
        cls.s = SessionLocal()
        cls.kunde = None
        cls.angebot_id = None
        cls.quelle = "Demo-Kontext"
        cls._aufraeumen()
        kontext = None
        try:
            from app import angebot_aufbau
            from app import logik as logik_modul
            from tests.test_regression import KONTROLL_SZENARIO
            logik, _ = logik_modul.hole_logik(cls.s)
            cls.kunde = Kunde(anrede="Herr", vorname="Max", nachname="V36-Laufzeit-Test", strasse="Musterstraße 12",
                              plz="47139", ort="Duisburg", email=TEST_EMAIL, telefon="0203 1234567")
            cls.s.add(cls.kunde)
            cls.s.commit()
            angebot = angebot_aufbau.angebot_anlegen(cls.s, cls.kunde.id, antworten={**KONTROLL_SZENARIO, "P02": "Ja"},
                                                     logik=logik)
            angebot.rabatt_cent = 50000
            angebot.rabatt_bezeichnung = "Aktionsnachlass"
            cls.s.commit()
            cls.angebot_id = angebot.id
            kontext = pdf_kontext.fuer_angebot(cls.s, angebot)
            cls.quelle = f"WP-Kontrollangebot {angebot.nummer} ({len(angebot.positionen)} Positionen)"
        except Exception as fehler:   # noqa: BLE001 – Kopie ohne Logik/Artikel: Demo-Kontext
            cls.s.rollback()
            cls.quelle = f"Demo-Kontext (Kontrollangebot nicht möglich: {type(fehler).__name__}: {fehler})"
        if kontext is None:
            kontext = pdf_kontext.demo_kontext("WP")
        cls.kontext = kontext_auffuellen(kontext, POSITIONEN)
        cls.s.close()           # kein Sitzung während der Drucke
        cls.s = None
        protokoll(f"Laufzeittest v36: Quelle {cls.quelle}, Browser {BROWSER['browser']} {BROWSER['version']}, "
                  f"Probeseite {BROWSER['dauer_ms']} ms")

    @classmethod
    def _aufraeumen(cls):
        s = cls.s or SessionLocal()
        try:
            for k in s.query(Kunde).filter(Kunde.email == TEST_EMAIL):
                for a in s.query(Angebot).filter_by(kunde_id=k.id):
                    s.delete(a)
                for v in s.query(Vorgang).filter_by(kunde_id=k.id):
                    s.delete(v)
                s.delete(k)
            s.commit()
        finally:
            if cls.s is None:
                s.close()

    @classmethod
    def tearDownClass(cls):
        cls.s = None
        cls._aufraeumen()

    def drucken(self) -> bytes:
        return pdf_html.pdf_aus_kontext(self.kontext)

    def test_1_zwanzig_nacheinander(self):
        anzahl = sum(len(g["positionen"]) for g in self.kontext["gruppen"])
        self.assertEqual(anzahl, POSITIONEN)
        zeiten = []
        erstes = None
        for _ in range(ANZAHL_NACHEINANDER):
            start = time.perf_counter()
            pdf = self.drucken()
            zeiten.append(time.perf_counter() - start)
            self.assertTrue(pdf.startswith(b"%PDF"))
            erstes = erstes or pdf
        mittel = statistics.mean(zeiten)
        seiten = _seiten(erstes)
        protokoll(f"{ANZAHL_NACHEINANDER} Drucke nacheinander (WP, {POSITIONEN} Positionen, {seiten} Seiten, "
                  f"{len(erstes) / 1024:.0f} KB): Mittel {mittel:.2f} s · min {min(zeiten):.2f} s · max {max(zeiten):.2f} s "
                  f"· Median {statistics.median(zeiten):.2f} s · Ziel {ZIEL_S:.1f} s "
                  f"{'erfüllt' if mittel <= ZIEL_S else 'NICHT erfüllt (weiche Prüfung)'}")
        self.assertLessEqual(len(erstes), MAX_BYTES, "PDF größer als 2,5 MB")
        self.assertGreaterEqual(seiten, 7)
        self.assertEqual(pdf_html.status()["letzter_fehler"], "")
        # harter Fehler erst deutlich über dem Zielwert; der Zielwert selbst ist eine weiche Prüfung mit Protokoll
        self.assertLessEqual(mittel, HART_S, f"Mittelwert {mittel:.2f} s über {HART_S:.0f} s")
        if mittel > ZIEL_S:
            print(f"HINWEIS: Mittelwert {mittel:.2f} s über dem Zielwert {ZIEL_S:.1f} s (weiche Prüfung)")

    def test_2_vier_parallel_hoechstens_zwei_gleichzeitig(self):
        drucker = pdf_html.DRUCKER
        self.drucken()                                  # Browser läuft, Semaphore existiert
        alt = drucker._sem
        sem = _ZaehlSemaphore(pdf_html.PARALLEL)
        drucker._sem = sem
        ergebnisse: list[bytes] = []
        fehler: list[Exception] = []
        zeiten: dict[int, float] = {}
        vorher = pdf_html.status()

        def lauf(nr: int) -> None:
            start = time.perf_counter()
            try:
                ergebnisse.append(self.drucken())
            except Exception as e:   # noqa: BLE001
                fehler.append(e)
            zeiten[nr] = time.perf_counter() - start

        try:
            threads = [threading.Thread(target=lauf, args=(i,), name=f"pdf-parallel-{i}") for i in range(PARALLEL_DRUCKE)]
            start = time.perf_counter()
            for t in threads:
                t.start()
            for t in threads:
                t.join(timeout=120)
            gesamt = time.perf_counter() - start
        finally:
            drucker._sem = alt
        nachher = pdf_html.status()
        protokoll(f"{PARALLEL_DRUCKE} Drucke parallel: gesamt {gesamt:.2f} s, je Druck "
                  + " / ".join(f"{zeiten[i]:.2f} s" for i in sorted(zeiten))
                  + f", gleichzeitig im Browser höchstens {sem.maximum} (Semaphore {pdf_html.PARALLEL}), Fehler {len(fehler)}")
        self.assertEqual(fehler, [], f"Fehler bei parallelen Drucken: {fehler}")
        self.assertEqual(len(ergebnisse), PARALLEL_DRUCKE)
        self.assertTrue(all(p.startswith(b"%PDF") for p in ergebnisse))
        self.assertLessEqual(sem.maximum, pdf_html.PARALLEL, "mehr als zwei Drucke gleichzeitig im Browser")
        self.assertEqual(sem.maximum, pdf_html.PARALLEL, "die Semaphore ließ keine zwei parallelen Drucke zu")
        self.assertEqual(nachher["anzahl"], vorher["anzahl"] + PARALLEL_DRUCKE)
        self.assertEqual(nachher["fehler"], vorher["fehler"])

    def test_3_neustart_nach_browser_absturz(self):
        drucker = pdf_html.DRUCKER
        self.drucken()                                  # Browser läuft
        vorher = pdf_html.status()
        pid = browser_pid()
        ergebnis: dict = {}

        def lauf() -> None:
            try:
                ergebnis["pdf"] = self.drucken()
            except pdf_html.PdfDruckFehler as e:
                ergebnis["fehler"] = e

        t = threading.Thread(target=lauf, name="pdf-absturz")
        t.start()
        time.sleep(0.6)                                 # der Druck läuft (Seite laden / drucken)
        if pid is not None:
            weg = f"taskkill /F /PID {pid}"
            subprocess.run(["taskkill", "/F", "/PID", str(pid)], capture_output=True, timeout=30)
        else:
            weg = "browser.close() aus dem Drucker-Thread (PID nicht ermittelbar)"
            asyncio.run_coroutine_threadsafe(drucker._browser.close(), drucker._loop).result(timeout=20)
        t.join(timeout=120)
        self.assertFalse(t.is_alive(), "der unterbrochene Druck hängt")
        zwischen = pdf_html.status()
        # der nächste Druck muss laufen – notfalls nach einem zweiten Anlauf (Verbindung noch nicht als tot erkannt)
        start = time.perf_counter()
        versuche = 0
        pdf = b""
        letzter = ""
        while versuche < 3 and not pdf:
            versuche += 1
            try:
                pdf = self.drucken()
            except pdf_html.PdfDruckFehler as e:
                letzter = str(e)
        dauer = time.perf_counter() - start
        nachher = pdf_html.status()
        protokoll(f"Browser-Absturz ({weg}): unterbrochener Druck → "
                  f"{'PdfDruckFehler: ' + str(ergebnis['fehler'])[:90] if 'fehler' in ergebnis else 'noch fertig geworden'}; "
                  f"nächster Druck nach {versuche} Anlauf/Anläufen in {dauer:.2f} s, Neustarts {vorher['neustarts']} → "
                  f"{nachher['neustarts']}, Browser gestartet: {nachher['gestartet']}")
        self.assertTrue(pdf.startswith(b"%PDF"), f"kein Druck nach dem Absturz: {letzter}")
        self.assertTrue(nachher["gestartet"])
        self.assertGreaterEqual(nachher["neustarts"], vorher["neustarts"] + 1,
                                "Neustart-Zähler nach dem Absturz nicht erhöht")
        if "fehler" in ergebnis:
            self.assertIn("Browser-Druck fehlgeschlagen", str(ergebnis["fehler"]))
            self.assertEqual(zwischen["fehler"], vorher["fehler"] + 1)
        self.assertGreater(nachher["anzahl"], vorher["anzahl"])


if __name__ == "__main__":
    unittest.main()
