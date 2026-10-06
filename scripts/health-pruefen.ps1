# Friondo Angebotstool – /health prüfen (v27, PLAN_V17 Phase 129)
#
# Zweck 1 – Überwachung von fr-wts-02 aus (Aufgabenplanung alle 5 Minuten unter dem
#   Benutzerkonto von Andreas): http://192.168.35.4:8000/health abfragen; bei Ausfall
#   (keine Antwort) oder HTTP 503 Windows-Benachrichtigung an Andreas und Zeile in
#   C:\Users\a.scheelen\Tools\health.log. Bei anhaltendem Ausfall höchstens alle 30 Minuten
#   erneut benachrichtigen (-Erinnerung), bei Rückkehr einmal „wieder erreichbar“.
#   BurntToast wird NICHT vorausgesetzt: Reihenfolge New-BurntToastNotification (nur wenn
#   das Modul installiert ist) → msg.exe an die eigene Sitzung → Windows.Forms-MessageBox.
#   „warn“ ist kein Ausfall (nur Log-Zeile) – ebenso wenig HTTP 404 (Tool antwortet,
#   aber Fassung vor v27 ohne /health, z. B. nach rollback.bat).
#
# Zweck 2 – Anzeige für die Server-Skripte (dienst-*.bat, update.bat, rollback.bat):
#   -NurAnzeigen gibt den Status einmal aus (kein Log, keine Benachrichtigung),
#   -Warten N wartet bis zu N Sekunden auf die erste Antwort (nach einem Start).
#
# Einrichtung auf fr-wts-02 (Eingabeaufforderung unter dem eigenen Konto, kein Administrator
# nötig; die Aufgabe läuft nur bei angemeldetem Benutzer, damit die Benachrichtigung sichtbar ist):
#   schtasks /Create /F /TN "Friondo Health fr-wts-02" /SC MINUTE /MO 5 /TR "powershell.exe -NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File \"C:\Users\a.scheelen\Tools\Angebotstool\scripts\health-pruefen.ps1\""
#   Probelauf:   schtasks /Run /TN "Friondo Health fr-wts-02"      → Zeile in C:\Users\a.scheelen\Tools\health.log
#   Entfernen:   schtasks /Delete /F /TN "Friondo Health fr-wts-02"
#   Von Hand:    powershell -NoProfile -ExecutionPolicy Bypass -File scripts\health-pruefen.ps1 -NurAnzeigen
#
# Exit-Code: 0 = ok/warn (oder 404 = Tool ohne /health), 1 = fehler/503/keine Antwort, 2 = Bedienfehler.
[CmdletBinding()]
param(
    [string]$Adresse = "http://192.168.35.4:8000/health",
    [string]$Log = "C:\Users\a.scheelen\Tools\health.log",
    [int]$Warten = 0,              # Sekunden auf die erste Antwort warten (0 = ein Versuch)
    [int]$Timeout = 10,            # Sekunden je Abfrage
    [int]$Erinnerung = 30,         # Minuten zwischen zwei Benachrichtigungen bei anhaltendem Ausfall
    [switch]$NurAnzeigen,          # nur ausgeben – kein Log, keine Benachrichtigung
    [switch]$OhneBenachrichtigung, # Log schreiben, aber nicht benachrichtigen
    [switch]$Still                 # keine Konsolenausgabe (Aufgabenplanung)
)

$ErrorActionPreference = "Continue"
$script:Utf8Log = New-Object System.Text.UTF8Encoding($true)   # BOM nur beim Anlegen der Datei (AppendAllText), damit Notepad/Get-Content die Umlaute erkennen


function Health-Abfragen {
    param([string]$Url, [int]$Sekunden)
    # Liefert ein Objekt: Erreichbar, Http, Status, Version, Commit, DbMs, UptimeS, Pool, Gruende, Text
    $ergebnis = [ordered]@{ Erreichbar = $false; Http = 0; Status = ""; Version = ""; Commit = "";
                            DbMs = $null; UptimeS = $null; Pool = ""; Gruende = @(); Text = "" }
    $antwort = $null
    try {
        $anfrage = [System.Net.HttpWebRequest]::Create($Url)
        $anfrage.Method = "GET"
        $anfrage.Timeout = $Sekunden * 1000
        $anfrage.ReadWriteTimeout = $Sekunden * 1000
        $anfrage.UserAgent = "friondo-health-pruefen/v27"
        $anfrage.Headers.Add("Cache-Control", "no-cache")
        $host_ = ([System.Uri]$Url).Host
        if ($host_ -eq "127.0.0.1" -or $host_ -eq "localhost") { $anfrage.Proxy = $null }
        $antwort = $anfrage.GetResponse()
    } catch [System.Net.WebException] {
        if ($_.Exception.Response -ne $null) {
            $antwort = $_.Exception.Response
        } else {
            $ergebnis.Text = "keine Antwort: " + $_.Exception.Message
            return New-Object PSObject -Property $ergebnis
        }
    } catch {
        $ergebnis.Text = "keine Antwort: " + $_.Exception.Message
        return New-Object PSObject -Property $ergebnis
    }
    try {
        $ergebnis.Http = [int]$antwort.StatusCode
        $ergebnis.Erreichbar = $true
        $leser = New-Object System.IO.StreamReader($antwort.GetResponseStream(), [System.Text.Encoding]::UTF8)
        $rumpf = $leser.ReadToEnd()
        $leser.Close()
    } catch {
        $rumpf = ""
    } finally {
        try { $antwort.Close() } catch {}
    }
    if ($ergebnis.Http -eq 404) {
        $ergebnis.Status = "kein /health"
        $ergebnis.Text = "Tool antwortet (HTTP 404) – Fassung ohne /health (vor v27)?"
        return New-Object PSObject -Property $ergebnis
    }
    try {
        $json = $rumpf | ConvertFrom-Json
        $ergebnis.Status = [string]$json.status
        $ergebnis.Version = [string]$json.version
        $ergebnis.Commit = [string]$json.commit
        $ergebnis.DbMs = $json.db_ms
        $ergebnis.UptimeS = $json.uptime_s
        if ($json.pool -ne $null) {
            $ergebnis.Pool = "$($json.pool.checked_out)/$($json.pool.maximum) ($($json.pool.prozent) %)"
        }
        if ($json.gruende -ne $null) { $ergebnis.Gruende = @($json.gruende) }
    } catch {
        $ergebnis.Status = "unlesbar"
        $ergebnis.Text = "Antwort kein JSON (HTTP $($ergebnis.Http)): " + $rumpf.Substring(0, [Math]::Min(120, $rumpf.Length))
    }
    return New-Object PSObject -Property $ergebnis
}


function Uptime-Text([object]$Sekunden) {
    if ($Sekunden -eq $null) { return "-" }
    $s = [int]$Sekunden
    $tage = [math]::Floor($s / 86400); $rest = $s % 86400
    $stunden = [math]::Floor($rest / 3600); $minuten = [math]::Floor(($rest % 3600) / 60)
    if ($tage -gt 0) { return "$tage d $stunden h $minuten min" }
    return "$stunden h $minuten min"
}


function Zustand-Lesen([string]$Datei) {
    # Inhalt: "ausfall|<Zeit der letzten Benachrichtigung>" oder "ok"
    if (-not (Test-Path -LiteralPath $Datei)) { return @{ Art = "ok"; Zeit = $null } }
    try {
        $inhalt = (Get-Content -LiteralPath $Datei -ErrorAction Stop | Select-Object -First 1)
        if ($inhalt -and $inhalt.StartsWith("ausfall|")) {
            $zeit = [datetime]::ParseExact($inhalt.Substring(8), "yyyy-MM-dd HH:mm:ss", $null)
            return @{ Art = "ausfall"; Zeit = $zeit }
        }
    } catch {}
    return @{ Art = "ok"; Zeit = $null }
}


function Zustand-Schreiben([string]$Datei, [string]$Art, [datetime]$Zeit) {
    try {
        $text = $Art
        if ($Art -eq "ausfall") { $text = "ausfall|" + $Zeit.ToString("yyyy-MM-dd HH:mm:ss") }
        [System.IO.File]::WriteAllText($Datei, $text, $script:Utf8Log)
    } catch {}
}


function Benachrichtigen([string]$Titel, [string]$Text) {
    # Reihenfolge: BurntToast (nur wenn installiert) → msg.exe an die eigene Sitzung → MessageBox
    $ok = $false
    if (Get-Module -ListAvailable -Name BurntToast -ErrorAction SilentlyContinue) {
        try {
            Import-Module BurntToast -ErrorAction Stop
            New-BurntToastNotification -Text $Titel, $Text -ErrorAction Stop
            $ok = $true
        } catch {}
    }
    if (-not $ok) {
        try {
            $msg = Get-Command msg.exe -ErrorAction SilentlyContinue
            if ($msg) {
                & $msg.Source $env:USERNAME /TIME:120 ("$Titel`r`n$Text") 2>$null
                if ($LASTEXITCODE -eq 0) { $ok = $true }
            }
        } catch {}
    }
    if (-not $ok) {
        try {
            Add-Type -AssemblyName System.Windows.Forms -ErrorAction Stop
            [System.Windows.Forms.MessageBox]::Show($Text, $Titel, "OK", "Warning") | Out-Null
            $ok = $true
        } catch {}
    }
    return $ok
}


function Log-Schreiben([string]$Datei, [string]$Zeile) {
    try {
        $ordner = Split-Path -Parent $Datei
        if ($ordner -and -not (Test-Path -LiteralPath $ordner)) { New-Item -ItemType Directory -Path $ordner -Force | Out-Null }
        # Rotation: ab 2 MB → .1 (eine Generation)
        if ((Test-Path -LiteralPath $Datei) -and ((Get-Item -LiteralPath $Datei).Length -gt 2MB)) {
            Move-Item -LiteralPath $Datei -Destination ($Datei + ".1") -Force -ErrorAction SilentlyContinue
        }
        [System.IO.File]::AppendAllText($Datei, $Zeile + "`r`n", $script:Utf8Log)
    } catch {
        if (-not $Still) { Write-Host "Log $Datei konnte nicht geschrieben werden: $($_.Exception.Message)" }
    }
}


# --- Ablauf ---------------------------------------------------------------------------

if ($Timeout -lt 1) { $Timeout = 1 }
$start = Get-Date
$befund = Health-Abfragen -Url $Adresse -Sekunden $Timeout
while (-not $befund.Erreichbar -and ((Get-Date) - $start).TotalSeconds -lt $Warten) {
    Start-Sleep -Seconds 1
    $befund = Health-Abfragen -Url $Adresse -Sekunden $Timeout
}

$jetzt = Get-Date
$ausfall = $false
$kurz = ""
if (-not $befund.Erreichbar) {
    $ausfall = $true
    $kurz = "AUSFALL – " + $befund.Text
} elseif ($befund.Http -eq 503 -or $befund.Status -eq "fehler") {
    $ausfall = $true
    $kurz = "FEHLER (HTTP $($befund.Http)) – " + ($befund.Gruende -join "; ")
} elseif ($befund.Http -eq 404) {
    $kurz = $befund.Text
} elseif ($befund.Status -eq "unlesbar") {
    $kurz = $befund.Text
} else {
    $kurz = $befund.Status
    if ($befund.Gruende.Count -gt 0) { $kurz += " – " + ($befund.Gruende -join "; ") }
}

if (-not $Still) {
    $zeile1 = "/health $Adresse"
    if ($befund.Erreichbar) { $zeile1 += " (HTTP $($befund.Http))" }
    Write-Host $zeile1
    if ($befund.Erreichbar -and $befund.Version) {
        Write-Host ("  Status: {0,-6} Version {1}  Commit {2}  DB {3} ms  Uptime {4}  Pool {5}" -f `
            $befund.Status, $befund.Version, $befund.Commit, $befund.DbMs, (Uptime-Text $befund.UptimeS), $befund.Pool)
        if ($befund.Gruende.Count -gt 0) { Write-Host ("  Gruende: " + ($befund.Gruende -join "; ")) }
    } else {
        Write-Host ("  " + $kurz)
    }
}

if (-not $NurAnzeigen) {
    $zeitText = $jetzt.ToString("yyyy-MM-dd HH:mm:ss")
    $art = "ok"
    if ($ausfall) { $art = "AUSFALL" } elseif ($befund.Status -eq "warn") { $art = "warn" }
    $details = ""
    if ($befund.Erreichbar -and $befund.Version) {
        $details = "$($befund.Version) $($befund.Commit) | db $($befund.DbMs) ms | uptime $($befund.UptimeS) s"
    }
    Log-Schreiben -Datei $Log -Zeile ("{0} | {1,-7} | HTTP {2} | {3} | {4}" -f $zeitText, $art, $befund.Http, $details, $kurz)

    if (-not $OhneBenachrichtigung) {
        $zustandDatei = $Log + ".zustand"
        $zustand = Zustand-Lesen $zustandDatei
        if ($ausfall) {
            $melden = $false
            if ($zustand.Art -ne "ausfall") { $melden = $true }
            elseif ($zustand.Zeit -ne $null -and ($jetzt - $zustand.Zeit).TotalMinutes -ge $Erinnerung) { $melden = $true }
            if ($melden) {
                $text = "Angebotstool ($Adresse): $kurz`r`nZeit: $zeitText`r`nMassnahme: scripts\dienst-status.bat auf dem Server, dann scripts\dienst-neustart.bat (Runbook docs\betrieb.md)."
                $gemeldet = Benachrichtigen -Titel "Friondo Angebotstool nicht erreichbar" -Text $text
                Zustand-Schreiben -Datei $zustandDatei -Art "ausfall" -Zeit $jetzt
                Log-Schreiben -Datei $Log -Zeile ("{0} | meldung | Benachrichtigung {1}" -f $zeitText, $(if ($gemeldet) { "gesendet" } else { "NICHT moeglich (BurntToast/msg/MessageBox fehlgeschlagen)" }))
            }
        } elseif ($zustand.Art -eq "ausfall") {
            Benachrichtigen -Titel "Friondo Angebotstool wieder erreichbar" -Text "Angebotstool ($Adresse) antwortet wieder: $kurz`r`nZeit: $zeitText" | Out-Null
            Zustand-Schreiben -Datei $zustandDatei -Art "ok" -Zeit $jetzt
            Log-Schreiben -Datei $Log -Zeile ("{0} | meldung | wieder erreichbar" -f $zeitText)
        }
    }
}

if ($ausfall) { exit 1 }
exit 0
