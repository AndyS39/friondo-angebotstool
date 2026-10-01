# Wirtschaftlichkeit PV (v22, PLAN_V15 Phase 100): reiner Rechenkern ohne
# DB-Zugriffe. Ersetzt die additive Eigenverbrauchsquote der v16-Beispiel-
# rechnung durch eine Energiebilanz je Jahr (Direktverbrauch, Speicher,
# Netzbezug, Einspeisung), rechnet Stromkosten ohne/mit Anlage über den
# Betrachtungszeitraum, Break-even, Baustein-Treppe, Strompreis-Szenarien
# und CO₂. Alle Rechenwerte kommen aus dem Blatt „PV-Parameter" der Logik-
# Excel (parameter_lesen); fehlende Zeilen fallen auf STANDARD zurück.
#
# Formeln (Saisonmodell, Entscheidung 01.10.2026 – ersetzt das Jahresmodell
# aus Anhang A des Plans; Anhang B):
#   prod_j   = kwp × ertrag × (1 − degradation)^(j−1)
#   je Monat m (Monatsprofile als Anteile am Jahr, Σ = 1):
#     prod_m  = prod_j × profil_pv[m] · sonne_m = profil_pv[m] × 12 (1 = Durchschnittsmonat)
#     x_m     = x_kwh × profil_x[m], x ∈ {hh, wp, wb} · last_m = Σ x_m
#     q_x     = Direktanteil_x + HEMS-Zuschlag_x (nur mit HEMS)
#     direkt_m = min(Σ q_x × x_m × sonne_m, 0,9 × prod_m, last_m)
#     sp_out_m = min(speicher × zyklen × tage_m ÷ 365, (prod_m − direkt_m) × wirkungsgrad,
#                    last_m − direkt_m) · sp_in_m = sp_out_m ÷ wirkungsgrad
#     netz_m  = last_m − direkt_m − sp_out_m · einsp_m = prod_m − direkt_m − sp_in_m
#     wp_pv_m = direkt_m × (q_wp × wp_m) ÷ Σ q_x × x_m + sp_out_m × wp_m ÷ last_m
#   Jahreswerte = Σ über die Monate; dann wie bisher:
#   preis_j  = strompreis × (1+steigerung)^(j−1); bezug_j = spot_preis × … bei SpotDynamic
#   ohne_j   = last × preis_j · mit_j = netz × bezug_j − einsp × vergütung + betriebskosten
#   kum_j    = −investition + Σ ersparnis_1..j; Break-even = erstes j mit kum_j ≥ 0
# Monatsprofile (Standard, parametrierbar im Blatt „PV-Parameter“): PV nach
# typischer Ertragsverteilung Deutschland (Nov–Feb ≈ 12 %, Sommerhalbjahr ≈ 70 %),
# Haushalt angelehnt an BDEW-H0 (Winter höher), Wärmepumpe = 80 % Heizung nach
# VDI-2067-Gradtagszahlen + 20 % Warmwasser gleichverteilt, Wallbox gleichverteilt.

from __future__ import annotations

import re
from typing import Optional

MONATSTAGE = [31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]
MONATSNAMEN = ["Jan", "Feb", "Mär", "Apr", "Mai", "Jun", "Jul", "Aug", "Sep", "Okt",
               "Nov", "Dez"]
# Monatsprofile in % des Jahres (12 Werte, Januar … Dezember)
PROFIL_PV = [2.5, 4.5, 10.0, 11.0, 12.5, 13.0, 13.0, 11.5, 9.5, 7.0, 3.5, 2.0]
PROFIL_HH = [9.5, 8.5, 8.8, 8.0, 7.7, 7.3, 7.5, 7.5, 7.7, 8.4, 9.0, 10.1]
# 80 % Heizung (VDI 2067: 170/150/130/80/40/13,3/13,3/13,3/30/80/120/160 ‰) + 20 % WW flach
PROFIL_WP = [15.3, 13.7, 12.1, 8.1, 4.9, 2.7, 2.7, 2.7, 4.1, 8.1, 11.3, 14.5]
PROFIL_WB = [8.33] * 12


def _normiert(profil) -> list[float]:
    summe = float(sum(profil))
    return [float(w) / summe for w in profil] if summe > 0 else [1 / 12] * 12

# Standardwerte (greifen, wenn eine Zeile im Blatt „PV-Parameter" fehlt) –
# Prozentwerte hier als Anteile (0,03 = 3 %).
STANDARD: dict = {
    "ertrag": 960.0,            # kWh/kWp
    "strompreis": 0.32,         # €/kWh
    "verguetung": 0.078,        # €/kWh
    "steigerung": 0.03,         # je Jahr
    "degradation": 0.004,       # je Jahr
    "betriebskosten": 100.0,    # €/Jahr
    "jahre": 20,                # Betrachtungszeitraum
    "versatz": 1,               # Inbetriebnahme-Versatz (Startjahr = Angebotsjahr + Versatz)
    "direkt_hh": 0.35, "direkt_wp": 0.20, "direkt_wb": 0.30,       # Direktanteile
    "hems_hh": 0.05, "hems_wp": 0.15, "hems_wb": 0.20,             # HEMS-Zuschläge (Punkte)
    "zyklen": 250.0,            # Speicher-Vollzyklen je Jahr
    "wirkungsgrad": 0.90,       # Speicher
    "spot_preis": 0.18,         # €/kWh SpotDynamic-Bezug (Ø)
    "airbag": 0.39,             # €/kWh Kosten-Airbag (nur Text)
    "szenarien": [0.01, 0.03, 0.05],
    "co2_faktor": 380.0,        # g/kWh Netzstrom (Umweltbundesamt)
    "co2_auto": 120.0,          # g/km
    "co2_baum": 12.5,           # kg/Jahr je Baum
    "montage_text": "Montage in 1–2 Tagen",
    # Saisonmodell (01.10.2026): Monatsprofile als Anteile (Σ = 1)
    "profil_pv": _normiert(PROFIL_PV),
    "profil_hh": _normiert(PROFIL_HH),
    "profil_wp": _normiert(PROFIL_WP),
    "profil_wb": _normiert(PROFIL_WB),
}

# Blatt „PV-Parameter": Parametername → (Schlüssel, Art). Art: zahl · prozent
# (Wert in % → Anteil) · ganzzahl · liste_prozent („1; 3; 5") · text
PARAMETER_ZEILEN: list[tuple[str, str, str]] = [
    ("Spezifischer Ertrag", "ertrag", "zahl"),
    ("Strompreis", "strompreis", "zahl"),
    ("Einspeisevergütung", "verguetung", "zahl"),
    ("Strompreissteigerung", "steigerung", "prozent"),
    ("Degradation", "degradation", "prozent"),
    ("Betriebskosten", "betriebskosten", "zahl"),
    ("Betrachtungszeitraum", "jahre", "ganzzahl"),
    ("Inbetriebnahme-Versatz", "versatz", "ganzzahl"),
    ("Direktanteil Haushalt", "direkt_hh", "prozent"),
    ("Direktanteil Wärmepumpe", "direkt_wp", "prozent"),
    ("Direktanteil Wallbox", "direkt_wb", "prozent"),
    ("HEMS-Zuschlag Haushalt", "hems_hh", "prozent"),
    ("HEMS-Zuschlag Wärmepumpe", "hems_wp", "prozent"),
    ("HEMS-Zuschlag Wallbox", "hems_wb", "prozent"),
    ("Speicher Vollzyklen", "zyklen", "zahl"),
    ("Speicher Wirkungsgrad", "wirkungsgrad", "prozent"),
    ("SpotDynamic Bezugspreis", "spot_preis", "zahl"),
    ("Kosten-Airbag", "airbag", "zahl"),
    ("Szenarien Strompreissteigerung", "szenarien", "liste_prozent"),
    ("CO₂-Faktor Netzstrom", "co2_faktor", "zahl"),
    ("CO₂ Auto", "co2_auto", "zahl"),
    ("CO₂ Baum", "co2_baum", "zahl"),
    ("Montagedauer-Text", "montage_text", "text"),
    ("Monatsprofil PV", "profil_pv", "profil"),
    ("Monatsprofil Haushalt", "profil_hh", "profil"),
    ("Monatsprofil Wärmepumpe", "profil_wp", "profil"),
    ("Monatsprofil Wallbox", "profil_wb", "profil"),
]


def _profil_text(profil) -> str:
    return "; ".join(f"{w:g}".replace(".", ",") for w in profil)

# Neue Zeilen für das Blatt „PV-Parameter" (Parameter · Wert · Einheit ·
# Bemerkung) – Quelle für den Excel-Nachtrag und die Standardwert-Hinweise
# in der Parametrierung. Prozentwerte stehen als Zahl mit Einheit „%".
NEUE_PARAMETER_ZEILEN: list[tuple[str, str, str, str]] = [
    ("Strompreissteigerung", "3", "%/Jahr", "v22 Wirtschaftlichkeit: Annahme Strompreisentwicklung"),
    ("Degradation", "0,4", "%/Jahr", "v22: Leistungsabnahme der Module je Jahr"),
    ("Betriebskosten", "100", "€/Jahr", "v22: Versicherung, Wartung, Zählergebühr (pauschal)"),
    ("Betrachtungszeitraum", "20", "Jahre", "v22: Laufzeit der Betrachtung"),
    ("Inbetriebnahme-Versatz", "1", "Jahr", "v22: Startjahr = Angebotsjahr + Versatz"),
    ("Direktanteil Haushalt", "35", "%", "v22: Anteil des Haushaltsstroms, der direkt aus PV gedeckt wird"),
    ("Direktanteil Wärmepumpe", "20", "%", "v22: Anteil des WP-Stroms direkt aus PV (ohne HEMS)"),
    ("Direktanteil Wallbox", "30", "%", "v22 [ANNAHME]: Anteil des Wallbox-Stroms direkt aus PV"),
    ("HEMS-Zuschlag Haushalt", "5", "%-Punkte", "v22: Zuschlag auf den Direktanteil mit Friondo HEMS"),
    ("HEMS-Zuschlag Wärmepumpe", "15", "%-Punkte", "v22: Zuschlag auf den Direktanteil mit Friondo HEMS"),
    ("HEMS-Zuschlag Wallbox", "20", "%-Punkte", "v22 [ANNAHME]: Zuschlag auf den Direktanteil mit Friondo HEMS"),
    ("Speicher Vollzyklen", "250", "/Jahr", "v22: nutzbare Vollzyklen des Speichers je Jahr"),
    ("Speicher Wirkungsgrad", "90", "%", "v22: Round-trip-Wirkungsgrad des Speichers"),
    ("SpotDynamic Bezugspreis", "0,18", "€/kWh", "v22: Ø Netzbezugspreis mit Friondo SpotDynamic"),
    ("Kosten-Airbag", "0,39", "€/kWh", "v22: Obergrenze SpotDynamic (nur Text auf Seite 3)"),
    ("Szenarien Strompreissteigerung", "1; 3; 5", "%/Jahr", "v22: drei Säulen auf Seite 3 (vorsichtig · Ihre Rechnung · stark)"),
    ("CO₂-Faktor Netzstrom", "380", "g/kWh", "v22: Umweltbundesamt, deutscher Strommix"),
    ("CO₂ Auto", "120", "g/km", "v22: Umrechnung in Autokilometer"),
    ("CO₂ Baum", "12,5", "kg/Jahr", "v22: CO₂-Bindung je Baum und Jahr"),
    ("Montagedauer-Text", "Montage in 1–2 Tagen", "Text", "v22: Schritt 3 unter „So geht es weiter“ (Seite 3)"),
    ("Monatsprofil PV", _profil_text(PROFIL_PV), "% je Monat",
     "v22 Saisonmodell: Anteil des Jahresertrags je Monat Jan–Dez (typische Verteilung "
     "Deutschland: Nov–Feb ≈ 12 %, Apr–Sep ≈ 70 %)"),
    ("Monatsprofil Haushalt", _profil_text(PROFIL_HH), "% je Monat",
     "v22 Saisonmodell [ANNAHME]: Haushaltsstrom je Monat, angelehnt an BDEW-Lastprofil H0 "
     "(Winter höher, Sommer niedriger)"),
    ("Monatsprofil Wärmepumpe", _profil_text(PROFIL_WP), "% je Monat",
     "v22 Saisonmodell: 80 % Heizung nach VDI-2067-Gradtagszahlen + 20 % Warmwasser "
     "gleichverteilt"),
    ("Monatsprofil Wallbox", _profil_text(PROFIL_WB), "% je Monat",
     "v22 Saisonmodell [ANNAHME]: Wallbox gleichverteilt"),
]

# Bausteine der Treppe in fester Reihenfolge: (Schlüssel, Name)
BAUSTEINE = [("pv", "PV-Anlage allein"), ("speicher", "+ Speicher"),
             ("hems", "+ Friondo HEMS"), ("spot", "+ SpotDynamic")]


# --- Parameter ---------------------------------------------------------------

def _zahl(text) -> Optional[float]:
    """„0,4" · „3 %" · „380" → float; None, wenn keine Zahl."""
    t = str(text if text is not None else "").strip().replace(" ", "")
    t = t.replace("%", "").replace("€", "")
    if not t:
        return None
    if "," in t:
        t = t.replace(".", "").replace(",", ".")
    try:
        return float(t)
    except ValueError:
        return None


def _liste(text) -> list[str]:
    """Listenwerte „1; 3; 5“ bzw. „2,5; 4,5 …“ – Trenner Semikolon oder
    senkrechter Strich (Komma ist Dezimaltrenner); ohne Trenner Leerzeichen."""
    roh = str(text or "").strip()
    teile = [t.strip() for t in re.split(r"\s*[;|]\s*", roh) if t.strip()]
    if len(teile) <= 1:
        teile = [t for t in roh.split() if t]
    return teile


def _liste_prozent(text) -> Optional[list[float]]:
    werte = [_zahl(t) for t in _liste(text)]
    werte = [w / 100 for w in werte if w is not None]
    return sorted(werte) or None


def parameter_lesen(pv_parameter: dict | None) -> tuple[dict, list[str]]:
    """Baut den Parametersatz aus `logik.pv_parameter` (Name → (Wert,
    Bemerkung)); liefert (param, fehlende Zeilen). Fehlende oder unlesbare
    Zeilen nehmen den Standardwert – das PDF wird nie blockiert."""
    quelle = {name: (werte[0] if isinstance(werte, (tuple, list)) else werte)
              for name, werte in (pv_parameter or {}).items()}
    param = dict(STANDARD)
    fehlende: list[str] = []
    for name, schluessel, art in PARAMETER_ZEILEN:
        roh = quelle.get(name)
        if roh is None or str(roh).strip() == "":
            fehlende.append(name)
            continue
        if art == "text":
            param[schluessel] = str(roh).strip()
            continue
        if art == "liste_prozent":
            liste = _liste_prozent(roh)
            if liste is None:
                fehlende.append(name)
            else:
                param[schluessel] = liste
            continue
        if art == "profil":
            werte = [_zahl(t) for t in _liste(roh)]
            if len(werte) != 12 or any(w is None or w < 0 for w in werte) or sum(werte) <= 0:
                fehlende.append(name)
            else:
                param[schluessel] = _normiert(werte)
            continue
        wert = _zahl(roh)
        if wert is None:
            fehlende.append(name)
            continue
        if art == "prozent":
            wert = wert / 100
        elif art == "ganzzahl":
            wert = int(round(wert))
        param[schluessel] = wert
    param["jahre"] = max(1, int(param["jahre"]))
    return param, fehlende


def standardwert_text(name: str) -> str:
    """Standardwert einer Parameterzeile als Anzeigetext (Parametrierung)."""
    for zeile in NEUE_PARAMETER_ZEILEN:
        if zeile[0] == name:
            return f"{zeile[1]} {zeile[2]}".strip()
    return ""


# --- Energiebilanz -------------------------------------------------------------

def energie(p: dict, a: dict, j: int, hems: bool) -> dict:
    """Energiebilanz eines Jahres j (1-basiert) in kWh – Saisonmodell: die
    Bilanz wird je Monat mit den Monatsprofilen gerechnet und aufsummiert
    (Winter: wenig Sonne, viel Wärmepumpe; Sommer umgekehrt)."""
    prod_j = a["kwp"] * p["ertrag"] * (1 - p["degradation"]) ** (j - 1)
    q = {x: p["direkt_" + x] + (p["hems_" + x] if hems else 0.0)
         for x in ("hh", "wp", "wb")}
    speicher = a.get("speicher_kwh") or 0.0
    profil = {"hh": p["profil_hh"], "wp": p["profil_wp"], "wb": p["profil_wb"]}
    summe = dict(prod=0.0, direkt=0.0, sp_in=0.0, sp_out=0.0, last=0.0, netz=0.0,
                 einsp=0.0, wp_pv=0.0)
    monate = []
    for m in range(12):
        prod_m = prod_j * p["profil_pv"][m]
        sonne = p["profil_pv"][m] * 12          # 1 = Durchschnittsmonat
        x_m = {x: a[x + "_kwh"] * profil[x][m] for x in ("hh", "wp", "wb")}
        last_m = sum(x_m.values())
        gewichtet = sum(q[x] * x_m[x] for x in x_m)   # Σ q_x × x_m
        direkt_m = max(0.0, min(gewichtet * sonne, 0.9 * prod_m, last_m))
        sp_out_m = 0.0
        if speicher > 0:
            sp_out_m = max(0.0, min(speicher * p["zyklen"] * MONATSTAGE[m] / 365,
                                    (prod_m - direkt_m) * p["wirkungsgrad"],
                                    last_m - direkt_m))
        sp_in_m = sp_out_m / p["wirkungsgrad"] if sp_out_m else 0.0
        netz_m = max(0.0, last_m - direkt_m - sp_out_m)
        einsp_m = max(0.0, prod_m - direkt_m - sp_in_m)
        wp_pv_m = ((direkt_m * q["wp"] * x_m["wp"] / gewichtet if gewichtet else 0.0)
                   + (sp_out_m * x_m["wp"] / last_m if last_m else 0.0))
        monat = dict(prod=prod_m, direkt=direkt_m, sp_in=sp_in_m, sp_out=sp_out_m,
                     last=last_m, netz=netz_m, einsp=einsp_m, wp_pv=min(wp_pv_m, x_m["wp"]))
        monate.append(monat)
        for k in summe:
            summe[k] += monat[k]
    summe["wp_pv"] = min(summe["wp_pv"], a["wp_kwh"])
    return dict(summe, q=q, monate=monate)


def reihe(p: dict, a: dict, hems: bool, spot: bool) -> list[dict]:
    """Jahreszeilen 1…N mit Kosten ohne/mit Anlage, Ersparnis und kumuliertem
    Ergebnis (−Investition + Σ Ersparnis)."""
    zeilen, kum = [], -float(a["investition_eur"])
    for j in range(1, int(p["jahre"]) + 1):
        e = energie(p, a, j, hems)
        preis = p["strompreis"] * (1 + p["steigerung"]) ** (j - 1)
        bezug = (p["spot_preis"] * (1 + p["steigerung"]) ** (j - 1)) if spot else preis
        ohne = e["last"] * preis
        mit = e["netz"] * bezug - e["einsp"] * p["verguetung"] + p["betriebskosten"]
        kum += ohne - mit
        zeilen.append(dict(jahr=j, preis=preis, bezug=bezug, ohne=ohne, mit=mit,
                           ersparnis=ohne - mit, kum=kum,
                           **{k: v for k, v in e.items() if k != "monate"}))
    return zeilen


def _break_even(zeilen: list[dict]) -> Optional[int]:
    return next((z["jahr"] for z in zeilen if z["kum"] >= 0), None)


def _kennzahlen(zeilen: list[dict], a: dict) -> dict:
    summe_ohne = sum(z["ohne"] for z in zeilen)
    summe_mit = sum(z["mit"] for z in zeilen)
    summe_ersparnis = summe_ohne - summe_mit
    investition = float(a["investition_eur"])
    return {
        "ersparnis_1": zeilen[0]["ersparnis"],
        "monat": zeilen[0]["ersparnis"] / 12,
        "summe_ohne": summe_ohne, "summe_mit": summe_mit,
        "summe_ersparnis": summe_ersparnis,
        "faktor": (summe_ersparnis / investition) if investition > 0 else None,
        "gewinn_ende": zeilen[-1]["kum"],
        "break_even": _break_even(zeilen),
    }


# --- Gesamtrechnung ----------------------------------------------------------

def berechnen(param: dict, anlage: dict) -> dict:
    """Vollständige Wirtschaftlichkeit für ein Angebot.

    anlage: kwp · module · speicher_kwh (0 = kein Speicher) · hems (bool) ·
    spot (bool) · hh_kwh · wp_kwh · wb_kwh · investition_eur · startjahr
    (Kalenderjahr der Inbetriebnahme). param: siehe STANDARD/parameter_lesen.
    Liefert ein dict ohne DB-Bezug (alle Beträge in €, Energie in kWh,
    Quoten als Anteil 0…1)."""
    p = dict(STANDARD)
    p.update(param or {})
    a = {
        "kwp": float(anlage.get("kwp") or 0.0),
        "module": int(anlage.get("module") or 0),
        "speicher_kwh": float(anlage.get("speicher_kwh") or 0.0),
        "hems": bool(anlage.get("hems")),
        "spot": bool(anlage.get("spot")),
        "hh_kwh": float(anlage.get("hh_kwh") or 0.0),
        "wp_kwh": float(anlage.get("wp_kwh") or 0.0),
        "wb_kwh": float(anlage.get("wb_kwh") or 0.0),
        "investition_eur": float(anlage.get("investition_eur") or 0.0),
        "startjahr": int(anlage.get("startjahr") or 0),
    }
    n = int(p["jahre"])
    zeilen = reihe(p, a, a["hems"], a["spot"])
    for z in zeilen:
        z["kalenderjahr"] = a["startjahr"] + z["jahr"] - 1 if a["startjahr"] else None
    kennzahlen = _kennzahlen(zeilen, a)
    e1 = zeilen[0]
    e1_monate = energie(p, a, 1, a["hems"])["monate"]
    e1_ohne_hems = energie(p, a, 1, False)
    e1_mit_hems = energie(p, a, 1, True)
    last = e1["last"]
    wp = a["wp_kwh"]

    # Baustein-Treppe: nur enthaltene Stufen, sequentiell aufgebaut
    treppe: list[dict] = []
    stufen = [("pv", "PV-Anlage allein", 0.0, False, False)]
    if a["speicher_kwh"] > 0:
        stufen.append(("speicher", f"+ Speicher {_de(a['speicher_kwh'], 0 if a['speicher_kwh'] == int(a['speicher_kwh']) else 1)} kWh",
                       a["speicher_kwh"], False, False))
    if a["hems"]:
        stufen.append(("hems", "+ Friondo HEMS", a["speicher_kwh"], True, False))
    if a["spot"]:
        stufen.append(("spot", "+ SpotDynamic", a["speicher_kwh"], a["hems"], True))
    vorher = 0.0
    for schluessel, name, sp, hems, spot in stufen:
        zr = reihe(p, dict(a, speicher_kwh=sp), hems, spot)
        k = _kennzahlen(zr, a)
        treppe.append({"schluessel": schluessel, "name": name,
                       "ersparnis_1": k["ersparnis_1"], "summe": k["summe_ersparnis"],
                       "break_even": k["break_even"],
                       "delta": k["ersparnis_1"] - vorher if treppe else None})
        vorher = k["ersparnis_1"]
    spot_hinweis = None
    if not a["spot"]:
        zr = reihe(p, a, a["hems"], True)
        spot_hinweis = {"ersparnis_1": zr[0]["ersparnis"],
                        "delta_1": zr[0]["ersparnis"] - e1["ersparnis"],
                        "summe": sum(z["ersparnis"] for z in zr),
                        "break_even": _break_even(zr)}

    szenarien = []
    for steigerung in p["szenarien"]:
        zr = reihe(dict(p, steigerung=steigerung), a, a["hems"], a["spot"])
        szenarien.append({"steigerung": steigerung,
                          "summe": sum(z["ersparnis"] for z in zr),
                          "break_even": _break_even(zr)})

    co2_kg_1 = e1["prod"] * p["co2_faktor"] / 1000
    co2_kg_n = sum(z["prod"] for z in zeilen) * p["co2_faktor"] / 1000
    co2 = {"t_jahr": co2_kg_1 / 1000, "t_gesamt": co2_kg_n / 1000,
           "km": co2_kg_1 / (p["co2_auto"] / 1000) if p["co2_auto"] else None,
           "baeume": co2_kg_1 / p["co2_baum"] if p["co2_baum"] else None}

    # Aufschlüsselung Jahr 1 (Seite 2, Karte „Ihr Vorteil im ersten Jahr")
    preis_1 = e1["preis"]
    vorteil = {
        "last": last, "preis": preis_1,
        "stromkosten_heute": e1["ohne"],
        "netz": e1["netz"], "netzbezug": e1["netz"] * preis_1,
        "einsp": e1["einsp"], "einspeisung": e1["einsp"] * p["verguetung"],
        "spot_differenz": (preis_1 - e1["bezug"]) if a["spot"] else 0.0,
        "spot_vorteil": e1["netz"] * (preis_1 - e1["bezug"]) if a["spot"] else 0.0,
        "betriebskosten": p["betriebskosten"],
        "summe": e1["ersparnis"],
    }
    heizen = None
    if wp > 0:
        heizen = {
            "wp_kwh": wp,
            "anteil_pv": e1["wp_pv"] / wp,
            "anteil_ohne_hems": e1_ohne_hems["wp_pv"] / wp,
            "anteil_mit_hems": e1_mit_hems["wp_pv"] / wp,
            "kosten_ohne_pv": wp * preis_1,
            "kosten_mit_pv": (wp - e1["wp_pv"]) * preis_1,
        }

    return {
        "param": p, "anlage": a, "jahre": zeilen, "n": n,
        "monate_j1": e1_monate,
        "startjahr": a["startjahr"] or None,
        "endjahr": (a["startjahr"] + n - 1) if a["startjahr"] else None,
        "break_even_jahr": (a["startjahr"] + kennzahlen["break_even"] - 1)
        if (a["startjahr"] and kennzahlen["break_even"]) else None,
        "j1": {
            "prod": e1["prod"], "direkt": e1["direkt"], "sp_in": e1["sp_in"],
            "sp_out": e1["sp_out"], "netz": e1["netz"], "einsp": e1["einsp"],
            "last": last,
            "ev_quote": ((e1["direkt"] + e1["sp_in"]) / e1["prod"]) if e1["prod"] else None,
            "autarkie": ((e1["direkt"] + e1["sp_out"]) / last) if last else None,
            "solaranteil_wp": (e1["wp_pv"] / wp) if wp else None,
            "solaranteil_wp_ohne_hems": (e1_ohne_hems["wp_pv"] / wp) if wp else None,
            "solaranteil_wp_mit_hems": (e1_mit_hems["wp_pv"] / wp) if wp else None,
        },
        **kennzahlen,
        "treppe": treppe, "spot_hinweis": spot_hinweis,
        "szenarien": szenarien, "co2": co2, "vorteil": vorteil, "heizen": heizen,
    }


def _de(zahl: float, stellen: int = 0) -> str:
    text = f"{zahl:,.{stellen}f}"
    return text.replace(",", "X").replace(".", ",").replace("X", ".")
