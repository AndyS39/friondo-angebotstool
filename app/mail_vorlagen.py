# E-Mail-Vorlagen (Phase 30): Standard-Vorlage (Betreff + Text) plus optionale
# Vorlage je Außendienstler. Beim Versand zieht das Tool die Vorlage des AD des
# Vorgangs (Erfassung → Benutzer), sonst den Standard. Ablage in der Tabelle
# einstellungen: mail_vorlage_standard_betreff/_text bzw.
# mail_vorlage_<benutzer_id>_betreff/_text.
# v27-Nachtrag 2: zusätzlich eine Vorlage je Sparte WP / PV / KL / WB
# (mail_vorlage_sparte_<SPARTE>_betreff/_text). Reihenfolge beim Versand:
# Vorlage des Außendienstlers → Sparten-Vorlage des Angebots → Standard-Vorlage.
# migration_sparten() legt die Sparten-Vorlagen einmalig aus der Standard-
# Vorlage an (migrate.py); der Kombi-Versand behält seine eigene Vorlage.

import re
from datetime import timedelta

from app.models import (Angebot, Benutzer, Erfassung, Kunde, einstellung_holen,
                        einstellung_setzen)

# Bisheriger fester Text (Phase 17) – wird per migrate.py zur Standard-Vorlage
STANDARD_BETREFF = "Ihr Wärmepumpen-Angebot {angebotsnummer} der Friondo GmbH"
STANDARD_TEXT = (
    "{briefanrede}\n\n"
    "vielen Dank für Ihr Interesse an einer Wärmepumpe der Friondo GmbH.\n\n"
    "Anbei erhalten Sie Ihr individuelles Angebot {angebotsnummer} als PDF-Datei. "
    "Wir halten uns freibleibend 30 Tage an dieses Angebot gebunden "
    "(gültig bis {gueltig_bis}).\n\n"
    "Bei Fragen stehen wir Ihnen jederzeit gerne zur Verfügung – telefonisch unter "
    "0203 - 3965 710 oder per E-Mail an info@friondo.de. Ihr persönlicher "
    "Ansprechpartner vor Ort ist {vertriebler}.\n\n"
    "Mit freundlichen Grüßen\n"
    "Ihr Friondo-Team\n\n"
    "Friondo GmbH · Arnold-Overbeck-Str. 63-65 · 47139 Duisburg\n"
    "www.friondo.de")

PLATZHALTER = [
    ("{briefanrede}", "Briefanrede, z. B. „Sehr geehrte Frau Beispiel,“ (identisch mit dem PDF-Vortext)"),
    ("{anrede}", "wie {briefanrede} (Kurzform, aus v5-Vorlagen)"),
    ("{vorname}", "Vorname des Kunden"),
    ("{nachname}", "Nachname des Kunden"),
    ("{angebotsnummer}", "Angebotsnummer, z. B. AN-C-261015"),
    ("{endbetrag}", "Endbetrag brutto (nach Rabatt), z. B. 34.758,95 €"),
    ("{eigenanteil}", "Eigenanteil nach KfW-Förderung (nur WP – bei PV/KL leer)"),
    ("{foerderung}", "voraussichtliche KfW-Förderung (nur WP – bei PV/KL leer)"),
    ("{gueltig_bis}", "Angebotsdatum + 30 Tage"),
    ("{vertriebler}", "Name des Außendienstlers des Vorgangs"),
    ("{absender}", "Name des angemeldeten Innendienst-Mitarbeiters"),
]

_MUSTER = re.compile(r"\{[a-z_]+\}")

# v27-Nachtrag 2: Sparten-Vorlagen – Reiter in Parametrierung → E-Mail-Vorlagen
SPARTEN = ("WP", "PV", "KL", "WB")
SPARTEN_NAMEN = {"WP": "Wärmepumpe", "PV": "Photovoltaik", "KL": "Klimaanlage",
                 "WB": "Wallbox"}
MIGRATION_MARKER = "migration_nachtrag2_sparten"
MIGRATION_MARKER_WP = "migration_nachtrag2_sparten_wp"   # Nachtrag 08.10.2026: WP-Kopie entfernt
# Platzhalter ohne Wert bei PV/KL (kein KfW-Block): die Migration entfernt die
# Sätze, in denen sie stehen, und leert übrige Vorkommen
NUR_WP_PLATZHALTER = ("{eigenanteil}", "{foerderung}")
# Wortersetzungen je Sparte beim Ableiten aus der Standard-Vorlage
# (zusammengesetzte Begriffe zuerst; „Wärmepumpen“ → Plural folgt aus dem Stamm)
SPARTEN_ERSETZUNGEN = {
    "KL": (("Wärmepumpenangebot", "Klimaanlagenangebot"),
           ("Wärmepumpen-Angebot", "Klimaanlagen-Angebot"),
           ("Wärmepumpe", "Klimaanlage")),
    "PV": (("Wärmepumpenangebot", "PV-Angebot"),
           ("Wärmepumpen-Angebot", "PV-Angebot"),
           ("Wärmepumpen", "PV-Anlagen"),
           ("Wärmepumpe", "PV-Anlage")),
}


def sparten_schluessel(sparte: str) -> str:
    return f"mail_vorlage_sparte_{(sparte or '').upper()}"


KOMBI_BETREFF = "Ihre Angebote {angebotsnummern} – Friondo GmbH"
KOMBI_TEXT = (
    "{briefanrede}\n\n"
    "vielen Dank für Ihr Interesse an unseren Energielösungen. Wie besprochen "
    "erhalten Sie anbei Ihre Angebote – jeweils als eigenes PDF:\n\n"
    "{angebotsliste}\n\n"
    "Die Angebote sind einzeln beauftragbar; Details und Hinweise entnehmen "
    "Sie bitte den beigefügten Unterlagen.\n\n"
    "Bei Fragen sind wir gerne für Sie da.\n\n"
    "Mit freundlichen Grüßen\n{absender}\nFriondo GmbH\n\n"
    "Ihr Ansprechpartner im Außendienst: {vertriebler}")


def kombi_vorlage_laden(session) -> tuple[str, str]:
    """v10 (Phase 61): Kombi-Vorlage aus der Parametrierung, sonst Standard."""
    from app.models import einstellung_holen
    return (einstellung_holen(session, "kombi_vorlage_betreff", "") or KOMBI_BETREFF,
            einstellung_holen(session, "kombi_vorlage_text", "") or KOMBI_TEXT)


def angebotsliste_text(session, angebote) -> str:
    """{angebotsliste}: je Zeile Sparte, Angebotsnummer und Endbetrag; bei WP
    zusätzlich der Eigenanteil nach Förderung. Bewusst KEINE Gesamtsumme."""
    from app.pdf_export import _euro_betrag
    zeilen = []
    for angebot in angebote:
        kunde = None
        werte = werte_fuer_angebot(session, angebot, kunde)
        sparte = angebot.konfigurator_typ or "WP"
        nummer = (angebot.taifun_nummer or angebot.nummer) if angebot.extern else angebot.nummer
        zeile = (f"• {sparte}-Angebot {nummer} – "
                 f"Endbetrag: {_euro_betrag(angebot.summen()['endbetrag'])} €")
        if sparte == "WP" and not angebot.extern and werte.get("eigenanteil", "–") != "–":
            zeile += f" (Eigenanteil nach Förderung: {werte['eigenanteil']})"
        zeilen.append(zeile)
    return "\n".join(zeilen)


def kombi_mail_fuer_vorgang(session, angebote, kunde,
                            absender_name: str = "") -> tuple[str, str]:
    """Fertiger Betreff + HTML-Text für den Kombi-Versand (Phase 61)."""
    betreff, text = kombi_vorlage_laden(session)
    basis = werte_fuer_angebot(session, angebote[0], kunde, absender_name)
    basis["angebotsnummern"] = ", ".join(
        (a.taifun_nummer or a.nummer) if a.extern else a.nummer for a in angebote)
    basis["angebotsliste"] = angebotsliste_text(session, angebote)
    return (einsetzen(betreff, basis), einsetzen_html(als_html(text), basis))


def ist_html(text: str) -> bool:
    return "<" in text and ">" in text


def als_html(text: str) -> str:
    """Klartext-Vorlage (v5) nach HTML wandeln: Absätze als <p>, Zeilen als
    <br>; Platzhalter bleiben unangetastet. HTML bleibt HTML (v6)."""
    import html as html_modul
    if ist_html(text):
        return text
    absaetze = [a for a in text.split("\n\n")]
    teile = []
    for absatz in absaetze:
        zeilen = [html_modul.escape(z) for z in absatz.split("\n")]
        teile.append("<p>" + "<br>".join(zeilen) + "</p>")
    return "".join(teile)


def einsetzen_html(vorlage_html: str, werte: dict[str, str]) -> str:
    """Platzhalter in einer HTML-Vorlage ersetzen – Werte werden escaped."""
    import html as html_modul
    return _MUSTER.sub(
        lambda m: html_modul.escape(werte.get(m.group(0)[1:-1], m.group(0))),
        vorlage_html)


def briefanrede(kunde: Kunde | None) -> str:
    """Gemeinsamer Baustein (v5): Kunde.briefanrede – im PDF-Vortext und als
    Platzhalter {briefanrede}/{anrede} in den Mail-Vorlagen identisch."""
    if kunde is None:
        return "Sehr geehrte Damen und Herren,"
    return kunde.briefanrede


def vertriebler_fuer_angebot(session, angebot: Angebot) -> Benutzer | None:
    """AD des Vorgangs: über die verknüpfte Erfassung; bei manuellen Angeboten
    ohne Erfassung über angebot.vertriebler_id (v5-Nachtrag, vom Innendienst
    im Editor änderbar). Steuert CC und die Vorlagenwahl."""
    erfassung = (session.query(Erfassung)
                 .filter(Erfassung.angebot_id == angebot.id).first())
    if erfassung is not None:
        return session.get(Benutzer, erfassung.benutzer_id)
    if angebot.vertriebler_id:
        return session.get(Benutzer, angebot.vertriebler_id)
    return None


def werte_fuer_angebot(session, angebot: Angebot, kunde: Kunde | None,
                       absender_name: str = "") -> dict[str, str]:
    """Alle Platzhalter-Werte für ein konkretes Angebot."""
    from app import kfw
    from app import logik as logik_modul
    from app.pdf_export import _euro_betrag
    import json

    summen = angebot.summen()
    foerderung = eigenanteil = ""
    kfw_daten = json.loads(angebot.kfw_json or "{}")
    if kfw_daten.get("O01") and not angebot.foerderung_ausblenden:
        logik, bericht = logik_modul.hole_logik(session)
        if bericht is not None:
            parameter, _ = kfw.parameter_lesen(logik)
            eingaben = kfw.eingaben_aus_antworten(kfw_daten, summen["endbetrag"])
            if eingaben is not None:
                ergebnis = kfw.ergebnis_fuer_angebot(parameter, eingaben, angebot)
                foerderung = _euro_betrag(ergebnis.zuschuss_cent) + " €"
                eigenanteil = _euro_betrag(ergebnis.eigenanteil_cent) + " €"
    vertriebler = vertriebler_fuer_angebot(session, angebot)
    gueltig_bis = (angebot.datum + timedelta(days=30)).strftime("%d.%m.%Y") if angebot.datum else ""
    # v27-Nachtrag 2: PV/KL haben keinen KfW-Block – {eigenanteil}/{foerderung}
    # bleiben dort leer statt „–“ [ANNAHME], WP unverändert
    ohne_kfw = (angebot.konfigurator_typ or "WP").upper() in ("PV", "KL")
    return {
        "briefanrede": briefanrede(kunde),
        "anrede": briefanrede(kunde),
        "vorname": (kunde.vorname if kunde else "") or "",
        "nachname": (kunde.nachname if kunde else "") or "",
        "angebotsnummer": angebot.nummer,
        "endbetrag": _euro_betrag(summen["endbetrag"]) + " €",
        "eigenanteil": "" if ohne_kfw else (eigenanteil or "–"),
        "foerderung": "" if ohne_kfw else (foerderung or "–"),
        "gueltig_bis": gueltig_bis,
        "vertriebler": vertriebler.name if vertriebler else "Ihr Friondo-Team",
        "absender": absender_name or "Friondo Innendienst",
    }


def einsetzen(vorlage: str, werte: dict[str, str]) -> str:
    """Platzhalter ersetzen; unbekannte bleiben sichtbar stehen."""
    return _MUSTER.sub(lambda m: werte.get(m.group(0)[1:-1], m.group(0)), vorlage)


def unbekannte_platzhalter(vorlage: str) -> list[str]:
    bekannt = {p for p, _ in PLATZHALTER}
    return sorted({m for m in _MUSTER.findall(vorlage) if m not in bekannt})


def standard_vorlage_laden(session) -> tuple[str, str]:
    """Standard-Vorlage (Betreff, Text) aus der Parametrierung, sonst Festtext."""
    return (einstellung_holen(session, "mail_vorlage_standard_betreff", STANDARD_BETREFF),
            einstellung_holen(session, "mail_vorlage_standard_text", STANDARD_TEXT))


def sparten_vorlage_laden(session, sparte: str) -> tuple[str, str] | None:
    """v27-Nachtrag 2: eigene Vorlage der Sparte (Betreff, Text) oder None, wenn
    keine hinterlegt ist (dann gilt der Standard)."""
    sparte = (sparte or "").upper()
    if sparte not in SPARTEN:
        return None
    schluessel = sparten_schluessel(sparte)
    betreff = einstellung_holen(session, schluessel + "_betreff", "")
    text = einstellung_holen(session, schluessel + "_text", "")
    if not betreff and not text:
        return None
    return betreff, text


def sparten_vorlage_speichern(session, sparte: str, betreff: str, text: str) -> None:
    """v27-Nachtrag 2: Sparten-Vorlage schreiben; leer = entfernen (Standard gilt)."""
    sparte = (sparte or "").upper()
    if sparte not in SPARTEN:
        raise ValueError(f"Unbekannte Sparte: {sparte}")
    schluessel = sparten_schluessel(sparte)
    einstellung_setzen(session, schluessel + "_betreff", (betreff or "").strip())
    einstellung_setzen(session, schluessel + "_text", (text or "").strip())


def sparten_status(session) -> dict[str, bool]:
    """Je Sparte: hat sie eine eigene Vorlage? (Reiter-Beschriftung)."""
    return {sp: sparten_vorlage_laden(session, sp) is not None for sp in SPARTEN}


def vorlage_laden(session, benutzer_id: int | None,
                  sparte: str = "") -> tuple[str, str, str]:
    """(betreff, text, quelle) – Vorlage des AD, sonst Sparten-Vorlage der
    Sparte (v27-Nachtrag 2, nur wenn sparte übergeben), sonst Standard.
    Quelle: „Vorlage <AD>“ | „Sparten-Vorlage KL“ | „Standard-Vorlage“."""
    if benutzer_id:
        betreff = einstellung_holen(session, f"mail_vorlage_{benutzer_id}_betreff", "")
        text = einstellung_holen(session, f"mail_vorlage_{benutzer_id}_text", "")
        if betreff or text:
            benutzer = session.get(Benutzer, benutzer_id)
            return (betreff or STANDARD_BETREFF, text or STANDARD_TEXT,
                    f"Vorlage {benutzer.name if benutzer else benutzer_id}")
    standard_betreff, standard_text = standard_vorlage_laden(session)
    sparte = (sparte or "").upper()
    if sparte:
        eigene = sparten_vorlage_laden(session, sparte)
        if eigene is not None:
            # je Feld Rückfall auf den Standard (wie bei den AD-Vorlagen)
            return (eigene[0] or standard_betreff, eigene[1] or standard_text,
                    f"Sparten-Vorlage {sparte}")
    return (standard_betreff, standard_text, "Standard-Vorlage")


def vorlage_speichern(session, benutzer_id: int | None, betreff: str, text: str,
                      sparte: str = "") -> None:
    """AD-Vorlage (benutzer_id), Sparten-Vorlage (sparte, v27-Nachtrag 2) oder
    Standard; leer = entfernen."""
    if sparte:
        sparten_vorlage_speichern(session, sparte, betreff, text)
        return
    schluessel = f"mail_vorlage_{benutzer_id}" if benutzer_id else "mail_vorlage_standard"
    einstellung_setzen(session, schluessel + "_betreff", betreff.strip())
    einstellung_setzen(session, schluessel + "_text", text.strip())


def mail_fuer_angebot(session, angebot: Angebot, kunde: Kunde | None,
                      absender_name: str = "") -> tuple[str, str, str]:
    """Fertiger Betreff + HTML-Text für den Versand (v6); dritter Wert =
    verwendete Vorlage. Klartext-Vorlagen werden automatisch gewandelt.
    v27-Nachtrag 2: Reihenfolge AD-Vorlage → Sparten-Vorlage des Angebots
    (konfigurator_typ WP/PV/KL/WB) → Standard."""
    vertriebler = vertriebler_fuer_angebot(session, angebot)
    sparte = (angebot.konfigurator_typ or "WP").upper()
    betreff, text, quelle = vorlage_laden(session, vertriebler.id if vertriebler else None,
                                          sparte)
    werte = werte_fuer_angebot(session, angebot, kunde, absender_name)
    return (einsetzen(betreff, werte),
            einsetzen_html(als_html(text), werte), quelle)


# --- v27-Nachtrag 2: Sparten-Vorlagen aus der Standard-Vorlage ableiten ----------

# Block-Grenzen (Zeilenumbruch bzw. Block-Tags der HTML-Vorlagen v6)
_BLOCK_GRENZE = re.compile(r"\n|<\s*/?\s*(?:p|br|li|div|ul|ol|h[1-6]|tr|td|th|table)\b[^>]*>",
                           re.IGNORECASE)
# Satzende: . ! ? (ggf. gefolgt von schließenden Inline-Tags) vor Leerraum/Tag/Ende
_SATZ_ENDE = re.compile(r"[.!?](?:\s*</(?:strong|b|em|i|u|a|span)>)*(?=\s|<|$)",
                        re.IGNORECASE)
_TAG = re.compile(r"<[^>]+>")
# Abkürzungen, nach deren Punkt kein Satz endet
_ABKUERZUNGEN = {"z", "b", "ca", "bzw", "inkl", "zzgl", "nr", "tel", "ggf", "evtl",
                 "u", "a", "d", "h", "str", "vgl", "usw", "etc", "max", "min", "mind",
                 "s", "o", "ä"}


def _klartext(fragment: str) -> str:
    import html as html_modul
    text = " ".join(html_modul.unescape(_TAG.sub(" ", fragment)).split())
    return re.sub(r"\s+([.,;:!?])", r"\1", text)


def _ist_satzende(block: str, position: int) -> bool:
    """Punkt an `position`: Satzende, außer nach Abkürzung/Einzelbuchstabe/Zahl."""
    if block[position] != ".":
        return True
    wort = re.search(r"([\wäöüÄÖÜß]+)$", block[:position])
    if wort is None:
        return True
    w = wort.group(1).lower()
    return not (w in _ABKUERZUNGEN or len(w) == 1 or w.isdigit())


def _saetze_in_block(block: str) -> list[str]:
    saetze, start = [], 0
    for treffer in _SATZ_ENDE.finditer(block):
        if not _ist_satzende(block, treffer.start()):
            continue
        saetze.append(block[start:treffer.end()])
        start = treffer.end()
    rest = block[start:]
    if rest.strip():
        saetze.append(rest)
    return saetze


def saetze_entfernen(text: str, platzhalter=NUR_WP_PLATZHALTER) -> tuple[str, list[str]]:
    """Sätze entfernen, die einen der Platzhalter enthalten – je Zeile (Klartext)
    bzw. je Block (<p>, <br>, <li> … in HTML-Vorlagen). Leer gewordene Absätze
    fallen weg. Rückgabe: (neuer Text, entfernte Sätze als Klartext)."""
    entfernte: list[str] = []
    teile: list[str] = []
    position = 0
    for grenze in list(_BLOCK_GRENZE.finditer(text)) + [None]:
        block = text[position:] if grenze is None else text[position:grenze.start()]
        if any(p in block for p in platzhalter):
            behalten = []
            for satz in _saetze_in_block(block):
                if any(p in satz for p in platzhalter):
                    if _klartext(satz):
                        entfernte.append(_klartext(satz))
                else:
                    behalten.append(satz.strip())
            fuehrend = re.match(r"\s*", block).group(0)
            block = fuehrend + " ".join(s for s in behalten if s)
        teile.append(block)
        if grenze is not None:
            teile.append(grenze.group(0))
            position = grenze.end()
    neu = "".join(teile)
    if ist_html(text):
        neu = re.sub(r"<p\b[^>]*>(?:\s|&nbsp;|<br\s*/?>)*</p>", "", neu, flags=re.IGNORECASE)
        neu = re.sub(r"(?:<br\s*/?>\s*){2,}", "<br>", neu, flags=re.IGNORECASE)
        neu = re.sub(r"(<p\b[^>]*>)\s*(?:<br\s*/?>\s*)+", r"\1", neu, flags=re.IGNORECASE)
        neu = re.sub(r"(?:\s*<br\s*/?>)+\s*(</p>)", r"\1", neu, flags=re.IGNORECASE)
    else:
        neu = "\n".join(z.rstrip() for z in neu.split("\n"))
        neu = re.sub(r"\n{3,}", "\n\n", neu).strip("\n")
    return neu, entfernte


def sparten_vorlage_ableiten(betreff: str, text: str,
                             sparte: str) -> tuple[str, str, list[str]]:
    """v27-Nachtrag 2: Sparten-Vorlage aus der Standard-Vorlage. KL/PV: Wort-
    ersetzungen (SPARTEN_ERSETZUNGEN), Sätze mit {eigenanteil}/{foerderung}
    entfernt (Rückgabe als Liste – der Innendienst liest gegen), übrige
    Vorkommen geleert; WP und WB: unveränderte Kopie [ANNAHME WB]."""
    sparte = (sparte or "").upper()
    ersetzungen = SPARTEN_ERSETZUNGEN.get(sparte)
    if not ersetzungen:
        return betreff, text, []
    for alt, neu in ersetzungen:
        betreff = betreff.replace(alt, neu)
        text = text.replace(alt, neu)
    text, entfernte = saetze_entfernen(text, NUR_WP_PLATZHALTER)
    for p in NUR_WP_PLATZHALTER:
        betreff = betreff.replace(p, "")
        text = text.replace(p, "")
    betreff = re.sub(r"\s+([.,;:!?])", r"\1", re.sub(r"[ \t]{2,}", " ", betreff)).strip()
    text = re.sub(r"[ \t]{2,}", " ", text)
    return betreff, text, entfernte


def migration_sparten(session) -> list[str]:
    """v27-Nachtrag 2 (migrate.py): Sparten-Vorlagen WP/PV/KL/WB einmalig aus
    der heutigen Standard-Vorlage anlegen – nur Sparten ohne eigene Vorlage;
    Marker `migration_nachtrag2_sparten = erledigt`. Idempotent, committet nicht."""
    meldungen = []
    if einstellung_holen(session, MIGRATION_MARKER, "") != "erledigt":
        betreff, text = standard_vorlage_laden(session)
        for sparte in SPARTEN:
            if sparte == "WP":
                # Nachtrag 08.10.2026 (Antwort Andreas): WP bleibt die Standard-Vorlage –
                # keine Kopie, damit es nur EINE Stelle zum Pflegen gibt
                continue
            if sparten_vorlage_laden(session, sparte) is not None:
                meldungen.append(f"E-Mail-Vorlage {sparte}: eigene Vorlage vorhanden – unverändert")
                continue
            neu_betreff, neu_text, entfernte = sparten_vorlage_ableiten(betreff, text, sparte)
            sparten_vorlage_speichern(session, sparte, neu_betreff, neu_text)
            meldungen.append(f"E-Mail-Vorlage {sparte} ({SPARTEN_NAMEN[sparte]}) aus der "
                             f"Standard-Vorlage angelegt – Betreff „{neu_betreff}“")
            for satz in entfernte:
                meldungen.append(f"E-Mail-Vorlage {sparte}: Satz entfernt: „{satz}“")
        einstellung_setzen(session, MIGRATION_MARKER, "erledigt")
    # Nachtrag 08.10.2026: eine vom ersten Lauf angelegte, unveränderte WP-Kopie wieder
    # entfernen (WP nutzt die Standard-Vorlage); eine von Hand geänderte WP-Vorlage bleibt
    if einstellung_holen(session, MIGRATION_MARKER_WP, "") != "erledigt":
        wp = sparten_vorlage_laden(session, "WP")
        if wp is not None and wp == standard_vorlage_laden(session):
            sparten_vorlage_speichern(session, "WP", "", "")
            meldungen.append("E-Mail-Vorlage WP: unveränderte Kopie der Standard-Vorlage entfernt "
                             "– WP nutzt die Standard-Vorlage (Antwort Andreas 08.10.2026)")
        einstellung_setzen(session, MIGRATION_MARKER_WP, "erledigt")
    return meldungen
