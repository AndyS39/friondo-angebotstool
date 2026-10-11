# Friondo Design-System (v14, PLAN_V12 · Design v2 ab v30, PLAN_V18)

Ein zentrales Stylesheet (`app/static/style.css`), keine externen CDNs
oder Webfonts – das Tool funktioniert vollständig ohne Internet. Das
Angebots-PDF (und alle anderen fpdf2-PDFs) sind davon unberührt.

## Design v2 (v30, PLAN_V18 Phasen 145/146) – Hell und Dunkel

Vorlage ist der HTML-Prototyp „Nachtglas“ von Andreas mit den Screenshots
`portal-dunkel.png` und `hauptboard-dunkel.png` (alles unter
`docs/design-v30/vorlage/`). Übernommen wurde **nur die Optik**: ruhige
Flächen, Karten mit feiner 1-px-Kontur und Radius 14–18 px, gefüllte
Status-Pillen, farbige Chips und Avatare, große Kennzahlen, Tabellenkopf
in Kapitälchen mit Buchstabenabstand. Aufbau, Inhalte, Routen,
Formularnamen und Rollenregeln sind unverändert („Jetzt dran“, Suche oben,
Icon-Leiste für alle Module und „441 Hinweise“ wurden nicht nachgebaut).
Schrift bleibt die Systemschrift (`--schrift`), Zahlen tabellarisch
(`font-variant-numeric: tabular-nums`) statt Monospace.

**Zwei Modi, drei Token-Blöcke** am Anfang von `style.css`:

1. `:root` – **Hell** (heutige Friondo-CI: Friondo-Blau, Dunkelblau der Kopfzeile),
2. `:root[data-theme="dunkel"]` – **Dunkel** (Vorlage),
3. `@media (prefers-color-scheme: dark) { :root:not([data-theme="hell"]) … }` –
   **„Gerät entscheidet“** mit exakt denselben Werten wie Block 2
   (der Wächter `tests/test_v30_design.py` prüft die Gleichheit).

**Umschalter:** im Kopfzeilen-Menü (`base.html`) stehen die Radio-Chips
„Darstellung: Gerät · Hell · Dunkel“ (`.darstellung-wahl`, Icons
`geraet`/`sonne`/`mond`). Die Wahl wird per JS sofort auf `<html data-theme>`
gesetzt (`navigation.js`), über `POST /einstellungen/darstellung` je Benutzer
gespeichert (`benutzer_einstellungen`, Key `darstellung`, Werte `geraet` |
`hell` | `dunkel`, `app/darstellung.py`) und als Cookie `darstellung` (1 Jahr)
abgelegt; die Middleware (`auth.RollenMiddleware`) schreibt den Modus **vor
dem Rendern** in das `<html>`-Tag (kein Aufblitzen). Angemeldet gilt die
gespeicherte Wahl – das Cookie wird nachgezogen; die Login-Seite liest nur
das Cookie. `<meta name="theme-color">` folgt dem Modus
(`darstellung.THEME_COLOR`: Hell `#1b2a5e`, Dunkel `#070d1a`).

### Semantische Tokens (Hex je Modus)

| Token | Hell | Dunkel | Zweck |
|---|---|---|---|
| `--flaeche` | `#f6f8fa` | `#070d1a` | Seitenhintergrund |
| `--flaeche-karte` | `#ffffff` | `#0e1626` | Karten, Tabellen, Formulare, Menüs, Eingabefelder |
| `--flaeche-erhoeht` | `#1b2a5e` | `#0b1322` | Kopfzeile, Summenzeile, aktive Navigationschips |
| `--flaeche-hover` | `#eef1f5` | `#16213a` | Zeilen-Hover, aktive Flächen |
| `--flaeche-abgesetzt` | `#eef1f5` | `#121b2e` | Tabellenkopf, Kacheln in Portal-Karten, Chips, Leer-Zustände |
| `--linie` / `--linie-stark` | `#dde3ea` / `#c6cfda` | `#1e2a40` / `#2c3a55` | Konturen, Zeilenlinien / Feldränder |
| `--text` / `--text-dezent` | `#1f2937` / `#64748b` | `#eef3fb` / `#9fb0c8` | Text / Unterzeilen, Hinweise (≥ 3 : 1) |
| `--text-titel` / `--text-invers` | `#1b2a5e` / `#ffffff` | `#eef3fb` / `#eef3fb` | Überschriften, Kennzahlen / Text auf `--flaeche-erhoeht` |
| `--link` | `#326ea5` | `#8ab4f8` | Textlinks, blaue Kennzahlen (`.stat-zahl.blau`) |
| `--akzent` / `--akzent-hover` | `#3376b6` / `#326ea5` | `#67e8f9` / `#9cf0fb` | Primärknopf, aktive Elemente, Fortschritt |
| `--akzent-text` | `#ffffff` | `#06202a` | Text auf `--akzent` (Dunkel: dunkler Text auf Cyan) |
| `--akzent-flaeche` | `#eaf2fa` | `#0f2a36` | Akzent-Tint (aktive Zeile, Hover, eigene Notiz) |
| `--akzent-glanz` / `--fokus` | `rgba(51,118,182,.25)` / `#3376b6` | `rgba(103,232,249,.25)` / `#67e8f9` | Fokusring, Glanz unter Primärknöpfen |
| `--status-gruen` (-bg) | `#2e7d32` (`#e6f4e6`) | `#5fd38a` (`#0f2b1d`) | Angenommen / OK |
| `--status-orange` (-bg) | `#9e5305` (`#fdf1dc`) | `#f5b74a` (`#33230a`) | Vorbereitet / Warnung / Demo-Badges / Wartungsbanner |
| `--status-rot` (-bg) | `#c0392b` (`#fdeaea`) | `#ff8a80` (`#3a1518`) | Abgelehnt / fällig / Fehler |
| `--status-blau` (-bg) | `#2c6cb0` (`#e3effa`) | `#7cb8ff` (`#0f2544`) | Versendet / Neu |
| `--status-grau` (-bg) | `#566376` (`#eef1f5`) | `#aab8cc` (`#1a2335`) | Entwurf / Überholt |
| `--status-violett` (-bg) | `#6b3fa0` (`#efe6f7`) | `#c4b5fd` (`#261c40`) | Individuell / TAIFUN / Kanal-Badge |
| `--text-auf-farbe` | `#ffffff` | `#06202a` | Text auf gefüllten Status-/Sparten-/Teamflächen (SLA-Chips, Glocke, gefährlicher Knopf) |
| `--sparte-wp/-pv/-kl/-wb` | `#a84c33` / `#8a6307` / `#246fa3` / `#36722b` | `#f0a08a` / `#f2c14e` / `#7cc4f5` / `#7fd49a` | Sparten-Chips (`.chip-wp …`), Interesse-Badges, Kalendermarken |
| `--q-website … --q-monday` | wie v21 | aufgehellt | Lead-Quellen (kategorial) |
| `--pj-*` | wie PLAN_PROJ_V1b | abgedunkelte Flächen, helle Farben | Projektierung (Board, Akte, Ampeln, Sparten) |
| `--avatar-1 … --avatar-8`, `--avatar-text` | 8 Farben, Weiß | identisch | Avatar-Palette (Initialen, Farbe aus der Benutzer-ID) |
| `--schatten-1` / `--schatten-2` | weiche Schatten | `0 0 0 1px --linie` / Kontur + Tiefe | Karten / Overlays – im Dunkelmodus Kontur statt Schatten |
| `--r-s/-m/-l/-xl` | 6 / 10 / 14 / 18 px | – | Radien (Chips/Felder, Knöpfe, Karten, Portal-Karten) |
| `--a-1 … --a-6`, `--t-xs … --t-xxl`, `--schrift` | – | – | Abstände, Schriftgrößen (`--t-xxl` = große Kennzahl), Schriftstack |

Aliase aus v14 bleiben erhalten und zeigen auf die semantischen Tokens:
`--friondo-blau` = `--akzent`, `--friondo-blau-dunkel` = `--akzent-hover`,
`--friondo-blau-hell` = `--akzent-flaeche`, `--friondo-dunkel` = `--text-titel`
(**nur für Text** – Kopfzeile und dunkle Flächen nutzen `--flaeche-erhoeht`),
`--g-50 … --g-700`, `--grau-hell` = `--flaeche`, `--grau-linie` = `--linie`.

### Regeln für neue Seiten

- **Nur Tokens.** Keine Hex-, rgb()- oder benannten Farben in CSS oder
  Templates; feste Werte nur mit Kommentar `/* fest: Grund */` (CSS),
  `{# fest: Grund #}` (Template) bzw. `// fest: Grund` (JS) in derselben oder
  der Vorzeile. Der Wächter `tests/test_v30_design.py` sucht in
  `app/static/*.css` (unterhalb der Token-Blöcke) und `app/templates/**/*.html`.
  Zulässige Ausnahmen heute: Logo-Kachel der Kopfzeile, Dialog-/Lightbox-
  Abdunklung, Text auf dynamischen Teamfarben, Druckansicht, Unterschrift-
  Canvas (PDF-Einbettung), Formularwerte von Farbfeldern.
- **Dynamische Farben** (Kanal-Badges aus `kanal_farben`, Teamfarben) laufen
  über eine CSS-Variable im `style`-Attribut (`style="--f: {{ farbe }}"`); im
  Dunkelmodus den Text aufhellen: `color: color-mix(in srgb, var(--f), white 35%)`.
- **Text auf farbigen Flächen** immer `--akzent-text` (Akzent) bzw.
  `--text-auf-farbe` (Status-/Sparten-/Teamfarben) – nie `#fff`.
- **Dunkle Flächen** (Kopfzeile, Summenzeile, aktive Chips der alten
  Navigation) nutzen `--flaeche-erhoeht` + `--text-invers`; `--friondo-dunkel`
  ist im Dunkelmodus fast Weiß und taugt nur als Textfarbe.
- **Kontrast:** Text auf Flächen ≥ 4,5 : 1, dezenter Text ≥ 3 : 1 – in
  beiden Modi (`tests/test_v30_design.py::Kontrast`, WCAG-Luminanz). Neue
  Token-Paare dort eintragen.
- **Beide Modi prüfen:** jede neue Seite einmal hell und einmal dunkel
  ansehen (`scripts/design_screenshots.py nachher --modus hell|dunkel`,
  Chrome headless + DevTools, Ziel `docs/design-v30/`); angemeldete Benutzer
  folgen ihrer gespeicherten Wahl, das Skript setzt sie über die Route.
- **Neue Tokens** immer in allen drei Blöcken ergänzen (Dunkel- und
  Media-Block identisch); Druck (`@media print`) bleibt Schwarz auf Weiß.
- PDFs (fpdf2) kennen keine Tokens: `pdf_export`, `protokoll_pdf`,
  `lieferschein_pdf`, `bza_datenblatt`, `wirtschaftlichkeit_pdf`,
  `steckbrief_pdf` und die Montage-Formular-PDFs lesen nie `style.css`
  und importieren kein `templating` (Test `PdfUnveraendert`).

### Bausteine (Design v2)

- **Karten** `.karte`, `.formular`, `.suchleiste`, `.tabelle`, `.hinweis`,
  Akte-/Editor-Kopfkarten: Fläche `--flaeche-karte`, 1-px-Kontur `--linie`,
  Radius `--r-l` (Portal-Karten `--r-xl`), Schatten `--schatten-1` (hell
  weich, dunkel Kontur).
- **Kennzahl-Kacheln** `.kachel.stat`: Zahl `.stat-zahl` in `--t-xxl`/800,
  Unterzeile `.dezent`, Farbakzent als 3-px-Balken links (`--kachel-akzent`:
  Standard `--akzent`, rot bei `.stat-zahl.dringend`, orange bei `.warn`,
  `--link` bei `.blau`, Kontur bei `.inaktiv`). In Portal-Karten liegen die
  Kacheln auf `--flaeche-abgesetzt` ohne Kontur.
- **Portal** (`index.html`): Begrüßungszeile `.portal-kopf` →
  `.portal-begruessung` („Guten Morgen/Tag/Abend, Vorname“: < 11 Uhr Morgen,
  < 18 Uhr Tag, sonst Abend; Vorname aus `benutzer.vorname`, sonst erster
  Namensteil) und `.portal-datum` (Wochentag · Datum · KW) über den drei
  Bereichen; darunter alles wie bisher.
- **Status-Badges** `.abzeichen.status-*` (Makro `status_badge(status)`):
  gefüllte Pille mit Status-Punkt (`.abzeichen-punkt`), Textfarbe
  `--status-*`, Fläche `--status-*-bg`, 1-px-Kontur in der Textfarbe.
  Der Pfeil „▾“ erscheint nur in Auswahl-Kontexten (`.abzeichen.mit-pfeil`,
  `summary > .abzeichen`, `.statusform .abzeichen`).
- **Chips** `.chip.chip-wp/-pv/-kl/-wb` (Sparten, `--sparte-*`), `.lm-kanal`
  (Kanal), `.lm-quelle` (Quelle), `.abzeichen.interesse-*`: farbige Pille auf
  getönter Fläche (`color-mix(in srgb, Farbe 12–14 %, transparent)`), gefüllt
  (`.chip-erfasst`) mit `--text-auf-farbe`, ausgeblendet grau durchgestrichen.
- **Avatare** (Makro `avatar(name, id, klasse='')` in `_komponenten.html`):
  zwei Initialen (erstes und letztes Wort), Klasse `avatar-<n>` mit
  `n = id % 8 + 1` → `--avatar-<n>`; Größen `.klein`/`.gross`, Gruppen
  `.avatar-gruppe`, mit Text `.avatar-mit-name`. Boards und Benutzerverwaltung
  nutzen es.
- **Tabellen** `.tabelle`: Kopf `--flaeche-abgesetzt`, Kapitälchen
  (0.72 rem, 700, Buchstabenabstand 0.08 em, `--text-dezent`), feine
  Zeilenlinie `--linie` ohne Zebra, Hover `--flaeche-hover`, Zahlen
  tabellarisch (`.rechts`), Summenzeile `--flaeche-erhoeht`/`--text-invers`.
- **Filterleiste** `.suchleiste`: Karte mit Suchfeld auf
  `--flaeche-abgesetzt` und Chip-Selects (Radius 8 px, Kontur
  `--linie-stark`, Hover Akzent). Formularnamen unverändert.
- **Knöpfe** `.knopf`: Primär = `--akzent` mit `--akzent-text` (Dunkel:
  dunkler Text auf Cyan), Radius `--r-m`, Glanz `--akzent-glanz`;
  `.zweitrangig` = Kontur `--linie-stark` auf `--flaeche-karte`;
  `.gefaehrlich` = `--status-rot` mit `--text-auf-farbe`; `.ghost` = nur
  Text `--link`; `.symbol` = kompakter Icon-Knopf; `.gross` (mobil) Radius `--r-l`.
- **Eingabefelder**: Grundlinie für alle `input`/`select`/`textarea`
  (`--flaeche-karte`, `--text`, Rand `--linie-stark`), Fokus `--fokus` +
  Ring `--akzent-glanz`; Fokusring überall sichtbar (`:focus-visible`).
- **Dropdown-Menüs** `.menue-liste`, `.lm-menue`, `.erwaehnung-liste`:
  `--flaeche-karte`, Kontur `--linie-stark`, `--schatten-2`, Text `--text`.
- **Glocke** `.glocke-zahl` (`--status-rot`/`--text-auf-farbe`), ungelesene
  Einträge `--akzent-flaeche`; **Wartungsbanner** `--status-orange`/`--text-auf-farbe`.
- **Leer-Zustände** `.leer-zustand`: gestrichelte Kontur `--linie-stark` auf
  `--flaeche-abgesetzt`; **Fehlerseite** `fehler.html` als `.fehler-seite`
  (Fehler-Nr. in Monospace, Aktionen als Knopfreihe).
- **Umschalter** `.darstellung-wahl`: Segment-Gruppe auf `--flaeche-abgesetzt`,
  aktiver Chip `--akzent`/`--akzent-text`; **Zurück-Knopf** `.zurueck-knopf`:
  Pille mit Kontur auf `--flaeche-karte`, Hover Akzent.
- **Angebots-Editor**: Kopfkarte, Blocküberschriften `.gruppentitel`
  (Kapitälchen mit Akzentbalken), sticky `.aktionsleiste-unten`
  (halbtransparente Karte + Kontur), Positionszeilen mit Drag-Griff
  (`--text-dezent`, Hover Akzent). **Mobile Erfassung**: Fortschritt
  (`--linie`/`--akzent`), Frage-Karten, Wahl-Chips (`.wahl span`, gewählt
  `--akzent`), sticky Weiter-Leiste, Einschätzung als große Buttons – bei
  390 px in beiden Modi geprüft. **Anmeldeseite** (`login_v27.css`): Karte
  `--flaeche-karte`, Titel `--text-titel`, Knopf `--akzent`; Energiehaus-Foto bleibt.

Screenshots vorher/nachher (beide Modi): `docs/design-v30/<seite>-<praefix>-<modus>.png`
(`scripts/design_screenshots.py`). Prototypen `docs/projektierung-prototyp.html`
und `docs/leadmanagement-prototyp.html` bleiben Layout-Vorlagen; für Farben
gilt dieser Abschnitt.

## Design-Tokens bis v29 (v14, CSS-Variablen in `:root` – als Alias erhalten)

| Token | Wert (Hell) | Bedeutung |
|---|---|---|
| `--friondo-blau` | `#3376b6` (v14: `#3f86c6`) | Primärblau aus dem Logo (Buttons, Links, Akzente) – jetzt Alias auf `--akzent` |
| `--friondo-blau-dunkel` | `#326ea5` | Hover-Zustand des Primärblaus – Alias auf `--akzent-hover` |
| `--friondo-blau-hell` | `#eaf2fa` | Tint für Hover-Flächen/aktive Zeilen – Alias auf `--akzent-flaeche` |
| `--friondo-dunkel` | `#1b2a5e` | Dunkelblau: Überschriften – Alias auf `--text-titel` (Kopfzeile → `--flaeche-erhoeht`) |
| `--g-50 … --g-700`, `--text` | Grauskala | Flächen, Linien, Sekundärtext (je Modus) |
| `--status-gruen(-bg)` | `#2e7d32` | Angenommen, Erledigt, DB grün |
| `--status-orange(-bg)` | `#9e5305` (v14: `#b45f06`) | Versand vorbereitet, Warnungen, EP |
| `--status-rot(-bg)` | `#c0392b` | Abgelehnt, fällig, Fehler, DB rot |
| `--status-blau(-bg)` | `#2c6cb0` | Versendet, Neu/In Bearbeitung |
| `--status-grau(-bg)` | `#566376` (v14: `#64748b`) | Entwurf, Überholt |
| `--status-violett(-bg)` | `#6b3fa0` | Individuell, TAIFUN |
| `--a-1 … --a-6` | 0.25–2 rem | Abstände-Skala |
| `--r-s/-m/-l` | 6/10/14 px | Eckenradien (+ `--r-xl` 18 px seit v30) |
| `--schatten-1/-2` | – | Karten- bzw. Overlay-Schatten |
| `--schrift`, `--t-xs … --t-xl` | Segoe UI/System | Schriftstack + Größenhierarchie (+ `--t-xxl` seit v30) |

Regel: **Farben nie hart in Templates** – immer Token oder Komponente.

## Komponenten (Auszug, Klasse → Zweck)

- **Buttons `.knopf`**: primär (Standard), `.zweitrangig`, `.gefaehrlich`,
  `.ghost`, `.klein`, `.gross` (mobil), `.symbol` (kompakter Icon-Button
  für Listen-Aktionen, Beschriftung über `title`).
- **Status-Badges `.abzeichen.status-*`**: EIN Farbschema für alle
  Status; immer über das Makro `status_badge(status)` aus
  `_komponenten.html` rendern (mappt auch Erfassungs-Status und
  Sonderfälle wie „Erledigt (extern)"); seit v30 gefüllte Pille mit Punkt.
- **Status-Schrittleiste `.statuskette`**: Mini-Pipeline eines Angebots
  (Makro `statuskette(status)`); „Überholt" komplett ausgegraut,
  „Abgelehnt" rot.
- **Sparten-Chips `.chip.chip-wp/…`**: aus v9 (erfasst = gefüllt, offen =
  umrandet, ausgeblendet = durchgestrichen), Farben seit v30 über `--sparte-*`.
- **Avatare `.avatar`**: Makro `avatar(name, id)` (seit v30).
- **Ampeln**: Hot-Ampel als Emoji (🔥/🌤/❄, etabliert), Planungs-/
  DB-Ampeln über `.ampel-punkt` bzw. `.db-gruen/-orange/-rot`.
- **Karten**: `.karte` (generisch), `.kachel` (+`.stat` mit
  `.stat-zahl`), `.portal-karte`, `.angebot-karte` (Vorgangsakte),
  `.akte-kopfkarte`, `.editor-kopfkarte`.
- **Tabellen `.tabelle`**: Zeilenlinie + Hover (Zebra entfällt seit v30),
  Sticky-Kopfzeile, Beträge in `.rechts` (tabellarische Ziffern); Summenzeile
  über `tr.summenzeile`; unter 1180 px scrollt die Tabelle intern.
- **Filterleiste `.suchleiste`**: Karte, Suchfeld + Selects im
  Chip-Stil (Formularnamen unverändert).
- **Formulare `.formular`**: Labels über den Feldern, Fokusring in
  `--fokus`, Fehler über `.feld-fehler`/`.fehlertext`.
- **Hinweis-Boxen**: `.meldung` (Erfolg) / `.meldung.fehler`,
  `.warnblock` (Warnung/fachlicher Hinweis) / `.warnblock.fehlerblock`,
  `.hinweis` (Info).
- **Leerzustände `.leer-zustand`**: Makro `leer_zustand(text, url,
  aktionstext)`.
- **Wiedervorlage-Chip `.wv-chip`**: Makro `wiedervorlage_chip(datum,
  heute)` – rot = fällig, blau = geplant.
- **Notizen-Chat `.notizen-chat`**: `.notiz` (fremde, links),
  `.notiz.eigene` (rechts, akzentgetönt), `.notiz.systemnotiz`.
- **Sticky-Leisten**: `.aktionsleiste-unten` (Editor),
  `.mobil-aktionen.sticky-fuss` (Erfassung).
- **Fortschritt (Erfassung)**: `.erfassung-fortschritt` („Seite x von
  y" + Balken).
- **Tabs `.tab-leiste .tab`**: Unterstreichungs-Stil.
- **Demo-Badges**: `.demo-badge`/`.coming-soon`/`.pj-dbadge` –
  einheitlich orange.
- **Umschalter/Zurück (v30)**: `.darstellung-wahl` (Menü), `.zurueck-leiste`/`.zurueck-knopf`.

## Icons

`_symbole.html` → Makro `symbol(name)`: schlanke Lucide-Auswahl als
Inline-SVG (`stroke: currentColor`, Größe 1.05em über `.symbol-svg`).
Verfügbar: suche, filter, plus, stift, pdf, haken, warnung, brief, uhr,
wiedervorlage, oeffnen, kopie, loeschen, muell, telefon, notiz, nutzer,
ort, euro, … sowie seit v30 pfeil-links, sonne, mond, geraet. Emojis bleiben
nur, wo etabliert (Hot-Ampel 🔥/🌤/❄, Glocke 🔔, Kamera in der Montage).

## Leitplanken

- Reines Frontend: Templates, CSS, statische Assets – keine Routen-,
  Logik- oder Formularnamen-Änderungen.
- Rollen-/Rechteverhalten unverändert (AD nie EK/DB).
- Neue Module (Projektierung `pj-*`, Lead-Management `lm-*`) bauen auf den
  Tokens auf; Layout-Änderungen der Projektierung weiterhin zuerst im
  Prototyp `docs/projektierung-prototyp.html` – Farben nach Abschnitt „Design v2“.
