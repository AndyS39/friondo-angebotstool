# Nach dem Update auf v33 – was ist neu, was ist zu tun

Stand 14.10.2026 · v33 = PLAN_V20 (Phasen 166–177): Outlook je Mitarbeiter, Graph als Anwendung,
zentraler Kalender, Rollen-Varianten, Service-Einsätze, automatischer Phasenwechsel, Rabatt bei 0 % USt,
Mein Tag mobil, Tabellen-Layout, Nachfassen. Rollout wie immer im Wartungsfenster (Dienstag 22:30–23:30) per
`update.bat`; die Datenbank wird nur erweitert (v32-Code läuft auf der v33-Datenbank, Rückweg
`rollback.bat --nur-code`). **Bis der Verbindungstest unter „Versand“ grün ist, läuft das Tool im Modus
„delegiert“ weiter – also genau wie heute.**

## Für das Team

### Alle Büro-Rollen: neuer Mitarbeiter-Kalender
Neuer Menüpunkt **Kalender** (Innendienst/Admin: Menü ☰; Projektierung: Menü ☰ und Knopf
„Mitarbeiter-Kalender“ im Team-Kalender; Lead-Management: Icon-Leiste „Mehr … → Kalender“). Eine Zeile je
Mitarbeiter, Tag | Woche | Monat, Sa/So einblendbar; die Gruppen-Chips (Außendienst, Handelsvertreter,
Projektierung, Montage Heizung/Elektro, Service Heizung/Elektro, Innendienst) merken sich die Auswahl je
Einstieg. Farben: blau Vor-Ort-Termin, grün Telefon, violett Online, grün (dunkel) Montage, blau Elektro,
orange Sub, Service orange-braun, grau Abwesenheit, schraffiert Outlook-belegt (nur die Zeit, kein Betreff).
Klick öffnet den Termin im jeweiligen Modul, Ziehen verschiebt (mit Rückfrage bei Konflikten), Doppelklick auf
freie Fläche legt einen Termin an (erst Kunde/Projekt wählen). Monteure und Service-Techniker sehen nur sich
und ihr Team – lesend, am Handy als Tagesansicht. Der alte Wochen-Terminkalender je Außendienstler
(`/lead-management/kalender`) leitet in den neuen Kalender um; Außendienst und Handelsvertreter sehen dort
ihre eigene Zeile.

### Außendienst, Projektierung, Monteure, Service: Termine im eigenen Outlook-Kalender
Jeder Termin aus dem Tool steht jetzt **in eurem persönlichen Outlook-Kalender** (TAIFUN liest von dort):
Vor-Ort-Termine beim eingeteilten Vertriebler, Montage-/Elektro-/Sub-/Service-Einsätze bei jeder Person der
Besetzung, Feinplanung/Abnahme/Sonstiges bei der eingetragenen Person. Der Eintrag heißt z. B.
„Montage (WP): Müller, 47139 Duisburg (PR-260012)“, trägt die Kategorie „Friondo-Tool“, enthält Kunde, Adresse,
Besetzung, Steckbrief-Kurzfassung und den Link in die Akte – und kommt etwa eine Minute nach dem Speichern an
(Stand „Outlook: ausstehend/ok“ am Termin). **Verschiebt ihr den Eintrag in Outlook**, übernimmt das Tool die
neue Zeit innerhalb von fünf Minuten (Verlauf „aus Outlook übernommen von …“), auch bei den Kollegen derselben
Besetzung. **Löscht ihr den Eintrag in Outlook**, bleibt der Termin im Tool bestehen und wird als „in Outlook
gelöscht“ markiert (Glocke an Projektierung bzw. Leadmanager) – absagen oder verschieben bitte im Tool. Eure
eigenen Outlook-Termine fasst das Tool nie an; sie erscheinen im Terminassistenten und im Mitarbeiter-Kalender
nur als „belegt“. Handelsvertreter ohne Friondo-Postfach bekommen keinen Eintrag (Hinweis „HV ohne Postfach“).

### Innendienst: Angebots-Entwürfe liegen künftig im Postfach angebot@
- Sobald die IT „Graph als Anwendung“ eingeschaltet hat, legt „Versand vorbereiten“ den Entwurf nicht mehr
  in deinem eigenen Postfach ab, sondern in **angebot@friondo.de → Entwürfe** (für alle Innendienstler
  sichtbar). In Outlook das eingeblendete Postfach angebot@ öffnen, Entwurf prüfen, senden – der Status
  springt wie bisher auf „Versendet“.
- Deine Signatur steckt weiterhin im Entwurf (Signatur-Upload in der Parametrierung).
- „Mit Microsoft anmelden“ unter Versand ist dann nicht mehr nötig (die Seite heißt jetzt „Verbindung zu
  Microsoft 365“). Solange die IT die Umstellung nicht abgeschlossen hat, zeigt die Seite „Delegiert“ und
  alles läuft wie vorher.

### Innendienst/Außendienst: Rabatt bei PV-Angeboten (0 % USt)
Der Gesamtrabatt wird bei jedem Steuersatz vom Gesamtbetrag nach USt abgezogen – bei PV-Angeboten (0 % USt)
also vom Nettobetrag. Beispiel: 20.000,00 € netto, 5 % Rabatt → Endbetrag 19.000,00 €; 500 € Rabatt →
19.500,00 €. So steht es im Editor, im PDF, in der Angebotsliste (Spalte „Endbetrag“ und Summenzeile), im
Mail-Platzhalter {endbetrag} und im monday-Deal-Wert. Der Hinweis am Rabatt-Feld heißt jetzt „Abzug vom
Gesamtbetrag (nach USt)“. Rabatte je Position sind unverändert. (Rechnerisch stimmte der Endbetrag schon
vorher – die Angebotsliste zeigte in der Spalte „Brutto“ den Betrag **vor** Rabatt, daher der Eindruck, der
Rabatt werde bei 0 % nicht abgezogen.)

### Benutzer und Rollen: Varianten
Benutzer können jetzt eine **Variante** tragen (Montage Heizung/Elektro, Service Heizung/Elektro,
Handelsvertreter) – Rechte wie die Basisrolle, zusätzlich Gewerk/Service/HV. In der Benutzerliste stehen
Varianten mit „↳“ und kleinen Kennzeichen-Badges. Das Häkchen „Handelsvertreter – terminiert selbst“ im
AD-Profil und die Rolle Handelsvertreter sind dasselbe (ein Klick ändert beides). Der Infotext in der
Terminbestätigung ist weg – nur noch Bild, Name, Telefon, E-Mail. Sammelaktion „An Handelsvertreter
verschieben“: Schaltfläche „Simons Gruppe“ – der Lead liegt bei Simon mit dem Kennzeichen „Simons Gruppe
(noch nicht verteilt)“, Simon wählt in der Kartei (Feld Außendienst / Handelsvertreter) das Mitglied; danach
verschwindet das Kennzeichen. Die Kanal-Regel im AD-Profil kennt „Stadtwerke Düsseldorf“ (gilt auch für den
monday-Kanal „SWD“).

### Projektierung/Innendienst: Service-Einsätze und automatischer Phasenwechsel
Im Termin-Dialog gibt es die Art „Service-Einsatz“ (Gewerk, Anlass, Uhrzeit, Dauer, Techniker).
Bestandskunden ohne Projekt: Vorgangsakte → Block „Termine“ → „Service-Einsatz planen“ (auch für die Rolle
Projektierung erreichbar). Die Projektakte zeigt Service-Einsätze mit Badge „Service“; das Board bleibt
unverändert. Phasen springen jetzt automatisch weiter, sobald alle Pflichtaufgaben erledigt oder „entfällt“
sind (Verlauf + Glocke); je Gewerk über das Häkchen „automatisch weiterschalten“ abschaltbar; ein manueller
Rückschritt pausiert die Automatik in dieser Phase. Montage/Abnahme/Abgeschlossen bleiben manuell (Montage
starten/beenden, Abnahmeprotokoll, Rechnung freigeben). Neue Auswertung: Projektierung → Statistik
(Service-Einsätze je Monat).

### Service-Techniker (Rollen Service Heizung/Elektro)
`/montage` zeigt nur eure Service-Einsätze (Liste + Wochenkalender). Im Einsatz: Kunde, Adresse
(Karten-Link), Steckbrief, Notizen, „Einsatz gestartet“ → „Einsatz beendet“, danach den Servicebericht
ausfüllen (Unterschrift Kunde + Techniker) – das PDF landet automatisch in der Galerie im Ordner „Service“.

### Monteure (Montage Heizung/Elektro)
Ihr seht nur die Termine eures Gewerks (Montage (WP) + Sub bzw. Elektro); der Knopf „Kalender“ öffnet den
Mitarbeiter-Kalender (nur lesend, am Handy als Tagesansicht).

### Außendienst am Handy: „Mein Tag“, Wiedervorlage, untere Leiste (Phase 173)
- **Außendienst am Handy:** `/leads` („Mein Tag“) hat einen neuen Aufbau: oben Datum und Initialen,
  Karte „Als Nächstes“ mit „Route starten“ (Google Maps mit der Kundenadresse als Ziel), darunter
  „Heute“ als Zeitstrahl – grüner Punkt = Erfassung abgeschlossen (Link „Erfassung“), orangener Punkt =
  nächster Termin. Ein Termin gilt als erledigt, sobald die Erfassung dazu abgesendet ist; einen Haken
  gibt es nicht. Überfällige Termine (vergangene Vor-Ort-Termine ohne Erfassung) stehen oben in einem
  aufklappbaren Block. Telefon-/Teams-Termine ohne Erfassung verschwinden am Folgetag.
- **Wiedervorlage:** Der Abschnitt zeigt bis zu vier Vorgänge (fällige Wiedervorlagen, heiße Vorgänge,
  angekündigte Bestellungen) mit Badge Hoch/Mittel/Niedrig = Hot-Ampel; Chips und „Sortieren“
  merken sich die Wahl pro Browser-Tab. Antippen öffnet die Anruf-Karte (Nächster Schritt, Notiz,
  letzte Aktivitäten). „Alle N Wiedervorlagen anzeigen“ öffnet die neue Seite mit Suchfeld; am PC gibt
  es diese Seite nicht (Innendienst: Angebotsliste mit Verfolgungsfilter).
- **Untere Leiste** (nur Handy, Außendienst): Mein Tag · Kalender (Meine Termine) · Wiedervorlage ·
  Kunden (öffnet die Suche in der Kopfzeile).
- **Am PC** sehen alle Rollen in „Leads VOT“ die Tabelle mit Gruppen je Termintag (Überfällig · Heute ·
  Donnerstag, 15. Oktober …), Filter oben fest (neu: Priorität = Hot-Ampel), Spalten/Sortierung je
  Nutzer wie in den Lead-Boards („Spalten“-Knopf, Klick auf den Spaltenkopf). Der Umschalter
  „Karten | Tabelle“ aus v32 ist weg.
- **Glocke „Fällig heute: n Anrufe“** springt jetzt zum Abschnitt „Wiedervorlage“.
- Doku: `docs/design-v32/leads-vot-vorher.png` bleibt als Vergleichsbild des v32-Stands liegen (keine
  Löschung); neue Screenshots „Mein Tag“ 390 px hell/dunkel, „Wiedervorlage“, Leads VOT Desktop unter
  `docs/design-v33/`.
- Keine neuen Parameter, keine Migration, keine Datenbankänderung.

### Alle Rollen: Listen im Lead-Board-Layout (Phase 174)
- Alle Listen (Angebote, Erfassungen, Meine Angebote, Kunden, Leads VOT) sehen jetzt aus wie die Lead-Boards: Filter oben bleiben beim Scrollen stehen, die Tabelle scrollt in ihrem Rahmen (Kopfzeile bleibt sichtbar), am unteren Rand liegt eine zweite Scrollleiste für seitliches Scrollen.
- Klick auf einen Spaltennamen sortiert (erster Klick aufsteigend, zweiter absteigend, Pfeil im Kopf, leere Werte stehen immer unten); die Wahl wird je Person und Tabelle gemerkt.
- Knopf „Spalten“: Spalten ein-/ausblenden; Spaltenkopf ziehen = Reihenfolge; Stift im Kopf = eigener Name (leer = Standard); rechter Rand des Kopfs ziehen = Breite; „Zurücksetzen“ = Standard. Alles gilt nur für die eigene Person. Die erste Spalte (Kundenname bzw. „Erfassung“ in der TAIFUN-Warteschlange) ist fest.
- Außendienst: „Meine Angebote“ ist jetzt eine Tabelle mit Filtern Status/Sparte; EK, DB und DB-Ampel gibt es dort auch im Spaltenwähler nicht (Rollenregel).
- Angebotsliste: Spalte „Endbetrag“ zeigt den Betrag nach USt **und** Rabatt (vorher „Brutto“ = vor Rabatt); die Summenzeile folgt der gefilterten und sortierten Liste; Filter-Chip „Ohne Kontakt“ (Phase 176).
- Kundenliste: Filter Vertriebskanal und Objektart.
- Projektierung: Spalten werden über `/einstellungen/spalten` gespeichert (gleiche Bedienung).
- Keine Sammelaktionen in den Angebotstool-Tabellen (Entscheidung Claudia Castro).

### Außendienst: Nachfassen – Zähler, Einwände, Nachfass-Mail (Phase 176)
Im Dialog „Nächster Schritt“ (Vorgangsakte und Mein Tag) zählt „Nochmal
anrufen“ jetzt mit – der Chip zeigt „Nachgefasst (2)“. Beim Ergebnis „Nochmal anrufen“ kann ein
Einwand des Kunden angeklickt werden (Förderung unklar, wartet auf Mitbewerber, Entscheidung in der
Familie, Finanzierung offen – oder keiner); der zuletzt gesetzte Einwand steht beim nächsten Anruf oben
auf der Karte. Neuer Knopf **Nachfass-Mail**: Vorlage „Nachfassen 1“ oder „2“ wählen, Vorschau ansehen,
optional das Angebots-PDF anhängen, Senden – die Mail geht aus Ihrem eigenen Postfach (Absender Ihre
Friondo-Adresse) und landet im Mail-Verlauf und im Notizen-Chat des Vorgangs. Die Signatur dazu laden
Sie einmalig unter Menü → „Meine E-Mail-Signatur“ (`/einstellungen/signatur`) hoch (Outlook: .htm-Datei
plus Bilder aus dem gleichnamigen Ordner). Solange der Knopf ausgegraut ist („Versand aus dem eigenen
Postfach erst mit Graph als Anwendung“), ist die Microsoft-Anbindung noch nicht umgestellt.
Vorgänge mit Status Versendet/Nachgefasst, bei denen seit 14 Tagen (MFH: 20) kein Kontakt mehr stand
(Notiz, Anruf, Mail), tragen das rote Kennzeichen „ohne Kontakt seit X Tagen“ – eine Wiedervorlage in
der Zukunft nimmt es nicht weg.

### Innendienst: Nachfassen in Angebotsliste, Statistik und Vorlagen (Phase 176)
Angebotsliste mit Kennzeichen/Filter „ohne Kontakt seit X Tagen“;
Statistik → unter den Ablehnungsgründen die Tabelle „Einwände beim Nachfassen“ (gleiche Filter).
Vorlagen-Editor (Parametrierung → E-Mail-Vorlagen) hat die Reiter „Nachfassen 1“ und „Nachfassen 2“ –
die Standardtexte sind Entwürfe, bitte gegenlesen; `{absender}` ist dort der sendende Außendienstler,
die Signatur hängt das Tool darunter.

### Alle: Fotos werden vor dem Upload verkleinert (Nachtrag 15.10.2026)
Fotos aus Galerie, Montage-Foto und Formularen werden jetzt **auf dem Handy verkleinert** (längste Kante 2000 px,
dieselbe Größe, die der Server bisher nach dem Upload erzeugt hat) und **Foto für Foto** hochgeladen – der Knopf
zeigt „Lade 2 von 5 …“. Ein Foto ist damit meist 300–600 KB statt mehrere MB; über LTE/VPN geht der Upload
fünf- bis zehnmal schneller. Nicht lesbare Formate (z. B. HEIC ohne Browser-Unterstützung) gehen unverändert.

### Weitere Entscheidungen vom 15.10.2026 (Team)
- Mitarbeiter-Kalender: erledigte Vor-Ort-Termine bleiben in der Vergangenheit sichtbar (ausgegraut).
  Wer einen Vor-Ort-Termin in die Zeile eines anderen Vertrieblers zieht, bekommt eine Rückfrage – der Termin
  wird umgebucht und der Kunde erhält eine Terminänderungs-Mail.
- Service-Einsätze dürfen ohne Team/Techniker geplant werden; die Besetzung folgt in der Akte (im
  Service-Backend und in Outlook erscheint der Einsatz erst mit Besetzung).
- Handelsvertreter-Dashboard: Block „Simons Gruppe – noch nicht verteilt“ listet die Leads, für die noch ein
  Mitglied gewählt werden muss.
- Verschiebt ein Mitarbeiter einen Vor-Ort-Termin in Outlook, übernimmt das Tool die Zeit und schickt dem
  Leadmanager eine Glocke – die Terminänderung an den Kunden geht bewusst von Hand. Diese Glocke (wie die
  Glocke „in Outlook gelöscht“) erscheint nur, wenn in den Lead-Einstellungen die Glocken-Art
  „Terminänderung“ angehakt ist (Admin-Punkt 10).
- Nachfass-Mail: die Vorlagen enden mit Grußformel und {absender}; die hochgeladene Signatur daher ohne eigene
  Grußformel anlegen (sonst doppelt).

## Für Andreas / Admin

1. **Graph als Anwendung einschalten (IT, Anleitung `docs/graph-einrichtung.md`):**
   Entra: Anwendungsberechtigungen `Mail.Send`, `Mail.ReadWrite`, `Calendars.ReadWrite` + Administrator-
   zustimmung; geheimen Clientschlüssel (24 Monate) anlegen – Wert NUR in die `.env` auf dem Server
   (`GRAPH_CLIENT_SECRET`, dazu `GRAPH_GEHEIMNIS_ABLAUF=JJJJ-MM-TT`), Dienst neu starten. Exchange: Gruppe
   `friondo-tool-zugriff@friondo.de` mit allen Postfächern aus der Kopierliste der Verbindungs-Seite
   (Versand → „Kopierliste aller Postfächer“), `New-ApplicationAccessPolicy … -AccessRight RestrictAccess`,
   `Test-ApplicationAccessPolicy`, `Set-Mailbox angebot@ -MessageCopyForSentAsEnabled $true`. Im Tool:
   Versand → „Verbindung testen“ – alle Funktionspostfächer grün → Modus „Anwendung“; rote
   Mitarbeiter-Postfächer nachtragen (Kopierliste „Fehlt in der Zugriffsgruppe“), erneut testen.
   Go-live-Checkliste: Punkt 12 „Graph als Anwendung verbunden“ muss grün sein; `/health` warnt 30 Tage vor
   Ablauf des Geheimnisses (dann neues Geheimnis anlegen, `.env`, Neustart, Test). Neue Mitarbeiter: Benutzer
   mit E-Mail im Tool + Postfach in die Gruppe. Die delegierten Freigaben vom 14.10.2026 (Kalender, termin@)
   bleiben bestehen und können später zurückgenommen werden.
2. **Rollen und Teams prüfen:** Parametrierung → Rollen (neue Varianten anlegen, umbenennen, deaktivieren –
   Basisrollen sind gesperrt); Benutzer den Varianten zuweisen (René Golaschewski und Simon O Grady wurden von
   der Migration auf „Handelsvertreter“ gesetzt – bitte prüfen); Parametrierung → Teams: Gewerk je Team prüfen
   (Migration: Elektro-Teams an Gewerken → Elektro, alle übrigen → Heizung). Angebotsprofil SWD: Kanalwerte
   „SWD, Stadtwerke Düsseldorf“ eintragen (Rückfrage R4 im Durchlauf). CSV-Import akzeptiert Rollen-Namen und
   -Keys der Varianten.
3. **Kalender:** Parameter `kalender_tagesbeginn`/`kalender_tagesende` (Lead-Einstellungen, Standard
   07:00/18:00) bestimmen die Zeitachse. Rollen-Varianten entscheiden über die Gruppen (Montage/Service je
   Gewerk, Handelsvertreter-Kennzeichen) – Benutzer ohne Gewerk stehen unter „Montage Heizung“.
4. **Projektierung:** Projektierung-Einstellungen → Board & Wächter → Häkchen „Phasen automatisch
   weiterschalten“ (Standard an). Rollen Service Heizung/Elektro und Montage Heizung/Elektro zuweisen.
   Servicebericht-Feldliste in der Steuerdatei `projektierung_logik_v1.xlsx` (Blatt „Formulare“, 9 Felder
   `sb_*`) gegenlesen [ANNAHME im Plan].
5. **Rabatt / Schreibvorgänge:** keine Einstellung nötig. Technisch werden Speichern-Aktionen (Formulare)
   jetzt beim ersten Zugriff auf die Datenbank als Schreibvorgang angemeldet; bei belegter Datenbank wartet
   das Tool bis 5 s, versucht es einmal erneut und meldet sonst wie bisher „Datenbank kurz belegt“ mit
   Fehler-Nr. In Parametrierung → Betrieb bleiben `schreibsperre_locked`/`schreibsperre_max_ms` die
   Kennzahlen; neu dazu der Zähler `transaktionen` in `/health`.
6. **Outlook je Mitarbeiter einschalten und beobachten (Anleitung `docs/outlook-sync.md`):**
   1) Graph als Anwendung verbinden (Verbindungs-Seite „Versand“, Abschnitt Graph) und **alle Postfächer mit
   Terminen** (Außendienst, Projektierung, Monteure, Service, Testpostfach) in die Zugriffsgruppe
   `friondo-tool-zugriff@` aufnehmen – fehlende Postfächer zeigt die Verbindungs-Seite unter „Fehlt in der
   Zugriffsgruppe“ mit Kopierliste; danach laufen die hängenden Aufträge von selbst nach (stündlich).
   2) Betriebs-Seite: Läufe `outlook-sync` (jede Minute) und `outlook-ruecklesen` (alle 5 Minuten) müssen „ok“
   zeigen; die Fußzeile des Deals-Boards nennt offene/fehlgeschlagene Aufträge.
   3) Lead-Einstellungen: `kalender_sync = an` schaltet die Kopien der Vor-Ort-Termine frei (Testphase: erst
   `kalender_testpostfach` setzen und mit Demo-Leads prüfen); Benutzerverwaltung: jede Person mit Terminen braucht
   eine E-Mail (bzw. `kalender_postfach` im AD-Profil), Handelsvertreter nur mit Friondo-Postfach.
   4) **TAIFUN-Abgleich beobachten:** vor dem Echtbetrieb `scripts\outlook_abgleich.py --postfach <Monteur> --tage 14`
   ausführen (nur lesend) und entscheiden, ob die Tool-Termine für TAIFUN sichtbar bleiben (Betreff-Muster,
   Kategorie) – `docs/outlook-sync.md` Abschnitt 1. Die delegierten Kalender-Freigaben vom 14.10.2026 stören
   nicht und können später zurückgenommen werden.
   5) Altbestand: vorhandene Outlook-Einträge (Team-Kalender, alte VOT-Einträge) kennt das Tool nach `migrate.py`;
   persönliche Kopien bekommen Bestandstermine beim nächsten Speichern (oder einmalig per Handlauf – Rückfrage R7).
7. **Nachfassen (Phase 176):** Parametrierung → Angebotstool-Einstellungen → Nachfassen: Schwellen „Kennzeichen ‚ohne
Kontakt‘ ab 14 / bei MFH ab 20 Tagen“ und die Liste „Einwände beim Nachfassen“ (anlegen, umbenennen,
deaktivieren, Reihenfolge). migrate.py legt die vier Start-Einwände einmalig an. Voraussetzung für die
Nachfass-Mail: Graph als Anwendung (Phase 166) mit allen Außendienst-Postfächern in der Zugriffsgruppe
`friondo-tool-zugriff@` (ein AD ohne Postfach in der Gruppe bekommt beim Senden „Versand aus
<Postfach> fehlgeschlagen: … 403“). Bis dahin bleibt der Knopf im Modus delegiert gesperrt.
8. **Tabellen (Phase 174):** keine Einstellung nötig – Spalten/Sortierung speichert jede Person für sich (`benutzer_einstellungen`); „Zurücksetzen“ stellt den Standard her.

9. **Bestandstermine nach Outlook (Nachtrag 15.10.2026):** nach dem grünen Verbindungstest einmalig
   `venv\Scripts\python scripts\outlook_bestand_einreihen.py --trocken` (zählt) und dann ohne `--trocken`
   ausführen – alle Projekt-/Service-Termine und (bei `kalender_sync = an`) offenen Vor-Ort-Termine der
   nächsten 8 Wochen bekommen persönliche Outlook-Kopien über den Lauf outlook-sync. Angebotsprofil SWD:
   die Kanalwerte „SWD, Stadtwerke Düsseldorf“ setzt `migrate.py` selbst, wenn sie fehlen.
10. **Glocken-Art „Terminänderung“ einschalten (Nachtrag 15.10.2026):** Parametrierung → Lead-Einstellungen →
    Glocken → Häkchen „Terminänderung“. Ohne das Häkchen (Standard seit v29: nur To-Do-Glocken) bekommt der
    Leadmanager keine Glocke, wenn ein Vor-Ort-Termin in Outlook verschoben oder gelöscht wurde – die
    Aktivität in der Timeline des Leads gibt es trotzdem.
