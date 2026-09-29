# Friondo Angebotstool – Projektkontext (v18)

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
  Import, monday-Mapping, Nummernkreis, Förderparameter-Ansicht).

## Zentrale Dateien
- `konfigurator_logik_v5.xlsx` – Steuerdatei (ersetzt v4): zusätzlich Frage A13
  „Leitungslänge Hauseinführung ↔ WP-Inneneinheit" (immer; Pos. 103 × [Eingabe − 5 m, nie unter 0] – 5 m stecken in Pos. 006),
  SLS/ÜSS/APZ-Fragen komplett entfernt. 14 AMPEL-Gründe (Blatt Aktionen).
- `Artikel-Preislisten/Angebotserstellung Tool mit EK.xlsx` (WP-Preisliste),
  `Artikel-Preislisten/PV/` (PV-Positionslisten, v16), `ANGEBOTSTEXTE.md`,
  `anlagen/`, `Layout - Logo/`.
- `projektierung_logik_v1.xlsx` (Projektierung, v11+) und
  `leadmanagement_logik_v1.xlsx` (Lead-Management, v12).

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
  (Blätter „Fragen PV" / „Fragen KL", ohne Artikel-Aktionen) und laufen
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
  einen chronologischen Notizen-Chat (Autor + Zeitstempel,
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
  Außendienstler (greift automatisch nach AD des Vorgangs). Platzhalter: {anrede},
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
  Wächter je Phasenwechsel, Override mit Begründung protokolliert.
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
- **Terminassistent:** Top-5-Slots über AD-Profile (Startadresse, Arbeitszeiten,
  Dauer/Puffer/Max), Tool-Termine (`vot_termine`, auch aus monday-VOT-Datum),
  optional Outlook-Frei/Belegt (Graph, `kalender_sync`), Fahrzeiten
  (`routing_anbieter` ors / google / luftlinie, Caches), Bewertung Umweg +
  Wunschzeit/Tour-Tag/Randzeit; Buchen schreibt Termin, Outlook-Ereignis (falls an),
  Bestätigung + Erinnerung; Umbuchen, No-Show (Lead zurück auf Qualifiziert),
  Terminkalender Woche je AD, Karte (Leaflet lokal, OSM-Kacheln), „Adresse prüfen".
- **Kommunikation:** Vorlagen eingangsbestaetigung / nicht_erreicht /
  terminbestaetigung (ICS) / terminerinnerung (−24 h) / terminaenderung / nurture
  (nur mit Einwilligung), Warteschlange + Versand-Job, `mail_modus` protokoll / test /
  live, Reiter Kommunikation in der Akte, Absender `leads@friondo.de` (Fallback angebot@).
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
  Notizen-Chat-Optik mit eigenen Einträgen rechts), Angebots-Editor
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
  Kalender); Zuweisung am Gewerk (WP-/Elektro-/Sub-Team) und je Termin;
  Kalender mit Balken über die Projektdauer (Standard 1 Woche), Drag,
  Konfliktwarnung; Outlook-Sync über Graph in beide Richtungen.
- Galerie am Vorgang mit festen Ordnern (*Ordnerliste überholt – seit
  27.09. Galerie je Sparte + Ordner „Förderung", siehe unten*), Upload mobil per Kamera für Vertrieb (auch ohne
  Auftrag), Planung und Montage; Projektakte zeigt dieselbe Galerie.
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
- Montage-Backend `/montage`: Team-Auswahl, chronologische Liste,
  Wochenkalender, Auftragsdetail mit Steckbrief und Galerie,
  Montagebericht · Inbetriebnahmeprotokoll · Abnahmeprotokoll (Felder im
  Blatt „Formulare", PDF in Galerie, Kundenunterschrift über Signatur).
- Kunden-Terminbestätigung per Mail mit Antwort-Erkennung.

## Neu 27.09.2026 – Review: Lead-Prozess + Design (v15-Nachtrag)

- Lead→AD-Übergabe repariert (Akte-Zugriff über VOT-Termin, „Erfassung
  starten" in Meine Termine, AD-Glocke, Vorgang direkt beim monday-Sync,
  No-Show bleibt No-Show).
- Mail-Warteschlange an den Terminstatus gekoppelt (Storno bei Umbuchung/
  No-Show/Absage, Statusprüfung im Versand, Nurture +30 Tage) – Pflicht
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
  Nachtext (parametrierbare Annahmen). Dachbelegungstool folgt –
  bis dahin Interim-Felder für Modulanzahl/Quer-Anteil.
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
  Termin); alle Spalten chronologisch, Unterminierte unten. Phasen
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
  „Montageteam zuweisen" (Team + Termin) jetzt Schritt 2 im Auftragseingang;
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
  nicht öffentlich). **UGL:** Formatabgleich (docs/ugl-format.md,
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
  – pauschal erledigt“), Montagetermin mit Team/Bestätigung, Steckbrief.
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
