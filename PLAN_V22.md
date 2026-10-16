# Umsetzungsplan v22 – Teil A: Angebotslayout v3 (eigenes Layout je Sparte WP/PV/KL/WB, HTML-Vorlagen + Browser-Druck) · Teil B: Cloover-Finanzierung (berechnete Monatsrate je Angebot, persönlicher Abschluss-Link, Status-Rückmeldung)

> **Prüfvermerk 16.10.2026 (Claude Code, Vorprüfung der Plan-Kette):** Nummern **v36 / Phasen 188–195** gegen die
> Zuordnungstabelle in CLAUDE.md bestätigt (v34 = PLAN_V21, v35 = PLAN_LEAD_V6 – beide gebaut und gepusht; der
> Vorspann unten ist entsprechend angepasst). Ergänzungen von Andreas: Design-Vorlagen liegen anonymisiert unter
> `docs/design-v36/vorlage/`; Browser-Druck wird auf dem Dev-PC mit Edge geprüft, für den Server kommt
> `scripts\pdf-browser-pruefen.bat`; **der Cloover-Key kommt ausschließlich per `.env`** (Platzhalter in
> `.env.example`, Wert nie in Code, Doku oder Protokoll) – ohne Key läuft Teil B im Modus „aus“, alle Tests gemockt.

Voraussetzung: kein anderer Plan in Umsetzung (strangübergreifend). Stand 16.10.2026 (Vorprüfung der Plan-Kette): v34 (PLAN_V21) und v35 (PLAN_LEAD_V6) sind gebaut
und gepusht. **Dieser Plan kommt nach v35** und setzt auf dessen committetem Stand auf – er braucht
aus v33 die Graph-Anbindung als Anwendung (Phase 166) für die PDF-Ablage (Teil B) und aus v34 den
Wallbox-Konfigurator (Phase 179). Die PDF-Darstellung des Alternativ-Kennzeichens und die
Auslegungszeile aus PLAN_V21 Phase 180 werden hier im neuen Layout erneut umgesetzt (v34 hat den
Alternativ-Kasten bereits in fpdf2 gebaut – diese Fassung bleibt in der Rückfall-Engine). Vor der
Übergabe fragt der Planungs-Chat erneut ab, ob v33 bis v35 committet,
gepusht und auf dem Server sind. CLAUDE.md ist Live-Master im Projektordner
`C:\Users\a.scheelen\Tools\Angebotstool` (Git-Arbeitskopie). ALLE PHASEN
DIESES PLANS IN EINEM DURCHLAUF UMSETZEN (Reihenfolge einhalten – Teil A vor
Teil B, jede Checkbox nach Umsetzung und Test abhaken, am Ende
Gesamtübersicht mit Testergebnissen und offenen Punkten, fachliche
Rückfragen gebündelt). **Ein gemeinsamer Commit am Ende**, migrate.py
idempotent, **nur additive Migrationen** (v35-Code muss auf der
v36-Datenbank weiterlaufen, Rückweg `rollback.bat --nur-code`). **Kein git
push vor Freigabe.**

CLAUDE-Abschnitt: **„Neu in v36“** (geprüft 16.10.2026: v34 = PLAN_V21, v35 = PLAN_LEAD_V6 – v36 ist
die nächste freie Nummer der Zuordnungstabelle). Phasen **188 bis 195** (Teil A 188–191, Teil B
192–195; geprüft: 183–187 gehören zu PLAN_LEAD_V6, 188 ist die nächste freie Nummer). Die v27-Regeln gelten (`def`-Routen, **kein Netz- oder
Prozess-I/O mit offener Datenbanksitzung** – Browser-Druck und jeder
Cloover-Aufruf laufen außerhalb der Sitzung wie der Heizreport-Client v26,
Scheduler nur über `scheduler.registrieren`, Wächter-Test
`tests/test_v27_sitzungen.py` grün, Inventartabelle `docs/betrieb.md`), die
v30-Regeln für Oberflächen (Tokens Hell/Dunkel, `tojson | forceescape`).
**Geheimnisse:** API-Key und Live-Zugang stehen ausschließlich in der `.env`
(Dev-PC und Server) – nie in Plan, Doku, Protokoll, Fehlerprotokoll, Chat
oder Projektwissen. **Außendienst sieht weiterhin nie EK oder DB** – auch
nicht in der HTML-Vorschau des PDFs oder in der Finanzierungskarte.

Geltungsbereich: Angebotstool – **Angebots-PDF** (neue Engine
`app/pdf_html.py` + Vorlagen `app/templates/pdf/angebot/`, bisherige
`pdf_export.py` bleibt als Rückfall), Textblöcke/Profile
(`app/angebotsprofile.py`, `ANGEBOTSTEXTE.md`), Zahlungsbedingungen (nur
Darstellung), Signatur (`app/signaturen.py`, Einbettung), Wirtschaftlichkeit
PV (`wirtschaftlichkeit_pdf.py` → HTML-Vorlagen), Parametrierung → „Angebots-
PDF“, neuer Client `app/cloover_api.py`, PDF-Ablage `app/cloover_pdf_ablage.py`,
Angebots-Editor (Karte „Finanzierung“), „Versand vorbereiten“ und Kombi-
Versand, Vorgangsakte (Badge/Verlauf), Parametrierung → Cloover, ein
Scheduler-Lauf `cloover-status`. **Nicht berührt:** Konfiguratoren und
Rechenkerne, KfW-Rechnung (nur Darstellung), Angebotssummen, Lieferschein-,
Protokoll-, BzA- und Montageformular-PDFs (bleiben fpdf2), monday, Lead-
Management, Projektierung.

## Entscheidungen (Chat Angebotstool, 15./16.10.2026, Andreas)

- **Neues Angebotslayout je Sparte** nach den vier Claude-Design-Vorlagen
  (Wärmepumpe, PV-Anlage, Klimaanlage, Wallbox): Deckblatt mit Titelbild und
  Infokasten · „Ihr Angebot im Überblick“ mit Teamfoto · Festpreisangebot ·
  (WP) „Ihre KfW-Förderung“ · „Auftragserteilung“ mit zwei Karten ·
  Vertragsbedingungen · Vollmacht. Schrift Nunito Sans, Farben Dunkelblau
  #15153a / Friondo-Blau #4389c8 / Grau #6b6f85 / Linie #dfe3ee / Fläche
  #f1f6fc.
- **Weg A – HTML-Vorlagen + Browser-Druck:** Das Angebots-PDF wird aus
  Jinja2-HTML-Vorlagen mit einem Browser im Hintergrund (Edge/Chromium,
  gesteuert über Playwright) gedruckt; die fpdf2-Engine bleibt eine Version
  lang als Rückfall (`pdf_engine = fpdf2`).
- **„Jetzt online beauftragen“:** Knopf führt auf den Fern-Signatur-Link,
  sobald eine öffentliche HTTPS-Adresse (`BASIS_URL`) eingerichtet ist;
  bis dahin „Per E-Mail beauftragen“ (Mail an angebot@friondo.de mit
  Angebotsnummer). Die öffentliche Adresse ist Gegenstand eines eigenen
  Konzepts (Erreichbarkeit: Fern-Signatur, Cloover-PDF, Lead-Webhooks,
  Heizreport-Webhook, Diktat/Kamera) – nicht Teil dieses Plans.
- **PV mit 0 % USt** (§ 12 Abs. 3 UStG) – das Design zeigte 19 %, das wird
  korrigiert; die drei Wirtschaftlichkeitsseiten (v22) bleiben und werden
  ins neue Layout übertragen.
- **Vollmacht wie bisher** nur bei iMSys und/oder SpotDynamic (Positionen
  016/017) – nicht in jedem Angebot, auch wenn die Vorlage sie zeigt.
- **Enni, SWD, Sparkasse DU ohne Cloover:** keine Cloover-Karte, keine
  Rate, kein Cloover-Projekt; zweite Karte der Auftragserteilung trägt den
  jeweiligen Profiltext (Enni Contracting, Contracting, Finanzierung mit
  Sparkasse Duisburg).
- **Cloover (Teil B, 15.10.):** Rate für dieses Angebot aus der Cloover-API
  statt festem Beispiel; **persönlicher Abschluss-Link in jedem Angebot**
  (Cloover-Projekt beim „Versand vorbereiten“, Kundendaten + PDF gehen an
  Cloover); Laufzeit 20 Jahre, Innendienst kann Laufzeit/Anzahlung ändern;
  alle Sparten (WP mit/ohne Förderung, PV/KL/WB ohne Förderung), nur Profil
  Standard.
- **Nicht Teil dieses Plans:** öffentliche HTTPS-Adresse/Erreichbarkeit
  (Konzept), Lead-Übergabe an Cloover, automatische Annahme bei
  Vertragsunterschrift, Dachbelegungstool.

## Befund Design-Vorlagen (geprüft 16.10.2026)

Dateien (anonymisierte Kopien, Kundendaten durch Max Mustermann ersetzt):
`docs/design-v36/vorlage/angebot-waermepumpe.html`, `angebot-pv-anlage.html`,
`angebot-klimaanlage.html`, `angebot-wallbox.html` – Claude-Design-Export
(`doc-page`-Dokument, Vorlage-HTML im Script `__bundler/template`, Bilder/
Schriften im `__bundler/manifest`; im Browser öffnen oder entpacken). Je
Sparte ein eigenes Titelbild; Logo, Award-Badge („German Energy Awards
Winner 2026“ mit Link auf das Interview), fünf Zertifikats-Logos (SHK
Innungsfachbetrieb, E-Handwerk, bdsh, Fachbetrieb Wärmepumpe, Bosch Premium
Partner) und das Teamfoto sind in allen vier gleich. Fußzeile fünfspaltig
(Anschrift · Geschäftsführung · Kontakt · Bankverbindung · Steuerdaten),
Kopfzeile „Angebot-Nr. … · Kundenname“, Seitenzahl „Seite x von y“ oben
rechts. **Abweichungen vom Tool, die der Plan auflöst:** PV mit 19 % USt
(→ 0 %), Vollmacht überall (→ Regel), keine Wirtschaftlichkeitsseiten (→
übernehmen), Eventualposition als „0,00“ (→ „EP.“), feste Positionsnummern
im KfW-Text („Pos. 017“, „Pos. 008“ → dynamisch), Seitenzahl überlappt auf
dem Deckblatt den Award (→ Seitenzahl in die Randzone), Link
`friondo.de/beauftragung` (→ Fern-Signatur/E-Mail), Cloover-Link
`app.cloover.com/apply?partner=…` (→ `checkout_link` aus Teil B), Beispiel-
raten „ab 129 € / 250 €“ (→ berechnete Rate), keine Darstellung für
bauseits/Alternativ/Rabatt/Endbetrag/Ausführungsort/Lieferanschrift/
Versionen/Vermerke (→ Regeln in Phase 189). Titelbilder liegen als 3-MB-PNG
vor (→ JPEG ≤ 350 KB).

## Teil A – Angebotslayout v3

## Phase 188 – PDF-Engine: HTML-Vorlagen + Browser-Druck

- [x] **Renderer `app/pdf_html.py`:** `angebot_pdf(session, angebot, *,
      signatur=None, fassung="kunde") -> bytes` rendert die Jinja2-Vorlage zu
      HTML (alle Bilder/Schriften als `file://`-Pfade unter
      `app/static/pdf/`, keine externen Quellen), schreibt sie in einen
      Temp-Ordner und druckt mit **Playwright** (`playwright` in
      `requirements.txt`; Browser: `channel="msedge"` = auf Windows Server
      vorhandenes Edge, Rückfall Playwright-Chromium (`playwright install
      chromium` in `update.bat`, nur wenn Edge fehlt), Pfad überschreibbar
      per `.env PDF_BROWSER_PFAD`) über `page.pdf(format="A4",
      print_background=True, prefer_css_page_size=True,
      display_header_footer=True, header_template=…, footer_template=…)`.
      Kopfzeile über `header_template` auf **allen** Seiten (Angebot-Nr. ·
      Kundenname links, „SEITE <pageNumber> VON <totalPages>“ rechts, 7 pt,
      Grau, Systemschrift – Kopf-/Fußvorlagen laden keine Webfonts) in einer
      Randzone von 10 mm, in die kein Seiteninhalt reicht – damit überlappt
      die Seitenzahl auf dem Deckblatt nicht mehr den Award [ANNAHME: ein
      Druckdurchgang, Seitenzahl auch auf Seite 1]; Fußzeile fünfspaltig im
      Seiteninhalt als wiederholter Tabellenfuß (`<tfoot>`, Nunito)
      [ANNAHME]. **Ein Browser-Prozess je Dienst**
      (Start beim ersten PDF, Neustart bei Fehler), höchstens 2 parallele
      Drucke (Semaphore), Timeout 30 s je PDF, Zielzeit ≤ 3 s für ein
      WP-Angebot mit 25 Positionen; der Druck läuft **außerhalb der
      Datenbanksitzung** (Daten vorher in ein Kontext-Dict). Fehler →
      Fehlerprotokoll (Fehlertyp „PDF“) und Rückfall auf fpdf2 mit Hinweis
      in der Versand-Meldung „PDF im alten Layout erzeugt (Browser-Druck
      fehlgeschlagen: <Grund>)“.
- [x] **Engine-Schalter:** Parameter `pdf_engine` = `html` | `fpdf2`
      (Standard `html`, migrate.py setzt `fpdf2`, solange der Browser-Test
      beim Start fehlschlägt, und protokolliert das); Parametrierung →
      **Angebots-PDF** (`/parametrierung/angebots-pdf`, Admin): Browser
      gefunden (Pfad, Version), Knopf „Test-PDF erzeugen“ (Demo-Angebot,
      Dauer in ms), Schalter, Hinweis auf fehlende Schriften/Bilder; Go-live-
      Checkliste (v18) erhält den Prüfpunkt „Angebots-PDF: Browser-Druck
      grün“; `GET /health` meldet `pdf_engine` und letzte Druckdauer.
- [x] **Vorlagenbasis `app/templates/pdf/angebot/basis.html`:** CSS-Tokens
      aus dem Design (`--pdf-dunkel:#15153a; --pdf-blau:#4389c8;
      --pdf-grau:#6b6f85; --pdf-linie:#dfe3ee; --pdf-flaeche:#f1f6fc;
      --pdf-hell:#dbe9f7`), `@page { size: A4; margin: 0 }`, Innenabstand
      16 mm, Grundschrift 9,5 pt / 1,45, Seitenumbrüche über
      `break-before: page`, Tabellenzeilen `break-inside: avoid`, Nunito Sans
      400/600/700/800 als woff2 lokal (`app/static/pdf/fonts/nunito-sans/`,
      OFL-Lizenzdatei daneben; Quelle: die fünf woff2 aus dem Manifest der
      Vorlagen = Google-Fonts-Dateien), Bilder unter `app/static/pdf/bilder/`
      (`logo.png`, `award-2026.png`, `zert-shk.jpg`, `zert-ehandwerk.jpg`,
      `zert-bdsh.png`, `zert-fachbetrieb-wp.jpg`, `zert-bosch.png`,
      `team.jpg`, `titel-wp.jpg`, `titel-pv.jpg`, `titel-kl.jpg`,
      `titel-wb.jpg`; Titelbilder auf 1600 px Breite, JPEG 82 %, ≤ 350 KB;
      Teamfoto ≤ 400 KB). Ziel: Angebots-PDF ≤ 2,5 MB (Test).
- [x] **Sparten-Vorlagen** `wp.html`, `pv.html`, `kl.html`, `wb.html` erben
      von `basis.html` und setzen nur Titel/Untertitel/Titelbild/Spartenname;
      Seiten-Bausteine als Includes: `deckblatt.html`, `ueberblick.html`,
      `positionen.html`, `kfw.html`, `wirtschaftlichkeit.html` (3 Seiten),
      `auftrag.html`, `bedingungen.html`, `vollmacht.html`. Kontext kommt
      aus **einer** Funktion `pdf_kontext.fuer_angebot(session, angebot)`
      (Anschriften v20, Positionen mit Kennzeichen, Summen, Rabatt, KfW-
      Bausteine, Vermerke, Zahlungsbedingung, Textblöcke, Signatur, Cloover
      aus Teil B) – dieselbe Funktion versorgt die HTML-Vorschau (Phase 190).
      Lieferschein/Protokoll/BzA/Montageformulare bleiben fpdf2.
- [x] Tests `tests/test_v36_pdf_engine.py`: Druck läuft ohne offene Sitzung
      (Wächter), Semaphore/Timeout, Rückfall fpdf2 bei fehlendem Browser
      (gemockt), Dateigröße, Seitenzahl „SEITE 2 VON n“ auf Seite 2 (pypdf-
      Textprüfung), Schrift eingebettet (Fontname in der
      PDF), keine externen URLs im HTML.

## Phase 189 – Seitenaufbau und Datenbindung (alle Sparten)

Alle Wortlaute, die hier nicht stehen, kommen **wörtlich aus den
Vorlagendateien** (`docs/design-v36/vorlage/…`, Abschnitte Deckblatt ·
Anschreiben · Positionen · KfW-Förderung · Auftragserteilung · Bedingungen
· Vollmacht); Claude Code übernimmt sie 1:1 und listet in der
Gesamtübersicht jede Abweichung.

- [x] **Deckblatt** (Seitenzahl nur in der Randzone): Logo links, rechts Award-
      Badge mit Link (`https://www.germanenergyawards.com/interview/friondo-gmbh`,
      „Mehr dazu im Interview ›“); Titelbild je Sparte mit dunklem Verlauf;
      Eyebrow „ANGEBOT · WÄRMEPUMPE | PV-ANLAGE | KLIMAANLAGE | WALLBOX“,
      Titel/Untertitel wörtlich: WP „Ihr individuelles Wärmepumpen-Angebot
      zum Festpreis“ / „Effizienz, Komfort und zukunftssicher“; PV „Ihr
      individuelles PV-Angebot zum Festpreis“ / „Eigener Strom, mehr
      Unabhängigkeit“; KL „Ihr individuelles Klimaanlagen-Angebot zum
      Festpreis“ / „Kühlen, heizen und wohlfühlen“; WB „Ihr individuelles
      Wallbox-Angebot zum Festpreis“ / „Laden zu Hause – einfach und
      sicher“. Absenderzeile „Friondo GmbH · Arnold-Overbeck-Str. 63-65 ·
      47139 Duisburg“, **Empfängerblock nach v20** (Rechnungs-Name ersetzt
      bei Abweichung den Kundennamen, Zusatz als eigene Zeile), darunter in
      7 pt Grau „Ausführungsort: …“ nur bei abweichender Rechnungsadresse
      und „Lieferanschrift: …“ nur bei Abweichung vom Ausführungsort
      [ANNAHME: unter dem Empfängerblock]. Infokasten rechts: „Angebot-Nr.“,
      „Datum“, „Gültig bis“ (Datum + Bindefrist 30 Tage) [ANNAHME], „Ihr
      Ansprechpartner“ (AD des Vorgangs, Vorname Nachname; ohne AD:
      vorbereitender Innendienstler), „Telefon“ (Telefon des AD aus der
      Benutzerverwaltung; leer → Zeile entfällt), bei Versionen „Ersetzt
      Angebot AN-… vom TT.MM.JJJJ“, bei Kopien „Kopie von AN-…“ [ANNAHME: im
      Infokasten]. Leiste „Mitgliedschaften & Zertifizierungen“ mit den fünf
      Logos.
- [x] **„Ihr Angebot im Überblick“ + Teamfoto:** Briefanrede-Baustein
      ({briefanrede}), Einleitungsabsatz, zweispaltig „DARIN ENTHALTEN“
      (blaue Haken) und „WARUM FRIONDO?“ (dunkle Haken), Schlusssatz, „Ihr
      Friondo-Team“, darunter „DAS FRIONDO-TEAM“ mit Teamfoto (volle Breite).
      **Quelle bleibt der Vortext-Textblock des Profils/der Sparte**
      (Parametrierung → Textblöcke): der Renderer bildet die Markdown-
      Struktur ab – Absätze vor der ersten Liste → Einleitung, erste Liste
      → linke Spalte, Überschrift „Warum Friondo?“ + zweite Liste → rechte
      Spalte, Absätze danach → Schluss [ANNAHME]. Migration
      `migration_v36_texte` spielt die **Design-Wortlaute je Sparte** als
      neue Fassung der Vortext-Textblöcke ein (WP = heutiger Text; PV/KL/WB
      wörtlich aus den Vorlagen, inkl. Schlusssätze „… Lassen Sie uns
      gemeinsam Ihren eigenen Strom erzeugen!“ / „… für Ihr Wohlfühlklima
      sorgen!“ / „… Ihr Zuhause zur Ladestation machen!“), alte Fassungen
      bleiben als Historie (Textblock-Versionen). Enni/SWD/Sparkasse DU
      behalten ihre Vortexte.
- [x] **Festpreisangebot:** Titel „Festpreisangebot“ (Folgeseiten
      „Festpreisangebot (Fortsetzung)“ über wiederholten Tabellenkopf),
      rechts „Alle Preise in EUR, netto“, Spalten POS. · MENGE · EINH. ·
      BEZEICHNUNG · E-PREIS · G-PREIS, Gruppenüberschriften (editierbar wie
      seit v22) als fette Zwischenzeile. Artikeltext: erste Zeile fett,
      weitere Zeilen normal; Zeilen, die mit „-“, „•“ oder „– “ beginnen,
      werden Aufzählungspunkte „•“ [ANNAHME]; editierte Texte und Freitext-
      positionen wie heute. **Kennzeichen:** Eventualposition → G-Preis
      „EP.“ (E-Preis bleibt); bauseits → E-/G-Preis „bauseits“;
      **Alternativ** „in anderem Angebot enthalten“ → farbiger Hinweiskasten
      vor der ersten Alternativ-Position des Blocks („Die folgenden
      Positionen sind bereits in Ihrem Angebot <Nr> (<Sparte>) enthalten und
      werden dort berechnet.“, Fläche `--pdf-flaeche`, Rahmen `--pdf-blau`)
      und G-Preis „im PV-Angebot“ (bzw. Sparte), Zeile hellgrau (übernimmt v34 Phase 180); Positionsrabatt → Zeile „− Rabatt <x %|Betrag>“ unter
      dem Text, G-Preis nach Rabatt; Sonderpreis/manuell geändert ohne
      Kennzeichen. Auslegungszeile entfällt (V21). Vermerke (bedingte
      Vermerke v9, Alternativ-Vermerk v10) als Absatz „Hinweise“ vor dem
      Summenblock. **Summenblock** rechts: „Netto-Summe“ · „19,00 % USt.“
      bzw. bei 0 % „0,00 % USt. (§ 12 Abs. 3 UStG)“ · „Gesamt-Betrag“ (fett,
      Linie) · bei Gesamtrabatt „− Rabatt <Bezeichnung>“ und „= Endbetrag“ ·
      bei WP mit Förderblock „− voraussichtliche KfW-Förderung (<xx %>)“
      (blau) und dunkle Box „= Ihr Eigenanteil“ mit Hinweis „Unverbindliche
      Beispielrechnung – Details und Ablauf auf der nächsten Seite.“; ohne
      Förderblock steht der Gesamt-Betrag bzw. Endbetrag in der dunklen Box
      [ANNAHME]. Zahlen wie heute (Decimal, Cent, Rundung laut V21
      Rückfrage 7).
- [x] **„Ihre KfW-Förderung“** (nur WP, Förderblock nicht ausgeblendet):
      Eyebrow „ANTRAG: KFW 458 (WOHNGEBÄUDE)“, Titel, Untertitel „<F> % zahlt
      die KfW – <100−F> % bleiben für Sie“, Zeile „Angebotssumme <Endbetrag>
      (inkl. 19 % USt.)“ / „Förderfähig bis <Höchstkosten>“, **Balken** mit
      Segmenten Grund <%> · Klima <%> · Einkommen <%> · „Ihr Eigenanteil
      <%>“ (Breiten anteilig an der Angebotssumme; fehlende Bausteine
      entfallen), Liste Grundförderung / Klimageschwindigkeits-Bonus /
      Einkommensbonus mit Beträgen und MFH-Zusatz „(<x %> anteilig WE)“ (v9-
      Logik), „KfW-Zuschuss gesamt“, Kasten Angebotssumme − KfW-Zuschuss =
      Eigenanteil, Hinweistexte wörtlich (Deckel-Satz nur bei gedeckelten
      Boni; „Konditionen ab <Datum>“ = Angebotsdatum), „So läuft Ihre
      Förderung ab“ mit sechs Schritten wörtlich – „Pos. 017“ und „Pos.
      008“ werden durch die **tatsächlichen Positionsnummern** der BzA-
      bzw. Hydraulik-Position dieses Angebots ersetzt, fehlt die Position,
      entfällt der Klammerzusatz –, Boxen „GUT ZU WISSEN“ und „DAS BRAUCHEN
      SIE FÜR DEN ANTRAG“ wörtlich, KfW-Wortmarke rechts oben
      (`kfw.svg`, Verwendung wie heute im Förderblock). Manuell
      überschriebene Förderung (v8) wird wie heute ohne Kennzeichen
      gedruckt; Förderblock ausgeblendet → Seite entfällt, Summenblock ohne
      Förderzeilen.
- [x] **Wirtschaftlichkeit PV** (drei Seiten, nur PV, nicht ausgeblendet):
      Inhalte und Rechenkern unverändert (v22), Darstellung als HTML-Vorlagen
      nach `docs/wirtschaftlichkeit-mockup/seite1–3.html`, Schrift Nunito
      statt Poppins, Farben auf die PDF-Tokens gezogen; Platz: nach dem
      Festpreisangebot, vor der Auftragserteilung. `wirtschaftlichkeit_pdf.py`
      bleibt nur für den fpdf2-Rückfall. Kontrollwerte
      `test_wirtschaftlichkeit_v22.py` unverändert.
- [x] **„Auftragserteilung“:** Einleitungssatz wörtlich, **Karte 1
      „BARKAUF – Online beauftragen“** mit Kurzsatz aus der gewählten
      Zahlungsbedingung (erste Zeile des Textes [ANNAHME]) und Knopf: mit
      `BASIS_URL` und aktiver Fern-Signatur → „Jetzt online beauftragen ›“
      auf den Fern-Signatur-Link des Angebots (Token wie Modul v4), sonst
      „Per E-Mail beauftragen ›“ (`mailto:angebot@friondo.de?subject=Auftrag
      <Angebotsnummer>`); **Karte 2** je Profil: Standard → „FINANZIERUNG MIT
      CLOOVER – Online beauftragen & finanzieren“ mit Rate/Laufzeit/Knopf
      „Finanzierung abschließen ›“ (Teil B füllt; ohne Rate: Karte mit Text
      „Monatsrate auf Anfrage“ und ohne Knopf), Enni → „ENNI CONTRACTING“
      mit dem heutigen Enni-Text, SWD → „CONTRACTING“ mit dem SWD-Text,
      Sparkasse DU → „FINANZIERUNG MIT SPARKASSE DUISBURG“ mit dem
      Sparkasse-Text (Texte aus den bestehenden Nachtext-A-Textblöcken,
      ohne Rate, ohne Knopf). Block „Finanzierung mit Cloover – Saubere
      Energie. Faire Raten. Maximale Freiheit.“ mit den vier Boxen (Sofort
      starten · Planbare Monatsraten · Maximale Flexibilität · Ihre
      Vorteile) nur bei Standard; die Box „Planbare Monatsraten“ zeigt die
      berechnete Rate aus Teil B (nicht mehr „ab 129 €“), Fußnote aus Teil
      B. „Beauftragung per Post“ wörtlich; bei WP zusätzlich „Aufschiebende
      Bedingung“ und „Voraussichtliches Datum der Umsetzung: ____“ (heutiger
      Nachtext C WP); Unterschriftszeile „Ort, Datum“ / „Unterschrift des
      Auftraggebers“ – hier wird die **Vor-Ort-Signatur** eingebettet
      (Bild, Name, Zeitstempel, siehe Phase 190).
- [x] **„Vertragsbedingungen“:** Abschnitte aus den Nachtext-Textblöcken B/C
      (`###`-Überschriften → blaue Zwischenüberschriften): Haftungsbegrenzung
      · Rücktrittsrecht im Zusammenhang mit Technischer Feinplanung ·
      Zahlung (= `{zahlungsbedingungen}`, v30) · WP „Hinweis zur KfW-
      Förderung“ · KL „Hinweis zur Kältetechnik“ (v24) · Schlusskasten
      (Bindefrist, AGB-/Datenschutz-Links klickbar, Zusicherung, „Mit
      freundlichen Grüßen / Ihr Friondo-Team“). Die Design-Wortlaute sind
      mit den heutigen Textblöcken identisch (geprüft); Abweichungen meldet
      Claude Code.
- [x] **Vollmacht** (Regel unverändert: nur bei aktiver Position 016 und/oder
      017; in keinem KL-Angebot ohne diese Positionen): Text wörtlich, Kasten
      „ANGABEN ZUR VERBRAUCHSSTELLE“ **vorbelegt** mit Name (Kunde),
      Adresse (Ausführungsort), Telefon, E-Mail (leer → Linie), Geburtsdatum
      leer; Kasten „BITTE ANKREUZEN“ mit drei Kästchen; SEPA-Block mit vier
      Linien; drei Unterschriftslinien.
- [x] **Kopf-/Fußzeile:** Kopf auf jeder Seite „Angebot-Nr. <Nr> ·
      <Kundenname>“ und „SEITE x VON y“ (Randzone); Fuß auf jeder Seite fünfspaltig wörtlich wie das
      Design (Anschrift · Geschäftsführung · Kontakt · Bankverbindung ·
      Steuerdaten) – Inhalte aus den bestehenden Firmen-Konstanten.
- [x] Tests `tests/test_v36_layout.py` (HTML-Kontext und gerendertes HTML,
      dazu je Sparte ein PDF-Text-Vergleich): Empfängerblock-Varianten (v20-
      Fälle), EP/bauseits/Alternativ/Rabatt/Endbetrag/Förderzeilen, 0 %-Zeile
      PV, KfW-Seite nur mit Förderblock, dynamische Positionsnummern,
      Vollmacht-Regel, Karte 2 je Profil, Knopf-Variante ohne `BASIS_URL`,
      Wirtschaftlichkeitsseiten nur PV, Kontrollwerte der Summen unverändert
      (Netto 30.245,43 €; KL Fall A/B; PV-Fälle; WB Fälle A–D aus V21).

## Phase 190 – Einbindung: Vorschau, Versand, Signatur, Rückfall

- [x] **Alle PDF-Wege** nutzen `pdf_html.angebot_pdf`: Editor-Vorschau,
      Download, „Versand vorbereiten“, Kombi-Versand, Archiv/Ablage unter
      `data/angebote/`, Fern-Signatur-Anzeige, Außendienst „Meine Angebote“
      (ohne EK/DB – unverändert, der Kontext enthält keine EK-Felder). Neue
      Route **`GET /angebote/<id>/pdf.html`** (ID/Admin): dieselbe Vorlage
      als HTML im Browser (Design-Abnahme ohne Druck, Druckvorschau über
      `@media print`).
- [x] **Vor-Ort-Signatur:** `signaturen.py` erzeugt das signierte PDF durch
      **erneutes Rendern** mit `signatur={bild_data_url, name, zeitstempel,
      geraet}` – das Signaturbild sitzt auf der Linie „Unterschrift des
      Auftraggebers“, darunter „<Name> · signiert am TT.MM.JJJJ HH:MM“; Ablage
      `data/angebote/signiert/` und Signaturprotokoll unverändert; Status
      „Angenommen“ wie heute. Bestehende signierte PDFs bleiben unverändert.
      Fern-Signatur (Modul v4) rendert ebenso – Link nur mit `BASIS_URL`.
- [x] **Rückfall und Bestand:** `pdf_engine = fpdf2` erzeugt weiterhin das
      alte Layout (alle Routen); bereits erzeugte PDFs versendeter Angebote
      werden **nicht** neu erzeugt (Archiv bleibt); „Überarbeiten“ erzeugt
      die neue Version im neuen Layout. Versand-Meldung nennt bei Rückfall
      den Grund.
- [x] **Doku/Texte:** `ANGEBOTSTEXTE.md` neu gegliedert – Abschnitt 11
      „Layout v3 (v36)“ mit Seitenfolge je Sparte, Kennzeichen-Regeln,
      Zuordnung Textblock → Seite; Abschnitte 1–10 als Quelle der Wortlaute
      gekennzeichnet. `docs/design-v36/` mit Abnahme-PDFs je Sparte (Demo-
      Daten) und Screenshots Editor-Vorschau.
- [x] Tests `tests/test_v36_einbindung.py`: alle Routen liefern PDF mit
      neuer Engine, HTML-Vorschau nur ID/Admin (AD 403, kein EK im HTML),
      Signatur-Rendering (Bild und Zeile im PDF-Text), Rückfall-Schalter,
      Kombi-Versand mit zwei PDFs im neuen Layout.

## Phase 191 – Abnahme Teil A

- [x] **Abnahme-PDFs** `docs/design-v36/abnahme-wp.pdf` (WP mit Förderung,
      Rabatt, einer EP-Position, Vollmacht), `abnahme-pv.pdf` (0 %, drei
      Wirtschaftlichkeitsseiten, Vollmacht über 017), `abnahme-kl.pdf` (ohne
      Vollmacht), `abnahme-wb.pdf` (Fall B aus V21), `abnahme-enni.pdf` (WP
      Enni: Karte 2 Contracting, keine Cloover-Boxen), `abnahme-alternativ.pdf`
      (WP mit Alternativ-Kasten), `abnahme-signiert.pdf` (mit Demo-Signatur)
      – Demo-Daten, keine Kundendaten. Sichtvergleich mit den Vorlagen,
      Abweichungsliste in der Gesamtübersicht.
- [x] **Laufzeit:** 20 PDFs nacheinander ≤ 3 s im Mittel, 4 parallel ohne
      Fehler (Semaphore greift), Browser-Prozess nach Absturz neu gestartet
      (Test mit gekilltem Prozess); Lasttest-Profil `normal` mit PDF-
      Erzeugung im Modell (`docs/lasttest-v27.md` ergänzen).

## Teil B – Cloover-Finanzierung

## Befund Cloover Partners API (Test-Umgebung, geprüft 15.10.2026)

Dokumentation: `https://partners-api-530331765008.europe-west3.run.app/api-docs/`
(Swagger, OpenAPI 1.0.0 „Cloover Partners API“). Authentifizierung: Header
`X-API-Key`. Alle Anfragen tragen `userEmail` = der Friondo-Benutzer, unter
dessen Cloover-Konto das Projekt geführt wird (Test: c.castro@friondo.de).
Test-Key liegt bei Andreas (nur `.env`). Endpunkte:

| Endpunkt | Zweck | Eingabe | Antwort |
|---|---|---|---|
| `POST /api/price-calculator` | Rate aus Gesamtbetrag | `totalCostOfInstallation` (brutto), `userEmail`, `durationInYears`, `downPayment`, `currency: EUR` | `monthlyPayment` (ungerundet, z. B. 93,3582…), `currency` |
| `POST /api/price-calculator/v2` | Rate aus Anlagen-Positionen (empfohlen) | `userEmail`, `country: Germany`, `projectAssets[]` je `{type: Heat pump | Solar | Battery | Wallbox | Energetic Renovation, priceInfo{price (NETTO), vatPercentage, subsidy, currency}, capacity}`, `durationInYears` 1–25, `downPayment`, `inflateTransactionFee` | `monthlyPayment`, `monthlyPaymentAfterSubsidies` (gerundet auf Cent), `currency` |
| `POST /api/projects` | Cloover-Projekt anlegen → persönlicher Abschluss-Link | `userEmail`, `customer{firstName, lastName, email, phone, type: Individual}` (alle Pflicht), `projectAddress{street, city, postalCode, country}`, `projectAssets[]` wie v2, `financingDuration{start, end}` (Jahre), `financingOption[]` aus `Cash | Financing | ClooverPay`, **`offerPDF[]` = öffentlich abrufbare URL(s) des Angebots-PDFs (Pflicht)**, `inflateTransactionFee` | HTTP 201 `{checkout_link, project_id, financial_offer}` |
| `GET /api/projects/{id}` | Status | – | `{id, status, primary_signed_contract, secondary_signed_contract, contract_signed_date, financing_option_chosen}` |
| `POST /api/projects/leads` | Leads an Cloover übergeben | `userEmail`, `leads[]` (Kunde + Adresse) | – (nicht Teil dieses Plans) |
| `/api/project/create`, `/api/project/leads` | veraltet (307) | – | – |

Kontrollaufrufe gegen die Test-Umgebung (15.10.2026, Werte können sich
ändern – Tests mocken HTTP): 10.000 € brutto, Anzahlung 2.000 €, 10 Jahre →
**93,36 €/Monat**; 30.000 € brutto, 0 € Anzahlung, 15 Jahre → **273,16 €/
Monat**; v2 Wärmepumpe `price` 35.992,06 (netto), 19 % USt, `subsidy`
16.500, 15 Jahre → **389,99 € ohne / 242,70 € mit Förderung**. Daraus
abgeleitet: `price` in v2 ist der **Nettobetrag**, Cloover rechnet die USt
selbst dazu (389,99 ÷ 273,16 × 30.000 = 42.830 € = 35.992,06 × 1,19);
`monthlyPaymentAfterSubsidies` behandelt die Förderung als spätere
Sondertilgung; implizierter Nominalzins der Test-Umgebung ≈ 7,2 % p. a.
(**nur Test**); `inflateTransactionFee: true` liefert HTTP 400
„inflateTransactionFee cannot be set to true for this organization“ → immer
`false`. Für Klimaanlagen gibt es keinen Anlagentyp (Rückfrage B2).

## Phase 192 – Cloover-Client, Konfiguration, Verbindungstest

- [x] **`.env` und Konfiguration:** `CLOOVER_API_KEY` (leer = Modul aus),
      `CLOOVER_BASIS_URL` (Standard Test-URL
      `https://partners-api-530331765008.europe-west3.run.app`; Live-URL
      trägt Andreas nach Zulieferung von Cloover ein), `.env.example`
      ergänzen. Parametrierung → neue Seite **Cloover** (`/parametrierung/
      cloover`, Admin; Karte „Angebotstool“ der Verteilerseite): `cloover_modus`
      = `aus` | `test` | `live` (Standard `test`, solange die Basis-URL die
      Test-URL ist; `live` nur mit Live-URL – sonst Fehlermeldung beim
      Speichern), Anzeige „Key gesetzt/fehlt“ (nie der Wert),
      `cloover_standard_email` (Cloover-Konto für Projekte, Standard
      c.castro@friondo.de [bestätigt für Test]), `cloover_laufzeit_jahre` 20,
      `cloover_anzahlung_eur` 0, `cloover_optionen` (Mehrfachauswahl aus
      Cash/Financing/ClooverPay, Standard Cash + Financing [ANNAHME, Rückfrage
      3]), `cloover_laufzeit_min/_max` für `financingDuration` (1/20
      [ANNAHME]), `cloover_sparten` (Standard WP, PV, KL, WB), `cloover_kl_typ`
      (Anlagentyp für Klima, Standard „Energetic Renovation“ [ANNAHME,
      Rückfrage B2]), Texte (Phase 193) und PDF-Ablage (Phase 194). Je Benutzer
      (Benutzerverwaltung, Innendienst/Admin) optional `benutzer.cloover_email`
      – hat der vorbereitende Innendienstler ein Cloover-Konto, läuft das
      Projekt unter ihm, sonst unter dem Standard-Konto [ANNAHME].
      Änderungen ins Protokoll `cloover_protokoll` (letzte 30, Key nur als
      gesetzt/entfernt).
- [x] **Client `app/cloover_api.py`** (Vorbild `heizreport_api.py`):
      `konfiguriert()`, `rate_berechnen(assets, laufzeit, anzahlung,
      user_email)` (v2; Fallback v1 mit `totalCostOfInstallation` = Endbetrag
      brutto, wenn v2 HTTP 4xx wegen Anlagentyp liefert), `projekt_anlegen(
      kunde, adresse, assets, laufzeit_von_bis, optionen, pdf_urls,
      user_email)` → `{projekt_id, checkout_link, financial_offer}`,
      `projekt_status(projekt_id)`, `verbindung_testen()`. JSON, Timeout 20 s,
      `X-API-Key` aus `.env`, nie geloggt; Fehlerblock `{message, error}` →
      Nutzer-Meldung „Cloover: <message>“; 401 „Cloover: API-Key abgelehnt“,
      422 „Cloover: Eingabe abgelehnt (<message>)“, 5xx/Timeout „Cloover
      nicht erreichbar – später erneut versuchen“; jeder Fehler ins
      Fehlerprotokoll (Fehlertyp „Cloover“, ohne Header/Key, Körper ohne
      Kundendaten – nur Feldnamen). HTTP-Nahtstelle `_roh_anfrage` (in Tests
      gemockt). Rundung: `monthlyPayment` kaufmännisch auf Cent.
- [x] **Anlagen aus dem Angebot (`cloover_api.assets_fuer(angebot)`):** je
      Angebot genau ein Asset (Kombi: eines je Angebot): WP → `Heat pump`,
      `capacity` = Leistungsklasse kW aus dem Steckbrief/Paket; PV → `Solar`,
      `capacity` = kWp aus `pv_json` [ANNAHME: Speicher nicht als eigenes
      `Battery`-Asset – Rate hängt nur vom Preis ab]; KL → `cloover_kl_typ`,
      `capacity` = Σ Kühllast kW; WB → `Wallbox`, `capacity` 11. `price` =
      **Endbetrag ÷ (1 + USt-Satz)** (Netto nach Gesamtrabatt, Positionsrabatte
      und bauseits/EP/Alternativ sind in den Summen bereits berücksichtigt),
      `vatPercentage` = USt-Satz des Angebots (19 bzw. 0), `subsidy` =
      Förderbetrag aus `kfw_json` (WP; ohne Förderblock oder bei
      „Förderblock ausgeblendet“ = 0), `currency` EUR, `inflateTransactionFee`
      immer `false`. Kontrollwert: WP Endbetrag 42.830,55 €, Förderung
      16.500,00 € → `price` 35.992.06, `vatPercentage` 19, `subsidy` 16500.
- [x] **Verbindungstest** (`POST /parametrierung/cloover/test`):
      `rate_berechnen` mit 10.000 € brutto, 2.000 € Anzahlung, 10 Jahre über
      v1 → „Verbindung OK · Beispielrate 93,36 €/Monat (Test-Umgebung)“
      bzw. „Cloover erreichbar, aber Key abgelehnt (HTTP 401)“; zusätzlich
      v2-Probe mit einem Asset je aktiver Sparte und Meldung je Typ („Klima:
      Typ Energetic Renovation akzeptiert“ / „abgelehnt: <message>“).
- [x] Tests `tests/test_v36_cloover_api.py`: Body v2 wörtlich (Netto-Preis,
      USt, subsidy), v1-Fallback, Rundung 93,3582 → 93,36, Fehlerblöcke,
      Fehlerprotokoll ohne Key, Modus `aus` = keine Aufrufe, Parametrierungs-
      Seite ohne Key-Wert.

## Phase 193 – Rate im Angebot (Karte „Finanzierung mit Cloover“, Editor-Karte)

- [x] **Speicherung:** Spalte `angebote.cloover_json` (additiv) mit
      `{laufzeit_jahre, anzahlung_cent, rate_ohne_cent, rate_mit_cent,
      endbetrag_cent, foerderung_cent, ust_satz, stand, quelle: v2|v1,
      fehler, projekt_id, checkout_link, financial_offer, pdf_url, status,
      status_stand, ausgeblendet}`; Überarbeiten/Duplizieren/Kopieren
      übernehmen nur Laufzeit/Anzahlung/`ausgeblendet` (Rate und Projekt
      werden neu ermittelt – neue Version = neuer Endbetrag).
- [x] **Berechnung** (`cloover.rate_aktualisieren(angebot_id)`, außerhalb der
      Sitzung, `_speichern`-Muster beim Schreiben): automatisch beim
      „Versand vorbereiten“, beim Kombi-Versand und vor jeder PDF-Erzeugung,
      wenn `stand` fehlt oder Endbetrag/Förderung/USt/Laufzeit/Anzahlung vom
      gespeicherten Stand abweichen; manuell über den Knopf „Rate neu
      berechnen“. Schlägt der Aufruf fehl, bleibt die letzte Rate mit
      `stand` stehen (PDF druckt „Stand TT.MM.JJJJ“); gab es noch nie eine
      Rate, zeigt die Karte „Monatsrate auf Anfrage“ ohne Zahlen und die Versand-Meldung nennt „Cloover-Rate nicht
      verfügbar: <Grund>“. Keine Rate bei Modus `aus`, bei den Profilen Enni/SWD/Sparkasse DU,
      bei Sparten außerhalb `cloover_sparten`, bei `ausgeblendet`.
- [x] **Editor-Karte „Finanzierung (Cloover)“** unter der Kopfkarte
      (Innendienst/Admin; AD lesend ohne Knöpfe): Laufzeit (1–25, Standard
      aus Parametrierung), Anzahlung €, Rate ohne Förderung, Rate mit
      Förderung (nur WP mit Förderbetrag > 0), Stand, Quelle, Häkchen
      **„Finanzierung im PDF ausblenden“** (`ausgeblendet`, Route `POST
      /angebote/<id>/cloover`, wie `wirtschaftlichkeit_ausblenden`), Knopf
      „Rate neu berechnen“, Block „Cloover-Projekt“ (Phase 194: Status, Link
      kopieren, Finanzierungsangebot öffnen, „Projekt anlegen“ bei fehlendem
      Projekt). Hinweise rot: „E-Mail des Kunden fehlt“, „Telefon fehlt“,
      „Firmenkunde – Cloover nur für Privatkunden“ (Phase 194).
- [x] **Rate im neuen Layout** (Seite „Auftragserteilung“, Teil A Phase
      189, nur Profil Standard): **Karte 2** „FINANZIERUNG MIT CLOOVER –
      Online beauftragen & finanzieren“ zeigt „ab <Rate ohne Förderung> € /
      Monat*“ (bei WP mit Förderung stattdessen die Rate **mit** Förderung
      und darunter klein „ohne Förderung ab <Rate> €“ [ANNAHME]), „Laufzeit
      <n> Jahre · Ihre Finanzierungsanfrage ist bereits angelegt – nur noch
      bestätigen.“ (zweiter Halbsatz nur mit `checkout_link`, sonst
      „Laufzeit <n> Jahre“) und den Knopf aus Phase 194; die Box „Planbare
      Monatsraten“ im Cloover-Block trägt wörtlich:

      **Planbare Monatsraten – Ihre Rate für dieses Angebot:**
      - **ab 242,70 € pro Monat mit Förderung\*** (nur WP mit Förderung)
      - **ab 389,99 € pro Monat ohne Förderung**

      Für den fpdf2-Rückfall gilt dasselbe als Platzhalter **`[CLOOVER]`** in
      den Nachtexten A Standard/Sparkasse DU (Migration
      `migriere_cloover_platzhalter` ersetzt dort den Absatz „Planbare
      Monatsraten – Zum Beispiel: … Oder ab 250 € pro Monat ohne Förderung“
      samt Fußnote; WB erhält für den Rückfall Nachtext A als Kopie des
      KL-Textes mit „Ihre Wallbox-Lösung“ [ANNAHME]).

      Fußnote am Seitenende, wörtlich: „\*Unverbindliche Beispielrechnung
      unseres Finanzierungspartners Cloover auf Basis des Endbetrags dieses
      Angebots von 42.830,55 €, einer Laufzeit von 20 Jahren und 0,00 €
      Anzahlung; ‚mit Förderung‘ berücksichtigt die voraussichtliche
      Förderung von 16.500,00 € als Sondertilgung nach Auszahlung. Stand
      15.10.2026. Verbindliche Konditionen, Sollzins und effektiver
      Jahreszins ergeben sich aus dem Finanzierungsangebot von Cloover.“
      Ohne Förderung entfällt die erste Zeile und der Halbsatz „‚mit
      Förderung‘ …“; mit Anzahlung > 0 steht der Betrag; ohne Rate (Fehler)
      bleibt der Absatz weg. Der Pflichtangaben-Wortlaut ist bis zur
      Rückfrage B1 (Cloover/PAngV) ein Entwurf und in der Parametrierung als
      Textbaustein `cloover_fussnote` editierbar (Platzhalter {endbetrag},
      {laufzeit}, {anzahlung}, {foerderung}, {stand}).
- [x] **Mail-Platzhalter** `{cloover_rate}` („ab 389,99 € pro Monat“ bzw.
      leer) und `{cloover_link}` (Phase 194) in allen Angebots- und
      Kombi-Vorlagen verfügbar; Vorlagen-Vorschau zeigt sie; bestehende
      Vorlagen werden nicht automatisch geändert (Team-Hinweis).
- [x] Tests `tests/test_v36_rate.py`: Block wörtlich für WP mit/ohne
      Förderung, PV 0 %, KL, WB; Enni/SWD/Sparkasse DU ohne Cloover-Karte; `ausgeblendet`;
      Fehlerfall ohne Zahlen; Neuberechnung bei geändertem Endbetrag;
      Platzhalter; AD-Sicht lesend.

## Phase 194 – Persönlicher Abschluss-Link: PDF-Ablage, Cloover-Projekt, QR-Code, Status

- [x] **PDF-Ablage `app/cloover_pdf_ablage.py`** (Cloover braucht eine
      öffentlich abrufbare URL des Angebots-PDFs; das Tool läuft nur im
      VPN): Anbieter-Schnittstelle `ablegen(datei, name) -> url`,
      `ersetzen(url, datei)`, `pruefen(url)` mit zwei Anbietern –
      **`sharepoint`** (Standard): Upload über Graph als Anwendung (v33) in
      eine eigene SharePoint-Bibliothek (Parameter `cloover_sharepoint_site`,
      `cloover_sharepoint_ordner`, Berechtigung `Sites.Selected` nur für diese
      Site), danach anonymer Lese-Link (`createLink` type `view`, scope
      `anonymous`, Ablauf 180 Tage [ANNAHME]) und Download-URL (`?download=1`),
      `pruefen` = HEAD ohne Anmeldung muss `application/pdf` liefern;
      **`basis_url`**: Token-Route `GET /oeffentlich/cloover/<token>.pdf`
      unter `BASIS_URL` (v27-Vorbereitung, nur wenn eine öffentliche HTTPS-
      Adresse existiert; Token 32 Zeichen, Ablauf 180 Tage, kein Login,
      keine Verzeichnisliste). Parameter `cloover_pdf_ablage` = `sharepoint`
      | `basis_url` | `keine` (bei `keine` oder Prüf-Fehler: Rate ja, Projekt
      nein, Hinweis „Cloover-Link nicht möglich: PDF-Ablage nicht
      eingerichtet“). Verbindungstest „Test-PDF ablegen und prüfen“ in der
      Parametrierung. Ablage-Datei trägt den Angebotsnamen ohne Kundennamen
      (`AN-C-<Nr>-<Zufall>.pdf`). Rückfrage B4 (Cloover: anderer Upload-Weg).
- [x] **Projekt anlegen beim „Versand vorbereiten“** (und im Kombi-Versand;
      Reihenfolge innerhalb der bestehenden Versandroute, Netz-I/O außerhalb
      der Sitzung): (1) Voraussetzungen prüfen – Modus ≠ `aus`, Sparte
      zugelassen, Profil = Standard, nicht `ausgeblendet`, Kunde Privatperson
      (kein Großkunde/Firmenname [ANNAHME: `kunden.firma` leer]), E-Mail und
      Telefon des Kunden vorhanden (E.164 wie Lead-Modul), Ausführungsort mit
      Straße/PLZ/Ort, PDF-Ablage eingerichtet – fehlt etwas: Angebot ohne
      Link (Rate bleibt), Meldung „Cloover-Link nicht möglich: <Grund>“, rot
      in der Editor-Karte; (2) Rate aktualisieren (Phase 193); (3) **PDF-
      Fassung A** ohne Link/QR erzeugen und ablegen; (4) `projekt_anlegen`
      mit `financingDuration{start: cloover_laufzeit_min, end: _max}`,
      `financingOption` aus `cloover_optionen`, `offerPDF: [url]`; HTTP 201 →
      `projekt_id`, `checkout_link`, `financial_offer` in `cloover_json`,
      Verlauf „Cloover-Projekt <id> angelegt“, Notiz im Vorgangs-Chat;
      Fehler → Angebot ohne Link, Meldung, Fehlerprotokoll, Knopf „Projekt
      anlegen“ in der Editor-Karte zum Nachholen; (5) **PDF-Fassung B** mit
      Link und QR erzeugen = das Angebots-PDF für Kunde/Mail/Archiv, die
      abgelegte Datei wird durch Fassung B ersetzt (`ersetzen`, gleiche
      URL) [ANNAHME]. Nicht idempotent: zweites „Versand vorbereiten“
      desselben Angebots legt **kein** zweites Projekt an (Projekt-ID
      vorhanden → nur PDF neu); „Überarbeiten“ (neue Version) legt ein
      neues Projekt an, das alte bleibt bei Cloover stehen und wird im
      Verlauf vermerkt (Rückfrage B5: Storno-Weg bei Cloover). **Kombi-
      Versand:** EIN Projekt je Kombi-Mail mit allen Angeboten als Assets,
      derselbe Link in allen PDFs; jedes PDF zeigt seine eigene Rate und
      zusätzlich „Gesamtrate für alle Angebote dieser Mail: ab … €“
      [ANNAHME, Rückfrage B6].
- [x] **Link im PDF** (Karte 2 der Auftragserteilung, nur mit
      `checkout_link`): Knopf „Finanzierung abschließen ›“ verlinkt auf den
      `checkout_link`, daneben ein **QR-Code** (Bibliothek `qrcode` als SVG
      im HTML, 22 × 22 mm, Fehlerkorrektur M; im fpdf2-Rückfall mit
      Rechtecken gezeichnet) und darunter in 7 pt der Link als Kurzform; ohne
      `checkout_link` statt des Knopfes der Satz „Ihren persönlichen
      Finanzierungs-Link erhalten Sie von uns per E-Mail.“ Unter dem Cloover-
      Block der Satz „Prüfung und Zusage erfolgen direkt bei Cloover; Friondo
      erhält eine Rückmeldung über den Stand.“ und der
      Datenschutzsatz (Textbaustein `cloover_datenschutz`, Entwurf:
      „Zur Bereitstellung Ihres persönlichen Finanzierungs-Links haben wir
      Ihre Kontaktdaten, die Adresse des Vorhabens und dieses Angebot an
      unseren Finanzierungspartner Cloover übermittelt. Hinweise zum
      Datenschutz: https://friondo.de/Datenschutz“ – Wortlaut mit
      Datenschutzbeauftragtem abstimmen, Rückfrage B7). `financial_offer`
      wird nicht gedruckt, sondern in der Editor-Karte und als Mail-
      Platzhalter `{cloover_finanzierungsangebot}` angeboten.
- [x] **Status-Abruf:** Scheduler-Lauf `cloover-status` alle 60 Minuten
      (`scheduler.registrieren`, `db.kurz()` je Angebot, höchstens 50 je
      Lauf): für Angebote mit `projekt_id`, Status Versendet/Versand
      vorbereitet/Angenommen, nicht überholt/abgelehnt, Projekt jünger als
      180 Tage → `projekt_status`; Änderung von `status`,
      `primary_signed_contract`, `financing_option_chosen` → `cloover_json`,
      Verlauf „Cloover: <status>“; bei `primary_signed_contract = true` →
      Badge **„Cloover: Vertrag unterschrieben (TT.MM.JJJJ)“** in Editor,
      Angebotsliste und Vorgangsakte, Notiz im Vorgangs-Chat, Glocke an den
      vorbereitenden Innendienstler und den AD des Vorgangs (art
      `cloover`, ohne Mail), Vorschlag „Angebot auf Angenommen setzen?“
      (manuell, keine Automatik); `financing_option_chosen = Cash` → Badge
      „Cloover: Barzahlung gewählt“. Knopf „Status jetzt abrufen“ in der
      Editor-Karte. Statistik: Kennzahl „Cloover-Verträge“ (Anzahl/Summe
      Endbetrag im Zeitraum) im Reiter Angebote [ANNAHME]. Unbekannte
      `status`-Werte werden roh angezeigt (Rückfrage B8: Statusliste).
- [x] Tests `tests/test_v36_projekt.py` (HTTP und Ablage gemockt): Body
      `POST /api/projects` wörtlich (Kunde, Adresse, Asset, Laufzeit 1–20,
      Optionen, PDF-URL), Voraussetzungen je Grund, kein Doppelprojekt,
      Überarbeiten = neues Projekt, Kombi = ein Projekt mit n Assets,
      Fassung A/B (Fassung B enthält Link + QR, Fassung A nicht), Status-
      Lauf mit Badge/Glocke/Notiz, Datei ohne Kundennamen, Token-Route ohne
      Login nur mit gültigem Token (404 sonst), Key nie im Fehlerprotokoll.


## Phase 195 – Tests, Rollout-Vorbereitung, Doku, CLAUDE.md v36 (Teil A + B)

- [x] **Tests gesamt:** `test_v36_pdf_engine.py`, `test_v36_layout.py`,
      *(Stand 16.10.2026: v36-Tests und Nachbarn auf der migrierten Kopie grün. Kettenende 17.10.2026: Gesamtsuite
      1859 bestanden / 7 übersprungen / 4 Mitternachts- bzw. Umgebungs-Fehler ohne Codefehler, Wiederholung 4/4 grün, Wächter v27/v30/v33 grün – `diagnose/v36/gesamtuebersicht.md` §10; Cloover-Echtlauf
      offen, kein Key auf dem Dev-PC (§9 Nr. 11).)*
      `test_v36_einbindung.py`, `test_v36_cloover_api.py`, `test_v36_rate.py`,
      `test_v36_projekt.py`; angepasste Alt-Tests (PDF-Textprüfungen der
      Regressionstests auf die neue Engine umgestellt – Summen und Pflicht-
      sätze bleiben, Layoutzeilen ändern sich; Nachtext-Wortlaute; Versand-
      Meldungen; `test_wirtschaftlichkeit_v22.py` nur Darstellung) mit
      Begründung; `pytest tests -q` grün, Wächter v27 (Scheduler-Lauf
      `cloover-status` und Browser-Prozess im Inventar), Token-Wächter v30
      grün; HTTP in allen Cloover-Tests gemockt, kein Netzzugriff; der
      Browser-Druck läuft in den Tests echt (Edge/Chromium auf dem Dev-PC),
      in CI-losen Umgebungen über eine Markierung überspringbar.
      **Echtlauf Cloover gegen die Test-Umgebung** (einmalig, von Hand,
      Demo-Kunde mit Friondo-Testadresse und -Telefon): Rate, Projektanlage,
      QR-Scan öffnet den Checkout, Statusabruf; Ergebnis in die
      Gesamtübersicht (Projekt-ID, ohne Link).
- [x] **Rollout-Vorbereitung** nach Grundregel: Server-DB-Kopie nach
      *(EINE Rollout-Vorbereitung am Ende der Plan-Kette v36–v38, erledigt 16./17.10.2026 – Ergebnis in
      `diagnose/v36/gesamtuebersicht.md` §10: migrate ×2 (2. Lauf ohne Änderung), Rückweg v33-/v37-Code je 24/24, Abnahme 93/93, Voll-Crawl 16 Läufe 0 Abstürze, Smoke 8/8, Lasttest schreibsturm 190/190, normal 0 × 5xx / 0 locked – p95 Listen/Akten 2,3 s, Terminvorschläge 11,7 s und Angebots-PDF 4,2 s über den Zielwerten (Rückfragen 7 und 18 R7).)*
      diagnose\, migrate.py zweimal (additiv: Parameter `pdf_engine`,
      Textblock-Fassungen v36, `angebote.cloover_json`,
      `benutzer.cloover_email`, Cloover-Parameter, Textbausteine,
      Platzhalter-Migration der Nachtexte mit Protokoll), Rückweg-Probe
      v35-Code auf v36-DB, Voll-Crawl (admin, innendienst, aussendienst) inkl.
      PDF-Routen aller Sparten, Abnahmeskript, Smoke (Angebots-PDF < 3 s),
      Lasttest `normal` mit PDF-Erzeugung und `cloover-status` im Modell,
      Abnahme-PDFs aus Phase 191 plus `docs/cloover/abnahme-<Sparte>-<Nr>.pdf`
      (Karte 2 mit Rate und Test-Link/QR), Screenshots Editor-Karte und
      Parametrierungs-Seiten hell/dunkel nach `docs/design-v36/`. **Server:**
      Edge-Pfad prüfen (`scripts\pdf-browser-pruefen.bat`: findet Edge/Chrome,
      druckt ein Test-PDF unter dem Dienstkonto SYSTEM, meldet Dauer),
      Ergebnis in `docs/nach-dem-update-v36.md`.
- [x] **Doku:** CLAUDE.md Abschnitt „Neu in v36 – Angebotslayout v3
      (HTML-Vorlagen + Browser-Druck) und Cloover-Finanzierung (abgestimmt
      15./16.10.2026)“ nach „Neu in v35“, Zuordnungstabelle `| v36 |
      PLAN_V22.md | 188–195 |`, Titelzeile „(v36)“; in „Unverändert aus v2“
      (PDF nach Referenz AN250096, fpdf2), v2/v9/v22/v24 (Nachtext-Aufbau,
      festes Raten-Beispiel, Wirtschaftlichkeit mit fpdf2/Poppins) als
      *überholt – siehe v36* markieren; „Zentrale Dateien“ um
      `app/templates/pdf/angebot/`, `app/static/pdf/`, `docs/design-v36/
      vorlage/`; „Fachliche Regeln“ um „Angebots-PDF aus HTML-Vorlagen,
      fpdf2 nur Rückfall“ und „Cloover nur Profil Standard“.
      `ANGEBOTSTEXTE.md` (Phase 190), `docs/angebots-pdf.md` (neu: Engine,
      Vorlagenstruktur, Bausteine, wie man ein Design-Update einspielt,
      Bilder/Schriften, Rückfall), `docs/cloover-api.md` (Endpunkte,
      Feldzuordnung, Netto-Regel, Kontrollwerte, Einrichtung `.env`,
      SharePoint-Site + `Sites.Selected`, Anonym-Links, Rückfragenliste an
      Cloover), `docs/graph-einrichtung.md` (SharePoint-Ablage),
      `docs/betrieb.md` (Inventar: Browser-Prozess, Lauf `cloover-status`,
      Ablage, Link-Ablauf), `docs/nach-dem-update-v36.md` (Team: neues
      Angebotslayout je Sparte, HTML-Vorschau, Signatur, Finanzierungskarte,
      Link nur mit E-Mail + Telefon, Badges; Admin: Edge auf dem Server,
      `pdf_engine`, Titelbilder/Teamfoto tauschen, Cloover-Modus test →
      live erst nach Live-Key, Verbindungstest, Test-PDF, Fußnoten-Wortlaut
      von Cloover, Datenschutzsatz); `docs/updates.md`; `config.VERSION =
      "v36"`.
- [x] **Gesamtübersicht am Ende:** erledigte Phasen, Testergebnisse,
      angepasste Alt-Tests mit Begründung, Abweichungsliste Layout ↔
      Vorlagen, Druckzeiten, Ergebnis des Cloover-Echtlaufs, Liste der
      [ANNAHME]-Stellen, Rückfragen gebündelt. **Ein Commit** „v36:
      Angebotslayout v3 (HTML + Browser-Druck), Cloover-Finanzierung
      (PLAN_V22, Phasen 188-195)“; **kein push vor Freigabe**.

## Kontrollwerte für die Abnahme

Teil A – Layout:

- WP-Demo-Angebot (Förderung, Gesamtrabatt 500 €, eine EP-Position, 016
  aktiv): 11 Seiten in der Reihenfolge Deckblatt · Überblick+Team ·
  Positionen (n Seiten) · KfW · Auftragserteilung · Bedingungen · Vollmacht;
  Seitenzahl in der Randzone (Deckblatt ohne Überlappung), Seite 2 „SEITE 2 VON 11“; Summenblock Netto ·
  19,00 % USt. · Gesamt-Betrag · − Rabatt · = Endbetrag · − voraussichtliche
  KfW-Förderung (xx %) · dunkle Box „= Ihr Eigenanteil“; EP-Position mit
  „EP.“; KfW-Seite mit dynamischen Positionsnummern; Vollmacht mit
  vorbelegtem Namen/Adresse/Telefon/E-Mail; PDF ≤ 2,5 MB; Druck ≤ 3 s.
- PV-Demo-Angebot: „0,00 % USt. (§ 12 Abs. 3 UStG)“, drei Wirtschaftlich-
  keitsseiten vor der Auftragserteilung, Vollmacht nur bei 017.
- KL-Demo-Angebot ohne 016/017: keine Vollmacht, „Hinweis zur Kältetechnik“
  in den Bedingungen; WB-Fall B (V21): fünf Positionen, 4.918,09 € Gesamt.
- Profil Enni: Karte 2 „ENNI CONTRACTING“, kein Cloover-Block, kein
  Cloover-Projekt; Sparkasse DU: Karte 2 „FINANZIERUNG MIT SPARKASSE
  DUISBURG“.
- Ohne `BASIS_URL`: Karte 1 mit „Per E-Mail beauftragen ›“ (mailto mit
  Angebotsnummer); mit `BASIS_URL` und aktiver Fern-Signatur: „Jetzt online
  beauftragen ›“ auf den Token-Link.
- Vor-Ort-Signatur am WP-Angebot → signiertes PDF mit Signaturbild auf der
  Unterschriftslinie und „<Name> · signiert am …“, Status Angenommen.
- `pdf_engine = fpdf2` → altes Layout auf allen Routen, Meldung bei
  automatischem Rückfall.
- Summen aller bestehenden Kontrollfälle unverändert (WP 30.245,43 € netto,
  KL Fall A 6.518,66 €, WB Fälle A–D, PV-Fälle).

Teil B – Cloover:

- Verbindungstest (Test-Umgebung): „Verbindung OK · Beispielrate 93,36 €/
  Monat (Test-Umgebung)“; v2-Probe je Sparte grün bzw. mit Cloover-Meldung.
- WP-Angebot Endbetrag 42.830,55 €, Förderung 16.500,00 €, Laufzeit 15 Jahre
  (Editor): Body `price` 35992.06 / `vatPercentage` 19 / `subsidy` 16500 /
  `durationInYears` 15 → gemockte Antwort 389,99 / 242,70 → Karte 2 „ab
  242,70 € / Monat*“ mit „ohne Förderung ab 389,99 €“, Box „Planbare
  Monatsraten“ mit beiden Zeilen, Fußnote mit 42.830,55 €, 16.500,00 €, 15
  Jahren.
- PV-Angebot 20.000,00 € (0 % USt): Body `price` 20000 / `vatPercentage` 0 /
  ohne `subsidy`; eine Zeile „ab … € pro Monat ohne Förderung“.
- KL- und WB-Angebot: eine Zeile; Häkchen „ausblenden“: Karte ohne Rate,
  kein Projekt.
- Kunde ohne Telefon → Versand vorbereiten liefert PDF mit Rate, ohne
  Knopf/QR, Meldung „Cloover-Link nicht möglich: Telefon fehlt“; Telefon
  nachgetragen + Knopf „Projekt anlegen“ → Knopf + QR im PDF, Verlauf
  „Cloover-Projekt … angelegt“; erneutes „Versand vorbereiten“ → kein
  zweites Projekt.
- Kombi-Mail WP + PV → ein Projekt mit zwei Assets, derselbe Link in beiden
  PDFs, je PDF eigene Rate + Gesamtrate.
- Status-Lauf mit gemockter Antwort `primary_signed_contract = true` →
  Badge „Cloover: Vertrag unterschrieben (TT.MM.JJJJ)“, Notiz, Glocke an ID
  und AD, kein Statuswechsel am Angebot.
- `pytest tests -q` grün, Abnahmeskript grün, Voll-Crawl ohne Absturz,
  Lasttest normal innerhalb der Zielwerte, 0 „database is locked“; Key
  taucht in keiner Log-/Protokoll-/Fehlerdatei auf (Test).

## Zulieferungen / bewusst offen

Teil A – Layout:

- **Andreas (vor der Übergabe):** die vier anonymisierten Vorlagen aus dem
  Chat nach `docs\design-v36\vorlage\` (angebot-waermepumpe.html,
  angebot-pv-anlage.html, angebot-klimaanlage.html, angebot-wallbox.html);
  die Original-Exporte mit Kundendaten nicht in den Projektordner.
- **Server:** Edge auf dem Server vorhanden? (Claude Code prüft mit
  `scripts\pdf-browser-pruefen.bat`; sonst `playwright install chromium`
  beim Update – braucht Internet auf dem Server.)
- **Rückfrage A1 (Andreas):** Telefonnummer des Außendienstlers im
  Infokasten – aus der Benutzerverwaltung (Feld Telefon, v29) für alle AD
  gepflegt? Sonst Zeile weglassen.
- **Rückfrage A2 (Andreas):** „Gültig bis“ im Infokasten (Angebotsdatum +
  30 Tage) – gewünscht oder weglassen?
- **Rückfrage A3 (Andreas):** Titelbilder/Teamfoto später in der
  Parametrierung austauschbar (Upload) oder feste Dateien im Projektordner
  (Vorschlag: feste Dateien, Austausch per Update)?
- Bestätigung der [ANNAHME]-Stellen Teil A: Seitenzahl auch auf dem
  Deckblatt (Randzone); Fußzeile als Tabellenfuß; Ausführungsort/Lieferanschrift
  unter dem Empfängerblock; Version/Kopie im Infokasten; Markdown-Struktur
  des Vortexts → zwei Spalten; Aufzählungsregel „-“/„•“; dunkle Box ohne
  Förderung = Gesamt-/Endbetrag; Kurzsatz der Zahlungsbedingung in Karte 1;
  Rate mit Förderung groß, ohne Förderung klein.
- **Eigenes Konzept (nächster Schritt, nicht Teil dieses Plans):**
  öffentliche HTTPS-Adresse/Erreichbarkeit des Tools – Fern-Signatur-Link,
  Cloover-PDF-Ablage, Lead-Webhooks (`POST /api/leads` von außen),
  Heizreport-Webhook, Diktat/Kamera im Browser.

Teil B – Cloover:

- **Andreas:** Test-Key in die `.env` von Dev-PC und Server
  (`CLOOVER_API_KEY=…`), nicht in den Plan, nicht ins Projektwissen; Live-
  URL und Live-Key von Cloover, sobald freigegeben.
- **Andreas mit admin@ (für die PDF-Ablage):** SharePoint-Site/Bibliothek
  „Cloover-Angebote“ anlegen, der Tool-App `Sites.Selected` auf diese Site
  geben, Freigabe „Jeder mit dem Link“ für diese Site erlauben – Befehle in
  `docs/cloover-api.md` nach Phase 194. Alternative: öffentliche HTTPS-
  Adresse für die Token-Route (Konzept Erreichbarkeit).
- **Rückfrage B1 (Cloover/PAngV):** verbindlicher Wortlaut für die Rate im
  Angebot – Werbung mit Monatsraten gegenüber Verbrauchern verlangt
  Pflichtangaben (Sollzins, effektiver Jahreszins, Gesamtbetrag,
  repräsentatives Beispiel); die API liefert nur die Rate. Cloover hat als
  Finanzierungspartner üblicherweise einen freigegebenen Partnertext – bis
  dahin ist die Fußnote ein Entwurf (kein Rechtsrat; mit Cloover/Jurist
  abstimmen).
- **Rückfrage B2 (Cloover):** Anlagentyp für Klimaanlagen („Energetic
  Renovation“ oder eigener Typ?); Bedeutung von `capacity` je Typ.
- **Rückfrage B3 (Cloover):** Was ist `ClooverPay`? Welche
  `financingOption` sollen dem Kunden im Checkout angeboten werden?
- **Rückfrage B4 (Cloover):** Gibt es einen anderen Weg für `offerPDF` als
  eine öffentliche URL (Upload, Base64)? Wie lange muss die URL abrufbar
  bleiben?
- **Rückfrage B5 (Cloover):** Storno/Ersatz eines Projekts bei neuer
  Angebotsversion; Umgang mit mehreren Projekten je Kunde.
- **Rückfrage B6 (Andreas):** Kombi-Mail = ein Cloover-Projekt für alle
  Angebote (Vorschlag) oder ein Projekt je Angebot?
- **Rückfrage B7 (Andreas/Datenschutz):** Mit dem persönlichen Link in
  jedem Angebot gehen Name, E-Mail, Telefon, Adresse und das Angebot bei
  jedem Versand an Cloover – also auch bei Kunden, die bar zahlen.
  Empfehlung: Datenschutzsatz im Angebot (Textbaustein), Auftrags-/
  Partnervereinbarung mit Cloover prüfen, Häkchen „Finanzierung ausblenden“
  für Kunden, die das nicht wünschen. Das Tool setzt um, die rechtliche
  Einordnung liegt bei Friondo.
- **Rückfrage B8 (Cloover):** Liste der `status`-Werte eines Projekts.
- Bestätigung der [ANNAHME]-Stellen Teil B: Standard-Optionen Cash +
  Financing; `financingDuration` 1–20; Projekt unter dem Cloover-Konto des
  vorbereitenden Innendienstlers, sonst Standard-Konto; ein Asset je
  Angebot (kein eigenes Battery-Asset); Link-Ablauf 180 Tage; Fassung A/B
  des PDFs; Kennzahl in der Statistik; Versionsnummer v36 und Phasen
  188–195.
- Nicht Teil dieses Plans: Lead-Übergabe an Cloover, automatische
  Annahme bei Vertragsunterschrift, Sparkasse-Finanzierung mit Rate,
  Enni/SWD-Contracting-Rechnung.
