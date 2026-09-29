# Projektierung – Bedienanleitung (v15, Projektierung V2)

Kurzer Leitfaden für den Alltag. Grundlage: PROJEKTIERUNG-KONZEPT.md
(abgestimmt 20.09.2026). V1 läuft als **Demo im Live-Tool**: solange der
Freigabe-Schalter auf „Nur Admin“ steht, sehen nur Admins das Modul
(Portal-Badge „Demo · Coming soon“). Freischalten: Parametrierung →
Projektierung-Einstellungen → „Alle berechtigten Rollen“.

## 1. Angebot → Projekt

- Am **angenommenen** Angebot (Editor, Liste oder Vorgangsakte) erscheint der
  Button **„Angebot → Projekt“**. Er öffnet den Anlage-Dialog:
  - **Projekt-Wahl**: neues Projekt oder das offene Projekt des Vorgangs
    (je Vorgang gibt es höchstens ein offenes Projekt).
  - **Sparten** (WP/PV/KL/WB): je Sparte entsteht ein **Gewerk**.
  - **Projektleiter** ist Pflicht; Feinplaner/Elektroplaner optional
    (sonst greifen die Standards aus den Einstellungen).
- Beim Anlegen passiert automatisch: PR-Nummer (PR-JJNNNN), Ordnerstruktur
  unter `data/projekte/<PR-Nr.>/`, Angebots-PDF-Ablage, die
  IMMER-Aufgabenpakete der Sparte, Verlaufseintrag und Benachrichtigungen.
- Wird später eine **neue Version** des Angebots angenommen, zieht das Gewerk
  automatisch nach (Auftragswert aktuell, Verlaufseintrag).

## 2. Board, Liste, Termine, Meine Aufgaben

- **/projektierung** ist das Kanban-Board: eine Karte je Projekt in der Spalte
  seines Status (= am wenigsten fortgeschrittenes offenes Gewerk). Chips je
  Gewerk zeigen Phase, Planungs-Ampel, nächsten Termin und offene/überfällige
  Aufgaben. Drag & Drop wechselt die Phase (Wächter wie in der Akte; bei
  Kombi-Projekten fragt ein Dialog, welches Gewerk gemeint ist).
- Filter: Sparte (schaltet auf Karte je Gewerk um), Projektleiter, Team,
  Kanal, PLZ-Präfix, Suche, „Storniert anzeigen“.
- **Liste**: dieselben Filter als Tabelle mit Sortierung, Summenzeile und
  CSV-Export. **Termine**: Wochen-/Monatsansicht mit Termin-Dialog
  (Montage-/Feinplanungstermine berechnen `M±N`/`FP+N`-Fälligkeiten nach).
- **Meine Aufgaben**: Überfällig · Heute · Diese Woche · Später · Neu
  zugewiesen – mit Status-Dropdown und Erledigt-Haken.

## 3. Projektakte

- Kopf: Kunde, Ausführungsadresse, Projektleiter, Kanal, Notiz.
- Je Gewerk eine Spalte: Phasen-Stepper, Ampel, Zuweisungen, Heizlast,
  Aufgaben (nach Paketen gruppiert, mit Kommentaren je Aufgabe), Termine,
  Auftrag (Positionen; EK/DB nur mit Berechtigung), Phase ändern / Storno /
  Rechnungsfreigabe.
- **Wächter** je Phasenwechsel (z. B. offene Pflichtaufgaben, fehlender
  Montagetermin): kein hartes Sperren – mit Begründung geht es weiter
  (Override wird protokolliert).
- **Rechnungsfreigabe** fragt nach Restarbeiten (Pflichtfrage); mit
  Restarbeiten entsteht eine Aufgabe (+14 Tage), die Buchhaltung wird
  benachrichtigt, das Gewerk wird „Abgeschlossen“.
- Reiter: **Dokumente** (Ordnerstruktur, Upload auch mobil),
  **Verlauf & Kommentare** (@Name erwähnt Benutzer), **Subs & Bestellungen**.

## 4. Aufgabenpakete pflegen

- Steuerdatei `daten/projektierung_logik_v1.xlsx` (Blätter Aufgabenpakete,
  Paketregeln, Ordnerstruktur, Sub-Typen). Upload/Prüfbericht unter
  Parametrierung → **Projektierung-Logik**; Änderungen wirken auf **neue**
  Paket-Aktivierungen, bestehende Aufgaben bleiben unverändert.
- V1 aktiviert die IMMER-Pakete je Sparte; weitere Pakete lassen sich in der
  Akte manuell aktivieren (die Feinplanungs-Fragen kommen ab V2).
- Fälligkeitsregeln je Schritt: `+N` (ab Aktivierung), `FP+N` (ab
  Feinplanungstermin), `M-N`/`M+N` (um den Montagetermin).

## 5. Rollen

- **Admin/Innendienst**: alles (Innendienst erst nach Freischaltung).
- **Projektierung** (Hauptrolle): Projektierung voll; Angebote, Erfassungen
  und Kunden nur lesend (Angebotsliste ohne DB-Spalte, außer das Häkchen
  „Kalk.“ ist gesetzt); Parametrierung nur Projektierung-Logik, Teams,
  Subunternehmer.
- **Montage** (Hauptrolle): nur der mobile Bereich **/montage** – „Meine
  Einsätze“ (Termine der eigenen Teams), Steckbrief ohne Preise, Foto-Upload,
  „Montage gestartet“ / „Montage fertig“ (mit Pflicht-Kurzbericht).
- **Außendienst**: am eigenen Angebot der Block „Projektstand“ (Phase, Ampel,
  nächster Termin, Projektleiter mit Telefon) + Kommentar an die Projektierung.
- **Zusatzrollen**: In der Benutzerverwaltung lassen sich projektierung/
  montage zusätzlich zur Hauptrolle anhaken (z. B. Innendienst, der auch
  projektiert); dort auch Team-Zuordnung, Telefon und Benachrichtigungs-Mail
  (aus / sofort / Tagesdigest 07:15).

## 6. Benachrichtigungen

- Glocke in der Kopfzeile (alle Rollen): Zähler + letzte 20, Klick öffnet den
  Link und markiert gelesen.
- Ereignisse: Aufgabe zugewiesen, @Erwähnung, Phasenwechsel, neues Gewerk,
  Freigabe, täglicher Fälligkeits-Lauf 07:00 (gebündelt je Benutzer).
- E-Mail je Benutzerprofil (aus / sofort / Tagesdigest 07:15) über Graph;
  Absender-Postfach in den Projektierungs-Einstellungen (Fehler stehen dort
  im Mail-Protokoll, der Versand blockiert das Tool nie).

## 7. Ablage

`data/projekte/<PR-Nr.>/` mit der Standardstruktur aus dem Konzept (3.5);
Ordner der Ebene „gewerk“ liegen je Sparte unter `<Sparte>/<Ordner>`.
Änderbar über die Steuerdatei (Blatt Ordnerstruktur), wirkt auf neue Projekte.

## Neu in V2 (v15, 26.09.2026) – Kurzüberblick

- **Phasen**: Auftragseingang → Feinplanung VOT → Planung →
  Montagevorbereitung → Montage → Abnahme & Freigabe → Abgeschlossen
  (+ Storniert). Terminstatus-Badge je Gewerk (grün terminiert /
  gelb unbestätigt / rot unterminiert), Filter in Board und Liste,
  Sichten **Board | Kalender | Chronologisch**.
- **Teams & Kalender**: Stammdaten unter Parametrierung → Teams
  (Leiter, Farbe, Outlook-Adresse). Zuweisung über „👥 Team + Termin"
  am Gewerk; der Kalender zeigt Balken je Team über die Projektdauer,
  Drag verschiebt (Zeile = Teamwechsel), ▐ zieht das Ende,
  Konfliktwarnung bei Doppelbelegung. **Outlook-Sync** in beide
  Richtungen (Einrichtung: docs/graph-einrichtung.md; Warnsymbol am
  Termin + „Erneut senden" bei Fehlern).
- **Galerie**: Ablage am Vorgang mit acht festen Ordnern; Upload mobil
  per Kamera (Vertrieb im eigenen Vorgang, Projektierung, Montage);
  der Dokumente-Reiter der Projektakte zeigt dieselbe Galerie.
- **Steckbrief** ganz oben in der Projektakte: abgeleitet aus Erfassung,
  Auftragspositionen und Feinplanung (Logik-Blatt „Steckbrief");
  Klick ins Feld = manuell überschreiben (✎, wird nie überschrieben),
  „Neu ableiten" aktualisiert den Rest.
- **Aufgabenpakete v2**: Reihenfolge = Boardspalten, das Paket der
  aktuellen Phase ist aufgeklappt. Aktionstypen an den Aufgaben:
  Radio-Auswahl (Option mit * = erledigt), Link (Portal-URLs aus der
  Parametrierung), ✉ Sub-Mail, 📅 Termin, 🖼 Galerie (hakt sich selbst
  ab, wenn alle geforderten Ordner ein Bild haben), Formular, API.
  Alte V1-Pakete tragen ein V1-Kennzeichen und lassen sich per Knopf
  entfernen. Restarbeiten/Reklamationen als Liste je Gewerk.
- **Sub-Beauftragung per Mail**: „✉ Mail senden" an den Planungs-
  Aufgaben öffnet den Dialog (Vorlage je Sub-Typ aus der Logik-Excel,
  Fotos aus den Vorlage-Ordnern auf 1600 px, Steckbrief-PDF, CC
  Projektleiter, Absender projektierung@). Antworten landen im Reiter
  „Mails"; die Akte schlägt „bestätigt" vor. Standard-Sub je Typ in
  der Parametrierung.
- **Feinplanungs-Erfassung** (Aufgabe „Feinplanungs-Erfassung" oder
  /projektierung/gewerk/<id>/feinplanung): mobil, seitenweise,
  vorbelegt aus der Vertriebs-Erfassung („vom Vertrieb" bestätigen);
  der Abschluss schreibt Steckbrief + Heizlast und setzt das Häkchen
  „Feinplanung erfasst".
- **UGL-Bestellung Collin**: „📦 Material bestellen (UGL)" erzeugt die
  Bestelldatei aus Auftrag × Blatt „Stücklisten" (Lieferdatum =
  Montagebeginn − 3 Werktage), zeigt fehlende Zuordnungen, legt sie in
  „Montagedokumente" ab; Upload in GC Online Plus manuell.
- **BzA**: Link-Aufgabe öffnet das Portal; „📋 BzA-Datenblatt" zeigt
  alle Antragsfelder mit Kopier-Buttons und Druckansicht.
- **Kunden-Terminbestätigung**: „✉ Termin an Kunden" am Montagetermin
  (Vorlage in der Parametrierung); die Antwort erzeugt den Ein-Klick-
  Vorschlag „Kunde hat geantwortet – bestätigen".
- **Montage-Backend /montage**: Team-Auswahl → Liste/Wochenkalender;
  Auftragsdetail mit Steckbrief, Galerie (ansehen + aufnehmen),
  Montage-Aufgaben, „Montage gestartet/fertig", Restarbeit melden und
  den drei Formularen (Montagebericht, Inbetriebnahme-, Abnahme-
  protokoll; Felder im Blatt „Formulare", Unterschrift auf dem Gerät,
  PDF in der Galerie „Inbetrieb-/Abnahme"). Keine Preise.

## Neu in V4 (29.09.2026) – Kurzüberblick

- **Board:** Auftragseingang in zwei Spalten – *unterminiert* und
  *terminiert* (chronologisch nach Montagebeginn). Karte von „unterminiert“
  auf „terminiert“ ziehen öffnet direkt „Team + Termin“. Alle Spalten sind
  chronologisch sortiert, Unterminierte stehen unten. Die frühere Phase
  „Abnahme & Freigabe“ ist geteilt: **Abnahme** (Montagebericht,
  IBN-Protokoll, Abnahmeprotokoll, Restarbeiten, Abweichungen/Nachtrag) und
  **Freigabe** (Rechnung freigegeben, BnD). Wechsel Abnahme → Freigabe erst,
  wenn die Pflichtaufgaben der Abnahme erledigt sind; „Rechnung freigeben“
  gibt es nur in der Phase Freigabe.
- **Ampeln:** Die *Vorlauf-Ampel* (Punkt vor dem Termin-Badge, Spalte
  „Vorlauf“ in der Liste, Filter im Board) zeigt die Zeit bis Montagebeginn:
  grün > 8 Wochen, gelb 4–8, rot < 4 oder unterminiert (Schwellen in den
  Projektierung-Einstellungen). Die *Planungs-Ampel* (Aufgabenstand) bleibt
  davon getrennt; darunter steht, ob der Wächter zur nächsten Phase erfüllt
  ist.
- **Bedienung:** Uhrzeiten im 15-Minuten-Takt. Häkchen, Auswahl, Kommentare,
  Steckbrief-Felder usw. speichern ohne Seitensprung; nach anderen Aktionen
  steht die Seite wieder an derselben Stelle.
- **Pakete:** „Montageteam zuweisen“ ist Schritt 2 im Auftragseingang (erledigt
  sich mit „Team + Termin“), „Auftragsunterlagen prüfen“ Schritt 1 in
  Planung WP. Fit for Future: HEMS / iMSys / SpotDynamic mit Ja/Nein,
  vorgewählt aus dem Steckbrief – „Übernehmen“ bestätigt. Neue
  Feinplanungs-Fragen iMSys, HEMS, Restöl; Steckbrief-Felder Restöl,
  Stemmarbeiten, Erdleitung. Sub-Mails GaLa/Entsorgung enthalten Erdarbeiten,
  Restöl und Stemmarbeiten automatisch.
- **BzA:** Aufgabe „BzA erstellen und an Kunden senden“ (nur bei gefördertem
  Auftrag): Portal ↗ · 📋 Datenblatt · **BzA erfassen** (BzA-ID, Datum, PDF →
  Galerie „Förderung“) → Kundenmail „BzA“ mit ID, Förderbetrag und KfW-Link
  (Vorlage in den Projektierung-Einstellungen; im Demo-Modus nur an die
  Test-Adresse). KfW-Antragsnummer und Zusage-Datum in der
  Montagevorbereitung (freiwillig, kein Wächter).
- **Heizreport:** Ist die API in den Projektierung-Einstellungen konfiguriert
  („Verbindung testen“), zeigt die Aufgabe „Heizlastberechnung liegt vor“
  die Knöpfe **Projekt im Heizreport anlegen** und **Ergebnis abrufen**
  (übernimmt kW, Datum, Quelle „Heizreport API“). Sonst wie bisher Link +
  Upload. Einrichtung und Anfrage an den Support: docs/heizreport-api.md.
- **UGL-Bestellung Collin:** „📦 Material bestellen (UGL)“ öffnet den
  Bestell-Dialog: Vorschau Position → Artikelnummer × Menge, rote Liste
  „ohne Zuordnung“ mit Sprung in die Stücklisten-Pflege, Lieferdatum
  (Montagebeginn − 3 Werktage), Lieferadresse (Ausführungsort | Lager),
  Bemerkung → **UGL erzeugen** (Download + Galerie „Montagedokumente“).
  Nach dem Upload in GC Online Plus „✓ hochgeladen“ mit Datum → Aufgabe
  erledigt. Jede weitere Bestellung ist eine Nachbestellung (`PR-…-2.ugl`).
- **Stücklisten-Pflege:** Parametrierung → **Stücklisten**: je
  Angebotsposition Lieferant · Artikelnummer · Bezeichnung · Menge je
  Einheit · Einheit; Filter „nur ohne Zuordnung“, Fortschritt x von y,
  CSV-Export/-Import. Speichern schreibt in das Blatt „Stücklisten“ der
  Projektierungs-Logik (Backup vorher). Oben die Go-live-Prüfpunkte
  (≥ 90 % zugeordnet, Kundennummer, „Testdatei von Collin bestätigt“).
  Format und Testdatei: docs/ugl-format.md, docs/ugl-beispiel.ugl.
- **Bestandsimport:** Für einen späteren Import bestehender Projekte gelten
  die Phasenwerte `auftragseingang`, `feinplanung_vot`, `planung`,
  `montagevorbereitung`, `montage`, `abnahme`, `freigabe`, `abgeschlossen`,
  `storniert` (`abnahme_freigabe` ist Altwert und wird von migrate.py auf
  `abnahme` umgestellt).

