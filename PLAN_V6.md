# Umsetzungsplan v6

Voraussetzung: v5 inkl. Nachträge ist live (Commit 5e3ba88). CLAUDE.md (v6)
vorher lesen. Entwicklung am Entwicklungs-PC, Auslieferung über git push +
update.bat; jede DB-Änderung idempotent in migrate.py.
Abgestimmt am 21.08.2026: Punkt „PDF-Formatierung uneinheitlich“ entfällt;
AD-Spalte in der Angebotsliste ist seit v5-Nachtrag vorhanden (anpassbar per
Dropdown) und wird mit v6 ausgerollt.

## Phase 37 – Leads: Zuordnungs-Bugfix & Vertriebskanal
- [x] BUGFIX: Personen-Zuordnung (Parametrierung) wirkt sofort rückwirkend auf
      alle vorhandenen Leads mit diesem monday-Namen (nicht erst beim nächsten
      Sync; manuelle Zuordnungen bleiben unberührt)
- [x] Automatisches Matching zusätzlich über die Benutzer-E-Mail (monday liefert
      z. T. E-Mail-Adressen wie h.becker@friondo.de als Personen-Namen)
- [x] Leads VOT: Warnhinweis „X Leads ohne Vertriebler – Zuordnung prüfen“ mit
      Link auf die Personen-Zuordnung (nur Büro-Rollen)
- [x] Vertriebskanal aus monday: Mapping-Feld „vertriebskanal“ je Board,
      Feld an Lead + Kunde, Badge/Spalte + Filter in Leads VOT, Erfassungs- und
      Angebotsliste; migrate.py
- [x] Erfassungsliste: Filter nach Vertriebler

## Phase 38 – Archiv & Status „Individuell“
- [x] Erfassungen archivieren (Innendienst/Admin): Flag + Filter „Archiv“ in der
      Erfassungsliste mit Zurückholen; Statistik-Kacheln zählen Archivierte nicht
- [x] Neuer Status „Individuell“ für Erfassungen UND Angebote: markiert Vorgänge,
      die außerhalb des Tools geschrieben werden; Setzen archiviert automatisch
      (keine „Leichen“ in den Listen); Filter zeigt sie im Archiv
- [x] Angebotsliste: Summenzeile über die gefilterte Liste – Netto, Endbetrag
      (brutto) und DB
- [x] migrate.py (Erfassung archiviert-Flag; Statuslisten erweitert)

## Phase 39 – Angebots-Editor: Texte, EP, Förderung, Löschen
- [x] Artikeltexte (Bezeichnung + Beschreibung) je Position im Editor editierbar;
      gilt nur für das Angebot, Artikelstamm bleibt unberührt
- [x] Lange Beschreibungen: gekürzte Anzeige mit „mehr…“ zum Aufklappen
      (aufgeklappt = editierbar), kein Abschneiden mehr mit „…“
- [x] EP-Kästchen je Position (wie „bauseits“): Position wird Eventualposition
      bzw. wieder normal; wirkt auf Summen/KfW/DB wie bisherige EP-Regel
- [x] Förderung anpassbar: (b) Förderbetrag manuell überschreibbar mit
      Kennzeichen „manuell“ (Eigenanteil rechnet mit dem manuellen Betrag,
      leeren = wieder automatisch); (c) Schalter „Förderblock im PDF ausblenden“
- [x] Versendete/angenommene/abgelehnte Angebote löschbar für Innendienst UND
      Admin: Sicherheitsabfrage + Lösch-Protokoll (Nummer, Kunde, Endbetrag,
      Benutzer, Zeit) in der Parametrierung einsehbar; Nummer wird nie
      wiederverwendet; migrate.py (Lösch-Protokoll-Tabelle, Förder-Override)

## Phase 40 – Angebotsverfolgung
- [x] Je Angebot: Hot-Ampel (heiß/warm/kalt/–), Wiedervorlage-Datum, Notizen-
      Verlauf (nur anhängen, mit Zeitstempel + Benutzer)
- [x] Angebotsliste: Ampel-Spalte + Filter, Wiedervorlage-Spalte (überfällig
      rot); Startseite: Kachel „Fällige Wiedervorlagen“
- [x] migrate.py (Ampel, Wiedervorlage, Notizen-Tabelle)

## Phase 41 – Statistik
- [x] Menüpunkt „Statistik“: Zeitraumwahl (Woche/Monat/Quartal/Jahr/frei),
      Kennzahlen gesamt + je Vertriebler: neue Leads, Erfassungen, Angebote
      erstellt/versendet/angenommen/abgelehnt, Summe versendet (Endbetrag),
      Summe angenommen, DB, Abschlussquote
- [x] Auswertung je Vertriebskanal (Leads, Angebote, Abschlüsse)
- [x] Außendienst sieht die Seite mit ausschließlich eigenen Zahlen
- [x] Archivierte/„Individuell“ zählen als das, was sie zuletzt waren
      (versendet bleibt versendet), tauchen aber nicht doppelt auf

## Phase 42 – HTML-Mail, Formatierung & Outlook-Signatur
- [ ] Versand als HTML-Mail (contentType html); Vorlagen-Editor mit einfacher
      Formatierung (fett, kursiv, unterstrichen, Aufzählung, Link) ohne externe
      Bibliotheken; Platzhalter funktionieren weiter; Alt-Vorlagen (Klartext)
      werden automatisch nach HTML gewandelt
- [ ] Signatur je Innendienst-Benutzer: Upload der Outlook-Signatur (HTML-Datei
      + Bilderordner, Anleitung in docs/) in der Parametrierung; Bilder werden
      als Inline-Anhänge (CID) eingebettet – Darstellung exakt wie in Outlook
      (Logo, Badges, Fotos); Fallback: Standard-Signatur der Firma
- [ ] Entwurf per Graph: HTML-Text + Signatur + Inline-Bilder + PDF-Anhänge;
      Test mit gemocktem Graph (HTML, CIDs, Anhänge)
- [ ] docs/graph-einrichtung.md bzw. docs/: Signatur-Export aus Outlook
      Schritt für Schritt (%APPDATA%\Microsoft\Signatures)

## Phase 43 – Migration, Abnahme & Rollout
- [ ] migrate.py idempotent gegen Kopie der echten DB (vor v6) und aktuellen Stand
- [ ] Regressionstests unverändert grün; Abnahmeskript um v6-Punkte erweitert
      (Individuell-Archiv, Summenzeile, Förder-Override, EP-Kästchen,
      HTML-Mail/Signatur mit Mocks, Lead-Zuordnung rückwirkend)
- [ ] docs/nach-dem-update-v6.md: ① Personen-Zuordnung prüfen (P. Diblasi als
      Benutzer anlegen oder zuordnen; Ioannis Simeonidis klären) ② Vertriebskanal-
      Spalte je Board mappen ③ Signaturen der ID-Mitarbeiter hochladen
      ④ Kurzanleitung Verfolgung/Statistik/Individuell
- [ ] git push; Rollout am Server über update.bat
