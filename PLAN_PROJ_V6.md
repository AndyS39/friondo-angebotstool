# Umsetzungsplan Projektierung V6 – Pilot-Feedback 1 (Board, Termine, Besetzung, Notizen, Montage-Backend, Formulare)

Voraussetzung: kein anderer Plan in Umsetzung (strangübergreifend). Reihenfolge
laut Abstimmung 06.10.2026: erst PLAN_PROJ_V5 (v26, Phasen 122–126, Rollout),
dann PLAN_V17 (v27, Phasen 127–132, Angebotstool-Chat), **dann dieser Plan**.
Vor der Übergabe fragt der Planungs-Chat erneut ab, ob V5 und V17 committet,
gepusht und auf dem Server sind. CLAUDE.md und `projektierung_logik_v1.xlsx`
sind Live-Master im Projektordner `C:\Users\a.scheelen\Tools\Angebotstool`
(Git-Arbeitskopie). ALLE PHASEN DIESES PLANS IN EINEM DURCHLAUF UMSETZEN
(Reihenfolge einhalten, jede Checkbox nach Umsetzung und Test abhaken, am Ende
Gesamtübersicht mit Testergebnissen und offenen Punkten, fachliche Rückfragen
gebündelt). migrate.py idempotent. **Kein git push vor Freigabe.**

CLAUDE-Abschnitt: **„Neu in v28“** [ANNAHME: v26 = PLAN_PROJ_V5, v27 = PLAN_V17
– vor dem Bau gegen die Zuordnungstabelle in CLAUDE.md prüfen und bei Abweichung
die nächste freie Nummer nehmen]. Phasen **133–139** [ANNAHME: 127–132 gehören
zu PLAN_V17; bei Abweichung die nächsten freien Nummern nehmen und die
Phasennummern in diesem Plan durchgängig ersetzen].

Geltungsbereich: Modul Projektierung (`app/projektierung.py`,
`app/routers/projektierung.py`, `app/routers/montage.py`,
`app/montage_formulare.py`, `app/projektierung_logik.py`, Templates unter
`templates/projektierung/`, `templates/montage/`, `_galerie.html`), das Blatt
„Formulare“ und das Blatt „Aufgabenpakete“ der `projektierung_logik_v1.xlsx`,
der Notizen-Chat des Vorgangs (`VorgangsNotiz`, v10 – nur Anzeige und
bestehende Schreibroute, keine neue Notizlogik) sowie die Stücklisten-Nachträge
(Phase 139). Angebotstool-Logik, Lead-Management-Logik, monday-Sync,
Angebots-PDF und Heizreport-Anbindung (V5) bleiben unberührt. Projektierung
läuft weiter im `freigabe_modus` wie eingestellt (Pilot).

Dieser Plan wurde gegen CLAUDE.md v25 und den Code-Stand vom 06.10.2026
geschrieben (vor Abschluss von V5). Stellen, die V5 verändert
(`templates/projektierung/akte.html`, `_aufgabe.html`, Parametrierungs-Seiten,
Benutzerliste), vor dem Bau gegen den Stand nach V5/V17 abgleichen; die
Checkboxen beschreiben das Soll, nicht Zeilennummern.

## Entscheidungen (Chat Projektierung, 06.10.2026, Andreas)

- **Team-Konzept = „Besetzung je Termin“:** Teams bleiben Stammdaten und
  Vorlage; am Termin wird die Mannschaft (Monteure) gesetzt und ist änderbar.
  Jeder Monteur hat einen eigenen Zugang (Rolle Montage) und ein Stamm-Team
  (Dropdown am Benutzer aus V5). Der Monteur sieht die Einsätze, in denen er
  eingeteilt ist; das Montageteam ist am Termin wechselbar (protokolliert,
  Outlook folgt).
- **Wächter nur warnen:** Parameter `waechter_modus` (warnen | sperren),
  Standard **warnen**. Phasenwechsel ist immer möglich; offene Pflichtaufgaben
  werden im Dialog gezeigt, Begründung optional (bei rückwärts weiterhin
  Pflicht). „sperren“ = bisheriges Verhalten (Override nur mit Begründung).
  Zusätzlich Zustand **„entfällt“ mit Grund** je Aufgabe. Die Frage, ob der
  Override im Board sichtbar ist, ist damit erledigt (im Modus warnen gibt es
  keinen Override mehr).
- **Notizen über alle Phasen:** Der Notizen-Chat des Vorgangs (v10) ist die
  einzige Notizspur von Lead bis Montage. Projektakten-Kommentare gehen darin
  auf. **Der Monteur liest nur** – er schreibt über das Feld „Bemerkungen des
  Monteurs“ im Montagebericht.
- **Ein Termin-Dialog** für alle Terminarten (die heutigen vier Einstiege
  widersprechen sich – siehe Phase 135). **Terminvorschläge Stufe 1** aus
  Tool-Daten; Stufe 2 (Outlook-Frei/Belegt) erst nach Einrichtung des
  Kalender-Syncs (Go-live-Checkliste Punkt 2) – nicht Teil dieses Plans.
- **Montage-Backend** in neuer Reihenfolge, Block „Offene Montage-Aufgaben“
  entfällt, „Montage beenden“ als Button und automatisch mit der Abnahme.
- **Formulare:** Montagebericht ohne Arbeitsbeginn/-ende, Nachbestellung und
  Regie, dafür „Bemerkungen des Monteurs“ und Foto-Felder; Inbetriebnahme-
  protokoll mit Seriennummern + Systemkomponenten als Wiederholfeld und den
  elf Fragen von Andreas (Wortlaut in Phase 138, verbindlich).
- Screenshots der widersprüchlichen Termin-Dialoge sind nicht nötig – die
  Widersprüche sind aus dem Code belegt (Phase 135).

## Phase 133 – Wächter „warnen“, Aufgaben „entfällt“, Bedingungen in der Live-Excel

- [x] **Parameter `waechter_modus`** (Werte `warnen` | `sperren`, Standard
      `warnen`) in den Projektierung-Einstellungen der Parametrierung
      (Abschnitt „Board & Wächter“, mit Erklärtext: „warnen: Phasenwechsel
      immer möglich, offene Pflichtaufgaben werden angezeigt · sperren:
      Wechsel nur mit Begründung“). `kern.waechter_modus(session)` liefert
      den Wert; Änderung wird im Verlauf der Parametrierung protokolliert wie
      die übrigen Projektierungs-Parameter.
- [x] **`kern.phase_wechseln`** (app/projektierung.py): `waechter_pruefen`
      liefert weiterhin die Liste offener Punkte. Im Modus `warnen` blockiert
      die Liste nicht mehr; der Verlaufstext lautet
      „Phase des Gewerks <Sparte> geändert: <alt> → <neu> – mit offenen
      Punkten: <Liste>“ bzw. mit Begründung „… – mit offenen Punkten:
      <Liste> – Begründung: <Text>“. Rückwärts-Wechsel bleibt in beiden Modi
      nur mit Begründung („Rückwärts-Wechsel nur mit Begründung“). Modus
      `sperren` = Verhalten wie heute (Meldung „Wächter: … – Override nur mit
      Begründung.“). `abgeschlossen` bleibt in beiden Modi nur über
      „Rechnung freigeben“ erreichbar; `montage_fertig_am` wird wie bisher
      beim Wechsel nach Abnahme/Freigabe gesetzt.
- [x] **Dialog „Phase ändern“ (Akte, `dlg-phase-<gewerk>`)** und der neue
      Board-Dialog (Phase 134) laden die offenen Punkte per
      `GET /projektierung/gewerk/{id}/waechter?ziel=<phase>` (JSON:
      `{modus, rueckwaerts, offen: [{text, aufgabe_id|null, pflicht}],
      begruendung_pflicht}`) und zeigen sie als Liste mit je einem Häkchen
      „erledigt“ und einem Knopf „entfällt“ (siehe nächster Punkt) – Aufgaben
      lassen sich direkt im Dialog abhaken (bestehende Route
      `POST /projektierung/aufgabe/{id}/erledigt-umschalten`, per fetch, JSON
      bei Accept application/json). Begründungsfeld: Pflicht nur bei
      `begruendung_pflicht` (rückwärts oder Modus sperren), sonst optional
      mit Platzhalter „optional“. Der Hinweistext im Dialog richtet sich nach
      dem Modus (warnen: „Offene Punkte blockieren nicht – sie werden im
      Verlauf vermerkt.“).
- [x] **„entfällt“ mit Grund:** neue Spalte `aufgaben.entfaellt_grund`
      (String 300, Migration idempotent). Route
      `POST /projektierung/aufgabe/{id}/entfaellt` (Formular `grund`, Pflicht,
      max. 300 Zeichen) setzt `status = entfaellt`, `entfaellt_grund`,
      `erledigt_am = jetzt`, `erledigt_von`; Verlauf „Aufgabe „<Titel>“ entfällt
      – <Grund>“; `POST …/wieder-aufnehmen` setzt zurück auf `offen` und
      leert den Grund (Verlauf). Beide Routen in der Akte (`_aufgabe.html`:
      Knopf „entfällt“ mit Inline-Grundfeld, Badge „entfällt · <Grund>“ als
      Tooltip, Knopf „wieder aufnehmen“) und in „Meine Aufgaben“. Bestehende
      Auswahl-Aufgaben (Option ohne `*` = entfällt, `aufgabe_auswahl_setzen`)
      bleiben unverändert und tragen als Grund die gewählte Option.
      `_pflicht_offen_in_paketen`, `planungs_ampel`, Wächter und Kacheln
      zählen `entfaellt` weiterhin nicht als offen (bestehender Filter
      `status != "entfaellt"` – prüfen, dass `planungs_ampel` und die
      Startseiten-Kacheln ihn ebenfalls haben).
- [x] **Arbeitsanweisung Live-Excel, Blatt „Aufgabenpakete“** (Spalten
      `sichtbar_wenn` und `optionen`; Sicherung
      `diagnose/projektierung_logik_v1.vor_v28.xlsx` vorher anlegen):
      - `auftragseingang` Schritt 4 „BzA erstellen und an Kunden senden“:
        `sichtbar_wenn = foerderung:ja`; `freigabe` Schritt 2 „BnD nach
        Abnahme erstellt“: `sichtbar_wenn = foerderung:ja`. Neue
        Bedingungsform `foerderung:ja|nein` in `_schritt_sichtbar` und
        `abhaengige_pruefen`: wertet `bza.ist_gefoerdert(gewerk)` aus; bei
        „unbekannt“ bleibt der Schritt sichtbar (nie blockieren). Bei
        Änderung von `kfw_gefoerdert` am Angebot oder der Auftragsdaten
        werden die Schritte nachgezogen (`steckbrief_schritte_nachziehen`
        bzw. ein neuer Hook `foerderung_schritte_nachziehen`, aufgerufen von
        der Route, die `kfw_gefoerdert` setzt).
      - `planung_wp` Schritt 5 „Öltank-Entsorgung“: `sichtbar_wenn =
        steckbrief:oeltank=ja` (Werte laut Blatt Steckbrief ja/nein).
      - `pv_standard` Schritt 3 „Gerüst bestellen“: `sichtbar_wenn =
        steckbrief:geruest=ja` [ANNAHME: Steckbrief-Feld `geruest` kommt heute
        nur aus den Auftragsdaten; fehlt der Wert, bleibt der Schritt sichtbar].
      - `planung_elektro` Schritt 1 „Elektro-Montageteam zuweisen“:
        `sichtbar_wenn = planung_elektro.3=erfolgt über Friondo` [ANNAHME:
        Elektro-Team nur, wenn die Elektro-Leistung über Friondo läuft; bei
        „Sub beauftragt“ oder „bauseits“ entfällt der Schritt automatisch].
      - `montagevorbereitung` Schritt 1 „Anzahlung geschrieben“: `aktion_typ =
        auswahl`, `optionen = keine Anzahlung | geschrieben*`; Schritt 2
        „Anzahlung bezahlt“: `sichtbar_wenn = montagevorbereitung.1=geschrieben`.
      - `abnahme` Schritt 4 „Restarbeiten/Reklamationen erfasst“: `aktion_typ =
        auswahl`, `optionen = keine* | erfasst*`; Schritt 5 „Abweichungen zum
        Angebot geprüft, ggf. Nachtrag“: `aktion_typ = auswahl`, `optionen =
        keine Abweichungen* | Nachtrag erstellt*`; `feinplanung_vot` Schritt 4
        (gleicher Titel) ebenso.
      - Alle übrigen Zeilen unverändert; `pflicht = J` bleibt (im Modus
        warnen bedeutet Pflicht nur „wird angezeigt“).
      „Logik prüfen“ kennt `foerderung:` und meldet unbekannte
      `sichtbar_wenn`-Formen weiterhin als Hinweis. Blatt „Lesehilfe“ (falls
      vorhanden, sonst Spalte Beschreibung der ersten Zeile) um einen Satz
      zu `foerderung:ja` ergänzen. Bestehende Gewerke: beim nächsten
      `abhaengige_pruefen`/Nachziehen werden Schritte, deren Bedingung nicht
      erfüllt ist, auf `entfaellt` mit Grund „Bedingung nicht erfüllt
      (<Bedingung>)“ gesetzt (Verlauf), nicht gelöscht.
- [x] Kontrollwerte: Gewerk in `planung` mit drei offenen Pflichtaufgaben →
      Modus `warnen`: `phase_wechseln(…, "montagevorbereitung", "")` liefert
      `(True, …)`, Verlauf enthält „mit offenen Punkten: Planungs-Pakete: 3
      von …“; Modus `sperren`: `(False, "Wächter: …")`. Rückwärts
      `montagevorbereitung → planung` ohne Begründung in beiden Modi `False`.
      Aufgabe „Öltank-Entsorgung“ bei Steckbrief `oeltank = nein` → Status
      `entfaellt`, Grund „Bedingung nicht erfüllt (steckbrief:oeltank=ja)“;
      bei `oeltank = ja` offen. `POST …/entfaellt` ohne Grund → 400/Meldung
      „Bitte einen Grund angeben.“

## Phase 134 – Board: Scrollen, Drag & Drop zwischen Phasen, volle Breite

- [x] **Volle Breite:** `main.breit` in `style.css` auf `max-width: none`
      (Innenabstand 16 px) und die Klasse auf allen Projektierungs-Seiten
      setzen (`/projektierung`, `/liste`, `/kalender`, `/termine`,
      `/meine-aufgaben`, `/projekt/<id>` – `{% block mainklasse %}breit{%
      endblock %}`). Angebotstool- und Lead-Seiten bleiben wie bisher.
      Board-Spalten `flex: 1 1 0; min-width: 240px` [ANNAHME], die Anzahl
      sichtbarer Spalten ergibt sich aus der Monitorbreite (heute neun
      Spalten: zwei Auftragseingang, sechs Phasen, Abgeschlossen; Storniert
      nur mit Filter). Kontrollwert: bei 1.920 px Breite sind mindestens
      sieben Spalten ohne waagerechtes Scrollen sichtbar, bei 2.560 px alle
      neun.
- [x] **Senkrecht je Spalte, Köpfe fest:** `.pj-board` erhält die Höhe
      `calc(100vh – <Kopf/Kacheln/Filter>)` (Wert per JS aus der Position des
      Boards berechnet, Mindesthöhe 480 px); jede `.pj-col` scrollt für sich
      (`overflow-y: auto`), der Spaltenkopf (`h3` mit Zähler) ist `position:
      sticky; top: 0`. Die Spalte `abgeschlossen` bleibt als `details`
      einklappbar.
- [x] **Horizontaler Balken dauerhaft sichtbar, oben und unten:** das Board
      scrollt waagerecht (`overflow-x: auto`, Scrollbalken immer sichtbar –
      `scrollbar-gutter: stable`, WebKit-Scrollbar 12 px); zusätzlich ein
      synchronisierter Dummy-Scrollbalken **über** dem Board (`div.pj-hscroll`
      mit gleicher Scrollbreite, `scroll`-Ereignisse in beide Richtungen
      gekoppelt), damit der Balken auch ohne Scrollen nach unten erreichbar
      ist. Shift + Mausrad scrollt waagerecht (Browser-Standard; zusätzlich
      ein `wheel`-Handler, der `deltaY` bei gedrückter Shift-Taste auf
      `scrollLeft` legt, falls der Browser es nicht selbst tut).
- [x] **Drag & Drop zwischen Phasen mit Dialog:** `kartenDrop` sendet nicht
      mehr sofort (`dropSenden`), sondern öffnet den Dialog „Phase ändern“
      (`dlg-phase-board`, einmal pro Seite) mit Zielphase, Liste der offenen
      Punkte aus `GET /gewerk/{id}/waechter?ziel=…` (Häkchen „erledigt“,
      Knopf „entfällt“ wie in Phase 133), Begründungsfeld (optional/Pflicht
      laut JSON) und Knöpfen „Verschieben“ / „Abbrechen“. Senden per fetch an
      `POST /gewerk/{id}/phase-drop` (JSON-Antwort bei Accept
      application/json: `{ok, meldung}`); bei `ok` wird die Karte ohne
      Neuladen in die Zielspalte verschoben (Zähler der Spalten und Kacheln
      aktualisiert), sonst Meldung im Dialog. Karten mit mehreren offenen
      Gewerken fragen weiterhin zuerst „Welches Gewerk verschieben?“.
      Rückwärts-Drop öffnet denselben Dialog mit Begründung Pflicht. Drop von
      `auftragseingang_unterminiert` auf `…_terminiert` öffnet weiterhin den
      Termin-Dialog (jetzt den gemeinsamen aus Phase 135); der umgekehrte
      Weg zeigt statt des Alert-Textes den Hinweis „Termin in der Projektakte
      löschen (Block Termine)“ – die Löschfunktion gibt es ab Phase 135.
      `abgeschlossen` bleibt kein Drop-Ziel; `storniert` auch nicht.
- [x] Hinweistext unter dem Board (`pj-note`) anpassen: „Karte = Projekt …
      Ziehen in eine andere Phase öffnet den Dialog „Phase ändern“ (offene
      Pflichtaufgaben werden gezeigt, blockieren im Modus „warnen“ nicht).“
- [x] Kontrollwerte (Playwright, Chromium 1366 × 768 und 1920 × 1080):
      Board-Höhe ≤ Viewport, kein Seiten-Scroll bei 30 Karten in einer
      Spalte; Dummy-Scrollbalken oben vorhanden und synchron (scrollLeft
      gleich); Drop `planung → montagevorbereitung` mit offenen Punkten im
      Modus warnen: Dialog zeigt „3 offene Punkte“, „Verschieben“ ohne
      Begründung → Karte wandert, Verlaufseintrag vorhanden. `tests/`:
      Route `GET /gewerk/{id}/waechter?ziel=montage` liefert
      `begruendung_pflicht = false` (warnen) bzw. `true` (sperren).

## Phase 135 – Termine: ein Dialog, Block „Termine“, Besetzung je Termin, Terminvorschläge

Befund (Code 06.10.2026): Montagetermine entstehen über vier Wege mit
unterschiedlichen Feldern – (1) `dlg-termin-<gewerk>` in der Akte (Typ, Beginn
mit Uhrzeit, Ende, Notiz, Kunde bestätigt – **ohne Team/Person**, obwohl
`POST /gewerk/{id}/termin` bei Typ Montage ein Team verlangt → Meldung
„Montagetermine brauchen ein Team“), (2) `dlg-team-<gewerk>` „Team + Termin“
(Zuweisung WP/Elektro/Sub, Team, ganztägig Beginn/Ende, Kunde bestätigt →
`POST /gewerk/{id}/team-termin`), (3) derselbe Dialog im Board (Drop auf
„terminiert“), (4) Kalender-Drag (`POST /termin/{id}/kalender-drop`, Datum und
Team). Die Terminübersicht (`POST /projektierung/termine`) ruft (1) auf. Es gibt
**keine** Route zum Bearbeiten oder Löschen eines Termins (der Board-Hinweis
„Montagetermin in der Projektakte löschen“ führt ins Leere). Elektro-Montage-
termine sind vom WP-Montagetermin nicht unterscheidbar (`typ = montage`, nur
`team_id`), `terminstatus_map` nimmt den frühesten Montagetermin.

- [x] **Datenmodell:** `projekt_termine.zweck` (String 10: `wp` | `elektro` |
      `sub` | leer; Migration: Termine mit `typ = montage` erhalten `wp`,
      `elektro` oder `sub` je nachdem, mit welchem Feld des Gewerks
      (`wp_team_id` / `elektro_team_id` / `sub_team_id`) `team_id`
      übereinstimmt, sonst `wp`). Neue Tabelle `termin_besetzung` (`id`,
      `termin_id` Index, `benutzer_id`, `erstellt_am`, `erstellt_von`;
      eindeutig je `termin_id + benutzer_id`). Migration: für jeden
      bestehenden Termin mit `team_id` die Mitglieder aus `team_mitglieder`
      als Besetzung eintragen (nur, wenn noch keine Besetzung existiert).
      `terminstatus_map` wertet nur Montagetermine mit `zweck in ("wp", "")`
      aus (Elektro-/Sub-Termine bestimmen den Terminstatus nicht).
- [x] **Makro `termin_dialog(gewerk, termin=None, …)`** in
      `templates/projektierung/_termin_dialog.html` (CSS `pj-`), verwendet in
      der Akte (Knopf „+ Termin“ je Gewerk und „bearbeiten“ je Termin), im
      Board (Drop auf „terminiert“ und Aktion an der Karte), in der
      Terminübersicht `/projektierung/termine` (nach Gewerk-Wahl) und an den
      Aufgaben mit `aktion_typ = kalender` („Montageteam zuweisen“,
      „Elektro-Montageteam zuweisen“, „HEMS-Inbetriebnahme terminiert“, FP-
      Termin). Felder:
      - **Art** (Pflicht): Montage (WP) · Elektro-Montage · Sub-Einsatz ·
        Feinplanung VOT · Abnahme · Sonstiges (→ `typ`/`zweck`: montage/wp ·
        montage/elektro · sub/sub · feinplanung · abnahme · sonstige). Die
        Art ist vorbelegt (Aufgabe/Drop) und beim Bearbeiten gesperrt.
      - **Team** (Pflicht bei Montage/Elektro-Montage; Sub-Einsatz: Subteam
        **oder** Subunternehmer aus den Stammdaten) bzw. **Person** (Pflicht
        bei Feinplanung VOT und Abnahme; Sonstiges optional) – Liste der
        Benutzer mit Rolle Projektierung/Innendienst/Admin.
      - **Beginn** (Datum, Pflicht) und **Uhrzeit** (optional, 15-Minuten-
        Takt; leer = ganztägig), **Ende** (Datum; leer = bei Montage/Elektro
        Beginn + 4 Arbeitstage, sonst = Beginn).
      - **Besetzung** (nur Montage/Elektro-Montage/Sub-Einsatz mit Team):
        Mehrfachauswahl aller aktiven Montage-Benutzer, vorbelegt mit den
        Mitgliedern des gewählten Teams (Wechsel des Teams belegt neu, solange
        die Besetzung nicht von Hand geändert wurde), Chips mit × zum
        Entfernen; Hinweis „Mannschaft für diesen Einsatz – das Team ist nur
        die Vorlage“.
      - **Kunde bestätigt** (Häkchen), **Notiz**.
      - Bei Montage (WP): Knopf **„Terminvorschläge“** (unten).
      Beim Anlegen und Bearbeiten derselbe Dialog; der Titel lautet
      „Termin anlegen · <Sparte>“ bzw. „Termin bearbeiten · <Datum>“.
- [x] **Routen:** `POST /projektierung/gewerk/{id}/termin` wird die einzige
      Anlege-Route (nimmt alle Dialogfelder: `art`, `team_id`, `sub_id`,
      `person_id`, `beginn`, `uhrzeit`, `ende`, `besetzung` mehrfach,
      `kunde_bestaetigt`, `notiz`; bei Montage/Elektro-Montage setzt sie wie
      `team_termin_zuweisen` das Zuweisungsfeld am Gewerk (`wp_team_id` /
      `elektro_team_id` / `sub_team_id`), erledigt die passende Aufgabe
      „<Team> zuweisen“, berechnet Fälligkeiten nach, sendet Outlook, meldet
      Konflikte als Warnung). `POST /gewerk/{id}/team-termin` bleibt als
      Alias auf dieselbe Funktion (alte Formulare/Tests). Neu:
      `POST /projektierung/termin/{id}/bearbeiten` (gleiche Felder;
      Teamwechsel setzt das Zuweisungsfeld am Gewerk um und protokolliert
      „Montageteam gewechselt: <alt> → <neu>“; Outlook-Ereignis wird
      aktualisiert – vorhandene Funktion `outlook_kalender.event_senden`,
      best effort) und `POST /projektierung/termin/{id}/loeschen` (Pflicht-
      Grund, Verlauf „Termin <Art> <Datum> gelöscht – <Grund>“, Outlook-
      Storno best effort (bestehende Storno-Funktion nutzen, sonst
      `outlook_fehler` setzen), Besetzung mit löschen; war es der
      maßgebliche Montagetermin, wird die Aufgabe „Montageteam zuweisen“
      wieder `offen` und das Gewerk steht im Board unter „unterminiert“).
      Alle drei Routen antworten mit JSON bei Accept application/json
      (`{ok, meldung, konflikte}`), sonst Redirect.
- [x] **Block „Termine“ in der Projektakte** je Gewerk (ersetzt die Zeilen
      „Feinplanung“/„Montage“/„weitere Termine“ in `pj-kv`): Tabelle Art ·
      Datum/Uhrzeit · Team/Person · Besetzung (Namen, gekürzt „A. Müller,
      B. Schmidt +2“) · Kunde (bestätigt ✔ / „✉ Termin an Kunden“ / „✓
      bestätigt“ wie heute) · Outlook (📅✓ / ⚠ erneut senden) · Aktionen
      (bearbeiten, löschen). Der Zählerwechsel-Termin (`zaehlerwechsel_termin`)
      bleibt als eigene Zeile darunter. Terminübersicht `/projektierung/
      termine` und Kalender zeigen Besetzung als Tooltip am Balken.
- [x] **Kalender-Drag** (`termin_verschieben`): bei Teamwechsel per Drag wird
      die Besetzung aus dem neuen Team neu vorbelegt, falls sie der
      Mitgliederliste des alten Teams entsprach; sonst bleibt sie und der
      Verlauf vermerkt „Besetzung beibehalten (von Hand gesetzt)“.
- [x] **Terminvorschläge Stufe 1** (`kern.terminvorschlaege(session, gewerk,
      team_id=None)` → Liste von max. 5 je Team, Route
      `GET /projektierung/gewerk/{id}/terminvorschlaege.json`):
      - Montagedauer: `dauer_tage` des Dialogs, Standard 5 Arbeitstage
        (Parameter `montage_dauer_tage_standard`, Standard 5).
      - Frühester Beginn = max(heute + `vorschlag_vorlauf_wochen` (Parameter,
        Standard 4 = gelbe Vorlaufgrenze), Lieferdatum der letzten
        UGL-Bestellung des Gewerks + 1 Arbeitstag, falls vorhanden); Vorschläge
        beginnen montags [ANNAHME].
      - Je aktivem Montage-Team (`typ = montage`): die ersten freien
        Zeitfenster ohne Überschneidung mit dessen Terminen im Tool
        (`team_konflikte`), Suche bis 26 Wochen voraus.
      - Bewertung: Umweg = Fahrzeit von der Ausführungsadresse des letzten
        Einsatzes des Teams vor dem Fenster und zum ersten Einsatz danach,
        ersatzweise von der Startadresse (Parameter
        `montage_startadresse`, Standard „Arnold-Overbeck-Str. 63-65, 47139
        Duisburg“ [ANNAHME: Firmensitz]); Fahrzeit über die vorhandene
        Routing-Funktion des Lead-Terminassistenten (`routing_anbieter`,
        Caches, Luftlinie als Fallback). Sortierung: Beginn aufsteigend, bei
        gleichem Beginn geringerer Umweg.
      - Darstellung im Dialog: Liste „Mo 09.11.–Fr 13.11. · Montageteam 2 ·
        Umweg 18 min · Begründung“; Klick übernimmt Team, Beginn, Ende und
        belegt die Besetzung vor. Ohne Routing-Anbieter: Umweg „–“, Hinweis
        „Fahrzeiten: kein Routing-Anbieter konfiguriert“. Stufe 2
        (Outlook-Frei/Belegt) ist ein Schalter `vorschlag_outlook` (Standard
        aus), der in diesem Plan nur angelegt, nicht ausgewertet wird.
- [x] **Konflikte:** bei Besetzung wird zusätzlich je Person geprüft, ob sie
      im Zeitraum in einem anderen Termin eingeteilt ist (Warnung „<Name>
      ist am 12.11. bereits bei PR-26…“) – kein Verbot
      (`termin_konflikt_modus` der Projektierung bleibt „warnen“).
- [x] Kontrollwerte: `tests/test_proj_v6_termine.py` – (a) Dialog-Anlage
      Montage ohne Team → 400/Meldung „Montagetermine brauchen ein Team“;
      (b) Anlage mit Team 1 (Mitglieder A, B) → Besetzung {A, B}, `zweck =
      wp`, `wp_team_id` gesetzt, Aufgabe „Montageteam zuweisen“ erledigt;
      (c) Bearbeiten: Besetzung {A, C} → C sieht den Einsatz unter
      `/montage`, B nicht mehr (Phase 137); (d) Löschen des einzigen
      Montagetermins → Terminstatus `unterminiert`, Aufgabe wieder offen,
      Verlauf mit Grund; (e) Elektro-Montagetermin (zweck elektro) am
      20.11. und WP-Montagetermin am 10.11. → Terminstatus nimmt den 10.11.;
      (f) Vorschläge: Team 2 hat Termin 02.–06.11., Vorlauf 4 Wochen ab
      06.10.2026, Dauer 5 AT → erster Vorschlag Mo 09.11.2026, zweiter Mo
      16.11.2026; Team ohne Termine → Mo 09.11.2026 (erster Montag ≥
      03.11.2026).

## Phase 136 – Notizen über alle Phasen, Galerie-Lightbox

- [x] **Vorgangs-Notizen-Chat als einzige Spur:** Das Kommentarfeld der
      Projektakte (Reiter Verlauf, `POST /projektierung/projekt/{id}/
      kommentar`) schreibt in `VorgangsNotiz` des Vorgangs (`herkunft =
      projektierung`, `benutzer_name`), statt in `ProjektVerlauf` mit
      `art = kommentar`; @Erwähnungen (`erwaehnungen_finden`) und die
      Glocke bleiben. `ProjektVerlauf` bleibt für Systemeinträge. Projekte
      ohne Vorgang (`projekt.vorgang_id` leer – Altbestand) behalten den
      bisherigen Weg mit Hinweis „Kein Vorgang – Kommentar nur im
      Projektverlauf“. Migration `migration_v28_notizen`: bestehende
      `ProjektVerlauf`-Einträge mit `art = kommentar` werden in
      `VorgangsNotiz` kopiert (`herkunft = projektierung (migriert)`,
      Zeit/Autor übernommen), das Original bleibt.
- [x] **Anzeige:** Reiter Verlauf der Projektakte zeigt oben den Notizen-
      Chat des Vorgangs (alle Einträge, Chat-Optik aus der Vorgangsakte v14,
      eigene Einträge rechts, Kennzeichen „Projektierung“/„Vertrieb“/
      „Lead“ aus `herkunft`), darunter eingeklappt den Systemverlauf. Die
      Vorgangsakte (Angebotstool) und die Kundenkartei (Lead-Management,
      Block „Notizen“ in voller Breite unter den Blöcken, read + write über
      die bestehende Route der Vorgangsakte `POST /vorgaenge/{id}/notiz`
      [ANNAHME: Routenname prüfen]) zeigen denselben Chat; Lead-Aktivitäten
      bleiben unberührt. Montage-Backend: Phase 137.
- [x] **Eingabefeld:** Textarea 4 Zeilen, wächst mit dem Inhalt (bis 12
      Zeilen), Strg + Enter sendet, Senden per fetch ohne Neuladen
      (Eintrag wird unten angehängt) – in Projektakte, Vorgangsakte und
      Kundenkartei gleich (gemeinsames Makro `notizen_chat` in
      `_komponenten.html`, CSS-Tokens des Design-Systems).
- [x] **Rechte:** Schreiben wie heute in der Vorgangsakte (ID/Admin überall,
      AD bei eigenen Vorgängen) plus Rolle Projektierung/Leadmanagement
      für Vorgänge, auf die sie Zugriff haben; Rolle Montage **nur lesen**
      (Phase 137). Einträge bleiben unveränderlich.
- [x] **Galerie-Lightbox:** Befund – `_galerie.html` hat `pjLightbox`
      (einfacher Dialog ohne Vor/Zurück); Andreas sieht Sofort-Download.
      Ursache prüfen (Seiten, die das Makro `galerie` ohne `galerie_fuss()`
      einbinden; `Content-Disposition: attachment` der Datei-Route
      `/vorgaenge/galerie/datei/{id}` – für Bilder `inline` liefern) und die
      Lightbox ausbauen: Bild groß (max. 95 vh/vw), Pfeile ◀ ▶ und
      Pfeiltasten für alle Bilder des Ordners, Wischen auf dem Handy,
      Kopfzeile „<Ordner> · <n> von <m> · <Datum> · <Bemerkung>“, Knöpfe
      „Herunterladen“ (Link mit `download`-Attribut auf
      `…/datei/{id}?download=1` → Content-Disposition attachment),
      „Schließen“ und Esc; Klick außerhalb schließt. Download nur über den
      Knopf. Gilt für Vorgangsakte, Projektakte, Montage-Backend und
      Erfassungs-Fotoblock (überall dasselbe Makro).
- [x] Kontrollwerte: Kommentar in der Projektakte → `VorgangsNotiz` mit
      `herkunft = projektierung`, kein neuer `ProjektVerlauf` mit `art =
      kommentar`; Migration zweimal gegen die Server-DB-Kopie: zweiter Lauf
      0 Kopien; `GET /vorgaenge/galerie/datei/{id}` für ein JPG antwortet
      `inline`, mit `?download=1` `attachment`; Montage-Login kann die
      Notiz-Route nicht aufrufen (303/403).

## Phase 137 – Montage-Backend `/montage`: Steckbrief, Reihenfolge, Besetzung, Montage starten/beenden

- [x] **Fehlersuche Steckbrief:** Screenshot 06.10. (mobil) zeigt nur
      Hersteller, Leistungsklasse, Innengerät-Variante, Stemmarbeiten.
      `einsatz.html` blendet Felder ohne Wert aus (`{% if w and w.wert %}`),
      `steckbrief_daten` liefert nur gespeicherte `SteckbriefWert`-Zeilen.
      Soll: alle Felder der Sparte in der Reihenfolge von
      `kern.steckbrief_felder(sparte)` (inkl. Auftragsdaten-Felder), leere
      Felder als „–“, derselbe Datenstand wie der Steckbrief der Projektakte
      (`steckbrief_ableiten` wurde ausgeführt, Werte mit `quelle =
      auftragsdaten` inklusive); Raster `pj-steck-raster` mobil einspaltig
      mit Umbruch langer Werte. Ursache in der Gesamtübersicht benennen
      (fehlende Ableitung beim Bestandsimport, Template-Filter, CSS).
- [x] **Neue Reihenfolge der Auftragsseite** (`templates/montage/einsatz.html`):
      1. Kopf: Kunde, Sparte, Termin (Datum/Uhrzeit, Team, Besetzung),
         Adresse mit Karten-Link, Telefon, Ansprechpartner Friondo
         (Projektleiter), Status.
      2. **Steckbrief** vollständig (offen).
      3. **Teams & Termine** (alle Termine des Gewerks mit Art, Team/Person,
         Besetzung, Kunde bestätigt; Sub-Einträge).
      4. **Notizen der Projektierung** (read-only): `projekt.notiz_kopf`
         („Bemerkung für die Technik“) als erste Zeile, darunter die letzten
         fünf Einträge des Vorgangs-Notizen-Chats mit Autor/Datum und
         „alle anzeigen“ (aufklappbar); kein Eingabefeld (Entscheidung
         „Monteur nur lesen“), Hinweistext „Bemerkungen bitte im
         Montagebericht eintragen“.
      5. **Montage starten / Montage beenden** (Status-Block mit Uhrzeit im
         15-Minuten-Takt wie heute): „Montage starten“ in den Phasen
         auftragseingang … montagevorbereitung (Phasenwechsel nach
         `montage` mit Begründung „Montage gestartet (mobil, <Zeit>)“ – im
         Modus warnen ohne Rückfrage, offene Punkte im Verlauf);
         „Montage beenden“ in Phase montage: setzt `montage_fertig_am` und
         wechselt nach `abnahme`; der Kurzbericht wird **optional**
         [ANNAHME: Bemerkungen stehen jetzt im Montagebericht
         `mb_bemerkung`]; Hinweis unter dem Knopf „Wird automatisch beendet,
         sobald das Abnahmeprotokoll unterschrieben ist.“ Nach Abnahme/
         Freigabe nur Statuszeile.
      6. **Formulare** (Montagebericht · Inbetriebnahmeprotokoll ·
         Abnahmeprotokoll, Knöpfe mit ✓ wie heute).
      7. **Restarbeiten** (Liste + Melden wie heute).
      8. **Galerie** ganz unten (Sammelbox wie heute, Lightbox aus Phase 136).
      Der Block „Offene Montage-Aufgaben“ (`Aufgabe.rolle == "montage"`)
      entfällt samt Route `POST /montage/aufgabe/{id}/erledigt` (Route
      bleibt für den Übergang erreichbar, wird aber nicht mehr verlinkt;
      in der Gesamtübersicht vermerken, ob Aufgaben mit `rolle = montage`
      im Blatt existieren – heute keine). „Gerät & Positionen (ohne
      Preise)“ bleibt eingeklappt zwischen Steckbrief und Teams & Termine
      [ANNAHME].
- [x] **Automatisch beenden mit der Abnahme:** `montage_formulare.
      abschliessen` für `formular = abnahme` (Kundenunterschrift ist
      Pflichtfeld `ab_unterschrift_kunde`): ist das Gewerk noch in Phase
      `montage`, werden `montage_fertig_am` gesetzt und
      `phase_wechseln(gewerk, "abnahme", "Abnahmeprotokoll unterschrieben
      (mobil)")` aufgerufen; Verlauf „Montage beendet mit Abnahme“. Ist das
      Gewerk bereits in `abnahme`, nichts weiter.
- [x] **Besetzungs-Sicht:** `_einsatz_erlaubt` erlaubt den Einsatz, wenn der
      Benutzer in `termin_besetzung` steht **oder** (Fallback für Termine
      ohne Besetzung) Mitglied des Termin-Teams ist oder `person_id` ist;
      Admin alles. „Meine Einsätze“ (`GET /montage`): Standardansicht
      **„Meine Einsätze“** = Termine mit eigener Besetzung (plus Fallback),
      chronologisch Heute / Diese Woche / Danach wie heute; der
      Team-Umschalter bleibt für Benutzer mit mehreren Teams und für
      Admin/Projektierung (Ansicht „Team <Name>“ = alle Termine des Teams).
      Wochenkalender zeigt in der Teamansicht je Termin die Besetzung als
      Initialen.
- [x] Kontrollwerte: Monteur C (nicht im Team 1) mit Besetzung am Termin
      → sieht den Einsatz; Monteur B (Team 1, aus der Besetzung entfernt)
      → sieht ihn nicht; Termin ohne Besetzung → Teammitglieder sehen ihn.
      Abnahmeprotokoll abschließen bei Phase montage → Phase abnahme,
      `montage_fertig_am` gesetzt, Verlauf „Montage beendet mit Abnahme“.
      Steckbrief-Seite zeigt für das Demo-Projekt „Demo Montage, Bernd“ alle
      WP-Felder (20 feste + Auftragsdaten-Felder), leere als „–“.

## Phase 138 – Formulare: Blatt „Formulare“, Wiederholfeld, elf Fragen, PDF

Arbeitsanweisung an der Live-Excel (Blatt „Formulare“, Spalten wie bisher
`formular | seite | feld_key | bezeichnung | typ | pflicht | optionen`;
Sicherung aus Phase 133 reicht). Bestehende Einträge in `montage_formulare`
(Entwürfe) behalten alte Schlüssel im JSON – sie werden ignoriert;
abgeschlossene PDFs bleiben unverändert.

- [x] **Montagebericht:** Zeilen `mb_beginn`, `mb_ende`, `mb_nachbestellung`,
      `mb_regie` **löschen**. Seite „Abweichungen & Material“ heißt
      „Abweichungen & Bemerkungen“ [ANNAHME]. Neue Zeilen (in dieser
      Reihenfolge nach `mb_abweichung_foto`):
      `montagebericht | Abweichungen & Bemerkungen | mb_bemerkung | Bemerkungen des Monteurs | text | N | gross`
      (Option `gross` = Textarea 6 Zeilen),
      `montagebericht | Fotos | mb_foto_zaehlerschrank | Foto Zählerschrank | foto | N | Elektro`,
      `montagebericht | Fotos | mb_foto_aussengeraet | Foto Außengerät | foto | N | Außengerät`,
      `montagebericht | Fotos | mb_foto_innengeraet | Foto Innengerät / Heizungsraum | foto | N | Neue Anlage`,
      `mb_foto_anlage` („Foto Neue Anlage“, Ordner Neue Anlage) wandert auf
      die Seite „Fotos“ ans Ende. [ANNAHME: Ordnernamen = bestehende
      WP-Galerie-Ordner Elektro · Außengerät · Neue Anlage; es gibt keinen
      Ordner „Zählerschrank“/„Innengerät“ in der WP-Galerie.]
      `mb_mitarbeiter` („Mitarbeiter (Team)“) wird mit der Besetzung des
      Termins vorbelegt (Namen, kommagetrennt), bleibt editierbar.
- [x] **Foto-Felder mehrfach:** `typ = foto` nimmt mehrere Dateien an
      (`multiple`, Sammelbox-Verhalten wie die Galerie: aufnehmen oder
      auswählen, Vorschau, ein Upload beim Seiten-Speichern); gespeichert als
      `galerie:<id>:<name>|galerie:<id>:<name>`; `_wert_anzeige` und das PDF
      listen „Fotos in Galerie: a.jpg, b.jpg“; Bestandswerte mit einem Foto
      bleiben lesbar. `ab_maengel_foto` (Restarbeiten-Foto) hängt wie bisher
      das erste Foto an den ersten Restarbeiten-Eintrag.
- [x] **Inbetriebnahmeprotokoll – Blatt komplett ersetzen** durch folgende
      Zeilen (Wortlaut der Fragen verbindlich, Andreas 06.10.2026):

      Seite „Gerät“:
      `inbetriebnahme | Gerät | ib_sn_aussen | Seriennummer Außengerät | text | J |`
      `inbetriebnahme | Gerät | ib_sn_innen | Seriennummer Innengerät | text | J |`
      `inbetriebnahme | Gerät | ib_sn_puffer | Seriennummer Puffer/Speicher | text | N |`
      `inbetriebnahme | Gerät | ib_sn_komponenten | Systemkomponenten – weitere Seriennummern | wiederhol | N | Seriennummer`
      `inbetriebnahme | Gerät | ib_kaeltemittel | Kältemittel / Füllmenge | text | N |` [ANNAHME: bleibt als freiwillige Angabe für den F-Gase-Nachweis]

      Seite „Prüfungen“ (Fragen 1–6, 8, 9 Pflicht):
      `inbetriebnahme | Prüfungen | ib_f01 | 1. Entsprechen Aufstellung und Montage den Herstellervorgaben, einschließlich Abständen, Schutzbereichen und gegebenenfalls Kondensatablauf? | ja_nein | J |`
      `inbetriebnahme | Prüfungen | ib_f02 | 2. Ist die Heizungsanlage gespült, befüllt, entlüftet und auf Dichtheit geprüft? | ja_nein | J |`
      `inbetriebnahme | Prüfungen | ib_f03 | 3. Ist die Anlage mit Heizwasserqualität nach VDI2035 befüllt worden? | ja_nein | J |`
      `inbetriebnahme | Prüfungen | ib_f04 | 4. Ist der hydraulische Abgleich durchgeführt? | ja_nein | J |`
      `inbetriebnahme | Prüfungen | ib_f05 | 5. Sind die herstellerseitig vorgesehenen Prüfungen an Sicherheitseinrichtungen, Frostschutz, Wärmequelle und Kältemittelkreis abgeschlossen? | ja_nein | J |`
      `inbetriebnahme | Prüfungen | ib_f06 | 6. Sind Mindestvolumenstrom und erforderliches Anlagenwasservolumen sichergestellt? | ja_nein | J |`
      `inbetriebnahme | Prüfungen | ib_f07_heizen | 7. Wurden die vorgesehenen Betriebsarten erfolgreich getestet? – Heizen | auswahl | J | OK|nicht OK|nicht vorhanden`
      `inbetriebnahme | Prüfungen | ib_f07_warmwasser | 7. Betriebsart Warmwasser | auswahl | J | OK|nicht OK|nicht vorhanden`
      `inbetriebnahme | Prüfungen | ib_f07_kuehlen | 7. Betriebsart Kühlen | auswahl | J | OK|nicht OK|nicht vorhanden`
      `inbetriebnahme | Prüfungen | ib_f07_zusatzheizung | 7. Betriebsart Zusatzheizung | auswahl | J | OK|nicht OK|nicht vorhanden`
      `inbetriebnahme | Prüfungen | ib_f08 | 8. Sind die vereinbarten Steuerungs- und Kommunikationsschnittstellen eingerichtet und geprüft? | ja_nein | J |`
      `inbetriebnahme | Prüfungen | ib_f09 | 9. Wurde der Betreiber in Bedienung, Störungsverhalten und Wartung eingewiesen und wurden die Unterlagen übergeben? | ja_nein | J |`
      `inbetriebnahme | Prüfungen | ib_f10 | 10. Welche Mängel oder Restarbeiten bestehen, wer erledigt sie und bis wann? (eine je Zeile, „keine“ erlaubt – wird als Restarbeiten-Liste übernommen) | text | J | gross`
      `inbetriebnahme | Prüfungen | ib_f11 | 11. Wird die Anlage durch den Techniker zum Betrieb freigegeben? | auswahl | J | Ja|Mit dokumentierten Einschränkungen|Nein`
      `inbetriebnahme | Prüfungen | ib_f11_text | Einschränkungen / Begründung | text | N | pflicht_wenn:ib_f11≠Ja`

      Seite „Betriebswerte im stabilen Betrieb“:
      `inbetriebnahme | Betriebswerte im stabilen Betrieb | ib_bw_betriebsart | Betriebsart | auswahl | N | Heizen|Warmwasser|Kühlen`
      `inbetriebnahme | Betriebswerte im stabilen Betrieb | ib_bw_aussen | Außen-/Quellentemperatur (°C) | zahl | N |`
      `inbetriebnahme | Betriebswerte im stabilen Betrieb | ib_bw_druck | Anlagendruck (bar) | zahl | N |`
      `inbetriebnahme | Betriebswerte im stabilen Betrieb | ib_bw_vorlauf | Vorlauf (°C) | zahl | N |`
      `inbetriebnahme | Betriebswerte im stabilen Betrieb | ib_bw_ruecklauf | Rücklauf (°C) | zahl | N |`
      `inbetriebnahme | Betriebswerte im stabilen Betrieb | ib_bw_volumenstrom | Volumenstrom (l/min) | zahl | N |`

      Seite „Einstellungen“:
      `inbetriebnahme | Einstellungen | ib_e_heizkurve | Heizkurve / Niveau | text | N |`
      `inbetriebnahme | Einstellungen | ib_e_raumsoll | Raum-Solltemperatur (°C) | zahl | N |`
      `inbetriebnahme | Einstellungen | ib_e_wwsoll | Warmwasser-Solltemperatur (°C) | zahl | N |`

      Seite „Unterschriften“:
      `inbetriebnahme | Unterschriften | ib_unterschrift_techniker | Unterschrift Techniker | unterschrift | J |`
      `inbetriebnahme | Unterschriften | ib_unterschrift_betreiber | Betreiber – Einweisung und Unterlagenerhalt bestätigt | unterschrift | J |`

      Entfallen damit: `ib_dichtheit`, `ib_spuelung`, `ib_druck`, `ib_vorlauf`,
      `ib_heizkurve`, `ib_abgleich`, `ib_frostschutz`, `ib_rcd`, `ib_iso`,
      `ib_schleife`, `ib_zaehlernummer`, `ib_hems`, `ib_probelauf`,
      `ib_einweisung`, `ib_einweisung_dauer`, `ib_bemerkung`,
      `ib_unterschrift_monteur`. Abnahmeprotokoll unverändert.
- [x] **Lader/Renderer:** neuer Feldtyp `wiederhol` (Spalte `optionen` =
      Bezeichnung des Einzelfelds, z. B. „Seriennummer“): Oberfläche zeigt
      die vorhandenen Werte als Zeilen mit × und einen Knopf „+ weitere
      Seriennummer“ (JS, ohne Neuladen); Speicherung als JSON-Liste im
      `antworten_json` (Formularfelder `ib_sn_komponenten[]`); PDF: eine
      Zeile je Wert („Systemkomponente 1: …“). Option `gross` bei `text` =
      Textarea 6 Zeilen. Neue Optionsform `pflicht_wenn:<feld>≠<wert>` (und
      `=`) für `text`/`zahl`/`auswahl`: `offene_pflicht` prüft sie zusätzlich
      zur Spalte `pflicht` (Meldung mit der Bezeichnung des Feldes). `ja_nein`
      bleibt Radio Ja/Nein; `auswahl` Radio-Liste wie heute. „Logik prüfen“
      meldet unbekannte Typen/Optionsformen als Fehler; `wiederhol`, `gross`,
      `pflicht_wenn:` sind bekannt.
- [x] **Restarbeiten aus Frage 10:** `abschliessen` für `inbetriebnahme`
      übernimmt die Zeilen von `ib_f10` wie `ab_maengel` als `Restarbeit`
      (ohne Frist/Foto); die Zeile „keine“ (auch „Keine“, „-“, „–“) erzeugt
      nichts. Doppelte Übernahme vermeiden: Zeilen, die bereits wörtlich als
      offene Restarbeit des Gewerks existieren, werden übersprungen.
      Verlauf „… abgeschlossen (PDF in Galerie Inbetrieb-/Abnahme) – n
      Restarbeiten übernommen“.
- [x] **PDF (`_FormularPdf`):** Fragen in voller Länge mit Umbruch
      (`multi_cell` für Bezeichnungen > 52 Zeichen statt Abschneiden),
      Antwort in der Folgezeile; Frage 7 als vier Zeilen Heizen/Warmwasser/
      Kühlen/Zusatzheizung; Betriebswerte und Einstellungen als Tabelle
      zweispaltig; zwei Unterschriften nebeneinander mit Beschriftung
      „Techniker“ und „Betreiber – Einweisung und Unterlagenerhalt bestätigt“,
      Datum/Uhrzeit des Abschlusses, Kundenname und Projektnummer im Kopf wie
      heute. Dateiname bleibt `Inbetriebnahmeprotokoll_<PR>.pdf`.
- [x] **Blatt „Lesehilfe“ / Doku:** Absatz „Formulare (v28)“ mit den Typen
      datum · text (Option gross) · ja_nein · auswahl · zahl · foto (Ordner,
      mehrere Dateien) · unterschrift · wiederhol und der Optionsform
      `pflicht_wenn:`; Abschnitt in docs/projektierung-entscheidungen.md.
- [x] Kontrollwerte (`tests/test_proj_v6_formulare.py`): Blatt lädt ohne
      Fehler, Inbetriebnahme hat 5 Seiten und 31 Felder; `ib_f10 = "keine"`
      → 0 Restarbeiten; `ib_f10 = "Dämmung Rohr Keller – Müller – 20.11.\n
      Kondensatablauf prüfen"` → 2 Restarbeiten; `ib_f11 = Nein` ohne
      `ib_f11_text` → `offene_pflicht` enthält „Einschränkungen / Begründung“;
      `ib_sn_komponenten = ["A1", "B2"]` → PDF enthält beide; Montagebericht
      hat keine Felder `mb_beginn`/`mb_regie` mehr und `mb_bemerkung`
      vorhanden; Foto-Feld mit zwei Dateien → zwei Galerie-Dateien im Ordner
      Elektro, Wert mit `|`.

## Phase 139 – Stücklisten-Nachträge, Tests, Doku, CLAUDE.md v28

Die Stücklisten-Punkte sind klein und können als Nachtrag zu V5 vorgezogen
werden; sind sie dort bereits umgesetzt, die Checkboxen hier als erledigt
abhaken und nur gegenprüfen.

- [x] **Blatt „Stücklisten“ aus `docs/stuecklisten_v26.csv` übernehmen**
      (Import über die Parametrierung oder `stuecklisten.csv_import` im
      Skript; Logik-Validierung grün; 121 Zeilen, 80 Positionen); Datei
      danach in `docs/stuecklisten_v26.csv` belassen und in
      docs/projektierung-entscheidungen.md als „eingespielt am <Datum>“
      vermerken.
- [x] **Konvention Lieferant** (Parameter `stueckliste_standard_lieferant`,
      Standard „Collin“): `Collin` = bestellen · `Lager`/`LAGER` = Lagerware ·
      `–`/`KEIN-MATERIAL` = Leistung ohne Material · anderer Name =
      Fremdlieferant. `ugl.material_fuer_gewerk` nimmt nur Zeilen des
      Standard-Lieferanten in die UGL; die Bestell-Vorschau zeigt die
      übrigen Zeilen im Block „nicht bestellt (Lager / Leistung /
      Fremdlieferant)“. `stuecklisten.fortschritt` zählt eine Position als
      zugeordnet, wenn sie mindestens eine Zeile hat (auch Lager/–); die
      Go-live-Quote rechnet nur über Positionen der Sparte WP und
      spartenübergreifende Positionen (PV-/KL-Positionen `PV…`/`KL…`
      ausgenommen, solange sie keinen Lieferanten haben) [ANNAHME].
      Stücklisten-Seite: Spalte „Art“ (bestellen / Lager / Leistung / Fremd)
      aus dem Lieferanten abgeleitet, Filter „nur ohne Zuordnung“ berück-
      sichtigt die Konvention. Konvention in docs/projektierung-entscheidungen.md
      und in der Anleitung des Stücklisten-Entwurfs (`docs/Stuecklisten-
      Entwurf.xlsx`, Blatt Anleitung – nur Text) dokumentieren.
- [x] **Tests:** `tests/test_proj_v6_waechter.py`, `_board.py` (Routen/JSON),
      `_termine.py`, `_notizen.py`, `_montage.py`, `_formulare.py`,
      `_stuecklisten.py`; Alt-Tests, die den Wächter als sperrend voraus-
      setzen, auf `waechter_modus = sperren` umstellen (Begründung in der
      Gesamtübersicht je Test). Gesamtlauf `pytest tests -q` grün, Anzahl
      in CLAUDE.md eintragen.
- [x] **Abnahme nach Grundregel:** Server-DB-Kopie nach `diagnose\`,
      `migrate.py` zweimal (zweiter Lauf ohne Änderungen; Migrationen
      `aufgaben.entfaellt_grund`, `projekt_termine.zweck`, `termin_besetzung`,
      Notizen-Kopie), `scripts/voll_crawl.py` für admin/innendienst/
      aussendienst/montage ohne Absturz, `tests/abnahme.py`; Screenshots
      vorher/nachher (Board 1920 px, Projektakte Block Termine, Montage-
      Auftragsseite mobil 390 px, Inbetriebnahmeprotokoll Seite Prüfungen,
      Lightbox) nach `docs/design-v28/` – nur Demo-Daten im Bild.
- [x] **Doku:** docs/projektierung-entscheidungen.md Abschnitt „V6 (v28)“
      mit allen [ANNAHME]-Auflösungen; docs/nach-dem-update-v28.md
      (Team-Hinweise: Wächter warnen, Besetzung je Termin, Termin-Dialog,
      Notizen-Chat, Montage-Reihenfolge, neue Formulare, Lightbox,
      Stücklisten-Konvention; Server-To-dos: Parameter prüfen, Blatt
      Formulare/Aufgabenpakete sind im Git-Pull enthalten);
      `docs/projektierung-prototyp.html` um Block „Termine“ und den
      Phase-ändern-Dialog ergänzen (Regel: Layout erst im Prototyp).
- [x] **CLAUDE.md:** Abschnitt „Neu in v28 – Projektierung V6 Pilot-Feedback 1
      (abgestimmt 06.10.2026)“ mit Plan-Verweis und Phasen 133–139 (Nummern
      laut Vorspann prüfen); Zuordnungstabelle um die Zeile `v28 |
      PLAN_PROJ_V6.md | 133–139` ergänzen; in v11/v15/v17-Abschnitten die
      Sätze zu Wächter („Override mit Begründung“), Montage-Backend-
      Reihenfolge, Teams („Monteur fest im Team“) und Formularen als
      *überholt – siehe v28* markieren. Gesamtübersicht mit Testergebnissen,
      offenen Punkten und gebündelten Rückfragen; **kein git push vor
      Freigabe**.

## Zulieferungen / offen

- Rollen-Liste für „Person“ im Termin-Dialog (Feinplanung VOT/Abnahme):
  Projektierung + Innendienst + Admin [ANNAHME]; falls Außendienst
  Feinplanungstermine wahrnimmt, Liste erweitern.
- Startadresse für Fahrzeiten (`montage_startadresse`): Firmensitz
  Arnold-Overbeck-Str. 63-65, 47139 Duisburg [ANNAHME] – ggf. je Team eine
  eigene Startadresse (Feld am Team) nachziehen.
- Terminvorschläge Stufe 2 (Outlook-Frei/Belegt) erst nach Einrichtung des
  Kalender-Syncs (Go-live-Checkliste Punkt 2); Schalter wird angelegt.
- Stücklisten-Rückfragen aus dem Protokoll 06.10. (AWE-Pakete 050–054,
  Pos. 064, Lieferant Warmwasserspeicher 004/065, Meterpositionen) und die 83
  Positionen ohne Collin-Nummer – unabhängig von diesem Plan, Pflege über
  die Stücklisten-Seite.
- Formular-Wortlaute sind verbindlich (Andreas 06.10.2026); offen bleibt nur,
  ob `ib_kaeltemittel` bleibt (ANNAHME oben) – in der Gesamtübersicht
  nachfragen.
- Lead-Kundenkartei: der Block „Notizen“ ist reine Anzeige + bestehende
  Schreibroute; weitergehende Verzahnung mit Lead-Aktivitäten ist Sache des
  Lead-Strangs.
