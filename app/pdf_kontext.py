"""v36 (PLAN_V22 Phase 189): EIN Kontext für das Angebots-PDF (Browser-Druck, app/pdf_html.py) und die
HTML-Vorschau (GET /angebote/<id>/pdf.html). Alle Daten werden hier mit offener Sitzung gelesen; der Druck
selbst läuft danach ohne Datenbank (pdf_html.angebot_pdf gibt die Verbindung frei). Das Modul liest nur –
es schreibt nie in die Datenbank und ruft kein Netz.

**Vertrag** `fuer_angebot(session, angebot, *, signatur=None, fassung="kunde", benutzer=None) -> dict` –
Schlüssel (Datenquellen = die heutigen Quellen von app/pdf_export.py; Teilbäume `kfw`/`wirtschaftlichkeit`
kommen aus pdf_kontext_kfw / pdf_kontext_wirtschaftlichkeit (Agent A2), `auftrag.cloover` aus app/cloover.py
(Teil B); Beträge im Summenblock als fertige Texte „1.234,56 €“, in der Positionstabelle ohne €-Zeichen
(„12.422,61“ – Kopf „Alle Preise in EUR, netto“ wie die Design-Vorlage); nie EK/DB – auch nicht in der
Fassung „intern“):

  sparte            "WP" | "PV" | "KL" | "WB"
  sparte_name       Wärmepumpe | PV-Anlage | Klimaanlage | Wallbox
  eyebrow, titel, untertitel, titelbild   wörtlich aus SPARTEN (Deckblatt), titelbild relativ zu static/pdf/
  fassung           "kunde" | "intern" (Vorschau Innendienst – keine zusätzlichen Zahlen, nur Kennzeichnung)
  angebot           {nummer, datum "TT.MM.JJJJ", datum_iso, gueltig_bis "TT.MM.JJJJ" | "", bindefrist_tage,
                     status, version_von {nummer, datum} | None, ersetzt_hinweis str, kopie_von str | None,
                     profil "standard"|"enni"|"swd"|"sparkasse", profil_name, ust_satz 19 | 0}
  firma             {name, strasse, plz_ort, absenderzeile, telefon, email, web, ort, fuss [{titel, zeilen}],
                     zertifikate [{bild, alt}], award_link}
  kunde             {name (Kopfzeile: Firma bzw. „Vorname Nachname“), anrede, vorname, nachname, firma,
                     briefanrede, telefon, email}
  empfaenger        {zeilen [..] (v20: Rechnungs-Name ersetzt den Kundennamen, Zusatz als Zeile),
                     ausfuehrungsort str | None (nur bei abweichender Rechnungsadresse),
                     lieferanschrift str | None (nur bei Abweichung vom Ausführungsort)}
  ansprechpartner   {name, telefon} – AD des Vorgangs, sonst der vorbereitende Innendienstler (`benutzer`);
                    name "" → Zeile entfällt, telefon "" → Zeile entfällt
  ueberblick        {anrede, einleitung [absaetze], enthalten_titel, enthalten [{titel, text}], warum_titel,
                     warum [{titel, text}], schluss [{text, fett}], gruss [zeilen]}
                    (aus dem Vortext-Textblock des Profils/der Sparte – Markdown-Struktur, siehe vortext_parsen)
  gruppen           [{titel, alternativ_hinweis str | None, positionen [{nr, pos_nr, menge, einheit,
                     bezeichnung, zeilen [{text, punkt bool, ebene 1|2, dezent bool}], einzelpreis,
                     gesamtpreis, kennzeichen ""|"ep"|"bauseits"|"alternativ", rabatt_text str | None,
                     hinweiskasten str | None (Kasten VOR dieser Position – erste Alternativ-Position des Blocks)}]}]
  hinweise          [{titel, text}]  (bedingte Vermerke v9, Alternativ-Vermerk v10) – Absatz „Hinweise“ vor dem
                    Summenblock
  summen            {zeilen [{text, betrag, fett bool, blau bool, linie bool}] (Zeilen VOR der dunklen Box),
                     box {titel, betrag, hinweis}, netto, ust_text, ust, gesamt, rabatt {text, betrag} | None,
                     endbetrag, foerderung {text, betrag, prozent} | None, eigenanteil str | None,
                     hat_foerderung bool, hat_rabatt bool}
  kfw               None | dict (nur WP mit Förderblock; Schlüssel laut pdf_kontext_kfw)
  wirtschaftlichkeit None | dict (nur PV, nicht ausgeblendet; Schlüssel laut pdf_kontext_wirtschaftlichkeit)
  auftrag           {einleitung, karte1 {titel, untertitel, text, knopf_text, knopf_url, online bool},
                     karte2 {art "cloover"|"enni"|"swd"|"sparkasse", titel, untertitel, text, absaetze [..],
                             knopf_text, knopf_url},
                     cloover_block bool (nur Profil Standard), cloover None | dict (Teil B – Felder: rate_text
                     „389,99 €“ (ohne Förderung), rate_mit_text „242,70 €“ | "" (WP mit Förderung), laufzeit,
                     fussnote, checkout_link, qr_svg, datenschutz, hinweis_link (Satz statt Knopf ohne Link)),
                     post_text, aufschiebende_bedingung str | None (Text aus Nachtext C), umsetzungsdatum bool,
                     ausfuehrungszeitraum bool, unterschrift {ort_datum, unterschrift}}
  bedingungen       {abschnitte [{titel, absaetze [..]}], schluss {absaetze [[{text, url|None}, ..], ..],
                     links [{text, url}], gruss [..]}, fussnoten [..]}
  vollmacht         None | {titel, absaetze [{text, fett_ab str | None}], verbrauchsstelle_titel,
                     verbrauchsstelle [{label, wert}], kaestchen_titel, kaestchen [..], sepa_titel, sepa_text,
                     sepa_zeilen [..], unterschriften [..]}
  signatur          None | {bild_data_url, name, zeitstempel "TT.MM.JJJJ HH:MM", geraet}

`demo_kontext(sparte)` liefert einen vollständigen Kontext mit Demo-Daten (Max Mustermann) für Tests,
den Browser-Test der Parametrierung und die Entwicklung der Vorlagen ohne Datenbank – gleiche Struktur
und dieselben Parser wie `fuer_angebot`.
"""
from __future__ import annotations

import json
import re
from datetime import date, datetime, timedelta
from urllib.parse import quote

BINDEFRIST_TAGE = 30   # [ANNAHME PLAN_V22 Phase 189] „Gültig bis“ = Angebotsdatum + 30 Tage (Rückfrage A2)

SPARTEN = {
    "WP": {"name": "Wärmepumpe", "eyebrow": "ANGEBOT · WÄRMEPUMPE",
           "titel": "Ihr individuelles Wärmepumpen-Angebot zum Festpreis",
           "untertitel": "Effizienz, Komfort und zukunftssicher", "titelbild": "bilder/titel-wp.jpg"},
    "PV": {"name": "PV-Anlage", "eyebrow": "ANGEBOT · PV-ANLAGE",
           "titel": "Ihr individuelles PV-Angebot zum Festpreis",
           "untertitel": "Eigener Strom, mehr Unabhängigkeit", "titelbild": "bilder/titel-pv.jpg"},
    "KL": {"name": "Klimaanlage", "eyebrow": "ANGEBOT · KLIMAANLAGE",
           "titel": "Ihr individuelles Klimaanlagen-Angebot zum Festpreis",
           "untertitel": "Kühlen, heizen und wohlfühlen", "titelbild": "bilder/titel-kl.jpg"},
    "WB": {"name": "Wallbox", "eyebrow": "ANGEBOT · WALLBOX",
           "titel": "Ihr individuelles Wallbox-Angebot zum Festpreis",
           "untertitel": "Laden zu Hause – einfach und sicher", "titelbild": "bilder/titel-wb.jpg"},
}

ZERTIFIKATE = [   # Leiste „Mitgliedschaften & Zertifizierungen“ (Deckblatt), Dateien unter static/pdf/bilder/
    ("bilder/zert-shk.jpg", "SHK Innungsfachbetrieb"),
    ("bilder/zert-ehandwerk.jpg", "E-Handwerk – Qualifizierter Fachbetrieb der Innung"),
    ("bilder/zert-bdsh.png", "Bundesverband des Solarhandwerks"),
    ("bilder/zert-fachbetrieb-wp.jpg", "Fachbetrieb Wärmepumpe"),
    ("bilder/zert-bosch.png", "Bosch Premium Partner – Zertifizierter Profi Split-Klimageräte und Wärmepumpen"),
]
AWARD_LINK = "https://www.germanenergyawards.com/interview/friondo-gmbh"

# ----------------------------------------------------------------------------- feste Wortlaute (Design-Vorlagen)
# Alle Texte wörtlich aus docs/design-v36/vorlage/entpackt/angebot-*.html (Abschnitte Auftragserteilung,
# Cloover-Block, Vollmacht). Abweichungen sind im Bericht diagnose/v36/A1_ergebnis.md aufgeführt.
AUFTRAG_EINLEITUNG = ("Sollte Ihnen das Angebot zusagen, beauftragen Sie uns bequem online – oder senden Sie uns "
                      "das unterschriebene Angebot per Post zurück.")
POST_TITEL = "Beauftragung per Post"
POST_TEXT = ("Senden Sie uns das unterschriebene Angebot an: Friondo GmbH, Arnold-Overbeck-Str. 63-65, "
             "47139 Duisburg – oder eingescannt an info@friondo.de.")
UMSETZUNG_VOR = "Voraussichtliches Datum der Umsetzung:"
UMSETZUNG_NACH = ", liegt innerhalb des Bewilligungszeitraum nach Nummer 9.4.1."
AUSFUEHRUNGSZEITRAUM = "Voraussichtlicher Ausführungszeitraum:"
UNTERSCHRIFT = {"ort_datum": "Ort, Datum", "unterschrift": "Unterschrift des Auftraggebers"}
KARTE1_TITEL = "BARKAUF"
KARTE1_UNTERTITEL = "Online beauftragen"
KNOPF_ONLINE = "Jetzt online beauftragen ›"
KNOPF_MAIL = "Per E-Mail beauftragen ›"
KNOPF_CLOOVER = "Finanzierung abschließen ›"
KARTE2_CLOOVER = {"titel": "FINANZIERUNG MIT CLOOVER", "untertitel": "Online beauftragen & finanzieren",
                  "text": "Mit der Ersparnis Ihrer neuen Anlage finanzieren Sie die Anlage."}
RATE_AUF_ANFRAGE = "Monatsrate auf Anfrage"
# Karte 2 der Kanal-Profile: Titel laut Plan, Untertitel = Kopf des Nachtext-A-Blocks (Rückfall, wenn der
# Block – z. B. bei Wallbox – keinen Nachtext A trägt)
KARTE2_PROFILE = {
    "enni": {"titel": "ENNI CONTRACTING", "untertitel": "Barkauf oder Enni Contracting"},
    "swd": {"titel": "CONTRACTING", "untertitel": "Barkauf oder Contracting"},
    "sparkasse": {"titel": "FINANZIERUNG MIT SPARKASSE DUISBURG", "untertitel": "Barkauf oder Finanzierung"},
}
SLOGAN = "Saubere Energie. Faire Raten. Maximale Freiheit."
CLOOVER_BLOCK = {
    "titel": "Finanzierung mit Cloover", "slogan": SLOGAN,
    "sofort_titel": "Sofort starten",
    "sofort_text": ("Keine Anzahlung, Keine Grundbuchbelastung, Schnelle - digitale Prüfung, Finanzierungszusage "
                    "in wenigen Minuten, 100 % digital, Kein Papierkram und keine Banktermine"),
    "raten_titel": "Planbare Monatsraten – Ihre Rate für dieses Angebot:",
    "raten_schluss": "So bleibt Ihr Budget flexibel und Ihre Energiekosten sinken langfristig.",
    "flex_titel": "Maximale Flexibilität",
    "flex_punkte": ["Kostenlose Sondertilgungen", "Vorzeitige Rückzahlung ohne Strafgebühren",
                    "Individuell anpassbare Laufzeiten"],
    "vorteile_titel": "Ihre Vorteile",
    "vorteile_text": "Sofort investieren · Monatlich entspannt zahlen · Energiekosten senken · Unabhängiger werden",
    "zufriedenheit": "Kundenzufriedenheit: 4,8 von 5",
    "zitat": "„Dank Cloover konnten wir unsere {anlage} einfach, fair und transparent finanzieren.“",
    "rueckmeldung": ("Prüfung und Zusage erfolgen direkt bei Cloover; Friondo erhält eine Rückmeldung über den "
                     "Stand."),
}
CLOOVER_ANLAGE = {"WP": "Wärmepumpe", "PV": "PV-Anlage", "KL": "Klimaanlage", "WB": "Wallbox"}

VOLLMACHT_TITEL = ("Vollmacht zur Beauftragung der SpotmyEnergy GmbH sowie zur Anmeldung und Inbetriebsetzung "
                   "von Anlagen")
VOLLMACHT_ABSAETZE = [
    {"text": ("Ich bevollmächtige als zukünftiger Anlagenbetreiber und Gebäudeeigentümer die Friondo GmbH, in "
              "meinem Namen alle erforderlichen Schritte zur Beauftragung der SpotmyEnergy GmbH als "
              "Messstellenbetreiber und/oder Stromlieferant einzuleiten und entsprechende Verträge abzuschließen. "
              "Dies umfasst auch die Erteilung eines SEPA-Lastschriftmandats für damit verbundene Zahlungen."),
     "fett_ab": None},
    {"text": ("Die Vollmacht gilt ebenfalls für die Friondo GmbH sowie deren Nachunternehmer zur Anmeldung, "
              "Inbetriebnahme, Änderung, Erweiterung oder Abmeldung folgender Anlagen und Verbrauchseinrichtungen "
              "beim zuständigen Netzbetreiber oder Energieversorgungsunternehmen: Photovoltaikanlagen, "
              "Wärmepumpen, Ladeeinrichtungen/Wallboxen sowie sonstige steuerbare Verbrauchseinrichtungen gemäß "
              "§ 14a EnWG (Modul 1, 2 oder 3)."),
     "fett_ab": "Photovoltaikanlagen, Wärmepumpen"},
    {"text": ("Die Vollmacht umfasst insbesondere die An- und Abmeldung von Zählern, die Beantragung neuer Zähler, "
              "die Einreichung und Entgegennahme erforderlicher Unterlagen, die Kommunikation mit Netzbetreibern, "
              "Messstellenbetreibern und Stromlieferanten, die Kündigung bestehender Verträge, die Durchführung "
              "eines Anbieterwechsels sowie die Beauftragung und Betreuung eines intelligenten Messsystems."),
     "fett_ab": None},
    {"text": ("Die Vollmacht gilt ausschließlich für die genannten Zwecke und erlischt nach Abschluss des "
              "beauftragten Vorgangs. Sie kann jederzeit schriftlich widerrufen werden."),
     "fett_ab": None},
]
VOLLMACHT_KAESTCHEN = ["Messstellenbetreiber", "Stromlieferant",
                       "Anmeldung/Inbetriebnahme/Änderung/Erweiterung/Abmeldung"]
VOLLMACHT_SEPA_TEXT = ("Ich ermächtige den Zahlungsempfänger, fällige Zahlungen mittels Lastschrift von folgendem "
                       "Konto einzuziehen.")
VOLLMACHT_SEPA_ZEILEN = ["Kontoinhaber:", "Adresse:", "IBAN:", "Kreditinstitut:"]
VOLLMACHT_UNTERSCHRIFTEN = ["Ort, Datum", "Unterschrift Vollmachtgeber",
                            "Unterschrift Kontoinhaber, sofern abweichend"]

ENTHALTEN_TITEL = "Darin enthalten"
WARUM_TITEL = "Warum Friondo?"
EIGENANTEIL_HINWEIS = "Unverbindliche Beispielrechnung – Details und Ablauf auf der nächsten Seite."
PLATZHALTER_WIRTSCHAFTLICHKEIT = ("[WIRTSCHAFTLICHKEIT]", "[BEISPIELRECHNUNG]")
PLATZHALTER_CLOOVER = "[CLOOVER]"   # Teil B (fpdf2-Rückfall) – im neuen Layout nie gerendert

# Absätze des Nachtexts, die in den Schlusskasten der Vertragsbedingungen wandern (Bindefrist, AGB/Datenschutz,
# Zusicherung, Gruß) bzw. durch die Auftragsseite ersetzt werden
_SCHLUSS_START = ("Wir halten uns freibleibend", "Es gelten unsere Allgemeinen", "Informationen zu unserem Datenschutz",
                  "Wir sichern Ihnen", "Sie haben Fragen", "Mit freundlichen Grüßen", "Mit herzlichen Grüßen",
                  "Ihr Friondo-Team")
_GRUSS_START = ("Mit freundlichen Grüßen", "Mit herzlichen Grüßen", "Ihr Friondo-Team")
_AUFTRAG_SATZ = "Sollte Ihnen das Angebot zusagen"
# „# “-Seitentitel der Nachtexte, die das Layout v3 selbst als Seite trägt – sie entfallen; alle anderen
# „# “-Titel (z. B. „Installationsvoraussetzungen“) werden Zwischenüberschriften der Vertragsbedingungen
# (Nachtrag Orchestrator 16.10.2026, Befund A3/H6)
_SEITENTITEL = ("zahlungsoptionen", "vertragsbedingungen", "auftragserteilung", "vollmacht", "angebot im überblick",
                "festpreisangebot", "kfw-förderung", "wirtschaftlichkeit", "unterschrift")
_URL = re.compile(r"(https?://[^\s<>\"„“]+)")
_LISTE = re.compile(r"^\s*[-*•]\s+(.*\S)\s*$")
_PUNKT = re.compile(r"^(?P<einzug>[\s ]*)[-•–]\s*(?P<text>\S.*)$")
_ANREDE = re.compile(r"^(Sehr geehrte|Liebe|Guten Tag|Hallo)")


# ----------------------------------------------------------------------------- Grundbausteine
def sparte_von(angebot) -> str:
    sparte = (getattr(angebot, "konfigurator_typ", "") or "WP").upper()
    return sparte if sparte in SPARTEN else "WP"


def firma_kontext() -> dict:
    """Firmen-Konstanten aus app/pdf_export (Fußzeile, Absenderzeile) – eine Quelle für beide Engines."""
    from app import pdf_export
    fuss = []
    for titel, zeilen in pdf_export.FUSSZEILE:
        zeilen = list(zeilen)
        if titel.upper().startswith("BANK") and len(zeilen) % 3 == 0:
            # Vorlage: „Sparkasse Duisburg · IBAN: … · BIC: …“ je Bank in EINER Zeile
            zeilen = [" · ".join(zeilen[i:i + 3]) for i in range(0, len(zeilen), 3)]
        fuss.append({"titel": titel, "zeilen": zeilen})
    return {"name": "Friondo GmbH", "strasse": "Arnold-Overbeck-Str. 63-65", "plz_ort": "47139 Duisburg",
            "absenderzeile": pdf_export.ABSENDERZEILE, "telefon": "0203 - 3965 710", "email": "info@friondo.de",
            "web": "www.friondo.de", "ort": pdf_export.AUSSTELLUNGSORT, "fuss": fuss,
            "zertifikate": [{"bild": b, "alt": a} for b, a in ZERTIFIKATE], "award_link": AWARD_LINK}


def sparte_kontext(sparte: str) -> dict:
    s = SPARTEN[sparte]
    return {"sparte": sparte, "sparte_name": s["name"], "eyebrow": s["eyebrow"], "titel": s["titel"],
            "untertitel": s["untertitel"], "titelbild": s["titelbild"]}


def _datum(d) -> str:
    return d.strftime("%d.%m.%Y") if d else ""


def _euro(cent: int) -> str:
    """„1.234,56 €“ (Summenblock, Kästen) – Rechenweg wie pdf_export._euro_betrag."""
    from app.pdf_export import _euro_betrag
    return f"{_euro_betrag(int(cent))} €"


def _betrag_tabelle(cent: int) -> str:
    """„1.234,56“ ohne €-Zeichen (Positionstabelle: „Alle Preise in EUR, netto“)."""
    from app.pdf_export import _euro_betrag
    return _euro_betrag(int(cent))


def _prozent_text(wert: float) -> str:
    """„55“ bzw. „49,6“ – wie kfw._prozent."""
    if abs(wert - round(wert)) < 0.05:
        return str(int(round(wert)))
    return f"{wert:.1f}".replace(".", ",")


def _ust_text(ust_prozent) -> str:
    """Beschriftung der Steuerzeile im Summenblock (Plan Phase 189): „19,00 % USt.“ bzw. bei 0 %
    „0,00 % USt. (§ 12 Abs. 3 UStG)“ – Zahlen kommen aus Angebot.summen()."""
    satz = float(ust_prozent)
    if satz == 0:
        return "0,00 % USt. (§ 12 Abs. 3 UStG)"
    return f"{satz:.2f}".replace(".", ",") + " % USt."


def basis(session, angebot, *, signatur: dict | None = None, fassung: str = "kunde") -> dict:
    """Grundgerüst des Kontexts aus Angebot + Kunde (Sparte, Nummer, Datum, Firma, Signatur);
    `fuer_angebot` ergänzt Empfänger, Überblick, Positionen, Summen, Auftrag, Bedingungen, Vollmacht."""
    from app.models import Kunde
    sparte = sparte_von(angebot)
    kunde = session.get(Kunde, angebot.kunde_id) if getattr(angebot, "kunde_id", None) else None
    datum = getattr(angebot, "datum", None)
    ust = getattr(angebot, "ust_prozent", None)
    ust_satz = (0 if sparte == "PV" else 19) if ust is None else (int(ust) if float(ust) == int(ust) else float(ust))
    kontext = {**sparte_kontext(sparte), "fassung": fassung, "firma": firma_kontext(),
               "angebot": {"nummer": getattr(angebot, "nummer", ""), "datum": _datum(datum),
                           "datum_iso": datum.strftime("%Y-%m-%d") if datum else "",
                           "gueltig_bis": _datum(datum + timedelta(days=BINDEFRIST_TAGE)) if datum else "",
                           "bindefrist_tage": BINDEFRIST_TAGE, "status": getattr(angebot, "status", ""),
                           "version_von": None, "ersetzt_hinweis": "",
                           "kopie_von": (getattr(angebot, "kopie_von", "") or None),
                           "profil": "standard", "profil_name": "Standard",
                           "ust_satz": ust_satz},
               "kunde": kunde_kontext(kunde), "signatur": signatur}
    return kontext


def kunde_kontext(kunde) -> dict:
    """Kundendaten: `name` für die Kopfzeile der Engine (Firma bzw. „Vorname Nachname“ – wie das Design
    „Angebot-Nr. … · Max Mustermann“), Briefanrede wie der Mail-Platzhalter (Kunde.briefanrede)."""
    if kunde is None:
        return {"name": "", "anrede": "", "vorname": "", "nachname": "", "firma": "", "briefanrede":
                "Sehr geehrte Damen und Herren,", "telefon": "", "email": ""}
    anrede = (getattr(kunde, "anrede", "") or "").strip()
    vorname = (getattr(kunde, "vorname", "") or "").strip()
    nachname = (getattr(kunde, "nachname", "") or "").strip()
    firma = (getattr(kunde, "firma", "") or "").strip()
    person = " ".join(t for t in (vorname, nachname) if t)
    brief = getattr(kunde, "briefanrede", None)
    if not isinstance(brief, str) or not brief:
        if anrede.lower().startswith("herr") and nachname:
            brief = f"Sehr geehrter Herr {nachname},"
        elif anrede.lower().startswith("frau") and nachname:
            brief = f"Sehr geehrte Frau {nachname},"
        else:
            brief = "Sehr geehrte Damen und Herren,"
    return {"name": firma or person, "anrede": anrede, "vorname": vorname, "nachname": nachname, "firma": firma,
            "briefanrede": brief, "telefon": (getattr(kunde, "telefon", "") or "").strip(),
            "email": (getattr(kunde, "email", "") or "").strip()}


# ----------------------------------------------------------------------------- Vortext → Überblick
def _listeneintrag(text: str) -> dict:
    """„Titel – Rest“ → {titel, text}; die Vorlage setzt den Teil vor „ – “ fett [ANNAHME: für beide
    Listen, auch bei „- “-Zeilen des Textblocks]."""
    if " – " in text:
        titel, rest = text.split(" – ", 1)
        return {"titel": titel.strip(), "text": rest.strip()}
    return {"titel": "", "text": text.strip()}


def vortext_parsen(text: str, briefanrede: str) -> dict:
    """Markdown-Struktur des Vortext-Textblocks (Parametrierung → Textblöcke) → Bausteine der Seite „Ihr
    Angebot im Überblick“ [ANNAHME Plan Phase 189]: führende „## “-Zeilen = Titel (stehen im neuen Layout auf
    dem Deckblatt, entfallen hier) · Briefanrede-Zeile ({briefanrede} oder „Sehr geehrte …“) · Absätze vor
    der ersten Liste → Einleitung · erste Liste („- “/„* “) → „Darin enthalten“ · „## Warum Friondo?“ (jede
    „## “-Zeile nach der ersten Liste) + zweite Liste → rechte Spalte · Absätze danach → Schluss („**…**“ =
    fett) · Grußzeilen („Ihr Friondo-Team“, „Mit herzlichen Grüßen, …“) → gruss. Eine „## “-Zeile nach der
    zweiten Liste (z. B. „Komplettpaket …“) wird fetter Schlussabsatz."""
    text = (text or "").replace("{briefanrede}", briefanrede)
    ergebnis = {"anrede": briefanrede, "einleitung": [], "enthalten_titel": ENTHALTEN_TITEL, "enthalten": [],
                "warum_titel": WARUM_TITEL, "warum": [], "schluss": [], "gruss": []}
    phase = "einleitung"          # einleitung → liste1 → zwischen → liste2 → schluss
    puffer: list[str] = []

    def absatz_schliessen(fett: bool = False) -> None:
        nonlocal phase
        if not puffer:
            return
        zeilen = [z.strip() for z in puffer if z.strip()]
        absatz = " ".join(zeilen).strip()
        puffer.clear()
        if not absatz:
            return
        if absatz.startswith(_GRUSS_START):
            ergebnis["gruss"].extend(zeilen)      # „Mit herzlichen Grüßen,“ / „Ihr Friondo-Team“ je Zeile
            return
        if phase in ("einleitung", "liste1"):
            ergebnis["einleitung"].append(absatz)
        else:
            ergebnis["schluss"].append({"text": absatz, "fett": fett})
            phase = "schluss"

    for zeile in text.splitlines():
        zeile = zeile.rstrip()
        if not zeile.strip():
            absatz_schliessen()
            continue
        m = _LISTE.match(zeile)
        if zeile.startswith("## "):
            absatz_schliessen()
            titel = zeile[3:].strip()
            if phase == "einleitung":
                continue                       # Titelzeilen → Deckblatt (SPARTEN)
            if phase == "liste1":
                ergebnis["warum_titel"] = titel
                phase = "zwischen"
            else:
                ergebnis["schluss"].append({"text": titel, "fett": True})
                phase = "schluss"
        elif m:
            absatz_schliessen()
            if phase in ("einleitung", "liste1"):
                ergebnis["enthalten"].append(_listeneintrag(m.group(1)))
                phase = "liste1"
            else:
                ergebnis["warum"].append(_listeneintrag(m.group(1)))
                phase = "liste2"
        elif zeile.startswith("**") and zeile.endswith("**") and len(zeile) > 4:
            absatz_schliessen()
            puffer.append(zeile[2:-2])
            absatz_schliessen(fett=True)
        elif zeile.strip() == briefanrede.strip() or (_ANREDE.match(zeile.strip()) and phase == "einleitung"
                                                     and not puffer):
            absatz_schliessen()
            ergebnis["anrede"] = zeile.strip()
        else:
            if phase in ("liste2", "zwischen"):
                phase = "schluss"
            puffer.append(zeile)
    absatz_schliessen()
    if not ergebnis["gruss"]:
        ergebnis["gruss"] = ["Ihr Friondo-Team"]
    return ergebnis


# ----------------------------------------------------------------------------- Nachtext → Auftrag / Bedingungen
def _segmente(zeile: str) -> list[dict]:
    """Text mit URLs → Segmente [{text, url}] für klickbare AGB-/Datenschutz-Links."""
    teile = []
    letzte = 0
    for m in _URL.finditer(zeile):
        if m.start() > letzte:
            teile.append({"text": zeile[letzte:m.start()], "url": None})
        url = m.group(1).rstrip(".,;)")
        teile.append({"text": url, "url": url})
        letzte = m.start() + len(url)
    if letzte < len(zeile):
        teile.append({"text": zeile[letzte:], "url": None})
    return teile or [{"text": zeile, "url": None}]


def nachtext_parsen(text: str) -> dict:
    """Nachtext-Textblock (A–C) → Seiten „Auftragserteilung“ und „Vertragsbedingungen“ des Layouts v3.
    Regeln: Seiten „---“; Platzhalter-Seiten [WIRTSCHAFTLICHKEIT]/[BEISPIELRECHNUNG]/[CLOOVER] entfallen
    (A2-Partial bzw. Teil B); „# “-Titel werden Zwischenüberschriften der Vertragsbedingungen (Ebene 1, z. B.
    „Installationsvoraussetzungen“ – auch ohne eigene Absätze), außer sie sind Seitentitel des Layouts v3
    (_SEITENTITEL: Zahlungsoptionen, Vertragsbedingungen, Auftragserteilung, Vollmacht …) – die entfallen;
    Nachtext A („# Ihre Zahlungsoptionen …“): erste
    „## “-Zeile → Untertitel der Karte 2, weitere „## “-Zeilen und Absätze → Karte-2-Text, alles unter
    „## Finanzierung mit Cloover“ (Boxen, Fußnote) entfällt – der Cloover-Block kommt wörtlich aus der
    Design-Vorlage; „### “-Abschnitte (auch auf der A-Seite: Unsere Leistungen, Installationsvoraussetzungen)
    → Vertragsbedingungen; Absätze mit Bindefrist/AGB/Datenschutz/Zusicherung/Gruß → Schlusskasten (jede
    Zeile einzeln, URLs klickbar); „~ “ → Fußnote (klein, z. B. Nullsteuersatz PV); „### Aufschiebende
    Bedingung“ → Auftragsseite (WP); „Voraussichtliches Datum der Umsetzung“/„Voraussichtlicher
    Ausführungszeitraum“ → Linie auf der Auftragsseite; der Satz „Sollte Ihnen das Angebot zusagen …“ und
    [UNTERSCHRIFT] entfallen (die Auftragsseite trägt Einleitung und Unterschriftszeile des Designs)."""
    ergebnis = {"abschnitte": [], "schluss": [], "fussnoten": [], "karte2_untertitel": "", "karte2_absaetze": [],
                "aufschiebende_bedingung": None, "umsetzungsdatum": False, "ausfuehrungszeitraum": False}
    for seite in (text or "").split("\n---\n"):
        if seite.strip() in PLATZHALTER_WIRTSCHAFTLICHKEIT or seite.strip() == PLATZHALTER_CLOOVER:
            continue
        in_a = "# Ihre Zahlungsoptionen" in seite
        in_cloover = False
        abschnitt: dict | None = None
        aufschiebend = False
        puffer: list[str] = []

        def absatz_schliessen() -> None:
            nonlocal abschnitt, aufschiebend
            if not puffer:
                return
            zeilen = [z.strip() for z in puffer if z.strip()]
            puffer.clear()
            if not zeilen:
                return
            if in_cloover:
                return
            if any(z.startswith(_SCHLUSS_START) for z in zeilen):
                for z in zeilen:
                    if z.startswith(_AUFTRAG_SATZ):
                        continue
                    ergebnis["schluss"].append(z)
                return
            absatz = " ".join(zeilen)
            if absatz.startswith(_AUFTRAG_SATZ):
                return
            if absatz.startswith(UMSETZUNG_VOR):
                ergebnis["umsetzungsdatum"] = True
                return
            if absatz.startswith(AUSFUEHRUNGSZEITRAUM):
                ergebnis["ausfuehrungszeitraum"] = True
                return
            if aufschiebend:
                ergebnis["aufschiebende_bedingung"] = ((ergebnis["aufschiebende_bedingung"] or "") + " "
                                                       + absatz).strip()
                return
            if abschnitt is not None:
                abschnitt["absaetze"].append(absatz)
            elif in_a:
                ergebnis["karte2_absaetze"].append(absatz)
            else:
                abschnitt = {"titel": "", "absaetze": [absatz], "ebene": 2}
                ergebnis["abschnitte"].append(abschnitt)

        for zeile in seite.splitlines():
            zeile = zeile.rstrip()
            s = zeile.strip()
            if not s:
                absatz_schliessen()
                continue
            if s in PLATZHALTER_WIRTSCHAFTLICHKEIT or s in (PLATZHALTER_CLOOVER, "[UNTERSCHRIFT]"):
                absatz_schliessen()
                continue
            if s.startswith("# ") and not s.startswith("## "):
                absatz_schliessen()
                titel = s[2:].strip()
                if in_cloover or any(t in titel.lower() for t in _SEITENTITEL):
                    continue                       # Seitentitel des Layouts v3 (z. B. Zahlungsoptionen)
                aufschiebend = False
                abschnitt = {"titel": titel, "absaetze": [], "ebene": 1}   # z. B. „Installationsvoraussetzungen“
                ergebnis["abschnitte"].append(abschnitt)
                continue
            if s.startswith("### "):
                absatz_schliessen()
                if in_cloover:
                    continue
                titel = s[4:].strip().rstrip(":")
                if titel.lower().startswith("aufschiebende bedingung"):
                    aufschiebend, abschnitt = True, None
                    continue
                aufschiebend = False
                abschnitt = {"titel": titel, "absaetze": [], "ebene": 2}
                ergebnis["abschnitte"].append(abschnitt)
                continue
            if s.startswith("## "):
                absatz_schliessen()
                titel = s[3:].strip()
                if in_a:
                    if "cloover" in titel.lower():
                        in_cloover = True
                    elif not ergebnis["karte2_untertitel"]:
                        ergebnis["karte2_untertitel"] = titel
                    else:
                        ergebnis["karte2_absaetze"].append(titel)
                else:
                    aufschiebend = False
                    abschnitt = {"titel": titel, "absaetze": [], "ebene": 2}
                    ergebnis["abschnitte"].append(abschnitt)
                continue
            if s.startswith("~ "):
                absatz_schliessen()
                if not in_cloover:
                    ergebnis["fussnoten"].append(s[2:].strip())
                continue
            puffer.append(zeile)
        absatz_schliessen()
    # leere „###“-Abschnitte entfallen; „#“-Überschriften (Ebene 1) bleiben auch ohne eigene Absätze
    ergebnis["abschnitte"] = [a for a in ergebnis["abschnitte"] if a["absaetze"] or a.get("ebene") == 1]
    return ergebnis


def bedingungen_aus(parsed: dict) -> dict:
    """Vertragsbedingungen-Teilbaum aus dem Parser-Ergebnis: Abschnitte, Schlusskasten (Zeilen mit
    klickbaren Links; Gruß „Mit freundlichen Grüßen“ / „Ihr Friondo-Team“ ohne Schlusskomma wie die
    Vorlage), Fußnoten."""
    absaetze, gruss, links = [], [], []
    for zeile in parsed["schluss"]:
        if zeile.startswith(_GRUSS_START):
            gruss.append(zeile.rstrip(","))
            continue
        segmente = _segmente(zeile)
        absaetze.append(segmente)
        links.extend({"text": t["text"], "url": t["url"]} for t in segmente if t["url"])
    if not gruss:
        gruss = ["Mit freundlichen Grüßen", "Ihr Friondo-Team"]
    return {"abschnitte": parsed["abschnitte"],
            "schluss": {"absaetze": absaetze, "links": links, "gruss": gruss},
            "fussnoten": parsed["fussnoten"]}


def kurzsatz(text: str) -> str:
    """Kurzsatz der Zahlungsbedingung für Karte 1 [ANNAHME Plan: erste Zeile; besteht sie aus mehr als zwei
    Sätzen, die ersten zwei – „Eine Anzahlung von 50% … zu zahlen. Die Restzahlung wird … fällig.“]."""
    zeile = next((z.strip() for z in (text or "").splitlines() if z.strip()), "")
    saetze = re.split(r"(?<=[.!?])\s+", zeile)
    return " ".join(saetze[:2]).strip()


# ----------------------------------------------------------------------------- Positionen
def _textzeilen(text: str) -> list[dict]:
    zeilen = []
    for roh in (text or "").splitlines():
        if not roh.strip():
            continue
        m = _PUNKT.match(roh.replace(" ", " "))
        if m:
            ebene = 2 if m.group("einzug") else 1
            zeilen.append({"text": m.group("text").strip(), "punkt": True, "ebene": ebene, "dezent": False})
        else:
            zeilen.append({"text": roh.strip(), "punkt": False, "ebene": 1, "dezent": False})
    return zeilen


def position_kontext(position, nummer: str, alt_sparte: str = "", alt_nummer: str = "") -> dict:
    """Eine Angebotsposition → Tabellenzeile: Bezeichnung (fett) = erste Textzeile (Bezeichnung, sonst
    erste Zeile der Beschreibung – Freitextpositionen), weitere Zeilen normal, „-“/„•“/„– “ → Aufzählung
    [ANNAHME]; Kennzeichen EP → G-Preis „EP.“, bauseits → E-/G-Preis „bauseits“, Alternativ → G-Preis
    „im PV-Angebot“ (elektro_pv.pdf_label) + v10-Vermerk unter dem Text; Positionsrabatt als Zeile
    „− Rabatt <x %|Betrag> (− 123,45 €)“ unter dem Text, G-Preis nach Rabatt; Sonderpreis/manuell geändert
    ohne Kennzeichen."""
    from app import elektro_pv
    text = position.beschreibung or ""
    erste = text.splitlines()[:1]
    bezeichnung = (position.bezeichnung or "").strip()
    if bezeichnung and bezeichnung not in erste:
        voll = bezeichnung + ("\n" + text if text else "")
    else:
        voll = text
    zeilen_roh = [z for z in voll.splitlines() if z.strip()]
    bezeichnung_fett = zeilen_roh[0].strip() if zeilen_roh else ""
    m = _PUNKT.match(bezeichnung_fett)
    if m:   # Freitextposition, deren erste Zeile ein Aufzählungspunkt ist: Punkt bleibt, Titel leer
        bezeichnung_fett = ""
        rest = zeilen_roh
    else:
        rest = zeilen_roh[1:]
    zeilen = _textzeilen("\n".join(rest))
    if position.rabatt_effektiv_cent and not position.bauseits:
        # Minus nur im Label, Betrag ohne Minus (wie der Summenblock, Abnahme A4 Nr. 10)
        rabatt_text = f"− Rabatt {position.rabatt_text}"
        if not position.rabatt_cent:
            rabatt_text += f" ({_euro(position.rabatt_effektiv_cent)})"
    else:
        rabatt_text = None
    if position.alternativ:
        zeilen.append({"text": ("Hinweis: Diese Position ist im parallel vorliegenden "
                                f"{position.alternativ_zu or 'Parallel-Angebot'} enthalten und kommt nur zum "
                                "Tragen, wenn ausschließlich das vorliegende Angebot beauftragt wird."),
                       "punkt": False, "ebene": 1, "dezent": True})
    from app.pdf_export import _menge_text
    eintrag = {"nr": nummer, "pos_nr": position.pos_nr or "", "menge": _menge_text(position.menge),
               "einheit": position.einheit or "", "bezeichnung": bezeichnung_fett, "zeilen": zeilen,
               "rabatt_text": rabatt_text, "hinweiskasten": None}
    if position.alternativ:
        eintrag.update(kennzeichen="alternativ", einzelpreis=_betrag_tabelle(position.e_preis_cent),
                       gesamtpreis=elektro_pv.pdf_label(alt_sparte))
    elif position.bauseits:
        eintrag.update(kennzeichen="bauseits", einzelpreis="bauseits", gesamtpreis="bauseits",
                       rabatt_text=None)
    elif position.ep_flag:
        eintrag.update(kennzeichen="ep", einzelpreis=_betrag_tabelle(position.e_preis_cent), gesamtpreis="EP.")
    else:
        eintrag.update(kennzeichen="", einzelpreis=_betrag_tabelle(position.e_preis_cent),
                       gesamtpreis=_betrag_tabelle(position.gesamt_cent))
    return eintrag


def gruppen_kontext(angebot) -> list[dict]:
    """Positionen in Gruppen (Gruppenüberschrift = fette Zwischenzeile, editierbar seit v22; Positionen ohne
    Gruppe laufen unter der vorigen Überschrift – wie pdf_export._positionsteil); je Block (Gruppe + Block-Nr.)
    genau ein Alternativ-Hinweiskasten vor der ersten Alternativ-Position (v34 Phase 180)."""
    from app import elektro_pv
    gruppen: list[dict] = []
    aktuell: dict | None = None
    kasten_gezeigt: set[tuple] = set()
    for position, nummer in zip(angebot.positionen, angebot.nummerierung()):
        gruppe = (position.gruppe or "").strip()
        if aktuell is None or (gruppe and gruppe != aktuell["titel"]):
            aktuell = {"titel": gruppe, "alternativ_hinweis": None, "positionen": []}
            gruppen.append(aktuell)
        alt_sparte = alt_nummer = ""
        if position.alternativ:
            alt_sparte, alt_nummer = elektro_pv.ziel_parsen(position.alternativ_zu)
        eintrag = position_kontext(position, nummer, alt_sparte, alt_nummer)
        if position.alternativ:
            schluessel = (gruppe or aktuell["titel"], position.block_nr or 0)
            if schluessel not in kasten_gezeigt:
                kasten_gezeigt.add(schluessel)
                eintrag["hinweiskasten"] = elektro_pv.hinweis_text(alt_sparte, alt_nummer)
                if aktuell["alternativ_hinweis"] is None:
                    aktuell["alternativ_hinweis"] = eintrag["hinweiskasten"]
        aktuell["positionen"].append(eintrag)
    return gruppen


def hinweise_kontext(angebot) -> list[dict]:
    """Vermerke (v9 bedingte Vermerke, v10/v34 Alternativ-Vermerk): erste Zeile = Titel, Rest = Text."""
    hinweise = []
    for vermerk in json.loads(getattr(angebot, "vermerke_json", "[]") or "[]"):
        zeilen = [z.strip() for z in str(vermerk).splitlines()]
        zeilen = [z for z in zeilen if z]
        if not zeilen:
            continue
        hinweise.append({"titel": zeilen[0], "text": " ".join(zeilen[1:])})
    return hinweise


# ----------------------------------------------------------------------------- Summen
def summen_kontext(summen: dict, ust_prozent, rabatt_bezeichnung: str = "",
                   foerderung: tuple | None = None) -> dict:
    """Summenblock aus Angebot.summen() (Cent; Netto → USt → Gesamt-Betrag → − Rabatt → = Endbetrag) und
    optional der KfW-Förderung (zuschuss_cent, eigenanteil_cent, prozent_text). Die dunkle Box trägt ohne
    Förderblock den Gesamt-Betrag bzw. Endbetrag [ANNAHME Plan], mit Förderblock „= Ihr Eigenanteil“."""
    netto, ust, gesamt = summen["netto"], summen["ust"], summen["brutto"]
    rabatt, endbetrag = summen.get("rabatt") or 0, summen["endbetrag"]
    ust_text = _ust_text(ust_prozent)
    zeilen = [{"text": "Netto-Summe", "betrag": _euro(netto), "fett": False, "blau": False, "linie": False},
              {"text": ust_text, "betrag": _euro(ust), "fett": False, "blau": False, "linie": False}]
    # Vorlage (Abnahme A4 Nr. 10): das Minus steht nur im Label („− Rabatt …“, „− voraussichtliche
    # KfW-Förderung (xx %)“), der Betrag ohne Minus („500,00 €“, „19.600,00 €“)
    rabatt_eintrag = None
    if rabatt:
        rabatt_eintrag = {"text": "− Rabatt" + (f" {rabatt_bezeichnung.strip()}" if rabatt_bezeichnung else ""),
                          "betrag": _euro(rabatt)}
    foerder_eintrag = None
    eigenanteil = None
    if foerderung is not None:
        zuschuss_cent, eigenanteil_cent, prozent = foerderung
        foerder_eintrag = {"text": f"− voraussichtliche KfW-Förderung ({prozent} %)",
                           "betrag": _euro(zuschuss_cent), "prozent": prozent}
        eigenanteil = _euro(eigenanteil_cent)
    if rabatt_eintrag or foerder_eintrag:
        zeilen.append({"text": "Gesamt-Betrag", "betrag": _euro(gesamt), "fett": True, "blau": False, "linie": True})
    if rabatt_eintrag:
        zeilen.append({"text": rabatt_eintrag["text"], "betrag": rabatt_eintrag["betrag"], "fett": False,
                       "blau": False, "linie": False})
        if foerder_eintrag:
            zeilen.append({"text": "= Endbetrag", "betrag": _euro(endbetrag), "fett": True, "blau": False,
                           "linie": False})
    if foerder_eintrag:
        zeilen.append({"text": foerder_eintrag["text"], "betrag": foerder_eintrag["betrag"], "fett": True,
                       "blau": True, "linie": False})
        box = {"titel": "= Ihr Eigenanteil", "betrag": eigenanteil, "hinweis": EIGENANTEIL_HINWEIS}
    elif rabatt_eintrag:
        box = {"titel": "= Endbetrag", "betrag": _euro(endbetrag), "hinweis": ""}
    else:
        box = {"titel": "Gesamt-Betrag", "betrag": _euro(gesamt), "hinweis": ""}
    return {"zeilen": zeilen, "box": box, "netto": _euro(netto), "ust_text": ust_text, "ust": _euro(ust),
            "gesamt": _euro(gesamt), "rabatt": rabatt_eintrag, "endbetrag": _euro(endbetrag),
            "foerderung": foerder_eintrag, "eigenanteil": eigenanteil,
            "hat_foerderung": foerder_eintrag is not None, "hat_rabatt": rabatt_eintrag is not None}


def _foerderung_fuer(session, angebot, kfw: dict | None = None) -> tuple | None:
    """(Zuschuss, Eigenanteil, Förderquote-Text) aus dem heutigen KfW-Ergebnis (pdf_export._kfw_ergebnis_fuer –
    Baustein-Overrides v8, manueller Zuschuss v6, MFH v9); None ohne Förderblock. Die Quote „(xx %)“ im
    Summenblock ist der Anteil des Zuschusses an der Angebotssumme (Endbetrag) – wie der Untertitel der
    KfW-Seite (Orchestrator 16.10.2026): liegt der Teilbaum von Agent A2 vor, gilt dessen `foerderquote`
    (Summe der gerundeten Baustein-Anteile), sonst Zuschuss ÷ Angebotssumme gerundet; NICHT der nominale
    KfW-Fördersatz (z. B. 70 %)."""
    from app import pdf_export
    ergebnis = pdf_export._kfw_ergebnis_fuer(session, angebot)
    if ergebnis is None:
        return None
    quote = (kfw or {}).get("foerderquote")
    if quote is None:
        summe_cent = ergebnis.zuschuss_cent + ergebnis.eigenanteil_cent
        quote = round(ergebnis.zuschuss_cent / summe_cent * 100) if summe_cent > 0 else 0
    return ergebnis.zuschuss_cent, ergebnis.eigenanteil_cent, _prozent_text(float(quote))


# ----------------------------------------------------------------------------- Auftrag / Vollmacht
def _fern_link(session, angebot) -> str:
    """Fern-Signatur-Link (Modul v4) nur mit BASIS_URL aus der .env, aktivem Schalter (Parametrierung oder
    SIGNATUR_FERN_AKTIV) und gültigem Token am Angebot (ausgestellt beim „Versand vorbereiten“) – dieses
    Modul stellt selbst keinen Token aus (liest nur) [ANNAHME]."""
    from app import config
    from app.models import einstellung_holen
    if not config.BASIS_URL_AUS_ENV:
        return ""
    aktiv = einstellung_holen(session, "signatur_fern_aktiv", "0") == "1" or config.SIGNATUR_FERN_AKTIV
    if not aktiv:
        return ""
    token = getattr(angebot, "signatur_token", None)
    gueltig = getattr(angebot, "signatur_token_gueltig_bis", None)
    if token and gueltig and gueltig > datetime.now():
        return f"{config.BASIS_URL}/signatur/extern/{token}"
    return ""


def karte1_kontext(zahlungstext: str, nummer: str, online_url: str = "", absender: str = "angebot@friondo.de") -> dict:
    """Karte 1 „BARKAUF – Online beauftragen“: Kurzsatz der Zahlungsbedingung, Knopf online (Fern-Signatur)
    oder per E-Mail (mailto an das Angebots-Postfach mit der Angebotsnummer im Betreff)."""
    if online_url:
        return {"titel": KARTE1_TITEL, "untertitel": KARTE1_UNTERTITEL, "text": kurzsatz(zahlungstext),
                "knopf_text": KNOPF_ONLINE, "knopf_url": online_url, "online": True}
    return {"titel": KARTE1_TITEL, "untertitel": KARTE1_UNTERTITEL, "text": kurzsatz(zahlungstext),
            "knopf_text": KNOPF_MAIL, "knopf_url": f"mailto:{absender}?subject={quote('Auftrag ' + nummer)}",
            "online": False}


_SLOGAN_KERN = re.sub(r"[^a-zäöüß]", "", SLOGAN.lower())


def ist_slogan(text: str) -> bool:
    """Cloover-Slogan „Saubere Energie. Faire Raten. Maximale Freiheit.“ – auch mit abweichender Zeichensetzung
    (Vergleich nur über die Buchstaben)."""
    return re.sub(r"[^a-zäöüß]", "", (text or "").lower()) == _SLOGAN_KERN


def karte2_kontext(profil: str, parsed: dict, cloover: dict | None) -> dict:
    """Karte 2 je Profil: Standard → Cloover (Rate/Laufzeit/Knopf aus Teil B, sonst „Monatsrate auf
    Anfrage“ ohne Knopf); Enni/SWD/Sparkasse DU → Titel laut Plan, Untertitel/Text aus dem heutigen
    Nachtext-A-Block (ohne Rate, ohne Knopf). Der Cloover-Slogan der v9-Seeds gehört nur zum Cloover-Block
    des Profils Standard und wird aus den Kartentexten der Kanal-Profile herausgefiltert (Abnahme A4 Nr. 12) –
    die Textblöcke selbst bleiben unverändert."""
    if profil in KARTE2_PROFILE:
        fest = KARTE2_PROFILE[profil]
        absaetze = [a for a in parsed.get("karte2_absaetze", []) if a and not ist_slogan(a)]
        return {"art": profil, "titel": fest["titel"],
                "untertitel": parsed.get("karte2_untertitel") or fest["untertitel"],
                "text": absaetze[0] if absaetze else "", "absaetze": absaetze, "knopf_text": "", "knopf_url": ""}
    karte = {"art": "cloover", "titel": KARTE2_CLOOVER["titel"], "untertitel": KARTE2_CLOOVER["untertitel"],
             "text": KARTE2_CLOOVER["text"], "absaetze": [KARTE2_CLOOVER["text"]], "knopf_text": "",
             "knopf_url": ""}
    if cloover and (cloover.get("rate_text") or cloover.get("rate_mit_text")):
        if cloover.get("checkout_link"):
            karte.update(knopf_text=KNOPF_CLOOVER, knopf_url=cloover["checkout_link"])
    else:
        karte["text"] = RATE_AUF_ANFRAGE
        karte["absaetze"] = [RATE_AUF_ANFRAGE]
    return karte


def auftrag_kontext(sparte: str, profil: str, parsed: dict, zahlungstext: str, nummer: str, *,
                    online_url: str = "", absender: str = "angebot@friondo.de",
                    cloover: dict | None = None) -> dict:
    return {"einleitung": AUFTRAG_EINLEITUNG,
            "karte1": karte1_kontext(zahlungstext, nummer, online_url, absender),
            "karte2": karte2_kontext(profil, parsed, cloover),
            "cloover_block": profil == "standard", "cloover": cloover if profil == "standard" else None,
            "cloover_anlage": CLOOVER_ANLAGE.get(sparte, "Anlage"), "cloover_texte": CLOOVER_BLOCK,
            "post_titel": POST_TITEL, "post_text": POST_TEXT,
            "aufschiebende_bedingung": parsed.get("aufschiebende_bedingung") or None,
            "umsetzungsdatum": bool(parsed.get("umsetzungsdatum")),
            "umsetzung_vor": UMSETZUNG_VOR, "umsetzung_nach": UMSETZUNG_NACH,
            "ausfuehrungszeitraum": bool(parsed.get("ausfuehrungszeitraum")),
            "ausfuehrungszeitraum_text": AUSFUEHRUNGSZEITRAUM, "unterschrift": dict(UNTERSCHRIFT)}


def vollmacht_kontext(name: str, adresse: str, telefon: str, email: str) -> dict:
    """Vollmacht (Nachtext D) wörtlich aus der Vorlage; Verbrauchsstelle vorbelegt (leer → Linie)."""
    return {"titel": VOLLMACHT_TITEL, "absaetze": [dict(a) for a in VOLLMACHT_ABSAETZE],
            "verbrauchsstelle_titel": "Angaben zur Verbrauchsstelle",
            "verbrauchsstelle": [{"label": "Name:", "wert": name or ""}, {"label": "Adresse:", "wert": adresse or ""},
                                 {"label": "Geburtsdatum:", "wert": ""}, {"label": "Telefon:", "wert": telefon or ""},
                                 {"label": "E-Mail:", "wert": email or ""}],
            "kaestchen_titel": "Bitte ankreuzen", "kaestchen": list(VOLLMACHT_KAESTCHEN),
            "sepa_titel": "SEPA-Lastschriftmandat", "sepa_text": VOLLMACHT_SEPA_TEXT,
            "sepa_zeilen": list(VOLLMACHT_SEPA_ZEILEN), "unterschriften": list(VOLLMACHT_UNTERSCHRIFTEN)}


def _ansprechpartner(session, angebot, benutzer) -> dict:
    """AD des Vorgangs (Erfassung → vertriebler_id → vorgaenge.ad_id), sonst der vorbereitende
    Innendienstler (`benutzer`, von der Route übergeben); Telefon aus der Benutzerverwaltung."""
    from app import mail_vorlagen
    from app.models import Benutzer, Vorgang
    person = mail_vorlagen.vertriebler_fuer_angebot(session, angebot)
    if person is None and getattr(angebot, "vorgang_id", None):
        vorgang = session.get(Vorgang, angebot.vorgang_id)
        if vorgang is not None and getattr(vorgang, "ad_id", None):
            person = session.get(Benutzer, vorgang.ad_id)
    if person is None:
        person = benutzer
    if person is None:
        return {"name": "", "telefon": ""}
    return {"name": (getattr(person, "name", "") or "").strip(),
            "telefon": (getattr(person, "telefon", "") or "").strip()}


def _profil(session, angebot, kunde) -> tuple[str, str]:
    from app import angebotsprofile
    profil = angebotsprofile.profil_fuer_angebot(session, angebot, kunde)
    if profil is None:
        return "standard", "Standard"
    kennung = (profil.regel_kennung or "standard").strip().lower()
    if kennung not in ("standard", "enni", "swd", "sparkasse"):
        kennung = "standard"
    return kennung, profil.name


def _teilbaum(modulname: str, session, angebot):
    """Teilbäume von Agent A2 / Teil B – fehlt das Modul, bleibt der Teilbaum None."""
    import importlib
    try:
        modul = importlib.import_module(modulname)
    except ImportError:
        return None
    funktion = getattr(modul, "kontext", None)
    if funktion is None:
        return None
    return funktion(session, angebot)


def _cloover(session, angebot) -> dict | None:
    """Teil B: app.cloover.kontext_fuer_pdf(session, angebot) – ohne Modul/Funktion (oder solange die
    Funktion noch NotImplementedError wirft) None; ein Fehler im Finanzierungs-Teilbaum verhindert nie das
    Angebots-PDF (Warnung im Log, Karte „Monatsrate auf Anfrage“)."""
    import importlib
    import logging
    try:
        modul = importlib.import_module("app.cloover")
    except ImportError:
        return None
    funktion = getattr(modul, "kontext_fuer_pdf", None)
    if funktion is None:
        return None
    try:
        return funktion(session, angebot)
    except NotImplementedError:
        return None
    except Exception as e:   # noqa: BLE001 – Finanzierungskarte ist Zusatz, nie ein Grund abzubrechen
        logging.getLogger("angebotstool.pdf").warning("Cloover-Teilbaum für das PDF nicht verfügbar: %s", e)
        return None


# ----------------------------------------------------------------------------- Hauptfunktion
def fuer_angebot(session, angebot, *, signatur: dict | None = None, fassung: str = "kunde",
                 benutzer=None) -> dict:
    """Vollständiger Kontext (Vertrag im Modul-Docstring) aus den heutigen Datenquellen von app/pdf_export.py:
    Anschriften v20/v31, Positionen mit Kennzeichen, Summen (Angebot.summen), Rabatt, KfW-Ergebnis, Vermerke,
    Zahlungsbedingung v30, Textblöcke v9, Vollmacht-Regel, Signatur; `kfw`/`wirtschaftlichkeit` über die
    Module von Agent A2, `auftrag.cloover` über Teil B (fehlende Module → None). `benutzer` = der
    vorbereitende Innendienstler (Ansprechpartner ohne AD). Liest nur – keine Schreibzugriffe."""
    from app import angebotsprofile, anschriften, pdf_export, zahlungsbedingungen
    from app.models import Angebot, Kunde, einstellung_holen
    kunde = session.get(Kunde, angebot.kunde_id) if getattr(angebot, "kunde_id", None) else None
    kontext = basis(session, angebot, signatur=signatur, fassung=fassung)
    sparte = kontext["sparte"]
    # Angebot: Profil, Version, Kopie
    kennung, profil_name = _profil(session, angebot, kunde)
    kontext["angebot"]["profil"] = kennung
    kontext["angebot"]["profil_name"] = profil_name
    kontext["angebot"]["ersetzt_hinweis"] = pdf_export._ersetzt_hinweis(session, angebot)
    if getattr(angebot, "vorgaenger_id", None):
        vorgaenger = session.get(Angebot, angebot.vorgaenger_id)
        if vorgaenger is not None:
            kontext["angebot"]["version_von"] = {"nummer": vorgaenger.nummer, "datum": _datum(vorgaenger.datum)}
    # Empfänger (v20/v31): Rechnungsanschrift, Ausführungsort, Lieferanschrift
    ort = anschriften.ausfuehrungsort_fuer(session, angebot=angebot, kunde=kunde)
    zeilen, abweichend = anschriften.empfaenger(angebot, kunde, ort) if kunde is not None else ([], False)
    ausfuehrung = anschriften.adresszeile(ort) if (abweichend and kunde is not None) else ""
    lieferzeile = anschriften.lieferzeile(angebot, kunde, ort) if kunde is not None else ""
    kontext["empfaenger"] = {"zeilen": zeilen, "ausfuehrungsort": ausfuehrung or None,
                             "lieferanschrift": lieferzeile or None}
    kontext["ansprechpartner"] = _ansprechpartner(session, angebot, benutzer)
    # Überblick (Vortext-Textblock)
    kontext["ueberblick"] = vortext_parsen(angebotsprofile.vortext_fuer_angebot(session, angebot),
                                           kontext["kunde"]["briefanrede"])
    # Teilbäume A2 (kfw zuerst – die Förderquote des Summenblocks folgt der KfW-Seite)
    kontext["kfw"] = _teilbaum("app.pdf_kontext_kfw", session, angebot) if sparte == "WP" else None
    kontext["wirtschaftlichkeit"] = (_teilbaum("app.pdf_kontext_wirtschaftlichkeit", session, angebot)
                                     if sparte == "PV" else None)
    # Positionen, Vermerke, Summen
    kontext["gruppen"] = gruppen_kontext(angebot)
    kontext["hinweise"] = hinweise_kontext(angebot)
    kontext["summen"] = summen_kontext(angebot.summen(), angebot.ust_prozent,
                                       getattr(angebot, "rabatt_bezeichnung", "") or "",
                                       _foerderung_fuer(session, angebot, kontext["kfw"]))
    # Auftrag / Bedingungen (Nachtext-Textblock + Zahlungsbedingung v30)
    _zb_name, zb_text = zahlungsbedingungen.fuer_angebot(session, angebot)
    nachtext = zahlungsbedingungen.text_einsetzen(angebotsprofile.nachtext_fuer_angebot(session, angebot), zb_text)
    parsed = nachtext_parsen(nachtext)
    cloover = _cloover(session, angebot) if kennung == "standard" else None
    absender = einstellung_holen(session, "mail_absender", "angebot@friondo.de") or "angebot@friondo.de"
    kontext["auftrag"] = auftrag_kontext(sparte, kennung, parsed, zb_text, kontext["angebot"]["nummer"],
                                         online_url=_fern_link(session, angebot), absender=absender,
                                         cloover=cloover)
    kontext["bedingungen"] = bedingungen_aus(parsed)
    # Vollmacht (Regel unverändert: 016/017 bzw. WB immer; Enni/SWD ohne)
    if kunde is not None and pdf_export._mit_vollmacht(session, angebot):
        name = kunde.firma or " ".join(t for t in (kunde.vorname, kunde.nachname) if t)
        kontext["vollmacht"] = vollmacht_kontext(name, anschriften.adresszeile(ort), kunde.telefon, kunde.email)
    else:
        kontext["vollmacht"] = None
    kontext["signatur"] = signatur
    return kontext


# ----------------------------------------------------------------------------- Demo (ohne Datenbank)
def demo_kontext(sparte: str = "WP", *, mit_signatur: bool = False) -> dict:
    """Vollständiger Kontext mit Demo-Daten (Max Mustermann, keine Kundendaten) für Tests, Browser-Test und die
    Entwicklung der Vorlagen – dieselben Parser und Bausteine wie `fuer_angebot` (Vortext/Nachtext aus den
    Seed-Konstanten von app/angebotsprofile.py). Zahlen sind Beispiele (WP: Endbetrag 42.830,55 €,
    Förderung 16.500,00 €)."""
    from app import angebotsprofile, zahlungsbedingungen
    sparte = sparte if sparte in SPARTEN else "WP"
    heute = date(2026, 10, 16)
    ust_satz = 0 if sparte == "PV" else 19
    kontext = {**sparte_kontext(sparte), "fassung": "kunde", "firma": firma_kontext()}
    kontext["angebot"] = {"nummer": "AN-C-269999", "datum": _datum(heute), "datum_iso": heute.isoformat(),
                          "gueltig_bis": _datum(heute + timedelta(days=BINDEFRIST_TAGE)),
                          "bindefrist_tage": BINDEFRIST_TAGE, "status": "Entwurf", "version_von": None,
                          "ersetzt_hinweis": "", "kopie_von": None, "profil": "standard",
                          "profil_name": "Standard", "ust_satz": ust_satz}
    kontext["kunde"] = {"name": "Max Mustermann", "anrede": "Herr", "vorname": "Max", "nachname": "Mustermann",
                        "firma": "", "briefanrede": "Sehr geehrter Herr Mustermann,", "telefon": "0203 1234567",
                        "email": "max.mustermann@example.de"}
    kontext["empfaenger"] = {"zeilen": ["Herr Max Mustermann", "Musterstraße 12", "47139 Duisburg"],
                             "ausfuehrungsort": None, "lieferanschrift": None}
    kontext["ansprechpartner"] = {"name": "Erika Beispiel", "telefon": "0203 - 3965 710"}
    vortexte = {"WP": angebotsprofile.STANDARD_VORTEXT,
                "PV": getattr(angebotsprofile, "PV_VORTEXT_V36", angebotsprofile.PV_VORTEXT),
                "KL": getattr(angebotsprofile, "KL_VORTEXT_V36", angebotsprofile.KL_VORTEXT),
                "WB": getattr(angebotsprofile, "WB_VORTEXT_V36", angebotsprofile.WB_VORTEXT)}
    kontext["ueberblick"] = vortext_parsen(vortexte[sparte], kontext["kunde"]["briefanrede"])
    positionen = [
        {"nr": "001", "pos_nr": "045", "menge": "1,00", "einheit": "psl.",
         "bezeichnung": "Bosch Compress 7000i AW 9 kW – Wärmepumpen-Paket",
         "zeilen": [{"text": "Luft-Wasser-Wärmepumpe mit Inneneinheit AWE und 300-l-Warmwasserspeicher",
                     "punkt": False, "ebene": 1, "dezent": False},
                    {"text": "Monoblock-Außeneinheit, Kältemittel R290", "punkt": True, "ebene": 1, "dezent": False},
                    {"text": "Inneneinheit mit Hocheffizienzpumpe", "punkt": True, "ebene": 1, "dezent": False}],
         "einzelpreis": "18.900,00", "gesamtpreis": "18.900,00", "kennzeichen": "", "rabatt_text": None,
         "hinweiskasten": None},
        {"nr": "002", "pos_nr": "060", "menge": "1,00", "einheit": "psl.",
         "bezeichnung": "Hydraulische Einbindung und Pufferspeicher 50 l",
         "zeilen": [{"text": "Einbindung in das bestehende Heizsystem inkl. Armaturen", "punkt": False, "ebene": 1,
                     "dezent": False}],
         "einzelpreis": "3.450,00", "gesamtpreis": "3.450,00", "kennzeichen": "", "rabatt_text": None,
         "hinweiskasten": None},
        {"nr": "003", "pos_nr": "120", "menge": "1,00", "einheit": "psl.",
         "bezeichnung": "Demontage und Entsorgung der Altanlage",
         "zeilen": [{"text": "Fachgerechte Entsorgung mit Nachweis", "punkt": False, "ebene": 1, "dezent": False}],
         "einzelpreis": "1.250,00", "gesamtpreis": "1.187,50", "kennzeichen": "",
         "rabatt_text": "− Rabatt 5 % (62,50 €)", "hinweiskasten": None},
        {"nr": "004", "pos_nr": "017", "menge": "1,00", "einheit": "psl.",
         "bezeichnung": "SpotDynamic-Tarif – Anmeldung und Einrichtung",
         "zeilen": [{"text": "Eventualposition – nur bei Beauftragung", "punkt": False, "ebene": 1, "dezent": False}],
         "einzelpreis": "590,00", "gesamtpreis": "EP.", "kennzeichen": "ep", "rabatt_text": None,
         "hinweiskasten": None},
        {"nr": "005", "pos_nr": "102", "menge": "1,00", "einheit": "psl.",
         "bezeichnung": "Fundament für die Außeneinheit",
         "zeilen": [{"text": "Wird vom Auftraggeber gestellt", "punkt": False, "ebene": 1, "dezent": False}],
         "einzelpreis": "bauseits", "gesamtpreis": "bauseits", "kennzeichen": "bauseits", "rabatt_text": None,
         "hinweiskasten": None},
    ]
    from app import elektro_pv
    elektro = [
        {"nr": "006", "pos_nr": "011", "menge": "1,00", "einheit": "psl.",
         "bezeichnung": "Elektroanschluss der Wärmepumpe",
         "zeilen": [{"text": "Zuleitung, Absicherung, Anschluss der Außen- und Inneneinheit", "punkt": False,
                     "ebene": 1, "dezent": False}],
         "einzelpreis": "2.400,00", "gesamtpreis": "2.400,00", "kennzeichen": "", "rabatt_text": None,
         "hinweiskasten": None},
        {"nr": "007", "pos_nr": "104", "menge": "1,00", "einheit": "psl.",
         "bezeichnung": "Zählerschrank-Erweiterung",
         "zeilen": [{"text": "Hinweis: Diese Position ist im parallel vorliegenden PV-Angebot AN-C-269998 "
                             "enthalten und kommt nur zum Tragen, wenn ausschließlich das vorliegende Angebot "
                             "beauftragt wird.", "punkt": False, "ebene": 1, "dezent": True}],
         "einzelpreis": "1.890,00", "gesamtpreis": elektro_pv.pdf_label("PV"), "kennzeichen": "alternativ",
         "rabatt_text": None, "hinweiskasten": elektro_pv.hinweis_text("PV", "AN-C-269998")},
    ]
    kontext["gruppen"] = [
        {"titel": "Wärmepumpe und Hydraulik", "alternativ_hinweis": None, "positionen": positionen},
        {"titel": "Elektroarbeiten", "alternativ_hinweis": elektro[1]["hinweiskasten"], "positionen": elektro},
    ]
    kontext["hinweise"] = [{"titel": "Hinweis zur Alternativ-Position",
                            "text": "Position 007 ist in Ihrem PV-Angebot AN-C-269998 enthalten und wird dort berechnet."}]
    if sparte == "WP":
        # 36.412,23 € netto + 19 % = 43.330,55 € − 500,00 € Rabatt = 42.830,55 € (Demo-Kontrollwert)
        summen = {"netto": 3641223, "ust": 691832, "brutto": 4333055, "rabatt": 50000, "endbetrag": 4283055}
        kontext["summen"] = summen_kontext(summen, 19, "Aktionsnachlass", (1650000, 2633055, "55"))
    else:
        netto = 2000000
        ust = 0 if ust_satz == 0 else 380000
        summen = {"netto": netto, "ust": ust, "brutto": netto + ust, "rabatt": 0, "endbetrag": netto + ust}
        kontext["summen"] = summen_kontext(summen, ust_satz, "", None)
    # Teilbäume kfw / wirtschaftlichkeit: Demo-Strukturen liefern die Module von Agent A2
    kontext["kfw"] = None
    kontext["wirtschaftlichkeit"] = None
    if sparte == "WP":
        try:
            from app import pdf_kontext_kfw
            kontext["kfw"] = pdf_kontext_kfw.demo()
        except Exception:   # noqa: BLE001 – Modul folgt (Phase 189, A2)
            kontext["kfw"] = None
    if sparte == "PV":
        try:
            from app import pdf_kontext_wirtschaftlichkeit
            kontext["wirtschaftlichkeit"] = pdf_kontext_wirtschaftlichkeit.demo()
        except Exception:   # noqa: BLE001 – Modul folgt (Phase 189, A2)
            kontext["wirtschaftlichkeit"] = None
    nachtexte = {"WP": angebotsprofile.STANDARD_NACHTEXT, "PV": angebotsprofile.PV_STANDARD_NACHTEXT,
                 "KL": angebotsprofile.KL_STANDARD_NACHTEXT, "WB": angebotsprofile.WB_STANDARD_NACHTEXT}
    parsed = nachtext_parsen(zahlungsbedingungen.text_einsetzen(nachtexte[sparte],
                                                                zahlungsbedingungen.STANDARD_ABSATZ))
    cloover = ({"rate_text": "389,99 €", "rate_mit_text": "242,70 €" if sparte == "WP" else "", "laufzeit": 20,
                "fussnote": ("*Unverbindliche Beispielrechnung unseres Finanzierungspartners Cloover auf Basis "
                             "des Endbetrags dieses Angebots von 42.830,55 €, einer Laufzeit von 20 Jahren und "
                             "0,00 € Anzahlung; ‚mit Förderung‘ berücksichtigt die voraussichtliche Förderung "
                             "von 16.500,00 € als Sondertilgung nach Auszahlung. Stand 16.10.2026. Verbindliche "
                             "Konditionen, Sollzins und effektiver Jahreszins ergeben sich aus dem "
                             "Finanzierungsangebot von Cloover."),
                "checkout_link": "", "qr_svg": "", "datenschutz": "",
                "hinweis_link": "Ihren persönlichen Finanzierungs-Link erhalten Sie von uns per E-Mail."}
               if sparte == "WP" else None)
    kontext["auftrag"] = auftrag_kontext(sparte, "standard", parsed, zahlungsbedingungen.STANDARD_ABSATZ,
                                         "AN-C-269999", cloover=cloover)
    kontext["bedingungen"] = bedingungen_aus(parsed)
    kontext["vollmacht"] = None if sparte == "KL" else vollmacht_kontext(
        "Max Mustermann", "Musterstraße 12, 47139 Duisburg", "0203 1234567", "max.mustermann@example.de")
    kontext["signatur"] = ({"bild_data_url": "", "name": "Max Mustermann", "zeitstempel": "16.10.2026 14:30",
                            "geraet": "Demo"} if mit_signatur else None)
    return kontext
