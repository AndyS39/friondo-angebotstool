# Nach dem Update auf v36 – Angebotslayout v3 (HTML-Vorlagen + Browser-Druck) und Cloover-Finanzierung (PLAN_V22, Phasen 188–195)

Stand 16.10.2026. Rollout nur im Wartungsfenster Dienstag 22:30–23:30: Wartungsbanner setzen, `update.bat`, danach
`scripts\smoke.bat`. Rückweg `rollback.bat --nur-code` (alle Datenbankänderungen sind additiv, der v35-Code läuft auf
der v36-Datenbank – Rückweg-Probe im Durchlauf). **Teil A** (dieser Abschnitt, Agent A3) beschreibt das Angebots-PDF;
**Teil B** (Cloover-Finanzierung) ergänzt der Orchestrator unten.

## Teil A – Angebots-PDF (Layout v3)

### Für den Admin (Reihenfolge nach dem Update)

1. **Abhängigkeit Playwright:** `update.bat` installiert `playwright` aus `requirements.txt`. Edge ist auf dem Windows
   Server vorhanden (Kanal `msedge`) – dann ist nichts weiter nötig. Fehlt Edge und steht kein `PDF_BROWSER_PFAD` in
   der `.env`, lädt `update.bat` den Playwright-Chromium nach (`venv\Scripts\python -m playwright install chromium`,
   braucht Internet auf dem Server; schlägt das fehl, läuft das Tool mit dem alten Layout weiter – siehe Punkt 2).
2. **migrate.py** führt den Browser-Test aus und meldet entweder „Angebots-PDF: Browser-Test ok (msedge …, n ms) –
   Engine html (Layout v3) angelegt“ **oder** „Angebots-PDF: Browser-Druck nicht verfügbar (<Grund>) – Engine auf fpdf2
   gestellt“. Im zweiten Fall bleibt alles beim bisherigen Layout; Ursache klären (Punkt 3) und danach in der
   Parametrierung die Engine auf html stellen. Der zweite Lauf meldet nichts (idempotent).
3. **Browser unter dem Dienstkonto prüfen:** Der Dienst `FriondoAngebotstool` läuft als SYSTEM. Nach dem Start:
   Parametrierung → **Angebots-PDF** → „Test-PDF erzeugen“ (Demo-Angebot, Dauer in ms, Download) – das ist der
   Nachweis im Prozess des Dienstes. Zusätzlich außerhalb des Tools: `scripts\pdf-browser-pruefen.bat` (sucht
   Edge/Chrome, druckt ein Test-PDF nach `data\log\pdf-browser-test-<Zeit>.pdf`); unter SYSTEM mit
   `psexec -s -i 0 cmd /c "cd /d <Projekt> && scripts\pdf-browser-pruefen.bat"` oder als geplante Aufgabe unter SYSTEM
   (Befehle in `docs/angebots-pdf.md`, Abschnitt 6). Ergebnis bitte in diese Datei nachtragen (Browser, Version,
   Dauer).
4. **Engine-Schalter:** Parametrierung → Angebots-PDF → „HTML-Vorlagen + Browser-Druck (Layout v3)“ (Standard) oder
   „fpdf2 – bisheriges Layout (Rückfall)“. fpdf2 erzwingt das alte Layout auf allen Wegen ohne Hinweis; mit html
   fällt das Tool bei einem Druckfehler automatisch auf fpdf2 zurück und schreibt einen Eintrag ins Fehlerprotokoll
   (Fehlertyp „PDF“) – die Versand-Meldung nennt dann „PDF im alten Layout erzeugt (Browser-Druck fehlgeschlagen:
   <Grund>)“. Jede Änderung des Schalters steht im Änderungsprotokoll der Seite.
5. **Go-live-Checkliste** (Parametrierung): neuer Punkt 13 „Angebots-PDF: Browser-Druck grün“ = Engine html UND
   letzter Browser-Test ok (migrate.py oder „Test-PDF erzeugen“). Badge auf der Verteilerseite jetzt „n/13 grün“.
6. **/health und Betrieb:** `GET /health` liefert `pdf_engine`, `pdf_browser`, `pdf_letzte_druckdauer_ms`,
   `pdf_drucke`, `pdf_fehler`, `pdf_letzter_test_ok`; Warnung „Angebots-PDF: Browser-Druck fehlgeschlagen – Rückfall auf
   fpdf2 je Aufruf“, wenn die Engine html ist und der letzte Browser-Test rot war (Admin-Glocke über `betrieb-wache`).
   Betriebs-Seite: Kachel „Angebots-PDF“. Parametrierung → Betrieb zeigt die Antwortzeiten der PDF-Routen
   (Zielwert: WP-Angebot mit 25 Positionen ≤ 3 s; der erste Druck nach dem Start ist langsamer – Browser-Start,
   Schriften).
7. **Bilder/Schriften:** Titelbilder je Sparte, Logo, Award, Teamfoto, Zertifikats-Logos und die Schrift Nunito Sans
   liegen unter `app/static/pdf/` (Git). Austausch = Datei gleichen Namens ersetzen (Titelbilder 1600 px breit,
   JPEG ≤ 350 KB, Teamfoto ≤ 400 KB), kein Neustart; die Parametrierungsseite meldet fehlende Dateien. Vorgehen für
   ein neues Design: `docs/angebots-pdf.md`, Abschnitt 7.
8. **Temp-Ordner:** `data\tmp\pdf\` (HTML je Druck, sofort gelöscht; `angebots-pdf-test.pdf` = letztes Test-PDF).
   Dienstkonto SYSTEM braucht Schreibrecht dort und unter `data\angebote\` (wie bisher).

### Für das Team

- **Neues Angebotslayout je Sparte** (WP · PV · KL · WB) nach den Design-Vorlagen: Deckblatt mit Titelbild, Infokasten
  (Angebot-Nr., Datum, Gültig bis, Ansprechpartner) und Zertifikats-Leiste · „Ihr Angebot im Überblick“ mit Teamfoto ·
  Festpreisangebot (Positionen wie bisher: EP., bauseits, Alternativ-Kasten „im PV-Angebot“, Rabatte, Summenblock mit
  Endbetrag/Eigenanteil) · WP „Ihre KfW-Förderung“ · PV drei Wirtschaftlichkeitsseiten · „Auftragserteilung“ mit zwei
  Karten (Barkauf / Finanzierung bzw. Enni-/SWD-/Sparkasse-Text) · Vertragsbedingungen · Vollmacht nur bei iMSys/
  SpotDynamic (WB immer). Summen, KfW-Rechnung, Rabatt, Anschriften (v20) und Zahlungsbedingung (v30) sind unverändert –
  nur die Darstellung ist neu. Kopfzeile „Angebot-Nr. … · Kunde“ und „SEITE x VON y“ auf jeder Seite.
- **Alle Wege liefern das neue Layout:** Editor „PDF anzeigen“, Download, „Versand vorbereiten“, Kombi-Versand,
  Projektablage („Angebot → Projekt“), Nachfass-Mail mit Angebots-PDF, Signatur-Anzeige, Außendienst „Meine Angebote“
  (weiterhin ohne EK/DB). **Archiv:** versendete, angenommene, abgelehnte und überholte Angebote behalten ihr
  vorhandenes PDF unter `data\angebote\` unverändert (kein Neu-Rendern – egal welche Engine); nur Entwürfe und
  „Versand vorbereitet“ werden je Aufruf neu erzeugt; fehlt bei einem Altbestand die Datei, entsteht sie einmal im
  aktuellen Layout. „Überarbeiten“ erzeugt die neue Version im neuen Layout.
- **Ansprechpartner und Online-Beauftragung:** Im Infokasten steht der Außendienstler des Vorgangs, sonst der
  Innendienstler, der „Versand vorbereiten“ ausführt. Der Knopf „Jetzt online beauftragen ›“ erscheint nur, wenn die
  Fern-Signatur aktiv ist **und** `BASIS_URL` in der `.env` steht (öffentliche Adresse – eigenes Konzept); dann wird der
  Signatur-Link beim „Versand vorbereiten“ vor dem Druck ausgestellt und steht in PDF und Mail gleich. Bis dahin
  „Per E-Mail beauftragen ›“ (mailto an angebot@friondo.de mit Angebotsnummer).
- **HTML-Vorschau** (Innendienst/Admin): Knopf „HTML-Vorschau“ im Editor-Kopf bzw. `/angebote/<id>/pdf.html` – das
  Angebot als Webseite zum Gegenlesen ohne Druck (Druckvorschau des Browsers = Seitenaufteilung). Keine EK/DB darin.
- **Signatur:** Vor-Ort- und Fern-Signatur setzen das Signaturbild auf die Linie „Unterschrift des Auftraggebers“
  mit „<Name> · signiert am TT.MM.JJJJ HH:MM“; Ablage, Protokoll und Status „Angenommen“ wie bisher. Vorhandene
  signierte PDFs bleiben unverändert.
- **Hinweis in der Versand-Meldung:** Erscheint „PDF im alten Layout erzeugt (Browser-Druck fehlgeschlagen: …)“, ist
  das PDF trotzdem vollständig (bisheriges Layout) – bitte dem Admin melden (Parametrierung → Angebots-PDF).

### Ergebnis der Server-Prüfung (nach dem Rollout nachtragen)

| Datum | Konto | Browser / Version | Dauer Test-PDF | Ergebnis |
|---|---|---|---|---|
| Dev-PC 16.10.2026 | FRIONDO\a.scheelen (FR-WTS-02, Terminal-Server mit Fremdlast) | Edge 155.0.4283.45 (Kanal msedge), Playwright 1.64.0 | Demo-WP 7 Seiten, 1,8 MB: 5,3 s kalt (erster Druck), 2,9–3,4 s warm; PV 2,9 s · KL 2,2 s · WB 2,3 s; Probeseite warm 0,7 s; 4 parallel = 2 × 3 s (Semaphore) | ok |
| Server | SYSTEM | _offen_ | _offen_ | _offen_ |

## Teil B – Cloover-Finanzierung

### Für den Admin (Reihenfolge nach dem Update)

1. **Cloover-Key:** `CLOOVER_API_KEY=<Test-Key von Cloover>` in die `.env` (Dev-PC und Server), optional
   `CLOOVER_BASIS_URL` (leer = Test-URL); Dienst neu starten. Der Wert erscheint nirgends – Parametrierung → Cloover
   zeigt nur „Key gesetzt/fehlt“. **Ohne Key läuft Teil B im Modus „aus“** (keine Raten, keine Projekte, der Lauf
   `cloover-status` meldet „inaktiv“) – so ist der Stand nach dem Rollout, solange kein Key vorliegt.
2. **Modus:** Parametrierung → Cloover → `test` (Standard, solange die Basis-URL die Test-URL ist); `live` erst
   nach Live-URL und Live-Key von Cloover (mit Test-URL wird „live“ abgewiesen). Standard-Konto
   (`cloover_standard_email`, c.castro@friondo.de), Laufzeit 20 Jahre / Anzahlung 0 €, Optionen (Cash + Financing),
   Sparten (WP, PV, KL, WB) und Klima-Anlagentyp („Energetic Renovation“) dort prüfen; **Fußnote und
   Datenschutzsatz sind Entwürfe** (Textbausteine `cloover_fussnote`/`cloover_datenschutz`, Rückfragen B1/B7 –
   Wortlaut mit Cloover bzw. dem Datenschutzbeauftragten abstimmen).
3. **Verbindungstest:** Knopf „Verbindung testen“ → erwartet „Verbindung OK · Beispielrate 93,36 €/Monat
   (Test-Umgebung) · Wärmepumpe: Typ Heat pump akzeptiert · …“; „Key abgelehnt (HTTP 401)“ → Key prüfen; abgelehnte
   Typen (z. B. Klima) → Rückfrage B2, bis dahin rechnet das Tool die Rate über v1 (Gesamtbetrag).
4. **PDF-Ablage (für den persönlichen Finanzierungs-Link):** SharePoint-Site/Bibliothek „Cloover-Angebote“ anlegen,
   der Tool-App `Sites.Selected` (Write) auf diese Site geben, Freigabe „Jeder mit dem Link“ für Mandant und Site
   erlauben, Ablauf anonymer Links ≥ 180 Tage (`docs/graph-einrichtung.md` Abschnitt 8). Voraussetzung: Graph-Modus
   **anwendung** (Verbindungstest grün). Dann Parametrierung → Cloover → PDF-Ablage: Anbieter `sharepoint`, Site
   `friondo.sharepoint.com:/sites/<name>`, Ordner; **„Test-PDF ablegen und prüfen“** muss „Ablage OK“ melden (sonst
   bleibt es bei Rate ohne Link). Alternative ohne SharePoint: Anbieter `basis_url` mit öffentlicher HTTPS-Adresse in
   `BASIS_URL` (Konzept Erreichbarkeit); `keine` = Raten, aber keine Cloover-Projekte.
5. **Cloover-Konto je Innendienstler:** Benutzerverwaltung → Details → „Cloover-Konto (E-Mail)“ (optional) – Projekte
   laufen dann unter diesem Konto, sonst unter dem Standard-Konto.
6. **Betrieb:** Der Lauf `cloover-status` (stündlich, 18. Lauf) erscheint auf der Betriebs-Seite; fehlgeschlagene Aufrufe
   stehen in Parametrierung → Fehlerprotokoll, Fehlertyp „Cloover“ (ohne Key und Kundendaten). `/health` zeigt
   **18 Läufe**.
7. **Echtlauf gegen die Test-Umgebung (einmalig, von Hand, erst mit Key):** Demo-Angebot mit Friondo-Testadresse und
   -Telefon „Versand vorbereiten“ → Karte „Finanzierung (Cloover)“ zeigt Rate und Projekt, das PDF Karte 2 mit
   Knopf/QR; QR-Scan öffnet den Checkout; „Status jetzt abrufen“ liefert den Stand. Ergebnis (Projekt-ID, ohne Link)
   in `diagnose/v36/gesamtuebersicht.md` §10 nachtragen – auf dem Dev-PC war das ohne Key nicht möglich.

### Für das Team

- **Finanzierungskarte im Editor:** Unter der Kopfkarte steht bei Angeboten mit Profil Standard (WP/PV/KL/WB) die Karte
  „Finanzierung (Cloover)“: die Monatsrate wird automatisch vor jedem PDF und beim „Versand vorbereiten“ bei Cloover
  berechnet (Laufzeit 20 Jahre, Anzahlung 0 € aus der Parametrierung – je Angebot änderbar, nur im Entwurf/„Versand
  vorbereitet“). „Rate neu berechnen“ fragt sofort neu ab. Rot erscheinen „E-Mail des Kunden fehlt“, „Telefon fehlt“,
  „Firmenkunde – Cloover nur für Privatkunden“, „Ausführungsort unvollständig“ – dann gibt es keinen persönlichen
  Finanzierungs-Link (Rate bleibt). Enni/SWD/Sparkasse DU haben keine Karte (Hinweiszeile mit Grund).
- **Persönlicher Link:** Ein Cloover-Projekt (persönlicher Link + QR im PDF, Karte 2 der Auftragserteilung) entsteht
  beim „Versand vorbereiten“ nur, wenn Name, E-Mail, Telefon und Ausführungsort des Kunden vollständig sind, der Kunde
  Privatperson ist und die PDF-Ablage eingerichtet ist – nach dem Nachtragen „Projekt anlegen“ in der Karte. Ein
  zweites „Versand vorbereiten“ legt kein zweites Projekt an; „Überarbeiten“ (neue Version) schon. Ohne Link steht im
  PDF „Ihren persönlichen Finanzierungs-Link erhalten Sie von uns per E-Mail.“
- **Badges:** „Cloover: Vertrag unterschrieben (TT.MM.JJJJ)“ / „Cloover: Barzahlung gewählt“ kommen aus dem Status-Lauf
  (oder „Status jetzt abrufen“); der Angebotsstatus bleibt – „Angenommen“ setzt der Innendienst von Hand (Glocke
  erinnert Innendienst und Außendienst).
- **Häkchen „Finanzierung im PDF ausblenden“:** Karte 2, Box „Planbare Monatsraten“ und Fußnote entfallen im PDF,
  es wird kein Cloover-Projekt angelegt (z. B. Barzahler, die keine Datenweitergabe wünschen). Überarbeiten/
  Duplizieren übernehmen Laufzeit, Anzahlung und das Häkchen; die Rate wird neu berechnet.
- **Kombi-Versand:** ein Projekt je Kombi-Mail, derselbe Link in allen PDFs; jedes PDF zeigt seine eigene Rate und
  zusätzlich „Gesamtrate für alle Angebote dieser Mail: ab … € pro Monat“.
- **Außendienst:** sieht in „Meine Angebote“ die Rate (lesend), nie Knöpfe.
- **Mail-Vorlagen:** neue Platzhalter `{cloover_rate}` („ab 389,99 € pro Monat“), `{cloover_link}`,
  `{cloover_finanzierungsangebot}` – die bestehenden Vorlagen wurden nicht geändert; wer die Rate oder den Link in der
  Mail nennen will, trägt den Platzhalter in Parametrierung → E-Mail-Vorlagen ein.
- **Altes Layout (fpdf2-Rückfall):** statt der festen Beispielraten („ab 129 € / 250 €“) druckt der Nachtext die
  berechnete Rate; die Textblöcke tragen dafür den Platzhalter `[CLOOVER]` (Migration beim Update) – beim Bearbeiten
  der Nachtexte den Platzhalter stehen lassen. „Friondo WB Standard“ hat dafür einen neuen Nachtext A („Ihre
  Zahlungsoptionen bei Friondo“, Kopie des KL-Textes mit „Ihre Wallbox-Lösung“) – Entwurf fürs Gegenlesen.
