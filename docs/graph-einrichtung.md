# Microsoft Graph für den E-Mail-Versand einrichten (Phase 17)

Anleitung für die IT: Das Angebotstool legt E-Mail-Entwürfe direkt im Postfach
des angemeldeten Innendienst-Mitarbeiters ab (delegierte Berechtigung
**Mail.ReadWrite** – es wird nichts automatisch gesendet). Dafür ist einmalig
eine App-Registrierung im Microsoft-365-Mandanten der Friondo GmbH nötig.

## 1. App-Registrierung anlegen

1. https://portal.azure.com → **Microsoft Entra ID** → **App-Registrierungen**
   → **Neue Registrierung**
2. Name: `Friondo Angebotstool`
3. Unterstützte Kontotypen: **Nur Konten in diesem Organisationsverzeichnis**
   (einzelner Mandant)
4. Umleitungs-URI: leer lassen → **Registrieren**

## 2. Device-Code-Anmeldung erlauben

App-Registrierung → **Authentifizierung** →
„Erweiterte Einstellungen" → **Öffentliche Clientflows zulassen: Ja** → Speichern.

## 3. Berechtigung vergeben

App-Registrierung → **API-Berechtigungen** → **Berechtigung hinzufügen** →
**Microsoft Graph** → **Delegierte Berechtigungen** → folgende auswählen →
Hinzufügen → anschließend **„Administratorzustimmung für Friondo erteilen"**
(bei jeder späteren Erweiterung der Liste erneut nötig):

| Berechtigung | Wofür |
|---|---|
| `Mail.ReadWrite` | Entwurf im Postfach des Mitarbeiters ablegen (Phase 17) |
| `Mail.Read` | Mail-Verlauf am Angebot (Phase 27) |
| `Mail.Send` | Info-Mail an den Innendienst nach Fern-Signatur (Phase 28) |
| `Mail.ReadWrite.Shared` | Zugriff auf das freigegebene Postfach **angebot@friondo.de** – Versand-Erkennung + Kundenantworten (Phase 31) |
| `Mail.Send.Shared` | Senden im Namen von angebot@friondo.de (Phase 31) |

Es wird weiterhin nichts ohne Zutun eines Mitarbeiters an Kunden gesendet:
Das Tool legt Entwürfe an, gesendet wird in Outlook.

## 3a. Postfach angebot@friondo.de („Senden als") – Phase 31

Alle Angebots-Mails gehen mit dem Absender **angebot@friondo.de** raus, und
Kundenantworten laufen dort auf. Dafür richtet der M365-Admin ein:

1. **Freigegebenes Postfach** `angebot@friondo.de` anlegen (Exchange Admin
   Center → Empfänger → Postfächer → Freigegebenes Postfach hinzufügen), falls
   noch nicht vorhanden.
2. Für **jeden Innendienst-Mitarbeiter** unter diesem Postfach →
   **Postfachdelegierung** zwei Rechte vergeben:
   - **„Senden als"** – damit der in Outlook gesendete Entwurf mit dem
     Absender angebot@friondo.de rausgeht
   - **„Lesen und Verwalten (Vollzugriff)"** – damit das Tool über das
     Konto des Mitarbeiters die gesendeten Mails und Antworten im Postfach
     angebot@ lesen kann (Graph `Mail.ReadWrite.Shared`)
3. Die Rechte greifen nach bis zu 60 Minuten. Danach im Tool einmal
   **Versand → Abmelden → Mit Microsoft anmelden**, damit das Token die
   neuen Berechtigungen enthält.

Im Tool stehen Absender und Abgleich-Postfach unter **Parametrierung →
E-Mail-Versand** (Vorbelegung angebot@friondo.de, BCC info@friondo.de).

## 4. IDs in die .env eintragen

Von der Übersichtsseite der App-Registrierung kopieren und in die `.env`
im Projektordner eintragen (danach App neu starten):

```
GRAPH_CLIENT_ID=<Anwendungs-ID (Client)>
GRAPH_TENANT_ID=<Verzeichnis-ID (Mandant)>
```

## 5. Anmeldung im Tool

Im Angebotstool: **Versand** → „Mit Microsoft anmelden" → der angezeigte Code
wird auf https://microsoft.com/devicelogin mit dem Microsoft-365-Konto des
Innendienst-Mitarbeiters eingegeben. Das Token wird lokal gespeichert
(`data/.graph_token.json`) und automatisch erneuert; „Abmelden" löscht es.

## 6. Ablauf danach

„Versand vorbereiten" im Angebots-Editor erzeugt den Entwurf mit Betreff
„Ihr Wärmepumpen-Angebot AN-C-… der Friondo GmbH", Standardtext, Angebots-PDF
und den Anhängen laut Blatt „Anhänge". Gesendet wird in Outlook nach Kontrolle;
anschließend im Tool den Status auf „Versendet" setzen.

**Übergangslösung, solange Graph nicht eingerichtet ist:** „PDF anzeigen" im
Editor und die E-Mail manuell verfassen.

## 7. Ablauf Versand, Status-Automatik und Mail-Verlauf (Phase 27/31)

1. **„Versand vorbereiten"** im Angebots-Editor (seit v6 als **HTML-Mail** mit
   der Outlook-Signatur des Mitarbeiters, siehe `docs/signaturen.md`): Das Tool baut Betreff und
   Text aus der E-Mail-Vorlage (Standard oder die des Außendienstlers des
   Vorgangs), setzt Absender angebot@friondo.de, **CC = E-Mail des
   Außendienstlers** (aus der Benutzerverwaltung; fehlt sie, kommt ein
   deutlicher Hinweis und der Entwurf geht ohne CC raus), **BCC** aus der
   Parametrierung, hängt PDF + Anlagen an, legt den Entwurf im Postfach des
   Mitarbeiters ab und setzt den Status auf **„Versand vorbereitet"**.
2. Der Mitarbeiter prüft den Entwurf in Outlook und sendet ihn.
3. Der **Abgleich alle 15 Minuten** sucht die Konversation der Angebots-Mail
   im Postfach angebot@friondo.de. Sobald dort eine gesendete (nicht mehr als
   Entwurf markierte) Nachricht von uns liegt, springt der Status automatisch
   auf **„Versendet"** – erst das löst die monday-Rückspielung aus. Notfalls
   kann der Status im Editor auch manuell gesetzt werden.
4. Antworten des Kunden in derselben Konversation (Fallback: Betreff mit der
   AN-C-Nummer) erscheinen in der Angebotsliste als Brief-Symbol mit Zähler;
   Klick öffnet den Mail-Verlauf (Absender, Zeitpunkt, Textauszug).
   Geantwortet wird weiterhin in Outlook – das Tool zeigt nur an.

## Projektierung V1 (v11): Shared-Postfach projektierung@friondo.de

Aufgaben für den M365-Admin, damit die Benachrichtigungs-Mails der
Projektierung (Sofort-Mail und Tagesdigest 07:15) mit dem richtigen Absender
rausgehen:

1. **Shared-Postfach anlegen**: Exchange Admin Center → Empfänger →
   Postfächer → „Freigegebenes Postfach hinzufügen" →
   `projektierung@friondo.de` (kein eigenes Konto/keine Lizenz nötig).
2. **„Senden als"-Berechtigung** für die Benutzer vergeben, unter deren
   Graph-Anmeldung das Tool läuft (dieselben Konten wie beim Angebotsversand):
   Shared-Postfach → Delegierung → „Senden als" → Benutzer hinzufügen.
   Die Berechtigung greift erfahrungsgemäß erst nach bis zu einer Stunde.
3. Das Absender-Postfach steht im Tool unter **Parametrierung →
   Projektierung-Einstellungen** (Standard `projektierung@friondo.de`).
   Fehlt die Berechtigung, versucht das Tool automatisch den Fallback
   `angebot@friondo.de`; beide Fehler landen im **Mail-Protokoll** auf
   derselben Einstellungsseite. Der Mail-Versand blockiert das Tool nie.

## Lead-Management V1 (v12): Kalender-Rechte + Postfächer

Aufgaben für den M365-Admin (Terminassistent, Mail-Parser, Kundenmails):

1. **Postfach `leads@friondo.de`** anlegen (Shared-Postfach) – Eingang der
   Formular-Mails (Parser). *Seit v29 (Lead-Management V4) wird leads@ nur
   noch gelesen – Absender aller Kundenmails ist termin@friondo.de, siehe
   den Abschnitt „Lead-Management V4 (v29)“ unten.*
2. **Testpostfach** (z. B. `lead-test@friondo.de`) anlegen: Im Demo-Modus
   schreibt der Terminassistent Kalender-Ereignisse AUSSCHLIESSLICH in
   dieses Postfach (Parametrierung → Lead-Einstellungen →
   `kalender_testpostfach`) – nie in echte AD-Kalender.
3. **Kalender-Berechtigung**: App-Registrierung um `Calendars.ReadWrite`
   (Application) erweitern, Admin-Consent erteilen und den Zugriff mit
   einer **Application Access Policy** auf die AD-Postfächer + das
   Testpostfach beschränken:
   `New-ApplicationAccessPolicy -AppId <App-ID> -PolicyScopeGroupId
   <Mail-aktivierte Sicherheitsgruppe mit den AD-Postfächern> -AccessRight
   RestrictAccess`
4. Ohne Kalender-Recht arbeitet der Assistent nur mit Tool-Terminen
   (Frei/Belegt aus Outlook entfällt) – das Tool blockiert nie; ein Hinweis
   erscheint in der Parametrierung.

## Lead-Management V4 (v29): Postfach termin@friondo.de – Absender aller Lead-Mails

Entscheidung 07.10.2026 (Claudia Castro): **Alle automatisierten Kundenmails des
Lead-Moduls** (Eingangsbestätigung, Nicht erreicht, Disqualifiziert,
Terminbestätigung – auch „erneut senden“ –, Terminerinnerung, Terminänderung,
Terminabsage, Online-Termin-Einladung und alle künftigen Vorlagen) gehen mit dem
Absender **termin@friondo.de** raus (Parameter `absender_lead_mails`,
Parametrierung → Lead-Einstellungen → „Lead-Management V4“). **Es gibt bewusst
keinen Fallback** auf ein anderes Postfach: fehlt das Senderecht oder schlägt
der Versand fehl, bleibt die Mail nach drei Versuchen mit Status `fehler` in
der Warteschlange, der Lead steht oben im Hauptboard mit dem roten Vermerk
„Mail nicht gesendet“ und die Kundenkartei zeigt „Erneut senden“.
**leads@friondo.de bleibt ausschließlich Eingangspostfach** (Parser, Formulare,
Portale, Lead-Partner) und wird nicht mehr als Absender genutzt.

Aufgaben für den M365-Admin (vor der Freischaltung `lead_freigabe_modus = alle`;
im Demo-Modus betrifft das nur das Testpostfach):

1. **Shared-Postfach `termin@friondo.de`** anlegen (Exchange Admin Center →
   Empfänger → Postfächer → Freigegebenes Postfach hinzufügen; keine Lizenz
   nötig).
2. **„Senden als“** für die Konten vergeben, unter deren Graph-Anmeldung das
   Tool läuft (dieselben Konten wie beim Angebotsversand): Shared-Postfach →
   Delegierung → „Senden als“ → Benutzer hinzufügen. Das Tool sendet über
   `/me/sendMail` mit `from = termin@friondo.de` (Berechtigung
   `Mail.Send.Shared`, bereits in der App-Registrierung).
3. **Lesezugriff („Lesen und Verwalten / Vollzugriff“)** für dieselben Konten:
   Der Lauf `lead-mail-abruf` (alle 2 Minuten, Betriebs-Seite/`/health`) liest
   ungelesene Nachrichten im Posteingang von termin@ (Graph
   `/users/termin@friondo.de/mailFolders/inbox/messages`, Berechtigung
   `Mail.ReadWrite.Shared`), ordnet **Kundenantworten** dem Vorgang zu (Timeline
   „Antwort von …“, Wiedervorlage „jetzt“) und erkennt
   **Unzustellbarkeitsberichte** (Absender postmaster/MAILER-DAEMON, Betreff
   „Unzustellbar“/„Undeliverable“/„Delivery Status Notification“): der Lead
   erhält `email_status = ungueltig` („E-Mail falsch“, oben im Hauptboard),
   weitere Mails an die Adresse warten bis zur Adressänderung. Verarbeitete
   Nachrichten werden als gelesen markiert; nicht zuordenbare landen in
   „Posteingang unklar“. Die Rechte greifen nach bis zu 60 Minuten; danach im
   Tool einmal Versand → Abmelden → Mit Microsoft anmelden.
4. **Prüfpunkt im Tool:** Parametrierung → Lead-Einstellungen → „Prüfpunkte V4“
   → „Testmail aus dem Lead-Absender senden“ (Admin). Die Testmail geht als
   termin@ an die Testadresse (`mail_testadresse`; im Demo-Modus ausschließlich
   dorthin); Ergebnis steht in der Meldung und im Einstellungs-Protokoll
   („fehlgeschlagen … (kein Fallback)“ = Senderecht fehlt). Ohne eingerichtetes
   Graph (`GRAPH_CLIENT_ID`) melden Testmail und Lauf „Graph nicht eingerichtet“.
5. **Handelsvertreter** (ohne Friondo-Postfach) sind von termin@ nicht
   betroffen: für ihre Leads sendet das Tool bis zur Entscheidung
   [OFFEN 2] keine Terminbestätigung (`hv_versandweg = offen`), sondern legt
   dem HV ein To-Do mit Vorschau (Text + ICS) an.

Übersicht der Postfächer nach v29:

| Postfach | Zweck | Graph-Zugriff des Tools |
|---|---|---|
| angebot@friondo.de | Angebots-Mails (Entwurf in Outlook, Abgleich) | Senden als + Vollzugriff (Phase 31) |
| projektierung@friondo.de | Benachrichtigungen der Projektierung | Senden als (v11) |
| leads@friondo.de | **nur Eingang**: Lead-Parser (Lauf `lead-parser`) | Lesen und Verwalten (nur lesen + `isRead`) |
| termin@friondo.de | **Absender aller Lead-Mails**, Antworten + Bounces (Lauf `lead-mail-abruf`) | Senden als + Lesen und Verwalten |
| lead-test@ (Testpostfach) | Demo-Modus: Kalender-Ereignisse, Testmails | wie bisher |


## Outlook-Kalender-Sync der Montageteams (v15, Phase 81)

Das Tool spiegelt Montage-, Feinplanungs- und Abnahmetermine nach Outlook
und liest Verschiebungen alle 15 Minuten zurück. Zwei Wege – die Wahl
trifft die Parametrierung (Projektierung-Einstellungen → Outlook-Kalender):

### Weg A: Team-Postfächer (Standard)

1. In Microsoft 365 je Team ein Postfach oder eine freigegebene Mailbox
   anlegen: `team1@friondo.de` … `team10@friondo.de`,
   `subteam1@friondo.de` … `subteam5@friondo.de`.
2. Dem in der Azure-App angemeldeten Konto die Berechtigung
   **Calendars.ReadWrite.Shared** (delegiert) erteilen und die Kalender
   der Team-Postfächer für dieses Konto freigeben (Bearbeiter-Rechte).
3. Im Tool unter Parametrierung → Teams je Team die **Outlook-Adresse**
   des Postfachs eintragen.
4. Sync-Modus in den Projektierung-Einstellungen auf
   „Team-Postfächer“ lassen.

Vorteil: jedes Team sieht nur den eigenen Kalender (auch am Handy).

### Weg B: Gemeinsamer Kalender mit Kategorien

1. EIN Postfach (z. B. `montage@friondo.de`) anlegen und dessen Kalender
   für alle freigeben; Berechtigung wie oben.
2. Sync-Modus „Gemeinsamer Kalender mit Kategorie je Team“ wählen und
   die Adresse eintragen; jeder Eintrag bekommt die Kategorie mit dem
   Teamnamen (Farben in Outlook einmalig je Kategorie festlegen).

Vorteil: eine einzige Kalenderfreigabe, Filterung über Kategorien.

### Verhalten

- Betreff: „PR-… · Kunde · Sparte“, Ort = Ausführungsadresse, Text =
  Steckbrief-Kurzfassung + Link in die Projektakte (Basis-URL in der
  Parametrierung).
- Outlook → Tool: Datum/Dauer-Änderungen werden alle 15 Minuten
  übernommen (Verlaufseintrag „Termin in Outlook verschoben von …“);
  alles andere (Teilnehmer, Text) bleibt Outlook.
- Fehler blockieren nie: der Termin zeigt ein Warnsymbol mit
  „Erneut senden“.
