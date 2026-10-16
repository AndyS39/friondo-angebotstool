# Friondo Design-System (v14, PLAN_V12 · Design v2 ab v30, PLAN_V18 · Design v3 Lead-Modul ab v37, PLAN_LEAD_V7)

Ein zentrales Stylesheet (`app/static/style.css`), keine externen CDNs
oder Webfonts – das Tool funktioniert vollständig ohne Internet. Das
Angebots-PDF (und alle anderen fpdf2-PDFs) sind davon unberührt.
Seit v37 trägt **nur das Lead-Modul** das Design v3 (Abschnitt unten);
Angebotstool, Projektierung, Vorgangsakte, Kopfzeile und der zentrale
Kalender bleiben beim Design v2.

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
- **v31 Lead-Management V5:** Badge **Großkunde** `.abzeichen.lm-grosskunde` (Fläche/Kontur
  aus `color-mix` der Variable `--f`, Standard `--status-violett`; Farbe aus Parameter
  `grosskunde_farbe` per `style="--f: …"`); Kartei V5 `.lk-v5` (Raster `.lk-oben` Notizen 2/3
  neben To-Dos 1/3, Objekt-Karten `.lk-objekt` auf `--flaeche-abgesetzt`, Hauptobjekt mit
  `--akzent`-Kontur, Statuskette klickbar `.lk-schritt.setzbar`), Archiv-Banner
  `.lm-archiv-banner` (Klasse `.meldung`), Zweit-Scrollleiste `.lm-scrollleiste` (sticky
  bottom unter `.lm-tabellen`), Herkunfts-Badge in Timeline/Notizen-Chat
  `.abzeichen.nc-herkunft` (Lead · Angebot · Projekt), Testphase-Sperre
  `a.lmt-gesperrt[aria-disabled="true"]` (ausgegraut, Tooltip), Mailstatus
  `.lm-mailstatus-gesperrt`. Regeln in `lead_v2.css` (nur Tokens).
- **Kartenliste „Mein Tag“** (v32, `app/static/mein_tag.css`, Präfix `mt-`): `main.mein-tag-seite`
  (max. 720 px zentriert, < 600 px Vollbreite, Safe-Area-Abstände), `.mt-block` mit `h2` + Zähler
  `.mt-zahl` (`.rot` bei fälligen), `.mt-karte` (Fläche `--flaeche-karte`, Kontur `--linie`, Radius
  `--r-l`, `.mt-ueberfaellig` = rote linke Kante), Zeile 1 `.mt-zeile1` (Datum/Uhrzeit
  `.mt-datum-zeit`/`.mt-uhr`, Labels `.mt-label`/`.mt-label-rot`, Badges rechts `.mt-badges` mit
  Sparten-Chips und `.mt-herkunft`), `.mt-name`, `.mt-adresse`/`.mt-tel` (44 px Zeilenhöhe),
  Aktionen `.mt-aktionen` mit Hauptknopf `.knopf.mt-haupt` (unter 600 px volle Breite) und
  Zweitlink `.mt-akte`; Anruf-Karte mit Hot-Ampel-Punkt `.mt-ampel-heiss|warm|kalt|leer`, Chip
  `.mt-chip-orange|rot`, `.mt-aktivitaeten` (details), `.mt-notiz`; Umschalter `.mt-umschalter`
  (Karten | Tabelle); Filter als `details.karte.mt-filter`. Nur Tokens; Leerzustände `leer_zustand`.
- **Verfolgungs-Chip `.verfolgung-chip.vf-<status>`** (v32, `static/verfolgung.css`): Makro
  `verfolgung_chip(status, klein=False, vorgang_id=None)` – fünf Stufen versendet (blau) ·
  nachgefasst (grau) · bestellung_angekuendigt (orange) · angenommen (grün) · abgelehnt (rot)
  aus den Status-Token-Paaren; `klein` für Listen; `vorgang_id` setzt `data-verfolgung-chip`,
  damit `verfolgung.js` den Chip nach dem Dialog „Nächster Schritt“ ohne Neuladen aktualisiert.
  Dialog-Bausteine `.ns-dialog` (Knöpfe `.ns-rot/.ns-gruen/.ns-blau` ≥ 44 px, Chips `.ns-chip`
  mit `:has(:checked)`, Bestätigungszeile `.ns-bestaetigung`); display-Regeln mit
  `[hidden]`-Gegenregel.
- **v32 Kundensuche** (`suche.css`): Suchfeld `.kopf-suche` in der Kopfzeile (Text
  `--text-invers` auf getönter Fläche), Vorschlagsliste `.kopf-suche-liste` als Karte
  (`--flaeche-karte`, `--linie`, `--schatten-2`), Treffer `.kopf-suche-treffer` mit
  Interesse-Badges und Verfolgungs-Chip `.kopf-suche-chip` (`--akzent-flaeche`/`--akzent-text`);
  unter 600 px Lupe `.kopf-suche-lupe`, Feld klappt in voller Breite aus (`.kopf-suche.offen`).
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

## Design v3 (Lead-Modul, v37, PLAN_LEAD_V7 Phasen 196/197)

Vorlage ist der claude.ai-Export „Friondo Tool Design.html“ (Claudia Castro, vier
Boards: Dashboard Desktop · Lead Detail Übersicht · Termine · Anrufe). Die Datei lag
bei der Umsetzung **nicht** vor – die Tokens tragen die Startwerte aus PLAN_LEAD_V7
(Abweichungen der Vorlage gewinnen, sobald sie unter `docs/design-v37/vorlage/` liegt).
Übernommen wird **nur die Optik** (Schrift, Größen, Farben, Rundungen, Kacheln,
Abstände), keine Inhalte; Aufbau, Routen, Formularnamen und Rollenregeln der Lead-Seiten
sind unverändert (v31–v35).

**Geltungsbereich – der Wrapper:** `base.html` setzt `<body data-modul="lead">` für alle
Seiten unter `/lead-management` und `/parametrierung/lead-*` (Lead-Einstellungen,
Lead-Routing, Quellen, Steuerdatei); eine Seite kann sich mit `{% set lead_modul = true %}`
zusätzlich anmelden. Alles andere – Angebotstool, Projektierung, Vorgangsakte, Leads VOT /
Mein Tag, der zentrale `/kalender`, die Angebotstool-Tabellen im Lead-Board-Layout (v33) –
bleibt Design v2.

**Mechanik:** Am Wrapper überschreibt `lead_v2.css` (Block „Design v3“, Token-Marker
`/* v3-tokens-anfang */ … /* v3-tokens-ende */`) die semantischen v2-Tokens (`--flaeche*`,
`--linie*`, `--text*`, `--akzent*`, `--link`, `--fokus`, `--status-orange(-bg)`, `--g-*`,
`--r-*`, `--schatten-*`) und deklariert die Aliase (`--friondo-*`, `--grau-*`,
`--lm-aktiv-*`) neu – Alias-Tokens werden am deklarierenden Element berechnet, am `:root`
würden sie sonst die v2-Werte behalten. Damit folgen alle Lead-Regeln (v23–v37) ohne
Umschreiben dem neuen Design. Typografie-Tokens (`--schrift`, `--t-*`) liegen auf
`[data-modul="lead"] main`, die Kopfzeile behält Schrift, Größe und Farbe der v2
(`--flaeche-erhoeht`, `--text-invers` werden nicht überschrieben; `theme-color` bleibt).
Dunkelmodus: `:root[data-theme="dunkel"] [data-modul="lead"]` und
`@media (prefers-color-scheme: dark) { :root:not([data-theme="hell"]) [data-modul="lead"] }`
mit identischen Werten (Wächter `tests/test_v30_design.py::TokenBloeckeV3`), Umschalter und
Speicherung je Benutzer aus v30 unverändert. Hex-Werte in `lead_v2.css` sind nur zwischen
den Markern erlaubt (Wächter blendet den Block aus).

### Tokens Design v3 (Hell / Dunkel – Dunkel abgeleitet [ANNAHME])

| Token | Hell | Dunkel | Zweck |
|---|---|---|---|
| `--flaeche` | `#f6f8fa` | `#0f1a26` | Seite |
| `--flaeche-karte` | `#ffffff` | `#16243a` | Karten, Tabellen, Dialoge |
| `--flaeche-hover` | `#eef1f5` | `#1e2f48` | Zeilen-Hover |
| `--flaeche-abgesetzt` | `#ecf0f5` | `#1b2a40` | Tabellenkopf, Gruppenköpfe, Kästen |
| `--lm3-feld` | `#eef1f5` | `#1b2a40` | Eingabefelder (Fokus → Karte + Akzentrand) |
| `--linie` / `--linie-stark` | `#dce4eb` / `#c8d2dd` | `#2a3b52` / `#3a4d68` | Rahmen / Feldränder |
| `--text` / `--text-titel` | `#0e2338` | `#e8eef5` | Text, Überschriften |
| `--lm3-text-zweit` (`--g-700`) | `#33414f` | `#c9d4e2` | Zweittext |
| `--text-dezent` (`--g-500`) | `#687186` | `#9aa8ba` | gedämpft (≥ 4,5 : 1 auf Karte) |
| `--akzent` / `--akzent-hover` | `#2f72b5` / `#245c95` | unverändert | Primärblau: Knöpfe, aktive Kachel der Icon-Leiste, Reiter, Chips |
| `--akzent-text` | `#ffffff` | `#ffffff` | Text auf Primärblau (5,0 : 1) |
| `--akzent-flaeche` | `#e3edf7` | `#1c3450` | Hintergrund-Blau (Tint) |
| `--lm3-akzent-auf-flaeche` | `#245c95` | `#8db4de` | Akzent-Text auf dem Tint (Zähler, Phasen „fertig“) |
| `--lm3-akzent-hell` / `--lm3-akzent-linie` | `#4489c9` / `#8db4de` | unverändert | helles Blau (Balken, Symbole) / dekorative Akzentlinie (nie für Text) |
| `--link` / `--fokus` | `#2f72b5` | `#8db4de` / `#4489c9` | Textlinks / Fokusring |
| `--lm3-orange` + `--lm3-orange-text-auf` | `#ffa500` + `#0e2338` | unverändert | Pille „IDEAL“, Vorschlagsrahmen (dunkler Text, 8,1 : 1) |
| `--lm3-orange-text` / `--lm3-orange-flaeche` (= `--status-orange(-bg)`) | `#a85400` / `#fff1d6` | `#ffc266` / `#3a2a0e` | Hinweis/Warnung, Testphase-Kästen |
| `--sparte-pvv` (global am `:root`) | `#1f7a72` | `#6fd6c8` | Badge „PV vorhanden“ (Merkmal, v37 Phase 199) |
| `--r-s` / `--r-m` / `--r-l` / `--r-xl` / `--lm3-r-kachel` | 8 / 12 / 14 / 20 / 18 px | – | Knöpfe+Felder / Karten / große Karten+Dialoge / große Kacheln / Dashboard-Kacheln; Chips/Pills 999 px, Avatare 50 % |
| `--schatten-1` / `--schatten-2` | `0 1px 4px rgba(0,0,0,.08)` / `0 8px 24px rgba(0,0,0,.12)` | Kontur `#2a3b52` / `#3a4d68` + Tiefe | Karten / Overlays |
| `--lm3-schrift` (`--schrift` auf `main`) | `"Inter", "Open Sans", system-ui, -apple-system, "Segoe UI", Roboto, sans-serif` | – | Inter liegt nicht lokal vor (kein Netz, keine lizenzfreie Datei) – Rückfall auf die Systemschrift [ANNAHME]; eine lokale woff2 unter `static/fonts/` braucht nur ein `@font-face` im v3-Block |
| `--t-xs` / `--t-s` / `--t-m` / `--t-l` / `--lm3-t-h2` / `--t-xl` / `--t-xxl` / `--lm3-t-klein` / `--lm3-t-kennzahl` | 12 / 13 / 14 / 16 / 18 / 22 / 32 / 11 / 32 px | – | Nebentext / Nebentext / Grundgröße / Überschrift klein / Karten-Überschrift / Seitentitel / Kennzahl / Kleintext (Tabellenkopf, Pillen) / Dashboard-Kennzahl (800) |

Status- und Kanalfarben bleiben Daten (Blatt Status, Tabelle `vertriebskanaele`, Parameter
`grosskunde_farbe`) und kommen weiter als `--f` im `style`-Attribut; Sparten-Chips WP/PV/KL/WB
behalten ihre v2-Tokens. Abstände = v2-Skala `--a-2 … --a-6` (8/12/16/24/32 px).

### Bausteine Design v3 (Regeln im Block „Phase 197“ von `lead_v2.css`)

- **Dashboard:** Kennzahl-Kacheln `.lm-dash-kacheln-v4 .kachel.stat` – drei Spalten ab 1200 px,
  Rundung 18 px, Kennzahl 32 px/800 oben links, Beschriftung darunter, Farbbalken links bleibt
  (rot bei dringend). Karten `.lm-karte` 14 px.
- **Boards (Hauptboard, Deals, Infoabend, Handelsvertreter, Kontaktiert, Anrufliste):**
  Filterleiste `.lm-filterblock .lm-suchleiste` als Karte (12 px, Kontur, Schatten), Suchfeld auf
  `--lm3-feld`, Selects/Filter-Chips/Umschalter als Pills (999 px, 32 px hoch, aktiv Primärblau),
  Tabellenzeilen 40 px (`td { height: 40px }`), Kopfzeile 11 px Kapitälchen auf
  `--flaeche-abgesetzt`, Status-/Kanal-Pillen 11 px.
- **Kundenkartei:** Kopfkarte 14 px mit Avatar (Ring `--akzent-flaeche`), Phasen-Pills
  `.lk-schritt` (aktiv Primärblau), runde Aktions-Icons `.lk-rund` 42 px; Reiter Anruf · E-Mail ·
  Timeline als Pill-Leiste (`.lk-reiter` auf `--flaeche-abgesetzt`, aktiver Tab Primärblau);
  Anruf-Block mit großen Ergebnis-Buttons (Raster, ≥ 44 px, 14 px); Termine-Block mit
  Vorschlagskarten `.lk-vorschlag` und „IDEAL“-Pille in Orange (`.lmt-ideal-badge`, Rahmen
  `--lm3-orange`), ebenso im Terminassistenten (`.lmt-vorschlag.lmt-ideal`) und in der
  Kalenderansicht; Eingabefelder auf `--lm3-feld` mit 8 px.
- **Notizblock der Kartei (Phase 196):** `.lk-v5 .lk-notizen .nc-eingabe` ist ein Raster –
  Textfeld über die volle Spaltenbreite (mindestens 3 Zeilen, wächst mit dem Makro-JS), rechts
  eine Spalte mit „Senden“ über „Diktieren“ und dem Diktat-Hinweis klein darunter; unter 900 px
  Feld oben, Knöpfe nebeneinander. Das Makro `notizen_chat` bleibt für Vorgangsakte, Projektakte
  und Montage unverändert. Kopfzeile ohne Badge „monday“ und ohne SLA-Chip (Quelle steht in der
  Eingangszeile „Eingang … (monday)“, im Kundeninfo-Block und in der Timeline; SLA in
  Anrufliste/Statistik).
- **Icon-Leiste:** aktive Kachel Primärblau mit weißem Text ohne Innenkontur, Hover
  `--akzent-flaeche`.

### Regeln für neue Lead-Seiten

- **Nur v3-Tokens** – keine Hex-/rgb()-Werte außerhalb des Token-Blocks; neue Farbtokens immer
  in Hell-, Dunkel- und Geräte-Block (identische Dunkelwerte), neue Textpaare in
  `TOKEN_PAARE_V3_TEXT/_DEZENT` (`tests/test_v30_design.py`) eintragen (≥ 4,5 : 1 bzw. ≥ 3 : 1).
- Neue Lead-Seiten liegen unter `/lead-management` (Wrapper automatisch) oder melden sich mit
  `{% set lead_modul = true %}` an; sie nutzen die bestehenden Bausteine (`.karte`, `.lm-karte`,
  `.knopf`, `.lm-filterblock`, `.lm-tabelle`, `.abzeichen`) – Rundungen und Schatten kommen aus
  den Tokens.
- Angebotstool-Tabellen im Lead-Board-Layout (`/angebote`, `/erfassungen`, `/kunden`, `/leads`,
  Meine Angebote) bleiben v2 – keine Lead-Wrapper-Regel dorthin tragen.
- Beide Modi prüfen: `scripts/design_screenshots.py nachher --modus hell|dunkel --ziel
  docs/design-v37` (Seiten `lead-dashboard, hauptboard, deals, infoabend, handelsvertreter,
  kontaktiert, anrufliste, kartei, termin, karte-lead, todos, vorlagen, kalender-lead-alt,
  kanaele, taifun-uebergaben, lead-einstellungen, lead-routing, kartei-mobil, hauptboard-mobil,
  lead-dashboard-mobil`); die Instanz läuft mit `--lifespan off`, Chrome löst nur `127.0.0.1`
  auf (keine Netzaufrufe). Nur Demo-Daten im Bild (DB-Kopie vorher mit
  `diagnose/v31/anonymisieren.py` + `diagnose/v37/L1_patches/anonym_rest.py` anonymisieren).

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

## Kalender (v33, PLAN_V20 Phase 169)

`app/static/kalender_zentral.css` (Klassen `.kz-*`): Art-Farbe je Eintrag als Token `--kz-f` – VOT
`--status-blau`, Telefon `--status-gruen`, Online `--status-violett`, Sperrzeit `--status-grau`, Montage
`--pj-wp`, Elektro `--pj-kl`, Sub `--pj-pv`, Feinplanung `--pj-info`, Abnahme `--pj-wb`, Sonstiges
`--pj-muted`, Service `--status-orange`, Abwesenheit `--status-grau-bg`; Schraffuren (Outlook-belegt,
Sperrzeit) aus `--linie`/`--flaeche-abgesetzt`; Einträge `color-mix(in srgb, var(--kz-f) 18 %,
var(--flaeche-karte))`. Hell und Dunkel ausschließlich über die Tokens aus `style.css`; keine Farbliterale
(Token-Wächter `tests/test_v30_design.py`). Unter 600 px Tagesansicht, Zeilenköpfe sticky.

**Rollen-Seite (v33, Phase 167):** nutzt nur bestehende Klassen (`tabelle`, `karte formular`, `abzeichen
status-*`, `kontrollfeld`); Badge „Simons Gruppe (noch nicht verteilt)“ = `abzeichen status-versand-vorbereitet`
(Orange-Token), kein neues CSS.

## Tabellen mit Spalten je Nutzer (v33, PLAN_V20 Phase 174)

Aufbau jeder Angebotstool-Tabelle: `div.lm-filterblock` (sticky; Chip-Selects = `label.kontrollfeld > select`,
Filter-Chips = `label.lm-filterchip`, Suchfeld `data-lm-suche`, Spaltenwähler über das Makro `spaltenwahl`) →
`p#lm-meldung` → `div.lm-tabellen.lm-tabellen-at` (`table.tabelle.lm-tabelle` mit `spalten_colgroup` +
`spalten_kopf`, Zeilen `tr[data-zeile][data-suche]`, Zellen `td.sp-<key>` mit `data-wert` für Datum/Beträge,
Zweit-Scrollleiste `.lm-scrollleiste`) → `tabellen_daten(board, spalten, sortierung)`. Neue Spalten nur in
`lead_boards.KATALOGE` eintragen und die Zelle im Template-Makro `zelle` ergänzen; Rollenregel über
`lead_boards.INTERNE_SPALTEN` (EK/DB/DB-Ampel nie für Außendienst oder ohne Kalkulationssicht). Alles über
Tokens, CSS-Block „v33“ in `lead_v2.css`.

## Mein Tag mobil (v33, PLAN_V20 Phase 173)

- Mobile Bausteine (Block „Mein Tag“ in `static/mein_tag.css`): Hero-Karte `.mt-naechstes`
  (`--flaeche-erhoeht` + `--text-invers`, Akzent-Knopf `.mt-route` = `--akzent`/`--akzent-text`, runde
  Nebenknöpfe `.mt-rund` aus `color-mix(--text-invers 14 %)`), Zeitstrahl `.mt-zeitstrahl`/`.mt-punkt`
  (Linie `--linie`, Punkte `--status-gruen`/`--status-orange`/leer `--linie-stark`), Prioritäts-Badge
  `.mt-prio` mit drei Balken in `--status-rot/-orange/-grau` (+ `-bg`), Chips `.mt-chip` (aktiv =
  `--akzent`), Segment `.mt-segment` (`--flaeche-abgesetzt`, aktiv `--flaeche-karte` + `--schatten-1`),
  Datumskachel `.mt-datumskachel`, untere Leiste `.mt-leiste` (fixed, `--flaeche-karte`, aktiv `--akzent`
  auf `--akzent-flaeche`, Safe-Area). Regel: Mobile Leisten/Karten nur unter 600 px (`@media
  (max-width: 600px)`), beide Modi über Tokens – keine `fest:`-Ausnahmen nötig.

## Nachfassen (v33, PLAN_V20 Phase 176)

Bausteine in `static/verfolgung.css` (nur Tokens): Makro `verfolgung_chip(status, klein, vorgang_id, versuche)`
(„Nachgefasst (2)“), `.inaktiv-kennzeichen` (rote Pille, Variante `klein`), Kopfzeile `.ns-kopf` /
`.ns-letzter-einwand` (orange Pille), Block `.ns-mail` (Vorlage, Vorschau, PDF-Häkchen, Senden).
