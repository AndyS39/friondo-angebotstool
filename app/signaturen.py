# E-Mail-Signaturen (v6, Phase 42): je Innendienst-Benutzer die echte
# Outlook-Signatur (HTML-Datei + Bilder), hochgeladen in der Parametrierung.
# Ablage unter data/signaturen/<benutzer_id>/; beim Versand werden die Bilder
# als Inline-Anhänge (CID) eingebettet – Darstellung exakt wie in Outlook.
# Fallback: schlichte Standard-Signatur der Firma (Text aus den Firmendaten).

import re
import shutil
from pathlib import Path

from app import config

BILD_ENDUNGEN = {".png", ".jpg", ".jpeg", ".gif", ".bmp"}
BILD_TYPEN = {".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
              ".gif": "image/gif", ".bmp": "image/bmp"}

STANDARD_SIGNATUR_HTML = (
    "<p>Mit freundlichen Grüßen<br><strong>Ihr Friondo-Team</strong></p>"
    "<p>Friondo GmbH · Arnold-Overbeck-Str. 63-65 · 47139 Duisburg<br>"
    "Telefon: +49 (0) 203 / 396571-0 · "
    "<a href=\"https://www.friondo.de\">www.friondo.de</a><br>"
    "Amtsgericht Duisburg HRB 34795</p>")


def _ordner(benutzer_id: int) -> Path:
    return config.DATA_ORDNER / "signaturen" / str(benutzer_id)


def vorhanden(benutzer_id: int) -> bool:
    return bool(_html_datei(benutzer_id))


def _html_datei(benutzer_id: int) -> Path | None:
    ordner = _ordner(benutzer_id)
    if not ordner.exists():
        return None
    for datei in sorted(ordner.iterdir()):
        if datei.suffix.lower() in (".htm", ".html"):
            return datei
    return None


def _html_lesen(datei: Path) -> str:
    """Outlook speichert .htm meist als windows-1252 (charset-Meta)."""
    roh = datei.read_bytes()
    for codec in ("utf-8", "windows-1252", "latin-1"):
        try:
            return roh.decode(codec)
        except UnicodeDecodeError:
            continue
    return roh.decode("utf-8", errors="replace")


def speichern(benutzer_id: int, dateien: list[tuple[str, bytes]]) -> tuple[bool, str]:
    """Upload aus der Parametrierung: genau eine .htm/.html plus Bilder.
    Ersetzt eine vorhandene Signatur komplett."""
    html = [(n, d) for n, d in dateien if Path(n).suffix.lower() in (".htm", ".html")]
    bilder = [(n, d) for n, d in dateien
              if Path(n).suffix.lower() in BILD_ENDUNGEN]
    if len(html) != 1:
        return False, ("Bitte genau EINE .htm-Datei auswählen (plus die Bilder "
                       "aus dem zugehörigen Dateien-Ordner).")
    ordner = _ordner(benutzer_id)
    if ordner.exists():
        shutil.rmtree(ordner)
    ordner.mkdir(parents=True)
    for name, daten in html + bilder:
        # nur der Dateiname, keine Pfade (Browser liefern je nach OS Pfade mit)
        sicher = Path(name).name
        (ordner / sicher).write_bytes(daten)
    return True, f"Signatur gespeichert ({len(bilder)} Bild{'er' if len(bilder) != 1 else ''})."


def entfernen(benutzer_id: int) -> None:
    ordner = _ordner(benutzer_id)
    if ordner.exists():
        shutil.rmtree(ordner)


def _koerper(html: str) -> str:
    """Nur den Body-Inhalt der Outlook-Datei übernehmen (ohne <html>-Gerüst)."""
    m = re.search(r"<body[^>]*>(.*)</body>", html, re.S | re.I)
    return m.group(1) if m else html


def fuer_versand(benutzer_id: int) -> tuple[str, list[tuple[str, Path, str]]]:
    """Signatur-HTML mit cid:-Bildverweisen + Liste der Inline-Bilder
    [(content_id, pfad, mime_typ)]. Ohne hochgeladene Signatur: Standard."""
    datei = _html_datei(benutzer_id)
    if datei is None:
        return STANDARD_SIGNATUR_HTML, []
    ordner = datei.parent
    html = _koerper(_html_lesen(datei))
    bilder: list[tuple[str, Path, str]] = []
    vergeben: dict[str, str] = {}   # Dateiname -> cid

    def ersetzen(m):
        quelle = m.group(2)
        if quelle.startswith(("http:", "https:", "data:", "cid:")):
            return m.group(0)
        name = Path(quelle.replace("\\", "/").split("?")[0]).name
        pfad = ordner / name
        if not pfad.exists() or pfad.suffix.lower() not in BILD_ENDUNGEN:
            return m.group(0)
        if name not in vergeben:
            cid = f"sig{benutzer_id}-{len(vergeben)}"
            vergeben[name] = cid
            bilder.append((cid, pfad, BILD_TYPEN[pfad.suffix.lower()]))
        return f'{m.group(1)}cid:{vergeben[name]}{m.group(3)}'

    html = re.sub(r'(src=["\'])([^"\']+)(["\'])', ersetzen, html, flags=re.I)
    return html, bilder


def dateien_auflisten(benutzer_id: int) -> list[str]:
    ordner = _ordner(benutzer_id)
    if not ordner.exists():
        return []
    return sorted(d.name for d in ordner.iterdir())
