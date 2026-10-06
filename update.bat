@echo off
rem Friondo Angebotstool: Update auf dem Server einspielen (als Administrator, nur im Wartungsfenster).
rem Ablauf: Hinweis Wartungsfenster/Banner -> Tool stoppen -> Backup -> git pull -> Abhaengigkeiten
rem         -> migrate.py -> Tool starten + /health -> scripts\smoke.bat (Ergebnis anzeigen)
rem Der Weg wird ueber scripts\dienst-neustart.bat erkannt (v27): Dienst FriondoAngebotstool (NSSM)
rem -> net stop/start; Aufgabe "Friondo Angebotstool" -> schtasks /End + /Run; sonst Konsolenfenster
rem beenden und am Ende Hinweis "start.bat neu starten". Waehrend des Updates liegt der Wartungsmarker
rem data\log\wartung.marker (der Waechter startet nichts neu).
rem Fehlerpfade: git pull fehlgeschlagen   -> alter Stand wird wieder gestartet
rem              Migration fehlgeschlagen  -> Tool bleibt GESTOPPT, Backup-Hinweis, rollback.bat
rem              Smoke-Test fehlgeschlagen -> Tool laeuft mit neuem Stand, Hinweis rollback.bat
rem Schalter: --ohne-smoke (Smoke-Test ueberspringen), --hilfe
setlocal
cd /d "%~dp0"
set "NEUSTART=%~dp0scripts\dienst-neustart.bat"
if /i "%~1"=="--hilfe" goto :hilfe
echo == Friondo Angebotstool: Update ==
echo.
echo HINWEIS: Updates nur im Wartungsfenster ^(Standard Dienstag 18:30-19:30^) und mit gesetztem
echo Wartungsbanner ^(Parametrierung -^> Betrieb -^> Wartungshinweis, mindestens 30 Minuten vorher^).
echo Beim Stoppen werden angemeldete Nutzer kurz getrennt. Nur Hinweis - keine Blockade.
echo Abbruch: Strg+C - weiter: beliebige Taste ^(automatisch nach 10 s^).
timeout /t 10 >nul
echo.

echo [1/7] Tool stoppen ...
call "%NEUSTART%" --stop || (
    echo FEHLER: Stoppen fehlgeschlagen - siehe Meldung oben. Es wurde nichts geaendert.
    pause
    exit /b 1
)

echo [2/7] Backup anlegen ...
for /f %%i in ('powershell -NoProfile -Command "Get-Date -Format yyyy-MM-dd_HHmm"') do set "ZEITSTEMPEL=%%i"
set "BACKUP=data\backups\update_%ZEITSTEMPEL%"
mkdir "%BACKUP%" 2>nul
if exist data\*.db copy /y data\*.db "%BACKUP%\" >nul
if exist .env copy /y .env "%BACKUP%\" >nul
echo       Backup: %CD%\%BACKUP%

echo [3/7] Neuen Stand holen ^(git pull^) ...
git remote get-url origin >nul 2>&1 || (
    echo FEHLER: Kein Git-Remote origin eingerichtet - siehe docs\updates.md.
    goto :pull_fehler
)
git pull --ff-only || goto :pull_fehler

echo [4/7] Abhaengigkeiten aktualisieren ...
venv\Scripts\python.exe -m pip install -q -r requirements.txt || (
    echo FEHLER: pip install fehlgeschlagen - siehe Meldung oben.
    goto :migration_fehler
)

echo [5/7] Datenbank migrieren ...
if exist migrate.py (
    venv\Scripts\python.exe migrate.py || goto :migration_fehler
) else (
    echo       migrate.py nicht vorhanden - uebersprungen.
)

echo [6/7] Tool starten ...
call "%NEUSTART%" --start
set "START_RC=%errorlevel%"
if "%START_RC%"=="3" goto :konsole_start
if not "%START_RC%"=="0" goto :start_fehler

:smoke
if /i "%~1"=="--ohne-smoke" goto :fertig
echo [7/7] Smoke-Test ^(etwa 2 Minuten^) ...
set "FRIONDO_OHNE_PAUSE=1"
call "%~dp0scripts\smoke.bat"
if errorlevel 1 goto :smoke_fehler

:fertig
echo.
echo Fertig. Bitte http://localhost:8000 pruefen und das Wartungsbanner wieder entfernen
echo ^(Parametrierung -^> Betrieb -^> Hinweis entfernen^).
echo Backup dieses Updates: %CD%\%BACKUP%
pause
endlocal
exit /b 0

:konsole_start
echo.
echo Kein Dienst und keine Aufgabe vorhanden - bitte start.bat neu starten.
echo ^(Dauerhaft besser: scripts\dienst-installieren.bat als Administrator, docs\betrieb.md.^)
set /p ANTWORT=start.bat jetzt starten? (j/n)
if /i "%ANTWORT%"=="j" (
    call "%~dp0start.bat"
    goto :smoke
)
echo Danach den Smoke-Test von Hand ausfuehren: scripts\smoke.bat
echo Backup dieses Updates: %CD%\%BACKUP%
pause
endlocal
exit /b 0

:start_fehler
echo.
echo ========================================================================
echo FEHLER: Das Tool wurde gestartet, antwortet aber nicht auf /health.
echo Bitte data\fehler.log und data\log\dienst-err.log pruefen.
echo Zurueck zum alten Stand: rollback.bat ^(Code + Datenbank aus der Sicherung^)
echo oder rollback.bat --nur-code ^(nur Code, Datenbank bleibt^).
echo Backup dieses Updates: %CD%\%BACKUP%
echo ========================================================================
pause
endlocal
exit /b 3

:smoke_fehler
echo.
echo ========================================================================
echo FEHLER: Der Smoke-Test ist fehlgeschlagen ^(Protokoll: data\log\smoke-*.txt^).
echo Das Tool laeuft mit dem neuen Stand. Zurueck zum alten Stand:
echo   rollback.bat            Code + Datenbank aus der Sicherung ^(mit Rueckfrage^)
echo   rollback.bat --nur-code nur der Code, Datenbank bleibt ^(kein Datenverlust^)
echo Backup dieses Updates: %CD%\%BACKUP%
echo ========================================================================
pause
endlocal
exit /b 4

:pull_fehler
echo.
echo FEHLER: git pull fehlgeschlagen - es wurde NICHTS geaendert.
echo Der bisherige Stand wird wieder gestartet.
call "%NEUSTART%" --start
if errorlevel 3 echo Bitte start.bat neu starten.
echo Backup ^(unveraendert^): %CD%\%BACKUP%
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
echo Zuruecksetzen: rollback.bat ^(stellt Code und Sicherung wieder her^).
echo Der Waechter bleibt passiv, solange data\log\wartung.marker liegt
echo ^(rollback.bat bzw. scripts\dienst-neustart.bat entfernen ihn^).
echo ========================================================================
pause
endlocal
exit /b 2

:hilfe
echo update.bat [--ohne-smoke]   ^(als Administrator im Projektordner, im Wartungsfenster^)
echo   stoppt das Tool ^(Dienst/Aufgabe/Konsole wird erkannt^), sichert data\*.db und .env nach
echo   data\backups\update_^<Zeit^>, holt den neuen Stand ^(git pull --ff-only^), aktualisiert die
echo   Abhaengigkeiten, migriert die Datenbank, startet das Tool, prueft /health und fuehrt
echo   scripts\smoke.bat aus. Rueckweg: rollback.bat bzw. rollback.bat --nur-code. Details: docs\updates.md
endlocal
exit /b 0
