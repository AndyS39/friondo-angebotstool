# Updates ausliefern: Entwicklungs-PC → GitHub → Server

Ablauf ab v5: Änderungen werden am Entwicklungs-PC committet und nach GitHub
gepusht; auf dem Server holt `update.bat` den neuen Stand, migriert die
Datenbank und startet das Tool neu. `rollback.bat` nimmt ein Update zurück.
**Seit v27:** Updates nur im **Wartungsfenster** (Standard Dienstag 22:30–23:30
[ANNAHME]) mit vorher gesetztem Wartungsbanner; das Tool läuft als Dienst bzw.
Aufgabe (`update.bat`/`rollback.bat` erkennen den Weg), nach jedem Update läuft
der **Smoke-Test** `scripts\smoke.bat`, und `rollback.bat --nur-code` nimmt nur
den Code zurück (Datenbank bleibt). Das vollständige Runbook mit Reihenfolge,
Störungen und Ansprechpartnern steht in `docs/betrieb.md`.
**v28 + v29 (08.10.2026):** ein gemeinsames Update für den v27-Nachtrag 2 (Klima-Versand,
E-Mail-Vorlagen je Sparte, Anmeldeseite), Projektierung V6 (v28, Phasen 133–139) und
Lead-Management V4 (v29, Phasen 140–144) – EIN Commit. `migrate.py` legt nur additive
Spalten/Tabellen an (`termin_besetzung`, `aufgaben.entfaellt_grund`, `projekt_termine.zweck`,
`vorgaenge.email_status*`/`mail_fehler*`, `benutzer.vorname/infotext/bild_datei`,
`kommunikation_log.absender/versuche`) und führt die Datenmigrationen der Module aus
(Sparten-Vorlagen, Termin-Zweck/Besetzung, Notizen-Kopie, Lead-Parameter, Lead-Mails);
zweiter Lauf ohne Änderungen. Die Live-Excel-Dateien (`projektierung_logik_v1.xlsx` Blätter
Aufgabenpakete/Formulare/Stücklisten/Lesehilfe, `leadmanagement_logik_v1.xlsx` Blätter
Kaskade/Terminhinweise, `konfigurator_logik_v5.xlsx` Blatt Anhänge) und
`anlagen/Bosch Climate 3200i.pdf` kommen mit dem Pull. Nach dem Update:
`docs/nach-dem-update-v28.md` und `docs/nach-dem-update-v29.md`; neuer Scheduler-Lauf
`lead-mail-abruf` (14 Läufe, `/health`).

## 1. Einmalige Einrichtung (GitHub, privates Repository)

**Stand 20.08.2026: komplett eingerichtet** – Repository
`https://github.com/AndyS39/friondo-angebotstool` (privat), Entwicklungs-PC pusht,
Server ist per `git init` + `git checkout -f -B master origin/master` verbunden
(Dateikopie ohne `.git` nachträglich angebunden; Projektordner auf dem Server
heute `C:\Users\kdadmin\Desktop\Angebotstool`). Die Schritte hier nur zur
Dokumentation bzw. für eine Neuinstallation:

1. Auf https://github.com/new ein **privates** Repository anlegen, Name z. B.
   `friondo-angebotstool`, **ohne** README/.gitignore/Lizenz (leer lassen).
2. Am Entwicklungs-PC im Projektordner (heute fr-wts-02,
   `C:\Users\a.scheelen\Tools\Angebotstool`):

   ```bat
   scripts\github-einrichten.bat https://github.com/AndyS39/friondo-angebotstool.git
   ```

   Das Skript setzt `origin`, pusht `master` und setzt den Upstream. Beim ersten
   Push öffnet der **Git Credential Manager** ein Browserfenster zur Anmeldung
   bei GitHub (einmalig; danach ist die Anmeldung gespeichert).
3. Auf dem **Server** einmalig als Administrator im Projektordner:

   ```bat
   git remote add origin https://github.com/AndyS39/friondo-angebotstool.git
   git fetch origin
   git branch --set-upstream-to=origin/master master
   ```

   Auch hier fragt Git beim ersten `fetch` einmal nach der GitHub-Anmeldung
   (Browser oder Personal Access Token mit Recht „repo“; das Token wird im
   Windows-Anmeldeinformationsmanager gespeichert). Tipp: für den Server ein
   eigenes Token mit **nur Leserechten** (Fine-grained PAT, Contents: Read)
   anlegen.

Was **nie** auf GitHub landet (`.gitignore`): `data\` (Datenbank, PDFs,
Backups, Logs), `.env` (Tokens), `venv\`, `diagnose\`, `docs\betrieb\`
(Restore-Protokolle).

## 2. Jedes Update (im Wartungsfenster)

Vorher am Entwicklungs-PC (Rollout-Grundregel, Details `docs/betrieb.md`
Abschnitt „Update im Wartungsfenster“): aktuelle Server-DB-Kopie nach
`diagnose\`, `migrate.py --db` zweimal auf der Kopie, Voll-Crawl
(`scripts\voll_crawl.py`) + Abnahmeskript (`tests\abnahme.py`) grün, dann:

```bat
git push
```

Auf dem Server als Administrator im Projektordner (Banner vorher unter
Parametrierung → Betrieb → Wartungshinweis setzen, mindestens 30 Minuten
vor dem Fenster):

```bat
update.bat
```

`update.bat` macht der Reihe nach:

| Schritt | Was passiert | Bei Fehler |
|---|---|---|
| 0 | Hinweis auf Wartungsfenster und Banner (10 s, Abbruch mit Strg+C – keine Blockade) | – |
| 1 | Tool stoppen über `scripts\dienst-neustart.bat --stop`: Dienst `FriondoAngebotstool` (NSSM) → `net stop`; Aufgabe „Friondo Angebotstool“ → `schtasks /End`; sonst Konsolenfenster beenden. Setzt `data\log\wartung.marker` (Wächter greift nicht ein) | Abbruch, nichts geändert |
| 2 | **Backup** von `data\*.db` und `.env` nach `data\backups\update_<JJJJ-MM-TT_HHMM>\` (Pfad wird angezeigt) | – |
| 3 | `git pull --ff-only` (prüft vorher, ob `origin` eingerichtet ist) | **alter Stand wird wieder gestartet**, nichts geändert |
| 4 | `pip install -r requirements.txt` | Tool bleibt **gestoppt**, Meldung mit Backup-Hinweis |
| 5 | `migrate.py` (nur wenn vorhanden; idempotent) | Tool bleibt **gestoppt**, Meldung mit Backup-Hinweis, kein „Fertig“ |
| 6 | Tool starten (`--start`), `/health` abwarten (bis 45 s), Marker entfernen | Meldung, Hinweis `rollback.bat` |
| 7 | **Smoke-Test** `scripts\smoke.bat` (etwa 2 Minuten; Ergebnis als Tabelle, Protokoll `data\log\smoke-<Datum>.txt`) | Tool läuft mit neuem Stand, Hinweis `rollback.bat` / `rollback.bat --nur-code` |

Am Ende und bei jedem Fehler wartet das Fenster mit `pause`, damit die
Meldung lesbar bleibt. Danach `http://localhost:8000` prüfen und das
Wartungsbanner wieder entfernen (Parametrierung → Betrieb → „Hinweis
entfernen“). `update.bat --ohne-smoke` überspringt Schritt 7.

Läuft das Tool noch als Konsolenfenster (kein Dienst, keine Aufgabe), beendet
`update.bat` das Fenster und fragt am Ende, ob `start.bat` neu gestartet werden
soll – dauerhaft richtig ist aber `scripts\dienst-installieren.bat`
(`docs/installation-terminal-server.md`, Abschnitt 4).

## 3. Rollback

Wenn nach einem Update etwas nicht stimmt (Smoke-Test rot, Migration
abgebrochen, Fehler im Betrieb), gibt es zwei Wege:

```bat
rollback.bat --nur-code
```

- setzt nur den **Code** auf den Stand vor dem letzten `git pull` zurück
  (`ORIG_HEAD`), installiert die passenden Abhängigkeiten und startet das Tool;
- **Datenbank und `.env` bleiben** – seit v27 sind alle Datenbankänderungen
  additiv (neue Spalten/Tabellen/Indizes), der vorherige Code läuft auf der
  neueren Datenbank weiter, nichts geht verloren; deshalb keine Rückfrage;
- Sitzungs-Cookies der neuen Fassung weist der alte Code ab → alle Nutzer
  melden sich einmal neu an. Nach dem Rollback fehlen nur die neuen
  Zusatzfunktionen (z. B. Betriebs-Seite, Login-Protokoll, Wartungsbanner).

```bat
rollback.bat
```

- setzt den **Code** zurück (wie oben) **und** spielt **Datenbank und .env**
  aus dem jüngsten `data\backups\update_*` zurück (optional einen bestimmten
  Ordner als Parameter: `rollback.bat data\backups\update_2026-10-07_1830`),
- **Achtung:** Alles, was nach dem Update erfasst wurde, geht verloren – das
  Skript fragt deshalb vorher nach (j/n). Nur nötig, wenn die Datenbank selbst
  beschädigt wurde oder eine Migration halb durchgelaufen ist.

Beide Varianten erkennen Dienst/Aufgabe/Konsolenfenster wie `update.bat`.
Hinweis: `/health` gibt es erst ab v27 – nach einem Rollback auf einen Stand
davor meldet die Kontrolle „HTTP 404“ (normal). Nach dem Rollback
`scripts\smoke.bat` bzw. eine Sichtprüfung im Browser.

## 4. Typische Fehler

- **„Kein Git-Remote origin eingerichtet“** → Schritt 1.3 auf dem Server
  ausführen.
- **`git pull` meldet Konflikte / „not possible to fast-forward“** → auf dem
  Server wurde am Code manuell geändert. Änderungen verwerfen mit
  `git reset --hard origin/master` (Daten in `data\` sind davon nicht
  betroffen), dann `update.bat` erneut.
- **Anmeldung schlägt fehl** → Token abgelaufen: im Windows-Anmeldeinformationsmanager
  den Eintrag `git:https://github.com` löschen, `update.bat` erneut starten und
  neu anmelden.
- **Migration fehlgeschlagen** → Meldung lesen; Backup liegt unter dem
  angezeigten Pfad; `rollback.bat` stellt den Vorzustand her. Fehler bitte
  mit der Meldung an die Entwicklung geben. Solange `data\log\wartung.marker`
  liegt, startet der Wächter nichts neu.
- **Stoppen fehlgeschlagen / Port 8000 bleibt belegt** → ein anderer Prozess
  hält den Port (z. B. Konsolenfenster in einer anderen Sitzung):
  `scripts\dienst-status.bat` zeigt die PID, im Task-Manager beenden, dann
  `update.bat` erneut.
- **Smoke-Test rot** → Protokoll `data\log\smoke-<Datum>.txt` lesen (welche
  Seite, HTTP-Status, Zeit). 303 auf `/login` = Anmeldung defekt; „zu langsam“
  kurz nach dem Start einmal wiederholen (`scripts\smoke.bat`); bleibt es rot
  → `rollback.bat --nur-code`.
- **`/health` nach dem Start `fehler` (HTTP 503)** → Datenbank nicht
  erreichbar: `data\fehler.log` und `data\log\dienst-err.log` lesen, Pfad
  `data\angebotstool.db` und Rechte des Dienstkontos prüfen.

## 5. Versionsstand prüfen

Auf PC und Server zeigt `git log --oneline -1` den aktuellen Commit; auf dem
Server zusätzlich `http://192.168.35.4:8000/health` (Felder `version` und
`commit`) oder Parametrierung → Betrieb – stimmen beide überein, ist der
Server auf dem neuesten Stand.
