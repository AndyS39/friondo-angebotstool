# Lead-API: POST /api/leads (v12, Lead-Management V1 · v23: Info-Veranstaltung)

REST-Eingang für Website, Landingpages, Förderrechner, Portale mit Webhook
und die Anmeldungen zur Info-Veranstaltung (Marketingagentur). Im LAN sofort
nutzbar; von außen erst mit öffentlicher HTTPS-Route (siehe
LEADMANAGEMENT-KONZEPT.md Abschnitt 15).

## Authentifizierung

Header `X-Api-Key` mit dem Schlüssel der Quelle. Schlüssel erzeugen:
Parametrierung → Lead-Quellen & Kampagnen → Häkchen „neu“ beim Speichern
der Quelle (vollständiger Schlüssel im Maus-Tooltip). Rate-Limit: 60
Aufrufe je Minute je Schlüssel (429 darüber).

## Anfrage

`POST http://192.168.35.4:8000/api/leads` mit JSON-Rumpf:

| Feld | Typ | Pflicht |
|---|---|---|
| `quelle` | Quellen-Key (überschreibt die Schlüssel-Quelle), z. B. `info_veranstaltung` | nein |
| `kampagne` | Kampagnen-Name | nein |
| `anrede`, `vorname` | Text | nein |
| `nachname` | Text | **ja** |
| `strasse`, `ort` | Text | nein |
| `plz` | Text | **ja** |
| `telefon` / `email` | Text | **mind. eines** |
| `sparten` | Liste aus WP/PV/KL/WB/**GW** (Gewerbe); Klartext-Aliase wie „Wärmepumpe“, „Gewerbe“ werden erkannt | **ja**, außer die Quelle hat Standard-Sparten (siehe unten) |
| `veranstaltung` | Datum `YYYY-MM-DD` der gewählten Info-Veranstaltung (v23) | nein |
| `wunschzeiten` | Liste (vormittags/nachmittags/abends/samstag) | nein |
| `nachricht` | Freitext | nein |
| `utm_source`, `utm_medium`, `utm_campaign`, `utm_content` | Text | nein |
| `einwilligung_werbung` | bool (Quelle wird als „portal“ gespeichert) | nein |
| `rohdaten` | beliebiges JSON (wird am Vorgang gespeichert) | nein |

Zahlen statt Text (PLZ, Telefon) und Sparten als kommagetrennter Text
werden akzeptiert; eine vierstellige PLZ bekommt die führende Null zurück.

### Standard-Sparten der Quelle (v23)

Fehlt `sparten` oder enthält es keinen gültigen Code, gelten die
**Standard-Sparten der Quelle** (Parametrierung → Lead-Quellen, Feld
„Standard-Sparten“; die Quelle aus `quelle` im Rumpf hat Vorrang vor der
Schlüssel-Quelle). Erst wenn auch dort nichts hinterlegt ist, antwortet der
Endpunkt mit 422 `sparten (WP/PV/KL/WB/GW)`. Die Antwort nennt dann
`"sparten": [...]` und `"hinweis": "Sparten aus den Standard-Sparten der
Quelle übernommen"`.

### Info-Veranstaltung (v23, PLAN_LEAD_V2 Abschnitt I)

Anmeldungen zur monatlichen Info-Veranstaltung (1. Donnerstag 18:00 Uhr,
Krefeld; Feiertagsregel NRW) kommen über denselben Endpunkt. Ein Lead gilt
als **Info-Lead**, wenn die Quelle vom Typ „veranstaltung“ ist (Startquelle
`info_veranstaltung`) **oder** das Feld `veranstaltung` mitkommt.

Zuordnung zur Veranstaltung (`vorgaenge.veranstaltung_id`):

1. Feld `veranstaltung` (`YYYY-MM-DD`) → die Veranstaltung an diesem Tag.
   Gibt es keine, antwortet der Endpunkt mit **422** und den nächsten
   Terminen: `{"fehler": "Keine Info-Veranstaltung am 06.11.2026",
   "felder": ["veranstaltung"], "naechste_termine": ["2026-11-05", …]}`.
   Ein unlesbares Datum ergibt 422 `veranstaltung: Datum im Format
   YYYY-MM-DD erwartet`.
2. Ohne Feld (die Agentur liefert den Termin heute nicht mit, [OFFEN 1]):
   Standardregel A-8 **„nächste Veranstaltung ab Eingang +
   `info_vorlauf_tage` (Standard 3)“**. Beispiel: Eingang 30.09.2026 →
   01.10. fällt wegen des Vorlaufs weg → **05.11.2026**. Die Zuordnung ist im
   Board je Lead per Dropdown änderbar; Parameter in Parametrierung →
   Lead-Einstellungen (Block Info-Veranstaltung).

Info-Leads werden **immer als eigener Vorgang** angelegt – kein Anhängen an
einen offenen Vorgang, also kein 409. Stattdessen läuft der **Abgleich I5**:
Treffer, wenn (E-Mail gleich **oder** Telefon normalisiert gleich, E.164 wie
in der Suche: „0203 …“ = „+49 203 …“) **und** der Nachname gleich ist
(Groß-/Kleinschreibung, Umlaute, Leer- und Satzzeichen ignoriert) – gegen
Kunden, die bereits Vorgänge haben (Demo-Vorgänge zählen nur im Demo-Modus
mit). Bei Treffer erhält der neue Vorgang eine Aktivität vom Typ `hinweis`
„Kunde bereits im System: Vorgang #… (Phase …)“, die das Board
Info-Veranstaltung als **roten Hinweis mit Link** zeigt. Kein automatisches
Zusammenführen. Die bestehende Duplikatprüfung (Telefon E.164, E-Mail,
Name+PLZ, Adresse; Anhängen mit 409) gilt unverändert für alle anderen
Quellen.

Info-Leads sind normale Leads (Phasen Neu → In Kontaktierung → …); sie
erscheinen im Board Info-Veranstaltung in der Gruppe ihrer Veranstaltung
und nach Terminierung zusätzlich im Board Terminiert. Spalte „Teilgenommen“
(Ja/Nein, leer bis zur Veranstaltung) wird im Board gepflegt.

## Antworten

- **201** `{"vorgang_id": 123, "status": "neu", "veranstaltung": null,
  "hinweis_bestand": null}` (oder `"status": "wiederkehrer"`). Bei Info-Leads:
  `"veranstaltung": "2026-11-05"` und bei Treffer
  `"hinweis_bestand": {"vorgang_id": 98, "phase": "terminiert", "text":
  "Kunde bereits im System: Vorgang #98 (Phase Terminiert) – …"}`.
  Optional `"sparten"` + `"hinweis"`, wenn die Standard-Sparten der Quelle
  griffen.
- **409** `{"vorgang_id": 123, "status": "angehaengt", …}` – Duplikat, die
  Anfrage wurde als zusätzliche Sparte an den offenen Vorgang gehängt (nicht
  bei Info-Leads)
- **422** `{"fehler": "Pflichtfelder fehlen", "felder": […]}` bzw. die
  Veranstaltungs-Fehler oben
- **401** ungültiger/fehlender Schlüssel · **429** Rate-Limit

## curl-Beispiele

Website-Lead:

```bash
curl -X POST http://192.168.35.4:8000/api/leads \
  -H "Content-Type: application/json" \
  -H "X-Api-Key: <SCHLUESSEL>" \
  -d '{
    "quelle": "website",
    "anrede": "Herr", "vorname": "Max", "nachname": "Muster",
    "strasse": "Sonnenwall 1", "plz": "47051", "ort": "Duisburg",
    "telefon": "0203 1234567", "email": "max@example.org",
    "sparten": ["WP", "PV"],
    "wunschzeiten": ["abends"],
    "nachricht": "Bitte um Rückruf wegen Wärmepumpe.",
    "utm_source": "google", "utm_campaign": "herbst26",
    "einwilligung_werbung": true
  }'
```

Anmeldung Info-Veranstaltung (Schlüssel der Quelle `info_veranstaltung`;
`veranstaltung` optional, `sparten` optional, wenn die Quelle
Standard-Sparten hat):

```bash
curl -X POST http://192.168.35.4:8000/api/leads \
  -H "Content-Type: application/json" \
  -H "X-Api-Key: <SCHLUESSEL_INFO>" \
  -d '{
    "anrede": "Frau", "vorname": "Erika", "nachname": "Muster",
    "plz": "47798", "ort": "Krefeld",
    "telefon": "+49 2151 123456", "email": "erika@example.org",
    "sparten": ["WP"],
    "veranstaltung": "2026-11-05",
    "nachricht": "Anmeldung über die Landingpage"
  }'
```

Hinweis Demo-Modus (`lead_freigabe_modus = admin`): über die API angelegte
Leads tragen `demo = 1` und erscheinen nur im Lead-Modul. Achtung bei der
Umstellung auf `alle`: „Demo-Leads löschen“ träfe auch echte
Agentur-Anmeldungen – vorher prüfen (siehe Bestandsabgleich
`diagnose/v23_bestand_H-eingang-info-sparten.json`, Risiken).
