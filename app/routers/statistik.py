# Statistik (v6, Phase 41): Kennzahlen mit Zeitraumwahl – gesamt, je
# Vertriebler und je Vertriebskanal. Außendienst sieht ausschließlich die
# eigenen Zahlen. Zeitpunkte: Leads = angelegt_am, Erfassungen = abgesendet_am,
# Angebote erstellt = angelegt_am, versendet/angenommen/abgelehnt = die mit
# angebot_status_setzen gestempelten Zeitpunkte (Bestand: Näherung
# Angebotsdatum, siehe migrate.py). Archivierte/„Individuell“ zählen als das,
# was sie zuletzt waren – über die Zeitstempel automatisch ohne Doppelzählung.

from datetime import date, datetime, timedelta

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.db import get_session
from app.models import Angebot, Benutzer, Erfassung, Kunde, Lead
from app.templating import render

router = APIRouter(prefix="/statistik")

ZEITRAEUME = [("woche", "Diese Woche"), ("monat", "Dieser Monat"),
              ("quartal", "Dieses Quartal"), ("jahr", "Dieses Jahr"),
              ("frei", "Frei wählbar")]


def _zeitraum(name: str, von: str, bis: str) -> tuple[datetime, datetime, str]:
    heute = date.today()
    if name == "woche":
        start = heute - timedelta(days=heute.weekday())
        ende = start + timedelta(days=7)
    elif name == "quartal":
        q_monat = ((heute.month - 1) // 3) * 3 + 1
        start = heute.replace(month=q_monat, day=1)
        ende = (start.replace(month=q_monat + 3, day=1) if q_monat < 10
                else start.replace(year=start.year + 1, month=1, day=1))
    elif name == "jahr":
        start = heute.replace(month=1, day=1)
        ende = start.replace(year=start.year + 1)
    elif name == "frei" and von:
        try:
            start = datetime.strptime(von, "%Y-%m-%d").date()
            ende = (datetime.strptime(bis, "%Y-%m-%d").date() + timedelta(days=1)
                    if bis else heute + timedelta(days=1))
        except ValueError:
            start, ende = heute.replace(day=1), heute + timedelta(days=1)
    else:   # monat (Standard)
        name = "monat"
        start = heute.replace(day=1)
        ende = (start.replace(month=start.month + 1) if start.month < 12
                else start.replace(year=start.year + 1, month=1))
    return (datetime.combine(start, datetime.min.time()),
            datetime.combine(ende, datetime.min.time()), name)


def _vertriebler_map(session: Session) -> dict[int, int]:
    """Angebot-ID -> Benutzer-ID (Erfassung gewinnt, sonst Override-Feld)."""
    zuordnung: dict[int, int] = {}
    for a in session.query(Angebot).filter(Angebot.vertriebler_id.isnot(None)):
        zuordnung[a.id] = a.vertriebler_id
    for e in session.query(Erfassung).filter(Erfassung.angebot_id.isnot(None)):
        zuordnung[e.angebot_id] = e.benutzer_id
    return zuordnung


def _leer() -> dict:
    # Angebots-Kennzahlen sind GESAMT-Werte; die x_-Felder zählen den darin
    # enthaltenen TAIFUN-Anteil (v7), Tool = gesamt − extern. DB nur für Tool.
    return {"leads": 0, "erfassungen": 0, "erstellt": 0, "versendet": 0,
            "angenommen": 0, "abgelehnt": 0, "summe_versendet": 0,
            "summe_angenommen": 0, "db": 0,
            "x_erstellt": 0, "x_versendet": 0, "x_angenommen": 0,
            "x_abgelehnt": 0, "x_summe_versendet": 0, "x_summe_angenommen": 0}


def kennzahlen(session: Session, von: datetime, bis: datetime,
               nur_benutzer_id: int | None = None) -> dict:
    """Kennzahlen im Zeitraum: gesamt, je Vertriebler-ID, je Kanal."""
    gesamt = _leer()
    je_ad: dict[int, dict] = {}
    je_kanal: dict[str, dict] = {}
    je_sparte: dict[str, dict] = {}   # v8: WP/PV/KL/WB
    zuordnung = _vertriebler_map(session)
    kunden = {k.id: k for k in session.query(Kunde)}

    def topf(sammlung, schluessel):
        if schluessel not in sammlung:
            sammlung[schluessel] = _leer()
        return sammlung[schluessel]

    def zaehle(feld, ad_id, kanal, betrag=None, sparte=""):
        if nur_benutzer_id is not None and ad_id != nur_benutzer_id:
            return
        ziele = [gesamt] + ([topf(je_ad, ad_id)] if ad_id else [])
        if kanal:
            ziele.append(topf(je_kanal, kanal))
        if sparte:
            ziele.append(topf(je_sparte, sparte))
        for ziel in ziele:
            ziel[feld] += 1
            if betrag:
                for name, wert in betrag.items():
                    ziel[name] += wert

    for lead in session.query(Lead).filter(Lead.angelegt_am >= von,
                                           Lead.angelegt_am < bis):
        zaehle("leads", lead.benutzer_id, lead.vertriebskanal)
    for erf in session.query(Erfassung).filter(Erfassung.abgesendet_am >= von,
                                               Erfassung.abgesendet_am < bis):
        kanal = kunden[erf.kunde_id].vertriebskanal if erf.kunde_id in kunden else ""
        zaehle("erfassungen", erf.benutzer_id, kanal, sparte=erf.sparte or "WP")
    for a in session.query(Angebot):
        if a.status == "Überholt":
            continue   # v9: durch eine neue Version ersetzt – zählt nicht mehr
        ad_id = zuordnung.get(a.id)
        kanal = kunden[a.kunde_id].vertriebskanal if a.kunde_id in kunden else ""
        a_sparte = a.konfigurator_typ or "WP"
        summen = None
        if von <= a.angelegt_am < bis:
            zaehle("erstellt", ad_id, kanal, sparte=a_sparte)
            if a.extern:
                zaehle("x_erstellt", ad_id, kanal, sparte=a_sparte)
        if a.versendet_am and von <= a.versendet_am < bis:
            summen = a.summen()
            betrag = {"summe_versendet": summen["endbetrag"]}
            if not a.extern:   # DB gibt es nur für Tool-Angebote (v7)
                betrag["db"] = a.deckungsbeitrag()["db"]
            zaehle("versendet", ad_id, kanal, betrag, sparte=a_sparte)
            if a.extern:
                zaehle("x_versendet", ad_id, kanal,
                       {"x_summe_versendet": summen["endbetrag"]}, sparte=a_sparte)
        if a.angenommen_am and von <= a.angenommen_am < bis:
            summen = summen or a.summen()
            zaehle("angenommen", ad_id, kanal,
                   {"summe_angenommen": summen["endbetrag"]}, sparte=a_sparte)
            if a.extern:
                zaehle("x_angenommen", ad_id, kanal,
                       {"x_summe_angenommen": summen["endbetrag"]}, sparte=a_sparte)
        if a.abgelehnt_am and von <= a.abgelehnt_am < bis:
            zaehle("abgelehnt", ad_id, kanal, sparte=a_sparte)
            if a.extern:
                zaehle("x_abgelehnt", ad_id, kanal, sparte=a_sparte)

    def quote(topf_):
        topf_["quote"] = (topf_["angenommen"] / topf_["versendet"] * 100
                          if topf_["versendet"] else 0.0)
        topf_["x_quote"] = (topf_["x_angenommen"] / topf_["x_versendet"] * 100
                            if topf_["x_versendet"] else 0.0)
        t_versendet = topf_["versendet"] - topf_["x_versendet"]
        topf_["t_quote"] = ((topf_["angenommen"] - topf_["x_angenommen"])
                            / t_versendet * 100 if t_versendet else 0.0)
    quote(gesamt)
    for t in je_ad.values():
        quote(t)
    for t in je_kanal.values():
        quote(t)
    for t in je_sparte.values():
        quote(t)
    return {"gesamt": gesamt, "je_ad": je_ad, "je_kanal": je_kanal,
            "je_sparte": je_sparte}


def ablehnungsgruende_verteilung(session: Session, von: datetime, bis: datetime,
                                 nur_benutzer_id=None, ad_id: int = 0,
                                 kanal: str = "", sparte: str = "") -> list[tuple[str, int]]:
    """v8: Verteilung der Ablehnungsgründe im Zeitraum, filterbar nach
    Vertriebler, Kanal und Sparte (Tool- UND TAIFUN-Angebote)."""
    zuordnung = _vertriebler_map(session)
    kunden = {k.id: k for k in session.query(Kunde)}
    zaehler: dict[str, int] = {}
    for a in session.query(Angebot).filter(Angebot.abgelehnt_am.isnot(None),
                                           Angebot.abgelehnt_am >= von,
                                           Angebot.abgelehnt_am < bis):
        a_ad = zuordnung.get(a.id)
        if nur_benutzer_id is not None and a_ad != nur_benutzer_id:
            continue
        if ad_id and a_ad != ad_id:
            continue
        if kanal and (a.kunde_id not in kunden
                      or kunden[a.kunde_id].vertriebskanal != kanal):
            continue
        if sparte and (a.konfigurator_typ or "WP") != sparte:
            continue
        grund = a.ablehnungsgrund or "– ohne Angabe –"
        zaehler[grund] = zaehler.get(grund, 0) + 1
    return sorted(zaehler.items(), key=lambda kv: (-kv[1], kv[0]))


@router.get("")
async def seite(request: Request, zeitraum: str = "monat", von: str = "",
                bis: str = "", grund_ad: int = 0, grund_kanal: str = "",
                grund_sparte: str = "", session: Session = Depends(get_session)):
    benutzer = request.state.benutzer
    start, ende, zeitraum = _zeitraum(zeitraum, von, bis)
    nur = benutzer.id if benutzer.rolle == "aussendienst" else None
    daten = kennzahlen(session, start, ende, nur_benutzer_id=nur)
    grund_zeilen = ablehnungsgruende_verteilung(
        session, start, ende, nur_benutzer_id=nur,
        ad_id=grund_ad, kanal=grund_kanal, sparte=grund_sparte)
    benutzer_map = {b.id: b for b in session.query(Benutzer)}
    ad_zeilen = sorted(daten["je_ad"].items(),
                       key=lambda kv: benutzer_map[kv[0]].name
                       if kv[0] in benutzer_map else "")
    kanal_zeilen = sorted(daten["je_kanal"].items())
    reihenfolge = {"WP": 0, "PV": 1, "KL": 2, "WB": 3}
    sparten_zeilen = sorted(daten["je_sparte"].items(),
                            key=lambda kv: reihenfolge.get(kv[0], 9))
    return render(request, "statistik.html", aktiv="/statistik",
                  mobil=benutzer.rolle == "aussendienst",
                  gesamt=daten["gesamt"], ad_zeilen=ad_zeilen,
                  kanal_zeilen=kanal_zeilen, sparten_zeilen=sparten_zeilen,
                  grund_zeilen=grund_zeilen, grund_ad=grund_ad,
                  grund_kanal=grund_kanal, grund_sparte=grund_sparte,
                  benutzer_map=benutzer_map,
                  eigene_ansicht=nur is not None,
                  zeitraum=zeitraum, zeitraeume=ZEITRAEUME,
                  von=start.strftime("%Y-%m-%d"),
                  bis=(ende - timedelta(days=1)).strftime("%Y-%m-%d"),
                  meldung="")
