# v35 (PLAN_LEAD_V6 Phase 185, Agent R): Profilbild je Benutzer – „Mein Profil“
# (/einstellungen/profil). Dieselbe Ablage wie das Vertriebler-Bild aus v29
# (data/benutzerbilder/<id>.<ext>, benutzer.bild_datei relativ zu DATA_ORDNER), damit die
# Terminbestätigung ({vertriebler_block}, lead_mail.bild_pfad) das Bild unverändert findet.
# Hier liegt nur die Datei-Seite (ohne Datenbank): Prüfen, quadratisch zuschneiden
# (Mitte) und auf 512 px verkleinern [ANNAHME], als JPEG ablegen, URL für die
# Avatar-Makros (profilbild_url, Cache-Busting über die Änderungszeit). Die Routen
# in app/routers/einstellungen.py lesen das Formular VOR dem ersten Datenbankzugriff,
# schreiben die Datei ohne offene Sitzung und setzen erst danach benutzer.bild_datei.
import io
import os
import time
from pathlib import Path

from app import config

ORDNER = config.DATA_ORDNER / "benutzerbilder"
ENDUNGEN = (".jpg", ".jpeg", ".png")          # Reihenfolge = Vorrang bei mehreren Dateien
MIME = {".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png"}
KANTE = 512                                   # Zielgröße (quadratisch) [ANNAHME]
MAX_BYTES = 2 * 1024 * 1024                   # 2 MB (Plan)
JPEG_QUALITAET = 88
BILD_PFAD = "/einstellungen/profil/bild/"     # Bild-Route (angemeldet, Cache-Header)
CACHE_SEKUNDEN = 30                           # Ordnerliste je Prozess – nicht je Avatar ein stat()

_cache: dict = {"stand": 0.0, "dateien": {}}


def _dateien(frisch: bool = False) -> dict:
    """{benutzer_id: (Pfad, mtime)} aus dem Ordner (eine Verzeichnisliste, 30 s gecacht)."""
    jetzt = time.monotonic()
    if not frisch and _cache["dateien"] and jetzt - _cache["stand"] < CACHE_SEKUNDEN:
        return _cache["dateien"]
    dateien: dict = {}
    try:
        eintraege = list(os.scandir(ORDNER))
    except OSError:
        eintraege = []
    for eintrag in eintraege:
        name = eintrag.name.lower()
        stamm, punkt, endung = name.rpartition(".")
        if not punkt or ("." + endung) not in ENDUNGEN or not stamm.isdigit():
            continue
        try:
            mtime = eintrag.stat().st_mtime
        except OSError:
            continue
        nr = int(stamm)
        alt = dateien.get(nr)
        # mehrere Dateien je Benutzer (z. B. alte .png neben neuer .jpg): die jüngste gewinnt
        if alt is None or mtime > alt[1]:
            dateien[nr] = (Path(eintrag.path), mtime)
    _cache["dateien"] = dateien
    _cache["stand"] = jetzt
    return dateien


def cache_leeren() -> None:
    _cache["dateien"] = {}
    _cache["stand"] = 0.0


def pfad_fuer(benutzer_id) -> Path | None:
    """Pfad des Profilbilds (jpg/jpeg/png) oder None."""
    try:
        nr = int(benutzer_id or 0)
    except (TypeError, ValueError):
        return None
    if nr <= 0:
        return None
    eintrag = _dateien().get(nr)
    if eintrag is None:
        return None
    pfad = eintrag[0]
    return pfad if pfad.exists() else None


def url_fuer(benutzer_id) -> str:
    """URL für <img> in den Avatar-Makros (leer = kein Bild → Initialen). Die Änderungszeit
    hängt als ?v= an, damit Browser nach einem Upload nicht das alte Bild zeigen."""
    try:
        nr = int(benutzer_id or 0)
    except (TypeError, ValueError):
        return ""
    eintrag = _dateien().get(nr) if nr > 0 else None
    if eintrag is None:
        return ""
    return f"{BILD_PFAD}{nr}?v={int(eintrag[1])}"


def mime_fuer(pfad: Path) -> str:
    return MIME.get(pfad.suffix.lower(), "application/octet-stream")


def verarbeiten(daten: bytes) -> tuple[bytes | None, str]:
    """Bilddaten prüfen (JPG/PNG), EXIF-Drehung anwenden, quadratisch aus der Mitte
    zuschneiden, auf KANTE verkleinern, als JPEG liefern. (bytes | None, Fehlertext)."""
    if not daten:
        return None, "Keine Datei gewählt."
    if len(daten) > MAX_BYTES:
        return None, "Bild nicht gespeichert: größer als 2 MB."
    try:
        from PIL import Image, ImageOps
    except ImportError:   # pragma: no cover – Pillow steht in requirements.txt
        return None, "Bildverarbeitung nicht verfügbar (Pillow fehlt)."
    try:
        bild = Image.open(io.BytesIO(daten))
        bild_format = (bild.format or "").upper()
        if bild_format not in ("JPEG", "PNG"):
            return None, "Bild nicht gespeichert: nur JPG oder PNG."
        bild = ImageOps.exif_transpose(bild) or bild
        if bild.mode in ("RGBA", "LA", "P"):
            # Transparenz auf weißen Grund legen (JPEG kennt keinen Alphakanal)
            grund = Image.new("RGB", bild.size, (255, 255, 255))
            quelle = bild.convert("RGBA")
            grund.paste(quelle, mask=quelle.split()[-1])
            bild = grund
        else:
            bild = bild.convert("RGB")
        breite, hoehe = bild.size
        kante = min(breite, hoehe)
        if kante <= 0:
            return None, "Bild ist leer."
        links = (breite - kante) // 2
        oben = (hoehe - kante) // 2
        bild = bild.crop((links, oben, links + kante, oben + kante))
        if kante > KANTE:
            bild = bild.resize((KANTE, KANTE), Image.LANCZOS)
        puffer = io.BytesIO()
        bild.save(puffer, format="JPEG", quality=JPEG_QUALITAET, optimize=True)
        return puffer.getvalue(), ""
    except Exception:   # noqa: BLE001 – defekte/unlesbare Datei
        return None, "Bild nicht lesbar – bitte eine JPG- oder PNG-Datei wählen."


def speichern(benutzer_id: int, daten: bytes) -> tuple[bool, str, str]:
    """Profilbild ablegen: (ok, Meldung, relativer Pfad für benutzer.bild_datei).
    Schreibt <id>.jpg (erst Temporärdatei, dann Austausch) und entfernt ältere
    Varianten (.png/.jpeg) desselben Benutzers – kein Datenbankzugriff."""
    fertig, fehler = verarbeiten(daten)
    if fertig is None:
        return False, fehler, ""
    nr = int(benutzer_id)
    ORDNER.mkdir(parents=True, exist_ok=True)
    ziel = ORDNER / f"{nr}.jpg"
    tmp = ORDNER / f"{nr}.jpg.tmp"
    tmp.write_bytes(fertig)
    os.replace(tmp, ziel)
    for endung in ENDUNGEN:
        alt = ORDNER / f"{nr}{endung}"
        if alt.resolve() != ziel.resolve() and alt.exists():
            try:
                alt.unlink()
            except OSError:
                pass
    cache_leeren()
    return True, "Profilbild gespeichert.", f"benutzerbilder/{nr}.jpg"


def entfernen(benutzer_id: int) -> bool:
    """Alle Bilddateien des Benutzers löschen (kein Datenbankzugriff); True, wenn eine da war."""
    nr = int(benutzer_id)
    weg = False
    for endung in ENDUNGEN:
        pfad = ORDNER / f"{nr}{endung}"
        if pfad.exists():
            try:
                pfad.unlink()
                weg = True
            except OSError:
                pass
    cache_leeren()
    return weg
