# Umsetzungsplan v17 – Betriebsreife für 50 Nutzer (Lastfestigkeit, Dienst, Backup, Login, Lasttest)

Voraussetzung: kein anderer Plan in Umsetzung (strangübergreifend geprüft);
v26 (PLAN_PROJ_V5, Phasen 122–126) und der **Hotfix 06.10.2026
(Verbindungspool)** sind committet und ausgerollt – dieser Plan baut auf dem
Hotfix auf und ersetzt ihn nicht. CLAUDE.md ist Live-Master im Projektordner
`C:\Users\a.scheelen\Tools\Angebotstool` (Git-Arbeitskopie); der Server
läuft aus seinem eigenen Ordner (derzeit `C:\Users\kdadmin\Desktop\
Angebotstool`, siehe Phase 127). ALLE PHASEN DIESES PLANS IN EINEM
DURCHLAUF UMSETZEN (Reihenfolge einhalten, jede Checkbox nach Umsetzung und
Test abhaken, am Ende Gesamtübersicht mit Testergebnissen und offenen
Punkten, fachliche Rückfragen gebündelt). migrate.py idempotent.
**Kein git push vor Freigabe. Rollout nur im Wartungsfenster (Phase 132).**

CLAUDE-Abschnitt: **„Neu in v27"** (höchste + 1; v26 = Heizreport). Phasen
**127–132** (frei laut Zuordnungstabelle; 122–126 gehören zu PLAN_PROJ_V5).

Anlass: Das Tool wird demnächst von **50 Mitarbeitern** genutzt (Innendienst,
Außendienst mobil, Lead-Management, Projektierung, Montage – Zugriff per
Browser im Firmennetz bzw. VPN). In den letzten Tagen traten zwei
Betriebsstörungen auf, die bei 50 Nutzern sofort flächig wirken:
`sqlite3.OperationalError: database is locked` (v22, Hintergrundläufe
halten die Schreibsperre während Netz-I/O) und
`sqlalchemy.exc.TimeoutError: QueuePool limit of size 5 overflow 10 reached`
(06.10.2026, Verbindungen während Netz-I/O gehalten, zwei Verbindungen je
Anfrage). Beides sind Code- und Betriebsregeln, keine Hardwaregrenzen.
Dieser Plan macht die Regeln verbindlich, misst sie im Lasttest nach und
bringt den Betrieb (Dienst, Backup, Überwachung, Login, Rollout) auf
50-Nutzer-Niveau. Erfassungsliste als Vorgangs-Sicht und Online-Signatur
rücken auf PLAN_V18.

## Entscheidungen (Chat Angebotstool, 06.10.2026)

- **SQLite bleibt** – gehärtet (Sitzungsdisziplin, Pool, kurze
  Schreibtransaktionen, WAL-Pflege). **Der Lasttest entscheidet**, ob ein
  PostgreSQL-Umstieg nötig wird (Entscheidungsregel in Phase 131); er wird
  nicht vorsorglich gebaut.
- **Zugriff:** alle 50 Nutzer per Browser am eigenen PC/Handy im Firmennetz
  oder per VPN; der Terminal-Server ist nur noch Server, keine RDP-Sitzungen
  für die Tool-Nutzung.
- **Betrieb als Windows-Dienst** (NSSM, Autostart, automatischer Neustart,
  Dienstkonto) statt Konsolenfenster in einer Benutzersitzung; **festes
  Wartungsfenster** einmal pro Woche abends für Updates, keine Rollouts zur
  Arbeitszeit, Smoke-Test nach jedem Update, Rollback-Weg geprüft.
- **IT ist vorhanden, aber derzeit nicht erreichbar.** Deshalb ist der
  Plan so geschnitten, dass **alle sechs Phasen ohne IT umsetzbar** sind –
  Andreas hat Administratorrechte auf dem Server (update.bat läuft dort
  bereits als Administrator), Claude Code liefert fertige Skripte und
  Schritt-für-Schritt-Anleitungen. Alles, was nur die IT kann (VPN,
  Zertifikat/Reverse-Proxy, zentrales Monitoring, Netzlaufwerk,
  Serverausbau), steht im Abschnitt „Zulieferungen IT (nachgelagert)" und
  **blockiert keine Checkbox**; der Plan sieht für jeden dieser Punkte einen
  Zwischenstand vor, der ohne IT funktioniert.
- **Regel „keine offene Datenbanksitzung während Netz-I/O"** wird
  Projektregel (CLAUDE.md, Abschnitt Fachliche Regeln) und per Test
  abgesichert; sie gilt für Hintergrundläufe und Anfragen gleichermaßen.
- **Login-Härtung** ohne Verfahrenswechsel: PIN bleibt (mobiler Außendienst),
  aber mit sicherem Hash, Mindestlänge, Fehlversuchssperre, Sitzungsablauf
  und Erst-Login-Wechsel; Microsoft-365-Anmeldung ist eine spätere Option
  (Zulieferungen).

## Phase 127 – Ist-Aufnahme, Inventar, Messbasis

- [x] **Betriebsart des Servers feststellen** (Andreas/IT liefern, Claude
      Code dokumentiert in neuem `docs/betrieb.md`, Abschnitt „Ist 10/2026"):
      Startweg (Konsolenfenster „Friondo Angebotstool Server" aus `start.bat`
      in der Sitzung kdadmin **oder** Aufgabe „Friondo Angebotstool" der
      Aufgabenplanung, Konto SYSTEM), Projektpfad auf dem Server,
      Python-Version, Uvicorn-Aufruf, Firewall-Regel, Größe von `data\`
      (DB, WAL-Datei, PDFs, Projekte), Anzahl Benutzer je Rolle, CPU/RAM des
      Servers, Zugangswege (Firmennetz; Außendienst mobil über WireGuard-VPN
      – vorhanden, `docs/mobilzugriff.md` als umgesetzt kennzeichnen).
      Befund „läuft in einer Benutzersitzung" = Risiko Nr. 1 (Abmelden
      beendet das Tool) – wird in Phase 129 beseitigt.
- [x] **Inventar Datenbanksitzungen & Netzaufrufe** (`docs/betrieb.md`,
      Tabelle Modul | Auslöser (Anfrage/Scheduler) | Intervall | Netzaufruf |
      hält Sitzung während Netz-I/O ja/nein | Schreibtransaktion ja/nein |
      Maßnahme): alle `SessionLocal()`-Stellen und alle `scheduler_starten`
      (monday_sync, mail_sync, ablauf_pruefung, benachrichtigungen,
      lead_parser, leadmanagement, geocoding, lead_mail, v23/v25-Läufe wie
      `faellige_wiedervorlagen_melden`, Terminvorschläge-Cache, v26
      Heizreport), dazu Importe (Preisliste, PV, Klima, Logik neu einlesen,
      Bestandsimport) und PDF-Erzeugung. Diese Tabelle ist die Arbeitsliste
      für Phase 128 – jede Zeile endet dort mit „erledigt" oder einer
      Begründung.
- [x] **Zugriffsprotokoll mit Dauer** (Messbasis für den Lasttest):
      Middleware schreibt je Anfrage eine Zeile nach `data\log\zugriff.log`
      (RotatingFileHandler 10 × 10 MB): Zeit, Benutzer-ID, Rolle, Methode,
      Pfad ohne Query, Status, Dauer ms, Pool-Checkouts zu Beginn. Keine
      Formdaten, keine Namen. Parametrierung → Betrieb (Phase 129) wertet die
      letzten 24 h aus: Anfragen/Minute, p50/p95 je Route (Top 20), Anteil
      > 2 s.
- [x] **Lastmodell festlegen** (`docs/lasttest-v27.md`, Abschnitt 1, Zahlen
      [ANNAHME] – Andreas bestätigt): 50 Nutzer, gleichzeitig aktiv zur
      Spitzenzeit 9–11 Uhr etwa 35: 15 Außendienst mobil (Leads VOT öffnen,
      Erfassungsbogen 25 Fragen, Absenden, Protokoll-PDF), 12 Innendienst
      (Erfassungsliste, Angebot erzeugen, Editor mit 10 Positionsänderungen,
      PDF, Versand vorbereiten, Vorgangsakte), 6 Lead-Management (Hauptboard,
      Kundenkartei mit Terminvorschlägen, Anrufergebnis, Deals), 4
      Projektierung/Montage (Board, Projektakte, Aufgabe erledigen, Galerie-
      Upload 2 MB), dazu alle Hintergrundläufe im Normaltakt. Denkzeit je
      Nutzer 5–15 s. Daraus Zielwerte in Phase 131.

## Phase 128 – Sitzungsdisziplin, Pool und Schreibtransaktionen (Code)

- [x] **Projektregel umsetzen:** „Eine Datenbanksitzung wird vor jedem
      Netzaufruf (monday, Graph/Outlook, Nominatim, openrouteservice,
      Heizreport, SMTP, HTTP allgemein) committet und geschlossen; nach dem
      Netzaufruf wird für das Zurückschreiben eine neue, kurze Sitzung
      geöffnet." Jede Zeile der Inventartabelle aus Phase 127 abarbeiten.
      Muster: Hilfsfunktion `db.kurz()` (Kontextmanager: `with db.kurz() as
      s:` → commit bei Erfolg, rollback bei Fehler, immer close) für
      Scheduler und Hilfsfunktionen; Anfragen behalten `get_session`.
- [x] **Middleware (`auth.RollenMiddleware`):** Sitzung nach den Rollen-,
      Glocken- und Modulabfragen und **vor** `call_next` schließen (falls im
      Hotfix noch nicht geschehen); `request.state.benutzer` ist danach ein
      losgelöstes Objekt – alle Stellen, die daran Beziehungen nachladen,
      auf `session.get(Benutzer, id)` umstellen (Suche nach
      `request.state.benutzer.` mit Relationen). Ergebnis: höchstens **eine**
      Verbindung je Anfrage.
- [x] **Pool und Threads aus der `.env`** (Standardwerte im Code, Doku in
      `.env.example`): `DB_POOL_SIZE` = 20, `DB_POOL_OVERFLOW` = 40,
      `DB_POOL_TIMEOUT` = 10 s, `WORKER_THREADS` = 64 (Starlette-Threadpool
      via `anyio.to_thread.current_default_thread_limiter().total_tokens` beim
      Start). Invariante, beim Start geprüft und protokolliert: Pool gesamt
      ≥ Threads + Anzahl Scheduler + 5; sonst Warnung im Fehlerprotokoll.
- [x] **Scheduler-Rahmen** (`app/scheduler.py`, alle bestehenden Läufe
      darauf umstellen, Verhalten unverändert): je Lauf ein Name, Intervall,
      Single-Flight-Sperre (kein zweiter Start, solange der vorige läuft),
      Zufallsversatz 0–30 s beim ersten Start (nicht alle Läufe zur gleichen
      Sekunde), Laufzeitmessung, letzter Fehler, Zähler; Status in Tabelle
      `scheduler_status` (name, letzter_start, letzte_dauer_ms, letzter_fehler,
      laeufe, fehler). Kein Lauf hält eine Sitzung länger als 2 s ohne
      Netz-I/O; Läufe mit vielen Datensätzen (Geocoding, Nurture, Löschlauf)
      arbeiten in Blöcken mit Commit je Block (höchstens 50 Datensätze oder
      1 s Schreibsperre am Stück). Geocoding: Backoff für Adressen mit Status
      „fehler" (1 h, 6 h, 24 h), wie in v22 offen gelassen.
- [x] **Sofort-Mails erst nach dem Commit des Aufrufers** (Nachtrag aus dem
      Hotfix 06.10.2026, Rückfrage 3 von Claude Code): der Hotfix lässt
      `kern.benachrichtigen` vor einer Sofort-Mail die anstehenden Änderungen
      des Aufrufers committen – scheitert der Request danach, bleibt dieser
      Teilstand stehen. Lösung: **Ausgangs-Warteschlange** – `benachrichtigen`
      legt den Mailauftrag nur noch als Zeile in `mail_ausgang` (Empfänger,
      Betreff, Text, Bezug, Status offen/gesendet/fehler, Versuche) an, in
      derselben Transaktion wie die fachliche Änderung; der Versand erfolgt
      außerhalb des Requests durch den Scheduler-Lauf „Mail-Ausgang" (jede
      Minute, Single-Flight, Freigabe vor jedem Graph-Aufruf, 3 Versuche,
      danach Fehlerprotokoll + Admin-Glocke). Kein Request führt mehr
      Netz-I/O für Benachrichtigungen aus; die Zustellung verzögert sich
      höchstens um eine Minute. Bestehende Lead-Mail-Warteschlange
      (`lead_mail`, v12) bleibt getrennt, gleiche Regeln. Test: Request mit
      Fehler nach `benachrichtigen` hinterlässt weder Änderung noch
      Mailauftrag.
- [x] **Importe und Migrationen** (Preisliste, PV, Klima, Logik neu
      einlesen, Bestandsimport, monday-Vollabgleich): Schreiben in Blöcken
      mit Commit je 200 Zeilen; vor dem Start Hinweis in der Parametrierung
      „Dauer etwa <n> s – während des Imports können Speichern-Aktionen
      anderer Nutzer kurz warten; empfohlen außerhalb der Kernzeit" mit
      Bestätigung; laufender Import wird im Betriebs-Status (Phase 129)
      angezeigt. migrate.py unverändert nur im Wartungsfenster (update.bat).
- [x] **SQLite-Pflege:** nächtlich 02:40 (Scheduler) `PRAGMA
      wal_checkpoint(TRUNCATE)` und `PRAGMA optimize`; WAL-Dateigröße im
      Betriebs-Status; `PRAGMA busy_timeout` bleibt 5000 ms. Indexprüfung
      der häufigsten Abfragen (Angebotsliste, Erfassungsliste, Vorgangsakte,
      Leads VOT, Hauptboard/Deals, Anrufliste, Projektboard, Glocke) mit
      `EXPLAIN QUERY PLAN`; fehlende Indizes (z. B. `vorgaenge.lead_phase`,
      `angebote.status`, `erfassungen.status`, `lead_aktivitaeten.vorgang_id,
      erstellt_am`, `benachrichtigungen.benutzer_id, gelesen`) per Migration
      anlegen – Liste der tatsächlich angelegten Indizes in der
      Gesamtübersicht.
- [x] **Blockierende Arbeit außerhalb der Event-Loop:** alle `async def`-
      Endpunkte prüfen, die synchron Dateien/DB/PDF/HTTP bearbeiten → in
      `def` (Threadpool) umstellen oder `run_in_threadpool`; PDF-Erzeugung
      und Excel-Importe laufen nie in der Event-Loop. Galerie-Uploads
      streamen in Blöcken (keine 50-MB-Datei im Speicher).
- [x] **Tests** (`tests/test_v27_sitzungen.py`): (a) Wächter-Test, der im
      gesamten `app/`-Code nach Netzaufrufen innerhalb offener Sitzungen
      sucht (AST-Prüfung: `urlopen`/`httpx`/`requests`/`_api`/`graph`-Aufrufe
      zwischen `SessionLocal()`/`get_session` und `close()`/Kontextende
      außerhalb markierter Ausnahmen) und bei Treffern fehlschlägt; (b) 40
      parallele Anfragen auf Kundenkartei + Terminvorschläge mit 3 s
      Routing-Mock ohne `TimeoutError`; (c) Scheduler-Lauf mit 1.000
      Geocoding-Adressen hält die Schreibsperre nie länger als 1 s
      (Messung über parallelen Schreibversuch); (d) Pool-Invariante.

## Phase 129 – Betrieb: Dienst, Backup, Überwachung, Reverse-Proxy

Alle Punkte dieser Phase sind **ohne IT** umsetzbar (Andreas als lokaler
Administrator auf dem Server + Skripte von Claude Code); wo die IT später
etwas Besseres liefern kann, steht der Zwischenstand ausdrücklich dabei.

- [x] **Windows-Dienst** – zwei gleichwertige Wege, `scripts\dienst-
      installieren.bat` erkennt selbst, welcher möglich ist: (A) **NSSM**,
      wenn `nssm.exe` neben dem Skript oder unter `C:\Friondo\` liegt
      (Download von nssm.cc durch Andreas, keine Installation nötig): Dienst
      `FriondoAngebotstool`, AppDirectory = Projektordner, Start automatisch,
      Neustart bei Absturz nach 5 s, Ausgabe nach `data\log\dienst-out.log`/
      `dienst-err.log` mit Rotation 10 MB, Konto SYSTEM (ein Dienstkonto der
      IT kann später nachgetragen werden). (B) **Aufgabenplanung ohne
      Zusatzsoftware** (wie heute vorgesehen, Aufgabe „Friondo Angebotstool",
      Konto SYSTEM, Start bei Boot) **plus Wächter-Aufgabe** „Friondo
      Angebotstool Wächter" alle 5 Minuten: prüft, ob Port 8000 antwortet
      (`/health`), sonst Aufgabe neu starten und Eintrag in
      `data\log\waechter.log`. In beiden Fällen: Ausgaben in Dateien statt in
      ein Fenster, kein Start mehr aus einer Benutzersitzung; das Skript
      beendet ein laufendes Konsolenfenster „Friondo Angebotstool Server"
      nach Rückfrage. `update.bat`/`rollback.bat` erkennen den Weg (nssm
      stop/start bzw. schtasks /End /Run). `start.bat` bleibt für den
      Entwicklungs-PC und warnt auf dem Server („Dienst vorhanden – bitte
      `scripts\dienst-neustart.bat`"). Anleitung Schritt für Schritt in
      `docs/installation-terminal-server.md` (Abschnitt 4 neu), so dass
      Andreas sie allein ausführen kann: Eingabeaufforderung als
      Administrator, ein Befehl, Kontrolle über `/health`.
- [x] **`GET /health`** (ohne Anmeldung, nur Lesen, keine Daten): JSON
      `{"status": "ok|warn|fehler", "version": "v27", "commit": "<hash>",
      "db": "ok", "db_ms": <n>, "pool": {"size": 20, "checked_out": n,
      "overflow": n}, "scheduler": [{"name": …, "letzter_start": …,
      "ok": true}], "backup_letztes": "<Zeit>", "wal_mb": <n>, "uptime_s":
      <n>}`; `warn`, wenn Pool > 70 % belegt, ein Scheduler > 2 Intervalle
      ohne Lauf, letztes Backup > 26 h; HTTP 503 bei `fehler`. Bis die IT
      ein Monitoring anbindet, übernimmt das die Wächter-Aufgabe aus dem
      Dienst-Punkt (Neustart bei Ausfall) plus eine **Admin-Glocke** des
      Tools selbst bei `warn` (höchstens eine je Stunde); zusätzlich legt
      Claude Code `scripts\health-pruefen.ps1` für fr-wts-02 an (alle 5
      Minuten per Aufgabenplanung: `/health` abfragen, bei Ausfall
      Windows-Benachrichtigung an Andreas und Zeile in
      `C:\Users\a.scheelen\Tools\health.log`).
- [x] **Parametrierung → Betrieb** (Admin): Kacheln Version/Commit, Uptime,
      Pool (aktuell/Spitze 24 h), Threads, WAL-Größe, letztes Backup und
      Backup-Ziel erreichbar, Scheduler-Tabelle (aus `scheduler_status`,
      Knopf „jetzt ausführen" je Lauf), Zugriffsstatistik aus Phase 127
      (Anfragen/Minute, p95 Top 20, langsamste 20 Anfragen 24 h), laufende
      Importe, Wartungshinweis setzen (Phase 132). Fehlerprotokoll verlinkt.
- [x] **Backup:** (a) nächtlich 02:30 per Scheduler (nicht nur beim Start):
      SQLite-Backup-API nach `data\backups\angebotstool-<Datum>.db`
      (Aufbewahrung 30 Tage); (b) danach Spiegelung nach `BACKUP_ZIEL` aus der
      `.env` – **jeder Ordner außerhalb des Servers taugt als Ziel**, in
      dieser Reihenfolge der Vorzüge: Netzlaufwerk der IT (später), bis dahin
      ein von Andreas freigegebener Ordner auf fr-wts-02 oder ein
      OneDrive-/SharePoint-Ordner (für Sicherungskopien ist Sync-Speicher in
      Ordnung – nur die laufende Datenbank darf dort nie liegen); ohne Eintrag
      bleibt es bei der lokalen Sicherung und `/health` meldet `warn` „kein
      Backup-Ziel". Inhalt: DB-Sicherung + `data\angebote\` +
      `data\angebote\signiert\` + `data\projekte\` + `.env` mit `robocopy /MIR
      /R:2 /W:5` in `data\backups\ziel.log`; Aufbewahrung am Ziel 90 Tage;
      (c) Ergebnis in `/health` und Betriebs-Status, Fehlschlag → Glocke an
      Admins + Fehlerprotokoll; (d) `scripts\restore-test.bat`: jüngste
      Sicherung nach `diagnose\restore_<Datum>\` einspielen, `migrate.py`
      darauf, `voll_crawl.py --data … --max-ids 20` – Protokoll nach
      `docs\betrieb\restore-<Datum>.txt`; monatlich durch Andreas/IT
      (Runbook-Eintrag).
- [x] **Reverse-Proxy & HTTPS – nur die Tool-Seite vorbereiten** (der Proxy
      selbst ist IT-Zulieferung, nachgelagert): Uvicorn mit `--proxy-headers
      --forwarded-allow-ips <Proxy-IP>`; Cookie `secure` und `samesite=lax`,
      gesteuert über `.env` `HTTPS_AKTIV=1`; absolute Links (PDF-Mails, ICS,
      Signatur-Links) nutzen `BASIS_URL` aus der `.env` (z. B.
      `https://tool.friondo.local`); `/health` bleibt ohne Login erreichbar.
      Ohne Proxy läuft alles wie bisher über `http://192.168.35.4:8000` im
      Firmennetz – für den Start mit 50 Nutzern ausreichend.
- [x] **Serverressourcen-Check** in `docs/betrieb.md` (Andreas liest die
      Werte im Task-Manager des Servers ab, Claude Code trägt sie ein):
      Empfehlung für 50 Nutzer 4 vCPU / 8 GB RAM / SSD, `data\` auf lokaler
      Platte (nie Netzlaufwerk/OneDrive – SQLite-WAL verträgt keine
      Sync-Ordner), Uhrzeit per NTP, Virenscanner-Ausnahme für `data\`
      (Datei-Sperren durch Echtzeitscan sind eine bekannte Ursache für
      „database is locked" – wenn der Virenscanner zentral verwaltet wird,
      Punkt an die IT; sonst lokal eintragen). Ein Ausbau des Servers ist
      IT-Zulieferung und wird erst nach dem Lasttest entschieden.

## Phase 130 – Login-Härtung für 50 Nutzer

- [x] **PIN-Hash:** neue PINs mit PBKDF2-HMAC-SHA256 (200.000 Runden,
      16-Byte-Salz je Benutzer) in der **neuen Spalte `benutzer.pin_hash_v2`**;
      die bisherige Spalte `pin_hash` bleibt unverändert stehen und wird vom
      alten Code weiter gelesen – so bleibt ein Rollback auf v26 jederzeit
      möglich (Rückweg, Phase 132). Login: `pin_hash_v2` gesetzt → PBKDF2,
      sonst SHA-256 wie bisher; beim nächsten erfolgreichen Login wird
      `pin_hash_v2` still gefüllt, `pin_hash` erst in einem späteren Plan
      geleert (frühestens nach 30 Tagen störungsfreiem Betrieb). Mindestlänge
      neuer PINs **6 Ziffern** [ANNAHME; Alternative: Passwort für Büro-
      Rollen, PIN nur für Außendienst/Montage – Andreas entscheidet],
      Verbot von 123456/111111/Geburtsjahr-Mustern (Liste in der
      Parametrierung).
- [x] **Fehlversuchssperre:** nach 5 Fehlversuchen je Benutzer innerhalb von
      15 Minuten Sperre 15 Minuten (Spalten `benutzer.fehlversuche`,
      `gesperrt_bis`), Meldung wörtlich: „Zu viele Fehlversuche – bitte in
      15 Minuten erneut versuchen oder den Admin um eine neue PIN bitten."
      Zusätzlich je IP höchstens 30 Login-Versuche in 15 Minuten. Alle
      Versuche (Erfolg/Fehler, Benutzer, IP-Kurzform, Zeit) in Tabelle
      `login_protokoll` (90 Tage), Ansicht Parametrierung → Benutzer →
      Login-Protokoll.
- [x] **Sitzungsdauer:** signiertes Cookie mit Ablauf – Büro-Rollen 12 h,
      Außendienst/Montage 30 Tage mit Häkchen „Auf diesem Gerät angemeldet
      bleiben" [ANNAHME]; Abmelden überall; „Alle Sitzungen beenden" je
      Benutzer durch Admin (Sitzungszähler im Cookie). Parameter in der
      Parametrierung → Benutzer.
- [x] **Erst-Login und Massenanlage:** Kennzeichen `pin_wechsel_noetig`
      (Pflichtwechsel beim ersten Login und nach Admin-Reset); CSV-Import
      von Benutzern (Spalten Name, Rolle, E-Mail, Team, Vertriebskanal-
      Zuordnung optional) mit Vorschau, erzeugt Start-PINs und eine
      druckbare/ausgebbare Liste nur für den Admin (nicht gespeichert);
      Benutzerliste mit Filter Rolle/aktiv und Spalte „letzter Login".
- [x] Tests (`tests/test_v27_login.py`): Alt-Hash-Login + stille Umstellung,
      Sperre nach 5 Fehlversuchen und Freigabe nach Ablauf, Cookie-Ablauf,
      Pflichtwechsel, CSV-Import mit 50 Benutzern; Außendienst sieht nach wie
      vor nie EK/DB (Regressionstests der Rollen).

## Phase 131 – Lasttest mit 50 Nutzern und Entscheidungsregel

- [x] **`scripts/lasttest.py`** (gegen DB-Kopie `diagnose\test_v27\data`,
      eigener Uvicorn auf Port 8001 mit denselben Pool-/Thread-Werten wie der
      Server, **echte HTTP-Anfragen** über httpx, nicht TestClient): virtuelle
      Nutzer nach dem Lastmodell aus Phase 127 (35 gleichzeitig aus 50, feste
      Zufallssaat), Szenarien je Rolle mit Denkzeiten 5–15 s, Dauer 20
      Minuten; externe Dienste wie in `voll_crawl.py` abgeklemmt, aber mit
      **simulierter Latenz 2 s** (Routing, Graph, Nominatim, Heizreport), damit
      die Sitzungsdisziplin unter realen Wartezeiten geprüft wird; alle
      Scheduler laufen im Normaltakt mit. Messung je Route: Anzahl, p50, p95,
      p99, Fehler (HTTP 5xx, Timeout), dazu Pool-Spitze, maximale Wartezeit
      auf die Schreibsperre (Zeitmessung im `_speichern`-Pfad), WAL-Größe,
      CPU/RAM des Prozesses. Bericht `docs/lasttest-v27.md` mit Tabellen.
- [x] **Zielwerte (Abnahmekriterien, [ANNAHME] – Andreas bestätigt):**
      p95 Listen und Akten (Erfassungsliste, Angebotsliste, Vorgangsakte,
      Hauptboard, Kundenkartei ohne Vorschläge, Leads VOT) **≤ 1,5 s**; p95
      Editor-Aktionen (Position ändern/löschen/sortieren) **≤ 1,0 s**; p95
      Angebots-PDF **≤ 4 s**, Protokoll-PDF ≤ 3 s; Terminvorschläge ≤ 6 s (mit
      2 s simulierter Latenz); **0** `TimeoutError`, **0** `database is
      locked` an der Oberfläche (interne Wiederholung erlaubt, Zähler im
      Bericht); Pool-Spitze ≤ 60 % des Maximums; Fehlerquote < 0,1 %.
- [x] **Schreibsturm:** 20 Innendienst-Nutzer ändern gleichzeitig je 10
      Positionen in 20 verschiedenen Angeboten (Editor-Fragment) – keine
      verlorene Änderung (Prüfung Soll/Ist je Position), keine 500er.
- [x] **Stressstufe:** Lastmodell auf 100 Nutzer verdoppelt (10 Minuten) –
      nur zur Ermittlung der Reserve, keine Abnahmekriterien; Ergebnis als
      „Reserve-Faktor" im Bericht.
- [x] **Entscheidungsregel PostgreSQL** (im Bericht ausfüllen): Werden die
      Zielwerte nach Behebung aller gefundenen Code-Ursachen (zweiter Lauf)
      **nicht** erreicht **und** ist die Ursache nachweislich die
      Ein-Schreiber-Grenze von SQLite (Wartezeit auf die Schreibsperre > 20 %
      der Antwortzeit bei p95), empfiehlt die Gesamtübersicht den Umstieg
      (eigener Plan, nicht in v27). Sonst: SQLite bestätigt, nächster
      Lasttest nach dem nächsten großen Modul.
- [x] Lasttest-Skript, Lastmodell und Zielwerte sind wiederverwendbar
      (`--nutzer`, `--dauer`, `--profil`); Aufruf im Runbook dokumentiert.

## Phase 132 – Rollout-Regeln, Runbook, Doku, Übergabe

- [x] **Wartungsfenster und Ankündigung:** Parameter `wartungshinweis`
      (Text + von/bis) → Banner oben auf jeder Seite für alle Rollen,
      wörtlich: „Wartung heute von <von> bis <bis> Uhr – bitte Arbeit bis
      dahin speichern. Das Tool ist in dieser Zeit kurz nicht erreichbar."
      Standard-Fenster **Dienstag 18:30–19:30** [ANNAHME]; Updates nur in
      diesem Fenster, Hotfixes nur mit Freigabe von Andreas und Banner
      mindestens 30 Minuten vorher.
- [x] **Rückweg garantiert (Rollback-Sicherheit von v27):** alle
      Datenbankänderungen dieses Plans sind **nur additiv** (neue Spalten
      `pin_hash_v2`, `fehlversuche`, `gesperrt_bis`, `pin_wechsel_noetig`,
      neue Tabellen `scheduler_status`, `login_protokoll`, neue Indizes) –
      der v26-Code läuft auf einer v27-Datenbank unverändert weiter;
      `.env`-Schlüssel, die v26 nicht kennt, werden ignoriert. `rollback.bat`
      erhält den Schalter **`--nur-code`** (Code auf den Stand vor dem Update,
      Datenbank bleibt – kein Datenverlust; Standard bleibt Code + Datenbank
      aus der Sicherung) und erkennt Dienst/Aufgabe/Konsolenfenster wie
      `update.bat`. **Rollback-Probe auf der DB-Kopie** vor dem Rollout:
      v26-Stand → `update.bat`-Ablauf → Smoke-Test → `rollback.bat --nur-code`
      → v26 läuft wieder, Logins (alte und zwischenzeitlich geänderte PINs),
      Angebotsliste, PDF und Lead-Boards funktionieren → Ergebnis in der
      Gesamtübersicht. Nach Rollback sind nur die v27-Zusatzfunktionen weg
      (Betriebs-Seite, Login-Protokoll, Wartungsbanner); Cookies der
      v27-Fassung werden von v26 abgewiesen → einmal neu anmelden.
- [x] **`scripts\smoke.bat`** (nach jedem Update, 2 Minuten): `/health` =
      ok, Login als Admin, Startseite, Erfassungsliste, Angebotsliste, eine
      Vorgangsakte, ein Angebots-PDF, Hauptboard, Projektboard – jeweils
      HTTP 200 und Antwortzeit < 3 s; Ergebnis als Datei
      `data\log\smoke-<Datum>.txt`; bei Fehlschlag Hinweis „rollback.bat".
- [x] **Runbook `docs/betrieb.md`** (für IT und Andreas, Schritt für
      Schritt): Dienst starten/stoppen/neustarten, Update im Wartungsfenster
      (Reihenfolge: Banner → Server-DB-Kopie nach `diagnose\` → migrate.py
      zweimal auf der Kopie → Voll-Crawl + Abnahmeskript → push → update.bat →
      smoke.bat → Banner aus), Rollback, Backup/Restore-Test, Logdateien und
      ihre Bedeutung (`fehler.log`, `zugriff.log`, `dienst-*.log`,
      `backups\ziel.log`), `/health`-Felder, typische Störungen und erste
      Maßnahmen (Pool voll, database is locked, Dienst steht, Backup-Ziel
      nicht erreichbar, Zertifikat abgelaufen), Ansprechpartner-Tabelle
      (Tool: Andreas/Claude Code; Server/Netz/Backup/VPN: IT).
- [x] **Projektregeln in CLAUDE.md** (Abschnitt Fachliche Regeln,
      Unterpunkt „Betrieb"): keine offene Sitzung während Netz-I/O; Importe
      nur außerhalb der Kernzeit; Rollout nur im Wartungsfenster mit
      Smoke-Test; jede neue Hintergrundaufgabe über `app/scheduler.py`; jeder
      Plan mit neuen Netzaufrufen ergänzt das Inventar in `docs/betrieb.md`.
      `UMZUGS-BRIEFING.md` Abschnitt 2 um das Wartungsfenster ergänzen.
- [x] CLAUDE.md: Abschnitt „Neu in v27 – Betriebsreife für 50 Nutzer
      (abgestimmt 06.10.2026)" (Plan: PLAN_V17.md, Phasen 127–132;
      Sitzungsdisziplin, Pool/Threads aus `.env`, Scheduler-Rahmen,
      SQLite-Pflege, Indizes, Dienst/NSSM, `/health`, Betriebs-Seite, Backup
      mit Spiegelung, Proxy/HTTPS-Vorbereitung, Login-Härtung, Lasttest mit
      Ergebnis und Entscheidung, Wartungsfenster), Zuordnungstabelle
      `| v27 | PLAN_V17.md | 127–132 |`, Hinweis in „Neu in v22", dass die
      offene Scheduler-Folgeänderung hiermit erledigt ist.
      `docs/nach-dem-update-v27.md` (Team: neue PIN-Regeln, Erst-Login,
      Wartungsbanner, angemeldet bleiben; IT: Dienst, Backup-Ziel, Proxy,
      Monitoring; Admin: Betriebs-Seite, Login-Protokoll, Benutzer-Import).
- [x] Gesamtübersicht am Ende: Inventar mit Status je Zeile, angelegte
      Indizes, Lasttest-Ergebnisse (beide Läufe) gegen die Zielwerte,
      PostgreSQL-Entscheidung, offene IT-Zulieferungen, alle
      [ANNAHME]-Stellen, gebündelte Rückfragen. Commit mit sprechender
      Nachricht; **kein push vor Freigabe**; Rollout erst im Wartungsfenster
      nach Smoke-Test-Probe auf der DB-Kopie.

## Nachtrag 06.10.2026 – Klima-Versand und Anmeldeseite

(Quelle: PROTOKOLL-2026-10-06-Projektierung.md, Abschnitt 3 „Feedback
Angebotstool"; gehört zu v27, keine neuen Phasennummern. Die beiden
Versand-Punkte sind kleine Korrekturen und werden **zu Beginn des
Durchlaufs vor Phase 128** erledigt, die Anmeldeseite in Phase 130.)

(**Stand 07.10.2026, 23:10:** Dieser Abschnitt lag Claude Code beim v27-Durchlauf
nicht vor – die drei Punkte sind in v27 (2bbd924/2544005) **nicht** umgesetzt und
werden als erster Schritt des Durchlaufs v28/v29 nachgeholt (ein gemeinsamer
Commit für Nachtrag + v28 + v29 am Ende des Durchlaufs, Entscheidung Andreas); die
Anmeldeseite baut auf dem v27-Login auf (Häkchen „angemeldet bleiben“, Sperr-
Meldungen, `login_v27.css`) – Login-Logik unverändert. CLAUDE.md: Absatz
„Nachtrag 2“ im Abschnitt „Neu in v27“, keine neue Versionsnummer.)

- [x] **Anhänge Klima** (Blatt „Anhänge", Arbeitsanweisung an der
      Live-Excel): die Platzhalterzeile „(Bosch Climate Broschüre –
      Zulieferung)" auf den Dateinamen **`Bosch Climate 3200i.pdf`** setzen
      (Datei liegt seit 06.10.2026 in `anlagen\`), Regel „wenn Sparte = KL",
      Bemerkung „Gerätebroschüre Bosch Climate 3200i (v27)". Zusätzlich die
      Ursache finden, warum beim Versand eines KL-Angebots die
      Unternehmenspräsentation fehlte, obwohl ihre Regel „immer" lautet
      (Vermutung: Anhangsauswahl prüft Sparte/Profil vor der „immer"-Regel
      oder der KL-Versand nimmt einen anderen Pfad) – beheben. Test: Versand
      eines KL-Angebots (Profil Standard) hängt Unternehmenspräsentation,
      Ratenkauf-Broschüre und Bosch Climate 3200i an; Enni/SWD ohne
      Ratenkauf; WP-/PV-Versand unverändert.
- [x] **E-Mail-Vorlage je Sparte** (Parametrierung → E-Mail-Vorlagen): die
      Standard-Vorlage für Betreff + Text gibt es künftig **je Sparte WP / PV
      / KL / WB** (Reiter oder Auswahl „Sparte"), Platzhalter wie bisher;
      Auswahl beim Versand: Vorlage je Außendienstler (wie v5) → Sparten-
      Vorlage des Angebots → Standard (Fallback). Migration legt die
      Sparten-Vorlagen aus der heutigen Standard-Vorlage an und ersetzt dabei
      für KL im Betreff und Text „Wärmepumpenangebot" → „Klimaanlagenangebot"
      und „Wärmepumpe" → „Klimaanlage", für PV „Wärmepumpenangebot" →
      „PV-Angebot" und „Wärmepumpe" → „PV-Anlage"; Platzhalter `{eigenanteil}`
      und `{foerderung}` werden bei PV/KL leer bzw. die zugehörigen Sätze
      entfernt (Satzliste in der Gesamtübersicht, Innendienst liest gegen).
      Kombi-Versand behält seine eigene Vorlage. Test: KL-Angebot → Entwurf
      mit Betreff „Klimaanlagenangebot …", ohne „Eigenanteil"; WP unverändert.
- [x] **Anmeldeseite neu** (in Phase 130, da der Login dort ohnehin
      angefasst wird): zweispaltiges Layout nach dem Muster SingleKey ID –
      links Friondo-Logo, Überschrift „Anmeldung", Benutzerwahl, PIN-Feld,
      Häkchen „Auf diesem Gerät angemeldet bleiben" (nur Außendienst/
      Montage), Knopf „Anmelden", darunter Fehlermeldungen (Sperre); rechts
      das Energiehaus-Foto bildschirmhoch (`Layout - Logo\anmeldung-
      energiehaus-2000.jpg` nach `app/static/anmeldung-energiehaus.jpg`
      kopieren, 0,4 MB, `object-fit: cover`). Farben nur über die Tokens des
      Design-Systems v14 (`--friondo-blau`, `--friondo-dunkel`), keine
      externen Schriften/CDNs. Unter 900 px eine Spalte: Foto als schmales
      Kopfbild (max. 180 px) über dem Formular, auf dem Handy ohne Foto bei
      weniger als 500 px Breite. Login-Logik unverändert (Phase 130).
      Screenshot vorher/nachher nach `docs/design-v27/`.

## Zulieferungen IT (nachgelagert – blockieren keine Phase)

Diese Punkte verbessern den Betrieb, sobald die IT erreichbar ist; bis
dahin gilt jeweils der Zwischenstand aus Phase 129. Claude Code legt die
Liste zusätzlich als `docs/betrieb-it-uebergabe.md` ab (eine Seite, zum
Weitergeben an die IT).

- **Dienstkonto** für den Tool-Dienst (lokaler Dienstaccount oder gMSA) mit
  Schreibrecht auf Projektordner und `data\` – Zwischenstand: Konto SYSTEM.
- **Backup-Ziel** als Netzlaufwerk/UNC mit Schreibrecht, Aufbewahrung 90
  Tage, Einbindung in die zentrale Sicherung – Zwischenstand: Ordner auf
  fr-wts-02 oder OneDrive/SharePoint als `BACKUP_ZIEL`.
- **Reverse-Proxy mit HTTPS** (IIS mit ARR, Caddy oder nginx), internes
  Zertifikat, DNS-Name (Vorschlag `tool.friondo.local` [ANNAHME]) →
  `http://127.0.0.1:8000`, danach Port 8000 nur noch lokal – Zwischenstand:
  HTTP im Firmennetz wie heute.
- **VPN für den mobilen Außendienst: vorhanden** (WireGuard, Stand
  06.10.2026 – der Außendienst arbeitet darüber bereits mit dem Tool). IT
  nur noch für zusätzliche WireGuard-Profile, wenn mit den 50 Nutzern neue
  Geräte dazukommen; `docs/mobilzugriff.md` entsprechend als „umgesetzt
  (Variante A)" kennzeichnen (Phase 127).
- **Monitoring**: `GET /health` alle 60 s, Alarm bei HTTP ≠ 200 oder
  `status ≠ ok` länger als 5 Minuten, Empfänger Andreas + IT –
  Zwischenstand: Wächter-Aufgabe auf dem Server + `health-pruefen.ps1` auf
  fr-wts-02 + Admin-Glocke.
- **Serverausbau** (4 vCPU / 8 GB / SSD) nur, wenn der Lasttest es verlangt;
  zentral verwalteter Virenscanner: Ausnahme für `data\`; Windows-Updates
  des Servers nur im Wartungsfenster.
- Später/Option: Anmeldung über Microsoft 365 (Entra ID) statt PIN – eigener
  Plan, wenn gewünscht.

## Zulieferungen / bewusst offen (Andreas)

- Bestätigung der [ANNAHME]-Werte: Lastmodell (Phase 127), Zielwerte und
  Entscheidungsregel (Phase 131), PIN-Mindestlänge 6 bzw. Passwort für
  Büro-Rollen, Sitzungsdauern 12 h / 30 Tage, Wartungsfenster Dienstag
  18:30–19:30, DNS-Name.
- Befund aus der Ist-Aufnahme (Phase 127) kann einzelne Checkboxen in Phase
  129 verändern (z. B. wenn der Server bereits als Aufgabe läuft).
- Nicht Teil dieses Plans: PostgreSQL-Umstieg (nur Entscheidungsregel),
  Microsoft-365-Login, Fern-Signatur-Route, Erfassungsliste als
  Vorgangs-Sicht und Online-Signatur (→ PLAN_V18).
