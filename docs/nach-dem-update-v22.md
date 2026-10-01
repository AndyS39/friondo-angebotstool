# Nach dem Update v22 (PLAN_V15) – Wirtschaftlichkeit im PV-Angebot, PA04, Team-Feedback 30.09.

Ab diesem Update ersetzt eine **dreiseitige Wirtschaftlichkeitsbetrachtung**
die bisherige Text-„Beispielrechnung“ im PV-Angebots-PDF. Dazu kommen das
Team-Feedback vom 30.09. (Fehlerprotokoll, Editor, BzA-Dialog,
Gruppen-Überschriften) und die PA04-Entscheidung.

## Für den Innendienst – PV-Angebote

- **Drei neue Seiten im PV-PDF** („Wirtschaftlichkeitsbetrachtung“ · „Ihre
  Ersparnis im Detail“ · „Sicherheit & Transparenz“), eingebettet zwischen
  Zahlungsoptionen und Installationsvoraussetzungen – kein separater Anhang.
  Grundlage: Anlagenleistung, Module, Speicher (PA10), HEMS (Pos. 015),
  SpotDynamic (Pos. 017), Verbrauch Haushalt/Wärmepumpe/Wallbox aus der
  Erfassung (PO06, PO07, PO08/PO09), Investition = Endbetrag des Angebots,
  Start = Angebotsjahr + 1.
- **Rechenweg (Energiebilanz statt additiver Quote, saisonal):** je Monat
  Produktion nach Monatsprofil (Sommer viel, Winter wenig), Verbrauch nach
  Monatsprofil (Wärmepumpe im Winter hoch), Direktverbrauch je
  Verbrauchergruppe (Direktanteil + HEMS-Zuschlag, skaliert mit dem
  Sonnenangebot des Monats, höchstens 90 % der Monatsproduktion), Speicher
  (Vollzyklen × kWh, Wirkungsgrad), Netzbezug, Einspeisung; Jahreswerte als
  Summe der Monate. Dann Kosten ohne Anlage vs. mit Anlage (SpotDynamic:
  Netzbezug zu Ø 18 ct/kWh), Break-even, Baustein-Treppe, drei
  Strompreis-Szenarien, CO₂. Alle Annahmen stehen auf Seite 3 des PDFs
  („Unsere Annahmen – transparent“). Folge des Saisonmodells: im Winter
  bleibt ein deutlicher Netzbezug, der Solaranteil der Wärmepumpe liegt
  realistisch bei rund der Hälfte.
- **Häkchen „Wirtschaftlichkeit im PDF ausblenden“** im Angebots-Kopf des
  Editors (nur PV): Seiten entfallen komplett. Überarbeiten/Duplizieren/Für
  anderen Kunden kopieren übernehmen das Häkchen.
- **Altfälle:** PV-Angebote ohne gespeicherte Auslegung (vor v16 erzeugt)
  bekommen keine Wirtschaftlichkeitsseiten und keinen Fehler. Für Angebote
  mit Auslegung, aber ohne Verbrauchsdaten (v16-Bestand), holt das Tool die
  Verbrauchswerte aus der verknüpften Erfassung.
- **Textblöcke:** Die PV-Nachtexte (Standard/Enni/SWD/Sparkasse DU) enthalten
  jetzt den Platzhalter `[WIRTSCHAFTLICHKEIT]` als eigene Seite; die
  Migration stellt bestehende Blöcke um. Der alte Platzhalter
  `[BEISPIELRECHNUNG]` funktioniert weiter (Alias). Selbst angelegte oder
  umbenannte PV-Blöcke bitte in Parametrierung → Textblöcke prüfen.
- **Schrift Poppins** liegt im Tool (app/static/pdf/fonts, Lizenz OFL).
  Fehlt sie auf dem Server, fallen die drei Seiten auf Arial zurück – das
  PDF wird trotzdem erzeugt, im Serverlog steht eine Warnung.

## Parametrierung

- **PV-Parameter** (Parametrierung → Übersicht, neue Tabelle): 24 neue
  Zeilen im Blatt „PV-Parameter“ der Logik-Excel – Strompreissteigerung 3 %,
  Degradation 0,4 %/Jahr, Betriebskosten 100 €/Jahr, Betrachtungszeitraum 20,
  Inbetriebnahme-Versatz 1, Direktanteile Haushalt 35 / Wärmepumpe 20 /
  Wallbox 30 %, HEMS-Zuschläge 5 / 15 / 20 %-Punkte, Speicher 250 Vollzyklen
  und 90 % Wirkungsgrad, SpotDynamic Bezugspreis 0,18 €/kWh, Kosten-Airbag
  0,39 €/kWh (nur Text), Szenarien „1; 3; 5“ %, CO₂ 380 g/kWh, Auto 120 g/km,
  Baum 12,5 kg/Jahr, Montagedauer-Text „Montage in 1–2 Tagen“ (Schritt 3 auf
  Seite 3) sowie vier Monatsprofile (PV, Haushalt, Wärmepumpe, Wallbox) als
  zwölf Werte „Jan; Feb; …; Dez“ in Prozent des Jahres. Die drei Zeilen
  „Eigenverbrauchsquote PV / Zuschlag Speicher / Zuschlag HEMS“ bleiben
  stehen, sind aber ungenutzt.
  **Eingabekonvention:** Prozentwerte als Zahl mit Einheit „%“ (3, nicht
  0,03 und kein Excel-Prozentformat), Tausender ohne Punkt, Listen mit
  Semikolon getrennt (Komma ist Dezimaltrenner).
- Fehlt eine der neuen Zeilen, bleibt die Validierung grün und zeigt einen
  Hinweis mit dem verwendeten Standardwert; ein vorhandener, aber
  unlesbarer Wert ist ein Fehler.
- **Fehlerprotokoll** (Parametrierung → Fehlerprotokoll): Jede unbehandelte
  Störung („Internal Server Error“) wird mit Fehler-Nr., Zeit, Benutzer,
  Route, Formulardaten (PIN maskiert) und Traceback gespeichert; zusätzlich
  in `data/fehler.log`. Der Benutzer sieht eine lesbare Fehlerseite bzw. im
  Editor eine Meldung mit Fehler-Nr. statt „Internal Server Error“. Einträge
  lassen sich als erledigt markieren und erledigte löschen.

## Editor (Team-Feedback 30.09.)

- Nach EP / bauseits / Alternativ / Rabatt / Preis / Menge bleibt die
  Scroll-Position erhalten (kein Sprung an den Seitenanfang); neu
  eingefügte Positionen werden angesprungen.
- **Gruppen-Überschriften** (z. B. „Bosch Monoblock Wärmepumpe CS3800i AW
  Paket …“) sind je Angebot editierbar (✎ neben der Überschrift) – gilt nur
  für dieses Angebot, Editor und PDF zeigen den neuen Text.
- Die Auslegungszeile der Wärmepumpe trägt jetzt die Einheit „psl.“ (wie
  bei PV); Bestandsangebote werden per Migration nachgezogen.
- **BzA-Datenblatt:** Im Dialog sind alle Felder überschreibbar (leer =
  automatischer Wert, rot = fehlt), inklusive Contracting (Ja/Nein,
  vorbelegt Nein). Übersteuerungen gelten nur für das erzeugte PDF und
  werden nicht gespeichert.

## Für den Außendienst

- **PA04 „Ertüchtigung bestehender ZV?“** setzt die Erfassung nicht mehr auf
  Individuell; die Antwort (und PA05/PA06) steht nur im Protokoll. Liegende
  PV-Erfassungen mit PA04 = Ja lassen sich mit „Erneut prüfen“ auf Grün holen.

## Sporadischer „Internal Server Error“ beim Löschen/Verschieben (Diagnose)

Ursache ist nach der Analyse nicht die Positionslogik (stale IDs,
Doppelklick, leere Sortierung, letzte Position, Fremdsperre sind alle
abgefangen), sondern **„database is locked“**: Hintergrundläufe (Geocoding
alle 5 Minuten, monday-Sync alle 15 Minuten, Mail-Läufe 07:00/07:15) halten
nach dem ersten Schreibzugriff die SQLite-Schreibsperre, während sie auf
Netzantworten warten; ein Speichern im Editor wartet dann 5 Sekunden
(busy_timeout) und bricht ab. Mit v22 wiederholen die Positionsrouten
(Löschen, Verschieben, Zeile ändern, Menge, Neu durchnummerieren) den
Schreibzugriff einmal automatisch; bleibt die Sperre, wird der Fall
protokolliert und als Meldung „Datenbank kurz belegt – Änderung nicht
gespeichert, bitte erneut versuchen (Fehler-Nr. …)“ angezeigt. Zusätzlich
haben die Graph-Aufrufe jetzt ein Timeout. Die Verkürzung der
Hintergrund-Transaktionen (commit vor Netz-I/O, Backoff für nicht
geokodierbare Adressen) ist als Folgeänderung notiert (CLAUDE.md v22).
Bitte melden, ob der Fehler weiterhin auftritt – das Fehlerprotokoll
zeigt dann Uhrzeit und Route.

## Nebenbefund aus dem Voll-Crawl

Zwei ältere Angebote (Signaturen vom Entwicklungs-PC, 08/2026) speichern die
signierte PDF mit dem absoluten Pfad des alten Rechners – „Signiertes PDF
anzeigen“ lief dort in einen Internal Server Error. Jetzt wird die Datei
über ihren Namen im Ordner `data/angebote/signiert` gesucht; fehlt sie,
erscheint eine Meldung statt des Absturzes. Bitte auf dem Server prüfen,
ob die Dateien `AN-C-261008-signiert.pdf` und `AN-C-261015-signiert.pdf`
dort liegen (sonst aus dem Backup des alten Rechners dorthin kopieren).

## Rollout

`update.bat` auf dem Terminal-Server. Die Migration ergänzt die Spalte
`wirtschaftlichkeit_ausblenden`, stellt die PV-Nachtexte auf
`[WIRTSCHAFTLICHKEIT]` um, setzt WP-Auslegungszeilen auf „psl.“ und legt die
Tabelle `fehlerprotokoll` an. Danach in der Parametrierung
„Parametrierung neu einlesen“ – die Validierung muss grün sein (die 20 neuen
PV-Parameter-Zeilen stehen bereits in der Logik-Excel des Repos).

## Checkliste nach dem Rollout

- [ ] Migrationslog: Spalte wirtschaftlichkeit_ausblenden, PV-Nachtexte
      umgestellt, Auslegungszeilen psl., keine Fehler
- [ ] Parametrierung: Validierung grün, Tabelle „PV-Parameter“ zeigt 41 Zeilen
- [ ] Test-PV-Erfassung → Angebot erzeugen → PDF: drei Wirtschaftlichkeits-
      seiten mit Poppins (sonst Warnung im Log prüfen)
- [ ] Bestehendes PV-Angebot (v16) → PDF neu erzeugen → Seiten vorhanden,
      Verbrauch aus der Erfassung
- [ ] Editor: Häkchen „Wirtschaftlichkeit im PDF ausblenden“, Scroll bleibt,
      Gruppen-Überschrift ✎, BzA-Dialog mit Contracting
- [ ] Parametrierung → Fehlerprotokoll erreichbar (leer)
