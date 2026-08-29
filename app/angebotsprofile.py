# Angebotsprofile (v9, Phase 53): bündeln je Vertriebskanal den Nachtext-
# Block, Positionsregeln und Versandregeln. Auto-Auswahl über den Kanal des
# Kunden (Teilstring-Abgleich der Profil-Kanalwerte), Fallback Standard.
# Die Textblöcke (Nach-/Vortexte) sind in der Parametrierung editierbar;
# die Konstanten hier sind die Seed-Inhalte der Migration und zugleich der
# Fallback, solange keine Blöcke in der Datenbank liegen.

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
Eine Anzahlung von 50% des Angebotsbetrags ist spätestens 14 Tage vor Arbeitsbeginn zu zahlen. Die Restzahlung wird mit der Schlussrechnungsstellung fällig. Die Rechnung erhalten Sie im Anschluss zur Installation."""

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

### Planbare Monatsraten – Zum Beispiel:
• Wärmepumpe ab 129 € pro Monat mit Förderung*
• Oder ab 250 € pro Monat ohne Förderung

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

~ *Beispielrate auf Basis einer Angebotssumme von 29.000 €, einer Förderung von 56 %, gedeckelt auf 28.000 €, und einer Laufzeit von 20 Jahren.
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
    if profil is not None and profil.nachtext_id:
        block = session.get(Textblock, profil.nachtext_id)
        if block is not None and block.text.strip():
            return block.text
    return STANDARD_NACHTEXT


def vortext_fuer_angebot(session: Session, angebot: Angebot) -> str:
    if (angebot.vortext_text or "").strip():
        return angebot.vortext_text
    profil = profil_fuer_angebot(session, angebot)
    if profil is not None and profil.vortext_id:
        block = session.get(Textblock, profil.vortext_id)
        if block is not None and block.text.strip():
            return block.text
    return STANDARD_VORTEXT


def vollmacht_erlaubt(session: Session, angebot: Angebot) -> bool:
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


def positionsregeln_anwenden(session: Session, angebot: Angebot,
                             profil: Profil | None) -> list[str]:
    """Wendet die Positionsregeln des Profils auf den Angebotsentwurf an.
    Idempotent; liefert die Liste der Änderungen (für die Meldung)."""
    from app.models import Artikel
    kennung = profil.regel_kennung if profil else "standard"
    meldungen: list[str] = []
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
