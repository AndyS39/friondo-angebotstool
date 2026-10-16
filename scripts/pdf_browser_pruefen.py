# v36 (PLAN_V22 Phase 188/195): Server-Prüfung des Browser-Drucks für das Angebots-PDF.
#
# Aufruf im Projektordner (normalerweise über scripts\pdf-browser-pruefen.bat):
#   venv\Scripts\python.exe scripts\pdf_browser_pruefen.py [--nur-suchen] [--sparte WP|PV|KL|WB]
#       [--ziel PFAD] [--ohne-datei]
# Ablauf:
#   1. Browser suchen: PDF_BROWSER_PFAD aus der .env (app.config), dann die Standardpfade von Edge und
#      Chrome (Program Files / Program Files (x86)), dazu der Playwright-Chromium-Cache
#      (%LOCALAPPDATA%\ms-playwright). Ausgabe je Kandidat: vorhanden / fehlt.
#   2. Test-PDF drucken wie das Tool (app.pdf_html.browser_test: Probeseite bzw. Demo-Angebot über die
#      Sparten-Vorlage – keine Kundendaten, keine Datenbank): Browser-Kanal, Version, Dauer in ms,
#      Seiten, Bytes; PDF nach --ziel (Standard data\log\pdf-browser-test-<JJJJ-MM-TT_HHMM>.pdf).
#   3. Konto, unter dem der Druck lief (whoami) – der Dienst FriondoAngebotstool läuft als SYSTEM:
#      dort prüfen mit  psexec -s -i 0 cmd /c "cd /d <Projekt> && scripts\pdf-browser-pruefen.bat"
#      oder über eine geplante Aufgabe unter SYSTEM (docs/angebots-pdf.md, Abschnitt Server-Prüfung).
# Exit-Code 0 = Druck ok, 1 = kein Browser / Druck fehlgeschlagen, 2 = Bedienfehler (venv, Playwright).
import argparse
import getpass
import os
import platform
import sys
import time
from datetime import datetime
from pathlib import Path

PROJEKT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJEKT))


def kandidaten(pfad_env: str) -> list[tuple[str, str]]:
    """(Bezeichnung, Pfad) in der Reihenfolge, in der app/pdf_html.py den Browser sucht."""
    liste: list[tuple[str, str]] = []
    if pfad_env:
        liste.append(("PDF_BROWSER_PFAD (.env)", pfad_env))
    for basis in (os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)"),
                  os.environ.get("ProgramFiles", r"C:\Program Files")):
        liste.append(("Edge (Kanal msedge)", rf"{basis}\Microsoft\Edge\Application\msedge.exe"))
    for basis in (os.environ.get("ProgramFiles", r"C:\Program Files"),
                  os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)"),
                  os.environ.get("LOCALAPPDATA", "")):
        if basis:
            liste.append(("Chrome (nur über PDF_BROWSER_PFAD)", rf"{basis}\Google\Chrome\Application\chrome.exe"))
    cache = os.environ.get("PLAYWRIGHT_BROWSERS_PATH") or (
        rf"{os.environ.get('LOCALAPPDATA', '')}\ms-playwright" if os.environ.get("LOCALAPPDATA") else "")
    if cache:
        liste.append(("Playwright-Chromium (Rückfall, playwright install chromium)", cache))
    return liste


def main() -> int:
    parser = argparse.ArgumentParser(description="Friondo Angebotstool – Browser-Druck prüfen (v36)")
    parser.add_argument("--nur-suchen", action="store_true", help="nur Browser suchen, kein Druck")
    parser.add_argument("--sparte", default="WP", help="Sparten-Vorlage für das Test-PDF (WP|PV|KL|WB)")
    parser.add_argument("--ziel", default="", help="Zielpfad des Test-PDFs (Standard data\\log\\pdf-browser-test-<Zeit>.pdf)")
    parser.add_argument("--ohne-datei", action="store_true", help="Test-PDF nicht speichern")
    argumente = parser.parse_args()

    try:
        from app import config
    except Exception as fehler:   # noqa: BLE001
        print(f"FEHLER: app.config nicht ladbar ({fehler}) – im Projektordner mit venv ausführen.")
        return 2
    konto = f"{os.environ.get('USERDOMAIN', '')}\\{getpass.getuser()}".strip("\\")
    print("== Friondo Angebotstool: Browser-Druck prüfen (v36) ==")
    print(f"Projekt:  {PROJEKT}")
    print(f"Konto:    {konto}  (Rechner {platform.node()}, Python {platform.python_version()})")
    print(f".env:     PDF_BROWSER_PFAD={config.PDF_BROWSER_PFAD or '(leer – Kanal msedge, sonst Chromium)'}")
    print()
    print("Browser-Kandidaten:")
    gefunden = 0
    for name, pfad in kandidaten(config.PDF_BROWSER_PFAD):
        p = Path(pfad)
        da = p.is_file() or (p.is_dir() and any(p.glob("chromium*")))
        gefunden += 1 if da else 0
        print(f"  [{'x' if da else ' '}] {name}: {pfad}")
    if not gefunden:
        print("  -> kein Browser gefunden: Edge installieren, PDF_BROWSER_PFAD in der .env setzen oder "
              "venv\\Scripts\\python -m playwright install chromium (Internet noetig).")
    try:
        import playwright   # noqa: F401
        from importlib.metadata import version
        print(f"Playwright: {version('playwright')}")
    except Exception as fehler:   # noqa: BLE001
        print(f"FEHLER: Playwright fehlt in der venv ({fehler}) – venv\\Scripts\\python -m pip install -r requirements.txt")
        return 2
    if argumente.nur_suchen:
        return 0 if gefunden else 1

    print()
    print("Test-PDF drucken ...")
    from app import pdf_html
    start = time.perf_counter()
    ergebnis = pdf_html.browser_test(argumente.sparte.upper(), vollstaendig=True)
    gesamt_ms = int((time.perf_counter() - start) * 1000)
    if not ergebnis["ok"]:
        print(f"FEHLER: {ergebnis['fehler']}")
        print(f"  Browser: {ergebnis['browser'] or '-'} {ergebnis['version']}  ({ergebnis['dauer_ms']} ms)")
        print("  Hinweise: Edge-Pfad pruefen, PDF_BROWSER_PFAD in der .env setzen, unter dem Dienstkonto SYSTEM "
              "wiederholen (psexec -s); Details docs/angebots-pdf.md, Abschnitt Fehlersuche.")
        return 1
    ziel = None
    if not argumente.ohne_datei:
        ziel = Path(argumente.ziel) if argumente.ziel else (
            config.LOG_ORDNER / f"pdf-browser-test-{datetime.now():%Y-%m-%d_%H%M}.pdf")
        try:
            ziel.parent.mkdir(parents=True, exist_ok=True)
            ziel.write_bytes(ergebnis["pdf"])
        except OSError as fehler:
            print(f"WARNUNG: Test-PDF nicht gespeichert ({fehler}).")
            ziel = None
    print(f"OK: {ergebnis['vorlage']} – {ergebnis['seiten']} Seite(n), {ergebnis['bytes'] // 1024} KB")
    print(f"  Browser: {ergebnis['browser']} {ergebnis['version']}"
          + (f" ({ergebnis['pfad']})" if ergebnis['browser'] == 'pfad' else ""))
    print(f"  Dauer:   {ergebnis['dauer_ms']} ms Druck (inkl. Browser-Start {gesamt_ms} ms; Zielwert "
          f"{pdf_html.ZIELZEIT_S:.0f} s je Angebot)")
    if ziel is not None:
        print(f"  Datei:   {ziel}")
    print(f"  Konto:   {konto} – der Dienst laeuft als SYSTEM; dort erneut pruefen, falls abweichend.")
    try:
        pdf_html.DRUCKER.schliessen()
    except Exception:   # noqa: BLE001
        pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
