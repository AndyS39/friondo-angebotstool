# PLAN_LEAD_V2 – Lead-Management V2 (CLAUDE v23, Phasen 104–112)

> **Entscheidung 02.10.2026 (Andreas):** kein Lastenheft, sondern direkt codieren.
> Teil 1 ist der Umsetzungsplan für Claude Code, Teil 2 der ursprüngliche
> Auftragstext (Anforderungsdiktat A–I, Statusliste 5a, Festlegungen F1–F16).
> Alles läuft weiter **im Demo-Modus** (`lead_freigabe_modus = admin`,
> Sendesperre, Kalender nur ins Testpostfach) – V3 schaltet frei.
> Offene Punkte werden nicht gefragt, sondern als **Annahme A-n** umgesetzt
> und gelten bis zum Widerspruch.

---

# Teil 1 – Umsetzungsplan

## Annahmen (gelten bis Widerspruch)

- **A-1 Handelsvertreter** = Kennzeichen `ad_profile.terminiert_selbst` (Hauptrolle
  bleibt `aussendienst`; Helfer `ist_handelsvertreter()`); keine neue Rolle.
  Vorteil: AD-Profil (Startadresse, Gebiet, Kapazität, Outlook-Postfach) wird
  mitbenutzt, Leads VOT → Erfassung → Angebot läuft unverändert. Nachteil: Rechte
  hängen an einem Profilfeld statt an der Rolle – deshalb zentral in
  `lead_handelsvertreter.py` gekapselt.
- **A-2 Terminarten:** `vot_termine.typ` = `vot` | `telefon` | `online` (Teams);
  `medium` = `vor_ort` | `telefon` | `teams`. Status „Telefongespräch“ (H6) und
  „Teams Meeting“ (F12) sind damit Termine, keine Phasen.
- **A-3 Vorab-Angebot** = Kennzeichen `vorgaenge.vorab_angebot`; Weg: aus der
  Kundenkartei „Erfassung ohne Termin“ (bestehende Erfassung mit lead_id, ohne
  VOT) → Phase springt von Qualifiziert direkt nach Erfasst/Angebot; keine
  Terminbestätigung.
- **A-4 Nachbearbeitung** = Zurückgestellt mit Grund „Nachbearbeitung, noch nicht
  bereit für VOT“ (Blatt Gründe) und Pflicht-Wiedervorlage; sichtbar als Gruppe
  „Pausiert“ im Hauptboard und im Dashboard als Wiedervorlage.
- **A-5 Kaskade 5 Stufen:** 1 +2h · 2 +1d 18:00 Mail nicht_erreicht · 3 +3d ·
  4 +7d Mail nicht_erreicht · 5 +14d letzter → Phase Nicht erreicht, Mail
  `disqualifiziert`, Nurture +30 Tage. `versuche_max` = 5 (Parameter); danach sind
  die Ergebnis-Buttons Nicht erreicht/Besetzt/Mailbox gesperrt.
- **A-6 Objektart** am Kunden (`kunden.objektart` EFH|RH|REH|MFH, `kunden.parteien`);
  Rechnungsadresse = bestehende `kunden.rechnung_*`. Vorbelegung des WP-Bogens:
  O01 (Gebäudetyp) aus der Objektart, Q-W02/Q-P02 füllen die Objektart rückwärts.
- **A-7 Außendienst am Vorgang:** `vorgaenge.ad_id` (Zuständiger AD/HV), unabhängig
  vom Termin; Termine tragen weiter `vot_termine.ad_id`.
- **A-8 Info-Lead → Veranstaltung** [OFFEN 1]: nächste Veranstaltung ab Eingang +
  `info_vorlauf_tage` (3); API-Feld `veranstaltung` (YYYY-MM-DD) optional übersteuert.
- **A-9 „Terminbestätigung erneut senden“** [OFFEN 2]: Button in der Kartei,
  gleiche ICS-UID, SEQUENCE+1, Aktivität.
- **A-10 Sparte Gewerbe:** Code `GW` (wie WB nur Freitext-Erfassung); Kompetenz
  „MFH“ und „Gewerbe“ sind Objektkompetenzen am AD-Profil.
- **A-11 Navigation:** linke Icon-Leiste mit 5 Einträgen (H1) + „Mehr …“
  (Übersicht, Kalender, Karte, Statistik, Import, Posteingang, Handelsvertreter);
  Hauptboard mit Umschalter Tabelle | Anrufliste | Kanban – kein Einstieg geht verloren.
- **A-12 Dashboard** (A1) für Innendienst/Leadmanagement/Admin und Handelsvertreter
  (F16); Außendienst behält Meine Termine/Leads VOT.
- **A-13 Terminassistent:** Puffer = max(`puffer_min` 30, Fahrzeit), Dauer 90,
  Raster 30, `max_termine_tag` Vorschlag 3 (Startwert für neue Profile).
- **A-14 Spaltenkonfiguration** je Nutzer in `benutzer_einstellungen` (key/wert
  JSON); Farben, Pflichtfelder, Ausschlussliste, Veranstaltungsparameter als
  LeadParameter (Parametrierung → Lead-Logik/Lead-Boards).
- **A-15 Bestandsabgleich** (Kennzeichnung [Bestand]/[Erweiterung]/[Neu]) steht
  in `docs/leadmanagement-entscheidungen.md` (Abschnitt V2) statt in einem Lastenheft.

## Arbeitsregeln

- Steuerdatei `leadmanagement_logik_v1.xlsx` bleibt die Quelle für Kaskade,
  Gründe, Objektarten, Status-Mapping (neue Blätter „Objektarten“, „Status“).
- Geteilte Dateien (`app/models.py`, `app/db.py`, `app/leadmanagement.py`,
  `app/auth.py`, `app/main.py`, `migrate.py`, `base.html`) werden nur in Phase
  104/112 zentral geändert; die Fachphasen liefern eigene Module, Router,
  Templates, Tests und hängen CSS an `app/static/lead_v2.css` an.
- Tests laufen im Demo-Modus gegen die Entwicklungs-DB (Muster
  `tests/test_lead_v11.py`); jede Phase hat eine eigene Testdatei.
- Commit am Ende: „v23: Lead-Management V2 (PLAN_LEAD_V2, Phasen 104–112)“;
  **kein Push ohne Freigabe.**

## Phase 104 – Fundament (Datenmodell, Steuerdatei, Parameter, Migration)

- [ ] Spalten: `kunden.objektart`, `kunden.parteien`; `vorgaenge.ad_id`,
  `vorab_angebot`, `veranstaltung_id`, `teilgenommen`; `vot_termine.typ`,
  `medium`, `ics_uid`, `ics_sequence`; `benutzer.buchungslink`, `nebenstelle`;
  `ad_profile.terminiert_selbst`, `kompetenz_sparten` (JSON), `kompetenz_kombi`,
  `kompetenz_mfh`, `kompetenz_gewerbe`; `lead_aktivitaeten.call_id`, `richtung`,
  `nebenstelle`; Tabellen `todos`, `info_veranstaltungen`, `benutzer_einstellungen`.
- [ ] Sparte `GW` (Gewerbe) in Konstanten, Chips, Interesse-Badges, API.
- [ ] Steuerdatei: Kaskade 5 Stufen (A-5), Gründe `verloren` (Zu teuer · Kein
  Interesse mehr · Bleibt bei Öl/Gas · Woanders unterschrieben · Sonstiges) und
  „Nachbearbeitung, noch nicht bereit für VOT“ (zurueckgestellt), Blatt
  „Objektarten“, Blatt „Status“ (5a → Phase/Board/Gruppe).
- [ ] LeadParameter: `versuche_max` 5, `wv_meldet_sich_tage` 14, `phasen_farben`,
  `kanal_farben`, `pflichtfelder`, `hv_ausschluss`, `hv_standard_benutzer`,
  `ersatz_radius_stufen` „5; 10“, `ersatz_alter_tage` 14, `info_wochentag` 3,
  `info_woche` 1, `info_uhrzeit` 18:00, `info_ort`, `info_vorlauf_tage` 3,
  `info_rollierend_monate` 12, `puffer_min` 30, `max_termine_tag_start` 3.
- [ ] Mail-Vorlagen `disqualifiziert` ({briefanrede} {vertriebler}
  {rueckruf_telefon} {sparten}) und `online_termin_einladung` ({buchungslink}
  {kollege}) als Starttexte.
- [ ] `kaskade_anwenden`: Stufe 5, Aktion `mail_disqualifiziert`, Sperre ab
  `versuche_max`.
- [ ] `app/lead_info.py` Terminregel (1. Donnerstag 18:00, NRW-Feiertage mit
  Osterformel, Ausweichen +7 Tage) + Kontrollliste Okt 2026–Aug 2027.
- [ ] `migrate.py`: Parameter/Vorlagen/Veranstaltungen anlegen, `ad_id` aus
  aktiven Terminen, Objektart aus Qualifizierungsantworten, Kompetenz-Startwerte
  F3 per Namensabgleich, `terminiert_selbst` für die sechs Handelsvertreter.
- [ ] Tests `tests/test_lead_v2_fundament.py`.

## Phase 105 – Menü, Hauptboard, Terminiert, Kontaktiert (A3/A4/H1–H5/H7/H8)

- [ ] Linke Icon-Leiste (lokale SVGs, Tooltips) mit Hauptboard · Terminiert ·
  Kontaktiert · Info-Veranstaltung · E-Mail-Vorlagen + „Mehr …“; Suchleiste oben.
- [ ] Tabelle A3 generisch (`app/lead_boards.py`): Pflichtspalten, fixierte
  Spaltenköpfe, farbige Labels (`phasen_farben`/`kanal_farben`), Avatare mit
  Initialen, Spaltenkonfiguration je Nutzer, Inline-Bearbeitung (Status, Notiz,
  AD, ID, Wiedervorlage) per fetch.
- [ ] Status → Board → Gruppe (Blatt „Status“), Hauptboard Neu/Pausiert/
  Disqualifiziert, Board Terminiert Angebotserstellung/Angebotsversand/
  Gewonnen/Verloren; Umschalter Tabelle | Anrufliste | Kanban.
- [ ] Sammelaktionen registrierbar je Board (Status ändern), Aktivität je Lead.
- [ ] Reiter Kontaktiert (alle Versuche, Suche, Rufnummernsuche E.164).
- [ ] Menüpunkt E-Mail-Vorlagen (Vorlagen-Editor im Modul).
- [ ] Tests `tests/test_lead_v2_boards.py`.

## Phase 106 – Kundenkartei dreispaltig (B1–B8)

- [ ] Dreispaltige Kartei `/lead-management/lead/<id>`: links Kontaktinfos +
  Aktions-Icons, Pflichtfelder rot + Zähler (`pflichtfelder`), Objektart/
  Parteien/Rechnungsadresse (MFH), Innendienst/Außendienst-Dropdowns.
- [ ] Mitte: Reiter mit Icons – Timeline (Karten, Suche, Filter), E-Mail-Verlauf
  (eigene/automatisiert/Kollegen, ein/aus), Anrufnotizen, Qualifizierung,
  Termin, Erfassungen/Angebote/Projekt.
- [ ] Rechts: einklappbare Bereiche mit Zähler (Termine, Angebote, Erfassungen,
  Projekt, Anhänge, To-Dos).
- [ ] Termin vorschlagen (Assistent), manuell (15-Min-Raster, Konfliktwarnung),
  Telefongespräch/Online-Termin (A-2), Erfassung ohne Termin (A-3), Button
  „Terminierung“ (B8) mit Fehlliste, „Terminbestätigung erneut senden“ (A-9).
- [ ] Responsiv: Spalten untereinander auf Tablet/Mobil.
- [ ] Tests `tests/test_lead_v2_kartei.py`.

## Phase 107 – Anruf-Workflow & Telefonie (C1–C4, D1–D3)

- [ ] 5 Versuchs-Punkte mit Ergebnisfarbe/Tooltip; Sperre ab `versuche_max`.
- [ ] „Nicht erreicht“-Dialog mit Kaskaden-Vorschlag (änderbar), Wiedervorlage +
  Glocke zum Zeitpunkt; Mailbox zählt; Kein Interesse mit Pflichtgrund.
- [ ] Mail-Regeln: Stufe 2/4 `nicht_erreicht`, Stufe 5 `disqualifiziert`;
  Doppelversand-Schutz über Warteschlange/Terminstatus.
- [ ] tel:-Links überall + Stoppuhr (`dauer_sek`, korrigierbar); „Meine Anrufe“;
  Rufnummernsuche E.164 (gemeinsam mit H7).
- [ ] Tests `tests/test_lead_v2_anruf.py`.

## Phase 108 – Terminassistent & Routenplaner (E1–E4, F3, F4)

- [ ] AD-Profil: Kompetenzen (Sparten, Kombi WP+PV(+KL), MFH, Gewerbe),
  Kennzeichen Handelsvertreter, Startwerte F3.
- [ ] Filterregel: Ausschluss = Kanal-Regel, Kompetenz, Kapazität, Arbeitszeit;
  Abwertung = Gebiet, Fahrzeit, Wunschzeit; Begründung in Klartext + Mini-Karte.
- [ ] Puffer = max(30, Fahrzeit), Dauer 90, Raster 30.
- [ ] Ersatzkunde bei Absage/Umbuchung (Radius 5→10 km, Alter ≥ 14 Tage bevorzugt,
  mehrere Kandidaten mit Begründung), Glocke ans Leadmanagement.
- [ ] ICS: Titel, Adresse, Berater + Telefon, Erinnerung, Absage-Hinweis;
  Umbuchung gleiche UID + SEQUENCE, Absage METHOD:CANCEL.
- [ ] Tests `tests/test_lead_v2_termin.py`.

## Phase 109 – Handelsvertreter (G1–G5, F13–F16)

- [ ] Kennzeichen + Rechte (`lead_handelsvertreter.py`): eigene Leads anrufen,
  Kartei bearbeiten, terminieren (nur eigener Kalender), Terminierung.
- [ ] Ansicht „Handelsvertreter“ (Gesamtsicht ID/LM/Admin, gefiltert für HV).
- [ ] Zuweisung per Dropdown (Tabelle, Kartei, Schnellanlage), Ausschlussliste
  `hv_ausschluss` (Dropdown deaktiviert + Hinweis; Kanalwechsel → Hinweis +
  Glocke an Verantwortlichen), Standard Simon O'Grady außer „Deals - Rene“,
  Umverteilung mit Aktivität + Glocke.
- [ ] Tests `tests/test_lead_v2_handelsvertreter.py`.

## Phase 110 – Dashboard & To-Dos (A1, A2, F7)

- [ ] Persönliches Dashboard beim Modul-Einstieg: fällige/kommende
  Wiedervorlagen, eigene Vorgänge, Termine der nächsten Tage, To-Dos.
- [ ] To-Dos (`todos`): jeder an jeden, Fälligkeit, erledigt; Glocke mit
  Zähler-Badge.
- [ ] Tests `tests/test_lead_v2_dashboard.py`.

## Phase 111 – Info-Veranstaltung (I1–I5)

- [ ] Veranstaltungen rollierend (12 Monate), Board mit Gruppen je Termin,
  Archiv, Spalte „Teilgenommen“, Sammelaktionen „Status ändern“ und „In die
  nächste Veranstaltung verschieben“.
- [ ] Quelle „Info-Veranstaltung“, API-Zuordnung (A-8), Abgleich E-Mail-oder-
  Telefon + Nachname → roter Hinweis „Kunde bereits im System“.
- [ ] Tests `tests/test_lead_v2_info.py`.

## Phase 112 – Abnahme, Doku, Rollout

- [ ] Alle Tests, Abnahmeskript, Voll-Crawl gegen migrierte DB-Kopie.
- [ ] `docs/leadmanagement-entscheidungen.md` (V2: Bestandsabgleich, Mapping 5a,
  Status → Board → Gruppe), `docs/nach-dem-update-v23.md`, `docs/leads-api.md`,
  Prototyp-Hinweise, CLAUDE.md „Neu in v23“ + Zuordnungstabelle.
- [ ] Commit, kein Push ohne Freigabe.

---

# Teil 2 – Auftragstext (Original)

# Prompt: Lastenheft „Lead-Management V2“ für das Friondo-Tool

> Diesen Text komplett in einen neuen Cowork-Chat im Projekt „Friondo Tool“ einfügen und die beiden Screenshots (monday-Tabellenzeile und HubSpot-Kontaktkarte) anhängen.

---

## 1. Deine Rolle und dein Auftrag

Du bist Fachkonzepter für das Friondo-Tool (FastAPI, SQLite, Jinja, lokal auf dem Terminal-Server fr-wts-02). Dein Auftrag: Erstelle aus dem untenstehenden Anforderungsdiktat ein vollständiges, widerspruchsfreies **Lastenheft für die Erweiterung und Optimierung des Moduls Lead-Management** (Arbeitstitel „Lead-Management V2“). Das Lastenheft ist die Entscheidungsgrundlage für Andreas Scheelen (Geschäftsführung) und anschließend die Vorlage für einen Umsetzungsplan in Claude Code (PLAN_LEAD_V2.md). Du schreibst **keinen Code** und keinen Umsetzungsplan, sondern das fachliche Soll.

Sprache: Deutsch, Fachbegriffe wie im Projekt (Vorgang, Vorgangsakte, Lead-Phase, Leads VOT, Außendienst/AD, Innendienst/ID, Leadmanagement/LM, Parametrierung, Sparte WP/PV/KL/WB, Vertriebskanal).

## 2. Pflichtlektüre vor dem ersten Satz

Lies zuerst vollständig im Projektwissen:

1. `CLAUDE.md` (v21), insbesondere die Abschnitte „Neu in v10 (Kundenvorgänge)“, „Neu in v12 (Lead-Management V1 Demo)“, „Neu 27.09.2026 (Review Lead-Prozess)“, „Neu in v14 (Design-Update)“ und „Neu in v21 (Lead-Management V1.1)“.
2. `claude/LEADMANAGEMENT-KONZEPT.md` (Gesamtkonzept, Datenmodell, Terminassistent, Kommunikation, Rollen, Annahmen in Abschnitt 16, offene Fragen in Abschnitt 17).
3. `claude/PROTOKOLL-2026-09-30-Angebotstool.md` (aktueller Stand, Ordner-Umzug, Rollout-Regeln).

Wichtig: Vieles aus dem Diktat existiert bereits in V1/V1.1 (Anrufliste mit Ergebnis-Buttons und Tasten 1 bis 7, Wiedervorlage-Kaskade, Vorlagen `nicht_erreicht` und `terminbestaetigung` mit ICS, Terminassistent mit AD-Profilen, Outlook-Frei/Belegt über Graph, Routing über openrouteservice, Lead-Akte mit Reitern, Übersicht mit Kacheln, Versuchs-Punkte in der Anrufliste). **Jede Anforderung musst du gegen diesen Bestand abgleichen und eindeutig kennzeichnen als:**

- **[Bestand]** existiert bereits, keine Änderung nötig (mit Verweis auf die Stelle in CLAUDE.md),
- **[Erweiterung]** existiert in Grundzügen, wird verändert oder ergänzt (was genau sich ändert),
- **[Neu]** existiert nicht.

Erfinde keine Bestandsfunktionen. Wenn du eine Stelle in CLAUDE.md nicht findest, kennzeichne sie als „[Neu, Bestand unklar]“ und nimm sie in die Rückfragenliste auf.

## 3. Feste Rahmenbedingungen (nicht verhandelbar)

- Lead = Vorgang (v10). Keine zweite Lead-Tabelle. Alle neuen Felder hängen am Vorgang, am Kunden oder an bestehenden Lead-Tabellen (`lead_aktivitaeten`, `vot_termine`, `ad_profile`, `kommunikation_log`).
- monday-Lesesync und monday-Rückspielung bleiben unverändert. Das Modul läuft weiter hinter `lead_freigabe_modus` (admin / alle); alles Neue muss im Demo-Modus funktionieren (Sendesperre für Kundenmails außer Testpostfach, Kalender nur ins Testpostfach).
- Oberfläche folgt dem Design-System v14 (CSS-Tokens, Makros `status_badge`, `wiedervorlage_chip`, lokale SVG-Icons, keine externen CDNs oder Webfonts) und der Vorlage `docs/leadmanagement-prototyp.html`. Layout-Änderungen werden zuerst im Prototyp beschrieben. Gestaltungsvorgaben innerhalb dieses Rahmens: clean, minimalistisch, modern; Friondo-Blau und Weiß mit den exakten Farbwerten aus den bestehenden CSS-Tokens; alle Karten, Kästen und Eingabefelder mit abgerundeten Ecken; viel Weißraum, dezente Trennlinien; schmale Icon-Menüleiste am linken Rand, Suchleiste oben; responsiv für Desktop, Tablet und Mobil (Spalten der Kundenkartei werden auf Tablet/Mobil untereinander angeordnet, das Menü bleibt per Icon erreichbar). Wo das mit dem Design-System v14 kollidiert (z. B. heutige Hauptnavigation oben), beschreibe den Unterschied und schlage vor, wie beides zusammenpasst.
- Das Angebotstool ist **Teil des Friondo-Tools** (gleiche Anwendung, gleiche Datenbank, Vorgang → Erfassung → Angebot). Es gibt kein externes Angebotssystem; Anbindungsfragen sind daher Fragen der internen Verknüpfung, nicht der Schnittstelle.
- Prozesswissen (Gründe, Kaskade, Statuslisten, Objektarten) gehört in pflegbare Tabellen (`leadmanagement_logik_v1.xlsx` bzw. Parametrierung), nicht in den Code.
- Rollenmodell v12/v21 bleibt: Admin, Innendienst, Leadmanagement, Außendienst (read-only an eigenen Vorgängen plus No-Show/Verschieben), Projektierung, Montage.
- Bestehende Tastenkürzel 1 bis 7 der Anrufliste bleiben erhalten.
- Datenschutz: Für jede Telefonie-, Kalender- oder Routing-Anbindung nennst du die übertragenen Daten und ob ein AVV nötig ist.

## 4. Die beiden Screenshots (Inspiration, keine 1:1-Kopie)

**Screenshot 1, monday-Tabellenzeile:** Eine Zeile „Herr Helmut Schliwa“ mit Spalten in dieser Reihenfolge: Lead (Name mit Zähler für Unterelemente, Aufklapp-Pfeil, Chat-Icon), Anrede, Vorname, Nachname, Status (graues Label „Neuer Lead“), Vertriebskanal (rosa Label „Sparkasse“), Anzahl Kontaktversuche, Letzter Kontakt, Eingangsdatum („Sep. 30, 2026“), Notiz (breites Freitextfeld), Außendienst (Personen-Avatar, hier leer), Innendienst (Avatar mit Initialen „PT“), Ort („47269 Duisburg“), Interessen (blaues Label „WP“), Straße, Telefon, E-Mail (mit Landesflagge), Vor-Ort-Termin. Zu übernehmen: farbige Labels je Spaltenwert, Avatare mit Initialen für Zuständige, Spaltenköpfe fixiert, kompakte Zeilenhöhe.

**Screenshot 2, HubSpot-Kontaktkarte:** Dreispaltig. Links schmale Spalte mit Foto/Avatar, Name, E-Mail, darunter Aktions-Icons (E-Mail, Anruf, Notiz, Meeting, Mehr), dann „Über diesen Kontakt“ mit Feldern (E-Mail, Telefon, Zuständiger, Erstelldatum, Lifecycle-Phase), darunter einklappbare Bereiche. Mitte: Reiter Überblick / Aktivitäten / Intelligence, darunter Unterreiter Aktivität / Notizen / E-Mails / Anrufe / Aufgaben / Meetings mit Suchfeld, Filter und einer chronologischen Timeline aus Karten (Titel, Zeitstempel, Beschreibung, aufklappbar). Rechts: einklappbare Zuordnungsbereiche (Leads, Unternehmen, Tickets, Anhänge) mit Zähler und „Hinzufügen“. Zu übernehmen: Dreispalten-Aufteilung, Aktions-Icons direkt unter dem Namen, Timeline als Karten, Reiter mit Icons.

## 5. Anforderungsdiktat (vollständig abzudecken)

### A. Lead-Übersicht und benutzerindividuelles Dashboard

A1. Jeder Nutzer (Innendienst, Leadmanagement, Admin; Außendienst eingeschränkt auf eigene Termine) erhält beim Modul-Einstieg eine eigene Übersicht mit: fällige und kommende Wiedervorlagen, ihm zugeteilte Kunden/Vorgänge, Termine der nächsten Tage.
A2. Separater Bereich **To-Dos**: zugewiesene (von Kollegen oder vom System) und selbst gesetzte Aufgaben mit Fälligkeit, Vorgangsbezug (optional), Erledigt-Häkchen. Abgrenzung zur Wiedervorlage klar definieren (Wiedervorlage = Kundenkontakt zu einem Zeitpunkt; To-Do = Arbeitsauftrag).
A3. **Tabellenansicht nach monday-Vorbild** als zusätzliche Ansicht neben der bestehenden Anrufliste (die Anrufliste bleibt als priorisierte Arbeitsliste erhalten, Umschalter Tabelle | Anrufliste | Kanban). Pflichtspalten in dieser Reihenfolge: Kundenname, Status, Vertriebskanal, Interessen (so weit vorn wie möglich), Anzahl Kontaktversuche, letzter Kontaktversuch (Datum/Uhrzeit/Ergebnis), Innendienst (Avatar mit Initialen), Außendienst (Avatar), Eingangsdatum, Vor-Ort-Termin, Notiz, Straße, PLZ, Ort, Telefon, E-Mail. Spalten ein-/ausblendbar und per Drag sortierbar, Einstellung je Nutzer gespeichert; Sortierung und Filter je Spalte; Sticky-Kopf; Inline-Bearbeitung mindestens für Status, Innendienst, Außendienst, Notiz; Klick auf den Namen öffnet die Kundenkartei.
A4. **Status-Labels farbig**: Die Status-Spalte zeigt die Lead-Phase als farbiges Label. Grundlage ist die bisherige monday-Statusliste (Abschnitt 5a), die aber **nicht 1:1 übernommen** wird: Viele monday-Status sind im Tool bereits durch andere Mechanismen abgedeckt (Versuchszähler, Sparten-Badge, Aktivitätstyp, abgeleitete Phasen). Übernimm die Vorab-Bewertung aus Abschnitt 5a, prüfe sie gegen den Bestand und erstelle eine **Mapping-Tabelle monday-Status → Tool-Darstellung** (Phase, Versuchszähler, Sparte, Aktivitätstyp, Terminart oder Kennzeichen) mit Farbe je Phase, angelehnt an die monday-Farben. Die Mapping-Tabelle dient später auch dem monday-Import (Konzept Abschnitt 14). Zusätzlich farbige Labels für Vertriebskanal (Farben je Kanal in der Parametrierung) und Interessen (WP/PV/KL/WB, bestehende Sparten-Badges). Phasen- und Kanalfarben werden in der Parametrierung gepflegt, nicht im Code.

### 5a. monday-Statusliste und Vorab-Bewertung

Aktive monday-Status (gestrichene bereits entfernt: Export, AB gesprochen, Reklamation, Nicht erreicht disqualifiziert). Spalte „Vorab-Bewertung“ ist mein Vorschlag; du prüfst ihn gegen CLAUDE.md und bestätigst oder widersprichst mit Begründung.

| monday-Status | Farbe (ca.) | Vorab-Bewertung | Tool-Entsprechung |
|---|---|---|---|
| Neuer Lead | grau | entfällt, Bestand | Phase Neu |
| 1. Kontaktversuch | rosa | entfällt, Bestand | Phase In Kontaktierung + Versuchszähler 1 (`versuche_punkte`) |
| 2. Kontaktversuch | blauviolett | entfällt, Bestand | Versuchszähler 2 |
| 3. Kontaktversuch | violett | entfällt, Bestand | Versuchszähler 3 |
| 4. Kontaktversuch | orange | entfällt, Bestand | Versuchszähler 4 |
| 5. Kontaktversuch | graublau | entfällt, Bestand | Versuchszähler 5 (Maximum laut Entscheidung) |
| erneuter Anruf | graulila | entfällt, Bestand | Wiedervorlage bzw. Rückruf gewünscht (Kaskade), sichtbar als Wiedervorlage-Chip |
| Disqualifiziert - nicht erreicht | pink | entfällt, Bestand | Phase Nicht erreicht (Kaskade ausgeschöpft) |
| Disqualifiziert | rot | entfällt, Bestand | Phase Unqualifiziert mit Pflichtgrund |
| Standby | ocker | entfällt, Bestand | Phase Zurückgestellt (Datum + Grund) |
| Will sich selber zurückmelden | dunkelviolett | Erweiterung | Zurückgestellt mit Grund „meldet sich selbst“ und Standard-Wiedervorlage (Vorschlag +14 Tage, parametrierbar), kein eigener Status |
| Terminiert | hellgrün | entfällt, Bestand | Phase Terminiert |
| Angebotserstellung | dunkelblaugrau | entfällt, Bestand | abgeleitete Phase Erfasst (Erfassung vorhanden, Angebot noch nicht versendet) |
| Angebot versendet | braun | entfällt, Bestand | abgeleitete Phase Angebot |
| Vorab Angebot | blau | geklärt, siehe F10 | vermutlich Angebot ohne vorherigen Vor-Ort-Termin; Vorschlag: Kennzeichen am Angebot bzw. Vorgang „Vorab-Angebot“, keine eigene Phase |
| Nachbearbeitung | blau | geklärt, siehe F11 | Bedeutung unklar (nach VOT vor Angebot, oder Verfolgung nach Angebot?) |
| Klima | grün | entfällt, Bestand | Interesse KL (Sparten-Badge), kein Status |
| E-Mail | altrosa | entfällt, Bestand | Aktivitätstyp mail_aus / mail_ein, sichtbar in „letzter Kontakt (Art)“ |
| WhatsApp | dunkelgrün | entfällt, Bestand (Typ vorgesehen) | Aktivitätstyp whatsapp; echter WhatsApp-Versand erst V3 |
| Telefongespräch | hellblau | entfällt, Bestand | Aktivitätstyp anruf mit Ergebnis erreicht |
| Teams Meeting | gelb | geklärt, siehe F12 | Vorschlag: Terminart „Online-Termin (Teams)“ neben „Vor-Ort-Termin“ an `vot_termine` plus Aktivitätstyp online_meeting |

Ergebnis-Erwartung: Die Status-Spalte der Tabelle zeigt die Lead-Phasen (Neu, In Kontaktierung, Qualifiziert, Terminiert, Erfasst, Angebot, Gewonnen, Verloren, Zurückgestellt, Nicht erreicht, Unqualifiziert); Versuche, Sparte und Kontaktart stehen in eigenen Spalten. Wenn du zu einem anderen Schluss kommst, begründe ihn im Bestandsabgleich.

### B. Kundenkartei (Lead-Akte): Aufbau

B1. Dreispaltiges Layout nach Screenshot 2. **Links** breite Spalte mit Kontaktinfos: Anrede, Vorname, Nachname, Telefon (Click-to-Call, siehe D1), E-Mail (mailto), Adresse (Straße, PLZ, Ort), Vertriebskanal, Interessen, Objektart, Innendienst, Außendienst, Quelle/Kampagne, Eingangsdatum, Einwilligungen. Direkt unter dem Namen Aktions-Icons: Anrufen, E-Mail, Notiz, Termin vorschlagen, Wiedervorlage.
B2. **Pflichtfelder ohne Wert erhalten eine rote Umrandung**, zusätzlich ein Zähler „x Pflichtfelder offen“ im Kopf. Definiere die Pflichtfeldliste (Vorschlag: Anrede, Nachname, Telefon, Straße, PLZ, Ort, Vertriebskanal, mindestens eine Interesse, Objektart; bei Mehrfamilienhaus zusätzlich Anzahl Parteien und Rechnungsadresse). Pflichtfeldliste in der Parametrierung pflegbar.
B3. **Objektart** als neues Feld am Kunden/Vorgang mit den Werten Einfamilienhaus, Reihenhaus, Reihenendhaus, Mehrfamilienhaus. Bei Mehrfamilienhaus erscheinen zusätzlich: Anzahl Parteien (Zahl) und Rechnungsadresse (nutzt den bestehenden Kunden-Standard `kunden.rechnung_*` aus v20, keine Doppelstruktur). Prüfe, ob und wie die Objektart den WP-Erfassungsbogen vorbelegen kann.
B4. **Mitte**: Reiter mit Icons statt Textüberschriften (Tooltip mit Bezeichnung, barrierearm): Aktivitäten-Timeline (alle Ereignisse), E-Mail-Verlauf (getrennt filterbar nach eigene, automatisierte, Kollegen; ein- und ausgehend aus `kommunikation_log` und dem Mail-Verlauf), Anrufnotizen (nur `lead_aktivitaeten` vom Typ anruf), Qualifizierung, Termin, Erfassungen/Angebote/Projekt (bestehend). Timeline als Karten mit Titel, Zeitstempel, Autor, aufklappbarem Inhalt, Suchfeld und Filter.
B5. **Rechts**: einklappbare Bereiche mit Zähler: Termine, Angebote, Erfassungen, Projekt, Anhänge, To-Dos zum Vorgang.
B6. **„Termin vorschlagen“**: nutzt den bestehenden Terminassistenten (Top 5 aus AD-Profilen, Tool-Terminen, Outlook-Frei/Belegt über Graph, Fahrzeiten). Die Vorauswahl der Vertriebler ist zwingend an deren Voraussetzungen gekoppelt: Vertriebskanal (Kanal-Regel), Gebiet (PLZ-Präfixe), **Produktkompetenz (neu: Sparten, Kombi- und Objektkompetenz je AD im AD-Profil, Liste in Abschnitt 6, F3)**, Tageskapazität (`max_termine_tag`). Beschreibe das AD-Profil nach Erweiterung vollständig.
B7. **Vor-Ort-Termin manuell eintragen** mit Datum und Uhrzeit (15-Minuten-Raster wie in v17), AD-Auswahl aus den vorgefilterten Vertrieblern, Konfliktwarnung bei Kalenderüberschneidung.
B8. **Button „Terminierung“**: nur aktiv, wenn alle Pflichtfelder (B2) gefüllt sind und ein Termin (B6 oder B7) gesetzt ist; sonst ausgegraut mit Hinweis, welche Felder fehlen. Klick setzt die Phase auf Terminiert, schreibt den Outlook-Termin, löst die Terminbestätigung mit ICS aus und übergibt an „Leads VOT“ (bestehende Übergabe).

### C. Anruf-Workflow und Wiedervorlage

C1. Shortcut-Buttons oben oder rechts in der Kundenkartei (gleiche Buttons wie in der Anrufliste, gleiche Tasten 1 bis 7) für Anrufversuche. **Maximal 5 Versuche**, visuell nachvollziehbar als 5 Punkte/Kreise mit Ergebnis-Farbe und Tooltip (Datum, Uhrzeit, Ergebnis, Benutzer). Abgleich mit der bestehenden Darstellung `versuche_punkte` (grau 1 bis 2, orange 3, rot 4+) und der Kaskade aus der Steuerdatei: Beschreibe, was nach dem 5. Versuch passiert (Phase „Nicht erreicht“, Nurture, Wiedervorlage +30 Tage laut Konzept) und ob die Kaskade auf 5 Stufen angepasst wird.
C2. Button **„nicht erreicht“** öffnet eine Datum/Uhrzeit-Auswahl (Vorschlag aus der Kaskade vorbelegt, manuell änderbar) und erzeugt eine Wiedervorlage mit Glocken-Benachrichtigung zum Zeitpunkt und Anzeige im Dashboard (A1) des Verantwortlichen.
C3. Shortcuts **Mailbox/AB** (zählt als Versuch, Kaskade läuft) und **„kein Interesse“** mit Pflicht-Dropdown der Gründe (Blatt „Gründe“, Phase unqualifiziert) plus optionalem Freitext.
C4. Shortcut **„Disqualifiziert / Nicht erreicht“** löst eine automatisierte E-Mail an den Kunden aus (bestehende Vorlage `nicht_erreicht` bzw. neue Vorlage `disqualifiziert`; Inhalte als Platzhaltertext vorschlagen, Platzhalter `{briefanrede}`, `{vertriebler}`, `{rueckruf_telefon}`, `{sparten}`). Definiere genau, bei welchem Ergebnis welche Mail nach welchem Versuch geht und wie Doppelversand verhindert wird (Warteschlange, Terminstatus-Kopplung aus dem Review 27.09.).

### D. Telefonie-Integration

D1. **Click-to-Call** über jede Telefonnummer (Tabelle, Kartei, Anrufliste) als `tel:`-Link, der das am Arbeitsplatz hinterlegte Telefonieprogramm bzw. das Handy öffnet. **Die Anbindung einer Telefonanlage oder eines Softphones (CTI, automatische Anrufprotokolle, Zuordnung eingehender Anrufe) ist bewusst ausgeklammert und wird in einem späteren Schritt separat angegangen.** Im Lastenheft daher nur: der `tel:`-Link, eine **manuelle Dauer-Erfassung** je Anruf (Stoppuhr im Tool ab Klick auf die Nummer oder den Ergebnis-Button, Wert in `lead_aktivitaeten.dauer_sek`, manuell korrigierbar) und ein kurzer Abschnitt „Vorbereitung für spätere CTI-Anbindung“, der festhält, welche Felder und Ereignisse (Call-ID, Richtung, Beginn/Ende, Nebenstelle je Benutzer) heute schon so angelegt werden, dass eine spätere Anlage ohne Umbau andocken kann. Kein Variantenvergleich, keine Anbieterbewertung.
D2. Button **„Meine Anrufe“**: Liste der eigenen protokollierten Anrufe (aus `lead_aktivitaeten`) mit Datum, Nummer, Vorgang, Ergebnis und Dauer, damit Rückrufe zugeordnet werden können.
D3. **Eingehende Anrufe**: Suchfeld „Rufnummer eingeben“ (E.164-normalisiert, wie in der Duplikatprüfung) mit direktem Sprung in die Kundenkartei; die automatische Erkennung über eine Telefonanlage folgt später (siehe D1).

### E. Terminplanung und Routing

E1. **Routenplaner in der Kartei**: schlägt Termine vor, die zu Wohnort des Kunden, Vertriebskanal und Interessen passen (Erweiterung des Terminassistenten um die Produktkompetenz-Filterung aus B6). Darstellung: Top 5 mit Begründung in Klartext und Mini-Karte (Leaflet lokal, OSM-Kacheln).
E2. **Vorfilterung des Vertrieblers** anhand Kanal, Gebiet, Produktkompetenz und Tageskapazität (Reihenfolge und Härte der Filter definieren: Was ist Ausschluss, was ist nur Abwertung).
E3. **Absage/Umbuchung**: Wird ein Termin abgesagt oder verschoben, schlägt das Tool einen **Ersatzkunden in der Umgebung** vor (offene, qualifizierte Leads im Radius X km um den frei gewordenen Slot, Radius parametrierbar), **ältere Leads bevorzugt** (Eingangsdatum als Gewichtung), und optimiert die Tagesroute (bestehende Bewertungslogik Umweg + Zuschläge erweitern). Beschreibe den Dialog und die Benachrichtigung an das Leadmanagement.
E4. **ICS-Datei in der Terminbestätigung** [Bestand prüfen]: Bestätige, dass die Vorlage `terminbestaetigung` den ICS-Anhang enthält, und ergänze Anforderungen an den ICS-Inhalt (Titel, Adresse des Kunden, Name und Telefon des Vertrieblers, Erinnerung, Absage-Hinweis) sowie an Umbuchung (aktualisiertes ICS mit gleicher UID) und Absage (Storno-ICS).

### G. Handelsvertreter-Ansicht

G1. Neuer Reiter bzw. neue Ansicht **„Handelsvertreter“** im Lead-Management: Innendienst, Leadmanagement und Admin sehen dort alle Handelsvertreter-Leads, gruppier- und filterbar je Vertreter; ein Handelsvertreter sieht ausschließlich die ihm zugewiesenen Leads (server-seitig gefiltert, wie heute bei Leads VOT für den Außendienst).
G2. **Handelsvertreter terminieren ihre Leads eigenständig**, nicht über den Innendienst: Sie dürfen an ihren Leads anrufen und Ergebnisse protokollieren (C1 bis C4), die Kundenkartei bearbeiten, Termine über den Terminassistenten oder manuell (B6/B7) setzen, wobei der Assistent nur den eigenen Kalender rechnet, und den Button „Terminierung“ (B8) auslösen. Danach läuft der Lead wie heute in Leads VOT → Erfassung → Angebot. Preise, EK, DB und Angebotseditor bleiben wie beim Außendienst gesperrt.
G3. **Zuweisung per Dropdown** mit den Namen der Handelsvertreter in Tabelle (A3, Spalte Außendienst), Kundenkartei (B1) und Schnellanlage. Die Namen kommen aus der Benutzerverwaltung (Kennzeichen „Handelsvertreter“ am Benutzer bzw. AD-Profil), nicht aus einer festen Liste im Code. Aktuelle Handelsvertreter: René Golaschewski, Simon O'Grady, Paolo Di Blasi, André Lind, Ralf Kinkel, Hartmut Leinenbach. Bei Zuweisung: Glocken-Benachrichtigung an den Vertreter, Aktivität „zugewiesen an …“ in der Timeline.
G4. **Ausschluss**: Leads der Kanäle bzw. Quellen Empfehlung, Messe, Sparkasse Duisburg, Stadtwerke Düsseldorf (SWD) und Enni werden **nicht** an Handelsvertreter vergeben und ausschließlich vom Innendienst terminiert. Das Dropdown ist bei diesen Leads deaktiviert (mit Hinweis), die Ausschlussliste (Quellen und Kanäle) ist in der Parametrierung pflegbar. Beschreibe, was passiert, wenn der Kanal eines bereits zugewiesenen Leads nachträglich auf einen Ausschlusskanal geändert wird.
G5. **Bestandsabgleich zwingend**: Prüfe, wie sich der Handelsvertreter zur bestehenden Rolle Außendienst und zu den AD-Profilen (Startadresse, Arbeitszeiten, Gebiet, Kapazität) verhält. Vorschlag: keine neue Rolle, sondern Kennzeichen „terminiert selbst“ am AD-Profil, das die erweiterten Rechte (G2) freischaltet; Vor- und Nachteile gegenüber einer eigenen Rolle nennen. Berücksichtige, dass die monday-Boards „Deals - Simon“ und „Deals - Rene“ (Pool Working Space) heute genau diesen Fall abbilden (Sonderregel „Deals - Rene“: Verantwortlicher immer Rene Golaschewski) und dass die neue Ansicht diese Boards perspektivisch ablöst; monday-Sync bleibt trotzdem unverändert.

### H. Modul-Navigation, Boards und Gruppen (Nachtrag 02.10.2026)

H1. **Menü des Lead-Management-Moduls** als schmale Icon-Leiste links mit genau diesen fünf Einträgen (Tooltip mit Bezeichnung): 1 Hauptboard (Leads ohne Vor-Ort-Termin), 2 Terminiert (Leads mit Vor-Ort-Termin), 3 Kontaktiert, 4 Info-Veranstaltung, 5 E-Mail-Vorlagen. Die bestehenden Ansichten (Übersicht/Dashboard, Anrufliste, Kanban, Kalender, Karte, Handelsvertreter) ordnest du diesen fünf Einträgen zu oder begründest, wo sie zusätzlich erreichbar bleiben (z. B. Anrufliste als Umschalter im Hauptboard, Kalender/Karte aus dem Terminassistenten, Handelsvertreter als Filter oder Reiter im Hauptboard). Kein bestehender Einstieg darf verloren gehen; die Tabelle aus A3 ist die Darstellungsform der Boards.
H2. **Status steuert Gruppe:** Jeder Status ist fest einer Gruppe auf einem Board zugeordnet. Beim Setzen eines Status verschiebt das Tool den Lead automatisch in die passende Gruppe bzw. auf das passende Board. Lege die vollständige Zuordnungstabelle Status → Board → Gruppe an und gleiche sie mit den Lead-Phasen und der Mapping-Tabelle in 5a ab (eine Quelle der Wahrheit: die Lead-Phase; die Gruppe ist eine Sicht darauf).
H3. **Markieren und Sammelaktionen:** Jede Zeile hat vorne ein Kästchen; Mehrfachauswahl möglich, Kopfzeile mit „alle sichtbaren markieren“. Sammelaktionen: Hauptboard „Status ändern“; Info-Veranstaltung „Status ändern“ und „In die nächste Veranstaltung verschieben“; Terminiert vorerst keine. Die Zuweisung des Vertrieblers bleibt Einzelaktion je Lead. Die Sammelaktions-Mechanik ist generisch anzulegen (Aktion registrierbar je Board), damit weitere Aktionen später ohne Umbau dazukommen; jede Sammelaktion schreibt je Lead eine Aktivität.
H4. **Hauptboard** (nur Leads ohne Vor-Ort-Termin, also die Kontaktversuche) mit drei Gruppen:
   - **Neu**: noch nicht kontaktierte Leads sowie kontaktierte, aber noch nicht terminierte Leads (Phasen Neu, In Kontaktierung, Qualifiziert); Leads mit Status „Telefongespräch“ (H6) bleiben hier und tragen das Label „Telefongespräch“.
   - **Pausiert**: Status „Zurückgestellt“ oder „Meldet sich selbst“ (Phase Zurückgestellt mit Grund); kein Handlungsbedarf für den Innendienst, bis die Wiedervorlage fällig ist (dann zurück nach Neu, sichtbar markiert).
   - **Disqualifiziert**: automatisch, wenn der 5. Anrufversuch erfolglos war (Phase Nicht erreicht) oder der Status „Kein Interesse“ gesetzt wird (Phase Unqualifiziert mit Pflichtgrund).
   Ziel: Die aktive Liste bleibt kurz. Status „Vor-Ort-Termin vereinbart“ (= Terminierung, B8) verschiebt den Lead automatisch ins Board Terminiert, Gruppe Angebotserstellung.
H5. **Board „Terminiert“** (nur Leads mit Vor-Ort-Termin; hier wird das Angebot nachverfolgt) mit vier Gruppen:
   - **Angebotserstellung**: alle neu terminierten Leads; der Innendienst schreibt das Angebot im Angebotstool desselben Tools (Leads VOT → Erfassung → Angebotseditor). Beschreibe, wie die Gruppe mit den bestehenden Sichten „Leads VOT“, Erfassungsliste und Vorgangsakte verknüpft ist (Buttons „Erfassung starten“, „Angebot öffnen“, Status-Chips je Sparte), ohne diese zu duplizieren.
   - **Angebotsversand**: automatisch, sobald ein Angebot des Vorgangs auf „Versendet“ wechselt (bestehende Versand-Erkennung über Graph); Zweck: Vertriebler fassen nach (Angebot angekommen, alles verstanden). Bestehende Hot-Ampel, Wiedervorlage und Notizen-Chat der Angebotsverfolgung bleiben die Werkzeuge dafür.
   - **Gewonnen**: Status Gewonnen, wenn der Kunde unterschreibt (abgeleitet aus Angebot Angenommen, inkl. E-Signatur).
   - **Verloren**: Status Verloren mit Pflichtauswahl eines Grundes: Zu teuer · Kein Interesse mehr · Bleibt bei Öl/Gas · Woanders unterschrieben · Sonstiges (mit Freitext). Abgleich mit der bestehenden Ablehnungsgründe-Liste in der Parametrierung (eine Liste, Phase-Kennzeichen); Verloren setzt alle offenen Angebote des Vorgangs auf Abgelehnt mit diesem Grund.
   An jedem Lead dieses Boards: Button **„Terminbestätigung erneut senden“** (Vorlage `terminbestaetigung` mit aktuellem ICS, Protokoll als Aktivität; Details folgen in einem nachgereichten Punkt 8 des Auftrags).
H6. **Status „Telefongespräch“** (ersetzt die Deutung in F12 teilweise, siehe unten): wird gesetzt, wenn vor dem Vor-Ort-Termin ein zweites Telefonat mit einem Vertriebler nötig ist, weil der Kunde Fragen hat. Der Innendienst wählt den Vertriebler aus und trägt Datum und Uhrzeit des Telefontermins ein; der Termin erscheint im Tool-Kalender des Vertrieblers und über die bestehende Microsoft-365-Anbindung in seinem Outlook-Kalender. Nach dem Gespräch aktualisiert der Vertriebler den Lead selbst (z. B. Vor-Ort-Termin eintragen) oder schickt eine Notiz an den Innendienst (Notizen-Chat mit @Erwähnung und Glocke). Modelliere „Telefongespräch“ und „Online-Termin (Teams)“ aus F12 als **eine Terminart „Vorab-Gespräch“ mit Medium Telefon oder Teams**, damit es nur einen Workflow gibt; der Lead bleibt dabei in der Gruppe Neu.
H7. **Reiter „Kontaktiert“**: zusätzliche Ansicht, die Leads bleiben auf dem Hauptboard. Zeigt alle Kontaktversuche je Lead mit Datum, Uhrzeit, Ergebnis und Benutzer (Quelle `lead_aktivitaeten`), neueste zuerst, durchsuchbar. Zweck: Ruft ein Kunde zurück, sieht man sofort, wer das ist. Enthält die **Telefonnummernsuche** aus D3: durchsucht alle Leads im Tool, erkennt dieselbe Nummer unabhängig von der Schreibweise („0203…“ und „+49 203…“ sind gleich, Leerzeichen und Trennzeichen werden ignoriert, Normalisierung auf E.164 wie in der Duplikatprüfung).
H8. **Menüpunkt „E-Mail-Vorlagen“**: Zugriff auf die bestehenden Lead-Mail-Vorlagen (Vorlagen-Editor aus der Parametrierung) direkt aus dem Modul für Innendienst/Leadmanagement; Rechte wie heute (Admin/Innendienst pflegen).

### I. Reiter „Info-Veranstaltung“ (Nachtrag 02.10.2026)

I1. **Termine**: jeden Monat am 1. Donnerstag um 18:00 Uhr bei Friondo, Königstraße 102-104, 47798 Krefeld. Fällt der 1. Donnerstag auf einen gesetzlichen Feiertag in NRW, findet die Veranstaltung eine Woche später statt. Die Feiertagsregel ist im Tool zu hinterlegen (feste und bewegliche NRW-Feiertage, Osterformel), nicht von Hand zu pflegen; Termin, Uhrzeit und Ort parametrierbar.
I2. **Gruppen**: je Veranstaltung eine Gruppe. Sofort anzulegen: Oktober 2026 bis einschließlich August 2027; danach legt das Tool die Gruppen automatisch an (rollierend, z. B. immer 12 Monate voraus). Erwartete Termine zur Kontrolle: 01.10.2026, 05.11.2026, 03.12.2026, 07.01.2027, 04.02.2027, 04.03.2027, 01.04.2027, **13.05.2027** (06.05. ist Christi Himmelfahrt), 03.06.2027, 01.07.2027, 05.08.2027; der Chat prüft diese Liste nach. Gruppen einklappbar; vergangene Veranstaltungen werden archiviert (Filter „Archiv“), Leads bleiben erhalten.
I3. **Aufbau jeder Gruppe** wie die Liste des Hauptboards (gleiche Spalten, Status, Ergebnis-Buttons und Funktionen): Info-Leads werden direkt auf diesem Board angerufen und terminiert. Zusätzliche Spalte **„Teilgenommen“** (Ja/Nein, leer bis zur Veranstaltung). Sammelaktion „In die nächste Veranstaltung verschieben“ verschiebt markierte Leads in die Gruppe der nächsten Veranstaltung (Aktivität je Lead). Beschreibe, wie Info-Leads zu den Lead-Phasen und zum Hauptboard stehen (Vorschlag: eigene Quelle „Info-Veranstaltung“ mit Kennzeichen Veranstaltungstermin; nach Terminierung wechseln sie wie alle anderen ins Board Terminiert).
I4. **Eingang**: Anmeldungen kommen über die API der Marketingagentur (bestehender Endpunkt `POST /api/leads` mit API-Key je Quelle; prüfe, welche Felder zusätzlich nötig sind). Die API liefert den gewählten Veranstaltungstermin **nicht** mit; die Zuordnungsregel Lead → Veranstaltung wird nachgereicht **[OFFEN 1]**. Bis dahin: Vorschlag „nächste Veranstaltung ab Eingangsdatum + X Tage Vorlauf“ als parametrierbare Standardregel, manuell änderbar.
I5. **Abgleich bei der Anmeldung** (nur beim Eingang über die API): Treffer, wenn E-Mail-Adresse **oder** Telefonnummer übereinstimmt **und** zusätzlich mindestens der Nachname gleich ist; Telefonnummern werden wie bei der Suche normalisiert verglichen (H7). Bei Treffer erhält der Lead am Kasten einen **roten Hinweis „Kunde bereits im System“** mit Link zum bestehenden Vorgang; so sieht man sofort, dass der Kunde bekannt ist (z. B. schon Vor-Ort-Termin hatte) und nicht angerufen werden muss. Abgleich mit der bestehenden Duplikatprüfung (Telefon E.164, E-Mail, Name+PLZ, Adresse): dieselbe Funktion, nur andere Trefferregel und andere Darstellung; kein automatisches Zusammenführen bei Info-Leads. Der Auftragstext bricht nach „Duplikate, die das Tool selbst erzeugt (siehe nächster …“ ab; dieser Teil und Punkt 8 werden **nachgereicht [OFFEN 2]**.

### F. Entscheidungen (bereits getroffen, nicht wieder zur Diskussion stellen)

- Lead-Übersicht als Tabelle mit mehreren Spalten nach monday-Vorbild, zusätzlich zur Anrufliste.
- Status-Spalte zeigt Lead-Phasen; monday-Status werden über die Mapping-Tabelle (Abschnitt 5a) abgebildet, Farben an monday angelehnt. Gestrichene monday-Status (Export, AB gesprochen, Reklamation, Nicht erreicht disqualifiziert) entfallen ersatzlos.
- Handelsvertreter-Ansicht mit eigenständiger Terminierung; Ausschluss von Empfehlung, Messe, Sparkasse Duisburg, Stadtwerke Düsseldorf und Enni; Zuweisung immer manuell, Simon O'Grady verantwortlich für alle außer René Golaschewski.
- Neue Sparte „Gewerbe“; Produktkompetenz je AD inkl. Kombi-Kompetenz WP+PV(+KL) und Objektkompetenz MFH (Abschnitt 6, F3).
- Terminart „Vorab-Gespräch“ (Telefon mit Vertriebler oder Teams mit Kollegen, Outlook-Buchungslink möglich); Kennzeichen „Vorab-Angebot“ ohne Terminbestätigung.
- Modul-Menü mit fünf Icons (Hauptboard, Terminiert, Kontaktiert, Info-Veranstaltung, E-Mail-Vorlagen); Status steuert Gruppe; Sammelaktionen über Markier-Kästchen.
- Verloren-Gründe: Zu teuer · Kein Interesse mehr · Bleibt bei Öl/Gas · Woanders unterschrieben · Sonstiges mit Freitext.
- Info-Veranstaltung monatlich am 1. Donnerstag 18:00 Uhr in Krefeld, Feiertagsregel NRW, Gruppen Oktober 2026 bis August 2027 sofort.
- Kunden werden bis zu 5 Mal angerufen, Versuche visuell sichtbar.
- Objektarten: Einfamilienhaus, Reihenhaus, Reihenendhaus, Mehrfamilienhaus; bei Mehrfamilienhaus Zusatzfelder Anzahl Parteien und Rechnungsadresse.
- Reiter in der Kundenkartei mit Icons statt Überschriften.
- Nicht ausgefüllte Pflichtfelder in der Kundenkartei mit roter Umrandung.
- Click-to-Call vorerst nur als `tel:`-Link mit manueller Dauer-Erfassung; Telefonanlage/Softphone-Anbindung wird später separat behandelt und ist nicht Teil dieses Lastenhefts.

## 6. Festlegungen aus der Abstimmung (bereits beantwortet, als Vorgaben übernehmen)

F1. **Statusliste:** Die Vorab-Bewertung in Abschnitt 5a gilt wie dort beschrieben; die drei offenen Status sind in F10 bis F12 geklärt.
F2. **Telefonie:** Keine Telefonanlagen- oder Softphone-Anbindung in diesem Lastenheft (siehe D1); nur `tel:`-Link und manuelle Dauer. Das Thema wird später gesondert bearbeitet.
F3. **Produktkompetenz der angestellten Außendienstler** (im AD-Profil hinterlegen, Pflege durch Admin):
   - Horst: WP, WP+PV(+KL), WB
   - Detlev B.: WP, WP+PV(+KL), PV, WB
   - Detlef J.: WP, WP+PV(+KL), KL, PV, WB
   - Kyriakos: WP, WP+PV(+KL), KL, WB, MFH, Gewerbe
   - Rudi: WP, PV, KL
   Daraus folgt für das Datenmodell: (a) **„Gewerbe“ ist als neue Sparte zu ergänzen** (neben WP/PV/KL/WB; Auswirkungen auf Interessen-Badges, Filter, Statistik, Angebotsprofile und monday-Mapping benennen); (b) „WP+PV(+KL)“ ist eine **Kombi-Kompetenz** (ein Lead mit mehreren Interessen braucht einen AD, der die Kombination darf, nicht nur jede Sparte einzeln); (c) „MFH“ ist eine **Objektkompetenz** (Objektart Mehrfamilienhaus aus B3, nur AD mit dieser Kompetenz). Modelliere das AD-Profil so, dass alle drei Arten abgebildet sind, und beschreibe die Filterregel des Terminassistenten (B6/E2) darauf.
F4. **Termindauer und Puffer:** Termindauer 90 Minuten. Puffer zwischen zwei Terminen **mindestens 30 Minuten, bei größerer Fahrzeit die berechnete Fahrzeit** (Puffer = max(30 Min, Fahrzeit zwischen den Terminen)). Raster 30 Minuten bleibt. Tageskapazität je AD weiterhin im AD-Profil (`max_termine_tag`), Startwert vom Chat vorschlagen.
F5. **Gründe:** Bestehende Werte aus dem Blatt „Gründe“ verwenden, keine neuen Listen.
F6. **Eigene Dashboards** zunächst nur für Innendienst, Leadmanagement und Admin. Außendienst bleibt bei der bestehenden Sicht (Meine Termine, Leads VOT). Handelsvertreter siehe F16.
F7. **To-Dos:** Jeder darf jedem To-Dos zuweisen. Benachrichtigung über die Glocke mit **Zähler-Badge** (Anzahl ungelesener Benachrichtigungen als Zahl am Glockensymbol, wie bei Apps); keine Mail.
F8. **Ersatzkunde bei Absage:** Suchradius zunächst 5 km um den frei gewordenen Slot, bei zu wenigen Treffern schrittweise auf 10 km ausweiten (Stufen parametrierbar). Gewichtung: ältere Leads bevorzugt (ab 14 Tagen seit Eingang), aber **mehrere Kandidaten vorschlagen, auch neuere**, mit Begründung je Vorschlag (Entfernung, Alter, Score).
F9. **Mail-Texte** für „nicht erreicht“ und „disqualifiziert“ liegen vor; der Chat liefert keine Entwürfe, sondern nur die Platzhalterliste und die Auslöseregeln.
F10. **„Vorab Angebot“** = Angebot ohne Vor-Ort-Termin; für diesen Fall ist keine Terminbestätigung nötig. Umsetzung als Kennzeichen „Vorab-Angebot“ am Vorgang/Angebot, keine eigene Phase; der Lead springt von Qualifiziert direkt in die abgeleitete Phase Erfasst/Angebot. Beschreibe, welcher Weg (Freitext-Erfassung ohne VOT?) dafür im Bestand genutzt wird und was an „Leads VOT“ vorbei laufen muss.
F11. **„Nachbearbeitung“** = Kunde ist noch nicht bereit für einen Vor-Ort-Termin (z. B. Unterlagen, Entscheidung, Finanzierung offen). Vorschlag: Zurückgestellt mit Grund „Nachbearbeitung, noch nicht bereit für VOT“ und Pflicht-Wiedervorlage; alternativ eigener Seitenzustand „Nachbearbeitung“ in der Phase Qualifiziert. Der Chat entscheidet mit Begründung und zeigt, wie der Lead in Dashboard und Tabelle sichtbar bleibt.
F12. **„Teams Meeting“** = Online-Termin per Teams mit einem Kollegen des Innendienstes **anstelle** eines Vor-Ort-Termins, meist bei vielen Fragen vorab. Anforderungen: Terminart „Online-Termin (Teams)“ neben „Vor-Ort-Termin“; Option, dem Kunden per Mail den persönlichen **Outlook-Buchungslink („Book with me“) des Kollegen** zu senden, über den der Kunde den Slot selbst wählt (Beispiel: Buchungsseite „Teams-Besprechung mit Nikolaos Goritsas“ unter outlook.office.com/bookwithme/…). Je Benutzer wird der Buchungslink in der Benutzerverwaltung hinterlegt; Mail-Vorlage `online_termin_einladung` mit Platzhalter `{buchungslink}` und `{kollege}`. Beschreibe, wie der gebuchte Teams-Termin zurück ins Tool kommt (Outlook-Kalender des Kollegen über Graph lesen, oder manuelles Eintragen als Fallback) und dass ein Online-Termin die Phase nicht auf Terminiert setzt (kein VOT), sondern als Aktivität/Termin eigener Art gezählt wird.
F13. **Handelsvertreter, Zuweisung:** immer manuell, keine Automatik. **Simon O'Grady ist der Verantwortliche für alle Handelsvertreter-Leads außer denen von René Golaschewski** (bestehende monday-Sonderregel „Deals - Rene“ bleibt). Neue Handelsvertreter-Leads landen also standardmäßig bei Simon, der sie weitergibt; die Handelsvertreter dürfen Leads **untereinander frei umverteilen** (Dropdown für alle Vertreter sichtbar, jede Umverteilung als Aktivität protokolliert, Glocke an den neuen Vertreter).
F14. **Handelsvertreter, Ausschluss (ersetzt die Liste in G4):** Alle Vertriebskanäle gehen an Handelsvertreter **außer** Empfehlung, Stadtwerke Düsseldorf (SWD), Sparkasse Duisburg, Messe und **Enni**. Diese fünf werden ausschließlich vom Innendienst terminiert. Liste in der Parametrierung pflegbar.
F15. **Handelsvertreter, Zugang:** Alle sechs haben einen Tool-Zugang und ein eigenes Outlook-Postfach (Kalenderabgleich über Graph möglich). Ob eigene Rolle oder Kennzeichen am AD-Profil, entscheidet der Chat mit Empfehlung (G5).
F16. **Handelsvertreter, Sichten:** Sie erhalten Dashboard (A1) **und** Tabelle (A3) in einer auf ihre eigenen Leads beschränkten Form, zusätzlich zum Reiter „Handelsvertreter“ (der für Innendienst/Admin die Gesamtsicht über alle Vertreter ist).

### Verbleibende Rückfragen

Stelle nur noch Fragen, die beim Bestandsabgleich neu entstehen, gesammelt in einer Nachricht mit deinem Vorschlag als Standardantwort. Antworte ich „weiter mit Vorschlägen“, nimmst du deine Standardantworten und kennzeichnest sie im Lastenheft als Annahme. Keine der Festlegungen F1 bis F16 darf erneut gefragt werden. Bekannt offen und im Lastenheft als Platzhalter zu führen: [OFFEN 1] Zuordnungsregel Info-Lead → Veranstaltung, [OFFEN 2] fehlender Rest des Auftragstexts (Duplikate durch das Tool, Punkt 8 „Terminbestätigung erneut senden“ und eventuell weitere Punkte).

## 7. Aufbau des Lastenhefts (genau diese Gliederung)

1. **Zusammenfassung** (max. 15 Zeilen: Ziel, Nutzen, größte Änderungen).
2. **Bestandsabgleich** als Tabelle: Anforderung | Kennzeichnung [Bestand/Erweiterung/Neu] | Verweis CLAUDE.md | Kurzbegründung.
3. **Anforderungen je Bereich A bis E sowie G bis I**, jede Anforderung mit eindeutiger ID (LM2-A01, LM2-A02, …), Beschreibung, Rolle(n), Vorbedingung, Ablauf, Nachbedingung, **Akzeptanzkriterien** (prüfbar formuliert: „Wenn … dann …“), Abhängigkeiten zu anderen IDs.
4. **Datenmodell-Änderungen**: neue Felder und Tabellen mit Name, Typ, Pflicht, Herkunft; neue Blätter oder Spalten in `leadmanagement_logik_v1.xlsx`; neue Parameter in der Parametrierung (Key, Standardwert, Bedeutung).
5. **Oberfläche**: je Seite (Dashboard, Hauptboard, Board Terminiert, Kontaktiert, Info-Veranstaltung, Kundenkartei, Handelsvertreter-Ansicht, Terminassistent, Meine Anrufe) eine Skizze in Textform (Bereiche, Spalten, Buttons, Zustände) plus Hinweis, was im Prototyp `docs/leadmanagement-prototyp.html` zu ergänzen ist.
6. **Schnittstellen**: Outlook/Graph (Kalender, Mail), Routing/Geocoding, ICS; je Schnittstelle übertragene Daten, Berechtigungen, AVV-Bedarf, Fallback bei Ausfall.
7. **Rollen und Rechte**: Matrix Funktion × Rolle (sehen / bearbeiten / auslösen).
8. **Demo-Modus und Rollout**: Was im Demo-Modus gesperrt bleibt, was bei `alle` scharf wird; Migrationsbedarf (z. B. Objektart für Bestandskunden leer, Pflichtfeld-Zähler rückwirkend).
9. **Priorisierung**: Stufe 1 (Pflicht für den nächsten Plan), Stufe 2, Stufe 3; je Stufe Aufwandsklasse klein/mittel/groß und Begründung.
10. **Offene Entscheidungen für Andreas**: nummeriert, je Punkt Optionen, Empfehlung, Konsequenz bei Nichtentscheidung.
11. **Annahmen**, die du getroffen hast (nummeriert).
12. **Glossar** der neuen Begriffe.

## 8. Qualitätsregeln

- Keine Anforderung aus Abschnitt 5 darf fehlen. Prüfe am Ende Punkt für Punkt gegen A1 bis E4, G1 bis G5, H1 bis H8, I1 bis I5, F und die Festlegungen F1 bis F16 sowie jede Zeile der Statusliste in 5a und liste die Abdeckung in einer Checkliste (Diktatpunkt → LM2-ID).
- Keine Widersprüche zu den Rahmenbedingungen in Abschnitt 3. Wo das Diktat dem Bestand widerspricht (z. B. 5 Versuche gegen die bestehende Kaskade), benenne den Konflikt ausdrücklich und schlage eine Auflösung vor, statt stillschweigend zu entscheiden.
- Jede Akzeptanzbedingung muss ohne Blick in den Code prüfbar sein.
- Keine Technologie-Entscheidungen, die nicht fachlich begründet sind; Technik nur dort, wo die Fachlichkeit sie erzwingt (Graph, ICS, E.164).
- Keine Füllsätze, kein Marketing-Ton. Tabellen, wo sie Vergleiche tragen; sonst Fließtext und kurze Listen.
- Schreibe Gedankenstriche nicht; nutze Kommas, Doppelpunkte oder Klammern.
- Umfang: so lang wie nötig, voraussichtlich 8 bis 15 Seiten.

## 9. Ablage und Übergabe

- Speichere das fertige Lastenheft im Projektwissen als `claude/LASTENHEFT-LEADMANAGEMENT-V2.md` (Datum und Stand im Kopf, Basis CLAUDE.md v21).
- Schließe mit einer kurzen Nachricht ab: Was ist Stufe 1, welche Entscheidungen braucht Andreas, welche Rückfragen sind noch offen. Kein Plan, kein Code, kein Git.
