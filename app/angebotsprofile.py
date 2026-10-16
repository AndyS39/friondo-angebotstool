# Angebotsprofile (v9, Phase 53): bündeln je Vertriebskanal den Nachtext-
# Block, Positionsregeln und Versandregeln. Auto-Auswahl über den Kanal des
# Kunden (Teilstring-Abgleich der Profil-Kanalwerte), Fallback Standard.
# Die Textblöcke (Nach-/Vortexte) sind in der Parametrierung editierbar;
# die Konstanten hier sind die Seed-Inhalte der Migration und zugleich der
# Fallback, solange keine Blöcke in der Datenbank liegen.

import re

from sqlalchemy.orm import Session

from app.models import Angebot, Kunde, Profil, Textblock

ENNI_CC = "energieberatung@enni.de"

POS_162_TEXT = (
    "Ihr intelligentes Messsystem (iMSys) – der Schlüssel zur smarten "
    "Energieversorgung. Neuer Zweiwegezähler inkl. Smart Meter (Zählertausch) "
    "und dynamischer Stromtarif ‚enni.flexstrom' direkt über die ENNI.\n"
    "https://www.enni.de/energie-und-wasser/strom/flexstrom/")
POS_162_BEZEICHNUNG = ("Voranmeldung ‚iMSys' und dynamischer Stromtarif "
                       "‚enni.flexstrom'")

# --- Standard-Vortext (bisheriger fester Vortext, 1:1) ---------------------
# Konventionen: "## " fette Titelzeile · "- " Haken-Zeile · "* " Haken-Zeile
# mit fettem Anfang bis " – " · "**…**" fetter Absatz · {briefanrede} Anrede.
STANDARD_VORTEXT = """## Ihr individuelles Wärmepumpen-Angebot zum Festpreis
## Effizienz, Komfort und zukunftssicher

{briefanrede}

vielen Dank für Ihr Vertrauen in die Friondo GmbH. Sie haben eine zukunftssichere Entscheidung getroffen – eine moderne Wärmepumpe senkt Ihre Energiekosten, steigert den Wohnkomfort und macht Sie unabhängiger von fossilen Brennstoffen.

Anbei erhalten Sie Ihr maßgeschneidertes Angebot. Darin enthalten sind:

- Ihre individuelle Wärmepumpe – optimal dimensioniert für Ihre Immobilie
- Detaillierte Installationsleistungen – fachgerecht, sauber und termingerecht
- Transparent und Festpreis – klar verständlich und ohne versteckte Kosten
- Unser Rundum-Sorglos-Service – von der Planung bis zur Inbetriebnahme

## Warum Friondo?

* Fachkompetenz & Qualität – Als Meisterbetrieb, Mitglied der Innung und VDI-zertifiziertes Fachunternehmen setzen wir auf höchste Standards.
* Zertifizierte Sachkundige für Wärmepumpensysteme nach VDI 4650 – Fundiertes Fachwissen und tiefgehender Expertise der Wärmepumpentechnik.
* Persönliche Beratung – Wir begleiten Sie von der ersten Idee bis zur perfekten Lösung für Ihr Zuhause.
* Effizienz & Nachhaltigkeit – Unsere Systeme senken Ihren Energieverbrauch spürbar und steigern den Wert Ihrer Immobilie.
* Fördermittel-Check & Unterstützung – Wir helfen Ihnen, maximale staatliche Zuschüsse zu nutzen.

**Wir sind auf Wärmepumpen spezialisiert und gehören in der Region zu den führenden Anbieter.**

Lassen Sie uns gemeinsam Ihre Heizung zukunftsfähig machen!

Ihr Friondo-Team"""

# --- Nachtext-Blöcke -------------------------------------------------------
# Konventionen: "# " Seitenüberschrift · "## " fette Zwischenzeile (10 pt) ·
# "### " fette Absatz-Überschrift (9 pt) · "---" allein = Seitenumbruch ·
# "~ " kleine kursive Fußnote · "[UNTERSCHRIFT]" = Ort/Datum-Block (inkl.
# elektronischer Signatur). Aufeinanderfolgende Zeilen bilden EINEN Absatz.

_RECHT_UND_ZAHLUNG = """### Haftungsbegrenzung
Technische und kaufmännische Angaben sind freibleibend. Sie werden erst durch eine nachfolgende Auftragsbestätigung verbindlich.

### Rücktrittsrecht im Zusammenhang mit Technischer Feinplanung
Die in diesem Vertrag vorgesehenen Verpflichtungen und (Liefer-)Leistungen setzen eine eingehende technische Feinplanung voraus, um sicherzustellen, dass das Vorhaben zu den vereinbarten Bedingungen umgesetzt werden kann. Sollte die technische Feinplanung ergeben, dass die Umsetzung des Vorhabens technisch nicht möglich ist oder nur mit erheblichem Mehraufwand erfolgen kann, ist jede Vertragspartei – abweichend der AGB von Friondo – berechtigt, von dem Vertrag zurückzutreten. Ein entsprechender Rücktritt ist innerhalb von sechs (6) Wochen ab Kenntnisnahme in Textform gegenüber der jeweils anderen Vertragspartei zu erklären.

### Zahlung
{zahlungsbedingungen}"""
# v30 (PLAN_V18 Phase 150): der bisherige feste Zahlungsabsatz („Eine Anzahlung
# von 50% des Angebotsbetrags ist spätestens 14 Tage vor Arbeitsbeginn …“) ist
# Eintrag 1 der Tabelle zahlungsbedingungen (app.zahlungsbedingungen.STANDARD_ABSATZ);
# der Platzhalter {zahlungsbedingungen} wird beim PDF-Rendern durch den Text der
# am Angebot gewählten Zahlungsbedingung ersetzt (pdf_export._nachtext_rendern).
# Die Überschrift „Zahlung“ bleibt im Textblock. Alle Seed-Konstanten (WP/PV/KL)
# bauen auf _RECHT_UND_ZAHLUNG auf und tragen den Platzhalter damit ebenfalls.
PLATZHALTER_ZAHLUNG = "{zahlungsbedingungen}"

_KFW_HINWEIS = """### Hinweis zur KfW-Förderung
Der Wechsel zu einer klimafreundlichen Heizlösung kann unter bestimmten Voraussetzungen durch Förderprogramme der Bundesregierung unterstützt werden. Im Rahmen des Programms „Heizungsförderung für Privatpersonen – Wohngebäude“ (Programmnummer 458) erfolgt die Förderung über die Kreditanstalt für Wiederaufbau (KfW).

Bitte beachten Sie, dass weder der Anspruch auf Fördermittel noch deren konkrete Höhe garantiert werden kann. Die abschließende Entscheidung über Bewilligung und Umfang der Förderung liegt ausschließlich bei der KfW.

Die Ihnen kommunizierte, voraussichtliche Förderhöhe basiert auf den Angaben, die im Beratungsgespräch erfasst wurden. Für die Richtigkeit und Vollständigkeit dieser Informationen übernimmt Friondo keine Haftung. Zudem wird bestätigt, dass sich die Antragsteller bei mehreren am Vorhaben beteiligten Investoren über die Verteilung der Förderbeträge einvernehmlich verständigt haben.

Eine Kombination bzw. Kumulierung der KfW-Förderung mit der steuerlichen Förderung gemäß § 35 EStG ist ausgeschlossen. Antragsteller sind verpflichtet, für dieselbe Maßnahme keinen zusätzlichen Antrag auf steuerliche Förderung zu stellen. Voraussetzung für die Förderung von Wärmepumpen ist außerdem, dass am vorgesehenen Installationsort kein Anschluss- oder Benutzungszwang an ein Wärmenetz besteht. Die Prüfung dieser Voraussetzung obliegt dem Kunden und muss vor Auftragserteilung erfolgen."""

_BINDUNG = """Wir halten uns freibleibend 30 Tage an dieses Angebot gebunden.
Es gelten unsere Allgemeinen Geschäftsbedingungen, diese sind zu finden unter: https://friondo.de/AGB
Informationen zu unserem Datenschutz finden Sie unter: https://friondo.de/Datenschutz"""

_ABSCHLUSS = """Wir sichern Ihnen eine fach- und zeitgerechte Ausführung aller angebotenen Leistungen zu.

Sie haben Fragen oder wünschen weitere Informationen? Rufen Sie uns an - wir sind für Sie da.

Mit freundlichen Grüßen,

Ihr Friondo-Team

Sollte Ihnen das Angebot zusagen, senden Sie uns bitte zur Auftragserteilung das unterschriebene Angebot zurück.

### Aufschiebende Bedingung:
Dieser Vertrag tritt hinsichtlich der Liefer- und Leistungspflichten zur Umsetzung, erst und nur insoweit in Kraft, wenn und soweit die KfW den Antrag zur Förderung Heizungstausch BEG EM bewilligt und die Förderung mit einer Zusage gegenüber der antragstellenden Vertragspartei zugesagt hat (aufschiebende Bedingung). Die antragstellende Vertragspartei wird die jeweils andere Vertragspartei über den Eintritt und den Umfang des Eintritts der Bedingung unverzüglich in Kenntnis setzen. Die Förderzusage löst dann direkt den Vorhabensbeginn aus.

Voraussichtliches Datum der Umsetzung: ______________ ,liegt innerhalb des Bewilligungszeitraum nach Nummer 9.4.1.

[UNTERSCHRIFT]"""

_ANMELDUNG_NETZBETREIBER = """### Anmeldung der Wärmepumpenanlage bzw. PV-Anlage beim Netzbetreiber / Energieversorger
Die Anmeldung der Wärmepumpenanlage bzw. PV-Anlage beim zuständigen Netzbetreiber bzw. Energieversorger wird durch den Auftragnehmer nach Installation der Anlage und Vorliegen der hierfür erforderlichen technischen Daten unverzüglich veranlasst und an die zuständigen Stellen übermittelt.

Die weitere Bearbeitung der Anmeldung, insbesondere Genehmigungen, Freigaben, technische Prüfungen, Terminvergaben sowie gegebenenfalls erforderliche Maßnahmen wie Zählerwechsel, Anpassungen am Hausanschluss oder sonstige Arbeiten im Verantwortungsbereich des Netzbetreibers oder Energieversorgers, erfolgt ausschließlich durch diese Stellen.

Der Auftragnehmer hat keinen Einfluss auf Bearbeitungsdauer, Terminierung oder Durchführung der vorgenannten Maßnahmen durch Netzbetreiber oder Energieversorger. Etwaige Verzögerungen, die aus der Bearbeitung oder Durchführung durch Netzbetreiber oder Energieversorger entstehen, stellen keinen Mangel der Leistung des Auftragnehmers dar und begründen keine Verzögerung der vertraglich geschuldeten Leistungen.

Die Leistung des Auftragnehmers gilt mit der fachgerechten Installation und betriebsbereiten Herstellung der Anlage gemäß Leistungsbeschreibung als erbracht. Die weitere Bearbeitung der Netzbetreiberanmeldung oder der Austausch bzw. die Anpassung von Zähleinrichtungen durch Dritte ist nicht Bestandteil der vertraglichen Leistungspflicht des Auftragnehmers.

Ein Zurückbehaltungsrecht, eine Minderung oder ein Einbehalt von Rechnungsbeträgen, insbesondere der Schlussrechnung, kann aus einer noch ausstehenden Bearbeitung oder Durchführung der Anmeldung durch Netzbetreiber oder Energieversorger nicht abgeleitet werden."""

_LEISTUNGEN_UND_VORAUSSETZUNGEN = """### Unsere Leistungen
Wir planen, liefern und installieren für Sie die gewünschte Wärmepumpe. Anhand Ihrer angegebenen Informationen planen wir die geeignete Anlage für Ihre Bedürfnisse. In der Regel findet ein vor Ort Termin statt, um ein detailliertes Angebot erstellen zu können.

Bestimmte bauliche Gegebenheiten setzen wir bei der Planung voraus und orientieren uns dabei an übliche Rahmenbedingungen unserer Kunden. Bitte informieren Sie uns, falls wir spezielle Leistungen berücksichtigen müssen für Ihr Objekt.

### Installationsvoraussetzungen
Mit Ihrer Auftragserteilung bestätigen Sie, dass diese Voraussetzungen gegeben sind oder Sie diese durch uns beauftragen. Bei Nichteinhaltung müssen Sie mit Zusatzkosten rechnen. Gesonderte Positionen, die nicht im Angebot aufgeführt sind, werden zusätzlich berechnet."""

_HEIZKOERPER_CHECK = """### Durchführung eines Heizkörper-Checks
Wärmepumpen liefern grundsätzlich niedrigere Heizwassertemperaturen als Gas- oder Ölkessel. Damit es trotz dieser vglw. niedrigen Heizwassertemperaturen auch im tiefsten Winter behaglich warm bleibt, prüfen wir, ob Ihre Heizflächen für einen solchen Betrieb geeignet sind und bestimmen gegebenenfalls die benötigten Ersatzheizkörper.

Nach der Heizlastberechnung ihres Gebäudes und der anschließenden Überprüfung Ihrer Heizflächen werden wir mit dem Ergebnis der Prüfung auf Sie zukommen. Sofern bisher nicht eingeplante Ersatzheizkörper erforderlich sind, erhalten Sie ein Angebot mit passenden Heizkörpern zur Deckung Ihres Wärmebedarfs.

Sollten in Ihrem Gebäude ausschließlich Fußbodenheizungen verbaut sein, ist der Einbau einer Wärmepumpe in der Regel unproblematisch. Dennoch kann es in Einzelfällen erforderlich sein, einen Heizkörper-Check durchzuführen, um die korrekte Dimensionierung Ihres neuen Heizsystems zu gewährleisten."""

STANDARD_NACHTEXT = """# Ihre Zahlungsoptionen bei Friondo
## Barkauf oder Finanzierung
Saubere Energie. Faire Raten. Maximale Freiheit.

## Finanzierung mit Cloover
Investieren Sie jetzt in Ihre Energie- oder Wärmelösung – ohne hohe Einmalzahlung und bequem in festen Monatsraten über bis zu 20 Jahre.

### Sofort starten
• Keine Anzahlung, Keine Grundbuchbelastung, Schnelle - digitale Prüfung, Finanzierungszusage in wenigen Minuten, 100 % digital, Kein Papierkram und keine Banktermine

[CLOOVER]

So bleibt Ihr Budget flexibel und Ihre Energiekosten sinken langfristig.

### Maximale Flexibilität
• Kostenlose Sondertilgungen
• Vorzeitige Rückzahlung ohne Strafgebühren
• Individuell anpassbare Laufzeiten

### Ihre Vorteile
• Sofort investieren · Monatlich entspannt zahlen · Energiekosten senken · Unabhängiger werden

### Kundenzufriedenheit: 4,8 von 5
„Dank Cloover konnten wir unsere Wärmepumpe einfach, fair und transparent finanzieren.“

Starten Sie jetzt mit Friondo und Cloover in eine nachhaltige Zukunft.
---
# Installationsvoraussetzungen
""" + _RECHT_UND_ZAHLUNG + "\n\n" + _KFW_HINWEIS + "\n\n" + _BINDUNG + """
---
""" + _ABSCHLUSS

ENNI_NACHTEXT = """# Ihre Zahlungsoptionen bei Friondo
## Barkauf oder Enni Contracting
Saubere Energie. Faire Raten. Maximale Freiheit.

""" + _LEISTUNGEN_UND_VORAUSSETZUNGEN + """
---
""" + _RECHT_UND_ZAHLUNG + "\n\n" + _ANMELDUNG_NETZBETREIBER + """
---
""" + _KFW_HINWEIS + "\n\n" + _HEIZKOERPER_CHECK + "\n\n" + _BINDUNG + """
---
""" + _ABSCHLUSS

SWD_NACHTEXT = """# Ihre Zahlungsoptionen bei Friondo
## Barkauf oder Contracting
Saubere Energie. Faire Raten. Maximale Freiheit.

# Installationsvoraussetzungen
""" + _RECHT_UND_ZAHLUNG + """
---
""" + _KFW_HINWEIS + "\n\n" + _BINDUNG + """
---
""" + _ABSCHLUSS

SPARKASSE_NACHTEXT = """# Ihre Zahlungsoptionen bei Friondo
## Barkauf oder Finanzierung
Saubere Energie. Faire Raten. Maximale Freiheit.

## Finanzierung mit Sparkasse Duisburg

""" + _LEISTUNGEN_UND_VORAUSSETZUNGEN + """
---
""" + _RECHT_UND_ZAHLUNG + "\n\n" + _ANMELDUNG_NETZBETREIBER + """
---
""" + _KFW_HINWEIS + "\n\n" + _HEIZKOERPER_CHECK + "\n\n" + _BINDUNG + """
---
""" + _ABSCHLUSS

# --- v13-PV (PLAN_V13 Phase 78): PV-Texte nach Muster AN261699 -------------
PV_VORTEXT = """## Ihr individuelles PV-Angebot zum Festpreis
## Effizienz, Komfort und zukunftssicher

{briefanrede}

vielen Dank für Ihr Vertrauen in die Friondo GmbH. Sie haben eine zukunftssichere Entscheidung getroffen – eine moderne PV-Anlage sorgt für Unabhängigkeit und Kosteneinsparungen.

Anbei erhalten Sie Ihr maßgeschneidertes Angebot.

- Ihre individuelle PV-Anlage – optimal dimensioniert für Ihre Immobilie
- Detaillierte Installationsleistungen – fachgerecht, sauber und termingerecht
- Transparent zum Festpreis – klar verständlich und ohne versteckte Kosten
- Unser Rundum-Sorglos-Service – von der Planung bis zur Inbetriebnahme

## Warum Friondo?

* Fachkompetenz & Qualität – Als Meisterbetrieb, Mitglied der Innung und VDI-zertifiziertes Fachunternehmen setzen wir auf höchste Standards.
* Zertifizierte Sachkundige – Fundiertes Fachwissen und tiefgehende Expertise für energieeffiziente und leistungsstarke PV-Systeme.
* Persönliche Beratung – Wir begleiten Sie von der ersten Idee bis zur optimalen PV-Lösung für Ihr Zuhause oder Unternehmen.
* Effizienz & Nachhaltigkeit – Unsere modernen PV-Anlagen reduzieren den Energieverbrauch spürbar und steigern Ihre Autarkie.
* Fördermittel-Check & Unterstützung – Wir helfen Ihnen, staatliche Zuschüsse bestmöglich zu nutzen.

**Wir sind auf PV-Anlagen, Wärmepumpen und Klimaanlage spezialisiert und gehören in der Region zu den führenden Anbieter.**

Lassen Sie uns gemeinsam Ihr Objekt zukunftsfähig machen!

Mit herzlichen Grüßen,
Ihr Friondo-Team"""

_PV_NULLSTEUER = """~ *Anwendung des Nullsteuersatzes: § 12 Absatz 3 UStG regelt, dass auf die Lieferung von Photovoltaikanlagen ab 1. Januar 2023 u. a. dann keine Umsatzsteuer mehr anfällt, wenn diese auf oder in der Nähe eines Wohngebäudes installiert werden (Nullsteuersatz)."""

_PV_ABSCHLUSS = """Wir sichern Ihnen eine fach- und zeitgerechte Ausführung aller angebotenen Leistungen zu.

Sie haben Fragen oder wünschen weitere Informationen? Rufen Sie uns an - wir sind für Sie da.

Mit freundlichen Grüßen,

Ihr Friondo-Team

Sollte Ihnen das Angebot zusagen, senden Sie uns bitte zur Auftragserteilung das unterschriebene Angebot zurück.

[UNTERSCHRIFT]"""

# [WIRTSCHAFTLICHKEIT] = die drei gestalteten Wirtschaftlichkeitsseiten (v22,
# app/wirtschaftlichkeit_pdf.py); der alte Platzhalter [BEISPIELRECHNUNG]
# (v16) bleibt im Renderer als Alias gültig
_PV_BEISPIEL = "[WIRTSCHAFTLICHKEIT]"
_PV_BEISPIEL_ALT = "[BEISPIELRECHNUNG]"

PV_STANDARD_NACHTEXT = _PV_NULLSTEUER + """

# Ihre Zahlungsoptionen bei Friondo
## Barkauf oder Finanzierung
Saubere Energie. Faire Raten. Maximale Freiheit.

## Finanzierung mit Cloover
Investieren Sie jetzt in Ihre Energie- oder Wärmelösung – ohne hohe Einmalzahlung und bequem in festen Monatsraten über bis zu 20 Jahre.

### Sofort starten
• Keine Anzahlung, Keine Grundbuchbelastung, Schnelle - digitale Prüfung, Finanzierungszusage in wenigen Minuten, 100 % digital, Kein Papierkram und keine Banktermine

[CLOOVER]

So bleibt Ihr Budget flexibel und Ihre Energiekosten sinken langfristig.

### Maximale Flexibilität
• Kostenlose Sondertilgungen
• Vorzeitige Rückzahlung ohne Strafgebühren
• Individuell anpassbare Laufzeiten

### Ihre Vorteile
• Sofort investieren · Monatlich entspannt zahlen · Energiekosten senken · Unabhängiger werden

### Kundenzufriedenheit: 4,8 von 5
„Dank Cloover konnten wir unsere PV-Anlage einfach, fair und transparent finanzieren.“

Starten Sie jetzt mit Friondo und Cloover in eine nachhaltige Zukunft.
---
""" + _PV_BEISPIEL + """
---
# Installationsvoraussetzungen
""" + _RECHT_UND_ZAHLUNG + "\n\n" + _BINDUNG + "\n\n" + _PV_ABSCHLUSS


def _pv_variante(kopf: str) -> str:
    """PV-Nachtext der Kanal-Profile: eigener Finanzierungs-Kopf, sonst wie
    PV Standard (ohne KfW-Hinweis/aufschiebende Bedingung – kein Förderblock)."""
    return (_PV_NULLSTEUER + "\n\n" + kopf + "\n---\n" + _PV_BEISPIEL + "\n---\n"
            + _LEISTUNGEN_UND_VORAUSSETZUNGEN.replace("gewünschte Wärmepumpe",
                                                      "gewünschte PV-Anlage")
            + "\n\n" + _RECHT_UND_ZAHLUNG + "\n\n" + _ANMELDUNG_NETZBETREIBER
            + "\n\n" + _BINDUNG + "\n---\n" + _PV_ABSCHLUSS)


PV_SEED_BLOECKE = [
    ("vortext", "Friondo PV Standard", PV_VORTEXT),
    ("nachtext", "Friondo PV Standard", PV_STANDARD_NACHTEXT),
    ("nachtext", "Friondo PV Enni", _pv_variante(
        "# Ihre Zahlungsoptionen bei Friondo\n## Barkauf oder Enni Contracting\n"
        "Saubere Energie. Faire Raten. Maximale Freiheit.")),
    ("nachtext", "Friondo PV SWD", _pv_variante(
        "# Ihre Zahlungsoptionen bei Friondo\n## Barkauf oder Contracting\n"
        "Saubere Energie. Faire Raten. Maximale Freiheit.")),
    ("nachtext", "Friondo PV Sparkasse DU", _pv_variante(
        "# Ihre Zahlungsoptionen bei Friondo\n## Barkauf oder Finanzierung\n"
        "Saubere Energie. Faire Raten. Maximale Freiheit.\n\n"
        "## Finanzierung mit Sparkasse Duisburg")),
]


def seed_pv(session: Session) -> list[str]:
    """v13-PV: PV-Textblöcke nachträglich anlegen (idempotent, je Name)."""
    vorhanden = {(b.art, b.name) for b in session.query(Textblock)}
    neu = 0
    for art, name, text in PV_SEED_BLOECKE:
        if (art, name) not in vorhanden:
            session.add(Textblock(art=art, name=name, text=text))
            neu += 1
    return [f"{neu} PV-Textblöcke (Vor-/Nachtexte PV) angelegt"] if neu else []


def migriere_pv_platzhalter(session: Session) -> list[str]:
    """v22 (PLAN_V15 Phase 101): bestehende PV-Nachtexte von [BEISPIELRECHNUNG]
    auf [WIRTSCHAFTLICHKEIT] umstellen (alle Profile; idempotent – zweiter
    Lauf findet nichts mehr). Umbenannte/zusätzliche Blöcke behalten den
    alten Platzhalter und funktionieren über den Alias weiter."""
    anzahl = 0
    for block in (session.query(Textblock)
                  .filter(Textblock.art == "nachtext",
                          Textblock.name.like("Friondo PV %"))):
        if _PV_BEISPIEL_ALT in (block.text or ""):
            block.text = block.text.replace(_PV_BEISPIEL_ALT, _PV_BEISPIEL)
            anzahl += 1
    return [f"{anzahl} PV-Textblöcke auf [WIRTSCHAFTLICHKEIT] umgestellt"] if anzahl else []


def _pv_block(session: Session, art: str, profil: Profil | None) -> str:
    """PV-Textblock des Profils („Friondo PV <Profil>“), sonst PV Standard."""
    namen = ([f"Friondo PV {profil.name}"] if profil is not None else []) \
        + ["Friondo PV Standard"]
    for name in namen:
        block = (session.query(Textblock)
                 .filter(Textblock.art == art, Textblock.name == name).first())
        if block is not None and block.text.strip():
            return block.text
    return PV_VORTEXT if art == "vortext" else PV_STANDARD_NACHTEXT


def ist_pv(angebot: Angebot) -> bool:
    return (angebot.konfigurator_typ or "WP").upper() == "PV"


# --- v24 (PLAN_V16 Phase 115): Klima-Texte (Klimakonfigurator) --------------
# Entwürfe für das Gegenlesen durch den Innendienst (A14) – Formulierungen zu
# Zertifizierung/Kältemittel sind [ANNAHME]. Kein KfW-/Förderteil, kein
# Platzhalter [WIRTSCHAFTLICHKEIT], keine Vollmacht (Nachtext D), 19 % USt.
# Vortext wörtlich aus PLAN_V16 Phase 115; [Haken] wie bei WP/PV als "- "
# (Haken-Zeile) bzw. "* " (Haken-Zeile mit fettem Anfang bis " – ").
KL_VORTEXT = """## Ihr individuelles Klimaanlagen-Angebot zum Festpreis
## Angenehmes Raumklima – kühlen im Sommer, heizen in der Übergangszeit

{briefanrede}

vielen Dank für Ihr Vertrauen in die Friondo GmbH. Mit einer modernen Split-Klimaanlage von Bosch schaffen Sie an heißen Tagen ein angenehmes Raumklima, heizen effizient in der Übergangszeit und verbessern die Luftqualität in Ihren Räumen.

Anbei erhalten Sie Ihr maßgeschneidertes Angebot. Darin enthalten sind:

- Ihre individuelle Klimaanlage – ausgelegt auf Ihre Räume
- Detaillierte Installationsleistungen – fachgerecht, sauber und termingerecht
- Transparent und Festpreis – klar verständlich und ohne versteckte Kosten
- Unser Rundum-Sorglos-Service – von der Planung bis zur Inbetriebnahme

## Warum Friondo?

* Fachkompetenz & Qualität – Als Meisterbetrieb, Mitglied der Innung und VDI-zertifiziertes Fachunternehmen setzen wir auf höchste Standards.
* Fachgerechte Kältetechnik – Montage, Dichtheitsprüfung und Inbetriebnahme durch geschultes Fachpersonal nach den Vorgaben der F-Gase-Verordnung.
* Persönliche Beratung – Wir begleiten Sie von der ersten Idee bis zur perfekten Lösung für Ihr Zuhause.
* Effizienz & Komfort – Inverter-Technik mit hoher Energieeffizienz, leiser Betrieb und auf Wunsch Steuerung per App.

**Wir sind auf Wärmepumpen und Klimatechnik spezialisiert und gehören in der Region zu den führenden Anbietern.**

Lassen Sie uns gemeinsam für ein angenehmes Raumklima sorgen!

Ihr Friondo-Team"""

# Nachtext A KL = Nachtext A „Ihre Zahlungsoptionen bei Friondo“ mit den drei
# Änderungen aus PLAN_V16: „Klimalösung“, ohne „Planbare Monatsraten“ samt
# Fußnote „*Beispielrate …“, Kundenstimme „unsere Anlage“.
_KL_ZAHLUNGSOPTIONEN = """# Ihre Zahlungsoptionen bei Friondo
## Barkauf oder Finanzierung
Saubere Energie. Faire Raten. Maximale Freiheit.

## Finanzierung mit Cloover
Investieren Sie jetzt in Ihre Klimalösung – ohne hohe Einmalzahlung und bequem in festen Monatsraten über bis zu 20 Jahre.

### Sofort starten
• Keine Anzahlung, Keine Grundbuchbelastung, Schnelle - digitale Prüfung, Finanzierungszusage in wenigen Minuten, 100 % digital, Kein Papierkram und keine Banktermine

[CLOOVER]

So bleibt Ihr Budget flexibel und Ihre Energiekosten sinken langfristig.

### Maximale Flexibilität
• Kostenlose Sondertilgungen
• Vorzeitige Rückzahlung ohne Strafgebühren
• Individuell anpassbare Laufzeiten

### Ihre Vorteile
• Sofort investieren · Monatlich entspannt zahlen · Energiekosten senken · Unabhängiger werden

### Kundenzufriedenheit: 4,8 von 5
„Dank Cloover konnten wir unsere Anlage einfach, fair und transparent finanzieren.“

Starten Sie jetzt mit Friondo und Cloover in eine nachhaltige Zukunft."""

# Nachtext B KL: statt „Hinweis zur KfW-Förderung“ nach „Zahlung“ (wörtlich
# PLAN_V16, [ANNAHME] – Innendienst liest gegen)
_KL_KAELTETECHNIK = """### Hinweis zur Kältetechnik
Die angebotenen Geräte arbeiten mit dem Kältemittel R32. Montage, Evakuierung, Dichtheitsprüfung und Inbetriebnahme erfolgen durch sachkundiges Personal nach den Vorgaben der F-Gase-Verordnung (EU) 2024/573; die Dichtheitsprüfung wird dokumentiert. Die Kältemittel-, Kondensat- und Elektroleitungen sind bis 5 m je Innengerät enthalten; längere Leitungswege sind als eigene Position ausgewiesen. Der Montageort der Außeneinheit wird so gewählt, dass Schall- und Abstandsvorgaben eingehalten werden; die endgültige Festlegung erfolgt in der technischen Feinplanung vor Ort."""

# Nachtext C KL: Schlussseite ohne „Aufschiebende Bedingung“ und ohne die
# Zeile „Voraussichtliches Datum der Umsetzung …“; Unterschriftenblock wie WP
_KL_ABSCHLUSS = """Wir sichern Ihnen eine fach- und zeitgerechte Ausführung aller angebotenen Leistungen zu.

Sie haben Fragen oder wünschen weitere Informationen? Rufen Sie uns an - wir sind für Sie da.

Mit freundlichen Grüßen,

Ihr Friondo-Team

Sollte Ihnen das Angebot zusagen, senden Sie uns bitte zur Auftragserteilung das unterschriebene Angebot zurück.

Voraussichtlicher Ausführungszeitraum: ______________

[UNTERSCHRIFT]"""

_KL_LEISTUNGEN_UND_VORAUSSETZUNGEN = _LEISTUNGEN_UND_VORAUSSETZUNGEN.replace(
    "gewünschte Wärmepumpe", "gewünschte Klimaanlage")

KL_STANDARD_NACHTEXT = _KL_ZAHLUNGSOPTIONEN + """
---
# Installationsvoraussetzungen
""" + _RECHT_UND_ZAHLUNG + "\n\n" + _KL_KAELTETECHNIK + "\n\n" + _BINDUNG + """
---
""" + _KL_ABSCHLUSS


def _kl_variante(kopf: str, mit_leistungen: bool = True) -> str:
    """KL-Nachtext der Kanal-Profile nach dem WP-Muster: Enni/SWD ohne
    Nachtext A (nur Kopf „Barkauf oder … Contracting“), Sparkasse DU mit
    eigenem Finanzierungs-Kopf; Enni/Sparkasse mit „Unsere Leistungen /
    Installationsvoraussetzungen“ (wie WP), SWD ohne. Danach Haftung,
    Rücktrittsrecht, Zahlung, Hinweis zur Kältetechnik, Bindefrist/AGB/
    Datenschutz und die Schlussseite – ohne KfW-Hinweis, ohne Heizkörper-
    Check, ohne Netzbetreiber-Absatz (WP/PV-spezifisch), ohne Vollmacht."""
    if mit_leistungen:
        return (kopf + "\n\n" + _KL_LEISTUNGEN_UND_VORAUSSETZUNGEN + "\n---\n"
                + _RECHT_UND_ZAHLUNG + "\n\n" + _KL_KAELTETECHNIK + "\n\n" + _BINDUNG
                + "\n---\n" + _KL_ABSCHLUSS)
    return (kopf + "\n\n# Installationsvoraussetzungen\n" + _RECHT_UND_ZAHLUNG
            + "\n\n" + _KL_KAELTETECHNIK + "\n\n" + _BINDUNG + "\n---\n" + _KL_ABSCHLUSS)


KL_SEED_BLOECKE = [
    ("vortext", "Friondo KL Standard", KL_VORTEXT),
    ("nachtext", "Friondo KL Standard", KL_STANDARD_NACHTEXT),
    ("nachtext", "Friondo KL Enni", _kl_variante(
        "# Ihre Zahlungsoptionen bei Friondo\n## Barkauf oder Enni Contracting\n"
        "Saubere Energie. Faire Raten. Maximale Freiheit.")),
    ("nachtext", "Friondo KL SWD", _kl_variante(
        "# Ihre Zahlungsoptionen bei Friondo\n## Barkauf oder Contracting\n"
        "Saubere Energie. Faire Raten. Maximale Freiheit.", mit_leistungen=False)),
    ("nachtext", "Friondo KL Sparkasse DU", _kl_variante(
        "# Ihre Zahlungsoptionen bei Friondo\n## Barkauf oder Finanzierung\n"
        "Saubere Energie. Faire Raten. Maximale Freiheit.\n\n"
        "## Finanzierung mit Sparkasse Duisburg")),
]


def seed_kl(session: Session) -> list[str]:
    """v24: KL-Textblöcke nachträglich anlegen (idempotent, je Art + Name;
    vorhandene – ggf. in der Parametrierung bearbeitete – Blöcke bleiben)."""
    vorhanden = {(b.art, b.name) for b in session.query(Textblock)}
    neu = 0
    for art, name, text in KL_SEED_BLOECKE:
        if (art, name) not in vorhanden:
            session.add(Textblock(art=art, name=name, text=text))
            neu += 1
    return [f"{neu} KL-Textblöcke (Vor-/Nachtexte Klima) angelegt"] if neu else []


def _kl_block(session: Session, art: str, profil: Profil | None) -> str:
    """KL-Textblock des Profils („Friondo KL <Profil>“), sonst KL Standard;
    ohne Blöcke in der Datenbank die Seed-Konstanten."""
    namen = ([f"Friondo KL {profil.name}"] if profil is not None else []) \
        + ["Friondo KL Standard"]
    for name in namen:
        block = (session.query(Textblock)
                 .filter(Textblock.art == art, Textblock.name == name).first())
        if block is not None and block.text.strip():
            return block.text
    return KL_VORTEXT if art == "vortext" else KL_STANDARD_NACHTEXT


def ist_kl(angebot: Angebot) -> bool:
    """v24: Klima-Angebot aus dem Klimakonfigurator (konfigurator_typ „KL“)."""
    return (angebot.konfigurator_typ or "WP").upper() == "KL"


# --- v34 (PLAN_V21 Phase 179): Wallbox-Texte (Wallbox-Konfigurator) -----------------
# Vortext wörtlich aus PLAN_V21 „Grundlagen Wallbox“ (TAIFUN-Muster AN261737, Seite 1);
# [Haken] wie bei WP/PV/KL als "- " (Haken-Zeile) bzw. "* " (Haken-Zeile mit fettem
# Anfang bis " – "). Der TAIFUN-„Text vor Position“ („Komplettpaket Wallbox inkl.
# Montage …“) ist ein eigener Absatz am Ende des Vortexts [ANNAHME Plan] – der Seed trägt
# den im Plan zitierten Anfang als ENTWURF; den vollständigen Wortlaut der Excel-
# Textzeile (Import-Protokoll zeigt sie) trägt der Innendienst in Parametrierung →
# Textblöcke nach. Nachtext = B „Installationsvoraussetzungen“ (Haftungsbegrenzung,
# Rücktrittsrecht Feinplanung wie KL, Zahlung mit {zahlungsbedingungen} = v30-Standard,
# Rückfrage 3) + C Schlussseite; die Vollmacht (Nachtext D) rendert pdf_export bei WB
# immer (anhaenge.vollmacht_erforderlich, Rückfrage 4). Kein Nachtext A „Ihre
# Zahlungsoptionen“, kein KfW-/Förderblock, keine Wirtschaftlichkeit. Alle WB-Texte sind
# Entwürfe für das Gegenlesen durch den Innendienst.
WB_KOMPLETTPAKET_TITEL = "Komplettpaket Wallbox inkl. Montage"
WB_KOMPLETTPAKET_TEXT = ("Die Zukunft der Energie beginnt bei Ihnen zuhause – effizient, "
                         "nachhaltig und zuverlässig.")

_WB_VORTEXT_KOPF = """## Ihre individuelle Wallbox zum Festpreis

{briefanrede}

vielen Dank für Ihr Vertrauen in die Friondo GmbH. Mit einer modernen Wallbox laden Sie Ihr Elektrofahrzeug bequem zu Hause, sparen Zeit und machen sich unabhängiger von öffentlichen Ladeinfrastrukturen. So schaffen Sie Komfort, Sicherheit und ein smartes Energiemanagement direkt bei Ihnen vor Ort.

Anbei erhalten Sie Ihr maßgeschneidertes Angebot. Darin enthalten sind:

- Ihre individuelle Wallbox – perfekt abgestimmt auf Ihre Immobilie & Ihren Bedarf
- Fachgerechte Installation – sauber, sicher und termingerecht
- Transparent & zum Festpreis – klar verständlich, ohne versteckte Kosten
- Unser Rundum-Sorglos-Service – von der Planung bis zur Inbetriebnahme

## Warum Friondo?

* Fachkompetenz & Qualität – Als Meisterbetrieb und zertifizierter Fachbetrieb setzen wir auf höchste Standards
* Alles aus einer Hand – Von Photovoltaik bis Energiemanagement – perfekt kombinierbar mit Ihrer Wallbox
* Persönliche Beratung – Wir begleiten Sie von der ersten Idee bis zur fertigen Lösung
* Effizienz & Nachhaltigkeit – Wir helfen Ihnen, Ihr Zuhause energieoptimiert und zukunftssicher zu gestalten
* Fördermittel-Check & Unterstützung – Wir prüfen für Sie mögliche Zuschüsse und Förderungen

Wir sind auf moderne Energiesysteme spezialisiert und gehören in der Region zu den führenden Anbietern von Photovoltaik, Wärmepumpen, Klimaanlagen, Energiemanagement-Systemen und Wallboxen. Lassen Sie uns gemeinsam Ihr Zuhause fit für die Zukunft machen!

Ihr Friondo-Team"""


def wb_vortext(komplettpaket: str | None = None) -> str:
    """Vortext WB mit dem Absatz „Komplettpaket Wallbox inkl. Montage“ am Ende: Text aus der
    Textzeile der Wallbox-Excel (erste Zeile = Überschrift, Rest = Absätze; Nachtrag
    15.10.2026, `import_wallbox.komplettpaket_text`) oder – ohne Datei – der Entwurf."""
    titel, text = WB_KOMPLETTPAKET_TITEL, WB_KOMPLETTPAKET_TEXT
    zeilen = [z.strip() for z in (komplettpaket or "").strip().splitlines()]
    if zeilen:
        if zeilen[0].lower().startswith("komplettpaket"):
            titel, zeilen = zeilen[0], zeilen[1:]
        rest = "\n".join(zeilen).strip()
        if rest:
            text = rest
    return _WB_VORTEXT_KOPF + "\n\n## " + titel + "\n\n" + text


WB_VORTEXT = wb_vortext()   # Entwurf (ohne Excel-Textzeile)

# Nachtext C WB: Schlussseite ohne „Aufschiebende Bedingung“ (keine KfW-Förderung),
# mit „Voraussichtlicher Ausführungszeitraum“ wie KL [ANNAHME]; Unterschriftenblock wie WP
_WB_ABSCHLUSS = """Wir sichern Ihnen eine fach- und zeitgerechte Ausführung aller angebotenen Leistungen zu.

Sie haben Fragen oder wünschen weitere Informationen? Rufen Sie uns an - wir sind für Sie da.

Mit freundlichen Grüßen,

Ihr Friondo-Team

Sollte Ihnen das Angebot zusagen, senden Sie uns bitte zur Auftragserteilung das unterschriebene Angebot zurück.

Voraussichtlicher Ausführungszeitraum: ______________

[UNTERSCHRIFT]"""

# Nachtext B WB: nur „Installationsvoraussetzungen“ (Haftungsbegrenzung, Rücktrittsrecht
# Feinplanung, Zahlung {zahlungsbedingungen}), Bindefrist/AGB/Datenschutz – wie das
# TAIFUN-Muster; kein Hinweis zur Kältetechnik (KL), kein KfW-Hinweis (WP)
WB_STANDARD_NACHTEXT = """# Installationsvoraussetzungen
""" + _RECHT_UND_ZAHLUNG + "\n\n" + _BINDUNG + """
---
""" + _WB_ABSCHLUSS

# v36 (PLAN_V22 Phase 193, Agent B2) [ANNAHME]: für den fpdf2-Rückfall erhält WB Standard einen
# Nachtext A als Kopie des KL-Textes mit „Ihre Wallbox-Lösung“ (v34 hatte für WB bewusst keinen
# Nachtext A); Enni/SWD/Sparkasse DU bleiben ohne Cloover. Im Layout v3 ist der Block wirkungslos
# (der Cloover-Block kommt aus der Design-Vorlage, pdf_kontext.nachtext_parsen überliest [CLOOVER]).
WB_ZAHLUNGSOPTIONEN = _KL_ZAHLUNGSOPTIONEN.replace("Ihre Klimalösung", "Ihre Wallbox-Lösung")
WB_STANDARD_NACHTEXT_V36 = WB_ZAHLUNGSOPTIONEN + "\n---\n" + WB_STANDARD_NACHTEXT

# Nachtexte der Kanal-Profile: Start = Kopie des Standard-Nachtexts [ANNAHME Plan]
WB_SEED_BLOECKE = [
    ("vortext", "Friondo WB Standard", WB_VORTEXT),
    ("nachtext", "Friondo WB Standard", WB_STANDARD_NACHTEXT_V36),   # v36: mit Nachtext A ([CLOOVER])
    ("nachtext", "Friondo WB Enni", WB_STANDARD_NACHTEXT),
    ("nachtext", "Friondo WB SWD", WB_STANDARD_NACHTEXT),
    ("nachtext", "Friondo WB Sparkasse DU", WB_STANDARD_NACHTEXT),
]


def seed_wb(session: Session, komplettpaket: str | None = None) -> list[str]:
    """v34: WB-Textblöcke nachträglich anlegen (idempotent, je Art + Name; vorhandene –
    ggf. in der Parametrierung bearbeitete – Blöcke bleiben). Der Vortext trägt den Absatz
    „Komplettpaket Wallbox inkl. Montage“ wörtlich aus der Textzeile der Wallbox-Excel
    (Nachtrag 15.10.2026; `komplettpaket` übergeben oder aus Artikel-Preislisten/Wallbox/
    gelesen); liegt die Datei nicht vor, bleibt der Entwurf. Ein noch unveränderter
    Entwurfs-Vortext wird beim nächsten Lauf mit Datei auf den Excel-Text gehoben."""
    if komplettpaket is None:
        try:
            from app import import_wallbox
            komplettpaket = import_wallbox.komplettpaket_text()
        except Exception:   # noqa: BLE001 – Textzeile ist Zusatz, nie ein Grund abzubrechen
            komplettpaket = ""
    vortext = wb_vortext(komplettpaket or None)
    bloecke = [("vortext", "Friondo WB Standard", vortext)] + [
        b for b in WB_SEED_BLOECKE if b[0] != "vortext"]
    vorhanden = {(b.art, b.name): b for b in session.query(Textblock)}
    neu = 0
    aktualisiert = 0
    for art, name, text in bloecke:
        block = vorhanden.get((art, name))
        if block is None:
            session.add(Textblock(art=art, name=name, text=text))
            neu += 1
        elif art == "vortext" and block.text == WB_VORTEXT and text != WB_VORTEXT:
            block.text = text          # Entwurf → wörtlicher Text aus der Excel-Textzeile
            aktualisiert += 1
    meldungen = []
    if neu:
        meldungen.append(f"{neu} WB-Textblöcke (Vor-/Nachtexte Wallbox) angelegt"
                         + ("" if komplettpaket else " – Absatz „Komplettpaket“ als Entwurf "
                            "(Wallbox-Excel nicht gefunden)"))
    if aktualisiert:
        meldungen.append("WB-Vortext: Absatz „Komplettpaket Wallbox inkl. Montage“ aus der "
                         "Wallbox-Excel übernommen")
    return meldungen


def _wb_block(session: Session, art: str, profil: Profil | None) -> str:
    """WB-Textblock des Profils („Friondo WB <Profil>“), sonst WB Standard; ohne
    Blöcke in der Datenbank die Seed-Konstanten."""
    namen = ([f"Friondo WB {profil.name}"] if profil is not None else []) \
        + ["Friondo WB Standard"]
    for name in namen:
        block = (session.query(Textblock)
                 .filter(Textblock.art == art, Textblock.name == name).first())
        if block is not None and block.text.strip():
            return block.text
    if art == "vortext":
        return WB_VORTEXT
    # v36 (Phase 193): Standard-Profil mit Nachtext A (Cloover), Kanal-Profile ohne
    standard = profil is None or (profil.regel_kennung or "standard").strip().lower() == "standard"
    return WB_STANDARD_NACHTEXT_V36 if standard else WB_STANDARD_NACHTEXT


def ist_wb(angebot: Angebot) -> bool:
    """v34: Wallbox-Angebot aus dem Wallbox-Konfigurator (konfigurator_typ „WB“)."""
    return (angebot.konfigurator_typ or "WP").upper() == "WB"


# --- v36 (PLAN_V22 Phase 189): Vortexte PV/KL/WB wörtlich aus den Design-Vorlagen ---------------------
# Quelle: docs/design-v36/vorlage/entpackt/angebot-pv-anlage.html, angebot-klimaanlage.html,
# angebot-wallbox.html (Abschnitt „Anschreiben“ – Einleitung, „Darin enthalten“, „Warum Friondo?“,
# Schlusssatz, „Ihr Friondo-Team“). Markdown-Konventionen wie bisher (fpdf2-Rückfall rendert die
# „## “-Titel auf Seite 1, „* “ = Haken-Zeile mit fettem Anfang bis „ – “); das Layout v3
# (app/pdf_kontext.vortext_parsen) nimmt die Titel vom Deckblatt und baut aus den beiden Listen die zwei
# Spalten der Seite „Ihr Angebot im Überblick“. WP bleibt beim heutigen Text (STANDARD_VORTEXT – Plan);
# Enni/SWD/Sparkasse DU behalten ihre Vortexte. Migration: migration_v36_texte (migrate.py).
_V36_WARUM_FACH = ("* Fachkompetenz & Qualität – Als Meisterbetrieb, Mitglied der Innung und VDI-zertifiziertes "
                   "Fachunternehmen setzen wir auf höchste Standards.")
_V36_WARUM_BERATUNG = ("* Persönliche Beratung – Wir begleiten Sie von der ersten Idee bis zur perfekten Lösung "
                       "für Ihr Zuhause.")
_V36_WARUM_EFFIZIENZ = ("* Effizienz & Nachhaltigkeit – Unsere Systeme senken Ihren Energieverbrauch spürbar und "
                        "steigern den Wert Ihrer Immobilie.")
_V36_WARUM_HAND = "* Alles aus einer Hand – Planung, Installation, Anmeldung und Service aus einem Haus."
_V36_ENTHALTEN_REST = """* Detaillierte Installationsleistungen – fachgerecht, sauber und termingerecht
* Transparent und Festpreis – klar verständlich und ohne versteckte Kosten
* Unser Rundum-Sorglos-Service – von der Planung bis zur Inbetriebnahme"""

PV_VORTEXT_V36 = """## Ihr individuelles PV-Angebot zum Festpreis
## Eigener Strom, mehr Unabhängigkeit

{briefanrede}

vielen Dank für Ihr Vertrauen in die Friondo GmbH. Sie haben eine zukunftssichere Entscheidung getroffen – eine eigene Photovoltaikanlage senkt Ihre Stromkosten, macht Sie unabhängiger von steigenden Energiepreisen und steigert den Wert Ihrer Immobilie.

* Ihre individuelle PV-Anlage – Module, Wechselrichter und Speicher passend zu Dach und Verbrauch
""" + _V36_ENTHALTEN_REST + """

## Warum Friondo?

""" + _V36_WARUM_FACH + """
* Mitglied im Bundesverband des Solarhandwerks – Geprüfte Fachkompetenz für Planung, Montage und Netzanschluss Ihrer Solaranlage.
""" + _V36_WARUM_BERATUNG + "\n" + _V36_WARUM_EFFIZIENZ + "\n" + _V36_WARUM_HAND + """

Wir sind auf Photovoltaik spezialisiert und gehören in der Region zu den führenden Anbietern. Lassen Sie uns gemeinsam Ihren eigenen Strom erzeugen!

Ihr Friondo-Team"""

KL_VORTEXT_V36 = """## Ihr individuelles Klimaanlagen-Angebot zum Festpreis
## Kühlen, heizen und wohlfühlen

{briefanrede}

vielen Dank für Ihr Vertrauen in die Friondo GmbH. Sie haben eine gute Entscheidung getroffen – eine moderne Split-Klimaanlage sorgt im Sommer für angenehme Kühle, heizt in der Übergangszeit effizient und verbessert die Luftqualität in Ihren Räumen.

* Ihre individuelle Klimaanlage – Außen- und Innengeräte passend zu Raumgröße und Nutzung
""" + _V36_ENTHALTEN_REST + """

## Warum Friondo?

""" + _V36_WARUM_FACH + """
* Bosch-zertifizierter Profi für Split-Klimageräte – Geschulte Kältetechniker mit Sachkundenachweis nach ChemKlimaschutzV.
""" + _V36_WARUM_BERATUNG + "\n" + _V36_WARUM_EFFIZIENZ + "\n" + _V36_WARUM_HAND + """

Wir sind auf Klimatechnik spezialisiert und gehören in der Region zu den führenden Anbietern. Lassen Sie uns gemeinsam für Ihr Wohlfühlklima sorgen!

Ihr Friondo-Team"""

WB_VORTEXT_V36 = """## Ihr individuelles Wallbox-Angebot zum Festpreis
## Laden zu Hause – einfach und sicher

{briefanrede}

vielen Dank für Ihr Vertrauen in die Friondo GmbH. Sie haben eine praktische Entscheidung getroffen – mit einer eigenen Wallbox laden Sie Ihr Elektroauto sicher, schnell und günstig zu Hause, auf Wunsch mit Ihrem eigenen Solarstrom.

* Ihre individuelle Wallbox – Ladeleistung und Standort passend zu Fahrzeug und Hausanschluss
""" + _V36_ENTHALTEN_REST + """

## Warum Friondo?

""" + _V36_WARUM_FACH + """
* Qualifizierter E-Handwerk-Fachbetrieb der Innung – Eingetragener Elektrofachbetrieb mit Netzbetreiber-Zulassung für Ladeinfrastruktur.
""" + _V36_WARUM_BERATUNG + "\n" + _V36_WARUM_EFFIZIENZ + "\n" + _V36_WARUM_HAND + """

Wir sind auf Elektromobilität und Ladeinfrastruktur spezialisiert. Lassen Sie uns gemeinsam Ihr Zuhause zur Ladestation machen!

Ihr Friondo-Team"""

V36_VORTEXTE = [("PV", "Friondo PV Standard", PV_VORTEXT_V36),
                ("KL", "Friondo KL Standard", KL_VORTEXT_V36),
                ("WB", "Friondo WB Standard", WB_VORTEXT_V36)]
V36_HISTORIE_SUFFIX = " (bis v35)"
MARKER_V36_TEXTE = "migration_v36_texte"


def migration_v36_texte(session: Session) -> list[str]:
    """v36 (PLAN_V22 Phase 189): Design-Wortlaute der Vortexte PV/KL/WB als neue Fassung der Textblöcke
    „Friondo PV/KL/WB Standard“ einspielen. Textblöcke kennen keine Versionierung – die bisherige Fassung
    bleibt als additive Historie im Textblock „<Name> (bis v35)“ (inaktiv: kein Profil verweist darauf,
    die Sparten-Auflösung sucht nur „Friondo <Sparte> <Profil>“/„… Standard“). WP bleibt beim heutigen
    Text (Plan), Enni/SWD/Sparkasse DU behalten ihre Vortexte; der WB-Absatz „Komplettpaket Wallbox inkl.
    Montage“ (v34, TAIFUN-Textzeile) steht im neuen Wortlaut nicht mehr – er bleibt in der Historie
    [ANNAHME, Rückfrage]. Idempotent über den Marker migration_v36_texte (zweiter Lauf: keine Meldung);
    fehlende Blöcke werden mit dem neuen Wortlaut angelegt."""
    from app.models import einstellung_holen, einstellung_setzen
    if einstellung_holen(session, MARKER_V36_TEXTE, "") == "erledigt":
        return []
    meldungen: list[str] = []
    vorhanden = {(b.art, b.name): b for b in session.query(Textblock)}
    for _sparte, name, neu in V36_VORTEXTE:
        block = vorhanden.get(("vortext", name))
        if block is None:
            session.add(Textblock(art="vortext", name=name, text=neu))
            meldungen.append(f"v36: Vortext „{name}“ mit dem Design-Wortlaut angelegt")
            continue
        if (block.text or "").strip() == neu.strip():
            continue
        historie = name + V36_HISTORIE_SUFFIX
        if ("vortext", historie) not in vorhanden:
            session.add(Textblock(art="vortext", name=historie, text=block.text or ""))
        block.text = neu
        meldungen.append(f"v36: Vortext „{name}“ auf den Design-Wortlaut gesetzt – bisherige Fassung "
                         f"als „{historie}“ erhalten")
    einstellung_setzen(session, MARKER_V36_TEXTE, "erledigt")
    if meldungen:
        meldungen.append("v36: Vortexte WP (Friondo Standard), Enni, SWD und Sparkasse DU unverändert")
    return meldungen


# --- v36 (PLAN_V22 Phase 193, Agent B2): Platzhalter [CLOOVER] für den fpdf2-Rückfall ----------------
# Die Nachtexte A tragen statt der festen Beispielraten („Wärmepumpe ab 129 € pro Monat mit
# Förderung* / Oder ab 250 € pro Monat ohne Förderung“ + Fußnote „*Beispielrate …“; PV „z. B. PV-Anlage
# ab 119 € pro Monat“) den Platzhalter [CLOOVER]; pdf_export._nachtext_rendern druckt dort die
# berechnete Cloover-Rate (Box „Planbare Monatsraten – Ihre Rate für dieses Angebot:“, Laufzeit, Link/QR)
# und die Fußnote am Seitenende. KL (seit v24 ohne Raten-Absatz) und WB (neuer Nachtext A) erhalten den
# Platzhalter vor dem Satz „So bleibt Ihr Budget flexibel …“. Das Layout v3 (Standard-Engine) überliest
# den Platzhalter – der Cloover-Block kommt dort aus der Design-Vorlage (pdf_kontext).
PLATZHALTER_CLOOVER = "[CLOOVER]"
MARKER_V36_CLOOVER = "migration_v36_cloover_platzhalter"
_CLOOVER_RATEN_ABSATZ = re.compile(r"^### Planbare Monatsraten[^\n]*\n(?:[•\-*] ?[^\n]*\n?)+", re.MULTILINE)
_CLOOVER_BEISPIELRATE = re.compile(r"\n*^~ \*Beispielrate[^\n]*\n?", re.MULTILINE)
_CLOOVER_SO_BLEIBT = re.compile(r"^(?=So bleibt Ihr Budget flexibel)", re.MULTILINE)
_CLOOVER_BLOCK_TITEL = "## Finanzierung mit Cloover"


def cloover_platzhalter_einsetzen(text: str) -> tuple[str, list[str]]:
    """Reine Textumstellung eines Nachtext-Blocks (v36): Raten-Absatz „### Planbare Monatsraten …“ samt
    Aufzählung → [CLOOVER]; Fußnote „~ *Beispielrate …“ entfällt; trägt der Text den Cloover-Block, aber
    keinen Raten-Absatz (KL), steht [CLOOVER] vor „So bleibt Ihr Budget flexibel …“. Liefert (neuer Text,
    Liste der Änderungen); ohne Cloover-Block oder mit vorhandenem Platzhalter unverändert."""
    text = text or ""
    aenderungen: list[str] = []
    if PLATZHALTER_CLOOVER in text:
        return text, aenderungen
    neu, anzahl = _CLOOVER_RATEN_ABSATZ.subn(PLATZHALTER_CLOOVER + "\n", text)
    if anzahl:
        aenderungen.append("Raten-Absatz -> [CLOOVER]")
    neu, anzahl = _CLOOVER_BEISPIELRATE.subn("\n", neu)
    if anzahl:
        aenderungen.append("Fußnote „*Beispielrate …“ entfernt")
    if PLATZHALTER_CLOOVER not in neu and _CLOOVER_BLOCK_TITEL in neu:
        neu, anzahl = _CLOOVER_SO_BLEIBT.subn(PLATZHALTER_CLOOVER + "\n\n", neu, count=1)
        if anzahl:
            aenderungen.append("[CLOOVER] vor „So bleibt Ihr Budget flexibel …“ eingefügt")
    return (neu if aenderungen else text), aenderungen


def migriere_cloover_platzhalter(session: Session) -> list[str]:
    """v36 (PLAN_V22 Phase 193): bestehende Nachtext-Textblöcke auf den Platzhalter [CLOOVER] umstellen
    (alle Profile/Sparten; Enni/SWD/Sparkasse DU tragen keinen Cloover-Block und bleiben unverändert) und
    dem Block „Friondo WB Standard“ den Nachtext A (Kopie des KL-Textes mit „Ihre Wallbox-Lösung“)
    voranstellen [ANNAHME]. Idempotent: Marker migration_v36_cloover_platzhalter (zweiter Lauf → []);
    die Textumstellung selbst ist zusätzlich inhaltsbasiert (vorhandener Platzhalter = keine Änderung)."""
    from app.models import einstellung_holen, einstellung_setzen
    if einstellung_holen(session, MARKER_V36_CLOOVER, "") == "erledigt":
        return []
    meldungen: list[str] = []
    for block in session.query(Textblock).filter(Textblock.art == "nachtext").order_by(Textblock.id):
        neu, aenderungen = cloover_platzhalter_einsetzen(block.text or "")
        if aenderungen and neu != (block.text or ""):
            block.text = neu
            meldungen.append(f"v36: Nachtext „{block.name}“: {', '.join(aenderungen)}")
    wb = (session.query(Textblock)
          .filter(Textblock.art == "nachtext", Textblock.name == "Friondo WB Standard").first())
    if wb is not None and "# Ihre Zahlungsoptionen" not in (wb.text or "") \
            and PLATZHALTER_CLOOVER not in (wb.text or ""):
        wb.text = WB_ZAHLUNGSOPTIONEN + "\n---\n" + (wb.text or "")
        meldungen.append("v36: Nachtext „Friondo WB Standard“: Nachtext A (Finanzierung mit Cloover, "
                         "[CLOOVER]) vorangestellt – Kopie des KL-Textes mit „Ihre Wallbox-Lösung“")
    einstellung_setzen(session, MARKER_V36_CLOOVER, "erledigt")
    return meldungen


SEED_BLOECKE = [
    ("nachtext", "Friondo Standard", STANDARD_NACHTEXT),
    ("nachtext", "Friondo Enni", ENNI_NACHTEXT),
    ("nachtext", "Friondo SWD", SWD_NACHTEXT),
    ("nachtext", "Friondo Sparkasse DU", SPARKASSE_NACHTEXT),
    ("vortext", "Friondo Standard", STANDARD_VORTEXT),
]

# (Name, Regel-Kennung, Nachtext-Blockname, Kanalwerte, CC, Empf. leer, ohne Vollmacht)
SEED_PROFILE = [
    ("Standard", "standard", "Friondo Standard", "", "", False, False),
    ("Enni", "enni", "Friondo Enni", "Enni", ENNI_CC, False, True),
    ("SWD", "swd", "Friondo SWD", "", "", True, True),
    ("Sparkasse DU", "sparkasse", "Friondo Sparkasse DU", "Sparkasse", "", False, False),
]


def seed(session: Session) -> list[str]:
    """Migration: Textblöcke + Profile anlegen (nur, wenn noch keine existieren)."""
    meldungen = []
    if session.query(Textblock).count() == 0:
        for art, name, text in SEED_BLOECKE:
            session.add(Textblock(art=art, name=name, text=text))
        meldungen.append(f"{len(SEED_BLOECKE)} Textblöcke (Nach-/Vortexte) angelegt")
    if session.query(Profil).count() == 0:
        session.flush()
        bloecke = {(b.art, b.name): b.id for b in session.query(Textblock)}
        vortext_id = bloecke.get(("vortext", "Friondo Standard"))
        for name, kennung, nachtext_name, kanal, cc, leer, ohne_vm in SEED_PROFILE:
            session.add(Profil(name=name, regel_kennung=kennung,
                               nachtext_id=bloecke.get(("nachtext", nachtext_name)),
                               vortext_id=vortext_id, kanalwerte=kanal,
                               versand_cc=cc, empfaenger_leer=leer,
                               ohne_vollmacht=ohne_vm))
        meldungen.append("4 Angebotsprofile angelegt (Standard/Enni/SWD/Sparkasse DU)")
    return meldungen


# --- Auflösung -------------------------------------------------------------

def standard_profil(session: Session) -> Profil | None:
    return (session.query(Profil)
            .filter(Profil.regel_kennung == "standard")
            .order_by(Profil.id).first())


def profil_fuer_kanal(session: Session, kanal: str) -> Profil | None:
    """Kanalwert → Profil (Teilstring, Groß-/Kleinschreibung egal); Fallback
    Standard. None nur, wenn noch gar keine Profile existieren (Alt-DB)."""
    kanal = (kanal or "").strip().lower()
    if kanal:
        for profil in session.query(Profil).order_by(Profil.id):
            for wert in (w.strip().lower() for w in profil.kanalwerte.split(",")):
                if wert and wert in kanal:
                    return profil
    return standard_profil(session)


def profil_fuer_angebot(session: Session, angebot: Angebot,
                        kunde: Kunde | None = None) -> Profil | None:
    if angebot.profil_id:
        profil = session.get(Profil, angebot.profil_id)
        if profil is not None:
            return profil
    kunde = kunde or session.get(Kunde, angebot.kunde_id)
    return profil_fuer_kanal(session, kunde.vertriebskanal if kunde else "")


def profil_fuer_erfassung(session: Session, erfassung) -> Profil | None:
    """Profil des Vorgangs beim Erfassen: Kanal des Leads, sonst des Kunden."""
    from app.models import Lead
    kanal = ""
    if erfassung.lead_id:
        lead = session.get(Lead, erfassung.lead_id)
        kanal = lead.vertriebskanal if lead else ""
    if not kanal:
        kunde = session.get(Kunde, erfassung.kunde_id)
        kanal = kunde.vertriebskanal if kunde else ""
    return profil_fuer_kanal(session, kanal)


def nachtext_fuer_angebot(session: Session, angebot: Angebot) -> str:
    profil = profil_fuer_angebot(session, angebot)
    if ist_pv(angebot):   # v13-PV: eigene PV-Nachtexte je Profil
        return _pv_block(session, "nachtext", profil)
    if ist_kl(angebot):   # v24: eigene KL-Nachtexte je Profil
        return _kl_block(session, "nachtext", profil)
    if ist_wb(angebot):   # v34: eigene WB-Nachtexte je Profil
        return _wb_block(session, "nachtext", profil)
    if profil is not None and profil.nachtext_id:
        block = session.get(Textblock, profil.nachtext_id)
        if block is not None and block.text.strip():
            return block.text
    return STANDARD_NACHTEXT


def vortext_fuer_angebot(session: Session, angebot: Angebot) -> str:
    if (angebot.vortext_text or "").strip():
        return angebot.vortext_text
    profil = profil_fuer_angebot(session, angebot)
    if ist_pv(angebot):   # v13-PV
        return _pv_block(session, "vortext", profil)
    if ist_kl(angebot):   # v24
        return _kl_block(session, "vortext", profil)
    if ist_wb(angebot):   # v34
        return _wb_block(session, "vortext", profil)
    if profil is not None and profil.vortext_id:
        block = session.get(Textblock, profil.vortext_id)
        if block is not None and block.text.strip():
            return block.text
    return STANDARD_VORTEXT


def vollmacht_erlaubt(session: Session, angebot: Angebot) -> bool:
    """Profil-Regel „ohne Vollmacht“ (Enni/SWD, v9). v34 (PLAN_V21 Phase 179, Rückfrage 4):
    bei Wallbox-Angeboten gilt die Vollmacht immer – auch bei Enni/SWD, weil die
    Netzanmeldung nach § 14a EnWG (WB004) Teil des Angebots ist [ANNAHME]."""
    if ist_wb(angebot):
        return True
    profil = profil_fuer_angebot(session, angebot)
    return not (profil is not None and profil.ohne_vollmacht)


# --- Positionsregeln -------------------------------------------------------

ENNI_SONDERPREIS_CENT = 59900   # Pos. 015 „Friondo HEMS“ im Enni-Profil


def regeln_beschreibung(profil: Profil | None) -> str:
    """Kurzbeschreibung für den Umschalt-Hinweis am Angebot."""
    if profil is None or profil.regel_kennung == "standard":
        return "Standard: keine besonderen Positions-/Versandregeln."
    if profil.regel_kennung == "enni":
        return ("Enni: Pos. 015 (HEMS) zum Sonderpreis 599,00 €, Pos. 162 "
                "automatisch, Pos. 014/016/017 entfallen; keine Vollmacht-Seite; "
                f"Versand zusätzlich CC {profil.versand_cc or ENNI_CC}.")
    if profil.regel_kennung == "swd":
        return ("SWD: Pos. 014–017 entfallen (P01–P03 nur Protokoll); keine "
                "Vollmacht-Seite; Versand-Empfänger bleibt leer (SWD-Kontakt "
                "manuell in Outlook eintragen).")
    if profil.regel_kennung == "sparkasse":
        return "Sparkasse DU: eigener Nachtext, sonst Standard-Regeln."
    return ""


def regeln_beschreibung_fuer_angebot(angebot: Angebot, profil: Profil | None) -> str:
    """v24: Umschalt-Hinweis je Angebot – bei Klima-Angeboten gelten nur
    Nachtext und Versandregeln des Profils (keine Positionsregeln 014–017)."""
    if ist_kl(angebot) and profil is not None and profil.regel_kennung in ("enni", "swd"):
        versand = ("Versand zusätzlich CC " + (profil.versand_cc or ENNI_CC)
                   if profil.regel_kennung == "enni"
                   else "Versand-Empfänger bleibt leer")
        return (f"{profil.name}: Klima-Angebot – keine Positionsregeln (kein Friondo "
                f"Fit for Future); eigener KL-Nachtext; {versand}.")
    if ist_wb(angebot) and profil is not None and profil.regel_kennung in ("enni", "swd"):
        # v34: Wallbox – keine Positionsregeln, Vollmacht immer (Netzanmeldung § 14a)
        versand = ("Versand zusätzlich CC " + (profil.versand_cc or ENNI_CC)
                   if profil.regel_kennung == "enni"
                   else "Versand-Empfänger bleibt leer")
        return (f"{profil.name}: Wallbox-Angebot – keine Positionsregeln (kein Friondo "
                f"Fit for Future); eigener WB-Nachtext; Vollmacht-Seite immer; {versand}.")
    return regeln_beschreibung(profil)


def positionsregeln_anwenden(session: Session, angebot: Angebot,
                             profil: Profil | None) -> list[str]:
    """Wendet die Positionsregeln des Profils auf den Angebotsentwurf an.
    Idempotent; liefert die Liste der Änderungen (für die Meldung)."""
    from app.models import Artikel
    kennung = profil.regel_kennung if profil else "standard"
    meldungen: list[str] = []
    # v24 (PLAN_V16 Phase 114): Klima-Angebote führen kein Friondo Fit for
    # Future – die WP-Artikel 014–017 werden weder eingefügt noch entfernt/
    # umgepreist, Pos. 162 nie ergänzt (kein Gruppen-Trigger). Versandregeln
    # (Enni-CC, SWD-Empfänger leer) greifen weiterhin über das Profil.
    # v34 (PLAN_V21 Phase 179): Wallbox-Angebote ebenso – keine Pos. 014–017 [ANNAHME].
    if ist_kl(angebot) or ist_wb(angebot):
        return meldungen
    if kennung not in ("enni", "swd"):
        return meldungen

    entfernen = {"014", "016", "017"} if kennung == "enni" else {"014", "015", "016", "017"}
    hems_vorhanden = False
    for position in list(angebot.positionen):
        if position.pos_nr == "015" and kennung == "enni":
            hems_vorhanden = True
            if position.e_preis_cent != ENNI_SONDERPREIS_CENT:
                if position.original_preis_cent is None:
                    position.original_preis_cent = position.e_preis_cent
                position.e_preis_cent = ENNI_SONDERPREIS_CENT
                position.sonderpreis = True
                meldungen.append("Pos. 015 (HEMS) auf Sonderpreis 599,00 € gesetzt")
            continue
        if position.pos_nr in entfernen:
            angebot.positionen.remove(position)
            meldungen.append(f"Pos. {position.pos_nr} entfernt ({kennung.upper()}-Profil)")
    if kennung == "enni" and hems_vorhanden:
        if not any(p.pos_nr == "162" for p in angebot.positionen):
            stamm = (session.query(Artikel)
                     .filter(Artikel.pos_nr == "162", Artikel.aktiv.is_(True)).first())
            if stamm is not None:
                from app.models import AngebotsPosition
                angebot.positionen.append(AngebotsPosition(
                    sort=max((p.sort for p in angebot.positionen), default=0) + 1,
                    block_nr=10, gruppe="", pos_nr="162",
                    bezeichnung=stamm.bezeichnung, beschreibung=stamm.beschreibung,
                    menge=1, einheit=stamm.einheit, e_preis_cent=stamm.e_preis_cent,
                    ep_flag=False, ek_cent=stamm.ek_cent, guid=stamm.guid))
                meldungen.append("Pos. 162 (Voranmeldung iMSys/enni.flexstrom) ergänzt")
    return meldungen


def enni_bogen(session: Session, erfassung) -> bool:
    """v9: Zeigt der Erfassungsbogen des Vorgangs nur die HEMS-Frage (Enni)?"""
    profil = profil_fuer_erfassung(session, erfassung)
    return profil is not None and profil.regel_kennung == "enni"
