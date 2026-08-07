@echo off
rem Startet das Friondo Angebotstool (lokale Web-App).
rem Erreichbar im Browser unter http://localhost:8000
rem (im Firmennetz auch über http://<Rechnername>:8000)

cd /d "%~dp0"

if not exist "venv\Scripts\python.exe" (
    echo Fehler: venv nicht gefunden. Bitte zuerst einrichten:
    echo   python -m venv venv
    echo   venv\Scripts\pip install -r requirements.txt
    pause
    exit /b 1
)

echo Friondo Angebotstool startet ... http://localhost:8000
venv\Scripts\python.exe -m uvicorn app.main:app --host 0.0.0.0 --port 8000
pause
