# Friondo Angebotstool – Projektkontext (v5)

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
- `konfigurator_logik_v4.xlsx` – Steuerdatei (ersetzt v3): Dachzentralen-Block
  D01–D05, geänderte Bedingungen A05/A06, Pos. 163 bei DG, SLS/ÜSS/APZ nur Protokoll,
  Summenblock mit Rabatt. 15 AMPEL-Gründe.
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
- SLS/ÜSS/APZ (E04–E06): reine Protokollfragen – Komponenten sind in Pos. 011
  enthalten; Pos. 149/150/153 bleiben ungenutzt im Artikelstamm.
- EK-Preise sind unter „Artikel bearbeiten" änderbar (Innendienst/Admin).
- **Löschen & Archiv (v5):** Benutzer sind löschbar, solange keine Vorgänge an
  ihnen hängen – sonst deaktivieren (Historie bleibt lesbar). Erfassungen sind
  löschbar (ID/Admin), außer ein Angebot ist verknüpft. Angebote: nur **Entwürfe**
  löschbar; versendete/abgelehnte werden **archiviert** (Aufbewahrungspflicht) und
  über den Filter „Archiv" erreichbar. Benutzer haben ein E-Mail-Feld (für CC).

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
