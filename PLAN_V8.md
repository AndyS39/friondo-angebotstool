# Umsetzungsplan v8 – „Mammut": Multi-Sparten, Heizlast, Prozess-Feinschliff

Voraussetzung: Phasen 0–46 umgesetzt, v7 läuft auf dem Server.
WICHTIG: CLAUDE.md und konfigurator_logik_v5.xlsx sind die Live-Master im
Projekt – NICHT ersetzen, sondern gemäß Phase 47 direkt ändern. Je Phase:
Ansatz erläutern → umsetzen → testen → abhaken → committen. Alle
Schema-Änderungen in migrate.py (idempotent).

## Phase 47 – Grundlagen: CLAUDE, Logik-Excel, neue Formulare

- [x] CLAUDE.md: Kopf auf „(v8)"; im v7-Abschnitt den Satz zur Erfassung
      „Erledigt (extern) + Archiv" korrigieren zu „Erledigt (extern); Archiv
      erst manuell"; neuen Abschnitt einfügen:

      ## Neu in v8 (abgestimmt 28.08.2026)
      - Multi-Sparten: Ein Lead kann mehrere Interessen (WP/PV/KL/WB) haben;
        je Sparte eine eigene Erfassung mit Status-Chips am Lead. Der Lead
        verlässt „Leads VOT" erst, wenn alle Interessen erfasst oder
        ausgeblendet sind. Sparten-Auswahl beim Erfassungsstart
        (Lead-Interessen vorausgewählt); je Sparte Weiche Katalog/Freitext,
        WB vorerst immer Freitext. PV/KL sind reine Erfassungsformulare
        (Blätter „Fragen PV" / „Fragen KL", ohne Artikel-Aktionen) und laufen
        über die TAIFUN-Schiene; Sparten-Badge an Erfassung, Warteschlange,
        externem Angebotseintrag und in der Statistik.
      - WP-Bogen: Heizlast-Abfrage (entscheidet bei Bekanntsein über das
        Paket, Unterdimensionierungs-Matrix in der Paketmatrix; kWh bleibt
        Pflicht fürs Protokoll); Rechnungs-/Ausführungsanschrift getrennt
        (monday-Adresse = Ausführungsort); Unterverteilung (Pos. 152) mit
        MID-Zwischenzähler (Z23); Wärmemengenzähler Pos. 096 × Anzahl bei
        mehr als einer WE; Stemmarbeiten Pos. 126 im Öl-Zweig; Abschluss-
        Seite „Einschätzung" mit Hot-Ampel + Wiedervorlage (Startwerte der
        Verfolgung).
      - Angebote: Verfolgungs-Block oben im Editor; Förder-Editor
        baustein-basiert (Grundförderung, Klima-Bonus, Einkommensbonus,
        Höchstkosten einzeln überschreibbar, Kennzeichen „manuell
        angepasst"); Drag & Drop ohne Scroll-Sprung, mit Auto-Scroll;
        Vollmacht-Häkchen wieder leer; Kunden-Nr. entfällt im Briefkopf;
        PDF zeigt Rechnungsanschrift im Empfängerfeld und abweichenden
        Ausführungsort als eigene Zeile.
      - Rollen: Außendienst sieht „Meine Angebote" (read-only, Kundenpreise
        und PDF, ohne EK/DB/Editor/Versand).
      - Abgelehnt-Prozess: Pflichtdialog „Grund der Ablehnung" (Auswahlliste
        aus Parametrierung + Freitext) für Tool- und TAIFUN-Angebote;
        Statistik-Auswertung „Ablehnungsgründe"; täglicher Prüflauf setzt
        versendete Angebote ohne Annahme/Ablehnung nach 90 Tagen
        (Parametrierung) auf Abgelehnt mit Grund „90 Tage Ablauf" –
        außer eine Wiedervorlage liegt in der Zukunft.

- [x] Logik-Excel (Live-Datei!) – WP-Bogen ändern, danach Validierung + neu
      einlesen:
      1. Fragen: nach A03 einfügen – „Heizlast bekannt?" (Ja | Nein) und
         „Heizlast in kW" (Dezimalzahl, nur wenn Ja; Hinweis: entscheidet
         über das Paket, A03 bleibt Pflicht fürs Protokoll).
      2. Paketmatrix: Spalte „Heizlast" ergänzen – bis 5,9 → 4 kW;
         6,0–7,9 → 6 kW; 8,0–9,9 → 7 kW; 10,0–12,9 → 10 kW;
         13,0–15,9 → 13 kW. Aktion: ab 16,0 → AMPEL „Leistungsklasse zu
         hoch". Regel in Aktionen: Heizlast (falls angegeben) hat Vorrang
         vor der kWh-Zuordnung.
      3. Adressen: O06/O07 ersetzen durch „Rechnungsanschrift identisch mit
         Ausführungsort?" (Ja | Nein) + bei Nein strukturierte Felder
         Rechnungs-Name (optional, Vorbelegung Kunde), Straße, PLZ, Ort.
         Hinweis im Blatt: monday-Adresse = Ausführungsort.
      4. Elektro-Block, nur wenn E02 = Nein, nach E01/E02-Kaskade:
         „Unterverteilung erforderlich?" (Ja | Nein); Ja → Pos. 152 ×1 und
         Folgefrage „MID-Zwischenzähler erforderlich?" (Ja | Nein);
         Ja → Z23 ×1. Einsortierung Angebotsaufbau Block 7 (Elektro).
      5. Zusatzartikel: Z23 „Privater Unterzähler inkl. Anbindung –
         3-Phasen Stromzähler mit MID zur privaten Verbrauchsmessung einer
         Wohneinheit", Stück, VK 217,00 €, EK 155,00 €.
      6. Nach H01 (Heizkreise), nur wenn Anzahl WE > 1 (O01 = 2FH oder MFH
         bzw. O03 > 1): „Wärmemengenzähler erforderlich?" (Ja | Nein);
         Ja → „Anzahl Wärmemengenzähler" (Zahl) → Pos. 096 × Anzahl als
         NORMALE Position (kein EP), Angebotsaufbau Block 2.
      7. Öl-Zweig, nach der Tankgrößen-Frage (nur Stahl/Kunststoff):
         „Stemmarbeiten für einen Durchgang benötigt?" (Ja | Nein);
         Ja → Pos. 126 ×1, Angebotsaufbau Block 5.
      8. Neue letzte Seite „Einschätzung" (alle Katalog-Bögen):
         „Einschätzung des Kunden" (heiß | warm | kalt) und
         „Wiedervorlage am" (Datum, optional) – keine Artikel; Werte werden
         Startwerte der Angebotsverfolgung.
- [x] Neue Blätter „Fragen PV" und „Fragen KL" anlegen (Spaltenstruktur wie
      „Fragen", Aktionen-Spalte entfällt/bleibt leer) – Inhalte exakt aus
      den Spezifikationen unten. Validierung um die neuen Blätter und den
      Fragetyp „Wiederholgruppe" erweitern.
- [x] migrate.py-Grundgerüst v8 anlegen (Felder folgen je Phase).

### Spezifikation Blatt „Fragen PV"
Seite Objektdaten: PO01 Gebäudeart (EFH | 2FH | REH | RMH | MFH | Gewerbe) ·
PO02 Baujahr Haus (Zahl) · PO03 Letzte Dachsanierung (Freitext) ·
PO04 Stromverbrauch inkl. WP & WB in kWh (Zahl) · PO05 Bemerkung (Freitext groß).
Seite DC-Dachmontage: PD01 Dachart (Satteldach | Flachdach | Walmdach |
Sonstige) · PD02 Dachziegel und Ortgang fotografiert? (Ja | Nein) ·
PD03 Gerüstart (Fanggerüst | Vollgerüst | Sonstiges) · PD04 Dachrinnenhöhe
in m (Zahl) · PD05 Verschattung vorhanden? (Ja | Nein) · PD06 Anzahl
Optimierer (Zahl, nur wenn PD05 = Ja) · PD07 Montage auf mehreren
Dachseiten? (Ja | Nein) · PD08 Leitungslänge DC-Kabelweg in m (Zahl) ·
PD09 DC-kWp (Zahl) · PD10 Bemerkung (Freitext groß).
Seite AC-Elektromontage: PA01 Lage ZV (KG | EG | OG | DG | Sonstiges) ·
PA02 Neue ZV erforderlich? (Ja | Nein) · PA03 Anzahl Felder (1-Feld |
2-Feld | 3-Feld | 4-Feld | Sonstige; nur wenn PA02 = Ja) · PA04
Ertüchtigung bestehender ZV? (Ja | Nein; nur wenn PA02 = Nein) · PA05
Externes APZ-Feld erforderlich? (Ja | Nein; nur wenn PA04 = Ja) · PA06
HAK-Leitung erneuern? (Ja | Nein; nur wenn PA04 = Ja) · PA07
Unterverteilung erforderlich? (Ja | Nein) · PA08 Tiefenerder vorhanden?
(Ja | Nein) · PA09 Leistung Wechselrichter in kW (Zahl) · PA10 Kapazität
Batteriespeicher in kWh (Zahl) · PA11 Friondo HEMS gewünscht? (Ja | Nein) ·
PA12 iMSys inkl. Smart Meter gewünscht? (Ja | Nein) · PA13 Friondo
SpotDynamic gewünscht? (Ja | Nein) · PA14 Bemerkung (Freitext groß).

### Spezifikation Blatt „Fragen KL"
Seite Objekt & Anlage: KO01 Gebäudeart (wie PO01) · KO02 Baujahr Haus
(Zahl) · KO03 Kunde ist Eigentümer? (Ja | Nein, Zustimmung des Eigentümers
liegt vor | Nein, Zustimmung noch nicht vorhanden) · KO04 Anzahl
Außengeräte (1 | 2 | 3) · KO05 Anzahl zu klimatisierender Räume (Zahl) →
öffnet Wiederholgruppe „Raum {n}".
Wiederholgruppe je Raum: KR01 Raumbezeichnung (Freitext, z. B. Wohnzimmer) ·
KR02 Lage des Raums (Keller/Souterrain | Erdgeschoss | 1. OG | 2. OG |
3. OG+ | Dachgeschoss) · KR03 Hauptzweck (hauptsächlich kühlen | kühlen und
in der Übergangszeit heizen | regelmäßig heizen und kühlen) · KR04
Montageort Innengerät (Außenwand | Innenwand | noch nicht bekannt) · KR05
Entfernung Innen- zu Außengerät (bis 3 m | 3–5 m | 6–10 m | 11–15 m |
über 16 m) · KR06 Kondensatpumpe erforderlich? (Ja | Nein) · KR07
Zuordnung zum Außengerät (Optionen dynamisch: nur so viele wie KO04).
Seite Außengerät: KA01 Montageort Außengerät (auf dem Boden | an der
Außenwand | auf einer Terrasse | auf einem Balkon | auf einem Flachdach |
auf einem Schrägdach | noch unklar) · KA02 Montagehöhe (unter 2 m |
2–4 m | über 5 m).
Seite Elektroinstallation: KE01 Geeignete Stromversorgung nahe Außengerät?
(Ja | Nein | Unklar) · KE02 Entfernung zum Sicherungskasten (0–5 m |
6–10 m | 11–15 m | über 16 m) · KE03 Freie Sicherungsplätze vorhanden?
(Ja | Nein).
Seite Zugänglichkeit: KZ01 Erreichbarkeit der Montageorte (vom Boden/
Leiter | Gerüst erforderlich | Hubsteiger erforderlich).

## Phase 48 – WP-Bogen v8 & Editor/PDF
- [x] WP-Bogen: neue Fragen aus Phase 47 umsetzen (Heizlast-Vorrang,
      Adressen, Unterverteilung/MID, Wärmemengenzähler, Stemmarbeiten,
      Abschluss-Seite „Einschätzung" → Startwerte Ampel/Wiedervorlage)
- [x] Editor: Verfolgungs-Block an den Seitenanfang
- [x] Förder-Editor baustein-basiert: Grundförderung (%), Klima-Bonus (%),
      Einkommensbonus (%), förderfähige Höchstkosten (€) einzeln
      überschreibbar; Live-Neuberechnung; Reset je Baustein; PDF-Kennzeichen
      „Förderung manuell angepasst"; alter Gesamt-Override entfällt
      (Migration: vorhandene Overrides in Höchstkosten/Zuschuss überführen
      oder als Gesamtwert weiter anzeigen – sauber dokumentieren)
- [x] Drag & Drop: Scroll-Position beim Ablegen erhalten; Auto-Scroll beim
      Ziehen an oberen/unteren Fensterrand
- [x] Vollmacht: automatische Häkchen entfernen (alle Kästchen leer)
- [x] Briefkopf: Zeile „Kunden-Nr." entfernen
- [x] PDF: Empfängerfeld = Rechnungsanschrift; Zeile „Ausführungsort: …"
      unter der Betreffzeile, wenn abweichend
- [x] migrate.py: Heizlast, Rechnungsadresse (Felder), Förder-Bausteine,
      Einschätzungs-Startwerte

## Phase 49 – Rollen, Tabs & Lead-Chips
- [x] „Meine Angebote" für Außendienst: eigene Angebote read-only inkl.
      PDF-Download und Kundenpreisen; ohne EK/DB, ohne Editor/Versand/Löschen
- [x] Tab-Fix: „Erledigt (extern)" erscheint im Reiter „Erledigt"; Archiv
      nur manuell; Migration holt falsch archivierte Fälle zurück
- [x] Leads VOT: Status-Chips je Interesse („WP ✓ · PV offen"); Lead
      verschwindet erst, wenn alle Interessen erfasst oder ausgeblendet sind;
      Ausblenden wahlweise je Sparte oder ganz
- [x] migrate.py: Chip-Status je Lead-Sparte

## Phase 50 – Multi-Sparten-Erfassung
- [x] Erfassungsstart: Sparten-Auswahl (Lead-Interessen vorausgewählt,
      weitere zuwählbar); je Sparte eigene Erfassung mit eigenem Protokoll
- [x] Weiche je Sparte: Katalog (WP aus „Fragen", PV aus „Fragen PV",
      KL aus „Fragen KL") oder Freitext; „In Freitext wechseln" überall;
      WB startet immer direkt im Freitext
- [x] Fragetyp „Wiederholgruppe" generisch umsetzen (KO05 → n Raumblöcke;
      dynamische Optionsliste KR07 aus KO04); Darstellung in Ansicht und
      Protokoll-PDF sauber je Raum
- [x] PV-/KL-/WB-Erfassungen: immer Ampel „Individuell" (reine Erfassung),
      Weg über Warteschlange → „Extern erledigt" → externer Angebotseintrag;
      Sparten-Badge an Erfassung, Warteschlange, Angebotseintrag
- [x] Filter nach Sparte in Erfassungsliste, Warteschlange, Angebotsliste;
      Statistik zusätzlich je Sparte
- [x] migrate.py: Sparte an Erfassung/Angebotseintrag; Bestandsdaten = WP

## Phase 51 – Ablehnungsgründe & 90-Tage-Automatik
- [x] Pflichtdialog bei Statuswechsel auf „Abgelehnt" (Tool + extern):
      Auswahlliste + optionales Freitextfeld; Liste in der Parametrierung
      pflegbar, Startwerte: Preis zu hoch · Wettbewerber beauftragt ·
      Förderung unsicher/abgelehnt · Projekt verschoben · Finanzierung
      gescheitert · Kunde nicht erreichbar · Technisch nicht umsetzbar ·
      Sonstiges
- [x] Grund an Angebot + Verfolgungs-Historie; Statistik-Auswertung
      „Ablehnungsgründe" (Verteilung, filterbar nach Zeitraum/AD/Kanal/Sparte)
- [x] Täglicher Prüflauf: Status „Versendet" (inkl. „Versendet (extern)"),
      älter als 90 Tage (Wert in Parametrierung), keine Wiedervorlage in
      der Zukunft → „Abgelehnt", Grund „90 Tage Ablauf"; Lauf protokollieren
- [x] docs/nach-dem-update-v8.md: Hinweis auf die einmalige Absage-Welle
      bei Altfällen (gewollt – Statistik wird ehrlich)
- [x] migrate.py: Ablehnungsgrund-Felder + Gründe-Tabelle

## Phase 52 – Migration, Abnahme & Rollout
- [ ] migrate.py final: idempotent, zweimal gegen Kopie der echten DB
- [ ] Regressionstests: bestehende Kontroll-Szenarien unverändert; NEU:
      Heizlast 8,4 kW → 7-kW-Paket (kWh-Angabe wird ignoriert);
      Unterverteilung Ja + MID Ja → Pos. 152 + Z23; Wärmemengenzähler ×3 →
      Pos. 096 ×3 (keine EP-Kennung); Öl/Stahl + Stemmarbeiten → Pos. 126;
      abweichende Rechnungsanschrift im PDF (Empfänger + Ausführungsort-
      Zeile); Klima-Erfassung mit 2 Außengeräten und 3 Räumen
      (Wiederholgruppe, KR07 zeigt nur 1–2); Ablehnung mit Grund;
      90-Tage-Lauf im Trockenmodus
- [ ] Abnahmeskript v8-Block; git push → Rollout per update.bat →
      docs/nach-dem-update-v8.md abarbeiten
