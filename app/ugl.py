# UGL-Bestellung (v15, Phase 80): erzeugt eine UGL-Datei (Satzarten
# KOP/ADR/POA/END, feste Satzlänge 200 Byte, Anfrageart BE) aus den
# Auftragspositionen × Blatt "Stücklisten". Upload in GC Online Plus
# erfolgt manuell; IDS-Connect ist als späterer Schalter vorbereitet
# (Parameter ugl_ids_aktiv – heute ohne Funktion).
# Feldbelegung vereinfacht nach UGL 4.0 – beim ersten echten Upload mit
# Collin/GC Online abgleichen (docs/projektierung-entscheidungen.md).

from datetime import datetime, timedelta

from app import projektierung as kern

SATZ_LAENGE = 200


def werktage_zurueck(datum: datetime, tage: int) -> datetime:
    """N Werktage (Mo-Fr) vor dem Datum – Lieferdatum = Montagebeginn - 3."""
    ergebnis = datum
    rest = tage
    while rest > 0:
        ergebnis -= timedelta(days=1)
        if ergebnis.weekday() < 5:
            rest -= 1
    return ergebnis


def _satz(*felder: tuple[str, int]) -> str:
    """Felder (wert, laenge) links bündig auf die Satzlänge auffüllen."""
    text = "".join(str(wert)[:laenge].ljust(laenge) for wert, laenge in felder)
    return text[:SATZ_LAENGE].ljust(SATZ_LAENGE)


def material_fuer_gewerk(session, gewerk) -> tuple[list[dict], list[str]]:
    """(Materialzeilen, Positionen ohne Zuordnung) aus Auftrag × Stückliste.
    Z-Positionen (Arbeitspakete) und EP/bauseits/alternativ zählen nicht."""
    from app import projektierung_logik
    from app.models import Angebot
    logik = projektierung_logik.hole_logik(session)
    angebot = session.get(Angebot, gewerk.angebot_id) if gewerk.angebot_id else None
    zeilen: dict[str, dict] = {}
    fehlend: list[str] = []
    if angebot is None or angebot.extern:
        return [], []
    for position in angebot.positionen:
        nr = (position.pos_nr or "").strip()
        if not nr or nr.upper().startswith("Z"):
            continue
        if position.ep_flag or position.bauseits or position.alternativ:
            continue
        stueckliste = logik.stuecklisten.get(nr)
        if not stueckliste:
            fehlend.append(f"{nr} · {position.bezeichnung}")
            continue
        for teil in stueckliste:
            menge = (position.menge or 1) * teil.menge_je_einheit
            eintrag = zeilen.setdefault(teil.lieferant_artnr, {
                "artnr": teil.lieferant_artnr, "bezeichnung": teil.bezeichnung,
                "lieferant": teil.lieferant, "menge": 0.0})
            eintrag["menge"] += menge
    return list(zeilen.values()), fehlend


def ugl_erzeugen(session, gewerk) -> tuple[bytes | None, str, list[str], str]:
    """(dateiinhalt, dateiname, fehlende Zuordnungen, fehler)."""
    from app.models import Projekt
    projekt = session.get(Projekt, gewerk.projekt_id)
    zeilen, fehlend = material_fuer_gewerk(session, gewerk)
    if not zeilen:
        return None, "", fehlend, ("Keine Materialzeilen – Stücklisten-Blatt "
                                   "prüfen (Positionen ohne Zuordnung unten).")
    kundennummer = kern.parameter_holen(session, "collin_kundennummer", "")
    if not kundennummer:
        return None, "", fehlend, ("Collin-Kundennummer fehlt – bitte in der "
                                   "Parametrierung hinterlegen.")
    ts = kern.terminstatus(session, gewerk)
    termin = ts.get("termin")
    if termin is not None and termin.beginn:
        lieferdatum = werktage_zurueck(termin.beginn, 3)
    else:
        lieferdatum = datetime.now() + timedelta(days=7)
    # Lieferadresse: Ausführungsort oder Lager (Parametrierung)
    if kern.parameter_holen(session, "ugl_lieferadresse", "ausfuehrung") == "lager":
        adresse = kern.parameter_holen(session, "lager_adresse",
                                       "Friondo GmbH Lager")
        adresszeilen = [z.strip() for z in adresse.splitlines() if z.strip()]
    else:
        adresszeilen = [t for t in [
            projekt.ausfuehrung_strasse,
            f"{projekt.ausfuehrung_plz} {projekt.ausfuehrung_ort}".strip()]
            if t] or ["Ausführungsadresse fehlt"]
    saetze = [
        # Kopfsatz: Satzart, Version, Kundennummer, Anfrageart BE,
        # Belegnummer (PR-Nummer), Datum, Lieferdatum
        _satz(("KOP", 3), ("04.00", 5), (kundennummer, 10), ("BE", 2),
              (projekt.nummer if projekt else "", 15),
              (datetime.now().strftime("%Y%m%d"), 8),
              (lieferdatum.strftime("%Y%m%d"), 8)),
        # Adresssatz: Lieferanschrift (Name/Straße/Ort)
        _satz(("ADR", 3), ("Friondo GmbH", 40),
              (adresszeilen[0] if adresszeilen else "", 40),
              (adresszeilen[1] if len(adresszeilen) > 1 else "", 40),
              (adresszeilen[2] if len(adresszeilen) > 2 else "", 40)),
    ]
    for lfd, zeile in enumerate(zeilen, 1):
        menge = f"{zeile['menge']:.2f}".replace(".", ",")
        # Positionssatz: Satzart, lfd. Nr, Artikelnummer Lieferant, Menge,
        # Einheit, Bezeichnung
        saetze.append(_satz(("POA", 3), (f"{lfd:04d}", 4),
                            (zeile["artnr"], 20), (menge, 11), ("Stk", 4),
                            (zeile["bezeichnung"], 70)))
    saetze.append(_satz(("END", 3), (f"{len(saetze) + 1:06d}", 6)))
    inhalt = "\r\n".join(saetze).encode("latin-1", errors="replace")
    dateiname = f"UGL_{(projekt.nummer if projekt else 'PR')}_{datetime.now():%Y%m%d_%H%M}.ugl"
    return inhalt, dateiname, fehlend, ""
