# PLAN_LEAD_V1.1 – Lead-Management: Übersicht, Anrufliste neu, Verknüpfung Quelle · Kampagne · Kanal (Phasen 87–89)

Voraussetzung: PLAN_LEAD_V1 (Lead-Management V1, CLAUDE.md v12) ist umgesetzt,
inklusive des Review-Durchgangs vom 27.09.2026 (LM-Unternavigation, SLA-Chips,
Icons). Dieser Plan setzt die Rückmeldung von Andreas vom 27.09.2026 um:

1. **„Wie erfolgt der Lead-Eingang über diverse Vertriebskanäle und
   Landingpages, wie wird die Verknüpfung hergestellt?"** → Phase 87 macht den
   Datenfluss Quelle → Kampagne → Kanal → Angebotsprofil lückenlos und
   selbsterklärend (neue Landingpages legen sich selbst an).
2. **„Die Ansicht ist noch unübersichtlich – ich muss sehen, wie viele neue
   Lead-Eingänge wir am Tag haben, über welche Vertriebskanäle, und ob wir einen
   Kunden schon dreimal angerufen und nicht erreicht haben."** → Phase 88 baut
   eine neue **Übersicht** (Modul-Einstieg), Phase 89 die **Anrufliste als
   gruppierte, zweizeilige Arbeitsliste** mit Versuchs-Anzeige.

**Design-Vorlage (verbindlich):** `docs/leadmanagement-prototyp.html` – eine
Datei mit beiden Seiten (Übersicht oben, Anrufliste unten), gebaut auf den
Tokens aus `docs/design-system.md`. Layout, Gruppierung, Chips, Farbregeln und
Texte von dort übernehmen; Zahlen darin sind Beispieldaten.

Leitplanken unverändert: Demo-Modus (`lead_freigabe_modus = admin`) bleibt,
monday-Sync und -Rückspielung werden nicht angefasst, keine Kundenmails im
Demo-Modus. Datenbank-Änderungen nur idempotent in migrate.py.

**Phasen-Zähler:** PLAN_PROJ_V3 belegt 84–86; dieser Plan belegt **87–89**.

**Start-Prompt für Claude Code (kopieren):**

> Lies `CLAUDE.md`, `LEADMANAGEMENT-KONZEPT.md`, `PLAN_LEAD_V1.1.md` und
> `docs/leadmanagement-prototyp.html` (Prototyp im Browser öffnen und
> Abschnitte vergleichen). Verschaffe dir einen Überblick über den Stand des
> Lead-Managements (app/leadmanagement.py, routers/leadmanagement.py,
> lead_parser.py, templates/leadmanagement/*, vorgaenge/_lead_kopf.html,
> Parametrierung Lead-Quellen/-Parser, Kanal-Report, Startportal). Setze dann
> Phase 87 um, danach 88 und 89. Datenbank-Änderungen nur idempotent in
> migrate.py. Nach jeder Phase: Zusammenfassung, betroffene Dateien,
> Testschritte als Admin. Rückfragen nur bei echten Widersprüchen – sonst im
> Sinne des Konzepts entscheiden und in `docs/leadmanagement-entscheidungen.md`
> notieren. Checkboxen abhaken, committen, nicht pushen.

---

## Phase 87 – Verknüpfung Quelle · Kampagne · Kanal (Datenfluss schärfen)

**Begriffe (so in Oberfläche und Doku verwenden):**

| Begriff | Bedeutung | Beispiel | Wo gepflegt |
|---|---|---|---|
| **Quelle** | Herkunft des Leads, Träger von Kosten je Lead, Typ-Farbe, Standard-Sparten, Score-Bonus, API-Key | `website`, `landingpage`, `portal_a`, `partner_enni`, `telefon`, `monday_deals` | Parametrierung → Lead-Quellen |
| **Kampagne** | konkrete Landingpage oder Aktion innerhalb einer Quelle, Träger von Budget/Zeitraum | `lp-waermepumpe-duisburg`, `lp-pv-speicher`, `herbst26-google` | Parametrierung → Kampagnen; **legt sich beim ersten Eingang selbst an** |
| **Kanal** | Vertriebskanal (Standard / Enni / SWD / Sparkasse DU) – steuert das Angebotsprofil (v9) und die AD-Zuweisung | `Enni` | an der Quelle (Vorbelegung) und am Kunden/Vorgang (übersteuerbar) |

Der Weg eines Landingpage-Leads: Formular sendet Mail an leads@friondo.de mit
Betreff `[LEAD] landingpage lp-waermepumpe-duisburg` (oder ruft `POST
/api/leads` mit `quelle` + `kampagne`) → Parser/API finden die **Quelle** über
den Key → **Kampagne** über den Namen (sonst Auto-Anlage) → der Vorgang trägt
`quelle_id`, `kampagne_id`, `utm_*` → der **Kanal der Quelle** wird an Kunde/
Vorgang gesetzt, falls dort noch keiner steht → das Angebotsprofil folgt dem
Kanal wie bisher. Ein neuer Kanal-Wert am Kunden (manuell) bleibt geschützt.

- [x] **Auto-Anlage unbekannter Quellen und Kampagnen** (Parser und API):
  Unbekannter Quellen-Key im Betreff/Feld `quelle` → Quelle wird angelegt
  (`typ = landingpage`, `aktiv = 1`, neue Spalte `auto_angelegt = 1`,
  `name = key`); unbekannter Kampagnen-Name → Kampagne angelegt (`quelle_id` =
  getroffene Quelle, `auto_angelegt = 1`, `von` = heute). Kein Lead bleibt mehr
  ohne Quelle: Fallback-Quelle `unbekannt` (Typ website) für Mails ohne Key,
  deren Regel keine Quelle trägt. Badge **„neu · automatisch angelegt"** in der
  Quellen-/Kampagnenpflege und am Lead (Anrufliste, Kopfblock: „Kampagne neu"),
  bis Admin die Zeile einmal speichert (`auto_angelegt = 0`). Glocke an Admin
  bei jeder Auto-Anlage („Neue Quelle/Kampagne aus Eingang: …").
- [x] **utm-Abgleich**: liefert der Betreff keine Kampagne, wird `utm_campaign`
  gegen `kampagnen.utm_campaign` (dann gegen `kampagnen.name`) geprüft; Treffer
  → `kampagne_id`. Ohne Treffer → Auto-Anlage mit Name = utm_campaign.
- [x] **Kanal an der Quelle als Dropdown** der bestehenden Kanalwerte (Werte aus
  der v9-Profil-Zuordnung + „Standard") statt Freitext; daneben read-only das
  zugeordnete Angebotsprofil („→ Profil Enni"). Beim Lead-Eingang (alle
  Eingangswege inkl. Import) Kanal an Kunde und Vorgang setzen, wenn dort leer;
  Feldschutz wie beim monday-Kanal („im Tool geändert schlägt Quelle").
  monday-Quellen behalten „Kanal am Kunden" (kein Wert, Anzeige grau).
- [x] **Quellen-Seite erweitern**: je Quelle Typ-Farbpunkt (Token `--q-<typ>`,
  Phase 88), Spalten „Eingänge 7 Tage / 30 Tage", „zuletzt", Badge neu;
  Kampagnen-Tabelle: Spalten „Eingänge 30 Tage", „Kosten je Lead" (= Budget ÷
  Eingänge im Kampagnenzeitraum, leer ohne Budget). Sortierung: aktive zuerst,
  dann nach Eingängen 30 Tage.
- [x] **Kanal-Report**: zusätzliche Tabelle je Kampagne (Leads, Termine,
  Aufträge, Budget, Kosten je Lead/Termin/Auftrag) unter der Quellen-Tabelle.
- [x] **Doku für die Agentur** `docs/formular-standard-agentur.md`: Betreff-
  Format, Feldliste (`Feld: Wert`), Pflichtfelder, Sparten-Schreibweisen,
  utm-Felder als versteckte Formularfelder, je Landingpage ein eigener
  Kampagnen-Slug (`lp-<thema>-<ort>`), Beispielmail, Hinweis auf Testadresse
  im Demo-Modus, Alternativ-Weg API (Verweis auf docs/leads-api.md).
- [x] Test: Parser-Test mit unbekanntem Key `lp-test-neu` → Quelle/Kampagne
  entstehen mit Badge; zweiter Eingang hängt an derselben Kampagne; API-Aufruf
  mit `utm_campaign` ohne `kampagne` → Zuordnung; Quelle mit Kanal Enni → Lead
  trägt Kanal Enni, Angebotsprofil Enni greift (nur prüfen, im Demo kein
  Angebot); manueller Kanal am Kunden bleibt bei weiterem Eingang erhalten.

## Phase 88 – Übersicht (neuer Modul-Einstieg) und Startportal-Kacheln

Vorlage: Abschnitt „Übersicht" im Prototyp.

- [ ] **Quellen-Typ-Farben als Tokens** in `style.css` (Werte aus dem Prototyp,
  mit dem Paletten-Validator geprüft): `--q-website #2a78d6`,
  `--q-landingpage #eb6834`, `--q-portal #1baf7a`, `--q-partner #eda100`,
  `--q-telefon #e87ba4` (auch empfehlung/bestand), `--q-monday #a5afbb`
  (bewusst grau = Bestand, kein Fokus). Feste Reihenfolge überall: Website ·
  Landingpage · Portal · Partner · Telefon/Empfehlung/Bestand · monday. Jede
  farbige Darstellung hat Legende **und** Zahl (Farbe trägt nie allein).
  Neue Makros in `_komponenten.html`: `quelle_badge(quelle)` (Punkt in
  Typ-Farbe + Name), `kanal_badge(kanal)` (violett, nur wenn ≠ Standard),
  `versuche_punkte(vorgang)` (Phase 89).
- [ ] **Route `/lead-management/uebersicht`**, in `lm_nav` an erster Stelle.
  Modul-Einstieg (Portal-Karte, Hauptmenü): Übersicht für Admin/Innendienst,
  Anrufliste für Benutzer mit Hauptrolle Leadmanagement (Parameter
  `lm_startseite = uebersicht | anrufliste`, Standard wie beschrieben).
  Die bisherige Cockpit-Seite geht in der Übersicht auf: ihre Blöcke
  (Teamtabellen heute/Woche, je AD, Termin-Rückmeldung offen, SLA-rot-Liste)
  stehen unten als aufklappbare Abschnitte; `/lead-management/cockpit` leitet
  weiter, Nav-Eintrag „Cockpit" entfällt.
- [ ] **Zeitbezug**: Kopfzeile mit Datum/Stand; Umschalter „Woche | 30 Tage"
  wirkt nur auf die Tabelle (Spalte „Zeitraum"); die Tageskacheln bleiben.
- [ ] **KPI-Kacheln** (sechs, klickbar → Anrufliste mit Filter):
  *Eingänge heute* (Untertitel „Ø 10 Arbeitstage: x · ▲/▼ %") · *Eingänge 7
  Tage* (Vorwoche + %) · *SLA rot jetzt* · *Jetzt dran* (fällige Rückrufe +
  Wiedervorlagen + SLA gelb/rot) · *≥ 3 Versuche offen* (Untertitel „davon n
  mit 4+") · *VOT-Termine heute* (Untertitel je AD). „Posteingang unklar" nur
  als siebte Kachel, wenn > 0.
- [ ] **Eingänge je Tag** (letzte 14 Kalendertage inkl. heute): gestapelte
  CSS-Balken je Tag nach Quellen-Typ (Technik wie `ae-balken`, keine
  Bibliothek), Segmentreihenfolge fix, 2 px Abstand zwischen Segmenten,
  Tagessumme über dem Balken, heute fett, Wochentag + Datum an der Achse,
  Legende darunter, Hover-Titel je Segment („Landingpages: 5"). Klick auf einen
  Tag → Anrufliste `?eingang_von=<Tag>&eingang_bis=<Tag>`.
- [ ] **Kontaktstatus der offenen Leads**: horizontale Balken „Noch kein Versuch
  / 1 / 2 / 3 / 4+ Versuche" mit Anzahl (offene Leads = Phasen neu,
  in_kontaktierung, qualifiziert ohne Termin, zurueckgestellt fällig);
  3 = orange, 4+ = rot (Status-Tokens); Klick → Anrufliste `?versuche=3`
  bzw. `?versuche_min=4`. Darunter Hinweiszeile mit der Kaskade aus der
  Steuerdatei.
- [ ] **Erstkontakt heute** (drei Mini-Kacheln): Median Minuten bis 1. Versuch
  (Arbeitsminuten, wie Statistik), Anteil im SLA, „heute erreicht x / y".
- [ ] **Tabelle „Eingänge je Quelle und Kanal"**: Gruppen nach Quellen-Typ
  (Zeile mit Farbpunkt), je Quelle: Kanal (Badge), heute, 7 Tage, 30 Tage
  (bzw. gewählter Zeitraum), **erreicht %** und **terminiert %** (Kohorte: von
  den Eingängen des Zeitraums haben x % `erreicht_am` bzw. `terminiert_am`;
  Mini-Balken + Zahl), **≥ 3 Versuche** (offene Leads der Quelle mit
  `versuch_nr ≥ 3`), Kosten je Lead (aus Quelle; Kampagnen-CPL als Tooltip),
  Summenzeile. Landingpages: eine Zeile je **Kampagne** unter der Quelle
  `landingpage` (Kampagne = Landingpage); auto-angelegte mit Badge „neu –
  bitte zuordnen". Klick auf eine Zeile → Anrufliste mit Quellen-/Kampagnen-
  Filter. Demo-Leads im Demo-Modus enthalten (Kennzeichen im Kopf „inkl. Demo").
- [ ] **Startportal-Karte Lead-Management** (nur bei Modul-Sichtbarkeit): Kacheln
  neu = *Eingänge heute (Ø 10 AT)* · *SLA rot* · *Jetzt dran* · *≥ 3 Versuche
  offen* · *Termine heute*; „Posteingang unklar" ersetzt die letzte Kachel,
  wenn > 0. Klick auf die Karte → `lm_startseite`.
- [ ] **Statistik → Leads**: neue Tabelle „Eingänge je Woche × Quellen-Typ"
  (letzte 12 Wochen) mit CSV-Export – dieselben Zähldefinitionen wie die
  Übersicht (eine Funktion `eingaenge_zaehlen(session, von, bis, gruppierung)`
  für Übersicht, Statistik, Kanal-Report und Portal-Kacheln – keine zweite
  Zählweise).
- [ ] Test: Demo-Daten erzeugen, Zahlen der Kacheln = Summen der Tabelle =
  Balkenhöhen; Klicks führen zu korrekt gefilterten Anruflisten; Übersicht
  lädt < 1 s bei 500 Vorgängen; als Innendienst weiterhin 404.

## Phase 89 – Anrufliste als gruppierte Arbeitsliste

Vorlage: Abschnitt „Anrufliste" im Prototyp. Die Route, die Ergebnis-Buttons,
die Dialoge, das Seitenpanel (einbett=1) und die Tasten 1–7 bleiben – nur
Filterleiste, Sortierung/Gruppierung und Zeilenaufbau ändern sich.

- [ ] **Schnellfilter-Chips** mit Zählern statt Dropdown-Leiste (Dropdowns
  Quelle/Sparte/Klasse und Suche bleiben rechts daneben): *Arbeitsliste* ·
  *Heute eingegangen* · *SLA rot* · *≥ 3 Versuche* · *Rückruf heute* · *Ohne
  Leadmanager*. URL-Parameter (auch von der Übersicht genutzt): `eingang_von`,
  `eingang_bis`, `sla=rot`, `versuche=<n>`, `versuche_min=<n>`, `rueckruf=heute`,
  `frei=1`, `quelle_id`, `kampagne_id`, `quelle_typ`. Filter „Quelle" bietet
  Typ-Gruppen (Website / Landingpages / Portale / Partner / Telefon / monday)
  und einzelne Quellen.
- [ ] **Gruppen** (feste Reihenfolge, Kopfzeile mit Zähler und Erklärtext, sticky):
  1. **Jetzt dran** – SLA gelb/rot ohne ersten Versuch, fällige Rückrufwünsche,
     fällige `naechste_aktion_am` ≤ jetzt; Reihenfolge: SLA rot → Rückruf-
     Uhrzeit → SLA gelb.
  2. **Weiter versuchen** – In Kontaktierung mit fälliger Kaskade, Nummer
     prüfen; `versuch_nr` absteigend (3+ oben), dann Fälligkeit.
  3. **Neu heute** – heute eingegangen, SLA grün, noch kein Versuch; nach
     Score-Klasse, dann Eingang.
  4. **Wiedervorlagen fällig** – zurückgestellte Leads mit erreichtem Datum.
  5. **Sonstige offene** – Rest der Arbeitsliste (nicht fällig), eingeklappt
     mit Zähler; aufklappbar.
  Ist ein Filter-Chip außer „Arbeitsliste" aktiv, bleiben die Gruppen, leere
  Gruppen werden ausgeblendet.
- [ ] **Zeile zweizeilig** (Grid wie Prototyp, linker 4-px-Farbbalken: rot bei
  SLA rot, orange bei SLA gelb oder `versuch_nr ≥ 3`):
  - **Spalte Versuche**: Makro `versuche_punkte(vorgang)` – fünf Punkte,
    gefüllt = `versuch_nr` (grau bei 1–2, orange bei 3, rot ab 4; mehr als 5
    Versuche = fünf rote Punkte + „7×"); darunter Label „neu" (blau) bzw. „n×".
    Dasselbe Makro im Lead-Kopfblock der Vorgangsakte.
  - **Zeile 1**: Name (fett, Panel-Link) · Ort (PLZ) · Sparten-Chips
    `.chip.chip-wp/-pv/-kl/-wb` · `quelle_badge` · `kanal_badge` (nur ≠
    Standard) · Flags als ⚑ in Orange: „frei", „Nummer prüfen" · Badges
    „Wiederkehrer", „Demo", „Kampagne neu". Keine weiteren Badges in Zeile 1.
  - **Zeile 2 – Kontaktstatus in einem Satz**, Regeln:
    * ohne Versuch: „Eingang vor <Dauer> – noch nicht angerufen" (rot, wenn
      SLA rot) · „Wunschzeit: …" · bis zu zwei Stichworte aus Anfragetext/
      Qualifizierung (Heizung + Baujahr, Zeitrahmen), sonst die ersten 60
      Zeichen der Nachricht in Anführungszeichen;
    * mit Versuchen: „<n>× nicht erreicht" (orange ab 3, rot ab 4) · „zuletzt
      <Wochentag> <Datum> <Uhrzeit> (<Ergebnis>)" · „nächster Versuch: <Datum
      oder ‚heute HH:MM'>" – beim letzten Kaskadenschritt zusätzlich rot
      „letzter Versuch der Kaskade – danach ‚Nicht erreicht' + Nurture-Mail";
    * Rückruf gewünscht: blau „Rückruf gewünscht: <Datum/Uhrzeit>";
    * zurückgestellt/fällig: „zurückgestellt am <Datum> (‚<Grund>') · heute
      fällig"; monday-Lead: grauer Zusatz „Terminierung in monday – hier nur
      Verfolgung".
  - **Spalten rechts**: SLA-Chip (wie bisher) · Klasse + Punkte · Telefon
    (`tel:`-Link) · **Aktionen**: `✓ Erreicht` (grün, primär) · `Nicht erreicht`
    · `Mailbox` · `Rückruf` · `⋯`-Menü (Besetzt, Falsche Nummer, Kein
    Interesse, Zurückstellen, Reaktivieren bei Seitenzuständen). Tasten 1–7
    unverändert (3 = Besetzt, 6 = Falsche Nummer, 7 = Kein Interesse über das
    Menü).
- [ ] **Kopfzeile**: „Anrufliste · Meine + freie Leads · <n> offen", Umschalter
  „Alle Leads", Button „+ Neuer Lead". Hinweisbanner „x Leads ohne
  Leadmanager" entfällt (Chip „Ohne Leadmanager" mit Zähler übernimmt).
- [ ] **Legende** am Listenende (Punkte, Farbbalken, Quelle/Kanal, Tasten).
- [ ] **Mobil** (< 900 px): Zeile bricht auf zwei Reihen um (Prototyp-CSS),
  Aktionen in einer Reihe darunter.
- [ ] **Lead-Kopfblock der Vorgangsakte**: Zeile „Kontaktstatus" mit
  `versuche_punkte` + demselben Satz wie Zeile 2; Quelle/Kanal/Kampagne mit den
  neuen Badges; Badge „Kampagne neu".
- [ ] **Docs**: `docs/leadmanagement.md` Abschnitte 1, 2 und 6 anpassen
  (Übersicht, Anrufliste neu, Quelle/Kampagne/Kanal); `docs/leadmanagement-
  entscheidungen.md` fortschreiben.
- [ ] **CLAUDE.md**: Kopf auf die nächste freie Versionsnummer (höchste + 1);
  Abschnitt **„Neu in v<NN> – Lead-Management V1.1 (abgestimmt 27.09.2026)"**
  anhängen, wörtlich:

  > - **Quelle · Kampagne · Kanal:** Quelle = Herkunft (Kosten, Typ-Farbe,
  >   API-Key), Kampagne = Landingpage/Aktion (Budget), Kanal = Vertriebskanal
  >   (Dropdown an der Quelle, wird beim Eingang an Kunde/Vorgang gesetzt, falls
  >   leer; manuell gesetzter Kanal bleibt). Unbekannte Quellen-Keys und
  >   Kampagnen aus Betreff `[LEAD] <quelle> <kampagne>`, API oder utm_campaign
  >   legen sich selbst an (Badge „neu · automatisch angelegt", Glocke an Admin);
  >   Fallback-Quelle `unbekannt`. Quellen-/Kampagnenpflege zeigt Eingänge 7/30
  >   Tage und Kosten je Lead; Kanal-Report zusätzlich je Kampagne;
  >   `docs/formular-standard-agentur.md`.
  > - **Übersicht** `/lead-management/uebersicht` als Modul-Einstieg
  >   (`lm_startseite`): Kacheln Eingänge heute (Ø 10 AT) / 7 Tage / SLA rot /
  >   Jetzt dran / ≥ 3 Versuche offen / Termine heute; Eingänge je Tag (14 Tage,
  >   gestapelt nach Quellen-Typ, Tokens `--q-*`, feste Reihenfolge, Legende);
  >   Kontaktstatus offener Leads nach Versuchen; Erstkontakt heute; Tabelle
  >   Quelle × Kanal × Zeitraum mit erreicht-/terminiert-Quote (Kohorte),
  >   ≥ 3 Versuche und Kosten je Lead; Cockpit darin aufgegangen. Eine
  >   Zählfunktion `eingaenge_zaehlen` für Übersicht, Statistik, Kanal-Report
  >   und Portal-Kacheln.
  > - **Anrufliste neu:** Schnellfilter-Chips mit Zählern (Heute eingegangen ·
  >   SLA rot · ≥ 3 Versuche · Rückruf heute · Ohne Leadmanager), Gruppen Jetzt
  >   dran · Weiter versuchen · Neu heute · Wiedervorlagen fällig · Sonstige;
  >   zweizeilige Zeile mit Versuchs-Punkten (`versuche_punkte`, grau 1–2 /
  >   orange 3 / rot 4+), Kontaktstatus-Satz („3× nicht erreicht · zuletzt … ·
  >   nächster Versuch …"), Quelle-/Kanal-Badges, ⚑-Flags, Aktionen Erreicht /
  >   Nicht erreicht / Mailbox / Rückruf / ⋯-Menü; Tasten 1–7 unverändert;
  >   derselbe Kontaktstatus im Lead-Kopfblock der Vorgangsakte.

- [ ] Test: 30 Demo-Leads mit 0–5 Versuchen; Gruppen und Reihenfolge stimmen;
  Chip-Zähler = Zeilen nach Klick; Tasten 1–7 wirken im Panel; Übersicht-Klicks
  landen in der richtigen Gruppe/Filter; Kopfblock zeigt dieselben Punkte wie
  die Liste; als Innendienst 404.

---

## Antworten auf offene Punkte aus dem Review vom 27.09. (soweit hier berührt)

- **Kohorten-Conversion**: Die Übersichtstabelle zählt erreicht/terminiert als
  Kohorte der Eingänge im Zeitraum (nicht als Ereignisse im Zeitraum) – der
  Trichter auf der Statistik-Seite bleibt vorerst ereignisbasiert; Umstellung
  der Statistik auf Kohorten folgt in V2.
- **monday-Leads ohne erstkontakt_am**: erscheinen in Übersicht und Anrufliste
  nur als Eingänge (Typ monday, grau) und – solange sie in monday terminiert
  werden – nicht in „Jetzt dran".
- Nicht Teil dieses Plans: monday-Import/Parallelbetrieb, SMS, Tourenplanung,
  Kosten-Monatsimport (PLAN_LEAD_V2).
