# Friondo-Tool – Modul „Lead-Management": Gesamtkonzept (Stand 22.09.2026, Basis CLAUDE.md v10)

Dieses Dokument ist das Fundament für alle PLAN_LEAD-Dateien – das Gegenstück
zu PROJEKTIERUNG-KONZEPT.md für den ersten Bereich des Startportals. Es hält
Soll-Prozess, Datenmodell, Terminassistent, Kommunikation, Kennzahlen, Rollen,
Schnittstellen, die Ablösung von monday und die Ausbaustufen fest.
**Abschnitt 16 listet alle Annahmen, die ich ohne Rückfrage getroffen habe**,
Abschnitt 15 die Risiken, die vor dem Bau zu klären sind.

Weichenstellungen von Andreas (22.09.2026): monday wird **schrittweise
abgelöst** · Lead-Quellen: Website/Förderrechner, diverse Landingpages,
Partnerkanäle (Enni, SWD, Sparkasse DU), Lead-Portale/gekaufte Leads,
Telefon/Empfehlung/Bestand · Bearbeitung bis zum Termin durch den **Innendienst,
Abteilung Leadmanagement** · Ziele V1: zentraler Lead-Eingang, Terminierungs-
Workflow, Pipeline & Kennzahlen, Kundenkommunikation · zusätzlich Routenplaner
und KI-gestützte Terminvorschläge, plus eigene Ideen für ein möglichst
innovatives und effizientes Lead-Management.

**Nachtrag 22.09.2026 (Entscheidung Andreas):** V1 wird **sofort gebaut und
ausgerollt**, aber als **Demo ausschließlich für Admins** (Parameter
`lead_freigabe_modus = admin`, server-seitig). **monday läuft vorerst unverändert
weiter** – Lesesync und Rückspielung werden nicht angefasst; das Modul liest die
gesyncten Vorgänge nur mit. monday-Import und Parallelbetrieb rutschen nach V2.
Im Demo-Modus gehen keine Mails an Kunden, keine Termine in echte AD-Kalender,
und im Modul angelegte Leads bleiben als Demo-Leads unsichtbar für alle
bestehenden Listen. Details in PLAN_LEAD_V1.md.

---

## 1. Ziel und Leitprinzipien

Das Modul bildet den Weg vom ersten Kontakt bis zum vereinbarten Vor-Ort-Termin
(VOT) ab und übernimmt die Rolle, die heute monday.com spielt. Ab dem Termin
übernimmt das Angebotstool (Leads VOT → Erfassung → Angebot), ab der Unterschrift
die Projektierung. Damit lebt die ganze Kundenreise in **einem Vorgang** (v10).

1. **Jeder Lead ist in Minuten im Tool – ohne Abtippen.** Mails von Formularen,
   Landingpages und Portalen werden automatisch zu Leads; Partnerlisten werden
   importiert; Telefon-Leads in 30 Sekunden angelegt. Doppelte werden erkannt.
2. **Speed-to-Lead ist eine Kennzahl, kein Vorsatz.** Ziel: Erstkontakt
   innerhalb von 60 Minuten (Parametrierung). Jeder Lead zeigt eine SLA-Ampel,
   der Kunde bekommt sofort eine Eingangsbestätigung.
3. **Kein Lead liegt herum.** Jeder Lead hat einen Verantwortlichen, eine
   nächste Aktion und eine Fälligkeit. Nicht erreicht → automatische
   Wiedervorlage-Kaskade. Die Anrufliste ist priorisiert, nicht chronologisch.
4. **Terminieren mit Karte und Kalender.** Der Terminassistent schlägt die Slots
   vor, die zum Kundenwunsch passen **und** dem Außendienst die wenigsten
   Kilometer kosten – aus Outlook-Kalender, bestehenden Terminen und Fahrzeiten.
5. **Kanal-Wahrheit bis zum Auftrag.** Jeder Lead trägt Quelle, Kampagne und
   Kosten; die Auswertung reicht von „Kosten je Lead" bis „Umsatz je Kanal".
6. **Der Kunde wird automatisch mitgenommen.** Eingangsbestätigung,
   Terminbestätigung mit Kalendereintrag, Erinnerung vor dem Termin – erst per
   Mail, später SMS/WhatsApp und Online-Terminwahl.
7. **Prozesswissen liegt in pflegbaren Tabellen**, nicht im Code
   (`leadmanagement_logik_v1.xlsx`: Qualifizierungsfragen, Scoring,
   Wiedervorlage-Kaskade, Gründe) – wie beim Konfigurator und der Projektierung.

---

## 2. Soll-Prozesskette

| Nr. | Schritt | Verantwortlich | Im Tool |
|---|---|---|---|
| 0 | **Eingang** | System | Lead entsteht automatisch (Mail-Parser, Import, REST-Endpunkt) oder per Schnellanlage. Duplikatprüfung, Quelle/Kampagne gesetzt, Geokodierung, Score vorläufig. Eingangsbestätigung an den Kunden, Benachrichtigung an das Leadmanagement, SLA-Timer läuft. |
| 1 | **Erstkontakt** | Leadmanagement | Anrufliste „Jetzt anrufen" (SLA zuerst). Ein-Klick-Protokoll des Anrufergebnisses. Nicht erreicht → Kaskade (+2 h, +1 Tag, +3 Tage, +7 Tage; Parametrierung) und ab dem 2. Versuch automatische „Wir haben Sie nicht erreicht"-Mail mit Rückrufwunsch. |
| 2 | **Qualifizierung** | Leadmanagement | Kurzer Qualifizierungsbogen je Sparte (8–12 Fragen aus der Steuerdatei) im Gespräch, Score A/B/C. Entscheidung: **Terminieren** · **Zurückstellen** (Datum + Grund) · **Unqualifiziert** (Pflichtgrund). Antworten werden später in den AD-Erfassungsbogen vorbelegt. |
| 3 | **Terminierung** | Leadmanagement | Terminassistent: Top-5-Slots aus AD-Kalender + Fahrzeiten + Kundenwunsch, ein Klick bucht: VOT-Termin im Tool, Outlook-Termin beim Außendienst (Graph), Terminbestätigung mit ICS an den Kunden, Erinnerung 24 h vorher. Lead erscheint in **Leads VOT** (bestehende Übergabe an das Angebotstool). |
| 4 | **VOT & Erfassung** | Außendienst | Bestehend (Erfassung je Sparte). Neu: AD sieht die Lead-Akte (Anfragetext, Qualifizierung, Aktivitäten) und die Tagestour; meldet **No-Show** oder **Verschieben** → Lead geht mit Grund an das Leadmanagement zurück. |
| 5 | **Angebot & Verfolgung** | Innendienst | Bestehend (v10: Vorgangsakte, Hot-Ampel, Wiedervorlage, Versionen). Gewonnen/Verloren ergeben sich aus den Angebotsstatus. |
| 6 | **Nachlauf** | Leadmanagement | Verloren- und Unqualifiziert-Gründe auswerten; **Nurture-Liste** (Wiedervorlage in 6/12 Monaten); **Cross-Selling-Trigger** aus der Projektierung (WP abgeschlossen → PV-Lead in 6 Monaten); Löschung/Anonymisierung nach Frist (DSGVO). |

Nach dem Termin ändert sich am bestehenden Angebotsprozess nichts – das Modul
liefert bessere, vorbereitete Leads in „Leads VOT" und holt gescheiterte
Termine zurück.

---

## 3. Datenmodell

```
Kunde ─ Vorgang (v10) ─┬─ Lead-Kopf (Quelle, Kampagne, Eingang, Score, SLA, Einwilligungen, Koordinaten)
                       ├─ Aktivitäten (Anrufe, Mails, SMS, Notizen, Statuswechsel – Timeline)
                       ├─ Qualifizierung je Sparte (Antworten + Score)
                       ├─ VOT-Termine (AD, Zeit, Status, Outlook-ID, Fahrzeit)
                       ├─ Kommunikation (gesendete Bestätigungen/Erinnerungen + Antworten)
                       ├─ Erfassungen · Angebote · Notizen-Chat (bestehend v10)
                       └─ Projekt (Projektierung, bestehend)
Stammdaten: Lead-Quellen · Kampagnen · AD-Profile · Vorlagen · Gründe · Geocode-/Routing-Cache
```

**Lead = Vorgang.** Es gibt keine zweite Lead-Tabelle: Der v10-Vorgang wird um
den Lead-Kopf und die Lead-Phase erweitert. Heute wird ein Vorgang durch den
monday-Sync angelegt; künftig durch den Eingang. Die bestehende Sicht „Leads
VOT" (Vorgänge mit VOT-Datum ohne Angebot) bleibt unverändert – sie wird nur
aus den VOT-Terminen des Tools gespeist statt aus monday.

### 3.1 Lead-Phasen (vor dem Termin setzbar, danach abgeleitet)

| Phase | Bedeutung | Eintritt | Weiter, wenn |
|---|---|---|---|
| **Neu** | eingegangen, noch kein Kontaktversuch | Anlage | erster Kontaktversuch protokolliert |
| **In Kontaktierung** | mindestens ein Versuch, noch nicht erreicht oder noch nicht qualifiziert | automatisch | Qualifizierungsbogen abgeschlossen |
| **Qualifiziert** | Gespräch geführt, Bogen ausgefüllt, Score steht | automatisch | Termin gebucht |
| **Terminiert** | VOT-Termin steht (= heute „Leads VOT") | Buchung | Erfassung abgesendet (bestehend) |
| **Erfasst** · **Angebot** · **Gewonnen** · **Verloren** | abgeleitet aus Erfassungs-/Angebotsstatus (v10) | automatisch | – |
| **Zurückgestellt** | Kunde will später (Datum + Grund); erscheint am Datum wieder als Neu | manuell | Wiedervorlage fällig |
| **Nicht erreicht** | Kaskade ausgeschöpft; Nurture-Mail, Wiedervorlage +30 Tage | automatisch | Kunde meldet sich / Wiedervorlage |
| **Unqualifiziert** | Pflichtgrund (Mieter, außerhalb Gebiet, kein Bedarf, Spam, Doppelter …) | manuell | – (reaktivierbar) |

No-Show oder Verschiebung setzt den Vorgang von „Terminiert" zurück auf
„Qualifiziert" mit Aktivität „Termin verschoben/No-Show (Grund)" – der Termin
bleibt als Historie erhalten. Rückwärts-Übergänge sind immer möglich.

### 3.2 Neue Tabellen und Felder (Vorschlag für PLAN_LEAD_V1)

- `vorgaenge` (erweitern): `lead_phase`, `quelle_id`, `kampagne_id`, `utm_source/medium/campaign/content`,
  `eingang_am`, `eingang_art` (mail / import / api / manuell / monday / trigger), `anfrage_text`
  (Originaltext), `anfrage_rohdaten` (JSON aller Felder der Quelle), `erstkontakt_am` (1. Versuch),
  `erreicht_am` (1. erfolgreiches Gespräch), `terminiert_am`, `sla_status` (grün/gelb/rot),
  `leadmanager_id`, `score`, `score_klasse` (A/B/C), `wunschzeiten` (JSON: Wochentage +
  Zeitfenster), `lat`, `lon`, `geocode_status`, `einwilligung_werbung` (bool, Datum, Quelle),
  `einwilligung_sms_whatsapp`, `zurueckgestellt_bis`, `unqualifiziert_grund`, `loeschen_am`.
- `lead_quellen`: `key`, `name`, `typ` (website / landingpage / portal / partner / telefon /
  empfehlung / bestand / monday), `kanal` (→ bestehender Vertriebskanal, steuert Angebotsprofil),
  `kosten_je_lead`, `standard_sparten`, `parser_regel_id`, `aktiv`.
- `kampagnen`: `name`, `quelle_id`, `von`, `bis`, `budget`, `utm_campaign`.
- `lead_aktivitaeten`: `vorgang_id`, `typ` (anruf / mail_aus / mail_ein / sms / whatsapp / notiz /
  status / termin / system), `ergebnis` (erreicht / nicht_erreicht / besetzt / mailbox /
  rueckruf_gewuenscht / falsche_nummer / kein_interesse), `text`, `dauer_sek`, `benutzer_id`,
  `zeitpunkt`, `naechste_aktion_am`. Der v10-Notizen-Chat wird als Typ `notiz` in diese
  Timeline integriert (Anzeige gemeinsam, Einträge bleiben unveränderlich).
- `lead_qualifizierung`: `vorgang_id`, `sparte`, `antworten` (JSON, Frage-Keys aus der
  Steuerdatei), `score_punkte`, `abgeschlossen_am`, `benutzer_id`.
- `vot_termine`: `vorgang_id`, `ad_id`, `beginn`, `ende`, `adresse` + `lat/lon` (Ausführungsort),
  `status` (geplant / bestaetigt / verschoben / no_show / erfolgt / abgesagt), `outlook_event_id`,
  `bestaetigung_am`, `erinnerung_am`, `fahrzeit_hin_min`, `umweg_min`, `quelle` (assistent /
  manuell / monday), `grund_text`. Das bisherige VOT-Datum am Lead wird aus dem aktiven Termin
  abgeleitet.
- `ad_profile`: `benutzer_id`, `start_adresse` + `lat/lon` (Wohnort oder Büro), `arbeitszeiten`
  (JSON je Wochentag), `termin_dauer_min` (Standard 90), `puffer_min` (15), `max_termine_tag`,
  `gebiet_plz_praefixe`, `kalender_postfach`, `aktiv_terminierung` (bool).
- `kommunikation_log`: `vorgang_id`, `kanal` (mail / sms / whatsapp), `vorlage_key`, `an`,
  `gesendet_am`, `status` (geplant / gesendet / fehler / beantwortet), `antwort_text`.
- `lead_kosten`: `quelle_id`, `monat`, `betrag`, `anzahl_leads` (Import aus Rechnung/Excel) →
  Kosten je Lead = Betrag ÷ Leads des Monats (überschreibt `kosten_je_lead`).
- `geocode_cache` (`adresse_norm`, `lat`, `lon`, `anbieter`, `stand`) und `routing_cache`
  (`von_lat/lon`, `nach_lat/lon`, `minuten`, `km`, `gueltig_bis`).
- `lead_parameter` (Key-Value): SLA-Ziel Minuten, Kaskade, Vorschlags-Horizont Tage,
  Routing-Anbieter + API-Key, Absender-Postfach, Löschfristen, Lead-Modus (siehe 14).
- Bestehende Listen erweitern: Ablehnungsgründe um Vor-Termin-Gründe
  (Unqualifiziert / No-Show / Absage) – eine Liste mit Kennzeichen „Phase".

### 3.3 Steuerdatei `leadmanagement_logik_v1.xlsx` (Import in der Parametrierung)

| Blatt | Inhalt |
|---|---|
| **Qualifizierung** | `sparte`, `frage_key`, `frage`, `typ` (ja/nein, auswahl, zahl, text), `optionen`, `pflicht`, `reihenfolge`, `erfassungs_frage` (Mapping auf den AD-Bogen zur Vorbelegung, z. B. `A01`) |
| **Scoring** | `frage_key`, `wert`, `punkte` (z. B. Heizung = Öl +20; Alter Heizung > 20 Jahre +15; Eigentümer +15; Zeitrahmen < 3 Monate +20; PLZ im Kerngebiet +10; Quelle-Bonus aus Abschlussquote); Klassen: A ≥ 60, B ≥ 35, C darunter |
| **Kaskade** | `versuch_nr`, `wiedervorlage_nach` (`+2h`, `+1d 18:00`, `+3d`, `+7d`), `aktion` (keine / mail_nicht_erreicht / sms_nicht_erreicht), `nach_letztem` (→ Nicht erreicht + Nurture +30d) |
| **Gründe** | `phase` (unqualifiziert / zurueckgestellt / no_show / verloren), `grund` |
| **Wunschzeiten** | Zeitfenster-Definition (vormittags 08–12, nachmittags 12–17, abends 17–20, Samstag) |

Parser-Regeln, Vorlagen, Quellen und AD-Profile werden **in der Oberfläche**
gepflegt (Parametrierung → Lead-Management), nicht in der Excel – sie ändern
sich häufiger und brauchen Test-Funktionen.

---

## 4. Lead-Eingang (alle Quellen, ohne Abtippen)

| Weg | Quellen | Stufe | Funktionsweise |
|---|---|---|---|
| **Mail-Parser** | Website-Formular, Förderrechner, Landingpages, Lead-Portale, Partner-Mails | V1 | Shared-Postfach **leads@friondo.de** (Annahme), Abruf über Graph alle 2 Minuten (bestehende Abruf-Strecke von angebot@ wiederverwenden). Je Quelle eine **Parser-Regel** in der Parametrierung: Absender-/Betreff-Muster + Feldzuordnung (Zeilenformat `Feld: Wert`, HTML-Tabelle, JSON-Anhang). Test-Funktion: Beispiel-Mail einfügen → erkannte Felder. Erkannt → Lead; nicht erkannt → Liste **„Posteingang unklar"** mit Ein-Klick-Anlage (Felder soweit möglich vorbefüllt). |
| **Formular-Standard** | Website, Landingpages (Agentur) | V1 | Vorgabe an die Agentur: alle Formulare senden an leads@friondo.de mit Betreff `[LEAD] <quelle> <kampagne>` und Body `Feld: Wert` je Zeile (Anrede, Vorname, Nachname, Straße, PLZ, Ort, Telefon, E-Mail, Sparte(n), Wunschzeit, Nachricht, utm_*). Eine Regel deckt dann alle Landingpages ab; die Quelle kommt aus dem Betreff. |
| **REST-Endpunkt** | Website/Landingpages, Portale mit Webhook, Förderrechner | V1 (intern) / V2 (extern) | `POST /api/leads` mit API-Key und festem JSON-Schema. Sofort im LAN nutzbar; von außen erst mit öffentlicher HTTPS-Route (Abschnitt 15). |
| **CSV/Excel-Import** | Partnerlisten (Enni, SWD, Sparkasse DU), gekaufte Lead-Pakete | V1 | Upload mit Spaltenzuordnung (merkbar je Quelle), Vorschau, Duplikatprüfung, Quelle/Kampagne für die ganze Datei. |
| **Schnellanlage** | Telefon, Empfehlung, Messe | V1 | Formular mit 6 Feldern (Name, Telefon, PLZ, Sparte, Quelle, Notiz) – auch mobil. Vollständige Daten folgen im Qualifizierungsgespräch. |
| **Bestandskunden-Trigger** | Projektierung, Angebotstool | V3 | „Gewerk WP abgeschlossen" → Vorschlag Cross-Selling-Lead PV/KL/WB mit Wiedervorlage +6 Monate (Parametrierung je Sparte); „Angebot verloren" → Nurture-Wiedervorlage +12 Monate. Vorschläge bestätigt das Leadmanagement per Klick. |
| **monday-Import** | drei Deals-Boards, alle Gruppen | V1 (einmalig) + Übergangs-Sync | Abschnitt 14. |

**Duplikatprüfung** bei jedem Eingang: Telefon normalisiert (E.164), E-Mail,
Name + PLZ, Adresse. Treffer → Badge „möglicher Doppelter" mit Dialog
„Zusammenführen / Eigener Vorgang". Regel: Existiert ein **offener** Vorgang
desselben Kunden, wird die neue Anfrage als zusätzliche Interesse/Sparte an
diesen gehängt (kein zweiter Vorgang – konsistent mit v8/v10); ist der letzte
Vorgang abgeschlossen (Gewonnen/Verloren/Unqualifiziert), entsteht ein neuer
Vorgang am selben Kunden mit Hinweis „Wiederkehrer".

**Speed-to-Lead:** Jeder Eingang erzeugt eine Glocken-Benachrichtigung
(bestehende Glocke aus PLAN_PROJ_V1, Phase 69) an die Rolle Leadmanagement,
optional Push-Mail. SLA-Ampel am Lead: grün < 30 Min, gelb < 60 Min, rot
darüber ohne ersten Versuch (Parametrierung). Außerhalb der Arbeitszeit läuft
der Timer erst ab Arbeitsbeginn.

---

## 5. Terminierungs-Workflow

### 5.1 Anrufliste „Jetzt anrufen"

Eine Liste, sortiert nach Priorität – nicht nach Eingang:
1. Neue Leads mit SLA gelb/rot (älteste zuerst)
2. Fällige Wiedervorlagen und Rückrufwünsche (Uhrzeit)
3. Zurückgestellte, deren Datum erreicht ist
4. Rest nach Score, innerhalb des Scores nach bester Anrufzeit (V3: aus der
   Historie der erreichten Anrufe je Wochentag/Stunde)

Zeile: Name, Ort, Sparten-Chips, Quelle-Badge, Score-Klasse, SLA-Timer,
Versuch-Nr., letztes Ergebnis, Telefonnummer als `tel:`-Link (Click-to-Call
über Softphone/Handy, V1) und **Ergebnis-Buttons direkt in der Zeile**.
Filter: Leadmanager, Quelle, Sparte, Score, PLZ. Jeder Leadmanager sieht
„Meine Leads" (Zuweisung automatisch: Round-Robin oder nach Quelle,
Parametrierung) und kann in „Alle" wechseln.

### 5.2 Anruf protokollieren (ein Klick)

Ergebnis-Buttons: **Erreicht** (öffnet Qualifizierungsbogen) · **Nicht
erreicht** · **Besetzt** · **Mailbox** · **Rückruf gewünscht** (Datum/Uhrzeit
Pflicht) · **Falsche Nummer** · **Kein Interesse** (Grund Pflicht →
Unqualifiziert). Jeder Klick erzeugt eine Aktivität; Nicht erreicht / Besetzt /
Mailbox lösen die **Kaskade** aus: Wiedervorlage aus der Steuerdatei, ab dem
2. Versuch automatische „Nicht erreicht"-Mail (später SMS) mit den Optionen
„Rufen Sie mich an unter …" / „Antworten Sie mit Ihrer Wunschzeit". Nach dem
letzten Versuch → Phase „Nicht erreicht", Nurture-Mail, Wiedervorlage +30 Tage.

### 5.3 Qualifizierungsbogen

Je Sparte 8–12 Fragen aus dem Blatt „Qualifizierung", als Gesprächsleitfaden
gestaltet (große Buttons, Tastatur-Bedienung). Startvorschlag WP: Eigentümer? ·
Gebäudetyp · Baujahr · Wohnfläche · aktuelle Heizung + Baujahr · Verbrauch
(kWh/Liter/m³) · Warmwasser über Heizung? · Zeitrahmen · Förderinteresse ·
Entscheider beim Termin anwesend? · Wunschzeiten. PV zusätzlich: Dachform,
Dachfläche/Ausrichtung, Stromverbrauch, Speicher/Wallbox-Interesse. Antworten
werden über `erfassungs_frage` in den bestehenden AD-Erfassungsbogen
**vorbelegt** (der AD prüft vor Ort gegen – wie in der Projektierung geplant).
Score wird live berechnet und als A/B/C angezeigt; Klasse C erzeugt beim
Terminieren den Hinweis „Score C – Termin trotzdem buchen?" (kein Verbot).

### 5.4 Zuweisung des Außendienstlers

Vorschlag automatisch: (1) Kanal-Regel (z. B. Enni-Leads → fester AD),
(2) Gebiet (PLZ-Präfixe des AD-Profils), (3) Auslastung (Termine der nächsten
14 Tage), (4) manuell. Der Terminassistent rechnet für alle passenden AD und
zeigt die Slots AD-übergreifend – der beste Slot kann bei einem anderen AD
liegen als vorgeschlagen.

---

## 6. Terminassistent und Tourenplanung

### 6.1 Was der Assistent tut

Eingaben: Lead-Adresse (geokodiert) · Wunschzeiten des Kunden · zulässige AD ·
AD-Profil (Startadresse, Arbeitszeiten, Termindauer, Puffer, Max/Tag) ·
AD-Kalender aus Outlook (Graph: Frei/Belegt und Termine) · VOT-Termine des Tools
mit Koordinaten · Fahrzeiten aus dem Routing-Dienst (Cache).

Vorschlagsmaschine (deterministisch, im Tool, kein externer KI-Dienst nötig):

1. Horizont: nächste 14 Werktage (Parametrierung), Raster 30 Minuten innerhalb
   der Arbeitszeit des AD.
2. Je Kandidat-Slot: Kalender frei? Passt Termindauer + Puffer zwischen
   Vortermin und Folgetermin? Max/Tag nicht überschritten?
3. **Umweg** = Fahrzeit(Vortermin → Lead) + Fahrzeit(Lead → Folgetermin) −
   Fahrzeit(Vortermin → Folgetermin); ohne Nachbarn: Fahrzeit von/zur
   Startadresse.
4. Bewertung = Umweg in Minuten + Zuschläge/Abschläge: Wunschzeit getroffen
   −30 · Tag hat bereits Termine im Umkreis 10 km −15 („Tour-Tag") · leerer Tag
   +20 · Randzeiten +10 · Score-A-Lead bevorzugt früh (Tage bis Termin × 2).
5. Ausgabe: **Top 5** mit Begründung in Klartext –
   „Di 30.09. 14:00 · Simon · +12 Min Umweg · davor Müller (Moers, 11:30),
   danach Schmidt (Kamp-Lintfort, 16:30)" – plus Mini-Karte mit den Terminen
   des Tages. Alternativ: Wochenansicht des AD zum manuellen Setzen.
6. **Buchen** (ein Klick): `vot_termine` + Outlook-Termin im AD-Kalender
   (Betreff „VOT <Sparte> – <Name>, <Ort>", Adresse, Telefon, Link zur
   Lead-Akte, Kurz-Steckbrief aus der Qualifizierung) + Terminbestätigung an
   den Kunden + Aktivität. Verschieben = Umbuchung mit Kunden-Info.

Fällt der Routing-Dienst aus, rechnet der Assistent mit Luftlinie × 1,3 bei
45 km/h und markiert die Vorschläge als „geschätzt" – das Tool blockiert nie.

### 6.2 Tourenplanung Tag (V2)

Ansicht je AD und Tag: Karte (Leaflet mit OpenStreetMap-Kacheln) mit den
Terminen in Reihenfolge, Gesamtfahrzeit/-kilometer, Button **„Reihenfolge
optimieren"** (exakte Lösung bis 8 Termine), **„Route in Google Maps öffnen"**
(Link mit Wegpunkten fürs Handy) und **„Leads in der Nähe"**: offene,
qualifizierte Leads im 10-km-Radius der Tour → direkt in eine Lücke des Tages
terminieren. Für den AD mobil: „Meine Tour heute" mit Navigations-Links.

### 6.3 Gebietskarte (V2)

Heatmap Leads / Termine / Aufträge je PLZ, Filter Zeitraum/Sparte/Quelle; AD-
Gebiete als Flächen; Grundlage für Marketing-Steuerung (wo Landingpages
Leads bringen, wo nicht) und für die Gebietsaufteilung der AD.

### 6.4 KI-Schicht (V3/V4)

Das Herz ist ein Optimierer, keine Sprach-KI – das ist der robustere und
nachvollziehbarere Weg. Eine KI-Schicht kommt oben drauf: (a) Freitext-Frage im Tool
(„Wann passt Familie Müller am besten bei Simon?") → nutzt dieselbe Maschine
und antwortet in Sätzen; (b) Lernen aus der Historie: tatsächliche vs.
geschätzte Fahrzeiten, No-Show-Quote je Slot-Typ (Abend, Samstag), beste
Anrufzeiten; (c) Vorschlag „Diese Woche lohnt ein Tour-Tag in Moers: 4 offene
A-Leads im Umkreis". Datenschutz siehe Abschnitt 15.

### 6.5 Routing- und Geocoding-Dienst (Entscheidung V1)

| Option | Für | Gegen | Empfehlung |
|---|---|---|---|
| **openrouteservice (HeiGIT)** – Directions, Matrix, Geocoding per API-Key | kostenloser Plan, kommerzielle Nutzung erlaubt, OSM-Daten, EU-Anbieter (Heidelberg) | Tageslimits (zuletzt bekannt: ca. 2.000 Routen, 500 Matrix-Abfragen, 1.000 Geocodings je Tag – vor dem Bau auf account.heigit.org prüfen) | **V1-Standard**; mit Cache reicht das für einige hundert Leads/Monat |
| **Google Maps Platform** (Geocoding, Routes/Route Matrix) | zuverlässig, beste Adress-Erkennung, seit März 2025 monatliche Frei-Kontingente je SKU statt 200-$-Guthaben | Kosten oberhalb der Frei-Kontingente, US-Anbieter (AVV nötig), Abrechnungskonto | Fallback/Umschalter in der Parametrierung |
| **OSRM / Valhalla selbst gehostet** | keine Limits, keine Datenübermittlung | braucht Linux/Docker-Host (Terminal-Server ist Windows) und Kartenpflege | V3, falls Volumen oder Datenschutz es verlangen |
| **Nominatim (OSM)** für Geocoding | kostenlos | Nutzungsrichtlinie: max. 1 Anfrage/s, kein Massen-Geocoding, User-Agent Pflicht | nur als Notfall-Fallback |

Alle Adressen werden **einmal** geokodiert und gecacht; Fahrzeiten je
Koordinaten-Paar 90 Tage gecacht. Damit bleibt der API-Verbrauch klein.

---

## 7. Kundenkommunikation

| Stufe | Kanal | Nachrichten | Voraussetzung |
|---|---|---|---|
| **V1** | E-Mail über Graph, Absender **leads@friondo.de** (Annahme; Fallback angebot@) | **Eingangsbestätigung** (sofort; Sparte-spezifisch, „wir melden uns innerhalb von …", Vorbereitungs-Tipps, Broschüre) · **Nicht erreicht** (ab 2. Versuch; Rückruf-Optionen) · **Terminbestätigung** (mit ICS-Anhang, AD-Name, was der Kunde bereithalten soll: Heizkostenabrechnung, Stromrechnung, Grundriss, Fotos Heizungsraum) · **Erinnerung** (24 h vorher) · **Verschiebung/Absage** · **Nurture** (nach Kaskade) | Postfach + „Senden als" (M365-Admin); bestehender Vorlagen-Editor mit neuen Platzhaltern (`{termin_datum}`, `{termin_uhrzeit}`, `{vertriebler}`, `{vertriebler_telefon}`, `{sparten}`, `{quelle}`) |
| **V2** | SMS über Anbieter (seven.io, sipgate, Twilio – REST, wenige Cent je SMS) | Terminerinnerung, Nicht erreicht, Rückrufwunsch-Antwort | Anbieterkonto, Einwilligung am Lead (Kontaktanfrage des Kunden deckt Terminorganisation; Werbung nicht) |
| **V3** | WhatsApp Business Platform (Meta Cloud API direkt oder über 360dialog/Superchat) | Terminbestätigung/-erinnerung als Utility-Vorlage, Kundenantworten landen in der Lead-Akte | Meta-Business-Verifizierung, eigene Nummer, Vorlagen-Freigabe; Kosten je Nachricht im Cent-Bereich – **Meta stellt zum Oktober 2026 auf Abrechnung je Nachricht um, Preise vor V3 prüfen** |
| **V3** | **Online-Terminwahl**: Link in Mail/SMS „Termin selbst wählen" → öffentliche Seite zeigt die Top-Slots des Assistenten, Kunde bucht, Bestätigung automatisch | öffentliche HTTPS-Route (Abschnitt 15) |

Alle Nachrichten laufen über eine Warteschlange (Job jede Minute), werden in
`kommunikation_log` protokolliert und in der Lead-Akte unter „Kommunikation"
angezeigt. Antworten des Kunden auf leads@ werden per Konversations-ID dem
Vorgang zugeordnet (bestehende Mail-Verlauf-Logik von der Angebots- auf die
Vorgangsebene heben).

---

## 8. Kennzahlen und Auswertung

**Trichter** (je Zeitraum, filterbar nach Quelle, Kampagne, Kanal, Sparte,
Leadmanager, AD): Eingang → Erreicht → Qualifiziert → Terminiert → VOT
stattgefunden → Erfasst → Angebot → Gewonnen, jeweils Anzahl und Quote zum
Vorschritt.

| Kennzahl | Definition |
|---|---|
| Speed-to-Lead | Median Minuten Eingang → 1. Versuch und Eingang → erreicht; Anteil innerhalb SLA |
| Kontaktquote | erreicht ÷ Eingang; Versuche bis erreicht (Ø) |
| Terminquote | terminiert ÷ qualifiziert und ÷ Eingang |
| Show-Quote | VOT stattgefunden ÷ terminiert (No-Show-Quote als Gegenstück, je AD und Slot-Typ) |
| Angebots- und Abschlussquote | bestehend, jetzt bis zur Quelle zurückverfolgbar |
| Kosten je Lead / Termin / Auftrag | Kosten der Quelle (Parameter oder Monatsimport) ÷ Anzahl |
| Umsatz und Auftragswert je Quelle/Kampagne | aus angenommenen Angeboten (v10 Auftragswert) |
| Pipeline-Wert | Summe erwarteter Auftragswerte offener Leads, gewichtet nach Phase und Score (Parametrierung: Ø-Wert je Sparte × Quote je Phase) |
| Durchlaufzeiten | Eingang → Termin, Termin → Angebot, Angebot → Entscheidung |
| Aktivität je Leadmanager | Anrufe/Tag, erreichte Gespräche, Termine, überfällige Wiedervorlagen |
| Gründe | Unqualifiziert-, No-Show-, Verloren-Gründe als Verteilung |

Drei Sichten: **Cockpit Leadmanagement** (heute: neu, SLA rot, fällig, Termine
der Woche je AD), **Kanal-Report** (Monat: Trichter + Kosten je Quelle,
CSV-Export), **Geschäftsführung** (Trichter gesamt, Pipeline-Wert, Kosten je
Auftrag, Trend 12 Monate). Die bestehende Statistik-Seite erhält den Reiter
„Leads"; der Außendienst sieht wie bisher nur eigene Zahlen.

---

## 9. Rollen

| Rolle | Sieht | Darf |
|---|---|---|
| **Admin** | alles | alles; Parametrierung Lead-Management (Quellen, Parser, Vorlagen, Kaskade, SLA, Scoring-Import, AD-Profile, Routing-Dienst, Löschfristen) |
| **Innendienst** | alles wie bisher + Lead-Management komplett | wie Leadmanagement, zusätzlich Angebote wie bisher |
| **Leadmanagement** (neu) | alle Leads/Vorgänge, Kunden, Termine aller AD, Kommunikation, Statistik-Reiter „Leads"; Angebote nur Status + Endbetrag (keine EK/DB, kein Editor, kein Versand); Projektierung nur Phase am Vorgang | Leads anlegen/bearbeiten, anrufen/protokollieren, qualifizieren, terminieren/umbuchen, Vorlagen-Mails auslösen, Importe, „Posteingang unklar" bearbeiten, Zusammenführen |
| **Außendienst** | eigene Termine (Woche/Tour), eigene Leads ab „Terminiert" (wie heute Leads VOT) **plus** Lead-Akte read-only (Anfragetext, Qualifizierung, Aktivitäten, Kommunikation) | No-Show/Verschieben melden (Grund), Termin in der eigenen Woche verschieben (Kunde wird informiert, Leadmanagement benachrichtigt), Kommentar |
| **Projektierung / Montage** | unverändert (Lead-Daten nur über die Vorgangsakte, read-only) | – |

Rolle als zusätzliche Mehrfachrolle (Mechanik aus PLAN_PROJ_V1, Phase 64).
Leadmanager haben ein Profil (Arbeitszeiten für den SLA-Timer, Zuweisungs-
regel, Signatur wie ID-Benutzer).

---

## 10. Oberfläche

- **Startportal-Karte „Lead-Management"** (existiert, bekommt Inhalt): Kacheln
  *Neue Leads* (mit SLA-Rot-Zähler) · *Jetzt anrufen* · *Wiedervorlagen fällig* ·
  *Termine diese Woche* (je AD) · *Posteingang unklar*. Shortcuts: Anrufliste ·
  Pipeline · Kalender.
- **Anrufliste** `/leads` (Abschnitt 5.1) – die Arbeitsseite des Leadmanagements;
  Lead-Details als Seitenpanel ohne Seitenwechsel; Tastaturkürzel für die
  Ergebnis-Buttons.
- **Pipeline-Kanban** `/leads/board`: Spalten Neu · In Kontaktierung ·
  Qualifiziert · Terminiert · Erfasst · Angebot · Gewonnen | Verloren (eingeklappt);
  Nicht erreicht / Zurückgestellt / Unqualifiziert per Filter. Karte = Vorgang:
  Name, Ort, Sparten-Chips, Quelle-Badge, Score, SLA-Timer, nächste Aktion +
  Fälligkeit, Leadmanager-/AD-Kürzel. Drag & Drop nur, wo es fachlich passt
  (Zurückstellen, Unqualifiziert mit Grund-Dialog); Terminiert nur über den
  Assistenten.
- **Lead-Akte** = Vorgangsakte (v10) mit neuem Kopfblock (Quelle, Kampagne,
  Eingang, SLA, Score, Leadmanager, AD, Einwilligungen) und den Reitern
  **Aktivitäten** (Timeline inkl. Notizen-Chat) · **Qualifizierung** ·
  **Termin** (aktiver Termin, Historie, Button „Termin vorschlagen") ·
  **Kommunikation** (gesendet/beantwortet, Buttons „Mail senden" mit Vorlage) ·
  danach die bestehenden Bereiche Erfassungen · Angebote · Projekt.
- **Terminassistent** (Dialog aus Akte und Anrufliste): Top-5 mit Begründung,
  Mini-Karte, Wunschzeit-Abgleich; Reiter „Kalender" für manuelles Setzen.
- **Terminkalender** `/leads/kalender`: Woche je AD (alle AD nebeneinander oder
  einer), Drag & Drop = Umbuchung mit Kundeninfo; Tagesansicht mit Karte (V2).
- **Karte** `/leads/karte`: Pins für offene Leads (Farbe = Phase, Größe =
  Score) und Termine; Filter; Klick → Akte; Tour des Tages (V2); Heatmap (V2).
- **Statistik → Reiter Leads** (Abschnitt 8) und **Kanal-Report** mit Export.
- **Parametrierung → Lead-Management**: Quellen & Kampagnen · Parser-Regeln
  (mit Test-Mail) · Vorlagen (Mail/SMS/WhatsApp) · Kaskade/SLA · Steuerdatei-
  Import (Qualifizierung, Scoring, Gründe) · AD-Profile · Zuweisungsregeln ·
  Routing-Dienst (Anbieter, API-Key, Test-Button) · Lead-Modus/monday-Übergang ·
  Löschfristen · Lead-Kosten-Import.
- **Mobil**: Anrufliste und Akte (Leadmanager unterwegs/Homeoffice); AD: „Meine
  Tour heute" mit Navigations-Links, No-Show-Button, Lead-Akte.

---

## 11. Schnittstellen

| System | Befund | Umsetzung |
|---|---|---|
| **monday.com** | Lesesync (3 Boards, Gruppe Terminiert) und Rückspielung vorhanden | V1: Einmal-Import aller Gruppen, Übergangs-Sync, Abschaltung per Schalter (Abschnitt 14) |
| **Microsoft Graph – Mail** | Versand + Abruf für angebot@ vorhanden | Postfach leads@friondo.de: Abruf alle 2 Min (Parser), Versand der Kundenmails; Rechte wie bei angebot@ (`docs/graph-einrichtung.md` fortschreiben) |
| **Microsoft Graph – Kalender** | noch nicht genutzt (in PLAN_PROJ für V2 vorgesehen) | Frei/Belegt + Termine der AD-Postfächer lesen, VOT-Termine schreiben/ändern/löschen. Berechtigung `Calendars.ReadWrite` (Application) mit Zugriffsbeschränkung auf die AD-Postfächer (Application Access Policy) – Aufgabe M365-Admin. **Gemeinsame Kalender-Strecke mit der Projektierung bauen** (Montage-Termine nutzen dieselbe Funktion). |
| **Website / Landingpages / Förderrechner** | Formulare der Agentur, Mailversand | V1: Mail-Standard (Abschnitt 4) – eine Vorgabe an die Agentur, keine Programmierung; V2: Webhook auf `POST /api/leads` sobald öffentliche Route steht; Förderrechner-Ergebnis (Förderbetrag, Eingaben) als Lead-Felder mitgeben |
| **Lead-Portale** | Übergabe meist per Mail, teils Portal-Export/API | V1: Parser-Regel je Portal; Kosten je Lead in der Quelle; V2: API prüfen je Portal |
| **Partner (Enni, SWD, Sparkasse DU)** | Listen per Mail/Excel, feste Kanäle mit Angebotsprofilen (v9) | V1: CSV-Import + Parser-Regel; Quelle → Kanal → Angebotsprofil automatisch |
| **Routing / Geocoding** | siehe 6.5 | V1: openrouteservice mit Cache, Umschalter auf Google; Luftlinie als Fallback |
| **SMS-Anbieter** | – | V2: REST-Versand, Statusrückmeldung, Antworten (Inbound-Nummer) in die Akte |
| **WhatsApp Business Platform** | – | V3: Vorlagen-Nachrichten, Inbound in die Akte; Anbieterwahl (direkt Meta oder BSP) |
| **Telefonanlage (CTI)** | unbekannt – welche Anlage? (offene Frage) | V1: `tel:`-Links; V2: Click-to-Call und automatische Anruf-Aktivität über die API der Anlage (3CX, Placetel, sipgate, NFON haben REST/Webhooks); V4: Transkription nur mit Einwilligung |
| **Claude API (Anthropic)** | – | V2 optional: Feld-Extraktion aus unklaren Mails, Zusammenfassung des Anfragetexts, Antwortentwürfe; als Schalter, mit AVV/DPA und EU-Datenverarbeitung prüfen; ohne Schalter läuft alles regelbasiert |
| **Projektierung / Angebotstool** | intern | Trigger Cross-Selling (V3), Erfassungs-Vorbelegung (V1), No-Show-Rückgabe (V1), Auftragswert je Quelle (V1) |
| **Öffentliche HTTPS-Route** | wie beim Fern-Signieren offen | eine Entscheidung (Reverse-Proxy im RZ oder Tunnel-Dienst, nur für definierte Routen) schaltet frei: Webhooks, Online-Terminwahl, Rückruf-Link, Fern-Signatur, später Kundenportal |

---

## 12. Innovationsideen – bewertet

Bewertung: Nutzen (●●● hoch) · Aufwand (○ klein, ○○ mittel, ○○○ groß) · Stufe.

| # | Idee | Was es bringt | Nutzen | Aufwand | Stufe |
|---|---|---|---|---|---|
| 1 | **Speed-to-Lead-SLA mit Ampel und Alarm** | Erstkontakt in Minuten statt Tagen; messbar je Leadmanager | ●●● | ○ | V1 |
| 2 | **Terminassistent mit Fahrzeit-Optimierung** (Andreas' Wunsch) | weniger Kilometer, mehr Termine je AD-Tag, Vorschläge in Sekunden | ●●● | ○○ | V1 |
| 3 | **Wiedervorlage-Kaskade + automatische Nicht-erreicht-Mail** | kein Lead versandet; Kunde meldet sich selbst zurück | ●●● | ○ | V1 |
| 4 | **Qualifizierung → Erfassungs-Vorbelegung** | AD spart Fragen vor Ort, Datenqualität steigt | ●●● | ○ | V1 |
| 5 | **Lead-Score regelbasiert (A/B/C)** | Reihenfolge der Anrufe, Priorität beim Terminieren, C-Leads bewusst behandeln | ●● | ○ | V1 |
| 6 | **Kanal-ROI: Kosten je Lead → je Termin → je Auftrag** | Marketing-Budget nach Fakten steuern; Portale kündigen, die nur Termine, keine Aufträge bringen | ●●● | ○ | V1 (Kosten-Parameter) / V2 (Monatsimport) |
| 7 | **Tourenplanung Tag + „Leads in der Nähe"** | Lücken im AD-Tag mit passenden Leads füllen, Navigation fürs Handy | ●●● | ○○ | V2 |
| 8 | **Gebiets-Heatmap** | zeigt, wo Landingpages und Portale wirken und wo AD-Gebiete unausgewogen sind | ●● | ○○ | V2 |
| 9 | **KI-Extraktion unklarer Anfragen** (Freitext-Mail → Felder + Sparte + Dringlichkeit) | „Posteingang unklar" schrumpft; Anfragetext-Zusammenfassung in der Akte | ●● | ○○ | V2 (Schalter, Datenschutz prüfen) |
| 10 | **CTI: Click-to-Call und automatische Anrufprotokolle** | kein manuelles Loggen, Dauer/Ergebnis automatisch; echte Aktivitätszahlen | ●● | ○○ | V2 (abhängig von der Anlage) |
| 11 | **SMS-Erinnerung 24 h vor VOT** | weniger No-Shows (im Handwerk typischerweise spürbar), AD-Zeit gespart | ●●● | ○ | V2 |
| 12 | **Online-Terminwahl für den Kunden** (Link mit Top-Slots) | Terminieren ohne Telefon-Pingpong, auch abends/Wochenende | ●●● | ○○ | V3 (braucht HTTPS-Route) |
| 13 | **WhatsApp-Kommunikation** (Bestätigung, Erinnerung, Fotos vom Kunden) | höhere Öffnungsraten als Mail, Kunde kann Heizungsraum-Fotos vorab schicken | ●● | ○○ | V3 |
| 14 | **Cross-Selling-Trigger aus der Projektierung** | Bestandskunden automatisch als PV/KL/WB-Leads – günstigste Leads überhaupt | ●●● | ○ | V3 |
| 15 | **Empfehlungsprogramm** (Empfehler am Lead, Prämie nach Auftrag) | strukturierte Weiterempfehlung, Auswertung Empfehler | ●● | ○ | V3 |
| 16 | **Score-Kalibrierung und No-Show-Prognose aus der Historie** | Punkte werden aus echten Gewonnen/Verloren-Daten gelernt; riskante Slots erkennen | ●● | ○○ | V3 |
| 17 | **Beste Anrufzeit je Lead** (aus erreichten Anrufen je Wochentag/Stunde, Quelle, Alter) | höhere Kontaktquote je Versuch | ●● | ○ | V3 |
| 18 | **Voice-/Chat-Vorqualifizierung** (Website-Chat, Telefon-Assistent außerhalb der Zeiten) | 24/7 Erstreaktion, Wunschzeit und Sparte schon erfasst | ●● | ○○○ | V4 |
| 19 | **Leadmanagement-Cockpit mit Team-Übersicht** (Anrufe, Termine, Show-Quote je Person, Tagesziel) | Führung nach Zahlen, faire Verteilung | ●● | ○ | V1 (Basis) / V2 (Ziele) |
| 20 | **Einwilligungs- und Löschmanagement** | DSGVO-sicher: Einwilligung je Kanal, automatische Anonymisierung nach Frist | ●● (Pflicht) | ○ | V1 |

---

## 13. Ausbaustufen

| Stufe | Inhalt | Nutzen |
|---|---|---|
| **V1 – Fundament & Terminierung** | Lead-Kopf/Phasen am Vorgang, Quellen/Kampagnen, Steuerdatei-Import, Mail-Parser + Formular-Standard, CSV-Import, Schnellanlage, REST-Endpunkt (intern), Duplikatprüfung, Anrufliste + Ein-Klick-Protokoll + Kaskade, Qualifizierungsbogen + regelbasierter Score + Erfassungs-Vorbelegung, Zuweisung AD, **Terminassistent** (Graph-Kalender lesen/schreiben, Geocoding, Fahrzeiten mit Cache, Top-5, Buchen), Mail-Kommunikation (6 Vorlagen), Pipeline-Kanban, Lead-Akte, Terminkalender Woche, Karte einfach (Pins), Kennzahlen-Trichter + Cockpit + Kanal-Report (Kosten je Lead als Parameter), Rolle Leadmanagement, AD-Sicht (Akte, No-Show), Einwilligungen/Löschfristen, Startportal-Kacheln live – **alles hinter dem Admin-Demo-Schalter, monday unverändert, Sendesperre für Kundenmails, Kalender nur ins Testpostfach** | Lead-System im Tool als Demo mit echten Daten (gesyncte Leads + Demo-Leads), Terminieren mit Karte |
| **V2 – Freigabe, monday-Übergang, Kommunikation & Tour** | Freigabe `lead_freigabe_modus = alle` (Rollen Leadmanagement/AD/Innendienst scharf, Mails live, Kalender-Sync in AD-Postfächer, Erfassungs-Vorbelegung), monday-Import aller Gruppen + Parallelbetrieb (Abschnitt 14), SMS, Nicht-erreicht-Sequenz per Mail+SMS, Tourenplanung Tag + Leads in der Nähe + Navigations-Links, Gebietskarte, KI-Extraktion (Schalter), CTI-Anbindung, Webhook extern (wenn HTTPS-Route), Kosten-Monatsimport + CPL/CPO, Team-Ziele im Cockpit, Vorschlag „Tour-Tag" | weniger No-Shows, weniger Kilometer, weniger Handarbeit |
| **V3 – Self-Service & Bestand** | Online-Terminwahl, WhatsApp, Rückruf-Link, Cross-Selling-Trigger aus der Projektierung, Empfehlungsprogramm, Score-Kalibrierung, No-Show-Prognose, beste Anrufzeit, monday endgültig abgeschaltet | Kunde terminiert selbst, Bestand wird zur Lead-Quelle |
| **V4 – KI-Schicht & Telefonie** | Sprach-Assistent im Tool (Fragen an die Vorschlagsmaschine), Voice-/Chat-Vorqualifizierung, Anruf-Transkription mit Einwilligung, Lern-Schleife Fahrzeiten/Slots | 24/7 Erstreaktion, lernendes System |

**Reihenfolge zur Projektierung:** PLAN_PROJ_V1 belegt die Phasen 64–72,
**PLAN_LEAD_V1 die Phasen 73–82**. Beide Module liegen hinter eigenen
Admin-Schaltern und können parallel entwickelt werden; gemeinsame Bausteine
(Mehrfachrollen, Benachrichtigungen/Glocke, Kanban, Graph-Kalender) baut der
Plan, der sie zuerst braucht, in identischer Struktur, der andere verwendet sie
wieder. Rollouts auf den Terminal-Server weiterhin nacheinander.
CLAUDE.md-Stand nach LEAD_V1: nächste freie Versionsnummer (v11 oder v12).

---

## 14. Ablösung von monday (Fahrplan – startet erst mit PLAN_LEAD_V2 nach Freigabe der Demo)

In V1 bleibt monday vollständig unverändert (Sync + Rückspielung wie heute).
Ab V2: Parameter `lead_modus` in der Parametrierung: **`parallel`** → **`tool`**
(Stichtag).

1. **Import Altbestand** (einmalig, idempotent): alle Gruppen der drei Boards.
   Mapping: „Terminierte Leads" → Terminiert (VOT-Termin aus Spalte) ·
   „Aktive Deals" → Erfasst/Qualifiziert (je nachdem, ob eine Erfassung im Tool
   existiert) · „Angebot versendet" → Angebot · „Gewonnen"/„Verloren" →
   Endzustände · alle übrigen Gruppen (z. B. Neu/Kontakt) → Neu bzw. In
   Kontaktierung. Quelle = „monday <Board>", Kanal wie bisher gemappt; Deal-Wert
   und Notizen als Aktivität „Import". Duplikate zu bestehenden Vorgängen
   werden zusammengeführt (Vorgang existiert schon für alle je terminierten
   Leads).
2. **Parallelbetrieb**: Neue Leads entstehen im Tool (Mails auf leads@
   umgestellt, Importe, Schnellanlage). Der Lesesync bleibt für Boards aktiv,
   in denen noch jemand arbeitet (z. B. externe Terminierer); die Rückspielung
   bleibt für monday-Leads aktiv. Regel: **Ein Lead lebt dort, wo er entstanden
   ist** – keine Doppelpflege.
3. **Quellen umziehen**: Website/Landingpages (Agentur: Mail-Standard),
   Portale (Empfänger-Adresse ändern), Partner (Import statt monday). Checkliste
   in der Parametrierung mit Häkchen je Quelle.
4. **Stichtag** `lead_modus = tool`: Sync und Rückspielung aus, monday-
   Vollexport als Archiv unter `data/archiv/monday/`, Lizenzen kündigen.
5. Vier Wochen Beobachtung: Kennzahl „Leads je Quelle je Woche" gegen Vormonate
   – fällt eine Quelle auf 0, ist eine Weiterleitung vergessen.

---

## 15. Risiken und Prüfpunkte (vor dem Bau klären)

1. **DSGVO / UWG.** Leads sind personenbezogene Daten; Rechtsgrundlage für
   Anfrage-Bearbeitung ist die Vertragsanbahnung, für **Nachfass per SMS/
   WhatsApp und für Nurture-Mails braucht es eine Einwilligung** (§ 7 UWG).
   Bei gekauften Leads: Einwilligungstext des Portals prüfen und am Lead
   speichern. Löschkonzept (z. B. Unqualifiziert/Verloren nach 12 Monaten
   anonymisieren) und Auskunftsfähigkeit gehören in V1. Datenschutzerklärung
   der Website muss Tool und Dienste nennen.
2. **Datenübermittlung an Dienste.** Geocoding/Routing überträgt Adressen
   (openrouteservice: EU; Google: AVV), KI-Extraktion überträgt Anfragetexte
   (Anthropic: DPA/EU-Verarbeitung prüfen; Schalter, Standard aus). Ohne AVV
   keine Aktivierung.
3. **Öffentliche HTTPS-Route.** Dieselbe offene Entscheidung wie beim
   Fern-Signieren. Sie blockiert Webhooks, Online-Terminwahl und Rückruf-Link.
   Empfehlung: einmal entscheiden (RZ/IT-Reverse-Proxy oder Tunnel-Dienst, nur
   für explizit freigegebene Routen, Token-Schutz), dann profitieren vier
   Funktionen in zwei Modulen.
4. **Graph-Berechtigungen.** Kalender-Zugriff auf AD-Postfächer und
   Mail-Zugriff auf leads@ sind M365-Admin-Aufgaben; ohne Kalender-Recht
   arbeitet der Assistent nur mit Tool-Terminen (Fallback vorsehen).
5. **API-Limits und Kosten.** openrouteservice-Kontingente vor dem Bau
   prüfen; Google-Frei-Kontingente je SKU und Preise; WhatsApp-Preisumstellung
   Oktober 2026; SMS-Kosten. Bei angenommenen 200–400 Leads/Monat und Cache
   bleibt V1 im kostenlosen Bereich – das Volumen ist eine offene Frage.
6. **Betriebsumgebung.** Terminal-Server (Windows) kann OSRM nicht ohne Docker
   hosten → API-Dienst in V1; Kartenkacheln (OSM) brauchen Internet am
   Arbeitsplatz.
7. **Besetzung außerhalb der Bürozeiten.** Speed-to-Lead wirkt nur, wenn
   jemand reagiert; abends/Wochenende deckt die automatische Eingangsmail +
   (V3) Online-Terminwahl die Lücke. Klären: Wer trägt die SLA?
8. **Datenqualität Adressen.** Fehlerhafte Adressen scheitern beim Geocoding
   → Liste „Adresse prüfen" mit manueller Pin-Setzung auf der Karte.
9. **Parallelbetrieb-Verwirrung.** Klare Regel (Abschnitt 14, Punkt 2) und
   Badge „monday" an importierten/gesyncten Leads.
10. **Erfassungs-Vorbelegung.** Das Mapping Qualifizierungsfrage →
    Erfassungsfrage muss bei jeder Änderung der Konfigurator-Logik mitgepflegt
    werden (Hinweis beim Logik-Import, wenn ein gemappter Key fehlt).
11. **Externe Terminierer (Blinno?).** Wer im „Blinno Working Space" arbeitet,
    entscheidet, ob ein Board länger im Parallelbetrieb bleibt oder ob diese
    Personen einen Tool-Zugang (Rolle Leadmanagement, eingeschränkt) bekommen.

---

## 16. Selbst getroffene Annahmen (nach V1 gemeinsam prüfen)

1. **Lead = Vorgang.** Keine eigene Lead-Tabelle; der v10-Vorgang wird
   erweitert. Zweite Anfrage bei offenem Vorgang → zusätzliche Sparte; bei
   abgeschlossenem Vorgang → neuer Vorgang am Kunden.
2. **Postfach leads@friondo.de** als Eingangs- und Absender-Postfach (Fallback
   angebot@); info@ bleibt unangetastet, kann aber als zweite Quelle
   abgerufen werden.
3. **SLA-Ziel 60 Minuten** (grün < 30, gelb < 60, rot darüber), nur innerhalb
   der Arbeitszeiten des Leadmanagements gezählt.
4. **Kaskade** +2 h · +1 Tag 18:00 · +3 Tage · +7 Tage · dann Nicht erreicht
   mit Nurture +30 Tage; Nicht-erreicht-Mail ab dem 2. Versuch.
5. **Score-Klassen** A ≥ 60, B ≥ 35 Punkte; Startpunkte laut 3.3 sind
   Platzhalter, die Andreas in der Excel anpasst.
6. **Terminassistent**: Horizont 14 Werktage, Raster 30 Min, Termindauer 90
   Min, Puffer 15 Min, Bewertungsgewichte laut 6.1; Vorschläge AD-übergreifend.
7. **Routing-Dienst V1 = openrouteservice** mit Cache; Google als Umschalter;
   Luftlinie-Fallback. Geocoding einmal je Adresse.
8. **Outlook-Termin beim AD** wird bei jeder Buchung geschrieben (Betreff
   „VOT <Sparte> – <Name>, <Ort>"); Änderung/Absage werden nachgezogen; der
   Kalender des AD ist die Wahrheit für Frei/Belegt.
9. **Zuweisung des Leadmanagers** Round-Robin unter aktiven Leadmanagern,
   Ausnahme Quelle-Regel; Zuweisung des AD nach Kanal-Regel → Gebiet →
   Auslastung.
10. **AD darf eigene Termine verschieben** (Kunde wird automatisch informiert);
    Absagen laufen über das Leadmanagement.
11. **Kanban-Spalten** = Lead-Phasen laut 3.1; Terminieren nur über den
    Assistenten (kein Drag & Drop nach „Terminiert").
12. **Kosten je Lead** in V1 als Parameter je Quelle; Monatsimport in V2.
13. **Löschfristen**: Unqualifiziert/Nicht erreicht/Verloren nach 12 Monaten
    anonymisieren (Name, Kontakt, Adresse → „gelöscht", Kennzahlen bleiben);
    Gewonnen: keine Löschung (Vertrag). Parametrierbar.
14. **monday-Import** ordnet „Aktive Deals" danach ein, ob im Tool eine
    Erfassung existiert; Zweifelsfälle landen in „Qualifiziert" mit Badge
    „Import prüfen".
15. **Reihenfolge**: LEAD_V1 (Phasen 73–82) darf parallel zu PROJ_V1 gebaut
    werden, weil beide hinter Admin-Schaltern liegen; gemeinsame Bausteine werden
    vom jeweils ersten Plan in identischer Struktur angelegt. Rollouts nacheinander.
16. **KI-Funktionen** (Extraktion, Zusammenfassung, Sprach-Assistent) sind
    immer Schalter mit Standard „aus"; das Modul funktioniert vollständig
    regelbasiert.

---

## 17. Offene Fragen an Andreas (nicht blockierend – Antworten fließen in PLAN_LEAD_V1)

1. Lead-Volumen: ungefähr wie viele Leads je Monat, wie viele Termine je AD
   und Woche, wie viele Außendienstler und Leadmanager?
2. Telefonanlage: welches System (für Click-to-Call/CTI in V2)?
3. Postfach: existiert leads@friondo.de bzw. welche Adresse empfangen die
   Formulare heute?
4. Wer arbeitet im „Blinno Working Space" – externe Terminierer, die bleiben?
5. Kernvertriebsgebiet: Radius/PLZ-Liste um Duisburg (für Score und
   Unqualifiziert-Regel „außerhalb Gebiet")?
6. Öffentliche HTTPS-Route: gibt es IT/RZ, die einen Reverse-Proxy stellen
   kann, oder soll ich einen Tunnel-Dienst vorschlagen?
7. Nächster Schritt: Freigabe des Konzepts → ich schreibe PLAN_LEAD_V1.md
   (Phasen 73 ff.) im Format von PLAN_PROJ_V1.
