# Laptop als Entwicklungsrechner für das Friondo-Tool einrichten

Ziel: Der Laptop ersetzt den PC zuhause als Entwicklungsrechner. Der Code kommt
aus dem Git-Repository, alles andere richtet Claude Code ein.

## Schritt 1 – Einmalig installieren (falls noch nicht vorhanden)

- **Git** (git-scm.com, Standardeinstellungen)
- **Python 3.11 oder neuer** (python.org; beim Installieren das Häkchen
  „Add Python to PATH" setzen)
- **Node.js LTS** (nodejs.org) – wird für Claude Code gebraucht
- **Claude Code**: Terminal öffnen, `npm install -g @anthropic-ai/claude-code`,
  danach einmal `claude` starten und anmelden

## Schritt 2 – Repository klonen

Terminal öffnen, in den gewünschten Ordner wechseln (z. B. `cd Dokumente`) und:

```
git clone https://github.com/AndyS39/friondo-angebotstool.git friondo-tool
cd friondo-tool
```

Das Repository liegt auf GitHub (Konto AndyS39, Branch `master`). Beim ersten
Zugriff fragt Git nach dem GitHub-Login – am einfachsten über den Browser-Dialog
des Git Credential Managers, der mit Git für Windows mitkommt.

## Schritt 3 – Was NICHT im Repository liegt und einmalig kopiert werden muss

Geprüft am 22.09.2026 anhand von `.gitignore` und Ordnerinhalt – nur die `.env`
muss wirklich kopiert werden:

| Was | Wo zuhause | Wohin am Laptop | Nötig für |
|---|---|---|---|
| Steuer-Excel, Preislisten, Anhänge, Logo | – | **liegen im Repo**, kommen mit dem Klon | – |
| `.env` (MONDAY_API_TOKEN, GRAPH_CLIENT_ID, GRAPH_TENANT_ID) | Projektordner | gleicher Pfad – steht in `.gitignore`, **nie committen** | Mail, monday-Sync |
| `data/` (Test-Datenbank, PDFs, Signaturen) | Projektordner | **nicht nötig** – in `.gitignore`, Claude Code legt eine frische Test-DB an | – |
| `venv/` | Projektordner | **nicht kopieren** – Claude Code legt sie neu an | – |

Am einfachsten: die Dateien per USB-Stick oder OneDrive vom PC zuhause holen.
Ohne die Zugangsdaten läuft das Tool trotzdem (Mail/monday melden nur Fehler,
blockieren aber nichts).

## Schritt 4 – Claude Code starten und einrichten lassen

Im Ordner `friondo-tool` das Terminal öffnen, `claude` eingeben und diesen
Prompt einfügen:

> Dies ist eine frisch geklonte Kopie des Friondo-Tools auf einem neuen
> Entwicklungsrechner (Windows-Laptop). Lies `CLAUDE.md`. Richte die lokale
> Entwicklungsumgebung ein: virtuelle Python-Umgebung anlegen, Abhängigkeiten
> aus requirements.txt installieren, prüfen, welche Dateien und Ordner das Tool
> beim Start erwartet (Steuer-Excel, Preislisten, Anlagen, Logo, Konfiguration
> mit Zugangsdaten, data-Ordner) und mir eine Liste geben, was davon fehlt und
> von wo ich es kopieren muss. Lege eine leere Test-Datenbank per migrate.py
> an, starte das Tool lokal und sage mir die Adresse zum Öffnen. Lege
> anschließend einen Admin-Testbenutzer mit PIN 1234 sowie 3 Testkunden mit je
> einem angenommenen Angebot an (Tool- und TAIFUN-Variante gemischt), damit ich
> das Projektierungs-Modul später mit Daten testen kann. Dokumentiere alle
> Schritte in `docs/entwicklung-laptop.md` (inkl. „So starte ich das Tool
> künftig in zwei Befehlen"). Committe nichts aus `data/` und keine
> Zugangsdaten – prüfe, dass `.gitignore` das abdeckt.

Wenn Claude Code fertig ist: Tool im Browser öffnen, mit PIN 1234 anmelden,
kurz durchklicken. Dann die Liste der fehlenden Dateien abarbeiten (Schritt 3).

## Schritt 5 – Projektierung starten

`PLAN_PROJ_V1.md` und `PROJEKTIERUNG-KONZEPT.md` in den Ordner `friondo-tool`
kopieren, dann in Claude Code den Start-Prompt aus `PLAN_PROJ_V1.md` einfügen.

## Künftiger Alltag am Laptop

- Vor jeder Arbeitssitzung: `git pull` (holt Änderungen, die z. B. der
  Angebotstool-Chat über den PC zuhause eingespielt hat).
- Nach jeder abgenommenen Phase: Claude Code committet; `git push` erst, wenn
  der Plan komplett und getestet ist und der Rollout abgestimmt wurde.
- Rollout wie bisher: `update.bat` auf dem Terminal-Server.
- Der PC zuhause bleibt als Reserve; vor Arbeit dort ebenfalls `git pull`.
