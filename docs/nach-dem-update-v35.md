# Nach dem Update auf v35 – Lead-Management V6: TAIFUN-Kundenübergabe, Vertriebskanäle, Rechte, Profilbild, Boards (PLAN_LEAD_V6, Phasen 183–187; Nachtrag 16.10.2026: ohne Objektfotos, ohne Kartei-Knopf TAIFUN,
ohne Kundennummer-Feld)

Stand 16.10.2026. v35 ist PLAN_LEAD_V6 (im Plan stand v34/178–182 – diese Nummern waren durch PLAN_V21/v34
belegt). Rollout nur im Wartungsfenster Dienstag 22:30–23:30: Wartungsbanner setzen, `update.bat`, danach
`scripts\smoke.bat`. Rückweg `rollback.bat --nur-code` (alle Datenbankänderungen sind additiv, der v34-Code läuft
auf der v35-Datenbank – Rückweg-Probe im Durchlauf).

## Für den Admin (Reihenfolge nach dem Update)

1. **Abhängigkeiten:** `update.bat` installiert `lxml`, `Pillow` und `pillow-heif` aus `requirements.txt`. Danach
   prüfen: `venv\Scripts\python -c "import lxml, PIL, pillow_heif; print('ok')"`. Ohne `pillow_heif` bleiben
   HEIC-Fotos unverändert liegen (Hinweis beim Upload), ohne `lxml` schlägt jede TAIFUN-Übergabe mit „Validierung“
   fehl.
2. **migrate.py** meldet beim ersten Lauf: Tabellen `taifun_uebergaben` und `vertriebskanaele`, Spalten
   `vorgaenge.taifun_export_*`, `kunden.taifun_kundennr`, `galerie_dateien.objekt_id` (+ Index), Lead-Parameter
   `taifun_*`, „Kanaele (v35): 30 Vertriebskanaele aus der Liste angelegt“, die Zuordnung alter Schreibweisen
   (z. B. „'SWD' -> 'Stadtwerke Düsseldorf'“) und je Bestandswert außerhalb der Liste „'<Wert>' als inaktiver
   Kanal angelegt“ – **diese Zeilen bitte notieren** (Liste der nicht mehr wählbaren Kanäle, siehe Punkt 4). Der
   zweite Lauf meldet „keine Änderungen nötig“.
3. **TAIFUN-Übergabe bleibt AUS**, bis der Import-Weg mit dem TAIFUN-Betreuer geklärt ist (Fragenliste in
   `docs/taifun-kundenexport.md`, Abschnitt 5). Vorher testen: Parametrierung → Lead-Einstellungen → Abschnitt
   „TAIFUN-Übergabe“: (a) Import-Ordner eintragen – Standard `C:\Users\kdadmin\Desktop\LM Datenimport`; liegt der
   Ordner nicht auf dem Server, Freigabe anlegen und als UNC-Pfad `\\<Rechner>\LM Datenimport` eintragen; das
   Tool läuft als Dienst `FriondoAngebotstool` unter dem Konto SYSTEM, auf einer Freigabe braucht also das
   **Computerkonto des Servers** Schreibrecht; (b) „Ordner prüfen“; (c) „Testdatei schreiben“ → Datei
   `LM_TEST_<Zeit>.xml` in TAIFUN importieren, Umlaute/ß prüfen → Häkchen „Testdatei importiert“ und „Encoding
   bestätigt“; (d) erst dann Schalter „TAIFUN-Übergabe = an“. Liegt die Original-`ADRESSEN.xsd` von TAIFUN vor:
   1:1 nach `docs\taifun\ADRESSEN.xsd` legen (kein Codeeingriff; die Datei im Projekt ist eine Rekonstruktion).
4. **Vertriebskanäle:** Lead-Management → Mehr … → Vertriebskanäle (auch über die Parametrierung): die 30 Kanäle
   sind angelegt, Farben bei Bedarf anpassen (Textfarbe passt sich an). Abschnitt „Nicht mehr wählbar“ prüfen:
   dort stehen Bestandswerte, die nicht in der Liste sind (EON, Provinzial, EnergieDigital, ZEUS Empfehlung,
   RS Versicherungen …) – Leads behalten sie; wer sie auf einen Listenkanal umhängen will, wählt den Kanal je Lead in
   der Kartei. Leads mit Kanal „?“ (Hauptboard → Chip „Kanal unklar“) klären – bis dahin sind Terminierung und
   TAIFUN-Übergabe für diese Leads gesperrt. Das Feld „Kanal-Farben (JSON)“ in den Lead-Einstellungen ist weg
   (wird aus der Tabelle abgeleitet).
5. **HV-Gruppen:** Lead-Einstellungen prüfen – `hv_gruppe_rene` (René), `hv_gruppe_simon` (Simon) und
   `hv_gruppe_simon_mitglieder` (Paolo, André, Ralf, Hartmut). Bei leerer Mitgliederliste gilt der v31-Rückfall
   „alle Handelsvertreter außer René“ – und damit auch für die Sicht: jeder neue Handelsvertreter sähe dann Simons
   Leads. Die Liste deshalb bewusst pflegen.
6. **Dienstkonto SYSTEM** braucht Schreibrecht auf `data\taifun_export\` (Kopien der XML-Dateien),
   `data\benutzerbilder\` (Profilbilder) und wie bisher `data\vorgaenge\<id>\galerie\` – alles unter `data\`,
   Backup wie bisher über `data\`.
7. **/health und Smoke:** 17 Scheduler-Läufe (neu `taifun-uebergaben`, alle 15 Minuten); Pool-Invariante
   64 + 17 + 5 = 86 ≤ 90 bleibt erfüllt.

## Für das Team

### TAIFUN-Übergabe (Innendienst/Leadmanagement)

- Sobald der Admin den Schalter einschaltet: Nach „Terminierung“ (auch in der Testphase – der Knopf ist dann aktiv
  und sagt „Testphase: nur Übergabe an TAIFUN, keine Buchung, keine Mail“) liegt der Kunde als XML-Datei im
  TAIFUN-Ordner; Badge „TAIFUN <Datum>“ im Kartei-Kopf. Einen Knopf „An TAIFUN übergeben“ gibt es in der Kartei
  nicht (Review 16.10.2026) – die Übergabe läuft nur über „Terminierung“. Bei Kanal „?“ keine Übergabe – erst den
  Vertriebskanal klären.
- Ist der Kunde vermutlich schon in TAIFUN (TAIFUN-Angebotsnummer, Bestandsimport), überspringt die Terminierung die
  Übergabe; die Zeile steht dann als „übersprungen (Rückfrage)“ in der Übergabeliste – dort „Trotzdem übergeben“,
  wenn der Kunde wirklich neu angelegt werden soll.
- Erscheint „TAIFUN-Übergabe fehlgeschlagen“ (rot in Kartei und Hauptboard oben), den Grund lesen (Ordner/Rechte),
  Admin informieren; der Balken in der Kartei führt mit „Zur Übergabeliste“ zur Liste – dort „Erneut übergeben“
  (Rückfrage mit dem Datum der letzten Übergabe: doppelte Kunden in TAIFUN vermeiden).
- Die Kundennummer aus TAIFUN wird nicht mehr im Tool nachgetragen (Feld entfallen). Übergabeliste: Lead-Einstellungen
  → „Übergabeliste“ bzw. `/lead-management/taifun-uebergaben` (Status „abgeholt“ = Datei aus dem Ordner verschwunden;
  „Als importiert markieren“ für manuelle Importe; „XML“ zeigt die Kopie; „Erneut übergeben“ je Zeile).

### Vertriebskanäle (alle Lead-Rollen)

- Dropdowns sortieren nach Häufigkeit der letzten 90 Tage; Kanal „Standard“ gibt es nicht mehr (leer = kein
  Kanal). Die Schnellanlage hat ein Kanalfeld (leer = Kanal der Quelle, sonst „?“).
- Kanal „?“ bedeutet „Vertriebskanal unklar“: Kanalfeld rot, zählt als offenes Pflichtfeld, sperrt Terminierung und
  TAIFUN-Übergabe. Im Hauptboard findet der Chip „Kanal unklar“ diese Leads.

### Außendienst: eigene Leads voll bearbeiten

- Die Kundenkartei eigener Leads (Zuständigkeit „Außendienst“ = ihr) ist jetzt voll bearbeitbar – Felder speichern
  beim Verlassen, Status über die Statuskette/„Status ändern …“, Kanal, Objekte, Notizen, To-Dos,
  Anruf-Ergebnisse, Wiedervorlage. Leads anderer Außendienstler bleiben Lesesicht. Archivieren/Duplizieren und die
  Boards bleiben beim Innendienst.

### Handelsvertreter: Gruppensicht

- René sieht nur seine Leads; Simons Gruppe (Simon, Paolo, André, Ralf, Hartmut) sieht gegenseitig alle Leads der
  Gruppe („Leads meiner Gruppe“, Filter „Vertreter“). Innerhalb der Gruppe könnt ihr im Dropdown umverteilen; ein
  Wechsel in die andere Gruppe oder das Entziehen macht der Innendienst (Sammelaktion). Terminvorschläge rechnen
  mit den Kalendern der Gruppe.

### Mein Profil (alle Rollen)

- Menü ☰ → „Mein Profil“: Profilbild hochladen (JPG/PNG, max. 2 MB; der Ausschnitt wird automatisch quadratisch
  gewählt), Vorname und Telefon eintragen, Bild entfernen. Das Bild erscheint in Boards, Kartei, HV-Ansicht,
  „Mein Tag“, Benutzerverwaltung und in der Terminbestätigung an den Kunden.

### Boards: direkt bearbeiten, Filter speichern, Sofortsuche

- Interessen, Vertriebskanal, Großkunde, Objektart (Spalte über „Spalten“ einblenden), Telefon und E-Mail lassen
  sich direkt in der Zeile ändern – Klick auf den Stift bzw. in die Zelle; jede Änderung steht als Aktivität in
  der Kartei. Rote Zellen = Pflichtfeld fehlt (Kanal „?“, kein Außendienst). Gilt für Hauptboard, Deals, Infoabend
  und die Handelsvertreter-Ansicht (jeder nur im Rahmen seiner Rechte).
- „Gespeicherte Filter“ in der Filterleiste: „Filter speichern“ (Name, Häkchen „als Standard beim Öffnen“), Stern
  = Standard, „Filter zurücksetzen“ zeigt wieder alles. Innendienst/Admin können einen Filter für alle freigeben –
  bei den anderen erscheint er schreibgeschützt mit „alle“.
- Alle Suchfelder und Filter im Lead-Management wirken sofort beim Tippen/Auswählen – kein Enter, kein
  „Filtern“-Knopf mehr. In „Kontaktiert“ gibt es nur noch eine Suchleiste: eine Ziffernfolge ab 3 Ziffern (z. B.
  „4711“) sucht Rufnummern.

### Kundensuche: alle eigenen Kunden, jeder Status (Außendienst) – Nachtrag 16.10.2026

- Die Kopfzeilen-Suche (und die Leiste „Kunden“ in „Mein Tag“) findet jetzt jeden Kunden, mit dem ihr
  verbunden seid – als Zuständiger, als Verantwortlicher des monday-Leads, über eine eigene Erfassung, einen
  eigenen Vor-Ort-Termin oder ein eigenes Angebot –, unabhängig davon, ob der Vorgang offen, gewonnen,
  verloren oder archiviert ist. Der Treffer öffnet direkt die Vorgangsakte (bisher fehlten Kunden, bei denen
  ihr nicht als Zuständiger eingetragen wart).

### Meine Termine, Erfassungen (Außendienst) – Nachtrag 16.10.2026

- „Meine Termine“ hat oben den Reiter **„Vergangene Termine“**: alle eigenen Termine vor heute (neueste
  zuerst) mit Status (Erfolgt, No-Show, Abgesagt …), Knopf „Vorgangsakte öffnen“, den eigenen Erfassungen des
  Kunden und „Neue Erfassung“.
- In der Erfassungsübersicht (Startseite „Erfassungen“) führt jede Erfassung mit dem Knopf **„Vorgangsakte“** in
  die Akte des Kunden. Eigene Erfassungen ohne verknüpftes Angebot lassen sich dort mit **„Löschen“**
  (Sicherheitsabfrage) entfernen; hängt ein Angebot daran, bleibt die Erfassung (Hinweis). Ein verknüpfter
  monday-Lead erscheint nach dem Löschen wieder in „Leads VOT“.

### Fotos (Hinweis zum Review vom 16.10.2026)

- Die mit v35 angekündigten „Fotos je Objekt“ in der Kundenkartei sind nach dem Screenshot-Review entfallen – Fotos
  laufen wie bisher über die Galerie der Vorgangsakte (Anhänge, Sammelbox, Kamera-Serie). Geblieben: iPhone-Fotos
  (HEIC) werden bei jedem Galerie-Upload automatisch in JPG gewandelt (bisher hochgeladene HEIC-Dateien bleiben HEIC).
  Bereits in Ordnern „Objekt …“ abgelegte Fotos bleiben in der Galerie sichtbar und lassen sich per „→“ in einen
  Standard-Ordner einsortieren.

## Offene Rückfragen (werden im Chat beantwortet, Details in `diagnose/v35/gesamtuebersicht.md`)

- TAIFUN: Original-XSD und Muster-XML; automatischer Ordnerimport oder manuell, Verhalten bei Dubletten, Rückgabe
  der Kundennummer; Telefon-Schreibweise und Encoding bestätigen; Vorgangsnummer „V<ID>“ in Datei/Karteikarte;
  Terminierung bei Dublette überspringen (gebaut, seit dem Nachtrag mit Zeile „übersprungen (Rückfrage)“ und
  „Trotzdem übergeben“ in der Übergabeliste – [ANNAHME N6-1]) oder direkt am Terminierungs-Klick Ja/Nein fragen;
  Beschriftung „Übergabeliste (erneut)“ für den Übergabegrund „manuell“; darf ein Außendienstler über „Terminierung“ die
  Datei auslösen; Rechner/Rechte des Import-Ordners.
- Kanäle: Alt-Kanäle (EON …) nur inaktiv lassen oder je Lead umhängen; „info“/„Kontaktformular“ →
  Kontaktformular/info; monday-Sync ohne Label künftig „?“; darf die Rolle Leadmanagement Kanäle pflegen; darf ein
  Mitarbeiter „?“ bewusst setzen.
- HV-Gruppen: Vorschläge für alle Gruppenkalender; HV-Dashboard über `?hv=` als Gruppe; „An Standard geben“ über die
  Gruppengrenze gesperrt; Vorname/Telefon selbst pflegbar; `/kalender` für HV als Gruppe; v31-Rückfall „leer = alle
  außer René“ auch für die Sicht.
- Boards: Freigabe-Recht auch für Leadmanagement; Sortierung des Standardfilters; Sichtprüfung mobil.

