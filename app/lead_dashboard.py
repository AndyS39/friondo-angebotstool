# Lead-Management V2 – persönliches Dashboard „Meine Arbeit“ (v23,
# PLAN_LEAD_V2 Phase 110, Diktat A1, Festlegungen F6/F16, Annahme A-12).
# Blöcke für den angemeldeten Benutzer: Wiedervorlagen fällig + kommende
# Tage aus BEIDEN Mechaniken (Lead-Wiedervorlage naechste_aktion_am /
# zurueckgestellt_bis; Angebots-Wiedervorlage v10 wiedervorlage_am), mir
# zugeteilte Vorgänge nach Phase, Termine der nächsten Tage, offene To-Dos,
# Kacheln. Rollen: Innendienst/Leadmanagement/Admin (Zuständigkeit =
# leadmanager_id, freie Leads zählen mit) und Handelsvertreter (F16:
# Zuständigkeit = vorgaenge.ad_id, eigene Termine). Außendienst ohne
# HV-Kennzeichen bleibt bei „Meine Termine“ (F6, Weiterleitung im Router).
# Demo-Leads werden eingeschlossen und als „inkl. Demo“ gekennzeichnet.
# v25 (PLAN_LEAD_V3 Phase 120): Wiedervorlagen sind nur noch manuell gesetzte
# (die Kaskade setzt keine mehr); neue Liste „Ohne nächsten Schritt“ (eigene
# Leads der Gruppe Neu mit Versuch ≥ 1, ohne Wiedervorlage, ohne Termin,
# letzter Anruf älter als Parameter ohne_schritt_tage) ersetzt die automatische
# Wiedervorlage; Phasen-Labels aus dem Blatt Status („Kontaktiert“).

from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from app import lead_todos, lead_v2
from app import leadmanagement as kern
from app.models import (Benutzer, Kunde, LeadAktivitaet, Vorgang, VotTermin,
                        ANRUF_ERGEBNIS_NAMEN, LEAD_PHASEN, LEAD_PHASEN_NAMEN,
                        TERMIN_TYP_NAMEN)

# Phasen ohne weitere Kundenkontakte – deren Wiedervorlagen gelten als hinfällig
ABGESCHLOSSEN = ("gewonnen", "verloren", "unqualifiziert")
TERMIN_STATUS_OFFEN = ("geplant", "bestaetigt", "vorgemerkt")
HORIZONT_STANDARD = 7
AMPEL_NAMEN = {"heiss": "heiß", "warm": "warm", "kalt": "kalt"}
# Gruppe Neu des Hauptboards (Blatt Status): Phasen ohne aktiven Vor-Ort-Termin
GRUPPE_NEU = ("neu", "in_kontaktierung", "qualifiziert")
OHNE_SCHRITT_STANDARD = 2


def _tag(zeit: datetime) -> datetime:
    return zeit.replace(hour=0, minute=0, second=0, microsecond=0)


def horizont_tage(session: Session) -> int:
    """Parameter dashboard_horizont_tage (Standard 7, 1–60)."""
    try:
        wert = int(kern.parameter_holen(session, "dashboard_horizont_tage",
                                        str(HORIZONT_STANDARD)) or HORIZONT_STANDARD)
    except ValueError:
        wert = HORIZONT_STANDARD
    return max(1, min(60, wert))


def ohne_schritt_tage(session: Session) -> int:
    """v25: Parameter ohne_schritt_tage (Standard 2, 0–365) – ab wie vielen
    Tagen seit dem letzten Anruf ein Lead ohne Wiedervorlage/Termin in der
    Liste „Ohne nächsten Schritt“ steht."""
    try:
        wert = int(kern.parameter_holen(session, "ohne_schritt_tage",
                                        str(OHNE_SCHRITT_STANDARD)) or OHNE_SCHRITT_STANDARD)
    except ValueError:
        wert = OHNE_SCHRITT_STANDARD
    return max(0, min(365, wert))


def phase_label(phase: str) -> str:
    """Anzeige-Label einer Phase aus dem Blatt Status (v25: in_kontaktierung
    und qualifiziert tragen beide „Kontaktiert“), Fallback LEAD_PHASEN_NAMEN."""
    try:
        from app import leadmanagement_logik
        zeile = leadmanagement_logik.hole_logik().status_zeile(phase or "")
        if zeile is not None and zeile.label:
            return zeile.label
    except Exception:
        pass
    return LEAD_PHASEN_NAMEN.get(phase or "", phase or "")


def ist_hv(session: Session, benutzer) -> bool:
    return lead_v2.ist_handelsvertreter(session, benutzer)


def ist_buero(benutzer) -> bool:
    """Innendienst, Leadmanagement (auch als Mehrfachrolle) und Admin."""
    return benutzer is not None and (
        benutzer.rolle in ("admin", "innendienst") or benutzer.hat_rolle("leadmanagement"))


def _meine_leads(abfrage, benutzer, hv: bool, mit_freien: bool = True):
    """Zuständigkeitsfilter: HV = vorgaenge.ad_id; Büro = leadmanager_id
    (freie Leads ohne Leadmanager zählen mit, wie in der Anrufliste)."""
    if hv:
        return abfrage.filter(Vorgang.ad_id == benutzer.id)
    if mit_freien:
        return abfrage.filter((Vorgang.leadmanager_id == benutzer.id)
                              | (Vorgang.leadmanager_id.is_(None)))
    return abfrage.filter(Vorgang.leadmanager_id == benutzer.id)


def _kunden(session: Session, vorgaenge: list) -> dict:
    ids = {v.kunde_id for v in vorgaenge}
    if not ids:
        return {}
    return {k.id: k for k in session.query(Kunde).filter(Kunde.id.in_(ids))}


def _letzte_anrufe(session: Session, vorgang_ids: set) -> dict:
    """Letzter Anruf je Vorgang (Grund der Lead-Wiedervorlage)."""
    letzte: dict = {}
    if not vorgang_ids:
        return letzte
    for a in (session.query(LeadAktivitaet)
              .filter(LeadAktivitaet.vorgang_id.in_(vorgang_ids),
                      LeadAktivitaet.typ == "anruf")
              .order_by(LeadAktivitaet.zeitpunkt)):
        letzte[a.vorgang_id] = a
    return letzte


def _zeile(vorgang, kunde, datum, art, grund, jetzt, **extra) -> dict:
    heute = jetzt.date()
    tag = datum.date()
    if art == "lead" and extra.get("quelle") != "zurueckgestellt":
        ueberfaellig = datum < jetzt
    else:
        ueberfaellig = tag < heute          # Datumsangaben ohne Uhrzeit
    zeile = {
        "vorgang": vorgang, "kunde": kunde, "datum": datum, "art": art,
        "grund": grund, "phase": phase_label(vorgang.lead_phase or ""),
        "faellig": tag <= heute, "ueberfaellig": ueberfaellig, "heute": tag == heute,
        "kommend": tag > heute, "demo": bool(vorgang.demo),
        "mit_uhrzeit": art == "lead" and extra.get("quelle") != "zurueckgestellt",
    }
    zeile.update(extra)
    return zeile


def lead_wiedervorlagen(session: Session, benutzer, jetzt: datetime,
                        horizont: int, hv: bool) -> list[dict]:
    """Lead-Wiedervorlagen: naechste_aktion_am (v25: nur noch manuell gesetzt
    – Wiedervorlage-Button, Rückruf gewünscht, falsche Nummer; die Kaskade
    setzt keine Wiedervorlage mehr) und zurueckgestellt_bis – fällig oder
    innerhalb des Horizonts, nach Datum sortiert."""
    ende = _tag(jetzt) + timedelta(days=horizont + 1)
    abfrage = (session.query(Vorgang)
               .filter(Vorgang.lead_phase.isnot(None),
                       ~Vorgang.lead_phase.in_(ABGESCHLOSSEN)))
    abfrage = _meine_leads(abfrage, benutzer, hv)
    abfrage = abfrage.filter(
        ((Vorgang.lead_phase == "zurueckgestellt")
         & Vorgang.zurueckgestellt_bis.isnot(None)
         & (Vorgang.zurueckgestellt_bis < ende))
        | ((Vorgang.lead_phase != "zurueckgestellt")
           & Vorgang.naechste_aktion_am.isnot(None)
           & (Vorgang.naechste_aktion_am < ende)))
    vorgaenge = abfrage.all()
    kunden = _kunden(session, vorgaenge)
    anrufe = _letzte_anrufe(session, {v.id for v in vorgaenge})
    zeilen = []
    for v in vorgaenge:
        kunde = kunden.get(v.kunde_id)
        if kunde is None:
            continue
        if v.lead_phase == "zurueckgestellt":
            datum = v.zurueckgestellt_bis
            grund = "Zurückgestellt: " + (v.zurueckgestellt_grund or "ohne Grund")
            quelle = "zurueckgestellt"
        else:
            datum = v.naechste_aktion_am
            letzter = anrufe.get(v.id)
            n = v.versuch_nr or 0
            if v.lead_phase == "nicht_erreicht":
                grund = "Nurture nach Kaskade – erneut versuchen"
                quelle = "nurture"
            elif letzter is not None and letzter.ergebnis == "rueckruf_gewuenscht":
                grund = "Rückruf gewünscht"
                quelle = "rueckruf"
            elif letzter is not None and letzter.ergebnis == "falsche_nummer":
                grund = "Falsche Nummer – Nummer prüfen"
                quelle = "nummer"
            elif n:
                # v25: manuell gesetzte Wiedervorlage (die Kaskade setzt keine mehr)
                grund = (f"Wiedervorlage · {n}× "
                         f"{ANRUF_ERGEBNIS_NAMEN.get(letzter.ergebnis, 'nicht erreicht').lower() if letzter else 'nicht erreicht'}")
                quelle = "wiedervorlage"
            else:
                grund = "Wiedervorlage"
                quelle = "aktion"
        if datum is None:
            continue
        zeilen.append(_zeile(v, kunde, datum, "lead", grund, jetzt, quelle=quelle,
                             frei=v.leadmanager_id is None, versuche=v.versuch_nr or 0))
    zeilen.sort(key=lambda z: z["datum"])
    return zeilen


def angebots_wiedervorlagen(session: Session, benutzer, jetzt: datetime,
                            horizont: int, hv: bool) -> list[dict]:
    """Angebots-Wiedervorlagen (v10-Verfolgung): wiedervorlage_am mit
    wiedervorlage_benutzer_id = ich; für Büro-Rollen zusätzlich NULL
    (= Innendienst). HV/AD sehen nur selbst gesetzte."""
    ende = _tag(jetzt) + timedelta(days=horizont + 1)
    abfrage = (session.query(Vorgang)
               .filter(Vorgang.wiedervorlage_am.isnot(None),
                       Vorgang.wiedervorlage_am < ende))
    if hv or not ist_buero(benutzer):
        abfrage = abfrage.filter(Vorgang.wiedervorlage_benutzer_id == benutzer.id)
    else:
        abfrage = abfrage.filter((Vorgang.wiedervorlage_benutzer_id == benutzer.id)
                                 | (Vorgang.wiedervorlage_benutzer_id.is_(None)))
    vorgaenge = abfrage.order_by(Vorgang.wiedervorlage_am).all()
    kunden = _kunden(session, vorgaenge)
    benutzer_map = {b.id: b for b in session.query(Benutzer)}
    zeilen = []
    for v in vorgaenge:
        kunde = kunden.get(v.kunde_id)
        if kunde is None:
            continue
        ampel = AMPEL_NAMEN.get(v.verfolgung_ampel or "", "")
        verantwortlich = (benutzer_map[v.wiedervorlage_benutzer_id].name
                          if v.wiedervorlage_benutzer_id in benutzer_map else "Innendienst")
        grund = "Angebotsverfolgung" + (f" · {ampel}" if ampel else "")
        zeilen.append(_zeile(v, kunde, v.wiedervorlage_am, "angebot", grund, jetzt,
                             quelle="angebot", verantwortlich=verantwortlich,
                             frei=v.wiedervorlage_benutzer_id is None))
    return zeilen


def ohne_naechsten_schritt(session: Session, benutzer, jetzt: datetime,
                           hv: bool, tage: int | None = None) -> list[dict]:
    """v25 (Phase 120) [ANNAHME]: Ersatz für die weggefallene automatische
    Wiedervorlage – eigene Leads der Gruppe Neu (neu/in_kontaktierung/
    qualifiziert, ohne aktiven VOT) mit Versuch ≥ 1, ohne Wiedervorlage
    (naechste_aktion_am und zurueckgestellt_bis leer), ohne offenen Termin
    (geplant/bestätigt/vorgemerkt, alle Terminarten), letzter Anruf älter als
    ohne_schritt_tage (ohne Anruf-Aktivität: Erstkontakt bzw. Eingang).
    „Eigene“ wie bei den Wiedervorlagen: HV = ad_id, Büro = Leadmanager ich
    oder frei (Kennzeichen frei). Älteste zuerst."""
    tage = ohne_schritt_tage(session) if tage is None else tage
    grenze = jetzt - timedelta(days=tage)
    abfrage = (session.query(Vorgang)
               .filter(Vorgang.lead_phase.in_(GRUPPE_NEU),
                       Vorgang.versuch_nr.isnot(None), Vorgang.versuch_nr >= 1,
                       Vorgang.naechste_aktion_am.is_(None),
                       Vorgang.zurueckgestellt_bis.is_(None)))
    abfrage = _meine_leads(abfrage, benutzer, hv)
    vorgaenge = abfrage.all()
    if not vorgaenge:
        return []
    ids = {v.id for v in vorgaenge}
    mit_termin = {t.vorgang_id for t in session.query(VotTermin.vorgang_id)
                  .filter(VotTermin.vorgang_id.in_(ids),
                          VotTermin.status.in_(TERMIN_STATUS_OFFEN))}
    kunden = _kunden(session, vorgaenge)
    anrufe = _letzte_anrufe(session, ids)
    zeilen = []
    for v in vorgaenge:
        if v.id in mit_termin:
            continue
        kunde = kunden.get(v.kunde_id)
        if kunde is None:
            continue
        letzter = anrufe.get(v.id)
        zeit = letzter.zeitpunkt if letzter is not None else (v.erstkontakt_am or v.eingang_am)
        if zeit is None or zeit > grenze:
            continue
        ergebnis = (ANRUF_ERGEBNIS_NAMEN.get(letzter.ergebnis, letzter.ergebnis or "Anruf")
                    if letzter is not None else "kein Anruf protokolliert")
        zeilen.append({
            "vorgang": v, "kunde": kunde, "letzter": zeit, "ergebnis": ergebnis,
            "tage": max(0, (jetzt - zeit).days), "versuche": v.versuch_nr or 0,
            "phase": phase_label(v.lead_phase or ""), "frei": v.leadmanager_id is None,
            "demo": bool(v.demo),
        })
    zeilen.sort(key=lambda z: z["letzter"])
    return zeilen


def zugeteilte(session: Session, benutzer, hv: bool) -> dict:
    """Mir zugeteilte Vorgänge (HV: ad_id, sonst leadmanager_id), nach
    Lead-Phase gruppiert mit Zählern; abgeschlossene Phasen eingeklappt.
    v25: Phasen mit demselben Label (in_kontaktierung + qualifiziert →
    „Kontaktiert“) bilden eine Gruppe."""
    abfrage = session.query(Vorgang).filter(Vorgang.lead_phase.isnot(None))
    abfrage = _meine_leads(abfrage, benutzer, hv, mit_freien=False)
    vorgaenge = abfrage.order_by(Vorgang.eingang_am.desc().nullslast(), Vorgang.id.desc()).all()
    kunden = _kunden(session, vorgaenge)
    je_phase: dict[str, list] = {p: [] for p in LEAD_PHASEN}
    for v in vorgaenge:
        je_phase.setdefault(v.lead_phase, []).append({"vorgang": v, "kunde": kunden.get(v.kunde_id)})
    gruppen = []
    je_label: dict[str, dict] = {}
    for phase in LEAD_PHASEN + [p for p in je_phase if p not in LEAD_PHASEN]:
        zeilen = je_phase.get(phase) or []
        if not zeilen:
            continue
        name = phase_label(phase)
        gruppe = je_label.get(name)
        if gruppe is not None:
            gruppe["zeilen"].extend(zeilen)
            gruppe["n"] = len(gruppe["zeilen"])
            gruppe["phasen"].append(phase)
            continue
        gruppe = {"phase": phase, "phasen": [phase], "name": name,
                  "n": len(zeilen), "zeilen": list(zeilen),
                  "offen": phase not in ABGESCHLOSSEN}
        je_label[name] = gruppe
        gruppen.append(gruppe)
    aktiv = sum(g["n"] for g in gruppen if g["offen"])
    return {"gruppen": gruppen, "gesamt": len(vorgaenge), "aktiv": aktiv,
            "demo": sum(1 for v in vorgaenge if v.demo)}


def termine(session: Session, benutzer, jetzt: datetime, horizont: int,
            hv: bool, alle: bool = False) -> list[dict]:
    """Termine (vot_termine, alle Terminarten) ab heute bis Horizont: HV =
    eigene ad_id; Büro = Termine der eigenen Leads (leadmanager_id), mit
    Umschalter alle."""
    start = _tag(jetzt)
    ende = start + timedelta(days=horizont + 1)
    abfrage = (session.query(VotTermin)
               .filter(VotTermin.status.in_(TERMIN_STATUS_OFFEN),
                       VotTermin.beginn.isnot(None),
                       VotTermin.beginn >= start, VotTermin.beginn < ende))
    if hv:
        abfrage = abfrage.filter(VotTermin.ad_id == benutzer.id)
    liste = abfrage.order_by(VotTermin.beginn).all()
    vorgang_ids = {t.vorgang_id for t in liste}
    vorgaenge = ({v.id: v for v in session.query(Vorgang).filter(Vorgang.id.in_(vorgang_ids))}
                 if vorgang_ids else {})
    kunden = _kunden(session, list(vorgaenge.values()))
    benutzer_map = {b.id: b for b in session.query(Benutzer)}
    zeilen = []
    for t in liste:
        v = vorgaenge.get(t.vorgang_id)
        if v is None:
            continue
        if not hv and not alle and v.leadmanager_id != benutzer.id:
            continue
        ad = benutzer_map.get(t.ad_id)
        zeilen.append({"termin": t, "vorgang": v, "kunde": kunden.get(v.kunde_id),
                       "ad": ad.name if ad else "–",
                       "typ": TERMIN_TYP_NAMEN.get(getattr(t, "typ", "vot") or "vot",
                                                   "Vor-Ort-Termin"),
                       "heute": t.beginn.date() == jetzt.date(),
                       "vorgemerkt": t.status == "vorgemerkt", "demo": bool(v.demo)})
    return zeilen


def kacheln(lead_wv: list, angebot_wv: list, todos_zahlen: dict, termine_liste: list,
            ohne_schritt: list | None = None) -> dict:
    alle_wv = lead_wv + angebot_wv
    return {
        "faellig": sum(1 for z in alle_wv if z["faellig"]),
        "ueberfaellig": sum(1 for z in alle_wv if z["ueberfaellig"]),
        "kommend": sum(1 for z in alle_wv if z["kommend"]),
        "todos": todos_zahlen.get("offen", 0),
        "todos_faellig": todos_zahlen.get("faellig", 0),
        "termine": len(termine_liste),
        "termine_heute": sum(1 for z in termine_liste if z["heute"]),
        "ohne_schritt": len(ohne_schritt or []),   # v25 (Phase 120)
    }


def daten(session: Session, benutzer, termine_alle: bool = False,
          jetzt: datetime | None = None) -> dict:
    """Alles für dashboard.html."""
    jetzt = jetzt or datetime.now()
    hv = ist_hv(session, benutzer)
    horizont = horizont_tage(session)
    lead_wv = lead_wiedervorlagen(session, benutzer, jetzt, horizont, hv)
    angebot_wv = angebots_wiedervorlagen(session, benutzer, jetzt, horizont, hv)
    todos_offen = lead_todos.offene(session, benutzer.id)
    todos_zahlen = {"offen": len(todos_offen),
                    "faellig": sum(1 for t in todos_offen
                                   if t.faellig_am and t.faellig_am <= jetzt)}
    termine_liste = termine(session, benutzer, jetzt, horizont, hv, alle=termine_alle)
    schritt_tage = ohne_schritt_tage(session)
    ohne_schritt = ohne_naechsten_schritt(session, benutzer, jetzt, hv, tage=schritt_tage)
    return {
        "jetzt": jetzt, "heute": jetzt.date(), "horizont": horizont, "hv": hv,
        "lead_wv": lead_wv, "angebot_wv": angebot_wv,
        "lead_wv_faellig": [z for z in lead_wv if z["faellig"]],
        "lead_wv_kommend": [z for z in lead_wv if z["kommend"]],
        "angebot_wv_faellig": [z for z in angebot_wv if z["faellig"]],
        "angebot_wv_kommend": [z for z in angebot_wv if z["kommend"]],
        "zugeteilt": zugeteilte(session, benutzer, hv),
        "termine": termine_liste, "termine_alle": termine_alle,
        "todos": lead_todos.zeilen(session, todos_offen, jetzt),
        # v25 (Phase 120): Liste „Ohne nächsten Schritt“ + Parameter
        "ohne_schritt": ohne_schritt, "ohne_schritt_tage": schritt_tage,
        "kacheln": kacheln(lead_wv, angebot_wv, todos_zahlen, termine_liste, ohne_schritt),
        "mit_demo": kern.demo_aktiv(session),
        "empfaenger": lead_todos.empfaenger_liste(session),
    }


# --- Schnellaktionen Wiedervorlage (Erledigt / Verschieben) -----------------------

def _zugriff_wv(benutzer, vorgang: Vorgang, art: str, hv: bool) -> bool:
    if benutzer is None:
        return False
    if benutzer.rolle == "admin":
        return True
    if art == "angebot":
        if hv or not ist_buero(benutzer):
            return vorgang.wiedervorlage_benutzer_id == benutzer.id
        return vorgang.wiedervorlage_benutzer_id in (None, benutzer.id)
    if hv:
        return vorgang.ad_id == benutzer.id
    return ist_buero(benutzer) and vorgang.leadmanager_id in (None, benutzer.id)


def wiedervorlage_aktion(session: Session, vorgang: Vorgang, benutzer, art: str,
                         aktion: str, datum_text: str = "") -> str:
    """Erledigt = Wiedervorlage löschen (Lead: zurückgestellt → wieder Neu),
    Verschieben = neues Datum; immer mit Aktivität. Liefert die Meldung."""
    hv = ist_hv(session, benutzer)
    if not _zugriff_wv(benutzer, vorgang, art, hv):
        return "Kein Zugriff auf diese Wiedervorlage."
    kunde = session.get(Kunde, vorgang.kunde_id)
    name = kunde.anzeige_name if kunde else f"Vorgang {vorgang.id}"
    neu = lead_todos.faellig_parsen(datum_text) if aktion == "verschieben" else None
    if aktion == "verschieben" and neu is None:
        return "Verschieben: bitte ein Datum angeben."
    if art == "angebot":
        from app import vorgaenge as vorgaenge_modul
        alt = vorgang.wiedervorlage_am
        if aktion == "verschieben":
            vorgaenge_modul.verfolgung_setzen(
                session, vorgang, benutzer, vorgang.verfolgung_ampel or "",
                neu.strftime("%Y-%m-%d"),
                verantwortlicher_id=vorgang.wiedervorlage_benutzer_id)
            text = f"Angebots-Wiedervorlage verschoben auf {neu.strftime('%d.%m.%Y')}"
        else:
            vorgaenge_modul.verfolgung_setzen(
                session, vorgang, benutzer, vorgang.verfolgung_ampel or "", "")
            text = ("Angebots-Wiedervorlage erledigt"
                    + (f" (war {alt.strftime('%d.%m.%Y')})" if alt else ""))
        if vorgang.lead_phase:
            kern.aktivitaet(session, vorgang.id, "system", text + " – Dashboard",
                            benutzer=benutzer)
        session.flush()
        return f"{text}: {name}."
    # Lead-Wiedervorlage
    if vorgang.lead_phase == "zurueckgestellt":
        if aktion == "verschieben":
            vorgang.zurueckgestellt_bis = _tag(neu)
            text = f"Zurückstellung verschoben bis {neu.strftime('%d.%m.%Y')}"
        else:
            grund = vorgang.zurueckgestellt_grund or "-"
            vorgang.lead_phase = "neu"
            vorgang.zurueckgestellt_bis = None
            vorgang.naechste_aktion_am = None
            text = f"Wiedervorlage erledigt – Zurückstellung beendet (war: {grund})"
    else:
        if aktion == "verschieben":
            vorgang.naechste_aktion_am = neu
            text = f"Wiedervorlage verschoben auf {neu.strftime('%d.%m.%Y %H:%M')}"
        else:
            alt = vorgang.naechste_aktion_am
            vorgang.naechste_aktion_am = None
            text = ("Wiedervorlage erledigt (ohne Anruf)"
                    + (f" – war {alt.strftime('%d.%m.%Y %H:%M')}" if alt else ""))
    kern.aktivitaet(session, vorgang.id, "status", text + " – Dashboard", benutzer=benutzer)
    session.flush()
    return f"{text}: {name}."


# --- Portal-Karte (index.html) ------------------------------------------------------

def portal_zaehler(benutzer) -> dict | None:
    """Zähler „Meine fälligen Wiedervorlagen/To-Dos“ für die Portal-Karte;
    eigene Session, nie eine Ausnahme (die Karte zeigt sonst nichts)."""
    if benutzer is None or getattr(benutzer, "id", None) is None:
        return None
    from app.db import SessionLocal
    session = SessionLocal()
    try:
        if not lead_v2.zugriff_erlaubt(session, benutzer):
            return None
        jetzt = datetime.now()
        hv = ist_hv(session, benutzer)
        horizont = horizont_tage(session)
        wv = (lead_wiedervorlagen(session, benutzer, jetzt, horizont, hv)
              + angebots_wiedervorlagen(session, benutzer, jetzt, horizont, hv))
        wv_faellig = sum(1 for z in wv if z["faellig"])
        todos = lead_todos.zaehler(session, benutzer.id, jetzt)
        return {"faellig": wv_faellig + todos["faellig"], "wv": wv_faellig,
                "todos": todos["faellig"], "todos_offen": todos["offen"],
                "kommend": sum(1 for z in wv if z["kommend"])}
    except Exception:
        return None
    finally:
        session.close()


try:   # Portal-Karte liest den Zähler als Template-Global (main.py bleibt unverändert)
    from app.templating import templates as _templates
    _templates.env.globals["lm_portal_zaehler"] = portal_zaehler
except Exception:
    pass
