# Nach dem Update v25 (PLAN_LEAD_V3) – Lead-Management V3: Feedback-Runde nach V2

Dieses Update setzt das Feedback von Claudia Castro (05.10.2026) zum Lead-Modul um.
Alles bleibt im **Demo-Modus** (`lead_freigabe_modus = admin`); Angebotstool,
Projektierung und monday-Sync sind unverändert.

## Für das Leadmanagement / den Innendienst

- **Neue Menüreihenfolge** in der linken Icon-Leiste: Mein Dashboard · Hauptboard ·
  Deals · Kontaktiert · Karte · Infoabend · To-Dos · Handelsvertreter · Mehr …
  (Anrufliste, Kanban, Kalender, E-Mail-Vorlagen, Übersicht/Statistik, Kanal-Report,
  Posteingang, Import, Schnellanlage, Lead-Einstellungen). Kein Einstieg ist
  weggefallen.
- **„Deals“** ist der neue Name des Boards „Terminiert“ (Leads mit Vor-Ort-Termin,
  Angebotsnachverfolgung); **„Infoabend“** heißt die bisherige Info-Veranstaltung.
  Die Lead-Phase „Terminiert“ bleibt als Statuslabel bestehen.
- **Status „Kontaktiert“**: die Phasen „In Kontaktierung“ und „Qualifiziert“ zeigen
  beide das Label „Kontaktiert“ (Boards, Kanban, Kartei, Anrufliste, Dashboard,
  Statistik-Trichter). Intern bleiben beide Phasen bestehen.
- **Spalten selbst einstellen** (Hauptboard, Deals, Infoabend, Handelsvertreter):
  Spaltenkopf anklicken = sortieren, Stift = umbenennen, „Spalten“ in der
  Filterleiste = ein-/ausblenden, Spaltenkopf ziehen = verschieben, „Zurücksetzen“
  = Standard. Alles gilt nur für den eigenen Benutzer und je Board getrennt
  (Infoabend und Handelsvertreter-Ansicht haben ihre eigene Einstellung).
  Anrede, Vorname und Nachname sind standardmäßig ausgeblendet, die Spalte
  „Kundenname“ zeigt den vollen Namen.
- **Filterleiste bleibt oben stehen** beim Scrollen (auch seitlich).
- **Anrufliste ohne Gruppen**: eine Liste, sortiert nach SLA rot → SLA gelb →
  fällige Wiedervorlagen/Rückrufe → zurückgestellt fällig → Rest nach Eingang
  (älteste zuerst). Statt „Quelle“/„Einzelquelle“ gibt es den Filter
  **„Vertriebskanal“**; die Zeile zeigt das Kanal-Badge. Tasten 1–7 wie bisher.
- **„Nicht erreicht“, „Mailbox“ und „Besetzt“ ohne Pop-up**: ein Klick protokolliert den Versuch
  mit Zeitstempel. **Es wird keine automatische Wiedervorlage mehr gesetzt** –
  Wiedervorlagen setzt ihr über den Wiedervorlage-Button. Die automatischen Mails
  bleiben an die Versuchsnummer gekoppelt (2. und 4. Versuch „Nicht erreicht“,
  letzter Versuch „Disqualifiziert“), ab dem 5. Versuch sind die Buttons gesperrt.
  „Rückruf gewünscht“ und „Kein Interesse“ behalten ihren Dialog.
- **Dashboard „Meine Arbeit“**: Wiedervorlagen zeigen nur noch manuell gesetzte;
  neue Liste **„Ohne nächsten Schritt“** (eigene Leads mit mindestens einem Versuch,
  ohne Wiedervorlage und Termin, letzter Versuch älter als 2 Tage – Parameter
  `ohne_schritt_tage`), damit nichts liegen bleibt.
- **Score und Qualifizierung sind abgeschaltet** (Parameter `score_aktiv = aus`):
  keine Score-Klasse mehr in Kartei, Anrufliste, Boards, Kanban, Dashboard,
  Statistik; „Erreicht“ führt direkt in die Kundenkartei (Reiter Termin). Die
  Daten und Steuerdatei-Blätter bleiben erhalten.
- **To-Dos** als eigene Seite in der Icon-Leiste: Meine offenen · Von mir
  vergeben · Erledigt, Umschalter Alle | Fällig, Anlegen direkt auf der Seite
  (auch aus dem Block To-Dos der Kundenkartei).
- **Browser-Cache**: die Seiten laden CSS/JS jetzt mit neuer Versionsnummer –
  ein Hard-Reload nach dem Update ist nicht nötig; sieht eine Seite trotzdem
  alt aus, einmal Strg+F5.

## Kundenkartei

- Oben die **Statuskette** und rechts oben der Button **„Terminierung“** (aktiv, sobald
  alle Pflichtfelder gefüllt sind und ein Termin vorgemerkt ist; sonst Tooltip mit
  den fehlenden Feldern). Daneben Anrufen · E-Mail · Notiz · Wiedervorlage.
- **Kundeninformationen als Block** unter dem Kopf (mehrspaltig). **Autospeichern:**
  jedes Feld speichert beim Verlassen bzw. bei Auswahl, grünes Häkchen bestätigt,
  Fehler erscheinen rot unter dem Feld (alter Wert bleibt). Kein Speichern-Button.
  Jede Änderung steht als Aktivität („Telefon: alt → neu“) in der Timeline.
- Aus der Kartei entfernt: Score, Qualifizierung, Quelle/Kampagne, Einwilligungen
  (bleiben im Eingang und in Kanal-Report/Statistik).
- Reiter: Termin · Anrufnotizen · E-Mail-Verlauf · Timeline. Darunter die Blöcke
  Termine · Angebote · Erfassungen · Projekt · Anhänge · To-Dos.
- **Terminvorschläge direkt im Block Termine** (Top 5 mit Begründung, Button
  „Vormerken“); ohne Adresse erscheint der Hinweis „Adresse fehlt“, bei Leads eines
  Handelsvertreters der Hinweis „Lead liegt bei … (Handelsvertreter)“.

## Handelsvertreter

- Der Terminassistent schlägt dem Innendienst keine Handelsvertreter mehr vor
  („Handelsvertreter terminieren ihre Leads selbst“); ein Handelsvertreter sieht
  für seine Leads weiterhin nur sich selbst. Manuelle Buchung durch den Innendienst
  auf einen Vertreter bleibt möglich.

## Parametrierung

- Lead-Einstellungen: `score_aktiv` (Standard aus), `ohne_schritt_tage` (Standard 2).
- Steuerdatei `leadmanagement_logik_v1.xlsx` (Sicherung
  `diagnose/leadmanagement_logik_v1.vor_v25.xlsx`): Blatt Status mit Label
  „Kontaktiert“ für beide Kontakt-Phasen und neuer Spalte `board_label`
  (Hauptboard / Deals), neues Blatt „Lesehilfe“; Blatt Kaskade: Spalte
  `wiedervorlage_nach` wird nicht mehr ausgewertet.

## Offen / Rückfragen

Siehe Gesamtübersicht zur Übergabe und `docs/leadmanagement-entscheidungen.md`
Abschnitt V3 ([ANNAHME]-Stellen: Namensspalten nur in Boards ausgeblendet, „eine
Liste“ = ohne Gruppen, Wunschzeiten bleiben in der Kartei, Alt → Neu in der
Änderungs-Aktivität, Mailbox/Besetzt wie Nicht erreicht, manuelle HV-Buchung durch
ID bleibt, Liste „Ohne nächsten Schritt“ als Ersatz für die automatische
Wiedervorlage).
