# Cloover Partners API – Anbindung (v36, PLAN_V22 Teil B)

Stand: 16.10.2026 (Phase 192, Agent B1). Verbindliche Beschreibung der Schnittstelle: Swagger
`https://partners-api-530331765008.europe-west3.run.app/api-docs/` (OpenAPI 1.0.0 „Cloover Partners API“,
Test-Umgebung). Befund der Kontrollaufrufe vom 15.10.2026: PLAN_V22.md, Abschnitt „Befund Cloover Partners API“.
Der Client ist `app/cloover_api.py` (Vorbild `app/heizreport_api.py`), die Parametrierung
`app/routers/konfiguration_cloover.py` + `app/templates/konfiguration/cloover.html`, die Textbausteine
`app/cloover_texte.py`. Rate/Editor-Karte/PDF (Phase 193) und PDF-Ablage/Projekt/Status (Phase 194) bauen darauf
auf (`app/cloover.py`, `app/cloover_projekt.py`, `app/cloover_pdf_ablage.py`).

## 1. Endpunkte

Authentifizierung: Header `X-API-Key`. Alle Anfragen tragen `userEmail` = das Cloover-Konto, unter dem das
Projekt geführt wird (Test: c.castro@friondo.de). `inflateTransactionFee` ist immer `false` (`true` → HTTP 400
„inflateTransactionFee cannot be set to true for this organization“).

| Endpunkt | Zweck | Eingabe | Antwort | im Tool |
|---|---|---|---|---|
| `POST /api/price-calculator` | Rate aus Gesamtbetrag (v1) | `totalCostOfInstallation` (brutto), `userEmail`, `durationInYears`, `downPayment`, `currency: EUR` | `monthlyPayment` (ungerundet, z. B. 93,3582…), `currency` | Verbindungstest; Rückfall von v2 |
| `POST /api/price-calculator/v2` | Rate aus Anlagen-Positionen (empfohlen) | `userEmail`, `country: Germany`, `projectAssets[]` je `{type, priceInfo{price (NETTO), vatPercentage, subsidy, currency}, capacity}`, `durationInYears` 1–25, `downPayment`, `inflateTransactionFee` | `monthlyPayment`, `monthlyPaymentAfterSubsidies` (gerundet auf Cent), `currency` | `rate_berechnen` |
| `POST /api/projects` | Cloover-Projekt anlegen → persönlicher Abschluss-Link | `userEmail`, `customer{firstName, lastName, email, phone, type: Individual}` (alle Pflicht), `projectAddress{street, city, postalCode, country}`, `projectAssets[]` wie v2, `financingDuration{start, end}` (Jahre), `financingOption[]` aus `Cash | Financing | ClooverPay`, `offerPDF[]` = öffentlich abrufbare URL(s) des Angebots-PDFs (Pflicht), `inflateTransactionFee` | HTTP 201 `{checkout_link, project_id, financial_offer}` | `projekt_anlegen` (Phase 194) |
| `GET /api/projects/{id}` | Status | – | `{id, status, primary_signed_contract, secondary_signed_contract, contract_signed_date, financing_option_chosen}` | `projekt_status` (Phase 194) |
| `POST /api/projects/leads` | Leads an Cloover übergeben | `userEmail`, `leads[]` | – | nicht Teil von v36 |
| `/api/project/create`, `/api/project/leads` | veraltet (307) | – | – | – |

Anlagentypen (`projectAssets[].type`): `Heat pump`, `Solar`, `Battery`, `Wallbox`, `Energetic Renovation`.
Für Klimaanlagen gibt es keinen eigenen Typ – das Tool sendet den Parameter `cloover_kl_typ` (Standard
„Energetic Renovation“, Rückfrage B2).

## 2. Einrichtung

### `.env` (Dev-PC und Server – nie in Code, Doku, Protokoll oder Projektwissen)

```
CLOOVER_API_KEY=            # Test-Key von Cloover (leer = Modul aus)
# CLOOVER_BASIS_URL=https://partners-api-530331765008.europe-west3.run.app   # leer = Test-URL; Live-URL nach Zulieferung
```

Nach dem Eintragen den Dienst `FriondoAngebotstool` neu starten (`scripts\dienst-neustart.bat`); die
Parametrierung zeigt danach „Key gesetzt“. Der Wert wird nirgends angezeigt – auch nicht maskiert – und steht in
keinem Log, Fehlerprotokoll oder Änderungsprotokoll (`cloover_api._maskieren` ersetzt ihn vorsorglich durch `***`).

### Parametrierung → Cloover (`/parametrierung/cloover`, nur Admin – andere Rollen 403)

| Parameter (Tabelle `einstellungen`) | Bedeutung | Standard |
|---|---|---|
| `cloover_modus` | `aus` (keine Raten, keine Projekte) · `test` · `live`; ohne Key immer wirksam „aus“, `live` nur mit Live-URL in der .env (sonst Fehlermeldung beim Speichern, wirksam bleibt `test`) | `test` |
| `cloover_standard_email` | Cloover-Konto (`userEmail`) aller Anfragen, solange der vorbereitende Innendienstler kein eigenes Konto hat | `c.castro@friondo.de` |
| `cloover_laufzeit_jahre` | `durationInYears` der Rate (1–25; je Angebot in der Editor-Karte änderbar) | `20` |
| `cloover_anzahlung_eur` | `downPayment` in Euro (deutsches Format) | `0` |
| `cloover_optionen` | `financingOption[]` des Projekts (Mehrfachauswahl Cash/Financing/ClooverPay, mindestens eine) | `Cash,Financing` [ANNAHME, Rückfrage B3] |
| `cloover_laufzeit_min` / `_max` | `financingDuration{start, end}` des Projekts (1 ≤ von ≤ bis ≤ 25) | `1` / `20` [ANNAHME] |
| `cloover_sparten` | Sparten mit Cloover-Rate/-Projekt (nur Profil Standard); „keine“ wird als `-` gespeichert (leer = Standard) | `WP,PV,KL,WB` |
| `cloover_kl_typ` | Anlagentyp für Klima-Angebote | `Energetic Renovation` [ANNAHME, Rückfrage B2] |
| `cloover_fussnote` | Fußnote der Rate im Angebot (Platzhalter `{endbetrag}`, `{laufzeit}`, `{anzahlung}`, `{foerderung}`, `{stand}`; leer = Standardtext aus `cloover_texte.FUSSNOTE_STANDARD`) | Entwurf (Rückfrage B1) |
| `cloover_datenschutz` | Datenschutzsatz unter dem Cloover-Block (leer = `cloover_texte.DATENSCHUTZ_STANDARD`) | Entwurf (Rückfrage B7) |
| `cloover_letzter_test` | Ergebnis des letzten Verbindungstests (JSON ok/text/zeit) | – |
| `cloover_protokoll` | Änderungsprotokoll der Seite (letzte 30 Zeilen) | – |

Je Benutzer (Benutzerverwaltung → Details, nur Innendienst/Admin): **Cloover-Konto (E-Mail)** =
`benutzer.cloover_email`. `cloover_api.user_email_fuer(session, benutzer)` liefert dieses Konto, sonst das
Standard-Konto [ANNAHME Plan: Projekt läuft unter dem vorbereitenden Innendienstler, sonst Standard].

### Modus test → live

1. Live-URL und Live-Key von Cloover in die `.env` (`CLOOVER_BASIS_URL`, `CLOOVER_API_KEY`), Dienst neu starten.
2. Parametrierung → Cloover: Basis-URL zeigt „Live-URL“, Modus auf `live` stellen, speichern (mit Test-URL wird
   `live` abgewiesen), „Verbindung testen“ – der Text hat dann keinen Zusatz „(Test-Umgebung)“.

## 3. Verhalten des Clients

- **Kein Netz mit offener Datenbanksitzung** (v27-Regel): `rate_berechnen`, `projekt_anlegen`, `projekt_status`
  bekommen keine Session; Aufrufer lesen vorher und geben die Verbindung frei (`db.verbindung_freigeben`).
  `verbindung_testen(session)` liest Parameter, gibt frei und ruft dann das Netz. Der Wächter
  `tests/test_v27_sitzungen.py` erkennt die Aufrufkette über `_roh_anfrage` (urllib).
- **Modus aus = kein Aufruf:** ohne Key (`konfiguriert()` False) oder bei `cloover_modus = aus` wirft jeder
  Aufruf `ClooverFehler` („… Modul aus“), `_roh_anfrage` wird nicht erreicht – einzige Ausnahme ist der
  Verbindungstest (`modus_pruefen=False`, Nachtrag 17.10.2026). Der sitzungslose Client kennt den
  Modus über einen prozessweiten Merker (`modus(session)` setzt ihn; sonst einmal über eine kurze Lesesitzung).
- **HTTP:** `_roh_anfrage(methode, pfad, body)` – urllib, Header `X-API-Key`, `Accept`/`Content-Type:
  application/json`, Timeout 20 s, Rückgabe (Status, JSON-Dict; leerer/ungültiger Body → {} bzw. {"text"}),
  Netzfehler/Timeout → Status 0. In Tests gemockt.
- **Meldungen** (`fehler_meldung`):

| Status | Meldung im Tool |
|---|---|
| 401 | Cloover: API-Key abgelehnt |
| 403 | Cloover: Zugriff verweigert (HTTP 403): `<message>` |
| 422 | Cloover: Eingabe abgelehnt (`<message>`) |
| 429 | Cloover: zu viele Anfragen (HTTP 429) – später erneut versuchen |
| 4xx sonst | Cloover: `<message>` (bzw. „HTTP n“) |
| 0 / 5xx | Cloover nicht erreichbar – später erneut versuchen |

- **Fehlerprotokoll:** jeder Status 0/4xx/5xx → Parametrierung → Fehlerprotokoll, Fehlertyp „Cloover“, Meldung
  `POST /api/price-calculator/v2 → HTTP 422`, Detail = Feldnamen des Bodys (nie Werte, keine Kundendaten) und der
  Fehlertext der Antwort; der Key wird maskiert.
- **Rate** (`rate_berechnen(assets, laufzeit_jahre, anzahlung_cent, user_email, *, brutto_cent=None,
  rueckfall=True)`): v2-Body `{userEmail, country: "Germany", projectAssets, durationInYears, downPayment (EUR,
  2 Stellen), inflateTransactionFee: false}` → `{rate_ohne_cent, rate_mit_cent | None, quelle "v2", antwort,
  laufzeit_jahre, anzahlung_cent}`. Antwortet v2 mit 400/404/405/409/415/422 (Anlagentyp, Eingabe) und ist
  `brutto_cent` (Endbetrag brutto) übergeben, folgt der Rückfall v1 mit `totalCostOfInstallation` → `quelle "v1"`,
  `rate_mit_cent None`, `v2_fehler`. Rundung kaufmännisch auf Cent: 93,3582 → 93,36 € (9336). Laufzeit außerhalb
  1–25 wird vor dem Netz abgewiesen.

## 4. Anlage aus dem Angebot (`assets_fuer(session, angebot)`)

Genau ein Asset je Angebot (Kombi-Versand: eines je Angebot). Beträge ausschließlich aus `Angebot.summen()`:

| Feld | Quelle |
|---|---|
| `type` | WP „Heat pump“, PV „Solar“, WB „Wallbox“, KL `cloover_kl_typ`; GW/MS/WA/DMS und TAIFUN-Einträge → kein Asset |
| `priceInfo.price` | **Netto nach Gesamtrabatt** = `summen()["netto_nach_rabatt"]` (= Endbetrag ÷ (1 + USt-Satz); Positionsrabatte, bauseits/EP/Alternativ sind in den Summen berücksichtigt), EUR mit 2 Stellen |
| `priceInfo.vatPercentage` | USt-Satz des Angebots (19 bzw. 0 bei PV, § 12 Abs. 3 UStG) |
| `priceInfo.subsidy` | WP: Förderbetrag aus `kfw_json` über `pdf_export._kfw_ergebnis_fuer` (ohne Förderblock oder „Förderblock ausgeblendet“ = 0; manuell festgelegte Förderung v6/v8 zählt); PV/KL/WB 0 |
| `priceInfo.currency` | `EUR` |
| `capacity` | WP: kW der Leistungsklasse – (1) Steckbrief des verknüpften Gewerks `leistungsklasse` („7 kW (CS3800i)“), (2) `konfigurator.leistungsklasse` aus den Erfassungs-/Konfigurationsantworten (Paketmatrix), (3) Nennleistung der BAFA-Anlage zur Paket-Position (Blatt „BAFA-Anlagen“, 045–054 / 15+055/056), (4) „Leistungsklasse … kW“ im Protokoll/Auslegungstext; PV: kWp aus `pv_json`; KL: Σ Kühllast kW aus `kl_json`; WB: 11. Ohne Wert entfällt der Schlüssel [ANNAHME] |

Netto-Regel (Befund 15.10.2026): `price` in v2 ist der Nettobetrag, Cloover rechnet die USt selbst dazu
(389,99 ÷ 273,16 × 30.000 = 42.830 € = 35.992,06 × 1,19); `monthlyPaymentAfterSubsidies` behandelt die
Förderung als spätere Sondertilgung. Speicher wird nicht als eigenes `Battery`-Asset gesendet – die Rate hängt
nur vom Preis ab [ANNAHME].

Kontrollwerte (Tests `tests/test_v36_cloover_api.py`):

| Fall | price | vatPercentage | subsidy | capacity |
|---|---|---|---|---|
| WP Endbetrag 42.830,55 € (36.412,23 € netto, 500 € Rabatt), Förderung 16.500,00 € | 35992.06 | 19 | 16500 | 8 (BAFA 047) / 10 (Erfassung 25.000 kWh) / 7 (Steckbrief) |
| PV 20.000,00 € (0 %) | 20000 | 0 | 0 | 11.375 (kWp) |
| PV 20.000,00 € mit 5 % Gesamtrabatt | 19000 | 0 | 0 | – |
| KL 6.518,66 € netto, zwei Räume 1,98 + 2,52 kW | 6518.66 | 19 | 0 | 4.5 |
| WB 2.235,70 € netto | 2235.7 | 19 | 0 | 11 |

Gemockte Antwort der Test-Umgebung für den WP-Fall (15 Jahre): 389,99 € ohne / 242,70 € mit Förderung.

## 5. Verbindungstest (`verbindung_testen(session)`, Knopf „Verbindung testen“)

1. v1-Beispielrate 10.000 € brutto, 2.000 € Anzahlung, 10 Jahre → „Verbindung OK · Beispielrate 93,36 €/Monat
   (Test-Umgebung)“ (Rate aus der Antwort; Zusatz nur bei Test-URL) bzw. „Cloover erreichbar, aber Key abgelehnt
   (HTTP 401)“ bzw. Fehlertext; ohne Key „Cloover: kein API-Key in der .env (CLOOVER_API_KEY) – Modul aus“; bei
   Modus „aus“ läuft der Test seit dem Nachtrag 17.10.2026 ebenfalls (Key gesetzt) und hängt „Modus „aus“ – Raten und
   Projekte bleiben abgeschaltet“ an – so lässt sich der Key prüfen, ohne Raten oder Projekte freizuschalten
   (`_anfrage(modus_pruefen=False)` nur für den Test; der Modus wird nicht umgeschaltet).
2. v2-Probe mit einem Beispiel-Asset je aktiver Sparte (`PROBE_ASSETS`) und Meldung je Typ: „Wärmepumpe: Typ
   Heat pump akzeptiert · … · Klima: Typ Energetic Renovation akzeptiert“ bzw. „… abgelehnt: Eingabe abgelehnt
   (<message>)“.
3. Ergebnis in `cloover_letzter_test` (Text + Zeit) und auf der Seite; der Knopf übernimmt vorher den Formularstand.

## 6. Textbausteine (`app/cloover_texte.py`)

`FUSSNOTE_STANDARD` (Pflichtangaben-Entwurf laut Plan Phase 193 mit Platzhaltern; `fussnote_rendern(session,
endbetrag=, laufzeit=, anzahlung=, stand=, foerderung="")` entfernt ohne Förderung den Halbsatz „‚mit Förderung‘ …“)
und `DATENSCHUTZ_STANDARD` (Plan Phase 194). `text_holen(session, key)` liefert den gespeicherten Text, sonst den
Standard; `text_setzen` speichert (leer oder gleich dem Standard = Standard). Beide Texte sind Entwürfe – der
verbindliche Wortlaut kommt von Cloover (B1) bzw. vom Datenschutzbeauftragten (B7).

## 7. Projekt und Status (Phase 194, `app/cloover_projekt.py`)

Client-Funktionen (B1): `projekt_anlegen(kunde, adresse, assets, laufzeit_von_bis, optionen, pdf_urls,
user_email)` → HTTP 201 `{projekt_id, checkout_link, financial_offer, antwort}` (Kundenfelder/Adresse/Optionen/
PDF-URL werden vor dem Netz geprüft; deutsche und API-Schlüssel der Eingabe-Dicts werden verstanden);
`projekt_status(projekt_id)` → Dict mit den sechs Feldern, unbekannte `status`-Werte roh (Rückfrage B8),
404 → „Cloover: Projekt <id> nicht gefunden (HTTP 404)“.

**Ablauf beim „Versand vorbereiten“** (`POST /angebote/{id}/email`, Hook `cloover_projekt.vor_pdf` VOR dem Druck,
`nach_pdf` danach; Kombi-Versand analog mit `vor_pdf_kombi`/`nach_pdf_kombi`):

1. **Voraussetzungen** – Modus ≠ aus, Sparte in `cloover_sparten`, Profil Standard, nicht „im PDF ausgeblendet“
   (`cloover.relevant`); Kunde Privatperson (`kunden.firma` leer, Anrede ≠ Firma, kein Großkunde [ANNAHME]);
   Vor- und Nachname; E-Mail (gültig); Telefon als E.164 (`leadmanagement.telefon_normalisieren`, ≥ 8 Ziffern);
   Ausführungsort mit Straße/PLZ/Ort (`anschriften.ausfuehrungsort_fuer` – Objekt des Angebots); eine Anlage
   (`cloover_api.assets_fuer`); PDF-Ablage eingerichtet (Abschnitt 8). Fehlt etwas: **kein Projekt, Rate bleibt**,
   Versand-Meldung „Cloover-Link nicht möglich: <Grund>“, rote Hinweise in der Editor-Karte,
   `cloover_json.projekt_fehler`.
2. **Rate aktualisieren** (`cloover.rate_aktualisieren`, Phase 193 – Fehler blockieren das Projekt nicht).
3. **PDF-Fassung A** (ohne Link/QR, weil `cloover_json` noch keinen `checkout_link` hat) drucken und ablegen
   (`cloover_pdf_ablage.ablegen`, Dateiname `AN-C-<Nr>-<Zufall>.pdf` ohne Kundennamen), dann `pruefen` (HEAD ohne
   Anmeldung muss `application/pdf` liefern) – Prüf-Fehler = kein Projekt.
4. **`POST /api/projects`** mit `customer{firstName, lastName, email, phone, type Individual}`, `projectAddress`
   (Ausführungsort, `country Germany`), `projectAssets` (ein Asset je Angebot wie in Abschnitt 4),
   `financingDuration{start: cloover_laufzeit_min, end: cloover_laufzeit_max}`, `financingOption` aus
   `cloover_optionen`, `offerPDF: [URL]`, `userEmail` (Cloover-Konto des vorbereitenden Innendienstlers, sonst
   Standard), `inflateTransactionFee false`. HTTP 201 → `projekt_id`, `checkout_link`, `financial_offer`, `pdf_url`,
   `pdf_ablage`, `projekt_am`, `projekt_von` in `cloover_json`; AngebotsNotiz und Vorgangs-Chat „Cloover-Projekt
   <id> angelegt“. Fehler → kein Link, Meldung, Fehlerprotokoll (Typ „Cloover“, ohne Key), Knopf **„Projekt
   anlegen“** in der Editor-Karte zum Nachholen (`POST /angebote/{id}/cloover/projekt`).
5. **PDF-Fassung B** = das Versand-PDF mit Knopf „Finanzierung abschließen ›“, QR-Code und Kurzlink (B2s
   PDF-Kontext liest `checkout_link`); die abgelegte Datei wird durch Fassung B **ersetzt** (gleiche URL)
   [ANNAHME].

Regeln: ein zweites „Versand vorbereiten“ legt **kein** zweites Projekt an (Projekt-ID vorhanden → nur das PDF
wird neu abgelegt); „Überarbeiten“ (neue Version ohne Projektfelder) legt ein **neues** Projekt an, das alte bleibt
bei Cloover stehen und wird im Verlauf vermerkt (`alt_projekte`, Rückfrage B5). **Kombi-Versand:** EIN Projekt je
Kombi-Mail mit allen Cloover-fähigen Tool-Angeboten als Assets und allen PDF-URLs, derselbe `checkout_link` in allen
PDFs; jedes PDF zeigt seine eigene Rate, zusätzlich die Gesamtrate über alle Assets (eine v2-Anfrage;
`kombi_gesamtrate_cent`, Anzeige „Gesamtrate für alle Angebote dieser Mail: ab … €“) [ANNAHME, Rückfrage B6].
Haben alle relevanten Angebote schon dasselbe Projekt, passiert nichts; sonst entsteht ein neues Projekt für alle.

**Status-Lauf `cloover-status`** (60 min, Start +400 s, aktiv nur mit Key, ≤ 50 Angebote je Lauf): Angebote mit
`projekt_id` im Status Versand vorbereitet/Versendet/Angenommen (nicht überholt/abgelehnt/archiviert), Projekt
jünger als 180 Tage → `GET /api/projects/{id}`; Änderung von `status`, `primary_signed_contract`,
`financing_option_chosen` → `cloover_json` (+ `status_stand`, `vertrag_am` aus `contract_signed_date`) und
AngebotsNotiz „Cloover: <status> · …“. `primary_signed_contract = true` → Badge **„Cloover: Vertrag unterschrieben
(TT.MM.JJJJ)“** in Editor, Angebotsliste (Spalte „Cloover“, Standard ausgeblendet) und Vorgangsakte, Notiz im
Vorgangs-Chat mit „Angebot auf Angenommen setzen?“ (manuell, keine Automatik), Glocke art `cloover` (ohne Mail) an
den vorbereitenden Innendienstler und den AD des Vorgangs; `financing_option_chosen = Cash` → Badge **„Cloover:
Barzahlung gewählt“**. Knopf „Status jetzt abrufen“ (`POST /angebote/{id}/cloover/status`). Statistik: Kachel
„Cloover-Verträge“ (Anzahl + Summe Endbetrag der im Zeitraum unterschriebenen Verträge) [ANNAHME]. Unbekannte
`status`-Werte stehen roh in Karte und Verlauf (Rückfrage B8).

## 8. PDF-Ablage / SharePoint (Phase 194, `app/cloover_pdf_ablage.py`)

Cloover verlangt in `offerPDF` eine **ohne Anmeldung abrufbare URL** des Angebots-PDFs; das Tool läuft nur im VPN.
Parameter `cloover_pdf_ablage` (Parametrierung → Cloover → PDF-Ablage, nur Admin; Partial
`konfiguration/_cloover_ablage.html`, Routen `POST /parametrierung/cloover/ablage` und `…/ablage-test`):

| Anbieter | Weg | Voraussetzung |
|---|---|---|
| `sharepoint` (Standard) | Upload über Graph **als Anwendung** in die Bibliothek `cloover_sharepoint_ordner` (Standard „Cloover-Angebote“) der Site `cloover_sharepoint_site` (`PUT /sites/{site}/drive/root:/<Ordner>/<Name>:/content`, > 4 MB über Upload-Session), danach anonymer Lese-Link `POST …/items/{id}/createLink {type view, scope anonymous, expirationDateTime +180 Tage}` → `webUrl`; Cloover bekommt die Download-URL `…?download=1`; Ersetzen über `PUT /drives/{drive}/items/{id}/content` (bei reiner URL über `/shares/u!<base64url>/driveItem`) | Graph-Modus **anwendung** (Verbindungstest unter „Versand“ grün), App-Berechtigung **`Sites.Selected`** mit Schreibrecht auf genau diese Site, Freigabe „Jeder mit dem Link“ für Mandant und Site – Befehle in `docs/graph-einrichtung.md` Abschnitt 8 |
| `basis_url` | Token-Route `GET /oeffentlich/cloover/<token>.pdf` (`app/routers/oeffentlich.py`, ohne Login – `auth.OFFENE_PFADE`): Token 32 Zeichen (`secrets.token_urlsafe(24)`), Ablauf 180 Tage, Tabelle `cloover_pdf_tokens`, Datei `data/cloover_pdf/<token>.pdf`; unbekannt/abgelaufen → 404, keine Verzeichnisliste; HEAD liefert `application/pdf` | `BASIS_URL` in der `.env` = öffentliche HTTPS-Adresse des Tools (Konzept Erreichbarkeit – nicht Teil von v36) |
| `keine` | – | Rate ja, Projekt nein: „Cloover-Link nicht möglich: PDF-Ablage nicht eingerichtet“ |

`pruefen(url)` = HEAD ohne Anmeldung muss `application/pdf` liefern (Rückfall: GET der ersten Bytes auf „%PDF“ bei
405/403); der Knopf **„Test-PDF ablegen und prüfen“** legt ein fpdf2-PDF ohne Kundendaten ab, prüft HEAD und das
Ersetzen und speichert das Ergebnis in `cloover_ablage_letzter_test`. Alle Netzaufrufe laufen ohne offene
Datenbanksitzung (Konfiguration vorher lesen, `verbindung_freigeben`). Der anonyme Link/Token läuft nach 180 Tagen
ab [ANNAHME] – Rückfrage B4 an Cloover (anderer Upload-Weg? wie lange muss die URL abrufbar bleiben?). Abgelaufene
Token-Dateien räumt der Lauf `cloover-status` einmal täglich (03 Uhr, Karenz 30 Tage).

**Einrichtung SharePoint (Admin mit admin@)** – Kurzfassung, Details in `docs/graph-einrichtung.md` Abschnitt 8:

```powershell
# 1. Site + Bibliothek "Cloover-Angebote" anlegen (SharePoint Admin Center oder PnP)
New-PnPSite -Type TeamSite -Title "Cloover-Angebote" -Alias cloover-angebote
# 2. App-Berechtigung Sites.Selected (Entra: Graph > Anwendungsberechtigungen, Admin-Zustimmung), dann je Site:
Grant-PnPAzureADAppSitePermission -AppId <GRAPH_CLIENT_ID> -DisplayName "Friondo Angebotstool" `
    -Site https://friondo.sharepoint.com/sites/cloover-angebote -Permissions Write
# 3. Freigabe "Jeder mit dem Link" (Mandant + Site), Ablauf anonymer Links >= 180 Tage
Set-SPOTenant -SharingCapability ExternalUserAndGuestSharing -RequireAnonymousLinksExpireInDays 180
Set-SPOSite -Identity https://friondo.sharepoint.com/sites/cloover-angebote -SharingCapability ExternalUserAndGuestSharing
```

Danach im Tool: Anbieter `sharepoint`, Site `friondo.sharepoint.com:/sites/cloover-angebote` (oder Site-ID),
„Test-PDF ablegen und prüfen“.

## 9. Rate im Angebot, Editor-Karte, Mail-Platzhalter (Phase 193, `app/cloover.py`)

- **Relevanz** (`cloover.relevant(session, angebot)`): keine Rate bei Modus `aus`, bei den Profilen Enni/SWD/Sparkasse DU,
  bei Sparten außerhalb `cloover_sparten`, bei `cloover_json.ausgeblendet` und bei externen (TAIFUN-)Einträgen.
  `cloover.voraussetzungen` liefert die roten Hinweise der Karte („E-Mail des Kunden fehlt“, „Telefon fehlt“,
  „Firmenkunde – Cloover nur für Privatkunden“, „Großkunde – …“, „Ausführungsort unvollständig (Straße, PLZ, Ort)“) –
  dieselben Prüfungen gelten für das Projekt (Abschnitt 7).
- **Berechnung** `cloover.rate_aktualisieren(angebot_id, *, erzwingen=False, benutzer_id=None)` – außerhalb der Sitzung:
  `db.kurz(schreibend=False)` lesen (Endbetrag aus `summen()`, Förderung `foerderung_cent`, USt, Laufzeit/Anzahlung,
  `assets_fuer`, `user_email_fuer`) → Sitzung zu → `rate_berechnen` → kurze Schreibsitzung `json_schreiben`. Gerechnet
  wird nur, wenn `stand`/`rate_ohne_cent` fehlen oder Endbetrag/Förderung/USt/Laufzeit/Anzahlung von der **Basis der
  letzten Rate** (`endbetrag_cent`, `foerderung_cent`, `ust_satz`, `rate_laufzeit_jahre`, `rate_anzahlung_cent`)
  abweichen oder `erzwingen` gesetzt ist. Aufrufer: `pdf_export.pdf_fuer_angebot`/`signiertes_pdf_erzeugen` (vor jedem
  nicht eingefrorenen PDF, nach `verbindung_freigeben`; Fehler blockieren das PDF nie), „Versand vorbereiten“/Kombi
  (`cloover_projekt.vor_pdf`), Knopf „Rate neu berechnen“ (`POST /angebote/{id}/cloover/rate`), Speichern von
  Laufzeit/Anzahlung (`POST /angebote/{id}/cloover`). Erfolg: `rate_ohne_cent`, `rate_mit_cent` (nur WP mit Förderbetrag
  > 0 und v2-Antwort), Basisfelder, `stand` „TT.MM.JJJJ HH:MM“, `quelle` v2|v1. Fehler: letzte Rate mit Stand bleibt,
  `fehler` = „Cloover-Rate nicht verfügbar: <Grund>“; nie eine Rate → „Monatsrate auf Anfrage“.
- **Editor-Karte „Finanzierung (Cloover)“** (`templates/angebote/_cloover_karte.html`, `static/cloover_v36.css`,
  Kontext `cloover.editor_kontext`; Innendienst/Admin): Laufzeit 1–25, Anzahlung €, Rate ohne/mit Förderung, Stand/
  Quelle/Basis, Hinweis „veraltet“, Häkchen „Finanzierung im PDF ausblenden“, „Rate neu berechnen“, Block „Cloover-
  Projekt“ (Abschnitt 7); änderbar nur in Entwurf/„Versand vorbereitet“. Außendienst in „Meine Angebote“ lesend.
- **PDF** (`cloover.kontext_fuer_pdf` → `auftrag.cloover`): Karte 2 „ab 242,70 € / Monat*“ + „ohne Förderung ab
  389,99 €“, Box „Planbare Monatsraten – Ihre Rate für dieses Angebot:“, Fußnote aus `cloover_fussnote` (Platzhalter
  {endbetrag} {laufzeit} {anzahlung} {foerderung} {stand}), Knopf + QR (`qrcode`, 22 × 22 mm, Fehlerkorrektur M) +
  Kurzlink nur mit `checkout_link`, Datenschutzsatz `cloover_datenschutz` nur mit Link; Kombi-Gesamtrate als
  zusätzliche Box-Zeile. **fpdf2-Rückfall:** Platzhalter `[CLOOVER]` in den Nachtexten A (Migration
  `angebotsprofile.migriere_cloover_platzhalter`), Rendering in `pdf_export._nachtext_rendern` (QR aus Rechtecken).
- **Mail-Platzhalter** `{cloover_rate}` („ab 389,99 € pro Monat“, Rate ohne Förderung; leer bei nicht relevant/ohne
  Rate), `{cloover_link}` = `checkout_link`, `{cloover_finanzierungsangebot}` = `financial_offer` – in allen Angebots-,
  Sparten-, AD-, Nachfass- und Kombi-Vorlagen (Kombi: eine Zeile je Angebot; Link des Kombi-Projekts). Bestehende
  Vorlagen werden nicht automatisch geändert.
- **Kopie/Version:** Überarbeiten/Duplizieren/Kopieren übernehmen nur `laufzeit_jahre`, `anzahlung_cent`, `ausgeblendet`.
- Tests `tests/test_v36_rate.py` (25). Kontrollwerte: WP 42.830,55 € / Förderung 16.500 € / 15 Jahre → 389,99 € ohne,
  242,70 € mit Förderung (Antwort der Test-Umgebung, in Tests gemockt).

## 10. Rückfragen an Cloover / Andreas (PLAN_V22)

- **B1 (Cloover/PAngV):** verbindlicher Wortlaut für die Rate im Angebot (Pflichtangaben: Sollzins, effektiver
  Jahreszins, Gesamtbetrag, repräsentatives Beispiel) – bis dahin ist `cloover_fussnote` ein Entwurf.
- **B2 (Cloover):** Anlagentyp für Klimaanlagen („Energetic Renovation“ oder eigener Typ?); Bedeutung von
  `capacity` je Typ (kW / kWp / kWh?).
- **B3 (Cloover):** Was ist `ClooverPay`? Welche `financingOption` sollen dem Kunden im Checkout angeboten werden?
- **B4 (Cloover):** anderer Weg für `offerPDF` als eine öffentliche URL (Upload, Base64)? Wie lange muss die URL
  abrufbar bleiben?
- **B5 (Cloover):** Storno/Ersatz eines Projekts bei neuer Angebotsversion; mehrere Projekte je Kunde.
- **B6 (Andreas):** Kombi-Mail = ein Cloover-Projekt für alle Angebote (Vorschlag) oder ein Projekt je Angebot?
- **B7 (Andreas/Datenschutz):** Datenschutzsatz und Partnervereinbarung – mit jedem Versand gehen Name, E-Mail,
  Telefon, Adresse und das Angebot an Cloover.
- **B8 (Cloover):** Liste der `status`-Werte eines Projekts.
- Zusätzlich (B1-Umsetzung): Antwortformat bei 4xx (Feld `message` als Text oder Liste?), Muss `capacity` immer
  gesetzt sein (das Tool lässt den Schlüssel ohne Wert weg)?, Antwort von `POST /api/projects` flach oder unter
  `data` (das Tool liest beides)?

## 11. Tests

`tests/test_v36_cloover_api.py` (24 Tests, HTTP gemockt, Key nur per `mock.patch.object(config,
"CLOOVER_API_KEY", …)`): Body v2 wörtlich, Rundung, v1-Rückfall, Fehlerblöcke, Fehlerprotokoll ohne Key/Kundendaten,
Modus aus/ohne Key ohne Aufrufe, `_roh_anfrage` (Header, Body, Timeout 20 s, HTTPError/URLError), Projekt anlegen/
Status, `assets_fuer` je Sparte, Verbindungstest-Wortlaute und Route, Parametrierungs-Seite (Admin 200 ohne Key-Wert,
Innendienst 403, live ohne Live-URL abgelehnt, Speichern/Validierung/Protokoll), Benutzerfeld, Textbausteine.
