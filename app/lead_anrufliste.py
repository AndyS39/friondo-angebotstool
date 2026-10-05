# Anrufliste als Arbeitsliste (v21, PLAN_LEAD_V1.1 Phase 89; v25 umgebaut,
# PLAN_LEAD_V3 Phase 118): Schnellfilter-Chips mit Zählern, EINE durchgehend
# sortierte Liste ohne Gruppen – Reihenfolge SLA rot → SLA gelb → fällige
# Wiedervorlagen und Rückrufe (nach Uhrzeit) → Zurückgestellte mit erreichtem
# Datum → Rest nach Eingangsdatum (älteste zuerst); keine Score-Komponente.
# Filter „Vertriebskanal“ (Mehrfachauswahl, Farben aus Parameter kanal_farben)
# ersetzt die Quelle-/Einzelquelle-Selects; die URL-Parameter quelle_id /
# quelle_typ / kampagne_id der Übersichts-Links wirken weiter (ohne Select),
# gruppe= wird toleriert und ignoriert. Zweizeilige Zeile mit Versuchs-Punkten
# und Kontaktstatus-Satz; derselbe Satz steht im Lead-Kopf der Vorgangsakte
# (kopf_kontext). Route, Ergebnis-Buttons, Panel und Tasten 1–7 liegen in
# app/routers/leadmanagement.py.

import json
from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from app import leadmanagement as kern
from app.models import (Benutzer, Kampagne, Kunde, LeadAktivitaet, LeadQualifizierung,
                        LeadQuelle, Vorgang, VotTermin, ANRUF_ERGEBNIS_NAMEN,
                        LEAD_PHASEN, LEAD_PHASEN_NAMEN)

WOCHENTAGE = ["Mo", "Di", "Mi", "Do", "Fr", "Sa", "So"]
OFFENE_PHASEN = ("neu", "in_kontaktierung", "zurueckgestellt", "nicht_erreicht",
                 "qualifiziert")
# v25 (Phase 118): Sortier-Ränge der einen Liste (statt der v21-Gruppen) –
# Reihenfolge und Kurztext für Tooltip/Legende
RAENGE = [
    (0, "SLA rot", "noch kein Versuch, Erstkontakt überfällig"),
    (1, "SLA gelb", "noch kein Versuch, Erstkontakt wird knapp"),
    (2, "fällig", "Wiedervorlage oder Rückruf erreicht – nach Uhrzeit"),
    (3, "zurückgestellt", "Zurückgestellt, Datum erreicht"),
    (4, "", "übrige offene Leads nach Eingang, älteste zuerst"),
]
CHIPS = [("arbeitsliste", "Arbeitsliste"), ("heute", "Heute eingegangen"),
         ("sla_rot", "SLA rot"), ("drei", "≥ 3 Versuche"),
         ("rueckruf", "Rückruf heute"), ("frei", "Ohne Leadmanager")]
# Kanal-Wert für Kunden ohne Vertriebskanal (Filter „Vertriebskanal“)
KANAL_STANDARD = "Standard"


def _liste_aus_query(q, name: str) -> list[str]:
    """Mehrfach-Parameter (?kanal=A&kanal=B) – auch als Dict mit Liste oder
    kommagetrennt („A,B“); leer = kein Filter. Werte klein für den Vergleich."""
    if hasattr(q, "getlist"):
        roh = q.getlist(name)
    else:
        roh = q.get(name, "")
        roh = roh if isinstance(roh, (list, tuple)) else [roh]
    werte: list[str] = []
    for eintrag in roh:
        for teil in str(eintrag or "").split(","):
            teil = teil.strip().lower()
            if teil and teil not in werte:
                werte.append(teil)
    return werte


def filter_aus_query(q) -> dict:
    """Alle URL-Parameter der Anrufliste (auch die Links der Übersicht).
    v25: `kanal` (Mehrfach), `gruppe`/`klasse` werden nur noch toleriert."""
    def _int(name):
        wert = q.get(name, "")
        return int(wert) if str(wert).lstrip("-").isdigit() else None
    return {
        "meine": q.get("meine", "1") == "1",
        "quelle_id": q.get("quelle_id", ""), "kampagne_id": q.get("kampagne_id", ""),
        "quelle_typ": q.get("quelle_typ", ""),
        "sparte": q.get("sparte", ""), "klasse": q.get("klasse", ""),
        "kanal": _liste_aus_query(q, "kanal"),
        "plz": q.get("plz", ""), "phase": q.get("phase", ""), "q": q.get("q", ""),
        "eingang_von": q.get("eingang_von", ""), "eingang_bis": q.get("eingang_bis", ""),
        "sla": q.get("sla", ""), "versuche": _int("versuche"),
        "versuche_min": _int("versuche_min"), "rueckruf": q.get("rueckruf", ""),
        "frei": q.get("frei", "") == "1", "gruppe": q.get("gruppe", ""),
    }


def phasen_labels(logik) -> dict:
    """Phase → Anzeige-Label aus dem Blatt Status (v25: in_kontaktierung und
    qualifiziert tragen beide „Kontaktiert“), Fallback LEAD_PHASEN_NAMEN."""
    labels = {}
    for phase in LEAD_PHASEN:
        zeile = logik.status_zeile(phase) if logik is not None else None
        labels[phase] = (zeile.label if zeile is not None and zeile.label
                         else LEAD_PHASEN_NAMEN.get(phase, phase))
    return labels


def phasen_optionen(logik) -> list[tuple[str, str]]:
    """Optionen des Phase-Selects: Phasen mit demselben Label werden zu EINER
    Option zusammengefasst (Wert = kommagetrennte Phasen, z. B.
    „in_kontaktierung,qualifiziert“ → „Kontaktiert“)."""
    labels = phasen_labels(logik)
    optionen: list[tuple[list[str], str]] = []
    for phase in LEAD_PHASEN:
        label = labels[phase]
        for eintrag in optionen:
            if eintrag[1] == label:
                eintrag[0].append(phase)
                break
        else:
            optionen.append(([phase], label))
    return [(",".join(phasen), label) for phasen, label in optionen]


def aktiver_chip(f: dict) -> str:
    if f.get("eingang_von") and f.get("eingang_bis") and f["eingang_von"] == f["eingang_bis"] \
            and f["eingang_von"] == datetime.now().strftime("%Y-%m-%d"):
        return "heute"
    if f.get("sla") == "rot":
        return "sla_rot"
    if f.get("versuche_min") == 3:
        return "drei"
    if f.get("rueckruf") == "heute":
        return "rueckruf"
    if f.get("frei"):
        return "frei"
    return "arbeitsliste"


def _datum(text: str) -> datetime | None:
    try:
        return datetime.strptime(text, "%Y-%m-%d")
    except (TypeError, ValueError):
        return None


def _dauer(delta: timedelta) -> str:
    minuten = max(0, int(delta.total_seconds() // 60))
    if minuten < 60:
        return f"{minuten} Min"
    if minuten < 24 * 60:
        return f"{minuten // 60} Std {minuten % 60:02d} Min"
    tage = minuten // (24 * 60)
    return f"{tage} Tag{'en' if tage != 1 else ''}"


def _zeit(z: datetime, jetzt: datetime) -> str:
    if z.date() == jetzt.date():
        return f"heute {z.strftime('%H:%M')}"
    if z.date() == (jetzt + timedelta(days=1)).date():
        return f"morgen {z.strftime('%H:%M')}"
    return f"{WOCHENTAGE[z.weekday()]} {z.strftime('%d.%m.')} {z.strftime('%H:%M')}"


def stichworte(session: Session, vorgang: Vorgang, logik) -> list[str]:
    """Bis zu zwei Stichworte aus der Qualifizierung (Heizung + Baujahr,
    Zeitrahmen) – über die Fragetexte gefunden, damit das Blatt frei bleibt."""
    antworten: dict = {}
    for qf in (session.query(LeadQualifizierung)
               .filter(LeadQualifizierung.vorgang_id == vorgang.id)):
        try:
            antworten.update(json.loads(qf.antworten or "{}"))
        except ValueError:
            pass
    if not antworten:
        return []
    treffer = {"heizung": "", "baujahr": "", "zeit": ""}
    for frage in logik.fragen:
        wert = antworten.get(frage.key)
        if wert in (None, "", []):
            continue
        text = frage.frage.lower()
        wert = ", ".join(wert) if isinstance(wert, list) else str(wert)
        if not treffer["heizung"] and ("heizung" in text or "energieträger" in text):
            treffer["heizung"] = wert
        elif not treffer["baujahr"] and "baujahr" in text:
            treffer["baujahr"] = wert
        elif not treffer["zeit"] and ("zeitrahmen" in text or "wann" in text
                                      or "zeitpunkt" in text):
            treffer["zeit"] = wert
    worte = []
    if treffer["heizung"]:
        worte.append(treffer["heizung"] + (f" {treffer['baujahr']}" if treffer["baujahr"] else ""))
    if treffer["zeit"]:
        worte.append(f"Zeitrahmen {treffer['zeit']}")
    return worte[:2]


def kontaktstatus(session: Session, vorgang: Vorgang, anrufe: list[LeadAktivitaet],
                  status_aktivitaeten: list[LeadAktivitaet], sla: dict,
                  jetzt: datetime, logik, wunschzeiten: str = "",
                  stichwoerter: list[str] | None = None) -> list[tuple[str, str]]:
    """Zeile 2 – Kontaktstatus in einem Satz: Liste (Text, Klasse)."""
    teile: list[tuple[str, str]] = []
    n = vorgang.versuch_nr or 0
    letzter = anrufe[-1] if anrufe else None
    if vorgang.lead_phase == "zurueckgestellt":
        seit = next((a.zeitpunkt for a in reversed(status_aktivitaeten)
                     if "urückgestellt" in (a.text or "")), None)
        grund = vorgang.zurueckgestellt_grund or ""
        faellig = (vorgang.zurueckgestellt_bis is not None
                   and vorgang.zurueckgestellt_bis <= jetzt)
        teile.append((f"zurückgestellt{' am ' + seit.strftime('%d.%m.') if seit else ''}"
                      + (f" („{grund}“)" if grund else "")
                      + (" · heute fällig" if faellig else
                         f" · bis {vorgang.zurueckgestellt_bis.strftime('%d.%m.%Y')}"
                         if vorgang.zurueckgestellt_bis else ""),
                      "faellig" if faellig else ""))
        if vorgang.erreicht_am:
            teile.append((f"erreicht am {vorgang.erreicht_am.strftime('%d.%m. %H:%M')}", ""))
    elif letzter is not None and letzter.ergebnis == "rueckruf_gewuenscht" \
            and vorgang.naechste_aktion_am is not None:
        teile.append((f"Rückruf gewünscht: {_zeit(vorgang.naechste_aktion_am, jetzt)}", "rueckruf"))
        if n:
            teile.append((f"{n}× versucht · zuletzt {_zeit(letzter.zeitpunkt, jetzt)} "
                          f"({ANRUF_ERGEBNIS_NAMEN.get(letzter.ergebnis, letzter.ergebnis)})", ""))
    elif n == 0:
        eingang = vorgang.eingang_am or vorgang.angelegt_am
        text = f"Eingang vor {_dauer(jetzt - eingang)} – noch nicht angerufen" if eingang \
            else "noch nicht angerufen"
        if vorgang.eingang_art == "monday":
            text = f"Eingang (Sync) vor {_dauer(jetzt - eingang)}" if eingang else "monday-Lead"
        teile.append((text, "faellig" if sla.get("farbe") == "rot" else ""))
        if wunschzeiten:
            teile.append((f"Wunschzeit: {wunschzeiten}", ""))
        if stichwoerter:
            teile.extend((w, "") for w in stichwoerter)
        elif (vorgang.anfrage_text or "").strip():
            kurz = " ".join((vorgang.anfrage_text or "").split())[:60]
            teile.append((f"„{kurz}{'…' if len(vorgang.anfrage_text or '') > 60 else ''}“", ""))
    else:
        klasse = "rot" if n >= 4 else ("warn" if n >= 3 else "")
        if letzter is not None and letzter.ergebnis == "falsche_nummer":
            teile.append((f"{n}× falsche Nummer · {_zeit(letzter.zeitpunkt, jetzt)}", klasse))
            teile.append(("Nummer aus der Mail prüfen", ""))
        else:
            teile.append((f"{n}× nicht erreicht", klasse))
            if letzter is not None:
                davor = [a for a in anrufe[:-1]][-3:]
                teile.append((f"zuletzt {_zeit(letzter.zeitpunkt, jetzt)} "
                              f"({ANRUF_ERGEBNIS_NAMEN.get(letzter.ergebnis, letzter.ergebnis)})"
                              + (" · davor " + ", ".join(
                                  f"{WOCHENTAGE[a.zeitpunkt.weekday()]} {a.zeitpunkt.strftime('%d.%m.')}"
                                  for a in reversed(davor)) if davor and n >= 4 else ""), ""))
        if vorgang.naechste_aktion_am is not None:
            # v25: die Kaskade setzt keine Wiedervorlage mehr – hier steht eine
            # manuell gesetzte Wiedervorlage (Kartei/Board) oder „Nummer prüfen“ (+1d)
            teile.append((f"Wiedervorlage: {_zeit(vorgang.naechste_aktion_am, jetzt)}",
                          "faellig" if vorgang.naechste_aktion_am <= jetzt else ""))
        letzte_stufe = max((s.versuch_nr for s in logik.kaskade if s.letzter), default=0)
        if letzte_stufe and n + 1 >= letzte_stufe and vorgang.lead_phase != "nicht_erreicht":
            teile.append(("letzter Versuch der Kaskade – danach „Nicht erreicht“ + Nurture-Mail",
                          "faellig"))
    if vorgang.eingang_art == "monday":
        teile.append(("Terminierung in monday – hier nur Verfolgung", "dezent"))
    return teile


def _rang(v: Vorgang, sla: dict, jetzt: datetime) -> tuple[int, tuple]:
    """v25 (Phase 118): Sortier-Rang der einen Liste + Feinsortierung –
    0 SLA rot · 1 SLA gelb (je Eingang, älteste zuerst) · 2 fällige
    Wiedervorlage/Rückruf (nach Uhrzeit) · 3 zurückgestellt mit erreichtem
    Datum (nach Datum) · 4 Rest nach Eingang (älteste zuerst). Kein Score."""
    eingang = (v.eingang_am or v.angelegt_am or jetzt).timestamp()
    if v.lead_phase == "zurueckgestellt":
        return 3, ((v.zurueckgestellt_bis or jetzt).timestamp(), eingang)
    if sla.get("farbe") == "rot":
        return 0, (eingang,)
    if sla.get("farbe") == "gelb":
        return 1, (eingang,)
    if v.naechste_aktion_am is not None and v.naechste_aktion_am <= jetzt:
        return 2, (v.naechste_aktion_am.timestamp(), eingang)
    return 4, (eingang,)


def _kanal_farben(session: Session) -> dict:
    """Parameter kanal_farben wie in den Boards (lead_boards.kanal_farben) –
    lokaler Import, damit die Anrufliste ohne Boards-Modul ladbar bleibt."""
    try:
        from app import lead_boards
        return lead_boards.kanal_farben(session)
    except Exception:
        return {}


def kanal_farbe(farben: dict, kanal: str) -> str:
    """Farbe eines Kanals: Parameter kanal_farben, sonst die Automatik-Palette
    der Boards; „Standard“/leer bleibt ohne Farbe (grauer Badge)."""
    kanal = (kanal or "").strip()
    if not kanal or kanal.lower() == KANAL_STANDARD.lower():
        return ""
    try:
        from app import lead_boards
        return lead_boards.kanal_farbe(farben, kanal)
    except Exception:
        return farben.get(kanal.lower(), "")


def kanal_optionen(session: Session, gewaehlt: list[str], zusaetzlich=()) -> list[dict]:
    """Optionen des Filters „Vertriebskanal“: kern.kanal_werte (Standard + Kanäle
    der Angebotsprofile) plus Kanäle, die an den gelisteten Kunden stehen,
    aber in keinem Profil mehr vorkommen; je Eintrag wert, farbe, aktiv."""
    farben = _kanal_farben(session)
    werte = list(kern.kanal_werte(session))
    for extra in zusaetzlich:
        extra = (extra or "").strip()
        if extra and extra.lower() not in [w.lower() for w in werte]:
            werte.append(extra)
    gewaehlt = [g.lower() for g in (gewaehlt or [])]
    return [{"wert": w, "farbe": kanal_farbe(farben, w), "aktiv": w.lower() in gewaehlt}
            for w in werte]


def daten(session: Session, benutzer, f: dict) -> dict:
    """Eine sortierte Liste (zeilen) + Chip-Zähler. Chips zählen auf der
    Basisliste (nur der Meine/Alle-Schalter wirkt), die Liste ist gefiltert
    und nach _rang sortiert. Liefert zusätzlich kanaele (Filteroptionen)."""
    from app import leadmanagement_logik
    logik = leadmanagement_logik.hole_logik()
    jetzt = datetime.now()
    heute = jetzt.replace(hour=0, minute=0, second=0, microsecond=0)
    morgen = heute + timedelta(days=1)
    phase_filter = f.get("phase") or ""
    phasen = [p.strip() for p in phase_filter.split(",") if p.strip()]
    abfrage = session.query(Vorgang)
    if phasen:
        abfrage = abfrage.filter(Vorgang.lead_phase.in_(phasen))
    else:
        abfrage = abfrage.filter(Vorgang.lead_phase.in_(OFFENE_PHASEN))
    if f.get("meine") and benutzer is not None:
        abfrage = abfrage.filter((Vorgang.leadmanager_id == benutzer.id)
                                 | (Vorgang.leadmanager_id.is_(None)))
    vorgaenge = abfrage.all()
    ids = {v.id for v in vorgaenge} or {0}
    kunden = {k.id: k for k in session.query(Kunde)
              .filter(Kunde.id.in_({v.kunde_id for v in vorgaenge} or {0}))}
    quellen = {q.id: q for q in session.query(LeadQuelle)}
    kampagnen = {k.id: k for k in session.query(Kampagne)}
    mehrfach: dict[int, int] = {}
    for v in session.query(Vorgang.kunde_id):
        mehrfach[v.kunde_id] = mehrfach.get(v.kunde_id, 0) + 1
    anrufe: dict[int, list] = {}
    status_akt: dict[int, list] = {}
    for a in (session.query(LeadAktivitaet)
              .filter(LeadAktivitaet.vorgang_id.in_(ids))
              .order_by(LeadAktivitaet.zeitpunkt)):
        if a.typ == "anruf":
            anrufe.setdefault(a.vorgang_id, []).append(a)
        elif a.typ == "status":
            status_akt.setdefault(a.vorgang_id, []).append(a)
    mit_termin = {t.vorgang_id for t in session.query(VotTermin)
                  .filter(VotTermin.status.in_(("geplant", "bestaetigt")),
                          VotTermin.typ == "vot")}   # v23 (Phase 108): nur Vor-Ort-Termine
    wunsch_namen = {w.key: w.bezeichnung for w in logik.wunschzeiten}
    # v23 Phase 107: Benutzernamen für die Tooltips der Versuchs-Punkte,
    # Höchstzahl der Versuche (Sperre der Kaskaden-Buttons)
    benutzer_namen = _benutzer_namen(session, {a.benutzer_id for liste in anrufe.values()
                                               for a in liste})
    maximal = kern.versuche_max(session)
    farben = _kanal_farben(session)
    rang_texte = {r: text for r, text, _ in RAENGE}

    basis = []
    for v in vorgaenge:
        kunde = kunden.get(v.kunde_id)
        if kunde is None:
            continue
        if not phasen:
            if v.lead_phase == "zurueckgestellt" and (
                    v.zurueckgestellt_bis is None or v.zurueckgestellt_bis > jetzt):
                continue
            if v.lead_phase == "nicht_erreicht" and (
                    v.naechste_aktion_am is None or v.naechste_aktion_am > jetzt):
                continue
            if v.lead_phase == "qualifiziert" and v.id in mit_termin:
                continue
        sla = kern.sla_status(session, v, jetzt)
        if v.eingang_art == "monday" and not v.erstkontakt_am:
            # Plan 1.1: monday-Leads werden in monday terminiert – nur als
            # Eingang zeigen, nie SLA rot/gelb
            sla = {**sla, "farbe": "", "monday": True}
        liste = anrufe.get(v.id, [])
        letzter = liste[-1] if liste else None
        rang, sortierung = _rang(v, sla, jetzt)
        eingang = v.eingang_am or v.angelegt_am
        kanal = (kunde.vertriebskanal or "").strip()
        basis.append({
            "vorgang": v, "kunde": kunde, "sla": sla, "letzter": letzter, "anrufe": liste,
            "rang": rang, "rang_text": rang_texte.get(rang, ""),
            "_sortierung": (rang,) + tuple(sortierung), "eingang": eingang,
            "quelle": quellen.get(v.quelle_id),
            "quelle_gruppe": kern.quelle_gruppe(quellen.get(v.quelle_id)),
            "kampagne": kampagnen.get(v.kampagne_id),
            "kanal": kanal,
            "kanal_farbe": kanal_farbe(farben, kanal),
            "sparten": [s for s in (kunde.interesse or "").split(",") if s.strip()],
            "wiederkehrer": mehrfach.get(v.kunde_id, 0) > 1,
            "monday": v.eingang_art == "monday",
            "frei": v.leadmanager_id is None,
            "nummer_pruefen": letzter is not None and letzter.ergebnis == "falsche_nummer",
            "rueckruf_heute": (letzter is not None and letzter.ergebnis == "rueckruf_gewuenscht"
                               and v.naechste_aktion_am is not None
                               and heute <= v.naechste_aktion_am < morgen),
            # v23 Phase 107: Punkte je Ergebnis, Sperre, Click-to-Call (E.164)
            "versuche": versuche_fuer_punkte(session, liste, benutzer_namen),
            "gesperrt": (v.versuch_nr or 0) >= maximal,
            "tel_href": tel_href(kunde.telefon or ""),
        })

    zaehler = {
        "arbeitsliste": len(basis),
        "heute": sum(1 for z in basis if z["eingang"] and z["eingang"] >= heute),
        "sla_rot": sum(1 for z in basis if z["sla"].get("farbe") == "rot"),
        "drei": sum(1 for z in basis if (z["vorgang"].versuch_nr or 0) >= 3),
        "rueckruf": sum(1 for z in basis if z["rueckruf_heute"]),
        "frei": sum(1 for z in basis if z["frei"]),
    }

    von = _datum(f.get("eingang_von", ""))
    bis = _datum(f.get("eingang_bis", ""))
    suche = (f.get("q") or "").lower()
    zeilen = []
    for z in basis:
        v, kunde = z["vorgang"], z["kunde"]
        if von and (not z["eingang"] or z["eingang"] < von):
            continue
        if bis and (not z["eingang"] or z["eingang"] >= bis + timedelta(days=1)):
            continue
        if f.get("sla") and z["sla"].get("farbe") != f["sla"]:
            continue
        if f.get("versuche") is not None and (v.versuch_nr or 0) != f["versuche"]:
            continue
        if f.get("versuche_min") is not None and (v.versuch_nr or 0) < f["versuche_min"]:
            continue
        if f.get("rueckruf") == "heute" and not z["rueckruf_heute"]:
            continue
        if f.get("frei") and not z["frei"]:
            continue
        # v25: gruppe= (alte Übersichts-Links) wird toleriert und ignoriert –
        # die Liste ist durchgehend sortiert; quelle_typ/quelle_id/kampagne_id
        # der Übersichts-Links filtern weiter (ohne eigenes Select)
        if f.get("quelle_typ") and z["quelle_gruppe"] != f["quelle_typ"]:
            continue
        if f.get("quelle_id") and str(v.quelle_id or "") != str(f["quelle_id"]):
            continue
        if f.get("kampagne_id") not in ("", None) and str(v.kampagne_id or 0) != str(f["kampagne_id"]):
            continue
        if f.get("kanal") and (z["kanal"] or KANAL_STANDARD).lower() not in f["kanal"]:
            continue
        if f.get("sparte") and f["sparte"] not in z["sparten"]:
            continue
        if f.get("klasse") and v.score_klasse != f["klasse"]:
            continue
        if f.get("plz") and not (kunde.plz or "").startswith(f["plz"]):
            continue
        if suche and suche not in " ".join((kunde.vorname or "", kunde.nachname or "",
                                            kunde.telefon or "", kunde.ort or "",
                                            kunde.plz or "")).lower():
            continue
        wunsch = ", ".join(wunsch_namen.get(w, w) for w in kern.wunschzeiten_liste(v))
        z["satz"] = kontaktstatus(session, v, z["anrufe"], status_akt.get(v.id, []), z["sla"],
                                  jetzt, logik, wunsch,
                                  stichworte(session, v, logik) if not (v.versuch_nr or 0) else [])
        z["balken"] = ("sla-rot-zeile" if z["sla"].get("farbe") == "rot"
                       else "sla-gelb-zeile" if z["sla"].get("farbe") == "gelb"
                       else "viel-versuche" if (v.versuch_nr or 0) >= 3 else "")
        zeilen.append(z)

    zeilen.sort(key=lambda z: z["_sortierung"])
    kanaele = kanal_optionen(session, f.get("kanal") or [],
                             zusaetzlich={z["kanal"] for z in basis if z["kanal"]})
    return {"zeilen": zeilen, "zaehler": zaehler, "chip": aktiver_chip(f),
            "offen": len(zeilen), "jetzt": jetzt, "kanaele": kanaele,
            "raenge": RAENGE}


def kopf_kontext(session: Session, vorgang: Vorgang) -> dict:
    """Lead-Kopfblock der Vorgangsakte: Kontaktstatus-Satz, Quellen-Gruppe."""
    from app import leadmanagement_logik
    logik = leadmanagement_logik.hole_logik()
    jetzt = datetime.now()
    akt = (session.query(LeadAktivitaet).filter(LeadAktivitaet.vorgang_id == vorgang.id)
           .order_by(LeadAktivitaet.zeitpunkt).all())
    anrufe = [a for a in akt if a.typ == "anruf"]
    status_akt = [a for a in akt if a.typ == "status"]
    sla = kern.sla_status(session, vorgang, jetzt)
    wunsch_namen = {w.key: w.bezeichnung for w in logik.wunschzeiten}
    wunsch = ", ".join(wunsch_namen.get(w, w) for w in kern.wunschzeiten_liste(vorgang))
    quelle = session.get(LeadQuelle, vorgang.quelle_id) if vorgang.quelle_id else None
    kunde = session.get(Kunde, vorgang.kunde_id)
    return {"kontakt_satz": kontaktstatus(session, vorgang, anrufe, status_akt, sla, jetzt,
                                          logik, wunsch,
                                          stichworte(session, vorgang, logik)),
            "quelle_gruppe": kern.quelle_gruppe(quelle),
            "kanal": (kunde.vertriebskanal if kunde else "") or "",
            "versuche": versuche_fuer_punkte(session, anrufe),
            "gesperrt": versuche_gesperrt(session, vorgang)}


# =====================================================================================
# v23 – Lead-Management V2, Phase 107 (PLAN_LEAD_V2 C1–C4, D1–D3, F2, F9):
# Anruf-Workflow & Telefonie. Alles unterhalb dieser Linie gehört zur Phase 107;
# die Funktionen oben (Gruppen, Kontaktstatus) sind unverändert v21.
# =====================================================================================

# Ergebnisse, die als erfolgloser Versuch durch die Kaskade laufen (C3-a) und
# nach der Höchstzahl (Parameter versuche_max) gesperrt sind (A-5)
KASKADEN_ERGEBNISSE = ("nicht_erreicht", "besetzt", "mailbox")
SPERRE_MELDUNG = "Höchstzahl erreicht – Lead steht auf Nicht erreicht"
# Dedup-Kennzeichen der Fälligkeits-Glocke (Aktivität typ system, C2)
WV_GEMELDET_TEXT = "Wiedervorlage fällig gemeldet"
# Obergrenze für eine plausible Gesprächsdauer (4 h); größere Werte werden gekappt
DAUER_MAX_SEK = 4 * 3600
# Mindestlänge der Ziffernfolge für die Rufnummernsuche (D3/H7)
SUCHE_MIN_ZIFFERN = 7


# --- Sperre / Vorschlag (C1, C2) -----------------------------------------------------

def versuche_gesperrt(session: Session, vorgang: Vorgang) -> bool:
    """Nicht erreicht / Besetzt / Mailbox sind gesperrt, sobald der Lead auf
    „Nicht erreicht“ steht (kern.versuche_gesperrt) oder die Höchstzahl der
    Versuche erreicht ist – auch nach einem Reaktivieren bleibt der Zähler
    stehen (A-5: kein automatischer zweiter Zyklus)."""
    if vorgang is None:
        return False
    return (kern.versuche_gesperrt(session, vorgang)
            or (vorgang.versuch_nr or 0) >= kern.versuche_max(session))


def anruf_vorschlag(session: Session, vorgang: Vorgang,
                    jetzt: datetime | None = None) -> dict:
    """Kaskaden-Auskunft für den NÄCHSTEN erfolglosen Versuch (Stufe
    versuch_nr + 1): Stufe, Mail-Aktion, letzte Stufe, Sperre. v25 (Phase
    120): der „Nicht erreicht“-Dialog ist entfallen, die Kaskade setzt keine
    Wiedervorlage mehr – GET /anruf/{id}/vorschlag bleibt nur als Auskunft
    erreichbar; `zeitpunkt` ist der frühere Vorschlag (Spalte
    wiedervorlage_nach, nicht mehr angewendet)."""
    from app import leadmanagement_logik
    logik = leadmanagement_logik.hole_logik()
    jetzt = jetzt or datetime.now()
    naechste_nr = (vorgang.versuch_nr or 0) + 1
    stufe = logik.stufe(naechste_nr)
    maximal = kern.versuche_max(session)
    gesperrt = versuche_gesperrt(session, vorgang)
    letzte = stufe is None or stufe.letzter or naechste_nr >= maximal
    aktion = (stufe.aktion if stufe is not None else "mail_disqualifiziert") or "keine"
    if gesperrt:
        zeitpunkt = None
    elif letzte:
        # kaskade_anwenden: Phase Nicht erreicht, Wiedervorlage +30 Tage (Nurture)
        zeitpunkt = jetzt + timedelta(days=30)
    else:
        zeitpunkt = kern.kaskade_zeitpunkt(session, stufe.wiedervorlage_nach, jetzt)
    return {"zeitpunkt": zeitpunkt, "stufe": naechste_nr, "stufen": logik.letzte_stufe(),
            "regel": stufe.wiedervorlage_nach if stufe is not None else "+30d",
            "aktion": aktion, "letzte": letzte, "gesperrt": gesperrt,
            "versuche_max": maximal}


def dauer_lesen(roh) -> int | None:
    """Formularwert der Stoppuhr: Sekunden („95“) oder „mm:ss“ → int, gekappt
    auf DAUER_MAX_SEK; leer/ungültig → None (Dauer ist kein Pflichtfeld)."""
    text = str(roh or "").strip()
    if not text:
        return None
    try:
        if ":" in text:
            teile = [int(t) for t in text.split(":")]
            sek = 0
            for t in teile:
                sek = sek * 60 + t
        else:
            sek = int(float(text.replace(",", ".")))
    except ValueError:
        return None
    if sek < 0:
        return None
    return min(sek, DAUER_MAX_SEK)


def dauer_text(sek) -> str:
    """Sekunden → „mm:ss“ (ab einer Stunde „h:mm:ss“); None → „–“."""
    if sek is None:
        return "–"
    sek = max(0, int(sek))
    if sek >= 3600:
        return f"{sek // 3600}:{(sek % 3600) // 60:02d}:{sek % 60:02d}"
    return f"{sek // 60:02d}:{sek % 60:02d}"


def zeitpunkt_lesen(roh) -> datetime | None:
    """datetime-local („2026-10-02T14:30“, auch mit Sekunden) → datetime."""
    text = str(roh or "").strip()
    for muster in ("%Y-%m-%dT%H:%M", "%Y-%m-%dT%H:%M:%S", "%d.%m.%Y %H:%M"):
        try:
            return datetime.strptime(text, muster)
        except ValueError:
            continue
    return None


def zurueck_pfad(roh, standard: str = "/lead-management/anrufliste") -> str:
    """Redirect-Ziel aus dem Formular: nur relative Pfade (Open-Redirect-Schutz)."""
    text = str(roh or "").strip()
    if not text.startswith("/") or text.startswith("//") or "\\" in text \
            or any(c in text for c in "\r\n"):
        return standard
    return text


def mit_meldung(pfad: str, meldung: str) -> str:
    from urllib.parse import quote_plus
    return pfad + ("&" if "?" in pfad else "?") + "meldung=" + quote_plus(meldung)


# --- Versuchs-Punkte (C1-c) ----------------------------------------------------------

def _benutzer_namen(session: Session, ids: set) -> dict:
    ids = {i for i in ids if i}
    if not ids:
        return {}
    return {b.id: b.name for b in session.query(Benutzer).filter(Benutzer.id.in_(ids))}


def versuche_fuer_punkte(session: Session, anrufe: list, benutzer_namen: dict | None = None) -> list:
    """Anruf-Aktivitäten eines Vorgangs → Liste für das Makro versuche_punkte
    (Datum/Uhrzeit, Ergebnis, Benutzer je Punkt)."""
    if not anrufe:
        return []
    if benutzer_namen is None:
        benutzer_namen = _benutzer_namen(session, {a.benutzer_id for a in anrufe})
    punkte = []
    for a in anrufe:
        punkte.append({
            "id": a.id, "zeitpunkt": a.zeitpunkt, "ergebnis": a.ergebnis or "",
            "ergebnis_name": ANRUF_ERGEBNIS_NAMEN.get(a.ergebnis, a.ergebnis or "Anruf"),
            "benutzer_name": benutzer_namen.get(a.benutzer_id, "System" if not a.benutzer_id else "?"),
            "dauer_sek": a.dauer_sek,
            "titel": (f"{WOCHENTAGE[a.zeitpunkt.weekday()]} {a.zeitpunkt.strftime('%d.%m.%Y %H:%M')}"
                      f" · {ANRUF_ERGEBNIS_NAMEN.get(a.ergebnis, a.ergebnis or 'Anruf')}"
                      f" · {benutzer_namen.get(a.benutzer_id, 'System' if not a.benutzer_id else '?')}"
                      + (f" · {dauer_text(a.dauer_sek)}" if a.dauer_sek else "")),
        })
    return punkte


# --- Mail-Regeln (C4, F9) und Doppelversand-Schutz (C4-d) ----------------------------
# Auslöser sind Datenpflege im Blatt Kaskade (Spalte aktion), nicht Code. v25
# (PLAN_LEAD_V3 Phase 120): die Spalte wiedervorlage_nach wird NICHT mehr
# ausgewertet – kein Versuch setzt eine Wiedervorlage, die Mails hängen allein an
# der Versuchsnummer:
#   Stufe 1              keine
#   Stufe 2              mail_nicht_erreicht   → Vorlage nicht_erreicht, sofort geplant
#   Stufe 3              keine
#   Stufe 4              mail_nicht_erreicht   → Vorlage nicht_erreicht, sofort geplant
#   Stufe 5 (letzter)    mail_disqualifiziert → Vorlage disqualifiziert sofort, Phase
#                        Nicht erreicht, Vorlage nurture in 30 Tagen (Versand nur mit
#                        einwilligung_werbung); naechste_aktion_am wird geleert
# Kein Interesse (Unqualifiziert) löst KEINE Kundenmail aus (Bestand); Mailbox/Besetzt
# zählen wie Nicht erreicht. Ab versuche_max sind die drei Ergebnisse gesperrt – die
# Kaskade kann nicht erneut ausgeschöpft werden (vorher: jeder weitere Versuch plante
# erneut Nurture). Terminstatus-Kopplung (Review 27.09.) greift in
# lead_mail.eintrag_verarbeiten nur für terminbestaetigung/terminerinnerung mit
# termin_id; vorgangsbezogene Mails (nicht_erreicht, disqualifiziert, nurture) schützt
# dieser Abschnitt: kein zweiter OFFENER Eintrag gleicher Vorlage je Vorgang.
# Alle Mails laufen über kern.mail_planen → Warteschlange → Sendesperre im Demo.

def mail_bereits_geplant(session: Session, vorgang_id: int, vorlage_key: str) -> bool:
    """Gibt es für den Vorgang schon einen OFFENEN Eintrag (status geplant,
    ohne Termin-Bezug) derselben Vorlage? Vor kern.mail_planen prüfen."""
    from app.models import KommunikationLog
    return (session.query(KommunikationLog)
            .filter(KommunikationLog.vorgang_id == vorgang_id,
                    KommunikationLog.vorlage_key == vorlage_key,
                    KommunikationLog.status == "geplant",
                    KommunikationLog.termin_id.is_(None))
            .count()) > 0


def mail_planen_einmalig(session: Session, vorgang: Vorgang, vorlage_key: str,
                         geplant_am: datetime | None = None):
    """kern.mail_planen mit Doppelversand-Schutz: kein zweiter offener Eintrag
    gleicher Vorlage je Vorgang."""
    if mail_bereits_geplant(session, vorgang.id, vorlage_key):
        return None
    return kern.mail_planen(session, vorgang, vorlage_key, geplant_am=geplant_am)


def doppelversand_bereinigen(session: Session, vorgang_id: int) -> int:
    """Nach kaskade_anwenden: liegen für den Vorgang mehrere OFFENE Einträge
    derselben Vorlage (ohne Termin), bleibt der älteste – die jüngeren werden
    storniert („Doppelversand-Schutz“). Liefert die Anzahl der Stornos."""
    from app.models import KommunikationLog
    offen = (session.query(KommunikationLog)
             .filter(KommunikationLog.vorgang_id == vorgang_id,
                     KommunikationLog.status == "geplant",
                     KommunikationLog.termin_id.is_(None))
             .order_by(KommunikationLog.id).all())
    gesehen: set[str] = set()
    anzahl = 0
    for eintrag in offen:
        if eintrag.vorlage_key in gesehen:
            eintrag.status = "storniert"
            eintrag.fehler_text = "Doppelversand-Schutz: gleiche Vorlage bereits geplant"
            anzahl += 1
        else:
            gesehen.add(eintrag.vorlage_key)
    if anzahl:
        session.flush()
    return anzahl


def nurture_verschieben(session: Session, vorgang: Vorgang, zeitpunkt: datetime) -> int:
    """Nurture-Mail (geplant, ohne Termin) auf einen Zeitpunkt legen. v25: von
    POST /anruf/{id} nicht mehr aufgerufen (kein wiedervorlage_am mehr) –
    bleibt für manuelle Wiedervorlagen (Kartei) nutzbar."""
    from app.models import KommunikationLog
    anzahl = 0
    for eintrag in (session.query(KommunikationLog)
                    .filter(KommunikationLog.vorgang_id == vorgang.id,
                            KommunikationLog.vorlage_key == "nurture",
                            KommunikationLog.status == "geplant",
                            KommunikationLog.termin_id.is_(None))):
        eintrag.geplant_am = zeitpunkt
        anzahl += 1
    return anzahl


# Vorgangsbezogene Kundenmails der Kaskade (ohne Termin-Bezug): ihr Anlass
# entfällt, sobald der Kunde erreicht ist, zurückrufen will oder absagt.
VORGANGS_MAILS = ("nicht_erreicht", "disqualifiziert", "nurture")


def offene_mails_stornieren(session: Session, vorgang_id: int,
                            vorlagen: tuple[str, ...] = VORGANGS_MAILS,
                            grund: str = "Kunde erreicht") -> int:
    """Kopplung der Warteschlange an den Kontaktstatus (C4-d, Gegenstück zur
    Terminstatus-Kopplung vom 27.09.): offene Einträge (status geplant, ohne
    Termin) der Kaskaden-Vorlagen stornieren, wenn der Kunde erreicht wurde,
    einen Rückruf wünscht oder kein Interesse hat – sonst ginge „Wir haben Sie
    leider nicht erreicht“ bzw. die Nurture-Mail nach dem Gespräch raus.
    Liefert die Anzahl der Stornos."""
    from app.models import KommunikationLog
    anzahl = 0
    for eintrag in (session.query(KommunikationLog)
                    .filter(KommunikationLog.vorgang_id == vorgang_id,
                            KommunikationLog.vorlage_key.in_(vorlagen),
                            KommunikationLog.status == "geplant",
                            KommunikationLog.termin_id.is_(None))):
        eintrag.status = "storniert"
        eintrag.fehler_text = f"{grund} – Mail nicht mehr nötig"
        anzahl += 1
    if anzahl:
        session.flush()
    return anzahl


# --- Glocke zum Wiedervorlage-Zeitpunkt (C2) -----------------------------------------

def _leitung_ids(session: Session) -> list[int]:
    return [b.id for b in session.query(Benutzer)
            .filter(Benutzer.aktiv.is_(True),
                    Benutzer.rolle.in_(("admin", "leadmanagement")))]


def faellige_wiedervorlagen_melden(session: Session, jetzt: datetime | None = None) -> int:
    """Glocke, sobald naechste_aktion_am erreicht ist (Rückrufwunsch, manuell
    gesetzte Wiedervorlage, „Nummer prüfen“ +1d; v25: die Kaskade setzt keine
    Wiedervorlage mehr) – einmalig je Fälligkeit: Dedup über eine
    Aktivität typ system „Wiedervorlage fällig gemeldet“ mit demselben
    naechste_aktion_am. Empfänger leadmanager_id, freie Leads → Leitung
    (admin/leadmanagement) wie beim Tagesdigest. Zurückgestellte Leads meldet
    weiter der Tageslauf (zurueckgestellt_bis). Aufruf: 5-Minuten-Scheduler
    (hook_edit) und beim Rendern der Anrufliste. Liefert die Anzahl Meldungen."""
    jetzt = jetzt or datetime.now()
    phasen = tuple(p for p in OFFENE_PHASEN if p != "zurueckgestellt")
    faellig = (session.query(Vorgang)
               .filter(Vorgang.lead_phase.in_(phasen),
                       Vorgang.naechste_aktion_am.isnot(None),
                       Vorgang.naechste_aktion_am <= jetzt).all())
    if not faellig:
        return 0
    ids = {v.id for v in faellig}
    gemeldet: set[tuple[int, datetime]] = set()
    letzte_anrufe: dict[int, LeadAktivitaet] = {}
    for a in (session.query(LeadAktivitaet)
              .filter(LeadAktivitaet.vorgang_id.in_(ids),
                      LeadAktivitaet.typ.in_(("system", "anruf")))
              .order_by(LeadAktivitaet.zeitpunkt)):
        if a.typ == "system" and (a.text or "").startswith(WV_GEMELDET_TEXT) \
                and a.naechste_aktion_am is not None:
            gemeldet.add((a.vorgang_id, a.naechste_aktion_am.replace(microsecond=0)))
        elif a.typ == "anruf":
            letzte_anrufe[a.vorgang_id] = a
    kunden = {k.id: k for k in session.query(Kunde)
              .filter(Kunde.id.in_({v.kunde_id for v in faellig} or {0}))}
    leitung: list[int] | None = None
    anzahl = 0
    for v in faellig:
        schluessel = (v.id, v.naechste_aktion_am.replace(microsecond=0))
        if schluessel in gemeldet:
            continue
        kunde = kunden.get(v.kunde_id)
        letzter = letzte_anrufe.get(v.id)
        if letzter is not None and letzter.ergebnis == "rueckruf_gewuenscht":
            art = "Rückruf gewünscht"
        elif v.lead_phase == "nicht_erreicht":
            art = "Nicht erreicht – Wiedervorlage"
        else:
            art = "Nächster Versuch"
        text = (f"{art} fällig: {kunde.anzeige_name if kunde else '?'}"
                f"{', ' + kunde.ort if kunde and kunde.ort else ''}"
                f" ({v.naechste_aktion_am.strftime('%d.%m. %H:%M')})")
        if v.leadmanager_id:
            empfaenger = [v.leadmanager_id]
        else:
            if leitung is None:
                leitung = _leitung_ids(session)
            empfaenger = leitung
            text += " – ohne Leadmanager"
        if empfaenger:
            kern.benachrichtigen(session, empfaenger, text, f"/lead-management/lead/{v.id}")
        kern.aktivitaet(session, v.id, "system",
                        f"{WV_GEMELDET_TEXT} ({v.naechste_aktion_am.strftime('%d.%m.%Y %H:%M')})"
                        + (f" an {len(empfaenger)} Empfänger" if empfaenger else " – kein Empfänger"),
                        naechste_aktion_am=v.naechste_aktion_am)
        gemeldet.add(schluessel)
        anzahl += 1
    return anzahl


# --- Meine Anrufe (D2) ---------------------------------------------------------------

ZEITRAEUME = [("heute", "Heute"), ("7", "7 Tage"), ("30", "30 Tage"), ("alle", "Alle")]


def zeitraum_grenzen(zeitraum: str, von: str = "", bis: str = "",
                     jetzt: datetime | None = None) -> tuple[datetime | None, datetime | None]:
    """Zeitraum-Filter von „Meine Anrufe“: Kürzel oder explizite Daten."""
    jetzt = jetzt or datetime.now()
    heute = jetzt.replace(hour=0, minute=0, second=0, microsecond=0)
    d_von, d_bis = _datum(von), _datum(bis)
    if d_von or d_bis:
        return d_von, (d_bis + timedelta(days=1)) if d_bis else None
    if zeitraum == "heute":
        return heute, None
    if zeitraum == "alle":
        return None, None
    try:
        tage = int(zeitraum)
    except (TypeError, ValueError):
        tage = 30
    return heute - timedelta(days=max(0, tage - 1)), None


def anrufe_liste(session: Session, benutzer_id: int | None, zeitraum: str = "30",
                 ergebnis: str = "", von: str = "", bis: str = "", q: str = "",
                 nur_ad_id: int | None = None, limit: int = 500) -> list[dict]:
    """Protokollierte Anrufe (lead_aktivitaeten typ anruf) absteigend nach
    Zeitpunkt. benutzer_id = None → alle Benutzer (Team-Sicht);
    nur_ad_id → nur Vorgänge dieses Außendienstlers (Handelsvertreter)."""
    abfrage = session.query(LeadAktivitaet).filter(LeadAktivitaet.typ == "anruf")
    if benutzer_id is not None:
        abfrage = abfrage.filter(LeadAktivitaet.benutzer_id == benutzer_id)
    d_von, d_bis = zeitraum_grenzen(zeitraum, von, bis)
    if d_von:
        abfrage = abfrage.filter(LeadAktivitaet.zeitpunkt >= d_von)
    if d_bis:
        abfrage = abfrage.filter(LeadAktivitaet.zeitpunkt < d_bis)
    if ergebnis:
        abfrage = abfrage.filter(LeadAktivitaet.ergebnis == ergebnis)
    aktivitaeten = abfrage.order_by(LeadAktivitaet.zeitpunkt.desc()).limit(limit * 2).all()
    if not aktivitaeten:
        return []
    vorgaenge = {v.id: v for v in session.query(Vorgang)
                 .filter(Vorgang.id.in_({a.vorgang_id for a in aktivitaeten}))}
    kunden = {k.id: k for k in session.query(Kunde)
              .filter(Kunde.id.in_({v.kunde_id for v in vorgaenge.values()} or {0}))}
    namen = _benutzer_namen(session, {a.benutzer_id for a in aktivitaeten})
    suche = (q or "").strip().lower()
    such_ziffern = _ziffern(suche) if suche else ""
    zeilen = []
    for a in aktivitaeten:
        v = vorgaenge.get(a.vorgang_id)
        if v is None:
            continue
        if nur_ad_id is not None and v.ad_id != nur_ad_id:
            continue
        kunde = kunden.get(v.kunde_id)
        nummer = (kunde.telefon if kunde else "") or ""
        if suche:
            text = " ".join((kunde.vorname or "", kunde.nachname or "", kunde.ort or "",
                             nummer) if kunde else ("",)).lower()
            treffer = suche in text
            if not treffer and len(such_ziffern) >= 3:
                treffer = such_ziffern in _ziffern(nummer)
            if not treffer:
                continue
        notiz = (a.text or "")
        if notiz.startswith("Anruf:"):
            notiz = notiz.split("–", 1)[1].strip() if "–" in notiz else ""
        zeilen.append({
            "aktivitaet": a, "vorgang": v, "kunde": kunde, "nummer": nummer,
            "tel_href": tel_href(nummer), "ergebnis": a.ergebnis or "",
            "ergebnis_name": ANRUF_ERGEBNIS_NAMEN.get(a.ergebnis, a.ergebnis or "Anruf"),
            "dauer": dauer_text(a.dauer_sek), "dauer_sek": a.dauer_sek,
            "benutzer_name": namen.get(a.benutzer_id, ""), "notiz": notiz,
            "sparten": [s for s in ((kunde.interesse if kunde else "") or "").split(",") if s.strip()],
        })
        if len(zeilen) >= limit:
            break
    return zeilen


def anrufe_summen(zeilen: list[dict]) -> dict:
    gesamt = sum(z["dauer_sek"] or 0 for z in zeilen)
    mit_dauer = [z for z in zeilen if z["dauer_sek"]]
    return {"anzahl": len(zeilen), "erreicht": sum(1 for z in zeilen if z["ergebnis"] == "erreicht"),
            "dauer_gesamt": dauer_text(gesamt) if gesamt else "–",
            "dauer_schnitt": dauer_text(gesamt // len(mit_dauer)) if mit_dauer else "–"}


# --- Dauer-Korrektur (D1) ------------------------------------------------------------

def dauer_korrigieren(session: Session, aktivitaet: LeadAktivitaet, neu_sek: int | None,
                      benutzer) -> str:
    """dauer_sek einer eigenen Anruf-Aktivität (oder als Admin) nachträglich
    setzen; die Änderung wird als Aktivität typ system protokolliert – Texte
    bleiben unveränderlich (v10-Grundsatz). Liefert einen Fehlertext oder ""."""
    if aktivitaet is None or aktivitaet.typ != "anruf":
        return "Nur Anruf-Einträge haben eine Dauer."
    if benutzer is None:
        return "Nicht angemeldet."
    if aktivitaet.benutzer_id != benutzer.id and benutzer.rolle != "admin":
        return "Nur der eigene Eintrag oder ein Admin darf die Dauer ändern."
    if neu_sek is None:
        return "Bitte eine Dauer als Sekunden oder mm:ss angeben."
    alt = aktivitaet.dauer_sek
    if alt == neu_sek:
        return ""
    aktivitaet.dauer_sek = neu_sek
    kern.aktivitaet(session, aktivitaet.vorgang_id, "system",
                    f"Anrufdauer korrigiert: {dauer_text(alt)} → {dauer_text(neu_sek)}"
                    f" (Anruf vom {aktivitaet.zeitpunkt.strftime('%d.%m.%Y %H:%M')},"
                    f" Eintrag #{aktivitaet.id})", benutzer=benutzer)
    session.flush()
    return ""


# --- Rufnummernsuche (D3 / H7) -------------------------------------------------------

def _ziffern(nummer: str) -> str:
    """Vergleichsschlüssel: E.164 über kern.telefon_normalisieren, danach nur
    Ziffern; die Klammer-Null nach der Ländervorwahl („+49 (0)203 …“) fällt
    weg. Leer, wenn keine Ziffern."""
    import re
    norm = kern.telefon_normalisieren(nummer or "")
    ziffern = re.sub(r"\D", "", norm)
    if norm.startswith("+") and len(ziffern) > 3:
        # Ländervorwahl 1–3 Stellen; deutsche Nummern beginnen nach 49 nie mit 0
        if ziffern.startswith("490"):
            ziffern = "49" + ziffern[3:]
    return ziffern


def _national_laenge(ziffern: str) -> int:
    """Länge ohne Ländervorwahl – „0203 77“ hat 5 nationale Ziffern, obwohl
    der E.164-Schlüssel 4920377 schon 7 Zeichen lang ist."""
    return len(ziffern) - 2 if ziffern.startswith("49") else len(ziffern)


def tel_href(nummer: str) -> str:
    """href für Click-to-Call (D1): E.164 ohne Leerzeichen/Schrägstriche;
    ohne brauchbare Nummer leer."""
    if not (nummer or "").strip():
        return ""
    z = _ziffern(nummer)
    if _national_laenge(z) < SUCHE_MIN_ZIFFERN:
        return "tel:" + (nummer or "").strip().replace(" ", "")
    return "tel:+" + z


def rufnummer_suchen(session: Session, eingabe: str, nur_ad_id: int | None = None) -> dict:
    """E.164-Suche in kunden.telefon und leads.telefon (monday) mit
    Ziffernfolge-Vergleich (Mindestlänge 7). Liefert {"ziffern", "treffer":
    [{kunde, vorgang, vorgaenge, herkunft}], "zu_kurz"}. Je Kunde eine Zeile mit dem
    jüngsten offenen Vorgang (sonst jüngster überhaupt)."""
    from app.models import Lead
    gesucht = _ziffern(eingabe)
    ergebnis = {"ziffern": gesucht, "treffer": [],
                "zu_kurz": _national_laenge(gesucht) < SUCHE_MIN_ZIFFERN}
    if ergebnis["zu_kurz"]:
        return ergebnis

    def passt(nummer: str) -> bool:
        z = _ziffern(nummer)
        if _national_laenge(z) < SUCHE_MIN_ZIFFERN:
            return False
        if z == gesucht:
            return True
        # Durchwahl/Zusatz: die längere Nummer beginnt mit der kürzeren
        kurz, lang = sorted((z, gesucht), key=len)
        return len(kurz) >= 9 and lang.startswith(kurz)

    kunden_ids: dict[int, str] = {}
    for kunde_id, telefon in (session.query(Kunde.id, Kunde.telefon)
                              .filter(Kunde.telefon != "", Kunde.aktiv.is_(True))):
        if passt(telefon or ""):
            kunden_ids[kunde_id] = "kunde"
    lead_vorgang: dict[int, int] = {}
    for lead in (session.query(Lead).filter(Lead.telefon != "")):
        if passt(lead.telefon or ""):
            if lead.kunde_id:
                kunden_ids.setdefault(lead.kunde_id, "monday")
            v = session.query(Vorgang).filter(Vorgang.lead_id == lead.id).first()
            if v is not None:
                kunden_ids.setdefault(v.kunde_id, "monday")
                lead_vorgang[v.kunde_id] = v.id
    if not kunden_ids:
        return ergebnis
    vorgaenge: dict[int, list] = {}
    for v in (session.query(Vorgang).filter(Vorgang.kunde_id.in_(kunden_ids))
              .order_by(Vorgang.angelegt_am.desc())):
        if nur_ad_id is not None and v.ad_id != nur_ad_id:
            continue
        vorgaenge.setdefault(v.kunde_id, []).append(v)
    for kunde in (session.query(Kunde).filter(Kunde.id.in_(kunden_ids))
                  .order_by(Kunde.nachname, Kunde.vorname)):
        liste = vorgaenge.get(kunde.id, [])
        if nur_ad_id is not None and not liste:
            continue
        bevorzugt = next((v for v in liste if kern.vorgang_offen(v)), liste[0] if liste else None)
        if bevorzugt is None and lead_vorgang.get(kunde.id):
            bevorzugt = session.get(Vorgang, lead_vorgang[kunde.id])
        ergebnis["treffer"].append({"kunde": kunde, "vorgang": bevorzugt, "vorgaenge": liste,
                                    "herkunft": kunden_ids[kunde.id],
                                    "tel_href": tel_href(kunde.telefon or "")})
    return ergebnis
