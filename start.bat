@echo off
rem Startet das Friondo Angebotstool (Entwicklungs-PC / Einzelplatz) und oeffnet den Browser.
rem Erreichbar unter http://localhost:8000 (im Firmennetz: http://<Rechnername>:8000)
rem Auf dem SERVER laeuft das Tool seit v27 als Dienst bzw. Aufgabe (scripts\dienst-installieren.bat):
rem ist auf dieser Maschine der Dienst "FriondoAngebotstool" oder die Aufgabe "Friondo Angebotstool"
rem vorhanden, bricht dieses Skript mit Hinweis ab und oeffnet nur den Browser, falls Port 8000 antwortet.
rem PROXY_IPS in der .env (Reverse-Proxy) -> uvicorn --proxy-headers --forwarded-allow-ips.
setlocal
cd /d "%~dp0"

sc query FriondoAngebotstool >nul 2>&1 && goto :dienst_vorhanden
schtasks /Query /TN "Friondo Angebotstool" >nul 2>&1 && goto :dienst_vorhanden

if not exist "venv\Scripts\python.exe" (
    echo Fehler: venv nicht gefunden. Bitte zuerst einrichten:
    echo   python -m venv venv
    echo   venv\Scripts\pip install -r requirements.txt
    pause
    exit /b 1
)

rem Laeuft der Server bereits? Dann nur den Browser oeffnen.
powershell -NoProfile -Command "if (Get-NetTCPConnection -LocalPort 8000 -State Listen -ErrorAction SilentlyContinue) { exit 0 } else { exit 1 }"
if %errorlevel% equ 0 goto browser

rem Reverse-Proxy-Vorbereitung (v27): nur wenn PROXY_IPS in der .env gesetzt ist
set "PROXY_IPS="
if exist ".env" for /f "usebackq tokens=1,* delims==" %%A in (`findstr /b /i "PROXY_IPS=" ".env"`) do set "PROXY_IPS=%%B"
set "PROXY_ARGS="
if defined PROXY_IPS set "PROXY_IPS=%PROXY_IPS:"=%"
if defined PROXY_IPS set "PROXY_ARGS=--proxy-headers --forwarded-allow-ips %PROXY_IPS%"

start "Friondo Angebotstool Server" /min venv\Scripts\python.exe -m uvicorn app.main:app --host 0.0.0.0 --port 8000 %PROXY_ARGS%

rem Warten, bis der Server antwortet (max. 15 Sekunden)
powershell -NoProfile -Command "$ok=$false; for($i=0;$i -lt 30;$i++){ try { Invoke-WebRequest 'http://localhost:8000' -UseBasicParsing -TimeoutSec 1 | Out-Null; $ok=$true; break } catch { Start-Sleep -Milliseconds 500 } }; if(-not $ok){ exit 1 }"
if %errorlevel% neq 0 (
    echo Der Server konnte nicht gestartet werden.
    pause
    exit /b 1
)

:browser
start "" "http://localhost:8000"
exit /b 0

:dienst_vorhanden
echo Dienst vorhanden - bitte scripts\dienst-neustart.bat verwenden ^(Status: scripts\dienst-status.bat^).
echo start.bat ist nur fuer den Entwicklungs-PC bzw. einen Einzelplatz gedacht ^(docs\betrieb.md^).
powershell -NoProfile -Command "if (Get-NetTCPConnection -LocalPort 8000 -State Listen -ErrorAction SilentlyContinue) { exit 0 } else { exit 1 }"
if %errorlevel% equ 0 (
    echo Das Tool antwortet auf Port 8000 - der Browser wird geoeffnet.
    start "" "http://localhost:8000"
) else (
    echo Port 8000 antwortet nicht - Tool mit scripts\dienst-neustart.bat ^(als Administrator^) starten.
)
pause
exit /b 1
