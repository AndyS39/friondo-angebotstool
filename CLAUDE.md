# Friondo Angebotstool – Projektkontext (v2)

## Ziel
Zweistufiger Vertriebsprozess der Friondo GmbH (Wärmepumpen zum Festpreis):
1) Der **Außendienst** füllt beim Kunden mobil einen Fragenkatalog aus (Erfassung).
2) Der **Innendienst** sieht die Erfassung in einer Liste mit Ampel (konfigurierbar /
individuell), erzeugt per Klick das Angebot oder schreibt es manuell mit dem
Abfrageprotokoll daneben, prüft, versendet per E-Mail und behält den Deckungsbeitrag
im Blick. PDF im Friondo-Layout, KfW-Förderung inklusive. Läuft lokal/on-prem.

## Nutzer, Rollen & Betrieb
- Zwei Oberflächen derselben App: `/erfassung` (mobil, Außendienst) und das
  Innendienst-Tool (Desktop-Browser).
- Einfache Rollen mit leichtem Login (Benutzerliste + PIN): Außendienst sieht NIE
  Preise, EK oder Deckungsbeitrag; Deckungsbeitrag erscheint NIE im PDF.
- Zielbetrieb: Terminal Server im Rechenzentrum, App als Dienst/Autostart.
  Mobiler Zugriff: Entscheidung offen – Variante A (WireGuard-App auf Vertriebler-
  Handys, empfohlen) oder Variante B (HTTPS + Login öffentlich). Siehe PLAN_V2 Phase 16.

## Tech-Stack
Python 3.11+, FastAPI, Uvicorn · SQLite/SQLAlchemy · Jinja2 (Erfassung mobile-first)
· fpdf2 · openpyxl · Versand: Microsoft Graph API · monday.com: GraphQL (.env)

## Zentrale Dateien
- `konfigurator_logik_v2.xlsx` – Steuerdatei (ersetzt v1): Fragen mit Seiten,
  Aktionen mit AMPEL-Logik, Paketmatrix, Zusatzartikel inkl. EK-Spalte, Textregeln,
  Angebotsaufbau inkl. Vollmacht-Bedingung, NEU Blatt „Anhänge", KfW inkl.
  Ableitungsregeln. Änderungen dort erfordern keine Codeänderung.
- `Artikel-Preislisten/Angebotserstellung_Tool_mit_EK.xlsx` – **neue führende
  Preisliste** (ersetzt die alte Datei): 11 Spalten inkl. Artikelnummer, Multi,
  EK-Datum, „Einkaufspreis Material". Spalten beim Import über Header-Namen erkennen,
  nicht über feste Indizes (Layout hat sich gegenüber v1 geändert!).
- `ANGEBOTSTEXTE.md` – unverändert gültig; Vollmacht (Nachtext D) jetzt bedingt.
- `anlagen/` – PDF-Broschüren für den Versand (Regeln im Blatt „Anhänge").
- `Layout - Logo/` – Logos + Referenz-PDF. · `foerderrechner-website.html` – KfW-Referenz.

## Fragebogen & Ampel (ersetzt Konfigurator-Abbrüche)
- Seiten: Objektdaten → Alte Anlage → Neue Anlage → Heizverteilung → Elektro/ZV →
  Friondo → Förderung. IDs O/A/N/H/E/P/K lt. Logik-Excel.
- **Keine Abbrüche, keine Fehlermeldungen:** AMPEL-Antworten (14 Gründe) markieren
  die Erfassung als „individuell" mit Klartext-Grund; der Katalog läuft immer
  vollständig durch, Folgefragen-Bedingungen bleiben aktiv.
- Erfassungen landen in der Innendienst-Liste (Status Neu → In Bearbeitung →
  Erledigt) mit Ampel + Gründen. Grün: „Angebot erzeugen" (Antworten → Logik →
  Entwurf). Orange: „Manuelles Angebot" mit Protokoll-Seitenpanel. Antworten sind
  vom Innendienst korrigierbar; Erfassung bleibt mit Angebot verknüpft.
- KfW-Angaben werden abgeleitet (Objektart/WE/Fläche) und vorbelegt (Klima-Bonus
  aus Energieträger + Baujahr) – Regeln im Blatt „KfW".

## Fachliche Regeln
- Festpreise; Angebotspositionen sind Snapshots. Nummernkreis AN-C-<JJ><NNNN>
  (fortlaufend, transaktionssicher; Zählerstand aus v1 weiterführen).
- EP-Positionen: ausgewiesen mit „EP.", nicht in Summe, nicht im Deckungsbeitrag.
- **Erdleitung: berechnete Menge = Eingabe − 3 m, nie unter 0** (3 m im Fundament
  enthalten; gilt generell). Fassadenleitung: volle Meterzahl.
- **Deckungsbeitrag** je Angebot: Σ VK netto − Σ Material-EK (ohne EP), als Box mit
  € und % nur im Innendienst; Positionen ohne EK als Warnliste ausweisen.
- Beträge Decimal/Cent, 19 % USt., deutsche Formate. Gültigkeit 30 Tage.
- Status: Entwurf → Versendet → Angenommen / Abgelehnt.

## Versand (Microsoft Graph)
Versand ausschließlich durch den Innendienst: Das Tool legt den E-Mail-Entwurf im
Postfach des **angemeldeten Innendienst-Mitarbeiters** ab (Graph API, App-
Registrierung durch IT; Anleitung in docs/). Anhänge: Angebots-PDF + Dateien lt.
Blatt „Anhänge" (immer / bei HEMS / je WP-Paket). Absenden erfolgt in Outlook nach
Kontrolle; danach Status „Versendet". Übergangslösung bis Graph steht: PDF-Download.

## PDF
Wie v1 (Referenz AN250096, Blatt „Angebotsaufbau"), mit einer Änderung:
**Vollmacht-Seite (Nachtext D) nur, wenn iMSys (P02) und/oder SpotDynamic (P03)
im Angebot sind.**

## Konventionen & Nicht-Ziele
Deutsch überall; testen + abhaken + committen je Phase; Tokens/Secrets nur in .env.
Nicht-Ziele: keine Rechnungen, keine Rabattlogik, kein komplexes Rechtesystem
(einfache Rollen genügen), keine Cloud.
