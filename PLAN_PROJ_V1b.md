# PLAN_PROJ_V1b – Projektierung: Oberfläche nach Prototyp (Phase 73)

Voraussetzung: PLAN_PROJ_V1 (Phasen 64–72) ist vollständig umgesetzt und
funktioniert. Dieser Plan ändert **nur Templates und CSS** – keine Routen,
keine Datenbank, keine Logik. Alle Funktionen (Filter, Drag & Drop, Wächter,
Aufgaben-Status, Uploads, Kommentare, Dialoge) bleiben exakt so, wie sie sind;
nur die Darstellung wird gegen die Vorlage getauscht.

**Verbindliche Design-Vorlage:** `docs/projektierung-prototyp.html` – ein
klickbarer Prototyp mit Beispieldaten. Claude Code öffnet diese Datei, liest
CSS und Markup und baut jede Sicht **strukturgleich** nach: gleiche Anordnung,
gleiche Komponenten, gleiche Abstände, gleiche Informationen an gleicher
Stelle. Was im Prototyp als Demo-Toast angedeutet ist („(Demo)"), ist im Tool
bereits echt umgesetzt und bleibt so.

**Start-Prompt für Claude Code (kopieren):**

> Lies `CLAUDE.md`, `PLAN_PROJ_V1b.md` und öffne `docs/projektierung-prototyp.html`
> (CSS und Markup vollständig lesen – das ist die verbindliche Design-Vorlage
> für das Projektierungs-Modul). Setze Phase 73 um: Baue die Templates unter
> `app/templates/projektierung/`, `app/templates/montage/`, den
> Projektierungs-Bereich von `index.html` und die Projektierungs-Blöcke in der
> Vorgangsakte und im Angebots-Editor so um, dass sie dem Prototyp in Aufbau,
> Komponenten und Abständen entsprechen. Ändere dabei keine Routen, keine
> Formular-Namen, keine URLs und keine Logik – nur HTML-Struktur, Klassen und
> CSS. Lege das CSS als eigenen Abschnitt „Projektierung" mit dem Präfix `pj-`
> in `style.css` an (oder als `static/projektierung.css`, in base.html
> eingebunden). Nach jeder Sicht: kurz melden, welche Datei fertig ist. Committe
> am Ende, noch nicht pushen.

---

## Phase 73 – Oberfläche nach Prototyp

### 73.1 Grundregeln

- [x] **Farben:** Die Akzentfarbe des Prototyps (Grün) wird durch
  `--friondo-blau` ersetzt, die Akzent-Fläche (`--accent-soft`) durch ein
  helles Blau (#e3eefa). Sparten-Farben aus dem Prototyp übernehmen
  (WP grün-blau `#0f6e56`, PV orange `#c47a12`, KL blau `#2d6bd6`, WB violett
  `#7a3fbf`) – sie sind bewusst anders als die Tool-Farben, damit man Sparten
  sofort unterscheidet. Ampel-Farben: grün `#1f9d55`, gelb `#d98b0a`, rot
  `#cf3b2c`, „wartet" blau `#2d6bd6`. Neutrale Grautöne aus dem Prototyp
  (`#f3f5f4`, `#e9edeb`, `#d5dcd9`, Text `#17211d`, gedämpft `#5d6b66`).
  Dark Mode des Prototyps wird **nicht** übernommen.
- [x] **Schrift:** keine Google Fonts (Terminal-Server ohne Internetzugang
  im Browser vorausgesetzt) – „Segoe UI" wie im Rest des Tools; Zahlen in
  Tabellen/Karten mit `font-variant-numeric: tabular-nums`. Nummern (PR-…,
  AN-C-…, Beträge) in `Consolas, "Segoe UI Mono", monospace` wie `.mono` im
  Prototyp.
- [x] **Alle CSS-Klassen mit Präfix `pj-`** (z. B. `.pj-card`, `.pj-gw`,
  `.pj-paket`), damit nichts mit bestehenden Klassen (`.kachel`, `.tabelle`,
  `.kanban`) kollidiert. Die alten Klassen `.kanban`, `.kanban-karte`,
  `.gewerk-spalte`, `.karte-gewerk` werden in den Projektierungs-Templates
  durch die neuen ersetzt; ihr CSS bleibt vorerst stehen.
- [x] **Responsiv** wie der Prototyp: Kanban-Spalten seitlich scrollbar
  (`scroll-snap`), Gewerk-Spalten ab 300 px umbrechen, Meine Aufgaben und
  Montage auf Handybreite einspaltig. Seitliche Ränder mindestens 16 px.
- [x] Bestehende Buttons/Knöpfe (`.knopf`) dürfen bleiben, aber innerhalb der
  Projektierung in der kompakten Form des Prototyps (`.pj-btn`, `.pj-btn.primary`,
  `.pj-btn.danger`) – Größe 12 px, Radius 8 px.
- [x] Toast-Meldungen des Prototyps entsprechen den vorhandenen `.meldung`-Zeilen –
  keine Änderung nötig.

### 73.2 Startportal (`index.html`, Bereich Projektierung)

- [x] Karte „Projektierung" wie `.pcard.demo` im Prototyp: Überschrift mit
  gelbem Badge **„Demo · Coming soon"** (`.pj-dbadge`), darunter die fünf
  Kacheln als kompakte Zahlenfelder (`.pk.five`: Zahl groß, Bezeichnung klein),
  darunter der graue Hinweis „Nur für Admins sichtbar · andere Rollen sehen
  Null-Kacheln und ‚Das Modul befindet sich im Aufbau.'" (nur für Admin
  sichtbar; andere Rollen sehen den bisherigen Hinweistext). Rahmen der Karte
  in `--friondo-blau`, gesamte Karte klickbar → `/projektierung`.
- [x] Die beiden anderen Karten (Lead-Management, Angebotstool) **nicht**
  verändern.

### 73.3 Board (`projektierung/kanban.html`)

- [x] Kopfbereich: Eyebrow „Startseite · Bereich Projektierung", darunter die
  **Kachelzeile** `.pj-tiles` (je Phase: Zahl, Phasenname, Sparten-Untertitel
  „3 WP / 2 PV"; letzte Kachel „Überfällige Aufgaben" mit rotem Rand und roter
  Zahl, Untertitel „→ Meine Aufgaben", verlinkt).
- [x] **Filterleiste als Chips** (`.pj-chip`, aktiv = `.on`): Alle · WP · PV ·
  KL · WB (Sparten-Filter), dann „Projektleiter ▾", „Team ▾", „Kanal ▾"
  (Chips öffnen ein kleines Dropdown oder sind als `<select>` im Chip-Stil
  gestaltet), Textfeld Kunde/PR-Nr., Häkchen Storniert, Chip „+ Angebot →
  Projekt" (öffnet die bestehende Angebotsauswahl). Der bisherige
  `<form class="suchleiste">` bleibt funktional erhalten – nur optisch als
  Chips. Filter greifen wie bisher per Submit (Auto-Submit bei Chip-Klick).
- [x] **Spalten** `.pj-col`: Hintergrund `--surface2`, Radius 12 px,
  Kopfzeile „Phasenname   Anzahl" (Anzahl rechts, gedämpft), Breite 280 px,
  Spalte „Abgeschlossen" eingeklappt (Details) wie bisher.
- [x] **Karte** `.pj-card` exakt wie im Prototyp:
  Zeile 1: PR-Nummer mono klein links, rechts rotes Badge „n überfällig"
  (nur wenn > 0). Zeile 2: Kundenname fett. Zeile 3: Ort · PL-Kürzel ·
  Kanal-Badge (`.pj-badge.kanal`, hellblau). Danach **je Gewerk eine Zeile**
  `.pj-gw` (grauer Hintergrund, Radius 6): Sparten-Chip farbig (`.pj-sp.WP` …),
  Phasenname (abgeschnitten mit Ellipsis), Ampel-Punkt, rechts Datum des
  nächsten Termins oder „x/y" bzw. „1 überf." gedämpft. Fußzeile: Auftragswert
  mono links, rechts „2 Gewerke" bei Kombi. Storniertes Gewerk durchgestrichen.
  Hover: Rahmen in `--friondo-blau`. Drag & Drop, Klick → Akte, Gewerk-Dialog
  bei Kombi unverändert.
- [x] Unter dem Board der graue Hinweiskasten `.pj-note` mit dem Text
  „Karte = Projekt. Die Spalte richtet sich nach dem Gewerk, das am weitesten
  zurückliegt; die Chips zeigen jedes Gewerk einzeln." (nur beim ersten
  Aufruf pro Sitzung, danach ausblendbar – optional).

### 73.4 Projektakte (`projektierung/akte.html`)

- [x] Oben Link „← Board" als `.pj-btn`.
- [x] **Kopfblock** `.pj-akte-head` (weiße Karte, Radius 12): Eyebrow
  „Projektakte", Titel „PR-260041 · Müller, Duisburg-Rheinhausen" (Nummer mono),
  darunter die Datenzeile `.row` als umbrechende Label/Wert-Paare: Ausführung ·
  Rechnung („identisch", wenn gleich) · Kontakt (Telefon · E-Mail) · Vertrieb
  (Name + Kanal-Badge) · Projektleiter (änderbar wie bisher) · Gesamt-Auftragswert
  (fett, mono) · Projektstatus („Feinplanung (PV)" = Phase + Gewerk, das sie
  bestimmt). Button-Reihe: „💬 Kommentar" (springt zum Kommentarfeld), „⬆ Dokument",
  „📅 Termin" (öffnen die vorhandenen Dialoge/Formulare).
- [x] **Gewerk-Spalten** `.pj-gewerke` (Grid, min. 300 px, nebeneinander):
  jede Spalte `.pj-gcol` mit **4 px farbigem oberen Rand** in der Sparten-Farbe.
  Reihenfolge innerhalb der Spalte exakt wie im Prototyp:
  1. Kopf: Sparten-Chip + Name („Wärmepumpe", „Photovoltaik", „Klima",
     „Wallbox") + rechts Badge mit Gerät/Kurzbeschreibung (aus dem Angebot:
     Paketname bzw. erste Position; bei TAIFUN die Angebotsbezeichnung).
  2. **Stepper** `.pj-stepper`: fünf Balken (Feinplanung → Abnahme offen),
     erledigte in `--friondo-blau`, aktuelle halbtransparent; darunter
     „Phase: **Montage geplant**" links, „seit 12.09." rechts.
  3. **Ampel-Zeile** `.pj-ampel`: Punkt, Fortschrittsbalken (grün/gelb/rot nach
     Ampel), „15 / 18 Pflicht · 1 überfällig".
  4. **Datenraster** `.pj-kv` (2 Spalten Label/Wert): Auftrag (Nummer + Version ·
     Betrag mono · „(urspr. …)" gedämpft · TAIFUN-Badge), Feinplaner (Name ·
     Termin war/ist … oder **„Termin fehlt"** fett), Elektroplaner, Heizlast
     (kW mono · Datum · Link PDF · Upload), Montage (**Datum fett** · Teams ·
     „Kunde bestätigt ✔" oder „– noch nicht terminiert").
  5. **Aufgaben als Pakete** `.pj-paket` = `<details>` je Paket: Summary grau
     mit Paketname links und „4 / 5" rechts (`.cnt`); Pakete mit offenen
     Pflichtaufgaben sind `open`, vollständig erledigte eingeklappt (Summary
     „alle erledigt"). Aufgabenzeile `.pj-task`: Checkbox (bestehendes
     Erledigt-Formular), Titel, darunter klein Verantwortlicher · Zusatz
     („erledigt 08.09.", „wartet seit 11 Tagen", „am Montagetag"); rechts
     Fälligkeits-Badge `.due` (grau), `.due.over` (rot, „18.09. überfällig"),
     `.due.wait` (blau, „wartet"). Erledigte Zeilen durchgestrichen und
     gedämpft. Status-Dropdown wandert in ein aufklappbares Detail unter der
     Zeile (Klick auf den Titel), damit die Zeile schlank bleibt.
  6. Button-Reihe: „+ Aufgabe", „+ Paket", „📅 Feinplanungstermin" (wenn keiner
     existiert), primär „Phase ändern", rot „Stornieren"; ab Phase Abnahme offen
     zusätzlich primär „Rechnung freigeben".
- [x] **Reiter** `.pj-tabs` unter den Gewerken: Dokumente · Verlauf & Kommentare ·
  Subs & Bestellungen · Mail-Verlauf · Rechnungen. Nur ein Reiter sichtbar,
  Wechsel per JS ohne Neuladen; aktiver Reiter blau unterstrichen. Inhalte:
  - Dokumente als **Ordnerbaum** `.pj-tree` („📁 01 Angebot & Erfassung",
    darunter Dateien eingerückt gedämpft, mit Anzahl bei Fotos), Upload und
    Löschen wie bisher.
  - Verlauf als `.pj-log`: Autor fett + Zeit gedämpft, Text; Systemeinträge
    kursiv gedämpft; @Erwähnungen blau fett; Kommentarfeld + „Senden" unten.
    Notizen-Chat des Vorgangs darunter aufklappbar.
  - Subs & Bestellungen als `.pj-term`-Zeilen (Name fett links, Beschreibung ·
    **Status** · Termin), Buttons „+ Sub beauftragen", „Material bestellen".
  - Mail-Verlauf, Rechnungen: Platzhaltertexte wie bisher, gedämpft.
- [x] Dialoge (Phase ändern, Stornieren, Angebot → Projekt) im Stil
  `.pj-dialog .box`: Titel, Zeilen, roter Hinweiskasten für Wächter-Verstöße
  („Wächter: 3 Pflichtaufgaben offen (…)"), Auswahl-Optionen als
  `.opt`/`.opt.sel`, Button-Reihe. Vorhandene `<dialog>`-Elemente nur umstylen.

### 73.5 Meine Aufgaben (`projektierung/meine_aufgaben.html`)

- [x] Eyebrow „Angemeldet als <Name> · <Rolle>", Titel „Meine Aufgaben".
- [x] Keine Tabellen mehr: Gruppen `.pj-grp` mit Überschrift „Überfällig · 2"
  (rot), „Heute · 3", „Diese Woche · 4", „Später", „Neu zugewiesen · 1";
  jede Aufgabe als Karte `.pj-task` (Checkbox, Titel, darunter klein
  „PR-260041 Müller · WP · Montage Mo 22.09."), rechts Fälligkeits-Badge.
  Status-Dropdown wie in der Akte aufklappbar.

### 73.6 Liste und Termine

- [x] `liste.html`: Tabelle bleibt, aber Sparten-Chips, Ampel-Punkte,
  Fälligkeits-Badges und mono-Nummern aus dem Prototyp-Stil; Filterleiste
  als Chips wie im Board.
- [x] `termine.html`: Wochen-/Monatsansicht bleibt; Termineinträge als
  `.pj-term`-Zeilen mit Sparten-Chip und Team.

### 73.7 Montage (`montage/einsaetze.html`, `montage/einsatz.html`)

- [x] Einsätze-Liste wie `.mob` im Prototyp: schmale Karte (max. 420 px,
  zentriert), Eyebrow „SHK-Team 1 · Marco", Titel „Meine Einsätze", je Einsatz
  `.einsatz`: Datum fett blau, Kunde · Ort fett, Sparten-Chip + Gerät +
  Besonderheiten, Button-Reihe „Steckbrief" (primär), „📷 Foto",
  „Montage gestartet" bzw. „Montage fertig".
- [x] Einsatz-Detail (Steckbrief) im selben Karten-Stil: Datenraster `.pj-kv`,
  Fotos-Ordner, offene Montage-Aufgaben als `.pj-task`, Hinweiskasten
  „Formulare folgen in V3".

### 73.8 Vorgangsakte und Angebot

- [x] Block „Projekt PR-… · Phase je Gewerk" in der Vorgangsakte und
  „Projektstand" am Angebot (Außendienst-Sicht) als Mini-Karte im
  `.pj-card`-Stil mit den `.pj-gw`-Zeilen.

### 73.9 Abschluss

- [x] Alle Sichten mit dem Prototyp nebeneinander vergleichen (Board, Akte
  mit Kombi-Projekt WP + PV, Meine Aufgaben, Montage, Startportal) und
  Abweichungen beheben.
- [x] `CLAUDE.md`: Überschrift „## Neu in v10 – Projektierung V1 (abgestimmt
  20.09.2026)" korrigieren in „## Neu in v11 – Projektierung V1 (abgestimmt
  22.09.2026)"; am Ende dieses Abschnitts ergänzen:
  „- Oberfläche der Projektierung folgt der Design-Vorlage
  `docs/projektierung-prototyp.html` (CSS-Präfix `pj-`); spätere Änderungen
  am Modul-Layout zuerst im Prototyp, dann im Tool."
- [x] Commit „Phase 73: Projektierung-Oberfläche nach Prototyp".
