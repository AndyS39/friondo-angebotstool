# Galerie am Vorgang (v15, PLAN_PROJ_V2 Phase 76): feste Unterordner,
# Ablage data/vorgaenge/<vorgang_id>/galerie/<ordner>/, Bilder werden
# serverseitig auf max. 2000 px verkleinert. Vorgangsakte und Projektakte
# zeigen dieselbe Komponente (_galerie.html); Sub-Mails (Phase 79) und der
# Montage-Steckbrief (Phase 82) greifen auf die Ordner zu.

import re
import shutil
from datetime import datetime
from pathlib import Path

from sqlalchemy.orm import Session

from app import config
from app.models import GalerieDatei, Projekt, ProjektDokument, Vorgang

# Reihenfolge und Namen exakt laut Plan (Standardordner nicht löschbar)
STANDARD_ORDNER = ["Alte Heizung", "Elektro", "Außengerät", "Öl-Tank",
                   "Montagedokumente", "Inbetrieb-/Abnahme", "Neue Anlage",
                   "Allgemein"]

BILD_ENDUNGEN = {".jpg", ".jpeg", ".png", ".gif", ".webp", ".heic", ".bmp"}
MAX_KANTE = 2000


def ordner_liste(session: Session) -> list[str]:
    """Standardordner + Zusatzordner aus der Parametrierung (| getrennt)."""
    from app import projektierung as kern
    zusatz = [o.strip() for o in
              kern.parameter_holen(session, "galerie_zusatzordner", "").split("|")
              if o.strip()]
    return STANDARD_ORDNER + [o for o in zusatz if o not in STANDARD_ORDNER]


def _sicherer_name(name: str) -> str:
    name = re.sub(r"[^\w.ÄÖÜäöüß \-]", "_",
                  name or "datei")
    return name[:150] or "datei"


def _basis(vorgang_id: int) -> Path:
    return config.DATA_ORDNER / "vorgaenge" / str(vorgang_id) / "galerie"


def ist_bild(dateiname: str) -> bool:
    return Path(dateiname).suffix.lower() in BILD_ENDUNGEN


def _verkleinern(pfad: Path) -> None:
    """Bilder auf max. 2000 px Kante verkleinern (Original optional behalten
    über Parameter galerie_original_behalten = an)."""
    try:
        from PIL import Image, ImageOps
        with Image.open(pfad) as bild:
            bild = ImageOps.exif_transpose(bild)
            if max(bild.size) <= MAX_KANTE:
                return
            bild.thumbnail((MAX_KANTE, MAX_KANTE))
            bild.save(pfad)
    except Exception:
        pass   # nicht lesbare Bilder bleiben unverändert


def speichern(session: Session, vorgang_id: int, ordner: str, dateiname: str,
              inhalt: bytes, benutzer=None, bemerkung: str = "",
              quelle: str = "upload") -> GalerieDatei | None:
    """Datei in den Galerie-Ordner legen (Bilder verkleinert) + DB-Eintrag."""
    if ordner not in ordner_liste(session):
        ordner = "Allgemein"
    if not inhalt:
        return None
    name = _sicherer_name(dateiname)
    ziel_ordner = _basis(vorgang_id) / ordner.replace("/", "-")
    ziel_ordner.mkdir(parents=True, exist_ok=True)
    ziel = ziel_ordner / name
    zaehler = 1
    while ziel.exists():
        ziel = ziel_ordner / f"{Path(name).stem}_{zaehler}{Path(name).suffix}"
        zaehler += 1
    ziel.write_bytes(inhalt)
    if ist_bild(name):
        from app import projektierung as kern
        if kern.parameter_holen(session, "galerie_original_behalten", "aus") == "an":
            original = ziel_ordner / f"original_{ziel.name}"
            shutil.copy2(ziel, original)
        _verkleinern(ziel)
    eintrag = GalerieDatei(
        vorgang_id=vorgang_id, ordner=ordner, dateiname=ziel.name,
        pfad=str(ziel.relative_to(config.DATA_ORDNER)),
        bild=ist_bild(ziel.name), bemerkung=(bemerkung or "").strip()[:300],
        quelle=quelle,
        hochgeladen_von=benutzer.id if benutzer else None)
    session.add(eintrag)
    session.flush()
    return eintrag


def uebersicht(session: Session, vorgang_id: int) -> dict:
    """Je Ordner: Anzahl, Vorschaubild (erste Bilddatei), Einträge."""
    daten = {o: {"eintraege": [], "vorschau": None} for o in ordner_liste(session)}
    for d in (session.query(GalerieDatei)
              .filter(GalerieDatei.vorgang_id == vorgang_id)
              .order_by(GalerieDatei.hochgeladen_am.desc(), GalerieDatei.id.desc())):
        eintrag = daten.setdefault(d.ordner, {"eintraege": [], "vorschau": None})
        eintrag["eintraege"].append(d)
        if d.bild and eintrag["vorschau"] is None:
            eintrag["vorschau"] = d
    return daten


def verschieben(session: Session, datei: GalerieDatei, ziel_ordner: str) -> bool:
    if ziel_ordner not in ordner_liste(session) or ziel_ordner == datei.ordner:
        return False
    quelle = config.DATA_ORDNER / datei.pfad
    ziel_dir = _basis(datei.vorgang_id) / ziel_ordner.replace("/", "-")
    ziel_dir.mkdir(parents=True, exist_ok=True)
    ziel = ziel_dir / datei.dateiname
    zaehler = 1
    while ziel.exists():
        ziel = ziel_dir / f"{Path(datei.dateiname).stem}_{zaehler}{Path(datei.dateiname).suffix}"
        zaehler += 1
    if quelle.exists():
        shutil.move(str(quelle), str(ziel))
    datei.ordner = ziel_ordner
    datei.dateiname = ziel.name
    datei.pfad = str(ziel.relative_to(config.DATA_ORDNER))
    return True


def loeschen(session: Session, datei: GalerieDatei) -> None:
    pfad = config.DATA_ORDNER / datei.pfad
    if pfad.exists():
        pfad.unlink()
    session.delete(datei)


def _montage_zugriff(session: Session, vorgang: Vorgang, benutzer) -> bool:
    """v15 (Phase 82): Montage sieht die Galerie der Vorgänge, deren Gewerke
    einem eigenen Team zugewiesen oder terminiert sind."""
    from app.models import Angebot, Gewerk, ProjektTermin, TeamMitglied
    team_ids = [m.team_id for m in session.query(TeamMitglied)
                .filter(TeamMitglied.benutzer_id == benutzer.id)]
    if not team_ids:
        return False
    gewerk_ids = [g.id for g in
                  session.query(Gewerk)
                  .join(Angebot, Angebot.projekt_gewerk_id == Gewerk.id)
                  .filter(Angebot.vorgang_id == vorgang.id)]
    if not gewerk_ids:
        return False
    for g in session.query(Gewerk).filter(Gewerk.id.in_(gewerk_ids)):
        if any(tid in team_ids for tid in
               (g.wp_team_id, g.elektro_team_id, g.sub_team_id) if tid):
            return True
    return bool(session.query(ProjektTermin)
                .filter(ProjektTermin.gewerk_id.in_(gewerk_ids),
                        ProjektTermin.team_id.in_(team_ids)).first())


def darf_hochladen(session: Session, vorgang: Vorgang, benutzer) -> bool:
    """Vertrieb: eigene Vorgänge (auch ohne Auftrag); ID/Projektierung/Admin:
    alles; Montage (v15, Phase 82): Vorgänge der eigenen Team-Einsätze
    (ansehen + hochladen, nie löschen)."""
    if benutzer is None:
        return False
    if benutzer.rolle in ("admin", "innendienst", "projektierung"):
        return True
    if benutzer.rolle == "aussendienst":
        from app.routers.vorgaenge import _eigener
        return _eigener(session, vorgang, benutzer)
    if benutzer.hat_rolle("montage"):
        return _montage_zugriff(session, vorgang, benutzer)
    return False


def darf_loeschen(benutzer) -> bool:
    return benutzer is not None and benutzer.rolle in (
        "admin", "innendienst", "projektierung")


# --- Migration (Phase 76): data/projekte/<PR>/… → Galerie des Vorgangs -----

_ALT_MAPPING = [("Alte Anlage", "Alte Heizung"),
                ("Zählerschrank", "Elektro"),
                ("Außengerät", "Außengerät"),
                ("Öltank", "Öl-Tank"),
                ("05 Montage", "Montagedokumente"),
                ("Feinplanung & Heizlast", "Montagedokumente"),
                ("Neue Anlage", "Neue Anlage")]


def _ziel_ordner_fuer(alt_ordner: str) -> str:
    for teil, neu in _ALT_MAPPING:
        if teil in (alt_ordner or ""):
            return neu
    return "Allgemein"


def altbestand_migrieren(session: Session) -> int:
    """Bestehende Projekt-Dokumente in die Galerie des zugehörigen Vorgangs
    verschieben (idempotent über den Migrations-Schalter in migrate.py)."""
    umgezogen = 0
    for dok in session.query(ProjektDokument).all():
        projekt = session.get(Projekt, dok.projekt_id)
        if projekt is None or not projekt.vorgang_id:
            continue
        quelle = config.DATA_ORDNER / dok.pfad if dok.pfad else None
        if quelle is None or not quelle.exists():
            session.delete(dok)
            continue
        ordner = _ziel_ordner_fuer(dok.ordner)
        eintrag = speichern(session, projekt.vorgang_id, ordner, dok.dateiname,
                            quelle.read_bytes(), benutzer=None,
                            bemerkung=f"aus Projektordner {dok.ordner}",
                            quelle="migration")
        if eintrag is not None:
            eintrag.hochgeladen_von = dok.hochgeladen_von
            quelle.unlink()
            session.delete(dok)
            umgezogen += 1
    return umgezogen
