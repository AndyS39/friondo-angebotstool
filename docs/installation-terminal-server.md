# Installation auf dem Terminal Server (Phase 16, Stand 08/2026 – Abschnitte 1, 4, 5 und 7 aktualisiert für v27, 10/2026)

Anleitung für die IT und für Andreas: Friondo Angebotstool auf dem Server
einrichten – als Windows-Dienst mit Autostart, erreichbar im Firmennetz.
Für die Standard-Einrichtung genügt das Skript in Abschnitt 4. Der laufende
Betrieb (Starten/Stoppen, Update, Rollback, Backup, Störungen) steht im
Runbook `docs/betrieb.md`; die offenen Punkte für die IT in
`docs/betrieb-it-uebergabe.md`.

Stand 10/2026: Der Server läuft unter `C:\Users\kdadmin\Desktop\Angebotstool`
und ist im Firmennetz unter `http://192.168.35.4:8000` erreichbar; der
Entwicklungs-PC ist fr-wts-02 (`C:\Users\a.scheelen\Tools\Angebotstool`).

## 1. Voraussetzungen

- Windows Server, lokaler Administratorzugang (Andreas ist lokaler
  Administrator)
- Python 3.12 oder neuer (64-Bit) – Installation „für alle Benutzer“,
  Haken bei „Add python.exe to PATH“. Der Entwicklungs-PC läuft mit
  Python 3.14; welche Version der Server tatsächlich nutzt, zeigt im
  Projektordner `venv\Scripts\python.exe --version`.
  **Python-Version aktualisieren:** neue Python-Version installieren, das
  Tool stoppen (`scripts\dienst-neustart.bat --stop`), den Ordner `venv\`
  umbenennen (z. B. `venv_alt`) und `scripts\dienst-installieren.bat` erneut
  ausführen – das Skript legt die venv mit dem Python aus dem PATH neu an
  und installiert die Abhängigkeiten. Läuft alles (`/health`, Smoke-Test),
  kann `venv_alt` gelöscht werden.
- Freigegebener TCP-Port **8000** in der Windows-Firewall (nur Firmennetz;
  das Installationsskript legt die Regel automatisch an)
- Optional für Weg A in Abschnitt 4: `nssm.exe` (NSSM, https://nssm.cc/download,
  ZIP entpacken, Datei `win64\nssm.exe` – keine Installation nötig)

## 2. Projekt übertragen

1. Projektordner `Angebotserstellungtool` komplett auf den Server kopieren,
   empfohlen: `C:\Friondo\Angebotstool`
   (inkl. `konfigurator_logik_v4.xlsx`, `Artikel-Preislisten\`,
   `Layout - Logo\`, `anlagen\`, `ANGEBOTSTEXTE.md`, `scripts\`)
2. **Nicht** mitkopieren: `venv\` (wird neu erstellt).
3. Der Ordner `data\` enthält den kompletten Datenbestand und wird im
   Regelfall mitgenommen:
   - `angebotstool.db` **plus** `angebotstool.db-wal` und
     `angebotstool.db-shm` (SQLite läuft im WAL-Modus – die App auf dem
     alten Rechner **vor dem Kopieren beenden**, sonst fehlen die letzten
     Änderungen)
   - `angebote\` (erzeugte PDFs) und `angebote\signiert\` (signierte PDFs)
   - `backups\` (Tagesbackups), `.graph_token.json` (Microsoft-Anmeldung,
     optional), `.session_secret` (Login-Cookies; fehlt sie, müssen sich
     alle einmal neu anmelden)

## 3. .env prüfen

`copy .env.example .env` (macht das Skript automatisch) und anschließend
eintragen bzw. prüfen: `MONDAY_API_TOKEN` (Lead-Sync),
`GRAPH_CLIENT_ID`/`GRAPH_TENANT_ID` (E-Mail-Versand + Mail-Verlauf,
siehe `docs/graph-einrichtung.md`), seit v27 außerdem `BACKUP_ZIEL`
(Abschnitt 5) und – nur wenn die IT einen Reverse-Proxy stellt –
`PROXY_IPS`, `HTTPS_AKTIV`, `BASIS_URL` (Vorlage in `.env.example`).

## 4. Als Dienst mit Autostart (v27 – Schritt für Schritt)

Seit v27 läuft das Tool auf dem Server **nicht mehr als Konsolenfenster aus
`start.bat`** in der Sitzung kdadmin (Abmelden beendete das Tool), sondern als
Windows-Dienst bzw. als Aufgabe der Aufgabenplanung unter dem Konto SYSTEM:
Start beim Hochfahren, Neustart nach Absturz, Ausgaben in Logdateien,
Wächter-Aufgabe alle 5 Minuten. Ein einziges Skript richtet alles ein und
erkennt selbst, welcher Weg möglich ist:

- **Weg A – NSSM (empfohlen, echter Windows-Dienst `FriondoAngebotstool`):**
  wird gewählt, wenn `nssm.exe` neben dem Skript (`scripts\nssm.exe`), im
  Projektordner oder unter `C:\Friondo\nssm.exe` liegt. Neustart nach Absturz
  nach 5 s, Logs `data\log\dienst-out.log`/`dienst-err.log` mit Rotation ab
  10 MB, Konto SYSTEM (ein Dienstkonto der IT kann später nachgetragen
  werden, siehe unten).
- **Weg B – Aufgabenplanung ohne Zusatzsoftware (Aufgabe „Friondo
  Angebotstool“):** wird gewählt, wenn kein `nssm.exe` gefunden wird. Start
  beim Hochfahren als SYSTEM, kein Zeitlimit, Ausgabe nach
  `data\log\dienst-out.log`; Neustart bei Ausfall übernimmt die Wächter-Aufgabe.

In beiden Fällen legt das Skript die Wächter-Aufgabe „Friondo Angebotstool
Wächter“ (alle 5 Minuten `scripts\waechter.ps1`: `/health` prüfen, bei Ausfall
neu starten, Log `data\log\waechter.log`) und die Firewall-Regel an, erstellt
bei Bedarf venv und `.env`, beendet nach Rückfrage ein noch laufendes
Konsolenfenster „Friondo Angebotstool Server“ und entfernt die alte
Hotfix-Aufgabe „Friondo Backup“ (die Sicherung läuft seit v27 im Tool,
Abschnitt 5).

**So geht es (Andreas, etwa 10 Minuten, am besten im Wartungsfenster):**

1. Optional NSSM besorgen: https://nssm.cc/download → ZIP entpacken →
   `win64\nssm.exe` nach `C:\Users\kdadmin\Desktop\Angebotstool\scripts\`
   kopieren. Ohne diesen Schritt nimmt das Skript automatisch Weg B.
2. Startmenü → „cmd“ eingeben → Rechtsklick auf „Eingabeaufforderung“ →
   **Als Administrator ausführen**.
3. In den Projektordner wechseln und das Skript starten – ein Befehl:

   ```bat
   cd /d C:\Users\kdadmin\Desktop\Angebotstool
   scripts\dienst-installieren.bat
   ```

   Das Skript fragt nur, ob das noch laufende Konsolenfenster beendet werden
   darf (mit `j` antworten). Am Ende zeigt es das Ergebnis von `/health`
   (Status `ok` oder `warn`, Version, Commit) und den gewählten Weg.
4. Kontrolle: im Browser `http://localhost:8000` (auf dem Server) bzw.
   `http://192.168.35.4:8000` (im Firmennetz) öffnen und anmelden; danach
   einmal **abmelden und wieder anmelden** (Windows-Sitzung) – das Tool muss
   weiterlaufen. Zusätzlich `scripts\dienst-status.bat` ausführen: zeigt Weg,
   Zustand, Port 8000, Wächter und `/health`.
5. Die Zeile `BACKUP_ZIEL=` in der `.env` prüfen (Abschnitt 5) – ohne
   Eintrag meldet `/health` dauerhaft `warn` „kein Backup-Ziel“.

Danach: Starten/Stoppen nur noch über `scripts\dienst-neustart.bat`,
Status über `scripts\dienst-status.bat`, Entfernen über
`scripts\dienst-entfernen.bat`; `update.bat` und `rollback.bat` erkennen den
Weg selbst. `start.bat` bleibt für den Entwicklungs-PC und bricht auf dem
Server mit einem Hinweis ab, sobald der Dienst bzw. die Aufgabe existiert.

**Dienstkonto der IT (Weg A, später):** in der Administrator-Eingabeaufforderung
`scripts\nssm.exe set FriondoAngebotstool ObjectName "DOMÄNE\Konto" "Kennwort"`,
danach `scripts\dienst-neustart.bat`. Das Konto braucht Schreibrecht auf den
Projektordner und `data\` sowie – falls `BACKUP_ZIEL` eine Netzfreigabe ist –
auf die Freigabe (SYSTEM hat auf Netzfreigaben keine Rechte).

Die Hintergrundläufe (monday-Leads, Mail-Verlauf, Backup, Geokodierung,
Betriebs-Wache usw.) laufen im selben Prozess mit – es ist kein weiterer
Dienst nötig.

## 5. Daten & Backup prüfen (v27: Sicherung läuft im Tool)

- Datenpfad: `data\angebotstool.db` (SQLite im WAL-Modus), erzeugte PDFs
  unter `data\angebote\`, signierte unter `data\angebote\signiert\`,
  Projektunterlagen unter `data\projekte\`. `data\` muss auf einer lokalen
  Platte liegen – nie auf einem Netzlaufwerk oder in einem Sync-Ordner
  (OneDrive): SQLite-WAL verträgt das nicht.
- **Sicherung (seit v27 im Tool, Scheduler 02:30):** (a) SQLite-Backup-API
  nach `data\backups\angebotstool-<Datum>.db` (Aufbewahrung 30 Tage, auch bei
  laufendem Betrieb konsistent inkl. WAL-Änderungen), (b) Spiegelung von
  `data\backups`, `data\angebote` (inkl. `signiert`), `data\projekte` und
  `.env` per robocopy nach **`BACKUP_ZIEL`** aus der `.env` (Aufbewahrung am
  Ziel 90 Tage), Protokoll `data\backups\ziel.log`. Jeder Ordner außerhalb des
  Servers taugt als Ziel: Netzlaufwerk der IT (später, UNC-Pfad), bis dahin ein
  freigegebener Ordner auf fr-wts-02 oder ein OneDrive-/SharePoint-Ordner
  (für Sicherungskopien ist Sync-Speicher in Ordnung). Ohne Eintrag bleibt
  es bei der lokalen Sicherung, und `/health` meldet `warn` „kein Backup-Ziel“.
- Die geplante Aufgabe **„Friondo Backup“ aus dem Hotfix 06.10.2026 ist damit
  überflüssig** – `scripts\dienst-installieren.bat` entfernt sie; von Hand:
  `schtasks /Delete /TN "Friondo Backup" /F`. `scripts\backup-nacht.bat` bleibt
  für Handläufe erhalten (`scripts\backup-nacht.bat <Zielordner>`).
- Kontrolle: Parametrierung → Betrieb zeigt letzte Sicherung, Backup-Ziel und
  Spiegelungsstatus (Knopf „Backup jetzt“ für einen Sofortlauf); `/health`
  meldet `warn`, wenn das letzte Backup älter als 26 h ist oder die
  Spiegelung fehlschlug. Nach dem ersten Start muss
  `data\backups\angebotstool-<Datum>.db` existieren.
- **Restore-Test monatlich:** `scripts\restore-test.bat` spielt die jüngste
  Sicherung als Kopie nach `diagnose\restore_<Datum>\` ein, migriert sie und
  lässt den Voll-Crawl darüber laufen; Protokoll `docs\betrieb\restore-<Datum>.txt`
  (Runbook `docs/betrieb.md`, Abschnitt „Backup und Restore-Test“).

## 6. Zugriff im Firmennetz

- Innendienst (PC im Firmennetz): `http://192.168.35.4:8000` (bzw.
  `http://<SERVERNAME>:8000`) – die Adresse steht in der `README.md`.
- Desktop-Verknüpfung für den Innendienst: Rechtsklick → Neu → Verknüpfung →
  Ziel `http://192.168.35.4:8000` (Icon: `friondo.ico` aus dem Projektordner).
- Anmeldung beim allerersten Start (leere Datenbank): **Admin / PIN 1234** –
  sofort unter „Benutzer“ die echten Benutzer anlegen und die Admin-PIN ändern.
- Abnahmetest: aus dem Firmennetz anmelden, Erfassungsliste öffnen,
  ein Testangebot als PDF erzeugen, Angebotsliste auf Leads/DB-Ampel prüfen –
  oder `scripts\smoke.bat` auf dem Server ausführen.

## 7. Mobilzugriff Außendienst (VPN vorhanden)

**Umgesetzt (Variante A, WireGuard, Stand 06.10.2026):** Der Außendienst
arbeitet über das bestehende WireGuard-VPN bereits mit dem Tool
(`http://192.168.35.4:8000/erfassung` auf dem Handy nach Einschalten des
Tunnels). Die IT wird nur noch für zusätzliche WireGuard-Profile gebraucht,
wenn mit den 50 Nutzern neue Geräte dazukommen (je Gerät ein Peer, QR-Code,
Sperrprozess bei Geräteverlust). Hintergrund und Alternativen:
`docs/mobilzugriff.md`. Ein öffentlicher Zugang (Variante B) ist nicht
vorgesehen; der Reverse-Proxy mit HTTPS aus `docs/betrieb-it-uebergabe.md`
betrifft nur das Firmennetz/VPN.

## 8. Fern-Signatur (optional, Standard AUS)

Sollen Kunden Angebote online unterschreiben, braucht es zusätzlich eine
öffentliche HTTPS-Adresse für genau eine Route – Anforderung und
Alternativen: `docs/fern-signatur-it.md`. Aktiviert wird die Funktion danach
im Tool unter Parametrierung → Fern-Signatur.
