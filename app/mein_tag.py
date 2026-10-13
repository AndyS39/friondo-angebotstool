# v32 (PLAN_V19 Phase 161): Datenaufbereitung der Vertriebler-Ansicht „Mein Tag“
# (GET /leads, Template templates/leads/mein_tag.html). Quelle der Termine ist
# ausschließlich vot_termine (Tool-Termine und monday-VOT-Termine, seit v23 gemeinsam):
# - Terminart vot; offene Status geplant | bestaetigt | unbestaetigt [ANNAHME – der Plan
#   nennt „terminiert/unbestätigt“, in vot_termine stehen geplant/erfolgt; abgesagt,
#   no_show, verschoben und vorgemerkt fallen heraus]; ein Termin mit Status erfolgt
#   bleibt nur sichtbar, solange der Vorgang noch eine offene Sparte hat (v8-Regel der
#   Leads-VOT-Liste: Status-Chips je Sparte) [ANNAHME];
# - ohne verknüpftes Angebot am Vorgang (Regel von „Leads VOT“ seit v1);
# - Außendienst: nur eigene Termine – vot_termine.ad_id = Benutzer, Rückfall
#   vorgaenge.ad_id bzw. leads.benutzer_id, wenn ad_id am Termin leer ist [ANNAHME];
#   Innendienst/Admin: alle, Filter Vertriebler;
# - Blöcke: „Termine heute“ (überfällige Termine der Vergangenheit ohne Erfassung zuoberst,
#   Label „überfällig“) und „Weitere Termine“ (ab morgen, chronologisch);
# - je Karte Datum „Mo, 13.10.“, Uhrzeit, Kundenname, Objektadresse (objekte.
#   ausfuehrungsort, bei mehreren Objekten mit Bezeichnung) als Google-Maps-Link,
#   tel:-Link, Sparten-Chips, Herkunft monday | Tool, „Erfassung starten“ mit objekt_id.
# Die Blöcke „Fällig heute“ (app/nachfassen.py) und „Heiße Kunden“ (verfolgung.
# heisse_vorgaenge, Rückfall hier) liefern eigene Karten. Reine Datenbankarbeit.
from datetime import date, datetime, timedelta
from urllib.parse import quote

from sqlalchemy import and_, or_
from sqlalchemy.orm import Session

from app import nachfassen, objekte
from app.models import Angebot, Benutzer, Erfassung, Kunde, Lead, Vorgang, VotTermin

OFFENE_STATUS = ("geplant", "bestaetigt", "unbestaetigt")
STATUS_ABFRAGE = OFFENE_STATUS + ("erfolgt",)
WOCHENTAGE = ("Mo", "Di", "Mi", "Do", "Fr", "Sa", "So")
MAPS_URL = "https://www.google.com/maps/search/?api=1&query="
DARSTELLUNGEN = ("karten", "tabelle")
EINSTELLUNG_DARSTELLUNG = "leads_darstellung"   # benutzer_einstellungen (lead_v2.einstellung_*)
VERFOLGUNG_CHIPS = {"bestellung_angekuendigt": "Bestellung angekündigt"}


# --- Helfer ---------------------------------------------------------------------------

def _tag(wert) -> date | None:
    if isinstance(wert, datetime):
        return wert.date()
    if isinstance(wert, date):
        return wert
    roh = str(wert or "").strip()
    for muster in ("%Y-%m-%d", "%d.%m.%Y", "%d.%m.%y"):
        try:
            return datetime.strptime(roh, muster).date()
        except ValueError:
            continue
    return None


def datum_text(wert) -> str:
    """„Mo, 13.10.“ – Wochentag kurz, Tag und Monat."""
    tag = _tag(wert)
    if tag is None:
        return ""
    return f"{WOCHENTAGE[tag.weekday()]}, {tag.strftime('%d.%m.')}"


def uhr_text(wert) -> str:
    return f"{wert.strftime('%H:%M')} Uhr" if isinstance(wert, datetime) else ""


def maps_url(ort: dict) -> str:
    """Google-Maps-Suche mit URL-kodierter Adresse (neuer Tab im Template)."""
    adresse = ort.get("einzeilig") or ""
    return MAPS_URL + quote(adresse, safe="") if adresse else ""


def herkunft(termin: VotTermin) -> str:
    """Herkunfts-Badge „monday“ oder „Tool“ (Assistent/manuell) [ANNAHME]."""
    return "monday" if (termin.quelle or "") == "monday" else "Tool"


def effektiver_ad(termin: VotTermin, vorgang: Vorgang, lead: Lead | None) -> int | None:
    """Vertriebler des Termins: vot_termine.ad_id, sonst vorgaenge.ad_id, sonst der
    Vertriebler des monday-Leads [ANNAHME]."""
    return termin.ad_id or getattr(vorgang, "ad_id", None) or (lead.benutzer_id if lead else None)


def ist_aussendienst(benutzer) -> bool:
    return getattr(benutzer, "rolle", "") == "aussendienst"


def darstellung_lesen(session: Session, benutzer) -> str:
    """Karten | Tabelle für Innendienst/Admin (Standard Karten, je Nutzer gespeichert);
    der Außendienst sieht immer Karten."""
    if ist_aussendienst(benutzer):
        return "karten"
    from app import lead_v2
    wert = lead_v2.einstellung_holen(session, benutzer.id, EINSTELLUNG_DARSTELLUNG, "karten")
    return wert if wert in DARSTELLUNGEN else "karten"


def darstellung_setzen(session: Session, benutzer, wert: str) -> str:
    from app import lead_v2
    wert = wert if wert in DARSTELLUNGEN else "karten"
    if not ist_aussendienst(benutzer):
        lead_v2.einstellung_setzen(session, benutzer.id, EINSTELLUNG_DARSTELLUNG, wert)
    return wert


def _archiv_filter(abfrage):
    try:   # v31 (Phase 154): Archiv ist eine Lead-Sicht
        from app import lead_archiv
        return lead_archiv.filter_aktiv(abfrage)
    except (ImportError, AttributeError):
        return abfrage


def _chips(lead: Lead | None, sparten: list[str], erfasst: set[str]) -> list[tuple[str, str]]:
    """Status-Chips je Sparte wie in Leads VOT (v8): erfasst | ausgeblendet | offen."""
    if lead is not None:
        from app.routers.leads import sparten_chips
        return sparten_chips(lead, erfasst)
    return [(s, "erfasst" if s in erfasst else "offen") for s in sparten]


def erfassen_url(vorgang: Vorgang, lead: Lead | None, kunde: Kunde, objekt_id) -> str:
    """Startweiche der Erfassung mit Kunde und Objekt (v31): Lead-Vorgänge über
    /leads/{lead}/erfassen (Lead ↔ Erfassung bleibt verknüpft), sonst die Sparten-Auswahl."""
    if lead is not None:
        url = f"/leads/{lead.id}/erfassen"
        return url + (f"?objekt_id={int(objekt_id)}" if objekt_id else "")
    url = f"/erfassung/sparten?kunde_id={kunde.id}"
    return url + (f"&objekt_id={int(objekt_id)}" if objekt_id else "")


# --- Termine ---------------------------------------------------------------------------

def termin_karten(session: Session, benutzer, heute=None) -> list[dict]:
    """Alle sichtbaren Termin-Karten des Benutzers (ungefiltert, chronologisch)."""
    jetzt = heute if isinstance(heute, datetime) else datetime.now()
    heute_tag = jetzt.date()
    aussendienst = ist_aussendienst(benutzer)
    abfrage = (session.query(VotTermin, Vorgang)
               .join(Vorgang, Vorgang.id == VotTermin.vorgang_id)
               .outerjoin(Lead, Lead.id == Vorgang.lead_id)
               .filter(VotTermin.typ == "vot", VotTermin.beginn.isnot(None),
                       VotTermin.status.in_(STATUS_ABFRAGE)))
    abfrage = _archiv_filter(abfrage)
    if aussendienst:
        ich = benutzer.id
        abfrage = abfrage.filter(or_(
            VotTermin.ad_id == ich,
            and_(VotTermin.ad_id.is_(None),
                 or_(Vorgang.ad_id == ich,
                     and_(Vorgang.ad_id.is_(None), Lead.benutzer_id == ich)))))
    zeilen = abfrage.order_by(VotTermin.beginn, VotTermin.id).all()
    if not zeilen:
        return []
    vorgang_ids = {v.id for _, v in zeilen}
    mit_angebot = {a_vid for (a_vid,) in session.query(Angebot.vorgang_id)
                   .filter(Angebot.vorgang_id.in_(vorgang_ids))}
    leads = {l.id: l for l in session.query(Lead)
             .filter(Lead.id.in_({v.lead_id for _, v in zeilen if v.lead_id} or {0}))}
    kunden = {k.id: k for k in session.query(Kunde)
              .filter(Kunde.id.in_({v.kunde_id for _, v in zeilen} or {0}))}
    erfasst: dict[int, set[str]] = {}
    for e in (session.query(Erfassung)
              .filter(Erfassung.vorgang_id.in_(vorgang_ids), Erfassung.status != "Entwurf")):
        erfasst.setdefault(e.vorgang_id, set()).add(e.sparte or "WP")
    benutzer_map = {b.id: b for b in session.query(Benutzer)}
    karten: list[dict] = []
    for termin, vorgang in zeilen:
        if vorgang.id in mit_angebot:
            continue   # Regel seit v1: mit Angebot verlässt der Vorgang die Liste
        kunde = kunden.get(vorgang.kunde_id)
        if kunde is None:
            continue
        lead = leads.get(vorgang.lead_id) if vorgang.lead_id else None
        ad_id = effektiver_ad(termin, vorgang, lead)
        if aussendienst and ad_id != benutzer.id:
            continue
        sparten = (lead.sparten if lead is not None
                   else (objekte.vorgang_interessen(session, vorgang.id) or kunde.interessen or ["WP"]))
        erfasst_set = erfasst.get(vorgang.id, set())
        chips = _chips(lead, sparten, erfasst_set)
        offen = any(status == "offen" for _, status in chips)
        if termin.status == "erfolgt" and not offen:
            continue   # Erfassung vollständig – der Termin ist erledigt
        tag = termin.beginn.date()
        vergangen = tag < heute_tag
        ueberfaellig = vergangen and not erfasst_set
        teilweise = vergangen and bool(erfasst_set) and offen
        if vergangen and not (ueberfaellig or teilweise):
            continue
        ort = objekte.ausfuehrungsort(session, termin=termin, vorgang=vorgang, kunde=kunde)
        objekt_id = ort.get("objekt_id") or termin.objekt_id
        ad = benutzer_map.get(ad_id) if ad_id else None
        telefon = (kunde.telefon or "").strip() or (lead.telefon if lead else "") or ""
        karten.append({
            "termin": termin, "vorgang": vorgang, "kunde": kunde, "lead": lead,
            "tag": tag, "beginn": termin.beginn,
            "datum_text": datum_text(termin.beginn), "uhr_text": uhr_text(termin.beginn),
            "name": nachfassen.kundenname(kunde),
            "ort": ort, "adresse": ort.get("einzeilig") or "",
            "strasse": ort.get("strasse") or "", "plz_ort": " ".join(
                x for x in (ort.get("plz") or "", ort.get("ort") or "") if x),
            "objekt_bezeichnung": (ort.get("bezeichnung") or "") if ort.get("mehrere_objekte") else "",
            "objekt_id": objekt_id, "maps_url": maps_url(ort),
            "telefon": telefon, "tel_href": nachfassen.tel_href(telefon),
            "sparten": sparten, "chips": chips,
            "herkunft": herkunft(termin), "status": termin.status,
            "status_text": (lead.status_text if lead else "") or "",
            "ad_id": ad_id, "ad": ad, "ad_name": ad.name if ad else "",
            "ueberfaellig": ueberfaellig, "teilweise": teilweise, "heute": tag == heute_tag,
            "erfassen_url": erfassen_url(vorgang, lead, kunde, objekt_id),
            "akte_url": f"/vorgaenge/{vorgang.id}",
            "grosskunde": bool(getattr(kunde, "grosskunde", False)),
            "kanal": (lead.vertriebskanal if lead else "") or kunde.vertriebskanal or "",
        })
    return karten


def termine(session: Session, benutzer, von=None, bis=None, status: str = "",
            vertriebler_id: int = 0, heute=None) -> dict:
    """Termin-Blöcke mit Filtern (Termin von/bis, Status = monday-Statustext, Vertriebler
    bei ID/Admin): heute (überfällige zuoberst, dann die heutigen) und weitere (ab morgen),
    jeweils chronologisch; dazu die Auswahlwerte der Filter aus der ungefilterten Liste."""
    alle = termin_karten(session, benutzer, heute)
    status_werte = sorted({k["status_text"] for k in alle if k["status_text"]})
    vertriebler_werte = sorted({(k["ad_id"], k["ad_name"]) for k in alle if k["ad_id"]},
                               key=lambda x: (x[1] or "").lower())
    von_tag, bis_tag = _tag(von), _tag(bis)
    gefiltert = []
    for k in alle:
        if von_tag and k["tag"] < von_tag:
            continue
        if bis_tag and k["tag"] > bis_tag:
            continue
        if status and k["status_text"] != status:
            continue
        if vertriebler_id and k["ad_id"] != int(vertriebler_id):
            continue
        gefiltert.append(k)
    jetzt = heute if isinstance(heute, datetime) else datetime.now()
    heute_tag = jetzt.date()
    heute_block = [k for k in gefiltert if k["tag"] <= heute_tag]
    heute_block.sort(key=lambda k: (0 if k["tag"] < heute_tag else 1, k["beginn"], k["termin"].id))
    weitere = [k for k in gefiltert if k["tag"] > heute_tag]
    return {"heute": heute_block, "weitere": weitere, "alle": gefiltert,
            "ueberfaellig": sum(1 for k in heute_block if k["ueberfaellig"]),
            "status_werte": status_werte, "vertriebler_werte": vertriebler_werte,
            "anzahl": len(gefiltert), "gesamt": len(alle)}


# --- Heiße Kunden (Phase 163, Darstellung in Mein Tag) --------------------------------------

def _heisse_vorgaenge_rueckfall(session: Session, benutzer_id: int | None) -> list[Vorgang]:
    abfrage = _archiv_filter(session.query(Vorgang).filter(
        or_(Vorgang.verfolgung_ampel == "heiss",
            Vorgang.verfolgung_status == "bestellung_angekuendigt")))
    vorgaenge = abfrage.all()
    if benutzer_id:
        from app import vorgaenge as vorgaenge_modul
        vorgaenge = [v for v in vorgaenge
                     if v.ad_id == benutzer_id or v.wiedervorlage_benutzer_id == benutzer_id
                     or vorgaenge_modul.gehoert_benutzer(session, v, benutzer_id)]
    vorgaenge.sort(key=lambda v: (v.wiedervorlage_am is None, v.wiedervorlage_am or datetime.max, -v.id))
    return vorgaenge


def heisse_kunden(session: Session, benutzer, vertriebler_id: int = 0) -> list[dict]:
    """Karten „Heiße Kunden“: eigene Vorgänge mit Hot-Ampel heiß oder Verfolgungsstatus
    bestellung_angekuendigt (verfolgung.heisse_vorgaenge, Rückfall eigene Abfrage) –
    Kunde, Telefon-Link, Angebots-Kurzinfo, Chip, nächste Wiedervorlage, Akte."""
    benutzer_id = benutzer.id if ist_aussendienst(benutzer) else None
    try:
        from app import verfolgung
        vorgaenge = verfolgung.heisse_vorgaenge(session, benutzer_id=benutzer_id)
    except (ImportError, AttributeError):
        vorgaenge = _heisse_vorgaenge_rueckfall(session, benutzer_id)
    if vertriebler_id:
        vorgaenge = [v for v in vorgaenge if v.ad_id == int(vertriebler_id)
                     or v.wiedervorlage_benutzer_id == int(vertriebler_id)]
    kunden = {k.id: k for k in session.query(Kunde)
              .filter(Kunde.id.in_({v.kunde_id for v in vorgaenge} or {0}))}
    karten = []
    for v in vorgaenge:
        kunde = kunden.get(v.kunde_id)
        if kunde is None:
            continue
        status = v.verfolgung_status or ""
        karten.append({
            "vorgang": v, "kunde": kunde, "name": nachfassen.kundenname(kunde),
            "telefon": (kunde.telefon or "").strip(), "tel_href": nachfassen.tel_href(kunde.telefon),
            "angebot": nachfassen.angebots_kurzinfo(session, v),
            "verfolgung_status": status,
            "chip": VERFOLGUNG_CHIPS.get(status, "heiß"),
            "chip_klasse": "orange" if status == "bestellung_angekuendigt" else "rot",
            "ampel": v.verfolgung_ampel or "",
            "wiedervorlage_am": v.wiedervorlage_am,
            "wiedervorlage_text": v.wiedervorlage_am.strftime("%d.%m.%Y") if v.wiedervorlage_am else "",
            "akte_url": f"/vorgaenge/{v.id}",
            "grosskunde": bool(getattr(kunde, "grosskunde", False)),
        })
    return karten


# --- Dialog „Nächster Schritt“ (Partial von N) ---------------------------------------------

def naechster_schritt_kontext(session: Session, vorgang: Vorgang, ziel: str, heute=None) -> dict:
    """Variablen des Partials templates/vorgaenge/_naechster_schritt.html (Vertrag N:
    verfolgung.dialog_kontext); Rückfall mit denselben Schlüsseln, solange das Modul fehlt."""
    try:
        from app import verfolgung
        return verfolgung.dialog_kontext(session, vorgang, zurueck=ziel, heute=heute)
    except (ImportError, AttributeError):
        pass
    from app import werktage
    from app.models import AblehnungsGrund
    heute_tag = _tag(heute) or date.today()
    tag = werktage.plus_werktage(heute_tag, 3)
    gruende = (session.query(AblehnungsGrund).filter(AblehnungsGrund.aktiv.is_(True))
               .order_by(AblehnungsGrund.sort, AblehnungsGrund.id).all())
    return {"vorgang": vorgang, "gruende": gruende,
            "naechster_3wt": {"datum": tag, "text": f"{WOCHENTAGE[tag.weekday()]} {tag.strftime('%d.%m.')}",
                              "iso": tag.isoformat()},
            "ziel": ziel, "heute_iso": heute_tag.isoformat()}


def partial_vorhanden(name: str = "vorgaenge/_naechster_schritt.html") -> bool:
    """Liegt das Dialog-Partial von N vor? (Rückfall-Knöpfe, solange es fehlt.)"""
    from jinja2 import TemplateNotFound

    from app.templating import templates
    try:
        templates.env.get_template(name)
        return True
    except TemplateNotFound:
        return False
