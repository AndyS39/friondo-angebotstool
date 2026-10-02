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

## Review 27.09.2026 – Prozess- und Design-Durchgang (gesamtes Tool)

Vollständiger Rundgang durch alle Module mit Fokus Lead-Management.
Umgesetzt (Commits d797ad4, 5f5c17a, 3eb856e, 3737053):

**Übergabe Lead → Außendienst** (war der größte Bruch): Lead-Akte gehört
jetzt auch dem AD des VOT-Termins; „Meine Termine" hat „Erfassung starten";
der AD bekommt die Glocke „Neuer VOT-Termin"; der monday-Sync legt den
Vorgang sofort an; ein gemeldeter No-Show wird nicht mehr vom Sync auf
„terminiert" zurückgedreht.

**Mail-Sicherheit vor mail_modus=live**: Umbuchen/No-Show/Absage stornieren
geplante Termin-Mails; der Versand prüft zusätzlich den Terminstatus;
Nurture geht erst zur 30-Tage-Wiedervorlage raus (nicht sofort).

**Arbeitsvorrat ohne tote Enden**: „Meine + freie Leads" enthält nicht
zugeordnete Leads (Banner + frei-Badge); qualifizierte Leads ohne aktiven
Termin stehen wieder in der Anrufliste; „falsche Nummer" bekommt eine
Wiedervorlage; Kundenantworten wecken den Lead; Tagesdigest (SLA rot je LM,
freie Leads an die Leitung); Cockpit-Liste „Termin-Rückmeldung offen";
Pfad „Verloren vor Termin" mit Gründen aus der Steuerdatei; „Leads VOT"
markiert überfällige Termine ohne Erfassung.

**Konsistenz**: Lead-Phase zieht bei automatischem Versand, 90-Tage-Ablauf
und Projekt-Storno nach; Board zeigt Gewonnen/Verloren nur 30 Tage
(Maßstab letzte Aktivität); Gründe in qualifizierung_fertig aus der Logik.

**Design**: gemeinsame LM-Unternavigation; SLA-Chips lesbar (Min/Std/AT
statt „16291 Min"); deutsche Wochentage (de_datum-Filter, auch
Projektierung/Montage); Anrufliste-Panel ohne doppelte Kopfzeile
(einbett=1); Icons statt Emojis (Anrufliste + Lead-Kopf, neue Symbole in
_symbole.html); Cockpit-Kennzahlen als Kacheln; Hauptmenü mit Start/
Lead-Management/Projektierung/Montage; Parametrierungs-Reiter umbrechen.

**Bewusst offen gelassen** (größer, mit Andreas zu priorisieren):
- Kohorten-Conversion je Eingangsmonat/Quelle statt Zeitraum-Zählung;
  monday-Leads ohne erstkontakt_am/terminiert_am verfälschen den Trichter.
- Haupt-Statistik zählt „Leads" nur aus der monday-Tabelle (zwei Funnels).
- „Leads VOT" und Lead-Modul-Termine sind weiter zwei Listen; gemeinsame
  Sicht „Meine Aufgaben heute" (Lead-Aktionen + Angebots-Wiedervorlagen).
- Qualifizierung → Erfassung vorbelegen auch bei freigabe_modus=admin.
- /api/leads hat kein Demo-Gate (legt aber demo=1-Leads an).
- Karte/Terminassistent: harte Hex-Farben; „Meine Termine" ohne
  v14-Karten-Layout.

## PLAN_LEAD_V1.1 (30.09.2026) – Umsetzung durch Claude Code (v21)

- **Auflösung Quelle/Kampagne** an einer Stelle (`quelle_kampagne_aufloesen`)
  für Parser, API und Import; Schnellanlage/Import wählen Quelle/Kampagne
  weiter per Dropdown (dort gibt es nichts Unbekanntes). Nebenbefund
  behoben: der Parser fand die Kampagne, gab sie aber nicht an
  `lead_anlegen` weiter.
- **Kanal „Standard“** = kein eigener Kanal (`kanal = NULL`); die
  Dropdown-Werte sind der jeweils erste Kanalwert der Angebotsprofile.
  monday-Quellen bleiben ohne Kanal („Kanal am Kunden“).
- **Kosten je Lead einer Kampagne** = Budget ÷ Eingänge im Kampagnen-
  zeitraum (leer ohne Budget); in der Übersichtstabelle ersetzt der
  Kampagnen-CPL den Quellenwert.
- **Quellen-Typ-Farben** aus dem Prototyp übernommen; der Paletten-
  Validator (Node) ist auf dem Entwicklungs-PC nicht installiert – der
  Prototyp gilt laut Plan als validiert. Jede Farbfläche trägt Zahl +
  Legende.
- **Jetzt dran** enthält SLA gelb/rot ohne ersten Versuch und fällige
  Rückrufwünsche; fällige Kaskaden-Schritte stehen in „Weiter versuchen“
  (sonst wäre die Gruppe „Weiter versuchen“ leer). „Rückruf heute“ =
  letztes Ergebnis Rückruf gewünscht mit `naechste_aktion_am` heute.
- **Stichworte** der Zeile 2 kommen über die Fragetexte der Qualifizierung
  („Heizung“/„Energieträger“, „Baujahr“, „Zeitrahmen“/„wann“) – das Blatt
  braucht keine Sonderspalte.
- **Chip-Zähler** zählen auf der Basisliste (nur Meine/Alle wirkt), die
  Gruppen auf der gefilterten Liste; „Sonstige“ ist nur in der reinen
  Arbeitsliste eingeklappt.
- **Modul-Einstieg** `lm_startseite`: leer = nach Rolle (Hauptrolle
  Leadmanagement → Anrufliste, sonst Übersicht).
- Nebenbefund B2 behoben: Portal-Text der Projektierung im Pilot-Modus.


---

# Lead-Management V2 (v23, PLAN_LEAD_V2 Phasen 104–112) – Bestandsabgleich und Entscheidungen

Stand 02.10.2026. Andreas hat entschieden, statt eines Lastenhefts direkt zu
codieren (PLAN_LEAD_V2.md Teil 1). Der Bestandsabgleich, den der Auftrag für
das Lastenheft verlangte, steht deshalb hier; die Kennzeichnung je Anforderung
([Bestand] / [Erweiterung] / [Neu]) stammt aus dem Read-only-Abgleich der neun
Bereiche A–I gegen den Code v22 (Rohdaten lokal in `diagnose/v23_bestand_*.json`).
Alles läuft weiter im **Demo-Modus** (`lead_freigabe_modus = admin`).

## V2.1 Bestandsabgleich – Überblick

| Einstufung | Anzahl Punkte | Beispiele |
|---|---|---|
| [Bestand] | 52 | Anrufliste mit Tasten 1–7, Kaskade aus der Steuerdatei, Vorlagen `nicht_erreicht`/`terminbestaetigung` mit ICS, Terminassistent mit AD-Profilen/Outlook/Routing, Glocke mit Zähler-Badge, Demo-Modus, Duplikatprüfung E.164 |
| [Erweiterung] | 60 | Kaskade 4 → 5 Stufen, Versuchs-Punkte mit Ergebnisfarbe, Lead-Akte → dreispaltige Kartei, AD-Profil um Kompetenzen/Handelsvertreter, ICS mit UID/SEQUENCE/CANCEL, Übersicht → persönliches Dashboard, API um Veranstaltung/GW |
| [Neu] | 37 | Tabelle nach monday-Vorbild mit Spaltenkonfiguration, Icon-Leiste, Boards Hauptboard/Terminiert, Reiter Kontaktiert, Sammelaktionen, To-Dos, Objektart, Vorab-Angebot, Vorab-Gespräch (Telefon/Teams), Handelsvertreter-Ansicht, Info-Veranstaltung mit Feiertagsregel, Ersatzkunde bei Absage, Stoppuhr/Meine Anrufe/Rufnummernsuche |
| [Neu, Bestand unklar] | 3 | Phase-82-Sicherheitstest über alle GET-Routen (im Ordner tests/ nicht auffindbar), Aktivitätstyp `mail_ein`, Status `bestaetigt` an Terminen (wird nie gesetzt) |

Was aus dem Diktat bereits existierte und unverändert bleibt: Anrufliste
(Ergebnis-Buttons, Tasten 1–7, Panel), Wiedervorlage-Kaskade (Blatt Kaskade),
Mail-Warteschlange mit Sendesperre, Terminassistent (Top 5, Fahrzeiten,
Outlook-Frei/Belegt), Lead-Akte als Vorgangsakte, Quelle · Kampagne · Kanal,
Übersicht/Statistik, Demo-Schalter, Rollenmodell, monday-Sync/Rückspielung.

## V2.2 Datenmodell (Phase 104)

Lead = Vorgang bleibt; alles Neue hängt an bestehenden Tabellen:

| Tabelle | Neue Spalten | Zweck |
|---|---|---|
| `kunden` | `objektart` (EFH/RH/REH/MFH), `parteien` | B3 – Rechnungsadresse = bestehende `rechnung_*` (v20) |
| `vorgaenge` | `ad_id`, `vorab_angebot`, `veranstaltung_id`, `teilgenommen` | A-7 Zuständiger AD/HV ohne Termin, F10, I3 |
| `vot_termine` | `typ` (vot/telefon/online), `medium`, `ics_uid`, `ics_sequence` | A-2 Vorab-Gespräch, E4 ICS-Umbuchung |
| `benutzer` | `buchungslink`, `nebenstelle` | F12 Book-with-me, CTI-Vorbereitung |
| `ad_profile` | `terminiert_selbst`, `kompetenz_sparten`, `kompetenz_kombi`, `kompetenz_mfh`, `kompetenz_gewerbe` | A-1 Handelsvertreter, F3 Produktkompetenz |
| `lead_aktivitaeten` | `call_id`, `richtung`, `nebenstelle` | D1 Vorbereitung CTI (heute leer) |
| neu `todos` | – | A2/F7 To-Dos, Glocke ohne Mail |
| neu `info_veranstaltungen` | – | I1/I2 eine Zeile je Termin |
| neu `benutzer_einstellungen` | – | A-14 Spaltenkonfiguration je Nutzer |

Sparte **GW (Gewerbe)** als fünfter Code in `INTERESSEN`/`SPARTEN`, Chips und
Badges; Erfassung startet wie WB im Freitext (kein Fragenkatalog); Statistik
sortiert GW ans Ende; monday-Mapping bleibt unverändert (Label „Gewerbe“ wird
dort weiterhin ignoriert – Freigabe durch Andreas nötig).

## V2.3 Steuerdatei `leadmanagement_logik_v1.xlsx`

- **Kaskade** jetzt 5 Stufen: 1 +2h · 2 +1d 18:00 `mail_nicht_erreicht` · 3 +3d ·
  4 +7d `mail_nicht_erreicht` · 5 +14d `mail_disqualifiziert` (letzter). Nach
  Stufe 5: Phase Nicht erreicht, Nurture +30 Tage, Buttons Nicht erreicht/
  Besetzt/Mailbox gesperrt (`versuche_max` = 5). Aktionen heißen generisch
  `mail_<vorlage>`.
- **Gründe**: neue Phase `verloren` (Zu teuer · Kein Interesse mehr · Bleibt bei
  Öl/Gas · Woanders unterschrieben · Sonstiges mit Freitext-Pflicht) und für
  `zurueckgestellt` „Nachbearbeitung, noch nicht bereit für VOT“ (F11).
  Bestehende Tabelle `ablehnungsgruende` (Angebote) bleibt; Verloren setzt
  offene Angebote mit dem Lead-Grund auf Abgelehnt.
- **Objektarten** (neu): code, bezeichnung, parteien_pflicht, erfassungs_wert
  (Vorbelegung O01/PO01).
- **Status** (neu, Mapping 5a + H2): eine Zeile je Lead-Phase mit Label,
  Farbe, Board, Gruppe und den monday-Statuswerten, die darauf abgebildet
  werden – die Lead-Phase bleibt die einzige Quelle der Wahrheit, die Gruppe
  ist eine Sicht darauf.

### Mapping monday-Status → Phase → Board → Gruppe (Blatt Status)

| Lead-Phase | Label / Farbe | Board | Gruppe | monday-Status (5a) |
|---|---|---|---|---|
| neu | Neu · grau | Hauptboard | Neu | Neuer Lead |
| in_kontaktierung | In Kontaktierung · rosa | Hauptboard | Neu | 1.–5. Kontaktversuch, erneuter Anruf, Telefongespräch, E-Mail, WhatsApp |
| qualifiziert | Qualifiziert · blau | Hauptboard | Neu | – |
| zurueckgestellt | Zurückgestellt · ocker | Hauptboard | Pausiert | Standby, Will sich selber zurückmelden, Nachbearbeitung |
| nicht_erreicht | Nicht erreicht · pink | Hauptboard | Disqualifiziert | Disqualifiziert - nicht erreicht |
| unqualifiziert | Unqualifiziert · rot | Hauptboard | Disqualifiziert | Disqualifiziert |
| terminiert | Terminiert · hellgrün | Terminiert | Angebotserstellung | Terminiert, Teams Meeting |
| erfasst | Erfasst · blaugrau | Terminiert | Angebotserstellung | Angebotserstellung, Vorab Angebot |
| angebot | Angebot · braun | Terminiert | Angebotsversand | Angebot versendet |
| gewonnen | Gewonnen · grün | Terminiert | Gewonnen | – |
| verloren | Verloren · grau | Terminiert | Verloren | – (Verloren vor Termin mit Kennzeichen) |

Gestrichene monday-Status (Export, AB gesprochen, Reklamation, Nicht erreicht
disqualifiziert) haben keine Entsprechung. „Klima“ ist das Interesse KL,
„E-Mail“/„WhatsApp“/„Telefongespräch“ sind Aktivitäten bzw. Terminarten.

## V2.4 Annahmen (PLAN_LEAD_V2 Teil 1, A-1 … A-15) – Kurzbegründung

- **A-1 Handelsvertreter = Kennzeichen am AD-Profil**, keine Rolle: nutzt
  Startadresse/Gebiet/Kapazität/Postfach mit; Leads VOT → Erfassung → Angebot
  unverändert; Rechte zentral in `lead_v2.zugriff_erlaubt`. Nachteil (Rechte an
  einem Profilfeld) ist durch die zentrale Gate-Funktion begrenzt.
- **A-2** Telefongespräch/Teams sind Terminarten an `vot_termine` (typ/medium),
  keine Phasen – sie zählen in der Kollision, nicht in der Tageskapazität.
- **A-3** Vorab-Angebot = Kennzeichen am Vorgang; Weg „Erfassung ohne Termin“
  aus der Kartei; keine Terminbestätigung; im Demo nur Kennzeichen testbar.
- **A-4** Nachbearbeitung = Zurückgestellt mit Grund + Pflicht-Wiedervorlage
  (sichtbar in Gruppe Pausiert und im Dashboard).
- **A-5** Kaskade 5 Stufen, Stufe 5 sendet `disqualifiziert`; Nurture +30 bleibt.
- **A-6** Objektart am Kunden (Objekt = Ausführungsort = Kundenadresse).
- **A-7** `vorgaenge.ad_id` als Vorzuweisung; der aktive Termin trägt weiter
  seinen eigenen `ad_id`.
- **A-8 [OFFEN 1]** Info-Lead → nächste Veranstaltung ab Eingang + 3 Tage
  Vorlauf (Parameter `info_vorlauf_tage`), API-Feld `veranstaltung` optional.
- **A-9 [OFFEN 2]** „Terminbestätigung erneut senden“ mit gleicher UID und
  SEQUENCE+1; Duplikate durch das Tool: Rufnummernsuche/Kontaktiert zeigen
  dieselbe Nummer in jeder Schreibweise, Zusammenführen bleibt manuell.
- **A-10** Sparte GW; MFH und Gewerbe sind Objektkompetenzen am AD-Profil.
- **A-11** Icon-Leiste mit 5 Einträgen + „Mehr …“; kein Einstieg geht verloren.
- **A-12** Dashboard für ID/LM/Admin und Handelsvertreter (F16); AD unverändert.
- **A-13** Puffer = max(30 Min, Fahrzeit), Dauer 90, Raster 30, Startwert 3
  Termine/Tag für neue Profile.
- **A-14** Spaltenkonfiguration je Nutzer in `benutzer_einstellungen`; Farben,
  Pflichtfelder, Ausschlussliste, Veranstaltungsparameter als LeadParameter
  (Parametrierung → Lead-Einstellungen, Abschnitte „Lead-Management V2“).
- **A-15** Dieser Abschnitt ersetzt das Lastenheft.

## V2.5 Standardantworten aus dem Bestandsabgleich (gelten als Annahme)

- Dashboard zeigt **beide** Wiedervorlage-Mechaniken (Lead: `naechste_aktion_am`
  / `zurueckgestellt_bis`; Angebotsverfolgung v10: `wiedervorlage_am`) in zwei
  beschrifteten Blöcken; Umschalter „Meine Arbeit | Team“; Demo-Leads im
  Demo-Modus eingeschlossen und gekennzeichnet.
- To-Dos als eigene Tabelle (nicht die Projektierungs-`aufgaben`); Empfänger
  alle aktiven Benutzer; Glocke art `todo` ohne Mail.
- Begriff „Innendienst“ in Tabelle/Kartei = `vorgaenge.leadmanager_id`.
- Versuchszähler: jedes Ergebnis zählt wie bisher; Sperre ab `versuche_max`.
- Letzter Kontakt (Spalte) = letzter Anruf; Mails stehen in der Timeline.
- Sparten-Badges einheitlich als v9-Chips; Kanban zeigt nur das aktive Board,
  Spalten bleiben Phasen.
- Hauptboard = Phase ohne Termin **und** kein Termin geplant/bestätigt;
  „Verloren vor Termin“ steht im Board Terminiert mit Kennzeichen.
- Sammelaktion „Status ändern“ mit einem gemeinsamen Grund/Datum, Aktivität
  je Lead.
- Pflichtfeld Vertriebskanal verlangt einen expliziten Wert; Interesse führend
  am Kunden; Kanaländerung in der Kartei setzt `kanal_manuell`.
- Konfliktwarnung bei manuellen Terminen: warnen mit Bestätigung, sperren nur
  bei voller Überlappung desselben AD; Outlook nur bei `kalender_sync = an`.
- Ersatzkunde: Phase Qualifiziert zuerst, dann In Kontaktierung mit
  `erreicht_am`; Radius 5 → 10 km; ältere ab 14 Tagen bevorzugt, mehrere
  Kandidaten mit Begründung.
- ICS-UID wird bei Umbuchung weitergetragen (SEQUENCE+1), Absage als
  METHOD:CANCEL; No-Show ohne Kundenmail.
- Handelsvertreter: kein Kandidat im Innendienst-Assistenten, außer der Lead
  ist ihm zugewiesen; Standard-Verantwortlicher Simon nur als HV-Zuständiger
  (`leadmanager_id` bleibt Innendienst); „Deals - Rene“ gesperrt (Sonderregel
  monday); Kanalwechsel auf Ausschlusskanal: Zuweisung bleibt, roter Hinweis +
  Glocke, manuelle Rücknahme; fehlende HV-Benutzer (Di Blasi, Lind, Kinkel,
  Leinenbach) legt Andreas an – das Tool zeigt den Hinweis.
- Info-Leads: eigene Quelle `info_veranstaltung` (Typ `veranstaltung`, eigene
  Farbe), bei Treffer „Kunde bereits im System“ immer eigener Vorgang mit
  rotem Hinweis, kein automatisches Zusammenführen; `standard_sparten` der
  Quelle greifen, wenn keine Sparte mitkommt.
- GW: Code `GW`, Freitext-Erfassung, Qualifizierungsfragen pflegt Andreas im
  Blatt Qualifizierung nach (bis dahin Minimal-Bogen).
- Telefonie: nur `tel:`-Link + Stoppuhr; keine Anbieterangabe (F2); CTI-Felder
  bleiben leer.

## V2.6 Umsetzungsentscheidungen der Phasen 105–111 (Agenten, 02.10.2026)

- **Boards (105):** Hauptboard-Kriterium = Blatt Status **und** kein aktiver
  Vor-Ort-Termin; Seitenzustände bleiben immer im Hauptboard; Endzustände 30 Tage
  (Filter Archiv). Manuell setzbar: neu/in_kontaktierung/qualifiziert (=
  Reaktivieren), zurueckgestellt (Datum + Grund; „meldet sich selbst“ ohne
  Datum → +`wv_meldet_sich_tage`), unqualifiziert, verloren, nicht_erreicht;
  terminiert/erfasst/angebot/gewonnen sind abgeleitet. Verloren setzt alle nicht
  archivierten Angebote (Entwurf … Versendet) auf Abgelehnt mit dem Lead-Grund.
  Versuchs-Punkte zählen nur Anrufe (Farbe je Ergebnis), „Letzter Kontakt“ auch
  Mails. Notiz-Spalte = `kunden.notizen`. Kanban behält Phasen als Spalten,
  zeigt nur das aktive Board. Sammelaktionen nie für Außendienst/HV.
- **Kartei (106):** Terminierung zählt nur VOT (typ vot) mit Status vorgemerkt/
  geplant; zweiter Klick plant keine zweite Bestätigung; setzt `ad_id`, falls
  leer. Objektart-Vorbelegung des Bogens über Codes (EFH→EFH, RH→RMH, REH→REH,
  MFH→MFH; Parteien → O03; PV → PO01); Blatt Objektarten trägt jetzt dieselben
  Codes. Vertriebskanal gilt nur mit explizitem Wert als gefüllt. E-Mail-Verlauf:
  eigene/automatisiert/Kollegen aus `kommunikation_log`, Kunde aus
  `angebots_mails` (Leads ohne Angebot haben keinen eingehenden Verlauf).
  Kompetenz ist in der Kartei nur Hinweis, keine Sperre.
- **Anruf (107):** `versuch_nr` zählt wie bisher jedes Ergebnis; Sperre ab
  `versuche_max` auch nach Reaktivieren; Vorschlag für die letzte Stufe +30
  Tage, manuell gewählter Zeitpunkt verschiebt die Nurture-Mail mit; Fälligkeits-
  Glocke für neu/in_kontaktierung/qualifiziert/nicht_erreicht, Dedup über
  Aktivität typ system; Rufnummernsuche vergleicht Ziffernfolgen (Klammer-Null
  entfernt, ≥ 7 nationale Ziffern, Durchwahl-Treffer ≥ 9 Ziffern); Dauer-
  Korrektur nur eigener Eintrag oder Admin, Obergrenze 4 h.
- **Termin (108):** Kandidatenbasis = Rolle aussendienst (Haupt/Zusatz) oder
  AD-Profil; ohne gepflegte Kompetenz unbeschränkt; Gebiet nur Abwertung;
  Kanal-Regel `kanal_ad_regel` (JSON) mit Härte Ausschluss; Kollision zählt alle
  Terminarten inkl. vorgemerkt, Kapazität nur VOT; Buchung setzt `ad_id`;
  Konfliktmodus warnen|sperren; Vorab online ohne Datum = vorgemerkt mit
  Kollege, Zeit später nachtragen; Absage von Vorab-Gesprächen ohne Kundenmail
  und ohne Ersatzdialog; Ersatzkunde-Punkte = km·2 − 20 (alt) − Klassenbonus +
  10 (in_kontaktierung); keine Neuoptimierung der Tagesroute (Annahme zu E3);
  OSM-Kacheln bleiben extern (V1-Ausnahme); Outlook-Rücklesen gebuchter Teams-
  Termine nicht umgesetzt (manuell nachtragen).
- **Handelsvertreter (109):** „Eigene Leads“ = `ad_id` = ich oder (ad_id leer
  und monday `leads.benutzer_id` = ich); HV geben nur an andere HV weiter;
  Sonderregel „Deals - Rene“ auch für Admin gesperrt (Wahrheit in monday);
  Tool-Zuweisung an gesyncten Leads schreibt `leads.benutzer_id` +
  `benutzer_manuell`; Standardregel F13: Deals - Rene → René, Person auf HV →
  diese, Deals/Deals - Simon ohne Person → Simon, Tool-Leads nie automatisch.
  Login-Ziel für HV = Modul-Einstieg (Dashboard mit eigenen Leads).
- **Dashboard/To-Dos (110):** `lm_startseite` leer = Dashboard für alle Rollen;
  Lead-Wiedervorlagen Büro = leadmanager_id ich oder frei, HV = ad_id;
  Angebots-Wiedervorlagen = Verantwortlicher ich (Büro auch NULL); „Fällig
  heute“ inkl. überfällig; Erledigt bei zurückgestelltem Lead = zurück auf Neu;
  Glocke art `todo` ohne Modul-Filter (auch Außendienst/Projektierung/Montage),
  keine Mail; Selbstzuweisung ohne Glocke. Projektierung/Montage erreichen
  `/lead-management/todos` nicht (Pfadlisten) – To-Dos dort nur über die
  Glocke sichtbar (offen für V3).
- **Info-Veranstaltung (111):** Info-Leads immer eigener Vorgang (kein 409);
  Bestandsverweis als Aktivität typ `hinweis` (kein Schema); Abgleich (E-Mail
  oder Telefon E.164) und Nachname normalisiert; Archivierung 6 h nach Beginn;
  je Monat höchstens ein Regeltermin (manuell verschobene zählen); Info-Leads
  ohne VOT stehen zusätzlich im Hauptboard; Statistik-Gruppe „Info-Veranstaltung“.

## V2.7 Offen nach v23 (für Andreas / V3)

- [OFFEN 1] endgültige Zuordnungsregel Info-Lead → Veranstaltung der Agentur
  (umgesetzt: Standardregel A-8 + API-Feld `veranstaltung`).
- [OFFEN 2] Rest des Auftragstexts (Duplikate durch das Tool, Punkt 8); umgesetzt
  sind „Terminbestätigung erneut senden“ und die Rufnummernsuche.
- Vier Handelsvertreter als Benutzer anlegen (Di Blasi, Lind, Kinkel,
  Leinenbach), AD-Profile pflegen, Buchungslinks hinterlegen, Mail-Texte F9
  einsetzen, Kanal „Messe“ pflegen, GW-Qualifizierungsfragen ergänzen.
- `verloren` steht nicht in `LEAD_PHASEN_MANUELL`: „Verloren vor Termin“ ohne
  Angebot könnte durch eine spätere Ableitung überschrieben werden – bewusst
  belassen, damit ein später angenommenes Angebot weiter „gewonnen“ ableitet.
- Statistik: Gesprächsdauer je Leadmanager nicht ausgewertet (nur in „Meine
  Anrufe“ je Liste).
- Performance: Boards laden alle Vorgänge mit Lead-Phase in Python (wie
  `board_daten`); für große Bestände SQL-Filter/Paginierung nachrüsten.
- Rollen: Sammelaktions-Sperre, Erzwingen und Vorlagenpflege prüfen die
  Hauptrolle `benutzer.rolle` (wie im Bestand).
- Demo-Risiko: `/api/leads` legt im Demo-Modus `demo = 1` an – bei der
  Umstellung auf „alle“ „Behalten“ wählen.
