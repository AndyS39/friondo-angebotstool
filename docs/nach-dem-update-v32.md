# Nach dem Update v32 (PLAN_V19) – Mein Tag, automatische Wiedervorlage, Nächster Schritt, Bestellung angekündigt, Kundensuche

Dieses Update kommt zusammen mit v31 (PLAN_LEAD_V5, siehe `docs/nach-dem-update-v31.md`) als EIN
Commit auf den Server (Phasen 161–165, abgestimmt 13.10.2026). Rollout nur im Wartungsfenster
(Dienstag 22:30–23:30) nach `docs/betrieb.md`; nach `update.bat` läuft `migrate.py` (zweimal
fehlerfrei, zweiter Lauf ohne Änderungen) und `scripts\smoke.bat`. Die Migration legt die fünf
Ablehnungsgründe an (alte Gründe werden deaktiviert, nicht gelöscht), füllt die Verfolgungsstufe
der Vorgänge aus dem Angebotsstatus und legt die Indizes der Kundensuche an.

## Für alle Rollen – Kundensuche im Hauptmenü

Oben in der Kopfzeile (zwischen Logo und Glocke) steht das Feld **„Kunde suchen …“**. Ab zwei
Buchstaben erscheinen bis zu acht Vorschläge (Name, Ort, Sparten, Verfolgungs-Chip) – Pfeiltasten
und Enter öffnen den Treffer, Escape schließt, Enter ohne Auswahl zeigt alle Treffer als Tabelle.
Gesucht wird nach Vorname, Nachname („Peter M“ findet Peter Müller), Firma, Ort und nach den
letzten Ziffern der Telefonnummer (ab vier Ziffern). Der Klick öffnet die Vorgangsakte des
jüngsten offenen Vorgangs, sonst die Kundenakte. Außendienst findet nur eigene Kunden; Montage
und Projektierung haben kein Suchfeld. Auf dem Handy (unter 600 px) klappt die Lupe das Feld aus.

## Außendienst – „Mein Tag“ auf dem Handy

Der Menüpunkt „Leads VOT“ heißt für euch jetzt **„Mein Tag“** (wer nur die Rolle Außendienst hat,
landet nach dem Anmelden direkt dort): oben **„Fällig heute“** (Anrufe – Angebote, die 3 Werktage
nach dem Versand nachzufassen sind, bei Mehrfamilienhäusern 5), darunter **„Termine heute“**
(überfällige Termine ohne Erfassung ganz oben, rot „überfällig“), **„Heiße Kunden“** (Bestellung
angekündigt / Ampel heiß) und **„Weitere Termine“**. Jede Termin-Karte hat Telefon-Link, Adresse
als Google-Maps-Link und den Knopf „Erfassung starten“ (bei mehreren Objekten steht das Objekt
dabei). In der Anruf-Karte: anrufen, dann einer der drei Knöpfe „Abgelehnt“ · „Bestellung kommt“
· „Nochmal anrufen“; „Notiz zum Gespräch“ landet im Notizen-Chat des Vorgangs; „Letzte
Aktivitäten“ zeigt Versand, Antworten, Notizen und Signaturen. Morgens kommt eine Glocke „Fällig
heute: n Anrufe“. Der Filter (von/bis/Status) ist eine aufklappbare Karte; die Tagesansicht gibt
es auch aus „Meine Termine“ („Zur Tagesansicht“).

## Innendienst/Admin – Leads VOT als Karten oder Tabelle, automatische Wiedervorlage

„Leads VOT“ zeigt standardmäßig die Karten (mit Vertriebler-Filter; mit gewähltem Vertriebler
auch dessen „Fällig heute“ und „Heiße Kunden“), oben rechts **„Karten | Tabelle“** – die bisherige
Tabelle bleibt, die Wahl wird je Nutzer gespeichert. Nach jedem Versand (automatisch erkannt,
„Als versendet markieren“, Kombi, TAIFUN-Eintrag „Extern erledigt“) steht am Vorgang die
Wiedervorlage für den Außendienstler (3 Werktage, bei MFH 5; Chat-Eintrag „Wiedervorlage
automatisch gesetzt“); die Kachel „Fällige Wiedervorlagen“ zählt sie nicht. Die Werktage stehen in
Parametrierung → Angebotstool-Einstellungen → „Nachfassen“.

## Außendienst – nach dem Anruf: drei Knöpfe

In der Vorgangsakte (Block „Verfolgung“ → „Nächster Schritt nach dem Anruf“) und auf der
Anruf-Karte in „Mein Tag“ stehen drei Knöpfe: **Abgelehnt** (rot, ein Klick auf den Grund – bei
„Sonstiges“ bitte kurz schreiben, warum), **Bestellung kommt** (grün, speichert sofort: Kunde
wird „heiß“, Chip „Bestellung angekündigt“, Wiedervorlage in 7 Werktagen, der Innendienst
bekommt eine Glocke) und **Nochmal anrufen** (blau, „In 3 Werktagen“ ist vorgewählt, sonst ein
Datum ohne Uhrzeit). Die Notiz zum Gespräch landet mit dem Schritt im Notizen-Chat. Unter der
Bestätigung steht 10 Sekunden lang „Rückgängig“. „Abgelehnt“ lehnt alle versendeten Angebote
des Vorgangs mit diesem Grund ab und setzt den Lead auf Verloren – wie im Lead-Management
(abgesagte Termine und stornierte Mails kommen bei „Rückgängig“ nicht zurück – Hinweis in der
Meldung).

## Innendienst – Chip, Kachel, Filter, Gründe-Liste

Jeder Vorgang trägt einen Verfolgungs-Chip (Versendet → Nachgefasst → Bestellung angekündigt →
Angenommen | Abgelehnt) – in der Akte neben der Hot-Ampel, in „Meine Angebote“, in der
Angebotsliste als Spalte „Verfolgung“ und als Filter „Verfolgungsstatus“. Auf der Startseite
zählt die Kachel **„Bestellung angekündigt“** (Klick öffnet die gefilterte Angebotsliste). Bitte
die Liste der Ablehnungsgründe prüfen (Parametrierung → Angebotstool-Einstellungen →
Abgelehnt-Prozess): es gelten die fünf Lead-Gründe „Zu teuer · Kein Interesse mehr · Bleibt bei
Öl/Gas · Woanders unterschrieben · Sonstiges“, alte Gründe sind deaktiviert (nicht gelöscht, die
Statistik bleibt), „Sonstiges“ verlangt eine Ergänzung; Reihenfolge per ↑/↓, Häkchen „Freitext
Pflicht“. Neuer Abschnitt „Nachfassen nach Angebotsversand“: 3 Werktage, bei Mehrfamilienhaus 5
(Parameter `nachfass_werktage`, `nachfass_werktage_mfh`).

## Admin

- Nach `migrate.py` einmal die Meldungen „Ablehnungsgründe (v32)“ (angelegt/deaktiviert) und
  „Verfolgungsstatus (v32)“ lesen; die Lead-Excel (Blatt Gruende, Phase verloren) gegen die
  Gründe-Liste halten – zwei Pflegeorte mit denselben Texten.
- Kalender: Werktage = Montag bis Freitag ohne NRW-Feiertage (`app/werktage.py`); die Beispiele
  im Plan („Fr 10.10.2026“) passen nicht zum Kalender 2026 (Samstag) – die Regel gilt, die
  Beispieldaten im Plan sind entsprechend zu lesen.

- Nach dem Rollout einmal `venv\Scripts\python scripts\vot_abgleich.py --data <DB-Kopie>
  --bericht diagnose\vot_abgleich.txt` lesen (Leads mit VOT-Datum ohne Termin-Zeile, Abweichungen);
  der 15-Minuten-Sync hält `vot_termine` seitdem selbst nach (Absage bei gelöschtem monday-Datum,
  Reaktivierung). `--anlegen` nur gegen Kopien unter `diagnose\`.
- Die Glocke „Fällig heute“ (täglich 07:00) ist eine reine Glocke ohne Mail; Demo-Daten für
  Schulungen: `diagnose/v31/m_demo.py` (nur Kopien).

## Rollback

`rollback.bat --nur-code` stellt den v30-Code wieder her; die v31/v32-Datenbank läuft damit weiter
(nur additive Spalten/Tabellen/Trigger/Indizes – in der Rollout-Vorbereitung geprüft).
