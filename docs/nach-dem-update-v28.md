# Nach dem Update v28 (PLAN_PROJ_V6) – Projektierung V6: Pilot-Feedback 1, mit v27-Nachtrag 2

Dieses Update kommt **zusammen mit v29 (Lead-Management V4)** und dem **Nachtrag 2 zu v27**
(Klima-Versand, E-Mail-Vorlagen je Sparte, Anmeldeseite) in einem Schritt auf den Server
(ein gemeinsamer Commit, Entscheidung Andreas 07.10.2026). Hinweise zum Lead-Management
stehen in `docs/nach-dem-update-v29.md`. Rollout nur im Wartungsfenster (Dienstag
22:30–23:30) nach `docs/betrieb.md` → „Update im Wartungsfenster“; nach `update.bat` läuft
`migrate.py` (zweimal fehlerfrei) und `scripts\smoke.bat`.

Alle Datenbankänderungen sind additiv (neue Spalten `aufgaben.entfaellt_grund`,
`projekt_termine.zweck`, `benutzer.vorname/infotext/bild_datei`, `vorgaenge.email_status*`
/`mail_fehler*`, `kommunikation_log.absender/versuche`, neue Tabelle `termin_besetzung`);
der v27-Code läuft auf der neuen Datenbank weiter, Rückweg `rollback.bat --nur-code`.

## Nachtrag 2 zu v27 – Klima-Versand, E-Mail-Vorlagen je Sparte, Anmeldeseite

**Für das Team**
- **Neue Anmeldeseite:** links Logo und Anmeldung, rechts das Energiehaus-Foto. Benutzer und
  PIN wie bisher; das Häkchen „Auf diesem Gerät angemeldet bleiben“ erscheint nur noch, wenn
  ein Außendienst- oder Montage-Konto gewählt ist (Büro-Rollen bleiben 12 Stunden angemeldet).
  Fehlermeldungen (falsche PIN, Sperre) stehen jetzt unter dem Knopf „Anmelden“. Auf dem
  Handy (unter 500 px Breite) kommt die Seite ohne Foto.
- **Klima-Versand:** Beim „Versand vorbereiten“ eines Klima-Angebots gehen jetzt drei
  Broschüren mit – Unternehmenspräsentation, Ratenkauf (nicht bei Enni/SWD) und die
  Gerätebroschüre „Bosch Climate 3200i“. Fehlt eine Datei im Ordner `anlagen\`, steht das in
  der grünen Meldung nach dem Vorbereiten („Achtung, fehlende Anhang-Dateien …“) – bitte
  lesen und an den Admin melden; der Admin sieht fehlende Dateien auch als Kachel auf
  Parametrierung → Betrieb.
- **E-Mail-Vorlagen je Sparte (Innendienst/Admin):** Parametrierung → E-Mail-Vorlagen hat
  Reiter Standard · WP · PV · KL · WB. Beim Versand gilt: eigene Vorlage des Außendienstlers →
  Vorlage der Sparte des Angebots → Standard. Die Sparten-Vorlagen wurden beim Update
  automatisch aus der Standard-Vorlage erzeugt (KL: „Klimaanlagen-Angebot“/„Klimaanlage“,
  PV: „PV-Angebot“/„PV-Anlage“; Sätze mit Eigenanteil/Förderung sind bei PV/KL entfernt).
  **Bitte die Reiter PV, KL und WB einmal gegenlesen** (WB = Kopie des WP-Textes, von
  Andreas bestätigt) sowie die beim Update entfernten Sätze (Liste vom Admin). WP braucht
  keine eigene Vorlage: Wärmepumpen-Angebote nutzen weiter die Standard-Vorlage (Reiter
  „Standard“), die Versand-Meldung nennt die verwendete Vorlage („Standard-Vorlage“ bzw.
  „Sparten-Vorlage KL“). Der Kombi-Versand behält seine eigene Vorlage.

**Admin / Server-To-dos**
1. Beim Update die Ausgabe von `migrate.py` sichern: Zeilen „E-Mail-Vorlage … angelegt“ und
   „E-Mail-Vorlage KL/PV: Satz entfernt: „…““ an den Innendienst geben (Gegenlesen).
2. Nach dem Pull auf dem Server prüfen: `dir anlagen` muss `Friondo Unternehmenspräsentation.pdf`,
   `Broschüre Ratenkauf.pdf` und `Bosch Climate 3200i.pdf` zeigen (`anlagen\` ist versioniert;
   die Klima-Broschüre kommt mit dem Pull). Die Streudatei `anlagen\unternehmenspraesentation.pdf`
   (1 KB, ohne Inhalt) wurde in der Arbeitskopie gelöscht – auf dem Server ebenfalls löschen
   (Entscheidung Andreas 08.10.2026). Danach Dienst neu starten (lädt die Logik-Excel mit der
   neuen Anhänge-Zeile) bzw. Parametrierung → Logik & Importe → „Neu einlesen“.
3. Ein KL-Angebot probeweise „Versand vorbereiten“ und im Outlook-Entwurf die drei Anhänge
   zählen; Meldung auf den Zusatz „fehlende Anhang-Dateien“ prüfen. Kachel „Anhang-Dateien
   (anlagen/)“ auf Parametrierung → Betrieb muss „vollständig“ zeigen (heute fehlt nur die
   seit v13 offene Zulieferung `Bosch CS8800iAW.pdf`).
4. Anmeldeseite einmal im Firmennetz und über VPN auf dem Handy aufrufen (Foto 0,4 MB wird
   nur ab 500 px Breite geladen).

## Projektierung – Wächter, Board, Termine, Besetzung, Stücklisten (Phasen 133–135, 139)

- **Wächter warnt nur noch:** Beim Phasenwechsel (Akte „Phase ändern“ oder Ziehen im
  Board) zeigt der Dialog die offenen Pflichtaufgaben – ihr könnt sie direkt abhaken oder
  mit Grund auf „entfällt“ setzen; eine Begründung ist nur rückwärts Pflicht (oder wenn der
  Admin den Modus auf „sperren“ stellt). Offene Punkte stehen danach im Verlauf.
- **Aufgabe „entfällt“:** An jeder Aufgabe gibt es „entfällt …“ mit Pflicht-Grund und
  „wieder aufnehmen“; entfallene Aufgaben zählen nicht mehr als offen. Schritte, deren
  Bedingung nicht (mehr) zutrifft (z. B. BzA ohne Förderung, Öltank ohne Öltank, Anzahlung
  bezahlt bei „keine Anzahlung“), setzt das Tool selbst auf „entfällt“ mit Grund
  „Bedingung nicht erfüllt (…)“.
- **Board:** nutzt die volle Bildschirmbreite; jede Spalte scrollt für sich (Kopf bleibt
  stehen), der waagerechte Balken liegt über dem Board, Shift + Mausrad scrollt waagerecht.
  Ziehen einer Karte öffnet den Dialog „Phase ändern“; Ziehen von „unterminiert“ nach
  „terminiert“ öffnet den Termin-Dialog; zurück nach „unterminiert“ geht über „löschen“ im
  Block Termine der Akte.
- **Ein Termin-Dialog:** „+ Termin“ in der Akte (Block „Termine“ je Gewerk), am Board und in
  der Terminübersicht – Art wählen (Montage WP, Elektro-Montage, Sub-Einsatz, Feinplanung
  VOT, Abnahme, Sonstiges), Team oder Person, Beginn/Uhrzeit/Ende, **Besetzung** (vorbelegt
  aus dem Team, per Chips änderbar – das Team ist nur die Vorlage), Kunde bestätigt, Notiz.
  Termine lassen sich bearbeiten und mit Grund löschen. Bei Montage (WP): „Terminvorschläge“
  zeigt freie Fenster je Team (Umweg nur mit Routing-Anbieter).
- **Stücklisten:** Blatt aus der CSV (121 Zeilen) ist drin; Spalte „Lieferant“: Collin =
  bestellen, Lager = Lagerware, „–“ = Leistung ohne Material, anderer Name = Fremdlieferant –
  nur Collin-Zeilen landen in der UGL, der Rest steht in der Bestell-Vorschau unter „nicht
  bestellt“.
- **Admin:** Fahrzeiten der Terminvorschläge brauchen den Routing-Anbieter der
  Lead-Einstellungen (ORS/Google mit Schlüssel) – ohne ihn zeigt der Dialog Umweg „–“.
  Monteure brauchen Benutzer mit Rolle Montage (Mehrfachauswahl „Besetzung“ listet nur diese).
  Blatt „Stücklisten“ der Live-Excel kommt mit dem Git-Pull (Backup in `data/backups/`).

## Notizen-Chat (alle Rollen, Phase 136)
- Es gibt nur noch **eine** Notizspur je Kunde: der Notizen-Chat des Vorgangs. Er steht in
  der Vorgangsakte (Angebotstool), in der Projektakte (Reiter Verlauf) und in der
  Kundenkartei (Lead-Management) – überall dieselben Einträge. Alte Projektakten-
  Kommentare wurden beim Update in den Chat kopiert (Kennzeichen „Projektierung“).
- Jeder Eintrag trägt ein Kennzeichen (Projektierung · Vertrieb · Lead · Montage).
  Einträge bleiben unveränderlich. Das Eingabefeld wächst mit; **Strg + Enter** sendet,
  die Seite lädt nicht neu.
- Monteure lesen die Notizen im Montage-Backend (letzte fünf, „alle anzeigen“) – sie
  schreiben nicht im Chat, sondern im Montagebericht („Bemerkungen des Monteurs“).

## Galerie (Phase 136)
- Ein Klick auf ein Bild öffnet die **Lightbox** (groß, ◀ ▶, Pfeiltasten, Wischen auf dem
  Handy). Herunterladen nur über den Knopf „Herunterladen“ – der Sofort-Download beim
  Anklicken ist behoben. PDFs öffnen im Browser-Tab.

## Montage-Backend (Rolle Montage, Phase 137)
- „Meine Einsätze“ zeigt die Termine, in denen ihr **eingeteilt** seid (Besetzung je
  Termin – die Projektierung setzt sie im Termin-Dialog). Termine ohne Besetzung sehen
  weiterhin alle Mitglieder des Teams. Über die Knöpfe oben lässt sich auf die
  Teamansicht umschalten; der Wochenkalender zeigt die Mannschaft als Initialen.
- Die Auftragsseite ist neu sortiert: Kopf · Steckbrief (jetzt vollständig, leere Felder
  „–“) · Teams & Termine · Notizen der Projektierung · Montage starten/beenden ·
  Formulare · Restarbeiten · Galerie. Die „Offenen Montage-Aufgaben“ gibt es nicht mehr.
- „Montage beenden“ hat kein Kurzbericht-Feld mehr – Bemerkungen zur Montage gehören in den
  Montagebericht („Bemerkungen des Monteurs“). Die Montage endet weiterhin automatisch,
  sobald das Abnahmeprotokoll unterschrieben ist.

## Formulare (Rolle Montage, Phase 138)
- Montagebericht ohne Arbeitsbeginn/-ende, Nachbestellung und Regie, dafür
  „Bemerkungen des Monteurs“ und vier Foto-Felder (mehrere Fotos je Feld, Vorschau,
  Upload beim Speichern). Inbetriebnahmeprotokoll komplett neu (Seriennummern +
  „+ weitere Seriennummer“, elf Prüffragen, Betriebswerte, Einstellungen, zwei
  Unterschriften); Frage 10 wird als Restarbeiten-Liste übernommen („keine“ erlaubt),
  bei Frage 11 ≠ „Ja“ ist die Begründung Pflicht. Das Inbetriebnahmeprotokoll fragt kein
  Kältemittel mehr ab (30 Felder). **Angefangene Entwürfe der alten Formulare werden beim
  Update geleert** (sie enthielten Felder, die es nicht mehr gibt) – bitte neu ausfüllen;
  abgeschlossene Formulare und ihre PDFs bleiben unverändert.

## Bildschirmbreite (alle Bereiche)
- Portal, Lead-Management, Vorgangsakte, Kundenkartei und Projektierung nutzen jetzt die volle
  Monitorbreite (16 px Rand); auf großen Bildschirmen stehen Tabellen und Boards breiter.
- Das Projektierungs-Board passt auf Laptops (1366 × 768) und auf Full-HD mit Browserleisten
  ohne Seiten-Scroll: der Hinweistext unter dem Board ist dort einzeilig (Maus darüber zeigt
  alles), die Kacheln verzichten auf die Untertitel.

## Admin / Server (v28)
- Nach `update.bat`: `migrate.py` meldet die v28-Migrationen (Spalten/Tabelle, Termine:
  `zweck`-Backfill und Besetzung aus den Team-Mitgliedern, Notizen: „n Projektakten-
  Kommentar(e) kopiert“, „Formulare (v28): n alte Entwürfe geleert (…)“); zweiter Lauf
  ohne Meldung.
- Parametrierung → Projektierung-Einstellungen: Abschnitt „Board & Wächter“ (`waechter_modus`
  = warnen) und „Terminvorschläge“ (Montagedauer 5 AT, Vorlauf 4 Wochen, Startadresse
  Firmensitz, Outlook-Stufe aus) einmal prüfen.
- Blätter „Aufgabenpakete“, „Formulare“ und das neue Blatt „Lesehilfe“ der
  `projektierung_logik_v1.xlsx` sind im Git-Pull enthalten; Parametrierung →
  Projektierung-Logik → „Logik prüfen“ muss ohne Fehler sein (neue Bedingungsform
  `foerderung:`, Typen `wiederhol`, Optionen `gross`, `pflicht_wenn:` sind bekannt; Tippfehler
  im Blatt lehnen den Upload jetzt ab). Nach dem Neustart leiten bestehende Gewerke beim
  nächsten Nachziehen Schritte mit nicht erfüllter Bedingung auf „entfällt“ (Verlauf).
- Lightbox/Chat brauchen keine neuen Einstellungen; `app/static/akte_v28.css` und
  `projektierung_v28.css` werden über `base.html` geladen (Cache-Version `css_version`).
