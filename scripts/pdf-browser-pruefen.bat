@echo off
rem Friondo Angebotstool: Browser-Druck fuer das Angebots-PDF pruefen (v36, PLAN_V22 Phase 188/195).
rem Aufruf im Projektordner (kein Administrator noetig):   scripts\pdf-browser-pruefen.bat [--nur-suchen] [--sparte WP]
rem Sucht Edge/Chrome (PDF_BROWSER_PFAD aus der .env, Standardpfade, Playwright-Chromium), druckt ein
rem Test-PDF wie das Tool (keine Kundendaten, keine Datenbank) und meldet Browser, Version, Dauer und
rem den Pfad der Datei (data\log\pdf-browser-test-<Zeit>.pdf). Exit-Code 0 = ok, 1 = kein Browser oder
rem Druck fehlgeschlagen, 2 = Bedienfehler (venv/Playwright). Details: scripts\pdf_browser_pruefen.py
rem
rem Der Dienst FriondoAngebotstool laeuft als SYSTEM - der Druck muss auch unter diesem Konto laufen:
rem   psexec -s -i 0 cmd /c "cd /d %~dp0.. && scripts\pdf-browser-pruefen.bat"      (Sysinternals PsExec)
rem   oder geplante Aufgabe unter SYSTEM:  schtasks /Create /TN "Friondo PDF-Test" /SC ONCE /ST 23:59 /RU SYSTEM
rem        /TR "cmd /c cd /d <Projekt> && scripts\pdf-browser-pruefen.bat"  und dann  schtasks /Run /TN "Friondo PDF-Test"
rem   (Ergebnis in data\log\pdf-browser-test-*.pdf; Ausgabe mit > data\log\pdf-browser-test.txt umleiten).
setlocal
set "PROJEKT=%~dp0.."
for %%I in ("%PROJEKT%") do set "PROJEKT=%%~fI"
cd /d "%PROJEKT%"
if not exist "venv\Scripts\python.exe" (
    echo FEHLER: venv\Scripts\python.exe nicht gefunden - im Projektordner ausfuehren.
    exit /b 2
)
for /f "tokens=2 delims=:." %%c in ('chcp') do set "CP_ALT=%%c"
chcp 65001 >nul
set "PYTHONIOENCODING=utf-8"
venv\Scripts\python.exe scripts\pdf_browser_pruefen.py %*
set "RC=%errorlevel%"
if defined CP_ALT chcp %CP_ALT% >nul
if "%RC%"=="0" (
    echo.
    echo Browser-Pruefung OK ^(Exit-Code 0^). Parametrierung -^> Angebots-PDF zeigt den Stand; Engine html bleibt.
) else if "%RC%"=="1" (
    echo.
    echo Browser-Druck FEHLGESCHLAGEN - das Tool erzeugt PDFs im alten Layout ^(fpdf2^), bis der Browser laeuft.
    echo Edge installieren bzw. PDF_BROWSER_PFAD in der .env setzen oder:
    echo   venv\Scripts\python.exe -m playwright install chromium   ^(Internet noetig^)
)
if not defined FRIONDO_OHNE_PAUSE pause
endlocal & exit /b %RC%
