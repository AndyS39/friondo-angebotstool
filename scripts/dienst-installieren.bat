@echo off
rem Friondo Angebotstool: Einrichtung als Windows-Dienst mit Autostart (v27, PLAN_V17 Phase 129).
rem Als Administrator im Projektordner auf dem Server:   scripts\dienst-installieren.bat
rem   Weg A - NSSM: nssm.exe liegt neben diesem Skript (scripts\), im Projektordner oder unter
rem           C:\Friondo\ (Download https://nssm.cc/download, Datei win64\nssm.exe, keine Installation).
rem           -> Dienst "FriondoAngebotstool", Konto SYSTEM, Start automatisch, Neustart nach Absturz
rem              (5 s), Ausgabe data\log\dienst-out.log / dienst-err.log mit Rotation ab 10 MB.
rem   Weg B - Aufgabenplanung ohne Zusatzsoftware: Aufgabe "Friondo Angebotstool" (Start beim
rem           Hochfahren, SYSTEM, kein Zeitlimit, Ausgabe nach data\log\dienst-out.log).
rem   In beiden Faellen: Waechter-Aufgabe alle 5 Minuten (scripts\waechter.ps1: /health pruefen,
rem   bei Ausfall neu starten), venv/pip/.env, Firewall-Regel Port 8000, laufendes Konsolenfenster
rem   "Friondo Angebotstool Server" (start.bat) nach Rueckfrage beenden, alte Aufgabe "Friondo Backup"
rem   entfernen (die Sicherung laeuft seit v27 im Tool), am Ende /health anzeigen.
rem   PROXY_IPS in der .env (Reverse-Proxy der IT) -> uvicorn --proxy-headers --forwarded-allow-ips.
rem Schalter: --hilfe | --nssm PFAD\nssm.exe (nssm.exe an anderem Ort)
rem Wiederholbar: ein vorhandener Dienst bzw. eine vorhandene Aufgabe wird aktualisiert.
rem Anleitung: docs\installation-terminal-server.md Abschnitt 4 - Betrieb: docs\betrieb.md
setlocal
set "PROJEKT=%~dp0.."
for %%I in ("%PROJEKT%") do set "PROJEKT=%%~fI"
set "DIENST=FriondoAngebotstool"
set "AUFGABE=Friondo Angebotstool"
set "PS=powershell -NoProfile -ExecutionPolicy Bypass"
set "NSSM="
if /i "%~1"=="--hilfe" goto :hilfe
if /i "%~1"=="/?" goto :hilfe
if /i "%~1"=="--nssm" set "NSSM=%~f2"

echo == Friondo Angebotstool: Dienst einrichten ==
echo Projektordner: %PROJEKT%
net session >nul 2>&1 || (
    echo FEHLER: Bitte die Eingabeaufforderung "Als Administrator ausfuehren" und das Skript erneut starten.
    exit /b 1
)

rem --- 1) Weg bestimmen -------------------------------------------------------------
if defined NSSM if not exist "%NSSM%" (
    echo FEHLER: %NSSM% nicht gefunden.
    exit /b 1
)
if not defined NSSM if exist "%~dp0nssm.exe" set "NSSM=%~dp0nssm.exe"
if not defined NSSM if exist "%PROJEKT%\nssm.exe" set "NSSM=%PROJEKT%\nssm.exe"
if not defined NSSM if exist "C:\Friondo\nssm.exe" set "NSSM=C:\Friondo\nssm.exe"
set "WEG=B"
if defined NSSM set "WEG=A"
if "%WEG%"=="A" (
    echo Weg A: NSSM gefunden - %NSSM%
) else (
    echo Weg B: kein nssm.exe gefunden - Einrichtung ueber die Aufgabenplanung.
    echo         Fuer einen echten Windows-Dienst: nssm.exe von https://nssm.cc/download ^(win64\nssm.exe^)
    echo         nach %~dp0 kopieren und dieses Skript erneut ausfuehren.
)
sc query %DIENST% >nul 2>&1
if not errorlevel 1 if "%WEG%"=="B" (
    echo FEHLER: Der Dienst %DIENST% ist vorhanden, aber nssm.exe wurde nicht gefunden.
    echo         nssm.exe wieder nach scripts\ legen - oder den Dienst mit scripts\dienst-entfernen.bat entfernen.
    exit /b 1
)

rem --- 2) venv, Abhaengigkeiten, .env, Log-Ordner -------------------------------------
if not exist "%PROJEKT%\venv\Scripts\python.exe" (
    echo Erstelle virtuelle Umgebung ...
    python -m venv "%PROJEKT%\venv" || (
        echo FEHLER: python -m venv fehlgeschlagen - ist Python 3.12 oder neuer installiert und im PATH?
        exit /b 1
    )
)
echo Abhaengigkeiten pruefen ^(pip^) ...
"%PROJEKT%\venv\Scripts\python.exe" -m pip install -q -r "%PROJEKT%\requirements.txt" || (
    echo FEHLER: pip install fehlgeschlagen - Meldung oben pruefen.
    exit /b 1
)
if not exist "%PROJEKT%\.env" (
    if exist "%PROJEKT%\.env.example" copy "%PROJEKT%\.env.example" "%PROJEKT%\.env" >nul
    echo Hinweis: .env aus .env.example angelegt - BACKUP_ZIEL und Tokens eintragen ^(docs\betrieb.md^).
)
if not exist "%PROJEKT%\data\log" mkdir "%PROJEKT%\data\log"
rem Wartungsmarker: ein bereits eingerichteter Waechter startet waehrend der Einrichtung nichts neu
echo %date% %time% dienst-installieren.bat> "%PROJEKT%\data\log\wartung.marker"

rem --- 3) PROXY_IPS aus der .env (nur wenn gesetzt) -----------------------------------
set "PROXY_IPS="
if exist "%PROJEKT%\.env" for /f "usebackq tokens=1,* delims==" %%A in (`findstr /b /i "PROXY_IPS=" "%PROJEKT%\.env"`) do set "PROXY_IPS=%%B"
set "PROXY_ARGS="
if defined PROXY_IPS set "PROXY_IPS=%PROXY_IPS:"=%"
if defined PROXY_IPS set "PROXY_ARGS=--proxy-headers --forwarded-allow-ips %PROXY_IPS%"
if defined PROXY_ARGS echo Reverse-Proxy ^(.env PROXY_IPS^): uvicorn %PROXY_ARGS%

rem --- 4) Konsolenfenster "Friondo Angebotstool Server" (start.bat) beenden -----------
tasklist /FI "WINDOWTITLE eq Friondo Angebotstool Server*" /NH 2>nul | find /i ".exe" >nul
if errorlevel 1 goto :konsole_fertig
echo.
echo Ein Konsolenfenster "Friondo Angebotstool Server" ^(Start aus start.bat^) laeuft noch.
echo Es muss beendet werden, damit der Dienst Port 8000 uebernehmen kann.
set /p ANTWORT=Jetzt beenden? (j/n)
if /i not "%ANTWORT%"=="j" (
    echo Abgebrochen - das Konsolenfenster laeuft weiter. Bitte erst beenden, dann erneut ausfuehren.
    exit /b 1
)
taskkill /FI "WINDOWTITLE eq Friondo Angebotstool Server*" /T /F >nul 2>&1
timeout /t 2 /nobreak >nul
:konsole_fertig

rem --- 5) Laufende Instanzen anhalten (Wiederholungslauf) und Port 8000 freimachen ----
sc query %DIENST% >nul 2>&1 && net stop %DIENST% >nul 2>&1
schtasks /Query /TN "%AUFGABE%" >nul 2>&1 && schtasks /End /TN "%AUFGABE%" >nul 2>&1
%PS% -Command "$e=(Get-Date).AddSeconds(10); while((Get-Date) -lt $e){ if(-not (Get-NetTCPConnection -LocalPort 8000 -State Listen -ErrorAction SilentlyContinue)){ exit 0 }; Start-Sleep -Milliseconds 500 }; Get-NetTCPConnection -LocalPort 8000 -State Listen -ErrorAction SilentlyContinue | Select-Object -ExpandProperty OwningProcess -Unique | ForEach-Object { $p = Get-Process -Id $_ -ErrorAction SilentlyContinue; Write-Host ('  Port 8000 belegt durch ' + $(if($p){$p.ProcessName}else{'?'}) + ' (PID ' + $_ + ')') }; exit 1"
if errorlevel 1 goto :port_belegt
goto :port_fertig
:port_belegt
echo Port 8000 ist noch belegt ^(z. B. Konsolenfenster in einer anderen Sitzung^).
set /p ANTWORT=Diese Prozesse jetzt beenden? [j/n]
if /i not "%ANTWORT%"=="j" (
    echo Abgebrochen - Port 8000 muss frei sein. Prozess im Task-Manager beenden und erneut ausfuehren.
    exit /b 1
)
%PS% -Command "Get-NetTCPConnection -LocalPort 8000 -State Listen -ErrorAction SilentlyContinue | Select-Object -ExpandProperty OwningProcess -Unique | ForEach-Object { Stop-Process -Id $_ -Force -ErrorAction SilentlyContinue }; Start-Sleep -Seconds 1; if (Get-NetTCPConnection -LocalPort 8000 -State Listen -ErrorAction SilentlyContinue) { exit 1 }; exit 0"
if errorlevel 1 (
    echo FEHLER: Port 8000 ist weiterhin belegt.
    exit /b 1
)
:port_fertig

rem --- 6) Alte Backup-Aufgabe aus dem Hotfix entfernen --------------------------------
schtasks /Query /TN "Friondo Backup" >nul 2>&1 && (
    echo Hinweis: Die Aufgabe "Friondo Backup" ^(Hotfix 06.10.2026^) wird entfernt - die Sicherung laeuft
    echo          seit v27 im Tool ^(Scheduler 02:30, Spiegelung nach BACKUP_ZIEL aus der .env^).
    schtasks /Delete /TN "Friondo Backup" /F >nul 2>&1
)

rem --- 7) Weg A (NSSM) oder Weg B (Aufgabenplanung) einrichten -------------------------
if "%WEG%"=="A" goto :weg_a
echo.
echo Aufgaben anlegen ...
%PS% -File "%~dp0waechter.ps1" -AufgabeAnlegen -ProxyArgs "%PROXY_ARGS%" -WaechterAnlegen || goto :fehler
schtasks /Run /TN "%AUFGABE%" >nul 2>&1 || (
    echo FEHLER: Die Aufgabe "%AUFGABE%" konnte nicht gestartet werden.
    goto :fehler
)
goto :firewall

:weg_a
echo.
schtasks /Query /TN "%AUFGABE%" >nul 2>&1 && (
    echo Die Aufgabe "%AUFGABE%" ^(Weg B^) wird durch den Dienst ersetzt.
    schtasks /Delete /TN "%AUFGABE%" /F >nul 2>&1
)
sc query %DIENST% >nul 2>&1
if errorlevel 1 (
    echo Dienst %DIENST% anlegen ...
    "%NSSM%" install %DIENST% "%PROJEKT%\venv\Scripts\python.exe" >nul || goto :fehler
) else (
    echo Dienst %DIENST% vorhanden - Einstellungen werden aktualisiert ^(Dienstkonto bleibt^).
)
"%NSSM%" set %DIENST% Application "%PROJEKT%\venv\Scripts\python.exe" >nul || goto :fehler
"%NSSM%" set %DIENST% AppParameters "-m uvicorn app.main:app --host 0.0.0.0 --port 8000 %PROXY_ARGS%" >nul || goto :fehler
"%NSSM%" set %DIENST% AppDirectory "%PROJEKT%" >nul || goto :fehler
"%NSSM%" set %DIENST% DisplayName "Friondo Angebotstool" >nul
"%NSSM%" set %DIENST% Description "Friondo Angebotstool (uvicorn, Port 8000) - Projektordner %PROJEKT% - Verwaltung: scripts\dienst-*.bat" >nul
"%NSSM%" set %DIENST% Start SERVICE_AUTO_START >nul
"%NSSM%" set %DIENST% AppExit Default Restart >nul
"%NSSM%" set %DIENST% AppRestartDelay 5000 >nul
"%NSSM%" set %DIENST% AppStdout "%PROJEKT%\data\log\dienst-out.log" >nul
"%NSSM%" set %DIENST% AppStderr "%PROJEKT%\data\log\dienst-err.log" >nul
"%NSSM%" set %DIENST% AppRotateFiles 1 >nul
"%NSSM%" set %DIENST% AppRotateOnline 1 >nul
"%NSSM%" set %DIENST% AppRotateBytes 10000000 >nul
"%NSSM%" set %DIENST% AppStopMethodConsole 10000 >nul
"%NSSM%" set %DIENST% AppEnvironmentExtra PYTHONIOENCODING=utf-8 >nul
%PS% -File "%~dp0waechter.ps1" -WaechterAnlegen || goto :fehler
echo Dienst starten ...
net start %DIENST% >nul 2>&1
%PS% -Command "if ((Get-Service %DIENST% -ErrorAction SilentlyContinue).Status -eq 'Running') { exit 0 } else { exit 1 }" || (
    echo FEHLER: Der Dienst konnte nicht gestartet werden - data\log\dienst-err.log pruefen.
    goto :fehler
)

:firewall
rem --- 8) Firewall-Freigabe Port 8000 (nur falls noch nicht vorhanden) ----------------
netsh advfirewall firewall show rule name="Friondo Angebotstool" >nul 2>&1
if errorlevel 1 netsh advfirewall firewall add rule name="Friondo Angebotstool" dir=in action=allow protocol=TCP localport=8000 >nul
if exist "%PROJEKT%\data\log\wartung.marker" del /q "%PROJEKT%\data\log\wartung.marker"

rem --- 9) Kontrolle ueber /health ------------------------------------------------------
echo.
echo Kontrolle /health ^(wartet bis zu 30 s auf den Start^) ...
%PS% -File "%~dp0health-pruefen.ps1" -Adresse http://127.0.0.1:8000/health -Warten 30 -NurAnzeigen
if errorlevel 1 (
    echo FEHLER: /health antwortet nicht oder meldet "fehler" - data\log\dienst-err.log und data\fehler.log pruefen.
    goto :fehler
)
echo.
echo Fertig - Weg %WEG% eingerichtet.
if "%WEG%"=="A" (
    echo   Dienst %DIENST%: Konto SYSTEM, Autostart, Neustart nach Absturz. Dienstkonto der IT spaeter:
    echo     "%NSSM%" set %DIENST% ObjectName "DOMAENE\Konto" "Kennwort"   ^(danach scripts\dienst-neustart.bat^)
) else (
    echo   Aufgabe "%AUFGABE%": Konto SYSTEM, Start beim Hochfahren, kein Zeitlimit.
)
echo   Waechter-Aufgabe alle 5 Minuten ^(Log data\log\waechter.log^), Firewall-Regel "Friondo Angebotstool".
echo   Logs: data\log\dienst-out.log, dienst-err.log ^(Rotation 10 MB^), data\fehler.log, data\log\zugriff.log
echo   Verwaltung: scripts\dienst-status.bat, scripts\dienst-neustart.bat, scripts\dienst-entfernen.bat
echo   Im Browser: http://localhost:8000  -  im Firmennetz http://192.168.35.4:8000
endlocal
exit /b 0

:fehler
echo.
echo FEHLER bei der Einrichtung - Meldungen oben pruefen. Das Skript kann erneut ausgefuehrt werden.
endlocal
exit /b 1

:hilfe
echo scripts\dienst-installieren.bat [--nssm PFAD\nssm.exe]   ^(als Administrator im Projektordner^)
echo   Richtet das Friondo Angebotstool als Dienst mit Autostart ein:
echo   Weg A = NSSM ^(nssm.exe in scripts\, im Projektordner oder C:\Friondo\^) -^> Dienst FriondoAngebotstool
echo   Weg B = Aufgabenplanung -^> Aufgabe "Friondo Angebotstool" ^(SYSTEM, Start beim Hochfahren^)
echo   immer: Waechter-Aufgabe alle 5 Minuten, Firewall-Regel Port 8000, /health-Kontrolle.
echo   Anleitung: docs\installation-terminal-server.md Abschnitt 4
endlocal
exit /b 0
