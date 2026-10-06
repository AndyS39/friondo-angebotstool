@echo off
rem Friondo Angebotstool: Dienst/Aufgabe stoppen, starten, neu starten (v27, PLAN_V17 Phase 129).
rem Als Administrator im Projektordner:   scripts\dienst-neustart.bat [--stop | --start | --hilfe]
rem Erkennt den Weg selbst:
rem   Dienst "FriondoAngebotstool" (NSSM)   -> net stop / net start
rem   Aufgabe "Friondo Angebotstool"       -> schtasks /End (+ Log-Rotation) / schtasks /Run
rem   sonst Konsolenfenster "Friondo Angebotstool Server" (start.bat) -> beenden; Start nur per start.bat
rem Beim Stoppen bleibt nichts auf Port 8000 zurueck (verbliebene Prozesse werden beendet) und der
rem Wartungsmarker data\log\wartung.marker wird gesetzt - der Waechter greift dann nicht ein. Beim
rem Starten wird /health abgewartet (bis 45 s) und der Marker wieder entfernt.
rem update.bat und rollback.bat rufen dieses Skript mit --stop bzw. --start auf.
rem Exit-Code: 0 = ok, 1 = Fehler, 3 = kein Dienst/keine Aufgabe (Start von Hand: start.bat).
setlocal
set "PROJEKT=%~dp0.."
for %%I in ("%PROJEKT%") do set "PROJEKT=%%~fI"
set "DIENST=FriondoAngebotstool"
set "AUFGABE=Friondo Angebotstool"
set "PS=powershell -NoProfile -ExecutionPolicy Bypass"
set "MARKER=%PROJEKT%\data\log\wartung.marker"
set "MODUS=%~1"
if /i "%MODUS%"=="--hilfe" goto :hilfe
if /i "%MODUS%"=="/?" goto :hilfe
if "%MODUS%"=="" set "MODUS=--neustart"
if /i not "%MODUS%"=="--stop" if /i not "%MODUS%"=="--start" if /i not "%MODUS%"=="--neustart" (
    echo Unbekannter Schalter: %MODUS%
    goto :hilfe
)

net session >nul 2>&1 || (
    echo FEHLER: Bitte die Eingabeaufforderung "Als Administrator ausfuehren".
    exit /b 1
)

set "WEG=konsole"
sc query %DIENST% >nul 2>&1 && set "WEG=dienst"
if "%WEG%"=="konsole" (
    schtasks /Query /TN "%AUFGABE%" >nul 2>&1 && set "WEG=aufgabe"
)
echo Weg: %WEG%   ^(Projektordner %PROJEKT%^)

if /i "%MODUS%"=="--start" goto :start
call :marker_setzen
call :stoppen || exit /b 1
if /i "%MODUS%"=="--stop" exit /b 0

:start
call :starten
set "RC=%errorlevel%"
rem Marker weg bei Erfolg (0) und in der Konsolen-Variante (3, Start von Hand) - nicht bei Fehler (1)
if not "%RC%"=="1" call :marker_entfernen
exit /b %RC%


:stoppen
echo Stoppen ...
if "%WEG%"=="dienst" net stop %DIENST% >nul 2>&1
if "%WEG%"=="aufgabe" schtasks /End /TN "%AUFGABE%" >nul 2>&1
if "%WEG%"=="konsole" taskkill /FI "WINDOWTITLE eq Friondo Angebotstool Server*" /T /F >nul 2>&1
rem Port 8000 freigeben: bis 15 s warten, danach verbliebene Prozesse beenden (Waisen, andere Sitzung)
%PS% -Command "$e=(Get-Date).AddSeconds(15); while((Get-Date) -lt $e){ if(-not (Get-NetTCPConnection -LocalPort 8000 -State Listen -ErrorAction SilentlyContinue)){ exit 0 }; Start-Sleep -Milliseconds 500 }; Get-NetTCPConnection -LocalPort 8000 -State Listen -ErrorAction SilentlyContinue | Select-Object -ExpandProperty OwningProcess -Unique | ForEach-Object { $p = Get-Process -Id $_ -ErrorAction SilentlyContinue; Write-Host ('  Prozess ' + $(if($p){$p.ProcessName}else{'?'}) + ' (PID ' + $_ + ') haelt Port 8000 - wird beendet'); Stop-Process -Id $_ -Force -ErrorAction SilentlyContinue }; Start-Sleep -Seconds 1; if (Get-NetTCPConnection -LocalPort 8000 -State Listen -ErrorAction SilentlyContinue) { exit 1 }; exit 0"
if errorlevel 1 (
    echo FEHLER: Port 8000 ist weiterhin belegt - Prozess im Task-Manager beenden.
    exit /b 1
)
if "%WEG%"=="aufgabe" %PS% -File "%~dp0waechter.ps1" -Rotieren
echo Gestoppt.
exit /b 0


:starten
echo Starten ...
if "%WEG%"=="konsole" (
    echo Kein Dienst und keine Aufgabe vorhanden: bitte start.bat neu starten.
    echo ^(Dauerhaft besser: scripts\dienst-installieren.bat als Administrator - siehe docs\betrieb.md.^)
    exit /b 3
)
if "%WEG%"=="dienst" (
    net start %DIENST% >nul 2>&1
    %PS% -Command "if ((Get-Service %DIENST% -ErrorAction SilentlyContinue).Status -eq 'Running') { exit 0 } else { exit 1 }" || (
        echo FEHLER: Dienst %DIENST% laeuft nicht - data\log\dienst-err.log pruefen.
        exit /b 1
    )
)
if "%WEG%"=="aufgabe" (
    schtasks /Run /TN "%AUFGABE%" >nul 2>&1 || (
        echo FEHLER: Aufgabe "%AUFGABE%" konnte nicht gestartet werden.
        exit /b 1
    )
)
%PS% -File "%~dp0health-pruefen.ps1" -Adresse http://127.0.0.1:8000/health -Warten 45 -NurAnzeigen
if errorlevel 1 (
    echo FEHLER: /health antwortet nicht oder meldet "fehler" - data\fehler.log und data\log\dienst-err.log pruefen.
    exit /b 1
)
echo Gestartet.
exit /b 0


:marker_setzen
if not exist "%PROJEKT%\data\log" mkdir "%PROJEKT%\data\log"
echo %date% %time% %MODUS% ^(dienst-neustart.bat^)> "%MARKER%"
exit /b 0

:marker_entfernen
if exist "%MARKER%" del /q "%MARKER%"
exit /b 0

:hilfe
echo scripts\dienst-neustart.bat [--stop ^| --start]   ^(als Administrator^)
echo   ohne Schalter: Tool stoppen und wieder starten ^(Dienst, Aufgabe oder Konsolenfenster wird erkannt^)
echo   --stop : nur stoppen ^(setzt data\log\wartung.marker - Waechter bleibt passiv^)
echo   --start: nur starten, /health abwarten, Marker entfernen
echo   Exit-Code 3 = kein Dienst/keine Aufgabe - Start von Hand mit start.bat
exit /b 0
