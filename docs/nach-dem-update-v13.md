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

## Offene fachliche Rückfragen PV (Abschlussbericht 29.09.2026)

Nachgetragen in Phase 94 (vorher nur im Chat-Bericht). In Klammern steht,
was das Tool bis zur Antwort verwendet.

1. **Preisabweichungen zwischen den Listen**
   - Energy Gateway: 1.091,80 € (Sigenergy-Liste) vs. 980 € im Muster
     (1.091,80 €, als Eventualposition)
   - Zählerzusammenlegung: 448 € („Ersatz Position PV“) vs. 548 €
     („Elektro Allgemein“) (448 €)
   - Zählerschrank 2-Feld: EK 1.200 € („Elektro Allgemein“) vs. 1.488 € im
     Muster (1.200 €)
   - Hager VA36CN: kein EK in der Liste (0 € – verfälscht den DB)
   - HEMS: 0 € wie im Muster; die PV-Liste hat eine eigene HEMS-Position zu
     949 €
2. **Positionsreihenfolge:** Plan = Module Pos. 1, WR/Speicher Pos. 2; im
   Muster steht der WR auf Pos. 6 (gebaut nach Plan, im Blatt
   „Angebotsaufbau PV“ umstellbar).
3. **Solar/Erdungskabel-Set je String** (× Strings) steht im Muster, nicht im
   Plan – aufgenommen. Mehrmeter bei DC-Kabelweg > 10 m (PD08) werden nicht
   berechnet.
4. **Annahmen bestätigen:** WR-Leistung = kWp ÷ 1,2 · Speicherstufe nach der
   Nennzahl im Namen („/10“ = real 9,04 kWh) · Walmdach wie Satteldach ohne
   Quer-Abfrage · **Eigenverbrauch additiv** (32 + 33 + 10 = 75 %) ·
   Eigenverbrauch nicht auf den tatsächlichen Verbrauch begrenzt.
5. **PA04 „Ertüchtigung bestehender ZV“** (mit PA05 APZ-Feld, PA06
   HAK-Leitung): welche Positionen? Bis dahin individuell.
6. **Zählerschrank 4-Feld** und **kein Speicher** (PA10 = 0): kein Artikel,
   derzeit individuell – gewollt?
7. **PD09 (DC-kWp) / PA09 (WR-Leistung)** werden berechnet und nur
   protokolliert – Fragen aus dem Bogen streichen?
8. **Mailvorlage:** Standard spricht von „Interesse an einer Wärmepumpe“ –
   eigene PV-Vorlage anlegen?
9. **PV-Nachtexte Enni/SWD/Sparkasse** aus den WP-Texten abgeleitet (ohne
   KfW-Teil) – bitte unter Textblöcke gegenlesen.
10. **Flachdach:** eine gemeinsame Position „UK Flachdach S od. O/W“ für
    Ost/West und Süd – passt das?

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
