@echo off
rem Startet das Friondo Angebotstool (lokale Web-App) und oeffnet den Browser.
rem Erreichbar unter http://localhost:8000 (im Firmennetz: http://<Rechnername>:8000)

cd /d "%~dp0"

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

start "Friondo Angebotstool Server" /min venv\Scripts\python.exe -m uvicorn app.main:app --host 0.0.0.0 --port 8000

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
