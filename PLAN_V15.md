# Umsetzungsplan v15 – Wirtschaftlichkeit im PV-Angebot & PV-Feinschliff

Voraussetzung: kein anderer Plan in Umsetzung (strangübergreifend geprüft).
CLAUDE.md und konfigurator_logik_v5.xlsx sind Live-Master im Projektordner
`C:\Users\a.scheelen\Tools\Angebotstool`. ALLE PHASEN DIESES PLANS IN
EINEM DURCHLAUF UMSETZEN (Reihenfolge einhalten, jede Checkbox nach
Umsetzung und Test abhaken, am Ende Gesamtübersicht mit Testergebnissen
und offenen Punkten, fachliche Rückfragen gebündelt). migrate.py idempotent.

CLAUDE-Abschnitt: **„Neu in v22"** (höchste + 1). Phasen **99–103**
(frei laut Zuordnungstabelle).

## Entscheidungen (Chat Angebotstool, 30.09.2026)

- Die Text-„Beispielrechnung" im PV-Nachtext (v16, `_beispielrechnung`)
  wird durch **drei gestaltete A4-Seiten „Wirtschaftlichkeit"** ersetzt –
  **eingebettet im PV-Angebots-PDF** (keine separate Anlage, keine
  Bildschirmansicht; beides ist später ohne Umbau möglich).
- Visuelle Referenz: `docs/wirtschaftlichkeit-mockup/seite1.png … seite3.png`
  (Pixelmaße im HTML daneben; 1 px = 0,2646 mm, 1 px = 0,75 pt). Maß- und
  Farbabweichungen ≤ 1 mm sind unkritisch, der Aufbau ist verbindlich.
- **Kein Finanzierungsblock** (Cloover vorerst außen vor).
- **Friondo SpotDynamic:** Netzbezug wird mit Ø **18 ct/kWh** bewertet
  (statt Haushaltsstrompreis), Kosten-Airbag 39 ct nur als Text.
- Betrachtungszeitraum **20 Jahre**, Strompreissteigerung 3 %/Jahr –
  alles parametrierbar im Blatt „PV-Parameter".
- **PA04 „Ertüchtigung bestehender ZV?"**: Ja löst keine Positionen und
  keine Ampel aus, Antwort nur im Protokoll (Phase 99).
- Rechenkern: die additive Eigenverbrauchsquote (32 + 33 + 10 %, offene
  PV-Rückfrage Nr. 4) wird durch eine **Energiebilanz** ersetzt, die den
  Verbrauch berücksichtigt (Autarkie, Netzbezug, WP-Anteil brauchen das).
- **Team-Feedback 30.09.** (Phase 103): BzA-Datenblatt im Dialog
  übersteuerbar inkl. Contracting (Vorbelegung Nein); Editor springt bei
  EP/bauseits/Alt./Rabatt/Preis/Menge nicht mehr an den Seitenanfang;
  sporadischer „Internal Server Error" beim Löschen/Verschieben von
  Positionen wird diagnostizierbar gemacht und abgefangen; Gruppen-
  Überschriften (z. B. „Bosch Monoblock Wärmepumpe CS3800i AW Paket …")
  je Angebot editierbar; Einheit der Auslegungszeile „psl." statt „pauschal".

## Entscheidungen 01.10.2026 (Rückfragen zur Umsetzung, Antworten Andreas)

1. PA05/PA06 bleiben als Folgefragen von PA04 im Bogen (nur Protokoll).
2. Ort in der Kopfzeile der Wirtschaftlichkeitsseiten = Ausstellungsort
   „Duisburg“.
3. **Saisonmodell:** Die Energiebilanz rechnet mit Monatsprofilen (Sommer
   viel Produktion, Winter viel Wärmepumpe) – Formeln in Anhang B; das
   Jahresmodell aus Anhang A ist damit überholt, die Kontrollwerte wurden
   neu berechnet.
4. Enni/SWD: der Hinweis „mit SpotDynamic zusätzlich“ bleibt auch bei
   Contracting-Profilen.
5. Häkchen „Wirtschaftlichkeit im PDF ausblenden“ ist in jedem Status
   umschaltbar (nicht nur im Entwurf).
6. BzA-Übersteuerungen nur für das erzeugte PDF (nicht gespeichert),
   abgeleitete Felder als Platzhalter.
7. Rundungen nach Mockup (20-Jahres-Summen, Szenarien, Gewinn, Autokilometer
   auf 100).
8. „psl.“-Migration auch für versendete/angenommene WP-Angebote.
9. Signierte PDFs AN-C-261008/261015 auf dem Server prüfen.
10. `fehler.log` mit uvicorn-Startzeilen; „Erledigte löschen“ lässt die
    Datei unberührt.

## Phase 99 – PA04 nur Protokoll, Platzhalter-Inventur
- [x] Ampel-Grund „Individuell: Ertüchtigung bestehender ZV – Positionen
      noch nicht hinterlegt" entfernen (Blatt „Aktionen PV" bzw. Code).
      PA04 bleibt Bogenfrage; keine Positionen, keine Nachfrage, kein
      fachlicher Hinweis. Logik-Validierung grün.
      (30.09.: Zeile 20 „Aktionen PV" → „–", Bemerkung v22; Validierung grün)
- [x] Tests anpassen (`tests/test_pv_v13.py`: PA04 = Ja → keine Ampel,
      Antwort im Protokoll); Button „Erneut prüfen" holt eine liegende
      PV-Erfassung mit PA04 = Ja auf Grün. (Klasse Phase99PA04, 31/31 grün)
- [x] Nur melden, nicht ändern: alle weiteren Platzhalter-Gründe der Art
      „… noch nicht hinterlegt" im PV-Konfigurator (Frage, Bedingung,
      Grundtext) in der Gesamtübersicht auflisten. (Inventur: keine weitere
      Zeile dieser Art – Liste in der Gesamtübersicht)
- [x] docs/nach-dem-update-v13.md: Rückfrage 5 (PA04) als beantwortet
      markieren.

## Phase 100 – Rechenkern `app/wirtschaftlichkeit.py`
- [x] Neues Modul mit reiner Rechenfunktion (keine DB-Zugriffe):
      `berechnen(param, anlage) -> dict`. Eingaben `anlage`: `kwp`,
      `module`, `speicher_kwh` (0 = kein Speicher), `hems` (bool),
      `spot` (bool), `hh_kwh`, `wp_kwh`, `wb_kwh`, `investition_eur`,
      `startjahr`. Alle Rechenwerte kommen aus `param` (siehe unten).
- [x] Energiebilanz je Jahr j = 1…N (Formeln verbindlich):
      · prod_j = kwp × ertrag × (1 − degradation)^(j−1)
      · last = hh + wp + wb
      · q_x = Direktanteil_x + (HEMS-Zuschlag_x, wenn hems) für x ∈ {hh, wp, wb}
      · direkt = min(q_hh×hh + q_wp×wp + q_wb×wb, 0,9 × prod_j)
      · sp_out = min(speicher_kwh × zyklen, (prod_j − direkt) × wirkungsgrad,
        last − direkt); ohne Speicher 0 · sp_in = sp_out ÷ wirkungsgrad
      · netz = last − direkt − sp_out · einsp = prod_j − direkt − sp_in
      · preis_j = strompreis × (1+steigerung)^(j−1)
      · bezug_j = spot_preis × (1+steigerung)^(j−1), wenn spot; sonst preis_j
      · kosten_ohne_j = last × preis_j
      · kosten_mit_j = netz × bezug_j − einsp × verguetung + betriebskosten
      · ersparnis_j = kosten_ohne_j − kosten_mit_j
      · kum_j = −investition + Σ ersparnis_1..j; break_even = erstes j mit
        kum_j ≥ 0 (None, wenn nie)
- [x] Kennzahlen (Jahr 1): Eigenverbrauchsquote = (direkt + sp_in) ÷ prod;
      Autarkie = (direkt + sp_out) ÷ last; Solaranteil WP =
      (q_wp × wp + sp_out × wp ÷ last) ÷ wp (nur wenn wp > 0); Ersparnis
      Jahr 1 und je Monat; Summe 20 Jahre (ohne, mit, Ersparnis); Faktor
      Ersparnis ÷ Investition; Gewinn Ende = kum_N.
- [x] Baustein-Treppe (sequentiell, Jahr-1-Ersparnis + 20-J-Summe +
      Break-even je Stufe): (1) PV allein (speicher 0, hems False, spot
      False) · (2) + Speicher · (3) + Friondo HEMS · (4) + SpotDynamic.
      Stufen, die im Angebot nicht enthalten sind, entfallen aus der
      Treppe; **fehlt SpotDynamic, liefert der Rechenkern zusätzlich den
      Vorteil „mit SpotDynamic" als Hinweiswert** (Upsell-Zeile im PDF).
- [x] Szenarien: Ersparnis 20 J. und Break-even für die Steigerungen aus
      dem Parameter „Szenarien Strompreissteigerung" (Standard 1; 3; 5 %).
- [x] CO₂: t/Jahr = prod_1 × faktor ÷ 1000; 20 Jahre = Σ prod_j × faktor;
      Auto-km = kg ÷ (g/km ÷ 1000); Bäume = kg ÷ kg je Baum und Jahr.
- [x] Neue Zeilen im Blatt „PV-Parameter" (Spalten Parameter | Wert |
      Einheit | Bemerkung; Import unverändert, Standardwerte im Code):
      Strompreissteigerung 3 % · Degradation 0,4 %/Jahr · Betriebskosten
      100 €/Jahr · Betrachtungszeitraum 20 Jahre · Inbetriebnahme-Versatz
      1 Jahr (Startjahr = Angebotsjahr + Versatz) · Direktanteil Haushalt
      35 % · Direktanteil Wärmepumpe 20 % · Direktanteil Wallbox 30 %
      [ANNAHME] · HEMS-Zuschlag Haushalt 5 %-Punkte · HEMS-Zuschlag
      Wärmepumpe 15 %-Punkte · HEMS-Zuschlag Wallbox 20 %-Punkte [ANNAHME]
      · Speicher Vollzyklen 250 /Jahr · Speicher Wirkungsgrad 90 % ·
      SpotDynamic Bezugspreis 0,18 €/kWh · Kosten-Airbag 0,39 €/kWh (nur
      Text) · Szenarien Strompreissteigerung „1; 3; 5" % · CO₂-Faktor
      Netzstrom 380 g/kWh (Umweltbundesamt) · CO₂ Auto 120 g/km · CO₂ Baum
      12,5 kg/Jahr. Strompreis bleibt 0,32 €/kWh, Einspeisevergütung 0,078,
      Spezifischer Ertrag 960. Die drei Zeilen „Eigenverbrauchsquote PV /
      Zuschlag Speicher / Zuschlag HEMS" bleiben erhalten, Bemerkung
      „überholt durch Energiebilanz (v22), ungenutzt".
- [x] Anlagendaten: `pv_auslegung.als_dict()` zusätzlich mit `hh_kwh`,
      `wp_kwh`, `wb_kwh`, `speicher_kwh` (PA10) füllen; für bestehende
      PV-Angebote Fallback über die verknüpfte Erfassung (PO06, PO07 bzw.
      `_PO07_aus_wp`, PO09, PA10). Speicher/HEMS/SpotDynamic aus den aktiven
      Positionen wie heute (KOMBI_MUSTER bzw. „SigenStor Batterie", Pos.
      015, Pos. 017; ep/bauseits/alternativ zählen nicht). Investition =
      `summen()["endbetrag"]` wie bisher.
- [x] `pdf_export.beispielrechnung_fuer` → `wirtschaftlichkeit_fuer` (alter
      Name als Alias). `pv_auslegung.wirtschaftlichkeit` bleibt für den
      Übergang, ist aber nicht mehr im PDF-Weg.
- [x] **Kontrollwerte** (Test `tests/test_wirtschaftlichkeit_v22.py`,
      Toleranz ± 1 € bzw. ± 0,1 %-Punkt) mit Parametern: ertrag 950,
      strompreis 0,33, verguetung 0,078, steigerung 3 %, degradation 0,4 %,
      betriebskosten 100, zyklen 250, wirkungsgrad 90 %, Direktanteile
      35/20 %, HEMS +5/+15, spot_preis 0,18, N = 20; Anlage kwp 10,92,
      speicher 10, hh 4.500, wp 4.500, wb 0, investition 24.900:
      · Jahr 1 mit HEMS: prod 10.374 · direkt 3.375 · sp_in 2.778 ·
        sp_out 2.500 · netz 3.125 · einsp 4.221 · EV-Quote 59,3 % ·
        Autarkie 65,3 % · Solaranteil WP 62,8 % (ohne HEMS 47,8 %)
      · Vollausbau (HEMS + Spot): Ersparnis J1 2.637 € (220 €/Monat) ·
        Summe 20 J. 68.675 € · Summe ohne 79.805 € · Summe mit 11.130 € ·
        Gewinn Ende 43.775 € · Break-even Jahr 9 · Faktor 2,76
      · kum_j: −22.263 · −19.558 · −16.781 · −13.930 · −11.004 · −8.000 ·
        −4.915 · −1.748 · 1.506 · 4.848 · 8.281 · 11.808 · 15.431 · 19.155 ·
        22.982 · 26.915 · 30.957 · 35.112 · 39.384 · 43.775
      · Treppe J1: 1.333 · 1.941 · 2.168 · 2.637 € — 20 J.: 31.668 ·
        49.503 · 56.080 · 68.675 € — Break-even 17 · 12 · 11 · 9
      · Szenarien 1/3/5 %: 56.995 · 68.675 · 83.591 €, Break-even 10 · 9 · 9
      · CO₂: 3,94 t/Jahr · 75,9 t/20 J. · 32.851 km · 315 Bäume
      Referenzimplementierung: Anhang A dieses Plans.

## Phase 101 – PDF-Seiten `app/wirtschaftlichkeit_pdf.py`
- [x] Drei feste A4-Seiten, gezeichnet mit fpdf2-Primitiven (rect, line,
      cell/multi_cell) – keine Bild-Renderings, keine Matplotlib. Aufruf
      aus `_nachtext_rendern` an der Stelle des Platzhalters
      `[WIRTSCHAFTLICHKEIT]` (alter Platzhalter `[BEISPIELRECHNUNG]` bleibt
      als Alias); ohne Auslegungsdaten entfällt der Block wie bisher. Die
      PV-Textblöcke „Friondo PV <Profil>" auf den neuen Platzhalter
      umstellen (Migration, alle Profile).
- [x] Schrift **Poppins** (Google Fonts, SIL OFL): Regular, Medium,
      SemiBold, Bold als TTF nach `app/static/pdf/fonts/` (inkl. OFL.txt),
      `add_font` nur für diese Seiten; Fallback Arial, wenn Dateien fehlen
      (Warnung ins Log, kein Abbruch). Ziffern tabellarisch (Poppins: über
      `font-variant`-Äquivalent nicht verfügbar → rechtsbündige Zellen).
- [x] Farben (RGB): Navy 27/42/94 · Navy hell 36/54/110 (Kacheln im Hero)
      · Blau 63/134/198 · Blau dunkel 50/110/165 · Tint 234/242/250 ·
      Tint 2 201/216/234 · Sonne 240/165/0 · Grau-Fläche 213/219/229 ·
      Karte 246/248/251 · Linie 223/227/234 · Text 27/31/42 · Grau-Text
      90/98/112 · Weiß.
- [x] Kompakter Seitenkopf nur für diese drei Seiten (Attribut am PDF-
      Objekt, `header()` verzweigt): Logo `friondo_logo.png` rechts oben
      (Breite 29 mm, y 10,5 mm), links Eyebrow in Blau dunkel 8 pt fett,
      Zeichenabstand +1 („WIRTSCHAFTLICHKEITSBETRACHTUNG" · „IHRE
      ERSPARNIS IM DETAIL" · „SICHERHEIT & TRANSPARENZ"), darunter 9 pt
      grau „zu Angebot <Nr> · <Ort>, <Datum> · Seite x von 3". Fußzeile
      unverändert (5 Spalten). Ränder 20 mm, Inhaltsbreite 170 mm,
      Inhalt endet ≤ 258 mm.
- [x] **Seite 1 „Auf einen Blick"** (Aufbau wie seite1.png):
      H1 22,5 pt Navy fett „So rechnet sich Ihre Energielösung" (y 27 mm),
      Subline 10 pt grau: Anlage (kWp, Module, Speicher, HEMS, SpotDynamic
      – nur enthaltene Bausteine), Kunde/Ausführungsort, Verbrauchsbasis.
      · Hero-Karte Navy (y 57–118 mm, Radius 3 mm, Innenabstand 7 mm):
        Eyebrow „IHRE ERSPARNIS IN 20 JAHREN" (8 pt, 159/184/220), Betrag
        43 pt weiß (auf 100 € gerundet), rechts 10 pt Text „Das
        <Faktor,1>-Fache Ihrer Investition von <Investition> € – vermiedene
        Stromkosten plus Einspeisevergütung, bei nur <Steigerung> %
        Strompreissteigerung pro Jahr."; darunter drei Kacheln Navy hell:
        „<BE> Jahre / bis sich die Anlage bezahlt gemacht hat", „<Autarkie>
        % / Ihres Stroms kommen vom eigenen Dach", „<Monat> €/Monat /
        Ersparnis – schon im ersten Jahr" (18 pt weiß + 8 pt hell).
      · Karte „Wann sich Ihre Anlage bezahlt macht" (y 122–196 mm): rechts
        9 pt „Kumulierte Ersparnis abzüglich Investition, in €"; Balken je
        Jahr (kum_j): positiv Blau nach oben, negativ Tint 2 nach unten,
        Nulllinie Navy 0,3 mm; Positivbereich 28 mm, Negativbereich 13 mm,
        gemeinsame Skala; Jahreslabels 8 pt (alle 3 Jahre + letztes);
        Hinweis links oben 8 pt „Start <Jahr>: Investition <Betrag> €";
        Chip Sonne mit Navy-Text „Break-even <Jahr>" über der Nulllinie
        beim Break-even-Jahr; Endwert „+<kum_N> €" 9 pt fett über dem
        letzten Balken; Satz darunter 9 pt „Ab <Jahr> arbeitet die Anlage
        nur noch für Sie: **rund <Gewinn> € Gewinn bis <Endjahr>**."
        Ohne Break-even innerhalb N: Chip entfällt, Satz „Innerhalb von
        <N> Jahren erreicht die Anlage <kum_N> € – …" neutral formulieren.
      · Karte „Woher Ihr Strom kommt – und wohin Ihr Solarstrom geht"
        (y 200–256 mm): zwei gestapelte Balken (8 mm hoch) mit Beschriftung
        links (Solarstrom <prod> kWh / aus <kWp> kWp; Verbrauch <last> kWh /
        Haushalt + Wärmepumpe [+ Wallbox]); Segmente Sonne (direkt), Blau
        (Speicher), Grau (Netz) mit Prozent 9 pt; Legende; Schlusssatz
        10 pt „Sie nutzen **<EV> % Ihres Solarstroms selbst**
        (Eigenverbrauch) und decken **<Autarkie> % Ihres Bedarfs vom eigenen
        Dach** (Autarkie)."
- [x] **Seite 2 „Ersparnis im Detail"** (seite2.png): H1 „Was Sie Jahr für
      Jahr sparen", Subline wie Mockup.
      · Karte „Ihre Stromkosten pro Jahr" (y 57–133 mm): Legende „Ohne
        Anlage" Navy / „Mit Friondo (Netzbezug zu SpotDynamic-Preisen
        abzüglich Einspeisung)" Blau (Text ohne SpotDynamic: „Mit Friondo
        (Netzbezug abzüglich Einspeisung)"); je Jahr Balkenpaar, Höhe
        ∝ kosten_ohne_j / kosten_mit_j (max 28 mm); Nulllinie; Labels wie
        Seite 1; darunter drei Kacheln: „<Σ ohne> € / ohne Anlage in 20
        Jahren" (Karte), „<Σ mit> € / mit Friondo in 20 Jahren" (Tint,
        Blau dunkel), „<Σ Ersparnis> € / Ihr Vorteil in 20 Jahren" (Navy,
        weiß). Negatives „mit" (Erlöse > Kosten) als 0-Balken + Betrag mit
        Vorzeichen.
      · Karte links „Ihr Vorteil im ersten Jahr" (y 138–201 mm, Breite
        87 mm), drei Spalten (Bezeichnung | Rechnung 8 pt grau | Betrag
        rechts): Stromkosten heute · <last> × <ct> ct · <kosten_ohne_1> ·
        Netzbezug neu · <netz> × <ct> ct · −<netz×preis> · Einspeisung ·
        <einsp> × 7,8 ct · +<Betrag> · SpotDynamic (nur wenn enthalten) ·
        <netz> × −<Differenz> ct · +<Vorteil> · Betriebskosten · pauschal ·
        −<Betrag> · Summenzeile fett „Ihr Vorteil Jahr 1 · <Monat> €/Monat ·
        <ersparnis_1> €".
      · Karte rechts „Heizen mit Sonnenstrom" (nur wenn wp_kwh > 0, sonst
        Karte „Ihr Verbrauch" mit Haushalt/Wallbox-Aufteilung): Zeile
        „Wärmepumpe: <wp> kWh Strom pro Jahr", Balken Sonne/Grau „<Anteil> %
        vom Dach | <Rest> % Netz", zwei Kacheln „<wp×preis> € / Heizstrom
        pro Jahr ohne PV" und „<(wp−wp_pv)×preis> € / Heizstrom pro Jahr
        mit PV", Text „Friondo HEMS lässt die Wärmepumpe bevorzugt bei Sonne
        laufen: Solaranteil am Heizstrom <mit HEMS> % statt <ohne HEMS> %."
        (Satz nur mit HEMS im Angebot; ohne HEMS: „Mit Friondo HEMS stiege
        der Solaranteil auf <mit HEMS> %.").
      · Karte „Was jeder Baustein bringt" (y 205–256 mm): Treppe aus bis zu
        vier Säulen (Tint 2 / Blau / Blau dunkel / Navy), Jahr-1-Betrag
        10 pt fett in der Säule, Zuwachs „+ <Δ> €" 8 pt in Sonne dunkel
        (154/103/0) über der Säule, Basis „Basis"; unter der Linie Name
        (PV-Anlage allein · + Speicher <kWh> kWh · + Friondo HEMS ·
        + SpotDynamic) und „20 Jahre: <Σ> € · amortisiert nach <BE> J.".
        Fehlt SpotDynamic im Angebot: vierte Säule entfällt, stattdessen
        Hinweiszeile 9 pt „Mit Friondo SpotDynamic zusätzlich rund
        +<Δ> €/Jahr – sprechen Sie uns an."
- [x] **Seite 3 „Sicherheit & Transparenz"** (seite3.png): H1 „So sicher
      ist Ihre Rechnung", Subline wie Mockup.
      · Karte „Drei Strompreis-Szenarien" (y 57–128 mm), rechts „Ersparnis
        in 20 Jahren, in €": drei Säulen (Tint 2 / Blau / Navy) mit Betrag
        10 pt fett darüber und „Amortisation <BE> Jahre" 9 pt in der Säule
        unten; darunter „Strompreis +<x> % pro Jahr" 10 pt fett und Note
        (vorsichtig gerechnet · Ihre Rechnung · bei stark steigenden
        Preisen); Text 9,5 pt „Selbst bei nur <min> % Preissteigerung pro
        Jahr bleibt es bei rund <BE_min> Jahren bis zur Amortisation.
        SpotDynamic ist mit Ø <spot> ct/kWh angesetzt, der Kosten-Airbag
        deckelt bei <airbag> ct." (zweiter Satz nur mit SpotDynamic).
      · Karte „Ihr Beitrag zum Klima" (y 132–166 mm), rechts „Netzstrom
        mit <faktor> g CO₂/kWh (Umweltbundesamt)": vier Kacheln mit
        Strich-Icon (Wolke, Blatt, Auto, Baum – lokale SVG→Pfade oder
        einfache Linienzüge, keine Emojis): „<t> t CO₂ / pro Jahr
        vermieden", „<t20> t CO₂ / in 20 Jahren", „<km> km / Autofahrt pro
        Jahr", „<n> Bäume / gleiche Wirkung".
      · Karte „Unsere Annahmen – transparent" (y 170–256 mm), rechts
        „Modellannahmen, keine Zusage": zwei Spalten à vier Zeilen (Ertrag ·
        Strompreis · Einspeisung · Speicher | Verbrauch · Friondo HEMS ·
        SpotDynamic · Betrieb) mit den tatsächlichen Parameterwerten;
        Disclaimer 8 pt grau (Wortlaut Mockup); Abschluss „SO GEHT ES
        WEITER" mit vier nummerierten Schritten (Angebot annehmen ·
        Feinplanung vor Ort · Montage in 1–2 Tagen · Inbetriebnahme &
        Einweisung) – Schritt 3 Wortlaut aus Parameter „Montagedauer-Text"
        (Standard „Montage in 1–2 Tagen"), damit der Innendienst ihn
        anpassen kann.
- [x] Zahlenformate über `_zahl` (Tausenderpunkt, Komma); Beträge im Hero
      und in den 20-Jahres-Kacheln auf 100 € gerundet, Tabellen exakt;
      Prozent ohne Nachkommastelle; negative Beträge mit „−".
- [x] Layout-Sicherheit: jede Karte hat feste Höhe; Texte mit
      `multi_cell` und Schriftgrößen wie angegeben; lange Kundennamen/
      Anschriften in der Subline kürzen (…), nie umbrechen über die
      Kartenkante; Seitenumbruch innerhalb der drei Seiten ist verboten
      (Auto-Page-Break für den Block aus, danach wieder an).

## Phase 102 – Einbindung, Editor, Doku
- [x] Editor (Angebots-Kopf, nur PV, ID/Admin): Häkchen
      **„Wirtschaftlichkeit im PDF ausblenden"** (`angebote.
      wirtschaftlichkeit_ausblenden`, Standard aus; analog
      `foerderung_ausblenden`; „Überarbeiten"/„Duplizieren"/„Für anderen
      Kunden kopieren" übernehmen es). Ausgeblendet → Platzhalter-Seiten
      entfallen komplett.
- [x] Parametrierung → PV-Parameter-Ansicht zeigt die neuen Zeilen;
      Validierung meldet fehlende Pflichtparameter mit Standardwert-Hinweis.
      (Tabelle „PV-Parameter" mit Einheit in der Übersicht; fehlende v22-
      Zeilen = Hinweis mit Standardwert, unlesbare Werte = Fehler)
- [x] Regression: WP-PDF unverändert (Kontrollwerte Netto 30.245,43 €),
      PV-PDF ohne Auslegungsdaten (Altfälle) ohne Wirtschaftlichkeit und
      ohne Fehler, Lieferschein unverändert; Enni/SWD/Sparkasse-PV-Profile
      zeigen die Seiten; Kombi-Versand unverändert. Voll-Crawl + Abnahme-
      skript gegen aktuelle DB-Kopie in diagnose\ grün.
      (30.09.: 265 Unit-Tests grün; Abnahme 93/93 gegen Entwicklungs-DB und
      gegen die migrierte Kopie diagnose\test_v22\data (Server-Stand 29.09.
      15:32, migrate 2× sauber); Voll-Crawl `scripts/voll_crawl.py` 44.844
      Aufrufe, 4 Rollen, 0 Abstürze – zuvor 4 Abstürze durch signierte PDFs
      mit Altpfad, behoben in routers/signatur.py + Migration)
- [x] Abnahme-PDF: Test-Erfassung mit den Kontrollwerten aus Phase 100
      (Beispielkunde) → PDF-Seiten optisch gegen seite1–3.png prüfen;
      PDF nach `docs/wirtschaftlichkeit-mockup/abnahme-AN-<Nr>.pdf` (ohne
      Kundendaten) für Andreas ablegen. (abnahme-AN-C-261021.pdf, Familie
      Mustermann mit den Kontrollwert-Parametern; Seiten 7–9)
- [x] CLAUDE.md: Abschnitt „Neu in v22 – Wirtschaftlichkeit PV & PA04";
      Zuordnungstabelle v22 → PLAN_V15.md, Phasen 99–102; Hinweis in
      „Neu in v16", dass die Beispielrechnung durch v22 ersetzt ist.
      docs/nach-dem-update-v22.md (Team-Hinweise: neue Seiten, Häkchen,
      Parameter, Poppins-Fallback). Commit mit sprechender Nachricht;
      **kein push vor Freigabe**.
      (30.09.: Doku erledigt; **Commit offen** – auf diesem Rechner ist kein
      Git installiert und der Projektordner hat keinen `.git`-Ordner;
      Commit-Nachricht steht in der Gesamtübersicht)

## Phase 103 – Team-Feedback 30.09. (Fehlerprotokoll, Editor, BzA, Gruppen)

(Checkboxen am 30.09.2026 aus dem Abschnitt „Entscheidungen" abgeleitet –
der Plan nannte Phase 103 nur dort.)

- [x] **Fehlerprotokoll** zuerst: jede unbehandelte Ausnahme (Internal Server
      Error) landet mit Zeit, Benutzer, Rolle, Route, Methode, Formdaten
      (ohne PIN), Fehlertyp und Traceback in der Tabelle `fehlerprotokoll`;
      der Benutzer sieht eine lesbare Fehlerseite mit Fehler-Nr. statt
      „Internal Server Error"; Ansicht Parametrierung → Fehlerprotokoll
      (Admin/Innendienst, Filter, Leeren).
      (30.09.: `app/fehlerprotokoll.py` + `data/fehler.log`, Handler in
      main.py, Formdaten-Pufferung in der RollenMiddleware; Tests
      tests/test_fehlerprotokoll_v22.py)
- [x] Kandidaten für den sporadischen „Internal Server Error" beim
      Löschen/Verschieben von Positionen mit TestClient nachstellen
      (doppelte Anfrage, bereits gelöschte Position, Sortier-Payload,
      letzte Position, gesperrtes Angebot …); gefundene Ursachen in der
      Gesamtübersicht benennen und abfangen (Meldung statt Absturz).
      (30.09.: Ursache „database is locked" durch Hintergrundläufe;
      Positionsrouten mit Wiederholung `_speichern`, Parser-Schutz und
      Rückmeldung in der Sortierung; Graph-Timeouts; Tests
      tests/test_v22_positionen.py mit echter Schreibsperre)
- [x] Editor springt bei EP / bauseits / Alternativ / Rabatt / Preis / Menge
      nicht mehr an den Seitenanfang (Scroll-Position bleibt).
- [x] BzA-Datenblatt: alle Felder im Dialog übersteuerbar, inkl.
      Contracting (Vorbelegung Nein); PDF nimmt die übersteuerten Werte.
      (30.09.: 36 Felder mit Schlüssel, `erstellen(uebersteuert=…)`,
      Dialog-Inputs `f_<schluessel>`, Vorschau aktualisieren/Zurücksetzen;
      statuslos – nur für das erzeugte PDF; Tests Phase103Uebersteuern)
- [x] Gruppen-Überschriften (z. B. „Bosch Monoblock Wärmepumpe CS3800i AW
      Paket …") je Angebot editierbar (Editor + PDF; Kopieren/Überarbeiten
      übernehmen sie). (Route POST /angebote/<id>/gruppe, ✎ im Editor)
- [x] Einheit der Auslegungszeile „psl." statt „pauschal" (WP-Angebote;
      Bestand per Migration, nur bei unveränderter Auslegungszeile).
- [x] Tests `tests/test_v22_feedback.py`; Team-Hinweise in
      docs/nach-dem-update-v22.md; CLAUDE.md v22 (Phasen 99–103).

## Zulieferungen / bewusst offen
- Cloover-Finanzierungsbeispiel (Zins, Laufzeit) – später eigener Block.
- Separate Anlage / Bildschirmansicht / Wirtschaftlichkeit am WP-Angebot –
  Rechenkern und Seiten sind dafür vorbereitet, kein Bau in v22.
- Direktanteil Wallbox und HEMS-Zuschlag Wallbox sind Annahmen [ANNAHME]
  wie im Blatt markiert; übrige PV-Rückfragen aus
  docs/nach-dem-update-v13.md bleiben offen (Inventur aus Phase 99).

## Anhang A – Referenzimplementierung (für den Test; Python)
```python
def energie(p, a, j, hems):
    prod = a["kwp"] * p["ertrag"] * (1 - p["degradation"]) ** (j - 1)
    q = {x: p["direkt_" + x] + (p["hems_" + x] if hems else 0) for x in ("hh", "wp", "wb")}
    last = a["hh_kwh"] + a["wp_kwh"] + a["wb_kwh"]
    direkt = min(sum(q[x] * a[x + "_kwh"] for x in q), 0.9 * prod)
    sp_out = min(a["speicher_kwh"] * p["zyklen"], (prod - direkt) * p["wirkungsgrad"], last - direkt)
    sp_in = sp_out / p["wirkungsgrad"] if sp_out else 0.0
    return dict(prod=prod, direkt=direkt, sp_in=sp_in, sp_out=sp_out, last=last,
                netz=last - direkt - sp_out, einsp=prod - direkt - sp_in,
                wp_pv=q["wp"] * a["wp_kwh"] + (sp_out * a["wp_kwh"] / last if last else 0))

def reihe(p, a, hems, spot):
    rows, kum = [], -a["investition"]
    for j in range(1, p["jahre"] + 1):
        e = energie(p, a, j, hems)
        preis = p["strompreis"] * (1 + p["steigerung"]) ** (j - 1)
        bezug = p["spot_preis"] * (1 + p["steigerung"]) ** (j - 1) if spot else preis
        ohne = e["last"] * preis
        mit = e["netz"] * bezug - e["einsp"] * p["verguetung"] + p["betriebskosten"]
        kum += ohne - mit
        rows.append(dict(jahr=j, ohne=ohne, mit=mit, ersparnis=ohne - mit, kum=kum, **e))
    return rows
# p = dict(ertrag=950, strompreis=0.33, verguetung=0.078, steigerung=0.03,
#          degradation=0.004, betriebskosten=100, jahre=20, zyklen=250,
#          wirkungsgrad=0.90, direkt_hh=0.35, direkt_wp=0.20, direkt_wb=0.30,
#          hems_hh=0.05, hems_wp=0.15, hems_wb=0.20, spot_preis=0.18)
# a = dict(kwp=10.92, speicher_kwh=10, hh_kwh=4500, wp_kwh=4500, wb_kwh=0,
#          investition=24900)
# Treppe: (0, F, F) → (10, F, F) → (10, T, F) → (10, T, T)
```

## Anhang B – Saisonmodell (Entscheidung 01.10.2026, ersetzt Anhang A)

Die Energiebilanz je Jahr wird je Monat m = 1…12 mit Monatsprofilen
(Anteile am Jahr, Σ = 1; parametrierbar im Blatt „PV-Parameter“) gerechnet
und aufsummiert; Kosten, Break-even, Treppe, Szenarien und CO₂ bleiben wie
in Phase 100 beschrieben.

```
prod_m   = prod_j × profil_pv[m]          sonne_m = profil_pv[m] × 12  (1 = Durchschnittsmonat)
x_m      = x_kwh × profil_x[m]  (x ∈ hh, wp, wb)      last_m = Σ x_m
direkt_m = min(Σ q_x × x_m × sonne_m, 0,9 × prod_m, last_m)
sp_out_m = min(speicher × zyklen × tage_m ÷ 365, (prod_m − direkt_m) × wirkungsgrad, last_m − direkt_m)
sp_in_m  = sp_out_m ÷ wirkungsgrad
netz_m   = last_m − direkt_m − sp_out_m        einsp_m = prod_m − direkt_m − sp_in_m
wp_pv_m  = direkt_m × (q_wp × wp_m) ÷ Σ q_x × x_m + sp_out_m × wp_m ÷ last_m
Jahreswerte = Σ_m; Kennzahlen aus den Jahreswerten wie in Phase 100.
```

Standard-Monatsprofile (% je Monat, Jan–Dez):
- PV: 2,5 · 4,5 · 10 · 11 · 12,5 · 13 · 13 · 11,5 · 9,5 · 7 · 3,5 · 2
  (typische Ertragsverteilung Deutschland: Nov–Feb ≈ 12 %, Apr–Sep ≈ 70 %)
- Haushalt [ANNAHME, angelehnt an BDEW H0]: 9,5 · 8,5 · 8,8 · 8 · 7,7 · 7,3 ·
  7,5 · 7,5 · 7,7 · 8,4 · 9 · 10,1
- Wärmepumpe: 80 % Heizung nach VDI-2067-Gradtagszahlen (170/150/130/80/40/
  13,3/13,3/13,3/30/80/120/160 ‰) + 20 % Warmwasser gleichverteilt =
  15,3 · 13,7 · 12,1 · 8,1 · 4,9 · 2,7 · 2,7 · 2,7 · 4,1 · 8,1 · 11,3 · 14,5
- Wallbox [ANNAHME]: gleichverteilt (12 × 8,33)

Kontrollwerte Saisonmodell (Parameter und Anlage wie in Phase 100,
Test `tests/test_wirtschaftlichkeit_v22.py`; mit flachen Profilen
reproduziert das Modell die Werte aus Anhang A):
- Jahr 1 mit HEMS: prod 10.374 · direkt 2.922 · sp_in 2.479 · sp_out 2.232 ·
  netz 3.847 · einsp 4.973 · EV-Quote 52,1 % · Autarkie 57,3 % · Solaranteil
  WP 48,9 % (ohne HEMS 38,7 %); Netzbezug Jan 869 / Jun–Jul 0 / Dez 909 kWh
- Vollausbau (HEMS + Spot): Ersparnis J1 2.565 € (214 €/Monat) · Summe 20 J.
  66.256 € · Summe ohne 79.805 € · Summe mit 13.549 € · Gewinn Ende 41.356 € ·
  Break-even Jahr 9 · Faktor 2,66
- kum_j: −22.335 · −19.704 · −17.007 · −14.241 · −11.404 · −8.494 · −5.508 ·
  −2.444 · 700 · 3.927 · 7.239 · 10.640 · 14.131 · 17.716 · 21.397 · 25.177 ·
  29.060 · 33.049 · 37.147 · 41.356
- Treppe J1: 1.261 · 1.835 · 1.988 · 2.565 € — 20 J.: 29.599 · 46.277 ·
  50.628 · 66.256 € — Break-even 18 · 12 · 12 · 9
- Szenarien 1/3/5 %: 55.241 · 66.256 · 80.322 €, Break-even 10 · 9 · 9
- Vorteil J1: 2.970 − 1.269 + 388 + 577 − 100 = 2.565 €; Heizstrom 1.485 €
  ohne / 759 € mit PV; CO₂ unverändert (3,94 t · 75,9 t · 32.851 km · 315 Bäume)
