# Umsetzungsplan v16 – Klimakonfigurator (Bosch Climate, Single- und Multi-Split)

Voraussetzung: kein anderer Plan in Umsetzung (strangübergreifend geprüft
03.10.2026); v22 (PLAN_V15) und v23 (PLAN_LEAD_V2, Phasen 104–112) sind
committet und ausgerollt. CLAUDE.md und
konfigurator_logik_v5.xlsx sind Live-Master im Projektordner
`C:\Users\a.scheelen\Tools\Angebotstool` (Git-Arbeitskopie). ALLE PHASEN
DIESES PLANS IN EINEM DURCHLAUF UMSETZEN (Reihenfolge einhalten, jede
Checkbox nach Umsetzung und Test abhaken, am Ende Gesamtübersicht mit
Testergebnissen und offenen Punkten, fachliche Rückfragen gebündelt).
migrate.py idempotent. **Kein git push vor Freigabe.**

CLAUDE-Abschnitt: **„Neu in v24"** (höchste + 1; v23 = Lead-Management
V2). Phasen **113–117** (frei laut Zuordnungstabelle; 104–112 gehören zu
PLAN_LEAD_V2).

Fachliche Vorlage (freigegeben 03.10.2026): `docs\KL-Logik-Entwurf.xlsx`
(Blätter Lesehilfe KL · Fragen KL · KL-Artikel · Paketmatrix KL ·
Kombinationen KL · Montagematrix KL · Aktionen KL · Angebotsaufbau KL ·
KL-Parameter · Annahmen & offene Punkte). Der Entwurf nennt in der
Lesehilfe noch „PLAN_V17" – gemeint ist dieser Plan. Positionsquellen:
`Artikel-Preislisten\Klima\Ersatzangebot KL.xlsx` (48 Positionen) und
`Artikel-Preislisten\Klima\Musterangebot KL.xlsx` (Aufbau-Referenz,
Systemgarantie). Dieser Plan wurde gegen den Code-Stand vom 30.09.2026
geschrieben; Berührungspunkte mit v22 (Positions-Fragment im Editor,
editierbare Gruppen-Überschrift, Einheit „psl.", Fehlerprotokoll) und v23
(Objektart am Kunden belegt O01/O03/PO01 vor; Sparte GW als fünfter Code;
V2-Router vor den V1-Routern) vor dem Bau prüfen und übernehmen.

## Entscheidungen (Chat Angebotstool, 02./03.10.2026)

- Der Klimakonfigurator wird – wie der PV-Konfigurator in v16 – ein
  **vollwertiger Konfigurator**: Eine grüne KL-Katalog-Erfassung erzeugt
  ein Tool-Angebot (19 % USt, kein Förderblock, keine Wirtschaftlichkeit);
  die TAIFUN-Schiene bleibt nur für Ampel-Fälle und Freitext-Erfassungen.
- **Nur Bosch Climate**, Wandgeräte; Serien 3200i (Standard, Vorbelegung),
  7000i, 8000i. Die Serie 3000i ist ausgelaufen; die Single-Sets der
  3200i-Serie (KL034–KL036) haben Vorrang vor den Einzel-Außengeräten
  KL030–KL032 (nur Editor-Artikel).
- **Auslegung je Raum:** Kühllast = Raumfläche × Höhenfaktor × W/m²
  (60 normal / 90 stark), Innengeräte-Klasse = kleinste Klasse mit
  Nennleistung ≥ Kühllast (9 → 2,6 kW · 12 → 3,5 · 18 → 5,3 · 24 → 7,0);
  über 7,0 kW → Ampel. Alle Werte im neuen Blatt „KL-Parameter".
- **Multi-Split:** Außengerät = kleinstes Gerät der Serie, dessen
  Kombinationszeile (Blatt „Kombinationen KL", Bosch Tab. 7 für CL5000M)
  die aufsteigend sortierten Klassen-Codes enthält; kein Treffer → Ampel.
  Höchstens 5 Innengeräte je Außengerät, höchstens 3 Außengeräte.
- **Montagepauschalen** aus der Montagematrix (1/1, 2/1, 2/2, 3/1, 3/2,
  4/1); alle anderen Kombinationen (z. B. 5 Innengeräte an 1 Außengerät)
  → Ampel „individuell". 5 m Leitung je Innengerät und die Konsole sind in
  der Pauschale enthalten; 6–10 m → +5 m, 11–15 m → +10 m KL017, über
  15 m → Ampel.
- **Keine Bitumen-Durchführung** bei Klima (KL007 nie automatisch);
  Flachdach → fachlicher Hinweis statt Position. Reparaturschalter, SLS,
  ÜSS, FI-LS 3P+N, „Aufpreis weitere IDU" nur händisch im Editor.
- **Neue Position KL050 „Rollgerüst"** 499 € netto (ohne TAIFUN-GUID) bei
  KZ01 = Gerüst; bei Schrägdach steckt das Gerüst in den Dacharbeiten KL004.
- **Kein Friondo Fit for Future** im Klima-Angebot (keine Pos. 014–017,
  kein Gruppen-Trigger). WLAN-Gateway KL013 je Innengerät, Vorbelegung
  „als Eventualposition" (wie im Musterangebot).
- Positionen KL001–KL048 = Ersatzangebot KL Pos. 001–048 (GUID-Anker wie
  bei PV), KL049 = Systemgarantie (Musterangebot Pos. 006, 0 €), KL050 =
  Rollgerüst. Angebotsaufbau: Block 1 Montage/Zuschläge, Block 2 Elektro,
  Block 3 „Klimaanlage Bosch" (Geräte, Gateway, Garantie, Auslegungszeile).
- Erfassungsliste als Vorgangs-Sicht, Chip-Vereinheitlichung und
  Online-Signatur mit SMS-Code sind **nicht** Teil dieses Plans
  (→ PLAN_V17).

## Phase 113 – Logik-Blätter in der Live-Excel & Import der Klima-Positionen

- [x] **Blatt „Fragen KL" ersetzen** (Spalten Seite | ID | Fragetext | Typ |
      Antwortmöglichkeiten | Anzeigen wenn | Hinweis; Inhalt und
      Reihenfolge exakt wie Blatt „Fragen KL" des Entwurfs – 28 Fragen):
      neu KO06 Geräteserie, KO07 Demontage, KO08 WLAN-Steuerung, KO09
      Bemerkung, KR08 Raumfläche in m² (Pflicht), KR09 Deckenhöhe, KR10
      Wärmelast, KR11 Wanddurchbruch; geändert KR05 „bis 5 m | 6–10 m |
      11–15 m | über 15 m", KA02 „unter 2 m | 2–4 m | über 4 m", KE02
      „0–5 m | 6–10 m | 11–15 m | über 15 m"; KE02 und KE03 mit
      „nur wenn KE01 = Nein oder Unklar". Reihenfolge der Raumfragen:
      KR01, KR08, KR09, KR10, KR02, KR03, KR04, KR05, KR06, KR11, KR07.
      Die redaktionellen Zusätze des Entwurfs („NEU ·", „GEÄNDERT …",
      „[ANNAHME]") kommen **nicht** in die Live-Excel; Spalte Hinweis
      wörtlich: KO05 „öffnet je Raum einen eigenen Fragenblock (höchstens
      12 Räume)" · KO06 „Vorbelegung Climate 3200i. Climate 7000i: nur bis
      3,4 kW je Raum · Climate 8000i: nur Single-Split bis 3,5 kW" · KO08
      „Vorbelegung „als Eventualposition" – Gateway je Innengerät" · KO09
      „z. B. abweichende Montageorte bei mehreren Außengeräten" · KR01
      „z. B. Wohnzimmer" · KR08 „Grundfläche des Raums (Dezimalzahl
      möglich, z. B. 22,5)" · KR05 „bis 5 m je Innengerät in der
      Montagepauschale enthalten" · KR07 „es erscheinen nur so viele
      Optionen wie Außengeräte (KO04)" (Text muss erhalten bleiben –
      steuert `_wiederhol_klone`) · KA01 „gilt für alle Außengeräte –
      abweichende Orte in der Bemerkung (KO09)" · KZ01 „bei Montage auf
      dem Schrägdach ist das Gerüst in den Dacharbeiten enthalten" · S01/S02
      wie bisher · alle übrigen leer.
- [x] **Neue Blätter** aus dem Entwurf 1:1 übernehmen (Formatierung wie
      die PV-Blätter: Calibri 11, fette Kopfzeile, Spaltenbreiten):
      „KL-Artikel" (Spalten wie „PV-Artikel": KL-Nr. | Datei | Pos. in
      Datei | GUID | Bezeichnung (1. Zeile) | VK netto (€) | EK (€) | EP;
      **GUID-Spalte beim Anlegen aus den Dateien neu füllen** – die
      Orientierungsspalte des Entwurfs ist für KL030–KL048 um eine Zeile
      versetzt), „Paketmatrix KL", „Kombinationen KL" (215 Zeilen: 205
      CL5000M aus Bosch Tab. 7 + 10 CL7000M [ANNAHME]),
      „Montagematrix KL", „Aktionen KL" (Spalten wie „Aktionen PV"),
      „Angebotsaufbau KL", „KL-Parameter" (Spalten Parameter | Wert |
      Einheit | Bemerkung). Die Blätter „Lesehilfe KL" und „Annahmen &
      offene Punkte" bleiben im Entwurf; im Blatt „Lesehilfe" der
      Live-Excel einen Absatz „Klima (v24)" mit Rechenweg und Blattliste
      ergänzen.
- [x] **Aktionen KL – Schreibweisen** (Parser wie PV, Spalte Aktion):
      `Artikel: KL017 × 5` · `Artikel: KL013 × Innengeräte` ·
      `Artikel: KL013 × Innengeräte als EP` · `Artikel: KL001 ×
      Außengeräte` · `Artikel: KL004 ×1 · KL005 ×1 · KL006 ×1 je
      Außengerät` · `AMPEL: individuell – Grund: <Text>` · **neu**
      `Hinweis: <Text>` (fachlicher Hinweis am Vorgang, keine Position,
      keine Ampel) · `–`. Mengenwörter: „Innengeräte" = Σ Räume,
      „Außengeräte" = KO04, „je Außengerät" = × KO04, „je Raum" = Aktion
      gilt je Raum-Klon (KRxx#1, KRxx#2 …, Mengen werden addiert).
      Zusatzbedingung-Spalte wie PV (`nur wenn KA01 ≠ auf einem
      Schrägdach` als `nur wenn KA01 = auf dem Boden oder an der Außenwand
      oder auf einer Terrasse oder auf einem Balkon oder auf einem
      Flachdach oder noch unklar` schreiben – der Parser kennt kein ≠).
      Zeilen des Entwurfs mit „Fachlicher Hinweis: …" in die Form
      `Hinweis: …` bringen; die Zeilen „Auslegung"/„Grundpaket
      Montagepauschale" bleiben als Dokumentation stehen (der Rechenweg
      steckt in `app/kl_auslegung.py`, Werte im Blatt „KL-Parameter").
- [x] **Angebotsaufbau KL – Inhalt-Spalte nennt jede KL-Nummer
      ausdrücklich** (Sortierung im Block folgt der Reihenfolge im Text,
      wie `_index_im_inhalt` bei PV): Block 1 „(ohne Überschrift)":
      `KL020 · KL021 · KL022 · KL023 · KL024 · KL025 Montagepauschale lt.
      Montagematrix · KL019 Demontage · KL016 Kondensatpumpe · KL014
      Kernbohrung Beton · KL017 Zusatzmeter · KL004 · KL005 · KL006
      Dacharbeiten · KL050 Rollgerüst · KL015 Arbeitsbühne`; Block 2
      „(ohne Überschrift)": `KL001 · KL008 Elektro · KL009 Gehäuse · KL003
      §14a-Anmeldung`; Block 3 „Klimaanlage Bosch": `KL034 · KL035 ·
      KL036 · KL033 · KL037 · KL038 · KL039 · KL040 · KL043 · KL044 ·
      KL045 · KL046 · KL047 · KL048 Außengeräte/Sets · KL026 · KL027 ·
      KL028 · KL029 · KL041 · KL042 Innengeräte · KL013 WLAN-Gateway ·
      KL049 Systemgarantie · Auslegungszeile`; Zeilen Summenblock
      („Netto · Umsatzsteuer 19 % · Gesamt-Betrag · ggf. Rabatt ·
      Endbetrag", kein KfW-/Förderblock, keine Wirtschaftlichkeit),
      Nachtexte („Profil-Textblock KL"), Anhänge und Protokoll wie im
      Entwurf.
- [x] **KL-Parameter** (Zeilen wörtlich aus dem Entwurf; Standardwerte
      zusätzlich im Code, `parameter_lesen` meldet fehlende Zeilen wie bei
      PV v22): W/m² normal 60 · W/m² stark 90 · Höhenfaktor bis 2,5 m 1,0
      · Höhenfaktor 2,5–3 m 1,1 · Höhenfaktor über 3 m 1,2 · Klasse 9 bis
      2,6 kW · Klasse 12 bis 3,5 · Klasse 18 bis 5,3 · Klasse 24 bis 7,0 ·
      Leitung je Innengerät inklusive 5 m · Meterposition Zusatzleitung
      KL017 · Standardserie „Climate 3200i (Standard)" · Max. Innengeräte
      je Außengerät 5 · Max. Außengeräte 3 · §14a-Außengeräte „CL5000M
      105/4 E; CL5000M 125/5 E" · Gewerbe-Verhalten „Hinweis" · Rollgerüst
      VK 499 (nur Startwert für den Import von KL050; danach gilt der
      Artikelpreis in der Parametrierung).
- [x] **Lader `app/logik.py`:** Sparte KL bekommt – analog `pv_*` – die
      Felder `kl_aktionen`, `kl_bloecke`, `kl_paket` (Serie, Typ, Klasse →
      Artikel-Refs + Bemerkung), `kl_kombis` (Außengerät → Anzahl →
      Menge Kombinationen; Codes aufsteigend normalisiert), `kl_montage`
      ((Innengeräte, Außengeräte) → KL-Nr.), `kl_parameter` +
      `kl_parameter_einheit`, `kl_artikel` (Pinning). Parametrierung →
      „Logik prüfen" prüft zusätzlich: jede KL-Referenz in Aktionen,
      Paketmatrix, Montagematrix und Kombinationen existiert im Blatt
      „KL-Artikel"; jede Kombination enthält nur die Codes 7/9/12/18/24;
      Montagematrix ohne Doppelzeilen; Hinweis von KR07 enthält
      „Optionen wie … (KO04)"; alle Pflichtparameter vorhanden.
- [x] **Import „Artikel → Klima-Positionslisten importieren"**
      (Parametrierung, neben dem PV-Import; migrate.py ruft ihn
      automatisch, wenn referenzierte KL-Artikel fehlen): liest
      `Artikel-Preislisten/Klima/Ersatzangebot KL.xlsx` (Spalten GUID |
      Position | Menge | Einheit | Beschreibung | E-Preis | G-Preis |
      Einkaufspreis Material) → `pos_nr` „KL001" … „KL048" (= Pos. 001–048),
      `guid` aus derselben Zeile, `bezeichnung` = erste Zeile der
      Beschreibung, `beschreibung` = Rest, `einheit`, `e_preis_cent`,
      `ek_cent`, `quelle` = eigener Klima-Wert (analog PV); aus
      `Musterangebot KL.xlsx` nur Pos. 006 → KL049 (GUID
      `{38FC5932-9389-46DE-A9D0-8855676E1FD8}`, 0 €); KL050 „Rollgerüst /
      Arbeitsgerüst, Auf- und Abbau" ohne GUID, Einheit psl., VK 499,00 €,
      EK leer (Parametrierung → Artikel, Hinweis „EK ergänzen"). Re-Import
      aktualisiert Texte/Preise über den GUID-Anker im Blatt „KL-Artikel",
      legt nie doppelt an; WP- und PV-Import fassen KL-Artikel nicht an und
      umgekehrt. `_x000D_` bereinigen. Positionen ohne EP-Kennzeichen –
      das EP-Flag kommt nur aus der Aktion (KL013).
- [x] **Textregeln (Blatt „Textregeln", neue Zeilen, greifen bei jedem
      Re-Import):** (1) „Positionen KL020–KL025: nach der Zeile ‚Diese
      Leistung besteht aus folgenden Positionen' den Leistungsumfang
      ergänzen" – Text wörtlich [ANNAHME, Innendienst liest gegen – A13]:
      „– Montage der Innengeräte (Wandmontage) und des Außengeräts auf
      Wand- oder Bodenkonsole (Konsole enthalten)
      – Kältemittelleitung isoliert, Kondensatleitung, Elektroverbindung
      Innen-/Außengerät und Montagekanal bis 5 m je Innengerät
      – eine Kernbohrung je Innengerät durch die Außenwand (bis 32 cm)
      – Evakuieren, Dichtheitsprüfung mit Dokumentation (F-Gase-Verordnung),
      Inbetriebnahme und Einweisung
      – An- und Abfahrt, Kleinmaterial, Entsorgung des Verpackungsmaterials"
      (2) „Position KL013: ‚für Split-Klimagerät CL3000i' ersetzen durch
      ‚für Bosch Climate Split-Klimageräte'" [ANNAHME]. (3) „Positionen
      KL026–KL029: Zeile ‚Split Inneneinheit' bleibt; Bezeichnung =
      ‚BOSCH CL3200iU W <26|35|53|70> E Inneneinheit <kW>'" nur, falls die
      erste Beschreibungszeile länger als 60 Zeichen ist (sonst keine
      Änderung).
- [x] Logik-Validierung grün; Import auf DB-Kopie: 50 KL-Artikel aktiv,
      Stichprobe KL023 = 3.178,00 € psl., KL038 = 1.966,24 € Stück,
      KL034 = 1.341,60 € Set, KL049 = 0,00 €, KL050 = 499,00 € ohne GUID.

## Phase 114 – Rechenkern `app/kl_auslegung.py` & Einbindung

- [x] **Neues Modul** nach dem Muster `app/pv_auslegung.py` (keine
      DB-Zugriffe außer in `positionen_zusammenstellen`):
      `parameter(logik) -> dict` · Datenklassen `Raum` (nr, name, flaeche,
      hoehenfaktor, w_qm, kuehllast_kw, klasse, aussengeraet_nr,
      grund), `Aussengeraet` (nr, raeume, typ „single"/„multi",
      kombination „9+9+9", artikel: list[str], bezeichnung, grund) und
      `Auslegung` (serie, raeume, aussengeraete, innengeraete_gesamt,
      aussengeraete_gesamt, montage_ref, ampeln: list[str], hinweise:
      list[str]) mit `als_dict()` · `auslegen(logik, antworten)` ·
      `artikel_ermitteln(logik, antworten, a)` · `positionen_zusammenstellen
      (logik, antworten, session, erfassung=None)` · `auslegungs_text(a)` ·
      `ampel_gruende(logik, antworten)` · `fachliche_hinweise(logik,
      antworten)` · `protokoll_zeilen(logik, antworten)`.
- [x] **Rechenweg (verbindlich):** je Raum i (Klone `KR08#i`, `KR09#i`,
      `KR10#i`, `KR07#i` …): kuehllast_kw = round(KR08 × Höhenfaktor(KR09)
      × W/m²(KR10) ÷ 1000, 2); Klasse = erste Grenze aus „Klasse 9 bis" …
      „Klasse 24 bis" mit Grenze ≥ kuehllast_kw; keine Grenze → Ampel G1.
      Je Außengerät n (1 … KO04): Räume mit KR07 = n; 0 Räume → Validierung
      (siehe unten); 1 Raum → Paketmatrix (Serie KO06, Typ „Single",
      Klasse) → Artikel-Refs aus der Spalte Artikel (alle `KL\d{3}` der
      Zelle, z. B. „KL033 … + KL029" = zwei Positionen); Zelle „nicht im
      Sortiment" → Ampel G2 (Text aus der Bemerkung nach „→ AMPEL: ");
      2–5 Räume → Innengeräte je Raum aus Paketmatrix (Typ
      „Multi-Innengerät") + Außengerät: Kandidaten = Zeilen „Multi-
      Außengerät" der Serie in Blattreihenfolge (klein → groß), gewählt
      wird der erste Kandidat, dessen Kombinationsliste für `len(raeume)`
      die aufsteigend sortierten Codes („9+9+12") enthält; kein Kandidat →
      Ampel G4; Serie ohne Multi (8000i) → Ampel G3; mehr als 5 Räume →
      Ampel G5. Montage: `kl_montage[(Σ Räume, KO04)]`; fehlt → Ampel G6.
      §14a: Außengerät-Bezeichnung in Parameterliste „§14a-Außengeräte" →
      KL003 ×1 je Treffer. Rundung Kühllast 2 Dezimalstellen, Anzeige
      deutsch („1,50 kW", „25,0 m²").
- [x] **Ampel-Gründe (Texte wörtlich, Platzhalter in <>):**
      G1 „Kühllast über 7,0 kW: Raum <Nr> <Name> (<kW> kW) – Raum teilen
      oder Sonderlösung" · G2 „Klasse <Code> in Serie <Serie> nicht
      verfügbar – Serie wechseln" · G3 „Multi-Split in Serie Climate 8000i
      nicht verfügbar" · G4 „Multi-Split-Kombination <Codes> an Außengerät
      <n> nicht freigegeben (Bosch Tab. 7)" · G5 „Mehr als 5 Innengeräte an
      Außengerät <n>" · G6 „Montagekombination <Innengeräte> Innengeräte /
      <Außengeräte> Außengeräte nicht hinterlegt" · G7 „Leitungslänge über
      15 m: Raum <Nr> <Name> – max. Leitungslänge der Serie prüfen" (KR05)
      · G8 „Elektrozuleitung über 15 m" (KE02). Alle Gründe erscheinen in
      der Erfassungsliste/Vorgangsakte wie bei WP/PV („individuell",
      Grund), im Protokoll-PDF und beim Button „Erneut prüfen".
- [x] **Fachliche Hinweise (keine Ampel, Texte wörtlich):** KO03 = „Nein,
      Zustimmung noch nicht vorhanden" → „Zustimmung des Eigentümers
      einholen" · KO01 = Gewerbe → „Gewerbeobjekt – Auslegung prüfen" (bei
      Parameter Gewerbe-Verhalten „AMPEL" stattdessen Ampel „Gewerbeobjekt
      – individuelle Auslegung") · KR04 = Innenwand → „Raum <Nr> <Name>:
      Innengerät an Innenwand – Leitungsführung und Kondensatablauf
      prüfen" · KR03 = „regelmäßig heizen und kühlen" → „Raum <Nr> <Name>:
      Heizbetrieb als Hauptzweck – Serie 7000i/8000i empfohlen" · KA01 =
      Flachdach → „Flachdach – keine Dachdurchführung, Leitungsführung über
      Attika/Fassade prüfen" · KA01 = noch unklar → „Montageort Außengerät
      klären" · KA02 = über 4 m und KZ01 = vom Boden/Leiter → „Montagehöhe
      über 4 m ohne Gerüst/Bühne prüfen" · KE01 = Unklar → „Stromversorgung
      am Außengerät prüfen" · KO05 > 12 → „Mehr als 12 Räume – Rest
      händisch". Hinweise landen wie bei WP am Vorgang (fachliche Hinweise)
      und im Protokoll.
- [x] **Positionen** (`positionen_zusammenstellen`, Blockzuordnung über
      `kl_bloecke` wie bei PV, gleiche Artikel im selben Block addiert,
      EP-Flag aus der Aktion): Block 1 Montagepauschale + Zuschläge, Block
      2 Elektro, Block 3 Gruppe „Klimaanlage Bosch": Außengeräte/Sets in
      Außengerät-Reihenfolge, dann Innengeräte je Klasse gebündelt (Menge =
      Anzahl Räume dieser Klasse über alle Außengeräte), KL013, KL049,
      danach die **Auslegungszeile** (Bezeichnung „Auslegung der
      Klimaanlage", 0,00 €, Menge 1, Einheit „psl.", Beschreibung =
      `auslegungs_text`) als letzte Zeile von Block 3. Vorbelegungen
      (`konfigurator.vorbelegung`): KO06 = Standardserie, KO08 = „als
      Eventualposition", KR10#i = „stark", wenn KR02#i = Dachgeschoss (vom
      AD änderbar); KO01 aus `kunden.objektart` wie O01/PO01 seit v23
      (EFH → EFH, RH → RMH, REH → REH, MFH → MFH).
- [x] **`auslegungs_text` (wörtlich, eine Zeile je Raum/Außengerät):**
      „Auslegung Klimaanlage – Serie Bosch <Serie ohne „(Standard)">"
      · je Raum „Raum <Nr> „<Name>": <m²> m² × <Faktor> × <W/m²> W/m² =
      <kW> kW → Innengerät <Nennleistung> kW (Klasse <Code>), Außengerät
      <n>" · je Außengerät „Außengerät <n>: <Bezeichnung der 1. Zeile des
      Artikels>, <Single-Split | Multi-Split, Kombination <Codes>>, <k>
      Innengerät(e)" · „Montage: <Innengeräte> Innengerät(e) / <Außengeräte>
      Außengerät(e) (Pauschale). Leitungslänge bis 5 m je Innengerät
      enthalten." · „Auslegung nach Raumfläche; verbindliche Festlegung in
      der technischen Feinplanung vor Ort."
- [x] **Einbindung:** `angebot_aufbau.angebot_anlegen`: `sparte == "KL"`
      → `kl_auslegung.positionen_zusammenstellen`, `kfw_json = "{}"`, neue
      Spalte `angebote.kl_json` (Text, Migration; Inhalt `als_dict()`),
      `konfigurator_typ = "KL"`, `ust_satz = 19`. `konfigurator.
      ampel_gruende`/`protokoll`/`fachliche_hinweise` verzweigen bei
      `logik.sparte == "KL"` nach `kl_auslegung` (wie PV). `app/routers/
      erfassung.py`: die KL-Katalog-Erfassung läuft exakt wie PV (v16) –
      gleiche Status, Innendienst-Schritte, Buttons „Angebot erzeugen"
      und „Erneut prüfen"; **Validierung beim Absenden**: jedes Außengerät
      1 … KO04 hat mindestens einen Raum (Meldung wörtlich: „Außengerät
      <n> hat keinen zugeordneten Raum – Zuordnung (KR07) prüfen oder
      Anzahl Außengeräte anpassen."), KR08 > 0 je Raum („Raum <Nr>:
      Raumfläche fehlt"), Dezimaleingabe mit Komma erlaubt. Freitext-
      Erfassung KL unverändert (TAIFUN-Schiene).
- [x] **Profile & Regeln:** `angebotsprofile.positionsregeln_anwenden`
      fügt bei `konfigurator_typ == "KL"` keine WP-Artikel (014–017)
      ein; Versandregeln (Enni-CC, SWD-Empfänger leer) gelten weiter.
      DB-Ampel-Schwellen je Sparte: Parametrierung zeigt die Zeile KL
      (Schlüssel `db_ampel_rot_unter_KL`/`db_ampel_gruen_ueber_KL`,
      Standard wie WP). Editor: Gruppen-Überschrift „Klimaanlage Bosch"
      editierbar (v22), Positions-Fragment, Lieferschein, „Überarbeiten"/
      „Duplizieren"/„Für anderen Kunden kopieren", monday-Rückspielung
      (Deal-Wert brutto 19 %) und Statistik (Sparte KL, Tool/TAIFUN
      getrennt) funktionieren ohne Sonderfall.

## Phase 115 – Texte, Anhänge, Parametrierung

- [x] **Textblöcke „Friondo KL Standard / Enni / SWD / Sparkasse DU"**
      per Migration anlegen (Mechanik wie die PV-Textblöcke in v16; in der
      Parametrierung editierbar; Profil-Zuordnung wie PV). Enni/SWD ohne
      Nachtext A (wie bei WP), Sparkasse DU mit eigenem Nachtext wie WP.
      Kein Platzhalter `[WIRTSCHAFTLICHKEIT]`, keine Vollmacht (Nachtext D).
      Alle KL-Texte sind Entwürfe für das Gegenlesen durch den Innendienst
      (A14) – Formulierungen zu Zertifizierung/Kältemittel sind [ANNAHME].
- [x] **Vortext KL (wörtlich):**
      „**Ihr individuelles Klimaanlagen-Angebot zum Festpreis**
      **Angenehmes Raumklima – kühlen im Sommer, heizen in der Übergangszeit**

      Sehr geehrte Damen und Herren,

      vielen Dank für Ihr Vertrauen in die Friondo GmbH. Mit einer modernen
      Split-Klimaanlage von Bosch schaffen Sie an heißen Tagen ein angenehmes
      Raumklima, heizen effizient in der Übergangszeit und verbessern die
      Luftqualität in Ihren Räumen.

      Anbei erhalten Sie Ihr maßgeschneidertes Angebot. Darin enthalten sind:
      [Haken] Ihre individuelle Klimaanlage – ausgelegt auf Ihre Räume
      [Haken] Detaillierte Installationsleistungen – fachgerecht, sauber und
      termingerecht
      [Haken] Transparent und Festpreis – klar verständlich und ohne
      versteckte Kosten
      [Haken] Unser Rundum-Sorglos-Service – von der Planung bis zur
      Inbetriebnahme

      **Warum Friondo?**
      [Haken] **Fachkompetenz & Qualität** – Als Meisterbetrieb, Mitglied
      der Innung und VDI-zertifiziertes Fachunternehmen setzen wir auf
      höchste Standards.
      [Haken] **Fachgerechte Kältetechnik** – Montage, Dichtheitsprüfung und
      Inbetriebnahme durch geschultes Fachpersonal nach den Vorgaben der
      F-Gase-Verordnung.
      [Haken] **Persönliche Beratung** – Wir begleiten Sie von der ersten
      Idee bis zur perfekten Lösung für Ihr Zuhause.
      [Haken] **Effizienz & Komfort** – Inverter-Technik mit hoher
      Energieeffizienz, leiser Betrieb und auf Wunsch Steuerung per App.

      **Wir sind auf Wärmepumpen und Klimatechnik spezialisiert und gehören
      in der Region zu den führenden Anbietern.** Lassen Sie uns gemeinsam
      für ein angenehmes Raumklima sorgen!

      Ihr Friondo-Team"
- [x] **Nachtext A KL** = Nachtext A „Ihre Zahlungsoptionen bei Friondo"
      (ANGEBOTSTEXTE.md Abschnitt 5) mit drei Änderungen: „Investieren Sie
      jetzt in Ihre Energie- oder Wärmelösung" → „Investieren Sie jetzt in
      Ihre Klimalösung"; der Absatz „Planbare Monatsraten – Zum Beispiel:
      … Oder ab 250 € pro Monat ohne Förderung" entfällt samt Fußnote
      „*Beispielrate …"; „Dank Cloover konnten wir unsere Wärmepumpe …" →
      „Dank Cloover konnten wir unsere Anlage einfach, fair und transparent
      finanzieren."
- [x] **Nachtext B KL** = Nachtext B „Installationsvoraussetzungen"
      (Haftungsbegrenzung, Rücktrittsrecht, Zahlung, Bindefrist, AGB,
      Datenschutz unverändert) **ohne** den Abschnitt „Hinweis zur
      KfW-Förderung"; stattdessen nach „Zahlung" der Abschnitt (wörtlich,
      [ANNAHME]): „**Hinweis zur Kältetechnik**
      Die angebotenen Geräte arbeiten mit dem Kältemittel R32. Montage,
      Evakuierung, Dichtheitsprüfung und Inbetriebnahme erfolgen durch
      sachkundiges Personal nach den Vorgaben der F-Gase-Verordnung (EU)
      2024/573; die Dichtheitsprüfung wird dokumentiert. Die
      Kältemittel-, Kondensat- und Elektroleitungen sind bis 5 m je
      Innengerät enthalten; längere Leitungswege sind als eigene Position
      ausgewiesen. Der Montageort der Außeneinheit wird so gewählt, dass
      Schall- und Abstandsvorgaben eingehalten werden; die endgültige
      Festlegung erfolgt in der technischen Feinplanung vor Ort."
- [x] **Nachtext C KL** = Nachtext C (Schlussseite) ohne den Absatz
      „Aufschiebende Bedingung" und ohne die Zeile „Voraussichtliches Datum
      der Umsetzung … Bewilligungszeitraum nach Nummer 9.4.1."; stattdessen
      „Voraussichtlicher Ausführungszeitraum: ______________"; Unterschriften-
      block unverändert.
- [x] **Anhänge:** Zeile „(Bosch Climate Broschüre – Zulieferung)" mit Regel
      „wenn Sparte = KL" und Bemerkung „v24: Datei nach Lieferung in
      anlagen/ legen und diese Zeile auf den Dateinamen setzen" (wie der
      PV-Platzhalter); Unternehmenspräsentation und Ratenkauf greifen über
      „immer" (Ratenkauf nicht bei Enni/SWD, unverändert).
- [x] **Parametrierung:** Tabelle „KL-Parameter" (wie „PV-Parameter" v22,
      mit Einheit, fehlende Zeilen als Hinweis mit Standardwert), Button
      „Artikel → Klima-Positionslisten importieren", Artikelliste mit
      Filter „Sparte KL" (pos_nr KL*), Lesezugriff auf Paketmatrix KL /
      Montagematrix KL / Kombinationen KL als Ansicht (nur anzeigen, keine
      Bearbeitung – Live-Master bleibt die Excel). AD sieht wie bisher nie
      EK/DB.
- [x] **Erfassungsbogen:** Seite „Räume" rendert je Raum den Block KR01 …
      KR07 mit Zwischenüberschrift „Raum <i>" (wie heute); Zahleneingabe
      KR08 mit `inputmode="decimal"`; Seite „Objekt & Anlage" zeigt KO06
      vor KO04. Protokoll-PDF: Seite „Auslegung" mit den Zeilen aus
      `protokoll_zeilen` (je Raum: Fläche, Höhe, Wärmelast, Kühllast,
      Klasse, Außengerät; je Außengerät: Gerät und Kombination; Montage).

## Phase 116 – Tests & Abnahme

- [x] `tests/test_kl_v24.py` mit den Kontrollfällen (alle mit KO01 EFH,
      KO02 1995, KO03 Ja, KR02 Erdgeschoss, KR03 hauptsächlich kühlen,
      KR04 Außenwand, soweit nicht anders genannt; Toleranz ± 0,01 €):
      · **Fall A – Musterangebot nachgestellt:** KO06 Climate 3200i
        (Standard), KO04 1, KO05 3, KO07 Nein, KO08 als Eventualposition;
        Raum 1 „Wohnzimmer" 25 m², Raum 2 „Schlafzimmer" 18 m², Raum 3
        „Büro" 28 m², alle bis 2,5 m / normal / KR05 bis 5 m / KR06 Nein /
        KR11 Außenwand bis 32 cm / KR07 1; KA01 an der Außenwand, KA02
        unter 2 m, KE01 Nein, KE02 0–5 m, KE03 Ja, KZ01 vom Boden/Leiter.
        Erwartung: grün; Kühllasten 1,50 / 1,08 / 1,68 kW → Klassen
        9/9/9 → Kombination „9+9+9" → CL5000M 79/3 E (53/2 scheidet aus:
        max. 2 Innengeräte); Positionen in dieser Reihenfolge: KL023 ×1
        3.178,00 · KL008 ×1 498,00 · [Gruppe „Klimaanlage Bosch"] KL038 ×1
        1.966,24 · KL026 ×3 à 292,14 = 876,42 · KL013 ×3 à 82,50 **EP** ·
        KL049 ×1 0,00 · Auslegungszeile 0,00 psl.; **Netto 6.518,66 € ·
        USt 19 % 1.238,55 € · Gesamt 7.757,21 €** (identisch mit dem
        Musterangebot). `kl_json` enthält `aussengeraete[0].kombination ==
        "9+9+9"`.
      · **Fall B – Single-Split voll bestückt:** KO04 1, KO05 1, KO07 Ja,
        KO08 Nein; Raum 1 „Wohnküche" 30 m², 2,5–3 m, stark (30 × 1,1 × 90 =
        2,97 kW → Klasse 12), KR05 6–10 m, KR06 Ja, KR11 Beton oder dicker
        als 32 cm; KA01 an der Außenwand, KA02 2–4 m, KE01 Ja, KZ01 Gerüst
        erforderlich. Erwartung: grün; KL020 1.587,00 · KL019 529,00 ·
        KL016 356,00 · KL014 169,00 · KL017 ×5 à 68,00 = 340,00 · KL050
        499,00 · KL001 229,00 · KL035 1.786,00 · KL049 0,00 ·
        Auslegungszeile; kein KL013; **Netto 5.495,00 € · USt 1.044,05 € ·
        Gesamt 6.539,05 €**. KE02/KE03 nicht sichtbar (KE01 = Ja).
      · **Fall C – Montagematrix-Ampel:** KO04 2, KO05 5; Räume 1–2 an
        Außengerät 1 (50 m² normal bis 2,5 m → 3,00 kW → 12; 55 m² stark
        bis 2,5 m → 4,95 kW → 18 → „12+18" → CL5000M 53/2 E), Räume 3–5 an
        Außengerät 2 (je 20 m² normal → 1,20 kW → 9 → „9+9+9" → CL5000M
        79/3 E). Erwartung: Ampel mit genau dem Grund G6 „Montagekombination
        5 Innengeräte / 2 Außengeräte nicht hinterlegt"; Protokoll zeigt
        beide Kombinationen.
      · **Fall D – Serienampeln:** (D1) KO06 Climate 8000i, KO04 1, KO05 2
        → G3. (D2) KO06 Climate 7000i, KO08 Ja, 1 Raum 50 m² normal bis
        2,5 m → 3,00 kW → Klasse 12 → grün mit KL044 + KL042 + KL020 +
        KL013 ×1 82,50 (kein EP) + KL049. (D3) KO06
        Climate 7000i, 1 Raum 70 m² normal bis 2,5 m → 4,20 kW → Klasse 18
        → G2 „Klasse 18 in Serie Climate 7000i nicht verfügbar – Serie
        wechseln".
      · **Fall E – Kühllast:** 1 Raum 100 m², über 3 m, stark → 10,80 kW
        → G1. **Fall F – Kombination:** KO04 1, KO05 2, beide Räume 60 m²
        stark bis 2,5 m → 5,40 kW → „24+24" → G4 „Multi-Split-Kombination
        24+24 an Außengerät 1 nicht freigegeben (Bosch Tab. 7)".
      · **Fall G – Validierung:** KO04 2, alle Räume KR07 = 1 → Absenden
        blockiert mit der Meldung aus Phase 114; nach Korrektur grün.
      · **Fall H – Schrägdach & §14a:** KO04 1, 4 Räume je 40 m² normal
        bis 2,5 m (2,40 kW → 9 ×4 → „9+9+9+9" → CL5000M 105/4 E), KA01 auf
        einem Schrägdach, KZ01 Gerüst erforderlich → KL004/KL005/KL006 je
        ×1, **kein** KL050, KL003 ×1 (§14a-Liste), KL025 (4/1). Entfernt man
        „CL5000M 105/4 E" aus dem Parameter, entfällt KL003.
- [x] Regression: WP-Angebot unverändert (Kontrollwerte Netto 30.245,43 €),
      PV unverändert (`tests/test_pv_v13.py`, `tests/test_wirtschaft-
      lichkeit_v22.py` grün), Lieferschein für Fall A, Freitext-Erfassung
      KL weiterhin TAIFUN-Schiene, Projektierung legt beim Annehmen von
      Fall A ein Gewerk KL an. migrate.py zweimal auf der Server-DB-Kopie
      in diagnose\ ohne Fehler, danach Voll-Crawl + Abnahmeskript grün.
- [x] Abnahme-PDFs (ohne Kundendaten) nach `docs/klima/abnahme-A-AN-<Nr>.pdf`
      (Fall A) und `docs/klima/abnahme-B-AN-<Nr>.pdf` (Fall B) sowie das
      Protokoll-PDF zu Fall C für Andreas ablegen; Sichtprüfung: Gruppe
      „Klimaanlage Bosch", EP-Zeile „EP.", Auslegungszeile am Blockende,
      „19,00 % USt.", keine Förder-/Wirtschaftlichkeitsseiten, keine
      Vollmacht.

## Phase 117 – Doku & Übergabe

Ergebnis 03.10.2026: Kontrollfälle A–H grün (tests/test_kl_v24.py + Agenten-Tests, 135 KL-Tests),
Gesamtlauf siehe Gesamtübersicht/CLAUDE.md v24, Abnahmeskript 93/93, migrate.py zweimal auf der
Server-DB-Kopie (diagnose/test_v24) ohne Fehler, Voll-Crawl ohne Absturz. Commit v24, kein Push.

- [x] CLAUDE.md: Abschnitt „Neu in v24 – Klimakonfigurator (abgestimmt
      03.10.2026)" (Plan: PLAN_V16.md, Phasen 113–117; Rechenweg,
      Blätter, Artikel KL001–KL050, Ampel-Gründe G1–G8, Texte, Grenzen
      v1: KA01/KA02 für alle Außengeräte gemeinsam, Innengeräte je Klasse
      gebündelt), Zuordnungstabelle `| v24 | PLAN_V16.md | 113–117 |`,
      „Zentrale Dateien" um `Artikel-Preislisten/Klima/` und die
      KL-Blätter ergänzen, Hinweis in „Neu in v8", dass KL seit v24
      Konfigurator ist.
- [x] `docs/nach-dem-update-v24.md`: Team-Hinweise (neuer KL-Bogen, Serie,
      Raumfläche Pflicht, Vorbelegungen, EP-Gateway, Rollgerüst, händische
      Positionen KL002/KL007/KL010–KL012/KL018, EK für KL050 ergänzen) und
      die offenen Rückfragen A1–A15 aus dem Entwurf als Liste zum Abhaken.
      Blatt „Lesehilfe" der Live-Excel aktualisiert; `docs\KL-Logik-
      Entwurf.xlsx` bleibt unverändert als Herkunftsnachweis liegen.
- [x] Gesamtübersicht am Ende: Testergebnisse je Fall A–H, gefundene
      Abweichungen zwischen Entwurf und Code, Liste aller [ANNAHME]-Stellen,
      die beim Bau konkretisiert wurden, gebündelte Rückfragen. Commit mit
      sprechender Nachricht; **kein push vor Freigabe**.

## Zulieferungen / bewusst offen

- **A1** Single-Split Klasse 24 (7,0 kW) in Serie 3200i: bis ein
  3200i-Nachfolger in TAIFUN angelegt und neu exportiert ist, gilt die
  Paketmatrix-Zeile KL033 + KL029 [ANNAHME]. Andreas / TAIFUN.
- **A3** Meterzuschlag KL017 auch für die Elektrozuleitung (KE02) –
  umgesetzt als [ANNAHME]. **A4** §14a-Geräteliste (105/4, 125/5) nach
  Datenblatt prüfen – Parameter. **A5** Kombinationen CL7000M analog
  CL5000M (nur Codes 9/12) – Bosch-Tabelle 7000M nachreichen. **A6**
  Montagematrix erweitern, sobald Pauschalen für 5/1, 4/2, 3/3 … vorliegen.
  **A7** Flachdach als Hinweis (nicht Ampel). **A9** Gewerbe als Hinweis
  (Parameter). **A10** Code 7 (2,0 kW) nicht vergeben – Artikel fehlt in
  TAIFUN. **A11** Maximale Leitungslängen je Serie – Grenze 15 m je Raum.
- **A8** KA01/KA02 gelten für alle Außengeräte gemeinsam; Außengerät-Block
  je Gerät ist eine spätere Stufe. Ebenso: Innengeräte je Außengerät
  getrennt ausweisen, Heizleistungs-Auslegung (KR03), Dachbelegungs-/
  Fotofunktionen.
- **A13** Leistungsumfang der Montagepauschalen – Text im Plan ist
  [ANNAHME], vollständiger TAIFUN-Text kann ihn ersetzen. **A14** Alle
  KL-Textblöcke liest der Innendienst gegen. **A15** Bosch-Climate-
  Broschüre für `anlagen/` (Anhangsregel „wenn Sparte = KL").
- EK für KL050 (Rollgerüst) in der Parametrierung ergänzen (Innendienst).
- PLAN_V17 (nächster Plan des Strangs): Erfassungsliste als Vorgangs-Sicht
  mit vereinheitlichten Chips, Online-Signatur mit SMS-Code.

## Anhang A – Referenz-Rechenweg (für den Test; Python)
```python
GRENZEN = [("9", 2.6), ("12", 3.5), ("18", 5.3), ("24", 7.0)]
HOEHE = {"bis 2,5 m": 1.0, "2,5–3 m": 1.1, "über 3 m": 1.2}
WQM = {"normal": 60, "stark (Süd-/Westseite, große Fenster, Dachgeschoss)": 90}

def kuehllast(flaeche, hoehe, last):
    return round(flaeche * HOEHE[hoehe] * WQM[last] / 1000, 2)

def klasse(kw):
    for code, grenze in GRENZEN:
        if kw <= grenze:
            return code
    return None                      # → Ampel G1

def aussengeraet(kandidaten, kombis, codes):
    """kandidaten: ODU-Namen klein → groß; kombis[odu][n] = Menge
    der freigegebenen Kombinationen; codes: Klassen-Codes der Räume."""
    schluessel = "+".join(sorted(codes, key=int))
    for odu in kandidaten:
        if schluessel in kombis.get(odu, {}).get(len(codes), set()):
            return odu, schluessel
    return None, schluessel          # → Ampel G4

MONTAGE = {(1, 1): "KL020", (2, 1): "KL021", (2, 2): "KL022",
           (3, 1): "KL023", (3, 2): "KL024", (4, 1): "KL025"}

# Fall A: kuehllast(25,"bis 2,5 m","normal") == 1.5 → "9";
#         18 m² → 1.08 → "9"; 28 m² → 1.68 → "9";
#         aussengeraet(["CL5000M 53/2 E","CL5000M 79/3 E","CL5000M 105/4 E",
#                       "CL5000M 125/5 E"], kombis, ["9","9","9"])
#         == ("CL5000M 79/3 E", "9+9+9"); MONTAGE[(3, 1)] == "KL023"
# Fall B: kuehllast(30,"2,5–3 m","stark (…)") == 2.97 → "12" → KL035
```
