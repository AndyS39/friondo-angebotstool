# Kombi-Versand (v10, Phase 61): mehrere versandfertige Angebote eines
# Vorgangs in EINER Mail mit mehreren PDF-Anhängen. Wählbar sind Tool-Angebote
# im Status Entwurf/Versand vorbereitet sowie externe TAIFUN-Einträge mit
# hinterlegtem PDF. Broschüren werden über alle Angebote dedupliziert; die
# Profil-/Versandregeln des Vorgangs (Enni-CC, SWD-Empfänger leer, Mehrfach-
# BCC) gelten wie beim Einzelversand.

from pathlib import Path

from sqlalchemy.orm import Session

from app.models import Angebot, Vorgang, einstellung_holen

GEWERKE_ARTIKEL_START = "014,015,016,017,104,Z22,152,Z23"


def gewerke_artikel(session: Session) -> list[str]:
    """Parametrierungs-Liste „gewerkeübergreifende Artikel" (Phase 61)."""
    roh = einstellung_holen(session, "gewerke_artikel", GEWERKE_ARTIKEL_START)
    return [t.strip() for t in roh.split(",") if t.strip()]


def waehlbar(angebot: Angebot) -> tuple[bool, str]:
    """Ist das Angebot im Kombi-Versand wählbar? (ok, Begründung)."""
    if angebot.status == "Überholt":
        return False, "Überholt – durch eine neue Version ersetzt."
    if angebot.extern:
        if angebot.status not in ("Versendet (extern)", "Angenommen"):
            return False, f"TAIFUN-Eintrag im Status „{angebot.status}“."
        if not angebot.extern_pdf_pfad or not Path(angebot.extern_pdf_pfad).exists():
            return False, ("Ohne hinterlegtes PDF nicht wählbar – bitte das "
                           "TAIFUN-Angebots-PDF am Eintrag hochladen.")
        return True, ""
    if angebot.status not in ("Entwurf", "Versand vorbereitet"):
        return False, f"Status „{angebot.status}“ – nur Entwurf/Versand vorbereitet."
    return True, ""


def doppelte_artikel(angebote: list[Angebot]) -> list[str]:
    """Artikelnummern, die in MEHREREN Tool-Angeboten voll berechnet sind
    (EP/bauseits/Alternativ zählen nicht; TAIFUN-PDFs sind nicht prüfbar)."""
    vorkommen: dict[str, set[int]] = {}
    for angebot in angebote:
        if angebot.extern:
            continue
        for p in angebot.positionen:
            if p.ep_flag or p.bauseits or p.alternativ or not p.pos_nr:
                continue
            vorkommen.setdefault(p.pos_nr, set()).add(angebot.id)
    return sorted(nr for nr, ids in vorkommen.items() if len(ids) > 1)


def gewerke_hinweise(session: Session, vorgang: Vorgang,
                     angebote: list[Angebot]) -> list[str]:
    """Fachlicher Hinweis am Vorgang (Phase 61): Mehr-Sparten-Vorgang und ein
    gewerkeübergreifender Artikel ist in einem Tool-Angebot VOLL berechnet."""
    aktive = [a for a in angebote if a.status != "Überholt"]
    sparten = {a.konfigurator_typ or "WP" for a in aktive}
    if len(sparten) < 2:
        return []
    liste = set(gewerke_artikel(session))
    hinweise = []
    for angebot in aktive:
        if angebot.extern:
            continue
        voll = sorted({p.pos_nr for p in angebot.positionen
                       if p.pos_nr in liste
                       and not (p.ep_flag or p.bauseits or p.alternativ)})
        if voll:
            hinweise.append(
                f"{angebot.nummer}: Pos. {', '.join(voll)} voll berechnet – "
                "prüfen: ggf. ins PV-Angebot verlagern oder Alternativ-"
                "Kennzeichen setzen (Förder-/USt-Optimierung).")
    return hinweise


def pdf_fuer(session: Session, angebot: Angebot) -> Path:
    """Angebots-PDF für den Kombi-Anhang: Tool-Angebote frisch erzeugt,
    TAIFUN-Einträge aus dem hinterlegten Upload."""
    if angebot.extern:
        return Path(angebot.extern_pdf_pfad)
    from app import pdf_export
    return pdf_export.pdf_fuer_angebot(session, angebot)
