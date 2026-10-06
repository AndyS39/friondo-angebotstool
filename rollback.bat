@echo off
rem Friondo Angebotstool: letztes Update zuruecknehmen (als Administrator).
rem Standard:   rollback.bat [data\backups\update_JJJJ-MM-TT_HHMM]
rem   1) Code auf den Stand VOR dem letzten git pull zurueck (ORIG_HEAD)
rem   2) Datenbank + .env aus dem juengsten (oder angegebenen) data\backups\update_* zurueckspielen
rem      - mit Rueckfrage: alles, was seit dem Update erfasst wurde, geht verloren
rem   3) Tool wieder starten
rem Nur Code:   rollback.bat --nur-code
rem   Code zurueck (ORIG_HEAD), Datenbank und .env BLEIBEN. v27-Regel: alle Datenbank-Aenderungen sind
rem   additiv, der vorherige Code laeuft auf der neueren Datenbank weiter -> kein Datenverlust, keine
rem   Rueckfrage. Sitzungs-Cookies der neuen Fassung weist der alte Code ab -> einmal neu anmelden.
rem Der Weg (Dienst/Aufgabe/Konsolenfenster) wird ueber scripts\dienst-neustart.bat erkannt.
setlocal
cd /d "%~dp0"
set "NEUSTART=%~dp0scripts\dienst-neustart.bat"
set "NURCODE="
set "BACKUP="
:args
if "%~1"=="" goto :args_fertig
if /i "%~1"=="--nur-code" (
    set "NURCODE=1"
) else if /i "%~1"=="--hilfe" (
    goto :hilfe
) else (
    set "BACKUP=%~1"
)
shift
goto :args
:args_fertig
echo == Friondo Angebotstool: Rollback ==
if defined NURCODE goto :nur_code

if "%BACKUP%"=="" (
    for /f "delims=" %%d in ('dir /b /ad /o-n data\backups\update_* 2^>nul') do (
        if not defined BACKUP set "BACKUP=data\backups\%%d"
    )
)
if "%BACKUP%"=="" (
    echo FEHLER: Kein Update-Backup unter data\backups\update_* gefunden.
    echo Nur den Code zuruecksetzen: rollback.bat --nur-code
    pause
    exit /b 1
)
if not exist "%BACKUP%\angebotstool.db" (
    echo FEHLER: Im Backup %BACKUP% liegt keine angebotstool.db.
    pause
    exit /b 1
)
echo Backup: %CD%\%BACKUP%
echo.
echo ACHTUNG: Datenbank und .env werden auf den Stand dieses Backups
echo zurueckgesetzt - alles, was seit dem Update erfasst wurde, geht verloren.
echo ^(Nur den Code zuruecksetzen, Datenbank behalten: rollback.bat --nur-code^)
set /p ANTWORT=Fortfahren? (j/n)
if /i not "%ANTWORT%"=="j" (
    echo Abgebrochen.
    pause
    exit /b 0
)

echo [1/4] Tool stoppen ...
call "%NEUSTART%" --stop || (
    echo FEHLER beim Stoppen - siehe oben.
    pause
    exit /b 1
)
echo [2/4] Code zuruecksetzen ...
call :code_zurueck || (
    pause
    exit /b 1
)
echo [3/4] Datenbank und .env zurueckspielen ...
del /q data\angebotstool.db-wal data\angebotstool.db-shm 2>nul
copy /y "%BACKUP%\*.db" data\ >nul || (
    echo FEHLER beim Kopieren der Datenbank
    pause
    exit /b 1
)
if exist "%BACKUP%\.env" copy /y "%BACKUP%\.env" .env >nul
venv\Scripts\python.exe -m pip install -q -r requirements.txt
echo [4/4] Tool starten ...
goto :starten

:nur_code
echo Modus --nur-code: Code zurueck auf den Stand vor dem letzten Update, Datenbank und .env bleiben.
echo [1/3] Tool stoppen ...
call "%NEUSTART%" --stop || (
    echo FEHLER beim Stoppen - siehe oben.
    pause
    exit /b 1
)
echo [2/3] Code zuruecksetzen ...
call :code_zurueck || (
    pause
    exit /b 1
)
venv\Scripts\python.exe -m pip install -q -r requirements.txt
echo [3/3] Tool starten ...
goto :starten

:starten
call "%NEUSTART%" --start
set "RC=%errorlevel%"
if "%RC%"=="3" (
    echo Kein Dienst/keine Aufgabe: bitte start.bat neu starten.
) else if not "%RC%"=="0" (
    echo FEHLER: Das Tool antwortet nach dem Rollback nicht - data\fehler.log pruefen.
    pause
    exit /b 1
)
echo.
echo Rollback abgeschlossen. Bitte http://localhost:8000 pruefen - alle Nutzer muessen sich einmal neu anmelden.
echo Hinweis: /health gibt es erst ab v27 - bei einem Stand davor meldet die Kontrolle "HTTP 404" ^(normal^).
pause
endlocal
exit /b 0

:code_zurueck
git rev-parse -q --verify ORIG_HEAD >nul 2>&1
if errorlevel 1 (
    echo       Kein ORIG_HEAD vorhanden ^(kein vorheriger git pull^) - Code bleibt unveraendert.
    exit /b 0
)
git reset --hard ORIG_HEAD || (
    echo FEHLER beim git reset
    exit /b 1
)
exit /b 0

:hilfe
echo rollback.bat [--nur-code] [data\backups\update_JJJJ-MM-TT_HHMM]   ^(als Administrator^)
echo   ohne --nur-code: Code zurueck ^(ORIG_HEAD^) UND Datenbank/.env aus der Update-Sicherung ^(Rueckfrage^)
echo   --nur-code     : nur Code zurueck, Datenbank bleibt ^(v27: Datenbank-Aenderungen sind additiv^)
echo   Danach: einmal neu anmelden ^(alte Cookies werden abgewiesen^). Details: docs\updates.md
endlocal
exit /b 0
