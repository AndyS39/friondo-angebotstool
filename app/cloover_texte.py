"""v36 (PLAN_V22 Phase 192/193/194, Agent B1): Textbausteine der Cloover-Finanzierung – Fußnote der Rate
(Pflichtangaben-Entwurf, Rückfrage B1 Cloover/PAngV) und Datenschutzsatz (Entwurf, Rückfrage B7).

Ablage in der Tabelle einstellungen (Parametrierung → Cloover, Schlüssel `cloover_fussnote` /
`cloover_datenschutz` = app.cloover.TEXT_FUSSNOTE / TEXT_DATENSCHUTZ); leer = Standardtext aus diesem
Modul. Agent B2 rendert die Texte (PDF-Karte, fpdf2-Rückfall); `fussnote_rendern` liefert dafür die
fertige Fußnote mit Platzhaltern {endbetrag}, {laufzeit}, {anzahlung}, {foerderung}, {stand} – ohne
Förderung entfällt der Halbsatz „‚mit Förderung‘ …“ (Plan Phase 193).
"""
from __future__ import annotations

KEY_FUSSNOTE = "cloover_fussnote"
KEY_DATENSCHUTZ = "cloover_datenschutz"
PLATZHALTER = ("endbetrag", "laufzeit", "anzahlung", "foerderung", "stand")

# Halbsatz, der nur bei WP mit Förderbetrag > 0 steht (Plan Phase 193, wörtlich)
FOERDERUNG_TEILSATZ = ("; ‚mit Förderung‘ berücksichtigt die voraussichtliche Förderung von {foerderung} als "
                       "Sondertilgung nach Auszahlung")

# Entwurf laut Plan Phase 193 – Pflichtangaben-Wortlaut bis zur Rückfrage B1 (Cloover/PAngV)
FUSSNOTE_STANDARD = ("*Unverbindliche Beispielrechnung unseres Finanzierungspartners Cloover auf Basis des "
                     "Endbetrags dieses Angebots von {endbetrag}, einer Laufzeit von {laufzeit} Jahren und "
                     "{anzahlung} Anzahlung" + FOERDERUNG_TEILSATZ + ". Stand {stand}. Verbindliche "
                     "Konditionen, Sollzins und effektiver Jahreszins ergeben sich aus dem "
                     "Finanzierungsangebot von Cloover.")

# Entwurf laut Plan Phase 194 – Wortlaut mit dem Datenschutzbeauftragten abstimmen (Rückfrage B7)
DATENSCHUTZ_STANDARD = ("Zur Bereitstellung Ihres persönlichen Finanzierungs-Links haben wir Ihre Kontaktdaten, "
                        "die Adresse des Vorhabens und dieses Angebot an unseren Finanzierungspartner Cloover "
                        "übermittelt. Hinweise zum Datenschutz: https://friondo.de/Datenschutz")

STANDARD = {KEY_FUSSNOTE: FUSSNOTE_STANDARD, KEY_DATENSCHUTZ: DATENSCHUTZ_STANDARD}
HINWEIS_ENTWURF = "Entwurf – Rückfrage B1 (Cloover/PAngV) bzw. B7 (Datenschutz) offen"
MAX_LAENGE = 5000


def standard(key: str) -> str:
    return STANDARD.get(key, "")


def text_holen(session, key: str) -> str:
    """Gespeicherter Text, sonst der Standard (leer gespeichert = Standard)."""
    if key not in STANDARD:
        return ""
    from app.models import einstellung_holen
    return (einstellung_holen(session, key, "") or "").strip() or STANDARD[key]


def ist_standard(session, key: str) -> bool:
    from app.models import einstellung_holen
    return not (einstellung_holen(session, key, "") or "").strip()


def text_setzen(session, key: str, text: str) -> str:
    """Text speichern (leer oder gleich dem Standard = Standard wiederherstellen); liefert den
    gespeicherten Wert ("" = Standard). Der Aufrufer committet."""
    if key not in STANDARD:
        raise KeyError(key)
    from app.models import einstellung_setzen
    wert = (text or "").strip().replace("\r\n", "\n")[:MAX_LAENGE]
    if wert == STANDARD[key]:
        wert = ""
    einstellung_setzen(session, key, wert)
    return wert


def platzhalter_ersetzen(text: str, werte: dict) -> str:
    text = text or ""
    for name in PLATZHALTER:
        text = text.replace("{" + name + "}", str(werte.get(name, "") if werte.get(name) is not None else ""))
    return text


def fussnote_rendern(session, *, endbetrag: str, laufzeit, anzahlung: str, stand: str,
                     foerderung: str = "") -> str:
    """Fertige Fußnote: Beträge als Text („42.830,55 €“, „0,00 €“, „16.500,00 €“), `stand` als
    „TT.MM.JJJJ“. Ohne `foerderung` entfällt der Halbsatz „‚mit Förderung‘ …“ (im Standardtext wörtlich,
    in einem geänderten Text der Teil zwischen „;“ und „Auszahlung“ mit {foerderung}, sonst nur der
    Platzhalter)."""
    text = text_holen(session, KEY_FUSSNOTE)
    if not foerderung:
        if FOERDERUNG_TEILSATZ in text:
            text = text.replace(FOERDERUNG_TEILSATZ, "")
        else:
            import re
            text = re.sub(r";[^;.]*\{foerderung\}[^;.]*?Auszahlung", "", text)
    return platzhalter_ersetzen(text, {"endbetrag": endbetrag, "laufzeit": laufzeit, "anzahlung": anzahlung,
                                       "foerderung": foerderung, "stand": stand})


def datenschutz_text(session) -> str:
    return text_holen(session, KEY_DATENSCHUTZ)
