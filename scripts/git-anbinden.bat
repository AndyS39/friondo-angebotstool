@echo off
rem Bindet diese Dateikopie des Friondo-Tools an das GitHub-Repository an,
rem OHNE Dateien zu ueberschreiben (Gegenstueck zu scripts\github-einrichten.bat).
rem Ablauf: git init -> origin setzen -> fetch -> HEAD auf origin/master setzen
rem (Arbeitsdateien bleiben, wie sie sind) -> Unterschiede anzeigen.
rem Voraussetzung: Git for Windows (Installation "Only for me" reicht, kein Admin).
setlocal
cd /d "%~dp0.."
set REMOTE=https://github.com/AndyS39/friondo-angebotstool.git

rem Git suchen: im PATH, in der Benutzer-Installation oder als PortableGit
where git >nul 2>&1
if errorlevel 1 (
    if exist "%LOCALAPPDATA%\Programs\Git\cmd\git.exe" (
        set "PATH=%LOCALAPPDATA%\Programs\Git\cmd;%PATH%"
    ) else if exist "%USERPROFILE%\Tools\PortableGit\cmd\git.exe" (
        set "PATH=%USERPROFILE%\Tools\PortableGit\cmd;%PATH%"
    ) else if exist "%ProgramFiles%\Git\cmd\git.exe" (
        set "PATH=%ProgramFiles%\Git\cmd;%PATH%"
    )
)
where git >nul 2>&1 || (
    echo FEHLER: git wurde nicht gefunden.
    echo   Git for Windows installieren ^(git-scm.com, beim Start "Install for me only"^)
    echo   oder PortableGit nach %USERPROFILE%\Tools\PortableGit entpacken,
    echo   dann dieses Skript in einem NEUEN Fenster erneut starten.
    pause
    exit /b 1
)
echo Git: & git --version
echo Ordner: %CD%
echo.

if exist ".git" (
    echo Hinweis: In diesem Ordner gibt es bereits ein .git - nichts zu tun.
    echo Aktueller Stand:
    git status --short
    pause
    exit /b 0
)

echo [1/6] Repository initialisieren ...
git init -b master || goto :fehler
git config user.name "Andreas Scheelen"
git config user.email "a.scheelen@friondo.de"

echo [2/6] Remote setzen: %REMOTE%
git remote add origin %REMOTE% || goto :fehler

echo [3/6] Stand von GitHub holen ...
echo        Beim ersten Mal oeffnet sich ein Browserfenster zur GitHub-Anmeldung.
git fetch origin master || goto :fehler

echo [4/6] HEAD auf origin/master setzen - die Arbeitsdateien bleiben unveraendert ...
git reset --mixed origin/master || goto :fehler
git branch --set-upstream-to=origin/master master || goto :fehler

echo [5/6] Letzter Stand auf GitHub:
git log -1 --date=short --format="   %%h  %%ad  %%s"

echo [6/6] Unterschiede zwischen dieser Kopie und GitHub:
echo        M  = Datei weicht vom GitHub-Stand ab
echo        ?? = Datei gibt es nur hier ^(z. B. PLAN_V15.md, docs\wirtschaftlichkeit-mockup^)
echo        D  = Datei fehlt hier, gibt es aber auf GitHub
git status --short
echo.
echo Fertig. Es wurde nichts ueberschrieben und nichts committet.
echo Naechster Schritt: Unterschiede mit Claude Code durchgehen, dann committen.
pause
exit /b 0

:fehler
echo.
echo FEHLER - siehe Meldung oben. An den Arbeitsdateien wurde nichts geaendert.
echo Falls .git angelegt wurde, kann der Ordner .git gefahrlos geloescht und das
echo Skript erneut gestartet werden.
pause
exit /b 1
