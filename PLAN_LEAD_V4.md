# Umsetzungsplan Lead-Management V4: Feedback-Runde 2 (Handelsvertreter-Sicht, Dashboard, E-Mail-Vorlagen, Terminassistent)

**Stand 07.10.2026, 23:00 – Fassung für den kombinierten Durchlauf v28 → v29**
(Original: Chat Lead-Management, Claudia Castro, 07.10.2026; Einfügung in den
Durchlauf durch den Planungs-Chat Angebotstool, Andreas. Fachliche
Entscheidungen unverändert; geändert sind nur Vorspann, Nummern, der Abschnitt
„Einfügung in den Durchlauf v28/v29“ und die mit **(v27)** markierten Zusätze.)

Voraussetzung und Reihenfolge (Stand 07.10.2026, 21:48): **v27 (PLAN_V17,
Phasen 127–132) ist fertig**, committet (2bbd924 „v27: Betriebsreife für 50
Nutzer“, 2544005 „v27-Nachtrag 07.10.2026“) und gepusht (HEAD 1e317e7); ob v27
schon per `update.bat` auf dem Server liegt, ist für den Bau unerheblich – gebaut
wird auf dem **committeten v27-Stand** der Git-Arbeitskopie. **Dieser Plan wird
im selben Durchlauf wie der v27-Nachtrag 2 (PLAN_V17, Abschnitt „Nachtrag
06.10.2026“) und PLAN_PROJ_V6 (v28, Phasen 133–139) umgesetzt: erst Nachtrag,
dann PROJ_V6, dann dieser Plan – EIN gemeinsamer Commit am Ende des gesamten
Durchlaufs** (Entscheidung Andreas 07.10.2026 – die frühere Vorbedingung „V17
und PROJ_V6 müssen auf dem Server sein“ entfällt damit). CLAUDE.md und `leadmanagement_logik_v1.xlsx` sind
Live-Master im Projektordner `C:\Users\a.scheelen\Tools\Angebotstool`
(Git-Arbeitskopie). ALLE PHASEN DIESES PLANS IN EINEM DURCHLAUF UMSETZEN
(Reihenfolge einhalten, jede Checkbox nach Umsetzung und Test abhaken, am Ende
Gesamtübersicht mit Testergebnissen und offenen Punkten, fachliche Rückfragen
gebündelt). migrate.py idempotent, **nur additive Migrationen** (Regel v27
Phase 132: keine Spalte wird gelöscht oder umbenannt, der v27-Code muss auf einer
v29-Datenbank weiterlaufen – Rückweg `rollback.bat --nur-code`). **Kein git push
vor Freigabe.**

CLAUDE-Abschnitt: **„Neu in v29“** – bestätigt 07.10.2026 gegen die
Zuordnungstabelle in CLAUDE.md (v27 = PLAN_V17 steht dort bereits; v28 =
PLAN_PROJ_V6 schreibt der erste Teil des Durchlaufs). Phasen **140 bis 144** –
bestätigt (133–139 gehören zu PLAN_PROJ_V6). Vor dem Bau trotzdem einmal gegen
die Tabelle prüfen; bei Abweichung die nächsten freien Nummern nehmen und die
Phasennummern in diesem Plan durchgängig ersetzen.

Geltungsbereich: ausschließlich das Modul Lead-Management (Router
`app/routers/lm_*.py`, `app/lead_*.py`, `app/static/lead_v2.css`,
`lm_boards.js`, Templates unter `templates/lead_management/`), der
Vorlagen-Editor im Modul (`/lead-management/vorlagen`), die Lead-Glocken, der
Absender-Wechsel der Lead-Mails auf termin@ und der Antwort-/Bounce-Abruf dieses
Postfachs. Angebotstool, Projektierung, monday-Sync und monday-Rückspielung
bleiben unberührt. Alles weiter im Demo-Modus `lead_freigabe_modus = admin`;
Freischaltung ist nicht Teil dieses Plans. Bestehende Tests
(`tests/test_lead_v2_*.py`, `tests/test_lead_v3*.py`, `tests/test_v27_*.py`)
müssen nach Umbau grün sein oder bewusst angepasst werden (Begründung je Test in
der Gesamtübersicht).

Dieser Plan wurde fachlich gegen CLAUDE.md v26 geschrieben; die Einfügung
unten gleicht ihn mit dem **tatsächlichen v27-Code** ab (Scheduler-Rahmen,
Sitzungsdisziplin, Mail-Ausgang, Login, Betriebsglocken). Checkboxen
beschreiben das Soll, nicht Zeilennummern; Stellen, die PROJ_V6 (v28) im selben
Durchlauf verändert (`base.html`, `_komponenten.html`, Vorgangsakte), vor dem
Bau gegen den v28-Zwischenstand abgleichen.

## Einfügung in den Durchlauf v28/v29 (Planungs-Chat Angebotstool, 07.10.2026)

Diese Regeln gelten für jede Checkbox dieses Plans; sie ergänzen Claudias
Entscheidungen, ändern sie aber nicht.

- **Sitzungsdisziplin (v27, verbindlich):** Jeder neue Netzaufruf (Graph-Versand,
  Graph-Abruf termin@, Bild-/ICS-Erzeugung ohne Netz ausgenommen) läuft nur
  **ohne offene Datenbanksitzung** – Muster `db.kurz()` (lesen → Sitzung zu →
  Netz → kurze Sitzung schreiben) wie `lead_mail.versand_job` seit v27. Der
  Wächter-AST-Test `tests/test_v27_sitzungen.py` muss über den gesamten
  v29-Code grün bleiben; Ausnahme-Marker `netz-ohne-sitzung-ok` nur mit
  Begründung im Code-Kommentar. **Kein Request sendet selbst eine Mail**: Knöpfe
  wie „Erneut senden“ oder „Terminbestätigung erneut senden“ setzen nur den
  Warteschlangen-Eintrag auf `geplant` mit sofortiger Fälligkeit; der Lauf
  `lead-mail` (60 s) sendet. Einzige Ausnahme: der Admin-Knopf „Testmail aus
  termin@“ (Phase 142) darf im Request senden, aber mit geschlossener Sitzung
  wie der Heizreport-Verbindungstest.
- **Scheduler-Rahmen (v27):** Jeder neue Hintergrundlauf wird über
  `scheduler.registrieren(name, intervall_s, funktion, beschreibung=…)`
  angemeldet (Single-Flight, Status in `scheduler_status`, Betriebs-Seite,
  `/health`). Neu in v29: **`lead-mail-abruf`** 120 s (Antworten und Bounces
  aus termin@; „inaktiv (Graph nicht eingerichtet)“ ohne Graph, im Demo-Modus
  gegen das Testpostfach). Verarbeitung in Blöcken zu 50 mit Commit je Block
  (`leadmanagement.BLOCK_GROESSE`). Die Zahl der registrierten Läufe steigt
  von 13 auf 14 → `db.pool_invariante` beim Start prüfen (64 + 14 + 5 = 83 ≤
  20 + 70 = 90, erfüllt). Der bestehende Lauf `mail-sync` (angebot@, 900 s)
  bleibt unverändert; der Lauf `lead-parser` (leads@, 120 s) bleibt unverändert.
  Inventartabelle in `docs/betrieb.md` (Fachliche Regeln → Betrieb) um die
  neuen Zeilen ergänzen.
- **Zwei Warteschlangen, klar getrennt:** Die Lead-Mail-Warteschlange
  (`lead_mail`, v12; Vorlagen des Lead-Moduls, Absender `absender_lead_mails`)
  und die v27-Ausgangswarteschlange `mail_ausgang` (Sofort-Benachrichtigungen
  aus `benachrichtigungen.sofort_versenden`, Fallback-Absender) bleiben
  getrennt. **Der Absender termin@ gilt nur für die Lead-Mail-Warteschlange**;
  `mail_ausgang` wird in diesem Plan nicht angefasst. Die Statuswerte `fehler`
  und `wartet_adresse` (Phase 142) sind Zustände der Lead-Mail-Warteschlange.
- **Glocken (Phase 141) – Abgrenzung:** „Glocke nur To-Dos“ gilt für die
  **Lead-Glocken** (Quelle Lead-Modul). Unberührt bleiben: Projektierungs-
  Glocken (@Erwähnung, Aufgaben), Angebotstool-Glocken (Rabatt-Freigabe,
  Wiedervorlage-Kacheln) und die **v27-Betriebsglocken** (art `system` aus
  `betrieb-wache`, Backup-Fehlschlag, Mail-Ausgang nach 3 Fehlversuchen) – sie
  sind keine Lead-Glocken und werden weder vom Parameter `glocke_lead_arten`
  gesteuert noch aus dem Zähler-Badge entfernt. [ANNAHME: die v21-Admin-Glocke
  „Quelle automatisch angelegt“ zählt zu den Lead-Glocken und entfällt ebenfalls
  – Wert `quelle_auto` in `glocke_lead_arten` als wieder einschaltbar
  vorsehen.]
- **Login und Rollen (v27):** HV sind Benutzer mit Rolle Außendienst und
  `ad_profile.terminiert_selbst = 1`; für sie gelten Cookie-Dauer 30 Tage mit
  Häkchen (`sitzung_tage_mobil`), `pin_wechsel_noetig` beim Erst-Login und die
  Fehlversuchssperre wie für alle. Das 404-Gate (Phase 140) sitzt **hinter**
  der v27-Middleware (erst Login/PIN-Wechsel, dann Gate). Tests für die HV-Sicht
  nutzen die Login-Helfer aus `tests/test_v27_login.py` (Cookie v2) bzw. den
  Admin-Zugang `POST /benutzer/{id}/anmelden-als`.
- **Wartungsbanner und Anmeldeseite (v27) bleiben**, auch im Lead-Modul und in
  der HV-Sicht (über `base.html`); das „Mehr …“-Flyout (Phase 141) liegt im
  z-index **unter** dem Wartungsbanner.
- **Lasttest (v27 Phase 131) nach v29 wiederholen:** Terminassistent mit
  Kalenderansicht und drei Vorschlägen, Hauptboard mit Spaltenbreiten,
  Dashboard – Profil `normal`, 50 Nutzer, 20 min; Zielwerte unverändert (p95
  Listen/Akten ≤ 1,5 s, Terminvorschläge ≤ 6 s, 0 TimeoutError, 0 „database is
  locked“). Die Kalenderansicht (Phase 143) lädt deshalb **nachgelagert per
  fetch** (wie `vorschlaege.json` seit v25), Outlook-Belegt nur bei
  `kalender_sync = an`, Cache 10 Minuten je Lead; die Seite selbst rendert ohne
  Graph-Aufruf.
- **Rollout-Vorbereitung einmal für v28 + v29** am Ende des Durchlaufs
  (Server-DB-Kopie nach diagnose\, migrate.py zweimal, Voll-Crawl, Abnahmeskript,
  Smoke-Test, Lasttest); die Checkbox in Phase 144 gilt damit als erfüllt, wenn
  der gemeinsame Lauf grün ist. Rollout selbst nur im Wartungsfenster
  (Dienstag 22:30–23:30, v27) und erst nach Freigabe.
- **Zulieferung `docs/vorlagen/terminbestaetigung/`** liegt am 07.10.2026
  (23:00) **noch nicht** im Projektordner. Das Einspielen (Phase 142) ist
  deshalb ein **wiederholbarer** Schritt, der beim Fehlen des Ordners nichts
  tut und alle Vertriebler mit der Standard-Kopie versorgt; sobald die Dateien
  da sind, spielt `migrate.py` (oder der Knopf in der Lead-Parametrierung) sie
  ein. [ANNAHME: Kennzeichen `quelle = zulieferung` + Datei-Hash je Vorlage –
  im Editor manuell geänderte Vorlagen werden nie überschrieben.]

## Entscheidungen (Chat Lead-Management, 07.10.2026, Claudia Castro)

- **Handelsvertreter sehen nur ihre eigene Sicht**: Menü nur Mein Dashboard ·
  Karte · To-Dos · Handelsvertreter (eigene Leads); Hauptboard, Deals,
  Kontaktiert, Infoabend und das komplette „Mehr …“ sind für HV weder im
  Menü noch per URL erreichbar (404-Gate). Karte zeigt HV nur eigene Leads
  und Termine.
- **Zwei Handelsvertreter-Gruppen**: René Golaschewski allein; Simon O'Grady
  als Vorgesetzter aller übrigen (Paolo Di Blasi, André Lind, Ralf Kinkel,
  Hartmut Leinenbach). Sammelaktion „An Handelsvertreter verschieben“ bietet
  genau diese zwei Ziele: **René** oder **Simon** (Simon verteilt weiter).
  Ausschlussliste F14 (Empfehlung, Messe, Sparkasse Duisburg, SWD, Enni)
  gilt weiter.
- **Unzustellbare E-Mail**: erkennt das Tool einen Bounce auf eine
  Kundenmail, landet der Lead ganz oben im Hauptboard (Gruppe Neu) mit der
  Bemerkung „E-Mail falsch“; weitere automatische Mails an diese Adresse
  pausieren, bis die Adresse geändert wurde.
- **E-Mail-Vorlagen**: Vorlagenliste links untereinander statt oben als
  Leiste. **Terminbestätigung je Vertriebler** (Außendienst und
  Handelsvertreter): jede Vorlage individuell mit Bild und Infos des
  Vertrieblers, Oberkategorie „Terminbestätigung“ ausklappbar, Versand
  automatisch nach zugewiesenem Vertriebler; Option „Änderung für alle
  Vorlagen übernehmen“. Vorlagen und Bilder liegen vor (Zulieferung
  Claudia). **Sparten-Textbaustein**: je nach Interesse (WP, PV, KL, …)
  wird der Absatz „Damit wir uns optimal vorbereiten können, bitten wir Sie
  – sofern möglich – folgende Punkte bereitzuhalten:“ mit einer
  spartenspezifischen Punkteliste gefüllt; die Punkte werden nachgereicht
  [OFFEN 1].
- **Absender aller automatisierten Kundenmails des Lead-Moduls ist
  termin@friondo.de** (Entscheidung 07.10.2026): Eingangsbestätigung, Nicht
  erreicht, Disqualifiziert, Terminbestätigung, „Terminbestätigung erneut
  senden“, Terminerinnerung, Terminänderung, Terminabsage, Online-Termin-
  Einladung und alle künftigen Vorlagen. **leads@friondo.de bleibt
  ausschließlich Eingangspostfach** (Lead-Eingang per Mail-Parser,
  Formulare, Portale, Kommunikation mit den Lead-Partnern) und wird nicht
  mehr als Absender genutzt. Neuer Parameter `absender_lead_mails` (Standard
  `termin@friondo.de`), **kein Fallback auf ein anderes Postfach**: ist
  termin@ nicht sendeberechtigt oder schlägt der Versand fehl, bleibt die
  Mail in der Warteschlange mit Status `fehler`, und der Lead wird für den
  Innendienst sichtbar gemacht wie beim Szenario „E-Mail falsch“: ganz oben
  im Hauptboard mit rotem Vermerk **„Mail nicht gesendet“** (siehe Phase
  142).
  Kundenantworten und Unzustellbarkeitsberichte laufen damit auf termin@ auf
  und werden dort abgerufen und dem Vorgang zugeordnet; der Parser-Abruf von
  leads@ bleibt unverändert. In CLAUDE.md war bisher leads@ als Absender
  dokumentiert (v12, v21, v23); diese Stellen werden als überholt markiert.
  Voraussetzung M365-Admin: Postfach termin@ vorhanden, „Senden als“ und
  Graph-Zugriff (Shared Mailbox) wie bisher für leads@
  (docs/graph-einrichtung.md fortschreiben).
- **Handelsvertreter haben keine Friondo-Postfächer** (Feststellung
  07.10.2026): Terminbestätigungen für HV-Leads sollen aus den persönlichen
  Mailkonten der HV verschickt werden. Das Tool erreicht diese Konten heute
  nicht (Graph nur für Friondo-Postfächer). **Versandweg noch zu klären
  [OFFEN 2]** (Varianten: SMTP-Zugang je HV im Profil · Tool bereitet die
  Mail als Entwurf/.eml vor und der HV sendet selbst · Versand über termin@
  im Namen des HV mit Antwort-an). Ebenso kann das Tool für HV keinen
  Outlook-Kalender lesen oder schreiben; **Kalender-Umgang für HV noch zu
  klären [OFFEN 3]** (nur Tool-Termine mit Sperrzeiten · ICS-Abo des
  privaten Kalenders · HV ohne Assistent). Die Annahme F15 aus V2 („eigenes
  Outlook-Postfach“) ist damit überholt. Bis zur Entscheidung gilt das in
  Phase 142/143 beschriebene Zwischenverhalten.
- **Nurture entfällt**: die Vorlage `nurture` und die Nurture-Logik (+30
  Tage, Kundenantwort weckt den Lead) werden entfernt; was bisher Nurture
  auslöste, nutzt die Vorlage `disqualifiziert` („Disqualifiziert, nicht
  erreicht“, letzte Kaskaden-Stufe).
- **„Mehr …“** öffnet als Flyout rechts neben der schmalen Menüspalte in
  voller Breite der Einträge, nie mit horizontalem Scrollen innerhalb der
  Spalte.
- **Mein Dashboard**: Überschrift „Hallo, <Vorname>“ statt „Meine Arbeit“.
  Es bleiben nur **Fällig heute**, **Kommende Wiedervorlagen** (alle
  künftigen, nicht nur 7 Tage) und **Offene To-Dos**, kompakter gesetzt;
  entfernt werden „Ohne nächsten Schritt“, „Angebots-Wiedervorlagen“ (Kasten
  oben und Liste unten) und der Kasten „Termine 7 Tage“. Rechts eine Karte
  **„Routenplaner“** mit Shortlink zu Google Maps, Start = Friondo GmbH,
  Arnold-Overbeck-Straße 63-65, 47139 Duisburg, Ziel frei. Die ursprünglich
  gewünschte Kachel „Top 3 Baustellen Rhein-Ruhr“ entfällt (externe
  Datenquelle nötig, Entscheidung 07.10.).
- **Glocke nur noch für To-Dos**, für alle Rollen: (a) ein To-Do, das jemand
  anderes mir zugewiesen hat, (b) ein von mir erstelltes To-Do, das jemand
  anderes aktualisiert oder erledigt hat. Alle anderen Lead-Glocken
  (Lead-Eingang, Wiedervorlage fällig, Lead zugewiesen, Kanalwechsel,
  Kundenantwort, Fälligkeits-Scheduler) entfallen; die Ereignisse bleiben
  als Aktivität in der Timeline sichtbar. **(v27)** Betriebs-, Projektierungs-
  und Angebotstool-Glocken sind nicht gemeint (siehe Einfügung).
- **Terminassistent**: genau **3** Vorschläge, der erste als „ideal“
  hervorgehoben; darunter eine Kalenderansicht der in Frage kommenden
  Vertriebler; Aufklappmenü, um zusätzlich andere Vertriebler-Kalender
  einzublenden.
- **Spaltenbreite** im Hauptboard (und den übrigen Boards) mit gedrückter
  Maus am Spaltenrand verstellbar, je Nutzer gespeichert.
- **Eingangsdatum in der Kundenkartei** im Format „TT.MM.JJJJ, HH:MM Uhr“
  [ANNAHME: bisher ISO-/Rohformat; Wunschformat nicht genannt].
- Der Punkt „absagen“ aus der Liste wird nicht umgesetzt (Entscheidung
  07.10.).

## Phase 140: Handelsvertreter-Sicht und HV-Sammelaktion

- [x] **Navigation für HV** (`lm_nav`, `lead_v2.zugriff_erlaubt`/`gate`):
      Benutzer mit `ad_profile.terminiert_selbst = 1` (und ohne Rolle
      Innendienst/Leadmanagement/Admin) sehen in der Icon-Leiste nur **Mein
      Dashboard · Karte · To-Dos · Handelsvertreter** [ANNAHME: To-Dos bleibt,
      da HV To-Dos erhalten können]. Die Einträge Hauptboard, Deals,
      Kontaktiert, Infoabend und „Mehr …“ (mit allen Untereinträgen:
      Anrufliste, Kanban, Kalender, E-Mail-Vorlagen, Übersicht, Statistik,
      Kanal-Report, Posteingang unklar, Import, Schnellanlage,
      Lead-Einstellungen) sind für HV nicht sichtbar und liefern per URL
      **404** (server-seitig, wie das Demo-Gate). Login-Ziel für HV bleibt
      die Handelsvertreter-Ansicht (v23). Direktlinks aus Glocke, Mail oder
      Kartei auf gesperrte Seiten führen auf die HV-Ansicht mit Hinweis.
      **(v27)** Das Gate greift nach Login und PIN-Pflichtwechsel der
      v27-Middleware, nie davor.
- [x] **Karte für HV** (`/lead-management/karte`): zeigt einem HV
      ausschließlich Pins seiner zugewiesenen Leads (`vorgaenge.ad_id` =
      HV) und seiner Termine; Filter Leadmanager/Vertriebler ausgeblendet,
      Filter Phase und Sparte bleiben; Kartenmittelpunkt = Schwerpunkt der
      eigenen Leads, sonst Startadresse des HV-Profils. Innendienst/Admin
      sehen die Karte unverändert.
- [x] **Kundenkartei für HV**: Zugriff nur auf eigene Leads (bestehend);
      Felder Innendienst/Leadmanager nur Anzeige; Sammel- und
      Inline-Zuweisung an andere HV bleibt möglich (F13, untereinander frei).
- [x] **Sammelaktion „An Handelsvertreter verschieben“** (Hauptboard,
      Deals, Infoabend; Registrierung in `SAMMELAKTIONEN`): Dialog mit zwei
      Schaltflächen **„René Golaschewski“** und **„Simon O'Grady (verteilt
      an sein Team)“**; Zielbenutzer aus der Benutzerverwaltung über
      Parameter `hv_gruppe_rene` und `hv_gruppe_simon` (Benutzer-IDs, Lead-
      Einstellungen; Startwerte per Namensabgleich in der Migration), keine
      Namen im Code. Ausführung je Lead über `lead_handelsvertreter.zuweisen`
      (Ausschlussliste F14 greift: ausgeschlossene Leads werden übersprungen
      und im Ergebnis genannt „3 verschoben, 1 übersprungen: Kanal Enni“),
      Aktivität je Lead, keine Glocke (Phase 141). Leads, die bereits bei
      einem HV liegen, werden umgehängt (Aktivität „von X an Y“).
- [x] Handelsvertreter-Ansicht (Innendienst): Filter „Gruppe“ mit den
      Werten René | Simon-Team | alle; Gesamtsicht je Vertreter unverändert.

## Phase 141: Navigation, Boards, Dashboard, Glocke

- [x] **„Mehr …“ als Flyout** (`_nav.html`, `lead_v2.css`, kleines JS):
      Klick öffnet ein Panel, das rechts neben der Icon-Leiste über die
      Spalte hinausragt (position absolute/fixed, z-index über Inhalt,
      **(v27)** aber unter dem Wartungsbanner; Breite nach Inhalt, mindestens
      240 px), Einträge untereinander mit Icon und Text, Schließen per Klick
      außerhalb, Escape oder erneutem Klick; kein horizontales Scrollen
      innerhalb der Menüspalte. Unter 900 px (untere Icon-Zeile) öffnet das
      Flyout nach oben.
- [x] **Spaltenbreite je Nutzer** (`lm_boards.js`, `boards_spalten`): am
      rechten Rand jedes Spaltenkopfs ein Ziehgriff; Ziehen mit gedrückter
      Maus verändert die Breite live (min 60 px, max 600 px), Loslassen
      speichert per fetch `breite` je Spalte in `boards_spalten`
      (Struktur um `breite` erweitern, v25-Einträge ohne Breite = Standard).
      Doppelklick auf den Griff = Standardbreite. Gilt für Hauptboard, Deals,
      Infoabend, Handelsvertreter; nur für den angemeldeten Nutzer. Sticky-
      Filter und Sticky-Kopf bleiben funktionsfähig (Breiten über
      `<colgroup>` setzen).
- [x] **Mein Dashboard** (`app/lead_dashboard.py`, Template):
      Überschrift **„Hallo, <Vorname>“** (Vorname aus der Benutzerverwaltung;
      fehlt er, Anzeigename). Linke Spalte (ca. 40 % Breite ab 1200 px,
      kompakte Kästen): **Fällig heute** (Lead-Wiedervorlagen und Rückrufe
      heute), **Kommende Wiedervorlagen** (alle künftigen, chronologisch,
      ohne 7-Tage-Grenze, Gruppierung nach Datum, lange Listen mit „mehr
      anzeigen“), **Offene To-Dos** (Link zur To-Dos-Seite). **Entfernt:**
      Kasten und Liste „Ohne nächsten Schritt“ (Parameter
      `ohne_schritt_tage` bleibt ohne Wirkung, in der Parametrierung
      ausblenden), Kasten und Liste „Angebots-Wiedervorlagen“, Kasten
      „Termine 7 Tage“ oben [ANNAHME: nur der Kasten entfällt; die Liste
      „Meine Termine“ weiter unten bleibt]. **(v27)** Nur das Lead-Dashboard
      ist gemeint – die Startseiten-Kachel „fällig“ des Angebotstools und die
      Angebotsverfolgung bleiben unverändert. Rechte Spalte: Karte
      **„Routenplaner“** mit Button „Route in Google Maps öffnen“ → Link
      `https://www.google.com/maps/dir/?api=1&origin=Arnold-Overbeck-Stra%C3%9Fe+63-65,+47139+Duisburg&travelmode=driving`
      (Startadresse als Parameter `routen_start`, Standard Friondo Duisburg;
      Ziel bleibt leer, der Nutzer trägt es in Maps ein), öffnet in neuem
      Tab. Darunter bleibt die Liste „Meine Termine“ (eigene VOT der nächsten
      Tage) [ANNAHME]. Kacheln-Zeile oben entfällt bis auf die drei genannten
      Zahlen.
- [x] **Glocke nur To-Dos** (`lead_todos.py`, `lead_v2.py`, Scheduler): nur
      noch zwei Lead-Glocken-Arten: `todo_zugewiesen` (jemand anderes weist
      mir ein To-Do zu) und `todo_aktualisiert` (jemand anderes ändert oder
      erledigt ein von mir erstelltes To-Do; eigene Änderungen lösen nichts
      aus). Entfernt bzw. abgeschaltet: Glocken für Lead-Eingang, SLA,
      Wiedervorlage fällig (`faellige_wiedervorlagen_melden` im Lauf
      `leadmanagement` nur noch für To-Do-Fälligkeiten), Lead/HV-Zuweisung,
      Kanalwechsel-Hinweis, Kundenantwort, Terminänderung, Tagesdigest-Glocke,
      [ANNAHME] Quelle automatisch angelegt (v21). **(v27) Nicht betroffen:**
      Projektierungs-Glocken (@Erwähnung, Aufgaben), Angebotstool-Glocken und
      die Betriebsglocken art `system` (betrieb-wache, Backup, Mail-Ausgang) –
      sie zählen weiter im Zähler-Badge. Alle entfallenen Lead-Ereignisse
      bleiben als Aktivitäten in der Timeline. Parameter `glocke_lead_arten`
      als Liste (Standard nur die zwei To-Do-Arten; weitere Werte:
      `lead_eingang`, `sla`, `wiedervorlage`, `zuweisung`, `kanalwechsel`,
      `kundenantwort`, `terminaenderung`, `digest`, `quelle_auto`), damit
      einzelne Arten später wieder einschaltbar sind – der Parameter wirkt nur
      auf Lead-Glocken.
- [x] **Eingangsdatum in der Kundenkartei**: Anzeige „TT.MM.JJJJ, HH:MM
      Uhr“ (Filter `de_datum` erweitern oder neuer Filter `de_datum_zeit`),
      an allen Stellen der Kartei (Kundeninfo-Block, Kopf); Boards behalten
      das kurze Datumsformat.

## Phase 142: E-Mail-Vorlagen, Terminbestätigung je Vertriebler, Bounce

- [x] **Vorlagen-Editor** (`/lead-management/vorlagen`): Vorlagenliste als
      **linke Spalte untereinander** (Baum mit Kategorien) statt Reiterleiste
      oben; rechts der Editor der gewählten Vorlage (Betreff, HTML-Text mit
      Formatierung, Platzhalterliste, Vorschau mit Demo-Lead). Kategorien:
      Eingang (eingangsbestaetigung) · Kontakt (nicht_erreicht,
      disqualifiziert) · **Terminbestätigung** (ausklappbar, siehe unten) ·
      Termin (terminerinnerung, terminaenderung, terminabsage,
      online_termin_einladung) · Sonstige. Aktive Vorlage markiert, Suche
      über Vorlagennamen.
- [x] **Terminbestätigung je Vertriebler**: Oberkategorie
      „Terminbestätigung“ enthält die Vorlage **„Standard“** und je aktivem
      Vertriebler (Außendienst mit AD-Profil und Handelsvertreter) eine
      eigene Vorlage `terminbestaetigung_<benutzer_id>` mit Anzeigename
      „Terminbestätigung – <Name>“. Aufbau jeder Vertreter-Vorlage:
      gemeinsamer **Rahmen** (Betreff, Einleitung, Terminblock mit
      {termin_datum}/{termin_uhrzeit}/{adresse}, Sparten-Baustein
      {sparten_hinweise}, Schluss, Signatur) plus **individueller Block**
      {vertriebler_block} mit Bild, Name, Telefon, E-Mail und persönlichem
      Infotext. Je Vertriebler in der Benutzerverwaltung: **Bild** (Upload
      JPG/PNG, max 2 MB, Inline-CID im Versand wie bei den Signaturen),
      Infotext, Telefon, E-Mail. **Versandregel** (`lead_termin.buchen`,
      Terminierung B8, „Terminbestätigung erneut senden“): Vorlage des
      zugewiesenen Vertrieblers des Termins; fehlt sie oder ist sie leer →
      Standard mit Hinweis in der Aktivität. ICS-Anhang, Erinnerung und
      Storno bleiben. **(v27)** Der Request legt nur den Warteschlangen-
      Eintrag an (Bild als CID-Anhang-Verweis, kein Graph-Aufruf im Request);
      der Lauf `lead-mail` sendet. **Gilt vollständig für angestellte
      Außendienstler** (Versand über `absender_lead_mails` =
      termin@friondo.de). **Für Handelsvertreter-Leads** [OFFEN 2]: Parameter
      `hv_versandweg` mit den Werten `offen` (Standard) · `smtp` · `entwurf` ·
      `leads_im_namen`; Claude Code baut die Vorlagen und Bilder für HV mit,
      aber nur den Wert `offen`: beim Terminieren eines HV-Leads wird **keine**
      Kundenmail erzeugt, stattdessen Aktivität „Terminbestätigung nicht
      gesendet: Versandweg für Handelsvertreter offen“, To-Do an den HV
      „Terminbestätigung selbst senden“ mit Link auf eine Vorschau der
      fertigen Mail (Text und ICS zum Herunterladen) [ANNAHME als
      Zwischenlösung]. Die anderen drei Werte werden im Code als
      Erweiterungspunkt (eine Funktion je Weg, noch ohne Inhalt) angelegt und
      in `docs/leadmanagement-entscheidungen.md` mit Voraussetzungen
      beschrieben (SMTP: App-Passwort je HV, Speicherung verschlüsselt;
      Entwurf: .eml-Download; leads_im_namen: Reply-To). Erinnerung −24 h und
      Storno-ICS folgen demselben Schalter.
- [x] **„Änderung für alle Vorlagen übernehmen“**: im Editor einer
      Terminbestätigungs-Vorlage ein Häkchen „Rahmen für alle
      Terminbestätigungen übernehmen“; beim Speichern wird der Rahmen
      (alles außer {vertriebler_block}) in alle Vorlagen der Oberkategorie
      geschrieben, individuelle Blöcke bleiben; Sicherheitsabfrage mit
      Anzahl, Protokoll als Aktivität in der Parametrierung. Neue
      Vertriebler erhalten automatisch eine Kopie der Standard-Vorlage.
- [x] **Sparten-Baustein {sparten_hinweise}**: Absatz wörtlich „Damit wir
      uns optimal vorbereiten können, bitten wir Sie – sofern möglich –
      folgende Punkte bereitzuhalten:“ gefolgt von einer Aufzählung aus dem
      neuen Blatt **„Terminhinweise“** der `leadmanagement_logik_v1.xlsx`
      (Spalten `sparte` WP/PV/KL/WB/GW, `reihenfolge`, `punkt`;
      Arbeitsanweisung: Blatt anlegen, Import in der Parametrierung
      erweitern). Bei mehreren Interessen werden die Listen der Sparten
      nacheinander mit Zwischenüberschrift ausgegeben, Dubletten entfernt.
      Bis die Punkte nachgereicht sind [OFFEN 1]: Platzhalterzeile je Sparte
      „(Punkte folgen)“ und Hinweis in docs/nach-dem-update.
- [x] **Zulieferung einarbeiten**: die individuellen Terminbestätigungs-
      Texte und Bilder je Vertriebler (Claudia stellt sie unter
      `docs/vorlagen/terminbestaetigung/<name>.html` und `.jpg` in den
      Projektordner) werden als Vorlagen und Benutzerbilder eingespielt;
      fehlende Vertriebler erhalten die Standard-Kopie. **(v27/Stand 07.10.)**
      Der Ordner liegt noch nicht vor – das Einspielen ist ein **wieder-
      holbarer** Schritt (`scripts/vorlagen_einspielen.py`, läuft in
      `migrate.py` mit und ist als Knopf „Terminbestätigungen aus
      docs/vorlagen einspielen“ in der Lead-Parametrierung erreichbar): ohne
      Ordner tut er nichts außer Standard-Kopien anzulegen; mit Ordner spielt
      er je Datei ein, merkt sich `quelle = zulieferung` und den Datei-Hash
      und überschreibt nur Vorlagen, die seit dem letzten Einspielen nicht im
      Editor geändert wurden [ANNAHME]. Ergebnis je Lauf als Protokollzeile.
- [x] **Nurture entfernen**: Vorlage `nurture`, Kaskaden-Aktion
      `mail_nurture`, Wiedervorlage +30 Tage und „Kundenantwort weckt den
      Lead“ aus `lead_anrufliste`/Kaskade/Scheduler entfernen; letzte
      Kaskaden-Stufe nutzt ausschließlich `disqualifiziert`. Blatt Kaskade:
      Spalte `nach_letztem` auf `mail_disqualifiziert` setzen
      (Arbeitsanweisung Live-Excel); Einwilligungs-Prüfung bleibt für
      `disqualifiziert` nicht erforderlich (Vertragsanbahnung) [ANNAHME].
      Vorlage im Editor ausgeblendet, Datensatz bleibt (Historie).
      **(v27)** Der Nurture-Block im Lauf `leadmanagement` entfällt; die
      Scheduler-Registrierung bleibt bestehen (andere Teilschritte).
- [x] **Absender termin@friondo.de für alle Lead-Mails**: Parameter
      `absender_lead_mails` in den Lead-Einstellungen ersetzt den bisherigen
      Absender leads@ in `mail_planen`/Versand-Job für sämtliche Vorlagen
      des Moduls (keine Ausnahme je Kategorie); **kein Fallback**: bei
      fehlendem oder nicht sendeberechtigtem Postfach oder einem Graph-Fehler
      bleibt die Mail mit Status `fehler` in der Warteschlange (nach den
      üblichen Wiederholversuchen des Versand-Jobs). **Sichtbarkeit für den
      Innendienst** wie beim Szenario „E-Mail falsch“: am Vorgang
      `mail_fehler = 1` (Vorlage, Zeitpunkt, Fehlertext), Aktivität „Mail
      nicht gesendet: <Vorlage>, <Grund>“, Notiz-Spalte erhält vorn das rote
      Label **„Mail nicht gesendet“**, der Lead steht im Hauptboard ganz oben
      (Rang 0, bei Deals-Leads zusätzlich Hinweis im Deals-Board), in der
      Kundenkartei ein roter Hinweisbalken mit Button **„Erneut senden“**
      und Link zur Warteschlange; Dashboard-Kachel „Mails mit Fehler“ (nur
      sichtbar, wenn > 0). **(v27)** „Erneut senden“ setzt den Eintrag auf
      `geplant` mit sofortiger Fälligkeit und setzt den Versuchszähler zurück;
      gesendet wird durch den Lauf `lead-mail` (≤ 60 s), Rückmeldung „Erneuter
      Versand angestoßen – Ergebnis in etwa einer Minute“. Erfolgreicher
      erneuter Versand setzt `mail_fehler` zurück und entfernt Label und
      Rang. Zusätzlich Hinweis in der Lead-Parametrierung (Zähler offener
      Fehler, Link) und **(v27)** die Zahl der Lead-Mails mit Status `fehler`
      als Kachel auf der Betriebs-Seite `/parametrierung/betrieb` (kein
      `/health`-warn) [ANNAHME]. Mail-Abruf für Kundenantworten und Bounces
      auf termin@ umstellen (Konversations-Zuordnung wie bisher) – **(v27)**
      als neuer Lauf `lead-mail-abruf` (120 s, `scheduler.registrieren`,
      `db.kurz()`, 50er-Blöcke, siehe Einfügung); der Parser-Abruf des
      Lead-Eingangs bleibt auf leads@ und wird nicht angefasst. Prüfpunkt
      „Testmail aus termin@“ in der Lead-Parametrierung (Request ohne offene
      Sitzung); im Demo-Modus weiterhin nur Testpostfach.
      `docs/graph-einrichtung.md`: Shared-Mailbox-Zugriff und „Senden als“ für
      termin@ (M365-Admin); Hinweis, dass leads@ nur noch gelesen wird.
      Migration: offene Einträge der Mail-Warteschlange erhalten den neuen
      Absender. Inventartabelle `docs/betrieb.md` ergänzen.
- [x] **Unzustellbare E-Mail**: der Lauf `lead-mail-abruf` (termin@;
      leads@ nur noch für den Lead-Eingang) erkennt Unzustellbarkeitsberichte
      (Absender postmaster/MAILER-DAEMON, Betreff „Unzustellbar“/
      „Undeliverable“/„Delivery Status Notification“, Original-Empfänger aus
      Header oder Text; In-Reply-To/Konversation auf eine Tool-Mail aus
      `kommunikation_log`). Treffer → am Vorgang `email_status = ungueltig`
      (Datum, Grund), Aktivität „E-Mail unzustellbar“, Notiz-Spalte erhält
      vorn den Vermerk **„E-Mail falsch“** (rotes Label), E-Mail-Feld in der
      Kartei rot umrandet mit Tooltip; der Lead wird ins **Hauptboard,
      Gruppe Neu, ganz oben** einsortiert (Rang 0 vor SLA rot, Phase bleibt;
      bei Phase Terminiert/Deals zusätzlich Hinweis im Deals-Board, kein
      Rückfall der Phase [ANNAHME]). Weitere Mails der Warteschlange an
      diese Adresse werden angehalten (Status `wartet_adresse`); Änderung
      der E-Mail-Adresse per Autospeichern setzt `email_status` zurück und
      gibt die Warteschlange frei. Test mit zwei Beispiel-NDRs (Exchange
      Online deutsch und englisch) als Fixture; Graph in allen Tests gemockt.

## Phase 143: Terminassistent

- [x] **Drei Vorschläge statt fünf** (`lead_termin.vorschlaege`, Parameter
      `vorschlaege_anzahl` Standard 3): Vorschlag 1 wird als **„Ideal“**
      hervorgehoben (Rahmen in Friondo-Blau, Badge „Ideal“, Begründung in
      Klartext), 2 und 3 darunter; gleiche Bewertung wie v23/v25 (Umweg,
      Wunschzeit, Kompetenz, Kapazität, HV-Ausschluss) und **(v27)** derselbe
      gebündelte Routing-Aufruf (`routing.matrix_fuellen`, ein Aufruf). Block
      „Termine“ in der Kartei zeigt dieselben drei.
- [x] **Kalenderansicht darunter**: Wochenansicht (Mo bis Sa, 15-Minuten-
      Raster, Arbeitszeiten der AD-Profile) mit je einer Spalte pro
      **in Frage kommendem Vertriebler** (Kandidatenfilter des Assistenten),
      Tool-Termine und Outlook-Belegt (falls `kalender_sync` an) als Blöcke,
      die drei Vorschläge als farbig markierte Slots; Klick auf einen freien
      Slot = manuelle Buchung mit Konfliktprüfung (bestehender Dialog).
      Wochenwechsel vor/zurück, Standardwoche = Woche des ersten Vorschlags.
      **(v27)** Daten nachgelagert per fetch
      `GET /lead-management/lead/{id}/termin/kalender.json?woche=…`
      (Outlook-Belegt ohne offene Sitzung, Cache 10 Minuten je Lead und
      Woche, `?neu=1` erzwingt); die Seite rendert ohne Graph-Aufruf.
- [x] **Handelsvertreter im Kalender** [OFFEN 3]: bis zur Entscheidung
      zeigt die Kalenderansicht für HV ausschließlich Tool-Termine
      (`vot_termine`) und Sperrzeiten, die der HV selbst im Tool einträgt
      (neuer Eintragstyp `sperrzeit` an `vot_termine`, Anlegen in „Meine
      Termine“ der HV-Sicht: Datum, von/bis, Bemerkung) [ANNAHME als
      Zwischenlösung]; kein Graph-Zugriff, keine Outlook-Ereignisse für HV
      (`kalender_sync` überspringt Benutzer ohne Friondo-Postfach mit
      Protokollzeile statt Fehler). Die Varianten ICS-Abo und „ohne
      Assistent“ werden in `docs/leadmanagement-entscheidungen.md`
      beschrieben, nicht gebaut.
- [x] **Aufklappmenü „Weitere Kalender“**: Mehrfachauswahl aller aktiven
      Vertriebler (AD und HV), die nicht zum Kandidatenkreis gehören;
      ausgewählte Kalender erscheinen als zusätzliche Spalten (grau
      beschriftet „außerhalb der Vorauswahl“), Buchung dort erlaubt mit
      Warnhinweis (Kompetenz/Kanal/HV); Auswahl je Nutzer gemerkt
      (`benutzer_einstellungen` Key `assistent_kalender`).

## Phase 144: Tests, Doku, Übergabe

- [x] Tests `tests/test_lead_v4.py`: (a) HV-Login (Cookie v2, PIN-Wechsel
      erledigt): Menü nur vier Einträge, 404 auf Hauptboard/Deals/Kontaktiert/
      Infoabend/Anrufliste/Vorlagen; (b) Karte für HV nur eigene Pins;
      (c) Sammelaktion HV-Verschieben an René und an Simon, Ausschluss-Lead
      übersprungen und gemeldet; (d) Flyout-Markup vorhanden, kein
      `overflow-x` in der Nav-Spalte; (e) Spaltenbreite speichern/
      zurücksetzen nur für den Nutzer; (f) Dashboard: Überschrift „Hallo,
      <Vorname>“, keine Elemente „Ohne nächsten Schritt“/„Angebots-
      Wiedervorlagen“/„Termine 7 Tage“, Wiedervorlage in 30 Tagen erscheint
      unter „Kommende“, Maps-Link mit Startadresse; (g1) alle Lead-Vorlagen
      tragen Absender termin@, keine Mail trägt leads@ oder angebot@; ohne
      Senderecht Status `fehler`, Lead oben im Hauptboard mit „Mail nicht
      gesendet“, Kachel zählt 1, „Erneut senden“ setzt auf `geplant`, der
      Lauf `lead-mail` (synchron über `scheduler.ausfuehren`) räumt nach
      Freigabe alles auf; (g2) HV-Lead terminieren → keine Mail, Aktivität
      „Versandweg offen“, To-Do beim HV mit Vorschau; AD-Lead terminieren →
      Mail wie gewohnt; (g3) HV-Sperrzeit blockiert einen Vorschlags-Slot;
      (g) Glocke: Lead-Eingang und Zuweisung erzeugen keine Glocke,
      To-Do-Zuweisung und Fremd-Erledigung schon, eigene Erledigung nicht,
      **eine Betriebsglocke art `system` bleibt im Zähler**; (h) Eingangs-
      datum-Format in der Kartei; (i) Vorlagenbaum links, Terminbestätigung
      je Vertriebler, Versand wählt die Vorlage des zugewiesenen
      Vertrieblers, Fallback Standard, „für alle übernehmen“ lässt
      individuelle Blöcke unverändert; (j) Sparten-Baustein für WP, WP+PV,
      GW; (k) keine Nurture-Mail mehr, letzte Stufe = disqualifiziert;
      (l) Bounce-Fixture über `scheduler.ausfuehren("lead-mail-abruf")` →
      „E-Mail falsch“, Rang 0, Warteschlange angehalten, Adressänderung gibt
      frei; (m) drei Vorschläge, erster „Ideal“, Kalenderspalten =
      Kandidaten, weitere Kalender per Auswahl, `kalender.json` ohne
      gehaltene Verbindung; (n) **(v27)** `tests/test_v27_sitzungen.py`
      (Wächter-AST) und `test_v27_scheduler.py` grün mit dem neuen Lauf,
      Pool-Invariante mit 14 Läufen erfüllt. Bestehende Lead-Tests anpassen
      (Glocken, Nurture, Vorschlagsanzahl, Dashboard-Elemente), jede
      Anpassung begründen. Gesamtlauf grün.
- [x] Rollout-Vorbereitung nach Grundregel – **einmal für v28 + v29** am Ende
      des Durchlaufs: Server-DB-Kopie nach diagnose\, migrate.py zweimal
      fehlerfrei (Migrationen `email_status`, `mail_fehler`,
      `boards_spalten.breite`, Vorlagen je Vertriebler, Benutzerbilder,
      Parameter `absender_lead_mails`, `hv_gruppe_*`, `hv_versandweg`,
      `glocke_lead_arten`, `routen_start`, `vorschlaege_anzahl`, Blatt
      Terminhinweise; zweiter Lauf ohne Änderungen), `scripts/voll_crawl.py`
      für admin/innendienst/aussendienst/montage und einen HV-Testbenutzer,
      Abnahmeskript grün, `scripts\smoke.bat`, **Lasttest Profil `normal`
      (50 Nutzer, 20 min) mit Zielwerten v27**, Screenshots vorher/nachher
      (Dashboard, Flyout, Vorlagen-Editor, Terminassistent mit Kalender) nach
      `docs/design-v29/`, nur Demo-Daten.
- [x] CLAUDE.md: Abschnitt „Neu in v29 – Lead-Management V4 Feedback-Runde 2
      (abgestimmt 07.10.2026)“ **nach** dem Abschnitt „Neu in v28“ (Plan:
      PLAN_LEAD_V4.md, Phasen 140 bis 144), Zuordnungstabelle `| v29 |
      PLAN_LEAD_V4.md | 140–144 |`; in „Neu in v12“, „v21“, „v23“ und „v25“
      die Sätze zu Nurture, Lead-Glocken, fünf Vorschlägen, „Ohne nächsten
      Schritt“, Vorlagen-Reitern und zum Absender leads@ als *überholt –
      siehe v29* markieren (Absender aller Lead-Mails ist termin@, leads@ nur
      Eingang); in „Neu in v27“ die Scheduler-Liste um `lead-mail-abruf`
      ergänzen (14 Läufe). `docs/leadmanagement-entscheidungen.md` Abschnitt
      V4 mit allen [ANNAHME]-Auflösungen; `docs/nach-dem-update-v29.md`
      (Team-Hinweise: HV sehen nur noch ihre Sicht, Glocke nur To-Dos,
      Vorlagen je Vertriebler pflegen, Bilder hochladen, Terminhinweise je
      Sparte nachtragen, Spaltenbreiten; Server-To-dos: Parameter
      `hv_gruppe_*` prüfen, Bilder und Vorlagen aus `docs/vorlagen/`
      eingespielt?, M365: termin@ „Senden als“ + Graph-Lesezugriff);
      `docs/betrieb.md` Inventartabelle und `docs/updates.md` (Format wie
      vorhanden) um v29 ergänzen.
- [x] Gesamtübersicht am Ende: erledigte Phasen, Testergebnisse,
      angepasste Alt-Tests mit Begründung, Liste aller [ANNAHME]-Stellen,
      gebündelte Rückfragen. **Ein gemeinsamer Commit** für den ganzen
      Durchlauf (v27-Nachtrag 2 + v28 + v29) erst nach der Rollout-
      Vorbereitung, Nachricht „v27-Nachtrag 2 + v28 + v29: Klima-Versand/
      Anmeldeseite, Projektierung V6 (Phasen 133-139), Lead-Management V4
      (Phasen 140-144)“; **kein push vor Freigabe**.

## Kontrollwerte für die Abnahme

- Login als Paolo Di Blasi (HV): Icon-Leiste zeigt Mein Dashboard · Karte ·
  To-Dos · Handelsvertreter; Aufruf `/lead-management/hauptboard` → 404;
  Karte zeigt nur seine Leads.
- Hauptboard: 4 Leads markiert (einer mit Kanal Enni) → „An Simon“ →
  Meldung „3 verschoben, 1 übersprungen: Kanal Enni“; die drei stehen in
  Simons HV-Sicht.
- Dashboard Innendienst-Benutzerin „Claudia“: Überschrift „Hallo, Claudia“;
  Wiedervorlage am 15.11.2026 steht unter „Kommende Wiedervorlagen“;
  Maps-Button öffnet Google Maps mit Start „Arnold-Overbeck-Straße 63-65,
  47139 Duisburg“ und leerem Ziel.
- Neuer Lead per API → keine Glocke; To-Do von Benutzer A an B → Glocke
  bei B mit Zähler 1; B erledigt → Glocke bei A. Eine Betriebsglocke
  (`betrieb-wache`, art `system`) an einen Admin bleibt sichtbar und zählt.
- Neuer Lead per API → Eingangsbestätigung von termin@friondo.de (im
  Demo-Modus ans Testpostfach, Absender im Protokoll sichtbar), nie von
  leads@. Termin bei Vertriebler Horst gebucht → Terminbestätigung ebenfalls
  von termin@ und nutzt „Terminbestätigung – Horst“ mit seinem Bild (CID)
  und bei Interesse WP+PV zwei Punktelisten.
- Senderecht für termin@ im Test entzogen → Eingangsbestätigung bleibt
  `fehler`, Lead steht ganz oben im Hauptboard mit rotem „Mail nicht
  gesendet“, Kartei zeigt Hinweisbalken mit „Erneut senden“; nach Freigabe,
  Klick und einem Lauf `lead-mail` ist die Mail `gesendet`, Label und Rang
  verschwinden.
- NDR-Fixture auf die Eingangsbestätigung → Lead steht im Hauptboard ganz
  oben, Notiz beginnt mit „E-Mail falsch“, Kaskaden-Mail 2 bleibt
  `wartet_adresse`; nach Adressänderung Status `geplant`.
- Terminassistent zeigt genau drei Vorschläge, der erste mit Badge
  „Ideal“; Kalender darunter mit einer Spalte je Kandidat; Auswahl „René
  Golaschewski“ im Aufklappmenü ergänzt seine Spalte.
- `/health` listet den Lauf `lead-mail-abruf` mit Intervall 120 s;
  `/parametrierung/betrieb` zeigt die Kachel „Lead-Mails mit Fehler“;
  `pytest tests -q` grün inkl. `test_v27_sitzungen.py`; Lasttest Lauf nach
  v29: alle Zielwerte v27 erfüllt.

## Zulieferungen / bewusst offen

- **M365-Admin:** Postfach termin@friondo.de mit „Senden als“ und
  Graph-Zugriff (Shared Mailbox, lesen für Antworten/Bounces); ohne diese
  Rechte gehen keine Lead-Mails raus (bewusst kein Fallback), die
  betroffenen Leads erscheinen oben im Hauptboard mit „Mail nicht gesendet“.
  Im Demo-Modus (heute) betrifft das nur das Testpostfach – vor der
  Freischaltung `lead_freigabe_modus = alle` muss termin@ eingerichtet sein.
- **[OFFEN 2]** Versandweg der Terminbestätigung für Handelsvertreter-Leads
  (persönliche Mailkonten der HV): Entscheidung Claudia/Andreas, danach
  eigener kleiner Nachtrag oder Folgeplan; bis dahin Zwischenlösung
  `hv_versandweg = offen` (Phase 142).
- **[OFFEN 3]** Kalender der Handelsvertreter ohne Friondo-Postfach:
  Entscheidung Claudia/Andreas; bis dahin nur Tool-Termine und Sperrzeiten
  (Phase 143).
- **[OFFEN 1]** Punkte je Sparte für den Baustein „folgende Punkte
  bereitzuhalten“ (Claudia reicht nach; bis dahin Platzhalter).
- **Zulieferung Claudia:** individuelle Terminbestätigungs-Texte und Bilder
  je Vertriebler nach `docs/vorlagen/terminbestaetigung/` im Projektordner
  (Dateiname = Benutzername, z. B. `horst.html`, `horst.jpg`); am 07.10.2026
  noch nicht vorhanden – Einspielen nachholbar über migrate.py oder den Knopf
  in der Lead-Parametrierung (Phase 142); fehlt ein Vertriebler, bekommt er
  die Standard-Kopie.
- Bestätigung der [ANNAHME]-Stellen: To-Dos im HV-Menü; Liste „Meine
  Termine“ bleibt auf dem Dashboard; Eingangsdatum-Format „TT.MM.JJJJ,
  HH:MM Uhr“; Bounce bei Deals-Leads nur Hinweis, kein Phasenrückfall;
  `disqualifiziert` ohne Einwilligungsprüfung; v21-Glocke „Quelle
  automatisch angelegt“ entfällt mit; Fehler-Kachel auf der Betriebs-Seite
  ohne `/health`-warn; Einspiel-Regel „nur unveränderte Vorlagen
  überschreiben“. CLAUDE-Version v29 und Phasen 140 bis 144 sind bestätigt.
- Nicht umgesetzt (Entscheidung 07.10.): „Top 3 Baustellen Rhein-Ruhr“
  (externe Datenquelle), „absagen“. Weiterhin offen aus V2: Zuordnungsregel
  Infoabend-Lead → Veranstaltung, Rest des Auftragstexts (Duplikate durch
  das Tool), Telefonie/Softphone-Anbindung.
- Freischaltung `lead_freigabe_modus = alle` (eigener Plan).
