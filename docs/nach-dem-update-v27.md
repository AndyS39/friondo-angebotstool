# Nach dem Update v27 (PLAN_V17) – Betriebsreife für 50 Nutzer

Dieses Update macht das Tool für 50 gleichzeitige Nutzer betriebsfest: alle Seiten
laufen im Threadpool, Hintergrundläufe haben einen gemeinsamen Rahmen mit Status,
die Datenbank wird nachts gepflegt und gesichert (mit Spiegelung auf ein Backup-Ziel),
der Server läuft als Dienst mit Wächter, es gibt `GET /health`, eine Betriebs-Seite,
ein Wartungsbanner, eine gehärtete Anmeldung (PIN-Regeln, Sperre, Ablauf) und ein
Lasttest-Skript. Fachlich (Angebote, Leads, Projektierung, PDFs) ändert sich nichts.

**Rollout nur im Wartungsfenster** (Dienstag 22:30–23:30) nach der Reihenfolge
in `docs/betrieb.md` → „Update im Wartungsfenster“; nach `update.bat` läuft
`scripts\smoke.bat`.

## Für das Team (alle Rollen)

- **Einmal neu anmelden:** Die Sitzungs-Cookies der alten Fassung gelten nicht mehr.
- **Neue PIN-Regeln:** Neue PINs haben mindestens 4 Ziffern (Einstellung, Entscheidung Andreas
  07.10.2026) und dürfen keine Zahlenfolgen
  (123456, 654321), keine Wiederholungen (111111) und keine Jahreszahlen (1985…, 2024…)
  enthalten. Bestehende PINs bleiben gültig – niemand muss sich nach dem Update neu
  einrichten.
- **Erster Login mit Start-PIN:** Neue Benutzer (und Benutzer nach einem PIN-Reset durch
  den Admin) melden sich mit der Start-PIN an und müssen sofort eine eigene PIN vergeben –
  bis dahin ist keine andere Seite erreichbar. Die eigene PIN lässt sich jederzeit über
  Menü → „PIN ändern“ (`/pin-wechsel`) ändern (aktuelle PIN + neue PIN zweimal).
- **„Auf diesem Gerät angemeldet bleiben“:** Das Häkchen auf der Anmeldeseite hält
  Außendienst und Montage 30 Tage angemeldet (Handy/Tablet). Büro-Rollen bleiben – auch
  mit Häkchen – 12 Stunden angemeldet. Nur auf eigenen Geräten setzen. *Seit dem
  Nachtrag 2 (Update v28/v29) ist die Anmeldeseite zweispaltig mit Foto, und Büro-Rollen
  sehen das Häkchen nicht mehr.*
- **Sperre nach Fehlversuchen:** Nach 5 falschen PINs innerhalb von 15 Minuten ist der
  Benutzer 15 Minuten gesperrt („Zu viele Fehlversuche – bitte in 15 Minuten erneut
  versuchen oder den Admin um eine neue PIN bitten.“). Der Admin kann die Sperre sofort
  aufheben. Von einem Gerät sind höchstens 30 Fehlversuche je 15 Minuten möglich.
- **Wartungsbanner:** Vor einem Update erscheint oben auf jeder Seite „Wartung heute von
  <von> bis <bis> Uhr – bitte Arbeit bis dahin speichern. Das Tool ist in dieser Zeit
  kurz nicht erreichbar.“ – bitte ernst nehmen und Formulare vorher abschicken.
- **Meldung bei Überlast:** „Datenbank-Verbindungen ausgelastet – bitte in einer Minute
  erneut versuchen (Fehler-Nr. …)“ bzw. „Datenbank kurz belegt …“ sind keine Datenverluste:
  kurz warten und die Aktion wiederholen.
- **Hintergrundarbeiten** (monday-Abgleich, Mail-Abgleich, Lead-Mails, Geokodierung,
  Glocken, Löschlauf) laufen wie bisher automatisch; sie schreiben jetzt in kleinen
  Blöcken, damit Speichern-Aktionen anderer Nutzer nicht mehr auf einen langen Lauf warten.
- **Sofort-Mails der Glocke** (Benutzerprofil „sofort“) gehen in eine Warteschlange und
  werden innerhalb einer Minute versendet – nicht mehr im Moment des Klicks.
- **Adressen, die beim Geokodieren fehlschlagen,** werden automatisch erneut versucht
  (nach 1 Stunde, dann 6, dann täglich). „Adresse prüfen“ mit manuellem Pin bleibt der
  schnellste Weg und setzt den Zähler zurück.
- **Leads VOT → „Jetzt aktualisieren“** (monday-Vollabgleich) fragt vorher nach
  (Hinweis „Dauer etwa <n> s …“) und erscheint währenddessen als laufender Import im
  Betriebsstatus; Hinweise des Laufs stehen in der Meldung nach dem Klick.

## Für den Innendienst (Importe)

Vor jedem Import – Preisliste, PV-Positionslisten, Klima-Positionslisten, „Parametrierung
neu einlesen“ und Bestandsimport – zeigt die Seite den Hinweis „Dauer etwa <n> s –
während des Imports können Speichern-Aktionen anderer Nutzer kurz warten; empfohlen
außerhalb der Kernzeit“. Der Import startet erst nach dem Häkchen „Hinweis gelesen“
(Vorschau-Seiten) bzw. nach der Rückfrage des Knopfs (Logik & Importe, Klima-Logik).
<n> ist die Dauer des letzten Laufs; vor dem ersten Lauf gelten Richtwerte (Preisliste
20 s, PV 10 s, Klima 10 s, Logik 15 s, Bestand 30 s). Ein abgebrochener Import richtet
keinen Schaden an: einfach erneut starten – bereits übernommene Zeilen werden nur
aktualisiert, nichts wird doppelt angelegt. Abgebrochene Bestandsimporte stehen im
Importprotokoll als „abgebrochen (Teilstand)“ und können wie bisher rückgängig gemacht
oder erneut importiert werden.

## Für Admins

- **Parametrierung → Betrieb** (neu, nur Admin): Status (ok/warn/fehler mit Gründen),
  Version/Commit, Uptime, Pool (aktuell/Spitze 24 h), Threads, WAL-Größe mit
  „SQLite-Pflege jetzt“, letztes Backup mit Ziel und „Backup jetzt“, Prozess (RAM/CPU),
  laufende Importe, **Wartungshinweis** (Banner setzen/entfernen, Vorschlag = nächstes
  Dienstag-Fenster), **Scheduler-Tabelle** aller Hintergrundläufe (Intervall, letzter
  Start, Dauer, Läufe/Fehler, Zustand, letztes Ergebnis, Knopf „jetzt ausführen“ – läuft
  im Hintergrund, Seite danach neu laden), **Zugriffe der letzten 24 h** (Anfragen/Minute,
  Anteil über 2 s, p50/p95 je Route Top 20, langsamste 20 Anfragen, Pool-Spitze).
- **Fehlerprotokoll:** unverändert; Pool-Status steht in jedem Eintrag; die Pool-Größe
  ist jetzt 20 + 70 Überlauf (Timeout 10 s).
- **Benutzerverwaltung:** Filter nach Rolle und aktiv/inaktiv, Spalte „Letzter Login“ mit
  Hinweisen „gesperrt bis …“ (Knopf „Sperre aufheben“) und „PIN-Wechsel offen“. Beim
  Anlegen und beim PIN-Reset gelten die neuen PIN-Regeln; das Häkchen „PIN-Wechsel beim
  nächsten Login verlangen“ ist vorbelegt. In den Details: „Alle Sitzungen beenden“ meldet
  einen Benutzer auf allen Geräten ab (z. B. Handy verloren).
- **Sitzung & PIN-Regeln** (unten auf der Benutzerseite): Sitzungsdauer Büro (Stunden)
  und mobil (Tage), Mindestlänge neuer PINs (4–12), Sperrliste zu einfacher PINs.
- **CSV-Import** (Benutzer → CSV-Import): Datei mit `Name;Rolle;E-Mail;Team;Vertriebskanal`
  hochladen (Vorlage herunterladbar), Vorschau prüfen (alle Zeilen müssen grün sein),
  „Benutzer jetzt anlegen“. Die Start-PIN-Liste erscheint genau einmal – sofort drucken
  oder sicher weitergeben; sie wird nirgends gespeichert. Jeder importierte Benutzer muss
  beim ersten Login eine eigene PIN vergeben.
- **Login-Protokoll** (Parametrierung → System & Protokolle, oder Benutzerseite): letzte
  500 Versuche, Filter Benutzer / nur Fehlversuche, Zähler der letzten 24 h, aktuell
  gesperrte Benutzer mit „Sperre aufheben“. Aufbewahrung 90 Tage (Scheduler 03:10).
- **Import-Dauern:** Die Dauer des letzten Laufs steht in den Einstellungen
  `import_dauer_preisliste`, `import_dauer_pv`, `import_dauer_klima`, `import_dauer_logik`,
  `import_dauer_bestand` (Sekunden); wird ein Eintrag gelöscht, gilt wieder der Richtwert.
- **Admin-Glocke:** Steht `/health` auf `warn` (Pool > 70 %, ein Lauf überfällig, letztes
  Backup älter als 26 h, kein Backup-Ziel, Spiegelung fehlgeschlagen, mehr als 50 offene
  Sofort-Mails), bekommen alle Admins höchstens einmal je Stunde eine Glocke
  „Betriebswarnung: …“ mit Link auf die Betriebs-Seite.
- **Scheduler-Tabelle:** je Lauf letzter Start, Dauer, Ergebnis (z. B. `ok=3, fehler=0,
  backoff=2`), letzter Fehler, Zähler, „jetzt ausführen“. Teilschritt-Fehler stehen im
  Ergebnis als `fehler=<Anzahl>, hinweis=<erster Fehler>`; der Lauf gilt erst als
  fehlgeschlagen, wenn alle Teilschritte scheitern. Läufe ohne Voraussetzung (kein
  monday-Token, Graph nicht eingerichtet, Parser aus) stehen als „inaktiv (…)“ – kein
  Fehler. Details mit Traceback in `data\fehler.log`.
- **Mail-Ausgang:** Kachel „Mail-Ausgang (Sofort-Mails)“ zeigt offene und fehlgeschlagene
  Mails (nach 3 Versuchen „fehler“, Protokoll in Parametrierung → Projektierung →
  Mail-Protokoll); ohne Graph-Einrichtung werden offene Mails sofort als Fehler abgelegt.

## Für die IT / für Andreas als Administrator des Servers

1. **Dienst statt Konsolenfenster:** `scripts\dienst-installieren.bat` als Administrator
   im Projektordner (`C:\Users\kdadmin\Desktop\Angebotstool`) – erkennt NSSM (`nssm.exe`
   neben dem Skript, im Projektordner oder unter `C:\Friondo\`) und legt sonst die Aufgabe
   „Friondo Angebotstool“ plus Wächter-Aufgabe (alle 5 Minuten `/health`, Neustart bei
   Ausfall) an. Das laufende Konsolenfenster wird nach Rückfrage beendet. Schritt für
   Schritt: `docs/installation-terminal-server.md` Abschnitt 4; Betrieb (Start/Stopp/
   Neustart, Update, Rollback, Logs, Störungen): `docs/betrieb.md`.
2. **`.env` auf dem Server ergänzen** (Vorlage `.env.example`): `BACKUP_ZIEL=` (Ordner
   außerhalb des Servers – Netzlaufwerk der IT, bis dahin ein freigegebener Ordner auf
   fr-wts-02 oder ein OneDrive-/SharePoint-Ordner; ohne Eintrag meldet `/health` „kein
   Backup-Ziel“), optional `DB_POOL_SIZE`/`DB_POOL_OVERFLOW`/`DB_POOL_TIMEOUT`/
   `WORKER_THREADS` (Standard 20/70/10/64), `HTTPS_AKTIV`, `BASIS_URL`, `PROXY_IPS`
   (nur mit Reverse-Proxy).
3. **Backup läuft jetzt im Tool:** täglich 02:30 Sicherung nach `data\backups` (30 Tage)
   und Spiegelung von `backups`, `angebote` (inkl. `signiert`), `projekte` und `.env`
   nach `BACKUP_ZIEL` (robocopy, Log `data\backups\ziel.log`, Aufbewahrung am Ziel 90
   Tage); 02:40 SQLite-Pflege (WAL-Checkpoint + optimize). Die Hotfix-Aufgabe „Friondo
   Backup“ ist damit überflüssig: `schtasks /Delete /TN "Friondo Backup" /F`
   (`scripts\backup-nacht.bat` bleibt für Handläufe). Monatlich `scripts\restore-test.bat`.
4. **`GET /health`** (ohne Anmeldung, JSON): `status` ok|warn|fehler, `version`, `commit`,
   `db`, `db_ms`, `pool`, `threads`, `scheduler[]`, `backup_letztes`, `backup_ziel_status`,
   `wal_mb`, `uptime_s`, `importe[]`, `schreibsperre_max_ms`, `prozess`, `gruende[]`;
   HTTP 503 nur bei `fehler` (Datenbank nicht lesbar). Für ein zentrales Monitoring:
   alle 60 s abfragen, Alarm bei HTTP ≠ 200 oder `status ≠ ok` länger als 5 Minuten.
   Bis dahin: Wächter-Aufgabe auf dem Server + `scripts\health-pruefen.ps1` auf fr-wts-02.
5. **Reverse-Proxy/HTTPS (nachgelagert):** Tool-Seite ist vorbereitet (`HTTPS_AKTIV=1`
   → Cookie `secure`, `BASIS_URL` für absolute Links, `PROXY_IPS` → uvicorn
   `--proxy-headers --forwarded-allow-ips`). Ohne Proxy läuft alles wie bisher über
   `http://192.168.35.4:8000`. Liste der IT-Zulieferungen: `docs/betrieb-it-uebergabe.md`.
6. **Logs:** `data\fehler.log` (Fehler, rotierend), `data\log\zugriff.log` (Zugriffe
   mit Dauer, 10 × 10 MB), `data\log\dienst-out.log`/`dienst-err.log` (Dienst),
   `data\log\waechter.log`, `data\log\smoke-<Datum>.txt`, `data\backups\ziel.log`.
7. **Rückweg:** Alle Datenbankänderungen von v27 sind additiv – `rollback.bat --nur-code`
   stellt den v26-Code wieder her und behält die Datenbank (keine Datenverluste; alte und
   zwischenzeitlich geänderte PINs funktionieren, Cookies der v27-Fassung werden abgewiesen
   → einmal neu anmelden). Standard `rollback.bat` = Code + Datenbank aus der Sicherung.

## Nachtrag 07.10.2026 – Antworten von Andreas

- **Wartungsfenster: Dienstag 22:30–23:30** (statt 18:30–19:30) – Vorschlag auf der Betriebs-Seite,
  Runbook, update.bat.
- **PIN:** Mindestlänge 4 (Einstellung `pin_mindestlaenge`); jeder Benutzer wählt seine PIN selbst
  über Menü → „PIN ändern“. **Admin-Zugang zu allen Konten:** in der Benutzerverwaltung „Als
  Benutzer anmelden“ (ohne PIN, 2 Stunden, steht im Login-Protokoll als `admin_zugang:<Admin>`;
  nicht bei offenem Pflicht-PIN-Wechsel) – zusätzlich zu PIN-Reset und „Sperre aufheben“.
- **NSSM ist erlaubt:** `nssm.exe` von nssm.cc herunterladen und nach `scripts\` legen, dann
  `scripts\dienst-installieren.bat` – es legt den Dienst `FriondoAngebotstool` an.
- **Backup-Ziel (Entscheidung):** `BACKUP_ZIEL=D:\Backup\Angebotstool` (lokales zweites Laufwerk;
  gibt es kein D:, vorerst `C:\Backup\Angebotstool` – schützt gegen Datenfehler, nicht gegen
  Plattenverlust) – ein Netzlaufwerk folgt mit dem Dienstkonto der IT. Die Hotfix-Aufgabe
  „Friondo Backup“ entfernt das Installationsskript. Die Health-Aufgabe auf fr-wts-02 bleibt
  optional (Befehl im Kopf von `scripts\health-pruefen.ps1`); Wächter und Admin-Glocke reichen.
- **Bestands-Erfassungen:** später eingeführte optionale Fragen (O09 Rechnungs-Name, O13
  abweichende Lieferanschrift, A20 Nennleistung der Altanlage) blockieren „Angebot erzeugen“ und
  die Prüfseite nicht mehr; der Bogen führt weiter durch alle Fragen.
- **Mail-Abgleich** alle 15 Minuten nur noch für Angebote in „Versand vorbereitet“/„Versendet“
  der letzten 90 Tage (vorher alle nicht archivierten Angebote in vier Status).
- **Geokodierung:** nach 10 Fehlversuchen keine automatischen Versuche mehr; „Adresse prüfen“
  mit manuellem Pin setzt den Zähler zurück. **Prüflauf Ablehnung** läuft täglich 06:30.
- Lasttest-Zielwerte unverändert; „Versand vorbereiten“ bleibt außerhalb der Zielwerte (sieben
  Graph-Aufrufe, real etwa 3 s). Benutzer-Import: Start-PIN-Liste nur als Druckansicht, inaktive
  Benutzer werden nicht automatisch reaktiviert.

## Lasttest-Ergebnis (06.10.2026)

Lauf 2 mit dem Lastmodell (50 Nutzer, 35 gleichzeitig aktiv, 20 Minuten, 2 s simulierte
Latenz je externem Aufruf) erfüllt alle Zielwerte: Listen und Akten p95 0,5 s, Editor
0,3 s, Angebots-PDF 1,9 s, Protokoll-PDF 0,6 s, Terminvorschläge 4,2 s, keine Fehler,
Pool höchstens zu 18 % belegt. 20 gleichzeitige Innendienst-Nutzer verlieren keine
Änderung (190/190 Positionen). Erst bei doppelter Last (100 Nutzer) stößt SQLite an
seine Ein-Schreiber-Grenze – **SQLite bleibt**, Reserve rund 40 % über dem Lastmodell;
der nächste Lasttest folgt nach dem nächsten großen Modul (`docs/lasttest-v27.md`).

## Offen / Rückfragen

- Siehe Gesamtübersicht v27 (Rückfragen gebündelt) und `docs/lasttest-v27.md`
  (Zielwerte, Ergebnis, PostgreSQL-Entscheidung).
