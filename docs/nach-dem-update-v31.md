# Nach dem Update v31 (PLAN_LEAD_V5) – Lead-Management V5: Objekte, Großkunde, Kartei neu, Archiv, Vorlagen, Testphase

Dieses Update kommt zusammen mit v32 (PLAN_V19, siehe `docs/nach-dem-update-v32.md`) als EIN
Commit auf den Server (Phasen 153–160, abgestimmt 13.10.2026). Rollout nur im Wartungsfenster
(Dienstag 22:30–23:30) nach `docs/betrieb.md`; nach `update.bat` läuft `migrate.py` (zweimal
fehlerfrei, zweiter Lauf ohne Änderungen) und `scripts\smoke.bat`. Die Migration legt je Vorgang
ein „Hauptobjekt“ (= Kundenadresse) an, setzt die Leadmanager-Häkchen für die sechs Startnamen,
schaltet das Lead-Management für alle Rollen frei (`lead_freigabe_modus = alle`) und lässt die
Testphase-Schalter auf **aus**.

## Für das Team (alle Rollen)

- **Lead-Management ist freigeschaltet:** alle Rollen laut Rechte-Matrix sehen das Modul; die
  Startkarte trägt kein „Demo“-Badge mehr. **Testphase:** Der Terminassistent rechnet echt, aber
  Vormerken, Buchen, Absagen, Umbuchen, „Terminierung“ und Vorab-Gespräche sind ausgegraut
  („Testphase: …“), und keine Vorlagen-Mail wird verschickt – die Einträge stehen mit Status
  „gesperrt“ in der Warteschlange (Vorschau im E-Mail-Verlauf sichtbar). Beides schaltet der Admin
  unter Lead-Einstellungen → „Freischaltung“ frei, wenn die Prüfpunkte dort grün sind.
- **Kundenkartei neu sortiert:** oben Notizen (zwei Drittel) und To-Dos (ein Drittel), darunter
  die Kundeninformationen mit dem Block **„Objekte“**. Hat ein Kunde mehrere Objekte (z. B. EFH und
  ein MFH), legt ihr sie über „Weiteres Objekt hinzufügen“ an – jedes Objekt bekommt eigenen Termin,
  Erfassung und Angebot; Objekt 1 ist immer die Kundenadresse. Der Reiter „Termin“ ist in den Block
  „Termine“ gewandert (Vorschläge, Kalender, Historie); die Reiter heißen Anruf · E-Mail · Timeline
  (die Timeline zeigt auch Angebots- und Projekt-Einträge mit Herkunfts-Badge). Den Status setzt ihr
  direkt in der Kartei (Klick auf einen Schritt oder „Status ändern …“; Zurückgestellt braucht Datum
  und Grund, Disqualifiziert und Verloren einen Grund). **Außendienst ist Pflichtfeld** – ohne
  Zuweisung bleibt „Terminierung“ gesperrt (bei Handelsvertreter-Leads gilt der Vertreter). Bei
  Mehrfamilienhäusern fragt die Kartei, ob die Rechnungsadresse der Objektadresse entspricht. Die
  Schnellaktion „E-Mail“ öffnet einen Dialog mit Vorlagenwahl und ausgefüllter Vorschau.
  Wiedervorlage- und Rückruf-Uhrzeiten gibt es in 5-Minuten-Schritten. Das Häkchen „Großkunde“
  setzt das Badge in Boards und Kartei.
- **Termine bei mehreren Objekten:** je Objekt einen Termin vormerken (Objekt oben im Assistenten
  wählen) und einmal „Terminierung“ klicken – alle vorgemerkten Objekttermine werden gebucht; liegen
  die Termine am selben Tag, bekommt der Kunde eine Mail mit allen Objekten (ein Kalendereintrag je
  Objekt), sonst je Objekt eine Bestätigung mit der Objektadresse (umschaltbar). Der Assistent plant
  nur Montag bis Freitag; ein Samstag ist manuell nur mit Warnhinweis buchbar. Kranke Vertriebler
  werden nicht vorgeschlagen; „Umbuchen“ aus „Fällig heute“ öffnet den Assistenten ohne den Kranken.
- **Mails:** Die Mail „Nicht erreicht“ gibt es nicht mehr – nach Versuch 2 und 4 geht keine Mail,
  nur nach dem letzten Versuch „Disqualifiziert“. Sparten stehen in Kundenmails ausgeschrieben
  („Wärmepumpe und Photovoltaik“). „Falsche Nummer“ schickt dem Kunden (wenn eine E-Mail vorliegt)
  die Bitte um die richtige Nummer. Der Status „Unqualifiziert“ heißt jetzt „Disqualifiziert“.
- **Boards:** Badge und Filter „Großkunde“; Spalte „Großkunde“ einblendbar; die horizontale
  Scrollleiste ist immer am unteren Bildschirmrand (zusätzlich Shift + Mausrad, Ziehen mit der
  mittleren Maustaste); Sammelaktionen „Archivieren“ (Leads mit aktivem Termin/offener Erfassung/
  offenem Angebot werden übersprungen und gemeldet), „Duplizieren“ (neuer Vorgang am selben Kunden,
  Kennzeichen „Kopie von“) und im Filter „Archiv“ „Wiederherstellen“. Das Deals-Board zeigt bei
  mehreren Objekten Erfassung/Angebot/Termin je Objekt. Archivierte Leads bleiben im Angebotstool
  sichtbar (Banner mit „Wiederherstellen“ in der Vorgangsakte).
- **Mein Dashboard:** Stift oben rechts → Kacheln per Drag & Drop sortieren, Haken speichert (je
  Nutzer), „Zurücksetzen“; „Fällig heute“: Erledigt-Knopf rechts in der Zeile, Zeile wird
  durchgestrichen, „Rückgängig“; Hinweis „Krankheit: <Name>“ mit Umbuchen/Absagen; Karte
  „Abwesenheit“ für den eigenen Krankheits-/Urlaubseintrag (auch auf „Meine Termine“ des
  Außendienstes).
- **Zuständige:** Leadmanager-Dropdowns zeigen nur Benutzer mit dem Häkchen „Leadmanager“;
  Außendienst-Dropdowns zeigen keine Handelsvertreter mehr – bei HV-Leads nur die Gruppe des
  Vertreters.
- **Sparten:** Mieterstrom (MS), Wasser (WA), Denkmalschutz (DMS) in Kartei, Schnellanlage, Import,
  API, Filtern und Berichten; im Angebotstool starten sie immer als Freitext-Erfassung.
- **Anrufliste/Kontaktiert:** Rufnummernsuche ab 3 Ziffern (Endziffern zuerst, archivierte Leads
  markiert).
- **Angebotstool/Projektierung:** Bei Vorgängen mit mehreren Objekten zeigen Angebots-PDF,
  Lieferschein, BzA und Heizreport die Adresse des gewählten Objekts als Ausführungsort (Empfänger
  bleibt der Kunde); „Erfassung starten“ fragt bei mehreren Objekten das Objekt ab. Die
  Vorgangsakte gruppiert Erfassungen und Angebote je Objekt und zeigt im Notizen-Chat auf Wunsch
  („alles“) auch Anrufe, E-Mails, Termine und den Projekt-Verlauf. Für Ein-Objekt-Vorgänge ändert
  sich an PDFs nichts.

## Für Innendienst und Admin – To-dos nach dem Update

1. **Demo-Ende-Abfrage beantworten:** Beim ersten Öffnen der Lead-Einstellungen fragt das Tool
   einmal „Demo-Leads löschen oder behalten“ (Vorbelegung löschen – nur Generator-Leads ohne
   Erfassung/Angebot/Projekt; jede Löschung steht im Lösch-Protokoll).
2. **Benutzerverwaltung:** Häkchen „Leadmanager (Innendienst-Auswahl)“ prüfen (die Migration setzt
   es für die sechs Startnamen; fehlende Namen stehen im Migrationsprotokoll); HV-Gruppen
   (`hv_gruppe_rene`, `hv_gruppe_simon`, `hv_gruppe_simon_mitglieder`) prüfen; Krankheit/Urlaub je
   Benutzer unter „Details ▾ → Abwesenheiten“ eintragen und beenden; AD-Profile haben keinen
   Samstag mehr.
3. **Freischaltung** (Lead-Einstellungen → „Freischaltung“): Schalter „Terminierung aktiv“ und
   „Mailversand aktiv“ erst setzen, wenn die Prüfpunkte (Senderecht termin@, `kalender_sync`,
   Routing-Dienst, Leadmanager-Häkchen, HV-Gruppen, AD-Profile Mo–Fr) grün sind. Gesperrte Einträge
   werden danach nicht automatisch nachgesendet (bei Bedarf „Erneut senden“); `mail_modus` steuert
   nichts mehr.
4. **Vorlagen gegenlesen:** „Terminbestätigung – mehrere Objekte“ und „Falsche Telefonnummer“ (neu),
   Sparten-Langnamen über Parameter `sparten_langnamen` pflegbar; nach `migrate.py` die Meldungen
   „v31: Vorlage …: WP → Wärmepumpe“ prüfen.
5. **Farbe „Großkunde“** (Parameter `grosskunde_farbe`, leer = Violett) bei Bedarf setzen.
6. **Steuerdatei:** Blatt Terminhinweise – Zeilen MS/WA/DMS tragen „(Punkte folgen)“, Blatt
   Wunschzeiten hat die Spalte `aktiv` (samstag = nein).

## Rollback

`rollback.bat --nur-code` stellt den v30-Code wieder her; die v31/v32-Datenbank läuft damit weiter
(nur additive Spalten/Tabellen/Trigger – in der Rollout-Vorbereitung geprüft).
