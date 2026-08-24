# Friondo Angebotstool – Projektkontext (v7)

## Ziel
Zweistufiger Vertriebsprozess der Friondo GmbH: Außendienst erfasst mobil per
Fragenkatalog (gespeist aus monday-Leads mit Vor-Ort-Termin), Innendienst erzeugt,
prüft, rabattiert und versendet Angebote (PDF im Friondo-Layout, KfW-Förderung,
Deckungsbeitrag, E-Signatur). Läuft lokal/on-prem.

## Rollen & Navigation
- Rollen: **Admin** (Benutzer verwalten inkl. Namen ändern, alles sehen),
  **Innendienst** (alles außer Benutzerverwaltung), **Außendienst** (nur Leads VOT
  eigene + Erfassung; nie Preise/EK/DB/Rabatt).
- Startseite: Friondo-Logo oben links; nur drei Shortcuts **Leads VOT · Erfassungen ·
  Angebote**; alle weiteren Punkte im Dropdown „Menü" oben rechts; darunter
  Statistik-Kacheln: Offene Leads · Offene Erfassungen · Versendete Angebote.
- Menüpunkt „Konfiguration" heißt jetzt **„Parametrierung"** (Logik-/Preislisten-
  Import, monday-Mapping, Nummernkreis, Förderparameter-Ansicht).

## Zentrale Dateien
- `konfigurator_logik_v5.xlsx` – Steuerdatei (ersetzt v4): zusätzlich Frage A13
  „Leitungslänge Hauseinführung ↔ WP-Inneneinheit" (immer; Pos. 103 × [Eingabe − 5 m, nie unter 0] – 5 m stecken in Pos. 006),
  SLS/ÜSS/APZ-Fragen komplett entfernt. 15 AMPEL-Gründe.
- `Artikel-Preislisten/Angebotserstellung_Tool_mit_EK.xlsx`, `ANGEBOTSTEXTE.md`,
  `anlagen/`, `Layout - Logo/`, `foerderrechner-website.html` – unverändert.

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
- **Dachzentrale:** Bei alter Anlage im DG immer Pos. 163. D-Block steuert 141 bzw.
  139/140 × Meter. Fassadenleitung nur bei OG oder (DG und WP bleibt im DG);
  Erdleitung bei KG/EG oder (DG und WP zieht nach unten).
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
  Kachel „Individuell offen") → „Extern erledigt" → Erfassung „Erledigt (extern)"
  und Archiv. Das Protokoll-PDF ist der Übergabezettel für TAIFUN.
- **Externe Angebotseinträge:** „Extern erledigt" fragt TAIFUN-Angebotsnummer
  (optional, nachtragbar – Badge „Nummer fehlt"), Endbetrag brutto (Pflicht) und
  Datum ab und erzeugt einen Eintrag in der Angebotsliste mit Badge „TAIFUN":
  ohne PDF/Editor/Versand, aber mit monday-Rückspielung (Deal-Status + Deal-Wert),
  Verfolgung (Ampel/Wiedervorlage/Notizen) und Statistik. Die Statistik weist
  Tool-, TAIFUN- und Gesamt-Angebote getrennt aus.
- Fotos in der Erfassung: bewusst zurückgestellt (späteres Thema für alle Wege).

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
  Jeder Vorgang trägt zudem einen **Konfigurator-Typ** (aktuell „WP") als Unterbau
  für die späteren PV- und Klima-Konfiguratoren.
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
