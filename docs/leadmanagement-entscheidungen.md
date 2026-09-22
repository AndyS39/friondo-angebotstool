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

## Phase 78 – Kundenkommunikation mit Sendesperre

- **Vorlagen-Gruppe als eigene Unterseite** (/parametrierung/lead-vorlagen,
  vom Vorlagen-Editor verlinkt): Der bestehende Editor ist fest auf
  Angebots-Vorlagen (Standard + je AD) zugeschnitten; die sechs
  Lead-Schlüssel mit optionaler Sparten-Variante brauchen eine eigene Maske.
  Ablage in den bestehenden Einstellungen (lead_vorlage_<key>[_<Sparte>]_*).
- **mail_modus wird beim Versand ausgewertet** (nicht beim Einreihen):
  Umstellen des Schalters wirkt sofort auf alles, was noch in der
  Warteschlange liegt; der ausgeführte Modus wird am Eintrag gespeichert.
  live wird im Demo-Modus server-seitig zu protokoll herabgestuft
  (zusätzlich weist die Einstellungen-Seite in Phase 81 den Wert ab).
- **Nurture ohne Einwilligung** → Status fehler mit klarem Text (sichtbar
  in der Akte) statt stillem Verwerfen.
- **Rückruf-Betreff** „Rückruf V<Vorgangs-Nr>“ ({link_rueckruf} als
  mailto-Link) – die Antwort-Zuordnung erkennt dieses Muster und AN-C-Nummern.

## Phase 79 – Board, Lead-Akte, Karte, Portal, Cockpit

- **Portal-Karte ohne eingebettete Shortcuts**: Die v9-Portal-Regel (jede
  Karte ist EIN Klickziel) gilt weiter – die Shortcuts Anrufliste/Pipeline/
  Kalender/Karte liegen im Kopf jeder Modul-Seite, die Karte führt auf den
  Modul-Einstieg (Anrufliste).
- **Lead-Akte als Kopfblock + aufklappbare Reiter** direkt in der bestehenden
  Vorgangsakte (vor Erfassungen/Angeboten), eingebunden über ein Include –
  kein Umbau der bestehenden Akte-Blöcke. Der Kanban aus PLAN_PROJ Phase 68
  wird als CSS/Muster wiederverwendet (kanban/kanban-spalte/kanban-karte).
- **„AD änderbar“ im Kopfblock**: Der AD lebt am aktiven Termin – Wechsel
  läuft über Umbuchen im Assistenten; der Kopf zeigt ihn read-only.
- **Board-DnD**: nur → Zurückgestellt/→ Unqualifiziert (Dialog) und
  Seitenzustand → Neu (Reaktivieren); alle anderen Ziele zeigen den Hinweis
  „über Anrufliste/Assistent“ (Terminieren nur über den Assistenten).
- **Leaflet 1.9.4 lokal** unter static/leaflet/ eingecheckt (keine
  CDN-Abhängigkeit); Kacheln von tile.openstreetmap.org mit Attribution –
  ohne Internet erscheinen weiterhin die Pins auf grauem Grund.
- **Gewonnen/Verloren im Board** zeigen die Endzustände (Verloren
  eingeklappt); die 30-Tage-Grenze betrifft die eingeklappte Anzeige.

## Phase 80 – Kennzahlen

- **Reiter „Leads“ als eigene Seite** unter /lead-management/statistik,
  von der bestehenden Statistik-Seite verlinkt (Reiter-Knopf, nur bei
  Modul-Sichtbarkeit) – die Angebots-Statistik selbst bleibt unangetastet;
  Zeitraumwahl und Balken-Technik (ae-balken) werden wiederverwendet.
- **Trichter-Zählweise**: je Stufe zählt der ZEITPUNKT des Ereignisses im
  Zeitraum (eingang_am, erreicht_am, erste Qualifizierung, terminiert_am,
  erfolgter Termin, Erfassung abgesendet, Angebot versendet, angenommen) –
  die Quote bezieht sich auf die Vorstufe desselben Zeitraums.
- **Speed-to-Lead in Arbeitsminuten** (Mo–Fr, arbeitszeit_lm) – konsistent
  mit der SLA-Ampel.
- **Kanal-Report immer letzte 12 Monate** (unabhängig von der
  Zeitraumwahl des Reiters); Kosten = kosten_je_lead × Leads des Monats,
  der Kosten-Monatsimport folgt in V2 wie geplant.

## Phase 81 – Rollen, Sichten, Parametrierung, Löschlauf

- **AD-Zugriff auf die Lead-Akte** läuft über die bestehenden
  Vorgangs-Zugriffsregeln (v10: eigene Vorgänge über Erfassung/Lead) – die
  AD-Aktionen (No-Show, Verschieben) prüfen zusätzlich hart auf den eigenen
  Termin und Freigabe „alle“; „Meine Termine“ zeigt alle eigenen
  VOT-Termine unabhängig vom Vorgangs-Bezug.
- **„Verschieben nur in die eigene Woche“** = dieselbe ISO-Kalenderwoche wie
  der bestehende Termin; alles andere läuft über das Leadmanagement.
- **mail_modus=live wird beim Speichern abgewiesen**, solange der Demo-Modus
  aktiv ist (zusätzlich zur Laufzeit-Sperre im Versand-Job).
- **Demo-Umstellung** auf „alle“ erzwingt bei vorhandenen Demo-Leads die
  Entscheidung löschen/behalten direkt im Freigabe-Block der
  Einstellungen-Seite (kein separates Dialogfenster); beides wird
  protokolliert (einstellungs_protokoll, letzte 30 Zeilen).
- **Löschlauf** hängt am Lead-Scheduler (5-Minuten-Schleife, ab 03:00 mit
  Datums-Schalter); die Vorschau nutzt denselben Kandidaten-Filter im
  Trockenmodus. Im Demo-Modus werden ausschließlich Demo-Leads angefasst.

## Phase 82 – Qualität, Docs, Rollout

- **Assistent bei Geocode-Fehler**: nach einem gescheiterten Geokodier-
  Versuch ruft der Assistent NICHT erneut synchron nach außen (nie
  blockieren) – der 5-Minuten-Hintergrund-Job und „Adresse prüfen“
  übernehmen; der Assistent bewertet dann ohne Fahrzeiten mit Hinweis.
- **Sicherheitstest automatisiert**: der Phase-82-Test läuft über ALLE
  registrierten GET-Routen unter /lead-management und erwartet für den
  Innendienst im Demo-Modus 404 (Einstiegsseite = alte Platzhalterseite).
- **git push offen gelassen** (Anweisung Andreas „Noch nicht pushen“ aus dem
  v11-Auftrag gilt weiter): v11 (Projektierung) und v12 (Lead-Management)
  liegen ungepusht auf demselben Branch – ein Push würde beide Module
  gleichzeitig ausrollen; der Plan verlangt Rollouts nacheinander.
