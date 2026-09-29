# PLAN_PROJ_V4 – Projektierung: Rückmeldungen 29.09.2026 (Phasen 90–93)

Voraussetzung: PLAN_PROJ_V1–V3 (Phasen 64–86) inkl. der Nachträge vom
27.09.2026 (Abnahme & Freigabe Schritt 5, Galerie je Sparte, Team-Zuweisung)
sind umgesetzt; CLAUDE.md steht auf v15 oder höher. Dieser Plan setzt die
14 Rückmeldungen von Andreas vom 29.09.2026 um. Design-Vorlage bleibt
`docs/projektierung-prototyp.html` (`pj-`-Stil). Schema-Änderungen nur
idempotent in migrate.py; CLAUDE.md und `projektierung_logik_v1.xlsx` sind
Live-Master – Änderungen an der Excel nur über den Import-Weg bzw. wie in
Phase 91 beschrieben (Startinhalt ergänzen, bestehende Zeilen nicht löschen).

**Phasen-Zähler:** PLAN_LEAD_V1.1 belegt 87–89; dieser Plan belegt **90–93**.

**Start-Prompt für Claude Code (kopieren):**

> Lies `CLAUDE.md`, `PROJEKTIERUNG-KONZEPT.md`, `PLAN_PROJ_V4.md` und
> `docs/projektierung-entscheidungen.md` (Stand 27.09.). Verschaffe dir einen
> Überblick über Kanban (`templates/projektierung/kanban.html`,
> `_projektierung.html`), Projektakte (`akte.html`), Aufgabenpakete und
> Steckbrief (`projektierung_logik.py`, Blätter Aufgabenpakete / Fragen FP-WP
> / Steckbrief / Sub-Mailvorlagen), Sub-Mails (`sub_mail.py`), UGL (`ugl.py`),
> Heizreport (`heizreport_api.py`), BzA-Datenblatt (`bza.html`) und die
> Termin-Dialoge. **Setze dann alle Phasen 90 bis 93 vollständig in einem
> Durchlauf um** – nicht Phase für Phase auf Freigabe warten. Nach jeder
> Phase: committen und eine kurze Zusammenfassung (was gebaut, welche
> Dateien, wie ich es als Admin teste) anhängen; am Ende eine Gesamtübersicht.
> Datenbank-Änderungen nur idempotent in migrate.py. Rückfragen nur bei echten
> Widersprüchen zum bestehenden Code – sonst im Sinne des Konzepts entscheiden
> und in `docs/projektierung-entscheidungen.md` notieren. Checkboxen abhaken,
> committen, nicht pushen.

---

## Phase 90 – Kanban, Ampel, Termine, Bedienung

### 90.1 Erste Spalte zweigeteilt: Auftragseingang unterminiert | terminiert

- [x] Die Phase `auftragseingang` bleibt **eine** Phase; das Board zeigt sie als
  **zwei Spalten**: **„Auftragseingang · unterminiert"** (kein Montagetermin)
  und **„Auftragseingang · terminiert"** (Montagetermin vorhanden, auch
  unbestätigt). Die terminierte Spalte ist **chronologisch nach Montagebeginn**
  sortiert (frühester Termin oben); die unterminierte nach Auftragsdatum
  (ältester oben). Kombi-Projekte: das Gewerk, das die Spalte bestimmt,
  entscheidet auch über unterminiert/terminiert.
- [x] Drag & Drop von „unterminiert" nach „terminiert" öffnet den bestehenden
  Dialog **„Team + Termin"** (kein Phasenwechsel); zurück nach „unterminiert"
  ist nicht per Drag möglich (Termin löschen in der Akte).
- [x] **Chronologische Sortierung in allen weiteren Spalten**: Karten mit
  Montagetermin nach Montagebeginn aufsteigend, unterminierte darunter (rot,
  nach Auftragsdatum). Gleiches in der Liste (Standardsortierung) und in der
  Sicht „Chronologisch".
- [x] Startportal-Kacheln: „Auftragseingang" zeigt als Untertitel
  „x unterminiert · y terminiert".

### 90.2 Abnahme und Freigabe als getrennte Spalten

- [x] Phase `abnahme_freigabe` wird zu **zwei Phasen**: `abnahme`
  („Abnahme") und `freigabe` („Freigabe"). Spaltenfolge im Board:
  Auftragseingang (2 Spalten) · Feinplanung VOT · Planung · Montagevorbereitung
  · Montage · **Abnahme** · **Freigabe** · Abgeschlossen (eingeklappt) ·
  Storniert (Filter). Bei mehr als sieben sichtbaren Spalten scrollt das Board
  horizontal; Spaltenbreite unverändert, Karten kompakt (Prototyp-Stil).
- [x] Paket **„Abnahme & Freigabe"** wird zu zwei Paketen (Blatt Aufgabenpakete):
  **`abnahme` „Abnahme"** (ALLE): 1 Montagebericht liegt vor (M+1) · 2
  Inbetriebnahmeprotokoll liegt vor (M+1) · 3 Abnahmeprotokoll mit
  Kundenunterschrift (M+1) · 4 Restarbeiten/Reklamationen erfasst (M+3) ·
  5 Abweichungen zum Angebot geprüft, ggf. Nachtrag (M+4).
  **`freigabe` „Freigabe"** (ALLE): 1 Rechnung freigegeben (buchhaltung, M+5)
  · 2 BnD nach Abnahme erstellt (M+10; bei ungeförderten Aufträgen „entfällt").
  Paketregeln: beide `ALLE, IMMER`.
- [x] **Wächter**: Montage → Abnahme: Häkchen „Montage fertig" (wie bisher).
  Abnahme → Freigabe: Pflichtaufgaben des Pakets Abnahme erledigt (Override mit
  Begründung wie bisher). Freigabe → Abgeschlossen: „Rechnung freigeben"
  (bestehender Dialog mit Restarbeiten-Pflichtfrage; setzt Aufgabe 1 des
  Pakets Freigabe auf erledigt).
- [x] **Migration** (idempotent, `migration_abnahme_freigabe_split`): Gewerke in
  `abnahme_freigabe` → `abnahme`, wenn eine Pflichtaufgabe der Schritte 1–5
  offen ist, sonst `freigabe`; bestehende Paket-Instanzen `abnahme_freigabe`:
  Aufgaben 1–5 an eine neue Instanz `abnahme`, 6–7 an `freigabe` hängen
  (Status, Erledigt-Datum, Kommentare bleiben), alte Instanz deaktivieren;
  Verlaufseintrag „Phase migriert (V4: Abnahme/Freigabe getrennt)".
  Bestandsimport (Phase 85): Phasenwert „Abnahme & Freigabe" in der Vorlage
  durch „Abnahme" und „Freigabe" ersetzen (beide gültig, Anleitung anpassen).
- [x] Startportal: sieben Phasen-Kacheln (Auftragseingang · Feinplanung VOT ·
  Planung · Montagevorb. · Montage · Abnahme · Freigabe) + „Unterminiert";
  Kachel-Raster bricht sauber um (Prototyp `.pj-pk`).

### 90.3 Vorlauf-Ampel zum Montagetermin

- [x] Neue berechnete Größe je Gewerk **`vorlauf_wochen`** = (Montagebeginn −
  heute) ÷ 7 (Dezimal). **Ampel**: **grün > 8 Wochen · gelb 4–8 Wochen · rot
  < 4 Wochen**; **unterminiert = rot** mit Text „Unterminiert". Schwellen als
  Parameter `vorlauf_gruen_ab_wochen = 8`, `vorlauf_gelb_ab_wochen = 4` in den
  Projektierungs-Einstellungen.
- [x] Darstellung auf der Board-Karte: farbiger **Ampel-Punkt vor dem Termin-
  Badge** („● Terminiert · 13.10.–15.10. · Team 3"), Tooltip „noch 3 Wochen
  und 2 Tage bis Montagebeginn"; das Termin-Badge behält seine bisherige
  Bedeutung (bestätigt/unbestätigt). Die Ampel gilt für die Phasen
  Auftragseingang bis Montagevorbereitung; ab Montage (Termin läuft/vorbei)
  entfällt sie. Zusätzlich in Liste (Spalte „Vorlauf", sortierbar), Kalender-
  Sicht „Chronologisch" und in den Gewerk-Zeilen der Akte (Kopf).
- [x] Filter „Vorlauf" (grün/gelb/rot) in Board und Liste; Startportal-Kachel
  „Unterminiert" bekommt den Untertitel „+ n rot (< 4 Wochen)".
- [x] Die **Planungs-Ampel** (Pflichtaufgaben-Stand) bleibt unverändert – zwei
  Ampeln mit klarer Beschriftung: „Vorlauf" (Zeit) und „Planung" (Aufgaben).

### 90.4 Termine im 15-Minuten-Takt

- [x] Alle Zeitfelder der Projektierung (Termin-Dialog in Akte, Kalender,
  Terminübersicht, Feinplanungs-/Abnahme-/Sonstige-Termine, Zählerwechsel-
  termin, HEMS-Inbetriebnahme, Montage-Backend „Montage gestartet/fertig"
  mit Uhrzeit): `<input type="datetime-local" step="900">` bzw.
  `<input type="time" step="900">`, Vorbelegung auf das nächste Viertel;
  server-seitig wird jede Uhrzeit auf 15 Minuten gerundet (kaufmännisch).
  Kalender-Drag von Terminen mit Uhrzeit rastet in 15-Minuten-Schritten ein;
  ganztägige Montagetermine bleiben tagesgenau. (Der Terminassistent des
  Lead-Moduls behält sein eigenes Raster `vorschlag_raster_min`.)

### 90.5 Nach dem Häkchen nicht mehr nach oben springen

- [x] Alle Aktionen in der Projektakte, die heute per Formular-POST + Redirect
  laufen (Aufgaben-Häkchen, Status-Dropdown, Auswahl-Radios, Restarbeiten-
  Häkchen, Kommentar, Zuweisung, Steckbrief-Feld, Heizlast, Dokument-Upload),
  senden per **`fetch()`** und aktualisieren die betroffene Zeile/den Block
  **an Ort und Stelle** (Aufgabenzeile: Häkchen, „erledigt am", Paket-Zähler
  „x / y", Planungs-Ampel und Fortschrittsbalken, Wächter-Hinweise; Phase-
  Stepper, wenn ein Wächter dadurch erfüllt wird). Server liefert für diese
  Routen bei `Accept: application/json` ein JSON mit den neuen Werten und dem
  gerenderten Zeilen-HTML; ohne JSON-Accept bleibt das bisherige Redirect
  (Fallback ohne JavaScript).
- [x] Universeller Fallback für alle übrigen POST-Redirects der Projektierung
  und des Montage-Backends: vor dem Absenden `sessionStorage.pjScroll =
  window.scrollY` je URL, nach dem Laden wiederherstellen; zusätzlich Redirect
  mit Anker `#aufgabe-<id>` und `scroll-margin-top` unter dem Kopf.
- [x] Gleiches in „Meine Aufgaben" und im Montage-Backend (Aufgaben-Häkchen,
  Restarbeiten).
- [x] Test: 20 Aufgaben abhaken → Seite bleibt an der Stelle, Zähler/Ampel
  aktualisieren sich; ohne JavaScript weiterhin funktionsfähig.

## Phase 91 – Aufgabenpakete, Feinplanung, Sub-Mails, Fit for Future

### 91.1 Paketinhalte verschieben

- [x] **„Auftragsunterlagen prüfen (Angebot, Protokoll, Fotos)"** wandert aus
  `auftragseingang` nach **`planung_wp` als Schritt 1** (vor „Stückliste
  geprüft und Material bestellt"); für PV/KL/WB (die kein Paket Planung WP
  haben) bleibt der Punkt im Auftragseingang (Blatt: zweite Zeile mit
  `sparte = PV|KL|WB`, `sichtbar_wenn` entsprechend).
- [x] **„Montageteam zuweisen"** wandert aus `planung_wp` in **`auftragseingang`**
  (Schritt 2, `aktion_typ = kalender`, Team-Typ montage, mit Terminwahl) –
  damit entsteht der Montagetermin schon im Auftragseingang und die Karte
  rutscht in die Spalte „terminiert" (90.1). Pflicht = J; der Wächter
  Auftragseingang → Feinplanung VOT verlangt ihn damit (Override mit
  Begründung bleibt möglich – Annahme, siehe unten). „Elektro-Montageteam
  zuweisen" bleibt in Planung Elektro.
- [x] Ergebnis Auftragseingang (ALLE): 1 Kunde kontaktieren, Ablauf erklären,
  Feinplanungstermin abstimmen · 2 Montageteam zuweisen (Team + Termin) ·
  3 Auftrag in TAIFUN anlegen · 4 BzA erstellen und an Kunden senden (Phase
  92) · [nur PV/KL/WB: 5 Auftragsunterlagen prüfen].
  Planung WP: 1 Auftragsunterlagen prüfen · 2 Stückliste geprüft und Material
  bestellt · 3 GaLa-Beauftragung (Fundament + Erdarbeiten) · 4 WP-Montage Sub
  beauftragen · 5 Öltank-Entsorgung · 6 Folierung geplant.
- [x] Migration (`migration_pakete_v4`): offene Gewerke – Aufgabe
  „Auftragsunterlagen prüfen" an die Planung-WP-Instanz umhängen (Status
  bleibt), „Montageteam zuweisen" an die Auftragseingang-Instanz; Reihenfolgen
  nachziehen; Verlaufseintrag. Erledigte Gewerke unverändert.

### 91.2 Fit for Future mit Ja/Nein für iMSys und SpotDynamic

- [x] Paket `fit_for_future` (WP): alle drei Kernpunkte als **Auswahl** mit
  Link: 1 Friondo HEMS geplant („Ja* | Nein*") · 2 Friondo iMSys geplant
  („Ja* | Nein*", Link SpotmyEnergy-Portal, bei Ja: Feld „Zählerwechsel-
  termin" am Gewerk wie bisher) · 3 Friondo SpotDynamic („Ja* | Nein*", Link
  SpotmyEnergy-Portal) · 4 HEMS-Inbetriebnahme terminiert (kalender,
  `sichtbar_wenn = fit_for_future.1 = Ja`).
- [x] **Vorbelegung** der Auswahl aus dem Steckbrief (`hems`, `imsys`,
  `dyn_tarif`): steht dort ja/nein, ist die Option vorausgewählt, aber die
  Aufgabe erst erledigt, wenn der Projektierer sie bestätigt (Klick auf
  „Übernehmen"); Änderung schreibt zurück in den Steckbrief (Kennzeichen
  manuell).
- [x] Feinplanungs-Erfassung: neue Fragen im Blatt „Fragen FP-WP", Seite
  Elektro: **FP-E05 „Friondo iMSys gewünscht"** (ja_nein, Pflicht,
  `vorbelegung_aus = P02`) und **FP-E06 „Friondo HEMS gewünscht"** (ja_nein,
  Pflicht, `vorbelegung_aus = P01`); Steckbrief-Blatt: `imsys ← FP-E05`,
  `hems ← FP-E06` (fp_frage, Ja→ja | Nein→nein). Auftragsdaten-Formular (TAIFUN,
  Phase 84) zeigt die Felder ohnehin über das Steckbrief-Blatt.

### 91.3 Restöl, Stemmarbeiten, Erdarbeiten in den Sub-Mails

- [x] Feinplanungs-Erfassung, Seite „Öltank & Hydraulik": neue Frage
  **FP-O04 „Restöl im Tank (Liter, geschätzt)"** (zahl, Pflicht wenn FP-O01 =
  Ja, sonst ausgeblendet – Spalte `sichtbar_wenn` im Blatt ergänzen, falls
  nicht vorhanden). Steckbrief-Feld **`restoel_liter`** (fp_frage FP-O04);
  Anzeige im Steckbrief-Block „Öltankentsorgung: ja · 3.000 l · Stahl, Keller ·
  Restöl ca. 400 l".
- [x] Neue Steckbrief-Felder aus dem Auftrag (quelle_typ position):
  **`stemmarbeiten`** ← Pos. 126 (Menge > 0 → „ja (Pos. 126, Menge n)"), sonst
  „nein"; **`erdleitung_m`** ← Summe der Mengen der Pos. 139 und 140 (Meter
  Erdleitung); Fallback bei fehlender Position: Erfassungsantworten D07/D08
  (quelle_typ frage). Für TAIFUN-Aufträge: beide Felder im Auftragsdaten-
  Formular (Phase 84) eingebbar (`eingabe = zahl` bzw. `ja_nein`).
- [x] **Sub-Mail-Platzhalter** ergänzen: `{restoel}` („Restöl ca. 400 l" / „kein
  Restöl angegeben"), `{stemmarbeiten}` („Stemmarbeiten sind laut Angebot
  enthalten (Pos. 126) – bitte mit anbieten" / „Stemmarbeiten nicht Teil des
  Auftrags"), `{erdarbeiten}` („Erdarbeiten: Leitungsgraben ca. 12 m für die
  Erdleitung Außengerät ↔ Haus" / „keine Erdarbeiten laut Auftrag").
- [x] Vorlagen im Blatt „Sub-Mailvorlagen" ergänzen (bestehenden Text behalten,
  Absätze anfügen): **GaLa-Bau**: Absatz „Erdarbeiten" mit `{erdarbeiten}`
  (plus Hinweis auf Fundamentmaße aus `{aussengeraet_details}`);
  **Entsorgung**: Absätze `{restoel}` und `{stemmarbeiten}` sowie Tankgröße/
  Material/Zugang aus `{oeltank}`. Steckbrief-PDF zeigt die drei neuen Felder.
- [x] Test: Gewerk mit Öltank + Pos. 126 + 139/140 → Mail-Vorschau Entsorgung
  und GaLa enthalten Restöl, Stemmarbeiten, Meter; Gewerk ohne → die
  „nicht"-Varianten.

## Phase 92 – BzA: Link, BzA-ID, Kundenmail, KfW-Felder

- [x] Felder am Gewerk (nullable): `bza_id` (Text – ID/Vorgangsnummer der BzA aus
  dem Portal), `bza_erstellt_am`, `bza_gesendet_am`, `bza_datei_id` (Galerie),
  `kfw_antragsnummer`, `kfw_zusage_am` (vorbereitet, kein Wächter – Entscheidung
  aus dem CEO-Review steht noch aus).
- [x] Aufgabe **„BzA erstellen und an Kunden senden"** (Auftragseingang, Schritt
  4) zeigt **immer drei Buttons**: „BzA-Portal ↗" (Link `url_bza`; fehlt die
  URL, führt der Button zu den Projektierungs-Einstellungen mit Hinweis),
  „Datenblatt" (bestehende Seite `/projektierung/gewerk/<id>/bza`) und
  **„BzA erfassen"**. Nur sichtbar bei gefördertem Auftrag (Förderblock im
  Angebot aktiv oder TAIFUN-Auftragsdaten „gefördert = ja"); sonst Option
  „entfällt (nicht gefördert)".
- [x] Dialog **„BzA erfassen"**: BzA-ID (Pflicht), Datum (Vorbelegung heute),
  PDF-Upload der BzA (Pflicht; Ablage in Galerie-Ordner **„Förderung"** – neuer
  Standardordner für alle Sparten neben Montagedokumente), Häkchen „Sofort an
  Kunden senden" (Standard an). Speichern setzt die Felder, Verlaufseintrag,
  und – bei gesetztem Häkchen – erzeugt die Kundenmail.
- [x] **Kundenmail „BzA"**: neue Vorlage in Parametrierung → Projektierungs-
  Vorlagen (neben der Kunden-Terminbestätigung). Betreff „Ihre Bestätigung zum
  Antrag (BzA) für die Förderung Ihrer Wärmepumpe – {projektnummer}". Text
  (Startinhalt, von Andreas anzupassen): Anrede {briefanrede}; die BzA liegt
  bei; Schritte für den Kunden: im KfW-Zuschussportal registrieren/anmelden
  ({link_kfw} aus Parametrierung), Antrag mit der BzA-ID **{bza_id}** stellen,
  **den Antrag vor Beginn der Arbeiten stellen**; erwarteter Zuschuss
  {foerderbetrag} (aus dem Förder-Editor, bei TAIFUN aus Auftragsdaten, sonst
  Satz weglassen); Rückfragen an {ansprechpartner_friondo}; Bitte um kurze
  Rückmeldung mit der KfW-Antragsnummer. Anhang: BzA-PDF. Versand über Graph
  als `projektierung@friondo.de` (Fallback angebot@), CC Projektleiter; im
  Demo-/Pilot-Modus gilt die bestehende Sendesperre/Testadresse der
  Projektierung. Vorschau mit Bearbeiten vor dem Senden; Eintrag im Mail-
  Verlauf des Projekts; `bza_gesendet_am` gesetzt; Aufgabe → erledigt.
- [x] Anzeige: BzA-ID, Datum, „an Kunden gesendet am" und KfW-Antragsnummer/
  Zusage im Steckbrief-Block „Förderung" (Akte, Vorgangsakte-Reiter Projekt,
  Steckbrief-PDF) und auf dem BzA-Datenblatt. Neue, nicht verpflichtende
  Aufgabe in **Montagevorbereitung**: „KfW-Antragsnummer/Zusage eingetragen"
  (Häkchen mit Eingabefeldern; Frist später).
- [x] Parametrierung → Projektierungs-Einstellungen: `url_bza` prüfen/eintragen,
  neu `url_kfw_zuschussportal`, Vorlage BzA.
- [x] Test: gefördertes Gewerk → Buttons sichtbar, BzA erfassen mit PDF →
  Mail-Vorschau mit ID und Betrag → Versand an Testadresse → Aufgabe erledigt,
  Felder gefüllt; ungefördertes Gewerk → Option „entfällt".

## Phase 93 – Schnittstellen: Heizreport-API prüfen, UGL zu Ende einrichten

### 93.1 Heizreport

Stand der Recherche (29.09.2026): Heizreport bewirbt den Business-Account
(Cloud-Projekte, Heizlast DIN EN 12831, hydraulischer Abgleich, KfW-Service);
ein Hilfethema „Grundlagen zur Nutzung der API-Schnittstelle" existiert, ist
aber ohne Login nicht erreichbar – **eine öffentliche API-Dokumentation gibt es
nicht**. Die Anbindung braucht Zugangsdaten und die Doku aus dem Business-
Account.

- [x] Claude Code prüft zuerst, ob unter heizreport.com/heiz.report eine
  Doku (OpenAPI/Swagger, Hilfeseiten, Postman) erreichbar ist; Ergebnis in
  `docs/heizreport-api.md` festhalten (URL, Auth-Verfahren, Endpunkte, oder
  „nicht öffentlich").
- [x] `heizreport_api.py` zu einem **generischen REST-Client** ausbauen, der
  ohne Code-Änderung konfigurierbar ist: Parameter Basis-URL, Auth-Art
  (API-Key-Header / Bearer / Basic), Header-Name, Endpunkt-Pfade für „Projekt
  anlegen", „Projekt-Status", „Ergebnis abrufen", Feld-Mapping (JSON) für
  Adresse/Gebäudedaten hin und Heizlast (kW) zurück; Button **„Verbindung
  testen"** in den Projektierungs-Einstellungen (GET auf die Basis-URL mit
  Auth, Antwort-Code anzeigen). Aufgabe „Heizlastberechnung liegt vor" zeigt
  bei konfigurierter API die Buttons „Projekt im Heizreport anlegen" und
  „Ergebnis abrufen" (schreibt kW + Datum + Quelle „Heizreport API"), sonst wie
  bisher Link + Upload.
- [x] **Anfragetext für Andreas** in `docs/heizreport-api.md`: Nachricht an den
  Heizreport-Support (Business-Account, API-Zugang, Doku, Test-Zugangsdaten,
  Rate-Limits, Datenschutz/AVV) – zum Kopieren.

### 93.2 UGL-Bestellung Collin zu Ende einrichten

- [x] **Format-Abgleich**: `ugl.py` gegen die UGL-4.0-Spezifikation prüfen
  (Satzarten KOP · ADR · POA · POZ (Positionstext) · END; feste 200 Byte;
  Feldpositionen und -längen; Zeichensatz; Anfrageart BE; Lieferdatum; Bestell-
  und Kommissionsnummer = PR-Nummer; Kundennummer Collin; Lieferantennummer;
  Mengeneinheit; Preisfelder leer). Wenn die Spezifikation online erreichbar
  ist (GC-Gruppe / ITEK / Datanorm-Umfeld), Feldtabelle in
  `docs/ugl-format.md` ablegen; sonst die Annahmen dort kennzeichnen und eine
  **Testdatei** `docs/ugl-beispiel.ugl` erzeugen, die Andreas an Collin zur
  Prüfung schicken kann (Begleittext zum Kopieren).
- [x] **Stücklisten-Pflege in der Oberfläche** (statt nur Excel): Parametrierung
  → Projektierung → **„Stücklisten"**: Tabelle je Angebotsposition (aus dem
  Artikelstamm, Positionen mit Artikel-Aktion) mit Zeilen `Lieferant ·
  Lieferanten-Artikelnummer · Bezeichnung · Menge je Einheit`; Filter „ohne
  Zuordnung"; Import/Export zum Blatt „Stücklisten" (Excel bleibt Master,
  UI schreibt zurück); Fortschritt „x von y Positionen zugeordnet".
- [x] **Bestell-Dialog** an der Aufgabe „Stückliste geprüft und Material
  bestellt": Vorschau der Materialzeilen (Position → Artikelnummer × Menge),
  rote Liste „ohne Zuordnung" mit Sprung in die Stücklisten-Pflege,
  Lieferdatum (Vorbelegung Montagebeginn − 3 Werktage, änderbar, 15-Min-
  Regel gilt nicht – Datum), Lieferadresse (Ausführungsort | Lager), Bemerkung
  → **UGL erzeugen** (Datei in Galerie „Montagedokumente" + Download) →
  Häkchen „bei Collin hochgeladen" mit Datum → Aufgabe erledigt; zweite
  Bestellung erzeugt Datei `…-2.ugl` (Nachbestellung, Verlaufseintrag).
- [x] Parametrierung: Collin-Kundennummer, Lieferantennummer (falls im Format
  nötig), Lager-Adresse, Standard-Lieferant je Stückliste; Go-live-Checkliste
  (Phase 86) prüft „Stücklisten ≥ 90 % zugeordnet" und „Testdatei von Collin
  bestätigt" (Häkchen).
- [x] IDS-Connect bleibt vorbereiteter Schalter (kein Bau).

### 93.3 Live-Master und Docs

- [x] `CLAUDE.md`: Kopf auf nächste freie Versionsnummer (höchste + 1);
  Abschnitt **„Neu in v<NN> – Projektierung V4 (abgestimmt 29.09.2026)"**
  anhängen, wörtlich:

  > - **Board:** Auftragseingang als zwei Spalten (unterminiert | terminiert,
  >   chronologisch nach Montagebeginn; Drop auf „terminiert" öffnet Team +
  >   Termin); alle Spalten chronologisch, Unterminierte unten. Phasen
  >   `abnahme` und `freigabe` ersetzen `abnahme_freigabe` (Pakete Abnahme:
  >   Montagebericht · IBN-Protokoll · Abnahmeprotokoll · Restarbeiten ·
  >   Abweichungen/Nachtrag; Freigabe: Rechnung freigegeben · BnD); Wächter
  >   Abnahme → Freigabe = Pflichtaufgaben Abnahme.
  > - **Vorlauf-Ampel** je Gewerk bis Montagebeginn: grün > 8 Wochen, gelb
  >   4–8, rot < 4 / unterminiert (Parameter `vorlauf_gruen_ab_wochen`,
  >   `vorlauf_gelb_ab_wochen`); Punkt vor dem Termin-Badge, Spalte in Liste,
  >   Filter; getrennt von der Planungs-Ampel.
  > - **Zeiten im 15-Minuten-Takt** (step 900, serverseitige Rundung) in allen
  >   Projektierungs- und Montage-Dialogen; Aktionen in der Akte per fetch
  >   ohne Seitensprung (JSON-Antwort bei Accept application/json, Redirect
  >   als Fallback), Scroll-Position wird wiederhergestellt.
  > - **Pakete:** „Auftragsunterlagen prüfen" jetzt Schritt 1 in Planung WP;
  >   „Montageteam zuweisen" (Team + Termin) jetzt Schritt 2 im Auftragseingang;
  >   Fit for Future mit Ja/Nein für HEMS, iMSys und SpotDynamic (vorbelegt aus
  >   dem Steckbrief, bestätigt per Klick); FP-Fragen FP-E05 iMSys, FP-E06
  >   HEMS, FP-O04 Restöl; Steckbrief-Felder `restoel_liter`, `stemmarbeiten`
  >   (Pos. 126), `erdleitung_m` (Pos. 139/140), `imsys`, `hems` aus FP.
  > - **Sub-Mails:** Platzhalter {restoel}, {stemmarbeiten}, {erdarbeiten};
  >   GaLa-Vorlage mit Erdarbeiten, Entsorgungs-Vorlage mit Restöl und
  >   Stemmarbeiten.
  > - **BzA:** Felder bza_id, bza_erstellt_am, bza_gesendet_am, bza_datei_id,
  >   kfw_antragsnummer, kfw_zusage_am; Aufgabe mit Buttons Portal ↗ ·
  >   Datenblatt · BzA erfassen (ID, Datum, PDF in Galerie-Ordner „Förderung");
  >   automatische Kundenmail „BzA" (Vorlage in der Parametrierung, Platzhalter
  >   {bza_id}, {foerderbetrag}, {link_kfw}) über projektierung@; nicht
  >   verpflichtende Aufgabe „KfW-Antragsnummer/Zusage" in Montagevorbereitung
  >   (kein Wächter).
  > - **Heizreport:** generischer, in der Parametrierung konfigurierbarer
  >   REST-Client mit Verbindungstest; Buttons an der Heizlast-Aufgabe bei
  >   konfigurierter API; `docs/heizreport-api.md` mit Anfragetext (API-Doku
  >   nicht öffentlich). **UGL:** Formatabgleich (docs/ugl-format.md,
  >   Testdatei), Stücklisten-Pflege in der Parametrierung, Bestell-Dialog mit
  >   Vorschau/Lieferdatum/Lieferadresse, Nachbestellungen, Go-live-Prüfpunkte.

- [x] `docs/projektierung.md` (Board, Ampeln, Pakete, BzA, UGL) und
  `docs/projektierung-entscheidungen.md` fortschreiben; Bestandsimport-
  Anleitung (Phasenwerte) anpassen.

---

## Annahmen (bitte kurz bestätigen oder korrigieren)

1. Punkt 1 der Rückmeldung („erste Spalte 2x") habe ich als **unterminiert |
   terminiert** gelesen – die zweite Spalte chronologisch nach Montagebeginn.
2. **„Montageteam zuweisen" im Auftragseingang ist Pflicht** und damit Teil
   des Wächters Auftragseingang → Feinplanung VOT (Override mit Begründung
   möglich). Soll die Zuweisung optional sein, `pflicht = N` in der Excel.
3. **Vorlauf-Ampel** gilt nur bis Montagevorbereitung; die Planungs-Ampel
   (Aufgabenstand) bleibt separat bestehen.
4. **15-Minuten-Takt** betrifft die Projektierung und das Montage-Backend;
   der Terminassistent des Lead-Moduls behält sein 30-Minuten-Raster.
5. **BzA-Mail** enthält den Hinweis „Antrag vor Beginn der Arbeiten stellen";
   die Fristformulierung (vor Vertragsschluss vs. vor Beginn) bitte mit eurer
   Förderpraxis abgleichen, der Text ist in der Parametrierung änderbar.
6. **KfW-Zusage** bekommt Felder, aber **keinen Wächter** – das ist die offene
   Entscheidung 2 aus dem CEO-Review.
7. **Restöl** wird als geschätzte Literzahl abgefragt (nicht Ja/Nein).
8. **Erdarbeiten** = Meter der Pos. 139/140; wenn in eurem Angebot Erdarbeiten
   in einer anderen Position stecken, Positionsnummern in der Steckbrief-
   Zeile `erdleitung_m` anpassen.

## Was Andreas parallel erledigen kann

- BzA-Portal-URL und KfW-Zuschussportal-URL in die Projektierungs-
  Einstellungen; BzA-Mailtext gegenlesen.
- Heizreport: Anfrage an den Support mit dem Text aus `docs/heizreport-api.md`
  (API-Zugang, Doku, Testkonto).
- Collin: Kundennummer, Ansprechpartner für den UGL-Test; Testdatei aus
  `docs/ugl-beispiel.ugl` senden; Lieferanten-Artikelnummern für die
  wichtigsten Positionen (WP-Pakete 045–056, Puffer, Speicher, Elektro) in die
  Stücklisten-Pflege eintragen.
- Vorlauf-Schwellen (8/4 Wochen) und die Pflichtigkeit von „Montageteam
  zuweisen" nach zwei Wochen Praxis prüfen.
