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
