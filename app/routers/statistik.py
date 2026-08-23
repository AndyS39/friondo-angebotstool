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
    return {"leads": 0, "erfassungen": 0, "erstellt": 0, "versendet": 0,
            "angenommen": 0, "abgelehnt": 0, "summe_versendet": 0,
            "summe_angenommen": 0, "db": 0}


def kennzahlen(session: Session, von: datetime, bis: datetime,
               nur_benutzer_id: int | None = None) -> dict:
    """Kennzahlen im Zeitraum: gesamt, je Vertriebler-ID, je Kanal."""
    gesamt = _leer()
    je_ad: dict[int, dict] = {}
    je_kanal: dict[str, dict] = {}
    zuordnung = _vertriebler_map(session)
    kunden = {k.id: k for k in session.query(Kunde)}

    def topf(sammlung, schluessel):
        if schluessel not in sammlung:
            sammlung[schluessel] = _leer()
        return sammlung[schluessel]

    def zaehle(feld, ad_id, kanal, betrag=None):
        if nur_benutzer_id is not None and ad_id != nur_benutzer_id:
            return
        for ziel in ([gesamt, topf(je_ad, ad_id)] if ad_id else [gesamt]):
            ziel[feld] += 1
            if betrag:
                for name, wert in betrag.items():
                    ziel[name] += wert
        if kanal:
            k = topf(je_kanal, kanal)
            k[feld] += 1
            if betrag:
                for name, wert in betrag.items():
                    k[name] += wert

    for lead in session.query(Lead).filter(Lead.angelegt_am >= von,
                                           Lead.angelegt_am < bis):
        zaehle("leads", lead.benutzer_id, lead.vertriebskanal)
    for erf in session.query(Erfassung).filter(Erfassung.abgesendet_am >= von,
                                               Erfassung.abgesendet_am < bis):
        kanal = kunden[erf.kunde_id].vertriebskanal if erf.kunde_id in kunden else ""
        zaehle("erfassungen", erf.benutzer_id, kanal)
    for a in session.query(Angebot):
        ad_id = zuordnung.get(a.id)
        kanal = kunden[a.kunde_id].vertriebskanal if a.kunde_id in kunden else ""
        summen = None
        if von <= a.angelegt_am < bis:
            zaehle("erstellt", ad_id, kanal)
        if a.versendet_am and von <= a.versendet_am < bis:
            summen = a.summen()
            zaehle("versendet", ad_id, kanal,
                   {"summe_versendet": summen["endbetrag"],
                    "db": a.deckungsbeitrag()["db"]})
        if a.angenommen_am and von <= a.angenommen_am < bis:
            summen = summen or a.summen()
            zaehle("angenommen", ad_id, kanal,
                   {"summe_angenommen": summen["endbetrag"]})
        if a.abgelehnt_am and von <= a.abgelehnt_am < bis:
            zaehle("abgelehnt", ad_id, kanal)

    def quote(topf_):
        topf_["quote"] = (topf_["angenommen"] / topf_["versendet"] * 100
                          if topf_["versendet"] else 0.0)
    quote(gesamt)
    for t in je_ad.values():
        quote(t)
    for t in je_kanal.values():
        quote(t)
    return {"gesamt": gesamt, "je_ad": je_ad, "je_kanal": je_kanal}


@router.get("")
async def seite(request: Request, zeitraum: str = "monat", von: str = "",
                bis: str = "", session: Session = Depends(get_session)):
    benutzer = request.state.benutzer
    start, ende, zeitraum = _zeitraum(zeitraum, von, bis)
    nur = benutzer.id if benutzer.rolle == "aussendienst" else None
    daten = kennzahlen(session, start, ende, nur_benutzer_id=nur)
    benutzer_map = {b.id: b for b in session.query(Benutzer)}
    ad_zeilen = sorted(daten["je_ad"].items(),
                       key=lambda kv: benutzer_map[kv[0]].name
                       if kv[0] in benutzer_map else "")
    kanal_zeilen = sorted(daten["je_kanal"].items())
    return render(request, "statistik.html", aktiv="/statistik",
                  mobil=benutzer.rolle == "aussendienst",
                  gesamt=daten["gesamt"], ad_zeilen=ad_zeilen,
                  kanal_zeilen=kanal_zeilen, benutzer_map=benutzer_map,
                  eigene_ansicht=nur is not None,
                  zeitraum=zeitraum, zeitraeume=ZEITRAEUME,
                  von=start.strftime("%Y-%m-%d"),
                  bis=(ende - timedelta(days=1)).strftime("%Y-%m-%d"),
                  meldung="")
