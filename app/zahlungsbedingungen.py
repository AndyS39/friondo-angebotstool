# Zahlungsbedingungen je Angebot – v30 (PLAN_V18 Phase 150, Entscheidung Andreas
# 11.10.2026): Tabelle `zahlungsbedingungen` (Modell app.models.Zahlungsbedingung,
# Pflege in der Parametrierung – neue Einträge, deaktivieren statt löschen, genau
# ein Standard). Am Angebot wählt der Innendienst einen Eintrag
# (`angebote.zahlungsbedingung_key`, leer = Standard-Eintrag) oder einen Freitext
# (`zahlungsbedingung_key = "freitext"`, Text in `zahlungsbedingung_text`). Der
# Nachtext der Textblöcke enthält statt des bisherigen festen Absatzes den
# Platzhalter {zahlungsbedingungen}; beim PDF-Rendern (pdf_export._nachtext_rendern)
# wird er durch den Text des gewählten Eintrags ersetzt. Skonto wirkt nur im Text –
# keine Änderung an Summen, KfW oder Deckungsbeitrag.
# migration_v30_zahlung(session) (migrate.py) legt die drei Einträge an, setzt den
# Platzhalter in allen Nachtext-Blöcken und legt die Parameter aus Phase 148/149 an.

import re

from sqlalchemy.orm import Session

from app.models import (Angebot, Einstellung, Textblock, Zahlungsbedingung,
                        einstellung_holen, einstellung_setzen)

PLATZHALTER = "{zahlungsbedingungen}"
FREITEXT = "freitext"
FREITEXT_NAME = "Abweichend (Freitext)"
NAME_MAX = 100
TEXT_MAX = 2000
# Erstlauf-Marker der Nachtext-Umstellung: die Liste der Blöcke OHNE den
# Standardabsatz wird nur beim ersten Lauf gemeldet (zweiter Lauf stumm)
MARKER_NACHTEXTE = "migration_v30_zahlung_nachtexte"
# Parameter aus Phase 148 (BzA-Puffer) und 149 (Lieferschein-Folgepositionen) –
# angelegt, falls die Zeile fehlt (ein leerer Wert ist bei den Folgepositionen gültig)
PARAMETER_STANDARD = (("bza_kosten_puffer_prozent", "10"),
                      ("lieferschein_folgepositionen", "014: 015, 016, 017"))

# Startwerte wörtlich aus PLAN_V18 Phase 150 – Eintrag 1 ist der bisherige feste
# Absatz der Nachtexte (angebotsprofile._RECHT_UND_ZAHLUNG bis v29); die Texte 2
# und 3 sind [ANNAHME] und werden vom Innendienst in der Parametrierung gegengelesen.
STANDARD_EINTRAEGE = [
    ("standard", "Standard",
     "Eine Anzahlung von 50% des Angebotsbetrags ist spätestens 14 Tage vor "
     "Arbeitsbeginn zu zahlen. Die Restzahlung wird mit der Schlussrechnungsstellung "
     "fällig. Die Rechnung erhalten Sie im Anschluss zur Installation."),
    ("montagetag_50", "50 % am Montagetag",
     "Eine Anzahlung von 50% des Angebotsbetrags ist am Tag der Montage zu zahlen. "
     "Die Restzahlung wird mit der Schlussrechnungsstellung fällig. Die Rechnung "
     "erhalten Sie im Anschluss zur Installation."),
    ("anzahlung_80_skonto", "80 % Anzahlung, 2 % Skonto",
     "Eine Anzahlung von 80% des Angebotsbetrags ist spätestens 14 Tage vor "
     "Arbeitsbeginn zu zahlen. Bei Zahlung der Anzahlung innerhalb von 7 Tagen nach "
     "Auftragserteilung gewähren wir 2% Skonto auf den Anzahlungsbetrag. Die "
     "Restzahlung wird mit der Schlussrechnungsstellung fällig. Die Rechnung erhalten "
     "Sie im Anschluss zur Installation."),
]
STANDARD_ABSATZ = STANDARD_EINTRAEGE[0][2]


# --- Lesen ---------------------------------------------------------------------

def alle(session: Session) -> list[Zahlungsbedingung]:
    return (session.query(Zahlungsbedingung)
            .order_by(Zahlungsbedingung.sortierung, Zahlungsbedingung.id).all())


def aktive(session: Session) -> list[Zahlungsbedingung]:
    return [z for z in alle(session) if z.aktiv]


def standard(session: Session) -> Zahlungsbedingung | None:
    """Der Standard-Eintrag (genau einer); ohne Markierung der erste aktive."""
    eintraege = alle(session)
    for z in eintraege:
        if z.standard and z.aktiv:
            return z
    for z in eintraege:
        if z.aktiv:
            return z
    return None


def nach_schluessel(session: Session, schluessel: str) -> Zahlungsbedingung | None:
    schluessel = (schluessel or "").strip()
    if not schluessel or schluessel == FREITEXT:
        return None
    return (session.query(Zahlungsbedingung)
            .filter(Zahlungsbedingung.schluessel == schluessel).first())


def fuer_angebot(session: Session, angebot: Angebot) -> tuple[str, str]:
    """(Name, Text) der Zahlungsbedingung eines Angebots: Freitext → wörtlich,
    gewählter Eintrag (auch ein inzwischen deaktivierter bleibt am Angebot gültig),
    sonst der Standard-Eintrag; ohne Tabelleninhalt der Code-Standard."""
    key = (getattr(angebot, "zahlungsbedingung_key", "") or "").strip()
    if key == FREITEXT:
        text = (getattr(angebot, "zahlungsbedingung_text", "") or "").strip()
        if text:
            return FREITEXT_NAME, text
    elif key:
        eintrag = nach_schluessel(session, key)
        if eintrag is not None and (eintrag.text or "").strip():
            return eintrag.name, eintrag.text.strip()
    eintrag = standard(session)
    if eintrag is not None and (eintrag.text or "").strip():
        return eintrag.name, eintrag.text.strip()
    return STANDARD_EINTRAEGE[0][1], STANDARD_ABSATZ


def auswahl_fuer_editor(session: Session, angebot: Angebot) -> tuple[list[Zahlungsbedingung], str]:
    """Dropdown im Editor: aktive Einträge (+ der am Angebot gewählte, falls er
    inzwischen deaktiviert ist) und der vorzuwählende Schlüssel (leer = Standard →
    Schlüssel des Standard-Eintrags; „freitext“ bleibt)."""
    eintraege = aktive(session)
    key = (getattr(angebot, "zahlungsbedingung_key", "") or "").strip()
    if key and key != FREITEXT:
        gewaehlt = nach_schluessel(session, key)
        if gewaehlt is not None and gewaehlt not in eintraege:
            eintraege.append(gewaehlt)
        elif gewaehlt is None:
            key = ""
    if not key:
        std = standard(session)
        key = std.schluessel if std is not None else ""
    return eintraege, key


def uebernehmen(ziel: Angebot, quelle: Angebot) -> None:
    """Überarbeiten / Duplizieren / Kopieren: beide Felder mitnehmen."""
    ziel.zahlungsbedingung_key = getattr(quelle, "zahlungsbedingung_key", "") or ""
    ziel.zahlungsbedingung_text = getattr(quelle, "zahlungsbedingung_text", "") or ""


# --- Pflege (Parametrierung) ----------------------------------------------------

def schluessel_erzeugen(session: Session, name: str) -> str:
    """Technischer Schlüssel aus dem Namen (a–z, 0–9, _), eindeutig je Tabelle."""
    roh = (name or "").strip().lower()
    for von, nach in (("ä", "ae"), ("ö", "oe"), ("ü", "ue"), ("ß", "ss"), ("%", "prozent")):
        roh = roh.replace(von, nach)
    basis = re.sub(r"[^a-z0-9]+", "_", roh).strip("_")[:40] or "eintrag"
    if basis == FREITEXT:
        basis = "eintrag_freitext"
    schluessel, lauf = basis, 2
    while nach_schluessel(session, schluessel) is not None:
        schluessel, lauf = f"{basis}_{lauf}", lauf + 1
    return schluessel


def anlegen(session: Session, name: str, text: str) -> Zahlungsbedingung:
    name = (name or "").strip()[:NAME_MAX]
    if not name:
        raise ValueError("Bitte einen Namen angeben.")
    eintrag = Zahlungsbedingung(
        schluessel=schluessel_erzeugen(session, name), name=name,
        text=(text or "").strip()[:TEXT_MAX],
        sortierung=max((z.sortierung or 0) for z in alle(session)) + 1 if alle(session) else 1,
        aktiv=True, standard=session.query(Zahlungsbedingung).count() == 0)
    session.add(eintrag)
    session.flush()
    return eintrag


def speichern(session: Session, eintrag: Zahlungsbedingung, name: str, text: str) -> None:
    name = (name or "").strip()[:NAME_MAX]
    if not name:
        raise ValueError("Bitte einen Namen angeben.")
    eintrag.name = name
    eintrag.text = (text or "").strip()[:TEXT_MAX]


def aktiv_setzen(session: Session, eintrag: Zahlungsbedingung, aktiv: bool) -> None:
    """Deaktivieren statt löschen; der Standard-Eintrag bleibt immer aktiv."""
    if not aktiv and eintrag.standard:
        raise ValueError("Der Standard-Eintrag kann nicht deaktiviert werden – "
                         "zuerst einen anderen Eintrag als Standard setzen.")
    eintrag.aktiv = aktiv


def standard_setzen(session: Session, eintrag: Zahlungsbedingung) -> None:
    """Genau ein Standard: alle anderen verlieren die Markierung."""
    for z in alle(session):
        z.standard = z.id == eintrag.id
    eintrag.aktiv = True


# --- Platzhalter in den Nachtexten -----------------------------------------------

def _absatz_muster(absatz: str) -> re.Pattern:
    """Regex für den Absatz, tolerant gegen Leerzeichen-/Zeilenumbruch-Unterschiede."""
    return re.compile(r"\s+".join(re.escape(teil) for teil in absatz.split()))


def platzhalter_einsetzen(text: str) -> tuple[str, bool]:
    """Ersetzt im Textblock den Standard-Zahlungsabsatz (Textvergleich ohne
    Leerzeichen-/Umbruch-Unterschiede) durch den Platzhalter. (neuer Text,
    ersetzt?) – ein Block, der den Platzhalter schon trägt, bleibt unverändert."""
    text = text or ""
    if PLATZHALTER in text:
        return text, False
    neu, anzahl = _absatz_muster(STANDARD_ABSATZ).subn(PLATZHALTER, text, count=1)
    return neu, anzahl > 0


def text_einsetzen(nachtext: str, text: str) -> str:
    """Rendering: Platzhalter durch den Text der Zahlungsbedingung ersetzen."""
    return (nachtext or "").replace(PLATZHALTER, (text or "").strip())


def bloecke_ohne_platzhalter(session: Session) -> list[str]:
    """Namen der (nicht leeren) Nachtext-Blöcke ohne {zahlungsbedingungen} –
    dort druckt das Profil weiter seinen festen Text (Hinweis in der Parametrierung)."""
    return [b.name for b in (session.query(Textblock)
                             .filter(Textblock.art == "nachtext").order_by(Textblock.name))
            if (b.text or "").strip() and PLATZHALTER not in b.text]


# --- Migration (migrate.py) ------------------------------------------------------

def migration_v30_zahlung(session: Session) -> list[str]:
    """Idempotent (zweiter Lauf = keine Meldung): (1) die drei Einträge, falls die
    Tabelle leer ist; (2) in JEDEM Nachtext-Textblock (alle Profile WP/PV/KL) den
    Standardabsatz durch {zahlungsbedingungen} ersetzen – Blöcke ohne den
    wörtlichen Absatz werden beim Erstlauf mit Namen gemeldet (dort trägt der
    Innendienst den Platzhalter von Hand nach); (3) Parameter bza_kosten_puffer_prozent
    und lieferschein_folgepositionen anlegen, falls die Zeile fehlt."""
    meldungen: list[str] = []
    if session.query(Zahlungsbedingung).count() == 0:
        for lauf, (schluessel, name, text) in enumerate(STANDARD_EINTRAEGE, 1):
            session.add(Zahlungsbedingung(schluessel=schluessel, name=name, text=text,
                                          sortierung=lauf, aktiv=True, standard=lauf == 1))
        session.flush()
        meldungen.append("v30: 3 Zahlungsbedingungen angelegt (Standard · 50 % am "
                         "Montagetag · 80 % Anzahlung, 2 % Skonto)")
    umgestellt: list[str] = []
    offen: list[str] = []
    for block in (session.query(Textblock).filter(Textblock.art == "nachtext")
                  .order_by(Textblock.id)):
        if not (block.text or "").strip() or PLATZHALTER in block.text:
            continue
        neu, ersetzt = platzhalter_einsetzen(block.text)
        if ersetzt:
            block.text = neu
            umgestellt.append(block.name)
        else:
            offen.append(block.name)
    if umgestellt:
        meldungen.append(f"v30: Platzhalter {PLATZHALTER} in {len(umgestellt)} Nachtext-"
                         f"Block/Blöcken eingesetzt: " + ", ".join(f"„{n}“" for n in umgestellt))
    erstlauf = einstellung_holen(session, MARKER_NACHTEXTE, "") != "erledigt"
    if offen and erstlauf:
        meldungen.append("v30: Standard-Zahlungsabsatz NICHT wörtlich gefunden – Platzhalter "
                         f"{PLATZHALTER} von Hand nachtragen (Parametrierung → Angebotsprofile "
                         "→ Textblöcke): " + ", ".join(f"„{n}“" for n in offen))
    if erstlauf:
        einstellung_setzen(session, MARKER_NACHTEXTE, "erledigt")
    for name, wert in PARAMETER_STANDARD:
        if session.query(Einstellung).filter(Einstellung.name == name).first() is None:
            einstellung_setzen(session, name, wert)
            meldungen.append(f"v30: Parameter {name} = {wert} angelegt")
    return meldungen
