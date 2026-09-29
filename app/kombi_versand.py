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


def _titel_schluessel(position) -> str:
    """v13-PV: gleiche Leistung unter verschiedenen Nummern erkennen (WP-Pos. 104
    und PV123 heißen beide „Zähler-Komplettschrank 2-Feld inkl. Anbindung“) –
    normalisierte erste Zeile von Bezeichnung bzw. Beschreibung."""
    import re
    text = position.bezeichnung or ""
    if not text:
        zeilen = [z.strip() for z in (position.beschreibung or "").splitlines() if z.strip()]
        if len(zeilen) > 1 and zeilen[0].lower().startswith("(optionale position"):
            zeilen = zeilen[1:]
        text = zeilen[0] if zeilen else ""
    return re.sub(r"\s+", " ", text).strip().lower()


def doppelte_artikel(angebote: list[Angebot]) -> list[str]:
    """Artikelnummern, die in MEHREREN Tool-Angeboten voll berechnet sind
    (EP/bauseits/Alternativ zählen nicht; TAIFUN-PDFs sind nicht prüfbar).
    v13-PV: WP- und PV-Angebote werden zusätzlich über die Bezeichnung
    verglichen (Ausgabe dann „104/PV123“)."""
    vorkommen: dict[str, dict[int, str]] = {}
    for angebot in angebote:
        if angebot.extern:
            continue
        for p in angebot.positionen:
            if p.ep_flag or p.bauseits or p.alternativ or not p.pos_nr:
                continue
            titel = _titel_schluessel(p)
            schluessel = f"t:{titel}" if titel else f"n:{p.pos_nr}"
            vorkommen.setdefault(schluessel, {}).setdefault(angebot.id, p.pos_nr)
    doppelt = []
    for ids in vorkommen.values():
        if len(ids) > 1:
            doppelt.append("/".join(sorted(set(ids.values()))))
    return sorted(set(doppelt))


def gewerke_hinweise(session: Session, vorgang: Vorgang,
                     angebote: list[Angebot]) -> list[str]:
    """Fachlicher Hinweis am Vorgang (Phase 61): Mehr-Sparten-Vorgang und ein
    gewerkeübergreifender Artikel ist in einem Tool-Angebot VOLL berechnet."""
    aktive = [a for a in angebote if a.status != "Überholt"]
    sparten = {a.konfigurator_typ or "WP" for a in aktive}
    if len(sparten) < 2:
        return []
    liste = set(gewerke_artikel(session))
    # v13-PV: Listen-Artikel auch über die Bezeichnung erkennen (PV-Angebote
    # tragen eigene Nummern PV…, z. B. PV123 = WP-Pos. 104)
    from app.models import Artikel
    listen_titel = set()
    for artikel in session.query(Artikel).filter(Artikel.pos_nr.in_(liste)):
        listen_titel.add(_titel_schluessel(artikel))
    listen_titel.discard("")
    hinweise = []
    for angebot in aktive:
        if angebot.extern:
            continue
        voll = sorted({p.pos_nr for p in angebot.positionen
                       if (p.pos_nr in liste or _titel_schluessel(p) in listen_titel)
                       and not (p.ep_flag or p.bauseits or p.alternativ)})
        if voll:
            eigene = angebot.konfigurator_typ or "WP"
            andere = sorted(s for s in sparten if s != eigene)
            ziel = " bzw. ".join(f"{s}-Angebot" for s in andere) or "andere Angebot"
            hinweise.append(
                f"{angebot.nummer} ({eigene}): Pos. {', '.join(voll)} voll berechnet – "
                f"prüfen: ggf. ins {ziel} verlagern oder Alternativ-"
                "Kennzeichen setzen (Förder-/USt-Optimierung).")
    return hinweise


def pdf_fuer(session: Session, angebot: Angebot) -> Path:
    """Angebots-PDF für den Kombi-Anhang: Tool-Angebote frisch erzeugt,
    TAIFUN-Einträge aus dem hinterlegten Upload."""
    if angebot.extern:
        return Path(angebot.extern_pdf_pfad)
    from app import pdf_export
    return pdf_export.pdf_fuer_angebot(session, angebot)
