# Nach dem Update v30 (PLAN_V18) – Design v2 Hell/Dunkel, Zurück-Navigation, BzA/Lieferschein/Zahlungsbedingungen, Projektierung Go-live

Dieses Update kommt als EIN Commit auf den Server (Phasen 145–152, abgestimmt 11.10.2026).
Rollout nur im Wartungsfenster (Dienstag 22:30–23:30) nach `docs/betrieb.md`; nach
`update.bat` läuft `migrate.py` (zweimal fehlerfrei, zweiter Lauf ohne Änderungen) und
`scripts\smoke.bat`. Das Lead-Management bleibt im Demo-Modus (`lead_freigabe_modus = admin`).

## Für das Team (alle Rollen)

- **Darstellung Hell/Dunkel wählen:** Menü ☰ → Bereich „Darstellung“ mit drei Knöpfen:
  **Gerät** (Standard – folgt der Einstellung von Windows bzw. Handy), **Hell** (bisherige
  Friondo-Optik) und **Dunkel** (neue dunkle Optik nach der Vorlage: ruhige dunkle Flächen,
  Karten mit feiner Kontur, cyanfarbener Hauptknopf). Die Wahl gilt sofort, wird für das eigene
  Konto gespeichert (also auch am anderen PC oder Handy nach dem Anmelden) und kann jederzeit
  zurück auf „Gerät“ gestellt werden. Die Anmeldeseite merkt sich die letzte Wahl des Browsers.
  Angebots-PDFs, Lieferscheine und alle anderen PDFs sehen unverändert aus.
- **Neue Optik (Design v2):** Karten mit feiner Kontur, große Kennzahlen mit Farbbalken,
  Status als farbige Pille mit Punkt, Sparten als farbige Chips, Avatare mit Initialen
  (Benutzerverwaltung, Boards), Tabellen ohne Zebra-Streifen mit Hover-Zeile. Inhalte,
  Reihenfolge, Formulare, Knöpfe, Rollen und Rechte sind unverändert. Auf dem Portal begrüßt das
  Tool mit Vorname, Wochentag, Datum und KW – der Vorname kommt aus der Benutzerverwaltung
  (Feld „Vorname“), sonst aus dem ersten Namensteil.
- **Zurück-Knopf:** oben links auf jeder Detail- und Bearbeitungsseite steht „← Zurück“. Er
  führt zur **vorherigen Ansicht** (nicht zur Startseite und nicht zum Neuladen derselben
  Seite): Vorgangsakte → Angebot → Zurück = Vorgangsakte; nach „Speichern“ im Angebot führt
  Zurück ebenfalls in die Vorgangsakte. Direkt aufgerufene Seiten (Lesezeichen, Link aus einer
  Mail) springen zur Liste des Bereichs (Angebot → Angebotsliste, Erfassung →
  Erfassungsliste, Projektakte → Projektboard, Einsatz → Montage-Startseite). Auf Portal,
  Modul-Startseiten, Anmeldung und im Erfassungsbogen gibt es keinen Knopf (dort bleibt die
  eigene Seitennavigation). Der Browser-Zurück-Knopf funktioniert wie bisher.

### Lead-Management, Projektierung und Montage im neuen Design

- Hauptboard/Deals/Infoabend: Der Status steht als Pille „Neu ▾“ – ein Klick auf die Pille
  öffnet wie bisher die Statuswahl (Pflichtgründe im Dialog). Außendienst/Innendienst zeigen
  den Avatar mit Initialen und Pfeil – Klick auf den Avatar öffnet die Zuweisung. Kennzeichen
  (Demo, monday, Vorab-Angebot) stehen unter dem Kundennamen. Spaltenbreite, Reihenfolge,
  Umbenennen und Sortieren funktionieren unverändert.
- Kanalfarben und Statusfarben aus der Parametrierung bleiben; im Dunkelmodus wird der Text
  automatisch aufgehellt, die Fläche ist eine Tönung der Farbe.
- Karte und Mini-Karte des Terminassistenten: Die Kartenkacheln bleiben hell (OpenStreetMap),
  Rahmen, Zoom-Knöpfe und Popups folgen dem Modus.
- E-Mail-Vorschauen (Vorlagen-Editor, Kommunikation, Kartei → E-Mail-Verlauf) bleiben hell –
  so sieht der Kunde die Mail.
- Montage-Backend: beide Modi am Handy; die Unterschrift wird weiter auf weißer Fläche
  geleistet (sie landet so im PDF).
- **Board: Karten ziehen funktioniert wieder.** Das Ziehen einer Karte in eine andere Spalte öffnete
  bisher keinen Phasen-Dialog (Fehler im Seitencode seit v17, am 12.10.2026 behoben). Ebenso
  repariert: Abbrechen im Ablehnungsdialog des Editors, „Kanal ändern“, die Kopierknöpfe der
  BzA-Gewerkseite und die Zahlungsbedingungs-Auswahl im Editor.

## Für den Innendienst (Angebotstool)

- **BzA-Datenblatt:** Frage A20 „Nennleistung der bestehenden Heizung“ ist aus dem Bogen und
  dem Datenblatt entfernt (Abschnitt 2 ohne Zeile „Nennleistung“; alte Erfassungen zeigen die
  Antwort in bereits erzeugten Angebots-Protokollen weiter, neu berechnete Protokolle führen
  die Frage nicht mehr). Das Feld **Nennwärmeleistung** ist mit dem kW-Wert der erkannten
  BAFA-Anlage vorbelegt und folgt der Geräteauswahl; nur die Zahl eingeben („9,5“ oder „9.5“
  → „9,50 kW“, „kW“ hängt das Tool an). Bei einer Eingabe wie „neun“ bleibt die Vorschau offen
  und meldet „Nennwärmeleistung: bitte nur die Zahl eingeben“. Abschnitt 4 hat die neue Zeile
  **„Geplante förderfähige Kosten inkl. 10 % Puffer“** (Kosten × 1,10, auf volle Euro
  gerundet – Puffer für einen möglichen KfW-Ergänzungskredit, ändert den Auftragswert nicht;
  im Dialog wie jedes Feld übersteuerbar, bei übersteuerten Kosten rechnet das Tool den Puffer
  daraus). Abschnitt 6 „Ersteller“ entfällt. Parametrierung: die Seite heißt jetzt
  **„BzA-Datenblatt“** und führt den Prozentsatz (`bza_kosten_puffer_prozent`, Standard 10;
  0 = Zeile entfällt).
- **Lieferschein:** die Positionen erscheinen mit vollständiger Beschreibung (alle Zeilen,
  wie im Angebots-PDF, 7,5 pt; der Tabellenkopf wiederholt sich auf Folgeseiten). Steht
  „Friondo fit for future“ (Pos. 014) auf EP, Alternativ oder bauseits, fehlen auch 015
  (HEMS), 016 (iMSys) und 017 (SpotDynamic) auf dem Lieferschein. Die Zuordnung pflegt der
  Innendienst unter Angebotstool-Einstellungen → „Lieferschein: abhängige Positionen“ (eine
  Zeile je Hauptposition, Standard `014: 015, 016, 017`; Feld leer lassen schaltet die
  Abhängigkeit ab). Im Editor steht an 015–017 der Hinweis „↳ folgt auf dem Lieferschein
  Pos. 014“ – er ändert nichts automatisch: wer 015–017 ebenfalls nicht liefern will, setzt
  014 auf EP (oder die Positionen selbst).
- **Zahlungsbedingung je Angebot:** im Editor (Kopfkarte, unter der Vertriebler-Zeile) Auswahl
  „Zahlungsbedingung“ – Standard (50 % Anzahlung 14 Tage vor Arbeitsbeginn), „50 % am
  Montagetag“, „80 % Anzahlung, 2 % Skonto“ oder „Abweichend (Freitext)“ mit Textfeld (der
  Text erscheint wörtlich unter „Zahlung“). Auswahl nur im Entwurf; bei versendeten Angeboten
  über „Überarbeiten“ (die neue Version übernimmt die Wahl). Der Nachtext des Angebots-PDF
  druckt den gewählten Text an der Stelle des bisherigen festen Absatzes (Überschrift
  „Zahlung“ bleibt); Summen, KfW und Deckungsbeitrag ändern sich nicht (Skonto wirkt nur im
  Text). Überarbeiten, Duplizieren und Kopieren übernehmen die Wahl. Die Texte pflegt der
  Innendienst unter Parametrierung → **Zahlungsbedingungen** (neue Einträge, deaktivieren
  statt löschen – deaktivierte Einträge bleiben an bestehenden Angeboten gültig, sind aber
  nicht mehr wählbar –, genau ein Standard). **Bitte die Texte 2 und 3 gegenlesen** – sie sind
  Vorschläge aus dem Plan. In E-Mail-Vorlagen steht mit `{zahlungsbedingung}` der Name des
  gewählten Eintrags zur Verfügung (Parametrierung → E-Mail-Vorlagen, Platzhalterliste). Der
  Außendienst sieht den Namen der gewählten Zahlungsbedingung lesend auf seiner Angebotsseite
  („Meine Angebote“).
- **Fehler „Überarbeiten → Duplizieren“** (Fehler-Nr. F-20261002-073115-9c9e): behoben.
  Ursache war eine kurz gehaltene Datenbank-Schreibsperre eines Hintergrundlaufs, die die
  Routen Duplizieren/Überarbeiten/Kopieren bisher ohne die übliche Wiederholung traf; jetzt
  wiederholen sie wie die übrigen Editor-Aktionen, und statt der Fehlerseite erscheint im
  Zweifel die Meldung „Datenbank kurz belegt“.

## Admin / Server-To-dos

1. **migrate.py** nach `update.bat` prüfen: Tabelle `zahlungsbedingungen` (3 Einträge),
   Spalten `angebote.zahlungsbedingung_key/_text`, `angebots_loeschungen.art/grund`,
   Parameter `bza_kosten_puffer_prozent = 10` und `lieferschein_folgepositionen`,
   Nachtext-Migration: die Meldung nennt Textblöcke, in denen der Standard-Zahlungsabsatz
   **nicht** wörtlich gefunden wurde – dort unter Parametrierung → Angebotsprofile →
   Textblöcke den Platzhalter `{zahlungsbedingungen}` von Hand an die Stelle des
   Zahlungsabsatzes setzen (sonst druckt dieses Profil weiter den alten festen Text). Die
   Seite Parametrierung → Zahlungsbedingungen zeigt dafür dauerhaft einen Warnblock, solange
   solche Blöcke existieren. Auf der Entwicklungs-DB hat die Migration alle 12 Standard-Blöcke
   umgestellt.
2. **Parameter prüfen:** Parametrierung → BzA-Datenblatt (Puffer 10 %), Angebotstool-
   Einstellungen (abhängige Lieferschein-Positionen), Zahlungsbedingungen (Texte 2 und 3
   gegenlesen lassen).
3. **Vornamen pflegen:** Benutzerverwaltung → Feld „Vorname“ (Begrüßung auf dem Portal,
   Terminbestätigungen); danach einmal im Dunkelmodus durch Portal, Angebotsliste, Editor und
   mobile Erfassung klicken.
4. **Fehlerprotokoll:** den Original-Eintrag F-20261002-073115-9c9e unter Parametrierung →
   Fehlerprotokoll (oder `data\fehler.log`) einmal gegenlesen – erwartet `OperationalError …
   database is locked` bei `POST /angebote/<id>/duplizieren` – und als erledigt betrachten.
5. **Demo-Projekte löschen (Go-live der Projektierung):** Projektierung → Liste → Filterchip
   „Demo“ setzen. Die Demo-Projekte (Kunden „Demo Planung, Petra“ / „Demo Montage, Bernd“
   aus `scripts/demo_projekte.py`, Badge „Demo“) links anhaken → „🗑 Ausgewählte löschen“ →
   Grund eintragen (z. B. „Demo-Daten vor dem Go-live“), zur Bestätigung LÖSCHEN eingeben.
   Einzelne Projekte lassen sich auch in der Projektakte über den roten Knopf „Projekt
   löschen“ (ganz rechts in der Aktionsleiste, Projektnummer zur Bestätigung) entfernen. Nur
   Admins sehen diese Knöpfe. Gelöscht werden Gewerke, Aufgaben, Termine (Outlook-Einträge
   werden storniert, falls gesynct), Besetzungen, Verlauf, Steckbrief, Kommentare,
   Benachrichtigungen und Dokumente der Akte; der Projektordner wandert nach
   `data\projekte\_geloescht\<PR>_<Datum-Uhrzeit>\` (von Hand aufräumen, wenn sicher nicht
   mehr gebraucht). Das Angebot bleibt mit seinem Status bestehen und zeigt wieder „Angebot →
   Projekt“; Galerie-Fotos bleiben am Vorgang. Jede Löschung steht im Lösch-Protokoll
   (Parametrierung → Angebotstool-Einstellungen → Lösch-Protokoll, Art „Projekt“ mit Grund)
   und als Notiz im Vorgangs-Chat. Nicht löschbar sind Projekte mit einem Gewerk in Montage/
   Abnahme/Freigabe, das schon einen abgeschlossenen Montagebericht hat – dort „Stornieren“
   verwenden. Die Demo-Angebote AN-DEMO-2601/2602 und die Demo-Kunden können danach wie
   gewohnt über die Angebotsliste bzw. Kundenkartei entfernt werden (nicht automatisch).
   Hinweis: Auf der Server-Kopie vom 03.10.2026 gab es **keine** Demo-Projekte (nur in der
   Entwicklungs-DB) – der Schritt ist dann in Sekunden erledigt.
6. **Bestandsimport** (Parametrierung → Bestandsimport) für laufende Aufträge durchführen,
   falls noch nicht geschehen (Punkt 11 der Checkliste).
7. **Go-live-Checkliste** (Parametrierung → Go-live-Checkliste) auf 11/11 bringen oder
   Ausnahmen bewusst entscheiden. Auf der Server-Kopie vom 03.10. war nur „Montageteams mit
   Mitgliedern“ grün; offen: Testmail über projektierung@ (M365-Absender), Outlook-Kalender-
   Modus + Test-Termin, ein Benutzer mit Rolle Projektierung, Standard-Subunternehmer je Typ
   (aktiv, mit E-Mail), fünf Portal-URLs, Collin-Kundennummer, Stücklisten-Quote (seit der
   v28-CSV neu prüfen), Collin-Testdatei (Häkchen), Formulare abgenommen (Häkchen),
   Bestandsimport.
   **Pflicht vor dem Umlegen des Schalters** (Entscheidung 12.10.2026): Benutzer je Rolle
   Projektierung/Montage, Montageteams, Standard-Subunternehmer je Typ, Portal-URLs,
   Collin-Kundennummer, Montage-Formulare mit einem Monteur abgenommen, Demo-Projekte gelöscht,
   Bestandsimport der laufenden Aufträge. **Begründete Ausnahmen** (Zulieferungen, dürfen nach
   dem Go-live nachgeholt werden): Testmail über projektierung@ (M365-Absender), Outlook-
   Test-Termin (bis dahin Kalender-Modus „aus“ – Termine stehen nur im Tool), Collin-Testdatei
   (UGL-Bestellung bis dahin manuell), Stücklisten-Quote (Zahl nach dem Update neu lesen; unter
   90 % nur, wenn die fehlenden Positionen bekannt sind).
8. **Go-live-Schalter:** Parametrierung → Projektierung-Einstellungen → Abschnitt „Freigabe
   & Pilot“ → **`freigabe_modus = alle`** → Speichern. Wirkung sofort: das Badge „Demo · Coming
   soon“ auf dem Portal verschwindet, Innendienst/Außendienst/Projektierung sehen das Modul
   (Außendienst nur den Projektstand am eigenen Angebot), Montage-Logins landen in `/montage`,
   die BzA-Kundenmail geht echt an den Kunden statt an `projekt_testadresse`. Das
   Lead-Management bleibt davon unberührt (`lead_freigabe_modus = admin`). Rückweg:
   `freigabe_modus` wieder auf `admin` oder `pilot` (+ Pilotliste) – Daten bleiben erhalten.
9. **Darstellung:** keine Server-Einstellung nötig; die Wahl liegt je Benutzer in
   `benutzer_einstellungen` (Key `darstellung`) und als Cookie `darstellung` (1 Jahr).
10. **Rückweg des Updates:** `rollback.bat --nur-code` – der v29-Code läuft auf der
    v30-Datenbank weiter (nur additive Migrationen); der Platzhalter `{zahlungsbedingungen}`
    würde dann im PDF wörtlich erscheinen – vor einem Rückweg die Nachtexte in der
    Parametrierung prüfen.
