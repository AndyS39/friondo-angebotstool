# Friondo Design-System (v14, PLAN_V12)

Ein zentrales Stylesheet (`app/static/style.css`), keine externen CDNs
oder Webfonts – das Tool funktioniert vollständig ohne Internet. Das
Angebots-PDF ist davon unberührt.

## Design-Tokens (CSS-Variablen in `:root`)

| Token | Wert | Bedeutung |
|---|---|---|
| `--friondo-blau` | `#3f86c6` | Primärblau aus dem Logo (Buttons, Links, Akzente) |
| `--friondo-blau-dunkel` | `#326ea5` | Hover-Zustand des Primärblaus |
| `--friondo-blau-hell` | `#eaf2fa` | Tint für Hover-Flächen/aktive Zeilen |
| `--friondo-dunkel` | `#1b2a5e` | Dunkelblau der Kopfzeile, Überschriften |
| `--g-50 … --g-700`, `--text` | Grauskala | Flächen, Linien, Sekundärtext |
| `--status-gruen(-bg)` | `#2e7d32` | Angenommen, Erledigt, DB grün |
| `--status-orange(-bg)` | `#b45f06` | Versand vorbereitet, Warnungen, EP |
| `--status-rot(-bg)` | `#c0392b` | Abgelehnt, fällig, Fehler, DB rot |
| `--status-blau(-bg)` | `#2c6cb0` | Versendet, Neu/In Bearbeitung |
| `--status-grau(-bg)` | `#64748b` | Entwurf, Überholt |
| `--status-violett(-bg)` | `#6b3fa0` | Individuell, TAIFUN |
| `--a-1 … --a-6` | 0.25–2 rem | Abstände-Skala |
| `--r-s/-m/-l` | 6/10/14 px | Eckenradien |
| `--schatten-1/-2` | – | Karten- bzw. Overlay-Schatten |
| `--schrift`, `--t-xs … --t-xl` | Segoe UI/System | Schriftstack + Größenhierarchie |

Regel: **Farben nie hart in Templates** – immer Token oder Komponente.

## Komponenten (Auszug, Klasse → Zweck)

- **Buttons `.knopf`**: primär (Standard), `.zweitrangig`, `.gefaehrlich`,
  `.ghost`, `.klein`, `.gross` (mobil), `.symbol` (kompakter Icon-Button
  für Listen-Aktionen, Beschriftung über `title`).
- **Status-Badges `.abzeichen.status-*`**: EIN Farbschema für alle
  Status; immer über das Makro `status_badge(status)` aus
  `_komponenten.html` rendern (mappt auch Erfassungs-Status und
  Sonderfälle wie „Erledigt (extern)").
- **Status-Schrittleiste `.statuskette`**: Mini-Pipeline eines Angebots
  (Makro `statuskette(status)`); „Überholt" komplett ausgegraut,
  „Abgelehnt" rot.
- **Sparten-Chips `.chip.chip-wp/…`**: unverändert aus v9 (erfasst =
  gefüllt, offen = umrandet, ausgeblendet = durchgestrichen).
- **Ampeln**: Hot-Ampel als Emoji (🔥/🌤/❄, etabliert), Planungs-/
  DB-Ampeln über `.ampel-punkt` bzw. `.db-gruen/-orange/-rot`.
- **Karten**: `.karte` (generisch), `.kachel` (+`.stat` mit
  `.stat-zahl`), `.portal-karte`, `.angebot-karte` (Vorgangsakte),
  `.akte-kopfkarte`, `.editor-kopfkarte`.
- **Tabellen `.tabelle`**: Zebra, Zeilen-Hover, Sticky-Kopfzeile,
  Beträge in `.rechts` (tabellarische Ziffern); Summenzeile über
  `tr.summenzeile`; unter 1180 px scrollt die Tabelle intern.
- **Filterleiste `.suchleiste`**: weiße Karte, Suchfeld + Selects im
  Chip-Stil (Formularnamen unverändert).
- **Formulare `.formular`**: Labels über den Feldern, blauer
  Fokusring, Fehler über `.feld-fehler`/`.fehlertext`.
- **Hinweis-Boxen**: `.meldung` (Erfolg) / `.meldung.fehler`,
  `.warnblock` (Warnung/fachlicher Hinweis) / `.warnblock.fehlerblock`,
  `.hinweis` (Info).
- **Leerzustände `.leer-zustand`**: Makro `leer_zustand(text, url,
  aktionstext)`.
- **Wiedervorlage-Chip `.wv-chip`**: Makro `wiedervorlage_chip(datum,
  heute)` – rot = fällig, blau = geplant.
- **Notizen-Chat `.notizen-chat`**: `.notiz` (fremde, links),
  `.notiz.eigene` (rechts, blau getönt), `.notiz.systemnotiz`.
- **Sticky-Leisten**: `.aktionsleiste-unten` (Editor),
  `.mobil-aktionen.sticky-fuss` (Erfassung).
- **Fortschritt (Erfassung)**: `.erfassung-fortschritt` („Seite x von
  y" + Balken).
- **Tabs `.tab-leiste .tab`**: Unterstreichungs-Stil.
- **Demo-Badges**: `.demo-badge`/`.coming-soon`/`.pj-dbadge` –
  einheitlich orange.

## Icons

`_symbole.html` → Makro `symbol(name)`: schlanke Lucide-Auswahl als
Inline-SVG (`stroke: currentColor`, Größe 1.05em über `.symbol-svg`).
Verfügbar: suche, filter, plus, stift, pdf, haken, warnung, brief, uhr,
wiedervorlage, oeffnen, kopie, loeschen, muell, telefon, notiz, nutzer,
ort, euro. Emojis bleiben nur, wo etabliert (Hot-Ampel 🔥/🌤/❄,
Glocke 🔔, Kamera in der Montage).

## Leitplanken

- Reines Frontend: Templates, CSS, statische Assets – keine Routen-,
  Logik- oder Formularnamen-Änderungen.
- Rollen-/Rechteverhalten unverändert (AD nie EK/DB).
- Neue Module (Projektierung `pj-*`, Lead-Management) bauen auf den
  Tokens auf; Layout-Änderungen der Projektierung weiterhin zuerst im
  Prototyp `docs/projektierung-prototyp.html`.
