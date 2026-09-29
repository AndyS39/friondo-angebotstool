# Umsetzungsplan v14 – BzA-Datenblatt (KfW-Portal) & BAFA-Anlagennummern

Voraussetzung: der zuvor laufende Plan ist abgeschlossen und ausgerollt.
CLAUDE.md und konfigurator_logik_v5.xlsx sind Live-Master. ALLE PHASEN
DIESES PLANS IN EINEM DURCHLAUF UMSETZEN (Reihenfolge einhalten, jede
Checkbox nach Umsetzung und Test abhaken, am Ende Gesamtübersicht mit
Testergebnissen und offenen Punkten). migrate.py idempotent.

Referenz im Projektordner/Uploads: ausgefülltes KfW-Muster
„BZA-AKP-GQ6-XJY-BV3" (Bestätigung zum Antrag, Programm 458) – das
BzA-Datenblatt bildet dessen Abschnitte und Feldbezeichnungen exakt ab.

## Umnummerierung und Abgleich (30.09.2026, PLAN_GESAMT B3)

- **Phasen 82–84 → 95–97** (Kollision mit PLAN_PROJ_V2/V3, Empfehlung aus
  docs/STATUS-GESAMT.md); CLAUDE-Abschnitt „Neu in v19“ (v14 belegt,
  v18 = Projektierung Go-live).
- **ABGLEICH STATT NEUBAU:** Es gibt bereits das BzA-Datenblatt am Gewerk
  (v15, `projektierung/bza.html`, HTML mit Kopier-Knöpfen) und die
  BzA-Erfassung aus v17 (BzA-ID, Kundenmail, KfW-Felder). Beide nutzen jetzt
  EINEN Generator `app/bza_datenblatt.py` in KfW-Muster-Struktur; der neue
  Button am Angebot erzeugt daraus das PDF (funktioniert ohne Projekt), die
  Gewerk-Seite zeigt dieselben Abschnitte + „Stand BzA / KfW“.
- **Erfassungsfragen – Abgleich mit dem Bogen:**
  · „Vorhandene Heizflächen“ = bestehende Frage **H02 „Verteilsystem“**
    (Heizkörper | Fußbodenheizung | Heizkörper und Fußbodenheizung |
    Sonstiges) → 35 °C nur bei „Fußbodenheizung“, sonst 55 °C. Keine
    neue Frage.
  · „Inbetriebnahmejahr“ = bestehende Frage **A02** (bisher „Baujahr der
    alten Heizung“, steuert K02 schon heute) → nur neuer Fragetext, keine
    neue Frage; Bestandswerte bleiben gültig.
  · NEU: **A20 „Nennleistung der bestehenden Heizung in kW“** (Alte Anlage,
    nach A02) und **N11 „Contracting-Modell?“** (Neue Anlage, Vorbelegung
    Nein – im KfW-Muster Teil der geplanten Wärmeversorgung).
- **Änderung laut Chat 29.09.:** Button auch an externen TAIFUN-WP-
  Einträgen (Gerät als Pflichtauswahl aus dem Blatt „BAFA-Anlagen“, die
  Erfassungsdaten liegen über „Extern erledigt“ vor); kein Button bei
  Nicht-WP. Die Checkbox „Bei externen TAIFUN-Angeboten … ausgeblendet“
  (Phase 96) gilt damit nur noch für Nicht-WP.
- **KfW-gefördert** am externen Eintrag: Feld `angebote.kfw_gefoerdert`
  existiert seit PLAN_PROJ_V3 Phase 84 (Auftragsdaten) – hier kommt die
  Abfrage im „Extern erledigt“-Dialog und am Eintrag dazu.
- Rollout (Phase 97, letzte Checkbox) läuft über PLAN_GESAMT Teil C.

## Phase 95 – BAFA-Stammdaten & Erfassungs-Ergänzungen
- [x] Neues Logik-Blatt „BAFA-Anlagen" mit Spalten: Schlüssel (WP-Paket-
      Position bzw. Klasse+Inneneinheit) | BAFA-Anlagennummer | Hersteller |
      Gerätebezeichnung (exakter Listentext) | Nennwärmeleistung kW |
      Kältemittel | Netzdienlichkeit | E/E-Anzeige. Startbefüllung:

      045 → 16019273 · Bosch · Compress CS3800iAW 4 OM-S (CS3800iAW 4 O-S
            + AWMi) · 4,00 kW · R290 · Ja · Ja
      046 → 16019274 · Compress CS3800iAW 6 OM-S (CS3800iAW 6 O-S + AWMi)
            · 6,00 kW
      047 → 16019275 · Compress CS3800iAW 7 OM-S (CS3800iAW 7 O-S + AWMi)
            · 8,00 kW
      048 → 16019892 · Compress CS3800iAW 10 OM-T (CS3800iAW O-T + AWMi)
            · 10,00 kW
      049 → 16019894 · Compress CS3800iAW 13 OM-T (CS3800iAW 13 O-T +
            AWMi) · 12,50 kW
      050 → 16019269 · Compress CS3800iAW 4 OE-S (CS3800iAW 4 O-S + AWEi)
            · 4,00 kW
      051 → 16019271 · Compress CS3800iAW 6 OE-S (CS3800iAW 6 O-S + AWEi)
            · 6,00 kW
      052 → 16019272 · Compress CS3800iAW 7 OE-S (CS3800iAW 7 O-S + AWEi)
            · 8,00 kW
      053 → 16019891 · Compress CS3800iAW 10 OE-T (CS3800iAW 10 O-T +
            AWEi) · 10,00 kW
      054 → 16019893 · Compress CS3800iAW 13 OE-T (CS3800iAW 13 O-T +
            AWEi) · 12,50 kW
      Klasse 15 + AWMB (055) → 16019200 · Compress CS8800iAW 15 OMBD-T (B)
            (CS8800iAW 15 O-T (B) + AWMBi D) · 15,00 kW
      Klasse 15 + AWE (056) → 16019199 · Compress CS8800iAW 15 OED-T (B)
            (CS8800iAW 15 O-T (B) + AWEi D) · 15,00 kW
      OFFENER PRÜFPUNKT: Die 8800er-Einträge tragen den Zusatz „(B)" –
      klären, ob die weiße Außeneinheit (Pos. 030) eine eigene
      Anlagennummer hat; bis dahin gelten die obigen Nummern für beide
      Farben, im Datenblatt mit Prüfhinweis.
      Vorrats-Stammdaten ohne Konfigurator-Anbindung (für später, aus den
      gelieferten Screenshots): CS5800-Serie und alpha innotec Hybrox
      (u. a. Hybrox 21 → 16017387 · ait-deutschland GmbH · 21,00 kW).
- [x] Erfassungsbogen WP – vier neue Fragen (Platzierung bei den
      Anlagen-/Altanlagen-Fragen):
      · „Vorhandene Heizflächen" (nur Fußbodenheizung | Heizkörper |
        Heizkörper und Fußbodenheizung) → Vorlauftemperatur 35 °C nur
        bei „nur Fußbodenheizung", sonst 55 °C
      · „Nennleistung der bestehenden Heizung in kW" (Zahl)
      · „Inbetriebnahmejahr der bestehenden Heizung" (Jahr, Zahl) –
        die Klimabonus-Ableitung nutzt ab jetzt dieses Jahr (Gas ≥ 20
        Jahre bzw. Öl/Kohle/Nachtspeicher gemäß bestehender Regel);
        die bisherige Altersfrage entfällt bzw. wird daraus abgeleitet;
        Bestandserfassungen behalten ihre Werte, im Datenblatt
        erscheint sonst „Jahr fehlt – bitte nachfragen"
      · „Contracting-Modell?" (Ja | Nein, Vorbelegung Nein)
- [x] Parametrierung „BzA-Ersteller": Firmenblock fest (Friondo GmbH,
      Arnold-Overbeck-Str. 63-65, 47139 Duisburg, Handwerkskammer-
      Betriebsnummer 1862718); Ersteller-Person wählbar aus den
      ID-Benutzern (Name, E-Mail, Telefon), Vorbelegung = angemeldeter
      Benutzer
- [x] migrate.py: neue Erfassungsfelder, Stammdaten, Ersteller-Parameter

## Phase 96 – BzA-Datenblatt (PDF) am Angebot
- [x] Button „BzA-Datenblatt (PDF)" an jedem WP-Tool-Angebot (Editor-Kopf
      und Vorgangsakte, jeder Status); Dateiname
      BzA-Datenblatt-<Angebotsnummer>.pdf; Kopf mit Friondo-Logo,
      Angebotsnummer, Kunde, Erstellungsdatum und deutlichem Vermerk
      „Internes Arbeitsblatt zur Portaleingabe – keine KfW-Unterlage"
- [x] Inhalt exakt in der Reihenfolge und mit den Feldbezeichnungen des
      KfW-Musters:
      1. Daten zum Investitionsobjekt: Straße, Hausnummer, PLZ, Ort,
         Land (= Ausführungsort); Wohneinheiten im Gebäude nach
         Abschluss (= erfasste WE); Anzahl der zu fördernden
         Wohneinheiten (Vorbelegung = WE, im Datenblatt-Dialog
         übersteuerbar); Wohnfläche der zu fördernden WE (falls im
         Bogen erfasst, sonst „–")
      2. Wärmeversorgung vor Sanierung: Art des Wärmeerzeugers (aus
         A01, Portal-Wortlaut), Nennleistung (neue Frage),
         Inbetriebnahme (Jahr, Ausgabe „01.01.<Jahr>" mit Hinweis
         „Jahr aus Erfassung"), Endenergieverbrauch (= A03 kWh/a;
         bei Flächen-Auslegung „–"), Endenergiebedarf „–", Im Zuge
         der Sanierung ausgebaut: Ja (Nein nur, wenn keine Demontage
         im Angebot)
      3. Geplante Wärmeversorgung: Maßnahme „Wärmepumpe"; Contracting
         (neue Frage); Anlagennummer, Hersteller, Gerätebezeichnung,
         Pumpentyp „Luft / Wasser", Nennwärmeleistung – alles aus dem
         Blatt „BAFA-Anlagen" passend zum Paket bzw. zur
         Klasse-15-Kombination des Angebots; Vorlauftemperatur (35/55
         aus Heizflächen-Frage); Wärmequelle „Luft"; Anzahl geplanter
         Anlagen 1
      4. Geplante Kosten: „Geplante förderfähige Kosten" = Endbetrag
         (brutto, nach Rabatt) des Angebots – wie im Muster ungedeckelt;
         darunter nachrichtlich die Tool-Werte „davon förderfähig
         gemäß Höchstkostengrenze: X €" und „voraussichtlicher
         Zuschuss lt. Angebot: Y €"
      5. Boni: Klimageschwindigkeitsbonus Ja/Nein + Portal-Kategorie
         („Austausch Öl-, Kohle-, Gasetagen- oder Nachtspeicherheizung"
         bzw. „Austausch mindestens 20 Jahre alte Gasheizung" – aus
         A01 und Inbetriebnahmejahr); Einkommensbonus Ja/Nein mit
         Stufe (aus den K-Fragen) und Hinweis „Nachweis:
         Einkommensteuerbescheide"
      6. Ersteller: Person + Firmenblock aus der Parametrierung
- [x] Fehlende Pflichtangaben erscheinen rot als „— fehlt: bitte beim
      Kunden erfragen" (Datenblatt wird trotzdem erzeugt); Solarthermie-
      Übernahme, 8800er-Farb-Prüfpunkt und Alternativ-Positionen ändern
      nichts an Gerät/Nummer-Logik
- [x] Bei externen TAIFUN-Angeboten und Nicht-WP-Sparten ist der Button
      ausgeblendet

## Phase 97 – Abnahme & Rollout
- [x] Tests: Angebot mit Paket 048 → Datenblatt zeigt 16019892 +
      „Compress CS3800iAW 10 OM-T …" + 10,00 kW; Klasse 15 + AWMB →
      16019200; Heizflächen „nur FBH" → 35 °C, „HK+FBH" → 55 °C;
      Klimabonus-Kategorie bei Öl/1985; fehlendes Inbetriebnahmejahr →
      roter Hinweis; Kosten-Zeilen (Endbetrag + nachrichtliche Werte)
      stimmen mit dem Angebot überein; Button fehlt bei PV/TAIFUN
- [x] Regressionen: Kontroll-Szenarien und B1–B4 unverändert grün
- [x] CLAUDE.md: Kopf „(v19)" (Nummer = höchste + 1); Abschnitt einfügen:

      ## Neu in v19 (abgestimmt 29.09.2026)
      - BzA-Datenblatt (KfW „Bestätigung zum Antrag", Programm 458):
        Button am WP-Tool-Angebot erzeugt ein internes Arbeitsblatt in
        exakter Portal-Struktur – Investitionsobjekt, Altanlage
        (inkl. neuer Fragen Nennleistung, Inbetriebnahmejahr,
        Heizflächen → Vorlauftemperatur 35/55, Contracting), geplante
        Wärmepumpe mit BAFA-Anlagennummer/Gerätebezeichnung/
        Nennleistung aus dem neuen Blatt „BAFA-Anlagen", Kosten,
        Boni-Kategorien, Ersteller-Block (Parametrierung, HWK-Nr.
        1862718). Fehlende Angaben werden rot markiert.
      - Blatt „BAFA-Anlagen": Zuordnung aller 3800er-Pakete und der
        8800er-15-kW-Kombinationen zu BAFA-Anlagennummern; Vorrat für
        CS5800 und alpha innotec Hybrox (u. a. Hybrox 21 für die
        geplante Klassenerweiterung). Offener Prüfpunkt: eigene
        Nummer der weißen 8800er-Außeneinheit.
      - Klimabonus wird aus dem Inbetriebnahmejahr der Altheizung
        abgeleitet (präziser als die bisherige Altersfrage).

- [x] docs/nach-dem-update-v19.md: Team-Hinweis an den AD (vier neue
      Pflichtfragen im WP-Bogen und warum), ID-Anleitung Datenblatt →
      Portal; offene Punkte: weiße 8800er-Nummer prüfen, Hybrox-21-
      Erweiterung wartet auf Komponenten/Preise/Klassengrenzen
- [ ] git push → Rollout per update.bat → Checkliste abarbeiten (läuft über PLAN_GESAMT Teil C – wartet auf Freigabe)
