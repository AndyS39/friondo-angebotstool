# Nach dem Update auf v7 – Zwei-Wege-Prozess (Tool + TAIFUN)

Kurzinfo für das Team nach dem `update.bat`-Lauf. v7 bringt keinen neuen
Pflege-Aufwand in der Parametrierung – wichtig sind zwei Dinge:

## 1. Alte „Individuell“-Fälle tauchen bewusst wieder auf

Bis v6 wurden als „Individuell" markierte Erfassungen automatisch archiviert.
Die Migration hat **alle diese Fälle reaktiviert**: Sie stehen jetzt sichtbar
in der Erfassungsliste im Tab **„In TAIFUN zu schreiben"** und auf der
Startseite in der Kachel **„Individuell offen"**.

Das ist kein Fehler, sondern gewollt – diese Vorgänge waren bisher „Leichen"
ohne Abschluss. Bitte einmal durchgehen: Für jeden Fall entweder das Angebot
in TAIFUN schreiben und den Dialog **„Extern erledigt"** ausfüllen, oder den
Vorgang löschen, falls er sich erledigt hat. Jeder reaktivierte Fall trägt
einen Vermerk im Änderungsprotokoll.

## 2. Kurzanleitung Zwei-Wege-Prozess (Innendienst)

**Weg 1 – Tool (Standard):** wie bisher. Außendienst füllt den
Erfassungsbogen aus, grüne Fälle → „Angebot erzeugen", Versand über das Tool.

**Weg 2 – TAIFUN (individuelle Fälle):**

1. **Eingang:** Individuelle Fälle entstehen auf zwei Arten:
   - Der Außendienst wählt nach der Kundenauswahl die **Freitext-Erfassung**
     (oder wechselt mitten im Bogen per „In Freitext wechseln"). Diese Fälle
     stehen sofort im Tab **„In TAIFUN zu schreiben"**.
   - Ein Katalog-Fall kommt mit **oranger Ampel** herein → Status
     **„Individuell – zu prüfen"**. Der Innendienst entscheidet dort per
     Button: **„Doch konfigurierbar"** (zurück auf den normalen Tool-Weg,
     Antworten korrigierbar) oder **„Individuell bestätigt"** (→ Warteschlange).
2. **Abarbeiten:** Tab „In TAIFUN zu schreiben" ist die Arbeitsliste. Das
   **Protokoll-PDF** (Button direkt in der Liste) ist der Übergabezettel
   zum Abschreiben in TAIFUN – bei Freitext-Erfassungen steht die freie
   Beschreibung oben, darunter ggf. die Teilantworten aus dem Katalog.
3. **Abschließen:** Nach dem Schreiben in TAIFUN auf der Erfassung den Dialog
   **„Extern erledigt"** ausfüllen: Endbetrag brutto (Pflicht), Datum,
   TAIFUN-Angebotsnummer (optional – lässt sich am Eintrag nachtragen,
   solange sie fehlt, zeigt die Angebotsliste „Nummer fehlt").
4. **Danach automatisch:** Es entsteht ein Eintrag in der Angebotsliste mit
   Badge **„TAIFUN"** und Status **„Versendet (extern)"** – ohne PDF, Editor
   und Mail-Versand, aber mit Verfolgung (Ampel/Wiedervorlage/Notizen) und
   Statuspflege **Angenommen/Abgelehnt** (zählt in die Abschlussquote).
   Die monday-Rückspielung (Deal-Status + Deal-Wert) läuft wie bei
   Tool-Angeboten. Die Erfassung steht auf „Erledigt (extern)" im Archiv.

## 3. Statistik

Die Statistik weist Angebote jetzt getrennt aus: **Tool · TAIFUN (extern) ·
gesamt** (Anzahl, Auftragswert, Abschlussquote). Der Deckungsbeitrag lässt
sich nur für Tool-Angebote berechnen – bei TAIFUN-Einträgen ist nur der
Endbetrag brutto bekannt. In den Tabellen „Je Vertriebler" und „Je Kanal"
zeigt die Spalte „davon TAIFUN" die externen Anteile (versendet/angenommen).

## Hinweis

Der Status „Individuell" bei **Angeboten** archiviert nicht mehr automatisch –
wer ein Tool-Angebot als individuell markiert, sollte den Vorgang künftig
besser gleich über die Erfassungs-Kette (Weg 2) laufen lassen.
