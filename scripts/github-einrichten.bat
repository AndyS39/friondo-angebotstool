@echo off
rem Friondo Angebotstool: GitHub-Remote einmalig einrichten und ersten Push machen.
rem Voraussetzung: privates Repository auf github.com ist angelegt (leer, ohne README)
rem und Git for Windows mit Git Credential Manager ist installiert (Standard).
rem Beim ersten Push oeffnet sich ein Browserfenster zur GitHub-Anmeldung.
setlocal
cd /d "%~dp0.."
echo == Friondo Angebotstool: GitHub-Remote einrichten ==
echo.
git remote get-url origin >nul 2>&1 && (
    echo Es ist bereits ein Remote origin eingerichtet:
    git remote get-url origin
    echo Zum Aendern: git remote set-url origin NEUE-URL
    pause
    exit /b 0
)
set "URL=%~1"
if "%URL%"=="" set /p URL=Repository-URL (z. B. https://github.com/DEIN-KONTO/friondo-angebotstool.git):
if "%URL%"=="" (echo Abgebrochen - keine URL. & pause & exit /b 1)
git remote add origin "%URL%" || (echo FEHLER: Remote konnte nicht angelegt werden. & pause & exit /b 1)
git push -u origin master || (
    echo FEHLER: Push fehlgeschlagen - Anmeldung abgebrochen oder Repository nicht leer/nicht erreichbar.
    git remote remove origin
    pause
    exit /b 1
)
echo.
echo Fertig: origin = %URL%  (Branch master, Upstream gesetzt)
echo Naechste Updates: git push  (PC)  ->  update.bat  (Server)
pause
endlocal
