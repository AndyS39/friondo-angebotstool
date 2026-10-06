# Umsetzungsplan Projektierung V5 – Heizreport-Anbindung (API v2) & Pilot-Nebensachen

Voraussetzung: kein anderer Plan in Umsetzung (strangübergreifend geprüft
05.10.2026): v24 (PLAN_V16 Klimakonfigurator, Phasen 113–117) und v25
(PLAN_LEAD_V3, Phasen 118–121) sind committet, gepusht und auf dem Server
(Pull am 05.10.2026). CLAUDE.md (v25) und `projektierung_logik_v1.xlsx` sind
Live-Master im Projektordner `C:\Users\a.scheelen\Tools\Angebotstool`
(Git-Arbeitskopie). ALLE PHASEN DIESES PLANS IN EINEM DURCHLAUF UMSETZEN
(Reihenfolge einhalten, jede Checkbox nach Umsetzung und Test abhaken, am Ende
Gesamtübersicht mit Testergebnissen und offenen Punkten, fachliche Rückfragen
gebündelt). migrate.py idempotent. **Kein git push vor Freigabe.**

CLAUDE-Abschnitt: **„Neu in v26“** (höchste + 1; v25 = Lead-Management V3).
Phasen **122–126** (frei laut Zuordnungstabelle; 118–121 gehören zu
PLAN_LEAD_V3).

Geltungsbereich: Modul Projektierung (`app/projektierung.py`,
`app/heizreport_api.py`, `app/routers/projektierung*.py`, Templates unter
`templates/projektierung/` und `templates/konfiguration/`), die
Benutzerverwaltung (nur Team-Zuordnung) und die Einstiegsseite der
Parametrierung (Neugliederung ohne Funktionsänderung). Angebotstool-Logik,
Lead-Management, monday-Sync und PDF-Erzeugung der Angebote bleiben unberührt.
Projektierung läuft weiter im `freigabe_modus` wie eingestellt (Pilot);
Freischaltung „alle“ ist nicht Teil dieses Plans.

Dieser Plan wurde gegen CLAUDE.md v25 und den Code-Stand vom 05.10.2026
(heizreport_api.py aus Phase 93, Benutzerliste vom 27.09., Parametrierungs-
Übersicht mit KL-Block aus v24) geschrieben. Die Heizreport-Schnittstelle ist
öffentlich dokumentiert (API-Version 2.4.0, siehe Phase 122) – die
Recherche-Annahmen aus docs/heizreport-api.md (Phase 93: `heizreport.de/api/`,
`apiKey` im Body, Aktion `editReportData`) sind damit **überholt**.

## Entscheidungen (Chat Projektierung, 05.10.2026, Andreas)

- **Heizreport wird über die öffentliche Kunden-API v2 angebunden**
  (`https://heizreport.net/api/v2`, Bearer-Token, ein Token je Kunde). Der
  generische v17-Client bleibt als Modus „generisch“ erhalten; Standard ist
  der neue Modus „v2“ mit festen Endpunkten.
- **Die Heizlastberechnung selbst bleibt im Heizreport-Portal.** Die API
  kennt keine U-Werte und Heizkörper; das Tool legt das Projekt vorbelegt an,
  holt Ergebnis und PDF zurück und gleicht die Heizlast mit der verkauften
  Leistungsklasse ab. Räume per API und der Webhook sind **Stufe 2** (Räume:
  erst wenn die Feinplanung Räume erfasst; Webhook: braucht eine öffentliche
  HTTPS-Adresse – dieselbe offene IT-Frage wie die Fern-Signatur).
- **Nichts automatisch, was bei Heizreport Nebenwirkungen hat:** Projekt
  anlegen und PDF erzeugen nur per Klick; die PDF-Erzeugung legt bei
  Heizreport jedes Mal ein neues Dokument an und wird deshalb beim zweiten
  Klick nachgefragt.
- **Kennzahlen (Heizungsart 1–6, Altersklasse 1–3, Trinkwasser 1–3, Solarart
  1–2) sind nicht öffentlich dokumentiert** – auch nicht in der
  openapi.json. Sie werden nicht geraten: Die Zuordnung steht als
  Parameter in der Parametrierung; solange sie leer ist, werden diese Felder
  nicht gesendet, die Klartexte landen stattdessen in `bemerkungen`.
- **Token** nur in der Parametrierung (Admin, maskiert, serverseitig), nie in
  Logs, Fehlerprotokoll, Verlauf, Exporten oder im Projektwissen.
- **Montageteam am Benutzer als Dropdown** statt Chip-Reihe; Regelfall ein
  Team je Montage-Benutzer [ANNAHME A-1 – bei „mehrere“ bleibt die
  Mehrfachzuordnung über „+ weiteres Team“ erhalten, siehe Phase 125].
- **Parametrierung wird neu gegliedert, nicht umgebaut:** fünf Bereiche
  (Allgemein · Angebotstool · Projektierung · Lead-Management · System &
  Protokolle), alle bestehenden Adressen bleiben, kein Formular ändert sein
  Verhalten. Die Inline-Abschnitte der heutigen Übersicht ziehen auf zwei
  eigene Seiten um. Die anderen Stränge bauen bis zum Rollout dieses Plans
  nicht an der Parametrierungs-Übersicht (Absprache Andreas).
- **Erfassungsliste als Vorgangs-Sicht** (ein Eintrag je Vorgang) ist
  Angebotsstrang und liegt bereits in PLAN_V17 – **nicht** Teil dieses Plans.

## Phase 122 – Heizreport-Client v2 & Parametrierung-Seite „Heizreport“

- [x] **Doku ablegen:** `docs/heizreport/` anlegen und von
      `https://heizreport.net/api/v2/` die Dateien `openapi.json`,
      `docs.html`, `postman_collection.json` und `CLAUDE.md` (als
      `heizreport-CLAUDE.md`) herunterladen und einchecken. `docs/heizreport-api.md`
      neu schreiben: Abschnitt 1 „Recherche 29.09.“ als überholt markieren,
      Abschnitt 2 beschreibt den v2-Client (Modus, Parameter, Ablauf,
      Ratenlimit, Grenzen), Abschnitt 3 das Kennzahlen-Verfahren (Phase 123),
      Abschnitt 4 Webhook/Räume als Stufe 2.
- [x] **Modul `app/heizreport_api.py` erweitern** (bestehende Funktionen
      `verbindung_testen`, `projekt_anlegen`, `ergebnis_holen` behalten ihre
      Namen und Rückgabeformen; die generische Mapping-Mechanik bleibt für
      den Modus „generisch“): neuer Parameter `heizreport_modus` =
      `v2` (Standard) | `generisch`. Im Modus v2 gelten fest:
      Basis-URL `https://heizreport.net/api/v2`, `Authorization: Bearer
      <Token>` (Token = bestehender Parameter `heizreport_api_key`),
      `Accept: application/json`, JSON-Bodies mit `Content-Type:
      application/json`, Timeout 20 s; `konfiguriert()` = Token gesetzt.
      Endpunkte v2: `GET /` (Version), `GET /health`, `GET /reports`,
      `POST /reports/with-data`, `GET /reports/{key}`, `PATCH /reports/{key}`,
      `GET /reports/{key}/results`, `GET /reports/{key}/pdf?type=heizreport`.
      Nie `/api/v1`, nie Projekt-Schlüssel erraten, Schlüssel immer aus
      `projektHeader.key` übernehmen.
- [x] **Ratenlimit und Fehler:** alle authentifizierten Aufrufe laufen durch
      eine prozessweite Warteschlange (Lock + Zeitstempel des letzten
      Aufrufs) mit mindestens **600 ms Abstand**; bei HTTP 429 wird
      `Retry-After` (mindestens 1 s) abgewartet und **genau einmal**
      wiederholt. Fehlerantworten `{"status": …, "error": …, "details":
      {"type": …, "field": …}}` werden in die Nutzer-Meldung übernommen
      („Heizreport: <error> (Feld <field>)“). 401 → „Token ungültig oder
      Kunde gesperrt – Token in der Parametrierung prüfen“, 403 → „Lizenz
      oder Berechtigung fehlt (Heizreport-Konto prüfen)“, 404 →
      „Projekt nicht gefunden – gehört einem anderen Konto oder wurde
      gelöscht“, 413/415/422 → Meldung mit Feld, 5xx/Timeout → „Heizreport
      vorübergehend nicht erreichbar – später erneut versuchen“. Jeder
      fehlgeschlagene Aufruf landet im Fehlerprotokoll (v22) **ohne**
      Authorization-Header und ohne Token im Text; die Maskierung wird per
      Test abgesichert.
- [x] **Verbindungstest v2** (Button „Verbindung testen“): 1. `GET /health`
      ohne Token, 2. `GET /` (Version), 3. `GET /reports` mit Token. Meldung
      wörtlich: „Verbindung OK · API-Version <version> · <n> eigene Projekte
      (Gruppen: projekte <a>, leads <b>, api <c>, archiv <d>)“ bzw. bei
      Fehler die Meldung aus dem Fehlerblock oben. Health-OK ohne Token-OK →
      „Heizreport erreichbar, aber Token abgelehnt (HTTP 401)“.
- [x] **Neue Parametrierungs-Seite `/parametrierung/heizreport`** (Admin;
      Template `konfiguration/heizreport.html`, Link aus der Übersicht und
      aus den Projektierung-Einstellungen, in denen der bisherige Block
      „Heizreport-API (Phase 93)“ **entfällt** – die Parameter bleiben
      bestehen): Abschnitt „Zugang“ (Modus-Auswahl, Token-Feld als Passwort
      „gesetzt – leer lassen = unverändert“ + Häkchen „Token entfernen“,
      Button Verbindung testen, Hinweis „Token aus dem Pro-Bereich des
      Heizreport-Kontos; hat alle Rechte auf alle Heizreport-Projekte“);
      Abschnitt „Kennzahlen“ (Phase 123); Abschnitt „Ablage“ (Galerie-Ordner
      für das Heizreport-PDF, Vorbelegung = der Ordner, in den der bisherige
      manuelle Heizlast-Upload der Aufgabe geht – laut Aufgabentext
      „Montagedokumente“ der Sparte WP); Abschnitt „Portal-Link“ (bestehender
      Parameter `url_heizreport`, zieht aus den Projektierung-Einstellungen
      hierher um); aufklappbar „Generischer Client (v17)“ mit den
      bisherigen Feldern, nur relevant im Modus generisch. Speichern
      protokolliert Änderungen wie die übrigen Projektierungs-Parameter
      (ohne Tokenwert).
- [x] **migrate.py:** Parameter `heizreport_modus` (v2), `heizreport_kennzahlen`
      (leer, Phase 123), `heizreport_pdf_ordner` (Vorbelegung s. o.); neue
      Gewerk-Spalten `heizreport_angelegt_am` (datetime), `heizreport_pdf_am`
      (datetime). Zweimal gegen die Server-DB-Kopie: zweiter Lauf ohne
      Änderungen.
- [x] Test `tests/test_heizreport_v26.py`, Teil 1 (HTTP gemockt, kein echter
      Netzzugriff in Tests): Warteschlange hält 600 ms (5 Aufrufe → Abstände
      ≥ 0,6 s mit gemockter Uhr); 429 mit `Retry-After: 1` → eine
      Wiederholung nach ≥ 1 s, dann OK; 429 zweimal → Meldung ohne dritte
      Wiederholung; Verbindungstest-Meldung wörtlich; Fehlerprotokoll-Eintrag
      enthält weder „Bearer“ noch den Tokenwert.

## Phase 123 – Projekt anlegen und vorbelegen (Aufgabe „Heizlastberechnung liegt vor“)

- [x] **Datenaufbereitung `heizreport_api.projektdaten_v2(session, gewerk)
      -> dict`** liefert den Body `{"projectData": {…}}` (nur die Hülle
      `projectData`, nie `projektData` zusätzlich; nur skalare Werte; leere
      Werte weglassen; Body < 64 KiB). Feldbelegung – Quellen wie in der
      Tabelle, Frage-IDs aus dem Blatt „Fragen“ (WP) der
      konfigurator_logik_v5.xlsx, Kundendaten aus dem Kunden des Vorgangs,
      Adresse = Ausführungsort:

      | API-Feld | Quelle | Regel |
      |---|---|---|
      | `projektName` | Kunde + Projekt | `<Nachname>, <Vorname> – <PR-Nummer>` (max. 120 Zeichen) |
      | `projektPostleitzahl` | Ausführungsort | PLZ als Text; fehlt sie → Anlage abbrechen mit Meldung „Ausführungsort ohne PLZ“ |
      | `projektBaujahr` | Erfassung O02 | nur wenn 1000–2100 |
      | `projektJahresverbrauch` | Erfassung A03 | **nur** wenn in `heizreport_kennzahlen` die Einheit je Heizungsart bestätigt ist (s. u.), sonst weglassen |
      | `projektArtHeizung` | Erfassung A01 (Gas / Öl / Nachtspeicher / Sonstiges) | über `heizreport_kennzahlen.art_heizung`, sonst weglassen |
      | `projektAlterHeizung` | Erfassung A02 (Jahr) | über `heizreport_kennzahlen.alter_heizung` (Jahresgrenzen → 1–3), sonst weglassen |
      | `projektTrinkwasser` | Erfassung N02 (WW über WP Ja/Nein) + N03 | über `heizreport_kennzahlen.trinkwasser`, sonst weglassen |
      | `projektWaermeerzeugerSolarStatus` | Erfassung A10 | `true`, wenn A10 mit „Ja“ beginnt, sonst weglassen |
      | `projektWaermeerzeugerSolarArt` | – | nur über Kennzahlen-Parameter, sonst weglassen |
      | `projektBewohner`, Holz-Felder, `projektKollektorflaecheSolar` | – | nicht erfasst → weglassen (Projektierung ergänzt im Portal) |
      | `anrede`, `vorname`, `name`, `telefon`, `email` | Kunde | als Text; fehlende Felder weglassen |
      | `strasse`, `hausnummer`, `plz`, `ort` | Ausführungsort | Straße und Hausnummer trennen: letzter Block aus Ziffer + optionalem Buchstaben/Zusatz (`12`, `12a`, `12-14`) = Hausnummer, Rest = Straße; nicht trennbar → alles in `strasse` [ANNAHME A-2] |
      | `bemerkungen` | Tool | wörtlich: `Friondo <PR-Nummer> · Angebot <AN-Nummer> · verkauft: <Steckbrief leistungsklasse> · Energieträger alt: <A01>, Baujahr Heizung <A02>, Verbrauch <A03> kWh · Warmwasser über WP: <N02> · Solarthermie: <A10> · Heizlast lt. Erfassung: <A15 kW, nur wenn A14 = Ja>` – Teile ohne Wert entfallen |

- [x] **Kennzahlen-Parameter `heizreport_kennzahlen`** (JSON, Parametrierung →
      Heizreport → Abschnitt „Kennzahlen“, Textfeld mit Vorlage und Erklärung):
      `{"art_heizung": {"Gas": null, "Öl": null, "Nachtspeicher": null,
      "Sonstiges": null}, "verbrauch_einheit": {"Gas": null, "Öl": null,
      "Nachtspeicher": null, "Sonstiges": null}, "alter_heizung":
      [{"bis_jahr": null, "code": null}, …], "trinkwasser": {"Ja": null,
      "Nein": null}, "solar_art": {"Ja, soll übernommen werden": null,
      "Ja, soll stillgelegt werden": null}}`. `null` = unbekannt = Feld wird
      nicht gesendet. `verbrauch_einheit` = `kWh` | `l` | `m3`: nur bei
      `kWh` wird A03 unverändert gesendet; bei `l`/`m3` wird A03 **nicht**
      umgerechnet, sondern weggelassen (Klartext steht in `bemerkungen`)
      [ANNAHME A-3 – keine Umrechnung ohne bestätigte Heizwerte]. Die
      Seite zeigt, welche Felder derzeit gesendet würden.
- [x] **Kennzahlen-Ermittlung** `scripts/heizreport_kennzahlen.py` (nur
      manuell, nie im Scheduler): Parameter `--projekt <key>` (ein von Andreas
      benanntes **Testprojekt**, angelegt nach ausdrücklicher Freigabe über
      die Tool-Funktion an einem Demo-Gewerk) und `--feld
      projektArtHeizung --werte 1,2,3,4,5,6` (analog Alter 1–3, Trinkwasser
      1–3, Solarart 1–2); setzt per `PATCH /reports/{key}` jeden Wert
      nacheinander mit 600 ms Abstand, wartet nach jedem Wert auf Enter und
      gibt die Anweisung „Jetzt im Heizreport-Portal die Anzeige des Feldes
      ablesen und notieren“ aus; am Ende druckt es eine JSON-Vorlage für den
      Parameter. Beschreibung des Ablaufs in docs/heizreport-api.md
      Abschnitt 3 (Schritt-für-Schritt für Andreas). Kein Wert wird im Code
      vorbelegt.
- [x] **Aufgabe „Heizlastberechnung liegt vor“** (Paket feinplanung_vot,
      aktion_typ `api`, aktion_wert `heizreport`) im Modus v2 bei
      konfiguriertem Token: Buttons **„Heizreport-Projekt anlegen“** (nur
      solange `heizreport_projekt_key` leer), danach **„Heizreport öffnen ↗“**
      (`url_heizreport`; daneben der Schlüssel zum Kopieren – ein Deep-Link
      ins Projekt ist nicht dokumentiert [ANNAHME A-4]), **„Heizlast
      abrufen“** und **„Heizreport-PDF ablegen“** (Phase 124); ohne Token wie
      bisher Link + Upload. Bei Bestandsgewerken ohne Erfassung werden nur
      Kunde, Adresse und Steckbrief-Werte gesendet. Anlegen: `POST
      /reports/with-data`; Erfolg = HTTP **201** (das JSON-Feld `status`
      kann 200 enthalten – nicht auswerten); Schlüssel aus
      `projektHeader.key` (9 Buchstaben) → `gewerk.heizreport_projekt_key`,
      `heizreport_angelegt_am`, Verlauf „Heizreport-Projekt <key> angelegt
      (vorbelegt: <Liste der gesendeten Felder>)“. **Nicht idempotent:** bei
      Timeout/Status 0 kein zweiter POST, sondern `GET /reports` und Suche in
      den Gruppen nach `projektName`; Treffer → Schlüssel übernehmen und
      Verlauf „nach Timeout gefunden“; kein Treffer → Meldung „Anlage
      unklar – im Heizreport-Portal prüfen, dann Schlüssel von Hand eintragen“
      mit Feld „Schlüssel eintragen“ (9 Buchstaben, Prüfung über
      `GET /reports/{key}` → 404 = abgelehnt).
- [x] **Verknüpfung lösen:** Knopf am Schlüssel (Projektierung/Admin) mit
      Pflichtbegründung → Schlüssel und `heizreport_angelegt_am` leeren,
      Verlauf „Heizreport-Verknüpfung gelöst: <Begründung>“; Heizlast-Felder
      bleiben. Erst danach ist „Projekt anlegen“ wieder sichtbar.
- [x] Test Teil 2: Demo-Gewerk mit Erfassung (O02 1995, A01 Öl, A02 2003,
      A03 25000, A10 Nein, N02 Ja, Kunde Anrede Herr, Vorname Max, Nachname
      Mustermann, Ausführungsort „Musterstraße 12a, 47139 Duisburg“,
      Leistungsklasse „7 kW (CS3800i)“, PR-Nummer PR-260012, Angebot
      AN-C-260099) → Body `projectData` enthält genau: projektName
      „Mustermann, Max – PR-260012“, projektPostleitzahl „47139“,
      projektBaujahr 1995, anrede/vorname/name, strasse „Musterstraße“,
      hausnummer „12a“, plz „47139“, ort „Duisburg“, bemerkungen wörtlich
      „Friondo PR-260012 · Angebot AN-C-260099 · verkauft: 7 kW (CS3800i) ·
      Energieträger alt: Öl, Baujahr Heizung 2003, Verbrauch 25000 kWh ·
      Warmwasser über WP: Ja · Solarthermie: Nein“ – **keine** Kennzahlen-
      Felder und kein `projektJahresverbrauch`, solange der Parameter leer
      ist; mit `art_heizung.Öl = 2` und `verbrauch_einheit.Öl = "kWh"`
      zusätzlich `projektArtHeizung: 2` und `projektJahresverbrauch: 25000`.
      Antwort 201 mit `projektHeader.key = "abcdefghi"` → Schlüssel am
      Gewerk; Timeout + Treffer in `GET /reports` → Schlüssel übernommen;
      zweiter Klick ohne Lösen unmöglich (Button fehlt, POST → 409-Meldung).

## Phase 124 – Heizlast zurückholen, Abgleich, PDF ablegen

- [x] **„Heizlast abrufen“**: `GET /reports/{key}/results` ohne
      Zusatzparameter (keine `flowTemperature`/`spread` – Projektvorgaben
      gelten). Antwort 422 mit `details.type = calculation_unavailable` →
      Meldung wörtlich „Heizreport-Projekt noch nicht berechenbar – Räume
      und Heizflächen im Heizreport-Portal erfassen, dann erneut abrufen“,
      keine Änderung am Gewerk. Erfolg: Gesamtheizlast des Gebäudes in W aus
      `results` lesen und in kW (eine Nachkommastelle, kaufmännisch) nach
      `gewerk.heizlast_kw`, `heizlast_datum = jetzt`, `heizlast_quelle =
      "Heizreport API"`, Aufgabe erledigt, Verlauf „Heizlast aus Heizreport
      übernommen: <x,y> kW“. **Pfad zur Gesamtheizlast:** die openapi.json
      beschreibt `ResultsResponse` nicht vollständig – Claude Code ermittelt
      den Pfad am Referenzprojekt (Schlüssel von Andreas bei der Übergabe),
      legt ihn als Parameter `heizreport_pfad_heizlast` (Punktpfad, Vorbelegung
      = ermittelter Pfad) ab und dokumentiert die Ergebnisstruktur in
      docs/heizreport-api.md; ist keine Gebäude-Gesamtheizlast enthalten,
      Summe der Raumheizlasten in W aus den Raumstrukturen [ANNAHME A-5].
      Je-Raum-Werte werden nicht gespeichert (Stufe 2).
- [x] **Abgleich mit der verkauften Leistungsklasse:** dieselbe Zuordnung
      Heizlast → Leistungsklasse wie im WP-Konfigurator (Paketmatrix,
      Heizlast-Spalte, inkl. Unterdimensionierungs-Matrix) auf die
      Heizreport-Heizlast anwenden und mit dem Steckbrief-Feld
      `leistungsklasse` vergleichen. Abweichung → fachlicher Hinweis am
      Gewerk/Vorgang (wie die bestehenden fachlichen Hinweise), Text
      wörtlich: „Heizlast <x,y> kW laut Heizreport → Leistungsklasse <K>;
      verkauft: <Steckbrief leistungsklasse> – Auslegung prüfen (Nachtrag
      oder Freigabe)“. Keine automatische Änderung an Angebot, Steckbrief
      oder Stückliste. Gleiche Klasse → Verlauf „Heizlast passt zur verkauften
      Klasse“. FP-Erfassung WP: Fragen FP-L01/FP-L02 werden mit kW und
      „Heizreport“ vorbelegt (Badge „aus Heizreport“), solange sie noch nicht
      beantwortet sind [ANNAHME A-6].
- [x] **„Heizreport-PDF ablegen“**: `GET /reports/{key}/pdf?type=heizreport`
      ist **keine folgenlose Leseoperation** (erzeugt bei Heizreport ein
      Dokument, kann den Webhook auslösen). Erster Klick direkt; ist
      `heizreport_pdf_am` gesetzt, zuerst Sicherheitsabfrage „Bei Heizreport
      wird ein weiteres Dokument erzeugt – trotzdem erneut abrufen?“. Antwort
      ist JSON: `file.url` (bzw. `linkToDocument`) **sofort** ohne Token
      herunterladen (signierter, zeitlich begrenzter Link; kein
      Authorization-Header an diesen Host), Datei als
      `Heizreport-<PR-Nummer>-<Sparte>-<JJJJMMTT>.pdf` in den Galerie-Ordner
      aus `heizreport_pdf_ordner` ablegen, `heizreport_pdf_am = jetzt`,
      Verlauf „Heizreport-PDF abgelegt“, Aufgabe erledigt (falls noch offen).
      Der signierte Link wird **nicht** gespeichert. `type=check`
      (Wärmepumpen-Check) wird nicht angebunden (Angebotsstrang, Hinweis in
      docs/heizreport-api.md).
- [x] **Bilder:** kein Abruf (Stufe 2). **Projektpasswort** (`PUT …/password`)
      wird nicht angebunden.
- [x] Test Teil 3: results-Antwort (Mock nach der am Referenzprojekt
      dokumentierten Struktur) mit Gesamtheizlast 9 200 W → `heizlast_kw`
      9,2, Quelle „Heizreport API“, Aufgabe erledigt; verkaufte Klasse
      „7 kW (CS3800i)“ → Hinweis wörtlich mit „→ Leistungsklasse 10 kW“;
      6 500 W bei Klasse 7 kW → kein Hinweis, Verlauf „passt“; 422
      `calculation_unavailable` → Meldung, Gewerk unverändert; PDF-Antwort
      `{"file": {"url": "https://heizreport.net/x.pdf"}}` (Download gemockt)
      → Datei in der Galerie, `heizreport_pdf_am` gesetzt, zweiter Aufruf ohne
      Bestätigung → 409 mit Rückfrage-Text, mit Bestätigung → zweite Datei
      `…-2.pdf`.

## Phase 125 – Nebensachen: Montageteam-Dropdown, Parametrierung neu gegliedert

- [x] **Benutzer → Montageteam als Dropdown** (`templates/benutzer/liste.html`,
      Hauptzeile und „Neuer Benutzer“): statt der Chip-Reihe ein `<select
      name="team_ids">` mit „– kein Team –“ und allen aktiven Teams (Typ
      Montage zuerst, dann Sub, jeweils alphabetisch), sichtbar nur bei Rolle
      Montage (Live-Umschaltung wie bisher). Hat ein Benutzer heute mehrere
      Teams, erscheint je Team ein Dropdown untereinander; Link „+ weiteres
      Team“ fügt ein weiteres Dropdown hinzu, „×“ entfernt eines – so bleibt
      die Mehrfachzuordnung möglich, der Regelfall ist ein Team [A-1].
      Speichern über die bestehende Route (`teams_dabei` bleibt); leere
      Dropdowns werden ignoriert, doppelte Teams dedupliziert. Teams-Seite
      (Spalte Mitglieder) und Go-live-Prüfpunkt „Teams mit Mitgliedern“
      unverändert. Hilfetext unter „Montage“: „Team hier zuordnen – die
      Teams selbst werden unter Parametrierung → Teams angelegt.“
- [x] **Parametrierung – neue Übersicht `/parametrierung`**
      (`konfiguration/uebersicht.html` neu; Route bleibt): Suchfeld oben
      (filtert die Einträge clientseitig nach Titel und Kurztext), darunter
      fünf Bereichskarten mit Einträgen „Titel – Kurztext“ als Links; Admin-
      und Lead-Bedingungen wie heute. Zuordnung:
      **Allgemein:** Benutzer (`/benutzer`) · E-Mail-Vorlagen · Signaturen ·
      monday-Anbindung.
      **Angebotstool:** Angebotstool-Einstellungen (neu, s. u.) ·
      Angebotsprofile · BzA-Ersteller · Logik & Importe (neu, s. u.) ·
      Klima-Logik (KL) · Artikel (`/artikel`).
      **Projektierung:** Projektierung-Einstellungen · Heizreport (Phase 122)
      · Projektierung-Logik · Teams · Subunternehmer · Stücklisten ·
      Bestandsimport · Go-live-Checkliste (mit Badge „<n>/11 grün“).
      **Lead-Management:** Lead-Einstellungen · Lead-Quellen & Kampagnen ·
      Lead-Parser · Lead-Routing · Lead-Vorlagen · Lead-Steuerdatei ·
      Lead-Demo-Daten.
      **System & Protokolle:** Fehlerprotokoll · Kunden-Dubletten ·
      Lösch-Protokoll Angebote (Anker) · Versand-Erkennung (Anker) ·
      Prüflauf Ablehnung (Anker) · Mail-Protokoll Projektierung (Anker) ·
      Button „Parametrierung neu einlesen“ (bestehende POST-Route).
      Jeder Link der heutigen Button-Reihe erscheint **genau einmal**; weitere
      bestehende Einstiege, die hier nicht genannt sind, ordnet Claude Code
      dem passenden Bereich zu und nennt sie in der Gesamtübersicht.
- [x] **Neue Seite `/parametrierung/angebotstool`** („Angebotstool-
      Einstellungen“, Template `konfiguration/angebotstool.html`) nimmt die
      Inline-Abschnitte der alten Übersicht **unverändert** auf:
      Deckungsbeitrags-Ampel (+ je Sparte) · E-Mail-Versand (+ Protokoll
      Versand-Erkennung) · Kombi-Versand · Gewerkeübergreifende Artikel ·
      Fern-Signatur · Abgelehnt-Prozess (+ Gründe, Prüflauf-Protokoll) ·
      Lösch-Protokoll Angebote. Die Formulare behalten `action`, Feldnamen
      und Hidden-Felder; `POST /parametrierung/einstellungen` und
      `/parametrierung/ablehnungsgruende` leiten nach dem Speichern auf die
      Seite zurück, von der sie kamen (Referer, Fallback Übersicht).
- [x] **Neue Seite `/parametrierung/logik`** („Logik & Importe“, Template
      `konfiguration/logik.html`): Quelle/zuletzt eingelesen, Validierungs-
      bericht (Fehler/Hinweise), Button „Parametrierung neu einlesen“,
      Tabellen Eingelesene Logik · Fragen · Angebotsaufbau · KfW-Parameter ·
      PV-Parameter (+ fehlende) · Klimakonfigurator (Import-Buttons,
      KL-Parameter, fehlende) – alles 1:1 aus der alten Übersicht; die
      Kontext-Variablen der Route werden nur umverteilt, keine neue Logik.
- [x] **Projektierung-Einstellungen gegliedert** (gleiche Route, gleiches
      Formular): sticky Abschnitts-Navigation oben (Anker) mit den Karten
      Freigabe & Pilot · Vorlauf-Ampel · Standard-Verantwortliche ·
      Benachrichtigungs-Mails · Storno-Gründe · Galerie · Portal-URLs ·
      UGL/Collin · Outlook-Kalender · Terminbestätigung · Kundenmail BzA;
      ein sticky „Speichern“ unten (wie die Aktionsleiste des Angebots-
      Editors v14); der Heizreport-Block ist nach `/parametrierung/heizreport`
      umgezogen (Hinweis-Link an seiner alten Stelle). Feldnamen und
      POST-Verarbeitung unverändert.
- [x] **Design:** Tokens und Komponenten des Design-Systems (v14, `karte`,
      `knopf`, Status-Badges), keine neuen externen Ressourcen; Übersicht
      funktioniert bei 1366 px und mobil (Karten untereinander).
- [x] Test `tests/test_parametrierung_v26.py`: jeder Link der alten
      Button-Reihe (Liste im Test hart hinterlegt) kommt in der neuen
      Übersicht genau einmal vor; `/parametrierung/angebotstool` und
      `/parametrierung/logik` liefern 200 und enthalten die Überschriften
      „Deckungsbeitrags-Ampel“ bzw. „Eingelesene Logik“; `POST
      /parametrierung/einstellungen` mit `db_ampel_rot_unter` von der
      Angebotstool-Seite speichert und leitet dorthin zurück; Nicht-Admin
      sieht keine Admin-Einträge; ohne Lead-Modul keine Lead-Karte.
      `tests/test_benutzer_teams_v26.py`: Montage-Benutzer mit einem
      Dropdown-Wert → genau eine TeamMitglied-Zeile; zwei Dropdowns →
      zwei; Rolle Innendienst → keine Team-Felder im HTML; Chips kommen im
      HTML nicht mehr vor.

## Phase 126 – Tests, Doku, Übergabe

- [x] Gesamtlauf `pytest tests -q` grün (v25: 641 Tests; neue Tests aus
      122–125 kommen hinzu); `tests/abnahme.py` 93/93; `scripts/voll_crawl.py`
      für admin/innendienst/aussendienst/montage gegen die migrierte
      Server-DB-Kopie ohne Absturz (inkl. der neuen Parametrierungs-Seiten
      und der Heizreport-Seite).
- [x] **Echtlauf-Vorbereitung (ohne Netzaufrufe im Test):** Checkliste für
      Andreas in docs/nach-dem-update-v26.md: 1. Token in Parametrierung →
      Heizreport eintragen, Verbindung testen (Meldung „Verbindung OK …“);
      2. an einem Demo-Gewerk „Heizreport-Projekt anlegen“ (nach Freigabe –
      Projektanlage braucht eine aktive Jahreslizenz); 3. Kennzahlen mit
      `scripts/heizreport_kennzahlen.py` ermitteln und eintragen; 4. am
      Referenzprojekt „Heizlast abrufen“ und Pfad `heizreport_pdf_ordner`/
      `heizreport_pfad_heizlast` prüfen; 5. einmal „Heizreport-PDF ablegen“.
- [x] CLAUDE.md: Abschnitt „Neu in v26 – Heizreport-Anbindung & Pilot-
      Nebensachen (abgestimmt 05.10.2026)“ (Plan: PLAN_PROJ_V5.md, Phasen
      122–126; Modus v2, Parameter, Ablauf an der Aufgabe, Kennzahlen-
      Verfahren, Abgleich, PDF-Ablage, Grenzen/Stufe 2, Team-Dropdown,
      Parametrierungs-Gliederung mit den neuen Seiten), Zuordnungstabelle
      `| v26 | PLAN_PROJ_V5.md | 122–126 |`, Hinweis in „Neu in v17“ beim
      Heizreport-Absatz („seit v26 API v2“), Hinweis in „Rollen & Navigation“
      zur Parametrierungs-Übersicht.
- [x] `docs/projektierung-entscheidungen.md` Abschnitt V5 mit allen
      [ANNAHME]-Stellen A-1 … A-6 und ihrer Auflösung; `docs/nach-dem-update-v26.md`
      mit Team-Hinweisen (Heizreport-Knöpfe an der Heizlast-Aufgabe, neue
      Parametrierungs-Übersicht, Montageteam-Dropdown).
- [x] Gesamtübersicht am Ende: erledigte Phasen, Testergebnisse, Liste der
      beim Bau konkretisierten [ANNAHME]-Stellen, Liste der Parametrierungs-
      Einträge je Bereich, gebündelte Rückfragen. Commit mit sprechender
      Nachricht; **kein push vor Freigabe**.

## Kontrollwerte für die Abnahme

- Verbindungstest mit gültigem Token: „Verbindung OK · API-Version 2.4.0 ·
  <n> eigene Projekte (Gruppen: …)“; ohne Token: Health OK, Token-Meldung
  HTTP 401.
- Demo-Gewerk aus Phase 123 → Body wörtlich wie im Test; nach Anlage
  Schlüssel mit 9 Kleinbuchstaben am Gewerk, Verlaufseintrag mit Feldliste.
- Referenzprojekt (Schlüssel von Andreas): „Heizlast abrufen“ liefert die im
  Portal angezeigte Gebäudeheizlast auf 0,1 kW genau; Hinweis bei
  Klassenabweichung wörtlich; PDF liegt im eingestellten Galerie-Ordner.
- Zwei Aufrufe im Abstand < 600 ms werden serialisiert (Log/Protokoll zeigt
  ≥ 600 ms Abstand).
- Benutzerliste: Montage-Benutzer mit Dropdown; Mitgliederliste der Teams
  stimmt mit den Dropdown-Werten überein.
- Parametrierung: alle 22 Links der bisherigen Button-Reihe plus „Neu
  einlesen“ erreichbar (Crawl), kein Formular verhält sich anders als vor v26.

## Zulieferungen / bewusst offen

- **Token** (Pro-Bereich des Heizreport-Kontos) – Andreas trägt ihn direkt
  in die Parametrierung ein; nicht im Plan, nicht im Projektwissen.
- **Referenzprojekt** (Schlüssel eines fertig berechneten Heizreport-
  Projekts) – Andreas nennt ihn Claude Code bei der Übergabe; nötig für den
  Ergebnis-Pfad (Phase 124) und die Kennzahlen (Phase 123).
- **Kennzahlen-Bedeutungen** (Heizungsart 1–6, Altersklasse 1–3, Trinkwasser
  1–3, Solarart 1–2, Verbrauchseinheit je Heizungsart) – über das Skript oder
  eine Rückfrage an Heizreport; bis dahin werden die Felder nicht gesendet.
- **Lizenz:** Projektanlage per API setzt eine aktive Jahres- oder
  Bildungslizenz voraus; Berechnungen/PDF unterliegen Projekt-, Lizenz- und
  „Umkreis“-Prüfungen von Heizreport – Bedeutung der Umkreisprüfung bei
  Heizreport erfragen.
- **Stufe 2:** Räume aus der Feinplanung per API anlegen (Etagen-IDs 0–7,
  Temperatur 7/16–26 °C), Webhook `pdf.generated` (öffentliche HTTPS-Adresse
  + `authenticate`-Prüfung + `eventId`-Deduplizierung), Bilderliste,
  Wärmepumpen-Check (`type=check`) als Angebotsanhang → Angebotsstrang.
- **[ANNAHME]-Übersicht:** A-1 ein Team je Montage-Benutzer (Mehrfach bleibt
  möglich) · A-2 Trennung Straße/Hausnummer · A-3 keine Verbrauchsumrechnung
  ohne bestätigte Einheit · A-4 kein Deep-Link ins Heizreport-Projekt · A-5
  Gesamtheizlast = Gebäudewert, ersatzweise Summe der Räume · A-6 FP-L01/L02
  aus Heizreport vorbelegen.
- Erfassungsliste als Vorgangs-Sicht → PLAN_V17 (Angebotsstrang).


## Ergebnis der Umsetzung (06.10.2026, Claude Code)

Alle Phasen 122–126 umgesetzt (Heizreport zentral, Montageteam-Dropdown und
Parametrierungs-Gliederung durch zwei parallele Agenten), jede Checkbox nach Umsetzung
und Test abgehakt. Gesamtlauf `pytest tests -q` 681 passed (v25: 641; neu
`tests/test_heizreport_v26.py` 19, `test_parametrierung_v26.py` 13,
`test_benutzer_teams_v26.py` 8), `tests/abnahme.py` 93/93, `migrate.py` zweimal gegen die
Server-DB-Kopie (Lauf 1 legt die Parameter `heizreport_modus`, `heizreport_kennzahlen`,
`heizreport_pdf_ordner`, `heizreport_pfad_heizlast` und die Spalten
`heizreport_angelegt_am`/`heizreport_pdf_am` an, Lauf 2 ohne Änderungen), Voll-Crawl
admin/innendienst/aussendienst/montage gegen die migrierte Kopie: 57.068 Aufrufe, 0 Abstürze (155 GET-Routen inkl. /parametrierung/heizreport, /angebotstool, /logik), Bericht `diagnose/test_v26/crawl_v26_bericht.txt`. HTTP in
allen Tests gemockt – kein Heizreport-Projekt angelegt, kein PDF erzeugt, kein
Netzaufruf. Angepasste Alt-Tests: `test_projektierung_v4.py::Phase93Heizreport`
(Modus generisch, neue Testroute), `test_kl_v24.py`/`test_kl_v24_logik.py` (Inhalte der
alten Übersicht liegen auf /parametrierung/logik bzw. /angebotstool, KL-Import kehrt nach
Logik & Importe zurück). [ANNAHME]-Stellen A-1 … A-6 in
`docs/projektierung-entscheidungen.md` Abschnitt PLAN_PROJ_V5. Nicht erfüllbar im Bau:
Referenzprojekt-Schlüssel („<HIER EINSETZEN>“) und Token lagen nicht vor – Ergebnis-Pfad
`heizreport_pfad_heizlast` (Vorbelegung `results.summary.heatLoad`) und Kennzahlen sind
nach der Echtlauf-Checkliste in docs/nach-dem-update-v26.md zu bestätigen. Kein git push
vor Freigabe.
