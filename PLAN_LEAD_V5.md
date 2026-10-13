# Umsetzungsplan Lead-Management V5: Feedback-Runde 3 (Mehrobjekt-Kunden, Großkunde, Dashboard-Kacheln, Sammelaktionen, Kundenkartei, Vorlagen, Zuständigen-Auswahl; Nachtrag 13.10.: Felder/Status, Kalender, Mails, Krankheit, durchgängiger Prozess)

**Fassung 13.10.2026 für den kombinierten Durchlauf v31 → v32** (Original:
Chat Lead-Management, Claudia Castro, 12./13.10.2026; Einfügung durch den
Angebotstool-Chat, Andreas, 13.10.2026 – fachliche Entscheidungen unverändert,
geändert sind Vorspann, der Abschnitt „Einfügung in den Durchlauf“ und die mit
**(v30)** bzw. **(AT-Chat)** markierten Zusätze).

Voraussetzung und Stand 13.10.2026: v29 ist ausgerollt; **v30 (PLAN_V18,
Phasen 145 bis 152) ist fertig gebaut und committet** (4527c20 „v30: Design v2
…“ plus Nachträge 3cd0299 / 9f8b1cd / 1f0b764, Rollout im Wartungsfenster
13.10.). Gebaut wird auf dem **committeten v30-Stand** der Git-Arbeitskopie –
ob v30 schon auf dem Server liegt, ist für den Bau unerheblich. **Dieser Plan
wird im selben Durchlauf wie PLAN_V19 (v32, Phasen 161 bis 165) umgesetzt:
erst dieser Plan, dann PLAN_V19, EIN gemeinsamer Commit am Ende** (Entscheidung
Andreas 13.10.2026; die Vorbedingung „v30 auf dem Server“ entfällt damit).
CLAUDE.md und `leadmanagement_logik_v1.xlsx` sind Live-Master im
Projektordner `C:\Users\a.scheelen\Tools\Angebotstool` (Git-Arbeitskopie).
ALLE PHASEN DIESES PLANS IN EINEM DURCHLAUF UMSETZEN (Reihenfolge
einhalten, jede Checkbox nach Umsetzung und Test abhaken, am Ende
Gesamtübersicht mit Testergebnissen und offenen Punkten, fachliche
Rückfragen gebündelt). **Ein gemeinsamer Commit für v31 + v32 am Ende des
Durchlaufs** (Arbeitsweise seit v28/v29), migrate.py idempotent, **nur additive
Migrationen** (v30-Code muss auf der v32-Datenbank weiterlaufen, Rückweg
`rollback.bat --nur-code`). **Kein git push vor Freigabe.**

CLAUDE-Abschnitt: **„Neu in v31“** – bestätigt 13.10.2026 (v30 = PLAN_V18
steht in der Zuordnungstabelle). Phasen **153 bis 160** – bestätigt (145 bis
152 = PLAN_V18). Vor dem Bau trotzdem einmal gegen die Tabelle prüfen; bei
Abweichung die nächsten freien Nummern nehmen und durchgängig ersetzen. Die v27-Regeln
gelten (`def`-Routen, keine offene Datenbanksitzung während Netz-I/O,
Scheduler-Rahmen, Wächter-Test `tests/test_v27_sitzungen.py` grün,
`docs/betrieb.md` fortschreiben, wenn ein Punkt den Betrieb berührt).
Design v2 (v30, Hell/Dunkel-Tokens) ist für alle neuen Oberflächenteile
verbindlich.

Geltungsbereich: Modul Lead-Management (Router `app/routers/lm_*.py`,
`app/lead_*.py`, `app/static/lead_v2.css`, `lm_boards.js`, Templates unter
`templates/lead_management/`), der Vorlagen-Editor im Modul, die
Benutzerverwaltung (nur neue Kennzeichen Leadmanager/Großkunde), die
Terminierung/Terminbestätigung sowie die Verknüpfung Objekt ↔ Erfassung ↔
Angebot (nur Zuordnung, keine Änderung an Konfigurator, Angebots-PDF oder
Angebotslogik). monday-Sync und monday-Rückspielung bleiben unberührt.
**Der Demo-Modus endet mit diesem Plan** (Phase 159: `lead_freigabe_modus
= alle`, Testphase mit gesperrter Buchung und gesperrtem Mailversand).
Bestehende Tests
(`tests/test_lead_v2_*.py`, `test_lead_v3.py`, `test_lead_v4.py`) müssen
nach Umbau grün sein oder bewusst angepasst werden (Begründung je Test in
der Gesamtübersicht).

Dieser Plan wurde fachlich gegen CLAUDE.md v29 geschrieben, ohne Blick in
den Code von v30; die Einfügung unten gleicht ihn mit dem **tatsächlichen
v30-Code** ab. Checkboxen beschreiben das Soll, nicht Zeilennummern.

## Einfügung in den Durchlauf v31/v32 (Angebotstool-Chat, 13.10.2026)

Diese Regeln gelten für jede Checkbox dieses Plans; sie ergänzen Claudias
Entscheidungen, ändern sie aber nicht (eine Ausnahme ist markiert: Demo-Leads).

- **v30-Fakten, die neue Oberflächenteile nutzen müssen:** semantische Tokens
  (`--flaeche`, `--flaeche-karte`, `--linie`, `--text`, `--text-dezent`,
  `--akzent`, Status-Paare, Modul-Tokens) in beiden Modi – kein neuer Hex-Wert
  außerhalb der Token-Blöcke, der Token-Wächter `tests/test_v30_design.py`
  muss grün bleiben; die Zurück-Leiste `.zurueck-leiste` kommt aus `base.html`
  (Seiten setzen bei Bedarf `{% set zurueck_aus = true %}`, Standard-Rücksprung
  über `data-zurueck-standard`); neue Dialoge und Knöpfe mit `tojson` in
  doppelt gequoteten on*-Attributen **nur mit `| forceescape`** (v30-Nachtrag
  24; `tests/test_v30_nachtrag.py` prüft das); die Portal-Begrüßung „Guten
  Morgen, <Vorname>“ existiert seit v30, die Dashboard-Begrüßung (v29) bleibt
  getrennt.
- **v27-Regeln:** jede schreibende Route, die mehrere Zeilen anfasst
  (Archivieren, Duplizieren, Objekt-Sync, Terminierung mehrerer Objekte,
  Status aus der Kartei), läuft über das `_speichern`-Muster (Rollback + eine
  Wiederholung bei „database is locked“); kein Netz-I/O mit offener Sitzung
  (Graph, Routing, Geocoding je Objektadresse); keine neuen Hintergrundläufe
  außer über `scheduler.registrieren`; Inventartabelle in `docs/betrieb.md`
  ergänzen (Krankheits-Prüfung, Objekt-Geocoding). Wächter-Test
  `tests/test_v27_sitzungen.py` grün.
- **Objektadresse als Ausführungsort durchreichen (Phase 153, AT-Chat):** Das
  Angebotstool, die Projektierung und die Mails kennen bisher nur die
  Kundenadresse als Ausführungsort (`anschriften.py`, Angebots-PDF-Zeile
  „Ausführungsort“, Lieferschein, BzA-Datenblatt Abschnitt 1, Heizreport
  `projektdaten_v2`, Projektakte/Steckbrief, Sub-Mails, Montage-Backend,
  Terminvorschläge der Projektierung, Geocoding/Karte). Mit mehreren Objekten
  muss ein Angebot/Projekt für Objekt 2 überall die **Objektadresse** tragen:
  eine Funktion `objekte.ausfuehrungsort(objekt_id | angebot | erfassung |
  gewerk)` liefert Straße/PLZ/Ort des Objekts (Hauptobjekt = heutige
  Kundenadresse, damit sich für Ein-Objekt-Vorgänge nichts ändert); alle
  genannten Stellen lesen den Ausführungsort nur noch darüber. Claude Code
  listet in der Gesamtübersicht jede umgestellte Stelle. Die Anschriften-Logik
  v20 (Rechnungs-/Lieferanschrift) bleibt; die Rechnungsadresse eines
  MFH-Objekts (Phase 157) landet als Kunden-Standard `kunden.rechnung_*`, wenn
  das Objekt das Hauptobjekt ist, sonst als Objektfeld [ANNAHME].
- **Archivieren (Phase 154) ist eine Lead-Sicht:** `vorgaenge.archiviert_am`
  blendet den Vorgang aus Lead-Boards, Anrufliste, Kanban, Karte, Dashboard
  und Lead-Kennzahlen aus. Angebotsliste, Erfassungsliste, Vorgangsakte,
  Statistik des Angebotstools und Projektierung zeigen archivierte Vorgänge
  **unverändert** (Vorgangsakte mit Banner „Im Lead-Management archiviert am …“
  und Link „Wiederherstellen“); die monday-Rückspielung läuft weiter [ANNAHME].
- **Neue Sparten MS/WA/DMS (Phase 157):** die `SPARTEN`-Liste ist gemeinsam
  mit Angebotstool und Projektierung; Erfassungsstart = Freitext wie WB/GW,
  externer TAIFUN-Eintrag mit Sparten-Badge, Statistik je Sparte; die
  **E-Mail-Vorlage je Sparte** (v27-Nachtrag 2: Reiter Standard · WP · PV ·
  KL · WB) bekommt keine neuen Reiter – MS/WA/DMS nutzen die Standard-Vorlage
  [ANNAHME]; Anhangsregeln „wenn Sparte = …“ bleiben; die Projektierung legt
  für diese Sparten Gewerke wie für WB an (Freitext-Auftrag, keine Pakete)
  [ANNAHME]; DB-Ampel-Schwellen je Sparte fallen auf den WP-Wert zurück.
- **Durchgängiger Prozess (Phase 158) – v28-Stand beachten:** Seit v28 ist der
  Notizen-Chat des Vorgangs (`app/notizen.py`, Makro `notizen_chat`) die
  einzige Notizspur von Lead bis Montage und wird bereits in Kundenkartei,
  Vorgangsakte, Projektakte und Montage-Backend angezeigt; die alten
  Projektakten-Kommentare sind dort hinein migriert. Phase 158 baut daher
  **nur die Lücke**: Lead-Aktivitäten (Anrufe, Mails, Termine, Statuswechsel)
  erscheinen über `vorgang_verlauf(vorgang_id)` zusätzlich in der Vorgangsakte
  (Filter „nur Notizen“ / „alles“) und als Lesefunktion für die Projektakte
  [OFFEN 4]; keine zweite Notizspur, keine Kopien.
- **Demo-Ende (Phase 159) – Demo-Leads löschen statt entflaggen (AT-Chat):**
  Die mit dem Demo-Daten-Generator erzeugten Leads (`demo = 1`, erfundene
  Kunden wie „Test Test“) dürfen nach der Freischaltung **nicht** in Leads
  VOT, Kundenliste, Angebotstool-Statistik oder monday-Rückspielung auftauchen.
  Statt Claudias [ANNAHME] „behalten und entflaggen“: die v12-Abfrage beim
  ersten Aufruf bietet „Demo-Leads löschen“ (Generator-Leads samt Kunde,
  Terminen, Aktivitäten, Warteschlange – nur solche ohne Erfassung, Angebot
  oder Projekt) und „behalten (Kennzeichen bleibt, weiter ausgeblendet)“;
  Vorbelegung **löschen**, Protokoll ins Lösch-Protokoll. Andreas entscheidet
  beim ersten Aufruf. Echte Leads tragen kein `demo` und sind nicht betroffen.
- **Mail-Sperre (Phase 159) gilt nur für Lead-Vorlagen:** `mail_versand_aktiv =
  aus` sperrt die Lead-Mail-Warteschlange (`lead_mail`, Absender termin@).
  Nicht betroffen: Angebotsversand aus angebot@ (Angebotstool), Projekt-Mails
  (projektierung@), Sofort-Benachrichtigungen (`mail_ausgang`, v27), BzA-Mail
  (v17). Der Lauf `lead-mail-abruf` (Bounces/Antworten) und der Parser laufen
  weiter; die `fehler`-Betriebsglocke (v29) entsteht bei `gesperrt` nicht.
- **Freischaltung für alle Rollen (Phase 159) und Lasttest:** Mit
  `lead_freigabe_modus = alle` nutzen deutlich mehr Innendienst- und
  Leadmanagement-Nutzer das Modul echt (das Lastmodell v27 rechnete mit 6 LM).
  Deshalb am Ende des Durchlaufs (nach v32) **Lasttest Profil `normal`** mit
  angepasstem Modell (12 LM/ID auf Hauptboard, Kartei, Terminvorschläge) gegen
  die Zielwerte aus `docs/lasttest-v27.md`; Ergebnis in die Gesamtübersicht.
- **Rollout-Vorbereitung einmal für v31 + v32** am Ende des Durchlaufs; die
  Checkbox in Phase 160 gilt als erfüllt, wenn der gemeinsame Lauf grün ist.
  Rückweg-Probe: v30-Code gegen die v32-Datenbank.

## Entscheidungen (Chat Lead-Management, 12.10.2026, Claudia Castro)

- **Kunden mit mehreren Objekten = Objektliste am Vorgang.** Ein Lead/
  Vorgang je Kunde; der Vorgang trägt ein oder mehrere **Objekte** (Adresse,
  Objektart, Parteien bei MFH, Interessen). Kontaktversuche, Wiedervorlagen,
  Phase und Zuständige bleiben am Vorgang. Je Objekt: eigener Vor-Ort-
  Termin, eigene Erfassung, eigenes Angebot. Bestehende Vorgänge haben
  genau ein Objekt (Ausführungsort); nichts ändert sich für sie.
- **Terminbestätigung bei mehreren Objekten:** Standard ist **eine** Mail
  mit allen Objekten und Terminen (neue Vorlage
  `terminbestaetigung_objekte` mit {objektliste}). Liegen die Termine an
  verschiedenen Tagen, gibt es die Option, **je Objekt eine eigene
  Bestätigung mit Objektadresse** zu senden (Vertriebler-Vorlage mit
  {objektadresse}); Vorbelegung: verschiedene Tage → je Objekt, gleicher Tag
  → eine Mail; manuell umschaltbar.
- **Großkunde:** Kunden bzw. Leads lassen sich als **Großkunde**
  kennzeichnen (Häkchen am Kunden, Badge „Großkunde“ in Boards, Kartei,
  Kanban, HV-Ansicht; Filter-Chip; Spalte im Spaltenkatalog). Keine weitere
  Automatik [ANNAHME: Kennzeichen und Sichtbarkeit, keine Sonderregeln bei
  Zuweisung oder Terminierung].
- **Dashboard-Kacheln verschiebbar:** Stift oben rechts auf „Mein
  Dashboard“ schaltet den Bearbeitungsmodus ein (Kacheln per Drag & Drop
  umsortieren), Haken an derselben Stelle beendet ihn und speichert je
  Nutzer. Formatierung bleibt unverändert, Kacheln rasten in das Raster
  ein.
- **Hauptboard:** horizontales Scrollen auf jeder Seitenhöhe möglich
  (Scrollleiste am unteren Bildschirmrand fixiert, zusätzlich Shift +
  Mausrad); Sammelaktionen **„Archivieren“** (kein endgültiges Löschen) und
  **„Duplizieren“** für markierte Leads.
- **Kundenkartei:** Notizfeld und To-Dos rücken nach oben, To-Dos deutlich
  schmaler. Reiter in der Mitte nur noch **Anruf · E-Mail · Timeline**
  (Reiter „Termin“ entfällt und geht im Block „Termine“ auf, Anrufnotizen
  und Termin sind damit getrennt). Block „Termine“ (aktiver Termin,
  Historie, Vorschläge, Vorab-Gespräch, Absage/Umbuchung) steht unter den
  Reitern, direkt darunter „To-Dos“, danach Angebote · Erfassungen ·
  Projekt · Anhänge.
- **E-Mail-Vorlagen:** Sparten-Kürzel werden in allen Kundenmails
  ausgeschrieben (WP → „Wärmepumpe“, PV → „Photovoltaik“, KL →
  „Klimaanlage“, WB → „Wallbox“, GW → „Gewerbe“), z. B. „Interesse an einer
  Wärmepumpe“. Vorlage **„nicht erreicht“ entfällt**; die Kaskade schickt
  nach Versuch 2 und 4 **keine** Mail mehr, nur noch „Disqualifiziert, nicht
  erreicht“ nach dem letzten Versuch.
- **Innendienst-Auswahl** (Leadmanager/Innendienst-Dropdown in Kartei,
  Boards, Sammelaktion, Filter) zeigt nur noch die Benutzer mit neuem
  Kennzeichen **„Leadmanager“**; Startwerte (korrigierte Schreibweisen
  12.10.2026): Andreas Scheelen, Claudia Castro, Paula Köhler, Nikolaos
  Goritsas, Ioannis Simeonidis, Dimi Chatzis. Alle anderen Benutzer, auch
  wenn sie heute im Dropdown stehen (ausdrücklich Kyriakos S. und Gabriel
  S.), sind nicht mehr wählbar.
- **Außendienst-Auswahl** zeigt nur angestellte Außendienstler, keine
  Handelsvertreter (sie terminieren selbst). Liegt der Lead bereits bei
  einem Handelsvertreter, zeigt das Dropdown stattdessen seine Gruppe: bei
  René nur René; bei Simons Gruppe Simon, Paolo, André, Ralf, Hartmut. Die
  Übergabe an eine Gruppe läuft weiter über die Sammelaktion „An
  Handelsvertreter verschieben“ (v29).
- **Nachtrag 13.10.2026 (Claudia Castro):**
  - Neue Interessen **Mieterstrom (MS)**, **Wasser (WA)** und
    **Denkmalschutz (DMS)** als Häkchen neben WP/PV/KL/WB/GW (Badges,
    Filter, Statistik, Langnamen „Mieterstrom“, „Wasser“, „Denkmalschutz“;
    keine eigene Erfassung, Freitext-Weg wie WB/GW).
  - **Außendienst wird Pflichtfeld** (rote Umrandung und Hinweis wie die
    übrigen Pflichtfelder, zählt im Pflichtfeld-Zähler und sperrt den
    Button „Terminierung“); Layoutfehler „Eingangsdatum ragt ins Feld“ wird
    behoben.
  - Status **„unqualifiziert“ heißt überall „disqualifiziert“** (nur Label
    und Anzeige; interner Phasen-Key bleibt) und ist **in der Kundenkartei
    direkt änderbar** (Status-Auswahl in der Statuskette bzw. Dropdown, mit
    Pflichtgrund).
  - Bei **Mehrfamilienhaus** fragt die Kartei „Rechnungsadresse = Objekt-
    adresse?“ (Ja/Nein); bei Nein erscheinen die Rechnungsadressfelder;
    Anzahl der Parteien bleibt Pflicht.
  - **Terminassistent nur Montag bis Freitag:** Samstag verschwindet aus
    Arbeitszeiten, Vorschlägen und Kalenderansicht.
  - **Rückruf-Uhrzeit** nur in 5-Minuten-Schritten.
  - **Dashboard „Fällig heute“:** der Button „Erledigt“ überlappt das Feld
    und bleibt nach dem Klick sichtbar (Fehlerbehebung).
  - **Board Kontaktiert:** Kunde über beliebige letzte Ziffern der
    Telefonnummer auffindbar (Endziffern-Suche).
  - Button **„Falsche Telefonnummer“** sendet eine E-Mail mit Vorlage und
    Kundennamen an den Kunden (Vorlage `falsche_telefonnummer`, Textentwurf
    in Phase 158, [ANNAHME] bis Claudia den Text freigibt).
  - **Terminvorlage aus der Kundenkartei verschickbar:** Schnellaktion
    „E-Mail senden“ mit Vorlagenwahl, Platzhalter automatisch befüllt,
    Vorschau, Versand über termin@.
  - **Krankheit eines Vertrieblers** notierbar; seine Termine erscheinen in
    der Innendienst-Wiedervorlage „Fällig heute“ mit Hinweis „Krankheit“.
  - **Demo-Modus wird gestrichen (13.10.2026):** `lead_freigabe_modus =
  alle` für alle Rollen; Terminassistent liefert echte, konkrete
  Terminvorschläge zum Testen, aber **es wird noch nicht terminiert**
  (Buchen gesperrt) und **keine E-Mail aus den Vorlagen verschickt** (auch
  nicht ins Testpostfach). Zwei Schalter `terminierung_aktiv` und
  `mail_versand_aktiv`, beide Standard aus (Phase 159).
- **Durchgängiger Prozess:** Lead-Management, Angebotstool und
    Projektierung sind ein Prozess; alle Infos, Notizen und Kommentare zu
    einem Vorgang sind in allen drei Modulen durchgehend sichtbar (Phase
    158, nur Lead-Seite plus Anzeige; Projektierungs-Seite wird dem
    Projektierungs-Strang gemeldet).
- Offen geblieben (keine Umsetzung in diesem Plan): Einbindung von Add-ons
  wie Microsoft-Office-Paketen [OFFEN 2, Bedeutung klären]; die Punkte je
  Sparte für den Baustein „bereitzuhalten“ in der Terminbestätigung [OFFEN
  1 aus V4, siehe Zulieferungen].

## Phase 153: Objekte am Vorgang, Großkunde

- [x] **Datenmodell additiv:** neue Tabelle `vorgang_objekte` (`id`,
      `vorgang_id`, `bezeichnung` (frei, Standard „Objekt 1“), `strasse`,
      `plz`, `ort`, `objektart`, `parteien`, `interessen` (JSON),
      `lat`/`lon`/`geocode_status`, `reihenfolge`, `aktiv`). Migration legt
      je bestehendem Vorgang ein Objekt aus dem Ausführungsort des Kunden
      an (Objektart/Parteien/Interessen aus Kunde/Vorgang kopiert). Die
      bisherigen Felder am Kunden/Vorgang bleiben als „Hauptobjekt“
      (Objekt mit `reihenfolge = 1`) synchron: Änderung am Hauptobjekt
      schreibt die Kundenfelder mit und umgekehrt (eine Funktion
      `objekte.hauptobjekt_sync`), damit monday-Sync, Duplikatprüfung,
      Geocoding, Karte und alle Bestandslisten unverändert funktionieren.
      `vot_termine.objekt_id`, `erfassungen.objekt_id`, `angebote.objekt_id`
      (nullbar; Migration setzt Hauptobjekt). `kunden.grosskunde` (0/1).
      **(AT-Chat)** `projekt_gewerke.objekt_id` ebenfalls (Projekt aus einem
      Objekt-2-Angebot trägt dessen Objekt); Ausführungsort überall über
      `objekte.ausfuehrungsort` (siehe Einfügung).
- [x] **Kundenkartei, Block „Objekte“** im Kundeninfo-Bereich: Liste der
      Objekte als Karten (Bezeichnung, Adresse, Objektart, Interessen,
      Termin-Status, Erfassung/Angebot-Chips), Button „Objekt hinzufügen“
      (Formular mit denselben Feldern, Autospeichern, Pflichtfelder und
      rote Umrandung wie beim Hauptobjekt), Objekt bearbeiten, Objekt
      deaktivieren (nicht löschen, wenn Termin/Erfassung/Angebot hängt),
      Reihenfolge per Pfeil. Ein-Objekt-Vorgänge sehen weiterhin nur die
      bekannten Adressfelder plus den Link „Weiteres Objekt hinzufügen“
      (kein Mehraufwand im Normalfall). Interessen-Badges des Vorgangs =
      Vereinigung aller Objekt-Interessen.
- [x] **Termine je Objekt:** Terminassistent und manuelle Buchung fragen
      bei mehr als einem Objekt das Objekt ab (Auswahl mit Adresse; Fahrzeit
      und Geocoding je Objektadresse); Button „Terminierung“ (B8) wird
      aktiv, sobald mindestens ein Objekt einen vorgemerkten Termin hat,
      und bucht alle vorgemerkten Objekttermine in einem Schritt; Objekte
      ohne Termin bleiben offen (Hinweis „1 von 3 Objekten ohne Termin“).
      Phase Terminiert, sobald der erste Objekttermin steht; Leads VOT
      zeigt je Objekttermin eine Zeile mit Objektadresse; „Erfassung
      starten“ übergibt das Objekt (Ausführungsort = Objektadresse,
      Objektart belegt O01/O03/PO01 vor wie v23). Angebot erhält
      `objekt_id` aus der Erfassung; Vorgangsakte und Deals-Board gruppieren
      Erfassungen und Angebote je Objekt. Ersatzkunde-Dialog, Absage und
      Umbuchung arbeiten je Objekttermin. **(AT-Chat)** Angebots-PDF,
      Lieferschein, BzA-Datenblatt und Heizreport des Objekt-2-Angebots zeigen
      die Objektadresse als Ausführungsort (Test mit Kontrollkunde Schliwa,
      Objekt 2).
- [x] **Terminbestätigung bei mehreren Objekten:** neue Vorlage
      `terminbestaetigung_objekte` (Kategorie Terminbestätigung, je
      Vertriebler wie v29: Rahmen + {vertriebler_block}) mit Platzhalter
      {objektliste} (je Objekt: Bezeichnung, Adresse, Datum, Uhrzeit,
      Vertriebler); ICS-Anhang je Objekttermin (mehrere ICS in einer Mail,
      je eigene UID). Beim Klick auf „Terminierung“ erscheint bei mehr als
      einem Objekttermin die Wahl **„Eine Bestätigung für alle Objekte“ |
      „Je Objekt eine Bestätigung“**, vorbelegt nach Regel (alle Termine am
      selben Tag → eine; sonst je Objekt). „Je Objekt“ nutzt die bestehende
      Vertriebler-Vorlage `terminbestaetigung_<benutzer_id>` mit neuem
      Platzhalter {objektadresse} (bei Ein-Objekt-Vorgängen = Kundenadresse,
      daher auch in bestehenden Vorlagen ohne Änderung nutzbar). Absender
      termin@ (v29), HV-Versandweg (v29) unverändert; „Terminbestätigung
      erneut senden“ fragt bei mehreren Objekten, welche.
- [x] **Großkunde:** Häkchen „Großkunde“ im Kundeninfo-Block (Autospeichern,
      ID/LM/Admin), Badge „Großkunde“ (eigene Farbe aus `kanal_farben`-
      Mechanik, Parameter `grosskunde_farbe`) in Boards (Spalte „Großkunde“
      im Spaltenkatalog, Standard ausgeblendet, Badge zusätzlich am
      Kundennamen), Kartei-Kopf, Kanban-Karte, HV-Ansicht, Leads VOT;
      Filter-Chip „Großkunde“ in Hauptboard/Deals/Anrufliste; Sortierung
      möglich. Aktivität „als Großkunde gekennzeichnet“.

## Phase 154: Dashboard-Kacheln, Hauptboard-Scrollen, Sammelaktionen

- [x] **Kacheln verschieben:** auf „Mein Dashboard“ oben rechts ein
      Stift-Icon (lokales SVG). Klick → Bearbeitungsmodus: alle Kacheln und
      Blöcke (Fällig heute, Kommende Wiedervorlagen, Offene To-Dos,
      Routenplaner, Meine Termine, Mails mit Fehler) erhalten einen Griff
      und lassen sich per Drag & Drop innerhalb des Rasters umsortieren
      (Platzhalter beim Ziehen, Einrasten, keine Größenänderung); das
      Stift-Icon wird zum **Haken**; Klick auf den Haken speichert die
      Reihenfolge je Nutzer (`benutzer_einstellungen` Key
      `dashboard_kacheln`) und verlässt den Modus; Escape verwirft. Die
      Formatierung (Abstände, Breiten, Tokens aus v30, Hell/Dunkel) bleibt
      in beiden Modi identisch; neue Kacheln späterer Versionen hängen sich
      hinten an. Button „Zurücksetzen“ im Bearbeitungsmodus.
- [x] **Seitliches Scrollen auf jeder Seitenhöhe:** die horizontale
      Scrollleiste der Board-Tabelle (Hauptboard, Deals, Infoabend,
      Handelsvertreter) ist am unteren Rand des sichtbaren Bereichs fixiert
      (sticky bottom innerhalb `.lm-tabellen` bzw. synchronisierte
      Zweit-Scrollleiste), sodass man nicht erst ans Tabellenende scrollen
      muss; zusätzlich Shift + Mausrad und Ziehen mit gedrückter mittlerer
      Maustaste. Sticky-Kopf, Sticky-Filter (v25) und Spaltenbreiten (v29)
      bleiben funktionsfähig; geprüft bei 1366 px und 1920 px, hell und
      dunkel.
- [x] **Sammelaktion „Archivieren“** (Hauptboard, Deals, Infoabend;
      Registrierung in `SAMMELAKTIONEN`, Rechte ID/LM/Admin): markierte
      Leads erhalten `vorgaenge.archiviert_am` (additiv) und verschwinden
      aus allen Boards, Listen, Anrufliste, Kanban, Karte, Dashboard,
      Kennzahlen (Zeitraum-Kennzahlen zählen archivierte Leads weiterhin
      für die Vergangenheit [ANNAHME]); Sicherheitsabfrage mit Anzahl;
      Leads mit aktivem Termin, offener Erfassung oder offenem Angebot
      werden übersprungen und gemeldet; Aktivität je Lead. **(AT-Chat)**
      Angebotstool und Projektierung bleiben unberührt (siehe Einfügung);
      Vorgangsakte zeigt das Archiv-Banner. Filter-Chip
      **„Archiv“** in Hauptboard und Deals zeigt archivierte Leads (grau)
      mit Sammelaktion **„Wiederherstellen“**; Kartei eines archivierten
      Leads zeigt Banner „Archiviert am … von …“ mit Button
      „Wiederherstellen“. Kein endgültiges Löschen in diesem Plan; der
      bestehende Löschlauf (`loeschlauf`, Anonymisierung) bleibt davon
      unberührt.
- [x] **Sammelaktion „Duplizieren“**: je markiertem Lead ein neuer Vorgang
      am selben Kunden mit Phase Neu, kopierten Objekten, Interessen,
      Kanal, Zuständigen und Notiz, ohne Aktivitäten, Termine, Erfassungen,
      Angebote, Wiedervorlagen; Kennzeichen „Kopie von <Vorgang>“ (Link in
      beide Richtungen, Aktivität in beiden); Duplikatprüfung schlägt
      **nicht** an (bewusste Kopie); Ergebnis-Meldung mit Links. Zweck
      [ANNAHME]: zweiter Vorgang für denselben Kunden (z. B. neue Anfrage
      nach Abschluss), nicht für Mehrobjekt-Fälle (dafür Phase 153).

## Phase 155: Kundenkartei neu geordnet

- [x] **Reihenfolge der Kartei** (`lead_kartei.py`, Template, auf v30-
      Design): Kopf (Name, Badges inkl. Großkunde, Statuskette, Button
      Terminierung oben rechts, Schnellaktionen) → **Notizfeld**
      (Notizen-Chat mit Eingabefeld direkt sichtbar, volle Breite, kompakt)
      und daneben **To-Dos** als schmale Spalte (ca. ein Drittel der Breite,
      Liste der offenen To-Dos zum Vorgang mit Häkchen, Inline-Anlegen)
      [ANNAHME: Notizen links zwei Drittel, To-Dos rechts ein Drittel in
      einer Zeile; unter 900 px untereinander] → Kundeninfo-Block
      (horizontal wie v25, mit Objekte-Block aus Phase 153) → Reiter
      **Anruf · E-Mail · Timeline** (Anruf = Anrufnotizen mit Dauer; E-Mail
      = E-Mail-Verlauf; Timeline = alle Aktivitäten; Reiter „Termin“
      entfällt) → Block **Termine** (alles aus dem bisherigen Reiter Termin
      plus Block Termine: aktiver Termin je Objekt, Historie, drei
      Vorschläge mit Kalenderansicht (v29), Vorab-Gespräch, Umbuchung,
      Absage, „Terminbestätigung erneut senden“) → danach Angebote ·
      Erfassungen · Projekt · Anhänge. Der To-Dos-Block unten entfällt
      (ist nach oben gewandert). Alle Routen und Aktionen bleiben, nur die
      Anordnung ändert sich; Tests, die auf den Reiter „Termin“ prüfen,
      werden angepasst.
- [x] Responsiv: unter 900 px Kopf → Notizen → To-Dos → Kundeninfo →
      Reiter → Termine → übrige Blöcke untereinander.

## Phase 156: E-Mail-Vorlagen, Kaskade, Zuständigen-Auswahl

- [x] **Sparten ausschreiben:** zentrale Funktion `sparten_text(codes,
      form)` mit den Langformen Wärmepumpe · Photovoltaik · Klimaanlage ·
      Wallbox · Gewerbe (Parameter `sparten_langnamen`, pflegbar);
      Platzhalter {sparten} liefert in allen Lead-Vorlagen die Langform in
      natürlicher Aufzählung („Wärmepumpe und Photovoltaik“), neuer
      Platzhalter {sparten_interesse} liefert „Interesse an einer Wärmepumpe“
      / „Interesse an Photovoltaik“ / „Interesse an einer Klimaanlage“ /
      „Interesse an einer Wallbox“ / „Interesse an einer gewerblichen
      Lösung“ bzw. bei mehreren „Interesse an einer Wärmepumpe und
      Photovoltaik“ (Artikel je Sparte im Parameter). Bestehende
      Vorlagentexte werden per Migration durchsucht: wörtliche Kürzel „WP“,
      „PV“, „KL“, „WB“, „GW“ als eigenständige Wörter werden durch die
      Langform ersetzt, Liste der Ersetzungen in der Gesamtübersicht;
      Sparten-Baustein {sparten_hinweise} nutzt die Langform als
      Zwischenüberschrift. Betreffzeilen ebenfalls. Interne Badges (Boards,
      Chips) behalten die Kürzel.
- [x] **Vorlage „nicht erreicht“ entfernen:** Kategorie Kontakt enthält nur
      noch „Disqualifiziert, nicht erreicht“; Vorlage `nicht_erreicht` wird
      im Editor ausgeblendet (Datensatz bleibt für die Historie), Blatt
      Kaskade: Spalte `aktion` bei Versuch 2 und 4 auf `keine`
      (Arbeitsanweisung Live-Excel), Versand-Job verschickt `nicht_erreicht`
      nicht mehr (auch nicht aus alter Warteschlange: offene Einträge
      werden storniert mit Protokoll); „Disqualifiziert“ nach dem letzten
      Versuch unverändert (v23/v29). Doppelversand-Schutz bleibt.
- [x] **Innendienst-Auswahl = Leadmanager-Kennzeichen:** neues Häkchen
      „Leadmanager“ in der Benutzerverwaltung (additiv `benutzer.
      leadmanager`); alle Innendienst-/Leadmanager-Dropdowns des Moduls
      (Kartei, Inline-Edit der Boards, Sammelaktion, Filter, Anrufliste,
      Schnellanlage, Import) zeigen nur Benutzer mit diesem Häkchen
      (aktiv), sortiert nach Vorname. Migration setzt das Häkchen genau
      für: Andreas Scheelen · Claudia Castro · Paula Köhler · Nikolaos
      Goritsas · Ioannis Simeonidis · Dimi Chatzis (Abgleich über Vor- und
      Nachname, tolerant gegen Groß-/Kleinschreibung und Umlaute; nicht
      gefundene Namen in der Gesamtübersicht und in docs/nach-dem-update
      als Admin-To-do). Alle übrigen Benutzer erhalten das Häkchen nicht,
      ausdrücklich nicht Kyriakos S. und Gabriel S., auch wenn sie bisher
      als Innendienst/Leadmanager wählbar waren. Bestehende Zuweisungen an
      Benutzer ohne Häkchen bleiben gültig und werden im Dropdown nur am
      betroffenen Lead als „(nicht mehr wählbar)“ angezeigt.
- [x] **Außendienst-Auswahl ohne Handelsvertreter:** Dropdown Außendienst
      (Kartei, Inline-Edit, Sammelaktion „Vertriebler zuweisen“, Filter)
      listet nur AD-Profile ohne `terminiert_selbst`. Ausnahme: liegt der
      Lead bei einem Handelsvertreter (`vorgaenge.ad_id` in einer
      HV-Gruppe), zeigt das Dropdown **nur die Gruppe des aktuellen
      Vertreters**: René → nur René; Simon-Gruppe → Simon, Paolo Di Blasi,
      André Lind, Ralf Kinkel, Hartmut Leinenbach (aus `hv_gruppe_rene`/
      `hv_gruppe_simon` plus zugeordnete Mitglieder, Parameter
      `hv_gruppe_simon_mitglieder` [ANNAHME: Mitglieder = alle HV außer
      René]). Wechsel zwischen den Gruppen oder zurück zum angestellten AD
      nur über die Sammelaktion „An Handelsvertreter verschieben“ bzw.
      „An Standard geben“ (v23/v29). Terminassistent-Kandidatenfilter
      (v25/v29) bleibt.

## Phase 157: Felder, Status, Objektart (Nachtrag 13.10.)

- [x] **Interessen MS / WA / DMS:** Sparten-Codes `MS` (Mieterstrom), `WA`
      (Wasser), `DMS` (Denkmalschutz) additiv in der Sparten-Definition
      (`SPARTEN`-Liste, Langnamen-Parameter aus Phase 156, Badge-Farben
      Tokens `--q-*`/Status-Mechanik), Häkchen in Kundenkartei (Objekt-
      Interessen, Phase 153), Schnellanlage, Import-Spaltenzuordnung,
      `POST /api/leads` (Sparten als Text), Filter-Chips in Boards,
      Anrufliste, Kanban, Karte, Statistik-Trichter und Kanal-Report.
      Erfassungsstart: wie WB/GW immer Freitext-Erfassung, Sparten-Badge an
      Erfassung, Warteschlange und externem Angebotseintrag. Kompetenz je
      AD (`kompetenz_sparten`) um die drei Codes erweiterbar (Admin pflegt).
      Blatt „Terminhinweise“ erhält leere Zeilen je neuer Sparte. monday-
      Mapping unverändert (keine monday-Spalte dafür).
- [x] **Außendienst Pflichtfeld:** Parameter `pflichtfelder` erhält
      `ad_id`; Kartei zeigt das Feld rot umrandet mit Hinweis „Bitte
      Außendienst zuweisen“, Zähler und Button „Terminierung“ (B8) werten es
      aus; bei HV-Leads gilt der zugewiesene Handelsvertreter als erfüllt.
      Bestand: Leads ohne AD werden nicht automatisch verändert, erscheinen
      aber mit rotem Feld. **Layoutfehler:** das Eingangsdatum (Format aus
      v29) ragt im Kundeninfo-Block in das Nachbarfeld; Spaltenbreiten des
      Blocks so setzen, dass jedes Feld (auch „TT.MM.JJJJ, HH:MM Uhr“)
      vollständig in seiner Zelle bleibt, geprüft bei 1366 px, 1920 px und
      unter 900 px, hell und dunkel.
- [x] **„unqualifiziert“ → „disqualifiziert“:** Blatt Status: Label der
      Phase `unqualifiziert` lautet **„Disqualifiziert“** (Arbeitsanweisung
      Live-Excel; Label-Quelle bleibt `logik.status_zeile`); alle übrigen
      Anzeigestellen, die den Begriff noch fest im Template tragen
      (Gruppenname im Hauptboard, Gründe-Dialog, Trichter, Kanal-Report,
      Aktivitätstexte neu geschrieben, Mail-Vorlagenname „Disqualifiziert,
      nicht erreicht“ bleibt), werden auf „Disqualifiziert“ umgestellt;
      interner Key, Datenbankwerte, API-Werte und bestehende Tests mit dem
      Key bleiben. **Status in der Kartei änderbar:** die Statuskette im
      Kopf erhält einen Klick-/Dropdown-Wechsel auf jede manuell setzbare
      Phase (Neu, Kontaktiert, Zurückgestellt mit Datum/Grund,
      Disqualifiziert mit Pflichtgrund, Nachbearbeitung) mit denselben
      Regeln und Dialogen wie der Inline-Edit der Boards (`POST
      /lead-management/boards/zeile/{id}` wiederverwenden); abgeleitete
      Phasen (Terminiert, Erfasst, Angebot, Gewonnen, Verloren) sind nicht
      direkt wählbar, Verloren nur über den Grund-Dialog.
- [x] **Mehrfamilienhaus, Rechnungsadresse:** bei Objektart MFH erscheint
      im Objekt-Block die Frage **„Rechnungsadresse identisch mit der
      Objektadresse?“** (Ja/Nein, Vorbelegung Ja); bei Nein erscheinen die
      Felder der Rechnungsadresse (Kunden-Standard `kunden.rechnung_*`,
      v20); Anzahl der Parteien bleibt Pflicht. Pflichtfeld-Zähler: bei
      Nein zählen die Rechnungsadressfelder, bei Ja nicht.

## Phase 158: Kalender, Rückruf, Dashboard, Suche, E-Mails, Krankheit, durchgängiger Prozess (Nachtrag 13.10.)

- [x] **Terminassistent Montag bis Freitag:** AD-Profile erhalten keine
      Samstags-Arbeitszeit mehr (Migration leert Samstag, Eingabefeld in
      der Benutzerverwaltung entfällt), Vorschlagsmaschine lässt Samstag
      aus, Kalenderansicht (v29) zeigt Mo bis Fr (5 Spalten), Wunschzeit
      „Samstag“ aus dem Blatt Wunschzeiten wird beim Abgleich ignoriert
      (Arbeitsanweisung: Zeile im Blatt Wunschzeiten auf `aktiv = nein`).
      Manuelle Buchung an einem Samstag bleibt mit Warnhinweis möglich
      [ANNAHME].
- [x] **Rückruf-Uhrzeit in 5-Minuten-Schritten:** Dialog „Rückruf
      gewünscht“ (und Wiedervorlage-Dialog) mit `step = 300`, serverseitige
      Rundung auf volle 5 Minuten; gleiches Raster im Terminassistenten
      bleibt 15 Minuten.
- [x] **Dashboard „Fällig heute“, Button Erledigt:** Fehler beheben: der
      Button liegt nach dem Klick unter bzw. außerhalb des Feldes; Button
      als überlappendes Element rechts in der Zeile (position absolute im
      Listeneintrag, sichtbar vor und nach dem Klick), nach „Erledigt“ wird
      die Zeile durchgestrichen und mit Rückgängig-Link angezeigt
      (Fehlerursache in der Gesamtübersicht nennen).
- [x] **Kontaktiert, Endziffern-Suche:** Rufnummernsuche akzeptiert eine
      beliebige Ziffernfolge (mindestens 3 Ziffern) und findet alle Leads,
      deren normalisierte Nummer (E.164) **mit dieser Folge endet** oder sie
      enthält (Treffer „endet mit“ zuerst); Anzeige der Treffer mit voller
      Nummer, Name, Phase; gilt auch für monday-Leads (v23).
- [x] **Button „Falsche Telefonnummer“ mit Kundenmail:** Ergebnis
      „Falsche Nummer“ (Anrufliste, Kartei, Boards) sendet zusätzlich die
      neue Vorlage **`falsche_telefonnummer`** (Kategorie Kontakt, Absender
      termin@, Platzhalter {briefanrede}, {vorname}, {nachname},
      {rueckruf_telefon}, {sparten_interesse}, {absender}) an die
      E-Mail-Adresse des Leads, sofern vorhanden (sonst Hinweis, keine
      Mail); Aktivität, Doppelversand-Schutz, HV-Versandweg (v29) wie bei
      den übrigen Vorlagen. **Text (freigegeben 13.10.2026)**, Betreff „Ihre Anfrage bei Friondo: wir erreichen Sie
      nicht“, Text:
      „{briefanrede}
      vielen Dank für Ihr {sparten_interesse}. Wir haben versucht, Sie
      telefonisch zu erreichen, leider ist die uns vorliegende Rufnummer
      nicht korrekt oder nicht mehr gültig.
      Damit wir Ihre Anfrage weiter bearbeiten können, antworten Sie bitte
      einfach auf diese E-Mail mit Ihrer aktuellen Telefonnummer und, wenn
      möglich, einer Uhrzeit, zu der wir Sie gut erreichen. Alternativ
      erreichen Sie uns unter {rueckruf_telefon}.
      Wir freuen uns darauf, mit Ihnen zu sprechen.
      Mit freundlichen Grüßen
      {absender}
      Friondo GmbH“
- [x] **E-Mail aus der Kundenkartei mit Vorlage:** Schnellaktion
      „E-Mail“ im Kartei-Kopf öffnet einen Dialog mit Vorlagenwahl (alle
      Lead-Vorlagen inkl. Terminbestätigung je Vertriebler und
      `terminbestaetigung_objekte`), füllt alle Platzhalter automatisch aus
      Lead, Objekt, aktivem Termin und Vertriebler (bei mehreren Objekten
      Objektauswahl), zeigt Betreff und Text als Vorschau zum Nachbearbeiten,
      hängt bei Terminvorlagen das ICS an, sendet über termin@ (bzw.
      HV-Versandweg) und protokolliert als Aktivität und im E-Mail-Verlauf.
      Fehlende Pflichtdaten für die Vorlage (z. B. kein Termin) werden im
      Dialog rot genannt, Senden gesperrt.
- [x] **Krankheit eines Vertrieblers:** in der Benutzerverwaltung (Admin,
      Innendienst) und auf „Mein Dashboard“ des Vertrieblers (eigener
      Eintrag) ein Abwesenheitseintrag **Art „Krankheit“** mit von/bis
      (additiv Tabelle `benutzer_abwesenheiten`: `benutzer_id`, `art`,
      `von`, `bis`, `bemerkung`, `angelegt_von`). Wirkung: Terminassistent
      schlägt den Vertriebler im Zeitraum nicht vor (Ausschluss mit
      Begründung „krank“); alle seine Vor-Ort-Termine und Vorab-Gespräche im
      Zeitraum erscheinen in der Innendienst-Sicht „Fällig heute“ (jeder
      Leadmanager, ab dem ersten Krankheitstag, bis der Termin umgebucht,
      abgesagt oder der Eintrag beendet ist) mit rotem Hinweis
      **„Krankheit: <Name>“** und Buttons „Umbuchen“ (Terminassistent ohne
      den kranken Vertriebler, Ersatzkunde-Logik v29) und „Absagen“;
      Aktivität am Vorgang „Termin betroffen durch Krankheit <Name>“.
      Kein Mailversand an Kunden ohne Klick. Ende der Krankheit entfernt die
      Hinweise. Andere Arten (Urlaub) als Dropdown-Wert vorbereitet, gleiche
      Wirkung [ANNAHME].
- [x] **Durchgängiger Prozess (Lead-Seite):** ein gemeinsamer Notiz- und
      Kommentarstrom je Vorgang: der Notizen-Chat der Vorgangsakte (v10),
      die Lead-Timeline/Aktivitäten (v12 ff.) und die Kommentare der
      Projektakte (Projektierung, Verlauf + Kommentare mit @Erwähnung)
      werden in der Kundenkartei (Reiter Timeline und Notizfeld), in der
      Vorgangsakte und in der Projektakte **vollständig und identisch**
      angezeigt, mit Herkunfts-Badge (Lead · Angebot · Projekt), Autor und
      Zeitstempel, chronologisch; eine Notiz, die in einem Modul geschrieben
      wird, ist sofort in den anderen sichtbar (eine Schreibroute, keine
      Kopien). Lead-Seite: Kartei und Vorgangsakte lesen Projekt-Kommentare
      mit (nur Anzeige, Schreiben über die bestehende Projekt-Route) und
      zeigen Projektphase, Montagetermin und Projekt-To-Dos im Block
      „Projekt“. Angebotstool-Seite: Vorgangsakte zeigt Lead-Aktivitäten
      (Anrufe, Mails, Termine) im Notizen-Chat als eingeblendete Einträge
      (Filter „nur Notizen“). Projektierungs-Seite (Projektakte zeigt
      Lead-Aktivitäten und Angebots-Notizen) wird als Anforderung an den
      Projektierungs-Strang übergeben [OFFEN 4], nicht hier gebaut; der
      Plan legt dafür die Lesefunktion `vorgang_verlauf(vorgang_id)` an,
      die alle drei Quellen zusammenführt, damit die Projektakte sie nur
      einbinden muss. **(v30/v28)** Die Notizen selbst sind seit v28 bereits
      EINE Spur (`app/notizen.py`) und in allen vier Sichten sichtbar – hier
      nur prüfen und die Lead-Aktivitäten ergänzen, keine neue Notizstruktur.

## Phase 159: Demo-Modus beenden, Testphase (Nachtrag 13.10.)

- [x] **Freischaltung `lead_freigabe_modus = alle`:** Parameter umstellen
      (Migration setzt `alle`, Admin-Abfrage „Demo-Leads löschen oder
      behalten“ aus v12 läuft einmalig beim ersten Aufruf der Lead-
      Einstellungen; **(AT-Chat)** Vorbelegung **löschen** für Generator-
      Leads ohne Erfassung/Angebot/Projekt, Alternative „behalten – bleibt
      ausgeblendet“; siehe Einfügung [ANNAHME geändert]). Alle Rollen laut
      Rechte-Matrix (Innendienst, Leadmanagement, Außendienst, HV, Admin)
      sehen und nutzen das Modul echt; Startportal-Karte ohne Badge „Demo ·
      Coming soon“; Demo-Daten-Generator und Demo-Sperren (`demo = 1`-
      Filter in Listen, Statistik, Kacheln, Rückspielung) entfallen bzw.
      werden wirkungslos; Erfassungs-Vorbelegung aus der Objektart und die
      Lead→AD-Übergabe (Leads VOT) sind scharf.
- [x] **Terminassistent echt, Buchen gesperrt:** neuer Parameter
      `terminierung_aktiv` (Standard **aus**). Der Assistent rechnet mit
      echten Daten (Tool-Termine, Outlook-Frei/Belegt über Graph für
      angestellte AD, sofern `kalender_sync` eingerichtet ist, sonst nur
      Tool-Termine mit Hinweis; Fahrzeiten über den Routing-Dienst;
      Kompetenz-, Kanal- und HV-Regeln) und zeigt die drei konkreten
      Vorschläge mit Begründung und Kalenderansicht in Kartei und Block
      Termine. Bei `aus` sind **„Vormerken“, „Buchen“, manuelle Buchung,
      Umbuchen, Absagen und der Button „Terminierung“ gesperrt** (sichtbar,
      ausgegraut, Tooltip „Testphase: Terminierung noch nicht freigeschaltet“);
      kein Outlook-Eintrag, keine Phase Terminiert über das Modul, keine
      Übergabe in Leads VOT durch das Modul (monday-Weg bleibt unverändert).
      Vorschläge werden zur Auswertung protokolliert (Aktivität „Vorschläge
      berechnet: …“ nur im Testmodus, damit der Assistent beurteilt werden
      kann). Vorab-Gespräche (Telefon/Teams) sind ebenfalls gesperrt (Entscheidung
      13.10.2026): Status „Telefongespräch“/Online-Termin nicht setzbar,
      Buchungslink-Mail nicht auslösbar, gleicher Tooltip.
- [x] **Mailversand gesperrt:** neuer Parameter `mail_versand_aktiv`
      (Standard **aus**); `mail_modus` entfällt als Steuerung (Wert bleibt
      lesbar). Bei `aus` wird **keine** Vorlagen-Mail verschickt, auch nicht
      ins Testpostfach: Eingangsbestätigung, Disqualifiziert, Falsche
      Telefonnummer, Terminbestätigungen, Erinnerungen, Online-Termin-
      Einladung, der Dialog „E-Mail senden“ aus der Kartei und „Termin-
      bestätigung erneut senden“. Die Warteschlange nimmt Einträge mit
      Status `gesperrt` auf (Vorschau und Protokoll sichtbar, Zähler in den
      Lead-Einstellungen „Mails gesperrt: n“), damit der Ablauf prüfbar
      bleibt; beim späteren Einschalten werden gesperrte Einträge **nicht**
      automatisch nachgesendet, sondern verworfen, mit Hinweis [ANNAHME].
      Bounce-Abruf und Parser laufen weiter. Beide Schalter liegen in den
      Lead-Einstellungen unter „Freischaltung“ mit erklärendem Text und
      Prüfpunkten (Senderecht termin@, `kalender_sync`, Routing-Dienst,
      Leadmanager-Häkchen, HV-Gruppen, AD-Profile mit Arbeitszeiten Mo bis
      Fr); das spätere Einschalten ist ein Admin-Klick, kein neuer Plan.
      **(AT-Chat)** Die Sperre betrifft nur Lead-Vorlagen – Angebotsversand
      (angebot@), Projekt-Mails, `mail_ausgang` und BzA-Mail laufen weiter.
- [x] Rechte-Matrix und Gates prüfen: `lead_v2.gate` ohne Demo-Prüfung,
      HV-Gate (v29) bleibt, Außendienst-Sicht (Meine Termine, Lead-Akte
      read-only, No-Show/Verschieben) wie in v12/v23 beschrieben; Voll-Crawl
      mit allen Rollen.

## Phase 160: Tests, Doku, Übergabe

- [x] Tests `tests/test_lead_v5.py`: (a) Migration legt je Vorgang ein
      Hauptobjekt an, Kundenfelder und Hauptobjekt bleiben synchron;
      (b) zweites Objekt anlegen, Termin je Objekt, Terminierung bucht
      beide, Leads VOT zeigt zwei Zeilen, Erfassung übernimmt Objektadresse;
      (c) Terminbestätigung: gleicher Tag → eine Mail mit {objektliste} und
      zwei ICS; verschiedene Tage → zwei Mails mit {objektadresse};
      (d) Großkunde-Häkchen, Badge, Filter; (e) Dashboard-Reihenfolge
      speichern je Nutzer, Zurücksetzen; (f) Archivieren/Wiederherstellen,
      Übersprung bei aktivem Termin, archivierte Leads in keiner Liste;
      (g) Duplizieren ohne Duplikat-Warnung, Kopie-Verweis beidseitig;
      (h) Kartei-Reihenfolge (Notizen/To-Dos vor Kundeninfo, Reiter nur
      Anruf/E-Mail/Timeline, Block Termine enthält Vorschläge);
      (i) {sparten} und {sparten_interesse} für WP, PV+KL, GW; Migration
      ersetzt „WP“ im Vorlagentext; (j) Kaskade: Versuch 2 und 4 erzeugen
      keine Mail, Versuch 5 `disqualifiziert`; (k) Leadmanager-Häkchen
      steuert das Dropdown, Kyriakos S. und Gabriel S. erscheinen nicht; (l) AD-Dropdown ohne HV; bei René-Lead nur René,
      bei Simon-Lead die fünf Namen; (m) Sparten MS/WA/DMS in Kartei, Filter,
      API, Langnamen; (n) AD Pflichtfeld sperrt Terminierung, HV-Lead gilt
      als erfüllt; (o) Label „Disqualifiziert“ überall, Statuswechsel in der
      Kartei mit Pflichtgrund; (p) MFH-Frage Rechnungsadresse Ja/Nein mit
      Pflichtfeld-Zähler; (q) kein Samstag in Vorschlägen und Kalender;
      (r) Rückruf 14:07 → 14:05 bzw. 14:10 je Rundungsregel; (s) Endziffern-
      Suche „4711“ findet +49203…4711; (t) „Falsche Nummer“ sendet
      `falsche_telefonnummer` nur bei vorhandener E-Mail; (u) E-Mail-Dialog
      aus der Kartei füllt Platzhalter und hängt ICS an; (v) Krankheit von/
      bis: Vertriebler nicht vorgeschlagen, seine Termine unter „Fällig
      heute“ mit Hinweis, Ende entfernt Hinweise; (w) Notiz aus der
      Projektakte erscheint in Kartei-Timeline und Vorgangsakte, Notiz aus
      der Kartei in der Vorgangsakte; (x) `lead_freigabe_modus = alle`:
      Innendienst-Login sieht das Modul, kein Demo-Badge, Lead ohne `demo`
      zählt in Kacheln; (y) `terminierung_aktiv = aus`: Vorschläge
      vorhanden, Buchen/Terminierung liefern 403 mit Hinweis, kein
      Outlook-Aufruf; (z) `mail_versand_aktiv = aus`: Eingang erzeugt
      Warteschlangen-Eintrag `gesperrt`, kein Graph-Aufruf, auch nicht
      Testpostfach. Bestehende Lead-Tests anpassen
      (Reiter Termin, nicht_erreicht, Dropdown-Inhalte), jede Anpassung
      begründen. Gesamtlauf grün, `tests/test_v27_sitzungen.py` grün.
- [ ] Rollout-Vorbereitung nach Grundregel – **einmal für v31 + v32 am Ende
      des Durchlaufs** (siehe Einfügung): Server-DB-Kopie nach
      diagnose\, migrate.py zweimal fehlerfrei (nur additive Migrationen:
      `vorgang_objekte`, `objekt_id`-Spalten, `kunden.grosskunde`,
      `vorgaenge.archiviert_am/_von`, `benutzer.leadmanager`, `benutzer_abwesenheiten`, Sparten
      MS/WA/DMS, Parameter, Vorlagen `terminbestaetigung_objekte` und
      `falsche_telefonnummer`), Rückweg-Probe v30-Code auf
      v32-DB, `scripts/voll_crawl.py` für admin/innendienst/aussendienst/
      montage/projektierung und HV-Testbenutzer (hell und dunkel),
      Abnahmeskript und Smoke grün, **Lasttest Profil normal mit Lead-Nutzern
      (siehe Einfügung)**,
      Screenshots vorher/nachher (Kartei mit zwei Objekten, Dashboard im
      Bearbeitungsmodus, Hauptboard mit fixierter Scrollleiste) nach
      `docs/design-v31/`, nur Demo-Daten.
- [x] CLAUDE.md: Abschnitt „Neu in v31 – Lead-Management V5 Feedback-Runde 3
      (abgestimmt 12. und 13.10.2026)“ (Plan: PLAN_LEAD_V5.md, Phasen 153 bis 160;
      Nummern laut Vorspann prüfen), Zuordnungstabelle `| v31 |
      PLAN_LEAD_V5.md | 153–160 |`, Titelzeile auf „(v31)“, in „Neu in v12/
      v23/v25/v29“ die Sätze zu Vorlage nicht_erreicht, Reiter Termin, To-Dos-
      Block unten, Dropdown-Inhalten als *überholt – siehe v31* markieren;
      „Fachliche Regeln“ um „Objekt am Vorgang“ ergänzen (ein Vorgang,
      mehrere Objekte, Hauptobjekt synchron zum Kunden) und um „ein
      Verlauf je Vorgang über alle Module“; Sparten-Liste in „Leads VOT“
      und v23 um MS/WA/DMS ergänzen; Label Disqualifiziert in v12/v23.
      `docs/leadmanagement-entscheidungen.md` Abschnitt V5 mit allen
      [ANNAHME]-Auflösungen; `docs/nach-dem-update-v31.md` (Team: Objekte
      anlegen, Großkunde, Kacheln verschieben, Archiv statt Löschen,
      Kartei-Reihenfolge, nur noch eine Kaskaden-Mail; Admin: Leadmanager-
      Häkchen prüfen, HV-Gruppen-Mitglieder prüfen, Sparten-Langnamen,
      Vorlage `terminbestaetigung_objekte` je Vertriebler gegenlesen);
      `docs/updates.md`; `config.VERSION = "v31"`.
- [ ] Gesamtübersicht am Ende: erledigte Phasen, Testergebnisse,
      angepasste Alt-Tests mit Begründung, Liste der Vorlagen-Ersetzungen
      (Kürzel → Langform), Liste aller [ANNAHME]-Stellen, gebündelte
      Rückfragen. **Ein gemeinsamer Commit für v31 + v32** am Ende des
      Durchlaufs (Nachricht in PLAN_V19 Phase 165); **kein push vor Freigabe**.

## Kontrollwerte für die Abnahme

- Demo-Kunde Schliwa mit Objekt 1 (Im Knick 36, 47269 Duisburg, EFH, WP)
  und Objekt 2 (zweite Adresse, MFH 4 Parteien, PV): Kartei zeigt beide
  Objektkarten; Terminassistent fragt das Objekt ab; nach Terminierung
  beider Objekte am selben Tag eine Mail von termin@ mit zwei ICS; am
  nächsten Tag umgebucht → Option „Je Objekt“ vorbelegt, zwei Mails mit
  jeweiliger Objektadresse.
- Großkunde-Häkchen gesetzt → Badge im Hauptboard, Filter „Großkunde“
  liefert genau diesen Lead.
- Dashboard: Stift → Kachel „Offene To-Dos“ an Position 1 ziehen → Haken →
  Neuladen zeigt die Reihenfolge; zweiter Benutzer sieht Standard.
- Hauptboard mit 25 sichtbaren Spalten bei 1366 px: Scrollleiste unten
  sichtbar, ohne nach unten zu scrollen; Shift + Mausrad scrollt seitlich.
- Drei Leads markiert (einer mit aktivem Termin) → Archivieren → „2
  archiviert, 1 übersprungen: aktiver Termin“; Filter Archiv zeigt die zwei;
  Wiederherstellen bringt sie zurück ins Hauptboard.
- Vorlage Eingangsbestätigung mit Lead Interessen WP+PV: Text enthält
  „Wärmepumpe und Photovoltaik“, nirgends „WP“/„PV“.
- Lead mit Versuch 2 und 4 → keine Mail in der Warteschlange; Versuch 5 →
  `disqualifiziert` geplant.
- Dropdown Innendienst in der Kartei: genau Andreas Scheelen, Claudia
  Castro, Paula Köhler, Nikolaos Goritsas, Ioannis Simeonidis, Dimi Chatzis;
  Kyriakos S. und Gabriel S. fehlen; Dropdown
  Außendienst bei einem Lead von René: nur René; bei einem Lead von Paolo:
  Simon, Paolo, André, Ralf, Hartmut; bei einem Lead ohne HV: nur
  angestellte AD (Horst, Detlev B., Detlef J., Kyriakos, Rudi).

- Lead mit Interesse Mieterstrom: Badge „MS“ im Board, Eingangsbestätigung
  nennt „Mieterstrom“; Erfassungsstart führt in die Freitext-Erfassung.
- Lead ohne Außendienst: rotes Feld, Zähler +1, „Terminierung“ gesperrt;
  nach Zuweisung von Horst aktiv.
- Statuskette in der Kartei: Klick auf „Disqualifiziert“ fragt den Grund,
  Lead wandert in die Gruppe Disqualifiziert; nirgends steht mehr
  „unqualifiziert“ sichtbar.
- Kyriakos krank 14. bis 16.10.: seine zwei Termine am 15.10. stehen bei
  Claudia unter „Fällig heute“ mit „Krankheit: Kyriakos“; Terminassistent
  schlägt ihn bis 16.10. nicht vor; Umbuchen auf Detlef J. entfernt den
  Hinweis.
- Suche „4711“ im Board Kontaktiert findet den Lead mit +49 203 … 4711.
- Notiz „Kunde wünscht Rückruf“ in der Projektakte erscheint sofort in der
  Kartei-Timeline mit Badge „Projekt“.

- Login als Paula Köhler (Innendienst): Lead-Management ohne Demo-Badge
  erreichbar; Kartei eines echten Leads zeigt drei Vorschläge mit
  Begründung; „Buchen“ ausgegraut mit Tooltip „Testphase“; nach dem Klick
  auf „Erreicht“ und Eingang eines API-Leads stehen zwei Einträge
  `gesperrt` in der Warteschlange, im Testpostfach kommt nichts an.

## Zulieferungen / bewusst offen

- **[OFFEN 1] (aus V4, zur Erklärung):** In der Terminbestätigung steht der
  Absatz „Damit wir uns optimal vorbereiten können, bitten wir Sie – sofern
  möglich – folgende Punkte bereitzuhalten:“. Gesucht ist die **Liste der
  Punkte je Sparte**, die darunter stehen soll, zum Beispiel für
  Wärmepumpe: letzte Heizkostenabrechnung, Stromrechnung, Grundriss, Fotos
  vom Heizungsraum; für Photovoltaik: Stromrechnung, Fotos vom Dach und
  Zählerschrank; für Klimaanlage: Raumgrößen, Fotos der Räume und der
  Außenwand; für Wallbox: Fotos vom Stellplatz und Zählerschrank; für
  Gewerbe: Lastgang/Stromrechnung, Pläne. Claudia liefert die endgültigen
  Listen (Blatt „Terminhinweise“); bis dahin bleiben die Platzhalter aus
  v29.
- **[OFFEN 2]** „Add-ons wie Microsoft-Office-Pakete einbinden“: Bedeutung
  klären (Outlook-Add-in, das Mails dem Lead zuordnet? Office-Dateien in
  der Kartei öffnen? Teams-Integration?). Erst nach Klärung planbar; nicht
  Teil dieses Plans.
- **[OFFEN 4]** Projektakte zeigt Lead-Aktivitäten und Angebots-Notizen:
  Anforderung an den Projektierungs-Strang (PLAN_PROJ_V7 oder Nachtrag),
  Grundlage `vorgang_verlauf` aus Phase 158.
- Bestätigung der [ANNAHME]-Stellen: Großkunde ohne Automatik; Samstag
  manuell mit Warnhinweis buchbar; Abwesenheitsart Urlaub mit gleicher
  Wirkung; Rundung der Rückrufzeit auf die nächste volle 5 Minuten; archivierte
  Leads bleiben in vergangenen Kennzahlen; Duplizieren = neuer Vorgang am
  selben Kunden ohne Historie; Notizen/To-Dos-Aufteilung zwei Drittel zu
  ein Drittel; Simon-Gruppe = alle HV außer René. Versionsnummer v31 und
  Phasen 153 bis 160 sind bestätigt. **(AT-Chat, neu zu bestätigen):**
  Objektadresse als Ausführungsort in PDF/BzA/Heizreport/Projektierung;
  Archiv nur als Lead-Sicht; MS/WA/DMS ohne eigene E-Mail-Vorlagen-Reiter und
  als Freitext-Gewerke; Demo-Leads löschen statt entflaggen.
- Weiterhin offen aus V4: Versandweg HV (Standard seit 08.10. `entwurf`),
  Kalender der HV, Zuordnungsregel Infoabend-Lead → Veranstaltung,
  Telefonie/Softphone.
- Spätere Freischaltung von Terminierung und Mailversand: Admin-Klick in
  den Lead-Einstellungen nach Prüfpunkten (kein eigener Plan mehr nötig);
  Voraussetzungen termin@-Senderecht, `kalender_sync`, HV-Versandweg und
  HV-Kalender (offen seit V4).
