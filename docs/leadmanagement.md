# Lead-Management V1 – Bedienanleitung (v12, Demo)

Grundlage: LEADMANAGEMENT-KONZEPT.md (abgestimmt 22.09.2026). V1 läuft als
**Demo im Live-Tool**: `lead_freigabe_modus = admin` (Standard) – nur Admins
sehen das Modul (alle Routen server-seitig, 404 für andere), das Startportal
trägt das Badge „Demo · Coming soon“. **monday läuft unverändert weiter**
(Lesesync + Rückspielung unangetastet); im Modul angelegte Leads tragen
`demo = 1` und erscheinen nirgends außerhalb des Moduls. Sperren im Demo:
keine Kundenmails (`mail_modus` protokoll/test), Kalender nur ins
Testpostfach, monday-Leads nicht buchbar.

## 1. Eingangswege

- **Schnellanlage** (Anrufliste → „+ Neuer Lead“, auch mobil): Name, Telefon
  (Pflicht, ersatzweise E-Mail), PLZ, Sparten, Quelle – Duplikate werden
  erkannt (Telefon E.164, E-Mail, Name+PLZ, Adresse): offener Vorgang →
  anhängen (neue Sparte), abgeschlossener → neuer Vorgang „Wiederkehrer“.
- **CSV/Excel-Import**: Upload → Spaltenzuordnung (je Quelle gespeichert) →
  Vorschau mit Duplikat-Markierung → Protokoll (angelegt/angehängt/
  übersprungen mit Grund).
- **REST-API** `POST /api/leads` mit `X-Api-Key` je Quelle
  (docs/leads-api.md), Rate-Limit 60/min, 409 bei Duplikat-Anhängung.
- **Mail-Parser** (Postfach leads@friondo.de, Abruf alle 2 Minuten – nur bei
  `parser_modus = an`): Regeln je Quelle (zeilen/html_tabelle/json) mit
  Test-Funktion; Formular-Standard für die Agentur: Betreff
  `[LEAD] <quelle> <kampagne>`, Body `Feld: Wert`. Nicht erkannte Mails →
  **Posteingang unklar** (Ein-Klick-Anlage oder Ignorieren); Antworten mit
  Betreff „Rückruf V<Nr>“ oder AN-C-Nummer landen als Aktivität am Vorgang.
- Jeder Eingang: Eingangsbestätigung (Warteschlange), vorläufiger Score
  (Kerngebiet + Quellen-Bonus), Round-Robin-Zuweisung (lm_aktiv-Benutzer),
  Glocken-Benachrichtigung, SLA-Timer (Arbeitszeit Mo–Fr).

## 2. Anrufliste und Kaskade

- **/lead-management/anrufliste** ist die Arbeitsseite: sortiert nach
  (1) SLA gelb/rot, (2) fällige Aktionen/Rückrufe, (3) fällige
  Zurückgestellte, (4) Rest nach Score-Klasse. Klick auf den Namen öffnet
  die Akte als Seitenpanel; Tastatur 1–7 für die Ergebnis-Buttons.
- **Ein Klick je Anruf**: Erreicht → Qualifizierungsbogen · Nicht erreicht/
  Besetzt/Mailbox → Kaskade (+2 h · +1 Tag 18:00 · +3 Tage · +7 Tage, danach
  „Nicht erreicht“ +30 Tage mit Nurture-Mail) · Rückruf gewünscht (Datum
  Pflicht) · Falsche Nummer (Kennzeichen) · Kein Interesse (Grund Pflicht →
  Unqualifiziert). Zurückstellen mit Datum+Grund; der 07:00-Lauf holt
  fällige zurück auf „Neu“.

## 3. Qualifizierung und Score

- Bogen je Sparte als Gesprächsleitfaden (eine Frage je Block, Enter =
  weiter, Live-Score, Hinweis bei Ausschluss-Antworten); gemeinsame Fragen
  (Eigentümer, Zeitrahmen, Wunschzeiten) werden nur einmal gefragt und in
  die anderen Sparten übernommen.
- Fragen/Punkte/Klassen/Kaskade/Gründe/Wunschzeiten pflegt Andreas in
  `leadmanagement_logik_v1.xlsx` (Parametrierung → Lead-Steuerdatei);
  Bedingungen wie `=Öl` bitte als Text eingeben (führendes Apostroph in
  Excel) – der Import liest beides.
- Antworten belegen später den AD-Erfassungsbogen vor (Kennzeichen „aus
  Qualifizierung“) – aktiv erst bei Freigabe „alle“.

## 4. Terminassistent und Kalender

- **Termin vorschlagen** (Akte, Anrufliste, Qualifizierungs-Abschluss):
  Top 5 Slots über AD-Profile (Startadresse, Arbeitszeiten, Dauer/Puffer/
  Max je Tag; Benutzerverwaltung → AD-Profil), Tool-Termine (auch aus dem
  monday-VOT-Datum), optional Outlook-Frei/Belegt, Fahrzeiten
  (openrouteservice/Google/Luftlinie „geschätzt“; Parametrierung →
  Lead-Routing). Bewertung: Umweg − Wunschzeit − Tour-Tag + leerer Tag +
  Randzeit (Klasse A bevorzugt früh); Mini-Karte zeigt die Tagestour.
- **Buchen**: Termin + Kalender-Ereignis (nur bei `kalender_sync = an`; im
  Demo ausschließlich Testpostfach) + Bestätigung mit ICS + Erinnerung
  −24 h + Glocke an den AD. Umbuchen über den Assistenten (Kunde erhält
  Terminänderung), No-Show/Absage mit Grund → Lead zurück auf Qualifiziert.
- **Terminkalender** (Woche je AD): Ziehen = Umbuchen mit Bestätigung;
  monday-Termine sind gesperrt („in monday ändern“).
- Geokodier-Fehler landen in **Adresse prüfen** (Koordinaten manuell).

## 5. Kommunikation (Sendesperre)

Sechs Vorlagen (Parametrierung → Lead-Vorlagen, optional je Sparte):
Eingangsbestätigung, Nicht erreicht, Terminbestätigung (mit
Vorbereitungs-Checkliste + ICS), Erinnerung, Terminänderung, Nurture (nur
mit Werbe-Einwilligung). Warteschlange je Minute nach `mail_modus`:
**protokoll** = rendern ohne Senden (Demo-Standard, Vorschau in der Akte) ·
**test** = an die Testadresse mit „[TEST an …]“ · **live** = an den Kunden
(nur bei Freigabe „alle“ zulässig). Absender leads@friondo.de (Fallback
angebot@); Reiter „Kommunikation“ in der Akte mit „Jetzt senden“ und
„Mail mit Vorlage“.

## 6. Board, Karte, Cockpit, Statistik

- **Pipeline** (Kanban): Neu → … → Gewonnen | Verloren (eingeklappt);
  Seitenzustände per Häkchen; Ziehen nur nach Zurückgestellt/Unqualifiziert
  (Dialog) bzw. Reaktivieren – Terminieren nur über den Assistenten.
  Spaltenköpfe ab „Terminiert“ mit Summe der Erwartungswerte.
- **Karte**: Leaflet (lokal) mit OSM-Kacheln – Leads (Farbe je Phase, Größe
  je Klasse), Termine, AD-Startadressen.
- **Cockpit**: heute/Woche je Leadmanager, je AD (Termine/No-Shows),
  SLA-rot-Liste, Pipeline-Wert.
- **Statistik → Leads**: Trichter, Speed-to-Lead, Kontakt-/Termin-/
  Show-Quoten, Durchlaufzeiten, Gründe; **Kanal-Report** (Kosten je
  Lead/Termin/Auftrag, CSV).

## 7. Rollen

- **Admin**: alles (Demo-Phase). **Innendienst**: alles ab Freigabe „alle“.
- **Leadmanagement** (Haupt-/Zusatzrolle): Lead-Modul voll, Kunden,
  Vorgangsakte; Angebote nur Liste+PDF (keine EK/DB), Erfassungen lesend;
  Parametrierung nur Quellen & Kampagnen + Steuerdatei. Round-Robin über
  das Häkchen „LM aktiv“ in der Benutzerverwaltung.
- **Außendienst** (ab „alle“): Lead-Akte read-only, **No-Show melden** und
  **Termin verschieben** (nur eigene Termine, nur dieselbe Woche; Kunde
  wird informiert, Leadmanager benachrichtigt), mobile Seite
  **Meine Termine** (Navigation, Telefon, Steckbrief).

## 8. Parametrierung und Datenschutz

Parametrierung → **Lead-Einstellungen** (nur Admin): Demo-Schalter (bei
Umstellung auf „alle“ Pflicht-Entscheidung über die Demo-Leads: löschen
oder behalten + Kennzeichen entfernen), Mail-/Parser-/Kalender-Schalter,
SLA-Minuten, Arbeitszeit, Horizont/Raster, Kerngebiet-PLZ, Erwartungswerte
und Phasen-Quoten, **Löschlauf** (täglich 03:00, `loeschfrist_monate`,
Anonymisierung Unqualifiziert/Nicht erreicht/Verloren ohne Auftrag/Projekt,
Vorschau „Was würde gelöscht?“) und die Protokolle. Demo-Daten-Generator
unter Lead-Demo-Daten (25 fiktive Leads, Ein-Klick-Löschung).
