# Umsetzungsplan v19: Vertriebler-Ansicht mobil (Mein Tag), automatische Wiedervorlage nach Angebotsversand, Dialog „Nächster Schritt“, Bestellung angekündigt, allgemeine Suche

**Fassung 13.10.2026 für den kombinierten Durchlauf v31 → v32** (Entwurf:
Claudia Castro aus den Punkten von Andreas, 13.10.2026; Prüfung und Einfügung
durch den Angebotstool-Chat, Andreas, 13.10.2026 – Entscheidungen unverändert,
geändert sind Vorspann, der Abschnitt „Einfügung in den Durchlauf“ und die mit
**(AT-Chat)** markierten Zusätze).

Voraussetzung und Stand 13.10.2026: v29 ist ausgerollt; **v30 (PLAN_V18) ist
fertig gebaut und committet** (4527c20 plus Nachträge bis 1f0b764, Rollout im
Wartungsfenster 13.10.). **Dieser Plan wird im selben Durchlauf wie
PLAN_LEAD_V5 (v31, Phasen 153 bis 160) umgesetzt: erst PLAN_LEAD_V5, dann
dieser Plan, EIN gemeinsamer Commit am Ende** (Entscheidung Andreas
13.10.2026; die Vorbedingung „v30 und v31 auf dem Server“ entfällt damit –
gebaut wird auf dem committeten v30-Stand plus dem v31-Zwischenstand desselben
Durchlaufs). CLAUDE.md und
`konfigurator_logik_v5.xlsx` sind Live-Master im Projektordner
`C:\Users\a.scheelen\Tools\Angebotstool` (Git-Arbeitskopie). ALLE PHASEN
DIESES PLANS IN EINEM DURCHLAUF UMSETZEN (Reihenfolge einhalten, jede Checkbox
nach Umsetzung und Test abhaken, am Ende Gesamtübersicht mit Testergebnissen
und offenen Punkten, fachliche Rückfragen gebündelt). **Ein gemeinsamer Commit
am Ende des Durchlaufs** (Arbeitsweise seit v28/v29), migrate.py idempotent,
**nur additive Migrationen** (v31-Code muss auf der v32-Datenbank
weiterlaufen, Rückweg `rollback.bat --nur-code`). **Kein git push vor
Freigabe.**

CLAUDE-Abschnitt: **„Neu in v32“** – bestätigt 13.10.2026 (v30 = PLAN_V18 in
der Zuordnungstabelle, v31 = PLAN_LEAD_V5 schreibt der erste Teil des
Durchlaufs). Phasen **161 bis 165** – bestätigt (153 bis 160 = PLAN_LEAD_V5).
Vor dem Bau trotzdem einmal gegen die Tabelle prüfen; bei Abweichung die
nächsten freien Nummern nehmen und durchgängig ersetzen. Die v27-Regeln gelten
(`def`-Routen, keine offene Datenbanksitzung während Netz-I/O,
Scheduler-Rahmen, Wächter-Test `tests/test_v27_sitzungen.py` grün,
`docs/betrieb.md` fortschreiben, wenn ein Punkt den Betrieb berührt). Design
v2 (v30, Hell/Dunkel-Tokens) ist für alle neuen Oberflächenteile verbindlich;
die Zurück-Navigation (v30) gilt auch für die neuen Seiten.

Geltungsbereich: Angebotstool, Sicht des Außendienstes (Rolle Außendienst,
auch als Mehrfachrolle), Angebotsverfolgung auf Vorgangsebene, Versand
(Einzel und Kombi), Ablehnungsdialog, Startseiten-Kacheln des Innendienstes
nur dort, wo Phase 163 es sagt, sowie ein Suchfeld im Hauptmenü für alle
Rollen. Konfiguratoren, Angebots-PDF, Protokoll-PDF, monday-Sync und
monday-Rückspielung bleiben fachlich unverändert (die Rückspielung der
Ablehnung läuft über den bestehenden Weg). Lead-Management-Boards,
Terminassistent und Kaskade werden nicht geändert; die neue Vertriebler-
Ansicht liest nur aus `vot_termine`.

## Einfügung in den Durchlauf v31/v32 (Angebotstool-Chat, 13.10.2026)

- **Objekte aus v31 mitdenken:** `vot_termine.objekt_id` (v31, Phase 153) ist
  die Adresse des Termins. Die Termin-Karte in „Mein Tag“ zeigt **Straße und
  Ort des Objekts** (Fallback Kundenadresse bei Ein-Objekt-Vorgängen), bei
  mehreren Objekten je Objekttermin eine Karte mit Objekt-Bezeichnung;
  „Erfassung starten“ übergibt das Objekt (v31). Der Maps-Link nutzt die
  Objektadresse.
- **monday-Termine in `vot_termine` nachführen:** der monday-Sync legt seit
  v23 für VOT-Daten einen `vot_termine`-Eintrag an; damit „Mein Tag“ allein
  aus `vot_termine` stimmt, muss der Sync bei **geändertem VOT-Datum** den
  bestehenden Eintrag aktualisieren (nicht duplizieren) und bei gelöschtem
  Datum auf `abgesagt` setzen; `scripts/vot_abgleich.py` (Phase 161) meldet
  Abweichungen zwischen `leads.vot_datum` und `vot_termine` und repariert mit
  `--anlegen`. Der Sync bleibt ein Scheduler-Lauf nach v27-Regeln.
- **Innendienst/Admin behalten die Tabelle als zweite Darstellung
  [ANNAHME, AT-Chat]:** „Mein Tag“ ersetzt für den Außendienst die Tabelle;
  Innendienst/Admin sehen dieselbe Seite als Karten, bekommen aber oben einen
  Umschalter **„Karten | Tabelle“** (Standard Karten, Wahl je Nutzer in
  `benutzer_einstellungen`); die bisherige Tabelle bleibt als Template
  `leads/liste.html` erhalten – bei mehreren hundert offenen Leads ist die
  Tabelle für den Innendienst weiter das schnellere Werkzeug. Wenn Andreas das
  nicht will: den Zusatz in Phase 161 streichen, dann entfällt die Tabelle wie
  von Claudia beschrieben.
- **Ablehnung über EINEN Weg:** die Route „Nächster Schritt → abgelehnt“
  (Phase 163) ruft `kern.lead_verloren(vorgang, grund)` (v23: setzt die
  Lead-Phase auf Verloren mit Grund, lehnt offene Angebote über
  `lead_boards.angebote_ablehnen` ab, monday-Rückspielung wie heute). Die
  fünf Gründe sind dieselben wie die Lead-Gründe `verloren` aus
  `leadmanagement_logik_v1.xlsx` (Blatt Gruende) – die Parametrierungsliste
  der Ablehnungsgründe (v8) und das Blatt bleiben zwei Pflegeorte, werden aber
  per Migration auf dieselben fünf Texte gebracht; der ID-Dialog „Grund der
  Ablehnung“ nutzt die Angebotstool-Liste wie bisher.
- **Glocke „Fällig heute“ (Phase 162)** ist eine Angebotstool-Glocke über
  `benachrichtigungen` (art `nachfassen`), nicht über
  `leadmanagement.benachrichtigen` – sie fällt damit nicht unter
  `glocke_lead_arten` (v29). Zustellung über den bestehenden Lauf
  `benachrichtigungen` (v27), kein neuer Lauf, keine Mail.
- **Versand-Hook (Phase 162) an allen Versandwegen:** Versand-Erkennung
  (`mail_sync`, Scheduler, `db.kurz()`), Knopf „Als versendet markieren“
  (v13), Kombi-Versand (einmal je Mail), externer TAIFUN-Eintrag „Extern
  erledigt“ [ANNAHME: zählt als Versand am Datum des Eintrags]. Die
  Wiedervorlage nutzt die bestehenden Spalten `vorgaenge.wiedervorlage_am` und
  `wiedervorlage_benutzer_id` (v10) – keine neue Verantwortlichen-Spalte.
- **Suche (Phase 164):** Rufnummern-Normalisierung und Endziffern-Logik aus
  `lead_anrufliste` (v23/v31) wiederverwenden; das Feld sitzt in `base.html`
  zwischen Logo und „Menü ☰“ mit v30-Tokens; `tojson` in on*-Attributen nur
  mit `forceescape` (v30-Nachtrag 24). Die Design-Entscheidung v30 „nur
  Optik“ bleibt bestehen – die Kundensuche ist eine neue Entscheidung vom
  13.10.
- **Rollout-Vorbereitung und Lasttest einmal für v31 + v32** am Ende des
  Durchlaufs (siehe PLAN_LEAD_V5, Einfügung): Lasttest Profil `normal` mit
  Lead-Nutzern, weil das Lead-Modul mit v31 für alle Rollen scharf ist;
  „Mein Tag“ und die Suche kommen als Routen ins Lastmodell (AD-Profil).

## Entscheidungen (Chat Angebotstool, 13.10.2026, Punkte von Andreas, abgestimmt mit Claudia Castro)

- **Eine Terminliste für den Vertriebler.** „Leads VOT“ wird zur mobilen
  Vertriebler-Ansicht **„Mein Tag“**. Der Außendienst sieht nur Leads, die
  bereits terminiert sind und ihm zugewiesen wurden (Zuweisung über die
  monday-Spalte „Verantwortlicher“ bzw. über den Terminassistenten; der AD
  weist nicht selbst zu). Quelle ist ausschließlich `vot_termine` (dort liegen
  seit v23 Tool-Termine und monday-VOT-Termine gemeinsam), damit VOT-Termine
  überall gleich stehen. Die Lead-Management-Sicht „Meine Termine“ zeigt
  denselben Datenbestand; eine doppelte Pflege gibt es nicht.
- **Pflichtinformationen je Termin:** Datum, Uhrzeit, Kunde, Straße und Ort,
  Telefon, Button „Erfassung starten“. Telefon als Anruf-Link (`tel:`),
  Anschrift als Karten-Link (Google Maps), Sparten-Badges WP/PV/KL/WB klein
  dabei.
- **„Termine heute“ oben**, alle übrigen Termine darunter (chronologisch),
  die bestehenden Filter (Termin, Vertriebler, Status) bleiben; Innendienst
  und Admin sehen weiterhin alle Vertriebler.
- **Automatische Wiedervorlage nach Angebotsversand:** Versanddatum plus
  **3 Werktage** (Montag bis Freitag, NRW-Feiertage ausgenommen); bei
  **Mehrfamilienhaus** (Objektart MFH am Kunden) **5 Werktage** (Ergänzung
  Andreas 13.10.2026). Verantwortlicher = Außendienstler des Vorgangs. **Der AD ruft an, nicht der
  Innendienst.** Die Wiedervorlage erscheint im Block „Fällig heute“ der
  Vertriebler-Ansicht mit Notizfeld und den letzten Kundenaktivitäten.
- **Dialog „Nächster Schritt“ nach dem Anruf** mit genau drei Wegen:
  1. **Abgelehnt** mit Grund aus fester Auswahl: **zu teuer · kein Interesse
     mehr · bleibt bei Öl/Gas · woanders unterschrieben · sonstiges** (bei
     „sonstiges“ Pflicht-Freitext). Bedienung wie im Lead-Management (Chips,
     ein Klick, Freitext nur bei sonstiges).
  2. **Bestellung kommt**: Vorgang erhält den Verfolgungsstatus **„Bestellung
     angekündigt“**, Hot-Ampel wird **heiß**. Auf dem Vertriebler-Dashboard
     gibt es dafür einen **eigenen Block „Heiße Kunden“**.
  3. **Nochmal anrufen**: in **3 Werktagen** oder manuelles Datum **ohne
     Uhrzeit**.
- **Allgemeine Suche:** Suchfeld im Hauptmenü **für alle Rollen**; der
  Kunde erscheint schon beim Eintippen des Namens; Außendienst findet nur
  eigene Kunden.
- **Mobil:** Zielgerät Smartphone im Hochformat; dieselbe Seite passt sich
  an, Desktop-Darstellung bleibt. Kein separates Mobil-Tool.

## Darstellungsvorschlag aus der Sichtung anderer Tools (13.10.2026)

Gesichtet wurden die mobilen Sichten gängiger Vertriebs-CRMs (Pipedrive,
Pipeline CRM, monday CRM, einfache Lead-Apps). Gemeinsamer Nenner der
Außendienst-Startseiten: eine **Tagesliste** („heute“), auf der Termine und
fällige Anrufe als Aufgaben untereinander stehen, **ein Klick je Ergebnis**
nach dem Anruf statt Formular, ein **Aktivitätsverlauf** je Kunde, eine
**Pipeline** mit wenigen Stufen als Chip am Kunden und eine **Suche ganz
oben**. Daraus für Friondo (wird in den Phasen unten umgesetzt):

1. **„Mein Tag“ als eine Spalte von Karten**, von oben nach unten: Fällig
   heute (Anrufe) · Termine heute · Heiße Kunden · Weitere Termine. Jede Karte
   hat genau eine Hauptaktion rechts (Anrufen bzw. Erfassung starten).
2. **Verfolgungs-Chip je Vorgang** mit fünf Stufen: Versendet → Nachgefasst
   → Bestellung angekündigt → Angenommen | Abgelehnt. Der Chip steht in der
   Vorgangsakte, in „Meine Angebote“ und in der Angebotsliste des
   Innendienstes (dort als Filter).
3. **Anruf-Karte** (Fällig heute): oben Kunde + Telefon-Link, darunter die
   drei Ergebnis-Knöpfe nebeneinander (Abgelehnt · Bestellung kommt ·
   Nochmal anrufen), darunter aufklappbar „Letzte Aktivitäten“ (drei
   Einträge) und das Notizfeld.
4. Keine Kanban-Pipeline auf dem Handy (zu breit, nicht nötig): Stufen
   nur als Chip und als Filter in den Listen.

## Phase 161: Vertriebler-Ansicht „Mein Tag“ (mobil)

- [x] **Route und Template:** `GET /leads` bleibt die Adresse (Shortcut
      „Leads VOT“ auf der Startseite heißt für die Rolle Außendienst **„Mein
      Tag“**, für Innendienst/Admin weiterhin „Leads VOT“); neues Template
      `templates/leads/mein_tag.html` für Außendienst, Innendienst/Admin
      erhalten dieselbe Seite mit zusätzlichem Vertriebler-Filter oben
      (Screenshots vorher nach `docs/design-v32/leads-vot-vorher.png`).
      **(AT-Chat)** Für Innendienst/Admin zusätzlich Umschalter „Karten |
      Tabelle“ (Standard Karten, je Nutzer gespeichert); die bisherige Tabelle
      bleibt als zweite Darstellung erhalten [ANNAHME, siehe Einfügung]. Aufbau als Kartenliste in
      einer Spalte (Design v2, Tokens aus v30), unter 600 px Breite
      Vollbreite, darüber zentriert mit höchstens 720 px.
- [x] **Datenquelle:** nur `vot_termine` mit `status` terminiert/unbestätigt
      [ANNAHME: Statuswerte wie in v23/v29, abgesagte und No-Show-Termine
      fallen heraus] und ohne verknüpftes Angebot am Vorgang (Regel von
      „Leads VOT“ seit v1 bleibt). Außendienst: nur `vorgaenge.ad_id` =
      eigener Benutzer; Innendienst/Admin: alle, Filter Vertriebler. Für
      Vorgänge aus dem monday-Sync ohne `vot_termine`-Eintrag legt der Sync
      den Termin wie seit v23 an; **(AT-Chat)** bei geändertem monday-VOT-Datum
      aktualisiert der Sync den vorhandenen Eintrag, bei gelöschtem Datum
      setzt er ihn auf `abgesagt` (Test); ein Prüfskript `scripts/vot_abgleich.py`
      meldet Vorgänge mit VOT-Datum ohne Termin-Zeile und legt sie beim Aufruf
      mit `--anlegen` nach (einmal im Rollout ausführen, Protokoll in die
      Gesamtübersicht).
- [x] **Blöcke in dieser Reihenfolge** (Überschriften wörtlich): **„Fällig
      heute“** (Phase 162, Anrufe) · **„Termine heute“** · **„Heiße Kunden“**
      (Phase 163) · **„Weitere Termine“** (alle künftigen ab morgen,
      chronologisch; überfällige Termine der Vergangenheit ohne Erfassung
      stehen zuoberst in „Termine heute“ mit rotem Label „überfällig“,
      Überfällig-Banner aus v15-Nachtrag entfällt dafür in dieser Sicht).
      Leere Blöcke zeigen das Makro `leer_zustand` mit dem Text „Heute nichts
      offen.“ bzw. „Keine weiteren Termine.“
- [x] **Termin-Karte** (Pflichtinhalt, nichts weglassen): Zeile 1 Datum als
      „Mo, 13.10.“ + Uhrzeit „14:00 Uhr“ fett; Zeile 2 Kundenname (Anrede
      Vorname Nachname); Zeile 3 Straße Hausnummer, PLZ Ort **des Objekts**
      (`vot_termine.objekt_id`, v31; Fallback Kunde; bei mehreren Objekten
      Objekt-Bezeichnung davor) als Link
      `https://www.google.com/maps/search/?api=1&query=<Adresse
      URL-kodiert>` (neuer Tab); Zeile 4 Telefon als `tel:`-Link mit
      Telefon-Icon aus `_symbole.html`; Sparten-Badges WP/PV/KL/WB rechts
      oben; Herkunfts-Badge „monday“ oder „Tool“ klein grau [ANNAHME];
      Hauptknopf unten rechts **„Erfassung starten“** (volle Breite unter
      600 px) → bestehende Startweiche der Erfassung mit vorausgewähltem
      Kunden (wie Klick in „Leads VOT“ bisher). Zweitlink „Akte“ (klein) zur
      Vorgangsakte. Teilweise erfasste Mehr-Sparten-Vorgänge zeigen die
      Status-Chips je Sparte wie bisher.
- [x] **Filter bleiben:** Filterleiste als aufklappbare Karte oben
      (Termin von/bis, Status, bei ID/Admin Vertriebler); Standard = alles.
      Sortierung fest chronologisch (innerhalb der Blöcke).
- [x] **Mobil-Feinheiten:** `viewport-fit=cover` und Safe-Area-Abstände wie
      bei der mobilen Erfassung (v14); Schaltflächen mindestens 44 px hoch;
      kein horizontales Scrollen; PWA-Manifest um die Startadresse `/leads`
      für die Rolle Außendienst ergänzen [ANNAHME: Manifest-`start_url`
      bleibt `/`, Startseite leitet AD-Benutzer bei nur einer Rolle direkt auf
      `/leads`].
- [x] **Lead-Management „Meine Termine“ (F6)** zeigt denselben Bestand: dort
      nur den Link „Zur Tagesansicht“ auf `/leads` ergänzen, keine
      Logikänderung.
- [x] Test `tests/test_v32_mein_tag.py`: AD sieht nur eigene Termine; Termin
      heute 14:00 steht in „Termine heute“, Termin morgen in „Weitere
      Termine“, Termin gestern ohne Erfassung in „Termine heute“ mit
      „überfällig“; Karte enthält Datum, Uhrzeit, Name, Straße, Ort,
      `tel:`-Link, Maps-Link, Knopf „Erfassung starten“; Vorgang mit
      verknüpftem Angebot erscheint nicht; ID sieht alle und kann nach
      Vertriebler filtern. Playwright-Screenshot bei 390 × 844 px
      (Hochformat) und 1280 px nach `docs/design-v32/`.

## Phase 162: Automatische Wiedervorlage nach Angebotsversand, Block „Fällig heute“

- [x] **Werktagsrechner:** `app/werktage.py` mit `plus_werktage(datum, n)`
      (Montag bis Freitag, NRW-Feiertage über die bestehende Feiertagslogik
      der Info-Veranstaltung v23, Osterformel; kein neuer Code für Feiertage,
      Funktion dort herausziehen und beide Stellen darauf umstellen). Test mit
      Kontrollwerten: Fr 10.10.2026 + 3 = Mi 15.10.2026; Mi 30.09.2026 + 3 =
      Di 06.10.2026 (3.10. Feiertag, Wochenende); Do 17.12.2026 + 3 =
      Di 22.12.2026.
- [x] **Versand-Hook:** Nach erfolgreichem Versand eines Angebots (Einzel- und
      Kombi-Versand, Statuswechsel auf „Versendet“ in der bestehenden
      Versand-Erkennung; auch externer TAIFUN-Eintrag mit Versand) setzt das
      Tool am Vorgang `wiedervorlage_am` = Versandtag + 3 Werktage, bei
      `kunden.objektart = MFH` (Spalte seit v23) + 5 Werktage (beide Werte
      als Parameter `nachfass_werktage` = 3 und `nachfass_werktage_mfh` = 5 in
      den Angebotstool-Einstellungen, Standard wie genannt; fehlende Objektart
      zählt als Nicht-MFH),
      `wiedervorlage_benutzer_id` = `vorgaenge.ad_id` (bestehende Spalte aus
      v10, **(AT-Chat)** keine neue Spalte),
      `wiedervorlage_art` = `angebot_nachfassen` (neue Spalte, Text) und
      schreibt die Aktivität „Wiedervorlage automatisch gesetzt: Angebot
      nachfassen am TT.MM.JJJJ“ in den Notizen-Chat (Autor „System“).
      [ANNAHME] Eine bereits vorhandene Wiedervorlage wird nur überschrieben,
      wenn sie **vor** dem errechneten Datum liegt oder leer ist; eine spätere
      manuelle Wiedervorlage bleibt stehen. Ohne AD am Vorgang bleibt der
      Verantwortliche der versendende ID-Benutzer [ANNAHME].
- [x] **Block „Fällig heute“** in „Mein Tag“ (Phase 161): alle Vorgänge mit
      `wiedervorlage_verantwortlich` = eigener Benutzer und `wiedervorlage_am`
      ≤ heute, überfällige zuerst mit rotem Label „seit TT.MM.“. Anruf-Karte:
      Kunde, Telefon-Link, Angebots-Kurzinfo („WP-Angebot vom 10.10.2026,
      Endbetrag 32.450,00 €“; Kundenpreis, nie EK/DB), Hot-Ampel-Punkt, die
      drei Ergebnis-Knöpfe (Phase 163), aufklappbar **„Letzte Aktivitäten“**
      = die letzten drei Einträge aus Mail-Verlauf, Notizen-Chat und
      Signaturprotokoll des Vorgangs (Zeitstempel, Art, Kurztext), darunter
      **Notizfeld** „Notiz zum Gespräch“ (ein Feld, speichert als neuer
      Eintrag im Notizen-Chat, keine zweite Notizspur). Die Startseiten-Kachel
      „fällig“ des Innendienstes zählt diese AD-Wiedervorlagen wie seit v10
      **nicht** mit.
- [x] **Glocke:** Angebotstool-Glocke art `nachfassen` über
      `benachrichtigungen` (v27-Lauf `benachrichtigungen`, kein neuer Lauf)
      meldet dem AD morgens die Anzahl „Fällig heute“ [ANNAHME: keine Mail,
      nur Glocke]; **(AT-Chat)** nicht über die Lead-Glocken (v29), damit
      `glocke_lead_arten` sie nicht abschaltet.
- [x] Test `tests/test_v32_wiedervorlage.py`: Versand am Fr 10.10.2026 setzt
      Wiedervorlage Mi 15.10.2026, Verantwortlicher = AD, Aktivität im Chat;
      derselbe Versand bei Objektart MFH setzt Fr 17.10.2026; Parameter
      `nachfass_werktage_mfh` = 6 → Mo 20.10.2026;
      Kombi-Versand setzt einmal (nicht je Angebot); vorhandene spätere
      Wiedervorlage bleibt; am 15.10. erscheint der Vorgang beim AD in „Fällig
      heute“, beim ID nicht in der Kachel; Notiz aus dem Feld landet im
      Notizen-Chat mit Autor AD; „Letzte Aktivitäten“ zeigt den Versand.

## Phase 163: Dialog „Nächster Schritt“, Bestellung angekündigt, Heiße Kunden, Verfolgungs-Chip

- [x] **Ablehnungsgründe des Angebotstools** (Arbeitsanweisung an der
      Parametrierungsliste `/parametrierung/ablehnungsgruende`, Migration
      `migration_v32_ablehnungsgruende`): die fünf Gründe **„zu teuer“, „kein
      Interesse mehr“, „bleibt bei Öl/Gas“, „woanders unterschrieben“,
      „sonstiges“** anlegen, falls nicht vorhanden, und als `aktiv` + Reihenfolge
      1 bis 5 setzen; „sonstiges“ erhält das Kennzeichen `freitext_pflicht`
      (neue Spalte, Standard nein). Bestehende andere Gründe bleiben für die
      Statistik-Historie erhalten, werden aber `aktiv = nein` gesetzt
      [ANNAHME; der Systemgrund „90 Tage Ablauf“ bleibt aktiv]. Der ID-Dialog
      „Grund der Ablehnung“ nutzt dieselbe Liste und zeigt nur aktive Gründe.
- [x] **Route `POST /vorgaenge/{id}/naechster-schritt`** (Außendienst nur bei
      eigenem Vorgang, ID/Admin überall) mit Feld `schritt` ∈
      `abgelehnt | bestellung | nochmal`:
      - `abgelehnt` + `grund_id` (+ `freitext` bei sonstiges, sonst 400): alle
        versendeten, nicht überholten Angebote des Vorgangs auf „Abgelehnt“
        mit diesem Grund – **(AT-Chat)** über `kern.lead_verloren(vorgang,
        grund)` (v23: Lead-Phase Verloren mit demselben Grund, Angebote über
        `lead_boards.angebote_ablehnen`, monday-Rückspielung wie heute; bei
        Vorgängen ohne Lead-Phase nur der v8-Angebotsweg), Wiedervorlage
        leeren, Hot-Ampel auf kalt, Verfolgungsstatus `abgelehnt`, Aktivität
        „Kunde hat abgelehnt: <Grund>“.
      - `bestellung`: Verfolgungsstatus `bestellung_angekuendigt` (neue Spalte
        `vorgaenge.verfolgung_status`, Werte `versendet | nachgefasst |
        bestellung_angekuendigt | angenommen | abgelehnt`, Migration füllt aus
        dem Angebotsstatus), Hot-Ampel **heiß**, Aktivität „Bestellung
        angekündigt“, Wiedervorlage auf heute + 7 Werktage [ANNAHME, damit der
        Vorgang nicht aus dem Blick fällt], Glocke an den Innendienst „Bestellung
        angekündigt: <Kunde>“ [ANNAHME].
      - `nochmal` + `wann` ∈ `3wt | datum` (+ `datum` TT.MM.JJJJ ohne Uhrzeit):
        Wiedervorlage = heute + 3 Werktage bzw. das Datum, Verfolgungsstatus
        `nachgefasst`, Aktivität „Nochmal anrufen am TT.MM.JJJJ“.
      Das Notizfeld der Karte wird bei jedem Schritt mitgespeichert (ein
      Chat-Eintrag, Notiz vor der System-Aktivität).
- [x] **Dialog auf der Anruf-Karte** (Phase 162): drei Knöpfe nebeneinander
      „Abgelehnt“ (rot) · „Bestellung kommt“ (grün) · „Nochmal anrufen“
      (blau). Abgelehnt klappt die fünf Grund-Chips auf, bei „sonstiges“
      Pflicht-Freitext; Nochmal anrufen klappt „In 3 Werktagen (Mi 15.10.)“ als
      vorgewählten Chip und ein Datumsfeld (nur Datum) auf; Bestellung kommt
      speichert sofort mit Bestätigungszeile. Nach dem Speichern verschwindet
      die Karte aus „Fällig heute“ (bei Bestellung wandert sie in „Heiße
      Kunden“), Rückgängig-Link 10 s wie im Lead-Dashboard (v31) [ANNAHME].
      Derselbe Dialog steht in der Vorgangsakte im Verfolgungs-Block (ID und
      AD).
- [x] **Block „Heiße Kunden“** in „Mein Tag“: alle eigenen Vorgänge mit
      Hot-Ampel heiß oder Verfolgungsstatus `bestellung_angekuendigt`,
      Karte mit Kunde, Telefon-Link, Angebots-Kurzinfo, Chip „Bestellung
      angekündigt“ (orange) bzw. „heiß“, Datum der nächsten Wiedervorlage,
      Link zur Akte. Für Innendienst/Admin zusätzlich eine Startseiten-Kachel
      **„Bestellung angekündigt“** neben „Versendete Angebote“ (Anzahl,
      Klick = Angebotsliste mit Filter Verfolgungsstatus).
- [x] **Verfolgungs-Chip** (Makro `verfolgung_chip` in `_komponenten.html`,
      fünf Stufen wie im Darstellungsvorschlag, Farben aus den Status-Tokens
      v30) in Vorgangsakte (Kopfkarte neben Hot-Ampel), „Meine Angebote“ und
      Angebotsliste (Spalte + Filter). „Angenommen“ setzt der bestehende
      Annahme-/Signaturweg, „abgelehnt“ der Ablehnungsweg (ID-Dialog und
      Phase-163-Route gleichermaßen).
- [x] Test `tests/test_v32_naechster_schritt.py`: Abgelehnt mit „zu teuer“
      → beide versendeten Angebote abgelehnt, Grund gespeichert, Statistik
      „Ablehnungsgründe“ zählt; sonstiges ohne Freitext → 400; Bestellung
      kommt → Status `bestellung_angekuendigt`, Ampel heiß, Vorgang in „Heiße
      Kunden“, ID-Kachel zählt 1; Nochmal 3wt am Fr 10.10. → Wiedervorlage
      Mi 15.10.; Nochmal Datum 20.10.2026 → Wiedervorlage 20.10., keine Uhrzeit;
      AD darf fremden Vorgang nicht ändern (403); 90-Tage-Lauf respektiert die
      gesetzten Wiedervorlagen (Bestandstest bleibt grün).

## Phase 164: Allgemeine Suche im Hauptmenü

- [x] **Suchfeld** in der Kopfzeile von `base.html` (rechts neben dem Logo,
      vor dem Dropdown „Menü“; unter 600 px als Lupen-Icon, das ein Feld in
      voller Breite ausklappt), Platzhalter **„Kunde suchen …“**, auf allen
      Seiten außer Login/PIN-Wechsel und Erfassungsbogen. Dies ist bewusst
      **nur die Kundensuche**, nicht die Startseiten-Umstellung aus dem
      v30-Prototyp.
- [x] **Route `GET /suche.json?q=`** (ab 2 Zeichen, höchstens 8 Treffer,
      Antwort in unter 300 ms auf der Server-DB-Kopie): sucht in `kunden`
      nach Vorname, Nachname, „Vorname Nachname“, Ort und [ANNAHME]
      Telefon-Endziffern (ab 4 Ziffern, wie die Rufnummernsuche des
      Lead-Managements); Außendienst nur Kunden mit mindestens einem eigenen
      Vorgang (`vorgaenge.ad_id`), Montage keine Suche. Treffer: Name,
      Ort, Sparten-Badges, Verfolgungs-Chip des jüngsten Vorgangs; Klick
      öffnet die **Vorgangsakte** des jüngsten offenen Vorgangs (sonst die
      Kundenakte). Index auf `kunden(nachname)` und `kunden(ort)` anlegen,
      falls nicht vorhanden (`index_pruefung.py` erweitern).
- [x] **Bedienung:** Vorschlagsliste erscheint beim Tippen (Debounce 200 ms),
      Pfeiltasten + Enter, Escape schließt; Enter ohne Auswahl öffnet
      `/suche?q=` als Trefferseite (gleiche Logik, alle Treffer, Tabelle).
      Keine EK/DB-Werte in Treffern.
- [x] Test `tests/test_v32_suche.py`: „Mül“ findet „Müller“, „Peter M“ findet
      „Peter Müller“, „Krefeld“ findet Kunden in Krefeld, „4711“ findet
      +49 203 … 4711; AD findet fremde Kunden nicht; Montage erhält 403;
      Treffer enthalten keine EK/DB-Felder; Antwortzeit auf der DB-Kopie unter
      300 ms (Messung in die Gesamtübersicht).

## Phase 165: Tests, Rollout-Vorbereitung, Doku, CLAUDE.md v32

- [x] **Tests gesamt:** `tests/test_v32_mein_tag.py`, `test_v32_wiedervorlage.py`,
      `test_v32_werktage.py`, `test_v32_naechster_schritt.py`,
      `test_v32_suche.py`; angepasste Alt-Tests (Leads-VOT-Tabelle,
      Ablehnungsgründe-Liste, Startseiten-Kacheln, Überfällig-Banner) mit
      Begründung je Test. `pytest tests -q` komplett grün, Wächter-AST-Test v27
      grün, Token-Wächter v30 grün (keine neuen Hex-Werte).
- [x] **Screenshots** hell und dunkel, Handy (390 × 844) und Desktop, nach
      `docs/design-v32/` (Mein Tag mit allen vier Blöcken, Anruf-Karte mit
      aufgeklapptem Dialog, Heiße Kunden, Suche mit Vorschlägen, Vorgangsakte
      mit Verfolgungs-Chip, Angebotsliste mit Filter), nur Demo-Daten, keine
      EK/DB im Bild.
- [x] **Rollout-Vorbereitung** nach Grundregel – **einmal für v31 + v32 am Ende
      des Durchlaufs**: Server-DB-Kopie nach diagnose\,
      migrate.py zweimal (zweiter Lauf ohne Änderungen; neue Spalten
      `vorgaenge.verfolgung_status`, `vorgaenge.wiedervorlage_art`,
      `ablehnungsgruende.freitext_pflicht`, Parameter `nachfass_werktage`/
      `nachfass_werktage_mfh`, Gründe-Migration, Indizes),
      `scripts/vot_abgleich.py` (Bericht), `scripts/voll_crawl.py` für
      admin/innendienst/aussendienst/montage, `tests/abnahme.py` grün,
      `scripts\smoke.bat`; **(AT-Chat)** Lasttest Profil `normal` mit
      Lead-Nutzern und den Routen „Mein Tag“/Suche im AD-Profil (siehe
      Einfügung – nötig wegen der Freischaltung des Lead-Moduls in v31),
      Ergebnis in der Gesamtübersicht.
- [x] **Doku:** CLAUDE.md Abschnitt „Neu in v32 – Vertriebler-Ansicht Mein Tag,
      automatische Wiedervorlage, Nächster Schritt, Bestellung angekündigt,
      allgemeine Suche (abgestimmt 13.10.2026)“ nach „Neu in v31“,
      Zuordnungstabelle `| v32 | PLAN_V19.md | 161–165 |`, Titelzeile auf
      „(v32)“; in v1/v10/v15-Nachtrag die überholten Sätze (Leads-VOT-Tabelle,
      Überfällig-Banner, ID-Dialog-Gründe) als *überholt – siehe v32*
      markieren; `docs/design-system.md` (Makro `verfolgung_chip`, Karten-
      liste mobil); `docs/nach-dem-update-v32.md` (Außendienst: Mein Tag auf
      dem Handy, Anrufe aus „Fällig heute“, drei Ergebnis-Knöpfe, Suche;
      Innendienst: Kachel „Bestellung angekündigt“, Gründe-Liste prüfen,
      Filter Verfolgungsstatus; Admin: `vot_abgleich.py`-Bericht lesen);
      `docs/updates.md` ergänzen; `config.VERSION = "v32"`.
- [x] Gesamtübersicht am Ende: erledigte Phasen, Testergebnisse (Gesamtzahl),
      angepasste Alt-Tests mit Begründung, Bericht des VOT-Abgleichs,
      Messwert der Suche, Liste aller [ANNAHME]-Stellen, Rückfragen gebündelt.
      **Ein gemeinsamer Commit für v31 + v32** am Ende des Durchlaufs:
      „v31 + v32: Lead-Management V5 (PLAN_LEAD_V5, Phasen 153-160) + Mein Tag
      mobil, automatische Wiedervorlage, Nächster Schritt, Bestellung
      angekündigt, Suche (PLAN_V19, Phasen 161-165)“; **kein push vor
      Freigabe**.

## Kontrollwerte für die Abnahme

- AD „Rene“ meldet sich auf dem Handy an → landet auf „Mein Tag“: Termin
  heute 14:00 Uhr Müller, Krefeld mit Telefon- und Maps-Link und Knopf
  „Erfassung starten“; der Termin eines anderen AD erscheint nicht.
- Versand eines WP-Angebots am Fr 10.10.2026 → Wiedervorlage Mi 15.10.2026,
  Verantwortlicher AD, Chat-Eintrag „Wiedervorlage automatisch gesetzt“;
  ID-Kachel „fällig“ unverändert. Gleicher Versand an einen MFH-Kunden →
  Fr 17.10.2026.
- Am 15.10. steht der Vorgang bei Rene unter „Fällig heute“ mit Angebot
  „WP-Angebot vom 10.10.2026, Endbetrag 32.450,00 €“ (kein EK/DB), drei
  Aktivitäten aufklappbar, Notizfeld.
- „Abgelehnt“ + „zu teuer“ → beide Angebote des Vorgangs abgelehnt, Statistik
  zählt den Grund, monday-Status wie bisher.
- „Bestellung kommt“ → Chip „Bestellung angekündigt“, Ampel heiß, Vorgang
  unter „Heiße Kunden“, ID-Kachel „Bestellung angekündigt“ = 1.
- „Nochmal anrufen“ in 3 Werktagen am Fr 10.10. → Mi 15.10.; manuell
  20.10.2026 → 20.10. ohne Uhrzeit.
- Suche „Mül“ zeigt Müller beim Tippen; AD sieht nur eigene Kunden; Montage
  hat kein Suchfeld.
- `pytest tests -q` grün, Abnahmeskript grün, Voll-Crawl ohne Absturz,
  Smoke 8/8, migrate.py zweiter Lauf ohne Änderungen.

## Zulieferungen / bewusst offen

- [ANNAHME]-Bestätigungen durch Andreas/Claudia: spätere manuelle
  Wiedervorlage bleibt stehen; Bestellung angekündigt setzt Wiedervorlage
  +7 Werktage und eine ID-Glocke; alte Ablehnungsgründe werden deaktiviert
  statt gelöscht; Telefon-Endziffern in der Suche; Herkunfts-Badge
  monday/Tool; Rückgängig-Link 10 s; AD-Benutzer mit nur einer Rolle startet
  auf „Mein Tag“. **(AT-Chat, neu):** Innendienst/Admin behalten die Tabelle
  als Umschalter; „Extern erledigt“ zählt als Versand; Ablehnung läuft über
  `kern.lead_verloren`; Versionsnummer v32 und Phasen 161 bis 165 bestätigt.
- Lead-Management-Sicht „Meine Termine“ bleibt bestehen (nur Link); ob sie
  nach dem Live-Betrieb von v31 entfällt, entscheidet Andreas später.
- Nicht Teil dieses Plans: Startseiten-Umbau aus dem v30-Prototyp („Jetzt
  dran“, Icon-Leiste), Öffnungs-Tracking von Angebots-Mails (würde Lesebe-
  stätigungen oder Tracking-Pixel erfordern, nicht gewünscht), Routenplanung
  über mehrere Termine (vorhanden im Lead-Dashboard als Google-Maps-Link,
  könnte später in „Mein Tag“ übernommen werden).
- Demo-Daten für die Screenshots: mindestens zwei AD-Benutzer mit je drei
  Terminen und je einem versendeten Angebot (Generator des Lead-Managements
  nutzen).
