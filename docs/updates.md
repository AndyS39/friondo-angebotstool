# Updates ausliefern: Entwicklungs-PC → GitHub → Server

Ablauf ab v5: Änderungen werden am Entwicklungs-PC committet und nach GitHub
gepusht; auf dem Terminal Server holt `update.bat` den neuen Stand, migriert
die Datenbank und startet den Dienst neu. `rollback.bat` nimmt ein Update
zurück.

## 1. Einmalige Einrichtung (GitHub, privates Repository)

**Stand 19.08.2026: Repository `https://github.com/AndyS39/friondo-angebotstool`
(privat) ist angelegt, der Entwicklungs-PC pusht dorthin (Schritte 1 und 2 erledigt).
Offen ist nur noch Schritt 3 auf dem Server:**

1. Auf https://github.com/new ein **privates** Repository anlegen, Name z. B.
   `friondo-angebotstool`, **ohne** README/.gitignore/Lizenz (leer lassen).
2. Am Entwicklungs-PC im Projektordner `C:\Users\Andreas\Documents\Claude\Angebotserstellungtool`:

   ```bat
   scripts\github-einrichten.bat https://github.com/AndyS39/friondo-angebotstool.git
   ```

   Das Skript setzt `origin`, pusht `master` und setzt den Upstream. Beim ersten
   Push öffnet der **Git Credential Manager** ein Browserfenster zur Anmeldung
   bei GitHub (einmalig; danach ist die Anmeldung gespeichert).
3. Auf dem **Server** einmalig als Administrator in `C:\Friondo\Angebotstool`:

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
Backups), `.env` (Tokens), `venv\`.

## 2. Jedes Update

Am Entwicklungs-PC (nach Commit):

```bat
git push
```

Auf dem Server als Administrator im Projektordner:

```bat
update.bat
```

`update.bat` macht der Reihe nach:

| Schritt | Was passiert | Bei Fehler |
|---|---|---|
| 1 | Dienst „Friondo Angebotstool“ stoppen | – |
| 2 | **Backup** von `data\*.db` und `.env` nach `data\backups\update_<JJJJ-MM-TT_HHMM>\` (Pfad wird angezeigt) | – |
| 3 | `git pull --ff-only` (prüft vorher, ob `origin` eingerichtet ist) | **alter Stand wird wieder gestartet**, nichts geändert |
| 4 | `pip install -r requirements.txt` | Tool bleibt **gestoppt**, Meldung mit Backup-Hinweis |
| 5 | `migrate.py` (nur wenn vorhanden; idempotent) | Tool bleibt **gestoppt**, Meldung mit Backup-Hinweis, kein „Fertig“ |
| 6 | Dienst starten, „Fertig“ + Backup-Pfad | – |

Am Ende und bei jedem Fehler wartet das Fenster mit `pause`, damit die
Meldung lesbar bleibt. Danach `http://localhost:8000` prüfen.

## 3. Rollback

Wenn nach einem Update etwas nicht stimmt (oder die Migration abgebrochen hat):

```bat
rollback.bat
```

- setzt den **Code** auf den Stand vor dem letzten `git pull` zurück
  (`ORIG_HEAD`),
- spielt **Datenbank und .env** aus dem jüngsten `data\backups\update_*`
  zurück (optional einen bestimmten Ordner als Parameter übergeben:
  `rollback.bat data\backups\update_2026-08-19_1622`),
- installiert die zum alten Stand passenden Abhängigkeiten und startet den
  Dienst.

**Achtung:** Alles, was nach dem Update erfasst wurde, geht mit dem Rollback
verloren – das Skript fragt deshalb vorher nach (j/n).

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
  mit der Meldung an die Entwicklung geben.

## 5. Versionsstand prüfen

Auf PC und Server zeigt `git log --oneline -1` den aktuellen Commit – stimmen
beide überein, ist der Server auf dem neuesten Stand.
