# Galerie am Vorgang (v15, PLAN_PROJ_V2 Phase 76): feste Unterordner,
# Ablage data/vorgaenge/<vorgang_id>/galerie/<ordner>/, Bilder werden
# serverseitig auf max. 2000 px verkleinert. Vorgangsakte und Projektakte
# zeigen dieselbe Komponente (_galerie.html); Sub-Mails (Phase 79) und der
# Montage-Steckbrief (Phase 82) greifen auf die Ordner zu.
# v35 (PLAN_LEAD_V6 Phase 186, Agent G): Fotos je Objekt – je aktivem Objekt des Vorgangs
# (vorgang_objekte, v31) ein Galerie-Ordner „Objekt <Bezeichnung>“ (Ein-Objekt-Vorgang:
# „Objekt“), Upload direkt an der Objektkarte der Kundenkartei (Abschnitt „Fotos je Objekt“
# unten), HEIC/HEIF → JPG beim Speichern (auch für alle übrigen Uploads), Zuordnung über den
# Ordnernamen, solange galerie_dateien keine Spalte objekt_id hat (wird automatisch genutzt,
# sobald das Modell sie trägt – siehe _objekt_id_spalte).

import re
import shutil
from datetime import datetime
from pathlib import Path

from sqlalchemy.orm import Session

from app import config
from app.models import GalerieDatei, Projekt, ProjektDokument, Vorgang

# Reihenfolge und Namen exakt laut Plan (Standardordner nicht löschbar).
# 27.09.2026 (Andreas): eigene Galerie je Sparte - WP behaelt die acht
# Plan-Ordner, PV/KL/WB bekommen passende Ordner + die gemeinsamen vier.
# V4 (Phase 92): „Förderung“ (BzA-PDF u. a.) für alle Sparten
# v33 (PLAN_V20 Phase 168): Ordner „Service“ für Servicebericht-PDFs und Service-Fotos
GEMEINSAME_ORDNER = ["Montagedokumente", "Förderung", "Inbetrieb-/Abnahme",
                     "Neue Anlage", "Service", "Allgemein"]
SPARTEN_ORDNER = {
    "WP": ["Alte Heizung", "Elektro", "Außengerät", "Öl-Tank"]
          + GEMEINSAME_ORDNER,
    "PV": ["Dachfläche", "Zählerschrank", "Speicher-Standort"]
          + GEMEINSAME_ORDNER,
    "KL": ["Innengeräte", "Außengerät", "Leitungsweg"]
          + GEMEINSAME_ORDNER,
    "WB": ["Stellplatz", "Zählerschrank", "Leitungsweg"]
          + GEMEINSAME_ORDNER,
    # v31 (PLAN_LEAD_V5 Phase 157): Freitext-Sparten ohne eigene Fachordner –
    # Gewerbe, Mieterstrom, Wasser, Denkmalschutz nutzen die gemeinsamen Ordner
    "GW": ["Zählerschrank", "Bestand"] + GEMEINSAME_ORDNER,
    "MS": ["Zählerschrank", "Dachfläche"] + GEMEINSAME_ORDNER,
    "WA": ["Hausanschluss", "Bestand"] + GEMEINSAME_ORDNER,
    "DMS": ["Fassade", "Bestand"] + GEMEINSAME_ORDNER,
}
STANDARD_ORDNER = SPARTEN_ORDNER["WP"]   # Rueckwaerts-Kompatibilitaet


def sparte_pruefen(sparte: str) -> str:
    return sparte if sparte in SPARTEN_ORDNER else "WP"

BILD_ENDUNGEN = {".jpg", ".jpeg", ".png", ".gif", ".webp", ".heic", ".bmp"}
MAX_KANTE = 2000


def ordner_liste(session: Session, sparte: str = "WP", vorgang=None) -> list[str]:
    """Sparten-Ordner + Zusatzordner aus der Parametrierung (| getrennt).
    v35 (PLAN_LEAD_V6 Phase 186): mit `vorgang` (Vorgang oder Vorgangs-ID) zusätzlich je
    aktivem Objekt des Vorgangs der Ordner „Objekt <Bezeichnung>“ (Ein-Objekt-Vorgang:
    „Objekt“) – hinter den Sparten-Ordnern, vor den Zusatzordnern; ersetzt nichts
    Bestehendes. Ohne `vorgang` bleibt die Liste wie bisher (Parametrierung, Heizreport)."""
    from app import projektierung as kern
    basis = list(SPARTEN_ORDNER[sparte_pruefen(sparte)])
    if vorgang is not None:
        for name, _objekt in objekt_ordner(session, vorgang):
            if name not in basis:
                basis.append(name)
    zusatz = [o.strip() for o in
              kern.parameter_holen(session, "galerie_zusatzordner", "").split("|")
              if o.strip()]
    return basis + [o for o in zusatz if o not in basis]


def _sicherer_name(name: str) -> str:
    name = re.sub(r"[^\w.ÄÖÜäöüß \-]", "_",
                  name or "datei")
    return name[:150] or "datei"


def _basis(vorgang_id: int) -> Path:
    return config.DATA_ORDNER / "vorgaenge" / str(vorgang_id) / "galerie"


def ist_bild(dateiname: str) -> bool:
    return Path(dateiname).suffix.lower() in BILD_ENDUNGEN


# v28 (PLAN_PROJ_V6 Phase 136): Dateitypen, die die Datei-Route
# /vorgaenge/galerie/datei/{id} `inline` ausliefert (Lightbox, „PDF ansehen“);
# alles andere bleibt ein Download (attachment). ?download=1 erzwingt attachment.
INLINE_ENDUNGEN = BILD_ENDUNGEN | {".pdf"}


def inline_anzeige(dateiname: str) -> bool:
    return Path(dateiname or "").suffix.lower() in INLINE_ENDUNGEN


def datei_url(datei_id: int, herunterladen: bool = False) -> str:
    """Adresse der Datei-Route; mit `herunterladen` = Download-Knopf der Lightbox."""
    return f"/vorgaenge/galerie/datei/{datei_id}" + ("?download=1" if herunterladen else "")


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


STREAM_BLOCK = 1024 * 1024


def _datei_schreiben(ziel: Path, inhalt) -> int:
    """v27 (PLAN_V17 Phase 128): Bytes direkt schreiben, Datei-Objekte
    (UploadFile.file) in 1-MB-Blöcken auf die Platte streamen – keine
    50-MB-Datei im Speicher. Liefert die geschriebene Größe."""
    if isinstance(inhalt, (bytes, bytearray)):
        ziel.write_bytes(inhalt)
        return len(inhalt)
    try:
        inhalt.seek(0)
    except Exception:
        pass
    groesse = 0
    with ziel.open("wb") as ausgabe:
        while True:
            block = inhalt.read(STREAM_BLOCK)
            if not block:
                break
            ausgabe.write(block)
            groesse += len(block)
    return groesse


def speichern(session: Session, vorgang_id: int, ordner: str, dateiname: str,
              inhalt, benutzer=None, bemerkung: str = "",
              quelle: str = "upload", sparte: str = "WP") -> GalerieDatei | None:
    """Datei in den Galerie-Ordner der Sparte legen (Bilder verkleinert).
    `inhalt` ist bytes oder ein Datei-Objekt (v27: Upload wird gestreamt)."""
    sparte = sparte_pruefen(sparte)
    # v35: Objekt-Ordner des Vorgangs sind erlaubte Ziele (ordner_liste mit vorgang)
    if ordner not in ordner_liste(session, sparte, vorgang=vorgang_id):
        ordner = "Allgemein"
    if inhalt is None or (isinstance(inhalt, (bytes, bytearray)) and not inhalt):
        return None
    name = _sicherer_name(dateiname)
    ziel_ordner = _basis(vorgang_id) / sparte / ordner.replace("/", "-")
    ziel_ordner.mkdir(parents=True, exist_ok=True)
    ziel = _freier_pfad(ziel_ordner, name)
    if _datei_schreiben(ziel, inhalt) == 0:
        ziel.unlink(missing_ok=True)
        return None
    if ist_bild(name) or ist_heic(ziel):
        from app import projektierung as kern
        if kern.parameter_holen(session, "galerie_original_behalten", "aus") == "an":
            original = ziel_ordner / f"original_{ziel.name}"
            shutil.copy2(ziel, original)
        # v35 (PLAN_LEAD_V6 Phase 186): HEIC/HEIF (iPhone) → JPG – Browser zeigen HEIC nicht an
        if ist_heic(ziel):
            gewandelt = _heic_nach_jpg(ziel)
            if gewandelt is not None:
                ziel = gewandelt
        _verkleinern(ziel)
    eintrag = GalerieDatei(
        vorgang_id=vorgang_id, sparte=sparte, ordner=ordner,
        dateiname=ziel.name,
        pfad=str(ziel.relative_to(config.DATA_ORDNER)),
        bild=ist_bild(ziel.name), bemerkung=(bemerkung or "").strip()[:300],
        quelle=quelle,
        hochgeladen_von=benutzer.id if benutzer else None)
    _objekt_id_setzen(session, eintrag)   # v35: sobald galerie_dateien.objekt_id existiert
    session.add(eintrag)
    session.flush()
    return eintrag


def uebersicht(session: Session, vorgang_id: int, sparte: str = "WP") -> dict:
    """Je Ordner der Sparte: Anzahl, Vorschaubild, Einträge."""
    sparte = sparte_pruefen(sparte)
    daten = {o: {"eintraege": [], "vorschau": None}
             for o in ordner_liste(session, sparte, vorgang=vorgang_id)}   # v35: + Objekt-Ordner
    # v35: Fotos unter einem früheren Objekt-Ordnernamen („Objekt“ aus der Ein-Objekt-Zeit,
    # Name vor einer Umbenennung) erscheinen unter dem heutigen Ordner des Objekts
    alt_nach_neu: dict[str, str] = {}
    for d in (session.query(GalerieDatei)
              .filter(GalerieDatei.vorgang_id == vorgang_id,
                      GalerieDatei.sparte == sparte)
              .order_by(GalerieDatei.hochgeladen_am.desc(), GalerieDatei.id.desc())):
        ordner = d.ordner
        if ordner not in daten:
            if ordner not in alt_nach_neu:
                alt_nach_neu[ordner] = aktueller_objekt_ordner(session, vorgang_id, ordner) or ordner
            ordner = alt_nach_neu[ordner]
        eintrag = daten.setdefault(ordner, {"eintraege": [], "vorschau": None})
        eintrag["eintraege"].append(d)
        if d.bild and eintrag["vorschau"] is None:
            eintrag["vorschau"] = d
    return daten


def verschieben(session: Session, datei: GalerieDatei, ziel_ordner: str) -> bool:
    # v35: „Einsortieren“ aus der Sammelbox auch in den Objekt-Ordner (ordner_liste mit vorgang)
    if (ziel_ordner not in ordner_liste(session, datei.sparte, vorgang=datei.vorgang_id)
            or ziel_ordner == datei.ordner):
        return False
    quelle = config.DATA_ORDNER / datei.pfad
    ziel_dir = (_basis(datei.vorgang_id) / sparte_pruefen(datei.sparte)
                / ziel_ordner.replace("/", "-"))
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
    _objekt_id_setzen(session, datei)   # v35: Objekt-Zuordnung folgt dem Ordner
    return True


def loeschen(session: Session, datei: GalerieDatei) -> None:
    pfad = config.DATA_ORDNER / datei.pfad
    if pfad.exists():
        pfad.unlink()
    session.delete(datei)


# --- v34 (PLAN_V21 Phase 181): mehrere Dateien in EINEM Request, Teilerfolg je Datei -------

def _wert_an(liste, nr: int) -> str:
    try:
        return (liste[nr] or "").strip() if nr < len(liste) else ""
    except (TypeError, AttributeError):
        return ""


def _fehlergrund(fehler: Exception) -> str:
    text = str(fehler) or fehler.__class__.__name__
    if "locked" in text.lower():
        return "Datenbank kurz belegt – bitte erneut versuchen"
    return text[:120]


def mehrfach_speichern(session: Session, vorgang_id: int, dateien, ordner_je_datei=(),
                       bemerkung_je_datei=(), *, standard_ordner: str = "Allgemein",
                       standard_bemerkung: str = "", benutzer=None, sparte: str = "WP",
                       quelle: str = "upload") -> dict:
    """Mehrere Upload-Dateien (Starlette UploadFile) mit Ordner und Bemerkung je Datei
    (positionsgleiche Listen `datei_ordner` / `datei_bemerkung`; leer = Standard) ablegen.
    Commit je Datei (Block = eine Datei): eine leere oder unlesbare Datei bzw. „database is
    locked“ bei einer späten Datei lässt die bereits abgelegten stehen – Teilerfolg.
    Rückgabe {"abgelegt": [{nr, id, name, ordner}], "fehler": [{nr, name, grund}],
    "ordner": [benutzte Ordner]}; Dateifelder ohne Dateinamen (leere Formularfelder)
    werden übersprungen."""
    sparte = sparte_pruefen(sparte)
    erlaubt = ordner_liste(session, sparte, vorgang=vorgang_id)   # v35: + Objekt-Ordner
    ergebnis: dict = {"abgelegt": [], "fehler": [], "ordner": []}
    for nr, datei in enumerate(dateien or []):
        name = getattr(datei, "filename", "") or ""
        if not name:
            continue
        ziel_ordner = _wert_an(ordner_je_datei, nr) or (standard_ordner or "Allgemein")
        if ziel_ordner not in erlaubt:
            ziel_ordner = "Allgemein"
        bemerkung = _wert_an(bemerkung_je_datei, nr) or (standard_bemerkung or "")
        eintrag = None
        try:
            eintrag = speichern(session, vorgang_id, ziel_ordner, name,
                                getattr(datei, "file", datei), benutzer=benutzer,
                                bemerkung=bemerkung, quelle=quelle, sparte=sparte)
            if eintrag is None:
                raise ValueError("Datei ist leer")
            session.commit()
        except Exception as fehler:   # noqa: BLE001 – je Datei gemeldet, nie die ganze Anfrage
            session.rollback()
            if eintrag is not None and getattr(eintrag, "pfad", ""):
                (config.DATA_ORDNER / eintrag.pfad).unlink(missing_ok=True)
            ergebnis["fehler"].append({"nr": nr, "name": name[:150],
                                       "grund": _fehlergrund(fehler)})
            continue
        ergebnis["abgelegt"].append({"nr": nr, "id": eintrag.id, "name": eintrag.dateiname,
                                     "ordner": eintrag.ordner})
        if eintrag.ordner not in ergebnis["ordner"]:
            ergebnis["ordner"].append(eintrag.ordner)
    return ergebnis


def meldung_fuer(ergebnis: dict, standard_ordner: str = "") -> str:
    """Meldung für Redirect/JSON: „3 Datei(en) abgelegt (Aufstellort, Zählerschrank).“ bzw.
    bei Teilerfolg „2 von 3 Dateien abgelegt (…) – nicht abgelegt: x.pdf (Datei ist leer).“"""
    n_ok = len(ergebnis.get("abgelegt", []))
    fehler = ergebnis.get("fehler", [])
    ordner = ", ".join(sorted(ergebnis.get("ordner", []))) or (standard_ordner or "")
    if not fehler:
        return f"{n_ok} Datei(en) abgelegt ({ordner})."
    nicht = "; ".join(f"{f['name']} ({f['grund']})" for f in fehler)
    if n_ok:
        return f"{n_ok} von {n_ok + len(fehler)} Dateien abgelegt ({ordner}) – nicht abgelegt: {nicht}."
    return f"Keine Datei abgelegt – nicht abgelegt: {nicht}."


def _montage_zugriff(session: Session, vorgang: Vorgang, benutzer) -> bool:
    """v15 (Phase 82): Montage sieht die Galerie der Vorgänge, deren Gewerke
    einem eigenen Team zugewiesen oder terminiert sind.
    v33 (PLAN_V20 Phase 168): zusätzlich Vorgänge mit Terminen (Service-Einsätze,
    auch ohne Projekt), in denen der Benutzer eingeteilt ist (Besetzung/Person)."""
    from sqlalchemy import or_
    from app.models import Angebot, Gewerk, ProjektTermin, TeamMitglied, TerminBesetzung
    eigene_termine = [b.termin_id for b in session.query(TerminBesetzung)
                      .filter(TerminBesetzung.benutzer_id == benutzer.id)]
    projekt_ids = [p.id for p in session.query(Projekt).filter(Projekt.vorgang_id == vorgang.id)]
    eingeteilt = (session.query(ProjektTermin)
                  .filter(or_(ProjektTermin.vorgang_id == vorgang.id,
                              ProjektTermin.projekt_id.in_(projekt_ids or [0])),
                          or_(ProjektTermin.id.in_(eigene_termine or [0]),
                              ProjektTermin.person_id == benutzer.id))
                  .first())
    if eingeteilt is not None:
        return True
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
    if benutzer.basisrolle in ("admin", "innendienst", "projektierung"):
        return True
    if benutzer.basisrolle == "aussendienst":
        from app.routers.vorgaenge import _eigener
        return _eigener(session, vorgang, benutzer)
    if benutzer.hat_rolle("montage"):
        return _montage_zugriff(session, vorgang, benutzer)
    return False


def darf_loeschen(benutzer) -> bool:
    return benutzer is not None and benutzer.basisrolle in (
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


# --- v35 (PLAN_LEAD_V6 Phase 186, Agent G): Fotos je Objekt --------------------------------
#
# Die Galerie des Vorgangs bekommt je aktivem Objekt (vorgang_objekte, v31) einen eigenen
# Ordner. Zuordnung Foto ↔ Objekt über den Ordnernamen, solange galerie_dateien keine
# Spalte objekt_id trägt (Rückfall-Regeln für frühere Namen in objekt_ordner_namen); trägt das
# Modell die Spalte (Orchestrator), wird sie beim Speichern/Verschieben gesetzt und beim Lesen
# bevorzugt. Dateien liegen wie bisher unter data/vorgaenge/<id>/galerie/<Sparte>/<Ordner>/.

OBJEKT_PRAEFIX = "Objekt"
OBJEKTFOTO_MAX_BYTES = 10 * 1024 * 1024          # Plan: max. 10 MB je Bild
OBJEKTFOTO_ENDUNGEN = {".jpg", ".jpeg", ".png", ".heic", ".heif"}
OBJEKTFOTO_TYPEN = {"image/jpeg", "image/jpg", "image/pjpeg", "image/png", "image/heic",
                    "image/heif", "image/heic-sequence", "image/heif-sequence"}
HEIC_ENDUNGEN = {".heic", ".heif"}
_HEIC_MARKEN = (b"heic", b"heix", b"hevc", b"hevx", b"heim", b"heis", b"hevm", b"hevs",
                b"mif1", b"msf1", b"heif")
JPG_QUALITAET = 88
OBJEKTFOTOS_LEER = {"darf_hochladen": False, "je_objekt": {}, "einzel": None,
                    "max_mb": OBJEKTFOTO_MAX_BYTES // (1024 * 1024)}


def _freier_pfad(ordner: Path, name: str) -> Path:
    """Nächster freier Dateiname im Ordner (name, name_1, name_2 …)."""
    ziel = ordner / name
    zaehler = 1
    while ziel.exists():
        ziel = ordner / f"{Path(name).stem}_{zaehler}{Path(name).suffix}"
        zaehler += 1
    return ziel


def ist_heic(pfad: Path) -> bool:
    """HEIC/HEIF an der Endung oder am Dateikopf (ftyp-Box mit HEIF-Marke) erkennen –
    iPhones liefern die Fotos je nach Einstellung auch unter falscher Endung."""
    pfad = Path(pfad)
    if pfad.suffix.lower() in HEIC_ENDUNGEN:
        return True
    try:
        with pfad.open("rb") as quelle:
            kopf = quelle.read(16)
    except OSError:
        return False
    return len(kopf) >= 12 and kopf[4:8] == b"ftyp" and kopf[8:12] in _HEIC_MARKEN


def _heic_nach_jpg(pfad: Path) -> Path | None:
    """HEIC/HEIF → JPG daneben (EXIF-Drehung angewandt, längste Kante MAX_KANTE, Qualität
    JPG_QUALITAET); das HEIC wird entfernt. None, wenn die Datei nicht lesbar ist – dann
    bleibt sie unverändert liegen (Aufrufer entscheidet)."""
    pfad = Path(pfad)
    try:
        import pillow_heif
        from PIL import Image, ImageOps
        pillow_heif.register_heif_opener()
        ziel = _freier_pfad(pfad.parent, pfad.stem + ".jpg")
        with Image.open(pfad) as bild:
            bild = ImageOps.exif_transpose(bild)
            if bild.mode not in ("RGB", "L"):
                bild = bild.convert("RGB")
            if max(bild.size) > MAX_KANTE:
                bild.thumbnail((MAX_KANTE, MAX_KANTE))
            bild.save(ziel, format="JPEG", quality=JPG_QUALITAET)
    except Exception:   # noqa: BLE001 – nicht lesbare Datei: Original bleibt
        return None
    pfad.unlink(missing_ok=True)
    return ziel


def _bild_lesbar(pfad: Path) -> bool:
    """Prüft, ob Pillow die Datei als Bild öffnen kann (für JPG/PNG der Objektfotos)."""
    try:
        from PIL import Image
        with Image.open(pfad) as bild:
            bild.verify()
        return True
    except Exception:   # noqa: BLE001
        return False


def _objekt_id_spalte() -> bool:
    """True, sobald das Modell GalerieDatei die Spalte objekt_id trägt (Orchestrator)."""
    return hasattr(GalerieDatei, "objekt_id")


def _objekt_id_setzen(session: Session, datei: GalerieDatei) -> None:
    """objekt_id aus dem Ordnernamen ableiten – nur, wenn die Spalte existiert."""
    if not _objekt_id_spalte():
        return
    objekt = objekt_fuer_ordner(session, datei.vorgang_id, datei.ordner)
    datei.objekt_id = objekt.id if objekt is not None else None


def _ordner_sicher(name: str) -> str:
    """Bezeichnung als Ordnername: keine Pfadzeichen (Windows: \\ / : * ? " < > |),
    Mehrfach-Leerzeichen zusammengezogen."""
    name = re.sub(r'[\\/:*?"<>|]', "-", name or "").strip()
    return re.sub(r"\s+", " ", name)


def objekt_ordner_name(objekt, mehrere: bool) -> str:
    """Ordnername eines Objekts: Ein-Objekt-Vorgang „Objekt“, sonst „Objekt <Bezeichnung>“.
    Eine Bezeichnung, die selbst mit „Objekt“ beginnt (Standard „Objekt 2“), wird nicht
    verdoppelt – „Objekt 2“, nicht „Objekt Objekt 2“. Höchstens 100 Zeichen (Spalte ordner)."""
    if not mehrere:
        return OBJEKT_PRAEFIX
    bez = _ordner_sicher(getattr(objekt, "bezeichnung", "") or "")
    treffer = re.match(r"(?i)^objekt(?:[\s\-–:]+(.*))?$", bez)   # „Objekt 2“ → „2“, „Objektstraße“ bleibt
    if treffer:
        bez = (treffer.group(1) or "").strip()
    if not bez:
        bez = str(getattr(objekt, "reihenfolge", "") or getattr(objekt, "id", "") or "")
    return f"{OBJEKT_PRAEFIX} {bez}".strip()[:100]


def _vorgang_id_von(vorgang) -> int | None:
    if vorgang is None:
        return None
    try:
        return int(getattr(vorgang, "id", vorgang))
    except (TypeError, ValueError):
        return None


def objekt_ordner(session: Session, vorgang) -> list[tuple[str, object]]:
    """(Ordnername, Objekt) je aktivem Objekt des Vorgangs in Reihenfolge; gleiche
    Bezeichnungen bekommen „ (2)“, „ (3)“ … – `vorgang` ist ein Vorgang oder eine ID."""
    from app import objekte as objekte_modul
    vorgang_id = _vorgang_id_von(vorgang)
    if not vorgang_id:
        return []
    objekte = objekte_modul.objekte_fuer(session, vorgang_id)
    mehrere = len(objekte) > 1
    ergebnis, vergeben = [], set()
    for objekt in objekte:
        name = objekt_ordner_name(objekt, mehrere)
        basis, nr = name, 2
        while name in vergeben:
            name = f"{basis} ({nr})"[:100]
            nr += 1
        vergeben.add(name)
        ergebnis.append((name, objekt))
    return ergebnis


def _ist_hauptobjekt(objekt, liste) -> bool:
    if getattr(objekt, "reihenfolge", None) == 1:
        return True
    return bool(liste) and liste[0][1].id == objekt.id


def _alte_namen(objekt, haupt: bool) -> set[str]:
    """Frühere Ordnernamen desselben Objekts: „Objekt“ (Zeit mit nur einem Objekt),
    „Objekt <Reihenfolge>“ (Standardbezeichnung vor einer Umbenennung) und der volle Name mit
    Bezeichnung (Zeit mit mehreren Objekten)."""
    namen = {objekt_ordner_name(objekt, True)}
    if getattr(objekt, "reihenfolge", None):
        namen.add(f"{OBJEKT_PRAEFIX} {objekt.reihenfolge}")
    if haupt:
        namen.add(OBJEKT_PRAEFIX)
    return namen


def objekt_ordner_namen(session: Session, vorgang, objekt) -> set[str]:
    """Alle Ordnernamen, unter denen Fotos dieses Objekts liegen können: aktueller Name plus
    Alt-Namen (siehe _alte_namen) – ohne Namen, die heute ein anderes aktives Objekt trägt."""
    liste = objekt_ordner(session, vorgang)
    aktuell = next((n for n, o in liste if o.id == objekt.id),
                   objekt_ordner_name(objekt, len(liste) > 1))
    namen = {aktuell} | _alte_namen(objekt, _ist_hauptobjekt(objekt, liste))
    return namen - {n for n, o in liste if o.id != objekt.id}


def objekt_fuer_ordner(session: Session, vorgang, ordner: str):
    """Objekt zu einem Ordnernamen (aktuelle Namen zuerst, dann Alt-Namen); None für
    Sparten-/Zusatzordner."""
    if not ordner or not str(ordner).startswith(OBJEKT_PRAEFIX):
        return None
    liste = objekt_ordner(session, vorgang)
    for name, objekt in liste:
        if name == ordner:
            return objekt
    for name, objekt in liste:
        if ordner in _alte_namen(objekt, _ist_hauptobjekt(objekt, liste)):
            return objekt
    return None


def aktueller_objekt_ordner(session: Session, vorgang, ordner: str) -> str | None:
    """Heutiger Ordnername des Objekts, zu dem ein (ggf. früherer) Objekt-Ordnername gehört;
    None, wenn der Name kein Objekt-Ordner ist."""
    objekt = objekt_fuer_ordner(session, vorgang, ordner)
    if objekt is None:
        return None
    for name, o in objekt_ordner(session, vorgang):
        if o.id == objekt.id:
            return name
    return None


def objekt_ordner_nachziehen(session: Session, vorgang) -> int:
    """Fotos unter früheren Objekt-Ordnernamen (z. B. „Objekt“, nachdem ein zweites Objekt
    hinzukam) auf den heutigen Namen umschreiben – nur das Feld `ordner`, Dateien bleiben liegen.
    Wird vor einem Objekt-Upload aufgerufen (Schreibtransaktion); liefert die Anzahl."""
    vorgang_id = _vorgang_id_von(vorgang)
    if not vorgang_id:
        return 0
    liste = objekt_ordner(session, vorgang_id)
    aktuell = {name for name, _o in liste}
    anzahl = 0
    nach_neu: dict[str, str | None] = {}
    for datei in (session.query(GalerieDatei)
                  .filter(GalerieDatei.vorgang_id == vorgang_id,
                          GalerieDatei.ordner.like(OBJEKT_PRAEFIX + "%"))):
        if datei.ordner in aktuell:
            continue
        if datei.ordner not in nach_neu:
            nach_neu[datei.ordner] = aktueller_objekt_ordner(session, vorgang_id, datei.ordner)
        neu = nach_neu[datei.ordner]
        if neu and neu != datei.ordner:
            datei.ordner = neu
            anzahl += 1
    return anzahl


def objekt_sparte(session: Session, objekt) -> str:
    """Sparte, unter der Objektfotos aus der Kartei abgelegt werden: erstes Interesse des
    Objekts mit eigener Galerie, sonst erstes Interesse des Vorgangs, sonst WP [ANNAHME]."""
    from app import objekte as objekte_modul
    for code in objekte_modul.interessen_liste(objekt):
        if code in SPARTEN_ORDNER:
            return code
    for code in objekte_modul.vorgang_interessen(session, objekt.vorgang_id):
        if code in SPARTEN_ORDNER:
            return code
    return "WP"


def objektfotos(session: Session, vorgang, objekt) -> list[GalerieDatei]:
    """Fotos des Objekts über alle Sparten: bevorzugt über galerie_dateien.objekt_id (sobald
    vorhanden), sonst – und für Altbestand ohne objekt_id – über die Ordnernamen."""
    from sqlalchemy import and_, or_
    vorgang_id = _vorgang_id_von(vorgang) or objekt.vorgang_id
    namen = objekt_ordner_namen(session, vorgang_id, objekt)
    abfrage = session.query(GalerieDatei).filter(GalerieDatei.vorgang_id == vorgang_id)
    if _objekt_id_spalte():
        abfrage = abfrage.filter(or_(GalerieDatei.objekt_id == objekt.id,
                                     and_(GalerieDatei.objekt_id.is_(None),
                                          GalerieDatei.ordner.in_(sorted(namen)))))
    else:
        abfrage = abfrage.filter(GalerieDatei.ordner.in_(sorted(namen)))
    return abfrage.order_by(GalerieDatei.hochgeladen_am.desc(), GalerieDatei.id.desc()).all()


def objektfoto_loeschen_erlaubt(datei: GalerieDatei, benutzer) -> bool:
    """Plan: Löschen durch den Hochladenden, Innendienst oder Admin (dazu Projektierung wie in
    der Galerie, galerie.darf_loeschen [ANNAHME])."""
    if benutzer is None:
        return False
    if darf_loeschen(benutzer):
        return True
    return bool(datei.hochgeladen_von) and datei.hochgeladen_von == benutzer.id


def objektfotos_erlaubt(session: Session, vorgang: Vorgang, benutzer) -> bool:
    """Upload-Recht für Objektfotos aus der Kartei: Rechte der Galerie (darf_hochladen –
    Innendienst/Admin/Projektierung, Außendienst am eigenen Vorgang, Montage in der Besetzung)
    ODER die Bearbeiten-Rechte des Lead-Moduls.
    Vertrag Agent R (Phase 185): lead_v2.bearbeiten_erlaubt(session, benutzer, vorgang);
    solange R die Funktion noch nicht liefert, gilt die ÜBERGANGSPRÜFUNG lead_v2.zugriff_erlaubt
    (Modul-Sichtbare, Handelsvertreter am eigenen Lead)."""
    if benutzer is None or vorgang is None:
        return False
    if darf_hochladen(session, vorgang, benutzer):
        return True
    from app import lead_v2
    bearbeiten = getattr(lead_v2, "bearbeiten_erlaubt", None)
    if callable(bearbeiten):
        try:
            return bool(bearbeiten(session, benutzer, vorgang))
        except TypeError:   # andere Signatur – Übergang
            pass
    # ÜBERGANG (bis Agent R): Modul-Sichtbare und Handelsvertreter am eigenen Lead
    return bool(lead_v2.zugriff_erlaubt(session, benutzer, vorgang))


def foto_daten(datei: GalerieDatei, benutzer=None, vorgang_id: int | None = None,
               objekt_id: int | None = None) -> dict:
    """JSON-fähige Sicht auf ein Objektfoto für Kacheln/Lightbox (Kartei, Erfassung,
    Projektakte, Antwort der Upload-/Lösch-Route)."""
    vorgang_id = vorgang_id or datei.vorgang_id
    loeschen_url = ""
    if objekt_id:
        loeschen_url = (f"/lead-management/lead/{vorgang_id}/objekt/{objekt_id}"
                        f"/fotos/{datei.id}/loeschen")
    return {"id": datei.id, "name": datei.dateiname, "url": datei_url(datei.id),
            "download": datei_url(datei.id, herunterladen=True),
            "datum": datei.hochgeladen_am.strftime("%d.%m.%Y %H:%M") if datei.hochgeladen_am else "",
            "kurzdatum": datei.hochgeladen_am.strftime("%d.%m.") if datei.hochgeladen_am else "",
            "bemerkung": datei.bemerkung or "", "ordner": datei.ordner, "sparte": datei.sparte,
            "bild": bool(datei.bild),
            "loeschbar": objektfoto_loeschen_erlaubt(datei, benutzer) if benutzer else False,
            "loeschen_url": loeschen_url}


def objektfotos_daten(session: Session, vorgang, objekt, benutzer=None) -> list[dict]:
    vorgang_id = _vorgang_id_von(vorgang) or objekt.vorgang_id
    return [foto_daten(d, benutzer, vorgang_id, objekt.id)
            for d in objektfotos(session, vorgang_id, objekt)]


def objektfotos_kontext(session: Session, vorgang: Vorgang, benutzer) -> dict:
    """Kontext für den Block „Objekte“ der Kundenkartei (kartei_objekte.html): je aktivem
    Objekt Ordnername, Fotos (foto_daten) und Upload-URL; `einzel` = das einzige Objekt eines
    Ein-Objekt-Vorgangs (dort gibt es keine Objektkarte – der Fotoblock steht für sich)."""
    liste = objekt_ordner(session, vorgang)
    je_objekt = {}
    for name, objekt in liste:
        fotos = objektfotos_daten(session, vorgang.id, objekt, benutzer)
        je_objekt[objekt.id] = {
            "objekt_id": objekt.id, "ordner": name, "fotos": fotos, "anzahl": len(fotos),
            "bezeichnung": objekt.bezeichnung or name,
            "url": f"/lead-management/lead/{vorgang.id}/objekt/{objekt.id}/fotos",
            "gruppe": f"objekt/{vorgang.id}/{objekt.id}"}
    return {"darf_hochladen": objektfotos_erlaubt(session, vorgang, benutzer),
            "je_objekt": je_objekt,
            "einzel": je_objekt[liste[0][1].id] if len(liste) == 1 else None,
            "max_mb": OBJEKTFOTO_MAX_BYTES // (1024 * 1024)}


def objektfotos_je_gewerk(session: Session, projekt, gewerke) -> list[dict]:
    """Projektakte (nur Anzeige): Objektfotos des Objekts je Gewerk (gewerke.objekt_id, sonst
    Objekt des Angebots, sonst Hauptobjekt), je Objekt einmal, nur Objekte mit Fotos [ANNAHME]."""
    from app import objekte as objekte_modul
    from app.models import VorgangObjekt
    if projekt is None or not getattr(projekt, "vorgang_id", None):
        return []
    liste = objekt_ordner(session, projekt.vorgang_id)
    gesehen, ergebnis = set(), []
    for gewerk in gewerke or []:
        objekt_id = objekte_modul.ausfuehrungsort(session, gewerk=gewerk).get("objekt_id")
        objekt = session.get(VorgangObjekt, objekt_id) if objekt_id else None
        if objekt is None or objekt.vorgang_id != projekt.vorgang_id or objekt.id in gesehen:
            continue
        gesehen.add(objekt.id)
        fotos = objektfotos_daten(session, projekt.vorgang_id, objekt)
        if not fotos:
            continue
        name = next((n for n, o in liste if o.id == objekt.id), objekt_ordner_name(objekt, len(liste) > 1))
        ergebnis.append({"objekt_id": objekt.id, "ordner": name,
                         "titel": objekte_modul.objekt_text(objekt) if len(liste) > 1 else name,
                         "sparten": sorted({g.sparte for g in gewerke
                                            if objekte_modul.ausfuehrungsort(session, gewerk=g).get("objekt_id") == objekt.id}),
                         "fotos": fotos, "gruppe": f"projekt/{projekt.id}/{objekt.id}"})
    return ergebnis


def migration_v35_objektfotos(session: Session) -> list[str]:
    """Für den Orchestrator (migrate.py), sobald galerie_dateien die Spalte objekt_id trägt:
    Fotos in Objekt-Ordnern bekommen ihre objekt_id aus dem Ordnernamen (aktuelle und frühere
    Namen); ohne die Spalte passiert nichts. Additiv, idempotent (nur Zeilen ohne objekt_id)."""
    if not _objekt_id_spalte():
        return []
    gesetzt = 0
    cache: dict[tuple[int, str], int | None] = {}
    for datei in (session.query(GalerieDatei)
                  .filter(GalerieDatei.objekt_id.is_(None),
                          GalerieDatei.ordner.like(OBJEKT_PRAEFIX + "%"))):
        schluessel = (datei.vorgang_id, datei.ordner)
        if schluessel not in cache:
            objekt = objekt_fuer_ordner(session, datei.vorgang_id, datei.ordner)
            cache[schluessel] = objekt.id if objekt is not None else None
        if cache[schluessel] is not None:
            datei.objekt_id = cache[schluessel]
            gesetzt += 1
    if gesetzt:
        session.flush()
        return [f"v35: objekt_id an {gesetzt} Galerie-Datei(en) aus dem Objekt-Ordner gesetzt"]
    return []


def objekt_umbenannt(session: Session, objekt, alte_bezeichnung: str) -> int:
    """Hook aus der Kartei (lead_kartei.objekt_feld_speichern, Feld „bezeichnung“): Fotos unter
    dem alten Ordnernamen „Objekt <alt>“ tragen künftig den neuen Namen – nur das Feld
    `ordner` wird umgeschrieben (die Datei bleibt liegen, die Datei-Route liest `pfad`).
    Ein-Objekt-Vorgang: Ordner heißt unabhängig von der Bezeichnung „Objekt“ → nichts zu tun.
    Liefert die Anzahl der umgeschriebenen Einträge."""
    from types import SimpleNamespace
    liste = objekt_ordner(session, objekt.vorgang_id)
    if len(liste) < 2:
        return 0
    alt = SimpleNamespace(bezeichnung=alte_bezeichnung or "", reihenfolge=objekt.reihenfolge, id=objekt.id)
    alt_name = objekt_ordner_name(alt, True)
    neu_name = next((n for n, o in liste if o.id == objekt.id), objekt_ordner_name(objekt, True))
    if alt_name == neu_name or any(n == alt_name and o.id != objekt.id for n, o in liste):
        return 0
    anzahl = 0
    for datei in (session.query(GalerieDatei)
                  .filter(GalerieDatei.vorgang_id == objekt.vorgang_id,
                          GalerieDatei.ordner == alt_name)):
        datei.ordner = neu_name
        anzahl += 1
    return anzahl


def _objektfoto_pruefen(name: str, content_type: str) -> str:
    """Grund, warum eine Datei kein zulässiges Objektfoto ist ("" = zulässig)."""
    endung = Path(name or "").suffix.lower()
    typ = (content_type or "").lower().split(";")[0].strip()
    if endung in OBJEKTFOTO_ENDUNGEN or typ in OBJEKTFOTO_TYPEN:
        return ""
    return "nur JPG, PNG oder HEIC"


def _datei_schreiben_begrenzt(ziel: Path, inhalt, grenze: int) -> int:
    """Wie _datei_schreiben, bricht aber ab, sobald die Datei größer als `grenze` wird
    (Rückgabe −1; die Teil-Datei ist dann zu löschen)."""
    if isinstance(inhalt, (bytes, bytearray)):
        if len(inhalt) > grenze:
            return -1
        ziel.write_bytes(inhalt)
        return len(inhalt)
    try:
        inhalt.seek(0)
    except Exception:   # noqa: BLE001
        pass
    groesse = 0
    with ziel.open("wb") as ausgabe:
        while True:
            block = inhalt.read(STREAM_BLOCK)
            if not block:
                break
            groesse += len(block)
            if groesse > grenze:
                return -1
            ausgabe.write(block)
    return groesse


def objektfotos_speichern(session: Session, vorgang: Vorgang, objekt, dateien, benutzer=None,
                          sparte: str | None = None) -> dict:
    """Fotos je Objekt aus der Kartei (POST /lead-management/lead/{id}/objekt/{oid}/fotos):
    nur JPG/PNG/HEIC, je Bild höchstens OBJEKTFOTO_MAX_BYTES, HEIC → JPG, Ablage im Ordner
    des Objekts (objekt_ordner) unter der Sparte des Objekts.
    v27-Regel: erst alles Nötige lesen, dann die Sitzung freigeben (verbindung_freigeben),
    Dateien ohne Sitzung schreiben/wandeln, Zeilen in EINER kurzen Schreibtransaktion
    anlegen. Rückgabe wie mehrfach_speichern: {"abgelegt": [{nr, id, name, ordner}],
    "fehler": [{nr, name, grund}], "ordner": <Objekt-Ordner>}."""
    from app import projektierung as kern
    from app.db import verbindung_freigeben
    vorgang_id = vorgang.id
    liste = objekt_ordner(session, vorgang_id)
    ordner = next((n for n, o in liste if o.id == objekt.id), None) or objekt_ordner_name(objekt, len(liste) > 1)
    sparte = sparte_pruefen(sparte or objekt_sparte(session, objekt))
    original_behalten = kern.parameter_holen(session, "galerie_original_behalten", "aus") == "an"
    benutzer_id = benutzer.id if benutzer is not None else None
    objekt_id = objekt.id
    objekt_ordner_nachziehen(session, vorgang_id)   # frühere Objekt-Ordnernamen → heutiger Name
    verbindung_freigeben(session)   # (= Commit) ab hier Datei-I/O ohne gehaltene Verbindung/Schreibsperre
    ziel_ordner = _basis(vorgang_id) / sparte / ordner.replace("/", "-")
    ziel_ordner.mkdir(parents=True, exist_ok=True)
    geschrieben: list[tuple[int, Path, str]] = []
    fehler: list[dict] = []
    for nr, datei in enumerate(dateien or []):
        name = getattr(datei, "filename", "") or ""
        if not name:
            continue
        grund = _objektfoto_pruefen(name, getattr(datei, "content_type", "") or "")
        if grund:
            fehler.append({"nr": nr, "name": name[:150], "grund": grund})
            continue
        ziel = _freier_pfad(ziel_ordner, _sicherer_name(name))
        groesse = _datei_schreiben_begrenzt(ziel, getattr(datei, "file", datei), OBJEKTFOTO_MAX_BYTES)
        if groesse <= 0:
            ziel.unlink(missing_ok=True)
            fehler.append({"nr": nr, "name": name[:150],
                           "grund": "Datei ist leer" if groesse == 0
                           else f"größer als {OBJEKTFOTO_MAX_BYTES // (1024 * 1024)} MB"})
            continue
        if original_behalten:
            shutil.copy2(ziel, ziel_ordner / f"original_{ziel.name}")
        if ist_heic(ziel):
            gewandelt = _heic_nach_jpg(ziel)
            if gewandelt is None:
                ziel.unlink(missing_ok=True)
                fehler.append({"nr": nr, "name": name[:150], "grund": "HEIC nicht lesbar"})
                continue
            ziel = gewandelt
        elif not _bild_lesbar(ziel):
            ziel.unlink(missing_ok=True)
            fehler.append({"nr": nr, "name": name[:150], "grund": "kein lesbares Bild"})
            continue
        else:
            _verkleinern(ziel)
        geschrieben.append((nr, ziel, name))
    abgelegt: list[dict] = []
    if geschrieben:
        eintraege = []
        try:
            for nr, ziel, name in geschrieben:
                eintrag = GalerieDatei(
                    vorgang_id=vorgang_id, sparte=sparte, ordner=ordner, dateiname=ziel.name,
                    pfad=str(ziel.relative_to(config.DATA_ORDNER)), bild=True, bemerkung="",
                    quelle="upload", hochgeladen_von=benutzer_id)
                if _objekt_id_spalte():
                    eintrag.objekt_id = objekt_id
                session.add(eintrag)
                eintraege.append((nr, eintrag, name))
            session.commit()
        except Exception as problem:   # noqa: BLE001 – Dateien wieder entfernen, je Datei melden
            session.rollback()
            for nr, ziel, name in geschrieben:
                ziel.unlink(missing_ok=True)
                fehler.append({"nr": nr, "name": name[:150], "grund": _fehlergrund(problem)})
            return {"abgelegt": [], "fehler": fehler, "ordner": ordner}
        abgelegt = [{"nr": nr, "id": eintrag.id, "name": eintrag.dateiname, "ordner": ordner}
                    for nr, eintrag, name in eintraege]
    return {"abgelegt": abgelegt, "fehler": fehler, "ordner": ordner}


def objektfoto_loeschen(session: Session, datei: GalerieDatei, benutzer=None) -> str:
    """Objektfoto löschen: erst die Zeile in einer kurzen Schreibtransaktion (Commit, mit
    Chat-Notiz wie beim Galerie-Löschen), danach die Datei ohne gehaltene Sitzung. Liefert
    den Dateinamen."""
    from app import vorgaenge as vorgaenge_modul
    name, ordner, vorgang_id = datei.dateiname, datei.ordner, datei.vorgang_id
    pfad = config.DATA_ORDNER / datei.pfad if datei.pfad else None
    session.delete(datei)
    vorgaenge_modul.notiz_anlegen(session, vorgang_id, benutzer,
                                  f"Galerie: „{name}“ aus Ordner {ordner} gelöscht.",
                                  herkunft="Galerie")
    session.commit()
    if pfad is not None:
        pfad.unlink(missing_ok=True)
    return name
