# Lasttest v27 – 50 Nutzer (PLAN_V17 Phase 127 Lastmodell, Phase 131)

Stand: 06.10.2026 (Agent E, Werkzeug fertig; die vollen Läufe führt der
Orchestrator nach Abschluss aller Agenten aus – Abschnitt 4).
Werkzeuge: `scripts/lasttest.py` (Lastgenerator, httpx, ein Thread je
virtuellem Nutzer) und `scripts/lasttest_server.py` (uvicorn gegen die
DB-Kopie mit Lifespan, Scheduler und Latenz-Mocks). Arbeitsordner
`diagnose/test_v27/` (gitignored: DB-Kopie, Berichte, JSON, Serverlogs).

## 1. Lastmodell (Phase 127 – Zahlen [ANNAHME], Andreas bestätigt)

Das Tool wird von **50 Mitarbeitern** genutzt; zur Spitzenzeit (9–11 Uhr) sind
**etwa 35 gleichzeitig aktiv**. Der Plan nennt dafür den Rollenmix
15 Außendienst mobil + 12 Innendienst + 6 Lead-Management + 4 Projektierung/
Montage (= 37; das Skript skaliert den Mix auf 70 % der virtuellen Nutzer,
Standard 50 → 35 aktiv). Die übrigen 15 Nutzer sind angemeldet, aber nicht
aktiv: sie rufen alle 60–120 s eine Einstiegsseite auf („Leser“ [ANNAHME]).
Denkzeit **5–15 s je Schritt**, feste Zufallssaat (`--seed 27`), Dauer
**20 Minuten**, alle Hintergrundläufe (Scheduler) im Normaltakt.

| Rolle (aktiv) | Anzahl | Schritte je Szenario (Routen in Abschnitt 1.1) |
|---|---:|---|
| Außendienst mobil | 15 | Leads VOT öffnen → Erfassung starten → Erfassungsbogen WP (alle Seiten, „25 Fragen“ [ANNAHME: WP-Katalogbogen]) → Absenden → Protokoll-PDF |
| Innendienst | 12 | Erfassungsliste → Erfassung → Angebot erzeugen → Editor mit 10 Positionsänderungen (je Änderung Editor neu laden wie im Browser) → Angebots-PDF → Versand vorbereiten (Graph gemockt) → Vorgangsakte |
| Lead-Management | 6 | Hauptboard → Kundenkartei → Terminvorschläge (`?neu=1`, Routing gemockt) → Anrufergebnis → Board Deals |
| Projektierung | 3 | Board → Projektakte → Aufgabe erledigen (fetch/JSON) → Galerie-Upload 2 MB |
| Montage | 1 | Meine Einsätze → Einsatz → Montage-Aufgabe erledigt → Foto 2 MB |

Benutzer je Rolle kommen aus der Kopie (alle aktiven Benutzer der Hauptrolle,
reihum; Außendienst nur mit offenen Leads VOT). Rollen ohne Person in der
Kopie (Lead-Management, Projektierung – in der Server-Kopie vom 03.10.2026
nicht vorhanden) übernehmen Admins [ANNAHME]; `--benutzer rolle=id+id`
überschreibt.

Externe Dienste sind abgeklemmt, antworten aber mit **2 s simulierter Latenz**
je Aufruf (`--latenz`): ORS/Google-Matrix und -Geocoding, Nominatim, Microsoft
Graph (Mail-Entwurf, Postfach, Kalender), monday, Heizreport;
`urllib.request.urlopen` ist als Sicherheitsnetz gesperrt. Damit die Latenz-
Pfade überhaupt durchlaufen werden, setzt der Server in der Kopie
`parser_modus = an`, `routing_anbieter = ors`, `ors_api_key = lasttest`
(Terminvorschläge rufen die Matrix) und ergänzt AD-Profile mit
Startkoordinaten [ANNAHME]; `kalender_sync` bleibt wie in der Kopie `aus`
(`--kalender an` schaltet Outlook-Frei/Belegt – ebenfalls gemockt – dazu).

### 1.1 Schritte je Rolle mit den tatsächlich verwendeten Routen

**Außendienst mobil** (Benutzer mit Rolle aussendienst und eigenen Leads VOT)
`GET /leads` → `GET /leads/{id}/erfassen` (303) → `GET /erfassung/sparten?lead_id=` →
`POST /erfassung/sparten-start` (kunde_id, lead_id, sparte_WP=on; 303) →
`GET /erfassung/{id}/weiche` → je Seite `GET` + `POST /erfassung/{id}/seite/{nr}`
(Formular aus dem HTML gelesen, Antworten aus dem Kontroll-Szenario der
Regressionstests, Ampel grün) → `GET /erfassung/{id}/pruefen` →
`POST /erfassung/{id}/absenden` → `GET /erfassungen/{id}/protokoll.pdf`
([ANNAHME] der mobile Bogen hat keinen PDF-Link; die Route ist für den
Außendienst erreichbar – Innendienst-Sicht wäre die Alternative).

**Innendienst**
`GET /erfassungen` → `GET /erfassungen/{id}` → `GET /erfassungen/{id}/angebot-erzeugen`
(303 auf das neue Angebot; Rückfall auf ein vorhandenes Angebot, wenn die
Erfassung unvollständig ist) → `GET /angebote/{id}` (Editor, erwirbt die
Bearbeitungssperre) → 10 × `POST /angebote/{id}/position/{pid}/menge` (303) +
`GET /angebote/{id}` → `GET /angebote/{id}/pdf` → `POST /angebote/{id}/email`
(303) + `GET /angebote/{id}` → `GET /vorgaenge/{id}` → `POST /angebote/{id}/sperre-frei`.

**Lead-Management** (Admins, weil die Kopie keine Hauptrolle leadmanagement hat)
`GET /lead-management/hauptboard` → `GET /lead-management/lead/{id}` →
`GET /lead-management/lead/{id}/termin/vorschlaege.json?neu=1` (Accept JSON) →
`POST /lead-management/anruf/{id}` (ergebnis nicht_erreicht/mailbox/erreicht,
dauer_sek, zurueck; 303) + `GET /lead-management/lead/{id}` →
`GET /lead-management/terminiert` (Board Deals).

**Projektierung** (Admins)
`GET /projektierung` → `GET /projektierung/projekt/{id}` →
`POST /projektierung/aufgabe/{id}/erledigt-umschalten` (Accept JSON) →
`POST /vorgaenge/{id}/galerie/upload` (multipart, 2-MB-JPEG 3000 × 2250 px –
die Galerie verkleinert auf 2000 px; 303) + `GET /projektierung/projekt/{id}`.

**Montage** (Benutzer mit Rolle montage)
`GET /montage` → `GET /montage/einsatz/{id}` → `POST /montage/aufgabe/{id}/erledigt`
(termin_id, Accept JSON) → `POST /montage/einsatz/{id}/foto` (multipart, 2 MB; 303)
+ `GET /montage/einsatz/{id}`.

**Leser** (angemeldet, nicht aktiv): alle 60–120 s `GET /` (Büro), `GET /erfassung`
(Außendienst) bzw. `GET /montage`.

**Schreibsturm** (`--profil schreibsturm`): 20 Innendienst-Nutzer (Innendienst +
Admins reihum) öffnen je ein eigenes Angebot (`GET /angebote/{id}`) und ändern
gleichzeitig je 10 Positionen (`POST …/position/{pid}/menge` + Editor neu laden,
Denkzeit 1–3 s [ANNAHME]); nach dem Lauf vergleicht das Skript Soll/Ist je
Position direkt in der Kopie (`angebotspositionen.menge`).

## 2. Zielwerte und Entscheidungsregel PostgreSQL (Phase 131)

Zielwerte (Abnahmekriterien, [ANNAHME] – Andreas bestätigt), geprüft über die
Client-Sicht (p95 je Gruppe) und /health bzw. die Protokolle der Kopie:

| Kriterium | Ziel | Messung |
|---|---|---|
| p95 Listen und Akten (Erfassungsliste, Angebotsliste, Vorgangsakte, Hauptboard, Kundenkartei ohne Vorschläge, Leads VOT, Editor-Seite, Projektakte, Einsatz) | **≤ 1,5 s** | Gruppe `Listen und Akten` |
| p95 Editor-Aktionen (Position ändern/löschen/sortieren) | **≤ 1,0 s** | Gruppe `Editor-Aktionen` |
| p95 Angebots-PDF | **≤ 4 s** | `GET /angebote/{id}/pdf` |
| p95 Protokoll-PDF | ≤ 3 s | `GET /erfassungen/{id}/protokoll.pdf` |
| Terminvorschläge (mit 2 s simulierter Latenz) | ≤ 6 s | `GET …/termin/vorschlaege.json` |
| `TimeoutError` (Pool) | **0** | fehler.log der Kopie + Client-Timeouts |
| „database is locked“ an der Oberfläche | **0** (interne Wiederholung erlaubt, Zähler im Bericht) | 5xx-Antworten mit „Datenbank kurz belegt“ + Anfrage-Einträge in fehler.log |
| Pool-Spitze | ≤ 60 % des Maximums | /health alle 10 s und Pool-Checkouts in zugriff.log |
| Fehlerquote (5xx, Timeouts, Verbindungsfehler) | < 0,1 % | Client-Sicht |

**Schreibsturm:** keine verlorene Änderung (Soll/Ist je Position), keine 500er.
**Stressstufe:** Lastmodell auf 100 Nutzer verdoppelt (10 Minuten) – nur zur
Ermittlung der Reserve, keine Abnahmekriterien; Ergebnis als „Reserve-Faktor“
(Ziel-p95 ÷ Ist-p95 je Gruppe, dazu Pool-Reserve) im Bericht.

**Entscheidungsregel PostgreSQL (Wortlaut Phase 131):** Werden die Zielwerte
nach Behebung aller gefundenen Code-Ursachen (zweiter Lauf) **nicht** erreicht
**und** ist die Ursache nachweislich die Ein-Schreiber-Grenze von SQLite
(Wartezeit auf die Schreibsperre > 20 % der Antwortzeit bei p95), empfiehlt die
Gesamtübersicht den Umstieg (eigener Plan, nicht in v27). Sonst: SQLite
bestätigt, nächster Lasttest nach dem nächsten großen Modul. Die Wartezeit auf
die Schreibsperre liefert /health (`schreibsperre_max_ms`, `schreibsperre_locked`
aus dem `_speichern`-Pfad des Editors) – im Bericht unter „Betrieb“.

## 3. Aufruf

Immer aus dem Projektordner, immer gegen die Kopie (`--data` muss unter
`diagnose\` liegen; das Live-Verzeichnis `data\` wird abgewiesen). Port 8001
muss frei sein, keine andere Last auf dem Rechner.

```
rem Kopie frisch erzeugen (sqlite3-Backup-API aus diagnose\angebotstool.db) + migrate.py ×2
venv\Scripts\python scripts\lasttest.py --frisch --nur-kopie

rem Probelauf (10 Nutzer, 2 Minuten)
venv\Scripts\python scripts\lasttest.py --frisch --nutzer 10 --dauer 2

rem Lauf 1 und Lauf 2 (Lastmodell: 50 Nutzer, 20 Minuten)
venv\Scripts\python scripts\lasttest.py --frisch --profil normal

rem Schreibsturm (20 Innendienst-Nutzer × 10 Positionen, Soll/Ist-Prüfung)
venv\Scripts\python scripts\lasttest.py --frisch --profil schreibsturm

rem Stressstufe (100 Nutzer, 10 Minuten)
venv\Scripts\python scripts\lasttest.py --frisch --profil stress
```

Weitere Parameter: `--nutzer N`, `--dauer MIN`, `--denkzeit 5-15`, `--port 8001`,
`--data diagnose\test_v27\data`, `--seed 27`, `--latenz 2.0`,
`--benutzer aussendienst=4+7,leadmanagement=1`, `--bericht PFAD`,
`--kalender aus|an`, `--ohne-ad-profile`, `--ohne-server` (laufenden Server auf
dem Port verwenden), `--timeout 90`, `--health-intervall 10`, `--ohne-aufwaermen`.

Ausgaben je Lauf in `diagnose\test_v27\`: `lasttest_<zeit>.md` (Markdown-Bericht,
Tabellen passen 1:1 in Abschnitt 4), `lasttest_<zeit>.json` (Rohdaten: jede
Anfrage, /health-Proben, zugriff.log-Auswertung, Fehlerprotokoll),
`server_<zeit>.log` (Serverkonsole), `migrate_lauf1.txt`/`migrate_lauf2.txt`.
Exit-Code 0 = Zielwerte erfüllt (bzw. Schreibsturm ohne Verlust), 1 = nicht
erfüllt, 2 = Bedienfehler/Abbruch, 3 = Tool-Fehler im Lastgenerator.

Der Server läuft als Subprozess
(`scripts\lasttest_server.py --port 8001 --data … --latenz 2 --kalender aus`),
wird über /health abgewartet und am Ende per CTRL+BREAK sauber beendet
(Lifespan: Scheduler stoppen). Vor der Messung werden je realem Benutzer ein
paar Einstiegsseiten ungemessen aufgerufen (Logik-Excel, Templates, Caches wie
bei einem laufenden Server [ANNAHME]; `--ohne-aufwaermen` schaltet ab).

## 4. Ergebnisse

Die Abschnitte füllt der Orchestrator mit der Ausgabe von `lasttest.py`
(Markdown-Bericht je Lauf, 1:1 einfügen).

### 4.1 Lauf 1 (Lastmodell, 50 Nutzer, 20 Minuten)

<!-- lasttest.py 20261006-212646 -->
### Lauf 06.10.2026 21:26:53 – Profil normal, 50 Nutzer (35 aktiv), 20 min

- Lastmodell: 14 Außendienst mobil, 11 Innendienst, 6 Lead-Management, 3 Projektierung, 1 Montage; dazu 15 angemeldete Leser · Denkzeit 5–15 s · Seed 27 · Latenz je externem Aufruf 2 s · Port 8001
- Server: v27 · Commit da9df30 · Pool 20 (max 90) · Threads 64 · Scheduler 13 Läufe · DATA_ORDNER `C:\Users\a.scheelen\Tools\Angebotstool\diagnose\test_v27\data`
- Benutzer je Rolle: Außendienst mobil = 4, 7, 9, 13, 15, 17; Innendienst = 14, 18; Lead-Management = 1, 2, 12, 16, 20; Projektierung = 1, 2, 12, 16, 20; Montage = 24
- Hinweis: keine aktive Person mit Hauptrolle „leadmanagement“ in der Kopie – Admins übernehmen die Rolle [ANNAHME]
- Hinweis: keine aktive Person mit Hauptrolle „projektierung“ in der Kopie – Admins übernehmen die Rolle [ANNAHME]
- Anfragen gesamt: 6552 (327.4/min) · 5xx 0 · Timeouts 0 · Verbindungsfehler 0 · Szenarien 625 · Tool-Fehler 0 · Laufzeit 20.0 min (06.10.2026 21:26:53 – 21:46:53)

**Antwortzeiten je Route (Client-Sicht, Millisekunden)**

| Route | Anzahl | p50 | p95 | p99 | max | 5xx | Timeout | Verb. |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| `GET /erfassung/{id}/seite/{nr}` | 939 | 20 | 114 | 413 | 688 | 0 | 0 | 0 |
| `POST /erfassung/{id}/seite/{nr}` | 929 | 30 | 782 | 1.676 | 3.382 | 0 | 0 | 0 |
| `GET /angebote/{id}` | 849 | 58 | 402 | 926 | 1.711 | 0 | 0 | 0 |
| `POST /angebote/{id}/position/{pid}/menge` | 707 | 24 | 327 | 1.320 | 2.864 | 0 | 0 | 0 |
| `GET /lead-management/lead/{id}` | 298 | 58 | 634 | 1.213 | 1.473 | 0 | 0 | 0 |
| `GET /projektierung/projekt/{id}` | 172 | 65 | 356 | 922 | 957 | 0 | 0 | 0 |
| `GET /lead-management/hauptboard` | 151 | 156 | 1.661 | 1.993 | 2.200 | 0 | 0 | 0 |
| `GET /lead-management/lead/{id}/termin/vorschlaege.json` | 150 | 2.944 | 5.221 | 8.464 | 8.681 | 0 | 0 | 0 |
| `POST /lead-management/anruf/{id}` | 148 | 29 | 704 | 2.103 | 4.666 | 0 | 0 | 0 |
| `GET /lead-management/terminiert` | 147 | 909 | 2.749 | 4.353 | 4.540 | 0 | 0 | 0 |
| `GET /erfassung/sparten` | 126 | 24 | 130 | 478 | 522 | 0 | 0 | 0 |
| `GET /leads` | 126 | 43 | 436 | 562 | 928 | 0 | 0 | 0 |
| `GET /leads/{id}/erfassen` | 126 | 33 | 225 | 312 | 338 | 0 | 0 | 0 |
| `GET /erfassung/{id}/weiche` | 125 | 16 | 63 | 118 | 149 | 0 | 0 | 0 |
| `POST /erfassung/sparten-start` | 125 | 33 | 1.037 | 1.877 | 2.789 | 0 | 0 | 0 |
| `GET /` | 116 | 116 | 1.187 | 1.523 | 1.656 | 0 | 0 | 0 |
| `GET /erfassung/{id}/pruefen` | 112 | 18 | 75 | 216 | 749 | 0 | 0 | 0 |
| `GET /erfassungen/{id}/protokoll.pdf` | 112 | 286 | 1.060 | 1.533 | 1.558 | 0 | 0 | 0 |
| `POST /erfassung/{id}/absenden` | 112 | 38 | 589 | 2.900 | 3.005 | 0 | 0 | 0 |
| `GET /projektierung` | 88 | 48 | 553 | 1.039 | 1.303 | 0 | 0 | 0 |
| `POST /projektierung/aufgabe/{id}/erledigt-umschalten` | 86 | 80 | 847 | 1.552 | 1.731 | 0 | 0 | 0 |
| `POST /vorgaenge/{id}/galerie/upload` | 85 | 221 | 1.395 | 2.865 | 4.385 | 0 | 0 | 0 |
| `GET /erfassungen` | 77 | 100 | 352 | 533 | 1.835 | 0 | 0 | 0 |
| `GET /erfassungen/{id}` | 77 | 32 | 194 | 289 | 650 | 0 | 0 | 0 |
| `GET /erfassung` | 76 | 47 | 227 | 325 | 783 | 0 | 0 | 0 |
| `GET /erfassungen/{id}/angebot-erzeugen` | 76 | 49 | 891 | 1.202 | 2.718 | 0 | 0 | 0 |
| `GET /montage/einsatz/{id}` | 75 | 30 | 113 | 308 | 469 | 0 | 0 | 0 |
| `GET /angebote/{id}/pdf` | 66 | 941 | 2.456 | 3.004 | 3.378 | 0 | 0 | 0 |
| `GET /vorgaenge/{id}` | 66 | 51 | 1.472 | 1.971 | 2.047 | 0 | 0 | 0 |
| `POST /angebote/{id}/email` | 66 | 13.229 | 15.569 | 17.065 | 17.610 | 0 | 0 | 0 |
| `POST /angebote/{id}/sperre-frei` | 66 | 16 | 78 | 182 | 384 | 0 | 0 | 0 |
| `GET /montage` | 38 | 36 | 324 | 718 | 718 | 0 | 0 | 0 |
| `POST /montage/einsatz/{id}/foto` | 37 | 55 | 1.441 | 5.168 | 5.168 | 0 | 0 | 0 |
| `POST /montage/aufgabe/{id}/erledigt` | 3 | 35 | 565 | 565 | 565 | 0 | 0 | 0 |

**Zielwerte Phase 131 [ANNAHME]**

| Kriterium | Ziel | Ist | Ergebnis |
|---|---|---|---|
| p95 Listen und Akten | ≤ 1500 ms | 949 ms (n = 2356, p50 66 ms) | erfüllt |
| p95 Editor-Aktionen | ≤ 1000 ms | 308 ms (n = 773, p50 24 ms) | erfüllt |
| p95 Angebots-PDF | ≤ 4000 ms | 2456 ms (n = 66, p50 941 ms) | erfüllt |
| p95 Protokoll-PDF | ≤ 3000 ms | 1060 ms (n = 112, p50 286 ms) | erfüllt |
| p95 Terminvorschläge | ≤ 6000 ms | 5221 ms (n = 150, p50 2944 ms) | erfüllt |
| TimeoutError (Pool) / Client-Timeouts | 0 | Server 0 · Client 0 | erfüllt |
| „database is locked“ an der Oberfläche | 0 | 0 (fehler.log gesamt 0, davon Anfragen 0) | erfüllt |
| Pool-Spitze | ≤ 60 % von 90 | 15 (16.7 %) | erfüllt |
| Fehlerquote (5xx + Timeouts + Verbindungsfehler) | < 0.1 % | 0.000 % (0 von 6552) | erfüllt |

**Gruppen (p95 nach Kriterium)**

| Gruppe | Anzahl | p50 | p95 | p99 | max | 5xx |
|---|---:|---:|---:|---:|---:|---:|
| Listen und Akten | 2356 | 66 | 949 | 1.891 | 4.540 | 0 |
| Editor-Aktionen | 773 | 24 | 308 | 1.021 | 2.864 | 0 |
| Angebots-PDF | 66 | 941 | 2.456 | 3.004 | 3.378 | 0 |
| Protokoll-PDF | 112 | 286 | 1.060 | 1.533 | 1.558 | 0 |
| Terminvorschläge | 150 | 2.944 | 5.221 | 8.464 | 8.681 | 0 |
| übrige Schritte | 3095 | 30 | 800 | 13.265 | 17.610 | 0 |

**Betrieb (/health alle 10 s, 120 Proben)**: Pool-Spitze 8 von 90 (8.9 %) · WAL max 4.25 MB · Schreibsperre max 2518 ms, locked 0 · RSS max 370.4 MB · CPU 564.4 s · /health p95 154 ms · Status: ok ×120

**Server-Sicht (zugriff.log der Kopie)**: 6554 Anfragen (327.5/min) · 5xx 0 · Pool-Spitze zu Anfragebeginn 15 · Anteil > 2 s 3.39 %

| Route (Server) | Anzahl | p50 | p95 | max | 5xx |
|---|---:|---:|---:|---:|---:|
| `GET /erfassung/{id}/seite/{nr}` | 939 | 17 | 104 | 682 | 0 |
| `POST /erfassung/{id}/seite/{nr}` | 929 | 15 | 735 | 3.200 | 0 |
| `GET /angebote/{id}` | 849 | 55 | 400 | 1.708 | 0 |
| `POST /angebote/{id}/position/{pid}/menge` | 707 | 11 | 296 | 2.713 | 0 |
| `GET /lead-management/lead/{id}` | 298 | 45 | 606 | 1.448 | 0 |
| `GET /projektierung/projekt/{id}` | 172 | 55 | 316 | 901 | 0 |
| `GET /lead-management/hauptboard` | 152 | 141 | 1.547 | 2.157 | 0 |
| `GET /lead-management/lead/{id}/termin/vorschlaege.json` | 150 | 2.942 | 5.206 | 8.650 | 0 |
| `POST /lead-management/anruf/{id}` | 148 | 13 | 683 | 4.598 | 0 |
| `GET /lead-management/terminiert` | 147 | 881 | 2.742 | 4.343 | 0 |
| `GET /leads` | 126 | 27 | 363 | 898 | 0 |
| `GET /leads/{id}/erfassen` | 126 | 17 | 163 | 267 | 0 |
| `GET /erfassung/sparten` | 126 | 21 | 123 | 506 | 0 |
| `POST /erfassung/sparten-start` | 125 | 18 | 1.033 | 2.771 | 0 |
| `GET /erfassung/{id}/weiche` | 125 | 14 | 59 | 142 | 0 |

**Fehlerprotokoll der Kopie**: 0 neue Tabelleneinträge · fehler.log: 0 Fehler-Nummern, „database is locked“ 0 (Anfragen 0), TimeoutError 0, QueuePool 0

Zähler: formularfehler = 2, id_angebot_erzeugen_fallback:/erfassungen (Antworten unvollständig für die aktuelle Logik) = 11, id_angebot_erzeugt = 65, id_erfassung_vom_aussendienst = 66, szenario_bei_laufende_abgebrochen = 50, vorschlaege_status:hv_lead = 17, vorschlaege_status:ok = 133

Rohdaten: `C:\Users\a.scheelen\Tools\Angebotstool\diagnose\test_v27\lasttest_20261006-212646.json` · Serverkonsole: `C:\Users\a.scheelen\Tools\Angebotstool\diagnose\test_v27\server_20261006-212646.log`

_Hinweis Orchestrator: alle Zielwerte als Gruppe erfüllt; einzeln liegen `GET /lead-management/hauptboard` (p95 1,66 s) und das Deals-Board `GET /lead-management/terminiert` (p95 2,75 s, 856 SQL-Abfragen je Aufruf = N+1) über 1,5 s, `POST /angebote/{id}/email` (Versand vorbereiten, 7 Graph-Aufrufe à 2 s simulierter Latenz) bei 13–17 s – nicht Teil der Zielwerte. Schreibsperre max. 2,5 s (ein Commit), locked 0._

### 4.2 Lauf 2 (nach Behebung der Befunde aus Lauf 1)

<!-- lasttest.py 20261006-223943 -->
### Lauf 06.10.2026 22:39:50 – Profil normal, 50 Nutzer (35 aktiv), 20 min

- Lastmodell: 14 Außendienst mobil, 11 Innendienst, 6 Lead-Management, 3 Projektierung, 1 Montage; dazu 15 angemeldete Leser · Denkzeit 5–15 s · Seed 27 · Latenz je externem Aufruf 2 s · Port 8001
- Server: v27 · Commit da9df30 · Pool 20 (max 90) · Threads 64 · Scheduler 13 Läufe · DATA_ORDNER `C:\Users\a.scheelen\Tools\Angebotstool\diagnose\test_v27\data`
- Benutzer je Rolle: Außendienst mobil = 4, 7, 9, 13, 15, 17; Innendienst = 14, 18; Lead-Management = 1, 2, 12, 16, 20; Projektierung = 1, 2, 12, 16, 20; Montage = 24
- Hinweis: keine aktive Person mit Hauptrolle „leadmanagement“ in der Kopie – Admins übernehmen die Rolle [ANNAHME]
- Hinweis: keine aktive Person mit Hauptrolle „projektierung“ in der Kopie – Admins übernehmen die Rolle [ANNAHME]
- Anfragen gesamt: 6602 (330.0/min) · 5xx 0 · Timeouts 0 · Verbindungsfehler 0 · Szenarien 628 · Tool-Fehler 0 · Laufzeit 20.0 min (06.10.2026 22:39:50 – 22:59:51)

**Antwortzeiten je Route (Client-Sicht, Millisekunden)**

| Route | Anzahl | p50 | p95 | p99 | max | 5xx | Timeout | Verb. |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| `GET /erfassung/{id}/seite/{nr}` | 942 | 18 | 95 | 322 | 681 | 0 | 0 | 0 |
| `POST /erfassung/{id}/seite/{nr}` | 933 | 28 | 730 | 1.990 | 3.481 | 0 | 0 | 0 |
| `GET /angebote/{id}` | 857 | 54 | 257 | 486 | 1.096 | 0 | 0 | 0 |
| `POST /angebote/{id}/position/{pid}/menge` | 714 | 23 | 293 | 1.377 | 2.252 | 0 | 0 | 0 |
| `GET /lead-management/lead/{id}` | 307 | 47 | 455 | 1.254 | 2.888 | 0 | 0 | 0 |
| `GET /projektierung/projekt/{id}` | 174 | 61 | 411 | 491 | 1.081 | 0 | 0 | 0 |
| `GET /lead-management/hauptboard` | 155 | 109 | 1.153 | 2.024 | 2.101 | 0 | 0 | 0 |
| `GET /lead-management/lead/{id}/termin/vorschlaege.json` | 154 | 2.907 | 4.206 | 4.909 | 7.220 | 0 | 0 | 0 |
| `POST /lead-management/anruf/{id}` | 152 | 21 | 552 | 1.059 | 3.377 | 0 | 0 | 0 |
| `GET /lead-management/terminiert` | 149 | 425 | 948 | 1.391 | 1.538 | 0 | 0 | 0 |
| `GET /erfassung/sparten` | 126 | 16 | 63 | 164 | 225 | 0 | 0 | 0 |
| `GET /leads` | 126 | 41 | 303 | 448 | 463 | 0 | 0 | 0 |
| `GET /leads/{id}/erfassen` | 126 | 26 | 107 | 321 | 340 | 0 | 0 | 0 |
| `GET /erfassung/{id}/weiche` | 125 | 15 | 83 | 213 | 217 | 0 | 0 | 0 |
| `POST /erfassung/sparten-start` | 125 | 35 | 816 | 1.566 | 2.145 | 0 | 0 | 0 |
| `GET /` | 116 | 65 | 869 | 1.305 | 1.360 | 0 | 0 | 0 |
| `GET /erfassung/{id}/pruefen` | 112 | 18 | 90 | 173 | 302 | 0 | 0 | 0 |
| `GET /erfassungen/{id}/protokoll.pdf` | 112 | 265 | 649 | 1.353 | 1.685 | 0 | 0 | 0 |
| `POST /erfassung/{id}/absenden` | 112 | 36 | 371 | 1.612 | 1.698 | 0 | 0 | 0 |
| `GET /projektierung` | 88 | 46 | 783 | 959 | 996 | 0 | 0 | 0 |
| `POST /projektierung/aufgabe/{id}/erledigt-umschalten` | 87 | 60 | 615 | 1.317 | 3.471 | 0 | 0 | 0 |
| `POST /vorgaenge/{id}/galerie/upload` | 86 | 202 | 835 | 1.172 | 1.753 | 0 | 0 | 0 |
| `GET /erfassungen` | 77 | 87 | 478 | 599 | 627 | 0 | 0 | 0 |
| `GET /erfassungen/{id}` | 77 | 32 | 195 | 264 | 331 | 0 | 0 | 0 |
| `GET /erfassungen/{id}/angebot-erzeugen` | 77 | 40 | 250 | 1.035 | 1.051 | 0 | 0 | 0 |
| `GET /erfassung` | 76 | 40 | 154 | 296 | 368 | 0 | 0 | 0 |
| `GET /montage/einsatz/{id}` | 75 | 24 | 85 | 131 | 177 | 0 | 0 | 0 |
| `GET /angebote/{id}/pdf` | 66 | 968 | 1.887 | 2.089 | 2.229 | 0 | 0 | 0 |
| `GET /vorgaenge/{id}` | 66 | 34 | 726 | 837 | 2.795 | 0 | 0 | 0 |
| `POST /angebote/{id}/email` | 66 | 13.054 | 15.580 | 16.198 | 16.215 | 0 | 0 | 0 |
| `POST /angebote/{id}/sperre-frei` | 66 | 24 | 95 | 259 | 362 | 0 | 0 | 0 |
| `GET /montage` | 38 | 33 | 95 | 209 | 209 | 0 | 0 | 0 |
| `POST /montage/einsatz/{id}/foto` | 37 | 45 | 754 | 3.490 | 3.490 | 0 | 0 | 0 |
| `POST /montage/aufgabe/{id}/erledigt` | 3 | 98 | 126 | 126 | 126 | 0 | 0 | 0 |

**Zielwerte Phase 131 [ANNAHME]**

| Kriterium | Ziel | Ist | Ergebnis |
|---|---|---|---|
| p95 Listen und Akten | ≤ 1500 ms | 494 ms (n = 2381, p50 59 ms) | erfüllt |
| p95 Editor-Aktionen | ≤ 1000 ms | 291 ms (n = 780, p50 24 ms) | erfüllt |
| p95 Angebots-PDF | ≤ 4000 ms | 1887 ms (n = 66, p50 968 ms) | erfüllt |
| p95 Protokoll-PDF | ≤ 3000 ms | 649 ms (n = 112, p50 265 ms) | erfüllt |
| p95 Terminvorschläge | ≤ 6000 ms | 4206 ms (n = 154, p50 2907 ms) | erfüllt |
| TimeoutError (Pool) / Client-Timeouts | 0 | Server 0 · Client 0 | erfüllt |
| „database is locked“ an der Oberfläche | 0 | 0 (fehler.log gesamt 0, davon Anfragen 0) | erfüllt |
| Pool-Spitze | ≤ 60 % von 90 | 16 (17.8 %) | erfüllt |
| Fehlerquote (5xx + Timeouts + Verbindungsfehler) | < 0.1 % | 0.000 % (0 von 6602) | erfüllt |

**Gruppen (p95 nach Kriterium)**

| Gruppe | Anzahl | p50 | p95 | p99 | max | 5xx |
|---|---:|---:|---:|---:|---:|---:|
| Listen und Akten | 2381 | 59 | 494 | 1.100 | 2.888 | 0 |
| Editor-Aktionen | 780 | 24 | 291 | 1.243 | 2.252 | 0 |
| Angebots-PDF | 66 | 968 | 1.887 | 2.089 | 2.229 | 0 |
| Protokoll-PDF | 112 | 265 | 649 | 1.353 | 1.685 | 0 |
| Terminvorschläge | 154 | 2.907 | 4.206 | 4.909 | 7.220 | 0 |
| übrige Schritte | 3109 | 24 | 709 | 13.080 | 16.215 | 0 |

**Betrieb (/health alle 10 s, 120 Proben)**: Pool-Spitze 6 von 90 (6.7 %) · WAL max 4.18 MB · Schreibsperre max 2225 ms, locked 0 · RSS max 384.9 MB · CPU 481.9 s · /health p95 153 ms · Status: ok ×120

**Server-Sicht (zugriff.log der Kopie)**: 6608 Anfragen (330.3/min) · 5xx 0 · Pool-Spitze zu Anfragebeginn 16 · Anteil > 2 s 3.03 %

| Route (Server) | Anzahl | p50 | p95 | max | 5xx |
|---|---:|---:|---:|---:|---:|
| `GET /erfassung/{id}/seite/{nr}` | 942 | 16 | 88 | 668 | 0 |
| `POST /erfassung/{id}/seite/{nr}` | 933 | 13 | 723 | 3.470 | 0 |
| `GET /angebote/{id}` | 857 | 52 | 252 | 1.088 | 0 |
| `POST /angebote/{id}/position/{pid}/menge` | 714 | 11 | 280 | 2.247 | 0 |
| `GET /lead-management/lead/{id}` | 307 | 36 | 394 | 2.882 | 0 |
| `GET /projektierung/projekt/{id}` | 174 | 53 | 397 | 1.061 | 0 |
| `GET /lead-management/hauptboard` | 160 | 88 | 1.124 | 2.094 | 0 |
| `GET /lead-management/lead/{id}/termin/vorschlaege.json` | 154 | 2.900 | 4.203 | 7.218 | 0 |
| `POST /lead-management/anruf/{id}` | 152 | 10 | 547 | 3.356 | 0 |
| `GET /lead-management/terminiert` | 149 | 413 | 846 | 1.515 | 0 |
| `GET /leads` | 126 | 25 | 266 | 415 | 0 |
| `GET /leads/{id}/erfassen` | 126 | 12 | 87 | 201 | 0 |
| `GET /erfassung/sparten` | 126 | 14 | 61 | 215 | 0 |
| `POST /erfassung/sparten-start` | 125 | 17 | 798 | 2.121 | 0 |
| `GET /erfassung/{id}/weiche` | 125 | 14 | 77 | 215 | 0 |

**Fehlerprotokoll der Kopie**: 0 neue Tabelleneinträge · fehler.log: 0 Fehler-Nummern, „database is locked“ 0 (Anfragen 0), TimeoutError 0, QueuePool 0

Zähler: formularfehler = 2, id_angebot_erzeugen_fallback:/erfassungen (Antworten unvollständig für die aktuelle Logik) = 11, id_angebot_erzeugt = 66, id_erfassung_vom_aussendienst = 66, szenario_bei_laufende_abgebrochen = 50, vorschlaege_status:hv_lead = 18, vorschlaege_status:ok = 136

Rohdaten: `C:\Users\a.scheelen\Tools\Angebotstool\diagnose\test_v27\lasttest_20261006-223943.json` · Serverkonsole: `C:\Users\a.scheelen\Tools\Angebotstool\diagnose\test_v27\server_20261006-223943.log`

_Hinweis Orchestrator: Lauf 2 nach den beiden Code-Änderungen aus Lauf 1 (ein gebündelter Routing-Matrix-Aufruf je Vorschlagsrechnung; Lead-Parameter je Anfrage zwischengespeichert – Deals-Board 856 → 29 Abfragen). Alle Zielwerte mit Abstand erfüllt; Schreibsperre max. 2,2 s bei einem einzelnen Commit, locked 0._

### 4.3 Schreibsturm (20 Innendienst-Nutzer × 10 Positionen)

<!-- lasttest.py 20261006-230005 -->
### Lauf 06.10.2026 23:00:12 – Profil schreibsturm, 20 Nutzer (20 aktiv), 10 min

- Lastmodell: 20 Innendienst (Schreibsturm) · Denkzeit 1–3 s · Seed 27 · Latenz je externem Aufruf 2 s · Port 8001
- Server: v27 · Commit da9df30 · Pool 20 (max 90) · Threads 64 · Scheduler 13 Läufe · DATA_ORDNER `C:\Users\a.scheelen\Tools\Angebotstool\diagnose\test_v27\data`
- Benutzer je Rolle: Außendienst mobil = 4, 7, 9, 13, 15, 17; Innendienst = 14, 18; Lead-Management = 1, 2, 12, 16, 20; Projektierung = 1, 2, 12, 16, 20; Montage = 24; Innendienst (Schreibsturm) = 14, 18, 1, 2, 12, 16, 20
- Hinweis: keine aktive Person mit Hauptrolle „leadmanagement“ in der Kopie – Admins übernehmen die Rolle [ANNAHME]
- Hinweis: keine aktive Person mit Hauptrolle „projektierung“ in der Kopie – Admins übernehmen die Rolle [ANNAHME]
- Anfragen gesamt: 420 (896.7/min) · 5xx 0 · Timeouts 0 · Verbindungsfehler 0 · Szenarien 20 · Tool-Fehler 0 · Laufzeit 0.5 min (06.10.2026 23:00:12 – 23:00:40)

**Antwortzeiten je Route (Client-Sicht, Millisekunden)**

| Route | Anzahl | p50 | p95 | p99 | max | 5xx | Timeout | Verb. |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| `GET /angebote/{id}` | 210 | 83 | 824 | 859 | 906 | 0 | 0 | 0 |
| `POST /angebote/{id}/position/{pid}/menge` | 190 | 13 | 34 | 68 | 118 | 0 | 0 | 0 |
| `POST /angebote/{id}/sperre-frei` | 20 | 9 | 23 | 42 | 42 | 0 | 0 | 0 |

**Zielwerte Phase 131 [ANNAHME]**

| Kriterium | Ziel | Ist | Ergebnis |
|---|---|---|---|
| p95 Listen und Akten | ≤ 1500 ms | 824 ms (n = 210, p50 83 ms) | erfüllt |
| p95 Editor-Aktionen | ≤ 1000 ms | 34 ms (n = 210, p50 13 ms) | erfüllt |
| p95 Angebots-PDF | ≤ 4000 ms | keine Messung | offen |
| p95 Protokoll-PDF | ≤ 3000 ms | keine Messung | offen |
| p95 Terminvorschläge | ≤ 6000 ms | keine Messung | offen |
| TimeoutError (Pool) / Client-Timeouts | 0 | Server 0 · Client 0 | erfüllt |
| „database is locked“ an der Oberfläche | 0 | 0 (fehler.log gesamt 0, davon Anfragen 0) | erfüllt |
| Pool-Spitze | ≤ 60 % von 90 | 13 (14.4 %) | erfüllt |
| Fehlerquote (5xx + Timeouts + Verbindungsfehler) | < 0.1 % | 0.000 % (0 von 420) | erfüllt |

**Gruppen (p95 nach Kriterium)**

| Gruppe | Anzahl | p50 | p95 | p99 | max | 5xx |
|---|---:|---:|---:|---:|---:|---:|
| Listen und Akten | 210 | 83 | 824 | 859 | 906 | 0 |
| Editor-Aktionen | 210 | 13 | 34 | 68 | 118 | 0 |

**Betrieb (/health alle 10 s, 3 Proben)**: Pool-Spitze 9 von 90 (10.0 %) · WAL max 0.72 MB · Schreibsperre max 14 ms, locked 0 · RSS max 170.9 MB · CPU 15.0 s · /health p95 68 ms · Status: ok ×3

**Server-Sicht (zugriff.log der Kopie)**: 432 Anfragen (432.0/min) · 5xx 0 · Pool-Spitze zu Anfragebeginn 13 · Anteil > 2 s 0.0 %

| Route (Server) | Anzahl | p50 | p95 | max | 5xx |
|---|---:|---:|---:|---:|---:|
| `GET /angebote/{id}` | 210 | 81 | 819 | 904 | 0 |
| `POST /angebote/{id}/position/{pid}/menge` | 190 | 10 | 28 | 48 | 0 |
| `POST /angebote/{id}/sperre-frei` | 20 | 6 | 20 | 32 | 0 |
| `GET /` | 4 | 58 | 58 | 58 | 0 |
| `GET /erfassungen` | 4 | 49 | 57 | 57 | 0 |
| `GET /erfassungen/{id}` | 4 | 11 | 13 | 13 | 0 |

**Fehlerprotokoll der Kopie**: 0 neue Tabelleneinträge · fehler.log: 0 Fehler-Nummern, „database is locked“ 0 (Anfragen 0), TimeoutError 0, QueuePool 0

**Schreibsturm (Soll/Ist je Position aus der Kopie)**: 190 Positionen geändert · 190 korrekt · 0 Abweichungen · 5xx bei Editor-Aktionen: 0 · nicht bestätigte Änderungen: 0

Zähler: schreibsturm_wenig_positionen = 1

Rohdaten: `C:\Users\a.scheelen\Tools\Angebotstool\diagnose\test_v27\lasttest_20261006-230005.json` · Serverkonsole: `C:\Users\a.scheelen\Tools\Angebotstool\diagnose\test_v27\server_20261006-230005.log`

_Hinweis Orchestrator: 20 Innendienst-Nutzer gleichzeitig, 190 Positionsänderungen in 20 verschiedenen Angeboten (ein Angebot hatte weniger als 10 Positionen) – Soll/Ist je Position 190/190, keine verlorene Änderung, keine 500er._

### 4.4 Stressstufe (100 Nutzer, 10 Minuten) – Reserve-Faktor

<!-- lasttest.py 20261006-230058 -->
### Lauf 06.10.2026 23:01:06 – Profil stress, 100 Nutzer (70 aktiv), 10 min

- Lastmodell: 28 Außendienst mobil, 23 Innendienst, 11 Lead-Management, 6 Projektierung, 2 Montage; dazu 30 angemeldete Leser · Denkzeit 5–15 s · Seed 27 · Latenz je externem Aufruf 2 s · Port 8001
- Server: v27 · Commit da9df30 · Pool 20 (max 90) · Threads 64 · Scheduler 13 Läufe · DATA_ORDNER `C:\Users\a.scheelen\Tools\Angebotstool\diagnose\test_v27\data`
- Benutzer je Rolle: Außendienst mobil = 4, 7, 9, 13, 15, 17; Innendienst = 14, 18; Lead-Management = 1, 2, 12, 16, 20; Projektierung = 1, 2, 12, 16, 20; Montage = 24
- Hinweis: keine aktive Person mit Hauptrolle „leadmanagement“ in der Kopie – Admins übernehmen die Rolle [ANNAHME]
- Hinweis: keine aktive Person mit Hauptrolle „projektierung“ in der Kopie – Admins übernehmen die Rolle [ANNAHME]
- Anfragen gesamt: 6322 (631.2/min) · 5xx 41 · Timeouts 0 · Verbindungsfehler 7 · Szenarien 584 · Tool-Fehler 0 · Laufzeit 10.0 min (06.10.2026 23:01:06 – 23:11:07)

**Antwortzeiten je Route (Client-Sicht, Millisekunden)**

| Route | Anzahl | p50 | p95 | p99 | max | 5xx | Timeout | Verb. |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| `GET /erfassung/{id}/seite/{nr}` | 900 | 37 | 361 | 586 | 906 | 0 | 0 | 0 |
| `POST /erfassung/{id}/seite/{nr}` | 887 | 51 | 3.037 | 9.802 | 18.013 | 17 | 0 | 0 |
| `GET /angebote/{id}` | 833 | 137 | 1.380 | 1.936 | 2.336 | 0 | 0 | 7 |
| `POST /angebote/{id}/position/{pid}/menge` | 684 | 38 | 1.412 | 8.850 | 18.529 | 0 | 0 | 0 |
| `GET /lead-management/lead/{id}` | 260 | 105 | 2.752 | 5.903 | 7.208 | 0 | 0 | 0 |
| `GET /projektierung/projekt/{id}` | 169 | 130 | 803 | 1.180 | 2.016 | 0 | 0 | 0 |
| `GET /leads` | 137 | 86 | 701 | 1.265 | 1.305 | 0 | 0 | 0 |
| `GET /erfassung/sparten` | 136 | 40 | 395 | 687 | 736 | 0 | 0 | 0 |
| `GET /leads/{id}/erfassen` | 136 | 52 | 427 | 652 | 652 | 0 | 0 | 0 |
| `GET /lead-management/hauptboard` | 134 | 246 | 2.002 | 2.436 | 2.836 | 0 | 0 | 0 |
| `GET /lead-management/lead/{id}/termin/vorschlaege.json` | 134 | 3.539 | 8.728 | 15.262 | 19.790 | 4 | 0 | 0 |
| `POST /erfassung/sparten-start` | 132 | 203 | 2.716 | 5.688 | 8.890 | 1 | 0 | 0 |
| `GET /erfassung/{id}/weiche` | 131 | 36 | 345 | 439 | 464 | 0 | 0 | 0 |
| `POST /lead-management/anruf/{id}` | 129 | 46 | 2.685 | 10.345 | 15.640 | 3 | 0 | 0 |
| `GET /lead-management/terminiert` | 125 | 586 | 3.410 | 3.848 | 4.830 | 0 | 0 | 0 |
| `GET /` | 114 | 296 | 1.443 | 2.468 | 2.729 | 0 | 0 | 0 |
| `GET /erfassung/{id}/pruefen` | 94 | 27 | 287 | 564 | 1.040 | 0 | 0 | 0 |
| `POST /erfassung/{id}/absenden` | 94 | 174 | 10.632 | 15.329 | 18.010 | 8 | 0 | 0 |
| `GET /erfassungen/{id}/protokoll.pdf` | 92 | 449 | 1.207 | 1.920 | 2.026 | 0 | 0 | 0 |
| `GET /erfassungen` | 87 | 266 | 1.332 | 1.705 | 1.738 | 0 | 0 | 0 |
| `GET /projektierung` | 87 | 179 | 1.459 | 1.803 | 2.020 | 0 | 0 | 0 |
| `POST /projektierung/aufgabe/{id}/erledigt-umschalten` | 85 | 97 | 5.580 | 6.673 | 17.511 | 3 | 0 | 0 |
| `GET /erfassungen/{id}` | 84 | 48 | 358 | 435 | 450 | 0 | 0 | 0 |
| `POST /vorgaenge/{id}/galerie/upload` | 83 | 301 | 3.301 | 6.402 | 7.648 | 1 | 0 | 0 |
| `GET /erfassungen/{id}/angebot-erzeugen` | 79 | 79 | 1.468 | 3.510 | 3.876 | 0 | 0 | 0 |
| `GET /erfassung` | 78 | 89 | 934 | 1.133 | 1.259 | 0 | 0 | 0 |
| `GET /angebote/{id}/pdf` | 70 | 1.320 | 2.807 | 3.127 | 3.314 | 0 | 0 | 0 |
| `GET /vorgaenge/{id}` | 70 | 132 | 4.608 | 6.071 | 8.270 | 2 | 0 | 0 |
| `POST /angebote/{id}/email` | 70 | 13.664 | 17.436 | 18.610 | 25.497 | 0 | 0 | 0 |
| `POST /angebote/{id}/sperre-frei` | 69 | 29 | 272 | 322 | 685 | 0 | 0 | 0 |
| `GET /montage/einsatz/{id}` | 65 | 70 | 407 | 467 | 654 | 0 | 0 | 0 |
| `GET /montage` | 34 | 68 | 797 | 899 | 899 | 0 | 0 | 0 |
| `POST /montage/einsatz/{id}/foto` | 33 | 250 | 6.075 | 11.574 | 11.574 | 2 | 0 | 0 |
| `POST /montage/aufgabe/{id}/erledigt` | 7 | 36 | 3.648 | 3.648 | 3.648 | 0 | 0 | 0 |

**Zielwerte Phase 131 [ANNAHME]**

| Kriterium | Ziel | Ist | Ergebnis |
|---|---|---|---|
| p95 Listen und Akten | ≤ 1500 ms | 1459 ms (n = 2277, p50 146 ms) | erfüllt |
| p95 Editor-Aktionen | ≤ 1000 ms | 1356 ms (n = 753, p50 37 ms) | **nicht erfüllt** |
| p95 Angebots-PDF | ≤ 4000 ms | 2807 ms (n = 70, p50 1320 ms) | erfüllt |
| p95 Protokoll-PDF | ≤ 3000 ms | 1207 ms (n = 92, p50 449 ms) | erfüllt |
| p95 Terminvorschläge | ≤ 6000 ms | 8728 ms (n = 134, p50 3539 ms) | **nicht erfüllt** |
| TimeoutError (Pool) / Client-Timeouts | 0 | Server 0 · Client 0 | erfüllt |
| „database is locked“ an der Oberfläche | 0 | 7 (fehler.log gesamt 32, davon Anfragen 0) | **nicht erfüllt** |
| Pool-Spitze | ≤ 60 % von 90 | 41 (45.6 %) | erfüllt |
| Fehlerquote (5xx + Timeouts + Verbindungsfehler) | < 0.1 % | 0.759 % (48 von 6322) | **nicht erfüllt** |

**Gruppen (p95 nach Kriterium)**

| Gruppe | Anzahl | p50 | p95 | p99 | max | 5xx |
|---|---:|---:|---:|---:|---:|---:|
| Listen und Akten | 2277 | 146 | 1.459 | 3.159 | 8.270 | 2 |
| Editor-Aktionen | 753 | 37 | 1.356 | 7.839 | 18.529 | 0 |
| Angebots-PDF | 70 | 1.320 | 2.807 | 3.127 | 3.314 | 0 |
| Protokoll-PDF | 92 | 449 | 1.207 | 1.920 | 2.026 | 0 |
| Terminvorschläge | 134 | 3.539 | 8.728 | 15.262 | 19.790 | 4 |
| übrige Schritte | 2996 | 52 | 3.150 | 14.396 | 25.497 | 35 |

**Betrieb (/health alle 10 s, 60 Proben)**: Pool-Spitze 34 von 90 (37.8 %) · WAL max 4.29 MB · Schreibsperre max 5904 ms, locked 16 · RSS max 382.8 MB · CPU 479.2 s · /health p95 395 ms · Status: ok ×60

**Server-Sicht (zugriff.log der Kopie)**: 6317 Anfragen (630.7/min) · 5xx 48 · Pool-Spitze zu Anfragebeginn 41 · Anteil > 2 s 5.98 %

| Route (Server) | Anzahl | p50 | p95 | max | 5xx |
|---|---:|---:|---:|---:|---:|
| `GET /erfassung/{id}/seite/{nr}` | 900 | 33 | 327 | 860 | 0 |
| `POST /erfassung/{id}/seite/{nr}` | 887 | 34 | 2.944 | 6.647 | 17 |
| `GET /angebote/{id}` | 826 | 131 | 1.376 | 2.240 | 0 |
| `POST /angebote/{id}/position/{pid}/menge` | 684 | 22 | 1.405 | 12.485 | 6 |
| `GET /lead-management/lead/{id}` | 260 | 99 | 2.723 | 7.164 | 0 |
| `GET /projektierung/projekt/{id}` | 169 | 111 | 767 | 1.991 | 0 |
| `GET /leads` | 137 | 70 | 654 | 1.274 | 0 |
| `GET /leads/{id}/erfassen` | 136 | 34 | 372 | 594 | 0 |
| `GET /erfassung/sparten` | 136 | 37 | 386 | 678 | 0 |
| `GET /lead-management/hauptboard` | 135 | 237 | 1.994 | 2.830 | 0 |
| `GET /lead-management/lead/{id}/termin/vorschlaege.json` | 134 | 3.537 | 8.435 | 19.788 | 4 |
| `POST /erfassung/sparten-start` | 132 | 143 | 2.668 | 5.796 | 1 |
| `GET /erfassung/{id}/weiche` | 131 | 34 | 343 | 459 | 0 |
| `POST /lead-management/anruf/{id}` | 129 | 27 | 2.668 | 6.137 | 3 |
| `GET /lead-management/terminiert` | 125 | 564 | 3.386 | 4.738 | 0 |

**Fehlerprotokoll der Kopie**: 47 neue Tabelleneinträge · fehler.log: 0 Fehler-Nummern, „database is locked“ 32 (Anfragen 0), TimeoutError 0, QueuePool 0

**Reserve-Faktor (Stressstufe, Ziel-p95 ÷ Ist-p95 je Gruppe; > 1 = Reserve) [ANNAHME]**: Listen und Akten 1.03, Editor-Aktionen 0.74, Angebots-PDF 1.43, Protokoll-PDF 2.49, Terminvorschläge 0.69 · Minimum 0.69 · Pool-Reserve 1.59

Zähler: ad_start_fehlgeschlagen = 1, formularfehler = 4, id_angebot_erzeugen_fallback:/erfassungen (Antworten unvollständig für die aktuelle Logik) = 32, id_angebot_erzeugt = 47, id_erfassung_vom_aussendienst = 52, szenario_bei_laufende_abgebrochen = 100, verbindungsfehler_detail:RemoteProtocolError = 7, vorschlaege_status:adresse_fehlt = 1, vorschlaege_status:hv_lead = 23, vorschlaege_status:ok = 106

Rohdaten: `C:\Users\a.scheelen\Tools\Angebotstool\diagnose\test_v27\lasttest_20261006-230058.json` · Serverkonsole: `C:\Users\a.scheelen\Tools\Angebotstool\diagnose\test_v27\server_20261006-230058.log`

_Hinweis Orchestrator: Stressstufe ohne Abnahmekriterien (Plan). Bei doppelter Last (70 gleichzeitig aktive Nutzer) erreicht die Wartezeit auf die SQLite-Schreibsperre bis 5,9 s (busy_timeout 5 s) – 7 Anfragen scheiterten mit „Datenbank kurz belegt“, 41 × 5xx gesamt (0,76 %), Pool-Spitze 45,6 %. Reserve-Faktor (Ziel-p95 ÷ Ist-p95) minimal 0,69 (Terminvorschläge), Editor 0,74, Listen/Akten 1,03, PDFs 1,43/2,49; Pool-Reserve 1,59. Die Grenze liegt damit bei etwa dem 1,4-fachen des Lastmodells (≈ 50 gleichzeitig aktive Nutzer), limitierender Faktor ist der Ein-Schreiber-Betrieb von SQLite, nicht der Pool._

### 4.5 Entscheidung (Regel aus Abschnitt 2)

**SQLite bestätigt.** Lauf 2 (Lastmodell 50 Nutzer, 35 aktiv, 20 Minuten, 2 s simulierte Latenz je externem Aufruf) erfüllt nach Behebung der Befunde aus Lauf 1 alle Zielwerte mit Abstand: p95 Listen und Akten 494 ms (Ziel 1.500), Editor 291 ms (1.000), Angebots-PDF 1.887 ms (4.000), Protokoll-PDF 649 ms (3.000), Terminvorschläge 4.206 ms (6.000), 0 TimeoutError, 0 „database is locked“, Pool-Spitze 17,8 % (≤ 60 %), Fehlerquote 0,000 %. Die Regel aus Abschnitt 2 greift nicht (Zielwerte erreicht) – kein PostgreSQL-Umstieg in v27; nächster Lasttest nach dem nächsten großen Modul.

Einordnung aus der Stressstufe: bei doppelter Last (70 aktive Nutzer) ist die Ein-Schreiber-Grenze von SQLite nachweislich der limitierende Faktor (Schreibsperre bis 5,9 s, 7 × „Datenbank kurz belegt“, Editor-p95 1,36 s, Terminvorschläge-p95 8,7 s). Die Reserve zum Lastmodell beträgt rund 40 % (Reserve-Faktor 0,69 bei 2× Last ≈ Grenze bei 1,4× Last). Wächst die Nutzerzahl deutlich über 50 oder kommen schreibintensive Module hinzu, ist ein PostgreSQL-Umstieg (eigener Plan) oder eine weitere Verkürzung der Schreibtransaktionen (Schreibsturm-Pfade, Terminvorschläge-Cache in der DB) vorzusehen – Entscheidung beim nächsten Lasttest.

Schreibsturm (20 Innendienst-Nutzer × 10 Positionen): 190/190 Positionen korrekt, keine verlorene Änderung, keine 500er, Editor-POST p95 34 ms.

### 4.6 Probeläufe 06.10.2026 (Agent E)

Drei Probeläufe mit 10 Nutzern à 2 Minuten (Denkzeit 5–15 s bzw. 1–3 s) und
ein Mini-Schreibsturm (5 Nutzer): 0 × 5xx, 0 Timeouts, 0 Tool-Fehler,
Soll/Ist 50/50 Positionen – Berichte `diagnose/test_v27/lasttest_20261006-*.md`,
Auswertung in `diagnose/v27_patches/E_ergebnis.md`. Die Probeläufe prüfen nur
das Werkzeug (Routen, Formulare, Mocks, Bericht), nicht die Zielwerte.

### 4.7 Läufe nach v29 (08.10.2026, Durchlauf v27-Nachtrag 2 + v28 + v29)

Wiederholung nach PLAN_LEAD_V4 (Einfügung): Profil normal, 50 Nutzer, 20 Minuten, Server v29 mit 14
Scheduler-Läufen, Terminassistent mit drei Vorschlägen und Kalenderansicht (nachgelagert per fetch),
Hauptboard mit Spaltenbreiten, Dashboard „Hallo, <Vorname>“. Zielwerte unverändert (Abschnitt 2).
Kopie: `diagnose/angebotstool.db` (Stand 03.10.2026) → `diagnose/test_v28_final/lasttest_data`
(`--frisch`, migrate ×2). Berichte 1:1 aus `lasttest.py`.

#### Lauf 1 (08.10.2026 02:36)

<!-- lasttest.py 20261008-023605 -->
### Lauf 08.10.2026 02:36:13 – Profil normal, 50 Nutzer (35 aktiv), 20 min

- Lastmodell: 14 Außendienst mobil, 11 Innendienst, 6 Lead-Management, 3 Projektierung, 1 Montage; dazu 15 angemeldete Leser · Denkzeit 5–15 s · Seed 27 · Latenz je externem Aufruf 2 s · Port 8001
- Server: v29 · Commit 1e317e7 · Pool 20 (max 90) · Threads 64 · Scheduler 14 Läufe · DATA_ORDNER `C:\Users\a.scheelen\Tools\Angebotstool\diagnose\test_v28_final\lasttest_data`
- Benutzer je Rolle: Außendienst mobil = 4, 7, 9, 13, 15, 17; Innendienst = 14, 18; Lead-Management = 1, 2, 12, 16, 20; Projektierung = 1, 2, 12, 16, 20; Montage = 24
- Hinweis: keine aktive Person mit Hauptrolle „leadmanagement“ in der Kopie – Admins übernehmen die Rolle [ANNAHME]
- Hinweis: keine aktive Person mit Hauptrolle „projektierung“ in der Kopie – Admins übernehmen die Rolle [ANNAHME]
- Anfragen gesamt: 6594 (329.2/min) · 5xx 1 · Timeouts 0 · Verbindungsfehler 0 · Szenarien 630 · Tool-Fehler 0 · Laufzeit 20.0 min (08.10.2026 02:36:13 – 02:56:15)

**Antwortzeiten je Route (Client-Sicht, Millisekunden)**

| Route | Anzahl | p50 | p95 | p99 | max | 5xx | Timeout | Verb. |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| `GET /erfassung/{id}/seite/{nr}` | 945 | 20 | 81 | 310 | 681 | 0 | 0 | 0 |
| `POST /erfassung/{id}/seite/{nr}` | 935 | 22 | 573 | 1.594 | 2.586 | 0 | 0 | 0 |
| `GET /angebote/{id}` | 851 | 56 | 269 | 751 | 1.189 | 0 | 0 | 0 |
| `POST /angebote/{id}/position/{pid}/menge` | 709 | 21 | 342 | 1.042 | 6.618 | 0 | 0 | 0 |
| `GET /lead-management/lead/{id}` | 306 | 50 | 491 | 947 | 2.326 | 0 | 0 | 0 |
| `GET /projektierung/projekt/{id}` | 174 | 66 | 414 | 672 | 760 | 0 | 0 | 0 |
| `GET /lead-management/hauptboard` | 154 | 107 | 1.313 | 2.034 | 2.161 | 0 | 0 | 0 |
| `GET /lead-management/lead/{id}/termin/vorschlaege.json` | 154 | 2.884 | 4.015 | 5.076 | 8.940 | 0 | 0 | 0 |
| `POST /lead-management/anruf/{id}` | 152 | 22 | 592 | 2.225 | 3.021 | 0 | 0 | 0 |
| `GET /lead-management/terminiert` | 150 | 436 | 823 | 2.744 | 2.961 | 0 | 0 | 0 |
| `GET /erfassung/sparten` | 126 | 19 | 197 | 292 | 419 | 0 | 0 | 0 |
| `GET /leads` | 126 | 37 | 343 | 771 | 980 | 0 | 0 | 0 |
| `GET /leads/{id}/erfassen` | 126 | 28 | 197 | 371 | 671 | 0 | 0 | 0 |
| `GET /erfassung/{id}/weiche` | 125 | 17 | 102 | 234 | 306 | 0 | 0 | 0 |
| `POST /erfassung/sparten-start` | 125 | 29 | 817 | 1.494 | 1.554 | 0 | 0 | 0 |
| `GET /` | 116 | 80 | 1.004 | 1.282 | 1.323 | 0 | 0 | 0 |
| `GET /erfassung/{id}/pruefen` | 112 | 19 | 73 | 283 | 893 | 0 | 0 | 0 |
| `GET /erfassungen/{id}/protokoll.pdf` | 112 | 263 | 749 | 1.242 | 1.440 | 0 | 0 | 0 |
| `POST /erfassung/{id}/absenden` | 112 | 38 | 507 | 1.800 | 2.531 | 0 | 0 | 0 |
| `GET /projektierung` | 88 | 64 | 716 | 976 | 1.078 | 0 | 0 | 0 |
| `POST /projektierung/aufgabe/{id}/erledigt-umschalten` | 87 | 76 | 824 | 1.013 | 1.200 | 0 | 0 | 0 |
| `POST /vorgaenge/{id}/galerie/upload` | 86 | 200 | 1.007 | 1.278 | 1.598 | 0 | 0 | 0 |
| `GET /erfassungen` | 77 | 141 | 581 | 692 | 931 | 0 | 0 | 0 |
| `GET /erfassungen/{id}` | 77 | 33 | 142 | 365 | 484 | 0 | 0 | 0 |
| `GET /erfassung` | 76 | 44 | 242 | 398 | 700 | 0 | 0 | 0 |
| `GET /erfassungen/{id}/angebot-erzeugen` | 76 | 52 | 368 | 784 | 961 | 0 | 0 | 0 |
| `GET /montage/einsatz/{id}` | 76 | 27 | 118 | 488 | 500 | 0 | 0 | 0 |
| `GET /angebote/{id}/pdf` | 66 | 930 | 1.963 | 2.938 | 3.157 | 0 | 0 | 0 |
| `GET /vorgaenge/{id}` | 66 | 48 | 337 | 390 | 1.115 | 0 | 0 | 0 |
| `POST /angebote/{id}/email` | 66 | 13.128 | 16.196 | 16.917 | 17.234 | 0 | 0 | 0 |
| `POST /angebote/{id}/sperre-frei` | 66 | 21 | 88 | 207 | 244 | 0 | 0 | 0 |
| `GET /montage` | 39 | 34 | 236 | 396 | 396 | 0 | 0 | 0 |
| `POST /montage/einsatz/{id}/foto` | 38 | 45 | 1.201 | 6.846 | 6.846 | 1 | 0 | 0 |

**Zielwerte Phase 131 [ANNAHME]**

| Kriterium | Ziel | Ist | Ergebnis |
|---|---|---|---|
| p95 Listen und Akten | ≤ 1500 ms | 520 ms (n = 2376, p50 63 ms) | erfüllt |
| p95 Editor-Aktionen | ≤ 1000 ms | 284 ms (n = 775, p50 21 ms) | erfüllt |
| p95 Angebots-PDF | ≤ 4000 ms | 1963 ms (n = 66, p50 930 ms) | erfüllt |
| p95 Protokoll-PDF | ≤ 3000 ms | 749 ms (n = 112, p50 263 ms) | erfüllt |
| p95 Terminvorschläge | ≤ 6000 ms | 4015 ms (n = 154, p50 2884 ms) | erfüllt |
| TimeoutError (Pool) / Client-Timeouts | 0 | Server 0 · Client 0 | erfüllt |
| „database is locked“ an der Oberfläche | 0 | 1 (fehler.log gesamt 5, davon Anfragen 1) | **nicht erfüllt** |
| Pool-Spitze | ≤ 60 % von 90 | 16 (17.8 %) | erfüllt |
| Fehlerquote (5xx + Timeouts + Verbindungsfehler) | < 0.1 % | 0.015 % (1 von 6594) | erfüllt |

**Gruppen (p95 nach Kriterium)**

| Gruppe | Anzahl | p50 | p95 | p99 | max | 5xx |
|---|---:|---:|---:|---:|---:|---:|
| Listen und Akten | 2376 | 63 | 520 | 1.078 | 2.961 | 0 |
| Editor-Aktionen | 775 | 21 | 284 | 1.042 | 6.618 | 0 |
| Angebots-PDF | 66 | 930 | 1.963 | 2.938 | 3.157 | 0 |
| Protokoll-PDF | 112 | 263 | 749 | 1.242 | 1.440 | 0 |
| Terminvorschläge | 154 | 2.884 | 4.015 | 5.076 | 8.940 | 0 |
| übrige Schritte | 3111 | 24 | 630 | 13.151 | 17.234 | 1 |

**Betrieb (/health alle 10 s, 120 Proben)**: Pool-Spitze 5 von 90 (5.6 %) · WAL max 4.18 MB · Schreibsperre max 5595 ms, locked 1 · RSS max 368.9 MB · CPU 484.9 s · /health p95 159 ms · Status: ok ×120

**Server-Sicht (zugriff.log der Kopie)**: 6598 Anfragen (329.4/min) · 5xx 1 · Pool-Spitze zu Anfragebeginn 16 · Anteil > 2 s 3.03 %

| Route (Server) | Anzahl | p50 | p95 | max | 5xx |
|---|---:|---:|---:|---:|---:|
| `GET /erfassung/{id}/seite/{nr}` | 945 | 17 | 75 | 679 | 0 |
| `POST /erfassung/{id}/seite/{nr}` | 935 | 14 | 567 | 2.562 | 0 |
| `GET /angebote/{id}` | 851 | 54 | 255 | 1.174 | 0 |
| `POST /angebote/{id}/position/{pid}/menge` | 709 | 11 | 251 | 6.582 | 0 |
| `GET /lead-management/lead/{id}` | 306 | 43 | 457 | 2.296 | 0 |
| `GET /projektierung/projekt/{id}` | 174 | 60 | 389 | 686 | 0 |
| `GET /lead-management/hauptboard` | 157 | 92 | 1.237 | 2.144 | 0 |
| `GET /lead-management/lead/{id}/termin/vorschlaege.json` | 154 | 2.882 | 4.013 | 8.938 | 0 |
| `POST /lead-management/anruf/{id}` | 152 | 12 | 572 | 3.002 | 0 |
| `GET /lead-management/terminiert` | 150 | 421 | 815 | 2.915 | 0 |
| `GET /leads` | 126 | 25 | 240 | 958 | 0 |
| `GET /leads/{id}/erfassen` | 126 | 14 | 161 | 584 | 0 |
| `GET /erfassung/sparten` | 126 | 17 | 177 | 413 | 0 |
| `POST /erfassung/sparten-start` | 125 | 17 | 812 | 1.549 | 0 |
| `GET /erfassung/{id}/weiche` | 125 | 15 | 79 | 287 | 0 |

**Fehlerprotokoll der Kopie**: 1 neue Tabelleneinträge · fehler.log: 1 Fehler-Nummern, „database is locked“ 5 (Anfragen 1), TimeoutError 0, QueuePool 0
- F-20261008-023828-d3f3 · POST /montage/einsatz/1/foto · OperationalError

Zähler: formularfehler = 2, id_angebot_erzeugen_fallback:/erfassungen (Antworten unvollständig für die aktuelle Logik) = 11, id_angebot_erzeugt = 65, id_erfassung_vom_aussendienst = 66, szenario_bei_laufende_abgebrochen = 50, vorschlaege_status:hv_lead = 18, vorschlaege_status:ok = 136

Rohdaten: `C:\Users\a.scheelen\Tools\Angebotstool\diagnose\test_v27\lasttest_20261008-023605.json` · Serverkonsole: `C:\Users\a.scheelen\Tools\Angebotstool\diagnose\test_v27\server_20261008-023605.log`

_Hinweis Orchestrator (Lauf 1): alle Zielwerte erfüllt bis auf **„database is locked“ an der Oberfläche: 1** – `POST /montage/einsatz/1/foto` (2-MB-Foto, 02:38:28) lief in die 5-s-Busy-Grenze, während eine fremde Schreibtransaktion die Sperre etwa 5,6 s hielt (Schreibsperren-Messung des Angebots-Editors: `POST …/position/{pid}/menge` wartete 6,6 s und kam durch). Verursacher aus zugriff.log/scheduler_status nicht eindeutig: zeitgleich liefen der Lauf `mail-sync` (02:36:30–02:39:34, simulierte Graph-Latenz), `GET …/termin/vorschlaege.json` (8,9 s) und Angebots-PDFs. Fehlerquote 0,015 % (1 von 6.594). Lauf 2 unten als Wiederholung._

#### Lauf 2 (08.10.2026 03:00) – Wiederholung ohne Codeänderung

<!-- lasttest.py 20261008-030038 -->
### Lauf 08.10.2026 03:00:46 – Profil normal, 50 Nutzer (35 aktiv), 20 min

- Lastmodell: 14 Außendienst mobil, 11 Innendienst, 6 Lead-Management, 3 Projektierung, 1 Montage; dazu 15 angemeldete Leser · Denkzeit 5–15 s · Seed 27 · Latenz je externem Aufruf 2 s · Port 8001
- Server: v29 · Commit 1e317e7 · Pool 20 (max 90) · Threads 64 · Scheduler 14 Läufe · DATA_ORDNER `C:\Users\a.scheelen\Tools\Angebotstool\diagnose\test_v28_final\lasttest_data`
- Benutzer je Rolle: Außendienst mobil = 4, 7, 9, 13, 15, 17; Innendienst = 14, 18; Lead-Management = 1, 2, 12, 16, 20; Projektierung = 1, 2, 12, 16, 20; Montage = 24
- Hinweis: keine aktive Person mit Hauptrolle „leadmanagement“ in der Kopie – Admins übernehmen die Rolle [ANNAHME]
- Hinweis: keine aktive Person mit Hauptrolle „projektierung“ in der Kopie – Admins übernehmen die Rolle [ANNAHME]
- Anfragen gesamt: 6584 (328.9/min) · 5xx 1 · Timeouts 0 · Verbindungsfehler 0 · Szenarien 631 · Tool-Fehler 0 · Laufzeit 20.0 min (08.10.2026 03:00:46 – 03:20:47)

**Antwortzeiten je Route (Client-Sicht, Millisekunden)**

| Route | Anzahl | p50 | p95 | p99 | max | 5xx | Timeout | Verb. |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| `GET /erfassung/{id}/seite/{nr}` | 939 | 20 | 174 | 370 | 584 | 0 | 0 | 0 |
| `POST /erfassung/{id}/seite/{nr}` | 929 | 27 | 733 | 1.639 | 3.006 | 0 | 0 | 0 |
| `GET /angebote/{id}` | 852 | 58 | 380 | 986 | 2.688 | 0 | 0 | 0 |
| `POST /angebote/{id}/position/{pid}/menge` | 710 | 21 | 377 | 1.127 | 3.354 | 0 | 0 | 0 |
| `GET /lead-management/lead/{id}` | 305 | 51 | 382 | 1.032 | 3.229 | 0 | 0 | 0 |
| `GET /projektierung/projekt/{id}` | 173 | 72 | 418 | 1.240 | 1.760 | 0 | 0 | 0 |
| `GET /lead-management/hauptboard` | 155 | 105 | 1.392 | 1.728 | 2.211 | 0 | 0 | 0 |
| `GET /lead-management/lead/{id}/termin/vorschlaege.json` | 153 | 2.871 | 4.476 | 5.591 | 9.866 | 0 | 0 | 0 |
| `POST /lead-management/anruf/{id}` | 151 | 21 | 789 | 1.559 | 4.637 | 0 | 0 | 0 |
| `GET /lead-management/terminiert` | 150 | 452 | 829 | 4.449 | 4.846 | 0 | 0 | 0 |
| `GET /erfassung/sparten` | 126 | 20 | 128 | 209 | 329 | 0 | 0 | 0 |
| `GET /leads` | 126 | 37 | 466 | 812 | 993 | 0 | 0 | 0 |
| `GET /leads/{id}/erfassen` | 126 | 27 | 231 | 344 | 558 | 0 | 0 | 0 |
| `GET /erfassung/{id}/weiche` | 125 | 17 | 79 | 239 | 332 | 0 | 0 | 0 |
| `POST /erfassung/sparten-start` | 125 | 24 | 870 | 1.628 | 2.881 | 0 | 0 | 0 |
| `GET /` | 116 | 72 | 958 | 1.072 | 1.116 | 0 | 0 | 0 |
| `GET /erfassung/{id}/pruefen` | 112 | 18 | 97 | 185 | 278 | 0 | 0 | 0 |
| `GET /erfassungen/{id}/protokoll.pdf` | 112 | 270 | 979 | 1.516 | 1.930 | 0 | 0 | 0 |
| `POST /erfassung/{id}/absenden` | 112 | 40 | 690 | 2.718 | 7.656 | 1 | 0 | 0 |
| `GET /projektierung` | 88 | 51 | 729 | 1.041 | 1.370 | 0 | 0 | 0 |
| `POST /projektierung/aufgabe/{id}/erledigt-umschalten` | 87 | 61 | 809 | 1.006 | 1.362 | 0 | 0 | 0 |
| `POST /vorgaenge/{id}/galerie/upload` | 86 | 202 | 613 | 1.596 | 1.661 | 0 | 0 | 0 |
| `GET /montage/einsatz/{id}` | 78 | 40 | 365 | 462 | 909 | 0 | 0 | 0 |
| `GET /erfassungen` | 77 | 90 | 591 | 936 | 1.219 | 0 | 0 | 0 |
| `GET /erfassungen/{id}` | 77 | 25 | 52 | 164 | 535 | 0 | 0 | 0 |
| `GET /erfassung` | 76 | 41 | 190 | 360 | 429 | 0 | 0 | 0 |
| `GET /erfassungen/{id}/angebot-erzeugen` | 76 | 41 | 338 | 794 | 1.450 | 0 | 0 | 0 |
| `GET /angebote/{id}/pdf` | 66 | 1.030 | 2.419 | 2.685 | 2.842 | 0 | 0 | 0 |
| `GET /vorgaenge/{id}` | 66 | 43 | 872 | 1.288 | 1.909 | 0 | 0 | 0 |
| `POST /angebote/{id}/email` | 66 | 13.084 | 15.864 | 16.509 | 16.949 | 0 | 0 | 0 |
| `POST /angebote/{id}/sperre-frei` | 66 | 21 | 141 | 318 | 352 | 0 | 0 | 0 |
| `GET /montage` | 39 | 30 | 103 | 428 | 428 | 0 | 0 | 0 |
| `POST /montage/einsatz/{id}/foto` | 39 | 59 | 504 | 988 | 988 | 0 | 0 | 0 |

**Zielwerte Phase 131 [ANNAHME]**

| Kriterium | Ziel | Ist | Ergebnis |
|---|---|---|---|
| p95 Listen und Akten | ≤ 1500 ms | 591 ms (n = 2378, p50 63 ms) | erfüllt |
| p95 Editor-Aktionen | ≤ 1000 ms | 352 ms (n = 776, p50 21 ms) | erfüllt |
| p95 Angebots-PDF | ≤ 4000 ms | 2419 ms (n = 66, p50 1030 ms) | erfüllt |
| p95 Protokoll-PDF | ≤ 3000 ms | 979 ms (n = 112, p50 270 ms) | erfüllt |
| p95 Terminvorschläge | ≤ 6000 ms | 4476 ms (n = 153, p50 2871 ms) | erfüllt |
| TimeoutError (Pool) / Client-Timeouts | 0 | Server 0 · Client 0 | erfüllt |
| „database is locked“ an der Oberfläche | 0 | 1 (fehler.log gesamt 5, davon Anfragen 1) | **nicht erfüllt** |
| Pool-Spitze | ≤ 60 % von 90 | 15 (16.7 %) | erfüllt |
| Fehlerquote (5xx + Timeouts + Verbindungsfehler) | < 0.1 % | 0.015 % (1 von 6584) | erfüllt |

**Gruppen (p95 nach Kriterium)**

| Gruppe | Anzahl | p50 | p95 | p99 | max | 5xx |
|---|---:|---:|---:|---:|---:|---:|
| Listen und Akten | 2378 | 63 | 591 | 1.370 | 4.846 | 0 |
| Editor-Aktionen | 776 | 21 | 352 | 1.083 | 3.354 | 0 |
| Angebots-PDF | 66 | 1.030 | 2.419 | 2.685 | 2.842 | 0 |
| Protokoll-PDF | 112 | 270 | 979 | 1.516 | 1.930 | 0 |
| Terminvorschläge | 153 | 2.871 | 4.476 | 5.591 | 9.866 | 0 |
| übrige Schritte | 3099 | 25 | 690 | 13.118 | 16.949 | 1 |

**Betrieb (/health alle 10 s, 120 Proben)**: Pool-Spitze 11 von 90 (12.2 %) · WAL max 4.18 MB · Schreibsperre max 3311 ms, locked 0 · RSS max 377.7 MB · CPU 486.2 s · /health p95 225 ms · Status: ok ×120

**Server-Sicht (zugriff.log der Kopie)**: 6588 Anfragen (329.1/min) · 5xx 1 · Pool-Spitze zu Anfragebeginn 15 · Anteil > 2 s 3.01 %

| Route (Server) | Anzahl | p50 | p95 | max | 5xx |
|---|---:|---:|---:|---:|---:|
| `GET /erfassung/{id}/seite/{nr}` | 939 | 17 | 150 | 577 | 0 |
| `POST /erfassung/{id}/seite/{nr}` | 929 | 14 | 705 | 3.000 | 0 |
| `GET /angebote/{id}` | 852 | 55 | 377 | 2.632 | 0 |
| `POST /angebote/{id}/position/{pid}/menge` | 710 | 11 | 329 | 3.324 | 0 |
| `GET /lead-management/lead/{id}` | 305 | 43 | 380 | 3.224 | 0 |
| `GET /projektierung/projekt/{id}` | 173 | 63 | 408 | 1.715 | 0 |
| `GET /lead-management/hauptboard` | 158 | 92 | 1.338 | 2.136 | 0 |
| `GET /lead-management/lead/{id}/termin/vorschlaege.json` | 153 | 2.869 | 4.473 | 9.864 | 0 |
| `POST /lead-management/anruf/{id}` | 151 | 11 | 764 | 4.573 | 0 |
| `GET /lead-management/terminiert` | 150 | 436 | 815 | 4.818 | 0 |
| `GET /leads` | 126 | 26 | 455 | 972 | 0 |
| `GET /leads/{id}/erfassen` | 126 | 16 | 156 | 338 | 0 |
| `GET /erfassung/sparten` | 126 | 18 | 118 | 328 | 0 |
| `POST /erfassung/sparten-start` | 125 | 16 | 838 | 2.876 | 0 |
| `GET /erfassung/{id}/weiche` | 125 | 15 | 68 | 330 | 0 |

**Fehlerprotokoll der Kopie**: 1 neue Tabelleneinträge · fehler.log: 1 Fehler-Nummern, „database is locked“ 5 (Anfragen 1), TimeoutError 0, QueuePool 0
- F-20261008-030301-bf10 · POST /erfassung/296/absenden · OperationalError

Zähler: formularfehler = 2, id_angebot_erzeugen_fallback:/erfassungen (Antworten unvollständig für die aktuelle Logik) = 11, id_angebot_erzeugt = 65, id_erfassung_vom_aussendienst = 66, szenario_bei_laufende_abgebrochen = 50, vorschlaege_status:hv_lead = 18, vorschlaege_status:ok = 135

Rohdaten: `C:\Users\a.scheelen\Tools\Angebotstool\diagnose\test_v27\lasttest_20261008-030038.json` · Serverkonsole: `C:\Users\a.scheelen\Tools\Angebotstool\diagnose\test_v27\server_20261008-030038.log`

_Hinweis Orchestrator (Lauf 2): wieder genau **1 × „database is locked“** (`POST /erfassung/296/absenden`, 03:03:01, 6,4 s gewartet), alle übrigen Zielwerte erfüllt. Beide Fehler liegen exakt 143 s nach dem Serverstart und fallen in dieselbe Anfrage `GET /lead-management/lead/62/termin/vorschlaege.json` (9–10 s): nach dem Routing-Matrix-Aufruf (2 s simulierte Latenz) schreibt `routing.matrix_fuellen` bis zu 2.500 Cache-Zeilen in der Anfrage-Sitzung und hielt die SQLite-Schreibsperre danach bis zum Ende der Anfrage (6–7 s unter Last, GIL-Kontention durch parallele PDFs); zwei andere Schreiber warteten (Schreibsperren-Messung 5,6 s bzw. 3,3 s), einer lief in die 5-s-Busy-Grenze. Latenter v27-Befund (dort nur teilweise Überlappung, max. 2,5 s). **Behoben:** `routing.matrix_fuellen` und `lead_termin.vorschlaege` geben die Verbindung unmittelbar nach den Cache-Schreibungen frei (`verbindung_freigeben`), die Schreibtransaktion dauert damit Millisekunden. Lauf 3 unten mit der Korrektur._

#### Lauf 3 (08.10.2026, nach der Korrektur)

<!-- lasttest.py 20261008-032606 -->
### Lauf 08.10.2026 03:26:14 – Profil normal, 50 Nutzer (35 aktiv), 20 min

- Lastmodell: 14 Außendienst mobil, 11 Innendienst, 6 Lead-Management, 3 Projektierung, 1 Montage; dazu 15 angemeldete Leser · Denkzeit 5–15 s · Seed 27 · Latenz je externem Aufruf 2 s · Port 8001
- Server: v29 · Commit 1e317e7 · Pool 20 (max 90) · Threads 64 · Scheduler 14 Läufe · DATA_ORDNER `C:\Users\a.scheelen\Tools\Angebotstool\diagnose\test_v28_final\lasttest_data`
- Benutzer je Rolle: Außendienst mobil = 4, 7, 9, 13, 15, 17; Innendienst = 14, 18; Lead-Management = 1, 2, 12, 16, 20; Projektierung = 1, 2, 12, 16, 20; Montage = 24
- Hinweis: keine aktive Person mit Hauptrolle „leadmanagement“ in der Kopie – Admins übernehmen die Rolle [ANNAHME]
- Hinweis: keine aktive Person mit Hauptrolle „projektierung“ in der Kopie – Admins übernehmen die Rolle [ANNAHME]
- Anfragen gesamt: 6610 (330.2/min) · 5xx 0 · Timeouts 0 · Verbindungsfehler 0 · Szenarien 630 · Tool-Fehler 0 · Laufzeit 20.0 min (08.10.2026 03:26:14 – 03:46:15)

**Antwortzeiten je Route (Client-Sicht, Millisekunden)**

| Route | Anzahl | p50 | p95 | p99 | max | 5xx | Timeout | Verb. |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| `GET /erfassung/{id}/seite/{nr}` | 949 | 21 | 111 | 331 | 778 | 0 | 0 | 0 |
| `POST /erfassung/{id}/seite/{nr}` | 939 | 26 | 178 | 361 | 610 | 0 | 0 | 0 |
| `GET /angebote/{id}` | 856 | 60 | 401 | 852 | 2.266 | 0 | 0 | 0 |
| `POST /angebote/{id}/position/{pid}/menge` | 713 | 20 | 123 | 405 | 1.250 | 0 | 0 | 0 |
| `GET /lead-management/lead/{id}` | 303 | 48 | 317 | 733 | 2.011 | 0 | 0 | 0 |
| `GET /projektierung/projekt/{id}` | 173 | 75 | 476 | 1.184 | 1.789 | 0 | 0 | 0 |
| `GET /lead-management/hauptboard` | 155 | 107 | 1.053 | 2.183 | 2.726 | 0 | 0 | 0 |
| `GET /lead-management/lead/{id}/termin/vorschlaege.json` | 152 | 3.140 | 4.913 | 6.322 | 7.887 | 0 | 0 | 0 |
| `POST /lead-management/anruf/{id}` | 150 | 19 | 142 | 349 | 378 | 0 | 0 | 0 |
| `GET /lead-management/terminiert` | 149 | 465 | 1.090 | 1.636 | 4.008 | 0 | 0 | 0 |
| `GET /erfassung/sparten` | 126 | 19 | 154 | 574 | 621 | 0 | 0 | 0 |
| `GET /erfassung/{id}/weiche` | 126 | 19 | 73 | 326 | 441 | 0 | 0 | 0 |
| `GET /leads` | 126 | 43 | 464 | 911 | 1.643 | 0 | 0 | 0 |
| `GET /leads/{id}/erfassen` | 126 | 32 | 253 | 771 | 892 | 0 | 0 | 0 |
| `POST /erfassung/sparten-start` | 126 | 35 | 233 | 392 | 448 | 0 | 0 | 0 |
| `GET /` | 116 | 85 | 926 | 1.459 | 1.509 | 0 | 0 | 0 |
| `GET /erfassung/{id}/pruefen` | 112 | 19 | 73 | 163 | 342 | 0 | 0 | 0 |
| `GET /erfassungen/{id}/protokoll.pdf` | 112 | 261 | 716 | 1.231 | 2.294 | 0 | 0 | 0 |
| `POST /erfassung/{id}/absenden` | 112 | 35 | 178 | 418 | 1.441 | 0 | 0 | 0 |
| `GET /projektierung` | 88 | 51 | 1.083 | 1.144 | 1.676 | 0 | 0 | 0 |
| `POST /projektierung/aufgabe/{id}/erledigt-umschalten` | 87 | 62 | 382 | 610 | 721 | 0 | 0 | 0 |
| `POST /vorgaenge/{id}/galerie/upload` | 86 | 215 | 576 | 695 | 1.015 | 0 | 0 | 0 |
| `GET /montage/einsatz/{id}` | 78 | 37 | 139 | 313 | 326 | 0 | 0 | 0 |
| `GET /erfassungen` | 77 | 95 | 594 | 660 | 698 | 0 | 0 | 0 |
| `GET /erfassungen/{id}` | 77 | 30 | 138 | 180 | 205 | 0 | 0 | 0 |
| `GET /erfassungen/{id}/angebot-erzeugen` | 77 | 47 | 230 | 349 | 423 | 0 | 0 | 0 |
| `GET /erfassung` | 76 | 41 | 264 | 334 | 374 | 0 | 0 | 0 |
| `GET /angebote/{id}/pdf` | 66 | 1.021 | 2.531 | 3.350 | 3.854 | 0 | 0 | 0 |
| `GET /vorgaenge/{id}` | 66 | 40 | 342 | 380 | 392 | 0 | 0 | 0 |
| `POST /angebote/{id}/email` | 66 | 13.110 | 15.812 | 16.931 | 17.949 | 0 | 0 | 0 |
| `POST /angebote/{id}/sperre-frei` | 66 | 21 | 222 | 245 | 249 | 0 | 0 | 0 |
| `GET /montage` | 40 | 36 | 312 | 912 | 912 | 0 | 0 | 0 |
| `POST /montage/einsatz/{id}/foto` | 39 | 50 | 156 | 232 | 232 | 0 | 0 | 0 |

**Zielwerte Phase 131 [ANNAHME]**

| Kriterium | Ziel | Ist | Ergebnis |
|---|---|---|---|
| p95 Listen und Akten | ≤ 1500 ms | 591 ms (n = 2380, p50 65 ms) | erfüllt |
| p95 Editor-Aktionen | ≤ 1000 ms | 143 ms (n = 779, p50 21 ms) | erfüllt |
| p95 Angebots-PDF | ≤ 4000 ms | 2531 ms (n = 66, p50 1021 ms) | erfüllt |
| p95 Protokoll-PDF | ≤ 3000 ms | 716 ms (n = 112, p50 261 ms) | erfüllt |
| p95 Terminvorschläge | ≤ 6000 ms | 4913 ms (n = 152, p50 3140 ms) | erfüllt |
| TimeoutError (Pool) / Client-Timeouts | 0 | Server 0 · Client 0 | erfüllt |
| „database is locked“ an der Oberfläche | 0 | 0 (fehler.log gesamt 0, davon Anfragen 0) | erfüllt |
| Pool-Spitze | ≤ 60 % von 90 | 17 (18.9 %) | erfüllt |
| Fehlerquote (5xx + Timeouts + Verbindungsfehler) | < 0.1 % | 0.000 % (0 von 6610) | erfüllt |

**Gruppen (p95 nach Kriterium)**

| Gruppe | Anzahl | p50 | p95 | p99 | max | 5xx |
|---|---:|---:|---:|---:|---:|---:|
| Listen und Akten | 2380 | 65 | 591 | 1.231 | 4.008 | 0 |
| Editor-Aktionen | 779 | 21 | 143 | 380 | 1.250 | 0 |
| Angebots-PDF | 66 | 1.021 | 2.531 | 3.350 | 3.854 | 0 |
| Protokoll-PDF | 112 | 261 | 716 | 1.231 | 2.294 | 0 |
| Terminvorschläge | 152 | 3.140 | 4.913 | 6.322 | 7.887 | 0 |
| übrige Schritte | 3121 | 27 | 296 | 13.143 | 17.949 | 0 |

**Betrieb (/health alle 10 s, 120 Proben)**: Pool-Spitze 5 von 90 (5.6 %) · WAL max 4.19 MB · Schreibsperre max 788 ms, locked 0 · RSS max 351.2 MB · CPU 505.3 s · /health p95 151 ms · Status: ok ×120

**Server-Sicht (zugriff.log der Kopie)**: 6615 Anfragen (330.5/min) · 5xx 0 · Pool-Spitze zu Anfragebeginn 17 · Anteil > 2 s 2.89 %

| Route (Server) | Anzahl | p50 | p95 | max | 5xx |
|---|---:|---:|---:|---:|---:|
| `GET /erfassung/{id}/seite/{nr}` | 949 | 18 | 98 | 606 | 0 |
| `POST /erfassung/{id}/seite/{nr}` | 939 | 14 | 139 | 606 | 0 |
| `GET /angebote/{id}` | 856 | 57 | 368 | 2.263 | 0 |
| `POST /angebote/{id}/position/{pid}/menge` | 713 | 11 | 65 | 1.196 | 0 |
| `GET /lead-management/lead/{id}` | 303 | 42 | 308 | 1.975 | 0 |
| `GET /projektierung/projekt/{id}` | 173 | 63 | 447 | 1.724 | 0 |
| `GET /lead-management/hauptboard` | 159 | 98 | 1.035 | 2.460 | 0 |
| `GET /lead-management/lead/{id}/termin/vorschlaege.json` | 152 | 3.127 | 4.912 | 7.885 | 0 |
| `POST /lead-management/anruf/{id}` | 150 | 11 | 117 | 311 | 0 |
| `GET /lead-management/terminiert` | 149 | 443 | 1.029 | 3.934 | 0 |
| `GET /leads` | 126 | 25 | 458 | 1.584 | 0 |
| `GET /leads/{id}/erfassen` | 126 | 14 | 147 | 783 | 0 |
| `GET /erfassung/sparten` | 126 | 17 | 136 | 615 | 0 |
| `POST /erfassung/sparten-start` | 126 | 18 | 130 | 287 | 0 |
| `GET /erfassung/{id}/weiche` | 126 | 17 | 70 | 378 | 0 |

**Fehlerprotokoll der Kopie**: 0 neue Tabelleneinträge · fehler.log: 0 Fehler-Nummern, „database is locked“ 0 (Anfragen 0), TimeoutError 0, QueuePool 0

Zähler: formularfehler = 2, id_angebot_erzeugen_fallback:/erfassungen (Antworten unvollständig für die aktuelle Logik) = 11, id_angebot_erzeugt = 66, id_erfassung_vom_aussendienst = 66, szenario_bei_laufende_abgebrochen = 50, vorschlaege_status:hv_lead = 18, vorschlaege_status:ok = 134

Rohdaten: `C:\Users\a.scheelen\Tools\Angebotstool\diagnose\test_v27\lasttest_20261008-032606.json` · Serverkonsole: `C:\Users\a.scheelen\Tools\Angebotstool\diagnose\test_v27\server_20261008-032606.log`

_Hinweis Orchestrator (Lauf 3): **alle Zielwerte erfüllt** – 0 × 5xx, 0 Timeouts, 0 „database is locked“, Schreibsperre max. 0,8 s (vorher 5,6 s / 3,3 s), Pool-Spitze 17 von 90, Fehlerquote 0,000 % (0 von 6.610). Die Korrektur in `routing.matrix_fuellen`/`lead_termin.vorschlaege` ist damit bestätigt; die Entscheidung „SQLite bestätigt“ (Abschnitt 4.5) bleibt._
