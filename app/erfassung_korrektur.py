# v38 (PLAN_V23 Phase 202, Agent E): Erfassung zwischenspeichern („Entwurf · Frage 12 von 31“,
# „Später fortsetzen“, Wiedereinstieg bei der ersten unbeantworteten Frage) und nachträglich
# korrigieren („Antworten korrigieren“ mit Rechte-/Sperrprüfung, Diff der Antworten,
# Änderungsnotiz im Notizen-Chat, Badge „nachträglich geändert (TT.MM.)“) sowie die Objektzeile
# der Erfassungslisten (Phase 204: „<Objektbezeichnung> · <Straße Nr., PLZ Ort>“).
#
# Befund 16.10.2026 (diagnose/v38/E_patches/befund_abbruch.py, v37-Stand): Antworten werden nur
# seitenweise beim „Weiter“/„Zurück“ gespeichert (nicht je Frage), unvollständige Bögen tragen
# bereits den Status „Entwurf“ (Default des Modells) und stehen nur in der AD-Übersicht /erfassung,
# der Wiedereinstieg ist seitenbasiert (seite_index), ein beforeunload gab es nicht.
#
# Schnittstelle (Router erfassung.py / erfassungsliste.py, Templates, Jinja-Global):
#   fortschritt(logik, antworten) -> {nr, gesamt, frage, seite_nr, fertig}
#   entwurf_badge(logik, erfassung, antworten=None, heute=None) -> {text, nr, gesamt, alt, seite_nr, frage_id}
#   entwurf_alt(erfassung, heute=None) -> bool                  (Warnfarbe ab ENTWURF_WARN_TAGE Tagen)
#   verknuepfte_angebote(session, erfassung) / verknuepfte_aus_liste(erfassung, angebote)
#   sperre(angebote) -> (gesperrt, text)                          (irgendein Angebot nicht mehr „Entwurf“)
#   korrektur_erlaubt(benutzer, erfassung) -> bool               (Basisrolle: AD nur eigene, ID/Admin alle)
#   kontext(session, benutzer, erfassung, angebote=None) -> dict  (Knopf, Sperre, Badge, Angebots-Hinweis)
#   aenderungen(logik, vorher, nachher) -> list[{id, titel, alt, neu}]
#   notiz_text(name, zeit, liste) -> str                         (Kurzform ≤ 5, danach „… und n weitere“ +
#                                                                 Block „Alle Änderungen:“ – aufklappbar im Chat)
#   korrektur_verbuchen(session, erfassung, benutzer, liste, zeit=None) -> VorgangsNotiz | None
#   freitext_aenderung(session, erfassung, benutzer, alt, neu) -> VorgangsNotiz | None
#   objekt_zeilen(session, erfassungen, kunden=None) -> {erfassung_id: {text, bezeichnung, adresse, kunde, mehrere}}
#   info_fuer_template(erfassung, benutzer, angebote) -> dict    (Jinja-Global, ohne Datenbank – Vorgangsakte)
import json
from datetime import date, datetime, timedelta

from sqlalchemy.orm import Session

from app import konfigurator as engine
from app.models import Angebot, Erfassung, Kunde, Vorgang, VorgangObjekt

STATUS_ENTWURF = "Entwurf"
# [ANNAHME, Plan Phase 202]: Entwürfe ab 30 Tagen (Anlagedatum) mit Warnfarbe, kein automatisches Löschen
ENTWURF_WARN_TAGE = 30
SPERR_TEXT = "Angebot ist bereits versandfertig"
# [ANNAHME]: gesperrt, sobald irgendein verknüpftes Angebot (inkl. Versionen/Kombi, TAIFUN-Eintrag) den
# Status „Entwurf“ verlassen hat – Versand vorbereitet, Versendet, Angenommen, Abgelehnt, Überholt …
STATUS_FREI = (STATUS_ENTWURF,)
HINWEIS_ANGEBOT = "Antworten geändert. Bitte das Angebot neu berechnen."
MELDUNG_GESPEICHERT = "Erfassung gespeichert. Sie können jederzeit weitermachen."
MELDUNG_KORREKTUR = "Korrektur gespeichert."
MELDUNG_GESPERRT = ("Antworten können nicht mehr korrigiert werden – "
                    "das Angebot ist bereits versandfertig.")
MELDUNG_KEINE_AENDERUNG = "Keine Änderung – die Antworten sind unverändert."
NOTIZ_TITEL = "Erfassung nachträglich geändert von {name} am {zeit}: "
NOTIZ_KURZ_MAX = 5
NOTIZ_HERKUNFT = "Erfassung (Korrektur)"        # notizen.kennzeichen → „Vertrieb“
NOTIZ_ALLE_MARKER = "\nAlle Änderungen:\n"     # _komponenten._nc_eintrag klappt den Block auf
TITEL_MAX = 70
FREITEXT_MAX = 80
RICHTUNG_SPAETER = "spaeter"
RICHTUNG_KORREKTUR = "korrektur"


# --- Zwischenspeichern / Fortschritt -------------------------------------------------------

def fortschritt(logik, antworten: dict) -> dict:
    """Erste unbeantwortete sichtbare Frage des Bogens: nr (1-basiert in der Reihenfolge der
    sichtbaren Fragen), gesamt (Anzahl sichtbarer Fragen – folgt den Antworten), frage,
    seite_nr (Index der Bogenseite), fertig (keine offene Frage mehr). Optionale Fragen zählen
    wie im Bogen (naechste_frage), nicht wie die Prüfseite (naechste_pflichtfrage)."""
    sichtbar = engine.sichtbare_fragen(logik, antworten)
    gesamt = len(sichtbar)
    seiten = logik.seiten
    for nr, frage in enumerate(sichtbar, 1):
        if frage.id not in antworten:
            seite_nr = seiten.index(frage.seite) if frage.seite in seiten else 0
            return {"nr": nr, "gesamt": gesamt, "frage": frage, "seite_nr": seite_nr, "fertig": False}
    return {"nr": gesamt, "gesamt": gesamt, "frage": None,
            "seite_nr": max(len(seiten) - 1, 0), "fertig": True}


def entwurf_alt(erfassung: Erfassung, heute: date | None = None) -> bool:
    """Entwurf älter als ENTWURF_WARN_TAGE Tage (Anlagedatum) → Warnfarbe in den Listen."""
    bezug = getattr(erfassung, "angelegt_am", None)
    if bezug is None:
        return False
    tag = bezug.date() if isinstance(bezug, datetime) else bezug
    return (heute or date.today()) - tag >= timedelta(days=ENTWURF_WARN_TAGE)


def entwurf_badge(logik, erfassung: Erfassung, antworten: dict | None = None,
                  heute: date | None = None) -> dict:
    """Badge-Text „Entwurf · Frage 12 von 31“ (ohne Bogen-Logik nur „Entwurf“) + Warnkennzeichen."""
    ergebnis = {"text": STATUS_ENTWURF, "nr": 0, "gesamt": 0, "alt": entwurf_alt(erfassung, heute),
                "seite_nr": int(erfassung.seite_index or 0), "frage_id": ""}
    if logik is None or not getattr(logik, "fragen", None):
        return ergebnis
    if antworten is None:
        antworten = json.loads(erfassung.antworten_json or "{}")
    f = fortschritt(logik, antworten)
    ergebnis.update({"nr": f["nr"], "gesamt": f["gesamt"], "seite_nr": f["seite_nr"],
                     "frage_id": f["frage"].id if f["frage"] else ""})
    if f["gesamt"]:
        ergebnis["text"] = (f"Entwurf · Frage {f['nr']} von {f['gesamt']}" if not f["fertig"]
                            else f"Entwurf · vollständig ({f['gesamt']} Fragen)")
    return ergebnis


def logik_fuer(session: Session, erfassung: Erfassung):
    """Sparten-Sicht der Logik für eine Erfassung (None = kein Bogen, z. B. Freitext-Sparten)."""
    from app import logik as logik_modul
    from app.logik import logik_fuer_sparte
    logik, bericht = logik_modul.hole_logik(session)
    if not bericht.ok:
        return None
    return logik_fuer_sparte(logik, erfassung.sparte or "WP")


def entwurf_badges(session: Session, erfassungen, heute: date | None = None) -> dict[int, dict]:
    """Badges aller Entwürfe einer Liste (eine Logik-Sicht je Sparte)."""
    from app import logik as logik_modul
    from app.logik import logik_fuer_sparte
    ergebnis: dict[int, dict] = {}
    sichten: dict[str, object] = {}
    logik_voll = None
    for e in erfassungen:
        if e.status != STATUS_ENTWURF:
            continue
        sparte = e.sparte or "WP"
        if sparte not in sichten:
            if logik_voll is None:
                logik_voll, bericht = logik_modul.hole_logik(session)
                if not bericht.ok:
                    logik_voll = False
            sichten[sparte] = (logik_fuer_sparte(logik_voll, sparte) if logik_voll else None)
        ergebnis[e.id] = entwurf_badge(sichten[sparte], e, heute=heute)
    return ergebnis


# --- Rechte und Sperre ----------------------------------------------------------------------

def korrektur_erlaubt(benutzer, erfassung: Erfassung) -> bool:
    """Außendienst (Basisrolle, auch Handelsvertreter) nur an eigenen Erfassungen
    (erfassungen.benutzer_id = eigene ID), Innendienst und Admin an allen, andere Rollen nie."""
    if benutzer is None or erfassung is None:
        return False
    basis = getattr(benutzer, "basisrolle", None) or getattr(benutzer, "rolle", "") or ""
    if basis in ("admin", "innendienst"):
        return True
    if basis == "aussendienst":
        return erfassung.benutzer_id == getattr(benutzer, "id", None)
    return False


def _kette_aus_liste(start_id: int | None, angebote) -> list:
    """Angebot + alle Versionen (vorgaenger_id in beide Richtungen) aus einer gegebenen Liste."""
    if not start_id:
        return []
    je_id = {a.id: a for a in angebote}
    if start_id not in je_id:
        return []
    gefunden: dict[int, object] = {}
    offen = [start_id]
    while offen:
        aid = offen.pop()
        a = je_id.get(aid)
        if a is None or aid in gefunden:
            continue
        gefunden[aid] = a
        if a.vorgaenger_id and a.vorgaenger_id in je_id:
            offen.append(a.vorgaenger_id)
        offen.extend(b.id for b in angebote if b.vorgaenger_id == aid and b.id not in gefunden)
    return list(gefunden.values())


def verknuepfte_aus_liste(erfassung: Erfassung, angebote) -> list:
    return _kette_aus_liste(getattr(erfassung, "angebot_id", None), list(angebote or []))


def verknuepfte_angebote(session: Session, erfassung: Erfassung) -> list[Angebot]:
    """Das Angebot der Erfassung plus seine Versionen (Kette über vorgaenger_id in beide
    Richtungen – „Überarbeiten“ hängt die Erfassung immer an die neueste Version)."""
    start = session.get(Angebot, erfassung.angebot_id) if erfassung.angebot_id else None
    if start is None:
        return []
    kandidaten = [start]
    if start.vorgang_id:
        kandidaten = session.query(Angebot).filter(Angebot.vorgang_id == start.vorgang_id).all()
        if start not in kandidaten:
            kandidaten.append(start)
    else:
        kandidaten += session.query(Angebot).filter(Angebot.kunde_id == start.kunde_id).all()
    return _kette_aus_liste(start.id, kandidaten)


def sperre(angebote) -> tuple[bool, str]:
    """Gesperrt, sobald ein verknüpftes Angebot den Status „Entwurf“ verlassen hat."""
    for a in angebote or []:
        if (a.status or STATUS_ENTWURF) not in STATUS_FREI:
            return True, SPERR_TEXT
    return False, ""


def badge_text(erfassung: Erfassung) -> str:
    """„nachträglich geändert (16.10.)“ – leer ohne Korrektur."""
    am = getattr(erfassung, "geaendert_am", None)
    if not am:
        return ""
    return f"nachträglich geändert ({am.strftime('%d.%m.')})"


def _angebot_entwurf(angebote) -> Angebot | None:
    """Verknüpfter Tool-Angebotsentwurf (Hinweis „Angebot neu berechnen“); TAIFUN-Einträge nie."""
    for a in angebote or []:
        if (a.status or STATUS_ENTWURF) == STATUS_ENTWURF and not getattr(a, "extern", False):
            return a
    return None


def kontext(session: Session | None, benutzer, erfassung: Erfassung, angebote=None) -> dict:
    """Alles für Knopf, Sperre und Badges: erlaubt, gesperrt, sperr_text, knopf_aktiv, badge,
    geaendert_am, geaendert_von_name, angebot_entwurf, hinweis_angebot (Entwurf verknüpft und
    nachträglich geändert), entwurf (Status Entwurf)."""
    if angebote is None:
        angebote = verknuepfte_angebote(session, erfassung) if session is not None else []
    else:
        angebote = verknuepfte_aus_liste(erfassung, angebote)
    gesperrt, text = sperre(angebote)
    erlaubt = korrektur_erlaubt(benutzer, erfassung)
    name = ""
    if session is not None and getattr(erfassung, "geaendert_von", None):
        from app.models import Benutzer
        b = session.get(Benutzer, erfassung.geaendert_von)
        name = b.name if b is not None else ""
    entwurf = _angebot_entwurf(angebote)
    return {"erlaubt": erlaubt, "gesperrt": gesperrt, "sperr_text": text,
            "knopf_aktiv": erlaubt and not gesperrt and erfassung.status != STATUS_ENTWURF,
            "badge": badge_text(erfassung), "geaendert_am": getattr(erfassung, "geaendert_am", None),
            "geaendert_von_name": name, "angebot_entwurf": entwurf,
            "hinweis_angebot": bool(entwurf is not None and getattr(erfassung, "geaendert_am", None)),
            "hinweis_text": HINWEIS_ANGEBOT, "entwurf": erfassung.status == STATUS_ENTWURF}


def info_fuer_template(erfassung: Erfassung, benutzer, angebote) -> dict:
    """Jinja-Global `erfassung_korrektur_info` (Vorgangsakte, Karte Erfassung) – ohne Datenbank:
    die Akte hat alle Angebote des Vorgangs bereits geladen."""
    return kontext(None, benutzer, erfassung, angebote=list(angebote or []))


# --- Diff und Änderungsnotiz ----------------------------------------------------------------

def _titel(frage, frage_id: str) -> str:
    text = (frage.text if frage is not None else "") or ""
    text = text.strip()
    if len(text) > TITEL_MAX:
        text = text[:TITEL_MAX - 1].rstrip() + "…"
    return text


def _anzeige(frage, wert) -> str:
    if frage is None:
        if isinstance(wert, (dict, list)):
            return json.dumps(wert, ensure_ascii=False)
        return "– keine Angabe –" if wert in (None, "") else str(wert)
    return engine.antwort_anzeige(frage, wert)


def aenderungen(logik, vorher: dict, nachher: dict) -> list[dict]:
    """Geänderte Antworten als Liste {id, titel, alt, neu} in Bogen-Reihenfolge (Klone wie
    KR01#2 über ihre Basisfrage); unveränderte Anzeige (z. B. 1990 vs. 1990.0) zählt nicht."""
    fragen = getattr(logik, "fragen", {}) if logik is not None else {}

    def frage_fuer(frage_id: str):
        return fragen.get(frage_id) or fragen.get(frage_id.split("#", 1)[0])

    def reihenfolge(frage_id: str):
        f = frage_fuer(frage_id)
        return (0, f.reihenfolge, frage_id) if f is not None else (1, 0, frage_id)

    ergebnis = []
    for frage_id in sorted(set(vorher) | set(nachher), key=reihenfolge):
        if vorher.get(frage_id) == nachher.get(frage_id):
            continue
        frage = frage_fuer(frage_id)
        alt = _anzeige(frage, vorher.get(frage_id))
        neu = _anzeige(frage, nachher.get(frage_id))
        if alt == neu:
            continue
        ergebnis.append({"id": frage_id, "titel": _titel(frage, frage_id), "alt": alt, "neu": neu})
    return ergebnis


def _zeile(a: dict) -> str:
    titel = f" {a['titel']}" if a.get("titel") else ""
    return f"{a['id']}{titel}: {a['alt']} → {a['neu']}"


def notiz_text(name: str, zeit: datetime, liste: list[dict]) -> str:
    """„Erfassung nachträglich geändert von <Name> am TT.MM.JJJJ HH:MM: A04 …: KG → DG; B02 …“;
    ab der sechsten Änderung „… und n weitere“ und darunter der vollständige Block
    „Alle Änderungen:“ (das Chat-Makro zeigt ihn aufklappbar)."""
    kopf = NOTIZ_TITEL.format(name=name or "System", zeit=zeit.strftime("%d.%m.%Y %H:%M"))
    kurz = [_zeile(a) for a in liste[:NOTIZ_KURZ_MAX]]
    rest = len(liste) - len(kurz)
    text = kopf + "; ".join(kurz)
    if rest > 0:
        text += f" … und {rest} weitere"
        text += NOTIZ_ALLE_MARKER + "\n".join(f"– {_zeile(a)}" for a in liste)
    return text


def _vorgang_id(session: Session, erfassung: Erfassung) -> int | None:
    if erfassung.vorgang_id:
        return erfassung.vorgang_id
    from app import vorgaenge as vorgaenge_modul
    vorgang = vorgaenge_modul.vorgang_fuer_erfassung(session, erfassung)
    return vorgang.id if vorgang is not None else None


def korrektur_verbuchen(session: Session, erfassung: Erfassung, benutzer, liste: list[dict],
                        zeit: datetime | None = None):
    """Badge-Felder setzen und die Änderungsnotiz schreiben (Autor „System“, Herkunft Erfassung –
    der korrigierende Benutzer steht im Text). Ohne Änderungen passiert nichts."""
    if not liste:
        return None
    from app import notizen
    zeit = zeit or datetime.now()
    erfassung.geaendert_am = zeit
    erfassung.geaendert_von = getattr(benutzer, "id", None)
    vorgang_id = _vorgang_id(session, erfassung)
    if not vorgang_id:
        return None
    text = notiz_text(getattr(benutzer, "name", "") or "System", zeit, liste)
    return notizen.notiz_anlegen(session, vorgang_id, None, text, herkunft=NOTIZ_HERKUNFT)


def _kuerzen(text: str, laenge: int = FREITEXT_MAX) -> str:
    text = " ".join((text or "").split())
    if not text:
        return "– leer –"
    return text if len(text) <= laenge else text[:laenge - 1].rstrip() + "…"


def freitext_aenderung(session: Session, erfassung: Erfassung, benutzer, alt: str, neu: str):
    """Der Freitext-Editor (v13, POST /erfassungen/{id}/freitext) schreibt denselben Eintrag."""
    if (alt or "").strip() == (neu or "").strip():
        return None
    liste = [{"id": "Freitext", "titel": "Beschreibung des Vorhabens",
              "alt": f"„{_kuerzen(alt)}“", "neu": f"„{_kuerzen(neu)}“"}]
    return korrektur_verbuchen(session, erfassung, benutzer, liste)


# --- Objektzeile der Listen (Phase 204) -------------------------------------------------------

def _adresse(strasse: str, plz: str, ort: str) -> str:
    return ", ".join(t for t in ((strasse or "").strip(),
                                 " ".join(x for x in ((plz or "").strip(), (ort or "").strip()) if x))
                     if t)


def objekt_zeilen(session: Session, erfassungen, kunden: dict | None = None) -> dict[int, dict]:
    """Je Erfassung die Objektzeile: bei Vorgängen mit mehreren Objekten „<Bezeichnung> · <Adresse>“,
    bei Ein-Objekt-Vorgängen nur die Adresse, ohne Objektzuordnung die Kundenadresse mit „(Kunde)“.
    Master-Regel v31: beim Hauptobjekt (reihenfolge 1) zählt die Kundenadresse. Eine Abfrage je
    Liste (keine je Zeile); `kunden` = {id: Kunde} der Liste (sonst nachgeladen)."""
    erfassungen = list(erfassungen)
    if not erfassungen:
        return {}
    if kunden is None:
        kunden = {k.id: k for k in session.query(Kunde)
                  .filter(Kunde.id.in_({e.kunde_id for e in erfassungen} or {0}))}
    objekt_ids = {e.objekt_id for e in erfassungen if e.objekt_id}
    vorgang_ids = {e.vorgang_id for e in erfassungen if e.vorgang_id}
    objekte: dict[int, VorgangObjekt] = {}
    if objekt_ids:
        objekte = {o.id: o for o in session.query(VorgangObjekt).filter(VorgangObjekt.id.in_(objekt_ids))}
    vorgang_ids |= {o.vorgang_id for o in objekte.values()}
    anzahl: dict[int, int] = {}
    if vorgang_ids:
        for o in (session.query(VorgangObjekt)
                  .filter(VorgangObjekt.vorgang_id.in_(vorgang_ids), VorgangObjekt.aktiv.is_(True))):
            anzahl[o.vorgang_id] = anzahl.get(o.vorgang_id, 0) + 1
    ergebnis: dict[int, dict] = {}
    for e in erfassungen:
        kunde = kunden.get(e.kunde_id)
        objekt = objekte.get(e.objekt_id) if e.objekt_id else None
        if objekt is None:
            adresse = _adresse(kunde.strasse, kunde.plz, kunde.ort) if kunde else ""
            ergebnis[e.id] = {"text": f"{adresse} (Kunde)" if adresse else "(Kunde)", "bezeichnung": "",
                              "adresse": adresse, "kunde": True, "mehrere": False}
            continue
        mehrere = anzahl.get(objekt.vorgang_id, 0) > 1
        if objekt.reihenfolge == 1 and kunde is not None and (kunde.strasse or kunde.ort):
            adresse = _adresse(kunde.strasse, kunde.plz, kunde.ort)
        else:
            adresse = _adresse(objekt.strasse, objekt.plz, objekt.ort)
            if not adresse and kunde is not None:
                adresse = _adresse(kunde.strasse, kunde.plz, kunde.ort)
        bezeichnung = (objekt.bezeichnung or "").strip() if mehrere else ""
        text = " · ".join(t for t in (bezeichnung, adresse) if t)
        ergebnis[e.id] = {"text": text, "bezeichnung": bezeichnung, "adresse": adresse,
                          "kunde": False, "mehrere": mehrere}
    return ergebnis


def objekt_zeile(session: Session, erfassung: Erfassung, kunde: Kunde | None = None) -> dict:
    kunden = {kunde.id: kunde} if kunde is not None else None
    return objekt_zeilen(session, [erfassung], kunden).get(erfassung.id, {"text": "", "bezeichnung": "",
                                                                             "adresse": "", "kunde": False,
                                                                             "mehrere": False})


def vorgang_von(session: Session, erfassung: Erfassung) -> Vorgang | None:
    return session.get(Vorgang, erfassung.vorgang_id) if erfassung.vorgang_id else None
