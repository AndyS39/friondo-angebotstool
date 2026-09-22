# Friondo-Tool – Modul „Projektierung": Gesamtkonzept (Stand 22.09.2026, Basis CLAUDE.md v10)

Dieses Dokument ist das Fundament für alle PLAN_PROJ-Dateien. Es hält den
Soll-Prozess, das Datenmodell, die Rollen, die Schnittstellen und die
Ausbaustufen fest. **Abschnitt 9 listet alle Annahmen, die ich ohne Rückfrage
selbst getroffen habe** – diese Liste geht Andreas nach V1 durch.

---

## 1. Ziel und Leitprinzipien

Das Modul bildet den Weg vom angenommenen Angebot bis zur Rechnungsfreigabe
ab und ersetzt die heutigen Insellösungen (Auftragsaufbereitung per Mail,
Teams, WhatsApp, Loops, Excel). Vier Prinzipien:

1. **Eine Projektakte als einziger Ort der Wahrheit.** Alles, was ein
   Beteiligter wissen muss, steht in der Akte – nicht in einer Mail.
2. **Null Abtipparbeit.** Alle Daten aus Erfassung und Angebot fließen
   automatisch ins Projekt. Mails an Subunternehmer, Bestelldateien und
   Steckbriefe werden aus der Akte erzeugt, nicht geschrieben.
3. **Jeder Schritt hat einen Verantwortlichen und eine Fälligkeit.**
   Prozesswissen liegt in pflegbaren **Aufgabenpaket-Vorlagen** (Parametrierung),
   nicht im Programmcode – wie beim Konfigurator: Antwort → Paket.
4. **Jeder sieht, was der andere macht.** Verlauf, Kommentare mit @Erwähnung,
   Benachrichtigungen, Startseite „Meine Aufgaben".

---

## 2. Soll-Prozesskette

| Nr. | Schritt | Verantwortlich | Im Tool |
|---|---|---|---|
| 0 | Angebot „Angenommen" (Tool oder TAIFUN) | Innendienst | Button **„Angebot → Projekt"** legt Projekt + Gewerk an oder hängt das Gewerk an ein offenes Projekt desselben Kunden. Auftragsaufbereitung per Mail entfällt. Projektierer wird benachrichtigt. |
| 1 | Feinplanung vor Ort (i. d. R. zusammen mit Heizlast; Heizlast liegt manchmal schon vor) | Feinplanungs-Monteur | Termin „Feinplanung" am Gewerk. **Feinplanungs-Erfassung** (zweiter Fragenkatalog, mobil, Antworten des Vertriebs vorbelegt und gegenzuprüfen), Fotos in Unterordner (Außengerät, Öltank, Zählerschrank …), Heizlast-Ergebnis (kW + Heizreport-PDF/Link). |
| 2 | Planung im Büro (Oberbegriff: Beschaffung, Subs, Anmeldungen, Elektroplanung, SpotDynamic/iMSys, Teams einplanen) | Projektierer + Elektroplaner | Aufgabenpakete werden aus den Feinplanungs-Antworten aktiviert. Buttons: **„Sub beauftragen"** (Mail mit Daten + Fotos), **„Material bei Collin bestellen"** (UGL-Datei / IDS), Anmeldungen als Aufgaben mit Wartestatus. |
| 3 | Montage geplant | Projektierer | Montagetermin(e) + Team(s) am Gewerk, Kunde bestätigt, Subs terminiert, Material-Liefertermin geprüft. Wächter: alle Pflichtaufgaben erledigt. |
| 4 | In Ausführung | Montageteams SHK/Elektro | **Montage-Backend** (mobil, reduziert): Projektsteckbrief, Dokumente/Fotos, Montagebericht, Inbetriebnahme-, Abnahmeprotokoll mit Kundenunterschrift (bestehende Vor-Ort-Signatur). |
| 5 | Abnahme offen / Rechnungsfreigabe | Projektierer | Prüft Protokolle, Restarbeiten, Reklamationen → **„Rechnung freigeben"** (Pflicht: Restarbeiten erfasst oder „keine"). Gewerk → Abgeschlossen. |
| 6 | Abrechnung & Nachlauf | Buchhaltung | Rechnung in TAIFUN (bleibt dort). Im Tool: Rechnungsdaten, OP-Liste, Zahlungseingang, Mahnstufen, Restarbeiten bis Erledigung (Ausbaustufe V4). |

Bei **Kombi-Aufträgen** (WP + PV + KL + WB) laufen die Schritte 1–5 **je Gewerk
getrennt** – auch zeitlich Monate auseinander –, aber in **einer** Projektakte.

---

## 3. Datenmodell

```
Vorgang (v10) ─┬─ Projekt (PR-JJNNNN, Projektleiter, Status abgeleitet)
       │     ├─ Gewerk WP  (Phase, Verantwortliche, Aufgaben, Termine, Feinplanung, Protokolle)
       │     ├─ Gewerk PV  (…)
       │     ├─ Gewerk KL / WB
       │     ├─ Auftrag je Gewerk = angenommenes Angebot (folgt Versionen .2/.3)
       │     ├─ Dokumente (Ordnerstruktur aus Vorlage, projekt- oder gewerkbezogen)
       │     ├─ Kommentare/Verlauf (append-only, @Erwähnung)
       │     ├─ Sub-Beauftragungen, Bestellungen
       │     └─ Rechnungen/OP (V4)
```

**Projekt** = Bauvorhaben, verankert am **Vorgang** aus v10 (Lead = Kundenanfrage,
bündelt bereits alle Sparten, Erfassungen, Angebote, Mails und den Notizen-Chat
der Vertriebsphase). Pro Vorgang höchstens ein offenes Projekt; Kunde und
Ausführungsadresse werden aus dem Vorgang übernommen. Die Vorgangsakte ist
damit die Akte „bis zur Unterschrift", die Projektakte die Akte „ab der
Unterschrift" – beide verlinkt. Nummernkreis **PR-<JJ><NNNN>** (Parametrierung, analog AN-C).

**Gewerk** = Ausführungseinheit je Sparte WP / PV / KL / WB. Trägt den
**Phasenstatus**, eigene Aufgaben, Termine, Feinplanung, Abnahme, Freigabe.
Entsteht aus genau einem angenommenen Angebot (Tool oder TAIFUN). Enthält ein
Angebot mehrere Sparten (TAIFUN-Kombi), erzeugt der Dialog je gewählter Sparte
ein Gewerk mit demselben Auftrag.

**Elektroplanung** ist kein eigenes Gewerk, sondern ein Aufgabenpaket, das bei
jedem WP-Gewerk automatisch aktiviert wird (Verantwortlicher: Rolle Elektroplaner).

**Auftragswert** je Gewerk: ursprünglich (erste angenommene Version) / aktuell
(neueste angenommene Version). Nachträge laufen über „Überarbeiten" → .2/.3.

**Projektstatus** (abgeleitet, nicht setzbar): Phase des am wenigsten
fortgeschrittenen **offenen** Gewerks; „Abgeschlossen", wenn alle Gewerke
abgeschlossen oder storniert sind.

### 3.1 Phasen je Gewerk (= die fünf vorhandenen Kacheln + zwei Endzustände)

| Phase | Bedeutung | Eintritt | Wächter (Übergang nach rechts) |
|---|---|---|---|
| **Feinplanung** | Auftragseingang bis Ende der Büroplanung (VOT-Feinplanung, Heizlast, Beschaffung, Subs, Anmeldungen). Fortschritt = Planungs-Ampel. | automatisch bei Anlage | alle Pflichtaufgaben der aktiven Pakete erledigt; Feinplanungs-Erfassung abgeschlossen (Override mit Begründung, protokolliert) |
| **Feinplanung abgeschlossen** | Planung fertig, wartet auf Terminierung / Material | manuell oder automatisch, wenn Wächter erfüllt | mindestens ein Montagetermin mit Team |
| **Montage geplant** | Termin steht, Kunde informiert | manuell | Montagebeginn (Team setzt „Montage gestartet" im Montage-Backend oder Projektierer manuell) |
| **In Ausführung** | Teams auf der Baustelle | – | Montagebericht + Inbetriebnahme + Abnahmeprotokoll vorhanden (V1: Häkchen „Montage fertig") |
| **Abnahme offen** | Fertigmeldung liegt vor, Rechnungsfreigabe steht aus | – | „Rechnung freigeben" (Restarbeiten-Pflichtfrage) |
| **Abgeschlossen** | freigegeben | – | – |
| **Storniert** | Pflichtgrund (Liste + Freitext); Angebot → Abgelehnt mit demselben Grund | jederzeit | – |

Rückwärts-Übergänge sind immer möglich (mit Begründung im Verlauf).

### 3.2 Planungs-Ampel (die „wie weit ist die Planung"-Anzeige auf der Kachel)

- Grundlage: Pflichtaufgaben aller aktiven Pakete des Gewerks.
- **Grün** = alle erledigt · **Gelb** = offen, aber keine überfällig · **Rot** =
  mindestens eine Aufgabe überfällig oder blockiert (Warten auf Dritte über Frist).
- Zusätzlich Prozentbalken „12 von 18 Pflichtaufgaben".

### 3.3 Aufgaben und Aufgabenpakete

- **Aufgabe:** Titel, Beschreibung, Gewerk (oder Projekt), Verantwortliche
  Rolle → Person, Fälligkeit, Status (offen / in Arbeit / wartet auf Dritte /
  erledigt / entfällt), Pflicht ja/nein, Reihenfolge, Blockiert-durch
  (optional), Kommentare, Anhänge.
- **Paket-Vorlage** (Parametrierung, Tabelle „Aufgabenpakete"): Name, Sparte,
  Schritte mit Rolle, Pflicht, Fälligkeit relativ („+3 Tage nach Aktivierung",
  „−14 Tage vor Montagetermin", „+5 Tage nach Feinplanung"), Wartet-auf-Dritte-Frist.
- **Aktivierungsregeln** (Tabelle „Paketregeln"): Sparte, Feinplanungs-Frage,
  Antwortwert → Paket. Beispiele: `WP, immer → Elektroplanung WP`;
  `WP, FP-A05 Dynamischer Tarif = Ja → SpotDynamic/iMSys`;
  `WP, FP-A12 Fundament nötig = Ja → Fundament GaLa-Bau`;
  `WP, FP-A20 Öltank = Ja → Öltank-Entsorgung`; `WP, FP-A08 Aufstellort = Garagendach → Dach/Statik`;
  `PV, immer → Netzanschlussbegehren + MaStR`.
- Pakete lassen sich manuell aktivieren/deaktivieren; Aufgaben manuell ergänzen.
- Startpakete für V1 (Inhalte in PLAN_PROJ_V1, von Andreas später verfeinert):
  Auftragseingang · Elektroplanung WP · Netzbetreiber-Anmeldung WP ·
  SpotDynamic/iMSys (7 Schritte) · Fundament GaLa-Bau · Öltank-Entsorgung ·
  Materiallift/Kran · Dach/Statik · Förderung (BzA/BnD) · PV-Netzanschluss ·
  Wallbox-Anmeldung · Montagevorbereitung · Abnahme & Freigabe.

### 3.4 Termine

Termin-Entität am Gewerk: Typ (Feinplanung / Montage / Abnahme / Sub /
Sonstige), Beginn, Ende, Team oder Person, Sub (optional), Kunde bestätigt
ja/nein, Notiz. Ansichten: am Gewerk, Terminübersicht (Woche/Monat, Filter
Team). Kalender-Abgleich nach Outlook über Graph (Team-Postfach) ab V2;
Kunden-Terminbestätigung per Mail ab V2.

### 3.5 Dokumente und Fotos

Ordner-Vorlage in der Parametrierung (Standard):
`01 Angebot & Erfassung` (automatisch: Angebots-PDF, Erfassungsprotokoll) ·
`02 Feinplanung & Heizlast` · `03 Fotos/Außengerät` · `03 Fotos/Innengerät &
Heizungsraum` · `03 Fotos/Öltank` · `03 Fotos/Zählerschrank` · `03 Fotos/Dach` ·
`03 Fotos/Alte Anlage` · `03 Fotos/Neue Anlage` · `03 Fotos/Mängel` ·
`04 Bestellungen & Subs` · `05 Montage & Protokolle` · `06 Rechnungen`.
Ordner sind projekt- oder gewerkbezogen; Uploads mobil (Kamera) und am PC;
Ablage `data/projekte/<PR-Nr>/…`. Sub-Mailvorlagen referenzieren Ordner
(„hänge alle Fotos aus 03 Fotos/Öltank an").

### 3.6 Kommunikation

- Kommentar-Verlauf am Projekt, am Gewerk und an jeder Aufgabe (append-only,
  @Erwähnung von Benutzern, Anhänge).
- Systemverlauf: Phasenwechsel, Zuweisungen, Freigaben, Mails, Bestellungen.
- Benachrichtigungen: Glocke im Tool (Zuweisung, @Erwähnung, Fälligkeit,
  Phasenwechsel eigener Gewerke); optional E-Mail sofort oder als Tagesdigest
  (je Benutzer einstellbar) über die Graph-Strecke.
- Startseite Projektierung: „Meine Aufgaben" (überfällig / heute / diese Woche /
  neu zugewiesen), „Meine Projekte".

---

## 4. Rollen

| Rolle | Sieht | Darf |
|---|---|---|
| **Admin** | alles | alles, Parametrierung der Pakete/Vorlagen/Subs |
| **Innendienst** | alles wie bisher + Projektierung lesend/schreibend | Angebot → Projekt, Projekte bearbeiten |
| **Projektierung** (neu: Projektierer, Feinplanungs-/Heizlast-Monteur, Elektroplaner) | Projektierungs-Bereich komplett, Angebote lesend (Kundenpreise, PDF), keine EK/DB (Admin kann je Benutzer „Kalkulation sichtbar" setzen), keine Angebotserstellung | Projekte, Gewerke, Aufgaben, Termine, Dokumente, Subs, Bestellungen, Feinplanungs-Erfassung, Rechnungsfreigabe |
| **Montage** (neu: Monteure SHK/Elektro) | nur **Montage-Backend**: zugewiesene Gewerke mit Termin, Projektsteckbrief, Dokumente, Formulare; keine Preise | Montagebericht, Inbetriebnahme, Abnahme, Fotos, Restarbeiten melden, „Montage gestartet/fertig" |
| **Außendienst** | am eigenen Vorgang: Reiter „Projekt" read-only (Phase, Termine, Ampel, Ansprechpartner) | nichts ändern; Kommentar am Projekt schreiben erlaubt |

**Demo-Phase:** Solange der Parameter `freigabe_modus = admin` steht (Standard
nach V1), ist das gesamte Modul ausschließlich für Admins sichtbar; die
Startportal-Karte „Projektierung" trägt das Badge „Demo · Coming soon", alle
anderen Rollen sehen weiterhin Null-Kacheln. Erst die Umstellung auf `alle`
schaltet die Rollentabelle oben scharf.

Benutzer können mehrere Rollen haben (z. B. Projektierung + Montage). Teams
(SHK-Team 1, Elektro-Team 2 …) sind eine neue Stammtabelle mit Mitgliedern.

---

## 5. Oberfläche

**Kanban-Board** (Startseite Projektierung): Spalten = Phasen (Feinplanung ·
Feinplanung abgeschlossen · Montage geplant · In Ausführung · Abnahme offen;
Abgeschlossen eingeklappt rechts; Storniert nur per Filter). **Karte = Projekt**
(Kombi-Aufträge bleiben zusammen); Spalte = abgeleiteter Projektstatus.
Auf der Karte: PR-Nr., Kunde, Ort, Projektleiter, Sparten-Chips **je Gewerk mit
eigener Phase und Ampel** („WP · Montage geplant · 🟢 14.10." / „PV · Feinplanung ·
🟡 7/12"), Gesamt-Auftragswert, nächster Termin, Anzahl überfälliger Aufgaben,
Kanal-Badge. Drag & Drop verschiebt bei Ein-Gewerk-Projekten das Gewerk; bei
Kombi-Projekten öffnet der Drop einen Dialog „Welches Gewerk?". Filter: Sparte
(schaltet auf Karte-je-Gewerk um), Projektleiter, Team, Kanal, PLZ, Zeitraum.
Startseiten-Kacheln zählen **Gewerke** je Phase („Montage geplant: 5 · 3 WP / 2 PV").

**Liste**: dieselben Gewerke als Tabelle mit Filtern, Summenzeile Auftragswert.

**Projektakte**: Kopf (Kunde, Adressen, Ansprechpartner, Vertriebler, Kanal,
Projektleiter, Gesamtwert, Status), darunter **Gewerk-Spalten nebeneinander**
(links WP, rechts PV …; bei einem Gewerk volle Breite) mit je: Phase + Ampel,
Aufgaben (gruppiert nach Paket), Termine, Feinplanung, Protokolle, Auftrag
(Angebot + Versionen). Reiter über alle Gewerke: Dokumente · Verlauf &
Kommentare · Subs & Bestellungen · Mail-Verlauf · Rechnungen (V4).

**Montage-Backend** (`/montage`, mobil): Heute/Diese Woche → Gewerk →
Steckbrief (Feinplanungs-Zusammenfassung, Besonderheiten, Ansprechpartner,
Anfahrt), Dokumente/Fotos, Formulare.

---

## 6. Schnittstellen (Rechercheergebnis)

| System | Befund | Umsetzung |
|---|---|---|
| **Collin KG (GC-Gruppe)** | GC bietet **IDS-Connect** (Warenkorb aus Software in GC Online Plus übergeben, Bestellung dort), **UGL** (Textdatei, 200 Byte/Satz, Satzarten KOP/ADR/POA/POZ/END, Lieferdatum Pflicht; Upload im Shop oder per FTP), OCI, DATANORM. Format ist vollständig dokumentiert. | V3: Button „Material bei Collin bestellen" erzeugt UGL-Bestelldatei (Anfrageart BE) aus der Stückliste des Gewerks + Lieferadresse; V1 der Bestellung = Datei-Download + Upload in GC Online Plus; danach IDS-Connect (Warenkorb-Push) sobald Zugang/Lieferanten-ID vorliegt. **Voraussetzung:** Artikelstamm um Collin-Artikelnummern und Stücklisten je Position erweitern (Paket-Positionen wie 045 müssen in Einzelartikel aufgelöst werden). Kundennummer bei Collin + IDS-Zugang anfordern. |
| **Heizreport** | Hilfethema „Grundlagen zur Nutzung der API-Schnittstelle" existiert (Business-Account); Doku nicht öffentlich abrufbar. Bosch-Partnerschaft. | V1: Heizlast-Felder (kW, Datum, Heizreport-Projekt-Link) + PDF-Upload. V4: Anbindung (Projekt anlegen, Ergebnis abrufen) nach Anforderung der API-Doku beim Heizreport-Support. |
| **SpotDynamic / SpotmyEnergy** | Partnerprogramm mit Installer-App, Endkunden-Angebotsstrecke, Logistik (Versandetiketten Altzähler), Netzbetreiber-Kommunikation durch SpotmyEnergy. **Keine öffentliche API.** | V1: Aufgabenpaket „SpotDynamic/iMSys" (Vorlage, 7 Schritte, anpassbar). V4: Prüfung API/Partnerportal-Anbindung nach Rückfrage beim Partnerbetreuer. |
| **Outlook-Kalender** | Graph ist vorhanden. | V2: Termine als Kalendereinträge in Team-Postfächern anlegen/aktualisieren. |
| **monday** | Rückspielung vorhanden. | V2: Deal-Status „Auftrag" bei Projektanlage, „Abgeschlossen" bei Freigabe (konfigurierbar wie bisher). |
| **TAIFUN** | keine API im Einsatz. | Rechnung bleibt in TAIFUN; Rechnungsdaten werden im Tool erfasst (V4). |

---

## 7. Ausbaustufen

| Stufe | Inhalt | Nutzen |
|---|---|---|
| **V1 – Fundament** | Projekt/Gewerk/Auftrag, Button „Angebot → Projekt", Nummernkreis, Kanban + Liste + Projektakte, Aufgaben + Paket-Vorlagen + Regeln (Parametrierung), Planungs-Ampel, Wächter, Termine (einfach), Dokumente/Fotos mit Ordnern, Kommentare/@Erwähnung/Benachrichtigung, Rollen Projektierung/Montage (Montage vorerst ohne eigenes Backend), Vertriebs-Lesesicht, Storno, Migration Altbestand, Startseiten-Kacheln live, Subunternehmer-Stamm | Zentralisierung sofort: Akte statt Mail, jeder sieht Aufgaben und Stand |
| **V2 – Feinplanung & Subs** | Feinplanungs-Erfassung mobil (Logik-Blätter FP-WP/PV/KL/WB, Vorbelegung aus Vertriebs-Erfassung, Gegencheck), Foto-Aufnahme in Ordner, Heizlast-Block, automatische Paket-Aktivierung aus Antworten, **„Sub beauftragen"** per Mail mit Platzhaltern + Fotos + Steckbrief-PDF, Kunden-Terminbestätigung per Mail, Outlook-Kalender, monday-Status | Vor-Ort-Planung im Tool, Subs per Klick |
| **V3 – Montage & Material** | Montage-Backend mobil (Steckbrief, Bericht, Inbetriebnahme, Abnahme mit Signatur, Restarbeiten), Materialbestellung Collin (Stücklisten, UGL, später IDS) | Baustelle und Beschaffung im Tool |
| **V4 – Abrechnung & APIs** | Rechnungsfreigabe-Workflow vollständig, Rechnungsdaten/OP/Mahnstufen/Zahlungseingang, Restarbeiten-Verfolgung, Heizreport-API, SpotmyEnergy-Anbindung, Statistik Projektierung (Durchlaufzeiten je Phase) | Überblick Zahlungen, letzte Insellösungen weg |

Nur ein Plan gleichzeitig in Umsetzung; Absprache mit dem Angebotstool-Chat.

---

## 8. Rollout-Regeln (unverändert)

Plan-Phasen werden global weitergezählt (v10 endete mit Phase 63; PLAN_PROJ_V1
umfasst Phasen 64–72). CLAUDE.md-Stand nach V1: v11.

Entwicklung lokal mit Test-DB → git push → update.bat auf dem Terminal-Server
(sichert, zieht, migriert idempotent per migrate.py, startet neu). CLAUDE.md und
konfigurator_logik_v5.xlsx sind Live-Master; Änderungen nur als Anweisung im
Plan. Neue Steuerdatei **projektierung_logik_v1.xlsx** (Pakete, Regeln,
Feinplanungs-Fragen, Sub-Mailvorlagen, Ordnerstruktur) – bewusst getrennt vom
Konfigurator, damit Projektierung und Angebotstool unabhängig gepflegt werden.

---

## 9. Selbst getroffene Annahmen (nach V1 gemeinsam prüfen)

1. **Karte = Projekt, Spalte = am wenigsten fortgeschrittenes offenes Gewerk.**
   Alternative wäre Karte = Gewerk; die Gewerk-Chips auf der Karte zeigen den
   Einzelstand, der Sparten-Filter schaltet auf Karte-je-Gewerk.
2. **Die fünf vorhandenen Kacheln bleiben die Phasen.** „Feinplanung" umfasst
   die gesamte Planung inkl. Beschaffung; der Fortschritt darin wird über die
   Planungs-Ampel sichtbar statt über zusätzliche Phasen.
3. **Rolle Projektierung sieht keine EK/DB**, außer Admin schaltet es je Benutzer
   frei. Kundenpreise und Angebots-PDF sind sichtbar (Sub-Mails und Bestellungen
   brauchen Positionen).
4. **Projektleiter** = Pflichtfeld bei Projektanlage (Dropdown Benutzer mit Rolle
   Projektierung, Vorbelegung: Parametrierung „Standard-Projektleiter").
   Feinplanungs-Monteur und Elektroplaner werden je Gewerk zugewiesen
   (Vorbelegung ebenfalls aus der Parametrierung).
5. **Rollenzuordnung der Paketschritte:** Projektierer, Elektroplaner,
   Feinplanung, Innendienst, Buchhaltung, Montage. Personen werden bei
   Aktivierung aus den Gewerk-Zuweisungen bzw. Standard-Benutzern je Rolle
   gefüllt und sind änderbar.
6. **Absender für Projekt-Mails** (Subs, Kunden-Terminbestätigung): neues
   Shared-Postfach `projektierung@friondo.de`, in der Parametrierung
   einstellbar, Fallback `angebot@friondo.de`. Antworten laufen im Mail-Verlauf
   des Projekts auf (Betreff-Anker `PR-…`).
7. **Storno** setzt das Gewerk auf „Storniert", das Angebot auf „Abgelehnt" mit
   demselben Grund; Auftragswert zählt nicht mehr. Ein storniertes Gewerk bleibt
   in der Akte sichtbar (durchgestrichen).
8. **Migration Altbestand:** Alle Angebote mit Status „Angenommen" ohne
   Projekt erhalten beim ersten Start nach Update automatisch Projekt + Gewerk
   in Phase „Feinplanung", Projektleiter = Standard-Projektleiter, Aufgaben-
   Paket „Auftragseingang" aktiv. Ihr sortiert einmalig per Drag & Drop.
9. **Feinplanungs-Fragen V2** starten mit meinem Entwurf (Dynamischer Tarif,
   WP-Zähler §14a, Aufstellort inkl. Garagendach, Fundament, Materiallift/Kran,
   Öltank, Zählerschrank-Zustand, Leitungswege, Parkplatz/Anfahrt, Gerüst,
   Dachzugang, Netzbetreiber, Zählernummer) und werden durch das TAIFUN-Formular
   ersetzt, sobald es vorliegt.
10. **Termine V1** sind eine einfache Liste ohne Kalender-Sync; Kunden-
    Bestätigung ist ein Häkchen. Mail-Bestätigung an den Kunden erst in V2.
11. **Montage-Rolle in V1** nutzt den bestehenden mobilen Bereich (wie
    Außendienst) mit der Sicht „Meine Einsätze" (Gewerke mit eigenem Termin,
    Steckbrief read-only, Foto-Upload, Häkchen „Montage gestartet / fertig").
    Formulare kommen in V3.
12. **Auftragswert** = Endbetrag brutto des Angebots (wie Deal-Wert an monday);
    netto als Tooltip.
13. **Wächter-Override** ist Projektierer/Innendienst/Admin erlaubt, immer mit
    Begründung, immer protokolliert – kein hartes Sperren.
14. **Sub-Mails V2** gehen mit PDF-Steckbrief (Kunde, Ausführungsadresse,
    Gerät/Positionen, relevante Antworten, Termin) + Fotos aus den zugeordneten
    Ordnern; die Vorlage je Sub-Typ liegt in der Parametrierung.
15. **Material-Bestellung Collin V3** benötigt Stücklisten je Angebotsposition
    und Collin-Artikelnummern – das ist Pflegeaufwand im Artikelstamm, den ihr
    einmalig leisten müsst; ohne diese Daten bleibt der Button ohne Funktion.
