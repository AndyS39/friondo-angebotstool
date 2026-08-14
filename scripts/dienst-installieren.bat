@echo off
rem Friondo Angebotstool: Einrichtung als Autostart-Dienst (Aufgabenplanung).
rem Als Administrator im Projektordner auf dem Terminal Server ausfuehren.
rem Details: docs\installation-terminal-server.md

setlocal
set "PROJEKT=%~dp0.."
for %%I in ("%PROJEKT%") do set "PROJEKT=%%~fI"
echo Projektordner: %PROJEKT%

rem 1) venv anlegen, falls noch nicht vorhanden
if not exist "%PROJEKT%\venv\Scripts\python.exe" (
    echo Erstelle virtuelle Umgebung ...
    python -m venv "%PROJEKT%\venv" || exit /b 1
)

rem 2) Abhaengigkeiten installieren/aktualisieren
"%PROJEKT%\venv\Scripts\pip" install -r "%PROJEKT%\requirements.txt" || exit /b 1

rem 3) .env anlegen, falls noch nicht vorhanden
if not exist "%PROJEKT%\.env" (
    if exist "%PROJEKT%\.env.example" copy "%PROJEKT%\.env.example" "%PROJEKT%\.env"
)

rem 4) Geplante Aufgabe mit Autostart anlegen (laeuft als SYSTEM, Start bei Boot)
schtasks /Create /F /TN "Friondo Angebotstool" /SC ONSTART /RU SYSTEM ^
  /TR "\"%PROJEKT%\venv\Scripts\python.exe\" -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --app-dir \"%PROJEKT%\"" || exit /b 1

rem 5) Firewall-Freigabe Port 8000 (nur falls noch nicht vorhanden)
netsh advfirewall firewall show rule name="Friondo Angebotstool" >nul 2>&1
if errorlevel 1 (
    netsh advfirewall firewall add rule name="Friondo Angebotstool" dir=in action=allow protocol=TCP localport=8000
)

rem 6) Sofort starten (sonst erst beim naechsten Server-Neustart)
schtasks /Run /TN "Friondo Angebotstool"

echo.
echo Fertig. Pruefen: http://localhost:8000 im Browser oeffnen.
echo Erststart-Anmeldung Admin / PIN 1234 - danach sofort PIN aendern.
endlocal
