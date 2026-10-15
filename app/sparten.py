# v31 (PLAN_LEAD_V5 Phase 156/157): Sparten-Kürzel und ihre Langformen für Kundenmails.
# Kürzel bleiben intern (Badges, Chips, Datenbank); Kundentexte nutzen die Langform.
# Neue Interessen seit v31: MS (Mieterstrom), WA (Wasser), DMS (Denkmalschutz) – ohne
# eigene Erfassung (Freitext-Weg wie WB/GW), ohne monday-Spalte.
# Parameter `sparten_langnamen` (Lead-Einstellungen, JSON {"WP": "Wärmepumpe", …})
# übersteuert die Langformen; Parameter liest der Aufrufer über
# leadmanagement.parameter_holen und reicht ihn als `langnamen` herein.
import json
import re

# Reihenfolge = Anzeigereihenfolge (Badges, Filter, Statistik)
SPARTEN = ("WP", "PV", "KL", "WB", "GW", "MS", "WA", "DMS")
SPARTEN_LANG = {
    "WP": "Wärmepumpe", "PV": "Photovoltaik", "KL": "Klimaanlage", "WB": "Wallbox",
    "GW": "Gewerbe", "MS": "Mieterstrom", "WA": "Wasser", "DMS": "Denkmalschutz",
}
# Artikel für „Interesse an …“ (Phase 156): "einer Wärmepumpe", "Photovoltaik" (ohne
# Artikel), "einer Klimaanlage", "einer Wallbox", "einer gewerblichen Lösung" …
INTERESSE_FORM = {
    "WP": "einer Wärmepumpe", "PV": "Photovoltaik", "KL": "einer Klimaanlage",
    "WB": "einer Wallbox", "GW": "einer gewerblichen Lösung", "MS": "Mieterstrom",
    "WA": "einer Wasserlösung", "DMS": "einer denkmalgerechten Lösung",
}
# Platzhalter-Sparten, die keine eigene Konfigurator-Erfassung haben (Freitext-Weg)
FREITEXT_SPARTEN = ("WB", "GW", "MS", "WA", "DMS")
_TRENNER = re.compile(r"[,;/ ]+")


def codes(wert) -> list[str]:
    """Kürzel aus einem Text („WP,PV“, „WP PV“, JSON-Liste) oder einer Liste – in
    Anzeigereihenfolge, unbekannte Kürzel bleiben am Ende erhalten."""
    if wert is None:
        return []
    if isinstance(wert, str):
        text = wert.strip()
        if text.startswith("["):
            try:
                liste = json.loads(text)
            except ValueError:
                liste = _TRENNER.split(text)
        else:
            liste = _TRENNER.split(text)
    else:
        liste = list(wert)
    roh = [str(c).strip().upper() for c in liste if str(c).strip()]
    bekannt = [c for c in SPARTEN if c in roh]
    fremd = [c for c in roh if c not in SPARTEN]
    return bekannt + [c for c in dict.fromkeys(fremd)]


def langnamen_laden(parameter_wert: str | None) -> dict:
    """Langformen inkl. Übersteuerung aus dem Parameter `sparten_langnamen` (JSON)."""
    namen = dict(SPARTEN_LANG)
    if parameter_wert and parameter_wert.strip():
        try:
            daten = json.loads(parameter_wert)
            if isinstance(daten, dict):
                for k, v in daten.items():
                    if str(v).strip():
                        namen[str(k).strip().upper()] = str(v).strip()
        except ValueError:
            pass
    return namen


def langname(code: str, langnamen: dict | None = None) -> str:
    code = (code or "").strip().upper()
    return (langnamen or SPARTEN_LANG).get(code, code)


def _aufzaehlung(teile: list[str]) -> str:
    teile = [t for t in teile if t]
    if not teile:
        return ""
    if len(teile) == 1:
        return teile[0]
    return ", ".join(teile[:-1]) + " und " + teile[-1]


def sparten_text(wert, form: str = "lang", langnamen: dict | None = None) -> str:
    """Natürliche Aufzählung der Sparten: form „lang“ → „Wärmepumpe und Photovoltaik“,
    „kurz“ → „WP und PV“ (Phase 156, Platzhalter {sparten})."""
    liste = codes(wert)
    if form == "kurz":
        return _aufzaehlung(liste)
    return _aufzaehlung([langname(c, langnamen) for c in liste])


def sparten_interesse(wert, langnamen: dict | None = None) -> str:
    """Platzhalter {sparten_interesse}: „Interesse an einer Wärmepumpe“, „Interesse an
    Photovoltaik“, bei mehreren „Interesse an einer Wärmepumpe und Photovoltaik“.
    Übersteuerte Langnamen (Parameter) werden ohne Artikel eingesetzt."""
    liste = codes(wert)
    if not liste:
        return "Interesse an unseren Lösungen"
    teile = []
    for c in liste:
        if langnamen and langnamen.get(c) and langnamen.get(c) != SPARTEN_LANG.get(c):
            teile.append(langnamen[c])
        else:
            teile.append(INTERESSE_FORM.get(c, langname(c, langnamen)))
    return "Interesse an " + _aufzaehlung(teile)


def ist_freitext_sparte(code: str, logik=None) -> bool:
    """Reine Freitext-Sparte (kein Erfassungsbogen)? GW/MS/WA/DMS immer.
    v34 (PLAN_V21 Phase 179): WB ist keine reine Freitext-Sparte mehr, sobald die
    Logik das Blatt „Aktionen WB“ trägt (Wallbox-Konfigurator) – dann zeigt der
    Sparten-Start die Weiche Katalog | Freitext wie bei PV/KL. `logik` = die volle
    Logik (app.logik.hole_logik); ohne Angabe wird die im Prozess geladene Logik
    genutzt, ohne geladene Logik gilt WB weiter als Freitext."""
    code = (code or "").strip().upper()
    if code != "WB":
        return code in FREITEXT_SPARTEN
    if logik is None:
        try:
            from app import logik as logik_modul
            logik = logik_modul._cache.get("logik")
        except Exception:   # noqa: BLE001 – Logik nicht ladbar: Freitext bleibt der sichere Weg
            logik = None
    return not bool(getattr(logik, "wb_aktionen", None))


def freitext_sparten(logik=None) -> list[str]:
    """Alle Sparten, die derzeit nur als Freitext erfasst werden (Anzeige im
    Sparten-Start)."""
    return [code for code in SPARTEN if ist_freitext_sparte(code, logik)]
