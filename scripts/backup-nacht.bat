@echo off
rem Friondo Angebotstool - naechtliche Sicherung (Hotfix 06.10.2026, Uebergangsloesung
rem bis PLAN_V17). Laeuft als geplante Aufgabe "Friondo Backup" taeglich 02:30:
rem   1) SQLite-Datenbank ueber db.taegliches_backup() nach data\backups sichern
rem      (SQLite-Backup-API, WAL-sicher, eine Datei je Tag, 30 Tage Aufbewahrung)
rem   2) data\backups, data\angebote und data\projekte per robocopy nach
rem      BACKUP_ZIEL (aus .env) spiegeln
rem Aufruf von Hand zum Testen:  scripts\backup-nacht.bat  [Zielordner]
rem   (ein optionaler erster Parameter ueberschreibt BACKUP_ZIEL aus der .env)
rem Einrichtung der Aufgabe: docs\nach-dem-update-v26.md (Abschnitt Backup)
setlocal
set "PROJEKT=%~dp0.."
for %%I in ("%PROJEKT%") do set "PROJEKT=%%~fI"
set "LOG=%PROJEKT%\data\backup-nacht.log"

rem BACKUP_ZIEL aus .env lesen (Zeile BACKUP_ZIEL=<Pfad>, ohne Anfuehrungszeichen)
set "BACKUP_ZIEL="
if exist "%PROJEKT%\.env" (
    for /f "usebackq tokens=1,* delims==" %%A in (`findstr /b /i "BACKUP_ZIEL=" "%PROJEKT%\.env"`) do set "BACKUP_ZIEL=%%B"
)
if not "%~1"=="" set "BACKUP_ZIEL=%~1"
if "%BACKUP_ZIEL%"=="" (
    echo %date% %time% FEHLER: BACKUP_ZIEL fehlt in .env - Vorlage in .env.example >> "%LOG%"
    echo FEHLER: BACKUP_ZIEL fehlt in .env - Vorlage in .env.example
    exit /b 2
)

echo %date% %time% Backup startet - Ziel %BACKUP_ZIEL% >> "%LOG%"

rem 1) Datenbank sichern (bestehende Funktion, laeuft auch bei laufendem Server)
"%PROJEKT%\venv\Scripts\python.exe" -c "from app.db import taegliches_backup; taegliches_backup(); print('DB-Backup ok')" >> "%LOG%" 2>&1
if errorlevel 1 (
    echo %date% %time% FEHLER: DB-Backup fehlgeschlagen >> "%LOG%"
    exit /b 1
)

rem 2) Ordner spiegeln (robocopy: Exit-Code ab 8 = Fehler, darunter nur Statistik)
set "FEHLER=0"
for %%O in (backups angebote projekte) do (
    if exist "%PROJEKT%\data\%%O" (
        robocopy "%PROJEKT%\data\%%O" "%BACKUP_ZIEL%\%%O" /E /R:2 /W:5 /NP /NFL /NDL /NJH /LOG+:"%LOG%"
        if errorlevel 8 set "FEHLER=1"
    ) else (
        echo %date% %time% Hinweis: data\%%O fehlt - uebersprungen >> "%LOG%"
    )
)

if "%FEHLER%"=="1" (
    echo %date% %time% FEHLER: robocopy meldete Fehler - siehe Log >> "%LOG%"
    exit /b 1
)
echo %date% %time% Backup fertig >> "%LOG%"
exit /b 0
