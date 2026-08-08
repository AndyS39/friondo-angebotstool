# Umsetzungsplan Friondo Angebotstool

Phasen der Reihe nach abarbeiten. Vor jeder Phase kurz den Ansatz erläutern, nach
Abschluss testen, Checkboxen abhaken, committen. Bei Unklarheiten in der Logik-Excel
oder den Texten: nachfragen statt raten.

## Phase 0 – Projekt-Setup
- [x] venv + requirements.txt (fastapi, uvicorn, sqlalchemy, jinja2, python-multipart,
      openpyxl, fpdf2, python-dotenv)
- [x] Struktur: app/, app/templates/, app/static/, data/, docs/
- [x] FastAPI-Grundgerüst, Basis-Layout, Navigation (Kunden · Artikel · Angebote · Konfiguration)
- [x] SQLite/SQLAlchemy, Tabellen beim Start; .env + config.py (Pfade zu Preisliste,
      Logik-Excel, Logo-Ordner; MwSt 19 %; Nummernkreis-Start AN-C-261000)
- [x] `Layout - Logo` inspizieren, Haupt-Logo und Badge-Dateien identifizieren und in
      config.py hinterlegen (Logo-01.png = Haupt-Logo, Logo-02.png = Badge)
- [x] start.bat, README, Git init, .gitignore (data/, .env, venv/, __pycache__)

## Phase 1 – Kundenverwaltung
- [x] Modell `kunden` (Firma/Anrede, Vor-/Nachname, Straße, PLZ, Ort, E-Mail, Telefon,
      Kunden-Nr., Notizen, aktiv)
- [x] Liste mit Suche; anlegen / bearbeiten / deaktivieren (kein Löschen bei Angeboten)
- [x] Validierung: Name oder Firma Pflicht, E-Mail-Format

## Phase 2 – Preislisten-Import (TAIFUN)
- [x] Modell `artikel` inkl. GUID, Positionsnummer, Kategorie, EP-Flag, aktiv
- [x] Import lt. CLAUDE.md (GUID-Anker, Kategorien, _x000D_-Bereinigung, „EP.")
- [x] Textregeln aus Logik-Excel Blatt „Textregeln" beim Import anwenden
- [x] Zusatzartikel Z01–Z22 aus Blatt „Zusatzartikel" importieren; bei Textquelle
      „analog Pos. 125 / 130 / 131" den Beschreibungstext von dort übernehmen und
      Material/Größe anpassen
- [x] Re-Import mit Vorschau + Warnliste (Positionsnummer ↔ GUID-Abweichungen)
- [x] Artikelliste mit Suche/Kategorie-Filter; manuelles Anlegen/Bearbeiten möglich

## Phase 3 – Logik-Import & Validierung
- [x] Parser für konfigurator_logik.xlsx (Blätter Fragen, Aktionen, Paketmatrix,
      Angebotsaufbau, KfW)
- [x] Validierungslauf: alle referenzierten Positionen/Z-Artikel existieren, alle
      Fragen-IDs aus Aktionen bekannt, Bedingungen parsebar → Fehlerbericht im UI
- [x] „Konfiguration neu einlesen"-Funktion im Adminbereich

## Phase 4 – Konfigurator-UI
- [x] Fragenfluss F01–F36 mit Bedingungen („Anzeigen wenn"), ein Schritt pro Frage,
      zurückspringen möglich, Antworten änderbar
- [x] Fragetypen: Auswahl (Buttons), Zahlen-/Betragseingabe, Mengenmaske (F17),
      Wiederholfelder (F20 dynamisch aus F19)
- [x] ABBRUCH-Logik: Meldung + Button „Manuelles Angebot erstellen" (Kunde übernehmen)
- [x] Leistungsklassen-Ermittlung (F02) + Paketauflösung erst wenn F03/F04 beantwortet
- [x] Konfigurationsprotokoll (alle Fragen + Antworten) am Angebot speichern

## Phase 5 – Angebotserstellung
- [x] Modelle `angebote` + `angebotspositionen` (Snapshots: Bezeichnung, Beschreibung,
      Einheit, Einzelpreis, EP-Flag, Gruppenzuordnung)
- [x] Zusammenbau lt. Blatt „Angebotsaufbau": Blockreihenfolge, Gruppen-Überschriften,
      dynamische Überschrift Block 1, Gruppen-Trigger Pos. 014, Heizkörper-Pauschale
      129 × Gesamtanzahl, Verteiler-Pauschale 108 × Anzahl, EP-Regel
- [x] Summen: Netto / USt / Brutto (Decimal, Cent); EP-Positionen nicht einrechnen
- [x] Nummernkreis AN-C-<JJ><NNNN> ab 261000, transaktionssicher beim ersten Speichern
- [x] Nachbearbeitung: Mengen ändern, Position entfernen, Freitextposition, Artikel aus
      Stamm ergänzen; Angebotsliste mit Status/Suche; duplizieren
- [x] Manuelles Angebot (ohne Konfigurator) mit gleichem Editor

## Phase 6 – KfW-Berechnung
- [x] Rechenmodul exakt nach Blatt „KfW" (EFH/MFH/Gewerbe, Boni, Deckel, Höchstkosten,
      MFH-Anteilslogik, Programmnummer)
- [x] Gültigkeitswarnung nach 31.01.2027 im UI
- [x] Testfälle gegen foerderrechner-website.html (mind. 8 Szenarien inkl. Deckelung,
      Kind-Freibetrag, MFH anteilig, Gewerbe-Fläche) als automatisierte Tests

## Phase 7 – PDF-Export (Friondo-Layout)
- [x] Referenz „Layout - Logo/Angebot-Nr. AN250096" als visuelle Vorlage nachbauen
- [x] Seite 1: Logo-Leiste, Absenderzeile, Empfänger, Seite/Datum/Kunden-Nr.,
      Angebots-Nr., Vortext aus ANGEBOTSTEXTE.md
- [x] Jede Seite: Kopf (ab S. 2 Logo rechts + Angebots-Nr./Seite), 5-Spalten-Fußzeile
- [x] Positionstabelle mit Gruppen-Überschriften, Übertrag-Zeilen, EP-Darstellung,
      sauberen Umbrüchen bei langen Beschreibungen
- [x] Summenblock + KfW-Aufschlüsselung + Eigenanteil + Disclaimer
- [x] Nachtext-Seiten A–D aus ANGEBOTSTEXTE.md (Zahlungsoptionen, Installations-
      voraussetzungen, Unterschriften-Seite, Vollmacht mit vorbefüllten Kundendaten)
- [x] Ablage data/angebote/AN-C-<Nr>.pdf, Anzeige/Download im Browser

## Phase 8 – Outlook-Versand
- [x] pywin32; Button „Per E-Mail senden": Outlook-Entwurf an Kunden-E-Mail mit
      Betreff „Ihr Wärmepumpen-Angebot AN-C-… der Friondo GmbH", Standardtext, PDF-Anhang
- [x] Nach Bestätigung Status „Versendet"; Hinweis: klassisches Outlook nötig,
      Fallback PDF-Download

## Phase 9 – monday.com
- [ ] Vorher mit dem Nutzer klären: Ziel-Board + Spalten-Mapping
- [ ] API-Token via .env; bei Versand/Statuswechsel Item anlegen/aktualisieren,
      optional PDF anhängen; Fehler blockieren den Angebotsprozess nie

## Phase 10 – Feinschliff
- [ ] Statuspflege, tägliches SQLite-Backup nach data/backups/
- [ ] docs/anleitung.md für den Vertrieb (Konfigurator, Logik-Excel pflegen, Re-Import)
