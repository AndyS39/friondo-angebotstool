# Umsetzungsplan v5

Voraussetzung: Phasen 0–28 sind umgesetzt. CLAUDE.md (v5) vorher lesen.
Es gilt die neue Steuerdatei `konfigurator_logik_v5.xlsx`.
Entwicklung ausschließlich am Entwicklungs-PC mit Test-Datenbank; Auslieferung am
Ende über git push + update.bat auf dem Server. Jede Datenbank-Änderung wird in
einer gemeinsamen `migrate.py` gesammelt (idempotent: mehrfaches Ausführen ohne
Schaden), die update.bat führt sie automatisch aus.

## Phase 29 – Benutzer, Löschen & Archiv
- [x] Benutzer: E-Mail-Feld ergänzen (Pflicht für Außendienst-Rollen, für CC)
- [x] Benutzer löschen, wenn keine Erfassungen/Angebote/Leads zugeordnet sind;
      sonst nur deaktivieren (aus allen Auswahllisten raus, Historie lesbar)
- [x] Erfassungen löschen (Innendienst/Admin) mit Sicherheitsabfrage; gesperrt,
      wenn ein Angebot verknüpft ist
- [x] Angebote: Entwürfe löschen (mit Sicherheitsabfrage); Status „Versendet"/
      „Angenommen"/„Abgelehnt" → stattdessen „Archivieren"
- [x] Angebotsliste: Standardansicht ohne archivierte, Filter „Archiv";
      Statistik-Kacheln zählen Archiviertes nicht doppelt
- [x] migrate.py: neue Felder (Benutzer-E-Mail, Archiv-Flag)

## Phase 30 – E-Mail-Vorlagen je Außendienstler
- [x] Parametrierung „E-Mail-Vorlagen": Standard-Vorlage (Betreff + Text) und
      optionale Vorlage je Außendienstler; beim Versand zieht das Tool die Vorlage
      des AD des Vorgangs, sonst den Standard
- [x] Platzhalter: {anrede}, {vorname}, {nachname}, {angebotsnummer}, {endbetrag},
      {eigenanteil}, {foerderung}, {gueltig_bis}, {vertriebler}, {absender} –
      mit Platzhalterliste im Editor und Vorschau anhand eines echten Angebots
- [x] Bisherigen festen Mailtext als Standard-Vorlage migrieren
- [x] Rechte: Admin und Innendienst pflegen alle Vorlagen

## Phase 31 – Versand-Automatik & Absender angebot@friondo.de
- [x] Entwurf setzt Absender fest auf angebot@friondo.de („Senden als");
      docs/graph-einrichtung.md um die nötige Berechtigungsvergabe und die
      erweiterten Graph-Berechtigungen (Shared-Mailbox-Zugriff) ergänzen
- [x] CC automatisch = E-Mail des Außendienstlers des Vorgangs (fehlt sie:
      Entwurf ohne CC + gut sichtbarer Hinweis); BCC aus Parametrierung
      (Vorbelegung info@friondo.de)
- [x] Status-Kette: „Versand vorbereiten" → Status „Versand vorbereitet";
      Graph-Abgleich (alle 15 Min) erkennt den tatsächlichen Versand über
      Gesendete Elemente/Konversation → Status automatisch „Versendet"
- [x] Mail-Verlauf auf das Postfach angebot@friondo.de umstellen (Antworten
      laufen dort auf); prüfen, ob Phase 27 (Verlauf, Brief-Symbol, Thread-
      Ansicht) vollständig umgesetzt ist – falls nicht, hier nachziehen
- [x] Test: Versand an eine Testadresse → Absender angebot@, CC/BCC korrekt,
      Status springt nach echtem Senden automatisch um, Antwort erzeugt Symbol

## Phase 32 – monday-Rückspielung
- [x] Mapping in der Parametrierung erweitern: je Quell-Board wählbar –
      Statusänderung als Status-Spaltenwert „Angebot versendet" ODER Verschieben
      in eine Zielgruppe; Deal-Wert-Spalte per Dropdown; Betrag brutto (Standard)
      oder netto
- [x] Trigger: Statuswechsel auf „Versendet" (auch der automatische aus Phase 31)
- [x] Fehler blockieren nie: Warnhinweis am Angebot + „Erneut übertragen"-Button;
      jede Rückspielung mit Zeitstempel am Angebot protokollieren
- [x] Test mit einem Test-Deal in monday (Status und Wert prüfen, dann zurücksetzen)

## Phase 33 – Interesse-Badges & Konfigurator-Typ
- [x] Mehrfach-Feld „Interesse" (WP / PV / KL / WB) an Lead und Kunde;
      monday-Mapping um die Interesse-Spalte erweitern
- [x] Badges in „Leads VOT", Erfassungs- und Angebotsliste + Filter danach
- [x] Unterbau: Feld „Konfigurator-Typ" an Erfassung/Angebot (aktuell immer „WP"),
      damit PV- und Klima-Konfigurator später als eigene Kataloge andocken
- [x] migrate.py erweitern (Interesse, Konfigurator-Typ)

## Phase 34 – Angebots-Editor: Positionen, Preise, Rabatte, bauseits
- [x] Positionen per Drag & Drop umsortieren; Positionsnummern-Feld frei editierbar;
      Button „Neu durchnummerieren"; PDF folgt exakt Reihenfolge und Nummern
- [x] Einzelpreis je Position editierbar (Innendienst/Admin); Kennzeichnung
      „manuell geändert" mit Originalpreis als Tooltip; DB nutzt geänderten Preis
- [x] Positionsrabatt je Position (% oder €); im PDF sichtbar als Rabattangabe
      an der Position ausgewiesen; wirkt auf
      Summen, KfW-Basis und DB
- [x] Checkbox „bauseits" je Position: im Editor markiert, PDF zeigt „bauseits"
      statt E-/G-Preis, Position zählt nicht in Summe/KfW/DB
- [x] migrate.py erweitern (eigene Nummer, Rabatt, bauseits, Originalpreis)

## Phase 35 – Leads-VOT-Filter, Logik v5 & Briefanrede
- [ ] Leads VOT: Filter + Sortierung nach Termin, Vertriebler und Status,
      kombinierbar mit der Suche
- [ ] konfigurator_logik_v5.xlsx einlesen: neue Frage A13 „Leitungslänge zwischen
      Hauseinführung und WP-Inneneinheit (m)" → Pos. 103 × (Eingabe − 5 m,
      nie unter 0; die ersten 5 m stecken in Pos. 006), analog Erdleitungs-Abzug;
      SLS/ÜSS/APZ-Fragen entfallen (E02 = Nein → keine Folgefragen)
- [ ] Regressionstest: Kontroll-Szenarien um A13 ergänzen (Beispiel 8 m →
      Pos. 103 ×3 = 267,00 € netto zusätzlich; Beispiel 4 m → keine Position)
- [ ] Briefanrede im PDF-Vortext dynamisch (Herr/Frau + Nachname, Fallback
      „Sehr geehrte Damen und Herren"); Platzhalter {briefanrede} in Mail-Vorlagen

## Phase 36 – Migration, Abnahme & Rollout
- [ ] migrate.py final prüfen: läuft idempotent gegen eine Kopie der echten DB
- [ ] Regressionstests: Kontroll-Szenarien (KG-Fall, DG-Fall, Rabatt) mit A13-Eingabe gemäß Phase 35
- [ ] docs/nach-dem-update-v5.md erstellen (zusätzlich: Positionsrabatt-/bauseits-Kurzanleitung für den Innendienst): ① M365-Admin vergibt „Senden als"
      für angebot@friondo.de an alle ID-Mitarbeiter ② Graph-Berechtigungen
      erweitern + Admin-Zustimmung erneuern ③ Parametrierung: BCC-Adresse prüfen,
      monday-Rückspiel-Mapping zuweisen, Interesse-Spalte mappen ④ E-Mail-Adressen
      der Benutzer eintragen ⑤ Vorlagentexte je AD hinterlegen ⑥ Testversand
- [ ] git push; danach Rollout am Server über update.bat (führt migrate.py aus)
