# Angebots-PDF – Layout v3 (HTML-Vorlagen + Browser-Druck), v36

Stand 16.10.2026 (PLAN_V22 Teil A, Phasen 188–191). Das Angebots-PDF aller Sparten (WP · PV · KL · WB) entsteht
seit v36 aus Jinja2-HTML-Vorlagen, die ein Browser im Hintergrund (Edge, gesteuert über Playwright) als A4-PDF
druckt. Die bisherige fpdf2-Erzeugung (`app/pdf_export.py`) bleibt **eine Version lang als Rückfall** – über den
Schalter `pdf_engine = fpdf2` oder automatisch, wenn der Browser-Druck fehlschlägt. Lieferschein, Protokoll-PDF,
BzA-Datenblatt, Steckbrief und Montageformulare bleiben fpdf2.

## 1. Bausteine

| Datei | Aufgabe |
|---|---|
| `app/pdf_html.py` | Engine: Jinja-Umgebung der PDF-Vorlagen, Drucker (ein Browser-Prozess je Dienst, eigener Thread mit asyncio-Schleife, höchstens 2 parallele Drucke, 30 s je PDF), `angebot_pdf(session, angebot, signatur=, fassung=)`, `angebot_html(…)`, `browser_test(…)`, Engine-Schalter `engine()/engine_setzen()`, Testergebnis `letzter_test()`, Dateiprüfung `dateien_pruefen()`, Migration `migration_v36_pdf_engine()` |
| `app/pdf_kontext.py` | **EIN** Kontext-Dict je Angebot (`fuer_angebot(session, angebot, *, signatur=None, fassung="kunde")`) aus den heutigen Datenquellen (Anschriften v20, Positionen mit Kennzeichen, Summen, Rabatt, Vermerke, Zahlungsbedingung, Textblöcke, Signatur); Vertrag der Schlüssel im Modul-Docstring; `demo_kontext(sparte)` = Max Mustermann ohne Datenbank |
| `app/pdf_kontext_kfw.py`, `app/pdf_kontext_wirtschaftlichkeit.py` | Teilbäume `kfw` (WP mit Förderblock) und `wirtschaftlichkeit` (PV, drei Seiten) |
| `app/pdf_export.py` | Einstiegspunkte `pdf_fuer_angebot(session, angebot)` und `signiertes_pdf_erzeugen(session, angebot, png_bytes, name, zeit, geraet="")` mit der Engine-Weiche; darunter unverändert die fpdf2-Erzeugung (`_pdf_fpdf2`, `_signiertes_pdf_fpdf2`, `erzeuge_pdf`) |
| `app/templates/pdf/angebot/` | Vorlagen: `basis.html` (Dokumenttabelle, wiederholter Tabellenfuß `_fuss.html`, Block `seiten`), Sparten-Vorlagen `wp.html` · `pv.html` · `kl.html` · `wb.html` (erben von basis, setzen die Seitenfolge), Seiten-Bausteine `deckblatt.html` · `ueberblick.html` · `positionen.html` · `kfw.html` · `wirtschaftlichkeit.html` · `auftrag.html` (mit `_cloover.html`) · `bedingungen.html` · `vollmacht.html` |
| `app/static/pdf/angebot.css`, `angebot_kfw.css`, `angebot_wirtschaftlichkeit.css` | Druck-Stylesheets (Tokens `--pdf-dunkel #15153a`, `--pdf-blau #4389c8`, `--pdf-grau #6b6f85`, `--pdf-linie #dfe3ee`, `--pdf-flaeche #f1f6fc`, `--pdf-hell #dbe9f7`; `@page A4` mit 10 mm Randzone oben; `.pdf-seite` = eine Seite mit 16 mm Innenabstand und Seitenumbruch) |
| `app/static/pdf/bilder/` | `logo.jpg`, `award-2026.png`, `team.jpg`, `kfw.png`, `titel-wp|pv|kl|wb.jpg` (1600 px, JPEG ≤ 350 KB), `zert-shk.jpg`, `zert-ehandwerk.jpg`, `zert-bdsh.png`, `zert-fachbetrieb-wp.jpg`, `zert-bosch.png` |
| `app/static/pdf/fonts/nunito-sans/` | Nunito Sans (variable woff2, fünf Unicode-Teilmengen, `nunito-sans.css`, `OFL.txt`) |
| `docs/design-v36/vorlage/` | die vier anonymisierten Claude-Design-Exporte (Quelle der Wortlaute und Bilder), entpackt unter `entpackt/` |

Seitenfolge: WP Deckblatt · Überblick + Team · Festpreisangebot (n Seiten) · Ihre KfW-Förderung · Auftragserteilung ·
Vertragsbedingungen · Vollmacht (nur mit 016/017); PV wie WP, statt KfW die drei Wirtschaftlichkeitsseiten, Vollmacht
nur mit 017; KL ohne KfW/Wirtschaftlichkeit, Vollmacht nur mit 016/017; WB wie KL, Vollmacht immer. Kopfzeile auf
allen Seiten (Browser-Kopfvorlage in der 10-mm-Randzone, Systemschrift): „Angebot-Nr. … · Kunde“ links, „SEITE x VON y“
rechts. Fußzeile fünfspaltig als wiederholter Tabellenfuß. Details der Datenbindung: `ANGEBOTSTEXTE.md` Abschnitt 11.

## 2. Ablauf eines Drucks

1. Aufrufer (Editor „PDF anzeigen“, Download, „Versand vorbereiten“, Kombi-Versand, Projektablage, Nachfass-Mail,
   Signatur-Anzeige, „Meine Angebote“) rufen `pdf_export.pdf_fuer_angebot(session, angebot)` – wie bisher.
2. Engine `html`: `pdf_html.angebot_pdf` liest den Kontext (`pdf_kontext.fuer_angebot`) **mit** Sitzung, gibt die
   Datenbankverbindung frei (`db.verbindung_freigeben` = Commit) und druckt danach **ohne** Sitzung: Vorlage rendern →
   HTML in `data\tmp\pdf\angebot-<uuid>.html` → `page.pdf(format="A4", print_background=True,
   prefer_css_page_size=True, display_header_footer=True, header_template=…)` → Bytes an den bisherigen Zielpfad
   `data\angebote\<Nummer>.pdf` (signiert: `data\angebote\signiert\<Nummer>-signiert.pdf`).
3. Browser: Reihenfolge `.env PDF_BROWSER_PFAD` → Kanal `msedge` (auf dem Windows Server vorhanden) → Playwright-
   Chromium (`playwright install chromium`, nur wenn Edge fehlt). Ein Browser-Prozess je Dienst, Start beim ersten PDF,
   Neustart nach Fehler/Zeitüberschreitung, Semaphore 2, Timeout 30 s.
4. Rückfall: `PdfDruckFehler` (kein Browser, Absturz, Zeitüberschreitung), ein Fehler in Vorlage/Kontext oder ein
   noch fehlender Kontext → Eintrag im Fehlerprotokoll (Fehlertyp „PDF“, Parametrierung → Fehlerprotokoll), PDF im
   bisherigen Layout (fpdf2) an denselben Pfad, prozessweiter Merker `pdf_export.letzter_rueckfall(angebot_id)`.
   „Versand vorbereiten“ und der Kombi-Versand hängen den Grund an ihre Meldung: „PDF im alten Layout erzeugt
   (Browser-Druck fehlgeschlagen: <Grund>)“. Ein gelungener Druck oder der Schalter `fpdf2` löschen den Merker.
5. **Archiv (Entscheidung 16.10.2026):** bei Status Versendet, Angenommen, Abgelehnt, Überholt (und Versendet
   (extern)) bleibt eine vorhandene, nicht leere Datei unter `data\angebote\` unverändert – kein Neu-Rendern, egal
   welche Engine (`pdf_export.pdf_eingefroren`). Nur Entwurf und „Versand vorbereitet“ rendern je Aufruf neu; fehlt
   die Datei (Altbestand ohne Archiv), wird sie einmal erzeugt. Signierte PDFs (`signiert\`) sind eigene Dateien;
   „Überarbeiten“ erzeugt die neue Version als neuen Datensatz im aktuellen Layout.
6. **Benutzer und Fern-Signatur-Token:** „Versand vorbereiten“ (Einzel + Kombi) und die HTML-Vorschau übergeben den
   angemeldeten Benutzer (`pdf_fuer_angebot(session, angebot, benutzer=…)` → `pdf_kontext.fuer_angebot`) – er ist der
   Ansprechpartner im Infokasten, wenn der Vorgang keinen Außendienstler hat; übrige Aufrufer ohne (Rückfall wie bisher).
   Ist die Fern-Signatur aktiv (Parametrierung oder `SIGNATUR_FERN_AKTIV`) **und** `BASIS_URL` aus der `.env` gesetzt,
   stellt „Versand vorbereiten“ den Einmal-Token (Modul v4, `fern_token_ausstellen`) **vor** dem Druck aus – Karte 1
   der Auftragserteilung trägt dann „Jetzt online beauftragen ›“ mit dem Token-Link, die Mail denselben Link; sonst
   bleibt der PDF-Knopf „Per E-Mail beauftragen ›“ (mailto) und der Token entsteht wie bisher erst nach dem Druck für die
   Mail. Der Kombi-Versand stellt keine Token aus (unverändert) – ein bereits gültiger Token des Angebots erscheint
   aber auch dort im PDF.

**Regel (v27/v33):** Browser-Druck ist Prozess-I/O – nie mit gehaltener Datenbanksitzung. Der Wächter
`tests/test_v27_sitzungen.py` kennt `pdf_html.drucken` als Prozess-Nahtstelle; jede Aufrufkette zum Druck ohne
vorherige Freigabe ist ein Verstoß. Vor `pdf_html.angebot_pdf` darf nichts Ungesichertes in der Sitzung liegen – die
Freigabe committet.

## 3. Signatur

`pdf_export.signiertes_pdf_erzeugen` rendert das Angebot bei Engine `html` erneut mit
`signatur = {"bild_data_url": "data:image/png;base64,…", "name", "zeitstempel": "TT.MM.JJJJ HH:MM", "geraet"}`
(`pdf_export.signatur_dict`); das Bild sitzt auf der Linie „Unterschrift des Auftraggebers“, darunter
„<Name> · signiert am TT.MM.JJJJ HH:MM“. Ablage, Signaturprotokoll und Status „Angenommen“ unverändert; Vor-Ort-
(`/signatur/<id>`) und Fern-Signatur (`/signatur/extern/<token>`) nehmen denselben Weg; bestehende signierte PDFs
bleiben unverändert.

## 4. HTML-Vorschau

`GET /angebote/<id>/pdf.html` (Innendienst/Admin; Außendienst 403 bzw. Umleitung) liefert dieselbe Vorlage als
HTML im Browser – Design-Abnahme ohne Druck, Druckvorschau des Browsers über `@media print`. Bilder/Schriften kommen
über den Web-Mount `/static`. `?fassung=intern` kennzeichnet die interne Fassung (keine zusätzlichen Zahlen – der
Kontext enthält nie EK/DB), `?signatur=demo` zeigt die Signaturzeile mit Demo-Daten. Knopf „HTML-Vorschau“ im
Editor-Kopf (neben „PDF anzeigen“).

## 5. Parametrierung, Health, Go-live

- **Parametrierung → Angebots-PDF** (`/parametrierung/angebots-pdf`, Admin): Engine-Schalter html | fpdf2,
  Browser (Kanal/Pfad, Version, Drucke/Fehler/Neustarts dieses Prozesses, letzte Druckdauer), Knopf **„Test-PDF
  erzeugen“** (Demo-Angebot Max Mustermann über die Sparten-Vorlage, Dauer in ms, Download „Letztes Test-PDF öffnen“ =
  `data\tmp\pdf\angebots-pdf-test.pdf`), Prüfung der Bilder/Schriften unter `app/static/pdf/`, Ergebnis des letzten
  Browser-Tests (Einstellung `pdf_letzter_test`), Änderungsprotokoll (Einstellung `pdf_protokoll`, letzte 30).
- **migrate.py** (`pdf_html.migration_v36_pdf_engine`): führt beim Update den Browser-Test aus; schlägt er fehl →
  `pdf_engine = fpdf2` mit Meldung „Angebots-PDF: Browser-Druck nicht verfügbar (…) – Engine auf fpdf2 gestellt“;
  läuft er → Einstellung nur anlegen, wenn sie fehlt (Standard html), eine Wahl des Admins bleibt. Idempotent (zweiter
  Lauf ohne Meldung); das Ergebnis steht in `pdf_letzter_test`.
- **`GET /health`**: `pdf_engine`, `pdf_browser` (Kanal + Version), `pdf_letzte_druckdauer_ms`, `pdf_drucke`,
  `pdf_fehler`, `pdf_letzter_test_ok`; Warnung „Angebots-PDF: Browser-Druck fehlgeschlagen – Rückfall auf fpdf2 je
  Aufruf“, wenn die Engine html ist und der letzte Browser-Test fehlschlug. Betriebs-Seite: Kachel „Angebots-PDF“.
- **Go-live-Checkliste**: Punkt 13 „Angebots-PDF: Browser-Druck grün“ = Engine html UND letzter Browser-Test ok
  (Link auf die Parametrierungsseite).

## 6. Server-Prüfung

`scripts\pdf-browser-pruefen.bat` (im Projektordner, kein Administrator nötig) sucht Edge/Chrome
(`PDF_BROWSER_PFAD`, Standardpfade, Playwright-Cache), druckt ein Test-PDF wie das Tool (Demo-Angebot, keine
Kundendaten, keine Datenbank) und meldet Browser, Version, Dauer und den Pfad der Datei
(`data\log\pdf-browser-test-<Zeit>.pdf`); Exit-Code 0 = ok, 1 = kein Browser/Druck fehlgeschlagen, 2 = Bedienfehler.
Schalter: `--nur-suchen`, `--sparte PV`, `--ziel PFAD`, `--ohne-datei`.

Der Dienst `FriondoAngebotstool` läuft als **SYSTEM** – der Druck muss auch unter diesem Konto funktionieren:

```
psexec -s -i 0 cmd /c "cd /d C:\Users\kdadmin\Desktop\Angebotstool && scripts\pdf-browser-pruefen.bat"
```
oder als geplante Aufgabe unter SYSTEM:
```
schtasks /Create /TN "Friondo PDF-Test" /SC ONCE /ST 23:59 /RU SYSTEM /TR "cmd /c cd /d C:\Users\kdadmin\Desktop\Angebotstool && scripts\pdf-browser-pruefen.bat > data\log\pdf-browser-test.txt 2>&1"
schtasks /Run /TN "Friondo PDF-Test"
```
(danach `data\log\pdf-browser-test.txt` lesen und die Aufgabe wieder löschen). Innerhalb des laufenden Dienstes ist
der Knopf „Test-PDF erzeugen“ der Nachweis für das Dienstkonto. `update.bat` lädt den Playwright-Chromium nur nach,
wenn Edge fehlt und kein `PDF_BROWSER_PFAD` gesetzt ist (braucht Internet auf dem Server).

## 7. Design-Update einspielen

1. Die vier anonymisierten Claude-Design-Exporte nach `docs\design-v36\vorlage\` legen (Kundendaten durch Max
   Mustermann ersetzt; Originale mit Kundendaten nie in den Projektordner).
2. Entpacken: `venv\Scripts\python diagnose\v36\orch\vorlagen_entpacken.py` (Muster) – schreibt Vorlage-HTML und
   Manifest (Bilder, Schriften) nach `docs\design-v36\vorlage\entpackt\` und `entpackt\assets\`.
3. Bilder/Schriften übernehmen: `venv\Scripts\python diagnose\v36\orch\pdf_assets.py` (Muster; Zuordnung der
   Manifest-Dateinamen → `app/static/pdf/bilder/<name>`, Titelbilder 1600 px JPEG 82 %, Teamfoto ≤ 400 KB, Nunito-Sans-
   woff2 + OFL nach `fonts/nunito-sans/`).
4. Wortlaute/Markup in die Bausteine unter `app/templates/pdf/angebot/` übertragen – nur Layout und Text, kein React,
   kein Script, keine externe URL; Farben ausschließlich `var(--pdf-…)` (Token-Wächter `tests/test_v30_design.py`
   prüft Templates auf Hex-Farben); Beträge kommen fertig formatiert aus dem Kontext.
5. Prüfen: `GET /angebote/<id>/pdf.html` (Vorschau), Parametrierung → „Test-PDF erzeugen“,
   `tests/test_v36_pdf_engine.py`, `tests/test_v36_einbindung.py`, `tests/test_v36_layout.py`; Abnahme-PDFs nach
   `docs/design-v36/`.

## 8. Bilder/Schriften tauschen

Datei gleichen Namens unter `app/static/pdf/bilder/` ersetzen (Titelbilder `titel-<sparte>.jpg` 1600 px breit,
JPEG ≤ 350 KB; `team.jpg` ≤ 400 KB; Logos/Zertifikate wie geliefert) – kein Codeeingriff, kein Neustart (Dateien
werden je Druck geladen). Die Parametrierungsseite meldet fehlende Dateien. Ziel: Angebots-PDF ≤ 2,5 MB (Test).
Schriftwechsel: woff2 + `@font-face` in `fonts/<name>/<name>.css`, Einbindung in `angebot.css` (`@import`), Lizenz
daneben; die Browser-Kopfzeile nutzt bewusst die Systemschrift (Kopfvorlagen laden keine Webfonts).

## 9. Fehlersuche

| Befund | Ursache / Maßnahme |
|---|---|
| Versand-Meldung „PDF im alten Layout erzeugt (Browser-Druck fehlgeschlagen: Kein Browser …)“ | Edge nicht gefunden: `scripts\pdf-browser-pruefen.bat`, `PDF_BROWSER_PFAD` in der `.env`, sonst `venv\Scripts\python -m playwright install chromium`; Dienst neu starten |
| „… Zeitüberschreitung beim Browser-Druck (30 s)“ | Server unter Last oder Browser hängt – der Drucker startet den Browser neu; Parametrierung → Angebots-PDF (Fehler/Neustarts), `data\fehler.log` |
| „… Vorlage/Kontext: KeyError …“ | Fehler in einer Vorlage/dem Kontext – Traceback im Fehlerprotokoll (Fehlertyp PDF); bis zur Korrektur fällt jedes PDF auf fpdf2 zurück |
| „… Layout v3 noch nicht verfügbar“ | Kontext-Funktion fehlt (nur im Entwicklungsstand) |
| /health `warn` „Angebots-PDF: Browser-Druck fehlgeschlagen“ | letzter Browser-Test rot bei Engine html – Test wiederholen, sonst Engine auf fpdf2 stellen |
| Leere Stellen im PDF (Bild fehlt) | Parametrierung → Angebots-PDF → „Bilder und Schriften“ |
| Schrift sieht falsch aus | `fonts/nunito-sans/*.woff2` fehlen oder `angebot.css` ohne `@import`; Chromium bettet die variable Nunito Sans als Type3-Schrift ein (ohne Fontnamen im PDF – normal) |
| HTML-Vorschau ohne Bilder | Vorschau über HTTP lädt `/static/pdf/…` – Static-Mount und Dateien prüfen |
| PDF > 2,5 MB | Titelbilder/Teamfoto zu groß (Abschnitt 8) |
| Druck dauert > 3 s | erster Druck nach dem Start (Browser-Start, Schriften) ist langsamer; dauerhaft: Parametrierung → Betrieb (p95 der Route `/angebote/{id}/pdf`), Semaphore 2 |

Temp-Ordner `data\tmp\pdf\` (HTML je Druck, nach dem Druck gelöscht; `angebots-pdf-test.pdf` = letztes Test-PDF).
Protokolle: `data\fehler.log`, Parametrierung → Fehlerprotokoll (Fehlertyp „PDF“), Zugriffslog (Dauer der PDF-Routen).
