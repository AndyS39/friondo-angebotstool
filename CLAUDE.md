# Friondo Angebotstool – Projektkontext

## Ziel
Internes Angebotstool für den Vertrieb der Friondo GmbH (Wärmepumpen zum Festpreis).
Ein geführter Frage-Konfigurator stellt aus Kundendaten und Antworten automatisch ein
vollständiges Angebot zusammen, berechnet die voraussichtliche KfW-Förderung, erzeugt
ein PDF im gewohnten Friondo-Layout und versendet es per Outlook. Läuft lokal, keine Cloud.

## Nutzer & Betrieb
- Nutzer: ausschließlich das Vertriebsteam (interne Anwendung, kein Kundenzugang)
- Betrieb: lokale Web-App im Firmennetz; eine zentrale Instanz, Zugriff per Browser
- Umgebung: Windows, klassisches Outlook-Desktop vorhanden

## Tech-Stack
- Python 3.11+, FastAPI, Uvicorn; SQLite (`data/angebotstool.db`) über SQLAlchemy
- Server-gerenderte Jinja2-Templates, wenig JavaScript, kein SPA-Framework
- PDF: fpdf2 · Excel: openpyxl · Outlook: pywin32/COM · monday.com: GraphQL API (.env)

## Zentrale Dateien im Projektordner
- `konfigurator_logik.xlsx` – **die** Steuerdatei: Fragen, Aktionen, Paketmatrix,
  Zusatzartikel Z01–Z22, Textregeln, Angebotsaufbau, KfW-Parameter. Wird vom Tool
  eingelesen; Änderungen dort erfordern KEINE Codeänderung.
- `ANGEBOTSTEXTE.md` – Briefkopf-/Fußzeilen-Daten und alle statischen Angebotstexte
  (Vortext, Zahlungsoptionen, Installationsvoraussetzungen, Unterschriften-Seite,
  Vollmacht). Wortlaut exakt übernehmen.
- `Artikel-Preislisten/Angebotserstellung Tool.xlsx` – TAIFUN-Preisliste (163 Positionen).
- `Layout - Logo/` – Logodateien und Referenz-PDF „Angebot-Nr. AN250096" (Ordner beim
  Start inspizieren; das Referenz-PDF ist die visuelle Vorlage für das Angebots-Layout).
- `foerderrechner-website.html` – Referenz für die KfW-Berechnung (Testfälle dagegen).
- `PLAN.md` – Umsetzungsplan; immer nur eine Phase bearbeiten, Checkboxen abhaken.

## Preislisten-Import (TAIFUN)
- Spalten: GUID · Position (dreistellig, z. B. „045") · Menge · Einheit · Beschreibung ·
  E-Preis · G-Preis. Zeilen ohne Positionsnummer sind Kategorie-Überschriften.
- Jede Position an ihrer GUID verankern. Bei Re-Import warnen, wenn hinter einer
  Positionsnummer eine andere GUID/Beschreibung steckt (niemals still falsch zuordnen).
- `_x000D_`-Zeilenumbrüche bereinigen; G-Preis „EP." = Eventualposition-Kennzeichen.
- Textregeln aus der Logik-Excel bei jedem Import anwenden (z. B. Pos. 090 ohne BOSCH).
- Zusatzartikel Z01–Z22 aus der Logik-Excel zusätzlich in den Artikelstamm importieren.
- Re-Import aktualisiert Preise; bestehende Angebote bleiben unverändert (Snapshots).

## Konfigurator
- Ablauf: Kunde anlegen/wählen → Fragen F01–F36 lt. Logik-Excel → Angebotsentwurf.
- Fragetypen: Auswahl, Zahleneingabe, Betragseingabe, Mengenmaske (F17),
  Wiederholfelder (F20, Anzahl aus F19), Info-Frage (F21).
- ABBRUCH-Antworten (12 Fälle): Meldung anzeigen, Konfigurator stoppt, Wechsel ins
  manuelle Angebot anbieten.
- Alle Antworten als Konfigurationsprotokoll am Angebot speichern (intern, nicht im PDF).
- Nach dem Konfigurator ist das Angebot voll editierbar (Mengen, Positionen entfernen,
  Freitextpositionen ergänzen).

## Fachliche Regeln
- Nur Festpreise; Preise in Angeboten sind Snapshots.
- Angebotsnummer: eigener Kreis `AN-C-<JJ><NNNN>`, Start **AN-C-261000**, dann +1;
  Jahreswechsel: neues JJ, Zähler wieder 1000. Transaktionssicher, niemals doppelt.
- EP-Positionen: mit E-Preis und Kennzeichen „EP." ausweisen, NICHT in Summe einrechnen.
- Beträge als Decimal in Cent; 19 % USt.; deutsche Formatierung (1.234,56 €).
- Gültigkeit Angebot: 30 Tage („Wir halten uns freibleibend 30 Tage … gebunden").
- Status: Entwurf → Versendet → Angenommen / Abgelehnt.

## KfW-Förderung
- Parameter ausschließlich aus Logik-Excel Blatt „KfW" (editierbar, mit Gültigkeits-
  warnung nach 31.01.2027). Kosten der Maßnahme = Angebotssumme brutto (automatisch).
- Summenblock: Netto → USt → Gesamt brutto → volle Aufschlüsselung (Grundförderung,
  Boni, Fördersatz, förderfähige Kosten, Zuschuss) → Eigenanteil → Disclaimer.
- Ergebnisse müssen mit `foerderrechner-website.html` übereinstimmen (Testfälle!).

## PDF-Layout
Referenz-PDF pixelnah nachbauen: Logo-Leiste Seite 1, Folgeseiten Friondo-Logo rechts,
5-Spalten-Fußzeile auf jeder Seite, Positionstabelle mit Übertrag-Zeilen und fetten
Gruppen-Überschriften lt. Blatt „Angebotsaufbau" (Block 1 mit dynamischer Überschrift),
danach Summen-/KfW-Block und die vier statischen Nachtext-Seiten aus ANGEBOTSTEXTE.md.
Ablage: `data/angebote/AN-C-<Nr>.pdf`.

## Konventionen
- Sprache in UI, Kommentaren, Commits: Deutsch. Struktur: `app/`, `app/templates/`,
  `app/static/`, `data/` (nicht committen), `docs/`.
- Konfiguration (Pfade, MwSt, API-Tokens) über `.env` + `config.py`; Tokens nie committen.
- Nach jeder Phase aus @PLAN.md: testen, Checkboxen abhaken, Git-Commit.

## Nicht-Ziele (v1)
Kein Login/Rechteverwaltung, keine Rechnungen, keine Rabattlogik, keine Cloud.
