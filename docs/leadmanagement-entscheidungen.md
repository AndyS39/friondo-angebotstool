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
