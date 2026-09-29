# Formular-Standard für Landingpages (Agentur)

Stand: v21 (PLAN_LEAD_V1.1 Phase 87). Zwei Wege bringen einen Lead ins
Friondo-Tool: **E-Mail an leads@friondo.de** (Standard) oder **REST-API**
(`POST /api/leads`, siehe docs/leads-api.md).

## 1. E-Mail-Weg

**Betreff (Pflicht):** `[LEAD] <quelle> <kampagne>`

| Teil | Bedeutung | Beispiel |
|---|---|---|
| `<quelle>` | Quellen-Key (Kleinbuchstaben, `a–z 0–9 _ -`); unbekannte Keys legen sich selbst an (Typ Landingpage) | `landingpage`, `website`, `portal_a` |
| `<kampagne>` | Kampagnen-Slug = **eine Landingpage** (`lp-<thema>-<ort>`); unbekannte Slugs legen sich selbst an | `lp-waermepumpe-duisburg`, `lp-pv-speicher` |

**Textkörper:** eine Zeile je Feld, Format `Feld: Wert`

| Feld | Pflicht | Hinweis |
|---|---|---|
| `Anrede` | – | Herr / Frau / Firma |
| `Vorname` | – | |
| `Nachname` | **ja** | bei Firmen der Firmenname |
| `Straße` | – | Straße und Hausnummer |
| `PLZ` | **ja** | 5-stellig |
| `Ort` | – | |
| `Telefon` | **ja** (oder E-Mail) | |
| `E-Mail` | **ja** (oder Telefon) | |
| `Sparte` | **ja** | Schreibweisen: `WP` / `Wärmepumpe`, `PV` / `Photovoltaik`, `KL` / `Klima`, `WB` / `Wallbox`; mehrere kommagetrennt |
| `Wunschzeit` | – | `vormittags`, `nachmittags`, `abends`, `samstag`; mehrere kommagetrennt |
| `Nachricht` | – | Freitext des Interessenten |
| `Werbeeinwilligung` | – | `ja` / `nein` (Double-Opt-in bleibt bei der Agentur) |
| `utm_source`, `utm_medium`, `utm_campaign`, `utm_content` | – | aus versteckten Formularfeldern (siehe 3) |

**Beispielmail**

```
An: leads@friondo.de
Betreff: [LEAD] landingpage lp-waermepumpe-duisburg

Anrede: Frau
Vorname: Maria
Nachname: Beispiel
Straße: Musterweg 12
PLZ: 47139
Ort: Duisburg
Telefon: 0203 123456
E-Mail: maria@beispiel.de
Sparte: Wärmepumpe, PV
Wunschzeit: abends
Nachricht: Ölheizung von 1998, bitte um Rückruf.
Werbeeinwilligung: ja
utm_source: google
utm_medium: cpc
utm_campaign: lp-waermepumpe-duisburg
utm_content: anzeige-a
```

## 2. Zuordnung im Tool

Quelle (aus dem Key) → Kampagne (aus dem Slug; fehlt er, über `utm_campaign`)
→ der Kanal der Quelle wird an Kunde und Vorgang gesetzt, falls dort keiner
steht → das Angebotsprofil folgt dem Kanal. Automatisch angelegte Quellen/
Kampagnen erscheinen im Tool mit Badge „neu · automatisch angelegt“, bis ein
Admin sie zuordnet (Typ, Kanal, Kosten, Budget).

## 3. utm-Felder

Als **versteckte Formularfelder** mitsenden (`<input type="hidden"
name="utm_campaign" …>`), befüllt aus den URL-Parametern der Landingpage.
`utm_campaign` sollte dem Kampagnen-Slug entsprechen.

## 4. Demo-Modus / Test

Solange das Lead-Management im Demo-Modus läuft, gehen automatische Mails an
Interessenten nur an die Testadresse des Tools. Testleads bitte mit
Nachname `Test` und einer Testadresse der Agentur senden; der Slug
`lp-test-neu` ist für Tests reserviert.

## 5. Alternative: API

`POST /api/leads` mit Header `X-Api-Key` (Key je Quelle aus der
Parametrierung) und JSON-Rumpf (`quelle`, `kampagne`, `utm_campaign`,
Felder wie oben in Kleinschreibung). Details und Antwortcodes:
docs/leads-api.md.
