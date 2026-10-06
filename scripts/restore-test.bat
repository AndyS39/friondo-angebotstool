@echo off
rem Friondo Angebotstool: Restore-Test (v27, PLAN_V17 Phase 129) - monatlich durch Andreas/IT (Runbook).
rem Aufruf im Projektordner (kein Administrator noetig, das laufende Tool bleibt unberuehrt):
rem   scripts\restore-test.bat [Sicherungsdatei]        Standard: juengste data\backups\angebotstool-*.db
rem Ablauf:
rem   1) Sicherung nach diagnose\restore_<Datum>\data\angebotstool.db kopieren (Kopie, nie die Live-DB)
rem   2) migrate.py --db auf der Kopie (zweimal: Migration + Idempotenz; DATA_ORDNER zeigt auf die Kopie)
rem   3) scripts\voll_crawl.py --data diagnose\restore_<Datum>\data --max-ids 20 --rollen admin,innendienst
rem   4) Protokoll docs\betrieb\restore-<Datum>.txt: Zeit, Quelle, Migrationsausgabe, Crawl-Zusammenfassung
rem      (keine Kundendaten - der vollstaendige Crawl-Bericht bleibt unter diagnose\restore_<Datum>\)
rem Exit-Code 0 = Sicherung lesbar, Migration ok, Crawl ohne Absturz; 1 = Fehler; 2 = Bedienfehler.
rem Alte Ordner diagnose\restore_* koennen nach dem Test geloescht werden (gitignored).
setlocal
set "PROJEKT=%~dp0.."
for %%I in ("%PROJEKT%") do set "PROJEKT=%%~fI"
cd /d "%PROJEKT%"
if /i "%~1"=="--hilfe" goto :hilfe
if not exist "venv\Scripts\python.exe" (
    echo FEHLER: venv\Scripts\python.exe nicht gefunden.
    exit /b 2
)
for /f %%i in ('powershell -NoProfile -Command "Get-Date -Format yyyy-MM-dd_HHmm"') do set "STEMPEL=%%i"

set "QUELLE=%~1"
if "%QUELLE%"=="" (
    for /f "delims=" %%f in ('dir /b /o-n "data\backups\angebotstool-*.db" 2^>nul') do (
        if not defined QUELLE set "QUELLE=data\backups\%%f"
    )
)
if "%QUELLE%"=="" (
    echo FEHLER: Keine Sicherung data\backups\angebotstool-*.db gefunden.
    exit /b 2
)
if not exist "%QUELLE%" (
    echo FEHLER: %QUELLE% nicht gefunden.
    exit /b 2
)
set "ZIEL=diagnose\restore_%STEMPEL%"
set "PROTOKOLL=docs\betrieb\restore-%STEMPEL%.txt"
if not exist "%ZIEL%\data" mkdir "%ZIEL%\data"
if not exist "docs\betrieb" mkdir "docs\betrieb"
set "PYTHONIOENCODING=utf-8"
set "ERGEBNIS=OK"

echo == Friondo Angebotstool: Restore-Test %STEMPEL% ==
echo Quelle: %QUELLE%
echo Ziel:   %ZIEL%\data\angebotstool.db
> "%PROTOKOLL%" echo Restore-Test Friondo Angebotstool - %STEMPEL%
>> "%PROTOKOLL%" echo Projektordner: %PROJEKT%
>> "%PROTOKOLL%" echo Quelle: %QUELLE%
for %%F in ("%QUELLE%") do >> "%PROTOKOLL%" echo Quelle Groesse/Datum: %%~zF Byte, %%~tF
>> "%PROTOKOLL%" echo Kopie: %ZIEL%\data\angebotstool.db
>> "%PROTOKOLL%" echo.

echo [1/3] Sicherung kopieren ...
copy /y "%QUELLE%" "%ZIEL%\data\angebotstool.db" >nul || (
    echo FEHLER: Kopieren fehlgeschlagen.
    >> "%PROTOKOLL%" echo ERGEBNIS: FEHLER - Kopieren der Sicherung fehlgeschlagen
    exit /b 1
)

echo [2/3] Migration auf der Kopie ^(migrate.py --db, zweimal^) ...
set "DATA_ORDNER=%PROJEKT%\%ZIEL%\data"
>> "%PROTOKOLL%" echo --- Migration, 1. Lauf ---
venv\Scripts\python.exe migrate.py --db "%ZIEL%\data\angebotstool.db" >> "%PROTOKOLL%" 2>&1
if errorlevel 1 (
    set "ERGEBNIS=FEHLER - Migration"
    >> "%PROTOKOLL%" echo Migration 1. Lauf: FEHLER ^(Exit-Code %errorlevel%^)
    goto :protokoll_ende
)
>> "%PROTOKOLL%" echo --- Migration, 2. Lauf ^(Idempotenz^) ---
venv\Scripts\python.exe migrate.py --db "%ZIEL%\data\angebotstool.db" >> "%PROTOKOLL%" 2>&1
if errorlevel 1 (
    set "ERGEBNIS=FEHLER - Migration 2. Lauf"
    goto :protokoll_ende
)
set "DATA_ORDNER="

echo [3/3] Voll-Crawl gegen die Kopie ^(admin, innendienst, --max-ids 20 - einige Minuten^) ...
venv\Scripts\python.exe scripts\voll_crawl.py --data "%ZIEL%\data" --max-ids 20 --rollen admin,innendienst --bericht "%ZIEL%\crawl_bericht.txt" > "%ZIEL%\crawl_ausgabe.txt" 2>&1
set "CRAWL_RC=%errorlevel%"
>> "%PROTOKOLL%" echo.
>> "%PROTOKOLL%" echo --- Voll-Crawl ^(Exit-Code %CRAWL_RC%; 0 = keine Abstuerze^) ---
if exist "%ZIEL%\crawl_bericht.txt" (
    rem Kopf, Zusammenfassung und Statusverteilung bis zur Zeile "ABSTUERZE (n)" - keine Tracebacks/Kundendaten.
    rem PowerShell haengt selbst als UTF-8 an (ueber cmd ">>" kaeme die OEM-Codepage ins Protokoll).
    powershell -NoProfile -Command "$z = Get-Content -LiteralPath '%ZIEL%\crawl_bericht.txt' -Encoding UTF8; $n = 0; foreach ($l in $z) { $n++; if ($l -match '^ABST') { break } }; [System.IO.File]::AppendAllText('%PROJEKT%\%PROTOKOLL%', (($z[0..($n-1)]) -join [Environment]::NewLine) + [Environment]::NewLine, (New-Object System.Text.UTF8Encoding($false)))"
) else (
    >> "%PROTOKOLL%" echo Kein Crawl-Bericht erzeugt - letzte Zeilen der Ausgabe:
    powershell -NoProfile -Command "$z = Get-Content -LiteralPath '%ZIEL%\crawl_ausgabe.txt' -Encoding UTF8 -Tail 15; [System.IO.File]::AppendAllText('%PROJEKT%\%PROTOKOLL%', ($z -join [Environment]::NewLine) + [Environment]::NewLine, (New-Object System.Text.UTF8Encoding($false)))"
)
if not "%CRAWL_RC%"=="0" set "ERGEBNIS=FEHLER - Crawl mit Exit-Code %CRAWL_RC%, Bericht %ZIEL%\crawl_bericht.txt"

:protokoll_ende
>> "%PROTOKOLL%" echo.
>> "%PROTOKOLL%" echo Vollstaendiger Crawl-Bericht ^(mit Tracebacks^): %ZIEL%\crawl_bericht.txt
for /f %%i in ('powershell -NoProfile -Command "Get-Date -Format yyyy-MM-dd_HHmm"') do set "ENDE=%%i"
>> "%PROTOKOLL%" echo Ende: %ENDE%
>> "%PROTOKOLL%" echo ERGEBNIS: %ERGEBNIS%
echo.
echo ERGEBNIS: %ERGEBNIS%
echo Protokoll: %PROTOKOLL%
echo Kopie und Crawl-Bericht: %ZIEL%\
if not defined FRIONDO_OHNE_PAUSE pause
if "%ERGEBNIS%"=="OK" exit /b 0
exit /b 1

:hilfe
echo scripts\restore-test.bat [Sicherungsdatei]
echo   Spielt die juengste Sicherung ^(data\backups\angebotstool-*.db^) als Kopie nach diagnose\restore_^<Datum^>\
echo   ein, migriert sie, laesst den Voll-Crawl ^(admin, innendienst, 20 IDs je Tabelle^) darueber laufen
echo   und schreibt das Protokoll nach docs\betrieb\restore-^<Datum^>.txt. Monatlich ^(docs\betrieb.md^).
exit /b 0
