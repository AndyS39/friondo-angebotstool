"""v36 (PLAN_V22 Phase 194, Agent B3): PDF-Ablage für Cloover – öffentlich abrufbare URL des Angebots-PDFs.

Cloover verlangt für `POST /api/projects` eine öffentlich abrufbare URL des Angebots-PDFs (`offerPDF`);
das Tool selbst läuft nur im VPN. Drei Anbieter (Parameter `cloover_pdf_ablage`, Standard `sharepoint`):

  sharepoint  Upload über Graph **als Anwendung** (v33, Phase 166) in eine eigene SharePoint-Bibliothek
              (Parameter `cloover_sharepoint_site` = Site-ID oder `hostname:/sites/<name>`,
              `cloover_sharepoint_ordner`, Standard „Cloover-Angebote“; Berechtigung `Sites.Selected`
              nur für diese Site – docs/cloover-api.md), danach anonymer Lese-Link (`createLink`
              type view, scope anonymous, Ablauf LINK_TAGE = 180 Tage [ANNAHME]) und Download-URL
              (`?download=1`). Im Modus delegiert ist die Ablage nicht möglich („Ablage braucht
              Graph als Anwendung“).
  basis_url   Token-Route `GET /oeffentlich/cloover/<token>.pdf` (app/routers/oeffentlich.py) unter
              `config.BASIS_URL` – nur sinnvoll mit öffentlicher HTTPS-Adresse (v27-Vorbereitung
              `BASIS_URL` in der .env); Token 32 Zeichen (`secrets.token_urlsafe(24)`), Ablauf
              180 Tage, kein Login, keine Verzeichnisliste, Datei `data/cloover_pdf/<token>.pdf`,
              Tabelle `cloover_pdf_tokens` (models.ClooverPdfToken, additiv).
  keine       Rate ja, Projekt nein – Hinweis „Cloover-Link nicht möglich: PDF-Ablage nicht eingerichtet“.

Schnittstelle (für app/cloover_projekt.py):
  konfig(session) -> dict               Parameter + Bereitschaft (lesen, BEVOR die Sitzung freigegeben wird)
  eingerichtet(session) -> (bool, Grund)
  dateiname(angebotsnummer) -> str      „AN-C-261021-<Zufall>.pdf“ – nie ein Kundenname
  ablegen(datei, name, konfig=None, angebot_id=None) -> Ablage-Dict {anbieter, url, download_url, …}
  ersetzen(ablage_oder_url, datei, konfig=None) -> Ablage-Dict (gleiche URL, Inhalt = Fassung B)
  pruefen(url) -> (ok, Meldung)         HEAD ohne Anmeldung muss application/pdf liefern
  test_ablage(session) -> (ok, Text)    „Test-PDF ablegen und prüfen“ der Parametrierung

Alle Netzaufrufe laufen ohne offene Datenbanksitzung: die Aufrufer lesen `konfig(session)`, geben die
Sitzung frei (`verbindung_freigeben`) und rufen dann ablegen/ersetzen/pruefen (Wächter
tests/test_v27_sitzungen.py – `urlopen` ist die primitive Nahtstelle). Geheimnisse (Graph-Token) werden
nie protokolliert.
"""
from __future__ import annotations

import base64
import json
import logging
import secrets
import shutil
import tempfile
import threading
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

from app import config

log = logging.getLogger("angebotstool.cloover_pdf_ablage")

ANBIETER = ("sharepoint", "basis_url", "keine")
ANBIETER_NAMEN = {"sharepoint": "SharePoint-Bibliothek (Graph als Anwendung, anonymer Lese-Link)",
                  "basis_url": "Token-Route unter BASIS_URL (öffentliche HTTPS-Adresse des Tools)",
                  "keine": "keine Ablage – Rate ja, Cloover-Projekt nein"}
EINSTELLUNG_ANBIETER = "cloover_pdf_ablage"
EINSTELLUNG_SITE = "cloover_sharepoint_site"
EINSTELLUNG_ORDNER = "cloover_sharepoint_ordner"
EINSTELLUNG_LETZTER_TEST = "cloover_ablage_letzter_test"
STANDARD_ANBIETER = "sharepoint"
STANDARD_ORDNER = "Cloover-Angebote"
LINK_TAGE = 180                     # Ablauf anonymer Link / Token [ANNAHME Plan Phase 194]
TOKEN_ORDNER = config.DATA_ORDNER / "cloover_pdf"
TOKEN_PFAD = "/oeffentlich/cloover"             # Route: GET /oeffentlich/cloover/<token>.pdf
GRAPH_EINFACH_MAX = 4_000_000       # Graph: einfacher Upload bis 4 MB, darüber Upload-Session
UPLOAD_BLOCK = 10 * 327_680         # 3.276.800 Byte – Vielfaches von 320 KiB (Graph-Vorgabe)
HTTP_TIMEOUT = 60
PRUEF_TIMEOUT = 20
GRUND_KEINE = "PDF-Ablage nicht eingerichtet"
GRUND_DELEGIERT = "PDF-Ablage braucht Graph als Anwendung (Verbindungstest unter „Versand“)"
GRUND_SITE = "PDF-Ablage: SharePoint-Site fehlt (Parametrierung → Cloover → PDF-Ablage)"
GRUND_BASIS_URL = "PDF-Ablage: BASIS_URL fehlt in der .env (öffentliche HTTPS-Adresse)"

_site_cache: dict[str, str] = {}
_site_sperre = threading.Lock()


class AblageFehler(RuntimeError):
    """Fehler der PDF-Ablage mit Nutzer-Meldung (ohne Token/Geheimnisse)."""

    def __init__(self, meldung: str):
        super().__init__(meldung)
        self.meldung = meldung


# --- Konfiguration -------------------------------------------------------------------------------

def anbieter(session) -> str:
    from app.models import einstellung_holen
    wert = (einstellung_holen(session, EINSTELLUNG_ANBIETER, STANDARD_ANBIETER) or "").strip().lower()
    return wert if wert in ANBIETER else STANDARD_ANBIETER


def site(session) -> str:
    from app.models import einstellung_holen
    return (einstellung_holen(session, EINSTELLUNG_SITE, "") or "").strip()


def ordner(session) -> str:
    from app.models import einstellung_holen
    return (einstellung_holen(session, EINSTELLUNG_ORDNER, STANDARD_ORDNER) or "").strip("/ ") or STANDARD_ORDNER


def konfig(session) -> dict:
    """Alle Parameter der Ablage plus Bereitschaft – lesen, BEVOR die Sitzung freigegeben wird;
    das Dict geht ohne Sitzung in ablegen/ersetzen."""
    from app import graph_versand
    wahl = anbieter(session)
    daten = {"anbieter": wahl, "anbieter_name": ANBIETER_NAMEN[wahl], "site": site(session),
             "ordner": ordner(session), "basis_url": config.BASIS_URL,
             "basis_url_aus_env": bool(config.BASIS_URL_AUS_ENV),
             "graph_modus": graph_versand.modus(session), "link_tage": LINK_TAGE}
    daten["bereit"], daten["grund"] = _bereitschaft(daten)
    return daten


def _bereitschaft(daten: dict) -> tuple[bool, str]:
    from app import graph_versand
    wahl = daten.get("anbieter") or STANDARD_ANBIETER
    if wahl == "keine":
        return False, GRUND_KEINE
    if wahl == "sharepoint":
        if daten.get("graph_modus") != graph_versand.MODUS_ANWENDUNG:
            return False, GRUND_DELEGIERT
        if not daten.get("site"):
            return False, GRUND_SITE
        return True, ""
    if not daten.get("basis_url_aus_env"):
        return False, GRUND_BASIS_URL
    return True, ""


def eingerichtet(session) -> tuple[bool, str]:
    """(True, "") wenn Cloover-Projekte eine PDF-URL bekommen können; sonst (False, Grund)."""
    daten = konfig(session)
    return bool(daten["bereit"]), daten["grund"]


def konfig_lesen() -> dict:
    """Ohne übergebene Sitzung: kurze Lesesitzung (nur für Aufrufer außerhalb einer Anfrage)."""
    from app import db
    with db.kurz(schreibend=False) as s:
        return konfig(s)


def speichern(session, form) -> list[str]:
    """Parameter der Ablage aus dem Formular übernehmen; liefert die Änderungen (Protokollzeilen).
    Der Aufrufer committet."""
    from app.models import einstellung_setzen
    aenderungen: list[str] = []
    if "cloover_pdf_ablage" in form:
        neu = (form.get("cloover_pdf_ablage") or "").strip().lower()
        alt = anbieter(session)
        if neu in ANBIETER and neu != alt:
            einstellung_setzen(session, EINSTELLUNG_ANBIETER, neu)
            aenderungen.append(f"cloover_pdf_ablage: {alt} → {neu}")
    if "cloover_sharepoint_site" in form:
        neu = (form.get("cloover_sharepoint_site") or "").strip()[:300]
        alt = site(session)
        if neu != alt:
            einstellung_setzen(session, EINSTELLUNG_SITE, neu)
            _site_cache.clear()
            aenderungen.append(f"cloover_sharepoint_site: {alt or '–'} → {neu or '–'}")
    if "cloover_sharepoint_ordner" in form:
        neu = (form.get("cloover_sharepoint_ordner") or "").strip("/ ")[:200] or STANDARD_ORDNER
        alt = ordner(session)
        if neu != alt:
            einstellung_setzen(session, EINSTELLUNG_ORDNER, neu)
            aenderungen.append(f"cloover_sharepoint_ordner: {alt} → {neu}")
    return aenderungen


def letzten_test_merken(session, ok: bool, text: str, url: str = "") -> dict:
    from app.models import einstellung_setzen
    # einstellungen.wert ist als String(300) deklariert – SQLite erzwingt die Länge nicht (wie
    # cloover_letzter_test von B1, dort bis 2000 Zeichen); Text und URL trotzdem begrenzen
    daten = {"ok": bool(ok), "text": (text or "")[:400], "url": (url or "")[:400],
             "zeit": datetime.now().strftime("%d.%m.%Y %H:%M")}
    einstellung_setzen(session, EINSTELLUNG_LETZTER_TEST, json.dumps(daten, ensure_ascii=False))
    return daten


def letzter_test(session) -> dict | None:
    from app.models import einstellung_holen
    roh = einstellung_holen(session, EINSTELLUNG_LETZTER_TEST, "")
    if not roh:
        return None
    try:
        daten = json.loads(roh)
    except ValueError:
        return None
    return daten if isinstance(daten, dict) else None


def seiten_kontext(session) -> dict:
    """Kontext des Parametrierungs-Partials konfiguration/_cloover_ablage.html."""
    daten = konfig(session)
    daten["letzter_test"] = letzter_test(session)
    daten["anbieter_liste"] = [(k, ANBIETER_NAMEN[k]) for k in ANBIETER]
    daten["token_route"] = f"{config.BASIS_URL}{TOKEN_PFAD}/<token>.pdf"
    return daten


# --- Dateiname ----------------------------------------------------------------------------------

def dateiname(angebotsnummer: str) -> str:
    """Ablage-Name ohne Kundennamen: `AN-C-261021-<Zufall>.pdf` (Versionen: Punkt → Bindestrich)."""
    basis = "".join(c if c.isalnum() or c == "-" else "-" for c in (angebotsnummer or "Angebot"))
    return f"{basis.strip('-') or 'Angebot'}-{secrets.token_urlsafe(6).replace('_', '-')}.pdf"


# --- Anbieter: SharePoint über Graph -------------------------------------------------------------

def _token() -> str:
    from app import graph_versand
    if graph_versand.modus() != graph_versand.MODUS_ANWENDUNG:
        raise AblageFehler(GRUND_DELEGIERT)
    token = graph_versand._token()
    if not token:
        raise AblageFehler("Graph: " + graph_versand.nicht_verbunden_text())
    return token


def _graph_bytes(methode: str, pfad: str, token: str, daten: bytes | None = None,
                 content_type: str = "application/pdf", timeout: int = HTTP_TIMEOUT,
                 absolut: bool = False, zusatz_kopf: dict | None = None) -> tuple[int, dict]:
    """Roher Graph-Aufruf mit Binärkörper (PUT …:/content, Upload-Session). Liefert (Status, JSON-Dict).
    4xx/5xx → (Status, Fehlerdict); 403 wird wie in graph_versand als Zugriffsgruppen-Fehler gemerkt."""
    from app import graph_versand
    url = pfad if absolut else graph_versand.GRAPH + pfad
    kopf = {"Content-Type": content_type}
    if not absolut:
        kopf["Authorization"] = f"Bearer {token}"
    if zusatz_kopf:
        kopf.update(zusatz_kopf)
    anfrage = urllib.request.Request(url, data=daten, method=methode, headers=kopf)
    try:
        with urllib.request.urlopen(anfrage, timeout=timeout) as antwort:
            inhalt = antwort.read()
            status = antwort.status
    except urllib.error.HTTPError as fehler:
        try:
            inhalt = fehler.read()
        except Exception:   # noqa: BLE001
            inhalt = b""
        if fehler.code == 403 and not absolut:
            graph_versand.zugriff_verweigert_merken(graph_versand.postfach_aus_pfad(pfad) or "SharePoint-Site",
                                                   pfad)
        return fehler.code, _json(inhalt)
    except Exception as fehler:   # noqa: BLE001 – Netz/Timeout
        raise AblageFehler(f"Graph nicht erreichbar: {type(fehler).__name__}: {str(fehler)[:160]}") from None
    graph_versand.erfolg_merken(pfad if not absolut else "/upload")
    return status, _json(inhalt)


def _json(inhalt: bytes) -> dict:
    text = (inhalt or b"").decode("utf-8", "replace").strip()
    if not text:
        return {}
    try:
        daten = json.loads(text)
    except ValueError:
        return {"text": text[:300]}
    return daten if isinstance(daten, dict) else {"wert": daten}


def _graph_fehlertext(antwort: dict, status: int) -> str:
    fehler = antwort.get("error") if isinstance(antwort, dict) else None
    if isinstance(fehler, dict):
        return f"HTTP {status}: {fehler.get('code') or ''} {fehler.get('message') or ''}".strip()
    return f"HTTP {status}: {str(antwort.get('text') or antwort)[:200]}" if antwort else f"HTTP {status}"


def _site_id(token: str, site_wert: str) -> str:
    """Site-ID aus dem Parameter: Site-ID (`host,guid,guid`) direkt; `hostname:/sites/<name>` oder
    eine Site-URL werden einmal je Prozess über GET /sites/{hostname}:{pfad} aufgelöst."""
    from app import graph_versand
    wert = (site_wert or "").strip()
    if not wert:
        raise AblageFehler(GRUND_SITE)
    if "," in wert and not wert.startswith("http"):
        return wert
    with _site_sperre:
        bekannt = _site_cache.get(wert)
    if bekannt:
        return bekannt
    if wert.startswith("http"):
        teile = urllib.parse.urlsplit(wert)
        pfad = f"/sites/{teile.netloc}:{teile.path.rstrip('/') or '/'}"
    elif ":" in wert:
        host, _, rest = wert.partition(":")
        pfad = f"/sites/{host}:{rest if rest.startswith('/') else '/' + rest}"
    else:
        pfad = f"/sites/{wert}"
    try:
        antwort = graph_versand._graph_aufruf("GET", pfad + "?$select=id", token)
    except graph_versand.GraphZugriffVerweigert:
        raise AblageFehler(f"SharePoint-Site {wert}: Zugriff verweigert (HTTP 403) – der Tool-App fehlt "
                           "Sites.Selected auf dieser Site (docs/cloover-api.md)") from None
    except urllib.error.HTTPError as fehler:
        raise AblageFehler(f"SharePoint-Site {wert} nicht gefunden (HTTP {fehler.code})") from None
    except Exception as fehler:   # noqa: BLE001
        raise AblageFehler(f"SharePoint-Site {wert}: {type(fehler).__name__}: {str(fehler)[:160]}") from None
    kennung = str(antwort.get("id") or "")
    if not kennung:
        raise AblageFehler(f"SharePoint-Site {wert}: keine Site-ID in der Antwort")
    with _site_sperre:
        _site_cache[wert] = kennung
    return kennung


def _ordner_anlegen(token: str, site_id: str, ordner_name: str) -> None:
    body = json.dumps({"name": ordner_name, "folder": {},
                       "@microsoft.graph.conflictBehavior": "fail"}).encode("utf-8")
    status, antwort = _graph_bytes("POST", f"/sites/{site_id}/drive/root/children", token, body,
                                   content_type="application/json")
    if status not in (200, 201, 409):
        raise AblageFehler(f"SharePoint-Ordner „{ordner_name}“ konnte nicht angelegt werden – "
                           + _graph_fehlertext(antwort, status))


def _upload(token: str, site_id: str, ordner_name: str, name: str, daten: bytes) -> dict:
    """Datei in die Bibliothek hochladen (Pfad root:/<Ordner>/<Name>); ≤ 4 MB einfacher PUT, sonst
    Upload-Session in Blöcken. Liefert das DriveItem (id, webUrl, parentReference.driveId)."""
    pfad = (f"/sites/{site_id}/drive/root:/{urllib.parse.quote(ordner_name)}/"
            f"{urllib.parse.quote(name)}:/content?@microsoft.graph.conflictBehavior=rename")
    for versuch in (1, 2):
        if len(daten) <= GRAPH_EINFACH_MAX:
            status, antwort = _graph_bytes("PUT", pfad, token, daten)
        else:
            status, antwort = _upload_session(token, site_id, ordner_name, name, daten)
        if status in (200, 201):
            return antwort
        if status == 404 and versuch == 1:
            _ordner_anlegen(token, site_id, ordner_name)
            continue
        if status == 403:
            raise AblageFehler("SharePoint: Zugriff verweigert (HTTP 403) – der Tool-App fehlt Sites.Selected "
                               "mit Schreibrecht auf dieser Site (docs/cloover-api.md)")
        raise AblageFehler("SharePoint-Upload fehlgeschlagen – " + _graph_fehlertext(antwort, status))
    raise AblageFehler("SharePoint-Upload fehlgeschlagen")


def _upload_session(token: str, site_id: str, ordner_name: str, name: str, daten: bytes) -> tuple[int, dict]:
    from app import graph_versand
    pfad = (f"/sites/{site_id}/drive/root:/{urllib.parse.quote(ordner_name)}/"
            f"{urllib.parse.quote(name)}:/createUploadSession")
    sitzung = graph_versand._graph_aufruf("POST", pfad, token,
                                          {"item": {"@microsoft.graph.conflictBehavior": "rename"}})
    upload_url = sitzung.get("uploadUrl")
    if not upload_url:
        return 500, {"text": "keine uploadUrl"}
    gesamt = len(daten)
    status, antwort = 0, {}
    for start in range(0, gesamt, UPLOAD_BLOCK):
        block = daten[start:start + UPLOAD_BLOCK]
        ende = start + len(block) - 1
        status, antwort = _graph_bytes("PUT", upload_url, token, block, content_type="application/octet-stream",
                                       absolut=True, timeout=120,
                                       zusatz_kopf={"Content-Range": f"bytes {start}-{ende}/{gesamt}"})
        if status not in (200, 201, 202):
            return status, antwort
    return status, antwort


def _link_anlegen(token: str, site_id: str, item_id: str, tage: int) -> str:
    """Anonymer Lese-Link (createLink view/anonymous, Ablauf +tage) → webUrl."""
    from app import graph_versand
    ablauf = (datetime.now(timezone.utc) + timedelta(days=tage)).strftime("%Y-%m-%dT%H:%M:%SZ")
    body = {"type": "view", "scope": "anonymous", "expirationDateTime": ablauf}
    try:
        antwort = graph_versand._graph_aufruf("POST", f"/sites/{site_id}/drive/items/{item_id}/createLink",
                                              token, body)
    except graph_versand.GraphZugriffVerweigert:
        raise AblageFehler("SharePoint: anonymer Link verweigert (HTTP 403) – Freigabe „Jeder mit dem Link“ "
                           "für diese Site erlauben (docs/cloover-api.md)") from None
    except urllib.error.HTTPError as fehler:
        try:
            text = _graph_fehlertext(_json(fehler.read()), fehler.code)
        except Exception:   # noqa: BLE001
            text = f"HTTP {fehler.code}"
        raise AblageFehler("SharePoint: anonymer Link nicht möglich – " + text
                           + " (Freigabe „Jeder mit dem Link“ für die Site erlauben, docs/cloover-api.md)") from None
    link = antwort.get("link") if isinstance(antwort, dict) else None
    url = (link or {}).get("webUrl") if isinstance(link, dict) else None
    if not url:
        raise AblageFehler("SharePoint: createLink ohne webUrl in der Antwort")
    return str(url)


def _download_url(web_url: str) -> str:
    return web_url + ("&" if "?" in web_url else "?") + "download=1"


def _sharepoint_ablegen(datei: Path, name: str, konf: dict) -> dict:
    token = _token()
    site_id = _site_id(token, konf.get("site", ""))
    ordner_name = (konf.get("ordner") or STANDARD_ORDNER).strip("/ ")
    item = _upload(token, site_id, ordner_name, name, Path(datei).read_bytes())
    item_id = str(item.get("id") or "")
    if not item_id:
        raise AblageFehler("SharePoint-Upload ohne Item-ID in der Antwort")
    drive_id = str((item.get("parentReference") or {}).get("driveId") or "")
    web_url = _link_anlegen(token, site_id, item_id, int(konf.get("link_tage") or LINK_TAGE))
    ablauf = (datetime.now() + timedelta(days=int(konf.get("link_tage") or LINK_TAGE))).strftime("%d.%m.%Y")
    return {"anbieter": "sharepoint", "name": str(item.get("name") or name), "item_id": item_id,
            "drive_id": drive_id, "site_id": site_id, "web_url": web_url,
            "url": _download_url(web_url), "download_url": _download_url(web_url), "ablauf": ablauf,
            "abgelegt_am": datetime.now().strftime("%d.%m.%Y %H:%M")}


def _sharepoint_item_aus_url(token: str, url: str) -> tuple[str, str]:
    """(drive_id, item_id) zu einem Freigabe-Link über GET /shares/{u!…}/driveItem."""
    from app import graph_versand
    roh = url.split("?download=1")[0]
    kodiert = base64.urlsafe_b64encode(roh.encode("utf-8")).decode("ascii").rstrip("=")
    try:
        antwort = graph_versand._graph_aufruf("GET", f"/shares/u!{kodiert}/driveItem?$select=id,parentReference", token)
    except Exception as fehler:   # noqa: BLE001
        raise AblageFehler(f"SharePoint: Datei zum Link nicht gefunden ({type(fehler).__name__})") from None
    item_id = str(antwort.get("id") or "")
    drive_id = str((antwort.get("parentReference") or {}).get("driveId") or "")
    if not item_id or not drive_id:
        raise AblageFehler("SharePoint: Datei zum Link nicht gefunden")
    return drive_id, item_id


def _sharepoint_ersetzen(ablage: dict, datei: Path) -> dict:
    token = _token()
    drive_id, item_id = ablage.get("drive_id") or "", ablage.get("item_id") or ""
    if not (drive_id and item_id):
        drive_id, item_id = _sharepoint_item_aus_url(token, ablage.get("url") or "")
    status, antwort = _graph_bytes("PUT", f"/drives/{drive_id}/items/{item_id}/content", token,
                                   Path(datei).read_bytes())
    if status not in (200, 201):
        raise AblageFehler("SharePoint: Ersetzen fehlgeschlagen – " + _graph_fehlertext(antwort, status))
    neu = dict(ablage)
    neu.update(drive_id=drive_id, item_id=item_id, ersetzt_am=datetime.now().strftime("%d.%m.%Y %H:%M"))
    return neu


# --- Anbieter: Token-Route unter BASIS_URL --------------------------------------------------------

def token_url(token: str, basis_url: str | None = None) -> str:
    return f"{(basis_url or config.BASIS_URL).rstrip('/')}{TOKEN_PFAD}/{token}.pdf"


def _token_ablegen(datei: Path, name: str, konf: dict, angebot_id: int | None) -> dict:
    from app import db
    from app.models import ClooverPdfToken
    token = secrets.token_urlsafe(24)          # 32 Zeichen
    TOKEN_ORDNER.mkdir(parents=True, exist_ok=True)
    ziel = TOKEN_ORDNER / f"{token}.pdf"
    shutil.copyfile(datei, ziel)
    ablauf = datetime.now() + timedelta(days=int(konf.get("link_tage") or LINK_TAGE))
    with db.kurz() as s:
        s.add(ClooverPdfToken(token=token, angebot_id=angebot_id, datei=ziel.name, name=name[:120],
                              gueltig_bis=ablauf))
    url = token_url(token, konf.get("basis_url"))
    return {"anbieter": "basis_url", "name": name, "token": token, "url": url, "download_url": url,
            "ablauf": ablauf.strftime("%d.%m.%Y"), "abgelegt_am": datetime.now().strftime("%d.%m.%Y %H:%M")}


def _token_aus_url(url: str) -> str:
    teil = (url or "").rsplit("/", 1)[-1]
    return teil[:-4] if teil.endswith(".pdf") else teil


def _token_ersetzen(ablage: dict, datei: Path) -> dict:
    token = ablage.get("token") or _token_aus_url(ablage.get("url") or "")
    if not token or "/" in token or "\\" in token or ".." in token:
        raise AblageFehler("Token-Ablage: ungültiger Token")
    ziel = TOKEN_ORDNER / f"{token}.pdf"
    if not ziel.is_file():
        raise AblageFehler("Token-Ablage: Datei zum Token fehlt (abgelaufen oder gelöscht)")
    shutil.copyfile(datei, ziel)
    neu = dict(ablage)
    neu.update(token=token, ersetzt_am=datetime.now().strftime("%d.%m.%Y %H:%M"))
    return neu


def token_datei(session, token: str) -> Path | None:
    """Datei zu einem gültigen Token (Route GET /oeffentlich/cloover/<token>.pdf); None bei unbekannt,
    abgelaufen oder fehlender Datei – die Route antwortet dann 404, nie mit einer Liste."""
    from app.models import ClooverPdfToken
    token = (token or "").strip()
    if not token or len(token) > 64 or any(c in token for c in "/\\.?"):
        return None
    zeile = session.query(ClooverPdfToken).filter(ClooverPdfToken.token == token).first()
    if zeile is None or zeile.gueltig_bis is None or zeile.gueltig_bis < datetime.now():
        return None
    pfad = TOKEN_ORDNER / (zeile.datei or f"{token}.pdf")
    try:
        if pfad.is_file() and pfad.stat().st_size > 0:
            return pfad
    except OSError:
        pass
    return None


def abgelaufene_tokens_raeumen(jetzt: datetime | None = None, karenz_tage: int = 30) -> int:
    """Dateien abgelaufener Tokens (Ablauf + Karenz) entfernen; Zeilen bleiben (Protokoll). Lauf
    cloover-status (einmal täglich). Liefert die Anzahl entfernter Dateien."""
    from app import db
    from app.models import ClooverPdfToken
    jetzt = jetzt or datetime.now()
    grenze = jetzt - timedelta(days=karenz_tage)
    with db.kurz(schreibend=False) as s:
        alte = [z.datei for z in s.query(ClooverPdfToken)
                .filter(ClooverPdfToken.gueltig_bis < grenze)]
    entfernt = 0
    for name in alte:
        pfad = TOKEN_ORDNER / name
        try:
            if pfad.is_file():
                pfad.unlink()
                entfernt += 1
        except OSError:
            continue
    return entfernt


# --- Schnittstelle --------------------------------------------------------------------------------

def ablegen(datei: Path, name: str, konfig_daten: dict | None = None, angebot_id: int | None = None) -> dict:
    """PDF öffentlich ablegen → Ablage-Dict mit `url` (für offerPDF), `download_url`, `anbieter`, Ablauf.
    Netz-/Datei-I/O – nie mit offener Datenbanksitzung aufrufen (Konfiguration vorher lesen)."""
    konf = konfig_daten if konfig_daten is not None else konfig_lesen()
    if not Path(datei).is_file():
        raise AblageFehler(f"PDF-Datei fehlt: {Path(datei).name}")
    bereit, grund = _bereitschaft(konf)
    if not bereit:
        raise AblageFehler(grund)
    if konf.get("anbieter") == "sharepoint":
        return _sharepoint_ablegen(Path(datei), name, konf)
    return _token_ablegen(Path(datei), name, konf, angebot_id)


def ersetzen(ablage, datei: Path, konfig_daten: dict | None = None) -> dict:
    """Abgelegte Datei durch eine neue Fassung ersetzen (gleiche URL). `ablage` = Ablage-Dict aus
    ablegen() oder die reine URL (SharePoint: Auflösung über /shares, Token: aus dem Pfad)."""
    if isinstance(ablage, str):
        wahl = "basis_url" if TOKEN_PFAD in ablage else "sharepoint"
        ablage = {"anbieter": wahl, "url": ablage}
    if not Path(datei).is_file():
        raise AblageFehler(f"PDF-Datei fehlt: {Path(datei).name}")
    if (ablage.get("anbieter") or "sharepoint") == "basis_url":
        return _token_ersetzen(ablage, Path(datei))
    return _sharepoint_ersetzen(ablage, Path(datei))


def pruefen(url: str, timeout: int = PRUEF_TIMEOUT) -> tuple[bool, str]:
    """HEAD ohne Anmeldung muss `application/pdf` liefern (Cloover ruft die URL anonym ab). Antwortet der
    Dienst auf HEAD nicht sauber (405/403) oder mit anderem Content-Type, wird der Anfang per GET gelesen
    und das PDF-Kennzeichen „%PDF“ geprüft. (ok, Meldung)."""
    url = (url or "").strip()
    if not url.lower().startswith(("http://", "https://")):
        return False, "keine http(s)-URL"
    try:
        anfrage = urllib.request.Request(url, method="HEAD", headers={"User-Agent": "Friondo-Angebotstool"})
        with urllib.request.urlopen(anfrage, timeout=timeout) as antwort:
            status = antwort.status
            typ = (antwort.headers.get("Content-Type") or "").split(";")[0].strip().lower()
    except urllib.error.HTTPError as fehler:
        status, typ = fehler.code, ""
        if status not in (403, 405, 501):
            return False, f"HTTP {status} bei HEAD ohne Anmeldung"
    except Exception as fehler:   # noqa: BLE001
        return False, f"nicht erreichbar: {type(fehler).__name__}: {str(fehler)[:120]}"
    if status in (200, 206) and typ == "application/pdf":
        return True, "HEAD ohne Anmeldung: application/pdf"
    # Rückfall: Anfang der Datei lesen
    try:
        anfrage = urllib.request.Request(url, method="GET",
                                         headers={"Range": "bytes=0-15", "User-Agent": "Friondo-Angebotstool"})
        with urllib.request.urlopen(anfrage, timeout=timeout) as antwort:
            anfang = antwort.read(16)
            typ2 = (antwort.headers.get("Content-Type") or "").split(";")[0].strip().lower()
    except urllib.error.HTTPError as fehler:
        return False, f"HTTP {fehler.code} ohne Anmeldung (HEAD: {status}, Content-Type {typ or '–'})"
    except Exception as fehler:   # noqa: BLE001
        return False, f"nicht erreichbar: {type(fehler).__name__}: {str(fehler)[:120]}"
    if anfang.startswith(b"%PDF"):
        return True, f"Inhalt ist ein PDF (Content-Type {typ2 or typ or '–'}, HEAD {status})"
    return False, f"kein PDF ohne Anmeldung (HTTP {status}, Content-Type {typ or typ2 or '–'})"


# --- Test-PDF der Parametrierung ------------------------------------------------------------------

def test_pdf_bytes(zeit: datetime | None = None) -> bytes:
    """Kleines fpdf2-PDF ohne Kundendaten („Test-PDF ablegen und prüfen“)."""
    from fpdf import FPDF
    zeit = zeit or datetime.now()
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Helvetica", size=14)
    pdf.cell(0, 10, "Cloover-Ablage-Test - Friondo Angebotstool", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", size=10)
    pdf.cell(0, 8, "Testdatei der PDF-Ablage (ohne Kundendaten) - " + zeit.strftime("%d.%m.%Y %H:%M"),
             new_x="LMARGIN", new_y="NEXT")
    pdf.cell(0, 8, "Diese Datei kann geloescht werden.", new_x="LMARGIN", new_y="NEXT")
    return bytes(pdf.output())


def test_ablage(session) -> tuple[bool, str]:
    """Knopf „Test-PDF ablegen und prüfen“: Konfiguration lesen → Sitzung freigeben → Test-PDF ablegen →
    HEAD prüfen → Ersetzen prüfen → Ergebnis in `cloover_ablage_letzter_test` (der Aufrufer committet)."""
    from app.db import verbindung_freigeben
    konf = konfig(session)
    verbindung_freigeben(session)
    if not konf["bereit"]:
        text = f"Ablage nicht bereit: {konf['grund']}"
        letzten_test_merken(session, False, text)
        return False, text
    tmp = None
    url = ""
    try:
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as datei:
            datei.write(test_pdf_bytes())
            tmp = Path(datei.name)
        name = "TEST-" + secrets.token_urlsafe(6).replace("_", "-") + ".pdf"
        ablage = ablegen(tmp, name, konf)
        url = ablage.get("url") or ""
        ok, meldung = pruefen(url)
        if not ok:
            text = f"Test-PDF abgelegt ({ablage['anbieter']}), aber nicht öffentlich abrufbar: {meldung}"
            letzten_test_merken(session, False, text, url)
            return False, text
        ersetzen(ablage, tmp, konf)
        text = (f"Ablage OK ({ANBIETER_NAMEN[ablage['anbieter']].split(' (')[0]}): {name} abgelegt, "
                f"{meldung}, Ersetzen geprüft, Link gültig bis {ablage.get('ablauf', '–')}")
        letzten_test_merken(session, True, text, url)
        return True, text
    except AblageFehler as fehler:
        text = f"Ablage fehlgeschlagen: {fehler.meldung}"
        letzten_test_merken(session, False, text, url)
        return False, text
    except Exception as fehler:   # noqa: BLE001
        text = f"Ablage fehlgeschlagen: {type(fehler).__name__}: {str(fehler)[:160]}"
        letzten_test_merken(session, False, text, url)
        return False, text
    finally:
        if tmp is not None:
            tmp.unlink(missing_ok=True)
