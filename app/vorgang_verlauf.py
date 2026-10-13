# v31 (PLAN_LEAD_V5 Phase 153/158): gemeinsamer Verlauf je Vorgang über alle Module
# und die Objekt-Gruppierung der Vorgangsakte.
#
# Vertrag (Agent AT schreibt, K/B nutzen):
#   eintraege(session, vorgang_id, quellen=("lead", "angebot", "projekt"), limit=None)
#       -> list[dict] mit zeit (datetime), quelle (lead|angebot|projekt), art (notiz|anruf|
#          mail|termin|status|kommentar|verlauf|aenderung|system|…), text, autor, link
#          (optional) – zusätzlich id, titel, autor_id, herkunft, eigen_text; chronologisch
#          (älteste zuerst), `limit` = nur die letzten n.
#       Quellen: VorgangsNotiz (notizen.eintraege – EINE Notizspur seit v28, Zuordnung
#       über die Herkunft), LeadAktivitaet (Anrufe, Mails, Termine, Statuswechsel – Texte
#       wie die Lead-Timeline), KommunikationLog (Lead-Mails der Warteschlange) und der
#       Projekt-Verlauf (ProjektVerlauf art=system/kommentar; migrierte Kommentare sind
#       bereits Notizen und werden nicht doppelt gezeigt).
#   projekt_block(session, vorgang_id) -> dict | None (Projektphase je Gewerk,
#       Montagetermin, offene Projekt-To-Dos) für die Kartei (Block „Projekt“) und die Akte.
#   objekt_gruppen(session, vorgang) -> list[dict] (Objekt, Erfassungen, Angebote, Termine)
#       für die Vorgangsakte und das Deals-Board (B).
# Keine zweite Notizspur, keine Kopien – reine Lesefunktionen.
from datetime import datetime

from sqlalchemy.orm import Session

from app import notizen
from app.models import (Angebot, Aufgabe, Benutzer, Erfassung, Gewerk, KommunikationLog,
                        LeadAktivitaet, Projekt, ProjektVerlauf, VorgangObjekt, VotTermin,
                        Vorgang, VorgangsNotiz, ANRUF_ERGEBNIS_NAMEN, GEWERK_PHASEN_NAMEN)

QUELLEN = ("lead", "angebot", "projekt")
QUELLEN_NAMEN = {"lead": "Lead", "angebot": "Angebot", "projekt": "Projekt"}
# Aktivitätstyp des Lead-Moduls → Art im gemeinsamen Verlauf und Titel (wie lead_kartei.timeline)
_AKTIVITAET_ART = {"anruf": "anruf", "notiz": "notiz", "mail_aus": "mail", "mail_ein": "mail",
                   "mail": "mail", "whatsapp": "mail", "sms": "mail", "termin": "termin",
                   "status": "status", "system": "system", "import": "system",
                   "aenderung": "aenderung"}
_AKTIVITAET_TITEL = {"anruf": "Anruf", "notiz": "Notiz", "mail_aus": "E-Mail gesendet",
                     "mail_ein": "E-Mail eingegangen", "mail": "E-Mail", "termin": "Termin",
                     "status": "Status", "system": "System", "import": "Import",
                     "whatsapp": "WhatsApp", "sms": "SMS", "aenderung": "Änderung"}
ART_NAMEN = {"notiz": "Notiz", "anruf": "Anruf", "mail": "E-Mail", "termin": "Termin",
             "status": "Status", "kommentar": "Kommentar", "verlauf": "Verlauf",
             "aenderung": "Änderung", "system": "System"}
AUFGABE_OFFEN = ("offen", "in_arbeit", "wartet")


def _benutzer_namen(session: Session) -> dict[int, str]:
    return {b.id: b.name for b in session.query(Benutzer.id, Benutzer.name)}


def quelle_fuer_notiz(herkunft: str | None) -> str:
    """Herkunft einer VorgangsNotiz → Quelle des Verlaufs: Projektierung/Montage →
    projekt, Lead/Anruf → lead, alles andere (Vertrieb, Erfassung, Angebot, Galerie,
    Rabatt-Workflow, leer) → angebot."""
    text, _klasse = notizen.kennzeichen(herkunft)
    if text in ("Projektierung", "Montage"):
        return "projekt"
    if text == "Lead":
        return "lead"
    return "angebot"


def _eintrag(zeit, quelle: str, art: str, text: str, autor: str, link: str | None = None,
             **zusatz) -> dict:
    e = {"zeit": zeit, "quelle": quelle, "quelle_text": QUELLEN_NAMEN.get(quelle, quelle),
         "art": art, "art_text": ART_NAMEN.get(art, art.capitalize()),
         "text": text or "", "autor": autor or "System", "link": link}
    e.update(zusatz)
    return e


def _notiz_eintraege(session: Session, vorgang_id: int, quellen) -> list[dict]:
    ergebnis = []
    for n in notizen.eintraege(session, vorgang_id):
        quelle = quelle_fuer_notiz(n.herkunft)
        if quelle not in quellen:
            continue
        kennzeichen, klasse = notizen.kennzeichen(n.herkunft)
        ergebnis.append(_eintrag(
            n.zeit, quelle, "notiz", n.text, n.benutzer_name or "System",
            f"/vorgaenge/{vorgang_id}#notizen",
            id=f"n{n.id}", titel="Notiz", autor_id=n.benutzer_id,
            herkunft=n.herkunft or "", kennzeichen=kennzeichen, kennzeichen_klasse=klasse,
            notiz_id=n.id))
    return ergebnis


def _lead_eintraege(session: Session, vorgang_id: int, namen: dict[int, str]) -> list[dict]:
    """Lead-Aktivitäten (Anrufe, Mails, Termine, Statuswechsel …) mit den Titeln der
    Lead-Timeline sowie die Lead-Mails der Warteschlange (KommunikationLog)."""
    ergebnis = []
    link = f"/lead-management/lead/{vorgang_id}"
    for a in (session.query(LeadAktivitaet)
              .filter(LeadAktivitaet.vorgang_id == vorgang_id)
              .order_by(LeadAktivitaet.zeitpunkt, LeadAktivitaet.id)):
        typ = a.typ or "system"
        art = _AKTIVITAET_ART.get(typ, "system")
        titel = _AKTIVITAET_TITEL.get(typ, typ.capitalize())
        if typ == "anruf" and a.ergebnis:
            titel = "Anruf: " + ANRUF_ERGEBNIS_NAMEN.get(a.ergebnis, a.ergebnis)
        elif typ == "aenderung":
            kurz = (a.text or "").split(":")[0].strip()
            if kurz and len(kurz) <= 60:
                titel = f"Änderung: {kurz}"
        elif typ in ("status", "termin", "system", "import"):
            kurz = (a.text or "").split(":")[0].strip()
            if kurz and len(kurz) <= 60:
                titel = kurz
        ergebnis.append(_eintrag(
            a.zeitpunkt, "lead", art, a.text or "", namen.get(a.benutzer_id, "System"), link,
            id=f"a{a.id}", titel=titel, autor_id=a.benutzer_id, ergebnis=a.ergebnis,
            dauer_sek=a.dauer_sek, typ=typ))
    for k in (session.query(KommunikationLog)
              .filter(KommunikationLog.vorgang_id == vorgang_id)
              .order_by(KommunikationLog.id)):
        zeit = k.gesendet_am or k.geplant_am
        titel = f"E-Mail {k.vorlage_key or k.kanal} · {k.status}"
        text = (k.betreff or "") + (f"\n{k.fehler_text}" if k.fehler_text else "")
        ergebnis.append(_eintrag(
            zeit, "lead", "mail", text, namen.get(k.erstellt_von, "Automatik"), link,
            id=f"k{k.id}", titel=titel, autor_id=k.erstellt_von, ergebnis=k.status,
            typ="mail"))
    return ergebnis


def _projekt_eintraege(session: Session, vorgang_id: int, namen: dict[int, str],
                       notiz_schluessel: set[tuple]) -> list[dict]:
    """Projekt-Verlauf (system) und Projektakten-Kommentare, die NICHT bereits als
    Notiz im Chat stehen (migrierte Kommentare tragen denselben Zeitpunkt + Text)."""
    ergebnis = []
    projekte = (session.query(Projekt).filter(Projekt.vorgang_id == vorgang_id)
                .order_by(Projekt.id).all())
    if not projekte:
        return ergebnis
    sparten = {g.id: g.sparte for g in session.query(Gewerk)
               .filter(Gewerk.projekt_id.in_([p.id for p in projekte]))}
    for projekt in projekte:
        link = f"/projektierung/projekt/{projekt.id}"
        for v in (session.query(ProjektVerlauf)
                  .filter(ProjektVerlauf.projekt_id == projekt.id)
                  .order_by(ProjektVerlauf.erstellt_am, ProjektVerlauf.id)):
            text = (v.text or "").strip()
            if not text:
                continue
            if v.art == "kommentar":
                if (v.erstellt_am, text) in notiz_schluessel:
                    continue   # seit v28 als Notiz im Chat (Migration) – keine Dublette
                art = "kommentar"
            else:
                art = "verlauf"
            titel = f"{projekt.nummer}"
            if v.gewerk_id and v.gewerk_id in sparten:
                titel += f" · {sparten[v.gewerk_id]}"
            ergebnis.append(_eintrag(
                v.erstellt_am, "projekt", art, text, namen.get(v.benutzer_id, "System"),
                link, id=f"p{v.id}", titel=titel, autor_id=v.benutzer_id,
                projekt_id=projekt.id, gewerk_id=v.gewerk_id, aufgabe_id=v.aufgabe_id))
    return ergebnis


def eintraege(session: Session, vorgang_id: int, quellen=QUELLEN,
              limit: int | None = None) -> list[dict]:
    """Gemeinsamer Verlauf des Vorgangs – chronologisch (älteste zuerst)."""
    quellen = tuple(q for q in (quellen or QUELLEN) if q in QUELLEN) or QUELLEN
    namen = _benutzer_namen(session)
    alle = _notiz_eintraege(session, int(vorgang_id), quellen)
    if "lead" in quellen:
        alle += _lead_eintraege(session, int(vorgang_id), namen)
    if "projekt" in quellen:
        schluessel = {(e["zeit"], (e["text"] or "").strip()) for e in alle if e["art"] == "notiz"}
        if not schluessel:
            schluessel = {(n.zeit, (n.text or "").strip()) for n in
                          session.query(VorgangsNotiz).filter(VorgangsNotiz.vorgang_id == int(vorgang_id))}
        alle += _projekt_eintraege(session, int(vorgang_id), namen, schluessel)
    alle.sort(key=lambda e: (e["zeit"] or datetime.min, e.get("id") or ""))
    if limit:
        alle = alle[-int(limit):]
    return alle


def aktivitaeten_ohne_notizen(session: Session, vorgang_id: int, quellen=QUELLEN) -> list[dict]:
    """Nur die Einträge, die KEINE Notizen sind (Vorgangsakte: eingeblendete Lead-/
    Projekt-Aktivitäten neben dem Notizen-Chat – die Notizen zeigt das Makro selbst)."""
    return [e for e in eintraege(session, vorgang_id, quellen) if e["art"] != "notiz"]


# --- Block „Projekt“ ------------------------------------------------------------------

def projekt_block(session: Session, vorgang_id: int) -> dict | None:
    """Projektphase je Gewerk, Montagetermin und offene Projekt-To-Dos (Aufgaben) des
    jüngsten Projekts zum Vorgang; None ohne Projekt."""
    from app import projektierung as kern
    projekte = (session.query(Projekt).filter(Projekt.vorgang_id == int(vorgang_id))
                .order_by(Projekt.id.desc()).all())
    if not projekte:
        return None
    projekt = projekte[0]
    gewerke = (session.query(Gewerk).filter(Gewerk.projekt_id == projekt.id)
               .order_by(Gewerk.id).all())
    status_map = kern.terminstatus_map(session, [g.id for g in gewerke]) if gewerke else {}
    namen = _benutzer_namen(session)
    gewerk_zeilen = []
    naechster = None
    for g in gewerke:
        ts = status_map.get(g.id) or {"status": "unterminiert", "termin": None}
        termin = ts.get("termin")
        termin_text = ""
        if termin is not None and termin.beginn:
            termin_text = termin.beginn.strftime("%d.%m.%Y")
            if termin.ende and termin.ende.date() != termin.beginn.date():
                termin_text += " – " + termin.ende.strftime("%d.%m.%Y")
            if not termin.kunde_bestaetigt:
                termin_text += " (unbestätigt)"
            if g.phase != "storniert" and (naechster is None or termin.beginn < naechster["beginn"]):
                naechster = {"beginn": termin.beginn, "text": termin_text, "sparte": g.sparte}
        gewerk_zeilen.append({"gewerk": g, "gewerk_id": g.id, "sparte": g.sparte, "phase": g.phase,
                              "phase_name": GEWERK_PHASEN_NAMEN.get(g.phase, g.phase),
                              "terminstatus": ts.get("status"), "montagetermin": termin,
                              "montagetermin_text": termin_text})
    todos = []
    for a in (session.query(Aufgabe)
              .filter(Aufgabe.projekt_id == projekt.id, Aufgabe.status.in_(AUFGABE_OFFEN))
              .order_by(Aufgabe.faellig_am.is_(None), Aufgabe.faellig_am, Aufgabe.id)):
        todos.append({"id": a.id, "titel": a.titel, "status": a.status, "pflicht": bool(a.pflicht),
                      "faellig_am": a.faellig_am, "gewerk_id": a.gewerk_id,
                      "verantwortlich": namen.get(a.verantwortlich_id, ""),
                      "ueberfaellig": bool(a.faellig_am and a.faellig_am < datetime.now())})
    phase_text = " · ".join(f"{z['sparte']}: {z['phase_name']}" for z in gewerk_zeilen) or "–"
    return {"projekt": projekt, "projekt_id": projekt.id, "nummer": projekt.nummer,
            "link": f"/projektierung/projekt/{projekt.id}", "status": projekt.status_cache,
            "status_name": GEWERK_PHASEN_NAMEN.get(projekt.status_cache, projekt.status_cache),
            "gewerke": gewerk_zeilen, "phase_text": phase_text,
            "montagetermin": naechster["beginn"] if naechster else None,
            "montagetermin_text": naechster["text"] if naechster else "noch nicht terminiert",
            "todos": todos, "todos_offen": len(todos), "weitere_projekte": len(projekte) - 1}


# --- Objekt-Gruppierung (Phase 153) -----------------------------------------------------

def objekt_gruppen(session: Session, vorgang: Vorgang | int) -> list[dict]:
    """Erfassungen, Angebote und Vor-Ort-Termine je Objekt des Vorgangs. Zeilen ohne
    objekt_id gehören zum Hauptobjekt; deaktivierte Objekte erscheinen nur, wenn noch
    etwas an ihnen hängt. Bei genau einem Objekt liefert die Liste einen Eintrag –
    Aufrufer zeigen dann keine Gruppenüberschrift (`mehrere` = False)."""
    from app import objekte as objekte_modul
    vorgang_id = vorgang.id if isinstance(vorgang, Vorgang) else int(vorgang)
    alle = objekte_modul.objekte_fuer(session, vorgang_id, nur_aktive=False)
    aktive = [o for o in alle if o.aktiv]
    haupt = next((o for o in alle if o.reihenfolge == 1), None) or (alle[0] if alle else None)
    gruppen: dict[int | None, dict] = {}

    def gruppe_fuer(objekt: VorgangObjekt | None) -> dict:
        schluessel = objekt.id if objekt is not None else None
        if schluessel not in gruppen:
            gruppen[schluessel] = {
                "objekt": objekt, "objekt_id": schluessel,
                "bezeichnung": (objekt.bezeichnung if objekt is not None else "") or "Objekt 1",
                "adresse": objekte_modul.objekt_text(objekt, mit_bezeichnung=False) if objekt else "",
                "haupt": objekt is not None and objekt.id == (haupt.id if haupt else None),
                "aktiv": bool(objekt.aktiv) if objekt is not None else True,
                "interessen": objekte_modul.interessen_liste(objekt) if objekt else [],
                "erfassungen": [], "angebote": [], "termine": []}
        return gruppen[schluessel]

    for o in aktive:
        gruppe_fuer(o)
    je_id = {o.id: o for o in alle}

    def ziel(objekt_id) -> dict:
        if objekt_id and objekt_id in je_id:
            return gruppe_fuer(je_id[objekt_id])
        return gruppe_fuer(haupt)

    for e in (session.query(Erfassung).filter(Erfassung.vorgang_id == vorgang_id)
              .order_by(Erfassung.id)):
        ziel(e.objekt_id)["erfassungen"].append(e)
    for a in (session.query(Angebot).filter(Angebot.vorgang_id == vorgang_id)
              .order_by(Angebot.nummer)):
        ziel(a.objekt_id)["angebote"].append(a)
    for t in (session.query(VotTermin).filter(VotTermin.vorgang_id == vorgang_id)
              .order_by(VotTermin.beginn)):
        ziel(t.objekt_id)["termine"].append(t)
    ergebnis = sorted(gruppen.values(),
                      key=lambda g: (0 if g["haupt"] else 1,
                                     g["objekt"].reihenfolge if g["objekt"] is not None else 0,
                                     g["objekt_id"] or 0))
    mehrere = len(ergebnis) > 1
    for g in ergebnis:
        g["mehrere"] = mehrere
        g["ueberschrift"] = (f"{g['bezeichnung']}: {g['adresse']}" if g["adresse"]
                             else g["bezeichnung"])
    return ergebnis
