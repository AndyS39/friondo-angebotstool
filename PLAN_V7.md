# Umsetzungsplan v7 – Zwei-Wege-Prozess (Tool + TAIFUN)

Voraussetzung: Phasen 0–43 sind umgesetzt, v6 läuft auf dem Server.
CLAUDE.md (v7) vorher lesen, Abschnitt „Neu in v7". Die Logik-Excel bleibt in
v7 unverändert. Je Phase: Ansatz erläutern → umsetzen → testen → abhaken →
committen. Alle Schema-Änderungen in migrate.py (idempotent).

## Phase 44 – Startweiche & Freitext-Erfassung
- [x] Startweiche nach der Kundenwahl in /erfassung: zwei große Buttons
      „Erfassungsbogen starten" und „Freitext-Erfassung"
- [x] Freitext-Weg: großes Pflicht-Textfeld; Absenden setzt Ampel „Individuell"
      mit Grund „vom Außendienst als individuell erfasst" und Status direkt
      „In TAIFUN zu schreiben" (keine Vorprüfung)
- [x] Button „In Freitext wechseln" auf jeder Katalogseite: bereits gegebene
      Antworten bleiben erhalten und erscheinen im Protokoll, Freitextfeld kommt
      dazu, Ergebnis wie Freitext-Weg
- [x] Protokoll (Ansicht + PDF) zeigt Erfassungsart, Freitext und ggf.
      Teilantworten sauber getrennt
- [x] migrate.py: erfassungen.typ (katalog/freitext), erfassungen.freitext

## Phase 45 – Statuskette & TAIFUN-Warteschlange
- [x] v6-Verhalten entfernen: Status „Individuell" archiviert NICHT mehr
      automatisch
- [x] Neue Erfassungs-Statuskette: Katalog-Fälle mit oranger Ampel →
      „Individuell – zu prüfen" mit Buttons „Doch konfigurierbar" (Antworten
      korrigierbar, normaler Weg inkl. „Angebot erzeugen") und „Individuell
      bestätigt" → „In TAIFUN zu schreiben" → nach Phase-46-Dialog
      „Erledigt (extern)" + Archiv
- [x] Erfassungsliste: Tabs/Filter Offen · Individuell – zu prüfen ·
      In TAIFUN zu schreiben · Erledigt · Archiv; Protokoll-PDF-Button
      prominent in der Warteschlange
- [x] Startseiten-Kachel „Individuell offen: n" (zu prüfen + zu schreiben),
      klickbar auf die gefilterte Liste
- [x] migrate.py: BESTANDSDATEN REAKTIVIEREN – alle bisher als „Individuell"
      markierten (auto-archivierten) Erfassungen auf „In TAIFUN zu schreiben"
      setzen und entarchivieren, damit sie als Arbeitsliste sichtbar werden;
      im Änderungsprotokoll vermerken

## Phase 46 – Externe Angebotseinträge (TAIFUN)
- [x] Dialog „Extern erledigt" an Erfassungen der Warteschlange:
      TAIFUN-Angebotsnummer (optional, später nachtragbar → Badge „Nummer
      fehlt" am Eintrag), Endbetrag brutto (Pflicht), Datum (Pflicht,
      Vorbelegung heute)
- [x] Externer Angebotseintrag in der Angebotsliste: Badge „TAIFUN", Status
      „Versendet (extern)" mit Zeitstempel = Dialog-Datum; kein PDF, kein
      Editor, kein Mail-Versand; Detailseite mit Verfolgungs-Block (Ampel,
      Wiedervorlage, Notizen) und Verweis auf Erfassung + Protokoll;
      Status weiter pflegbar auf Angenommen/Abgelehnt (Abschlussquote)
- [x] monday-Rückspielung beim Anlegen des Eintrags (Deal-Status/Gruppe +
      Deal-Wert = Endbetrag), gleiche Fehler-/Wiederholen-Mechanik und
      Protokollierung wie bei Tool-Angeboten
- [x] Statistik: alle Kennzahlen getrennt nach Tool / TAIFUN / gesamt
      (Anzahl, Auftragswert, Abschlussquote); DB nur für Tool-Angebote,
      mit Fußnote
- [x] Summenzeile der Angebotsliste berücksichtigt externe Einträge
      (Endbetrag ja, DB nein)
- [x] migrate.py: Felder/Tabelle für externe Einträge; Abnahmeskript um
      v7-Block erweitern (Weiche, Statuskette, Reaktivierung, externer
      Eintrag inkl. monday-Rückspielung im Trockenlauf)
- [x] docs/nach-dem-update-v7.md: Team-Hinweis, dass alte Individuell-Fälle
      bewusst als Arbeitsliste wieder auftauchen; Kurzanleitung Zwei-Wege-
      Prozess für den Innendienst
