"""v36 (PLAN_V22 Phase 189, Agent A2): Kontext-Teilbaum ``kfw`` des Angebots-PDFs – Seite „Ihre KfW-Förderung“
(nur WP mit Förderblock). Vorlage: docs/design-v36/vorlage/entpackt/angebot-waermepumpe.html, Abschnitt
„KfW-Förderung“; Wortlaute 1:1, Positionsnummern dynamisch.

Rechenwerte kommen ausschließlich aus den heutigen Quellen – ``pdf_export._kfw_ergebnis_fuer`` (app/kfw.py mit
den Parametern des Blatts „KfW“, Eingaben aus ``angebote.kfw_json``, Baustein-Übersteuerung v8
``foerder_*``, Alt-Override v6 ``foerderung_manuell_cent``, MFH-Aufschlüsselung v9) – und werden hier NUR
aufbereitet: alle Beträge als Text „1.234,56 €“, Prozentwerte als Zahl/Text, nie neu gerechnet.

Schlüssel von ``kontext(session, angebot)`` bzw. ``demo()`` (None, wenn kein WP, Förderblock ausgeblendet,
``pdf_export.foerderblock_moeglich`` False oder keine KfW-Daten am Angebot):

  eyebrow             „ANTRAG: KFW 458 (WOHNGEBÄUDE)“ (Programmzeile des KfW-Ergebnisses in Großschreibung)
  programm            „KfW 458 (Wohngebäude)“
  titel               „Ihre KfW-Förderung“
  untertitel          „<F> % zahlt die KfW – <100−F> % bleiben für Sie“
  foerderquote        int – F = Anteil des KfW-Zuschusses an der Angebotssumme (Summe der gerundeten
                      Baustein-Anteile des Balkens, damit Balken, Untertitel und Eigenanteil zusammenpassen)
  eigenquote          int – 100 − foerderquote
  foerdersatz         str – nominaler Fördersatz laut KfW-Ergebnis („70 %“; MFH: effektiver Satz)
  satz_text           str – Satz-Zeile des KfW-Ergebnisses ohne „manuell“-Zusätze
  angebotssumme       „35.992,06 €“ (Endbetrag = Basis der KfW-Rechnung), angebotssumme_zusatz „(inkl. 19 % USt.)“
  foerderfaehig       „28.000,00 €“ (förderfähige Kosten), hoechstkosten „28.000,00 €“ (Zeile „Förderfähig bis …“)
  balken              [{key, klasse, name, prozent (int, Anteil an der Angebotssumme), breite_prozent (str, CSS),
                        betrag, kompakt (bool: nur Name + Prozent), schmal (bool: nur Prozent)}] – Segmente
                        Grund · Klima · Einkommen (fehlende Bausteine entfallen) + „Ihr Eigenanteil“; Breiten
                        anteilig an der Angebotssumme
  bausteine           [{key, klasse, name, prozent_text („30 %“, angewandter Satz), mfh_zusatz
                        („(16 % anteilig WE)“ | „“), klammer („(30 %)“ | „(16 % anteilig WE)“), betrag}]
  zuschuss            „19.600,00 €“ (Zeile „KfW-Zuschuss gesamt“), eigenanteil „16.392,06 €“
  deckel_satz         str | None – nur bei gedeckelten Boni, Wortlaut aus app/kfw.py
  hinweise            [str] – alle Hinweise des KfW-Ergebnisses ohne „manuell“-Kennzeichen (Deckel-Satz,
                      MFH-Näherung, Höchstkosten-Satz, Gewerbe-Hinweis) in der Reihenfolge von app/kfw.py
  disclaimer          str – Disclaimer der Logik-Excel, „Konditionen ab <Angebotsdatum>“
  konditionen_ab      „TT.MM.JJJJ“ (Angebotsdatum)
  schritte            [{nr, titel, text}] – sechs Schritte wörtlich; „Pos. 017“ → tatsächliche Nummer der
                      BzA-Position, Klammerzusatz entfällt ohne Position
  gut_zu_wissen       [str] – wörtlich, „(Pos. 008)“ → tatsächliche Nummer der Hydraulik-Position
  antrag_unterlagen   [str] – wörtlich
  pos_bza, pos_hydraulik   „018“ | None – Anzeigenummern (Angebot.nummerierung) der beiden Positionen
  manuell             bool – Förderung manuell angepasst/übersteuert (nur Kennzeichen, wird nie gedruckt)
  mfh                 bool, wohneinheiten int, objekt „efh“ | „mfh“ | „nwg“
  bild                „bilder/kfw.png“ – KfW-Wortmarke (im Template {{ static }}/pdf/bilder/kfw.png)

Zuordnung der festen Positionsnummern der Vorlage („Pos. 017“ = KfW-Förderantragsunterstützung, „Pos. 008“ =
hydraulischer Abgleich – dort Nummern des Beispielangebots): im Artikelstamm ist die BzA-Position der Artikel
mit TAIFUN-Pos. 012 („ANTRAG BEG EM“, Erstellung der LuL, BzA und BnD …), der hydraulische Abgleich der
Artikel mit TAIFUN-Pos. 008 („Hydraulischer Abgleich für Ihr neues Heizungssystem …“); gedruckt wird die
fortlaufende Anzeigenummer der Position in diesem Angebot. Rückfall ohne Artikelnummer (Freitext/editierte
Position): Titelzeile mit „BzA“ bzw. „Hydraulischer Abgleich“.
"""
from __future__ import annotations

import json
import re
from datetime import date, datetime

from app import kfw

TITEL = "Ihre KfW-Förderung"
BILD = "bilder/kfw.png"
ARTIKEL_BZA = "012"          # TAIFUN-Pos. „ANTRAG BEG EM“ – Erstellung der LuL, BzA und BnD (KfW Förderantragsunterstützung)
ARTIKEL_HYDRAULIK = "008"    # TAIFUN-Pos. 1013 – Hydraulischer Abgleich für Ihr neues Heizungssystem
_MUSTER_BZA = re.compile(r"\bBzA\b")
_MUSTER_HYDRAULIK = re.compile(r"hydraulische[rn]?\s+Abgleich", re.IGNORECASE)
_MUSTER_KONDITIONEN = re.compile(r"Konditionen ab \d{1,2}\.\d{1,2}\.\d{4}")
_MANUELL_ZUSAETZE = (" · Zuschuss manuell festgelegt", " · Förderung manuell angepasst")

# Wortlaute 1:1 aus der Design-Vorlage (Abschnitt „So läuft Ihre Förderung ab“, Boxen „Gut zu wissen“ und
# „Das brauchen Sie für den Antrag“). {pos_bza} / {pos_hydraulik} werden mit der tatsächlichen Positionsnummer
# gefüllt („, Pos. 018“ bzw. „ (Pos. 007)“) oder entfallen, wenn die Position im Angebot fehlt.
SCHRITTE = (
    ("Angebot annehmen",
     "Online oder per Post – der Vertrag gilt unter aufschiebender Bedingung bis zur Förderzusage."),
    ("Friondo erstellt die Unterlagen",
     "Leistungs- und Lieferungsbestätigung (LuL) sowie Bestätigung zum Antrag (BzA) – kostenfrei{pos_bza}."),
    ("Antrag im KfW-Portal",
     "Sie stellen den Antrag unter „Meine KfW“ mit der BzA-ID – wir unterstützen Sie Schritt für Schritt."),
    ("Förderzusage der KfW",
     "Mit der Zusage tritt die aufschiebende Bedingung ein – der Vorhabensbeginn wird ausgelöst."),
    ("Installation durch Friondo",
     "Montage, hydraulischer Abgleich und Inbetriebnahme innerhalb des Bewilligungszeitraums."),
    ("Nachweis & Auszahlung",
     "Wir erstellen die Bestätigung nach Durchführung (BnD); Sie reichen sie mit der Rechnung ein – "
     "die KfW zahlt den Zuschuss aus."),
)
GUT_ZU_WISSEN = (
    "Gefördert wird über das Programm „Heizungsförderung für Privatpersonen – Wohngebäude“ (KfW 458).",
    "Der hydraulische Abgleich{pos_hydraulik} ist Fördervoraussetzung und im Angebot enthalten.",
    "Am Installationsort darf kein Anschluss- oder Benutzungszwang an ein Wärmenetz bestehen.",
    "Keine Kombination mit der steuerlichen Förderung nach § 35c EStG.",
)
ANTRAG_UNTERLAGEN = (
    "Zugang zum KfW-Portal „Meine KfW“ (Registrierung mit E-Mail-Adresse)",
    "Die BzA-ID aus der Bestätigung zum Antrag von Friondo",
    "Angaben zum Gebäude und zur selbstgenutzten Wohneinheit",
    "Für den Einkommensbonus: Einkommensteuerbescheide des Haushalts",
)

_BAUSTEIN_NAMEN = {"grund": "Grundförderung", "klima": "Klimageschwindigkeits-Bonus",
                   "einkommen": "Einkommensbonus", "zuschuss": "KfW-Zuschuss"}
_BALKEN_NAMEN = {"grund": "Grund", "klima": "Klima", "einkommen": "Einkommen", "zuschuss": "KfW-Zuschuss"}
_KOMPAKT_AB_PROZENT = 14.0   # schmale Segmente zeigen nur Name und Prozent (Vorlage: „Klima“ / „8 %“)
_SCHMAL_AB_PROZENT = 9.0     # sehr schmale Segmente (< 9 % ≈ 16 mm) zeigen nur den Prozentwert


# ----------------------------------------------------------------------------- Helfer
def _euro(cent: int) -> str:
    return kfw._euro(int(cent))


def _prozent_text(zahl: float) -> str:
    return kfw._prozent(zahl)


def _zahl(text: str) -> float | None:
    return kfw._zahl(text or "")


def _euro_cent(text: str) -> int | None:
    """„12.781,58 €“ → 1278158; „–“ → None."""
    wert = _zahl(text)
    return None if wert is None else int(round(wert * 100))


def _datum_text(wert) -> str:
    if isinstance(wert, (datetime, date)):
        return wert.strftime("%d.%m.%Y")
    return str(wert or "")


def _ohne_manuell(satz_text: str) -> str:
    for zusatz in _MANUELL_ZUSAETZE:
        satz_text = satz_text.replace(zusatz, "")
    return satz_text


def _hinweise_filtern(hinweise: list[str]) -> list[str]:
    return [h for h in hinweise if not h.startswith("Förderung manuell angepasst")]


def _prozente_summe_100(anteile: list[float]) -> list[int]:
    """Anteile (0…100, Summe ≈ 100) so runden, dass sich die ganzen Prozentwerte zu 100 ergänzen
    (größter Rest)."""
    if not anteile:
        return []
    ganz = [int(a) for a in anteile]
    rest = 100 - sum(ganz)
    reihenfolge = sorted(range(len(anteile)), key=lambda i: anteile[i] - ganz[i], reverse=True)
    for i in range(abs(rest)):
        ganz[reihenfolge[i % len(anteile)]] += 1 if rest > 0 else -1
    return ganz


# ----------------------------------------------------------------------------- Positionen
def positionsnummern(angebot) -> dict:
    """Anzeigenummern der BzA- und der Hydraulik-Position dieses Angebots (None = fehlt). Artikelnummer
    (TAIFUN-Pos. 012 / 008) hat Vorrang, Rückfall über die Titelzeile; bauseits/Alternativ zählen nicht."""
    nummern = {"bza": None, "hydraulik": None}
    paare = [(nr, p) for nr, p in zip(angebot.nummerierung(), angebot.positionen)
             if not (getattr(p, "bauseits", False) or getattr(p, "alternativ", False))]
    for nr, p in paare:
        if nummern["bza"] is None and (p.pos_nr or "").strip() == ARTIKEL_BZA:
            nummern["bza"] = nr
        if nummern["hydraulik"] is None and (p.pos_nr or "").strip() == ARTIKEL_HYDRAULIK:
            nummern["hydraulik"] = nr
    for nr, p in paare:                                   # Rückfall: Titelzeile (Freitext, editierte Texte)
        titel = p.titel or ""
        if nummern["bza"] is None and _MUSTER_BZA.search(titel):
            nummern["bza"] = nr
        if nummern["hydraulik"] is None and _MUSTER_HYDRAULIK.search(titel):
            nummern["hydraulik"] = nr
    return nummern


def _schritte(pos_bza: str | None) -> list[dict]:
    zusatz = f", Pos. {pos_bza}" if pos_bza else ""
    return [{"nr": i, "titel": titel, "text": text.format(pos_bza=zusatz)}
            for i, (titel, text) in enumerate(SCHRITTE, 1)]


def _gut_zu_wissen(pos_hydraulik: str | None) -> list[str]:
    zusatz = f" (Pos. {pos_hydraulik})" if pos_hydraulik else ""
    return [text.format(pos_hydraulik=zusatz) for text in GUT_ZU_WISSEN]


# ----------------------------------------------------------------------------- Bausteine
def _bausteine(ergebnis: "kfw.KfwErgebnis", objekt: str, manuell_gesamt: bool) -> list[dict]:
    """Baustein-Aufschlüsselung in Cent aus den Zeilen des KfW-Ergebnisses (nur Aufbereitung).

    MFH (v9): Beträge stehen bereits je Zeile („Grundförderung (30 %)“, „Klimageschwindigkeits-Bonus (16 %
    anteilig auf die selbstgenutzte WE)“, „Einkommensbonus (34 % …)“). EFH: die Zeilen tragen nur Sätze
    („30 %“, „+16 %“, „+30 %“, „Fördersatz gesamt 70 % (gedeckelt)“) – die Beträge ergeben sich als
    förderfähige Kosten × angewandter Satz; bei gedeckeltem Satz wird wie in der v9-MFH-Anzeige der
    Klimabonus zuerst voll und der Einkommensbonus als Rest gezeigt [ANNAHME]. Rundungsdifferenzen landen im
    letzten Baustein, die Summe ist immer exakt ``zuschuss_cent``. Gewerbe: nur Grundförderung.
    v6-Alt-Override (Gesamtzuschuss manuell): keine Aufschlüsselung – ein Baustein „KfW-Zuschuss“ [ANNAHME]."""
    zuschuss = int(ergebnis.zuschuss_cent)
    if manuell_gesamt:
        return [{"key": "zuschuss", "prozent": None, "betrag_cent": zuschuss, "mfh_prozent": None}]
    zeilen = list(ergebnis.zeilen)
    bausteine: list[dict] = []
    if objekt == "mfh":
        for key, praefix in (("grund", "Grundförderung"), ("klima", "Klimageschwindigkeits-Bonus"),
                             ("einkommen", "Einkommensbonus")):
            for name, wert, _fett in zeilen:
                if not name.startswith(praefix):
                    continue
                betrag = _euro_cent(wert)
                m = re.search(r"\(([\d.,]+)\s*%", name)
                prozent = _zahl(m.group(1)) if m else None
                if betrag:
                    bausteine.append({"key": key, "prozent": prozent, "betrag_cent": betrag,
                                      "mfh_prozent": prozent if key != "grund" else None})
                break
    else:
        werte = {name: wert for name, wert, _fett in zeilen}
        grund_p = _zahl(werte.get("Grundförderung", "")) or 0.0
        klima_p = _zahl(werte.get("Klimageschwindigkeits-Bonus", "")) or 0.0
        eink_p = _zahl(werte.get("Einkommensbonus", "")) or 0.0
        satz = _zahl(werte.get("Fördersatz gesamt", ""))
        if satz is None:
            satz = grund_p + klima_p + eink_p
        grund_anz = min(grund_p, satz)
        klima_anz = min(klima_p, max(0.0, satz - grund_anz))
        eink_anz = min(eink_p, max(0.0, satz - grund_anz - klima_anz))
        foerderfaehig = int(ergebnis.foerderfaehig_cent)
        for key, prozent in (("grund", grund_anz), ("klima", klima_anz), ("einkommen", eink_anz)):
            if prozent > 0:
                bausteine.append({"key": key, "prozent": prozent,
                                  "betrag_cent": kfw._rund_cent(foerderfaehig * prozent / 100),
                                  "mfh_prozent": None})
    if not bausteine:
        return [{"key": "zuschuss", "prozent": None, "betrag_cent": zuschuss, "mfh_prozent": None}]
    differenz = zuschuss - sum(b["betrag_cent"] for b in bausteine)
    if differenz:
        bausteine[-1]["betrag_cent"] = max(0, bausteine[-1]["betrag_cent"] + differenz)
    return bausteine


# ----------------------------------------------------------------------------- Aufbereitung
def aufbereiten(ergebnis: "kfw.KfwErgebnis", *, endbetrag_cent: int, ust_prozent: float, datum,
                objekt: str = "efh", wohneinheiten: int = 0, pos_bza: str | None = None,
                pos_hydraulik: str | None = None, manuell: bool = False,
                manuell_gesamt: bool = False) -> dict:
    """KfW-Ergebnis → Kontext-Teilbaum (Struktur im Modul-Docstring). Reine Textaufbereitung."""
    datum_text = _datum_text(datum)
    zuschuss = int(ergebnis.zuschuss_cent)
    eigenanteil = int(ergebnis.eigenanteil_cent)
    programm = ergebnis.programm
    if programm.lower().startswith("antrag:"):
        programm = programm.split(":", 1)[1].strip()

    bausteine_cent = _bausteine(ergebnis, objekt, manuell_gesamt)
    anteile = []
    for b in bausteine_cent:
        anteile.append((b["betrag_cent"] / endbetrag_cent * 100) if endbetrag_cent > 0 else 0.0)
    eigen_anteil = (eigenanteil / endbetrag_cent * 100) if endbetrag_cent > 0 else 0.0
    prozente = _prozente_summe_100(anteile + [eigen_anteil])
    foerderquote = sum(prozente[:-1])
    eigenquote = prozente[-1]

    balken = []
    for b, anteil, prozent in zip(bausteine_cent, anteile, prozente[:-1]):
        balken.append({"key": b["key"], "klasse": b["key"], "name": _BALKEN_NAMEN[b["key"]],
                       "prozent": prozent, "breite_prozent": f"{anteil:.2f}", "betrag": _euro(b["betrag_cent"]),
                       "kompakt": anteil < _KOMPAKT_AB_PROZENT, "schmal": anteil < _SCHMAL_AB_PROZENT})
    balken.append({"key": "eigen", "klasse": "eigen", "name": "Ihr Eigenanteil", "prozent": eigenquote,
                   "breite_prozent": f"{eigen_anteil:.2f}", "betrag": _euro(eigenanteil),
                   "kompakt": eigen_anteil < _KOMPAKT_AB_PROZENT, "schmal": eigen_anteil < _SCHMAL_AB_PROZENT})

    bausteine = []
    for b in bausteine_cent:
        prozent_text = _prozent_text(b["prozent"]) + " %" if b["prozent"] is not None else ""
        mfh_zusatz = f"({prozent_text} anteilig WE)" if b["mfh_prozent"] is not None else ""
        bausteine.append({"key": b["key"], "klasse": b["key"], "name": _BAUSTEIN_NAMEN[b["key"]],
                          "prozent_text": prozent_text, "mfh_zusatz": mfh_zusatz,
                          "klammer": mfh_zusatz or (f"({prozent_text})" if prozent_text else ""),
                          "betrag": _euro(b["betrag_cent"])})

    hinweise = _hinweise_filtern(list(ergebnis.hinweise))
    deckel_satz = next((h for h in hinweise if "gedeckelt" in h or "begrenzt" in h), None)
    disclaimer = ergebnis.disclaimer or kfw.STANDARD_DISCLAIMER
    if datum_text:
        disclaimer = _MUSTER_KONDITIONEN.sub(f"Konditionen ab {datum_text}", disclaimer)
    satz_text = _ohne_manuell(ergebnis.satz_text)
    m = re.search(r"([\d.,]+)\s*%", satz_text)
    foerdersatz = f"{m.group(1)} %" if m else f"{foerderquote} %"
    ust = f"{ust_prozent:g}".replace(".", ",")
    return {
        "eyebrow": ergebnis.programm.upper(), "programm": programm, "titel": TITEL,
        "untertitel": f"{foerderquote} % zahlt die KfW – {eigenquote} % bleiben für Sie",
        "foerderquote": foerderquote, "eigenquote": eigenquote, "foerdersatz": foerdersatz,
        "satz_text": satz_text,
        "angebotssumme": _euro(endbetrag_cent), "angebotssumme_zusatz": f"(inkl. {ust} % USt.)",
        "foerderfaehig": _euro(ergebnis.foerderfaehig_cent), "hoechstkosten": _euro(ergebnis.hoechstkosten_cent),
        "balken": balken, "bausteine": bausteine,
        "zuschuss": _euro(zuschuss), "eigenanteil": _euro(eigenanteil),
        "deckel_satz": deckel_satz, "hinweise": hinweise, "disclaimer": disclaimer,
        "konditionen_ab": datum_text,
        "schritte": _schritte(pos_bza), "gut_zu_wissen": _gut_zu_wissen(pos_hydraulik),
        "antrag_unterlagen": list(ANTRAG_UNTERLAGEN),
        "pos_bza": pos_bza, "pos_hydraulik": pos_hydraulik,
        "manuell": bool(manuell), "mfh": objekt == "mfh", "wohneinheiten": int(wohneinheiten or 0),
        "objekt": objekt, "bild": BILD,
    }


def kontext(session, angebot) -> dict | None:
    """Teilbaum ``kfw`` für ein Angebot (liest nur; None ohne Förderblock)."""
    from app import pdf_export
    if not pdf_export.foerderblock_moeglich(angebot) or getattr(angebot, "foerderung_ausblenden", False):
        return None
    ergebnis = pdf_export._kfw_ergebnis_fuer(session, angebot)
    if ergebnis is None:
        return None
    summen = angebot.summen()
    kfw_daten = json.loads(angebot.kfw_json or "{}")
    eingaben = kfw.eingaben_aus_antworten(kfw_daten, summen["endbetrag"])
    objekt = eingaben.objekt if eingaben is not None else "efh"
    wohneinheiten = eingaben.wohneinheiten if eingaben is not None else 0
    nummern = positionsnummern(angebot)
    manuell_gesamt = getattr(angebot, "foerderung_manuell_cent", None) is not None
    manuell = manuell_gesamt or kfw.bausteine_aus_angebot(angebot).aktiv
    return aufbereiten(ergebnis, endbetrag_cent=summen["endbetrag"], ust_prozent=float(angebot.ust_prozent),
                       datum=getattr(angebot, "datum", None), objekt=objekt, wohneinheiten=wohneinheiten,
                       pos_bza=nummern["bza"], pos_hydraulik=nummern["hydraulik"], manuell=manuell,
                       manuell_gesamt=manuell_gesamt)


# ----------------------------------------------------------------------------- Demo (ohne Datenbank)
DEMO_ENDBETRAG_CENT = 4283055      # 42.830,55 € (pdf_kontext.demo_kontext)
DEMO_ZUSCHUSS_CENT = 1650000       # 16.500,00 € = 55 % von 30.000,00 € förderfähigen Kosten


def demo() -> dict:
    """Demo-Teilbaum mit den Zahlen aus pdf_kontext.demo_kontext (Endbetrag 42.830,55 €, Förderung
    16.500,00 €): EFH, Grundförderung 30 % + Klimageschwindigkeits-Bonus 16 % + Einkommensbonus 9 % von
    30.000,00 € förderfähigen Kosten (Standardparameter des Blatts „KfW“, Höchstkosten für die Demo auf
    30.000 € gesetzt) – keine Kundendaten, keine Datenbank."""
    parameter = kfw.KfwParameter()
    parameter.einkommens_stufen = [(40, 30000), (30, 40000), (10, 50000)]
    eingaben = kfw.KfwEingaben("efh", DEMO_ENDBETRAG_CENT, klima_bonus=True, einkommen_eur=45000, kind=True)
    bausteine = kfw.FoerderBausteine(einkommen_prozent=9, hoechstkosten_cent=3000000)
    ergebnis = kfw.berechnen(parameter, eingaben, bausteine)
    assert ergebnis.zuschuss_cent == DEMO_ZUSCHUSS_CENT, ergebnis.zuschuss_cent
    return aufbereiten(ergebnis, endbetrag_cent=DEMO_ENDBETRAG_CENT, ust_prozent=19.0,
                       datum=date(2026, 10, 16), objekt="efh", wohneinheiten=1,
                       pos_bza="018", pos_hydraulik="007", manuell=False)
