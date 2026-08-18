# E-Mail-Vorlagen (Phase 30): Standard-Vorlage (Betreff + Text) plus optionale
# Vorlage je Außendienstler. Beim Versand zieht das Tool die Vorlage des AD des
# Vorgangs (Erfassung → Benutzer), sonst den Standard. Ablage in der Tabelle
# einstellungen: mail_vorlage_standard_betreff/_text bzw.
# mail_vorlage_<benutzer_id>_betreff/_text.

import re
from datetime import timedelta

from app.models import (Angebot, Benutzer, Erfassung, Kunde, einstellung_holen,
                        einstellung_setzen)

# Bisheriger fester Text (Phase 17) – wird per migrate.py zur Standard-Vorlage
STANDARD_BETREFF = "Ihr Wärmepumpen-Angebot {angebotsnummer} der Friondo GmbH"
STANDARD_TEXT = (
    "{anrede}\n\n"
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
    ("{anrede}", "Briefanrede, z. B. „Sehr geehrte Frau Beispiel,“"),
    ("{vorname}", "Vorname des Kunden"),
    ("{nachname}", "Nachname des Kunden"),
    ("{angebotsnummer}", "Angebotsnummer, z. B. AN-C-261015"),
    ("{endbetrag}", "Endbetrag brutto (nach Rabatt), z. B. 34.758,95 €"),
    ("{eigenanteil}", "Eigenanteil nach KfW-Förderung"),
    ("{foerderung}", "voraussichtliche KfW-Förderung"),
    ("{gueltig_bis}", "Angebotsdatum + 30 Tage"),
    ("{vertriebler}", "Name des Außendienstlers des Vorgangs"),
    ("{absender}", "Name des angemeldeten Innendienst-Mitarbeiters"),
]

_MUSTER = re.compile(r"\{[a-z_]+\}")


def briefanrede(kunde: Kunde | None) -> str:
    if kunde is None:
        return "Sehr geehrte Damen und Herren,"
    if kunde.anrede == "Herr" and kunde.nachname:
        return f"Sehr geehrter Herr {kunde.nachname},"
    if kunde.anrede == "Frau" and kunde.nachname:
        return f"Sehr geehrte Frau {kunde.nachname},"
    if kunde.anrede == "Familie" and kunde.nachname:
        return f"Sehr geehrte Familie {kunde.nachname},"
    return "Sehr geehrte Damen und Herren,"


def vertriebler_fuer_angebot(session, angebot: Angebot) -> Benutzer | None:
    """AD des Vorgangs über die verknüpfte Erfassung."""
    erfassung = (session.query(Erfassung)
                 .filter(Erfassung.angebot_id == angebot.id).first())
    if erfassung is None:
        return None
    return session.get(Benutzer, erfassung.benutzer_id)


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
    if kfw_daten.get("O01"):
        logik, bericht = logik_modul.hole_logik(session)
        if bericht is not None:
            parameter, _ = kfw.parameter_lesen(logik)
            eingaben = kfw.eingaben_aus_antworten(kfw_daten, summen["endbetrag"])
            if eingaben is not None:
                ergebnis = kfw.berechnen(parameter, eingaben)
                foerderung = _euro_betrag(ergebnis.zuschuss_cent) + " €"
                eigenanteil = _euro_betrag(ergebnis.eigenanteil_cent) + " €"
    vertriebler = vertriebler_fuer_angebot(session, angebot)
    gueltig_bis = (angebot.datum + timedelta(days=30)).strftime("%d.%m.%Y") if angebot.datum else ""
    return {
        "anrede": briefanrede(kunde),
        "vorname": (kunde.vorname if kunde else "") or "",
        "nachname": (kunde.nachname if kunde else "") or "",
        "angebotsnummer": angebot.nummer,
        "endbetrag": _euro_betrag(summen["endbetrag"]) + " €",
        "eigenanteil": eigenanteil or "–",
        "foerderung": foerderung or "–",
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


def vorlage_laden(session, benutzer_id: int | None) -> tuple[str, str, str]:
    """(betreff, text, quelle) – Vorlage des AD, sonst Standard."""
    if benutzer_id:
        betreff = einstellung_holen(session, f"mail_vorlage_{benutzer_id}_betreff", "")
        text = einstellung_holen(session, f"mail_vorlage_{benutzer_id}_text", "")
        if betreff or text:
            benutzer = session.get(Benutzer, benutzer_id)
            return (betreff or STANDARD_BETREFF, text or STANDARD_TEXT,
                    f"Vorlage {benutzer.name if benutzer else benutzer_id}")
    return (einstellung_holen(session, "mail_vorlage_standard_betreff", STANDARD_BETREFF),
            einstellung_holen(session, "mail_vorlage_standard_text", STANDARD_TEXT),
            "Standard-Vorlage")


def vorlage_speichern(session, benutzer_id: int | None, betreff: str, text: str) -> None:
    schluessel = f"mail_vorlage_{benutzer_id}" if benutzer_id else "mail_vorlage_standard"
    einstellung_setzen(session, schluessel + "_betreff", betreff.strip())
    einstellung_setzen(session, schluessel + "_text", text.strip())


def mail_fuer_angebot(session, angebot: Angebot, kunde: Kunde | None,
                      absender_name: str = "") -> tuple[str, str, str]:
    """Fertiger Betreff + Text für den Versand; dritter Wert = verwendete Vorlage."""
    vertriebler = vertriebler_fuer_angebot(session, angebot)
    betreff, text, quelle = vorlage_laden(session, vertriebler.id if vertriebler else None)
    werte = werte_fuer_angebot(session, angebot, kunde, absender_name)
    return einsetzen(betreff, werte), einsetzen(text, werte), quelle
