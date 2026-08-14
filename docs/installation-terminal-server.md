# Installation auf dem Terminal Server (Phase 16, Stand 08/2026)

Anleitung für die IT: Friondo Angebotstool auf dem Terminal Server im
Rechenzentrum einrichten – als Dienst mit Autostart, erreichbar im Firmennetz.
Für die Standard-Einrichtung genügt das Skript in Schritt 4.

## 1. Voraussetzungen

- Windows Server (Terminalserver), lokaler Administratorzugang
- Python 3.12 (64-Bit) – Installation „für alle Benutzer",
  Haken bei „Add python.exe to PATH"
- Freigegebener TCP-Port **8000** in der Windows-Firewall (nur Firmennetz;
  das Installationsskript legt die Regel automatisch an)

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
siehe `docs/graph-einrichtung.md`).

## 4. Als Dienst mit Autostart

**Variante A – Aufgabenplanung (empfohlen, ohne Zusatzsoftware):**
Eingabeaufforderung **als Administrator** im Projektordner:

```bat
scripts\dienst-installieren.bat
```

Das Skript erstellt die venv, installiert die Abhängigkeiten, legt die
Autostart-Aufgabe „Friondo Angebotstool" (Start bei Boot, Konto SYSTEM,
Bindung an 0.0.0.0:8000) und die Firewall-Regel an und startet den Dienst
sofort. Entfernen: `scripts\dienst-entfernen.bat`.

**Variante B – NSSM (echter Windows-Dienst):**

1. NSSM herunterladen (nssm.cc), `nssm.exe` nach `C:\Friondo\` legen
2. ```bat
   nssm install FriondoAngebotstool "C:\Friondo\Angebotstool\venv\Scripts\python.exe" "-m uvicorn app.main:app --host 0.0.0.0 --port 8000"
   nssm set FriondoAngebotstool AppDirectory "C:\Friondo\Angebotstool"
   nssm start FriondoAngebotstool
   ```

Die Hintergrund-Abrufe (monday-Leads und Mail-Verlauf, je 15 Minuten)
laufen im selben Prozess mit – es ist kein weiterer Dienst nötig.

## 5. Daten & Backup prüfen

- Datenpfad: `data\angebotstool.db` (SQLite im WAL-Modus), erzeugte PDFs
  unter `data\angebote\`, signierte unter `data\angebote\signiert\`
- Tägliches Backup: läuft automatisch beim App-Start nach `data\backups\`
  (Aufbewahrung 30 Tage) und nutzt die SQLite-Backup-API – die Sicherung
  ist damit auch bei laufendem Betrieb konsistent inkl. WAL-Änderungen.
  Bei Dauerbetrieb ohne Neustart zusätzlich den Ordner `data\` ins
  zentrale Server-Backup einbeziehen.
- Kontrolle: nach dem ersten Start muss `data\backups\angebotstool-<Datum>.db`
  existieren.

## 6. Zugriff im Firmennetz

- Innendienst (Terminalsitzung oder PC im Firmennetz):
  `http://<SERVERNAME>:8000` – Servername/IP in der `README.md` eintragen.
- Desktop-Verknüpfung für den Innendienst: Rechtsklick → Neu → Verknüpfung →
  Ziel `http://<SERVERNAME>:8000` (Icon: `friondo.ico` aus dem Projektordner).
- Anmeldung beim allerersten Start (leere Datenbank): **Admin / PIN 1234** –
  sofort unter „Benutzer" die echten Benutzer anlegen und die Admin-PIN ändern.
- Abnahmetest: aus einer Terminalsitzung anmelden, Erfassungsliste öffnen,
  ein Testangebot als PDF erzeugen, Angebotsliste auf Leads/DB-Ampel prüfen.

## 7. Mobilzugriff Außendienst

Entscheidung offen – siehe `docs/mobilzugriff.md` (Variante A WireGuard,
empfohlen, oder Variante B öffentlich über HTTPS). **Bis dahin ist die App
ausschließlich im Firmennetz erreichbar.**

## 8. Fern-Signatur (optional, Standard AUS)

Sollen Kunden Angebote online unterschreiben, braucht es zusätzlich eine
öffentliche HTTPS-Adresse für genau eine Route – Anforderung und
Alternativen: `docs/fern-signatur-it.md`. Aktiviert wird die Funktion danach
im Tool unter Parametrierung → Fern-Signatur.
