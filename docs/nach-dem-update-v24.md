# Nach dem Update v24 (PLAN_V16) – Klimakonfigurator Bosch Climate

**Entwurf (Agent D, Phase 117) – wird nach der Integration (Phase 116) von
Agent E / Andreas ergänzt und freigegeben.**

Ab diesem Update erzeugt eine **grüne KL-Katalog-Erfassung ein vollständiges
Klima-Angebot im Tool** – wie bei Wärmepumpe (v1) und PV (v16). Klima-Angebote
rechnen mit **19 % USt**, haben **keinen Förderblock**, **keine
Wirtschaftlichkeitsseiten**, **keine Vollmacht** und **kein Friondo Fit for
Future** (keine Pos. 014–017). Die TAIFUN-Schiene bleibt nur für Ampel-Fälle
(„individuell") und Freitext-Erfassungen. Angeboten werden ausschließlich
**Bosch Climate** Wandgeräte: Serien **3200i** (Standard), **7000i**, **8000i**;
Single-Split und Multi-Split.

## Für den Außendienst – der neue KL-Bogen

1. **Objekt & Anlage:** Gebäudeart, Baujahr, Eigentümer (wie bisher), **neu
   „Geräteserie" (KO06)** – vorbelegt mit *Climate 3200i (Standard)*; *Climate
   7000i* nur bis 3,4 kW je Raum, *Climate 8000i* nur Single-Split bis 3,5 kW
   (sonst Ampel). Danach Anzahl Außengeräte (1–3), Anzahl Räume (max. 12 im
   Bogen, mehr → Hinweis „Rest händisch"), **neu** Demontage der Altanlage
   (KO07), **neu** WLAN-Steuerung (KO08, vorbelegt *„als Eventualposition"* →
   Gateway je Innengerät als EP-Zeile im Angebot), **neu** Bemerkung (KO09,
   z. B. abweichende Montageorte bei mehreren Außengeräten).
2. **Räume – je Raum ein Block „Raum <i>":** Bezeichnung, **Raumfläche in m²
   (Pflicht, Dezimalzahl mit Komma möglich, z. B. 22,5)**, Deckenhöhe (bis
   2,5 m | 2,5–3 m | über 3 m), Wärmelast (normal | stark – bei Dachgeschoss
   wird „stark" vorgeschlagen, änderbar), Lage, Hauptzweck, Montageort
   Innengerät, Entfernung zum Außengerät (**bis 5 m in der Pauschale**, 6–10 m
   → +5 m, 11–15 m → +10 m Zusatzleitung, über 15 m → Ampel), Kondensatpumpe,
   **neu** Wanddurchbruch (Beton/dicker als 32 cm → Zuschlag Kernbohrung),
   Zuordnung zum Außengerät (es erscheinen nur so viele Optionen wie
   Außengeräte).
3. **Außengerät:** Montageort (gilt für alle Außengeräte – abweichende Orte in
   die Bemerkung), Montagehöhe (unter 2 m | 2–4 m | über 4 m).
4. **Elektroinstallation:** Stromversorgung nahe Außengerät (Ja → Anschluss-
   pauschale; Nein/Unklar → Elektroinstallation mit Einzelabsicherung, dann
   zusätzlich Entfernung zum Sicherungskasten und freie Sicherungsplätze).
5. **Zugänglichkeit:** vom Boden/Leiter | Gerüst erforderlich (→ **Rollgerüst
   KL050, 499 € netto** – nicht bei Schrägdach, dort steckt das Gerüst in den
   Dacharbeiten) | Hubsteiger (→ Arbeitsbühne).
6. **Beim Absenden prüft das Tool:** jedes Außengerät hat mindestens einen Raum
   („Außengerät <n> hat keinen zugeordneten Raum – Zuordnung (KR07) prüfen
   oder Anzahl Außengeräte anpassen.") und jede Raumfläche ist > 0 („Raum
   <Nr>: Raumfläche fehlt").

**So rechnet das Tool:** Kühllast je Raum = Raumfläche × Höhenfaktor (1,0 /
1,1 / 1,2) × 60 bzw. 90 W/m²; Innengeräte-Klasse = kleinste Klasse mit
Nennleistung ≥ Kühllast (9 → 2,6 kW · 12 → 3,5 · 18 → 5,3 · 24 → 7,0). Ein Raum
am Außengerät → Single-Split-Set; 2–5 Räume → Multi-Split mit dem kleinsten
Außengerät, dessen Bosch-Kombinationsliste die Klassen enthält. Montagepauschale
aus der Montagematrix (1/1, 2/1, 2/2, 3/1, 3/2, 4/1).

**Individuell (orange) wird eine KL-Erfassung bei:** Kühllast über 7,0 kW in
einem Raum · Klasse in der gewählten Serie nicht verfügbar · Multi-Split in
Serie 8000i · Kombination nicht freigegeben (Bosch Tab. 7) · mehr als 5
Innengeräte an einem Außengerät · Montagekombination nicht hinterlegt (z. B.
5 Innengeräte an 1 Außengerät, 4/2, 3/3) · Leitungslänge über 15 m ·
Elektrozuleitung über 15 m. **Fachliche Hinweise (keine Ampel):** Zustimmung
des Eigentümers einholen · Gewerbeobjekt – Auslegung prüfen · Innengerät an
Innenwand · Heizbetrieb als Hauptzweck (Serie 7000i/8000i empfohlen) ·
Flachdach (keine Dachdurchführung) · Montageort unklar · Montagehöhe über 4 m
ohne Gerüst/Bühne · Stromversorgung prüfen · mehr als 12 Räume.

## Für den Innendienst

- **Angebot erzeugen** wie bei PV: grüne KL-Erfassung → „Angebot erzeugen" →
  Klima-Angebot mit Sparten-Badge KL, Editor, Versand, Verfolgung, monday
  (Deal-Wert brutto 19 %), Statistik. Ampel-Fälle: „Erneut prüfen" nach
  Korrektur des Bogens, sonst TAIFUN-Schiene wie bisher.
- **Angebotsaufbau:** Block 1 Montagepauschale + Zuschläge (Demontage,
  Kondensatpumpe, Kernbohrung Beton, Zusatzmeter, Dacharbeiten, Rollgerüst/
  Arbeitsbühne), Block 2 Elektro (Anschlusspauschale oder Elektroinstallation,
  Gehäuse, §14a-Anmeldung bei CL5000M 105/4 E und 125/5 E), Block 3 Gruppe
  **„Klimaanlage Bosch"** (Außengeräte/Sets, Innengeräte je Klasse gebündelt,
  WLAN-Gateway, Systemgarantie 5 Jahre 0 €, Auslegungszeile „Auslegung der
  Klimaanlage" 0,00 € psl. als letzte Zeile). Die Gruppen-Überschrift ist wie
  seit v22 im Editor änderbar.
- **EP-Gateway:** Bei KO08 „als Eventualposition" steht das Internet-Gateway
  KL013 (je Innengerät) als EP-Zeile im Angebot („EP." statt Gesamtpreis,
  zählt nicht in der Summe); bei „Ja" als normale Position; bei „Nein" gar
  nicht.
- **Rollgerüst KL050:** neue Position ohne TAIFUN-GUID, 499,00 € netto,
  Einheit psl.; nur bei Zugänglichkeit „Gerüst erforderlich" und Montageort
  ≠ Schrägdach. **Bitte den EK in der Parametrierung → Artikel ergänzen**
  (Import legt KL050 ohne EK an – bis dahin fehlt er im Deckungsbeitrag).
- **Nur händisch im Editor** (nie automatisch): KL002 Aufpreis weitere IDU,
  KL007 Durchführung am Bitumen, KL010 FI-LS 3P+N, KL011 SLS-Hauptschalter,
  KL012 AC-Überspannungsschutz, KL018 Reparaturschalter. Ebenso die
  Einzel-Außengeräte KL030–KL032 (CL3000i – ausgelaufen, Sets KL034–KL036
  haben Vorrang).
- **Texte:** Vortext und Nachtexte der Klima-Angebote sind neue Textblöcke
  „Friondo KL Standard / Enni / SWD / Sparkasse DU" (Parametrierung →
  Textblöcke). Sie sind aus den WP-Texten abgeleitet (ohne KfW, ohne
  aufschiebende Bedingung, mit „Hinweis zur Kältetechnik" und
  „Voraussichtlicher Ausführungszeitraum: ______") – **bitte gegenlesen
  (A14)**, insbesondere die Formulierungen zu F-Gase-Verordnung/Kältemittel
  R32 und den Leistungsumfang der Montagepauschalen (A13). Wortlaut in
  ANGEBOTSTEXTE.md Abschnitt 9.
- **Summenblock:** Netto · 19,00 % USt. · Gesamt-Betrag · ggf. Rabatt/
  Endbetrag – kein Förderblock, keine Wirtschaftlichkeit, keine Vollmacht.
- **Lieferschein (PDF)** für angenommene Klima-Angebote wie bei WP/PV (ohne
  Preise, ohne EP-/Textzeilen); neu steht die Gruppen-Überschrift auch im
  Lieferschein.
- **Protokoll-PDF:** Seite „Auslegung" mit Fläche, Höhe, Wärmelast, Kühllast,
  Klasse und Außengerät je Raum, Gerät und Kombination je Außengerät sowie
  der Montagekombination.
- **Anhänge:** Die Bosch-Climate-Broschüre geht mit jedem Klima-Angebot mit,
  sobald die Datei in `anlagen/` liegt und im Blatt „Anhänge" die vorbereitete
  Zeile (Regel „wenn Sparte = KL") auf den Dateinamen gesetzt ist (A15).
  Unternehmenspräsentation und Ratenkauf wie bisher („immer", Ratenkauf nicht
  bei Enni/SWD).
- **Profile:** Enni/SWD/Sparkasse DU gelten auch für Klima-Angebote – eigener
  KL-Nachtext, Versandregeln (Enni-CC, SWD-Empfänger leer) unverändert; die
  WP-Positionsregeln (HEMS-Sonderpreis, Pos. 162, 014–017) greifen bei Klima
  nicht.
- **DB-Ampel je Sparte:** Parametrierung → Deckungsbeitrags-Ampel → Zeile KL
  (leer = allgemeine Schwellen). Bitte die KL-Schwellen setzen.

## Parametrierung

- **Artikel → „Klima-Positionslisten importieren"** (neben dem PV-Import):
  liest `Artikel-Preislisten/Klima/Ersatzangebot KL.xlsx` (KL001–KL048) und
  die Systemgarantie aus `Musterangebot KL.xlsx` (KL049), legt KL050
  Rollgerüst an; Re-Import aktualisiert Texte/Preise über den GUID-Anker im
  Blatt „KL-Artikel" und legt nie doppelt an. migrate.py importiert
  automatisch, wenn referenzierte KL-Artikel fehlen. Achtung: wie beim WP-/
  PV-Import überschreibt ein Re-Import manuelle Preisänderungen an KL-Artikeln.
- **Artikelliste:** Filter „Sparte KL" (pos_nr KL*) und der Button
  „Klima-Positionslisten importieren" neben dem PV-Import (führt zur
  Import-Vorschau); KL-Artikel pflegbar wie WP/PV-Artikel (AD sieht nie EK/DB).
- **KL-Parameter** (Tabelle wie „PV-Parameter", mit Einheit): W/m² normal 60 ·
  W/m² stark 90 · Höhenfaktoren 1,0 / 1,1 / 1,2 · Klassengrenzen 2,6 / 3,5 /
  5,3 / 7,0 kW · Leitung je Innengerät inklusive 5 m · Meterposition KL017 ·
  Standardserie · Max. Innengeräte je Außengerät 5 · Max. Außengeräte 3 ·
  §14a-Außengeräte (CL5000M 105/4 E; CL5000M 125/5 E) · Gewerbe-Verhalten
  (Hinweis | AMPEL) · Rollgerüst VK 499 (nur Startwert für den Import).
  Fehlende Zeilen werden mit Standardwert als Hinweis gemeldet. Live-Master
  bleibt `konfigurator_logik_v5.xlsx`.
- **KL-Logik (Ansicht):** Paketmatrix KL, Montagematrix KL und Kombinationen KL
  als Lesesicht; „Logik prüfen" prüft zusätzlich die KL-Referenzen,
  Kombinations-Codes (7/9/12/18/24), Doppelzeilen der Montagematrix, den
  KR07-Hinweis und die Pflichtparameter.
- **Texte aus der Excel:** Die fachlichen Hinweise kommen aus den Zeilen
  „Hinweis: <Text>" des Blatts „Aktionen KL" (Platzhalter `<Nr> <Name>` je
  Raum, Zusatzbedingung z. B. KA02 nur bei KZ01 = vom Boden/Leiter), die
  Ampel-Texte „Klasse … nicht verfügbar" / „Multi-Split in Serie … nicht
  verfügbar" aus der Bemerkung „→ AMPEL: …" der Paketmatrix KL (Platzhalter
  `<Code>`, `<Serie>`). Fehlen die Zeilen, gelten die wörtlichen Texte aus
  PLAN_V16 im Code. Die übrigen Ampel-Gründe (Kühllast, Kombination,
  Montagematrix, Leitungslängen) und die Validierungsmeldungen beim Absenden
  rechnet `app/kl_auslegung.py` mit den Plan-Texten.
- **Textblöcke:** „Friondo KL Standard" (Vortext + Nachtext), „Friondo KL
  Enni", „Friondo KL SWD", „Friondo KL Sparkasse DU" (Nachtexte) – kein
  Platzhalter `[WIRTSCHAFTLICHKEIT]`.

## Grenzen der ersten Stufe (bewusst, siehe Entwurf A8)

- Montageort und Montagehöhe (KA01/KA02) gelten für **alle Außengeräte
  gemeinsam** – abweichende Orte in der Bemerkung (KO09), Innendienst passt
  das Angebot an.
- Innengeräte werden **je Klasse gebündelt** ausgewiesen (Menge = Anzahl Räume
  dieser Klasse über alle Außengeräte), nicht je Außengerät getrennt.
- Keine Heizleistungs-Auslegung (KR03 nur Hinweis), keine Dachbelegungs-/
  Fotofunktionen.

## Offene Rückfragen aus dem Entwurf (Blatt „Annahmen & offene Punkte") – zum Abhaken

- [ ] **A1** Single-Split Klasse 24 (7,0 kW) in Serie 3200i: in der Liste nur
      CL3000i 70 E (Außen) + CL3200iU W 70 E (Innen), kein Set. Da die
      3000i-Serie ausgelaufen ist: 3200i-Nachfolger in TAIFUN anlegen und Liste
      neu exportieren – oder Klasse 24 Single vorerst AMPEL. *(bis dahin:
      Paketmatrix-Zeile KL033 + KL029 [ANNAHME])* – **Andreas / TAIFUN**
- [ ] **A2** Außeneinheiten KL030–KL032 (CL3000i 26/35/53 E) werden vom
      Konfigurator nicht benutzt (Sets KL034–036 haben Vorrang), nur als
      Artikel für den Editor. – **Info**
- [ ] **A3** Elektrozuleitung KE02: Meterzuschlag KL017 auch für die Zuleitung
      (6–10 → +5 m, 11–15 → +10 m, über 15 → AMPEL) – so umgesetzt [ANNAHME].
      – **Andreas**
- [ ] **A4** §14a-Anmeldung KL003: betroffene Außengeräte nach Leistungsaufnahme
      > 4,2 kW festlegen (Vorschlag 105/4 und 125/5; Datenblatt prüfen) –
      Parameter „§14a-Außengeräte". – **Andreas / Bosch-Datenblatt**
- [ ] **A5** Kombinationen CL7000M 53/2 und 79/3: analog CL5000M angenommen (nur
      Codes 9 und 12). Bosch-Tabelle für Climate 7000 M nachreichen. –
      **Andreas / Bosch**
- [ ] **A6** Montagekombinationen außerhalb der Matrix (5/1, 4/2, 3/3, 5/2 …) =
      AMPEL individuell. Wenn Pauschalen dafür entstehen, Matrix erweitern. –
      **Andreas**
- [ ] **A7** Flachdach: keine Dachdurchführung – Außengerät mit Konsole auf dem
      Flachdach zulässig, Leitungsführung über Attika/Fassade, fachlicher
      Hinweis statt Ampel. Falls Flachdach grundsätzlich individuell sein soll,
      Aktion auf AMPEL ändern. – **Andreas**
- [ ] **A8** KA01/KA02 gelten für alle Außengeräte gemeinsam (v1-Vereinfachung).
      Bei zwei Außengeräten an unterschiedlichen Orten: Bemerkung KO09 +
      Innendienst. Spätere Stufe: Außengerät-Block je Gerät. – **Design**
- [ ] **A9** Gewerbe (KO01): fachlicher Hinweis statt AMPEL (Parameter
      „Gewerbe-Verhalten"). Bei Bedarf umstellen. – **Andreas**
- [ ] **A10** Code 7 (2,0 kW, CL3200iU W 20 E) nicht in der TAIFUN-Liste;
      kleinste vergebene Klasse ist 9 (2,6 kW). Falls gewünscht, Artikel
      nachpflegen – Kombinationen stehen schon in der Tabelle. – **Andreas /
      TAIFUN**
- [ ] **A11** Maximale Leitungslängen je Serie (Single-Sets und Multi gesamt)
      nicht bekannt – Grenze 15 m je Raum als AMPEL gesetzt; mit
      Bosch-Planungsunterlage schärfen. – **Andreas / Bosch**
- [ ] **A12** GUIDs: Musterangebot und Ersatzangebot tragen für dieselben Artikel
      unterschiedliche GUIDs (Angebots-GUIDs). Artikelquelle für den Import ist
      ausschließlich „Ersatzangebot KL" (+ Systemgarantie aus dem Muster,
      Pos. 006). – **Claude Code (beim Import geprüft)**
- [ ] **A13** Montagepauschalen-Text „Diese Leistung besteht aus folgenden
      Positionen" – die Unterpositionen fehlen im Export. Textregel (1) ergänzt
      den Leistungsumfang [ANNAHME]; vollständiger TAIFUN-Text kann ihn
      ersetzen (inkl. Dichtheitsprüfung/F-Gase-Nachweis). – **Andreas / TAIFUN**
- [ ] **A14** Nachtexte KL (Profil-Textblöcke „Friondo KL …") – aus den
      WP-Texten abgeleitet, **Innendienst liest gegen** (Vortext, Zahlungs-
      optionen ohne Monatsraten-Beispiel, Hinweis zur Kältetechnik,
      Ausführungszeitraum statt aufschiebender Bedingung). – **Innendienst**
- [x] **A15** Bosch-Climate-Broschüre für `anlagen/` (Anhangsregel „wenn
      Sparte = KL" – Zeile im Blatt „Anhänge" auf den Dateinamen setzen). –
      **Andreas** – *erledigt 06./08.10.2026: `Bosch Climate 3200i.pdf` liegt in
      `anlagen/`, Zeile im Blatt gesetzt (v27-Nachtrag 2).*
- [ ] **EK für KL050 (Rollgerüst)** in der Parametrierung → Artikel ergänzen. –
      **Innendienst**

## Rollout

`update.bat` auf dem Terminal-Server. Die Migration ergänzt die Spalte
`angebote.kl_json`, legt die fünf KL-Textblöcke an (Vor-/Nachtext Standard,
Nachtexte Enni/SWD/Sparkasse DU) und importiert die Klima-Positionslisten
automatisch, wenn referenzierte KL-Artikel fehlen (Migrationslog prüfen).
Danach in der Parametrierung „Parametrierung neu einlesen" – die Validierung
muss grün sein.

## Checkliste nach dem Rollout

- [ ] Migrationslog: kl_json, 5 KL-Textblöcke, 50 KL-Artikel (KL050 ohne GUID,
      499,00 €)
- [ ] Parametrierung: Validierung grün, KL-Parameter vollständig (kein
      Standardwert-Hinweis)
- [ ] Test-KL-Erfassung wie Kontrollfall A (3 Räume 25/18/28 m², 1 Außengerät,
      Climate 3200i) → grün → Angebot erzeugen → PDF prüfen: Gruppe
      „Klimaanlage Bosch", EP-Zeile „EP.", Auslegungszeile am Blockende,
      „19,00 % USt.", Netto 6.518,66 €, keine Förder-/Wirtschaftlichkeits-
      seiten, keine Vollmacht
- [ ] KL-Textblöcke gegengelesen (A14), EK für KL050 ergänzt
- [ ] DB-Schwellen KL gesetzt
- [ ] bestehende WP-/PV-Angebote unverändert
