# Nach dem Update auf v6 – Checkliste

Diese Punkte einmalig nach dem `update.bat`-Lauf auf dem Terminal Server
erledigen. Reihenfolge egal, alles zusammen ca. 15 Minuten.

## 1. Personen-Zuordnung vervollständigen (Leads ohne Außendienstler)

Die Migration hat allen Leads, deren monday-Person bereits zugeordnet ist,
rückwirkend den Außendienstler eingetragen. Neu in v6: Trägt monday eine
**E-Mail-Adresse** als Person ein, findet das Tool den Benutzer automatisch
über seine E-Mail aus der Benutzerverwaltung. Zwei Fälle bleiben offen:

1. **Parametrierung → Personen-Zuordnung** öffnen und prüfen, ob dort noch
   Personen ohne Zuordnung stehen. Bekannt aus den Daten:
   - **P. Diblasi** – dazu gibt es noch keinen Benutzer im Tool. Benutzer
     anlegen (Benutzerverwaltung, Rolle Außendienst, **mit E-Mail**), danach in
     der Personen-Zuordnung zuweisen. Die Zuordnung wirkt sofort rückwirkend
     auf alle vorhandenen Leads.
   - **Ioannis Simeonidis** – klären, ob das ein aktiver Außendienstler ist;
     falls ja, ebenso anlegen und zuordnen.
2. In der **Benutzerverwaltung** bei allen Außendienstlern die **E-Mail**
   eintragen (falls noch leer) – dann greift das automatische E-Mail-Matching
   auch für künftige Leads ohne manuelle Zuordnung.

Kontrolle: **Leads (VOT)** öffnen – der gelbe Hinweis „x Leads ohne
Außendienstler" sollte danach verschwinden bzw. deutlich kleiner werden.

## 2. Vertriebskanal aus monday übernehmen

Der Vertriebskanal wird beim 15-Minuten-Abgleich aus einer Spalte des
monday-Boards gelesen. Dafür je Board einmalig die Spalte hinterlegen:

**Parametrierung → monday-Anbindung** → beim jeweiligen Board die Spalte
**„Vertriebskanal"** auswählen (beim Deals-Board ist das die Status-Spalte
„Vertriebskanal", interne ID `color_mkyp1qm6`) → Speichern.

Beim nächsten Abgleich füllt sich der Kanal bei Leads und wird beim Anlegen
des Kunden übernommen. Sichtbar als Filter + Badge in Leadliste und
Angebotsliste sowie in der Statistik („Je Kanal").

## 3. Outlook-Signaturen der Innendienst-Mitarbeiter hochladen

E-Mails gehen ab v6 als **HTML** raus, mit der echten Outlook-Signatur des
angemeldeten Mitarbeiters (inkl. Logos/Bildern). Je Mitarbeiter einmalig:

1. Auf dem PC des Mitarbeiters den Ordner
   `%APPDATA%\Microsoft\Signatures` öffnen (Windows-Taste + R, den Pfad
   einfügen, Enter).
2. Die **.htm-Datei** der gewünschten Signatur **und den zugehörigen
   Datei-Ordner** (z. B. `Signatur-Dateien/` mit den Bildern) kopieren.
3. Im Tool: **Parametrierung → Signaturen** → Mitarbeiter wählen → alle
   Dateien (die .htm + alle Bilder) zusammen hochladen. Die Vorschau zeigt
   sofort, ob Bilder und Formatierung stimmen.

Ohne hochgeladene Signatur nimmt das Tool eine einfache
Standard-Textsignatur der Friondo GmbH. Details: `docs/signaturen.md`.

## 4. Kurz erklärt: die neuen v6-Funktionen

- **Angebotsverfolgung**: Im Angebots-Editor gibt es den Block „Verfolgung"
  mit Ampel (🔥 heiß / 🌤 warm / ❄ kalt), Wiedervorlage-Datum und Notizen.
  Fällige Wiedervorlagen erscheinen rot in der Angebotsliste (Filter
  „Wiedervorlage fällig") und als Kachel auf der Startseite.
- **Statistik**: Neuer Menüpunkt für Admin/Innendienst (Zeitraum wählbar:
  Woche/Monat/Quartal/Jahr/frei) mit Leads, Erfassungen, Angeboten,
  Auftragswert, DB und Quote – gesamt, je Vertriebler und je Kanal.
  Außendienstler sehen unter „Meine Statistik" nur die eigenen Zahlen.
- **Status „Individuell"**: Für Erfassungen und Angebote, die außerhalb des
  Tools geschrieben werden. Beim Setzen wird der Vorgang automatisch
  archiviert und liegt nicht mehr als „Leiche" in den Listen.
- **Versendete Angebote** sind jetzt für Innendienst und Admin änderbar und
  löschbar. Jede Löschung eines Nicht-Entwurfs landet im **Lösch-Protokoll**
  (Parametrierung), die Angebotsnummer wird nie neu vergeben.
- **Förderung im Angebot**: Im Editor kann der KfW-Zuschuss manuell
  überschrieben oder der Förderblock komplett aus dem PDF ausgeblendet
  werden.
- **Artikeltexte im Angebot**: Bezeichnung und Beschreibung jeder Position
  sind direkt im Editor änderbar; lange Texte lassen sich aufklappen.
  Zusätzlich je Position ein **EP-Kästchen** (wie „bauseits").
- **E-Mail-Vorlagen** haben jetzt einen Formatierungs-Editor
  (fett/kursiv/Listen/Links); der Versand ist durchgängig HTML.

## Noch offen aus v5 (falls nicht schon erledigt)

- `MONDAY_API_TOKEN` in der `.env` auf dem Server (monday-Abgleich).
- M365-Admin: „Senden als" für angebot@friondo.de + Graph-Berechtigungen
  laut `docs/graph-einrichtung.md`, Abschnitt 3/3a.
