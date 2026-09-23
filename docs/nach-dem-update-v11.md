# Nach dem Update: Team-Feedback-Paket (PLAN_V11, intern v13)

Hinweis zur Zählung: Dieses Paket wurde als „Plan v11" beauftragt; im
Tool heißt der Abschnitt in CLAUDE.md „Neu in v13", weil v11
(Projektierung) und v12 (Lead-Management) bereits vergeben waren.

## Für das ganze Team

- **50-l-Puffer:** Bei den 3800er-Klassen (4–13 kW) wird der 50-l-Puffer
  nicht mehr als eigene Position berechnet – er steckt laut TAIFUN-Text
  im Paket (AN-C-261082). Angebote werden dadurch 405,00 € netto
  günstiger als bisher. Größere Puffer (100/200/300/500 l) kommen
  unverändert als Zusatzposition.
- **CS8800 (15 kW):** Außeneinheit steht jetzt auf Position 1,
  Inneneinheit auf Position 2, danach Puffer/Warmwasser (AN-C-261127).
  Wenn eine ältere Erfassung noch offene Fragen hat (z. B. Farbe/
  Puffer der Serie CS8800i), verweigert „Angebot erzeugen" mit einer
  klaren Meldung – bitte die Erfassung öffnen und vervollständigen,
  statt ein unvollständiges Angebot zu bekommen.
- **Sortieren im Editor:** Eine per Drag & Drop verschobene Position
  gehört jetzt automatisch zu dem Block, in den sie gezogen wurde –
  die Blocküberschrift bleibt immer über der ersten Position.

## Konfigurator / Erfassung

- **Verbrauch unbekannt:** Bei „Aktueller Verbrauch (kWh)" gibt es die
  Checkbox „Verbrauch unbekannt". Dann fragen zwei Folgefragen die
  beheizte Wohnfläche und den Gebäudestandard ab (saniert 40 /
  Altbau 60 / unsaniert 70 W/m²); die Heizlast wird daraus berechnet
  und die Herleitung steht im Protokoll und im Angebot.
- **Auslegungszeile:** Jedes WP-Angebot trägt in Block 1 eine
  0,00-€-Zeile mit der Auslegung (kWh, Heizlast oder Flächen-
  Herleitung). Der Wortlaut ist vorläufig, bis das TAIFUN-Muster
  vorliegt (Zulieferung 4).
- **Dachaufstellung:** Bei Aufstellort „Garagendach" wird jetzt die
  Fassadenleitung abgefragt (wie bei OG) und der mobile Kran ist eine
  eigene Ja/Nein-Frage – die automatische Kran-EP-Position entfällt.
- **Öltank ab 9.000 l:** Neue Nachfrage „Tatsächliche Tankgröße in
  Litern" fürs Protokoll (der Fall bleibt individuell).
- **Dachzentrale → Keller:** Neue Frage „In welcher Etage liegen die
  Anschlüsse?" – gleiche Etage (KG) = Pauschale 141 wie bisher;
  andere Etage = getrennte Meterabfragen für Heizung (Pos. 139) und
  Warmwasser (Pos. 140). Der Vermerk zur Heizungsumverlegung erscheint
  als 0,00-€-Position Z25 im Montage-Block (nicht mehr als Textabsatz).

## Editor / Angebote

- **Freitextpositionen** brauchen keine Bezeichnung mehr (dann zeigt
  das PDF nur die Beschreibung) und haben ein EK-Feld (netto) für den
  korrekten Deckungsbeitrag.
- **Abweichende Lieferanschrift** (z. B. Contracting): optionales Feld
  in der Erfassung (Objektdaten) und im Editor; eigene Zeile im PDF.
- **„Für anderen Kunden kopieren":** Neuer Knopf im Editor. Zielkunde
  wählen oder direkt anlegen; es entsteht ein neues Angebot (neue
  Nummer, Entwurf) am Vorgang des Zielkunden mit allen Positionen und
  Einstellungen. WICHTIG: Die Förderdaten werden mitkopiert und sind
  im Editor als „Kopie von AN-… – Förderdaten prüfen" markiert –
  bitte immer prüfen, sie gehören ggf. nicht zum neuen Objekt.
- **Zusatzartikel „Elektroarbeiten – im PV-Angebot enthalten" (Z26):**
  für Kombi-Fälle; kommt beim Einfügen automatisch als
  Alternativ-Position mit Verknüpfung „PV-Angebot" (0,00 €).

## Außendienst

- **Statuswechsel:** Der AD kann eigene Angebote auf Angenommen /
  Abgelehnt / zurück auf „Versendet (offen)" setzen. Ablehnung nur mit
  Grund; jeder Wechsel steht im Notizen-Chat des Vorgangs;
  monday-Summen und Statistik laufen wie beim Innendienst.
- **Rabatt entfernen:** Eingabe 0 (oder Feld leeren) setzt den Rabatt
  zurück – keine Fehlermeldung mehr.

## Versand / Innendienst

- **Versand-Erkennung:** Mails, die ein ID-Mitarbeiter „im Auftrag"
  aus dem eigenen Postfach sendet, werden jetzt erkannt (alle
  Benutzer-Adressen zählen als eigene Absender). Jeder Prüflauf wird
  protokolliert: Parametrierung → „Versand-Erkennung: Protokoll der
  letzten Prüfläufe" zeigt, WARUM etwas (nicht) erkannt wurde.
- **„Als versendet markieren":** Der Button am Angebot ist nur der
  FALLBACK, wenn die automatische Erkennung nicht greift – er
  schreibt eine Protokoll-Notiz und löst die normale
  monday-Rückspielung aus.
- **Profilabhängige Anhänge:** Enni- und SWD-Angebote gehen ohne
  „Broschüre Ratenkauf" und „Friondo SpotDynamic" raus (Spalte
  „Nicht bei Profil" im Anhänge-Blatt der Logik-Excel).
- **Externe TAIFUN-Einträge** lassen sich vollständig ablehnen
  (Pflichtgrund, monday-Summen-Neuberechnung).

## Noch offen – Zulieferungen nachziehen

1. **Monoenergetische Klassengrenzen** (Andreas/Janni): neue Grenzen in
   die Paketmatrix (kWh- und Heizlast-Spalte) eintragen, danach
   Kontroll-Szenarien neu abnehmen (Checkbox in PLAN_V11.md offen).
2. **VK-Preisliste** (Janni/TAIFUN-Export): über Parametrierung →
   Preisliste importieren, Import-Protokoll prüfen, ein
   Kontroll-Angebot vorher/nachher vergleichen (Checkbox offen).
3. **Broschüre „Bosch CS8800iAW.pdf"** in den Ordner anlagen/ legen –
   die Anhangsregel ist aktiv, bis dahin erscheint die
   „Datei fehlt"-Warnung.
4. **TAIFUN-Muster** (Wortlaut Auslegungszeile + Text Position 124):
   danach die Auslegungszeile in app/konfigurator.py
   (auslegungs_text) anpassen und die Aktionszeile „D01 = Nein"
   von Z25 auf „Pos. 124" umstellen (Achtung: aktuell ist 124 in der
   Preisliste ein Raumthermostat – erst nach neuem TAIFUN-Export
   wechseln).

## Rollout

Wie immer: auf dem Terminal-Server `update.bat` ausführen (Backup →
git pull → pip → migrate.py → Dienststart). Die Migration ergänzt nur
zwei Spalten am Angebot (Lieferanschrift, Kopie-Kennzeichen) und ist
idempotent. Danach im Browser einmal Strg+F5.
