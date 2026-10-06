# Nach dem Update v26 (PLAN_PROJ_V5) – Heizreport-Anbindung & Pilot-Nebensachen

Dieses Update bindet Heizreport über die öffentliche Kunden-API v2 an
(Projektierung, Aufgabe „Heizlastberechnung liegt vor“), stellt das Montageteam
am Benutzer auf ein Dropdown um und gliedert die Parametrierung neu. Projektierung
läuft weiter im eingestellten `freigabe_modus` (Pilot); Angebotstool,
Lead-Management, monday-Sync und PDF-Erzeugung der Angebote sind unverändert.

## Echtlauf-Checkliste Heizreport (Andreas, ohne Netzaufrufe im Test)

1. **Token eintragen:** Parametrierung → Projektierung → Heizreport → Zugang:
   Modus „Kunden-API v2“, Token aus dem Pro-Bereich des Heizreport-Kontos,
   Speichern, dann „Verbindung testen“ – erwartete Meldung „Verbindung OK ·
   API-Version 2.4.0 · <n> eigene Projekte (Gruppen: …)“. Ohne Token: „Heizreport
   erreichbar, aber Token abgelehnt (HTTP 401)“.
2. **Erstes Projekt anlegen** (nach Freigabe – Projektanlage braucht eine aktive
   Jahres- oder Bildungslizenz): an einem Demo-Gewerk in der Projektakte, Aufgabe
   „Heizlastberechnung liegt vor“ → „Heizreport-Projekt anlegen“. Danach steht der
   Schlüssel (9 Buchstaben) an der Aufgabe, der Verlauf nennt die vorbelegten Felder.
3. **Kennzahlen ermitteln** mit `scripts/heizreport_kennzahlen.py` am Testprojekt
   (Ablauf in docs/heizreport-api.md, Abschnitt 3) und als JSON unter
   Parametrierung → Heizreport → Kennzahlen eintragen; bis dahin werden
   Heizungsart/Altersklasse/Trinkwasser/Solarart nicht gesendet (Klartext steht in
   `bemerkungen`).
4. **Referenzprojekt prüfen:** am fertig berechneten Referenzprojekt (Schlüssel von
   Hand eintragen, falls nicht aus dem Tool angelegt) „Heizlast abrufen“ und den
   Wert mit der Portal-Anzeige vergleichen (0,1 kW genau). Weicht er ab, den
   richtigen Ergebnis-Pfad unter Parametrierung → Heizreport → Ergebnis-Pfad
   eintragen (Vorbelegung `results.summary.heatLoad`; Ersatz = Summe der
   Raumheizlasten). Galerie-Ordner unter „Ablage“ prüfen (Vorbelegung
   „Montagedokumente“).
5. **Einmal „Heizreport-PDF ablegen“** – das PDF liegt danach in der Galerie des
   Vorgangs im eingestellten Ordner als `Heizreport-<PR-Nummer>-WP-<Datum>.pdf`.
   Achtung: jeder weitere Abruf erzeugt bei Heizreport ein neues Dokument – das
   Tool fragt deshalb beim zweiten Klick nach.

## Für die Projektierung

- **Heizreport-Knöpfe an der Heizlast-Aufgabe** (sobald der Token hinterlegt ist):
  „Heizreport-Projekt anlegen“ (nur solange kein Schlüssel am Gewerk; alternativ
  „Schlüssel von Hand eintragen“), danach „Heizreport öffnen ↗“ mit dem Schlüssel
  zum Kopieren, „Heizlast abrufen“ und „Heizreport-PDF ablegen“; „Verknüpfung
  lösen“ nur mit Begründung. Die Heizlastberechnung selbst (Räume, U-Werte,
  Heizflächen) bleibt im Heizreport-Portal – „Heizlast abrufen“ meldet „noch nicht
  berechenbar“, solange dort nichts erfasst ist.
- **Abgleich mit der verkauften Leistungsklasse:** nach „Heizlast abrufen“ zeigt die
  Aufgabe (und der Heizlast-Block der Akte) einen roten Hinweis, wenn die
  Heizreport-Heizlast laut Paketmatrix in eine andere Leistungsklasse fällt als
  im Steckbrief verkauft – „Auslegung prüfen (Nachtrag oder Freigabe)“. Angebot,
  Steckbrief und Stückliste werden nicht automatisch geändert.
- In der Feinplanungs-Erfassung sind „Heizlast (kW)“ und „Heizlast-Quelle“ nach
  dem Abruf mit dem Badge „aus Heizreport“ vorbelegt (bestätigen oder ändern).
- Ohne Token bleibt alles wie bisher (Link + Upload, Heizlast von Hand).
- Fehlgeschlagene Heizreport-Aufrufe stehen im Fehlerprotokoll (Fehlertyp
  „Heizreport“) – ohne Token.

## Benutzer und Parametrierung

- **Montageteam am Benutzer:** Unter Parametrierung → Allgemein → Benutzer wird das
  Montageteam je Montage-Benutzer über ein Dropdown gewählt („– kein Team –“ oder
  ein aktives Team); bestehende Zuordnungen bleiben erhalten, bei mehreren Teams
  steht je Team ein Dropdown untereinander. Ein weiteres Team gibt es über
  „+ weiteres Team“, „×“ entfernt eines – die Teams selbst werden weiterhin unter
  Parametrierung → Teams angelegt.
- **Parametrierung neu gegliedert:** Die Übersicht zeigt jetzt fünf Bereiche
  (Allgemein · Angebotstool · Projektierung · Lead-Management · System &
  Protokolle) mit Suchfeld; alle bisherigen Adressen bleiben gültig. Die
  Inline-Abschnitte der alten Übersicht liegen auf zwei eigenen Seiten:
  „Angebotstool-Einstellungen“ (Deckungsbeitrags-Ampel, E-Mail-Versand,
  Kombi-Versand, gewerkeübergreifende Artikel, Fern-Signatur, Abgelehnt-Prozess,
  Lösch-Protokoll) und „Logik & Importe“ (eingelesene Logik, Fragen,
  Angebotsaufbau, KfW-/PV-/KL-Parameter, Klima-Import, „Parametrierung neu
  einlesen“). Kein Formular verhält sich anders als vorher. Die
  Projektierung-Einstellungen haben eine Abschnitts-Navigation und einen festen
  Speichern-Knopf; der Heizreport-Block ist nach Parametrierung → Heizreport
  umgezogen (dort auch der Portal-Link).

## Offen

- Referenzprojekt-Schlüssel und Token liegen nur bei Andreas (nicht im Projekt);
  der Ergebnis-Pfad gilt bis zur Prüfung am Referenzprojekt als Annahme [A-5].
- Kennzahlen-Bedeutungen (Abschnitt 3 der Heizreport-Doku) – bis zur Eintragung
  werden die Felder nicht gesendet.
- Stufe 2: Räume per API, Webhook (öffentliche HTTPS-Adresse), Bilder,
  Wärmepumpen-Check (Angebotsstrang).
- Siehe Gesamtübersicht zur Übergabe und `docs/projektierung-entscheidungen.md`
  Abschnitt PLAN_PROJ_V5 (Annahmen A-1 … A-6).
