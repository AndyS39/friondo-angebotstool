# Umsetzungsplan Lead-Management V6: Kundenübergabe an TAIFUN (XML-Export nach ADRESSEN.xsd bei Terminierung); Nachtrag 15.10.: Vertriebskanal-Stammdaten, Rechte Außendienst/HV-Gruppen, Inline-Bearbeitung, gespeicherte Filter, Profilbild, Objektfotos

> **Nummernhinweis 15.10.2026 (Claude Code):** PLAN_V21 wurde vor diesem Plan als **v34, Phasen 178–182**
> gebaut (nächste freie Nummern der Zuordnungstabelle in CLAUDE.md). Bei der Umsetzung dieses Plans
> gelten deshalb **v35 und Phasen 183–187** – im Text unten am 15.10.2026 durchgängig ersetzt
> (Nummern geprüft 15.10.2026, Claude Code).

Voraussetzung: kein anderer Plan in Umsetzung (strangübergreifend). Stand
15.10.2026: v31 (PLAN_LEAD_V5, Phasen 153 bis 160) und v32 (PLAN_V19, Phasen
161 bis 165) laufen als gemeinsamer Durchlauf bzw. stehen vor dem Rollout;
danach folgt PLAN_V20 (v33, Phasen 166 bis 177). **Dieser Plan kommt nach
v33** und setzt auf dessen committetem Stand auf (Objekte am Vorgang und
Testphase aus v31, Lead-Nachträge aus v33 Phase 175). Vor der Übergabe fragt
der Planungs-Chat erneut ab, ob v31, v32 und v33 committet, gepusht und auf
dem Server sind. CLAUDE.md und `leadmanagement_logik_v1.xlsx` sind
Live-Master im Projektordner `C:\Users\a.scheelen\Tools\Angebotstool`
(Git-Arbeitskopie). ALLE PHASEN DIESES PLANS IN EINEM DURCHLAUF UMSETZEN
(Reihenfolge einhalten, jede Checkbox nach Umsetzung und Test abhaken, am
Ende Gesamtübersicht mit Testergebnissen und offenen Punkten, fachliche
Rückfragen gebündelt). **Ein gemeinsamer Commit am Ende**, migrate.py
idempotent, **nur additive Migrationen** (v35-Code muss auf der
v35-Datenbank weiterlaufen, Rückweg `rollback.bat --nur-code`). **Kein git
push vor Freigabe.**

CLAUDE-Abschnitt: **„Neu in v35“** [ANNAHME: v31 = PLAN_LEAD_V5, v32 =
PLAN_V19, v33 = PLAN_V20; vor dem Bau gegen die Zuordnungstabelle prüfen,
bei Abweichung die nächste freie Nummer nehmen]. Phasen **183 bis 187**
[ANNAHME: 166 bis 177 gehören zu PLAN_V20; bei Abweichung die nächsten
freien Nummern nehmen und durchgängig ersetzen]. Die v27-Regeln gelten
(`def`-Routen, keine offene Datenbanksitzung während Datei- oder Netz-I/O,
Scheduler-Rahmen, Wächter-Test `tests/test_v27_sitzungen.py` grün,
Inventartabelle `docs/betrieb.md` um den Export-Ordner ergänzen), die
v30-Regeln für Oberflächen (Tokens Hell/Dunkel).

Geltungsbereich: Modul Lead-Management (Kundenkartei, Boards, Button
„Terminierung“, Lead-Einstellungen, Rechte-Matrix, HV-Sicht), ein neues
Modul `app/taifun_export.py`, ein Scheduler-Job, die Vertriebskanal-
Stammdaten (Parametrierung, Kanal-Farben, Angebotsprofil-Zuordnung nur
lesend), Benutzereinstellungen (Profilbild) und die Galerie des Vorgangs
(Objektfotos) sowie die Doku. Keine Änderung an
Angebotstool, Projektierung, TAIFUN-Import der Artikel/Preislisten,
Bestandsimport, monday-Sync oder monday-Rückspielung. Die Testphase aus
v31 (Phase 159: Buchen und Mailversand gesperrt) bleibt bestehen; der
TAIFUN-Export läuft **trotz** gesperrter Buchung.

## Entscheidungen (Chat Lead-Management, 14./15.10.2026, Claudia Castro)

- **Bei Terminierung wird der Kunde in TAIFUN angelegt**, indem das Tool den
  Lead als XML-Datei nach dem TAIFUN-Schema `ADRESSEN.xsd` (Wurzel
  `AdList`, Einträge `Ad`, Namensraum `urn:taifun-software.de:schema:TAIFUN`)
  in den Ordner **`C:\Users\kdadmin\Desktop\LM Datenimport`** schreibt. Die
  XSD liegt vor (Felder: Kunde ja/nein, Name 3, Straße, Hausnummer, PLZ,
  Ort, Briefanrede, E-Mail, Telefon, Mobil, Karteikarte).
- **Name 3 = „Vorname Nachname“**; die Anrede (Herr/Frau) geht nur über die
  Briefanrede nach TAIFUN („Sehr geehrter Herr Schliwa,“), weil die XSD
  keine Felder für Anrede, Vorname und Nachname hat.
- **Auslöser: Klick auf „Terminierung“, auch in der Testphase.** Der Button
  bleibt für Buchung und Mail gesperrt (v31), erzeugt aber bereits die
  TAIFUN-Datei, damit der Export sofort getestet werden kann. Zusätzlich
  Button „An TAIFUN übergeben / erneut übergeben“ in der Kundenkartei.
- **Import-Weg in TAIFUN [ANNAHME, Rückfrage unbeantwortet]:** Das Tool legt
  die Datei ab und führt eine Übergabeliste; ob TAIFUN den Ordner
  automatisch liest oder ein Mitarbeiter den Import manuell startet, ist
  mit dem TAIFUN-Betreuer zu klären [OFFEN 1]. Der Plan baut beides
  tauglich: Ablage plus Liste „TAIFUN-Übergaben“ mit Status; eine Datei,
  die aus dem Ordner verschwindet, gilt als abgeholt.
- **Keine Rückmeldung aus TAIFUN** (Kundennummer zurück ins Tool) in diesem
  Plan; vorbereitet als Feld `kunden.taifun_kundennr` zum manuellen
  Nachtragen [OFFEN 2].

- **Nachtrag 15.10.2026 (Claudia Castro):**
  - **Außendienst darf die Lead-Kartei anpassen wie der Innendienst**: an
    eigenen Leads alle Felder inkl. Status, Zuständige, Kanal, Objekte,
    Notizen, To-Dos (nicht: Archivieren, Löschlauf, Parametrierung).
  - **Hauptboard: Zeilen direkt bearbeiten** (z. B. Interessen ändern, ohne
    die Kartei zu öffnen) und **Filter speichern** je Nutzer.
  - **HV-Gruppensicht:** René sieht nur seine Leads; alle Mitglieder von
    Simons Gruppe (Simon, Paolo, André, Ralf, Hartmut) sehen gegenseitig
    alle Leads der Gruppe; keine Gruppe sieht die andere. Innendienst/Admin
    sehen alles.
  - **Profilbild** in den eigenen Benutzereinstellungen hochladen (dient
    Avataren und der Terminbestätigung je Vertriebler, v29).
  - **Vertriebskanäle werden Stammdaten** mit Farbe, bearbeitbar, löschbar,
    erweiterbar, in Dropdowns nach Häufigkeit sortiert. Übernahme aus den
    monday-Labels (Bilder vom 15.10.) mit ähnlichen Farben; **nicht
    übernommen** (gelöscht): EON, Provinzial, EnergieDigital, ZEUS
    Empfehlung, RS Versicherungen. Leads, die einen gelöschten Kanal tragen,
    behalten ihn (Label bleibt sichtbar, nicht neu wählbar). EnergieDigital
    wird durch „ED - Google“ und „ED - Meta“ ersetzt. Kanal „?“ bedeutet
    „Vertriebskanal unklar“ und macht den Kanal zum rot markierten
    Pflichtfeld, bis ein echter Kanal gewählt ist. Kanal „Standard“ entfällt
    als Label; das Angebotsprofil „Standard“ bleibt Fallback.
  - **Fotos je Objekt** hochladen (Galerie am Objekt).
  - **Kontaktiert: eine Suchleiste** für Name, Ort und Rufnummer, keine
    separate Rufnummernleiste; **Sofortsuche beim Tippen ohne Enter**, das
    gilt für alle Suchfelder und Filter im Lead-Management.

## Phase 183: TAIFUN-Kundenexport

- [x] **Schema und Generator:** `ADRESSEN.xsd` nach `docs/taifun/ADRESSEN.xsd`
      legen (unverändert, Herkunftsnachweis). Modul `app/taifun_export.py`
      mit `xml_fuer_vorgang(vorgang_id) -> bytes` und
      `exportieren(vorgang_id, benutzer_id, grund)`. Datei: XML-Deklaration
      mit **`encoding="windows-1252"`** (wie die XSD; Umlaute und ß bleiben
      als Zeichen, keine Entities) [ANNAHME: TAIFUN erwartet dieselbe
      Kodierung wie die XSD; vor dem Rollout mit einer Testdatei im
      TAIFUN-Import prüfen, bei Fehlschlag auf UTF-8 umschaltbar über
      Parameter `taifun_export_encoding`]. Wurzel `<TAIFUN:AdList
      xmlns:TAIFUN="urn:taifun-software.de:schema:TAIFUN">` mit genau einem
      `<TAIFUN:Ad>` je Datei (ein Lead = eine Datei), Elementreihenfolge
      exakt wie im Schema, leere Felder weggelassen. Jede Datei wird vor
      dem Schreiben **gegen die XSD validiert** (lxml); Validierungsfehler
      verhindern das Schreiben und erscheinen als Fehler am Vorgang.
      Längen laut Schema werden eingehalten (Name 60, Straße 60, Hausnummer
      20, PLZ 10, Ort 60, Briefanrede 200, E-Mail 80, Telefon/Mobil 30);
      längere Werte werden gekürzt und der Kürzungshinweis in die
      Karteikarte und die Aktivität geschrieben.
- [x] **Feldzuordnung Lead → Ad** (wörtlich so umsetzen):
      - `KdUse` = `true`.
      - `Name3` = „<Vorname> <Nachname>“ (ohne Anrede; nur Nachname, wenn
        kein Vorname; bei Firmenkunden/Großkunde mit Firmenname: Firmenname
        [ANNAHME: Feld `kunden.firma`, falls vorhanden, sonst Name]).
      - `AnschriftStr` = Straße ohne Hausnummer, `AnschriftHNr` = Hausnummer
        inkl. Zusatz („12a“, „63-65“); Trennung aus dem Straßenfeld des
        Tools mit der bestehenden Adress-Parser-Logik (v20 Anschriften:
        „Straße + Nr.“); ist die Hausnummer nicht sicher erkennbar, bleibt
        `AnschriftHNr` leer und das ganze Straßenfeld steht in
        `AnschriftStr` plus Hinweis in der Karteikarte.
      - `AnschriftPLZ`, `AnschriftOrt` aus der **Rechnungsadresse**, falls
        eine abweichende hinterlegt ist (MFH, v20/v31), sonst aus dem
        Hauptobjekt bzw. der Kundenadresse [ANNAHME: TAIFUN-Kunde =
        Rechnungsempfänger; Objektadressen gehen in die Karteikarte].
      - `Anrede` = bestehender Baustein {briefanrede} („Sehr geehrter Herr
        <Nachname>,“ / „Sehr geehrte Frau <Nachname>,“ / Fallback „Sehr
        geehrte Damen und Herren,“).
      - `EMail` = E-Mail des Leads (nur wenn `email_status` nicht
        `ungueltig`, v29; sonst leer plus Hinweis).
      - `Telefon` / `Funk`: Das Tool führt eine Nummer je Lead. Nummern mit
        deutscher Mobilvorwahl (015x, 016x, 017x bzw. +4915/16/17) gehen
        nach `Funk`, alle anderen nach `Telefon`; Formatierung national
        („0203 3965710“), E.164 nur intern [ANNAHME: Schreibweise; TAIFUN-
        Muster nachreichen, falls anders gewünscht]. Gibt es in v33
        (Phase 175) ein zweites Nummernfeld, werden beide befüllt.
      - `Kartei` = mehrzeiliger Freitext, Zeilen in dieser Reihenfolge:
        „Übergabe aus dem Friondo-Tool am <TT.MM.JJJJ HH:MM> durch
        <Benutzer>“ · „Lead/Vorgang: <Vorgangsnummer>“ · „Vertriebskanal:
        <Kanal>“ · „Interessen: <Langnamen>“ · „Objekt(e): <Bezeichnung,
        Objektart, Parteien, Adresse> je Zeile“ (v31) · „Vertriebler:
        <Name>“ · „Vor-Ort-Termin: <Datum, Uhrzeit> je Objekt“ (bei
        gesperrter Buchung: „vorgemerkt: …“) · „Quelle: <Quelle/Kampagne>“ ·
        „Großkunde: ja“ (falls gesetzt) · Kürzungs-/Parserhinweise.
        Keine Notizen, Anrufprotokolle oder Preise.
- [x] **Zielordner und Schreiben:** Parameter `taifun_import_ordner`
      (Lead-Einstellungen, Abschnitt „TAIFUN-Übergabe“, Standard
      `C:\Users\kdadmin\Desktop\LM Datenimport`), Parameter
      `taifun_export_aktiv` (Standard an). Prüfung beim Speichern des
      Parameters und per Button „Ordner prüfen“: existiert, beschreibbar
      (Testdatei schreiben und löschen). **Hinweis:** Der Pfad liegt im
      Benutzerprofil `kdadmin`; das Tool läuft als Dienst auf fr-wts-02
      (v27). Ist der Ordner vom Dienstkonto nicht erreichbar, muss der
      Ordner freigegeben und als UNC-Pfad (`\\<Rechner>\LM Datenimport`)
      eingetragen werden [OFFEN 3, IT: Rechner und Berechtigung des
      Dienstkontos]. Dateiname `LM_<Vorgangsnummer>_<JJJJMMTT-HHMMSS>.xml`
      (nur A bis Z, 0 bis 9, Unterstrich, Bindestrich). Schreiben atomar
      (temporäre Datei `.tmp` im selben Ordner, dann Umbenennen), niemals
      eine vorhandene Datei überschreiben. Datei-I/O außerhalb der
      Datenbanksitzung (v27-Regel). Fehler (Ordner fehlt, keine Rechte,
      Validierung) → Vorgang erhält `taifun_export_status = fehler` mit
      Grund, rotes Label **„TAIFUN-Übergabe fehlgeschlagen“** in Notiz-
      Spalte und Kartei (gleiches Muster wie „Mail nicht gesendet“, v29),
      Button „Erneut übergeben“, Zähler in den Lead-Einstellungen.
- [x] **Auslöser und Bedienung:** (1) Klick auf **„Terminierung“** (B8)
      erzeugt nach erfolgreicher Pflichtfeldprüfung die Datei, **auch in der
      Testphase** mit `terminierung_aktiv = aus`: der Button ist dann nicht
      mehr ausgegraut, sondern aktiv mit Tooltip „Testphase: nur Übergabe an
      TAIFUN, keine Buchung, keine Mail“; die übrigen Wirkungen (Buchung,
      Outlook, Mail, Phase Terminiert, Leads VOT) bleiben gesperrt wie in
      v31 Phase 159 und werden beim Freischalten wieder aktiv. (2) Button
      **„An TAIFUN übergeben“** in der Kundenkartei (Kopf, neben
      Terminierung; ID/LM/Admin, nicht AD/HV) für Übergaben ohne Termin;
      nach erfolgter Übergabe heißt er „Erneut an TAIFUN übergeben“ und
      fragt mit Hinweis auf das Datum der letzten Übergabe nach (Doppelte
      in TAIFUN vermeiden). (3) **Dubletten-Hinweis vor dem Export:** hat
      der Kunde bereits einen TAIFUN-Angebotseintrag (externer Eintrag mit
      TAIFUN-Nummer, v7), einen Bestandsimport (v18) oder ein gefülltes
      `kunden.taifun_kundennr`, erscheint „Kunde ist vermutlich schon in
      TAIFUN angelegt (<Beleg>). Trotzdem übergeben?“ mit Ja/Nein.
      (4) Nach Erfolg: `vorgaenge.taifun_export_am/_von/_datei`
      (additiv), Aktivität „An TAIFUN übergeben: <Dateiname>“, grünes Badge
      **„TAIFUN“** mit Datum im Kartei-Kopf, Spalte „TAIFUN-Übergabe“ im
      Spaltenkatalog der Boards (Standard ausgeblendet), Filter-Chip
      „an TAIFUN übergeben“. Keine Glocke (v29-Regel), keine Kundenmail.
- [x] **Übergabeliste und Abholung:** Lead-Einstellungen → „TAIFUN-Übergabe“
      zeigt die Liste aller Exporte (Datum, Vorgang, Datei, Benutzer,
      Status: geschrieben · abgeholt · fehler · manuell importiert). Ein
      Scheduler-Job (alle 15 Minuten, v27-Rahmen) prüft, ob die Datei noch
      im Ordner liegt; fehlt sie, Status **abgeholt** (= von TAIFUN oder
      einem Mitarbeiter verarbeitet). Button „Als importiert markieren“ je
      Zeile, Button „XML anzeigen/herunterladen“ (Kopie bleibt unter
      `data/taifun_export/<Dateiname>` als Protokoll, 12 Monate, Löschlauf
      vorhanden). Feld `kunden.taifun_kundennr` (additiv) im Kundeninfo-
      Block der Kartei zum manuellen Nachtragen, Badge zeigt die Nummer.
- [x] **Parametrierung und Prüfpunkte:** Abschnitt „TAIFUN-Übergabe“ mit
      Schalter, Ordner, Encoding, Button „Testdatei schreiben“ (Demo-Lead
      „Max Mustermann“, Datei `LM_TEST_<Zeit>.xml`, zum Import-Test in
      TAIFUN) und Prüfpunkten für den Go-live: Ordner erreichbar, Testdatei
      in TAIFUN erfolgreich importiert (Häkchen), Encoding bestätigt.
      `docs/taifun-kundenexport.md`: Feldzuordnung als Tabelle, Beispiel-
      XML, Ordner/Rechte, Fragenliste an den TAIFUN-Betreuer (automatischer
      Import ja/nein, Verhalten bei Dubletten, Rückgabe der Kundennummer).

## Phase 184: Vertriebskanal-Stammdaten (Nachtrag 15.10.)

- [x] **Tabelle `vertriebskanaele`** (additiv: `key`, `name`, `farbe`,
      `aktiv`, `pflicht_hinweis`, `reihenfolge`, `angelegt_am`); Parameter
      `kanal_farben` (v23) wird daraus abgeleitet und nicht mehr von Hand
      gepflegt. Migration legt die Kanäle aus den Bildern an (Farben ca.,
      Hex als Startwert, Admin kann ändern): RegioScout `#F28B82` ·
      Thermondo `#5B6B9E` · ED - Google `#C75AA0` · ED - Meta `#7FC8E8` ·
      Webinar `#333333` · DAA `#F0B14A` · Enni `#7BC67E` · Google `#C9A0A0` ·
      Andere `#E06C75` · Prepair Tech. `#6B8BD6` · Konfigurator `#3FB8A0` ·
      Stadtwerke Düsseldorf `#4F8FCF` · Mitsubishi `#8E9AA8` · WhatsApp
      `#8B6B5E` · OTC `#5BA6A0` · Klimakonfigurator `#3AA0C8` · Empfehlung
      `#C8B45A` · Bosch `#2E5E6E` · Sparkasse `#F08A7A` · EEE `#9A86D6` ·
      Messe `#3F7FB8` · Showroom `#A4C84A` · Infoveranstaltung `#8A5AD6` ·
      Kontaktformular/info `#B06AE0` (Name bestätigt 15.10.2026) · Reonic `#7A4FB0` · WELOVEX `#4F9AD6` ·
      Comodomo `#A85A8A` · Bestandskunde `#5AA0D6` · ? `#3F6F7F` · Energy
      Systems `#5A8FB0`. Bestehende Kanalwerte im Datenbestand (aus monday
      und Quellen), die nicht in dieser Liste stehen, werden als Kanal mit
      `aktiv = 0` angelegt (EON, Provinzial, EnergieDigital, ZEUS Empfehlung,
      RS Versicherungen und eventuelle weitere, Liste in der
      Gesamtübersicht); „Standard“ wird als Kanal gelöscht, Leads mit Kanal
      „Standard“ erhalten Kanal leer (bestätigt 15.10.2026).
      Abgleich der Schreibweisen gegen monday-Mapping und Quellen-Dropdown
      (v21) mit Zuordnungstabelle alt → neu in der Migration (z. B.
      „Stadtwerke Düsseld…“ = Stadtwerke Düsseldorf).
- [x] **Pflege in der Parametrierung** → „Vertriebskanäle“: Liste mit
      Name, Farbe (Farbwähler, Kontrast zum Text automatisch), aktiv,
      Anzahl Leads, Anzahl Verwendungen 90 Tage; Anlegen, Umbenennen (wirkt
      überall), Farbe ändern, **Löschen** = `aktiv = 0` (nicht neu wählbar;
      Leads behalten den Kanal, Label bleibt sichtbar, Filter zeigt
      inaktive Kanäle unter „weitere“), endgültiges Löschen nur, wenn kein
      Lead den Kanal trägt. Zuordnung Kanal → Angebotsprofil (v9) liest
      die neue Tabelle; Kanäle ohne Zuordnung nutzen Profil „Standard“
      (unverändert). HV-Ausschlussliste (v29 `hv_ausschluss`) und Kanal-
      AD-Regel (v23) wählen aus der neuen Liste.
- [x] **Dropdowns nach Häufigkeit:** alle Kanal-Dropdowns (Kartei, Inline-
      Edit, Schnellanlage, Import, Quelle, Filter) sortieren aktive Kanäle
      nach Anzahl Verwendungen der letzten 90 Tage absteigend, dann
      alphabetisch; inaktive nur am betroffenen Lead als „(nicht mehr
      wählbar)“. Labels in Boards, Kartei, Kanban, Anrufliste, Leads VOT,
      Angebotsliste aus der neuen Tabelle (Farbe, Name).
- [x] **Kanal „?“ = unklar:** Lead mit Kanal „?“ zeigt das Kanalfeld rot
      umrandet mit Hinweis „Vertriebskanal klären“, zählt im Pflichtfeld-
      Zähler und sperrt „Terminierung“ und TAIFUN-Übergabe (Phase 183), bis
      ein anderer Kanal gewählt ist; Filter-Chip „Kanal unklar“ im
      Hauptboard. Eingang ohne erkennbaren Kanal (Parser, API ohne Kanal,
      Quelle ohne Kanal) setzt „?“ statt leer (bestätigt 15.10.2026).

## Phase 185: Rechte Außendienst, HV-Gruppensicht, Profilbild (Nachtrag 15.10.)

- [x] **Außendienst bearbeitet eigene Leads wie der Innendienst:**
      Rechte-Matrix: Rolle Außendienst (angestellt) an Leads mit
      `vorgaenge.ad_id` = eigener Benutzer: alle Felder der Kundenkartei
      (Autospeichern), Status/Phase inkl. Pflichtgründe, Zuständige
      (Innendienst-Dropdown = Leadmanager, Außendienst-Dropdown wie v31),
      Vertriebskanal, Objekte, Objektfotos, Notizen, To-Dos, Anruf-
      Ergebnisse, Wiedervorlage, Termine (im Rahmen der Testphase-Sperren);
      nicht: Archivieren, Duplizieren, Sammelaktionen anderer Leads,
      Parametrierung, Löschlauf. Fremde Leads bleiben read-only wie bisher
      (Lead-Akte). Jede Änderung protokolliert als Aktivität mit Autor; EK/
      DB bleiben unsichtbar (Rolle unverändert). Mobile Darstellung der
      Kartei (v25 responsiv) geprüft bei 390 px.
- [x] **HV-Gruppensicht:** `lead_v2.hv_sicht` und alle HV-Filter
      (Handelsvertreter-Ansicht, Dashboard, Karte, To-Dos, Kartei-Gate,
      Terminassistent) arbeiten mit der **Gruppe** statt mit dem einzelnen
      Benutzer: Gruppe René = {René}; Gruppe Simon = {Simon, Paolo, André,
      Ralf, Hartmut} (aus `hv_gruppe_rene`, `hv_gruppe_simon`, Mitglieder
      v31/v33, eine Funktion `hv_gruppe_fuer(benutzer_id)`). Ein HV sieht und
      bearbeitet alle Leads, deren `ad_id` in seiner Gruppe liegt, und
      **nie** Leads der anderen Gruppe (server-seitig, 303 auf die
      HV-Ansicht mit Hinweis wie v29). Umverteilung innerhalb der Gruppe
      per Dropdown (v31), zwischen den Gruppen nur Innendienst/Admin über
      die Sammelaktion. Filter „Vertreter“ in der HV-Ansicht zeigt nur die
      eigene Gruppe. Statistik/Kacheln der HV-Ansicht rechnen je Gruppe.
- [x] **Profilbild in den eigenen Benutzereinstellungen:** Menü „Mein
      Profil“ (alle Rollen): Bild hochladen (JPG/PNG, max 2 MB, quadratischer
      Zuschnitt im Browser, Speicherung als `benutzer.bild_datei`, v29),
      Vorschau, Entfernen. Das Bild ersetzt die Initialen-Avatare in Boards,
      HV-Ansicht, Kartei-Zuständige, Mein Tag (v32/v33) und wird in der
      Terminbestätigung je Vertriebler (v29 `{vertriebler_block}`) genutzt;
      Admin kann Bilder weiterhin in der Benutzerverwaltung setzen.

## Phase 186: Hauptboard Inline-Bearbeitung, gespeicherte Filter, Sofortsuche, Objektfotos (Nachtrag 15.10.)

- [x] **Zeilen direkt bearbeiten:** Inline-Edit (v23: status, notiz,
      ad_id, leadmanager_id, wiedervorlage) wird erweitert auf **Interessen**
      (Mehrfach-Häkchen im Popover mit allen Sparten inkl. MS/WA/DMS),
      **Vertriebskanal** (Dropdown, Phase 184), **Großkunde** (Häkchen),
      **Objektart**, **Telefon**, **E-Mail**, **Vor-Ort-Termin** (nur
      Anzeige + Link, keine Buchung), **Teilgenommen** (Infoabend). Klick in
      die Zelle öffnet das Eingabeelement, Enter/Verlassen speichert per
      fetch (`POST /lead-management/boards/zeile/{id}`, Validierung wie das
      Autospeichern der Kartei, Aktivität bei Änderung), Escape bricht ab;
      Pflichtfeld-Verletzungen (Kanal „?“, fehlender AD) werden rot in der
      Zelle markiert. Gilt für Hauptboard, Deals, Infoabend, HV-Ansicht
      (Rechte je Rolle wie Phase 185). Sortierung und Spaltenbreiten (v29)
      bleiben erhalten; keine Seitenneuladung.
- [x] **Filter speichern:** in der Sticky-Filterleiste Button „Filter
      speichern“ (Name, Häkchen „als Standard beim Öffnen“), Dropdown
      „Gespeicherte Filter“ je Nutzer und Board (`benutzer_einstellungen`
      Key `boards_filter`: Chips, Suche, Sortierung, Gruppen-Klappzustand),
      Umbenennen, Löschen, „Filter zurücksetzen“; Standardfilter wird beim
      Öffnen des Boards angewendet, URL-Parameter überschreiben ihn.
      Innendienst kann einen Filter „für alle freigeben“ (schreibgeschützte
      Kopie bei den anderen Nutzern) (bestätigt 15.10.2026).
- [x] **Eine Suchleiste, Sofortsuche:** Im Board „Kontaktiert“ entfällt die
      separate Rufnummernsuche; die breite Suchleiste (Name, Ort, E-Mail,
      Notiz) durchsucht zusätzlich die Telefonnummer (Endziffern- und
      Teilsuche nach v31 Phase 158, E.164-normalisiert, ab 3 Ziffern; Eingabe
      mit Leerzeichen, Schrägstrich oder Pluszeichen wird bereinigt). Die
      Suche und **alle Filter des Lead-Moduls** (Suchleisten und Chip-Selects
      in Hauptboard, Deals, Kontaktiert, Infoabend, Handelsvertreter,
      Anrufliste, Kanban, Karte, To-Dos, Übergabeliste) wirken **sofort beim
      Tippen bzw. Auswählen**, ohne Enter: Suchfeld mit Verzögerung 300 ms
      nach dem letzten Tastendruck, Filter-Chips unmittelbar, Ergebnis per
      fetch ohne Seitenneuladen, Zähler und Gruppen aktualisieren sich mit,
      Enter bleibt als Abschluss erlaubt, Escape leert das Feld. Laufende
      Anfragen werden bei neuer Eingabe verworfen (keine veralteten
      Ergebnisse). Lupe-Button und „Suchen“-Buttons entfallen; die URL
      spiegelt den aktuellen Filter (teilbar, Zurück-Navigation v30 bleibt).
      Gespeicherte Filter (oben) speichern den Suchtext mit.
- [x] **Fotos je Objekt:** die Galerie des Vorgangs (v15, je Sparte +
      Sammelbox) erhält je Objekt (v31 `vorgang_objekte`) einen eigenen
      Ordner „Objekt <Bezeichnung>“; Upload in der Kartei direkt an der
      Objektkarte (mehrere Dateien, mobil per Kamera, JPG/PNG/HEIC → JPG,
      max 10 MB je Bild, Vorschaukacheln, Lightbox v28, Löschen durch
      Hochladenden/ID/Admin), zusätzlich Zuordnung „Objekt“ beim Upload in
      der Galerie und beim Einsortieren aus der Sammelbox. Erfassung und
      Projektakte zeigen die Objektfotos des jeweiligen Objekts (nur
      Anzeige). Ein-Objekt-Vorgänge: Ordner heißt „Objekt“ und ersetzt
      nichts Bestehendes.

## Phase 187: Tests, Doku, Übergabe

- [x] Tests `tests/test_lead_v6_taifun.py`: (a) XML eines Demo-Leads
      validiert gegen `docs/taifun/ADRESSEN.xsd`, Elementreihenfolge und
      Namensraum korrekt, Encoding-Deklaration windows-1252, Umlaut im Namen
      korrekt kodiert; (b) Name3 „Helmut Schliwa“, Straße „Im Knick“,
      Hausnummer „36“, PLZ/Ort, Briefanrede „Sehr geehrter Herr Schliwa,“;
      (c) Mobilnummer → Funk, Festnetz → Telefon; (d) MFH mit abweichender
      Rechnungsadresse → Rechnungsadresse im Ad, Objektadresse in der
      Karteikarte; (e) Terminierung in der Testphase schreibt die Datei,
      bucht nicht, sendet nicht; (f) Ordner nicht beschreibbar → Status
      fehler, Label, Erneut-Button, nach Reparatur Erfolg; (g) zweite
      Übergabe fragt nach, Dubletten-Hinweis bei TAIFUN-Angebotsnummer;
      (h) Scheduler setzt „abgeholt“, wenn die Datei fehlt; (i) Längen über
      60 Zeichen werden gekürzt und vermerkt; (j) kein Export bei
      `taifun_export_aktiv = aus`; (k) Kanäle: Migration legt die Liste an,
      EON inaktiv und am Alt-Lead sichtbar, „Standard“ weg, Dropdown nach
      Häufigkeit, „?“ sperrt Terminierung; (l) AD ändert Status und Kanal am
      eigenen Lead, fremder Lead read-only; (m) Paolo sieht Simons und
      Hartmuts Leads, René nicht, und umgekehrt; (n) Profilbild erscheint
      als Avatar und in der Terminbestätigung; (o) Inline-Edit Interessen
      und Kanal im Hauptboard mit Aktivität; (p) gespeicherter Standardfilter
      greift beim Öffnen; (q) Objektfoto landet im Objekt-Ordner und ist in
      der Erfassung sichtbar; (r) Kontaktiert: „4711“ in der allgemeinen
      Suchleiste findet die Rufnummer, Treffer erscheinen ohne Enter; Filter-
      Chip im Hauptboard aktualisiert die Liste ohne Seitenneuladen. Gesamtlauf grün,
      `tests/test_v27_sitzungen.py` grün.
- [x] Rollout-Vorbereitung nach Grundregel: Server-DB-Kopie nach
      diagnose\, migrate.py zweimal (additiv: `vorgaenge.taifun_export_*`,
      `kunden.taifun_kundennr`, Tabellen `taifun_uebergaben` und
      `vertriebskanaele`, Galerie-Ordner je Objekt, `boards_filter`,
      Parameter),
      Rückweg-Probe, Voll-Crawl, Abnahmeskript, Smoke grün;
      `docs/betrieb.md` Inventar: Export-Ordner, Scheduler-Job, Rechte des
      Dienstkontos; `docs/nach-dem-update-v35.md` (Admin: Ordner prüfen,
      Testdatei in TAIFUN importieren, Encoding bestätigen; Team: Badge
      TAIFUN, Button, Kundennummer nachtragen).
- [x] CLAUDE.md: Abschnitt „Neu in v35 – Lead-Management V6 TAIFUN-
      Kundenübergabe, Kanal-Stammdaten, Rechte, Inline-Bearbeitung
      (abgestimmt 15.10.2026)“ (Plan: PLAN_LEAD_V6.md, Phasen 183 bis 187;
      Nummern laut Vorspann prüfen), Zuordnungstabelle
      `| v35 | PLAN_LEAD_V6.md | 183–187 |`, in „Neu in v6/v9/v23/v29“ die
      Sätze zu Kanal aus monday-Mapping als einzige Quelle, `kanal_farben`
      von Hand, HV sieht nur eigene Leads und AD read-only als *überholt –
      siehe v35* markieren, „Zentrale Dateien“ um
      `docs/taifun/ADRESSEN.xsd`, Hinweis in „Neu in v31“ (Testphase:
      Terminierung erzeugt TAIFUN-Datei), `config.VERSION = "v35"`.
      Gesamtübersicht, ein Commit „v35: TAIFUN-Kundenübergabe (PLAN_LEAD_V6,
      Phasen 183-187)“, **kein push vor Freigabe**.

## Kontrollwerte für die Abnahme

- Demo-Lead Helmut Schliwa (Herr, Im Knick 36, 47269 Duisburg, Mobilnummer,
  Interesse WP, Vertriebler Horst, Termin vorgemerkt 22.10. 10:00): Klick
  „Terminierung“ in der Testphase → Datei `LM_<Nr>_<Zeit>.xml` im Ordner,
  Inhalt: KdUse true, Name3 „Helmut Schliwa“, AnschriftStr „Im Knick“,
  AnschriftHNr „36“, PLZ „47269“, Ort „Duisburg“, Anrede „Sehr geehrter Herr
  Schliwa,“, Funk gefüllt, Telefon leer, Kartei mit Vorgang, Kanal,
  „Wärmepumpe“, Objekt, Horst, „vorgemerkt: 22.10.2026 10:00“; keine Mail,
  kein Outlook, Phase unverändert; Badge „TAIFUN 15.10.2026“ in der Kartei.
- Datei aus dem Ordner entfernen → nach spätestens 15 Minuten Status
  „abgeholt“ in der Übergabeliste.
- Ordner auf nur lesen setzen → Übergabe schlägt fehl, Label rot, Zähler 1;
  Rechte zurück, „Erneut übergeben“ → Erfolg, Label weg.

## Zulieferungen / bewusst offen

- **[OFFEN 1] TAIFUN-Betreuer:** liest TAIFUN den Ordner automatisch oder
  importiert ein Mitarbeiter manuell? Verhalten bei doppelten Kunden?
  Erwartete Kodierung (windows-1252 bestätigen)? Gibt es ein Muster-XML?
- **[OFFEN 2]** Rückgabe der TAIFUN-Kundennummer ins Tool (Export-Datei von
  TAIFUN oder Abfrage); bis dahin manuelles Feld.
- **[OFFEN 3] IT:** Auf welchem Rechner liegt `C:\Users\kdadmin\Desktop\LM
  Datenimport`, und hat das Dienstkonto des Tools auf fr-wts-02 Schreib-
  recht dort? Falls anderer Rechner: Freigabe und UNC-Pfad.
- Bestätigt 15.10.2026 (keine Annahmen mehr): Leads mit Kanal „Standard“
  erhalten Kanal leer; Eingang ohne Kanal setzt „?“; Filter „für alle
  freigeben“.
- Bestätigung der [ANNAHME]-Stellen: Encoding windows-1252; Rechnungs-
  adresse als TAIFUN-Adresse; Mobil-Erkennung über Vorwahl; nationale
  Nummernschreibweise; Firmenname in Name 3 bei Firmenkunden; Versionsnummer
  v35 und Phasen 183 bis 187.
