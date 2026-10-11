# Umsetzungsplan v18 – Design v2 (Hell/Dunkel), Zurück-Navigation, BzA-/Lieferschein-Korrekturen, Zahlungsbedingungen, Projektierung Go-live

Voraussetzung: kein anderer Plan in Umsetzung (strangübergreifend). Stand
11.10.2026: v27-Nachtrag 2 + v28 + v29 (Commit 2d86a78 / 9a08d3b) sind gepusht
und laufen seit dem Rollout auf dem Server; Claude Code ist frei. CLAUDE.md und
`konfigurator_logik_v5.xlsx` sind Live-Master im Projektordner
`C:\Users\a.scheelen\Tools\Angebotstool` (Git-Arbeitskopie). ALLE PHASEN DIESES
PLANS IN EINEM DURCHLAUF UMSETZEN (Reihenfolge einhalten, jede Checkbox nach
Umsetzung und Test abhaken, am Ende Gesamtübersicht mit Testergebnissen und
offenen Punkten, fachliche Rückfragen gebündelt). **Ein gemeinsamer Commit am
Ende des Durchlaufs** (Arbeitsweise seit v28/v29), migrate.py idempotent, **nur
additive Migrationen** (v29-Code muss auf der v30-Datenbank weiterlaufen,
Rückweg `rollback.bat --nur-code`). **Kein git push vor Freigabe.**

CLAUDE-Abschnitt: **„Neu in v30“**. Phasen **145 bis 152** (Zuordnungstabelle:
v29 = PLAN_LEAD_V4 belegt 140–144). Vor dem Bau einmal gegen die Tabelle
prüfen; bei Abweichung die nächsten freien Nummern nehmen und durchgängig
ersetzen. Die v27-Regeln gelten (`def`-Routen, keine offene Datenbanksitzung
während Netz-I/O, Scheduler-Rahmen, Wächter-Test `tests/test_v27_sitzungen.py`
grün, `docs/betrieb.md` fortschreiben, wenn ein Punkt den Betrieb berührt).

Geltungsbereich: Angebotstool (BzA-Datenblatt, Lieferschein, Editor,
Nachtexte, Duplizieren) sowie zwei querschnittliche Punkte für ALLE Module –
Design v2 mit Hell/Dunkel (wie das Design-Update v14, PLAN_V12) und die
Zurück-Navigation – und als abgegrenzte Phase 151 der Go-live der
Projektierung (Projekt löschen, Demo-Daten raus; Entscheidung Andreas
11.10.2026, hier mitgeplant, damit es ein Durchlauf bleibt). Angebots-PDF,
Protokoll-PDF, Wirtschaftlichkeits-Seiten, Lead-Logik, monday-Sync und
Rückspielung bleiben fachlich unverändert; die PDFs ändern sich nur, wo
Phase 148/149/150 es sagen.

## Entscheidungen (Chat Angebotstool, 11.10.2026, Andreas)

- **Design v2 nach Vorlage:** Die Oberfläche bekommt den Stil der beiden
  Screenshots (Portal und Hauptboard, dunkel): ruhige dunkle Flächen, Karten
  mit feiner Kontur, farbige Chips und Avatare, große Kennzahlen, gleichmäßige
  Abstände. Vorlage ist der **HTML-Prototyp von Andreas** (liegt in
  `docs\design-v30\vorlage\`, zusammen mit den Screenshots
  `portal-dunkel.png` und `hauptboard-dunkel.png`). **Nur die Optik** wird
  übernommen – Aufbau und Inhalte der Seiten (Startseite mit drei Bereichen,
  Hauptmenü oben, Lead-Icon-Leiste, Kacheln, Listen) bleiben wie heute; die
  Prototyp-Elemente „Jetzt dran“, Suche oben, Icon-Leiste für alle Module,
  „441 Hinweise“ werden **nicht** nachgebaut.
- **Hell und Dunkel wählbar**, Standard = **Gerät entscheidet**
  (`prefers-color-scheme`); jeder Benutzer kann im Menü dauerhaft Hell oder
  Dunkel wählen (je Benutzer gespeichert). Der Hellmodus bleibt in der heutigen
  Friondo-CI (Friondo-Blau, Dunkelblau), der Dunkelmodus folgt der Vorlage.
- **Zurück-Button** auf allen Detail- und Bearbeitungsseiten: springt genau
  **eine Ansicht zurück** (nicht zur Startseite), damit man nach einem Abstecher
  wieder dort landet, wo man gearbeitet hat.
- **BzA-Datenblatt:** Frage A20 „Nennleistung der bestehenden Heizung“ ist keine
  Pflichtangabe – sie wird aus dem Bogen und aus dem Datenblatt entfernt. Die
  „Nennwärmeleistung“ wird nur als Zahl eingegeben, „kW“ hängt das Tool an.
  Neue Zeile **„Geplante förderfähige Kosten inkl. 10 % Puffer“** (Friondo
  trägt bei der KfW zur Sicherheit immer 10 % auf die Auftragssumme ein, falls
  der Kunde später einen Ergänzungskredit will; am Auftrag ändert das nichts).
  **Abschnitt 6 „Ersteller“ entfällt** vollständig [ANNAHME: „Punkt 6“ =
  Abschnitt 6 des Datenblatts].
- **Lieferschein:** Langtexte der Positionen erscheinen vollständig. Steht
  „Friondo fit for future“ (Pos. 014) auf EP, dürfen auch „Friondo HEMS“ (015),
  „Friondo iMSys“ (016) und „Friondo SpotDynamic“ (017) nicht auf dem
  Lieferschein erscheinen.
- **Fehler nach Überarbeiten + Duplizieren** (Fehler-Nr. F-20261002-073115-9c9e)
  wird über das Fehlerprotokoll aufgeklärt und behoben.
- **Zahlungsbedingungen** sind je Angebot wählbar (z. B. „50 % Anzahlung am Tag
  der Montage“, „80 % Anzahlung und 2 % Skonto“), der Nachtext passt sich an;
  die Texte pflegt der Innendienst in der Parametrierung.
- **Projektierung geht live:** Vorher braucht es **„Projekt löschen“ (nur
  Admin)**, damit Demo- und Testprojekte verschwinden; die Umstellung
  `freigabe_modus = alle` macht Andreas nach dem Rollout in der Parametrierung
  (Anleitung in docs/nach-dem-update-v30.md). Lead-Management bleibt im
  Demo-Modus.

## Phase 145 – Design v2: Tokens, Hell/Dunkel, Umschalter (Fundament)

- [x] **Vorlage auswerten:** alle `.html` in `docs\design-v30\vorlage\` und die
      beiden Screenshots lesen; daraus eine Token-Tabelle „Vorlage → Token“
      ableiten (Flächen, Karten, Linien, Text, Akzent, Status, Radien,
      Schatten, Abstände, Schriftgrößen) und als Abschnitt „Design v2“ in
      `docs/design-system.md` festhalten (mit Hex-Werten je Modus). Schrift:
      die Schrift der Vorlage nur, wenn sie als OFL-Datei lokal abgelegt werden
      darf (wie Poppins unter `app/static/pdf/fonts`), sonst bleibt die
      Systemschrift; Zahlen in Tabellen und Kacheln mit
      `font-variant-numeric: tabular-nums` statt Monospace [ANNAHME]. Keine
      externen CDNs/Webfonts (Regel v14).
- [x] **Semantische Tokens** in `style.css` `:root` ergänzen (bestehende Tokens
      bleiben als Alias erhalten): `--flaeche` (Seitenhintergrund),
      `--flaeche-karte`, `--flaeche-erhoeht` (Kopfzeile/Menü), `--flaeche-hover`,
      `--linie`, `--linie-stark`, `--text`, `--text-dezent`, `--text-invers`,
      `--akzent`, `--akzent-text`, `--akzent-flaeche`, `--fokus`, dazu die
      Statusfarben als Paar Text/Fläche je Modus (`--status-*`/`--status-*-bg`
      wie heute, im Dunkelmodus abgedunkelte Flächen mit hellen Texten),
      `--schatten-1/2` je Modus (im Dunkelmodus Kontur statt Schatten),
      Kanal-/Quellen-Farben des Lead-Moduls (`--q-*`, `kanal_farben`) als Paar
      Hell/Dunkel. Zwei Definitionsblöcke: `:root` (Hell, heutige CI) und
      `:root[data-theme="dunkel"]`; zusätzlich `@media (prefers-color-scheme:
      dark) { :root:not([data-theme="hell"]) { … } }` mit denselben Werten.
- [x] **Alle festen Farbwerte auf Tokens umstellen:** `style.css` (387 Hex-
      Werte, Stand 11.10.), `lead_v2.css` (95), `akte_v28.css` (7),
      `projektierung_v28.css` (8), `login_v27.css` (6) sowie Inline-Farben in
      Templates (`style="…color…"`, `fill=`/`stroke=` in `_symbole.html` auf
      `currentColor`). Ausnahmen nur mit Kommentar `/* fest: … */` (z. B.
      Kanal-Badges mit gespeicherter Hex-Farbe aus `kanal_farben` – diese
      bekommen im Dunkelmodus einen helleren Text über
      `color-mix(in srgb, <farbe>, white 35 %)` oder eine feste Mindest-
      Helligkeit). Leaflet-Karte: Kacheln bleiben hell, Kartenrahmen und
      Popups folgen den Tokens [ANNAHME]. Wächter-Test (Phase 152) sucht nach
      neuen Hex-Werten außerhalb der Token-Blöcke.
- [x] **Umschalter:** im Benutzer-Menü der Kopfzeile (`base.html`, neben
      „Menü ☰“) ein Eintrag **„Darstellung: Gerät · Hell · Dunkel“** (drei
      Radio-Chips, Icon Sonne/Mond aus `_symbole.html`). Auswahl wird
      (a) sofort per JS auf `<html data-theme>` gesetzt, (b) in
      `benutzer_einstellungen` (Key `darstellung`, Werte `geraet` | `hell` |
      `dunkel`) per `POST /einstellungen/darstellung` (JSON, alle Rollen)
      gespeichert und (c) als Cookie `darstellung` (1 Jahr, `samesite=lax`)
      abgelegt, damit die Middleware sie **vor dem Rendern** in das `<html>`-Tag
      schreibt (kein Aufblitzen des falschen Modus); Login-Seite liest nur das
      Cookie. `<meta name="theme-color">` folgt dem Modus (Hell `#1b2a5e`,
      Dunkel = Flächenfarbe der Vorlage). Montage-Backend und mobile Erfassung
      haben denselben Umschalter in ihrer Kopfzeile.
- [x] **PDF unverändert:** `pdf_export`, `protokoll_pdf`, `lieferschein_pdf`,
      `bza_datenblatt`, `wirtschaftlichkeit_pdf`, `steckbrief_pdf`, Montage-
      Formular-PDFs rendern weiter mit festen Farben – kein Token-Zugriff aus
      fpdf2-Code; Test: Angebots-PDF eines Kontrollangebots ist vor und nach
      der Phase byteidentisch bis auf das Datum (Vergleich der gerenderten
      Seiten als Bild, Toleranz 0).

## Phase 146 – Design v2: Oberflächen im neuen Stil

Nur Optik – Reihenfolge, Texte, Routen, Formularfelder und Rollenregeln
bleiben. Jede Seite wird in beiden Modi geprüft (Screenshots vorher/nachher
nach `docs/design-v30/`, nur Demo-Daten, keine EK/DB im Bild).

- [x] **Bausteine** in `_komponenten.html`/`style.css` an die Vorlage angleichen:
      Karten (Radius, 1-px-Kontur, dezenter Schatten nur hell), Kennzahl-
      Kacheln (große Zahl, Unterzeile dezent, Farbakzent links wie
      Projektierung-Spalten der Vorlage), Status-Badges (gefüllte Pille mit
      Pfeil wie „Neu ▾“), Kanal-/Sparten-Chips (farbige Pille mit dunkler
      Fläche), Avatare mit Initialen (zwei Buchstaben, Farbe aus Benutzer-ID),
      Tabellen (dunkler Kopf in Kapitälchen mit Buchstabenabstand, Zeilen mit
      feiner Linie, Hover-Fläche, Zahlen tabellarisch), Filterleiste als
      Chip-Selects, Knöpfe (Primär = Akzentfläche mit dunklem Text im
      Dunkelmodus, Sekundär = Kontur), Eingabefelder, Dropdown-Menüs, Glocke,
      Wartungsbanner, Leer-Zustände, Fehlerseite.
- [x] **Portal/Startseite** (`index.html`, `_angebotstool_kacheln.html`): drei
      Bereiche wie heute, Kacheln im Kachel-Stil der Vorlage (Zahl groß, rote
      Zahl bei Dringlichem bleibt), Begrüßungszeile „Guten Morgen/Tag/Abend,
      <Vorname>“ mit Datum und KW als reine Kopfzeile über den Bereichen
      [ANNAHME: einzige inhaltliche Ergänzung, weil sie den Vorname aus v29
      nutzt und keine Daten braucht].
- [x] **Angebotstool:** Angebotsliste, Erfassungsliste, Leads VOT, Vorgangsakte,
      Angebots-Editor (Kopfkarte, Blocküberschriften, sticky Aktionsleiste,
      Positionszeilen, Drag-Griff), Statistik, Parametrierung (Verteilerseite,
      Karten, Formulare, Betriebs-Seite), Benutzerverwaltung, Fehlerprotokoll.
      Mobile Erfassung (Seite x von y, Frage-Karten, sticky Weiter-Leiste,
      Einschätzung) in beiden Modi bei 390 px prüfen.
- [x] **Lead-Management** (`lead_v2.css`, Templates `leadmanagement/`): Icon-
      Leiste, Hauptboard/Deals/Infoabend-Tabelle (Vorlage `hauptboard-dunkel.png`
      ist hier der Maßstab: Spaltenköpfe, Status-Pille, Kanal-Chip, Versuchs-
      Punkte, Avatare AD/ID, Telefon/E-Mail zweizeilig, rote Überfällig-
      Markierung), Anrufliste, Kartei, Dashboard, Terminassistent mit
      Kalenderansicht, Vorlagen-Editor, Karte.
- [x] **Projektierung und Montage:** Board (Spalten, Karten, Vorlauf-Ampel,
      Termin-Badge), Liste, Kalender, Projektakte (`akte_v28.css`), Aufgaben,
      Dialoge, Galerie-Lightbox, Montage-Backend `/montage` (Einsätze,
      Auftragsdetail, Formulare) – auch am Handy bei 390 px.
- [x] **Anmeldeseite** (`login_v27.css`): beide Modi; das Energiehaus-Foto bleibt.
- [x] **Kontrast:** Text auf Flächen mindestens 4,5 : 1, dezenter Text 3 : 1,
      in beiden Modi (Prüfskript über die Token-Paare in der Gesamtübersicht);
      Fokus-Ring sichtbar.
- [x] Prototyp-Dateien `docs/projektierung-prototyp.html` und
      `docs/leadmanagement-prototyp.html` bleiben unverändert; maßgeblich für
      Farben ist ab jetzt `docs/design-system.md` Abschnitt „Design v2“
      (Hinweis in beiden Prototypen als Kommentar oben).

## Phase 147 – Zurück-Navigation (eine Ansicht zurück)

- [x] **Knopf „← Zurück“** links in der Seitenkopfzeile (vor dem Seitentitel,
      `base.html`, Makro `zurueck_knopf`) auf allen Seiten außer: Startseite/
      Portal, Modul-Startseiten (`/lead-management/dashboard`, `/projektierung`,
      `/montage`), Login/PIN-Wechsel und den Seiten des Erfassungsbogens (dort
      gibt es die eigene Seitennavigation). Der Knopf ist kein Browser-Zurück:
      er führt zur **vorherigen Ansicht**, also zur zuletzt besuchten anderen
      Seite (nicht zum Neuladen derselben Seite nach einem Speichern).
- [x] **Verlauf im Browser-Tab** (`app/static/navigation.js`, eingebunden in
      `base.html`): bei jedem Seitenaufbau wird der aktuelle Pfad (mit Query,
      ohne `#`) in `sessionStorage` (`friondo_verlauf`, höchstens 30 Einträge,
      je Tab) angehängt – aber nicht, wenn er dem obersten Eintrag entspricht
      (Reload, Redirect nach POST). Klick auf „Zurück“ nimmt den obersten
      anderen Eintrag, entfernt ihn und navigiert dorthin (einmal zurück =
      eine Ansicht; zweimal = zwei Ansichten, nie Schleifen). Ist der Verlauf
      leer (Direktaufruf, neuer Tab), geht der Knopf zur Standard-Rücksprung-
      seite der Route (Attribut `data-zurueck-standard`: Angebot → Angebotsliste,
      Erfassung → Erfassungsliste, Vorgangsakte → Leads VOT bzw. Hauptboard,
      Projektakte → Projektboard, Einsatz → `/montage`, Parametrierungs-
      Unterseite → `/parametrierung`, sonst `/`). Alt/⌫ bleiben Browser-
      Verhalten; Tastenkürzel keins.
- [x] **Editor-Sonderfall:** Im Angebots-Editor führt „Zurück“ nicht aus dem
      Editor heraus, solange ungespeicherte Änderungen in einem offenen Feld
      stehen – erst Hinweis „Änderungen speichern?“ (bestehender
      `beforeunload`-Schutz, sofern vorhanden, sonst keiner).
- [x] Test (`tests/test_v30_navigation.py` + Playwright-Lauf im Headless-Chrome
      wie `scripts/design_screenshots.py`): Vorgangsakte → Angebot → Zurück
      landet in der Vorgangsakte; Angebot → Speichern (Redirect auf dieselbe
      Seite) → Zurück landet in der Vorgangsakte, nicht im Angebot; Direktaufruf
      `/angebote/<id>` → Zurück = `/angebote`; Startseite hat keinen Knopf;
      Erfassungsbogen hat keinen Knopf.

## Phase 148 – BzA-Datenblatt: A20 raus, Nennwärmeleistung als Zahl, 10 %-Puffer, ohne Abschnitt 6

- [x] **A20 entfernen** (Arbeitsanweisung Live-Excel `konfigurator_logik_v5.xlsx`,
      Blatt Fragen WP, Sicherung `diagnose/konfigurator_logik_v5.vor_v30.xlsx`):
      Zeile A20 „Nennleistung der bestehenden Heizung in kW“ löschen; „Logik
      prüfen“ grün. Code: A20 aus `konfigurator.OPTIONALE_FRAGEN` (v27-
      Nachtrag) und aus allen Vorbelegungen/Protokoll-Sonderfällen streichen;
      bestehende Erfassungen mit A20-Antwort zeigen sie weiter im Protokoll
      (keine Datenänderung). BzA-Datenblatt Abschnitt 2: Zeile „Nennleistung“
      entfällt; der Dialog bietet dafür kein Feld mehr.
- [x] **Nennwärmeleistung als Zahl:** im Dialog `/angebote/<id>/bza-datenblatt`
      (und auf der Gewerk-Seite `/projektierung/gewerk/<id>/bza`) ist das Feld
      `f_nennwaermeleistung` ein Zahlenfeld (`type="number"`, `step="0.01"`,
      `inputmode="decimal"`, Suffix „kW“ rechts im Feld als Text, Vorbelegung =
      Wert aus der BAFA-Anlage ohne Einheit). Beim Speichern: Zahl mit Komma
      oder Punkt annehmen, Ausgabe im PDF „9,00 kW“; Eingaben mit „kW“ hinten
      dran werden bereinigt (kein doppeltes „kW kW“ mehr); ungültige Eingabe →
      Meldung „Nennwärmeleistung: bitte nur die Zahl eingeben“.
- [x] **10 %-Puffer:** Abschnitt 4 bekommt nach „Geplante förderfähige Kosten“
      die Zeile **„Geplante förderfähige Kosten inkl. 10 % Puffer“** = Kosten ×
      1,10, kaufmännisch auf volle Euro gerundet, Hinweis „Puffer für einen
      möglichen KfW-Ergänzungskredit – ändert den Auftragswert nicht“
      (Schlüssel `kosten_puffer`, übersteuerbar wie die anderen Felder; bei
      manuell übersteuerten Kosten wird der Puffer aus dem übersteuerten Wert
      gerechnet). Prozentsatz als Parameter `bza_kosten_puffer_prozent`
      (Standard 10, 0 = Zeile entfällt) auf der Parametrierungs-Seite, die
      bisher „BzA-Ersteller“ heißt und jetzt **„BzA-Datenblatt“** heißt.
      KfW-Berechnung, Förderblock im Angebot und Höchstkostengrenze bleiben
      unverändert (die nachrichtlichen Zeilen rechnen weiter mit den echten
      Kosten).
- [x] **Abschnitt 6 „Ersteller“ entfällt** in Generator (`bza_datenblatt.
      erstellen`), PDF, Gewerk-Seite und Dialog (Auswahl „Ersteller“ entfällt).
      Parameter `bza_ersteller_standard` und der Firmenblock bleiben in der
      Datenbank/Code, werden aber auf der Parametrierungs-Seite nicht mehr
      angezeigt [ANNAHME: kein Löschen, damit v29-Code weiterläuft]. Vermerk
      „Internes Arbeitsblatt … keine KfW-Unterlage“ bleibt.
- [x] Kontrollwerte in `tests/test_bza_v19.py` nachziehen und neue Tests
      `tests/test_v30_bza.py`: Datenblatt eines WP-Angebots mit Endbetrag
      28.350,00 € zeigt „Geplante förderfähige Kosten 28.350,00 €“ und „… inkl.
      10 % Puffer 31.185,00 €“; Eingabe „9,5“ → „9,50 kW“, Eingabe „9,5 kW“ →
      „9,50 kW“, Eingabe „neun“ → Meldung; kein Abschnitt „6.“ und keine Zeile
      „Nennleistung“ im PDF-Text; Parameter 0 → keine Puffer-Zeile; A20 ist in
      der Logik nicht mehr vorhanden, `naechste_pflichtfrage` kennt sie nicht.

## Phase 149 – Lieferschein (Langtexte, EP-Folgepositionen) und Duplizieren-Fehler

- [x] **Langtexte:** `lieferschein_pdf._kurztext` kürzt nicht mehr – jede
      Position erscheint mit Bezeichnung (fett) und der vollständigen
      Beschreibung (alle Zeilen, wie im Angebots-PDF inkl. editierter Texte und
      Textregeln, Schrift 7,5 pt, Seitenumbruch innerhalb langer Texte
      erlaubt, Positionsnummer/Menge/Einheit bleiben in der ersten Zeile).
      Konstanten `MAX_BESCHREIBUNG_ZEILEN/ZEICHEN` entfallen. Gruppen-
      Überschriften und Unterschriftsblock unverändert.
- [x] **EP-Folgepositionen:** neue Parametrierungs-Liste **„Lieferschein:
      abhängige Positionen“** (Parameter `lieferschein_folgepositionen`,
      Standard `014: 015, 016, 017`; Pflege unter Angebotstool-Einstellungen,
      eine Zeile je Hauptposition). Regel in `lieferschein_positionen`: ist die
      Hauptposition im Angebot EP, Alternativ oder bauseits (also nicht auf dem
      Lieferschein), entfallen auch die aufgeführten Folgepositionen – auch
      wenn sie selbst nicht EP sind. Fehlt die Hauptposition im Angebot ganz,
      bleiben die Folgepositionen unberührt. Zusätzlich zeigt der **Editor** an
      Pos. 015–017 den Hinweis „folgt auf dem Lieferschein Pos. 014“ (nur
      Anzeige, keine automatische EP-Änderung) [ANNAHME].
- [x] **Fehler F-20261002-073115-9c9e:** Eintrag in der Tabelle
      `fehlerprotokoll` der Server-DB-Kopie (und `data\fehler.log`, falls in
      diagnose\ vorhanden) lesen – Traceback, Route, Angebot. Ablauf
      „Überarbeiten → Version .2 → Duplizieren“ auf der DB-Kopie reproduzieren.
      Erwartete Ursachen (prüfen, nicht raten): (a) `sqlite3.OperationalError:
      database is locked` – die Routen `duplizieren`, `ueberarbeiten` und
      `kopieren` laufen ohne die v22-Wiederholung `_speichern` → Wiederholung
      ergänzen und Ursache im Protokoll als „kurz belegt“ ausweisen; (b) ein
      Feld, das beim Duplizieren einer **Version** nicht mitkopiert bzw. doppelt
      vergeben wird (`anzeige_nr`, `alternativ_zu` auf ein Geschwister-Angebot
      der alten Version, Nummernkreis bei Nummern mit „.2“) → beheben. In jedem
      Fall: Regressionstest `tests/test_v30_duplizieren.py` (Überarbeiten →
      Duplizieren der Version → neues Angebot mit eigener Nummer, allen
      Positionen und Kennzeichen; parallel gehaltene Schreibsperre → kein 500,
      Meldung „Datenbank kurz belegt …“), Eintrag in der Gesamtübersicht mit
      der tatsächlichen Ursache.
- [x] Tests `tests/test_v30_lieferschein.py`: Kontrollangebot mit 014 auf EP →
      Lieferschein ohne 014/015/016/017; 014 normal → alle vier dabei; 014
      fehlt, 015 vorhanden → 015 dabei; Position mit 12-zeiliger Beschreibung →
      alle 12 Zeilen im PDF-Text; Parameter leer → keine Abhängigkeit.

## Phase 150 – Zahlungsbedingungen je Angebot

- [x] **Parametrierung → Zahlungsbedingungen** (Angebotstool-Einstellungen,
      eigene Karte; Tabelle `zahlungsbedingungen`: schluessel, name, text,
      sortierung, aktiv, standard): drei Einträge per Migration, Texte als
      Startwerte (Innendienst liest gegen, [ANNAHME] bei 2 und 3):
      1. **Standard** (heutiger Absatz, wörtlich aus den Nachtexten): „Eine
         Anzahlung von 50% des Angebotsbetrags ist spätestens 14 Tage vor
         Arbeitsbeginn zu zahlen. Die Restzahlung wird mit der
         Schlussrechnungsstellung fällig. Die Rechnung erhalten Sie im Anschluss
         zur Installation.“
      2. **50 % am Montagetag:** „Eine Anzahlung von 50% des Angebotsbetrags ist
         am Tag der Montage zu zahlen. Die Restzahlung wird mit der
         Schlussrechnungsstellung fällig. Die Rechnung erhalten Sie im Anschluss
         zur Installation.“
      3. **80 % Anzahlung, 2 % Skonto:** „Eine Anzahlung von 80% des
         Angebotsbetrags ist spätestens 14 Tage vor Arbeitsbeginn zu zahlen. Bei
         Zahlung der Anzahlung innerhalb von 7 Tagen nach Auftragserteilung
         gewähren wir 2% Skonto auf den Anzahlungsbetrag. Die Restzahlung wird
         mit der Schlussrechnungsstellung fällig. Die Rechnung erhalten Sie im
         Anschluss zur Installation.“
      Editor für Name/Text (HTML-Editor wie Vorlagen), neue Einträge anlegbar,
      deaktivieren statt löschen, genau ein Standard. Skonto wirkt nur im Text –
      keine Änderung an Summen, KfW oder DB.
- [x] **Platzhalter `{zahlungsbedingungen}`:** die Nachtexte (Textblöcke aller
      Profile WP/PV/KL, Abschnitt „Zahlung“) enthalten statt des festen
      Absatzes den Platzhalter; Migration `migration_v30_zahlung` ersetzt in
      jedem Textblock den Standardabsatz (Textvergleich ohne Leerzeichen-
      Unterschiede) durch den Platzhalter und meldet Blöcke, in denen der Absatz
      nicht wörtlich gefunden wurde (Liste in der Gesamtübersicht; dort trägt
      der Innendienst den Platzhalter von Hand nach). Die Überschrift
      „**Zahlung**“ bleibt im Textblock. Rendering in `_nachtext_rendern` wie die
      übrigen Platzhalter; ANGEBOTSTEXTE.md Abschnitt 6/9 entsprechend.
- [x] **Auswahl am Angebot:** Spalten `angebote.zahlungsbedingung_key` (Standard
      leer = Standard-Eintrag) und `zahlungsbedingung_text` (Freitext). Im
      Editor-Bereich der Kopfkarte (bei Rabatt/Profil) Auswahl „Zahlungs-
      bedingung“ (Dropdown der aktiven Einträge + „Abweichend (Freitext)“ mit
      Textfeld, `POST /angebote/<id>/zahlungsbedingung`, nur Entwurf; ID/Admin,
      nicht AD). PDF druckt den gewählten Text; Vorschau im Editor zeigt den
      Namen („Zahlungsbedingung: 80 % Anzahlung, 2 % Skonto“). Überarbeiten,
      Duplizieren, Kopieren übernehmen beide Felder. Kombi-Versand und Mails
      unverändert; die E-Mail-Vorlage bekommt den Platzhalter `{zahlungsbedingung}`
      (Name des Eintrags) [ANNAHME].
- [x] Tests `tests/test_v30_zahlung.py`: Kontrollangebot mit Standard → PDF-Text
      enthält „50% des Angebotsbetrags ist spätestens 14 Tage“; Auswahl 3 →
      „80% des Angebotsbetrags“ und „2% Skonto“; Freitext „Zahlung nach
      Vereinbarung.“ → wörtlich im PDF; Migration auf der DB-Kopie: alle
      Standard-Nachtexte tragen den Platzhalter, Liste der nicht ersetzten
      Blöcke; Summen/KfW unverändert (Netto 30.245,43 € des Kontrollangebots).

## Phase 151 – Projektierung Go-live: Projekt löschen (Admin), Demo-Daten

- [x] **„Projekt löschen“ (nur Admin)** in der Projektakte (Aktionsleiste,
      rot, ganz rechts) und in der Projektliste (Mehrfachauswahl → „Ausgewählte
      löschen“, nur Admin): Sicherheitsdialog mit Pflichtgrund (Text), Eingabe
      der Projektnummer zur Bestätigung und Hinweis „Das Löschen ist endgültig
      – das Angebot bleibt erhalten und kann erneut in ein Projekt überführt
      werden.“ Ausführung `projektierung.projekt_loeschen(session, projekt,
      grund, benutzer)`: löscht Projekt, Gewerke, Aufgaben/Schritte, Termine
      (Outlook-Ereignisse werden vorher storniert, falls `kalender_sync` an –
      Netzaufruf ohne offene Sitzung), Besetzungen, Verlauf, Kommentare,
      Benachrichtigungen des Projekts, Steckbrief, BzA-/Heizreport-Felder des
      Gewerks (Heizreport-Projekt bleibt im Portal, nur Verknüpfung weg);
      Dokumentenordner `data/projekte/<PR>/` wird nach
      `data/projekte/_geloescht/<PR>_<JJJJMMTT-HHMM>/` **verschoben** (nicht
      gelöscht) [ANNAHME]; Galerie-Dateien am Vorgang bleiben. Angebot:
      `projekt_gewerk_id` leeren, Status unverändert, Button „Angebot →
      Projekt“ wieder sichtbar; Vorgangsakte zeigt „kein Projekt“. Eintrag im
      **Lösch-Protokoll** (Parametrierung, v6: Art „Projekt“, Nummer, Grund,
      Benutzer, Zeit) und Notiz im Vorgangs-Chat „Projekt <PR> gelöscht: <Grund>“.
      Nicht löschbar: Gewerke in Phase Montage oder später mit Montagebericht
      [ANNAHME – Rückfrage]; stattdessen Hinweis auf Storno.
- [x] **Demo-Projekte:** die von `scripts/demo_projekte.py` angelegten Projekte
      (Kennzeichen prüfen – Kunde/Vorgang `demo = 1` bzw. Namensmuster des
      Skripts) erscheinen in der Projektliste mit Filter „Demo“ und Badge, der
      Admin löscht sie über die Mehrfachauswahl; `docs/nach-dem-update-v30.md`
      beschreibt den Schritt. Bestand aus dem Bestandsimport (`bestand = 1`) ist
      davon nicht betroffen.
- [x] **Go-live-Schritte für Andreas** (keine Code-Änderung, nur Doku + Prüfung
      durch Claude Code auf der DB-Kopie): Go-live-Checkliste 11/11 oder
      begründete Ausnahmen (Claude Code listet den Stand der Kopie in der
      Gesamtübersicht), Demo-Projekte gelöscht, Bestandsimport erledigt,
      danach Parametrierung → Projektierung-Einstellungen → `freigabe_modus =
      alle`; Portal-Badge verschwindet, Montage-Login landet in `/montage`,
      Projektierungs-Rolle sieht das Modul. Lead-Management bleibt
      `lead_freigabe_modus = admin`.
- [x] Tests `tests/test_v30_projekt_loeschen.py`: Admin löscht ein Projekt mit
      zwei Gewerken → keine Zeilen mehr in Projekt/Gewerk/Aufgaben/Termine/
      Besetzung, Angebot Status „Angenommen“ mit `projekt_gewerk_id = NULL`,
      Ordner unter `_geloescht`, Lösch-Protokoll-Eintrag, Vorgangsnotiz;
      Innendienst → 403; ohne Grund → Meldung; falsche Projektnummer → Meldung;
      Gewerk in Montage mit Bericht → abgelehnt mit Storno-Hinweis.

## Phase 152 – Tests, Rollout-Vorbereitung, Doku, CLAUDE.md v30

- [x] **Tests gesamt:** neue Dateien `tests/test_v30_design.py` (Token-Wächter:
      keine neuen Hex-Werte außerhalb der `:root`-Blöcke und der `/* fest */`-
      Ausnahmen; `data-theme` wird aus Cookie/Einstellung gesetzt; Umschalter-
      Route speichert je Benutzer; Kontrastprüfung der Token-Paare ≥ 4,5 : 1),
      `test_v30_navigation.py`, `test_v30_bza.py`, `test_v30_lieferschein.py`,
      `test_v30_duplizieren.py`, `test_v30_zahlung.py`,
      `test_v30_projekt_loeschen.py`; angepasste Alt-Tests (BzA-Kontrollwerte,
      Lieferschein-Kürzung, A20 in `test_bza_v19.py`/`test_rueckfragen_0930.py`)
      mit Begründung. `pytest tests -q` komplett grün, Wächter-AST-Test v27 grün.
- [x] **Screenshots** vorher/nachher in beiden Modi nach `docs/design-v30/`
      (Portal, Angebotsliste, Editor, Vorgangsakte, Hauptboard, Kartei,
      Projektboard, Projektakte, Montage-Einsatz, mobile Erfassung, Login),
      erzeugt mit `scripts/design_screenshots.py` (um `--modus hell|dunkel`
      erweitert), nur Demo-Daten, keine EK/DB im Bild.
- [x] **Rollout-Vorbereitung** nach Grundregel: Server-DB-Kopie nach diagnose\,
      migrate.py zweimal (zweiter Lauf ohne Änderungen; neue Tabelle
      `zahlungsbedingungen`, Spalten `angebote.zahlungsbedingung_*`, Parameter
      `bza_kosten_puffer_prozent`, `lieferschein_folgepositionen`,
      Einstellung `darstellung`, Nachtext-Migration), `scripts/voll_crawl.py`
      für admin/innendienst/aussendienst/montage/projektierung **je einmal hell
      und dunkel** (Cookie), `tests/abnahme.py` grün, `scripts\smoke.bat`;
      kein neuer Lasttest nötig (keine neuen Netz- oder Hintergrundläufe) –
      Begründung in der Gesamtübersicht.
- [x] **Doku:** CLAUDE.md Abschnitt „Neu in v30 – Design v2, Zurück-Navigation,
      BzA/Lieferschein/Zahlungsbedingungen, Projektierung Go-live (abgestimmt
      11.10.2026)“ nach „Neu in v29“, Zuordnungstabelle `| v30 | PLAN_V18.md |
      145–152 |`, Titelzeile von CLAUDE.md auf „(v30)“ (steht seit v27 auf
      „(v27)“), in v14 und v19 die überholten Sätze (feste Farben, A20 Pflicht,
      Abschnitt 6 Ersteller) als *überholt – siehe v30* markieren;
      `docs/design-system.md` Abschnitt „Design v2“ (Tokens je Modus,
      Umschalter, Regeln für neue Seiten); `docs/nach-dem-update-v30.md`
      (Team: Darstellung wählen, Zurück-Knopf, Zahlungsbedingung im Editor,
      BzA-Änderungen, Lieferschein; Admin: Demo-Projekte löschen, Go-live-
      Schalter, Parameter prüfen, Nachtext-Blöcke ohne Platzhalter nachtragen);
      `docs/updates.md` ergänzen; `config.VERSION = "v30"`.
- [x] Gesamtübersicht am Ende: erledigte Phasen, Testergebnisse (Gesamtzahl),
      angepasste Alt-Tests mit Begründung, tatsächliche Ursache des
      Duplizieren-Fehlers, Liste der nicht ersetzten Nachtext-Blöcke, Stand der
      Go-live-Checkliste, Liste aller [ANNAHME]-Stellen, Rückfragen gebündelt.
      **Ein Commit** „v30: Design v2 Hell/Dunkel, Zurück-Navigation,
      BzA/Lieferschein/Zahlungsbedingungen, Projektierung Go-live (PLAN_V18,
      Phasen 145-152)“; **kein push vor Freigabe**.

## Kontrollwerte für die Abnahme

- Ohne Cookie/Einstellung folgt die Darstellung dem Gerät; Auswahl „Dunkel“ im
  Menü → sofort dunkel, nach Neuanmeldung an einem anderen Browser ebenfalls
  dunkel (Einstellung je Benutzer); „Gerät“ setzt zurück. Kein Aufblitzen des
  hellen Modus beim Laden im Dunkelmodus.
- Angebots-PDF des Kontrollangebots (Netto 30.245,43 €) ist nach Phase 145/146
  unverändert; Lieferschein zeigt vollständige Beschreibungen; mit Pos. 014
  auf EP fehlen 014–017.
- Vorgangsakte → Angebot → Zurück = Vorgangsakte; Angebot → Speichern → Zurück
  = Vorgangsakte; Direktaufruf → Zurück = Angebotsliste.
- BzA-Datenblatt: keine Zeile „Nennleistung“, kein Abschnitt 6; Eingabe „9,5“
  → „9,50 kW“; Kosten 28.350,00 € → Puffer-Zeile 31.185,00 €.
- Überarbeiten → Duplizieren der Version .2 → neues Angebot ohne Fehlerseite,
  alle Positionen und Kennzeichen übernommen; Fehlerprotokoll ohne neuen Eintrag.
- Zahlungsbedingung 3 am Angebot → PDF-Nachtext enthält „80% des Angebotsbetrags“
  und „2% Skonto“; Summen unverändert.
- Admin löscht ein Demo-Projekt → verschwindet aus Board/Liste/Akte, Angebot
  wieder mit Button „Angebot → Projekt“, Eintrag im Lösch-Protokoll.
- `pytest tests -q` grün, Abnahmeskript grün, Voll-Crawl hell + dunkel ohne
  Absturz, Smoke 8/8.

## Zulieferungen / bewusst offen

- **HTML-Prototyp (Andreas):** nach `docs\design-v30\vorlage\` legen (jede
  `.html`, zugehörige Bilder daneben) – vor dem Start des Durchlaufs; die
  Screenshots liegen dort bereits.
- Texte der Zahlungsbedingungen 2 und 3 sind [ANNAHME] – Innendienst liest sie
  nach dem Update in der Parametrierung gegen (dort editierbar).
- [ANNAHME]-Bestätigungen: „Punkt 6“ = Abschnitt 6 Ersteller; Begrüßungszeile
  auf dem Portal; Editor-Hinweis an 015–017 ohne Automatik; Projektordner
  verschieben statt löschen; Sperre „Projekt löschen“ ab Phase Montage mit
  Bericht; Parametrierungs-Seite „BzA-Datenblatt“; `{zahlungsbedingung}` in
  der E-Mail-Vorlage; Zahlen tabellarisch statt Monospace; Schrift der Vorlage
  nur bei OFL-Datei.
- Go-live der Projektierung: Umstellung `freigabe_modus = alle` durch Andreas
  nach dem Rollout; offene Checklisten-Punkte (M365-Absender, Outlook-
  Kalender, Collin-Testdatei) sind keine Code-Punkte dieses Plans.
- Nicht Teil dieses Plans: neue Startseiten-Struktur („Jetzt dran“, Suche,
  Icon-Leiste für alle Module) – bei Bedarf eigener Plan nach dem Live-Betrieb.
