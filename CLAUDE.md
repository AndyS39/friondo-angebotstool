# Friondo Angebotstool – Projektkontext (v35)

## Ziel
Zweistufiger Vertriebsprozess der Friondo GmbH: Außendienst erfasst mobil per
Fragenkatalog (gespeist aus monday-Leads mit Vor-Ort-Termin), Innendienst erzeugt,
prüft, rabattiert und versendet Angebote (PDF im Friondo-Layout, KfW-Förderung,
Deckungsbeitrag, E-Signatur). Läuft lokal/on-prem.

## Rollen & Navigation
- Rollen: **Admin** (Benutzer verwalten inkl. Namen ändern, alles sehen),
  **Innendienst** (alles außer Benutzerverwaltung), **Außendienst** (nur Leads VOT
  eigene + Erfassung; nie Preise/EK/DB/Rabatt), seit v11 **Projektierung** und
  **Montage** (nur `/montage`), seit v12 **Leadmanagement**; Mehrfachrollen *(ergänzt v33: Varianten einer Basisrolle – Montage Heizung/Elektro, Service Heizung/Elektro, Handelsvertreter – Parametrierung → Rollen; Rechte prüfen die Basisrolle)*
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
  (Ersatzangebot KL · Musterangebot KL – Klima-Positionen, v24), `Artikel-Preislisten/Wallbox/`
  (Wallbox Artikel Excel · Extraleitung – Wallbox-Positionen mit EK, v34; nur Projektordner/Git, nie
  Projektwissen; `Beispielangebot.pdf` gitignored), `ANGEBOTSTEXTE.md`,
  `anlagen/`, `Layout - Logo/`.
- `projektierung_logik_v1.xlsx` (Projektierung, v11+) und
  `leadmanagement_logik_v1.xlsx` (Lead-Management, v12; seit v23 zusätzlich die
  Blätter Objektarten und Status, Kaskade mit 5 Stufen, Gründe `verloren`).
- `docs/taifun/ADRESSEN.xsd` (TAIFUN-Schema der Kundenübergabe, v35 – Rekonstruktion aus dem Plan,
  bis das Original von TAIFUN vorliegt; Beispiel `docs/taifun/beispiel_LM.xml`, Doku
  `docs/taifun-kundenexport.md`).
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
| v30 | PLAN_V18.md | 145–152 |
| v31 | PLAN_LEAD_V5.md | 153–160 |
| v32 | PLAN_V19.md | 161–165 |
| v33 | PLAN_V20.md | 166–177 |
| v34 | PLAN_V21.md | 178–182 |
| v35 | PLAN_LEAD_V6.md | 183–187 |

## Fachliche Regeln (Änderungen v3)
- **Rabatt** (optional je Angebot, nur Innendienst/Admin): Betrag in € oder %,
  optionale Bezeichnung, keine Angebotsposition. Darstellung: Netto → 19 % USt →
  Gesamt-Betrag → **− Rabatt (brutto) → = Endbetrag**. KfW rechnet mit dem *(überholt – siehe v33 Phase 172: Rabatt bei jedem Steuersatz vom Gesamtbetrag nach USt, bei 0 % vom Netto; kein Zusatz „brutto“)*
  Endbetrag; der Deckungsbeitrag sinkt um den Netto-Anteil (Rabatt ÷ 1,19). *(v33: Rabatt ÷ (1 + USt-Satz), bei 0 % voller Rabatt)*
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
- **Rollen = Basisrolle + Kennzeichen (v33, Phase 167):** `benutzer.rolle` trägt den Key einer Rolle aus der
  Tabelle `rollen` (Basisrollen admin · innendienst · aussendienst · montage · projektierung · leadmanagement
  und Varianten wie Montage Heizung, Service Elektro, Handelsvertreter). Rechte und Pfadtabellen prüfen immer
  die **Basisrolle** (`Benutzer.basisrolle`, `hat_rolle`), Kennzeichen (`gewerk`, `hat_kennzeichen("service")`,
  `hat_kennzeichen("handelsvertreter")`) filtern innerhalb der Module; Pflege unter Parametrierung → Rollen.
- **Outlook je Person, TAIFUN liest Outlook (v33, Phase 170):** jeder Tool-Termin steht als Kopie im
  persönlichen Outlook-Kalender jeder eingeteilten Person (Vertriebler, Monteure, Techniker, Projektierer) –
  erzeugt und gepflegt ausschließlich durch die Läufe `outlook-sync`/`outlook-ruecklesen` über die Warteschlange
  `outlook_auftraege`; fremde Outlook-Einträge (TAIFUN, privat) werden nie verändert, nur als Belegtzeit gelesen.
  Löschen in Outlook löscht nie im Tool (Markierung + Glocke).
- **Rabatt bei jedem Steuersatz (v33, Phase 172):** der Gesamtrabatt wird vom Gesamtbetrag nach USt abgezogen –
  bei 0 % USt (PV, § 12 Abs. 3 UStG) also vom Nettobetrag; der Deckungsbeitrag sinkt um Rabatt ÷ (1 + USt-Satz).
  Kontrollwerte: 20.000,00 € netto, 0 %, 5 % → 19.000,00 €, DB −1.000,00 €.
- **USt kaufmännisch gerundet (v34, Phase 180):** `Angebot.summen()` rundet die USt wie TAIFUN
  (`ROUND_HALF_UP`) statt abzuschneiden – Summenblock, Editor, Liste, Statistik, monday und
  Mail-Platzhalter folgen; Rabatt-/KfW-Logik unverändert (Kontrollwert WP 30.245,43 € netto → USt
  5.746,63 € bleibt; KL-Fall A 1.238,55 € wie das TAIFUN-Musterangebot).
- **Keine Auslegungs-Position im Angebot (v34, Phase 180):** die 0,00-€-Zeilen „Auslegung der
  Wärmepumpe“ / „Auslegung der Klimaanlage“ / PV-Auslegungszeile entfallen; die Herleitung bleibt im
  Konfigurationsprotokoll und steht in `angebote.auslegung_text` (Editor-Hinweis „Auslegung (intern)“
  nur Innendienst/Admin, nie Außendienst); Bestand: Entwürfe per Migration bereinigt.
- **Alternativ-Darstellung (v34, Phase 180):** Positionen „in anderem Angebot enthalten“ (v10) sind im
  PDF durch einen farbigen Hinweiskasten vor dem Block und „im PV-Angebot“ (bzw. „im WP-Angebot“ …) in
  der G-Preis-Spalte klar von Eventualpositionen („EP.“) getrennt; im Editor farbiger Balken + Badge mit
  Link (Tokens `--alternativ`/`--alternativ-flaeche`).
- **Elektroarbeiten ins PV-Angebot (v34, Phase 180):** Knopf im Editor eines WP-/KL-/WB-Entwurfs
  verschiebt die Elektro-Positionen (Block Elektroarbeiten bzw. WB003/WB005/WB006 + gewerkeübergreifende
  Artikel) in das PV-Angebot desselben Vorgangs (dort voll berechnet zu 0 % USt, eigene Gruppe,
  `uebernommen_von_*`), im Ursprung als Alternativ-Positionen; „zurückholen“ solange beide Entwurf/Versand
  vorbereitet sind. Steuerliche Zulässigkeit entscheidet Friondo/Steuerberatung – das Tool setzt nur um.

## Neu in v6 (abgestimmt 21.08.2026)
- **Lead-Zuordnung:** Personen-Zuordnung wirkt sofort rückwirkend auf bestehende
  Leads; Matching zusätzlich über Benutzer-E-Mail; Warnhinweis bei Leads ohne AD.
- **Vertriebskanal** aus monday (Mapping je Board) an Lead/Kunde, Badge + Filter
  in allen Listen, Auswertung in der Statistik. *(ergänzt v35: Kanäle sind Stammdaten der Tabelle
  `vertriebskanaele` mit Farbe, Pflege unter Lead-Management → Vertriebskanäle; monday-/Quellen-Werte
  werden über die Zuordnungstabelle alt → neu abgebildet, Phase 184)*
- **Archiv:** Erfassungen archivierbar; neuer Status **„Individuell“** für
  Erfassungen und Angebote (außerhalb des Tools geschrieben); seit v7 gilt
  die Statuskette aus „Neu in v7" statt Auto-Archiv. Versendete Angebote sind (ID + Admin) mit Sicherheitsabfrage
  löschbar; jede Löschung landet im Lösch-Protokoll (Parametrierung).
- **Angebotsliste:** Summenzeile Netto/Endbetrag/DB über die gefilterte Liste. *(ergänzt v33: über die gefilterte UND sortierte Liste, Spalte „Endbetrag“ nach USt und Rabatt, DB-Summe nur mit Kalkulationssicht)*
- **Editor:** Artikeltexte je Position editierbar (nur im Angebot), lange
  Beschreibungen aufklappbar statt abgeschnitten, EP-Kästchen je Position;
  Förderbetrag manuell überschreibbar (Kennzeichen „manuell“) und Förderblock
  im PDF ausblendbar.
- **Angebotsverfolgung:** Hot-Ampel (heiß/warm/kalt), Wiedervorlage-Datum
  (Startseiten-Kachel „fällig“), Notizen-Verlauf (append-only).
- **Statistik-Seite:** Zeitraumwahl, Kennzahlen gesamt/je AD/je Kanal,
  Abschlussquote; Außendienst sieht nur die eigenen Zahlen.
- **E-Mail:** Versand als HTML; Vorlagen-Editor mit Formatierung (fett usw.);
  je ID-Benutzer die echte Outlook-Signatur (Upload .htm + Bilder, Inline-CID) *(ergänzt v33: auch der Außendienst über `/einstellungen/signatur` – Nachfass-Mail)*
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
  WB vorerst immer Freitext *(überholt – seit v34 ist WB ein Konfigurator mit Weiche Katalog | Freitext,
  siehe v34)*. PV/KL sind reine Erfassungsformulare
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
- Rollen: Außendienst sieht „Meine Angebote" (read-only, Kundenpreise *(seit v33 als Tabelle im Lead-Board-Layout, Katalog `meine_angebote` ohne DB – siehe v33)*
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
  in der Parametrierung, Fallback Standard *(v35: Kanalwerte aus der Kanal-Tabelle, nur lesend)*), am Angebot manuell
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
- Kombi-Versand *(ergänzt v34: Kasten „Gemeinsam versenden“ mit Häkchen an allen versandfähigen
  Angeboten, Entwürfe werden automatisch vorbereitet – Beschränkung auf „Versand vorbereitet“ entfällt)*:
  Aus der Akte mehrere versandfertige Angebote in
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
  Wiedervorlagen haben einen Verantwortlichen: vom AD gesetzte *(ergänzt – siehe v32: „Mein Tag“ aus `vot_termine`, automatische Wiedervorlage, monday-Nachführung, Glocke nachfassen)*
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
  Graph-Berechtigungen um Shared-Mailbox-Zugriff erweitern, docs/graph-einrichtung.md *überholt – siehe v33 (Phase 166): Modus anwendung legt Entwurf/Versand direkt am Postfach angebot@ an, kein „Senden als“, keine Anmeldung einer Person*
  fortschreiben).
- Automatisch: **CC = Außendienstler des Vorgangs** (E-Mail aus der Benutzer-
  verwaltung; fehlt sie, Entwurf ohne CC + Hinweis), **BCC** aus der Parametrierung
  (Standard info@friondo.de).
- **Vorlagen:** Standard-Vorlage für Betreff + Text plus optionale Vorlage je *(ergänzt v33: zusätzlich die Nachfass-Vorlagen „Nachfassen 1/2“, Versand durch den AD aus dem eigenen Postfach)*
  Außendienstler (greift automatisch nach AD des Vorgangs) – *ergänzt seit v27-Nachtrag 2:
  zusätzlich Vorlage je Sparte WP/PV/KL/WB, Reihenfolge AD → Sparte → Standard* *(überholt – seit v34 bei
  PV/KL/WB Sparten-Vorlage → AD-Vorlage → Standard, WP unverändert)*. Platzhalter: {anrede},
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
Graph-Versand über Innendienst, Terminal-Server-Betrieb. *überholt – siehe v33 (Phase 166): Zugriff als Anwendung (Client Credentials), Modus delegiert nur als Rückfall*

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
  erreicht · Unqualifiziert – seit v31 Label „Disqualifiziert“), Quelle/Kampagne/UTM, Eingang, SLA, Score (A/B/C),
  Leadmanager, Wunschzeiten, Koordinaten, Einwilligungen. Gesyncte monday-Leads
  erhalten die Phase abgeleitet (Badge „monday"); **monday-Sync und -Rückspielung
  unverändert**.
- **Demo-Modus** *(überholt – seit v31 beendet: `leadmanagement.DEMO_BEENDET`, `lead_freigabe_modus` wirkungslos = alle; Testphase über `terminierung_aktiv`/`mail_versand_aktiv`, `mail_modus` keine Steuerung mehr)*: Parameter `lead_freigabe_modus` (admin / alle, Standard admin):
  bei admin sind alle Routen unter `/lead-management` (`app/routers/leadmanagement.py`),
  Menüpunkte, Reiter, Kacheln nur für Admins (server-seitig, 404 für andere);
  `/leads` bleibt die Liste „Leads VOT", `POST /api/leads` ist nicht
  Admin-gesperrt, sondern per API-Key je Quelle geschützt; Startportal-Karte
  „Lead-Management" trägt das Badge „Demo · Coming soon". Im Modul angelegte Leads
  tragen `demo = 1` und erscheinen in keiner bestehenden Liste/Statistik/Kachel/
  Rückspielung; Umstellung auf `alle` fragt: Demo-Leads löschen oder behalten.
  Sperren im Demo-Modus: `mail_modus` nur protokoll/test (live abgewiesen),
  `kalender_sync` nur ins Testpostfach, monday-Leads nicht buchbar. *(ergänzt v33: Testpostfach nur für Demo-Termine; Kopien je Person über die Warteschlange, Phase 170)*
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
  optional Outlook-Frei/Belegt (Graph, `kalender_sync`), Fahrzeiten *(überholt – seit v33 Belegtzeiten aus dem Cache `outlook_belegt`, Ereignisse über die Warteschlange `outlook_auftraege`, Phase 170)*
  (`routing_anbieter` ors / google / luftlinie, Caches), Bewertung Umweg +
  Wunschzeit/Tour-Tag/Randzeit; Buchen schreibt Termin, Outlook-Ereignis (falls an),
  Bestätigung + Erinnerung; Umbuchen, No-Show (Lead zurück auf Qualifiziert),
  Terminkalender Woche je AD, Karte (Leaflet lokal, OSM-Kacheln), „Adresse prüfen". *(Terminkalender Woche je AD überholt – seit v33 zentraler Planungskalender `/kalender?gruppe=vertrieb`, Umleitung [ANNAHME])*
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
  Verschieben *(überholt – seit v35 bearbeitet der Außendienst eigene Leads wie der Innendienst, Phase 185)* – alles erst bei `alle` wirksam. Löschlauf (`loeschlauf`, Frist
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
  ausgewiesener Herleitung im Protokoll; Auslegungszeile in Block 1 *(überholt – seit v34 keine
  Auslegungs-Position, Text intern im Editor)*
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
- Rollen: AD setzt eigene Angebote auf Angenommen/Abgelehnt/Offen *(ergänzt – siehe v32: Verfolgungsstufe je Vorgang, Dialog „Nächster Schritt“, fünf Gründe mit Pflicht-Freitext)*
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
  Chip-Selects, Sticky-Tabellenkopf, Zebra + Hover (*Zebra überholt – seit v30
  feine Zeilenlinie + Hover, siehe v30*), EIN
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
  scripts/design_screenshots.py (Playwright + lokales Chrome) (*überholt –
  siehe v30: Design v2 mit semantischen Tokens je Modus Hell/Dunkel statt
  fester Farbwerte, Screenshot-Helfer ohne Playwright über Chrome headless +
  DevTools, Screenshots unter docs/design-v30/*).

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
  Konfliktwarnung; Outlook-Sync über Graph in beide Richtungen. *(ergänzt v33: Team-Kalender bleibt, daneben der Mitarbeiter-Kalender `/kalender?gruppe=projektierung` mit einer Zeile je Person; Outlook-Sync seit v33 über die Auftrags-Warteschlange je Mitarbeiter, Phase 170)*
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
  Pfad „Verloren vor Termin", Überfällig-Banner in Leads VOT. *(ergänzt – siehe v32: „Mein Tag“ aus `vot_termine`, automatische Wiedervorlage, monday-Nachführung, Glocke nachfassen)*
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
  Abnahme → Freigabe = Pflichtaufgaben Abnahme. *ergänzt v33 (Phase 171): dieser Wechsel läuft automatisch, sobald alle Abnahme-Pflichtaufgaben erledigt sind (phase_auto)*
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
  Parametrierung → **Go-live-Checkliste** (`app/golive.py`, 11 Live-Punkte *überholt – v33: 12 Live-Punkte (Punkt 12 „Graph als Anwendung verbunden“)*
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
  Wärmeversorgung · 4 Geplante Kosten · 5 Boni · 6 Ersteller – *Abschnitt 6
  „Ersteller“ überholt, entfällt seit v30*). Button
  „BzA-Datenblatt (PDF)“ an jedem WP-Angebot (Editor-Kopf, Vorgangsakte,
  jeder Status) **und an TAIFUN-WP-Einträgen** (Gerät dann Pflichtauswahl aus
  dem Blatt „BAFA-Anlagen“); Dialog `/angebote/<id>/bza-datenblatt` (WE
  übersteuerbar, Ersteller wählbar – *überholt, seit v30 ohne Ersteller*),
  PDF `BzA-Datenblatt-<Nr>.pdf` mit Vermerk
  „Internes Arbeitsblatt … keine KfW-Unterlage“. Fehlende Angaben rot
  („— fehlt: bitte beim Kunden erfragen“). Die Projektierungs-Seite
  `/projektierung/gewerk/<id>/bza` (v15/v17) nutzt denselben Generator
  (+ Kundendaten, Stand BzA/KfW, Link zum PDF).
- **Erfassung WP:** A02 heißt „Inbetriebnahmejahr (Baujahr) der bestehenden
  Heizung“ (steuert K02 wie bisher, Boni-Kategorie im Datenblatt); neu A20
  „Nennleistung der bestehenden Heizung in kW“ (Pflicht) (*überholt – A20 ist
  seit v30 aus Bogen und Datenblatt entfernt, siehe v30*) und N11
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
  Ersteller `bza_ersteller_standard` (leer = angemeldeter Benutzer) (*überholt –
  die Seite heißt seit v30 „BzA-Datenblatt“ und führt den Puffer-Prozentsatz;
  Ersteller und Firmenblock werden nicht mehr angezeigt, siehe v30*).
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
  nach 0,7 s für entfernen/sortierung/aendern/menge/neu-nummerieren – *seit v30 *(seit v33 wiederholt bereits `BEGIN IMMEDIATE` beim ersten Zugriff; `_speichern` wiederholt diesen Fall nicht erneut)*
  auch duplizieren/ueberarbeiten/kopieren, siehe v30*;
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
  des Blocks), Auslegungszeile WP mit Einheit „psl.“ *(überholt – seit v34 entfernt)* (Migration für den
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
im Plan. Alles weiter im **Demo-Modus** `lead_freigabe_modus = admin` *(bis v30; seit v31 freigeschaltet)*; V3 schaltet
frei. Umsetzung als paralleler Workflow: ein Agent je Fachphase 105–111 plus
Prüf-Agent, Hook-Änderungen an geteilten Dateien zentral eingespielt.)

- **Fundament (Phase 104):** Lead = Vorgang bleibt. Spalten `kunden.objektart`
  (EFH/RH/REH/MFH) + `parteien`; `vorgaenge.ad_id` (zuständiger AD/HV, A-7),
  `vorab_angebot` (F10), `veranstaltung_id`, `teilgenommen`; `vot_termine.typ`
  (vot|telefon|online, A-2), `medium`, `ics_uid`, `ics_sequence`;
  `benutzer.buchungslink`, `nebenstelle`; `ad_profile.terminiert_selbst` *(seit v33 gespiegeltes Kennzeichen der Rolle Handelsvertreter)*
  (Handelsvertreter, A-1), `kompetenz_sparten` (JSON), `kompetenz_kombi`,
  `kompetenz_mfh`, `kompetenz_gewerbe`; `lead_aktivitaeten.call_id/richtung/
  nebenstelle` (CTI-Vorbereitung). Tabellen `todos`, `info_veranstaltungen`,
  `benutzer_einstellungen`. Sparte **GW (Gewerbe)** als fünfter Code (Freitext-
  Erfassung wie WB). Steuerdatei (*v29: Spalte `nach_letztem` im Blatt Kaskade, keine
  Nurture-Mail +30 Tage, neues Blatt Terminhinweise*): Kaskade 5 Stufen (+2h · +1d 18:00 Mail · *(überholt – siehe v31)*
  +3d · +7d Mail · +14d `mail_disqualifiziert` letzter), Gründe `verloren`
  (Zu teuer · Kein Interesse mehr · Bleibt bei Öl/Gas · Woanders unterschrieben ·
  Sonstiges) und „Nachbearbeitung, noch nicht bereit für VOT“, Blätter
  **Objektarten** und **Status** (Phase → Label/Farbe/Board/Gruppe + monday-Status,
  Mapping 5a; `logik.board_fuer`, `logik.phase_fuer_monday`). Parameter
  `versuche_max` 5, `wv_meldet_sich_tage`, `pflichtfelder`, `kanal_farben` *(überholt – seit v35 aus
  `vertriebskanaele` abgeleitet, nicht mehr von Hand gepflegt)*,
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
  Status-/Kanal-Labels mit Farbe aus Blatt Status/`kanal_farben` *(Kanal-Farbe seit v35 aus der Kanal-Tabelle)*, 5 Versuchs-
  Punkte, Avatare, tel:/mailto, Spaltenkonfiguration je Nutzer
  (`benutzer_einstellungen` key `boards_spalten`), Inline-Edit per fetch
  (`POST /lead-management/boards/zeile/{id}`: status mit Pflichtgründen, notiz,
  ad_id, leadmanager_id, wiedervorlage *(ergänzt v35: zusätzlich Interessen, Kanal, Großkunde, Objektart,
  Telefon, E-Mail, Teilgenommen – Phase 186)*), Sammelaktionen registrierbar
  (`SAMMELAKTIONEN`, `POST /boards/sammelaktion`, Aktivität je Lead).
  Hauptboard = Phasen ohne aktiven VOT (Neu · Pausiert · Disqualifiziert, Label
  „Telefongespräch“), Terminiert = mit VOT bzw. terminiert/erfasst/angebot/
  gewonnen/verloren (Angebotserstellung mit „Erfassung starten“/„Angebot öffnen“,
  Angebotsversand, Gewonnen, Verloren „vor Termin“); Verloren setzt offene
  Angebote auf Abgelehnt (`lead_boards.angebote_ablehnen`, Hook in *(ergänzt – siehe v32: Verfolgungsstufe je Vorgang, Dialog „Nächster Schritt“, fünf Gründe mit Pflicht-Freitext)*
  `kern.lead_verloren`). Kanban zeigt nur das aktive Board. Reiter Kontaktiert
  (alle Versuche, Rufnummernsuche E.164 inkl. monday-Leads *(überholt – seit v35 EINE Suchleiste inkl.
  Rufnummer mit Sofortsuche, Phase 186)*), `/vorlagen` =
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
  Link „Zur Kundenkartei“; Objektart belegt O01/O03/PO01 des Bogens vor. *(überholt – siehe v31)*
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
  `lead_handelsvertreter.zuweisen` *(v35: Handelsvertreter verteilen nur innerhalb der eigenen Gruppe um,
  Phase 185)* (Sonderregel „Deals - Rene“, Ausschluss F14,
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
  Block 3 endet mit der Auslegungszeile – *überholt, seit v34 ohne Auslegungszeile*), „KL-Parameter“ (17 Zeilen: W/m²
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
  psl.) als letzter Zeile *(überholt – seit v34 keine Auslegungs-Position, Text in
  `angebote.auslegung_text`)*; `auslegungs_text` wörtlich nach Plan;
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
Dateien zentral. Alles weiter im **Demo-Modus** `lead_freigabe_modus = admin` *(bis v30; seit v31 freigeschaltet)*.
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
- **Spalten je Nutzer** (Hauptboard, Deals, Infoabend, Handelsvertreter; *(seit v33 auch die sechs Angebotstool-Tabellen, `TABELLEN_BOARDS` – siehe v33)*
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
  ohne Formular *(überholt – seit v35 `lead_v2.bearbeiten_erlaubt`: Außendienst an eigenen Leads mit Formular, Phase 185)*). `POST /stammdaten` bleibt als noscript-Fallback. Reiter Termin
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
  benutzer)` lässt HV (`terminiert_selbst`) nur zu, wenn `benutzer.id == hv.id` *(seit v33 auch über das Rollen-Kennzeichen handelsvertreter)*
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
  liefert `order_by(typ, name)`, das Template sichert montage-zuerst ab). Sichtbar nur *(seit v33 Basisrolle montage inkl. Varianten, `data-basis`)*
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
  Go-live-Eintrag trägt ein Badge „n/11 grün“. Die Inline-Abschnitte der alten *überholt – v33: „n/12 grün“*
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
  `kalender.frei_belegt/termin_schreiben/termin_aendern/termin_loeschen` (Rumpf *(überholt – seit v33 rufen diese Funktionen kein Netz mehr: Warteschlange + Cache, Phase 170)*
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
  `lead-mail-abruf`: 64 + 14 + 5 = 83 ≤ 90*), `DB_POOL_TIMEOUT` (10), *(seit v33 16 Läufe mit `outlook-sync`/`outlook-ruecklesen`: 64 + 16 + 5 = 85 ≤ 90)*
  `WORKER_THREADS` (64). `db.pool_invariante(anzahl_scheduler)` wird beim Start
  geprüft, protokolliert (`data\fehler.log`, Betriebs-Seite, /health „Pool-Invariante
  verletzt“) und bei Verletzung ins Fehlerprotokoll geschrieben.
- **`db.kurz()`** (Kontextmanager, commit bei Erfolg / rollback bei Fehler / immer *(seit v33 `kurz(schreibend=True)` → BEGIN IMMEDIATE; Lesesitzungen `kurz(schreibend=False)`)*
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
  (Antworten/Bounces aus termin@, aktiv nur mit Graph) – 14 Läufe*. Inaktive Läufe *(seit v33 zusätzlich `outlook-sync` 60 s und `outlook-ruecklesen` 300 s – 16 Läufe; mail-sync ohne Outlook-Teilschritt)*
  melden „inaktiv (Grund)“ – kein Fehler.
- **Sitzungsdisziplin der Läufe (Agent A):** `mail_sync.sync`, `sub_mail`/
  `terminmail.antworten_abgleichen`, `outlook_kalender.ruecklesen`, der monday- *(v33: `outlook_kalender.ruecklesen` ruft den Lauf `outlook_sync.ruecklesen_lauf`)*
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
  `/benutzer/import` (`app/benutzer_import.py`: `Name;Rolle;E-Mail;Team;Vertriebskanal`, *(seit v33 Rolle = Key oder Name jeder aktiven Rolle)*
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
  ohne Blättern, Bestands-Erfassungen ohne spätere optionale Fragen (O13/O09/A20 – *A20
  überholt, seit v30 gestrichen*) gelten
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
  (überspringt `OPTIONALE_FRAGEN` O09/O13/A20 – *seit v30 nur O09/O13, A20 gestrichen* –
  und Fragen mit „optional“/„leer lassen“ im
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
  _text`; Reihenfolge beim „Versand vorbereiten“ *(überholt – seit v34 bei PV/KL/WB Sparte vor
  AD-Vorlage)*: Vorlage des Außendienstlers → Sparten-Vorlage
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
  mit Kopfbild (180 px), unter 500 px ohne Foto; nur Tokens (*seit v30 die semantischen
  Tokens `--akzent`/`--text-titel`/`--flaeche-karte`, beide Modi – siehe v30*), keine
  externen Schriften;
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
- **Termine (Phase 135):** EIN Dialog (`templates/projektierung/_termin_dialog.html`, Makro *ergänzt v33 (Phase 168): Terminart Service-Einsatz (Gewerk, Anlass, auch am Vorgang ohne Projekt; Dialog-Kontext `projektierung.termin_dialog_kontext`)*
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
  Admin/Projektierung alles – bestätigt 08.10.2026). Standardansicht „Meine Einsätze“ (Heute/Diese *ergänzt v33 (Phase 167/168): Rollen-Varianten filtern nach Gewerk, Service-Varianten sehen nur Service-Einsätze ihres Gewerks*
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
  `wiederhol` (Spalte optionen = Einzelfeld, Formularfelder `<key>[]`, JSON-Liste, „+ weitere *ergänzt v33 (Phase 168): zusätzlich Typ `zeit`; Formular `servicebericht` hängt am Termin (`montage_formulare.termin_id`)*
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
`lead_freigabe_modus = admin` *(bis v30; seit v31 freigeschaltet)*. Alle Datenbankänderungen additiv (`vorgaenge.email_status*`,
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
  `ad_profile.terminiert_selbst` ohne Innendienst-/Leadmanagement-/Admin-Rolle sehen in der *(überholt – seit v33 Rolle Handelsvertreter (Kennzeichen) oder gespiegeltes Flag)*
  Icon-Leiste (`_nav.html`, Import `lm_nav … with context`) nur Mein Dashboard · Karte ·
  To-Dos · Handelsvertreter; Hauptboard, Deals, Kontaktiert, Infoabend und alle
  „Mehr …“-Einstiege liefern per URL 404 (`lead_v2.HV_GESPERRTE_PFADE`, `lead_v2.gate` –
  hinter Login/PIN-Wechsel der v27-Middleware; Links aus dem Tool mit Referer → 303 auf die
  HV-Ansicht mit Hinweis [ANNAHME A1] – *überholt seit Nachtrag 08.10.2026: immer 303, nie 404*).
  Karte (`routers/leadmanagement.karte/karte_daten`)
  zeigt HV nur eigene Leads/Termine/Startadresse, Mittelpunkt = eigene Leads *(überholt – seit v35
  Gruppensicht: alle Leads der eigenen HV-Gruppe, `lead_v2.hv_gruppe_fuer`, Phase 185)*; Kartei:
  Innendienst/Leadmanager nur Anzeige. Sammelaktion **„An Handelsvertreter verschieben“**
  (`lead_boards.SAMMELAKTION_HV`, auch Deals/Infoabend) mit zwei Ziel-Schaltflächen aus
  `hv_gruppe_rene`/`hv_gruppe_simon` (erster Eintrag = Ziel), Ausschluss F14 wird gemeldet *(überholt – seit v33 zweite Schaltfläche „Simons Gruppe“ mit Kennzeichen „noch nicht verteilt“)*
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
  Vorschläge, der erste „Ideal“ (`ideal`, `ideal_grund`; Rahmen Friondo-Blau – *seit v30
  Akzentfarbe je Modus* –, Badge, auch im
  Block Termine der Kartei), gebündelter Routing-Aufruf unverändert; Kalenderansicht per
  `GET /lead/{id}/termin/kalender.json?woche=&neu=1` (`lead_termin.kalender_json`: Mo–Sa,
  15-Minuten-Raster, Spalte je Kandidat, Tool-Termine, Outlook-Belegt nur bei `kalender_sync *(überholt – seit v33 Belegtzeiten aus dem Cache `outlook_belegt`, kein Graph im Request)*
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
  Infotext aus der Benutzerverwaltung – `Benutzer.vorname/infotext/bild_datei`, Upload *überholt – siehe v33 (Phase 175): ohne Infotext, Block = Bild, Name, Telefon, E-Mail*
  JPG/PNG ≤ 2 MB im AD-Profil nach `data/benutzerbilder/` *(ergänzt v35: eigener Upload unter „Mein Profil“,
  Phase 185)*) oder ein Bereich zwischen
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
  (Admin, Sitzung vorher frei, Demo nur Testpostfach – einzige Request-Ausnahme). Neuer Lauf *(überholt – siehe v31)*
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

## Neu in v30 – Design v2, Zurück-Navigation, BzA/Lieferschein/Zahlungsbedingungen, Projektierung Go-live (abgestimmt 11.10.2026)

(Plan: PLAN_V18.md, Phasen 145–152; ein gemeinsamer Commit am 11.10.2026, Rollout im
Wartungsfenster nach `docs/nach-dem-update-v30.md`. Vorlage für das Design: HTML-Prototyp
`docs/design-v30/vorlage/friondo-nachtglas-design.html` plus Screenshots `portal-dunkel.png`
und `hauptboard-dunkel.png` – nur die Optik übernommen; Aufbau, Inhalte, Routen,
Formularnamen und Rollenregeln aller Seiten sind unverändert; „Jetzt dran“, Suche oben,
Icon-Leiste für alle Module, „441 Hinweise“ wurden nicht nachgebaut. Umsetzung in vier
parallelen Agenten D1/D2/B/P mit eigenen DB-Kopien, Briefings und Berichte unter
`diagnose/v30/`.)

- **Design v2 – Tokens, Hell/Dunkel, Umschalter (Phase 145):** drei Token-Blöcke am Anfang
  von `app/static/style.css` – Hell (`:root`, heutige Friondo-CI; für 4,5 : 1 leicht
  nachgedunkelt: `--akzent #3376b6`, `--status-orange #9e5305`, `--status-grau #566376`,
  Sparten-Farben hell ebenso), Dunkel (`:root[data-theme="dunkel"]`, Vorlage „Nachtglas“:
  Fläche #070d1a, Karten #0e1626, Linien #1e2a40, Text #eef3fb/#9fb0c8, Akzent Cyan
  #67e8f9 mit dunklem Text #06202a, helle Statusfarben auf abgedunkelten Flächen, Kontur
  statt Schatten) und „Gerät entscheidet“ (`@media (prefers-color-scheme: dark)
  { :root:not([data-theme="hell"]) }` mit denselben Werten – Wächter prüft die Gleichheit).
  Semantische Tokens: `--flaeche`, `--flaeche-karte`, `--flaeche-erhoeht` (Kopfzeile),
  `--flaeche-hover`, `--flaeche-abgesetzt`, `--linie(-stark)`, `--text`, `--text-dezent`,
  `--text-titel`, `--text-invers`, `--text-auf-farbe`, `--link`, `--akzent(-hover/-text/
  -flaeche/-glanz)`, `--fokus`, `--status-*`(+`-bg`), `--sparte-wp/pv/kl/wb`, `--avatar-1…8`
  + `--avatar-text`, `--q-*` (inkl. `--q-veranstaltung`), `--pj-*`, `--schatten-1/2`,
  `--r-xl`, `--t-xxl`; die v14-Tokens (`--friondo-*`, `--g-*`, `--grau-*`) bleiben als Alias
  (`--friondo-dunkel` nur noch für Text – dunkle Flächen = `--flaeche-erhoeht` +
  `--text-invers`). Alle 363 Hex-/19 rgba-Werte in `style.css`, 95 in `lead_v2.css`, je 6–8
  in `login_v27.css`, `lead_v29.css`, `akte_v28.css`, `projektierung_v28.css` und die
  Inline-Farben der Templates sind auf Tokens umgestellt; feste Werte nur mit Kommentar
  `fest:` (Logo-Kachel, Dialog-/Lightbox-`::backdrop`, Druckansicht, Unterschrift-Canvas,
  Teamfarben-Text, helle Mail-Vorschauen, Leaflet-Pins, Farbfeld-Formularwerte). Schrift
  bleibt Systemschrift (Manrope der Vorlage liegt nur als woff2-Blob ohne Lizenzdatei im
  Bundle), Zahlen mit `tabular-nums` statt Monospace [ANNAHME]. Dokumentation
  `docs/design-system.md` Abschnitt „Design v2“ (Hex je Modus, Umschalter, Regeln für neue
  Seiten, Bausteine; alte Tabelle „bis v29“); Hinweis-Kommentar oben in
  `docs/projektierung-prototyp.html` und `docs/leadmanagement-prototyp.html`.
  **Umschalter** Menü ☰ → „Darstellung: Gerät · Hell · Dunkel“ (Radio-Chips, Icons
  `geraet`/`sonne`/`mond` in `_symbole.html`): `app/darstellung.py` (Werte `geraet | hell |
  dunkel`, Key `darstellung` in `benutzer_einstellungen`, Cookie `darstellung` 1 Jahr
  samesite=lax, `THEME_COLOR` hell #1b2a5e / dunkel #070d1a), `POST /einstellungen/darstellung`
  (`app/routers/einstellungen.py`, JSON oder Formular, alle Rollen – `/einstellungen` steht in
  allen Rollen-Pfadtabellen von `auth.py`), Middleware `auth._laden` → `request.state.darstellung`
  (gespeicherte Wahl gewinnt, nie gewählt → Cookie, sonst „Gerät“) → `<html data-theme>` in
  `base.html` VOR dem Rendern (kein Aufblitzen); `dispatch` zieht das Cookie nach, Login
  setzt es aus der Einstellung; `navigation.js` schaltet sofort um; `<meta name="theme-color">`
  je Modus (Jinja-Global `theme_color`, bei „Gerät“ zwei Einträge mit Media-Query). PDFs
  (fpdf2) unverändert: Kontroll-PDF byteidentisch bis auf Erstellzeit/ID, AST-Test ohne
  Token-/Template-Import in den PDF-Modulen.
- **Design v2 – Bausteine, Portal, Angebotstool, Anmeldeseite (Phase 146, D1):** Block
  „Design v2“ am Ende von `style.css`: Karten mit 1-px-Kontur/Radius `--r-l` (Schatten nur
  hell), Kennzahl-Kacheln `.kachel.stat` mit großer Zahl und Farbbalken links, Status-Pillen
  mit Punkt (Makro `status_badge`, Markup erweitert, Signatur unverändert; Pfeil „▾“ nur in
  Auswahl-Kontexten `.abzeichen.mit-pfeil`/`summary > .abzeichen`/`.statusform .abzeichen`),
  getönte Sparten-/Kanal-Chips (`color-mix`), Avatare mit Initialen (neues Makro
  `avatar(name, id, klasse='')` in `_komponenten.html`, Farbe aus `--avatar-1…8`), Tabellen
  mit Kapitälchen-Kopf/feiner Linie/Hover **ohne Zebra**, Chip-Selects, Knöpfe (Primär =
  `--akzent` + `--akzent-text`), Eingabefeld-Grundlinie, Menüs/Glocke/Wartungsbanner/
  Leer-Zustände/Fehlerseite (`fehler.html` mit `.fehler-seite`), `.darstellung-*`,
  `.zurueck-*`, Fokusring. Portal (`index.html`): Begrüßung „Guten Morgen/Tag/Abend,
  <Vorname>“ (Vorname aus `benutzer.vorname`, sonst erster Namensteil; Morgen < 11, Tag < 18)
  mit Wochentag · Datum · KW als reine Kopfzeile, Bereiche wie bisher [ANNAHME].
  Benutzerverwaltung mit Avataren; Anmeldeseite (`login_v27.css`) beide Modi; mobile
  Erfassung bei 390 px geprüft. Kontrast-Test: 27 Textpaare ≥ 4,5 : 1 und 21 dezente Paare
  ≥ 3 : 1 je Modus. Nebenbefund behoben: `.textform { display: grid }` übersteuerte das
  `hidden`-Attribut – die Inline-Textformulare aller Positionen standen im Editor offen
  (jetzt `.textform[hidden], .text-anzeige[hidden] { display: none }`).
- **Design v2 – Lead-Management, Projektierung, Montage (Phase 146, D2):** Modul-Tokens am
  Ende von `lead_v2.css` (`--lm-aktiv-bg/-fg`, `--lm-chip-text-mix`, `--lm-punkt-leer`, in
  allen drei Blöcken). Board-Tabellen (`leadmanagement/_tabelle.html`) nach
  `hauptboard-dunkel.png`: Spaltenköpfe Versalien mit Buchstabenabstand, feine Linien,
  Hover, Zahlen tabellarisch; **Status-Pille „Neu ▾“** (`status_pille`/`status_zusatz`,
  `.lm-status-pille.mit-pfeil` – Pfeil als `::after`, das `select.lm-mini` liegt unsichtbar
  über der Pille, `lm_boards.js` unverändert), Kanal-Chip und HV-Status als getönte Pille
  (Fläche `color-mix(in srgb, var(--f) 18%, transparent)`, Text hell `black 34%` / dunkel
  `white 35%`), Avatare AD/ID mit Pfeil (`.lm-person-pille`), Versuchs-Punkte, rote
  Überfällig-Markierung, Kennzeichen unter dem Kundennamen; Spaltenbreiten-Resizer (v29)
  unverändert. Statuskette der Kartei und Teamfarben (Kalender, Montage) nur noch als
  `--f`; Leaflet: Kacheln hell, Rahmen/Popups/Zoom über Tokens [ANNAHME]; Mail-Vorschauen
  bleiben hell (`fest:`). Projektierung: Kacheln mit Farbakzent oben, Chips, `pj-btn.primary`
  = Akzent, Spalten/Karten/Dialoge (nackte Lead-Dialoge tragen `lm-dialog`)/Kalender/
  Galerie/Steckbrief über Tokens, `.pj-mono` tabular-nums; Montage-Backend bei 390 px in
  beiden Modi. Nebenbefund behoben: Status-Farben der Phasen-Zähler (`.lm-phase .n`) waren
  seit v23 von einer Nachtrags-Regel überdeckt.
- **Zurück-Navigation (Phase 147):** Makro `zurueck_knopf(standard)` in `base.html`, Leiste
  `.zurueck-leiste` am Anfang von `<main>` auf allen Seiten außer `/`, `/angebotstool`,
  `/erfassung` (Außendienst-Start), `/lead-management(/dashboard)`, `/projektierung`,
  `/montage`, `/login`, `/pin-wechsel`, Erfassungsbogen (`/erfassung/…`) und eingebetteten
  Seiten (`einbett=1`); Seiten können `{% set zurueck_aus = true %}` setzen.
  `app/static/navigation.js`: Verlauf je Tab in `sessionStorage` (`friondo_verlauf`,
  30 Einträge, Pfad mit Query ohne `#`; gleicher Pfad wie der oberste Eintrag wird nicht
  angehängt – Reload/Redirect nach POST), Klick nimmt den obersten ANDEREN Eintrag, kürzt
  den Verlauf und navigiert (eine Ansicht zurück, keine Schleifen); leerer Verlauf →
  `data-zurueck-standard` (Angebot → `/angebote`, Erfassung → `/erfassungen`, Vorgangsakte →
  `/leads` bzw. Hauptboard für Leadmanagement, Projektakte → `/projektierung`, Einsatz →
  `/montage`, Parametrierung → `/parametrierung`, Lead-Seiten → Dashboard, sonst `/`).
  Editor-Sonderfall: kein `beforeunload`-Schutz vorhanden → keiner (Plan-Wortlaut). Test
  `tests/test_v30_navigation.py` (TestClient + Headless-Chrome über DevTools gegen uvicorn
  im Thread, lifespan aus).
- **BzA-Datenblatt (Phase 148, `app/bza_datenblatt.py`):** Frage A20 ist aus der Live-Excel
  (Blatt „Fragen“, Sicherung `diagnose/konfigurator_logik_v5.vor_v30.xlsx`) und aus
  `konfigurator.OPTIONALE_FRAGEN` gestrichen (alte Antworten bleiben im Erfassungs-JSON,
  `protokoll()` übergeht sie; gespeicherte Angebots-Protokolle zeigen die Zeile weiter);
  Abschnitt 2 ohne „Nennleistung“. Die Nennwärmeleistung ist im Dialog ein Zahlenfeld mit
  „kW“-Suffix (`.feld-mit-suffix`/`.feld-suffix`; Vorbelegung = kW der BAFA-Anlage, folgt
  der Geräteauswahl per `data-kw`, Komma/Punkt, „kW“ wird bereinigt, Ausgabe „9,50 kW“;
  ungültig → „Nennwärmeleistung: bitte nur die Zahl eingeben“, PDF-Route leitet mit Meldung
  in den Dialog zurück). Abschnitt 4 hat die Zeile „Geplante förderfähige Kosten inkl. 10 %
  Puffer“ (Schlüssel `kosten_puffer`, Kosten × (1 + Prozent), kaufmännisch auf volle Euro,
  Hinweis „Puffer für einen möglichen KfW-Ergänzungskredit – ändert den Auftragswert nicht“;
  Parameter `bza_kosten_puffer_prozent`, Standard 10, 0 = Zeile entfällt, Zeilentext folgt
  dem Satz; bei übersteuerten Kosten aus dem übersteuerten Wert); KfW-Rechnung, Förderblock
  und Höchstkostengrenze unverändert. Abschnitt 6 „Ersteller“ entfällt in Generator, PDF,
  Dialog und Gewerk-Seite (`routers/projektierung.py` ruft `erstellen` ohne Ersteller);
  `bza_ersteller_standard`, `FIRMA`, `ersteller_kandidaten/-standard` bleiben ohne Wirkung
  [ANNAHME]. Parametrierungs-Seite `/parametrierung/bza-ersteller` heißt „BzA-Datenblatt“
  und führt nur den Prozentsatz (Verteilerseite angepasst). Tests `tests/test_v30_bza.py`;
  `tests/test_bza_v19.py` und `tests/test_regression.py` nachgezogen (A20/Ersteller/Puffer).
- **Lieferschein (Phase 149, `app/lieferschein_pdf.py`):** jede Position mit Bezeichnung
  (fett) und VOLLSTÄNDIGER Beschreibung (7,5 pt, alle Zeilen wie im Angebots-PDF;
  Seitenumbruch innerhalb langer Texte, `header()` wiederholt den Tabellenkopf; `_kurztext`
  ist Alias von `_positionstext` und kürzt nicht mehr, `MAX_BESCHREIBUNG_*` entfallen).
  EP-Folgepositionen: Parameter `lieferschein_folgepositionen` (Standard `014: 015, 016,
  017`, Angebotstool-Einstellungen → „Lieferschein: abhängige Positionen“, eine Zeile je
  Hauptposition; leer = keine Abhängigkeit) – `lieferschein_positionen(angebot,
  folgepositionen)`: steht die Hauptposition im Angebot auf EP/Alternativ/bauseits,
  entfallen auch die Folgepositionen; fehlt sie ganz, bleiben sie. Der Editor zeigt an
  Folgepositionen „↳ folgt auf dem Lieferschein Pos. 014“ (`.folge-hinweis`, nur Anzeige)
  [ANNAHME]. Tests `tests/test_v30_lieferschein.py`; `tests/test_pv_v13.py::
  test_lieferschein_wp` prüft statt „kein €“ gezielt die Preisspalten (der Langtext von 014
  enthält „39,90 €/a“).
- **Fehler F-20261002-073115-9c9e (Phase 149):** der Eintrag liegt in keiner lokalen
  DB-Kopie (die Server-Kopie vom 03.10. hat die Tabelle `fehlerprotokoll` noch nicht, die
  migrierte Kopie 0 Zeilen; `data\fehler.log` des Servers lag nicht vor). Reproduktion
  „Überarbeiten → Version .2 → Duplizieren“ auf der DB-Kopie am unveränderten v29-Code:
  ohne Sperre fehlerfrei (alle Kennzeichen kopiert, Nummernkreis überspringt „.2“ – Ursache
  (b) ausgeschlossen); mit gehaltener SQLite-Schreibsperre (6,5 s und 13 s) starb
  `duplizieren` ohne die v22-Wiederholung an `sqlite3.OperationalError: database is locked`
  beim `INSERT INTO angebote` (`angebot_aufbau.angebot_anlegen` → `session.commit()`) →
  Fehlerseite „Datenbank kurz belegt“ mit Fehler-Nr. = **Ursache (a)**; der Zeitpunkt
  02.10. 07:31:15 passt zum Viertelstunden-Lauf 07:30 (monday-/mail-sync des v22-Codes
  hielt die Sitzung während der Netz-I/O – seit Hotfix 06.10./v27 kurz). Fix:
  `duplizieren`, `ueberarbeiten` und `kopieren` laufen über `_speichern` (Rollback + eine
  Wiederholung nach 0,7 s; Helfer `_positionen_kopieren`, `kl_json` wird mitkopiert).
  Regressionstest `tests/test_v30_duplizieren.py` (Sperre 6,5 s → Wiederholung greift,
  13 s → Meldung statt 500 + genau ein Protokolleintrag). Der Original-Eintrag auf dem Server
  (Parametrierung → Fehlerprotokoll bzw. `data\fehler.log`) ist einmal gegenzulesen.
- **Zahlungsbedingungen (Phase 150, `app/zahlungsbedingungen.py`, Tabelle
  `zahlungsbedingungen`, Spalten `angebote.zahlungsbedingung_key/_text`):** drei Einträge
  per `migration_v30_zahlung` (Standard = bisheriger Absatz, „50 % am Montagetag“, „80 %
  Anzahlung, 2 % Skonto“ – Texte 2/3 [ANNAHME], Innendienst liest gegen); die Nachtexte aller
  Profile WP/PV/KL tragen unter „### Zahlung“ den Platzhalter `{zahlungsbedingungen}`
  (`angebotsprofile._RECHT_UND_ZAHLUNG`; die Migration ersetzt den Standardabsatz
  leerzeichen-tolerant in jedem Nachtext-Block, meldet Blöcke ohne wörtlichen Absatz beim
  Erstlauf und legt die Parameter `bza_kosten_puffer_prozent`/`lieferschein_folgepositionen`
  an; Entwicklungs-DB: alle 12 Blöcke umgestellt, keine offenen). Rendering in
  `pdf_export._nachtext_rendern(zahlungsbedingung=…)` (`fuer_angebot(session, angebot)` →
  (Name, Text); leerer Schlüssel = Standard, `freitext` = Freitext; der Platzhalter
  erscheint nie wörtlich). Editor-Kopfkarte: „Zahlungsbedingung: <Name>“, im Entwurf
  Dropdown + „Abweichend (Freitext)“, `POST /angebote/<id>/zahlungsbedingung` (ID/Admin, nur
  Entwurf). Überarbeiten/Duplizieren/Kopieren, `angebot_aufbau.version_erzeugen` (damit
  auch die Rabatt-Version des Außendienst-Pfads) übernehmen beide Felder. Parametrierung →
  Zahlungsbedingungen (`konfiguration/zahlungsbedingungen.html`: Textfeld wie Textblöcke,
  neue Einträge, deaktivieren statt löschen – deaktivierte Einträge bleiben an bestehenden
  Angeboten gültig –, genau ein Standard, Warnblock für Nachtext-Blöcke ohne Platzhalter).
  E-Mail-Vorlagen: `{zahlungsbedingung}` = Name [ANNAHME]. Summen, KfW und DB unverändert
  (Kontrollangebot 30.245,43 €). Tests `tests/test_v30_zahlung.py`; `ANGEBOTSTEXTE.md`
  Abschnitte 6/9.3/9.6.
- **Projekt löschen (nur Admin, Phase 151):** Projektakte (Kopfblock, roter Knopf
  `pj-btn danger rechts`) und Projektliste (Checkbox je Zeile, „Ausgewählte löschen“) mit
  Sicherheitsdialog (`templates/projektierung/_loeschen_dialog.html`): Pflichtgrund, Eingabe
  der Projektnummer (Mehrfachauswahl: Anzahl + Nummern, Bestätigung „LÖSCHEN“ [ANNAHME]) und
  Hinweis „Das Löschen ist endgültig – das Angebot bleibt erhalten und kann erneut in ein
  Projekt überführt werden.“ `projektierung.projekt_loeschen(session, projekt, grund,
  benutzer) -> (ok, meldung)` räumt Projekt, Gewerke, Aufgaben/Paketinstanzen, Termine mit
  Besetzung (Outlook-Ereignisse vorher storniert – `verbindung_freigeben`, dann
  `outlook_kalender.event_loeschen`, best effort), Verlauf/Kommentare, Dokumente, Subs,
  Projekt-Mails, Montage-Formulare, Restarbeiten, UGL-Bestellungen, Steckbrief und die
  Glocken-Einträge der Akte ab; BzA-/Heizreport-Felder gehen mit dem Gewerk (Heizreport-
  Projekt bleibt im Portal). Angebote: `projekt_gewerk_id = NULL`, Status unverändert
  („Angebot → Projekt“ wieder sichtbar, Vorgangsakte ohne Projekt); Galerie-Dateien bleiben
  am Vorgang. Dokumentenordner wird nach `data/projekte/_geloescht/<PR>_<JJJJMMTT-HHMM>/`
  verschoben (nicht gelöscht [ANNAHME]). Lösch-Protokoll (`AngebotsLoeschung`, neue
  additive Spalten `art` „angebot“|„projekt“ und `grund`; Anzeige unter Parametrierung →
  Angebotstool-Einstellungen → „Lösch-Protokoll Angebote & Projekte“ mit Spalten Art/Grund)
  und Notiz im Vorgangs-Chat „Projekt <PR> gelöscht: <Grund>“ (`herkunft = projektierung`).
  Nicht löschbar (`loeschen_gesperrt`): Gewerk in Phase Montage oder später mit
  abgeschlossenem Montage-Formular → Hinweis auf Storno [ANNAHME]. Routen `POST
  /projektierung/projekt/{id}/loeschen` und `POST /projektierung/liste/loeschen` (403 für
  Nicht-Admins, JSON bei Accept application/json). Projektnummern werden nie
  wiederverwendet. **Demo-Projekte:** `projektierung.ist_demo_projekt(projekt, kunde,
  vorgang)` – `vorgaenge.demo = 1` oder Kunde „Demo …“ / `@demo.example` (Muster von
  `scripts/demo_projekte.py`); Projektliste mit Filter „Demo“ (`?demo=1`) und Badge
  (`.demo-badge`, auch im Kopf der Akte); Bestandsimport-Projekte (`angebote.bestand = 1`)
  sind nicht betroffen. Go-live: nach dem Rollout Demo-Projekte löschen, Checkliste prüfen,
  dann Parametrierung → Projektierung-Einstellungen → `freigabe_modus = alle` (Portal-Badge
  weg, Montage-Login in `/montage`, Rolle Projektierung sieht das Modul); Lead-Management
  bleibt `lead_freigabe_modus = admin` *(überholt – seit v31 alle)*. Stand der Go-live-Checkliste auf der Server-Kopie
  vom 03.10.2026: 1/11 (nur Montageteams), alle offenen Punkte sind Stammdaten-/
  Betriebspunkte. Tests `tests/test_v30_projekt_loeschen.py` (9).
- **Tests, Rollout-Vorbereitung, Doku (Phase 152):** neue Tests `tests/test_v30_design.py`
  (26: Token-Wächter CSS + Templates mit `fest:`-Begründungen, Dunkel = Media-Block,
  data-theme aus Cookie/Einstellung inkl. Cookie-Nachzug, Kontrast, Makros, Portal-Begrüßung,
  Seiten in beiden Modi, PDF unverändert), `test_v30_navigation.py` (9), `test_v30_bza.py`,
  `test_v30_lieferschein.py`, `test_v30_duplizieren.py`, `test_v30_zahlung.py` (zusammen 33),
  `test_v30_projekt_loeschen.py` (9); angepasste Alt-Tests: `test_v27_nachtrag2.py::
  Anmeldeseite::test_foto_und_styles` (semantische Tokens statt `--friondo-*`/Hex),
  `test_bza_v19.py`, `test_regression.py`, `test_pv_v13.py` (siehe oben).
  `scripts/design_screenshots.py` neu ohne Playwright (Chrome headless + DevTools über
  `websockets`; `vorher|nachher --modus hell|dunkel [--server URL --port --cdp --db --data
  --seiten --ziel]`, elf Seiten inkl. Montage-Einsatz und mobile Erfassung bei 390 px, EK/DB
  per eingefügtem Style ausgeblendet); Screenshots `docs/design-v30/<seite>-vorher-hell.png`
  (v29-Code aus einem Worktree) und `-nachher-hell|dunkel.png`. `scripts/voll_crawl.py
  --darstellung hell|dunkel` (Cookie). Rollout-Vorbereitung `diagnose/v30/abschluss_tests.sh`
  (Server-Kopie, `migrate.py` zweimal, Testbenutzer je Rolle, Gesamtsuite, Abnahme, Crawl
  sechs Rollen je hell/dunkel, Smoke). Kein neuer Lasttest: keine neuen Netz- oder
  Hintergrundläufe (eine indexierte Leseabfrage je Anfrage in der Middleware, Outlook-Storno
  nur beim seltenen Projekt-Löschen nach Sitzungsfreigabe). Doku: `docs/design-system.md`
  („Design v2“), `docs/nach-dem-update-v30.md`, `docs/updates.md`, `docs/betrieb.md`
  (Middleware-Zeile, Outlook-Storno), `config.VERSION = "v30"`.
- **Nachtrag 12.10.2026 – Entscheidungen zu den Rückfragen des Durchlaufs** (Andreas: „im
  Sinne des Projekts entscheiden“, Nummern wie in `diagnose/v30/gesamtuebersicht.md`):
  (1) Pfeil „▾“ nur an Pillen mit Auswahlmenü; (2) **Kennzahlen der Angebotstool-Karte in
  Blau** wie in der Vorlage (`.stat-zahl.blau` in `index.html` und `_angebotstool_kacheln.html`,
  Dringendes bleibt rot); (3) weiße Logo-Kachel bleibt, bis eine Logo-Variante für dunkle
  Flächen vorliegt; (4) Telefon/E-Mail bleiben getrennte Spalten (Spaltenkonfiguration je
  Benutzer, keine Migration); (5) Lead-Pins fest auf hellen Kacheln; (6) Systemschrift bleibt
  (kein Font-Download); (7) „Gerät entscheidet“ mit emuliertem dunklem Farbschema im Browser
  geprüft – kein Aufblitzen, `data-theme` bleibt leer, Media-Block greift beim ersten
  Rendern; (8) Texte 2/3 bleiben bis zur Durchsicht des Innendiensts; (9) **Außendienst sieht
  die Zahlungsbedingung** (Name, lesend) auf `/meine-angebote/<id>`
  (`routers/meine_angebote.detail`, `meine_detail.html`); (10) deaktivierte Einträge bleiben an
  bestehenden Angeboten gültig; (11) Textfeld statt HTML-Editor; (12) Gewerk-Seite verlinkt auf
  den Dialog am Angebot; (13) halbe Prozentpunkte erlaubt; (14) Sperre nur bei
  abgeschlossenem Montage-Formular ab Phase Montage (sonst wäre das Demo-Projekt in Montage nicht
  löschbar); (15) „LÖSCHEN“ bleibt; (16) Lösch-Protokoll mit Art/Grund bleibt; (17)
  `_geloescht` wird von Hand aufgeräumt (kein neuer Lauf); (18) Demo-Kennzeichen über
  Namensmuster/`vorgaenge.demo` reicht; (19) Go-live-Pflichtpunkte und begründete Ausnahmen in
  `docs/nach-dem-update-v30.md` Punkt 7 festgelegt; (20) Server-Kopie/`fehler.log` weiter
  erbeten (Gegenlesen des Fehlers); (21) **Routing-Cache und Aufruf-Zähler best effort:**
  `routing._cache_schreiben` fängt `OperationalError … locked` beim Upsert ab (Warnung im Log,
  Eintrag übersprungen, Anfrage rechnet weiter); `geocoding._zaehler` beendet vorher die laufende
  Lesetransaktion und zählt in einer eigenen kurzen Transaktion, bei Sperre wird die Zählung
  übersprungen. Hintergrund: SQLite WAL liefert bei einem Schreibzugriff nach Lesezugriffen
  derselben Transaktion sofort „database is locked“ (BUSY_SNAPSHOT), sobald ein anderer
  Schreiber zwischenzeitlich festgeschrieben hat – der `busy_timeout` greift dort nicht; die
  Flanke in `test_pool_hotfix::test_40_…` (20 gleichzeitige Terminvorschläge) kam daher. Eine
  allgemeine Lösung (`BEGIN IMMEDIATE` für schreibende Anfragen) bleibt ein eigener Punkt; *(erledigt in v33, Phase 172 – Hybrid: nur Schreibsitzungen)*
  (22) `angebot_anlegen` mit
  `commit=False` innerhalb von `_speichern` bleibt ein eigener Plan; (23) **Demo-Badge auch auf *(erledigt in v33, Phase 172)*
  den Board-Karten** (`projektierung/kanban.html`). **(24) Befund Andreas (Vorschau 12.10.2026):
  Drag & Drop im Kanban-Board tat nichts.** Ursache: Jinja `tojson` lässt doppelte
  Anführungszeichen stehen – in DOPPELT gequoteten on*-Attributen endete das Attribut am ersten
  Anführungszeichen der Sparten-Liste (`ondragstart="kartenStart(event, [1, 3], ["` → Browser
  „Uncaught SyntaxError: Unexpected end of input“, `kartenStart` lief nie, `kartenDrop` brach
  mangels `dragGewerke` ab) – seit v17 (V4 Phase 90.1, Sparten-Liste). Dasselbe Muster brach den
  Kanal-Prompt und den Abbrechen-Knopf des Ablehnungsdialogs im Editor (v8/v11), den
  Abbrechen-Knopf am TAIFUN-Eintrag, die Kopierknöpfe der Gewerk-BzA-Seite (v15) und die neue
  Zahlungsbedingungs-Auswahl (v30). Lösung: `| tojson | forceescape` in allen sechs Stellen
  (Regel: `tojson` in doppelt gequoteten Attributen nur mit `forceescape`, sonst einfach
  gequotet); Test `tests/test_v30_nachtrag.py` prüft on*-Attribute auf ausgeglichene Klammern und
  die `&quot;`-Kodierung. Commit „v30-Nachtrag 12.10.2026“ (3cd0299, gepusht).
  **(25) Vollansicht des Kanban-Boards** (Wunsch Andreas 12.10.2026, Commit „v30-Nachtrag 2“):
  Knopf „⛶ Vollansicht“ im Seitenkopf des Boards (`projektierung/kanban.html`, `pjVollansicht()`)
  setzt `body.pj-vollansicht` (CSS in `projektierung_v28.css`: Kopfzeile, Seitenkopf, Kennzahlen,
  Hinweis, Fußzeile, Zurück-Leiste ausgeblendet, Filter bleiben, `hoeheSetzen` rechnet die
  Board-Höhe neu) und fordert Browser-Vollbild an (`requestFullscreen`, ohne Geste bleibt die
  CSS-Vollansicht); Knopf „⤡ Vollansicht beenden“ fest oben rechts (`.pj-nur-vollansicht`),
  Escape beendet beides (`fullscreenchange`/`keydown`, nicht bei offenem Dialog); Wahl in
  `sessionStorage` (`pj_vollansicht`), damit sie ein Neuladen im Tab überlebt. Test in
  `tests/test_v30_nachtrag.py`.
  **(26) Sub-Teams im Termin-Dialog** (Befund Andreas 12.10.2026, Commit „v30-Nachtrag 3“): die
  Arten Montage (WP) und Elektro zeigten in `static/projektierung.js` (`ARTEN_TEAM`) nur Teams
  vom Typ `montage`; Sub-Teams waren nur beim Sub-Einsatz wählbar. Jetzt `{montage: '',
  elektro: '', sub: 'sub'}` (leer = kein Filter): Montage/Elektro bieten Montage- und Sub-Teams
  (Zusatz „(Sub)“), der Sub-Einsatz bleibt auf Sub-Teams beschränkt. Serverseitig war ein
  Sub-Team für Montagetermine schon immer erlaubt (`termin_speichern` verlangt nur ein Team;
  Zuweisung `wp_team_id`/`elektro_team_id` folgt dem Team), der Team-Kalender zeigt alle
  aktiven Teams. Tests in `tests/test_v30_nachtrag.py` und `tests/test_proj_v6_termine.py`.

## Neu in v31 – Lead-Management V5 Feedback-Runde 3: Objekte am Vorgang, Großkunde, Kartei V5, Archiv/Duplizieren, Vorlagen in Langform, MS/WA/DMS, Testphase (abgestimmt 13.10.2026)

(Plan: PLAN_LEAD_V5.md, Phasen 153–160; umgesetzt am 13.10.2026 im gemeinsamen Durchlauf mit
v32 (PLAN_V19, Phasen 161–165) – EIN Commit, kein Push vor Freigabe. Entscheidung Andreas
13.10.2026: die Vorbedingung „v30 auf dem Server“ entfällt, gebaut auf dem committeten
v30-Stand `1f0b764`. Arbeitsweise: Fundament durch den Orchestrator, dann vier Agenten
K (Kartei), T (Termine/Mails), B (Boards/Dashboard/Einstellungen), AT (Angebotstool/
Projektierung/Benutzer) auf eigenen DB-Kopien, Berichte unter `diagnose/v31/` (lokal). Alle
Datenbankänderungen additiv – v30-Code läuft auf der v32-Datenbank weiter (Rückweg-Probe in
der Rollout-Vorbereitung v32). Entscheidungen, [ANNAHME]-Auflösung, angepasste Alt-Tests und
Rückfragen: `docs/leadmanagement-entscheidungen.md` Abschnitt V5; Team-Hinweise:
`docs/nach-dem-update-v31.md`.)

- **Fundament (Orchestrator):** neue Tabellen `vorgang_objekte` (Modell `VorgangObjekt`:
  `vorgang_id`, `bezeichnung` „Objekt 1“, Adresse, `objektart`, `parteien`, `interessen` (JSON),
  Koordinaten, `reihenfolge` (1 = Hauptobjekt), `aktiv`, `rechnung_abweichend` + `rechnung_*`) und
  `benutzer_abwesenheiten` (`BenutzerAbwesenheit`: `art` krankheit|urlaub, `von`, `bis`, `bemerkung`);
  neue Spalten `vorgaenge.archiviert_am/archiviert_von/kopie_von_id/wiedervorlage_art/
  verfolgung_status`, `kunden.grosskunde`, `benutzer.leadmanager`, `objekt_id` an `vot_termine`,
  `erfassungen`, `angebote`, `projekt_gewerke`, `ablehnungsgruende.freitext_pflicht` (alle in
  `db._NACHTRAEGLICHE_SPALTEN`). Migrationen (Hooks in `migrate.py`, idempotent):
  `objekte.migration_v31_objekte` (je Vorgang ein Hauptobjekt aus der Kundenadresse, `objekt_id`
  an Terminen/Erfassungen/Angeboten/Gewerken, Waisen-Bereinigung, **Trigger
  `trg_v31_vorgang_objekte`** – löscht die Objekte eines gelöschten Vorgangs, auch bei Bulk-/
  SQL-Löschungen; Befund: SQLite vergibt IDs neu, verwaiste Objekte „erbten“ sonst an neue
  Vorgänge), `lead_v5.migration_v31_lead` (Leadmanager-Häkchen für die sechs Startnamen, Parameter
  `terminierung_aktiv`/`mail_versand_aktiv` = aus, `sparten_langnamen`, `grosskunde_farbe`,
  `hv_gruppe_simon_mitglieder`, Samstag aus den AD-Arbeitszeiten, `lead_freigabe_modus = alle`,
  `pflichtfelder` + `ad_id`), `lead_mail.migration_v31_mails` (T). Neue Module: `app/werktage.py`
  (NRW-Feiertage/Osterformel aus `lead_info` herausgezogen, `ist_werktag`, `plus_werktage`,
  `naechster_werktag`), `app/sparten.py` (`SPARTEN` = WP/PV/KL/WB/GW/MS/WA/DMS, Langnamen,
  `sparten_text`, `sparten_interesse`, `ist_freitext_sparte`; `models.INTERESSEN` erweitert),
  `app/objekte.py` (`hauptobjekt`, `hauptobjekt_sync` Kundenfelder ↔ Hauptobjekt,
  `objekt_anlegen`, `objekte_fuer`, `vorgang_interessen`, `objekte_loeschen`,
  **`ausfuehrungsort(session, objekt_id=|angebot=|erfassung=|gewerk=|termin=|vorgang=|kunde=)`** –
  Master-Regel: beim Hauptobjekt zählt immer die Kundenadresse, bei Objekt 2 ff. die Objektadresse),
  `app/abwesenheiten.py` (`anlegen`, `beenden`, `aktive`, `ist_abwesend`, `hinweis_text`),
  `app/lead_v5.py` (`runden_5min`, Schalter `terminierung_aktiv`/`mail_versand_aktiv`,
  `TESTPHASE_HINWEIS`, `MAILSPERRE_HINWEIS`). Steuerdatei `leadmanagement_logik_v1.xlsx`
  (Sicherung `diagnose/leadmanagement_logik_v1.vor_v31.xlsx`): Blatt Kaskade Versuch 2/4
  `aktion = keine`, Blatt Status Label „Disqualifiziert“ (Key `unqualifiziert` bleibt), Blatt
  Wunschzeiten neue Spalte `aktiv` (samstag = nein), Blatt Terminhinweise Zeilen MS/WA/DMS „(Punkte
  folgen)“; `leadmanagement_logik.SPARTEN` um MS/WA/DMS, `Wunschzeit.aktiv`. `auth.py`: der
  Innendienst darf die Abwesenheits-Routen der Benutzerverwaltung (`_INNENDIENST_BENUTZER_AUSNAHME`);
  `monday_sync.kunde_fuer_lead` zieht das Hauptobjekt nach. Tests `tests/test_lead_v5.py` (11:
  Werktage, Sparten, Rundung, Schalter, Abwesenheiten, Migrationen zweimal ohne Änderung).
- **Kundenkartei V5 (Phasen 153/155/157/158, Agent K; `app/lead_kartei.py`, `app/routers/lm_kartei.py`,
  Templates `leadmanagement/kartei*.html`, neu `kartei_objekte.html`, `kartei_mail_dialog.html`,
  `app/static/lm_kartei.js`):** Reihenfolge Kopf (Name, Badges inkl. **Großkunde** `lm-grosskunde`,
  Archiv-Banner mit „Wiederherstellen“ und Kopie-Verweise, Statuskette mit **Statuswechsel** per
  Klick/Dropdown „Status ändern …“ → `POST /lead/{id}/status`, dieselben Regeln/Gründe wie
  `lead_boards.status_setzen`; abgeleitete Phasen nicht wählbar, Verloren nur mit Grund) →
  **Notizen-Chat (zwei Drittel) neben To-Dos (ein Drittel, Makro `todo_spalte`)** → Kundeninfo-Block
  mit **Block „Objekte“** (Ein-Objekt-Vorgang: bekannte Adressfelder + „Weiteres Objekt hinzufügen“;
  ab zwei Objekten Karten je Objekt mit Autospeichern `POST /lead/{id}/objekt/{oid}`, Termin-Status
  aus `lead_termin.objekt_termine`, Erfassungs-/Angebots-Chips, Pfeile – Hauptobjekt bleibt
  Position 1 –, Deaktivieren statt Löschen; Routen `POST …/objekt`, `…/deaktivieren`,
  `…/aktivieren`, `…/reihenfolge`; Hauptobjekt ↔ Kundenfelder über `objekte.hauptobjekt_sync`;
  Interessen-Badges = `objekte.vorgang_interessen`) → Reiter **Anruf · E-Mail · Timeline**
  (`?tab=termin` springt zum Block Termine; Timeline aus `vorgang_verlauf.eintraege` mit
  Herkunfts-Badge Lead · Angebot · Projekt) → Block **Termine** (Werkzeuge, Termin je Objekt, drei
  Vorschläge, Kalenderansicht `#lmt-kalender` über `lm_termin.js`, Historie mit Aktionen) →
  Angebote · Erfassungen · Projekt (`vorgang_verlauf.projekt_block`) · Anhänge. **Pflichtfeld
  Außendienst** (`ad_id`, rot + „Bitte Außendienst zuweisen“, HV-Lead gilt als erfüllt;
  `lead_kartei.pflicht_offen_namen` ergänzt Pflichtfelder weiterer Objekte „Objekt 2: Straße“),
  **MFH-Frage** „Rechnungsadresse identisch mit der Objektadresse?“ (Ja/Nein, Feld
  `rechnung_abweichend`; Rechnungsadresse zählt nur bei Nein; Hauptobjekt → `kunden.rechnung_*`,
  sonst `vorgang_objekte.rechnung_*`), Interessen inkl. **MS/WA/DMS**, Innendienst-Dropdown nur
  Leadmanager (`lead_dropdowns`, „(nicht mehr wählbar)“), Großkunde-Häkchen mit Aktivität „als
  Großkunde gekennzeichnet“. **E-Mail-Dialog** (Schnellaktion E-Mail / „Mail mit Vorlage“,
  `kartei_mail_dialog.html`) auf T's Routen `GET /lead/{id}/mail/vorschau.json?vorlage=&objekt_id=&
  termin_id=` (Vorlagen aus `lead_mail.vorlagen_katalog`, Platzhalter aus Lead/Objekt/Termin/
  Vertriebler, fehlende Pflichtdaten → Senden gesperrt, ICS bei Terminvorlagen) und
  `POST /lead/{id}/mail/senden` → `lead_mail.in_warteschlange` (Lauf `lead-mail` sendet;
  Testphase: gesperrt), Aktivität + E-Mail-Verlauf. Terminierung: der Kopf-Knopf postet
  `bestaetigung` (eine | je_objekt | auto, Radios bei > 1 vorgemerktem Objekttermin) an T's
  `POST /lead/{id}/terminierung`; `lead_kartei.terminierung_pruefung` = vorgemerkte Objekttermine +
  Pflichtfelder, „Vormerken“ im Block Termine per fetch an `…/termin/vormerken` (Objektauswahl bei
  mehreren Objekten). Wiedervorlage-Dialog `step=300` + `lead_v5.runden_5min`. Testphase:
  „Terminierung“, „Vormerken“, „Termin manuell“, Umbuchen/Absagen ausgegraut mit Tooltip
  `lead_v5.TESTPHASE_HINWEIS`. Die Kartei-V5-Regeln liegen in `lead_v2.css` (Block „Kartei V5“).
  Tests `tests/test_lead_v5_kartei.py` (18).
- **Termine je Objekt (Phase 153, Agent T; `app/lead_termin.py`, `routers/lm_termin.py`):**
  Terminassistent, Kalenderansicht und manuelle Buchung nehmen `?objekt_id=` (bei mehreren Objekten
  Auswahl „Objekt wählen“ mit Terminstand); Vorschläge, Kandidatenfilter und Fahrzeiten rechnen mit
  der Objektadresse (`objekte.ausfuehrungsort`, Geocoding je Objekt in `_geokodieren_bei_bedarf`);
  `vot_termine.objekt_id`/`adresse` sind immer gesetzt. Vormerken je Objekt (`POST /lead/{id}/termin/
  vormerken`, `lead_termin.vormerken`), „Terminierung“ bucht alle vorgemerkten Objekttermine in einem
  Schritt (`lead_termin.terminierung_ausfuehren`, Route `POST /lead/{id}/terminierung` + Alias
  `…/termin/terminierung`, `_speichern`-Muster; Objekte ohne Termin bleiben offen – „1 von 3
  Objekten ohne Termin“); Phase Terminiert ab dem ersten Objekttermin, Absage/Umbuchung/Ersatzkunde
  je Objekttermin; `lead_termin.objekt_termine(session, vorgang)` für den Kartei-Block; Buchung über
  `lead_termin.vot_buchen` (Objektfelder) statt `kern.termin_buchen`. `lead_termin.adresse_fehlt`
  prüft beim Hauptobjekt die Kundenadresse (Master-Regel).
- **Terminbestätigung bei mehreren Objekten (`app/lead_mail.py`):** Vorlage
  `terminbestaetigung_objekte` (Rahmen + `{vertriebler_block}`, `{objektliste}`, `{termin_datum}` =
  Tag/Zeitraum) mit ICS je Objekttermin (eigene UID, `anhang_pfad` „;“-getrennt,
  `lead_mail.anhang_pfade`); Wahl „eine Bestätigung“ | „je Objekt“ (`bestaetigung_vorbelegung`:
  gleicher Tag → eine), „je Objekt“ nutzt die Vertriebler-Vorlage mit `{objektadresse}`;
  „Bestätigung erneut“ fragt bei mehreren Objekten (`termin_ids`, `zusammen`).
- **Sparten ausgeschrieben (Phase 156):** `{sparten}` = `sparten.sparten_text` („Wärmepumpe und
  Photovoltaik“), `{sparten_interesse}` („Interesse an einer Wärmepumpe“), `{sparten_hinweise}` mit
  Langform als Zwischenüberschrift, ICS-Titel in Langform; `migration_v31_mails` ersetzt Kürzel
  WP/PV/KL/WB/GW als eigenständige Wörter in gespeicherten Vorlagen/Betreffs (`kuerzel_ersetzen`,
  Meldungen „v31: Vorlage <key>: WP → Wärmepumpe (n×)“), legt `terminbestaetigung_objekte` und
  `falsche_telefonnummer` an und storniert offene `nicht_erreicht`-Mails. Vorlage `nicht_erreicht`
  ist ausgeblendet (`VORLAGEN_AUSGEBLENDET`, Datensatz bleibt), der Lauf `lead-mail` storniert
  Altbestand; Kaskade Versuch 2/4 = keine (`lead_uebersicht.kaskade_text`: „nach Versuch n
  „Disqualifiziert“ (Mail, …)“).
- **Montag bis Freitag, Krankheit (Phase 158, T):** Vorschläge, `kalender.json` (5 Spalten) und
  `/kalender` ohne Samstag, Wunschzeit „samstag“ (`Wunschzeit.aktiv = False`) ignoriert, manuelle
  Buchung am Samstag nur mit Warnhinweis; Vertriebler mit `abwesenheiten.ist_abwesend` werden mit
  Begründung „krank“ ausgeschlossen (tagesgenau), Umbuchung ohne den Kranken per `?ohne_ad_id=`.
  `lead_mail.falsche_nummer_mail(session, vorgang, benutzer)` sendet die Vorlage
  `falsche_telefonnummer` (Platzhalter `{absender}`, `{vorname}`, `{nachname}`) nur bei vorhandener
  E-Mail.
- **Testphase (Phase 159, T/B)** *(ergänzt v35: „Terminierung“ erzeugt in der Testphase die TAIFUN-Übergabedatei,
  sobald `taifun_export_aktiv = an`, Phase 183)*: `terminierung_aktiv = aus` → Vormerken/Buchen/manuell/Umbuchen/
  Absagen/Terminierung/Vorab-Gespräche liefern `lead_v5.TESTPHASE_HINWEIS` (403 JSON
  `{"ok": false, "meldung": …}` bzw. Redirect), Knöpfe ausgegraut mit Tooltip, Vorschläge als
  Aktivität „Vorschläge berechnet: …“ (max. alle 10 Min je Lead, eigene kurze Transaktion
  `lead_termin.vorschlaege_protokollieren`); Kontext `lead_termin.testphase_kontext(session)`.
  `mail_versand_aktiv = aus` → Warteschlangen-Einträge enden gerendert als `gesperrt` (kein Graph,
  kein Testpostfach, keine fehler-Glocke), `mail_modus` ist keine Steuerung mehr, gesperrte
  Einträge werden nicht nachgesendet („Erneut senden“ = bewusster Klick), `lead_mail.
  gesperrte_anzahl`. Verträge für die Kartei: `lead_mail.vorlage_rendern(…) -> (betreff, html,
  fehlende)`, `lead_mail.in_warteschlange(…)` (fester Text, `kanal = mail_fest`). **Demo-Ende:**
  `leadmanagement.DEMO_BEENDET = True` – `freigabe_modus()` immer „alle“, `demo_aktiv()` False,
  Sichtbarkeit rollenbasiert, Portal-Karte ohne „Coming soon“; einmalige Abfrage „Demo-Leads löschen
  oder behalten“ in den Lead-Einstellungen (`demo_leads_loeschen` mit Lösch-Protokoll
  `AngebotsLoeschung art=lead`, Marker `demo_ende_v31`); Abschnitt „Freischaltung“ mit
  `terminierung_aktiv`/`mail_versand_aktiv`, Prüfpunkten (`lead_v2.freischaltung_pruefpunkte`) und
  Zähler „Mails gesperrt“; Kommunikation: Status `gesperrt`, Meldung „Testphase: nicht gesendet
  (gesperrt).“, `mail_mit_vorlage` über `lead_mail.in_warteschlange`.
- **Großkunde (Phase 153, B):** `kunden.grosskunde` – Badge `.lm-grosskunde` (Farbe Parameter
  `grosskunde_farbe`, `lead_boards.grosskunde_farbe`) am Kundennamen in Boards, Anrufliste, Kanban,
  Karte, HV-Ansicht; Spalte „Großkunde“ (Standard aus, sortierbar), Filter-Chip in Hauptboard/Deals/
  Anrufliste.
- **Archiv als Lead-Sicht (Phase 154, B/AT):** `app/lead_archiv.py` – `vorgaenge.archiviert_am/_von`;
  `filter_aktiv(abfrage)` in JEDER Lead-Liste/Kennzahl (Vertrag); Sammelaktionen Archivieren
  (Übersprung bei aktivem Termin/offener Erfassung/offenem Angebot), Wiederherstellen (Archiv-Sicht
  `?archiviert=1` und Vorgangsakte `POST /vorgaenge/{id}/archiv-wiederherstellen`), Duplizieren
  (`vorgaenge.kopie_von_id`, Objekte 1:1, keine Historie); Angebotstool/Projektierung zeigen
  archivierte Vorgänge unverändert (Banner in der Vorgangsakte).
- **Dashboard (Phase 154/158, B):** Kachel-Reihenfolge je Nutzer (`dashboard_kacheln`,
  `lead_dashboard.KACHELN`, `lm_dashboard.js`, Stift-Symbol, Drag & Drop, „Zurücksetzen“); „Fällig
  heute“ Erledigt als absolut positionierte Leiste mit Rückgängig (JSON `POST /dashboard/
  wiedervorlage/{id}`; Ursache des alten Fehlers: unpositioniertes `<details>`-Menü in der 1 %-Zelle);
  Krankheitshinweise `lead_dashboard.kranke_termine` mit Umbuchen/Absagen; eigener
  Abwesenheitseintrag (Karte „Abwesenheit“, auch auf „Meine Termine“ des angestellten AD).
- **Boards (Phase 154, B):** fixierte Zweit-Scrollleiste `.lm-scrollleiste` (sticky bottom,
  synchron, Shift + Rad, mittlere Maustaste) in `lm_boards.js`; Deals-Board gruppiert Erfassungen/
  Angebote/Termine je Objekt (`vorgang_verlauf.objekt_gruppen`, nur bei mehreren Objekten).
- **Zuständigen-Dropdowns (Phase 156, B):** NUR über `app/lead_dropdowns.py` – Leadmanager =
  `benutzer.leadmanager` (nach Vorname, Altwert „(nicht mehr wählbar)“), Außendienst = angestellte AD
  ohne `terminiert_selbst`; HV-Lead → nur seine Gruppe (`hv_gruppe_rene`, `hv_gruppe_simon` + *(seit v33 ohne Rolle/Kennzeichen Handelsvertreter)*
  `hv_gruppe_simon_mitglieder`). Round-Robin verlangt weiterhin `lm_aktiv` UND Häkchen.
- **Sparten MS/WA/DMS (Phase 157, B/AT):** Codes aus `app/sparten.py` überall (Jinja-Globals
  `lm_sparten`, `lm_sparten_lang`), Boards/Anrufliste/Kanban/Karte/Trichter/Kanal-Report/
  Schnellanlage/Import/`POST /api/leads`/Kompetenz; Label „Disqualifiziert“; Pflichtfeld `ad_id`
  prüft `vorgang.ad_id` (HV erfüllt, `lead_v2.pflichtfelder_offen`). Angebotstool/Projektierung:
  Freitext-Erfassungsstart wie WB/GW, Badges/Chips (Status-Token-Paare), Statistik, Filterlisten,
  Galerie-Ordner, DB-Ampel (WP-Rückfall), Projektierung (`projektierung_logik.SPARTEN`, Dialog,
  Steckbrief „Auftrag / Leistung“, nur ALLE-Pakete), E-Mail-Vorlage = Standard.
- **Anruf (Phase 158, B):** Rückruf/Wiedervorlage im 5-Minuten-Raster (`lead_v5.runden_5min`);
  Endziffern-Suche `lead_anrufliste.rufnummer_suchen` *(seit v35 Teil der einen Suchleiste in „Kontaktiert“,
  Phase 186)* (≥ 3 Ziffern, „endet mit“ zuerst, archivierte
  Leads markiert); „Falsche Nummer“ plant `falsche_telefonnummer` über
  `lead_mail.falsche_nummer_mail`.
- **Ausführungsort = Objekt (Phase 153, Einfügung AT-Chat, Agent AT):** Angebotstool, Projektierung
  und Mails lesen den Ausführungsort nur noch über `objekte.ausfuehrungsort` – im Angebotstool über
  `anschriften.ausfuehrungsort_fuer(session, angebot=|erfassung=|gewerk=|objekt_id=)` (Feldsatz
  name/strasse/plz/ort + objekt_id/bezeichnung/mehrere_objekte/haupt/einzeilig; Hauptobjekt =
  Kundenadresse, daher Ein-Objekt-Vorgänge byteidentisch – Kontroll-PDF
  `diagnose/v31/pdf_kontrolle_AT.pdf`), in der Projektierung über
  `projektierung.projekt_ausfuehrungsort(session, projekt, gewerk)` (Projektadresse, bei der Anlage
  aus dem Objekt übernommen, sonst Objekt des Gewerks). Umgestellt: `pdf_export`
  (`erzeuge_pdf(ausfuehrungsort=)`, Zeile „Ausführungsort“, Lieferanschrift-Vergleich,
  Verbrauchsstelle der Vollmacht, Kopf der Wirtschaftlichkeitsseiten), `lieferschein_pdf`,
  `bza_datenblatt` Abschnitt 1, `heizreport_api.projektdaten_v2`, `steckbrief_pdf`, Sub-Mail-
  Platzhalter, `ugl.lieferadresse_zeilen`, `outlook_kalender._event_daten`, Montage-Auftragsseite, *(v33: `outlook_sync._daten_projekt` über `projektierung.termin_adresse`)*
  `projektierung.terminvorschlaege`, `projekt_anlegen`/`gewerk_anlegen` (`gewerke.objekt_id`),
  Dialog „Angebot → Projekt“ (Vorbelegung), `geocoding.lead_adresse(objekt_id=)`. Regeln in
  `anschriften.py`: Empfänger = Kunde (Kundenadresse), „Ausführungsort: …“ sobald die
  Rechnungsadresse vom Objekt abweicht, Lieferanschrift fällt auf das Objekt zurück; die
  Rechnungsadresse eines MFH-Objekts ≠ Hauptobjekt liegt am Objekt (`objekt_rechnung`).
- **Erfassung übergibt das Objekt (AT):** `/leads/{id}/erfassen?objekt_id=` → `/erfassung/sparten?
  objekt_id=` (Objektwahl bei mehreren Objekten ohne Übergabe); `erfassungen.objekt_id` (ohne
  Übergabe Hauptobjekt), Objektart/Parteien aus dem Objekt → O01/O03/PO01/KO01; Angebot erbt
  `objekt_id` (`angebot_aufbau.angebot_anlegen(erfassung=)`, `version_erzeugen`, Duplizieren;
  Kopieren für anderen Kunden ohne Objekt).
- **Vorgangsakte (AT):** Erfassungen/Angebote je Objekt gruppiert (Überschrift „Objekt 2: Adresse“,
  nur bei mehreren Objekten; `vorgang_verlauf.objekt_gruppen`), Archiv-Banner „Im Lead-Management
  archiviert am … von …“ mit `POST /vorgaenge/{id}/archiv-wiederherstellen`
  (`lead_archiv.wiederherstellen`, `_speichern`-Muster, ID/LM/Admin); Notizen-Chat mit Filter „nur
  Notizen“ / „alles“ (`notizen.kontext(..., verlauf=True)` → `verlauf_alle`), Lead-Aktivitäten und
  Projekt-Verlauf nur als Anzeige – keine zweite Notizspur.
- **`app/vorgang_verlauf.py` (Phase 158, AT):** `eintraege(session, vorgang_id, quellen=("lead",
  "angebot", "projekt"), limit=None)` (zeit, quelle, art, titel, text, autor, link …; Quellen
  VorgangsNotiz über Herkunft, LeadAktivitaet mit Timeline-Titeln, KommunikationLog, ProjektVerlauf
  ohne migrierte Kommentar-Dubletten), `projekt_block(session, vorgang_id)` (Phase je Gewerk,
  nächster Montagetermin, offene Aufgaben), `objekt_gruppen(session, vorgang)`.
- **Benutzerverwaltung (156/158, AT):** Häkchen „Leadmanager“ (`benutzer.leadmanager`, Badge „LM“,
  Marker `leadmanager_dabei`), Abschnitt „Abwesenheiten“ je Benutzer (`abwesenheiten.anlegen/
  beenden/je_benutzer`, Routen `POST /benutzer/{id}/abwesenheit`, `POST /benutzer/abwesenheit/{id}/
  beenden`, Admin und Innendienst), AD-Profil nur Mo–Fr (`routers.benutzer.WOCHENTAGE`).
- **Objekt-Geocoding (AT):** Lauf `geocoding` kodiert zusätzlich aktive Objekte 2 ff. ohne `lat`
  (`_offene_objekte`, v27-Muster, Backoff, Zähler `objekte`); das Hauptobjekt übernimmt die
  Koordinaten des Vorgangs. Tests `tests/test_lead_v5_at.py` (26).
- **Tests (Phase 160):** neu `tests/test_lead_v5.py` (11), `test_lead_v5_kartei.py` (18),
  `test_lead_v5_termine.py` (15), `test_lead_v5_boards.py` (22), `test_lead_v5_at.py` (26);
  Alt-Tests mit Plan-Begründung angepasst (Demo-Ende, Testphase-Schalter `terminierung_aktiv = an`
  in Terminierungs-Tests, Kaskade 2/4 ohne Mail, Label „Disqualifiziert“, Reiter/Blöcke der Kartei,
  Endziffern ab 3, Sammelaktionen, Kandidaten-Label mit „Krankheit“, Kartei-CSS in `lead_v2.css` –
  Liste in `docs/leadmanagement-entscheidungen.md` V5.3). Rollout-Vorbereitung, Screenshots
  (`docs/design-v31/`) und Lasttest: einmal für v31 + v32, siehe „Neu in v32“.

## Neu in v32 – Vertriebler-Ansicht Mein Tag, automatische Wiedervorlage, Nächster Schritt, Bestellung angekündigt, allgemeine Suche (abgestimmt 13.10.2026)

(Plan: PLAN_V19.md, Phasen 161–165; umgesetzt am 13.10.2026 im gemeinsamen Durchlauf mit v31
(PLAN_LEAD_V5) – EIN Commit, kein Push vor Freigabe. Welle 2 mit zwei Agenten M (Mein Tag,
Wiedervorlage) und N (Nächster Schritt, Verfolgung) auf eigenen DB-Kopien; Suche, Lastmodell,
Rollout-Vorbereitung, Doku durch den Orchestrator; Berichte `diagnose/v31/M_ergebnis.md`,
`N_ergebnis.md` (lokal). Alle Datenbankänderungen additiv (`vorgaenge.verfolgung_status`,
`wiedervorlage_art`, `ablehnungsgruende.freitext_pflicht`, Indizes `ix_v32_kunden_*`, Parameter
`nachfass_werktage`/`nachfass_werktage_mfh`, Gründe-Migration); v30-Code läuft auf der
v32-Datenbank (Rückweg-Probe). Entscheidungen und Rückfragen: Gesamtübersicht des Durchlaufs
(`diagnose/v31/gesamtuebersicht.md`, lokal) und `docs/nach-dem-update-v32.md`. **Kalender:**
der Plan nennt „Fr 10.10.2026“ – der 10.10.2026 ist ein Samstag; Tests und Kontrollwerte
rechnen mit echten Wochentagen (Fr 09.10. + 3 Werktage = Mi 14.10., Bestellung Di 13.10. + 7 =
Do 22.10.; Rückfrage).)

- **Vertriebler-Ansicht „Mein Tag“ (Phase 161, Agent M, `app/mein_tag.py`, `routers/leads.py`,
  `templates/leads/mein_tag.html`, `static/mein_tag.css/.js`):** `GET /leads` ist für den Außendienst
  eine Kartenliste in einer Spalte (< 600 px Vollbreite, sonst max. 720 px) mit den Blöcken **Fällig *(überholt – seit v33 Karten nur mobil für den Außendienst mit den Blöcken Als Nächstes · Heute · Wiedervorlage · Kommende Tage, Innendienst/Admin nur die Tabelle, kein Umschalter „Karten | Tabelle“, siehe v33)*
  heute · Termine heute · Heiße Kunden · Weitere Termine**; Innendienst/Admin sehen dieselbe Seite mit
  Vertriebler-Filter und Umschalter **„Karten | Tabelle“** (Standard Karten, Wahl je Nutzer
  `benutzer_einstellungen.leads_darstellung`; Tabelle = bisheriges `leads/liste.html`) [ANNAHME
  AT-Chat]. Datenquelle **nur `vot_termine`** (Status geplant/bestaetigt/unbestaetigt – der Plan nannte
  „terminiert/unbestätigt“; erfolgt nur bei offener Sparte – v8-Chips), ohne verknüpftes Angebot am
  Vorgang; AD nur eigene (`vot_termine.ad_id`, Rückfall `vorgaenge.ad_id`/`leads.benutzer_id`).
  Termin-Karte: „Mo, 13.10.“ + „14:00 Uhr“, Kundenname, Objektadresse (`objekte.ausfuehrungsort( *(überholt – seit v33 Termin-Zeile mit Zeitstrahl, überfällige Termine als aufklappbarer Block, keine Filterkarte)*
  termin=…)`, bei mehreren Objekten mit Bezeichnung) als Google-Maps-Link, `tel:`-Link, Sparten-/
  Status-Chips, Herkunft „monday“/„Tool“ [ANNAHME], „Erfassung starten“ (mit `objekt_id`), „Akte“;
  überfällige Termine ohne Erfassung zuoberst in „Termine heute“ mit rotem Label „überfällig“ (der
  Überfällig-Banner v15 bleibt nur in der Tabelle). Filterkarte (Termin von/bis, Status, Vertriebler),
  Leerzustände `leer_zustand`, Safe-Area/`viewport-fit=cover` (`base.html`), Knöpfe ≥ 44 px, keine
  Zurück-Leiste für den AD; Außendienst mit nur einer Rolle startet bei „/“ auf `/leads` [ANNAHME]
  (`main.py`, `auth.py`), Menüpunkt und Kachel heißen für ihn „Mein Tag“. „Meine Termine“
  (Lead-Modul) verlinkt „Zur Tagesansicht“.
- **monday-Termine nachführen (`monday_sync.vot_termine_nachfuehren`, Nachlauf beider Sync-Pfade;
  `leadmanagement.monday_termine_ableiten` delegiert darauf):** geändertes VOT-Datum aktualisiert den
  vorhandenen monday-Eintrag (nicht duplizieren, `objekt_id` = Hauptobjekt), gelöschtes Datum setzt
  offene Einträge auf `abgesagt` (`grund_text` „monday: VOT-Datum entfernt“), ein wieder gesetztes
  Datum reaktiviert denselben Eintrag; erfolgt/No-Show/manuell abgesagt bei unverändertem Datum bleibt.
  `scripts/vot_abgleich.py --data <Kopie> [--anlegen] [--bericht]` meldet Leads mit VOT-Datum ohne
  Termin-Zeile und Abweichungen (Datum, Vertriebler, Objekt, offene Termine ohne Datum) und repariert
  mit `--anlegen` (nur Kopien, nie `data\`).
- **Automatische Wiedervorlage nach Angebotsversand (Phase 162, `app/nachfassen.py`):** Hook
  `nachfassen.nach_versand(session, angebot, benutzer, versandtag)` an Versand-Erkennung (`mail_sync`,
  Einzel- und Kombi-Versand – einmal je Mail), Statuswechsel „Versendet“/„Versendet (extern)“ und „Als
  versendet markieren“ (`routers/angebote`), externer Eintrag „Extern erledigt“
  (`routers/erfassungsliste`, Datum des Eintrags [ANNAHME]): setzt `vorgaenge.wiedervorlage_am` =
  Versandtag + `nachfass_werktage` (3) bzw. `nachfass_werktage_mfh` (5) bei `kunden.objektart = MFH`
  (Angebotstool-Einstellungen → Nachfassen; Werktage Mo–Fr ohne NRW-Feiertage, `app/werktage.py`),
  `wiedervorlage_benutzer_id` = AD des Vorgangs (Rückfall AD der Erfassung, Lead-Vertriebler,
  versendender Benutzer [ANNAHME]), `wiedervorlage_art = angebot_nachfassen`, Chat-Eintrag „Wiedervorlage
  automatisch gesetzt: Angebot nachfassen am TT.MM.JJJJ“ (Autor System); eine vorhandene Wiedervorlage
  wird nur überschrieben, wenn sie leer ist oder früher liegt [ANNAHME]; Verfolgungsstufe „versendet“
  über `verfolgung.nach_angebotsstatus`. Vertrag `nachfassen.wiedervorlage_setzen(session, vorgang,
  datum, benutzer_id, art)` (Datum ohne Uhrzeit) für „Nochmal anrufen“/„Bestellung“ (N).
- **Block „Fällig heute“** (`nachfassen.faellig_heute`): eigene Wiedervorlagen mit Datum ≤ heute, *(überholt – seit v33 Abschnitt „Wiedervorlage“ über `nachfassen.wiedervorlage_liste`; `faellig_heute` bleibt für die Glocke)*
  überfällige zuerst („seit TT.MM.“), Anruf-Karte mit Telefon-Link, Angebots-Kurzinfo („WP-Angebot vom
  09.10.2026, Endbetrag 32.450,00 €“ – Kundenpreis, nie EK/DB), Hot-Ampel, Verfolgungs-Chip, Dialog
  „Nächster Schritt“ (N), „Letzte Aktivitäten“ (drei Einträge aus Mail-Verlauf/Versand, Notizen-Chat,
  Signaturprotokoll), Notizfeld → `POST /leads/notiz/{vorgang_id}` (ein Eintrag im Notizen-Chat). Die
  ID-Kachel „fällig“ zählt AD-Wiedervorlagen weiterhin nicht. **Glocke:** art `nachfassen` im täglichen
  Lauf `benachrichtigungen` (07:00) – je AD „Fällig heute: n Anrufe zum Nachfassen – Mein Tag“, Link
  `/leads#faellig`, keine Mail (`MAIL_FREIE_ARTEN` = todo, nachfassen, verfolgung), nicht Teil von *(v33: `/leads#wiedervorlage`)*
  `glocke_lead_arten`. Tests `tests/test_v32_mein_tag.py` (13), `test_v32_wiedervorlage.py` (14),
  `test_v32_werktage.py` (5; Kontrollwerte nach echtem Kalender – 10.10.2026 ist ein Samstag).

- **Dialog „Nächster Schritt“, Bestellung angekündigt, Verfolgungs-Chip, Ablehnungsgründe
  (Phase 163, Agent N, `app/verfolgung.py`):** Verfolgungsstufe je Vorgang
  `vorgaenge.verfolgung_status` (`versendet | nachgefasst | bestellung_angekuendigt | angenommen |
  abgelehnt`, `STATUS_TEXTE`, Makro `verfolgung_chip(status, klein, vorgang_id)` in *(ergänzt v33: mit Zähler `versuche` → „Nachgefasst (2)“)*
  `_komponenten.html`, Klassen `.vf-<status>` in `static/verfolgung.css`, zentral in `base.html`
  eingebunden); Migration `migration_v32_verfolgung` (Marker `migration_v32_ablehnungsgruende`):
  die fünf Gründe „Zu teuer · Kein Interesse mehr · Bleibt bei Öl/Gas · Woanders unterschrieben ·
  Sonstiges (Pflicht-Freitext, Spalte `ablehnungsgruende.freitext_pflicht`)“ = Lead-Gründe
  `verloren` (zwei Pflegeorte, gleiche Texte, Schreibweise der Excel [ANNAHME]), andere Gründe
  deaktiviert [ANNAHME], „90 Tage Ablauf“ bleibt; Stufe aus dem Angebotsstatus gefüllt
  (`ableiten`: Angenommen > offene Versendete > Abgelehnte). Route `POST /vorgaenge/{id}/
  naechster-schritt` (`def`, `_speichern`-Muster, JSON bei Accept, sonst Redirect `zurueck`; AD
  nur eigener Vorgang 403): `abgelehnt` + `grund_id` (+ `freitext` bei Pflicht, sonst 400) →
  `kern.lead_verloren` (Lead-Phase Verloren, Angebote über `lead_boards.angebote_ablehnen`,
  monday), ohne Lead-Phase nur Versendete (v8-Weg); Wiedervorlage leer, Ampel kalt, Stufe
  `abgelehnt`, System-Notiz „Kunde hat abgelehnt: <Grund>“; `bestellung` →
  `bestellung_angekuendigt`, Ampel heiß, Wiedervorlage heute + 7 Werktage [ANNAHME]
  (`wiedervorlage_art = bestellung_angekuendigt`), Glocke art `verfolgung` an den Innendienst
  ohne Mail; `nochmal` + `wann` 3wt|datum → Wiedervorlage ohne Uhrzeit (`nochmal_anrufen`), Stufe
  `nachgefasst`, Notiz „Nochmal anrufen am TT.MM.JJJJ“; das Notizfeld wird als Chat-Eintrag VOR
  der System-Notiz gespeichert; `schritt=rueckgaengig` + Token (10 s Link, Schnappschuss 10 min)
  [ANNAHME]. Partial `vorgaenge/_naechster_schritt.html` (+ `static/verfolgung.js`, Events
  `ns:gespeichert`/`ns:rueckgaengig`, Notiz über `data-ns-notiz`) in der Vorgangsakte
  (Verfolgungs-Block, ID und AD) und in „Mein Tag“ (M). Chip in Akte-Kopfkarte, „Meine Angebote“
  (Liste + Detail) und Angebotsliste (Spalte „Verfolgung“, Filter `?verfolgung=<stufe>` über
  `verfolgung.filter_anwenden`); `heisse_vorgaenge(session, benutzer_id)` (Heiße Kunden), *(Block „Heiße Kunden“ entfällt seit v33 – heiße Vorgänge laufen im Abschnitt „Wiedervorlage“ mit Chip „Hoch“)*
  ID-Kachel „Bestellung angekündigt“ (`bestellung_angekuendigt_anzahl`, Klick = Angebotsliste mit
  Filter). „Angenommen“ setzen Signaturweg (`routers/signatur.py`) und AD-Statuswechsel über
  `nach_angebotsstatus`, „abgelehnt“ ID-Dialog/Route; Parametrierung → Angebotstool-Einstellungen:
  Gründe mit Nr./↑↓/Häkchen „Freitext Pflicht“, Abschnitt „Nachfassen nach Angebotsversand“ *(ergänzt v33: auch `inaktiv_tage` 14 / `inaktiv_tage_mfh` 20 und die Liste „Einwände beim Nachfassen“)*
  (`nachfass_werktage` 3 / `nachfass_werktage_mfh` 5, Lead-Parameter). Tests
  `tests/test_v32_naechster_schritt.py` (18); `tests/abnahme.py` v8-Block nutzt den ersten
  aktiven Grund.
- **Allgemeine Kundensuche (Phase 164, Orchestrator, `app/suche.py`, `app/routers/suche.py`):**
  Suchfeld in der Kopfzeile von `base.html` zwischen Logo und Glocke/Menü (Platzhalter „Kunde
  suchen …“, Admin/Innendienst/Lead-Management/Außendienst; nicht auf Login/PIN-Wechsel, im
  Erfassungsbogen `/erfassung/{id}/…` und eingebettet `einbett=1`; unter 600 px Lupe, die das Feld
  in voller Breite ausklappt). `GET /suche.json?q=` (ab 2 Zeichen, höchstens 8 Treffer): Kunden
  nach Vorname, Nachname, „Vorname Nachname“, Firma und Ort (Wortanfänge, Groß-/Kleinschreibung
  und Umlaute egal; SQL-Vorfilter = Bereichsvergleich auf den Anfangsbuchstaben – nutzt die
  Indizes `ix_v32_kunden_nachname`/`ix_v32_kunden_ort` aus `db._INDIZES` – plus LIKE, exakte
  Prüfung in Python) sowie Telefon-Endziffern ab 4 Ziffern [ANNAHME] (Normalisierung
  `leadmanagement.telefon_normalisieren`, „endet mit“ vor „enthält“); Außendienst nur Kunden mit
  eigenem Vorgang (`vorgaenge.ad_id`), Montage und Projektierung 403 [ANNAHME: Plan nennt nur
  Montage]. Treffer: Name, PLZ/Ort, Sparten-Badges, Verfolgungs-Chip des jüngsten Vorgangs
  (`verfolgung.status_text`), Link = Vorgangsakte des jüngsten offenen Vorgangs, sonst
  Kundenakte (`/kunden/{id}/bearbeiten`; Außendienst: jüngster eigener Vorgang [ANNAHME]);
  keine EK/DB-Felder. Bedienung (`static/suche.js`, ES5, DOM-Aufbau ohne innerHTML): Debounce
  200 ms, Pfeiltasten + Enter öffnen den markierten Treffer, Escape schließt, Enter ohne Auswahl
  → Trefferseite `GET /suche?q=` (`templates/suche.html`, Tabelle, bis 200 Treffer, Zurück-Leiste
  aus `base.html`). `/suche` steht in allen Rollen-Pfadlisten (`auth.py`), damit die Route selbst
  entscheidet. Styles `static/suche.css` (nur Tokens: Kopfzeile `--text-invers`, Liste
  `--flaeche-karte`). `scripts/index_pruefung.py` prüft `/suche?q=Mü`, `/suche.json?q=…`;
  Lasttest-Gruppe „Kundensuche“ (Zielwert 300 ms) im AD-Szenario. Messung: Entwicklungs-Kopie
  (143 Kunden) Median 17 ms; Server-Kopie siehe Gesamtübersicht. Tests `tests/test_v32_suche.py`
  (12: Mül/Peter M/Krefeld/4711, AD nur eigene Kunden, Montage/Projektierung 403, keine EK/DB,
  Antwortzeit, Suchfeld je Seite, Trefferseite).
- **Lastmodell (Phase 165, `scripts/lasttest.py`):** 35 aktive von 50 Nutzern = 15 Außendienst
  (Mein Tag `/leads`, Kundensuche `/suche.json`, Erfassung), 12 Lead-/Innendienst-Nutzer im
  Lead-Szenario (Hauptboard, Kartei, Terminvorschläge; ohne Hauptrolle leadmanagement übernehmen
  Innendienst-Personen – Modul seit v31 für alle Rollen frei), 5 Innendienst, 3 Projektierung/
  Montage; Messgruppe „Kundensuche“ ≤ 300 ms; Kundennamen-Pool `kunden_namen`.
- **Tests, Rollout, Doku (Phase 165):** neue Tests `tests/test_v32_mein_tag.py`,
  `test_v32_wiedervorlage.py`, `test_v32_werktage.py`, `test_v32_naechster_schritt.py`,
  `test_v32_suche.py`; Alt-Tests mit Begründung angepasst (siehe Gesamtübersicht). Rollout-
  Vorbereitung einmal für v31 + v32 (`diagnose/v31/abschluss_tests.sh`: Server-Kopie, `migrate.py`
  ×2, Testbenutzer + HV, `scripts/vot_abgleich.py`, Rückweg-Probe v30-Code gegen die
  v32-Datenbank, Gesamtsuite, `tests/abnahme.py`, Voll-Crawl sechs Rollen + HV je hell/dunkel,
  Smoke, Suche-Messung, Lasttest `normal`); Screenshots `docs/design-v31/`, `docs/design-v32/`
  (hell/dunkel, Handy 390 × 844 und Desktop, anonymisierte Kopie); `config.VERSION = "v32"`;
  `docs/nach-dem-update-v31.md`, `docs/nach-dem-update-v32.md`, `docs/updates.md`,
  `docs/betrieb.md` („Ergänzungen v31 + v32“), `docs/design-system.md`.

## Neu in v33 – Outlook je Mitarbeiter, Graph als Anwendung, zentraler Kalender, Rollen-Varianten, Service-Einsätze, Auto-Phase, Rabatt 0 %, Mein Tag mobil, Tabellen-Layout, Nachfassen (abgestimmt 14.10.2026)

(Plan: PLAN_V20.md, Phasen 166–177; Protokoll Claudia Castro vom 14.10.2026 in
`docs/PROTOKOLL-2026-10-14-Angebotstool.md` als Phasen 173–176 eingearbeitet; Design-Entwurf
`docs/design-v33/vorlage/` gibt Aufbau und Verhalten vor, nicht die Farben. Umgesetzt am 14.10.2026 in EINEM
Durchlauf: Fundament durch den Orchestrator (Rollen-Modell, Tabellen/Spalten, Graph-Kern, Verträge), Welle 1
mit sechs Agenten G (Graph), R (Rollen), S (Service/Auto-Phase), A (Rabatt/Schreibtransaktionen), O
(Outlook), K (Kalender), Welle 2 mit M (Mein Tag/Leads), T (Tabellen), N (Nachfassen) auf eigenen
DB-Kopien; Lastmodell, Rollout-Vorbereitung und Doku durch den Orchestrator; Berichte
`diagnose/v33/<X>_ergebnis.md` (lokal). EIN Commit, kein Push vor Freigabe. Alle Datenbankänderungen
additiv – v32-Code läuft auf der v33-Datenbank (Rückweg-Probe im Rollout-Skript).)

**Leitplanken ab v33 (zusätzlich zu v27/v30):**
- **Rollen:** Rechte prüfen ausschließlich `Benutzer.basisrolle` / `basisrollen` / `hat_rolle` /
  `hat_kennzeichen("service"|"handelsvertreter")` / `gewerk` (`app/rollen.py`); DB-Filter über
  `rollen.filter_basis/filter_basen/keys_fuer_basis`. Nie mehr `rolle == "montage"` – `benutzer.rolle`
  trägt den Varianten-Key (`montage_heizung`, `service_elektro`, `handelsvertreter`, …). Umgestellte Stellen:
  `diagnose/v33/basisrolle_stellen.md` (179 Vergleiche + 5 SQL-Abfragen im Fundament, Ergänzungen in
  `R_ergebnis.md`).
- **Schreibtransaktionen:** nur Schreibsitzungen (`get_session` bei POST/PUT/PATCH/DELETE, `db.kurz()`,
  `db.schreibsitzung()`) eröffnen mit `BEGIN IMMEDIATE`; alle anderen Sitzungen bleiben im Legacy-Modus des
  sqlite3-Treibers. Ein pauschales explizites BEGIN für alle Sitzungen ist verboten (BUSY_SNAPSHOT – 29
  Alt-Tests rot im Durchlauf). **Der Request-Body ist Netz-I/O:** eine Route mit Datei-Upload liest das
  Formular (`anfrage.formular(request)`) VOR dem ersten Datenbankzugriff oder ruft davor
  `verbindung_freigeben(session)` auf – sonst hält die Schreibsitzung die SQLite-Schreibsperre während der
  gesamten Übertragung (Handy-Upload über LTE/VPN: Sekunden bis Minuten; Befund 15.10.2026, sieben Routen
  umgestellt, Wächter `tests/test_v33_fundament.py::UploadRoutenOhneSchreibsperre`). **Rein lesende
  Kurz-Sitzungen** (Kataloge, Einstellungen, Template-Globals, /health, Lesephasen der Läufe) nutzen
  `db.kurz(schreibend=False)` – eine `kurz()`-Sitzung innerhalb einer Anfrage oder eines Laufs, der selbst
  schreibt, liefe sonst gegen die eigene Sperre. Tests, die über ihre Sitzung schreiben und danach eine
  POST-Anfrage oder einen Lauf auslösen, committen (oder verwerfen) vorher – der Lauf bzw. die Anfrage
  eröffnet sofort eine Schreibtransaktion.
- **Graph:** Modus `anwendung` nur über den grünen Verbindungstest (`/versand`), bis dahin `delegiert`
  (heutiger Betrieb); kein Geheimnis in Code, Doku oder Tests; alle Graph-Aufrufe über
  `graph_versand.basis_pfad(postfach)`; 403 = „nicht in der Zugriffsgruppe“ (einmal je Postfach und Stunde
  im Fehlerprotokoll).
- **Outlook:** Schreibvorgänge nur über die Auftrags-Warteschlange `outlook_auftraege` und den Lauf
  `outlook-sync` (nie Graph in einer Anfrage); fremde Outlook-Einträge (TAIFUN, privat) werden nie geändert;
  Belegtzeiten aus dem Cache `outlook_belegt` (Lauf `outlook-ruecklesen`).
- **Kalender:** `GET /kalender/daten.json` ist eine reine Leseanfrage (kein Netz, kein Betreff fremder
  Einträge).
- Weiterhin: keine offene Datenbanksitzung während Netz-I/O (Wächter `tests/test_v27_sitzungen.py`),
  def-Routen, jeder Hintergrundlauf über `scheduler.registrieren`, nur Tokens Hell/Dunkel (Token-Wächter),
  `tojson` in on*-Attributen nur mit `forceescape`, Zurück-Leiste aus `base.html`, `docs/betrieb.md`
  fortschreiben.

- **Graph als Anwendung (Phase 166, `app/graph_versand.py`, G):** zwei Betriebsmodi – `anwendung` (Client-
  Credentials-Token der App-Registrierung, Anwendungsberechtigungen `Mail.Send`/`Mail.ReadWrite`/
  `Calendars.ReadWrite`, Exchange-Zugriffsgruppe `friondo-tool-zugriff@` per `New-ApplicationAccessPolicy
  -AccessRight RestrictAccess`) und `delegiert` (Rückfallebene: Device-Code-Anmeldung einer Person, `/me/…` +
  „Senden als“, unverändert). `.env`: `GRAPH_CLIENT_SECRET` (oder `GRAPH_ZERTIFIKAT_PFAD` PEM +
  `GRAPH_ZERTIFIKAT_THUMBPRINT` [ANNAHME: beide Wege, Secret reicht zum Start]), `GRAPH_GEHEIMNIS_ABLAUF`
  (JJJJ-MM-TT). Einstellung `graph_modus` (Migration `delegiert`); `anwendung` erst, wenn das Geheimnis
  gesetzt ist UND der Verbindungstest grün war (`graph_versand.modus()`, `modus_setzen`, Cache im Prozess).
  `_token()` liefert je Modus das Token (`_token_anwendung`: MSAL ConfidentialClient, Scope `/.default`,
  Cache, Erneuerung 5 min vor Ablauf, Fehlertext `token_fehler()`); `basis_pfad(postfach)` →
  `/users/<postfach>` (anwendung: leer = Funktionspostfach `mail_absender`), `versand_pfad(absender)` →
  (`/users/<absender>`, kein `from`) bzw. (`/me`, `from`); alle Sende-/Abruf-/Entwurfsfunktionen
  (`text_mail_senden`, `mail_mit_anhaengen_senden`, `entwurf_erstellen`, `info_mail_senden`,
  `postfach_ungelesen`/`nachricht_*`, `mail_sync._basis`, `lead_mail._graph_senden`/`testmail_senden`,
  `lead_parser` über `basis_pfad`) nutzen sie – Versand `sendMail` direkt an angebot@/termin@/projektierung@,
  kein „Senden als“, **Entwürfe von „Versand vorbereiten“ und Kombi-Versand liegen im Modus anwendung in
  angebot@ → Entwürfe** (Signatur des ID-Benutzers im HTML, CC/BCC wie bisher; Exchange
  `MessageCopyForSentAsEnabled` für die Versand-Erkennung). HTTP 403 → `GraphZugriffVerweigert` +
  Fehlerprotokoll „Postfach <x> ist nicht in der Zugriffsgruppe Friondo-Tool-Zugriff“ (einmal je Postfach und
  Stunde), erfolgreiche Aufrufe je Postfach in `letzte_erfolge()`. Neu `mail_senden_als(postfach, empfaenger,
  betreff, html, anhaenge=, cc=, text_alternativ=) -> (ok, fehler, conversation_id)` (Versand aus einem
  beliebigen Postfach der Gruppe, Nachfass-Mail Phase 176; im Modus delegiert nur eigenes Konto).
  **Verbindungs-Seite `/versand`** (`routers/versand.py`, `versand/status.html`): Modus mit Grund, Mandant
  maskiert, Geheimnis-Ablauf, letzter Verbindungstest, Liste aller Postfächer, die das Tool braucht
  (`benoetigte_postfaecher`: Funktionspostfächer aus Einstellungen/Parametern inkl. Team-/Testpostfächer +
  aktive Benutzer mit E-Mail der Basisrollen Außendienst/Projektierung/Montage/Innendienst, HV ohne
  Friondo-Postfach ausgenommen, `AdProfil.kalender_postfach` berücksichtigt) mit letztem Erfolg/403 und
  Kopierlisten, Knopf „Verbindung testen“ (`POST /versand/test` → `verbindungstest(session)`: je
  Funktionspostfach `GET /users/<pf>/mailFolders/inbox?$select=id`, je Mitarbeiter
  `GET /users/<upn>/calendar?$select=id`, 403 → „nicht in der Zugriffsgruppe“, 404 → „Postfach unbekannt“,
  Token-Fehler → „Anmeldung der Anwendung fehlgeschlagen: …“; alle Funktionspostfächer grün → `graph_modus =
  anwendung`, sonst `delegiert` [eigene Annahme G: rote Mitarbeiter-Postfächer schalten nicht zurück, Rückfrage];
  Ergebnis in Einstellung `graph_letzter_test`), Vertrag O `outlook_sync.postfaecher_ohne_zugriff(session)`,
  im Modus delegiert weiter „Mit Microsoft anmelden“/„Abmelden“. `angemeldeter_benutzer()` liefert im Modus
  anwendung `KONTO_ANWENDUNG`; die Versand-Routen (`routers/angebote.py`, `routers/vorgaenge.py`) prüfen
  `graph_versand.verbunden(session)` und melden `nicht_verbunden_text(session)`. Go-live-Checkliste: 12. Punkt
  „Graph als Anwendung verbunden“ (`golive.graph_punkt`); `/health`: Felder `graph_modus`,
  `graph_geheimnis_tage`, `warn` „Graph-Geheimnis läuft in n Tagen ab“ (≤ 30); Betriebs-Seite Kachel
  „Graph-Modus“. Doku `docs/graph-einrichtung.md` komplett neu (Entra, Exchange, Verbindungstest,
  Geheimnis-Wechsel, neue Mitarbeiter). Tests `tests/test_v33_graph.py` (28, alles gemockt).
- **Rollen als Varianten (Phase 167, `app/rollen.py`, Parametrierung → Rollen `/parametrierung/rollen`, nur
  Admin, R):** Tabelle `rollen` (Basisrollen als Systemzeilen, Varianten Montage Heizung/Elektro, Service
  Heizung/Elektro, Handelsvertreter; Kennzeichen Gewerk/Service/HV). Rollen-Seite: Anlegen (Name, Basisrolle,
  Gewerk, Service, HV; Key aus dem Namen), Umbenennen, Deaktivieren nur ohne aktive Benutzer (Meldung mit
  Namen), Systemrollen gesperrt (`rollen.anlegen/umbenennen/deaktivieren`, Cache `rollen.cache_leeren`).
  Benutzerverwaltung: Dropdown/Zusatzrollen/Filter aus dem Katalog (`rollen.katalog_liste`, Basisrolle filtert
  mit Varianten, `data-basis` steuert das Team-Dropdown bei jeder Montage-Variante), Kennzeichen-Badges
  (`rollen.benutzer_badges`), `ROLLEN_NAMEN` nur noch Alias über `rollen.namen()`. Handelsvertreter = Rolle:
  `rollen.hv_spiegeln` (Rolle → `ad_profile.terminiert_selbst`) und `rollen.hv_rolle_setzen` (AD-Profil-Häkchen
  → Rolle); `lead_v2.ist_handelsvertreter/handelsvertreter_ids/handelsvertreter_liste`, `lead_dropdowns._hv_ids`,
  Kartei-Dropdown lesen Rollen-Kennzeichen ∪ Profil-Flag. Migration `rollen.migration_v33_rollen` (idempotent):
  Systemzeilen + Varianten, AD-Profile mit `terminiert_selbst` → Rolle `handelsvertreter` (Dev-DB: Rene
  Golaschewski, Simon O Grady), Teams-Gewerk (Elektro-Teams an Gewerken → elektro, übrige → heizung
  [ANNAHME]), überflüssige Zusatzrollen bereinigt. CSV-Import (`benutzer_import.rolle_zuordnen`) akzeptiert Keys
  und Namen aller aktiven Rollen. Teams tragen `teams.gewerk`. Login-Ziel (`anmeldung.STARTSEITEN`) und
  Cookie-Dauer über die Basisrolle; Pfadtabellen in `auth.py` prüfen die Basisrolle – neu `/kalender` in
  `AUSSENDIENST_PFADE`, `/vorgaenge` (lesend) in `PROJEKTIERUNG_PFADE`. Montage-Backend `/montage` zeigt einem
  Benutzer der Variante nur die Termine seines Gewerks (S). Tests `tests/test_v33_rollen.py` (22),
  `tests/test_v33_fundament.py` (12).
- **Service-Einsätze (Phase 168, S):** Terminart `service` im gemeinsamen Termin-Dialog
  (`projektierung.TERMIN_ARTEN["service"]`, Gewerk heizung | elektro in `service_gewerk`, Anlass
  `SERVICE_ANLAESSE` Wartung · Störung · Nacharbeit · Sonstiges [ANNAHME], Uhrzeit im 15-Minuten-Takt
  Pflicht, Dauer → `ende` (Standard 2 h), Team optional als Vorlage, Techniker in der Besetzung –
  Service-Varianten des Gewerks zuerst, andere grau); planbar am Projekt-Gewerk und **am Vorgang ohne Projekt**
  (`projekt_id = 0` + `vorgang_id`; Vorgangsakte → Block „Termine“ → „Service-Einsatz planen“, Route
  `POST /projektierung/vorgang/{id}/service-termin`, ID/Admin/Projektierung). Service hat keine Phase,
  erledigt keine Aufgabe, setzt keine Zuweisung; ohne Projekt keinen Projektverlauf – die Spur ist der
  Notizen-Chat. `kern.termin_speichern(session, gewerk | None, daten, …)`, `termin_loeschen`,
  `termin_vorgang/termin_kunde/termin_adresse` (Ausführungsort v31 über Projekt bzw. Hauptobjekt/
  Kundenadresse). **Service-Backend** `/montage`: Service Heizung/Elektro sehen NUR Service-Einsätze ihres
  Gewerks (`routers/montage._sicht`/`_termin_passt`), Montage Heizung Montage (WP) + Sub, Montage Elektro
  Elektro-Montagen, Basisrolle montage alles außer Service; Seite `montage/service_einsatz.html` (Kunde,
  Ausführungsort, Steckbrief, Notizen lesen, Galerie, „Einsatz gestartet/beendet“ → `service_status` geplant →
  gestartet → beendet mit `gestartet_am/beendet_am`, Verlauf + Chat-Notiz), Formular **Servicebericht**
  (Blatt „Formulare“ der Logik-Excel, 9 Felder `sb_*` [ANNAHME, Andreas liest gegen], neuer Feldtyp `zeit`;
  Datensatz je Termin – `montage_formulare.termin_id` (Spalte, Übergangsschlüssel `_termin_id` per
  `migration_v33_termin_id`); PDF `Servicebericht_<Nr>_<Datum>.pdf` im Galerie-Ordner „Service“, Chat-Eintrag,
  Einsatz beendet). Akten zeigen Service mit Badge „Service“ + Anlass · Gewerk · Status und dem Outlook-Stand
  (Makro `_outlook_status.html`); Statistik `/projektierung/statistik` (Service-Einsätze je Monat) [ANNAHME].
  Verträge für `/kalender`: `projektierung.termine_fuer_personen(session, ids, von, bis)` und
  `termin_verschieben(session, termin, beginn, ende, benutzer) -> (ok, meldung, konflikte)` (Kalender-Drag v15 =
  `termin_kalender_drag`). `migration_v33_service`: Parameter `phase_auto`, Status-Backfill. Tests
  `tests/test_v33_service.py` (17).
- **Zentraler Planungskalender `/kalender` (Phase 169, `app/kalender_zentral.py`, `routers/kalender_zentral.py`,
  `templates/kalender/zentral.html`, `static/kalender_zentral.js/.css`, K):** eine Zeile je Mitarbeiter,
  Zeitachse waagerecht im 15-Minuten-Raster zwischen `kalender_tagesbeginn`/`kalender_tagesende`
  (Lead-Parameter, 07:00–18:00), Ansichten Tag | Woche (Mo–Fr, Sa/So einblendbar) | Monat (Tageskästchen mit
  Punkten), Gruppen Außendienst · Handelsvertreter · Projektierung · Montage Heizung · Montage Elektro ·
  Service Heizung · Service Elektro · Innendienst aus Basisrolle/Kennzeichen/Gewerk
  (`kalender_zentral.gruppe_von`; montage ohne Gewerk → Heizung [ANNAHME], leadmanagement → Innendienst),
  aufklappbar mit Zählern, Suche nach Name, Einstieg `?gruppe=projektierung` (Menü/Team-Kalender) ·
  `?gruppe=vertrieb` (Lead-Icon-Leiste „Mehr …“) · ohne Parameter nach Basisrolle; Auswahl je Nutzer und
  Einstieg in `benutzer_einstellungen` Key `kalender_gruppen`. Daten nachgelagert über
  `GET /kalender/daten.json?von&bis&personen&ansicht` (je Quelle eine Abfrage: `vot_termine` offene Status
  inkl. Vorab-Gespräche/Sperrzeiten, Projekt-/Service-Termine über `projektierung.termine_fuer_personen`,
  Abwesenheiten, Outlook-Belegt aus `outlook_belegt` – nie Graph im Request, nie ein Betreff; Messung 60
  Personen × 1 Woche ≈ 40 ms). Klick öffnet Kartei `?tab=termin`, Projektakte `#termine` bzw. Vorgangsakte;
  Drag → `POST /kalender/verschieben` (VOT = Umbuchung über `lead_termin.termin_anlegen`, Vorab direkt,
  Projekt/Service über `projektierung.termin_verschieben`; Konflikte als Liste mit Bestätigung; Outlook über
  die Hooks der Phase 170; Rechte wie im Modul, monday/Sperrzeiten nie, Testphase sperrt); Doppelklick auf
  freie Fläche → Such-Dialog Kunde/Projekt (`GET /kalender/suche.json`) → Dialog des Moduls mit
  `?termin_neu=…&beginn=&uhrzeit=&person=` (Projektakte, Vorgangsakte, Terminassistent `?beginn=`).
  Montage/Service-Benutzer sehen nur sich und ihr Team (lesend, unter 600 px Tagesansicht; Knopf „Kalender“
  im Montage-Backend); Außendienst/HV die eigene Zeile. Menü „Kalender“ (Admin/Innendienst/Projektierung/
  Leadmanagement), `projektierung/kalender.html` → „Mitarbeiter-Kalender“, `GET /lead-management/kalender`
  (v12) leitet auf `/kalender?gruppe=vertrieb&ansicht=woche&datum=…&person=…` um [ANNAHME] (`?alt=1`/
  `?meldung=` zeigen die alte Ansicht; Lead-Links zeigen auf `/kalender?gruppe=vertrieb`). Farben nur über
  Tokens (`--kz-f` je Art), CSS-Schraffur für Belegt/Sperrzeit. Tests `tests/test_v33_kalender.py` (17).
- **Outlook-Sync je Mitarbeiter (Phase 170, `app/outlook_sync.py`, O):** Jeder Tool-Termin steht als Kopie im
  persönlichen Outlook-Kalender jeder eingeteilten Person (TAIFUN liest von dort): VOT → Vertriebler (`ad_id`;
  Demo-Termine ins Testpostfach `kalender_testpostfach`; Schalter `kalender_sync` gilt weiter für VOT und den
  Belegt-Abgleich), Montage/Elektro/Sub/Service → jede Person der Besetzung, Feinplanung/Abnahme/Sonstiges →
  Person, Team-Kalender nur zusätzlich bei `teams.outlook_adresse` [ANNAHME optional], Abwesenheiten/Sperrzeiten
  nicht. Postfach = `AdProfil.kalender_postfach`, sonst `Benutzer.email`; Handelsvertreter nur mit
  Friondo-Postfach, sonst Hinweis **„HV ohne Postfach“**. **Kein Graph-Aufruf im Request:**
  `kalender.termin_schreiben/termin_aendern/termin_loeschen` und `outlook_kalender.event_senden/event_loeschen`
  (Signaturen unverändert, `RELEVANTE_TYPEN` + sub/sonstige/service) reihen über
  `outlook_sync.auftrag_einreihen(session, aktion, termin_art, termin_id, benutzer_ids=None)` Aufträge in
  `outlook_auftraege` ein (anlegen | aendern | loeschen; Besetzungswechsel = loeschen für entfernte, anlegen für
  neue Personen); Wahrheit ist `outlook_ereignisse` (termin_art vot|projekt, termin_id, benutzer_id, postfach,
  event_id, stand ausstehend|ok|fehler|geloescht|in_outlook_geloescht|leer), die alten Felder `outlook_event_id`
  spiegeln die erste Kopie. Lauf **`outlook-sync`** (60 s, Start +60 s, aktiv nur mit Graph): Block ≤ 50 in
  `db.kurz()` lesen → Graph `POST/PATCH/DELETE /users/<upn>/events` (`graph_versand.basis_pfad`, Modus delegiert
  dieselben Pfade) → kurze Sitzung je Auftrag; 3 Versuche dann `fehler` + Fehlerprotokoll „Outlook-Sync“; HTTP 403
  sofort `fehler` („nicht in der Zugriffsgruppe“) mit stündlicher Wiederholung bis 7 Tage. Ereignis: Betreff
  **`<Art>: <Kunde>, <PLZ Ort> (<Nummer>)`** [ANNAHME bis TAIFUN-Abgleich], Service `Service <Anlass>: …`, Body
  (Kunde, Adresse, Besetzung, Steckbrief, Link ins Tool), `categories ["Friondo-Tool"]`,
  `singleValueExtendedProperties friendoTerminId` = `<art>:<termin_id>:<benutzer_id>` (feste GUID), `showAs busy`,
  ganztägig als `isAllDay`. Lauf **`outlook-ruecklesen`** (300 s, Start +330 s): `calendarView` je Person mit
  Terminen in den nächsten 8 Wochen (`$expand` des Kennzeichens, seitenweise) – verschobene Tool-Kopien ziehen den
  Termin nach (erste Änderung gewinnt, übrige Kopien per Auftrag `aendern`, Verlauf/Aktivität „Termin aus Outlook
  übernommen von <Name>“, keine Kundenmail), fehlende Kopien → Stand `in_outlook_geloescht`, Termin markiert
  (VOT `grund_text` + Aktivität, Projekt `outlook_fehler = "in Outlook gelöscht"` + Verlauf) und Glocke an
  Projektleiter/Ersteller (`kommentar`) bzw. Leadmanager (`terminaenderung`), nie stilles Löschen; fremde Einträge
  nur als Belegtzeit im Cache **`outlook_belegt`** (`outlook_sync.belegt(session, benutzer_ids, von, bis)` für
  `/kalender`; `kalender.frei_belegt` liest denselben Cache, `lead_termin` nutzt `outlook_sync.belegt_fuer` – nie
  Graph im Request). `outlook_kalender.ruecklesen()` ruft den Lauf (Rückgabe int, mail-sync-Teilschritt).
  Anzeige: Makro `templates/_outlook_status.html` `outlook_status(stand)` über `outlook_sync.status_fuer(session,
  termin_art, termin_id) -> {stand, text, kopien}` / `status_map` / Template-Global `outlook_status_map` –
  Terminassistent (Block „Outlook“, HV-Hinweis an vorgemerkten Terminen), Meine Termine, Projektierung → Termine,
  Projekt-/Vorgangsakte (S), Deals-Board-Fußzeile (`outlook_zusammenfassung`). Verbindungs-Seite:
  `outlook_sync.postfaecher_ohne_zugriff(session)` (Aufträge mit 403-Text + Rücklese-403 + graph_versand-Liste).
  Migration `outlook_sync.migration_v33_outlook` spiegelt den Altbestand (`outlook_event_id`) als Ereignisse
  (VOT → Person, Projekt → Team-Kopie `benutzer_id 0`), idempotent. TAIFUN-Vorab-Abgleich nur vorbereitet
  (`docs/outlook-sync.md` Abschnitt 1, `scripts/outlook_abgleich.py` – nur lesend); Entscheidung Andreas offen.
  Pool-Invariante mit 16 Läufen: 64 + 16 + 5 = 85 ≤ 90. Tests `tests/test_v33_outlook.py` (21).
- **Automatischer Phasenwechsel (Phase 171, S):** Parameter `phase_auto` (Standard an, Projektierung-
  Einstellungen „Board & Wächter“, protokolliert) + Häkchen je Gewerk (`gewerke.phase_auto`,
  `POST …/gewerk/{id}/phase-auto`). `projektierung.auto_weiterschalten` läuft nach Aufgaben-Erledigung/entfällt
  (Routen, `aufgabe_auswahl_setzen`, `aufgabe_entfaellt`, Galerie-Häkchen), Formular-Abschluss
  (`montage_formulare.abschliessen`, `fp_abschliessen`), Termin/Besetzung (`termin_speichern`) und
  Steckbrief-/Förder-Nachzug: alle Pflichtaufgaben der aktuellen Phase erledigt/entfällt →
  `phase_wechseln(…, "automatisch – alle Pflichtaufgaben erledigt", automatisch=True)` (Verlauf, Glocke
  [ANNAHME]). Nur Auftragseingang → Feinplanung VOT → Planung → Montagevorbereitung und Abnahme → Freigabe;
  Montage/Abnahme sind Ereignis-Phasen, abgeschlossen nur über Rechnung freigeben; nie mit offenen
  Wächter-Punkten. Manueller Rückschritt → `gewerke.phase_auto_pause` (Hinweis im Dialog „Phase ändern“),
  endet beim Verlassen der Phase oder beim Neu-Setzen des Häkchens. Tests `tests/test_v33_auto_phase.py` (10).
- **Rabatt bei 0 % USt + Schreibtransaktionen (Phase 172, A):** Der Gesamtrabatt gilt bei jedem Steuersatz
  auf den Gesamtbetrag nach USt (bei 0 % nach § 12 Abs. 3 UStG ist das der Nettobetrag): Netto → USt →
  Gesamt-Betrag → − Rabatt → = Endbetrag; der Deckungsbeitrag sinkt um Rabatt ÷ (1 + USt-Satz).
  `Angebot.summen()` liefert zusätzlich `rabatt_netto` und `netto_nach_rabatt`. **Ursache des gemeldeten
  Fehlers:** rechnerisch griff der Rabatt bei 0 % schon vorher (Editor, PDF, {endbetrag}, monday, Statistik,
  DB korrekt); er fehlte nur in der Angebotsliste (Spalte „Brutto“ = Gesamt-Betrag vor Rabatt – jetzt
  „Endbetrag“) und in den Beschriftungen („Brutto-Gesamtbetrag“, „€ (brutto)“). Kontrollwerte: PV 20.000,00 €
  netto, 0 %, Rabatt 5 % → 19.000,00 €, DB −1.000,00 €; 500 € → 19.500,00 €. Tests `tests/test_v33_rabatt.py`
  (21). **Schreibtransaktionen (v30-Nachtrag 21/22):** Sitzungen schreibender Anfragen (`get_session` bei
  POST/PUT/PATCH/DELETE – FastAPI reicht den Request herein, Rückfall `anfrage.METHODE` aus der
  RollenMiddleware), `db.kurz()` (Standard `schreibend=True`) und `db.schreibsitzung()` eröffnen ihre
  Transaktion mit `BEGIN IMMEDIATE` (SQLAlchemy-begin-Event in `app/db.py`, Treiber je Transaktion auf
  `isolation_level=None`): die Schreibsperre liegt vor dem ersten Lesen, ein weiterer Schreiber wartet den
  busy_timeout (5 s) ab, bei „database is locked“ wird einmal nach 0,7 s wiederholt (`_speichern` wiederholt
  dann nicht erneut – Budget ≈ 10,7 s). Alle übrigen Sitzungen bleiben im Legacy-Modus (SELECT ohne
  Schnappschuss). Zähler `db.TRANSAKTIONEN` (`/health`-Feld `transaktionen`), Schalter
  `db.SCHREIBTRANSAKTION_SOFORT` (nur Messung). `angebot_aufbau.angebot_anlegen(commit=False)` in
  `duplizieren`/`kopieren` (SAVEPOINT bei Nummernkollision), `rabatt_setzen` über `_speichern`, `wal_pflege`
  über eine rohe Pool-Verbindung. Dazu (Orchestrator): `routing.fahrzeit` schreibt den Luftlinien-Cache-
  Eintrag sofort fest, `geocoding._zaehler` fängt den IntegrityError des Tageszählers ab. Messung:
  Schreibsturm 20 parallele POST → 0 locked; Lesen → fremder Commit → Schreiben serialisiert (vorher
  verlorenes Update). Tests `tests/test_pool_hotfix.py` (Klassen `Schreibtransaktionen`, `Schreibsturm`).
- **„Mein Tag“ nur mobil, Seite „Wiedervorlage“, Leads VOT Desktop mit Gruppen (Phase 173 + 174,
  Agent M; Protokoll Claudia Castro 14.10.2026 Teil A, Design-Entwurf „Außendienst App“ –
  Aufbau/Abstände/Verhalten, Farben aus den Design-v2-Tokens):** `GET /leads` liefert dem Außendienst
  (Basisrolle, auch Handelsvertreter) Karten (`.mt-mobil`, unter 600 px) und die Tabelle „Leads VOT“
  (`.mt-desktop`, ab 600 px) im selben HTML (`templates/leads/mein_tag.html`, Media-Query in
  `static/mein_tag.css`); Innendienst/Admin/Leadmanagement sehen nur die Tabelle
  (`templates/leads/liste.html` → Partial `leads/_tabelle.html`). Der v32-Umschalter „Karten |
  Tabelle“, die Einstellung `leads_darstellung`, die mobile Filterkarte und die Blöcke „Fällig heute“/
  „Heiße Kunden“/„Weitere Termine“ entfallen. Aufbau mobil (`app/mein_tag.py`, Makros
  `leads/_karten.html`): Kopf „Mittwoch, 14. Oktober“ + „Mein Tag“ + Initialen (`avatar`), keine
  Kennzahlen; Karte **„Als Nächstes“** (nächster nicht erledigter Termin, dessen Ende noch nicht
  erreicht ist: „in 25 Min“/„jetzt“, Uhrzeit groß + „bis HH:MM“ aus `ende` bzw. Beginn +
  `ad_profile.termin_dauer_min`, „Sparte, Termintyp“ aus `app/sparten.py` + `vot_termine.typ`
  (vot/telefon/online → Vor-Ort-Termin/Telefontermin/Teams [ANNAHME]), Anschrift als Maps-Link,
  „Route starten“ = Google-Maps-Routenplaner mit Zieladresse, `tel:`); aufklappbarer Block
  „n überfällige Termine“ (Vergangenheit ohne Erfassung, eingeklappt ab vier) [eigene Annahme];
  **„Heute · n Termine“** mit Zeitstrahl (erledigt = `--status-gruen`, nächster = `--status-orange`,
  übrige leer; erledigte gedämpft mit Link „Erfassung“ auf `/erfassung/<id>/pruefen` statt Knopf);
  Zeilen klappen Details auf; **Erledigt-Logik:** Termin erledigt, sobald alle Sparten des
  Termin-Objekts abgesendet oder ausgeblendet sind (Vorgang + `objekt_id` + Sparte, kein Haken);
  Telefon-/Teams-Termine ohne Erfassung bleiben bis Tagesende offen und fehlen am Folgetag [ANNAHME];
  **Abschnitt „Wiedervorlage“** (Untertitel „Vorgänge, die auf Rückmeldung warten“, Zähler, Chips
  Alle · Hoch · Mittel · Niedrig mit Anzahl, Segment „Sortieren: Priorität · Name · Datum“ mit ↓/↑,
  höchstens vier Karten mit Initialen, Sparten in Langform, Badge aus der Hot-Ampel (heiß = Hoch,
  warm = Mittel, kalt/leer = Niedrig), „Letzter Kontakt TT.MM. · seit X Tagen“ (ab 14 Tagen Warnfarbe,
  „heute“/„seit gestern“), Tippen klappt die Anruf-Karte v32 (Dialog „Nächster Schritt“, Notizfeld,
  letzte Aktivitäten) auf, Link „Alle N Wiedervorlagen anzeigen“; Datenbasis
  `nachfassen.wiedervorlage_liste(session, benutzer_id, heute=None)` = fällige + überfällige
  Wiedervorlagen des AD ∪ eigene Vorgänge mit Ampel heiß oder Status `bestellung_angekuendigt`,
  „Letzter Kontakt“ = letzter Notizen-Chat-Eintrag aller Herkünfte [ANNAHME], Inaktivitäts-Kennzeichen
  von N über `inaktiv_kennzeichen`); **„Kommende Tage“** (14 Tage [ANNAHME], Datumskachel „DO/15“,
  „Donnerstag, 15. Oktober · 2 Termine“); **untere feste Leiste** Mein Tag · Kalender (Meine Termine) ·
  Wiedervorlage · Kunden (Kopfzeilen-Suche) mit aktivem Eintrag und Safe-Area
  (`leads/_leiste.html`, von `base.html` für den Außendienst auf allen Seiten außer Login/PIN-Wechsel/
  Erfassungsbogen/Signatur/einbett eingebunden; Logik in `static/mein_tag.js`, Chips/Sortierung/Suche
  clientseitig, Zustand `sessionStorage` [ANNAHME]). **Seite „Wiedervorlage“** `GET /leads/
  wiedervorlagen` (Außendienst; andere Rollen → `/angebote?verfolgung=versendet` [ANNAHME]):
  Zurück-Pfeil „Mein Tag“, Titel „n offen“, Suchfeld „Nach Name suchen“, Chips bezogen auf die
  Suchtreffer, alle Vorgänge, Telefon-Knopf je Karte, Leerzustand „Keine Vorgänge gefunden“ + „Filter
  oder Suche anpassen.“. Glocke art `nachfassen` verlinkt `/leads#wiedervorlage`. **Leads VOT Desktop
  (Phase 174):** Lead-basierte Tabelle (wie seit v1/v8) mit Gruppen Überfällig · Heute · je Folgetag
  (`details.lm-gruppe`, Uhrzeit innerhalb der Gruppe), Sticky-Filterleiste (Suche, Termin/Ansicht,
  Vertriebler, Status, **Priorität = Hot-Ampel** (`?prioritaet=hoch|mittel|niedrig`), Kanal, Sparte,
  Spaltenwähler), Spalten je Nutzer über T's Bausteine (Board-Key `leads_vot`,
  `lead_boards.spalten_fuer/sortierung_fuer/spalten_fest`, Jinja-Globals `lm_spalten_url`/
  `lm_spalten_fest`, Makros `spalten_kopf`/`spalten_colgroup`/`breiten_gesetzt`/`spaltenwahl`/
  `tabellen_daten`, `lm_boards.js` im Nur-Spalten-Modus; `mein_tag.SPALTEN_RUECKFALL` nur noch als
  dokumentiertes Spiegelbild des Katalogs), feste erste Spalte Kundenname, Spaltensortierung innerhalb
  der Gruppen (`mein_tag.gruppen_sortieren` → `lead_boards.zeilen_sortieren(…, wert=)`).
  Tests `tests/test_v33_mein_tag.py` (15); Alt-Tests v32 angepasst (Protokoll A.5).
- **Lead-Board-Layout für alle Tabellen des Angebotstools (Phase 174, Protokoll Claudia Castro
  14.10.2026 Teil A.4):** Angebotsliste, Erfassungen (inkl. TAIFUN-Warteschlange = Reiter „In TAIFUN
  zu schreiben“/Kachel `individuell-offen`), Meine Angebote, Kunden und Leads VOT Desktop (M) haben
  dieselbe Bedienung wie die Lead-Boards: Sticky-Filterblock (heutige Filter als Chip-Selects,
  Suchfeld mit Schnellfilter, Spaltenwähler „Spalten“ *(Lead-Boards seit v35 mit serverseitiger Sofortsuche,
  Phase 186)*), Tabelle scrollt waagerecht/senkrecht im
  eigenen Container (`.lm-tabellen-at`, Sticky-Kopf, Zweit-Scrollleiste), Sortierung per Klick
  auf den Spaltenkopf (1. Klick auf, 2. ab, Pfeil, leere Werte ans Ende, je Nutzer gemerkt und
  serverseitig vor dem Rendern angewendet), Spalten je Nutzer (ein-/ausblenden, umbenennen,
  Reihenfolge per Drag & Drop, Breite, „Zurücksetzen“), **keine Sammelaktionen**. Bausteine in
  `app/lead_boards.py`: `TABELLEN_BOARDS` (`leads_vot · erfassungen · angebote · meine_angebote ·
  taifun_warteschlange · kunden`, `KONFIG_BOARDS` bleibt das Lead-Tupel), Kataloge `KATALOGE`
  (Standard = heutige Spaltenfolge, feste erste Spalte Kundenname bzw. „Erfassung“ in der
  Warteschlange – `spalten_fest`), **Rollenregel** `katalog_fuer(board, benutzer)`: EK,
  Deckungsbeitrag, DB-Ampel und Rabatt-Interna (`INTERNE_SPALTEN`) fehlen für die Basisrolle
  Außendienst (und Varianten) sowie für jede Rolle ohne Kalkulationssicht komplett, gespeicherte
  Keys werden beim Lesen und Speichern gegen den Rollen-Katalog gefiltert; `zeilen_sortieren(…,
  wert=)` generisch, `angebot_sortwert`, `migration_v33_tabellen` (idempotent). Makros
  `spalten_kopf`/`spalten_colgroup` (generisch) + `spaltenwahl`/`tabellen_daten` in
  `leadmanagement/_tabelle.html`; `lm_boards.js` läuft über `data-lm-spalten-board` auf jeder
  Seite (Route aus `data-lm-spalten-url`, Zeilen `data-zeile`, Schnellfilter `data-lm-suche`).
  Speicher-Route `GET/POST /lead-management/boards/spalten` für alle Rollen bei Angebotstool-Boards
  (Lead-Gate nur für Lead-Boards), Alias `GET/POST /einstellungen/spalten` für die Projektierung
  (`lead_boards.spalten_url`). Angebotsliste: Spalte **„Endbetrag“** (Gesamtbetrag nach USt und
  Rabatt, Phase 172) statt „Brutto“, Summenzeile folgt Filter + Sortierung, DB-Summe nur mit
  Kalkulationssicht, Filter/Spalte „Ohne Kontakt“ (Phase 176, `nachfassen.inaktiv_tage_fuer`).
  Kunden: Filter Kanal und Objektart. Meine Angebote: Tabelle mit Status/Sparte-Filter (Katalog
  ohne DB). Tests `tests/test_v33_tabellen.py`.
- Phase 175 (R 4c): Hauptboard-Zeilen tragen `hv_gruppe_offen` (Badge „Simons Gruppe (noch nicht
  verteilt)“ in der AD-Zelle, eine Abfrage je Board über `lead_v2.hv_gruppe_offen_ids`).
- **Lead-Management-Nachträge (Phase 175, R + G):** Kanal „Stadtwerke Düsseldorf“ (`leadmanagement.KANAL_SWD`,
  Aliase `SWD`: `kanal_anzeige/kanal_schluessel/kanal_aliase/kanal_gleich`; `kanal_werte` liefert ihn, sobald
  das Angebotsprofil SWD existiert) – AD-Profil/CSV-Import hinterlegen `kanal_ad_regel` mit allen
  Schreibweisen, `lead_termin.kanal_regel…` unverändert (Semantik „fest zuständig“, Rückfrage R2);
  `lead_v2.hv_ausgeschlossen` alias-sicher. **Infotext zum AD entfällt vollständig** (AD-Profil,
  Benutzerverwaltung, Vorlagen-Baum; `lead_mail.vertriebler_block_html/_text` nur Bild, Name, Telefon, E-Mail;
  Spalte `benutzer.infotext` bleibt ungelesen; Kontrollwert: Terminbestätigung eines AD mit altem Infotext
  enthält den Text nicht). Sammelaktion „An Handelsvertreter verschieben“: zweite Schaltfläche „Simons Gruppe“
  (`lead_v2.hv_gruppen_wahl`, `HV_GRUPPE_SIMON_NAME`) → `ad_id` = Gruppenleiter + Marker-Aktivität
  `hv_gruppe_offen` (`lead_v2.hv_gruppe_offen_setzen/hv_gruppe_offen/hv_gruppe_offen_ids/hv_gruppe_verteilt`)
  [ANNAHME: kein neues Feld], Badge „Simons Gruppe (noch nicht verteilt)“ in Kartei, HV-Ansicht und
  Hauptboard (T), Auflösung über jede Zuweisung (`ad_zuweisen` → Aktivität „Zuständiger: <Name>“; Simon wählt
  sich selbst → behält den Lead). Tests `tests/test_v33_lead_nachtrag.py` (6), Alt-Test `test_lead_v4`
  (C_SammelaktionHV: Schaltfläche „Simons Gruppe“) und `test_lead_v4_mail` (Infotext) angepasst.
- **Angebotsverfolgung / Nachfassen (Phase 176, `app/nachfassen.py` unten, `app/verfolgung.py`):**
  **Inaktivitäts-Kennzeichen** „ohne Kontakt seit X Tagen“ für Vorgänge mit Verfolgungsstatus
  Versendet/Nachgefasst – Schwelle `inaktiv_tage` (14) bzw. `inaktiv_tage_mfh` (20, Objektart MFH am
  Kunden; Lead-Parameter, Angebotstool-Einstellungen → Nachfassen); „Kontakt“ = jüngster Eintrag aus
  Notizen-Chat (alle Herkünfte), Anruf-Ergebnis (`LeadAktivitaet` anruf), Lead-Mail
  (`KommunikationLog.gesendet_am`), Mail-Verlauf der Angebote und Angebotsversand; eine Wiedervorlage
  in der Zukunft schützt nicht (`nachfassen.inaktiv_tage_fuer`, `inaktiv_kennzeichen` als Mengenabfrage,
  `inaktiv_text`; Anzeige in Mein Tag/Wiedervorlage und Angebotsliste mit Filter, Baustein
  `.inaktiv-kennzeichen` in `verfolgung.css`). **Telefonversuche:** jedes „Nochmal anrufen“ zählt
  `vorgaenge.nachfass_versuche` (Rückgängig senkt), Chip „Nachgefasst (2)“ (`verfolgung.status_text(status,
  versuche)`, Makro `verfolgung_chip(status, klein, vorgang_id, versuche)`), Akte zeigt „n Nachfass-Anrufe“;
  keine Schwelle, keine Eskalation. **Einwand-Chips** beim Ergebnis „Nochmal anrufen“ (optional):
  Tabelle `einwaende` (Startwerte Förderung unklar · wartet auf Mitbewerber · Entscheidung in der Familie ·
  Finanzierung offen, `verfolgung.migration_v33_nachfassen`), Speicherung `vorgang_einwaende` +
  `vorgaenge.letzter_einwand_id`, der letzte Einwand steht oben auf der Anruf-Karte; Pflege wie die
  Ablehnungsgründe (`POST /parametrierung/einwaende`: anlegen, umbenennen, deaktivieren, ↑/↓);
  Statistik „Einwände beim Nachfassen“ neben den Ablehnungsgründen (`verfolgung.einwaende_verteilung`,
  gleiche Filter). **Nachfass-Mail aus dem eigenen Postfach:** Vorlagen „Nachfassen 1/2“ im
  Vorlagen-Editor (`?vorlage=nachfassen_1|2`, `mail_vorlage_nachfassen_<n>_betreff/_text`, Platzhalter
  wie die Angebotsvorlagen, `{absender}` = sendender Außendienstler, Standardtexte als Entwurf), Block im
  Partial `_naechster_schritt.html` (Vorlage, Vorschau `GET /vorgaenge/{id}/nachfass-mail/vorschau`,
  Häkchen Angebots-PDF [ANNAHME], Senden `POST /vorgaenge/{id}/nachfass-mail` – JSON/Redirect, AD nur
  eigener Vorgang); Versand über `graph_versand.mail_senden_als(<E-Mail des Absenders>, …)` nur im Modus
  anwendung (delegiert: Knopf ausgegraut, Route 409 „Versand aus dem eigenen Postfach erst mit Graph als
  Anwendung“); Ablauf vorbereiten → `verbindung_freigeben` → Graph → Verbuchen im `_speichern`-Muster
  (nie doppelt senden); Mail im Mail-Verlauf (`AngebotsMail`, `eingehend = False`, `graph_id`
  `nachfass-mail:<conversationId>`) und als System-Notiz im Chat (+ Lead-Aktivität `mail`). Signatur des
  Absenders aus dem Upload: neue Seite `/einstellungen/signatur` (eigene Signatur für Außendienst/
  Innendienst/Admin, gleiche Ablage wie v6; ohne Upload nur der Firmenblock); Inline-Bilder bis zur
  Erweiterung von `mail_senden_als` als data:-URI. Tests `tests/test_v33_nachfassen.py` (17).
- **Tests, Rollout-Vorbereitung, Doku (Phase 177, Orchestrator, 14./15.10.2026):** elf neue Testdateien
  `tests/test_v33_*.py` (graph 28, rollen 22, service 17, kalender 17, outlook 21, auto_phase 10, rabatt 21,
  mein_tag 15, tabellen 15, lead_nachtrag 6, nachfassen 17, fundament 13); Gesamtsuite `pytest tests -q`
  **1344 bestanden, 5 übersprungen, 0 Fehler** (11:48 min), Wächter-AST v27, Token-Wächter v30 und der neue
  Wächter `UploadRoutenOhneSchreibsperre` grün. Angepasste Alt-Tests (Begründung in der Gesamtübersicht
  `diagnose/v33/gesamtuebersicht.md`): Lead-Kalender-Umleitung (`?alt=1`), Infotext, Go-live 12 Punkte,
  „Simons Gruppe“, Kalender-Rechte AD, Scheduler 16 Läufe / 3 mail-sync-Teilschritte, Outlook-Warteschlange
  statt Direktaufruf, Basisrolle auf der Anmeldeseite, Spaltenkopf mit Werkzeugen, Mein-Tag-Blöcke, zwei Tests
  mit ungesicherter Schreibung über eine Anfrage/einen Lauf hinweg (commit/rollback davor), festes Testdatum →
  `date.today()`, `tests/abnahme.py` „Endbetrag:“. **Rollout-Vorbereitung** (`diagnose/v33/abschluss_tests.sh`,
  Server-Kopie vom 03.10.2026, Protokolle `diagnose/test_v33_final/`): `migrate.py` zweimal (zweiter Lauf ohne
  Änderungen), Testbenutzer je Basisrolle + Varianten Montage Heizung / Service Elektro / Handelsvertreter,
  VOT-Abgleich ohne Abweichungen, **Rückweg-Probe v32-Code (Worktree c3be9fc) auf der v33-Datenbank 24/24**,
  Abnahmeskript 93/93, Voll-Crawl sechs Basisrollen + drei Varianten je hell/dunkel (106.884 Aufrufe, 0 Abstürze,
  inkl. der sechs Tabellen der Phase 174), Smoke 8/8, **Lasttest** Profil `normal` (50 Nutzer, 20 min, Modus
  anwendung gemockt, `kalender_sync = an` → 16 Läufe inkl. `outlook-sync`/`outlook-ruecklesen`, Pool-Invariante
  85 ≤ 90): 0 × 5xx, 0 locked, Pool-Spitze 43 %, p95 Editor 261 ms / PDF 1,8 s / Kundensuche 224 ms erfüllt,
  **nicht erfüllt** p95 Listen und Akten 1.568 ms (Ziel 1.500) und p95 Terminvorschläge 14,2 s (Ziel 6 s; v32
  8,9 s – Rückfrage, Vergleichslauf ohne Kalender-Sync in `docs/lasttest-v27.md` 4.8); Profil `schreibsturm`
  190/190 Positionen korrekt, 0 locked, Schreibsperre max. 9 ms. Screenshots `docs/design-v33/` (64 Bilder
  nachher hell/dunkel: Kalender je Modul/Tag/Monat/mobil, Rollen, Service- und Montage-Backend, Verbindungs-
  Seite, Mein Tag und Wiedervorlage 390 px, sechs Tabellen, Kartei, Portal …; anonymisierte Kopie, EK/DB
  ausgeblendet). **Befunde des Abschlusslaufs (behoben):** `migrate.py`-Meldung mit „→“ hätte auf der
  cp1252-Konsole des Servers NACH den Commits abgebrochen (`update.bat` → `:migration_fehler`) → ASCII-Meldung +
  `errors="replace"`; sieben Upload-Routen hielten mit Phase 172 die Schreibsperre während der Übertragung →
  Freigabe vor `anfrage.formular` + Wächter; 13 rein lesende Kurz-Sitzungen → `kurz(schreibend=False)`;
  `lead_anrufliste.dauer_korrigieren` mit getattr-Rückfall. Doku: dieser Abschnitt, Zuordnungszeile v33,
  Titelzeile, Leitplanken ab v33, Fachliche Regeln (Rollen, Outlook, Rabatt), überholt-Marker in v5/v6/v8/v12/
  v15/v17/v22/v25/v27/v28/v29/v30/v32; `docs/graph-einrichtung.md` (neu gegliedert), `docs/outlook-sync.md`
  (neu), `docs/betrieb.md` („Ergänzungen v33“), `docs/lasttest-v27.md` (4.8), `docs/nach-dem-update-v33.md`,
  `docs/updates.md` (4b), `docs/projektierung-entscheidungen.md`, `docs/leadmanagement-entscheidungen.md`,
  `docs/design-system.md`, `docs/signaturen.md`, `docs/PROTOKOLL-2026-10-14-Angebotstool.md`;
  `config.VERSION = "v33"`. Foto-Upload-Meldung der Vertriebler (15.10.2026): Ursache Datenmenge der
  Originalfotos über LTE/VPN – Vorschlag Verkleinern auf dem Handy, Entscheidung offen (nicht Teil von v33).
- **Nachtrag 15.10.2026 – Entscheidungen zu den Rückfragen des Durchlaufs** (Andreas: „alle offenen Fragen
  selbst nach bestem Gewissen und im Interesse des Projekts beantworten“; Nummern wie in
  `diagnose/v33/gesamtuebersicht.md`, Commit „v33-Nachtrag 15.10.2026“, kein Push):
  **Plan/Orchestrator:** P1 Tests rechnen nach echtem Kalender (10.10.2026 = Samstag); P2 die alte
  Lead-Wochenansicht bleibt in v33 über `?alt=1` als Übergang und entfällt mit einem späteren Plan; P3
  nächste Rollout-Prüfung mit frischer Server-Kopie; P4 „Claude outputs/“ steht jetzt in `.gitignore`; P5
  Alias `GET/POST /einstellungen/spalten` bleibt; P6 Lasttest-Zielwerte bleiben – nach dem Rollout auf dem
  Server nachmessen (Parametrierung → Betrieb, p95 je Route), bei Bestätigung Folgeplan (Cache für
  `nachfassen.wiedervorlage_liste`, Profil der Terminvorschläge); **P7 Foto-Upload in v33:**
  `app/static/bild_verkleinern.js` (in `base.html`) verkleinert Bilder vor dem Upload auf dem Gerät auf
  2000 px Kante / JPEG 0,85 (Grenze wie `galerie.MAX_KANTE`; < 400 KB, Nicht-Bilder und nicht dekodierbare
  Formate bleiben) – jedes Formular mit Bild-Dateien (Galerie-Upload, Montage-Foto, Formular-Fotos) wird beim
  Absenden abgefangen und mit den verkleinerten Dateien gesendet (DataTransfer + `requestSubmit`); die
  Foto-Sammelbox (`_galerie.html`) verkleinert beim Hinzufügen und lädt **Foto für Foto** mit Fortschritt
  „Lade 2 von 5 …“ hoch; Server unverändert.
  **K:** R1 Umleitung bleibt; R2 Leadmanagement zählt zu „Innendienst“; **R3 erfolgte Vor-Ort-Termine bleiben
  als Rückschau sichtbar** (gedämpft `kz-erfolgt`, nicht verschiebbar); R5 Kalender-Knopf im Montage-Backend
  reicht; **R6 Drag in die Zeile eines anderen Vertrieblers verlangt eine Bestätigung** („Vertriebler wechseln
  zu …? Umbuchung + Terminänderungs-Mail“, `bestaetigung_noetig`); R8 Monatsansicht mit Punkten reicht.
  **G:** R1 rote Mitarbeiter-Postfächer schalten den Modus nicht zurück; R2 keine Suche in
  Innendienst-Postfächern (`MessageCopyForSentAsEnabled` ist Pflicht); R3 Info-Mail an angebot@ ja; **R4
  Admins mit E-Mail stehen in der Postfach-Liste** (`MITARBEITER_BASISROLLEN` + admin); R5 Verbindungstest
  prüft alle Kalender; R6 PEM + Thumbprint bleibt.
  **R:** R1 Marker-Aktivität bleibt; R2 Kanal-Regel bleibt „fest zuständig“; R3 Standardregel F13 ohne
  Kennzeichen; **R4 Migration `leadmanagement.migration_v33_swd_profil` setzt dem SWD-Profil die
  Kanalwerte „SWD, Stadtwerke Düsseldorf“, wenn leer**; **R5 HV-Dashboard zeigt den Block „Simons Gruppe –
  noch nicht verteilt“** (`dashboard_daten["gruppe_offen"]`, `hv_dashboard_block.html`); R6 Admin keine
  Zusatzrolle.
  **S:** R1 Ereignis-Phasen bleiben manuell; R2 Pflichtfelder bestätigt; R3 Abschluss beendet den Einsatz;
  **R5 Service-Einsatz ohne Team/Techniker ist erlaubt** (Besetzung folgt in der Akte; Backend-Sicht und
  Outlook-Kopien erst mit Besetzung); R6 Standarddauer 2 h, Anlass Pflicht.
  **A:** **R1 monday-Deal-Wert bei Basis „netto“ = Netto nach Rabatt** (`summen["netto_nach_rabatt"]`,
  alle Quellen stehen auf brutto – keine Änderung im Bestand); R2 schreibende GET-Routen bleiben (Folgeplan);
  R6 Backup-Test nur bei parallelen Läufen flaky.
  **O:** R1 TAIFUN-[ANNAHME] bleibt bis zum Abgleich mit dem Monteur-Kalender (Skript liegt bereit, Kategorie
  „Friondo-Tool“ erlaubt späteres Filtern); R2 `kalender_sync` bleibt der VOT-Schalter; R3 Kundennummer,
  sonst Vorgangs-ID; R4 Glockenart `kommentar`; **R5 keine automatische Kundenmail bei Verschiebung aus
  Outlook – Glocke an den Leadmanager** („bitte den Kunden über die Terminänderung informieren“); R6
  Team-Kalender nur bei `outlook_adresse`; **R7 Handlauf `scripts/outlook_bestand_einreihen.py`**
  (Projekt-/Service-Termine und bei `kalender_sync = an` offene VOT der nächsten 8 Wochen als Aufträge
  „anlegen“, Blöcke je 50, `--trocken`) nach dem grünen Verbindungstest.
  **M:** R1 Überfällig-Block bleibt; R2 ohne Einstufung = Niedrig; R3 Tabelle Lead-basiert; R4 Leiste
  „Kalender“ = Meine Termine; R5 Hinweiszeile bleibt. **T:** R1 DB-Summe mit Kalkulationssicht; R2 acht
  Spalten; R3 Katalog `erfassungen`. **N:** R1 Einwand-Startliste bestätigt; R2 Standardtexte als Entwurf
  (Innendienst passt im Editor an); R3 Grußformel bleibt in den Vorlagen – Signatur ohne eigene Grußformel
  hochladen; R4 PDF-Häkchen Standard aus; R5 Innendienst/Admin aus eigenem Postfach ja; R6 Antworten im
  AD-Postfach reichen; R7 Kontakt inkl. System-Notizen; R8 Zähler nur bei „nachgefasst“; R10 delegiert bleibt
  gesperrt. Tests `tests/test_v33_nachtrag.py` (9); angepasste Alt-Tests: `test_v33_service::
  test_pflichtfelder_und_mannschaft` (Service ohne Besetzung erlaubt), `test_v33_kalender` (Fixture „erledigt“
  = erfolgt sichtbar, neue Fixture abgesagt unsichtbar), `test_monday_rueckspielung::test_deal_wert_netto` und
  `test_v33_rabatt::test_monday_deal_wert` (Basis netto = Netto nach Rabatt). Gesamtsuite nach dem Nachtrag
  1352 bestanden, 5 übersprungen; `migrate.py` zweimal auf einer Kopie (2. Lauf ohne Änderungen); Skripte
  per Chrome headless geprüft (`diagnose/v33/orch/js_check.py`).

## Neu in v34 – Wallbox-Konfigurator, Angebotstool-Feedback 15.10., Mobil (abgestimmt 15.10.2026)

(Plan: PLAN_V21.md, Phasen 178–182. **Nummern:** der Plan nannte v35 und Phasen 183–187; die Zuordnungstabelle
endete bei v33/177, deshalb wurde er als v34/178–182 gebaut (Vorspann des Plans mit Prüfvermerk) –
PLAN_LEAD_V6 (noch nicht umgesetzt) bekommt v35/183–187 (Hinweisblock in der Plan-Datei). Umgesetzt am
15.10.2026 in EINEM Durchlauf: Fundament durch den Orchestrator (Spalten `angebote.wb_json`,
`angebote.auslegung_text`, `angebotspositionen.uebernommen_von_angebot_id/_position_id`, Tokens
`--alternativ`/`--alternativ-flaeche`, Router-Hüllen, pypdf), dann vier Agenten W (Wallbox, Phasen 178/179),
E (Alternativ, Elektro ins PV, Auslegungs-Position, USt – Phase 180), V (Kombi-Versand, Mail-Vorlage,
TAIFUN-PDF – Phase 180), M (Mobil – Phase 181) auf eigenen DB-Kopien; Integration, Lastmodell, Rollout-
Vorbereitung, Doku durch den Orchestrator; Berichte `diagnose/v34/<X>_ergebnis.md` (lokal). EIN Commit, kein
Push vor Freigabe. Alle Datenbankänderungen additiv – v33-Code läuft auf der v34-Datenbank (Rückweg-Probe im
Rollout-Skript). **Rückfragen 1–7 des Plans** wurden mit den Plan-Vorschlägen umgesetzt (Andreas: „bis zu
meiner Antwort mit den Vorschlägen arbeiten“): R1 WB003 = 1.297,20 € (Konflikt 1.597,20 € im Import-
Protokoll), R2 Montagekanal immer mit der Mehrlänge, R3 Zahlung v30-Standard, R4 Vollmacht bei WB immer,
R5 Auslegungszeile per Migration aus allen Entwürfen, R6 PV/KL/WB Sparten-Vorlage → AD-Vorlage → Standard,
R7 USt kaufmännisch. **Zulieferungen:** die Wallbox-Excel und das Musterangebot kamen erst am Nachmittag des 15.10. (im
Projekt-Stamm abgelegt, nach `Artikel-Preislisten/Wallbox/` verschoben: `WB Angebot Excel 1.xlsx` versioniert,
`Beispielangebot.pdf` gitignored) – zusammen mit der geänderten Wallbox-Logik (Nachtrag am Ende von PLAN_V21.md:
eine Datei, Erdarbeiten, Säule, Durchbrüche); das Mennekes-Datenblatt fehlt weiterhin. Tests laufen mit einer
synthetischen Fixture gleichen Aufbaus plus Stichproben gegen die echte Datei. Entscheidungen und [ANNAHME]-Listen: `diagnose/v34/gesamtuebersicht.md`.)

- **Wallbox-Konfigurator (Phase 178/179, `app/wb_auslegung.py`, `app/import_wallbox.py`, Agent W – Stand
  Nachtrag 15.10.2026 mit den Antworten von Andreas: eine Zulieferdatei, Erdarbeiten, Säule, Durchbrüche):**
  Eine grüne WB-Katalog-Erfassung erzeugt ein Tool-Angebot mit 19 % USt, ohne Förder-/KfW-Block (auch der
  Förder-Editor entfällt im Editor für KL/WB), ohne Wirtschaftlichkeit, **mit Vollmacht-Seite** (immer –
  Netzanmeldung § 14a; `anhaenge.vollmacht_erforderlich` + `angebotsprofile.vollmacht_erlaubt` [ANNAHME: auch
  bei Enni/SWD]); Freitext-Erfassungen laufen weiter über die TAIFUN-Schiene, GW/MS/WA/DMS bleiben Freitext.
  Bogen (Blatt „Fragen WB“, WB06 unbelegt): WB01 „Welche Wallbox?“ (Mennekes AMTRON 4You 310 → WB001
  938,50 € / 560 → WB002 1.390,55 €, keine Vorbelegung), WB02 „Wie viel Meter Leitungsverlegung
  erforderlich?“ (Vorbelegung 10 = `leitung_inklusive_m`, Dezimalkomma; Mehrlänge = WB02 − 10 m,
  kaufmännisch auf ganze Meter, nie unter 0 → WB005 lfd. Meter NYY-J 49,34 €/m), WB03 „Erdarbeiten
  erforderlich?“ (Vorbelegung Nein, unabhängig von der Montageart) mit WB04 „Erdarbeiten: wie viele Meter?“
  (nur bei Ja, Pflicht, ganze Meter → WB006 Erdarbeiten 123,50 €/m; 0/leer = Absende-Meldung „Erdarbeiten:
  Meter fehlen“), WB05 „Wandmontage oder Säule?“ (Vorbelegung Wandmontage; Säule → WB007 Fundament und
  Standsäule 1.020,00 € 1 × psl.), WB07 „Wie viele Durchbrüche erforderlich?“ (Vorbelegung 2 =
  `durchbrueche_inklusive`; darüber WB008 Bohrung/Durchbrüche 169,00 € × (WB07 − 2), ganze Stück), WB08
  Bemerkung (nur Protokoll); immer WB003 Anschlussvorbereitung (1.297,20 € psl. – bis 10 m Leitung und
  2 Durchbrüche enthalten) und WB004 Netzanmeldung (0,00 €). Angebotsaufbau: Block 1 „Wallbox“ · 2
  „Installation und Anschluss“ (WB003 · WB008 · WB005 · WB006 · WB007) · 3 „Netzanmeldung“. Keine
  AMPEL-Gründe; über 100 m Warnung ohne Sperre; keine Auslegungs-Position – Protokoll-Seite „Auslegung“ und
  `angebote.auslegung_text`: „Wallbox: AMTRON 4You 560“, „Leitungsverlegung gesamt: 25 m, davon 10 m
  enthalten, Mehrlänge 15 m“, „Erdarbeiten: 8 m“ bzw. „keine“, „Montage: Säule (Fundament und Standsäule)“
  bzw. „Wandmontage“, „Durchbrüche: 4 (2 in der Anschlussvorbereitung enthalten, 2 zusätzlich)“.
  **Steuerdatei `konfigurator_logik_v5.xlsx`** (Sicherung `diagnose/konfigurator_logik_v5.vor_v34.xlsx`):
  Blätter „Fragen WB“, „WB-Artikel“ (8 Zeilen WB001–WB008 = Positionen 001, 002, 003, 005, 006, 007, 008,
  004 der Datei; Anker Datei „WB Angebot Excel 1“ + Position + Beschreibungsanfang – die GUIDs der
  TAIFUN-Exporte sind Angebots-GUIDs, Spalte „GUID (zuletzt gesehen)“; die Blattspalte „Einheit“ überstimmt
  die Export-Einheit: WB007 psl. statt „m“, Protokollzeile), „Aktionen WB“ (13 Zeilen; Mengenwörter
  „× Mehrlänge“ nur bei WB02, „× WB04“, „× (WB07 − 2)“ – müssen auf Zahleneingaben zeigen), „Angebotsaufbau
  WB“, „WB-Parameter“ (`leitung_inklusive_m` 10 m, `meterposition_leitung` WB005, `erdarbeiten_position`
  WB006, `fundament_position` WB007, `durchbrueche_inklusive` 2, `durchbruch_position` WB008,
  `wallbox_standard` leer), Anhänge-Zeile `Mennekes AMTRON 4You Datenblatt.pdf` („wenn Sparte = WB“; neue
  Regelform „wenn Artikel WB001 im Angebot“), Lesehilfe „Wallbox (v34)“. **Lader `app/logik.py`:** Felder
  `wb_aktionen`, `wb_bloecke`, `wb_parameter`, `wb_parameter_einheit`, `wb_artikel`; `logik_fuer_sparte(logik,
  "WB")` liefert die WB-Sicht, sobald „Aktionen WB“ existiert UND die WB-Artikel importiert sind
  (`wb_artikel_fehlen` aus `artikel_pruefen`: ohne Artikel nur ein Hinweis – sonst wäre nach einem Rollout
  ohne Import die Parametrierung rot und jeder Bogen blockiert; WB bleibt dann reiner Bogen → TAIFUN);
  „Logik prüfen“ prüft Pflichtfragen mit Typ, Parameter (fehlend = Hinweis mit Standardwert), Schwellen
  „über N“ gegen die Parameter, Referenzen gegen „WB-Artikel“; `sparten.ist_freitext_sparte("WB", logik)` ist
  dann False (Sparten-Start zeigt die Weiche Katalog | Freitext). **Import `app/import_wallbox.py`**
  („Artikel → Wallbox-Positionslisten importieren“, Parametrierung → Logik & Importe mit Hinweis/Bestätigung,
  Lesesicht `/parametrierung/wb-logik`, Artikelliste Filter „Sparte WB“): liest den TAIFUN-Export
  `Artikel-Preislisten/Wallbox/WB Angebot Excel 1.xlsx` (`config.WB_PREISLISTEN_ORDNER`; Blatt „Tabelle 1“,
  Pos. 001–008 → WB001–WB008, Textzeile ohne Position = Vortext „Komplettpaket Wallbox inkl. Montage“),
  weitere xlsx im Ordner nur als Preisvergleich (Konflikt → Ankerdatei gewinnt, Protokoll), Quelle `wb`
  (`models.QUELLE_WB`), `_x000D_`/„?“-Platzhalter/„ ,“ bereinigt, **EK nur in `artikel.ek_cent`** (nie im
  Protokoll – Import nur Innendienst/Admin), Blöcke je 200 mit Commit, Import-Status
  „Wallbox-Positionslisten“, idempotent, WP-/PV-/KL-Importe fassen WB nicht an. `migration_v34_wallbox`
  (migrate.py) importiert automatisch, wenn referenzierte WB-Artikel fehlen und die Datei liegt – sonst
  einmalige Meldung „Wallbox-Preislisten fehlen – Import übersprungen (Artikel-Preislisten/Wallbox/)“ –, und
  legt die Textblöcke an (`angebotsprofile.seed_wb`: der Absatz „Komplettpaket Wallbox inkl. Montage“ wörtlich
  aus der Textzeile der Excel, ohne Datei als Entwurf). Einstellung `wb_guid_nachfuehren` (**Standard 0**,
  Entscheidung Orchestrator: die Logik-Excel ist auf dem Server git-versioniert; 1 = Angebots-GUIDs in die
  Blattspalte schreiben, nur Entwicklungs-PC). DB-Ampel WB: Startwerte rot < 800 € / grün > 1.200 €
  (`models.DB_SCHWELLEN_SPARTE` [ANNAHME]; mit den WP-Schwellen wäre jedes WB-Angebot rot). **Texte**
  (`angebotsprofile.wb_vortext`/`WB_VORTEXT`/`WB_STANDARD_NACHTEXT`, Blöcke „Friondo WB Standard/Enni/SWD/
  Sparkasse DU“, `ANGEBOTSTEXTE.md` Abschnitt 10): Vortext wörtlich TAIFUN-Muster + Komplettpaket-Absatz,
  Nachtext B + C mit `{zahlungsbedingungen}` (der v30-Standardtext ist wörtlich die Muster-Klausel
  „Anzahlung 50 % spätestens 14 Tage vor Arbeitsbeginn“) und „Voraussichtlicher Ausführungszeitraum“ wie KL,
  kein Nachtext A – alle Entwürfe fürs Gegenlesen; Mail-Vorlage WB ohne KfW-Platzhalter
  (`mail_vorlagen.ohne_kfw`). Kontrollwerte (`tests/test_wb_v34.py`; Fixture `tests/fixtures/wallbox/
  WB Angebot Excel 1.xlsx` mit VK wie die Zulieferung und erfundenem EK, Stichproben gegen die echte Datei):
  A 310 / 10 m / Nein / Wand / 2 Durchbrüche 2.235,70 / 424,78 / 2.660,48 €; B 560 / 25 m / Erdarbeiten 8 m /
  Säule 5.435,85 / 1.032,81 / 6.468,66 €; B2 = B + 4 Durchbrüche 5.773,85 / 1.097,03 / 6.870,88 €; C 560 / 8 m
  2.687,75 €; D 310 / 12,4 m 2.334,38 €; Muster AN251131 (001 + 002 + 003 + 005) 3.626,25 € (USt dort 688,99 €
  = kaufmännisch, R7). Abnahme-PDFs `docs/wallbox/abnahme-A-…/-B-…/-B2-….pdf`, `abnahme-protokoll.pdf`
  (echte Langtexte, Demo-Kunde). Tests `tests/test_wb_v34_logik.py` (33), `test_wb_v34_import.py` (22),
  `test_wb_v34.py` (25).
- **Alternativ-Kennzeichen klar abgegrenzt (Phase 180, Agent E, `app/elektro_pv.py`, `app/pdf_export.py`,
  `templates/angebote/editor.html`, `static/angebot_v34.css`):** Alternativ-Positionen (v10 „in anderem Angebot
  enthalten“) sind im PDF und im Editor auf einen Blick von Eventualpositionen unterscheidbar. PDF: vor der
  ersten Alternativ-Position eines Blocks ein farbig hinterlegter Hinweiskasten „Die folgenden Positionen sind
  bereits in Ihrem Angebot <Nr> (<Sparte>) enthalten und werden dort berechnet.“ (fpdf2-Primitiven), die Zeile
  leicht grau, Einzelpreis bleibt, G-Preis-Spalte „im PV-Angebot“ (bzw. „im WP-Angebot“ …; ohne erkennbare
  Sparte „anderes Angebot“ in kleinerer Schrift, `elektro_pv.pdf_label`), der automatische v10-Vermerk
  bleibt. Sparte und Nummer kommen aus dem v10-Verknüpfungstext `alternativ_zu` („<Sparte>-Angebot
  <Nummer>“, `elektro_pv.ziel_parsen`). Editor: Positionszeile mit farbigem linken Balken (Tokens
  `--alternativ`/`--alternativ-flaeche`), Badge „Alternativ · im PV-Angebot AN-C-…“ mit Link zum
  Geschwister-Angebot, „EP“-Badge unverändert; verweist die Verknüpfung auf ein gelöschtes/überholtes/
  abgelehntes Angebot, zeigt der Editor „Geschwister-Angebot nicht mehr gültig“ (neu – den v10-Hinweis gab es
  im Bestand nicht). Lieferschein weiterhin ohne Alternativ-Positionen. Abnahme-PDFs
  `docs/wallbox/abnahme-alternativ-<Nr>.pdf` (+ `…-pv-<Nr>.pdf`). Tests `tests/test_v34_alternativ.py`.
- **Elektroarbeiten ins PV-Angebot (0 % USt) (Phase 180, Agent E, `app/elektro_pv.py`,
  `app/routers/angebote_elektro.py`):** Knopf im Editor eines WP-/KL-/WB-**Entwurfs** (Innendienst/Admin),
  sichtbar nur, wenn der Vorgang ein PV-Tool-Angebot im Status Entwurf/Versand vorbereitet hat
  (`elektro_pv.knopf_sichtbar`; bei mehreren das jüngste). `POST /angebote/<id>/elektro-ins-pv` (eine
  `_speichern`-Transaktion, JSON bei Accept application/json): Elektro-Positionen = Block „Elektroarbeiten“
  (WP Block 7, KL Block 2, WB WB003/WB005/WB006) plus alle Positionen der Parametrierungsliste
  „gewerkeübergreifende Artikel“ (v10 – Standard 014–017, 104, Z22, 152, Z23; damit wandern auch die
  Fit-for-Future-Positionen mit, Rückfrage), ohne EP/bauseits/bereits Alternativ; im Ursprung werden sie
  Alternativ mit `alternativ_zu = "PV-Angebot <Nr>"`, im PV-Angebot entstehen voll berechnete Kopien (Artikel,
  Netto-Einzelpreis inkl. Positionsrabatt, Menge, Langtext, `ek_cent`) in einer eigenen Gruppe
  „Elektroarbeiten <Sparte> (aus Angebot AN-C-…)“ am Ende, Kennzeichen `uebernommen_von_angebot_id/
  _position_id`, 0 % USt über den Steuersatz des PV-Angebots; **Dubletten** (gleiche Artikelnummer oder
  gleiche normalisierte Bezeichnung, z. B. Zählerschrank 104 vs. PV123) werden nicht kopiert, die
  Ursprungsposition wird trotzdem Alternativ (Meldung „… davon n bereits im PV-Angebot vorhanden – nicht
  kopiert“) [ANNAHME]; Vermerk „Enthält die Elektroarbeiten aus Angebot AN-C-… (<Sparte>).“ im PV-PDF,
  System-Notiz im Vorgangs-Chat, Meldung „n Positionen (netto x €) in AN-C-… übernommen – Kundenersparnis
  <Netto × (USt Ursprung − USt PV)> €“ (Kontrollwert 2.400,00 € → 456,00 €); ohne neue Elektro-Positionen
  „Nichts zu übernehmen“. „Elektroarbeiten zurückholen“ (`POST …/elektro-zurueckholen`): entfernt nur Kopien
  mit `uebernommen_von_*` (solange das PV-Angebot Entwurf/Versand vorbereitet ist) und hebt das Kennzeichen im
  Ursprung auf (Ursprung Entwurf/Versand vorbereitet; versendete/angenommene PV → gesperrt); der Editor des
  PV-Angebots zeigt an Kopien „↩ übernommen aus Angebot …“; `kombi_versand.doppelte_artikel` schlägt nach der
  Übernahme nicht mehr an, `gewerke_hinweise` ignoriert Kopien. DB je Angebot folgt den Positionen.
  Steuerliche Zulässigkeit ist Entscheidung von Friondo/Steuerberatung. Tests `tests/test_v34_elektro_pv.py`.
- **Auslegungs-Position entfällt (Phase 180, Agent E, `app/angebot_aufbau.py`, `app/kl_auslegung.py`,
  `app/pv_auslegung.py`):** WP „Auslegung der Wärmepumpe“ (Block 1, v11), KL „Auslegung der Klimaanlage“
  (Block 3, v24) und die PV-Auslegungszeile (Block 1, v16) werden nicht mehr als 0,00-€-Position angelegt; der
  Text steht in `angebote.auslegung_text` (`angebot_aufbau.auslegungs_text_fuer` je Sparte, WB über
  `wb_auslegung`), bleibt im Konfigurationsprotokoll und erscheint im Editor als aufklappbarer grauer Hinweis
  „Auslegung (intern)“ unter der Kopfkarte (nur Innendienst/Admin; der Außendienst sieht ihn nicht).
  Versionen/Duplikate/Kopien übernehmen das Feld; trifft `version_erzeugen`/`_positionen_kopieren` eine
  Alt-Zeile (`angebot_aufbau.ist_auslegungs_position`), entfällt sie und ihr Text wandert ins Feld. Bestand:
  `migration_v34_auslegung` (migrate.py) entfernt die Zeile aus allen **Entwürfen**, füllt das Feld und
  nummeriert wie „Neu durchnummerieren“ (R5); versendete/angenommene/überholte Angebote bleiben unverändert
  (Entwicklungs-DB: 2 PV-Entwürfe). Kontrollwerte unverändert (WP netto 30.245,43 €, KL-Fall A 6.518,66 €,
  PV). Tests `tests/test_v34_auslegung.py`.
- **USt-Rundung wie TAIFUN (Phase 180, R7, Agent E, `app/models.py`):** `Angebot.summen()` rundet die USt
  kaufmännisch (`ROUND_HALF_UP`) statt abzuschneiden – KL-Fall A 6.518,66 € netto → USt 1.238,55 €, Gesamt
  7.757,21 € (bis v33 1.238,54 / 7.757,20); Fall B (1.044,05 €), WP-Kontrollwert (5.746,63 €) und alle
  WB-Kontrollfälle unverändert. Editor, Angebotsliste, PDF, Meine Angebote, Statistik, monday-Deal-Wert und
  Mail-Platzhalter nutzen ausschließlich `summen()`; Rabatt-/KfW-Logik, `rabatt_netto`, `netto_nach_rabatt`
  unverändert. Tests `tests/test_v34_ust.py`; angepasste Alt-Tests siehe Gesamtübersicht.
- **Kombi-Versand verständlich (Phase 180, Agent V, `app/kombi_versand.py`, `routers/vorgaenge.py`,
  `templates/vorgaenge/akte.html`, `static/vorgang_v34.css`):** Die Vorgangsakte zeigt unter den Angeboten den
  Kasten **„Gemeinsam versenden“** (`id="gemeinsam-versenden"`) mit Häkchen an allen versandfähigen Angeboten –
  Entwurf, Versand vorbereitet, TAIFUN-Eintrag mit PDF; nicht wählbare (überholt, versendet, angenommen,
  abgelehnt, TAIFUN ohne PDF „PDF fehlt“) ausgegraut mit Grund (`kombi_versand.waehlbar`, `auswahl`). Erklärsatz
  „Alle angehakten Angebote gehen als separate PDFs in einer Mail an den Kunden; Entwürfe werden dabei
  automatisch versandfertig gemacht.“ Knopf „Kombi-Versand vorbereiten (n Angebote)“ (ab zwei) → EINE Mail mit
  mehreren PDFs wie v10; Entwürfe werden nach dem erfolgreichen Graph-Entwurf automatisch auf „Versand
  vorbereitet“ gesetzt (`entwuerfe_vorbereiten`, AngebotsNotiz „Versand vorbereitet durch Kombi-Versand“,
  Vorgangs-Notiz, Meldung); scheitert Graph, bleibt alles Entwurf [ANNAHME]. Vorauswahl über
  `?kombi=<angebot_id>#gemeinsam-versenden` (Editor-Knopf „Mit weiteren Angeboten dieses Vorgangs versenden“,
  Agent E). Die Häkchen an den Angebots-Karten sind entfallen; Formular `kombiform`/Feld `angebot_ids`/Route
  `POST /vorgaenge/<id>/kombi-versand` unverändert; Einzelversand unverändert. Tests `tests/test_v34_kombi.py`.
- **Mail-Vorlage je Sparte (Phase 180, Agent V, `app/mail_vorlagen.py`):** Ursache des Befunds „Klima-Mailtext
  wird nicht gezogen“: `vorlage_laden` nahm immer die Vorlage des Außendienstlers (WP-Wortlaut), sobald eine
  hinterlegt war; die Sparten-Vorlage KL/PV/WB wurde nur ohne AD-Vorlage geprüft (dokumentierte v27-Nachtrag-2-
  Reihenfolge, fachlich falsch für KL/PV/WB; `konfigurator_typ` war überall gesetzt, TAIFUN-Einträge erben die
  Sparte der Erfassung). Neue Reihenfolge (R6): **WP** AD-Vorlage → WP-Sparten-Vorlage → Standard (unverändert);
  **PV/KL/WB** (`SPARTEN_VORLAGE_ZUERST`) Sparten-Vorlage → AD-Vorlage → Standard; Rückfall je Feld auf den
  Standard bleibt; Versand-Meldung nennt die Quelle („Sparten-Vorlage KL“); Kombi-Versand behält seine
  Vorlage; Erklärtext in Parametrierung → E-Mail-Vorlagen angepasst. Tests `tests/test_v34_mail_vorlage.py`.
- **TAIFUN-Angebots-PDF per Drag & Drop (Phase 180, Agent V, `app/taifun_pdf.py`, `app/routers/taifun_pdf.py`,
  `templates/_taifun_pdf.html`, `static/taifun_pdf.js`):** Textextraktion mit **pypdf** (requirements.txt; nur
  Text, keine OCR – Scans melden „Kein Text im PDF gefunden“), `felder_erkennen`: TAIFUN-Nummer `AN\d{6}` hinter
  „ANGEBOT - Nr.:“, Datum „Datum : TT.MM.JJJJ“ der ersten Seite, Endbetrag brutto „Gesamt-Betrag € x.xxx,xx“
  bzw. „= Endbetrag“ (letzter Treffer), Sparte nur als Vorschlag aus Schlagwörtern. `POST
  /angebote/extern/pdf-lesen` (JSON, ohne Sitzung, ≤ 20 MB, nur PDF) liest das PDF im Dialog **„Extern
  erledigt“** VOR dem Speichern (Drop-Zone „TAIFUN-Angebot (PDF) hierher ziehen oder auswählen“, Felder mit
  `data-tp-feld` vorbelegt und „aus PDF gelesen – bitte prüfen“ markiert, nicht Erkanntes bleibt leer);
  `extern_erledigt` speichert das PDF am Eintrag (`extern_pdf_pfad`, Kombi-fähig) und als Kopie in der Galerie
  „Allgemein“. **Am TAIFUN-Eintrag** (TAIFUN-Seite, Vorgangsakte, Angebotsliste) ersetzt die Drop-Zone den
  Datei-Knopf: erneutes Ablegen ersetzt das PDF nur nach Sicherheitsabfrage (`bestaetigt=1`, sonst 409) und
  bietet Häkchen „Nummer / Datum / Endbetrag aus dem neuen PDF übernehmen“ (`POST /angebote/<id>/taifun-pdf`:
  Upload lesen und pypdf-Extraktion VOR dem ersten Datenbankzugriff, dann kurze Schreibtransaktion
  `taifun_pdf.eintrag_pdf_speichern(…, felder=)`; monday nicht automatisch – Knopf „Erneut übertragen“).
  Tastatur, `<noscript>`-Fallback, mobil nur Datei-Dialog; Styles nur Tokens. Tests
  `tests/test_v34_taifun_pdf.py` (synthetisches fpdf2-PDF; das Muster AN261737 fehlte).
- **„Angemeldet bleiben“ am Handy (Phase 181, Agent M, `app/auth.py`, `routers/anmeldung.py`,
  `anmeldung/login.html`):** Ursache: seit v27-Nachtrag 2 war das Häkchen nur für Außendienst/Montage sichtbar
  (`MOBILE_ROLLEN`) und `auth.sitzungsdauer_s` vergab die 30 Tage nur diesen Rollen – Admin/Innendienst
  bekamen am Handy immer 12 h (Max-Age 43200); verstärkend trug das Cookie nur `Max-Age`, und die
  Home-Bildschirm-App (PWA `standalone`) hat auf iOS einen eigenen Cookie-Speicher (Nachweis
  `diagnose/v34/M_patches/nachweis_angemeldet_bleiben.py`; das Login-Protokoll des Servers lag nicht vor).
  Jetzt: Häkchen „Auf diesem Gerät angemeldet bleiben“ für **alle Rollen auf Mobilgeräten** – Server erkennt
  das Gerät am User-Agent (`auth.ist_mobilgeraet`) oder am Feld `mobil=1`, das `login.html` bei Breite < 600 px
  bzw. Touch-Gerät setzt; Dauer `sitzung_tage_mobil` (30 Tage), `sitzungsdauer_s(session, benutzer,
  angemeldet_bleiben, mobil=)`; Außendienst/Montage wie v27 auf jedem Gerät 30 Tage, Büro-Rollen am PC 12 h.
  `auth.cookie_setzen` schreibt `Max-Age` **und** `Expires` (UTC), `HttpOnly`, `SameSite=Lax`, `Path=/`,
  `Secure` nur bei `HTTPS_AKTIV`; verlängert wird nur beim Login (nie je Anfrage; `anmelden-als` 2 h und „Alle
  Sitzungen beenden“ unverändert). Hinweis unter dem Häkchen „Als App auf dem Home-Bildschirm bitte dort
  anmelden.“ `auth.cookie_wert(id)` unverändert. Nebenbefund behoben: die Rolle Projektierung durfte die
  Galerie-Schreibrouten unter `/vorgaenge` nicht aufrufen (`_GALERIE_SCHREIBEN` in `auth.py`). Tests
  `tests/test_v34_login_mobil.py` (14).
- **Diktierfunktion (Phase 181, Agent M):** Makro `diktat_knopf(feld_id, klasse)` in `_diktat.html` + Icon
  `mikrofon` (`_symbole.html`) + `static/diktat.js` (in `base.html`): Knopf „Diktieren“ an den
  Bemerkungsfeldern der mobilen Erfassung (`Freitext groß`: O08, A12, PO05, PD10, PA14, KO09, WB03), der
  Freitext-Erfassung, am Notizen-Chat (`_komponenten.html`), an den großen Feldern der Montage-Formulare und am
  Restarbeiten-Feld des Montage-Backends. Web Speech API `de-DE`, Zwischenergebnisse live am Cursor, Stopp
  per Knopf oder Sprechpause; ohne `window.isSecureContext` (das Tool läuft über http im VPN) oder ohne
  `SpeechRecognition` zeigt die Stelle „Diktat: bitte das Mikrofon Ihrer Handy-Tastatur verwenden“.
  HTTPS-Vorbereitung `docs/https-intern.md` (Optionen interne Subdomain per DNS-Challenge / interne CA mit
  Geräteprofil / vorerst Tastatur-Diktat; `HTTPS_AKTIV`/`BASIS_URL`/`PROXY_IPS` aus v27) – Entscheidung
  Andreas/IT offen.
- **Galerie-Mehrfachupload und Kamera-Serie (Phase 181, Agent M, `_galerie.html`, `app/galerie.py`,
  `static/galerie_v34.js/.css`):** Makros `sammelbox(…)` (Kamera-Serie „Fotos aufnehmen“ → „Weiteres Foto“ mit
  `capture="environment"`, „Dateien wählen“ `multiple`, Liste mit Vorschaubild, Dateiname/Größe,
  Ordner-Dropdown je Datei (Vorbelegung Standard-Ordner; Ordnerliste je Sparte – Objekt-Ordner aus PLAN_LEAD_V6
  liegen noch nicht vor), Bemerkung je Datei, „Für alle übernehmen“, Fortschrittsbalken, Abbrechen/Leeren,
  `beforeunload`-Hinweis bei ungesendeten Fotos) und `galerie_einbindung()`; Bilder werden beim Hinzufügen auf
  dem Gerät verkleinert (`bild_verkleinern.js`, 2.000 px / JPEG 85 %, PDFs unverändert). **EIN Request** `POST
  /vorgaenge/<id>/galerie/upload` mit `dateien` / `datei_ordner` / `datei_bemerkung` positionsgleich (Aliase
  `dateien[]`/`ordner[]`/`bemerkung[]`); `galerie.mehrfach_speichern` legt mit Commit je Datei ab und meldet
  Teilerfolg (`galerie.meldung_fuer`: „2 von 3 Dateien abgelegt (…) – nicht abgelegt: x.jpg (Datei ist
  leer).“); mit `Accept: application/json` antwortet die Route `{ok, anzahl, abgelegt[], fehler[], meldung,
  ziel}` (403/404 als JSON), sonst Redirect; Rechte unverändert (`galerie.darf_hochladen`). Der Foto-für-Foto-
  Upload des v33-Nachtrags ist ersetzt; Einzel-Upload je Ordner, Drag & Drop und „Einsortieren“ bleiben.
  Mobile Erfassung (Seite Einschätzung): dieselbe Sammelbox im Formular-Modus (Dateien gehen mit „Weiter“
  mit) [ANNAHME]. Gilt in Vorgangs-/Projektakte, Montage-/Service-Backend und mobiler Erfassung. Tests
  `tests/test_v34_galerie.py` (15, davon 2 in Chrome headless über DevTools); `tests/test_v33_nachtrag.py::
  FotoUpload` angepasst.
- **Tests, Rollout-Vorbereitung, Doku (Phase 182, Orchestrator):** neue Testdateien `test_wb_v34_logik/
  _import/test_wb_v34` (71), `test_v34_alternativ/_elektro_pv/_auslegung/_ust` (47), `test_v34_kombi/
  _mail_vorlage/_taifun_pdf` (28), `test_v34_login_mobil/_galerie` (29). Angepasste Alt-Tests (Begründung in
  der Gesamtübersicht): Auslegungszeile/USt-Rundung (`test_kl_v24.py`, `test_kl_v24_auslegung.py`,
  `test_pv_v13.py`, `test_v22_feedback.py`, `test_v11.py`), Vorlagen-Reihenfolge (`test_v27_nachtrag2.py`),
  WB-Sicht/Freitext-Sparten (`test_kl_v24_logik.py`, `test_lead_v5.py`), Import-Schlüssel „wallbox“
  (`test_v27_importe.py`), Sammel-Request (`test_v33_nachtrag.py`). Lastmodell: Galerie-Upload mit drei Fotos in einem Request, TAIFUN-PDF lesen
  (`scripts/lasttest.py`). Rollout-Vorbereitung `diagnose/v34/abschluss_tests.sh` (Server-Kopie, `migrate.py`
  zweimal, Wallbox-Fixtures + Demo-Angebot in der Kopie, Testbenutzer, Rückweg-Probe v33-Code (Worktree
  2ab17a6) auf der v34-DB, Gesamtsuite, Abnahme, Voll-Crawl sechs Basisrollen + drei Varianten hell/dunkel,
  Smoke, Lasttest normal + schreibsturm). **Ergebnis (15.10.2026):** `migrate.py` zweimal (2. Lauf ohne
  Änderungen), Rückweg-Probe 24/24, Gesamtsuite **1535 bestanden, 4 übersprungen** (2 lastabhängige Tests einzeln
  grün), Abnahme 93/93, Voll-Crawl 8 Läufe 0 Abstürze, Smoke 8/8; Lasttest `normal` (50 Nutzer, 20 min, 6.358
  Anfragen) 0 × 5xx, 0 locked, Pool-Spitze 44 %, TAIFUN-PDF lesen p95 269 ms, Galerie-Mehrfachupload p95 971 ms,
  **wie in v33 nicht erfüllt** p95 Listen/Akten 1.850 ms (Ziel 1.500) und Terminvorschläge 13,2 s (Ziel 6 s) –
  keine v34-Route in den Spitzen, Empfehlung v33 P6 bleibt; `schreibsturm` 190/190 Positionen korrekt, 0 locked.
  Details: Gesamtübersicht `diagnose/v34/gesamtuebersicht.md`, `docs/lasttest-v27.md` 4.9. Screenshots `docs/design-v34/` (Login mobil, Galerie-Sammelbox mobil,
  Wallbox-Editor und -Erfassung, Vorgangsakte mit Kasten „Gemeinsam versenden“, hell/dunkel). Doku: dieser
  Abschnitt, Zuordnungstabelle, Titelzeile, Zentrale Dateien, Fachliche Regeln (USt-Rundung, Auslegungs-
  Position, Alternativ-Darstellung, Elektro ins PV), überholt-Marker in v8/v10/v11/v13/v22/v24/v27-Nachtrag 2
  und im E-Mail-Abschnitt; `ANGEBOTSTEXTE.md` Abschnitt 10, `docs/nach-dem-update-v34.md`, `docs/updates.md`
  (4c), `docs/betrieb.md` („Ergänzungen v34“), `docs/https-intern.md`; `config.VERSION = "v34"`.

## Neu in v35 – Lead-Management V6: TAIFUN-Kundenübergabe, Kanal-Stammdaten, Rechte Außendienst/HV-Gruppen, Profilbild, Inline-Bearbeitung, Filter, Sofortsuche, Objektfotos (abgestimmt 15.10.2026)

(Plan: PLAN_LEAD_V6.md, Phasen 183–187 – der Plan nannte v34/178–182, diese Nummern waren durch PLAN_V21
belegt (Hinweisblock im Plan). Umgesetzt am 15./16.10.2026 auf dem v34-Stand 7327226 in EINEM Durchlauf:
Fundament durch den Orchestrator (Tabellen `taifun_uebergaben`, `vertriebskanaele`; Spalten
`vorgaenge.taifun_export_am/_von/_datei/_status/_grund`, `kunden.taifun_kundennr`, `galerie_dateien.objekt_id`
(+ Index); Router-Hüllen `lm_taifun`, `lm_kanaele`, `lm_objektfotos`; `app/taifun_export.py` mit dem 17. Scheduler-
Lauf; `requirements.txt` lxml/Pillow/pillow-heif; Menüpunkt „Mein Profil“), dann fünf Agenten T (TAIFUN-Export,
Phase 183), K (Kanal-Stammdaten, Phase 184), R (Rechte, HV-Gruppen, Profilbild, Phase 185), B (Inline-Edit, Filter,
Sofortsuche, Phase 186), G (Objektfotos, Phase 186) parallel auf eigenen DB-Kopien; Integration, Rollout-
Vorbereitung und Doku durch den Orchestrator; Berichte `diagnose/v35/<X>_ergebnis.md` (lokal). EIN Commit, kein
Push vor Freigabe. **Ergänzungen von Andreas (15.10.2026):** `taifun_export_aktiv` standardmäßig AUS (Testen über
„Testdatei schreiben“), lxml + Pillow + pillow-heif in `requirements.txt`, Dienstkonto = Dienst `FriondoAngebotstool`
(SYSTEM) statt fr-wts-02, HV-Gruppen wie v31/v33 (`hv_gruppe_rene`, `hv_gruppe_simon`, `hv_gruppe_simon_mitglieder`,
Simons Gruppe) – keine zweite Gruppenlogik. Alle Datenbankänderungen additiv – v34-Code läuft auf der v35-Datenbank
(Rückweg-Probe im Rollout-Skript). **Zulieferung fehlt:** die Original-`ADRESSEN.xsd` von TAIFUN lag nicht vor –
`docs/taifun/ADRESSEN.xsd` ist eine Rekonstruktion aus dem Plan (Kopfkommentar); die Validierung liest immer diese
Datei, das Original kann ohne Codeänderung eingesetzt werden. Entscheidungen, [ANNAHME]-Listen und Rückfragen:
`diagnose/v35/gesamtuebersicht.md`; Team-Hinweise `docs/nach-dem-update-v35.md`.)

**Leitplanken ab v35 (zusätzlich zu v27/v30/v33):** Kanäle kommen ausschließlich aus `app/lead_kanaele.py`
(Tabelle `vertriebskanaele`; nie mehr `kanal_farben` von Hand, „Standard“ ist kein Kanal); Rechte im Lead-Modul
prüfen `lead_v2.bearbeiten_erlaubt(session, benutzer, vorgang)` (eine Funktion für Innendienst/Leadmanagement/Admin,
angestellten Außendienst an eigenen Leads und Handelsvertreter in ihrer Gruppe `lead_v2.hv_gruppe_fuer`); der
TAIFUN-Export schreibt Dateien nur über `taifun_export` nach `verbindung_freigeben` (nie überschreiben, immer
validiert); Objektfotos laufen über `galerie` (Formular vor dem ersten DB-Zugriff, HEIC → JPG); Lead-Filter und
Suchfelder sind Sofortsuche (`lm_sofort.js`, keine „Suchen“-Knöpfe, kein `onchange="this.form.submit()"`).

- **TAIFUN-Kundenübergabe (Phase 183, `app/taifun_export.py`, `app/routers/lm_taifun.py`, Agent T):** Ein Lead wird
  als XML-Datei nach `docs/taifun/ADRESSEN.xsd` (Namensraum `urn:taifun-software.de:schema:TAIFUN`, Wurzel
  `TAIFUN:AdList`, genau ein `TAIFUN:Ad`, Deklaration `encoding="windows-1252"` – Parameter `taifun_export_encoding`,
  Alternative utf-8) in den Import-Ordner `taifun_import_ordner` (Standard `C:\Users\kdadmin\Desktop\LM Datenimport`)
  geschrieben: `LM_<Vorgang>_<JJJJMMTT-HHMMSS>.xml` (Vorgang = „V<ID>“ [ANNAHME], Laufnummer „-2“ bei
  Sekundengleichheit), atomar (.tmp + Umbenennen, nie überschreiben), vorher gegen die XSD validiert (lxml), Kopie
  12 Monate unter `data/taifun_export/`. Feldzuordnung wörtlich nach Plan: `KdUse` true · `Name3` „Vorname Nachname“
  (Firma bei Firmenkunden [ANNAHME]) · `AnschriftStr`/`AnschriftHNr` über die Adress-Parser-Logik (unsichere Hausnummer
  → leer + Hinweis in der Karteikarte) · `AnschriftPLZ`/`AnschriftOrt` aus der abweichenden Rechnungsadresse (MFH,
  v20/v31), sonst Hauptobjekt/Kundenadresse · `Anrede` = Briefanrede · `EMail` nur bei `email_status ≠ ungueltig` ·
  `Telefon`/`Funk` nach Mobilvorwahl (015x/016x/017x bzw. +4915/16/17), national formatiert („0203 3965710“
  [ANNAHME]) · `Kartei` mehrzeilig (Übergabe am … durch …, Lead/Vorgang, Vertriebskanal, Interessen in Langform,
  Objekte je Zeile, Vertriebler, Vor-Ort-Termin je Objekt – „vorgemerkt: …“ in der Testphase –, Quelle/Kampagne,
  Großkunde, Kürzungs-/Parserhinweise; keine Notizen/Anrufe/Preise); Längen laut XSD gekürzt und vermerkt.
  **Schalter `taifun_export_aktiv` ist standardmäßig AUS** (Andreas 15.10.2026): „Terminierung“ schreibt dann keine
  Datei (Aktivität „TAIFUN-Übergabe nicht aktiv“), der Kartei-Knopf ist ausgegraut – „Testdatei schreiben“ (Demo-Lead
  Max Mustermann, `LM_TEST_<Zeit>.xml`) funktioniert immer. Auslöser bei `an`: (1) „Terminierung“ (B8) nach
  erfolgreicher Pflichtfeldprüfung, **auch in der Testphase** `terminierung_aktiv = aus` – der Knopf ist dann aktiv mit
  Tooltip „Testphase: nur Übergabe an TAIFUN, keine Buchung, keine Mail“, Buchung/Outlook/Mail/Phase bleiben gesperrt
  (`lm_termin.terminierung` → `taifun_export.terminierung_export` VOR der Testphase-Sperre; freigeschaltet läuft der
  Export vor der Buchung, ein Export-Fehler blockiert die Buchung nicht); (2) Kartei-Knopf „An TAIFUN übergeben“ →
  nach Erfolg „Erneut an TAIFUN übergeben“ mit Rückfrage und Datum der letzten Übergabe (Innendienst/Leadmanagement/
  Admin, nicht AD/HV; Kanal „?“ sperrt über `lead_kanaele.kanal_unklar`); (3) Dubletten-Hinweis vor dem Export
  (externer TAIFUN-Eintrag mit Nummer, Bestandsimport `angebote.bestand = 1`, gefülltes `kunden.taifun_kundennr` –
  alle über den Kunden): „Kunde ist vermutlich schon in TAIFUN angelegt (<Beleg>). Trotzdem übergeben?“ mit Ja/Nein;
  die Terminierung überspringt den Export in diesem Fall mit Aktivität [ANNAHME]; (4) nach Erfolg
  `vorgaenge.taifun_export_am/_von/_datei/_status = geschrieben`, Aktivität „An TAIFUN übergeben: <Datei>“, grünes
  Badge „TAIFUN <Datum>“ (+ Kundennummer) im Kartei-Kopf, Spalte „TAIFUN-Übergabe“ im Spaltenkatalog der Boards
  (Standard ausgeblendet), Filter-Chip „an TAIFUN übergeben“ (`taifun=1`); keine Glocke, keine Kundenmail. Fehler
  (Ordner fehlt, keine Rechte, Validierung) → `taifun_export_status = fehler` + Grund, rotes Label „TAIFUN-Übergabe
  fehlgeschlagen“ (Notiz-Spalte mit Rang 0 wie „Mail nicht gesendet“ v29, Kartei-Balken `_taifun_hinweis.html` mit
  „Erneut übergeben“), Zähler in den Lead-Einstellungen. **Übergabeliste** `/lead-management/taifun-uebergaben`
  (Datum, Vorgang, Datei, Benutzer, Status geschrieben · abgeholt · fehler · manuell importiert; „XML“ lädt die
  Kopie, „Als importiert markieren“); Scheduler-Lauf **`taifun-uebergaben`** (900 s, Start +240 s, 17. Lauf –
  Pool-Invariante 64 + 17 + 5 = 86 ≤ 90): Übergaben mit Status geschrieben, deren Datei nicht mehr im Ordner liegt →
  abgeholt (ein nicht erreichbarer Ordner markiert nichts), Kopien älter als 12 Monate werden 03:00–03:20 gelöscht;
  `db.kurz()`-Muster (lesen → Sitzung zu → Datei → kurze Sitzung je Block ≤ 50). Lead-Einstellungen → Abschnitt
  „TAIFUN-Übergabe“: Schalter, Ordner (Speichern prüft den Ordner nach `verbindung_freigeben`), Encoding, Knöpfe
  „Ordner prüfen“ (Testdatei schreiben und löschen, Hinweis auf das Dienstkonto SYSTEM des Dienstes
  `FriondoAngebotstool`, UNC-Pfad bei fremdem Rechner) und „Testdatei schreiben“, Prüfpunkte für den Go-live (Ordner
  erreichbar · Testdatei in TAIFUN importiert (Häkchen) · Encoding bestätigt (Häkchen)), Fehlerzähler mit Link.
  Feld „TAIFUN-Kundennummer“ (`kunden.taifun_kundennr`, Autospeichern im Kundeninfo-Block, Badge zeigt sie; Rückgabe
  aus TAIFUN OFFEN 2). Doku `docs/taifun-kundenexport.md` (Feldzuordnung als Tabelle, Beispiel `docs/taifun/
  beispiel_LM.xml`, Ordner/Rechte, Fragen an den TAIFUN-Betreuer: automatischer Import, Dubletten, Kundennummer,
  Encoding, Original-XSD). Tests `tests/test_lead_v6_taifun.py` (21; (a)–(j) des Plans).
- **Vertriebskanal-Stammdaten (Phase 184, `app/lead_kanaele.py`, `app/routers/lm_kanaele.py`, Agent K):** Tabelle
  `vertriebskanaele` (key, name, farbe, aktiv, pflicht_hinweis, reihenfolge) ist die einzige Quelle für Kanäle;
  `migration_v35_kanaele` legt die 30 Kanäle aus dem Nachtrag 15.10. an (RegioScout · Thermondo · ED - Google ·
  ED - Meta · Webinar · DAA · Enni · Google · Andere · Prepair Tech. · Konfigurator · Stadtwerke Düsseldorf ·
  Mitsubishi · WhatsApp · OTC · Klimakonfigurator · Empfehlung · Bosch · Sparkasse · EEE · Messe · Showroom ·
  Infoveranstaltung · Kontaktformular/info · Reonic · WELOVEX · Comodomo · Bestandskunde · ? · Energy Systems, mit
  den Hex-Startwerten des Plans), bildet alte Schreibweisen ab (`lead_kanaele.ALT_NEU`: „SWD“/„Stadtwerke
  Düsseld…“ → Stadtwerke Düsseldorf, „Sparkasse DU“ → Sparkasse, „EnergieDigital Google/Meta“ → ED - Google/Meta,
  „info“/„Kontaktformular“ → Kontaktformular/info …), leert den Alt-Kanal „Standard“ (kein Kanal mehr; das
  Angebotsprofil „Standard“ bleibt Fallback) und legt Bestandswerte außerhalb der Liste (EON, Provinzial,
  EnergieDigital, ZEUS Empfehlung, RS Versicherungen …) als inaktive Kanäle an (Label bleibt sichtbar, nicht neu
  wählbar; Meldung „als inaktiver Kanal angelegt“ – Dev-DB: keiner, Server: siehe Gesamtübersicht); der Parameter
  `kanal_farben` wird aus der Tabelle gespiegelt (Feld in den Lead-Einstellungen entfällt). Pflege unter
  Lead-Management → „Mehr …“ → **Vertriebskanäle** (`/lead-management/kanaele`, Link auch auf der Parametrierung-
  Verteilerseite; Admin/Innendienst pflegen, Lead-Rollen lesen): Name, Farbe (Farbwähler, Textkontrast automatisch
  aus der Luminanz), Anzahl Leads, Verwendungen 90 Tage, Anlegen, Umbenennen (wirkt auf Kunden, monday-Leads,
  Quellen, Angebotsprofil-Zuordnung, `hv_ausschluss`, `kanal_ad_regel`), Deaktivieren (= Löschen; Leads behalten den
  Kanal, Filter zeigen ihn unter „weitere“), endgültig löschen nur ohne Lead, „Bestand abgleichen“. Alle Kanal-
  Dropdowns (`leadmanagement.kanal_werte` → Tabelle, Kartei, Inline-Bearbeitung über `kanal_sortiert`, Schnellanlage
  mit neuem Kanalfeld, Benutzer-Import, Quelle, Leads VOT, Filter) zeigen die aktiven Kanäle nach Verwendungen der
  letzten 90 Tage absteigend, dann alphabetisch; inaktive nur am betroffenen Lead „(nicht mehr wählbar)“; Labels
  (Boards, Kartei, Anrufliste, Leads VOT, Angebots- und Kundenliste) holen die Farbe aus der Tabelle (Makro
  `kanal_badge` ohne Farbparameter, Jinja-Global `lm_kanal_farbe` mit 60-s-Lesecache). Die Zuordnung Kanal →
  Angebotsprofil (v9) bleibt der Teilstring-Abgleich, die Profil-Seite bekommt eine Vorschlagsliste. **Kanal „?“ =
  Vertriebskanal unklar:** Eingang ohne erkennbaren Kanal (Quelle ohne Kanal, API, Parser, Import, Schnellanlage ohne
  Wahl – alle über `leadmanagement.lead_anlegen`) setzt „?“ statt leer; das Kanalfeld ist rot markiert
  („Vertriebskanal klären“), zählt im Pflichtfeld-Zähler (`lead_v2.pflichtfelder_offen`, unabhängig vom Parameter
  `pflichtfelder`), sperrt Terminierung und TAIFUN-Übergabe (`lead_kanaele.kanal_unklar(vorgang)`), Filter-Chip
  „Kanal unklar“ im Hauptboard; „?“ ist Systemkanal (nie umbenenn-/löschbar, in Dropdowns zuletzt). Die Anrufliste
  zeigt den Filterwert `Standard` als „ohne Kanal“ (trifft leer und „?“). monday-Leads ohne Label behalten einen
  leeren Kanal (Sync außerhalb des Geltungsbereichs, Rückfrage). Tests `tests/test_lead_v6_kanaele.py` (14).
- **Außendienst bearbeitet eigene Leads wie der Innendienst (Phase 185, `app/lead_v2.py`, Agent R):**
  `lead_v2.bearbeiten_erlaubt(session, benutzer, vorgang) -> bool` ist die eine Rechtefunktion des Lead-Moduls –
  Innendienst/Leadmanagement/Admin überall, angestellter Außendienst an Leads mit `vorgaenge.ad_id` = eigene ID,
  Handelsvertreter an Leads seiner Gruppe (auch monday-Leads ohne `ad_id` über `leads.benutzer_id`);
  `zugriff_erlaubt`/`gate` entscheiden mit Vorgang darüber. Der Außendienst öffnet die Kundenkartei eigener Leads
  ohne Lesesicht (Autospeichern aller Felder, Status mit Pflichtgründen, Innendienst-Dropdown = Leadmanager,
  Außendienst-Dropdown wie v31, Kanal, Objekte, Objektfotos, Notizen, To-Dos, Anruf-Ergebnisse, Wiedervorlage,
  Termine im Rahmen der Testphase-Sperren); jede Änderung ist eine Aktivität mit Autor. Nicht: Archivieren/
  Duplizieren/Sammelaktionen (Boards bleiben dem AD verschlossen), Parametrierung, Löschlauf; fremde Leads bleiben
  Lesesicht (`kern.lead_ad_sicht` + `gehoert_benutzer`); EK/DB unverändert unsichtbar; `auth.py` brauchte keine
  Änderung. Mobile Kartei bei 390 px geprüft (Markup-Test + Chrome-Screenshots).
- **HV-Gruppensicht (Phase 185, Agent R):** `lead_v2.hv_gruppe_fuer(session, benutzer_id) -> set[int]` liefert die
  Gruppe aus den v31/v33-Parametern (`hv_gruppe_rene` → {René}; `hv_gruppe_simon` ∪ `hv_gruppe_simon_mitglieder`,
  leer = alle Handelsvertreter außer der René-Gruppe – v31-Rückfall, Rückfrage) – keine zweite Gruppenlogik. Ein
  Handelsvertreter sieht und bearbeitet alle Leads, deren `ad_id` in seiner Gruppe liegt: Handelsvertreter-Ansicht
  je Mitglied gruppiert („Leads meiner Gruppe“, Filter „Vertreter“ nur die Gruppe), Dashboard/Kacheln und Karte je
  Gruppe (Block „Simons Gruppe – noch nicht verteilt“ sehen alle Mitglieder), To-Dos, Kartei-Gate (fremde Gruppe
  404, gesperrte Seiten 303 wie v29), Terminassistent (Kandidaten = Gruppenmitglieder, Buchen/Umbuchen/Vormerken/
  Vorab nur auf Kalender der Gruppe über `lead_termin.hv_gruppe_ids`/`hv_ad_erlaubt`; `hv_nur_eigene` bleibt
  Kennzeichen), `board_zeilen`, Lead-Dashboard; nie Leads der anderen Gruppe. Umverteilung innerhalb der Gruppe per
  Dropdown (Kartei, HV-Ansicht; Sperre in `lead_v2.ad_zuweisen`: kein Entziehen, kein Gruppenwechsel, „An Standard
  geben“ nur innerhalb der Gruppe), zwischen den Gruppen nur Innendienst/Admin über die Sammelaktion (v33). Der
  zentrale Kalender `/kalender` zeigt dem HV weiter nur die eigene Zeile (Rückfrage).
- **Profilbild „Mein Profil“ (Phase 185, `app/profilbild.py`, `app/routers/einstellungen.py`, Agent R):** Menü ☰ →
  „Mein Profil“ (`GET/POST /einstellungen/profil`, alle Rollen): JPG/PNG ≤ 2 MB, quadratischer Zuschnitt (Mitte) im
  Browser (`profil_v35.js`, Canvas, Vorschau) und serverseitig (Pillow, 512 px JPEG), Entfernen, zusätzlich Vorname
  und Telefon [ANNAHME]; Ablage wie v29 (`data/benutzerbilder/<id>.jpg`, `benutzer.bild_datei`; `POST
  /einstellungen/profil/bild` liest Formular + Pillow VOR dem ersten Datenbankzugriff). Das Bild ersetzt die
  Initialen-Avatare (Makro `avatar(name, id, klasse, bild)` + Jinja-Global `profilbild_url`, `_tabelle.avatar` in
  Boards/HV-Ansicht, Kartei-Zuständige, HV-Gruppenkopf, Mein Tag, Benutzerverwaltung; CSS `lm_v35_r.css` in
  `base.html`) und steht in der Terminbestätigung `{vertriebler_block}` (v29-Weg); Bild-Route `GET /einstellungen/
  profil/bild/{id}` (angemeldet, Cache ein Tag mit `?v=`, 30-s-Ordnercache, ohne Datenbank). Admin setzt Bilder
  weiterhin in der Benutzerverwaltung. Tests `tests/test_lead_v6_rechte.py` (10; (l)–(n)).
- **Hauptboard: Zeilen direkt bearbeiten (Phase 186, `app/lead_boards.py`, `_tabelle.html`, `lm_boards.js`,
  Agent B):** Inline-Edit (v23: Status, Notiz, AD, Innendienst, Wiedervorlage) erweitert auf **Interessen** (Popover
  mit Mehrfach-Häkchen, alle Sparten inkl. MS/WA/DMS; Häkchen speichern 600 ms verzögert, „Übernehmen“ sofort),
  **Vertriebskanal** (Auswahl hinter der Pille, Kanäle nach Häufigkeit aus `lead_kanaele.kanal_sortiert`, „?“ rot
  mit „Vertriebskanal klären“ und wählbar [Rückfrage]), **Großkunde** (Häkchen, nur Innendienst/Leadmanagement/
  Admin), **Objektart** (neue Spalte, Standard ausgeblendet), **Telefon/E-Mail** (Klick in die Zelle öffnet das
  Textfeld, Enter/Verlassen speichert, Escape bricht ab; Fehler stellen den alten Wert wieder her), **Vor-Ort-Termin**
  nur Anzeige + Link in die Kartei, **Teilgenommen** (Infoabend, auch über die Board-Route). Validierung und
  Aktivität „<Feld>: „alt“ → „neu““ über `lead_kartei.feld_speichern` (dieselbe Funktion wie das Autospeichern der
  Kartei); Rechte je Zeile über `lead_v2.bearbeiten_erlaubt` (fremde Leads 404, lesbare ohne Recht 403 JSON);
  Pflichtfeld-Verletzungen (Kanal „?“, fehlender Außendienst, leere Pflichtfelder) färben die Zelle
  (`td[data-pflicht]`, Spaltenklassen bleiben exakt). Gilt für Hauptboard, Deals, Infoabend (eigene Route, Sender
  `window.lmInline.senden`) und die Handelsvertreter-Ansicht (Zeile als Makro `hv_zeile` in `_hv_zeile.html`,
  `POST /boards/zeile/{id}` mit `board=handelsvertreter` liefert sie neu); Sortierung/Spaltenbreiten bleiben, keine
  Seitenneuladung.
- **Gespeicherte Filter je Nutzer und Board (Phase 186, Agent B):** Leiste „Gespeicherte Filter“ in der Sticky-
  Filterleiste (Hauptboard, Deals, Infoabend, HV-Ansicht): „Filter speichern“ (Name, Häkchen „als Standard beim
  Öffnen“), Anwenden, ★ Standard, Umbenennen, Löschen, „Filter zurücksetzen“; Ablage `benutzer_einstellungen` Key
  `boards_filter` (`{board: {filter: [{id, name, werte, geteilt_id}], standard_id}}` – werte = Chips, Suche,
  Auswahlfelder, Sortierung, eingeklappte Gruppen); der Standardfilter greift beim Öffnen ohne Filterparameter
  (`lead_boards.filter_query`), URL-Parameter überschreiben ihn, `?filter=0` hebt ihn für den Aufruf auf (seine
  Sortierung gilt nur für den Aufruf [Rückfrage]). Innendienst/Admin „für alle freigeben“ → schreibgeschützte Kopie
  im globalen Eintrag `boards_filter_geteilt` (benutzer_id 0; andere Nutzer können sie als eigenen Standard setzen,
  Freigabe entfernen nur Ersteller/Admin) [ANNAHME; Leadmanagement-Rolle: Rückfrage]. Routen `GET/POST
  /lead-management/boards/filter` (speichern · umbenennen · loeschen · standard · freigeben · freigabe_entfernen);
  keine Datenbankänderung. Der Dialog „Filter speichern“ liegt als eigenes Makro `filter_dialog` außerhalb des
  Filterformulars (Befund: `<form>` im `<form>`).
- **Eine Suchleiste, Sofortsuche (Phase 186, `app/static/lm_sofort.js`, `lm_v35_b.css`, Agent B):** „Kontaktiert“
  hat nur noch eine Suchleiste – Name, Ort, PLZ, E-Mail, Notiz, Ergebnis, Benutzer und Rufnummer (Ziffernfolge ab
  3 Ziffern = Endziffern-/Teilsuche v31, E.164-normalisiert, Leerzeichen/Schrägstrich/Plus egal; `telefon=` bleibt
  Alias). Alle Suchfelder und Filter des Lead-Moduls (Hauptboard, Deals, Kontaktiert, Infoabend, Handelsvertreter,
  Anrufliste, Kanban, Karte, To-Dos, TAIFUN-Übergabeliste) wirken sofort: Formulare mit `data-lm-sofort` – Suchfeld
  300 ms nach dem Tippen, Chips/Auswahl sofort, Chip-Links über `data-lm-sofort-links`, Enter erlaubt, Escape leert,
  laufende Anfragen verworfen (AbortController), URL per `history.replaceState` (Zurück-Navigation v30 bleibt);
  Boards und Kontaktiert liefern `?fragment=1` als JSON `{ziele: {name: html}}` (`lead_boards.fragment_ziele`), die
  übrigen Seiten werden geparst und nur die Bereiche `data-lm-sofort-ziel` getauscht (Klappzustand der Gruppen
  bleibt); danach feuert `lm-sofort:geladen` (`lm_boards.js`/`lm_info.js`/`lm_hv.js`/Anrufliste binden neu). Die
  Knöpfe „Filtern“/„Suchen“/„Anwenden“ sind entfallen (noscript-Rückfall), `onchange="this.form.submit()"` kommt im
  Modul nicht mehr vor; gespeicherte Filter speichern den Suchtext mit. Tests `tests/test_lead_v6_boards.py` (12,
  davon einer in Chrome headless; (o), (p), (r)).
- **Fotos je Objekt (Phase 186, `app/galerie.py` Abschnitt „Fotos je Objekt“, `app/routers/lm_objektfotos.py`,
  `templates/_objektfotos.html`, `kartei_objekte.html`, `static/objektfotos_v35.js`/`lm_v35_g.css`, Agent G):** Die
  Galerie des Vorgangs (v15) erhält je aktivem Objekt (`vorgang_objekte`, v31) einen Ordner „Objekt <Bezeichnung>“ –
  bei Ein-Objekt-Vorgängen „Objekt“ – hinter den Sparten-Ordnern (`galerie.ordner_liste(session, sparte,
  vorgang=…)`); Zuordnung Foto ↔ Objekt über `galerie_dateien.objekt_id` (Migration `migration_v35_objektfotos`
  füllt sie aus den Ordnernamen; Alt-Namen „Objekt“/„Objekt <Nr>“ werden toleriert, eine Umbenennung in der Kartei
  zieht den Ordner nach – `objekt_umbenannt`). Kundenkartei: Block „Fotos“ in jeder Objektkarte bzw. „Fotos zum
  Objekt“ beim Ein-Objekt-Vorgang – Vorschaukacheln mit Lightbox v28, „Foto aufnehmen“ (Kamera) / „Fotos wählen“
  (mehrere), Upload sofort nach der Auswahl (auf dem Gerät verkleinert, `bild_verkleinern.js`), `POST
  /lead-management/lead/{id}/objekt/{oid}/fotos` (JPG/PNG/HEIC → JPG über pillow-heif, max. 10 MB je Bild,
  Teilerfolg je Datei, JSON oder Redirect; Formular VOR dem ersten DB-Zugriff, Dateien ohne Sitzung, Zeilen in einer
  kurzen Schreibtransaktion), Löschen `POST …/fotos/{datei_id}/loeschen` durch Hochladenden/Innendienst/Admin
  (+ Projektierung [ANNAHME]) mit Chat-Notiz. Rechte `galerie.objektfotos_erlaubt` = Galerie-Rechte
  (`darf_hochladen`) ∪ `lead_v2.bearbeiten_erlaubt` (Außendienst am eigenen Lead). Zuordnung „Objekt“ auch beim
  Galerie-Upload und beim Einsortieren aus der Sammelbox (Vorgangs-/Projektakte, Montage-Backend, Erfassungs-
  Sammelbox); Erfassung (Sparten-Start, Übersicht) und Projektakte (Reiter Dokumente) zeigen die Objektfotos des
  jeweiligen Objekts nur an. **HEIC/HEIF wird bei jedem Galerie-Upload nach JPG gewandelt** (Befund: iPhone-Fotos
  lagen bisher nicht darstellbar in der Galerie). Tests `tests/test_lead_v6_objektfotos.py` (21; (q)).
- **Tests, Rollout-Vorbereitung, Doku (Phase 187, Orchestrator):** neue Testdateien `tests/test_lead_v6_taifun.py`
  (21), `test_lead_v6_kanaele.py` (14), `test_lead_v6_rechte.py` (10), `test_lead_v6_boards.py` (12),
  `test_lead_v6_objektfotos.py` (21); `tests/test_v27_scheduler.py` kennt den 17. Lauf. Angepasste Alt-Tests
  (Begründung in der Gesamtübersicht): Kanal „Standard“/Nav-Eintrag/„ohne Kanal“ (`test_lead_v11.py`,
  `test_lead_v3_anruf.py`, `test_lead_v3.py`, `test_lead_v3_boards.py` – K), HV-Gruppen statt Einzel-HV und AD am
  eigenen Lead ohne Lesesicht (`test_lead_v2_handelsvertreter.py`, `test_lead_v2_kartei.py`,
  `test_lead_v3_kartei.py`, `test_lead_v4.py`, `test_lead_v2_dashboard.py`, `test_lead_v3.py`,
  `test_lead_v3_phase120.py` – R). **Ergebnis der Rollout-Prüfung:** [ZAHLEN_FOLGEN]. Rollout-Vorbereitung
  `diagnose/v35/abschluss_tests.sh` (Server-Kopie, `migrate.py` zweimal, Testbenutzer, Rückweg-Probe v34-Code
  (Worktree 7327226) auf der v35-DB, Gesamtsuite, Abnahme, Voll-Crawl sechs Basisrollen + drei Varianten hell/dunkel,
  Smoke, Lasttest normal + schreibsturm). Doku: dieser Abschnitt, Zuordnungstabelle, Titelzeile, Zentrale Dateien,
  überholt-/ergänzt-Marker in v6/v9/v12/v23/v25/v29/v31/v33; `docs/taifun-kundenexport.md`, `docs/taifun/`,
  `docs/nach-dem-update-v35.md`, `docs/updates.md` (4d), `docs/betrieb.md` („Ergänzungen v35“);
  `config.VERSION = "v35"`.
