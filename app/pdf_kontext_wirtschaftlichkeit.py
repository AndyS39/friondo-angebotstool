"""v36 (PLAN_V22 Phase 189, Agent A2): Kontext-Teilbaum ``wirtschaftlichkeit`` des Angebots-PDFs – die drei
Wirtschaftlichkeitsseiten PV (v22: „Auf einen Blick“ · „Ersparnis im Detail“ · „Sicherheit & Transparenz“)
nach den Mockups docs/wirtschaftlichkeit-mockup/seite1–3.html. Inhalte, Varianten und Zahlenformate sind
identisch mit der fpdf2-Umsetzung app/wirtschaftlichkeit_pdf.py (bleibt für den Rückfall); der Rechenkern
app/wirtschaftlichkeit.py und ``pdf_export.wirtschaftlichkeit_fuer`` bleiben unverändert – hier werden die
Ergebnisse nur in Texte, Listen und Balkenmaße (mm, als Text für CSS) aufbereitet.

Varianten wie in v22: ohne Speicher/HEMS/SpotDynamic entfallen die Stufen der Treppe (SpotDynamic-Hinweis nur,
wenn der Netzbezug > 0 ist), ohne Wärmepumpe steht rechts die Karte „Ihr Verbrauch“ statt „Heizen mit
Sonnenstrom“, ohne Break-even der neutrale Satz.

Schlüssel von ``kontext(session, angebot)`` bzw. ``demo()`` (None, wenn kein PV, ``wirtschaftlichkeit_ausblenden``
oder keine Auslegungsdaten):

  kopf      {nummer, ort, datum, kunde, adresse}
  n         Betrachtungszeitraum in Jahren
  seiten    [seite1, seite2, seite3] (dieselben Dicts wie unten, für Schleifen)
  seite1    {nr, eyebrow, meta „zu Angebot … · Duisburg, TT.MM.JJJJ“ (ohne innere Seitenzählung – die
             Dokument-Seitenzahl der Browser-Kopfzeile ist die einzige Zählung, Entscheidung Orchestrator
             16.10.2026), titel, subline,
             hero {eyebrow, betrag, text, kacheln [{wert, label}]},
             amortisation {titel, meta, start_text, pos_mm, neg_mm,
                           balken [{jahr, label, pos_mm, neg_mm, negativ, letzter, kum_text, end_mm}],
                           chip {text, links_mm, oben_mm} | None, satz [{text, fett}]},
             strom {titel, meta, zeilen [{titel, unter, segmente [{prozent, breite, klasse, label_sichtbar}]}],
                    legende [{klasse, text}], satz [{text, fett}]}}
  seite2    {nr, eyebrow, meta, titel, subline,
             kosten {titel, meta, legende [{klasse, text}], hoehe_mm, balken [{label, ohne_mm, mit_mm}],
                     kacheln [{wert, label, klasse}]},
             vorteil {titel, meta, zeilen [{name, rechnung, betrag}], summe {name, rechnung, betrag}},
             rechts {art „heizen“|„verbrauch“, titel, intro [{text, fett}], balken [{text, breite, klasse}],
                     kacheln [{wert, label, klasse}], satz},
             treppe {titel, meta, spalten, hoehe_mm, bereich_mm (Säulenbereich inkl. Delta-Zeile),
                     stufen [{name, betrag, hoehe_mm, delta, detail, klasse}], hinweis {text, betrag, name, sub} | None}}
  seite3    {nr, eyebrow, meta, titel, subline,
             szenarien {titel, meta, hoehe_mm, bereich_mm, saeulen [{summe, hoehe_mm, amort, label, note, klasse}],
                        text},
             klima {titel, meta, kacheln [{icon, wert, label}]},
             annahmen {titel, meta, links [{name, wert}], rechts [{name, wert}], hinweis, weiter_eyebrow,
                       schritte [str]}}

Balkenklassen (Farben nur in app/static/pdf/angebot_wirtschaftlichkeit.css): sonne · blau · grau · hell ·
blau-dunkel · dunkel.
"""
from __future__ import annotations

from datetime import date

from app import wirtschaftlichkeit

EYEBROWS = ("WIRTSCHAFTLICHKEITSBETRACHTUNG", "IHRE ERSPARNIS IM DETAIL", "SICHERHEIT & TRANSPARENZ")
TITEL = ("So rechnet sich Ihre Energielösung", "Was Sie Jahr für Jahr sparen", "So sicher ist Ihre Rechnung")
SUBLINE_2 = ("Ihre Stromkosten über {n} Jahre – ohne Anlage und mit Ihrer Friondo-Energielösung. Dazu: wie "
             "sich Ihr Vorteil im ersten Jahr zusammensetzt und was jeder Baustein des Systems beiträgt.")
SUBLINE_3 = ("Was passiert, wenn der Strompreis kaum steigt? Was bringt Ihre Anlage dem Klima? Und auf welchen "
             "Annahmen beruht das alles? Wir legen es offen.")
MODELL_HINWEIS = ("Modellrechnung auf Basis Ihrer Angaben und üblicher Erfahrungswerte. Erträge und Einsparungen "
                  "hängen von Ausrichtung, Verschattung, Wetter, Verbrauch und Strompreisen ab und können "
                  "abweichen. Keine Garantie, kein Vertragsbestandteil.")
AUSSTELLUNGSORT = "Duisburg"

# Diagramm-Maße in mm (wie wirtschaftlichkeit_pdf.py, damit die drei Seiten je eine A4-Seite füllen)
KUM_POS_MM = 24.0          # Positivbereich der kumulierten Ersparnis
KUM_NEG_MM = 11.0          # Negativbereich
KOSTEN_MM = 28.0           # Stromkosten je Jahr
TREPPE_MM = 15.0           # Baustein-Treppe
SZENARIEN_MM = 22.0        # Strompreis-Szenarien
CHART_BREITE_MM = 168.0    # Innenbreite der Karten (178 mm Inhalt − 2 × 5 mm) – nur für die Chip-Platzierung
CHIP_BREITE_MM = 30.0
CHIP_HOEHE_MM = 6.5
LABEL_AB_PROZENT = 8.0     # Prozentwert im Segment nur ab dieser Breite (fpdf2: ab 9 mm)


# ----------------------------------------------------------------------------- Zahlenformate (= wirtschaftlichkeit_pdf)
def _zahl(wert: float, stellen: int = 0) -> str:
    """Tausenderpunkt, Komma; negative Beträge mit „−“ (U+2212)."""
    text = f"{abs(wert):,.{stellen}f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return ("−" if round(wert, stellen) < 0 else "") + text


def _eur(wert: float, stellen: int = 0) -> str:
    return f"{_zahl(wert, stellen)} €"


def _eur100(wert: float) -> str:
    return _eur(round(wert / 100) * 100)


def _prozent(anteil: float | None) -> str:
    return "–" if anteil is None else f"{_zahl(anteil * 100)} %"


def _ct(preis_eur: float) -> str:
    """0,33 €/kWh → „33 ct“, 0,078 → „7,8 ct“."""
    ct = preis_eur * 100
    return f"{_zahl(ct, 0 if abs(ct - round(ct)) < 0.05 else 1)} ct"


def _prozentzahl(anteil: float) -> str:
    """0,004 → „0,4“, 0,03 → „3“."""
    p = anteil * 100
    return _zahl(p, 0 if abs(p - round(p)) < 0.005 else 1)


def _kwh(wert: float) -> str:
    return f"{_zahl(wert)} kWh"


def _mm(wert: float) -> str:
    """Länge in mm als CSS-Text (Punkt als Dezimaltrenner)."""
    return f"{max(0.0, float(wert)):.2f}"


def _anzahl_wort(n: int) -> str:
    return {1: "Ein", 2: "Zwei", 3: "Drei", 4: "Vier", 5: "Fünf"}.get(n, str(n))


def _jahres_labels(n: int) -> set[int]:
    labels = {j for j in range(1, n + 1) if (j - 1) % 3 == 0}
    labels = {j for j in labels if j == n or n - j >= 2}
    labels.add(n)
    return labels


def _text(text: str, fett: bool = False) -> dict:
    return {"text": text, "fett": fett}


# ----------------------------------------------------------------------------- Bausteine der Seiten
def _bausteine_text(a: dict) -> str:
    teile = [f"PV-Anlage {_zahl(a['kwp'], 2)} kWp mit {a['module']} Modulen"]
    if a["speicher_kwh"] > 0:
        teile.append(f"Sigenergy Speicher {_zahl(a['speicher_kwh'])} kWh")
    if a["hems"]:
        teile.append("Friondo HEMS")
    if a["spot"]:
        teile.append("Friondo SpotDynamic")
    return " · ".join(teile)


def _verbrauchsbasis(a: dict) -> str:
    teile = []
    if a["hh_kwh"]:
        teile.append(f"{_kwh(a['hh_kwh'])} Haushaltsstrom")
    if a["wp_kwh"]:
        teile.append(f"{_kwh(a['wp_kwh'])} Wärmepumpenstrom")
    if a["wb_kwh"]:
        teile.append(f"{_kwh(a['wb_kwh'])} Wallbox-Strom")
    if not teile:
        return ""
    if len(teile) == 1:
        return teile[0]
    return ", ".join(teile[:-1]) + " und " + teile[-1]


def _segmente(teile: list[tuple[float, str]]) -> list[dict]:
    """Gestapelter Balken: Anteile (0…1) → Prozentwerte, die sich zu 100 ergänzen; Breite in % der Zeile."""
    teile = [(max(0.0, anteil), klasse) for anteil, klasse in teile]
    summe = sum(anteil for anteil, _ in teile) or 1.0
    anteile = [anteil / summe for anteil, _ in teile]
    prozente = [int(round(x * 100)) for x in anteile]
    diff = 100 - sum(prozente)
    if prozente:
        groesster = max(range(len(prozente)), key=lambda i: prozente[i])
        prozente[groesster] += diff
    segmente = []
    for (anteil, klasse), prozent in zip(zip(anteile, [k for _, k in teile]), prozente):
        if anteil <= 0:
            continue
        segmente.append({"prozent": prozent, "breite": f"{anteil * 100:.2f}", "klasse": klasse,
                         "label_sichtbar": anteil * 100 >= LABEL_AB_PROZENT})
    return segmente


def _meta(kopf: dict) -> str:
    """Meta-Zeile unter dem Eyebrow – ohne „Seite x von 3“ (Entscheidung Orchestrator 16.10.2026: die
    Dokument-Seitenzahl „SEITE x VON y“ der Browser-Kopfzeile ist die einzige Seitenzählung im Layout v3)."""
    return f"zu Angebot {kopf.get('nummer', '')} · {kopf.get('ort', '')}, {kopf.get('datum', '')}"


KUNDE_MAX_ZEICHEN = 90     # Subline Seite 1: Kunde + Adresse werden wie in der fpdf2-Fassung mit „…“ gekürzt,
                           # damit die Subline drei Zeilen nicht überschreitet [ANNAHME]


def _kuerzen(text: str, maximum: int) -> str:
    """Auf `maximum` Zeichen kürzen (an der letzten Wortgrenze) und mit „…“ abschließen."""
    if len(text) <= maximum:
        return text
    kurz = text[:maximum - 1]
    if " " in kurz[maximum // 2:]:
        kurz = kurz.rsplit(" ", 1)[0]
    return kurz.rstrip(" ,.-") + "…"


def _seite1(e: dict, kopf: dict) -> dict:
    a = e["anlage"]
    p = e["param"]
    fuer = _kuerzen(", ".join(t for t in (kopf.get("kunde", ""), kopf.get("adresse", "")) if t), KUNDE_MAX_ZEICHEN)
    subline = _bausteine_text(a) + (f" — für {fuer}." if fuer else ".")
    basis = _verbrauchsbasis(a)
    if basis:
        subline += f" Grundlage: {basis} pro Jahr."
    faktor = e["faktor"]
    if faktor is not None:
        hero_text = (f"Das {_zahl(faktor, 1)}-Fache Ihrer Investition von {_eur(a['investition_eur'])} – "
                     f"vermiedene Stromkosten plus Einspeisevergütung, bei nur {_prozentzahl(p['steigerung'])} % "
                     "Strompreissteigerung pro Jahr.")
    else:
        hero_text = ("Vermiedene Stromkosten plus Einspeisevergütung, bei nur "
                     f"{_prozentzahl(p['steigerung'])} % Strompreissteigerung pro Jahr.")
    be = e["break_even"]
    kacheln = [
        {"wert": f"{be} Jahre" if be else "über " + str(e["n"]) + " J.",
         "label": "bis sich die Anlage bezahlt gemacht hat" if be
         else "Amortisation liegt außerhalb der Betrachtung"},
        {"wert": _prozent(e["j1"]["autarkie"]), "label": "Ihres Stroms kommen vom eigenen Dach"},
        {"wert": f"{_zahl(e['monat'])} €/Monat", "label": "Ersparnis – schon im ersten Jahr"},
    ]

    # Karte „Wann sich Ihre Anlage bezahlt macht“
    jahre = e["jahre"]
    n = len(jahre)
    pos_max = max((z["kum"] for z in jahre if z["kum"] > 0), default=0.0)
    neg_max = max((-z["kum"] for z in jahre if z["kum"] < 0), default=0.0)
    skala = min(KUM_POS_MM / pos_max if pos_max else float("inf"),
                KUM_NEG_MM / neg_max if neg_max else float("inf"))
    if skala == float("inf"):
        skala = 0.0
    labels = _jahres_labels(n)
    balken = []
    for z in jahre:
        j = z["jahr"]
        h = abs(z["kum"]) * skala
        negativ = z["kum"] < 0
        balken.append({"jahr": j, "label": str(z.get("kalenderjahr") or j) if j in labels else "",
                       "pos_mm": _mm(0 if negativ else h), "neg_mm": _mm(h if negativ else 0),
                       "negativ": negativ, "letzter": j == n,
                       "kum_text": (("+" if z["kum"] >= 0 else "") + _eur(z["kum"])) if j == n else "",
                       "end_mm": _mm((0 if negativ else h) + 1.2)})
    chip = None
    be_jahr = e["break_even_jahr"]
    if be and be_jahr and n:
        slot = CHART_BREITE_MM / n
        cx = (be - 1) * slot + slot / 2
        x0 = min(max(cx - CHIP_BREITE_MM / 2, 0.0), CHART_BREITE_MM - 1.3 * slot - CHIP_BREITE_MM)
        x0 = max(x0, 0.0)
        j_von = max(1, int(x0 / slot) + 1)
        j_bis = min(n, int((x0 + CHIP_BREITE_MM) / slot) + 1)
        hoechster = max((jahre[j - 1]["kum"] * skala for j in range(j_von, j_bis + 1)
                         if jahre[j - 1]["kum"] > 0), default=0.0)
        oben = min(KUM_POS_MM - 9.5, KUM_POS_MM - hoechster - CHIP_HOEHE_MM - 1.5)
        chip = {"text": f"Break-even {be_jahr}", "links_mm": _mm(x0), "oben_mm": _mm(max(oben, 0.0))}
    if be and be_jahr:
        satz = [_text(f"Ab {be_jahr} arbeitet die Anlage nur noch für Sie: "),
                _text(f"rund {_eur100(e['gewinn_ende'])} Gewinn bis {e['endjahr']}", True), _text(".")]
    else:
        satz = [_text(f"Innerhalb von {e['n']} Jahren erreicht die Anlage {_eur(e['gewinn_ende'])} – die "
                      "Amortisation liegt jenseits des Betrachtungszeitraums.")]
    amortisation = {"titel": "Wann sich Ihre Anlage bezahlt macht",
                    "meta": "Kumulierte Ersparnis abzüglich Investition, in €",
                    "start_text": f"Start {e['startjahr'] or ''}: Investition {_eur(a['investition_eur'])}",
                    "pos_mm": _mm(KUM_POS_MM), "neg_mm": _mm(KUM_NEG_MM), "balken": balken, "chip": chip,
                    "satz": satz}

    # Karte „Woher Ihr Strom kommt“
    j1 = e["j1"]
    prod = j1["prod"] or 1.0
    last = j1["last"] or 1.0
    teile = [t for t, kwh in (("Haushalt", a["hh_kwh"]), ("Wärmepumpe", a["wp_kwh"]),
                              ("Wallbox", a["wb_kwh"])) if kwh]
    strom = {
        "titel": "Woher Ihr Strom kommt – und wohin Ihr Solarstrom geht", "meta": "Jahr 1, in kWh",
        "zeilen": [
            {"titel": f"Solarstrom {_kwh(j1['prod'])}", "unter": f"aus {_zahl(a['kwp'], 2)} kWp",
             "segmente": _segmente([(j1["direkt"] / prod, "sonne"), (j1["sp_in"] / prod, "blau"),
                                    (j1["einsp"] / prod, "grau")])},
            {"titel": f"Verbrauch {_kwh(j1['last'])}", "unter": " + ".join(teile) or "Verbrauch",
             "segmente": _segmente([(j1["direkt"] / last, "sonne"), (j1["sp_out"] / last, "blau"),
                                    (j1["netz"] / last, "grau")])},
        ],
        "legende": [{"klasse": "sonne", "text": "Direkt von der Sonne"},
                    {"klasse": "blau", "text": "Über den Speicher"},
                    {"klasse": "grau", "text": "Ins Netz bzw. aus dem Netz"}],
        "satz": [_text("Sie nutzen "), _text(f"{_prozent(j1['ev_quote'])} Ihres Solarstroms selbst", True),
                 _text(" (Eigenverbrauch) und decken "),
                 _text(f"{_prozent(j1['autarkie'])} Ihres Bedarfs vom eigenen Dach", True), _text(" (Autarkie).")],
    }
    return {"nr": 1, "eyebrow": EYEBROWS[0], "meta": _meta(kopf), "titel": TITEL[0], "subline": subline,
            "hero": {"eyebrow": f"IHRE ERSPARNIS IN {e['n']} JAHREN", "betrag": _eur100(e["summe_ersparnis"]),
                     "text": hero_text, "kacheln": kacheln},
            "amortisation": amortisation, "strom": strom}


def _seite2(e: dict, kopf: dict) -> dict:
    a = e["anlage"]
    p = e["param"]
    # Karte „Ihre Stromkosten pro Jahr“
    jahre = e["jahre"]
    maximum = max(max(z["ohne"], z["mit"], 0.0) for z in jahre) or 1.0
    skala = KOSTEN_MM / maximum
    labels = _jahres_labels(len(jahre))
    kosten_balken = [{"label": str(z.get("kalenderjahr") or z["jahr"]) if z["jahr"] in labels else "",
                      "ohne_mm": _mm(max(0.0, z["ohne"]) * skala), "mit_mm": _mm(max(0.0, z["mit"]) * skala)}
                     for z in jahre]
    mit_text = ("Mit Friondo (Netzbezug zu SpotDynamic-Preisen abzüglich Einspeisung)" if a["spot"]
                else "Mit Friondo (Netzbezug abzüglich Einspeisung)")
    kosten = {"titel": "Ihre Stromkosten pro Jahr",
              "meta": f"ohne Anlage vs. mit Friondo, in €, Strompreis +{_prozentzahl(p['steigerung'])} % p. a.",
              "legende": [{"klasse": "dunkel", "text": "Ohne Anlage"}, {"klasse": "blau", "text": mit_text}],
              "hoehe_mm": _mm(KOSTEN_MM), "balken": kosten_balken,
              "kacheln": [{"wert": _eur100(e["summe_ohne"]), "label": f"ohne Anlage in {e['n']} Jahren", "klasse": "karte"},
                          {"wert": _eur100(e["summe_mit"]), "label": f"mit Friondo in {e['n']} Jahren", "klasse": "tint"},
                          {"wert": _eur100(e["summe_ersparnis"]), "label": f"Ihr Vorteil in {e['n']} Jahren",
                           "klasse": "dunkel"}]}

    # Karte links „Ihr Vorteil im ersten Jahr“
    v = e["vorteil"]
    ct = _ct(v["preis"])
    zeilen = [
        {"name": "Stromkosten heute", "rechnung": f"{_zahl(v['last'])} × {ct}", "betrag": _eur(v["stromkosten_heute"])},
        {"name": "Netzbezug neu", "rechnung": f"{_zahl(v['netz'])} × {ct}", "betrag": "− " + _eur(v["netzbezug"])},
        {"name": "Einspeisung", "rechnung": f"{_zahl(v['einsp'])} × {_ct(p['verguetung'])}",
         "betrag": "+ " + _eur(v["einspeisung"])},
    ]
    if a["spot"]:
        zeilen.append({"name": "SpotDynamic", "rechnung": f"{_zahl(v['netz'])} × −{_ct(v['spot_differenz'])}",
                       "betrag": "+ " + _eur(v["spot_vorteil"])})
    zeilen.append({"name": "Betriebskosten", "rechnung": "pauschal", "betrag": "− " + _eur(v["betriebskosten"])})
    vorteil = {"titel": "Ihr Vorteil im ersten Jahr", "meta": "kWh × Preis = Betrag", "zeilen": zeilen,
               "summe": {"name": "Ihr Vorteil Jahr 1", "rechnung": f"{_zahl(e['monat'])} €/Monat",
                         "betrag": _eur(v["summe"])}}

    # Karte rechts: „Heizen mit Sonnenstrom“ oder „Ihr Verbrauch“
    h = e["heizen"]
    if h:
        anteil = h["anteil_pv"]
        if a["hems"]:
            satz = ("Friondo HEMS lässt die Wärmepumpe bevorzugt bei Sonne laufen: Solaranteil am Heizstrom "
                    f"{_prozent(h['anteil_mit_hems'])} statt {_prozent(h['anteil_ohne_hems'])}.")
        else:
            satz = f"Mit Friondo HEMS stiege der Solaranteil auf {_prozent(h['anteil_mit_hems'])}."
        rechts = {"art": "heizen", "titel": "Heizen mit Sonnenstrom",
                  "intro": [_text("Wärmepumpe: "), _text(f"{_kwh(h['wp_kwh'])} Strom/Jahr", True)],
                  "balken": [{"text": f"{_prozent(anteil)} vom Dach", "breite": f"{anteil * 100:.2f}", "klasse": "sonne"},
                             {"text": f"{_prozent(1 - anteil)} Netz", "breite": f"{(1 - anteil) * 100:.2f}", "klasse": "grau"}],
                  "kacheln": [{"wert": _eur(h["kosten_ohne_pv"]), "label": "Heizstrom pro Jahr ohne PV", "klasse": "karte"},
                              {"wert": _eur(h["kosten_mit_pv"]), "label": "Heizstrom pro Jahr mit PV", "klasse": "tint"}],
                  "satz": satz}
    else:
        last = e["j1"]["last"] or 1.0
        hh, wb = a["hh_kwh"], a["wb_kwh"]
        balken = [{"text": f"{_prozent(hh / last)} Haushalt", "breite": f"{hh / last * 100:.2f}", "klasse": "sonne"}]
        if wb:
            balken.append({"text": f"{_prozent(wb / last)} Wallbox", "breite": f"{wb / last * 100:.2f}", "klasse": "grau"})
        rechts = {"art": "verbrauch", "titel": "Ihr Verbrauch",
                  "intro": [_text("Gesamt: "), _text(f"{_kwh(e['j1']['last'])} Strom pro Jahr", True)],
                  "balken": balken,
                  "kacheln": [{"wert": _kwh(hh), "label": "Haushalt pro Jahr", "klasse": "karte"},
                              {"wert": _kwh(wb) if wb else _kwh(e["j1"]["netz"]),
                               "label": "Wallbox pro Jahr" if wb else "Netzbezug mit PV", "klasse": "tint"}],
                  "satz": "Ohne Wärmepumpe im Verbrauch – die Rechnung berücksichtigt Haushalt"
                          + (" und Wallbox." if wb else ".")}

    # Karte „Was jeder Baustein bringt“
    stufen = e["treppe"]
    klassen = ["hell", "blau", "blau-dunkel", "dunkel"]
    hinweis = e.get("spot_hinweis")
    if hinweis and hinweis["delta_1"] < 1:
        hinweis = None            # ohne Netzbezug bringt SpotDynamic nichts
    maximum = max((s["ersparnis_1"] for s in stufen), default=0.0) or 1.0
    treppe_stufen = []
    for i, s in enumerate(stufen):
        be = s["break_even"]
        treppe_stufen.append({
            "name": s["name"], "betrag": _eur(s["ersparnis_1"]),
            "hoehe_mm": _mm(max(6.0, max(0.0, s["ersparnis_1"]) / maximum * TREPPE_MM)),
            "delta": "Basis" if i == 0 else (("+ " + _eur(s["delta"])) if s["delta"] is not None else ""),
            "detail": (f"{e['n']} Jahre: {_eur100(s['summe'])} · "
                       + (f"amortisiert nach {be} J." if be else "keine Amortisation")),
            "klasse": klassen[min(i, len(klassen) - 1)]})
    treppe = {"titel": "Was jeder Baustein bringt", "meta": "Ersparnis im ersten Jahr, in €",
              "spalten": len(treppe_stufen) + (1 if hinweis else 0), "hoehe_mm": _mm(TREPPE_MM),
              "bereich_mm": _mm(TREPPE_MM + 5.0), "stufen": treppe_stufen,
              "hinweis": ({"text": "Mit Friondo SpotDynamic zusätzlich rund",
                           "betrag": f"+ {_eur(hinweis['delta_1'])}/Jahr", "name": "+ SpotDynamic",
                           "sub": "sprechen Sie uns an"} if hinweis else None)}
    return {"nr": 2, "eyebrow": EYEBROWS[1], "meta": _meta(kopf), "titel": TITEL[1],
            "subline": SUBLINE_2.format(n=e["n"]), "kosten": kosten, "vorteil": vorteil, "rechts": rechts,
            "treppe": treppe}


def _seite3(e: dict, kopf: dict) -> dict:
    a = e["anlage"]
    p = e["param"]
    sz = e["szenarien"]
    klassen = ["hell", "blau", "dunkel"]
    n = len(sz)
    maximum = max((s["summe"] for s in sz), default=0.0) or 1.0
    eigene = p["steigerung"]
    niedrig = min((s["steigerung"] for s in sz), default=eigene)
    hoch = max((s["steigerung"] for s in sz), default=eigene)
    saeulen = []
    for i, s in enumerate(sz):
        if abs(s["steigerung"] - eigene) < 1e-9:
            note = "Ihre Rechnung"
        elif s["steigerung"] == niedrig:
            note = "vorsichtig gerechnet"
        elif s["steigerung"] == hoch:
            note = "bei stark steigenden Preisen"
        else:
            note = ""
        be = s["break_even"]
        saeulen.append({"summe": _eur100(s["summe"]),
                        "hoehe_mm": _mm(max(8.0, max(0.0, s["summe"]) / maximum * SZENARIEN_MM)),
                        "amort": f"Amortisation {be} Jahre" if be else "keine Amortisation",
                        "label": f"Strompreis +{_prozentzahl(s['steigerung'])} % pro Jahr", "note": note,
                        "klasse": klassen[min(i, 2)] if n <= 3 else klassen[i % 3]})
    min_sz = min(sz, key=lambda s: s["steigerung"]) if sz else None
    text = ""
    if min_sz is not None:
        if min_sz["break_even"]:
            text = (f"Selbst bei nur {_prozentzahl(min_sz['steigerung'])} % Preissteigerung pro Jahr bleibt es "
                    f"bei rund {min_sz['break_even']} Jahren bis zur Amortisation.")
        else:
            text = (f"Bei nur {_prozentzahl(min_sz['steigerung'])} % Preissteigerung pro Jahr liegt die "
                    f"Amortisation außerhalb von {e['n']} Jahren.")
    if a["spot"]:
        text += (f" SpotDynamic ist mit Ø {_ct(p['spot_preis'])}/kWh angesetzt, der Kosten-Airbag deckelt "
                 f"bei {_ct(p['airbag'])}.")
    szenarien = {"titel": f"{_anzahl_wort(n)} Strompreis-Szenarien", "meta": f"Ersparnis in {e['n']} Jahren, in €",
                 "hoehe_mm": _mm(SZENARIEN_MM), "bereich_mm": _mm(SZENARIEN_MM + 6.0), "saeulen": saeulen,
                 "text": text.strip()}

    co2 = e["co2"]
    klima = {"titel": "Ihr Beitrag zum Klima",
             "meta": f"Netzstrom mit {_zahl(p['co2_faktor'])} g CO₂/kWh (Umweltbundesamt)",
             "kacheln": [{"icon": "wolke", "wert": f"{_zahl(co2['t_jahr'], 1)} t CO₂", "label": "pro Jahr vermieden"},
                         {"icon": "blatt", "wert": f"{_zahl(co2['t_gesamt'])} t CO₂", "label": f"in {e['n']} Jahren"},
                         {"icon": "auto", "wert": f"{_zahl(round((co2['km'] or 0) / 100) * 100)} km",
                          "label": "Autofahrt pro Jahr"},
                         {"icon": "baum", "wert": f"{_zahl(co2['baeume'] or 0)} Bäume", "label": "gleiche Wirkung"}]}

    verbrauch = " + ".join(t for t in (
        f"{_zahl(a['hh_kwh'])} kWh Haushalt" if a["hh_kwh"] else "",
        f"{_zahl(a['wp_kwh'])} WP" if a["wp_kwh"] else "",
        f"{_zahl(a['wb_kwh'])} Wallbox" if a["wb_kwh"] else "") if t) or "–"
    links = [
        {"name": "Ertrag", "wert": f"{_zahl(p['ertrag'])} kWh/kWp · Monatsprofil · −{_prozentzahl(p['degradation'])} %/Jahr"},
        {"name": "Strompreis", "wert": f"{_ct(p['strompreis'])}/kWh · +{_prozentzahl(p['steigerung'])} %/Jahr"},
        {"name": "Einspeisung", "wert": f"{_ct(p['verguetung'])}/kWh · {e['n']} Jahre fest"},
        {"name": "Speicher", "wert": (f"{_zahl(p['wirkungsgrad'] * 100)} % Wirkungsgrad · {_zahl(p['zyklen'])} Zyklen")
         if a["speicher_kwh"] > 0 else "nicht enthalten"},
    ]
    rechts = [
        {"name": "Verbrauch", "wert": verbrauch + " · saisonal"},
        {"name": "Friondo HEMS", "wert": "PV-optimierte WP und Speicher" if a["hems"] else "nicht enthalten"},
        {"name": "SpotDynamic", "wert": (f"Ø {_ct(p['spot_preis'])}/kWh statt {_ct(p['strompreis'])} · "
                                         f"Airbag {_ct(p['airbag'])}") if a["spot"] else "nicht enthalten"},
        {"name": "Betrieb", "wert": f"{_eur(p['betriebskosten'])}/Jahr · {e['n']} Jahre ab {e['startjahr'] or ''}"},
    ]
    annahmen = {"titel": "Unsere Annahmen – transparent", "meta": "Modellannahmen, keine Zusage",
                "links": links, "rechts": rechts, "hinweis": MODELL_HINWEIS, "weiter_eyebrow": "SO GEHT ES WEITER",
                "schritte": ["Angebot annehmen", "Feinplanung vor Ort",
                             p.get("montage_text") or "Montage in 1–2 Tagen", "Inbetriebnahme & Einweisung"]}
    return {"nr": 3, "eyebrow": EYEBROWS[2], "meta": _meta(kopf), "titel": TITEL[2], "subline": SUBLINE_3,
            "szenarien": szenarien, "klima": klima, "annahmen": annahmen}


# ----------------------------------------------------------------------------- Einstieg
def aufbereiten(daten: dict, kopf: dict) -> dict:
    """Daten aus pdf_export.wirtschaftlichkeit_fuer ({anlage, param, ergebnis, …}) + Kopf → Teilbaum."""
    e = daten["ergebnis"]
    seiten = [_seite1(e, kopf), _seite2(e, kopf), _seite3(e, kopf)]
    return {"kopf": dict(kopf), "n": e["n"], "seiten": seiten,
            "seite1": seiten[0], "seite2": seiten[1], "seite3": seiten[2]}


def _kundenname(kunde) -> str:
    """Wie pdf_export.erzeuge_pdf (Kopf der v22-Seiten): Firma, sonst „Familie/Eheleute Vorname Nachname“."""
    if kunde is None:
        return ""
    if getattr(kunde, "firma", "") or "":
        return kunde.firma
    anrede = kunde.anrede if (kunde.anrede or "") in ("Familie", "Eheleute") else ""
    return " ".join(t for t in (anrede, kunde.vorname, kunde.nachname) if t)


def kontext(session, angebot) -> dict | None:
    """Teilbaum ``wirtschaftlichkeit`` für ein PV-Angebot (liest nur; None ohne Auslegung/ausgeblendet)."""
    if (getattr(angebot, "konfigurator_typ", "") or "WP").upper() != "PV":
        return None
    if getattr(angebot, "wirtschaftlichkeit_ausblenden", False):
        return None
    from app import anschriften, pdf_export
    from app.models import Kunde
    daten = pdf_export.wirtschaftlichkeit_fuer(session, angebot)
    if daten is None:
        return None
    kunde = session.get(Kunde, angebot.kunde_id) if getattr(angebot, "kunde_id", None) else None
    ort = anschriften.ausfuehrungsort_fuer(session, angebot=angebot, kunde=kunde)
    datum = getattr(angebot, "datum", None)
    kopf = {"nummer": angebot.nummer, "ort": pdf_export.AUSSTELLUNGSORT,
            "datum": datum.strftime("%d.%m.%Y") if datum else "", "kunde": _kundenname(kunde),
            "adresse": anschriften.adresszeile(ort)}
    return aufbereiten(daten, kopf)


# ----------------------------------------------------------------------------- Demo (ohne Datenbank)
# Kontrollwerte PLAN_V15 Phase 100 (tests/test_wirtschaftlichkeit_v22.py): Vollausbau 10,92 kWp, Speicher 10 kWh,
# HEMS, SpotDynamic, 4.500 + 4.500 kWh, Investition 24.900 €, Start 2027 → Ersparnis 66.256 €, Break-even 9 Jahre
DEMO_PARAM = dict(ertrag=950, strompreis=0.33, verguetung=0.078, steigerung=0.03, degradation=0.004,
                  betriebskosten=100, jahre=20, zyklen=250, wirkungsgrad=0.90, direkt_hh=0.35, direkt_wp=0.20,
                  direkt_wb=0.30, hems_hh=0.05, hems_wp=0.15, hems_wb=0.20, spot_preis=0.18,
                  szenarien=[0.01, 0.03, 0.05], co2_faktor=380, co2_auto=120, co2_baum=12.5)
DEMO_ANLAGE = dict(kwp=10.92, module=24, speicher_kwh=10, hems=True, spot=True, hh_kwh=4500, wp_kwh=4500,
                   wb_kwh=0, investition_eur=24900, startjahr=2027)


def demo() -> dict:
    """Demo-Teilbaum mit den v22-Kontrollwerten (Max Mustermann, keine Kundendaten, keine Datenbank)."""
    daten = {"anlage": DEMO_ANLAGE, "param": DEMO_PARAM, "fehlende_parameter": [],
             "ergebnis": wirtschaftlichkeit.berechnen(DEMO_PARAM, DEMO_ANLAGE)}
    kopf = {"nummer": "AN-C-269999", "ort": AUSSTELLUNGSORT, "datum": date(2026, 10, 16).strftime("%d.%m.%Y"),
            "kunde": "Familie Mustermann", "adresse": "Musterstraße 12, 47139 Duisburg"}
    return aufbereiten(daten, kopf)
