# Rollen als Varianten einer Basisrolle – v33 (PLAN_V20 Phase 167).
#
# Eine Rolle (Tabelle `rollen`) ist entweder eine der sechs Basisrollen (Systemzeilen,
# nicht löschbar) oder eine Variante davon mit Kennzeichen: Gewerk (heizung | elektro),
# Service (0/1) und Handelsvertreter (0/1). Rechte erben IMMER von der Basisrolle –
# der Code vergleicht deshalb nie mehr `benutzer.rolle == "montage"`, sondern
# `benutzer.basisrolle == "montage"` (Property in models.Benutzer, liest `basisrolle_von`).
# Die Kennzeichen steuern Einsatzlisten, Kalender und Zuweisungen
# (`Benutzer.hat_kennzeichen("service")`, `Benutzer.gewerk`).
#
# Der Katalog wird je Prozess zwischengespeichert (ein Lesezugriff beim ersten
# Aufruf; `cache_leeren()` nach jeder Änderung in der Parametrierung und nach der
# Migration). Fehlt die Tabelle noch (v32-Datenbank vor migrate.py), gilt der
# statische Startkatalog – die Basisrollen und die fünf Startvarianten.
import threading
from typing import Optional

BASISROLLEN = ("admin", "innendienst", "aussendienst", "projektierung", "montage",
               "leadmanagement")
BASISROLLEN_NAMEN = {"admin": "Admin", "innendienst": "Innendienst",
                     "aussendienst": "Außendienst", "projektierung": "Projektierung",
                     "montage": "Montage", "leadmanagement": "Lead-Management"}
GEWERKE = ("", "heizung", "elektro")
GEWERK_NAMEN = {"": "–", "heizung": "Heizung", "elektro": "Elektro"}
KENNZEICHEN = ("service", "handelsvertreter")
# Startvarianten (Entscheidung Andreas 14.10.2026): key, Name, Basisrolle, Gewerk,
# service, handelsvertreter, Sortierung
VARIANTEN_START = (
    ("montage_heizung", "Montage Heizung", "montage", "heizung", False, False, 10),
    ("montage_elektro", "Montage Elektro", "montage", "elektro", False, False, 11),
    ("service_heizung", "Service Heizung", "montage", "heizung", True, False, 12),
    ("service_elektro", "Service Elektro", "montage", "elektro", True, False, 13),
    ("handelsvertreter", "Handelsvertreter", "aussendienst", "", False, True, 20),
)
MARKER_HV = "migration_v33_hv"
MARKER_TEAMS = "migration_v33_teams_gewerk"

_cache: Optional[dict] = None
_sperre = threading.Lock()


def _eintrag(key: str, name: str, basisrolle: str, gewerk: str = "", service: bool = False,
             handelsvertreter: bool = False, aktiv: bool = True, system: bool = False,
             sortierung: int = 0) -> dict:
    return {"key": key, "name": name, "basisrolle": basisrolle, "gewerk": gewerk or "",
            "service": bool(service), "handelsvertreter": bool(handelsvertreter),
            "aktiv": bool(aktiv), "system": bool(system), "sortierung": int(sortierung or 0)}


def statischer_katalog() -> dict:
    """Basisrollen + Startvarianten ohne Datenbank (Rückfall, Tests, v32-DB)."""
    katalog = {}
    for i, basis in enumerate(BASISROLLEN):
        katalog[basis] = _eintrag(basis, BASISROLLEN_NAMEN[basis], basis, system=True,
                                  sortierung=i)
    for key, name, basis, gewerk, service, hv, sort in VARIANTEN_START:
        katalog[key] = _eintrag(key, name, basis, gewerk, service, hv, sortierung=sort)
    return katalog


def _aus_datenbank() -> Optional[dict]:
    """Katalog aus der Tabelle `rollen` (eigene kurze Sitzung); None, wenn die Tabelle
    fehlt oder leer ist."""
    try:
        from app.db import kurz
        from app.models import Rolle
        with kurz(schreibend=False) as s:   # v33 (Phase 172): nur lesen - keine Schreibtransaktion
            zeilen = s.query(Rolle).all()
            if not zeilen:
                return None
            return {r.key: _eintrag(r.key, r.name, r.basisrolle, r.gewerk, r.service,
                                    r.handelsvertreter, r.aktiv, r.system, r.sortierung)
                    for r in zeilen}
    except Exception:   # noqa: BLE001 – Tabelle fehlt (v32-DB) oder DB nicht erreichbar
        return None


def katalog() -> dict:
    """Alle Rollen (key → Eintrag), zwischengespeichert."""
    global _cache
    daten = _cache
    if daten is not None:
        return daten
    with _sperre:
        if _cache is None:
            geladen = _aus_datenbank()
            grund = statischer_katalog()
            if geladen:
                # Basisrollen immer vorhanden, auch wenn eine Datenbank sie nicht führt
                for key, eintrag in grund.items():
                    geladen.setdefault(key, eintrag)
                _cache = geladen
            else:
                _cache = grund
        return _cache


def cache_leeren() -> None:
    global _cache
    with _sperre:
        _cache = None


def _norm(key) -> str:
    return (key or "").strip().lower()


def eintrag(key) -> Optional[dict]:
    return katalog().get(_norm(key))


def basisrolle_von(key) -> str:
    """Basisrolle eines Rollen-Keys; Basisrollen liefern sich selbst, unbekannte Keys
    bleiben unverändert (dann greift keine Rechte-Regel)."""
    k = _norm(key)
    e = katalog().get(k)
    if e is not None:
        return e["basisrolle"]
    return k


def name_von(key) -> str:
    e = eintrag(key)
    if e is not None:
        return e["name"]
    return BASISROLLEN_NAMEN.get(_norm(key), key or "")


def gewerk_von(key) -> str:
    e = eintrag(key)
    return e["gewerk"] if e is not None else ""


def kennzeichen_von(key) -> set:
    e = eintrag(key)
    if e is None:
        return set()
    return {k for k in KENNZEICHEN if e.get(k)}


def ist_variante(key) -> bool:
    e = eintrag(key)
    return e is not None and e["key"] != e["basisrolle"]


def keys_fuer_basis(basis: str, nur_aktive: bool = False) -> list:
    """Alle Rollen-Keys mit dieser Basisrolle (die Basisrolle selbst zuerst) – für
    Datenbankfilter `Benutzer.rolle.in_(...)`. Deaktivierte Varianten zählen mit, weil
    Benutzer sie noch tragen können (`nur_aktive=True` für Auswahlfelder)."""
    b = _norm(basis)
    keys = [b] if b in BASISROLLEN else []
    for key, e in sorted(katalog().items(), key=lambda kv: (kv[1]["sortierung"], kv[0])):
        if e["basisrolle"] == b and key != b and (e["aktiv"] or not nur_aktive):
            keys.append(key)
    return keys or [b]


def keys_fuer_basen(basen, nur_aktive: bool = False) -> list:
    keys = []
    for basis in basen:
        for key in keys_fuer_basis(basis, nur_aktive):
            if key not in keys:
                keys.append(key)
    return keys


def filter_basis(basis):
    """SQLAlchemy-Kriterium: Benutzer mit dieser Basisrolle (Hauptrolle)."""
    from app.models import Benutzer
    return Benutzer.rolle.in_(keys_fuer_basis(basis))


def filter_basen(basen):
    from app.models import Benutzer
    return Benutzer.rolle.in_(keys_fuer_basen(basen))


def alle(session, nur_aktive: bool = False) -> list:
    """Rollen-Zeilen aus der Datenbank, sortiert (Basisrollen zuerst)."""
    from app.models import Rolle
    abfrage = session.query(Rolle)
    if nur_aktive:
        abfrage = abfrage.filter(Rolle.aktiv.is_(True))
    return abfrage.order_by(Rolle.system.desc(), Rolle.sortierung, Rolle.name).all()


def auswahl(session, nur_aktive: bool = True) -> list:
    """(key, name) für Dropdowns – Basisrollen zuerst, dann Varianten nach Sortierung."""
    zeilen = alle(session, nur_aktive=nur_aktive)
    if zeilen:
        return [(r.key, r.name) for r in zeilen]
    return [(k, e["name"]) for k, e in sorted(statischer_katalog().items(),
                                              key=lambda kv: (not kv[1]["system"],
                                                              kv[1]["sortierung"]))]


def namen(session=None) -> dict:
    """key → Name (für Listen/Badges); ohne Sitzung aus dem Cache."""
    return {k: e["name"] for k, e in katalog().items()}


# --- v33 (PLAN_V20 Phase 167, Agent R): Helfer für Benutzerverwaltung, Import, Parametrierung ---

def _sortiert(eintraege) -> list:
    """Basisrollen zuerst (feste Reihenfolge), dann Varianten nach Sortierung/Name."""
    return sorted(eintraege, key=lambda e: (not e["system"], e["sortierung"], e["name"].lower()))


def katalog_liste(nur_aktive: bool = True) -> list:
    """Katalog als sortierte Liste von Einträgen (Kopien) – für Dropdowns und Häkchen der
    Benutzerverwaltung; `nur_aktive=False` liefert auch deaktivierte Varianten."""
    return [dict(e, variante=(e["key"] != e["basisrolle"]))
            for e in _sortiert(katalog().values()) if e["aktiv"] or not nur_aktive]


def keys_aktiv() -> list:
    """Alle aktiven Rollen-Keys (Basisrollen zuerst)."""
    return [e["key"] for e in katalog_liste(nur_aktive=True)]


def key_gueltig(key, zusaetzlich=()) -> bool:
    """Darf dieser Key als (Haupt-/Zusatz-)Rolle gespeichert werden? Aktive Rollen des
    Katalogs; `zusaetzlich` = Keys, die trotz Deaktivierung bleiben dürfen (die heutige
    Rolle eines Benutzers)."""
    k = _norm(key)
    if k in {_norm(z) for z in zusaetzlich}:
        return True
    e = katalog().get(k)
    return e is not None and e["aktiv"]


def kennzeichen_badges(key) -> list:
    """Kleine Badges einer Variante für die Benutzerliste: [(Kurztext, Titel)] –
    Gewerk (Heizung/Elektro), Service, HV; Basisrollen liefern eine leere Liste."""
    e = eintrag(key)
    if e is None:
        return []
    badges = []
    if e["gewerk"]:
        badges.append((GEWERK_NAMEN.get(e["gewerk"], e["gewerk"]), f"Gewerk {GEWERK_NAMEN.get(e['gewerk'], e['gewerk'])}"))
    if e["service"]:
        badges.append(("Service", "Service-Einsätze (Terminart Service)"))
    if e["handelsvertreter"]:
        badges.append(("HV", "Handelsvertreter – terminiert selbst, HV-Sicht im Lead-Management"))
    return badges


def benutzer_badges(benutzer) -> list:
    """Badges über alle Rollen eines Benutzers (Haupt- und Zusatzrollen, ohne Dubletten)."""
    gesehen, badges = set(), []
    for r in getattr(benutzer, "rollen_liste", []) or []:
        for kurz, titel in kennzeichen_badges(r):
            if kurz not in gesehen:
                gesehen.add(kurz)
                badges.append((kurz, titel))
    return badges


def benutzer_anzahl(session, nur_aktive: bool = True) -> dict:
    """key → Zahl der Benutzer, die den Key als Haupt- oder Zusatzrolle tragen
    (Parametrierung → Rollen, Spalte „Benutzer“)."""
    from app.models import Benutzer
    zaehler: dict = {}
    abfrage = session.query(Benutzer)
    if nur_aktive:
        abfrage = abfrage.filter(Benutzer.aktiv.is_(True))
    for b in abfrage:
        for r in {_norm(x) for x in b.rollen_liste}:
            zaehler[r] = zaehler.get(r, 0) + 1
    return zaehler


def hv_keys(nur_aktive: bool = False) -> list:
    """Rollen-Keys mit Kennzeichen Handelsvertreter (Basisrolle Außendienst)."""
    return [k for k, e in katalog().items()
            if e["handelsvertreter"] and e["basisrolle"] == "aussendienst"
            and (e["aktiv"] or not nur_aktive)]


def hv_rolle_setzen(session, benutzer, hv: bool) -> bool:
    """Gegenrichtung zu `hv_spiegeln`: das Häkchen `terminiert_selbst` im AD-Profil setzt
    die Rolle Handelsvertreter (Hauptrolle aussendienst → handelsvertreter) bzw. nimmt sie
    zurück (Hauptrolle mit HV-Kennzeichen → aussendienst, HV-Varianten aus den Zusatzrollen).
    Nur für Benutzer der Basisrolle Außendienst; liefert True bei einer Änderung."""
    if benutzer is None or basisrolle_von(benutzer.rolle) != "aussendienst":
        return False
    keys = hv_keys()
    if hv:
        if any(_norm(r) in keys for r in benutzer.rollen_liste):
            return False
        aktive = [k for k in hv_keys(nur_aktive=True)]
        ziel = "handelsvertreter" if "handelsvertreter" in aktive else (aktive[0] if aktive else "")
        if not ziel:
            return False
        benutzer.rolle = ziel
        benutzer.rollen = ",".join([ziel] + [r for r in benutzer.rollen_liste[1:] if _norm(r) != ziel])
        return True
    if not any(_norm(r) in keys for r in benutzer.rollen_liste):
        return False
    zusatz = [r for r in benutzer.rollen_liste[1:] if _norm(r) not in keys]
    haupt = "aussendienst" if _norm(benutzer.rolle) in keys else benutzer.rolle
    benutzer.rolle = haupt
    benutzer.rollen = ",".join([haupt] + [r for r in zusatz if _norm(r) != _norm(haupt)])
    return True


def benutzer_mit_rolle(session, key: str, nur_aktive: bool = True) -> list:
    """Benutzer, die den Key als Haupt- oder Zusatzrolle tragen."""
    from app.models import Benutzer
    k = _norm(key)
    treffer = []
    abfrage = session.query(Benutzer)
    if nur_aktive:
        abfrage = abfrage.filter(Benutzer.aktiv.is_(True))
    for b in abfrage:
        if k in [r.lower() for r in b.rollen_liste]:
            treffer.append(b)
    return treffer


def anlegen(session, key: str, name: str, basisrolle: str, gewerk: str = "",
            service: bool = False, handelsvertreter: bool = False, benutzer=None):
    """Variante anlegen (Admin, Parametrierung → Rollen). Liefert (ok, meldung, rolle)."""
    import re
    from app.models import Rolle
    k = _norm(key) or re.sub(r"[^a-z0-9]+", "_", (name or "").lower()).strip("_")
    if not k or not re.match(r"^[a-z][a-z0-9_]{1,39}$", k):
        return False, "Bitte einen Schlüssel aus Kleinbuchstaben, Ziffern und _ angeben.", None
    if not (name or "").strip():
        return False, "Bitte einen Namen angeben.", None
    if _norm(basisrolle) not in BASISROLLEN:
        return False, "Unbekannte Basisrolle.", None
    if (gewerk or "") not in GEWERKE:
        return False, "Unbekanntes Gewerk.", None
    if session.query(Rolle).filter(Rolle.key == k).first() is not None:
        return False, f"Die Rolle „{k}“ gibt es bereits.", None
    letzte = max([r.sortierung for r in session.query(Rolle)] or [0])
    rolle = Rolle(key=k, name=name.strip()[:100], basisrolle=_norm(basisrolle),
                  gewerk=gewerk or "", service=bool(service),
                  handelsvertreter=bool(handelsvertreter), aktiv=True, system=False,
                  sortierung=letzte + 1)
    session.add(rolle)
    session.flush()
    cache_leeren()
    return True, f"Rolle „{rolle.name}“ angelegt.", rolle


def umbenennen(session, key: str, name: str):
    from app.models import Rolle
    rolle = session.query(Rolle).filter(Rolle.key == _norm(key)).first()
    if rolle is None:
        return False, "Rolle nicht gefunden."
    if not (name or "").strip():
        return False, "Bitte einen Namen angeben."
    rolle.name = name.strip()[:100]
    session.flush()
    cache_leeren()
    return True, f"Rolle „{rolle.name}“ umbenannt."


def deaktivieren(session, key: str, aktiv: bool = False):
    """Deaktivieren nur ohne aktive Benutzer; Systemrollen sind gesperrt."""
    from app.models import Rolle
    rolle = session.query(Rolle).filter(Rolle.key == _norm(key)).first()
    if rolle is None:
        return False, "Rolle nicht gefunden."
    if rolle.system:
        return False, "Systemrollen (Basisrollen) können nicht deaktiviert werden."
    if not aktiv:
        traeger = benutzer_mit_rolle(session, rolle.key, nur_aktive=True)
        if traeger:
            namen_liste = ", ".join(b.name for b in traeger[:5])
            return False, (f"Rolle „{rolle.name}“ hat noch {len(traeger)} aktive Benutzer "
                           f"({namen_liste}) – zuerst eine andere Rolle zuweisen.")
    rolle.aktiv = bool(aktiv)
    session.flush()
    cache_leeren()
    return True, (f"Rolle „{rolle.name}“ {'aktiviert' if aktiv else 'deaktiviert'}.")


def hv_spiegeln(session, benutzer) -> None:
    """Kennzeichen `ad_profile.terminiert_selbst` mit der Rolle Handelsvertreter synchron
    halten (v32-Code liest weiter das Profil): Rolle mit Kennzeichen → Flag an; Basisrolle
    Außendienst ohne Kennzeichen → Flag aus."""
    from app.models import AdProfil
    if benutzer is None or basisrolle_von(benutzer.rolle) != "aussendienst":
        return
    soll = any("handelsvertreter" in kennzeichen_von(r) for r in benutzer.rollen_liste)
    profil = session.query(AdProfil).filter(AdProfil.benutzer_id == benutzer.id).first()
    if profil is None:
        if not soll:
            return
        profil = AdProfil(benutzer_id=benutzer.id)
        session.add(profil)
    if bool(profil.terminiert_selbst) != soll:
        profil.terminiert_selbst = soll


def migration_v33_rollen(session) -> list:
    """migrate.py-Hook (idempotent): Systemzeilen + fünf Startvarianten, AD-Profile mit
    `terminiert_selbst` → Rolle `handelsvertreter` (einmalig, Marker), Teams-Gewerk
    (Elektro-Teams an Gewerken → elektro, übrige → heizung [ANNAHME], einmalig)."""
    from app.models import (AdProfil, Benutzer, Gewerk, Rolle, Team, einstellung_holen,
                            einstellung_setzen)
    meldungen = []
    vorhanden = {r.key for r in session.query(Rolle)}
    neu = 0
    for i, basis in enumerate(BASISROLLEN):
        if basis not in vorhanden:
            session.add(Rolle(key=basis, name=BASISROLLEN_NAMEN[basis], basisrolle=basis,
                              system=True, aktiv=True, sortierung=i))
            neu += 1
    for key, name, basis, gewerk, service, hv, sort in VARIANTEN_START:
        if key not in vorhanden:
            session.add(Rolle(key=key, name=name, basisrolle=basis, gewerk=gewerk,
                              service=service, handelsvertreter=hv, aktiv=True,
                              system=False, sortierung=sort))
            neu += 1
    session.flush()
    cache_leeren()
    if neu:
        meldungen.append(f"Rollen (v33): {neu} Rollen angelegt – 6 Basisrollen als Systemzeilen, "
                         "Varianten Montage Heizung/Elektro, Service Heizung/Elektro, Handelsvertreter")
    if einstellung_holen(session, MARKER_HV, "") != "erledigt":
        umgestellt = []
        for profil in session.query(AdProfil).filter(AdProfil.terminiert_selbst.is_(True)):
            b = session.get(Benutzer, profil.benutzer_id)
            if b is not None and _norm(b.rolle) == "aussendienst":
                b.rolle = "handelsvertreter"
                umgestellt.append(b.name)
        gespiegelt = 0
        for b in session.query(Benutzer).filter(Benutzer.rolle == "handelsvertreter"):
            profil = session.query(AdProfil).filter(AdProfil.benutzer_id == b.id).first()
            if profil is None:
                profil = AdProfil(benutzer_id=b.id)
                session.add(profil)
            if not profil.terminiert_selbst:
                profil.terminiert_selbst = True
                gespiegelt += 1
        session.flush()
        einstellung_setzen(session, MARKER_HV, "erledigt")
        meldungen.append("Rollen (v33): Handelsvertreter-Rolle gesetzt für "
                         + (", ".join(umgestellt) if umgestellt else "keinen Benutzer")
                         + (f"; Kennzeichen terminiert_selbst bei {gespiegelt} Benutzern nachgezogen"
                            if gespiegelt else ""))
    # v33 (Agent R): Zusatzrollen bereinigen – trägt ein Benutzer eine Variante als
    # Hauptrolle (z. B. handelsvertreter nach der HV-Umstellung), ist deren Basisrolle
    # (aussendienst) als Zusatzrolle überflüssig (Rechte erben ohnehin). Idempotent,
    # ohne Marker: schreibt nur, wenn etwas zu bereinigen ist.
    bereinigt = 0
    for b in session.query(Benutzer):
        basis = basisrolle_von(b.rolle)
        liste = b.rollen_liste
        if basis != _norm(b.rolle) and any(_norm(r) == basis for r in liste[1:]):
            b.rollen = ",".join([b.rolle] + [r for r in liste[1:] if _norm(r) != basis])
            bereinigt += 1
    if bereinigt:
        session.flush()
        meldungen.append(f"Rollen (v33): Zusatzrollen bei {bereinigt} Benutzern bereinigt "
                         "(Basisrolle der eigenen Variante entfernt)")
    if einstellung_holen(session, MARKER_TEAMS, "") != "erledigt":
        elektro_ids = {g.elektro_team_id for g in session.query(Gewerk)
                       .filter(Gewerk.elektro_team_id.isnot(None))}
        elektro = heizung = 0
        for team in session.query(Team):
            if (team.gewerk or "").strip():
                continue
            if team.id in elektro_ids:
                team.gewerk = "elektro"
                elektro += 1
            else:
                team.gewerk = "heizung"
                heizung += 1
        session.flush()
        einstellung_setzen(session, MARKER_TEAMS, "erledigt")
        meldungen.append(f"Teams (v33): Gewerk gesetzt – {elektro} Elektro (an Gewerken als "
                         f"Elektro-Team), {heizung} Heizung [ANNAHME: uebrige -> heizung]")   # ASCII: cp1252-Konsole (update.bat)
    return meldungen
