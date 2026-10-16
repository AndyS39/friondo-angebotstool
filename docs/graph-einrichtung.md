# Microsoft Graph einrichten – Zugriff als Anwendung (v33, PLAN_V20 Phase 166)

Anleitung für die IT (M365-Admin, `admin@`) und für Andreas. Stand 14.10.2026.

Das Angebotstool greift ab v33 **als Anwendung** auf Microsoft 365 zu: Es meldet sich
mit einer App-Registrierung (Anwendungs-ID + Geheimnis) an und darf genau die
Postfächer anfassen, die in der Exchange-Zugriffsgruppe **`friondo-tool-zugriff@friondo.de`**
stehen. Es gibt keine persönliche „Mit Microsoft anmelden“-Verbindung mehr und keine
Kalender-Freigaben je Person. Der bisherige Weg (Anmeldung einer Person, „Senden als“)
bleibt als **Übergangsweg „delegiert“** erhalten (Abschnitt 4) und wird automatisch
benutzt, solange der Verbindungstest nicht grün ist.

Was das Tool im Modus Anwendung tut:

| Was | Postfach | Graph-Aufruf |
|---|---|---|
| „Versand vorbereiten“ (Angebots-Entwurf mit PDF, Anhängen, Signatur des ID-Benutzers, CC/BCC) | `angebot@friondo.de` → Ordner **Entwürfe** | `POST /users/angebot@…/messages` + Anhänge |
| Versand-Erkennung („Versand vorbereitet“ → „Versendet“) und Mail-Verlauf am Angebot | `angebot@friondo.de` (Konversation: Entwurf, gesendete Kopie, Antworten) | `GET /users/angebot@…/messages?$filter=conversationId …` |
| Lead-Mails (Eingangsbestätigung, Terminbestätigung, Erinnerung, Absage …) | `termin@friondo.de` | `POST /users/termin@…/sendMail` |
| Antworten und Unzustellbarkeitsberichte zu Lead-Mails (Lauf `lead-mail-abruf`) | `termin@friondo.de` | `GET /users/termin@…/mailFolders/inbox/messages`, `PATCH … isRead` |
| Lead-Parser (Formular-Mails, Lauf `lead-parser`) | `leads@friondo.de` (nur Eingang) | `GET /users/leads@…/mailFolders/inbox/messages` |
| Projektierung: Benachrichtigungen, Tagesdigest, Sub-Anfragen, Kunden-Terminmail, BzA-Mail | `projektierung@friondo.de` (Fallback angebot@ nur bei Benachrichtigungen) | `POST /users/projektierung@…/sendMail` bzw. `…/messages` + `/send` |
| Antworten der Subs und der Kunden auf Terminmails | `projektierung@friondo.de` | `GET /users/projektierung@…/messages?$filter=conversationId …` |
| Kalender je Mitarbeiter (Tool-Termine schreiben, Rücklesen, Belegtzeiten – Phase 170) | persönliches Postfach jedes Mitarbeiters mit Terminen | `/users/<upn>/events`, `/users/<upn>/calendarView` |
| Nachfass-Mail durch den Außendienst (Phase 176) | persönliches Postfach des AD | `POST /users/<upn>/messages` + `/send` |

Jeder Aufruf, der mit **HTTP 403** scheitert, landet als „Postfach <x> ist nicht in der
Zugriffsgruppe Friondo-Tool-Zugriff“ im Fehlerprotokoll (einmal je Postfach und Stunde)
und auf der Verbindungs-Seite (Abschnitt 6).

## 1. Entra ID: App-Registrierung, Anwendungsberechtigungen, Geheimnis

1. https://entra.microsoft.com → **Identität → Anwendungen → App-Registrierungen** →
   die bestehende Registrierung **„Friondo Angebotstool“** öffnen (sonst neu anlegen:
   Name `Friondo Angebotstool`, Kontotyp „Nur Konten in diesem Organisationsverzeichnis“,
   keine Umleitungs-URI).
2. **API-Berechtigungen → Berechtigung hinzufügen → Microsoft Graph →
   Anwendungsberechtigungen** (nicht „delegiert“):

   | Berechtigung | Wofür |
   |---|---|
   | `Mail.Send` | Lead-, Projekt-, Nachfass-Mails direkt aus den Postfächern senden |
   | `Mail.ReadWrite` | Entwürfe in angebot@ anlegen, Posteingänge lesen, `isRead` setzen |
   | `Calendars.ReadWrite` | Termine in die persönlichen Kalender schreiben und zurücklesen |

   Danach **„Administratorzustimmung für Friondo erteilen“** (grüner Haken in der
   Spalte Status). Die bisherigen delegierten Berechtigungen (`Mail.ReadWrite`,
   `Mail.Read`, `Mail.Send`, `Mail.ReadWrite.Shared`, `Mail.Send.Shared`,
   `Calendars.ReadWrite.Shared`) bleiben für den Übergangsweg stehen.
3. **Zertifikate & Geheimnisse → Geheime Clientschlüssel → Neuer geheimer Clientschlüssel**:
   Beschreibung `Angebotstool Server`, Gültigkeit **24 Monate** (längste Auswahl).
   Den **Wert** sofort kopieren – er ist nur einmal sichtbar. **Der Wert gehört nur in die
   `.env` auf dem Server**, nie in E-Mails, Chats, Tickets, das Projektwissen oder
   diese Doku. Das **Ablaufdatum** notieren.
4. Auf dem Server (`C:\Users\kdadmin\Desktop\Angebotstool\.env`, als kdadmin) eintragen:

   ```
   GRAPH_CLIENT_ID=<Anwendungs-ID (Client) von der Übersichtsseite>
   GRAPH_TENANT_ID=<Verzeichnis-ID (Mandant)>
   GRAPH_CLIENT_SECRET=<Wert des geheimen Clientschlüssels>
   GRAPH_GEHEIMNIS_ABLAUF=<Ablaufdatum JJJJ-MM-TT>
   ```

   Danach den Dienst neu starten (`scripts\dienst-neustart.bat`). Das Tool liest die
   `.env` nur beim Start.
5. **Alternative Zertifikat** statt Geheimnis (läuft länger, kein Klartext-Wert in der
   `.env`): unter „Zertifikate & Geheimnisse → Zertifikate“ das öffentliche Zertifikat
   (`.cer`) hochladen; auf dem Server den privaten Schlüssel als PEM ablegen (aus einer
   `.pfx`: `openssl pkcs12 -in angebotstool.pfx -nocerts -nodes -out angebotstool.key.pem`)
   und eintragen:

   ```
   GRAPH_ZERTIFIKAT_PFAD=C:\Friondo\zertifikate\angebotstool.key.pem
   GRAPH_ZERTIFIKAT_THUMBPRINT=<Fingerabdruck aus Entra, ohne Doppelpunkte>
   ```

   Ist `GRAPH_CLIENT_SECRET` gesetzt, hat das Geheimnis Vorrang. Die PEM-Datei nur für
   kdadmin/SYSTEM lesbar machen (NTFS-Rechte), nicht in den Projektordner legen.

## 2. Exchange: Zugriffsgruppe und Application Access Policy

Ohne Einschränkung dürfte die Anwendung **jedes** Postfach des Mandanten lesen und
senden. Deshalb wird der Zugriff auf eine mail-aktivierte Sicherheitsgruppe beschränkt.
PowerShell als M365-Admin (Modul `ExchangeOnlineManagement`):

```powershell
Connect-ExchangeOnline -UserPrincipalName admin@friondo.de

# 1) mail-aktivierte Sicherheitsgruppe anlegen (einmalig)
New-DistributionGroup -Name "Friondo-Tool-Zugriff" -Alias "friondo-tool-zugriff" `
    -PrimarySmtpAddress "friondo-tool-zugriff@friondo.de" -Type Security `
    -Notes "Postfaecher, auf die das Friondo Angebotstool als Anwendung zugreifen darf"

# 2) Mitglieder: Funktionspostfächer + alle Mitarbeiter mit Terminen
#    (die vollständige Liste liefert das Tool: Versand → Verbindungs-Seite → Kopierliste)
"angebot@friondo.de","termin@friondo.de","leads@friondo.de","projektierung@friondo.de" |
    ForEach-Object { Add-DistributionGroupMember -Identity "friondo-tool-zugriff@friondo.de" -Member $_ }
# Mitarbeiter aus der Kopierliste (eine Adresse je Zeile) ebenso hinzufügen:
Get-Content .\kopierliste.txt | ForEach-Object { Add-DistributionGroupMember -Identity "friondo-tool-zugriff@friondo.de" -Member $_ }

# 3) Zugriff der Anwendung auf die Gruppe beschränken (AppId = GRAPH_CLIENT_ID)
New-ApplicationAccessPolicy -AppId "<Anwendungs-ID (Client)>" `
    -PolicyScopeGroupId "friondo-tool-zugriff@friondo.de" -AccessRight RestrictAccess `
    -Description "Friondo Angebotstool: nur Postfaecher der Gruppe Friondo-Tool-Zugriff"

# 4) prüfen – AccessCheckResult muss „Granted“ sein (Mitglied) bzw. „Denied“ (Nichtmitglied)
Test-ApplicationAccessPolicy -Identity "angebot@friondo.de" -AppId "<Anwendungs-ID (Client)>"
Test-ApplicationAccessPolicy -Identity "jemand-ohne-zugriff@friondo.de" -AppId "<Anwendungs-ID (Client)>"

# 5) gesendete Kopie im Funktionspostfach ablegen (Versand-Erkennung liest die Konversation in angebot@)
Set-Mailbox -Identity "angebot@friondo.de" -MessageCopyForSentAsEnabled $true -MessageCopyForSendOnBehalfEnabled $true
```

Hinweise:

- Die Policy greift erfahrungsgemäß nach **bis zu 30 Minuten**; Gruppenänderungen
  (neue Mitglieder) ebenfalls. Danach im Tool **„Verbindung testen“**.
- Die Gruppe braucht keine Lizenz und muss nicht in der Adressliste sichtbar sein
  (`Set-DistributionGroup -HiddenFromAddressListsEnabled $true` ist erlaubt).
- Freigegebene Postfächer (angebot@, termin@, leads@, projektierung@) sind normale
  Mitglieder; Team-Kalender-Postfächer (Parametrierung → Teams → Outlook-Adresse) und
  das Testpostfach des Terminassistenten gehören ebenfalls hinein, wenn sie genutzt
  werden – die Verbindungs-Seite listet sie.
- Damit jeder Innendienstler die Entwürfe in angebot@ sieht und von dort sendet, braucht
  er wie bisher **Vollzugriff + Senden als** auf angebot@ (Outlook blendet das Postfach
  dann automatisch ein). Das ist Exchange-Delegierung, unabhängig von Graph.

## 3. Einschalten im Tool: Verbindungstest

1. Im Angebotstool als Admin oder Innendienst: **Menü → Versand** (`/versand`,
   „Verbindung zu Microsoft 365“). Die Seite zeigt Modus, Mandant (maskiert),
   Geheimnis-Ablauf, die **Liste aller Postfächer, die das Tool braucht**
   (Funktionspostfächer aus den Einstellungen + alle aktiven Benutzer mit E-Mail der
   Rollen Außendienst, Projektierung, Montage, Innendienst; Handelsvertreter ohne
   Friondo-Postfach ausgenommen) mit **Kopierliste** für Schritt 2.
2. **„Verbindung testen“**: Das Tool holt ein Anwendungs-Token und liest je
   Funktionspostfach den Posteingangs-Ordner (`GET /users/<pf>/mailFolders/inbox?$select=id`)
   und je Mitarbeiter den Kalender (`GET /users/<upn>/calendar?$select=id`) – nur lesend,
   nichts wird gesendet. Ergebnis je Postfach grün/rot mit Grund.
3. Sind **alle Funktionspostfächer grün**, stellt das Tool die Einstellung
   `graph_modus = anwendung` – ab jetzt laufen alle Aufrufe als Anwendung. Rote
   Mitarbeiter-Postfächer schalten den Modus nicht zurück, sie stehen unter „Fehlt in der
   Zugriffsgruppe“ mit eigener Kopierliste für die IT (Termine dieser Personen landen erst
   nach dem Nachtragen in Outlook).
4. Ist ein Funktionspostfach rot oder die Anmeldung der Anwendung schlägt fehl, bleibt
   (oder wird) der Modus `delegiert` – der bisherige Weg läuft weiter, nichts bricht ab.

Die Anmeldung einer Person („Mit Microsoft anmelden“) ist im Modus Anwendung **nicht
mehr nötig**; der Knopf bleibt als Rückfallebene auf der Seite.

## 4. Übergangsweg „delegiert“ (bis zum grünen Verbindungstest)

Die am **14.10.2026** gesetzten delegierten Freigaben bleiben gültig und stören im Modus
Anwendung nicht; sie werden dort nicht mehr gebraucht und können später von der IT
zurückgenommen werden:

- Skript mit `Add-MailboxFolderPermission` (Kalender-Freigaben der Außendienstler für
  das im Tool angemeldete Konto),
- **Vollzugriff und „Senden als“ auf `termin@friondo.de`** für die Konten, unter deren
  Anmeldung das Tool lief,
- Vollzugriff/„Senden als“ auf `angebot@friondo.de` (Phase 31) und „Senden als“ auf
  `projektierung@friondo.de` (v11) – Vollzugriff/Senden als auf angebot@ bleibt für
  Outlook auch im Modus Anwendung nötig (Abschnitt 2).

So funktioniert der Übergangsweg: Ein Innendienst-Mitarbeiter meldet sich unter
**Versand → „Mit Microsoft anmelden“** per Device-Code (https://microsoft.com/devicelogin)
mit seinem Microsoft-365-Konto an (delegierte Berechtigungen `Mail.ReadWrite`, `Mail.Read`,
`Mail.Send`, `Mail.ReadWrite.Shared`, `Mail.Send.Shared`; App-Registrierung →
Authentifizierung → „Öffentliche Clientflows zulassen: Ja“). Das Token liegt in
`data/.graph_token.json` und wird automatisch erneuert; „Abmelden“ löscht es. Alle
Aufrufe laufen dann über `/me/…` mit `from = Funktionspostfach` („Senden als“),
Entwürfe liegen im Postfach der angemeldeten Person, Shared-Postfächer werden über
`/users/<postfach>` mit Vollzugriff gelesen.

## 5. Checkliste neuer Mitarbeiter

1. Benutzer im Tool anlegen (Benutzerverwaltung) **mit E-Mail-Adresse** (= UPN des
   Postfachs; Außendienst mit abweichendem Kalender-Postfach: Feld im AD-Profil).
2. Postfach in die Gruppe aufnehmen:
   `Add-DistributionGroupMember -Identity friondo-tool-zugriff@friondo.de -Member <upn>`
   (bis zu 30 Minuten warten).
3. Im Tool **Versand → „Verbindung testen“** – das neue Postfach muss grün sein.
4. Handelsvertreter ohne Friondo-Postfach: nichts zu tun (keine Outlook-Termine, keine
   Nachfass-Mail aus dem Tool; OFFEN 3 aus Lead-Management V4).
5. Beim Ausscheiden: Benutzer im Tool deaktivieren, Postfach aus der Gruppe nehmen.

## 6. Verbindungstest und Fehlerbilder

| Anzeige | Bedeutung | Maßnahme |
|---|---|---|
| „Geheimnis fehlt (.env …)“ | `GRAPH_CLIENT_SECRET` bzw. Zertifikat nicht in der `.env` | Abschnitt 1 Schritt 4/5, Dienst neu starten |
| „Anmeldung der Anwendung fehlgeschlagen: invalid_client …“ | Geheimnis falsch/abgelaufen oder Anwendungs-ID/Mandant falsch | neues Geheimnis anlegen, `.env` prüfen |
| „Anmeldung der Anwendung fehlgeschlagen: … consent …“ / HTTP 401 | Administratorzustimmung fehlt | Abschnitt 1 Schritt 2 |
| „nicht in der Zugriffsgruppe Friondo-Tool-Zugriff (HTTP 403)“ | Postfach ist kein Mitglied der Gruppe (oder Policy noch nicht aktiv) | Mitglied hinzufügen, 30 Minuten warten, erneut testen |
| „Postfach unbekannt (HTTP 404)“ | Adresse existiert nicht (Tippfehler in Einstellung/Benutzerverwaltung) | Adresse korrigieren |
| „Timeout“/„URLError“ | keine Verbindung zu `login.microsoftonline.com`/`graph.microsoft.com` | Proxy/Firewall des Servers (HTTPS ausgehend) |
| Modus bleibt „Delegiert“ trotz grünem Test | Seite neu laden; Einstellung `graph_modus` prüfen (Parametrierung → Betrieb → Kachel Graph-Modus) | – |

Laufender Betrieb:

- **`/health`** meldet `graph_modus` (anwendung | delegiert) und warnt (`warn`) mit
  „Graph-Geheimnis läuft in n Tagen ab“, sobald `GRAPH_GEHEIMNIS_ABLAUF` ≤ 30 Tage
  entfernt ist; die Betriebs-Seite zeigt die Kachel „Graph-Modus“.
- **Go-live-Checkliste** (Parametrierung → Go-live): Punkt „Graph als Anwendung verbunden“
  ist grün, wenn der Verbindungstest grün war und das Geheimnis noch > 30 Tage gilt.
- **Geheimnis erneuern** (alle 24 Monate, spätestens bei der /health-Warnung): neuen
  geheimen Clientschlüssel in Entra anlegen, Wert und neues Ablaufdatum in die `.env`,
  Dienst neu starten, „Verbindung testen“, altes Geheimnis in Entra löschen.
- 403-Treffer aus den Hintergrundläufen (Outlook-Sync je Mitarbeiter, Postfach-Abrufe)
  erscheinen im Fehlerprotokoll und auf der Verbindungs-Seite unter „Fehlt in der
  Zugriffsgruppe“ mit Kopierliste.

## 7. Postfächer im Überblick

| Postfach | Zweck | Modus Anwendung | Modus delegiert (Übergang) |
|---|---|---|---|
| angebot@friondo.de | Angebots-Entwürfe (Ordner Entwürfe), Absender, Versand-Erkennung, Kundenantworten | Gruppe; Innendienst braucht Vollzugriff + Senden als für Outlook | Senden als + Vollzugriff (Phase 31) |
| termin@friondo.de | Absender aller Lead-Mails, Antworten + Bounces (Lauf `lead-mail-abruf`) | Gruppe | Senden als + Vollzugriff (v29) |
| leads@friondo.de | nur Eingang: Lead-Parser (Lauf `lead-parser`) | Gruppe | Vollzugriff (lesen + `isRead`) |
| projektierung@friondo.de | Benachrichtigungen, Sub-/Termin-/BzA-Mails, Antworten | Gruppe | Senden als (v11) |
| Mitarbeiter (UPN) | Kalender je Person (Phase 170), Nachfass-Mail des AD (Phase 176) | Gruppe | Kalender-Freigaben vom 14.10.2026 |
| Team-/Testpostfächer | Team-Kalender (v15), Testpostfach Terminassistent | Gruppe (wenn genutzt) | Kalender-Freigabe |

Keine Geheimnisse und keine Mandanten-IDs in diese Datei schreiben – die Verbindungs-Seite
zeigt den Mandanten bewusst nur maskiert.

## Hinweis Outlook je Mitarbeiter (Phase 170)

Die Zugriffsgruppe `friondo-tool-zugriff@` muss **alle Postfächer mit Terminen** enthalten (Außendienst,
Projektierung, Monteure, Service-Techniker, Testpostfach, Team-Postfächer). Fehlende Postfächer erscheinen auf
der Verbindungs-Seite unter „Fehlt in der Zugriffsgruppe“ (Kopierliste); Aufträge, die mit HTTP 403 scheiterten,
laufen nach dem Nachtragen stündlich von selbst nach (bis zu 7 Tage). Details: `docs/outlook-sync.md`.

Dazu gehören **alle Außendienst-Postfächer**: Die Nachfass-Mail (v33, Phase 176) sendet mit `messages`/`send` am
Postfach `/users/<AD-E-Mail>`; fehlt ein Postfach in der Gruppe, meldet der Knopf „Versand aus <Postfach>
fehlgeschlagen“ und das Fehlerprotokoll „Postfach … ist nicht in der Zugriffsgruppe“.

## 8. SharePoint-Ablage für Cloover-PDFs (v36, PLAN_V22 Phase 194)

Cloover braucht für jedes Projekt (`POST /api/projects`, Feld `offerPDF`) eine **ohne Anmeldung
abrufbare URL** des Angebots-PDFs; das Tool selbst läuft nur im VPN. Standardweg ist eine eigene
SharePoint-Bibliothek, in die das Tool **als Anwendung** (dieselbe App-Registrierung wie Abschnitt 1)
hochlädt und einen anonymen Lese-Link erzeugt (`app/cloover_pdf_ablage.py`, Parametrierung → Cloover →
PDF-Ablage). Voraussetzungen (Admin mit `admin@`):

1. **Site und Bibliothek anlegen** – eigene Site (z. B. `Cloover-Angebote`, Vorlage „Teamsite“ ohne
   Microsoft-365-Gruppe), darin die Dokumentbibliothek/der Ordner `Cloover-Angebote` (Parameter
   `cloover_sharepoint_ordner`). Dateien heißen `AN-C-<Nr>-<Zufall>.pdf` – nie mit Kundennamen.
2. **Anwendungsberechtigung `Sites.Selected`** (Microsoft Graph) in der App-Registrierung ergänzen und
   Admin-Zustimmung erteilen – im Gegensatz zu `Sites.ReadWrite.All` sieht die App damit **nur** die
   freigegebenen Sites. Danach der App Schreibrecht auf genau diese Site geben (Graph, als Admin):

   ```http
   POST https://graph.microsoft.com/v1.0/sites/{site-id}/permissions
   {"roles": ["write"],
    "grantedToIdentities": [{"application": {"id": "<GRAPH_CLIENT_ID>", "displayName": "Friondo Angebotstool"}}]}
   ```

   Die `site-id` liefert `GET https://graph.microsoft.com/v1.0/sites/friondo.sharepoint.com:/sites/Cloover-Angebote`
   (Graph Explorer oder PowerShell `Invoke-MgGraphRequest`); alternativ PnP PowerShell:
   `Grant-PnPAzureADAppSitePermission -AppId <GRAPH_CLIENT_ID> -DisplayName "Friondo Angebotstool" -Site https://friondo.sharepoint.com/sites/Cloover-Angebote -Permissions Write`.
3. **Freigabe „Jeder mit dem Link“ erlauben** – Mandant (SharePoint Admin Center → Richtlinien → Freigabe:
   „Jeder“) und die Site selbst (`Set-SPOSite -Identity https://friondo.sharepoint.com/sites/Cloover-Angebote
   -SharingCapability ExternalUserAndGuestSharing`); Ablauf anonymer Links auf mindestens 180 Tage stellen
   (`Set-SPOTenant -RequireAnonymousLinksExpireInDays 180` bzw. je Site `-AnonymousLinkExpirationInDays 180`).
   Das Tool legt die Links mit `createLink` (type `view`, scope `anonymous`, `expirationDateTime` = +180 Tage)
   an und übergibt Cloover die Download-URL (`…?download=1`).
4. Im Tool: Parametrierung → Cloover → PDF-Ablage: Anbieter `sharepoint`, Site als
   `friondo.sharepoint.com:/sites/Cloover-Angebote` (oder Site-ID), Ordner, **„Test-PDF ablegen und prüfen“**
   (lädt ein PDF ohne Kundendaten hoch, prüft den anonymen Link per HEAD und das Ersetzen). Der Graph-Modus muss
   **anwendung** sein (Abschnitt 3) – im Modus delegiert ist die Ablage gesperrt.

Fehlerbilder: HTTP 403 beim Upload = `Sites.Selected` fehlt oder nur `read`; 403/400 bei `createLink` =
anonyme Freigabe für Mandant oder Site nicht erlaubt; HEAD-Prüfung rot = Link braucht Anmeldung (Freigabe
prüfen). Alternative ohne SharePoint: Anbieter `basis_url` = Token-Route `GET /oeffentlich/cloover/<token>.pdf`
unter `BASIS_URL` (nur mit öffentlicher HTTPS-Adresse des Tools, Konzept Erreichbarkeit). Details und
Rückfragen an Cloover (anderer Upload-Weg, Gültigkeitsdauer der URL): `docs/cloover-api.md` Abschnitt 8.
