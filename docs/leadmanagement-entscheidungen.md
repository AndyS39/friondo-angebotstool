# Lead-Management V1 – Entscheidungen während der Umsetzung (Claude Code)

Stellen, an denen PLAN_LEAD_V1/LEADMANAGEMENT-KONZEPT Spielraum ließen und
Claude Code im Sinne des Konzepts entschieden hat. Andreas geht die Liste
nach V1 durch.

## Phase 73 – Datenmodell, Demo-Schalter, Lead-Phase

- **Modul-Präfix `/lead-management` statt `/leads`**: Der Plan nennt `/leads`,
  dort liegt aber die bestehende Leads-VOT-Liste (GET /leads), die laut
  Leitplanke 2/3 unverändert bleiben muss – ein 404-Demo-Gate auf `/leads`
  hätte sie für alle Rollen zerstört. Das Modul übernimmt stattdessen das Ziel
  der bestehenden Startportal-Karte `/lead-management` (Anrufliste, Board,
  Kalender, Karte …); `/api/leads` bleibt wie geplant. Nicht-Sichtbare sehen
  auf `/lead-management` weiterhin die alte Platzhalterseite (Verhalten exakt
  wie bisher), alle anderen Modulrouten liefern 404.
- **`kosten_je_lead` und `budget` als Cent-Integer** (`kosten_je_lead_cent`,
  `budget_cent`) statt Decimal – durchgängiges Muster des Tools.
- **monday-Quelle ohne Kanal**: Der Plan nennt „Kanal aus dem bestehenden
  Board-Mapping“, ein Board-Kanal existiert im Tool aber nicht (der
  Vertriebskanal lebt je Lead/Kunde). Die automatischen `monday_<board>`-
  Quellen bleiben daher ohne Kanalwert; der Kanal wird wie bisher am Kunden
  geführt.
- **`ohne_demo` nur dort, wo Demo-Daten real auftauchen könnten**: Vorgangs-
  liste, Kundenliste (Kunden, die NUR an Demo-Vorgängen hängen), Portal-Kachel
  „Fällige Wiedervorlagen“ und die monday-Wert-Rückspielung (Guard auf
  `vorgang.demo`). Leads VOT, Angebotsliste und Statistik speisen sich aus
  Lead-/Angebots-/Erfassungs-Tabellen, in die Demo-Leads in V1 nie gelangen
  (Demo-Leads haben keine Erfassung/kein Angebot; der Erfassungs-Button ist in
  der Demo-Akte ausgeblendet) – dort ist kein Filter nötig.
- **Lead-Phase-Hooks**: Neben dem Sync-Lauf wird `lead_phase_berechnen` an den
  vorhandenen Statuswechsel-Stellen aufgerufen (Angebots-Status-Route,
  Signatur 2×, Erfassung absenden) – dieselben Orte, an denen bereits der
  Projektierungs-Hook `version_nachziehen` hängt; keine Logikänderung.
- **`benutzer.lm_arbeitszeit`** als String „HH:MM-HH:MM“ (wie der Parameter
  `arbeitszeit_lm`); leer = Modul-Standard.
- **Glocken-Ereignisse des Moduls** laufen als art=`lead` über die bestehende
  Benachrichtigungs-Strecke (Phase 69) und werden für Benutzer ohne
  Modul-Sichtbarkeit gefiltert – Glocke UND Mail (gleiches Muster wie der
  Projektierungs-Demo-Filter).

## Phase 74 – Steuerdatei

- **erfassungs_frage-Mapping** nur bei inhaltlich identischen Fragen gesetzt:
  WP: Q-W02→O01, Q-W03→O02, Q-W04→O05, Q-W05→A01, Q-W06→A02, Q-W07→A03,
  Q-W09→H02; PV: Q-P02→PO01, Q-P03→PD01, Q-P07→PO04; KL: Q-K01→KO03,
  Q-K02→KO05. Q-W08 (Warmwasser über die Heizung, IST-Zustand) wurde bewusst
  NICHT auf N02 (Warmwasser über die Wärmepumpe, SOLL) gemappt; die
  Eigentümer-Fragen der Sparten WP/PV haben keinen identischen Bogen-Key.
- **Zusatz-Spalte `unqualifiziert_bei`** liegt als 9. Spalte im Blatt
  Qualifizierung (Plan nennt sie im Blattaufbau, Startinhalt setzt sie bei
  den Eigentümer-Fragen auf „nein“).
- **hole_logik ohne Session**: Anders als die Projektierung braucht die
  Lead-Steuerdatei keine Parameter-Übernahme in die Datenbank – der Cache
  hängt nur an der Datei (mtime).

## Phase 75 – Lead-Eingang

- **Tabelle `lead_posteingang`** (nicht in der Plan-Tabellenliste): „Posteingang
  unklar“ braucht eine Ablage für nicht erkannte Mails inkl. graph_id-Dedup;
  eine eigene kleine Tabelle ist sauberer als ein Missbrauch des
  kommunikation_log.
- **API-Key als Spalte `lead_quellen.api_key`** (Erzeugen-Häkchen in der
  Quellen-Pflege, Anzeige gekürzt mit Tooltip) statt einer eigenen
  Schlüssel-Tabelle – ein Schlüssel je Quelle, wie der Plan ihn beschreibt.
- **Import zweistufig mit Datei-Token** unter `data/lead_import_tmp/`
  (Vorschau → Ausführen); die Spaltenzuordnung je Quelle liegt als
  `import_mapping_<key>` in lead_parameter.
- **Duplikat „Name+PLZ“** vergleicht den Kunden-Nachnamen als Teil des
  eingegebenen Namens (Vorname+Nachname), Telefon nach E.164-Normalisierung;
  Startquellen-Kanäle: Enni, SWD, Sparkasse (Teilstrings der bestehenden
  v9-Profil-Automatik).
- **Parser**: Der Formular-Standard zieht Quelle/Kampagne aus dem Betreff
  `[LEAD] <quelle> <kampagne>`; Sparten-Aliase (Wärmepumpe→WP, Wallbox→WB …)
  werden normalisiert. Der Posteingangs-Abruf markiert verarbeitete Mails als
  gelesen und prüft den Schalter parser_modus bei jedem Lauf.
- **Demo-Generator-Nachnamen** sind erkennbar fiktiv (Demolead, Testinger,
  Musterfrau …) – bewusst kein realistisch klingender Namenspool, damit
  Demo-Daten nie mit echten Kunden verwechselt werden.

## Phase 76 – Anrufliste, Kaskade, Qualifizierung, Score

- **Seitenpanel** der Anrufliste lädt die bestehende Vorgangsakte in einem
  eingebetteten Rahmen (rechts, ohne Seitenwechsel) – ab Phase 79 zeigt
  dieselbe Akte den Lead-Kopfblock. Tastaturkürzel 1–7 wirken auf die im
  Panel geöffnete Zeile.
- **Score über mehrere Sparten**: Gemeinsame Fragen (gleicher Fragetext, z. B.
  Zeitrahmen), die per Übernahme in mehreren Sparten stehen, zählen nur
  EINMAL – sonst würde ein WP+PV-Lead den Zeitrahmen doppelt bepunktet.
- **„=Wert“-Bedingungen**: Excel speichert Zellen mit führendem „=“ als
  Formel. Der Import liest deshalb mit data_only=False (liefert den rohen
  Text), der Erzeuger erzwingt Text-Zellen – Andreas kann in Excel gefahrlos
  `'=Öl` (mit Apostroph) oder direkt Text eingeben.
- **„Falsche Nummer“** wird nicht als eigenes Vorgangsfeld gespeichert –
  die Anrufliste zeigt das Kennzeichen „Nummer prüfen“, solange der letzte
  Anruf dieses Ergebnis trägt.
- **Reaktivieren aus „Nicht erreicht“** geht auf „In Kontaktierung“ (die
  Versuche bleiben gezählt), aus Zurückgestellt/Unqualifiziert auf „Neu“.
- **Vorbelegungs-Kennzeichen**: neue nullable Spalte `erfassungen.
  vorbelegt_json` + Badge „aus Qualifizierung“ mit Tooltip im Erfassungsbogen;
  der Hook in sparten-start greift NUR bei lead_freigabe_modus = alle.

## Phase 77 – Geocoding, Routing, Terminassistent, Kalender

- **AD-Kandidaten ohne Kanal-Regel**: Der Plan nennt „Kanal-Regel aus der
  Quelle → Gebiets-PLZ → alle mit aktiv_terminierung“ – ein Feld „fester AD
  je Quelle/Kanal“ existiert im Datenmodell (Phase 73) aber nicht. V1 nutzt
  Gebiets-PLZ → aktiv_terminierung (manuell einschränkbar); die Kanal-festen
  AD kommen mit den Zuweisungsregeln in V2.
- **„AD am Vorgang“**: Der Vorgang trägt kein eigenes AD-Feld – der
  Außendienstler lebt am aktiven VOT-Termin (`vot_termine.ad_id`), bei
  monday-Leads zusätzlich wie bisher am Lead. Kein neues Feld nötig.
- **Fahrzeit-Fallback je Paar**: `fahrzeit()` liefert IMMER einen Wert –
  fehlt der Matrix-Cache, wird Luftlinie × 1,3 bei 45 km/h gecacht und als
  „geschätzt“ markiert; ein späterer Matrix-Lauf überschreibt den Eintrag.
- **Vielfalt der Top 5**: höchstens zwei Slots je AD und Tag, damit die
  Vorschläge nicht alle auf demselben Tour-Tag liegen.
- **Slots frühestens +2 Stunden** ab jetzt (kein Vorschlag „in 30 Minuten“).
- **Outlook-Ereignis-ID** wird als `postfach|id` gespeichert, damit
  Ändern/Löschen im Demo-Modus (Testpostfach) und später im echten
  AD-Postfach dasselbe Feld nutzen.
- **„Adresse prüfen“** setzt Koordinaten in V1 über zwei Eingabefelder
  (Google-Maps-Rechtsklick); die Karten-Pin-Setzung kommt mit der
  Leaflet-Karte in Phase 79.
- **Samstag** zählt zu den Vorschlags-Tagen (Wunschzeit „samstag“), sofern
  das AD-Profil dort Arbeitszeiten hat.
