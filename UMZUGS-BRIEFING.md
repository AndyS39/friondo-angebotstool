# UMZUGS-BRIEFING – Projekt „Angebotstool" im Friondo-Firmenaccount

Zweck dieser Datei: Erste Orientierung für jeden neuen Chat in diesem
Projekt (und für jeden Kollegen, der hier mitarbeitet). Das Projekt ist die
Planungszentrale für das Friondo-Tool; die Historie bis 09/2026 liegt im
bisherigen Privat-Account von Andreas (Archiv, nur Lesen). Maßgeblich für
den Systemstand ist IMMER die CLAUDE.md im Projektwissen.

## 1. Was hier geplant wird
Das Friondo-Tool (FastAPI/SQLite, Terminal-Server http://192.168.35.4:8000)
mit drei Bereichen: **Angebotstool** (Erfassung → Konfigurator WP + PV →
Angebot → Versand → Verfolgung, monday-Sync, Graph-Mail als
angebot@friondo.de), **Projektierung** (Auftrag → Feinplanung → Montage →
Abnahme/Freigabe; aktuell Demo-Modus) und **Lead-Management** (Lead-Eingang
→ VOT-Termin; aktuell Demo-Modus). Rollen: Admin, Innendienst, Außendienst,
Projektierung, Montage, Leadmanagement – der Außendienst sieht nie EK und
Deckungsbeiträge.

## 2. Arbeitsmodell (bewährt seit v1 – bitte beibehalten)
- **Chats planen, Claude Code baut.** Chats in diesem Projekt spezifizieren
  und erzeugen Plan-Dateien; umgesetzt wird von Claude Code auf dem
  Entwicklungs-PC (bzw. in Cowork-Sitzungen mit Ordnerzugriff). Andreas ist
  kein Programmierer: Schritt-für-Schritt-Anleitungen, fertige Prompts zum
  Kopieren, keine unerklärten Fachbegriffe.
- **Eine Plan-Datei je Ausbaustufe** (PLAN_*, PLAN_PROJ_*, PLAN_LEAD_*) mit
  Phasen und Checkboxen; alle Texte wörtlich im Plan. Standard-Startprompt:
  „alle Phasen vollständig in einem Durchlauf umsetzen, Checkboxen abhaken,
  am Ende Gesamtübersicht, Rückfragen gebündelt."
- **Live-Master im Projektordner** (C:\Users\Andreas\Documents\Claude\
  Angebotserstellungtool): CLAUDE.md, konfigurator_logik_v5.xlsx,
  projektierung_logik_v1.xlsx. Nie ersetzen – Änderungen stehen als
  Arbeitsanweisung im Plan, Claude Code führt sie an der Datei aus.
- **Nummern:** CLAUDE-Versionsabschnitt je Plan = „höchste + 1";
  Phasennummern laufen global fortlaufend (Kollisionen vermeiden – die
  Zuordnungstabelle Plan ↔ Version steht in der CLAUDE.md). Nur EIN Plan
  gleichzeitig in Umsetzung, strangübergreifend abstimmen.
- **Rollout-Grundregel:** aktuelle Server-DB-Kopie nach diagnose\ →
  migrate.py zweimal gegen die Kopie → Voll-Crawl + Abnahmeskript → erst
  dann git push und auf dem Server update.bat (als Administrator; sichert,
  zieht, migriert, startet). Danach docs/nach-dem-update-*.md abarbeiten
  und die CLAUDE.md hier im Projektwissen austauschen.
- **Wartungsfenster (seit v27, PLAN_V17 Phase 132):** Updates nur im festen
  Fenster **Dienstag 22:30–23:30** [ANNAHME], nie zur Arbeitszeit; vorher
  Wartungsbanner über Parametrierung → Betrieb setzen (mindestens 30 Minuten
  vorher), nach update.bat `scripts\smoke.bat`, Banner wieder entfernen.
  Hotfixes außerhalb des Fensters nur mit Freigabe von Andreas. Der Server
  läuft als Dienst (NSSM bzw. Aufgabe + Wächter, `docs/betrieb.md`).

## 3. Dateien und Ablage
- **Projektwissen (hier):** CLAUDE.md (kanonisch), PLAN_GESAMT.md, aktive
  Pläne, Konzepte (PROJEKTIERUNG-/LEADMANAGEMENT-KONZEPT), Briefings,
  bei Bedarf der letzte STATUS-GESAMT-Schnappschuss. Schlank halten:
  erledigte Pläne fliegen raus – Archiv ist der Projektordner/Git.
- **Projektordner/Git (Entwicklungs-PC):** kompletter Code, alle Pläne,
  docs/ (u. a. projektierung-entscheidungen.md,
  leadmanagement-entscheidungen.md, nach-dem-update-*.md, STATUS-GESAMT.md),
  Logik-Excels, anlagen/ (Broschüren), Artikel-Preislisten.
- **NIE ins Projektwissen hochladen:** die Preislisten-Excel mit
  EK-Spalten, .env/Zugangsdaten/Tokens, Datenbank-Kopien (diagnose\),
  Server-Backups, Kunden-Exporte. Grund: Projektinhalte können je nach
  Freigabe von Kollegen gelesen werden – EK/DB-Wissen bleibt beim
  GF/ID-Kreis, exakt wie im Tool.
- **Sichtbarkeit dieses Projekts:** privat bzw. nur für GF/Innendienst
  freigeben, solange Außendienst-Kollegen im selben Firmen-Account sind.

## 4. Startprompts (Kopiervorlagen)
Neuer Planungs-Chat:
> Lies zuerst die CLAUDE.md und dieses UMZUGS-BRIEFING aus dem
> Projektwissen. Ich möchte am Strang <Angebotstool | Projektierung |
> Lead-Management> weiterarbeiten: <Thema>. Arbeitsmodell wie im Briefing.

Umsetzung an Claude Code:
> Lies CLAUDE.md und <PLANDATEI>.md und setze alle Phasen vollständig in
> einem Durchlauf um. Hake jede Checkbox nach Umsetzung und Test ab, führe
> am Ende alle Regressions- und Abnahmetests aus und zeige mir eine
> Gesamtübersicht (erledigte Phasen, Testergebnisse, offene Punkte).
> Fachliche Unklarheiten nicht raten – sammeln und gebündelt fragen.

Statusaufnahme (bei Unklarheit über den Stand):
> Erzeuge docs/STATUS-GESAMT.md neu nach dem Muster vom 29.09.2026
> (Checkbox-Stände aller Pläne, Server vs. lokal, CLAUDE-Abgleich, Bugs,
> Provisorien, Wartet-auf-Nutzer, Datenstand, empfohlene Reihenfolge).

## 5. Stand zum Umzugszeitpunkt (Ende September 2026)
- Angebotstool produktiv (Kennzahlen 29.09.: 484 Kunden, 498 Vorgänge,
  176 Angebote); PV-Konfigurator (v16) und Projektierung V4 (v17)
  ausgerollt; PLAN_GESAMT Teil B (Doku-Bereinigung, Projektierung-Go-live-
  Rest, BzA-Datenblatt am Angebot, Anschriften, Lead 1.1) umgesetzt –
  Teil C (Gesamtabnahme + finaler Rollout) nach Freigabe. Maßgeblich:
  beiliegende CLAUDE.md und PLAN_GESAMT.md.
- **Offene Zulieferungen** (Details: STATUS-GESAMT Abschnitt 6):
  monoenergetische Klassengrenzen + VK-Preisliste (Abstimmung Janni),
  CS8800-Broschüre, TAIFUN-Muster (Auslegungszeile, Pos.-124-Text), weiße
  8800er-BAFA-Nummer, Hybrox-21-Bausteine, Dachbelegungstool + PV-Feinschliff,
  Collin-Daten (UGL), Heizreport-API-Zugang, M365 (projektierung@-Postfach,
  Fern-Signatur-Route, WireGuard mobil), CEO-Entscheidungen (Rabattstufen,
  KfW-Wächter u. a.), Freigaben Demo → Pilot/alle für Projektierung und Lead.

## 6. Eigenheiten, die Zeit sparen
- Datei-Uploads in Chats kommen gelegentlich leer an → Inhalt notfalls als
  Text einfügen; in Cowork-Sitzungen entfällt das (direkter Ordnerzugriff).
- Ein bereits laufender Chat sieht nachträgliche Projektwissen-Uploads
  nicht – neue Dateien wirken erst in neu gestarteten Chats.
- Browser-Chats sehen den Entwicklungs-PC nicht; Claude Code sieht nur den
  PC. Brücke ist der Nutzer (Dateien hin- und herreichen) – außer in Cowork.
- Nach jedem Rollout: CLAUDE.md hier austauschen, sonst planen neue Chats
  auf veraltetem Stand.
