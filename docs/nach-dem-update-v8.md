# Nach dem Update auf v8 – Checkliste & Hinweise

## ⚠ Wichtig: einmalige Absage-Welle bei Altfällen (gewollt!)

v8 bringt einen **täglichen Prüflauf**: Versendete Angebote (Tool und
TAIFUN), die seit mehr als **90 Tagen** (Wert in der Parametrierung
änderbar) weder angenommen noch abgelehnt wurden und **keine Wiedervorlage
in der Zukunft** haben, werden automatisch auf **„Abgelehnt"** mit Grund
**„90 Tage Ablauf"** gesetzt.

Beim ersten Lauf nach dem Update trifft das alle entsprechenden Altfälle
auf einmal – die Statistik zeigt dann eine **Absage-Welle**. Das ist
beabsichtigt: Die Abschlussquote wird dadurch ehrlich, statt dass alte
Angebote ewig als „Versendet" mitgezählt werden. Wer einen Altfall noch
aktiv verfolgt, setzt ihm **vor** dem ersten Prüflauf (läuft ca. 2 Minuten
nach dem Serverstart) eine Wiedervorlage in der Zukunft – oder holt ihn
danach einfach per Status wieder auf „Versendet" zurück.

Das Prüflauf-Protokoll steht in der Parametrierung (Abschnitt
„Abgelehnt-Prozess"), jede automatische Ablehnung zusätzlich als Notiz am
Angebot.

## Ablehnungsgründe

Der Statuswechsel auf „Abgelehnt" verlangt jetzt einen **Grund**
(Pflichtdialog, Auswahlliste + optionaler Freitext) – auch bei
TAIFUN-Einträgen. Die Liste ist in der **Parametrierung** pflegbar
(Startwerte: Preis zu hoch · Wettbewerber beauftragt · Förderung
unsicher/abgelehnt · Projekt verschoben · Finanzierung gescheitert ·
Kunde nicht erreichbar · Technisch nicht umsetzbar · Sonstiges). Die
Statistik-Seite zeigt die **Verteilung der Ablehnungsgründe**, filterbar
nach Zeitraum, Vertriebler, Kanal und Sparte.

## Multi-Sparten (WP/PV/KL/WB)

- Beim Erfassungsstart wählt der Außendienst die **Sparten** (die
  Lead-Interessen sind vorausgewählt). Je Sparte entsteht eine eigene
  Erfassung mit eigenem Protokoll.
- **PV und KL** haben eigene Erfassungsbögen (Blätter „Fragen PV" /
  „Fragen KL" in der Logik-Excel), **WB** startet immer im Freitext.
  Alle drei laufen als „individuell" direkt in die TAIFUN-Warteschlange –
  Angebote entstehen dort über „Extern erledigt".
- **Leads VOT** zeigt je Interesse einen **Status-Chip** (WP ✓ · PV offen).
  Der Lead verschwindet erst, wenn alle Interessen erfasst oder
  ausgeblendet sind; einzelne Sparten lassen sich per Klick auf den Chip
  ausblenden.
- „Erledigt (extern)" archiviert **nicht mehr automatisch** – die Fälle
  stehen im Reiter „Erledigt"; die Migration hat früher auto-archivierte
  Fälle einmalig zurückgeholt.

## WP-Bogen & Angebote

- **Heizlast-Abfrage:** Ist die Heizlast bekannt, entscheidet sie über das
  WP-Paket (kWh bleibt Pflicht fürs Protokoll); ab 16 kW → individuell.
- Neue Fragen: Unterverteilung (Pos. 152) mit MID-Zwischenzähler (Z23),
  Wärmemengenzähler (Pos. 096 × Anzahl, bei 2FH/MFH), Stemmarbeiten
  (Pos. 126, Öl-Zweig), getrennte **Rechnungs-/Ausführungsanschrift**
  (monday-Adresse = Ausführungsort; das PDF zeigt die Rechnungsanschrift
  im Empfängerfeld und den Ausführungsort als eigene Zeile; die
  Kunden-Nr. entfällt im Briefkopf).
- Neue Abschluss-Seite **„Einschätzung"** (heiß/warm/kalt +
  Wiedervorlage) liefert die Startwerte der Angebotsverfolgung.
- **Förder-Editor** baustein-basiert: Grundförderung, Klima-Bonus,
  Einkommensbonus (je %) und Höchstkosten (€) einzeln überschreibbar,
  Kennzeichen „Förderung manuell angepasst". Ein alter Gesamt-Override
  aus v6 bleibt sichtbar und wird beim ersten Speichern der Bausteine
  zurückgesetzt.
- **Vollmacht:** alle Ankreuzfelder sind wieder leer (Kunde kreuzt selbst an).
- **„Meine Angebote":** der Außendienst sieht seine Angebote read-only
  inkl. Kundenpreisen und PDF – ohne EK/DB, ohne Editor/Versand.

## Nichts weiter zu tun

Die Migration läuft komplett über update.bat (neue Spalten, Gründe-Seed,
Lead-Verknüpfungen, Archiv-Rückholung). Preisliste/Zusatzartikel wurden um
**Z23** ergänzt – beim nächsten „Preisliste importieren" bleibt alles
konsistent. Die Logik-Excel ist weiterhin die Live-Datei im Projektordner
(Backup unter data/backups/konfigurator_logik_v5_vor_v8_*.xlsx).
