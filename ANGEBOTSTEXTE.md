# Angebotstexte & Firmendaten (Quelle: Referenz-Angebot AN250096)

Diese Texte sind fester Bestandteil jedes Angebots-PDFs. Reihenfolge und Platzierung
siehe PLAN.md Phase 7. Formulierungen exakt übernehmen.

> **Hinweis v36 (PLAN_V22 Phase 189):** Die Abschnitte 1–10 beschreiben das Layout v2
> (fpdf2 – seit v36 nur noch Rückfall-Engine `pdf_engine = fpdf2`) und sind zugleich die
> **Quelle der Wortlaute** der Textblöcke (Parametrierung → Textblöcke: Vortexte, Nachtexte
> A–C, Vollmacht). Das neue Layout v3 (HTML-Vorlagen + Browser-Druck) ordnet dieselben
> Textblöcke neuen Seiten zu – siehe Abschnitt 11.

## 1. Briefkopf (Seite 1)

- Logo-Leiste oben: Innungs-Fachbetrieb (SHK) · BOSCH Premium Partner / Zertifizierter
  Profi Wärmepumpen · German Energy Awards Winner 2026 · Friondo-Logo ·
  Fachbetrieb Wärmepumpe · BOSCH Zertifizierter Profi Split-Klimageräte
  (Logodateien im Ordner `Layout - Logo`)
- Absenderzeile klein über Empfängeradresse:
  `Friondo GmbH · Arnold-Overbeck-Str. 63-65 · 47139 Duisburg`
- Empfängerblock: Kundenadresse aus Kundenverwaltung
- Rechts: Seite / Datum / Kunden-Nr.
- Titelzeile: `A N G E B O T - Nr.: AN-C-2610xx` (gesperrt wie im Original)
- Folgeseiten: nur Friondo-Logo rechts oben + Kopfzeile mit Angebots-Nr. und Seite

## 2. Fußzeile (jede Seite, 5 Spalten)

| ANSCHRIFT | GESCHÄFTSFÜHRUNG | KONTAKT | BANKVERBINDUNG | STEUERDATEN |
|---|---|---|---|---|
| Friondo GmbH | Andreas Scheelen | T: 0203 - 3965 710 | Sparkasse Duisburg, IBAN: DE98 3505 0000 0200 4064 03, BIC: DUISDE33XXX | Amtsgericht Duisburg |
| Arnold-Overbeck-Str. 63-65 | Charoula Scheelen | info@friondo.de | Sparkasse Krefeld, IBAN: DE06 3205 0000 0000 4974 53, BIC: SPKRDE33 | HRB 34795 |
| 47139 Duisburg | Ioannis Simeonidis | www.friondo.de | | USt-IdNr. DE350979869 |

## 3. Vortext (Seite 1, vor den Positionen)

**Ihr individuelles Wärmepumpen-Angebot zum Festpreis**
**Effizienz, Komfort und zukunftssicher**

Sehr geehrte Damen und Herren,

vielen Dank für Ihr Vertrauen in die Friondo GmbH. Sie haben eine zukunftssichere
Entscheidung getroffen – eine moderne Wärmepumpe senkt Ihre Energiekosten, steigert
den Wohnkomfort und macht Sie unabhängiger von fossilen Brennstoffen.

Anbei erhalten Sie Ihr maßgeschneidertes Angebot. Darin enthalten sind:

- [Haken] Ihre individuelle Wärmepumpe – optimal dimensioniert für Ihre Immobilie
- [Haken] Detaillierte Installationsleistungen – fachgerecht, sauber und termingerecht
- [Haken] Transparent und Festpreis – klar verständlich und ohne versteckte Kosten
- [Haken] Unser Rundum-Sorglos-Service – von der Planung bis zur Inbetriebnahme

**Warum Friondo?**

- [Haken] **Fachkompetenz & Qualität** – Als Meisterbetrieb, Mitglied der Innung und
  VDI-zertifiziertes Fachunternehmen setzen wir auf höchste Standards.
- [Haken] **Zertifizierte Sachkundige für Wärmepumpensysteme nach VDI 4650** –
  Fundiertes Fachwissen und tiefgehender Expertise der Wärmepumpentechnik.
- [Haken] **Persönliche Beratung** – Wir begleiten Sie von der ersten Idee bis zur
  perfekten Lösung für Ihr Zuhause.
- [Haken] **Effizienz & Nachhaltigkeit** – Unsere Systeme senken Ihren Energieverbrauch
  spürbar und steigern den Wert Ihrer Immobilie.
- [Haken] **Fördermittel-Check & Unterstützung** – Wir helfen Ihnen, maximale staatliche
  Zuschüsse zu nutzen.

**Wir sind auf Wärmepumpen spezialisiert und gehören in der Region zu den führenden
Anbieter.** Lassen Sie uns gemeinsam Ihre Heizung zukunftsfähig machen!

Ihr Friondo-Team

## 4. Positionsteil

Tabelle: Position | Menge | Einh. | Bezeichnung | E-Preis | G-Preis.
Gruppen-Überschriften fett als eigene Zeile (lt. Logik-Excel „Angebotsaufbau").
Bei Seitenwechsel „Übertrag:"-Zeile unten und oben. EP-Positionen: E-Preis normal,
G-Preis = „EP.". Danach Summenblock:

```
Netto-Summe            €   xx.xxx,xx
19,00 % USt.           €    x.xxx,xx
Gesamt-Betrag          €   xx.xxx,xx
```

Direkt darunter KfW-Aufschlüsselung (Grundförderung, Klimageschwindigkeits-Bonus,
Einkommensbonus, Fördersatz gesamt, förderfähige Kosten mit Höchstbetrag,
KfW-Zuschuss, ggf. Deckel-Hinweis) und:

```
Angebotssumme (brutto)         €   xx.xxx,xx
− voraussichtliche Förderung   €   xx.xxx,xx
= Eigenanteil                  €   xx.xxx,xx
```

Zeile „Antrag: KfW 458 (Wohngebäude)" bzw. „KfW 522 (Nichtwohngebäude)", dann
Disclaimer (siehe Logik-Excel Blatt KfW).

## 5. Nachtext A – „Ihre Zahlungsoptionen bei Friondo" (eigene Seite)

**Barkauf oder Finanzierung**

Saubere Energie. Faire Raten. Maximale Freiheit.

**Finanzierung mit Cloover**

Investieren Sie jetzt in Ihre Energie- oder Wärmelösung – ohne hohe Einmalzahlung und
bequem in festen Monatsraten über bis zu 20 Jahre.

Sofort starten
- Keine Anzahlung, Keine Grundbuchbelastung, Schnelle - digitale Prüfung,
  Finanzierungszusage in wenigen Minuten, 100 % digital, Kein Papierkram und keine
  Banktermine

Planbare Monatsraten – Zum Beispiel:
- Wärmepumpe ab 129 € pro Monat mit Förderung*
- Oder ab 250 € pro Monat ohne Förderung

So bleibt Ihr Budget flexibel und Ihre Energiekosten sinken langfristig.

Maximale Flexibilität
- Kostenlose Sondertilgungen
- Vorzeitige Rückzahlung ohne Strafgebühren
- Individuell anpassbare Laufzeiten

Ihre Vorteile
- Sofort investieren · Monatlich entspannt zahlen · Energiekosten senken ·
  Unabhängiger werden

Kundenzufriedenheit: 4,8 von 5

„Dank Cloover konnten wir unsere Wärmepumpe einfach, fair und transparent finanzieren."

Starten Sie jetzt mit Friondo und Cloover in eine nachhaltige Zukunft.

*Beispielrate auf Basis einer Angebotssumme von 29.000 €, einer Förderung von 56 %,
gedeckelt auf 28.000 €, und einer Laufzeit von 20 Jahren.

**v36 (PLAN_V22 Phase 193, Platzhalter `[CLOOVER]`):** Im Textblock „Friondo Standard“ (und „Friondo PV
Standard“) steht statt des Absatzes „Planbare Monatsraten – Zum Beispiel: … Oder ab 250 € pro Monat ohne
Förderung“ und der Fußnote „*Beispielrate …“ der Platzhalter `[CLOOVER]` (Migration
`angebotsprofile.migriere_cloover_platzhalter`, Seed-Konstanten `STANDARD_NACHTEXT`/`PV_STANDARD_NACHTEXT`).
Der fpdf2-Rückfall druckt dort die bei Cloover berechnete Rate des Angebots: Box „Planbare Monatsraten – Ihre
Rate für dieses Angebot:“ mit „ab … € pro Monat mit Förderung*“ (nur WP mit Förderung) / „ab … € pro Monat
ohne Förderung“, bei Kombi-Versand „Gesamtrate für alle Angebote dieser Mail: ab … € pro Monat“, Knopf
„Finanzierung abschließen ›“ + QR-Code + Kurzlink nur mit persönlichem Link (sonst „Ihren persönlichen
Finanzierungs-Link erhalten Sie von uns per E-Mail.“), Rückmeldungs- und Datenschutzsatz (Textbaustein
`cloover_datenschutz`), Fußnote aus dem Textbaustein `cloover_fussnote` am Seitenende; ohne Rate „• Monatsrate
auf Anfrage“. Das Layout v3 rendert den Platzhalter nicht (Karte 2 + Box aus `_cloover.html`, Abschnitt 11).
Die Beispielwerte oben bleiben nur als Herkunftsnachweis stehen. Wortlaute: `app/cloover.py`,
`app/cloover_texte.py` (Entwürfe, Rückfragen B1/B7).

## 6. Nachtext B – „Installationsvoraussetzungen" (eigene Seite)

**Haftungsbegrenzung**
Technische und kaufmännische Angaben sind freibleibend. Sie werden erst durch eine
nachfolgende Auftragsbestätigung verbindlich.

**Rücktrittsrecht im Zusammenhang mit Technischer Feinplanung**
Die in diesem Vertrag vorgesehenen Verpflichtungen und (Liefer-)Leistungen setzen eine
eingehende technische Feinplanung voraus, um sicherzustellen, dass das Vorhaben zu den
vereinbarten Bedingungen umgesetzt werden kann. Sollte die technische Feinplanung
ergeben, dass die Umsetzung des Vorhabens technisch nicht möglich ist oder nur mit
erheblichem Mehraufwand erfolgen kann, ist jede Vertragspartei – abweichend der AGB
von Friondo – berechtigt, von dem Vertrag zurückzutreten. Ein entsprechender Rücktritt
ist innerhalb von sechs (6) Wochen ab Kenntnisnahme in Textform gegenüber der jeweils
anderen Vertragspartei zu erklären.

**Zahlung**
`{zahlungsbedingungen}` *(seit v30, PLAN_V18 Phase 150: Platzhalter im Textblock – das
PDF druckt hier den Text der am Angebot gewählten Zahlungsbedingung; die Überschrift
„Zahlung“ bleibt im Textblock. Die Texte pflegt der Innendienst unter Parametrierung →
Zahlungsbedingungen (`app/zahlungsbedingungen.py`, Tabelle `zahlungsbedingungen`); ohne
Auswahl gilt der Standard-Eintrag. Startwerte:)*

1. **Standard** (bisheriger fester Absatz, wörtlich):
   Eine Anzahlung von 50% des Angebotsbetrags ist spätestens 14 Tage vor Arbeitsbeginn zu
   zahlen. Die Restzahlung wird mit der Schlussrechnungsstellung fällig. Die Rechnung
   erhalten Sie im Anschluss zur Installation.
2. **50 % am Montagetag** [ANNAHME, Innendienst liest gegen]:
   Eine Anzahlung von 50% des Angebotsbetrags ist am Tag der Montage zu zahlen. Die
   Restzahlung wird mit der Schlussrechnungsstellung fällig. Die Rechnung erhalten Sie im
   Anschluss zur Installation.
3. **80 % Anzahlung, 2 % Skonto** [ANNAHME, Innendienst liest gegen]:
   Eine Anzahlung von 80% des Angebotsbetrags ist spätestens 14 Tage vor Arbeitsbeginn zu
   zahlen. Bei Zahlung der Anzahlung innerhalb von 7 Tagen nach Auftragserteilung gewähren
   wir 2% Skonto auf den Anzahlungsbetrag. Die Restzahlung wird mit der
   Schlussrechnungsstellung fällig. Die Rechnung erhalten Sie im Anschluss zur Installation.

Abweichend (Freitext) am Angebot: der eingegebene Text erscheint wörtlich. Skonto wirkt nur
im Text – keine Änderung an Summen, KfW-Rechnung oder Deckungsbeitrag.

**Hinweis zur KfW-Förderung**
Der Wechsel zu einer klimafreundlichen Heizlösung kann unter bestimmten
Voraussetzungen durch Förderprogramme der Bundesregierung unterstützt werden. Im
Rahmen des Programms „Heizungsförderung für Privatpersonen – Wohngebäude"
(Programmnummer 458) erfolgt die Förderung über die Kreditanstalt für Wiederaufbau
(KfW).

Bitte beachten Sie, dass weder der Anspruch auf Fördermittel noch deren konkrete Höhe
garantiert werden kann. Die abschließende Entscheidung über Bewilligung und Umfang
der Förderung liegt ausschließlich bei der KfW.

Die Ihnen kommunizierte, voraussichtliche Förderhöhe basiert auf den Angaben, die im
Beratungsgespräch erfasst wurden. Für die Richtigkeit und Vollständigkeit dieser
Informationen übernimmt Friondo keine Haftung. Zudem wird bestätigt, dass sich die
Antragsteller bei mehreren am Vorhaben beteiligten Investoren über die Verteilung der
Förderbeträge einvernehmlich verständigt haben.

Eine Kombination bzw. Kumulierung der KfW-Förderung mit der steuerlichen Förderung
gemäß § 35 EStG ist ausgeschlossen. Antragsteller sind verpflichtet, für dieselbe
Maßnahme keinen zusätzlichen Antrag auf steuerliche Förderung zu stellen.
Voraussetzung für die Förderung von Wärmepumpen ist außerdem, dass am vorgesehenen
Installationsort kein Anschluss- oder Benutzungszwang an ein Wärmenetz besteht. Die
Prüfung dieser Voraussetzung obliegt dem Kunden und muss vor Auftragserteilung
erfolgen.

Wir halten uns freibleibend 30 Tage an dieses Angebot gebunden.
Es gelten unsere Allgemeinen Geschäftsbedingungen, diese sind zu finden unter:
https://friondo.de/AGB
Informationen zu unserem Datenschutz finden Sie unter: https://friondo.de/Datenschutz

## 7. Nachtext C – Schlussseite mit Unterschriften (eigene Seite)

Wir sichern Ihnen eine fach- und zeitgerechte Ausführung aller angebotenen Leistungen zu.

Sie haben Fragen oder wünschen weitere Informationen? Rufen Sie uns an - wir sind für
Sie da.

Mit freundlichen Grüßen,

Ihr Friondo-Team

Sollte Ihnen das Angebot zusagen, senden Sie uns bitte zur Auftragserteilung das
unterschriebene Angebot zurück.

**Aufschiebende Bedingung:**
Dieser Vertrag tritt hinsichtlich der Liefer- und Leistungspflichten zur Umsetzung,
erst und nur insoweit in Kraft, wenn und soweit die KfW den Antrag zur Förderung
Heizungstausch BEG EM bewilligt und die Förderung mit einer Zusage gegenüber der
antragstellenden Vertragspartei zugesagt hat (aufschiebende Bedingung). Die
antragstellende Vertragspartei wird die jeweils andere Vertragspartei über den Eintritt
und den Umfang des Eintritts der Bedingung unverzüglich in Kenntnis setzen. Die
Förderzusage löst dann direkt den Vorhabensbeginn aus.

Voraussichtliches Datum der Umsetzung: ______________ ,liegt innerhalb des
Bewilligungszeitraum nach Nummer 9.4.1.

```
...............................................    ......................................................
Ort, Datum                                         Unterschrift des Auftraggebers
```

## 8. Nachtext D – Vollmacht (eigene Seite)

**Vollmacht zur Beauftragung der SpotmyEnergy GmbH sowie zur Anmeldung und
Inbetriebsetzung von Anlagen**

Ich bevollmächtige als zukünftiger Anlagenbetreiber und Gebäudeeigentümer die Friondo
GmbH, in meinem Namen alle erforderlichen Schritte zur Beauftragung der SpotmyEnergy
GmbH als Messstellenbetreiber und/oder Stromlieferant einzuleiten und entsprechende
Verträge abzuschließen. Dies umfasst auch die Erteilung eines SEPA-Lastschriftmandats
für damit verbundene Zahlungen.

Die Vollmacht gilt ebenfalls für die Friondo GmbH sowie deren Nachunternehmer zur
Anmeldung, Inbetriebnahme, Änderung, Erweiterung oder Abmeldung folgender Anlagen und
Verbrauchseinrichtungen beim zuständigen Netzbetreiber oder
Energieversorgungsunternehmen:

Photovoltaikanlagen, Wärmepumpen, Ladeeinrichtungen/Wallboxen sowie sonstige
steuerbare Verbrauchseinrichtungen gemäß § 14a EnWG (Modul 1, 2 oder 3).

Die Vollmacht umfasst insbesondere die An- und Abmeldung von Zählern, die Beantragung
neuer Zähler, die Einreichung und Entgegennahme erforderlicher Unterlagen, die
Kommunikation mit Netzbetreibern, Messstellenbetreibern und Stromlieferanten, die
Kündigung bestehender Verträge, die Durchführung eines Anbieterwechsels sowie die
Beauftragung und Betreuung eines intelligenten Messsystems.

Die Vollmacht gilt ausschließlich für die genannten Zwecke und erlischt nach Abschluss
des beauftragten Vorgangs. Sie kann jederzeit schriftlich widerrufen werden.

**Angaben zur Verbrauchsstelle**
Name / Adresse / Geburtsdatum / Telefon / E-Mail (Formularfelder; Name und Adresse aus
Kundendaten vorbefüllen)

Bitte ankreuzen:
[ ] Messstellenbetreiber und [ ] Stromlieferant
[ ] Anmeldung/Inbetriebnahme/Änderung/Erweiterung/Abmeldung

**SEPA-Lastschriftmandat**
Ich ermächtige den Zahlungsempfänger, fällige Zahlungen mittels Lastschrift von
folgendem Konto einzuziehen.

Kontoinhaber / Adresse / IBAN / Kreditinstitut / Ort, Datum (Formularfelder)

Unterschrift Vollmachtgeber: ______________________
Unterschrift Kontoinhaber, sofern abweichend: ______________________

## 9. Klima (v24) – Texte des Klimakonfigurators

Quelle: PLAN_V16.md Phase 115 (abgestimmt 03.10.2026). Klima-Angebote
(`konfigurator_typ = "KL"`, 19 % USt) nutzen eigene Textblöcke
„Friondo KL Standard" (Vortext + Nachtext), „Friondo KL Enni", „Friondo KL SWD",
„Friondo KL Sparkasse DU" (Nachtexte) – Seed-Konstanten in
`app/angebotsprofile.py` (`KL_VORTEXT`, `KL_STANDARD_NACHTEXT`, `KL_SEED_BLOECKE`),
Migration `seed_kl`, Auswahl `_kl_block` / `ist_kl`, editierbar in der
Parametrierung → Textblöcke. **Alle KL-Texte sind Entwürfe für das Gegenlesen
durch den Innendienst (A14)**; Formulierungen zu Zertifizierung/Kältemittel sind
[ANNAHME]. Kein Platzhalter `[WIRTSCHAFTLICHKEIT]`, kein KfW-/Förderblock, keine
Vollmacht (Nachtext D), keine Wirtschaftlichkeitsseiten. Nachtext A entfällt bei
Enni und SWD (wie WP); Sparkasse DU hat den eigenen Finanzierungs-Kopf (wie WP).

### 9.1 Vortext KL (Seite 1)

**Ihr individuelles Klimaanlagen-Angebot zum Festpreis**
**Angenehmes Raumklima – kühlen im Sommer, heizen in der Übergangszeit**

Sehr geehrte Damen und Herren, *(dynamisch: `{briefanrede}`)*

vielen Dank für Ihr Vertrauen in die Friondo GmbH. Mit einer modernen
Split-Klimaanlage von Bosch schaffen Sie an heißen Tagen ein angenehmes Raumklima,
heizen effizient in der Übergangszeit und verbessern die Luftqualität in Ihren
Räumen.

Anbei erhalten Sie Ihr maßgeschneidertes Angebot. Darin enthalten sind:

- [Haken] Ihre individuelle Klimaanlage – ausgelegt auf Ihre Räume
- [Haken] Detaillierte Installationsleistungen – fachgerecht, sauber und termingerecht
- [Haken] Transparent und Festpreis – klar verständlich und ohne versteckte Kosten
- [Haken] Unser Rundum-Sorglos-Service – von der Planung bis zur Inbetriebnahme

**Warum Friondo?**

- [Haken] **Fachkompetenz & Qualität** – Als Meisterbetrieb, Mitglied der Innung und
  VDI-zertifiziertes Fachunternehmen setzen wir auf höchste Standards.
- [Haken] **Fachgerechte Kältetechnik** – Montage, Dichtheitsprüfung und
  Inbetriebnahme durch geschultes Fachpersonal nach den Vorgaben der
  F-Gase-Verordnung.
- [Haken] **Persönliche Beratung** – Wir begleiten Sie von der ersten Idee bis zur
  perfekten Lösung für Ihr Zuhause.
- [Haken] **Effizienz & Komfort** – Inverter-Technik mit hoher Energieeffizienz,
  leiser Betrieb und auf Wunsch Steuerung per App.

**Wir sind auf Wärmepumpen und Klimatechnik spezialisiert und gehören in der
Region zu den führenden Anbietern.** Lassen Sie uns gemeinsam für ein angenehmes
Raumklima sorgen!

Ihr Friondo-Team

### 9.2 Nachtext A KL – „Ihre Zahlungsoptionen bei Friondo" (nur Standard und Sparkasse-Kopf)

Wie Abschnitt 5 mit drei Änderungen: „Investieren Sie jetzt in Ihre
**Klimalösung** – ohne hohe Einmalzahlung …"; der Absatz „Planbare Monatsraten –
Zum Beispiel: … Oder ab 250 € pro Monat ohne Förderung" entfällt samt Fußnote
„*Beispielrate …" (der Satz „So bleibt Ihr Budget flexibel und Ihre Energiekosten
sinken langfristig." bleibt); Kundenstimme „Dank Cloover konnten wir unsere
**Anlage** einfach, fair und transparent finanzieren."

**v36 (Phase 193):** Im Textblock „Friondo KL Standard“ steht der Platzhalter `[CLOOVER]` unmittelbar vor
„So bleibt Ihr Budget flexibel …“ (Migration `migriere_cloover_platzhalter`, Seed `_KL_ZAHLUNGSOPTIONEN`) –
der fpdf2-Rückfall druckt dort die berechnete Rate wie in Abschnitt 5 beschrieben; die Kanalprofile KL
(Enni/SWD/Sparkasse DU) bleiben ohne Cloover.

**Barkauf oder Finanzierung**

Saubere Energie. Faire Raten. Maximale Freiheit.

**Finanzierung mit Cloover**

Investieren Sie jetzt in Ihre Klimalösung – ohne hohe Einmalzahlung und bequem in
festen Monatsraten über bis zu 20 Jahre.

Sofort starten
- Keine Anzahlung, Keine Grundbuchbelastung, Schnelle - digitale Prüfung,
  Finanzierungszusage in wenigen Minuten, 100 % digital, Kein Papierkram und keine
  Banktermine

So bleibt Ihr Budget flexibel und Ihre Energiekosten sinken langfristig.

Maximale Flexibilität
- Kostenlose Sondertilgungen
- Vorzeitige Rückzahlung ohne Strafgebühren
- Individuell anpassbare Laufzeiten

Ihre Vorteile
- Sofort investieren · Monatlich entspannt zahlen · Energiekosten senken ·
  Unabhängiger werden

Kundenzufriedenheit: 4,8 von 5

„Dank Cloover konnten wir unsere Anlage einfach, fair und transparent finanzieren."

Starten Sie jetzt mit Friondo und Cloover in eine nachhaltige Zukunft.

Enni: Kopf „Barkauf oder Enni Contracting" + „Unsere Leistungen /
Installationsvoraussetzungen" („… die gewünschte Klimaanlage"); SWD: Kopf
„Barkauf oder Contracting", danach direkt „Installationsvoraussetzungen";
Sparkasse DU: Kopf „Barkauf oder Finanzierung" + „Finanzierung mit Sparkasse
Duisburg" + „Unsere Leistungen / Installationsvoraussetzungen".

### 9.3 Nachtext B KL – „Installationsvoraussetzungen"

Haftungsbegrenzung, Rücktrittsrecht im Zusammenhang mit Technischer Feinplanung
und Zahlung wörtlich wie Abschnitt 6 (seit v30 ebenfalls mit dem Platzhalter
`{zahlungsbedingungen}` – die am Angebot gewählte Zahlungsbedingung gilt auch für
Klima-Angebote); **ohne** „Hinweis zur KfW-Förderung", stattdessen nach „Zahlung"
([ANNAHME], Innendienst liest gegen):

**Hinweis zur Kältetechnik**
Die angebotenen Geräte arbeiten mit dem Kältemittel R32. Montage, Evakuierung,
Dichtheitsprüfung und Inbetriebnahme erfolgen durch sachkundiges Personal nach den
Vorgaben der F-Gase-Verordnung (EU) 2024/573; die Dichtheitsprüfung wird
dokumentiert. Die Kältemittel-, Kondensat- und Elektroleitungen sind bis 5 m je
Innengerät enthalten; längere Leitungswege sind als eigene Position ausgewiesen.
Der Montageort der Außeneinheit wird so gewählt, dass Schall- und Abstandsvorgaben
eingehalten werden; die endgültige Festlegung erfolgt in der technischen
Feinplanung vor Ort.

Danach unverändert: Bindefrist („Wir halten uns freibleibend 30 Tage …"), AGB,
Datenschutz. Der WP-Absatz „Anmeldung … beim Netzbetreiber" und der
„Heizkörper-Check" (Enni/Sparkasse WP) entfallen bei Klima.

### 9.4 Nachtext C KL – Schlussseite mit Unterschriften

Wie Abschnitt 7 **ohne** den Absatz „Aufschiebende Bedingung" und **ohne** die Zeile
„Voraussichtliches Datum der Umsetzung … Bewilligungszeitraum nach Nummer 9.4.1.";
stattdessen:

Voraussichtlicher Ausführungszeitraum: ______________

Unterschriftenblock (Ort, Datum / Unterschrift des Auftraggebers, inkl.
elektronischer Signatur) unverändert. Kein Nachtext D (Vollmacht) bei Klima.

### 9.5 Positionsteil / Summenblock Klima

Block 1 Montage/Zuschläge und Block 2 Elektro ohne Überschrift, Block 3 mit
Gruppen-Überschrift „Klimaanlage Bosch" (editierbar wie seit v22), WLAN-Gateway
KL013 als Eventualposition mit G-Preis „EP.", Auslegungszeile „Auslegung der
Klimaanlage" (0,00 €, psl.) als letzte Zeile von Block 3. Summenblock:

```
Netto-Summe            €   x.xxx,xx
19,00 % USt.           €     xxx,xx
Gesamt-Betrag          €   x.xxx,xx
```

ggf. „− Rabatt" / „= Endbetrag"; **kein** KfW-Block, keine Wirtschaftlichkeit.

### 9.6 Anhänge, Lieferschein, Protokoll (Klima)

- **Anhänge:** Regel „wenn Sparte = KL" im Blatt „Anhänge" (Zeile „(Bosch
  Climate Broschüre – Zulieferung)", Platzhalter in Klammern bleibt bis zur
  Lieferung unwirksam – A15). Der Parser (`app/logik.py`, Regelart „sparte",
  seit v13-PV) und die Auswertung (`app/anhaenge.py`, Vergleich mit
  `konfigurator_typ`) brauchen dafür keinen neuen Code. Unternehmenspräsentation
  und Ratenkauf greifen über „immer" (Ratenkauf nicht bei Enni/SWD).
- **Lieferschein:** wie WP/PV ohne Preise; EP-Zeile (Gateway) und die
  Auslegungszeile entfallen; die Gruppen-Überschrift „Klimaanlage Bosch" steht
  seit v24 auch im Lieferschein. Seit v30 (PLAN_V18 Phase 149) erscheint jede
  Position mit Bezeichnung (fett) und der **vollständigen** Beschreibung (alle
  Zeilen wie im Angebots-PDF, 7,5 pt, Seitenumbruch innerhalb langer Texte
  erlaubt); EP-Folgepositionen nach Parameter `lieferschein_folgepositionen`
  (Standard `014: 015, 016, 017` – bei WP: steht „Friondo fit for future“ auf EP,
  Alternativ oder bauseits, fehlen auch HEMS, iMSys und SpotDynamic).
- **Protokoll-PDF:** Seite „Auslegung" mit den Zeilen aus
  `kl_auslegung.protokoll_zeilen` (je Raum Fläche · Höhe · Wärmelast · Kühllast ·
  Klasse · Außengerät; je Außengerät Gerät und Kombination; Montage) – Einträge
  ohne Frage-ID werden nur mit Beschriftung gerendert.

## 10. Wallbox (v34) – Texte des Wallbox-Konfigurators

Seit v34 (PLAN_V21, Phasen 178/179, Nachtrag + Ergänzung 15.10.2026) erzeugt eine grüne
WB-Katalog-Erfassung (Mennekes AMTRON 4You 310/560, Leitungsverlegung, Erdarbeiten,
Wandmontage/Säule, Durchbrüche) ein Tool-Angebot mit 19 % USt. Textblöcke „Friondo WB
Standard" (Vortext + Nachtext), „Friondo WB Enni", „Friondo WB SWD", „Friondo WB
Sparkasse DU" (Nachtexte, Start = Kopie des Standards [ANNAHME]) – Seed-Konstanten in
`app/angebotsprofile.py` (`wb_vortext`, `WB_VORTEXT`, `WB_STANDARD_NACHTEXT`,
`WB_SEED_BLOECKE`), Migration `seed_wb`, Auswahl `_wb_block` / `ist_wb`, editierbar in der
Parametrierung → Textblöcke. **Alle WB-Texte sind Entwürfe für das Gegenlesen durch den
Innendienst.** Kein Nachtext A „Ihre Zahlungsoptionen" (nicht im TAIFUN-Muster AN251131;
der Cloover-Plan kann ihn später ergänzen) *(überholt – seit v36 (PLAN_V22 Phase 193) trägt
„Friondo WB Standard“ einen Nachtext A „Ihre Zahlungsoptionen bei Friondo“ = Kopie des KL-Textes
mit „Ihre Wallbox-Lösung“ und dem Platzhalter `[CLOOVER]` (`WB_ZAHLUNGSOPTIONEN`,
`WB_STANDARD_NACHTEXT_V36`, Migration stellt ihn dem bisherigen Text voran; nur Profil Standard –
die Kanalprofile WB bleiben ohne) [ANNAHME B2-8, Entwurf fürs Gegenlesen])*, kein KfW-/Förderblock, keine
Wirtschaftlichkeit, **keine Auslegungs-Position** (Herleitung im Protokoll, Seite
„Auslegung", und intern im Editor); **Vollmacht (Nachtext D) immer** (Netzanmeldung
§ 14a EnWG, Rückfrage 4).

### 10.1 Vortext WB (Seite 1) – wörtlich aus dem TAIFUN-Muster

**Ihre individuelle Wallbox zum Festpreis**

Sehr geehrte Damen und Herren, *(dynamisch: `{briefanrede}`)*

vielen Dank für Ihr Vertrauen in die Friondo GmbH. Mit einer modernen Wallbox laden
Sie Ihr Elektrofahrzeug bequem zu Hause, sparen Zeit und machen sich unabhängiger von
öffentlichen Ladeinfrastrukturen. So schaffen Sie Komfort, Sicherheit und ein smartes
Energiemanagement direkt bei Ihnen vor Ort.

Anbei erhalten Sie Ihr maßgeschneidertes Angebot. Darin enthalten sind:

- [Haken] Ihre individuelle Wallbox – perfekt abgestimmt auf Ihre Immobilie & Ihren Bedarf
- [Haken] Fachgerechte Installation – sauber, sicher und termingerecht
- [Haken] Transparent & zum Festpreis – klar verständlich, ohne versteckte Kosten
- [Haken] Unser Rundum-Sorglos-Service – von der Planung bis zur Inbetriebnahme

**Warum Friondo?**

- [Haken] **Fachkompetenz & Qualität** – Als Meisterbetrieb und zertifizierter Fachbetrieb
  setzen wir auf höchste Standards
- [Haken] **Alles aus einer Hand** – Von Photovoltaik bis Energiemanagement – perfekt
  kombinierbar mit Ihrer Wallbox
- [Haken] **Persönliche Beratung** – Wir begleiten Sie von der ersten Idee bis zur fertigen
  Lösung
- [Haken] **Effizienz & Nachhaltigkeit** – Wir helfen Ihnen, Ihr Zuhause energieoptimiert
  und zukunftssicher zu gestalten
- [Haken] **Fördermittel-Check & Unterstützung** – Wir prüfen für Sie mögliche Zuschüsse
  und Förderungen

Wir sind auf moderne Energiesysteme spezialisiert und gehören in der Region zu den
führenden Anbietern von Photovoltaik, Wärmepumpen, Klimaanlagen,
Energiemanagement-Systemen und Wallboxen. Lassen Sie uns gemeinsam Ihr Zuhause fit für
die Zukunft machen!

Ihr Friondo-Team

**Komplettpaket Wallbox inkl. Montage** *(eigener Absatz am Ende des Vortexts [ANNAHME
Plan]; Wortlaut wörtlich aus der Textzeile ohne Position der Wallbox-Excel `WB Angebot
Excel 1.xlsx` – `_x000D_`-Umbrüche und „?"-Platzhalter der TAIFUN-Symbole entfernt;
`seed_wb` liest ihn beim Anlegen des Textblocks aus `Artikel-Preislisten/Wallbox/` und
hebt einen noch unveränderten Entwurf auf den Excel-Text. Ohne Datei bleibt der Entwurf
„Die Zukunft der Energie beginnt bei Ihnen zuhause – effizient, nachhaltig und
zuverlässig." Die Import-Vorschau zeigt die Textzeile unter „Textzeilen ohne Position".)*

### 10.2 Nachtext B WB – „Installationsvoraussetzungen"

Haftungsbegrenzung, Rücktrittsrecht im Zusammenhang mit Technischer Feinplanung und
Zahlung wörtlich wie Abschnitt 6 (mit dem Platzhalter `{zahlungsbedingungen}`; der
v30-Standardtext ist wörtlich die Muster-Klausel „Anzahlung 50 % spätestens 14 Tage vor
Arbeitsbeginn …" – Rückfrage 3 damit erledigt; die Zahlungsbedingung bleibt je Angebot
wählbar). Danach Bindefrist („Wir halten uns freibleibend 30 Tage …"), AGB,
Datenschutz. **Ohne** „Hinweis zur KfW-Förderung" (WP), **ohne** „Hinweis zur
Kältetechnik" (KL), **ohne** Netzbetreiber-Absatz und Heizkörper-Check.

### 10.3 Nachtext C WB – Schlussseite mit Unterschriften

Wie Abschnitt 7 **ohne** den Absatz „Aufschiebende Bedingung" und **ohne** die Zeile
„Voraussichtliches Datum der Umsetzung … Bewilligungszeitraum"; stattdessen wie KL:

Voraussichtlicher Ausführungszeitraum: ______________

Unterschriftenblock (Ort, Datum / Unterschrift des Auftraggebers, inkl. elektronischer
Signatur) unverändert.

### 10.4 Nachtext D WB – Vollmacht (immer)

Die Vollmacht-Seite (Abschnitt 8, SpotmyEnergy/§ 14a) erscheint bei Wallbox-Angeboten
**immer** – unabhängig von iMSys/SpotDynamic-Fragen und unabhängig vom Profil (auch
Enni/SWD) [ANNAHME, Rückfrage 4], weil die Netzanmeldung nach § 14a EnWG (WB004)
Teil des Angebots ist. Verankert in `app/anhaenge.py` (`vollmacht_erforderlich`:
`konfigurator_typ == "WB"` → True) und `app/angebotsprofile.py` (`vollmacht_erlaubt`:
WB → True); `pdf_export._mit_vollmacht` nutzt beide Funktionen unverändert.

### 10.5 Positionsteil / Summenblock Wallbox

Block 1 „Wallbox" (WB001 oder WB002), Block 2 „Installation und Anschluss" in der
Reihenfolge WB003 Anschlussvorbereitung (psl., immer; bis 10 m Leitung und 2 Durchbrüche
enthalten) · WB008 Zusätzliche Bohrung/Durchbrüche × (WB07 − 2) · WB005 lfd. Meter
NYY-J × Mehrlänge (nur über 10 m) · WB006 Erdarbeiten × Meter (nur bei WB03 = Ja) ·
WB007 Fundament und Standsäule (1 × psl., nur bei Säule); Block 3 „Netzanmeldung"
(WB004, 0,00 €); Gruppen-Überschriften editierbar wie seit v22. Keine Auslegungszeile.
Summenblock:

```
Netto-Summe            €   x.xxx,xx
19,00 % USt.           €     xxx,xx
Gesamt-Betrag          €   x.xxx,xx
```

ggf. „− Rabatt" / „= Endbetrag"; **kein** KfW-Block, keine Wirtschaftlichkeit.
Kontrollwerte (Preis WB003 1.297,20 €, kaufmännische USt wie TAIFUN): A 310 / 10 m /
Erdarbeiten Nein / Wandmontage / 2 Durchbrüche → 2.235,70 / 424,78 / 2.660,48 €; B 560 /
25 m / Ja 8 m / Säule → 5.435,85 / 1.032,81 / 6.468,66 €; B2 = B + 4 Durchbrüche →
5.773,85 / 1.097,03 / 6.870,88 €; C 560 / 8 m → 2.687,75 / 510,67 / 3.198,42 €; D 310 /
12,4 m → Mehrlänge 2 m → 2.334,38 € netto. Musterangebot AN251131 (Positionen 001 + 002 +
003 + 005): Netto 3.626,25 €, USt 688,99 €, Gesamt 4.315,24 €.

### 10.6 Anhänge, Lieferschein, Protokoll (Wallbox)

- **Anhänge:** Zeile `Mennekes AMTRON 4You Datenblatt.pdf` mit Regel „wenn Sparte = WB"
  im Blatt „Anhänge" (Datei = Zulieferung; `anhaenge.fehlende_dateien` meldet sie, bis
  sie in `anlagen/` liegt). Unternehmenspräsentation und Ratenkauf greifen über „immer"
  (Ratenkauf nicht bei Enni/SWD). Liefert Mennekes getrennte Datenblätter je Modell:
  Regel „wenn Artikel WB001 im Angebot" / „wenn Artikel WB002 im Angebot" (seit v34
  erlaubt der Parser Artikel mit Sparten-Präfix).
- **Lieferschein:** wie WP/PV/KL ohne Preise, Gruppen-Überschriften, vollständige
  Beschreibung je Position (v30).
- **Protokoll-PDF:** Seite „Auslegung" mit „Wallbox: AMTRON 4You 560",
  „Leitungsverlegung gesamt: 25 m, davon 10 m enthalten, Mehrlänge 15 m" (ohne
  Mehrlänge: „… – bis 10 m enthalten, keine Mehrlänge"), „Erdarbeiten: 8 m" bzw.
  „Erdarbeiten: keine", „Montage: Säule (Fundament und Standsäule)" bzw. „Montage:
  Wandmontage", „Durchbrüche: 4 (2 in der Anschlussvorbereitung enthalten, 2
  zusätzlich)" bzw. „Durchbrüche: 2 (in der Anschlussvorbereitung enthalten)"; ab 100 m
  Leitungsverlegung zusätzlich „Leitungslänge über 100 m – bitte prüfen" (Warnung, keine
  Sperre). Derselbe Text steht in `angebote.auslegung_text` (Editor „Auslegung
  (intern)", nur Innendienst/Admin).

## 11. Layout v3 (v36) – HTML-Vorlagen + Browser-Druck

Seit v36 (PLAN_V22 Phase 188/189) entsteht das Angebots-PDF aus Jinja2-Vorlagen unter
`app/templates/pdf/angebot/` (Basis `basis.html`, Fußzeile `_fuss.html`, Seiten-Bausteine
`deckblatt.html` · `ueberblick.html` · `positionen.html` · `kfw.html` · `wirtschaftlichkeit.html` ·
`auftrag.html` (+ `_cloover.html`) · `bedingungen.html` · `vollmacht.html`, Sparten-Vorlagen
`wp.html` / `pv.html` / `kl.html` / `wb.html`), gedruckt über Edge/Chromium (`app/pdf_html.py`).
Alle Daten kommen aus EINEM Kontext `app/pdf_kontext.fuer_angebot` (Vertrag im Modul-Docstring);
die fpdf2-Engine (Abschnitte 1–10) bleibt Rückfall. Design-Vorlagen: `docs/design-v36/vorlage/`.
Schrift Nunito Sans, Farben Dunkelblau #15153a · Friondo-Blau #4389c8 · Grau #6b6f85 · Linie
#dfe3ee · Fläche #f1f6fc (nur in `app/static/pdf/angebot.css`, Templates nur `var(--pdf-…)`).

### 11.1 Seitenfolge je Sparte

| Sparte | Seiten |
|---|---|
| WP | Deckblatt · Ihr Angebot im Überblick + Teamfoto · Festpreisangebot (n Seiten, Summenblock mit Förderzeilen) · Ihre KfW-Förderung (nur mit Förderblock) · Auftragserteilung · Vertragsbedingungen · Vollmacht (nur bei Pos. 016/017, nicht bei Enni/SWD) |
| PV | Deckblatt · Überblick + Team · Festpreisangebot (0,00 % USt.) · Wirtschaftlichkeit (3 Seiten, nicht ausgeblendet) · Auftragserteilung · Vertragsbedingungen · Vollmacht (nur bei 017) |
| KL | Deckblatt · Überblick + Team · Festpreisangebot · Auftragserteilung · Vertragsbedingungen (mit „Hinweis zur Kältetechnik") · Vollmacht nur mit 016/017 |
| WB | Deckblatt · Überblick + Team · Festpreisangebot · Auftragserteilung · Vertragsbedingungen · Vollmacht (immer, v34) |

Kopfzeile auf jeder Seite (Randzone der Engine): „Angebot-Nr. <Nr> · <Vorname Nachname bzw.
Firma>" links, „SEITE x VON y" rechts – auch auf dem Deckblatt. Fußzeile fünfspaltig
(Anschrift · Geschäftsführung · Kontakt · Bankverbindung · Steuerdaten) aus `pdf_export.FUSSZEILE`,
Bankverbindung je Bank in einer Zeile („Sparkasse Duisburg · IBAN: … · BIC: …").

### 11.2 Deckblatt und Infokasten

Logo links, Award-Badge „German Energy Awards Winner 2026" rechts mit Link
(`https://www.germanenergyawards.com/interview/friondo-gmbh`, „Mehr dazu im Interview ›"),
Titelbild je Sparte (`app/static/pdf/bilder/titel-<sparte>.jpg`) mit dunklem Verlauf, Eyebrow/Titel/
Untertitel wörtlich (`pdf_kontext.SPARTEN`): WP „ANGEBOT · WÄRMEPUMPE" / „Ihr individuelles
Wärmepumpen-Angebot zum Festpreis" / „Effizienz, Komfort und zukunftssicher"; PV „ANGEBOT ·
PV-ANLAGE" / „Ihr individuelles PV-Angebot zum Festpreis" / „Eigener Strom, mehr Unabhängigkeit";
KL „ANGEBOT · KLIMAANLAGE" / „Ihr individuelles Klimaanlagen-Angebot zum Festpreis" / „Kühlen,
heizen und wohlfühlen"; WB „ANGEBOT · WALLBOX" / „Ihr individuelles Wallbox-Angebot zum
Festpreis" / „Laden zu Hause – einfach und sicher". Die „## "-Titelzeilen der Vortext-Textblöcke
werden im Layout v3 NICHT gedruckt (sie bleiben für den fpdf2-Rückfall).
Absenderzeile „Friondo GmbH · Arnold-Overbeck-Str. 63-65 · 47139 Duisburg", Empfängerblock nach
v20 (`anschriften.empfaenger`: Rechnungs-Name ersetzt bei Abweichung den Kundennamen, Zusatz als
eigene Zeile), darunter in 7 pt Grau „Ausführungsort: …" (nur bei abweichender Rechnungsadresse)
und „Lieferanschrift: …" (nur bei Abweichung vom Ausführungsort). Infokasten rechts: Angebot-Nr. ·
Datum · Gültig bis (Datum + 30 Tage, `pdf_kontext.BINDEFRIST_TAGE`) · Ihr Ansprechpartner (AD des
Vorgangs über Erfassung/`vertriebler_id`/`vorgaenge.ad_id`, sonst der vorbereitende Innendienstler;
ohne Person entfällt die Zeile) · Telefon (aus der Benutzerverwaltung; leer → Zeile entfällt) ·
„Ersetzt Angebot AN-… vom TT.MM.JJJJ" (Versionen) · „Kopie von AN-…". Leiste „Mitgliedschaften &
Zertifizierungen" mit SHK Innungsfachbetrieb · E-Handwerk · bdsh · Fachbetrieb Wärmepumpe · Bosch
Premium Partner.

### 11.3 Zuordnung Textblock → Seite

| Textblock / Quelle | Seite im Layout v3 | Regel (`app/pdf_kontext.py`) |
|---|---|---|
| Vortext des Profils/der Sparte (`angebotsprofile.vortext_fuer_angebot`, Override `angebote.vortext_text`) | „Ihr Angebot im Überblick" | `vortext_parsen`: führende „## "-Zeilen entfallen (Deckblatt) · Briefanrede ({briefanrede}) · Absätze vor der ersten Liste → Einleitung · erste Liste („- "/„* ") → Spalte „DARIN ENTHALTEN" (blaue Haken) · „## Warum Friondo?" + zweite Liste → Spalte „WARUM FRIONDO?" (dunkle Haken) · Absätze danach → Schluss („**…**" fett) · „Ihr Friondo-Team"/„Mit herzlichen Grüßen," → Grußzeilen. In beiden Listen wird der Teil vor „ – " fett gesetzt. |
| Nachtext A „Ihre Zahlungsoptionen bei Friondo" | Karte 2 der Auftragserteilung (nur Enni/SWD/Sparkasse DU) | `nachtext_parsen`: erste „## "-Zeile → Untertitel („Barkauf oder Enni Contracting" …), weitere „## "-Zeilen und Absätze → Kartentext; alles unter „## Finanzierung mit Cloover" (Boxen, Beispielraten, Fußnote) entfällt – der Cloover-Block kommt wörtlich aus der Design-Vorlage (nur Profil Standard), Rate/Fußnote aus Teil B; „### "-Abschnitte der A-Seite (Unsere Leistungen, Installationsvoraussetzungen) → Vertragsbedingungen |
| Nachtext B „Installationsvoraussetzungen" (Haftungsbegrenzung · Rücktrittsrecht · Zahlung {zahlungsbedingungen} · Hinweis zur KfW-Förderung / Kältetechnik · Netzbetreiber · Heizkörper-Check) | „Vertragsbedingungen" | „# "-Titel (z. B. „Installationsvoraussetzungen") = übergeordnete blaue Zwischenüberschrift, auch ohne eigene Absätze – nur Seitentitel des Layouts v3 (Zahlungsoptionen, Vertragsbedingungen, Auftragserteilung, Vollmacht …) entfallen; jede „### "-Überschrift = blaue Zwischenüberschrift mit ihren Absätzen; „~ "-Zeilen (PV-Nullsteuersatz) → Fußnote in klein; Bindefrist/AGB/Datenschutz → Schlusskasten (Links klickbar) |
| Nachtext C (Schlussseite) | Schlusskasten der Vertragsbedingungen + Auftragserteilung | „Wir sichern Ihnen …", „Sie haben Fragen …", „Mit freundlichen Grüßen" / „Ihr Friondo-Team" → Schlusskasten; „### Aufschiebende Bedingung" → Auftragserteilung (WP); „Voraussichtliches Datum der Umsetzung …" bzw. „Voraussichtlicher Ausführungszeitraum …" → Linie auf der Auftragsseite; der Satz „Sollte Ihnen das Angebot zusagen, senden Sie uns …" und [UNTERSCHRIFT] entfallen (Auftragsseite trägt Einleitung und Unterschriftszeile des Designs) |
| Zahlungsbedingung (v30, `zahlungsbedingungen.fuer_angebot`) | Abschnitt „Zahlung" + Kurzsatz in Karte 1 | Kurzsatz = erste Zeile, höchstens die ersten zwei Sätze |
| Vollmacht (Nachtext D) | „Vollmacht …" | Wortlaut fest in `pdf_kontext.VOLLMACHT_*` (= Design-Vorlage = Abschnitt 8), Verbrauchsstelle vorbelegt |
| Vermerke (`angebote.vermerke_json`, v9/v10) | Absatz „Hinweise" vor dem Summenblock | erste Zeile = Titel |
| KfW-Ergebnis (`pdf_export._kfw_ergebnis_fuer`) | Förderzeilen im Summenblock + Seite „Ihre KfW-Förderung" (`pdf_kontext_kfw`) | Quote „(xx %)" = Anteil des Zuschusses an der Angebotssumme (wie der Untertitel der KfW-Seite) |
| Wirtschaftlichkeit (`pdf_export.wirtschaftlichkeit_fuer`) | drei Seiten (`pdf_kontext_wirtschaftlichkeit`) | der Platzhalter [WIRTSCHAFTLICHKEIT]/[BEISPIELRECHNUNG] im Nachtext wird im Layout v3 nicht gerendert |
| Cloover (Teil B, `app/cloover.kontext_fuer_pdf`) | Karte 2 + Box „Planbare Monatsraten" + Fußnote | ohne Daten „Monatsrate auf Anfrage", kein Knopf; [CLOOVER] im Nachtext nur fpdf2 |

### 11.4 Festpreisangebot – Kennzeichen-Regeln

- Titel „Festpreisangebot", rechts „Alle Preise in EUR, netto"; Spalten POS. · MENGE · EINH. ·
  BEZEICHNUNG · E-PREIS · G-PREIS (Spaltenkopf wird auf Folgeseiten wiederholt – ohne die
  Überschrift „Festpreisangebot (Fortsetzung)" der Vorlage); Beträge in der Tabelle ohne €-Zeichen.
- Gruppenüberschrift (editierbar, v22) als fette Zwischenzeile; Positionen ohne Gruppe laufen unter
  der vorigen Überschrift.
- Artikeltext: erste Zeile (Bezeichnung) fett, weitere Zeilen normal; Zeilen, die mit „-", „•"
  oder „– " beginnen, werden Aufzählungspunkte „•" (eingerückte „-"-Zeilen als Unterpunkt);
  editierte Texte und Freitextpositionen wie heute.
- Eventualposition → G-Preis „EP." (E-Preis bleibt); bauseits → E- und G-Preis „bauseits";
  Alternativ („in anderem Angebot enthalten") → blauer Hinweiskasten vor der ersten Alternativ-
  Position des Blocks („Die folgenden Positionen sind bereits in Ihrem Angebot <Nr> (<Sparte>)
  enthalten und werden dort berechnet."), Zeile hellgrau, G-Preis „im PV-Angebot" (bzw. Sparte,
  `elektro_pv.pdf_label`), v10-Vermerk unter dem Text; Positionsrabatt → blaue Zeile „− Rabatt
  <x %> (<Betrag>)" bzw. „− Rabatt <Betrag>" unter dem Text (Minus nur im Label), G-Preis nach
  Rabatt; Sonderpreis/manuell geändert ohne Kennzeichen; keine Auslegungszeile (v34).
- Summenblock rechts: „Netto-Summe" · „19,00 % USt." bzw. „0,00 % USt. (§ 12 Abs. 3 UStG)" ·
  Linie · „Gesamt-Betrag" (fett) · bei Gesamtrabatt „− Rabatt <Bezeichnung>" und „= Endbetrag" ·
  bei WP mit Förderblock „− voraussichtliche KfW-Förderung (<xx %>)" (blau) – das Minus steht
  nur im Label, die Beträge ohne Minus („500,00 €", „19.600,00 €") wie die Vorlage – und dunkle Box
  „= Ihr Eigenanteil" mit „Unverbindliche Beispielrechnung – Details und Ablauf auf der nächsten
  Seite."; ohne Förderblock steht der Gesamt-Betrag (ohne Rabatt) bzw. „= Endbetrag" (mit Rabatt)
  in der dunklen Box. Zahlen ausschließlich aus `Angebot.summen()`.

### 11.5 Auftragserteilung (wörtlich aus der Design-Vorlage)

„Sollte Ihnen das Angebot zusagen, beauftragen Sie uns bequem online – oder senden Sie uns das
unterschriebene Angebot per Post zurück." · Karte 1 „BARKAUF – Online beauftragen" mit Kurzsatz
der Zahlungsbedingung und Knopf „Jetzt online beauftragen ›" (nur mit `BASIS_URL` aus der .env,
aktiver Fern-Signatur und gültigem Token am Angebot) bzw. „Per E-Mail beauftragen ›"
(`mailto:angebot@friondo.de?subject=Auftrag <Nr>`) · Karte 2: Standard „FINANZIERUNG MIT
CLOOVER – Online beauftragen & finanzieren", „Mit der Ersparnis Ihrer neuen Anlage finanzieren
Sie die Anlage.", „ab <Rate> € / Monat*", „Laufzeit <n> Jahre · Ihre Finanzierungsanfrage ist
bereits angelegt – nur noch bestätigen." (zweiter Halbsatz nur mit Link), Knopf „Finanzierung
abschließen ›" + QR; ohne Rate „Monatsrate auf Anfrage"; Enni „ENNI CONTRACTING", SWD
„CONTRACTING", Sparkasse DU „FINANZIERUNG MIT SPARKASSE DUISBURG" mit Untertitel/Text aus dem
Nachtext A (der Cloover-Slogan „Saubere Energie. Faire Raten. Maximale Freiheit." der v9-Seeds wird dort
herausgefiltert – er gehört nur zum Cloover-Block des Profils Standard; die Textblöcke bleiben unverändert)
· Block „Finanzierung mit Cloover – Saubere Energie. Faire Raten. Maximale Freiheit."
mit den Boxen „Sofort starten" (Keine Anzahlung, Keine Grundbuchbelastung, Schnelle - digitale
Prüfung, Finanzierungszusage in wenigen Minuten, 100 % digital, Kein Papierkram und keine
Banktermine), „Planbare Monatsraten – Ihre Rate für dieses Angebot:" (• ab <Rate> € pro Monat mit
Förderung* · • ab <Rate> € pro Monat ohne Förderung · So bleibt Ihr Budget flexibel und Ihre
Energiekosten sinken langfristig.), „Maximale Flexibilität" (Kostenlose Sondertilgungen ·
Vorzeitige Rückzahlung ohne Strafgebühren · Individuell anpassbare Laufzeiten), „Ihre Vorteile"
(Sofort investieren · Monatlich entspannt zahlen · Energiekosten senken · Unabhängiger werden ·
Kundenzufriedenheit: 4,8 von 5 – „Dank Cloover konnten wir unsere <Wärmepumpe|PV-Anlage|
Klimaanlage|Wallbox> einfach, fair und transparent finanzieren.") und der Fußnote aus Teil B
(nur Profil Standard) · „Beauftragung per Post": „Senden Sie uns das unterschriebene Angebot an:
Friondo GmbH, Arnold-Overbeck-Str. 63-65, 47139 Duisburg – oder eingescannt an info@friondo.de."
· WP: „Aufschiebende Bedingung: …" (Nachtext C) und „Voraussichtliches Datum der Umsetzung:
____, liegt innerhalb des Bewilligungszeitraum nach Nummer 9.4.1." · KL/WB: „Voraussichtlicher
Ausführungszeitraum: ____" (aus dem Nachtext C) · Unterschriftszeile „Ort, Datum" /
„Unterschrift des Auftraggebers" – Vor-Ort-Signatur: Bild auf der Linie, Zeitstempel über
„Ort, Datum", darunter „<Name> · signiert am TT.MM.JJJJ HH:MM".

### 11.6 Vortexte PV/KL/WB (v36, Migration `angebotsprofile.migration_v36_texte`)

Die Design-Wortlaute (`PV_VORTEXT_V36`, `KL_VORTEXT_V36`, `WB_VORTEXT_V36` in
`app/angebotsprofile.py`) ersetzen die Vortexte „Friondo PV/KL/WB Standard"; die bisherigen
Fassungen bleiben als Textblock „<Name> (bis v35)". WP bleibt beim heutigen Text (Abschnitt 3),
Enni/SWD/Sparkasse DU behalten ihre Vortexte.

- **PV:** „vielen Dank für Ihr Vertrauen in die Friondo GmbH. Sie haben eine zukunftssichere
  Entscheidung getroffen – eine eigene Photovoltaikanlage senkt Ihre Stromkosten, macht Sie
  unabhängiger von steigenden Energiepreisen und steigert den Wert Ihrer Immobilie." · Darin
  enthalten: Ihre individuelle PV-Anlage – Module, Wechselrichter und Speicher passend zu Dach und
  Verbrauch · Detaillierte Installationsleistungen – fachgerecht, sauber und termingerecht ·
  Transparent und Festpreis – klar verständlich und ohne versteckte Kosten · Unser Rundum-Sorglos-
  Service – von der Planung bis zur Inbetriebnahme · Warum Friondo?: Fachkompetenz & Qualität – Als
  Meisterbetrieb, Mitglied der Innung und VDI-zertifiziertes Fachunternehmen setzen wir auf höchste
  Standards. · Mitglied im Bundesverband des Solarhandwerks – Geprüfte Fachkompetenz für Planung,
  Montage und Netzanschluss Ihrer Solaranlage. · Persönliche Beratung – Wir begleiten Sie von der
  ersten Idee bis zur perfekten Lösung für Ihr Zuhause. · Effizienz & Nachhaltigkeit – Unsere
  Systeme senken Ihren Energieverbrauch spürbar und steigern den Wert Ihrer Immobilie. · Alles aus
  einer Hand – Planung, Installation, Anmeldung und Service aus einem Haus. · Schluss: „Wir sind auf
  Photovoltaik spezialisiert und gehören in der Region zu den führenden Anbietern. Lassen Sie uns
  gemeinsam Ihren eigenen Strom erzeugen!" · „Ihr Friondo-Team"
- **KL:** Einleitung „… Sie haben eine gute Entscheidung getroffen – eine moderne Split-Klimaanlage
  sorgt im Sommer für angenehme Kühle, heizt in der Übergangszeit effizient und verbessert die
  Luftqualität in Ihren Räumen." · „Ihre individuelle Klimaanlage – Außen- und Innengeräte passend
  zu Raumgröße und Nutzung" (+ die drei gemeinsamen Punkte) · Warum: Fachkompetenz & Qualität ·
  „Bosch-zertifizierter Profi für Split-Klimageräte – Geschulte Kältetechniker mit Sachkundenachweis
  nach ChemKlimaschutzV." · Persönliche Beratung · Effizienz & Nachhaltigkeit · Alles aus einer Hand
  · Schluss „Wir sind auf Klimatechnik spezialisiert und gehören in der Region zu den führenden
  Anbietern. Lassen Sie uns gemeinsam für Ihr Wohlfühlklima sorgen!"
- **WB:** Einleitung „… Sie haben eine praktische Entscheidung getroffen – mit einer eigenen Wallbox
  laden Sie Ihr Elektroauto sicher, schnell und günstig zu Hause, auf Wunsch mit Ihrem eigenen
  Solarstrom." · „Ihre individuelle Wallbox – Ladeleistung und Standort passend zu Fahrzeug und
  Hausanschluss" (+ drei gemeinsame Punkte) · Warum: Fachkompetenz & Qualität · „Qualifizierter
  E-Handwerk-Fachbetrieb der Innung – Eingetragener Elektrofachbetrieb mit Netzbetreiber-Zulassung
  für Ladeinfrastruktur." · Persönliche Beratung · Effizienz & Nachhaltigkeit · Alles aus einer Hand ·
  Schluss „Wir sind auf Elektromobilität und Ladeinfrastruktur spezialisiert. Lassen Sie uns gemeinsam
  Ihr Zuhause zur Ladestation machen!"

### 11.7 Abweichungen Layout v3 ↔ Design-Vorlagen (bewusst, siehe PLAN_V22 „Befund Design-Vorlagen")

PV mit 0 % USt. statt 19 % · Vollmacht nur nach Regel (016/017, WB immer) statt in jedem Angebot ·
Eventualposition „EP." statt „0,00" · Wirtschaftlichkeitsseiten PV ergänzt · Seitenzahl in der
Randzone (auch Deckblatt) · „Festpreisangebot (Fortsetzung)" entfällt (wiederholter Spaltenkopf) ·
Empfängerblock mit Anrede („Herr Max Mustermann", v20) statt „Max Mustermann" · WP-Vortext bleibt
der heutige Text (mit „Anbei erhalten Sie … Darin enthalten sind:" und „VDI 4650" – die Vorlage
sagt „VDI 4645") · KL-Vertragsbedingungen mit „Hinweis zur Kältetechnik" (v24) und
„Voraussichtlicher Ausführungszeitraum" (die Vorlage hat beides nicht) · Cloover-Beispielraten
„ab 129 € / 250 €" durch die berechnete Rate bzw. „Monatsrate auf Anfrage" ersetzt, Fußnote aus
Teil B · Links `friondo.de/beauftragung` und `app.cloover.com/apply` durch Fern-Signatur/E-Mail bzw.
`checkout_link` ersetzt · Gruß im Schlusskasten ohne Komma („Mit freundlichen Grüßen") wie die
Vorlage · Teamfoto 80 mm statt 92 mm hoch (Platz auf Seite 2 mit dem längeren WP-Vortext).
