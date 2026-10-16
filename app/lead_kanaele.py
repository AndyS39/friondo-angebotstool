# Vertriebskanal-Stammdaten – v35 (PLAN_LEAD_V6 Phase 184, Nachtrag 15.10.2026, Agent K).
# Einzige Quelle für Kanäle ist die Tabelle `vertriebskanaele` (Modell app.models.Vertriebskanal:
# key, name, farbe, aktiv, pflicht_hinweis, reihenfolge, angelegt_am). Der von Hand gepflegte
# Parameter `kanal_farben` (v23) wird aus der Tabelle gespiegelt (kanal_farben_parameter_schreiben)
# und nirgends mehr von Hand bearbeitet.
#
# Regeln (Chat Lead-Management 15.10.2026, Claudia Castro):
# - Dropdowns zeigen die aktiven Kanäle nach Anzahl Verwendungen der letzten 90 Tage absteigend,
#   dann alphabetisch (kanal_sortiert); der Kanal „?“ steht immer zuletzt.
# - „?“ = „Vertriebskanal unklar“: rot markiertes Pflichtfeld „Vertriebskanal klären“, sperrt die
#   Terminierung (lead_kartei.terminierung_pruefung über lead_v2.pflichtfelder_offen) und die
#   TAIFUN-Übergabe (Vertrag Agent T: kanal_unklar(vorgang)). Eingang ohne erkennbaren Kanal
#   (Quelle ohne Kanal, API/Parser/Schnellanlage ohne Wahl) setzt „?“ statt leer (leadmanagement.
#   lead_anlegen).
# - Löschen = `aktiv = 0` (nicht mehr wählbar, Leads behalten den Kanal, Label bleibt sichtbar);
#   endgültig gelöscht wird nur ein Kanal, den kein Kunde/Lead/keine Quelle trägt.
# - Umbenennen wirkt überall: kunden.vertriebskanal, leads.vertriebskanal, lead_quellen.kanal,
#   Angebotsprofil-Zuordnung (profile.kanalwerte), Parameter hv_ausschluss und kanal_ad_regel.
# - „Standard“ ist kein Kanal mehr (Angebotsprofil „Standard“ bleibt Fallback); Leads mit Kanal
#   „Standard“ erhalten einen leeren Kanal (Migration).
# - Keine Glocken, keine Netz-/Datei-I/O in diesem Modul.
#
# Verträge: Agent B (Inline-Dropdown) nutzt kanal_sortiert/kanal_optionen und kanal_farbe,
# Agent R dieselben Funktionen, Agent T kanal_unklar(vorgang).
# Migration: migration_v35_kanaele(session) -> list[str] (Hook registriert der Orchestrator).

import json
import re
import time
import unicodedata
from datetime import datetime, timedelta

from sqlalchemy import func
from sqlalchemy.orm import Session, object_session

from app.models import Kunde, Lead, LeadQuelle, Profil, Vertriebskanal, Vorgang

KANAL_UNKLAR = "?"
UNKLAR_HINWEIS = "Vertriebskanal klären"
UNKLAR_KEY = "unklar"
KANAL_STANDARD_ALT = "Standard"      # bis v34 „Standard“ = ohne Kanal (Angebotsprofil-Fallback)
VERWENDUNG_TAGE = 90
PARAMETER_FARBEN = "kanal_farben"
NAME_MAX = 120
TEXT_HELL = "hell"                   # heller Text auf dunkler Kanalfarbe
TEXT_DUNKEL = "dunkel"               # dunkler Text auf heller Kanalfarbe
CACHE_SEKUNDEN = 60

# Startliste aus PLAN_LEAD_V6 Phase 184 (monday-Labels, Bilder vom 15.10.2026) – Reihenfolge
# wie im Plan, Farben als Startwert (Admin kann sie unter Lead-Management → Vertriebskanäle
# ändern). Name „Kontaktformular/info“ bestätigt 15.10.2026.
START_KANAELE = [
    ("RegioScout", "#F28B82"), ("Thermondo", "#5B6B9E"), ("ED - Google", "#C75AA0"),
    ("ED - Meta", "#7FC8E8"), ("Webinar", "#333333"), ("DAA", "#F0B14A"), ("Enni", "#7BC67E"),
    ("Google", "#C9A0A0"), ("Andere", "#E06C75"), ("Prepair Tech.", "#6B8BD6"),
    ("Konfigurator", "#3FB8A0"), ("Stadtwerke Düsseldorf", "#4F8FCF"), ("Mitsubishi", "#8E9AA8"),
    ("WhatsApp", "#8B6B5E"), ("OTC", "#5BA6A0"), ("Klimakonfigurator", "#3AA0C8"),
    ("Empfehlung", "#C8B45A"), ("Bosch", "#2E5E6E"), ("Sparkasse", "#F08A7A"), ("EEE", "#9A86D6"),
    ("Messe", "#3F7FB8"), ("Showroom", "#A4C84A"), ("Infoveranstaltung", "#8A5AD6"),
    ("Kontaktformular/info", "#B06AE0"), ("Reonic", "#7A4FB0"), ("WELOVEX", "#4F9AD6"),
    ("Comodomo", "#A85A8A"), ("Bestandskunde", "#5AA0D6"), (KANAL_UNKLAR, "#3F6F7F"),
    ("Energy Systems", "#5A8FB0"),
]

# Abgleich alter Schreibweisen (monday-Mapping, Quellen-Dropdown v21, Aliase v33) → Name der
# Liste. Schlüssel normalisiert (_norm). Werte, die nicht hier stehen und auch keinen Listen-
# namen treffen, werden als Kanal mit aktiv = 0 angelegt (EON, Provinzial, EnergieDigital,
# ZEUS Empfehlung, RS Versicherungen …). „Standard“ → kein Kanal.
ALT_NEU = {
    "swd": "Stadtwerke Düsseldorf", "stadtwerke duesseldorf": "Stadtwerke Düsseldorf",
    "stadtwerke-düsseldorf": "Stadtwerke Düsseldorf", "stadtwerke-duesseldorf": "Stadtwerke Düsseldorf",
    "stadtwerke düsseldorf ag": "Stadtwerke Düsseldorf", "partner swd": "Stadtwerke Düsseldorf",
    "stadtwerke düsseld": "Stadtwerke Düsseldorf",
    "sparkasse du": "Sparkasse", "sparkasse duisburg": "Sparkasse", "partner sparkasse du": "Sparkasse",
    "sparkasse-duisburg": "Sparkasse",
    "partner enni": "Enni", "enni energie & umwelt": "Enni", "enni energie und umwelt": "Enni",
    "ed google": "ED - Google", "ed-google": "ED - Google", "ed – google": "ED - Google",
    "energiedigital google": "ED - Google", "energiedigital - google": "ED - Google",
    "ed meta": "ED - Meta", "ed-meta": "ED - Meta", "energiedigital meta": "ED - Meta",
    "energiedigital - meta": "ED - Meta", "ed facebook": "ED - Meta", "ed - facebook": "ED - Meta",
    "kontaktformular": "Kontaktformular/info", "kontaktformular / info": "Kontaktformular/info",
    "kontaktformular/ info": "Kontaktformular/info", "kontaktformular /info": "Kontaktformular/info",
    "info": "Kontaktformular/info", "info@": "Kontaktformular/info",
    "prepair": "Prepair Tech.", "prepair tech": "Prepair Tech.", "prepair technologies": "Prepair Tech.",
    "prepair technology": "Prepair Tech.",
    "infoabend": "Infoveranstaltung", "info-veranstaltung": "Infoveranstaltung",
    "info veranstaltung": "Infoveranstaltung", "info-abend": "Infoveranstaltung",
    "regio scout": "RegioScout", "regio-scout": "RegioScout",
    "we love x": "WELOVEX", "welove x": "WELOVEX", "welovex gmbh": "WELOVEX",
    "energysystems": "Energy Systems", "energy-systems": "Energy Systems",
    "whats app": "WhatsApp", "whatsapp business": "WhatsApp",
    "klima-konfigurator": "Klimakonfigurator", "klima konfigurator": "Klimakonfigurator",
    "wp-konfigurator": "Konfigurator", "wp konfigurator": "Konfigurator",
    "bestandskunden": "Bestandskunde", "bestand": "Bestandskunde",
    "empfehlungen": "Empfehlung", "weiterempfehlung": "Empfehlung",
    "sonstige": "Andere", "sonstiges": "Andere", "andere quelle": "Andere",
    "unklar": KANAL_UNKLAR, "unbekannt": KANAL_UNKLAR, "?": KANAL_UNKLAR,
}

# Automatik-Palette für Werte ohne Stammdaten-Zeile (gleiche Reihenfolge wie lead_boards.
# KANAL_PALETTE – dort nur als Rückfall, hier ohne Import des Board-Moduls)
_PALETTE = ["#e87ba4", "#2a78d6", "#1baf7a", "#eda100", "#8e44ad", "#eb6834", "#5b6b8a", "#c9a227"]
_HEX = re.compile(r"^#[0-9a-fA-F]{6}$")


# --- Normalisierung ---------------------------------------------------------------------

def _norm(text) -> str:
    """Vergleichsform: NFC, klein, Gedankenstriche → „-“, Auslassungszeichen und Punkte am Ende
    entfernt, Leerraum verdichtet („Stadtwerke Düsseld…“ → „stadtwerke düsseld“)."""
    t = unicodedata.normalize("NFC", str(text or "")).strip().lower()
    t = t.replace("–", "-").replace("—", "-").replace("…", "")
    t = re.sub(r"\.{2,}$", "", t).strip()
    t = re.sub(r"\s+", " ", t)
    return t.rstrip(".").strip()


def _hash_index(text: str, n: int) -> int:
    import hashlib
    return int(hashlib.md5((text or "").lower().encode("utf-8")).hexdigest(), 16) % n


def key_aus_name(name: str) -> str:
    """Technischer Schlüssel aus dem Namen („ED - Google“ → „ed_google“, „?“ → „unklar“)."""
    if (name or "").strip() == KANAL_UNKLAR:
        return UNKLAR_KEY
    t = unicodedata.normalize("NFKD", (name or "").strip().lower())
    t = t.replace("ä", "ae").replace("ö", "oe").replace("ü", "ue").replace("ß", "ss")
    t = "".join(c for c in t if not unicodedata.combining(c))
    t = re.sub(r"[^a-z0-9]+", "_", t).strip("_")
    return t[:80] or "kanal"


def ist_unklar(wert) -> bool:
    return (str(wert or "")).strip() == KANAL_UNKLAR


def farbe_pruefen(farbe: str) -> str:
    """„#rrggbb“ (klein/groß egal) oder leer; sonst ValueError."""
    f = (farbe or "").strip()
    if not f:
        return ""
    if not _HEX.match(f):
        raise ValueError("Farbe bitte als #rrggbb angeben.")
    return f.upper()


def kontrast(farbe: str) -> str:
    """Textfarbe zur Kanalfarbe aus der relativen Luminanz (WCAG): „hell“ (weißer Text) auf
    dunklen Flächen, „dunkel“ auf hellen. Leer/ungültig → „dunkel“."""
    f = (farbe or "").strip()
    if not _HEX.match(f):
        return TEXT_DUNKEL
    def _kanal(wert: int) -> float:
        c = wert / 255.0
        return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4
    r, g, b = (int(f[i:i + 2], 16) for i in (1, 3, 5))
    luminanz = 0.2126 * _kanal(r) + 0.7152 * _kanal(g) + 0.0722 * _kanal(b)
    # Kontrast zu Weiß = 1.05 / (L + 0.05); zu Schwarz = (L + 0.05) / 0.05 – größeren nehmen
    return TEXT_HELL if (1.05 / (luminanz + 0.05)) >= ((luminanz + 0.05) / 0.05) else TEXT_DUNKEL


# --- Lesen ---------------------------------------------------------------------------------

def kanal_liste(session: Session, nur_aktive: bool = True) -> list[Vertriebskanal]:
    """Zeilen der Tabelle in Pflege-Reihenfolge (reihenfolge, Name)."""
    abfrage = session.query(Vertriebskanal)
    if nur_aktive:
        abfrage = abfrage.filter(Vertriebskanal.aktiv.is_(True))
    return abfrage.order_by(Vertriebskanal.reihenfolge, Vertriebskanal.name).all()


def tabelle_gefuellt(session: Session) -> bool:
    return session.query(Vertriebskanal.id).first() is not None


def _zeile_fuer(zeilen: list, wert) -> Vertriebskanal | None:
    """Zeile zu einem gespeicherten Wert: Name/Key exakt, Alias (v33 SWD), Abgleichstabelle
    ALT_NEU, abgeschnittene Labels („Stadtwerke Düsseld…“) über den Wortanfang."""
    roh = str(wert or "").strip()
    if not roh:
        return None
    n = _norm(roh)
    if not n:
        return None
    for z in zeilen:
        if _norm(z.name) == n or z.key == n:
            return z
    from app import leadmanagement as kern
    ziel = kern.kanal_anzeige(roh)
    if _norm(ziel) != n:
        for z in zeilen:
            if _norm(z.name) == _norm(ziel):
                return z
    neu = ALT_NEU.get(n)
    if neu:
        for z in zeilen:
            if _norm(z.name) == _norm(neu):
                return z
    if roh.endswith(("…", "...")) and len(n) >= 4:
        for z in zeilen:
            if _norm(z.name).startswith(n):
                return z
    return None


def kanal_zeile(session: Session, wert) -> Vertriebskanal | None:
    return _zeile_fuer(kanal_liste(session, nur_aktive=False), wert)


def name_aufloesen(session: Session, wert) -> str:
    """Kanonischer Name eines Wertes (Alias/alte Schreibweise → Listenname); unbekannte
    Werte kommen bereinigt zurück, „Standard“ → leer."""
    roh = str(wert or "").strip()
    if not roh or _norm(roh) == _norm(KANAL_STANDARD_ALT):
        return ""
    zeile = kanal_zeile(session, roh)
    if zeile is not None:
        return zeile.name
    return ALT_NEU.get(_norm(roh), roh)


def schluessel(wert) -> str:
    """Vergleichsschlüssel (klein, Alias/alte Schreibweise aufgelöst) ohne Datenbank."""
    n = _norm(wert)
    if not n:
        return ""
    from app import leadmanagement as kern
    return _norm(ALT_NEU.get(n) or kern.kanal_anzeige(str(wert).strip()))


def _schluessel_zeile(zeile: Vertriebskanal) -> str:
    return _norm(zeile.name)


def verwendungen(session: Session) -> dict:
    """{Schlüssel (klein, aufgelöst): (gesamt, letzte 90 Tage)} – gesamt = Kunden mit dem Kanal
    (kunden.vertriebskanal), 90 Tage = Vorgänge dieser Kunden mit Eingang/Anlage in den
    letzten 90 Tagen (Grundlage der Dropdown-Reihenfolge)."""
    grenze = datetime.now() - timedelta(days=VERWENDUNG_TAGE)
    ergebnis: dict = {}
    for wert, anzahl in (session.query(Kunde.vertriebskanal, func.count(Kunde.id))
                         .filter(Kunde.vertriebskanal.isnot(None), Kunde.vertriebskanal != "")
                         .group_by(Kunde.vertriebskanal)):
        s = schluessel(wert)
        if s:
            g, t = ergebnis.get(s, (0, 0))
            ergebnis[s] = (g + int(anzahl), t)
    for wert, anzahl in (session.query(Kunde.vertriebskanal, func.count(Vorgang.id))
                         .join(Kunde, Kunde.id == Vorgang.kunde_id)
                         .filter(Kunde.vertriebskanal.isnot(None), Kunde.vertriebskanal != "",
                                 func.coalesce(Vorgang.eingang_am, Vorgang.angelegt_am) >= grenze)
                         .group_by(Kunde.vertriebskanal)):
        s = schluessel(wert)
        if s:
            g, t = ergebnis.get(s, (0, 0))
            ergebnis[s] = (g, t + int(anzahl))
    return ergebnis


def verwendet_von(session: Session, wert) -> dict:
    """Verwendungen eines Kanals je Tabelle (alias-sicher): kunden, leads, quellen, gesamt."""
    s = schluessel(wert)
    zaehler = {"kunden": 0, "leads": 0, "quellen": 0}
    if s:
        for spalte, modell, name in ((Kunde.vertriebskanal, Kunde, "kunden"),
                                     (Lead.vertriebskanal, Lead, "leads"),
                                     (LeadQuelle.kanal, LeadQuelle, "quellen")):
            for gespeichert, anzahl in (session.query(spalte, func.count(modell.id))
                                        .filter(spalte.isnot(None), spalte != "").group_by(spalte)):
                if schluessel(gespeichert) == s:
                    zaehler[name] += int(anzahl)
    zaehler["gesamt"] = zaehler["kunden"] + zaehler["leads"] + zaehler["quellen"]
    return zaehler


def kanal_sortiert(session: Session) -> list[Vertriebskanal]:
    """Aktive Kanäle für Dropdowns: nach Verwendungen der letzten 90 Tage absteigend, dann
    alphabetisch; „?“ immer zuletzt (Vertrag Agent B/R)."""
    zeilen = kanal_liste(session, nur_aktive=True)
    nutzung = verwendungen(session)
    def _key(z):
        unklar = ist_unklar(z.name)
        return (1 if unklar else 0, -nutzung.get(_schluessel_zeile(z), (0, 0))[1], _norm(z.name))
    return sorted(zeilen, key=_key)


def kanal_namen_sortiert(session: Session, mit_unklar: bool = False) -> list[str]:
    return [z.name for z in kanal_sortiert(session) if mit_unklar or not ist_unklar(z.name)]


def kanal_optionen(session: Session, aktuell: str = "", mit_unklar: bool = True) -> list[dict]:
    """Dropdown-Einträge {name, farbe, aktiv, kontrast, label, gewaehlt}: aktive Kanäle sortiert,
    der aktuelle Wert eines Leads auch dann, wenn er inaktiv/unbekannt ist („(nicht mehr
    wählbar)“). Für Kartei, Inline-Bearbeitung (B), Außendienst-Kanalwahl (R)."""
    aktuell = (aktuell or "").strip()
    eintraege = []
    gesehen = set()
    for z in kanal_sortiert(session):
        if not mit_unklar and ist_unklar(z.name):
            continue
        eintraege.append({"name": z.name, "farbe": z.farbe or "", "aktiv": True,
                          "kontrast": kontrast(z.farbe), "gewaehlt": schluessel(z.name) == schluessel(aktuell),
                          "label": f"{z.name} – {UNKLAR_HINWEIS}" if ist_unklar(z.name) else z.name})
        gesehen.add(schluessel(z.name))
    if aktuell and schluessel(aktuell) not in gesehen:
        zeile = kanal_zeile(session, aktuell)
        name = zeile.name if zeile is not None else aktuell
        farbe = (zeile.farbe if zeile is not None else "") or kanal_farbe(session, aktuell)
        eintraege.append({"name": name, "farbe": farbe, "aktiv": False, "kontrast": kontrast(farbe),
                          "gewaehlt": True, "label": f"{name} (nicht mehr wählbar)"})
    return eintraege


def kanal_farben_map(session: Session) -> dict:
    """{name klein: #hex} aller Zeilen (auch inaktive), zusätzlich die Aliase (v33 „swd“) und
    Schreibweisen der Abgleichstabelle – Ersatz für den Parameter kanal_farben."""
    from app import leadmanagement as kern
    farben: dict = {}
    for z in kanal_liste(session, nur_aktive=False):
        if not z.farbe:
            continue
        farben[z.name.strip().lower()] = z.farbe
        farben.setdefault(_norm(z.name), z.farbe)
        for alias in kern.kanal_aliase(z.name):
            farben.setdefault(alias.strip().lower(), z.farbe)
    for alt, neu in ALT_NEU.items():
        f = farben.get(_norm(neu))
        if f:
            farben.setdefault(alt, f)
    return farben


def kanal_farbe(session: Session, name) -> str:
    """Farbe eines Kanals aus der Tabelle; Werte ohne Zeile bekommen die Automatik-Palette
    (Hash über den Namen), leer/„Standard“ keine Farbe."""
    roh = str(name or "").strip()
    if not roh or _norm(roh) == _norm(KANAL_STANDARD_ALT):
        return ""
    zeile = kanal_zeile(session, roh)
    if zeile is not None and zeile.farbe:
        return zeile.farbe
    return _PALETTE[_hash_index(roh, len(_PALETTE))]


# --- Schneller Zugriff ohne Request-Sitzung (Jinja-Global lm_kanal_farbe) --------------------

_CACHE = {"stand": 0.0, "farben": {}}


def cache_leeren() -> None:
    _CACHE["stand"] = 0.0
    _CACHE["farben"] = {}


def farben_schnell() -> dict:
    """Farbkarte mit Prozess-Cache (CACHE_SEKUNDEN) aus einer kurzen Lesesitzung – für Makros
    ohne Request-Kontext (kanal_badge). Schreibfunktionen dieses Moduls leeren den Cache."""
    if time.monotonic() - _CACHE["stand"] <= CACHE_SEKUNDEN and _CACHE["farben"]:
        return _CACHE["farben"]
    from app import db
    try:
        with db.kurz(schreibend=False) as s:
            farben = kanal_farben_map(s)
    except Exception:   # noqa: BLE001 – Farben sind Beiwerk, nie die Seite
        return _CACHE["farben"] or {}
    _CACHE["farben"] = farben
    _CACHE["stand"] = time.monotonic()
    return farben


def farbe_schnell(name) -> str:
    roh = str(name or "").strip()
    if not roh or _norm(roh) == _norm(KANAL_STANDARD_ALT):
        return ""
    farben = farben_schnell()
    f = farben.get(roh.lower()) or farben.get(_norm(roh)) or farben.get(schluessel(roh))
    return f or _PALETTE[_hash_index(roh, len(_PALETTE))]


# --- Kanal „?“ -----------------------------------------------------------------------------

def _kunde_von(objekt) -> Kunde | None:
    if objekt is None:
        return None
    if isinstance(objekt, Kunde):
        return objekt
    if isinstance(objekt, Vorgang):
        kunde = getattr(objekt, "kunde", None)
        if isinstance(kunde, Kunde):
            return kunde
        s = object_session(objekt)
        return s.get(Kunde, objekt.kunde_id) if s is not None and objekt.kunde_id else None
    return None


def kanal_unklar(vorgang) -> bool:
    """True, wenn der Kunde des Vorgangs den Kanal „?“ trägt (auch Kunde oder Wert direkt
    übergebbar). Vertrag Agent T: vor dem TAIFUN-Export prüfen."""
    if isinstance(vorgang, str):
        return ist_unklar(vorgang)
    kunde = _kunde_von(vorgang)
    return bool(kunde is not None and ist_unklar(kunde.vertriebskanal))


def kanal_pflicht_offen(vorgang) -> str:
    """„Vertriebskanal klären“ bei Kanal „?“, sonst leer (Pflichtfeld-Zähler, Tooltips)."""
    return UNKLAR_HINWEIS if kanal_unklar(vorgang) else ""


# --- Pflege ---------------------------------------------------------------------------------

def _parameter(session: Session, name: str, standard: str = "") -> str:
    from app import leadmanagement as kern
    return kern.parameter_holen(session, name, standard) or ""


def _parameter_setzen(session: Session, name: str, wert: str) -> None:
    from app import leadmanagement as kern
    kern.parameter_setzen(session, name, wert)


def kanal_farben_parameter_schreiben(session: Session) -> bool:
    """Spiegelt die Tabelle in den Parameter kanal_farben (JSON {Name: #hex}); True bei
    Änderung. Alt-Lesestellen bleiben damit auch ohne Codeänderung farbig."""
    werte = {z.name: z.farbe for z in kanal_liste(session, nur_aktive=False) if z.farbe}
    neu = json.dumps(werte, ensure_ascii=False, sort_keys=True) if werte else ""
    alt = _parameter(session, PARAMETER_FARBEN, "")
    if alt.strip() == neu.strip():
        return False
    _parameter_setzen(session, PARAMETER_FARBEN, neu)
    cache_leeren()
    return True


def _freier_key(session: Session, name: str, ausser_id: int | None = None) -> str:
    basis = key_aus_name(name)
    key = basis
    n = 2
    while True:
        treffer = session.query(Vertriebskanal).filter(Vertriebskanal.key == key).first()
        if treffer is None or treffer.id == ausser_id:
            return key
        key = f"{basis}_{n}"
        n += 1


def _name_pruefen(session: Session, name: str, ausser_id: int | None = None) -> str:
    sauber = re.sub(r"\s+", " ", (name or "").strip())
    if not sauber:
        raise ValueError("Bitte einen Kanalnamen eingeben.")
    if len(sauber) > NAME_MAX:
        raise ValueError(f"Der Kanalname darf höchstens {NAME_MAX} Zeichen haben.")
    if _norm(sauber) == _norm(KANAL_STANDARD_ALT):
        raise ValueError("„Standard“ ist kein Vertriebskanal (Angebotsprofil-Fallback).")
    for z in kanal_liste(session, nur_aktive=False):
        if z.id != ausser_id and _norm(z.name) == _norm(sauber):
            raise ValueError(f"Den Kanal „{z.name}“ gibt es schon"
                             + ("" if z.aktiv else " (inaktiv – wieder aktivieren)") + ".")
    return sauber


def kanal_anlegen(session: Session, name: str, farbe: str = "", aktiv: bool = True,
                  pflicht_hinweis: str = "", reihenfolge: int | None = None) -> Vertriebskanal:
    """Neuer Kanal; ohne Farbe die Automatik-Palette. ValueError bei leerem/doppeltem Namen."""
    sauber = _name_pruefen(session, name)
    farbe = farbe_pruefen(farbe) or _PALETTE[_hash_index(sauber, len(_PALETTE))].upper()
    if reihenfolge is None:
        reihenfolge = (session.query(func.max(Vertriebskanal.reihenfolge)).scalar() or 0) + 1
    zeile = Vertriebskanal(key=_freier_key(session, sauber), name=sauber, farbe=farbe,
                           aktiv=bool(aktiv), pflicht_hinweis=(pflicht_hinweis or "")[:200],
                           reihenfolge=int(reihenfolge), angelegt_am=datetime.now())
    session.add(zeile)
    session.flush()
    kanal_farben_parameter_schreiben(session)
    cache_leeren()
    return zeile


def _werte_ersetzen(session: Session, zeile: Vertriebskanal, neuer_name: str,
                    alte_namen: set) -> int:
    """Alle gespeicherten Schreibweisen des Kanals (Kunden, Leads, Quellen) auf den neuen
    Namen setzen; liefert die Anzahl geänderter Datensätze."""
    geaendert = 0
    for spalte, modell in ((Kunde.vertriebskanal, Kunde), (Lead.vertriebskanal, Lead),
                           (LeadQuelle.kanal, LeadQuelle)):
        werte = [w for (w,) in session.query(spalte).filter(spalte.isnot(None), spalte != "")
                 .distinct() if w and (schluessel(w) in alte_namen or _norm(w) in alte_namen)
                 and w != neuer_name]
        for wert in werte:
            geaendert += session.query(modell).filter(spalte == wert).update(
                {spalte.key: neuer_name}, synchronize_session=False)
    return geaendert


def kanal_umbenennen(session: Session, zeile: Vertriebskanal, neuer_name: str) -> tuple[bool, str]:
    """Umbenennen wirkt überall: kunden/leads/lead_quellen, profile.kanalwerte (Angebotsprofil-
    Zuordnung v9), Parameter hv_ausschluss und kanal_ad_regel, kanal_farben. „?“ bleibt „?“."""
    if ist_unklar(zeile.name):
        return False, "Der Kanal „?“ (Vertriebskanal unklar) kann nicht umbenannt werden."
    try:
        sauber = _name_pruefen(session, neuer_name, ausser_id=zeile.id)
    except ValueError as fehler:
        return False, str(fehler)
    if sauber == zeile.name:
        return True, "Keine Änderung."
    alt = zeile.name
    from app import leadmanagement as kern
    alte = {_norm(alt), schluessel(alt)} | {_norm(a) for a in kern.kanal_aliase(alt)}
    alte |= {k for k, v in ALT_NEU.items() if _norm(v) == _norm(alt)}
    zeile.name = sauber
    zeile.key = _freier_key(session, sauber, ausser_id=zeile.id)
    session.flush()
    anzahl = _werte_ersetzen(session, zeile, sauber, alte)
    # Angebotsprofile: Kanalwerte (kommagetrennt) – Eintrag austauschen, Dubletten vermeiden
    for profil in session.query(Profil):
        teile = [t.strip() for t in (profil.kanalwerte or "").split(",") if t.strip()]
        if not teile:
            continue
        neu_teile: list[str] = []
        getroffen = False
        for t in teile:
            ziel = sauber if (_norm(t) in alte or schluessel(t) in alte) else t
            getroffen = getroffen or ziel != t
            if ziel not in neu_teile:
                neu_teile.append(ziel)
        if getroffen:
            profil.kanalwerte = ", ".join(neu_teile)[:200]
    # Parameter hv_ausschluss (Semikolon-Liste aus Kanälen und Quellen-Keys)
    roh = _parameter(session, "hv_ausschluss", "")
    if roh.strip():
        teile = [t.strip() for t in roh.split(";") if t.strip()]
        neu_teile = []
        getroffen = False
        for t in teile:
            ziel = sauber if (_norm(t) in alte or schluessel(t) in alte) else t
            getroffen = getroffen or ziel != t
            if ziel not in neu_teile:
                neu_teile.append(ziel)
        if getroffen:
            _parameter_setzen(session, "hv_ausschluss", "; ".join(neu_teile))
    # Parameter kanal_ad_regel (JSON {kanal klein: [ad_ids]}) über lead_termin
    try:
        from app import lead_termin
        regel = lead_termin.kanal_regel(session)
        if regel:
            neu_regel: dict = {}
            getroffen = False
            for kanal, ids in regel.items():
                ziel = sauber.lower() if (_norm(kanal) in alte or schluessel(kanal) in alte) else kanal
                getroffen = getroffen or ziel != kanal
                vorhanden = neu_regel.setdefault(ziel, [])
                vorhanden.extend(i for i in ids if i not in vorhanden)
            if getroffen:
                lead_termin.kanal_regel_setzen(session, neu_regel)
    except Exception:   # noqa: BLE001 – Regel ist Beiwerk des Umbenennens
        pass
    kanal_farben_parameter_schreiben(session)
    cache_leeren()
    return True, (f"Kanal „{alt}“ heißt jetzt „{sauber}“ – {anzahl} Datensatz"
                  f"{'' if anzahl == 1 else 'e'} (Kunden, Leads, Quellen) umgestellt.")


def farbe_setzen(session: Session, zeile: Vertriebskanal, farbe: str) -> tuple[bool, str]:
    try:
        neu = farbe_pruefen(farbe)
    except ValueError as fehler:
        return False, str(fehler)
    if not neu:
        return False, "Bitte eine Farbe wählen."
    zeile.farbe = neu
    session.flush()
    kanal_farben_parameter_schreiben(session)
    cache_leeren()
    return True, f"Farbe von „{zeile.name}“ gespeichert."


def kanal_deaktivieren(session: Session, zeile: Vertriebskanal) -> tuple[bool, str]:
    """Löschen im Sinne der Oberfläche: nicht mehr wählbar, Leads behalten den Kanal."""
    if ist_unklar(zeile.name):
        return False, "Der Kanal „?“ (Vertriebskanal unklar) bleibt immer aktiv."
    if not zeile.aktiv:
        return True, f"„{zeile.name}“ ist bereits inaktiv."
    zeile.aktiv = False
    session.flush()
    cache_leeren()
    return True, f"„{zeile.name}“ ist nicht mehr wählbar – bestehende Leads behalten den Kanal."


def kanal_aktivieren(session: Session, zeile: Vertriebskanal) -> tuple[bool, str]:
    if zeile.aktiv:
        return True, f"„{zeile.name}“ ist bereits aktiv."
    zeile.aktiv = True
    session.flush()
    cache_leeren()
    return True, f"„{zeile.name}“ ist wieder wählbar."


def kanal_loeschen(session: Session, zeile: Vertriebskanal) -> tuple[bool, str]:
    """Endgültig nur ohne Verwendung; sonst wird der Kanal deaktiviert (aktiv = 0). Liefert
    (endgültig_geloescht, Meldung)."""
    if ist_unklar(zeile.name):
        return False, "Der Kanal „?“ (Vertriebskanal unklar) kann nicht gelöscht werden."
    nutzung = verwendet_von(session, zeile.name)
    if nutzung["gesamt"]:
        kanal_deaktivieren(session, zeile)
        return False, (f"„{zeile.name}“ wird noch verwendet ({nutzung['kunden']} Kunden, "
                       f"{nutzung['leads']} monday-Leads, {nutzung['quellen']} Quellen) – nur "
                       "deaktiviert: nicht mehr wählbar, das Label bleibt an den Leads sichtbar.")
    name = zeile.name
    session.delete(zeile)
    session.flush()
    kanal_farben_parameter_schreiben(session)
    cache_leeren()
    return True, f"„{name}“ endgültig gelöscht (kein Lead trug den Kanal)."


# --- Bestand abgleichen / Migration ---------------------------------------------------------

def bestand_abgleichen(session: Session) -> list[str]:
    """Gespeicherte Kanalwerte (Kunden, monday-Leads, Quellen) gegen die Tabelle abgleichen:
    „Standard“ → kein Kanal; Aliase/alte Schreibweisen → Listenname; unbekannte Werte → Kanal
    mit aktiv = 0 (Label bleibt sichtbar, nicht neu wählbar). Idempotent, Meldungen ASCII."""
    meldungen: list[str] = []
    zeilen = kanal_liste(session, nur_aktive=False)
    for spalte, modell, tabelle in ((Kunde.vertriebskanal, Kunde, "kunden"),
                                    (Lead.vertriebskanal, Lead, "leads"),
                                    (LeadQuelle.kanal, LeadQuelle, "lead_quellen")):
        werte = [w for (w,) in session.query(spalte).filter(spalte.isnot(None), spalte != "")
                 .distinct()]
        for wert in sorted(werte, key=_norm):
            if _norm(wert) == _norm(KANAL_STANDARD_ALT):
                leer = None if modell is LeadQuelle else ""
                n = session.query(modell).filter(spalte == wert).update(
                    {spalte.key: leer}, synchronize_session=False)
                meldungen.append(f"Kanaele (v35): '{wert}' -> kein Kanal ({tabelle}: {n} Datensaetze)")
                continue
            zeile = _zeile_fuer(zeilen, wert)
            if zeile is None:
                ziel = ALT_NEU.get(_norm(wert))
                if ziel:
                    zeile = _zeile_fuer(zeilen, ziel)
            if zeile is None:
                zeile = kanal_anlegen(session, wert, aktiv=False)
                zeilen.append(zeile)
                meldungen.append(f"Kanaele (v35): '{wert}' als inaktiver Kanal angelegt "
                                 f"(nicht in der Liste; {tabelle})")
            if wert != zeile.name:
                n = session.query(modell).filter(spalte == wert).update(
                    {spalte.key: zeile.name}, synchronize_session=False)
                meldungen.append(f"Kanaele (v35): '{wert}' -> '{zeile.name}' ({tabelle}: {n} Datensaetze)")
    if meldungen:
        session.flush()
        cache_leeren()
    return meldungen


def migration_v35_kanaele(session: Session) -> list[str]:
    """Phase 184: Startliste anlegen (30 Kanaele, '?' mit Pflichthinweis), Bestand abgleichen,
    Parameter kanal_farben aus der Tabelle schreiben. Idempotent – zweiter Lauf still."""
    meldungen: list[str] = []
    vorhanden = kanal_liste(session, nur_aktive=False)
    neu = 0
    for stelle, (name, farbe) in enumerate(START_KANAELE, start=1):
        if any(_norm(z.name) == _norm(name) or z.key == key_aus_name(name) for z in vorhanden):
            continue
        zeile = kanal_anlegen(session, name, farbe, aktiv=True,
                              pflicht_hinweis=(UNKLAR_HINWEIS if ist_unklar(name) else ""),
                              reihenfolge=stelle)
        vorhanden.append(zeile)
        neu += 1
    if neu:
        meldungen.append(f"Kanaele (v35): {neu} Vertriebskanaele aus der Liste angelegt")
    meldungen.extend(bestand_abgleichen(session))
    if kanal_farben_parameter_schreiben(session):
        meldungen.append("Kanaele (v35): Parameter kanal_farben aus der Tabelle geschrieben")
    session.flush()
    return meldungen
