# Umsetzungsplan v21 – Wallbox-Konfigurator (Sparte WB), Angebotstool-Feedback 15.10.2026 (Alternativ-Kennzeichen, Elektroarbeiten ins PV-Angebot, Kombi-Versand, Auslegungszeile, Mail-Vorlage je Sparte, TAIFUN-PDF per Drag & Drop), Mobil (Angemeldet bleiben, Diktat, Galerie-Mehrfachupload, Kamera-Serie)

Voraussetzung: kein anderer Plan in Umsetzung (strangübergreifend). Stand
15.10.2026: v30 (PLAN_V18) ist ausgerollt; **v31 (PLAN_LEAD_V5, Phasen
153–160) und v32 (PLAN_V19, Phasen 161–165)** laufen als gemeinsamer
Durchlauf bzw. stehen vor dem Rollout; **v33 (PLAN_V20, Phasen 166–177)** ist
an Claude Code übergeben; **PLAN_LEAD_V6 (Claudia Castro)** wartet noch. **Nummern geprüft 15.10.2026 (Claude Code, Auftrag
Andreas):** die Zuordnungstabelle in CLAUDE.md endet bei v33 / Phase 177 – dieser Plan wird daher
als **v34, Phasen 178–182** gebaut (vorher v35/183–187 im Text); PLAN_LEAD_V6 rückt auf v35/183–187.
Dieser Plan setzt auf dem committeten v33-Stand auf (Objekte am Vorgang aus v31 – die Objekt-Ordner der Galerie aus PLAN_LEAD_V6 (v35)
liegen noch nicht vor –, Graph als Anwendung und Rollen-Varianten aus v33, Tabellen-Layout
aus v33). v31 bis v33 sind committet und gepusht (v33 Rollout im Wartungsfenster Dienstag). CLAUDE.md und
`konfigurator_logik_v5.xlsx` sind Live-Master im Projektordner
`C:\Users\a.scheelen\Tools\Angebotstool` (Git-Arbeitskopie). ALLE PHASEN
DIESES PLANS IN EINEM DURCHLAUF UMSETZEN (Reihenfolge einhalten, jede
Checkbox nach Umsetzung und Test abhaken, am Ende Gesamtübersicht mit
Testergebnissen und offenen Punkten, fachliche Rückfragen gebündelt). **Ein
gemeinsamer Commit am Ende**, migrate.py idempotent, **nur additive
Migrationen** (v33-Code muss auf der v34-Datenbank weiterlaufen, Rückweg
`rollback.bat --nur-code`). **Kein git push vor Freigabe.**

CLAUDE-Abschnitt: **„Neu in v34“** (geprüft 15.10.2026: v31 = PLAN_LEAD_V5, v32 =
PLAN_V19, v33 = PLAN_V20; v34 ist die nächste freie Nummer der Zuordnungstabelle).
Phasen **178 bis 182** (nächste freie Nummern; PLAN_LEAD_V6 bekommt bei seiner Umsetzung
v35 / 183–187). Die
v27-Regeln gelten (`def`-Routen, keine offene Datenbanksitzung während
Datei- oder Netz-I/O, `_speichern`-Muster für schreibende Routen,
Scheduler-Rahmen, Wächter-Test `tests/test_v27_sitzungen.py` grün,
Inventartabelle `docs/betrieb.md`), die v30-Regeln für Oberflächen (Tokens
Hell/Dunkel, Token-Wächter `tests/test_v30_design.py`, `tojson |
forceescape` in on*-Attributen, Zurück-Leiste aus `base.html`) und die
v33-Tabellenregeln (Lead-Board-Layout) für neue Listen.

Geltungsbereich: Angebotstool – Konfigurator-Rahmen (`app/logik.py`,
`app/angebot_aufbau.py`, `app/konfigurator.py`, `app/routers/erfassung.py`,
Steuerdatei `konfigurator_logik_v5.xlsx`), neues Modul `app/wb_auslegung.py`
und Import `app/import_wallbox.py`, Angebots-Editor und PDF
(`app/pdf_export.py`, `app/routers/angebote.py`, `app/angebotsprofile.py`,
`ANGEBOTSTEXTE.md`), Kombi-Versand und externe TAIFUN-Einträge
(Vorgangsakte, Dialog „Extern erledigt“), Mail-Vorlagen
(`app/mail_vorlagen.py`), Anmeldung (`app/auth.py`, `/login`), mobile
Erfassung (Diktat) und Galerie (`app/galerie.py`, `_galerie.html`,
Upload-Routen). **Nicht berührt:** WP-/PV-/KL-Rechenkerne (nur die
Auslegungszeile, Phase 180), KfW-Modul, monday-Sync und -Rückspielung,
Lead-Management (außer Galerie-Upload am Vorgang), Projektierung (außer
Galerie-Upload und Montage-Fotos), Graph/Kalender (v33), Cloover (eigener
Plan). **Außendienst sieht weiterhin nie EK oder Deckungsbeiträge** – auch
nicht in den neuen WB-Positionen, im Import-Protokoll oder in der
Parametrierungs-Lesesicht.

## Entscheidungen (Chat Angebotstool, 15.10.2026, Andreas)

- **Wallbox-Konfigurator fertig machen:** Eine WB-Katalog-Erfassung erzeugt
  ein vollständiges Tool-Angebot (bisher WB = immer Freitext → TAIFUN). Nur
  **zwei Abfragen ändern das Angebot**: (1) Wallbox **Mennekes AMTRON 4You
  310** oder **560** (bestätigt 15.10.: 310/560 wie in der Excel, nicht
  360/510); (2) **Leitungslänge** als freie Zahl – **10 m sind in der
  Anschlussvorbereitung enthalten**, jeder weitere Meter wird mit den beiden
  Meter-Positionen aus `Extraleitung.xlsx` berechnet („lfd. Meter NYY-J
  5x10mm² … liefern und verlegen“ 49,34 €/m und „Lieferung und Montage
  zusätzlichen Montagekanal in Designausführung“ 47,00 €/m).
- **Immer im Angebot:** „Anschlussvorbereitung Ladestation …“ (psl.) und
  „Netzanmeldung beim EVU nach §14a EnWG“ (0,00 €).
- **TAIFUN-„Text vor Position“** („Komplettpaket Wallbox inkl. Montage …“)
  wird im Tool **Vortext** (Textblock), keine Position.
- **Elektroarbeiten ins PV-Angebot (0 % USt):** Der gewünschte Knopf zur
  „Förderungs-/USt-Optimierung“ verschiebt die Elektroarbeiten eines
  WP-/KL-/WB-Angebots in das PV-Angebot desselben Vorgangs: im Ursprungs-
  angebot als Alternativ-Positionen „im PV-Angebot enthalten“, im PV-Angebot
  voll berechnet zu 0 % USt.
- **Alternativ-Hinweis** („in anderem Angebot enthalten“) im PDF und im
  Editor **klar abgegrenzt und farbig** – heute ist er von einer
  Eventualposition kaum zu unterscheiden.
- **Kombi-Versand:** Die Auswahl in der Vorgangsakte war unklar, und es war
  nicht nachvollziehbar, warum Angebote erst auf „Versand vorbereitet“ stehen
  müssen. Künftig Häkchen an allen versandfähigen Angeboten; Entwürfe werden
  beim Kombi-Versand automatisch vorbereitet.
- **Auslegungs-Position** („Auslegung der Wärmepumpe“, „Auslegung der
  Klimaanlage“, PV-Auslegungszeile) **aus dem Angebot entfernen** – die
  Herleitung bleibt im Konfigurationsprotokoll und für den Innendienst im
  Editor sichtbar.
- **Klima-Mailtext** wurde beim Versand eines Klima-Angebots nicht
  automatisch gezogen – Ursache finden und beheben (Sparten-Vorlage muss
  greifen).
- **TAIFUN-Angebots-PDF per Drag & Drop** beim Anlegen externer
  TAIFUN-Einträge („Extern erledigt“) und am Eintrag; Nummer, Datum und
  Endbetrag werden aus dem PDF vorbelegt.
- **Mobil:** „Angemeldet bleiben“ funktioniert am Handy nicht; eine
  Diktierfunktion für Textfelder fehlt; in der Galerie sollen mehrere Fotos
  in verschiedene Ordner gelegt und **einmal gemeinsam** hochgeladen werden;
  mit der Kamera sollen **mehrere Fotos nacheinander** geschossen und dann
  gemeinsam hochgeladen werden.
- **Nicht Teil dieses Plans:** Cloover-Finanzierung (eigener Plan),
  Outlook/Kalender (v33), Dachbelegungstool (offen seit v16).

## Grundlagen Wallbox (Zulieferung Andreas 15.10.2026)

Quellen: `Wallbox Artikel Excel.xlsx` (TAIFUN-Angebotsexport, Blatt
„Tabelle 1“, Spalten GUID · Position · Menge · Einheit · Beschreibung ·
E-Preis · G-Preis · Einkaufspreis Material), `Extraleitung.xlsx` (gleicher
Aufbau, zusätzlich die beiden Meter-Positionen), Beispielangebot AN261737
vom 17.09.2026 (PDF mit Kundendaten – **nicht ins Git, nicht ins
Projektwissen**; Ablage siehe Zulieferungen). Beide Excel-Dateien enthalten
eine EK-Spalte und gehören deshalb **nur** in den Projektordner unter
`Artikel-Preislisten/Wallbox/` (wie die WP-/PV-/KL-Preislisten), nie ins
Projektwissen.

Positionen (VK netto, Kundenpreise laut Export):

| WB-Nr. | Quelle (Datei · Pos.) | Einheit | Bezeichnung (erste Zeile) | E-Preis |
|---|---|---|---|---|
| WB001 | Wallbox Artikel Excel · 001 | Stück | Mennekes AMTRON 4You 310 11 kW mit 7,5 m Ladekabel | 938,50 € |
| WB002 | Wallbox Artikel Excel · 002 | Stück | Mennekes AMTRON 4You 560 11 kW mit 7,5 m Ladekabel | 1.390,55 € |
| WB003 | Wallbox Artikel Excel · 003 | psl. | Anschlussvorbereitung Ladestation mit Ladeanschlussleistung bis zu 11 KW | 1.297,20 € (**Extraleitung.xlsx: 1.597,20 €** – Rückfrage 1) |
| WB004 | Wallbox Artikel Excel · 004 | psl. | Netzanmeldung beim EVU nach §14a EnWG | 0,00 € |
| WB005 | Extraleitung · 004 | m | lfd. meter NYY-J 5x10mm², separate Erdung 16mm² und Ethernet-Kabel CAT7 zwischen der Hauptverteilung und geplantem Ort der Ladestation liefern und verlegen | 49,34 €/m |
| WB006 | Extraleitung · 005 | m | Lieferung und Montage zusätzlichen Montagekanal in Designausführung | 47,00 €/m |

Die Langtexte der Positionen (Produktvorteile, Produkteigenschaften,
Leistungsumfang der Anschlussvorbereitung) kommen wörtlich aus der Spalte
„Beschreibung“ (Zeilenumbrüche `_x000D_\n` → echte Zeilenumbrüche, „?“-
Platzhalter der TAIFUN-Symbole entfernen). **Die GUIDs sind je Export
verschieden** (dieselbe Anschlussvorbereitung trägt in beiden Dateien eine
andere GUID) – sie sind Angebots-GUIDs, keine Artikelstamm-GUIDs. Der Import
pinnt deshalb über das Blatt „WB-Artikel“ (Datei + Position + Beschreibungs-
anfang), nicht über die GUID.

Vortext laut TAIFUN-Muster (Seite 1, wörtlich zu übernehmen, Häkchen-Liste
wie beim WP-/KL-Vortext):

> **Ihre individuelle Wallbox zum Festpreis**
>
> {briefanrede}
>
> vielen Dank für Ihr Vertrauen in die Friondo GmbH. Mit einer modernen
> Wallbox laden Sie Ihr Elektrofahrzeug bequem zu Hause, sparen Zeit und
> machen sich unabhängiger von öffentlichen Ladeinfrastrukturen. So schaffen
> Sie Komfort, Sicherheit und ein smartes Energiemanagement direkt bei Ihnen
> vor Ort.
>
> Anbei erhalten Sie Ihr maßgeschneidertes Angebot. Darin enthalten sind:
>
> - [Haken] Ihre individuelle Wallbox – perfekt abgestimmt auf Ihre Immobilie & Ihren Bedarf
> - [Haken] Fachgerechte Installation – sauber, sicher und termingerecht
> - [Haken] Transparent & zum Festpreis – klar verständlich, ohne versteckte Kosten
> - [Haken] Unser Rundum-Sorglos-Service – von der Planung bis zur Inbetriebnahme
>
> **Warum Friondo?**
>
> - [Haken] **Fachkompetenz & Qualität** – Als Meisterbetrieb und zertifizierter Fachbetrieb setzen wir auf höchste Standards
> - [Haken] **Alles aus einer Hand** – Von Photovoltaik bis Energiemanagement – perfekt kombinierbar mit Ihrer Wallbox
> - [Haken] **Persönliche Beratung** – Wir begleiten Sie von der ersten Idee bis zur fertigen Lösung
> - [Haken] **Effizienz & Nachhaltigkeit** – Wir helfen Ihnen, Ihr Zuhause energieoptimiert und zukunftssicher zu gestalten
> - [Haken] **Fördermittel-Check & Unterstützung** – Wir prüfen für Sie mögliche Zuschüsse und Förderungen
>
> Wir sind auf moderne Energiesysteme spezialisiert und gehören in der Region
> zu den führenden Anbietern von Photovoltaik, Wärmepumpen, Klimaanlagen,
> Energiemanagement-Systemen und Wallboxen. Lassen Sie uns gemeinsam Ihr
> Zuhause fit für die Zukunft machen!
>
> Ihr Friondo-Team

Der TAIFUN-„Text vor Position“ („Komplettpaket Wallbox inkl. Montage – Die
Zukunft der Energie beginnt bei Ihnen zuhause … effizient, nachhaltig und
zuverlässig.“) wird **ein eigener Absatz am Ende des Vortexts** (Überschrift
„Komplettpaket Wallbox inkl. Montage“, Text wörtlich aus der Excel-Zeile ohne
GUID/Position, „?“-Platzhalter entfernt) [ANNAHME: am Ende des Vortexts, nicht
als Gruppen-Überschrift im Positionsteil].

Muster-Nachtext (TAIFUN): nur „Installationsvoraussetzungen“ (Haftungs-
begrenzung, Rücktrittsrecht Feinplanung), Zahlung, Bindefrist 30 Tage, AGB,
Datenschutz, Schlussseite mit Unterschrift **und die Vollmacht-Seite**
(SpotmyEnergy/§14a, Nachtext D). Kein „Ihre Zahlungsoptionen“ (Nachtext A),
kein Förderblock, keine Wirtschaftlichkeit.

## Phase 178 – Wallbox: Steuerdatei und Artikel-Import

Vorbild ist der Klimakonfigurator (v24): eigene Blätter in
`konfigurator_logik_v5.xlsx`, eigener Import, `logik_fuer_sparte(logik,
"WB")` liefert die WB-Sicht, sobald „Aktionen WB“ existiert. Sicherung der
Steuerdatei vor der Änderung nach `diagnose/konfigurator_logik_v5.vor_v34.xlsx`.

- [x] **Blatt „Fragen WB“** (ersetzt das bisherige Nicht-Vorhandensein; WB
      hatte keinen Bogen): eine Seite „Wallbox“ mit
      **WB01** „Welche Wallbox?“ (Auswahl, Pflicht: „Mennekes AMTRON 4You 310
      – 11 kW, 7,5 m Ladekabel“ | „Mennekes AMTRON 4You 560 – 11 kW, 7,5 m
      Ladekabel, MID-Zähler, App, OCPP“; keine Vorbelegung [ANNAHME]),
      **WB02** „Leitungslänge Hauptverteilung ↔ Wallbox in Metern (gesamt;
      bis 10 m in der Anschlussvorbereitung enthalten)“ (Zahl, Pflicht,
      Dezimalkomma erlaubt, `inputmode="decimal"`, Vorbelegung 10),
      **WB03** „Bemerkungen zur Ausführung (optional)“ (Freitext, nur
      Protokoll). Hilfetexte in der Spalte „Hinweis“ wie bei KL. Die
      Abschluss-Seite „Einschätzung“ (Hot-Ampel + Wiedervorlage, S01/S02)
      erscheint wie bei den übrigen Katalog-Sparten, sofern der Bogen-Rahmen
      sie spartenübergreifend liefert [ANNAHME – Claude Code prüft und
      berichtet]. Objektart aus `kunden.objektart` wird **nicht** abgefragt
      (keine Auswirkung auf das Angebot).
- [x] **Blatt „WB-Artikel“** (Pinning wie „PV-Artikel“/„KL-Artikel“, aber
      über Datei + Position statt GUID): Spalten `WB-Nr.` · `Datei` ·
      `Position` · `Beschreibungsanfang` · `GUID (zuletzt gesehen)` ·
      `Einheit` · `Bemerkung`; sechs Zeilen WB001–WB006 laut Tabelle im
      Abschnitt „Grundlagen Wallbox“. Der Import findet die Zeile über
      `Datei` + `Position`, prüft den `Beschreibungsanfang` (erste 40
      Zeichen, Groß-/Kleinschreibung und doppelte Leerzeichen ignoriert) und
      schreibt die aktuelle GUID in „zuletzt gesehen“; Abweichung des
      Beschreibungsanfangs → Fehler im Import-Protokoll, Zeile wird nicht
      importiert.
- [x] **Blatt „Aktionen WB“** (Schreibweise wie „Aktionen KL“, Spalten
      Frage · Antwort · Aktion · Zusatzbedingung · Bemerkung):
      `WB01 = AMTRON 4You 310 → WB001 × 1`; `WB01 = AMTRON 4You 560 → WB002
      × 1`; `immer → WB003 × 1`; `immer → WB004 × 1`; `WB02 > 10 → WB005 ×
      Mehrlänge`; `WB02 > 10 → WB006 × Mehrlänge` [ANNAHME: Montagekanal
      immer zusammen mit der Mehrlänge – Rückfrage 2]. Mengenwort
      „× Mehrlänge“ wird vom Lader erkannt (`refs_extrahieren`); Mehrlänge =
      WB02 − `leitung_inklusive_m`, kaufmännisch auf ganze Meter gerundet,
      nie unter 0 [ANNAHME: ganze Meter wie Pos. 103 bei A13].
- [x] **Blatt „Angebotsaufbau WB“:** Block 1 „Wallbox“ (WB001/WB002), Block 2
      „Installation und Anschluss“ (WB003, WB005, WB006), Block 3
      „Netzanmeldung“ (WB004) – Gruppen-Überschriften editierbar wie seit
      v22 [ANNAHME: drei Blöcke; alternativ ein Block ohne Überschrift wie im
      TAIFUN-Muster]. Keine Auslegungszeile (siehe Phase 180).
- [x] **Blatt „WB-Parameter“:** `leitung_inklusive_m` = 10 (Einheit m),
      `meterposition_leitung` = WB005, `meterposition_kanal` = WB006,
      `wallbox_standard` = leer (keine Vorbelegung) – Anzeige in der
      Parametrierung mit Einheit wie KL-/PV-Parameter, fehlende Zeilen als
      Hinweis mit Standardwert (`logik.wb_parameter`,
      `wb_parameter_einheit`).
- [x] **Blatt „Textregeln“:** keine neuen Regeln nötig; „?“-Platzhalter und
      `_x000D_` werden im Import bereinigt (siehe unten). **Blatt „Anhänge“:**
      Zeile `Mennekes AMTRON 4You Datenblatt.pdf` mit Regel „wenn Sparte =
      WB“ (Platzhalterzeile „(Mennekes-Datenblatt – Zulieferung)“ bis die
      Datei in `anlagen/` liegt; `anhaenge.fehlende_dateien` meldet sie),
      optional zwei Dateien je Modell mit Regel „bei Artikel WB001“ / „bei
      Artikel WB002“, falls Mennekes getrennte Datenblätter liefert
      [ANNAHME]. „Lesehilfe“-Absatz „Wallbox (v34)“.
- [x] **Lader `app/logik.py`:** Felder `wb_aktionen`, `wb_bloecke`,
      `wb_parameter`, `wb_parameter_einheit`, `wb_artikel` (+ `_zeilen`,
      `_nummern`); `logik_fuer_sparte(logik, "WB")` liefert die WB-Sicht,
      sobald „Aktionen WB“ existiert (sonst wie bisher `None` → Freitext).
      „Logik prüfen“: WB-Referenzen gegen „WB-Artikel“, Mengenwort
      „× Mehrlänge“ nur bei WB02-Bedingungen, Parameter vollständig,
      unlesbare Zahlen (Fehler); fehlende Pflichtparameter sind Hinweise mit
      Standardwert.
- [x] **Import `app/import_wallbox.py`** („Artikel → Wallbox-Positionslisten
      importieren“ in Parametrierung → Logik & Importe, Lesesicht und
      Artikelliste; migrate.py importiert automatisch, wenn referenzierte
      WB-Artikel fehlen): liest `Artikel-Preislisten/Wallbox/Wallbox Artikel
      Excel.xlsx` und `Artikel-Preislisten/Wallbox/Extraleitung.xlsx`
      (Blatt „Tabelle 1“, Kopfzeile wie oben; Zeilen ohne Position =
      Textzeilen, werden übersprungen), Quelle `QUELLE_WB = "wb"`, Anker =
      WB-Nr. aus dem Blatt „WB-Artikel“; Re-Import ohne Doppel, WP-/PV-/
      KL-Importe fassen WB nicht an. Beschreibung: `_x000D_\n` → `\n`,
      „?“-Platzhalter (TAIFUN-Symbole) samt umgebendem Doppel-Leerzeichen
      entfernen, führende Leerzeichen je Zeile entfernen; Einheit `psl.` /
      `Stück` / `m`; VK = E-Preis; **EK aus der Spalte „Einkaufspreis
      Material“ nur in `artikel.ek_cent`** (Innendienst/Admin, nie in
      Protokoll-Ausgaben, die der Außendienst sehen könnte). Import-Protokoll
      mit Datei, Position, WB-Nr., VK, GUID-Wechsel; **Preiskonflikt**: liegt
      dieselbe WB-Nr. in beiden Dateien mit verschiedenem Preis, gewinnt die
      im Blatt „WB-Artikel“ genannte Datei, der Konflikt wird im Protokoll
      und in der Gesamtübersicht genannt (Rückfrage 1).
- [x] **Parametrierung:** Lesesicht `/parametrierung/wb-logik` (Fragen,
      Aktionen, Angebotsaufbau, WB-Artikel, WB-Parameter – nur Anzeige, AD
      nie), Import-Knopf, Filter „Sparte WB“ in der Artikelliste (Suchlink
      WB0), DB-Ampel-Zeile WB (Schwellen je Sparte, v16; Standard = WP-Werte
      [ANNAHME]). `.gitignore`: `Artikel-Preislisten/Wallbox/Beispielangebot.pdf`
      (Kundendaten, wie PV).
- [x] Tests `tests/test_wb_v34_import.py` / `_logik.py`: Stichproben WB001
      938,50 € Stück, WB003 1.297,20 € psl. (bzw. der laut Rückfrage 1
      bestätigte Preis), WB005 49,34 € m, WB006 47,00 € m, WB004 0,00 €;
      Summe der importierten Preise aus `Wallbox Artikel Excel.xlsx` =
      3.626,25 € (Kontrolle gegen das Muster AN261737); Re-Import idempotent;
      Beschreibung ohne `_x000D_` und ohne „?“; „Logik prüfen“ grün.

## Phase 179 – Wallbox: Rechenkern, Erfassung, Angebot, Texte, PDF

- [x] **Rechenkern `app/wb_auslegung.py`** (reine Funktionen, Vorbild
      `kl_auslegung.py`): `auslegen(logik, antworten)` → `Auslegung(wallbox,
      leitung_m, mehrlaenge_m, positionen)`; `positionen_zusammenstellen(logik,
      antworten, session)` liefert die Positionsliste in Blockreihenfolge
      (Wallbox · Anschlussvorbereitung · Meter-Positionen × Mehrlänge ·
      Netzanmeldung), `validierung(antworten)` liefert Absende-Meldungen
      („Wallbox auswählen“, „Leitungslänge fehlt oder ist keine Zahl“,
      „Leitungslänge über 100 m – bitte prüfen“ [ANNAHME: Warnung, keine
      Sperre]), `protokoll_zeilen(a)` füllt die Seite „Auslegung“ des
      Protokoll-PDFs („Wallbox: AMTRON 4You 560“, „Leitungslänge gesamt:
      25 m, davon 10 m in der Anschlussvorbereitung enthalten, Mehrlänge
      15 m“). **Keine AMPEL-Gründe** – eine WB-Katalog-Erfassung ist immer
      grün; individuelle Fälle laufen über die Freitext-Weiche [ANNAHME].
- [x] **Einbindung:** `angebot_aufbau.angebot_anlegen` behandelt WB wie KL
      (`konfigurator_typ = "WB"`, `kfw_json = "{}"`, 19 % USt über
      `ust_standard`, Spalte `angebote.wb_json` (neu, additiv) mit
      `Auslegung.als_dict()`), `konfigurator.*`-Verzweigungen (Vorbelegung
      WB02 = `leitung_inklusive_m`), `routers/erfassung.py`: Sparten-Start
      leitet WB **nicht mehr** direkt in den Freitext, sondern auf die Weiche
      (Katalog | Freitext) wie PV/KL (`sparten_start`, `weiche`); GW bleibt
      Freitext; Innendienst-Knöpfe „Angebot erzeugen“ / „Erneut prüfen“ auch
      für WB; Versionen/Duplikate/Kopien übernehmen `wb_json`;
      `positionsregeln_anwenden` fügt bei WB keine Pos. 014–017 ein (kein
      Fit for Future) [ANNAHME]. Bestehende WB-Freitext-Erfassungen bleiben
      unverändert in der TAIFUN-Schiene.
- [x] **Texte** (`app/angebotsprofile.py`, Seed `seed_wb` in migrate.py,
      editierbar in Parametrierung → Textblöcke): Textblöcke „Friondo WB
      Standard“ (Vortext wörtlich aus „Grundlagen Wallbox“ inkl. Absatz
      „Komplettpaket Wallbox inkl. Montage“ + Nachtext), „Friondo WB Enni“,
      „Friondo WB SWD“, „Friondo WB Sparkasse DU“ (Nachtexte, Start = Kopie
      des Standard-Nachtexts [ANNAHME]). Nachtext WB = Nachtext B
      „Installationsvoraussetzungen“ (Haftungsbegrenzung, Rücktrittsrecht
      Feinplanung wie KL) + Nachtext C (Schlussseite; Zahlungsbedingungen
      laut v30-Standard „50 % am Montagetag …“ – das TAIFUN-Muster nennt
      „Anzahlung 50 % spätestens 14 Tage vor Arbeitsbeginn“, Rückfrage 3) +
      **Nachtext D Vollmacht** (im TAIFUN-Muster enthalten; Vollmacht bei WB
      immer, weil Netzanmeldung §14a [ANNAHME – Rückfrage 4]); **kein**
      Nachtext A „Ihre Zahlungsoptionen“ (nicht im Muster; Cloover-Plan kann
      ihn später ergänzen), kein KfW-/Förderblock, keine Wirtschaftlichkeit,
      kein `[WIRTSCHAFTLICHKEIT]`-Platzhalter. Wortlaut in `ANGEBOTSTEXTE.md`
      Abschnitt 10 „Wallbox (v34)“; alle WB-Texte sind Entwürfe für das
      Gegenlesen durch den Innendienst.
- [x] **PDF/Editor:** Gruppen-Überschriften aus „Angebotsaufbau WB“,
      Summenblock Netto · 19,00 % USt. · Gesamt-Betrag (ggf. − Rabatt /
      = Endbetrag), Anhang laut Anhänge-Regel, Lieferschein (v16) und
      Protokoll-PDF (Seite „Auslegung“) funktionieren für WB; Sparten-Badge
      WB in Angebotsliste/Akte/Statistik unverändert; E-Mail-Vorlage WB (v27-
      Nachtrag 2) wird gezogen (nach Korrektur in Phase 180).
- [x] **Kontrollfälle** `tests/test_wb_v34.py` (bei bestätigtem Preis
      1.297,20 € für WB003; weicht der bestätigte Preis ab, Werte im Plan
      durch Claude Code neu rechnen und in der Gesamtübersicht nennen):
      **Fall A** 310, 10 m → Positionen WB001 · WB003 · WB004, Netto
      **2.235,70 €**, USt **424,78 €**, Gesamt **2.660,48 €**; **Fall B** 560,
      25 m → WB002 · WB003 · WB005 × 15 (740,10 €) · WB006 × 15 (705,00 €) ·
      WB004, Netto **4.132,85 €**, USt **785,24 €**, Gesamt **4.918,09 €**;
      **Fall C** 560, 8 m → keine Meter-Positionen, Netto **2.687,75 €**, USt
      **510,67 €**, Gesamt **3.198,42 €**; **Fall D** 310, „12,4“ → Mehrlänge
      2 m (kaufmännisch) → Netto 2.235,70 + 2 × 96,34 = **2.428,38 €**;
      **Fall E** Leitungslänge leer → Absende-Meldung „Leitungslänge fehlt
      oder ist keine Zahl“; **Fall F** Freitext-Weiche WB → unverändert
      Individuell/TAIFUN-Warteschlange. Abnahme-PDFs ohne Kundendaten
      `docs/wallbox/abnahme-A-<Nr>.pdf`, `abnahme-B-<Nr>.pdf`,
      `abnahme-protokoll.pdf`; Außendienst-Sicht „Meine Angebote“ eines
      WB-Angebots ohne EK/DB (Test).

## Phase 180 – Angebotstool-Feedback 15.10.2026

- [x] **Alternativ-Kennzeichen klar abgrenzen** (v10 „in anderem Angebot
      enthalten“): **PDF** – vor der ersten Alternativ-Position eines Blocks
      ein farbig hinterlegter Hinweiskasten (Akzentfarbe hell, Rahmen
      Akzent; fpdf2-Primitiven wie die Wirtschaftlichkeitsseiten) mit dem
      Text „Die folgenden Positionen sind bereits in Ihrem Angebot
      <Angebotsnummer des Geschwister-Angebots> (<Sparte>) enthalten und
      werden dort berechnet.“; die Positionen selbst zeigen in der
      G-Preis-Spalte **„im PV-Angebot“** (bzw. „im WP-Angebot“ …) statt „EP.“,
      Einzelpreis bleibt sichtbar, die Zeile ist leicht grau hinterlegt; der
      bisherige automatische Vermerk am Ende des Positionsteils bleibt.
      **Editor** – Positionszeile mit farbigem linken Balken und Badge
      „Alternativ · im PV-Angebot AN-C-…“ (Link zum Geschwister-Angebot),
      Eventualpositionen behalten ihr bisheriges Badge „EP“ – beide Zustände
      sind auf einen Blick unterscheidbar (Tokens Hell/Dunkel, neuer Token
      `--alternativ` + `--alternativ-flaeche` im Token-Block). Lieferschein:
      Alternativ-Positionen wie bisher nicht enthalten. Abnahme-PDF nach
      `docs/wallbox/abnahme-alternativ-<Nr>.pdf`.
- [x] **Knopf „Elektroarbeiten ins PV-Angebot (0 % USt)“** im Editor eines
      WP-/KL-/WB-Angebots (Entwurf; Innendienst/Admin), sichtbar nur, wenn
      der Vorgang ein PV-Angebot im Status Entwurf oder Versand vorbereitet
      hat (`konfigurator_typ = PV`, nicht überholt). Ablauf (eine
      `_speichern`-Transaktion, Route `POST /angebote/<id>/elektro-ins-pv`):
      (1) Ermitteln der **Elektro-Positionen** = alle Positionen des Blocks
      „Elektroarbeiten“ (WP Block 7; KL Block 2 „Elektro“; WB WB003/WB005/
      WB006) **plus** alle Positionen aus der Parametrierungsliste
      „gewerkeübergreifende Artikel“ (v10), ohne bauseits/EP/bereits
      Alternativ; (2) im Ursprungsangebot werden sie Alternativ „im
      PV-Angebot enthalten“ mit Verknüpfung zum PV-Angebot (bestehendes
      Kennzeichen und Vermerk aus v10, Darstellung aus dem Punkt oben); (3)
      im PV-Angebot werden sie als voll berechnete Positionen (gleicher
      Artikel, gleicher Netto-Einzelpreis, gleiche Menge, Langtext,
      `ek_cent`) in einer neuen Gruppe „Elektroarbeiten <Sparte>
      (aus Angebot AN-C-…)“ am Ende eingefügt, Kennzeichen
      `uebernommen_von_angebot_id` + `uebernommen_von_position_id` (neue
      Spalten, additiv); 0 % USt gilt automatisch über den Steuersatz des
      PV-Angebots; (4) Vermerk im PV-Angebot „Enthält die Elektroarbeiten aus
      Angebot AN-C-… (<Sparte>).“; (5) Notiz im Vorgangs-Chat; (6) Meldung
      „n Positionen (netto x €) in AN-C-… übernommen – Kundenersparnis
      <19 % von x> €“. **Rückgängig:** Knopf „Elektroarbeiten zurückholen“
      im Ursprungsangebot entfernt die übernommenen Positionen aus dem
      PV-Angebot und hebt das Alternativ-Kennzeichen auf (nur solange beide
      Angebote Entwurf/Versand vorbereitet sind). Wiederholter Klick ohne neue
      Elektro-Positionen → Meldung „Nichts zu übernehmen“. **Konsistenz:**
      wird das PV-Angebot gelöscht/abgelehnt/überholt, zeigt das
      Ursprungsangebot den bestehenden v10-Hinweis „Geschwister-Angebot
      nicht mehr gültig“ und bietet „Elektroarbeiten zurückholen“ an;
      Kombi-Versand-Warnung „doppelt voll berechnet“ (v10) schlägt danach
      nicht mehr an (Test). DB je Angebot folgt den Positionen (Ursprung
      sinkt, PV steigt). Mehrere Sparten (WP + KL + PV): je Ursprungsangebot
      eigene Gruppe im PV-Angebot. Steuerliche Zulässigkeit ist Entscheidung
      von Friondo/Steuerberatung – das Tool setzt nur um (Hinweis in
      `docs/nach-dem-update-v34.md`).
- [x] **Kombi-Versand verständlich** (Vorgangsakte, Abschnitt „Angebote“):
      eigener Kasten **„Gemeinsam versenden“** mit Häkchen an **allen
      versandfähigen Angeboten** des Vorgangs – Status Entwurf, Versand
      vorbereitet, TAIFUN-Eintrag mit PDF (ohne PDF ausgegraut mit Hinweis
      „PDF fehlt“); überholte/abgelehnte/angenommene/versendete nicht
      wählbar (ausgegraut, Tooltip mit Grund). Knopf „Kombi-Versand
      vorbereiten (n Angebote)“: Entwürfe werden **automatisch auf „Versand
      vorbereitet“** gesetzt (Verlaufsnotiz „durch Kombi-Versand“), dann
      läuft der bestehende Kombi-Versand (v10: eine Mail, mehrere PDFs,
      Kombi-Vorlage mit {angebotsliste}, Dedupe der Broschüren, Warnung bei
      doppelt voll berechneten Artikeln). Erklärsatz über den Häkchen: „Alle
      angehakten Angebote gehen als separate PDFs in einer Mail an den
      Kunden; Entwürfe werden dabei automatisch versandfertig gemacht.“ Im
      Angebots-Editor ein Knopf „Mit weiteren Angeboten dieses Vorgangs
      versenden“ (Sprung in den Kasten, Angebot vorausgewählt). Die
      bisherige Beschränkung auf „Versand vorbereitet“ entfällt; Einzel-
      Versand unverändert.
- [x] **Auslegungs-Position aus dem Angebot entfernen** (WP „Auslegung der
      Wärmepumpe“ Block 1, KL „Auslegung der Klimaanlage“ Block 3, PV-
      Auslegungszeile „Auslegung: … Module …“): `angebot_aufbau`,
      `kl_auslegung.positionen_zusammenstellen`, `pv_auslegung.
      positionen_zusammenstellen` legen **keine** Auslegungs-Position mehr an;
      der Auslegungstext bleibt (a) im Konfigurationsprotokoll (Seite
      „Auslegung“ bzw. Protokollzeile, unverändert), (b) im Editor als
      aufklappbarer grauer Hinweis „Auslegung (intern)“ unter der Kopfkarte
      (Innendienst/Admin; **Außendienst sieht ihn nicht** – er enthält bei WP
      Verbrauch/Heizlast, keine Preise, aber die interne Herleitung),
      gespeichert in `angebote.auslegung_text` (neu, additiv, beim Anlegen
      gefüllt, bei Überarbeiten/Duplizieren/Kopieren übernommen). Bestand:
      Migration `migration_v34_auslegung` entfernt die 0,00-€-Auslegungs-
      Position aus allen Angeboten im Status **Entwurf** (Protokoll-Zeile je
      Angebot; versendete/angenommene/überholte Angebote bleiben unverändert)
      [ANNAHME – Rückfrage 5]; „Überarbeiten“ eines versendeten Angebots
      entfernt die Zeile in der neuen Version. PDF, Lieferschein, DB und
      Kontrollwerte (Netto 30.245,43 €, KL-Fälle A/B, PV-Fälle) bleiben
      unverändert – die Zeile hatte 0,00 €; betroffene Tests, die die Zeile
      zählen, anpassen und begründen.
- [x] **Mail-Vorlage je Sparte greift nicht (Klima):** Reproduzieren mit
      einem KL-Angebot und einem Außendienstler mit eigener AD-Vorlage:
      Erwartung laut v27-Nachtrag 2 „AD-Vorlage → Sparten-Vorlage →
      Standard“ – die AD-Vorlage (WP-Wortlaut) gewinnt, die Sparten-Vorlage
      KL wird nie gezogen; zusätzlich prüfen, ob `konfigurator_typ` bei allen
      KL-Angeboten gesetzt ist und ob TAIFUN-Einträge (`angebote.sparte`)
      die Sparte liefern. Ursache in der Gesamtübersicht nennen. **Neue
      Reihenfolge:** für **WP** unverändert (AD-Vorlage → WP-Vorlage →
      Standard); für **PV/KL/WB**: Sparten-Vorlage → AD-Vorlage → Standard
      [ANNAHME: AD-Vorlagen sind WP-formuliert; alternativ AD-Vorlage je
      Sparte – Rückfrage 6]. Die Versand-Meldung nennt die Quelle („Sparten-
      Vorlage KL“). Kombi-Versand behält seine Vorlage. Test
      `tests/test_v34_mail_vorlage.py` (KL + AD-Vorlage → KL-Text; WP +
      AD-Vorlage → AD-Text; WB → WB-Vorlage).
- [x] **TAIFUN-Angebots-PDF per Drag & Drop:** (a) im Dialog **„Extern
      erledigt“** (v7; Freitext-/Individuell-Erfassung → externer Eintrag)
      eine Drop-Zone „TAIFUN-Angebot (PDF) hierher ziehen oder auswählen“
      (ein PDF, max. 20 MB, auch per Datei-Dialog); beim Ablegen liest das
      Tool das PDF **vor dem Speichern** aus (`POST /angebote/extern/pdf-
      lesen`, JSON) und belegt vor: **TAIFUN-Angebotsnummer** (Muster
      `AN\d{6}` hinter „ANGEBOT - Nr.:“), **Datum** („Datum : TT.MM.JJJJ“ der
      ersten Seite), **Endbetrag brutto** (Zeile „Gesamt-Betrag € x.xxx,xx“;
      bei „= Endbetrag“ dieser Wert), **Sparte** [ANNAHME: aus Schlagwörtern
      Wallbox/Wärmepumpe/Klimaanlage/Photovoltaik der ersten Seite, nur als
      Vorschlag]; jedes vorbelegte Feld trägt den Hinweis „aus PDF gelesen –
      bitte prüfen“, nicht Erkanntes bleibt leer; das PDF wird mit dem
      Eintrag gespeichert (bestehendes `pdf`-Feld des externen Eintrags,
      v10) und in die Galerie „Allgemein“ gelegt (wie v18). (b) **Am
      TAIFUN-Eintrag** (Vorgangsakte und Angebotsliste): die Drop-Zone
      ersetzt den bisherigen Datei-Knopf; erneutes Ablegen ersetzt das PDF
      (Sicherheitsabfrage) und bietet an, Nummer/Datum/Endbetrag aus dem
      neuen PDF zu übernehmen (Häkchen je Feld). (c) Textextraktion mit
      `pypdf` (neu in `requirements.txt`; reine Python-Bibliothek, keine
      Systemabhängigkeit) [ANNAHME: pypdf statt pdfplumber]; nur Text,
      keine OCR – gescannte PDFs liefern nichts (Hinweis „Kein Text im PDF
      gefunden“). Drag & Drop nach v30-Tokens, Tastatur-/Datei-Dialog als
      Fallback, mobil nur Datei-Dialog. Test `tests/test_v34_taifun_pdf.py`
      mit einem synthetischen PDF (fpdf2) im TAIFUN-Layout → Nummer, Datum,
      Betrag erkannt; Datei ohne Text → leer; Muster AN261737 nur lokal
      (Kundendaten).
- [x] **USt-Rundung wie TAIFUN** [ANNAHME – Rückfrage 7]: `Angebot.summen()`
      schneidet die USt seit Phase 26 ab (v24-Fall A: 1.238,54 € statt
      TAIFUN 1.238,55 €; WB-Muster AN261737: Abschneiden ergäbe 688,98 €,
      TAIFUN zeigt 688,99 €). Umstellen auf kaufmännische Rundung
      (`ROUND_HALF_UP`) in Summenblock, Editor, Liste, Statistik, monday-
      Deal-Wert und Mail-Platzhaltern; Rabatt-/KfW-Logik unverändert; alle
      Alt-Tests, die um 0,01 € abweichen, anpassen und in der Gesamtübersicht
      auflisten (WP-Kontrollwert 30.245,43 € netto → USt 5.746,63 € bleibt
      gleich). Wenn Andreas Rückfrage 7 verneint: Checkbox streichen.

## Phase 181 – Mobil: Angemeldet bleiben, Diktat, Galerie-Mehrfachupload, Kamera-Serie

- [x] **„Angemeldet bleiben“ am Handy:** Reproduzieren mit Playwright
      (Mobile-Emulation iPhone/Android, Rollen Admin, Innendienst,
      Außendienst, Montage) und mit dem Login-Protokoll vom Server
      (Benutzer Andreas, Gerät Handy). Hypothesen prüfen und Ursache in der
      Gesamtübersicht nennen: (1) das Häkchen ist seit v27-Nachtrag 2 **nur
      für Außendienst/Montage sichtbar** (`MOBILE_ROLLEN`) – Admin/
      Innendienst bekommen am Handy immer 12 h; (2) Cookie ohne `max_age`/
      `expires` (Browser verwirft es beim Schließen); (3) `Secure`-Flag
      trotz http; (4) Cookie wird bei jedem Request neu gesetzt und dabei
      auf 12 h verkürzt; (5) PWA-Standalone (Home-Bildschirm) hat einen
      eigenen Cookie-Speicher – ein Login in Safari gilt dort nicht; (6)
      `benutzer.sitzungszaehler` wird durch PIN-Wechsel/„Alle Sitzungen
      beenden“/Benutzer-Speichern erhöht. **Soll:** Häkchen „Auf diesem
      Gerät angemeldet bleiben“ für **alle Rollen** auf Mobilgeräten (UA
      enthält Mobile/Android/iPhone/iPad **oder** Breite < 600 px, Prüfung
      serverseitig über UA + Formularfeld), Gültigkeit `sitzung_tage_mobil`
      (30 Tage), Cookie mit `max_age` **und** `expires`, `SameSite=Lax`,
      `HttpOnly`, `Path=/`, `Secure` nur bei `HTTPS_AKTIV`; Verlängerung
      („sliding“) bei jedem Login, nicht bei jedem Request [ANNAHME];
      Büro-Rollen am PC unverändert 12 h. Hinweis unter dem Häkchen: „Als
      App auf dem Home-Bildschirm bitte dort anmelden.“ Test
      `tests/test_v34_login_mobil.py` (Cookie-Attribute je Rolle/Gerät) +
      manuelle Probe mit Andreas’ Handy in `docs/nach-dem-update-v34.md`.
- [x] **Diktierfunktion mobil:** Knopf „Diktieren“ (Mikrofon-Icon aus
      `_symbole.html`) an allen Freitext-Feldern der mobilen Erfassung
      (Freitext-Erfassung, Bemerkungsfragen, Notizen-Chat, Montage-Formulare)
      über ein gemeinsames Makro `diktat_knopf(feld_id)` + `static/diktat.js`
      (Web Speech API, `de-DE`, Zwischenergebnisse, Text wird am Cursor
      angefügt, Stopp per Knopf oder Pause). **Die Browser-Spracherkennung
      läuft nur in einem sicheren Kontext (HTTPS)** – das Tool läuft heute
      über http im VPN; ohne `window.isSecureContext` oder ohne
      `SpeechRecognition` zeigt der Knopf stattdessen den Hinweis „Diktat:
      bitte das Mikrofon Ihrer Handy-Tastatur verwenden“ (iOS/Android-
      Tastaturdiktat funktioniert in jedem Textfeld). Vorbereitung HTTPS:
      `docs/https-intern.md` (Optionen: Zertifikat für eine interne
      Friondo-Subdomain per DNS-Challenge oder interne CA mit Geräteprofil;
      `HTTPS_AKTIV`/`BASIS_URL` aus v27 nutzen) – Entscheidung Andreas/IT,
      nicht Teil dieses Plans.
- [x] **Galerie: mehrere Fotos, verschiedene Ordner, ein Upload** (Vorgangs-
      und Projektakte, Montage-Backend, mobile Erfassung): Datei-Auswahl
      `multiple`; vor dem Hochladen erscheint eine Liste mit Vorschaubild je
      Datei und **Ordner-Dropdown je Datei** (Vorbelegung = der beim Öffnen
      gewählte Ordner bzw. „Sammelbox“; Ordnerliste je Sparte/Objekt wie
      v15/27.09.; Objekt-Ordner aus PLAN_LEAD_V6 liegen noch nicht vor), optional Bemerkung je Datei, „Für alle übernehmen“;
      ein Knopf „n Fotos hochladen“ sendet **einen** Request (`POST
      /vorgaenge/<id>/galerie/upload` erweitert: `dateien[]`, `ordner[]`,
      `bemerkung[]` positionsgleich; Teilerfolg wird je Datei gemeldet).
      Client-seitige Verkleinerung auf max. 2.000 px lange Kante, JPEG 85 %
      (Canvas) vor dem Senden, Original-Dateiname bleibt [ANNAHME: spart
      Datenvolumen im VPN; PDFs unverändert]. Fortschrittsbalken, bei
      Abbruch bleibt die Liste erhalten. Bestehender Einzel-Upload und
      „Einsortieren“ aus der Sammelbox unverändert.
- [x] **Kamera-Serie:** Knopf „Fotos aufnehmen“ öffnet die Kamera
      (`<input type="file" accept="image/*" capture="environment">`); nach
      jedem Foto landet es in der Upload-Liste des Punktes oben (Vorschau,
      Ordner-Dropdown), der Knopf heißt dann „Weiteres Foto“, dazu „n Fotos
      hochladen“ – die Fotos bleiben bis zum Hochladen im Speicher der Seite
      (kein Zwischen-Upload; Hinweis beim Verlassen der Seite mit
      ungesendeten Fotos). Live-Kamera im Browser (`getUserMedia`) ist nicht
      Teil des Plans (braucht ebenfalls HTTPS). Gilt in Vorgangs-/Projektakte,
      Montage-Backend und mobiler Erfassung (auch ohne Auftrag, v15).
      Tests `tests/test_v34_galerie.py` (Mehrfach-Upload mit drei Dateien in
      zwei Ordner, Teilerfolg, Rechte je Rolle unverändert).

## Phase 182 – Tests, Rollout-Vorbereitung, Doku, CLAUDE.md v34

- [x] **Tests gesamt:** neue Dateien `test_wb_v34_import.py`,
      `test_wb_v34_logik.py`, `test_wb_v34.py`, `test_v34_alternativ.py`,
      `test_v34_elektro_pv.py`, `test_v34_kombi.py`, `test_v34_auslegung.py`,
      `test_v34_mail_vorlage.py`, `test_v34_taifun_pdf.py`,
      `test_v34_login_mobil.py`, `test_v34_galerie.py`; angepasste Alt-Tests
      (Auslegungszeile, Kombi-Status, Mail-Reihenfolge, ggf. USt-Rundung,
      WB-Weiche) mit Begründung; `pytest tests -q` komplett grün,
      Wächter-AST v27 und Token-Wächter v30 grün; Außendienst-Sichtprüfung
      (kein EK/DB in WB-Angebot, Alternativ-Badge, Elektro-Knopf unsichtbar).
- [x] **Rollout-Vorbereitung** nach Grundregel: Server-DB-Kopie nach
      diagnose\, migrate.py zweimal (zweiter Lauf ohne Änderungen; additiv:
      `angebote.wb_json`, `angebote.auslegung_text`, Positions-Spalten
      `uebernommen_von_angebot_id/_position_id`, WB-Artikel-Import, Seeds
      `seed_wb`, Textblöcke, Parameter, Migration Auslegungszeile in
      Entwürfen mit Protokoll), Rückweg-Probe v33-Code auf v34-DB,
      Voll-Crawl (admin, innendienst, aussendienst, montage, projektierung)
      hell/dunkel, Abnahmeskript, Smoke, Lasttest Profil `normal` (Galerie-
      Mehrfachupload und PDF-Lesen im Modell), Screenshots (Alternativ-
      Kasten im PDF, Kombi-Kasten, Galerie-Upload-Liste mobil, Login mobil)
      nach `docs/design-v34/`, nur Demo-Daten.
- [x] **Doku:** CLAUDE.md Abschnitt „Neu in v34 – Wallbox-Konfigurator,
      Angebotstool-Feedback 15.10., Mobil (abgestimmt 15.10.2026)“ nach „Neu
      in v33“, Zuordnungstabelle `| v34 | PLAN_V21.md | 178–182 |`,
      Titelzeile „(v34)“; in „Neu in v8“ (WB vorerst immer Freitext), „v10“
      (Kombi-Versand nur bei Versand vorbereitet), „v11/v13/v16/v24“
      (Auslegungszeile im Angebot), „v27-Nachtrag 2“ (Vorlagen-Reihenfolge)
      die Sätze als *überholt – siehe v34* markieren; „Zentrale Dateien“ um
      `Artikel-Preislisten/Wallbox/` ergänzen; „Fachliche Regeln“ um
      „Elektroarbeiten ins PV-Angebot“ und „Alternativ-Darstellung“.
      `ANGEBOTSTEXTE.md` Abschnitt 10 Wallbox; `docs/nach-dem-update-v34.md`
      (Team: WB-Katalog statt Freitext, Elektro-Knopf, Kombi-Kasten, Drop-Zone,
      Diktat-Hinweis, Galerie-Serie; Admin: Wallbox-Preisliste pflegen,
      Mennekes-Datenblatt ablegen, Login-Probe mit Handy, USt-Rundung);
      `docs/betrieb.md` (pypdf, Galerie-Mehrfachupload); `docs/updates.md`;
      `config.VERSION = "v34"`.
- [x] **Gesamtübersicht am Ende:** erledigte Phasen, Testergebnisse
      (Gesamtzahl), angepasste Alt-Tests mit Begründung, Preiskonflikt
      WB003, Ursache Klima-Mailvorlage, Ursache „Angemeldet bleiben“,
      Liste der entfernten Auslegungszeilen (Anzahl Entwürfe), [ANNAHME]-
      Liste, Rückfragen gebündelt. **Ein Commit** „v34: Wallbox-Konfigurator,
      Alternativ/Elektro ins PV, Kombi-Versand, Auslegungszeile, Mail je
      Sparte, TAIFUN-PDF, Mobil (PLAN_V21, Phasen 178-182)“; **kein push vor
      Freigabe**.

## Kontrollwerte für die Abnahme

- WB-Katalog-Erfassung „AMTRON 4You 310, 10 m“ → Angebot mit drei
  Positionen, Netto 2.235,70 €, USt 424,78 €, Gesamt 2.660,48 €, Vortext
  „Ihre individuelle Wallbox zum Festpreis“ mit Absatz „Komplettpaket
  Wallbox inkl. Montage“, Nachtext ohne Zahlungsoptionen, mit Vollmacht,
  Anhang Mennekes-Datenblatt (sobald Datei vorhanden), Protokoll-Seite
  „Auslegung“ mit Leitungslänge; keine Auslegungs-Position.
- „AMTRON 4You 560, 25 m“ → fünf Positionen, Meter-Positionen je 15 m,
  Netto 4.132,85 €, Gesamt 4.918,09 €.
- Alte WB-Freitext-Erfassung → unverändert Individuell/TAIFUN; neue
  WB-Erfassung zeigt die Weiche Katalog | Freitext.
- WP-Angebot mit Alternativ-Positionen → PDF mit farbigem Hinweiskasten und
  „im PV-Angebot“ in der G-Preis-Spalte; Editor-Badge mit Link.
- Vorgang mit WP-Entwurf (Block Elektroarbeiten, netto 2.400,00 €) und
  PV-Entwurf → Knopf „Elektroarbeiten ins PV-Angebot“ → WP: Positionen
  Alternativ, Netto um 2.400,00 € niedriger; PV: neue Gruppe mit denselben
  Positionen, Netto um 2.400,00 € höher, USt 0 %; Meldung nennt
  Kundenersparnis 456,00 €; „Zurückholen“ stellt beide her; Kombi-Versand
  ohne Doppel-Warnung.
- Vorgang mit WP-Entwurf, PV „Versand vorbereitet“, TAIFUN-Eintrag mit PDF
  → Kasten „Gemeinsam versenden“ zeigt drei Häkchen; Auswahl aller drei →
  WP automatisch „Versand vorbereitet“, eine Mail mit drei PDFs.
- KL-Angebot, Außendienstler mit AD-Vorlage → Versand-Entwurf nutzt
  „Sparten-Vorlage KL“ (Meldung); WP-Angebot desselben AD → AD-Vorlage.
- „Extern erledigt“ mit TAIFUN-PDF im Muster-Layout → Nummer AN…, Datum
  und Gesamt-Betrag vorbelegt mit Hinweis „aus PDF gelesen“; gescanntes PDF
  → Felder leer, Hinweis „Kein Text im PDF gefunden“.
- Admin am Handy (390 px): Häkchen „Angemeldet bleiben“ sichtbar; nach
  Login Cookie mit `Max-Age=2592000` und `Expires`, ohne `Secure`; nach
  Browser-Neustart weiterhin angemeldet; am PC 12 h.
- Mobile Erfassung, Freitext-Feld: Knopf „Diktieren“ über http zeigt den
  Tastatur-Hinweis; unter HTTPS (lokaler Test mit selbstsigniertem
  Zertifikat) startet die Erkennung.
- Galerie mobil: drei Fotos nacheinander mit der Kamera, Ordner „Zählerschrank“,
  „Zählerschrank“, „Aufstellort“ → ein Upload, drei Dateien in zwei Ordnern,
  jede unter 2.000 px lange Kante; Sammelbox leer.
- `pytest tests -q` grün, Abnahmeskript grün, Voll-Crawl ohne Absturz,
  Lasttest normal innerhalb der Zielwerte, 0 „database is locked“.

## Zulieferungen / bewusst offen

- **Dateien (Andreas, vor der Übergabe):** `Wallbox Artikel Excel.xlsx` und
  `Extraleitung.xlsx` nach `Artikel-Preislisten\Wallbox\` (enthalten EK –
  nur Projektordner/Git wie die übrigen Preislisten, nie Projektwissen);
  Beispielangebot AN261737 als `Artikel-Preislisten\Wallbox\
  Beispielangebot.pdf` (Kundendaten – `.gitignore`-Eintrag, Phase 178);
  Mennekes-Datenblatt AMTRON 4You (ein PDF für beide Modelle oder zwei) nach
  `anlagen\`.
- **Rückfrage 1 – Preis Anschlussvorbereitung:** 1.297,20 € (Wallbox
  Artikel Excel, Muster AN261737) oder 1.597,20 € (Extraleitung.xlsx)? Der
  Plan rechnet mit 1.297,20 €.
- **Rückfrage 2 – Montagekanal:** immer zusammen mit der Mehrlänge
  (Vorschlag) oder eigene Ja/Nein-Frage „Montagekanal in Designausführung?“
- **Rückfrage 3 – Zahlungsklausel WB:** v30-Standard („50 % am Montagetag
  …“, wie WP/KL) oder TAIFUN-Muster („Anzahlung 50 % spätestens 14 Tage vor
  Arbeitsbeginn, Rest mit Schlussrechnung“)? Vorschlag: v30-Standard,
  damit alle Sparten gleich sind.
- **Rückfrage 4 – Vollmacht bei WB:** immer (wie im Muster, wegen
  Netzanmeldung §14a – Vorschlag) oder nie?
- **Rückfrage 5 – Auslegungszeile im Bestand:** aus allen Entwürfen per
  Migration entfernen (Vorschlag) oder nur bei neuen Angeboten?
- **Rückfrage 6 – Mail-Vorlage:** Sparten-Vorlage vor AD-Vorlage bei
  PV/KL/WB (Vorschlag) oder AD-Vorlagen je Sparte (mehr Pflege)?
- **Rückfrage 7 – USt-Rundung:** auf kaufmännisch (wie TAIFUN) umstellen –
  ja (Vorschlag) oder beim Abschneiden bleiben?
- **Entscheidung Andreas/IT – HTTPS im VPN** (`docs/https-intern.md`):
  Voraussetzung für Browser-Diktat und Live-Kamera; bis dahin Tastatur-
  Diktat und Foto-Serie über die Kamera-App.
- Bestätigung der [ANNAHME]-Stellen: keine Vorbelegung WB01; drei Blöcke
  im Angebotsaufbau WB; ganze Meter bei der Mehrlänge; Warnung ab 100 m;
  keine AMPEL-Gründe bei WB; kein Fit for Future bei WB; Nachtexte
  Enni/SWD/Sparkasse DU als Kopie des Standards; Sparte aus dem PDF nur als
  Vorschlag; `pypdf`; Elektro-Positionen = Block Elektroarbeiten +
  gewerkeübergreifende Artikel; Cookie-Verlängerung nur beim Login;
  Bildverkleinerung 2.000 px; Versionsnummer v34 und Phasen 178–182 (geprüft, siehe Vorspann).
- Nicht Teil dieses Plans: Cloover-Finanzierung im Nachtext (eigener Plan),
  Dachbelegungstool, Live-Kamera im Browser, OCR für gescannte TAIFUN-PDFs,
  Wallbox-Varianten anderer Hersteller (Erweiterung über die Blätter
  WB-Artikel/Aktionen WB ohne Codeänderung vorgesehen).

## Nachtrag 15.10.2026 – Wallbox-Logik (Antwort Andreas, ersetzt Fragen/Aktionen/Artikel der Phasen 178/179)

Zulieferung am 15.10.2026 ~17:00: `WB Angebot Excel 1.xlsx` (TAIFUN-Export, Blatt „Tabelle 1“, Spalten
GUID · Position · Menge · Einheit · Beschreibung · E-Preis · G-Preis · Einkaufspreis Material, Positionen
001–008 + Textzeile „Komplettpaket Wallbox inkl. Montage“) und das Musterangebot AN251131 (PDF mit
Kundendaten). Beide lagen im Projektordner-Stamm und wurden nach `Artikel-Preislisten/Wallbox/` verschoben
(`WB Angebot Excel 1.xlsx` – Git wie die übrigen Preislisten, nie Projektwissen; `Beispielangebot.pdf` –
gitignored). **`Extraleitung.xlsx` entfällt** – der Montagekanal (47,00 €/m) kommt nicht mehr vor; die
Mehrlänge besteht nur noch aus der Leitungsposition.

**Positionen der Datei (VK netto):** 001 Mennekes AMTRON 4You 310 (938,50 € Stück) · 002 AMTRON 4You 560
(1.390,55 € Stück) · 003 Anschlussvorbereitung Ladestation (1.297,20 € psl. – bestätigt R1) · 004 Zusätzliche
erforderte Bohrung/Durchbrüche (169,00 € Stück) · 005 Netzanmeldung beim EVU nach §14a EnWG (0,00 € psl.) ·
006 lfd. Meter NYY-J 5x10mm² … (49,34 €/m) · 007 Erdarbeiten zwischen Wallbox bis zur Hauseinführung …
(123,50 €/m) · 008 Fundament und Standsäule für Wallbox MENNEKES AMTRON 4You Serie (1.020,00 €; Einheit im
Export „m“ – im Tool 1 × psl. [ANNAHME, Rückfrage]). Musterangebot: Netto 3.626,25 €, USt 688,99 €, Gesamt
4.315,24 € (kaufmännisch gerundet – bestätigt R7; Zahlungsklausel im Muster „Anzahlung 50 % spätestens
14 Tage vor Arbeitsbeginn“ – R3 bleibt v30-Standard, Rückfrage offen).

**Fragen WB (Erfassungsbogen, Andreas 15.10.2026):**
1. **WB01** „Welche Wallbox?“ – Auswahl „Mennekes AMTRON 4You 310 – 11 kW, 7,5 m Ladekabel“ |
   „Mennekes AMTRON 4You 560 – 11 kW, 7,5 m Ladekabel, MID-Zähler, App, OCPP“ (Pflicht, keine Vorbelegung).
2. **WB02** „Wie viel Meter Leitungsverlegung erforderlich?“ – Zahl (Pflicht, Vorbelegung 10, Dezimalkomma);
   10 m sind in der Anschlussvorbereitung enthalten, jeder weitere Meter → Position „lfd. meter NYY-J
   5x10mm² …“ (WB005).
3. **WB03** „Erdarbeiten erforderlich?“ – Ja | Nein (Pflicht, Vorbelegung Nein [ANNAHME]); bei Ja
   **WB04** „Erdarbeiten: wie viele Meter?“ (Zahl, nur wenn WB03 = Ja, dann Pflicht) → Anzahl × Position
   „Erdarbeiten zwischen Wallbox bis zur Hauseinführung …“ (WB006; Andreas schrieb „zwischen Modulfeld“ –
   es gilt der Text der Excel).
4. **WB05** „Wandmontage oder Säule?“ – Auswahl „Wandmontage“ | „Säule“ (Pflicht, Vorbelegung Wandmontage
   [ANNAHME]); Wandmontage = keine Position, Säule → Position „Fundament und Standsäule für Wallbox …“
   (WB007 × 1).
5. **WB07** „Wie viele Durchbrüche erforderlich?“ – Zahl (Pflicht, Vorbelegung 2 [ANNAHME]); 2 Durchbrüche
   sind in der Anschlussvorbereitung enthalten, jeder weitere → Position „Zusätzliche erforderte Bohrung/
   Durchbrüche …“ (WB008 × (WB07 − 2)) – Antwort Andreas 15.10.2026, zweite Runde.
6. **WB08** „Bemerkungen zur Ausführung (optional)“ – Freitext, nur Protokoll (bisher WB03).
   Einschätzung S01/S02 wie bei allen Katalog-Sparten. Erdarbeiten (WB03/WB04) werden unabhängig von
   Wandmontage/Säule abgefragt (Andreas: „Es können auch Erdarbeiten bei Wandmontage anfallen“).
Immer im Angebot: Anschlussvorbereitung (WB003) und Netzanmeldung (WB004).

**Blatt „WB-Artikel“** (Anker `Datei` = „WB Angebot Excel 1“ + Position + Beschreibungsanfang):
WB001 = 001, WB002 = 002, WB003 = 003, WB004 = 005, WB005 = 006, WB006 = 007 (Erdarbeiten, m),
WB007 = 008 (Fundament/Standsäule, psl.), WB008 = 004 (Bohrung/Durchbrüche, Stück). Der alte WB006
(Montagekanal) entfällt ersatzlos.

**Blatt „Aktionen WB“:** `WB01 = … 310 → WB001 × 1`; `WB01 = … 560 → WB002 × 1`; `immer → WB003 × 1`;
`immer → WB004 × 1`; `WB02 > 10 → WB005 × Mehrlänge` (kaufmännisch ganze Meter, nie unter 0);
`WB03 = Ja → WB006 × WB04` (Meter aus WB04, kaufmännisch ganze Meter [ANNAHME]; 0 oder leer →
Absende-Meldung „Erdarbeiten: Meter fehlen“); `WB05 = Säule → WB007 × 1`; `WB07 > 2 → WB008 × (WB07 − 2)` (ganze Stück, nie unter 0).
**Blatt „Angebotsaufbau WB“:** Block 1 „Wallbox“ (WB001/WB002), Block 2 „Installation und Anschluss“
(WB003, WB008, WB005, WB006, WB007), Block 3 „Netzanmeldung“ (WB004). **Blatt „WB-Parameter“:**
`leitung_inklusive_m` 10, `meterposition_leitung` WB005, `erdarbeiten_position` WB006,
`fundament_position` WB007, `wallbox_standard` leer; `meterposition_kanal` entfällt.
**Vortext:** der Absatz „Komplettpaket Wallbox inkl. Montage“ wörtlich aus der Textzeile der Excel
(„?“-Platzhalter entfernt) – `seed_wb` übernimmt ihn aus der Datei, wenn sie vorliegt (sonst Entwurf).
**Import:** eine Pflichtdatei (`WB Angebot Excel 1`); eine zweite Datei ist optional (Konflikt-Logik bleibt
für den Fall, dass eine weitere Liste dieselbe WB-Nr. mit anderem Preis führt).

**Kontrollfälle neu** (`tests/test_wb_v34.py`): A 310, 10 m, Erdarbeiten Nein, Wandmontage → WB001 · WB003 ·
WB004, Netto 2.235,70 €, USt 424,78 €, Gesamt 2.660,48 €; B 560, 25 m, Erdarbeiten Ja 8 m, Säule → WB002 ·
WB003 · WB005 × 15 (740,10 €) · WB006 × 8 (988,00 €) · WB007 × 1 (1.020,00 €) · WB004, Netto **5.435,85 €**,
USt **1.032,81 €**, Gesamt **6.468,66 €**; B2 = B + 4 Durchbrüche (WB008 × 2 = 338,00 €) → Netto **5.773,85 €**,
USt **1.097,03 €**, Gesamt **6.870,88 €**; C 560, 8 m, Nein, Wandmontage → 2.687,75 / 510,67 / 3.198,42 €;
D 310, „12,4“ → Mehrlänge 2 m → Netto 2.235,70 + 2 × 49,34 = **2.334,38 €**; E Leitungslänge leer →
„Leitungslänge fehlt oder ist keine Zahl“; F Freitext-Weiche → TAIFUN; G Erdarbeiten Ja ohne Meter →
„Erdarbeiten: Meter fehlen“; Import-Kontrolle: Summe der Preise 001 + 002 + 003 + 005 = 3.626,25 € =
Netto des Musterangebots AN251131.

**Rückfragen aus dem Nachtrag – Antworten Andreas 15.10.2026 (zweite Runde):** (a) Bohrung/Durchbrüche
bekommt die Frage WB07 (2 Stück enthalten); (b) Fundament/Standsäule 1 × pauschal bestätigt; (c) Montagekanal
entfällt; (d) Erdarbeiten auch bei Wandmontage möglich – Frage immer, Vorbelegungen Nein/Wandmontage
[ANNAHME]; (e) Zahlungsklausel: der v30-Standardtext ist bereits wörtlich die Muster-Klausel („Anzahlung 50 %
spätestens 14 Tage vor Arbeitsbeginn …“) – Rückfrage 3 damit erledigt.
