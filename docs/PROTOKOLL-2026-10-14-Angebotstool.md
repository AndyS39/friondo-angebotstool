# PROTOKOLL 14.10.2026 – Angebotstool (Nachträge zu PLAN_V19 und PLAN_LEAD_V5, Vormerkung Nachfassen)

Sitzung: Claudia Castro mit dem Angebotstool-Chat, 14.10.2026.
Empfänger: Andreas (Umsetzung mit Claude Code).
Grundlage: CLAUDE.md v30, PLAN_LEAD_V5 (v31, Phasen 153 bis 160), PLAN_V19
(v32, Phasen 161 bis 165), beide im kombinierten Durchlauf; Design-Entwurf
„Außendienst App“ (claude.ai-Artefakt vom 14.10.2026, zwei Screens „Mein Tag“
und „Wiedervorlage“).

Alle fachlichen Entscheidungen hat Claudia Castro getroffen. Alles, was der
Chat selbst hergeleitet hat, ist mit [ANNAHME] markiert und darf im Sinne des
Projekts entschieden werden.

Hinweis eiserne Regel: Teil A und Teil B sind Nachträge zu den beiden Plänen,
die gerade im selben Durchlauf laufen (erst PLAN_LEAD_V5, dann PLAN_V19, ein
gemeinsamer Commit). Teil C ist eine Vormerkung für einen eigenen Plan NACH dem
v32-Rollout und wird jetzt nicht gebaut.

---

## Teil A: Nachtrag 14.10.2026 zu PLAN_V19 (v32, Angebotstool)

Einfügen als Abschnitt „Nachtrag 14.10.2026 (Claudia Castro)“ unter den
Entscheidungen von PLAN_V19; die Checkboxen unten ergänzen bzw. ersetzen die
genannten Punkte der Phasen 161 bis 163. Die neue Phase 166 wird vor Phase 165
(Tests, Doku) umgesetzt. [ANNAHME: 166 ist die nächste freie Nummer nach 165;
vor dem Bau gegen die Zuordnungstabelle in CLAUDE.md prüfen.]

### A.1 Entscheidungen

- **„Mein Tag“ nur mobil.** Die Kartenansicht nach dem Design-Entwurf gilt
  ausschließlich für die Rolle Außendienst auf dem Smartphone (unter 600 px
  Breite). Auf dem Desktop (alle Rollen, auch Außendienst am PC) bleibt die
  bisherige Tabelle „Leads VOT“; sie bekommt die neue Aufteilung (Gruppen,
  Filter) und die Spaltensortierung aus Teil A.4. Der in PLAN_V19 Phase 161
  vorgesehene Umschalter „Karten | Tabelle“ für Innendienst/Admin **entfällt**.
- **Farben:** Friondo-CI über die Design-v2-Tokens aus v30 (Hell/Dunkel). Die
  Farbwerte des Entwurfs (dunkles Grün, Gelb, Anthrazit) werden **nicht**
  übernommen; der Entwurf gibt nur Aufbau, Abstände und Verhalten vor.
- **Kennzahlen im Kopf entfallen** (Termine offen, Wiedervorlagen, Route
  heute). Der Kopf zeigt nur Wochentag mit Datum, Titel „Mein Tag“ und die
  Initialen des angemeldeten AD.
- **Priorität = Hot-Ampel.** Die Stufen Hoch/Mittel/Niedrig des Entwurfs
  entsprechen heiß/warm/kalt der bestehenden Vorgangs-Ampel; keine neue
  Priorität, keine neue Spalte.
- **Nur „Erfassung starten“** als Aktion je Termin (wie PLAN_V19). Der Haken
  „Erledigt“ aus dem Entwurf entfällt. Ein Termin gilt als erledigt, sobald die
  zugehörige Erfassung abgeschlossen ist.
- **„Heiße Kunden“** ist kein eigener Block mehr, sondern geht im Abschnitt
  „Wiedervorlage“ auf (Chip „Hoch“ = heiß, sortiert zuerst). Die Startseiten-
  Kachel „Bestellung angekündigt“ für Innendienst/Admin aus Phase 163 bleibt.
- **Lead-Board-Layout für alle Tabellen des Angebotstools** (Teil A.4), ohne
  Sammelaktionen.

### A.2 Aufbau „Mein Tag“ mobil (ersetzt die Kartenbeschreibung in Phase 161)

Eine Spalte, von oben nach unten:

1. **Kopf:** „Mittwoch, 14. Oktober“ (Wochentag ausgeschrieben, Tag, Monat
   ausgeschrieben), darunter Titel „Mein Tag“, rechts ein runder Kreis mit den
   Initialen des AD (zwei Buchstaben aus Vor- und Nachname).
2. **Karte „Als Nächstes“:** der nächste noch nicht erledigte Termin des
   Tages. Inhalt: Hinweis „in 25 Min“ (Minuten bis Beginn; nach Beginn „jetzt“;
   kein Hinweis, wenn der nächste Termin erst morgen ist, dann steht die Karte
   nicht da), Uhrzeit „09:30“ groß mit „bis 10:30“ darunter, Kundenname, Zeile
   Sparte und Termintyp (zum Beispiel „Wärmepumpe, Erstberatung“ aus den
   Sparten-Badges und dem Typ in `vot_termine`), Anschrift mit Karten-Link,
   Knopf „Route starten“ (öffnet Google Maps mit der Anschrift als Ziel,
   bestehender Maps-Link aus Phase 161). Telefonnummer als `tel:`-Link bleibt
   wie in Phase 161.
3. **Liste „Heute“** mit Zähler „5 Termine“: je Termin eine Zeile mit Uhrzeit
   links, einem Punkt auf einer senkrechten Linie (erledigt = Punkt in der
   Erfolgsfarbe, nächster Termin = Punkt in der Hinweisfarbe, übrige = leerer
   Punkt), Kundenname, Zeile Sparte/Termintyp, Ort. Erledigte Termine in der
   gedämpften Textfarbe. Hauptaktion rechts: Knopf „Erfassung starten“ (bei
   erledigten Terminen kein Knopf, stattdessen Link zur Erfassung).
4. **Abschnitt „Wiedervorlage“** mit Untertitel „Vorgänge, die auf Rückmeldung
   warten“ und Zähler. Darunter Chips „Alle · Hoch · Mittel · Niedrig“ jeweils
   mit Anzahl (gewählter Chip gefüllt), daneben Segment-Umschalter „Sortieren:
   Priorität · Name · Datum“; der gewählte Eintrag trägt einen Pfeil ↓ bzw. ↑,
   nochmaliges Tippen dreht die Richtung. Darunter höchstens vier Karten je
   Vorgang: Kreis mit Initialen des Kunden, Kundenname, Sparte(n), Badge
   „Hoch“/„Mittel“/„Niedrig“ in den Ampel-Farben, Zeile „Letzter Kontakt
   TT.MM. · seit X Tagen“ (X Tage ab 14 in der Warnfarbe, sonst gedämpft;
   „heute“ bzw. „seit gestern“ statt Zahl). Tippen öffnet die Anruf-Karte aus
   Phase 162/163 (Dialog „Nächster Schritt“, Notizfeld, letzte Aktivitäten).
   Unten Link „Alle N Wiedervorlagen anzeigen“ auf die Seite aus A.3.
   Datenbasis: alle fälligen und überfälligen Angebots-Wiedervorlagen des AD
   (`vorgaenge.wiedervorlage_am` ≤ heute, Verantwortlicher = AD) plus alle
   eigenen Vorgänge mit Hot-Ampel heiß oder Verfolgungsstatus
   `bestellung_angekuendigt` (die bisherigen „Heißen Kunden“). „Letzter
   Kontakt“ = Datum des letzten Eintrags im Notizen-Chat des Vorgangs
   [ANNAHME: Chat-Einträge aller Herkünfte, auch System-Einträge].
5. **Abschnitt „Kommende Tage“:** Termine der nächsten 14 Tage
   [ANNAHME: Zeitraum], gruppiert je Tag mit Datumskachel links (Wochentag
   zweibuchstabig über der Tageszahl), Überschrift „Donnerstag, 15. Oktober“
   und Zähler „2 Termine“; je Termin Uhrzeit, Kundenname, Sparte/Typ · Ort.
6. **Untere feste Leiste** mit vier Einträgen: „Mein Tag“ (diese Seite),
   „Kalender“ (= Meine Termine aus dem Lead-Management), „Wiedervorlage“
   (= Seite A.3), „Kunden“ (= allgemeine Suche aus Phase 164). Aktiver Eintrag
   hervorgehoben; die Leiste berücksichtigt die Safe-Area des Geräts.

Keine Kennzahlen, keine Sammelaktionen, keine Kanban-Pipeline.

### A.3 Seite „Wiedervorlage“ mobil (neu, gehört zu Phase 162)

Route [ANNAHME] `GET /leads/wiedervorlagen` (Rolle Außendienst, mobil).
Aufbau: Zurück-Pfeil „Mein Tag“, Titel „Wiedervorlage“ mit Zähler „9 offen“,
Suchfeld „Nach Name suchen“ (filtert beim Tippen), Chips Alle/Hoch/Mittel/
Niedrig mit Anzahl (Anzahl bezieht sich auf die Suchtreffer), Sortieren wie in
A.2 mit Richtungspfeil, Liste aller Vorgänge ohne Begrenzung auf vier, gleiche
Karte wie in A.2. Leerzustand: „Keine Vorgänge gefunden“ mit Zeile „Filter oder
Suche anpassen.“ Untere Leiste wie A.2 mit aktivem „Wiedervorlage“.
Für Innendienst/Admin entfällt diese Seite; sie nutzen die Angebotsliste mit
dem Filter Verfolgungsstatus (Phase 163).

### A.4 Neue Phase 166: Lead-Board-Layout für alle Tabellen des Angebotstools

Ziel: Die Tabellen des Angebotstools bekommen dieselbe Bedienung wie die
Lead-Boards (v23/v25): Sticky-Filterleiste, Spalten je Nutzer, Sortierung per
Spaltenkopf. Keine Sammelaktionen (Entscheidung Claudia Castro 14.10.2026);
Löschen, Archivieren, Zuweisen bleiben Einzelaktionen wie heute.

Betroffene Tabellen (Board-Keys in `boards_spalten` [ANNAHME: Schreibweise]):
`leads_vot` (Leads VOT Desktop), `erfassungen`, `angebote` (Angebotsliste),
`meine_angebote` (Außendienst), `taifun_warteschlange`, `kunden`.

- [ ] **Gemeinsame Bausteine wiederverwenden** [ANNAHME: Vorgabe an die
      Umsetzung, damit nichts doppelt entsteht]: Makro `spalten_kopf` aus
      `_tabelle.html`, Skript `lm_boards.js` (Sortieren, Umbenennen, Drag &
      Drop, Spaltenwähler, Zurücksetzen), Ablage je Nutzer in
      `benutzer_einstellungen` → `boards_spalten` mit den neuen Board-Keys,
      Funktionen `lead_boards.spalten_fuer / sortierung_fuer /
      spalten_speichern / zeilen_sortieren` um die neuen Boards erweitern
      (Spaltenkataloge je Board als Konstanten, Standard-Spaltensatz =
      heutige Spaltenfolge der jeweiligen Tabelle). CSS: die Klassen
      `.lm-filterblock` / `.lm-tabellen` aus `lead_v2.css` auch außerhalb des
      Lead-Moduls nutzbar machen (Design-v2-Tokens, Hell/Dunkel).
- [ ] **Sticky-Filterleiste** je Tabelle unter der Kopfzeile: die heutigen
      Filter als Chip-Auswahlfelder (Leads VOT: Termin, Vertriebler, Status,
      Priorität = Hot-Ampel; Erfassungen: Status, Sparte, Vertriebler, Archiv;
      Angebotsliste: Status, Verfolgungsstatus (Phase 163), Sparte, Profil/
      Kanal, Vertriebler, Archiv; Meine Angebote: Status, Sparte; Warteschlange:
      Sparte, Status; Kunden: Kanal, Objektart), Suchfeld, Spaltenwähler
      „Spalten“. Tabelle scrollt waagerecht und senkrecht im eigenen Container,
      Tabellenkopf bleibt sichtbar.
- [ ] **Leads VOT Desktop mit Gruppen:** Zeilen gruppiert in „Heute“ und je
      einen Block pro Folgetag („Donnerstag, 15. Oktober · 2 Termine“),
      Gruppenköpfe auf- und zuklappbar [ANNAHME], Sortierung innerhalb der
      Gruppe nach Uhrzeit; Spaltensortierung (nächster Punkt) sortiert innerhalb
      der Gruppen.
- [ ] **Sortierung per Klick auf den Spaltennamen** in allen sechs Tabellen:
      erster Klick aufsteigend, zweiter Klick absteigend, Pfeil im Kopf, leere
      Werte ans Ende, Wahl je Nutzer und Tabelle gemerkt.
- [ ] **Spalten je Nutzer:** ein-/ausblenden, umbenennen (Stift, leer =
      Standard), Reihenfolge per Drag & Drop am Kopf, „Zurücksetzen“. Feste
      erste Spalte je Tabelle: Kundenname (Leads VOT, Erfassungen,
      Angebotsliste, Meine Angebote, Kunden) bzw. Erfassung (Warteschlange).
- [ ] **Rollenregel (fest, keine Rückfrage):** EK, Deckungsbeitrag, DB-Ampel,
      Rabatt-Interna und Summenzeilen mit DB stehen für die Rolle Außendienst in
      keinem Spaltenkatalog, auch nicht ausgeblendet; der Katalog wird
      serverseitig nach Rolle gebaut, Spalten-Keys aus einem gespeicherten
      Satz werden gegen den Katalog der Rolle gefiltert.
- [ ] **Summenzeile der Angebotsliste** (v6) bleibt und folgt der gefilterten
      und sortierten Liste.
- [ ] Tests `tests/test_v32_tabellen.py`: Kontrollwerte: (1) Klick auf
      „Endbetrag“ in der Angebotsliste → aufsteigend, zweiter Klick absteigend,
      nach Neuladen gemerkt; (2) AD ruft `GET /lead-management/boards/spalten?
      board=meine_angebote` → Katalog ohne `ek`, `db`, `db_ampel`; gespeicherter
      Satz mit `db` wird beim Lesen verworfen; (3) Leads VOT Desktop am
      14.10.2026 mit Terminen am 14., 15. und 19.10. → drei Gruppen „Heute“,
      „Donnerstag, 15. Oktober“, „Montag, 19. Oktober“; (4) Spalte umbenennen
      „Vertriebler“ → „AD“ nur für diesen Nutzer sichtbar; (5) Zurücksetzen
      stellt die heutige Spaltenfolge her; (6) Voll-Crawl aller sechs Tabellen
      je Rolle hell/dunkel ohne Fehler.

### A.5 Anpassungen an Phase 161 bis 165 (Checkboxen zum Ersetzen/Ergänzen)

- [ ] Phase 161: Kartenansicht nur bei Rolle Außendienst **und** Breite unter
      600 px (CSS-Media-Query plus serverseitig derselbe Datenbestand); ab
      600 px und für alle anderen Rollen die Tabelle aus A.4. Umschalter
      „Karten | Tabelle“ und `docs/design-v32/leads-vot-vorher.png` als
      Vergleich der ID-Ansicht entfallen; Screenshots „Mein Tag“ mobil bei
      390 px hell/dunkel nach `docs/design-v32/`.
- [ ] Phase 161: Kopf ohne Kennzahlen; Karte „Als Nächstes“, Liste „Heute“
      mit Zeitstrahl, „Kommende Tage“ und untere Leiste nach A.2.
- [ ] Phase 161: Erledigt-Logik: Termin gilt als erledigt, wenn die aus
      „Erfassung starten“ angelegte Erfassung den Status abgeschlossen hat
      (bestehende Verknüpfung Termin ↔ Erfassung aus v31 nutzen; kein eigener
      Haken, kein manuelles Abhaken). Telefontermine ohne Erfassung bleiben
      bis Tagesende offen und erscheinen am Folgetag nicht mehr in „Heute“
      [ANNAHME].
- [ ] Phase 162: Block „Fällig heute“ wird zum Abschnitt „Wiedervorlage“ nach
      A.2 (vier Karten, Chips, Sortierung, Link auf A.3); Anruf-Karte mit
      Dialog „Nächster Schritt“ öffnet beim Antippen der Karte.
- [ ] Phase 163: Block „Heiße Kunden“ entfällt; heiße Vorgänge und
      `bestellung_angekuendigt` laufen im Abschnitt „Wiedervorlage“ mit Chip
      „Hoch“. Test `test_v32_naechster_schritt.py`: Kontrollwert „Vorgang in
      Heiße Kunden“ ersetzen durch „Vorgang in Wiedervorlage mit Badge Hoch,
      an erster Stelle bei Sortierung Priorität“.
- [ ] Phase 164: Suche zusätzlich als Eintrag „Kunden“ in der unteren Leiste
      (mobil).
- [ ] Phase 165: Tests und Crawl um A.3 und A.4 erweitern; CLAUDE.md
      „Neu in v32“ um Phase 166 und diesen Nachtrag ergänzen; Zuordnungstabelle
      v32 = PLAN_V19 Phasen 161 bis 166.

---

## Teil B: Nachtrag 14.10.2026 zu PLAN_LEAD_V5 (v31, Lead-Management)

Einfügen als Abschnitt „Nachtrag 14.10.2026 (Claudia Castro)“; die
Checkboxen gehören zu Phase 157 (Felder) bzw. 158 (durchgängiger Prozess)
[ANNAHME: Zuordnung; Andreas kann sie auch in eine der Phasen 153 bis 158
einhängen, keine neue Phasennummer nötig].

- [ ] **Kanal-Regel im AD-Profil um „Stadtwerke Düsseldorf“ ergänzen.** Die
      Kanal-Regel des AD-Profils (Terminassistent-Kandidatenfilter, v25)
      bietet den Kanalwert „Stadtwerke Düsseldorf“ (monday-Kanal SWD,
      Angebotsprofil SWD aus v9) als Auswahl, gleichwertig zu den heutigen
      Kanalwerten; Ausschluss/Beschränkung wirkt im Terminassistenten und in
      der Sammelaktion „An Handelsvertreter verschieben“ („übersprungen: Kanal
      Stadtwerke Düsseldorf“) wie bei Enni. Kontrollwert: AD mit Regel „nur
      Stadtwerke Düsseldorf“ erscheint im Terminassistenten nur bei SWD-Leads;
      AD mit Regel „außer Stadtwerke Düsseldorf“ nie bei SWD-Leads.
- [ ] **Infotext zum AD entfällt vollständig:** Feld `Benutzer.infotext` aus
      dem AD-Profil und der Benutzerverwaltung entfernen (Formular, Anzeige),
      im Vertriebler-Block der Terminbestätigung (`{vertriebler_block}`, v29)
      nur noch Bild, Name, Telefon, E-Mail. Datenbankspalte bleibt stehen
      (nur additive Migrationen), wird nicht mehr gelesen; Vorlagen-Vorschau
      und Test der Terminbestätigung anpassen. Kontrollwert: Terminbestätigung
      eines AD mit altem Infotext in der DB enthält den Text nicht mehr.
- [ ] **Sammelaktion „An Handelsvertreter verschieben“: Ziel „Simons
      Gruppe“ statt André Lind.** Die zweite Ziel-Schaltfläche heißt
      „Simons Gruppe“. Der Lead hängt danach an der Gruppe, nicht an einem
      festen Mitglied; Simon verteilt innerhalb seiner Gruppe selbst.
      Umsetzung [ANNAHME, einfachster Weg ohne neue Datenstruktur]:
      `vorgaenge.ad_id` = Simon (Gruppenleiter, erster Eintrag von
      `hv_gruppe_simon`), Kennzeichen im Board/Kartei „Simons Gruppe (noch
      nicht verteilt)“, solange kein Mitglied gewählt wurde; Simon weist über
      das Zuständigen-Dropdown der Kartei (zeigt bei HV-Leads nur die eigene
      Gruppe, PLAN_LEAD_V5 Phase 156) ein Mitglied zu, dann verschwindet das
      Kennzeichen. Aktivität „An Simons Gruppe verschoben“. Alternative, falls
      Andreas sie bevorzugt: neue Spalte `vorgaenge.hv_gruppe` mit `ad_id =
      NULL`; dann müssen HV-Sicht, Karte und Kandidatenfilter die Gruppe
      kennen. Kontrollwert: drei Leads verschieben → Meldung „3 verschoben“,
      alle drei bei Simon mit Kennzeichen; Simon wählt Paolo → Kennzeichen weg,
      `ad_id` = Paolo, Aktivität „Zuständiger: Paolo Di Blasi“.

---

## Teil C: Vormerkung für einen eigenen Plan nach dem v32-Rollout (Angebotsverfolgung / Nachfassen)

Entschieden am 14.10.2026, **noch nicht zu bauen**; wird nach dem Rollout von
v31/v32 als PLAN_V20 (CLAUDE „Neu in v33“, Phasen ab 167 [ANNAHME]) mit
Checkboxen und Kontrollwerten ausformuliert. Grundlage: Sichtung der
Nachfass-Logik von Pipedrive (Deal-Rotting, Aktivitätsprinzip), HubSpot
(Angebotsstatus, Erinnerungen) und Handwerker-Tools.

1. **Inaktivitäts-Kennzeichen** „ohne Kontakt seit X Tagen“ für Vorgänge mit
   Verfolgungsstatus Versendet/Nachgefasst: Schwelle **14 Tage** (Einfamilienhaus)
   und **20 Tage** (Objektart MFH), beide in der Parametrierung änderbar;
   Anzeige in „Mein Tag“/Wiedervorlage (AD) und in der Angebotsliste (ID) als
   Kennzeichen und Filter. „Kontakt“ = letzter Eintrag im Notizen-Chat,
   Anruf-Ergebnis oder Mail am Vorgang. Eine weit in der Zukunft gesetzte
   Wiedervorlage schützt nicht vor dem Kennzeichen.
2. **Telefonversuche zählen:** jedes Ergebnis „Nochmal anrufen“ aus dem
   Dialog „Nächster Schritt“ erhöht einen Zähler je Vorgang; Anzeige im
   Verfolgungs-Chip „Nachgefasst (2)“ und in der Vorgangsakte. Keine Schwelle,
   keine Eskalation, keine Liste beim Innendienst.
3. **Einwand-Chips** beim Ergebnis „Nochmal anrufen“, optional (auch kein
   Chip erlaubt): „Förderung unklar“, „wartet auf Mitbewerber“, „Entscheidung
   in der Familie“, „Finanzierung offen“. Liste pflegbar in der
   Parametrierung wie die Ablehnungsgründe. Der zuletzt gesetzte Chip steht
   beim nächsten Anruf oben auf der Anruf-Karte; Auswertung in der Statistik
   neben den Ablehnungsgründen.
4. **Nachfass-Mail durch den AD:** zwei Vorlagen „Nachfassen 1“ und
   „Nachfassen 2“ im bestehenden Vorlagen-Editor; der AD löst den Versand aus
   der Anruf-Karte selbst aus; Versand **aus dem eigenen Postfach des AD**
   (eigener Outlook-Zugang je AD, nicht über das ID-Postfach); Signatur des AD
   per Upload wie beim Innendienst [ANNAHME]; Mail landet im Mail-Verlauf des
   Vorgangs und als Aktivität im Chat.
   **Voraussetzung (Zulieferung):** der Outlook-Zugang je AD ist bei Andreas
   in Arbeit; ohne ihn bleibt Punkt 4 im Plan als „offen“.

Bewusst verworfen (14.10.2026): Feld „Gültig bis“ am Angebot, Erkennung, ob der
Kunde das Angebot geöffnet hat, automatische Mail-Sequenzen ohne Freigabe,
Kanban-Pipeline auf dem Handy.

---

## Zulieferungen / offen

- Andreas: Phasennummer 166 und die Einhängung von Teil B gegen die
  Zuordnungstabelle prüfen.
- Andreas: Entscheidung zur Umsetzung „Simons Gruppe“ (ad_id = Simon mit
  Kennzeichen oder neue Spalte `hv_gruppe`).
- Andreas: Stand des Outlook-Zugangs je AD (Voraussetzung Teil C, Punkt 4).
- Claudia Castro: Design-Entwurf bleibt als Referenz unter
  https://claude.ai/artifact/LMzyjrovcVvv9NyK9jmMwG (Aufbau und Verhalten,
  nicht die Farben).
- Nach dem Rollout: CLAUDE.md im Projektwissen austauschen, dieses Protokoll
  unter claude/ ablegen.
