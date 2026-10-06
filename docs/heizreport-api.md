# Heizreport-API – Anbindung über die öffentliche Kunden-API v2 (v26)

Stand: 06.10.2026 (PLAN_PROJ_V5, Phasen 122–124). Verbindliche Beschreibung der
Schnittstelle: `docs/heizreport/openapi.json` (API-Version 2.4.0), deutsche
Anleitung `docs/heizreport/docs.html`, Postman-Sammlung
`docs/heizreport/postman_collection.json`, Integrationsregeln von Heizreport
`docs/heizreport/heizreport-CLAUDE.md` (alle am 06.10.2026 von
`https://heizreport.net/api/v2/` geladen).

## 1. Recherche 29.09.2026 (Phase 93) – überholt

Die Annahmen der Phase 93 (`https://heizreport.de/api/`, `apiKey` im JSON-Body,
Aktion `editReportData`, „keine öffentliche Dokumentation“) sind **überholt**:
Heizreport stellt seit API-Version 2.x eine öffentlich dokumentierte Kunden-API
unter `https://heizreport.net/api/v2` bereit (Bearer-Token, feste Endpunkte).
Der damals gebaute generische REST-Client bleibt als Modus „generisch“ erhalten
(Parameter `heizreport_api_url`, `heizreport_auth_art`, `heizreport_auth_header`,
`heizreport_benutzer`, `heizreport_pfad_*`, `heizreport_methode_*`,
`heizreport_mapping_hin/_zurueck`; aufklappbar unter Parametrierung → Heizreport),
wird aber nicht mehr benötigt. Der Anfragetext an den Support entfällt.

## 2. Der v2-Client (`app/heizreport_api.py`)

### Modus und Parameter (Parametrierung → Heizreport, Admin)

| Parameter | Bedeutung | Vorbelegung |
|---|---|---|
| `heizreport_modus` | `v2` (Standard) oder `generisch` (v17-Client) | `v2` |
| `heizreport_api_key` | Bearer-Token aus dem Pro-Bereich des Heizreport-Kontos (ein Token je Kunde, alle Rechte auf alle eigenen Projekte); nur serverseitig, maskiert, nie in Logs/Fehlerprotokoll/Verlauf/Exporten | leer |
| `heizreport_kennzahlen` | JSON-Zuordnung der nicht dokumentierten Kennzahlen (Abschnitt 3); leer = die Kennzahlen-Felder werden nicht gesendet | leer |
| `heizreport_pdf_ordner` | Galerie-Ordner für das Heizreport-PDF | `Montagedokumente` |
| `heizreport_pfad_heizlast` | Punktpfad zur Gebäude-Gesamtheizlast (W) in der results-Antwort (Abschnitt 2, Ergebnisstruktur) | `results.summary.heatLoad` [A-5, am Referenzprojekt zu bestätigen] |
| `url_heizreport` | Portal-Link (Button „Heizreport öffnen ↗“); aus den Projektierung-Einstellungen hierher umgezogen | leer |

`konfiguriert()` = Token gesetzt (Modus v2). Ohne Token bleibt es an der
Heizlast-Aufgabe beim Link + Upload wie bisher.

### Feste Endpunkte

Basis-URL `https://heizreport.net/api/v2`, `Authorization: Bearer <Token>`,
`Accept: application/json`, JSON-Bodies mit `Content-Type: application/json`
(< 64 KiB), Timeout 20 s. Nie `/api/v1`, nie Projekt-Schlüssel raten – der
Schlüssel kommt immer aus `projektHeader.key` (9 Buchstaben).

| Aufruf | Verwendung im Tool |
|---|---|
| `GET /` · `GET /health` | Verbindungstest (ohne Token) |
| `GET /reports` | Verbindungstest (mit Token: Gruppen projekte/leads/api/archiv) und Suche nach `projektName` nach einem Timeout der Anlage |
| `POST /reports/with-data` | „Heizreport-Projekt anlegen“ (Erfolg = HTTP 201; das JSON-Feld `status` enthält historisch 200 und wird nicht ausgewertet) |
| `GET /reports/{key}` | Prüfung eines von Hand eingetragenen Schlüssels (404 = abgelehnt) |
| `PATCH /reports/{key}` | nur `scripts/heizreport_kennzahlen.py` (Abschnitt 3) |
| `GET /reports/{key}/results` | „Heizlast abrufen“ (ohne `flowTemperature`/`spread` – Projektvorgaben gelten) |
| `GET /reports/{key}/pdf?type=heizreport` | „Heizreport-PDF ablegen“ – erzeugt bei Heizreport ein Dokument (keine Leseoperation) |

### Ratenlimit und Fehler

Heizreport erlaubt zwei authentifizierte Zugriffe je gleitender Sekunde und
Kunde. Alle authentifizierten Aufrufe laufen durch eine prozessweite
Warteschlange (`_warten()`: Lock + Zeitstempel des letzten Aufrufs, mindestens
600 ms Abstand). Bei HTTP 429 wartet der Client `Retry-After` (mindestens 1 s)
und wiederholt **genau einmal**; ein zweites 429 wird als Meldung gezeigt.
Andere Clients desselben Kunden (z. B. das Portal im Browser) zählen mit.

| Status | Meldung im Tool |
|---|---|
| 401 | Heizreport: Token ungültig oder Kunde gesperrt – Token in der Parametrierung prüfen |
| 403 | Heizreport: Lizenz oder Berechtigung fehlt (Heizreport-Konto prüfen) |
| 404 | Heizreport: Projekt nicht gefunden – gehört einem anderen Konto oder wurde gelöscht |
| 400/413/415/422 | Heizreport: `<error>` (Feld `<field>`) – aus dem Fehlerblock `{"status", "error", "details": {"type", "field"}}` |
| 422 `calculation_unavailable` | Heizreport-Projekt noch nicht berechenbar – Räume und Heizflächen im Heizreport-Portal erfassen, dann erneut abrufen |
| 429 (nach Wiederholung) | Heizreport: Ratenlimit erreicht (HTTP 429) – später erneut versuchen |
| 5xx / Timeout (Status 0) | Heizreport vorübergehend nicht erreichbar – später erneut versuchen |

Jeder fehlgeschlagene Aufruf (Status 0 oder ≥ 400) landet im Fehlerprotokoll
(Parametrierung → System & Protokolle → Fehlerprotokoll, Fehlertyp „Heizreport“)
mit Methode, URL, Status und Antwortauszug – **ohne** Authorization-Header und
ohne Tokenwert (Maskierung per Test abgesichert, `tests/test_heizreport_v26.py`).

### Verbindungstest

1. `GET /health` ohne Token, 2. `GET /` (Version), 3. `GET /reports` mit Token.
Meldung: „Verbindung OK · API-Version <version> · <n> eigene Projekte (Gruppen:
projekte <a>, leads <b>, api <c>, archiv <d>)“; Health OK, Token abgelehnt →
„Heizreport erreichbar, aber Token abgelehnt (HTTP 401)“; sonst die Meldung aus
der Tabelle oben.

### Ablauf an der Aufgabe „Heizlastberechnung liegt vor“ (Paket Feinplanung VOT)

Modus v2 mit Token:

1. **Heizreport-Projekt anlegen** (nur solange kein Schlüssel am Gewerk):
   `POST /reports/with-data` mit `projektdaten_v2()` (Abschnitt „Datenaufbereitung“).
   Erfolg → Schlüssel aus `projektHeader.key` nach `gewerke.heizreport_projekt_key`,
   `heizreport_angelegt_am = jetzt`, Verlauf „Heizreport-Projekt <key> angelegt
   (vorbelegt: <Liste der gesendeten Felder>)“. Die Anlage ist **nicht idempotent**:
   bei Timeout (Status 0) kein zweiter POST, sondern `GET /reports` und Suche in
   allen Gruppen nach `projektName`; Treffer → Schlüssel übernommen, Verlauf „nach
   Timeout gefunden“; kein Treffer → „Anlage unklar – im Heizreport-Portal prüfen,
   dann Schlüssel von Hand eintragen“. Ein zweiter Klick bei bestehender
   Verknüpfung liefert 409 („bereits verknüpft – zuerst die Verknüpfung lösen“).
   Fehlende PLZ des Ausführungsorts → Abbruch „Ausführungsort ohne PLZ“.
2. **Schlüssel von Hand eintragen** (aufklappbar, nur ohne Schlüssel): 9 Buchstaben,
   Prüfung über `GET /reports/{key}` (404 = abgelehnt).
3. **Heizreport öffnen ↗** (`url_heizreport`) – daneben der Schlüssel zum Kopieren;
   ein Deep-Link ins Projekt ist nicht dokumentiert [A-4].
4. **Heizlast abrufen**: `GET /reports/{key}/results` → Gesamtheizlast in W → kW
   (eine Nachkommastelle, kaufmännisch) nach `heizlast_kw`, `heizlast_datum`,
   `heizlast_quelle = "Heizreport API"`, Aufgabe erledigt, Verlauf „Heizlast aus
   Heizreport übernommen: <x,y> kW“; danach Abgleich mit der verkauften
   Leistungsklasse (unten) und Vorbelegung FP-L01/FP-L02 [A-6].
5. **Heizreport-PDF ablegen**: `GET /reports/{key}/pdf?type=heizreport` (erzeugt
   bei Heizreport ein Dokument, kann den Webhook auslösen). Erster Klick direkt; ist
   `heizreport_pdf_am` gesetzt, zuerst die Sicherheitsabfrage „Bei Heizreport wird
   ein weiteres Dokument erzeugt – trotzdem erneut abrufen?“ (ohne Bestätigung
   antwortet der Server mit 409). Der signierte Link (`file.url`, ersatzweise
   `linkToDocument`; nur `https://heizreport.net/…`) wird sofort **ohne Token**
   geladen, nicht gespeichert und als `Heizreport-<PR-Nummer>-<Sparte>-<JJJJMMTT>.pdf`
   (zweites Dokument am selben Tag `…-2.pdf`) im Galerie-Ordner
   `heizreport_pdf_ordner` abgelegt; `heizreport_pdf_am = jetzt`, Verlauf
   „Heizreport-PDF abgelegt“, Aufgabe erledigt.
6. **Verknüpfung lösen** (aufklappbar, Pflichtbegründung): Schlüssel und
   `heizreport_angelegt_am` werden geleert, Verlauf „Heizreport-Verknüpfung gelöst:
   <Begründung> (bisher <key>)“; Heizlast-Felder bleiben. Danach ist „Projekt
   anlegen“ wieder sichtbar.

Ohne Token bleibt die Aufgabe wie bisher: Link ↗ + Ablage/Upload, Heizlast von
Hand in der Akte (Quelle „manuell“).

### Datenaufbereitung (`projektdaten_v2`)

Body `{"projectData": {…}}` (nur diese Hülle, nie zusätzlich `projektData`; nur
skalare Werte; leere Werte weggelassen). Quellen: Kunde des Vorgangs,
Ausführungsort des Projekts, Erfassungsantworten (Frage-IDs des WP-Bogens),
Steckbrief, Parameter `heizreport_kennzahlen`.

| API-Feld | Quelle / Regel |
|---|---|
| `projektName` | `<Nachname>, <Vorname> – <PR-Nummer>` (max. 120 Zeichen) |
| `projektPostleitzahl` | PLZ des Ausführungsorts (Pflicht) |
| `projektBaujahr` | O02, nur 1000–2100 |
| `projektJahresverbrauch` | A03, nur wenn `verbrauch_einheit[A01] = "kWh"` bestätigt ist (l/m3 → weggelassen, keine Umrechnung [A-3]) |
| `projektArtHeizung` | A01 über `art_heizung`, sonst weggelassen |
| `projektAlterHeizung` | A02 über `alter_heizung` (Jahresgrenzen `bis_jahr` → `code`), sonst weggelassen |
| `projektTrinkwasser` | N02 (Ja/Nein) über `trinkwasser`, sonst weggelassen |
| `projektWaermeerzeugerSolarStatus` | `true`, wenn A10 mit „Ja“ beginnt |
| `projektWaermeerzeugerSolarArt` | A10 über `solar_art`, sonst weggelassen |
| `anrede`, `vorname`, `name`, `telefon`, `email` | Kunde, fehlende Felder weggelassen |
| `strasse`, `hausnummer`, `plz`, `ort` | Ausführungsort; Hausnummer = letzter Block aus Ziffer + optionalem Buchstaben/Zusatz (`12`, `12a`, `12-14`), Rest = Straße; nicht trennbar → alles in `strasse` [A-2] |
| `bemerkungen` | `Friondo <PR> · Angebot <AN> · verkauft: <Steckbrief leistungsklasse> · Energieträger alt: <A01>, Baujahr Heizung <A02>, Verbrauch <A03> kWh · Warmwasser über WP: <N02> · Solarthermie: <A10> · Heizlast lt. Erfassung: <A15> kW (nur bei A14 = Ja)` – Teile ohne Wert entfallen |

Bestandsgewerke ohne Erfassung senden nur Kunde, Adresse, Projektname und die
Steckbrief-Bemerkung. `projektBewohner`, Holz-Felder und
`projektKollektorflaecheSolar` werden nicht erfasst (Projektierung ergänzt im
Portal).

### Ergebnisstruktur und Gesamtheizlast

`ResultsResponse` (openapi.json): `project.key`, `results` mit `available`,
`status`, `source`, `calculatedAt`, `warnings`, `header`, `summary`, `vdz`,
`roomHeatLoads`, `heatingSurfaceTemperatureColumns`, `radiators`,
`hydraulicBalance`, `heatpump`, `exchange`, `floorHeatingBalance` sowie die
Kompatibilitätsstruktur `projekt.abgleichFBH[]`. Die openapi.json beschreibt
nur `floorHeatingBalance` vollständig (`groups[].rooms[].heatingLoad` in W,
`setting.value` in l/min, `flowRate` in l/h); `summary`, `header` und
`roomHeatLoads` sind „Detailstrukturen des Rechenkerns“ ohne Feldliste.

Das Tool liest die Gesamtheizlast so: 1. Punktpfad aus `heizreport_pfad_heizlast`
(Vorbelegung `results.summary.heatLoad`), 2. bekannte Kandidaten
(`results.summary.totalHeatLoad`, `…heatingLoad`, `…heizlast`, `…heatLoadTotal`,
`…buildingHeatLoad`, `results.header.heatLoad`, `results.header.heizlast`),
3. ersatzweise die **Summe der Raumheizlasten** aus `results.roomHeatLoads`
(Liste oder Objekt; je Raum der erste numerische Wert unter `heatLoad`,
`heatingLoad`, `heizlast`, `heatLoadTotal`, `total`, `value`), zuletzt
`results.floorHeatingBalance.groups[].rooms[].heatingLoad` [A-5]. Findet sich
nichts, meldet das Tool die vorhandenen Ergebnisschlüssel („Parameter
heizreport_pfad_heizlast prüfen“), das Gewerk bleibt unverändert.

**Der Pfad ist am Referenzprojekt zu bestätigen** (Schlüssel von Andreas): im
Tool „Heizlast abrufen“, Wert mit der Portal-Anzeige vergleichen; weicht er ab,
den richtigen Pfad in Parametrierung → Heizreport → Ergebnis-Pfad eintragen und
hier nachtragen. Je-Raum-Werte werden nicht gespeichert (Stufe 2).

### Abgleich mit der verkauften Leistungsklasse

Dieselbe Zuordnung wie im WP-Konfigurator: Heizlast → Zeile der Paketmatrix
über die Spalte „Heizlast (A15)“ (`bis 5,9 kW` → 4 kW, `6,0 – 7,9` → 6 kW,
`8,0 – 9,9` → 7 kW, `10,0 – 12,9` → 10 kW, `13,0 – 15,9` → 13 kW,
`16,0 – 18,5` → 15 kW; diese Spalte ist die Unterdimensionierungs-Matrix aus
v8). Ergebnis ≠ Steckbrief `leistungsklasse` (Vergleich der kW-Zahl) → Hinweis
am Gewerk (Verlauf, Art `hinweis`; angezeigt an der Aufgabe und im Heizlast-Block
der Akte): „Heizlast <x,y> kW laut Heizreport → Leistungsklasse <K>; verkauft:
<Steckbrief> – Auslegung prüfen (Nachtrag oder Freigabe)“. Keine automatische
Änderung an Angebot, Steckbrief oder Stückliste. Gleiche Klasse → Verlauf
„Heizlast passt zur verkauften Klasse“. Passt keine Zeile (über 18,5 kW) →
Hinweis mit „keine Leistungsklasse der Paketmatrix“.

## 3. Kennzahlen-Verfahren (Phase 123) – Schritt für Schritt für Andreas

Die Kennzahlen `projektArtHeizung` (1–6), `projektAlterHeizung` (1–3),
`projektTrinkwasser` (1–3) und `projektWaermeerzeugerSolarArt` (1–2) sind nicht
öffentlich dokumentiert; ihre Bedeutung wird am Portal abgelesen – nie geraten.
Bis zur Eintragung werden diese Felder nicht gesendet (Klartext in `bemerkungen`).

1. Token in Parametrierung → Heizreport eintragen, „Verbindung testen“.
2. Ein **Testprojekt** benennen: nach ausdrücklicher Freigabe an einem Demo-Gewerk
   „Heizreport-Projekt anlegen“ (braucht eine aktive Jahres- oder Bildungslizenz)
   oder ein vorhandenes Testprojekt aus dem Portal (Schlüssel 9 Buchstaben).
3. Im Tool-Ordner ausführen (ein Feld je Lauf):
   ```
   venv\Scripts\python scripts\heizreport_kennzahlen.py --projekt <key> --feld projektArtHeizung --werte 1,2,3,4,5,6 --ablesen
   venv\Scripts\python scripts\heizreport_kennzahlen.py --projekt <key> --feld projektAlterHeizung --werte 1,2,3 --ablesen
   venv\Scripts\python scripts\heizreport_kennzahlen.py --projekt <key> --feld projektTrinkwasser --werte 1,2,3 --ablesen
   venv\Scripts\python scripts\heizreport_kennzahlen.py --projekt <key> --feld projektWaermeerzeugerSolarArt --werte 1,2 --ablesen
   ```
   Das Skript bestätigt das Projekt (Name), fragt „Dieses Projekt wird bei
   Heizreport GEÄNDERT. Fortfahren?“, setzt dann jeden Wert per
   `PATCH /reports/{key}` mit 600 ms Abstand und hält nach jedem Wert an: „Jetzt
   im Heizreport-Portal die Anzeige des Feldes ablesen und notieren.“ Mit
   `--ablesen` wird der abgelesene Text direkt abgefragt. Am Ende druckt es die
   JSON-Vorlage für den Parameter.
4. Die abgelesenen Bedeutungen den Klartexten des Erfassungsbogens zuordnen und
   als JSON in Parametrierung → Heizreport → Kennzahlen eintragen, z. B.
   `{"art_heizung": {"Gas": 1, "Öl": 2, "Nachtspeicher": null, "Sonstiges": null},
   "verbrauch_einheit": {"Gas": "kWh", "Öl": "l", …}, "alter_heizung":
   [{"bis_jahr": 1995, "code": 1}, {"bis_jahr": 2010, "code": 2}, {"bis_jahr": null,
   "code": 3}], "trinkwasser": {"Ja": 2, "Nein": 1}, "solar_art": {"Ja, soll
   übernommen werden": 1, "Ja, soll stillgelegt werden": 1}}` – `null` = unbekannt.
   `verbrauch_einheit` gibt an, in welcher Einheit Heizreport den Jahresverbrauch
   je Heizungsart erwartet: nur bei `kWh` wird A03 gesendet, bei `l`/`m3` nicht
   (keine Umrechnung ohne bestätigte Heizwerte [A-3]).
5. Die Seite zeigt unter „Kennzahlen“, welche API-Felder derzeit gesendet würden.
   Das Testprojekt danach im Portal bereinigen oder archivieren.

## 4. Stufe 2 (nicht angebunden)

- **Räume per API** (`GET/POST /reports/{key}/rooms`, `PATCH …/rooms/{id}`:
  Etagen-IDs 0–7, Temperatur 7/16–26 °C, Fläche/Höhe): erst, wenn die
  Feinplanung Räume erfasst. U-Werte und Heizflächen bietet die API nicht –
  die Heizlastberechnung bleibt im Portal.
- **Webhook `pdf.generated`** (Adresse und `authenticate`-Wert im Pro-Bereich
  unter Integrationen, Header `X-Heizreport-Event`/`X-Heizreport-Delivery`,
  `eventId` zur Deduplizierung, 2xx bestätigt): braucht eine öffentliche
  HTTPS-Adresse des Tools – dieselbe offene IT-Frage wie die Fern-Signatur.
- **Bilder** (`GET /reports/{key}/pictures`, signierte Links) – kein Abruf.
- **Wärmepumpen-Check** (`GET /reports/{key}/pdf?type=check`, braucht das
  Wärmepumpen-Funktionsrecht) – Angebotsstrang, nicht angebunden.
- **Projektpasswort** (`PUT /reports/{key}/password`) – nicht angebunden.
- Keine öffentlichen Endpunkte zum Löschen von Projekten/Räumen, zum Hochladen
  von Bildern oder zur Token-Verwaltung; Erweiterungen nur nach aktualisierter
  openapi.json.
