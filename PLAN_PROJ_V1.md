# PLAN_PROJ_V1 – Projektierung, Ausbaustufe 1 „Fundament"

Grundlage: `PROJEKTIERUNG-KONZEPT.md` (Abschnitte 3–5, 7, 9). Dieser Plan wird
von Claude Code auf dem Entwicklungs-PC umgesetzt. Reihenfolge der Phasen
einhalten; jede Phase endet mit einem lokalen Test und einem Commit.
`CLAUDE.md` und `konfigurator_logik_v5.xlsx` nie ersetzen – nur die in Phase 72
beschriebenen Ergänzungen anhängen. Stand der CLAUDE.md ist **v10**; dieser Plan
erzeugt **v11**.

**Start-Prompt für Claude Code (kopieren):**

> Lies `CLAUDE.md` und `PLAN_PROJ_V1.md` vollständig. Verschaffe dir einen
> Überblick über die vorhandene Struktur (Routen, Modelle/Tabellen, Templates,
> migrate.py, Rollenprüfung, Startseite, Nummernkreis, Signatur, Graph-Versand,
> Datei-Ablage unter data/). Setze dann Phase 64 des Plans um. Erzeuge alle
> Datenbank-Änderungen ausschließlich als idempotente Schritte in migrate.py.
> Ändere bestehende Funktionen des Angebotstools nur dort, wo der Plan es
> ausdrücklich verlangt. Nach jeder Phase: kurze Zusammenfassung, was gebaut
> wurde, welche Dateien betroffen sind und wie ich es lokal teste. Stelle
> Rückfragen nur bei echten Widersprüchen zum bestehenden Code – sonst
> entscheide im Sinne des Konzepts und notiere die Entscheidung in
> `docs/projektierung-entscheidungen.md`.

Nach jeder Phase an Claude Code: „Phase X ist getestet, weiter mit Phase X+1."

**Voraussetzung:** v10 (Kundenvorgänge, Phasen 59–63) ist umgesetzt und auf dem
Server – dieser Plan setzt darauf auf und nummeriert ab Phase 64 weiter.

---

## Phase 64 – Datenmodell und Migration

- [x] Neue Tabellen (alle mit `id`, `erstellt_am`, `erstellt_von`, `geaendert_am`):
  - `projekte`: `nummer` (PR-JJNNNN, eindeutig), **`vorgang_id`** (v10-Vorgang = Lead/
    Kundenanfrage; pro Vorgang höchstens ein offenes Projekt), `kunde_id`, `ausfuehrung_strasse/plz/ort`
    (aus dem Vorgang übernommen, editierbar),
    `projektleiter_id`, `vertriebler_id` (vom ersten Auftrag), `kanal`, `status_cache`
    (abgeleitet, bei jeder Gewerk-Änderung neu berechnet), `abgeschlossen_am`, `notiz_kopf`.
  - `gewerke`: `projekt_id`, `sparte` (WP/PV/KL/WB), `phase` (feinplanung /
    feinplanung_abgeschlossen / montage_geplant / in_ausfuehrung / abnahme_offen /
    abgeschlossen / storniert), `angebot_id` (aktuelle angenommene Version),
    `angebot_id_original`, `auftragswert_original`, `auftragswert_aktuell`,
    `feinplaner_id`, `elektroplaner_id`, `storno_grund`, `storno_text`,
    `montage_fertig_am`, `freigabe_am`, `freigabe_von`, `restarbeiten_text`,
    `heizlast_kw`, `heizlast_datum`, `heizlast_link`, `phase_geaendert_am`.
  - `aufgaben`: `gewerk_id` (nullable → projektbezogen), `projekt_id`, `paket_instanz_id`
    (nullable), `titel`, `beschreibung`, `rolle`, `verantwortlich_id`, `faellig_am`,
    `status` (offen / in_arbeit / wartet / erledigt / entfaellt), `pflicht` (bool),
    `reihenfolge`, `wartet_frist_am`, `erledigt_am`, `erledigt_von`.
  - `aufgabenpaket_instanzen`: `gewerk_id`, `paket_key`, `aktiviert_am`, `aktiviert_von`,
    `quelle` (regel / manuell / migration), `deaktiviert_am`.
  - `projekt_termine`: `gewerk_id`, `projekt_id`, `typ` (feinplanung / montage / abnahme /
    sub / sonstige), `beginn`, `ende`, `team_id`, `person_id`, `sub_id`, `kunde_bestaetigt`
    (bool), `notiz`.
  - `projekt_dokumente`: `projekt_id`, `gewerk_id` (nullable), `ordner` (Pfad-Text),
    `dateiname`, `pfad`, `typ` (pdf/bild/sonstige), `hochgeladen_von`, `quelle`
    (auto / upload).
  - `projekt_verlauf`: `projekt_id`, `gewerk_id` (nullable), `aufgabe_id` (nullable),
    `art` (kommentar / system), `text`, `benutzer_id`, `erwaehnte_ids` (JSON-Liste).
  - `benachrichtigungen`: `benutzer_id`, `text`, `link`, `gelesen_am`, `art`.
  - `teams`: `name`, `typ` (SHK / Elektro / Sonstige), `aktiv`; `team_mitglieder`: `team_id`, `benutzer_id`.
  - `subunternehmer`: `firma`, `typ` (GaLa-Bau / Elektro / Dachdecker / Entsorgung /
    Lift-Kran / Gerüst / Sonstige), `ansprechpartner`, `email`, `telefon`, `notiz`, `aktiv`.
  - `projektierung_parameter`: Key-Value (Standard-Projektleiter, Standard-Feinplaner,
    Standard-Elektroplaner, Nummernkreis-Zähler, Ordnervorlage JSON, Storno-Gründe JSON,
    Absender-Postfach).
- [x] Bestehende Tabellen erweitern (nullable, idempotent): `angebote.projekt_gewerk_id`;
  `benutzer.rollen` – falls Rollen bisher ein Einzelwert sind: neue Rollen
  `projektierung` und `montage` ergänzen und Mehrfachrollen erlauben (Komma-Liste
  oder Zuordnungstabelle – Claude Code wählt passend zum Bestand);
  `benutzer.kalkulation_sichtbar` (bool, Standard 0); `benutzer.benachrichtigung_mail`
  (aus / sofort / digest, Standard aus).
- [x] Nummernkreis `PR-<JJ><NNNN>` analog AN-C (Zähler in `projektierung_parameter`,
  Jahreswechsel setzt auf 0001).
- [x] Ablageordner `data/projekte/<PR-Nr>/` wird bei Projektanlage mit der
  Ordnervorlage angelegt.
- [x] Storno-Gründe Standard: „Kunde widerrufen", „Finanzierung/Förderung nicht
  erhalten", „Technisch nicht umsetzbar", „Kunde hat anderen Anbieter gewählt",
  „Sonstiges" (Freitext Pflicht bei Sonstiges).
- [x] Test: migrate.py zweimal ausführen → keine Fehler, keine doppelten Spalten.

## Phase 65 – Steuerdatei `projektierung_logik_v1.xlsx` + Import

- [ ] Datei anlegen mit Blättern:
  - **Aufgabenpakete**: Spalten `paket_key`, `paket_name`, `sparte` (WP/PV/KL/WB/ALLE),
    `schritt_nr`, `titel`, `beschreibung`, `rolle` (projektierer / elektroplaner /
    feinplaner / innendienst / buchhaltung / montage), `pflicht` (J/N), `faellig_regel`
    (`+N` Tage nach Aktivierung · `M-N` = N Tage vor erstem Montagetermin · `FP+N` =
    N Tage nach Feinplanungs-Termin), `wartet_frist_tage` (leer = keine).
  - **Paketregeln**: `sparte`, `bedingung` (`IMMER` oder `<frage_key>=<wert>`), `paket_key`.
    In V1 nur `IMMER`-Regeln wirksam; Frage-Regeln werden importiert, aber erst in V2
    ausgewertet.
  - **Ordnerstruktur**: `pfad`, `ebene` (projekt / gewerk).
  - **Sub-Typen**: `typ`, `bezeichnung`.
- [ ] Startinhalt Aufgabenpakete (Andreas passt später in der Excel an):
  - `auftragseingang` (ALLE, IMMER): 1 Auftragsunterlagen prüfen (Angebot, Protokoll,
    Fotos) – projektierer, Pflicht, +2 · 2 Kunde kontaktieren, Ablauf erklären,
    Feinplanungstermin abstimmen – projektierer, Pflicht, +3 · 3 Auftrag in TAIFUN
    anlegen – innendienst, Pflicht, +3 · 4 Anzahlungsrechnung veranlassen – buchhaltung,
    N, +5.
  - `feinplanung_wp` (WP, IMMER): 1 Feinplanungstermin vor Ort durchführen – feinplaner,
    Pflicht, +14 · 2 Heizlast berechnen (Heizreport) und Ergebnis eintragen – feinplaner,
    Pflicht, FP+3 · 3 Fotos Außengerät/Heizungsraum/Zählerschrank abgelegt – feinplaner,
    Pflicht, FP+1 · 4 Abweichungen zum Angebot prüfen, ggf. Nachtrag (Überarbeiten) –
    projektierer, Pflicht, FP+5 · 5 Gerät/Paket final festgelegt – projektierer, Pflicht, FP+5.
  - `elektroplanung_wp` (WP, IMMER): 1 Zählerschrank/Unterverteilung bewerten –
    elektroplaner, Pflicht, FP+5 · 2 Leitungsweg und Querschnitt festlegen – elektroplaner,
    Pflicht, FP+5 · 3 Netzbetreiber-Anmeldung WP (§14a) einreichen – elektroplaner,
    Pflicht, FP+7, wartet 21 · 4 Zustimmung Netzbetreiber liegt vor – elektroplaner,
    Pflicht, M-7 · 5 Elektro-Team einplanen oder externen Elektriker beauftragen –
    elektroplaner, Pflicht, M-14.
  - `beschaffung_wp` (WP, IMMER): 1 Stückliste prüfen – projektierer, Pflicht, FP+5 ·
    2 Material bei Collin bestellen – projektierer, Pflicht, FP+7 · 3 Liefertermin bestätigt –
    projektierer, Pflicht, M-10 · 4 Wareneingang geprüft – projektierer, Pflicht, M-2.
  - `spotdynamic_imsys` (WP, `FP-A05=Ja`): 1 Kunde Tarifvertrag SpotDynamic unterschreiben
    lassen – projektierer, Pflicht, +5 · 2 Smart-Meter-/iMSys-Bestellung beim Partner
    auslösen – projektierer, Pflicht, +7 · 3 Zählerwechsel-Termin mit Netzbetreiber/Partner
    – projektierer, N, +14, wartet 28 · 4 iMSys eingebaut, Zählernummer eingetragen –
    montage, Pflicht, M+0 · 5 HEMS eingerichtet und mit WP verbunden – montage, Pflicht,
    M+0 · 6 Tarifstart bestätigt – projektierer, Pflicht, M+14, wartet 28 · 7 Kunde in
    App eingewiesen – montage, N, M+0.
  - `fundament_gala` (WP, `FP-A12=Ja`): 1 Fundamentmaße aus Gerätedaten festlegen –
    projektierer, Pflicht, FP+3 · 2 GaLa-Bau beauftragen (Mail mit Fotos) – projektierer,
    Pflicht, FP+5 · 3 Fundamenttermin bestätigt – projektierer, Pflicht, M-10 · 4 Fundament
    fertig, Foto abgelegt – projektierer, Pflicht, M-3.
  - `oeltank_entsorgung` (WP, `FP-A20=Ja`): 1 Entsorger beauftragen (Mail mit Fotos,
    Tankgröße, Zugang) – projektierer, Pflicht, FP+5 · 2 Termin vor Montage bestätigt –
    projektierer, Pflicht, M-7 · 3 Entsorgungsnachweis abgelegt – projektierer, Pflicht, M+5.
  - `lift_kran` (WP, `FP-A14=Ja`): 1 Lift/Kran bestellen – projektierer, Pflicht, M-14 ·
    2 Stellfläche/Straßensperrung geklärt – projektierer, N, M-7.
  - `dach_statik` (WP, `FP-A08=Garagendach`): 1 Statik/Tragfähigkeit prüfen – projektierer,
    Pflicht, FP+7 · 2 Dachdecker beauftragen – projektierer, N, FP+10.
  - `foerderung` (WP, IMMER): 1 BzA (Bestätigung zum Antrag) an Kunden – innendienst,
    Pflicht, +3 · 2 Förderantrag durch Kunden gestellt (Nachweis) – projektierer, Pflicht,
    +21, wartet 30 · 3 Zusage liegt vor – projektierer, N, M-1 · 4 BnD nach Abnahme
    erstellt – innendienst, Pflicht, M+10.
  - `montagevorbereitung` (ALLE, IMMER): 1 Montagetermin mit Kunde vereinbart und
    bestätigt – projektierer, Pflicht, M-14 · 2 Teams zugewiesen – projektierer, Pflicht,
    M-14 · 3 Steckbrief für Montage geprüft – projektierer, Pflicht, M-3.
  - `abnahme_freigabe` (ALLE, IMMER): 1 Montagebericht liegt vor – montage, Pflicht, M+1 ·
    2 Inbetriebnahmeprotokoll liegt vor – montage, Pflicht, M+1 · 3 Abnahmeprotokoll mit
    Kundenunterschrift – montage, Pflicht, M+1 · 4 Restarbeiten/Reklamationen erfasst –
    projektierer, Pflicht, M+3 · 5 Rechnung freigegeben – projektierer, Pflicht, M+5.
  - `pv_standard` (PV, IMMER): 1 Feinplanung Dach/Strang/Speicherort – feinplaner, Pflicht,
    +14 · 2 Netzanschlussbegehren beim Netzbetreiber – elektroplaner, Pflicht, FP+5,
    wartet 42 · 3 Gerüst bestellen – projektierer, Pflicht, M-14 · 4 Material bestellen –
    projektierer, Pflicht, FP+7 · 5 Inbetriebnahme + Fertigmeldung Netzbetreiber –
    elektroplaner, Pflicht, M+5 · 6 Marktstammdatenregister eingetragen – elektroplaner,
    Pflicht, M+20.
  - `wb_standard` (WB, IMMER): 1 Wallbox beim Netzbetreiber anmelden – elektroplaner,
    Pflicht, +5 · 2 Material bestellen – projektierer, Pflicht, +7 · 3 Montage + Protokoll –
    montage, Pflicht, M+1.
  - `kl_standard` (KL, IMMER): 1 Feinplanung Innen-/Außengerät, Leitungsweg, Kondensat –
    feinplaner, Pflicht, +14 · 2 Material bestellen – projektierer, Pflicht, FP+7 ·
    3 Montage + Inbetriebnahme (Kältemittel-Nachweis) – montage, Pflicht, M+1.
- [ ] Ordnerstruktur Standard: siehe Konzept 3.5 (`01 …` bis `06 …`, Foto-Unterordner
  auf Ebene gewerk, `01`, `04`, `06` auf Ebene projekt).
- [ ] Import in der Parametrierung: neuer Menüpunkt **„Projektierung-Logik"** mit
  Upload der Excel (wie Logik-Import), Anzeige der Pakete als Tabelle, Versionsstand.
  Änderungen wirken auf **neue** Aktivierungen; bestehende Aufgaben bleiben.
- [ ] Test: Import läuft, Pakete werden angezeigt, doppelter Import ohne Dubletten.

## Phase 66 – „Angebot → Projekt", Storno, Migration

- [ ] Button **„Angebot → Projekt"** im Angebots-Editor und in der Angebotsliste
  (Zeilenaktion) für Status „Angenommen" (Tool und TAIFUN), Rollen Innendienst/Admin/
  Projektierung. Ausgeblendet, wenn `projekt_gewerk_id` gesetzt ist (dann Link
  „→ Projekt PR-…").
- [ ] Button zusätzlich in der **Vorgangsakte** (v10) im Bereich Angebote je angenommenem
  Angebot; die Vorgangsakte zeigt nach Anlage einen Block „Projekt PR-… · Phase je Gewerk"
  mit Link zur Projektakte.
- [ ] Dialog: Kopf mit Kunde + Ausführungsadresse (aus dem Vorgang, editierbar). Wenn zum
  **Vorgang** bereits ein offenes Projekt existiert → Auswahl
  „Zu Projekt PR-… hinzufügen" (vorausgewählt) oder „Neues Projekt anlegen".
  Sparten-Häkchen (Vorbelegung: Sparte des Angebots; bei TAIFUN-Angebot alle
  Interessen des Leads wählbar). Projektleiter (Pflicht, Vorbelegung Standard),
  Feinplaner, Elektroplaner (Vorbelegung Standard), Bemerkung für die Technik.
  Button „Projekt anlegen".
- [ ] Anlage: Projekt (falls neu) + je Sparte ein Gewerk in Phase „Feinplanung";
  Auftragswert = Endbetrag brutto; `IMMER`-Pakete der Sparte + `ALLE` aktivieren,
  Fälligkeiten berechnen (`+N` ab heute; `FP+N` und `M-N` bleiben leer, bis der
  jeweilige Termin existiert, und werden beim Anlegen des Termins nachberechnet);
  Verantwortliche aus Zuweisungen füllen; Ordnerstruktur anlegen; Angebots-PDF
  (bei Tool-Angebot) und Erfassungsprotokoll-PDF automatisch in `01 Angebot & Erfassung`
  ablegen; Verlaufseintrag; Benachrichtigung an Projektleiter, Feinplaner, Elektroplaner
  („Neues Gewerk WP im Projekt PR-26xxxx – Müller, Duisburg").
- [ ] Versionsfolge: Wenn zu einem verknüpften Angebot eine neue Version „Angenommen"
  wird, `gewerke.angebot_id` und `auftragswert_aktuell` automatisch nachziehen,
  Verlaufseintrag „Auftragswert geändert von … auf … (Version .2)".
- [ ] **Storno**: Button am Gewerk (Projektierung/Innendienst/Admin), Pflichtdialog
  Grund + Text, setzt Gewerk „Storniert", Angebot „Abgelehnt" mit Grund
  „Storno nach Auftrag: <Grund>" (bestehende Ablehnungslogik wiederverwenden,
  inkl. monday-Rückspielung wie bei Ablehnung). Projektstatus neu berechnen.
- [ ] **Migration Altbestand** (einmalig in migrate.py, idempotent über Markierung):
  alle Angebote „Angenommen" ohne `projekt_gewerk_id` → Projekt + Gewerk wie oben,
  `quelle = migration`, Projektleiter = Standard (ist der Standard leer: erster
  Admin), Verlaufseintrag „Automatisch aus Altbestand angelegt". Angebote desselben
  Vorgangs werden zu einem Projekt zusammengefasst.
- [ ] Test: Tool-Angebot annehmen → Projekt; zweites Angebot (PV) desselben Kunden →
  Dialog schlägt vorhandenes Projekt vor; TAIFUN-Angebot → Projekt; Storno → Angebot
  abgelehnt; Migration mit Test-DB.

## Phase 67 – Projektakte

- [ ] Route `/projektierung/projekt/<id>`. Kopfbereich: PR-Nr., Kunde (Link zur
  Kundenakte), Rechnungs- und Ausführungsadresse, Telefon/E-Mail, Vertriebler,
  Kanal-Badge, Projektleiter (änderbar), Gesamt-Auftragswert (Summe aktive Gewerke),
  Projektstatus, Buttons „Kommentar", „Dokument hochladen", „Termin anlegen".
- [ ] **Gewerk-Spalten nebeneinander** (1 Gewerk = volle Breite, 2 = halbe, ab 3
  scrollbar/umbrechend). Je Spalte: Sparten-Badge, Phase als Stepper (5 Schritte),
  Planungs-Ampel + „x von y Pflichtaufgaben", Auftragswert original/aktuell,
  Zuweisungen (Feinplaner, Elektroplaner – änderbar), Heizlast-Block (kW, Datum,
  Link, Upload-Button → `02 Feinplanung & Heizlast`), **Aufgabenliste gruppiert nach
  Paket** (Checkbox erledigt, Status-Dropdown, Verantwortlicher, Fälligkeit mit
  Überfällig-Markierung, Kommentar-Symbol mit Zähler; Aufgabe klappt auf: Beschreibung,
  Kommentare, Anhänge), Buttons „Aufgabe hinzufügen", „Paket aktivieren"
  (Dropdown der Pakete der Sparte), **Termine** des Gewerks, **Auftrag**: Angebotsnummer
  + Version, Endbetrag, Link zum Angebot/PDF, Positionen aufklappbar (Kundenpreise;
  EK/DB nur bei `kalkulation_sichtbar` oder Innendienst/Admin), Buttons
  „Phase ändern", „Stornieren", ab Phase Abnahme offen: „Rechnung freigeben".
- [ ] Reiter unter den Gewerken: **Dokumente** (Ordnerbaum, Upload per Drag & Drop
  und Kamera, Vorschau Bilder, Löschen nur Projektierung/Admin mit Protokoll),
  **Verlauf & Kommentare** (Kommentare + Systemereignisse chronologisch, Eingabefeld
  mit @Erwähnung – Autovervollständigung der Benutzernamen; technisch als eigene
  Tabelle `projekt_verlauf`, Darstellung im Stil des v10-Notizen-Chats; darunter
  aufklappbar read-only der Notizen-Chat des Vorgangs aus der Vertriebsphase), **Subs & Bestellungen**
  (V1: Sub aus Stamm zuordnen mit Leistung, Status angefragt/beauftragt/bestätigt/
  erledigt, Termin, Notiz; Mailversand erst V2), **Mail-Verlauf** (Platzhalter mit
  Hinweis „ab V2").
- [ ] **Phasenwechsel** mit Wächtern (Konzept 3.1): Dialog zeigt unerfüllte
  Bedingungen; Override-Feld „Begründung" (Pflicht) → Verlaufseintrag „Phase geändert
  trotz offener Punkte: …". Rückwärts immer mit Begründung.
- [ ] **Rechnung freigeben**: Dialog „Restarbeiten/Reklamationen?" (Radio: keine /
  ja + Pflichttext), setzt `freigabe_am/von`, Phase „Abgeschlossen", Benachrichtigung an
  Rolle Buchhaltung (Benutzer mit Rolle Innendienst, in Parametrierung
  „Buchhaltungs-Benutzer" wählbar), Verlaufseintrag. Restarbeiten-Text erzeugt
  automatisch eine offene Aufgabe „Restarbeiten: …" (Pflicht, projektierer, +14).
- [ ] Test: Kombi-Projekt mit WP + PV nebeneinander, Aufgaben abhaken, Ampel wechselt,
  Phasenwechsel mit und ohne Override, Freigabe mit Restarbeiten.

## Phase 68 – Kanban, Liste, Startseite

- [ ] Route `/projektierung` = **Kanban**. Spalten: Feinplanung · Feinplanung
  abgeschlossen · Montage geplant · In Ausführung · Abnahme offen · (Abgeschlossen,
  eingeklappt, letzte 30 Tage). Karte = Projekt in der Spalte seines abgeleiteten
  Status. Karteninhalt: PR-Nr., Kunde, Ort, Projektleiter-Kürzel, Kanal-Badge,
  je Gewerk eine Chip-Zeile „WP · Phase · Ampel · nächster Termin (Datum) · x offen/
  y überfällig", Gesamtwert, rotes Badge bei überfälligen Pflichtaufgaben.
  Klick → Akte. Drag & Drop: bei einem offenen Gewerk direkt (Wächter-Dialog wie in
  der Akte), bei mehreren Dialog „Welches Gewerk verschieben?".
  Filterleiste: Sparte (schaltet auf Karte-je-Gewerk um), Projektleiter, Team,
  Kanal, PLZ-Präfix, Suche Kunde/PR-Nr., Häkchen „Storniert anzeigen".
- [ ] **Liste** `/projektierung/liste`: Gewerke als Tabelle (PR-Nr., Kunde, Ort,
  Sparte, Phase, Ampel, Projektleiter, nächster Termin, Auftragswert, überfällig,
  Kanal, Angebotsnummer), Sortierung, dieselben Filter, Summenzeile Auftragswert,
  CSV-Export.
- [ ] **Terminübersicht** `/projektierung/termine`: Wochen- und Monatsansicht aller
  Termine (Filter Team/Person/Typ), Klick → Akte. Termin-Dialog (Typ, Beginn/Ende,
  Team/Person/Sub, Kunde bestätigt, Notiz) aus Akte und Übersicht; beim Anlegen
  eines Montage- oder Feinplanungs-Termins werden `M-N`/`FP+N`-Fälligkeiten des
  Gewerks (nach)berechnet.
- [ ] **Startseite**: Bereich Projektierung – Kacheln zählen Gewerke je Phase mit
  Sparten-Untertitel; Kachel „Überfällige Aufgaben" (Anzahl, Klick → Meine Aufgaben
  mit Filter). Neue Seite **„Meine Aufgaben"** `/projektierung/meine-aufgaben`:
  Gruppen Überfällig · Heute · Diese Woche · Später · Neu zugewiesen (7 Tage);
  Zeile: Aufgabe, Projekt/Gewerk, Fälligkeit, Status-Dropdown, Erledigt-Checkbox.
  Startseiten-Shortcut „Meine Aufgaben" für Rollen Projektierung/Innendienst/Admin.
- [ ] Test: 10 Testprojekte, Board-Filter, Drag & Drop, Kachelzahlen stimmen mit
  Liste überein.

## Phase 69 – Kommunikation und Benachrichtigungen

- [ ] Glocke in der Kopfzeile (alle Rollen): Zähler ungelesen, Dropdown der letzten
  20, Klick → Link + gelesen. Ereignisse: Aufgabe zugewiesen, @Erwähnung,
  Aufgabe fällig heute/überfällig (täglicher Lauf 07:00, gebündelt je Benutzer),
  Phasenwechsel an Gewerken, in denen der Benutzer zugewiesen ist, Freigabe
  (Buchhaltung), neues Gewerk (Projektleiter/Feinplaner/Elektroplaner).
- [ ] E-Mail-Benachrichtigung je Benutzer (Profil): aus / sofort / Tagesdigest 07:15,
  über die bestehende Graph-Strecke, Absender aus `projektierung_parameter`
  (`absender_postfach`, Standard `projektierung@friondo.de`, Fallback
  `angebot@friondo.de`, wenn das Postfach keine Senden-als-Berechtigung hat →
  Fehler protokollieren, Tool nie blockieren). Betreff: „[Friondo] <Ereignis> –
  PR-… <Kunde>". Text schlicht, Link zum Tool (`http://192.168.35.4:8000/...`).
- [ ] @Erwähnung: `@` im Kommentarfeld öffnet Benutzerliste; gespeicherte IDs in
  `erwaehnte_ids`; Erwähnte erhalten Benachrichtigung.
- [ ] Test: Zuweisung → Glocke; Erwähnung → Glocke + Mail (sofort); Digest-Lauf manuell
  anstoßen.

## Phase 70 – Rollen und Sichten

- [ ] **Demo-Schalter (V1 gilt als Demo im Live-Tool):** In `projektierung_parameter`
  Schlüssel `freigabe_modus` mit Wert `admin` (Standard) oder `alle`. Bei `admin`
  sind **alle** Routen unter `/projektierung`, `/montage`, der Button „Angebot →
  Projekt", der Projektstand-Block am Angebot und die Glocken-Ereignisse aus der
  Projektierung ausschließlich für die Rolle **Admin** sichtbar und aufrufbar
  (Server-seitige Prüfung, nicht nur Menü ausblenden). Innendienst, Projektierung,
  Montage und Außendienst sehen das Modul erst nach Umstellung auf `alle`
  (Parametrierung → Projektierung-Einstellungen, nur Admin). Die Migration des
  Altbestands läuft trotzdem sofort, damit die Demo echte Daten zeigt.
- [ ] **Startportal-Karte:** Die dritte Karte heißt weiterhin „Projektierung";
  darunter in der Karte ein Badge **„Demo · Coming soon"** (gelb, wie ein
  Status-Badge). Für Admins ist die Karte anklickbar und die fünf Kacheln zählen
  live (Phase 68); für alle anderen Rollen bleibt die Karte nicht anklickbar, die
  Kacheln zeigen weiterhin 0 und darunter steht der Hinweis „Das Modul befindet
  sich im Aufbau." Wird `freigabe_modus` auf `alle` gestellt, verschwindet das
  Badge automatisch.
- [ ] Rolle **Projektierung**: Menü zeigt Projektierung (Board, Liste, Termine, Meine
  Aufgaben), Angebote (nur lesend: Liste, PDF, Kundenpreise; kein Editor, kein Versand,
  kein EK/DB außer `kalkulation_sichtbar`), Erfassungen lesend, Kunden lesend. Keine
  Parametrierung außer „Projektierung-Logik", Subunternehmer, Teams.
- [ ] Rolle **Montage** (V1 reduziert): mobiler Bereich `/montage` mit „Meine Einsätze"
  (Termine der eigenen Teams heute/diese Woche), je Einsatz: Steckbrief read-only
  (Kunde, Ausführungsadresse mit Karten-Link, Telefon, Sparte, Gerät/Positionen ohne
  Preise, Bemerkung für die Technik, Heizlast, offene Aufgaben mit Rolle montage,
  erledigbar), Dokumente/Fotos ansehen + Foto-Upload in Ordner, Buttons „Montage
  gestartet" (→ In Ausführung) und „Montage fertig" (→ Abnahme offen, Pflichtfeld
  Kurzbericht → Verlauf). Keine Preise, keine Angebote, keine anderen Projekte.
- [ ] **Außendienst**: an eigenen Angeboten mit Projekt ein Block „Projektstand"
  (Phase je Gewerk, Ampel, nächster Termin, Projektleiter mit Telefon) + Kommentar
  schreiben (landet im Projektverlauf, Projektleiter wird benachrichtigt).
- [ ] Benutzerverwaltung (Admin): Mehrfachrollen, Häkchen `kalkulation_sichtbar`,
  Team-Zuordnung. Neue Stammseiten in der Parametrierung: **Teams**,
  **Subunternehmer**, **Projektierung-Einstellungen** (Standard-Projektleiter/
  Feinplaner/Elektroplaner, Buchhaltungs-Benutzer, Absender-Postfach, Storno-Gründe,
  Ordnervorlage anzeigen).
- [ ] Test je Rolle mit Test-PINs: Projektierung sieht keine EK/DB; Montage sieht nur
  eigene Einsätze; Außendienst sieht Projektstand read-only.

## Phase 71 – Qualität, Docs, Rollout

- [ ] Fehlerfälle: Angebot ohne Kunde-Adresse, Angebot bereits verknüpft, Storno eines
  abgeschlossenen Gewerks (verboten), Phasenwechsel bei storniertem Gewerk (verboten),
  Upload > 20 MB (Hinweis), Benutzer ohne E-Mail bei Mail-Benachrichtigung (überspringen
  + Log).
- [ ] `docs/projektierung.md`: Bedienanleitung (Angebot → Projekt, Board, Akte, Aufgaben,
  Pakete pflegen, Rollen) und `docs/projektierung-entscheidungen.md` (Entscheidungen
  von Claude Code während der Umsetzung).
- [ ] `docs/graph-einrichtung.md` ergänzen: Shared-Postfach `projektierung@friondo.de`
  anlegen, „Senden als" für die Projektierungs-Benutzer (Aufgabe für den M365-Admin).
- [ ] git push → Absprache mit dem Angebotstool-Chat → update.bat auf dem Terminal-
  Server → Migration prüfen (Anzahl migrierter Projekte im Log) → Board öffnen und
  Altbestand einmalig sortieren.

## Phase 72 – Live-Master fortschreiben (Anweisung an Claude Code)

- [ ] `CLAUDE.md`: Kopf auf „(v11)"; neuen Abschnitt **„Neu in v10 – Projektierung V1 (abgestimmt
  20.09.2026)"** anhängen, wörtlich:

  > - **Projektierung V1:** Projekt = Bauvorhaben am v10-Vorgang (höchstens ein
  >   offenes Projekt je Vorgang, Nummer PR-JJNNNN) mit Gewerken je Sparte WP/PV/KL/WB; jedes Gewerk hat eigene Phase
  >   (Feinplanung · Feinplanung abgeschlossen · Montage geplant · In Ausführung ·
  >   Abnahme offen · Abgeschlossen · Storniert), Aufgaben, Termine, Auftrag
  >   (angenommenes Angebot, folgt Versionen). Button „Angebot → Projekt" an
  >   Angeboten „Angenommen" (Tool + TAIFUN, auch in der Vorgangsakte) mit Vorschlag
  >   „zu offenem Projekt des Vorgangs hinzufügen"; Vorgangsakte zeigt den Projektstand. Projektstatus abgeleitet vom am wenigsten fortgeschrittenen
  >   offenen Gewerk.
  > - **Aufgabenpakete** aus `projektierung_logik_v1.xlsx` (Blätter Aufgabenpakete,
  >   Paketregeln, Ordnerstruktur, Sub-Typen), Import in der Parametrierung.
  >   Fälligkeitsregeln `+N`, `FP+N`, `M-N`. Planungs-Ampel = Pflichtaufgaben-Stand.
  >   Wächter je Phasenwechsel, Override mit Begründung protokolliert.
  > - **Oberfläche:** Kanban (Karte = Projekt, Gewerk-Chips), Liste, Terminübersicht,
  >   Projektakte mit Gewerk-Spalten nebeneinander, Dokumente in Ordnerstruktur
  >   `data/projekte/<PR>/`, Verlauf + Kommentare mit @Erwähnung, Glocke +
  >   Mail-Benachrichtigung (aus/sofort/digest), „Meine Aufgaben".
  > - **Rollen:** neu Projektierung (keine EK/DB außer Häkchen „Kalkulation
  >   sichtbar", keine Angebotserstellung) und Montage (nur `/montage`: Meine
  >   Einsätze, Steckbrief, Fotos, Montage gestartet/fertig); Mehrfachrollen;
  >   Teams und Subunternehmer als Stammdaten; Außendienst sieht Projektstand
  >   read-only am eigenen Angebot.
  > - **Demo-Modus:** Parameter `freigabe_modus` (admin / alle, Standard admin):
  >   bei admin ist das gesamte Modul nur für Admins sichtbar und aufrufbar
  >   (server-seitig), Startportal-Karte trägt Badge „Demo · Coming soon", andere
  >   Rollen sehen Null-Kacheln und „Das Modul befindet sich im Aufbau."
  > - **Storno** mit Pflichtgrund setzt Angebot auf Abgelehnt. **Rechnung
  >   freigeben** mit Restarbeiten-Pflichtfrage → Abgeschlossen. Migration legt für
  >   alle angenommenen Angebote Projekte an. Absender Projekt-Mails
  >   `projektierung@friondo.de` (Fallback angebot@).
  > - Geplant: V2 Feinplanungs-Erfassung + Sub-Mails + Kalender, V3 Montage-
  >   Formulare + Collin-Bestellung (UGL/IDS), V4 Rechnungen/OP/Mahnwesen +
  >   Heizreport-/SpotmyEnergy-Anbindung.

- [ ] `konfigurator_logik_v5.xlsx`: **keine Änderung** in V1.

---

## Offene Punkte für Andreas nach V1 (aus Konzept Abschnitt 9)

Karte = Projekt vs. Gewerk · Phasen beibehalten · Projektierung ohne EK/DB ·
Pflicht-Projektleiter · Absender-Postfach · Paketinhalte und Fälligkeiten
verfeinern · TAIFUN-Feinplanungsformular hochladen (V2) · Montage-Formulare
hochladen (V3) · Collin-Kundennummer + IDS-Zugang, Stücklisten je Position (V3) ·
Heizreport-API-Doku und SpotmyEnergy-Partnerkontakt anfragen (V4).
