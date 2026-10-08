# Friondo Angebotstool – Projektkontext (v27)

## Ziel
Zweistufiger Vertriebsprozess der Friondo GmbH: Außendienst erfasst mobil per
Fragenkatalog (gespeist aus monday-Leads mit Vor-Ort-Termin), Innendienst erzeugt,
prüft, rabattiert und versendet Angebote (PDF im Friondo-Layout, KfW-Förderung,
Deckungsbeitrag, E-Signatur). Läuft lokal/on-prem.

## Rollen & Navigation
- Rollen: **Admin** (Benutzer verwalten inkl. Namen ändern, alles sehen),
  **Innendienst** (alles außer Benutzerverwaltung), **Außendienst** (nur Leads VOT
  eigene + Erfassung; nie Preise/EK/DB/Rabatt), seit v11 **Projektierung** und
  **Montage** (nur `/montage`), seit v12 **Leadmanagement**; Mehrfachrollen
  möglich (Details in den jeweiligen Abschnitten).
- Startseite: Friondo-Logo oben links; nur drei Shortcuts **Leads VOT · Erfassungen ·
  Angebote**; alle weiteren Punkte im Dropdown „Menü" oben rechts; darunter
  Statistik-Kacheln: Offene Leads · Offene Erfassungen · Versendete Angebote.
- Menüpunkt „Konfiguration" heißt jetzt **„Parametrierung"** (Logik-/Preislisten-
  Import, monday-Mapping, Nummernkreis, Förderparameter-Ansicht). Die Parametrierung
  (`/parametrierung`) ist seit v26 eine durchsuchbare Verteilerseite mit fünf
  Bereichskarten (Allgemein, Angebotstool, Projektierung, Lead-Management, System &
  Protokolle); Admin-Einträge (Benutzer, Projektierung-Einstellungen, Heizreport,
  Bestandsimport, Go-live, Kunden-Dubletten, Lead-Einstellungen, Lead-Demo) und die
  Lead-Karte erscheinen nur mit der jeweiligen Berechtigung, die Einstellungen der
  alten Übersicht liegen unter „Angebotstool-Einstellungen“ und „Logik & Importe“.

## Zentrale Dateien
- `konfigurator_logik_v5.xlsx` – Steuerdatei (ersetzt v4): zusätzlich Frage A13
  „Leitungslänge Hauseinführung ↔ WP-Inneneinheit" (immer; Pos. 103 × [Eingabe − 5 m, nie unter 0] – 5 m stecken in Pos. 006),
  SLS/ÜSS/APZ-Fragen komplett entfernt. 14 AMPEL-Gründe (Blatt Aktionen).
- `Artikel-Preislisten/Angebotserstellung Tool mit EK.xlsx` (WP-Preisliste),
  `Artikel-Preislisten/PV/` (PV-Positionslisten, v16), `Artikel-Preislisten/Klima/`
  (Ersatzangebot KL · Musterangebot KL – Klima-Positionen, v24), `ANGEBOTSTEXTE.md`,
  `anlagen/`, `Layout - Logo/`.
- `projektierung_logik_v1.xlsx` (Projektierung, v11+) und
  `leadmanagement_logik_v1.xlsx` (Lead-Management, v12; seit v23 zusätzlich die
  Blätter Objektarten und Status, Kaskade mit 5 Stufen, Gründe `verloren`).
- Betrieb (v27): `docs/betrieb.md` (Runbook, Ist-Aufnahme, Inventar),
  `docs/betrieb-it-uebergabe.md`, `docs/lasttest-v27.md`; Skripte
  `scripts/dienst-installieren.bat`, `dienst-neustart.bat`, `dienst-status.bat`,
  `dienst-entfernen.bat`, `waechter.ps1`, `health-pruefen.ps1`, `smoke.bat`/`smoke.py`,
  `restore-test.bat`, `lasttest.py`/`lasttest_server.py`, `index_pruefung.py`,
  `backup-nacht.bat` (nur Handläufe); `update.bat`, `rollback.bat --nur-code`.

## Plan ↔ CLAUDE-Version (Zuordnung)

Die Plan-Nummern und die CLAUDE-Versionen laufen seit v11 auseinander.
Phasennummern sind planübergreifend; ab Phase 94 werden nur noch freie
Nummern vergeben.

| CLAUDE | Plan-Datei | Phasen |
|---|---|---|
| v1–v2 | PLAN.md, PLAN_V2.md | 0–17 |
| v3–v10 | PLAN_V3.md … PLAN_V10.md | 18–63 |
| v11 | PLAN_PROJ_V1.md, PLAN_PROJ_V1b.md | 64–73 (kollidiert mit v13/v14) |
| v12 | PLAN_LEAD_V1.md | 73–82 |
| v13 | PLAN_V11.md | 64–68 |
| v14 | PLAN_V12.md | 69–74 |
| v15 | PLAN_PROJ_V2.md | 74–83 |
| v15-Nachtrag | Review 27.09.2026 (ohne Plan) | – |
| v16 | PLAN_V13.md | 75–81 |
| v17 | PLAN_PROJ_V4.md | 90–93 |
| – | PLAN_GESAMT.md (Orchestrierung), Doku-Bereinigung | 94 |
| v18 | PLAN_PROJ_V3_GOLIVE.md | 84–86 |
| v19 | PLAN_V14.md | 95–97 |
| v20 | PLAN_GESAMT.md B4 (Anschriften) | 98 |
| v21 | PLAN_LEAD_V1.1.md | 87–89 |
| v22 | PLAN_V15.md | 99–103 |
| v23 | PLAN_LEAD_V2.md | 104–112 |
| v24 | PLAN_V16.md | 113–117 |
| v25 | PLAN_LEAD_V3.md | 118–121 |
| v26 | PLAN_PROJ_V5.md | 122–126 |
| v27 | PLAN_V17.md | 127–132 |
| v27-Nachtrag 2 | PLAN_V17.md, Abschnitt „Nachtrag 06.10.2026“ (im Durchlauf v28/v29) | – |
| v28 | PLAN_PROJ_V6.md | 133–139 |
| v29 | PLAN_LEAD_V4.md | 140–144 |

## Fachliche Regeln (Änderungen v3)
- **Rabatt** (optional je Angebot, nur Innendienst/Admin): Betrag in € oder %,
  optionale Bezeichnung, keine Angebotsposition. Darstellung: Netto → 19 % USt →
  Gesamt-Betrag → **− Rabatt (brutto) → = Endbetrag**. KfW rechnet mit dem
  Endbetrag; der Deckungsbeitrag sinkt um den Netto-Anteil (Rabatt ÷ 1,19).
  Hinweis in docs/: Auf der späteren Rechnung (TAIFUN) ist der Rabatt vor der
  USt auszuweisen – die Angebots-Darstellung ist eine Brutto-Optik.
- **Deckungsbeitrag** in der Angebotsliste absolut in € mit Farbampel:
  unter 9.000 € rot · 9.000–10.000 € orange · über 10.000 € grün
  (Schwellen in der Parametrierung änderbar).
- **PDF-Nummerierung:** Positionen im Angebot werden fortlaufend neu nummeriert
  (001, 002, …) – Editor und PDF identisch. TAIFUN-Pos./Z-Nr./GUID bleiben intern
  gespeichert und sind im Editor als Zusatzinfo sichtbar.
- **Dachzentrale:** Bei alter Anlage im DG immer Pos. 163. D-Block (seit v13:
  Etagen-Frage D06) steuert 141 (gleiche Etage) bzw. 139/140 × Meter über die
  getrennten Abfragen D07/D08. Fassadenleitung bei OG, (DG und WP bleibt im DG)
  oder Dachaufstellung der Außeneinheit (N10); Erdleitung bei KG/EG oder
  (DG und WP zieht nach unten).
- SLS/ÜSS/APZ werden nicht mehr abgefragt – die Komponenten sind in Pos. 011
  enthalten; Pos. 149/150/153 bleiben ungenutzt im Artikelstamm.
- EK-Preise sind unter „Artikel bearbeiten" änderbar (Innendienst/Admin).
- **Löschen & Archiv (v5):** Benutzer sind löschbar, solange keine Vorgänge an
  ihnen hängen – sonst deaktivieren (Historie bleibt lesbar). Erfassungen sind
  löschbar (ID/Admin), außer ein Angebot ist verknüpft. Angebote: nur **Entwürfe**
  löschbar; versendete/abgelehnte werden **archiviert** (Aufbewahrungspflicht) und
  über den Filter „Archiv" erreichbar. Benutzer haben ein E-Mail-Feld (für CC).
- **Angebots-Editor (v5):** Positionen per Drag & Drop umsortierbar, Positions-
  nummern frei editierbar + Button „Neu durchnummerieren" (PDF folgt exakt).
  Einzelpreise je Position änderbar (interne Kennzeichnung „manuell geändert",
  Originalpreis als Tooltip; DB nutzt den geänderten Preis). Rabatt je Position
  (% oder €), wird im PDF sichtbar an der Position ausgewiesen und wirkt auf
  Summen, KfW-Basis und DB. Kennzeichen **„bauseits"** je Position:
  PDF zeigt „bauseits" statt Preisen, zählt weder in Summe noch DB.
- **Briefanrede im PDF-Vortext:** „Sehr geehrter Herr <Nachname>," bzw.
  „Sehr geehrte Frau <Nachname>,"; ohne eindeutige Anrede Fallback „Sehr geehrte
  Damen und Herren," – identischer Baustein als Platzhalter {briefanrede} in den
  Mail-Vorlagen.
- **Betrieb (v27, PLAN_V17 Phase 132 – verbindlich für jeden weiteren Plan):**
  - **Keine offene Datenbanksitzung während Netz-I/O** (monday, Graph/Outlook,
    Nominatim, openrouteservice, Heizreport, SMTP, HTTP allgemein): vor dem
    Netzaufruf alle Daten lesen, `db.verbindung_freigeben(session)` (Anfragen)
    bzw. Sitzung schließen (`with db.kurz() as s:` lesen → Netz → neue kurze
    Sitzung zum Zurückschreiben, Hintergrundläufe). Der Wächter-Test
    `tests/test_v27_sitzungen.py` prüft das per AST über ganz `app/` – Ausnahmen
    nur mit Kommentar `netz-ohne-sitzung-ok` und Begründung.
  - **Alle Endpunkte sind `def`-Routen** (Threadpool, `WORKER_THREADS`); Formulare
    über `anfrage.formular(request)`, JSON über `anfrage.json_lesen(request)`,
    Uploads über `datei.file` (Streaming) – kein `async def`/`await` in Routern,
    PDF-Erzeugung und Excel-Importe laufen nie in der Event-Loop.
  - **Jede neue Hintergrundaufgabe läuft über `app/scheduler.py`**
    (`scheduler.registrieren(...)` im `scheduler_starten()` des Moduls, kein
    eigener `threading.Thread`); kein Lauf hält eine Sitzung länger als 2 s ohne
    Netz-I/O, große Mengen in Blöcken mit Commit je Block (≤ 50 Datensätze).
  - **Importe nur außerhalb der Kernzeit**, in Blöcken mit Commit je 200 Zeilen,
    mit Hinweis und Bestätigung in der Parametrierung; laufende Importe stehen im
    Betriebs-Status (`betrieb.import_markieren`).
  - **Rollout nur im Wartungsfenster** (Dienstag 22:30–23:30) mit
    Wartungsbanner vorher, `update.bat` und `scripts\smoke.bat` danach; Hotfixes
    außerhalb nur mit Freigabe von Andreas. Datenbankänderungen bleiben additiv
    (Rückweg `rollback.bat --nur-code`).
  - **Jeder Plan mit neuen Netzaufrufen ergänzt das Inventar** in
    `docs/betrieb.md` (Modul, Auslöser, Intervall, Netzaufruf, Freigabe, Maßnahme).

## Neu in v6 (abgestimmt 21.08.2026)
- **Lead-Zuordnung:** Personen-Zuordnung wirkt sofort rückwirkend auf bestehende
  Leads; Matching zusätzlich über Benutzer-E-Mail; Warnhinweis bei Leads ohne AD.
- **Vertriebskanal** aus monday (Mapping je Board) an Lead/Kunde, Badge + Filter
  in allen Listen, Auswertung in der Statistik.
- **Archiv:** Erfassungen archivierbar; neuer Status **„Individuell“** für
  Erfassungen und Angebote (außerhalb des Tools geschrieben); seit v7 gilt
  die Statuskette aus „Neu in v7" statt Auto-Archiv. Versendete Angebote sind (ID + Admin) mit Sicherheitsabfrage
  löschbar; jede Löschung landet im Lösch-Protokoll (Parametrierung).
- **Angebotsliste:** Summenzeile Netto/Endbetrag/DB über die gefilterte Liste.
- **Editor:** Artikeltexte je Position editierbar (nur im Angebot), lange
  Beschreibungen aufklappbar statt abgeschnitten, EP-Kästchen je Position;
  Förderbetrag manuell überschreibbar (Kennzeichen „manuell“) und Förderblock
  im PDF ausblendbar.
- **Angebotsverfolgung:** Hot-Ampel (heiß/warm/kalt), Wiedervorlage-Datum
  (Startseiten-Kachel „fällig“), Notizen-Verlauf (append-only).
- **Statistik-Seite:** Zeitraumwahl, Kennzahlen gesamt/je AD/je Kanal,
  Abschlussquote; Außendienst sieht nur die eigenen Zahlen.
- **E-Mail:** Versand als HTML; Vorlagen-Editor mit Formatierung (fett usw.);
  je ID-Benutzer die echte Outlook-Signatur (Upload .htm + Bilder, Inline-CID)
  1:1 unter dem Entwurf.

## Neu in v7 (abgestimmt 24.08.2026)
- **Startweiche der Erfassung** (nach Kundenwahl): „Erfassungsbogen starten" oder
  „Freitext-Erfassung" (großes Pflicht-Textfeld). Freitext setzt die Ampel sofort
  auf Individuell (Grund „vom Außendienst als individuell erfasst") und geht ohne
  Vorprüfung direkt in die TAIFUN-Warteschlange. Im Katalog jederzeit Button
  „In Freitext wechseln" – bereits gegebene Antworten bleiben im Protokoll.
- **Statuskette für Individuell-Fälle** (ersetzt das v6-Auto-Archiv):
  „Individuell – zu prüfen" (Katalog-Fälle mit oranger Ampel) → Buttons „Doch
  konfigurierbar" (Antworten korrigieren, normaler Tool-Weg) oder „Individuell
  bestätigt" → „In TAIFUN zu schreiben" (sichtbare Arbeitsliste + Startseiten-
  Kachel „Individuell offen") → „Extern erledigt" → Erfassung „Erledigt (extern)";
  Archiv erst manuell (seit v8). Das Protokoll-PDF ist der Übergabezettel für TAIFUN.
- **Externe Angebotseinträge:** „Extern erledigt" fragt TAIFUN-Angebotsnummer
  (optional, nachtragbar – Badge „Nummer fehlt"), Endbetrag brutto (Pflicht) und
  Datum ab und erzeugt einen Eintrag in der Angebotsliste mit Badge „TAIFUN":
  ohne PDF/Editor/Versand, aber mit monday-Rückspielung (Deal-Status + Deal-Wert),
  Verfolgung (Ampel/Wiedervorlage/Notizen) und Statistik. Die Statistik weist
  Tool-, TAIFUN- und Gesamt-Angebote getrennt aus.
- Fotos in der Erfassung: bewusst zurückgestellt (späteres Thema für alle Wege).

## Neu in v8 (abgestimmt 28.08.2026)
- Multi-Sparten: Ein Lead kann mehrere Interessen (WP/PV/KL/WB) haben;
  je Sparte eine eigene Erfassung mit Status-Chips am Lead. Der Lead
  verlässt „Leads VOT" erst, wenn alle Interessen erfasst oder
  ausgeblendet sind. Sparten-Auswahl beim Erfassungsstart
  (Lead-Interessen vorausgewählt); je Sparte Weiche Katalog/Freitext,
  WB vorerst immer Freitext. PV/KL sind reine Erfassungsformulare
  (Blätter „Fragen PV" / „Fragen KL", ohne Artikel-Aktionen; PV ist seit v16,
  KL seit v24 ein vollwertiger Konfigurator – siehe dort) und laufen
  über die TAIFUN-Schiene; Sparten-Badge an Erfassung, Warteschlange,
  externem Angebotseintrag und in der Statistik.
- WP-Bogen: Heizlast-Abfrage (entscheidet bei Bekanntsein über das
  Paket, Unterdimensionierungs-Matrix in der Paketmatrix; kWh bleibt
  Pflicht fürs Protokoll); Rechnungs-/Ausführungsanschrift getrennt
  (monday-Adresse = Ausführungsort); Unterverteilung (Pos. 152) mit
  MID-Zwischenzähler (Z23); Wärmemengenzähler Pos. 096 × Anzahl bei
  mehr als einer WE; Stemmarbeiten Pos. 126 im Öl-Zweig; Abschluss-
  Seite „Einschätzung" mit Hot-Ampel + Wiedervorlage (Startwerte der
  Verfolgung).
- Angebote: Verfolgungs-Block oben im Editor; Förder-Editor
  baustein-basiert (Grundförderung, Klima-Bonus, Einkommensbonus,
  Höchstkosten einzeln überschreibbar, Kennzeichen „manuell
  angepasst"); Drag & Drop ohne Scroll-Sprung, mit Auto-Scroll;
  Vollmacht-Häkchen wieder leer; Kunden-Nr. entfällt im Briefkopf;
  PDF zeigt Rechnungsanschrift im Empfängerfeld und abweichenden
  Ausführungsort als eigene Zeile.
- Rollen: Außendienst sieht „Meine Angebote" (read-only, Kundenpreise
  und PDF, ohne EK/DB/Editor/Versand).
- Abgelehnt-Prozess: Pflichtdialog „Grund der Ablehnung" (Auswahlliste
  aus Parametrierung + Freitext) für Tool- und TAIFUN-Angebote;
  Statistik-Auswertung „Ablehnungsgründe"; täglicher Prüflauf setzt
  versendete Angebote ohne Annahme/Ablehnung nach 90 Tagen
  (Parametrierung) auf Abgelehnt mit Grund „90 Tage Ablauf" –
  außer eine Wiedervorlage liegt in der Zukunft.

## Neu in v9 (abgestimmt 29.08.2026)
- Angebotsprofile (Standard / Enni / SWD / Sparkasse DU) bündeln je
  Vertriebskanal: Nachtext-Block, Positionsregeln und Versandregeln.
  Auto-Auswahl über den Kanal des Leads (Zuordnung Kanalwert → Profil
  in der Parametrierung, Fallback Standard), am Angebot manuell
  umschaltbar mit Konsistenz-Hinweis. Nach- und Vortexte sind
  editierbare Textblöcke in der Parametrierung.
- Enni: nur HEMS-Frage (P02/P03 entfallen im Bogen); HEMS = Ja →
  Pos. 015 zum Sonderpreis 599 € (kein 014) + Pos. 162 automatisch;
  keine Vollmacht; Versand zusätzlich CC energieberatung@enni.de.
  SWD: P01–P03 nur Protokoll (keine 014–017, keine Vollmacht);
  Empfängerfeld beim Versand leer (ID trägt SWD-Kontakt manuell ein).
  Sparkasse DU: nur eigener Nachtext. BCC-Feld akzeptiert mehrere
  Adressen (kommagetrennt).
- Neue Leistungsklasse 15 kW (Serie CS8800i): Verbrauch 31.001–37.000
  kWh bzw. Heizlast 16,0–18,5 kW; Farbwahl Außeneinheit (030 weiß /
  031 schwarz); Inneneinheit aus Pufferwahl abgeleitet (70 l → AWMB
  055; 200/300/500 l → AWE 056 + externer Puffer); Warmwasser fix
  über Pos. 065. Pos. 067 kommt automatisch bei jedem AWM-Paket
  (045–049) – einzige Quelle: Paketmatrix.
- Solarthermie ist konfigurierbar: „stilllegen" → Z24 (0 €, Rückbau
  im Heizungsraum); „übernehmen" → AWE-Paket + Pos. 069 (bivalenter
  390-l-Speicher) statt 065/067, WW-Größenfrage entfällt; Widerspruch
  „Übernahme, aber WW über WP = Nein" erzeugt einen fachlichen
  Hinweis am Vorgang (069 übersteuert). Noch 14 eindeutige AMPEL-Gründe.
- Angebots-Versionierung: Button „Überarbeiten" an versendeten/
  angenommenen Angeboten erzeugt Version .2/.3 … als Entwurf;
  Original erhält Status „Überholt" (zählt nicht mehr in Statistik,
  Summen, 90-Tage-Lauf); PDF trägt „Ersetzt Angebot … vom …";
  monday-Deal-Wert folgt der neuen Version.
- Bedingte Angebotsvermerke (neues Logik-Blatt „Vermerke"): erster
  Vermerk „Heizungsumverlegung DG → Keller" bei A04 = DG und
  D01 = Nein. MFH-Förderaufschlüsselung weist Klima- und
  Einkommensbonus getrennt aus (Rechenlogik unverändert korrekt).
  Freitext von Erfassungen nachträglich editierbar (auch AD bei
  eigenen), Vertriebskanal manuell änderbar (Vorrang vor Sync),
  Sparten-Chips mit Zustandsanzeige, Startseite in drei Bereichen
  (Lead-Management · Angebotstool · Projektierung).

## Neu in v10 (abgestimmt 05.09.2026)
- Kundenvorgänge: Jeder Lead ist ein Vorgang mit eigener Akte –
  sie bündelt Sparten-Chips, alle Erfassungen, alle Angebote
  (Tool/TAIFUN, inkl. Versionen), Mail-Verlauf, Verfolgung und
  einen chronologischen Notizen-Chat (*seit v28 die einzige Notizspur Lead → Montage
  über das Makro `notizen_chat`, Rechte erweitert um Projektierung/Leadmanagement,
  Montage nur lesen – siehe v28*; Autor + Zeitstempel,
  Einträge unveränderlich; AD bei eigenen Vorgängen, ID/Admin
  überall). Verfolgung (Hot-Ampel, Wiedervorlage) lebt auf
  Vorgangsebene – EINE Ampel je Kundenanfrage; Angenommen/
  Abgelehnt bleibt je Angebot. Der 90-Tage-Lauf respektiert die
  Vorgangs-Wiedervorlage für alle Angebote des Vorgangs.
- Kombi-Versand: Aus der Akte mehrere versandfertige Angebote in
  EINER Mail versenden (mehrere separate PDFs). Kombi-Vorlage mit
  {angebotsliste} (je Angebot Sparte + Endbetrag, WP zusätzlich
  Eigenanteil) – Einzelbeträge, keine Gesamtsumme. Broschüren
  dedupliziert. Die Versand-Erkennung setzt alle enthaltenen
  Angebote auf „Versendet"; der Mail-Verlauf hängt an allen.
- Externe TAIFUN-Einträge können übergangsweise ein PDF tragen
  (Upload am Eintrag), damit Kombi-Mails alle Angebote enthalten.
- Alternativ-Kennzeichen je Position: „in anderem Angebot enthalten"
  – Darstellung wie EP (ausgewiesen, nicht in Summe/KfW/DB) mit
  automatischem Vermerk und Verknüpfung zum Geschwister-Angebot des
  Vorgangs. Parametrierungs-Liste „gewerkeübergreifende Artikel"
  löst bei Mehr-Sparten-Vorgängen einen fachlichen Hinweis aus;
  der Kombi-Versand warnt bei doppelt voll berechneten Artikeln
  (nur zwischen Tool-Angeboten prüfbar).
- monday: Deal-Wert = Summe aller versendeten, nicht überholten
  Angebote des Vorgangs (aktualisiert bei Versand, neuer Version,
  Ablehnung). Statistik zusätzlich je Vorgang (Kombiquote,
  Auftragswert je Vorgang) und als Monatsübersicht Auftragseingang
  (angenommene Angebote), filterbar.
- Außendienst-Ausbau: Suche in „Meine Angebote"; vollständige
  Angebotsansicht der eigenen Angebote (weiterhin ohne EK/DB);
  AD kann den Gesamtrabatt selbst setzen, solange die DB-Ampel
  nicht rot wird – darunter Freigabe-Anfrage an den Innendienst.
  Wiedervorlagen haben einen Verantwortlichen: vom AD gesetzte
  erscheinen in dessen Sicht, nicht in der ID-Kachel.

## Leads VOT (monday-Lesesync)
- Quellen (friondo-gmbh.monday.com), jeweils NUR die Gruppe mit Titel „Terminiert"
  (Gruppe über den Titel finden, nicht über die ID – robust bei Board-Kopien):
  1. Workspace „Blinno Working Space" (5217202) → Board „Deals" (ID 5080725439;
     Gruppe „Terminiert" dort = group_mkzb5f0e)
  2. Workspace „Pool Working Space" (5578078) → Board „Deals - Simon" (ID 5089971526)
  3. Workspace „Pool Working Space" (5578078) → Board „Deals - Rene" (ID 5092657267)
  Quellenliste in der Parametrierung pflegbar (Board + Gruppentitel je Zeile).
- Spalten-Mapping je Board über Zuordnungsseite in der Parametrierung (Dropdowns,
  Spalten live von monday geladen): VOT-Datum, **„Verantwortlicher"** (Personen-
  Spalte → AD-Mitarbeiter), Anrede/Vorname/Nachname, Adresse, PLZ, Ort, Telefon,
  E-Mail, Status. Zuordnung monday-Person ↔ Tool-Benutzer.
  **Sonderregel „Deals - Rene": Verantwortlicher ist immer Rene Golaschewski**,
  auch wenn die Spalte leer ist. Derselbe Kunde in mehreren Boards → deduplizieren.
- **Interesse (v5):** Mehrfach-Feld WP / PV / KL / WB an Lead und Kunde, aus einer
  monday-Spalte gemappt; Badges + Filter in Leads VOT, Erfassungen und Angeboten.
  Jeder Vorgang trägt zudem einen **Konfigurator-Typ** („WP" oder – seit v16 –
  „PV") als Unterbau für weitere Konfiguratoren (Klima folgt).
- Sync: alle 15 Minuten + Button „Jetzt aktualisieren"; nur lesend, Fehler
  blockieren das Tool nie.
- Liste „Leads VOT": nur Leads **mit** VOT-Datum und **ohne** verknüpftes Angebot,
  chronologisch nach Termin; Außendienst sieht nur eigene, Innendienst/Admin alle.
  Filter und Sortierung nach Termin, Vertriebler und Status.
- Der Sync legt **alle** Leads sofort als Kunden an bzw. aktualisiert sie
  (Duplikatabgleich Name + PLZ). Klick auf Lead → Fragenkatalog mit vorausgewähltem
  Kunden. Nach Absenden gilt der Lead als erfasst und verschwindet aus der Liste
  (Verknüpfung Lead ↔ Erfassung ↔ Angebot speichern).

## E-Signatur
- Jedes Angebots-PDF erhält die Unterschriften-Seite wie bisher; zusätzlich digitales
  Signieren: **Vor-Ort-Modus** (sofort aktiv): Innendienst/Außendienst öffnet
  „Signieren", Kunde unterschreibt auf dem Touchscreen; Signaturbild + Name +
  Zeitstempel werden in das PDF eingebettet, Status → „Angenommen", signierte Datei
  separat unter data/angebote/signiert/ abgelegt, Signaturprotokoll (Zeit, Gerät,
  Benutzer) am Angebot.
- **Fern-Modus** (Ziel v4): Der Kunde signiert selbst von zu Hause über einen
  Token-Link aus der Angebots-Mail (Gültigkeitsdauer, Einmal-Token, Protokoll).
  Voraussetzung: öffentliche HTTPS-Adresse ausschließlich für die Signatur-Route
  (RZ/IT) oder ein externer Signatur-Anbieter – Entscheidung offen, Modul wird
  fertig gebaut und per Schalter aktiviert.

## E-Mail-Versand, Vorlagen & Verlauf (v5)
- Versand über Graph aus dem Postfach des angemeldeten ID-Mitarbeiters, Absender
  ist immer **angebot@friondo.de** („Senden als"-Berechtigung durch M365-Admin;
  Graph-Berechtigungen um Shared-Mailbox-Zugriff erweitern, docs/graph-einrichtung.md
  fortschreiben).
- Automatisch: **CC = Außendienstler des Vorgangs** (E-Mail aus der Benutzer-
  verwaltung; fehlt sie, Entwurf ohne CC + Hinweis), **BCC** aus der Parametrierung
  (Standard info@friondo.de).
- **Vorlagen:** Standard-Vorlage für Betreff + Text plus optionale Vorlage je
  Außendienstler (greift automatisch nach AD des Vorgangs) – *ergänzt seit v27-Nachtrag 2:
  zusätzlich Vorlage je Sparte WP/PV/KL/WB, Reihenfolge AD → Sparte → Standard*. Platzhalter: {anrede},
  {vorname}, {nachname}, {angebotsnummer}, {endbetrag}, {eigenanteil}, {foerderung},
  {gueltig_bis}, {vertriebler}, {absender}. Pflege durch Admin/Innendienst in der
  Parametrierung, mit Vorschau; bisheriger Festtext wird als Standard migriert.
- **Status-Automatik:** „Versand vorbereiten" setzt Status **„Versand vorbereitet"**;
  Graph erkennt den tatsächlichen Versand (Gesendete Elemente/Konversation) und
  stellt automatisch auf **„Versendet"** – erst das löst die monday-Rückspielung aus.
- **Mail-Verlauf:** Kundenantworten laufen im Postfach angebot@friondo.de auf und
  werden per Konversation bzw. Betreff AN-C-… dem Angebot zugeordnet (Abruf alle
  15 Min); Angebotsliste zeigt ein Brief-Symbol, Klick öffnet den Verlauf.

## monday-Rückspielung (v5)
Sobald ein Angebot auf „Versendet" wechselt, wird der Quell-Deal aktualisiert:
Status „Angebot versendet" (konfigurierbar als Status-Spaltenwert ODER Verschieben
in eine Zielgruppe) und Deal-Wert = Endbetrag (Zielspalte per Dropdown, brutto oder
netto wählbar). Fehler blockieren nie – Warnung am Angebot mit Wiederholen-Button,
alle Rückspielungen werden protokolliert.

## Unverändert aus v2
Stack (FastAPI/SQLite/fpdf2), TAIFUN-Import mit GUID-Anker und Textregeln,
Fragebogen mit Seiten + AMPEL, Erfassungsliste, Nummernkreis AN-C-<JJ><NNNN>,
EP-Regel, Decimal/Cent, 19 % USt, KfW-Modul mit Testfällen gegen den HTML-Rechner,
PDF nach Referenz AN250096, Vollmacht nur bei iMSys/SpotDynamic, Anhänge-Bibliothek,
Graph-Versand über Innendienst, Terminal-Server-Betrieb.

## Neu in v11 – Projektierung V1 (abgestimmt 22.09.2026)

(Plan: PLAN_PROJ_V1.md + PLAN_PROJ_V1b.md)

- **Projektierung V1:** Projekt = Bauvorhaben am v10-Vorgang (höchstens ein
  offenes Projekt je Vorgang, Nummer PR-JJNNNN) mit Gewerken je Sparte WP/PV/KL/WB; jedes Gewerk hat eigene Phase
  (*überholt – gültige Phasen siehe v17*), Aufgaben, Termine, Auftrag
  (angenommenes Angebot, folgt Versionen). Button „Angebot → Projekt" an
  Angeboten „Angenommen" (Tool + TAIFUN, auch in der Vorgangsakte) mit Vorschlag
  „zu offenem Projekt des Vorgangs hinzufügen"; Vorgangsakte zeigt den Projektstand. Projektstatus abgeleitet vom am wenigsten fortgeschrittenen
  offenen Gewerk.
- **Aufgabenpakete** aus `projektierung_logik_v1.xlsx` (Blätter Aufgabenpakete,
  Paketregeln, Ordnerstruktur, Sub-Typen), Import in der Parametrierung.
  Fälligkeitsregeln `+N`, `FP+N`, `M-N`. Planungs-Ampel = Pflichtaufgaben-Stand.
  Wächter je Phasenwechsel, Override mit Begründung protokolliert (*überholt – seit v28
  Modus `waechter_modus`, Standard warnen: offene Punkte blockieren nicht, Begründung
  optional; sperren = Override mit Begründung – siehe v28*).
- **Oberfläche:** Kanban (Karte = Projekt, Gewerk-Chips), Liste, Terminübersicht,
  Projektakte mit Gewerk-Spalten nebeneinander, Dokumente in Ordnerstruktur
  `data/projekte/<PR>/`, Verlauf + Kommentare mit @Erwähnung, Glocke +
  Mail-Benachrichtigung (aus/sofort/digest), „Meine Aufgaben".
- **Rollen:** neu Projektierung (keine EK/DB außer Häkchen „Kalkulation
  sichtbar", keine Angebotserstellung) und Montage (nur `/montage`: Meine
  Einsätze, Steckbrief, Fotos, Montage gestartet/fertig); Mehrfachrollen;
  Teams und Subunternehmer als Stammdaten; Außendienst sieht Projektstand
  read-only am eigenen Angebot.
- **Demo-Modus:** Parameter `freigabe_modus` (admin / alle, Standard admin):
  bei admin ist das gesamte Modul nur für Admins sichtbar und aufrufbar
  (server-seitig), Startportal-Karte trägt Badge „Demo · Coming soon", andere
  Rollen sehen Null-Kacheln und „Das Modul befindet sich im Aufbau."
- **Storno** mit Pflichtgrund setzt Angebot auf Abgelehnt. **Rechnung
  freigeben** mit Restarbeiten-Pflichtfrage → Abgeschlossen. Migration legt für
  alle angenommenen Angebote Projekte an. Absender Projekt-Mails
  `projektierung@friondo.de` (Fallback angebot@).
- *Roadmap überholt:* Feinplanung, Sub-Mails, Kalender, Montage-Formulare
  und Collin-UGL kamen mit v15; „Projektierung V4" (v17) ist Board/BzA/UGL-
  Feinschliff, V3 (v18) der Go-live. Rechnungen/OP/Mahnwesen und
  SpotmyEnergy-Anbindung sind **nicht gebaut**.
- Oberfläche der Projektierung folgt der Design-Vorlage
  `docs/projektierung-prototyp.html` (CSS-Präfix `pj-`); spätere Änderungen am
  Modul-Layout zuerst im Prototyp, dann im Tool.

## Neu in v12 – Lead-Management V1 Demo (abgestimmt 22.09.2026)

> Hinweis v25: Score, Score-Klassen und der Qualifizierungsbogen sind seit v25
> abgeschaltet (Parameter `score_aktiv = aus`); die Blätter Qualifizierung/
> Scoring/Klassen bleiben in der Steuerdatei liegen, Daten bleiben in der DB.

(Plan: PLAN_LEAD_V1.md)

- **Lead-Management V1 (Demo):** Lead = Vorgang (v10) mit Lead-Phase
  (Neu · In Kontaktierung · Qualifiziert · Terminiert · danach abgeleitet
  Erfasst/Angebot/Gewonnen/Verloren; Seitenzustände Zurückgestellt · Nicht
  erreicht · Unqualifiziert), Quelle/Kampagne/UTM, Eingang, SLA, Score (A/B/C),
  Leadmanager, Wunschzeiten, Koordinaten, Einwilligungen. Gesyncte monday-Leads
  erhalten die Phase abgeleitet (Badge „monday"); **monday-Sync und -Rückspielung
  unverändert**.
- **Demo-Modus:** Parameter `lead_freigabe_modus` (admin / alle, Standard admin):
  bei admin sind alle Routen unter `/lead-management` (`app/routers/leadmanagement.py`),
  Menüpunkte, Reiter, Kacheln nur für Admins (server-seitig, 404 für andere);
  `/leads` bleibt die Liste „Leads VOT", `POST /api/leads` ist nicht
  Admin-gesperrt, sondern per API-Key je Quelle geschützt; Startportal-Karte
  „Lead-Management" trägt das Badge „Demo · Coming soon". Im Modul angelegte Leads
  tragen `demo = 1` und erscheinen in keiner bestehenden Liste/Statistik/Kachel/
  Rückspielung; Umstellung auf `alle` fragt: Demo-Leads löschen oder behalten.
  Sperren im Demo-Modus: `mail_modus` nur protokoll/test (live abgewiesen),
  `kalender_sync` nur ins Testpostfach, monday-Leads nicht buchbar.
- **Eingang:** Schnellanlage, CSV/Excel-Import mit Spaltenzuordnung, `POST
  /api/leads` (API-Key je Quelle), Mail-Parser mit Regeln + Test (Abruf nur bei
  `parser_modus = an`), Formular-Standard `[LEAD] <quelle> <kampagne>` + `Feld: Wert`,
  „Posteingang unklar", Duplikatprüfung (Telefon E.164, E-Mail, Name+PLZ, Adresse)
  mit Anhängen an offenen Vorgang, Demo-Daten-Generator.
- **Terminierung:** Anrufliste priorisiert (SLA → fällig → zurückgestellt → Score),
  Ein-Klick-Anrufergebnisse, Wiedervorlage-Kaskade und Gründe aus
  `leadmanagement_logik_v1.xlsx` (Blätter Qualifizierung, Scoring, Klassen, Kaskade,
  Gruende, Wunschzeiten; Import in der Parametrierung), Qualifizierungsbogen je
  Sparte mit Live-Score und Vorbelegung des Erfassungsbogens über `erfassungs_frage`
  (aktiv erst bei `alle`).
- **Terminassistent:** Top-5-Slots (*überholt – seit v29 genau drei Vorschläge, der erste
  „Ideal“, Parameter `vorschlaege_anzahl`*) über AD-Profile (Startadresse, Arbeitszeiten,
  Dauer/Puffer/Max), Tool-Termine (`vot_termine`, auch aus monday-VOT-Datum),
  optional Outlook-Frei/Belegt (Graph, `kalender_sync`), Fahrzeiten
  (`routing_anbieter` ors / google / luftlinie, Caches), Bewertung Umweg +
  Wunschzeit/Tour-Tag/Randzeit; Buchen schreibt Termin, Outlook-Ereignis (falls an),
  Bestätigung + Erinnerung; Umbuchen, No-Show (Lead zurück auf Qualifiziert),
  Terminkalender Woche je AD, Karte (Leaflet lokal, OSM-Kacheln), „Adresse prüfen".
- **Kommunikation:** Vorlagen eingangsbestaetigung / nicht_erreicht /
  terminbestaetigung (ICS) / terminerinnerung (−24 h) / terminaenderung / nurture
  (nur mit Einwilligung), Warteschlange + Versand-Job, `mail_modus` protokoll / test /
  live, Reiter Kommunikation in der Akte, Absender `leads@friondo.de` (Fallback angebot@)
  (*überholt – seit v29 Absender aller Lead-Mails `absender_lead_mails` = termin@friondo.de
  ohne Fallback, leads@ nur Eingang; Vorlage nurture entfällt; Lead-Glocken nur To-Dos*).
- **Oberfläche:** Anrufliste, Pipeline-Kanban, Lead-Akte (Vorgangsakte + Kopfblock
  Lead + Reiter Aktivitäten/Qualifizierung/Termin/Kommunikation), Kalender, Karte,
  Cockpit, Statistik-Reiter „Leads" (Trichter, Speed-to-Lead, Quoten, Gründe),
  Kanal-Report (Kosten je Lead/Termin/Auftrag), Pipeline-Wert.
- **Rollen:** neu `leadmanagement` (Mehrfachrolle; keine EK/DB, kein Angebots-Editor),
  AD-Profile in der Benutzerverwaltung, AD-Sicht Lead-Akte read-only + No-Show/
  Verschieben – alles erst bei `alle` wirksam. Löschlauf (`loeschlauf`, Frist
  `loeschfrist_monate`, Anonymisierung) mit Vorschau.
- Geplant: V2 monday-Import + Parallelbetrieb, SMS, Tourenplanung Tag + „Leads in
  der Nähe", Gebietskarte, KI-Extraktion (Schalter), CTI, Webhook extern; V3
  Online-Terminwahl, WhatsApp, Cross-Selling-Trigger, Score-Kalibrierung; V4
  KI-Sprachschicht, Voice-/Chat-Vorqualifizierung.

## Neu in v13 – Team-Feedback (abgestimmt 23.09.2026)

(Plan: PLAN_V11.md; die Zählung v11/v12 war zu diesem
Zeitpunkt bereits durch Projektierung und Lead-Management belegt.)

- Kalkulation: Der 50-l-Puffer bleibt eine eigene Position (Z15,
  Entscheidung 23.09.2026); die doppelte DARSTELLUNG ist behoben, indem
  eine Textregel die Pufferzeile aus den Pakettexten 045–054 entfernt
  (Blatt „Textregeln", neue Regelform „Positionen 045–054" + „Zeile '…'
  aus der Beschreibung entfernen" – greift bei jedem Re-Import).
  Kontrollwerte unverändert (Netto 30.245,43 €).
  CS8800: Außen-/Inneneinheit stehen auf Position 1+2, eigene
  Broschüren-Regel (Bosch CS8800iAW.pdf bei 030/031), Fehlerfall „Klasse 15
  ohne Paket" behoben (Angebot-erzeugen prüft auf offene Fragen).
- Konfigurator: Auslegung ohne Verbrauch über Fläche × Gebäudestandard
  (40/60/70 W/m², Fragen A17/A18 nach A03 = „Verbrauch unbekannt") mit
  ausgewiesener Herleitung im Protokoll; Auslegungszeile in Block 1
  (0,00 €, Wortlaut vorläufig bis TAIFUN-Muster); Fassadenleitung auch bei
  Dachaufstellung (N10); Kran-Frage N09 statt EP-Automatik;
  Tankgrößen-Nachfrage A19 ab 9.000 l; Dachzentrale-KG-Kette mit
  Etagen-Frage D06 und Meterabfragen D07/D08 (139 = Heizung, 140 =
  Warmwasser laut Artikeltexten); Vermerk Heizungsumverlegung als
  0,00-€-Position Z25 (nach Zulieferung auf TAIFUN-Pos. 124 umstellen);
  Erdleitung im Fundament-Block (Block 6, seit v10); Blocküberschrift
  „Elektroarbeiten" (Block 7).
- Editor: Freitextpositionen ohne Bezeichnung und mit EK-Feld (netto, nur
  für den DB); abweichende Lieferanschrift (Erfassungsfrage O13, Feld im
  Editor, eigene PDF-Zeile); „Für anderen Kunden kopieren" (Zielkunde
  wählen/anlegen, neuer Vorgang, Kennzeichen „Kopie von AN-…" +
  Warnblock „Förderdaten prüfen (kopiert)"). Zusatzartikel Z26
  „Elektroarbeiten – im PV-Angebot enthalten" (0,00 €) kommt beim
  Einfügen automatisch als Alternativ-Position mit Verknüpfung
  „PV-Angebot".
- Rollen: AD setzt eigene Angebote auf Angenommen/Abgelehnt/Offen
  (Grund-Pflicht, Notiz-Protokoll im Vorgangs-Chat, monday/Statistik wie
  beim ID). Externe Einträge vollständig ablehnbar (bestand schon, per
  Test abgesichert).
- Versand: Anhänge-Regeln profilabhängig (Spalte „Nicht bei Profil":
  Enni/SWD ohne Ratenkauf/SpotDynamic); Versand-Erkennung robuster
  (Benutzer-Postfächer zählen als eigene Absender) mit Protokoll der
  Prüfläufe in der Parametrierung + Button „Als versendet markieren" mit
  Protokoll-Notiz; Rabatt mit 0 oder leerem Feld entfernbar (ID und AD).
- Offen bis Zulieferung: monoenergetische Klassengrenzen (Paketmatrix),
  VK-Preisliste (Janni), Bosch-CS8800iAW-Broschüre (anlagen/),
  TAIFUN-Wortlaute (Auslegungszeile, Pos.-124-Text).

## Neu in v14 – Design-Update (abgestimmt 24.09.2026)

(Plan: PLAN_V12.md; die Zählung v12 war bereits durch das
Lead-Management belegt.)

- Reines Design-Update, keine Funktionsänderungen: zentrales
  Design-System (CSS-Tokens in style.css, Komponenten-Baukasten, lokale
  SVG-Icons in `_symbole.html`, gemeinsame Makros in
  `_komponenten.html`: status_badge · statuskette · wiedervorlage_chip
  · leer_zustand; Dokumentation in docs/design-system.md). Keine
  externen CDNs/Webfonts – alles lokal.
- Überarbeitet: Portal, Angebotstool-Startseite (Icon-Kacheln,
  dringliche Zahlen rot), alle Listen (Filterleiste als Karte mit
  Chip-Selects, Sticky-Tabellenkopf, Zebra + Hover, EIN
  Status-Badge-Schema, kompakte Icon-Aktionen, dunkle Summenzeile),
  Vorgangsakte (Kundenkopfkarte mit Hot-Ampel + Wiedervorlage-Chip,
  zweispaltig, Angebots-Karten mit Status-Schrittleiste,
  Notizen-Chat-Optik mit eigenen Einträgen rechts – *seit v28 gemeinsames Makro
  `notizen_chat`*), Angebots-Editor
  (Kopfkarte mit Schrittleiste, abgesetzte Blocküberschriften, sticky
  Aktionsleiste unten), Parametrierung/Statistik, mobile Erfassung
  (Seite x von y + Balken, Frage-Karten, sticky Weiter-Leiste,
  Einschätzung als große Buttons, PWA-Manifest + theme-color).
- Bestands-Bugfix: `td.aktionen` fiel durch `display:flex` aus dem
  Tabellenlayout (Aktions-Buttons standen seit v6 versetzt neben den
  Listen) – jetzt table-cell.
- Angebots-PDF unverändert. Künftige Module bauen auf den Tokens auf;
  Screenshots vorher/nachher unter docs/design-v12/, Screenshot-Helfer
  scripts/design_screenshots.py (Playwright + lokales Chrome).

## Neu in v15 – Projektierung V2 (abgestimmt 26.09.2026)

(Plan: PLAN_PROJ_V2.md)

- Kanban-Phasen (*überholt – „Abnahme & Freigabe" ist seit v17 in
  `abnahme` und `freigabe` getrennt*): Auftragseingang · Feinplanung VOT ·
  Planung · Montagevorbereitung · Montage · Abnahme & Freigabe ·
  Abgeschlossen · Storniert; Terminstatus je Gewerk (terminiert / unbestätigt /
  unterminiert) als Badge; Sichten Board | Kalender | Chronologisch.
- Teams: Montageteam 1–10, Subteam 1–5 (Stammdaten, Farbe, Outlook-
  Kalender); Zuweisung am Gewerk (WP-/Elektro-/Sub-Team) und je Termin (*ergänzt v28:
  das Team ist nur die Vorlage, die Mannschaft steht je Termin in der Besetzung
  `termin_besetzung`; EIN Termin-Dialog für alle Terminarten – siehe v28*);
  Kalender mit Balken über die Projektdauer (Standard 1 Woche), Drag,
  Konfliktwarnung; Outlook-Sync über Graph in beide Richtungen.
- Galerie am Vorgang mit festen Ordnern (*Ordnerliste überholt – seit
  27.09. Galerie je Sparte + Ordner „Förderung", siehe unten*), Upload mobil per Kamera für Vertrieb (auch ohne
  Auftrag), Planung und Montage; Projektakte zeigt dieselbe Galerie (*seit v28 Lightbox
  mit Vor/Zurück, Bilder inline, Download nur über den Knopf – siehe v28*).
- Projektsteckbrief über den To-dos (Hersteller, Leistungsklasse,
  Innengerät, Zählerschrank, Öltank, Aufstellort, Tarif/iMSys/HEMS,
  Folierung …), abgeleitet über Logik-Blatt „Steckbrief", editierbar.
- Aufgabenpakete v2 mit Aktionstypen (Häkchen, Auswahl, Link, Mail,
  Formular, Kalender, Galerie, API) und Fristen; Pakete Auftragseingang ·
  Feinplanung VOT · Planung WP · Planung Elektro · Friondo Fit for Future ·
  Montagevorbereitung · Abnahme & Freigabe (*überholt: seit 27.09. ohne
  Paket „Förderung", BnD unter Abnahme; seit v17 Pakete Abnahme und
  Freigabe getrennt*); Restarbeiten-Liste je Gewerk.
- Sub-Beauftragung per Mail aus der Aufgabe (Vorlagen je Sub-Typ,
  Fotos aus Galerie-Ordner, Steckbrief-PDF), Absender projektierung@.
- Feinplanungs-Erfassung WP (Blatt „Fragen FP-WP", vorbelegt aus der
  Vertriebs-Erfassung), Heizreport-Link/Upload (API vorbereitet),
  UGL-Bestelldatei für Collin aus Stücklisten (Blatt „Stücklisten",
  Artikelstamm-Feld Lieferanten-Artikelnummer), Portal-Links (BzA,
  SpotmyEnergy, Heizreport, GC Online Plus), BzA-Datenblatt mit
  Kopier-Buttons.
- Montage-Backend `/montage` (*überholt – seit v28 Besetzungs-Sicht „Meine Einsätze“,
  neue Reihenfolge der Auftragsseite, Montage starten/beenden, Formulare v28 – siehe
  v28*): Team-Auswahl, chronologische Liste,
  Wochenkalender, Auftragsdetail mit Steckbrief und Galerie,
  Montagebericht · Inbetriebnahmeprotokoll · Abnahmeprotokoll (Felder im
  Blatt „Formulare", PDF in Galerie, Kundenunterschrift über Signatur).
- Kunden-Terminbestätigung per Mail mit Antwort-Erkennung.

## Neu 27.09.2026 – Review: Lead-Prozess + Design (v15-Nachtrag)

- Lead→AD-Übergabe repariert (Akte-Zugriff über VOT-Termin, „Erfassung
  starten" in Meine Termine, AD-Glocke, Vorgang direkt beim monday-Sync,
  No-Show bleibt No-Show).
- Mail-Warteschlange an den Terminstatus gekoppelt (Storno bei Umbuchung/
  No-Show/Absage, Statusprüfung im Versand, Nurture +30 Tage – *seit v29 ohne Nurture*) – Pflicht
  vor mail_modus=live.
- Arbeitsvorrat: freie + qualifizierte Leads in der Anrufliste, Kunden-
  antwort weckt den Lead, Tagesdigest, Cockpit „Termin-Rückmeldung offen",
  Pfad „Verloren vor Termin", Überfällig-Banner in Leads VOT.
- Design: LM-Unternavigation, lesbare SLA-Chips (Min/Std/AT), de_datum-
  Filter (deutsche Wochentage), Icons statt Emojis, Cockpit-Kacheln,
  einbett=1 für das Anrufliste-Panel, Hauptmenü + Parametrierungs-Reiter.
- Details + bewusst offene Punkte: docs/leadmanagement-entscheidungen.md
  (Abschnitt Review 27.09.2026).
- Projektierung (27.09.): Galerie **je Sparte** mit Foto-Sammelbox
  (unsortierte Uploads, später einsortieren), Ordner „Förderung";
  Paket „Förderung" entfällt, BnD liegt im Paket Abnahme (& Freigabe);
  V1-Reste restlos entfernt; Demo-Projekte (`scripts/demo_projekte.py`);
  Team-Zuweisung repariert, Benutzer-Seite entrümpelt; Montage-Login im
  Demo-Modus landet in `/montage` statt am Portal; Sparten-Badges
  sichtbar (CSS-Kollision `.chip`).
- CEO-Review 27.09.2026: Kontrolldurchgang des Gesamtprozesses als
  Besprechungsgrundlage in `docs/ceo-review-2026-09.md` (offene
  CEO-Entscheidungen dort).

## Hotfix 29.09.2026 (7408bb4)

- Vorgangsakte mit Wiedervorlage warf Internal Server Error: Makro
  `wiedervorlage_chip` vergleicht nur noch den Tag (date vs. datetime);
  Regressionstest `tests/test_wiedervorlage_chip.py`.

## Neu in v16 – PV-Konfigurator (abgestimmt 29.09.2026)

(Plan: PLAN_V13.md; die Zählung v13 war bereits durch das
Team-Feedback belegt – Plan-Text „Neu in v13“ entspricht diesem Abschnitt.)

- PV-Konfigurator: Erfassung erzeugt vollständige PV-Angebote
  (0 % USt gem. § 12 Abs. 3 UStG, kein Förderblock). Auslegung:
  Maximal- oder Bedarfsbelegung ((HH×1,3 + WP×1,5 + WB) ÷ 960,
  Module à 0,455 kWp, Deckel = Dachbelegung), Strings (max. 27
  Module, 1.000 V), Sigenergy TP2/SigenStor-Auswahl aus kWp und
  Speicherwunsch; Parameter im Blatt „PV-Parameter“. Positions-
  logik: UK je Dachart inkl. Kreuz-Verlegung, Montage je Modul,
  Tigo-Optimierer, Gerüst (Vollgerüst → individuell), Elektro-
  Kette (Zählerschrank/UV/Zusammenlegung/Erdungsspieß/DC-ÜSS
  nach Strings), Immer-Positionen, Fit for Future analog WP
  inkl. Profile. Wirtschaftlichkeits-Beispielrechnung im
  Nachtext (parametrierbare Annahmen) – *seit v22 ersetzt durch die
  drei Wirtschaftlichkeitsseiten (Energiebilanz)*. Dachbelegungstool
  folgt – bis dahin Interim-Felder für Modulanzahl/Quer-Anteil.
- Steuersatz je Angebot (PV 0 %, sonst 19 %) in Summen, DB,
  monday und Statistik. DB-Ampel-Schwellen je Sparte
  parametrierbar.
- Lieferschein-PDF (ohne Preise) für angenommene Angebote
  aller Sparten.
- Technik: PV-Artikel PV001–PV176 aus den vier TAIFUN-Positionslisten
  in `Artikel-Preislisten/PV/` (Import „Artikel → PV-Positionslisten
  importieren“, GUID-Pinning im Blatt „PV-Artikel“, migrate.py importiert
  automatisch, wenn referenzierte PV-Artikel fehlen; der WP-Import fasst
  PV nie an). Logik-Blätter „Aktionen PV“ (Spalte Zusatzbedingung),
  „Angebotsaufbau PV“, „PV-Parameter“; Modul `app/pv_auslegung.py`
  (Schnittstelle Dachbelegungstool: `dachbelegung_setzen`). Fit for Future
  nutzt die WP-Artikel 014–017 (Enni/SWD-Regeln greifen identisch).
  PV-Vor-/Nachtexte als Textblöcke „Friondo PV <Profil>“, Platzhalter
  `[BEISPIELRECHNUNG]`. Anhangsregel „wenn Sparte = PV“. Button „Erneut
  prüfen“ für Katalog-Erfassungen. Tests: `tests/test_pv_v13.py`.
- Offen/Zulieferung: Dachbelegungstool, Sigenergy-/Modul-Datenblatt;
  fachliche Rückfragen siehe docs/nach-dem-update-v13.md.

## Neu in v17 – Projektierung V4 (abgestimmt 29.09.2026)

(Plan: PLAN_PROJ_V4.md; gültige Kanban-Phasen ab hier.)

- **Board:** Auftragseingang als zwei Spalten (unterminiert | terminiert,
  chronologisch nach Montagebeginn; Drop auf „terminiert" öffnet Team +
  Termin – *überholt: seit v28 der gemeinsame Termin-Dialog; Drop in eine andere
  Phase öffnet den Dialog „Phase ändern“, Spalten in voller Breite mit eigenem
  Scroll – siehe v28*); alle Spalten chronologisch, Unterminierte unten. Phasen
  `abnahme` und `freigabe` ersetzen `abnahme_freigabe` (Pakete Abnahme:
  Montagebericht · IBN-Protokoll · Abnahmeprotokoll · Restarbeiten ·
  Abweichungen/Nachtrag; Freigabe: Rechnung freigegeben · BnD); Wächter
  Abnahme → Freigabe = Pflichtaufgaben Abnahme.
- **Vorlauf-Ampel** je Gewerk bis Montagebeginn: grün > 8 Wochen, gelb
  4–8, rot < 4 / unterminiert (Parameter `vorlauf_gruen_ab_wochen`,
  `vorlauf_gelb_ab_wochen`); Punkt vor dem Termin-Badge, Spalte in Liste,
  Filter; getrennt von der Planungs-Ampel.
- **Zeiten im 15-Minuten-Takt** (step 900, serverseitige Rundung) in allen
  Projektierungs- und Montage-Dialogen; Aktionen in der Akte per fetch
  ohne Seitensprung (JSON-Antwort bei Accept application/json, Redirect
  als Fallback), Scroll-Position wird wiederhergestellt.
- **Pakete:** „Auftragsunterlagen prüfen" jetzt Schritt 1 in Planung WP;
  „Montageteam zuweisen" (Team + Termin – *seit v28 Termin-Dialog mit Art „Montage
  (WP)“; neue Bedingungen `foerderung:ja`, `montagevorbereitung.1=geschrieben`,
  `planung_elektro.3=erfolgt über Friondo`, `steckbrief:geruest=ja` – siehe v28*) jetzt
  Schritt 2 im Auftragseingang;
  Fit for Future mit Ja/Nein für HEMS, iMSys und SpotDynamic (vorbelegt aus
  dem Steckbrief, bestätigt per Klick); FP-Fragen FP-E05 iMSys, FP-E06
  HEMS, FP-O04 Restöl; Steckbrief-Felder `restoel_liter`, `stemmarbeiten`
  (Pos. 126), `erdleitung_m` (Pos. 102 / Erfassung A05 – nicht 139/140,
  Begründung in docs/projektierung-entscheidungen.md), `imsys`, `hems` aus FP.
- **Sub-Mails:** Platzhalter {restoel}, {stemmarbeiten}, {erdarbeiten};
  GaLa-Vorlage mit Erdarbeiten, Entsorgungs-Vorlage mit Restöl und
  Stemmarbeiten.
- **BzA:** Felder bza_id, bza_erstellt_am, bza_gesendet_am, bza_datei_id,
  kfw_antragsnummer, kfw_zusage_am; Aufgabe mit Buttons Portal ↗ ·
  Datenblatt · BzA erfassen (ID, Datum, PDF in Galerie-Ordner „Förderung");
  automatische Kundenmail „BzA" (Vorlage in der Parametrierung, Platzhalter
  {bza_id}, {foerderbetrag}, {link_kfw}) über projektierung@; nicht
  verpflichtende Aufgabe „KfW-Antragsnummer/Zusage" in Montagevorbereitung
  (kein Wächter).
- **Heizreport:** generischer, in der Parametrierung konfigurierbarer
  REST-Client mit Verbindungstest; Buttons an der Heizlast-Aufgabe bei
  konfigurierter API; `docs/heizreport-api.md` mit Anfragetext (API-Doku
  nicht öffentlich). *Seit v26 API v2:* öffentliche Kunden-API
  `https://heizreport.net/api/v2` mit Bearer-Token ist Standardmodus, der
  generische Client bleibt als Modus „generisch“ (siehe „Neu in v26“). **UGL:** Formatabgleich (docs/ugl-format.md,
  Testdatei), Stücklisten-Pflege in der Parametrierung, Bestell-Dialog mit
  Vorschau/Lieferdatum/Lieferadresse, Nachbestellungen, Go-live-Prüfpunkte.

## Neu in v18 – Projektierung Go-live (abgestimmt 30.09.2026)

(Plan: PLAN_PROJ_V3_GOLIVE.md, Phasen 84–86; Abgleich mit V4 im Plan-Vorspann.)

- **Auftragsdaten TAIFUN:** „Angebot → Projekt“ führt bei TAIFUN-Aufträgen
  auf die Pflichtseite „Auftragsdaten“ (`/projektierung/gewerk/<id>/auftragsdaten`,
  je Gewerk des Angebots ein Abschnitt). Feldliste aus Blatt „Steckbrief“:
  neue Spalten `eingabe` (`text` / `zahl` / `ja_nein` / `auswahl:A|B`) und
  `bezeichnung`, Zeilen mit `quelle_typ = auftragsdaten` (reine Definition).
  Werte landen im Steckbrief mit `steckbrief_werte.quelle = auftragsdaten`
  (nicht manuell – nur die FP-Erfassung überschreibt sie; „Neu ableiten“
  nicht). Pflicht-PDF, falls am Eintrag keins liegt (Angebot + Galerie
  „Allgemein“ + Projektablage). **KfW-gefördert** ist das Angebotsfeld
  `kfw_gefoerdert` (ja/nein/leer = unbekannt) – `bza.ist_gefoerdert` wertet
  es für TAIFUN aus. Knopf „Auftragsdaten bearbeiten“ + Badge „Auftragsdaten
  fehlen“ im Steckbrief, Material-Aufgabe zeigt bei TAIFUN den Hinweis statt
  UGL; steckbrief-abhängige Paketschritte werden nachgezogen
  (`steckbrief_schritte_nachziehen`). Stub `auftragsdaten_aus_pdf` (Stufe 2).
- **Bestandsimport** (`app/bestandsimport.py`, Parametrierung →
  Bestandsimport, nur Admin): Vorlage `docs/bestandsimport_vorlage.xlsx`
  (Blätter Projekte + Anleitung, eine Zeile je Gewerk), Vorschau mit
  Prüfung je Zeile, Import nur fehlerfreier Zeilen, idempotent über
  TAIFUN-Nr. + Sparte, Kunde über Name + PLZ, weitere Aufträge derselben
  Sparte → eigenes Projekt. Legt Kunde/Vorgang/externen Eintrag
  (`angebote.bestand = 1`, Status Angenommen)/Projekt/Gewerk in der Phase an,
  Pflichtaufgaben der Pakete vor der Phase pauschal erledigt (Verlauf „Bestand
  – pauschal erledigt“), Montagetermin mit Team/Bestätigung (*v28: Besetzung =
  Team-Mitglieder*), Steckbrief.
  Badge „Bestand“ (`gewerke.bestand_import_id`) in Akte und Board; Statistik
  zählt `bestand` nie. Protokoll-Tabelle `bestandsimporte` mit „Rückgängig“
  (nur Angelegtes, das seither unverändert ist). Trockenlauf:
  docs/bestandsimport-trockenlauf.md.
- **Freigabe pilot + Go-live-Checkliste:** `freigabe_modus` admin / **pilot**
  / alle; pilot = Admin + Pilotliste (`pilot_benutzer`, Häkchen in den
  Projektierung-Einstellungen; Hauptrolle Projektierung/Montage sieht das
  Modul immer). Portal-Badge „Demo · Coming soon“ / „Pilot“ / keins. BzA-
  Kundenmail nur im Demo-Modus an `projekt_testadresse`, im Pilot echt.
  Parametrierung → **Go-live-Checkliste** (`app/golive.py`, 11 Live-Punkte
  mit Link: Absender + Testmail ohne Fallback, Kalender-Modus + Outlook-
  Termin, Benutzer je Rolle, Teams mit Mitgliedern, Sub je Typ, Portal-URLs,
  Collin-Kundennummer, Stücklisten ≥ 90 % ohne BEISPIEL-Nummern,
  Collin-Testdatei (Häkchen, von der Stücklisten-Seite umgezogen), Formulare
  abgenommen (Häkchen), Bestandsimport). Tests: `tests/test_projektierung_v3.py`.

## Neu in v19 – BzA-Datenblatt & BAFA-Anlagen (abgestimmt 29.09.2026)

(Plan: PLAN_V14.md, umnummeriert auf Phasen 95–97; der Plan-Text „Neu in
v14“ entspricht diesem Abschnitt.)

- **BzA-Datenblatt** (KfW „Bestätigung zum Antrag“, Programm 458): EIN
  Generator `app/bza_datenblatt.py` in exakter Portal-Struktur (1
  Investitionsobjekt · 2 Wärmeversorgung vor Sanierung · 3 Geplante
  Wärmeversorgung · 4 Geplante Kosten · 5 Boni · 6 Ersteller). Button
  „BzA-Datenblatt (PDF)“ an jedem WP-Angebot (Editor-Kopf, Vorgangsakte,
  jeder Status) **und an TAIFUN-WP-Einträgen** (Gerät dann Pflichtauswahl aus
  dem Blatt „BAFA-Anlagen“); Dialog `/angebote/<id>/bza-datenblatt` (WE
  übersteuerbar, Ersteller wählbar), PDF `BzA-Datenblatt-<Nr>.pdf` mit Vermerk
  „Internes Arbeitsblatt … keine KfW-Unterlage“. Fehlende Angaben rot
  („— fehlt: bitte beim Kunden erfragen“). Die Projektierungs-Seite
  `/projektierung/gewerk/<id>/bza` (v15/v17) nutzt denselben Generator
  (+ Kundendaten, Stand BzA/KfW, Link zum PDF).
- **Erfassung WP:** A02 heißt „Inbetriebnahmejahr (Baujahr) der bestehenden
  Heizung“ (steuert K02 wie bisher, Boni-Kategorie im Datenblatt); neu A20
  „Nennleistung der bestehenden Heizung in kW“ (Pflicht) und N11
  „Contracting-Modell?“ (Vorbelegung Nein). Heizflächen = bestehende Frage
  H02 (nur Fußbodenheizung → 35 °C, sonst 55 °C).
- **Blatt „BAFA-Anlagen“** (konfigurator_logik_v5.xlsx, `logik.bafa_anlagen`,
  `bafa_fuer_positionen`): 045–054 und 15+055 / 15+056 → Anlagennummer,
  Hersteller, Gerätebezeichnung, kW, Kältemittel, Netzdienlichkeit,
  E/E-Anzeige, Hinweis; Schlüssel `vorrat:…` (Hybrox 21) ohne Konfigurator-
  Anbindung. Die weiße 8800er-Außeneinheit (030) hat KEINE eigene Nummer
  (bestätigt 30.09.2026) – 16019200/16019199 gelten für beide Farben.
- **Parametrierung „BzA-Ersteller“:** Firmenblock fest (Friondo GmbH,
  Arnold-Overbeck-Str. 63-65, 47139 Duisburg, HWK-Nr. 1862718), Standard-
  Ersteller `bza_ersteller_standard` (leer = angemeldeter Benutzer).
- **KfW-gefördert am TAIFUN-Eintrag** (`angebote.kfw_gefoerdert`, Bestand =
  unbekannt): Abfrage im Dialog „Extern erledigt“ (WP), nachträglich am
  Eintrag änderbar; `bza.ist_gefoerdert` bietet nur noch bei „unbekannt“
  beide Wege an. Tests: `tests/test_bza_v19.py`; Team-Hinweise:
  docs/nach-dem-update-v19.md.

## Neu in v20 – Anschriften (abgestimmt 29.09.2026)

(Plan: PLAN_GESAMT.md B4, Phase 98 – Chat-Abstimmung 29.09.)

- **Editor-Bereich „Anschriften“** mit zwei Karten Rechnungsanschrift und
  Lieferanschrift (Name/Firma, Zusatz optional, Straße + Nr., PLZ, Ort; Makro
  `_anschriften.html`, CSS `.anschrift-karten`). Vorbelegung: Rechnung aus
  Erfassung (O06/O09–O12) bzw. Kunden-Standard, sonst Kundenname +
  Ausführungsort; Lieferung aus O13 (strukturiert geparst) bzw. Kunden-
  Standard, sonst Ausführungsort. Neue Spalten `angebote.rechnung_zusatz`,
  `liefer_name/_zusatz/_strasse/_plz/_ort` (`liefer_anschrift` = Alt-Text
  v13, Migration `migration_v20_anschriften` strukturiert ihn).
- **Regel:** editierbar nur im Entwurf (`POST /angebote/<id>/anschriften`);
  versendete Angebote über „Überarbeiten“ → Version .2 (kopiert alle
  Anschriftsfelder).
- **Kunden-Standard** in der Vorgangsakte (aufklappbar, ID/Admin und AD an
  eigenen Vorgängen,
  `POST /vorgaenge/<id>/anschriften`; Werte gleich Kundenname/Ausführungsort
  werden nicht gespeichert): Spalten `kunden.rechnung_*` / `kunden.liefer_*`;
  wirkt auf NEUE Angebote (`anschriften.angebot_vorbelegen`) und neue
  WP-Erfassungen (O06 = Nein + O09–O12, O13; `vorbelegt_json`).
- **PDF:** Logik in `app/anschriften.py` – der Rechnungs-Name ersetzt bei
  Abweichung den Kundennamen im Empfängerblock (Briefanrede bleibt der
  Ansprechpartner), Zusatz als eigene Zeile, „Ausführungsort: …“ nur bei
  abweichender Rechnungsadresse, „Lieferanschrift: …“ nur, wenn sie vom
  Ausführungsort abweicht; der **Lieferschein** (v16) ist an die
  Lieferanschrift adressiert. Tests: `tests/test_anschriften_v20.py`.

## Neu in v21 – Lead-Management V1.1 (abgestimmt 27.09.2026)

(Plan: PLAN_LEAD_V1.1.md, Phasen 87–89; Vorlage docs/leadmanagement-prototyp.html.)

- **Quelle · Kampagne · Kanal:** Quelle = Herkunft (Kosten, Typ-Farbe,
  API-Key), Kampagne = Landingpage/Aktion (Budget), Kanal = Vertriebskanal
  (Dropdown an der Quelle, wird beim Eingang an Kunde/Vorgang gesetzt, falls
  leer; manuell gesetzter Kanal bleibt). Unbekannte Quellen-Keys und
  Kampagnen aus Betreff `[LEAD] <quelle> <kampagne>`, API oder utm_campaign
  legen sich selbst an (Badge „neu · automatisch angelegt", Glocke an Admin – *seit v29
  Glocke `quelle_auto` standardmäßig aus [ANNAHME]*);
  Fallback-Quelle `unbekannt`. Quellen-/Kampagnenpflege zeigt Eingänge 7/30
  Tage und Kosten je Lead; Kanal-Report zusätzlich je Kampagne;
  `docs/formular-standard-agentur.md`.
- **Übersicht** `/lead-management/uebersicht` als Modul-Einstieg
  (`lm_startseite`): Kacheln Eingänge heute (Ø 10 AT) / 7 Tage / SLA rot /
  Jetzt dran / ≥ 3 Versuche offen / Termine heute; Eingänge je Tag (14 Tage,
  gestapelt nach Quellen-Typ, Tokens `--q-*`, feste Reihenfolge, Legende);
  Kontaktstatus offener Leads nach Versuchen; Erstkontakt heute; Tabelle
  Quelle × Kanal × Zeitraum mit erreicht-/terminiert-Quote (Kohorte),
  ≥ 3 Versuche und Kosten je Lead; Cockpit darin aufgegangen. Eine
  Zählfunktion `eingaenge_zaehlen` für Übersicht, Statistik, Kanal-Report
  und Portal-Kacheln.
- **Anrufliste neu:** Schnellfilter-Chips mit Zählern (Heute eingegangen ·
  SLA rot · ≥ 3 Versuche · Rückruf heute · Ohne Leadmanager), Gruppen Jetzt
  dran · Weiter versuchen · Neu heute · Wiedervorlagen fällig · Sonstige;
  zweizeilige Zeile mit Versuchs-Punkten (`versuche_punkte`, grau 1–2 /
  orange 3 / rot 4+), Kontaktstatus-Satz („3× nicht erreicht · zuletzt … ·
  nächster Versuch …"), Quelle-/Kanal-Badges, ⚑-Flags, Aktionen Erreicht /
  Nicht erreicht / Mailbox / Rückruf / ⋯-Menü; Tasten 1–7 unverändert;
  derselbe Kontaktstatus im Lead-Kopfblock der Vorgangsakte.
- Technik: `app/lead_uebersicht.py`, `app/lead_anrufliste.py`, Spalten
  `lead_quellen.auto_angelegt` / `kampagnen.auto_angelegt`, Parameter
  `lm_startseite`; Tests `tests/test_lead_v11.py`.

## Nachtrag 30.09.2026 – Rückfragen und Bugfix

- **Bugfix:** Erfassungs-Detail einer vollständigen PV-Katalog-Erfassung warf
  500 (berechneter Protokoll-Abschnitt „Auslegung“ ist keine Bogenseite) –
  Korrektur-Link nur noch für echte Bogenseiten (`ad57a28`).
- **Kunden-Dubletten** (`app/kunden_dubletten.py`, Parametrierung →
  Kunden-Dubletten, Admin): Gruppen gleicher Nachname + Vorname + PLZ,
  Hauptdatensatz wählbar (Vorschlag: ältester), Verweise (Vorgänge,
  Angebote, Erfassungen, Leads, Projekte, Konfigurationen) wandern um, leere
  Felder werden ergänzt, Dubletten gelöscht, Protokoll
  `kunden_zusammenfuehrung_protokoll`. Gruppen mit abweichender Straße sind
  nicht vorausgewählt. Vor dem Bestandsimport ausführen.
- **BzA-Kundenmail per Häkchen** (Projektierung-Einstellungen, Parameter
  `bza_mail_aktiv`, Standard an): aus = kein Mail-Knopf, „BzA erfassen“
  erledigt die Aufgabe ohne Mail; zusätzlich Knopf „ohne Mail abschließen“.
  Text/Betreff wie bisher dort unter „Kundenmail BzA“.
- **Go-live-Checkliste:** prüft das echte Standard-Kennzeichen je Sub-Typ
  (Parametrierung → Subunternehmer, Spalte „Standard“; aktiv + E-Mail).
- Tests: `tests/test_rueckfragen_0930.py`.
- **Fehlersuche mit Daten im neuen Format (30.09.):** Anschriften – kein
  Rückgriff auf den Kunden-Standard zur Anzeigezeit (Standard wird nur beim
  Anlegen kopiert; versendete Angebote bleiben unverändert), die Erfassung
  gewinnt (O06 beantwortet bzw. O13 vorhanden → kein Standard), O13-Freitext
  wird nur bei sicher erkennbarer Adresse strukturiert (sonst Zusatz), ein
  Zusatz allein behält den Ansprechpartner, keine leere Zeile
  „Ausführungsort:“, lange Anschriften schieben die Überschrift.
  „Überarbeiten“ behält das Alternativ-Kennzeichen (Bug seit v10),
  „Duplizieren“ behält bauseits/Rabatt/Sonderpreis/Alternativ.
  `zahl_parsen` weist inf/nan ab. Lead: `wunschzeiten_liste` (robust),
  ungültige Filter-IDs werden ignoriert, `POST /api/leads` akzeptiert Zahlen
  (PLZ/Telefon) und Sparten als Text, Budget/Kosten im deutschen Format.
  Auftragsdaten bei storniertem Gewerk leiten um; BzA-Dialog mit
  Geräteauswahl auch für Tool-Angebote; Dubletten übernehmen Anschriften nur
  als ganze Gruppe. Tests: `tests/test_sweep_0930.py`.

## Neu in v22 – Wirtschaftlichkeit PV & PA04 (abgestimmt 30.09.2026)

(Plan: PLAN_V15.md, Phasen 99–103; Team-Feedback 30.09. = Phase 103.)

- **PA04 „Ertüchtigung bestehender ZV?“** (Phase 99): Ja löst keine
  Positionen und keine Ampel mehr aus – Antwort (mit PA05/PA06) nur im
  Protokoll; Zeile im Blatt „Aktionen PV“ auf „–“ gesetzt. Es gibt keine
  weiteren Platzhalter-Gründe „… noch nicht hinterlegt“ im PV-Konfigurator;
  die übrigen AMPEL-Gründe (Dachart Sonstige, Vollgerüst/Sonstiges,
  Zählerschrank 4-Feld/Sonstige, > 4 Strings, WR/Speicher nicht im
  Sortiment) sind fachlich gewollt (offene Rückfragen in
  docs/nach-dem-update-v13.md).
- **Rechenkern `app/wirtschaftlichkeit.py`** (Phase 100): reine Funktion
  `berechnen(param, anlage)` – **Saisonmodell (Entscheidung 01.10.2026,
  PLAN_V15 Anhang B):** Energiebilanz je Monat mit Monatsprofilen (PV nach
  typischer Ertragsverteilung Deutschland, Haushalt angelehnt an BDEW H0,
  Wärmepumpe 80 % Heizung nach VDI-2067-Gradtagszahlen + 20 % Warmwasser,
  Wallbox flach; alle vier im Blatt „PV-Parameter“ als 12 Werte „Jan; …;
  Dez“ parametrierbar): Direktverbrauch = Direktanteil × Monatsverbrauch ×
  Sonnenfaktor (Monatsertrag ÷ Durchschnittsmonat), höchstens 90 % der
  Monatsproduktion; Speicher = min(kWh × Zyklen × Tage ÷ 365, Überschuss ×
  Wirkungsgrad, Restlast); Jahreswerte = Summe der Monate; mit flachen
  Profilen ergibt sich das Jahresmodell aus Anhang A. Danach Kosten
  ohne/mit Anlage (Degradation, Strompreissteigerung, SpotDynamic-
  Bezugspreis), Break-even, Baustein-Treppe PV → + Speicher → + HEMS →
  + SpotDynamic mit Upsell-Hinweis, Szenarien 1/3/5 %, CO₂. Parameter aus
  dem Blatt „PV-Parameter“ (24 neue Zeilen, Prozent als Zahl mit Einheit
  „%“, Listen mit Semikolon, Standardwerte im Code, `parameter_lesen`
  meldet fehlende Zeilen).
  Anlagendaten: `pv_auslegung.als_dict()` liefert zusätzlich
  hh_kwh/wp_kwh/wb_kwh/speicher_kwh (Verbrauch jetzt auch bei
  Maximalbelegung ermittelt); `pdf_export.wirtschaftlichkeit_fuer` (Alias
  `beispielrechnung_fuer`) holt Speicher/HEMS/SpotDynamic aus den aktiven
  Positionen (KOMBI_MUSTER bzw. „SigenStor Batterie“, 015, 017), fällt bei
  altem pv_json auf die verknüpfte PV-Erfassung zurück (auch über
  Versionskette/Vorgang), Investition = Endbetrag, Startjahr = Angebotsjahr
  + Versatz. Kontrollwerte: `tests/test_wirtschaftlichkeit_v22.py`.
  `pv_auslegung.wirtschaftlichkeit` (additive Quote) bleibt nur als
  Übergang und ist nicht mehr im PDF-Weg.
- **Drei PDF-Seiten `app/wirtschaftlichkeit_pdf.py`** (Phase 101): feste
  A4-Seiten (Auf einen Blick · Ersparnis im Detail · Sicherheit &
  Transparenz) nach `docs/wirtschaftlichkeit-mockup/seite1–3.html`, mit
  fpdf2-Primitiven, Schrift Poppins (`app/static/pdf/fonts`, OFL; Fallback
  Arial mit Log-Warnung; „₂“ in CO₂ wird als tiefgestellte Ziffer
  gezeichnet, da Poppins die Glyphe nicht hat), kompakter Kopf über
  `AngebotsPdf.kompakt_kopf` (header() verzweigt), Fußzeile unverändert,
  Auto-Page-Break für den Block aus. Einbindung in `_nachtext_rendern` am
  Platzhalter `[WIRTSCHAFTLICHKEIT]` (Alias `[BEISPIELRECHNUNG]`); reine
  Platzhalter-Seiten entfallen ohne Auslegungsdaten; Migration
  `angebotsprofile.migriere_pv_platzhalter` stellt bestehende PV-Nachtexte
  um. Varianten: ohne Speicher/HEMS/SpotDynamic entfallen Stufen (Spot-
  Hinweis nur, wenn Netzbezug > 0), ohne Wärmepumpe Karte „Ihr Verbrauch“,
  ohne Break-even neutraler Satz. Abnahme-PDF:
  `docs/wirtschaftlichkeit-mockup/abnahme-AN-C-261021.pdf`.
- **Einbindung** (Phase 102): Häkchen „Wirtschaftlichkeit im PDF
  ausblenden“ (`angebote.wirtschaftlichkeit_ausblenden`, nur PV, Route
  `POST /angebote/<id>/wirtschaftlichkeit`; Überarbeiten/Duplizieren/
  Kopieren übernehmen es); Parametrierung zeigt die Tabelle „PV-Parameter“
  mit Einheit, fehlende v22-Zeilen als Hinweis mit Standardwert
  (`logik.pv_parameter_einheit`). Team-Hinweise: docs/nach-dem-update-v22.md.
- **Team-Feedback 30.09.** (Phase 103): **Fehlerprotokoll** – Tabelle
  `fehlerprotokoll` + `data/fehler.log` (`app/fehlerprotokoll.py`), globaler
  Exception-Handler in `app/main.py` (Fehlerseite bzw. Editor-Meldung mit
  Fehler-Nr., JSON bei Accept application/json), Ansicht Parametrierung →
  Fehlerprotokoll. **Diagnose des sporadischen Internal Server Error** beim
  Löschen/Verschieben von Positionen: die Positionsrouten sind gegen stale
  IDs, Doppelklick, leere/fremde Sortier-Payloads, letzte Position und
  Fremdsperre robust (reproduziert: alle 303); bestätigte Ursache ist
  `sqlite3.OperationalError: database is locked` – Hintergrundläufe
  (Geocoding alle 5 min mit flush je Adresse und Nominatim-Wartezeiten,
  monday-Sync alle 15 min, Mail-Läufe 07:00/07:15 mit Graph-Aufruf) halten
  nach dem ersten Schreibzugriff die SQLite-Schreibsperre während der
  Netz-I/O; ein Editor-POST wartet busy_timeout (5 s) und stirbt. Abgefangen
  durch `_speichern` in `routers/angebote.py` (Rollback + eine Wiederholung
  nach 0,7 s für entfernen/sortierung/aendern/menge/neu-nummerieren;
  Sortierung mit robustem Parser und Rückmeldung bei geänderten
  Positionen), das Fehlerprotokoll (Meldung „Datenbank kurz belegt …“) und
  Timeouts für Graph-Aufrufe (`graph_versand`, `mail_sync`); Test mit echter
  Schreibsperre `tests/test_v22_positionen.py`. **Folgeänderung (seit v27
  erledigt):** Transaktionen der Scheduler verkürzen (commit vor Netz-I/O,
  Geocoding-Backoff für „fehler“-Adressen) – umgesetzt mit dem Scheduler-Rahmen
  `app/scheduler.py` und `db.kurz()` (PLAN_V17 Phase 128). Weitere Punkte: Editor behält
  die Scroll-Position (Scroll-Restore aus `projektierung.js` gilt auch für
  `/angebote/<id>`, Anker für neue Positionen), Gruppen-Überschriften je
  Angebot editierbar (`POST /angebote/<id>/gruppe`, wirkt auf alle Positionen
  des Blocks), Auslegungszeile WP mit Einheit „psl.“ (Migration für den
  Bestand), BzA-Datenblatt im Dialog vollständig übersteuerbar inkl.
  Contracting (Vorbelegung Nein; statuslos, nur für das erzeugte PDF).
  Tests: `tests/test_v22_feedback.py`, `tests/test_fehlerprotokoll_v22.py`,
  `tests/test_bza_v19.py` (Phase103Uebersteuern).
- **Voll-Crawl als Skript** `scripts/voll_crawl.py` (neu; vorher nur ad hoc):
  alle GET-Routen × alle IDs einer DB-Kopie für die Rollen admin/innendienst/
  aussendienst/montage, Aufruf `venv\Scripts\python scripts\voll_crawl.py
  --data diagnose\test_v22\data` (DATA_ORDNER-Umlenkung, Cookie-Login ohne
  PIN, Nebenwirkungs-Routen ausgeschlossen, Bericht mit Tracebacks). Befund
  30.09. gegen die Server-Kopie vom 29.09.: 44.812 Aufrufe, eine
  Absturzursache – `GET /signatur/<id>/signiert.pdf` mit absoluten
  Altpfaden des früheren Entwicklungs-PCs (`angebote.signierte_datei`) warf
  RuntimeError; jetzt Auflösung über den Dateinamen im Signatur-Ordner bzw.
  Meldung (`signatur.signierte_datei_pfad`) + Datenmigration der Pfade.
- **Umgebung 30.09.2026:** Entwicklungs-PC neu (kein Git installiert, kein
  `.git` im Projektordner – Commit von v22 steht aus); venv mit Python
  3.14 neu angelegt (`venv_alt_py312` = unbrauchbare Kopie des alten
  Rechners); Server-DB-Kopie in diagnose\ (29.09. 15:32) ist Vor-v16-Stand
  und wird für Crawl/Abnahme nach diagnose\test_v22\data kopiert und
  migriert.


## Neu in v23 – Lead-Management V2 (abgestimmt 02.10.2026)

> Hinweis v25: Score/Qualifizierung abgeschaltet, Board „Terminiert“ heißt „Deals“,
> „Info-Veranstaltung“ heißt „Infoabend“, „Nicht erreicht“ ohne Dialog und ohne
> automatische Wiedervorlage, Kundenkartei neu aufgeteilt mit Autospeichern – siehe v25.

(Plan: PLAN_LEAD_V2.md Teil 1, Phasen 104–112; Teil 2 = Auftragstext mit
Anforderungsdiktat A–I, Statusliste 5a, Festlegungen F1–F16. Entscheidung
Andreas: kein Lastenheft, direkt codieren; offene Punkte als Annahmen A-1…A-15
im Plan. Alles weiter im **Demo-Modus** `lead_freigabe_modus = admin`; V3 schaltet
frei. Umsetzung als paralleler Workflow: ein Agent je Fachphase 105–111 plus
Prüf-Agent, Hook-Änderungen an geteilten Dateien zentral eingespielt.)

- **Fundament (Phase 104):** Lead = Vorgang bleibt. Spalten `kunden.objektart`
  (EFH/RH/REH/MFH) + `parteien`; `vorgaenge.ad_id` (zuständiger AD/HV, A-7),
  `vorab_angebot` (F10), `veranstaltung_id`, `teilgenommen`; `vot_termine.typ`
  (vot|telefon|online, A-2), `medium`, `ics_uid`, `ics_sequence`;
  `benutzer.buchungslink`, `nebenstelle`; `ad_profile.terminiert_selbst`
  (Handelsvertreter, A-1), `kompetenz_sparten` (JSON), `kompetenz_kombi`,
  `kompetenz_mfh`, `kompetenz_gewerbe`; `lead_aktivitaeten.call_id/richtung/
  nebenstelle` (CTI-Vorbereitung). Tabellen `todos`, `info_veranstaltungen`,
  `benutzer_einstellungen`. Sparte **GW (Gewerbe)** als fünfter Code (Freitext-
  Erfassung wie WB). Steuerdatei (*v29: Spalte `nach_letztem` im Blatt Kaskade, keine
  Nurture-Mail +30 Tage, neues Blatt Terminhinweise*): Kaskade 5 Stufen (+2h · +1d 18:00 Mail ·
  +3d · +7d Mail · +14d `mail_disqualifiziert` letzter), Gründe `verloren`
  (Zu teuer · Kein Interesse mehr · Bleibt bei Öl/Gas · Woanders unterschrieben ·
  Sonstiges) und „Nachbearbeitung, noch nicht bereit für VOT“, Blätter
  **Objektarten** und **Status** (Phase → Label/Farbe/Board/Gruppe + monday-Status,
  Mapping 5a; `logik.board_fuer`, `logik.phase_fuer_monday`). Parameter
  `versuche_max` 5, `wv_meldet_sich_tage`, `pflichtfelder`, `kanal_farben`,
  `hv_ausschluss`, `hv_standard_benutzer`, `ersatz_radius_stufen`,
  `ersatz_alter_tage`, `info_*`, `puffer_min` 30, `max_termine_tag_start` 3,
  `dashboard_horizont_tage`, `kanal_ad_regel`, `vorab_dauer_min`,
  `ersatz_min_treffer`, `termin_konflikt_modus`, `vorschlag_raster_manuell_min`
  (Parametrierung → Lead-Einstellungen, Abschnitte „Lead-Management V2“).
  Vorlagen `disqualifiziert`, `online_termin_einladung`, `terminabsage`.
  `app/lead_v2.py`: `zugriff_erlaubt`/`gate` (404-Gate mit HV-Freigabe),
  `ad_zuweisen`/`leadmanager_zuweisen` (Ausschluss F14, Aktivität, Glocke),
  Kompetenzregel `kompetenz_passt`, Pflichtfelder, Benutzereinstellungen,
  Migration `bestand_nachziehen` (ad_id aus Terminen, Objektart aus Q-W02/Q-P02,
  F3-Startwerte und HV-Kennzeichen per Namensabgleich). `app/lead_info.py`:
  Terminregel 1. Donnerstag 18:00 Krefeld mit NRW-Feiertagen (Osterformel),
  Kontrollliste Okt 2026–Aug 2027 (13.05.2027 statt Himmelfahrt), rollierend 12
  Monate. V2-Router `app/routers/lm_*.py` sind **vor** dem V1-Router eingebunden
  (gleiche Pfade haben Vorrang); Styles in `app/static/lead_v2.css`.
- **Menü & Boards (Phase 105, `app/lead_boards.py`):** linke Icon-Leiste
  (`lm_nav`, 5 Einträge Hauptboard · Terminiert · Kontaktiert · Info-
  Veranstaltung · E-Mail-Vorlagen + „Mehr …“ mit allen V1-Einstiegen (*seit v29 Flyout;
  HV sehen nur vier Einträge, Vorlagen-Editor mit Baum in `lm_vorlagen.py`*), Demo-Badge,
  unter 900 px untere Icon-Zeile). Tabelle nach monday-Vorbild (`_tabelle.html`):
  Status-/Kanal-Labels mit Farbe aus Blatt Status/`kanal_farben`, 5 Versuchs-
  Punkte, Avatare, tel:/mailto, Spaltenkonfiguration je Nutzer
  (`benutzer_einstellungen` key `boards_spalten`), Inline-Edit per fetch
  (`POST /lead-management/boards/zeile/{id}`: status mit Pflichtgründen, notiz,
  ad_id, leadmanager_id, wiedervorlage), Sammelaktionen registrierbar
  (`SAMMELAKTIONEN`, `POST /boards/sammelaktion`, Aktivität je Lead).
  Hauptboard = Phasen ohne aktiven VOT (Neu · Pausiert · Disqualifiziert, Label
  „Telefongespräch“), Terminiert = mit VOT bzw. terminiert/erfasst/angebot/
  gewonnen/verloren (Angebotserstellung mit „Erfassung starten“/„Angebot öffnen“,
  Angebotsversand, Gewonnen, Verloren „vor Termin“); Verloren setzt offene
  Angebote auf Abgelehnt (`lead_boards.angebote_ablehnen`, Hook in
  `kern.lead_verloren`). Kanban zeigt nur das aktive Board. Reiter Kontaktiert
  (alle Versuche, Rufnummernsuche E.164 inkl. monday-Leads), `/vorlagen` =
  Vorlagen-Editor im Modul.
- **Kundenkartei (Phase 106, `app/lead_kartei.py`):** `GET /lead-management/lead/
  {id}` dreispaltig (B1–B8): Stammdaten inline mit roten Pflichtfeldern + Zähler,
  Objektart/Parteien/Rechnungsadresse (MFH), Zuständige, Einwilligungen; Reiter
  Timeline · E-Mail-Verlauf · Anrufnotizen · Qualifizierung · Termin ·
  Erfassungen/Angebote/Projekt; rechts Termine/Angebote/Erfassungen/Projekt/
  Anhänge/To-Dos. Button **Terminierung** (B8): vorgemerkter Termin → geplant,
  Terminbestätigung + Erinnerung, Kalender, Phase terminiert. „Erfassung ohne
  Termin“ = Vorab-Angebot (A-3), „Nachbearbeitung“ (F11/A-4), Wiedervorlage-
  Dialog, Anruf-Dialoge der Anrufliste. Lead-Kopf der Vorgangsakte reduziert +
  Link „Zur Kundenkartei“; Objektart belegt O01/O03/PO01 des Bogens vor.
- **Anruf-Workflow (Phase 107, `app/lead_anrufliste.py`, `lm_anruf.py`):**
  `POST /anruf/{id}` mit `dauer_sek`, `wiedervorlage_am`, `zurueck`; Sperre ab
  `versuche_max`; Dialog „Nicht erreicht“ mit Kaskaden-Vorschlag (`GET /anruf/
  {id}/vorschlag`); Doppelversand-Schutz (`mail_bereits_geplant` in
  `mail_planen`, Storno offener Kaskaden-Mails bei Erreicht/Rückruf/Kein
  Interesse); Fälligkeits-Glocke `faellige_wiedervorlagen_melden` (*seit v29 nur bei Art
  `wiedervorlage` in `glocke_lead_arten`, Standard aus*) (Anrufliste +
  5-Minuten-Scheduler); Stoppuhr `lm_anruf.js`, `telefon_link`-Makro (E.164),
  Dauer-Korrektur, „Meine Anrufe“, Rufnummernsuche `/anruf/suche`.
- **Terminassistent (Phase 108, `app/lead_termin.py`, `lm_termin.py`):**
  Kandidatenfilter Ausschluss (Kanal-Regel, Kompetenz, Terminierung aktiv, HV nur
  eigene Leads) / Abwertung (Gebiet, Umweg, Wunschzeit), Puffer = max(30 Min,
  Fahrzeit), Kapazität nur VOT, Begründung + Mini-Karte; Status **vorgemerkt**
  bei offenen Pflichtfeldern; manuelle Buchung (15-Min-Raster, Konfliktprüfung
  warnen|sperren); Vorab-Gespräch telefon/online (Buchungslink-Mail); Absage mit
  Storno-ICS (`METHOD:CANCEL`, gleiche UID, SEQUENCE+1) und **Ersatzkunde-Dialog**
  (F8); `bestaetigung-erneut` (A-9); ICS mit UID/SEQUENCE/Berater/Alarm;
  AD-Profil mit Kompetenzen, HV-Kennzeichen, Kanal-Regel, Buchungslink;
  Vorab-Gespräche kippen die Phase nicht (Hooks `typ == "vot"` in
  `lead_phase_berechnen`, Kennzahlen, Board).
- **Handelsvertreter (Phase 109, `app/lead_handelsvertreter.py`, `lm_hv.py`):**
  Rechte-Matrix, `GET /lead-management/handelsvertreter` (Gesamtsicht je
  Vertreter / eigene Leads + Dashboard-Block F16), Zuweisung immer über
  `lead_handelsvertreter.zuweisen` (Sonderregel „Deals - Rene“, Ausschluss F14,
  monday-Abgleich `leads.benutzer_id`), Standard F13 (`standard_nachziehen`
  nach monday-Sync, Button „An Standard geben“), Kanalwechsel-Hinweis + Glocke,
  Menüeinträge/Login-Ziel für HV, Lead-Glocken für HV auch im Demo (*überholt – seit v29
  HV-Sicht mit 404-Gate, Zuweisungs-/Kanalwechsel-Glocken standardmäßig aus*).
- **Dashboard & To-Dos (Phase 110, `app/lead_dashboard.py`, `lead_todos.py`):**
  `GET /lead-management/dashboard` „Meine Arbeit“ = Modul-Einstieg (Lead- und
  Angebots-Wiedervorlagen getrennt, fällig/kommende Tage, zugeteilte Vorgänge,
  Termine, To-Dos, Kacheln); To-Dos jeder an jeden, Glocke art `todo` ohne Mail
  (F7), Fälligkeits-Glocke im Scheduler, Block in der Vorgangsakte; Außendienst
  ohne HV → Meine Termine (F6).
- **Info-Veranstaltung (Phase 111, `lm_info.py`):** Board mit Gruppen je Termin,
  Archiv, Spalte „Teilgenommen“, Sammelaktionen Status ändern / nächste
  Veranstaltung / Teilgenommen, Termine-Pflege; `POST /api/leads` mit Feld
  `veranstaltung`, Standard-Sparten der Quelle, GW; Zuordnung A-8 für API,
  Parser, Schnellanlage, Import; Abgleich I5 → Aktivität `hinweis` + roter
  Hinweis „Kunde bereits im System“ (`docs/leads-api.md`).
- **Tests/Abnahme (Phase 112):** `tests/test_lead_v2_*.py` (8 Dateien),
  Gesamtlauf 416 Tests grün (268 Bestand + 148 V2), Abnahmeskript und Voll-Crawl gegen die migrierte
  DB-Kopie (siehe docs/nach-dem-update-v23.md). Offen/Annahmen:
  docs/leadmanagement-entscheidungen.md Abschnitt V2.

## Neu in v24 – Klimakonfigurator (abgestimmt 03.10.2026)

(Plan: PLAN_V16.md, Phasen 113–117; fachliche Vorlage docs/KL-Logik-Entwurf.xlsx
(bleibt als Herkunftsnachweis liegen); Umsetzung parallel durch sechs Agenten
A–F (Steuerdatei/Import, Lader/Parametrierung, Rechenkern/Einbindung,
Texte/PDF, Integration/Kontrollfälle, adversarialer Prüfer).)

- **Klima ist jetzt ein vollwertiger Konfigurator** (wie PV seit v16): eine
  grüne KL-Katalog-Erfassung erzeugt ein Tool-Angebot mit 19 % USt, ohne
  Förder-/KfW-Block, ohne Wirtschaftlichkeit, ohne Vollmacht; Ampel-Fälle und
  Freitext-Erfassungen laufen weiter über die TAIFUN-Schiene. Nur Bosch
  Climate (Wandgeräte), Serien 3200i (Standard, Vorbelegung), 7000i, 8000i;
  Klassen-Codes 9/12/18/24 (Code 7 wird nicht vergeben).
- **Steuerdatei `konfigurator_logik_v5.xlsx`** (Phase 113; Sicherung
  `diagnose/konfigurator_logik_v5.vor_v24.xlsx`): Blatt „Fragen KL“ ersetzt
  (28 Fragen: neu KO06 Geräteserie vor KO04, KO07 Demontage, KO08
  WLAN-Steuerung, KO09 Bemerkung, KR08 Raumfläche (Pflicht), KR09 Deckenhöhe,
  KR10 Wärmelast, KR11 Wanddurchbruch; Raumfragen als Wiederholgruppe „je Raum
  (KO05)“ in der Reihenfolge KR01, KR08, KR09, KR10, KR02, KR03, KR04, KR05,
  KR06, KR11, KR07; KE02/KE03 „nur wenn KE01 = Nein oder Unklar“). Neue
  Blätter: „KL-Artikel“ (GUID → KL-Nr., Pinning wie PV-Artikel), „Paketmatrix
  KL“ (Serie × Typ Single/Multi-Innengerät/Multi-Außengerät × Klasse →
  Artikel; „nicht im Sortiment“ mit Ampeltext in der Bemerkung), „Kombinationen
  KL“ (215 Zeilen: 205 CL5000M aus Bosch Tab. 7 + 10 CL7000M [ANNAHME A5]),
  „Montagematrix KL“ (1/1, 2/1, 2/2, 3/1, 3/2, 4/1 → KL020–KL025; alles
  andere Ampel), „Aktionen KL“ (Schreibweisen wie Aktionen PV, zusätzlich
  `Hinweis: <Text>` = fachlicher Hinweis ohne Position/Ampel, Mengenwörter
  „× Innengeräte“/„× Außengeräte“/„je Außengerät“/„je Raum“/„als EP“,
  Zusatzbedingungen ohne ≠), „Angebotsaufbau KL“ (Block 1 Montage/Zuschläge,
  Block 2 Elektro, Block 3 „Klimaanlage Bosch“ – jede KL-Nummer ausdrücklich,
  Block 3 endet mit der Auslegungszeile), „KL-Parameter“ (17 Zeilen: W/m²
  60/90, Höhenfaktoren 1,0/1,1/1,2, Klassengrenzen 2,6/3,5/5,3/7,0 kW,
  Leitung inklusive 5 m, Meterposition KL017, Standardserie, Max. 5 Innen-/3
  Außengeräte, §14a-Außengeräte „CL5000M 105/4 E; CL5000M 125/5 E“,
  Gewerbe-Verhalten Hinweis|AMPEL, Rollgerüst VK 499). Blatt „Textregeln“ +3
  Zeilen (Leistungsumfang KL020–KL025, KL013-Text, Kurzbezeichnung
  KL026–KL029), Blatt „Anhänge“ Platzhalter „(Bosch Climate Broschüre –
  Zulieferung)“ mit Regel „wenn Sparte = KL“ (*überholt – seit v27-Nachtrag 2 trägt die
  Zeile `Bosch Climate 3200i.pdf`*), Lesehilfe-Absatz „Klima (v24)“.
- **Lader `app/logik.py`:** Felder `kl_aktionen`, `kl_bloecke`, `kl_paket`
  (`KlPaketZeile`), `kl_kombis` (Außengerät → Anzahl → Kombinationen,
  aufsteigend normalisiert), `kl_kombi_artikel`, `kl_montage`, `kl_parameter`
  + `kl_parameter_einheit`, `kl_artikel`; `refs_extrahieren` kennt KL-Nummern
  mit Mengenwörtern und „als EP“; Aktionen „Hinweis:“ haben typ `hinweis`;
  `logik_fuer_sparte(logik, "KL")` liefert die KL-Sicht, sobald „Aktionen KL“
  existiert (sonst reiner Bogen). „Logik prüfen“: KL-Referenzen gegen
  „KL-Artikel“, Kombinationen nur Codes 7/9/12/18/24 und Anzahl = Codes,
  Montagematrix ohne Doppelzeilen, KR07-Hinweis „Optionen wie … (KO04)“,
  Standardserie ∈ KO06, Gewerbe-Verhalten, unlesbare Zahlen (Fehler);
  fehlende Pflichtparameter sind Hinweise mit Standardwert (wie PV v22).
- **Import `app/import_klima.py`** („Artikel → Klima-Positionslisten
  importieren“, Parametrierung/Lesesicht/Artikelliste; migrate.py automatisch,
  wenn referenzierte KL-Artikel fehlen): `Artikel-Preislisten/Klima/
  Ersatzangebot KL.xlsx` Pos. 001–048 → KL001–KL048, `Musterangebot KL.xlsx`
  Pos. 006 → KL049 Systemgarantie (0 €), KL050 „Rollgerüst / Arbeitsgerüst,
  Auf- und Abbau“ ohne TAIFUN-GUID (psl., 499,00 € aus KL-Parameter, EK leer –
  Innendienst ergänzt); Quelle `QUELLE_KL = "kl"`, GUID-Anker, Re-Import ohne
  Doppel, WP-/PV-Import fassen KL nicht an; Textregeln bei jedem Import.
  Stichproben: KL023 3.178,00 € psl., KL038 1.966,24 € Stück, KL034 1.341,60 €
  Set, KL049 0,00 €, KL050 499,00 €.
- **Rechenkern `app/kl_auslegung.py`** (Phase 114): je Raum-Klon Kühllast =
  KR08 × Höhenfaktor(KR09) × W/m²(KR10) ÷ 1000 (kaufmännisch, 2 Stellen),
  Klasse = kleinste Grenze ≥ Kühllast; je Außengerät (KR07) 1 Raum → Single aus
  der Paketmatrix, 2–5 Räume → Innengeräte je Raum + kleinstes Multi-Außengerät
  mit freigegebener Kombination (klein → groß), Montage `kl_montage[(Σ Räume,
  KO04)]`, §14a KL003 je Treffer der Parameterliste. Ampel-Gründe G1–G8
  wörtlich (Kühllast > 7,0 kW · Klasse in Serie nicht verfügbar · Multi 8000i ·
  Kombination nicht freigegeben · > 5 Innengeräte · Montagekombination · Leitung
  > 15 m · Elektrozuleitung > 15 m); G2/G3 kommen aus der Paketmatrix-Bemerkung
  „→ AMPEL: …“, die fachlichen Hinweise aus den „Hinweis:“-Zeilen des Blatts
  „Aktionen KL“ (Platzhalter <Nr> <Name> je Raum), jeweils mit den Plan-Texten
  als Fallback im Code. Positionen: Block 3 mit Außengeräten/Sets in
  Außengerät-Reihenfolge, Innengeräten je Klasse gebündelt, KL013 (EP laut
  KO08), KL049 und der Auslegungszeile „Auslegung der Klimaanlage“ (0,00 €,
  psl.) als letzter Zeile; `auslegungs_text` wörtlich nach Plan;
  `validierung` liefert die Absende-Meldungen („Außengerät <n> hat keinen
  zugeordneten Raum …“, „Raum <Nr>: Raumfläche fehlt“); `protokoll_zeilen`
  füllt die Seite „Auslegung“ des Protokoll-PDFs. Einbindung:
  `angebot_aufbau.angebot_anlegen` (KL → `kl_json` neue Spalte, `kfw_json =
  "{}"`, `konfigurator_typ = "KL"`, 19 %), `konfigurator.*`-Verzweigungen
  (Vorbelegungen KO06 = Standardserie, KO08 = „als Eventualposition“, KR10#i =
  stark bei Dachgeschoss, KO01 aus `kunden.objektart`), `routers/erfassung.py`
  behandelt PV und KL gleich (Validierung beim Absenden, Dezimalkomma bei KR08,
  Raum-Überschriften, `inputmode="decimal"`), Innendienst-Buttons „Angebot
  erzeugen“/„Erneut prüfen“ auch für KL; Versionen/Duplikate übernehmen
  `kl_json`; `positionsregeln_anwenden` fügt bei KL keine Pos. 014–017 ein.
- **Texte & PDF** (Phase 115): Textblöcke „Friondo KL Standard“ (Vor- +
  Nachtext), „Friondo KL Enni/SWD/Sparkasse DU“ (Nachtexte) per
  `angebotsprofile.seed_kl` (migrate.py), Vortext „Ihr individuelles
  Klimaanlagen-Angebot zum Festpreis“, Nachtext A ohne Monatsraten-Beispiel,
  Nachtext B mit „Hinweis zur Kältetechnik“ (R32, F-Gase-Verordnung (EU)
  2024/573) statt KfW-Hinweis, Nachtext C mit „Voraussichtlicher
  Ausführungszeitraum: ______“; alle KL-Texte sind Entwürfe für das Gegenlesen
  (A14), Wortlaut in ANGEBOTSTEXTE.md Abschnitt 9. PDF: Gruppe „Klimaanlage
  Bosch“ (editierbar), „EP.“, „19,00 % USt.“, kein Förderblock; Lieferschein
  zeigt Gruppen-Überschriften (spartenübergreifend); Protokoll-PDF rendert
  Einträge ohne Frage-ID (Seite „Auslegung“). Parametrierung: Tabelle
  „KL-Parameter“ mit Einheit, Import-Button, Lesesicht
  `/parametrierung/kl-logik` (Paketmatrix, Montagematrix, Kombinationen,
  Aktionen, Angebotsaufbau, KL-Artikel – nur Anzeige, AD nie EK), Filter
  „Sparte KL“ (Suchlink KL0), DB-Ampel-Zeile KL.
- **Kontrollfälle A–H** (Phase 116, `tests/test_kl_v24.py` + Agenten-Tests
  `test_kl_v24_import/_logik/_auslegung/_texte.py`, 135 KL-Tests): Fall A
  (Musterangebot) Netto 6.518,66 € exakt, USt/Gesamt 1.238,54 / 7.757,20 €
  (`Angebot.summen()` schneidet die USt seit Phase 26 ab – Musterangebot
  rundet kaufmännisch, Abweichung 0,01 € innerhalb der Plan-Toleranz, offene
  Rückfrage), `kl_json` Kombination „9+9+9“ → CL5000M 79/3 E; Fall B 5.495,00 /
  1.044,05 / 6.539,05 € exakt; C G6, D1 G3, D2 grün, D3 G2, E G1, F G4, G
  Validierung, H Dacharbeiten/§14a/kein Rollgerüst – alle wörtlich. Abnahme-
  PDFs ohne Kundendaten: `docs/klima/abnahme-A-AN-C-261021.pdf`,
  `abnahme-B-AN-C-261022.pdf`, `abnahme-C-protokoll.pdf`.
- **Grenzen v1 / Annahmen** (Details docs/nach-dem-update-v24.md): KA01/KA02
  gelten für alle Außengeräte gemeinsam; Innengeräte je Klasse gebündelt (nicht
  je Außengerät); keine Heizleistungs-Auslegung (KR03 nur Hinweis); Single
  Klasse 24 in 3200i = KL033 + KL029 [A1]; KE02-Meterzuschlag [A3]; §14a-Liste
  [A4]; CL7000M-Kombinationen [A5]; Flachdach Hinweis [A7]; Gewerbe Hinweis
  [A9]; Leitungsgrenze 15 m [A11]; Leistungsumfang-Text [A13];
  Auslegungszeile der Single-Sets nennt die generische 1. TAIFUN-Zeile
  („Klimaanlage Bosch Single-Split“, Rückfrage).

## Neu in v25 – Lead-Management V3 (abgestimmt 05.10.2026)

(Plan: PLAN_LEAD_V3.md, Phasen 118–121; Feedback-Runde Claudia Castro nach V2.
Umsetzung parallel durch sechs Agenten A–F (Navigation/Boards, Anrufliste/Nicht
erreicht, Kundenkartei/Autospeichern, Score aus/Terminassistent/Dashboard,
Integration/Tests, adversarialer Prüfer); Vorab- und Nacharbeiten an geteilten
Dateien zentral. Alles weiter im **Demo-Modus** `lead_freigabe_modus = admin`.
Entscheidungen und [ANNAHME]-Auflösung: docs/leadmanagement-entscheidungen.md
Abschnitt V3; Team-Hinweise: docs/nach-dem-update-v25.md.)

- **Navigation** (Phase 118, Makro `lm_nav(aktiv)` in `_nav.html`): linke
  Icon-Leiste (*v29: „Mehr …“ als Flyout, HV-Sicht nur Dashboard · Karte · To-Dos ·
  Handelsvertreter*) mit acht Einträgen Mein Dashboard · Hauptboard · Deals ·
  Kontaktiert · Karte · Infoabend · To-Dos · Handelsvertreter und „Mehr …“
  (Anrufliste, Kanban, Kalender, E-Mail-Vorlagen, Übersicht, Statistik Leads,
  Kanal-Report, Posteingang unklar, Import, Schnellanlage, Lead-Einstellungen).
  Nav-Keys `dashboard | hauptboard | terminiert | kontaktiert | karte | info |
  todos | handelsvertreter` bzw. `anrufliste | board | kalender | vorlagen |
  uebersicht | statistik | kanal_report | posteingang | import | neu |
  lead-einstellungen`; Alt-Keys werden abgebildet, unbekannte markieren „Mehr …“.
  Jede Seite markiert genau einen Eintrag (Kanban das gezeigte Board, Kartei das
  Board des Leads, Termin → Kalender, Cockpit → Übersicht). Icons lokal aus
  `_symbole.html` (neu: deals, aufgaben, einstellungen, griff, sortieren,
  zuruecksetzen); unter 900 px untere Icon-Zeile. `/lead-management/boards/haupt`
  leitet auf `/hauptboard`. Neue Seite **To-Dos** (`/lead-management/todos`,
  `lm_todos.py`/`lead_todos.py`): Sichten Meine offenen · Von mir vergeben ·
  Erledigt, Umschalter Alle | Fällig (`?faellig=1`), Anlegen inline mit
  Vorgangsbezug, Erledigen; Dashboard verlinkt dorthin.
- **Deals / Infoabend / Board-Namen**: Board „Terminiert“ heißt überall „Deals“
  (Titel, Menü, Kanban-Überschrift, Umschalter, Verschiebe-Meldung), „Info-
  Veranstaltung“ heißt „Infoabend“ (Menü, Titel, Kacheln, Gruppenüberschriften
  „Infoabend 05.11.2026“, Quellen-Anzeigename in `QUELLEN_START`/`QUELLEN_GRUPPEN`).
  Board-Namen kommen ausschließlich aus der neuen Spalte `board_label` im Blatt
  Status (`logik.board_label(board)`, Fallback Hauptboard/Deals;
  `lead_boards.board_label`, Jinja-Global `lm_board_label`). Pfade, Keys und
  Parameter (`/terminiert`, `/info-veranstaltung`, `info_*`, Quelle
  `info_veranstaltung`), das Phasen-Label „Terminiert“ und der Eingang/API
  bleiben unverändert; der DB-Datensatz `lead_quellen.name = Info-Veranstaltung`
  ist nicht migriert (R1: manuell unter Parametrierung → „Lead-Quellen &
  Kampagnen“ umbenennen; Dev-DB erledigt, Server-To-do in
  docs/nach-dem-update-v25.md).
- **Label „Kontaktiert“**: Blatt Status trägt für `in_kontaktierung` und
  `qualifiziert` dasselbe Label (gleiche Farbe); Phasen-Labels in Boards, Kanban,
  Kontaktiert, Kartei-Statuskette, Anrufliste, Dashboard, HV-Ansicht,
  Vorgangsakte und Trichter kommen nur aus `logik.status_zeile(phase).label`
  (`lead_boards.status_label/phasen_labels/phasen_mit_label`). Auswahlfelder
  führen das Label einmal (Wert `in_kontaktierung,qualifiziert`, Filter
  akzeptieren Phasenlisten), das Kanban fasst beide Phasen in der Anzeige-Spalte
  „kontaktiert“ zusammen (`KANBAN_ZUSAMMEN`), der Statistik-Trichter zeigt die
  Stufe „Kontaktiert“ als Kohorte (erster Kontaktversuch, erreicht oder
  qualifiziert im Zeitraum; Tooltip nach aktueller Phase; Terminquote ÷
  Kontaktiert). Interne Phasen, `lead_phase_berechnen` und Board-Zuordnung
  unverändert; Aktivitätstexte behalten die internen Phasennamen. Hinweis in der
  Parametrierung (Logik-Seite), dass zwei Phasen dasselbe Label tragen dürfen.
- **Spalten je Nutzer** (Hauptboard, Deals, Infoabend, Handelsvertreter;
  `benutzer_einstellungen` Key `boards_spalten`, Struktur
  `{"<board>": {"spalten": [{key, sichtbar, name}], "sort": {key, richtung}}}`,
  v23-Listen werden weiter gelesen): `lead_boards.spalten_fuer(session, benutzer,
  board)`, `sortierung_fuer`, `spalten_speichern(liste | sort | umbenennen |
  zuruecksetzen)`, Routen `GET/POST /lead-management/boards/spalten` (JSON).
  Bedienung in `lm_boards.js` (Makro `spalten_kopf` in `_tabelle.html`): Klick
  auf den Spaltenkopf sortiert auf/ab und wird gemerkt (serverseitig
  `zeilen_sortieren`, leere Werte ans Ende), Stift benennt um (leer = Standard),
  HTML5 Drag & Drop am Kopf verschiebt mit Platzhalter und speichert per fetch,
  Spaltenwähler „Spalten“ blendet ein/aus, „Zurücksetzen“ stellt den Standard
  her – alles nur für den angemeldeten Nutzer je Board. Standard-Spaltensatz:
  feste erste Spalte „Kundenname“ (Key `lead`, „Anrede Vorname Nachname“,
  `lead_boards.kundenname`), Anrede/Vorname/Nachname ausgeblendet und
  einblendbar; gespeicherte v23-Einträge mit sichtbaren Namensspalten bleiben.
  Infoabend konfiguriert unter Board-Key `info` (Kundenname/Status fest vorn,
  Ergebnis · Teilgenommen · Veranstaltung ohne Werkzeuge), HV-Ansicht unter
  `handelsvertreter` (Standard = v23-Spaltensatz, `STANDARD_SICHTBAR`; feste
  Spalte Vertreter); beide mit `data-lm-spalten-board` (nur Spaltenwerkzeuge,
  Zeilen bleiben bei `lm_info.js`/`lm_hv.js`). Spalte Score steht nur bei
  `score_aktiv` im Katalog.
- **Sticky-Filterleiste**: `.lm-filterblock` (Chip-Selects, Suche,
  Spaltenwähler, Sammelaktionen) liegt außerhalb des horizontal und vertikal
  scrollenden Tabellen-Containers `.lm-tabellen` und klebt unter der Kopfzeile
  (`top: var(--lm-kopf-fest)`, Höhe `--lm-tabellen-hoehe` von `lm_boards.js`
  gesetzt); Sticky-Tabellenkopf bleibt. Hauptboard, Deals, Infoabend; HV-Filter
  sticky ohne inneren Scroll-Container. Geprüft in der Chromium-Vorschau bei
  1366 px mit allen Spalten (Edge: manuelle Sichtprüfung offen). CSS nur als
  Blöcke „Phase 118/119/120“ in `lead_v2.css`.
- **Anrufliste** (`lead_anrufliste.daten`): die fünf Gruppen sind entfallen –
  EINE sortierte Liste `zeilen` mit Rang je Zeile (`_rang`/`RAENGE`): 0 SLA rot →
  1 SLA gelb → 2 fällige Wiedervorlagen/Rückrufe (nach Uhrzeit) → 3 Zurück-
  gestellte mit erreichtem Datum → 4 Rest nach Eingang (älteste zuerst), ohne
  Score-Komponente; Leiste „Reihenfolge“ (`lm-sortierung`) statt Gruppenköpfe.
  Schnellfilter-Chips bleiben; die Selects „Quelle“/„Einzelquelle“ sind durch
  das Mehrfach-Dropdown **„Vertriebskanal“** ersetzt (Parameter `kanal`, mehrfach
  oder kommagetrennt, Werte `kern.kanal_werte` + Kanäle der Liste, Farbpunkte aus
  `kanal_farben`; „Standard“ = ohne Kanal), die Zeile zeigt das farbige
  Kanal-Badge (`kanal_badge(kanal, farbe)`). Alt-Parameter `gruppe=` wird
  ignoriert, `quelle_id/quelle_typ/kampagne_id` filtern weiter (Abzeichen).
  Klasse-Select/-Spalte nur bei `score_aktiv = an`. Tasten 1–7 unverändert. Der
  tote V1-Helfer `_anruf_zeilen` ist entfernt.
- **Kundenkartei** (Phase 119, `lead_kartei.py`, `lm_kartei.py`, Templates
  `kartei.html` + `kartei_info.html` + `kartei_mitte.html` + `kartei_bloecke.html`
  + `kartei_dialoge.html`; `kartei_links/_rechts` entfallen): Kopf mit
  Kundenname, Kanal-/Interessen-Badges, Statuskette (`lead_kartei.phasen_kette`,
  Phasen mit gleichem Label = ein Schritt, Seitenzustände als roter Schritt),
  rechts oben Button „Terminierung“ (B8 unverändert, ausgegraut mit Tooltip der
  fehlenden Felder) und die runden Schnellaktionen Anrufen · E-Mail · Notiz ·
  Wiedervorlage. Darunter der **Kundeninfo-Block** (4 Spalten ab 1200 px, 2 ab
  900 px, 1 darunter): Anrede · Vorname · Nachname · Firma · Telefon (tel:) ·
  E-Mail (mailto) · Straße · PLZ · Ort · Vertriebskanal · Interessen · Objektart
  (+ Parteien, Rechnungsadresse bei MFH) · Innendienst · Außendienst ·
  Eingangsdatum · Wunschzeiten; Score/Klasse, Quelle/Kampagne und Einwilligungen
  sind aus der Kartei entfernt (bleiben im Eingang, in der Vorgangsakte und in
  Kanal-Report/Statistik). **Autospeichern**: `lm_kartei.js` postet bei blur/
  change JSON `{feld, wert}` an `POST /lead-management/lead/{id}/feld` →
  `{ok, feld, wert (normalisiert), meldung, geaendert, pflicht_offen,
  pflicht_anzahl, pflicht_keys, terminierung, adresse_vollstaendig}`;
  Validierung in `lead_kartei.feld_speichern` (PLZ 5 Ziffern, E-Mail, Telefon,
  Objektart, Parteien, Kanal, Interessen, Zuweisungen über
  `lead_v2.leadmanager_zuweisen/ad_zuweisen`), Fehler → HTTP 400 mit altem Wert,
  Häkchen 2 s, Dubletten client- und serverseitig unterdrückt, jede Änderung
  schreibt eine Aktivität typ `aenderung` „<Feld>: „alt“ → „neu““
  (Timeline-Gruppe „Änderungen“); Rechte wie bisher (`lead_v2.gate`, AD-Lesesicht
  ohne Formular). `POST /stammdaten` bleibt als noscript-Fallback. Reiter Termin
  (Standard) · Anrufnotizen · E-Mail-Verlauf · Timeline (`?tab=`), Reiter
  Qualifizierung/Vorgang entfallen. Blöcke in voller Breite Termine · Angebote ·
  Erfassungen · Projekt · Anhänge · To-Dos; der Block Termine lädt nach dem
  Seitenaufbau `GET /lead-management/lead/{id}/termin/vorschlaege.json`
  (`lead_termin.vorschlaege_json`: `{status: ok|adresse_fehlt|hv_lead|keine,
  hinweis, vorschlaege[{ad_id, ad_name, beginn, beginn_text, begruendung,
  umweg_min}], kandidaten, buchbar, pflicht_offen, aus_cache, berechnet_um,
  buchen_url}`, Top 5 (*überholt – seit v29 `vorschlaege_anzahl` = 3, erster „Ideal“,
  Kalenderansicht `kalender.json`*), Cache 10 Minuten je Lead und Sicht in
  `lead_termin.vorschlaege_cache`, `vorschlaege_cache_leeren(vorgang_id)` nach
  Adressänderung, komplett nach Buchung/Absage, `?neu=1` erzwingt) und zeigt
  „Vormerken“ (POST `/lead/{id}/termin`, `quelle=assistent`), „Adresse fehlt –
  Straße, PLZ und Ort eintragen“ (nach Autospeichern der Adresse Nachladen ohne
  Neuladen) oder „Lead liegt bei <Name> (Handelsvertreter), Terminierung durch
  den Vertreter“. Unter 900 px alles untereinander, Terminierung bleibt oben
  rechts. Der Lead-Kopf der Vorgangsakte (`_lead_kopf.html`) zeigt Labels aus
  `akte_kontext["status_labels"]` und keinen Score mehr.
- **Score und Qualifizierung abgeschaltet** (Phase 120): Parameter `score_aktiv`
  (Lead-Einstellungen, Standard „aus“, `lead_v2.score_aktiv(session)`) ist der
  zentrale Schalter: `lead_anlegen` ruft `score_vorlaeufig` nur bei „an“,
  `score_berechnen` liefert bei „aus“ den Bestand, `qualifizierung_abschliessen`
  schreibt keine Punkte/Klassen, `erfassungs_vorbelegung` liefert {},
  `erwartungswert`/`pipeline_wert` rechnen nur Sparten-Erwartungswert ×
  Phasen-Quote; keine Score-/Klassenanzeige in Kartei, Anrufliste, Boards,
  Kanban, Dashboard, HV-Ansicht, Statistik, Übersicht, Kanal-Report, Termin-
  Templates; Hinweis „Score C – Termin trotzdem buchen?“ entfällt. Routen
  `/lead/{id}/qualifizierung/{sparte}` bleiben erreichbar (GET Hinweisseite
  `qualifizierung_aus.html`, POST → Kartei `?tab=termin`), „Erreicht“ in der
  Anrufliste leitet bei „aus“ direkt auf `/lead-management/lead/{id}?tab=termin`
  (bei „an“ wie v23 in den Bogen); die Logik-Seite meldet die Blätter
  Qualifizierung/Scoring/Klassen als „vorhanden, nicht aktiv“. Daten und Blätter
  bleiben unverändert; bei „an“ verhält sich alles wie in V2.
- **Terminassistent ohne Handelsvertreter**: `lead_termin.kandidaten(...,
  benutzer)` lässt HV (`terminiert_selbst`) nur zu, wenn `benutzer.id == hv.id`
  („Handelsvertreter terminieren ihre Leads selbst“, `manuell_erlaubt`/
  `hv_manuell`); Leads mit `ad_id` = HV liefern `hv_lead`/`hv_hinweis` für den
  Innendienst, termin.html zeigt die HV als optgroup „Handelsvertreter (nur
  manuell)“ – die manuelle Buchung durch den Innendienst bleibt möglich
  (Annahme 6, bestätigt R8). Kontrollwert René Golaschewski: Innendienst sieht den HV-Hinweis,
  René nur eigene Vorschläge.
- **„Nicht erreicht“, „Mailbox“ und „Besetzt“ ohne Dialog** (Anrufliste,
  Kartei, Boards-Inline, Infoabend): Klick = `POST /lead-management/anruf/{id}`
  mit Zeitstempel jetzt, Versuch +1 und Stoppuhr-Dauer; **keine Wiedervorlage**
  (`naechste_aktion_am` unverändert, mitgesendetes `wiedervorlage_am` wird
  ignoriert). `kern.kaskade_anwenden` plant nur noch die Mails je Versuchsnummer
  (Blatt Kaskade Spalte `aktion`: 2./4. Versuch `nicht_erreicht`, letzter
  `disqualifiziert` + Nurture +30 Tage – *überholt: seit v29 nur `disqualifiziert`
  (`nach_letztem`), keine Nurture-Mail*), Spalte `wiedervorlage_nach` wird nicht
  mehr ausgewertet, der Übergang nach Nicht erreicht leert die Wiedervorlage;
  Sperre ab `versuche_max` bleibt. Meldungen „<Ergebnis> protokolliert (Versuch
  n)[ – Mail geplant].“; `GET /anruf/{id}/vorschlag` bleibt als Auskunft
  erreichbar, wird aber nicht mehr aufgerufen. Makro
  `anruf_dialoge(unq_gruende, zurueck_gruende, zurueck)` und
  `dialogOeffnen(art, id)` behalten ihre Signatur (Direktversand über
  `#lm-direkt-form`, Fallback `lmAnruf.ergebnisSenden`); „Rückruf gewünscht“ und
  „Kein Interesse“ behalten ihre Dialoge; Glocke `faellige_wiedervorlagen_melden`
  bleibt für manuelle Wiedervorlagen. Kontrollwert: 3 Versuche, letzter 14:05 →
  Aktivität mit Zeitstempel, Wiedervorlage leer, 3 Punkte orange, keine Mail.
- **Dashboard „Meine Arbeit“**: Wiedervorlagen zeigen nur noch manuell gesetzte;
  neue Kachel/Liste **„Ohne nächsten Schritt“** (*überholt – seit v29 vom Dashboard
  entfernt, Parameter `ohne_schritt_tage` ohne Wirkung*) (`lead_dashboard.
  ohne_naechsten_schritt`: eigene Leads der Phasen neu/in_kontaktierung/
  qualifiziert mit Versuch ≥ 1, ohne Wiedervorlage/Zurückstellung, ohne
  offenen Termin, letzter Anruf – ohne Anruf-Aktivität Erstkontakt bzw. Eingang –
  älter als Parameter `ohne_schritt_tage`, Standard 2, 0–365; älteste zuerst,
  Zeile mit Wiedervorlage-Formular, Links Terminassistent/Kartei).
  `zugeteilte` fasst Phasen mit gleichem Label zu einer Gruppe „Kontaktiert“.
- **Steuerdatei `leadmanagement_logik_v1.xlsx`** (Sicherung
  `diagnose/leadmanagement_logik_v1.vor_v25.xlsx`): Blatt Status – Label
  „Kontaktiert“ für beide Kontakt-Phasen, neue Spalte G `board_label`
  (Hauptboard/Deals; `StatusZeile.board_label`); neues Blatt „Lesehilfe“
  (Kaskade ohne Wiedervorlage, Status-Labels, Score nicht aktiv). Neue Parameter
  in `PARAMETER_START`: `score_aktiv = aus`, `ohne_schritt_tage = 2` (Lead-
  Einstellungen, protokolliert). Kein Migrationsschritt nötig (`migrate.py`
  zweimal gegen die Server-DB-Kopie: 2. Lauf ohne Änderungen).
- **Cache-Busting**: `templating._css_version()` hängt jetzt an der jüngsten
  Static-Datei (style.css, lead_v2.css, *.js) statt nur an style.css – nach
  einem Update ohne CSS-Änderung bekommen Browser sonst alte `lead_v2.css`/
  `lm_*.js` mit derselben `?v=`-Nummer.
- **Tests / Abnahme** (Phase 121): `tests/test_lead_v3.py` (21: Routen, Nav-
  Keys, Fälle a–k, Kontrollwerte, Prüfklasse L) + `test_lead_v3_boards.py` (17),
  `test_lead_v3_anruf.py` (7), `test_lead_v3_kartei.py` (22),
  `test_lead_v3_phase120.py` (23); zehn Alt-Tests bewusst angepasst
  (Begründungen in docs/leadmanagement-entscheidungen.md V3.3). Gesamtlauf
  `pytest tests -q` → **641 passed** (v24: 551), `tests/abnahme.py` 93/93,
  Voll-Crawl admin/innendienst/aussendienst gegen die Server-DB-Kopie ohne
  Absturz, Screenshots vorher/nachher (Kartei, Hauptboard, Anrufliste) als PNG
  in `docs/design-v25/` – nur Demo-Zeilen im Bild, „vorher“ aus einem Worktree
  des v24-Stands (`diagnose/v25_screenshots2.py`, Chrome headless).
- **Rückfragen R1–R12 beantwortet** (05.10.2026, alle wie vorgeschlagen – Tabelle
  V3.5 in docs/leadmanagement-entscheidungen.md): Quellen-Datensatz
  „Info-Veranstaltung“ wird manuell in „Infoabend“ umbenannt (Dev-DB erledigt,
  Server nach dem Pull), Parametrierung → „Lead-Quellen & Kampagnen“ zeigt
  „Score-Bonus (nicht aktiv)“ solange `score_aktiv = aus` (Werte bleiben); alles
  Übrige bleibt wie gebaut (eigene Spalten je Board, Aktivitätstexte intern,
  Besetzt ohne Dialog, Einstufung „zurückgestellt“ vor der SLA-Einstufung (Rang 3
  statt 0/1), Trichter-Kohorte, HV-Buchung über POST /termin
  erlaubt, Rückfall „Ohne nächsten Schritt“, Kanban markiert Board, kein
  Cockpit-Eintrag, API-Text unverändert). **Offen**: manuelle Sichtprüfung in
  Edge bei 1366 px (Drag & Drop, Mehrfach-Dropdown), Freischaltung
  `lead_freigabe_modus = alle` (eigener Plan).

## Neu in v26 – Heizreport-Anbindung & Pilot-Nebensachen (abgestimmt 05.10.2026)

(Plan: PLAN_PROJ_V5.md, Phasen 122–126; Heizreport-Doku `docs/heizreport/`
(openapi.json 2.4.0, docs.html, postman_collection.json, heizreport-CLAUDE.md) und
`docs/heizreport-api.md`; Entscheidungen/Annahmen A-1 … A-6 in
docs/projektierung-entscheidungen.md Abschnitt PLAN_PROJ_V5; Team-Hinweise und
Echtlauf-Checkliste in docs/nach-dem-update-v26.md. Umsetzung: Heizreport zentral,
Montageteam-Dropdown und Parametrierungs-Gliederung durch zwei parallele Agenten.
Projektierung weiter im eingestellten `freigabe_modus`.)

- **Heizreport-Client v2 (Phase 122, `app/heizreport_api.py`):** Parameter
  `heizreport_modus` = `v2` (Standard) | `generisch` (v17-Client bleibt erhalten).
  Modus v2: Basis-URL `https://heizreport.net/api/v2`, `Authorization: Bearer
  <Token>` (Parameter `heizreport_api_key`), JSON, Timeout 20 s, `konfiguriert()` =
  Token gesetzt; Endpunkte `GET /`, `/health`, `/reports`, `POST /reports/with-data`,
  `GET/PATCH /reports/{key}`, `GET /reports/{key}/results`,
  `GET /reports/{key}/pdf?type=heizreport`; nie `/api/v1`, Schlüssel nur aus
  `projektHeader.key`. Prozessweite Warteschlange (`_warten`: Lock + Zeitstempel,
  mindestens 600 ms Abstand), HTTP 429 → `Retry-After` (mindestens 1 s) abwarten
  und genau einmal wiederholen. Fehlerblock `{status, error, details{type, field}}`
  → Nutzer-Meldung „Heizreport: <error> (Feld <field>)“; 401/403/404/5xx/Timeout mit
  festen Texten (`fehler_meldung`). Jeder fehlgeschlagene Aufruf →
  Fehlerprotokoll (`fehlerprotokoll.eintragen_text`, Fehlertyp „Heizreport“) ohne
  Authorization-Header und ohne Tokenwert (per Test abgesichert). HTTP-Nahtstelle
  `_roh_anfrage` (auch PDF-Download), Uhr `_uhr`/`_schlafen` – in Tests gemockt.
  Verbindungstest: `GET /health` (ohne Token) → `GET /` → `GET /reports` →
  „Verbindung OK · API-Version <v> · <n> eigene Projekte (Gruppen: projekte a, leads
  b, api c, archiv d)“ bzw. „Heizreport erreichbar, aber Token abgelehnt (HTTP 401)“.
- **Parametrierung → Heizreport** (`/parametrierung/heizreport`, Admin, Router
  `app/routers/konfiguration_heizreport.py`, Template `konfiguration/heizreport.html`):
  Zugang (Modus, Token maskiert „gesetzt – leer lassen = unverändert“ + „Token
  entfernen“, Verbindung testen über `POST /parametrierung/heizreport/test`),
  Kennzahlen (Phase 123, JSON-Parameter `heizreport_kennzahlen` mit Vorlage,
  Validierung und Vorschau „welche Felder würden gesendet“), Ablage
  (`heizreport_pdf_ordner`, Vorbelegung „Montagedokumente“), Portal-Link
  (`url_heizreport`, aus den Projektierung-Einstellungen umgezogen), Ergebnis-Pfad
  (`heizreport_pfad_heizlast`), aufklappbar „Generischer Client (v17)“. Änderungen
  landen im Parameter `heizreport_protokoll` (letzte 30, Token nur als
  gesetzt/entfernt). Der alte Block „Heizreport-API (Phase 93)“ in den
  Projektierung-Einstellungen ist entfallen (Hinweis-Link). migrate.py: Parameter
  `heizreport_modus`, `heizreport_kennzahlen`, `heizreport_pdf_ordner`,
  `heizreport_pfad_heizlast`; Gewerk-Spalten `heizreport_angelegt_am`,
  `heizreport_pdf_am` (`db._NACHTRAEGLICHE_SPALTEN`).
- **Projekt anlegen und vorbelegen (Phase 123):** `heizreport_api.projektdaten_v2`
  liefert `{"projectData": {…}}` (nur skalare Werte, leere weggelassen):
  `projektName` = „<Nachname>, <Vorname> – <PR-Nummer>“, `projektPostleitzahl`
  (Pflicht – fehlt sie: „Ausführungsort ohne PLZ“), `projektBaujahr` (O02),
  Kundenfelder `anrede/vorname/name/telefon/email`, Ausführungsort
  `strasse/hausnummer/plz/ort` (Hausnummer = letzter Ziffernblock + Zusatz [A-2]),
  `bemerkungen` wörtlich „Friondo <PR> · Angebot <AN> · verkauft: <Steckbrief
  leistungsklasse> · Energieträger alt: <A01>, Baujahr Heizung <A02>, Verbrauch <A03>
  kWh · Warmwasser über WP: <N02> · Solarthermie: <A10> · Heizlast lt. Erfassung:
  <A15> kW“ (Teile ohne Wert entfallen). Die Kennzahlen `projektArtHeizung`,
  `projektAlterHeizung`, `projektTrinkwasser`, `projektWaermeerzeugerSolarArt` und
  `projektJahresverbrauch` werden **nur** über `heizreport_kennzahlen` gesendet
  (`null` = unbekannt; Verbrauch nur bei bestätigter Einheit kWh, keine Umrechnung
  [A-3]); `projektWaermeerzeugerSolarStatus = true` bei A10 „Ja…“. Ermittlung der
  Kennzahlen nur manuell mit `scripts/heizreport_kennzahlen.py` (PATCH je Wert am
  Testprojekt, 600 ms Abstand, Enter je Wert, JSON-Vorlage am Ende; Ablauf
  docs/heizreport-api.md Abschnitt 3). Aufgabe „Heizlastberechnung liegt vor“ (Paket
  feinplanung_vot, `api`/`heizreport`) im Modus v2 mit Token: „Heizreport-Projekt
  anlegen“ (nur ohne Schlüssel; `POST /reports/with-data`, Erfolg = HTTP 201,
  Schlüssel → `heizreport_projekt_key`, `heizreport_angelegt_am`, Verlauf
  „Heizreport-Projekt <key> angelegt (vorbelegt: <Felder>)“; nicht idempotent:
  Timeout → `GET /reports` und Suche nach `projektName`, Treffer → „nach Timeout
  gefunden“, sonst „Anlage unklar – im Heizreport-Portal prüfen, dann Schlüssel von
  Hand eintragen“), aufklappbar „Schlüssel von Hand eintragen“ (9 Buchstaben, Prüfung
  `GET /reports/{key}`, 404 = abgelehnt), danach „Heizreport öffnen ↗“
  (`url_heizreport`, Schlüssel daneben zum Kopieren [A-4]), „Heizlast abrufen“,
  „Heizreport-PDF ablegen“ und „Verknüpfung lösen“ (Pflichtbegründung; leert
  Schlüssel und `heizreport_angelegt_am`, Heizlast-Felder bleiben, Verlauf
  „Heizreport-Verknüpfung gelöst: <Begründung>“). Zweiter Klick auf Anlegen bei
  bestehender Verknüpfung → 409. Routen: `POST /projektierung/gewerk/{id}/heizreport/
  {anlegen|ergebnis|pdf|schluessel|loesen}` (fetch/JSON wie die übrigen Aufgaben-
  Aktionen; 409 mit `rueckfrage` bei der PDF-Sicherheitsabfrage). Ohne Token wie
  bisher Link + Upload.
- **Heizlast zurückholen, Abgleich, PDF (Phase 124):** „Heizlast abrufen“ =
  `GET /reports/{key}/results` ohne Zusatzparameter; 422 `calculation_unavailable`
  → „Heizreport-Projekt noch nicht berechenbar – Räume und Heizflächen im
  Heizreport-Portal erfassen, dann erneut abrufen“ (Gewerk unverändert). Erfolg:
  Gesamtheizlast in W über den Punktpfad `heizreport_pfad_heizlast` (Vorbelegung
  `results.summary.heatLoad` – **am Referenzprojekt zu bestätigen**, Schlüssel lag
  nicht vor), ersatzweise bekannte Kandidaten, dann Summe der Raumheizlasten
  (`results.roomHeatLoads`, zuletzt FBH-Räume) [A-5]; kW kaufmännisch auf eine
  Nachkommastelle → `heizlast_kw`, `heizlast_datum`, `heizlast_quelle = "Heizreport
  API"`, Aufgabe erledigt, Verlauf „Heizlast aus Heizreport übernommen: <x,y> kW“.
  Abgleich mit der verkauften Leistungsklasse über die Paketmatrix-Heizlastspalte
  (`klasse_fuer_heizlast`, dieselbe Zuordnung wie `konfigurator.leistungsklasse`):
  Abweichung → Verlaufseintrag `art = hinweis` am Gewerk, angezeigt an der Aufgabe
  und im Heizlast-Block der Akte, Text wörtlich „Heizlast <x,y> kW laut Heizreport →
  Leistungsklasse <K>; verkauft: <Steckbrief> – Auslegung prüfen (Nachtrag oder
  Freigabe)“; keine automatische Änderung an Angebot/Steckbrief/Stückliste; gleiche
  Klasse → Verlauf „Heizlast passt zur verkauften Klasse“. FP-L01/FP-L02 werden mit
  kW und „Heizreport“ vorbelegt, solange unbeantwortet (Badge „aus Heizreport“ in
  `feinplanung.html`) [A-6]. „Heizreport-PDF ablegen“: `GET /reports/{key}/pdf?type=
  heizreport` erzeugt bei Heizreport ein Dokument – erster Klick direkt, bei
  gesetztem `heizreport_pdf_am` Sicherheitsabfrage „Bei Heizreport wird ein weiteres
  Dokument erzeugt – trotzdem erneut abrufen?“ (ohne `bestaetigt=1` → 409);
  signierter Link (`file.url`/`linkToDocument`, nur Host heizreport.net) sofort ohne
  Token geladen, nicht gespeichert, Datei `Heizreport-<PR>-<Sparte>-<JJJJMMTT>.pdf`
  (zweites Dokument `…-2.pdf`) im Galerie-Ordner `heizreport_pdf_ordner`,
  `heizreport_pdf_am = jetzt`, Verlauf „Heizreport-PDF abgelegt“, Aufgabe erledigt.
  Nicht angebunden (Stufe 2): Räume per API, Webhook `pdf.generated` (öffentliche
  HTTPS-Adresse), Bilder, Wärmepumpen-Check (`type=check`), Projektpasswort.
- **Benutzer → Montageteam als Dropdown (Phase 125, A-1):** Auf der Benutzerseite
  (`templates/benutzer/liste.html`) steht in der Hauptzeile und im Formular „Neuer
  Benutzer“ statt der Chip-Reihe ein `<select name="team_ids">` mit „– kein Team –“
  und allen aktiven Teams (Typ montage zuerst, dann sub, je alphabetisch; die Route
  liefert `order_by(typ, name)`, das Template sichert montage-zuerst ab). Sichtbar nur
  bei Rolle Montage – Live-Umschaltung über `benTeamsUmschalten`; Nicht-Montage-
  Benutzer ohne Zuordnung haben kein Dropdown im HTML, beim Umschalten klont das JS
  eines aus `<template id="ben-team-vorlage">`. Hat ein Benutzer mehrere Teams,
  erscheint je Team ein Dropdown untereinander; „+ weiteres Team“ (`benTeamHinzu`)
  ergänzt eines, „×“ (`benTeamWeg`) entfernt eines (beim letzten Dropdown
  ausgeblendet – dort „– kein Team –“ wählen). Gespeichert wird unverändert über
  `POST /benutzer/neu` bzw. `/benutzer/{id}/aendern` (`teams_dabei=1`, `team_ids`
  mehrfach; leere Werte ignoriert, Dubletten per `set()` dedupliziert – Route
  unverändert). Die Zusatzrollen-Häkchen in der Detailzeile sind schlichte
  `kontrollfeld`-Labels; `ben-chip`/`chips` kommen im Benutzer-HTML nicht mehr vor
  (die zugehörigen CSS-Regeln in style.css sind verwaist). Teams-Seite (Spalte
  Mitglieder) und Go-live-Prüfpunkt „Montageteams mit Mitgliedern“ unverändert.
  Test: `tests/test_benutzer_teams_v26.py` (8 Tests).
- **Parametrierung neu gegliedert (Phase 125):** `/parametrierung` ist jetzt eine
  Verteilerseite mit Suchfeld (clientseitig, Titel + Kurztext) und fünf
  Bereichskarten – Allgemein · Angebotstool · Projektierung · Lead-Management ·
  System & Protokolle. Alle bisherigen Adressen bleiben; jeder Link der alten
  Button-Reihe kommt genau einmal vor, Admin- und Lead-Bedingungen wie zuvor, der
  Go-live-Eintrag trägt ein Badge „n/11 grün“. Die Inline-Abschnitte der alten
  Übersicht liegen auf zwei neuen Seiten: `/parametrierung/angebotstool`
  („Angebotstool-Einstellungen“: DB-Ampel inkl. je Sparte, E-Mail-Versand mit
  Versand-Erkennung (#versand), Kombi-Versand, gewerkeübergreifende Artikel,
  Fern-Signatur, Abgelehnt-Prozess mit Gründen und Prüflauf-Protokoll (#ablehnung),
  Lösch-Protokoll (#loeschprotokoll)) und `/parametrierung/logik` („Logik & Importe“:
  Quelle/zuletzt eingelesen, Validierungsbericht, Neu einlesen, Tabellen Eingelesene
  Logik/Fragen/Angebotsaufbau/KfW/PV/Klimakonfigurator mit KL-Import). Im Router
  liefert `_parametrierung_kontext(session)` den bisherigen Kontext, drei Routen
  verteilen ihn auf die drei Templates – keine neue Logik. `POST
  /parametrierung/einstellungen`, `/ablehnungsgruende`, `/neu-einlesen` und der
  KL-Import kehren per Referer auf die aufrufende Seite zurück (`_zurueck_ziel`: nur
  Pfade unter /parametrierung, ohne Query; Fallback Übersicht, bei Neu-einlesen und
  KL-Import /parametrierung/logik), `?meldung=` wie bisher. Projektierung-
  Einstellungen: gleiche Route, gleiche Feldnamen und POST-Verarbeitung, aber in
  Karten gegliedert mit sticky Abschnitts-Navigation (Freigabe & Pilot · Vorlauf-
  Ampel · Standard-Verantwortliche · Benachrichtigungs-Mails · Storno-Gründe ·
  Galerie · Portal-URLs · UGL/Collin · Outlook-Kalender · Terminbestätigung ·
  Kundenmail BzA, dazu Ordnervorlage und Mail-Protokoll #mailprotokoll) und einem
  sticky „Speichern“ (Aktionsleiste des Editors v14); der Heizreport-Block (Phase 93)
  und das Feld `url_heizreport` sind nach `/parametrierung/heizreport` umgezogen
  (Hinweis-Links an den alten Stellen), Portal-URL-Parameter werden nur gesetzt,
  wenn das Feld im Formular liegt. CSS: Block „v26 … Parametrierung“ am Ende von
  style.css (`.param-*`, `.pe-*`). Test: `tests/test_parametrierung_v26.py` (13 Tests).
- **Tests / Abnahme (Phase 126):** `tests/test_heizreport_v26.py` (19 Tests:
  Warteschlange 600 ms mit gemockter Uhr, 429 genau einmal wiederholt,
  Verbindungstest wörtlich, Fehlerprotokoll ohne Token, Parametrierungs-Seite,
  Body `projectData` wörtlich, Kennzahlen, Anlage 201/Timeout-Suche/409, Schlüssel
  von Hand, Verknüpfung lösen, Heizlast mit Abgleich-Hinweis, Raumsumme, 422,
  PDF-Ablage mit Rückfrage und `…-2.pdf`), `test_parametrierung_v26.py` (13),
  `test_benutzer_teams_v26.py` (8); angepasst: `test_projektierung_v4.py::
  Phase93Heizreport` (Modus generisch, neue Testroute), `test_kl_v24.py` und
  `test_kl_v24_logik.py` (Inhalte der alten Übersicht liegen auf den neuen Seiten;
  KL-Import kehrt nach Logik & Importe zurück). HTTP in allen Tests gemockt
  (`heizreport_api._roh_anfrage`), kein Netzzugriff. Gesamtlauf, Abnahmeskript,
  migrate.py zweimal gegen die Server-DB-Kopie und Voll-Crawl (admin, innendienst,
  aussendienst, montage): siehe Gesamtübersicht der Übergabe.
- **Offen / Rückfragen:** Referenzprojekt-Schlüssel und Token (nur bei Andreas;
  Ergebnis-Pfad und Kennzahlen am Referenz-/Testprojekt bestätigen, Checkliste in
  docs/nach-dem-update-v26.md), Kontrollwerte des Plans zur Leistungsklasse
  (9,2 kW → „10 kW“) widersprechen der Paketmatrix-Heizlastspalte (8,0–9,9 kW → 7 kW)
  – Tests folgen der Steuerdatei, „Umkreisprüfung“ bei Heizreport, Stufe 2 (Räume,
  Webhook, Bilder, Wärmepumpen-Check).

## Hotfix 06.10.2026 (Verbindungspool)

**Störung:** Auf dem Server trat `sqlalchemy.exc.TimeoutError: QueuePool limit of
size 5 overflow 10 reached, connection timed out, timeout 30.00` auf. Ursache (aus
dem Code, die Server-Logs lagen im Projektordner nicht vor): SQLite läuft über einen
QueuePool mit 5 + 10 Verbindungen; die `RollenMiddleware` hielt je Anfrage eine
eigene Sitzung (und damit eine Verbindung) über die gesamte Dauer bis nach
`call_next`, und Endpunkte wie die Terminvorschläge der Kundenkartei (v25, je
Kartei-Aufruf) hielten ihre Request-Sitzung während Netz-I/O (Routing-Matrix,
Geocoding, Outlook-Frei/Belegt, Heizreport, Graph-Mails – bis zu 60 s Timeout).
Bei mehreren gleichzeitigen Nutzern waren damit 15 Verbindungen belegt, weitere
Anfragen warteten 30 s und scheiterten.

**Regel „keine offene Sitzung während Netz-I/O“:** Vor jedem Netzaufruf (urllib,
Graph/msal, ORS/Google/Nominatim, monday, Heizreport) alle benötigten Daten lesen,
dann `app.db.verbindung_freigeben(session)` (= `commit`, beendet die Transaktion und
gibt die Pool-Verbindung frei; die Session bleibt nutzbar, Objekte behalten ihre
Werte – `expire_on_commit=False`), dann der Netzaufruf, danach wieder normale
DB-Arbeit (die nächste Abfrage holt eine Verbindung). Hintergrundläufe mit eigener
`SessionLocal()` lesen, schließen, rufen das Netz ohne Session und öffnen zum
Zurückschreiben eine neue kurze Session. Die Freigabe committet – nie mitten in
einer halb fertigen Änderung aufrufen. Beim Code-Review: jeder neue Netzaufruf ohne
Freigabe davor ist ein Fehler.

**Maßnahmen:**
- `app/db.py`: `create_engine(pool_size=20, max_overflow=40, pool_timeout=10)` –
  Anfragen scheitern nach 10 s mit klarer Meldung statt 30 s zu hängen;
  `pool_status()` und `verbindung_freigeben(session)`.
- `app/auth.py` RollenMiddleware: Sitzung nach den Rollen-, Glocken- und
  Modulabfragen und VOR `call_next` geschlossen (`finally` bleibt als Sicherung);
  `request.state.benutzer` ist ein abgelöstes Objekt mit allen Spalten (Benutzer hat
  keine Relationships, Routen laden ihn bei Bedarf über `session.get`).
- Freigabe vor Netz-I/O eingebaut in `routing.matrix_fuellen`,
  `geocoding.geokodieren` (auch im 5-Minuten-Hintergrundlauf je Adresse),
  `kalender.frei_belegt/termin_schreiben/termin_aendern/termin_loeschen` (Rumpf
  vorher gelesen), `heizreport_api._anfrage_v2/_anfrage` und PDF-Download sowie in
  den Mail-/Sync-Modulen (siehe unten). Die automatischen Terminvorschläge der
  Kundenkartei rechnen damit ohne gehaltene Verbindung (Routing-Matrix und
  Outlook-Abfragen laufen nach der Freigabe) und nutzen weiter ihren
  10-Minuten-Cache (`lead_termin.vorschlaege_cache`).
- Hintergrundläufe und Mail-/Graph-Aufrufe (monday_sync, mail_sync, lead_parser,
  lead_mail, benachrichtigungen, outlook_kalender, terminmail, sub_mail, bza, golive,
  monday_rueckspielung, die monday-Übersicht der Parametrierung sowie die
  Versand-Routen in routers/angebote.py und routers/vorgaenge.py) lesen alle
  benötigten Daten aus der Session, rufen unmittelbar vor jedem Netzaufruf (Graph
  inkl. msal-Token, monday-GraphQL) `verbindung_freigeben(session)` auf und
  schreiben erst danach zurück; in Schleifen (je Angebot, Termin, Sub-Eintrag,
  Quelle, Mail) steht die Freigabe vor JEDEM Aufruf. Token und angemeldetes Konto
  der Hintergrundläufe (mail_sync.sync, terminmail/sub_mail.antworten_abgleichen,
  outlook_kalender.ruecklesen) werden vor `SessionLocal()` ermittelt. Folge:
  `benachrichtigungen.mail_senden` – und damit `kern.benachrichtigen` mit
  Sofort-Mail – committet die bis dahin anstehenden Änderungen des Aufrufers;
  `kern.benachrichtigen` committet deshalb selbst VOR dem Mail-Schritt, damit ein
  Commit-Fehler den Aufrufer wie bisher abbricht statt still zu verschwinden.
  Hintergrundschleifen committen je Durchlauf (best effort je Eintrag).
- **Nebenbefund des Lasttests:** parallele Anfragen fügten dasselbe Routing-Paar
  bzw. dieselbe Geocode-Adresse gleichzeitig in den Cache ein („UNIQUE constraint
  failed“ in `routing_cache`/`geocode_cache`, bisher ein 500er für den zweiten
  Nutzer). `routing._cache_schreiben` und `geocoding.geokodieren` schreiben jetzt
  per SQLite-Upsert (`INSERT … ON CONFLICT DO UPDATE`) und laden die Zeile danach
  mit `populate_existing()` frisch.
- `app/fehlerprotokoll.py`: `ist_pool_timeout()`; bei erschöpftem Pool nur
  Datei-Log `data/fehler.log` („Pool erschöpft – nur Datei-Log“, kein
  Tabellen-INSERT, der selbst auf den Pool warten würde); `engine.pool.status()`
  steht in jedem Eintrag (Datei-Log und Spalte `traceback`, auch bei
  `eintragen_text`); `app/main.py` meldet „Datenbank-Verbindungen ausgelastet –
  bitte in einer Minute erneut versuchen (Fehler-Nr.)“; Parametrierung →
  Fehlerprotokoll zeigt den Pool-Status oben.
- **Backup (Übergangslösung bis PLAN_V17):** `scripts\backup-nacht.bat` sichert die
  Datenbank über `db.taegliches_backup()` (SQLite-Backup-API, eine Datei je Tag,
  30 Tage) und spiegelt `data\backups`, `data\angebote`, `data\projekte` per robocopy
  nach `BACKUP_ZIEL` aus der `.env` (Vorlage in `.env.example`, Standard
  `D:\Backup\Angebotstool`; Log `data\backup-nacht.log`). Geplante Aufgabe
  „Friondo Backup“ täglich 02:30 auf dem Server (Pfad dort
  `C:\Users\kdadmin\Desktop\Angebotstool`; Variante A lokales Laufwerk als SYSTEM,
  Variante B Netzfreigabe unter Benutzerkonto mit `/RU … /RP *`) – Anleitung in
  docs/nach-dem-update-v26.md.
- **Antworten Andreas (06.10.2026):** Server-Logs und DB-Sicherung kommen nach dem
  Update nach `diagnose\fehler-server-2026-10-06.log` bzw.
  `diagnose\server-2026-10-06\angebotstool.db` (gitignored); erstes Auftreten,
  laufende Version und betroffene Routen folgen als Nachtrag in diesem Abschnitt.
  Der frühere Commit vor Sofort-Mails bleibt im Hotfix; die saubere Lösung
  (Ausgangs-Warteschlange `mail_ausgang`, Versand nach dem Commit durch einen
  Scheduler-Lauf) ist PLAN_V17 Phase 128. Betrieb: auf dem Server läuft das Tool als
  Konsolenfenster aus `start.bat` (keine Aufgabe, kein Dienst) – nach `update.bat`
  Fenster schließen und `start.bat` neu starten, erst dann gelten die Pool-Parameter.
- **Diagnose-Nachtrag 07.10.2026:** Die Server-Logs (`diagnose\fehler-server-2026-10-06.log`,
  DB-Kopie) wurden nicht nachgeliefert (Entscheidung Andreas: offen lassen, kein weiterer
  Aufwand). Die Ursache gilt als bestätigt: aus dem Code (RollenMiddleware hielt je Anfrage
  eine zweite Verbindung bis nach `call_next`; Terminvorschläge/Routing/Outlook/Graph
  hielten die Request-Sitzung während Netz-I/O) und durch `tests/test_pool_hotfix.py`
  (40 parallele Anfragen reproduzierten die Belegung von 37 Verbindungen – mehr als die
  früheren 5 + 10). Erstes Auftreten und betroffene Routen auf dem Server bleiben ohne
  Logdatei unbekannt. Seit v27 sind Pool-Belegung und Antwortzeiten je Route dauerhaft
  messbar (`data\log\zugriff.log`, Parametrierung → Betrieb, `/health`), die Invariante
  Pool ≥ Threads + Scheduler + 5 wird beim Start geprüft; eine Wiederholung der Störung
  würde im Zugriffsprotokoll (Pool-Checkouts je Anfrage) und als Warnung in `/health`
  sichtbar. Thema abgeschlossen.
- Tests: `tests/test_pool_hotfix.py` – 40 parallele Anfragen (Kundenkartei +
  Terminvorschläge, ORS-Matrix gemockt mit 3 s) ohne TimeoutError, Welle 2 belegt
  während des Netzaufrufs keine Verbindung, `verbindung_freigeben` gibt die
  Verbindung frei, Middleware-Sitzung vor dem Endpunkt geschlossen, Pool-Timeout nur
  im Datei-Log, Pool-Status in Einträgen und auf der Seite;
  `tests/test_pool_hotfix_mail.py` misst für die Mail-/Sync-/Outlook-Pfade
  (benachrichtigungen, golive, lead_mail, lead_parser, monday_sync, outlook_kalender,
  mail_sync, terminmail, sub_mail) `pool.checkedout() == 0` im Moment des gemockten
  Netzaufrufs (drei Schleifen ohne passende Dev-DB-Daten werden übersprungen).

## Neu in v27 – Betriebsreife für 50 Nutzer (abgestimmt 06.10.2026)

(Plan: PLAN_V17.md, Phasen 127–132; baut auf dem Hotfix 06.10.2026 auf. Alle
Datenbankänderungen sind additiv – der v26-Code läuft auf einer v27-Datenbank
weiter, Rückweg `rollback.bat --nur-code`. Rollout nur im Wartungsfenster.)

- **Ist-Aufnahme und Inventar (Phase 127):** `docs/betrieb.md` – Abschnitt „Ist
  10/2026“ (Server läuft als Konsolenfenster aus `start.bat` in der Sitzung
  kdadmin = Risiko Nr. 1, Pfad `C:\Users\kdadmin\Desktop\Angebotstool`, Firmennetz
  `http://192.168.35.4:8000`, Außendienst über WireGuard-VPN – vorhanden) und die
  Inventartabelle aller `SessionLocal()`-Stellen, Scheduler-Läufe, Netzaufrufe aus
  Anfragen, Importe und PDF-Erzeugungen (Modul | Auslöser | Intervall | Netzaufruf |
  hält Sitzung während Netz-I/O | Schreibtransaktion | Maßnahme). Jeder Plan mit
  neuen Netzaufrufen ergänzt diese Tabelle (Fachliche Regeln → Betrieb).
- **Zugriffsprotokoll mit Dauer** (`app/zugriffslog.py`): die RollenMiddleware
  schreibt je Anfrage eine Zeile nach `data\log\zugriff.log` (RotatingFileHandler
  10 × 10 MB; Zeit | Benutzer-ID | Rolle | Methode | Pfad ohne Query | Status |
  Dauer ms | Pool-Checkouts zu Beginn – keine Formdaten, keine Namen; /static und
  /health ausgenommen). `zugriffslog.auswerten(24)` (60 s zwischengespeichert,
  höchstens die jüngsten 40 MB) liefert Anfragen/Minute, p50/p95 je Route (Top 20,
  `/angebote/{id}`-Normalisierung), Anteil > 2 s, langsamste 20 Anfragen, Pool-Spitze.
- **Lastmodell und Zielwerte** [ANNAHME, Phase 127/131]: `docs/lasttest-v27.md`
  Abschnitt 1/2 – 50 Nutzer, 35 gleichzeitig (15 AD mobil, 12 ID, 6 LM, 4
  Projektierung/Montage), Denkzeit 5–15 s; Zielwerte p95 Listen/Akten ≤ 1,5 s,
  Editor ≤ 1,0 s, Angebots-PDF ≤ 4 s, Protokoll-PDF ≤ 3 s, Terminvorschläge ≤ 6 s,
  0 TimeoutError, 0 „database is locked“, Pool-Spitze ≤ 60 %, Fehlerquote < 0,1 %.
- **`def`-Routen statt `async def` (Phase 128):** alle 379 Endpunkte laufen im
  Starlette-Threadpool (`WORKER_THREADS`, Standard 64, in `main.lifespan` über
  `anyio.to_thread.current_default_thread_limiter().total_tokens` gesetzt);
  Formulare `anfrage.formular(request)`, JSON `anfrage.json_lesen(request)`, Uploads
  `datei.file` – `galerie.speichern` streamt Datei-Objekte in 1-MB-Blöcken auf die
  Platte (`_datei_schreiben`). Umstellungsskript (AST-gestützt, Kommentare bleiben):
  `diagnose/v27_patches/async_umstellen.py`. Die Middleware (`auth.RollenMiddleware`)
  erledigt ihre Datenbankarbeit in `_laden()` im Threadpool, schließt die Sitzung VOR
  `call_next` (Hotfix) und reicht Werte für Jinja-Globals ohne Request-Kontext über
  `anfrage.KONTEXT` (ContextVar) durch – `lm_demo_badge` öffnet keine zweite Sitzung
  mehr (Befund B7); der Wartungshinweis liest mit der Middleware-Sitzung (B8).
- **Pool, Threads, Invariante:** `.env`-Schlüssel `DB_POOL_SIZE` (20),
  `DB_POOL_OVERFLOW` (**70** – Plan 40; mit 64 Threads und 13 Scheduler-Läufen
  verlangt die Invariante 64 + 13 + 5 = 82 Verbindungen; *seit v29 14 Läufe mit
  `lead-mail-abruf`: 64 + 14 + 5 = 83 ≤ 90*), `DB_POOL_TIMEOUT` (10),
  `WORKER_THREADS` (64). `db.pool_invariante(anzahl_scheduler)` wird beim Start
  geprüft, protokolliert (`data\fehler.log`, Betriebs-Seite, /health „Pool-Invariante
  verletzt“) und bei Verletzung ins Fehlerprotokoll geschrieben.
- **`db.kurz()`** (Kontextmanager, commit bei Erfolg / rollback bei Fehler / immer
  close) für Scheduler und Hilfsfunktionen; Anfragen behalten `get_session`.
- **Scheduler-Rahmen `app/scheduler.py`:** `scheduler.registrieren(name, intervall_s,
  funktion, beschreibung=, start_verzoegerung_s=, taeglich_um=, aktiv=)` je Lauf;
  Single-Flight-Sperre, Zufallsversatz 0–30 s beim ersten Start, Laufzeitmessung,
  letzter Fehler (mit Traceback in `data\fehler.log` – kein `except Exception: pass`
  mehr), Zähler, Tabelle `scheduler_status`; `ausfuehren(name)` synchron (Tests),
  `im_hintergrund_ausfuehren(name)` (Knopf „jetzt ausführen“, eigener Thread),
  `starten_alle()`/`stoppen()` nur in `main.lifespan`. Läufe: `monday-sync` 900 s
  (aktiv nur mit Token), `mail-sync` 900 s (Graph eingerichtet), `ablauf-pruefung`
  24 h, `benachrichtigungen` 300 s, `lead-parser` 120 s (parser_modus an),
  `leadmanagement` 300 s, `geocoding` 300 s, `lead-mail` 60 s, **`mail-ausgang`**
  60 s, `backup` täglich 02:30, `sqlite-pflege` täglich 02:40, `betrieb-wache` 300 s,
  `login-protokoll` täglich 03:10; *seit v29 zusätzlich `lead-mail-abruf` 120 s
  (Antworten/Bounces aus termin@, aktiv nur mit Graph) – 14 Läufe*. Inaktive Läufe
  melden „inaktiv (Grund)“ – kein Fehler.
- **Sitzungsdisziplin der Läufe (Agent A):** `mail_sync.sync`, `sub_mail`/
  `terminmail.antworten_abgleichen`, `outlook_kalender.ruecklesen`, der monday-
  Scheduler-Pfad, `geocoding.hintergrund_lauf`, `lead_mail.versand_job` arbeiten mit
  `db.kurz()` (lesen → Sitzung zu → Netz → kurze Sitzung schreiben); geteilte
  Funktionen mit Request-Session behalten die Hotfix-Freigabe (`geokodieren`,
  `postfach_abrufen`, `_graph_senden`, `mail_senden`, `_quelle_syncen`). Blöcke mit
  Commit: Geocoding je Adresse, Lead-Mail je Eintrag, Glocken/Reaktivierung/Löschlauf
  je 50 (`leadmanagement.BLOCK_GROESSE`), monday je 200 Items und je Quelle
  (`monday_sync.BLOCK_GROESSE`); Teilschritte je für sich abgesichert, Ausnahme nur,
  wenn alle Teilschritte (bzw. alle monday-Quellen) scheitern. **Geocoding-Backoff:**
  `geocode_cache.versuche`/`stand` – nach dem 1. Fehlversuch 1 h, nach dem 2. 6 h, ab
  dem 3. 24 h (`geocoding.backoff_pause`, `erneut_faellig`); Erfolg/manueller Pin
  setzen 0; Vorgänge mit `geocode_status = fehler` werden nach der Pause wieder
  versucht (vorher nie – Befund), Kundenkartei/Terminassistent überspringen „fehler“
  nicht mehr dauerhaft (in der Pause nur eine Cache-Abfrage). Löschlauf mit
  Mengenabfragen (`loeschlauf_kandidaten`) in 50er-Blöcken.
- **Mail-Ausgangswarteschlange `mail_ausgang`** (Antwort Andreas 06.10.2026 zum
  Hotfix): `benachrichtigungen.sofort_versenden` reiht Sofort-Mails in derselben
  Transaktion wie die Glocke ein (Tabelle `MailAusgang`: empfaenger, betreff, text,
  art, status offen|gesendet|fehler, versuche, fehler_text); der Lauf `mail-ausgang`
  sendet jede Minute bis zu 50 Einträge (lesen → Sitzung zu → Graph mit
  Fallback-Absender → kurze Sitzung je Eintrag), nach 3 Fehlversuchen „fehler“ mit
  Protokollzeile, ohne Graph-Einrichtung sofort „fehler: Graph nicht eingerichtet“.
  Der Hotfix-Commit mitten in `projektierung.benachrichtigen` entfällt damit (Befund
  B9); `/health` warnt ab 50 offenen Mails, die Betriebs-Seite zeigt offen/Fehler 24 h.
- **Importe in Blöcken (Agent D):** `import_preisliste`, `import_pv`, `import_klima`
  committen je `BLOCK = 200` Zeilen, `bestandsimport.importieren` je `BLOCK = 10`
  [ANNAHME: 95 ms je Bestandszeile gemessen ≈ 1 s Schreibsperre]; vor jedem
  Block-Commit Zwischenstand am `Bestandsimport`-Datensatz (`_zwischenstand`),
  `abgeschlossen_am` bleibt bei Abbruch leer („abgebrochen (Teilstand)“). Jeder
  Import ist je Schlüssel ein Upsert und nach Abbruch wiederholbar; Verwaiste werden
  erst nach allen Zeilen deaktiviert; „Logik neu einlesen“ schreibt nichts (nur
  Cache). Laufende Importe: `betrieb.import_markieren("Preisliste" |
  "PV-Positionslisten" | "Klima-Positionslisten" | "Logik-Excel" | "Bestandsimport" |
  "monday-Sync")` – Betriebs-Seite und `/health` (`importe`). **Hinweis vor dem Start**
  (nur Routen): `import_preisliste.import_hinweis(session, schluessel)` („Dauer etwa
  <n> s – während des Imports können Speichern-Aktionen anderer Nutzer kurz warten;
  empfohlen außerhalb der Kernzeit“), Bestätigung `import_bestaetigt(form)` (Feld
  `bestaetigt`, sonst Redirect „Bitte den Hinweis bestätigen“), Dauer
  `import_dauer_merken(session, schluessel, start)` → Einstellung
  `import_dauer_<schluessel>` (Standards preisliste 20, pv 10, klima 10, logik 15,
  bestand 30, monday 30 s). Betroffene Routen: `/artikel/import`, `/artikel/import-pv`,
  `/parametrierung/artikel/kl-import`, `/parametrierung/neu-einlesen` (Knöpfe auf
  Übersicht, Logik & Importe, Klima-Logik mit `confirm()` + verstecktem Feld),
  `/parametrierung/bestandsimport/ausfuehren`, `/leads/sync` (monday-Vollabgleich).
  Tests, die Import-Routen posten, senden `bestaetigt=1`; `migrate.py`-Aufrufe
  verlangen keine Bestätigung.
- **SQLite-Pflege und Indizes:** Lauf `sqlite-pflege` 02:40 (`db.wal_pflege()`:
  `PRAGMA wal_checkpoint(TRUNCATE)` + `PRAGMA optimize`), WAL-Größe in /health und
  Betriebs-Seite, `busy_timeout` bleibt 5000 ms. Indexprüfung mit `EXPLAIN QUERY PLAN`
  (`scripts/index_pruefung.py --data <Kopie>`, Bericht
  `diagnose/test_v27_index/index_bericht.txt`): Befund – die im Modell mit
  `index=True` deklarierten Indizes auf nachträglich per ALTER TABLE ergänzten Spalten
  (`erfassungen.vorgang_id`, `erfassungen.lead_id`, `angebote.vorgang_id`,
  `angebote.projekt_gewerk_id` u. a.) hatte `create_all` nie angelegt → `db.indizes_anlegen()`
  legt jetzt alle Modell-Indizes nach und zusätzlich `_INDIZES`
  (`ix_v27_*`: vorgaenge.lead_phase, angebote.status, angebote(archiviert, status),
  erfassungen.status, erfassungen.archiviert, erfassungen.angebot_id,
  lead_aktivitaeten(vorgang_id, erstellt_am), benachrichtigungen(benutzer_id, gelesen_am),
  vot_termine.beginn, vot_termine(status, typ), vorgaenge.wiedervorlage_am,
  vorgaenge.naechste_aktion_am, leads.benutzer_id, leads.vot_datum, aufgaben.status,
  aufgaben(verantwortlich_id, status), login_protokoll(benutzer_id, zeit)); `migrate.py`
  meldet neue Tabellen und Indizes.
- **Betrieb (Phase 129):** `scripts\dienst-installieren.bat` erkennt NSSM
  (`nssm.exe` neben dem Skript/im Projektordner/`C:\Friondo\`) → Dienst
  `FriondoAngebotstool` (AppDirectory = Projektordner, Autostart, Neustart nach 5 s,
  Logs `data\log\dienst-out.log`/`dienst-err.log` mit 10-MB-Rotation, Konto SYSTEM),
  sonst Aufgabe „Friondo Angebotstool“ (ONSTART, SYSTEM) plus Wächter-Aufgabe alle
  5 Minuten (`scripts\waechter.ps1`: `/health`, Neustart bei Ausfall,
  `data\log\waechter.log`); beendet ein laufendes Konsolenfenster nach Rückfrage,
  entfernt die Hotfix-Aufgabe „Friondo Backup“. `scripts\dienst-neustart.bat`,
  `dienst-status.bat`, `dienst-entfernen.bat`; `update.bat`/`rollback.bat` erkennen
  Dienst/Aufgabe/Konsole, `rollback.bat --nur-code`; `start.bat` warnt auf dem Server;
  `scripts\smoke.bat` (+ `smoke.py`: /health, Login-Cookie, Startseite, Erfassungs- und
  Angebotsliste, Vorgangsakte, Angebots-PDF, Hauptboard, Projektboard – je 200 und
  < 3 s, `data\log\smoke-<Datum>.txt`); `scripts\restore-test.bat` (jüngste Sicherung →
  `diagnose\restore_<Datum>`, migrate, Crawl `--max-ids 20`, Protokoll
  `docs\betrieb\restore-<Datum>.txt`, gitignored); `scripts\health-pruefen.ps1` für
  fr-wts-02. **`GET /health`** (ohne Anmeldung, `app/routers/betrieb.py`): JSON mit
  status ok|warn|fehler, version, commit (aus `.git`), db/db_ms (eigene sqlite3-Probe,
  nicht über den Pool), pool, threads, scheduler[], backup_letztes/backup_ziel_status,
  wal_mb, uptime_s, importe[], mail_ausgang, schreibsperre_max_ms/locked, prozess
  (RSS über psapi, CPU-Sekunden), gruende[]; warn bei Pool > 70 % (oder erschöpft),
  Scheduler > 2 Intervalle ohne Lauf, letztes Backup > 26 h, kein Backup-Ziel,
  Spiegelung fehlgeschlagen, Pool-Invariante verletzt, > 50 offene Mails; HTTP 503
  nur bei fehler. **Betriebs-Seite** `/parametrierung/betrieb` (Admin, Template
  `konfiguration/betrieb.html`): Kacheln, Wartungshinweis-Formular, Scheduler-Tabelle
  (mit Stand vor Neustart aus `scheduler_status`) und „jetzt ausführen“ (Hintergrund),
  „Backup jetzt“, „SQLite-Pflege jetzt“, Zugriffsstatistik 24 h. **Admin-Glocke:**
  Lauf `betrieb-wache` alle 5 Minuten – bei warn/fehler eine Glocke an alle Admins
  (art `system`, höchstens eine je Stunde). **Backup:** Lauf `backup` 02:30
  (`betrieb.backup_lauf`): `db.taegliches_backup()` + Spiegelung von `backups`
  (90 Tage am Ziel), `angebote` (/MIR), `projekte` (/MIR) und `.env` per robocopy
  nach `BACKUP_ZIEL` (Log `data\backups\ziel.log`), Ergebnis in Einstellung
  `backup_letztes`; Fehlschlag → Fehlerprotokoll + Admin-Glocke; ohne Ziel nur lokal.
  **Proxy/HTTPS-Vorbereitung:** `HTTPS_AKTIV=1` → Cookie `secure` (immer `httponly`,
  `samesite=lax`), `BASIS_URL` (Mails, ICS, Signatur-Links – `BASIS_URL_AUS_ENV` geht
  der Einstellung `signatur_fern_basis_url` vor), `PROXY_IPS` für die Start-Skripte
  (`--proxy-headers --forwarded-allow-ips`), `/health` ohne Login. Serverressourcen-
  Empfehlung in `docs/betrieb.md` (4 vCPU / 8 GB / SSD, `data\` lokal, NTP,
  Virenscanner-Ausnahme).
- **Login-Härtung (Phase 130, `app/auth.py` + Agent B):** `pin_hash_v2` =
  PBKDF2-HMAC-SHA256 (200.000 Runden, 16-Byte-Salz, Format
  `pbkdf2_sha256$Runden$Salz$Hash`); Login: v2 gesetzt → PBKDF2, sonst SHA-256
  (`pin_hash`), stille Umstellung beim nächsten Erfolg; `pin_setzen` schreibt BEIDE
  Spalten (Rollback-Sicherheit). PIN-Regeln für neue PINs (`pin_regel_pruefen`):
  nur Ziffern, Mindestlänge 4 (Andreas 07.10.2026; Parameter `pin_mindestlaenge` 4–12),
  Sperrliste (`pin_sperrliste`, Standard 123456/111111/…), keine Wiederholung, keine
  Zahlenfolge, kein Jahreszahl-Muster 19xx/20xx. Fehlversuchssperre: 5 Fehlversuche in
  15 Minuten (seit dem letzten erfolgreichen Login) → 15 Minuten Sperre
  (`fehlversuche`, `gesperrt_bis`, Text wörtlich laut Plan); je IP höchstens 30
  **Fehl**versuche in 15 Minuten [ANNAHME statt „Versuche“ – gemeinsame Adressen];
  Tabelle `login_protokoll` (zeit, benutzer_id, benutzer_name, ip_kurz a.b.c.x, erfolg,
  grund; 90 Tage, Lauf `login-protokoll`). Cookie v2 `v2:<id>:<Ablauf>:<Sitzungszähler>:
  <HMAC>` mit Ablauf (Büro 12 h, Außendienst/Montage mit Häkchen „Auf diesem Gerät
  angemeldet bleiben“ 30 Tage – Parameter `sitzung_stunden_buero`/`sitzung_tage_mobil`
  [ANNAHME]), `benutzer.sitzungszaehler` („Alle Sitzungen beenden“), v26-Cookies werden
  abgewiesen (einmal neu anmelden). `pin_wechsel_noetig` (Erst-Login, Admin-Reset,
  Standard-Admin einer leeren DB) → Middleware leitet auf `/pin-wechsel`.
  Oberfläche (Agent B): `/login` mit Häkchen (*seit Nachtrag 2 zweispaltig mit Foto, Häkchen
  nur bei Außendienst/Montage sichtbar*), `GET/POST /pin-wechsel` (jede Rolle, Menü
  „PIN ändern“), Benutzerverwaltung mit Filter Rolle/aktiv, Spalte „Letzter Login“,
  „Sperre aufheben“, „Alle Sitzungen beenden“, Einstellungen-Block, CSV-Import
  `/benutzer/import` (`app/benutzer_import.py`: `Name;Rolle;E-Mail;Team;Vertriebskanal`,
  Vorschau, Start-PINs einmalig angezeigt, nicht gespeichert), Login-Protokoll
  `/benutzer/login-protokoll`; Styles in `app/static/login_v27.css`. Tests:
  `tests/test_v27_login.py`; `tests/conftest.py` setzt den IP-Zähler je Test zurück.
- **Befunde aus Lauf 1 des Lasttests, behoben vor Lauf 2:** (1) `lead_termin.vorschlaege`
  rief die Routing-Matrix zweimal (hin/zurück) – jetzt EIN gebündelter Aufruf
  (Quellen = Ziele = Lead + Punkte, `routing.matrix_fuellen(session, alle, alle)`);
  (2) `leadmanagement.parameter_holen` lief auf dem Deals-Board 835-mal je Seite
  (je eine Abfrage) – jetzt je Transaktion zwischengespeichert (`session.info`,
  geleert bei `after_begin`, gepflegt von `parameter_setzen`): Deals-Board 856 → 29
  Abfragen, 840 → 420 ms (Einzelaufruf). Nicht geändert (Befunde für einen eigenen
  Plan): PDF-Erzeugung CPU-gebunden (fpdf2, 4 gleichzeitige Renderings ≈ 3× Einzelzeit),
  „Versand vorbereiten“ = 7 sequenzielle Graph-Aufrufe, Deals-Board rendert alle Zeilen
  ohne Blättern, Bestands-Erfassungen ohne spätere optionale Fragen (O13/O09/A20) gelten
  für „Angebot erzeugen“ als unvollständig (Rückfrage).
- **Lasttest (Phase 131, Agent E):** `scripts/lasttest_server.py` (uvicorn 8001 gegen
  `diagnose/test_v27/data`, Lifespan mit allen Läufen, externe Dienste mit 2 s
  simulierter Latenz) + `scripts/lasttest.py` (httpx, Thread je virtuellem Nutzer,
  Profile `normal` | `schreibsturm` | `stress`, `--nutzer --dauer --seed --latenz
  --bericht`, Messung je Route p50/p95/p99/Fehler, /health-Polling: Pool-Spitze,
  WAL, Schreibsperre, RSS/CPU; Bericht `docs/lasttest-v27.md`, Rohdaten
  `diagnose/test_v27/lasttest_<zeit>.json`). Ergebnis und PostgreSQL-Entscheidung:
  `docs/lasttest-v27.md` Abschnitt 4. **Ergebnis 06.10.2026:** Lauf 2 (50 Nutzer, 35
  aktiv, 20 min, 6.602 Anfragen) erfüllt alle Zielwerte – p95 Listen/Akten 494 ms,
  Editor 291 ms, Angebots-PDF 1.887 ms, Protokoll-PDF 649 ms, Terminvorschläge
  4.206 ms, 0 TimeoutError, 0 „database is locked“, Pool-Spitze 17,8 %, Fehlerquote
  0 %; Schreibsturm 190/190 Positionen korrekt; Stressstufe (100 Nutzer) zeigt die
  Ein-Schreiber-Grenze (Schreibsperre bis 5,9 s, 7 × „Datenbank kurz belegt“,
  Reserve-Faktor 0,69). **Entscheidung: SQLite bestätigt**, kein PostgreSQL-Umstieg in
  v27; Reserve ≈ 40 % über dem Lastmodell, nächster Lasttest nach dem nächsten großen
  Modul.
- **Rollout-Regeln (Phase 132):** Wartungshinweis (Einstellungen `wartung_von`,
  `wartung_bis`, `wartung_text`; Banner-Wortlaut „Wartung heute von <von> bis <bis>
  Uhr – bitte Arbeit bis dahin speichern. Das Tool ist in dieser Zeit kurz nicht
  erreichbar.“ für alle Rollen und auf /login, `betrieb.wartungshinweis`, 60-s-Cache
  in der Middleware), Standardfenster Dienstag 22:30–23:30
  (`betrieb.naechstes_wartungsfenster`). Rollback-Probe auf der DB-Kopie
  (`diagnose/v27_patches/rollback_probe.py`, Worktree `diagnose/wt_v26` = da9df30):
  v26 gegen v27-DB – Login mit alter und unter v27 geänderter PIN, Angebotsliste, PDF,
  Hauptboard, Anrufliste = 200, v27-Cookie abgewiesen; danach v27 wieder ok. Runbook
  `docs/betrieb.md`, IT-Übergabe `docs/betrieb-it-uebergabe.md`, Team-Hinweise
  `docs/nach-dem-update-v27.md`; `UMZUGS-BRIEFING.md` Abschnitt 2 um das
  Wartungsfenster ergänzt; `docs/mobilzugriff.md` als umgesetzt (Variante A)
  gekennzeichnet.
- **Tests v27:** `tests/test_v27_sitzungen.py` (Wächter-AST-Test über `app/`:
  Netzaufruf nur nach Freigabe/close/commit der Sitzung, Fixpunkt über Aufrufketten,
  Ausnahme-Marker `netz-ohne-sitzung-ok`; 40 parallele Terminvorschläge mit 3-s-Mock
  ohne gehaltene Verbindung; Pool-Invariante, `kurz()`), `tests/test_v27_betrieb.py`
  (/health, Betriebs-Seite, Wartungsbanner, Scheduler-Rahmen, Zugriffslog, Backup mit
  Spiegelung, SQLite-Pflege, Indizes, Mail-Ausgang), `tests/test_v27_scheduler.py`
  (Agent A: Registrierung ohne Threads, Single-Flight, Status-Tabelle, Backoff, 1.000
  Geocoding-Adressen ≤ 1 s Schreibsperre, Blöcke), `tests/test_v27_login.py` (Agent B),
  `tests/test_v27_importe.py` (Agent D). `tests/test_pool_hotfix.py` prüft die
  Pool-Werte jetzt gegen `db.POOL_SIZE/MAX_OVERFLOW/POOL_TIMEOUT` (Zeitgrenze 30 s je
  Welle, CPU-Last durch parallele Läufe).
- **Nachtrag 07.10.2026 (Antworten Andreas auf die Rückfragen der Gesamtübersicht):**
  Wartungsfenster **Dienstag 22:30–23:30**; PIN-Mindestlänge 4; Admin-Zugang zu jedem Konto
  über `POST /benutzer/{id}/anmelden-als` (Cookie 2 h [ANNAHME], Login-Protokoll Grund
  `admin_zugang:<Admin>`, nicht bei offenem Pflichtwechsel); NSSM erlaubt (nssm.exe nach
  `scripts\`); `BACKUP_ZIEL` vorerst `D:\Backup\Angebotstool` (Fallback C:), Netzlaufwerk mit
  Dienstkonto nachgelagert; **Bestands-Erfassungen:** `konfigurator.naechste_pflichtfrage`
  (überspringt `OPTIONALE_FRAGEN` O09/O13/A20 und Fragen mit „optional“/„leer lassen“ im
  Text) in `/erfassung/{id}/pruefen`, `…/absenden` und den Erfassungslisten-Sichten – der Bogen
  selbst nutzt weiter `naechste_frage`; **mail_sync** nur „Versand vorbereitet“/„Versendet“
  der letzten `ABGLEICH_TAGE` = 90 Tage; Geocoding-Backoff gibt nach `BACKOFF_MAX_VERSUCHE`
  = 10 Fehlversuchen auf (manueller Pin setzt zurück); `ablauf-pruefung` täglich 06:30;
  Lasttest-Zielwerte unverändert, „Versand vorbereiten“ ohne Zielwert; Benutzer-Import ohne
  CSV-Download der Start-PINs, inaktive Benutzer nicht automatisch reaktiviert.
- **Nachtrag 2 (08.10.2026 – Klima-Versand, E-Mail-Vorlage je Sparte, Anmeldeseite; PLAN_V17
  Abschnitt „Nachtrag 06.10.2026“, umgesetzt im Durchlauf v28/v29, ein gemeinsamer Commit):**
  Blatt „Anhänge“ der Live-Excel trägt statt der Platzhalterzeile `Bosch Climate 3200i.pdf`
  (Regel „wenn Sparte = KL“, Bemerkung „Gerätebroschüre Bosch Climate 3200i (v27)“; Sicherung
  `diagnose/konfigurator_logik_v5.vor_nachtrag2.xlsx`) – ein KL-Angebot (Profil Standard)
  hängt Unternehmenspräsentation, Ratenkauf-Broschüre und Bosch Climate 3200i an, Enni/SWD
  ohne Ratenkauf, WP/PV unverändert. Befund zur fehlenden Unternehmenspräsentation: im Code
  keine Lücke (`anhaenge.fuer_angebot` prüft „immer“ unabhängig von Sparte/Profil, Einzel- und
  Kombi-Versand nutzen die volle Logik); einziger stiller Pfad war eine nicht gefundene Datei
  (nur Hinweis in der Versand-Meldung) – `app/anhaenge.py` sucht Dateien jetzt tolerant
  (Groß-/Kleinschreibung, Unicode-NFC/NFD, Leerzeichen; `_datei_suchen`) und bietet
  `fehlende_dateien(logik)`; die Betriebs-Seite zeigt fehlende Anhang-Dateien als Kachel.
  **E-Mail-Vorlage je Sparte** (`app/mail_vorlagen.py`): Parametrierung → E-Mail-Vorlagen hat
  Reiter Standard · WP · PV · KL · WB (`?sparte=`), Ablage `mail_vorlage_sparte_<SPARTE>_betreff/
  _text`; Reihenfolge beim „Versand vorbereiten“: Vorlage des Außendienstlers → Sparten-Vorlage
  des Angebots (`konfigurator_typ`) → Standard (`vorlage_laden(session, benutzer_id, sparte)`,
  Quelle „Sparten-Vorlage KL“ in der Meldung); Kombi-Versand behält seine Vorlage.
  `migration_sparten` (migrate.py, Marker `migration_nachtrag2_sparten`) legt die vier
  Vorlagen einmalig aus der Standard-Vorlage an: KL „Wärmepumpen(-)angebot“ →
  „Klimaanlagen(-)angebot“, „Wärmepumpe“ → „Klimaanlage“; PV → „PV-Angebot“ / „PV-Anlage“;
  bei PV/KL werden Sätze mit `{eigenanteil}`/`{foerderung}` entfernt (Meldung je Satz) und
  die Platzhalter liefern dort leer; WB = Kopie des WP-Textes (Wortlaut von Andreas am
  08.10.2026 bestätigt); **WP bekommt keine Kopie** – WP nutzt die Standard-Vorlage
  (Antwort Andreas 08.10.2026, eine im ersten Lauf angelegte unveränderte WP-Kopie entfernt
  die Migration wieder, Marker `migration_nachtrag2_sparten_wp`; Versand-Meldung „Standard-
  Vorlage“). Streudatei `anlagen/unternehmenspraesentation.pdf` (1 KB, ohne Inhalt) in der
  Arbeitskopie gelöscht – auf dem Server ebenfalls entfernen.
  **Anmeldeseite** (`anmeldung/login.html`, `login_v27.css`, `static/anmeldung-energiehaus.jpg`):
  zweispaltig nach Muster SingleKey ID – links Logo, „Anmeldung“, Benutzer, PIN, Häkchen
  „Auf diesem Gerät angemeldet bleiben“ (nur bei Außendienst/Montage eingeblendet,
  `data-mobil` aus `auth.MOBILE_ROLLEN`), Knopf, darunter die Fehlermeldungen aus `auth`;
  rechts das Energiehaus-Foto bildschirmhoch (`object-fit: cover`); unter 900 px eine Spalte
  mit Kopfbild (180 px), unter 500 px ohne Foto; nur Tokens, keine externen Schriften;
  Login-Logik, Feldnamen, Wartungsbanner unverändert. Screenshots
  `docs/design-v27/anmeldung-vorher.png` / `-nachher*.png`. Tests `tests/test_v27_nachtrag2.py` (16).

## Neu in v28 – Projektierung V6 Pilot-Feedback 1 (abgestimmt 06.10.2026)

(Plan: PLAN_PROJ_V6.md, Phasen 133–139; umgesetzt am 08.10.2026 im gemeinsamen
Durchlauf mit dem v27-Nachtrag 2 und v29 – EIN Commit. Alle Datenbankänderungen sind
additiv (`aufgaben.entfaellt_grund`, `projekt_termine.zweck`, Tabelle `termin_besetzung`);
der v27-Code läuft auf der v28-Datenbank weiter. Die v27-Regeln gelten: `def`-Routen,
keine offene Sitzung während Netz-I/O, Scheduler-Rahmen, Inventar in `docs/betrieb.md`.
Entscheidungen: `docs/projektierung-entscheidungen.md` Abschnitt „PLAN_PROJ_V6“.)

- **Parametrierung → Projektierung-Einstellungen:** Abschnitt „Board & Wächter“
  (`waechter_modus` warnen | sperren, Standard warnen, Änderung protokolliert im Parameter
  `einstellungs_protokoll` – Verlauf unten auf der Seite) und „Terminvorschläge“
  (`montage_dauer_tage_standard` 5, `vorschlag_vorlauf_wochen` 4, `montage_startadresse`
  Firmensitz Arnold-Overbeck-Str. 63-65, 47139 Duisburg [ANNAHME], `vorschlag_outlook` aus –
  Stufe 2 nur angelegt). Live-Excel `projektierung_logik_v1.xlsx`: Blatt „Aufgabenpakete“
  mit den Bedingungen/Optionen der Phase 133 (BzA/BnD `foerderung:ja`, Öltank
  `steckbrief:oeltank=ja`, Gerüst `steckbrief:geruest=ja`, Elektro-Team
  `planung_elektro.3=erfolgt über Friondo`, Anzahlung als Auswahl + `montagevorbereitung.1=
  geschrieben`, Restarbeiten/Abweichungen als Auswahl), Blatt „Formulare“ (Phase 138) und neues
  Blatt „Lesehilfe“ (Bedingungen, Optionen, Wächter, Formular-Typen); Sicherung
  `diagnose/projektierung_logik_v1.vor_v28.xlsx`.
- **Wächter „warnen“ (Phase 133, `app/projektierung.py`):** `kern.waechter_modus(session)`;
  `phase_wechseln` behält Signatur/Rückgabe: warnen = Wechsel immer möglich, Verlauf „… – mit
  offenen Punkten: <Liste>“ (+ „– Begründung: <Text>“); sperren = Override nur mit Begründung
  wie bisher; rückwärts in beiden Modi nur mit Begründung; „abgeschlossen“ nur über „Rechnung
  freigeben“ (in beiden Modi hart). `waechter_bloecke`/`waechter_details` liefern die offenen
  Punkte je Aufgabe für `GET /projektierung/gewerk/{id}/waechter?ziel=` (JSON `modus,
  rueckwaerts, offen[{text, aufgabe_id, pflicht}], begruendung_pflicht`; Dialoge „Phase
  ändern“ in Akte und Board: Häkchen „erledigt“, Knopf „entfällt“, Begründung Pflicht nur laut
  JSON). **„entfällt“ mit Grund:** `aufgaben.entfaellt_grund`, Routen `POST …/aufgabe/{id}/
  entfaellt` (Grund Pflicht, 400 ohne Grund) und `…/wieder-aufnehmen`, Badge in Akte und
  „Meine Aufgaben“; Auswahl-Optionen ohne `*` tragen die Option als Grund; Ampel/Wächter/
  Kacheln zählen `entfaellt` nicht. **Bedingungen:** `sichtbar_wenn` kennt `foerderung:ja|nein`
  (`bza.ist_gefoerdert`, unbekannt = sichtbar); `steckbrief:`/`foerderung:` werden an der
  Aufgabe gespeichert und von `abhaengige_pruefen` nachgezogen („entfällt“ mit Grund
  „Bedingung nicht erfüllt (<Bedingung>)“, wieder „offen“ nur bei automatischem Grund);
  Hook `foerderung_schritte_nachziehen` (= `bedingungen_nachziehen`, aufgerufen aus den
  Förder-Routen des Angebots-Editors); „Logik prüfen“ meldet unbekannte Formen
  (`projektierung_logik.sichtbar_wenn_pruefen`).
- **Board (Phase 134):** volle Breite nur auf Projektierungs-Seiten (`main.breit.pj-voll`,
  `app/static/projektierung_v28.css` – Portal/Lead-Seiten behalten `breit` wie bisher
  [ANNAHME P1-2] – *überholt seit Nachtrag 08.10.2026: volle Breite für alle `main.breit`-Seiten
  über `style.css`, Sonderregel `.pj-voll` entfallen*), Spalten `flex: 1 1 0; min-width 240 px`
  mit eigenem senkrechten Scroll und sticky Kopf, Board-Höhe per JS (min. 480 px – *seit
  Nachtrag 08.10.2026 nur ab 900 px Viewport-Höhe, sonst 320 px*), Dummy-Scrollbalken `#pj-hscroll`
  über dem Board (synchron), Shift + Mausrad; Drag & Drop öffnet `dlg-phase-board` (offene
  Punkte per JSON, `POST …/phase-drop` antwortet JSON `{ok, meldung, phase, projekt_status}`,
  Karte wandert ohne Neuladen, Zähler/Kacheln aktualisiert); Drop unterminiert → terminiert
  öffnet den Termin-Dialog, umgekehrt Hinweis „Termin in der Projektakte löschen (Block
  Termine)“. Kontrollwerte ohne Playwright: `diagnose/v28_patches/p1_screenshots.py` (Chrome
  headless, DevTools) – 1 920 px: 7 Spalten, kein Seiten-Scroll; 2 560 px: 9 Spalten;
  1 366 × 768: Mindesthöhe 480 px greift (*seit Nachtrag 08.10.2026 ohne Seiten-Scroll*).
  Bilder `docs/design-v28/`.
- **Termine (Phase 135):** EIN Dialog (`templates/projektierung/_termin_dialog.html`, Makro
  `termin_dialog`, JS in `projektierung.js`) für Montage (WP) · Elektro-Montage · Sub-Einsatz ·
  Feinplanung VOT · Abnahme · Sonstiges (`projekt_termine.zweck` wp/elektro/sub);
  `kern.termin_speichern` ist die einzige Anlage-/Bearbeiten-Funktion (`team_termin_zuweisen`
  und `POST …/team-termin` bleiben als Wrapper/Alias), Routen `POST …/gewerk/{id}/termin`,
  `…/termin/{id}/bearbeiten`, `…/termin/{id}/loeschen` (Pflichtgrund, Outlook-Storno best
  effort, Besetzung mit, „Montageteam zuweisen“ wieder offen); JSON `{ok, meldung, konflikte}`
  bei Accept JSON. **Besetzung je Termin** (`termin_besetzung`, Team = Vorlage):
  `besetzung_ids/map/namen/setzen`, `team_mitglieder_ids`, `montage_benutzer`; Kalender-Drag
  belegt bei Teamwechsel neu, wenn die Besetzung der alten Vorlage entsprach, sonst „Besetzung
  beibehalten (von Hand gesetzt)“; `terminstatus_map` nur `zweck in (wp, leer)`; Konflikte je
  Person (`person_konflikte`, Warnung, kein Verbot). Block „Termine“ in der Akte (Art · Datum ·
  Team/Person · Besetzung · Kunde · Outlook · Aktionen), Zählerwechsel darunter; Personen-Liste
  Projektierung + Innendienst + Admin (bestätigt 08.10.2026, kein Außendienst). **Terminvorschläge Stufe 1**
  (`kern.terminvorschlaege`, `GET …/terminvorschlaege.json`): Vorlauf `vorschlag_vorlauf_wochen`,
  Dauer `montage_dauer_tage_standard`, UGL-Lieferdatum + 1 AT, montags [ANNAHME], je
  Montage-Team 5 freie Fenster (26 Wochen), Umweg über `app/routing.py` (Startadresse
  `montage_startadresse`), ohne Routing-Anbieter „–“; Netz nur nach `verbindung_freigeben`.
  `migration_v28` (migrate.py): zweck-Backfill, Besetzung aus Team-Mitgliedern, `sichtbar_wenn`
  am Altbestand.
- **Notizen über alle Phasen (Phase 136, `app/notizen.py`):** Der Notizen-Chat des Vorgangs
  (`VorgangsNotiz`, v10) ist die einzige Notizspur von Lead bis Montage. Gemeinsames Makro
  `notizen_chat(ctx)` in `templates/_komponenten.html` (Kontext aus `notizen.kontext(session,
  vorgang_id, benutzer, limit=, post_url=, hinweis=, nur_lesen=, herkunft=, zurueck=)` bzw.
  `kontext_projekt(session, projekt, benutzer)`), Chat-Optik v14, Kennzeichen Projektierung/
  Vertrieb/Lead/Montage aus `herkunft` (`notizen.KENNZEICHEN`), eigene Einträge rechts, Textarea
  4 → 12 Zeilen, Strg + Enter, Senden per fetch (Route `POST /vorgaenge/{id}/notiz`, JSON
  `{"ok", "eintrag": {id, benutzer_name, zeit "TT.MM.JJ HH:MM", text, kennzeichen,
  kennzeichen_klasse}}`, 403/400 mit `meldung`). Rechte `notizen.schreiben_erlaubt`: ID/Admin
  überall, AD bei eigenen Vorgängen, Projektierung bei Vorgängen mit Projekt, Leadmanagement
  bei sichtbarem Lead-Modul, Hauptrolle Montage nur lesen; Einträge unveränderlich. Eingebunden
  in Vorgangsakte, Projektakte (Reiter Verlauf, Systemverlauf eingeklappt; Kommentare über
  `notizen.kommentar_speichern`, `herkunft = projektierung`; ohne Vorgang bleibt der
  Projektverlauf; aufgabenbezogene Kommentare bleiben im Projektverlauf – bestätigt 08.10.2026), Kundenkartei
  (Block „Notizen“, `herkunft = lead`) und Montage-Backend (nur lesen). Migration
  `notizen.migration_v28_notizen` kopiert alte `ProjektVerlauf art=kommentar` in den Chat
  (`herkunft = "projektierung (migriert)"`, Dublettenschlüssel vorgang_id + zeit + text,
  Original bleibt). CSS `app/static/akte_v28.css`.
- **Galerie-Lightbox (Phase 136, `_galerie.html`):** Bild groß (95 vw / 85 vh), ◀ ▶,
  Pfeiltasten, Wischen, Kopfzeile „<Ordner> · n von m · Datum · Bemerkung“, Knöpfe
  Herunterladen/Schließen, Esc und Klick außerhalb; Bild-Links tragen `data-lb-*`. Die
  Datei-Route `GET /vorgaenge/galerie/datei/{id}` liefert Bilder und PDFs `inline`
  (`galerie.inline_anzeige`), Download nur über `?download=1` (`Content-Disposition:
  attachment`) – Ursache des Sofort-Downloads war das `filename=`-Attachment der Route.
- **Montage-Backend `/montage` (Phase 137, `app/routers/montage.py`):** Besetzung je Termin
  entscheidet (`termin_besetzung`; Termine ohne Besetzung: Team-Mitglied oder `person_id`;
  Admin/Projektierung alles – bestätigt 08.10.2026). Standardansicht „Meine Einsätze“ (Heute/Diese
  Woche/Danach), Team-Umschalter für mehrere Teams und Admin/Projektierung („Team <Name>“ =
  alle Termine des Teams), Wochenkalender mit Besetzungs-Initialen. Auftragsseite: Kopf ·
  Steckbrief vollständig (`steckbrief_zeilen`: alle Felder aus `kern.steckbrief_felder`, leere
  „–“, Ableitung einmal nachgeholt – Ursache des Befunds: Template blendete leere Felder aus,
  Bestandsimport ohne Ableitung, CSS-Raster) · Gerät & Positionen (eingeklappt) · Teams &
  Termine (Art aus `typ`/`zweck`, Besetzung) · Notizen der Projektierung (read-only, letzte fünf
  + „alle anzeigen“, Hinweis „Bemerkungen bitte im Montagebericht eintragen.“) · Montage
  starten/beenden (*seit Nachtrag 08.10.2026 ohne Kurzbericht – Bemerkungen im Montagebericht*,
  Hinweis auf automatisches Ende) · Formulare ·
  Restarbeiten · Galerie. Block „Offene Montage-Aufgaben“ entfällt (Route `POST /montage/
  aufgabe/{id}/erledigt` bleibt erreichbar; im Blatt gibt es keine `rolle = montage`). Das
  unterschriebene Abnahmeprotokoll beendet die Montage automatisch
  (`montage_formulare.abschliessen`: Phase montage → abnahme, `montage_fertig_am`, Verlauf
  „Montage beendet mit Abnahme“).
- **Formulare (Phase 138, `app/montage_formulare.py`, `projektierung_logik.py`):** Blatt
  „Formulare“ auf v28-Stand (Montagebericht 19 Felder ohne Arbeitsbeginn/-ende, Nachbestellung,
  Regie; `mb_bemerkung` „Bemerkungen des Monteurs“ als Textarea; Fotos Zählerschrank/
  Außengerät/Innengerät/Neue Anlage; Inbetriebnahmeprotokoll 5 Seiten / 30 Felder (Nachtrag
  08.10.2026: `ib_kaeltemittel` entfällt, Antwort Andreas) mit den elf
  Fragen von Andreas; Abnahme unverändert). Feldtypen datum · text (Option `gross`) · ja_nein ·
  auswahl · zahl · foto (Ordner, mehrere Dateien, Wert `galerie:<id>:<name>|…`) · unterschrift ·
  `wiederhol` (Spalte optionen = Einzelfeld, Formularfelder `<key>[]`, JSON-Liste, „+ weitere
  <Einzelfeld>“); Optionsform `pflicht_wenn:<feld>≠<wert>` / `=<wert>`
  (`FormularFeld.pflicht_erfuellt`, in `offene_pflicht`); „Logik prüfen“ meldet unbekannte
  Typen/Optionsformen als Fehler. `mb_mitarbeiter` wird mit der Besetzung vorbelegt. Abschluss
  der Inbetriebnahme übernimmt Frage 10 als Restarbeiten (ohne Dubletten, „keine“/„-“/„–“ →
  nichts). PDF: `multi_cell` für lange Fragen, Frage 7 als vier Zeilen, Betriebswerte/
  Einstellungen als Tabelle, zwei Unterschriften nebeneinander („Techniker“, „Betreiber –
  Einweisung und Unterlagenerhalt bestätigt“); Dateiname `Inbetriebnahmeprotokoll_<PR>.pdf`.
- **Stücklisten (Phase 139):** Blatt „Stücklisten“ aus `docs/stuecklisten_v26.csv` (121
  Zeilen, 80 Positionen, eingespielt 08.10.2026); Konvention Lieferant
  (`stuecklisten.art_fuer_lieferant`: Standard-Lieferant = bestellen · Lager · „–“ = Leistung ·
  anderer Name = Fremd), `ugl.material_fuer_gewerk(mit_uebrigen=True)` für den Block „nicht
  bestellt“, Spalte „Art“ auf der Stücklisten-Seite, Go-live-Quote ohne PV/KL-Positionen ohne
  Zeile [ANNAHME].
- **Tests v28:** `tests/test_proj_v6_waechter.py` (12), `_board.py` (3), `_termine.py` (12),
  `_stuecklisten.py` (4), `_notizen.py` (10), `_montage.py` (14), `_formulare.py` (12), Basis
  `tests/proj_v6_p2_basis.py`; angepasst `tests/test_projektierung_v4.py` (BzA-Schritt nur bei
  `foerderung:ja`; Stücklisten-Beispielzeile durch CSV ersetzt). Screenshots `docs/design-v28/`
  (Board 1 920/1 366, Akte Block Termine, Phase-Dialog, Montage-Auftrag 390 px,
  Inbetriebnahme Prüfungen, Lightbox, Notizen-Chat). Doku: `docs/nach-dem-update-v28.md`,
  `docs/projektierung-entscheidungen.md` (Teile P1/P2), `docs/projektierung-prototyp.html`
  (Block Termine, Dialog Phase ändern).
- **Nachtrag 08.10.2026 (Antworten Andreas auf die Rückfragen des Durchlaufs, Projektierung):**
  (1) `main.breit` ohne Breitenbegrenzung (`style.css`: `max-width: none`, 16 px Innenabstand) für
  ALLE breiten Seiten – Portal, Lead-Management, Vorgangsakte, Projektierung; die Sonderregel
  `main.breit.pj-voll` ist entfallen (Klasse bleibt Marker); die Kundenkartei ist ebenfalls
  unbegrenzt (`lead_v2.css` `main.lk-seite` ohne `max-width`). (2) Board-Höhe
  (`projektierung.js` `hoeheSetzen`, `projektierung_v28.css`): Mindesthöhe 480 px nur bei
  Viewport-Höhe ≥ 900 px, darunter 320 px; Messung mit übergroßem Board (Board füllt den
  Viewport auch bei wenigen Karten); unter 960 px Höhe oder in schmalen Fenstern wird die
  Board-Seite verdichtet (Hinweis einzeilig mit Hover, Kachel-Untertitel aus, Fußabstand 8 px)
  → kein Seiten-Scroll bei 1 366 × 768; Kontrollwerte `diagnose/v28_patches/pb_kontrolle.py`.
  (3) „Montage beenden“ ohne Kurzbericht (`templates/montage/einsatz.html`; Bemerkungen im
  Montagebericht `mb_bemerkung`); `POST /montage/einsatz/{id}/phase` nimmt das Feld `bericht`
  nur noch aus Altgründen an (Verlauf nur, wenn nicht leer). (4) `ib_kaeltemittel` entfällt –
  Inbetriebnahmeprotokoll 5 Seiten / 30 Felder (Zeile aus dem Blatt „Formulare“ entfernt).
  (5) `montage_formulare.migration_v28_entwuerfe` (migrate.py) leert Entwürfe mit Schlüsseln,
  die das Blatt nicht mehr kennt (`antworten_json = "{}"`, `seite_index = 0`; Meldung
  „Formulare (v28): n alte Entwürfe geleert (…)“, idempotent). (6) Bestätigt ohne Codeänderung:
  Personen-Liste der Termin-Dialoge Projektierung + Innendienst + Admin (kein Außendienst),
  Sub-Einsatz ohne Subteam mit leerer Besetzung, Foto-Ordner Elektro/Außengerät/Neue Anlage,
  Seite „Abweichungen & Bemerkungen“, aufgabenbezogene Kommentare im Projektverlauf,
  Projektierung liest das Montage-Backend, PDF-Präfix „Seriennummer n“. Tests:
  `MigrationEntwuerfe` in `tests/test_proj_v6_formulare.py` (30 Felder), angepasst
  `tests/test_proj_v6_montage.py`; Entscheidungstabelle in
  `docs/projektierung-entscheidungen.md`.

## Neu in v29 – Lead-Management V4 Feedback-Runde 2 (abgestimmt 07.10.2026)

(Plan: PLAN_LEAD_V4.md, Phasen 140–144; umgesetzt am 08.10.2026 im gemeinsamen Durchlauf
mit dem v27-Nachtrag 2 und v28 – EIN Commit. Alles weiter im Demo-Modus
`lead_freigabe_modus = admin`. Alle Datenbankänderungen additiv (`vorgaenge.email_status*`,
`mail_fehler*`, `benutzer.vorname/infotext/bild_datei`, `kommunikation_log.absender/
versuche`); v27-Code läuft auf der v29-Datenbank weiter. Entscheidungen:
`docs/leadmanagement-entscheidungen.md` Abschnitt V4 (Teile L2/L1).)

- **Lead-Glocken zentral gesperrt (Phase 141, `app/lead_glocken.py`):** Parameter
  `glocke_lead_arten` (Komma-Liste, Standard `todo_zugewiesen,todo_aktualisiert`; Häkchen in
  den Lead-Einstellungen; weitere Werte `lead_eingang`, `sla`, `wiedervorlage`, `zuweisung`,
  `kanalwechsel`, `kundenantwort`, `terminaenderung`, `digest`, `quelle_auto`).
  `leadmanagement.benachrichtigen(session, ids, text, link, art=…)` legt nur erlaubte Arten
  an (ohne `art` nie); alle Aufrufstellen des Lead-Moduls tragen ihre Art;
  `lead_todos._glocke` prüft die beiden To-Do-Arten (Zuweisung durch jemand anderen;
  Erledigen/Öffnen/Löschen eines eigenen To-Dos durch jemand anderen; Fälligkeits-Glocke
  bleibt als `todo_zugewiesen` [ANNAHME]). Nicht betroffen: Projektierungs-Glocken,
  Angebotstool-Glocken, v27-Betriebsglocken (art `system`). Aktivitäten bleiben.
- **Parametrierung → Lead-Einstellungen** Abschnitt „Lead-Management V4“: `absender_lead_mails`
  (termin@friondo.de), `hv_versandweg` (entwurf – Standard seit Nachtrag 08.10.2026 | offen | smtp | leads_im_namen),
  `vorschlaege_anzahl` (3), `hv_gruppe_rene`/`hv_gruppe_simon` (Benutzer-IDs, Startwerte per
  Namensabgleich in `lead_v2.migration_v29_oberflaeche`), `routen_start`, Glocken-Häkchen,
  Zähler „Lead-Mails mit Fehler“ mit Link zur Warteschlange, Prüfpunkte „Testmail aus dem
  Lead-Absender“ und „Terminbestätigungen aus docs/vorlagen einspielen“; `ohne_schritt_tage`
  ausgeblendet (ohne Wirkung); `absender_postfach` heißt „Parser-Eingangspostfach (leads@)“.
  Logik-Seite zeigt das Blatt „Terminhinweise“ und die Kaskaden-Spalte `nach_letztem`.
  Betriebs-Seite: Kachel „Lead-Mails mit Fehler“ (kein `/health`-warn [ANNAHME]).
- **Handelsvertreter-Sicht (Phase 140, `lead_v2.hv_sicht`):** Benutzer mit
  `ad_profile.terminiert_selbst` ohne Innendienst-/Leadmanagement-/Admin-Rolle sehen in der
  Icon-Leiste (`_nav.html`, Import `lm_nav … with context`) nur Mein Dashboard · Karte ·
  To-Dos · Handelsvertreter; Hauptboard, Deals, Kontaktiert, Infoabend und alle
  „Mehr …“-Einstiege liefern per URL 404 (`lead_v2.HV_GESPERRTE_PFADE`, `lead_v2.gate` –
  hinter Login/PIN-Wechsel der v27-Middleware; Links aus dem Tool mit Referer → 303 auf die
  HV-Ansicht mit Hinweis [ANNAHME A1] – *überholt seit Nachtrag 08.10.2026: immer 303, nie 404*).
  Karte (`routers/leadmanagement.karte/karte_daten`)
  zeigt HV nur eigene Leads/Termine/Startadresse, Mittelpunkt = eigene Leads; Kartei:
  Innendienst/Leadmanager nur Anzeige. Sammelaktion **„An Handelsvertreter verschieben“**
  (`lead_boards.SAMMELAKTION_HV`, auch Deals/Infoabend) mit zwei Ziel-Schaltflächen aus
  `hv_gruppe_rene`/`hv_gruppe_simon` (erster Eintrag = Ziel), Ausschluss F14 wird gemeldet
  („3 verschoben, 1 übersprungen: Kanal Enni“), Aktivität je Lead, keine Glocke; HV-Ansicht
  mit Filter „Gruppe“ (René | Simon-Team | alle).
- **Navigation, Boards, Dashboard (Phase 141):** „Mehr …“ ist ein Flyout
  (`.lm-leiste-menue[data-flyout]`, `app/static/lm_nav.js`, position fixed, z-index 45 unter
  dem Wartungsbanner, Escape/Klick außerhalb, unter 900 px nach oben, kein Scrollen in der
  Spalte). **Spaltenbreite je Nutzer**: `boards_spalten` je Spalte mit `breite` (60–600 px),
  Ziehgriff im Spaltenkopf (`lm_boards.js`, `<colgroup>` über Makro `spalten_colgroup`,
  Doppelklick = Standard), `POST /boards/spalten {breite:{key,px}}`. **Dashboard** „Hallo,
  <Vorname>“ (`Benutzer.vorname`, sonst Name; `lead_dashboard.anrede_name`): links Fällig
  heute · Kommende Wiedervorlagen (alle künftigen, nach Datum, „weitere anzeigen“) · Offene
  To-Dos, rechts „Routenplaner“ (Google-Maps-Link, Start = Parameter `routen_start`, Ziel
  leer) und „Meine Termine“ (HV: mit Sperrzeiten); entfernt „Ohne nächsten Schritt“,
  „Angebots-Wiedervorlagen“, „Termine 7 Tage“; „Mir zugeteilte Vorgänge“ eingeklappt
  [ANNAHME] (*seit Nachtrag 08.10.2026 entfernt*); Kachel „Mails mit Fehler“ nur bei > 0.
  **Eingangsdatum** in der Kartei
  „TT.MM.JJJJ, HH:MM Uhr“ (Filter `de_datum_zeit`, Kopf + Kundeninfo). **Boards**: Rang 0
  ganz oben für Leads mit `mail_fehler` oder `email_status = ungueltig`, rote Labels „Mail
  nicht gesendet“/„E-Mail falsch“ in der Notiz-Spalte, Kartei mit Hinweisbalken
  (`_mail_hinweis.html`) und Block „Notizen“ (gemeinsamer Notizen-Chat, `notizen.kontext(…,
  herkunft="lead")`); Warteschlangen-Seite `/lead-management/kommunikation?status=…` mit
  Absender, Versuchen und „Erneut senden“.
- **Terminassistent (Phase 143, `lead_termin`):** genau `vorschlaege_anzahl` (Standard 3)
  Vorschläge, der erste „Ideal“ (`ideal`, `ideal_grund`; Rahmen Friondo-Blau, Badge, auch im
  Block Termine der Kartei), gebündelter Routing-Aufruf unverändert; Kalenderansicht per
  `GET /lead/{id}/termin/kalender.json?woche=&neu=1` (`lead_termin.kalender_json`: Mo–Sa,
  15-Minuten-Raster, Spalte je Kandidat, Tool-Termine, Outlook-Belegt nur bei `kalender_sync
  = an` und nie für HV, Vorschlags-Slots, Cache 10 Min je Lead/Woche, Verbindung vor dem
  Graph-Abruf freigegeben; Klick auf freien Slot = manuelle Buchung), „Weitere Kalender“
  (Mehrfachauswahl, `benutzer_einstellungen` Key `assistent_kalender`, Spalten „außerhalb
  der Vorauswahl“, Buchung mit Warnhinweis + Bestätigung). **HV-Sperrzeiten** [OFFEN 3]:
  `VotTermin.typ = "sperrzeit"` (vorgang_id 0, `TERMIN_TYP_NAMEN["sperrzeit"]`) aus „Meine
  Termine“ des HV-Dashboards (`POST /dashboard/sperrzeit`), blockieren Vorschlags-Slots;
  `kalender.py` überspringt HV mit Protokollzeile (kein Friondo-Postfach).
- **E-Mail-Vorlagen und Terminbestätigung je Vertriebler (Phase 142,
  `app/routers/lm_vorlagen.py`, `app/lead_mail.py`):** `/lead-management/vorlagen` zeigt die
  Vorlagen als Baum in der linken Spalte (Eingang · Kontakt · Terminbestätigung (ausklappbar)
  · Termin · Sonstige, Suche) und rechts den Editor (Betreff, HTML-/Textvorlage mit
  Formatierungsleiste und Platzhalter-Dropdown, Vorschau mit Demo-Lead über
  `POST /vorlagen/vorschau`); der v23-Editor in `lm_boards.py` ist entfernt. Die
  Oberkategorie Terminbestätigung enthält „Standard“ und je aktivem Vertriebler (Außendienst
  mit AD-Profil, auch HV) die Vorlage `terminbestaetigung_<benutzer_id>` („Terminbestätigung –
  <Name>“; Ablage weiter in `lead_vorlage_<key>_betreff/_text`, dazu `_quelle`
  editor|zulieferung|standard_kopie und `_hash`). Rahmen + individueller Block: Platzhalter
  `{vertriebler_block}` (Bild als Inline-CID `cid:vertriebler-<id>`, Name, Telefon, E-Mail,
  Infotext aus der Benutzerverwaltung – `Benutzer.vorname/infotext/bild_datei`, Upload
  JPG/PNG ≤ 2 MB im AD-Profil nach `data/benutzerbilder/`) oder ein Bereich zwischen
  `<!-- vertriebler_block -->` und `<!-- /vertriebler_block -->`; „Rahmen für alle
  Terminbestätigungen übernehmen“ (`lead_mail.rahmen_uebernehmen`, Sicherheitsabfrage mit
  Anzahl, Protokoll) schreibt Betreff und Rahmen in alle Vorlagen der Oberkategorie, Blöcke
  bleiben; neue Vertriebler bekommen die Standard-Kopie (`vertriebler_vorlage_sicherstellen`).
  Versandregel: `kern.mail_planen` / `lead_mail.rendern` wählen die Vorlage des zugewiesenen
  Vertrieblers des Termins (`terminbestaetigung_key`), sonst Standard mit Hinweis-Aktivität;
  der Warteschlangen-Key bleibt `terminbestaetigung`. Neue Platzhalter `{adresse}`,
  `{sparten_hinweise}` (Absatz „Damit wir uns optimal vorbereiten können …“ + Punkte je
  Interesse aus dem Blatt **Terminhinweise** der Steuerdatei, mehrere Sparten mit
  Zwischenüberschrift, Dubletten entfernt, Platzhalter „(Punkte folgen)“ [OFFEN 1]),
  `{vertriebler_block}`, `{vertriebler_vorname}`, `{vertriebler_email}`. Zulieferung
  `docs/vorlagen/terminbestaetigung/<name>.html|.jpg` wiederholbar einspielbar
  (`lead_mail.zulieferung_einspielen`: Zuordnung über den Benutzernamen, Hash, im Editor
  geänderte Vorlagen nie überschrieben; `scripts/vorlagen_einspielen.py`, `migrate.py`, Knopf
  in den Lead-Einstellungen). **Nurture entfällt**: Vorlage ausgeblendet
  (`VORLAGEN_AUSGEBLENDET`, Datensatz bleibt), offene Einträge storniert, Kaskade endet mit
  der Aktion der neuen Spalte `nach_letztem` (Standard `mail_disqualifiziert`,
  `logik.nach_letztem()`); Kundenantworten erzeugen Aktivität + Wiedervorlage „jetzt“,
  keinen Phasenwechsel mehr [ANNAHME] (*überholt seit Nachtrag 08.10.2026: nicht erreichte/
  zurückgestellte Leads kommen zurück nach `in_kontaktierung`*).
- **Absender termin@ ohne Fallback, Status fehler, Bounce (Phase 142, `app/lead_mail.py`,
  `app/lead_mail_abruf.py`, `app/routers/lm_mail.py`):** Absender ALLER Lead-Mails ist der
  Parameter `absender_lead_mails` (Standard termin@friondo.de, `lead_mail.absender`) – kein
  Fallback (`ABSENDER_FALLBACK` nur noch Konstante); leads@ (`absender_postfach`) ist reines
  Parser-Eingangspostfach. Scheitert der Versand (Graph-Fehler, kein Token, Konfiguration),
  wiederholt der Lauf `lead-mail` bis `VERSUCHE_MAX` = 3 (Pause 60 s × Versuch,
  `KommunikationLog.versuche`), danach Status `fehler` + Vorgang `mail_fehler/_am/_vorlage/
  _text` + Aktivität „Mail nicht gesendet: <Vorlage>, <Grund>“; Label/Rang 0/Kartei-Balken
  (`lead_mail.kartei_hinweis`, `_mail_hinweis.html`), Zähler in Lead-Einstellungen und
  Betriebs-Seite. „Erneut senden“ (`POST /lead-management/mail/{id}/erneut`,
  `lead_mail.erneut_senden`) setzt nur `geplant` sofort fällig/Versuche 0 – gesendet wird
  durch den Lauf; Erfolg setzt `mail_fehler` zurück. Prüfpunkt `POST /lead-management/testmail`
  (Admin, Sitzung vorher frei, Demo nur Testpostfach – einzige Request-Ausnahme). Neuer Lauf
  **`lead-mail-abruf`** (120 s, Startverzögerung 270 s, aktiv nur mit Graph): liest ungelesene
  Nachrichten in termin@ (`graph_versand.postfach_ungelesen`), ordnet Antworten
  (`lead_mail.kundenantwort_verbuchen`) und Unzustellbarkeitsberichte
  (`lead_mail_abruf.ist_ndr/ndr_empfaenger`, Original-Empfänger aus Kopfzeile/Text, Testmodus
  über „[TEST an …]“) über `kommunikation_log.an` + Betreff bzw. Kunden-E-Mail dem Vorgang
  zu (`bounce_verbuchen`: `email_status = ungueltig`, Aktivität „E-Mail unzustellbar“,
  offene Einträge `wartet_adresse`; `adresse_geaendert` gibt nach Adressänderung im
  Autospeichern der Kartei frei), markiert sie als gelesen, Unklares → „Posteingang unklar“;
  im Demo-Modus nur Demo-Leads. Blöcke zu 50, `db.kurz()`-Muster. `migration_v29_mails`:
  Parameter, Absender offener Einträge, v29-Rahmen der Standard-Terminbestätigung,
  Standard-Kopien/Zulieferung, Nurture-Stornos. HV-Leads (*seit Nachtrag 08.10.2026 Standard
  `entwurf` – fertige .eml aus der Vorschau, siehe Nachtrag unten*): `hv_versandweg = offen` → keine
  Kundenmail, Aktivität + To-Do mit Vorschau (`GET /lead-management/lead/{id}/termin/{tid}/
  vorschau`, Text + ICS); smtp/entwurf/leads_im_namen sind Erweiterungspunkte
  (`lead_mail.hv_versand_*`). Doku: `docs/graph-einrichtung.md` „Lead-Management V4 (v29)“.
- **Tests v29:** `tests/test_lead_v4.py` (13: a–h, m + Warteschlangen-Vertrag),
  `tests/test_lead_v4_mail.py` (17 + 1 Skip g3 → Sperrzeit von L1 vorhanden), Fixtures
  `tests/fixtures/ndr_exchange_de.eml`/`_en.eml`; angepasst (Glocken-Arten per Helfer
  einschaltbar, HV-404, `breite`, kein Nurture, `ohne_schritt_tage`, 14 Läufe, kein
  Absender-Fallback): `test_lead_v2_*`, `test_lead_v3*`, `test_v27_scheduler.py`,
  `test_pool_hotfix_mail.py` (Begründungen in `docs/leadmanagement-entscheidungen.md` V4.4/V4.7).
  Screenshots `docs/design-v29/` (Dashboard vorher/nachher, Flyout, HV-Sicht,
  Terminassistent mit Kalender, Vorlagen-Editor vorher/nachher, Kartei/Hauptboard „Mail nicht
  gesendet“, Hauptboard vorher). Doku: `docs/nach-dem-update-v29.md`,
  `docs/leadmanagement-entscheidungen.md` V4, `docs/graph-einrichtung.md`, `docs/betrieb.md`
  Inventar (Lauf `lead-mail-abruf`, Testmail-Route).
- **Abschluss des Durchlaufs (08.10.2026, Nachtrag 2 + v28 + v29):** Gesamtsuite
  `pytest tests -q` **898 bestanden, 5 übersprungen, 0 Fehler** (7:53 min); Server-DB-Kopie
  (Stand 03.10.2026) `migrate.py` zweimal (zweiter Lauf ohne Änderungen); `tests/abnahme.py`
  93/93; Voll-Crawl admin/innendienst/aussendienst/montage 61.184 Aufrufe + HV-Testbenutzer
  15.299 Aufrufe ohne Absturz; `scripts/smoke.py` 8/8 gegen einen Testserver auf der Kopie
  (`/health` v29, 14 Läufe); Lasttest Profil normal (50 Nutzer, 20 min) siehe
  `docs/lasttest-v27.md` Abschnitt 4.7 – Lauf 1 und 2 je **1 × „database is locked“**
  (Zielwert 0): `GET …/termin/vorschlaege.json` schrieb nach dem Routing-Matrix-Aufruf bis zu
  2.500 `routing_cache`-Zeilen in der Anfrage-Sitzung und hielt die Schreibsperre danach bis
  zum Anfrageende (6–7 s unter Last; latenter v27-Befund, dort max. 2,5 s). **Behoben:**
  `routing.matrix_fuellen` und `lead_termin.vorschlaege` geben die Verbindung direkt nach den
  Cache-Schreibungen frei (`verbindung_freigeben`); **Lauf 3 nach der Korrektur: alle Zielwerte
  erfüllt** (6.610 Anfragen, 0 × 5xx, 0 locked, Schreibsperre max. 0,8 s, Pool-Spitze 17 von 90,
  p95 Listen/Akten 0,59 s, Terminvorschläge 4,9 s). Entscheidung „SQLite bestätigt“ bleibt.
  Gesamtsuite nach der Korrektur zweimal: ein Lauf mit 1 × „database is locked“ in
  `tests/test_pool_hotfix.py::Lasttest::test_40_parallele_anfragen_ohne_pool_timeout`
  (lastabhängig, einzeln und im Wiederholungslauf grün: 898 bestanden, 5 übersprungen).
  `config.VERSION = "v29"`. Angepasste Alt-Tests durch den Orchestrator:
  `tests/test_kl_v24_import.py` (Anhänge-Zeile = `Bosch Climate 3200i.pdf`, Nachtrag 2) und
  `tests/test_lead_v2_boards.py` (Rechte-Helfer des neuen Editors `lm_vorlagen._pflege_erlaubt`).
- **Nachtrag 08.10.2026 (Antworten Andreas auf die Rückfragen des Durchlaufs, Lead-Management):**
  HV-Sicht: gesperrte Seiten (`lead_v2.HV_GESPERRTE_PFADE`) leiten **immer** mit 303 auf
  `/lead-management/handelsvertreter?meldung=…` um (`lead_v2.hv_umleitung`, von `gate` und vom
  V1-Demo-Gate `routers/leadmanagement._gate` aufgerufen; auch JSON-Routen, kein Referer-Fall,
  kein 404 mehr). Dashboard ohne „Mir zugeteilte Vorgänge“ (`lead_dashboard.zugeteilte` bleibt
  als Funktion). **Sperrzeiten** zählen in `lead_termin._slot_frei`/`konflikte` exakt von–bis
  (kein Mindestpuffer, kein Nachbartermin für Umweg/Tour-Tag); Admin/Innendienst tragen sie für
  einen HV ein (`POST /dashboard/sperrzeit` mit `benutzer_id`, `lead_termin.sperrzeit_anlegen(…,
  ziel)`, `sperrzeit_fremd_erlaubt`, Block „Sperrzeiten der Handelsvertreter“ in
  `hv_uebersicht.html`, Listen zeigen „eingetragen von …“, Glocke art `terminaenderung`).
  **Kundenantwort** (termin@ und leads@, `lead_mail.kundenantwort_verbuchen`) holt
  `nicht_erreicht`/`zurueckgestellt` zurück nach `in_kontaktierung` (Zurückstellung aufgehoben,
  Aktivität „Kunde hat geantwortet – zurück in die Kontaktierung“, Wiedervorlage „jetzt“) –
  danach manuell, keine Nurture-Logik. **Status `fehler`** legt zusätzlich eine Betriebsglocke
  (art `system`) an alle aktiven Admins an (`lead_mail._admins_glocke`, einmal je Eintrag,
  dieselbe Sitzung). Graph-Mails tragen **`replyTo`** = Leadmanager (`Benutzer.email`) +
  Absender termin@ (`lead_mail.antwort_adressen`, `_graph_senden(…, vorgang=)`).
  **HV-Versandweg `entwurf` ist gebaut und Standard** (`PARAMETER_START`, `migration_v29_mails`
  stellt `offen` einmalig um, Marker `migration_v29_hv_entwurf`; `offen` bleibt wählbar,
  smtp/leads_im_namen weiter Erweiterungspunkte): `lead_mail.eml_erstellen` liefert die fertige
  Termin-Mail als RFC-822-Datei (HTML + Text, Inline-Bilder als CID, ICS mit METHOD, From =
  E-Mail des HV aus der Benutzerverwaltung, `X-Unsent: 1`), Download
  `GET /lead-management/lead/{id}/termin/{tid}/vorschau?eml=1` (message/rfc822,
  `Terminbestaetigung_<Kunde>.eml`, Knopf + Anleitung in `_vorlagen_termin_vorschau.html`);
  beim Terminieren eines HV-Leads keine Warteschlangen-Mail, sondern Aktivität „… als Entwurf
  (.eml) bereitgestellt – Versand aus dem eigenen Postfach des HV“ und To-Do „… aus dem eigenen
  Postfach senden“ mit Vorschau-Link (Vertrag der `hv_versand_*`-Funktionen: `(eintrag,
  hinweis, erledigt)`); Erinnerung −24 h bleibt Aktivität mit Vorschau-Link. Bestätigt ohne
  Codeänderung: Fälligkeits-Glocke der To-Dos, Terminhinweise-Platzhalter, Dateinamen-Konvention
  der Zulieferung, Bounces im Testmodus; OFFEN 3 (HV-Kalender) bleibt bei der Zwischenlösung.
  Tests: `tests/test_lead_v4.py` (14), `tests/test_lead_v4_mail.py` (20, g3 echt); angepasst
  `test_lead_v2_boards/v3_boards/v2_anruf/v2_dashboard/v2_handelsvertreter` (303 statt 404).
  Entscheidungstabelle in `docs/leadmanagement-entscheidungen.md` (Antworten 08.10.2026).
  Gesamtsuite nach dem Nachtrag (v28 + v29 + Nachtrag 2): **903 bestanden, 4 übersprungen**;
  `migrate.py` zweimal auf der Dev-DB (neu: `hv_versandweg offen → entwurf`, WP-Kopie entfernt,
  alte Formular-Entwürfe geleert).
