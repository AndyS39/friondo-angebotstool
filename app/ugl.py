# UGL-Bestellung (v15 Phase 80; V4 / PLAN_PROJ_V4 Phase 93.2 formatgenau):
# erzeugt eine UGL-4.0-Datei (Anfrageart BE = Lieferauftrag Handwerk →
# Großhandel) aus den Auftragspositionen × Blatt "Stücklisten".
#
# Format laut "UGL Version 4 – Beschreibung Datenaustausch" (Feldtabelle in
# docs/ugl-format.md):
#   · feste Satzlänge 200 Byte + CR/LF; numerische Felder rechtsbündig mit
#     führenden Nullen, alphanumerische linksbündig mit Leerzeichen
#   · Satzfolge KOP → ADR → (POA + POT) … → END
#   · Preise/Rabatte bleiben 0 (der Großhandel füllt sie in der AB)
#   · Zeichensatz "deutsche Sonderzeichen wie Datanorm 4.0" → Codepage 850
#     (ANNAHME – beim ersten Test mit Collin abgleichen)
# Upload in GC Online Plus erfolgt manuell; IDS-Connect bleibt ein
# vorbereiteter Schalter (Parameter ugl_ids_aktiv – ohne Funktion).

from datetime import datetime, timedelta

from app import projektierung as kern

SATZ_LAENGE = 200
ZEICHENSATZ = "cp850"


def werktage_zurueck(datum: datetime, tage: int) -> datetime:
    """N Werktage (Mo-Fr) vor dem Datum – Lieferdatum = Montagebeginn - 3."""
    ergebnis = datum
    rest = tage
    while rest > 0:
        ergebnis -= timedelta(days=1)
        if ergebnis.weekday() < 5:
            rest -= 1
    return ergebnis


# --- Feld-Formatierung ------------------------------------------------------------

def alpha(wert, laenge: int) -> str:
    """Alphanumerisch: linksbündig, Leerzeichen auffüllen, abschneiden."""
    text = " ".join(str(wert or "").split())
    return text[:laenge].ljust(laenge)


def numerisch(wert, laenge: int, nachkomma: int = 0) -> str:
    """Numerisch: rechtsbündig mit führenden Nullen, Komma implizit
    (Menge 11 Stellen/3 Nachkomma: 2,5 → 00000002500)."""
    zahl = int(round(float(wert or 0) * (10 ** nachkomma)))
    return str(max(0, zahl)).rjust(laenge, "0")[-laenge:]


def satz(*felder: str) -> str:
    text = "".join(felder)
    if len(text) > SATZ_LAENGE:
        raise ValueError(f"UGL-Satz zu lang ({len(text)} > {SATZ_LAENGE})")
    return text.ljust(SATZ_LAENGE)


def kop_satz(kundennummer, lieferantennummer, bestellnummer, auftragstext,
             lieferdatum: datetime, sachbearbeiter, belegdatum: datetime) -> str:
    return satz("KOP",                                   # 1–3
                alpha(kundennummer, 10),                 # 4–13 Kundennr. beim GH
                alpha(lieferantennummer, 10),            # 14–23 Lieferantennr. beim HW
                "BE",                                    # 24–25 Anfrageart Lieferauftrag
                alpha(bestellnummer, 15),                # 26–40 Anfragenummer HW
                alpha(auftragstext, 50),                 # 41–90 Kundenauftragstext
                alpha("", 15),                           # 91–105 Vorgangsnr. GH
                lieferdatum.strftime("%Y%m%d"),          # 106–113 Lieferdatum
                "EUR",                                   # 114–116 Währung
                "04.00",                                 # 117–121 Version
                alpha(sachbearbeiter, 40),               # 122–161 Sachbearbeiter
                belegdatum.strftime("%Y%m%d"))           # 162–169 Dokumentdatum


def adr_satz(name1, name2, name3, strasse, plz, ort, land="") -> str:
    return satz("ADR", alpha(name1, 30), alpha(name2, 30), alpha(name3, 30),  # 4–93
                alpha(strasse, 30),                      # 94–123
                alpha(land, 3),                          # 124–126
                alpha(plz, 6),                           # 127–132
                alpha(ort, 30))                          # 133–162


def poa_satz(positionsnummer: int, artikelnummer, menge: float,
             bezeichnung1="", bezeichnung2="", mengeneinheit="ST") -> str:
    return satz("POA",
                numerisch(positionsnummer, 10),          # 4–13 Pos.-Nr. HW
                numerisch(0, 10),                        # 14–23 Pos.-Nr. GH
                alpha(artikelnummer, 15),                # 24–38 Artikelnummer
                numerisch(menge, 11, 3),                 # 39–49 Menge (11,3)
                alpha(bezeichnung1, 40),                 # 50–89 Bezeichnung 1
                alpha(bezeichnung2, 40),                 # 90–129 Bezeichnung 2
                numerisch(0, 11),                        # 130–140 Preis (leer)
                "0",                                     # 141 Preiseinheit
                numerisch(0, 11),                        # 142–152 Netto-Positionswert
                numerisch(0, 5),                         # 153–157 Rabatt 1
                numerisch(0, 5),                         # 158–162 Rabatt 2
                alpha("", 18),                           # 163–180 LV-Nummer
                " ",                                     # 181 Alternativ-Kz.
                "H",                                     # 182 Positionstyp Haupt
                " ",                                     # 183 Vorbehalt
                alpha((mengeneinheit or "ST").upper(), 3),  # 184–186 Mengeneinheit
                " ",                                     # 187 Preis-Kz.
                " ")                                     # 188 Lager-Kz.


def pot_satz(positionsnummer: int, text1="", text2="", text3="") -> str:
    return satz("POT", numerisch(positionsnummer, 10), numerisch(0, 10),  # 4–23
                alpha(text1, 40), alpha(text2, 40), alpha(text3, 40),     # 24–143
                alpha("", 18))                                            # 144–161


def end_satz(*texte: str) -> str:
    felder = [alpha(t, 40) for t in (list(texte) + ["", "", "", ""])[:4]]
    return satz("END", *felder)                          # 4–163 Zusatztexte


# --- Material aus Auftrag × Stückliste -----------------------------------------------

def material_fuer_gewerk(session, gewerk) -> tuple[list[dict], list[str]]:
    """(Materialzeilen, Positionen ohne Zuordnung) aus Auftrag × Stückliste.
    Z-Positionen (Arbeitspakete) und EP/bauseits/alternativ zählen nicht.
    Jede Materialzeile nennt ihre Herkunftspositionen (Vorschau, POT-Text)."""
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
                "lieferant": teil.lieferant, "menge": 0.0,
                "einheit": teil.mengeneinheit or "ST", "positionen": []})
            eintrag["menge"] += menge
            if nr not in eintrag["positionen"]:
                eintrag["positionen"].append(nr)
    return list(zeilen.values()), fehlend


def lieferdatum_vorschlag(session, gewerk) -> datetime | None:
    termin = kern.terminstatus(session, gewerk).get("termin")
    if termin is not None and termin.beginn:
        return werktage_zurueck(termin.beginn, 3)
    return None


def bestellungen(session, gewerk) -> list:
    from app.models import UglBestellung
    return (session.query(UglBestellung)
            .filter(UglBestellung.gewerk_id == gewerk.id)
            .order_by(UglBestellung.nr).all())


def lieferadresse_zeilen(session, projekt, kunde, art: str) -> dict:
    """Name/Straße/PLZ/Ort für den ADR-Satz."""
    if art == "lager":
        zeilen = [z.strip() for z in kern.parameter_holen(
            session, "lager_adresse", "Friondo GmbH Lager").splitlines() if z.strip()]
        name = zeilen[0] if zeilen else "Friondo GmbH"
        strasse = zeilen[1] if len(zeilen) > 1 else ""
        plz, _, ort = (zeilen[2] if len(zeilen) > 2 else "").partition(" ")
        return {"name": name, "strasse": strasse, "plz": plz, "ort": ort}
    return {"name": f"Baustelle {kunde.anzeige_name}" if kunde else "Baustelle",
            "strasse": projekt.ausfuehrung_strasse if projekt else "",
            "plz": projekt.ausfuehrung_plz if projekt else "",
            "ort": projekt.ausfuehrung_ort if projekt else ""}


def ugl_erzeugen(session, gewerk, lieferdatum: datetime | None = None,
                 lieferadresse: str = "", bemerkung: str = "",
                 sachbearbeiter: str = "", nr: int | None = None,
                 jetzt: datetime | None = None
                 ) -> tuple[bytes | None, str, list[str], str]:
    """(dateiinhalt, dateiname, fehlende Zuordnungen, fehler).
    nr = laufende Bestellung im Gewerk (1 = Erstbestellung, ab 2 →
    Nachbestellung, Dateiname/Anfragenummer mit "-2" …)."""
    from app.models import Kunde, Projekt
    projekt = session.get(Projekt, gewerk.projekt_id)
    kunde = session.get(Kunde, projekt.kunde_id) if projekt else None
    zeilen, fehlend = material_fuer_gewerk(session, gewerk)
    if not zeilen:
        return None, "", fehlend, ("Keine Materialzeilen – Stücklisten-Pflege "
                                   "prüfen (Positionen ohne Zuordnung unten).")
    kundennummer = kern.parameter_holen(session, "collin_kundennummer", "")
    if not kundennummer:
        return None, "", fehlend, ("Collin-Kundennummer fehlt – bitte in den "
                                   "Projektierung-Einstellungen hinterlegen.")
    jetzt = jetzt or datetime.now()
    if lieferdatum is None:
        lieferdatum = lieferdatum_vorschlag(session, gewerk) or jetzt + timedelta(days=7)
    art = lieferadresse or kern.parameter_holen(session, "ugl_lieferadresse",
                                                "ausfuehrung")
    if nr is None:
        nr = len(bestellungen(session, gewerk)) + 1
    pr = projekt.nummer if projekt else "PR"
    bestellnummer = pr + (f"-{nr}" if nr > 1 else "")
    auftragstext = " ".join(t for t in [
        f"Kommission {pr}", "Nachbestellung" if nr > 1 else "",
        kunde.nachname if kunde else "", gewerk.sparte] if t)
    adresse = lieferadresse_zeilen(session, projekt, kunde, art)
    saetze = [
        kop_satz(kundennummer,
                 kern.parameter_holen(session, "collin_lieferantennummer", ""),
                 bestellnummer, auftragstext, lieferdatum,
                 sachbearbeiter or "Friondo Projektierung", jetzt),
        adr_satz(adresse["name"], f"Kommission {pr}",
                 bemerkung[:30] if bemerkung else "",
                 adresse["strasse"], adresse["plz"], adresse["ort"]),
    ]
    for lfd, zeile in enumerate(zeilen, 1):
        bezeichnung = zeile["bezeichnung"] or ""
        saetze.append(poa_satz(lfd * 10, zeile["artnr"], zeile["menge"],
                               bezeichnung[:40], bezeichnung[40:80],
                               zeile["einheit"]))
        saetze.append(pot_satz(lfd * 10, "Angebotsposition "
                               + ", ".join(zeile["positionen"])))
    saetze.append(end_satz(("Nachbestellung " if nr > 1 else "Bestellung ") + bestellnummer,
                           bemerkung[:40],
                           bemerkung[40:80]))
    inhalt = ("\r\n".join(saetze) + "\r\n").encode(ZEICHENSATZ, errors="replace")
    return inhalt, f"{bestellnummer}.ugl", fehlend, ""
