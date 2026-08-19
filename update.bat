@echo off
rem Friondo Angebotstool: Update auf dem Server einspielen (als Administrator).
rem Ablauf: Dienst stoppen -> Backup -> git pull -> Abhaengigkeiten -> migrate.py -> Dienst starten
rem Fehlerpfade: git pull fehlgeschlagen  -> alter Stand wird wieder gestartet
rem              Migration fehlgeschlagen -> Tool bleibt GESTOPPT, Backup-Hinweis
setlocal
cd /d "%~dp0"
echo == Friondo Angebotstool: Update ==

echo [1/6] Dienst stoppen ...
schtasks /End /TN "Friondo Angebotstool" >nul 2>&1
timeout /t 3 /nobreak >nul

echo [2/6] Backup anlegen ...
for /f %%i in ('powershell -NoProfile -Command "Get-Date -Format yyyy-MM-dd_HHmm"') do set "ZEITSTEMPEL=%%i"
set "BACKUP=data\backups\update_%ZEITSTEMPEL%"
mkdir "%BACKUP%" 2>nul
if exist data\*.db copy /y data\*.db "%BACKUP%\" >nul
if exist .env copy /y .env "%BACKUP%\" >nul
echo       Backup: %CD%\%BACKUP%

echo [3/6] Neuen Stand holen (git pull) ...
git remote get-url origin >nul 2>&1 || (
    echo FEHLER: Kein Git-Remote origin eingerichtet - siehe docs\updates.md.
    goto :pull_fehler
)
git pull --ff-only || goto :pull_fehler

echo [4/6] Abhaengigkeiten aktualisieren ...
venv\Scripts\pip install -q -r requirements.txt || (
    echo FEHLER: pip install fehlgeschlagen - siehe Meldung oben.
    goto :migration_fehler
)

echo [5/6] Datenbank migrieren ...
if exist migrate.py (
    venv\Scripts\python migrate.py || goto :migration_fehler
) else (
    echo       migrate.py nicht vorhanden - uebersprungen.
)

echo [6/6] Dienst starten ...
schtasks /Run /TN "Friondo Angebotstool" >nul 2>&1
echo.
echo Fertig. Bitte http://localhost:8000 pruefen.
echo Backup dieses Updates: %CD%\%BACKUP%
pause
endlocal
exit /b 0

:pull_fehler
echo.
echo FEHLER: git pull fehlgeschlagen - es wurde NICHTS geaendert.
echo Der bisherige Stand wird wieder gestartet.
schtasks /Run /TN "Friondo Angebotstool" >nul 2>&1
echo Backup (unveraendert): %CD%\%BACKUP%
pause
endlocal
exit /b 1

:migration_fehler
echo.
echo ========================================================================
echo FEHLER: Die Datenbank-Migration ist fehlgeschlagen.
echo Das Tool wurde NICHT gestartet, damit keine inkonsistenten Daten
echo entstehen. Bitte Meldung oben pruefen.
echo Backup von Datenbank und .env vor dem Update:
echo   %CD%\%BACKUP%
echo Zuruecksetzen: rollback.bat ausfuehren (stellt Code und Backup wieder her)
echo ========================================================================
pause
endlocal
exit /b 2
