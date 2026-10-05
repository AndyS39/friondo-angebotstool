# Lead-Management Übersicht (v21, PLAN_LEAD_V1.1 Phase 88): Modul-Einstieg für
# Leitung/Admin – KPI-Kacheln, Eingänge je Tag (gestapelt nach Quellen-Typ),
# Kontaktstatus der offenen Leads, Erstkontakt heute, Tabelle Quelle × Kanal,
# das bisherige Cockpit als aufklappbare Abschnitte. Alle Eingangszahlen
# kommen aus leadmanagement.eingaenge_zaehlen (eine Zählweise für Übersicht,
# Statistik, Kanal-Report und Portal-Kacheln).

from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from app import leadmanagement as kern
from app.models import (Benutzer, Kampagne, Kunde, LeadPosteingang, LeadQuelle,
                        Vorgang, VotTermin)

WOCHENTAGE = ["Mo", "Di", "Mi", "Do", "Fr", "Sa", "So"]


def _tag(zeit: datetime) -> datetime:
    return zeit.replace(hour=0, minute=0, second=0, microsecond=0)


def _arbeitstage_zurueck(heute: datetime, anzahl: int) -> list[datetime]:
    """Die letzten <anzahl> Werktage VOR heute (Mo–Fr)."""
    tage = []
    tag = heute
    while len(tage) < anzahl:
        tag -= timedelta(days=1)
        if tag.weekday() < 5:
            tage.append(tag)
    return tage


def _delta(neu: float, alt: float) -> dict:
    if not alt:
        return {"prozent": None, "richtung": ""}
    prozent = round((neu - alt) / alt * 100)
    return {"prozent": prozent, "richtung": "auf" if prozent > 0 else ("ab" if prozent < 0 else "")}


def offene_leads(session: Session, jetzt: datetime | None = None) -> list[Vorgang]:
    """Offen = Phasen neu, in_kontaktierung, nicht_erreicht (fällig),
    qualifiziert ohne aktiven Termin, zurückgestellt fällig (Plan 88)."""
    jetzt = jetzt or datetime.now()
    mit_termin = {t.vorgang_id for t in session.query(VotTermin)
                  .filter(VotTermin.status.in_(("geplant", "bestaetigt")),
                          VotTermin.typ == "vot")}   # v23 (Phase 108): nur Vor-Ort-Termine
    ergebnis = []
    for v in (session.query(Vorgang)
              .filter(Vorgang.lead_phase.in_(("neu", "in_kontaktierung", "nicht_erreicht",
                                              "qualifiziert", "zurueckgestellt")))):
        if v.lead_phase == "qualifiziert" and v.id in mit_termin:
            continue
        if v.lead_phase == "zurueckgestellt" and (
                v.zurueckgestellt_bis is None or v.zurueckgestellt_bis > jetzt):
            continue
        if v.lead_phase == "nicht_erreicht" and (
                v.naechste_aktion_am is None or v.naechste_aktion_am > jetzt):
            continue
        ergebnis.append(v)
    return ergebnis


def jetzt_dran(session: Session, offene: list[Vorgang], jetzt: datetime) -> list[Vorgang]:
    """SLA gelb/rot ohne ersten Versuch, fällige Rückrufe/nächste Aktionen,
    fällige Wiedervorlagen (zurückgestellt) – die Gruppe „Jetzt dran“."""
    liste = []
    for v in offene:
        if v.lead_phase == "zurueckgestellt":
            liste.append(v)
        elif v.naechste_aktion_am is not None and v.naechste_aktion_am <= jetzt:
            liste.append(v)
        elif not (v.versuch_nr or 0) and v.erstkontakt_am is None \
                and v.eingang_art != "monday" \
                and kern.sla_status(session, v, jetzt)["farbe"] in ("gelb", "rot"):
            liste.append(v)
    return liste


def kpis(session: Session, jetzt: datetime | None = None) -> dict:
    """Die Kacheln – auch für die Portal-Karte."""
    jetzt = jetzt or datetime.now()
    heute = _tag(jetzt)
    morgen = heute + timedelta(days=1)
    heute_n = kern.eingaenge_zaehlen(session, heute, morgen).get("gesamt", 0)
    at = _arbeitstage_zurueck(heute, 10)
    je_tag = kern.eingaenge_zaehlen(session, min(at), heute, "tag")
    schnitt = sum(je_tag.get(t.date(), 0) for t in at) / 10
    woche_n = kern.eingaenge_zaehlen(session, morgen - timedelta(days=7), morgen).get("gesamt", 0)
    vorwoche_n = kern.eingaenge_zaehlen(session, morgen - timedelta(days=14),
                                        morgen - timedelta(days=7)).get("gesamt", 0)
    offene = offene_leads(session, jetzt)
    sla_rot = [v for v in offene if v.lead_phase == "neu" and v.eingang_art != "monday"
               and kern.sla_status(session, v, jetzt)["farbe"] == "rot"]
    dran = jetzt_dran(session, offene, jetzt)
    drei = [v for v in offene if (v.versuch_nr or 0) >= 3]
    vier = [v for v in drei if (v.versuch_nr or 0) >= 4]
    termine = (session.query(VotTermin)
               .filter(VotTermin.status.in_(("geplant", "bestaetigt")),
                       VotTermin.typ == "vot",   # v23 (Phase 108)
                       VotTermin.beginn >= heute, VotTermin.beginn < morgen).all())
    je_ad: dict[int, int] = {}
    for t in termine:
        if t.ad_id:
            je_ad[t.ad_id] = je_ad.get(t.ad_id, 0) + 1
    benutzer_map = {b.id: b for b in session.query(Benutzer)}
    termine_text = " · ".join(
        f"{benutzer_map[ad].name.split()[0] if ad in benutzer_map else '?'} {n}"
        for ad, n in sorted(je_ad.items(), key=lambda x: -x[1])[:3])
    posteingang = (session.query(LeadPosteingang)
                   .filter(LeadPosteingang.status == "offen").count())
    return {
        "heute": heute_n, "schnitt_10at": round(schnitt, 1),
        "delta_heute": _delta(heute_n, schnitt),
        "woche": woche_n, "vorwoche": vorwoche_n, "delta_woche": _delta(woche_n, vorwoche_n),
        "sla_rot": len(sla_rot), "jetzt_dran": len(dran),
        "drei_versuche": len(drei), "vier_versuche": len(vier),
        "termine_heute": len(termine), "termine_text": termine_text,
        "posteingang": posteingang, "offene": len(offene),
        "_offene": offene,
    }


def eingaenge_je_tag(session: Session, jetzt: datetime) -> dict:
    """Letzte 14 Kalendertage inkl. heute, gestapelt nach Quellen-Typ."""
    heute = _tag(jetzt)
    start = heute - timedelta(days=13)
    zaehlung = kern.eingaenge_zaehlen(session, start, heute + timedelta(days=1), "tag_typ")
    tage = []
    maximum = 1
    for i in range(14):
        tag = start + timedelta(days=i)
        segmente = [(typ, zaehlung.get((tag.date(), typ), 0)) for typ, _ in kern.QUELLEN_GRUPPEN]
        summe = sum(n for _, n in segmente)
        maximum = max(maximum, summe)
        tage.append({"datum": tag, "segmente": segmente, "summe": summe,
                     "heute": tag == heute,
                     "achse": ("heute" if tag == heute else
                               f"{WOCHENTAGE[tag.weekday()]} {tag.day}." if i % 3 == 0
                               else WOCHENTAGE[tag.weekday()])})
    return {"tage": tage, "maximum": maximum,
            "legende": [(typ, name) for typ, name in kern.QUELLEN_GRUPPEN]}


def kontaktstatus(offene: list[Vorgang]) -> list[dict]:
    stufen = [("0", "Noch kein Versuch", "", "versuche=0"), ("1", "1 Versuch", "", "versuche=1"),
              ("2", "2 Versuche", "", "versuche=2"), ("3", "3 Versuche", "warn", "versuche=3"),
              ("4", "4+ Versuche", "rot", "versuche_min=4")]
    zaehler = {k: 0 for k, *_ in stufen}
    for v in offene:
        n = min(v.versuch_nr or 0, 4)
        zaehler[str(n)] += 1
    maximum = max(zaehler.values()) or 1
    return [{"titel": titel, "klasse": klasse, "filter": filt, "n": zaehler[k],
             "breite": round(zaehler[k] / maximum * 100)}
            for k, titel, klasse, filt in stufen]


def erstkontakt_heute(session: Session, jetzt: datetime) -> dict:
    heute = _tag(jetzt)
    morgen = heute + timedelta(days=1)
    try:
        gelb = int(kern.parameter_holen(session, "sla_gelb_min", "60"))
    except ValueError:
        gelb = 60
    vorgaenge = kern._eingang_vorgaenge(session, heute, morgen)
    minuten = [kern.arbeitsminuten(session, v.eingang_am, v.erstkontakt_am)
               for v in vorgaenge if v.erstkontakt_am is not None]
    im_sla = sum(1 for m in minuten if m < gelb)
    erreicht = sum(1 for v in vorgaenge if v.erreicht_am is not None)
    return {"median": kern._median([float(m) for m in minuten]),
            "sla_quote": round(im_sla / len(minuten) * 100) if minuten else None,
            "erreicht": erreicht, "gesamt": len(vorgaenge), "sla_gelb": gelb}


def tabelle(session: Session, jetzt: datetime, zeitraum: str) -> dict:
    """Eingänge je Quelle und Kanal, gruppiert nach Quellen-Typ; Landingpages
    je Kampagne. Spalten heute / 7 Tage / Zeitraum, erreicht %, terminiert %
    (Kohorte der Eingänge des Zeitraums), ≥ 3 Versuche (offen), Kosten je Lead."""
    heute = _tag(jetzt)
    morgen = heute + timedelta(days=1)
    tage = 7 if zeitraum == "woche" else 30
    von = morgen - timedelta(days=tage)
    quellen = {q.id: q for q in session.query(LeadQuelle)}
    kampagnen = {k.id: k for k in session.query(Kampagne)}
    heute_q = kern.eingaenge_zaehlen(session, heute, morgen, "quelle")
    woche_q = kern.eingaenge_zaehlen(session, morgen - timedelta(days=7), morgen, "quelle")
    heute_k = kern.eingaenge_zaehlen(session, heute, morgen, "kampagne")
    woche_k = kern.eingaenge_zaehlen(session, morgen - timedelta(days=7), morgen, "kampagne")
    kohorte = kern._eingang_vorgaenge(session, von, morgen)
    offene = offene_leads(session, jetzt)

    def _schluessel(v):
        q = quellen.get(v.quelle_id)
        if q is not None and q.typ == "landingpage":
            return ("k", v.quelle_id or 0, v.kampagne_id or 0)
        return ("q", v.quelle_id or 0, 0)

    stat: dict[tuple, dict] = {}
    for v in kohorte:
        e = stat.setdefault(_schluessel(v), {"n": 0, "erreicht": 0, "terminiert": 0})
        e["n"] += 1
        if v.erreicht_am is not None:
            e["erreicht"] += 1
        if v.terminiert_am is not None:
            e["terminiert"] += 1
    drei: dict[tuple, int] = {}
    for v in offene:
        if (v.versuch_nr or 0) >= 3:
            drei[_schluessel(v)] = drei.get(_schluessel(v), 0) + 1

    def _anrufliste_link(kanal: str) -> str:
        """v25 (Phase 118): die Anrufliste filtert nicht mehr nach Quelle/
        Kampagne (Filter „Vertriebskanal“) – Zeilen verlinken auf die Liste
        mit dem Kanal der Zeile, Platzhalter-Kanäle ohne Parameter."""
        from urllib.parse import urlencode
        if kanal and kanal not in ("Kanal am Kunden", "– bitte zuordnen"):
            return "/lead-management/anrufliste?" + urlencode({"kanal": kanal})
        return "/lead-management/anrufliste"

    def _zeile(name, kanal, schluessel, heute_n, woche_n, kosten_cent, link,
               kampagne=None, quelle=None):
        e = stat.get(schluessel, {"n": 0, "erreicht": 0, "terminiert": 0})
        return {"name": name, "kanal": kanal, "heute": heute_n, "woche": woche_n,
                "zeitraum": e["n"],
                "erreicht": round(e["erreicht"] / e["n"] * 100) if e["n"] else None,
                "terminiert": round(e["terminiert"] / e["n"] * 100) if e["n"] else None,
                "drei": drei.get(schluessel, 0), "kosten": kosten_cent,
                "link": _anrufliste_link(kanal), "kampagne": kampagne, "quelle": quelle}

    gruppen = []
    summe = {"heute": 0, "woche": 0, "zeitraum": 0, "erreicht": 0, "terminiert": 0,
             "drei": 0, "kosten": 0, "kosten_n": 0}
    for typ, gruppen_name in kern.QUELLEN_GRUPPEN:
        zeilen = []
        for q in sorted(quellen.values(), key=lambda q: q.name.lower()):
            if kern.quelle_gruppe(q) != typ:
                continue
            kanal = "Kanal am Kunden" if q.typ == "monday" else (q.kanal or "Standard")
            if q.typ == "landingpage":
                eigene = [k for k in kampagnen.values() if k.quelle_id == q.id]
                for k in sorted(eigene, key=lambda k: k.name.lower()):
                    s = ("k", q.id, k.id)
                    if not (heute_k.get(k.id) or woche_k.get(k.id) or s in stat or k.aktiv):
                        continue
                    kpl = (round(k.budget_cent / stat[s]["n"]) if k.budget_cent and s in stat
                           and stat[s]["n"] else q.kosten_je_lead_cent)
                    zeilen.append(_zeile(k.name, "– bitte zuordnen" if k.auto_angelegt else kanal,
                                         s, heute_k.get(k.id, 0), woche_k.get(k.id, 0), kpl,
                                         f"/lead-management/anrufliste?kampagne_id={k.id}",
                                         kampagne=k, quelle=q))
                s = ("k", q.id, 0)
                if s in stat or heute_q.get(q.id) or woche_q.get(q.id):
                    ohne = _zeile(f"{q.name} · ohne Kampagne", kanal, s,
                                  heute_q.get(q.id, 0) - sum(z["heute"] for z in zeilen if z["quelle"] is q),
                                  woche_q.get(q.id, 0) - sum(z["woche"] for z in zeilen if z["quelle"] is q),
                                  q.kosten_je_lead_cent,
                                  f"/lead-management/anrufliste?quelle_id={q.id}&kampagne_id=0",
                                  quelle=q)
                    if ohne["zeitraum"] or ohne["heute"] or ohne["woche"]:
                        zeilen.append(ohne)
            else:
                s = ("q", q.id, 0)
                if not (q.aktiv or s in stat or heute_q.get(q.id) or woche_q.get(q.id)):
                    continue
                zeilen.append(_zeile(q.name, kanal, s, heute_q.get(q.id, 0), woche_q.get(q.id, 0),
                                     q.kosten_je_lead_cent,
                                     f"/lead-management/anrufliste?quelle_id={q.id}", quelle=q))
        if zeilen:
            # v25: kein quelle_typ-Filter mehr in der Anrufliste – Gruppenlink ohne Parameter
            gruppen.append({"typ": typ, "name": gruppen_name, "zeilen": zeilen,
                            "link": "/lead-management/anrufliste"})
        for z in zeilen:
            summe["heute"] += z["heute"]
            summe["woche"] += z["woche"]
            summe["zeitraum"] += z["zeitraum"]
            summe["drei"] += z["drei"]
            if z["kosten"]:
                summe["kosten"] += z["kosten"] * z["zeitraum"]
                summe["kosten_n"] += z["zeitraum"]
    gesamt_n = sum(e["n"] for e in stat.values())
    summe["erreicht"] = (round(sum(e["erreicht"] for e in stat.values()) / gesamt_n * 100)
                         if gesamt_n else None)
    summe["terminiert"] = (round(sum(e["terminiert"] for e in stat.values()) / gesamt_n * 100)
                           if gesamt_n else None)
    summe["kosten_schnitt"] = (round(summe["kosten"] / summe["kosten_n"])
                               if summe["kosten_n"] else None)
    return {"gruppen": gruppen, "summe": summe, "tage": tage, "von": von}


def uebersicht_daten(session: Session, zeitraum: str = "30") -> dict:
    jetzt = datetime.now()
    k = kpis(session, jetzt)
    offene = k.pop("_offene")
    return {
        "jetzt": jetzt, "kpis": k, "zeitraum": zeitraum,
        "tage": eingaenge_je_tag(session, jetzt),
        "kontakt": kontaktstatus(offene),
        "erstkontakt": erstkontakt_heute(session, jetzt),
        "tabelle": tabelle(session, jetzt, zeitraum),
        "kaskade": kaskade_text(session),
        "cockpit": kern.cockpit_daten(session),
        "pipeline_wert": kern.pipeline_wert(session),
        "mit_demo": kern.demo_aktiv(session),
        "heute_param": jetzt.strftime("%Y-%m-%d"),
        # v25 (Phase 120): kein Score in der Übersicht (Spalte „qualifiziert“ im Cockpit)
        "score_aktiv": kern.score_aktiv(session),
    }


def kaskade_text(session: Session) -> str:
    """Hinweiszeile aus der Steuerdatei (Blatt Kaskade). v25: die Spalte
    wiedervorlage_nach wird nicht mehr ausgewertet – gezeigt werden die
    Mail-Aktionen je Versuch und der letzte Versuch (keine automatische
    Wiedervorlage)."""
    try:
        from app import leadmanagement_logik
        logik = leadmanagement_logik.hole_logik()
        mails = [str(s.versuch_nr) for s in logik.kaskade
                 if str(s.aktion or "keine").startswith("mail_") and not s.letzter]
        letzte = logik.letzte_stufe()
        if letzte:
            teile = []
            if mails:
                teile.append("Mail nach Versuch " + ", ".join(mails))
            teile.append(f"nach Versuch {letzte} „Nicht erreicht“ (keine automatische Wiedervorlage)")
            return "Kaskade: " + " · ".join(teile)
    except Exception:
        pass
    return ""


def wochen_typ(session: Session, wochen: int = 12) -> dict:
    """Statistik → Leads: Eingänge je Woche × Quellen-Typ (letzte <wochen> Wochen)."""
    jetzt = datetime.now()
    heute = _tag(jetzt)
    montag = heute - timedelta(days=heute.weekday())
    start = montag - timedelta(weeks=wochen - 1)
    zaehlung = kern.eingaenge_zaehlen(session, start, heute + timedelta(days=1), "woche_typ")
    zeilen = []
    for i in range(wochen):
        wochenstart = start + timedelta(weeks=i)
        jahr, kw, _ = wochenstart.isocalendar()
        key = f"{jahr}-KW{kw:02d}"
        werte = [(typ, zaehlung.get((key, typ), 0)) for typ, _ in kern.QUELLEN_GRUPPEN]
        zeilen.append({"woche": key, "von": wochenstart, "werte": werte,
                       "summe": sum(n for _, n in werte)})
    return {"zeilen": zeilen, "typen": kern.QUELLEN_GRUPPEN}


STARTSEITEN = ("dashboard", "hauptboard", "uebersicht", "anrufliste")


def startseite(session: Session, benutzer) -> str:
    """Modul-Einstieg (Parameter lm_startseite): dashboard | hauptboard |
    uebersicht | anrufliste; leer = persönliches Dashboard „Meine Arbeit“
    (v23, PLAN_LEAD_V2 Phase 110 – vorher Übersicht bzw. Anrufliste für die
    Hauptrolle Leadmanagement). Die Team-Übersicht bleibt über den Umschalter
    „Meine Arbeit | Team“ und „Mehr …“ erreichbar."""
    wert = kern.parameter_holen(session, "lm_startseite", "").strip().lower()
    if wert in STARTSEITEN:
        return wert
    return "dashboard"
