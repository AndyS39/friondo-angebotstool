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
**Microsoft Graph** → **Delegierte Berechtigungen** → `Mail.ReadWrite`
auswählen → Hinzufügen. (Der Mitarbeiter stimmt bei der ersten Anmeldung
selbst zu; alternativ „Administratorzustimmung erteilen".)

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
