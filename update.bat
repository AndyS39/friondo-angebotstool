@echo off
rem Friondo Angebotstool: Update auf dem Server einspielen (als Administrator).
rem Ablauf: Dienst stoppen -> git pull -> Abhaengigkeiten -> migrate.py -> Dienst starten
setlocal
cd /d "%~dp0"
echo == Friondo Angebotstool: Update ==

echo [1/5] Dienst stoppen ...
schtasks /End /TN "Friondo Angebotstool" >nul 2>&1
timeout /t 3 /nobreak >nul

echo [2/5] Neuen Stand holen (git pull) ...
git pull --ff-only || (echo FEHLER: git pull fehlgeschlagen & goto :ende)

echo [3/5] Abhaengigkeiten aktualisieren ...
venv\Scripts\pip install -q -r requirements.txt || (echo FEHLER: pip install fehlgeschlagen & goto :ende)

echo [4/5] Datenbank migrieren ...
venv\Scripts\python migrate.py || (echo FEHLER: Migration fehlgeschlagen & goto :ende)

:ende
echo [5/5] Dienst starten ...
schtasks /Run /TN "Friondo Angebotstool" >nul 2>&1
echo Fertig. Bitte http://localhost:8000 pruefen.
endlocal
