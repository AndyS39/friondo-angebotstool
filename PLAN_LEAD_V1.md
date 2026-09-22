# PLAN_LEAD_V1 – Lead-Management, Ausbaustufe 1 „Fundament & Terminassistent" (Demo, nur Admin)

Grundlage: `LEADMANAGEMENT-KONZEPT.md` (Abschnitte 2–10, 16). Dieser Plan wird von
Claude Code auf dem Entwicklungs-PC umgesetzt. Reihenfolge der Phasen einhalten;
jede Phase endet mit einem lokalen Test und einem Commit. `CLAUDE.md` und
`konfigurator_logik_v5.xlsx` nie ersetzen – nur die in Phase 82 beschriebenen
Ergänzungen anhängen.

**Drei Leitplanken dieses Plans (Entscheidung Andreas, 22.09.2026):**

1. **Demo-Modus.** Das gesamte Modul liegt hinter dem Parameter
   `lead_freigabe_modus = admin` (Standard). Nur Admins sehen und erreichen es –
   server-seitig geprüft, nicht nur im Menü ausgeblendet. Alle anderen Rollen
   sehen das Tool exakt wie heute.
2. **monday läuft unverändert weiter.** Lesesync (Gruppe „Terminiert") und
   Rückspielung (Status + Deal-Wert) werden **nicht** angefasst. Das Modul liest
   die gesyncten Vorgänge nur mit und leitet ihre Lead-Phase ab. Kein Import
   anderer Gruppen, kein Parallelbetrieb, keine Schreibzugriffe – das kommt in
   PLAN_LEAD_V2 nach Freigabe der Demo.
3. **Keine Nebenwirkungen nach außen.** Im Demo-Modus werden keine Mails an
   Kunden gesendet (Sendesperre `mail_modus = protokoll`), keine Termine in echte
   Außendienst-Kalender geschrieben (`kalender_sync = aus`), und Leads, die im
   Modul entstehen, tragen `demo = 1` und tauchen **nirgends** außerhalb des
   Moduls auf (nicht in Leads VOT, Erfassungen, Angeboten, Statistik, Kacheln,
   monday). Alle Sperren fallen erst mit `lead_freigabe_modus = alle`.

**Start-Prompt für Claude Code (kopieren):**

> Lies `CLAUDE.md`, `LEADMANAGEMENT-KONZEPT.md` und `PLAN_LEAD_V1.md`
> vollständig. Verschaffe dir einen Überblick über die vorhandene Struktur
> (Routen, Modelle/Tabellen, Templates, migrate.py, Rollenprüfung, Startportal,
> Vorgangsakte v10, monday-Sync und -Rückspielung, Graph-Versand und -Abruf,
> Vorlagen-Editor, Statistik, mobile Erfassungswelt). Prüfe, ob PLAN_PROJ_V1
> bereits ganz oder teilweise umgesetzt ist (Tabellen `benachrichtigungen`,
> `teams`, Mehrfachrollen, Glocke, Kanban-Komponente) – Vorhandenes
> wiederverwenden, Fehlendes exakt in der dort beschriebenen Struktur anlegen,
> damit PLAN_PROJ_V1 später darauf aufsetzt. Setze dann Phase 73 um. Erzeuge
> alle Datenbank-Änderungen ausschließlich als idempotente Schritte in
> migrate.py (neue Spalten nullable). Ändere bestehende Funktionen nur dort, wo
> der Plan es ausdrücklich verlangt (Liste in Phase 73), und nie den
> monday-Sync oder die Rückspielung. Nach jeder Phase: kurze Zusammenfassung,
> was gebaut wurde, welche Dateien betroffen sind und wie ich es lokal als
> Admin teste. Stelle Rückfragen nur bei echten Widersprüchen zum bestehenden
> Code – sonst entscheide im Sinne des Konzepts und notiere die Entscheidung in
> `docs/leadmanagement-entscheidungen.md`.

Nach jeder Phase an Claude Code: „Phase X ist getestet, weiter mit Phase X+1."

**Nummerierung:** PLAN_PROJ_V1 belegt die Phasen 64–72; dieser Plan belegt
**73–82**. Beide Module liegen hinter eigenen Admin-Schaltern und dürfen
deshalb parallel entwickelt werden; gemeinsame Bausteine (Mehrfachrollen,
Benachrichtigungen, Kanban, Graph-Kalender) werden vom Plan gebaut, der sie
zuerst braucht, und vom anderen wiederverwendet. Rollouts auf den
Terminal-Server weiterhin nacheinander (update.bat).

---

## Phase 73 – Datenmodell, Demo-Schalter, Rolle, abgeleitete Lead-Phase

- [x] Neue Tabellen (alle mit `id`, `erstellt_am`, `erstellt_von`, `geaendert_am`):
  - `lead_quellen`: `key` (eindeutig), `name`, `typ` (website / landingpage / portal /
    partner / telefon / empfehlung / bestand / monday), `kanal` (Wert der bestehenden
    Vertriebskanal-Liste, nullable), `kosten_je_lead` (Decimal, nullable),
    `standard_sparten` (JSON-Liste WP/PV/KL/WB), `score_bonus` (int, Standard 0),
    `parser_regel_id` (nullable), `aktiv`.
  - `kampagnen`: `name`, `quelle_id`, `von`, `bis`, `budget`, `utm_campaign`, `aktiv`.
  - `lead_aktivitaeten`: `vorgang_id`, `typ` (anruf / mail_aus / mail_ein / sms / notiz /
    status / termin / system / import), `ergebnis` (erreicht / nicht_erreicht / besetzt /
    mailbox / rueckruf_gewuenscht / falsche_nummer / kein_interesse, nullable), `text`,
    `dauer_sek` (nullable), `benutzer_id`, `zeitpunkt`, `naechste_aktion_am` (nullable).
    **Bestehende Notizen-Chat-Einträge (v10) bleiben in ihrer Tabelle**; die Timeline
    liest beide Tabellen zusammen (Union nach Zeit). Kein Umzug alter Daten.
  - `lead_qualifizierung`: `vorgang_id`, `sparte`, `antworten` (JSON `{frage_key: wert}`),
    `score_punkte`, `score_klasse` (A/B/C), `abgeschlossen_am`, `benutzer_id`.
  - `vot_termine`: `vorgang_id`, `ad_id`, `beginn`, `ende`, `adresse`, `lat`, `lon`,
    `status` (geplant / bestaetigt / verschoben / no_show / erfolgt / abgesagt),
    `outlook_event_id` (nullable), `bestaetigung_am`, `erinnerung_am`, `fahrzeit_hin_min`,
    `umweg_min`, `quelle` (assistent / manuell / monday), `grund_text`, `demo` (bool).
  - `ad_profile`: `benutzer_id` (eindeutig), `start_adresse`, `start_lat`, `start_lon`,
    `arbeitszeiten` (JSON je Wochentag `{"mo":["08:00","18:00"], …}`), `termin_dauer_min`
    (Standard 90), `puffer_min` (15), `max_termine_tag` (4), `gebiet_plz_praefixe`
    (JSON-Liste), `kalender_postfach` (nullable), `aktiv_terminierung` (bool).
  - `kommunikation_log`: `vorgang_id`, `termin_id` (nullable), `kanal` (mail), `vorlage_key`,
    `an`, `betreff`, `body_html`, `anhang_pfad` (nullable), `geplant_am`, `gesendet_am`
    (nullable), `status` (geplant / protokolliert / gesendet / fehler), `fehler_text`,
    `modus` (protokoll / test / live).
  - `parser_regeln`: `name`, `quelle_id`, `absender_muster`, `betreff_muster`,
    `format` (zeilen / html_tabelle / json), `feldzuordnung` (JSON: Feldname in der Mail →
    Lead-Feld), `aktiv`, `zuletzt_getroffen_am`.
  - `geocode_cache`: `adresse_norm` (eindeutig), `lat`, `lon`, `anbieter`, `stand`,
    `status` (ok / fehler).
  - `routing_cache`: `von_key`, `nach_key` (gerundete Koordinaten, 4 Nachkommastellen),
    `minuten`, `km`, `anbieter`, `gueltig_bis`. Eindeutig über (`von_key`, `nach_key`).
  - `lead_parameter`: Key-Value. Startwerte: `lead_freigabe_modus=admin`,
    `mail_modus=protokoll`, `mail_testadresse=` (leer), `parser_modus=aus`,
    `kalender_sync=aus`, `kalender_testpostfach=` (leer), `routing_anbieter=luftlinie`
    (ors / google / luftlinie), `ors_api_key=`, `google_api_key=`, `sla_gruen_min=30`,
    `sla_gelb_min=60`, `vorschlag_horizont_tage=14`, `vorschlag_raster_min=30`,
    `absender_postfach=leads@friondo.de`, `loeschlauf=aus`, `loeschfrist_monate=12`,
    `kerngebiet_plz=` (kommagetrennte Präfixe, z. B. `47,46,45,41`), `zuweisung_lm=round_robin`,
    `arbeitszeit_lm=08:00-17:00`, `demo_badge_text=Demo · Coming soon`.
- [x] `vorgaenge` erweitern (alle nullable, idempotent): `lead_phase`, `quelle_id`, `kampagne_id`,
  `utm_source`, `utm_medium`, `utm_campaign`, `utm_content`, `eingang_am`, `eingang_art`
  (mail / import / api / manuell / monday / trigger), `anfrage_text`, `anfrage_rohdaten` (JSON),
  `erstkontakt_am`, `erreicht_am`, `terminiert_am`, `leadmanager_id`, `score_punkte`,
  `score_klasse`, `wunschzeiten` (JSON), `lat`, `lon`, `geocode_status`,
  `einwilligung_werbung` (bool), `einwilligung_werbung_am`, `einwilligung_quelle`,
  `zurueckgestellt_bis`, `zurueckgestellt_grund`, `unqualifiziert_grund`,
  `unqualifiziert_text`, `versuch_nr` (int, Standard 0), `naechste_aktion_am`,
  `loeschen_am`, **`demo` (bool, Standard 0)**.
- [x] Gemeinsame Bausteine mit PLAN_PROJ_V1 (nur anlegen, wenn nicht vorhanden – exakt
  wie dort beschrieben): Mehrfachrollen an `benutzer.rollen`, Tabelle
  `benachrichtigungen` (`benutzer_id`, `text`, `link`, `gelesen_am`, `art`) und die
  Glocke in der Kopfzeile (Phase 69 dort). Neue Rolle **`leadmanagement`** in der
  Rollenliste; in der Benutzerverwaltung wählbar (Mehrfachrolle). Neue Felder
  `benutzer.lm_arbeitszeit` (nullable) und `benutzer.lm_aktiv` (bool, für Round-Robin).
- [x] **Demo-Schalter, server-seitig:** Hilfsfunktion `lead_modul_sichtbar(benutzer)` =
  `lead_freigabe_modus == 'alle'` **oder** Benutzer ist Admin. Alle Routen unter
  `/leads` und `/api/leads`, alle neuen Menüpunkte, Reiter, Blöcke und Kacheln prüfen
  sie. Bei `admin`-Modus liefern die Routen für Nicht-Admins 404 (nicht 403 – das
  Modul soll unsichtbar sein).
- [x] **Demo-Kennzeichen:** Jeder Vorgang, der im Modul angelegt wird (Schnellanlage,
  Import, API, Parser, Demo-Generator), erhält `demo = 1`, solange
  `lead_freigabe_modus = admin`. Zentrale Abfragefunktion `ohne_demo(query)` wird in
  **allen bestehenden** Listen, Kacheln, Statistiken, im Leads-VOT-Filter, in der
  Kundenliste, in der Angebotsliste und in der monday-Rückspielung angewandt (Demo-
  Vorgänge existieren dort nicht). Innerhalb des Moduls: Badge „Demo" (gelb) an
  jedem Demo-Lead. Umstellung auf `alle`: Dialog in der Parametrierung listet alle
  Demo-Leads mit Auswahl „Alle löschen" (Standard) oder „Behalten und Kennzeichen
  entfernen" (nur für Admin, protokolliert).
- [x] **Abgeleitete Lead-Phase für bestehende Vorgänge** (Funktion
  `lead_phase_berechnen(vorgang)`, nach jedem monday-Sync-Lauf und bei jeder
  Änderung an Erfassung/Angebot/Termin aufgerufen; **schreibt nur `vorgaenge.lead_phase`**,
  nie nach monday): Angebot angenommen → `gewonnen`; alle Angebote abgelehnt/keins mehr
  offen und mind. eins vorhanden → `verloren`; Angebot versendet → `angebot`; Erfassung
  vorhanden → `erfasst`; VOT-Datum vorhanden (monday) oder aktiver `vot_termine`-Eintrag →
  `terminiert`; Qualifizierung abgeschlossen → `qualifiziert`; `versuch_nr ≥ 1` →
  `in_kontaktierung`; sonst `neu`. Manuelle Zustände `zurueckgestellt`, `nicht_erreicht`,
  `unqualifiziert` haben Vorrang, bis sie aufgehoben werden. Für gesyncte Vorgänge:
  `eingang_art = monday`, `eingang_am` = erster Sync-Zeitpunkt (falls unbekannt:
  `erstellt_am`), Quelle = automatisch angelegte Quelle `monday_<board>` (Typ monday,
  Kanal aus dem bestehenden Board-Mapping). Badge „monday" an diesen Leads.
- [x] **Liste der erlaubten Änderungen an bestehenden Funktionen** (sonst nichts):
  (1) `vorgaenge` neue Spalten; (2) Startportal-Karte „Lead-Management": für Admins
  im Demo-Modus zusätzliche Kacheln + Badge (Phase 79), für alle anderen unverändert;
  (3) Vorgangsakte: neuer Kopfblock und neue Reiter, nur bei `lead_modul_sichtbar`;
  (4) Statistik: neuer Reiter „Leads" (Phase 80), nur bei `lead_modul_sichtbar`;
  (5) Menü: neue Einträge, nur bei `lead_modul_sichtbar`; (6) Benutzerverwaltung:
  Rolle `leadmanagement`, Felder `lm_aktiv`/`lm_arbeitszeit`, Unterseite AD-Profil;
  (7) Parametrierung: neuer Bereich „Lead-Management"; (8) `ohne_demo()` in den
  genannten bestehenden Abfragen; (9) Aufruf `lead_phase_berechnen` am Ende des
  Sync-Laufs und an den Statuswechseln von Erfassung/Angebot (nur Aufruf, keine
  Logikänderung); (10) Erfassungsbogen-Vorbelegung (Phase 76) – **erst aktiv bei
  `lead_freigabe_modus = alle`**.
- [x] Test: migrate.py zweimal ausführen → keine Fehler, keine doppelten Spalten.
  Als Innendienst/Außendienst anmelden → nichts Neues sichtbar, `/leads` liefert 404.
  Als Admin → Menüpunkt „Lead-Management (Demo)" sichtbar. Sync-Lauf → bestehende
  Vorgänge tragen eine plausible `lead_phase`.

## Phase 74 – Steuerdatei `leadmanagement_logik_v1.xlsx` + Import

- [x] Datei anlegen (Repo-Ordner wie `konfigurator_logik_v5.xlsx`) mit Blättern:
  - **Qualifizierung**: `sparte`, `frage_key`, `frage`, `typ` (janein / auswahl / mehrfach /
    zahl / text), `optionen` (mit `|` getrennt), `pflicht` (J/N), `reihenfolge`,
    `erfassungs_frage` (Frage-Key des bestehenden Erfassungsbogens aus
    `konfigurator_logik_v5.xlsx`, Blatt „Fragen", **nur wo die Frage inhaltlich identisch
    ist** – Claude Code füllt die Spalte beim Anlegen anhand der vorhandenen Fragen-Keys;
    nicht zuordenbare bleiben leer), `unqualifiziert_bei` (Wert, der den Hinweis
    „Unqualifiziert?" auslöst, optional).
  - **Scoring**: `frage_key`, `bedingung` (`=Wert`, `>N`, `>=N`, `<N`, `enthält Wert`),
    `punkte`, `bemerkung`.
  - **Klassen**: `klasse`, `ab_punkte` (A 60, B 35, C 0).
  - **Kaskade**: `versuch_nr`, `wiedervorlage_nach` (`+2h`, `+1d 18:00`, `+3d`, `+7d`),
    `aktion` (keine / mail_nicht_erreicht), `letzter` (J/N).
  - **Gruende**: `phase` (unqualifiziert / zurueckgestellt / no_show / verloren_vor_termin),
    `grund`, `freitext_pflicht` (J/N).
  - **Wunschzeiten**: `key`, `bezeichnung`, `von`, `bis`, `wochentage` (`mo-fr`, `sa`).
- [x] Startinhalt **Qualifizierung WP** (Reihenfolge 1–14; Andreas passt später in der Excel an):
  Q-W01 „Sind Sie Eigentümer des Gebäudes?" janein, Pflicht, unqualifiziert_bei = nein ·
  Q-W02 „Gebäudetyp" auswahl `Einfamilienhaus|Doppelhaushälfte|Reihenhaus|Mehrfamilienhaus|Gewerbe`, Pflicht ·
  Q-W03 „Baujahr des Gebäudes" zahl · Q-W04 „Beheizte Wohnfläche (m²)" zahl ·
  Q-W05 „Aktuelle Heizung" auswahl `Öl|Gas|Nachtspeicher|Pellets|Fernwärme|Sonstiges`, Pflicht ·
  Q-W06 „Baujahr der Heizung" zahl · Q-W07 „Jahresverbrauch (kWh Gas bzw. Liter Öl)" zahl, Pflicht ·
  Q-W08 „Warmwasser über die Heizung?" janein · Q-W09 „Wärmeabgabe" auswahl
  `Heizkörper|Fußbodenheizung|gemischt` · Q-W10 „Zeitrahmen" auswahl
  `sofort|innerhalb 3 Monate|innerhalb 6 Monate|später als 6 Monate|unklar`, Pflicht ·
  Q-W11 „Förderung (KfW) bekannt/gewünscht?" auswahl `ja|nein|unklar` ·
  Q-W12 „Sind alle Entscheider beim Termin anwesend?" janein ·
  Q-W13 „Wunschzeiten" mehrfach `vormittags|nachmittags|abends|samstag`, Pflicht ·
  Q-W14 „Zusätzliches Interesse" mehrfach `PV|Klima|Wallbox|Speicher`.
- [x] Startinhalt **PV**: Q-P01 Eigentümer (janein, Pflicht, unqualifiziert_bei nein) · Q-P02 Gebäudetyp
  (wie W02) · Q-P03 „Dachform" `Satteldach|Flachdach|Walmdach|Pultdach` · Q-P04 „Dachausrichtung"
  `Süd|Südost/Südwest|Ost/West|Nord|unklar` · Q-P05 „Freie Dachfläche ca. (m²)" zahl ·
  Q-P06 „Dacheindeckung" `Ziegel|Blech|Bitumen|Schiefer|Sonstiges` · Q-P07 „Stromverbrauch
  (kWh/Jahr)" zahl, Pflicht · Q-P08 „Speicher gewünscht?" `ja|nein|unklar` · Q-P09
  „Wallbox/E-Auto" `vorhanden|geplant|nein` · Q-P10 Zeitrahmen (wie W10, Pflicht) · Q-P11
  Entscheider (wie W12) · Q-P12 Wunschzeiten (wie W13, Pflicht).
  **KL**: Q-K01 Eigentümer · Q-K02 „Anzahl zu klimatisierende Räume" zahl, Pflicht ·
  Q-K03 „Gesamtfläche der Räume (m²)" zahl · Q-K04 „Platz für Außengerät vorhanden?"
  `ja|nein|unklar` · Q-K05 Zeitrahmen · Q-K06 Wunschzeiten.
  **WB**: Q-B01 „Eigener Stellplatz/Garage?" janein, Pflicht · Q-B02 „E-Fahrzeug"
  `vorhanden|bestellt|geplant` · Q-B03 „Entfernung Zählerschrank ↔ Stellplatz (m)" zahl ·
  Q-B04 „PV vorhanden/geplant?" `vorhanden|geplant|nein` · Q-B05 Zeitrahmen · Q-B06 Wunschzeiten.
- [x] Startinhalt **Scoring** (Punkte, Platzhalter): Q-W01 `=nein` −100 · Q-W05 `=Öl` +20 ·
  Q-W05 `=Gas` +10 · Q-W05 `=Nachtspeicher` +15 · Q-W06 `<2005` +15 · Q-W06 `<2013` +5 ·
  Q-W07 `>20000` +10 · Q-W10 `=sofort` +25 · `=innerhalb 3 Monate` +20 ·
  `=innerhalb 6 Monate` +10 · Q-W11 `=ja` +5 · Q-W12 `=ja` +10 · Q-W12 `=nein` −10 ·
  Q-W14 `enthält PV` +5 · Q-P01 `=nein` −100 · Q-P04 `=Süd` +15 · `=Südost/Südwest` +10 ·
  Q-P07 `>4000` +10 · Q-P08 `=ja` +10 · Q-P09 `=vorhanden` +10 · Q-P10 wie W10 ·
  Q-K05/Q-B05 wie W10. **Systemregeln** (im Code, nicht in der Excel): PLZ-Präfix in
  `kerngebiet_plz` +10; `lead_quellen.score_bonus` addieren.
- [x] Startinhalt **Kaskade**: 1 → `+2h`, keine · 2 → `+1d 18:00`, mail_nicht_erreicht ·
  3 → `+3d`, keine · 4 → `+7d`, mail_nicht_erreicht, letzter = J (danach Phase
  „Nicht erreicht", Wiedervorlage +30 Tage, Aktion mail_nurture).
- [x] Startinhalt **Gruende**: unqualifiziert: Mieter/kein Eigentümer · außerhalb
  Vertriebsgebiet · kein Bedarf, nur Information · Budget/Finanzierung · technisch nicht
  geeignet · Doppelter · Spam/Fehleingabe · Sonstiges (Freitext Pflicht) ·
  zurueckgestellt: Kunde meldet sich selbst · Bauphase später · Förderung/Finanzierung
  abwarten · Sonstiges (Pflicht) · no_show: Kunde nicht angetroffen · Kunde hat kurzfristig
  abgesagt · Außendienst verhindert · Sonstiges (Pflicht) · verloren_vor_termin:
  Wettbewerber · Preiserwartung · keine Reaktion mehr · Sonstiges (Pflicht).
- [x] Startinhalt **Wunschzeiten**: vormittags 08:00–12:00 mo-fr · nachmittags 12:00–17:00
  mo-fr · abends 17:00–20:00 mo-fr · samstag 09:00–14:00 sa.
- [x] Import in der Parametrierung: Bereich **„Lead-Management → Steuerdatei"** mit Upload
  (wie Logik-Import), Anzeige der Blätter als Tabellen, Versionsstand, Prüfung: unbekannte
  `erfassungs_frage`-Keys werden als Warnung gelistet. Änderungen wirken auf neue
  Qualifizierungen; abgeschlossene bleiben mit ihren Antworten.
- [x] Test: Import läuft, alle Blätter sichtbar, doppelter Import ohne Dubletten,
  Warnung bei falschem Key.

## Phase 75 – Lead-Eingang: Quellen, Schnellanlage, Import, API, Parser, Duplikate, Demo-Daten

- [x] **Parametrierung → Lead-Management → Quellen & Kampagnen**: Tabellenpflege mit den
  Feldern aus Phase 73. Startquellen anlegen: `website` (Website/Förderrechner, Typ
  website), `landingpage` (Typ landingpage), `portal` (Lead-Portal, Typ portal),
  `partner_enni`, `partner_swd`, `partner_sparkasse_du` (Typ partner, Kanal = der
  jeweilige bestehende Kanalwert), `telefon`, `empfehlung`, `bestand`. Die
  `monday_<board>`-Quellen entstehen automatisch (Phase 73).
- [x] **Schnellanlage** `/leads/neu` (auch mobil): Anrede, Vorname, Nachname (Pflicht),
  Telefon (Pflicht, sonst E-Mail Pflicht), E-Mail, Straße, PLZ (Pflicht), Ort, Sparten
  (Mehrfach, Pflicht), Quelle (Pflicht, Dropdown), Kampagne, Wunschzeiten, Notiz/
  Anfragetext. Anlage = Kunde (bestehender Duplikatabgleich Name + PLZ) + Vorgang
  (`eingang_art = manuell`, `eingang_am = jetzt`, `lead_phase = neu`, Interessen aus
  Sparten) + Aktivität „Lead angelegt (manuell)" + Geokodierung im Hintergrund +
  Zuweisung Leadmanager (Round-Robin über `lm_aktiv`-Benutzer; Admin ohne aktive
  Leadmanager → sich selbst) + Benachrichtigung an den Leadmanager.
- [x] **Duplikatprüfung** (Funktion `duplikat_pruefen(telefon, email, name, plz, adresse)`):
  Telefon normalisiert auf E.164 (+49…), E-Mail klein, Name + PLZ, Straße + PLZ. Treffer
  → im Anlage-Dialog Hinweis „Möglicher Doppelter: <Name>, <Ort>, Vorgang <Phase>" mit
  Wahl „An bestehenden Vorgang anhängen (neue Sparte)" (Standard, wenn der Vorgang
  offen ist) oder „Eigenen Vorgang anlegen". Bei automatischen Eingängen (Import/API/
  Parser): offener Vorgang → anhängen + Aktivität „Neue Anfrage <Quelle> angehängt";
  abgeschlossener Vorgang → neuer Vorgang mit Badge „Wiederkehrer"; kein Treffer → neu.
- [x] **CSV/Excel-Import** `/leads/import`: Upload, Spaltenzuordnung per Dropdown
  (Zuordnung je Quelle speicherbar), Vorschau der ersten 20 Zeilen mit Duplikat-
  Markierung, Quelle/Kampagne/Sparten für die Datei, Import-Protokoll (angelegt /
  angehängt / übersprungen mit Grund). `eingang_art = import`.
- [x] **REST-Endpunkt** `POST /api/leads` (JSON: `quelle`, `kampagne`, `anrede`, `vorname`,
  `nachname`, `strasse`, `plz`, `ort`, `telefon`, `email`, `sparten` [Liste], `wunschzeiten`
  [Liste], `nachricht`, `utm_*`, `einwilligung_werbung` bool, `rohdaten` beliebig).
  Auth über Header `X-Api-Key` (Schlüssel je Quelle in der Parametrierung erzeugbar).
  Antwort 201 mit Vorgangs-ID; 409 bei Duplikat-Anhängung (mit ID); 422 bei fehlenden
  Pflichtfeldern. Rate-Limit 60/min. Doku in `docs/leads-api.md` mit curl-Beispiel.
- [x] **Mail-Parser**: Tabelle `parser_regeln` in der Parametrierung pflegen; **Test-
  Funktion**: Beispiel-Mail (Betreff + Body) einfügen → Anzeige der erkannten Felder
  ohne Anlage. Formate: `zeilen` (`Feld: Wert` je Zeile), `html_tabelle` (2-spaltig),
  `json` (Anhang oder Body). Standardregel „Formular-Standard" anlegen: Betreff
  `[LEAD] <quelle> <kampagne>`, Body `Feld: Wert` mit den Feldnamen der API. Abruf des
  Postfachs `absender_postfach` über die bestehende Graph-Abrufstrecke alle 2 Minuten,
  **nur wenn `parser_modus = an`** (Standard aus). Erkannte Mails → Lead
  (`eingang_art = mail`, Original als `anfrage_text`/`anfrage_rohdaten`); nicht erkannte
  → Liste **„Posteingang unklar"** `/leads/posteingang` (Absender, Betreff, Vorschau,
  Button „Als Lead anlegen" mit vorbefülltem Schnellanlage-Formular, Button „Ignorieren").
- [x] **SLA**: `sla_status` berechnet, nicht gespeichert: Minuten seit `eingang_am` innerhalb
  `arbeitszeit_lm` (Mo–Fr) bis `erstkontakt_am`; grün < `sla_gruen_min`, gelb <
  `sla_gelb_min`, rot darüber; nach erstem Versuch „erfüllt (n Min)". Anzeige als Chip
  mit laufender Minutenzahl.
- [x] **Benachrichtigung** bei jedem Eingang an den zugewiesenen Leadmanager (Glocke:
  „Neuer Lead: <Name>, <Ort> – <Sparten> – <Quelle>", Link zur Akte); ohne Zuweisung an
  alle Benutzer mit Rolle leadmanagement bzw. Admins.
- [x] **Demo-Daten-Generator** (Parametrierung, nur Admin, nur im Demo-Modus): Button
  „25 Demo-Leads erzeugen" – fiktive Namen (kein Bezug zu echten Personen), reale
  Straßen-/Ortsnamen aus Duisburg, Moers, Oberhausen, Mülheim, Dinslaken, Krefeld ohne
  Hausnummern-Bezug, Telefon `0203 000 xx`, verteilt über Quellen, Sparten, Phasen
  (10 neu, 6 in Kontaktierung mit Versuchen, 5 qualifiziert, 4 terminiert mit
  `vot_termine` in den nächsten 10 Werktagen, verteilt auf die vorhandenen AD) und
  Eingangszeiten der letzten 14 Tage; alle mit `demo = 1`. Button „Alle Demo-Leads
  löschen" (mit Sicherheitsabfrage, löscht Vorgänge, Kunden ohne andere Vorgänge,
  Aktivitäten, Termine, Log).
- [x] Test: Schnellanlage mit Duplikat → Anhängen; CSV mit 10 Zeilen; `curl` gegen die API;
  Parser-Test mit Beispiel-Mail; Demo-Generator → 25 Leads sichtbar **nur** im Modul,
  nicht in Leads VOT/Kunden/Angebote/Statistik (als Innendienst prüfen).

## Phase 76 – Anrufliste, Aktivitäten, Kaskade, Qualifizierung, Score

- [ ] **Anrufliste** `/leads` (Startseite des Moduls): Reihenfolge (1) SLA gelb/rot, älteste
  zuerst · (2) fällige `naechste_aktion_am` und Rückrufwünsche · (3) Zurückgestellte mit
  erreichtem Datum · (4) übrige Neue/In Kontaktierung nach Score-Klasse, dann Eingang.
  Zeile: Name, Ort (PLZ), Sparten-Chips, Quelle-Badge, Badges „monday"/„Demo"/„Wiederkehrer",
  Score-Klasse, SLA-Chip, Versuch-Nr., letztes Ergebnis + Zeit, Telefon als `tel:`-Link,
  **Ergebnis-Buttons** in der Zeile. Filter: Meine/Alle, Quelle, Sparte, Klasse,
  PLZ-Präfix, Phase; Suche Name/Telefon/Ort. Klick auf den Namen öffnet die Akte als
  Seitenpanel (rechts, ohne Seitenwechsel), Vollansicht per Link.
- [ ] **Ergebnis-Buttons** (ein Klick, Aktivität `anruf` mit Ergebnis): Erreicht → öffnet den
  Qualifizierungsbogen · Nicht erreicht · Besetzt · Mailbox → Kaskade · Rückruf gewünscht →
  Dialog Datum/Uhrzeit Pflicht, setzt `naechste_aktion_am` · Falsche Nummer → Hinweis, Lead
  bleibt mit Kennzeichen „Nummer prüfen" · Kein Interesse → Grund-Dialog (Liste
  `unqualifiziert` + Freitext) → Phase `unqualifiziert`. Jeder Klick setzt
  `erstkontakt_am` (falls leer), erhöht `versuch_nr`, setzt `lead_phase` auf
  `in_kontaktierung`; Erreicht setzt `erreicht_am`. Tastaturkürzel 1–7 im Seitenpanel.
- [ ] **Kaskade**: nach Nicht erreicht/Besetzt/Mailbox wird `naechste_aktion_am` aus dem
  Blatt Kaskade gesetzt (`+2h` = jetzt + 2 h innerhalb `arbeitszeit_lm`, sonst nächster
  Arbeitsbeginn; `+1d 18:00` = nächster Werktag 18:00 – liegt 18:00 außerhalb der
  Arbeitszeit, gilt Arbeitsende); Aktion `mail_nicht_erreicht` legt einen Eintrag in
  `kommunikation_log` an (Phase 78 verarbeitet ihn). Nach dem letzten Versuch: Phase
  `nicht_erreicht`, `naechste_aktion_am` = +30 Tage, Aktion `mail_nurture`. Manuelles
  „Erneut aktivieren" setzt zurück auf `in_kontaktierung`.
- [ ] **Zurückstellen** (Dialog Datum Pflicht + Grund aus Liste): Phase `zurueckgestellt`,
  `zurueckgestellt_bis`; täglicher Lauf 07:00 setzt fällige zurück auf `neu` mit Aktivität
  „Wiedervorlage fällig" und Benachrichtigung. **Unqualifiziert** (Dialog Grund Pflicht):
  Phase `unqualifiziert`; Button „Reaktivieren" (Begründung) → `neu`.
- [ ] **Qualifizierungsbogen** `/leads/<id>/qualifizierung/<sparte>`: Fragen des Blatts
  Qualifizierung als Gesprächsleitfaden (eine Frage je Block, große Buttons, Enter =
  weiter, Rücksprung möglich, Fortschrittsbalken); Sparten-Reiter, wenn der Lead mehrere
  Interessen hat (gemeinsame Fragen wie Eigentümer/Zeitrahmen/Wunschzeiten werden nur
  einmal gefragt und in alle Sparten übernommen). Live-Score rechts oben (Punkte +
  Klasse). `unqualifiziert_bei` getroffen → Hinweisbalken „Antwort spricht gegen einen
  Termin – als unqualifiziert kennzeichnen?" (Button, kein Zwang). Abschluss speichert
  `lead_qualifizierung`, setzt `lead_phase = qualifiziert`, Wunschzeiten an den Vorgang,
  Zusatzinteressen (Q-W14) als Interessen, Aktivität „Qualifiziert (<Klasse>, <Punkte>)".
  Abschluss-Seite: Buttons **„Termin vorschlagen"** (Phase 77), „Zurückstellen",
  „Unqualifiziert", „Später weiter".
- [ ] **Score-Berechnung** `score_berechnen(vorgang)`: Summe aus Blatt Scoring über alle
  Sparten-Antworten (je Frage nur die erste zutreffende Zeile), + Systemregeln
  (Kerngebiet, Quellen-Bonus); Klasse aus Blatt Klassen; vorläufiger Score bereits bei
  Anlage (nur Systemregeln), Anzeige „vorläufig" bis zur Qualifizierung.
- [ ] **Erfassungs-Vorbelegung** (vorbereiten, **erst aktiv bei `lead_freigabe_modus = alle`**):
  Beim Start einer Erfassung zu einem Vorgang mit abgeschlossener Qualifizierung werden
  Antworten über `erfassungs_frage` vorbelegt und je Antwort mit Kennzeichen „aus
  Qualifizierung" markiert (Tooltip mit Datum/Leadmanager); der AD kann sie ändern. Im
  Demo-Modus nur im Code vorhanden, Test über Unit-Test der Mapping-Funktion.
- [ ] Test: 10 Demo-Leads durch die Liste arbeiten; Kaskade-Zeiten stimmen (auch abends/
  Freitag → Montag); Qualifizierung WP + PV am selben Lead; Score-Klasse ändert sich
  live; Kein Interesse → unqualifiziert; Zurückstellen → Wiedervorlage-Lauf manuell
  anstoßen.

## Phase 77 – Geocoding, Routing, AD-Profile, Terminassistent, Kalender

- [ ] **Geocoding** (`geocoding.py`): Adresse normalisieren → Cache → Anbieter laut
  `routing_anbieter` (ors: Geocode-Endpunkt mit `ors_api_key`; google: Geocoding API;
  luftlinie: Nominatim `https://nominatim.openstreetmap.org/search` mit User-Agent
  `Friondo-Tool/1.0 (info@friondo.de)`, **max. 1 Anfrage/s**, `countrycodes=de`).
  Hintergrund-Job alle 5 Minuten: offene Leads (Phasen neu … terminiert), Termine der
  nächsten 60 Tage, AD-Startadressen; Fehler → `geocode_status = fehler` und Liste
  **„Adresse prüfen"** `/leads/adressen` mit manueller Pin-Setzung auf der Karte
  (speichert lat/lon, Status `manuell`). Alle Aufrufe nach außen mit Timeout 8 s,
  Fehler nie blockierend.
- [ ] **Routing** (`routing.py`): `fahrzeit(von, nach)` → Cache (90 Tage) → Anbieter:
  ors Matrix (`/v2/matrix/driving-car`, Quellen × Ziele, `metrics: duration,distance`),
  google Route Matrix, sonst Luftlinie × 1,3 bei 45 km/h (Kennzeichen `geschaetzt`).
  Matrix-Aufrufe bündeln: je Assistenten-Lauf **ein** Aufruf Lead → alle relevanten
  Punkte (Termine im Horizont + Startadressen, ≤ 50) plus fehlende Nachbar-Paare in
  einem zweiten Aufruf; Ergebnisse in `routing_cache`. Parametrierung: Anbieter,
  Schlüssel, Button „Verbindung testen" (Fahrzeit Duisburg Hbf → Moers Bahnhof anzeigen),
  Tageszähler der externen Aufrufe.
- [ ] **AD-Profile** (Benutzerverwaltung, Unterseite je Außendienstler; auch für Admins
  mit AD-Rolle): Felder aus Phase 73; Startadresse wird geokodiert; Arbeitszeiten-Editor
  je Wochentag; Häkchen `aktiv_terminierung`. Ohne Profil nimmt der Assistent Standard
  (Mo–Fr 08:00–18:00, Start = Firmenadresse aus der Parametrierung, 90/15/4).
- [ ] **Kalender-Anbindung** (`kalender.py`, Graph): `frei_belegt(ad, von, bis)` liest
  `calendarView` des `kalender_postfach`; `termin_schreiben/aendern/loeschen(vot_termin)`
  legt Ereignis an (Betreff `VOT <Sparten> – <Nachname>, <Ort>`, Ort = Adresse, Body:
  Telefon, Anfragetext-Kurzfassung, Qualifizierungs-Steckbrief, Link zur Akte
  `http://192.168.35.4:8000/leads/<id>`). **Nur aktiv bei `kalender_sync = an`**; im
  Demo-Modus (`lead_freigabe_modus = admin`) wird ausschließlich in
  `kalender_testpostfach` geschrieben und gelesen – nie in echte AD-Kalender. Fehlende
  Berechtigung → Warnung in der Parametrierung, Assistent arbeitet nur mit Tool-Terminen.
  `docs/graph-einrichtung.md` ergänzen: `Calendars.ReadWrite` (Application) +
  Application Access Policy auf die AD-Postfächer und das Testpostfach (Aufgabe
  M365-Admin).
- [ ] **VOT-Termine der gesyncten Leads**: Beim Sync-Lauf wird aus dem VOT-Datum des
  monday-Leads ein `vot_termine`-Eintrag mit `quelle = monday`, `status = geplant`,
  Dauer laut AD-Profil erzeugt bzw. aktualisiert (nur lesend aus monday; Änderung in
  monday überschreibt den Tool-Eintrag, solange `quelle = monday`). Diese Termine sind
  die Grundlage, damit der Assistent in der Demo mit den echten Tagen der AD rechnet.
- [ ] **Terminassistent** `/leads/<id>/termin` (Button aus Akte, Anrufliste und
  Qualifizierungs-Abschluss): Vorschlagsmaschine laut Konzept 6.1 – Horizont
  `vorschlag_horizont_tage` Werktage, Raster `vorschlag_raster_min`, AD-Kandidaten
  (Kanal-Regel aus der Quelle → Gebiets-PLZ → alle mit `aktiv_terminierung`; manuell
  einschränkbar), Kalender frei (Tool-Termine + Graph, falls an), Termindauer + Puffer,
  Max/Tag, Umweg-Berechnung mit Vor-/Folgetermin bzw. Startadresse, Bewertung: Umweg-
  Minuten + Wunschzeit getroffen −30 · Tag hat Termine im Umkreis 10 km −15 · leerer Tag
  +20 · Slot vor 09:00 oder nach 17:00 +10 · Klasse A: Tage bis Termin × 2. Ausgabe
  **Top 5** als Karten: Datum/Uhrzeit, AD, Umweg („+12 Min", „geschätzt" bei
  Luftlinie), Begründungstext mit Vor-/Folgetermin (Name, Ort, Uhrzeit), Wunschzeit-
  Treffer, Mini-Karte (Phase 79-Komponente; in dieser Phase Platzhalter-Liste der
  Tagestermine). Reiter „Kalender": Wochenansicht des gewählten AD zum manuellen Setzen.
  Laufzeit-Ziel < 3 s; Fortschrittsanzeige bei externen Aufrufen.
- [ ] **Buchen** (im Demo-Modus nur für Demo-Leads aktiv; bei gesyncten monday-Leads
  zeigt der Assistent die Vorschläge, der Buchen-Button trägt den Hinweis „Terminierung
  im Demo-Modus nur für Demo-Leads – in monday terminieren"): `vot_termine`
  (`quelle = assistent`/`manuell`, `demo` vom Vorgang),
  `lead_phase = terminiert`, `terminiert_am`, AD am Vorgang setzen, Aktivität „Termin
  gebucht <Datum> bei <AD> (+<Umweg> Min)", Kalender-Ereignis (falls an), Terminbestätigung
  + Erinnerung als `kommunikation_log`-Einträge (Phase 78), Benachrichtigung an den AD
  (Glocke). **Umbuchen**: neuer Slot über den Assistenten, alter Termin `verschoben`,
  Kalender nachgezogen, Mail „Terminänderung". **No-Show / Absage** (Dialog Grund aus
  Liste `no_show`): Termin-Status, Phase zurück auf `qualifiziert`, `naechste_aktion_am` =
  jetzt, Benachrichtigung an den Leadmanager. **Erfolgt**: automatisch, wenn eine
  Erfassung zum Vorgang abgesendet wird, sonst manuell durch den AD.
- [ ] **Terminkalender** `/leads/kalender`: Wochenansicht, Spalten = AD (Filter einzelner
  AD), Einträge = `vot_termine` (Farbe je Sparte, Demo/monday-Badge) + bei `kalender_sync
  = an` die belegten Zeiten aus Outlook (grau). Drag & Drop eines Tool-Termins =
  Umbuchung mit Bestätigungsdialog; monday-Termine nicht verschiebbar (Hinweis „in monday
  ändern"). Klick → Akte.
- [ ] Test: Demo-Lead in Moers → Vorschläge liegen an Tagen, an denen der AD dort Termine
  hat; Umweg-Werte plausibel; ohne API-Key → „geschätzt"; Buchen → Termin im Kalender,
  Log-Einträge vorhanden; Umbuchen; No-Show → Lead zurück in Anrufliste. Als Innendienst:
  keine Demo-Termine in Leads VOT.

## Phase 78 – Kundenkommunikation (Mail) mit Sendesperre

- [ ] **Vorlagen** im bestehenden Vorlagen-Editor, neue Gruppe „Lead-Management" mit
  Schlüsseln `eingangsbestaetigung`, `nicht_erreicht`, `terminbestaetigung`,
  `terminerinnerung`, `terminaenderung`, `nurture`; je Vorlage Betreff + HTML-Text,
  optional je Sparte (Fallback allgemein). Platzhalter zusätzlich zu den bestehenden:
  `{sparten}`, `{quelle}`, `{termin_datum}`, `{termin_uhrzeit}`, `{termin_dauer}`,
  `{vertriebler}`, `{vertriebler_telefon}`, `{leadmanager}`, `{leadmanager_telefon}`,
  `{wunschzeiten}`, `{link_rueckruf}` (V1: mailto-Link mit vorausgefülltem Betreff
  „Rückruf <Vorgangs-Nr>"). Starttexte für alle sechs Vorlagen anlegen (sachlich,
  Sie-Form, Friondo-Signatur; Terminbestätigung mit Vorbereitungs-Liste: letzte
  Heizkostenabrechnung, Stromrechnung, Grundriss falls vorhanden, Zugang zum
  Heizungsraum/Zählerschrank).
- [ ] **Auslöser** → `kommunikation_log` (`status = geplant`): Eingang (sofort, nur wenn
  E-Mail vorhanden) · Kaskade-Aktionen · Buchen (Bestätigung sofort; Erinnerung
  `geplant_am` = Termin − 24 h) · Umbuchung · Nurture. ICS-Anhang bei Bestätigung/
  Änderung (`text/calendar`, METHOD:REQUEST, Organizer `absender_postfach`, Ort =
  Adresse). Kein Versand an Leads mit `einwilligung_werbung = 0` für `nurture`
  (Terminorganisation und Eingangsbestätigung sind von der Anfrage gedeckt).
- [ ] **Versand-Job** jede Minute: fällige Einträge verarbeiten nach `mail_modus`:
  `protokoll` → Mail rendern, als `status = protokolliert` speichern, **nicht senden**
  (Vorschau in der Akte); `test` → Versand über Graph an `mail_testadresse` mit Präfix
  „[TEST an <echte Adresse>]" im Betreff; `live` → Versand an den Kunden, Absender
  `absender_postfach` (Fallback angebot@ wie bei der Projektierung) – **`live` ist
  server-seitig nur zulässig bei `lead_freigabe_modus = alle`**, sonst wird der Wert beim
  Speichern abgewiesen. Fehler → `status = fehler`, Wiederholen-Button, nie blockierend.
- [ ] **Reiter „Kommunikation"** in der Akte: alle Log-Einträge mit Status, Vorschau
  (gerendertes HTML), Anhang, Button „Jetzt senden/erneut senden" (nach `mail_modus`),
  Button „Mail mit Vorlage" (Auswahl + Editierfeld vor dem Senden). Aktivität `mail_aus`
  je gesendeter/protokollierter Mail.
- [ ] **Antworten** (nur bei `parser_modus = an`): Mails im Postfach, die keine Parser-Regel
  treffen, aber per Konversations-ID oder Betreff „Rückruf <Vorgangs-Nr>"/`AN-C-…` einem
  Vorgang zuzuordnen sind, werden als Aktivität `mail_ein` an den Vorgang gehängt
  (Kurztext, Link auf die Mail), Benachrichtigung an den Leadmanager. Sonst „Posteingang
  unklar".
- [ ] Test: Buchen → Bestätigung und Erinnerung im Log als „protokolliert" mit korrektem
  ICS; `mail_modus = test` → Mail kommt an der Testadresse an; Versuch `live` im
  Demo-Modus → abgewiesen; Platzhalter alle gefüllt (keine `{…}` im Ergebnis).

## Phase 79 – Pipeline-Kanban, Lead-Akte, Karte, Startportal, Cockpit

- [ ] **Kanban** `/leads/board` (Kanban-Komponente aus PLAN_PROJ_V1 Phase 68 wiederverwenden,
  falls vorhanden; sonst hier bauen und für die Projektierung wiederverwendbar ablegen):
  Spalten Neu · In Kontaktierung · Qualifiziert · Terminiert · Erfasst · Angebot ·
  Gewonnen | Verloren (eingeklappt, letzte 30 Tage); Zurückgestellt / Nicht erreicht /
  Unqualifiziert per Filter-Häkchen. Karte = Vorgang: Name, Ort, Sparten-Chips,
  Quelle-Badge, Badges Demo/monday/Wiederkehrer, Score-Klasse, SLA-Chip (nur Neu),
  nächste Aktion + Fälligkeit (rot bei überfällig), Leadmanager-/AD-Kürzel, Termin-
  Datum (ab Terminiert). Drag & Drop nur: → Zurückgestellt (Dialog), → Unqualifiziert
  (Dialog), Zurückgestellt/Nicht erreicht/Unqualifiziert → Neu (Reaktivieren);
  alles andere mit Hinweis „über Anrufliste/Assistent". Filter wie Anrufliste + Zeitraum
  Eingang. Spaltenköpfe zeigen Anzahl und (ab Terminiert) Summe erwarteter Werte
  (Parameter `erwartungswert_<sparte>` in `lead_parameter`, Standard WP 30.000 €,
  PV 20.000 €, KL 8.000 €, WB 2.500 € brutto – Andreas korrigiert).
- [ ] **Lead-Akte** = bestehende Vorgangsakte (v10), erweitert (nur bei `lead_modul_sichtbar`):
  **Kopfblock „Lead"** (Quelle, Kampagne, Eingang am/Art, SLA, Score + Klasse mit
  Punkte-Aufschlüsselung als Tooltip, Leadmanager (änderbar), AD (änderbar), Phase mit
  Stepper, Wunschzeiten, Einwilligungen (Häkchen + Datum + Quelle), Badges) und
  Aktionsleiste (Anruf-Ergebnisse, Qualifizieren, Termin vorschlagen, Zurückstellen,
  Unqualifiziert, Mail mit Vorlage). Neue Reiter **vor** den bestehenden: **Aktivitäten**
  (Timeline = `lead_aktivitaeten` ∪ Notizen-Chat, chronologisch, Eingabefeld für Notiz
  bleibt der Notizen-Chat), **Qualifizierung** (Antworten je Sparte, Button „Bearbeiten"
  → Bogen, Änderungen protokolliert), **Termin** (aktiver Termin mit Umweg/AD/Status,
  Historie, Buttons Umbuchen/No-Show/Absagen/Erfolgt), **Kommunikation** (Phase 78).
  Bestehende Bereiche Erfassungen · Angebote · Mail-Verlauf · Projekt unverändert
  dahinter. Bei Demo-Leads: Bereich Erfassungen zeigt den Hinweis „Demo-Lead – keine
  Erfassung möglich", Button „Erfassung starten" ausgeblendet.
- [ ] **Karte** `/leads/karte`: Leaflet lokal unter `static/leaflet/` ablegen (keine CDN-
  Abhängigkeit), Kacheln `https://tile.openstreetmap.org/{z}/{x}/{y}.png` mit
  Attribution, Zentrum Duisburg. Pins: offene Leads (Farbe je Phase, Größe je Klasse),
  Termine (Symbol je AD), AD-Startadressen. Filter Phase/Sparte/AD/Zeitraum; Klick →
  Popup mit Name, Ort, Phase, Buttons „Akte", „Termin vorschlagen". Komponente
  `karte_termine_tag(ad, datum)` für die Mini-Karte im Assistenten (Termine des Tages
  als nummerierte Pins + Kandidat als Stern, Linie in Reihenfolge).
- [ ] **Startportal**: Karte „Lead-Management" – für Admins im Demo-Modus zusätzlich
  Badge `demo_badge_text` (gelb, wie bei der Projektierung) und die Kacheln **Neue
  Leads** (Zähler + SLA-Rot-Anteil) · **Jetzt anrufen** (fällig jetzt) · **Wiedervorlagen
  heute** · **Termine diese Woche** (Summe, Untertitel je AD) · **Posteingang unklar**;
  Shortcuts Anrufliste · Pipeline · Kalender · Karte. Bestehende Kacheln/Shortcuts
  (Leads VOT …) bleiben. Für alle anderen Rollen: Karte unverändert. Bei
  `lead_freigabe_modus = alle`: Badge weg, Kacheln für Innendienst/Leadmanagement/Admin.
- [ ] **Cockpit** `/leads/cockpit` (Admin, später Leadmanagement-Leitung): heute/diese
  Woche je Leadmanager: Anrufe, erreicht, qualifiziert, terminiert, überfällige
  Aktionen; je AD: Termine, No-Shows; Liste „SLA rot jetzt".
- [ ] Test: 30 Vorgänge (Demo + gesyncte) im Board richtig einsortiert; Akte zeigt alle
  Reiter; Karte lädt ohne Internet-Kacheln wenigstens die Pins; Kachelzahlen = Listen.

## Phase 80 – Kennzahlen: Statistik-Reiter „Leads" und Kanal-Report

- [ ] **Statistik → Reiter „Leads"** (nur `lead_modul_sichtbar`), Zeitraumwahl wie bestehend,
  Filter Quelle/Kampagne/Kanal/Sparte/Leadmanager/AD, Häkchen „Demo-Leads einbeziehen"
  (Standard: im Demo-Modus **an**, sonst aus). **Trichter** (Anzahl + Quote zum
  Vorschritt): Eingang → erreicht → qualifiziert → terminiert → VOT erfolgt → erfasst →
  Angebot versendet → gewonnen. Kennzahlen laut Konzept Abschnitt 8: Speed-to-Lead
  (Median Minuten bis 1. Versuch / bis erreicht, Anteil im SLA), Kontaktquote, Versuche
  bis erreicht, Terminquote, Show-Quote/No-Show-Quote (je AD, je Wunschzeit-Typ),
  Angebots-/Abschlussquote je Quelle, Durchlaufzeiten (Eingang → Termin, Termin →
  Angebot), Aktivität je Leadmanager, Gründe-Verteilungen (unqualifiziert, no_show,
  Ablehnung). Darstellung: Zahlenkacheln + einfache Balken (bestehende Chart-Technik
  der Statistik-Seite wiederverwenden).
- [ ] **Kanal-Report** `/leads/statistik/kanal`: Tabelle je Quelle × Monat: Leads, Termine,
  Aufträge, Auftragswert (aus angenommenen Angeboten der Vorgänge, brutto wie Deal-Wert),
  Kosten (= `kosten_je_lead` × Leads), Kosten je Termin, Kosten je Auftrag,
  Umsatz je Euro Lead-Kosten. CSV-Export. Hinweis, wenn eine Quelle keine Kosten hat.
- [ ] **Pipeline-Wert**: Summe `erwartungswert_<sparte>` × Phasen-Quote (Parameter je Phase,
  Standard neu 5 % · in_kontaktierung 8 % · qualifiziert 15 % · terminiert 30 % ·
  erfasst 40 % · angebot 50 %) über offene Vorgänge; Anzeige im Cockpit und Reiter.
- [ ] Test: Zahlen stimmen mit Board/Liste überein (Stichprobe je Phase); Export öffnet
  in Excel mit Umlauten.

## Phase 81 – Rollen, Sichten, Parametrierung, Löschlauf

- [ ] **Rolle Leadmanagement** (im Demo-Modus vollständig gebaut, aber unsichtbar – wirkt
  erst bei `alle`): Menü Lead-Management (Anrufliste, Board, Kalender, Karte, Posteingang,
  Import, Statistik-Reiter Leads), Kunden lesend/schreibend, Vorgangsakte mit allen
  Lead-Reitern; Angebote nur Liste mit Status/Endbetrag + PDF-Ansicht (keine EK/DB, kein
  Editor, kein Versand, kein Rabatt), Erfassungen lesend, Projektierung nur Phasen-Block.
  Keine Parametrierung außer „Lead-Management → Quellen & Kampagnen" und „Steuerdatei".
- [ ] **Außendienst-Sicht** (ebenfalls erst bei `alle`): in „Leads VOT" und in der eigenen
  Angebotsansicht Link „Lead-Akte" → Kopfblock + Reiter Aktivitäten/Qualifizierung/
  Termin read-only; Buttons **No-Show melden** und **Termin verschieben** (nur eigene
  Termine, nur in die eigene Woche, Dialog mit Grund; Kunde erhält Terminänderung nach
  `mail_modus`, Leadmanager wird benachrichtigt). Mobil: Seite **„Meine Termine"** (heute/
  diese Woche, Adresse mit Karten-Link `https://www.google.com/maps/dir/?api=1&destination=…`,
  Telefon, Steckbrief aus der Qualifizierung).
- [ ] **Innendienst** erhält bei `alle` alles wie Leadmanagement plus die bestehenden Rechte.
- [ ] **Parametrierung → Lead-Management** (nur Admin), Unterseiten: Einstellungen
  (`lead_freigabe_modus` mit dem Demo-Leads-Dialog aus Phase 73, `mail_modus` +
  Testadresse, `parser_modus`, `kalender_sync` + Testpostfach, SLA-Minuten,
  Arbeitszeit LM, Zuweisung, Horizont/Raster, Absender, Kerngebiet-PLZ, Erwartungswerte,
  Phasen-Quoten, Löschlauf + Frist, Firmenadresse) · Quellen & Kampagnen · Parser-Regeln
  (mit Test) · Routing (Anbieter, Schlüssel, Test, Tageszähler) · Steuerdatei · API-
  Schlüssel je Quelle · Demo-Daten (Generator, Löschen) · Protokoll (Änderungen an
  Parametern, Löschläufe, Demo-Umstellung).
- [ ] **Löschlauf** (täglich 03:00, **nur bei `loeschlauf = an`**): Vorgänge in Phase
  unqualifiziert / nicht_erreicht / verloren, deren letzte Aktivität älter als
  `loeschfrist_monate` ist und die kein angenommenes Angebot und kein Projekt haben →
  Anonymisierung: Name „Gelöscht", Kontakt/Adresse/Anfragetext/Rohdaten leer,
  Aktivitäten-Texte leer, Kennzahlen (Phase, Quelle, Zeiten, Sparten, PLZ-Präfix)
  bleiben; Kunde ebenfalls anonymisiert, wenn kein anderer Vorgang hängt. Protokoll mit
  Anzahl. Vorschau-Button „Was würde gelöscht?" in der Parametrierung. Im Demo-Modus
  läuft der Lauf zusätzlich nur über Demo-Leads.
- [ ] **Einwilligung**: Häkchen in Schnellanlage/Import/API mit Pflicht-Quelle
  (`formular` / `telefonisch` / `portal`), Datum automatisch; Anzeige in der Akte;
  `nurture`-Mails nur mit Einwilligung (Phase 78).
- [ ] Test je Rolle mit Test-PINs im Demo-Modus: Innendienst/AD/Projektierung sehen nichts
  Neues; Admin alles. Dann lokal `lead_freigabe_modus = alle` setzen: Leadmanagement
  sieht keine EK/DB; AD sieht Lead-Akte read-only und kann No-Show melden; zurück auf
  `admin` → alles wieder verborgen. Löschlauf-Vorschau plausibel.

## Phase 82 – Qualität, Docs, Rollout, Live-Master fortschreiben

- [ ] Fehlerfälle: Lead ohne Telefon und E-Mail (Anlage verweigern), Adresse ohne
  Geocode (Assistent mit Hinweis „Adresse prüfen"), Routing-Dienst nicht erreichbar
  (Luftlinie, Kennzeichen), Graph-Kalender ohne Recht (Hinweis, Tool-Termine), Import
  mit fehlerhafter Zeile (übersprungen + Protokoll), doppelter API-Aufruf (409), Termin
  außerhalb der Arbeitszeit (Warnung, erlaubt), monday-Lead im Assistenten (Buchen
  nur, wenn `lead_freigabe_modus = alle` – im Demo-Modus Hinweis „Terminierung im
  Demo-Modus nur für Demo-Leads", Vorschläge trotzdem sichtbar).
- [ ] Sicherheitsprüfung: jede `/leads`- und `/api/leads`-Route serverseitig gegen
  `lead_modul_sichtbar` bzw. API-Key; Demo-Leads in **keiner** bestehenden Abfrage
  (automatisierter Test: Demo-Lead anlegen → Leads VOT, Kundenliste, Angebotsliste,
  Statistik, Startportal-Kacheln als Innendienst zählen ihn nicht; Rückspielungs-Job
  überspringt ihn).
- [ ] `docs/leadmanagement.md` (Bedienanleitung: Eingangswege, Anrufliste, Kaskade,
  Qualifizierung, Assistent, Kalender, Kommunikation, Board, Statistik, Parametrierung,
  Demo-Modus und Umstellung auf `alle`), `docs/leads-api.md`, `docs/leadmanagement-
  entscheidungen.md`, `docs/graph-einrichtung.md` (Kalender-Rechte, Postfach leads@ und
  Testpostfach – Aufgaben für den M365-Admin).
- [ ] git push → Absprache mit dem Angebotstool-Chat (kein PROJ-Rollout am selben Tag) →
  update.bat auf dem Terminal-Server → migrate-Log prüfen → als Admin: Demo-Daten
  erzeugen, Sync-Lauf anstoßen, Board und Assistent öffnen. Als Innendienst gegenprüfen:
  nichts Neues sichtbar.
- [ ] `CLAUDE.md`: Kopf auf die nächste Versionsnummer erhöhen (v11, oder v12, falls
  PLAN_PROJ_V1 bereits v11 erzeugt hat); neuen Abschnitt **„Neu in v<NN> – Lead-Management
  V1 Demo (abgestimmt 22.09.2026)"** anhängen, wörtlich:

  > - **Lead-Management V1 (Demo):** Lead = Vorgang (v10) mit Lead-Phase
  >   (Neu · In Kontaktierung · Qualifiziert · Terminiert · danach abgeleitet
  >   Erfasst/Angebot/Gewonnen/Verloren; Seitenzustände Zurückgestellt · Nicht
  >   erreicht · Unqualifiziert), Quelle/Kampagne/UTM, Eingang, SLA, Score (A/B/C),
  >   Leadmanager, Wunschzeiten, Koordinaten, Einwilligungen. Gesyncte monday-Leads
  >   erhalten die Phase abgeleitet (Badge „monday"); **monday-Sync und -Rückspielung
  >   unverändert**.
  > - **Demo-Modus:** Parameter `lead_freigabe_modus` (admin / alle, Standard admin):
  >   bei admin sind alle Routen unter `/leads` und `/api/leads`, Menüpunkte, Reiter,
  >   Kacheln nur für Admins (server-seitig, 404 für andere); Startportal-Karte
  >   „Lead-Management" trägt das Badge „Demo · Coming soon". Im Modul angelegte Leads
  >   tragen `demo = 1` und erscheinen in keiner bestehenden Liste/Statistik/Kachel/
  >   Rückspielung; Umstellung auf `alle` fragt: Demo-Leads löschen oder behalten.
  >   Sperren im Demo-Modus: `mail_modus` nur protokoll/test (live abgewiesen),
  >   `kalender_sync` nur ins Testpostfach, monday-Leads nicht buchbar.
  > - **Eingang:** Schnellanlage, CSV/Excel-Import mit Spaltenzuordnung, `POST
  >   /api/leads` (API-Key je Quelle), Mail-Parser mit Regeln + Test (Abruf nur bei
  >   `parser_modus = an`), Formular-Standard `[LEAD] <quelle> <kampagne>` + `Feld: Wert`,
  >   „Posteingang unklar", Duplikatprüfung (Telefon E.164, E-Mail, Name+PLZ, Adresse)
  >   mit Anhängen an offenen Vorgang, Demo-Daten-Generator.
  > - **Terminierung:** Anrufliste priorisiert (SLA → fällig → zurückgestellt → Score),
  >   Ein-Klick-Anrufergebnisse, Wiedervorlage-Kaskade und Gründe aus
  >   `leadmanagement_logik_v1.xlsx` (Blätter Qualifizierung, Scoring, Klassen, Kaskade,
  >   Gruende, Wunschzeiten; Import in der Parametrierung), Qualifizierungsbogen je
  >   Sparte mit Live-Score und Vorbelegung des Erfassungsbogens über `erfassungs_frage`
  >   (aktiv erst bei `alle`).
  > - **Terminassistent:** Top-5-Slots über AD-Profile (Startadresse, Arbeitszeiten,
  >   Dauer/Puffer/Max), Tool-Termine (`vot_termine`, auch aus monday-VOT-Datum),
  >   optional Outlook-Frei/Belegt (Graph, `kalender_sync`), Fahrzeiten
  >   (`routing_anbieter` ors / google / luftlinie, Caches), Bewertung Umweg +
  >   Wunschzeit/Tour-Tag/Randzeit; Buchen schreibt Termin, Outlook-Ereignis (falls an),
  >   Bestätigung + Erinnerung; Umbuchen, No-Show (Lead zurück auf Qualifiziert),
  >   Terminkalender Woche je AD, Karte (Leaflet lokal, OSM-Kacheln), „Adresse prüfen".
  > - **Kommunikation:** Vorlagen eingangsbestaetigung / nicht_erreicht /
  >   terminbestaetigung (ICS) / terminerinnerung (−24 h) / terminaenderung / nurture
  >   (nur mit Einwilligung), Warteschlange + Versand-Job, `mail_modus` protokoll / test /
  >   live, Reiter Kommunikation in der Akte, Absender `leads@friondo.de` (Fallback angebot@).
  > - **Oberfläche:** Anrufliste, Pipeline-Kanban, Lead-Akte (Vorgangsakte + Kopfblock
  >   Lead + Reiter Aktivitäten/Qualifizierung/Termin/Kommunikation), Kalender, Karte,
  >   Cockpit, Statistik-Reiter „Leads" (Trichter, Speed-to-Lead, Quoten, Gründe),
  >   Kanal-Report (Kosten je Lead/Termin/Auftrag), Pipeline-Wert.
  > - **Rollen:** neu `leadmanagement` (Mehrfachrolle; keine EK/DB, kein Angebots-Editor),
  >   AD-Profile in der Benutzerverwaltung, AD-Sicht Lead-Akte read-only + No-Show/
  >   Verschieben – alles erst bei `alle` wirksam. Löschlauf (`loeschlauf`, Frist
  >   `loeschfrist_monate`, Anonymisierung) mit Vorschau.
  > - Geplant: V2 monday-Import + Parallelbetrieb, SMS, Tourenplanung Tag + „Leads in
  >   der Nähe", Gebietskarte, KI-Extraktion (Schalter), CTI, Webhook extern; V3
  >   Online-Terminwahl, WhatsApp, Cross-Selling-Trigger, Score-Kalibrierung; V4
  >   KI-Sprachschicht, Voice-/Chat-Vorqualifizierung.

- [ ] `konfigurator_logik_v5.xlsx`: **keine Änderung** in V1.

---

## Was Andreas parallel zum Bau erledigen kann (nicht blockierend)

1. **M365-Admin:** Postfach `leads@friondo.de` + Testpostfach (z. B.
   `lead-test@friondo.de`) anlegen, „Senden als" für das Tool-Konto, Graph-Rechte
   `Calendars.ReadWrite` (Application) mit Zugriffsbeschränkung auf AD-Postfächer +
   Testpostfach (Anleitung entsteht in `docs/graph-einrichtung.md`).
2. **openrouteservice-Konto** (kostenlos, account.heigit.org) anlegen, API-Key in die
   Parametrierung; Kontingente des Free-Plans dabei notieren.
3. **Agentur informieren:** Formular-Standard (Betreff `[LEAD] <quelle> <kampagne>`,
   Body `Feld: Wert`) für Website, Förderrechner und Landingpages – Umstellung erst,
   wenn die Demo freigegeben ist; vorher nur an die Testadresse.
4. **Excel-Feinschliff:** Qualifizierungsfragen, Punkte, Kaskade und Gründe in
   `leadmanagement_logik_v1.xlsx` anpassen; Erwartungswerte je Sparte und
   Kerngebiet-PLZ in der Parametrierung setzen.
5. **AD-Profile** ausfüllen (Startadressen, Arbeitszeiten) – ohne sie rechnet der
   Assistent mit Standardwerten ab Firmenadresse.
6. **Antworten auf die offenen Fragen** aus dem Konzept (Abschnitt 17): Lead-Volumen,
   Telefonanlage, Blinno-Workspace, Kernvertriebsgebiet, HTTPS-Route – fließen in
   PLAN_LEAD_V2.

---

## Offene Punkte nach V1 (aus Konzept Abschnitt 16)

Lead = Vorgang · SLA-Werte · Kaskade · Score-Punkte und Klassen · Assistent-
Gewichte · Routing-Anbieter · Zuweisungsregeln · Kanban-Spalten · Erwartungswerte
und Phasen-Quoten · Löschfristen · Reihenfolge PROJ/LEAD-Rollouts · Freigabe der
Demo (`alle`) und Start der monday-Ablösung (PLAN_LEAD_V2).
