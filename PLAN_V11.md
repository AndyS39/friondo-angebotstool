# Umsetzungsplan v11 – Team-Feedback: Bugfixes, Kalkulation, Konfigurator-Feinschliff

Voraussetzung: Phasen 0–63 umgesetzt, v10 läuft auf dem Server. CLAUDE.md und
konfigurator_logik_v5.xlsx sind Live-Master – direkt ändern, nicht ersetzen.
Je Phase: Ansatz erläutern → umsetzen → testen → abhaken → committen.
Schema-Änderungen in migrate.py (idempotent). Nur EIN Plan gleichzeitig in
Umsetzung (Absprache mit PLAN_LEAD/PLAN_PROJ).

VORAB-CHECK: Zwei Punkte der Team-Liste waren bereits Teil von PLAN_V10 –
Phase 59 (Absenden-Button bei Erfassung ohne Lead) und Phase 63 (Erdleitung
in den Fundament-Block). Zuerst prüfen, ob diese Checkboxen wirklich
umgesetzt und ausgerollt sind: falls ja → als Regression behandeln und
Ursache suchen; falls nein → im Rahmen von Phase 64/65 nachziehen.

ZULIEFERUNGEN (blockieren einzelne Checkboxen, nicht den Start):
1. Neue Leistungsklassen-Grenzen für monoenergetische Auslegung
   (Abstimmung Andreas/Janni) – bis dahin bleiben die aktuellen Grenzen.
2. Aktualisierte VK-Preisliste nach Rücksprache Janni (TAIFUN-Export)
   → Import über die bestehende Preislisten-Funktion.
3. Broschüre „Bosch CS8800iAW" als PDF in anlagen/.
4. TAIFUN-Muster in den Projektordner: Wortlaut der Heizlast-/
   Auslegungsangabe im Angebot sowie der Text von TAIFUN-Position 124
   („Vermerk Heizungsumverlegung").

## Phase 64 – Kritische Bugfixes (Kalkulation, Status, Bedienung)
- [x] PUFFER-DOPPELBERECHNUNG (AN-C-261082): Gegen die TAIFUN-Preisliste
      klären, ob die Pakete 045–054 den 50-l-Puffer im Paketpreis
      enthalten (laut Team: ja, zumindest AWM). Dann Regel: Pufferwahl
      „50 l" bei den 3800er-Klassen → KEINE Zusatzposition (Pos. 002
      entfällt, Puffer ist Paketbestandteil); größere Puffer unverändert
      als Zusatz. Doppler-Schutzprüfung erweitern, Test mit der
      Konstellation aus AN-C-261082
- [x] Pakettexte AWM + AWE (AN-C-261096) gegen TAIFUN kontrollieren und
      korrigieren – Pufferinhalt darf textlich nicht doppelt/irreführend
      erscheinen; Texte in der Preisliste/Artikelverwaltung anpassen
- [x] CS8800 FEHLT TROTZ KLASSE 15 (AN-C-261127): Erfassung
      reproduzieren, Ursache beheben. Verdacht: Konstellation
      Solarthermie-Übernahme (AWE-Zwang-Regel aus v9 kennt bei Klasse 15
      keine Paket-Position, sondern Komponenten) oder Klassenermittlung
      über einen der beiden Pfade. Automatischen Test ergänzen
- [x] CS8800-Reihenfolge: Außeneinheit (030/031) auf Position 1,
      Inneneinheit (055/056) auf Position 2 im Block 1, danach
      Puffer/Warmwasser
- [x] Drag & Drop: Blocküberschriften vom Verschieben entkoppeln – die
      Überschrift bleibt immer vor der ersten Position ihres Blocks,
      auch wenn ein Artikel auf Position 1 gezogen wird (AN-C-261127)
- [x] Versand-Erkennung robuster (AN-C-261083 blieb auf „Versand
      vorbereitet", obwohl die Mail den Kunden erreichte): Erkennungslauf
      protokollieren und Abgleich verbessern; zusätzlich manueller
      Button „Als versendet markieren" (ID, mit Protokolleintrag und
      normaler monday-Rückspielung) als Fallback
- [x] Rabatt entfernen: Eingabe 0 (oder Leeren des Feldes) setzt den
      Rabatt zurück statt „ungültiger Wert"
- [x] Externe/individuelle Angebotseinträge können auf „Abgelehnt"
      gesetzt werden (inkl. Pflichtdialog Ablehnungsgrund und
      monday-Summen-Neuberechnung) – Statuswechsel vollständig wie bei
      Tool-Angeboten
- [x] Erfassung ohne Lead (Menü Angebote → Neuer Vorgang): Absenden-/
      Abschluss-Button am Ende des Bogens vorhanden und identischer
      Ablauf wie bei Lead-Erfassungen (siehe VORAB-CHECK)

## Phase 65 – Logik-Excel: Konfigurator-Erweiterungen
- [ ] FLÄCHEN-AUSLEGUNG OHNE VERBRAUCH: A03 erhält die Alternative
      „Verbrauch unbekannt". Dann Folgefragen: „Beheizte Wohnfläche in
      m²" (Zahl) und „Gebäudestandard" (saniert – 40 W/m² |
      Altbau – 60 W/m² | Altbau unsaniert – 70 W/m²). Heizlast =
      Fläche × Faktor ÷ 1000 (kW), danach greift die bestehende
      Heizlast-Klassenlogik (inkl. 15-kW-Klasse und Ampel). Protokoll
      und Angebots-Auslegungszeile weisen die Herleitung aus
      („Auslegung über Fläche: 150 m² × 60 W/m² = 9,0 kW")
- [ ] Heizlast-/Auslegungstext im Angebot: Zeile im Block 1 nach dem
      TAIFUN-Muster (Zulieferung 4) – bei Verbrauchs-Auslegung mit
      kWh-Wert, bei Heizlast/Fläche mit der Herleitung
- [ ] Fassadenleitung bei Dachaufstellung: Wird als Aufstellort der
      Außeneinheit eine Dach-Variante gewählt (Garagendach etc.),
      erscheint die Fassadenleitungs-Abfrage analog zur bestehenden
      OG-Logik (Pos. 134, ggf. mit Meterangabe wie bisher)
- [ ] Mobiler Kran: automatische EP-Position entfernen; stattdessen bei
      Dachaufstellung neue Frage „Mobiler Kran erforderlich?" (Ja |
      Nein), Ja → Kran-Position als EP ins Angebot
      (Entscheidung siehe Chat – Veto möglich)
- [ ] Öltank-Entsorgung „ab 9.000 l": Folgefrage „Tatsächliche
      Tankgröße in Litern" (Zahl) – landet im Protokoll und als
      Zusatz im Positionstext der Entsorgung
- [ ] DACHZENTRALE → KG, ANSCHLÜSSE IN ANDERER ETAGE (Kette
      überarbeiten): Bei Ziel Kellergeschoss zusätzlich abfragen, in
      welcher Etage die Anschlüsse (Heizung/Warmwasser) liegen.
      Gleiche Etage (KG) → Pauschale 141 wie bisher. Andere Etage
      (z. B. EG) → NICHT 141, sondern Meterabfragen getrennt:
      „Rohrleitung Heizung in m" und „Rohrleitung Warmwasser in m"
      → Artikel 139/140 × Meter (Zuordnung der beiden Artikel zu
      Heizung/WW anhand der Artikeltexte prüfen und dokumentieren)
- [ ] Vermerk Heizungsumverlegung als Position: TAIFUN-Artikel 124
      (0,00 €, Text laut Zulieferung 4) wird bei jeder
      KG-Verlegung der Dachzentrale im Montage-/Demontage-Block
      ausgegeben. Der v9-Vermerke-Blatt-Eintrag (Textabsatz) wird auf
      diese Positionsausgabe umgestellt – EINE Quelle, kein Doppel
- [ ] Erdleitung (Pos. 102) in Block 6 „Aufstellung der Außeneinheit
      und Hauseinführung" (siehe VORAB-CHECK; Fassadenleitung bleibt
      in Block 2)
- [ ] Blocküberschrift für die Elektroarbeiten ergänzen (Block 7),
      Wortlaut analog TAIFUN-Muster, sonst „Elektroarbeiten"
- [ ] Leistungsklassen monoenergetisch: NEUE GRENZEN gemäß
      Zulieferung 1 in Paketmatrix (kWh- und Heizlast-Spalte)
      eintragen; Kontroll-Szenarien danach neu abnehmen
      [WARTET auf Zulieferung – Rest von Phase 65 nicht blockieren]

## Phase 66 – Editor & Angebote
- [ ] Freitextpositionen: Bezeichnung optional (leer erlaubt, PDF zeigt
      dann nur die Beschreibung); zusätzliches EK-Feld (netto) für die
      korrekte DB-Berechnung
- [ ] Abweichende Lieferanschrift (optional, z. B. Contracting):
      Feld in Erfassung und Editor, eigene Zeile im PDF unterhalb von
      Rechnungs-/Ausführungsanschrift
- [ ] Angebot kopieren → anderem Kunden zuordnen: Aktion „Für anderen
      Kunden kopieren" (bestehenden Kunden wählen oder neu anlegen);
      erzeugt neuen Vorgang + neues Angebot (neue Nummer, Entwurf) mit
      allen Positionen, Texten und Einstellungen; Anrede/Adressen vom
      Zielkunden; KfW-Eingaben werden übernommen und mit fachlichem
      Hinweis „Förderdaten prüfen (kopiert)" markiert; Kennzeichen
      „Kopie von AN-…" in der Detailansicht
- [ ] AD-Statuswechsel: Außendienst kann eigene Angebote auf
      Angenommen / Abgelehnt / zurück auf Versendet („Offen") setzen –
      Abgelehnt mit Pflichtdialog Ablehnungsgrund; jeder Wechsel wird
      im Notizen-Chat des Vorgangs protokolliert; monday-Summenlogik
      und Statistik greifen wie beim ID
- [ ] Neuer Zusatzartikel „Elektroarbeiten – im PV-Angebot enthalten"
      (pauschal, 0,00 €/0,00 €), beim Einfügen automatisch mit
      Alternativ-Kennzeichen und Verknüpfungs-Freitext „PV-Angebot"
      vorbelegt – für den schnellen Griff im Kombi-Fall
      (Klärung siehe Chat)

## Phase 67 – Profile, Anhänge & Preise
- [ ] Anhänge profilabhängig: Blatt „Anhänge" erhält eine Spalte
      „Nicht bei Profil" (kommagetrennt). Eintragen: „Broschüre
      Ratenkauf.pdf" → nicht bei Enni, SWD; „Friondo SpotDynamic.pdf"
      → nicht bei Enni, SWD. Engine wertet die Spalte beim
      Zusammenstellen der Mail-Anhänge aus (auch im Kombi-Versand)
- [ ] CS8800-Broschüre: Zeile im Blatt „Anhänge" – „Bosch
      CS8800iAW.pdf" wenn Pos. 030 oder 031 im Angebot (Datei aus
      Zulieferung 3; solange sie fehlt, greift die bestehende
      „Datei fehlt"-Warnung)
- [ ] VK-Anpassung: nach Zulieferung 2 neue Preisliste importieren,
      Import-Protokoll prüfen (Anzahl geänderter Preise), ein
      Kontroll-Angebot vorher/nachher vergleichen

## Phase 68 – Abnahme & Rollout
- [ ] Regressionstests: alle Kontroll-Szenarien (KG-, DG-, Rabatt-Fall,
      A13, Heizlast, B1–B4, Doppler-Schutz 065/067) grün
- [ ] Neue Tests: AWM 6 kW + 50-l-Puffer → keine Pos. 002; 8800er-
      Angebot → 030/031 Pos. 1, 055/056 Pos. 2, Broschüren-Regel;
      Flächen-Auslegung 150 m² × 60 W/m² = 9,0 kW → 7-kW-Klasse;
      Dachzentrale KG + Anschlüsse EG → 139/140 × m statt 141 +
      Pos. 124; Enni-Mail ohne Ratenkauf/SpotDynamic; Rabatt setzen
      und mit 0 entfernen; externer Eintrag → Abgelehnt mit Grund;
      AD-Statuswechsel mit Protokoll-Notiz; Kopie zu anderem Kunden
      (neuer Vorgang, Hinweis Förderdaten)
- [ ] CLAUDE.md: Kopf auf „(v11)"; Abschnitt einfügen:

      ## Neu in v11 (abgestimmt 23.09.2026)
      - Kalkulation: 50-l-Puffer ist Bestandteil der 3800er-Pakete –
        keine Zusatzposition mehr bei Pufferwahl 50 l; Pakettexte
        bereinigt. CS8800: Außen-/Inneneinheit stehen auf Position 1+2,
        eigene Broschüren-Regel, Fehlerfall „Klasse 15 ohne Paket"
        behoben.
      - Konfigurator: Auslegung ohne Verbrauch über Fläche ×
        Gebäudestandard (40/60/70 W/m²) mit ausgewiesener Herleitung;
        Auslegungszeile im Angebot nach TAIFUN-Muster; Fassadenleitung
        auch bei Dachaufstellung; Kran-Frage statt EP-Automatik;
        Tankgrößen-Nachfrage ab 9.000 l; Dachzentrale-KG-Kette mit
        Etagen-/Meterlogik (139/140) und Vermerk-Position 124;
        Erdleitung im Fundament-Block; Überschrift Elektroarbeiten.
      - Editor: Freitextpositionen ohne Bezeichnung und mit EK-Feld;
        abweichende Lieferanschrift; „Für anderen Kunden kopieren"
        (neuer Vorgang, Hinweis Förderdaten prüfen).
      - Rollen: AD setzt eigene Angebote auf Angenommen/Abgelehnt/
        Offen (Grund-Pflicht, Notiz-Protokoll). Externe Einträge
        vollständig ablehnbar.
      - Versand: Anhänge-Regeln profilabhängig (Enni/SWD ohne
        Ratenkauf/SpotDynamic); Versand-Erkennung robuster + manueller
        „Als versendet markieren"-Fallback; Rabatt mit 0 entfernbar.
      - Offen bis Zulieferung: monoenergetische Klassengrenzen,
        VK-Preisliste (Janni).

- [ ] docs/nach-dem-update-v11.md: Team-Hinweise (AD-Statuswechsel,
      Kopier-Funktion, Kran-Frage, „Als versendet markieren" nur als
      Fallback), Erinnerung Zulieferungen 1–4 nachziehen
- [ ] git push → Rollout per update.bat → Checkliste abarbeiten
