# UGL-Format (Bestellung Collin) – Feldtabelle und Annahmen

Stand: 29.09.2026 (PLAN_PROJ_V4, Phase 93.2) · Umsetzung: `app/ugl.py`

Quelle: „UGL Version 4 – Beschreibung Datenaustausch Handwerk ↔ Großhandel“
(öffentlich als PDF, z. B. über Schrack Technik / GC-Umfeld). Die Feldtabelle
unten ist daraus übernommen, beschränkt auf das, was das Tool schreibt.

## Grundregeln

- Feste Satzlänge **200 Byte**, danach **CR/LF** (202 Byte je Zeile).
- Numerische Felder rechtsbündig mit führenden Nullen, Komma implizit
  (Menge 11,3: 12,5 → `00000012500`).
- Alphanumerische Felder linksbündig, mit Leerzeichen aufgefüllt.
- Satzfolge: `KOP` → `ADR` → je Artikel `POA` (+ `POT`) → `END`.
- Anfrageart **BE** (Bestellung / Lieferauftrag Handwerk → Großhandel).
- Preise, Rabatte, Netto-Werte bleiben **0** – der Großhandel füllt sie.

## KOP – Kopfsatz

| Stelle | Länge | Inhalt im Tool |
|---|---|---|
| 1–3 | 3 | `KOP` |
| 4–13 | 10 | Kundennummer Friondo bei Collin (`collin_kundennummer`) |
| 14–23 | 10 | Lieferantennummer Collin bei Friondo (`collin_lieferantennummer`, optional) |
| 24–25 | 2 | `BE` |
| 26–40 | 15 | Anfragenummer = **PR-Nummer**, Nachbestellung `PR-…-2` |
| 41–90 | 50 | Kundenauftragstext: `Kommission PR-… Nachname Sparte [Nachbestellung]` |
| 91–105 | 15 | Vorgangsnummer GH (leer) |
| 106–113 | 8 | Lieferdatum `JJJJMMTT` (Vorschlag Montagebeginn − 3 Werktage) |
| 114–116 | 3 | `EUR` |
| 117–121 | 5 | `04.00` |
| 122–161 | 40 | Sachbearbeiter (angemeldeter Benutzer) |
| 162–169 | 8 | Dokumentdatum `JJJJMMTT` |

## ADR – Lieferadresse

| Stelle | Länge | Inhalt |
|---|---|---|
| 1–3 | 3 | `ADR` |
| 4–33 | 30 | Name 1: `Baustelle <Kunde>` bzw. 1. Zeile der Lager-Adresse |
| 34–63 | 30 | Name 2: `Kommission PR-…` |
| 64–93 | 30 | Name 3: Bemerkung (gekürzt) |
| 94–123 | 30 | Straße |
| 124–126 | 3 | Land (leer = D) |
| 127–132 | 6 | PLZ |
| 133–162 | 30 | Ort |

## POA – Artikelposition

| Stelle | Länge | Inhalt |
|---|---|---|
| 1–3 | 3 | `POA` |
| 4–13 | 10 | Positionsnummer HW (10, 20, 30 …) |
| 14–23 | 10 | Positionsnummer GH (0) |
| 24–38 | 15 | Artikelnummer Collin (Stückliste Spalte B) |
| 39–49 | 11 (3 NK) | Menge = Angebotsmenge × Menge je Einheit, je Artikelnummer summiert |
| 50–89 | 40 | Bezeichnung 1 |
| 90–129 | 40 | Bezeichnung 2 (Rest der Bezeichnung) |
| 130–140 | 11 | Preis (0) |
| 141 | 1 | Preiseinheit (0) |
| 142–152 | 11 | Netto-Positionswert (0) |
| 153–157 / 158–162 | 5 / 5 | Rabatt 1 / 2 (0) |
| 163–180 | 18 | LV-Nummer (leer) |
| 181 | 1 | Alternativ-Kennzeichen (leer) |
| 182 | 1 | Positionstyp `H` |
| 183 | 1 | Vorbehalt (leer) |
| 184–186 | 3 | Mengeneinheit (Stückliste Spalte F, Standard `ST`) |
| 187 / 188 | 1 / 1 | Preis-Kz. / Lager-Kz. (leer) |

## POT – Positionstext (optional)

| Stelle | Länge | Inhalt |
|---|---|---|
| 1–3 | 3 | `POT` |
| 4–13 | 10 | Positionsnummer HW (wie POA) |
| 14–23 | 10 | Positionsnummer GH (0) |
| 24–63 | 40 | Infotext 1: `Angebotsposition 047, 048` |
| 64–143 | 80 | Infotext 2/3 (leer) |
| 144–161 | 18 | LV-Nummer (leer) |

## END – Endesatz

| Stelle | Länge | Inhalt |
|---|---|---|
| 1–3 | 3 | `END` |
| 4–43 | 40 | Zusatztext 1: `Bestellung PR-…` |
| 44–83 | 40 | Zusatztext 2: Bemerkung |
| 84–163 | 80 | Zusatztext 3/4 (Rest der Bemerkung / leer) |

## Annahmen (mit Collin abgleichen)

1. **Zeichensatz:** Die Spezifikation sagt „deutsche Sonderzeichen wie in
   Datanorm 4.0“ – umgesetzt als **Codepage 850 (DOS)**. Falls GC Online Plus
   Umlaute falsch anzeigt: Konstante `ZEICHENSATZ` in `app/ugl.py` auf
   `cp437` oder `latin-1` stellen.
2. **Dokumentdatum:** Die Spezifikation nennt für KOP 162–169 „JJJMMTT“ bei
   8 Stellen – vermutlich Tippfehler; geschrieben wird `JJJJMMTT` wie beim
   Lieferdatum.
3. **POZ vs. POT:** Der Plan nennt „POZ (Positionstext)“. Laut Spezifikation
   ist **POZ = Zuschläge**, Positionstexte sind **POT** – das Tool schreibt POT.
4. **Dateiname:** Die Spezifikation sieht `A` + `JJJMMTT` + `.nnn` vor
   (z. B. `A0260929.001`). Für den **manuellen Upload** in GC Online Plus
   verwendet das Tool den sprechenden Namen `PR-….ugl` bzw. `PR-…-2.ugl`
   (Nachbestellung). Verlangt Collin das Spezifikationsschema, nur die
   Namensbildung in `ugl_erzeugen` ändern.
5. **Lieferantennummer (KOP 14–23):** optional; leer, solange nicht hinterlegt.
6. Preise bleiben leer (0) – Konditionen kommen aus der Auftragsbestätigung.

## Testdatei und Begleittext

`docs/ugl-beispiel.ugl` – fiktive Bestellung (Kundennummer `0000123456`,
Artikelnummern `BEISPIEL-…`, 4 Positionen inkl. Meterware `M` und Umlauten).

Begleittext zum Kopieren:

> **Betreff:** UGL-Testdatei Friondo GmbH – Bitte um Prüfung
>
> Hallo [Ansprechpartner],
>
> wir möchten Bestellungen künftig als UGL-Datei (Version 4.0, Anfrageart BE)
> über GC Online Plus hochladen. Anbei eine Testdatei mit fiktiven
> Artikelnummern. Könnten Sie bitte prüfen, ob
>
> 1. Aufbau und Feldpositionen (KOP, ADR, POA, POT, END) passen,
> 2. der Zeichensatz (Codepage 850) für Umlaute korrekt verarbeitet wird,
> 3. Lieferdatum, Lieferadresse und Kommissionsnummer richtig ankommen,
> 4. Sie eine Lieferantennummer in KOP 14–23 oder ein bestimmtes
>    Dateinamensschema erwarten?
>
> Außerdem bräuchten wir unsere Kundennummer für den UGL-Import bestätigt.
>
> Vielen Dank und viele Grüße
> Friondo GmbH

Nach der Bestätigung: in *Parametrierung → Stücklisten* den Go-live-Prüfpunkt
„Testdatei von Collin bestätigt“ abhaken.
