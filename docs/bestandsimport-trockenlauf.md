# Bestandsimport – Trockenlauf-Protokoll (PLAN_PROJ_V3 Phase 85)

Stand 30.09.2026 · ausgeführt von Claude Code **ausschließlich gegen Kopien**
der Server-DB (`diagnose\angebotstool.db`, Stand 29.09.2026 15:32), nie gegen
die produktive Datenbank. Jede Kopie wurde vorher mit `migrate.py` auf den
lokalen Stand gebracht.

## Testdatei

Erzeugt aus der Vorlage (`docs/bestandsimport_vorlage.xlsx`), 5 Zeilen:

| Zeile | Inhalt | Zweck |
|---|---|---|
| 2 | vorhandener Kunde, WP, Phase Planung, Montage 10.11. mit Montageteam 1, unbestätigt, Steckbrief Bosch/10 kW | Dublettenpfad + Termin |
| 3 | zweiter vorhandener Kunde, WP, Montagevorbereitung, Montage 03.11., bestätigt | Pauschal-Erledigung |
| 4 | neuer Kunde, WP, Auftragseingang | Neuanlage |
| 5 | derselbe neue Kunde, PV, gleiche TAIFUN-Nr. | zwei Sparten, ein Kunde/Projekt |
| 6 | PLZ 4-stellig, Phase „Abnahme & Freigabe“, Betrag „x“, Datum 32.13., unbekannter Projektleiter/Team | Fehlerzeile |

## Ergebnis Vorschau

- Zeilen 2–5 fehlerfrei; Zeile 6 mit sechs Fehlern (PLZ, Phase – mit Hinweis
  „seit V4 getrennt: Abnahme oder Freigabe“ –, Betrag, Datum, Projektleiter,
  Team) → wird nicht importiert.
- **Auffällig in den Server-Daten:** Die ersten Kunden der DB (#1–#3) sind
  Namensdubletten (gleicher Vor-/Nachname + PLZ). Der Abgleich nimmt dann
  immer den ältesten Treffer (#1). Vor dem echten Import bitte prüfen, ob
  solche Dubletten zusammengeführt werden sollen.

## Ergebnis Import

```
IMPORT #1: angelegt 4, aktualisiert 0, übersprungen 1
  PR-260005 WP Phase planung
  PR-260006 WP Phase montagevorbereitung
  PR-260007 WP Phase auftragseingang
  PR-260007 PV Phase auftragseingang
```

- Zwei WP-Aufträge desselben Kunden (andere TAIFUN-Nummer) bekommen je ein
  eigenes Projekt (im ersten Durchlauf landeten sie als zwei WP-Gewerke in
  einem Projekt – behoben, siehe Entscheidungen).
- Zweiter Lauf mit derselben Datei: **0 angelegt, 4 aktualisiert** – keine
  Dubletten.

## Rückgängig

- Direkt nach dem Import: **4 Gewerke entfernt**, Bestand danach exakt wie
  vorher (Kunden 484 · Projekte 4 · Gewerke 4 · Angebote 176). Vorher
  vorhandene Kunden bleiben immer stehen.
- Nach einem zweiten Lauf gehören die Gewerke dem jüngeren Import; der ältere
  Import entfernt sie dann nicht mehr („seit dem Import geändert – bleibt“).
  Ein Rückgängig des jüngeren Imports entfernt nichts (er hat nur
  aktualisiert).
- Nicht zurückgedreht wird der Projekt-Nummernkreis (PR-26…): nach einem
  Rückgängig bleiben die vergebenen Nummern verbraucht.

## Empfehlung für den echten Import (Stufe 2)

1. Frische Server-DB-Kopie ziehen, Excel mit echten Daten füllen.
2. Claude Code: Import gegen die Kopie, Vorschau + Protokoll prüfen.
3. Erst dann auf dem Server: Parametrierung → Bestandsimport → Vorschau →
   „Fehlerfreie Zeilen importieren“; Kalender und Board kontrollieren.
