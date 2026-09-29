# Nach dem Update v13 (PLAN_V13) – PV-Konfigurator

Ab diesem Update erzeugt die PV-Erfassung ein **vollständiges PV-Angebot**
im Tool – wie bei der Wärmepumpe. PV-Angebote rechnen mit **0 % USt**
(§ 12 Abs. 3 UStG) und haben **keinen Förderblock**.

## Für den Außendienst – PV-Erfassung neu

1. **Belegungsart** (erste Seite, zwei große Buttons):
   - **Maximalbelegung** – es werden so viele Module angeboten, wie
     aufs Dach passen.
   - **Bedarfsorientierte Belegung** – die Modulanzahl ergibt sich aus
     dem Verbrauch (Haushalt × 1,3 + Wärmepumpe × 1,5 + Wallbox, geteilt
     durch 960 kWh/kWp). Nie mehr als die Maximalbelegung – wird
     gedeckelt, steht das im Angebot.
2. **Verbrauchsfragen** (Seite Objektdaten):
   - Stromverbrauch des **Haushalts** in kWh (ohne WP und Wallbox).
   - Stromverbrauch der **Wärmepumpe**: Zahl eintragen (0 = keine WP)
     **oder** „Aus WP-Erfassung ermitteln“ anhaken – dann nimmt das Tool
     den Gas-/Ölverbrauch aus der WP-Erfassung desselben Kunden-Vorgangs
     und teilt ihn durch 3,5. Gibt es noch keine WP-Erfassung mit
     Verbrauch, erscheint ein Hinweis – dann bitte die Zahl eintragen.
   - **Wallbox** geplant oder vorhanden? Bei Ja den Verbrauch in kWh.
   - Die alte Frage „Stromverbrauch inkl. WP & WB“ entfällt.
3. **Dachmontage – Interim-Felder** (bis das Dachbelegungstool kommt):
   - „Maximale Modulanzahl lt. Dachbelegungstool“ (Pflicht).
   - Bei Satteldach: „davon quer verlegte Module“ (leer = 0).
   - Bei Flachdach: Belegung Ost/West oder Süd.
   - „Anzahl Optimierer“ gilt jetzt auch für Module mit abweichender
     Neigung (z. B. auf einer Gaube).
4. **Elektro:** neue Frage „Zählerzusammenlegung erforderlich?“.
5. Enni-Kunden: wie bei WP nur die HEMS-Frage.

Individuell (orange) wird eine PV-Erfassung u. a. bei: Dachart
„Sonstige“, Vollgerüst/Sonstiges, Zählerschrank 4-Feld/Sonstige,
Ertüchtigung der bestehenden ZV, mehr als 4 Strings, Wechselrichter über
30 kW, keine passende Sigenergy-WR/Speicher-Kombination.

## Für den Innendienst

- PV-Erfassungen mit grüner Ampel: **„Angebot erzeugen“** wie bei WP –
  PV-Angebot mit Sparten-Badge, Editor, Versand, Verfolgung, monday,
  Statistik wie gewohnt. Im Summenblock steht „Umsatzsteuer 0 %
  (§ 12 Abs. 3 UStG)“; der Steuersatz ist am Angebot umschaltbar
  (19 % / 0 %).
- Das PV-PDF folgt dem Muster AN261699: Vortext PV, eine Überschrift
  „Komplettpaket … kWp PV-Anlage …“, Auslegungszeile (Module, kWp,
  Strings, Wechselrichter/Speicher), Nachtext mit Nullsteuersatz-Hinweis,
  Zahlungsoptionen und **„Ihre Beispielrechnung“** (Ertrag,
  Eigenverbrauch, Ersparnis, grobe Amortisation – Annahmen im Blatt
  „PV-Parameter“ der Logik-Excel).
- **Warteschlange – PV-Altfälle:** Bestehende PV-Erfassungen in „In
  TAIFUN zu schreiben“ bleiben unverändert. Optional: in der Erfassung
  **„↻ Erneut prüfen“** – fehlen die neuen Fragen, nennt das Tool die
  erste fehlende Frage (Bogen ergänzen, erneut prüfen); ist alles grün,
  geht der Fall auf den normalen Tool-Weg.
- **Lieferschein:** Angenommene Angebote (alle Sparten) haben im Editor-
  Kopf und in der Vorgangsakte „Lieferschein (PDF)“ – ohne Preise,
  Dateiname LS-<Angebotsnummer>.pdf.
- **DB-Ampel je Sparte:** Parametrierung → Deckungsbeitrags-Ampel →
  „je Sparte“. Leer = allgemeine Schwellen (Start: PV wie WP). Bitte
  die PV-Schwellen setzen, sobald sie feststehen.
- PV-Artikel heißen PV001 … PV176 (Artikel → Suche „PV“), pflegbar wie
  WP-Artikel. Neue Positionslisten: Dateien in
  `Artikel-Preislisten/PV/` ersetzen → „PV-Positionslisten importieren“
  (Vorschau, dann ausführen). Achtung: wie beim WP-Import überschreibt
  ein Re-Import manuelle Preisänderungen an PV-Artikeln.

## Zulieferungen offen

- **Dachbelegungstool** (liefert Modulanzahl je Dachseite und
  Quer-Anteil – ersetzt dann die Interim-Felder; Schnittstelle
  `pv_auslegung.dachbelegung_setzen`).
- **Sigenergy-/Modul-Datenblatt** – Datei nach `anlagen/`, im Blatt
  „Anhänge“ die vorbereitete Zeile (Regel „wenn Sparte = PV“) mit dem
  Dateinamen füllen.

## Rollout

`update.bat` auf dem Terminal-Server. Die Migration ergänzt die Spalten
`ust_satz`/`pv_json`, legt die PV-Textblöcke an und importiert die
PV-Positionslisten automatisch (Migrationslog prüfen: „PV-Artikel fehlten
… PV-Positionslisten-Import ausgeführt (PV: 176 neu …)“). Danach in der
Parametrierung „Parametrierung neu einlesen“ – die Validierung muss grün sein.

## Checkliste nach dem Rollout

- [ ] Migrationslog: ust_satz, pv_json, 5 PV-Textblöcke, 176 PV-Artikel
- [ ] Parametrierung: Validierung grün, keine PV-Artikel-Fehler
- [ ] Test-PV-Erfassung (Maximalbelegung) → grün → Angebot erzeugen →
      PDF prüfen (0 % USt, Beispielrechnung)
- [ ] DB-Schwellen PV gesetzt
- [ ] bestehende WP-Angebote unverändert (19 %)
