@echo off
rem Friondo Angebotstool: Dienst und Aufgaben wieder entfernen (v27, PLAN_V17 Phase 129) - als Administrator.
rem Entfernt beide Wege: Dienst "FriondoAngebotstool" (per nssm remove, sonst sc delete) und die
rem Aufgabe "Friondo Angebotstool", dazu die Waechter-Aufgabe, die Firewall-Regel und den
rem Wartungsmarker. Projektordner, Datenbank und Daten bleiben erhalten.
rem Aufruf im Projektordner:   scripts\dienst-entfernen.bat [--hilfe]
setlocal
set "PROJEKT=%~dp0.."
for %%I in ("%PROJEKT%") do set "PROJEKT=%%~fI"
set "DIENST=FriondoAngebotstool"
set "PS=powershell -NoProfile -ExecutionPolicy Bypass"
if /i "%~1"=="--hilfe" (
    echo scripts\dienst-entfernen.bat  - entfernt Dienst/Aufgabe, Waechter-Aufgabe und Firewall-Regel ^(Daten bleiben^).
    exit /b 0
)
net session >nul 2>&1 || (
    echo FEHLER: Bitte die Eingabeaufforderung "Als Administrator ausfuehren".
    exit /b 1
)
echo == Friondo Angebotstool: Dienst entfernen ==
echo Entfernt werden: Dienst %DIENST% bzw. Aufgabe "Friondo Angebotstool", Waechter-Aufgabe,
echo Firewall-Regel "Friondo Angebotstool". Projektordner und Daten bleiben erhalten.
set /p ANTWORT=Fortfahren? (j/n)
if /i not "%ANTWORT%"=="j" (
    echo Abgebrochen.
    exit /b 0
)

rem Wartungsmarker, damit der Waechter waehrend des Entfernens nichts neu startet
if not exist "%PROJEKT%\data\log" mkdir "%PROJEKT%\data\log"
echo %date% %time% dienst-entfernen.bat> "%PROJEKT%\data\log\wartung.marker"
set "NSSM="
if exist "%~dp0nssm.exe" set "NSSM=%~dp0nssm.exe"
if not defined NSSM if exist "%PROJEKT%\nssm.exe" set "NSSM=%PROJEKT%\nssm.exe"
if not defined NSSM if exist "C:\Friondo\nssm.exe" set "NSSM=C:\Friondo\nssm.exe"

sc query %DIENST% >nul 2>&1
if errorlevel 1 (
    echo Dienst %DIENST% nicht vorhanden.
) else (
    echo Dienst %DIENST% stoppen und entfernen ...
    net stop %DIENST% >nul 2>&1
    if defined NSSM (
        "%NSSM%" remove %DIENST% confirm >nul 2>&1 || sc delete %DIENST% >nul
    ) else (
        sc delete %DIENST% >nul
    )
)
%PS% -File "%~dp0waechter.ps1" -Entfernen
netsh advfirewall firewall delete rule name="Friondo Angebotstool" >nul 2>&1
if exist "%PROJEKT%\data\log\wartung.marker" del /q "%PROJEKT%\data\log\wartung.marker"
%PS% -Command "if (Get-NetTCPConnection -LocalPort 8000 -State Listen -ErrorAction SilentlyContinue) { Write-Host 'Hinweis: Port 8000 ist noch belegt (Konsolenfenster aus start.bat?).' }"
echo.
echo Fertig. Dienst/Aufgaben und Firewall-Regel entfernt - Projektordner und Daten bleiben erhalten.
echo Neu einrichten: scripts\dienst-installieren.bat
endlocal
exit /b 0
