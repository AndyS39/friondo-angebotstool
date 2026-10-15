# Umsetzungsplan v20 – Outlook-Kalenderintegration je Mitarbeiter, Graph als Anwendung, zentraler Planungskalender, Rollen-Varianten, Service-Einsätze, Auto-Phase, Rabatt bei 0 % USt; Nachträge Claudia Castro 14.10.2026 (Mein Tag mobil, Tabellen-Layout, Lead-Nachträge, Nachfassen)

Voraussetzung: kein anderer Plan in Umsetzung (strangübergreifend). Stand
14.10.2026: v30 (PLAN_V18) ist ausgerollt; **v31 (PLAN_LEAD_V5, Phasen
153–160) und v32 (PLAN_V19, Phasen 161–165) laufen als gemeinsamer Durchlauf
bei Claude Code bzw. stehen vor dem Rollout. Dieser Plan kommt danach** und
setzt auf dem committeten v32-Stand auf (Objekte am Vorgang, Abwesenheiten/
Krankheit, Mein Tag, Verfolgungs-Chip, Lead-Modul für alle Rollen frei).
Vor der Übergabe fragt der Planungs-Chat erneut ab, ob v31/v32 committet und
gepusht sind. CLAUDE.md, `projektierung_logik_v1.xlsx` und
`leadmanagement_logik_v1.xlsx` sind Live-Master im Projektordner
`C:\Users\a.scheelen\Tools\Angebotstool` (Git-Arbeitskopie). ALLE PHASEN
DIESES PLANS IN EINEM DURCHLAUF UMSETZEN (Reihenfolge einhalten, jede Checkbox
nach Umsetzung und Test abhaken, am Ende Gesamtübersicht mit Testergebnissen
und offenen Punkten, fachliche Rückfragen gebündelt). **Ein gemeinsamer Commit
am Ende**, migrate.py idempotent, **nur additive Migrationen** (v32-Code muss
auf der v33-Datenbank weiterlaufen, Rückweg `rollback.bat --nur-code`).
**Kein git push vor Freigabe.**

CLAUDE-Abschnitt: **„Neu in v33“** [ANNAHME: v31 = PLAN_LEAD_V5, v32 =
PLAN_V19 – vor dem Bau gegen die Zuordnungstabelle prüfen, bei Abweichung die
nächste freie Nummer nehmen]. Phasen **166 bis 177** [ANNAHME: 161–165 gehören
zu PLAN_V19; bei Abweichung die nächsten freien Nummern nehmen und durchgängig
ersetzen]. Das Protokoll von Claudia Castro vom 14.10.2026
(PROTOKOLL-2026-10-14-Angebotstool.md) ist vollständig eingearbeitet: Teil A
(Mein Tag mobil, Tabellen-Layout) als Phasen 173/174, Teil B (Lead-Nachträge)
als Phase 175, Teil C (Nachfassen) als Phase 176 – es sind damit **keine
Nachträge mehr an PLAN_V19/PLAN_LEAD_V5 nötig**; die dort genannte „Phase 166“
und „PLAN_V20 ab 167“ sind durch diese Nummern ersetzt. Die v27-Regeln gelten (`def`-Routen, keine offene Datenbanksitzung
während Netz-I/O, Scheduler-Rahmen, Wächter-Test `tests/test_v27_sitzungen.py`
grün, Inventartabelle `docs/betrieb.md`), die v30-Regeln für Oberflächen
(Tokens Hell/Dunkel, Token-Wächter, `tojson | forceescape` in on*-Attributen,
Zurück-Leiste aus `base.html`).

Geltungsbereich: querschnittlich – Graph-Anbindung (`app/graph_versand.py`,
`app/kalender.py`, `app/outlook_kalender.py`, `app/mail_sync.py`,
`app/lead_mail.py`, `app/terminmail.py`, `app/sub_mail.py`), Benutzer- und
Rollenverwaltung (`app/auth.py`, `app/routers/benutzer.py`, `models.Benutzer`),
Projektierung (Terminarten, Phasenwechsel, Montage-Backend), Lead-Management
(VOT-Termine, Terminassistent – nur die Kalenderseite), Angebotstool (Rabatt,
Versand-Entwürfe, Schreibtransaktionen, Angebotsverfolgung/Nachfassen,
Tabellen-Layout, „Mein Tag“ mobil) und eine neue modulübergreifende Seite
`/kalender`. Cloover-Finanzierung ist **nicht** Teil dieses Plans (eigener
Plan nach Klärung mit Cloover). Konfiguratoren, Angebots-PDF (außer Rabatt-Block bei 0 %),
monday-Sync und monday-Rückspielung bleiben unberührt. **TAIFUN bleibt
unberührt:** Die bestehende Synchronisation Outlook → TAIFUN liest die
persönlichen Outlook-Kalender der Mitarbeiter; das Tool schreibt deshalb
Termine **in genau diese persönlichen Kalender** und fasst fremde Einträge
nie an.

## Entscheidungen (Chat Angebotstool, 14.10.2026, Andreas)

- **Ein zentraler Planungskalender** mit grundsätzlich allen Mitarbeitern;
  je Modul werden nur die relevanten gezeigt: **Projektierung = Monteure und
  Projektierer**, **Lead-Management = Außendienst (AD) und Handelsvertreter
  (HV)**. Admin und Innendienst sehen alle mit Filter.
- **Outlook-Schnittstelle je Mitarbeiter:** Jeder Tool-Termin steht im
  persönlichen Outlook-Kalender jedes eingeteilten Mitarbeiters, weil TAIFUN
  von dort synchronisiert (bestehende Schnittstelle, bleibt). Änderungen in
  Outlook (verschieben, löschen) fließen in das Tool zurück.
- **Zugriff als Anwendung** (Entscheidung 14.10.2026): Das Tool greift mit
  Anwendungsberechtigungen und einer Exchange-Zugriffsgruppe auf Postfächer
  und Kalender zu – keine persönliche „Mit Microsoft anmelden“-Verbindung
  mehr, keine Kalender-Freigaben je Person. Versand-Entwürfe liegen im
  Postfach **angebot@** (für alle Innendienstler sichtbar), nicht mehr im
  Postfach einer Person.
- **Rollen als Varianten einer Basisrolle**, pflegbar in der Parametrierung:
  sofort angelegt werden **Montage Heizung**, **Montage Elektro**, **Service
  Heizung**, **Service Elektro** (Basis Montage) und **Handelsvertreter**
  (Basis Außendienst). Rechte erben von der Basisrolle; die Kennzeichen
  (Gewerk, Service, Handelsvertreter) steuern Einsatzlisten, Kalender und
  Zuweisungen.
- **Service-Rollen = wie Montage, aber Service-Einsätze:** neue Terminart
  „Service“ mit eigenem Einsatzkalender, Kundendaten, Steckbrief, Fotos,
  Servicebericht und Outlook-Eintrag.
- **Projektierung: automatischer Phasenwechsel**, sobald alle Pflichtaufgaben
  einer Phase erledigt (oder „entfällt“) sind; manuelles Ändern bleibt in beide
  Richtungen möglich.
- **Rabatt bei 0 % USt** (PV-Angebote): Der hinterlegte Rabatt wird heute
  nicht abgezogen, weil die Rabattlogik am Bruttowert inkl. USt hängt. Künftig
  gilt der Rabatt bei jedem Steuersatz auf den Gesamtbetrag (bei 0 % ist
  brutto = netto).
- Mitgenommen aus v30 (offene Technikpunkte 21/22): allgemeine Lösung gegen
  „database is locked“ für schreibende Anfragen und `angebot_anlegen` innerhalb
  der Wiederholungslogik (Phase 172).

## Entscheidungen (Chat Angebotstool mit Claudia Castro, 14.10.2026 – Protokoll eingearbeitet)

- **„Mein Tag“ nur mobil** (Rolle Außendienst, unter 600 px); auf dem Desktop
  bleibt für alle Rollen die Tabelle „Leads VOT“ mit Gruppen und Spalten-
  sortierung; der v32-Umschalter „Karten | Tabelle“ entfällt. Farben aus den
  Design-v2-Tokens, nicht aus dem Entwurf. Kein Kennzahlen-Kopf. Priorität =
  Hot-Ampel. Nur „Erfassung starten“ als Aktion; ein Termin ist erledigt,
  sobald die Erfassung abgeschlossen ist. „Heiße Kunden“ geht im Abschnitt
  „Wiedervorlage“ auf (Chip „Hoch“); die ID-Kachel „Bestellung angekündigt“
  bleibt.
- **Lead-Board-Layout für alle Tabellen des Angebotstools** (Sticky-Filter,
  Spalten je Nutzer, Sortierung per Spaltenkopf), ohne Sammelaktionen.
- **Lead-Management:** Kanal-Regel um „Stadtwerke Düsseldorf“; Infotext zum
  AD entfällt vollständig; Sammelaktion „An Handelsvertreter verschieben“ mit
  Ziel „Simons Gruppe“ statt eines festen Mitglieds.
- **Nachfassen:** Inaktivitäts-Kennzeichen 14/20 Tage, Zähler der Telefon-
  versuche, Einwand-Chips, Nachfass-Mail durch den AD aus dem eigenen
  Postfach. Verworfen: „Gültig bis“, Öffnungs-Erkennung, automatische Mail-
  Sequenzen, Kanban auf dem Handy.

## Phase 166 – Graph als Anwendung (Fundament)

- [x] **Betriebsmodus:** `.env`-Schlüssel `GRAPH_CLIENT_SECRET` (Geheimnis
      aus Entra → Zertifikate & Geheimnisse; alternativ `GRAPH_ZERTIFIKAT_PFAD`
      für eine .pfx-Datei [ANNAHME: beide Wege, Secret reicht zum Start]).
      Parameter `graph_modus` = `anwendung` | `delegiert`; Startwert
      **automatisch**: `anwendung`, sobald das Geheimnis gesetzt ist und der
      Verbindungstest grün war, sonst `delegiert` (heutiger Weg bleibt als
      Rückfallebene vollständig erhalten, wird nicht ausgebaut).
- [x] **Token und Aufrufe:** `graph_versand._token()` liefert im Modus
      `anwendung` ein Client-Credentials-Token (MSAL ConfidentialClient, Scope
      `https://graph.microsoft.com/.default`, Cache im Prozess, Erneuerung vor
      Ablauf, Netzaufruf ohne offene Sitzung); alle Graph-Aufrufe arbeiten
      mit `/users/<postfach>/…` statt `/me/…` – Versand aus angebot@/termin@/
      projektierung@ (`sendMail` am Funktionspostfach, kein „Senden als“ mehr
      nötig), Abruf der Antworten aus angebot@ und termin@, Kalender der
      Mitarbeiter. Jeder Aufruf fällt bei HTTP 403 mit der Meldung „Postfach
      <x> ist nicht in der Zugriffsgruppe Friondo-Tool-Zugriff“ ins
      Fehlerprotokoll (einmal je Postfach und Stunde).
- [x] **Versand-Entwürfe im Funktionspostfach:** „Versand vorbereiten“ legt
      den Entwurf in `angebot@friondo.de` → Ordner Entwürfe an (Absender
      angebot@, Signatur des vorbereitenden ID-Benutzers wie v6, CC/BCC wie
      bisher); der Status „Versand vorbereitet“ und die Versand-Erkennung
      (Gesendete Elemente von angebot@) bleiben. Jeder Innendienstler sieht
      die Entwürfe in Outlook im eingeblendeten Postfach angebot@ und sendet
      von dort. Kombi-Versand ebenso. Lead-Mails (termin@) und Projekt-Mails
      (projektierung@) werden direkt gesendet wie heute.
- [x] **Versand-Seite (`/versand`)** wird zur **Verbindungs-Seite**: Modus,
      Mandant, letzte erfolgreiche Aufrufe je Postfach, Knopf „Verbindung
      testen“ (liest je Funktionspostfach einen Ordner und je einen
      Mitarbeiter-Kalender, Ergebnis je Postfach grün/rot mit Grund), Liste
      der Postfächer, die das Tool braucht (aus Benutzerverwaltung + Parameter)
      zum Abgleich mit der Zugriffsgruppe; im Modus `delegiert` weiter
      „Mit Microsoft anmelden“/„Abmelden“. Hinweis, dass eine Anmeldung einer
      Person im Modus `anwendung` nicht mehr nötig ist.
- [x] **Einrichtung dokumentieren** (`docs/graph-einrichtung.md` komplett neu
      gegliedert): (1) Entra: Anwendungsberechtigungen `Mail.Send`,
      `Mail.ReadWrite`, `Calendars.ReadWrite` (+ Administratorzustimmung),
      Geheimnis anlegen, Ablaufdatum in `/health` (`warn` 30 Tage vorher);
      (2) Exchange: mail-aktivierte Sicherheitsgruppe `friondo-tool-zugriff@`
      mit allen Postfächern, die das Tool anfasst (Funktionspostfächer +
      alle Mitarbeiter mit Terminen), `New-ApplicationAccessPolicy … 
      -AccessRight RestrictAccess`, `Test-ApplicationAccessPolicy`; (3) die
      heute (14.10.2026) gesetzten delegierten Freigaben (Skript mit
      `Add-MailboxFolderPermission`, Vollzugriff/Senden-als auf termin@) als
      Abschnitt „Übergangsweg delegiert“ – bleiben gültig, werden im Modus
      `anwendung` nicht mehr gebraucht; (4) Checkliste neuer Mitarbeiter:
      Postfach in die Gruppe, Benutzer im Tool mit E-Mail. Go-live-Checkliste:
      Punkt „Graph als Anwendung verbunden“ (grün = Verbindungstest grün und
      Geheimnis > 30 Tage gültig).
- [x] Tests `tests/test_v33_graph.py` (HTTP gemockt): Token-Flow, `/users/`-
      Pfade für alle Aufrufe, Entwurf landet in angebot@/Entwürfe mit Signatur
      des Vorbereiters, 403 → Fehlerprotokoll einmal je Stunde, Modus-
      Umschaltung, Verbindungstest-Ergebnisse, Wächter-AST grün.

## Phase 167 – Rollen als Varianten (Parametrierung → Rollen)

- [x] **Datenmodell:** Tabelle `rollen` (`key`, `name`, `basisrolle` ∈ admin |
      innendienst | aussendienst | projektierung | montage | leadmanagement,
      `gewerk` ∈ leer | heizung | elektro, `service` 0/1, `handelsvertreter`
      0/1, `aktiv`, `sortierung`, `system` 0/1). Migration legt die sechs
      Basisrollen als Systemzeilen an (nicht löschbar) und die fünf neuen
      Varianten: `montage_heizung` „Montage Heizung“ (montage, heizung),
      `montage_elektro` „Montage Elektro“ (montage, elektro),
      `service_heizung` „Service Heizung“ (montage, heizung, service),
      `service_elektro` „Service Elektro“ (montage, elektro, service),
      `handelsvertreter` „Handelsvertreter“ (aussendienst, handelsvertreter).
      `benutzer.rolle`/`rollen` nehmen Varianten-Keys auf; `Benutzer.
      basisrolle` (Property) und `hat_kennzeichen("service")` als einzige
      Prüfstellen – alle `rolle == "montage"`/`in ("admin","innendienst")`-
      Vergleiche im Code auf `basisrolle` umstellen (Liste der Stellen in der
      Gesamtübersicht), Pfadtabellen in `auth.py` über die Basisrolle.
- [x] **Handelsvertreter als Rolle:** Migration setzt bei allen AD-Profilen
      mit `terminiert_selbst = 1` die Rolle `handelsvertreter` (Hauptrolle
      aussendienst → handelsvertreter, Kennzeichen bleibt synchron);
      HV-Prüfungen in `lead_v2`, `lead_handelsvertreter`, `lead_termin` (v23/
      v29/v31) lesen künftig das Rollen-Kennzeichen (`terminiert_selbst` bleibt
      gespiegelt, damit v32-Code läuft). HV-Sicht, 303-Umleitung, HV-Gruppen,
      `hv_versandweg` unverändert.
- [x] **Montage Heizung/Elektro:** Teams tragen ein Gewerk (`teams.gewerk`
      heizung | elektro | leer, Parametrierung → Teams; Migration: Teams, die
      heute als Elektro-Team an Gewerken hängen, → elektro, übrige → heizung
      [ANNAHME]). Montage-Backend `/montage` zeigt einem Benutzer der
      Variante Montage Heizung die Einsätze der Terminarten Montage (WP) und
      Sub seines Teams, Montage Elektro die Elektro-Termine; Benutzer der
      Basisrolle montage weiter alles. Besetzung im Termin-Dialog schlägt
      Monteure passend zum Gewerk der Terminart vor (andere wählbar, grau).
- [x] **Parametrierung → Rollen** (Admin): Liste, Anlegen (Name, Basisrolle,
      Gewerk, Service, Handelsvertreter), Umbenennen, Deaktivieren (nur ohne
      aktive Benutzer), Systemrollen gesperrt; Benutzerverwaltung bietet im
      Rollen-Dropdown und bei den Zusatzrollen alle aktiven Rollen, Filter nach
      Rolle; CSV-Import (v27) akzeptiert die Keys. Login-Ziel je Basisrolle
      wie bisher (`auth`), Cookie-Dauer nach Basisrolle (mobil = montage/
      aussendienst).
- [x] Tests `tests/test_v33_rollen.py`: Varianten erben Pfadrechte der Basis
      (Montage Heizung erreicht `/montage`, nicht `/angebote`); HV-Migration;
      Montage-Backend filtert nach Gewerk; Rolle ohne Benutzer deaktivierbar,
      mit Benutzer nicht; Alt-Tests mit `rolle == "montage"` bleiben grün.

## Phase 168 – Service-Einsätze (Terminart „Service“)

- [x] **Terminart `service`** im Termin-Dialog der Projektierung (v28, ein
      Dialog): Gewerk Heizung | Elektro, Person(en) oder Team (Varianten
      Service Heizung/Elektro bzw. Service-Teams), Datum/Zeit im 15-Minuten-
      Takt, Dauer, Beschreibung, Anlass (Auswahl: Wartung · Störung · Nacharbeit
      · Sonstiges [ANNAHME]); planbar **am Vorgang** – auch ohne Projekt
      (Bestandskunde mit abgeschlossenem Projekt oder Bestandsimport) – über
      Vorgangsakte → Block „Termine“ → „Service-Einsatz planen“ (ID/Admin/
      Projektierung). Outlook-Eintrag je eingeteilter Person (Phase 170).
- [x] **Service-Backend:** `/montage` zeigt Benutzern der Service-Varianten
      ihre Service-Einsätze (chronologisch, Wochenkalender) mit Kundendaten,
      Ausführungsort (Objektadresse v31), Steckbrief, Galerie, Notizen-Chat
      (lesen), Buttons „Einsatz gestartet“/„Einsatz beendet“, Formular
      **Servicebericht** (Blatt „Formulare“ der `projektierung_logik_v1.xlsx`,
      Arbeitsanweisung: Formular `servicebericht` mit Feldern [ANNAHME, Andreas
      liest gegen]: `sb_anlass` (Auswahl wie oben), `sb_arbeiten` (Text,
      Pflicht), `sb_material` (Text), `sb_zeit_von`/`sb_zeit_bis` (Zeit),
      `sb_ergebnis` (Auswahl: behoben · Nacharbeit nötig · Ersatzteil
      bestellt), `sb_foto` (Galerie-Ordner „Service“), Unterschrift Kunde,
      Unterschrift Techniker) – PDF in die Galerie, Eintrag im Notizen-Chat.
- [x] Projektakte/Vorgangsakte zeigen Service-Einsätze im Block Termine mit
      Badge „Service“; Projektboard unverändert (Service hat keine Phase);
      Statistik Projektierung bekommt die Zahl der Service-Einsätze je Monat
      [ANNAHME].
- [x] Tests `tests/test_v33_service.py`: Service-Einsatz am Vorgang ohne
      Projekt; Service-Benutzer sieht nur Service-Einsätze seines Gewerks;
      Servicebericht-PDF in der Galerie; Montage-Benutzer sieht keinen Service.

## Phase 169 – Zentraler Planungskalender `/kalender`

- [x] **Seite** `/kalender` (Template `kalender/zentral.html`, JS
      `kalender_zentral.js`, Design v2): Wochenansicht Mo–Fr (Sa/So
      einblendbar), Tag und Monat als Umschalter, **eine Zeile je Mitarbeiter**
      (Zeitachse waagerecht, 15-Minuten-Raster; Monat als Tageskästchen),
      Mitarbeiter-Gruppen aufklappbar (Außendienst · Handelsvertreter ·
      Projektierung · Montage Heizung · Montage Elektro · Service Heizung ·
      Service Elektro · Innendienst). Vorbelegung nach Einstieg: aus der
      Projektierung (Menü/Board) → Monteure + Projektierer; aus dem
      Lead-Management (Icon-Leiste) → AD + HV; Admin/Innendienst → alle, mit
      Filter-Chips je Gruppe und Suche nach Name; Auswahl je Nutzer gemerkt
      (`benutzer_einstellungen`, Key `kalender_gruppen`). Parameter
      `kalender_tagesbeginn/-ende` (Standard 07:00–18:00).
- [x] **Einträge:** alle Tool-Termine der Person – VOT (`vot_termine` inkl.
      Vorab-Gespräche und Sperrzeiten v29), Projekt-Termine (Montage, Elektro,
      Sub, Feinplanung, Abnahme, Sonstiges – über Besetzung bzw. Person),
      Service (Phase 168), Abwesenheiten/Krankheit (v31) als graue Balken,
      **Outlook-Belegtzeiten** aus dem persönlichen Kalender (Phase 170,
      schraffiert, nur Zeit und „belegt“, kein Betreff fremder Einträge).
      Farbe je Terminart (Tokens), Kunde + Ort als Text, Klick öffnet den
      Termin-Dialog des jeweiligen Moduls (Lead-Termin, Projekt-Termin,
      Service), Drag verschiebt Tool-Termine (Rechte wie im Modul, Konflikt-
      warnung, Outlook-Update über Phase 170), Doppelklick auf freie Fläche =
      neuer Termin der zum Modul passenden Art.
- [x] **Einbindung:** Menü „Kalender“ für ID/Admin/Projektierung/
      Leadmanagement; Lead-Icon-Leiste → „Kalender“ zeigt `/kalender?gruppe=
      vertrieb`; Projektierung-Sicht „Kalender“ (v15, Team-Balken) bleibt,
      bekommt den Link „Mitarbeiter-Kalender“; der Terminkalender Woche je AD
      (v12) leitet auf `/kalender?gruppe=vertrieb&person=<id>` um [ANNAHME].
      Montage-/Service-Benutzer sehen `/kalender` nur für sich selbst und ihr
      Team (read-only, mobil in Tagesansicht).
- [x] **Leistung:** Daten nachgelagert per `GET /kalender/daten.json?von&bis&
      personen=` (eine Abfrage je Quelle, Outlook-Belegt aus dem Cache der
      Phase 170, nie Graph im Request), unter 1,5 s für 60 Personen × 1 Woche
      auf der DB-Kopie (Messung in die Gesamtübersicht).
- [x] Tests `tests/test_v33_kalender.py`: Vorbelegung je Einstieg, Gruppen-
      filter, alle sechs Terminarten + Abwesenheit sichtbar, Drag ändert den
      Tool-Termin und protokolliert, Rechte (Montage nur eigene), JSON-Zeit.

## Phase 170 – Outlook-Sync je Mitarbeiter (TAIFUN-kompatibel)

- [x] **Vorab-Abgleich mit TAIFUN** (Claude Code, nur lesend): im Kalender
      eines Monteurs mit laufendem TAIFUN-Abgleich (Andreas nennt den Namen)
      einen TAIFUN-Termin lesen und Betreff-Muster, Kategorie und Kennzeichen
      in `docs/outlook-sync.md` festhalten; daraus die Regel ableiten, ob
      Tool-Termine für TAIFUN sichtbar sein sollen (dann gleiches Muster) oder
      nicht (dann eigene Kategorie „Friondo-Tool“) – **Entscheidung Andreas
      vor Phase 170, Rückfrage im Durchlauf, bis dahin [ANNAHME]: sichtbar,
      Betreff „<Art>: <Kunde>, <PLZ Ort> (<Nummer>)“, Kategorie
      „Friondo-Tool“.** Das Tool fasst Einträge ohne sein Kennzeichen nie an.
- [x] **Schreiben:** jeder Tool-Termin erzeugt je eingeteilter Person ein
      Ereignis in deren persönlichem Kalender (`/users/<upn>/events`, Modus
      `anwendung`; im Modus `delegiert` wie heute über die Freigaben): VOT →
      AD (ersetzt `kalender.py`-Logik, Demo/Test weiter ins Testpostfach),
      Montage/Elektro/Sub/Service → jede Person der Besetzung (Team-Kalender
      der Teams nur zusätzlich, wenn `teams.outlook_kalender` gesetzt
      [ANNAHME: optional, nicht Pflicht]), Feinplanung/Abnahme/Sonstiges →
      Person, Abwesenheiten nicht (kommen aus Outlook). Kennzeichen im Ereignis
      (`singleValueExtendedProperties` `friondoTerminId` + Art + Modul), Body
      mit Kunde, Adresse, Link ins Tool; Betreff nach Regel oben. Tabelle
      `outlook_ereignisse` (termin_art, termin_id, benutzer_id, postfach,
      event_id, stand, letzte_aenderung) – additiv, ersetzt die verstreuten
      `outlook_event_id`-Felder nicht, sondern hängt sich daneben.
- [x] **Änderung/Absage/Besetzungswechsel:** Verschieben im Tool → alle
      Kopien aktualisiert; Person aus der Besetzung genommen → ihr Ereignis
      gelöscht; Absage/Storno → alle gelöscht; HV ohne Postfach → kein
      Ereignis, Hinweis in der Terminliste. Alle Netzaufrufe über den
      Scheduler-Lauf **`outlook-sync`** (60 s, Warteschlange `outlook_auftraege`
      mit Status offen/erledigt/fehler, 3 Versuche, Fehlerprotokoll) – kein
      Graph-Aufruf im Request; Anzeige „Outlook: ausstehend/ok/fehler“ am
      Termin.
- [x] **Rücklesen:** Lauf `outlook-ruecklesen` (300 s, `db.kurz()`): für jede
      Person mit Terminen in den nächsten 8 Wochen `calendarView` lesen; Tool-
      Ereignisse (Kennzeichen) mit verändertem Zeitraum → Tool-Termin
      nachziehen (bei mehreren Personen: erste Änderung gewinnt, übrige Kopien
      werden angeglichen, Verlauf „aus Outlook übernommen von <Name>“),
      gelöschte Tool-Ereignisse → Termin im Tool auf „in Outlook gelöscht“ mit
      Glocke an Projektierung/Leadmanager (kein stilles Löschen); fremde
      Einträge → nur als Belegtzeit in Cache `outlook_belegt` (person, von,
      bis, stand) für Phase 169 und den Terminassistenten (ersetzt
      `kalender.frei_belegt`-Direktaufrufe im Request).
- [x] **Zugriffsgruppe pflegen:** Verbindungs-Seite (Phase 166) listet alle
      Personen mit Terminen, deren Postfach beim letzten Lauf 403 lieferte –
      „nicht in der Zugriffsgruppe“ – mit Kopierliste für die IT.
- [x] Tests `tests/test_v33_outlook.py` (Graph gemockt): Montagetermin mit
      zwei Monteuren → zwei Ereignisse mit Kennzeichen; Monteur getauscht →
      ein Ereignis gelöscht, eines neu; Verschieben in Outlook → Termin im Tool
      verschoben, zweite Kopie angeglichen; Löschen in Outlook → Status +
      Glocke; fremder Termin → nur Belegtzeit, nie verändert; VOT-Demo →
      Testpostfach; Sitzungsdisziplin (Wächter-AST).

## Phase 171 – Projektierung: automatischer Phasenwechsel

- [x] Parameter `phase_auto` (Projektierung-Einstellungen → Board & Wächter,
      Standard **an**) und je Gewerk ein Häkchen „automatisch weiterschalten“
      (Standard an, in der Projektakte). Nach jeder Erledigung einer Aufgabe,
      eines Formulars, einer Besetzung oder eines Steckbrief-Nachzugs prüft
      `projektierung.auto_weiterschalten(session, gewerk)`: Sind alle
      **Pflichtaufgaben** der aktuellen Phase erledigt oder „entfällt“ (optionale
      Aufgaben zählen nicht), wechselt das Gewerk über `phase_wechseln` in die
      **nächste** Phase mit Begründung „automatisch – alle Pflichtaufgaben
      erledigt“ (Verlauf, Aktivität, Glocke an den Projektverantwortlichen
      [ANNAHME]). Nur vorwärts, nur eine Phase je Auslöser, nie nach
      `abgeschlossen` (bleibt „Rechnung freigeben“) und nie, wenn der Wächter
      im Modus `sperren` offene Punkte meldet oder die Zielphase eine
      Bedingung hat, die fehlt (z. B. Montage ohne bestätigten Termin).
      Manuelles Ändern (Board-Drag, Dialog, zurück mit Begründung) bleibt wie
      v28; ein manueller Rückschritt setzt das Gewerk-Häkchen für diese Phase
      aus, damit es nicht sofort wieder vorspringt (Hinweis im Dialog).
- [x] Tests `tests/test_v33_auto_phase.py`: letzte Pflichtaufgabe erledigt →
      nächste Phase, Verlauf; optionale offen → trotzdem Wechsel; Modus
      `sperren` mit offenem Punkt → kein Wechsel; `phase_auto = aus` → kein
      Wechsel; Rückschritt → kein erneutes Vorspringen; Abnahme → Freigabe nur
      mit allen Abnahme-Pflichtaufgaben, Freigabe → abgeschlossen nie
      automatisch.

## Phase 172 – Angebotstool: Rabatt bei 0 % USt, Schreibtransaktionen

- [x] **Rabatt bei 0 %:** Reproduzieren mit einem PV-Angebot (0 % USt,
      Rabatt 5 % und Rabatt 500 €) im Editor, PDF, Angebotsliste,
      Mail-Platzhalter {endbetrag}, monday-Deal-Wert, Statistik, DB. Ursache
      benennen (Erwartung: der Rabatt-Block hängt am 19 %-Summenblock des PDF
      bzw. an einer USt-Bedingung in Editor/Route) und beheben: Der Rabatt
      gilt bei jedem Steuersatz auf den Gesamtbetrag nach USt (bei 0 % =
      Netto), Darstellung „Gesamt-Betrag → − Rabatt → = Endbetrag“ ohne Zusatz
      „(brutto)“ bei 0 %; DB sinkt um Rabatt ÷ (1 + USt-Satz), also bei 0 %
      um den vollen Rabatt; Positionsrabatte unverändert. Kontrollwert:
      PV-Angebot Netto 20.000,00 €, 0 % USt, Rabatt 5 % → Endbetrag
      19.000,00 €, DB −1.000,00 €; Rabatt 500 € → 19.500,00 €. Test
      `tests/test_v33_rabatt.py`; bestehende PV-/KL-Kontrollwerte unverändert.
- [x] **Schreibende Anfragen mit `BEGIN IMMEDIATE`** (v30-Nachtrag 21):
      Sitzungen, die schreiben, eröffnen die Transaktion sofort als
      Schreibtransaktion (SQLAlchemy-Event `begin` → `BEGIN IMMEDIATE` für
      Routen mit `POST/PUT/DELETE` und für Scheduler-Blöcke), damit WAL-
      Schreiber nicht mehr an BUSY_SNAPSHOT scheitern; Leseanfragen
      unverändert. `angebot_anlegen` mit `commit=False` innerhalb von
      `_speichern` (v30-Nachtrag 22). Messung mit `tests/test_pool_hotfix.py`
      (20 parallele Terminvorschläge ohne „database is locked“) und Lasttest
      Profil `schreibsturm`; Ergebnis in die Gesamtübersicht.

## Phase 173 – „Mein Tag“ mobil nach Design-Entwurf, Leads VOT Desktop, Seite „Wiedervorlage“ (Nachtrag Claudia Castro 14.10.2026 zu v32)

Voraussetzung ist der v32-Stand (PLAN_V19 Phasen 161–163). Diese Phase
**ersetzt** dort die Kartenbeschreibung, den Umschalter „Karten | Tabelle“
und den Block „Heiße Kunden“. Der Design-Entwurf „Außendienst App“ (zwei
Screens „Mein Tag“ und „Wiedervorlage“, claude.ai-Artefakt vom 14.10.2026,
Link unter Zulieferungen) gibt Aufbau, Abstände und Verhalten vor – **nicht
die Farben**: Farben kommen aus den Design-v2-Tokens (v30), die Entwurfs-
farben (dunkles Grün, Gelb, Anthrazit) werden nicht übernommen.

- [x] **„Mein Tag“ nur mobil:** die Kartenansicht gilt ausschließlich für die
      Rolle Außendienst unter 600 px Breite (CSS-Media-Query plus serverseitig
      derselbe Datenbestand); ab 600 px und für alle anderen Rollen die Tabelle
      „Leads VOT“ aus Phase 174. Ein in v32 gebauter Umschalter „Karten |
      Tabelle“ entfällt; `docs/design-v32/leads-vot-vorher.png` als Vergleich
      der ID-Ansicht entfällt, stattdessen Screenshots „Mein Tag“ mobil bei
      390 px hell/dunkel nach `docs/design-v33/`.
- [x] **Aufbau mobil, eine Spalte von oben nach unten:** (1) Kopf „Mittwoch,
      14. Oktober“ (Wochentag ausgeschrieben, Tag, Monat ausgeschrieben),
      darunter Titel „Mein Tag“, rechts ein runder Kreis mit den Initialen des
      AD (zwei Buchstaben aus Vor- und Nachname); **keine Kennzahlen** im Kopf.
      (2) Karte **„Als Nächstes“**: der nächste noch nicht erledigte Termin des
      Tages – Hinweis „in 25 Min“ (Minuten bis Beginn; nach Beginn „jetzt“;
      liegt der nächste Termin erst morgen, steht die Karte nicht da), Uhrzeit
      „09:30“ groß mit „bis 10:30“ darunter, Kundenname, Zeile Sparte und
      Termintyp („Wärmepumpe, Erstberatung“ aus Sparten-Badges und Typ in
      `vot_termine`), Anschrift (Objektadresse v31) mit Karten-Link, Knopf
      „Route starten“ (Google-Maps-Link aus v32 mit der Anschrift als Ziel),
      Telefon als `tel:`-Link. (3) Liste **„Heute“** mit Zähler „5 Termine“: je
      Termin Uhrzeit links, ein Punkt auf einer senkrechten Linie (erledigt =
      Punkt in der Erfolgsfarbe, nächster Termin = Hinweisfarbe, übrige leer),
      Kundenname, Sparte/Termintyp, Ort; erledigte Termine in gedämpfter
      Textfarbe; Hauptaktion rechts „Erfassung starten“ (bei erledigten kein
      Knopf, stattdessen Link zur Erfassung). (4) Abschnitt **„Wiedervorlage“**
      (siehe nächste Checkbox). (5) Abschnitt **„Kommende Tage“**: Termine der
      nächsten 14 Tage [ANNAHME: Zeitraum], gruppiert je Tag mit Datumskachel
      links (Wochentag zweibuchstabig über der Tageszahl), Überschrift
      „Donnerstag, 15. Oktober“ und Zähler „2 Termine“; je Termin Uhrzeit,
      Kundenname, Sparte/Typ · Ort. (6) **Untere feste Leiste** mit vier
      Einträgen: „Mein Tag“ (diese Seite), „Kalender“ (= Meine Termine aus dem
      Lead-Management), „Wiedervorlage“ (= Seite unten), „Kunden“ (= allgemeine
      Suche aus v32 Phase 164); aktiver Eintrag hervorgehoben, Safe-Area des
      Geräts berücksichtigt. Keine Kennzahlen, keine Sammelaktionen, keine
      Kanban-Pipeline.
- [x] **Abschnitt „Wiedervorlage“** (ersetzt den v32-Block „Fällig heute“ und
      den Block „Heiße Kunden“): Untertitel „Vorgänge, die auf Rückmeldung
      warten“ mit Zähler; Chips „Alle · Hoch · Mittel · Niedrig“ jeweils mit
      Anzahl (gewählter Chip gefüllt), daneben Segment-Umschalter „Sortieren:
      Priorität · Name · Datum“ (gewählter Eintrag trägt ↓ bzw. ↑, nochmaliges
      Tippen dreht die Richtung). Darunter höchstens vier Karten je Vorgang:
      Kreis mit Initialen des Kunden, Kundenname, Sparte(n), Badge „Hoch“/
      „Mittel“/„Niedrig“ in den Ampel-Farben, Zeile „Letzter Kontakt TT.MM. ·
      seit X Tagen“ (X ab 14 in der Warnfarbe, sonst gedämpft; „heute“ bzw.
      „seit gestern“ statt Zahl). Tippen öffnet die Anruf-Karte aus v32
      (Dialog „Nächster Schritt“, Notizfeld, letzte Aktivitäten). Unten Link
      „Alle N Wiedervorlagen anzeigen“. **Priorität = Hot-Ampel** (Hoch = heiß,
      Mittel = warm, Niedrig = kalt; keine neue Priorität, keine neue Spalte).
      Datenbasis: alle fälligen und überfälligen Angebots-Wiedervorlagen des AD
      (`vorgaenge.wiedervorlage_am` ≤ heute, Verantwortlicher = AD) plus alle
      eigenen Vorgänge mit Hot-Ampel heiß oder Verfolgungsstatus
      `bestellung_angekuendigt`; „Letzter Kontakt“ = Datum des letzten Eintrags
      im Notizen-Chat des Vorgangs [ANNAHME: Einträge aller Herkünfte, auch
      System]. Die Startseiten-Kachel „Bestellung angekündigt“ für Innendienst/
      Admin (v32) bleibt.
- [x] **Seite „Wiedervorlage“ mobil:** Route [ANNAHME] `GET /leads/
      wiedervorlagen` (Rolle Außendienst): Zurück-Pfeil „Mein Tag“, Titel
      „Wiedervorlage“ mit Zähler „9 offen“, Suchfeld „Nach Name suchen“ (filtert
      beim Tippen), Chips Alle/Hoch/Mittel/Niedrig mit Anzahl (bezogen auf die
      Suchtreffer), Sortierung wie oben mit Richtungspfeil, Liste aller
      Vorgänge ohne Begrenzung, gleiche Karte; Leerzustand „Keine Vorgänge
      gefunden“ mit Zeile „Filter oder Suche anpassen.“; untere Leiste mit
      aktivem „Wiedervorlage“. Für Innendienst/Admin entfällt die Seite (sie
      nutzen die Angebotsliste mit Filter Verfolgungsstatus).
- [x] **Erledigt-Logik:** ein Termin gilt als erledigt, wenn die aus
      „Erfassung starten“ angelegte Erfassung abgeschlossen ist (Verknüpfung
      Termin ↔ Erfassung aus v31); kein eigener Haken, kein manuelles Abhaken.
      Telefontermine ohne Erfassung bleiben bis Tagesende offen und erscheinen
      am Folgetag nicht mehr in „Heute“ [ANNAHME].
- [x] Tests `tests/test_v33_mein_tag.py`: Karten nur bei AD + mobil (Desktop-
      Abruf liefert die Tabelle); Kopf ohne Kennzahlen; „Als Nächstes“ mit
      Minutenangabe, „jetzt“ nach Beginn, Karte fehlt ohne Termin heute;
      Zeitstrahl-Zustände; Wiedervorlage: vier Karten, Chip Hoch = heiß an
      erster Stelle bei Sortierung Priorität (ersetzt den v32-Kontrollwert
      „Vorgang in Heiße Kunden“), „seit X Tagen“ ab 14 in Warnfarbe; Seite
      Wiedervorlage mit Suche; Erledigt über abgeschlossene Erfassung.

## Phase 174 – Lead-Board-Layout für alle Tabellen des Angebotstools (Nachtrag Claudia Castro 14.10.2026)

Ziel: die Tabellen des Angebotstools bekommen dieselbe Bedienung wie die
Lead-Boards (v23/v25): Sticky-Filterleiste, Spalten je Nutzer, Sortierung per
Spaltenkopf. **Keine Sammelaktionen** (Entscheidung Claudia Castro
14.10.2026); Löschen, Archivieren, Zuweisen bleiben Einzelaktionen wie heute.
Betroffene Tabellen (Board-Keys in `boards_spalten` [ANNAHME: Schreibweise]):
`leads_vot` (Leads VOT Desktop), `erfassungen`, `angebote` (Angebotsliste),
`meine_angebote` (Außendienst), `taifun_warteschlange`, `kunden`.

- [x] **Gemeinsame Bausteine wiederverwenden** (damit nichts doppelt
      entsteht): Makro `spalten_kopf` aus `_tabelle.html`, Skript
      `lm_boards.js` (Sortieren, Umbenennen, Drag & Drop, Spaltenwähler,
      Zurücksetzen), Ablage je Nutzer in `benutzer_einstellungen` →
      `boards_spalten` mit den neuen Board-Keys; `lead_boards.spalten_fuer /
      sortierung_fuer / spalten_speichern / zeilen_sortieren` um die neuen
      Boards erweitern (Spaltenkataloge je Board als Konstanten, Standard-
      Spaltensatz = heutige Spaltenfolge der jeweiligen Tabelle). CSS: die
      Klassen `.lm-filterblock` / `.lm-tabellen` aus `lead_v2.css` auch
      außerhalb des Lead-Moduls nutzbar (Design-v2-Tokens, Hell/Dunkel).
- [x] **Sticky-Filterleiste** je Tabelle unter der Kopfzeile: die heutigen
      Filter als Chip-Auswahlfelder (Leads VOT: Termin, Vertriebler, Status,
      Priorität = Hot-Ampel; Erfassungen: Status, Sparte, Vertriebler, Archiv;
      Angebotsliste: Status, Verfolgungsstatus (v32), Sparte, Profil/Kanal,
      Vertriebler, Archiv; Meine Angebote: Status, Sparte; Warteschlange:
      Sparte, Status; Kunden: Kanal, Objektart), Suchfeld, Spaltenwähler
      „Spalten“. Tabelle scrollt waagerecht und senkrecht im eigenen
      Container, Tabellenkopf bleibt sichtbar.
- [x] **Leads VOT Desktop mit Gruppen:** Zeilen gruppiert in „Heute“ und je
      einen Block pro Folgetag („Donnerstag, 15. Oktober · 2 Termine“),
      Gruppenköpfe auf- und zuklappbar [ANNAHME], Sortierung innerhalb der
      Gruppe nach Uhrzeit; Spaltensortierung sortiert innerhalb der Gruppen.
- [x] **Sortierung per Klick auf den Spaltennamen** in allen sechs Tabellen:
      erster Klick aufsteigend, zweiter absteigend, Pfeil im Kopf, leere Werte
      ans Ende, Wahl je Nutzer und Tabelle gemerkt.
- [x] **Spalten je Nutzer:** ein-/ausblenden, umbenennen (Stift, leer =
      Standard), Reihenfolge per Drag & Drop am Kopf, „Zurücksetzen“. Feste
      erste Spalte je Tabelle: Kundenname (Leads VOT, Erfassungen,
      Angebotsliste, Meine Angebote, Kunden) bzw. Erfassung (Warteschlange).
- [x] **Rollenregel (fest, keine Rückfrage):** EK, Deckungsbeitrag, DB-Ampel,
      Rabatt-Interna und Summenzeilen mit DB stehen für die Rolle Außendienst
      (und ihre Varianten, Phase 167) in keinem Spaltenkatalog, auch nicht
      ausgeblendet; der Katalog wird serverseitig nach Basisrolle gebaut,
      gespeicherte Spalten-Keys werden gegen den Katalog der Rolle gefiltert.
- [x] **Summenzeile der Angebotsliste** (v6) bleibt und folgt der gefilterten
      und sortierten Liste.
- [x] Tests `tests/test_v33_tabellen.py`: (1) Klick auf „Endbetrag“ in der
      Angebotsliste → aufsteigend, zweiter Klick absteigend, nach Neuladen
      gemerkt; (2) AD ruft `GET /lead-management/boards/spalten?board=
      meine_angebote` → Katalog ohne `ek`, `db`, `db_ampel`; gespeicherter Satz
      mit `db` wird beim Lesen verworfen; (3) Leads VOT Desktop am 14.10.2026
      mit Terminen am 14., 15. und 19.10. → Gruppen „Heute“, „Donnerstag,
      15. Oktober“, „Montag, 19. Oktober“; (4) Spalte umbenennen „Vertriebler“
      → „AD“ nur für diesen Nutzer; (5) Zurücksetzen stellt die heutige
      Spaltenfolge her; (6) Voll-Crawl aller sechs Tabellen je Rolle hell/
      dunkel ohne Fehler.

## Phase 175 – Lead-Management-Nachträge (Nachtrag Claudia Castro 14.10.2026 zu v31)

- [x] **Kanal-Regel im AD-Profil um „Stadtwerke Düsseldorf“ ergänzen:** die
      Kanal-Regel des AD-Profils (Terminassistent-Kandidatenfilter, v25)
      bietet den Kanalwert „Stadtwerke Düsseldorf“ (monday-Kanal SWD,
      Angebotsprofil SWD aus v9) gleichwertig zu den heutigen Kanalwerten;
      Ausschluss/Beschränkung wirkt im Terminassistenten und in der
      Sammelaktion „An Handelsvertreter verschieben“ („übersprungen: Kanal
      Stadtwerke Düsseldorf“) wie bei Enni. Kontrollwert: AD mit Regel „nur
      Stadtwerke Düsseldorf“ erscheint im Terminassistenten nur bei SWD-Leads;
      AD mit Regel „außer Stadtwerke Düsseldorf“ nie bei SWD-Leads.
- [x] **Infotext zum AD entfällt vollständig:** Feld `Benutzer.infotext` aus
      AD-Profil und Benutzerverwaltung entfernen (Formular, Anzeige); im
      Vertriebler-Block der Terminbestätigung (`{vertriebler_block}`, v29) nur
      noch Bild, Name, Telefon, E-Mail. Datenbankspalte bleibt (additiv), wird
      nicht mehr gelesen; Vorlagen-Vorschau und Test anpassen. Kontrollwert:
      Terminbestätigung eines AD mit altem Infotext in der DB enthält den
      Text nicht mehr.
- [x] **Sammelaktion „An Handelsvertreter verschieben“: Ziel „Simons Gruppe“
      statt eines festen Mitglieds.** Die zweite Ziel-Schaltfläche heißt
      „Simons Gruppe“; der Lead hängt danach an der Gruppe, Simon verteilt
      selbst. Umsetzung [ANNAHME, einfachster Weg – Andreas kann die
      Alternative wählen]: `vorgaenge.ad_id` = Simon (Gruppenleiter, erster
      Eintrag von `hv_gruppe_simon`), Kennzeichen in Board/Kartei „Simons
      Gruppe (noch nicht verteilt)“, solange kein Mitglied gewählt wurde;
      Simon weist über das Zuständigen-Dropdown der Kartei (zeigt bei HV-Leads
      nur die eigene Gruppe, v31 Phase 156) ein Mitglied zu, dann verschwindet
      das Kennzeichen; Aktivität „An Simons Gruppe verschoben“. Alternative:
      neue Spalte `vorgaenge.hv_gruppe` mit `ad_id = NULL` (dann müssen HV-
      Sicht, Karte und Kandidatenfilter die Gruppe kennen). Kontrollwert: drei
      Leads verschieben → „3 verschoben“, alle drei bei Simon mit Kennzeichen;
      Simon wählt Paolo → Kennzeichen weg, `ad_id` = Paolo, Aktivität
      „Zuständiger: Paolo Di Blasi“. Mit der Rolle Handelsvertreter (Phase 167)
      bleibt die Gruppenlogik unverändert.
- [x] Tests `tests/test_v33_lead_nachtrag.py` mit den drei Kontrollwerten.

## Phase 176 – Angebotsverfolgung / Nachfassen (Claudia Castro 14.10.2026, Teil C)

Grundlage: Sichtung der Nachfass-Logik von Pipedrive (Deal-Rotting,
Aktivitätsprinzip), HubSpot (Angebotsstatus, Erinnerungen) und Handwerker-
Tools. Bewusst verworfen (14.10.2026): Feld „Gültig bis“ am Angebot, Erkennung,
ob der Kunde das Angebot geöffnet hat, automatische Mail-Sequenzen ohne
Freigabe, Kanban-Pipeline auf dem Handy.

- [x] **Inaktivitäts-Kennzeichen „ohne Kontakt seit X Tagen“** für Vorgänge
      mit Verfolgungsstatus Versendet/Nachgefasst: Schwelle **14 Tage**
      (Einfamilienhaus) und **20 Tage** (Objektart MFH), Parameter
      `inaktiv_tage` / `inaktiv_tage_mfh` in den Angebotstool-Einstellungen;
      Anzeige in „Mein Tag“/Wiedervorlage (AD, Phase 173) und in der
      Angebotsliste (ID) als Kennzeichen und Filter (Phase 174). „Kontakt“ =
      letzter Eintrag im Notizen-Chat, Anruf-Ergebnis oder Mail am Vorgang.
      Eine weit in der Zukunft gesetzte Wiedervorlage schützt nicht vor dem
      Kennzeichen.
- [x] **Telefonversuche zählen:** jedes Ergebnis „Nochmal anrufen“ aus dem
      Dialog „Nächster Schritt“ (v32) erhöht `vorgaenge.nachfass_versuche`
      (additiv); Anzeige im Verfolgungs-Chip „Nachgefasst (2)“ und in der
      Vorgangsakte. Keine Schwelle, keine Eskalation, keine Liste beim
      Innendienst.
- [x] **Einwand-Chips** beim Ergebnis „Nochmal anrufen“, optional (auch kein
      Chip erlaubt): „Förderung unklar“, „wartet auf Mitbewerber“,
      „Entscheidung in der Familie“, „Finanzierung offen“; Liste pflegbar in
      der Parametrierung wie die Ablehnungsgründe (Tabelle `einwaende`); der
      zuletzt gesetzte Chip steht beim nächsten Anruf oben auf der Anruf-
      Karte; Auswertung in der Statistik neben den Ablehnungsgründen.
- [x] **Nachfass-Mail durch den AD:** zwei Vorlagen „Nachfassen 1“ und
      „Nachfassen 2“ im bestehenden Vorlagen-Editor (Platzhalter wie die
      Angebotsvorlagen); der AD löst den Versand aus der Anruf-Karte selbst
      aus; Versand **aus dem eigenen Postfach des AD** – über den Zugriff als
      Anwendung (Phase 166: `sendMail` am Postfach des AD, Postfach in der
      Zugriffsgruppe; die Voraussetzung „Outlook-Zugang je AD“ aus dem
      Protokoll ist damit erfüllt, im Modus `delegiert` bleibt der Knopf
      ausgegraut mit Hinweis); Signatur des AD per Upload wie beim Innendienst
      (v6) [ANNAHME]; Mail landet im Mail-Verlauf des Vorgangs und als
      Aktivität im Chat, Angebots-PDF als Anhang wählbar [ANNAHME].
- [x] Tests `tests/test_v33_nachfassen.py`: Kennzeichen ab Tag 14 bzw. 20 bei
      MFH, Parameter geändert → Grenze folgt; Wiedervorlage in der Zukunft
      schützt nicht; Zähler nach zwei „Nochmal anrufen“ = 2, Chip zeigt
      „Nachgefasst (2)“; Einwand gespeichert und beim nächsten Anruf oben;
      Nachfass-Mail aus dem AD-Postfach (Graph gemockt), im Verlauf und Chat,
      im Modus `delegiert` gesperrt.

## Phase 177 – Tests, Rollout-Vorbereitung, Doku, CLAUDE.md v33

- [x] **Tests gesamt:** neue Dateien `test_v33_graph.py`, `test_v33_rollen.py`,
      `test_v33_service.py`, `test_v33_kalender.py`, `test_v33_outlook.py`,
      `test_v33_auto_phase.py`, `test_v33_rabatt.py`, `test_v33_mein_tag.py`,
      `test_v33_tabellen.py`, `test_v33_lead_nachtrag.py`,
      `test_v33_nachfassen.py`; angepasste Alt-Tests (Rollenvergleiche,
      Versand-Seite, kalender.py, v32-Tests zu Mein Tag/Heiße Kunden/
      Umschalter, Terminbestätigung ohne Infotext) mit Begründung;
      `pytest tests -q` komplett grün, Wächter-AST v27 und Token-Wächter v30
      grün.
- [x] **Rollout-Vorbereitung** nach Grundregel: Server-DB-Kopie nach
      diagnose\, migrate.py zweimal (zweiter Lauf ohne Änderungen; neue
      Tabellen `rollen`, `outlook_ereignisse`, `outlook_auftraege`,
      `outlook_belegt`, Spalten `teams.gewerk`, Terminart `service`,
      Parameter), Rückweg-Probe v32-Code auf v33-DB, Voll-Crawl für alle
      Basisrollen und je eine Variante (Montage Heizung, Service Elektro,
      Handelsvertreter) inkl. der sechs Tabellen aus Phase 174 hell/dunkel,
      Abnahmeskript, Smoke, **Lasttest Profil `normal` und
      `schreibsturm`** (neue Läufe `outlook-sync`/`outlook-ruecklesen` im
      Modell; Pool-Invariante mit 16 Läufen prüfen), Screenshots hell/dunkel
      (Kalender je Modul, Rollen-Seite, Service-Backend, Verbindungs-Seite)
      nach `docs/design-v33/`, nur Demo-Daten.
- [x] **Doku:** CLAUDE.md Abschnitt „Neu in v33 – Outlook je Mitarbeiter,
      Graph als Anwendung, zentraler Kalender, Rollen-Varianten, Service,
      Auto-Phase, Rabatt 0 % (abgestimmt 14.10.2026)“ nach „Neu in v32“,
      Zuordnungstabelle `| v33 | PLAN_V20.md | 166–177 |`, Titelzeile „(v33)“,
      in v5/v12/v15/v23/v29 die Sätze zu „Mit Microsoft anmelden“, Senden-als,
      `kalender_sync`-Testpostfach, Team-Outlook-Kalender, HV über
      `terminiert_selbst` als *überholt – siehe v33* markieren; „Fachliche
      Regeln“ um „Rollen = Basisrolle + Kennzeichen“, „Outlook je Person,
      TAIFUN liest Outlook“, „Rabatt bei jedem Steuersatz“ ergänzen.
      `docs/graph-einrichtung.md` (neu gegliedert, Phase 166),
      `docs/outlook-sync.md` (neu), `docs/betrieb.md` (Inventar, zwei neue
      Läufe, Geheimnis-Ablauf), `docs/projektierung-entscheidungen.md`
      (Auto-Phase, Service), `docs/nach-dem-update-v33.md` (Team: Kalender,
      Service-Rollen, Entwürfe in angebot@, Mein Tag mobil, Tabellen-Bedienung,
      Nachfassen; Admin: Entra-Geheimnis + Gruppe, Rollen zuweisen, Teams-
      Gewerk prüfen, TAIFUN-Abgleich beobachten, Einwand-Liste und
      Inaktivitäts-Tage prüfen); `docs/leadmanagement-entscheidungen.md`
      (Simons Gruppe, SWD-Kanal, Infotext); PROTOKOLL-2026-10-14-Angebotstool.md
      unter `docs/` ablegen,
      `docs/updates.md`; `config.VERSION = "v33"`.
- [x] Gesamtübersicht am Ende: erledigte Phasen, Testergebnisse (Gesamtzahl),
      angepasste Alt-Tests mit Begründung, Liste der auf `basisrolle`
      umgestellten Stellen, Ursache des Rabatt-Fehlers, TAIFUN-Betreffmuster
      und offene Entscheidung dazu, Lasttest-Ergebnisse, [ANNAHME]-Liste,
      Rückfragen gebündelt. **Ein Commit** „v33: Outlook je Mitarbeiter, Graph
      als Anwendung, zentraler Kalender, Rollen-Varianten, Service, Auto-Phase,
      Rabatt 0 %, Mein Tag mobil, Tabellen-Layout, Nachfassen (PLAN_V20, Phasen
      166-177)“; **kein push vor Freigabe**.

## Kontrollwerte für die Abnahme

- Verbindungs-Seite: Modus „Anwendung“, Test grün für angebot@, termin@,
  projektierung@ und einen Monteur; ein Postfach außerhalb der Gruppe wird
  rot mit „nicht in der Zugriffsgruppe“ gelistet.
- „Versand vorbereiten“ durch Claudia → Entwurf im Postfach angebot@/Entwürfe
  mit Claudias Signatur; Andreas sieht ihn in Outlook unter angebot@; nach dem
  Senden aus Outlook: Status „Versendet“, monday-Rückspielung wie bisher.
- Benutzer „Horst“ als Handelsvertreter angelegt → HV-Sicht (v29) ohne
  `terminiert_selbst` von Hand; Monteur mit Rolle „Montage Elektro“ sieht im
  Montage-Backend nur Elektro-Termine seines Teams.
- Service-Einsatz „Wartung“ am Vorgang eines Bestandskunden → im
  Service-Backend von „Service Heizung“, Outlook-Eintrag beim Techniker,
  Servicebericht-PDF in der Galerie.
- `/kalender` aus der Projektierung: nur Monteure + Projektierer vorbelegt;
  aus dem Lead-Modul: AD + HV; Montagetermin mit zwei Monteuren erscheint in
  beiden Zeilen, Krankheit (v31) als grauer Balken, Outlook-Belegt schraffiert.
- Montagetermin im Tool verschoben → beide Outlook-Kopien innerhalb einer
  Minute verschoben; Termin in Outlook um einen Tag verschoben → nach dem
  nächsten Rücklese-Lauf im Tool verschoben, zweite Kopie angeglichen,
  Verlauf „aus Outlook übernommen“; TAIFUN-Termin im selben Kalender bleibt
  unberührt.
- Gewerk in Phase Planung: letzte Pflichtaufgabe erledigt → Phase
  Montagevorbereitung automatisch, Verlauf; `phase_auto = aus` → bleibt.
- PV-Angebot 20.000,00 € netto, 0 % USt, Rabatt 5 % → Endbetrag 19.000,00 €
  im Editor, PDF, Liste, {endbetrag} und monday; DB um 1.000,00 € niedriger.
- AD „Horst“ am Handy (390 px): „Mein Tag“ mit Kopf „Mittwoch, 14. Oktober“,
  Karte „Als Nächstes“ („in 25 Min“, 09:30 bis 10:30, Route starten),
  Liste „Heute · 5 Termine“ mit Zeitstrahl, Abschnitt „Wiedervorlage“ mit
  Chips und höchstens vier Karten (heißer Vorgang mit Badge „Hoch“ zuerst),
  „Kommende Tage“, untere Leiste; derselbe AD am PC: Tabelle „Leads VOT“ mit
  Gruppen „Heute“, „Donnerstag, 15. Oktober“.
- Angebotsliste: Klick auf „Endbetrag“ sortiert, Spalte „Vertriebler“ als „AD“
  umbenannt nur für diesen Nutzer; AD-Katalog ohne EK/DB/DB-Ampel.
- Drei Leads → „An Simons Gruppe“: bei Simon mit Kennzeichen „noch nicht
  verteilt“; Simon wählt Paolo → Kennzeichen weg. Terminbestätigung ohne
  Infotext. AD mit Regel „nur Stadtwerke Düsseldorf“ nur bei SWD-Leads.
- Vorgang Versendet, letzter Kontakt vor 15 Tagen (EFH) → Kennzeichen „ohne
  Kontakt seit 15 Tagen“ in Angebotsliste und Wiedervorlage; MFH erst ab 20;
  zwei „Nochmal anrufen“ → Chip „Nachgefasst (2)“; Nachfass-Mail aus dem
  Postfach des AD im Mail-Verlauf.
- `pytest tests -q` grün, Abnahmeskript grün, Voll-Crawl ohne Absturz,
  Lasttest normal und schreibsturm innerhalb der Zielwerte, 0 „database is
  locked“.

## Zulieferungen / bewusst offen

- **Entra/Exchange (Andreas mit admin@):** Anwendungsberechtigungen
  `Mail.Send`, `Mail.ReadWrite`, `Calendars.ReadWrite` + Zustimmung;
  Geheimnis anlegen (Wert nur in die `.env` auf dem Server, nie ins
  Projektwissen oder in den Chat); Gruppe `friondo-tool-zugriff@` mit allen
  Postfächern (Funktionspostfächer, Außendienst, Projektierung, Monteure,
  Service); `New-ApplicationAccessPolicy` – Befehle stehen in
  `docs/graph-einrichtung.md` nach Phase 166. Bis dahin läuft das Tool im
  Modus `delegiert` weiter.
- **TAIFUN-Abgleich:** Name eines Monteurs mit laufendem Outlook→TAIFUN-
  Abgleich für den lesenden Vorab-Abgleich (Phase 170) und Entscheidung, ob
  Tool-Termine in TAIFUN sichtbar sein sollen.
- **Servicebericht:** Feldliste [ANNAHME] in Phase 168 gegenlesen (Andreas),
  Anlass-Werte bestätigen.
- **Design-Entwurf „Außendienst App“** (Claudia Castro, claude.ai-Artefakt
  https://claude.ai/artifact/LMzyjrovcVvv9NyK9jmMwG – zwei Screens „Mein Tag“
  und „Wiedervorlage“): als HTML-Export nach `docs/design-v33/vorlage/` legen,
  Claude Code nutzt Aufbau und Verhalten, nicht die Farben.
- **Entscheidung Andreas:** „Simons Gruppe“ als `ad_id = Simon` mit
  Kennzeichen (Vorschlag) oder als neue Spalte `vorgaenge.hv_gruppe`
  (Phase 175).
- **Entscheidung Andreas:** Einwand-Chips (Phase 176) – die vier Startwerte
  bestätigen oder ergänzen.
- Bestätigung der [ANNAHME]-Stellen: Teams-Gewerk-Migration (Elektro-Teams →
  elektro, übrige → heizung); Team-Kalender nur optional; Terminkalender
  Woche je AD leitet auf `/kalender` um; Glocke beim automatischen
  Phasenwechsel; Service-Zahl in der Statistik; Zertifikat als Alternative
  zum Geheimnis; Zeitraum „Kommende Tage“ 14 Tage; Route `/leads/wiedervorlagen`;
  Telefontermine ohne Erfassung bis Tagesende; Angebots-PDF als Anhang der
  Nachfass-Mail; Versionsnummer v33 und Phasen 166–177.
- Die heute (14.10.2026) gesetzten delegierten Kalender-Freigaben und die
  Vollzugriffe auf termin@ bleiben bestehen; sie stören im Modus `anwendung`
  nicht und können später von der IT zurückgenommen werden (Hinweis in
  docs/nach-dem-update-v33.md).
- Nicht Teil dieses Plans: Import fremder Outlook-Termine als Tool-Termine
  (bleiben Belegtzeiten), Mobile Push-Benachrichtigungen, Kalender der
  Handelsvertreter ohne Friondo-Postfach (OFFEN 3 aus V4 bleibt),
  **Cloover-Finanzierung im Nachtext** (eigener Plan nach Klärung der
  Installer-API mit Cloover), Sammelaktionen in den Angebotstool-Tabellen.
