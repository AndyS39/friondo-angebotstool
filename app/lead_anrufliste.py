# Anrufliste als gruppierte Arbeitsliste (v21, PLAN_LEAD_V1.1 Phase 89):
# Schnellfilter mit Zählern, fünf Gruppen (Jetzt dran · Weiter versuchen ·
# Neu heute · Wiedervorlagen fällig · Sonstige), zweizeilige Zeile mit
# Versuchs-Punkten und Kontaktstatus-Satz. Derselbe Satz steht im Lead-Kopf
# der Vorgangsakte (kopf_kontext). Route, Ergebnis-Buttons, Dialoge, Panel
# und Tasten 1–7 sind unverändert (app/routers/leadmanagement.py).

import json
from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from app import leadmanagement as kern
from app.models import (Kampagne, Kunde, LeadAktivitaet, LeadQualifizierung,
                        LeadQuelle, Vorgang, VotTermin, ANRUF_ERGEBNIS_NAMEN)

WOCHENTAGE = ["Mo", "Di", "Mi", "Do", "Fr", "Sa", "So"]
OFFENE_PHASEN = ("neu", "in_kontaktierung", "zurueckgestellt", "nicht_erreicht",
                 "qualifiziert")
GRUPPEN = [
    ("dran", "Jetzt dran", "SLA gelb/rot und fällige Rückrufe – in dieser Reihenfolge abarbeiten"),
    ("weiter", "Weiter versuchen", "Kaskade fällig – Leads mit 3 und mehr Versuchen stehen oben"),
    ("neu", "Neu heute", "eingegangen, SLA noch grün – nach Score sortiert"),
    ("wiedervorlage", "Wiedervorlagen fällig", "zurückgestellte Leads, deren Datum erreicht ist"),
    ("sonstige", "Sonstige offene", "nicht fällig – aufklappen"),
]
CHIPS = [("arbeitsliste", "Arbeitsliste"), ("heute", "Heute eingegangen"),
         ("sla_rot", "SLA rot"), ("drei", "≥ 3 Versuche"),
         ("rueckruf", "Rückruf heute"), ("frei", "Ohne Leadmanager")]


def filter_aus_query(q) -> dict:
    """Alle URL-Parameter der Anrufliste (auch die Links der Übersicht)."""
    def _int(name):
        wert = q.get(name, "")
        return int(wert) if str(wert).lstrip("-").isdigit() else None
    return {
        "meine": q.get("meine", "1") == "1",
        "quelle_id": q.get("quelle_id", ""), "kampagne_id": q.get("kampagne_id", ""),
        "quelle_typ": q.get("quelle_typ", ""),
        "sparte": q.get("sparte", ""), "klasse": q.get("klasse", ""),
        "plz": q.get("plz", ""), "phase": q.get("phase", ""), "q": q.get("q", ""),
        "eingang_von": q.get("eingang_von", ""), "eingang_bis": q.get("eingang_bis", ""),
        "sla": q.get("sla", ""), "versuche": _int("versuche"),
        "versuche_min": _int("versuche_min"), "rueckruf": q.get("rueckruf", ""),
        "frei": q.get("frei", "") == "1", "gruppe": q.get("gruppe", ""),
    }


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
            teile.append((f"nächster Versuch: {_zeit(vorgang.naechste_aktion_am, jetzt)}", ""))
        letzte_stufe = max((s.versuch_nr for s in logik.kaskade if s.letzter), default=0)
        if letzte_stufe and n + 1 >= letzte_stufe and vorgang.lead_phase != "nicht_erreicht":
            teile.append(("letzter Versuch der Kaskade – danach „Nicht erreicht“ + Nurture-Mail",
                          "faellig"))
    if vorgang.eingang_art == "monday":
        teile.append(("Terminierung in monday – hier nur Verfolgung", "dezent"))
    return teile


def _gruppe(v: Vorgang, sla: dict, letzter, jetzt: datetime, heute: datetime) -> tuple[str, tuple]:
    n = v.versuch_nr or 0
    rueckruf = (letzter is not None and letzter.ergebnis == "rueckruf_gewuenscht"
                and v.naechste_aktion_am is not None)
    if v.lead_phase == "zurueckgestellt":
        return "wiedervorlage", ((v.zurueckgestellt_bis or jetzt).timestamp(),)
    if rueckruf and v.naechste_aktion_am <= jetzt:
        return "dran", (1, v.naechste_aktion_am.timestamp())
    if n == 0 and v.erstkontakt_am is None and sla.get("farbe") in ("gelb", "rot"):
        return "dran", (0 if sla["farbe"] == "rot" else 2,
                        (v.eingang_am or v.angelegt_am).timestamp())
    if v.naechste_aktion_am is not None and v.naechste_aktion_am <= jetzt:
        return "weiter", (-n, v.naechste_aktion_am.timestamp())
    if letzter is not None and letzter.ergebnis == "falsche_nummer":
        return "weiter", (-n, letzter.zeitpunkt.timestamp())
    if n == 0 and (v.eingang_am or v.angelegt_am) >= heute:
        klasse = {"A": 0, "B": 1, "C": 2}.get(v.score_klasse or "C", 2)
        return "neu", (klasse, (v.eingang_am or v.angelegt_am).timestamp())
    klasse = {"A": 0, "B": 1, "C": 2}.get(v.score_klasse or "C", 2)
    return "sonstige", (klasse, (v.eingang_am or v.angelegt_am).timestamp())


def daten(session: Session, benutzer, f: dict) -> dict:
    """Gruppen + Chip-Zähler. Chips zählen auf der Basisliste (nur der
    Meine/Alle-Schalter wirkt), die Gruppen auf der gefilterten Liste."""
    from app import leadmanagement_logik
    logik = leadmanagement_logik.hole_logik()
    jetzt = datetime.now()
    heute = jetzt.replace(hour=0, minute=0, second=0, microsecond=0)
    morgen = heute + timedelta(days=1)
    phase_filter = f.get("phase") or ""
    abfrage = session.query(Vorgang)
    if phase_filter:
        abfrage = abfrage.filter(Vorgang.lead_phase == phase_filter)
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
                  .filter(VotTermin.status.in_(("geplant", "bestaetigt")))}
    wunsch_namen = {w.key: w.bezeichnung for w in logik.wunschzeiten}

    basis = []
    for v in vorgaenge:
        kunde = kunden.get(v.kunde_id)
        if kunde is None:
            continue
        if not phase_filter:
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
            # Eingang zeigen, nie „Jetzt dran“/SLA rot
            sla = {**sla, "farbe": "", "monday": True}
        liste = anrufe.get(v.id, [])
        letzter = liste[-1] if liste else None
        gruppe, sortierung = _gruppe(v, sla, letzter, jetzt, heute)
        eingang = v.eingang_am or v.angelegt_am
        basis.append({
            "vorgang": v, "kunde": kunde, "sla": sla, "letzter": letzter, "anrufe": liste,
            "gruppe": gruppe, "_sortierung": sortierung, "eingang": eingang,
            "quelle": quellen.get(v.quelle_id),
            "quelle_gruppe": kern.quelle_gruppe(quellen.get(v.quelle_id)),
            "kampagne": kampagnen.get(v.kampagne_id),
            "kanal": (kunde.vertriebskanal or ""),
            "sparten": [s for s in (kunde.interesse or "").split(",") if s.strip()],
            "wiederkehrer": mehrfach.get(v.kunde_id, 0) > 1,
            "monday": v.eingang_art == "monday",
            "frei": v.leadmanager_id is None,
            "nummer_pruefen": letzter is not None and letzter.ergebnis == "falsche_nummer",
            "rueckruf_heute": (letzter is not None and letzter.ergebnis == "rueckruf_gewuenscht"
                               and v.naechste_aktion_am is not None
                               and heute <= v.naechste_aktion_am < morgen),
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
        if f.get("gruppe") and z["gruppe"] != f["gruppe"]:
            continue
        if f.get("quelle_typ") and z["quelle_gruppe"] != f["quelle_typ"]:
            continue
        if f.get("quelle_id") and str(v.quelle_id or "") != str(f["quelle_id"]):
            continue
        if f.get("kampagne_id") not in ("", None) and str(v.kampagne_id or 0) != str(f["kampagne_id"]):
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

    gruppen = []
    for key, titel, erkl in GRUPPEN:
        eigene = sorted((z for z in zeilen if z["gruppe"] == key), key=lambda z: z["_sortierung"])
        gruppen.append({"key": key, "titel": titel, "erkl": erkl, "zeilen": eigene,
                        "eingeklappt": key == "sonstige" and aktiver_chip(f) == "arbeitsliste"
                        and not f.get("gruppe")})
    chip = aktiver_chip(f)
    if chip != "arbeitsliste" or f.get("gruppe") or f.get("quelle_id") or f.get("kampagne_id") \
            or f.get("quelle_typ") or von or f.get("versuche") is not None:
        gruppen = [g for g in gruppen if g["zeilen"]]
    return {"gruppen": gruppen, "zaehler": zaehler, "chip": chip,
            "offen": len(zeilen), "jetzt": jetzt}


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
            "kanal": (kunde.vertriebskanal if kunde else "") or ""}
