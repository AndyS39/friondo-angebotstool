# v28 (PLAN_PROJ_V6 Phase 136): Notizen über alle Phasen – der Notizen-Chat des
# Vorgangs (VorgangsNotiz, v10) ist die einzige Notizspur von Lead bis Montage.
# Dieses Modul liefert die Daten für das gemeinsame Makro `notizen_chat` in
# templates/_komponenten.html (Vorgangsakte, Projektakte, Kundenkartei,
# Montage-Backend nur lesend) und die Migration der alten Projektakten-Kommentare.
#
# Schnittstelle (Vertrag für alle Einbindungen):
#   kontext(session, vorgang_id, benutzer, limit=None, post_url=None, hinweis="",
#           vorgang=None, nur_lesen=False)
#       -> dict für notizen_chat(ctx): vorgang_id, post_url, eintraege, schreiben_erlaubt,
#          hinweis, mein_name, anzahl, limit
#   kontext_projekt(session, projekt, benutzer) -> dict | None (None ohne Vorgang)
#   kommentar_speichern(session, projekt, benutzer, text) -> (ok, meldung)
#   kommentar_speichern_eintrag(session, projekt, benutzer, text) -> (ok, meldung, eintrag|None)
#   schreiben_erlaubt(session, vorgang, benutzer) -> bool
#   notiz_anlegen(session, vorgang_id, benutzer, text, herkunft="") -> VorgangsNotiz
#   eintrag_json(notiz) -> dict  (JSON-Antwort der Schreibroute, Format laut Briefing)
#   migration_v28_notizen(session) -> list[str]  (idempotent, von migrate.py gerufen)

from datetime import datetime

from sqlalchemy.orm import Session

from app.models import Benutzer, Projekt, ProjektVerlauf, Vorgang, VorgangsNotiz

# Kennzeichen aus `herkunft` (Chat-Optik: Badge je Spur). Reihenfolge = Priorität
# bei zusammengesetzten Herkunftstexten („projektierung (migriert)“ → Projektierung).
KENNZEICHEN = (
    ("projektierung", "Projektierung", "nc-projektierung"),
    ("montage", "Montage", "nc-montage"),
    ("lead", "Lead", "nc-lead"),
    ("anruf", "Lead", "nc-lead"),
    ("vertrieb", "Vertrieb", "nc-vertrieb"),
    ("erfassung", "Vertrieb", "nc-vertrieb"),
    ("angebot", "Vertrieb", "nc-vertrieb"),
    ("kombi-versand", "Vertrieb", "nc-vertrieb"),
)

# Werte, die die Schreibroute als `herkunft` aus dem Formular annimmt (Whitelist);
# alles andere wird aus der Rolle des Schreibers abgeleitet (herkunft_fuer).
HERKUNFT_WERTE = ("projektierung", "vertrieb", "lead", "montage")

MIGRIERT_HERKUNFT = "projektierung (migriert)"
MAX_TEXT = 2000


def kennzeichen(herkunft: str | None) -> tuple[str, str]:
    """(Text, CSS-Klasse) für die Herkunft einer Notiz; leer = ohne Badge.
    Bestehende Einträge tragen z. T. leere oder freie Herkunftstexte („Galerie“,
    „Rabatt-Freigabe“) – die bleiben als gekürzter Freitext-Badge lesbar."""
    h = (herkunft or "").strip().lower()
    if not h:
        return "", ""
    for schluessel, text, klasse in KENNZEICHEN:
        if schluessel in h:
            return text, klasse
    return (herkunft or "").strip()[:24], "nc-sonstige"


def herkunft_fuer(benutzer, gewuenscht: str = "") -> str:
    """Herkunft eines neuen Eintrags: Formularwert aus der Whitelist, sonst aus
    der Hauptrolle (Projektierung → projektierung, Leadmanagement → lead,
    Montage → montage, Vertrieb/Innendienst/Admin → vertrieb)."""
    wunsch = (gewuenscht or "").strip().lower()
    if wunsch in HERKUNFT_WERTE:
        return wunsch
    rolle = getattr(benutzer, "rolle", "") or ""
    return {"projektierung": "projektierung", "leadmanagement": "lead",
            "montage": "montage"}.get(rolle, "vertrieb")


def eintraege(session: Session, vorgang_id: int, limit: int | None = None) -> list:
    """Alle Einträge chronologisch (älteste zuerst); `limit` = nur die letzten n."""
    abfrage = (session.query(VorgangsNotiz)
               .filter(VorgangsNotiz.vorgang_id == vorgang_id)
               .order_by(VorgangsNotiz.zeit.asc(), VorgangsNotiz.id.asc()))
    notizen = abfrage.all()
    if limit:
        notizen = notizen[-limit:]
    return notizen


def _hat_projekt(session: Session, vorgang_id: int) -> bool:
    return bool(session.query(Projekt.id).filter(Projekt.vorgang_id == vorgang_id).first())


def schreiben_erlaubt(session: Session, vorgang: Vorgang | None, benutzer) -> bool:
    """Rechte (Plan Phase 136): Innendienst/Admin überall, Außendienst bei eigenen
    Vorgängen (wie die Vorgangsakte: vorgaenge.gehoert_benutzer), Rolle
    Projektierung für Vorgänge mit Projekt (Modul sichtbar), Rolle Leadmanagement
    für alle Vorgänge des Lead-Moduls (Modul sichtbar); Hauptrolle Montage NUR
    lesen. Einträge sind unveränderlich (kein Bearbeiten/Löschen)."""
    if benutzer is None or vorgang is None:
        return False
    rolle = getattr(benutzer, "rolle", "") or ""
    if rolle in ("admin", "innendienst"):
        return True
    if rolle == "montage":
        return False
    hat = getattr(benutzer, "hat_rolle", None)

    def hat_rolle(name: str) -> bool:
        return rolle == name or bool(hat and hat(name))

    if rolle == "aussendienst":
        from app import vorgaenge as vorgaenge_modul
        if vorgaenge_modul.gehoert_benutzer(session, vorgang, benutzer.id):
            return True
    if hat_rolle("projektierung"):
        from app import projektierung as kern
        if kern.modul_sichtbar(session, benutzer) and _hat_projekt(session, vorgang.id):
            return True
    if hat_rolle("leadmanagement"):
        from app import leadmanagement
        if leadmanagement.lead_modul_sichtbar(session, benutzer):
            return True
    return False


def eintrag_dict(notiz: VorgangsNotiz, mein_id=None) -> dict:
    text, klasse = kennzeichen(notiz.herkunft)
    return {"id": notiz.id, "benutzer_name": notiz.benutzer_name, "zeit": notiz.zeit,
            "text": notiz.text, "herkunft": notiz.herkunft or "",
            "kennzeichen": text, "kennzeichen_klasse": klasse,
            "eigen": mein_id is not None and notiz.benutzer_id == mein_id}


def eintrag_json(notiz: VorgangsNotiz) -> dict:
    """JSON-Form eines Eintrags für die Schreibroute (Accept: application/json):
    {"id", "benutzer_name", "zeit": "TT.MM.JJ HH:MM", "text", "kennzeichen",
    "kennzeichen_klasse"} – das Makro hängt den Eintrag damit ohne Neuladen an."""
    text, klasse = kennzeichen(notiz.herkunft)
    return {"id": notiz.id, "benutzer_name": notiz.benutzer_name,
            "zeit": notiz.zeit.strftime("%d.%m.%y %H:%M") if notiz.zeit else "",
            "text": notiz.text, "kennzeichen": text, "kennzeichen_klasse": klasse}


def kontext(session: Session, vorgang_id: int, benutzer, *, limit: int | None = None,
            post_url: str | None = None, hinweis: str = "",
            vorgang: Vorgang | None = None, nur_lesen: bool = False,
            herkunft: str = "", zurueck: str = "") -> dict:
    """Daten für das Makro notizen_chat. `limit` = das Makro zeigt die letzten n
    Einträge direkt, ältere eingeklappt („alle anzeigen“); `nur_lesen` erzwingt
    die Leseansicht (Montage-Backend) unabhängig von den Rechten; `herkunft`
    (projektierung | vertrieb | lead | montage) setzt das Kennzeichen neuer
    Einträge fest (z. B. Kundenkartei → lead), sonst folgt es der Rolle;
    `zurueck` = Ziel des Redirects ohne JavaScript (Standard: Vorgangsakte)."""
    if vorgang is None:
        vorgang = session.get(Vorgang, vorgang_id)
    notizen = eintraege(session, vorgang_id)
    mein_id = getattr(benutzer, "id", None)
    liste = [eintrag_dict(n, mein_id) for n in notizen]
    erlaubt = (not nur_lesen) and schreiben_erlaubt(session, vorgang, benutzer)
    return {"vorgang_id": vorgang_id,
            "post_url": post_url or f"/vorgaenge/{vorgang_id}/notiz",
            "eintraege": liste, "schreiben_erlaubt": erlaubt,
            "hinweis": hinweis if not erlaubt else "",
            "mein_name": getattr(benutzer, "name", ""),
            "anzahl": len(notizen),
            "limit": int(limit) if limit and len(notizen) > int(limit) else 0,
            "herkunft": herkunft if herkunft in HERKUNFT_WERTE else "",
            "zurueck": zurueck or ""}


def kontext_projekt(session: Session, projekt, benutzer) -> dict | None:
    """Projektakte (Reiter Verlauf): Chat des zugehörigen Vorgangs; None bei
    Projekten ohne Vorgang (Altbestand) – dann bleibt der bisherige Weg."""
    vorgang_id = getattr(projekt, "vorgang_id", None)
    if not vorgang_id:
        return None
    return kontext(session, vorgang_id, benutzer,
                   post_url=f"/projektierung/projekt/{projekt.id}/kommentar")


def notiz_anlegen(session: Session, vorgang_id: int, benutzer, text: str,
                  herkunft: str = "") -> VorgangsNotiz:
    """Unveränderlicher Eintrag (wie app.vorgaenge.notiz_anlegen, mit Herkunft)."""
    eintrag = VorgangsNotiz(vorgang_id=vorgang_id,
                            benutzer_id=getattr(benutzer, "id", None),
                            benutzer_name=getattr(benutzer, "name", "") or "System",
                            zeit=datetime.now(), text=(text or "").strip()[:MAX_TEXT],
                            herkunft=(herkunft or "")[:100])
    session.add(eintrag)
    session.flush()
    return eintrag


def kommentar_speichern_eintrag(session: Session, projekt, benutzer,
                                text: str) -> tuple[bool, str, VorgangsNotiz | None]:
    """Kommentar der Projektakte → VorgangsNotiz (herkunft = projektierung).
    Rückgabe (ok, meldung, eintrag); bei Projekten ohne Vorgang (False, Hinweis,
    None) – der Aufrufer nimmt dann den alten Weg (ProjektVerlauf art=kommentar)."""
    text = (text or "").strip()
    if not text:
        return False, "Bitte einen Text eingeben.", None
    vorgang_id = getattr(projekt, "vorgang_id", None)
    if not vorgang_id:
        return False, "Kein Vorgang – Kommentar nur im Projektverlauf", None
    eintrag = notiz_anlegen(session, vorgang_id, benutzer, text, herkunft="projektierung")
    return True, "Notiz gespeichert.", eintrag


def kommentar_speichern(session: Session, projekt, benutzer, text: str) -> tuple[bool, str]:
    ok, meldung, _ = kommentar_speichern_eintrag(session, projekt, benutzer, text)
    return ok, meldung


def migration_v28_notizen(session: Session) -> list[str]:
    """Bestehende ProjektVerlauf-Einträge mit art = kommentar in VorgangsNotiz
    kopieren (herkunft = „projektierung (migriert)“, Zeit/Autor übernommen);
    das Original bleibt. Idempotent über den Dublettenschlüssel
    (vorgang_id, zeit, text) – zweiter Lauf: 0 Kopien, keine Meldung.
    Projekte ohne Vorgang (Altbestand) werden übersprungen (gezählt)."""
    kommentare = (session.query(ProjektVerlauf)
                  .filter(ProjektVerlauf.art == "kommentar")
                  .order_by(ProjektVerlauf.id).all())
    if not kommentare:
        return []
    projekte = {p.id: p for p in session.query(Projekt)
                .filter(Projekt.id.in_({k.projekt_id for k in kommentare}))}
    vorgang_ids = {p.vorgang_id for p in projekte.values() if p.vorgang_id}
    vorhanden: set[tuple] = set()
    if vorgang_ids:
        for n in (session.query(VorgangsNotiz)
                  .filter(VorgangsNotiz.vorgang_id.in_(vorgang_ids))):
            vorhanden.add((n.vorgang_id, n.zeit, (n.text or "").strip()))
    namen = {b.id: b.name for b in session.query(Benutzer)}
    kopiert = 0
    ohne_vorgang = 0
    for k in kommentare:
        projekt = projekte.get(k.projekt_id)
        if projekt is None or not projekt.vorgang_id:
            ohne_vorgang += 1
            continue
        text = (k.text or "").strip()[:MAX_TEXT]
        if not text:
            continue
        schluessel = (projekt.vorgang_id, k.erstellt_am, text)
        if schluessel in vorhanden:
            continue
        session.add(VorgangsNotiz(
            vorgang_id=projekt.vorgang_id, benutzer_id=k.benutzer_id,
            benutzer_name=namen.get(k.benutzer_id, "") or "System",
            zeit=k.erstellt_am, text=text, herkunft=MIGRIERT_HERKUNFT))
        vorhanden.add(schluessel)
        kopiert += 1
    if not kopiert:
        return []
    session.flush()
    meldung = (f"Notizen (v28): {kopiert} Projektakten-Kommentar(e) in den "
               f"Vorgangs-Notizen-Chat kopiert (Original bleibt im Verlauf)")
    if ohne_vorgang:
        meldung += f" – {ohne_vorgang} Kommentar(e) ohne Vorgang übersprungen"
    return [meldung]
