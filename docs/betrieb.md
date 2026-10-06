# Betrieb Friondo Angebotstool – Runbook (v27, PLAN_V17 Phase 129/132, Stand 06.10.2026)

Für die IT und für Andreas: Schritt für Schritt, was im laufenden Betrieb zu
tun ist. Alle Befehle werden auf dem Server in einer **Eingabeaufforderung als
Administrator im Projektordner** ausgeführt (`cd /d C:\Users\kdadmin\Desktop\Angebotstool`),
sofern nichts anderes steht. Einrichtung des Dienstes: `docs/installation-terminal-server.md`
Abschnitt 4; Update-Ablauf im Detail: `docs/updates.md`; offene Punkte für die IT:
`docs/betrieb-it-uebergabe.md`.

| Was | Wert |
|---|---|
| Server, Projektordner | `C:\Users\kdadmin\Desktop\Angebotstool` (Git-Arbeitskopie, `update.bat`) |
| Adresse | `http://192.168.35.4:8000` (Firmennetz und WireGuard-VPN), `GET /health` ohne Anmeldung |
| Betrieb | Windows-Dienst `FriondoAngebotstool` (NSSM, Weg A) oder Aufgabe „Friondo Angebotstool“ (Weg B), Konto SYSTEM, plus Wächter-Aufgabe alle 5 Minuten |
| Entwicklungs-PC | fr-wts-02, `C:\Users\a.scheelen\Tools\Angebotstool` (Claude Code, Tests, `git push`) |
| Wartungsfenster | Dienstag 18:30–19:30 [ANNAHME] – Updates nur dort, Hotfixes nur mit Freigabe von Andreas und Banner ≥ 30 Minuten vorher |
| Technik | FastAPI/uvicorn, SQLite (WAL) in `data\angebotstool.db`, Python 3.12+ in `venv\` |

## Ist 10/2026

_Stand der Aufnahme 06.10.2026 (Agent F, aus den Projektdateien; Server-Werte mit Platzhalter
„[Andreas: …]“ liest Andreas auf dem Server ab und trägt sie hier nach). Befund „läuft in einer
Benutzersitzung“ = Risiko Nr. 1 – beseitigt durch den Dienst (Abschnitt „Dienst starten/stoppen/
neustarten“, `scripts\dienst-installieren.bat`)._

| Merkmal | Befund | Quelle |
|---|---|---|
| Startweg (Server) | Konsolenfenster „Friondo Angebotstool Server“ aus `start.bat` (`start "Friondo Angebotstool Server" /min venv\Scripts\python.exe -m uvicorn app.main:app --host 0.0.0.0 --port 8000`) in der Benutzersitzung **kdadmin**; keine Aufgabe der Aufgabenplanung, kein Dienst. **Befund „läuft in einer Benutzersitzung“ = Risiko Nr. 1** (Abmelden/Fensterschließen beendet das Tool; Pool-Parameter greifen erst nach Neustart des Fensters). `update.bat` ruft `schtasks /End` und `/Run "Friondo Angebotstool"` – ohne angelegte Aufgabe wirkungslos (daher die Anweisung „Fenster schließen, start.bat neu starten“). | `start.bat`; CLAUDE.md „Hotfix 06.10.2026 → Antworten Andreas“; `docs/nach-dem-update-v26.md` Z. 107-109; `update.bat` |
| Vorbereitete, nicht aktive Startwege | Variante A `scripts\dienst-installieren.bat`: Aufgabe „Friondo Angebotstool“ `/SC ONSTART /RU SYSTEM`, Aufruf `venv\Scripts\python.exe -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --app-dir <Projekt>`, legt Firewall-Regel an; Variante B NSSM (Anleitung). Entfernen: `scripts\dienst-entfernen.bat`. PLAN_V17 Phase 129 sieht NSSM-Dienst vor. | `scripts/dienst-installieren.bat`; `docs/installation-terminal-server.md` Abschnitt 4 |
| Projektpfad Server | `C:\Users\kdadmin\Desktop\Angebotstool` (Git-Arbeitskopie Entwicklung: `C:\Users\a.scheelen\Tools\Angebotstool`). Die IT-Anleitung nennt noch `C:\Friondo\Angebotstool` (veraltet). | PLAN_V17 Kopf; `docs/nach-dem-update-v26.md` Z. 123-124; `docs/installation-terminal-server.md` Abschnitt 2 |
| Uvicorn-Aufruf | `python -m uvicorn app.main:app --host 0.0.0.0 --port 8000` – ein Prozess, keine `--workers`, kein `--proxy-headers`; Threadpool wird in `lifespan` über den anyio-Limiter auf `WORKER_THREADS` (Standard 64) gesetzt; alle Routen `def` (Threadpool). | `start.bat`; `app/main.py:41-44`; `app/config.py` |
| Firewall-Regel | Regel „Friondo Angebotstool“ (TCP 8000 eingehend) legt nur `dienst-installieren.bat` an; bei Start über `start.bat` ist unbekannt, ob/wie Port 8000 freigegeben ist (Zugriff aus dem Firmennetz funktioniert, also existiert eine Freigabe). **[Andreas: `netsh advfirewall firewall show rule name="Friondo Angebotstool"` bzw. `netsh advfirewall firewall show rule name=all \| findstr 8000`]** | `scripts/dienst-installieren.bat` Schritt 5 |
| Python-Version | Entwicklung: **3.14.7** (`venv\Scripts\python.exe`); IT-Anleitung nennt 3.12. Server: **[Andreas: `venv\Scripts\python --version` auf dem Server]** | `venv`; `docs/installation-terminal-server.md` Abschnitt 1 |
| Bibliotheken | Entwicklung: SQLAlchemy 2.1.1, FastAPI 0.142.2, uvicorn 0.54.0, SQLite 3.50.4. `requirements.txt` ohne Versions-Pins (fastapi, uvicorn[standard], sqlalchemy, jinja2, python-multipart, openpyxl, fpdf2, python-dotenv, msal; httpx nur Tests) → Server-Stand kann abweichen **[Andreas: `venv\Scripts\pip freeze` auf dem Server]**. | `requirements.txt`; venv-Abfrage |
| Datenbank | SQLite, Datei `data\angebotstool.db`, WAL-Modus, `synchronous=NORMAL`, `busy_timeout=5000` je Verbindung; SQLAlchemy QueuePool `pool_size` 20 / `max_overflow` **70** (Standard in `app/config.py` am 06.10.2026 von 40 auf 70 angehoben; `.env.example` nennt noch 40) / `pool_timeout` 10 s; `expire_on_commit=False`, `autoflush=False`. Start-Invariante Pool ≥ Threads + Scheduler + 5. | `app/db.py:13-29, 130-141`; `app/config.py:71-79`; `.env.example` |
| Größe `data\` | Entwicklungs-PC (Anhalt): `angebotstool.db` 4,7 MB (+ `-wal` 4,3 MB, `-shm` 32 KB), `angebote` 51 MB, `projekte` 1.011 MB, `backups` 28 MB. Server: **[Andreas: Explorer → Eigenschaften von `data\`, `data\angebote`, `data\projekte`, `data\backups`; WAL-Größe künftig in /health `wal_mb`]** | `du -sh`/`ls` auf dem Entwicklungs-PC |
| Benutzer je Rolle | Entwicklungs-DB (Spalte `rolle`, alle `aktiv=1`): admin 1, aussendienst 13, innendienst 3, montage 1 – Summe 18; die Mehrfachrollen-Spalte `rollen` ergänzt keine weitere Rolle (leadmanagement/projektierung als Hauptrolle: 0). Server (Ziel 50 Nutzer): **[Andreas: Benutzerverwaltung]** | `sqlite3`-Zählung (nur Zahlen) |
| CPU/RAM Server | **[Andreas liest im Task-Manager ab: Kerne, RAM gesamt/frei, `python.exe` Arbeitsspeicher]**; ab v27 liefert /health `prozess.rss_mb`, `cpu_s`, `threads`. | `app/betrieb.py:73-104` |
| Zugangswege | Firmennetz: `http://192.168.35.4:8000` (fester Standard `BASIS_URL` in `app/config.py`; README nennt noch den Platzhalter `<SERVERNAME-EINTRAGEN>`); Außendienst mobil über **WireGuard-VPN (vorhanden)** – `docs/mobilzugriff.md` steht noch auf „Entscheidung offen“ und ist als umgesetzt (Variante A) zu kennzeichnen; kein HTTPS/Reverse-Proxy (`HTTPS_AKTIV` 0), Cookie ohne `secure`. | `app/config.py:83`; `README.md` Z. 9-14; `docs/mobilzugriff.md`; PLAN_V17 Phase 127 |
| Backup heute | Beim App-Start `db.taegliches_backup()` (SQLite-Backup-API, eine Datei je Tag, 30 Tage) – bei Dauerbetrieb ohne Neustart also **kein tägliches Backup**; Übergangslösung Aufgabe „Friondo Backup“ 02:30 (`scripts\backup-nacht.bat` → Backup-API + robocopy nach `BACKUP_ZIEL`, Standard `D:\Backup\Angebotstool`, Log `data\backup-nacht.log`) – ob die Aufgabe auf dem Server angelegt ist: **[Andreas: `schtasks /Query /TN "Friondo Backup"`]**. v27: Scheduler-Lauf „backup“ 02:30 im Prozess (lokal + Spiegelung, Ergebnis in Einstellung `backup_letztes`) ersetzt die Aufgabe – nicht beides parallel betreiben. | `app/db.py:164-188`; `scripts/backup-nacht.bat`; `docs/nach-dem-update-v26.md` Z. 115-150; `app/betrieb.py:297-364` |
| Hintergrundläufe | 8 Modul-Threads (monday_sync, mail_sync [+ sub_mail, outlook_kalender, terminmail], ablauf_pruefung, benachrichtigungen, lead_parser, leadmanagement, geocoding, lead_mail) + 4 v27-Läufe im Scheduler-Rahmen (backup 02:30, sqlite-pflege 02:40, betrieb-wache 5 min, login-protokoll 03:10) + Device-Flow-Thread der Graph-Anmeldung (ohne DB) – alle im Uvicorn-Prozess, kein weiterer Dienst. Details Teil 2 B. | `app/main.py:47-88`; `app/betrieb.py:486-497` |
| Protokolle | `data\fehler.log` (Datei-Log, Pool-Status je Eintrag) + Tabelle `fehlerprotokoll`; v27 `data\log\zugriff.log` (RotatingFileHandler 10 × 10 MB, je Anfrage Dauer/Status/Pool-Checkouts; Auswertung 24 h in Parametrierung → Betrieb); `data\backup-nacht.log`, `data\backups\ziel.log`. Server-Logs der Störung vom 06.10.2026 (`diagnose\fehler-server-2026-10-06.log`, `diagnose\server-2026-10-06\angebotstool.db`) liegen in der Arbeitskopie **noch nicht** vor. | `app/fehlerprotokoll.py`; `app/zugriffslog.py`; `ls diagnose/` |
| Update-/Rollback-Weg | `update.bat` als Administrator: Aufgabe stoppen → Backup `data\backups\update_<Zeit>` (DB + .env) → `git pull --ff-only` → `pip install` → `migrate.py` → Aufgabe starten; `rollback.bat` vorhanden. Wartungsfenster-Standard v27: Dienstag 18:30–19:30 [ANNAHME]. | `update.bat`; `app/betrieb.py:31-34` |
| Hotfix-Stand | Störung `QueuePool limit of size 5 overflow 10 reached … timeout 30.00` am 06.10.2026; Maßnahmen (Pool 20+40/10 s, Middleware-Sitzung vor `call_next` zu, `verbindung_freigeben` vor jedem Netzaufruf, Upsert in `routing_cache`/`geocode_cache`) sind im Code (Marker `# Hotfix 06.10.2026`, 29 Aufrufe von `verbindung_freigeben` in 21 Modulen) und laut Doku ausgerollt. | CLAUDE.md „Hotfix 06.10.2026“; grep `verbindung_freigeben` |

## Inventar Datenbanksitzungen & Netzaufrufe

_Arbeitsliste für PLAN_V17 Phase 128 (Stand der Aufnahme 06.10.2026, vor den Umbauten der
Agenten A und D – Spalte „Maßnahme v27“ nennt die seither umgesetzte Maßnahme; Zeilennummern
gelten für den gelesenen Stand). Ergebnis nach v27: alle Scheduler-Läufe über `app/scheduler.py`
mit `db.kurz()`-Blöcken, Importe in Blöcken mit Commit, Mail-Ausgangswarteschlange `mail_ausgang`,
Geocoding-Backoff, keine zweite Sitzung je Anfrage mehr (Befunde B7/B8 behoben), B11 behoben;
der Wächter-Test `tests/test_v27_sitzungen.py` meldet 0 Verstöße. Jeder Plan mit neuen Netzaufrufen
ergänzt diese Tabelle._

Ergebnis vorweg: **Keine Stelle gefunden, an der nach dem Hotfix noch eine Pool-Verbindung während
Netz-I/O gehalten wird** – alle 6 Netzmodule (`geocoding`, `graph_versand`, `heizreport_api`,
`mail_sync`, `monday_sync`, `routing`) und ihre Aufrufer rufen vor dem Netzaufruf
`verbindung_freigeben(session)` (bzw. `session.commit()`) auf oder ermitteln Token/Konto vor
`SessionLocal()`. Die Befunde betreffen deshalb die *Form* der Freigabe (Sitzung bleibt offen),
lange Schreibtransaktionen, zweite Sitzungen je Anfrage und den Übergangszustand der Scheduler.

| Nr. | Datei:Zeile | Befund (kurz) | Vorschlag |
|---|---|---|---|
| B1 | `app/main.py:55-76`, `app/*.py scheduler_starten()` (ablauf_pruefung:79, benachrichtigungen:298, geocoding:213, lead_mail:513, lead_parser:293, leadmanagement:1324, mail_sync:246, monday_sync:341) | 8 Hintergrundläufe starten noch eigene `threading.Thread`-Schleifen mit `time.sleep` und `except Exception: pass` (kein Log); `monday_sync.sync()` und `mail_sync.sync()` laufen **sofort beim Start ohne Versatz**. `db.pool_invariante(scheduler.anzahl())` (main.py:79) zählt nur die 4 registrierten v27-Läufe → 8 Threads fehlen in der Invariante. | Phase 128: alle 8 auf `scheduler.registrieren` umstellen (Agent A), danach stimmt die Invariante (64 + 12 + 5 = 81 ≤ 20 + 70). |
| B2 | Hintergrundläufe mit **einer** Sitzung über den ganzen Lauf: `mail_sync.py:163-205`, `monday_sync.py:233-258`, `geocoding.py:171-207`, `lead_parser.py:308-312`, `lead_mail.py:489-507`, `outlook_kalender.py:161-208`, `sub_mail.py:186`, `terminmail.py:102`, `benachrichtigungen.py:191/248`, `leadmanagement.py:1252/1345/1356/1366` | Hotfix-Form „Session offen, Verbindung per commit frei“ – pool-sicher, aber die Phase-128-Regel verlangt für Hintergrundläufe „lesen → Sitzung schließen → Netz → neue kurze Sitzung“. Nebenwirkung: jede Freigabe ist ein Commit mitten im Lauf (best effort je Eintrag, kein Rollback des Laufs mehr möglich). | Phase 128: `with db.kurz()`-Blöcke je Eintrag/Block (Agent A); Zurückschreiben in eigener kurzer Sitzung. |
| B3 | `app/monday_sync.py:272-333` (`_quelle_syncen`) | **Lange Schreibtransaktion:** nach dem Board-Abruf werden alle Items einer Quelle (Lead, Kunde mit `flush` Z. 224, Vorgang) in EINER Transaktion geschrieben; Commit erst bei der Freigabe der nächsten Quelle (Z. 271) bzw. Z. 248. Bei großen Boards hält der Sync die SQLite-Schreibsperre für die gesamte Verarbeitung (auch beim manuellen Vollabgleich `routers/leads.py:134` im Request-Thread). | Commit je 25 Items (Blöcke, Agent D/A); Vollabgleich als Scheduler-Lauf „jetzt ausführen“ statt im Request. |
| B4 | `app/routers/konfiguration.py:1232-1255` + `app/bestandsimport.py:537-562` | **Lange Schreibtransaktion:** Bestandsimport schreibt die ganze Datei (je Zeile Kunde, externes Angebot, Vorgang, Gewerk; `flush` je Zeile) in einer Transaktion, Commit erst in der Route Z. 1252. Kein `import_markieren`. | Phase 128: Blöcke je 25 Zeilen mit Commit, `with betrieb.import_markieren("Bestandsimport")` (Agent D). |
| B5 | `app/import_preisliste.py:399-418`, `app/import_pv.py:240-260`, `app/import_klima.py:508-540` | Artikel-Importe: ein Commit am Ende (alle Artikel in einer Transaktion); danach `logik.neu_einlesen` (Excel + Artikelprüfung, nur lesen) in derselben Anfrage. Kein `import_markieren`, keine Sperre gegen parallelen zweiten Import. | Phase 128: Blöcke + `import_markieren` (Agent D); Dauer über Zugriffsprotokoll messen. |
| B6 | `app/leadmanagement.py:1247-1318` (`taeglicher_lauf_leads`), `:1379-1452` (`loeschlauf`) | **Lange Schreibtransaktionen** (1×/Tag): Tageslauf reaktiviert Wiedervorlagen, rechnet `sla_status` je offenem Lead, legt Glocken an, legt Veranstaltungen an – ein Commit Z. 1314 (Sofort-Mails committen zwischendurch). Löschlauf: N+1-Abfragen je Vorgang, Anonymisierung aller Kandidaten in einer Transaktion, Commit Z. 1451 (nur bei `loeschlauf=an`, Standard aus). | Phase 128: Kandidaten lesen → Blöcke je 25 mit `db.kurz()` (Agent A). |
| B7 | `app/routers/lm_boards.py:37` (`lm_demo_badge`, Jinja-Global in `leadmanagement/_nav.html`, 10 Templates) | **Zweite Sitzung je Anfrage:** beim Rendern jeder Lead-Management-Seite öffnet das Template eine eigene `SessionLocal()`, während die Request-Sitzung (`get_session`) noch offen ist → kurzzeitig 2 Pool-Verbindungen je Lead-Seite (bei 6 Lead-Nutzern + Boards relevant). | Wert in der Middleware (`auth._laden`, dort wird `lead_modul_ok` ohnehin ermittelt) nach `request.state` legen bzw. über `render(...)` mitgeben; Global entfernen. |
| B8 | `app/auth.py:494` → `app/betrieb.py:184` (`wartungshinweis_aktuell`) | Zweite Sitzung innerhalb der Middleware-Sitzung (nur beim 60-s-Cache-Ablauf): `_laden` hält seine Sitzung, `wartungshinweis_aktuell()` öffnet eine weitere. | Middleware-Sitzung durchreichen (`wartungshinweis(session)` + Cache) – kleine Änderung in `app/auth.py`/`app/betrieb.py`. |
| B9 | `app/geocoding.py:112`, `app/routing.py:136`, `app/kalender.py:57/132/153/172`, `app/projektierung.py:223`, `app/benachrichtigungen.py:139` | Freigabe = **Commit mitten in Anfragen**: z. B. AD-Profil speichern (`routers/benutzer.py:295-304`: `flush` → `geokodieren` committet die halbfertigen Profiländerungen vor dem Netzaufruf), Glocke mit Sofort-Mail (`kern.benachrichtigen` committet den Aufrufer-Stand VOR der Mail – im Hotfix bewusst). Kein Pool-Problem, aber ein späterer Fehler in der Route kann nichts mehr zurückrollen. | Phase 128: Netzaufrufe vor den ersten Schreibzugriff ziehen (Geocoding/Routing zuerst, dann schreiben) bzw. Mail-Ausgangswarteschlange `mail_ausgang` (Versand nach Commit per Scheduler). |
| B10 | `app/routers/leads.py:128-139`, `app/routers/konfiguration.py:448-459`, `app/routers/angebote.py:1081-1182`, `app/routers/betrieb.py:125-133` | **Lange Anfragen im Worker-Thread** (pool-sicher, aber Thread minutenlang belegt): monday-Vollabgleich (3 Quellen × Seiten × ≤ 30 s), monday-Übersicht (6 Aufrufe × ≤ 30 s), E-Mail-Entwurf (PDF + 2–5 Graph-Aufrufe × ≤ 60 s), „Backup jetzt“ (robocopy bis 3600 s, bei UNC-Ziel Datei-I/O über das Netz). | Lastmodell/Zielwerte (Phase 131) berücksichtigen; Vollabgleich und Backup als Scheduler-Lauf „jetzt ausführen“ mit Rückmeldung statt synchron. |
| B11 | `app/routers/signatur.py:269-274` | Fern-Signatur (Standard aus) gibt die Verbindung per `session.commit()` statt `verbindung_freigeben` frei – fachlich gleich, Muster abweichend (Code-Review-Regel „jeder Netzaufruf ohne Freigabe davor ist ein Fehler“ greift per grep nicht). | `verbindung_freigeben(session)` verwenden (nur Lesbarkeit). |
| B12 | `app/mail_sync.py:178-199` | Laufdauer: je nicht archiviertem Angebot in Status Versand vorbereitet/Versendet/Angenommen/Abgelehnt ein Graph-Abruf (≤ 60 s) alle 15 min – Dauer wächst mit dem Bestand und kann das Intervall übersteigen (heute keine Single-Flight-Sperre im Modul-Thread, nur sequenziell). | Scheduler-Rahmen (Single-Flight) + Eingrenzung auf „Versand vorbereitet“ und Angebote mit Aktivität < 90 Tage (fachliche Rückfrage). |

Lesehilfe: „hält Sitzung während Netz-I/O“ = Pool-Verbindung während des Netzaufrufs belegt (Stand
nach Hotfix). „nein – Freigabe Z. n“ heißt: `verbindung_freigeben` (= commit) unmittelbar vor dem
Aufruf, das Session-Objekt bleibt offen und holt sich danach eine neue Verbindung; „Token vor
Sitzung“ heißt: msal-Token/Konto werden vor `SessionLocal()` ermittelt. „–“ = kein Netzaufruf.
Dauer-Anhalte: weder Tests noch Doku nennen Sekundenwerte für Importe/PDFs – die Messbasis ist das
v27-Zugriffsprotokoll (`data\log\zugriff.log`, p50/p95 je Route in Parametrierung → Betrieb).

#### A. Alle `SessionLocal()`-Stellen in `app/` (28 Treffer, Stand 06.10.2026)

| Modul | Funktion | Auslöser (Anfrage/Scheduler/Import) | Intervall | Netzaufruf | hält Sitzung während Netz-I/O (Stand nach Hotfix) | Schreibtransaktion | Maßnahme v27 |
|---|---|---|---|---|---|---|---|
| `app/ablauf_pruefung.py:41` | `lauf()` (eigene Sitzung, wenn keine übergeben) | Scheduler (Modul-Thread „ablauf-pruefung“) | 24 h, erster Lauf 120 s nach Start | – | – | ja: alle fälligen Angebote + Erfassungen + Protokoll-Einstellung in einer Transaktion, Commit Z. 68 (kleine Mengen) | Phase 128: Scheduler-Rahmen (Agent A) |
| `app/auth.py:349` | `_sitzungszaehler()` (für `cookie_wert` ohne Zähler: Tests/Crawl/Abnahme) | Anfrage (selten) | je Aufruf | – | – | nein | keine (kurz, `close` im finally) |
| `app/auth.py:420` | `standardbenutzer_anlegen()` | Start (`lifespan`) | einmal | – | – | ja: Admin anlegen/Rolle heben, Commit Z. 425/430 | keine |
| `app/auth.py:449` | `RollenMiddleware._laden()` – Benutzer, Glocke (Zähler + letzte 20), Modul-Schalter, HV-Sicht, Wartungsbanner | Anfrage (jede außer `/static`; läuft im Threadpool) | je Anfrage | – | – (Sitzung vor `call_next` geschlossen, Z. 505) | nein | Hotfix erledigt; PRÜFEN B8: Z. 494 `wartungshinweis_aktuell()` öffnet eine zweite Sitzung, solange diese offen ist |
| `app/benachrichtigungen.py:191` | `taeglicher_lauf()` (Fälligkeits-Glocken Projektierung, Datums-Schalter `faellig_lauf_datum`) | Scheduler (Modul-Thread „benachrichtigungen“, ab 07:00) | 5-min-Prüfung, 1×/Tag | indirekt: Glocke → Sofort-Mail Graph (`kern.benachrichtigen` → `mail_senden`) | nein – Freigabe `benachrichtigungen.py:139/146` (+ `projektierung.py:223`) | ja: Glocken + Parameter, Commit Z. 231; Sofort-Mails committen zwischendurch | Phase 128: Scheduler-Rahmen (Agent A); Mail-Ausgangswarteschlange |
| `app/benachrichtigungen.py:248` | `digest_versenden()` (Tagesdigest je Benutzer mit `digest`, Datums-Schalter) | Scheduler (ab 07:15) | 5-min-Prüfung, 1×/Tag | Graph `sendMail` je Benutzer (Timeout 60 s, msal-Token) | nein – Freigabe Z. 139/146 vor jedem Versand | ja: Protokoll + Parameter, Commit Z. 286; Freigabe = Commit je Mail | Phase 128: Scheduler-Rahmen (Agent A) |
| `app/betrieb.py:184` | `wartungshinweis_aktuell()` (Banner, Cache 60 s) | Anfrage (aus der Middleware) | ≤ 1×/60 s | – | – | nein | PRÜFEN B8: Middleware-Sitzung durchreichen |
| `app/betrieb.py:251` | `backup_letztes()` (eigene Sitzung, wenn keine übergeben) | Anfrage `/health`; Scheduler „betrieb-wache“ | je Aufruf / 5 min | – | – | nein | keine (kurz) |
| `app/db.py:75` | `kurz()` Kontextmanager (Scheduler-Status, Backup-Ergebnis, Admin-Glocke, Login-Protokoll-Lauf) | Hilfsfunktion | – | – | – | ja: Commit bei Erfolg, Rollback bei Fehler, immer close | v27-Muster für Phase 128 |
| `app/db.py:528` | `get_session()` FastAPI-Dependency (alle `def`-Routen) | Anfrage | je Anfrage | Netz nur in den Routen aus Abschnitt C | siehe C | je Route | def-Route (Threadpool) |
| `app/fehlerprotokoll.py:199` | `_in_tabelle_schreiben()` (Fehler-Nr., Tabelleneintrag; Pool-Timeout → nur Datei-Log) | Anfrage (Exception-Handler, nach Schließen der Request-Sitzung); `eintragen_text` (Heizreport, Backup, Start) | je Fehler | – | – | ja: 1 INSERT, Retry nach 0,5 s bei „database is locked“ | keine |
| `app/geocoding.py:171` | `hintergrund_lauf()` – ≤ 25 offene Leads, ≤ 25 Termine (60 Tage), alle AD-Startadressen | Scheduler (Modul-Thread „geocoding“) | 5 min, erster Lauf 300 s nach Start | Nominatim/ORS/Google je Adresse (Timeout 8 s; Nominatim 1 Aufruf/s) | nein – Freigabe `geocoding.py:112` vor jedem Aufruf (Sitzung bleibt offen) | ja: Tageszähler + Cache-Upsert + Vorgang/Termin/Profil; Freigabe = Commit je Adresse, Commit Z. 203 | Phase 128: Scheduler-Rahmen (Agent A); Backoff `GeocodeCache.versuche` |
| `app/leadmanagement.py:1252` | `taeglicher_lauf_leads()` – Zurückgestellte reaktivieren, SLA-Digest (rot/frei), Veranstaltungen anlegen/archivieren (`lead_info`), Datums-Schalter `lm_lauf_datum` | Scheduler (Modul-Thread „leadmanagement“, ab 07:00) | 5-min-Prüfung, 1×/Tag | indirekt: Glocken → Sofort-Mail Graph | nein – Freigabe in `mail_senden` | ja: **lange Transaktion** (alle Reaktivierungen, `sla_status` je offenem Lead, Glocken, Veranstaltungen), Commit Z. 1314 | Phase 128: Scheduler-Rahmen (Agent A); PRÜFEN B6 Blöcke |
| `app/leadmanagement.py:1345` | Schleife → `lead_anrufliste.faellige_wiedervorlagen_melden()` (Wiedervorlage-Glocke, Dedup über Aktivität `system`) | Scheduler (Modul-Thread „leadmanagement“) | 5 min, erster Lauf 200 s nach Start | indirekt: Glocke → Sofort-Mail | nein – Freigabe in `mail_senden` | ja: Commit Z. 1348 nur bei Treffern | Phase 128: Scheduler-Rahmen (Agent A) |
| `app/leadmanagement.py:1356` | Schleife → `lead_todos.faellige_glocken()` (To-Do-Glocken, dedupliziert) | Scheduler | 5 min | indirekt: Glocke → Sofort-Mail | nein | ja: Commit Z. 1360 bei Treffern, Rollback bei Fehler | Phase 128: Scheduler-Rahmen (Agent A) |
| `app/leadmanagement.py:1366` | Schleife → `loeschlauf()` (DSGVO-Anonymisierung; nur `loeschlauf=an`, Standard aus; Datums-Schalter) | Scheduler (ab 03:00) | 5-min-Prüfung, 1×/Tag | – | – | ja: Kandidatensuche mit N+1-Abfragen, **Anonymisierung aller Kandidaten in einer Transaktion**, Commit Z. 1451 | Phase 128: Scheduler-Rahmen (Agent A); PRÜFEN B6 Blöcke |
| `app/lead_dashboard.py:476` | `portal_zaehler()` (Jinja-Global `lm_portal_zaehler`, `index.html`) | Anfrage (Startseite „/“) | je Aufruf | – | – | nein | keine – `startseite()` schließt ihre Sitzung vor dem Rendern (keine Doppelbelegung) |
| `app/lead_mail.py:489` | `versand_job()` – ≤ 50 fällige `KommunikationLog`-Einträge je Lauf (protokoll/test/live) | Scheduler (Modul-Thread „lead-mail“) | 60 s, erster Lauf 150 s nach Start | Graph `sendMail` je Eintrag (Timeout 60 s), msal-Token | nein – Freigabe `lead_mail.py:376` vor Token + Versand | ja: Status je Eintrag; Freigabe = Commit je Mail, Commit Z. 503 | Phase 128: Scheduler-Rahmen (Agent A) |
| `app/lead_parser.py:308` | Schleife → `postfach_abrufen()` (nur `parser_modus=an`) | Scheduler (Modul-Thread „lead-parser“) | 2 min, erster Lauf 240 s nach Start | Graph: Inbox-Abruf ≤ 20 Mails (Timeout 60 s) + PATCH `isRead` je Mail | nein – Freigabe Z. 255 (vor Token/Abruf) und Z. 278 (vor jedem PATCH) | ja: `mail_verarbeiten` committet je Mail (Z. 233/238) | Phase 128: Scheduler-Rahmen (Agent A) |
| `app/mail_sync.py:163` | `sync()` – Versand-Erkennung + Mail-Verlauf über alle nicht archivierten Angebote in Versand vorbereitet/Versendet/Angenommen/Abgelehnt; Folgeaktion `_nach_versand` → monday-Rückspielung | Scheduler (Modul-Thread mail_sync, nur bei `GRAPH_CLIENT_ID`) | 15 min, **sofort beim Start** | Graph `messages` je Angebot (Timeout 60 s); monday-Mutation bei erkanntem Versand (30 s); Token + Konto **vor** der Sitzung (Z. 159-162) | nein – Freigabe Z. 188 vor jedem Abruf; `monday_rueckspielung.py:117` | ja: Mails/Status je Angebot; Freigabe = Commit je Angebot, Commits Z. 197/202/224 | Phase 128: Scheduler-Rahmen (Agent A); PRÜFEN B12 Laufdauer |
| `app/main.py:50` | `lifespan` → `monday_sync.quellen_vorbelegen()` | Start | einmal | – | – | ja (Commit in `monday_sync.py:62`, nur bei leerer Tabelle) | keine |
| `app/main.py:184` | `_start_kontext()` (Kacheln „Auf einen Blick“) | Anfrage „/“ und „/angebotstool“ | je Aufruf | – | – | nein | keine; Hinweis Lastmodell: Startseite = 2 Sitzungen nacheinander (Z. 184 und Z. 239) + Jinja-Global |
| `app/main.py:239` | `startseite()` (Projektierungs-/Lead-Kacheln, Demo-Badges) | Anfrage „/“ | je Aufruf | – | – | nein | keine |
| `app/monday_sync.py:233` | `sync()` (eigene Sitzung, wenn keine übergeben) → `_quelle_syncen` je aktiver Quelle, `leadmanagement.nach_sync` | Scheduler (Modul-Thread monday_sync, nur mit `MONDAY_API_TOKEN`) **und** Anfrage `POST /leads/sync` (Request-Sitzung) | 15 min, **sofort beim Start** | monday GraphQL je Quelle, mehrseitig (Timeout 30 s je Seite) | nein – Freigabe Z. 271 vor der Board-Abfrage je Quelle | ja: **alle Items einer Quelle in einer Transaktion** (Lead, Kunde `flush` Z. 224, Vorgang); Commit erst bei der nächsten Freigabe bzw. Z. 248 | Phase 128: Scheduler-Rahmen (Agent A); PRÜFEN B3 Blöcke je 25 Items |
| `app/outlook_kalender.py:161` | `ruecklesen()` – Datum/Dauer gesyncter Projekttermine aus Outlook | Scheduler (Teilschritt von mail_sync) | 15 min | Graph `GET …/events/{id}` je Termin (Timeout 60 s); Token **vor** der Sitzung (Z. 158) | nein – Freigabe Z. 175 vor jedem Abruf | ja: Termin + Verlauf + Fälligkeiten je Änderung; Freigabe = Commit, Commit Z. 206 | Phase 128: Scheduler-Rahmen (Agent A) |
| `app/routers/lm_boards.py:37` | `lm_demo_badge()` (Jinja-Global in `leadmanagement/_nav.html`, 10 Lead-Templates) | Anfrage (beim Rendern jeder Lead-Management-Seite) | je Aufruf | – | – | nein | PRÜFEN B7: zweite Sitzung, während die Request-Sitzung offen ist → Wert über `request.state`/Render-Kontext |
| `app/sub_mail.py:186` | `antworten_abgleichen()` – Antworten der Subs (Konversation) | Scheduler (Teilschritt von mail_sync) | 15 min | Graph `messages` je offener Sub-Anfrage (Timeout 60 s); Token + Konto **vor** der Sitzung (Z. 179-185) | nein – Freigabe Z. 204 vor jedem Abruf | ja: `ProjektMail` je neuer Antwort, `antwort_am`; Freigabe = Commit je Eintrag, Commit am Laufende | Phase 128: Scheduler-Rahmen (Agent A) |
| `app/terminmail.py:102` | `antworten_abgleichen()` – Kundenantworten auf Terminmails | Scheduler (Teilschritt von mail_sync) | 15 min | Graph `messages` je unbestätigtem Termin (Timeout 60 s); Token + Konto **vor** der Sitzung (Z. 95-101) | nein – Freigabe Z. 117 vor jedem Abruf | ja: `ProjektMail` + `kunden_antwort_am`; Freigabe = Commit je Termin, Commit am Laufende | Phase 128: Scheduler-Rahmen (Agent A) |

#### B. Scheduler-Läufe (Stand im Arbeitsverzeichnis: 8 Modul-Threads + 4 registrierte v27-Läufe)

| Modul | Funktion | Auslöser (Anfrage/Scheduler/Import) | Intervall | Netzaufruf | hält Sitzung während Netz-I/O (Stand nach Hotfix) | Schreibtransaktion | Maßnahme v27 |
|---|---|---|---|---|---|---|---|
| `app/monday_sync.py:341` | Thread (ohne Namen) → `sync()` | Scheduler (nur mit `MONDAY_API_TOKEN`) | 15 min, **sofort beim Start**, kein Versatz | monday GraphQL (3 Quellen, mehrseitig, 30 s je Seite) | nein – Freigabe Z. 271 | ja (siehe A, B3) | Phase 128: Scheduler-Rahmen (Agent A) – `registrieren("monday-sync", 900, …, aktiv=Token-Prüfung)` |
| `app/mail_sync.py:246` | Thread (ohne Namen) → `sync()`; Teilschritte nacheinander im selben Thread: `sub_mail.antworten_abgleichen()`, `outlook_kalender.ruecklesen()`, `terminmail.antworten_abgleichen()` | Scheduler (nur bei `graph_versand.konfiguriert()`) | 15 min, **sofort beim Start** | Graph (je Angebot/Sub/Termin ein Abruf, 60 s Timeout), monday bei erkanntem Versand | nein – Freigaben Z. 188 / `sub_mail.py:204` / `outlook_kalender.py:175` / `terminmail.py:117`; Token vor Sitzung | ja, je Eintrag (Freigabe = Commit) | Phase 128: Scheduler-Rahmen (Agent A) – vier getrennte Läufe empfohlen (eigene Laufzeit/Fehler je Teilschritt) |
| `app/ablauf_pruefung.py:79` | Thread „ablauf-pruefung“ → `lauf()` | Scheduler | 24 h, erster Lauf +120 s | – | – | ja (eine Transaktion, klein) | Phase 128: Scheduler-Rahmen (Agent A), `taeglich_um` |
| `app/benachrichtigungen.py:298` | Thread „benachrichtigungen“ → ab 07:00 `taeglicher_lauf()`, ab 07:15 `digest_versenden()` (Datums-Schalter) | Scheduler | 5-min-Prüfung, erster Lauf +180 s | Graph `sendMail` (Digest, Sofort-Mails) | nein – Freigabe `benachrichtigungen.py:139/146` | ja (siehe A) | Phase 128: Scheduler-Rahmen (Agent A) – 5-min-Lauf mit Datumsprüfung beibehalten (Plan-Hinweis) |
| `app/lead_parser.py:293` | Thread „lead-parser“ → `postfach_abrufen()` | Scheduler (Schalter `parser_modus` je Lauf geprüft) | 2 min, erster Lauf +240 s | Graph Inbox + PATCH | nein – Freigabe Z. 255/278 | ja, je Mail | Phase 128: Scheduler-Rahmen (Agent A), `aktiv=` Parameterprüfung („inaktiv (parser_modus aus)“) |
| `app/leadmanagement.py:1324` | Thread „leadmanagement“ → je Durchlauf: (1) Wiedervorlage-Glocke `faellige_wiedervorlagen_melden`, (2) ab 07:00 `taeglicher_lauf_leads` (inkl. SLA-Digest, Veranstaltungen `lead_info.veranstaltungen_anlegen/archivieren`), (3) To-Do-Glocken `lead_todos.faellige_glocken`, (4) ab 03:00 `loeschlauf` | Scheduler | 5 min, erster Lauf +200 s | indirekt Graph (Sofort-Mails über Glocken) | nein – Freigabe in `mail_senden` | ja, je Teilschritt eigene Sitzung (Z. 1345/1356/1366) bzw. in `taeglicher_lauf_leads` | Phase 128: Scheduler-Rahmen (Agent A) – vier Läufe (wiedervorlage-glocke 5 min, lm-tageslauf 07:00, todo-glocken 5 min, loeschlauf 03:00) |
| `app/geocoding.py:213` | Thread „geocoding“ → `hintergrund_lauf()` | Scheduler | 5 min, erster Lauf +300 s | Geocoder je Adresse (8 s) | nein – Freigabe `geocoding.py:112` | ja, je Adresse (Freigabe = Commit) | Phase 128: Scheduler-Rahmen (Agent A) |
| `app/lead_mail.py:513` | Thread „lead-mail“ → `versand_job()` | Scheduler | 60 s, erster Lauf +150 s | Graph `sendMail` je Eintrag | nein – Freigabe Z. 376 | ja, je Eintrag | Phase 128: Scheduler-Rahmen (Agent A) |
| `app/betrieb.py:489` | `backup_lauf()` – `taegliches_backup()` (sqlite3-Backup-API, eigene Verbindungen außerhalb des Pools) + robocopy `backups/angebote/projekte` + `.env` nach `BACKUP_ZIEL`, Ergebnis in `backup_letztes`, Fehler → Fehlerprotokoll + Admin-Glocke | Scheduler (registriert, v27) + Anfrage „Backup jetzt“ | täglich 02:30 | – (bei UNC-Ziel Datei-I/O über das Netz, robocopy-Timeout 3600 s) | – (keine Sitzung während Kopie; Ergebnis per `kurz()`) | ja: 1 Einstellung (kurz) + Glocke | v27 neu (Agent C); PRÜFEN B10 bei „Backup jetzt“ |
| `app/betrieb.py:491` | `pflege_lauf()` → `db.wal_pflege()` (`PRAGMA wal_checkpoint(TRUNCATE)` + `PRAGMA optimize`) | Scheduler (registriert) + Anfrage „Pflege jetzt“ | täglich 02:40 | – | – (`engine.connect()` AUTOCOMMIT, keine Session) | Checkpoint braucht kurz exklusiven Zugriff (`busy` möglich, Ergebnis wird zurückgegeben) | v27 neu |
| `app/betrieb.py:493` | `wache_lauf()` → `health()` (SELECT 1, Pool, Scheduler, Backup, WAL) → Admin-Glocke max. 1/h | Scheduler (registriert) | 300 s, Start +120 s | – | – (`backup_letztes` eigene kurze Sitzung; Glocke über `kurz()`) | ja: Glocke (kurz) | v27 neu |
| `app/betrieb.py:495` | `login_protokoll_lauf()` → `auth.login_protokoll_aufraeumen` (> 90 Tage) | Scheduler (registriert) | täglich 03:10 | – | – | ja (kurz) | v27 neu |
| `app/scheduler.py:226` | `_status_schreiben()` – Tabelle `scheduler_status` nach jedem Lauf | Scheduler-Rahmen | je Lauf | – | – | ja (kurz, 1 Zeile) | v27 neu |
| `app/graph_versand.py:113` | Device-Code-Anmeldung: Thread `warten()` pollt `acquire_token_by_device_flow` | Anfrage `POST /versand/anmelden` | einmalig je Anmeldung (bis Timeout) | login.microsoftonline.com (msal) | – (kein DB-Zugriff) | nein | keine (kein Scheduler, kein DB) |
| `app/lead_termin.py:49-59` | Terminvorschläge-Cache `vorschlaege_cache` (Prozessspeicher, 10 min je Lead und Sicht; geleert bei Adressänderung/Buchung/Absage) | Anfrage (Kundenkartei, Assistent) | Cache-TTL 600 s | – (die Berechnung ruft Routing/Kalender, siehe C) | – | nein | keine (Hotfix nutzt ihn weiter); Lasttest misst Trefferquote |

#### C. Netzaufrufe aus Anfragen (`def`-Routen, Request-Sitzung `get_session`)

| Modul | Funktion | Auslöser (Anfrage/Scheduler/Import) | Intervall | Netzaufruf | hält Sitzung während Netz-I/O (Stand nach Hotfix) | Schreibtransaktion | Maßnahme v27 |
|---|---|---|---|---|---|---|---|
| `app/routers/angebote.py:1081` | `email_entwurf` – `POST /angebote/{id}/email`: PDF erzeugen, Vorlage, Signatur, Fern-Signatur-Token, Graph-Entwurf mit Anhängen | Anfrage (Innendienst) | je Versand | Graph: Token (msal), `angemeldeter_benutzer`, Entwurf + Inline-Bilder + Anhänge (3–6 Aufrufe, je ≤ 60 s) | nein – Freigabe Z. 1110 (vor Token-Prüfung) und Z. 1167 (vor Entwurf); dazwischen PDF + Token-Commit Z. 1131 | ja: Konversations-ID + Status „Versand vorbereitet“, Commit Z. 1182 | def-Route (Threadpool), Hotfix-Freigabe vorhanden; PRÜFEN B10 Dauer |
| `app/routers/vorgaenge.py:~290` | Kombi-Versand (`POST /vorgaenge/{id}/…`): PDFs je Angebot, Broschüren, Graph-Entwurf | Anfrage (Innendienst/Admin) | je Versand | Graph Entwurf + Anhänge (mehrere Aufrufe, je ≤ 60 s) | nein – Freigabe Z. 326 und Z. 376 | ja: Konversation/Status je Angebot + Notiz, Commit danach | def-Route, Freigabe vorhanden |
| `app/monday_rueckspielung.py:91/151` | `uebertragen` / `wert_aktualisieren` / `bei_versand` – Aufrufer: `routers/angebote.py:276/1485/1490/1577/1623/1678`, `routers/meine_angebote.py:300/302/350/381`, `routers/erfassungsliste.py:301`, `lead_boards.py:757`, `projektierung.py:1960`, `mail_sync.py:236` | Anfrage (Statuswechsel Versendet/Abgelehnt, Löschung, neue Version, AD-Rabatt, manuelle Rückspielung) + Scheduler (mail_sync) | je Ereignis | monday GraphQL Mutation (1–2 Aufrufe, Timeout 30 s) | nein – Freigabe `monday_rueckspielung.py:117` bzw. `:172` (nach Lesen von Lead/Quelle/Betrag) | ja: Protokoll am Angebot, Commit Z. 143/147/183/189 | def-Route, Hotfix-Freigabe vorhanden |
| `app/routers/leads.py:128` | `jetzt_aktualisieren` – `POST /leads/sync` → `monday_sync.sync(session)` | Anfrage (Button „Jetzt aktualisieren“) | manuell | monday je Quelle, mehrseitig (3 × n × ≤ 30 s) | nein – Freigabe `monday_sync.py:271` | ja: lange Transaktion je Quelle (B3) | PRÜFEN B3/B10: als Scheduler „jetzt ausführen“ (Phase 128) |
| `app/routers/konfiguration.py:430` | `monday_uebersicht` – `GET /parametrierung/monday` (Spalten + Gruppen je Quelle live) | Anfrage (Admin) | je Seitenaufruf | monday GraphQL 2 × je Quelle (≤ 30 s je Aufruf) | nein – Freigabe Z. 452 | nein (`quellen_vorbelegen` committet nur bei leerer Tabelle) | def-Route, Freigabe vorhanden; PRÜFEN B10 Dauer |
| `app/routers/konfiguration.py:1151` | `golive_testmail` → `golive.testmail_senden` | Anfrage (Admin) | manuell | Graph `sendMail` (msal-Token) | nein – Freigabe `golive.py:146` | ja: Parameter `golive_testmail`, Commit Z. 1157 | def-Route, Freigabe vorhanden |
| `app/routers/konfiguration_heizreport.py:156` | `POST /parametrierung/heizreport/test` → `heizreport_api.verbindung_testen` | Anfrage (Admin) | manuell | Heizreport v2: `/health`, `/`, `/reports` (3 Aufrufe, Timeout 20 s, Warteschlange `ABSTAND_S`) bzw. generisch 1 Aufruf | nein – Freigabe `heizreport_api.py:262` (v2) bzw. `:369` (generisch) je Aufruf | ja: Parameter + Protokoll, Commit Z. 165/167 | def-Route, Freigabe vorhanden |
| `app/routers/projektierung.py:1585` | `POST /gewerk/{id}/heizreport/{aktion}` → `projekt_anlegen` (POST `with-data`; bei Timeout GET `/reports`), `ergebnis_holen` (GET `results`), `pdf_ablegen` (GET `pdf` + signierter Download `DOWNLOAD_TIMEOUT`), `schluessel_eintragen`, `verknuepfung_loesen` | Anfrage (Projektierung) | je Aktion | Heizreport v2 1–2 Aufrufe (+ PDF-Download) | nein – Freigabe `heizreport_api.py:262` je Aufruf, `:1118` vor dem Download | ja: Gewerk-Felder, Verlauf, Aufgaben, Galerie-Eintrag, Steckbrief/FP-Vorbelegung; `flush` im Modul, Commit in der Route | def-Route, Freigabe vorhanden |
| `app/routers/projektierung.py:1234/1257/2141/2281` | Termin anlegen/ändern/verschieben → `outlook_kalender.event_senden` (Outlook-Ereignis im Team-/AD-Kalender) | Anfrage (Projektierung) | je Termin | Graph `events` POST/PATCH (msal-Token, ≤ 60 s) | nein – Freigabe `outlook_kalender.py:90` (vor Token) und `:103` (vor Aufruf) | ja: `outlook_event_id`/`outlook_fehler`, Commit in der Route | def-Route, Freigabe vorhanden (`event_loeschen` hat außerhalb des Moduls keinen Aufrufer) |
| `app/routers/projektierung.py:1273` | Terminbestätigung an den Kunden → `terminmail.senden` | Anfrage | je Termin | Graph Entwurf + `send` (`mail_mit_anhaengen_senden`, 2 Aufrufe) | nein – Freigabe `terminmail.py:68` | ja: `ProjektMail`, Verlauf, Konversations-ID; `flush` Z. 85, Commit in der Route | def-Route, Freigabe vorhanden |
| `app/routers/projektierung.py:1811` | `POST /aufgabe/{id}/sub-mail` → `sub_mail` (Anfrage an Sub mit Fotos ≤ 20 MB, optional Steckbrief-PDF) | Anfrage | je Mail | Graph Entwurf + je Anhang ein Aufruf + `send` (bei vielen Fotos viele Aufrufe) | nein – Freigabe `sub_mail.py:132` (nach Anhängen/PDF/Absender/CC) | ja: `ProjektSub`, `ProjektMail`, Verlauf, Aufgabenauswahl; Commit in der Route | def-Route, Freigabe vorhanden |
| `app/bza.py:185-233` | BzA-Kundenmail mit PDF-Anhang (Route Projektierung → BzA) | Anfrage | je Mail | Graph Entwurf + Anhang + `send` | nein – Freigabe `bza.py:209` | ja: `bza_gesendet_am`, `ProjektMail`, Aufgaben erledigt, Verlauf; Commit in der Route | def-Route, Freigabe vorhanden |
| `app/routers/signatur.py:214` | `POST /signatur/extern/{token}` (Fern-Signatur, `SIGNATUR_FERN_AKTIV` Standard aus): signiertes PDF, Status „Angenommen“, Info-Mail | Anfrage (öffentlich per Token) | je Signatur | Graph `sendMail` an das eigene Postfach (`info_mail_senden`, msal-Token) | nein – `session.commit()` Z. 271 mit Hotfix-Kommentar (statt `verbindung_freigeben`) | ja: Commit Z. 271, ggf. Z. 283 | def-Route, Freigabe vorhanden (B11: Muster vereinheitlichen) |
| `app/routers/lm_termin.py:127` | `termin_vorschlaege_json` – `GET /lead-management/lead/{id}/termin/vorschlaege.json` (Kundenkartei, asynchron nach Seitenaufbau; `?neu=1` erzwingt): `_geokodieren_bei_bedarf` (Z. 97-106) → `lead_termin.vorschlaege_json` (Cache 10 min) → `vorschlaege` (Z. 298): `routing.matrix_fuellen` × 2 (Z. 331-332), `kalender.frei_belegt` je Kandidat (Z. 351) | Anfrage (je Kartei-Aufruf ohne Cache-Treffer; Lasttest-Szenario `tests/test_pool_hotfix.py`, 40 parallel) | je Aufruf | Geocoder (8 s) bei fehlenden Koordinaten; ORS/Google-Matrix 2 × (8 s) bei `routing_anbieter` ors/google; Graph `calendarView` je Kandidat (≤ 60 s) bei `kalender_sync` an | nein – Freigaben `geocoding.py:112`, `routing.py:136`, `kalender.py:57` | ja: Geocode-/Routing-Cache (Upsert) + Vorgang-Koordinaten; Commit Z. 106 und Z. 142 | def-Route, Hotfix-Freigabe vorhanden; Cache bleibt |
| `app/routers/lm_termin.py:151` | `termin_assistent` – Seite `GET …/lead/{id}/termin` (V2; gleiche Berechnung wie Zeile zuvor ohne Cache) | Anfrage | je Aufruf | wie oben | nein – wie oben | ja: Commit Routing-/Geocode-Cache | def-Route, Freigabe vorhanden |
| `app/routers/leadmanagement.py:857` | `termin_assistent` (V1, `kern.termin_vorschlaege` Z. 1557: `routing.matrix_fuellen` Z. 1603-1604, `kalender.frei_belegt` Z. 1614) – Pfad wird vom V2-Router verdeckt (`main.py:160`) | Anfrage (V1, praktisch nicht mehr erreichbar) | – | wie oben | nein – Freigaben in den Modulen | ja: Commit Z. 875/880 | def-Route, Freigabe vorhanden; PRÜFEN: V1-Route/Funktion entfernen (tote Strecke) |
| `app/routers/lm_termin.py:223/326/382` | Termin buchen (Assistent/manuell/Vorab) → `lead_termin` (Z. 734 `kalender.termin_schreiben`; Mail-Einträge nur geplant, Versand über `lead_mail`-Scheduler) | Anfrage | je Buchung | Graph `events` POST (≤ 60 s) bei `kalender_sync` an | nein – Freigabe `kalender.py:132` (Rumpf vorher gelesen) | ja: `VotTermin`, Aktivitäten, `KommunikationLog` geplant; Commit in der Route | def-Route, Freigabe vorhanden |
| `app/routers/lm_termin.py:413/477` | Absage (`lead_termin.absagen` Z. 801 `kalender.termin_loeschen`), Verschieben (`termin_aendern`/`termin_schreiben`) | Anfrage | je Aktion | Graph `events` DELETE/PATCH | nein – Freigabe `kalender.py:172` / `:153` | ja: Termin-Status, Storno-ICS/Mail geplant; Commit in der Route | def-Route, Freigabe vorhanden |
| `app/routers/lm_kartei.py:334` | Terminierung aus der Kartei → `lead_kartei.py:331` `kalender.termin_schreiben` | Anfrage | je Buchung | Graph `events` POST | nein – Freigabe `kalender.py:132` | ja: Commit in der Route | def-Route, Freigabe vorhanden |
| `app/leadmanagement.py:1733/1748/1775/1799` | V1 Buchen/Umbuchen/Absagen → `kalender.termin_loeschen/termin_schreiben` | Anfrage (V1-Routen) | je Aktion | Graph `events` | nein – Freigaben `kalender.py` | ja | def-Route, Freigabe vorhanden |
| `app/routers/benutzer.py:299` | AD-Profil speichern → `geocoding.geokodieren(profil.start_adresse)` (Startadresse sofort, best effort) | Anfrage (Admin/AD-Profil) | je Speichern ohne Koordinaten | Geocoder (8 s) | nein – Freigabe `geocoding.py:112` (committet die bereits geflushten Profiländerungen Z. 295) | ja: Commit Z. 304 | def-Route, Freigabe vorhanden; Hinweis B9 (Commit vor Netzaufruf) |
| `app/routers/lm_termin.py:97` / `app/routers/leadmanagement.py:870-875` | `_geokodieren_bei_bedarf` (Kartei-Vorschläge, Assistent) – einmalig synchron, nie erneut nach Fehlschlag | Anfrage | je Lead ohne Koordinaten | Geocoder (8 s) | nein – Freigabe `geocoding.py:112` | ja: Commit Z. 106 / 875 | def-Route, Freigabe vorhanden |
| `app/projektierung.py:199` | `benachrichtigen()` (Glocke; `art` ≠ To-Do) → `benachrichtigungen.sofort_versenden` → `mail_senden` – Aufrufer in Projektierung, Lead-Management, Erfassung, Betrieb (`admins_benachrichtigen`), Scheduler | Anfrage + Scheduler | je Glocke mit Empfänger „sofort“ | Graph `sendMail` je Empfänger (msal-Token, ≤ 60 s), ggf. zweiter Versuch über Fallback-Postfach | nein – Freigabe `projektierung.py:223` (Commit VOR der Mail, bewusst) + `benachrichtigungen.py:139/146` | ja: Commit mitten in der aufrufenden Route (B9) | Hotfix-Freigabe vorhanden; Phase 128: Ausgangswarteschlange `mail_ausgang` (Versand nach Commit per Scheduler) |
| `app/routers/versand.py:14/22` | Versand-Status (`angemeldeter_benutzer` → msal `acquire_token_silent`, kann Token über das Netz erneuern), Anmeldung starten (Device-Flow-Thread) | Anfrage (Innendienst) | je Aufruf | login.microsoftonline.com | – (Route ohne Sitzung) | nein | keine |
| `app/routers/betrieb.py:111` | `POST /parametrierung/betrieb/lauf/{name}` → `scheduler.jetzt_ausfuehren` (synchron, Single-Flight) | Anfrage (Admin) | manuell | je nach Lauf | Route ohne Sitzung; Lauf wie im Scheduler | je Lauf | v27 neu (Agent C); PRÜFEN B10: lange Läufe blockieren die Anfrage bis zum Ende |
| `app/routers/betrieb.py:125/136` | „Backup jetzt“ → `backup_lauf()` (robocopy bis 3600 s), „Pflege jetzt“ → `pflege_lauf()` | Anfrage (Admin) | manuell | – (UNC-Ziel = Datei-I/O über das Netz) | Route ohne Sitzung | ja (kurz) | v27 neu; PRÜFEN B10 |
| `app/routers/betrieb.py:21` | `GET /health` (ohne Login): `SELECT 1`, Pool, Scheduler, Backup, WAL | Anfrage (Wächter/Monitoring) | je Aufruf | – | – (`backup_letztes` eigene kurze Sitzung) | nein | v27 neu |

#### D. Importe

| Modul | Funktion | Auslöser (Anfrage/Scheduler/Import) | Intervall | Netzaufruf | hält Sitzung während Netz-I/O (Stand nach Hotfix) | Schreibtransaktion | Maßnahme v27 |
|---|---|---|---|---|---|---|---|
| `app/import_preisliste.py:399` ← `app/routers/artikel.py:66/79` | Preisliste: `GET /artikel/import` (Vorschau: `lese_dateien` + `berechne_diff`, nur lesen), `POST /artikel/import` → `import_ausfuehren` (Excel lesen → Diff → Artikel anlegen/aktualisieren) | Import (Admin, manuell) | selten (nach Preislisten-Änderung) | – | – (Excel-Lesen vor dem ersten DB-Zugriff; Request-Sitzung belegt die Verbindung nur für Diff + Schreiben) | ja: alle Artikel in **einer** Transaktion, ein Commit Z. 418. Dauer-Anhalt: keine Messung vorhanden **[Zugriffsprotokoll p95 `/artikel/import`]** | Phase 128: Blöcke (Agent D) + `import_markieren("Preisliste")` |
| `app/import_pv.py:240` ← `app/routers/artikel.py:88/99` | PV-Positionslisten: `GET/POST /artikel/import-pv` → `import_ausfuehren` (Ordner `Artikel-Preislisten/PV`), danach `logik.neu_einlesen(session)` (Logik-Excel + Artikelprüfung, nur lesen) | Import (Admin) | selten | – | – | ja: ein Commit Z. 260; anschließend Excel-Lesen der Logik in derselben Anfrage (kein Schreiben). Dauer: keine Messung | Phase 128: Blöcke (Agent D) + `import_markieren("PV")` |
| `app/import_klima.py:508` ← `app/routers/konfiguration.py:656/675` | Klima-Positionslisten: `GET/POST /parametrierung/artikel/kl-import` → `import_ausfuehren` (KL001–KL050, GUID-Anker), danach `logik.neu_einlesen` | Import (Admin) | selten | – | – | ja: `flush` Z. 522, ein Commit Z. 540; `rollback` bei `OSError` in der Route. Dauer: keine Messung | Phase 128: Blöcke (Agent D) + `import_markieren("Klima")` |
| `app/logik.py:1578` ← `app/routers/konfiguration.py:615` | Logik neu einlesen: `POST /parametrierung/neu-einlesen` → `logik_einlesen()` (Excel `konfigurator_logik_v5.xlsx`) → `artikel_pruefen(session)` → Prozess-Cache `_cache` | Import (Admin); implizit beim ersten `hole_logik` nach Start und nach PV-/Klima-Import | selten | – | – (Excel-Lesen ohne DB; Prüfung nur lesend) | nein (nur lesen). Hinweis: Cache ohne Sperre – paralleler Aufruf liest doppelt; während des Einlesens sehen andere Threads den alten Cache (kein Fehler). Dauer: keine Messung | Phase 128: `import_markieren("Logik")` (Agent D) |
| `app/bestandsimport.py:537` ← `app/routers/konfiguration.py:1202/1232/1258` | Bestandsimport: `POST …/bestandsimport/vorschau` (Upload, `einlesen`, `pruefen` – nur lesen; Datei nach `data/backups/bestandsimport/<kennung>.xlsx`), `POST …/ausfuehren` → `importieren` (je Zeile Kunde, externes Angebot, Vorgang, Gewerk über `projektierung.gewerk_anlegen(quelle="bestand")`; `flush` je Zeile), `…/rueckgaengig` | Import (Admin) | einmalig/selten (Altbestand) | – | – | ja: **gesamte Datei in einer Transaktion**, Commit erst in der Route Z. 1252 (Rückgängig: Z. 1269). Dauer: keine Messung (Trockenlauf-Doku `docs/bestandsimport-trockenlauf.md` ohne Zeiten) | Phase 128: Blöcke je 25 Zeilen mit Commit (Agent D) + `import_markieren("Bestandsimport")` |
| `app/monday_sync.py:229` ← `app/routers/leads.py:128` | monday-Vollabgleich „Jetzt aktualisieren“ (`POST /leads/sync`, Request-Sitzung) | Import/Anfrage (Innendienst) | manuell; derselbe Lauf alle 15 min per Scheduler | monday GraphQL je Quelle, mehrseitig (30 s je Seite) | nein – Freigabe Z. 271 je Quelle | ja: Commit je Quelle (Freigabe) bzw. Z. 248; alle Items einer Quelle in einer Transaktion (B3). Dauer-Anhalt: 3 Quellen × Seitenzahl × Netzlaufzeit, Minutenbereich möglich – keine Messung | PRÜFEN B3/B10: Blöcke (Agent D) und als Scheduler-Lauf „jetzt ausführen“ (Agent A) |
| `app/stuecklisten.py` ← `app/routers/konfiguration.py:1315` | Stücklisten-CSV-Import (`POST /parametrierung/stuecklisten/import`) | Import (Admin) | selten | – | – | ja: ein Commit Z. 1323 | Phase 128: `import_markieren` (Agent D), nachrangig |
| `app/projektierung_logik.py` ← `app/routers/konfiguration.py:573` | Projektierungs-Steuerdatei hochladen (`POST /parametrierung/projektierung-logik`, `hole_logik(erzwingen=True)`) | Import (Admin) | selten | – | – | ja: Commit Z. 606 | Phase 128: `import_markieren` (Agent D), nachrangig |

#### E. PDF-Erzeugung (fpdf2 – CPU + Datei-I/O, kein Netz)

| Modul | Funktion | Auslöser (Anfrage/Scheduler/Import) | Intervall | Netzaufruf | hält Sitzung während Netz-I/O (Stand nach Hotfix) | Schreibtransaktion | Maßnahme v27 |
|---|---|---|---|---|---|---|---|
| `app/pdf_export.py:891` | Angebot: `pdf_fuer_angebot` → `erzeuge_pdf` (Positionen, KfW, Wirtschaftlichkeit, Nachtexte, Signatur) nach `data/angebote/` – Routen `GET /angebote/{id}/pdf` (`routers/angebote.py:956`), `/meine-angebote/…` (`meine_angebote.py:405`), Signatur (`signatur.py:58/208`), E-Mail-Entwurf (`angebote.py:1117`), Kombi-Versand (`kombi_versand.py:115`), Projektanlage (`projektierung.py:847`) | Anfrage (Innendienst, AD mobil, Kunde Fern-Signatur) | je Aufruf (Lastmodell: 12 Innendienst + 15 AD mit PDF) | – | Sitzung offen während Erzeugung: **ja** (Request-Sitzung liest Angebot, Positionen, Logik, Erfassung/PV-Daten; Rendern selbst ohne DB; keine Pool-Belegung während Datei-I/O nur, wenn vorher committet wurde – Lesetransaktion bleibt offen) | nein (Datei; bei E-Mail-Entwurf/Projektanlage Commit der Route danach). Dauer: keine Messung **[Zugriffsprotokoll p95 `/angebote/{id}/pdf`]** | def-Route (Threadpool); Phase 131 Lasttest misst; ggf. Lesen vor Rendern abschließen (`verbindung_freigeben` vor `erzeuge_pdf`) |
| `app/wirtschaftlichkeit_pdf.py` | Wirtschaftlichkeitsseiten (PV) innerhalb des Angebots-PDF (`pdf_export.py:546/571`; Häkchen `POST /angebote/{id}/wirtschaftlichkeit` blendet aus) | Anfrage (mit Angebots-PDF) | je PV-Angebot | – | wie Angebot | nein | wie Angebot |
| `app/protokoll_pdf.py` | Abfrageprotokoll: `erzeuge_protokoll_pdf` – `GET /angebote/{id}/protokoll.pdf` (`routers/angebote.py:922`), `GET /erfassungen/{id}/protokoll.pdf` (`routers/erfassungsliste.py:126`, 25-Fragen-Protokoll des AD), Projektanlage (`projektierung.py:903`) | Anfrage | je Aufruf (Lastmodell: AD Protokoll-PDF) | – | ja (Request-Sitzung; Daten vorher gelesen, Rendern ohne DB) | nein. Dauer: keine Messung | def-Route (Threadpool) |
| `app/lieferschein_pdf.py` | Lieferschein: `erzeuge_lieferschein` – `GET /angebote/{id}/lieferschein.pdf` (`routers/angebote.py:971`, nur Status Angenommen) | Anfrage | selten | – | ja (Request-Sitzung) | nein | def-Route |
| `app/steckbrief_pdf.py` | Steckbrief: `steckbrief_pdf_bytes` – nur als Anhang der Sub-Mail (`sub_mail.py:113-120`, vor der Freigabe erzeugt); keine eigene Route | Anfrage (Sub-Mail) | je Sub-Mail mit Steckbrief | – (die Mail danach: Graph, Freigabe Z. 132) | ja (Request-Sitzung während Erzeugung; Netz erst nach Freigabe) | nein | def-Route, Freigabe vorhanden |
| `app/bza_datenblatt.py` | BzA-Datenblatt: `erstellen` + `pdf_bytes` – `GET /angebote/{id}/bza-datenblatt.pdf` (`routers/angebote.py:1044`), Dialog `…/bza-datenblatt` (`:1011`, HTML), Gewerk-Seite (`routers/projektierung.py:1440`, nur Felder) | Anfrage | je Aufruf | – | ja (Request-Sitzung) | nein (Response-Bytes) | def-Route |
| `app/montage_formulare.py:133` | Montage-Formulare: `pdf_bytes(session, logik, eintrag, gewerk)` – kein direkter Router-Aufruf gefunden (grep), vermutlich Galerie-Ablage beim Absenden eines Formulars (nicht weiter verfolgt) | Anfrage (Montage) | je Formular | – | ja | ggf. Galerie-Eintrag | def-Route |
| `app/pdf_export.py:854` | Signiertes PDF: `signiertes_pdf_erzeugen` (Signaturbild in Kopie des Angebots-PDF) – `routers/signatur.py:91/246` | Anfrage (Innendienst vor Ort / Kunde Fern-Signatur) | je Signatur | – (Fern: Info-Mail danach, Commit Z. 271) | ja (Request-Sitzung) | ja: Angebot signiert/Angenommen, Commit danach | def-Route, Freigabe vorhanden |
| `app/heizreport_api.py:1089` | Heizreport-PDF: **kein lokales Rendern** – Download vom Heizreport (siehe C) und Ablage in der Galerie | Anfrage | je Aktion | Heizreport GET + Download | nein – Freigabe Z. 1118 | ja: Galerie, Gewerk, Verlauf | def-Route, Freigabe vorhanden |

#### 3.1 Stellen, an denen noch eine Sitzung während Netz-I/O gehalten wird

Keine (Stand 06.10.2026). Geprüft wurden alle 28 `SessionLocal()`-Stellen, alle Aufrufer der sechs
Netzmodule (`grep` auf `graph_versand.*`, `monday_sync.*`, `routing.*`, `kalender.*`,
`heizreport_api.*`, `geocoding.geokodieren`, `outlook_kalender.*`, `terminmail.senden`,
`sub_mail.*`, `bza.*`, `golive.testmail_senden`, `monday_rueckspielung.*`,
`benachrichtigungen.mail_senden`) und die msal-Token-Stellen. Einzige Abweichung im Muster:
`app/routers/signatur.py:271` nutzt `session.commit()` statt `verbindung_freigeben` (B11).

Zwei Einschränkungen zur *Form* der Freigabe (kein Pool-Problem, aber Phase-128-relevant):

1. **Hintergrundläufe halten ein Session-Objekt über den ganzen Lauf** (B2) und geben die
   Verbindung je Iteration per Commit frei. Für die Phase-128-Regel („vor jedem Netzaufruf
   committet **und geschlossen**, danach neue kurze Sitzung“) sind alle Zeilen aus Abschnitt A mit
   Auslöser „Scheduler“ umzustellen: `mail_sync.py:163`, `monday_sync.py:233`, `geocoding.py:171`,
   `lead_parser.py:308`, `lead_mail.py:489`, `outlook_kalender.py:161`, `sub_mail.py:186`,
   `terminmail.py:102`, `benachrichtigungen.py:191/248`, `leadmanagement.py:1252/1345/1356/1366`.
   Vorschlag: je Eintrag `with db.kurz() as s:` lesen → Sitzung zu → Netz → `with db.kurz()`
   zurückschreiben; Lauf-Funktion ohne Argumente für `scheduler.registrieren`.
2. **Freigabe = Commit mitten in Anfragen** (B9): `geocoding.geokodieren:112`,
   `routing.matrix_fuellen:136`, `kalender.*`, `projektierung.benachrichtigen:223` committen den
   bis dahin aufgelaufenen Stand der aufrufenden Route (Beispiel `routers/benutzer.py:295-304`:
   Profiländerungen sind vor dem Geocoder-Aufruf dauerhaft). Vorschlag: in Routen die Netzaufrufe
   vor den ersten Schreibzugriff ziehen (Koordinaten/Routing zuerst, dann Profil/Termin schreiben)
   und für Sofort-Mails die geplante Ausgangswarteschlange `mail_ausgang` (Versand nach Commit durch
   einen Scheduler-Lauf) umsetzen.

#### 3.2 Schreibtransaktionen, die länger als nötig offen sind

| Stelle | Warum lang | Vorschlag |
|---|---|---|
| `app/monday_sync.py:272-333` `_quelle_syncen` | Nach dem Board-Abruf alle Items der Quelle in einer Transaktion (Lead + Kunde mit `flush` Z. 224 + Vorgang); Commit erst bei der Freigabe der nächsten Quelle (Z. 271) bzw. Z. 248. Beim manuellen Vollabgleich zusätzlich im Request-Thread. | Commit je 25 Items (Zähler in der Schleife, `session.commit()`), `gesehen`-Dedup bleibt im Speicher; Vollabgleich über `scheduler.jetzt_ausfuehren("monday-sync")` mit Rückmeldung. |
| `app/bestandsimport.py:537-562` + `routers/konfiguration.py:1232-1255` | Ganze Datei in einer Transaktion (je Zeile Kunde, Angebot, Vorgang, Gewerk, `flush` je Zeile), Commit erst in der Route. Während des Imports hält der Request die SQLite-Schreibsperre; andere Schreiber laufen in `busy_timeout` 5 s → „database is locked“ möglich. | Blöcke je 25 Zeilen mit Commit, Import als Ganzes mit `import_markieren`; Protokoll am `Bestandsimport`-Datensatz fortschreiben (Rückgängig je Block bleibt möglich, da `import_id` je Gewerk gespeichert ist). |
| `app/import_preisliste.py:399-418`, `app/import_pv.py:240-260`, `app/import_klima.py:508-540` | Alle Artikel in einer Transaktion, ein Commit am Ende; anschließend `logik.neu_einlesen` (Excel) in derselben Anfrage (nur lesen). Mengen: Preisliste einige hundert Artikel, PV/Klima ≤ 50 → kurz, aber ohne Messung. | Commit je 100 Artikel; `import_markieren`; Dauer über Zugriffsprotokoll festhalten (Phase 128 Abnahme). |
| `app/leadmanagement.py:1247-1318` `taeglicher_lauf_leads` | Reaktivierungen + `sla_status` je offenem Lead (Abfragen je Lead) + Glocken + Veranstaltungen in einer Transaktion; Sofort-Mails committen zwischendurch (zufällige Transaktionsgrenzen). | Drei Blöcke mit eigenem `db.kurz()`: (1) Reaktivierung, (2) SLA-Digest (nur Glocken, Mail über Warteschlange), (3) Veranstaltungen; Datums-Schalter zuletzt. |
| `app/leadmanagement.py:1379-1452` `loeschlauf` | Kandidatensuche mit 3–4 Abfragen je Vorgang (N+1) und Anonymisierung aller Kandidaten in einer Transaktion (nur bei `loeschlauf=an`). | Kandidaten-IDs lesen, Sitzung schließen, Anonymisierung je 25 Vorgänge in `db.kurz()`; Abfragen über `Vorgang`-Join bündeln. |
| `app/benachrichtigungen.py:240-290` `digest_versenden` | Je Benutzer Mail (Freigabe = Commit) – Transaktionen kurz; der Lauf hält jedoch bis zum Ende dieselbe Sitzung (B2). | Mit dem Scheduler-Rahmen auf `db.kurz()` je Benutzer. |
| `app/mail_sync.py:154-209` `sync` | Transaktionen kurz (Commit je Angebot), aber ein Lauf über alle nicht archivierten Angebote (vier Status) – Laufdauer wächst mit dem Bestand (B12). | Abfrage auf „Versand vorbereitet“ (Erkennung) und Angebote mit Versand < 90 Tage (Verlauf) eingrenzen – **fachliche Rückfrage**; Single-Flight über den Rahmen. |

#### 3.3 Zweite Sitzungen je Anfrage (Pool-Belegung)

- `app/routers/lm_boards.py:37` `lm_demo_badge` (B7): Jinja-Global, 10 Lead-Management-Templates
  → zweite Verbindung während des Renderns jeder Lead-Seite. Vorschlag: in `auth._laden`
  (Z. 471-482 wird bereits `lead_modul_sichtbar`/`demo` ermittelt) `request.state.lm_demo_badge`
  setzen; `_nav.html` liest `request.state`. Alternativ Render-Kontext in den Lead-Routern.
- `app/auth.py:494` → `app/betrieb.py:184` (B8): `wartungshinweis_aktuell()` öffnet beim
  60-s-Cache-Ablauf eine zweite Sitzung innerhalb der Middleware-Sitzung. Vorschlag:
  `wartungshinweis_aktuell(session=None)` – die Middleware reicht ihre Sitzung durch.
- `app/main.py:184/239` Startseite: zwei Sitzungen **nacheinander** (kein Problem), dazu
  `lead_dashboard.portal_zaehler` beim Rendern (Request-Sitzung bereits geschlossen → eine
  Verbindung). Kein Handlungsbedarf.
- `app/fehlerprotokoll.py:199`: eigene Sitzung im Exception-Handler, nachdem `get_session` die
  Request-Sitzung geschlossen hat (FastAPI-Dependency-Abbau vor dem Handler). Kein Handlungsbedarf.

#### 3.4 Übergangszustand Scheduler (für Agent A)

- `app/main.py:55-76` startet die 8 Modul-Threads weiterhin über `scheduler_starten()`;
  `scheduler.starten_alle()` (Z. 87) startet nur die 4 registrierten Betriebsläufe. Die
  Pool-Invariante (Z. 79) rechnet mit `scheduler.anzahl()` = 4; nach Umstellung sind es 12 (so
  auch der neue Kommentar in `app/config.py:74-75`: 64 + 12 + 5 = 81 ≤ 90).
- `monday_sync.scheduler_starten` (Z. 347-355) und `mail_sync.scheduler_starten` (Z. 252-282)
  laufen beim Start **ohne Verzögerung** (kein `sleep` vor dem ersten Lauf) – Startlast parallel
  zu `init_db`/Backup; die anderen sechs warten 120–300 s. Der Rahmen bringt Zufallsversatz
  0–30 s und `start_verzoegerung_s`.
- Alle 8 Schleifen fangen Fehler mit `except Exception: pass` (ohne Log) – mit dem Rahmen landen
  Fehler in `data/fehler.log` und `scheduler_status`.
- `mail_sync.scheduler_starten` prüft `graph_versand.konfiguriert()` je Durchlauf,
  `monday_sync.scheduler_starten` prüft `config.MONDAY_API_TOKEN`, `lead_parser` prüft
  `parser_modus` je Lauf → als `aktiv=`-Callables („inaktiv (kein Token)“) übernehmen.

## Serverressourcen-Check

Empfehlung für 50 Nutzer: **4 vCPU, 8 GB RAM, SSD**; `data\` auf einer
**lokalen Platte** (nie Netzlaufwerk oder OneDrive-/Sync-Ordner – SQLite-WAL
verträgt das nicht); Uhrzeit per **NTP** (Sitzungsablauf, Termine, Backup-Zeiten);
**Virenscanner-Ausnahme für `data\`** (Datei-Sperren durch den Echtzeitscan sind
eine bekannte Ursache für „database is locked“ – zentral verwalteter Scanner →
Punkt an die IT, sonst lokal eintragen). Ein Ausbau des Servers ist IT-Zulieferung
und wird erst nach dem Lasttest (Abschnitt „Lasttest“) entschieden. Andreas liest die
Werte im Task-Manager des Servers ab (Leistung → CPU/Arbeitsspeicher/Datenträger),
Claude Code trägt sie ein:

| Messwert (Server) | Wert | Quelle |
|---|---|---|
| CPU (Kerne) / RAM | [Andreas: Task-Manager → Leistung] | Server |
| Platte für `data\` (lokal? SSD?) | [Andreas: Explorer → Eigenschaften] | Server |
| Größe `data\` (DB, WAL, angebote, projekte, backups) | [Andreas: `dir data /s`] – Entwicklung: DB 4,7 MB + WAL 4,3 MB, angebote 51 MB, projekte 1.011 MB, backups 28 MB | Server / Entwicklungs-PC |
| Python-Version | [Andreas: `venv\Scripts\python --version`] – Entwicklung 3.14.7 | Server |
| Uhrzeit per NTP | [Andreas: `w32tm /query /status`] | Server |
| Virenscanner-Ausnahme `data\` | [Andreas/IT] | Server |
| Lastmessung (nach dem Rollout): p95 je Route, Pool-Spitze | Parametrierung → Betrieb (24 h) | Tool |


## Dienst starten/stoppen/neustarten

Alle drei Skripte erkennen selbst, ob das Tool als Dienst (NSSM), als Aufgabe
oder noch als Konsolenfenster läuft.

| Aufgabe | Befehl | Hinweis |
|---|---|---|
| Zustand anzeigen | `scripts\dienst-status.bat` | kein Administrator nötig: Weg, Zustand, Wächter, Port 8000, Wartungsmarker, Log-Größen, `/health`, letzte Sicherung, letzte Zeilen `ziel.log`/`fehler.log`; Exit 1 = `/health` rot |
| Neu starten | `scripts\dienst-neustart.bat` | stoppt (Port 8000 wird frei gemacht), startet, wartet bis 45 s auf `/health`; angemeldete Nutzer werden kurz getrennt |
| Nur stoppen | `scripts\dienst-neustart.bat --stop` | setzt `data\log\wartung.marker` – der Wächter startet nichts neu, bis `--start` lief |
| Nur starten | `scripts\dienst-neustart.bat --start` | entfernt den Marker nach erfolgreichem `/health` |
| Dienst/Aufgabe einrichten | `scripts\dienst-installieren.bat` | wiederholbar; Anleitung `docs/installation-terminal-server.md` Abschnitt 4 |
| Dienst/Aufgaben entfernen | `scripts\dienst-entfernen.bat` | Daten bleiben erhalten |

Ohne Skripte (Weg A): `net stop FriondoAngebotstool` / `net start FriondoAngebotstool`
oder Dienste-Konsole (`services.msc`, „Friondo Angebotstool“). Weg B:
`schtasks /End /TN "Friondo Angebotstool"` / `schtasks /Run /TN "Friondo Angebotstool"`.
`start.bat` ist nur für den Entwicklungs-PC und bricht auf dem Server mit Hinweis ab.

**Wächter** (`scripts\waechter.ps1`, Aufgabe „Friondo Angebotstool Wächter“ alle
5 Minuten): keine Antwort auf `/health` oder HTTP 503 → Neustart von Dienst bzw.
Aufgabe (höchstens einer je 15 Minuten), Zeile in `data\log\waechter.log`
(Zeit | Befund | Maßnahme); `warn` nur Log-Zeile; eine „ok“-Herzschlagzeile je
Tag. Zusätzlich auf fr-wts-02: `scripts\health-pruefen.ps1` (alle 5 Minuten,
Benachrichtigung an Andreas, Log `C:\Users\a.scheelen\Tools\health.log`; Einrichtung
steht im Kopf des Skripts) und die Admin-Glocke des Tools bei `warn`/`fehler`
(höchstens eine je Stunde).

## Update im Wartungsfenster

Reihenfolge (Rollout-Grundregel, nie zur Arbeitszeit):

1. **Banner setzen** – Parametrierung → Betrieb → Wartungshinweis: von/bis (Vorschlag
   = nächstes Fenster) → „Banner setzen“, mindestens 30 Minuten vorher. Text für alle
   Rollen: „Wartung heute von <von> bis <bis> Uhr – bitte Arbeit bis dahin speichern.
   Das Tool ist in dieser Zeit kurz nicht erreichbar.“
2. **Server-DB-Kopie nach `diagnose\`** (Entwicklungs-PC): jüngste Sicherung
   `data\backups\angebotstool-<Datum>.db` vom Server (oder `BACKUP_ZIEL\backups\`)
   nach `diagnose\test_v<nn>\data\angebotstool.db` kopieren.
3. **`migrate.py` zweimal auf der Kopie:** `venv\Scripts\python migrate.py --db diagnose\test_v<nn>\data\angebotstool.db`
   – zweiter Lauf muss „keine Änderungen nötig“ melden (Idempotenz).
4. **Voll-Crawl + Abnahmeskript:** `venv\Scripts\python scripts\voll_crawl.py --data diagnose\test_v<nn>\data`
   (0 Abstürze) und `venv\Scripts\python tests\abnahme.py` (Exit 0); dazu die
   Testsuite `venv\Scripts\python -m pytest tests -q`.
5. **`git push`** am Entwicklungs-PC (nach Commit; kein Push vor Freigabe).
6. **`update.bat`** auf dem Server als Administrator im Fenster: stoppt (Dienst/Aufgabe
   erkannt, Wartungsmarker), sichert `data\*.db` + `.env` nach `data\backups\update_<Zeit>\`,
   `git pull --ff-only`, `pip install`, `migrate.py`, startet, wartet auf `/health`.
7. **`scripts\smoke.bat`** – läuft am Ende von `update.bat` automatisch (etwa 2 Minuten):
   `/health` ok/warn, Startseite, Erfassungs-/Angebotsliste, Vorgangsakte, Angebots-PDF,
   Hauptboard, Projektierung je HTTP 200 und < 3 s; Ergebnis als Tabelle und in
   `data\log\smoke-<Datum>.txt`. Optional mit echtem Login: `scripts\smoke.bat --pin <PIN>`.
   Rot → Abschnitt „Rollback“.
8. **Banner aus** – Parametrierung → Betrieb → „Hinweis entfernen“ (läuft sonst bis
   „bis“ von selbst aus). Danach `docs/nach-dem-update-v<nn>.md` abarbeiten und
   die Nutzer informieren (Sitzungs-Cookies bleiben bei einem Update gültig).

Hotfixes außerhalb des Fensters nur mit Freigabe von Andreas und Banner ≥ 30 Minuten
vorher. Windows-Updates des Servers ebenfalls nur im Wartungsfenster (IT).

## Rollback

| Fall | Befehl | Wirkung |
|---|---|---|
| Neuer Stand fehlerhaft, Daten in Ordnung (Regelfall) | `rollback.bat --nur-code` | Code auf den Stand vor dem letzten `git pull` (`ORIG_HEAD`), Abhängigkeiten, Neustart; **Datenbank und `.env` bleiben** – seit v27 sind alle DB-Änderungen additiv, der vorherige Code läuft auf der neueren DB weiter; keine Rückfrage, kein Datenverlust |
| Datenbank beschädigt / Migration halb durchgelaufen | `rollback.bat` (optional `rollback.bat data\backups\update_<Zeit>`) | Code zurück **und** Datenbank + `.env` aus der Update-Sicherung – alles seit dem Update Erfasste geht verloren, deshalb Rückfrage (j/n) |

Nach jedem Rollback: alle Nutzer melden sich einmal neu an (Cookies der neueren
Fassung werden abgewiesen); `/health` gibt es erst ab v27 (Stand davor → „HTTP 404“
in der Kontrolle ist normal); `scripts\smoke.bat` bzw. Sichtprüfung im Browser;
Entwicklung informieren (Protokoll `data\log\smoke-*.txt`, `data\fehler.log`).
Rollback-Probe auf der DB-Kopie vor dem Rollout: Ergebnis steht in der Gesamtübersicht
von PLAN_V17.

## Backup und Restore-Test

- **Nächtliche Sicherung im Tool** (Scheduler „backup“, 02:30): SQLite-Backup-API nach
  `data\backups\angebotstool-<Datum>.db` (30 Tage), danach Spiegelung von `backups`,
  `angebote` (inkl. `signiert`), `projekte` und `.env` per robocopy nach **`BACKUP_ZIEL`**
  aus der `.env` (90 Tage am Ziel), Protokoll `data\backups\ziel.log`. Kein Ziel →
  nur lokale Sicherung und `/health` `warn` „kein Backup-Ziel“. Sofortlauf: Parametrierung
  → Betrieb → „Backup jetzt“; von Hand ohne Tool: `scripts\backup-nacht.bat <Zielordner>`.
  Die Hotfix-Aufgabe „Friondo Backup“ ist entfallen (`schtasks /Delete /TN "Friondo Backup" /F`).
- **Ziel-Rangfolge:** Netzlaufwerk der IT (UNC, 90 Tage, zentrale Sicherung; braucht
  ein Dienstkonto mit Schreibrecht – SYSTEM kommt auf Netzfreigaben nicht) → bis dahin
  freigegebener Ordner auf fr-wts-02 oder OneDrive-/SharePoint-Ordner. Die laufende
  Datenbank liegt nie in einem Sync-Ordner.
- **Kontrolle täglich/automatisch:** `/health` (`backup_letztes`, `backup_ziel_status`),
  Betriebs-Seite, Admin-Glocke bei Fehlschlag, Eintrag im Fehlerprotokoll.
- **Restore-Test monatlich (Andreas/IT, ~5 Minuten, kein Administrator nötig, das
  laufende Tool bleibt unberührt):** `scripts\restore-test.bat` [Sicherungsdatei]
  → kopiert die jüngste Sicherung nach `diagnose\restore_<Datum>\data\`, führt `migrate.py --db`
  zweimal darauf aus, lässt `scripts\voll_crawl.py --max-ids 20 --rollen admin,innendienst`
  darüber laufen und schreibt `docs\betrieb\restore-<Datum>.txt` (Zeit, Quelle,
  Migrationsausgabe, Crawl-Zusammenfassung; ohne Kundendaten – der vollständige
  Crawl-Bericht bleibt unter `diagnose\`). Erwartet: `ERGEBNIS: OK`. Alte
  `diagnose\restore_*`-Ordner danach löschen. Echte Wiederherstellung im Ernstfall:
  Tool stoppen (`--stop`), `data\angebotstool.db-wal`/`-shm` löschen, Sicherung nach
  `data\angebotstool.db` kopieren, `migrate.py`, `--start`, Smoke-Test.

## Logdateien

| Datei | Inhalt | Rotation |
|---|---|---|
| `data\fehler.log` | Fehler und Warnungen des Tools (auch uvicorn.error, Start-Zeile mit Version/Commit/Threads/Pool, Pool-Status je Eintrag; Pool erschöpft nur hier) | 1 MB × 5 (Tool) |
| Parametrierung → Fehlerprotokoll | dieselben Fehler mit Traceback in der Datenbank, Pool-Status oben | – |
| `data\log\zugriff.log` | ein Eintrag je Anfrage: Zeit, Benutzer-ID, Rolle, Methode, Pfad, Status, Dauer (Grundlage der Zugriffsstatistik auf der Betriebs-Seite) | 10 MB × 10 (Tool) |
| `data\log\dienst-out.log` / `dienst-err.log` | Konsolenausgabe des Prozesses (uvicorn-Zugriffs- und Startzeilen, Tracebacks beim Absturz) | 10 MB × 5 (NSSM online; Weg B beim Neustart/nachts 04 Uhr durch den Wächter) |
| `data\log\waechter.log` | Wächter: Zeit, Befund, Maßnahme; Herzschlag je Tag | 2 MB × 1 |
| `data\log\wartung.marker` | vorhanden = Wartung läuft (Wächter passiv); `dienst-neustart.bat --start` entfernt ihn | – |
| `data\log\smoke-<Datum>.txt` | Ergebnis je Smoke-Test | von Hand löschen |
| `data\backups\ziel.log` | robocopy-Protokoll der Spiegelung je Backup-Lauf | wächst (von Hand kürzen) |
| `data\backup-nacht.log` | nur Handläufe von `backup-nacht.bat` | – |
| `C:\Users\a.scheelen\Tools\health.log` (fr-wts-02) | Überwachung von außen, Benachrichtigungen | 2 MB × 1 |
| `docs\betrieb\restore-<Datum>.txt` | Restore-Test-Protokolle (gitignored) | – |

## /health-Felder

`GET http://192.168.35.4:8000/health` (ohne Anmeldung, nur Lesen, `Cache-Control: no-store`);
HTTP 200 bei `ok`/`warn`, **HTTP 503 bei `fehler`**. `warn` ist kein Grund für einen Neustart.

| Feld | Bedeutung |
|---|---|
| `status` | `ok` · `warn` (Gründe in `gruende`) · `fehler` (Datenbank nicht erreichbar) |
| `version`, `commit` | Tool-Version (`v27`) und kurzer Git-Commit – Vergleich mit `git log --oneline -1` am Entwicklungs-PC |
| `db`, `db_ms` | `SELECT 1` erfolgreich, Dauer in ms |
| `pool` | `size`, `checked_out`, `overflow`, `maximum`, `prozent` – Verbindungspool (Standard 20 + 70, Timeout 10 s); `warn` ab 70 % |
| `threads` | Threadpool-Größe (`WORKER_THREADS`, Standard 64) |
| `scheduler[]` | je Hintergrundlauf `name`, `letzter_start`, `ok`, `zustand`; `warn`, wenn ein Lauf > 2 Intervalle ohne Start ist |
| `backup_letztes`, `backup_ziel`, `backup_ziel_status`, `backup_ziel_zeit` | letzte lokale Sicherung, Zielordner, Ergebnis der Spiegelung; `warn` bei > 26 h, keinem Ziel oder Fehlschlag |
| `wal_mb` | Größe von `angebotstool.db-wal` (Pflege-Lauf 02:40 setzt sie zurück) |
| `uptime_s` | Sekunden seit dem Start des Prozesses |
| `importe[]` | gerade laufende Importe (Bestandsimport usw.) |
| `schreibsperre_max_ms`, `schreibsperre_locked` | längste gemessene Wartezeit auf die SQLite-Schreibsperre, Zähler „database is locked“ |
| `prozess` | CPU/RAM-Kennzahlen des Prozesses |
| `gruende[]` | Klartext der warn/fehler-Gründe, z. B. „Pool 75 % belegt“, „Scheduler „backup“ ohne Lauf“, „kein Backup-Ziel“, „letztes Backup > 26 h“, „Backup-Spiegelung fehlgeschlagen“, „Pool-Invariante verletzt“ |
| `zeit` | Zeitstempel der Antwort |

## Typische Störungen und erste Maßnahmen

| Störung | Woran erkennbar | Erste Maßnahmen |
|---|---|---|
| **Pool voll** | Meldung „Datenbank-Verbindungen ausgelastet – bitte in einer Minute erneut versuchen (Fehler-Nr. …)“, `/health` `warn` „Pool … % belegt“, Admin-Glocke | 1. Betriebs-Seite: Pool-Spitze, langsamste Anfragen, laufende Importe. 2. `data\fehler.log` (Pool-Status in jedem Eintrag; „Pool erschöpft – nur Datei-Log“). 3. Hält es an: `scripts\dienst-neustart.bat`. 4. Ursache ist fast immer ein Netzaufruf mit offener Sitzung → Fehler-Nr. und Route an die Entwicklung (Regel „keine offene Sitzung während Netz-I/O“) |
| **database is locked** | Fehlermeldung im Tool/Fehlerprotokoll, `schreibsperre_locked` > 0 in `/health`, Nutzer melden „Speichern dauert“ | 1. Virenscanner-Ausnahme für `data\` prüfen. 2. `data\` auf lokaler Platte? (nie Sync-Ordner). 3. `wal_mb` groß → Parametrierung → Betrieb → „SQLite-Pflege jetzt“. 4. Läuft gerade ein Import (Betriebs-Seite)? Importe nur außerhalb der Kernzeit. 5. Dauerhaft → Entwicklung mit Fehlerprotokoll |
| **Dienst steht** | Browser: Seite nicht erreichbar; `scripts\dienst-status.bat`: Port 8000 frei, `/health` keine Antwort; `waechter.log` | 1. `scripts\dienst-status.bat` – liegt `wartung.marker`? (nach abgebrochenem Update → `scripts\dienst-neustart.bat --start`). 2. `data\log\dienst-err.log` und `data\fehler.log` lesen (Traceback beim Start: `.env`, Migration fehlt → `rollback.bat --nur-code` bzw. `update.bat`). 3. Port 8000 von einem anderen Prozess belegt → Status zeigt PID, beenden. 4. `scripts\dienst-neustart.bat`. 5. Startet der Dienst in Schleife (NSSM neustart alle 5 s) → Fehler in `dienst-err.log` beheben, nicht endlos laufen lassen |
| **Backup-Ziel nicht erreichbar** | `/health` `warn` „Backup-Spiegelung fehlgeschlagen“, Glocke, Eintrag im Fehlerprotokoll, `data\backups\ziel.log` | 1. `BACKUP_ZIEL` in der `.env` prüfen (Pfad vorhanden? Rechte des Dienstkontos – SYSTEM hat auf Netzfreigaben keine Rechte → Dienstkonto der IT oder lokaler/OneDrive-Ordner). 2. „Backup jetzt“ auf der Betriebs-Seite. 3. Die lokale Sicherung (30 Tage) läuft weiter – kein Datenverlust, aber keine Kopie außerhalb des Servers |
| **Zertifikat abgelaufen** (nur mit Reverse-Proxy/HTTPS der IT) | Browser-Warnung „Verbindung nicht sicher“, Mobilgeräte verweigern den Zugriff; das Tool selbst antwortet auf `http://127.0.0.1:8000/health` normal | 1. IT: Zertifikat am Proxy erneuern. 2. Übergangsweise interne HTTP-Adresse nutzen. 3. `HTTPS_AKTIV`/`BASIS_URL` in der `.env` unverändert lassen |
| **Nutzer können sich nicht anmelden** | „Benutzer oder PIN falsch“, Sperrtext nach Fehlversuchen | Benutzerverwaltung: Sperre aufheben / PIN neu setzen; Login-Protokoll (`/benutzer/login-protokoll`); nach Rollback: einmal neu anmelden ist normal |
| **Tool nach Windows-Neustart nicht da** | Dienst/Aufgabe nicht gestartet | `scripts\dienst-status.bat`; Starttyp „Automatisch“ (Weg A) bzw. Aufgabe aktiviert (Weg B); `scripts\dienst-installieren.bat` erneut ausführen |

## Ansprechpartner

| Thema | Zuständig | Erreichbar über |
|---|---|---|
| Tool (Funktionen, Fehlermeldungen, Updates, Rollback, Smoke-/Restore-Test, Parametrierung) | Andreas (Admin) mit Claude Code auf fr-wts-02 | intern; Fehler mit Fehler-Nr./Protokoll melden |
| Server (Windows, Dienstkonto, Ressourcen, Windows-Updates im Wartungsfenster, Virenscanner) | IT | Ticket/Telefon IT |
| Netz (Firewall, DNS-Name, Reverse-Proxy/Zertifikat) | IT | Ticket IT |
| Backup (Netzlaufwerk/UNC, 90 Tage, zentrale Sicherung) | IT | Ticket IT |
| VPN (WireGuard-Profile für neue Geräte, Sperren bei Verlust) | IT | Ticket IT |
| Monitoring (`/health` alle 60 s, Alarm > 5 min) | IT (bis dahin Wächter + `health-pruefen.ps1` + Admin-Glocke) | – |

## Lasttest

Aufruf (Entwicklungs-PC, gegen eine DB-Kopie, eigener uvicorn auf Port 8001;
Lastmodell, Zielwerte und Bericht `docs/lasttest-v27.md` laut PLAN_V17 Phase 131):

```bat
venv\Scripts\python scripts\lasttest.py --nutzer 50 --dauer 20 --profil standard
```

Aufruf (Entwicklungs-PC, Port 8001 frei, keine andere Last; Details und Parameter in
`docs/lasttest-v27.md` Abschnitt 3):

```bat
venv\Scripts\python scripts\lasttest.py --frisch --profil normal
venv\Scripts\python scripts\lasttest.py --frisch --profil schreibsturm
venv\Scripts\python scripts\lasttest.py --frisch --profil stress
```

`--frisch` erzeugt die DB-Kopie aus `diagnosengebotstool.db` neu (migrate ×2), startet den
Server mit 2 s simulierter Latenz je externem Aufruf (`scripts\lasttest_server.py`) und
schreibt Bericht und Rohdaten nach `diagnose	est_v27\lasttest_<zeit>.md/.json`.
Zielwerte, Ergebnisse der Läufe und die PostgreSQL-Entscheidung stehen in
`docs/lasttest-v27.md` Abschnitt 2 und 4. Nächster Lasttest: nach dem nächsten großen Modul
(Regel aus Phase 131).

