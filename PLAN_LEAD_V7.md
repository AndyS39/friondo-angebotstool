# Umsetzungsplan Lead-Management V7: Design v3 für das Lead-Modul (Vorlage „Friondo Tool Design“), Kartei-Review 16.10., Termine anpassbar, Route in Kilometern, Kanäle/Interessen, Deals-Board, Login

> **Prüfvermerk 16.10.2026 (Claude Code, Vorprüfung der Plan-Kette):** Nummern **v37 / Phasen 196–200** gegen die
> Zuordnungstabelle bestätigt (v34 = PLAN_V21, v35 = PLAN_LEAD_V6, v36 = PLAN_V22; Vorspann angepasst). Reihenfolge
> laut Andreas: nach PLAN_V22. **Zulieferungen bei der Übergabe nicht vorhanden:** `docs/design-v37/vorlage/Friondo
> Tool Design.html` und `docs/design-v37/review-kartei-2026-10-16.png` (Claudia) – Phase 197 arbeitet mit den im Plan
> genannten Startwerten der Tokens, die Sichtprüfung gegen den Screenshot entfällt bis zur Zulieferung;
> `ORS_API_KEY` steht nicht in der `.env` – das Routing wird gebaut und meldet ohne Key den Rückfall „geschätzt“.

Voraussetzung: kein anderer Plan in Umsetzung (strangübergreifend). Stand 16.10.2026 (Vorprüfung der Plan-Kette): v34 (PLAN_V21, Phasen 178 bis 182) und v35
(PLAN_LEAD_V6, Phasen 183 bis 187) sind gebaut und gepusht, v36 (PLAN_V22, Phasen 188 bis 195) steht
in der Kette davor. **Dieser Plan kommt nach v36** und setzt auf dessen committetem Stand auf
(Kanal-Stammdaten, HV-Gruppen, Inline-Bearbeitung und Sofortsuche aus v35; Lead-Board-Layout aus v33;
Graph als Anwendung aus v33). Vor der Übergabe fragt der Planungs-Chat erneut ab,
ob v33 bis v36 committet, gepusht und auf dem Server sind. CLAUDE.md und
`leadmanagement_logik_v1.xlsx` sind Live-Master im Projektordner
`C:\Users\a.scheelen\Tools\Angebotstool` (Git-Arbeitskopie). ALLE PHASEN
DIESES PLANS IN EINEM DURCHLAUF UMSETZEN (Reihenfolge einhalten: **Phase 196
zuerst**, jede Checkbox nach Umsetzung und Test abhaken, am Ende
Gesamtübersicht mit Testergebnissen und offenen Punkten, fachliche
Rückfragen gebündelt). **Ein gemeinsamer Commit am Ende**, migrate.py
idempotent, **nur additive Migrationen** (v36-Code muss auf der
v37-Datenbank weiterlaufen, Rückweg `rollback.bat --nur-code`). **Kein git
push vor Freigabe.**

CLAUDE-Abschnitt: **„Neu in v37“** (geprüft 16.10.2026: v34 = PLAN_V21, v35 = PLAN_LEAD_V6, v36 =
PLAN_V22 – v37 ist die nächste freie Nummer). Phasen **196 bis 200** (geprüft: 188–195 gehören zu
PLAN_V22, 196 ist die nächste freie Nummer). Die
v27-Regeln gelten (`def`-Routen, keine offene Datenbanksitzung während
Netz-I/O, Scheduler-Rahmen, Wächter-Test `tests/test_v27_sitzungen.py` grün,
Inventartabelle `docs/betrieb.md`), die v30-Regeln für Oberflächen (Tokens
Hell/Dunkel, Token-Wächter `tests/test_v30_design.py`, `tojson |
forceescape` in on*-Attributen, Zurück-Leiste aus `base.html`).

Geltungsbereich: Modul Lead-Management (alle Seiten unter
`/lead-management`, `app/lead_*.py`, `app/routers/lm_*.py`,
`templates/lead_management/`, `app/static/lead_v2.css`, `lm_*.js`), der
Terminassistent und das Routing (`app/lead_termin.py`, Routing-Anbieter),
die Login-Seite (nur Vorbelegung des Benutzernamens) und die
Vertriebskanal-Stammdaten (nur Deaktivierung zweier Kanäle). Angebotstool,
Projektierung, monday-Sync und monday-Rückspielung bleiben unberührt; das
Design v2 (v30) der übrigen Module bleibt bestehen.

## Entscheidungen (Chat Lead-Management, 16.10.2026, Claudia Castro)

- **Design v3 nur für das Lead-Modul**, Hell und Dunkel: Vorlage ist die
  Datei `Friondo Tool Design.html` (claude.ai-Export „Außendienst App“ mit
  vier Boards: Dashboard Desktop · Lead Detail Übersicht · Lead Detail
  Termine · Lead Detail Anrufe). **Nur das Layout übernehmen** (Schrift,
  Schriftgrößen, Farben, Rundungen, Kacheln, Abstände), **keine Inhalte**;
  die Datei ist Inspiration, kein Nachbau. Die Werte werden als Tokens für
  den Hellmodus hinterlegt, der Dunkelmodus wird passend abgeleitet;
  Angebotstool und Projektierung bleiben beim Design v2.
- **Kartei-Review (Screenshot 16.10.)**: Der Notizblock wird **breiter**
  (volle Breite der linken Spalte, Eingabefeld mehrzeilig über die ganze
  Breite), die Buttons „Senden“ und „Diktieren“ stehen **rechts daneben**
  (nicht darunter). **Gestrichen:** Badge „monday“ neben dem Namen und der
  SLA-Chip in der Kopfzeile (die Information bleibt in der Timeline bzw. im
  Eingangstext). Die Punkte „An TAIFUN übergeben“, „TAIFUN-Kundennummer“ und
  „Fotos zum Objekt“ sind in PLAN_LEAD_V6 entfernt worden (Nachtrag dort).
- **Objekte bei Großkunden ein- und ausklappbar** (Objektliste zugeklappt,
  wenn der Kunde als Großkunde gekennzeichnet ist oder mehr als drei Objekte
  hat; Zustand je Nutzer gemerkt).
- **Routenplaner-Kachel vom Dashboard entfernen** (v29 „Routenplaner“ mit
  Google-Maps-Link).
- **Bereits terminierte Vor-Ort-Termine** (auch aus monday gesyncte) sind in
  der Kartei **sichtbar und anpassbar** (Datum, Uhrzeit, Vertriebler,
  Objekt, Bemerkung). **Offen, ob Termine manuell vergeben werden sollen
  [OFFEN 1]**: Bis zur Entscheidung bleibt die manuelle Neuanlage eines
  Vor-Ort-Termins in der Testphase gesperrt (v31 Phase 159), die Anpassung
  bestehender Termine ist frei.
- **Route als konkrete Strecke in Kilometern** (Straßenkilometer und
  Fahrzeit über den Routing-Dienst) statt Luftlinie, in Terminvorschlägen,
  Kalenderansicht, Ersatzkunde-Dialog und Karte.
- **Login: Benutzername vorbelegen** (zuletzt verwendeter Benutzername je
  Browser gemerkt, nur die PIN ist einzugeben).
- **Kanäle „WeLoveX“ und „DAA“ deaktivieren** (wie EON & Co. in v35: nicht
  mehr wählbar, Leads behalten das Label, Filter-Chips im Hauptboard und in
  Deals verschwinden).
- **Interesse „PV vorhanden“** als neues Häkchen (Code `PVV`), Langname
  „PV vorhanden“; kein Sparten-Code für Erfassungen, sondern ein Merkmal des
  Kunden (bestehende PV-Anlage) [ANNAHME: Merkmal, keine Erfassungs-Sparte].
- **Inline-Bearbeitung Interessen im Hauptboard:** ein **Plus** statt des
  Stifts öffnet die Auswahl; bereits gewählte Interessen lassen sich per
  Klick wieder abwählen.
- **Deals-Board:** Button „Bestätigung erneut“ je Zeile, die Spalte
  „Erfassung/Angebot“ und der Button „Erfassung starten“ **entfallen**
  (Erfassung wird weiterhin aus der Kartei, aus Leads VOT und aus „Mein
  Tag“ gestartet).

## Phase 196: Kartei-Review zuerst (Streichungen und Notizblock)

- [x] **Kundenkartei, Kopf:** Badge „monday“ neben dem Namen entfernen (die
      Quelle bleibt als Text in der Eingangszeile „Eingang (Sync)“ und in
      der Timeline); SLA-Chip in der Kopfzeile entfernen (SLA bleibt in der
      Anrufliste und Statistik). Die restliche Kopfzeile (Phasenkette,
      Versuchs-Punkte, Eingangstext, Pflichtfeld-Zähler, Schnellaktionen,
      Button „Terminierung“, „Nachbearbeitung“, „Vorgangsakte“) bleibt.
- [x] **Notizblock:** Block „Notizen (Vorgang: Lead bis Montage)“ nimmt die
      volle Breite seiner Spalte ein; das Eingabefeld ist mehrzeilig über
      die ganze Breite (mindestens 3 Zeilen, wächst mit), rechts daneben
      in einer Spalte die Buttons **„Senden“** und **„Diktieren“**
      untereinander; der Hinweistext „Diktat: bitte das Mikrofon Ihrer
      Handy-Tastatur verwenden“ steht klein unter dem Diktieren-Button.
      To-Dos-Block rechts bleibt schmal (v31). Unter 900 px: Eingabefeld,
      darunter Buttons nebeneinander.
- [x] Sichtprüfung gegen den Screenshot vom 16.10.2026
      (`docs/design-v37/review-kartei-2026-10-16.png`, von Claudia
      abzulegen): nichts Durchgestrichenes mehr sichtbar, Notizblock breit.

## Phase 197: Design v3 für das Lead-Modul

- [x] **Vorlage ablegen und entpacken:** `Friondo Tool Design.html` nach
      `docs/design-v37/vorlage/` (Claudia). Die Datei ist ein gepackter
      claude.ai-Export: vier Seiten liegen als gzip-komprimierte Base64-
      Einträge im `<script type="__bundler/manifest">` (Schlüssel = Board-
      UUID, Felder `mime`, `compressed`, `data`); Claude Code entpackt sie
      mit Python (`base64` + `gzip`) nach `docs/design-v37/vorlage/boards/`
      (dashboard.html, lead-uebersicht.html, lead-termine.html,
      lead-anrufe.html) und legt Screenshots der vier Boards bei 1600 px
      daneben. Nur Layout und Stil werden übernommen, **keine Inhalte**
      (keine Demo-Namen, keine „Quelle: monday“-Chips, keine Kennzahlen aus
      der Vorlage).
- [x] **Tokens Design v3 (Lead-Modul, Hellmodus)**, abgeleitet aus der
      Vorlage und in `lead_v2.css` als eigener Block `:root .lm-v3` bzw.
      `[data-modul="lead"]` angelegt (Werte als Startwerte, bei
      Abweichungen in der Vorlage gewinnt die Vorlage):
      - Schrift: „Inter“ (Fallback „Open Sans“, system-ui, sans-serif),
        lokal eingebunden (keine externen Webfonts, v14-Regel; Dateien
        unter `app/static/fonts/`); Grundgröße 14 px, Nebentext 12 bis
        13 px, Kleintext 11 px, Überschriften 16/18/22 px, Kennzahlen 26 bis
        38 px; Gewichte 400/500/600/700, Kennzahlen 800.
      - Farben: Primärblau `#2F72B5` (hover `#245C95`, hell `#4489C9`,
        Hintergrund-Blau `#E3EDF7`, Akzentlinie `#8DB4DE`); Text
        `#0E2338`, Zweittext `#33414F`, gedämpft `#687186`; Flächen Seite
        `#F6F8FA`, Karten `#FFFFFF`, Felder `#ECF0F5`/`#EEF1F5`, Rahmen
        `#DCE4EB`; Hinweis/Warnung Orange `#FFA500` mit Text `#A85400` und
        Fläche `#FFF1D6`; Status-/Kanalfarben bleiben aus den Stammdaten (v35).
      - Rundungen: Chips/Pills 999 px, Buttons und Felder 8 px, Karten
        12 bis 14 px, große Kacheln 18 bis 22 px, Avatare 50 %.
      - Schatten: Karten `0 1px 4px rgba(0,0,0,.08)`; Abstände 8/12/16/24/
        32 px; Kachelraster des Dashboards 3 Spalten ab 1200 px.
      - Dunkelmodus: dieselben Rollen mit abgeleiteten Werten (Seite
        `#0F1A26`, Karten `#16243A`, Rahmen `#2A3B52`, Text `#E8EEF5`,
        gedämpft `#9AA8BA`, Blau unverändert, Orange-Fläche abgedunkelt)
        [ANNAHME]; Umschalter und Speicherung je Benutzer aus v30 bleiben,
        Token-Wächter `tests/test_v30_design.py` wird um die v3-Tokens
        erweitert (keine festen Farben in Lead-Templates).
- [x] **Anwendung auf alle Lead-Seiten:** Mein Dashboard (Kacheln wie
      Vorlage „Dashboard Desktop“: große Kennzahl oben links, Beschriftung
      darunter, Kachelkarten mit 18 px Rundung), Hauptboard/Deals/Infoabend/
      Handelsvertreter/Kontaktiert (Filterleiste als Karte, Tabellenzeilen
      40 px, Chips als Pills), Kundenkartei (Aufteilung wie Vorlage „Lead
      Detail“: Kopfkarte mit Avatar, Phasen-Pills, Aktions-Icons rund;
      Reiter Anruf/E-Mail/Timeline als Pill-Leiste; Termine-Block mit
      Vorschlagskarten und „IDEAL“-Pill in Orange; Anruf-Block mit großen
      Ergebnis-Buttons), Terminassistent, Kalender, Karte, To-Dos,
      Vorlagen-Editor, Lead-Einstellungen. Aufbau und Inhalte der Seiten
      bleiben wie heute (v31 bis v35), nur Optik. Das Lead-Board-Layout des
      Angebotstools (v33 Phase 174) behält die v2-Tokens.
- [x] Screenshots vorher/nachher je Seite hell und dunkel nach
      `docs/design-v37/`; `docs/design-system.md` Abschnitt „Design v3
      (Lead-Modul)“ mit Token-Tabelle und Regel „neue Lead-Seiten nur mit
      v3-Tokens“.

## Phase 198: Termine anpassbar, Route in Kilometern, Objekte einklappbar, Dashboard

- [x] **Terminierte Vor-Ort-Termine anpassbar:** im Block „Termine“ der
      Kartei jeder bestehende Termin (Status geplant, bestätigt, vorgemerkt;
      auch Termine aus dem monday-Sync `quelle = monday`) mit Button
      **„Anpassen“**: Datum, Uhrzeit (15-Minuten-Raster), Vertriebler
      (Dropdown nach v31-Regeln), Objekt, Bemerkung; Konfliktprüfung
      (`termin_konflikt_modus`), Aktivität „Termin angepasst: alt → neu“,
      Outlook- und Kundenmail-Folgen nur, wenn `terminierung_aktiv` bzw.
      `mail_versand_aktiv` an sind (sonst Hinweis „Testphase: nur im Tool
      geändert“). monday-Termine: Änderung gilt im Tool; monday wird
      **nicht** zurückgeschrieben (Hinweis am Termin „ursprünglich aus
      monday: <Datum>“) [ANNAHME: keine Rückspielung des Termins]. Die
      **manuelle Neuanlage** eines Vor-Ort-Termins bleibt in der Testphase
      gesperrt [OFFEN 1].
- [x] **Route in Kilometern:** Routing-Dienst scharf schalten: Parameter
      `routing_anbieter` auf `ors` (openrouteservice) mit API-Key aus der
      `.env` (`ORS_API_KEY`, nie im Code oder Projektwissen; Google als
      Umschalter bleibt), Cache 90 Tage (v12). Überall, wo bisher Luftlinie
      stand (Terminvorschläge, Kalenderansicht, Ersatzkunde-Dialog, Karte,
      Mein Tag), werden **Straßenkilometer und Fahrzeit** angezeigt („18,4
      km · 24 Min“); nur bei Ausfall des Dienstes Luftlinie × 1,3 mit
      Kennzeichnung „geschätzt“ (v12-Regel). Verbrauchszähler je Tag in den
      Lead-Einstellungen, Hinweis bei 80 % des Tageskontingents. Prüfpunkt
      „Routing-Dienst antwortet“ in der Parametrierung.
- [x] **Objekte ein- und ausklappbar:** Objektliste in der Kartei als
      Akkordeon; Standard zugeklappt bei Großkunde oder mehr als drei
      Objekten, sonst aufgeklappt; Kopfzeile zeigt Anzahl Objekte, Anzahl
      mit Termin, Anzahl mit Angebot; Zustand je Nutzer gemerkt
      (`benutzer_einstellungen` Key `objekte_zu`). Ein-Objekt-Vorgänge ohne
      Akkordeon.
- [x] **Dashboard:** Kachel „Routenplaner“ entfernen (Parameter
      `routen_start` bleibt für „Mein Tag“ und Kalender); Kachelreihenfolge
      je Nutzer (v31) bereinigt den Eintrag.
- [x] **Login:** zuletzt verwendeter Benutzername wird je Browser gemerkt
      (Cookie 90 Tage, nur Benutzername, nie die PIN) und beim Aufruf der
      Login-Seite vorbelegt; Fokus steht in der PIN; Link „Anderer
      Benutzer“ leert das Feld. Gilt für alle Rollen; die v34-Funktion „Angemeldet bleiben“ (falls bereits gebaut) bleibt unabhängig davon.

## Phase 199: Kanäle, Interessen, Deals-Board

- [x] **Kanäle WeLoveX und DAA deaktivieren:** `vertriebskanaele.aktiv = 0`
      (Migration), Leads behalten das Label, nicht mehr wählbar, Filter-
      Chips in Hauptboard und Deals entfallen (inaktive Kanäle nur unter
      „weitere“); HV-Ausschlussliste und Kanal-AD-Regel prüfen, ob die
      beiden dort vorkamen (Hinweis in der Gesamtübersicht).
- [x] **Interesse „PV vorhanden“:** neues Häkchen in der Interessenliste
      (Code `PVV`, Langname „PV vorhanden“, Badge-Farbe aus der Sparten-
      Mechanik) in Kartei, Inline-Edit, Schnellanlage, Import, API
      (`sparten` akzeptiert „PV vorhanden“/`PVV`), Filter, Boards; **kein**
      Erfassungsstart und keine Kompetenz-Prüfung für `PVV` (Merkmal, keine
      Sparte); in Mails über {sparten} nicht als Interesse genannt, sondern
      als Zusatz „Sie haben bereits eine PV-Anlage“ nur in Vorlagen, die
      den Platzhalter {pv_vorhanden} nutzen [ANNAHME]. Vorbelegung der
      WP-/KL-Erfassung: Frage nach bestehender PV-Anlage (falls im Bogen
      vorhanden) mit Ja vorbelegt.
- [x] **Inline-Interessen mit Plus:** im Hauptboard (und Deals, Infoabend,
      HV-Ansicht) zeigt die Spalte Interessen die gewählten Badges plus ein
      **Plus-Symbol**; Klick öffnet das Popover mit allen Interessen
      (WP, PV, KL, WB, GW, MS, WA, DMS, PV vorhanden); bereits gewählte sind
      markiert und werden per Klick abgewählt; Speichern per fetch beim
      Schließen (v35-Mechanik), Aktivität bei Änderung. Kein Stift-Symbol
      mehr in dieser Spalte.
- [x] **Deals-Board:** Button „Bestätigung erneut“ je Zeile entfernen
      („Terminbestätigung erneut senden“ bleibt in der Kartei und in der
      Übergabeliste); Spalte „Erfassung/Angebot“ aus dem Spaltenkatalog des
      Deals-Boards entfernen (Status-Chips je Sparte bleiben in der Kartei
      und in Leads VOT); Button „Erfassung starten“ in der Gruppe
      Angebotserstellung entfernen (Start aus Kartei, Leads VOT, Mein Tag).
      Gespeicherte Spaltenkonfigurationen (v25) verlieren die Spalte ohne
      Fehler.

## Phase 200: Tests, Doku, Übergabe

- [x] Tests `tests/test_lead_v7.py`: (a) Kartei ohne monday-Badge und ohne
      *(Stand 16.10.2026: Tests je Agent `tests/test_lead_v7_design.py`, `test_lead_v7_termine_routing.py`, `test_lead_v7_kanaele_interessen.py` statt einer Datei; v37-Tests, Wächter und Lead-Nachbarn auf der migrierten Kopie grün. Kettenende 17.10.2026: Gesamtsuite 1859 bestanden / 7 übersprungen / 4 Mitternachts- bzw. Umgebungs-Fehler ohne Codefehler, Wiederholung 4/4 grün, `test_v27_sitzungen.py` und `test_v30_design.py` grün – `diagnose/v36/gesamtuebersicht.md` §10.)*
      SLA-Chip, Notizblock-Markup mit Buttons rechts; (b) Token-Wächter: keine
      festen Farben in Lead-Templates, v3-Tokens vorhanden, Dunkelmodus-
      Werte definiert; (c) Termin anpassen (Datum/AD) mit Aktivität,
      monday-Termin mit Ursprungs-Hinweis, keine Outlook-/Mail-Folge in der
      Testphase; manuelle Neuanlage weiter gesperrt; (d) Routing: Vorschlag
      zeigt km und Minuten vom Dienst, bei Ausfall „geschätzt“; (e) Objekte-
      Akkordeon zu bei Großkunde/4 Objekten, Zustand je Nutzer; (f) Dashboard
      ohne Routenplaner; (g) Login-Vorbelegung über Cookie, „Anderer
      Benutzer“ leert; (h) WeLoveX/DAA inaktiv, Alt-Lead behält Label, Chips
      weg; (i) Interesse PVV in Kartei/API/Filter, kein Erfassungsstart;
      (j) Inline-Interessen: Plus, abwählen, Aktivität; (k) Deals ohne
      Button Bestätigung erneut, ohne Spalte Erfassung/Angebot, ohne
      Erfassung starten. Bestehende Lead-Tests anpassen (Badge, Spalten,
      Buttons), jede Anpassung begründen. Gesamtlauf grün,
      `tests/test_v27_sitzungen.py` und `tests/test_v30_design.py` grün.
- [x] Rollout-Vorbereitung nach Grundregel: Server-DB-Kopie nach
      *(EINE Rollout-Vorbereitung am Kettenende v36–v38, erledigt 16./17.10.2026 – `diagnose/v36/gesamtuebersicht.md` §10: migrate ×2 (2. Lauf ohne Änderung), Rückweg v33-/v37-Code je 24/24, Abnahme 93/93, Voll-Crawl 16 Läufe 0 Abstürze, Smoke 8/8, Lasttest schreibsturm 190/190, normal 0 × 5xx / 0 locked – p95 Listen/Akten 2,3 s, Terminvorschläge 11,7 s und Angebots-PDF 4,2 s über den Zielwerten (Rückfragen 7 und 18 R7). Screenshots gegen die fehlende Design-Vorlage entfallen.)*
      diagnose\, migrate.py zweimal (additiv: Kanäle inaktiv, Interesse
      PVV, `objekte_zu`, Parameter), Rückweg-Probe v36-Code auf v37-DB,
      Voll-Crawl aller Rollen hell und dunkel, Abnahmeskript, Smoke,
      Screenshots nach `docs/design-v37/`, nur Demo-Daten; `docs/betrieb.md`
      Inventar: Routing-Dienst (Kontingent, Key in `.env`).
- [x] CLAUDE.md: Abschnitt „Neu in v37 – Lead-Management V7 Design v3,
      Kartei-Review, Termine, Routing (abgestimmt 16.10.2026)“ (Plan:
      PLAN_LEAD_V7.md, Phasen 196 bis 200; Nummern laut Vorspann prüfen),
      Zuordnungstabelle `| v37 | PLAN_LEAD_V7.md | 196–200 |`, Titelzeile
      „(v37)“, in „Neu in v12“ (Luftlinie-Fallback als Standard), „v29“
      (Routenplaner-Kachel), „v35“ (Interessenliste, Kanalliste), „v30“
      (Design v2 gilt nicht mehr im Lead-Modul) die Sätze als *überholt –
      siehe v37* markieren; `docs/design-system.md` Abschnitt Design v3;
      `docs/nach-dem-update-v37.md` (Team: neue Optik, Termine anpassen,
      Plus bei Interessen, Login-Vorbelegung; Admin: ORS-Key in `.env`,
      Routing-Prüfpunkt, Kanäle prüfen); `docs/updates.md`;
      `config.VERSION = "v37"`.
- [x] Gesamtübersicht am Ende: erledigte Phasen, Testergebnisse,
      angepasste Alt-Tests mit Begründung, Token-Tabelle v3, Liste aller
      [ANNAHME]-Stellen, gebündelte Rückfragen. **Ein Commit** „v37:
      Lead-Management V7 Design v3, Kartei-Review, Termine, Routing
      (PLAN_LEAD_V7, Phasen 196-200)“; **kein push vor Freigabe**.

## Kontrollwerte für die Abnahme

- Kartei Lauter, Thorsten: kein „monday“-Badge, kein SLA-Chip; Notizfeld
  über die volle Spaltenbreite, „Senden“ und „Diktieren“ rechts daneben.
- Hellmodus: Seite `#F6F8FA`, Karte weiß mit 12 px Rundung, Primärbutton
  `#2F72B5`, Schrift Inter 14 px; Dunkelmodus ohne Aufblitzen, keine feste
  Farbe im Lead-Template (Wächter grün).
- Termin aus monday am 22.10. 10:00 → „Anpassen“ auf 23.10. 14:00 und
  Vertriebler Horst: Aktivität „Termin angepasst“, Hinweis „ursprünglich
  aus monday: 22.10.2026 10:00“, keine Mail, kein Outlook (Testphase).
- Terminvorschlag Duisburg → Bochum zeigt „ca. 28 km · 31 Min“ vom
  Routing-Dienst, nicht „Luftlinie“.
- Großkunde mit 5 Objekten: Objektliste zugeklappt, Kopf „5 Objekte · 2 mit
  Termin“; Aufklappen bleibt nach Neuladen.
- Login-Seite nach Abmeldung: Benutzername vorbelegt, Fokus in der PIN.
- Hauptboard: Filter-Chips WeLoveX/DAA fehlen; Alt-Lead mit DAA zeigt das
  Label; Interessen-Spalte mit Plus, PV abwählbar, „PV vorhanden“ wählbar.
- Deals-Board: keine Spalte Erfassung/Angebot, kein „Bestätigung erneut“,
  kein „Erfassung starten“.

## Zulieferungen / bewusst offen

- **Claudia:** `Friondo Tool Design.html` nach `docs/design-v37/vorlage/`
  und den Screenshot vom 16.10. als
  `docs/design-v37/review-kartei-2026-10-16.png` ablegen.
- **IT/Andreas:** API-Key für openrouteservice (kostenloser Plan, Konto auf
  account.heigit.org) in die `.env` auf Dev-PC und Server (`ORS_API_KEY`);
  Kontingent laut v12-Konzept prüfen.
- **[OFFEN 1]** Sollen Vor-Ort-Termine manuell vergeben werden (ohne
  Assistent)? Bis zur Entscheidung bleibt die Neuanlage in der Testphase
  gesperrt, die Anpassung bestehender Termine ist frei.
- Bestätigung der [ANNAHME]-Stellen: Dunkelmodus-Werte; „PV vorhanden“ als
  Merkmal ohne Erfassung und mit eigenem Platzhalter; keine Rückspielung
  angepasster Termine nach monday; Versionsnummer v37 und Phasen 196 bis
  200.
