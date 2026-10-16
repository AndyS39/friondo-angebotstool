# v32 (PLAN_V19 Phase 161): Datenaufbereitung der Vertriebler-Ansicht „Mein Tag“
# (GET /leads, Template templates/leads/mein_tag.html).
# v33 (PLAN_V20 Phase 173, Protokoll Claudia Castro 14.10.2026 Teil A): „Mein Tag“ gilt nur
# noch mobil (Basisrolle Außendienst unter 600 px – CSS-Media-Query, derselbe Datenbestand im
# HTML); der v32-Umschalter „Karten | Tabelle“ und die Einstellung `leads_darstellung`
# entfallen, der Block „Heiße Kunden“ geht im Abschnitt „Wiedervorlage“ auf
# (app/nachfassen.wiedervorlage_liste). Aufbau nach dem Design-Entwurf: Kopf (Datum, Titel,
# Initialen) · Karte „Als Nächstes“ · Liste „Heute“ mit Zeitstrahl · Wiedervorlage ·
# „Kommende Tage“ (14 Tage [ANNAHME]) · untere Leiste.
#
# Quelle der Termine ist ausschließlich vot_termine (Tool-Termine und monday-VOT-Termine):
# - Terminarten vot | telefon | online (Phase 173: „Sparte, Termintyp“ aus vot_termine.typ –
#   vot → „Vor-Ort-Termin“, telefon → „Telefontermin“, online → „Teams“ [ANNAHME]);
#   offene Status geplant | bestaetigt | unbestaetigt [ANNAHME v32]; Status erfolgt bleibt nur
#   am selben Tag (als erledigt) bzw. solange eine Sparte des Objekts offen ist;
# - ohne verknüpftes Angebot am Vorgang (Regel von „Leads VOT“ seit v1);
# - Außendienst: nur eigene Termine – vot_termine.ad_id = Benutzer, Rückfall vorgaenge.ad_id
#   bzw. leads.benutzer_id [ANNAHME]; Innendienst/Admin: alle, Filter Vertriebler;
# - **Erledigt-Logik (Phase 173):** ein Termin ist erledigt, sobald die aus „Erfassung
#   starten“ angelegte Erfassung abgeschlossen ist – Verknüpfung Termin ↔ Erfassung über
#   Vorgang + Objekt (vot_termine.objekt_id ↔ erfassungen.objekt_id, v31) + Sparte: alle
#   Sparten des Objekts sind abgesendet (Status ≠ Entwurf) oder ausgeblendet. Kein Haken,
#   kein manuelles Abhaken. Telefon-/Teams-Termine ohne Erfassung bleiben bis Tagesende offen
#   und fallen am Folgetag aus „Heute“ [ANNAHME].
# v38 (PLAN_V23 Phase 203/204): „überfällig“ entfällt – „Heute“ enthält nur Termine mit Beginn am
#   heutigen Tag; vergangene Vor-Ort-Termine ohne abgeschlossene Erfassung (Erledigt-Logik oben)
#   der letzten VERGANGEN_TAGE (180) Tage stehen in der Gruppe „Vergangene Termine“ der
#   Desktop-Tabelle bzw. auf der mobilen Seite /leads/vergangene (vergangene_tage), neueste
#   zuerst, mit „vor 12 Tagen“; ältere erscheinen nirgends. Telefon-/Teams-Termine bleiben wie
#   v33 außen vor [ANNAHME: ein Vorab-Gespräch erwartet keine Erfassung]. Dazu die Datenbasis
#   der Zeilen „Vergangene Termine“ für die Desktop-Tabelle (vergangene_zeilen) und der Dialog
#   „Termin nicht stattgefunden“ (app/lead_termin_ausfall.py; Knopf an jeder Termin-Karte).
# Reine Datenbankarbeit – kein Netzaufruf (v27-Regel).
from datetime import date, datetime, timedelta
from urllib.parse import quote

from sqlalchemy import and_, or_
from sqlalchemy.orm import Session

from app import nachfassen, objekte
from app import sparten as sparten_modul
from app.models import (AdProfil, Angebot, Benutzer, Erfassung, Kunde, Lead, Vorgang,
                        VorgangObjekt, VotTermin)

OFFENE_STATUS = ("geplant", "bestaetigt", "unbestaetigt")
STATUS_ABFRAGE = OFFENE_STATUS + ("erfolgt",)
TERMIN_TYPEN = ("vot", "telefon", "online")
TYP_NAMEN = {"vot": "Vor-Ort-Termin", "telefon": "Telefontermin", "online": "Teams"}   # [ANNAHME]
WOCHENTAGE = ("Mo", "Di", "Mi", "Do", "Fr", "Sa", "So")
WOCHENTAGE_LANG = ("Montag", "Dienstag", "Mittwoch", "Donnerstag", "Freitag", "Samstag", "Sonntag")
MONATE = ("Januar", "Februar", "März", "April", "Mai", "Juni", "Juli", "August",
          "September", "Oktober", "November", "Dezember")
MAPS_URL = "https://www.google.com/maps/search/?api=1&query="
ROUTE_URL = "https://www.google.com/maps/dir/?api=1&destination={ziel}&travelmode=driving"
KOMMENDE_TAGE = 14            # [ANNAHME] Zeitraum „Kommende Tage“
VERGANGEN_TAGE = 180          # v38 (Phase 203): „Vergangene Termine“ = Beginn vor heute, höchstens 180 Tage zurück
STANDARD_DAUER_MIN = 90       # [ANNAHME] ohne Ende und ohne AD-Profil: Beginn + 90 Minuten
VERFOLGUNG_CHIPS = {"bestellung_angekuendigt": "Bestellung angekündigt"}
# Phase 174 (Vertrag T, Endstand 14.10.2026): der Spaltenkatalog „Leads VOT Desktop“ liegt in
# lead_boards.KATALOGE["leads_vot"]; diese Liste ist das dokumentierte Spiegelbild (T-Test
# test_vertrag_leads_vot_und_kataloge prüft die Gleichheit) und nur noch Dokumentation
BOARD_KEY = "leads_vot"
SPALTEN_RUECKFALL = [
    ("lead", "Kundenname", True), ("termin", "Termin", True),
    ("prioritaet", "Priorität", True), ("sparten", "Sparten", True),
    ("ort", "Ort", True), ("kanal", "Kanal", True),
    ("vertriebler", "Vertriebler", True), ("status", "Status", True),
]
SPALTEN_FEST = ("lead",)
PRIORITAET_TEXTE = {"hoch": "Hoch", "mittel": "Mittel", "niedrig": "Niedrig"}


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


def _jetzt(heute) -> datetime:
    """Bezugszeitpunkt: datetime wie übergeben, ein Datum → 00:00 dieses Tages, sonst jetzt."""
    if isinstance(heute, datetime):
        return heute
    if isinstance(heute, date):
        return datetime(heute.year, heute.month, heute.day)
    return datetime.now()


def datum_text(wert) -> str:
    """„Mo, 13.10.“ – Wochentag kurz, Tag und Monat."""
    tag = _tag(wert)
    if tag is None:
        return ""
    return f"{WOCHENTAGE[tag.weekday()]}, {tag.strftime('%d.%m.')}"


def datum_lang(wert) -> str:
    """„Mittwoch, 14. Oktober“ – Wochentag und Monat ausgeschrieben (Kopf, Gruppen)."""
    tag = _tag(wert)
    if tag is None:
        return ""
    return f"{WOCHENTAGE_LANG[tag.weekday()]}, {tag.day}. {MONATE[tag.month - 1]}"


def wochentag_kurz(wert) -> str:
    """„DO“ – Datumskachel der kommenden Tage (zweibuchstabig, Versalien)."""
    tag = _tag(wert)
    return WOCHENTAGE[tag.weekday()].upper() if tag is not None else ""


def uhr_text(wert) -> str:
    return f"{wert.strftime('%H:%M')} Uhr" if isinstance(wert, datetime) else ""


def uhr_kurz(wert) -> str:
    return wert.strftime("%H:%M") if isinstance(wert, datetime) else ""


def minuten_text(beginn: datetime, jetzt: datetime) -> str:
    """Hinweis der Karte „Als Nächstes“: „in 25 Min“ (Minuten bis Beginn), ab einer Stunde
    „in 1 Std 15 Min“, nach dem Beginn „jetzt“."""
    if beginn <= jetzt:
        return "jetzt"
    minuten = int((beginn - jetzt).total_seconds() // 60)
    if minuten < 1:
        return "jetzt"
    if minuten < 60:
        return f"in {minuten} Min"
    stunden, rest = divmod(minuten, 60)
    return f"in {stunden} Std" + (f" {rest} Min" if rest else "")


def tage_text_termine(anzahl: int) -> str:
    return f"{anzahl} Termin{'e' if anzahl != 1 else ''}"


def vor_text(wert, heute=None) -> str:
    """v38 (Phase 203): „vor 12 Tagen“ – Zusatz der Termin-Spalte in „Vergangene Termine“
    („gestern“ für einen Tag, „heute“ am selben Tag)."""
    tag = _tag(wert)
    if tag is None:
        return ""
    heute_tag = _jetzt(heute).date()
    tage = (heute_tag - tag).days
    if tage <= 0:
        return "heute"
    if tage == 1:
        return "gestern"
    return f"vor {tage} Tagen"


def maps_url(ort: dict) -> str:
    """Google-Maps-Suche mit URL-kodierter Adresse (neuer Tab im Template)."""
    adresse = ort.get("einzeilig") or ""
    return MAPS_URL + quote(adresse, safe="") if adresse else ""


def route_url(ort: dict) -> str:
    """„Route starten“ (Phase 173): Google-Maps-Routenplaner mit der Anschrift als Ziel
    (Start = Standort des Geräts; der v29-Routenplaner des Lead-Dashboards nutzt dieselbe
    dir-API mit festem Start)."""
    adresse = ort.get("einzeilig") or ""
    return ROUTE_URL.format(ziel=quote(adresse, safe="")) if adresse else ""


def herkunft(termin: VotTermin) -> str:
    """Herkunfts-Badge „monday“ oder „Tool“ (Assistent/manuell) [ANNAHME]."""
    return "monday" if (termin.quelle or "") == "monday" else "Tool"


def typ_name(termin: VotTermin) -> str:
    return TYP_NAMEN.get((termin.typ or "vot").strip(), TYP_NAMEN["vot"])


def effektiver_ad(termin: VotTermin, vorgang: Vorgang, lead: Lead | None) -> int | None:
    """Vertriebler des Termins: vot_termine.ad_id, sonst vorgaenge.ad_id, sonst der
    Vertriebler des monday-Leads [ANNAHME]."""
    return termin.ad_id or getattr(vorgang, "ad_id", None) or (lead.benutzer_id if lead else None)


def ist_aussendienst(benutzer) -> bool:
    """v33: Basisrolle (gilt auch für die Variante Handelsvertreter)."""
    if benutzer is None:
        return False
    basis = getattr(benutzer, "basisrolle", None)
    if basis is None:
        basis = getattr(benutzer, "rolle", "")
    return basis == "aussendienst"


def initialen(benutzer) -> str:
    """Zwei Buchstaben aus Vor- und Nachname (Kopf-Kreis); ohne Vorname die ersten beiden
    Namensteile bzw. Buchstaben des Namens."""
    vorname = (getattr(benutzer, "vorname", "") or "").strip()
    name = (getattr(benutzer, "name", "") or "").strip()
    teile = [t for t in name.replace("-", " ").split() if t]
    if vorname and teile:
        return (vorname[:1] + teile[-1][:1]).upper()
    if len(teile) >= 2:
        return (teile[0][:1] + teile[-1][:1]).upper()
    return (name[:2] or "?").upper()


def _archiv_filter(abfrage):
    try:   # v31 (Phase 154): Archiv ist eine Lead-Sicht
        from app import lead_archiv
        return lead_archiv.filter_aktiv(abfrage)
    except (ImportError, AttributeError):
        return abfrage


def _chips(lead: Lead | None, sparten: list[str], erfasst: set[str]) -> list[tuple[str, str]]:
    """Status-Chips je Sparte wie in Leads VOT (v8): erfasst | ausgeblendet | offen."""
    if lead is not None:
        # wie routers.leads.sparten_chips (v8), aber für eine beliebige Sparten-Liste
        # (Phase 173: Sparten des Termin-Objekts statt der Lead-Interessen)
        ausgeblendet = set(lead.ausgeblendete_sparten)
        return [(s, "erfasst" if s in erfasst else ("ausgeblendet" if s in ausgeblendet else "offen"))
                for s in sparten]
    return [(s, "erfasst" if s in erfasst else "offen") for s in sparten]


def erfassen_url(vorgang: Vorgang, lead: Lead | None, kunde: Kunde, objekt_id) -> str:
    """Startweiche der Erfassung mit Kunde und Objekt (v31): Lead-Vorgänge über
    /leads/{lead}/erfassen (Lead ↔ Erfassung bleibt verknüpft), sonst die Sparten-Auswahl."""
    if lead is not None:
        url = f"/leads/{lead.id}/erfassen"
        return url + (f"?objekt_id={int(objekt_id)}" if objekt_id else "")
    url = f"/erfassung/sparten?kunde_id={kunde.id}"
    return url + (f"&objekt_id={int(objekt_id)}" if objekt_id else "")


def sparten_text(sparten: list[str]) -> str:
    """„Wärmepumpe und Photovoltaik“ (Langform aus app/sparten.py)."""
    try:
        return sparten_modul.sparten_text(sparten) or ", ".join(sparten)
    except Exception:   # noqa: BLE001 – die Karte darf daran nie scheitern
        return ", ".join(sparten)


def _objekt_sparten(objekt: VorgangObjekt | None, haupt_sparten: list[str]) -> list[str]:
    """Sparten des Termin-Objekts: Objekt 2 ff. tragen eigene Interessen (v31), das
    Hauptobjekt die des Leads/Vorgangs."""
    if objekt is None or (objekt.reihenfolge or 1) == 1:
        return haupt_sparten
    try:
        eigene = sparten_modul.erfassungs_codes(objekt.interessen)   # v37: ohne Merkmal PVV
    except Exception:   # noqa: BLE001
        eigene = []
    return eigene or haupt_sparten


# --- Termine ---------------------------------------------------------------------------

def termin_karten(session: Session, benutzer, heute=None) -> list[dict]:
    """Alle sichtbaren Termin-Karten des Benutzers (ungefiltert, chronologisch): heutige und
    künftige Termine sowie – v38 (Phase 203) – vergangene Vor-Ort-Termine ohne abgeschlossene
    Erfassung der letzten VERGANGEN_TAGE Tage (Schlüssel `vergangen`, `vor_text`)."""
    jetzt = _jetzt(heute)
    heute_tag = jetzt.date()
    aussendienst = ist_aussendienst(benutzer)
    # v38: ältere Termine als 180 Tage erscheinen nirgends – die Abfrage endet dort
    ab = datetime.combine(heute_tag - timedelta(days=VERGANGEN_TAGE), datetime.min.time())
    abfrage = (session.query(VotTermin, Vorgang)
               .join(Vorgang, Vorgang.id == VotTermin.vorgang_id)
               .outerjoin(Lead, Lead.id == Vorgang.lead_id)
               .filter(VotTermin.typ.in_(TERMIN_TYPEN), VotTermin.beginn.isnot(None),
                       VotTermin.beginn >= ab,
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
    objekte_map: dict[int, VorgangObjekt] = {}
    haupt_map: dict[int, VorgangObjekt] = {}
    for o in (session.query(VorgangObjekt)
              .filter(VorgangObjekt.vorgang_id.in_(vorgang_ids), VorgangObjekt.aktiv.is_(True))):
        objekte_map[o.id] = o
        if (o.reihenfolge or 1) == 1 and o.vorgang_id not in haupt_map:
            haupt_map[o.vorgang_id] = o
    # abgesendete Erfassungen je Vorgang und je Objekt (Entwürfe zählen nicht)
    erfasst: dict[int, set[str]] = {}
    erfasst_objekt: dict[tuple[int, int | None], set[str]] = {}
    erfassungen_objekt: dict[tuple[int, int | None], list[Erfassung]] = {}
    for e in (session.query(Erfassung)
              .filter(Erfassung.vorgang_id.in_(vorgang_ids), Erfassung.status != "Entwurf")
              .order_by(Erfassung.abgesendet_am.desc().nullslast(), Erfassung.id.desc())):
        sparte = e.sparte or "WP"
        erfasst.setdefault(e.vorgang_id, set()).add(sparte)
        haupt = haupt_map.get(e.vorgang_id)
        schluessel = (e.vorgang_id, e.objekt_id or (haupt.id if haupt else None))
        erfasst_objekt.setdefault(schluessel, set()).add(sparte)
        erfassungen_objekt.setdefault(schluessel, []).append(e)
    benutzer_map = {b.id: b for b in session.query(Benutzer)}
    dauer_profil = {p.benutzer_id: p.termin_dauer_min for p in session.query(AdProfil)}
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
        # v37 (PLAN_LEAD_V7 Phase 199, Agent L3): Merkmale (PVV „PV vorhanden“) sind keine
        # Erfassungs-Sparte – weder Chip noch Erledigt-Logik (Lead.sparten filtert sie selbst)
        sparten = (lead.sparten if lead is not None
                   else (sparten_modul.erfassungs_codes(objekte.vorgang_interessen(session, vorgang.id))
                         or sparten_modul.erfassungs_codes(kunde.interessen) or ["WP"]))
        erfasst_set = erfasst.get(vorgang.id, set())
        chips = _chips(lead, sparten, erfasst_set)
        offen_vorgang = any(status == "offen" for _, status in chips)
        # Erledigt je Objekt (Phase 173): Sparten des Termin-Objekts gegen die Erfassungen
        # desselben Objekts; Termine ohne objekt_id zählen zum Hauptobjekt
        haupt = haupt_map.get(vorgang.id)
        objekt = objekte_map.get(termin.objekt_id) if termin.objekt_id else haupt
        objekt_schluessel = (vorgang.id, objekt.id if objekt is not None else None)
        sparten_objekt = _objekt_sparten(objekt, sparten)
        erfasst_obj = erfasst_objekt.get(objekt_schluessel, set())
        chips_objekt = _chips(lead, sparten_objekt, erfasst_obj)
        offen_objekt = any(status == "offen" for _, status in chips_objekt)
        erledigt = bool(sparten_objekt) and not offen_objekt
        tag = termin.beginn.date()
        vergangen = tag < heute_tag
        if termin.status == "erfolgt" and not offen_vorgang and (vergangen or not erledigt):
            continue   # Erfassung vollständig und nicht mehr heute – der Termin ist durch
        # v38 (Phase 203): vergangene Termine zählen nur als „Vergangene Termine“ – Vor-Ort-
        # Termine ohne abgeschlossene Erfassung des Termin-Objekts (Erledigt-Logik); erledigte
        # und Telefon-/Teams-Termine fallen am Folgetag heraus [ANNAHME]; kein „überfällig“ mehr
        if vergangen and (erledigt or termin.typ != "vot"):
            continue
        teilweise = vergangen and bool(erfasst_obj) and not erledigt
        ort = objekte.ausfuehrungsort(session, termin=termin, vorgang=vorgang, kunde=kunde)
        objekt_id = ort.get("objekt_id") or termin.objekt_id
        ad = benutzer_map.get(ad_id) if ad_id else None
        telefon = (kunde.telefon or "").strip() or (lead.telefon if lead else "") or ""
        dauer = dauer_profil.get(ad_id) or STANDARD_DAUER_MIN
        ende = termin.ende or (termin.beginn + timedelta(minutes=int(dauer)))
        letzte = (erfassungen_objekt.get(objekt_schluessel) or [None])[0]
        typ = (termin.typ or "vot").strip()
        karten.append({
            "termin": termin, "vorgang": vorgang, "kunde": kunde, "lead": lead,
            "tag": tag, "beginn": termin.beginn, "ende": ende,
            "datum_text": datum_text(termin.beginn), "uhr_text": uhr_text(termin.beginn),
            "uhr": uhr_kurz(termin.beginn), "ende_uhr": uhr_kurz(ende),
            "name": nachfassen.kundenname(kunde),
            "ort": ort, "adresse": ort.get("einzeilig") or "",
            "strasse": ort.get("strasse") or "", "plz_ort": " ".join(
                x for x in (ort.get("plz") or "", ort.get("ort") or "") if x),
            "ort_text": (ort.get("ort") or "").strip() or (ort.get("plz") or ""),
            "objekt_bezeichnung": (ort.get("bezeichnung") or "") if ort.get("mehrere_objekte") else "",
            "objekt_id": objekt_id, "maps_url": maps_url(ort), "route_url": route_url(ort),
            "telefon": telefon, "tel_href": nachfassen.tel_href(telefon),
            "sparten": sparten, "chips": chips, "sparten_objekt": sparten_objekt,
            "sparten_text": sparten_text(sparten_objekt),
            "typ": typ, "typ_name": typ_name(termin),
            "beschreibung": ", ".join(t for t in (sparten_text(sparten_objekt), typ_name(termin)) if t),
            "herkunft": herkunft(termin), "status": termin.status,
            "status_text": (lead.status_text if lead else "") or "",
            "ad_id": ad_id, "ad": ad, "ad_name": ad.name if ad else "",
            "teilweise": teilweise, "heute": tag == heute_tag,
            "vergangen": vergangen, "vor_text": vor_text(tag, heute_tag) if vergangen else "",
            "erledigt": erledigt,
            # v38 (Phase 204): Dialog „Termin nicht stattgefunden“ an jeder nicht erledigten Karte
            "ausfall": not erledigt and termin.status in OFFENE_STATUS,
            "ausfall_url": f"/leads/termin/{termin.id}/ausgefallen",
            "ausfall_zeit": f"{datum_text(termin.beginn)} · {uhr_kurz(termin.beginn)} Uhr",
            "erfassung": letzte,
            "erfassung_url": (f"/erfassung/{letzte.id}/pruefen" if letzte is not None
                              else f"/vorgaenge/{vorgang.id}"),
            "erfassen_url": erfassen_url(vorgang, lead, kunde, objekt_id),
            "akte_url": f"/vorgaenge/{vorgang.id}",
            "grosskunde": bool(getattr(kunde, "grosskunde", False)),
            "kanal": (lead.vertriebskanal if lead else "") or kunde.vertriebskanal or "",
            "ampel": vorgang.verfolgung_ampel or "",
        })
    return karten


# --- v37 (PLAN_LEAD_V7 Phase 198, Agent L2): Strecke in Kilometern je Termin des Tages ---------

STRECKE_VON_START = "von der Startadresse"


def _termin_ort(karte: dict) -> tuple | None:
    """Koordinaten des Termins: vot_termine.lat/lon, sonst Objekt (v31), sonst Vorgang."""
    t = karte["termin"]
    if t.lat is not None and t.lon is not None:
        return (t.lat, t.lon)
    v = karte["vorgang"]
    if v.lat is not None and v.lon is not None:
        return (v.lat, v.lon)
    return None


def _startpunkt(session: Session, ad_id, benutzer) -> tuple | None:
    """Startpunkt des Tages: Startadresse des AD-Profils (start_lat/start_lon), sonst der
    Parameter routen_start (Firmensitz) über den Geocode-Cache [ANNAHME]."""
    kandidaten = [i for i in (ad_id, getattr(benutzer, "id", None)) if i]
    for nr in kandidaten:
        profil = session.query(AdProfil).filter(AdProfil.benutzer_id == int(nr)).first()
        if profil is not None and profil.start_lat is not None and profil.start_lon is not None:
            return (profil.start_lat, profil.start_lon)
    try:
        from app import geocoding, lead_dashboard
        adresse = lead_dashboard.routen_start(session)
        if adresse:
            lat, lon, status = geocoding.geokodieren(session, adresse)
            if lat is not None and lon is not None:
                return (lat, lon)
    except Exception:   # noqa: BLE001 – die Karte darf daran nie scheitern
        pass
    return None


def strecken_ergaenzen(session: Session, karten: list[dict], benutzer, heute=None) -> None:
    """Strecke (Straßenkilometer und Fahrzeit) für die Termine des heutigen Tages: vom
    Vortermin des Tages (gleicher Vertriebler), beim ersten Termin von der Startadresse.
    EIN gebündelter Matrix-Aufruf über routing.matrix_fuellen (gibt die Sitzung vor dem
    Netzaufruf frei; ohne Key/Anbieter kein Netz), danach je Paar aus dem Cache
    (routing.strecke → „18,4 km · 24 Min“ bzw. „ca. 24 km · 31 Min (geschätzt)“).
    Setzt je Karte strecke (dict), strecke_text, strecke_von (Text), strecke_geschaetzt."""
    from app import routing
    heute_tag = _jetzt(heute).date()
    tages = sorted((k for k in karten if k.get("tag") == heute_tag),
                   key=lambda k: (k["beginn"], k["termin"].id))
    for k in karten:
        k.setdefault("strecke", None)
        k.setdefault("strecke_text", "")
        k.setdefault("strecke_von", "")
        k.setdefault("strecke_geschaetzt", False)
    if not tages:
        return
    paare = []
    starts: dict = {}
    vorher: dict = {}
    for k in tages:
        ziel = _termin_ort(k)
        if ziel is None:
            continue
        ad_id = k.get("ad_id")
        von = vorher.get(ad_id)
        von_text = ""
        if von is not None:
            von_text = f"vom Termin {von[1]}"
            von = von[0]
        else:
            if ad_id not in starts:
                starts[ad_id] = _startpunkt(session, ad_id, benutzer)
            von = starts[ad_id]
            von_text = STRECKE_VON_START if von is not None else ""
        if von is not None and von != ziel:
            paare.append((k, von, ziel, von_text))
        vorher[ad_id] = (ziel, k.get("uhr") or uhr_kurz(k["beginn"]))
    if not paare:
        return
    quellen = list(dict.fromkeys(p[1] for p in paare))
    ziele = list(dict.fromkeys(p[2] for p in paare))
    routing.matrix_fuellen(session, quellen, ziele)
    for k, von, ziel, von_text in paare:
        ergebnis = routing.strecke(session, von, ziel)
        k["strecke"] = ergebnis
        k["strecke_text"] = ergebnis.get("text", "")
        k["strecke_von"] = von_text
        k["strecke_geschaetzt"] = bool(ergebnis.get("geschaetzt"))


def naechster_termin(heute_karten: list[dict], jetzt: datetime) -> dict | None:
    """Karte „Als Nächstes“: der nächste noch nicht erledigte Termin des Tages – der erste,
    dessen Ende noch nicht erreicht ist (vor dem Beginn „in n Min“, danach „jetzt“); ohne
    Termin heute (oder alle vorbei/erledigt) keine Karte [ANNAHME: Ende = termin.ende bzw.
    Beginn + Dauer des AD-Profils]."""
    for k in sorted((k for k in heute_karten if k["heute"] and not k["erledigt"]),
                    key=lambda k: (k["beginn"], k["termin"].id)):
        if k["ende"] > jetzt:
            return k
    return None


def kommende_tage(karten: list[dict], heute_tag: date, tage: int = KOMMENDE_TAGE) -> list[dict]:
    """Abschnitt „Kommende Tage“: Termine ab morgen bis heute + `tage`, gruppiert je Tag
    (Datumskachel „DO“ + „15“, Überschrift „Donnerstag, 15. Oktober“, Zähler)."""
    grenze = heute_tag + timedelta(days=tage)
    gruppen: dict[date, list[dict]] = {}
    for k in karten:
        if heute_tag < k["tag"] <= grenze:
            gruppen.setdefault(k["tag"], []).append(k)
    ergebnis = []
    for tag in sorted(gruppen):
        eintraege = sorted(gruppen[tag], key=lambda k: (k["beginn"], k["termin"].id))
        ergebnis.append({"tag": tag, "iso": tag.isoformat(), "wochentag": wochentag_kurz(tag),
                         "tag_nr": str(tag.day), "titel": datum_lang(tag),
                         "zaehler": tage_text_termine(len(eintraege)), "termine": eintraege})
    return ergebnis


def termine(session: Session, benutzer, von=None, bis=None, status: str = "",
            vertriebler_id: int = 0, heute=None) -> dict:
    """Termin-Blöcke mit Filtern (Termin von/bis, Status = monday-Statustext, Vertriebler
    bei ID/Admin): heute (nur der heutige Tag, chronologisch – v38: ohne überfällige),
    naechster (Karte „Als Nächstes“), kommende (14 Tage je Tag), weitere (alle ab morgen),
    spaeter (Anzahl jenseits der 14 Tage), vergangene (v38: vergangene Vor-Ort-Termine ohne
    abgeschlossene Erfassung, neueste zuerst) + vergangene_tage (je Tag gruppiert); dazu die
    Auswahlwerte der Filter."""
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
    jetzt = _jetzt(heute)
    heute_tag = jetzt.date()
    # v38 (Phase 203): „Heute“ enthält nur Termine mit Beginn am heutigen Tag
    heute_block = [k for k in gefiltert if k["tag"] == heute_tag]
    heute_block.sort(key=lambda k: (k["beginn"], k["termin"].id))
    # v37 (Phase 198): Strecke in km für die heutigen Termine (Vortermin bzw. Startadresse)
    try:
        strecken_ergaenzen(session, heute_block, benutzer, jetzt)
    except Exception:   # noqa: BLE001 – Mein Tag darf an der Strecke nie scheitern
        for k in heute_block:
            k.setdefault("strecke_text", "")
            k.setdefault("strecke_von", "")
    naechster = naechster_termin(heute_block, jetzt)
    for k in heute_block:
        k["naechster"] = naechster is not None and k["termin"].id == naechster["termin"].id
    if naechster is not None:
        naechster["hinweis"] = minuten_text(naechster["beginn"], jetzt)
    weitere = [k for k in gefiltert if k["tag"] > heute_tag]
    kommende = kommende_tage(gefiltert, heute_tag)
    grenze = heute_tag + timedelta(days=KOMMENDE_TAGE)
    vergangene = vergangene_karten(gefiltert, heute_tag)
    return {"heute": heute_block, "heute_nur": heute_block,
            "weitere": weitere, "alle": gefiltert,
            "naechster": naechster, "kommende": kommende,
            "spaeter": sum(1 for k in weitere if k["tag"] > grenze), "grenze": grenze,
            "vergangene": vergangene, "vergangene_tage": vergangene_tage(vergangene, heute_tag),
            "vergangene_anzahl": len(vergangene),
            "status_werte": status_werte, "vertriebler_werte": vertriebler_werte,
            "anzahl": len(gefiltert), "gesamt": len(alle)}


# --- v38 (PLAN_V23 Phase 203/204): Vergangene Termine ------------------------------------

def vergangene_karten(karten: list[dict], heute_tag: date) -> list[dict]:
    """Vergangene Vor-Ort-Termine ohne abgeschlossene Erfassung (Beginn vor heute, höchstens
    VERGANGEN_TAGE Tage zurück – die Abfrage in termin_karten endet dort), neueste zuerst."""
    grenze = heute_tag - timedelta(days=VERGANGEN_TAGE)
    liste = [k for k in karten if k.get("vergangen") and grenze <= k["tag"] < heute_tag]
    liste.sort(key=lambda k: (k["beginn"], k["termin"].id), reverse=True)
    return liste


def vergangene_tage(karten: list[dict], heute_tag: date) -> list[dict]:
    """Seite „Vergangene Termine“ (mobil): Gruppen je Tag mit Datumskachel wie „Kommende
    Tage“, neueste zuerst, innerhalb des Tages nach Uhrzeit."""
    gruppen: dict[date, list[dict]] = {}
    for k in karten:
        gruppen.setdefault(k["tag"], []).append(k)
    ergebnis = []
    for tag in sorted(gruppen, reverse=True):
        eintraege = sorted(gruppen[tag], key=lambda k: (k["beginn"], k["termin"].id))
        ergebnis.append({"tag": tag, "iso": tag.isoformat(), "wochentag": wochentag_kurz(tag),
                         "tag_nr": str(tag.day), "titel": datum_lang(tag),
                         "vor_text": vor_text(tag, heute_tag),
                         "zaehler": tage_text_termine(len(eintraege)), "termine": eintraege})
    return ergebnis


def vergangene_zeilen(session: Session, benutzer, heute=None) -> list[dict]:
    """Zeilen der Desktop-Gruppe „Vergangene Termine“ (Phase 203) – dieselbe Datenbasis wie
    die mobile Seite (termin_karten → vergangene_karten), in der Form der Lead-Zeilen von
    routers.leads._tabelle_kontext (Kundenname, Termin, Priorität, Sparten/Chips, Ort, Kanal,
    Vertriebler, Status); `lead` ist bei Tool-Terminen ohne monday-Lead None."""
    jetzt = _jetzt(heute)
    zeilen = []
    for k in vergangene_karten(termin_karten(session, benutzer, jetzt), jetzt.date()):
        lead, vorgang, kunde, termin = k["lead"], k["vorgang"], k["kunde"], k["termin"]
        prio = prioritaet_von(k["ampel"])
        zeilen.append({
            "id": f"termin-{termin.id}", "zeilen_id": f"termin-{termin.id}", "termin_id": termin.id,
            "lead": lead, "vorgang": vorgang, "kunde": kunde, "karte": k,
            "termin": termin.beginn, "termin_text": termin.beginn.strftime("%d.%m.%Y %H:%M"),
            "uhr": k["uhr"], "vergangen": True, "vor_text": k["vor_text"],
            "name": k["name"], "ort": k["plz_ort"] or k["ort_text"],
            "kanal": k["kanal"], "vertriebler": k["ad_name"], "vertriebler_id": k["ad_id"],
            "status": k["status_text"], "prioritaet": prio,
            "prioritaet_text": PRIORITAET_TEXTE[prio], "ampel": k["ampel"],
            "sparten": list(k["sparten"]), "chips": k["chips"], "grosskunde": k["grosskunde"],
            "teilweise": k["teilweise"], "telefon": k["telefon"],
            "erfassen_url": k["erfassen_url"], "akte_url": k["akte_url"],
            "ausfall": k["ausfall"], "ausfall_url": k["ausfall_url"], "ausfall_zeit": k["ausfall_zeit"],
        })
    return zeilen


# --- Leads VOT Desktop: Gruppen und Spalten (Phase 174, Vertrag T) -------------------------

GRUPPE_VERGANGEN = "vergangen"
GRUPPE_VERGANGEN_TITEL = "Vergangene Termine"
GRUPPE_VERGANGEN_ERKL = f"ohne Erfassung · letzte {VERGANGEN_TAGE} Tage"


def _zeilen_id(z: dict):
    return z.get("zeilen_id") or z.get("id") or 0


def gruppen_bilden(zeilen: list[dict], heute=None) -> list[dict]:
    """Zeilen der Desktop-Tabelle in Gruppen: „Heute“ und je ein Block pro Folgetag
    („Donnerstag, 15. Oktober · 2 Termine“); innerhalb der Gruppe nach Uhrzeit. Eine Zeile
    braucht `termin` (datetime|None); ohne Termin → Gruppe „Ohne Termin“. v38 (Phase 203):
    die Gruppe „Überfällig“ entfällt – Zeilen mit Termin vor heute landen in der Gruppe
    „Vergangene Termine“ (Schlüssel GRUPPE_VERGANGEN, unten, standardmäßig zugeklappt,
    neueste zuerst); routers.leads füllt sie aus vot_termine (vergangene_zeilen)."""
    heute_tag = _jetzt(heute).date()
    sammel: dict[str, list[dict]] = {}
    for z in zeilen:
        termin = z.get("termin")
        tag = _tag(termin)
        if tag is None:
            key = "ohne"
        elif tag < heute_tag:
            key = GRUPPE_VERGANGEN
        elif tag == heute_tag:
            key = "heute"
        else:
            key = tag.isoformat()
        sammel.setdefault(key, []).append(z)
    gruppen = []
    for key in sorted(sammel, key=lambda k: {"heute": "1", "ohne": "8", GRUPPE_VERGANGEN: "9"}.get(k, "2" + k)):
        if key == GRUPPE_VERGANGEN:
            eintraege = sorted(sammel[key], key=lambda z: (z.get("termin") or datetime.min, str(_zeilen_id(z))),
                               reverse=True)
            gruppen.append(vergangene_gruppe(eintraege))
            continue
        eintraege = sorted(sammel[key], key=lambda z: (z.get("termin") or datetime.max, str(_zeilen_id(z))))
        if key == "heute":
            titel, erkl = "Heute", datum_lang(heute_tag)
        elif key == "ohne":
            titel, erkl = "Ohne Termin", ""
        else:
            titel, erkl = datum_lang(key), ""
        gruppen.append({"key": key, "titel": titel, "erkl": erkl,
                        "zaehler": tage_text_termine(len(eintraege)), "zeilen": eintraege,
                        "rot": False, "vergangen": False, "zu": False})
    return gruppen


def vergangene_gruppe(zeilen: list[dict]) -> dict:
    """Gruppe „Vergangene Termine · n“ der Desktop-Tabelle (Phase 203): unten, zugeklappt,
    Zustand je Benutzer in localStorage (mein_tag.js), Termin-Spalte gedämpft mit „vor n Tagen“."""
    return {"key": GRUPPE_VERGANGEN, "titel": GRUPPE_VERGANGEN_TITEL, "erkl": GRUPPE_VERGANGEN_ERKL,
            "zaehler": tage_text_termine(len(zeilen)), "zeilen": zeilen,
            "rot": False, "vergangen": True, "zu": True}


def gruppen_mit_vergangenen(gruppen: list[dict], vergangene: list[dict]) -> list[dict]:
    """Zeilen aus vot_termine (vergangene_zeilen) in die Gruppe „Vergangene Termine“ legen –
    sie ersetzt eine vorhandene Lead-basierte Vergangen-Gruppe; Lead-Zeilen bleiben nur, wenn
    ihr Vorgang keinen Termin in vot_termine kennt (Altbestand vor v32 [ANNAHME]), Dubletten je
    Vorgang entfallen; die Gruppe steht immer zuletzt und fehlt bei null Zeilen."""
    rest = [g for g in gruppen if g["key"] != GRUPPE_VERGANGEN]
    alt = next((g for g in gruppen if g["key"] == GRUPPE_VERGANGEN), None)
    zeilen = list(vergangene)
    bekannt = {z["vorgang"].id for z in zeilen if z.get("vorgang") is not None}
    for z in (alt["zeilen"] if alt else []):
        vorgang = z.get("vorgang")
        if vorgang is not None and (vorgang.id in bekannt or z.get("termin_bekannt")):
            continue
        zeilen.append(z)
    zeilen.sort(key=lambda z: (z.get("termin") or datetime.min, str(_zeilen_id(z))), reverse=True)
    if zeilen:
        rest.append(vergangene_gruppe(zeilen))
    return rest


def spalten_fuer(session: Session, benutzer) -> list[dict]:
    """Spalten je Nutzer für die Tabelle „Leads VOT“ (Vertrag T: lead_boards.spalten_fuer mit
    Board-Key leads_vot – Rollen-Katalog, feste Spalte Kundenname vorn)."""
    from app import lead_boards
    return lead_boards.spalten_fuer(session, benutzer, BOARD_KEY)


def sortierung_fuer(session: Session, benutzer) -> dict | None:
    """Gemerkte Spaltensortierung {key, richtung} des Nutzers (Vertrag T), sonst None."""
    from app import lead_boards
    return lead_boards.sortierung_fuer(session, benutzer, BOARD_KEY)


def spalten_fest() -> tuple:
    """Feste Spalten der Tabelle (immer sichtbar, vorn, kein Ablageziel) – Vertrag T."""
    from app import lead_boards
    return lead_boards.spalten_fest(BOARD_KEY)


def _sortier_wert(z: dict, key: str):
    """Sortierwert einer Zeile für lead_boards.zeilen_sortieren(wert=…): None = leer (ans Ende)."""
    wert = z.get(key)
    if key == "lead":
        wert = (z.get("name") or "").lower()
    elif key == "termin":
        wert = z.get("termin")
    elif key == "prioritaet":
        wert = {"hoch": 0, "mittel": 1, "niedrig": 2}.get(z.get("prioritaet") or "", None)
    elif key == "sparten":
        wert = ",".join(z.get("sparten") or []) or None
    elif isinstance(wert, str):
        wert = wert.lower() or None
    return wert


def gruppen_sortieren(gruppen: list[dict], sort: dict | None) -> list[dict]:
    """Spaltensortierung innerhalb der Gruppen über lead_boards.zeilen_sortieren (Vertrag T:
    leere Werte ans Ende; ohne Sortierung bleibt die Uhrzeit-Reihenfolge erhalten)."""
    from app import lead_boards
    for g in gruppen:
        lead_boards.zeilen_sortieren(g["zeilen"], sort, wert=_sortier_wert)
    return gruppen


def prioritaet_von(ampel: str) -> str:
    """Priorität = Hot-Ampel (Protokoll A.1): heiß → hoch, warm → mittel, kalt → niedrig;
    ohne Einstufung → niedrig [ANNAHME]."""
    return {"heiss": "hoch", "warm": "mittel", "kalt": "niedrig"}.get((ampel or "").strip(), "niedrig")


# --- Dialog „Nächster Schritt“ (Partial von N) ---------------------------------------------

def naechster_schritt_kontext(session: Session, vorgang: Vorgang, ziel: str, heute=None,
                              benutzer=None) -> dict:
    """Variablen des Partials templates/vorgaenge/_naechster_schritt.html (Vertrag N:
    verfolgung.dialog_kontext); Rückfall mit denselben Schlüsseln, solange das Modul fehlt."""
    try:
        from app import verfolgung
        # v33 (Phase 176, N 4b): Absender der Nachfass-Mail = angemeldeter Benutzer (sonst AD des Vorgangs)
        return verfolgung.dialog_kontext(session, vorgang, zurueck=ziel, heute=heute, benutzer=benutzer)
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
