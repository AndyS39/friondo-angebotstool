# Umsetzungsplan v4

Voraussetzung: Phasen 0–23 sind umgesetzt. CLAUDE.md (v4) vorher lesen.
Je Phase: Ansatz erläutern → umsetzen → testen → abhaken → committen.

## Phase 24 – Listen, Suche & Anzeige
- [x] Suchfeld in „Leads VOT", „Erfassungen" und „Angebote" (Name, Ort, Nummer)
- [x] Angebots-Editor „Position hinzufügen": Artikel-Suche mit Autocomplete
      (Bezeichnung, Positionsnummer, Artikelnummer, Kategorie; Fallback löst
      reine Pos-/Artikelnummern direkt auf)
- [x] Angebotsliste: DB-Spalte absolut in € (statt %); Farbampel: unter 9.000 € rot,
      9.000–10.000 € orange, über 10.000 € grün; Schwellen in Parametrierung pflegbar
- [x] Erfassungsliste: Symbol, wenn ein Bemerkungsfeld (O08 oder A12) gefüllt ist,
      mit Vorschau beim Daraufzeigen
- [x] Artikelliste: EK-Spalte neben VK; fehlender EK oder VK farblich markiert +
      Hinweisbanner „n Artikel ohne EK/VK" mit Filter-Klick
- [x] Leads-Sync legt ab sofort ALLE Leads als Kunden an / aktualisiert sie
      (Duplikatabgleich Name + PLZ); Bestands-Leads per Backfill versorgt

## Phase 25 – Protokoll & Logik v4
- [x] Protokoll-PDF: Download-Button an Erfassung und Angebot; Layout schlicht
      (Kopf mit Kunde/Datum/Vertriebler, Fragen je Kategorie)
- [x] AMPEL-Markierung: Fragen, die „individuell" ausgelöst haben, im Protokoll
      (Ansicht UND PDF) farblich hervorgehoben, mit Grund-Text
- [x] konfigurator_logik_v4.xlsx einlesen: O03 (Anzahl WE) nur noch bei 2FH/MFH –
      EFH/REH/RMH automatisch 1 WE, Gewerbe ohne WE-Frage
- [x] BUGFIX bedingte Anzeige: Radio-Gruppen ohne Auswahl lieferten im Seiten-JS
      das value-Attribut des ersten Radios („Ja") – D05 erschien deshalb immer;
      behoben und die bedingte Kette (D01–D05, A05/A06-ODER-Regel, Öl-Zweig)
      systematisch im Browser durchgetestet
- [x] Darstellung: Hinweistext optisch getrennt vom Fragetext (eigener kursiver
      Block mit Randlinie)

## Phase 26 – Rabatt-Umstellung & PDF-Feinschliff
- [ ] Rabatt neu: wird als BRUTTO-Betrag nach dem Gesamt-Betrag abgezogen –
      Summenblock: Netto → 19 % USt → Gesamt-Betrag → − Rabatt → **= Endbetrag**
- [ ] KfW: förderfähige Kosten = Endbetrag; DB zieht den Netto-Anteil des Rabatts
      ab (Rabatt ÷ 1,19); Testfall: Kontroll-Szenario + 500 € Brutto-Rabatt →
      Endbetrag 34.758,95 €, Zuschuss 19.600,00 €, Eigenanteil 15.158,95 €
- [ ] docs/: Hinweis, dass auf der späteren Rechnung (TAIFUN) der Rabatt vor der
      USt auszuweisen ist
- [ ] Logos exakt wie im Referenz-PDF: Positionen/Größen der Bilder aus
      „Angebot-Nr. AN250096.pdf" auslesen (z. B. pdfplumber Image-BBoxen) und
      1:1 übernehmen (Seite 1 Logo-Leiste, Folgeseiten Logo rechts oben)
- [ ] Eigenanteil hervorheben: Zeile „Eigenanteil" fett, größer, dezente farbige
      Hinterlegung – muss auf einen Blick ins Auge springen
- [ ] BUGFIX Leerseite: Angebot AN-C-261015 (ID 16) reproduziert eine komplett
      leere Seite 5 – Seitenumbruch-Logik prüfen (Verdacht: Umbruch vor Gruppen-
      überschrift oder langer Beschreibung erzeugt Leerseite); Fix + Test mit
      genau diesem Angebot und weiteren langen Angeboten

## Phase 27 – Mail-Verlauf am Angebot
- [ ] Graph-Berechtigung Mail.Read ergänzen (docs/graph-einrichtung.md erweitern)
- [ ] Beim Versand conversationId der Angebots-Mail speichern; Abruf alle 15 Min:
      neue Nachrichten der Konversation (Fallback: Betreff enthält AN-C-Nummer)
- [ ] Angebotsliste: Brief-Symbol mit Zähler, wenn Antworten vorliegen
- [ ] Klick → Mailverlauf-Ansicht (Absender, Zeitpunkt, Textauszug), nur lesend

## Phase 28 – Fern-Signatur (Kunde signiert selbst)
- [ ] Signatur-Link in die Angebots-Mail: Einmal-Token, Gültigkeitsdauer
      (Parametrierung), Seite mit PDF-Ansicht + Signaturfeld, mobiltauglich
- [ ] Nach Signatur: wie Vor-Ort-Modus (Einbettung, Status „Angenommen",
      Ablage signiert/, Protokoll mit Zeit/IP), zusätzlich Info-Mail an den
      Innendienst-Postfachinhaber
- [ ] Aktivierungsschalter in Parametrierung; standardmäßig AUS, bis die
      öffentliche HTTPS-Adresse für die Signatur-Route steht (RZ/IT) –
      Anforderung an die IT in docs/ beschreiben (nur diese eine Route öffentlich,
      Rest bleibt intern); Alternative externer Signatur-Anbieter dokumentieren
