# Umsetzungsplan Lead-Management V3: Feedback-Runde nach V2 (Bedienung, Kundenkartei, Navigation)

Voraussetzung: kein anderer Plan in Umsetzung. v23 (PLAN_LEAD_V2, Phasen
104 bis 112) und v24 (PLAN_V16 Klimakonfigurator, Phasen 113 bis 117) sind
committet und gepusht; **der Server-Pull von v24 findet am Abend des
05.10.2026 statt. Dieser Plan wird erst danach an Claude Code übergeben**
(Prüfpunkt im Vorspann der Übergabe). CLAUDE.md und
`leadmanagement_logik_v1.xlsx` sind Live-Master im Projektordner
`C:\Users\a.scheelen\Tools\Angebotstool` (Git-Arbeitskopie). ALLE PHASEN
DIESES PLANS IN EINEM DURCHLAUF UMSETZEN (Reihenfolge einhalten, jede
Checkbox nach Umsetzung und Test abhaken, am Ende Gesamtübersicht mit
Testergebnissen und offenen Punkten, fachliche Rückfragen gebündelt).
migrate.py idempotent. **Kein git push vor Freigabe.**

CLAUDE-Abschnitt: **„Neu in v25“** (höchste + 1; v24 = Klimakonfigurator).
Phasen **118 bis 121** (frei laut Zuordnungstabelle; 113 bis 117 gehören zu
PLAN_V16).

Geltungsbereich: ausschließlich das Modul Lead-Management (Router
`app/routers/lm_*.py`, `app/lead_*.py`, `app/static/lead_v2.css`,
Templates unter `templates/lead_management/`). Angebotstool, Projektierung,
monday-Sync und monday-Rückspielung bleiben unberührt. Alles weiter im
Demo-Modus `lead_freigabe_modus = admin`; die Freischaltung ist nicht Teil
dieses Plans. Bestehende Tests (`tests/test_lead_v2_*.py`, Gesamtlauf 416
grün nach v23) müssen nach Umbau weiter grün sein oder bewusst angepasst
werden (Begründung je angepasstem Test in der Gesamtübersicht).

Dieser Plan wurde gegen CLAUDE.md v23 geschrieben, ohne Blick in den
v24-Code. Vor dem Bau prüfen, ob v24 Dateien des Lead-Moduls berührt hat
(Sparten-Badges KL, `kompetenz_sparten`); falls ja, auf dem v24-Stand
aufsetzen.

## Entscheidungen (Chat Lead-Management, 05.10.2026, Claudia Castro)

- **Score und Qualifizierung werden komplett abgeschaltet**: kein Score,
  keine Score-Klasse A/B/C, kein Qualifizierungsbogen mehr in Kundenkartei,
  Anrufliste, Boards, Kanban, Dashboard, Statistik. Die Anrufliste
  priorisiert nur noch nach SLA, Fälligkeit und Eingangsdatum. Daten
  (`score`, `score_klasse`, `lead_qualifizierung`) bleiben in der Datenbank,
  die Steuerdatei-Blätter Qualifizierung, Scoring und Klassen bleiben
  unverändert liegen (kein Import-Fehler, nur unbenutzt). Die Vorbelegung
  des Erfassungsbogens aus der Qualifizierung (`erfassungs_frage`) entfällt
  damit; die Vorbelegung aus der Objektart (v23) bleibt.
- **„Nicht erreicht“ ohne Pop-up**: ein Klick protokolliert den Versuch mit
  aktuellem Datum und Uhrzeit, **keine automatische Wiedervorlage**. Die
  Kaskade setzt keine Wiedervorlage mehr; die automatischen Kaskaden-Mails
  (`nicht_erreicht` ab dem 2. Versuch, `disqualifiziert` nach dem letzten)
  bleiben an die Versuchsnummer gekoppelt. Wiedervorlagen setzt der Nutzer
  über den Wiedervorlage-Button.
- **Status-Label „Qualifiziert“ entfällt**: die Phasen `in_kontaktierung`
  und `qualifiziert` zeigen beide das Label **„Kontaktiert“**; intern bleiben
  beide Phasen bestehen (Terminassistent, Boards, Trichter unverändert).
- **Handelsvertreter sind im Terminassistenten keine Kandidaten**, wenn
  der Innendienst terminiert. Terminiert ein Handelsvertreter einen eigenen
  Lead, rechnet der Assistent weiterhin nur ihn selbst (v23, Phase 108).
- **Autospeichern** in der Kundenkartei: jedes Feld speichert beim
  Verlassen des Feldes (blur) bzw. bei Auswahl, kein Speichern-Button.
- **Navigation** des Moduls (linke Icon-Leiste) in dieser Reihenfolge:
  Mein Dashboard · Hauptboard · Deals · Kontaktiert · Karte · Infoabend ·
  To-Dos · Handelsvertreter · Mehr … (alles Übrige). „Deals“ ersetzt die
  Bezeichnung „Terminiert“ überall in der Oberfläche; „Infoabend“ ersetzt
  „Info-Veranstaltung“ in Menü und Seitentiteln (Parameter-Keys `info_*`
  und Tabellennamen bleiben).
- **Kundenkartei** neu aufgeteilt: Statuskette (Phasen) oben, Button
  „Terminierung“ oben rechts, Kundeninformationen als horizontaler Block
  darunter (nicht mehr als linke Spalte), darunter die Reiter in der
  Reihenfolge Termin · Anrufnotizen · E-Mail-Verlauf · Timeline, darunter die
  Blöcke Termine · Angebote · Erfassungen · Projekt · Anhänge · To-Dos. Im
  Block „Termine“ werden die Terminvorschläge des Assistenten direkt
  angezeigt. Aus der Kartei entfernt: Score, Qualifizierung, Einwilligung
  Werbung, Quelle.
- **Spalten der Boards** (Hauptboard, Deals, Infoabend, Handelsvertreter)
  je Nutzer: umbenennen, sortieren, ausblenden, per Drag & Drop am
  Spaltenkopf verschieben; Änderungen gelten nur für den jeweiligen Nutzer
  (`benutzer_einstellungen`, Key `boards_spalten`), nie für alle.
  Filterleiste bleibt beim horizontalen und vertikalen Scrollen oben
  fixiert. Spalten Anrede, Vorname, Nachname sind in den Boards
  standardmäßig ausgeblendet (Spalte „Kundenname“ zeigt den vollen Namen);
  in der Kundenkartei bleiben die drei Felder sichtbar [ANNAHME].
- **Anrufliste**: nur noch eine durchgehend sortierte Liste ohne die
  Gruppen „Jetzt dran · Weiter versuchen · Neu heute · Wiedervorlagen fällig
  · Sonstige“ [ANNAHME: „nur eine Liste“ meint die Gruppen]; die
  Filter-Chips „Quelle“ und „Einzelquelle“ werden durch einen Filter
  **„Vertriebskanal“** ersetzt (Werte = bestehende Vertriebskanäle mit
  `kanal_farben`).
- „Einwilligung Werbung“ und „Quelle“ verschwinden nur aus der
  Kundenkartei; die Felder bleiben im Datenmodell, im Eingang (API,
  Parser, Import) und in Kanal-Report/Statistik erhalten. Die Nurture-Mail
  bleibt wie bisher an die Einwilligung gebunden [ANNAHME].

## Phase 118: Navigation, Boards, Anrufliste

- [x] `lm_nav` (linke Icon-Leiste) auf die neue Reihenfolge umstellen:
      **Mein Dashboard** (`/lead-management/dashboard`) · **Hauptboard**
      (`/lead-management/boards/haupt`) · **Deals** (bisher Terminiert,
      Pfad bleibt, Titel und Breadcrumb „Deals“) · **Kontaktiert** ·
      **Karte** (`/lead-management/karte`) · **Infoabend** (bisher
      Info-Veranstaltung) · **To-Dos** (neue Seite
      `/lead-management/todos`: eigene offene und erledigte To-Dos,
      zugewiesene To-Dos an andere, Filter fällig/alle, Anlegen inline;
      Logik aus `lead_todos.py` wiederverwenden) · **Handelsvertreter** ·
      **Mehr …** (Aufklappmenü mit allen übrigen Einstiegen: Anrufliste,
      Kanban, Kalender, E-Mail-Vorlagen, Übersicht/Statistik Leads,
      Kanal-Report, Posteingang unklar, Import, Schnellanlage,
      Lead-Einstellungen). Lokale SVG-Icons aus `_symbole.html`, Tooltip =
      Bezeichnung, aktiver Eintrag markiert, unter 900 px untere Icon-Zeile
      wie in v23. Kein V1-Einstieg darf verloren gehen (Crawl prüft alle
      Pfade).
- [x] Bezeichnung „Terminiert“ → „Deals“ in allen Templates des Moduls
      (Board-Titel, Menü, Kacheln, Sammelaktions-Dialog, Kanban-Überschrift,
      Mail-Betreffe sind nicht betroffen). Bezeichnung „Info-Veranstaltung“
      → „Infoabend“ in Menü, Seitentiteln, Kacheln, Gruppenüberschriften
      („Infoabend 05.11.2026“). Blatt Status der Steuerdatei: Spalte
      `board_label` ergänzen oder bestehende Labels anpassen, damit die
      Board-Namen aus der Logik kommen (Arbeitsanweisung an der Live-Excel,
      Import in der Parametrierung prüfen).
- [x] Spaltenkonfiguration je Nutzer erweitern (`boards_spalten` je Board):
      **Umbenennen** (Klick auf Stift im Spaltenkopf, eigener Anzeigename,
      leer = Standard), **Sortieren** (Klick auf Spaltenkopf auf-/absteigend,
      Sortierung wird gemerkt), **Ausblenden/Einblenden** (Spaltenwähler
      „Spalten“ in der Filterleiste mit Häkchen), **Verschieben** per Drag &
      Drop am Spaltenkopf (HTML5 Drag, Platzhalter beim Ziehen, Speichern
      per fetch nach dem Loslassen). Button „Zurücksetzen“ stellt den
      Standard wieder her. Alles nur für den angemeldeten Nutzer; ein
      zweiter Nutzer sieht die Standardkonfiguration unverändert (Test mit
      zwei Benutzern).
- [x] Standard-Spaltensatz der Boards: Anrede, Vorname, Nachname
      **ausgeblendet** (einblendbar); Spalte „Kundenname“ = „Anrede Vorname
      Nachname“ (Anrede nur wenn gesetzt). Migration: vorhandene
      `boards_spalten`-Einträge, die die drei Spalten sichtbar haben,
      bleiben unverändert (Nutzerwunsch), neue Nutzer erhalten den Standard.
- [x] Filterleiste (Karte mit Chip-Selects, Suchfeld, Spaltenwähler,
      Sammelaktionen) als **sticky** oben: bleibt beim vertikalen Scrollen
      unter der Kopfzeile stehen und beim horizontalen Scrollen der breiten
      Tabelle in voller Breite sichtbar (Filterleiste außerhalb des
      horizontal scrollenden Containers, `position: sticky; top: <Höhe
      Kopfzeile>`; Sticky-Tabellenkopf aus v14 bleibt zusätzlich). Prüfen
      in Chrome und Edge bei 1366 px Breite mit allen Spalten eingeblendet.
- [x] Anrufliste (`app/lead_anrufliste.py`, Template): Gruppen entfernen,
      eine Liste mit der Sortierung SLA rot → SLA gelb → fällige
      Wiedervorlagen und Rückrufe (Uhrzeit) → Zurückgestellte mit
      erreichtem Datum → Rest nach Eingangsdatum (älteste zuerst); keine
      Score-Komponente mehr. Schnellfilter-Chips bleiben (Heute eingegangen ·
      SLA rot · ≥ 3 Versuche · Rückruf heute · Ohne Leadmanager); die Chips
      bzw. Selects **„Quelle“ und „Einzelquelle“ entfallen**, stattdessen
      Select **„Vertriebskanal“** (Mehrfachauswahl, Farben aus
      `kanal_farben`). Zeile zeigt das Kanal-Badge statt des Quelle-Badges.
      Tasten 1 bis 7 unverändert.
- [x] Status-Label: Blatt Status der Steuerdatei: Zeilen `in_kontaktierung`
      und `qualifiziert` erhalten beide das Label **„Kontaktiert“** (gleiche
      Farbe); Kanban-Spalte „Qualifiziert“ wird mit „In Kontaktierung“ zu
      einer Spalte „Kontaktiert“ zusammengefasst (Anzeige), Trichter in der
      Statistik zeigt die Stufe „Kontaktiert“ (Summe beider Phasen). Interne
      Phasenwerte, `lead_phase_berechnen`, Board-Zuordnung und Tests der
      Phasenlogik bleiben unverändert. Hinweis in der Parametrierung beim
      Status-Import, dass zwei Phasen dasselbe Label tragen dürfen.

## Phase 119: Kundenkartei neu aufgeteilt, Autospeichern

- [x] Layout `GET /lead-management/lead/{id}` (`app/lead_kartei.py`,
      Template): **Kopfbereich** mit Kundenname, Kanal-Badge,
      Interessen-Badges, Statuskette der Phasen (Makro `statuskette`, Label
      „Kontaktiert“ laut Phase 118) und rechts oben dem Button
      **„Terminierung“** (Logik B8 unverändert: aktiv nur bei vollständigen
      Pflichtfeldern und vorgemerktem Termin, sonst ausgegraut mit Tooltip
      der fehlenden Felder). Daneben die Schnellaktionen Anrufen · E-Mail ·
      Notiz · Wiedervorlage als runde Icon-Buttons.
- [x] **Kundeninformationen als horizontaler Block** unter dem Kopf
      (Karte mit mehrspaltigem Formular, 3 bis 4 Spalten ab 1200 px, 2 ab
      900 px, 1 darunter): Anrede · Vorname · Nachname · Telefon (tel:) ·
      E-Mail (mailto) · Straße · PLZ · Ort · Vertriebskanal · Interessen ·
      Objektart (+ Parteien, Rechnungsadresse bei MFH) · Innendienst ·
      Außendienst/Handelsvertreter · Eingangsdatum (nur Anzeige).
      **Entfernt aus der Kartei:** Score/Score-Klasse, Quelle/Kampagne,
      Einwilligung Werbung, Einwilligung SMS/WhatsApp, Wunschzeiten bleiben
      [ANNAHME: Wunschzeiten bleiben, da der Terminassistent sie nutzt].
      Rote Umrandung und Zähler offener Pflichtfelder bleiben (Parameter
      `pflichtfelder`).
- [x] **Autospeichern**: jedes Feld des Kundeninfo-Blocks speichert per
      fetch beim Verlassen (Text) bzw. bei Änderung (Select, Häkchen) über
      `POST /lead-management/lead/{id}/feld` (Feldname + Wert, Validierung
      serverseitig, Antwort JSON mit normalisiertem Wert und
      Pflichtfeld-Zähler). Kein Speichern-Button. Rückmeldung: kleines
      Häkchen „gespeichert“ am Feld für 2 Sekunden, bei Fehler roter Text
      unter dem Feld und alter Wert bleibt stehen. Doppelte Übertragung
      desselben Werts wird unterdrückt. Jede tatsächliche Änderung schreibt
      eine Aktivität `aenderung` („Telefon geändert“ ohne Altwert-Anzeige
      bei Kontaktdaten? Nein: mit Alt → Neu, wie Notizen-Chat-Konvention)
      [ANNAHME: Alt → Neu wird protokolliert]. Rechte wie bisher
      (ID/LM/Admin alle, HV nur eigene Leads, AD read-only).
- [x] **Reiter (Mitte)** in dieser Reihenfolge und als Standard geöffnet
      der erste: **Termin** (aktiver Termin, Historie, Vorab-Gespräch,
      Absage/Umbuchung wie v23) · **Anrufnotizen** (Aktivitäten Typ anruf
      mit Dauer) · **E-Mail-Verlauf** (eigene / automatisierte / Kollegen,
      ein- und ausgehend) · **Timeline** (alle Aktivitäten inkl.
      Notizen-Chat). Reiter **Qualifizierung entfällt** (Route bleibt
      erreichbar, Link weg; bei Aufruf Hinweis „Qualifizierung ist
      abgeschaltet“). Icons statt Überschriften bleiben.
- [x] **Blöcke darunter** (statt der rechten Spalte, als einklappbare
      Karten in voller Breite, Reihenfolge): **Termine** · Angebote ·
      Erfassungen · Projekt · Anhänge · To-Dos. Im Block **Termine** werden
      die **Top-Terminvorschläge direkt angezeigt** (ohne Klick auf „Termin
      vorschlagen“): beim Laden der Kartei werden die Top 5 des Assistenten
      für den vorgefilterten Vertrieblerkreis berechnet (asynchron per
      fetch nach dem Seitenaufbau, Platzhalter „Vorschläge werden
      berechnet …“, Cache 10 Minuten je Lead) und als Liste mit Begründung
      und Button „Vormerken“ angezeigt; Mini-Karte und manuelle Buchung
      bleiben über „Alle Vorschläge / manuell“ erreichbar. Keine Vorschläge,
      wenn Pflichtfelder Adresse fehlen (Hinweis statt Liste).
- [x] Responsiv: unter 900 px Kopf → Kundeninfo → Reiter → Blöcke
      untereinander; Button Terminierung bleibt oben rechts im Kopf.

## Phase 120: Score abschalten, Terminassistent ohne HV, Nicht erreicht ohne Dialog

- [x] Parameter `score_aktiv` (Lead-Einstellungen, Standard **aus**) als
      zentraler Schalter; bei aus: keine Score-Berechnung bei Eingang und
      Änderung, keine Anzeige von Score/Klasse in Kartei, Anrufliste,
      Boards (Spalte entfernt aus dem Spaltenkatalog), Kanban-Karten,
      Dashboard, Handelsvertreter-Ansicht, Statistik („Score-Verteilung“
      ausgeblendet), Pipeline-Wert rechnet ohne Score-Gewichtung (nur
      Phase). Hinweis „Score C – Termin trotzdem buchen?“ entfällt.
      Qualifizierungsbogen: Einstieg aus Anrufliste („Erreicht“ öffnet
      direkt die Kartei mit Reiter Termin statt des Bogens), aus Kartei und
      Kanban entfernt; Vorbelegung `erfassungs_frage` wird übersprungen.
      Logik-Import meldet die Blätter Qualifizierung/Scoring/Klassen als
      „vorhanden, nicht aktiv“.
- [x] Terminassistent (`app/lead_termin.py`): Kandidatenfilter erhält
      Ausschluss **„Handelsvertreter (`ad_profile.terminiert_selbst = 1`)
      werden nicht vorgeschlagen, wenn der anfragende Benutzer nicht selbst
      dieser Handelsvertreter ist“**; Begründungstext im Dialog: „Handels-
      vertreter terminieren ihre Leads selbst“. Leads, die bereits einem
      Handelsvertreter zugewiesen sind (`vorgaenge.ad_id` = HV), zeigen dem
      Innendienst im Block Termine statt Vorschlägen den Hinweis „Lead liegt
      bei <Name> (Handelsvertreter), Terminierung durch den Vertreter“.
      Manuelle Buchung durch den Innendienst auf einen HV bleibt möglich
      [ANNAHME].
- [x] „Nicht erreicht“ (Anrufliste, Kartei, Boards-Inline): kein Dialog
      mehr. Klick = `POST /anruf/{id}` mit `ergebnis = nicht_erreicht`,
      Zeitstempel jetzt, Versuch +1, Stoppuhr-Dauer falls gelaufen;
      **keine Wiedervorlage** (`wiedervorlage_am` leer, Kaskaden-Vorschlag
      `GET /anruf/{id}/vorschlag` wird nicht mehr aufgerufen). Kaskaden-Mails
      bleiben an die Versuchsnummer gekoppelt (2. Versuch `nicht_erreicht`,
      4. Versuch `nicht_erreicht`, letzter `disqualifiziert`), Sperre ab
      `versuche_max` und Übergang nach Disqualifiziert bleiben. Gleiches
      Verhalten für „Mailbox“ [ANNAHME]. „Rückruf gewünscht“ behält seinen
      Datum/Uhrzeit-Dialog. Blatt Kaskade: Spalte `wiedervorlage_nach` wird
      nicht mehr ausgewertet; Lesehilfe entsprechend ergänzen
      (Arbeitsanweisung an der Live-Excel). Fälligkeits-Glocke
      `faellige_wiedervorlagen_melden` bleibt für manuell gesetzte
      Wiedervorlagen.
- [x] Dashboard „Meine Arbeit“: Kachel/Liste „Wiedervorlagen“ zeigt nur
      noch manuell gesetzte (Lead- und Angebots-Wiedervorlagen wie v23);
      neue Liste **„Ohne nächsten Schritt“**: eigene Leads der Gruppe Neu
      mit Versuch ≥ 1, ohne Wiedervorlage, ohne Termin, letzter Versuch
      älter als `ohne_schritt_tage` (Parameter, Standard 2) [ANNAHME: Ersatz
      für die weggefallene automatische Wiedervorlage, damit nichts liegen
      bleibt].

## Phase 121: Tests, Doku, Übergabe

- [x] Tests `tests/test_lead_v3.py`: (a) zwei Benutzer, Spalten umbenennen/
      verschieben/ausblenden wirkt nur beim ersten; (b) Standardspalten ohne
      Anrede/Vorname/Nachname; (c) Anrufliste ohne Gruppen, Sortierung
      SLA → fällig → zurückgestellt → Eingang, Filter Vertriebskanal;
      (d) Label „Kontaktiert“ für beide Phasen, Kanban eine Spalte;
      (e) Autospeichern: Feld ändern → Wert gespeichert, Aktivität
      geschrieben, ungültige PLZ → Fehler und alter Wert; (f) Kartei ohne
      Score/Quelle/Einwilligung/Qualifizierung im HTML; (g) Terminvorschläge
      im Block Termine, Hinweis bei fehlender Adresse, Hinweis bei
      HV-Lead; (h) Terminassistent schlägt für Innendienst keinen HV vor,
      für den HV selbst schon; (i) „Nicht erreicht“ ohne `wiedervorlage_am`,
      Versuch +1, Mail am 2. Versuch geplant, Sperre nach 5; (j)
      `score_aktiv = aus`: kein Score im Eingang, Pipeline-Wert ohne Score;
      (k) To-Dos-Seite. Bestehende `tests/test_lead_v2_*.py` anpassen, wo
      sie Gruppen, Score, Qualifizierung oder den Nicht-erreicht-Dialog
      voraussetzen (jede Anpassung in der Gesamtübersicht begründen).
      Gesamtlauf grün.
- [x] Rollout-Vorbereitung: Server-DB-Kopie nach diagnose\, migrate.py
      zweimal fehlerfrei, `scripts/voll_crawl.py` für admin/innendienst/
      aussendienst grün (alle Lead-Routen inkl. „Mehr …“-Einstiege),
      Abnahmeskript grün. Screenshots vorher/nachher der Kundenkartei und
      des Hauptboards nach `docs/design-v25/`.
- [x] CLAUDE.md: Abschnitt „Neu in v25 – Lead-Management V3 (abgestimmt
      05.10.2026)“ (Plan: PLAN_LEAD_V3.md, Phasen 118 bis 121; Navigation,
      Deals/Infoabend, Spalten je Nutzer, Sticky-Filter, Anrufliste eine
      Liste mit Kanal-Filter, Label Kontaktiert, Kartei-Layout mit
      Autospeichern, Terminvorschläge im Block Termine, Score aus,
      Terminassistent ohne HV, Nicht erreicht ohne Dialog und ohne
      Wiedervorlage, Liste „Ohne nächsten Schritt“), Zuordnungstabelle
      `| v25 | PLAN_LEAD_V3.md | 118–121 |`, Hinweise in „Neu in v12“ und
      „Neu in v23“, dass Score/Qualifizierung seit v25 abgeschaltet sind.
      `docs/leadmanagement-entscheidungen.md` Abschnitt V3 mit allen
      [ANNAHME]-Stellen und ihrer Auflösung. `docs/nach-dem-update-v25.md`:
      Team-Hinweise (neue Menüreihenfolge, Spalten selbst einstellen,
      Wiedervorlage jetzt manuell, Button Terminierung oben rechts).
- [x] Gesamtübersicht am Ende: erledigte Phasen, Testergebnisse,
      angepasste Alt-Tests mit Begründung, Liste aller [ANNAHME]-Stellen,
      gebündelte Rückfragen. Commit mit sprechender Nachricht; **kein push
      vor Freigabe**.

## Kontrollwerte für die Abnahme

- Demo-Lead mit 3 Versuchen, letzter „Nicht erreicht“ um 14:05: Aktivität
  mit Zeitstempel 14:05, `wiedervorlage_am` leer, Versuchspunkte 3 orange,
  keine Mail (Mail nur bei Versuch 2, 4 und 5).
- Demo-Lead ohne Adresse: Block Termine zeigt „Adresse fehlt“, kein
  Vorschlag; nach Eintrag von Straße/PLZ/Ort per Autospeichern erscheinen
  binnen 10 Sekunden Vorschläge ohne Seitenneuladen.
- Innendienst öffnet Lead von René Golaschewski: Block Termine zeigt den
  HV-Hinweis; René selbst sieht Vorschläge nur für sich.
- Benutzer A verschiebt „Telefon“ an Position 2 und benennt „Notiz“ in
  „Bemerkung“ um; Benutzer B sieht Standard.
- Kanban zeigt die Spalten Neu · Kontaktiert · Terminiert … (keine Spalte
  Qualifiziert); Trichter-Stufe „Kontaktiert“ = Summe beider Phasen.

## Zulieferungen / bewusst offen

- Bestätigung der [ANNAHME]-Stellen durch Claudia/Andreas vor oder während
  des Baus: Anrede/Vorname/Nachname nur in Boards ausgeblendet; „nur eine
  Liste“ = ohne Gruppen; Wunschzeiten bleiben in der Kartei; Alt → Neu in
  der Änderungs-Aktivität; „Mailbox“ wie „Nicht erreicht“; manuelle
  HV-Buchung durch ID bleibt; Liste „Ohne nächsten Schritt“ als Ersatz für
  die automatische Wiedervorlage.
- Telefonie/Softphone-Anbindung bleibt ausgeklammert (Entscheidung
  01.10.2026). [OFFEN 1] Zuordnungsregel Infoabend-Lead → Veranstaltung und
  [OFFEN 2] Rest des Auftragstexts V2 (Duplikate durch das Tool) sind
  weiterhin offen und nicht Teil dieses Plans.
- Freischaltung `lead_freigabe_modus = alle` (Lead V4 oder eigener Plan).


## Ergebnis der Umsetzung (05.10.2026, Claude Code)

Alle Phasen 118–121 umgesetzt (sechs Agenten A–F plus zentrale Vorab-/Nacharbeit),
jede Checkbox nach Umsetzung und Test abgehakt. Gesamtlauf `pytest tests -q`
641 passed (v24: 551; neu `tests/test_lead_v3*.py` 90 Tests), `tests/abnahme.py`
93/93, `migrate.py` zweimal gegen die Server-DB-Kopie (2. Lauf ohne Änderungen),
Voll-Crawl admin/innendienst/aussendienst ohne Absturz (Bericht
`diagnose/test_v25/crawl_v25_bericht.txt`). Zehn Alt-Tests bewusst angepasst,
Begründungen in `docs/leadmanagement-entscheidungen.md` Abschnitt V3.3; alle
[ANNAHME]-Stellen aufgelöst (V3.1). Rückfragen R1–R12 am 05.10.2026 wie
vorgeschlagen beantwortet (V3.5; Folgeänderung nur R6: Kennzeichnung „Score-Bonus
(nicht aktiv)“ in der Quellen-Parametrierung, +1 Test). Offen: manuelle
Sichtprüfung in Edge bei 1366 px, Server-Umbenennung der Quelle „Info-Veranstaltung“
→ „Infoabend“ (Admin-To-do in docs/nach-dem-update-v25.md), Freischaltung
`lead_freigabe_modus = alle`. Kein git push vor Freigabe.
