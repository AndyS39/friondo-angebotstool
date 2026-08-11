# Versand über Microsoft Graph (Phase 17): legt den E-Mail-Entwurf im Postfach
# des angemeldeten Innendienst-Mitarbeiters ab (delegierte Berechtigung
# Mail.ReadWrite, Device-Code-Anmeldung). Gesendet wird in Outlook nach
# Kontrolle. Einrichtung durch die IT: docs/graph-einrichtung.md.

import base64
import json
import threading
import urllib.request
from pathlib import Path

from app import config
from app.models import Angebot, Kunde

SCOPES = ["Mail.ReadWrite"]
GRAPH = "https://graph.microsoft.com/v1.0"

_token_cache = None
_flow_status: dict = {"laeuft": False, "user_code": "", "verification_uri": "",
                      "fehler": ""}


def konfiguriert() -> bool:
    return bool(config.GRAPH_CLIENT_ID)


def _cache_pfad() -> Path:
    return config.DATA_ORDNER / ".graph_token.json"


def _app():
    import msal
    global _token_cache
    if _token_cache is None:
        _token_cache = msal.SerializableTokenCache()
        if _cache_pfad().exists():
            _token_cache.deserialize(_cache_pfad().read_text(encoding="utf-8"))
    autoritaet = (f"https://login.microsoftonline.com/"
                  f"{config.GRAPH_TENANT_ID or 'organizations'}")
    return msal.PublicClientApplication(config.GRAPH_CLIENT_ID,
                                        authority=autoritaet,
                                        token_cache=_token_cache)


def _cache_speichern():
    if _token_cache is not None and _token_cache.has_state_changed:
        config.DATA_ORDNER.mkdir(parents=True, exist_ok=True)
        _cache_pfad().write_text(_token_cache.serialize(), encoding="utf-8")


def angemeldeter_benutzer() -> str | None:
    """Name/E-Mail des angemeldeten Kontos, wenn ein gültiges Token vorliegt."""
    if not konfiguriert():
        return None
    app = _app()
    konten = app.get_accounts()
    if not konten:
        return None
    ergebnis = app.acquire_token_silent(SCOPES, account=konten[0])
    _cache_speichern()
    if ergebnis and "access_token" in ergebnis:
        return konten[0].get("username", "angemeldet")
    return None


def _token() -> str | None:
    app = _app()
    konten = app.get_accounts()
    if not konten:
        return None
    ergebnis = app.acquire_token_silent(SCOPES, account=konten[0])
    _cache_speichern()
    if ergebnis and "access_token" in ergebnis:
        return ergebnis["access_token"]
    return None


def anmeldung_starten() -> dict:
    """Startet den Device-Code-Flow; das Polling läuft in einem Hintergrund-Thread."""
    if _flow_status["laeuft"]:
        return _flow_status
    app = _app()
    flow = app.initiate_device_flow(scopes=SCOPES)
    if "user_code" not in flow:
        _flow_status.update(laeuft=False, fehler=flow.get("error_description",
                                                          "Device-Flow fehlgeschlagen"))
        return _flow_status
    _flow_status.update(laeuft=True, user_code=flow["user_code"],
                        verification_uri=flow.get("verification_uri",
                                                  "https://microsoft.com/devicelogin"),
                        fehler="")

    def warten():
        try:
            ergebnis = app.acquire_token_by_device_flow(flow)  # blockiert bis Anmeldung/Timeout
            if "access_token" not in (ergebnis or {}):
                _flow_status["fehler"] = (ergebnis or {}).get("error_description",
                                                              "Anmeldung nicht abgeschlossen")
            _cache_speichern()
        except Exception as fehler:
            _flow_status["fehler"] = str(fehler)
        finally:
            _flow_status["laeuft"] = False

    threading.Thread(target=warten, daemon=True).start()
    return _flow_status


def anmeldestatus() -> dict:
    return dict(_flow_status)


def abmelden() -> None:
    global _token_cache
    _token_cache = None
    _cache_pfad().unlink(missing_ok=True)


# --- Entwurf im Postfach --------------------------------------------------

def _anrede(kunde: Kunde) -> str:
    if kunde.anrede == "Herr" and kunde.nachname:
        return f"Sehr geehrter Herr {kunde.nachname},"
    if kunde.anrede == "Frau" and kunde.nachname:
        return f"Sehr geehrte Frau {kunde.nachname},"
    if kunde.anrede == "Familie" and kunde.nachname:
        return f"Sehr geehrte Familie {kunde.nachname},"
    return "Sehr geehrte Damen und Herren,"


def standardtext(kunde: Kunde, angebot: Angebot) -> str:
    return (f"{_anrede(kunde)}\n\n"
            f"vielen Dank für Ihr Interesse an einer Wärmepumpe der Friondo GmbH.\n\n"
            f"Anbei erhalten Sie Ihr individuelles Angebot {angebot.nummer} "
            f"als PDF-Datei. Wir halten uns freibleibend 30 Tage an dieses "
            f"Angebot gebunden.\n\n"
            f"Bei Fragen stehen wir Ihnen jederzeit gerne zur Verfügung – "
            f"telefonisch unter 0203 - 3965 710 oder per E-Mail an info@friondo.de.\n\n"
            f"Mit freundlichen Grüßen\n"
            f"Ihr Friondo-Team\n\n"
            f"Friondo GmbH · Arnold-Overbeck-Str. 63-65 · 47139 Duisburg\n"
            f"www.friondo.de")


def _graph_aufruf(methode: str, pfad: str, token: str, daten: dict | None = None) -> dict:
    anfrage = urllib.request.Request(
        GRAPH + pfad,
        data=json.dumps(daten).encode() if daten is not None else None,
        method=methode,
        headers={"Authorization": f"Bearer {token}",
                 "Content-Type": "application/json"})
    with urllib.request.urlopen(anfrage) as antwort:
        inhalt = antwort.read()
    return json.loads(inhalt) if inhalt else {}


def entwurf_erstellen(kunde: Kunde, angebot: Angebot, pdf_pfad: Path,
                      weitere_anhaenge: list[Path] | None = None,
                      fehlende_anhaenge: list[str] | None = None
                      ) -> tuple[bool, str, str]:
    """Legt den Entwurf mit Anhängen im Postfach ab. Liefert (erfolg, meldung, weblink)."""
    if not kunde.email:
        return False, ("Der Kunde hat keine E-Mail-Adresse – bitte zuerst in der "
                       "Kundenverwaltung ergänzen."), ""
    token = _token()
    if token is None:
        return False, "Nicht bei Microsoft angemeldet – bitte unter „Versand“ anmelden.", ""
    try:
        nachricht = {
            "subject": f"Ihr Wärmepumpen-Angebot {angebot.nummer} der Friondo GmbH",
            "body": {"contentType": "text", "content": standardtext(kunde, angebot)},
            "toRecipients": [{"emailAddress": {"address": kunde.email}}],
        }
        entwurf = _graph_aufruf("POST", "/me/messages", token, nachricht)
        nachricht_id = entwurf["id"]
        for pfad in [pdf_pfad] + list(weitere_anhaenge or []):
            _graph_aufruf("POST", f"/me/messages/{nachricht_id}/attachments", token, {
                "@odata.type": "#microsoft.graph.fileAttachment",
                "name": Path(pfad).name,
                "contentBytes": base64.b64encode(Path(pfad).read_bytes()).decode(),
            })
        weblink = entwurf.get("webLink", "")
        meldung = ("Entwurf im Postfach abgelegt – bitte in Outlook prüfen und senden. "
                   "Danach hier den Status auf „Versendet“ setzen.")
        if fehlende_anhaenge:
            meldung += (" Achtung, fehlende Anhang-Dateien im Ordner anlagen/: "
                        + ", ".join(fehlende_anhaenge))
        return True, meldung, weblink
    except Exception as fehler:
        return False, (f"Entwurf konnte nicht erstellt werden: {fehler}. "
                       "Alternativ das PDF herunterladen und manuell versenden."), ""
