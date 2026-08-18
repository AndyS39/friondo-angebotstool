# Nach dem Update auf v5 – Checkliste (Phasen 29–34)

Diese Punkte sind **einmalig nach dem Rollout** zu erledigen, teils durch die
IT/M365-Admin, teils durch den Innendienst in der Parametrierung. Reihenfolge
einhalten – ①/② sind Voraussetzung für den Versand mit Absender angebot@.

## ① M365-Admin: „Senden als“ für angebot@friondo.de

Exchange Admin Center → Empfänger → Postfächer → **angebot@friondo.de**
(freigegebenes Postfach, ggf. neu anlegen) → **Postfachdelegierung**:
für **jeden Innendienst-Mitarbeiter** die Rechte **„Senden als“** und
**„Lesen und Verwalten (Vollzugriff)“** vergeben. Greift nach bis zu 60 Min.
Details: `docs/graph-einrichtung.md`, Abschnitt 3a.

## ② IT: Graph-Berechtigungen erweitern + Admin-Zustimmung erneuern

App-Registrierung „Friondo Angebotstool“ → API-Berechtigungen → delegiert
ergänzen: `Mail.Send`, `Mail.ReadWrite.Shared`, `Mail.Send.Shared`
(zusätzlich zu `Mail.ReadWrite`, `Mail.Read`) → **„Administratorzustimmung
für Friondo erteilen“**. Danach im Tool: **Versand → Abmelden → erneut mit
Microsoft anmelden**, damit das Token die neuen Berechtigungen enthält.

## ③ Parametrierung prüfen (Innendienst/Admin)

- **Parametrierung → E-Mail-Versand:** Absender `angebot@friondo.de`,
  Abgleich-Postfach `angebot@friondo.de`, **BCC-Adresse prüfen** (Vorbelegung
  `info@friondo.de`; leer = kein BCC).
- **Parametrierung → monday-Anbindung → Rückspielung:** je Quell-Board Modus
  wählen (Status-Spaltenwert „Angebot versendet“ **oder** Verschieben in die
  Gruppe „Angebot versendet“), Deal-Wert-Spalte (z. B. „Deal-Wert (WP)“) und
  brutto/netto zuweisen. Standard ist **aus** – erst nach bewusster Wahl aktiv.
- **Parametrierung → monday-Anbindung → Spalten-Mapping:** je Board das neue
  Feld **interesse** auf die Spalte „Interessen“ mappen (Board Deals:
  `dropdown_mkyps596`); danach „Jetzt aktualisieren“ in Leads VOT.
- Voraussetzung für beides: `MONDAY_API_TOKEN` in der `.env` auf dem Server.

## ④ E-Mail-Adressen der Benutzer eintragen (Admin)

**Benutzer** → bei jedem Außendienstler die E-Mail hinterlegen (Pflichtfeld für
die Rolle Außendienst) – sie wird beim Versand automatisch als **CC** gesetzt.
Fehlt sie, geht der Entwurf ohne CC raus und das Tool zeigt einen Hinweis.
Bei der Gelegenheit: nicht mehr benötigte Testbenutzer löschen bzw.
deaktivieren.

## ⑤ Vorlagentexte je Außendienstler hinterlegen (Innendienst/Admin)

**Parametrierung → E-Mail-Vorlagen:** Standard-Vorlage prüfen (der bisherige
Festtext ist bereits migriert) und bei Bedarf je Außendienstler eine eigene
Vorlage anlegen (Platzhalter siehe Liste auf der Seite, Vorschau anhand eines
echten Angebots).

## ⑥ Testversand

1. Testangebot an eine **eigene Testadresse** → „Versand vorbereiten“:
   Entwurf in Outlook prüfen – Absender angebot@friondo.de, CC = AD, BCC –
   und senden.
2. Nach spätestens 15 Minuten (oder Server-Neustart) muss der Status
   automatisch auf **„Versendet“** springen; die monday-Rückspielung
   (falls aktiviert) schreibt Status/Deal-Wert an den Test-Deal.
3. Auf die Testmail antworten → in der Angebotsliste erscheint das
   Brief-Symbol mit Zähler, Klick zeigt den Verlauf.
4. Test-Deal in monday zurücksetzen, Testangebot archivieren oder löschen.

---

## Rollout: Entwicklungs-PC → Server

Die Auslieferung läuft über **git push** (Entwicklungs-PC) und **update.bat**
(Server: Dienst stoppen → `git pull` → `pip install` → `migrate.py` → Dienst
starten). Dafür brauchen beide Seiten ein gemeinsames Git-Remote – **das ist
noch nicht eingerichtet** (Stand 18.08.2026: kein `origin` konfiguriert).
Zwei Varianten:

**Variante A – Bare-Repository auf dem Fileserver (ohne Internetdienst):**

Am Entwicklungs-PC (Pfad zur Freigabe anpassen):

```bat
git init --bare "\\FR-WFS-01\Daten\Friondo\Friondo GmbH\Tools\Angebotstool.git"
git remote add origin "\\FR-WFS-01\Daten\Friondo\Friondo GmbH\Tools\Angebotstool.git"
git push -u origin master
```

Auf dem Server einmalig im Projektordner `C:\Friondo\Angebotstool`:

```bat
git remote add origin "\\FR-WFS-01\Daten\Friondo\Friondo GmbH\Tools\Angebotstool.git"
git fetch origin
git branch --set-upstream-to=origin/master master
```

**Variante B – GitHub/Azure DevOps (privates Repository):** Repository anlegen,
`git remote add origin <URL>` auf beiden Seiten, `git push -u origin master`
am PC; auf dem Server muss dann Git mit Zugangsdaten (PAT) eingerichtet sein.

**Danach bei jedem Update:** am PC `git push`, auf dem Server als Administrator
im Projektordner:

```bat
update.bat
```

`update.bat` prüft, ob ein Remote eingerichtet ist, führt `migrate.py`
automatisch aus (idempotent, mehrfach ausführbar) und startet den Dienst neu.
Vor dem ersten v5-Update auf dem Server ist ein Backup von `data\` sinnvoll –
das Tagesbackup nach `data\backups\` legt der App-Start ohnehin an.

**Übergangsweise ohne Git-Remote:** Projektordner (ohne `venv\` und `data\`)
per robocopy auf den Server kopieren und dort im Projektordner ausführen:

```bat
venv\Scripts\python migrate.py
```

anschließend den Dienst neu starten (`schtasks /End` + `schtasks /Run /TN "Friondo Angebotstool"`).
