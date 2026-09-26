# PLAN_PROJ_V2 – Projektierung, Ausbaustufe 2 (Phasen 74–83)

Voraussetzung: PLAN_PROJ_V1 (Phasen 64–72) und PLAN_PROJ_V1b (Phase 73,
Oberfläche nach Prototyp) sind umgesetzt. Dieser Plan setzt die Rückmeldungen
von Andreas vom 26.09.2026 um. Reihenfolge einhalten; jede Phase endet mit
lokalem Test und Commit. Schema-Änderungen nur idempotent in migrate.py.
CLAUDE.md und Logik-Dateien sind Live-Master – Änderungen nur wie in Phase 83.
Design-Vorlage bleibt `docs/projektierung-prototyp.html`; neue Sichten
(Kalender, Montage-Backend) im selben `pj-`-Stil.

**Start-Prompt für Claude Code (kopieren):**

> Lies `CLAUDE.md`, `PROJEKTIERUNG-KONZEPT.md`, `PLAN_PROJ_V2.md` und
> `docs/projektierung-prototyp.html`. Verschaffe dir einen Überblick über den
> Stand der Projektierung (Phasen 64–73), die Vorgangsakte (v10), die Galerie/
> Dokumente, Teams, Termine, Graph-Versand und die Signatur. Setze dann
> Phase 74 um. Datenbank-Änderungen nur idempotent in migrate.py. Nach jeder
> Phase: Zusammenfassung, betroffene Dateien, Testschritte. Rückfragen nur bei
> echten Widersprüchen – sonst im Sinne des Konzepts entscheiden und in
> `docs/projektierung-entscheidungen.md` notieren. Checkboxen abhaken,
> committen, nicht pushen.

---

## Phase 74 – Kanban-Spalten neu, Terminstatus, Board/Kalender-Umschalter

- [x] **Phasen je Gewerk** (ersetzen die bisherigen): `auftragseingang` ·
  `feinplanung_vot` · `planung` · `montagevorbereitung` · `montage` ·
  `abnahme_freigabe` · `abgeschlossen` · `storniert`. Anzeigenamen:
  „Auftragseingang", „Feinplanung VOT", „Planung", „Montagevorbereitung",
  „Montage", „Abnahme & Freigabe", „Abgeschlossen", „Storniert".
- [x] Migration bestehender Gewerke: feinplanung → auftragseingang, wenn keine
  Feinplanungs-Erfassung abgeschlossen ist, sonst planung; feinplanung_abgeschlossen
  → montagevorbereitung; montage_geplant → montagevorbereitung; in_ausfuehrung →
  montage; abnahme_offen → abnahme_freigabe. Verlaufseintrag „Phase migriert (V2)".
- [x] **Wächter neu:** Auftragseingang → Feinplanung VOT: Pflichtaufgaben Paket
  „Auftragseingang" erledigt. Feinplanung VOT → Planung: Feinplanungs-Erfassung
  abgeschlossen (bis Phase 80: Häkchen „Feinplanung erfasst"). Planung →
  Montagevorbereitung: Pflichtaufgaben der Pakete Planung WP / Planung Elektro /
  Fit for Future erledigt. Montagevorbereitung → Montage: Aufgabe „Projekt zur
  Montage freigegeben" erledigt **und** Termin vorhanden. Montage → Abnahme &
  Freigabe: Häkchen „Montage fertig" (Montage-Backend oder Projektierer).
  Abnahme & Freigabe → Abgeschlossen: „Rechnung freigeben". Override mit
  Begründung wie bisher.
- [x] „Angebot → Projekt" legt das Gewerk in **Auftragseingang** an.
- [x] **Terminstatus** je Gewerk (berechnet): `terminiert` (Montagetermin mit
  Team, Kunde bestätigt), `unbestaetigt` (Montagetermin vorhanden, Kunde nicht
  bestätigt), `untermininiert` (kein Montagetermin). Auf der Board-Karte oben
  rechts als Badge: grün „Terminiert · 13.10.–15.10. · Team 3", gelb „Termin
  unbestätigt · 13.10.", rot „Unterminiert". Bei Kombi-Projekten je Gewerk-Zeile
  ein kleines Badge, oben rechts das des Gewerks, das die Spalte bestimmt.
  Filter „Terminstatus" in Board und Liste.
- [x] **Umschalter Board | Kalender** oben auf `/projektierung` (Chips). Die
  Kalendersicht kommt in Phase 75; der Umschalter zeigt bis dahin die
  Terminübersicht.
- [x] Startportal: sechs Kacheln (Auftragseingang · Feinplanung VOT · Planung ·
  Montagevorbereitung · Montage · Abnahme & Freigabe) + Kachel „Unterminiert"
  (Anzahl Gewerke ab Phase Planung ohne Montagetermin, rot).
- [x] Test: Migration mit Test-DB, Karten in richtiger Spalte, Badges korrekt.

## Phase 75 – Teams, Zuweisung, Kalender im Tool

- [x] Stammdaten Teams fest anlegen (idempotent): **Montageteam 1–10** (Typ
  `montage`) und **Subteam 1–5** (Typ `sub`), umbenennbar, deaktivierbar;
  je Team optional Leiter (Benutzer), Farbe (für den Kalender), Outlook-
  Kalenderadresse (Phase 81). Mitglieder = Benutzer mit Rolle Montage.
- [x] Zuweisung am Gewerk: `wp_team_id` (Montageteam), `elektro_team_id`
  (Montageteam), `sub_team_id` (Subteam, optional). Im Steckbrief und in der
  Gewerk-Spalte sichtbar; Aufgaben „Montageteam zuweisen" / „Elektro-Montageteam
  zuweisen" (Phase 78) öffnen den Zuweisungsdialog **mit Terminwahl**: Team,
  Beginn, Ende (Vorbelegung Beginn + 4 Arbeitstage = 1 Woche), Kunde bestätigt.
- [x] Termin-Entität erweitern: `dauer_tage`, `team_id` Pflicht bei Typ Montage,
  `ganztaegig` (Standard ja), `outlook_event_id` (Phase 81), `bestaetigt_am`,
  `bestaetigt_quelle` (manuell / mail).
- [x] **Kalender** `/projektierung/kalender`: Wochen- und Monatsansicht.
  Zeilen = Teams (Montageteam 1–10, Subteam 1–5, „ohne Team"), Spalten = Tage;
  Projekte als Balken über ihre Dauer (PR-Nr. · Kunde · Sparte, Farbe des
  Teams, Muster bei unbestätigt), Klick → Akte, Balken per Drag verschiebbar
  (Datum ändern, protokolliert), Ende per Ziehen verlängerbar. Zusätzliche
  Ansicht „Chronologisch" = Liste aller Gewerke nach Montagebeginn (Unterminierte
  ganz unten, rot) mit denselben Karten wie im Board. Filter Team / Sparte /
  Terminstatus. Feinplanungs- und Abnahmetermine als kleine Marker.
- [x] Umschalter aus Phase 74 zeigt jetzt Board | Kalender | Chronologisch.
- [x] Konflikthinweis: Team an zwei Projekten am selben Tag → Warnung im
  Dialog (kein Verbot).
- [x] Test: Zuweisung, Balken, Verschieben, Konfliktwarnung.

## Phase 76 – Galerie am Vorgang

- [ ] **Galerie** hängt an der **Vorgangsakte** (v10), nicht am Projekt. Feste
  Unterordner (Reihenfolge und Namen exakt): `Alte Heizung` · `Elektro` ·
  `Außengerät` · `Öl-Tank` · `Montagedokumente` · `Inbetrieb-/Abnahme` ·
  `Neue Anlage` · `Allgemein`. Ordnerliste in der Parametrierung erweiterbar
  (Standardordner nicht löschbar). Ablage `data/vorgaenge/<vorgang_id>/galerie/<ordner>/`.
- [ ] Migration: bestehende `data/projekte/<PR>/…`-Dateien in die Galerie des
  zugehörigen Vorgangs verschieben (Zuordnung alter Ordner → neuer Ordner:
  Fotos/Alte Anlage → Alte Heizung, Fotos/Zählerschrank → Elektro, Fotos/
  Außengerät → Außengerät, Fotos/Öltank → Öl-Tank, 05 Montage & Protokolle →
  Montagedokumente, Fotos/Neue Anlage → Neue Anlage, Rest → Allgemein).
  Angebots-PDFs bleiben am Angebot (Vorgangsakte zeigt sie ohnehin).
- [ ] Galerie-Ansicht (Vorgangsakte Reiter „Galerie", Projektakte Reiter
  „Galerie" – dieselbe Komponente): Ordner als Kacheln mit Anzahl und
  Vorschaubild, darin Bildraster mit Lightbox, Dokumente als Liste, Upload per
  Drag & Drop, **mobil: Button „📷 Foto aufnehmen" je Ordner** (`<input
  type=file accept=image/* capture=environment multiple>`), Bilder werden
  serverseitig auf max. 2000 px verkleinert (Original optional behalten),
  Metadaten: Ordner, Hochgeladen von/am, Bemerkung. Verschieben zwischen Ordnern,
  Löschen nur Innendienst/Projektierung/Admin (protokolliert).
- [ ] **Rechte:** Vertrieb (Außendienst) darf in eigenen Vorgängen hochladen und
  ansehen – **auch ohne Auftrag**; Innendienst/Projektierung/Admin alles;
  Montage in zugewiesenen Aufträgen ansehen und hochladen (Phase 82). Der
  mobile Erfassungsbogen bekommt am Ende (Seite „Einschätzung") einen Block
  „Fotos für die Galerie" mit den acht Ordnern.
- [ ] Sub-Mails (Phase 79) und Steckbrief (Phase 82) greifen auf diese Ordner zu.
- [ ] Test: Upload am Handy in Ordner, Vertrieb ohne Auftrag, Migration.

## Phase 77 – Projektsteckbrief (Zusammenfassung über den To-dos)

- [ ] Block **„Steckbrief"** ganz oben in der Projektakte (über Gewerk-Spalten
  und Aufgaben) und als Reiter in der Vorgangsakte nach Auftrag. Felder je
  WP-Gewerk (KV-Raster, zweispaltig, editierbar per Klick):
  Hersteller (Bosch / Mitsubishi / …) · Leistungsklasse (kW / Serie) ·
  Innengerät-Variante (AWMB / AWE + Puffer …) · Warmwasser (Speicher/l) ·
  Aufstellort Außengerät (Boden / Wand / Garagendach / Fundament nötig) ·
  Zählerschrank (bleibt / Zweifeld / Dreifeld / Vierfeld · Unterverteilung) ·
  Öltankentsorgung (nein / ja: Größe, Material, Zugang) · Alte Anlage (Öl/Gas,
  Standort, Dachzentrale) · Dynamischer Tarif / iMSys / HEMS (ja/nein) ·
  Folierung (nein/ja) · Materiallift/Kran · Besonderheiten (Freitext).
  Für PV: Module/kWp, Speicher, Wechselrichter, Dach, Gerüst. KL/WB: kompakt.
- [ ] **Ableitung** aus Erfassungsantworten und Angebotspositionen über ein
  neues Blatt **„Steckbrief"** in `projektierung_logik_v1.xlsx`: Spalten
  `feld`, `sparte`, `quelle_typ` (frage / position / profil), `quelle`
  (Fragen-Key oder Positionsnummer), `wert_oder_regel` (z. B. `Pos 045-049 →
  Hersteller Bosch, Serie aus Positionsname`, `Pos 030/031 → 15 kW`,
  `Pos 055 → AWMB`, `Pos 056 → AWE + externer Puffer`, `Pos 152 → Unterverteilung`,
  `A04 = DG → Dachzentrale`, `Z24 → Solarthermie stillgelegt`). Claude Code
  füllt das Blatt mit dem, was aus `konfigurator_logik_v5.xlsx` und den
  vorhandenen Fragen-Keys eindeutig ableitbar ist, und markiert Unsicheres in
  `docs/projektierung-entscheidungen.md`. Andreas ergänzt später.
- [ ] Ableitung läuft bei Projektanlage und auf Knopfdruck „Neu ableiten";
  manuell geänderte Felder werden nicht überschrieben (Kennzeichen).
- [ ] Der Steckbrief ist die Datenquelle für Sub-Mails (Phase 79) und das
  Montage-Backend (Phase 82).
- [ ] Test: Projekt aus Tool-Angebot → Felder vorbelegt; TAIFUN-Angebot → leer,
  editierbar.

## Phase 78 – Aufgabenpakete v2: Aktionstypen, Optionen, Fristen

- [ ] Blatt **Aufgabenpakete** erweitern um: `aktion_typ` (`keine` / `auswahl` /
  `link` / `mail` / `formular` / `kalender` / `galerie` / `api`), `aktion_wert`
  (URL, Sub-Typ + Ordner, Formularname, Ordnername, API-Name), `optionen`
  (durch `|` getrennt, für `auswahl`; die Option, die „erledigt" bedeutet, mit
  `*`), `frist_tage` (leer = später nachtragen), `frist_bezug` (`aktivierung` /
  `feinplanung` / `montage`).
- [ ] Aufgabenzeile in der Akte rendert je Aktionstyp: Häkchen · Radio-Auswahl
  (z. B. „erfolgt bauseits | nicht erforderlich | beauftragt*") · Button mit
  Link (öffnet neuen Tab, setzt „in Arbeit") · Button „Mail senden" (Phase 79)
  · Button zum Formular · Button „Team + Termin" (Phase 75) · Button „Galerie
  → Ordner" · Button API (Phase 80).
- [ ] **Neue Paketinhalte (ersetzen die V1-Pakete für WP; Andreas' Liste):**
  - **Auftragseingang** (ALLE): 1 Auftragsunterlagen prüfen · 2 Kunde
    kontaktieren, Ablauf erklären, Feinplanungstermin abstimmen (kalender:
    Feinplanung) · 3 Auftrag in TAIFUN anlegen · 4 **BzA erstellen und
    versenden** (link: BzA-Portal-URL aus Parametrierung; zusätzlich Button
    „BzA-Datenblatt" → Seite mit allen Feldern aus Vorgang/Förder-Editor in
    Portal-Reihenfolge mit Kopier-Buttons). Anzahlung entfällt hier.
  - **Feinplanung VOT** (WP): 1 **Feinplanungs-Erfassung** (formular:
    feinplanung_wp, vorbelegt aus Vertriebs-Erfassung; bis Phase 80 Häkchen) ·
    2 Heizlastberechnung liegt vor (Häkchen + api: heizreport – bis API-Doku
    vorliegt: Link Heizreport + Upload in Galerie „Montagedokumente") ·
    3 Fotos abgelegt (galerie: Alte Heizung, Elektro, Außengerät, Allgemein –
    Button öffnet Galerie, Häkchen automatisch, wenn in allen vier Ordnern
    mindestens ein Bild liegt) · 4 Abweichungen zum Angebot geprüft, ggf.
    Nachtrag · 5 Gerät/Paket final festgelegt (Steckbrief).
  - **Planung WP** (WP): 1 Montageteam zuweisen (kalender: montage, Team-Typ
    montage) · 2 Stückliste geprüft und Material bestellt (api: ugl_collin –
    Phase 80; Ablage AB des Großhändlers in Galerie „Montagedokumente") ·
    3 GaLa-Beauftragung (auswahl: „erfolgt bauseits | nicht erforderlich |
    beauftragt*" + mail: sub_typ=GaLa-Bau, ordner=Außengerät) · 4 WP-Montage
    Sub beauftragen (auswahl: „Montage durch Friondo* | Sub beauftragt*" +
    mail: sub_typ=WP-Montage, ordner=Alte Heizung) · 5 Öltank-Entsorgung
    (auswahl: „erfolgt bauseits | nicht erforderlich | beauftragt*" + mail:
    sub_typ=Entsorgung, ordner=Öl-Tank) · 6 Folierung geplant (auswahl:
    „keine Folierung | geplant*", nur sichtbar wenn Steckbrief Folierung = ja).
  - **Planung Elektro** (WP, PV, WB): 1 Elektro-Montageteam zuweisen (kalender:
    montage, Team-Typ montage) · 2 Zählerschrank/Unterverteilung mit Auftrag
    bewertet (Häkchen, Steckbrief-Feld Zählerschrank Pflicht) · 3 Elektro-Sub
    (auswahl: „erfolgt über Friondo* | erfolgt bauseits | Sub beauftragt*" +
    mail: sub_typ=Elektro, ordner=Elektro) · 4 Netzbetreiber-Anmeldung
    eingereicht / Zustimmung liegt vor (bleiben aus V1, Fristen später).
  - **Friondo Fit for Future** (WP): 1 Friondo HEMS geplant (auswahl: „Ja* |
    Nein*") · 2 Friondo iMSys geplant (link: SpotmyEnergy-Portal aus
    Parametrierung; Feld „Zählerwechseltermin" am Gewerk, wird im Kalender
    als Marker gezeigt) · 3 Friondo SpotDynamic (link: SpotmyEnergy-Portal) ·
    4 HEMS-Inbetriebnahme terminiert (kalender: sonstige, Person statt Team).
  - **Montagevorbereitung** (ALLE): 1 Anzahlung geschrieben · 2 Anzahlung
    bezahlt · 3 **Projekt zur Montage freigegeben** (Häkchen, Wächter für
    Phase Montage).
  - **Abnahme & Freigabe** (ALLE): wie V1 (Montagebericht · Inbetriebnahme-
    protokoll · Abnahmeprotokoll · Restarbeiten/Reklamationen erfasst ·
    Rechnung freigegeben); Restarbeiten/Reklamationen als eigene Liste am
    Gewerk (Text, Foto, Verantwortlicher, Status offen/erledigt).
  - PV-, KL-, WB-Pakete aus V1 bleiben, bekommen dieselben Aktionstypen
    (Team zuweisen, Galerie, Mail), Inhalte später mit Andreas.
- [ ] Paket-Reihenfolge in der Akte = Spaltenreihenfolge des Boards; das Paket
  der aktuellen Phase ist aufgeklappt, erledigte eingeklappt.
- [ ] Bestehende Gewerke: neue Pakete werden zusätzlich aktiviert, alte
  Aufgaben bleiben (Kennzeichen „V1") und können per Knopf „V1-Aufgaben
  entfernen" bereinigt werden.
- [ ] Test: alle Aktionstypen, Auswahl setzt erledigt korrekt, Wächter greifen.

## Phase 79 – Sub-Beauftragung per Mail

- [ ] Subunternehmer-Stamm: `typ` erweitern um `GaLa-Bau`, `WP-Montage`,
  `Elektro`, `Entsorgung`, `Dachdecker`, `Lift-Kran`, `Gerüst`, `Sonstige`;
  je Typ ein Standard-Sub (Vorbelegung), mehrere Adressen möglich.
- [ ] Blatt **Sub-Mailvorlagen** in der Logik-Excel: `sub_typ`, `betreff`,
  `text` (Platzhalter: {kunde}, {ausfuehrungsadresse}, {telefon_kunde},
  {projektnummer}, {geraet} (Hersteller + Leistungsklasse aus Steckbrief),
  {aussengeraet_details} (Aufstellort, Fundamentmaße aus Gerätedaten),
  {oeltank} (Größe, Material, Zugang, „Mauer entfernen"), {zaehlerschrank},
  {montagetermin}, {ansprechpartner_friondo}, {bemerkung}), `ordner` (Fotos,
  die angehängt werden, mehrere durch `|`), `anhang_steckbrief` (J/N).
  Startinhalte für GaLa-Bau (Fundament), WP-Montage, Elektro, Entsorgung.
- [ ] Button „Mail senden" an der Aufgabe: Dialog mit Sub-Auswahl (Vorbelegung
  Standard), Betreff/Text vorbefüllt (editierbar), Foto-Anhänge aus dem
  Ordner (Vorschau, abwählbar, Bilder auf 1600 px verkleinert, max. 20 MB
  gesamt), Steckbrief-PDF (fpdf2, eine Seite), Termin-Anfrage-Zeile. Versand
  über Graph als `projektierung@friondo.de` (Fallback angebot@), CC
  Projektleiter. Setzt Auswahl auf „beauftragt", legt Sub-Beauftragung an
  (Status angefragt), Mail in den Mail-Verlauf des Projekts; Antwort im
  Postfach (Betreff PR-…) → Status „bestätigt" vorschlagen.
- [ ] Test: Mail mit 3 Fotos + PDF an Testadresse, Verlaufseintrag, Status.

## Phase 80 – Feinplanungs-Erfassung, Heizreport, UGL, Portale, BzA-Datenblatt

- [ ] **Feinplanungs-Erfassung WP** als zweiter Fragenkatalog auf der
  Erfassungs-Infrastruktur: Blatt **„Fragen FP-WP"** in der Projektierungs-
  Logik (Seiten, Fragen-Keys `FP-…`, Typen wie im Konfigurator, ohne Artikel-
  Aktionen). Vorbelegung aus der Vertriebs-Erfassung: je FP-Frage optional
  `vorbelegung_aus` (Fragen-Key der Vertriebs-Erfassung); vorbelegte Antworten
  sind markiert „vom Vertrieb" und müssen bestätigt oder geändert werden.
  Startfragen (Andreas ersetzt durch das TAIFUN-Formular): Aufstellort
  Außengerät bestätigt (inkl. Garagendach) · Fundament nötig · Abstand/
  Leitungsweg Außen-Innen · Innengerät-Standort · Zählerschrank-Zustand
  (bleibt/Zweifeld/Dreifeld) · Unterverteilung · Dynamischer Tarif gewünscht ·
  WP-Zähler §14a · Öltank (ja/nein, Größe, Material, Zugang) · Materiallift/
  Kran · Parkplatz/Anfahrt · Hydraulik-Besonderheiten · Folierung · Heizlast
  (kW, Quelle). Abschluss schreibt Antworten in den Steckbrief (Mapping im
  Blatt Steckbrief, `quelle_typ = fp_frage`) und aktiviert Pakete nach
  Paketregeln. Mobil bedienbar (Rolle Projektierung).
- [ ] **Heizreport:** Button „Heizreport öffnen" (Link) + Upload des Ergebnis-
  PDFs in „Montagedokumente" + Felder kW/Datum. API-Anbindung als Modul
  `heizreport_api.py` vorbereiten (Projekt anlegen, Ergebnis abrufen), aktiv
  erst mit Zugangsdaten/Doku in der Parametrierung.
- [ ] **UGL-Bestellung Collin:** Blatt **„Stücklisten"** in der Logik
  (`position`, `lieferant_artnr`, `menge_je_einheit`, `bezeichnung`,
  `lieferant`) – Claude Code legt es leer mit Beispielzeilen an; Artikelstamm
  bekommt Feld `lieferant_artnr`. Button „Material bestellen" erzeugt die
  UGL-Datei (Satzarten KOP/ADR/POA/END, 200 Byte/Satz, Anfrageart BE,
  Lieferdatum = Montagebeginn − 3 Werktage, Lieferadresse = Ausführungsort
  oder Lager aus Parametrierung) aus den Positionen des Auftrags × Stückliste,
  zeigt fehlende Zuordnungen, legt die Datei in „Montagedokumente" ab und
  bietet Download an (Upload in GC Online Plus manuell). IDS-Connect als
  späterer Schalter vorbereiten. Kundennummer Collin in der Parametrierung.
- [ ] **Portale:** Parametrierung „Projektierung-Einstellungen" bekommt URLs:
  BzA-Portal, SpotmyEnergy-Partnerportal, Heizreport, GC Online Plus.
- [ ] **BzA-Datenblatt:** Seite `/projektierung/gewerk/<id>/bza` mit allen
  Feldern (Antragsteller, Adressen, Gebäude/Baujahr, Wohneinheiten,
  Maßnahme, förderfähige Kosten, Bonus-Bausteine, Fachunternehmer) aus
  Vorgang, Angebot und Förder-Editor, je Feld Kopier-Button; Hinweis, welche
  Felder fehlen. Druck-/PDF-Ansicht.
- [ ] Test: FP-Erfassung mobil, Steckbrief aktualisiert, Pakete aktiviert;
  UGL-Datei mit Testpositionen; Datenblatt vollständig.

## Phase 81 – Outlook-Kalender-Sync, Kunden-Terminbestätigung

- [ ] Je Team eine Outlook-Kalenderadresse (Team-Postfach oder Gruppen-
  kalender; Einrichtung in `docs/graph-einrichtung.md` beschreiben: Graph-
  Berechtigung Calendars.ReadWrite.Shared, Postfächer `team1@…` bis
  `team10@…`, `subteam1@…` bis `subteam5@…` oder ein gemeinsamer Kalender
  mit Kategorie je Team – Claude Code beschreibt beide Wege, Wahl in der
  Parametrierung).
- [ ] Tool → Outlook: Anlegen/Ändern/Löschen von Montage-, Feinplanungs- und
  Abnahmeterminen als Kalendereinträge (Betreff „PR-… Kunde · Sparte",
  Ort = Ausführungsadresse, Text = Steckbrief-Kurzfassung + Link). Outlook →
  Tool: alle 15 Minuten Änderungen an Datum/Dauer zurücklesen, Verlaufseintrag
  „Termin in Outlook verschoben von …". Fehler blockieren nie; Warnsymbol am
  Termin mit „Erneut senden".
- [ ] Kunden-Terminbestätigung: Button „Termin an Kunden senden" (Mail-Vorlage
  in der Parametrierung, Platzhalter Termin/Team/Ansprechpartner/Vorbereitung
  wie „Zugang Heizungsraum freihalten"), Versand über Graph; Kundenantwort im
  Postfach → Vorschlag „Kunde hat bestätigt" (ein Klick); manuelles Häkchen
  bleibt.
- [ ] Test: Termin anlegen → in Outlook; in Outlook verschieben → im Tool;
  Kundenmail.

## Phase 82 – Montage-Backend

- [ ] Eigener mobiler Bereich `/montage` (Rolle Montage; Login wie bisher
  per PIN). Startseite je Benutzer: **Team-Auswahl** (Teams, in denen er
  Mitglied ist) → **Chronologische Liste** der Aufträge des Teams (heute,
  diese Woche, danach; vergangene eingeklappt) als `.mob .einsatz`-Karten
  (Datum, Kunde, Ort, Sparte, Gerät, Besonderheiten, Terminstatus) und
  **Kalendersicht** (Woche, nur eigenes Team) mit Klick in den Auftrag.
- [ ] **Auftragsdetail**: Steckbrief (Phase 77), Ausführungsadresse mit
  Karten-Link und Telefon des Kunden, Ansprechpartner Friondo (Projektleiter,
  Telefon), zugewiesene Teams/Subs mit Terminen, offene Aufgaben mit Rolle
  montage (abhakbar), **Galerie** (alle acht Ordner, ansehen + Foto aufnehmen;
  Hydraulikschema u. Ä. aus „Montagedokumente" direkt öffnen), Buttons
  „Montage gestartet" / „Montage fertig", Restarbeiten melden (Text + Foto).
  Keine Preise, keine anderen Projekte.
- [ ] **Drei Formulare** (mobil, seitenweise, Zwischenspeichern, am Ende PDF
  in Galerie „Inbetrieb-/Abnahme" und Aufgabe im Paket „Abnahme & Freigabe"
  erledigt). Felder als Vorlage in der Logik-Excel, Blatt **„Formulare"**
  (`formular`, `seite`, `feld_key`, `bezeichnung`, `typ` (text / zahl / ja_nein /
  auswahl / foto / unterschrift / datum), `pflicht`, `optionen`), damit Andreas
  die Inhalte ohne Code anpasst. **Entwurf (von Andreas abzunehmen):**
  - **Montagebericht:** Datum, Team, Mitarbeiter, Beginn/Ende je Tag,
    ausgeführte Arbeiten (Checkliste: Altanlage demontiert · Außengerät
    gesetzt · Innengerät montiert · Hydraulik angeschlossen · Elektro
    angeschlossen · Zählerschrank · Puffer/WW · Kondensat · Dämmung · Folierung),
    Abweichungen/Mehrleistungen (Text + Foto), Materialnachbestellung, Stunden
    Regie, Fotos „Neue Anlage".
  - **Inbetriebnahmeprotokoll:** Gerät/Seriennummern (Außen, Innen, Puffer),
    Kältemittel/Füllmenge, Dichtheitsprüfung, Spülung/Befüllung, Anlagendruck,
    Vorlauftemperatur, Heizkurve, hydraulischer Abgleich durchgeführt,
    Frostschutz, elektrische Prüfung (RCD, Isolationswiderstand, Schleifen-
    impedanz), Zählernummer/iMSys, HEMS verbunden, Probelauf ok, Einweisung
    Kunde (ja/nein, Dauer), Bemerkungen, Unterschrift Monteur.
  - **Abnahmeprotokoll:** Leistungen vollständig ja/nein, Mängel-Liste (Text,
    Foto, Frist), Restarbeiten vereinbart, Übergabe Unterlagen (Bedienungs-
    anleitung, Garantie, Protokolle), Kunde bestätigt Einweisung, Datum,
    **Unterschrift Kunde** (bestehende Vor-Ort-Signatur) + Unterschrift
    Monteur; Restarbeiten aus dem Protokoll erzeugen automatisch Einträge in
    der Restarbeiten-Liste des Gewerks.
- [ ] Rechte: Montage sieht nur Aufträge seiner Teams; Vorgangs-/Angebotsdaten
  ohne Preise; Galerie ansehen/hochladen; keine Löschung.
- [ ] Test je Formular am Handy inkl. Unterschrift und PDF; Team 3 sieht nur
  seine Aufträge.

## Phase 83 – Live-Master, Docs, Rollout

- [ ] `CLAUDE.md`: neuen Abschnitt „## Neu in v<nächste freie Nummer> –
  Projektierung V2 (abgestimmt 26.09.2026)" anhängen (Nummer = höchste
  vorhandene + 1; Kopfzeile anpassen), Inhalt wörtlich:

  > - Kanban-Phasen: Auftragseingang · Feinplanung VOT · Planung ·
  >   Montagevorbereitung · Montage · Abnahme & Freigabe · Abgeschlossen ·
  >   Storniert; Terminstatus je Gewerk (terminiert / unbestätigt /
  >   unterminiert) als Badge; Sichten Board | Kalender | Chronologisch.
  > - Teams: Montageteam 1–10, Subteam 1–5 (Stammdaten, Farbe, Outlook-
  >   Kalender); Zuweisung am Gewerk (WP-/Elektro-/Sub-Team) und je Termin;
  >   Kalender mit Balken über die Projektdauer (Standard 1 Woche), Drag,
  >   Konfliktwarnung; Outlook-Sync über Graph in beide Richtungen.
  > - Galerie am Vorgang mit festen Ordnern (Alte Heizung · Elektro ·
  >   Außengerät · Öl-Tank · Montagedokumente · Inbetrieb-/Abnahme · Neue
  >   Anlage · Allgemein), Upload mobil per Kamera für Vertrieb (auch ohne
  >   Auftrag), Planung und Montage; Projektakte zeigt dieselbe Galerie.
  > - Projektsteckbrief über den To-dos (Hersteller, Leistungsklasse,
  >   Innengerät, Zählerschrank, Öltank, Aufstellort, Tarif/iMSys/HEMS,
  >   Folierung …), abgeleitet über Logik-Blatt „Steckbrief", editierbar.
  > - Aufgabenpakete v2 mit Aktionstypen (Häkchen, Auswahl, Link, Mail,
  >   Formular, Kalender, Galerie, API) und Fristen; Pakete Auftragseingang ·
  >   Feinplanung VOT · Planung WP · Planung Elektro · Friondo Fit for Future ·
  >   Montagevorbereitung · Abnahme & Freigabe; Restarbeiten-Liste je Gewerk.
  > - Sub-Beauftragung per Mail aus der Aufgabe (Vorlagen je Sub-Typ,
  >   Fotos aus Galerie-Ordner, Steckbrief-PDF), Absender projektierung@.
  > - Feinplanungs-Erfassung WP (Blatt „Fragen FP-WP", vorbelegt aus der
  >   Vertriebs-Erfassung), Heizreport-Link/Upload (API vorbereitet),
  >   UGL-Bestelldatei für Collin aus Stücklisten (Blatt „Stücklisten",
  >   Artikelstamm-Feld Lieferanten-Artikelnummer), Portal-Links (BzA,
  >   SpotmyEnergy, Heizreport, GC Online Plus), BzA-Datenblatt mit
  >   Kopier-Buttons.
  > - Montage-Backend `/montage`: Team-Auswahl, chronologische Liste,
  >   Wochenkalender, Auftragsdetail mit Steckbrief und Galerie,
  >   Montagebericht · Inbetriebnahmeprotokoll · Abnahmeprotokoll (Felder im
  >   Blatt „Formulare", PDF in Galerie, Kundenunterschrift über Signatur).
  > - Kunden-Terminbestätigung per Mail mit Antwort-Erkennung.

- [ ] `docs/projektierung.md` fortschreiben; `docs/graph-einrichtung.md` um
  Team-Kalender ergänzen; `docs/projektierung-entscheidungen.md` pflegen.
- [ ] Rollout nach Absprache (Lead-Management-Chat!): git push, update.bat,
  Migrationslog prüfen (Phasen, Galerie-Umzug).

---

## Offen / später

- Fristen je Aufgabe: Spalte ist da, Werte trägt Andreas in der Excel nach.
- PV/KL/WB-Pakete inhaltlich mit Andreas durchgehen.
- BzA-Browser-Assistent (halbautomatisches Ausfüllen mit Prüfung durch den
  Mitarbeiter) als Pilot nach V2 – keine Vollautomatik (Portal-Nutzungs-
  bedingungen, persönliche Verantwortung des Unterzeichners, Formularänderungen).
- Heizreport-API-Doku und SpotmyEnergy-Partnerportal-Schnittstelle anfragen.
- IDS-Connect für Collin, sobald Zugang/Lieferanten-ID vorliegt.
- Rechnungen/OP/Mahnwesen (V4 im Konzept).
