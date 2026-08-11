# Installation auf dem Terminal Server (Phase 16)

Anleitung für die IT: Friondo Angebotstool auf dem Terminal Server im
Rechenzentrum einrichten – als Dienst mit Autostart, erreichbar im Firmennetz.

## 1. Voraussetzungen

- Windows Server (Terminalserver), lokaler Administratorzugang
- Python 3.11 oder neuer (64-Bit) – Installation „für alle Benutzer",
  Haken bei „Add python.exe to PATH"
- Freigegebener TCP-Port **8000** in der Windows-Firewall (nur Firmennetz)

## 2. Projekt übertragen

1. Projektordner `Angebotserstellungtool` komplett auf den Server kopieren,
   empfohlen: `C:\Friondo\Angebotstool`
   (inkl. `konfigurator_logik_v2.xlsx`, `Artikel-Preislisten\`, `Layout - Logo\`,
   `anlagen\`, `ANGEBOTSTEXTE.md`)
2. **Nicht** mitkopieren: `venv\` (wird neu erstellt). Der Ordner `data\` nur
   mitkopieren, wenn der Datenbestand (Kunden, Angebote, Nummernkreis!)
   übernommen werden soll – im Regelfall: ja.

## 3. Einrichtung

In einer Eingabeaufforderung im Projektordner:

```bat
python -m venv venv
venv\Scripts\pip install -r requirements.txt
copy .env.example .env
```

Danach einmal testweise starten (`start.bat`) und im Browser
`http://localhost:8000` prüfen. Anmeldung beim ersten Start: **Admin / PIN 1234**
– sofort unter „Benutzer" die echten Benutzer anlegen und die Admin-PIN ändern.

## 4. Als Dienst mit Autostart

**Variante A – Aufgabenplanung (ohne Zusatzsoftware):**

```bat
schtasks /Create /TN "Friondo Angebotstool" /SC ONSTART /RU SYSTEM ^
  /TR "C:\Friondo\Angebotstool\venv\Scripts\python.exe -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --app-dir C:\Friondo\Angebotstool"
```

Start ohne Neustart: `schtasks /Run /TN "Friondo Angebotstool"`.

**Variante B – NSSM (echter Windows-Dienst, empfohlen):**

1. NSSM herunterladen (nssm.cc), `nssm.exe` nach `C:\Friondo\` legen
2. ```bat
   nssm install FriondoAngebotstool "C:\Friondo\Angebotstool\venv\Scripts\python.exe" "-m uvicorn app.main:app --host 0.0.0.0 --port 8000"
   nssm set FriondoAngebotstool AppDirectory "C:\Friondo\Angebotstool"
   nssm start FriondoAngebotstool
   ```

## 5. Daten & Backup prüfen

- Datenpfad: `data\angebotstool.db` (SQLite), erzeugte PDFs unter `data\angebote\`
- Tägliches Backup: läuft automatisch beim App-Start nach `data\backups\`
  (Aufbewahrung 30 Tage). Bei Dauerbetrieb ohne Neustart zusätzlich eine
  Aufgabe einrichten, die den Ordner `data\` ins zentrale Server-Backup einbezieht.
- Kontrolle: nach dem ersten Start muss `data\backups\angebotstool-<Datum>.db`
  existieren.

## 6. Zugriff im Firmennetz

- Innendienst (Terminalsitzung oder PC im Firmennetz):
  `http://<SERVERNAME>:8000` – Servername/IP in der `README.md` eintragen.
- Desktop-Verknüpfung für den Innendienst: Rechtsklick → Neu → Verknüpfung →
  Ziel `http://<SERVERNAME>:8000` (Icon: `friondo.ico` aus dem Projektordner).
- Abnahmetest: aus einer Terminalsitzung anmelden, Erfassungsliste öffnen,
  ein Testangebot als PDF erzeugen.

## 7. Mobilzugriff Außendienst

Entscheidung offen – siehe `docs/mobilzugriff.md` (Variante A WireGuard,
empfohlen, oder Variante B öffentlich über HTTPS). **Bis dahin ist die App
ausschließlich im Firmennetz erreichbar.**
