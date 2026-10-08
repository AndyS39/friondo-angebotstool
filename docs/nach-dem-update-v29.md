# Nach dem Update v29 (PLAN_LEAD_V4) – Lead-Management V4: Feedback-Runde 2

Dieses Update kommt **zusammen mit v28 (Projektierung V6) und dem v27-Nachtrag 2** in
einem Schritt auf den Server (ein gemeinsamer Commit, Entscheidung Andreas 07.10.2026);
die Hinweise zu Projektierung, Montage, Notizen-Chat, Klima-Versand und Anmeldeseite
stehen in `docs/nach-dem-update-v28.md`. Das Lead-Modul läuft weiter im Demo-Modus
(`lead_freigabe_modus = admin`) – Freischaltung ist nicht Teil dieses Updates. Rollout nur
im Wartungsfenster (Dienstag 22:30–23:30) nach `docs/betrieb.md`; nach `update.bat`
läuft `migrate.py` (zweimal fehlerfrei) und `scripts\smoke.bat`.

## Für das Team (Innendienst / Leadmanagement)

- **Handelsvertreter** sehen nach dem Update nur noch ihre eigene Sicht: Mein Dashboard ·
  Karte · To-Dos · Handelsvertreter. Hauptboard, Deals, Kontaktiert, Infoabend und „Mehr …“
  sind für sie weg (auch per Link: Lesezeichen laufen ins Leere, Links aus dem Tool führen
  auf „Meine Leads“).
- **„Mehr …“** in der Icon-Leiste klappt jetzt als Panel neben der Leiste auf (Escape oder
  Klick daneben schließt); auf dem Handy öffnet es nach oben.
- **Spaltenbreiten** in Hauptboard, Deals, Infoabend und Handelsvertreter-Ansicht: am rechten
  Rand eines Spaltenkopfs ziehen; Doppelklick auf den Rand = Standardbreite. Gilt nur für den
  eigenen Login.
- **Mein Dashboard** heißt „Hallo, <Vorname>“ (Vorname pflegt der Admin in der
  Benutzerverwaltung) und zeigt nur noch Fällig heute, Kommende Wiedervorlagen (alle, nach
  Datum) und Offene To-Dos; rechts der Routenplaner (Google Maps ab Friondo, Ziel selbst
  eintragen) und Meine Termine. Angebots-Wiedervorlagen stehen weiter in der
  Angebotsverfolgung/Startseite.
- **Glocke:** meldet im Lead-Modul nur noch To-Dos (mir zugewiesen bzw. mein To-Do wurde von
  jemand anderem erledigt). Neue Leads, Zuweisungen, Wiedervorlagen, Terminänderungen stehen
  in der Timeline; der Admin kann einzelne Arten in den Lead-Einstellungen wieder einschalten.
- **Terminassistent:** drei Vorschläge, der erste „Ideal“; darunter der Wochenkalender der
  Kandidaten – Klick auf einen freien Slot füllt „Manuell setzen“; „Weitere Kalender“ blendet
  andere Vertriebler ein (Buchung dort nur mit Bestätigung). Handelsvertreter tragen
  Sperrzeiten in „Meine Termine“ ein; sie blockieren Vorschläge.
- **Sammelaktion „An Handelsvertreter verschieben“** (Hauptboard, Deals, Infoabend):
  markieren, Ziel René oder Simon wählen; Leads mit Ausschlusskanal/-quelle werden
  übersprungen und gemeldet.
- **Eingangsdatum** in der Kundenkartei: „TT.MM.JJJJ, HH:MM Uhr“.
- **Notizen** der Kundenkartei sind der gemeinsame Notizen-Chat des Vorgangs (derselbe wie in
  Vorgangsakte und Projektakte, Kennzeichen „Lead“), Block in voller Breite unter den Blöcken.

- **E-Mail-Vorlagen** liegen jetzt links als Baum (Eingang · Kontakt · Terminbestätigung ·
  Termin). Unter „Terminbestätigung“ gibt es „Standard“ und je Vertriebler eine eigene
  Vorlage („Terminbestätigung – <Name>“). Beim Terminieren geht automatisch die Vorlage des
  zugewiesenen Vertrieblers raus; fehlt sie, der Standard (steht in der Timeline). Bild,
  Telefon, E-Mail und Infotext des Vertrieblers kommen aus der Benutzerverwaltung →
  AD-Profil (Bild JPG/PNG bis 2 MB) – bitte je Vertriebler pflegen. Der Platzhalter
  `{sparten_hinweise}` fügt je Interesse die Punkteliste „bitte bereithalten“ ein; bis
  Claudia die Punkte nachreicht, steht dort „(Punkte folgen)“ (Steuerdatei, Blatt
  „Terminhinweise“).
- **„Rahmen für alle Terminbestätigungen übernehmen“**: Häkchen im Editor einer
  Terminbestätigung – überträgt Betreff und Rahmen auf alle anderen, die persönlichen
  Blöcke bleiben; es kommt eine Sicherheitsabfrage mit der Anzahl.
- **Absender aller Lead-Mails ist termin@friondo.de** (Eingangsbestätigung, Nicht
  erreicht, Disqualifiziert, Terminbestätigung, Erinnerung, Änderung, Absage,
  Online-Termin). Es gibt keinen Fallback: kann termin@ nicht senden, bleibt die Mail nach
  drei Versuchen mit Status „fehler“ in der Warteschlange, der Lead steht ganz oben im
  Hauptboard mit dem roten Label **„Mail nicht gesendet“**, die Kundenkartei zeigt den
  roten Balken mit **„Erneut senden“** (der Lauf sendet in etwa einer Minute). Antworten
  der Kunden laufen jetzt auf termin@ auf und erscheinen in der Timeline („Antwort von …“)
  mit Wiedervorlage „jetzt“.
- **Unzustellbare Adresse**: Kommt ein Unzustellbarkeitsbericht, steht der Lead ganz oben
  im Hauptboard mit **„E-Mail falsch“**, das E-Mail-Feld ist rot umrandet, weitere Mails
  warten. Adresse im Kundeninfo-Block korrigieren → wartende Mails werden automatisch
  freigegeben.
- **Nurture gibt es nicht mehr**: Nach dem letzten Anrufversuch geht nur noch
  „Disqualifiziert / Nicht erreicht“ raus; eine Mail nach 30 Tagen entfällt (offene
  Nurture-Mails wurden storniert).
- **Handelsvertreter-Leads**: Terminbestätigungen werden nicht automatisch gesendet
  (Versandweg offen). Der HV bekommt ein To-Do „Terminbestätigung selbst senden“ mit Link
  auf die fertige Mail (Text zum Kopieren + ICS-Download) und sendet aus seinem eigenen
  Konto.

### Nachtrag 08.10.2026 (Antworten Andreas)
- Handelsvertreter, die einen Link auf eine Seite außerhalb ihrer Sicht öffnen (Lesezeichen,
  Mail, Tool), landen jetzt immer auf „Meine Leads“ mit dem Hinweis „Diese Seite gibt es in der
  Handelsvertreter-Sicht nicht“ – keine Fehlerseite mehr.
- Mein Dashboard: der Block „Mir zugeteilte Vorgänge“ ist weg; die Leads stehen im Hauptboard
  bzw. in der Handelsvertreter-Ansicht.
- Sperrzeiten der Handelsvertreter gelten exakt von–bis: ein Terminvorschlag darf direkt vor
  oder nach einer Sperrzeit liegen (kein 30-Minuten-Puffer wie bei Kundenterminen). Innendienst
  und Admin können Sperrzeiten für einen Handelsvertreter eintragen und löschen:
  Handelsvertreter-Ansicht → unten „Sperrzeiten der Handelsvertreter“ (Vertreter wählen, Datum,
  von, bis, Bemerkung); der HV sieht in „Meine Termine“, wer die Sperrzeit eingetragen hat.
- Antwortet ein Kunde auf eine Lead-Mail (termin@ oder leads@), kommt ein nicht erreichter oder
  zurückgestellter Lead automatisch zurück in die Kontaktierung (Timeline „Kunde hat geantwortet
  – zurück in die Kontaktierung“, Wiedervorlage „jetzt“) – danach arbeitet der Innendienst wie
  gewohnt manuell weiter.
- Antworten der Kunden auf Lead-Mails gehen jetzt an den zuständigen Leadmanager UND an
  termin@friondo.de (Reply-To) – der Leadmanager sieht die Antwort im eigenen Postfach, das Tool
  verbucht sie weiter über termin@.
- **Handelsvertreter-Leads:** Terminbestätigungen (auch Änderung/Absage) werden nicht vom Tool
  gesendet, sondern als fertige E-Mail-Datei bereitgestellt. Der HV bekommt ein To-Do
  „Terminbestätigung aus dem eigenen Postfach senden“ → Vorschau öffnen → „.eml herunterladen“
  → Datei öffnen (Outlook zeigt sie als Entwurf mit Senden-Knopf; andere Programme: „Als neu
  bearbeiten“) → prüfen → senden. Bild, Text und Kalenderanhang (ICS) sind enthalten; Absender
  ist die E-Mail-Adresse des HV aus der Benutzerverwaltung.
- Alle Lead-Seiten (auch die Kundenkartei) nutzen die volle Monitorbreite.

## Admin / Server-To-dos

- **M365 (vor der Freischaltung `lead_freigabe_modus = alle`, im Demo-Modus nur
  Testpostfach):** Shared-Postfach termin@friondo.de anlegen, „Senden als“ und „Lesen und
  Verwalten“ für die Graph-Anmeldekonten vergeben (`docs/graph-einrichtung.md`, Abschnitt
  „Lead-Management V4 (v29)“); danach einmal Versand → Abmelden → Mit Microsoft anmelden.
  Prüfen über Parametrierung → Lead-Einstellungen → Prüfpunkte V4 → „Testmail aus dem
  Lead-Absender senden“ (Ergebnis im Protokoll); `/health` und die Betriebs-Seite zeigen den
  Lauf `lead-mail-abruf` (120 s, „inaktiv (Graph nicht eingerichtet)“ ohne Graph).
- **Vorlagen und Bilder einspielen:** Zulieferung von Claudia nach
  `docs/vorlagen/terminbestaetigung/<name>.html` und `.jpg` legen (Dateiname =
  Benutzername/Vorname), dann `venv\Scripts\python scripts\vorlagen_einspielen.py` (oder
  Knopf „Terminbestätigungen aus docs/vorlagen einspielen“ in den Lead-Einstellungen, oder
  das nächste `update.bat`/`migrate.py`). Der Schritt ist wiederholbar; im Editor geänderte
  Vorlagen werden nicht überschrieben. Ohne Ordner haben alle Vertriebler die Standard-Kopie.
- **Terminhinweise nachtragen:** Steuerdatei `leadmanagement_logik_v1.xlsx`, Blatt
  „Terminhinweise“ (Spalten sparte WP/PV/KL/WB/GW, reihenfolge, punkt) – Platzhalterzeilen
  „(Punkte folgen)“ durch die Punkte ersetzen, in der Parametrierung „Steuerdatei neu
  einlesen“ (die Logik-Seite zeigt das Blatt und nennt die Sparten mit Platzhalter). Blatt
  Kaskade: Spalte `nach_letztem` (= `mail_disqualifiziert`) nur ändern, wenn nach dem
  letzten Versuch eine andere Vorlage gehen soll.
- **Benutzerverwaltung:** Vorname (alle Benutzer, „Hallo, <Vorname>“) in der Detailzeile;
  Bild und Infotext der Vertriebler im AD-Profil; Telefon/E-Mail prüfen (stehen in der
  Terminbestätigung). Parameter `hv_gruppe_rene`/`hv_gruppe_simon` (Lead-Einstellungen)
  prüfen – die Migration setzt sie per Namensabgleich.
- **Parameter prüfen:** `absender_lead_mails` (termin@friondo.de), `hv_versandweg` (offen),
  `mail_testadresse` (für Testmail und Testmodus), `glocke_lead_arten` (Standard nur To-Dos),
  `routen_start`, `vorschlaege_anzahl` (3); `absender_postfach` (leads@) bleibt nur für den
  Parser (Feld heißt jetzt „Parser-Eingangspostfach“).
- **Datenbank:** neue Statuswerte der Lead-Mail-Warteschlange `fehler`/`wartet_adresse`,
  Spalten `kommunikation_log.absender/versuche`, `vorgaenge.email_status*`/`mail_fehler*`,
  `benutzer.vorname/infotext/bild_datei` (alle additiv); Kachel „Lead-Mails mit Fehler“ auf
  der Betriebs-Seite – bei > 0 den Lead im Hauptboard prüfen. Pool-Invariante mit 14 Läufen:
  64 + 14 + 5 = 83 ≤ 90 (`.env` unverändert).
- **Nachtrag 08.10.2026:** `hv_versandweg` steht nach `migrate.py` auf `entwurf` (vorher `offen`;
  `offen` bleibt wählbar und verhält sich wie bisher). Für alle Handelsvertreter die **E-Mail-Adresse
  in der Benutzerverwaltung** pflegen – sie ist der Absender der .eml (fehlt sie, bleibt der Absender
  in der Datei leer und die Vorschau zeigt einen Hinweis). Admins erhalten bei jeder Lead-Mail mit
  Status „fehler“ (nach drei Versuchen) eine Betriebsglocke mit Link auf die Warteschlange
  (`/lead-management/kommunikation?status=fehler`) – zusätzlich zur Kachel auf der Betriebs-Seite.
