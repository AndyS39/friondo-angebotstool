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
