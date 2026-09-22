# Lead-API: POST /api/leads (v12, Lead-Management V1)

REST-Eingang für Website, Landingpages, Förderrechner und Portale mit
Webhook. Im LAN sofort nutzbar; von außen erst mit öffentlicher HTTPS-Route
(siehe LEADMANAGEMENT-KONZEPT.md Abschnitt 15).

## Authentifizierung

Header `X-Api-Key` mit dem Schlüssel der Quelle. Schlüssel erzeugen:
Parametrierung → Lead-Quellen & Kampagnen → Häkchen „neu“ beim Speichern
der Quelle (vollständiger Schlüssel im Maus-Tooltip). Rate-Limit: 60
Aufrufe je Minute je Schlüssel (429 darüber).

## Anfrage

`POST http://192.168.35.4:8000/api/leads` mit JSON-Rumpf:

| Feld | Typ | Pflicht |
|---|---|---|
| `quelle` | Quellen-Key (überschreibt die Schlüssel-Quelle) | nein |
| `kampagne` | Kampagnen-Name | nein |
| `anrede`, `vorname` | Text | nein |
| `nachname` | Text | **ja** |
| `strasse`, `ort` | Text | nein |
| `plz` | Text | **ja** |
| `telefon` / `email` | Text | **mind. eines** |
| `sparten` | Liste aus WP/PV/KL/WB | **ja** |
| `wunschzeiten` | Liste (vormittags/nachmittags/abends/samstag) | nein |
| `nachricht` | Freitext | nein |
| `utm_source`, `utm_medium`, `utm_campaign`, `utm_content` | Text | nein |
| `einwilligung_werbung` | bool (Quelle wird als „portal“ gespeichert) | nein |
| `rohdaten` | beliebiges JSON (wird am Vorgang gespeichert) | nein |

## Antworten

- **201** `{"vorgang_id": 123, "status": "neu"}` (oder `"wiederkehrer"`)
- **409** `{"vorgang_id": 123, "status": "angehaengt", …}` – Duplikat, die
  Anfrage wurde als zusätzliche Sparte an den offenen Vorgang gehängt
- **422** `{"fehler": "Pflichtfelder fehlen", "felder": […]}`
- **401** ungültiger/fehlender Schlüssel · **429** Rate-Limit

## curl-Beispiel

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

Hinweis Demo-Modus (`lead_freigabe_modus = admin`): über die API angelegte
Leads tragen `demo = 1` und erscheinen nur im Lead-Modul.
