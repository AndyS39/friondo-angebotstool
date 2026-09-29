# PLAN_PROJ_V3 – Go-live der Projektierung (Phasen 84–86 + Checkliste)

Voraussetzung: V1, V1b, V2 (Phasen 64–83) lokal umgesetzt. Dieser Plan hat
zwei Teile: **A** Bauphasen für die Go-live-Lücken (Claude Code), **B** die
organisatorische Checkliste (Andreas / M365-Admin / Team). Grundsatz:
**Ausrollen ≠ Go-live.** Der Demo-Modus (`freigabe_modus = admin`) erlaubt
den Rollout sofort; das Team sieht das Modul erst in Stufe 2.

**Start-Prompt für Claude Code (kopieren):**

> Lies `CLAUDE.md`, `PROJEKTIERUNG-KONZEPT.md` (Abschnitt 0) und
> `PLAN_PROJ_V3_GOLIVE.md`. Setze Phase 84 um, danach 85 und 86. Datenbank-
> Änderungen nur idempotent in migrate.py. Nach jeder Phase: Zusammenfassung,
> Dateien, Testschritte. Entscheidungen in `docs/projektierung-entscheidungen.md`.
> Checkboxen abhaken, committen, nicht pushen.

---

## Abgleich mit dem umgesetzten V4-Stand (30.09.2026, PLAN_GESAMT B2)

V4 (v17) wurde ohne V3 gebaut; nichts aus V3 ist dort doppelt vorhanden.
Berührungspunkte und Abweichungen – beim Bau berücksichtigt, nichts doppelt:

- **Phase 84:** Steckbrief-Felder `restoel_liter`, `stemmarbeiten`,
  `erdleitung_m` gibt es seit V4 → im Auftragsdaten-Formular mit angeboten
  (löst Provisorium 3). „gefördert“ ist KEIN Steckbrief-Feld, sondern das
  Angebotsfeld `kfw_gefoerdert` (ja/nein/unbekannt), das PLAN_V14 (B3,
  Phase 96) auch im „Extern erledigt“-Dialog abfragt – eine Quelle für
  `bza.ist_gefoerdert` (löst Provisorium 2). Steckbrief-Felder bleiben im
  Code (`STECKBRIEF_FELDER`), das Blatt ergänzt Zusatzfelder über die
  neuen Spalten `eingabe`/`bezeichnung` (Zeilen mit `quelle_typ =
  auftragsdaten`).
- **Phase 85:** Phasenwerte seit V4: `abnahme` und `freigabe` statt
  „Abnahme & Freigabe“ (Vorlage und Import nutzen die V4-Werte).
- **Phase 86:** Die Demo-Sendesperre `projekt_testadresse` (V4, BzA-Mail)
  gilt jetzt auch im Modus `pilot`. Die Go-live-Prüfpunkte der
  Stücklisten-Seite (≥ 90 % zugeordnet, Collin-Testdatei) wandern in die
  Checkliste (Provisorium 1); die Stücklisten-Seite verlinkt dorthin.
  Portal-URLs umfassen seit V4 auch `url_kfw_zuschussportal`.
- **CLAUDE.md:** Abschnitt heißt „Neu in v18 – Projektierung Go-live“
  (v16/v17 belegt).
- Teil B Stufe 0 (Rollout) ist durch PLAN_GESAMT Teil A abgedeckt.

## Teil A – Bauphasen

### Phase 84 – Auftragsdaten für TAIFUN-Aufträge

Problem: Externe TAIFUN-Angebote tragen nur Nummer, Endbetrag, Datum,
optional PDF – keine Positionen. Steckbrief-Ableitung, Sub-Mails und
Stückliste haben damit keine Grundlage.

- [x] Dialog „Angebot → Projekt" erkennt TAIFUN-Angebote und zeigt nach der
  Zuordnung eine zweite Seite **„Auftragsdaten"** (Pflicht, je gewählter Sparte):
  - WP: Hersteller (Bosch / Mitsubishi / Vaillant / Sonstige) · Serie/Modell ·
    Leistungsklasse (kW) · Innengerät-Variante · Puffer (l) · Warmwasser
    (Speicher l / über WP nein) · Aufstellort Außengerät (Boden / Wand /
    Garagendach / Fundament nötig) · Zählerschrank (bleibt / 2-Feld / 3-Feld /
    4-Feld) · Unterverteilung (ja/nein) · Alte Anlage (Öl / Gas / Sonstige,
    Standort) · Öltankentsorgung (nein / ja: Größe l, Material, Zugang) ·
    Dynamischer Tarif / iMSys / HEMS (ja/nein) · Folierung (ja/nein) ·
    Materiallift/Kran (ja/nein) · Besonderheiten (Freitext).
  - PV: Module (Anzahl, kWp) · Speicher (kWh) · Wechselrichter · Dachtyp ·
    Gerüst nötig · Wallbox mit dabei. KL / WB: Gerät, Anzahl, Besonderheiten.
  - Felder = die Steckbrief-Felder aus Blatt „Steckbrief" (Feldliste von dort
    laden, damit Änderungen am Blatt automatisch im Formular landen; Feldtyp
    und Optionen aus einer neuen Spalte `eingabe` im Blatt: `text` / `zahl` /
    `ja_nein` / `auswahl:A|B|C`).
  - Pflicht-Upload des Angebots-PDFs, falls am TAIFUN-Eintrag noch keins liegt
    (Ablage am Angebot wie bisher + Kopie in Galerie „Allgemein").
- [x] Speichern schreibt die Werte als Steckbrief (Kennzeichen `quelle =
  auftragsdaten`, nicht `manuell`, damit die FP-Erfassung sie später
  überschreiben darf) und aktiviert Pakete wie bei Tool-Angeboten.
- [x] Nachträglich änderbar: Button „Auftragsdaten bearbeiten" am Gewerk
  (nur TAIFUN-Gewerke), öffnet dasselbe Formular.
- [x] Material-Aufgabe („Stückliste geprüft und Material bestellt") zeigt bei
  TAIFUN-Gewerken den Hinweis „Bestellung aus TAIFUN-Positionen – Datei
  manuell in Montagedokumente ablegen" statt des UGL-Buttons.
- [x] Vorbereitung Stufe 2 (nicht bauen, nur Schnittstelle vorsehen):
  Funktion `auftragsdaten_aus_pdf(pdf) -> dict` als Stub, der später
  Text aus dem TAIFUN-PDF liest und das Formular vorbelegt.
- [x] Test: TAIFUN-Angebot → Projekt mit Auftragsdaten → Steckbrief gefüllt,
  Sub-Mail-Platzhalter {geraet}/{oeltank} korrekt.

### Phase 85 – Bestandsimport laufender Projekte

Problem: Die meisten laufenden Aufträge (ausgebucht bis November) sind nie
durch das Tool gelaufen; die V1-Migration erfasst nur angenommene Tool-Angebote.

- [ ] **Excel-Vorlage** `docs/bestandsimport_vorlage.xlsx` (Claude Code
  erzeugt sie, Blatt „Projekte", eine Zeile je Gewerk): Kunde Anrede ·
  Vorname · Nachname · Straße · PLZ · Ort · Telefon · E-Mail ·
  Ausführungsadresse (falls abweichend) · Sparte (WP/PV/KL/WB) ·
  TAIFUN-Angebotsnummer · Auftragswert brutto · Auftragsdatum · Vertriebler
  (Name) · Kanal · Projektleiter (Name) · **Phase** (Auftragseingang /
  Feinplanung VOT / Planung / Montagevorbereitung / Montage / Abnahme &
  Freigabe) · Montage von · Montage bis · Montageteam · Elektro-Team ·
  Subteam · Termin bestätigt (J/N) · Hersteller · Leistungsklasse ·
  Innengerät · Zählerschrank · Öltankentsorgung (J/N) · Bemerkung.
  Zweites Blatt „Anleitung" mit Ausfüllhinweisen und erlaubten Werten.
- [ ] Parametrierung → Projektierung → **„Bestandsimport"**: Upload der
  Excel, **Vorschau** mit Prüfung je Zeile (Kunde vorhanden? → Duplikat-
  abgleich Name + PLZ wie beim monday-Sync; Team/Projektleiter bekannt?;
  Phase gültig?; Datum plausibel?), Fehlerzeilen markiert, Import nur der
  fehlerfreien Zeilen oder Abbruch. Import idempotent über TAIFUN-Nummer +
  Sparte (zweiter Lauf aktualisiert statt dupliziert).
- [ ] Der Import legt je Zeile an: Kunde (oder nutzt vorhandenen), Vorgang,
  externen Angebotseintrag (Status Angenommen, Badge TAIFUN, Kennzeichen
  `bestand`), Projekt (oder hängt an offenes Projekt des Vorgangs), Gewerk in
  der angegebenen Phase, Steckbrief aus den Spalten, Pakete aktiviert;
  **alle Pflichtaufgaben der Pakete vor der aktuellen Phase werden auf
  „erledigt" gesetzt** (erledigt_von = Import, Verlaufseintrag „Bestand –
  pauschal erledigt"), die Aufgaben der aktuellen Phase bleiben offen;
  Montagetermin mit Team und Bestätigung; Verlaufseintrag „Aus Bestandsimport
  angelegt (Datei, Zeile)".
- [ ] Bestandsgewerke tragen ein Badge **„Bestand"** in Akte und Karte
  (Hinweis: Daten aus Import, keine Erfassung vorhanden). Kein monday-
  Rückspiel, keine Statistik-Zählung als Neuabschluss (Kennzeichen
  `bestand` in der Statistik ausgenommen).
- [ ] Importprotokoll (Datei, Zeilen angelegt/aktualisiert/übersprungen) in
  der Parametrierung; Rückgängig je Import (löscht nur, was der Import
  angelegt hat und was seither unverändert ist).
- [ ] Test: Vorlage mit 5 Zeilen (2 Sparten beim selben Kunden, 1 Fehlerzeile,
  1 Duplikat-Kunde), zweiter Lauf ohne Dubletten.

### Phase 86 – Go-live-Hilfen

- [ ] **Freigabe je Rolle statt nur admin/alle:** `freigabe_modus` erweitern
  um `pilot` = Admin + ausgewählte Benutzer (Liste in der Parametrierung);
  damit läuft Stufe 1 mit dem Projektierer und einem Montageteam, während
  der Rest weiter Null-Kacheln sieht.
- [ ] Startportal-Badge: „Demo · Coming soon" bei admin, „Pilot" bei pilot,
  kein Badge bei alle.
- [ ] Checkliste „Bereit für Go-live" als Seite in der Parametrierung mit
  Live-Prüfung: Absender-Postfach hinterlegt und Testmail erfolgreich ·
  Kalender-Modus gewählt und Test-Termin in Outlook angelegt · mindestens
  ein Benutzer je Rolle Projektierung/Montage · Teams mit Mitgliedern ·
  Standard-Sub je Typ · Portal-URLs gepflegt · Collin-Kundennummer ·
  Stücklisten-Blatt ohne Beispielnummern · Formulare abgenommen (Häkchen
  durch Admin) · Bestandsimport durchgeführt. Jede Zeile grün/rot mit
  Link zur Stelle.
- [ ] `CLAUDE.md`: Abschnitt „Neu in v16 – Projektierung Go-live" (Nummer =
  höchste + 1) mit den drei Punkten Auftragsdaten TAIFUN, Bestandsimport,
  Freigabe pilot + Go-live-Checkliste.

---

## Teil B – Organisatorische Checkliste (kein Code)

### Stufe 0 – Rollout im Demo-Modus (sofort möglich)

- [ ] Absprache mit dem Lead-Management-Chat: gemeinsamer Rollout-Tag.
- [ ] `git push`, auf dem Terminal-Server `update.bat`, Migrationslog prüfen
  (Phasen-Umzug, Galerie-Umzug, Paket-Kennzeichnung, Anzahl Projekte).
- [ ] Als Admin durchklicken: Board, Akte eines migrierten Projekts, Meine
  Aufgaben, Kalender, Montage-Sicht (Admin sieht alle Teams).

### Vor Stufe 1 – Entscheidungen und Einrichtung

- [ ] **Postfach (Entscheidung Andreas, Umsetzung M365-Admin):**
  Shared-Postfach `projektierung@friondo.de`; „Senden als" für alle Benutzer
  mit Rolle Projektierung und Innendienst; Graph-Berechtigungen
  `Mail.Send.Shared`, `Mail.Read.Shared`, `Calendars.ReadWrite.Shared`
  (Anleitung: `docs/graph-einrichtung.md`). Adresse in der Parametrierung
  eintragen, Testmail an eine eigene Adresse.
- [ ] **Kalender (Empfehlung):** ein gemeinsamer Kalender „Montageplanung"
  im Postfach projektierung@ mit Kategorie je Team (Montageteam 1–10,
  Subteam 1–5) – statt 15 Team-Postfächer. Monteure abonnieren den Kalender
  auf dem Handy. Modus in der Parametrierung setzen, Test-Termin anlegen,
  in Outlook verschieben, Rücklauf im Tool prüfen.
- [ ] **Benutzer und Teams:** Projektierer, Feinplaner, Elektroplaner mit
  Rolle Projektierung; Monteure mit Rolle Montage und Team-Zuordnung;
  Standard-Projektleiter/-Feinplaner/-Elektroplaner setzen.
- [ ] **Subunternehmer** anlegen (GaLa-Bau, WP-Montage, Elektro, Entsorgung,
  Dachdecker, Lift/Kran, Gerüst) mit E-Mail und Standard je Typ; Sub-Mail-
  Vorlagen im Logik-Blatt einmal lesen und Wortlaut anpassen.
- [ ] **Portal-URLs** eintragen: BzA-Portal, SpotmyEnergy-Partnerportal,
  Heizreport, GC Online Plus. Collin-Kundennummer.
- [ ] **Formulare abnehmen:** Montagebericht, Inbetriebnahme-, Abnahme-
  protokoll (49 Felder im Blatt „Formulare") – mit einem Monteur durchgehen,
  Felder streichen/ergänzen.
- [ ] **Fristen** je Aufgabe im Blatt „Aufgabenpakete" eintragen (frist_tage,
  frist_bezug) – mindestens für Planung WP, Planung Elektro, Montage-
  vorbereitung.
- [ ] **Feinplanungs-Fragen:** TAIFUN-Feinplanungsformular hochladen und
  Blatt „Fragen FP-WP" daran angleichen.

### Stufe 1 – Pilot (2 Wochen)

- [ ] `freigabe_modus = pilot`: Projektierer, Feinplaner, Elektroplaner,
  ein Montageteam.
- [ ] 3–5 **neue** Aufträge (Tool- und TAIFUN-Angebot gemischt) komplett
  durchs Tool: Angebot → Projekt, Feinplanung mobil mit Fotos, Sub-Mail
  echt versenden, Termin mit Kunde bestätigen, Montage-Backend auf der
  Baustelle, Abnahme mit Unterschrift, Rechnungsfreigabe.
- [ ] Alter Weg (Mail-Auftragsaufbereitung, Loops) läuft parallel weiter.
- [ ] Wöchentlich 30 Minuten Rückmeldungen sammeln → Nachbesserungen über
  Claude Code (kleine Fixes direkt, größere als PLAN_PROJ_V4).

### Stufe 2 – Vollbetrieb

- [ ] **Bestandsimport:** Excel aus den heutigen Listen befüllen (nur offene
  Projekte; Phase ehrlich setzen; Montagetermine und Teams eintragen),
  Vorschau prüfen, importieren, Kalender kontrollieren.
- [ ] Alle Monteure mit Team, kurze Einweisung je Team (15 Minuten am Handy:
  Liste, Kalender, Galerie, Formulare).
- [ ] `freigabe_modus = alle`; Startportal ohne Badge; alter Weg endet
  (Stichtag kommunizieren: ab dann keine Auftragsaufbereitung per Mail).

### Stufe 3 – laufend

- [ ] Collin: Artikelnummern ins Stücklisten-Blatt, erste UGL-Datei mit
  Collin abstimmen, IDS-Connect-Zugang anfragen.
- [ ] Heizreport-API-Doku anfordern → Anbindung aktivieren.
- [ ] SpotmyEnergy-Partnerbetreuer nach Schnittstelle fragen.
- [ ] TAIFUN-PDF-Auslesen für Auftragsdaten (Stufe 2 von Phase 84).
- [ ] PV/KL/WB-Pakete inhaltlich festlegen.
- [ ] Rechnungen/OP/Mahnwesen (Konzept V4).
