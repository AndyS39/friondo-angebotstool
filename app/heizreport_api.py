# Heizreport-API (v15, Phase 80): vorbereitetes Modul – AKTIV erst, wenn
# Zugangsdaten + API-Doku vorliegen (Parametrierung: heizreport_api_url,
# heizreport_api_key). Bis dahin läuft der Weg über den Link (url_heizreport)
# und den PDF-Upload in die Galerie „Montagedokumente“.

from app import projektierung as kern


def konfiguriert(session) -> bool:
    return bool(kern.parameter_holen(session, "heizreport_api_url", "")
                and kern.parameter_holen(session, "heizreport_api_key", ""))


def projekt_anlegen(session, gewerk) -> tuple[bool, str]:
    """Legt das Projekt im Heizreport an (sobald die API-Doku vorliegt)."""
    if not konfiguriert(session):
        return False, ("Heizreport-API nicht konfiguriert – URL und "
                       "API-Schlüssel in der Parametrierung hinterlegen.")
    return False, "Heizreport-API: Anbindung folgt (API-Doku ausstehend)."


def ergebnis_holen(session, gewerk) -> tuple[bool, str, float | None]:
    """Holt die berechnete Heizlast (kW) – Platzhalter bis zur API-Doku."""
    if not konfiguriert(session):
        return False, "Heizreport-API nicht konfiguriert.", None
    return False, "Heizreport-API: Anbindung folgt (API-Doku ausstehend).", None
