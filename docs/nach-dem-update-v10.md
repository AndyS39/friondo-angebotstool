# Nach dem Update auf v10 – Checkliste & Hinweise

## ✅ Checkliste für den Innendienst (einmalig nach dem Update)

1. **Kombi-Vorlage texten/abnehmen**: Unter **Parametrierung → Kombi-Versand
   (v10)** stehen Betreff und Text der Kombi-Mail (Standard ist vorbelegt).
   Bitte den Wortlaut einmal fachlich abnehmen. Platzhalter:
   `{angebotsliste}` (je Angebot Sparte, Nummer, Endbetrag; bei WP zusätzlich
   der Eigenanteil nach Förderung – bewusst **keine Gesamtsumme**),
   `{angebotsnummern}`, `{briefanrede}`, `{vertriebler}`, `{absender}`.

2. **monday-Deal-Werte einmalig angleichen**: Der Deal-Wert ist ab v10 die
   **Vorgangssumme** (alle versendeten, nicht überholten, nicht abgelehnten
   Angebote der Kundenanfrage – Tool und TAIFUN). Bestandswerte werden NICHT
   automatisch überschrieben. Ablauf:
   - `venv\Scripts\python scripts\monday_deal_werte.py` → Trockenlauf,
     zeigt alle Vorgänge mit neuem Wert **ohne etwas zu schreiben**.
   - Liste sichten, dann `… --ausfuehren` → schreibt die Werte nach monday
     (Protokoll wie gewohnt am Angebot).

3. **Gewerkeübergreifende Artikel prüfen**: Unter **Parametrierung** ist die
   Liste mit `014, 015, 016, 017, 104, Z22, 152, Z23` vorbelegt (pflegbar).
   Bei Mehr-Sparten-Vorgängen erscheint in der Akte ein fachlicher Hinweis,
   wenn ein solcher Artikel in einem Tool-Angebot **voll** berechnet ist.

## 📣 Hinweise für das Team

### Der Vorgang ist jetzt das zentrale Objekt

Jeder Lead (bzw. jede Kundenanfrage) hat eine **Vorgangsakte**: Klick auf den
Kundennamen in Leads VOT, Erfassungs- oder Angebotsliste (oder Menü
**Vorgänge** mit Suche). Die Akte bündelt Sparten-Chips, alle Erfassungen,
alle Angebote (inkl. Versionen und TAIFUN), den Mail-Verlauf, die Verfolgung
und den **Notizen-Chat**.

### Verfolgung jetzt am Vorgang

- Es gibt **EINE Hot-Ampel und EINE Wiedervorlage je Kundenanfrage** – nicht
  mehr je Angebot. Gepflegt wird sie in der Akte oder im Angebots-Editor
  (der Block dort schreibt auf den Vorgang). Angenommen/Abgelehnt bleibt
  je Angebot.
- Die Einschätzung des Außendiensts (Erfassungs-Abschluss) setzt die
  Startwerte des Vorgangs; der Ersteller ist Verantwortlicher der
  Wiedervorlage.
- **Wiedervorlagen haben einen Verantwortlichen**: vom AD gesetzte erscheinen
  in seiner mobilen Sicht (neue Fälligkeits-Anzeige), die ID-Kachel zählt
  nur Innendienst-Wiedervorlagen. Der ID kann den Verantwortlichen umhängen.
- Der 90-Tage-Lauf respektiert eine zukünftige **Vorgangs**-Wiedervorlage
  für ALLE Angebote des Vorgangs.
- Bestand: je Vorgang wurden die heißeste Angebots-Ampel und die früheste
  zukünftige Wiedervorlage übernommen; alte Angebots-Notizen stehen als
  Alt-Einträge (mit Herkunftsvermerk) im Chat.

### Notizen-Chat-Regeln

- Chronologischer Chat je Vorgang, Eintrag automatisch mit
  „<Name> <TT.MM.JJ> <HH:MM> Uhr:" – **Einträge sind unveränderlich**
  (kein Bearbeiten, kein Löschen). Kurz und sachlich schreiben.
- Rechte: ID/Admin an allen Vorgängen, Außendienst an den eigenen (auch
  mobil). Ein roter Punkt in der Vorgangsliste zeigt neue Notizen seit dem
  letzten Öffnen.

### Kombi-Versand-Ablauf

1. In der Vorgangsakte die versandfertigen Angebote ankreuzen
   (Entwurf/Versand vorbereitet; **TAIFUN-Einträge nur mit hinterlegtem
   PDF** – Upload direkt am Eintrag, Übergangslösung).
2. „Gemeinsam versenden" → EIN Outlook-Entwurf mit allen Angebots-PDFs und
   den (deduplizierten) Broschüren; Profil-Regeln gelten (Enni-CC,
   SWD-Empfänger leer, Mehrfach-BCC).
3. Die Versand-Erkennung stellt alle enthaltenen Tool-Angebote auf
   „Versendet"; der Mail-Verlauf hängt an allen; der monday-Deal-Wert wird
   als Vorgangssumme geschrieben.
4. Das Tool warnt, wenn dieselbe Artikelnummer in mehreren Tool-Angeboten
   voll berechnet ist (TAIFUN-PDFs sind nicht prüfbar) – dann ggf. das
   **Alternativ-Kennzeichen** setzen: Position wird wie EP ausgewiesen,
   zählt nicht in Summe/KfW/DB und trägt im PDF automatisch den Vermerk
   „…ist im parallel vorliegenden <Angebot> enthalten…".
5. Der Einzelversand über das Angebot bleibt unverändert möglich.

### Außendienst-Ausbau

- „Meine Angebote": Suchfeld (Name, Ort, Angebotsnummer) + **Vollansicht**
  der eigenen Angebote (alle Positionen, Preise, Summen, Status, PDF –
  weiterhin ohne EK/DB).
- **AD-Gesamtrabatt**: Der AD kann den Rabatt selbst setzen, solange die
  DB-Ampel nicht auf Rot fällt (er sieht nur die Ampel-FARBE). Bei
  Entwürfen direkt; bei versendeten Angeboten entsteht automatisch
  Version .2 als Entwurf – bereit für Vor-Ort-Signatur oder ID-Versand.
  Würde die Ampel Rot: **Freigabe-Anfrage an den Innendienst** (Kachel
  „Rabatt-Freigaben offen" → genehmigen oder mit Kommentar ablehnen);
  alles steht im Notizen-Chat des Vorgangs.

### Kleinere Änderungen

- Statistik: neue Kennzahlen **Kombiquote** und **Auftragswert je Vorgang**
  sowie die Monatsübersicht **Auftragseingang** (angenommene Angebote,
  filterbar nach Vertriebler/Kanal/Sparte/Tool-TAIFUN).
- Angebots-PDF: Die **Erdleitung (Pos. 102)** steht jetzt im Block
  „Aufstellung der Außeneinheit und Hauseinführung" (bei Fundament/Konsole);
  die Fassadenleitung bleibt bei „Leitungen und Heizkreise". Preise
  unverändert.
- Der Button „+ Neues Angebot (Konfigurator)" heißt jetzt **„+ Neuer
  Vorgang (Erfassung)"** und führt durch den regulären Erfassungs-Ablauf –
  auch für Kunden ohne monday-Lead (Bugfix: dort fehlte zuvor der
  Absenden-Schritt).

## 📌 Hinweis an den Projektierungs-Chat

**„Vorgang" ist ab v10 das zentrale Objekt** des Tools: Ein Vorgang =
eine Kundenanfrage, ggf. mit mehreren Gewerken (WP/PV/KL/WB), Erfassungen,
Angeboten und einem Notizen-Chat. Künftige Projekte (Projektierung) docken
am Vorgang an – ein Vorgang kann mehrere Gewerke in die Ausführung bringen.
