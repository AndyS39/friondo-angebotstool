# Umsetzungsplan v3

Voraussetzung: Phasen 0–17 (PLAN.md + PLAN_V2.md) sind umgesetzt. CLAUDE.md (v3)
vorher lesen. Je Phase: Ansatz erläutern → umsetzen → testen → abhaken → committen.

## Phase 18 – UI-Sammelphase & Bugfixes
- [x] Menüpunkt „Konfiguration" umbenennen in „Parametrierung" (alle Stellen;
      alte URL /konfiguration leitet um)
- [x] Friondo-Logo oben links in der App-Navigation (Datei aus Layout - Logo)
- [x] Bugfix: EK-Preis unter „Artikel bearbeiten" änderbar (Innendienst/Admin)
- [x] Benutzerverwaltung: Rolle **Admin** einführen; Admin kann Benutzer anlegen,
      Namen ändern, Rolle setzen, PIN zurücksetzen, deaktivieren (bestehender
      „Admin"-Benutzer automatisch migriert; /benutzer nur noch für Admin)
- [x] Neu-Nummerierung: Angebotspositionen fortlaufend 001, 002, … in Editor und
      PDF; interne Referenz (TAIFUN-Pos./Z-Nr./GUID) gespeichert und im Editor als
      Zusatzinfo sichtbar; bestehende Angebote werden beim Öffnen korrekt angezeigt

## Phase 19 – Startseite
- [x] Startseite: nur Shortcuts „Leads VOT", „Erfassungen", „Angebote"
- [x] Alle übrigen Punkte in Dropdown „Menü" oben rechts (rollenabhängig gefiltert)
- [x] Statistik-Kacheln: Offene Leads (VOT ohne Angebot) · Offene Erfassungen
      (Status Neu/In Bearbeitung) · Versendete Angebote (Status Versendet);
      Zahlen anklickbar → gefilterte Liste (Lead-Modell + /leads-Liste angelegt,
      Befüllung durch den monday-Sync folgt in Phase 22)

## Phase 20 – Logik v3
- [x] konfigurator_logik_v3.xlsx einlesen; Validierung (neue IDs D01–D05,
      Positionen 139/140/141/163 müssen im Artikelstamm existieren)
- [x] Dachzentralen-Block umsetzen: D01–D05 nur bei A04 = DG, Kette lt. Aktionen;
      D05 als Mengenmaske mit zwei Meterfeldern (Pos. 139 / Pos. 140 × Eingabe)
- [x] Bedingungen: A06 Fassadenleitung nur bei OG oder (DG und D01 = Ja);
      A05 Erdleitung bei KG/EG oder (DG und D01 = Nein) – ODER/UND-Klauseln
      generisch im Parser und in der Erfassungs-Sichtbarkeit (auch clientseitig)
- [x] Pos. 163 automatisch bei A04 = DG (Block 5); Pos. 141 bei D03 = Ja (Block 2)
- [x] E04–E06 ohne Artikelwirkung (nur Protokoll); AMPEL-Grund Nr. 15 (D04 = Nein)
- [x] Regressionstest: Kontroll-Szenario (KG-Fall) unverändert – Netto 29.629,37 € /
      Brutto 35.258,95 € / Eigenanteil 15.658,95 € (Detailantworten an die
      artikellosen E-Fragen angepasst, Summen identisch)
- [x] Neuer Testfall DG: A04 = DG, D01 = Nein, D02 = Nein, D03 = Nein, D04 = Ja,
      D05 = 6 m Heizung + 4 m Trinkwasser → Pos. 163 + 139×6 + 140×4 im Angebot;
      Fassadenleitung wird NICHT gefragt, Erdleitung wird gefragt

## Phase 21 – Rabatt
- [x] Angebots-Editor: Rabattfeld (Betrag € oder Prozent, optionale Bezeichnung),
      nur Innendienst/Admin sichtbar und änderbar
- [x] Summenlogik: Netto − Rabatt = Netto nach Rabatt → 19 % USt → Brutto;
      Rabatt ist keine Position; Decimal/Cent
- [x] KfW: förderfähige Kosten = Brutto nach Rabatt; DB-Box zieht Rabatt ab
- [x] PDF: Rabattzeile im Summenblock (mit Bezeichnung, falls angegeben)
- [x] Test: Kontroll-Szenario + 500 € Rabatt → Netto nach Rabatt 29.129,37 € /
      USt 5.534,58 € / Brutto 34.663,95 € / Zuschuss 19.600,00 € (Deckel weiter
      erreicht) / Eigenanteil 15.063,95 €

## Phase 22 – Leads VOT (monday-Lesesync)
- [ ] Parametrierung „monday-Anbindung": Quellenliste (Board + Gruppentitel),
      vorbelegt mit den drei verifizierten Quellen – „Deals" 5080725439 (Blinno
      Working Space, Gruppe „Terminiert" = group_mkzb5f0e), „Deals - Simon"
      5089971526 und „Deals - Rene" 5092657267 (Pool Working Space, Gruppe
      „Terminiert" je Board über den Titel auflösen)
- [ ] Spalten-Mapping je Board per Dropdown (Spalten live von monday laden):
      VOT-Datum, Personen-Spalte „Verantwortlicher", Anrede, Vorname, Nachname,
      Straße, PLZ, Ort, Telefon, E-Mail, Status
- [ ] Sonderregel: Bei „Deals - Rene" ist der Verantwortliche IMMER der Benutzer
      Rene Golaschewski (auch bei leerer Spalte); Deduplizierung, falls derselbe
      Kunde in mehreren Boards auftaucht
- [ ] Zuordnungstabelle monday-Person ↔ Tool-Benutzer (für AD-Filter)
- [ ] Lesesync alle 15 Min + Button „Jetzt aktualisieren"; API-Token aus .env;
      Fehler werden angezeigt, blockieren aber nichts
- [ ] Menüpunkt „Leads VOT": Leads mit VOT-Datum und ohne verknüpftes Angebot,
      chronologisch nach Termin; Spalten: Termin, Kunde, Ort, Vertriebler, Status;
      AD sieht nur eigene, ID/Admin alle
- [ ] Klick → Fragenkatalog mit automatisch angelegtem/abgeglichenem Kunden
      (Duplikatabgleich Name + PLZ); Verknüpfung Lead ↔ Erfassung ↔ Angebot
- [ ] Nach Absenden der Erfassung verschwindet der Lead aus der Liste;
      Statistik-Kachel „Offene Leads" speist sich hieraus

## Phase 23 – E-Signatur
- [ ] Signaturmodul: Seite mit Angebots-PDF-Vorschau + Touch-Signaturfeld (Canvas),
      Name des Unterzeichners, Datum/Uhrzeit
- [ ] Vor-Ort-Modus: aus Angebotsansicht „Signieren" starten (auch auf dem
      AD-Handy über die bestehende Erfassungs-Route erreichbar)
- [ ] Nach Signatur: Signaturbild + Name + Zeitstempel in die Unterschriften-Seite
      des PDFs einbetten; signiertes PDF unter data/angebote/signiert/ ablegen;
      Status „Angenommen"; Signaturprotokoll (Zeit, Benutzer, Gerät/IP) am Angebot
- [ ] Fern-Modus vorbereiten: Token-Link-Route + Gültigkeitsdauer, standardmäßig
      deaktiviert; Aktivierung erst nach Entscheidung öffentlicher Zugang
      (PLAN_V2 Phase 16 Variante B) oder externer Signatur-Anbieter
- [ ] Hinweis in docs/: einfache elektronische Signatur; rechtliche Feinheiten
      bei Bedarf mit Rechtsberatung klären
