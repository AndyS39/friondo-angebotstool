# Nach dem Update auf v19 – BzA-Datenblatt & BAFA-Anlagennummern

(Plan: PLAN_V14.md, Phasen 95–97 – ursprünglich als „v14“ geschrieben.)

## Für den Außendienst (WP-Erfassungsbogen)

Zwei neue Fragen, eine umbenannte – alle für das BzA-Datenblatt der KfW:

| Frage | Wo | Warum |
|---|---|---|
| **A02 „Inbetriebnahmejahr (Baujahr) der bestehenden Heizung“** (nur neuer Text) | Alte Anlage | Das Jahr steuert den Klimageschwindigkeitsbonus (Gas ≥ 20 Jahre) und steht im KfW-Portal als Inbetriebnahmedatum |
| **A20 „Nennleistung der bestehenden Heizung in kW“** (Pflicht) | Alte Anlage | Pflichtfeld im KfW-Portal – vom Typenschild ablesen; unbekannt → 0 eingeben |
| **N11 „Contracting-Modell?“** (vorbelegt Nein) | Neue Anlage | Pflichtfeld im KfW-Portal |

Die „vorhandenen Heizflächen“ fragt der Bogen schon über **H02 Verteilsystem** ab:
nur Fußbodenheizung → 35 °C Vorlauf, sonst 55 °C.

## Für den Innendienst: Datenblatt → KfW-Portal

1. Angebot öffnen (Editor-Kopf) oder Vorgangsakte → **„BzA-Datenblatt (PDF)“**
   (jedes WP-Angebot, jeder Status; auch TAIFUN-WP-Einträge).
2. Im Dialog: Anzahl der zu fördernden Wohneinheiten prüfen, Ersteller wählen,
   bei **TAIFUN-Angeboten das Gerät aus der BAFA-Liste wählen (Pflicht)**.
3. PDF „BzA-Datenblatt-<Angebotsnummer>.pdf“ – Abschnitte 1–6 in der
   Reihenfolge des KfW-Portals. Rot markierte Zeilen („— fehlt: bitte beim
   Kunden erfragen“) vor der Portaleingabe klären.
4. Das Datenblatt ist ein **internes Arbeitsblatt**, keine KfW-Unterlage.

Am **TAIFUN-Eintrag** gibt es außerdem „KfW-gefördert: Ja / Nein / unbekannt“
(auch im Dialog „Extern erledigt“). Es steuert die BzA-Aufgabe der
Projektierung (bei Nein entfällt sie).

In der Projektierung zeigt „Datenblatt“ an der BzA-Aufgabe dieselben
Abschnitte mit Kopier-Knöpfen plus den Stand BzA/KfW; „Datenblatt-PDF“ führt
zum Dialog am Angebot.

## Parametrierung

- **BzA-Ersteller:** Firmenblock fest (Friondo GmbH, Arnold-Overbeck-Str.
  63-65, 47139 Duisburg, HWK-Betriebsnummer 1862718); Standard-Ersteller
  wählbar (sonst der angemeldete Benutzer). E-Mail und Telefon kommen aus der
  Benutzerverwaltung – bitte dort pflegen.
- **Logik-Blatt „BAFA-Anlagen“** (konfigurator_logik_v5.xlsx): Zuordnung
  Paket 045–054 und Klasse 15 (Außeneinheit 030/031 + Inneneinheit 055/056)
  → BAFA-Anlagennummer, Gerätebezeichnung, Nennwärmeleistung.

## Offene Punkte

- **Weiße CS8800-Außeneinheit (Pos. 030):** Die Anlagennummern 16019200 /
  16019199 tragen den Zusatz „(B)“. Bis zur Klärung gelten sie für beide
  Farben; das Datenblatt zeigt den Prüfhinweis.
- **Hybrox 21** (16017387, ait-deutschland) steht als Vorrat im Blatt; die
  Klassenerweiterung wartet auf Komponenten, Preise und Klassengrenzen.
- **CS5800-Serie:** Die Nummern aus den Screenshots lagen nicht im Projekt
  vor – bitte liefern, dann als Vorrat-Zeilen ergänzen.
- **Portal-Wortlaut „Art des Wärmeerzeugers“** (Gasheizung / Ölheizung /
  Nachtspeicherheizung / Sonstiges) und die Boni-Kategorien sind aus dem
  Plan übernommen – beim ersten echten Portal-Durchgang gegenprüfen.
- „Im Zuge der Sanierung ausgebaut“ = Ja, wenn das Angebot eine Position mit
  „Demontage“ enthält (TAIFUN: immer Ja).
