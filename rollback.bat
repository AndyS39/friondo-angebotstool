@echo off
rem Friondo Angebotstool: letztes Update zuruecknehmen (als Administrator).
rem 1) Code auf den Stand VOR dem letzten git pull zurueck (ORIG_HEAD)
rem 2) Datenbank + .env aus dem juengsten data\backups\update_* zurueckspielen
rem 3) Dienst wieder starten
rem Aufruf ohne Parameter = juengstes Update-Backup; optional: rollback.bat data\backups\update_JJJJ-MM-TT_HHMM
setlocal
cd /d "%~dp0"
echo == Friondo Angebotstool: Rollback ==

set "BACKUP=%~1"
if "%BACKUP%"=="" (
    for /f "delims=" %%d in ('dir /b /ad /o-n data\backups\update_* 2^>nul') do (
        if not defined BACKUP set "BACKUP=data\backups\%%d"
    )
)
if "%BACKUP%"=="" (
    echo FEHLER: Kein Update-Backup unter data\backups\update_* gefunden.
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
set /p ANTWORT=Fortfahren? (j/n)
if /i not "%ANTWORT%"=="j" (
    echo Abgebrochen.
    pause
    exit /b 0
)

echo [1/4] Dienst stoppen ...
schtasks /End /TN "Friondo Angebotstool" >nul 2>&1
timeout /t 3 /nobreak >nul

echo [2/4] Code zuruecksetzen ...
git rev-parse -q --verify ORIG_HEAD >nul 2>&1
if errorlevel 1 (
    echo       Kein ORIG_HEAD vorhanden ^(kein vorheriger git pull^) - Code bleibt unveraendert.
) else (
    git reset --hard ORIG_HEAD || (echo FEHLER beim git reset & pause & exit /b 1)
)

echo [3/4] Datenbank und .env zurueckspielen ...
del /q data\angebotstool.db-wal data\angebotstool.db-shm 2>nul
copy /y "%BACKUP%\*.db" data\ >nul || (echo FEHLER beim Kopieren der Datenbank & pause & exit /b 1)
if exist "%BACKUP%\.env" copy /y "%BACKUP%\.env" .env >nul
venv\Scripts\pip install -q -r requirements.txt

echo [4/4] Dienst starten ...
schtasks /Run /TN "Friondo Angebotstool" >nul 2>&1
echo.
echo Rollback abgeschlossen. Bitte http://localhost:8000 pruefen.
pause
endlocal
exit /b 0
