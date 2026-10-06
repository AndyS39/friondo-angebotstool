# Friondo Angebotstool – Wächter (v27, PLAN_V17 Phase 129)
#
# Läuft auf dem Server als Aufgabe „Friondo Angebotstool Wächter“ alle 5 Minuten (Konto
# SYSTEM; angelegt von scripts\dienst-installieren.bat über -WaechterAnlegen):
#   1. http://127.0.0.1:8000/health abfragen (Timeout 10 s).
#   2. Keine Antwort oder HTTP 503 → Dienst „FriondoAngebotstool“ (NSSM) bzw. Aufgabe
#      „Friondo Angebotstool“ neu starten – der Weg wird selbst erkannt (Get-Service /
#      Get-ScheduledTask). Zeile in data\log\waechter.log (Zeit | Befund | Maßnahme).
#      Zwischen zwei Neustarts liegen mindestens 15 Minuten (-NeustartAbstand), damit ein
#      dauerhafter Fehler (z. B. Datenbank defekt) nicht alle 5 Minuten neu startet.
#   3. „warn“ → nur Log-Zeile (höchstens eine je Stunde bei gleichem Grund); „ok“ → eine
#      Herzschlag-Zeile je Tag. HTTP 404 = Tool antwortet ohne /health (Fassung vor v27,
#      z. B. nach rollback.bat) → kein Neustart.
#   4. Wartungsmarker data\log\wartung.marker (von dienst-neustart.bat --stop, update.bat,
#      rollback.bat gesetzt): solange er liegt, greift der Wächter NICHT ein (nur Log-Zeile).
#   5. Aufgaben-Variante: dienst-out.log / dienst-err.log > 10 MB → Umbenennen in .1 … .5
#      (höchstens 5). Laufende Ausgabedateien lassen sich nicht umbenennen, deshalb beim
#      Neustart – und falls nötig nachts zwischen 04:00 und 04:59 durch einen kurzen,
#      protokollierten Neustart. (NSSM rotiert selbst: AppRotateOnline.)
#
# Schalter (für die .bat-Skripte; alle PowerShell-5.1-tauglich):
#   -AufgabeAnlegen [-ProxyArgs "…"]  Aufgabe „Friondo Angebotstool“ (Start beim Hochfahren, SYSTEM,
#                                     Arbeitsordner = Projektordner, kein Zeitlimit, Ausgabe nach
#                                     data\log\dienst-out.log) anlegen/aktualisieren
#   -WaechterAnlegen                  Wächter-Aufgabe alle 5 Minuten anlegen/aktualisieren
#   -Entfernen                        beide Aufgaben entfernen
#   -Status                           Dienst/Aufgaben/Port/Marker/letzte Log-Zeilen anzeigen
#   -Rotieren                         nur die Log-Rotation versuchen
#   -Neustart                         Neustart erzwingen (wie bei Ausfall)
#   -WhatIf                           zeigt Neustart/Anlegen/Entfernen nur an
#   Von Hand (als Administrator):  powershell -NoProfile -ExecutionPolicy Bypass -File scripts\waechter.ps1 -Status
#
# Exit-Code: 0 = nichts zu tun / Maßnahme erfolgreich, 1 = Maßnahme fehlgeschlagen oder
# Tool trotz Neustart nicht erreichbar, 2 = Bedienfehler.
[CmdletBinding(SupportsShouldProcess = $true)]
param(
    [string]$Adresse = "http://127.0.0.1:8000/health",
    [string]$Projekt = "",
    [int]$Timeout = 10,
    [int]$NeustartAbstand = 15,
    [string]$ProxyArgs = "",
    [switch]$AufgabeAnlegen,
    [switch]$WaechterAnlegen,
    [switch]$Entfernen,
    [switch]$Status,
    [switch]$Rotieren,
    [switch]$Neustart
)

$ErrorActionPreference = "Continue"
$DIENST = "FriondoAngebotstool"
$AUFGABE = "Friondo Angebotstool"
$WAECHTER = "Friondo Angebotstool Wächter"
$ROTATION_BYTES = 10000000
$ROTATION_MAX = 5
$ROTATION_STUNDE = 4          # nächtlicher Rotations-Neustart (Aufgaben-Variante) 04:00–04:59
$HEARTBEAT_TEXT = "ok (Herzschlag, eine Zeile je Tag)"
$script:Utf8Log = New-Object System.Text.UTF8Encoding($true)   # BOM nur beim Anlegen der Datei (AppendAllText), damit Notepad/Get-Content die Umlaute erkennen

if (-not $Projekt) { $Projekt = Split-Path -Parent $PSScriptRoot }
$Projekt = [System.IO.Path]::GetFullPath($Projekt)
$LogOrdner = Join-Path $Projekt "data\log"
$LogDatei = Join-Path $LogOrdner "waechter.log"
$Marker = Join-Path $LogOrdner "wartung.marker"
$NeustartMarker = Join-Path $LogOrdner "waechter-neustart.marker"


# --- Hilfsfunktionen ------------------------------------------------------------------

function Protokoll([string]$Befund, [string]$Massnahme) {
    if ($WhatIfPreference) { Write-Host "WhatIf: Log-Zeile '$Befund | $Massnahme'"; return }
    try {
        if (-not (Test-Path -LiteralPath $LogOrdner)) { New-Item -ItemType Directory -Path $LogOrdner -Force | Out-Null }
        if ((Test-Path -LiteralPath $LogDatei) -and ((Get-Item -LiteralPath $LogDatei).Length -gt 2MB)) {
            Move-Item -LiteralPath $LogDatei -Destination ($LogDatei + ".1") -Force -ErrorAction SilentlyContinue
        }
        $zeile = "{0} | {1} | {2}" -f (Get-Date).ToString("yyyy-MM-dd HH:mm:ss"), $Befund, $Massnahme
        [System.IO.File]::AppendAllText($LogDatei, $zeile + "`r`n", $script:Utf8Log)
    } catch {}
}


function Letzte-Zeilen([int]$Anzahl) {
    if (-not (Test-Path -LiteralPath $LogDatei)) { return @() }
    try { return @(Get-Content -LiteralPath $LogDatei -Encoding UTF8 -Tail $Anzahl) } catch { return @() }
}


function Health {
    # Liefert @{ Erreichbar; Http; Status; Gruende; Text }
    $ergebnis = @{ Erreichbar = $false; Http = 0; Status = ""; Gruende = @(); Text = "" }
    $antwort = $null
    try {
        $anfrage = [System.Net.HttpWebRequest]::Create($Adresse)
        $anfrage.Timeout = $Timeout * 1000
        $anfrage.ReadWriteTimeout = $Timeout * 1000
        $anfrage.Proxy = $null
        $anfrage.UserAgent = "friondo-waechter/v27"
        $antwort = $anfrage.GetResponse()
    } catch [System.Net.WebException] {
        if ($_.Exception.Response -ne $null) { $antwort = $_.Exception.Response }
        else { $ergebnis.Text = "keine Antwort: " + $_.Exception.Message; return $ergebnis }
    } catch {
        $ergebnis.Text = "keine Antwort: " + $_.Exception.Message; return $ergebnis
    }
    $rumpf = ""
    try {
        $ergebnis.Http = [int]$antwort.StatusCode
        $ergebnis.Erreichbar = $true
        $leser = New-Object System.IO.StreamReader($antwort.GetResponseStream(), [System.Text.Encoding]::UTF8)
        $rumpf = $leser.ReadToEnd()
        $leser.Close()
    } catch {} finally { try { $antwort.Close() } catch {} }
    if ($ergebnis.Http -eq 404) { $ergebnis.Status = "kein /health"; $ergebnis.Text = "HTTP 404 – Fassung ohne /health"; return $ergebnis }
    try {
        $json = $rumpf | ConvertFrom-Json
        $ergebnis.Status = [string]$json.status
        if ($json.gruende -ne $null) { $ergebnis.Gruende = @($json.gruende) }
        $ergebnis.Text = "$($ergebnis.Status) v$($json.version) $($json.commit) db $($json.db_ms) ms"
    } catch { $ergebnis.Status = "unlesbar"; $ergebnis.Text = "HTTP $($ergebnis.Http), Antwort kein JSON" }
    return $ergebnis
}


function Weg-Erkennen {
    if (Get-Service -Name $DIENST -ErrorAction SilentlyContinue) { return "dienst" }
    if (Get-ScheduledTask -TaskName $AUFGABE -ErrorAction SilentlyContinue) { return "aufgabe" }
    return "keiner"
}


function Port-Prozesse {
    try {
        return @(Get-NetTCPConnection -LocalPort 8000 -State Listen -ErrorAction SilentlyContinue |
                 Select-Object -ExpandProperty OwningProcess -Unique)
    } catch { return @() }
}


function Port-Freimachen([int]$Sekunden) {
    # wartet, bis Port 8000 frei ist; danach verbliebene Prozesse beenden (Waisen nach schtasks /End)
    $ende = (Get-Date).AddSeconds($Sekunden)
    while ((Get-Date) -lt $ende) {
        if ((Port-Prozesse).Count -eq 0) { return $true }
        Start-Sleep -Milliseconds 500
    }
    foreach ($pid_ in (Port-Prozesse)) {
        if ($pid_ -gt 0 -and $PSCmdlet.ShouldProcess("PID $pid_ (Port 8000)", "Prozess beenden")) {
            try { Stop-Process -Id $pid_ -Force -ErrorAction Stop } catch {}
        }
    }
    Start-Sleep -Seconds 1
    return ((Port-Prozesse).Count -eq 0)
}


function Logs-Rotieren {
    # dienst-out.log / dienst-err.log > 10 MB → .1 … .5; liefert Liste der Meldungen
    $meldungen = @()
    foreach ($name in @("dienst-out.log", "dienst-err.log")) {
        $datei = Join-Path $LogOrdner $name
        if (-not (Test-Path -LiteralPath $datei)) { continue }
        $groesse = (Get-Item -LiteralPath $datei).Length
        if ($groesse -le $ROTATION_BYTES) { continue }
        try {
            $letzte = "$datei.$ROTATION_MAX"
            if (Test-Path -LiteralPath $letzte) { Remove-Item -LiteralPath $letzte -Force -ErrorAction Stop }
            for ($i = $ROTATION_MAX - 1; $i -ge 1; $i--) {
                $von = "$datei.$i"
                if (Test-Path -LiteralPath $von) { Move-Item -LiteralPath $von -Destination ("$datei." + ($i + 1)) -Force -ErrorAction Stop }
            }
            Move-Item -LiteralPath $datei -Destination "$datei.1" -Force -ErrorAction Stop
            $meldungen += "$name rotiert ($([math]::Round($groesse / 1MB, 1)) MB → .1)"
        } catch {
            $meldungen += "$name $([math]::Round($groesse / 1MB, 1)) MB – Rotation erst nach Neustart möglich (Datei in Benutzung)"
        }
    }
    return $meldungen
}


function Logs-Zu-Gross {
    foreach ($name in @("dienst-out.log", "dienst-err.log")) {
        $datei = Join-Path $LogOrdner $name
        if ((Test-Path -LiteralPath $datei) -and ((Get-Item -LiteralPath $datei).Length -gt $ROTATION_BYTES)) { return $true }
    }
    return $false
}


function Auf-Health-Warten([int]$Sekunden) {
    $ende = (Get-Date).AddSeconds($Sekunden)
    do {
        $h = Health
        if ($h.Erreichbar -and $h.Http -ne 503) { return $h }
        Start-Sleep -Seconds 1
    } while ((Get-Date) -lt $ende)
    return $h
}


function Tool-Neustarten([string]$Weg, [string]$Grund) {
    # liefert $true, wenn /health nach dem Neustart antwortet (nicht 503)
    switch ($Weg) {
        "dienst" {
            if (-not $PSCmdlet.ShouldProcess("Dienst $DIENST", "neu starten")) { return $true }
            try {
                Restart-Service -Name $DIENST -Force -ErrorAction Stop
            } catch {
                try { Stop-Service -Name $DIENST -Force -ErrorAction SilentlyContinue } catch {}
                Port-Freimachen 10 | Out-Null
                try { Start-Service -Name $DIENST -ErrorAction Stop } catch {
                    Protokoll $Grund "Dienst-Neustart FEHLGESCHLAGEN: $($_.Exception.Message)"
                    return $false
                }
            }
        }
        "aufgabe" {
            if (-not $PSCmdlet.ShouldProcess("Aufgabe $AUFGABE", "beenden, Logs rotieren, starten")) { return $true }
            & schtasks.exe /End /TN $AUFGABE 2>$null | Out-Null
            Port-Freimachen 10 | Out-Null
            foreach ($m in (Logs-Rotieren)) { Protokoll "Rotation" $m }
            & schtasks.exe /Run /TN $AUFGABE 2>$null | Out-Null
            if ($LASTEXITCODE -ne 0) { Protokoll $Grund "schtasks /Run FEHLGESCHLAGEN (Exit $LASTEXITCODE)"; return $false }
        }
        default {
            Protokoll $Grund "kein Dienst und keine Aufgabe gefunden (Konsolenfenster aus start.bat?) – keine Maßnahme möglich; bitte scripts\dienst-installieren.bat"
            return $false
        }
    }
    try { [System.IO.File]::WriteAllText($NeustartMarker, (Get-Date).ToString("yyyy-MM-dd HH:mm:ss"), $script:Utf8Log) } catch {}
    $h = Auf-Health-Warten 30
    if ($h.Erreichbar -and $h.Http -ne 503) {
        Protokoll $Grund "Neustart ($Weg) ausgeführt – /health danach: $($h.Text)"
        return $true
    }
    Protokoll $Grund "Neustart ($Weg) ausgeführt – /health antwortet NICHT (HTTP $($h.Http)) $($h.Text)"
    return $false
}


function Neustart-Erlaubt {
    if (-not (Test-Path -LiteralPath $NeustartMarker)) { return $true }
    $alter = (Get-Date) - (Get-Item -LiteralPath $NeustartMarker).LastWriteTime
    return ($alter.TotalMinutes -ge $NeustartAbstand)
}


# --- Verwaltungs-Schalter --------------------------------------------------------------

function Aufgabe-Anlegen {
    $proxy = ""
    if ($ProxyArgs) { $proxy = " " + $ProxyArgs.Trim() }
    $argument = "/c set PYTHONIOENCODING=utf-8&& venv\Scripts\python.exe -m uvicorn app.main:app --host 0.0.0.0 --port 8000" + $proxy + " >> data\log\dienst-out.log 2>&1"
    if (-not $PSCmdlet.ShouldProcess("Aufgabe $AUFGABE", "anlegen/aktualisieren")) { return $true }
    try {
        $aktion = New-ScheduledTaskAction -Execute "cmd.exe" -Argument $argument -WorkingDirectory $Projekt
        $trigger = New-ScheduledTaskTrigger -AtStartup
        $principal = New-ScheduledTaskPrincipal -UserId "SYSTEM" -LogonType ServiceAccount -RunLevel Highest
        # ExecutionTimeLimit 0 = KEIN Zeitlimit (Standard der Aufgabenplanung wären 3 Tage – danach
        # würde das Tool beendet); RestartCount: bei Absturz (Exit ≠ 0) nach 1 Minute neu starten
        $einstellungen = New-ScheduledTaskSettingsSet -ExecutionTimeLimit ([TimeSpan]::Zero) `
            -MultipleInstances IgnoreNew -StartWhenAvailable -RestartCount 5 -RestartInterval (New-TimeSpan -Minutes 1) `
            -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries
        Register-ScheduledTask -TaskName $AUFGABE -Action $aktion -Trigger $trigger -Principal $principal `
            -Settings $einstellungen -Force -ErrorAction Stop `
            -Description "Friondo Angebotstool (uvicorn, Port 8000) – Projektordner $Projekt. Verwaltung: scripts\dienst-*.bat" | Out-Null
        Write-Host "Aufgabe '$AUFGABE' angelegt (Start beim Hochfahren, SYSTEM, ohne Zeitlimit, Arbeitsordner $Projekt)."
        return $true
    } catch {
        Write-Host "Register-ScheduledTask fehlgeschlagen ($($_.Exception.Message)) – Ersatz über schtasks.exe."
        $tr = 'cmd.exe /c "cd /d "' + $Projekt + '" && ' + $argument.Substring(3) + '"'
        & schtasks.exe /Create /F /TN $AUFGABE /SC ONSTART /RU SYSTEM /RL HIGHEST /TR $tr | Out-Null
        if ($LASTEXITCODE -eq 0) {
            Write-Host "Aufgabe '$AUFGABE' über schtasks angelegt. HINWEIS: in der Aufgabenplanung unter Einstellungen"
            Write-Host "'Aufgabe beenden, falls sie länger ausgeführt wird als' (3 Tage) abschalten!"
            return $true
        }
        Write-Host "FEHLER: Aufgabe konnte nicht angelegt werden (schtasks Exit $LASTEXITCODE)."
        return $false
    }
}


function Waechter-Anlegen {
    if (-not $PSCmdlet.ShouldProcess("Aufgabe $WAECHTER", "anlegen/aktualisieren")) { return $true }
    $argument = '-NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File "' + $PSCommandPath + '"'
    try {
        $aktion = New-ScheduledTaskAction -Execute "powershell.exe" -Argument $argument -WorkingDirectory $Projekt
        $trigger = New-ScheduledTaskTrigger -Once -At (Get-Date).Date -RepetitionInterval (New-TimeSpan -Minutes 5)
        $principal = New-ScheduledTaskPrincipal -UserId "SYSTEM" -LogonType ServiceAccount -RunLevel Highest
        $einstellungen = New-ScheduledTaskSettingsSet -ExecutionTimeLimit (New-TimeSpan -Minutes 4) `
            -MultipleInstances IgnoreNew -StartWhenAvailable -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries
        Register-ScheduledTask -TaskName $WAECHTER -Action $aktion -Trigger $trigger -Principal $principal `
            -Settings $einstellungen -Force -ErrorAction Stop `
            -Description "Prüft alle 5 Minuten /health des Friondo Angebotstools und startet Dienst/Aufgabe bei Ausfall neu (data\log\waechter.log)." | Out-Null
        Write-Host "Aufgabe '$WAECHTER' angelegt (alle 5 Minuten, SYSTEM; Log data\log\waechter.log)."
        return $true
    } catch {
        Write-Host "Register-ScheduledTask fehlgeschlagen ($($_.Exception.Message)) – Ersatz über schtasks.exe."
        & schtasks.exe /Create /F /TN $WAECHTER /SC MINUTE /MO 5 /RU SYSTEM /RL HIGHEST /TR ("powershell.exe " + $argument) | Out-Null
        if ($LASTEXITCODE -eq 0) { Write-Host "Aufgabe '$WAECHTER' über schtasks angelegt."; return $true }
        Write-Host "FEHLER: Wächter-Aufgabe konnte nicht angelegt werden (schtasks Exit $LASTEXITCODE)."
        return $false
    }
}


function Aufgaben-Entfernen {
    $ok = $true
    foreach ($name in @($AUFGABE, $WAECHTER)) {
        $aufgabe = Get-ScheduledTask -TaskName $name -ErrorAction SilentlyContinue
        if (-not $aufgabe) { Write-Host "Aufgabe '$name' nicht vorhanden."; continue }
        if (-not $PSCmdlet.ShouldProcess("Aufgabe $name", "beenden und entfernen")) { continue }
        try {
            & schtasks.exe /End /TN $name 2>$null | Out-Null
            Unregister-ScheduledTask -TaskName $name -Confirm:$false -ErrorAction Stop
            Write-Host "Aufgabe '$name' entfernt."
        } catch { Write-Host "FEHLER beim Entfernen von '$name': $($_.Exception.Message)"; $ok = $false }
    }
    if ($ok -and $PSCmdlet.ShouldProcess("Port 8000", "verbliebene Prozesse beenden")) { Port-Freimachen 5 | Out-Null }
    return $ok
}


function Status-Anzeigen {
    $weg = Weg-Erkennen
    Write-Host "Projektordner : $Projekt"
    Write-Host ("Weg           : " + $(switch ($weg) { "dienst" { "A – Windows-Dienst $DIENST (NSSM)" } "aufgabe" { "B – Aufgabenplanung '$AUFGABE'" } default { "KEINER (weder Dienst noch Aufgabe – Konsolenfenster aus start.bat?)" } }))
    $dienst = Get-Service -Name $DIENST -ErrorAction SilentlyContinue
    if ($dienst) {
        $start = ""
        try { $start = (Get-CimInstance Win32_Service -Filter "Name='$DIENST'" -ErrorAction Stop | Select-Object -First 1).StartMode } catch {}
        Write-Host "Dienst        : $($dienst.Status)  (Starttyp $start, Konto $((Get-CimInstance Win32_Service -Filter "Name='$DIENST'" -ErrorAction SilentlyContinue).StartName))"
    }
    foreach ($name in @($AUFGABE, $WAECHTER)) {
        $aufgabe = Get-ScheduledTask -TaskName $name -ErrorAction SilentlyContinue
        if (-not $aufgabe) { Write-Host ("Aufgabe       : '{0}' nicht vorhanden" -f $name); continue }
        $info = Get-ScheduledTaskInfo -TaskName $name -ErrorAction SilentlyContinue
        $letzter = ""; $naechster = ""; $ergebnis = ""
        if ($info) { $letzter = $info.LastRunTime; $naechster = $info.NextRunTime; $ergebnis = $info.LastTaskResult }
        Write-Host ("Aufgabe       : '{0}' – {1}; letzter Lauf {2} (Ergebnis {3}); nächster {4}" -f $name, $aufgabe.State, $letzter, $ergebnis, $naechster)
    }
    $pids = Port-Prozesse
    if ($pids.Count -gt 0) {
        $namen = @()
        foreach ($p in $pids) { $proc = Get-Process -Id $p -ErrorAction SilentlyContinue; if ($proc) { $namen += "$($proc.ProcessName) (PID $p)" } else { $namen += "PID $p" } }
        Write-Host ("Port 8000     : belegt durch " + ($namen -join ", "))
    } else { Write-Host "Port 8000     : frei (Tool läuft NICHT)" }
    $konsole = @(Get-Process -Name python -ErrorAction SilentlyContinue | Where-Object { $_.MainWindowTitle -like "Friondo Angebotstool Server*" })
    if ($konsole.Count -gt 0) { Write-Host "Konsole       : Fenster 'Friondo Angebotstool Server' (start.bat) läuft, PID $($konsole[0].Id)" }
    if (Test-Path -LiteralPath $Marker) {
        Write-Host ("Wartungsmarker: GESETZT seit {0} ({1}) – Wächter greift nicht ein; entfernen mit scripts\dienst-neustart.bat --start" -f (Get-Item -LiteralPath $Marker).LastWriteTime, $Marker)
    } else { Write-Host "Wartungsmarker: nicht gesetzt" }
    foreach ($name in @("dienst-out.log", "dienst-err.log")) {
        $datei = Join-Path $LogOrdner $name
        if (Test-Path -LiteralPath $datei) { Write-Host ("Log           : {0} {1} MB, Stand {2}" -f $name, [math]::Round((Get-Item -LiteralPath $datei).Length / 1MB, 1), (Get-Item -LiteralPath $datei).LastWriteTime) }
    }
    $zeilen = Letzte-Zeilen 5
    if ($zeilen.Count -gt 0) { Write-Host "waechter.log (letzte Zeilen):"; foreach ($z in $zeilen) { Write-Host "  $z" } }
    else { Write-Host "waechter.log  : noch keine Einträge" }
}


# --- Ablauf ---------------------------------------------------------------------------

if ($AufgabeAnlegen -or $WaechterAnlegen -or $Entfernen -or $Status -or $Rotieren) {
    $rc = 0
    if ($Entfernen) { if (-not (Aufgaben-Entfernen)) { $rc = 1 } }
    if ($AufgabeAnlegen) { if (-not (Aufgabe-Anlegen)) { $rc = 1 } }
    if ($WaechterAnlegen) { if (-not (Waechter-Anlegen)) { $rc = 1 } }
    if ($Rotieren) { foreach ($m in (Logs-Rotieren)) { Write-Host $m; Protokoll "Rotation" $m } }
    if ($Status) { Status-Anzeigen }
    exit $rc
}

$weg = Weg-Erkennen
$befund = Health

if ($Neustart) {
    if (Tool-Neustarten $weg "Neustart angefordert (-Neustart)") { exit 0 } else { exit 1 }
}

$ausfall = (-not $befund.Erreichbar) -or ($befund.Http -eq 503) -or ($befund.Status -eq "fehler")
if ($ausfall) {
    $grund = $(if ($befund.Erreichbar) { "HTTP $($befund.Http) " + ($befund.Gruende -join "; ") } else { $befund.Text })
    if (Test-Path -LiteralPath $Marker) {
        Protokoll "AUSFALL: $grund" ("Wartungsmarker gesetzt seit {0} – keine Maßnahme" -f (Get-Item -LiteralPath $Marker).LastWriteTime)
        exit 0
    }
    if (-not (Neustart-Erlaubt)) {
        Protokoll "AUSFALL: $grund" "letzter Neustart vor weniger als $NeustartAbstand min – warte (Ursache prüfen: data\fehler.log, dienst-err.log)"
        exit 1
    }
    if (Tool-Neustarten $weg "AUSFALL: $grund") { exit 0 } else { exit 1 }
}

if ($befund.Status -eq "warn") {
    $text = "warn: " + ($befund.Gruende -join "; ")
    $letzte = Letzte-Zeilen 1
    $wiederholung = $false
    if ($letzte.Count -gt 0 -and $letzte[0] -like "* | $text | *") {
        try {
            $zeit = [datetime]::ParseExact($letzte[0].Substring(0, 19), "yyyy-MM-dd HH:mm:ss", $null)
            if (((Get-Date) - $zeit).TotalMinutes -lt 60) { $wiederholung = $true }
        } catch {}
    }
    if (-not $wiederholung) { Protokoll $text "keine Maßnahme (warn ist kein Neustartgrund)" }
} else {
    # ok / 404 / unlesbar: Herzschlag höchstens einmal am Tag
    $heute = (Get-Date).ToString("yyyy-MM-dd")
    $vorhanden = @(Letzte-Zeilen 300 | Where-Object { $_.StartsWith($heute) -and $_ -like "* | $HEARTBEAT_TEXT | *" })
    if ($vorhanden.Count -eq 0) { Protokoll $HEARTBEAT_TEXT ("Weg {0}; {1}" -f $weg, $befund.Text) }
}

# Rotation (Aufgaben-Variante): freie Dateien sofort, laufende nachts per kurzem Neustart
if ($weg -eq "aufgabe" -and (Logs-Zu-Gross)) {
    $meldungen = Logs-Rotieren
    foreach ($m in $meldungen) { if ($m -like "*rotiert*") { Protokoll "Rotation" $m } }
    if ((Logs-Zu-Gross) -and (Get-Date).Hour -eq $ROTATION_STUNDE -and -not (Test-Path -LiteralPath $Marker) -and (Neustart-Erlaubt)) {
        Tool-Neustarten $weg "Rotation: dienst-Log > 10 MB (nächtlicher Neustart)" | Out-Null
    }
}
exit 0
