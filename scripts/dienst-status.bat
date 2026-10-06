@echo off
rem Friondo Angebotstool: Betriebsstatus anzeigen (v27, PLAN_V17 Phase 129) - kein Administrator noetig.
rem Aufruf im Projektordner:   scripts\dienst-status.bat
rem Zeigt: Weg (Dienst/Aufgabe/Konsole) und Zustand, Waechter-Aufgabe, Port 8000, Wartungsmarker,
rem Log-Groessen, letzte Waechter-Zeilen, /health (Status, Version, Commit, DB, Uptime, Pool, Gruende),
rem letzte Sicherung, letzte Zeilen von backups\ziel.log und fehler.log.
rem Exit-Code: 0 = /health ok oder warn, 1 = fehler/keine Antwort.
setlocal
set "PROJEKT=%~dp0.."
for %%I in ("%PROJEKT%") do set "PROJEKT=%%~fI"
set "PS=powershell -NoProfile -ExecutionPolicy Bypass"
if /i "%~1"=="--hilfe" (
    echo scripts\dienst-status.bat  - zeigt Dienst/Aufgabe, Port 8000, Waechter, /health und Sicherungsstand.
    exit /b 0
)
echo == Friondo Angebotstool: Status ==
%PS% -File "%~dp0waechter.ps1" -Status
echo.
%PS% -File "%~dp0health-pruefen.ps1" -Adresse http://127.0.0.1:8000/health -NurAnzeigen
set "RC=%errorlevel%"
echo.
set "LETZTE="
for /f "delims=" %%f in ('dir /b /o-n "%PROJEKT%\data\backups\angebotstool-*.db" 2^>nul') do if not defined LETZTE set "LETZTE=%%f"
if defined LETZTE (
    echo Letzte Sicherung: data\backups\%LETZTE%
) else (
    echo Letzte Sicherung: keine gefunden ^(data\backups\angebotstool-*.db^)
)
if exist "%PROJEKT%\data\backups\ziel.log" (
    echo Spiegelung ^(data\backups\ziel.log, letzte 3 Zeilen^):
    %PS% -Command "Get-Content -LiteralPath '%PROJEKT%\data\backups\ziel.log' -Tail 3 -Encoding UTF8 | ForEach-Object { '  ' + $_ }"
)
if exist "%PROJEKT%\data\fehler.log" (
    echo fehler.log ^(letzte 3 Zeilen^):
    %PS% -Command "Get-Content -LiteralPath '%PROJEKT%\data\fehler.log' -Tail 3 -Encoding UTF8 | ForEach-Object { '  ' + $_ }"
)
echo.
echo Verwaltung: scripts\dienst-neustart.bat ^(als Administrator^), Runbook docs\betrieb.md
if not defined FRIONDO_OHNE_PAUSE pause
exit /b %RC%
