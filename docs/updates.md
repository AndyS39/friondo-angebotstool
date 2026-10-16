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
**v30 (PLAN_V18, Phasen 145–152):** Design v2 mit Hell/Dunkel (Umschalter im Menü,
Standard „Gerät entscheidet“), Zurück-Knopf auf Detailseiten, BzA-Datenblatt ohne A20 und
ohne Abschnitt „Ersteller“ (neue Puffer-Zeile), Lieferschein mit Langtexten und abhängigen
Positionen, Zahlungsbedingungen je Angebot, „Projekt löschen“ (Admin) für den Go-live der
Projektierung. `migrate.py` legt nur additive Dinge an (Tabelle `zahlungsbedingungen` mit
drei Einträgen, Spalten `angebote.zahlungsbedingung_key/_text`,
`angebots_loeschungen.art/grund`, Parameter `bza_kosten_puffer_prozent` und
`lieferschein_folgepositionen`) und ersetzt in den Nachtext-Blöcken den festen
Zahlungsabsatz durch den Platzhalter `{zahlungsbedingungen}` – Blöcke, in denen der Absatz
nicht wörtlich stand, meldet der Lauf (Platzhalter dort von Hand nachtragen). Die
Live-Excel `konfigurator_logik_v5.xlsx` kommt ohne die Frage A20 mit dem Pull. Keine neuen
Scheduler-Läufe. Vorher am Entwicklungs-PC: Voll-Crawl **je einmal hell und dunkel**
(`scripts\voll_crawl.py … --darstellung hell` bzw. `dunkel`). Nach dem Update:
`docs/nach-dem-update-v30.md` (Team: Darstellung wählen, Zurück-Knopf, Zahlungsbedingung im
Editor; Admin: Demo-Projekte löschen, Go-live-Schalter `freigabe_modus = alle`).

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
- **`git pull` bricht ab mit „Your local changes to the following files would be
  overwritten by merge“** (erlebt beim Update 08.10.2026 mit
  `projektierung_logik_v1.xlsx`) → das Tool hat eine versionierte Live-Excel auf dem
  Server verändert (Parametrierungs-Editoren schreiben in die Datei). Vorgehen: Tool ist
  bereits gestoppt; die genannte Datei nach `data\backups\excel-vor-<Version>\` kopieren,
  dann `git checkout -- <datei>` und `update.bat` erneut starten (Schritt 3 läuft dann
  durch; die Sicherung bleibt für den Vergleich). Vor jedem Update lohnt ein kurzes
  `git status` im Projektordner.
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

## 4a. Besonderheiten beim Update auf v31 + v32 (ein Commit, 13.10.2026)

- `migrate.py` meldet beim ersten Lauf u. a.: Hauptobjekte je Vorgang (`vorgang_objekte`), Trigger
  `trg_v31_vorgang_objekte`, Leadmanager-Häkchen (nicht gefundene Startnamen als Meldung),
  `lead_freigabe_modus = alle`, Vorlagen `terminbestaetigung_objekte`/`falsche_telefonnummer`, ggf.
  „v31: Vorlage …: WP → Wärmepumpe“ (Kürzel ersetzt), „Ablehnungsgründe (v32)“ (angelegt/deaktiviert),
  „Verfolgungsstatus (v32)“, Indizes `ix_v32_kunden_*`. Der zweite Lauf meldet „keine Änderungen nötig“.
- Danach `scripts\smoke.bat` wie immer; zusätzlich einmal `venv\Scripts\python scripts\vot_abgleich.py
  --data <DB-Kopie unter diagnose\> --bericht diagnose\vot_abgleich.txt` (Bericht lesen; Reparatur
  `--anlegen` nur gegen die Kopie, der Sync hält die Termine ab jetzt selbst nach).
- Admin-To-dos aus `docs/nach-dem-update-v31.md`/`-v32.md`: Demo-Ende-Abfrage in den Lead-Einstellungen,
  Leadmanager-Häkchen und HV-Gruppen prüfen, Ablehnungsgründe-Liste prüfen, Freischaltung
  (`terminierung_aktiv`/`mail_versand_aktiv`) erst nach grünen Prüfpunkten.
- Rückweg: `rollback.bat --nur-code` (v30-Code läuft auf der v32-Datenbank – nur additive Änderungen).

## 4b. Besonderheiten beim Update auf v33 (ein Commit, 14.10.2026)

- `.env` auf dem Server um die vier Schlüssel aus `.env.example` ergänzen (`GRAPH_CLIENT_SECRET`,
  `GRAPH_ZERTIFIKAT_PFAD`, `GRAPH_ZERTIFIKAT_THUMBPRINT`, `GRAPH_GEHEIMNIS_ABLAUF`) – zunächst LEER lassen:
  ohne Geheimnis läuft das Tool im Modus „delegiert“ genau wie v32 weiter. Das Geheimnis kommt erst, wenn die
  IT die Entra-/Exchange-Schritte aus `docs/graph-einrichtung.md` erledigt hat; danach Versand → „Verbindung
  testen“ (grün → Modus „anwendung“).
- `migrate.py` meldet beim ersten Lauf u. a.: „Rollen (v33): … Rollen angelegt“, „Handelsvertreter-Rolle gesetzt
  für …“, „Teams (v33): Gewerk gesetzt – n Elektro, m Heizung“, Graph-Modus `delegiert`, Outlook-Tabellen
  (`outlook_ereignisse`, `outlook_auftraege`, `outlook_belegt`), Service-Parameter (`phase_auto`), Einwände
  (vier Startwerte), Spalten/Indizes `ix_v33_*`. Der zweite Lauf meldet „keine Änderungen nötig“.
  Mit dem Nachtrag 15.10.2026 zusätzlich beim ersten Lauf: „Angebotsprofil SWD (v33): Kanalwerte … gesetzt“
  (nur, wenn das SWD-Profil keine Kanalwerte hatte).
- Nachtrag 15.10.2026: nach dem grünen Verbindungstest (Modus „anwendung“) einmalig
  `venv\Scripts\python scripts\outlook_bestand_einreihen.py --wochen 8` (vorher `--trocken` zum Zählen) –
  reiht die Bestandstermine als persönliche Outlook-Kopien ein; Fotos werden seit dem Nachtrag vor dem Upload
  auf dem Gerät verkleinert (keine Server-Einstellung nötig).
- Danach `scripts\smoke.bat` wie immer. Neue Hintergrundläufe `outlook-sync`/`outlook-ruecklesen` stehen in
  Parametrierung → Betrieb (aktiv erst im Modus „anwendung“ bzw. mit Kalender-Freigabe).
- Admin-To-dos aus `docs/nach-dem-update-v33.md`: Rollen/Teams prüfen (René Golaschewski und Simon O Grady
  als Handelsvertreter; Gewerk je Team), Kalender-Parameter, Häkchen „Phasen automatisch weiterschalten“,
  Servicebericht-Feldliste, Einwand-Liste und Nachfass-Vorlagen gegenlesen, Graph-Verbindungstest nach der
  Einrichtung.
- Rückweg: `rollback.bat --nur-code` (v32-Code läuft auf der v33-Datenbank – nur additive Änderungen;
  Rückweg-Probe im Durchlauf: `diagnose/test_v33_final/rueckweg_probe.txt`).
- `migrate.py` druckt seine Meldungen seit v33 auch auf der cp1252-Konsole des Servers ohne Abbruch
  (Zeichen außerhalb des Zeichensatzes werden ersetzt) – ein Abbruch NACH den Commits durch eine Meldung mit
  Sonderzeichen ist damit ausgeschlossen (Befund im Durchlauf, Probe mit `PYTHONIOENCODING=cp1252`).

## 4c. Besonderheiten beim Update auf v34 (ein Commit, 15.10.2026)

- Die Wallbox-Preisliste `Artikel-Preislisten\Wallbox\WB Angebot Excel 1.xlsx` (TAIFUN-Export mit EK) kommt
  mit dem Update aus Git; `migrate.py` importiert sie automatisch (Meldungen „WB-Artikel fehlten (…) –
  Wallbox-Positionslisten-Import ausgeführt (WB: 8 neu …)“ und „WB-Vortext: Absatz „Komplettpaket Wallbox
  inkl. Montage“ aus der Wallbox-Excel übernommen“). Spätere Preisänderungen über Parametrierung → Logik &
  Importe → „Wallbox-Positionslisten importieren“.
- `migrate.py` meldet beim ersten Lauf u. a.: Spalten `angebote.wb_json`, `angebote.auslegung_text`,
  `angebotspositionen.uebernommen_von_angebot_id/_position_id`; „Auslegung (v34): n Entwürfe bereinigt“
  (je Angebot eine Zeile – die 0,00-€-Auslegungs-Position wandert in das interne Feld); Textblöcke
  „Friondo WB …“ (seed_wb); Wallbox-Import (siehe oben). Der zweite Lauf meldet „keine Änderungen
  nötig“.
- Neue Abhängigkeit `pypdf` – `update.bat` führt `pip install -r requirements.txt` aus; danach prüfen:
  `venv\Scripts\python -c "import pypdf"`.
- Danach `scripts\smoke.bat` wie immer. Keine neuen Hintergrundläufe (16 wie v33).
- Mennekes-Datenblatt (`anlagen\Mennekes AMTRON 4You Datenblatt.pdf`) nachreichen; die Betriebs-Seite meldet
  die fehlende Anhang-Datei. Das Musterangebot AN251131 liegt nur lokal (`Beispielangebot.pdf`, gitignored).
- Rückweg: `rollback.bat --nur-code` (v33-Code läuft auf der v34-Datenbank – nur additive Änderungen;
  Rückweg-Probe im Durchlauf: `diagnose/test_v34_final/rueckweg_probe.txt`).
- Admin-To-dos und Team-Hinweise: `docs/nach-dem-update-v34.md` (Login-Probe mit dem Handy, Liste
  „gewerkeübergreifende Artikel“, Sparten-Mail-Vorlagen gegenlesen, HTTPS-Entscheidung).

## 4d. Besonderheiten beim Update auf v35 (ein Commit, 16.10.2026)

- Neue Abhängigkeiten `lxml`, `Pillow`, `pillow-heif` – `update.bat` führt `pip install -r requirements.txt` aus
  (binäre Wheels, kein Compiler nötig); danach prüfen: `venv\Scripts\python -c "import lxml, PIL, pillow_heif"`.
  Ohne `lxml` scheitert jede TAIFUN-Übergabe an der Validierung, ohne `pillow_heif` bleiben HEIC-Fotos liegen.
- `migrate.py` meldet beim ersten Lauf: Tabellen `taifun_uebergaben`, `vertriebskanaele`; Spalten
  `vorgaenge.taifun_export_*`, `kunden.taifun_kundennr`, `galerie_dateien.objekt_id` (+ Index); Lead-Parameter
  `taifun_*` (Schalter AUS); „Kanaele (v35): 30 Vertriebskanaele aus der Liste angelegt“, Zuordnungen alter
  Schreibweisen („'SWD' -> 'Stadtwerke Düsseldorf'“ …) und je Bestandswert außerhalb der Liste „als inaktiver
  Kanal angelegt“ – diese Zeilen notieren; „Objektfotos (v35)“ nur, wenn Objekt-Ordner im Bestand liegen. Der
  zweite Lauf meldet „keine Änderungen nötig“.
- Die TAIFUN-Übergabe bleibt nach dem Update AUS (Parameter `taifun_export_aktiv`); Einschalten erst nach den
  Prüfpunkten in `docs/nach-dem-update-v35.md` (Ordner für das Dienstkonto SYSTEM, Testdatei in TAIFUN importiert,
  Encoding bestätigt).
- Danach `scripts\smoke.bat` wie immer; `/health` zeigt **17 Läufe** (neu `taifun-uebergaben`).
- Rückweg: `rollback.bat --nur-code` (v34-Code läuft auf der v35-Datenbank – nur additive Änderungen; Rückweg-Probe
  im Durchlauf: `diagnose/test_v35_final/rueckweg_probe.txt`).
- Admin-To-dos und Team-Hinweise: `docs/nach-dem-update-v35.md` (TAIFUN-Ordner und Testdatei, Kanäle prüfen,
  HV-Gruppen-Parameter, Profilbilder).

## 4e. Besonderheiten beim Update auf v36 (ein Commit, 16.10.2026)

- Neue Abhängigkeiten `playwright` (Browser-Druck des Angebots-PDFs) und `qrcode` (QR-Code des Cloover-Links) –
  `update.bat` führt `pip install -r requirements.txt` aus und lädt Playwright-Chromium **nur**, wenn weder Edge noch
  `PDF_BROWSER_PFAD` in der `.env` vorhanden sind (braucht Internet); auf dem Server wird Edge erwartet (Kanal
  `msedge`). Danach prüfen: `venv\Scripts\python -c "import playwright, qrcode"` und
  `scripts\pdf-browser-pruefen.bat` (findet Edge/Chrome, druckt ein Test-PDF, meldet Dauer; unter dem Dienstkonto
  SYSTEM z. B. per `psexec -s` – Ergebnis in `docs/nach-dem-update-v36.md` Teil A nachtragen).
- `migrate.py` meldet beim ersten Lauf: „Angebots-PDF: Browser-Test ok (msedge …) – Engine html (Layout v3) angelegt“
  **oder** „Browser-Druck nicht verfügbar (…) – Engine auf fpdf2 gestellt“ (dann weiter das alte Layout, Parametrierung →
  Angebots-PDF zeigt den Grund); „v36: Vortext „Friondo PV|KL|WB Standard“ auf den Design-Wortlaut gesetzt – bisherige
  Fassung als „… (bis v35)“ erhalten“; „v36: Nachtext „Friondo Standard|PV Standard“: Raten-Absatz -> [CLOOVER] …“,
  „… KL Standard: [CLOOVER] vor „So bleibt Ihr Budget flexibel …“ eingefügt“, „… WB Standard: Nachtext A … vorangestellt“;
  Spalten `angebote.cloover_json`, `benutzer.cloover_email`, Tabelle `cloover_pdf_tokens`; Einstellungen `pdf_engine`,
  `pdf_letzter_test`, `cloover_*`. Der zweite Lauf meldet „keine Änderungen nötig“.
- Cloover bleibt nach dem Update **aus**, solange `CLOOVER_API_KEY` in der `.env` fehlt (keine Raten, keine Projekte);
  Einschalten erst nach den Prüfpunkten in `docs/nach-dem-update-v36.md` Teil B (Key, Modus test, Verbindungstest,
  PDF-Ablage, Echtlauf).
- Danach `scripts\smoke.bat` wie immer (Angebots-PDF jetzt über den Browser, Zielwert < 3 s warm); `/health` zeigt
  **18 Läufe** (neu `cloover-status`, ohne Key „inaktiv“) und die Felder `pdf_engine`/`pdf_browser`.
- Rückweg: `rollback.bat --nur-code` (v35-Code läuft auf der v36-Datenbank – nur additive Änderungen; Rückweg-Probe
  in der Rollout-Prüfung der Plan-Kette v36–v38). Nach einem Rückweg drucken Angebote wieder mit fpdf2; die Nachtexte
  tragen dann den Platzhalter `[CLOOVER]` als Text – vor einem längeren Rückweg die Textblöcke „Friondo Standard/PV/KL/WB
  Standard“ aus der Historie zurückstellen.
- Admin-To-dos und Team-Hinweise: `docs/nach-dem-update-v36.md` (Edge auf dem Server, `pdf_engine`, Titelbilder/Teamfoto,
  Cloover-Key/-Modus, Verbindungstest, PDF-Ablage, Fußnote/Datenschutzsatz).

## 4f. Besonderheiten beim Update auf v37 (ein Commit, 16.10.2026)

- Keine neuen Abhängigkeiten, keine neuen Hintergrundläufe (weiter 18). Neuer `.env`-Schlüssel `ORS_API_KEY`
  (openrouteservice, Konto account.heigit.org) – ohne Key bleibt das Routing „geschätzt“ (Luftlinie × 1,3), nichts
  bricht; nach dem Eintragen Dienst neu starten und in den Lead-Einstellungen den Prüfpunkt „Routing-Dienst
  antwortet“ ausführen (die Migration stellt `routing_anbieter` auf „ors“, sobald der Key da ist).
- `migrate.py` meldet beim ersten Lauf: Spalten `vot_termine.monday_beginn/angepasst_am/angepasst_von`; „Kanaele
  (v37): 'WELOVEX' deaktiviert …“ und „… 'DAA' deaktiviert …“ (dazu je Treffer „Hinweis - '<Kanal>' steht im Parameter
  hv_ausschluss/kanal_ad_regel (nicht geaendert, bitte pruefen)“ – diese Zeilen notieren), „Routing (v37):
  routing_kontingent_tag = 2000 angelegt“ bzw. „ORS_API_KEY fehlt - Anbieter bleibt luftlinie“. Der zweite Lauf meldet
  „keine Änderungen nötig“.
- Design v3 gilt nur im Lead-Modul (eigene Tokens, Hell/Dunkel); Browser laden die neuen Stylesheets über die
  `?v=`-Nummer automatisch nach. Die Design-Zulieferung (`Friondo Tool Design.html`) lag nicht vor – gebaut nach den
  Startwerten des Plans; Abweichungen später per CSS-Tokens nachziehen.
- Danach `scripts\smoke.bat` wie immer; `/health` zeigt `version` v37 und **18 Läufe**.
- Rückweg: `rollback.bat --nur-code` (v36-Code läuft auf der v37-Datenbank – nur additive Änderungen; Rückweg-Probe
  in der Rollout-Prüfung der Plan-Kette v36–v38).
- Admin-To-dos und Team-Hinweise: `docs/nach-dem-update-v37.md` (ORS-Key und Kontingent, Kanäle WeLoveX/DAA,
  Termine anpassen, Plus bei Interessen, Login-Vorbelegung, Design v3).

## 5. Versionsstand prüfen

Auf PC und Server zeigt `git log --oneline -1` den aktuellen Commit; auf dem
Server zusätzlich `http://192.168.35.4:8000/health` (Felder `version` und
`commit`) oder Parametrierung → Betrieb – stimmen beide überein, ist der
Server auf dem neuesten Stand.
