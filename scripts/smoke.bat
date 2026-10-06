@echo off
rem Friondo Angebotstool: Smoke-Test nach jedem Update (v27, PLAN_V17 Phase 132) - etwa 2 Minuten.
rem Aufruf im Projektordner (kein Administrator noetig):   scripts\smoke.bat [--pin PIN] [--basis URL]
rem Prueft /health (ok oder warn; fehler = Fehlschlag), dann mit dem Admin-Sitzungscookie je HTTP 200
rem und Antwortzeit unter 3 s: Startseite, Erfassungsliste, Angebotsliste, eine Vorgangsakte, ein
rem Angebots-PDF, Hauptboard, Projektierung. --pin prueft zusaetzlich den echten Login (POST /login;
rem die PIN steht nie im Protokoll). Ergebnis: Konsole + data\log\smoke-<JJJJ-MM-TT_HHMM>.txt.
rem Exit-Code 0 = bestanden, 1 = Fehlschlag (Hinweis rollback.bat), 2 = Bedienfehler. Details: scripts\smoke.py
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
venv\Scripts\python.exe scripts\smoke.py %*
set "RC=%errorlevel%"
if defined CP_ALT chcp %CP_ALT% >nul
if not defined FRIONDO_OHNE_PAUSE pause
endlocal & exit /b %RC%
