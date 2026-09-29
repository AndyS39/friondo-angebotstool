# Heizreport-API – Recherche, Konfiguration, Anfrage an den Support

Stand: 29.09.2026 (PLAN_PROJ_V4, Phase 93.1)

## 1. Ergebnis der Recherche

| Geprüft | Ergebnis |
|---|---|
| `https://heizreport.de/api/` | erreichbar; antwortet ohne Nutzdaten mit **HTTP 400 „kein JSON Object empfangen“** → die API erwartet JSON per POST |
| Hilfeseite „Grundlagen zur Nutzung der API-Schnittstelle“ | derzeit **404** (ohne Login nicht erreichbar) |
| Hilfeseiten „Ändern von Projektdaten“, „Business-Account“ | derzeit **404** |
| Hilfeseite Webhooks | lesbar: Webhook-Payload mit den Feldern `event` (`webhookcheck` / `webhooksave`), `authenticate` und `projektKey` (9-stellig) |
| Suchmaschinen-Auszüge | nennen eine Aktion `editReportData` sowie die Felder `apiKey` und `projektKey` |
| OpenAPI/Swagger, Postman-Collection | **nicht gefunden** |
| API-Freischaltung | laut Heizreport über **mail@heizreport.com** (Business-Account) |

**Fazit: Eine öffentliche API-Dokumentation gibt es nicht.** Wahrscheinliches
Muster (nicht bestätigt): ein Endpunkt `https://heizreport.de/api/`, JSON-POST
mit `apiKey` im Body, `action` als Befehl, `projektKey` als Projektkennung.

## 2. Wie das Tool vorbereitet ist

`app/heizreport_api.py` ist ein **generischer REST-Client** – alles Wichtige
ist in *Parametrierung → Projektierung-Einstellungen → Heizreport-API*
einstellbar, ohne Code-Änderung:

| Feld | Bedeutung | Vorschlag nach Recherche |
|---|---|---|
| Basis-URL | Endpunkt | `https://heizreport.de/api/` |
| Auth-Art | API-Key im Header · Bearer · Basic · API-Key im JSON-Body | **API-Key im JSON-Body** |
| Header-Name / JSON-Feld | Name des Schlüsselfelds | `apiKey` |
| API-Schlüssel | aus dem Business-Account | – |
| Endpunkt „Projekt anlegen“ + Methode | Pfad relativ zur Basis-URL | leer (= Basis-URL) · POST |
| Endpunkt „Projekt-Status“ | Pfad, `{projekt_key}` erlaubt | leer · POST |
| Endpunkt „Ergebnis abrufen“ | Pfad, `{projekt_key}` erlaubt | leer · POST |
| Feld-Mapping hin (JSON) | Zielfeld → Quelle | siehe unten |
| Feld-Mapping zurück (JSON) | `projekt_key`, `heizlast_kw`, `status` → Pfad in der Antwort | aus der Doku übernehmen |

Quellen im Mapping hin: `kunde.<attr>`, `projekt.<attr>`, `gewerk.<attr>`,
`steckbrief.<feld>`, `fp.<FP-Key>`, `erfassung.<Frage-ID>`, `fest:<Text>`,
`aktion:<Name>`. Punkte im Zielfeld erzeugen verschachtelte Objekte
(`adresse.plz` → `{"adresse": {"plz": …}}`).

**Verbindung testen** (Button in den Einstellungen) schickt einen GET mit der
eingestellten Authentifizierung an die Basis-URL und zeigt den HTTP-Code samt
Antwortauszug (400 „kein JSON Object“ heißt: Server erreichbar, erwartet POST).

**Ablauf an der Aufgabe „Heizlastberechnung liegt vor“:**

- API konfiguriert (Basis-URL + Schlüssel): Buttons **„Projekt im Heizreport
  anlegen“** (Mapping hin; der Projekt-Schlüssel aus der Antwort wird am
  Gewerk gespeichert) und **„Ergebnis abrufen“** (schreibt Heizlast kW +
  Datum + Quelle „Heizreport API“ und erledigt die Aufgabe).
- API nicht konfiguriert: wie bisher Link ↗ (`url_heizreport`) + Ablage/Upload;
  die Heizlast wird in der Akte von Hand eingetragen (Quelle „manuell“).

Webhooks (Heizreport meldet `webhooksave` mit `projektKey`) sind bewusst noch
**nicht** angebunden – das Tool ist nicht aus dem Internet erreichbar. Bei
Bedarf später: Endpoint `/api/heizreport/webhook` + `authenticate` prüfen.

## 3. Anfragetext an den Heizreport-Support (zum Kopieren)

> **An:** mail@heizreport.com
> **Betreff:** API-Zugang Business-Account – Friondo GmbH
>
> Guten Tag,
>
> wir (Friondo GmbH, Fachbetrieb für Wärmepumpen und PV) nutzen Heizreport
> für die Heizlastberechnung nach DIN EN 12831 und möchten unsere interne
> Projektsoftware per API anbinden: Projekt mit Kundenadresse und
> Gebäudedaten anlegen und die berechnete Heizlast (kW) nach Abschluss
> automatisch abrufen.
>
> Dazu bitten wir um:
>
> 1. Informationen zum **Business-Account** (Konditionen, API im Umfang
>    enthalten?) bzw. Freischaltung der API für unser Konto,
> 2. die **API-Dokumentation** (Endpunkte, Aktionen wie Projekt anlegen /
>    Projektdaten ändern / Ergebnis abrufen, Feldliste, Fehlercodes, Webhooks),
> 3. **Test-Zugangsdaten** bzw. ein Testprojekt, damit wir die Anbindung vor
>    dem Echtbetrieb prüfen können,
> 4. Angaben zu **Rate-Limits** und Verfügbarkeit,
> 5. Informationen zu **Datenschutz**: Serverstandort, Auftragsverarbeitungs-
>    vertrag (AVV nach Art. 28 DSGVO), Löschfristen für Projektdaten.
>
> Ansprechpartner bei uns: Andreas Scheelen, [E-Mail / Telefon]
>
> Vielen Dank und freundliche Grüße
> Friondo GmbH

## 4. Nach Eingang der Doku

1. Einstellungen gemäß Doku füllen (Tabelle oben), **Verbindung testen**.
2. Testprojekt: an einem Demo-Gewerk „Projekt im Heizreport anlegen“ →
   Projekt-Schlüssel erscheint an der Aufgabe → nach Berechnung „Ergebnis
   abrufen“.
3. Mapping zurück anpassen, bis kW korrekt ankommt; Abweichungen in
   `docs/projektierung-entscheidungen.md` festhalten.
