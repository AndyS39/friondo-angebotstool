# Heizreport API v2 Anleitung für Claude

Diese Datei erklärt die öffentliche Heizreport Kunden-API v2 für die Erstellung von Integrationen. Sie enthält keine Zugangsdaten und erteilt keine Berechtigung, eigenständig Kundendaten zu ändern. Verbindliche maschinenlesbare Beschreibung: [openapi.json](openapi.json). Deutsche Anleitung mit Swagger UI: [docs.html](docs.html). API-Version: 2.4.0.

## Verbindung und Zugriff

Produktive Basisadresse: `https://heizreport.net/api/v2`. Für API-Aufrufe ausschließlich diese Basisadresse verwenden. Nur HTTPS verwenden. Den vom Kunden bereitgestellten Token ausschließlich im HTTP-Header `Authorization: Bearer TOKEN` übermitteln. Nicht in URLs, Quellcode, Beispielen oder Logs speichern. Der Token ist kein JWT und darf nicht aus einer Projekt-ID abgeleitet werden.

Jeder Kunde hat genau einen Token mit allen öffentlich freigegebenen Rechten auf seine eigenen Projekte. Keine Scopes, kein OAuth-Ablauf. Die interne `/api/v1` ist für diese Integration nicht verfügbar. Ein entsperrter Kunde darf eigene Projektdaten auch bei abgelaufener Lizenz erfassen. Projektanlage benötigt eine aktive Jahres- oder Bildungslizenz. Berechnungen und PDFs unterliegen zusätzlichen Projekt-, Lizenz-, Umkreis- und gegebenenfalls Funktionsprüfungen.

Fest maximal zwei authentifizierte Zugriffe in jedem gleitenden Zeitraum von einer Sekunde, gemeinsam über alle geschützten Endpunkte eines Kunden. Das Limit lässt sich nicht durch Parallelisierung, Tokenrotation oder mehrere Clients erhöhen. Fachlich abgelehnte authentifizierte Aufrufe zählen ebenfalls. Requests in einer gemeinsamen Warteschlange für den Kunden serialisieren und z. B. mindestens 600 ms Abstand verwenden; andere Clients desselben Kunden können weiterhin 429 verursachen. Bei HTTP 429 mindestens den Header `Retry-After` (derzeit 1 Sekunde) abwarten. Auch ungültige Tokens unterliegen einem festen Limit pro Quell-IP.

## Verfügbare Endpunkte

| Methode | Pfad relativ zur Basisadresse | Funktion | Zugriff |
| --- | --- | --- | --- |
| GET | `/` | API-Version abrufen | öffentlich |
| GET | `/health` | Erreichbarkeit prüfen | öffentlich |
| GET | `/reports` | Eigene Projekte auflisten | Bearer-Token |
| POST | `/reports` | Leeres Projekt anlegen | Bearer-Token |
| OPTIONS | `/reports` | OPTIONS-Antwort prüfen | öffentlich |
| POST | `/reports/with-data` | Projekt mit Daten anlegen | Bearer-Token |
| PATCH | `/reports/{projectKey}` | Projektdaten ändern | Bearer-Token |
| GET | `/reports/{projectKey}` | Projektdetails lesen | Bearer-Token |
| PUT | `/reports/{projectKey}/password` | Projektpasswort ändern | Bearer-Token |
| GET | `/reports/{projectKey}/pdf` | PDF erzeugen und Link abrufen | Bearer-Token |
| GET | `/reports/{projectKey}/pictures` | Vorhandene Bilder auflisten | Bearer-Token |
| GET | `/reports/{projectKey}/results` | Berechnungsergebnisse abrufen | Bearer-Token |
| GET | `/reports/{projectKey}/rooms` | Räume auflisten | Bearer-Token |
| POST | `/reports/{projectKey}/rooms` | Raum anlegen | Bearer-Token |
| GET | `/reports/{projectKey}/rooms/{roomId}` | Einzelnen Raum lesen | Bearer-Token |
| PATCH | `/reports/{projectKey}/rooms/{roomId}` | Raumbasisdaten ändern | Bearer-Token |

OPTIONS liefert für beliebige API-Pfade 204. Das ist keine pauschale CORS-Freigabe. Der Healthcheck bestätigt die Erreichbarkeit des API-Codes, keine vollständige Datenbank- oder Lizenzprüfung.

## Projektanlage und Änderungen

Neue Projekt-Keys sind neun Kleinbuchstaben. Die Route akzeptiert neun Buchstaben einschließlich Großbuchstaben. Den Schlüssel exakt aus `projektHeader.key` übernehmen; keine Schlüssel erraten. Fremde und nicht vorhandene Projekte liefern beide 404. `GET /reports` liefert die Gruppen `projekte`, `leads`, `api`, `archiv`, keine Paginierung. `GET /reports/{projectKey}` liefert die freigegebenen Projektdaten und Kopfwerte; keine internen Einstellungen oder Passwörter.

Für `POST /reports` Body weglassen oder `{}` senden. Für vorbelegte Anlage und PATCH genau eine Hülle `projectData` verwenden. Der bisherige Name `projektData` ist weiterhin erlaubt; beide niemals gemeinsam senden. PATCH ändert nur die übermittelten Felder. JSON-Bodies benötigen `Content-Type: application/json` und dürfen maximal 65536 Bytes groß sein. Keine beliebigen Datenbankfelder senden. POST-Projektanlage ist nicht idempotent: bei einem Timeout nicht blind wiederholen, sondern zunächst die Projektliste prüfen. Bei erfolgreicher Anlage ist der HTTP-Status 201, während das historische JSON-Feld `status` 200 enthält.

Fiktives Beispiel für `POST /reports/with-data`:

```json
{
  "projectData": {
    "projektName": "API-Testprojekt",
    "projektPostleitzahl": "10115",
    "projektBewohner": 4,
    "projektBaujahr": 1995,
    "email": "api-test@example.com"
  }
}
```

## Erlaubte Projektfelder

Alle Felder sind optional, es muss aber mindestens ein freigegebenes Feld übermittelt werden. Optionale Werte lassen sich mit leer/null löschen. Die Objektpostleitzahl darf nicht leer sein und muss in den Klimadaten existieren. Nur skalare Werte senden; keine Arrays oder Objekte als Feldwerte. Eingaben werden normalisiert, Rückgabewerte sind häufig Zeichenketten.

| Feld | Bedeutung und Eingaberegel |
| --- | --- |
| `projektName` | Projektname. Zeichenketten empfohlen; einfache Zahlen und null werden zu Text normalisiert. Kein NUL-Zeichen. |
| `projektPostleitzahl` | Objektstandort. Muss in den Heizreport-Klimadaten existieren; darf nicht geleert werden. |
| `projektArtHeizung` | Kennzahl der Heizungsart; Zahl oder numerische Zeichenkette. Leer/null löscht den optionalen Wert. |
| `projektAlterHeizung` | Kennzahl der Altersklasse der Heizung; Zahl oder numerische Zeichenkette. Leer/null löscht den optionalen Wert. |
| `projektBewohner` | Anzahl der Bewohner. Bereich 0–10000; ganzzahlig. Numerische Zeichenketten (auch Dezimalkomma) werden akzeptiert und geprüft. Leer/null löscht den Wert. |
| `projektJahresverbrauch` | Jahresverbrauch passend zur gewählten Heizungsart. Bereich 0–1000000000. Numerische Zeichenketten (auch Dezimalkomma) werden akzeptiert und geprüft. Leer/null löscht den Wert. |
| `projektBaujahr` | Baujahr. Bereich 1000–2100; ganzzahlig. Numerische Zeichenketten (auch Dezimalkomma) werden akzeptiert und geprüft. Leer/null löscht den Wert. |
| `projektTrinkwasser` | Kennzahl der Trinkwasserbereitung; Zahl oder numerische Zeichenkette. Leer/null löscht den optionalen Wert. |
| `projektWaermeerzeugerSolarStatus` | Solarer Wärmeerzeuger vorhanden. true/on/1 wird intern on; false/off/0/leer/null wird intern leer. |
| `projektWaermeerzeugerSolarArt` | Kennzahl der Solarart; Zahl oder numerische Zeichenkette. Leer/null löscht den optionalen Wert. |
| `projektKollektorflaecheSolar` | Kollektorfläche in m². Bereich 0–1000000. Numerische Zeichenketten (auch Dezimalkomma) werden akzeptiert und geprüft. Leer/null löscht den Wert. |
| `projektWaermeerzeugerHolzStatus` | Holz-Wärmeerzeuger vorhanden. true/on/1 wird intern on; false/off/0/leer/null wird intern leer. |
| `projektJahresverbrauchHolz` | Holzverbrauch passend zur gewählten Holzart. Bereich 0–1000000. Numerische Zeichenketten (auch Dezimalkomma) werden akzeptiert und geprüft. Leer/null löscht den Wert. |
| `projektWaermeerzeugerHolzArt` | Kennzahl der Holzart; Zahl oder numerische Zeichenkette. Leer/null löscht den optionalen Wert. |
| `email` | E-Mail-Adresse des Kontakts; leer zum Löschen. Zeichenketten empfohlen; einfache Zahlen und null werden zu Text normalisiert. Kein NUL-Zeichen. |
| `anrede` | Anrede des Kontakts. Zeichenketten empfohlen; einfache Zahlen und null werden zu Text normalisiert. Kein NUL-Zeichen. |
| `vorname` | Vorname des Kontakts. Zeichenketten empfohlen; einfache Zahlen und null werden zu Text normalisiert. Kein NUL-Zeichen. |
| `name` | Nachname des Kontakts. Zeichenketten empfohlen; einfache Zahlen und null werden zu Text normalisiert. Kein NUL-Zeichen. |
| `strasse` | Straße des Kontakts. Zeichenketten empfohlen; einfache Zahlen und null werden zu Text normalisiert. Kein NUL-Zeichen. |
| `hausnummer` | Hausnummer des Kontakts. Zeichenketten empfohlen; einfache Zahlen und null werden zu Text normalisiert. Kein NUL-Zeichen. |
| `plz` | Postleitzahl des Kontakts; 4–5 Ziffern oder leer/null zum Löschen. Als Zeichenkette senden, damit führende Nullen erhalten bleiben. |
| `ort` | Ort des Kontakts. Zeichenketten empfohlen; einfache Zahlen und null werden zu Text normalisiert. Kein NUL-Zeichen. |
| `telefon` | Telefonnummer des Kontakts. Zeichenketten empfohlen; einfache Zahlen und null werden zu Text normalisiert. Kein NUL-Zeichen. |
| `bemerkungen` | Bemerkungen zum Projekt. Zeichenketten empfohlen; einfache Zahlen und null werden zu Text normalisiert. Kein NUL-Zeichen. |

Heizungsart: 1–6; Heizungsalter und Trinkwasser: 1–3; Solarart: 1 oder 2; Holzart: 1500, 1550, 1800, 2000, 2200 oder 2201. Kennzahlen nicht eigenständig mit erfundenen fachlichen Bezeichnungen belegen. Detaillierte Typen, erlaubte Werte und Längen stehen in `components.schemas.ProjectData` der OpenAPI-Datei.

## Räume lesen und erfassen

`GET /reports/{projectKey}/rooms` liefert `rooms[]`; `GET /reports/{projectKey}/rooms/{roomId}` liefert `room`. Beide enthalten `id`, `projectKey` und `roomData`. Die Raum-ID exakt übernehmen. Sie muss zum angegebenen eigenen Projekt gehören; IDs eines anderen Projekts liefern auch dann 404, wenn beide Projekte demselben Kunden gehören.

`POST /reports/{projectKey}/rooms` erwartet `{"roomData":{"raumBezeichnung":"Wohnzimmer","raumEtage":1,"raumFlaeche":25.5,"raumHoehe":2.5,"raumTemperatur":20}}`. HTTP 201; ID steht in `room.id`. `PATCH /reports/{projectKey}/rooms/{roomId}` mit derselben Hülle ändert nur gesendete Felder. Kein Idempotency-Key: nach Timeout zuerst Raumliste prüfen. Beide Schreibaufrufe sind auch bei abgelaufener Jahreslizenz für entsperrte Kunden verfügbar. Keine zusätzlichen allgemeinen Bearbeitungsrechte ableiten.

Erlaubt sind ausschließlich `raumBezeichnung` (Text, 1–120 Zeichen nach Trimmen), `raumNotiz` (Text, maximal 255 Zeichen), `raumEtage` (Ganzzahl 0–7), `raumFlaeche` (m², größer 0 bis 100000), `raumHoehe` (m, größer 0 bis 100) und `raumTemperatur` (Temperatur in °C: 7 oder ganzzahlig 16–26). Zahlen als JSON-Zahl oder numerische Zeichenkette, bei Fläche/Höhe auch Dezimalkomma; maximal 32 Zeichen. Fläche/Höhe leer oder null löscht den Wert. Notiz mit leerer Zeichenkette löschen. Raumname darf nicht leer sein; Raum-/Projekt-ID und Baujahr niemals schreiben.

`raumEtage` bleibt für Ein- und Ausgabe eine Geschoss-ID (in Antworten als Zeichenkette): 0 = Keller (KG), 1 = Erdgeschoss (EG), 2 = 1. Obergeschoss (1. OG), 3 = 2. Obergeschoss (2. OG), 4 = 3. Obergeschoss (3. OG), 5 = 4. Obergeschoss (4. OG), 6 = 5. Obergeschoss (5. OG), 7 = Dachgeschoss (DG). Standard bei Anlage: 1. Jede Raumantwort, auch in `rooms[]` sowie nach POST/PATCH, enthält in `roomData` zusätzlich die nur lesbaren Felder `raumEtageBezeichnung` und `raumEtageKuerzel`, z. B. `{"raumEtage":"1","raumEtageBezeichnung":"Erdgeschoss","raumEtageKuerzel":"EG"}`. Diese beiden Felder niemals als Eingaben senden; sie werden aus der ID abgeleitet. Bei fehlender oder unbekannter gespeicherter Geschoss-ID sind Bezeichnung und Kürzel leer. Raumtemperaturen werden in °C gesendet und als JSON-Zahl zurückgegeben, beispielsweise `raumTemperatur: 20` für 20 °C. Erlaubt sind 7 und die ganzen Temperaturen 16–26; andere Werte liefern 422. Intern gespeicherte IDs bleiben unverändert (0=7 °C, 1=16 °C bis 11=26 °C). Der Standard bei Anlage ist 20 °C. Bei fehlender oder unbekannter gespeicherter Temperatur-ID liefert die API null.

Bei Anlage ist der Raumname Pflicht. Ohne weitere Angaben: Geschoss 1, Höhe 2.5 m, Temperatur 20 °C, Fläche und Notiz leer. `raumBaujahr` wird bei Anlage vom Projekt übernommen und nur lesend zurückgegeben; spätere Projektänderungen führen es nicht automatisch nach. Raumbasisdaten allein reichen noch nicht für vollständige Heizlastberechnungen. Es werden keine U-Werte oder Bauteile automatisch ergänzt. Bestehende interne Raumdaten werden bei PATCH nicht überschrieben. U-Werte und Heizflächen folgen in späteren Ausbaustufen.

## Berechnungen und Einheiten

`GET /reports/{projectKey}/results` berechnet mit den vorhandenen Projektdaten. Optional `flowTemperature` (25–95 °C) und `spread` (größer 0, kleiner als Vorlauftemperatur, in K) gemeinsam übergeben. Beispiel: `?flowTemperature=55&spread=10`. Bisherige Aliase: `vorlaufT` und `spreizung`. Bei beiden Schreibweisen hat der aktuelle Name je Parameter Vorrang. Für neue Integrationen ausschließlich das aktuelle Paar verwenden. Diese Parameter ändern die gespeicherten Projektvorgaben nicht.

Bei fehlenden Berechnungsdaten kommt HTTP 422 mit `details.type = calculation_unavailable`. Nicht allein aus der erfolgreichen Projektanlage vollständige Berechnungsergebnisse erwarten: Räume und Heizflächen müssen bereits im Projekt erfasst sein.

Die Antwort enthält `project.key`, `results` und die bisherige Kompatibilitätsstruktur `projekt.abgleichFBH`. Fußbodenheizung: `results.floorHeatingBalance.groups[].rooms[].setting.value` in `l/min`; `setting.unit` ist explizit `l/min`. `flowRate` und `flowRateSum` stehen dagegen in `l/h`. Die bisherige Struktur `projekt.abgleichFBH[].raeume[].durchfluss` enthält `l/min`. Heizlasten der hier beschriebenen FBH-Räume sind in W, Spreizungen in K. Für weitere vom Rechenkern gelieferte Detailstrukturen keine unbekannten Felder oder Einheiten erfinden; OpenAPI kennzeichnet derzeit nur teilweise beschriebene Strukturen.

## PDF und Bilder

`GET /reports/{projectKey}/pdf?type=heizreport` oder `type=check` erzeugt ein Dokument und kann es speichern. Obwohl die HTTP-Methode GET lautet, ist dies keine folgenlose Leseoperation. Der Aufruf kann außerdem einen Webhook auslösen. Vor der Ausführung die beabsichtigte Dokumenterstellung mit dem Nutzer klären, falls sie nicht bereits beauftragt ist.

Die Antwort ist JSON, kein PDF-Stream. `linkToDocument`, `file.url` und vorhandene `file.viewerUrl` werden als vollständige URLs mit `https://heizreport.net/` ausgegeben. Den PDF-Link unverändert verwenden. `GET /reports/{projectKey}/pictures` liefert vorhandene Bilder als `pictures[]` mit `id`, `url`, `type`, `roomName`. PDF- und Bildlinks sind signiert und zeitlich begrenzt; sie sind vertraulich. Relative Bildlinks am Server-Ursprung (z. B. `https://heizreport.net`), nicht am `/api/v2`-Pfad auflösen. Beim Abrufen dieser signierten Links keinen API-Token an andere Hosts weitergeben. Keine dauerhafte Gültigkeit zusagen; bei abgelaufenen Bildlinks die Liste neu abrufen. Wiederholte PDF-Aufrufe können weitere Dokumente erzeugen.

## Projektpasswort

`PUT /reports/{projectKey}/password` erwartet `{"newPassword":"..."}` mit 12–256 Zeichen. Ändert das Portalpasswort des Projekts, nicht den API-Token. Das Passwort als vertrauliche Eingabe behandeln und den Aufruf nur im ausdrücklich beauftragten Projekt ausführen.

## Webhook

Die Webhook-Adresse und der separate Authentifizierungswert werden in Pro unter Integrationen eingerichtet, nicht über einen öffentlichen v2-Endpunkt. Ausgehend: JSON-POST an diese Adresse bei erster erfolgreicher PDF-Erstellung; Header `X-Heizreport-Event: pdf.generated` und `X-Heizreport-Delivery: EVENT_ID`. Payload enthält `event`, `eventType`, `eventId`, `authenticate`, `projektKey`, `projectKey`, `generatedAt` und `document`.

`eventType` ist `pdf.generated`, `event` ist `webhookheizreport` oder `webhookcheck`; `document.type` ist `heizreport` oder `heatpump-check`. Der Receiver soll den konfigurierten Wert in `authenticate` prüfen und `eventId` zur Deduplizierung nutzen. Eine 2xx-Antwort bestätigt den Empfang. Keine HMAC-Signatur behaupten. Derzeit keine automatische Wiederholung und keine garantierte Zustellung; ein reserviertes Ereignis pro Projekt. Webhook-Fehler verhindern die PDF-Ausgabe nicht. Private Ziel-IP-Adressen und Weiterleitungen werden abgewiesen.

## Fehler behandeln

Fehlerantwort: `{"status":422,"error":"Fehlermeldung","details":{"type":"validation","field":"..."}}`. Details können zusätzliche Angaben enthalten; `field` ist nicht immer vorhanden. Den HTTP-Status für die Ablaufsteuerung verwenden.

- 400: fehlerhaftes JSON.
- 401: Token fehlt/ist ungültig oder Kunde ist gesperrt; Tokenzuordnung prüfen.
- 403: erforderliche Projekt-, Lizenz- oder Funktionsberechtigung fehlt.
- 404: Projekt fehlt oder gehört einem anderen Kunden; ungültig aufgebaute Pfade ebenfalls nicht gefunden.
- 413: Body größer als 64 KiB.
- 415: falscher Content-Type.
- 422: Felder/Werte ungültig oder Berechnungsdaten noch nicht verfügbar.
- 429: festes Limit erreicht, mindestens Retry-After warten.
- 500/503: Serverfehler oder vorübergehend nicht verfügbar; bei Schreiboperationen vor Wiederholung prüfen, ob die Änderung bereits erfolgt ist.

## Noch nicht verfügbare Funktionen

Keine öffentlichen Endpunkte zum Erfassen von U-Werten oder Heizkörpern, Hochladen von Bildern, Löschen von Projekten oder Räumen oder Verwalten von API-Tokens. Keine entsprechenden Pfade aus der internen v1 übernehmen. Erweiterungen ausschließlich nach der dann aktualisierten OpenAPI-Datei verwenden.

## Empfohlener Testablauf

1. Healthcheck ohne Token ausführen.
2. Eigenen Token lokal konfigurieren und Projektliste lesen.
3. Nach ausdrücklicher Beauftragung ein Testprojekt mit fiktiven Daten anlegen.
4. Schlüssel aus `projektHeader.key` übernehmen und Datenänderungen am Testprojekt prüfen.
5. Ergebnisse erst bei ausreichenden Projektdaten abrufen; PDF-Erzeugung gezielt beauftragen.
6. Ratenlimit und Fehlerfälle mit der [Postman-Collection](postman_collection.json) prüfen. Fremdprojektprüfung benötigt einen tatsächlich einem anderen Kunden gehörenden Schlüssel; ein erfundener Schlüssel beweist keine Kundentrennung.
