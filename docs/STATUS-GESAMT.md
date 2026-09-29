# Status gesamt – Friondo Angebotstool

Stand: 29.09.2026, abends · reine Bestandsaufnahme (keine Code-Änderung) ·
Datenbasis: Repository `master` (lokal), `origin/master` (GitHub) und die
Server-DB-Kopie in `diagnose\` (Stand 29.09.2026 15:32).

**Kurzfassung**

- Auf GitHub liegt der Hotfix `7408bb4` (Vorgangsakte). Ob der Server ihn
  schon per `update.bat` gezogen hat, ist **noch nicht bestätigt**.
- Lokal liegen **11 Commits** darüber (v16 PV-Konfigurator, v17
  Projektierung V4), ungepusht.
- Ein Probelauf dieser 11 Commits gegen eine Kopie der Server-DB war sauber:
  Migration zweimal fehlerfrei, 43.372 Seitenaufrufe ohne Absturz.
- Drei Pläne sind **geschrieben, aber nicht begonnen** (und nicht eingecheckt):
  PLAN_PROJ_V3 (Go-live Projektierung), PLAN_V14 (BzA-Datenblatt/BAFA) und
  PLAN_LEAD_V1.1.
- Zwei Pläne haben **Phasennummern, die mit anderen Plänen kollidieren**
  (siehe 1.3).
- Die meisten Zulieferungen aus PLAN_V11 (Klassengrenzen, VK-Preisliste,
  CS8800-Broschüre, TAIFUN-Muster) sind weiter offen.

---

## 1. Plan-Dateien und Checkbox-Stand

„erledigt“ = alle Checkboxen `[x]`; „übersprungen“ kommt in keinem Plan vor
(keine `[-]`/`[~]`-Markierungen). Zählung automatisch über alle Checkbox-Zeilen.

### 1.1 Angebotstool-Strang (Konfigurator, Angebot, PV)

| Plan | Inhalt | Stand | offene Punkte |
|---|---|---|---|
| PLAN.md | Grundaufbau v1 | 41/45 | Phase 9 monday-Rückschreiben (Ziel-Board klären, API-Token), tägliches Backup, `docs/anleitung.md` – alle durch spätere Pläne überholt bzw. anders gelöst |
| PLAN_V2.md | Zwei-Stufen-Prozess | 35/36 | Mobilzugriff Variante A (WireGuard) – Entscheidung Nutzer/IT |
| PLAN_V3 – V5 | Regeln, Profile, E-Signatur, Mail | alle erledigt | – |
| PLAN_V6.md | | 28/29 | Checkbox „git push + update.bat“ nie abgehakt (Rollout ist laut Server-DB erfolgt) |
| PLAN_V7 – V10 | TAIFUN-Weg, Mammut, Profile, Vorgänge | alle erledigt | – |
| PLAN_V11.md (→ CLAUDE v13) | Team-Feedback | 30/32 | Ph. 65: **monoenergetische Klassengrenzen** (Zulieferung 1); Ph. 67: **VK-Preisliste importieren** (Zulieferung 2) |
| PLAN_V12.md (→ v14) | Design-Update, Phasen 69–74 | 29/29 erledigt | – |
| PLAN_V13.md (→ v16) | PV-Konfigurator, Phasen 75–81 | 32/33 | Ph. 81: „git push → Rollout per update.bat“ (**lokal, nicht ausgerollt**) |
| **PLAN_V14.md** (untracked) | BzA-Datenblatt (KfW-Portal) & BAFA-Anlagennummern, Phasen 82–84 | **0/13 – nicht begonnen** | Ph. 82 BAFA-Stammdaten (0/4), Ph. 83 BzA-Datenblatt-PDF am Angebot (0/4), Ph. 84 Abnahme & Rollout (0/5). Voraussetzung laut Plan: „vorheriger Plan abgeschlossen **und ausgerollt**“ → V13 muss erst live |

Hinweis zur Frage „PLAN_V13/V14 noch nicht gestartet“: **PLAN_V13 ist
umgesetzt** (lokal, nur der Rollout fehlt). **Nicht begonnen ist PLAN_V14.**

### 1.2 Lead-Management

| Plan | Inhalt | Stand |
|---|---|---|
| PLAN_LEAD_V1.md | Fundament & Terminassistent, Phasen 73–82 | 73/73 erledigt (live, im Demo-Modus) |
| **PLAN_LEAD_V1.1.md** (untracked) | Übersicht, Anrufliste neu, Verknüpfung Quelle·Kampagne·Kanal, Phasen 87–89 | **0/28 – nicht begonnen** (87: 0/7, 88: 0/11, 89: 0/10) |

### 1.3 Projektierung

| Plan | Inhalt | Stand |
|---|---|---|
| PLAN_PROJ_V1.md | Fundament (v11) | 47/47 erledigt |
| PLAN_PROJ_V1b.md | Oberfläche nach Prototyp, Phase 73 | 28/28 erledigt |
| PLAN_PROJ_V2.md (→ v15) | Phasen 74–83 | 53/54 – Ph. 83 „Rollout nach Absprache“ nicht abgehakt (Rollout laut Server-DB erfolgt) |
| **PLAN_PROJ_V3_GOLIVE.md** (untracked) | Phasen 84–86 + organisatorische Checkliste | **0/40 – nicht begonnen**: Ph. 84 TAIFUN-Auftragsdaten 0/6, Ph. 85 Bestandsimport 0/6, Ph. 86 Go-live-Hilfen 0/4, Checkliste Stufe 0–3 0/24 |
| PLAN_PROJ_V4.md (→ v17) | Phasen 90–93 | 47/47 erledigt (**lokal, nicht ausgerollt**). Wurde gebaut, obwohl V3 fehlt – Berührungspunkte in `docs/projektierung-entscheidungen.md` |

**Phasennummern-Kollisionen** (fachlich harmlos, aber verwirrend in
Commits, Doku und Rückfragen):

| Nummern | kommen vor in |
|---|---|
| 73–82 | PLAN_LEAD_V1 **und** PLAN_PROJ_V1b (73) / PLAN_PROJ_V2 (74–83) / PLAN_V12 (73–74) / PLAN_V13 (75–81) |
| **82–84** | **PLAN_V14 (neu)** kollidiert mit PLAN_PROJ_V2 (82–83) und PLAN_PROJ_V3 (84) |
| 84–86 | PLAN_PROJ_V3 |

Empfehlung: PLAN_V14 vor dem Start auf freie Nummern umstellen
(z. B. 94–96), PLAN_PROJ_V3 und PLAN_LEAD_V1.1 behalten ihre Nummern.

---

## 2. Server vs. lokal

**Server:** Welcher Commit dort gerade läuft, lässt sich nur über die Daten
erschließen. In der DB-Kopie sind alle Migrationsmerker bis
`migration_abweichung_abnahme` und `migration_v1_restlos` gesetzt; die kommen
aus `5328a2a` bzw. `b30da73` (27.09.). Nachfolgende Commits bis `4fac277`
ändern kein Schema. → **Der Server lief beim Kopieren auf dem Stand zwischen
`b30da73` und `4fac277`** (letzter Rollout am 27.09.).

**GitHub (`origin/master`):** `7408bb4` – Hotfix Vorgangsakte, gepusht am
29.09. Ob `update.bat` auf dem Server danach gelaufen ist: **offen**.

**Lokal über `origin/master` hinaus (11 Commits, ungepusht):**

```
9d0367f 2026-09-29 Projektierung V4 Phase 93: Heizreport-API, UGL formatgenau, Stuecklisten-Pflege, v17
d17eea4 2026-09-29 PLAN_PROJ_V4 Phase 92: BzA erfassen, Kundenmail BzA, KfW-Felder
f1438fa 2026-09-29 PLAN_PROJ_V4 Phase 91: Pakete umgebaut, Fit for Future Ja/Nein, FP-Fragen, Sub-Mails mit Restoel/Stemm/Erdarbeiten
61aaf98 2026-09-29 PLAN_PROJ_V4 Phase 90: Kanban zweigeteilt, Abnahme/Freigabe getrennt, Vorlauf-Ampel, 15-Min-Takt, Aktionen ohne Seitensprung
48f8be9 2026-09-29 PLAN_V13 Phase 81: Abnahme (145 Unit-Tests, 93/93 Abnahmepunkte), CLAUDE.md v16, Team-Anleitung
7b0a6d9 2026-09-29 PLAN_V13 Phase 80: Lieferschein-PDF ohne Preise fuer angenommene Angebote
d2ca8d0 2026-09-29 PLAN_V13 Phase 79: Prozessintegration PV (Ampel-Weg, Erneut pruefen, Anhaenge)
4699841 2026-09-29 PLAN_V13 Phase 78: PV-PDF nach Muster, Beispielrechnung, DB-Schwellen je Sparte
1b5eccd 2026-09-29 PLAN_V13 Phase 77: Positionslogik PV (UK, Montage, Tigo, Geruest, Elektro-Kette, Fit for Future)
73e0a69 2026-09-29 PLAN_V13 Phase 76: Auslegungsmodul pv_auslegung (Module, kWp, Strings, WR/Speicher, Ampel)
b683d99 2026-09-29 PLAN_V13 Phase 75: USt je Angebot, PV-Artikelimport, PV-Logikblaetter, Bogen-Umbau
```

Letzte Commits auf GitHub (zum Einordnen):

```
7408bb4 2026-09-29 Hotfix: Vorgangsakte mit Wiedervorlage warf Internal Server Error
4fac277 2026-09-27 CEO-Review 27.09.2026: Kontrolldurchgang gesamter Prozess (Besprechungsgrundlage)
f127898 2026-09-27 Bugfix: Sparten-Badges waren unsichtbar (CSS-Kollision .chip)
16ee8cf 2026-09-27 Bugfix: Montage-Login strandete auf dem Portal (Demo-Modus sperrte /montage)
292c15a 2026-09-27 Team-Zuweisung repariert + Benutzer-Seite entruempelt
b30da73 2026-09-27 Galerie je Sparte, Foto-Sammelbox, V1 restlos raus, Demo-Projekte
```

**Nicht eingecheckt** im Projektordner: PLAN_PROJ_V3_GOLIVE.md, PLAN_V14.md,
PLAN_LEAD_V1.1.md, docs/leadmanagement-prototyp.html; geändert:
PROJEKTIERUNG-KONZEPT.md; lokal von Git ausgeschlossen: `diagnose/`.

---

## 3. CLAUDE.md-Abgleich (Kopf „v17“)

Die Abschnitte v3, v6–v10, v13, v14 und v16 stimmen mit dem Code überein
(Stichproben). Befunde:

**Fehler (sachlich falsch)**

| Stelle | Befund |
|---|---|
| Zentrale Dateien | `Angebotserstellung_Tool_mit_EK.xlsx` heißt tatsächlich `Artikel-Preislisten/Angebotserstellung Tool mit EK.xlsx`; `foerderrechner-website.html` existiert im Projekt nicht; „15 AMPEL-Gründe“ – im Blatt Aktionen (v5) sind es 14 (v9-Abschnitt sagt selbst „Noch 14“) |
| v12 Lead-Management | Routen falsch: Modul liegt unter `/lead-management` (`app/routers/leadmanagement.py:22`), `/leads` ist die Leads-VOT-Liste; `/api/leads` ist per API-Key geschützt, nicht Admin-gesperrt |
| v17 | `erdleitung_m` stammt aus **Pos. 102** / Erfassung A05, nicht aus Pos. 139/140 (Text wurde wörtlich aus PLAN_PROJ_V4 übernommen; die Abweichung ist in `projektierung-entscheidungen.md` begründet, CLAUDE.md aber nicht angepasst) |

**Überholt, aber nicht als überholt markiert**

- Rollenliste im Kopf nennt nur Admin/ID/AD – es fehlen Projektierung,
  Montage, Leadmanagement.
- „Konfigurator-Typ (aktuell WP)“ – PV setzt ihn inzwischen.
- Kanban-Phasen stehen dreimal verschieden in der Datei (v11, v15, v17);
  gültig ist nur v17 (`abnahme` / `freigabe` getrennt).
- v15: Paket „Abnahme & Freigabe“ und die Galerie-Ordnerliste (jetzt
  Galerie je Sparte + Ordner „Förderung“).
- v11-Roadmap („V3 Montage-Formulare + Collin, V4 Rechnungen/OP/Mahnwesen“):
  Formulare/Collin kamen mit V2; „Projektierung V4“ bezeichnet heute etwas
  anderes; Rechnungen/OP/Mahnwesen sind nicht gebaut.

**Fehlt in CLAUDE.md (im Code vorhanden)**

- Stand 27.09.: Galerie je Sparte + Foto-Sammelbox, Demo-Projekte
  (`scripts/demo_projekte.py`), Team-Zuweisung/Benutzer-Seite, Montage-Login
  im Demo-Modus, Wegfall Paket „Förderung“ (BnD in Abnahme), CEO-Review.
- Hotfix 29.09. (`7408bb4`).
- Plan-Bezug fehlt bei v11, v12, v15, v17.

**Doppelt/verwirrend**

- Zwei Zählungen nebeneinander: Plan-Nummer ≠ CLAUDE-Version
  (PLAN_V11 → v13, PLAN_V12 → v14, PLAN_V13 → v16); `nach-dem-update-v13.md`
  beschreibt PV (= v16), nicht v13.
- „Go-live-Prüfpunkte“ (v17, Stücklisten) ≠ Go-live-Checkliste aus PLAN_PROJ_V3.

→ Empfehlung: CLAUDE.md in einem eigenen Doku-Commit bereinigen (Fehler
korrigieren, „überholt durch vX“-Vermerke, Zuordnungstabelle Plan ↔ Version).

---

## 4. Bug-Status

### 4.1 /vorgaenge/169 – Internal Server Error (BEHOBEN, Server-Update offen)

Reproduziert gegen die DB-Kopie mit dem Live-Code (`4fac277`):

```
app\routers\vorgaenge.py, line 235, in akte
    return render(request, "vorgaenge/akte.html", ...)
app\templates\vorgaenge\akte.html, line 24, in block 'inhalt'
    {{ wiedervorlage_chip(vorgang.wiedervorlage_am, heute) }}
app\templates\_komponenten.html, line 62, in template
    <span class="wv-chip {{ 'faellig' if datum.date() <= heute else 'geplant' }}">
TypeError: can't compare datetime.datetime to datetime.date
```

- **Ursache:** Das Makro verglich einen Tag (`date`) mit `heute`; die
  Vorgangsakte übergibt `heute = datetime.now()`. Eingeführt am 25.09. mit
  PLAN_V12 Phase 71 (`25a85d2`), live seit dem Rollout am 27.09.
- **Betroffen:** alle Vorgangsakten mit gesetzter Wiedervorlage – auf dem
  Server **21 Vorgänge**. Der Crawl zählte 42 Abstürze, weil jede dieser
  21 Akten mit zwei Rollen aufgerufen wurde (Admin, Innendienst). Die
  frühere Angabe „42 Vorgangsakten“ war zu hoch.
- **Keine Migrationsursache:** Schema und Datenmigrationen der Server-DB
  sind für den Live-Code vollständig (Tabellen/Spalten-Abgleich, `migrate.py`
  zweimal „keine Änderungen nötig“).
- **Fix:** `7408bb4` (Makro vergleicht nur den Tag; Regressionstest
  `tests/test_wiedervorlage_chip.py`), auf GitHub. **Offen:** `update.bat`
  auf dem Server + Kontrolle von Vorgang 169.
- **Gesamtsuche:** Alle GET-Seiten mit allen IDs der Server-Kopie für vier
  Rollen (Admin, Innendienst, Außendienst, Montage): vor dem Fix eine einzige
  Ursache, mit Fix 0 Abstürze (43.332 Aufrufe).

### 4.2 Weitere bekannte Punkte

| Punkt | Art | Stand |
|---|---|---|
| Lokaler 404 „BzA erfassen“ (29.09.) | kein Code-Fehler: lokaler Server lief ohne Reload seit vor Phase 92 | behoben durch Neustart |
| Abnahmeskript gegen Server-Daten: 91/93 | Testschwäche: erwartet Benutzer 1 = „Admin“ und den Standard-Mailtext; auf dem Server anders | mit Entwicklungs-DB 93/93; Skript bei Gelegenheit datenunabhängig machen |
| „Formular folgt (Phase 82)“ an Formular-Aufgaben außer Feinplanung | veralteter Hinweis (`app/templates/projektierung/_aufgabe.html:179`); die Montage-Formulare existieren, die Verknüpfung weiterer Formular-Aktionen fehlt | offen |
| Doku-Widerspruch UGL-Zeichensatz | `projektierung-entscheidungen.md:366` nennt latin-1, Code/Doku ab Z. 678 cp850 | Doku-Korrektur offen |

Weitere Abstürze wurden weder im Live- noch im lokalen Stand gefunden.

---

## 5. Provisorien im Code

| # | Provisorium | Ort | Ablöse-Voraussetzung |
|---|---|---|---|
| 1 | Go-live-Prüfpunkte (≥ 90 % Stücklisten, „Testdatei von Collin bestätigt“) auf der Stücklisten-Seite | `app/templates/konfiguration/stuecklisten.html:19-38`, `app/routers/konfiguration.py:948-959` | PLAN_PROJ_V3 Phase 86 (Go-live-Checkliste) bauen, Prüfpunkte dorthin |
| 2 | BzA-Aufgabe bei TAIFUN-Aufträgen: Status „unbekannt“ → Buttons **und** „entfällt“ | `app/bza.py:38-46`, `app/templates/projektierung/_aufgabe.html:104-137` | PLAN_PROJ_V3 Phase 84 (Auftragsdaten mit „gefördert“) |
| 3 | Steckbrief Stemmarbeiten/Erdleitung bei TAIFUN-Aufträgen nur per Hand | `docs/projektierung-entscheidungen.md:614-617` | PLAN_PROJ_V3 Phase 84 |
| 4 | TAIFUN-PDF-Upload am externen Eintrag (Kombi-Mail) | `app/routers/angebote.py:1228-1233`, `app/templates/angebote/extern.html:106-107` | alle Angebote im Tool erstellen |
| 5 | Ohne Graph: „PDF anzeigen und manuell versenden“ | `app/routers/angebote.py:843-848` | Graph-Einrichtung (`docs/graph-einrichtung.md`) |
| 6 | Heizlast-/Auslegungszeile mit vorläufigem Wortlaut | `app/angebot_aufbau.py:283-284`, `app/konfigurator.py:394` | TAIFUN-Muster (Zulieferung 4) |
| 7 | IDS-Connect-Schalter `ugl_ids_aktiv` ohne Funktion | `app/ugl.py:13-14` | Entscheidung + IDS-Zugang von Collin |
| 8 | UGL-Zeichensatz cp850 (Annahme) | `app/ugl.py:21` | Test mit Collin |
| 9 | UGL-Dateiname `PR-….ugl` statt Spezifikation `A<JJJMMTT>.<nnn>` | `app/ugl.py:207, 232` | Collin-Bestätigung |
| 10 | Stücklisten mit BEISPIEL-Artikelnummern | `projektierung_logik_v1.xlsx` (Blatt Stücklisten) | echte Collin-Artikelnummern |
| 11 | Stücklisten-Master in der git-verfolgten Excel (Speichern blockiert `update.bat`) | `app/stuecklisten.py`, `docs/projektierung-entscheidungen.md:703-710` | Stücklisten in DB-Tabelle umziehen |
| 12 | Heizreport: Link + Upload statt API, Webhooks nicht angebunden | `app/heizreport_api.py:1-26` | API-Doku + Schlüssel vom Support |
| 13 | Projektierung im Demo-Modus (`freigabe_modus = admin`) | `app/projektierung.py:96-114` | Freigabe → „alle“ |
| 14 | BzA-Mail im Demo nur an `projekt_testadresse` | `app/bza.py:143-144` | Pilot-Sendesperre (PLAN_PROJ_V3) bzw. Freigabe |
| 15 | Lead-Management im Demo (`lead_freigabe_modus = admin`) | `app/leadmanagement.py:20, 83-99` | Freigabe → „alle“ |
| 16 | Lead-Mails `mail_modus = protokoll`, Kalender nur Testpostfach | `app/lead_mail.py:308-320`, `app/kalender.py:2-4` | Freigabe, dann `mail_modus = live`, `kalender_sync` |
| 17 | PV-Dachbelegung über Interim-Felder | `pv_auslegung.dachbelegung_setzen` | Dachbelegungstool |
| 18 | Montage-Formulare (49 Felder) als Entwurf, FP-Fragen als Startfragen | Blatt „Formulare“ / „Fragen FP-WP“ | Abnahme durch Andreas / TAIFUN-Feinplanungsformular |
| 19 | Bestandsimport nur als dokumentierte Phasenwerte | `docs/projektierung.md` (V4-Abschnitt) | PLAN_PROJ_V3 Phase 85 |

---

## 6. Wartet auf Nutzer (Zulieferungen & Entscheidungen)

Nur Punkte, deren Erledigung im Repo **nicht** nachweisbar ist.

**Angebot / Konfigurator (WP)**

| Zulieferung | Quelle | blockiert |
|---|---|---|
| 1 Monoenergetische Klassengrenzen | PLAN_V11.md:105 | Paketmatrix, Kontroll-Szenarien |
| 2 VK-Preisliste (TAIFUN-Export) | PLAN_V11.md:145 | Preisimport, Wechsel Z25 → Pos. 124 |
| 3 Broschüre „Bosch CS8800iAW.pdf“ | PLAN_V11.md:140-144 | Anhang Pos. 030/031 (bis dahin Warnung „Datei fehlt“) |
| 4 TAIFUN-Muster (Auslegungszeile, Pos.-124-Text) | PLAN_V11.md:21-23 | endgültiger Wortlaut |
| Weiße 8800er: eigene BAFA-Nummer? | PLAN_V14.md:43-46 | BzA-Datenblatt V14 |
| Hybrox-21-Bausteine (Komponenten, Preise, Klassen) | PLAN_V14.md:48-49, 139-148 | Klassenerweiterung |
| Rabattstufen: ab wann persönliche Freigabe? | docs/ceo-review-2026-09.md:320 | Rabatt-Logik |

**PV**

| Zulieferung | Quelle | blockiert |
|---|---|---|
| Dachbelegungstool | PLAN_V13.md:14-17 | Interim-Felder ablösen |
| Sigenergy-/Modul-Datenblatt (anlagen/) | nach-dem-update-v13.md:74 | Anhangsregel „Sparte = PV“ |
| DB-Ampel-Schwellen PV | nach-dem-update-v13.md:61-62 | bis dahin WP-Werte |
| Fachliche PV-Rückfragen (Gateway/Zählerzusammenlegung, EV-Quote, PA04, 4-Feld, Set je String, Mailtext) | nur im Abschlussbericht vom 29.09., **nicht im Repo dokumentiert** | Feinschliff PV – sollte in `nach-dem-update-v13.md` nachgetragen werden |
| PV-Regeln im Steckbrief | projektierung-entscheidungen.md:244-248 | PV-Steckbrief |

**Lead-Management**

| Zulieferung | Quelle | blockiert |
|---|---|---|
| Postfach leads@, Testpostfach, „Senden als“, `Calendars.ReadWrite` | PLAN_LEAD_V1.md:654-657 | Mail-Eingang, Kalender, mail_modus live |
| openrouteservice-API-Key | PLAN_LEAD_V1.md:658-659 | Fahrzeiten |
| Agentur: Formular-Standard | PLAN_LEAD_V1.md:660-662 | Landingpage-Leads |
| Excel-Feinschliff, Kerngebiets-PLZ, AD-Profile | PLAN_LEAD_V1.md:663-667 | Score, Assistent |
| Konzeptfragen §17 (Volumen, Telefonanlage, Blinno, HTTPS-Route) | LEADMANAGEMENT-KONZEPT.md:608-620 | PLAN_LEAD_V2 |
| Freigabe Demo → „alle“ | PLAN_LEAD_V1.md:674-679 | Go-live Lead |

**Projektierung**

| Zulieferung | Quelle | blockiert |
|---|---|---|
| Annahmen 1–8 aus PLAN_PROJ_V4 bestätigen (u. a. „Montageteam zuweisen“ Pflicht, BzA-Fristtext) | PLAN_PROJ_V4.md:369-388 | Wächter, BzA-Mail |
| BzA-Portal-URL, KfW-Zuschussportal-URL, BzA-Mailtext | PLAN_PROJ_V4.md:392-393 | BzA-Aufgabe, Kundenmail |
| Heizreport: API-Zugang anfragen (Text in `docs/heizreport-api.md`) | PLAN_PROJ_V4.md:394-395 | Heizlast per API |
| Collin: Kundennummer, Ansprechpartner, Testdatei, echte Artikelnummern | PLAN_PROJ_V4.md:396-400 | UGL-Bestellung |
| KfW: „keine Montage vor Zusage“ ausnahmslos? (CEO-Entscheidung 2) | ceo-review-2026-09.md:317-318 | KfW-Wächter |
| CEO-Fragen 1, 4–7 (Anzahlung, Kundenmails, Wartung, TAIFUN/OP, Zahlenhoheit) | ceo-review-2026-09.md:312-326 | Montage-Sperre, Statistik |
| Fristen je Aufgabe, Paketinhalte PV/KL/WB | PLAN_PROJ_V3_GOLIVE.md:156-158, 191 | Überfälligkeit, Nicht-WP-Gewerke |
| Formulare abnehmen, TAIFUN-Feinplanungsformular | PLAN_PROJ_V3_GOLIVE.md:153-160 | Montage-Protokolle, FP-Fragen |
| Subunternehmer, Teams, SpotmyEnergy-Partnerbetreuer | PLAN_PROJ_V3_GOLIVE.md:145-150, 189 | Sub-Mails, Pilot |
| Vorlauf-Schwellen 8/4 nach 2 Wochen Praxis prüfen | PLAN_PROJ_V4.md:401-402 | – (nach Pilot) |

**Infrastruktur / M365**

| Zulieferung | Quelle | blockiert |
|---|---|---|
| Shared-Postfach projektierung@, „Senden als“, Graph `*.Shared` | PLAN_PROJ_V3_GOLIVE.md:134-139 | Sub-/BzA-/Terminmails live |
| Kalender „Montageplanung“: Outlook-Rundlauf testen | PLAN_PROJ_V3_GOLIVE.md:140-144 | Kalender-Sync |
| Fern-Signatur: öffentliche HTTPS-Route oder externer Anbieter | CLAUDE.md:252-255 | Fern-Modus Signatur |
| Mobilzugriff (WireGuard) | PLAN_V2.md:69 | Außendienst unterwegs |

„Signaturen“ als eigene Zulieferung: außer der Fern-Signatur-Entscheidung
nichts Offenes gefunden. Der Server-Rollout von v11 ist laut Plan offen, laut
Server-DB aber erfolgt (Migrationsmerker `migration_v11_projekte` gesetzt).

---

## 7. Datenstand (Server-DB-Kopie, 29.09.2026 15:32)

**Migrationsstand:** vollständig für den Live-Code. Alle Merker in
`einstellungen` sind gesetzt, von `migration_v8_extern_archiv` bis
`migration_abweichung_abnahme`. 52/52 Tabellen, keine fehlenden Spalten.
Für den lokalen Stand fehlen erwartungsgemäß 1 Tabelle (`ugl_bestellungen`)
und 11 Spalten; der Probelauf von `migrate.py` zieht alles nach
(inkl. 176 PV-Artikel, 5 PV-Textblöcke, V4-Paketumbau an 4 Gewerken).

| Bestand | Anzahl |
|---|---|
| Kunden | 484 |
| Vorgänge | 498 (angelegt 13.08.–29.09.) – davon 21 mit Wiedervorlage |
| Lead-Phasen der Vorgänge | terminiert 243 · angebot 111 · erfasst 59 · neu 36 · ohne 32 · verloren 9 · gewonnen 7 · in Kontaktierung 1 |
| Leads (monday) | 466 (434 sichtbar, 32 ausgeblendet), letzte Aktualisierung 29.09. 14:58 → **monday-Sync läuft** |
| Erfassungen | 266 |
| Angebote | 176 (11.08.–29.09.): Versendet 91 · Versendet (extern) 41 · Entwurf 14 · Überholt 11 · Abgelehnt 10 · Angenommen 7 · Versand vorbereitet 1 · Individuell 1 |
| Angebotspositionen | 2.401 |
| Artikel | 190 (lokal 339 inkl. PV) |
| Projekte / Gewerke | 4 / 4 (PR-260001–004 vom 23.09., alle WP, alle Auftragseingang) · 132 Aufgaben · 1 Termin |
| Galerie-Dateien | 65 |
| Benutzer aktiv | 18: Admin 5 · Außendienst 10 · Innendienst 2 · Montage 1 |
| Benachrichtigungen | 71 (letzte 29.09. 07:03 → **Tageslauf läuft**) |

**Laufende Automatiken** (werden beim Start in `app/main.py:25-58` gestartet):

| Automatik | Takt | Zustand laut DB |
|---|---|---|
| monday-Lesesync | 15 min | aktiv (Leads am 29.09. aktualisiert) |
| Mail-Verlauf (Antworten der Angebots-Konversationen) | periodisch | aktiv, sofern Graph eingerichtet |
| 90-Tage-Prüflauf (Angebote → Abgelehnt) | täglich | aktiv |
| Fälligkeiten 07:00 + Tagesdigest 07:15 | täglich | aktiv (Benachrichtigung 29.09. 07:03) |
| Lead-Postfach-Abruf | 2 min | **aus** (`parser_modus = aus`) |
| Lead-Wiedervorlage 07:00 + Löschlauf 03:00 | täglich | aktiv (Modul im Demo-Modus) |
| Geokodierung | 5 min | aktiv |
| Lead-Mail-Warteschlange | 1 min | läuft, aber `mail_modus = protokoll` → nichts wird versendet |
| Kalender-Sync Lead | – | **aus** (`kalender_sync = aus`) |

Demo-Schalter: Projektierung `freigabe_modus = admin`, Lead
`lead_freigabe_modus = admin`. Angebots-Mails: Absender angebot@friondo.de,
BCC gesetzt.

---

## 8. Empfohlene Reihenfolge für ein Gesamt-Update (Code-Sicht)

**Schritt 0 – Hotfix bestätigen (sofort).** `update.bat` auf dem Server,
dann Vorgang 169 öffnen. Kleinstes Risiko, beseitigt den einzigen bekannten
Live-Fehler. Keine Migration.

**Schritt 1 – v16 PV-Konfigurator ausrollen (Commits bis `48f8be9`).**
Getrennt von v17 pushen:
`git push origin 48f8be9:master`

- *Warum zuerst:* Der Vertrieb (Außendienst/Innendienst) nutzt das Tool
  produktiv; PV ist ein eigener Konfigurator-Weg, WP bleibt unverändert
  (Regression 93/93). PLAN_V14 setzt „vorheriger Plan ausgerollt“ voraus.
- *Risiken:* neue Angebots-Spalten `ust_satz`, `pv_json` und der
  PV-Artikelimport (176 Artikel) laufen automatisch durch `migrate.py`;
  im Probelauf sauber. Offene PV-Zulieferungen (Dachbelegung, Datenblatt,
  DB-Schwellen) sind Einschränkungen, keine Blocker.

**Schritt 2 – v17 Projektierung V4 ausrollen (`9d0367f`).**

- *Warum danach:* Die Projektierung ist im Demo-Modus (nur Admins), auf
  dem Server gibt es 4 Projekte, alle im Auftragseingang. Die
  Phasen-Migration (Abnahme/Freigabe) betrifft 0 Gewerke. Das Risiko für den
  laufenden Betrieb ist daher gering.
- *Risiken:*
  1. `projektierung_logik_v1.xlsx` ist git-verfolgt. Wurde sie auf dem
     Server per Upload geändert, bricht `git pull --ff-only`. **Vorher auf
     dem Server prüfen/sichern.**
  2. Danach keine Stücklisten auf dem Server pflegen, solange sie in der
     Excel liegen (Provisorium 11).

**Probelauf für Schritt 1+2 bereits gemacht:** Kopie der Server-DB mit
`master` migriert (zweiter Lauf „keine Änderungen“). Alle Seiten mit allen
IDs für 4 Rollen: 43.372 Aufrufe, 0 Abstürze. Abnahmeskript 91/93 (nur die
zwei datenabhängigen Punkte aus 4.2).

**Schritt 3 – CLAUDE.md bereinigen + untracked Pläne einchecken
(Doku-Commit).** Fehler aus Abschnitt 3 korrigieren, Plan↔Version-Tabelle,
PLAN_V14-Phasen auf freie Nummern umstellen. Kein Risiko, verhindert
Verwechslungen in den folgenden Plänen.

**Schritt 4 – PLAN_PROJ_V3 (Phasen 84–86).**
V4 setzt V3 voraus. V3 löst die Provisorien 1–3, 14 und 19 ab und ist
Bedingung für den Go-live der Projektierung (Demo → Pilot).
*Risiko:* Bestandsimport schreibt in Produktivdaten → vorher gegen eine
DB-Kopie testen (wie heute).

**Schritt 5 – PLAN_V14 (BzA-Datenblatt am Angebot, BAFA-Nummern).**
Erst nach V16-Rollout (Plan-Voraussetzung). *Achtung Überschneidung:* Es
gibt bereits ein BzA-Datenblatt am **Gewerk** (v15, `projektierung/bza.html`)
und die BzA-Erfassung aus v17. V14 sollte darauf aufbauen statt ein zweites
Datenblatt zu bauen – vor dem Start abgleichen. Offene Zulieferungen
(weiße 8800er, Hybrox) blockieren nur Teile.

**Schritt 6 – PLAN_LEAD_V1.1 (Phasen 87–89).**
Unabhängig von den anderen Strängen, im Demo-Modus risikoarm. Könnte auch
parallel zu Schritt 4/5 laufen, wenn das Lead-Team drängt.

**Querschnitt – jederzeit, sobald die Zulieferungen kommen:** Klassengrenzen,
VK-Preisliste, CS8800-Broschüre, TAIFUN-Muster (PLAN_V11-Reste), Collin-Daten,
Heizreport-Zugang.

**Grundregel für jeden Rollout** (bewährt am 29.09.): vorher eine aktuelle
Server-DB-Kopie ziehen, lokal migrieren, Crawl + Abnahmeskript dagegen.
Erst dann pushen und `update.bat`.
