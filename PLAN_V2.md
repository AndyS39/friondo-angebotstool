# Umsetzungsplan v2 – Ausbau zum Zwei-Stufen-Prozess

Phasen 0–10 (PLAN.md) sind abgeschlossen. Diese Datei enthält die v2-Phasen.
Reihenfolge einhalten, je Phase: Ansatz erläutern → umsetzen → testen → abhaken →
committen. CLAUDE.md (v2) vorher vollständig lesen.

## Phase 11 – Preisliste v2 & Deckungsbeitrag
- [x] Import auf `Angebotserstellung Tool mit EK.xlsx` umstellen; Spalten über
      Header-Namen erkennen (GUID, Position, Menge, Einheit, Beschreibung, E-Preis,
      G-Preis, Multi, Artikelnummer, Datum Einkaufspreis Material,
      Einkaufspreis Material)
- [x] Artikelmodell erweitern: Artikelnummer, EK Material, EK-Datum, Multi
- [x] Zusatzartikel-EKs aus Logik-Excel v2 übernehmen (Z01–Z14 gefüllt, Rest leer)
- [x] Plausiprüfung beim Import: |EK × Multi − VK| > 1 € → Hinweiszeile im Importbericht
- [x] Deckungsbeitrag je Angebot: Σ VK netto − Σ EK (ohne EP-Positionen); Box mit
      € und % in der Angebotsansicht und als Spalte in der Angebotsliste
- [x] Warnhinweis in der Box: „EK fehlt bei n Positionen" mit Aufklappliste
- [x] Sichtbarkeit: niemals im PDF (getestet); Rollen-Beschränkung auf Innendienst
      greift, sobald Phase 13 die Rollen einführt

## Phase 12 – Logik v2 & Fragebogen-Umbau
- [x] `konfigurator_logik_v2.xlsx` einlesen (neue IDs O/A/N/H/E/P/K, Spalte „Seite",
      Blatt „Anhänge"); Validierung wie gehabt
- [x] AMPEL statt Abbruch: 14 Gründe setzen Flag „individuell" + Grundliste,
      Katalog läuft immer vollständig durch, keine Fehlermeldungen
- [x] Neue Fragen der Seiten Objektdaten / Alte Anlage / Neue Anlage umsetzen
      (inkl. Folgefeld O07 bei „Rechnungsanschrift korrekt = Nein")
- [x] Erdleitung: Menge = max(0, Eingabe − 3); bei 0 keine Position
- [x] KfW-Ableitungen + Klima-Vorbelegung lt. Blatt „KfW" (alte Direktfragen entfallen)
- [x] Regressionstest Kontroll-Szenario (Werte wie gehabt, Erdleitung 8 m → 5 m
      berechnet): Netto 29.629,37 € · USt 5.629,58 € · Brutto 35.258,95 € ·
      Zuschuss 19.600,00 € · Eigenanteil 15.658,95 €
- [x] KfW-Testfälle gegen foerderrechner-website.html erneut laufen lassen

## Phase 13 – Rollen & mobile Erfassung
- [x] Einfache Benutzerverwaltung: Benutzerliste (Name, Rolle Innendienst/Außendienst,
      PIN); Login leichtgewichtig, Sitzung merken (Erststart: Admin / PIN 1234)
- [x] `/erfassung`: mobile-first, eine Seite pro Kategorie, große Bedienelemente,
      Fortschritt, vor/zurück, Pflichtfeld-Prüfung
- [x] Ablauf: Vertriebler angemeldet → Kunde anlegen oder wählen → Katalog → „Absenden"
- [x] Außendienst-Sicht ohne Preise, EK, DB und ohne Angebotsbereich
- [x] Erfassung speichert: Kunde, Vertriebler, Zeitpunkt, alle Antworten, Ampel + Gründe

## Phase 14 – Erfassungsliste Innendienst
- [x] Liste: Datum, Kunde, Vertriebler, Ampel (grün „Konfigurierbar" / orange
      „Individuell" mit Gründen), Status Neu / In Bearbeitung / Erledigt, Filter/Suche
- [x] Detailansicht: alle Antworten je Kategorie, vom Innendienst korrigierbar
      (Änderungen protokollieren)
- [x] Grün: Button „Angebot erzeugen" → Antworten durch die Logik → Angebotsentwurf
      öffnet sich; Erfassung ↔ Angebot verknüpft
- [x] Orange: Button „Manuelles Angebot" → Editor mit Abfrageprotokoll als Seitenpanel
- [x] Nach Angebotserstellung Status automatisch „In Bearbeitung"/„Erledigt" pflegen

## Phase 15 – Vollmacht-Bedingung & Anhänge-Bibliothek
- [x] PDF: Nachtext D (Vollmacht) nur wenn P02 und/oder P03 = Ja; Seitenzahlen bleiben korrekt
- [x] Ordner `anlagen/` anlegen; Blatt „Anhänge" einlesen (Regeln: immer /
      wenn Frage = Antwort / wenn Pos. im Angebot)
- [x] Fehlende Datei → Warnung beim Versand statt Absturz
- [x] Vorschau in der Angebotsansicht: welche Anhänge würden mitgehen

## Phase 16 – Umzug Terminal Server & Zugriff
- [ ] Installationsskript/Anleitung: Projekt auf Terminal Server, venv, Dienst mit
      Autostart (z. B. Aufgabenplanung oder NSSM), Datenpfad + tägliches Backup prüfen
- [ ] App an 0.0.0.0 binden, Firmen-Adresse (Server-IP/Hostname) in README festhalten
- [ ] Innendienst-Test aus Terminalsitzung; Desktop-Verknüpfungen auf Server-Adresse
- [ ] OFFEN (Entscheidung Nutzer/IT): Mobilzugriff Variante A – WireGuard-App auf
      Vertriebler-Handys (empfohlen, bestehendes WireGuard nutzen) ODER Variante B –
      /erfassung öffentlich über HTTPS + Login (Reverse Proxy, Zertifikat, Domain
      durch RZ/IT). Beide dokumentieren, Umsetzung erst nach Entscheidung.

## Phase 17 – Versand über Microsoft Graph
- [ ] docs/graph-einrichtung.md: App-Registrierung Schritt für Schritt für die IT
      (delegierte Berechtigung Mail.ReadWrite; Entwurf-Erstellung im Nutzerpostfach)
- [ ] Anmeldung des Innendienst-Nutzers (Device-Code oder OAuth), Token sicher speichern
- [ ] „Versand vorbereiten": Entwurf im Postfach des angemeldeten Mitarbeiters mit
      Betreff „Ihr Wärmepumpen-Angebot AN-C-… der Friondo GmbH", Standardtext,
      Angebots-PDF + Anhängen lt. Regeln
- [ ] Bestätigung im Tool setzt Status „Versendet"; COM-Versand entfernen;
      Fallback PDF-Download bleibt
