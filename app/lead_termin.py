# Lead-Management V2 (v23, PLAN_LEAD_V2 Phase 108): Terminassistent V2 und
# Routenplaner. Kandidatenfilter (E2: Ausschluss = Kanal-Regel, Produkt-
# kompetenz, Tageskapazität, Arbeitszeit; Abwertung = Gebiet, Fahrzeit,
# Wunschzeit), eigene Vorschlagsfunktion mit Puffer = max(puffer_min,
# Fahrzeit) (F4, A-13), Konfliktprüfung für manuelle Buchung (B7), Vertrag
# „vorgemerkt“ (B8, Phase 106 löst ein), Vorab-Gespräche Telefon/Teams
# (H6/F12), Absage mit Storno-ICS und Ersatzkunden-Suche (E3/F8),
# Terminbestätigung erneut (A-9). Baut auf den Bausteinen des V1-Kerns
# (kern.ad_profil, kern._arbeitszeiten_von_bis, kalender.frei_belegt,
# routing.fahrzeit) auf, ohne kern.termin_vorschlaege zu verändern.
# v29 (PLAN_LEAD_V4 Phase 143): genau `vorschlaege_anzahl` Vorschläge (Standard 3),
# der erste als „Ideal“ mit Begründung in Klartext; Kalenderansicht der in Frage
# kommenden Vertriebler als JSON (kalender_json: Mo–Sa, 15-Minuten-Raster,
# Arbeitszeiten der AD-Profile, Tool-Termine, Outlook-Belegt nur bei
# kalender_sync = an und nie für Handelsvertreter, Cache 10 Minuten je Lead und
# Woche); Sperrzeiten der Handelsvertreter (VotTermin typ „sperrzeit“, nur
# Tool-Kalender, Zwischenlösung bis [OFFEN 3]); „Weitere Kalender“ je Nutzer
# (benutzer_einstellungen Key assistent_kalender).
# Nachtrag 08.10.2026 (Antwort Andreas): Sperrzeiten zählen in der Kollision exakt
# von–bis (kein Mindest-/Fahrzeitpuffer, _slot_frei/konflikte); Admin/Innendienst
# dürfen Sperrzeiten eines Handelsvertreters eintragen (sperrzeit_anlegen(…, ziel),
# sperrzeit_fremd_erlaubt, sperrzeiten_uebersicht für die HV-Übersicht).
# v31 (PLAN_LEAD_V5 Phase 153/158/159):
#  - Termine je Objekt: Vorschläge, Kandidatenfilter (PLZ/Sparten/Objektart) und
#    Fahrzeiten rechnen mit der Adresse des gewählten Objekts (objekte.ausfuehrungsort,
#    Geocoding je Objekt); vot_termine.objekt_id und adresse sind immer gesetzt
#    (Hauptobjekt bei Ein-Objekt-Vorgängen). Vormerken je Objekt (vormerken), Button
#    „Terminierung“ bucht alle vorgemerkten Objekttermine in einem Schritt
#    (terminierung_ausfuehren – Vertrag mit K/B8) mit der Wahl „eine Bestätigung“
#    ({objektliste}, ICS je Objekt) | „je Objekt“ (Vertriebler-Vorlage mit
#    {objektadresse}); Vorbelegung: alle am selben Tag → eine, sonst je Objekt.
#    objekt_termine(session, vorgang) liefert je Objekt den aktiven Termin (Vertrag K).
#    Buchung über vot_buchen (eigene Fassung von kern.termin_buchen mit Objektfeldern).
#  - Montag bis Freitag: Vorschlagsmaschine, Kalenderansicht (5 Spalten) und
#    Wochenkalender ohne Samstag; Wunschzeit „samstag“ (Wunschzeit.aktiv = False) wird
#    ignoriert; manuelle Buchung an einem Samstag bleibt mit Warnhinweis möglich [ANNAHME].
#  - Krankheit: Vertriebler mit abwesenheiten.ist_abwesend am Tag werden nicht
#    vorgeschlagen (Begründung „krank“), Umbuchung „ohne den kranken Vertriebler“ =
#    Ausschluss-Parameter ohne_ad_id.
#  - Testphase (Schalter terminierung_aktiv, Standard aus): Vormerken, Buchen, manuelle
#    Buchung, Umbuchen, Absagen, Terminierung und Vorab-Gespräche liefern
#    lead_v5.TESTPHASE_HINWEIS (Routen 403 JSON / Redirect mit Meldung); Vorschläge
#    werden als Aktivität „Vorschläge berechnet: …“ protokolliert (testphase_kontext für
#    die Templates, auch für K).

import json
import threading
from datetime import date, datetime, timedelta

from sqlalchemy.orm import Session

from app import abwesenheiten, lead_v2, lead_v5
from app import leadmanagement as kern
from app import objekte as objekte_modul
from app.models import (AdProfil, Benutzer, Kunde, Vorgang, VorgangObjekt, VotTermin,
                        TERMIN_MEDIEN, TERMIN_TYP_NAMEN)

# Parameter dieses Moduls (Standardwerte; Pflege über Lead-Einstellungen oder
# das AD-Profil – kanal_ad_regel ist JSON {kanal: [ad_ids]}, leer = frei)
PARAMETER_LOKAL = {
    "kanal_ad_regel": "",
    "vorab_dauer_min": "30",
    "ersatz_min_treffer": "3",
    "termin_konflikt_modus": "warnen",     # warnen | sperren (Puffer-Konflikte)
    "vorschlag_raster_manuell_min": "15",
}
AKTIVE_STATUS = ("geplant", "bestaetigt")
BELEGT_STATUS = ("geplant", "bestaetigt", "vorgemerkt")   # zählen in der Kollision
STATUS_VORGEMERKT = "vorgemerkt"
VORAB_TYPEN = ("telefon", "online")

# v25 (PLAN_LEAD_V3 Phase 120): Handelsvertreter sind im Assistenten keine
# Kandidaten, wenn der anfragende Benutzer nicht selbst dieser HV ist –
# Begründung wörtlich laut Plan; manuelle Buchung durch den Innendienst auf
# einen HV bleibt möglich (ausgeschlossen[...]["manuell_erlaubt"]).
HV_GRUND = "Handelsvertreter terminieren ihre Leads selbst"
HV_HINWEIS = "Lead liegt bei {name} (Handelsvertreter), Terminierung durch den Vertreter"
ADRESSE_HINWEIS = ("Adresse fehlt – Straße, PLZ und Ort in der Kundenkartei ergänzen, "
                   "danach erscheinen die Terminvorschläge.")

# Cache der Terminvorschläge für den Block Termine der Kartei (Phase 119/120):
# {vorgang_id: {sicht: (berechnet_um, antwort)}}, 10 Minuten je Lead; Agent C
# ruft vorschlaege_cache_leeren(vorgang_id) nach dem Autospeichern einer
# Adresse auf; Buchungen/Absagen leeren den Cache komplett (Kalender ändert sich).
VORSCHLAEGE_CACHE_SEKUNDEN = 600
vorschlaege_cache: dict = {}
# v29 (Phase 143): Kalenderansicht – Cache 10 Minuten je Lead, Sicht, Woche und
# gewählten „Weiteren Kalendern“: {vorgang_id: {schluessel: (berechnet_um, antwort)}}
kalender_cache: dict = {}
VORSCHLAEGE_ANZAHL_STANDARD = 3
SPERRZEIT_TYP = "sperrzeit"
SPERRZEIT_VORGANG_ID = 0          # Sperrzeiten hängen an keinem Vorgang (vorgang_id ist NOT NULL)
KALENDER_RASTER_MIN = 15
KALENDER_TAGE = 5                 # v31 (Phase 158): Mo–Fr (bis v30 Mo–Sa)
WERKTAGE_MAX = 5                  # weekday() < 5 = Montag bis Freitag
EINSTELLUNG_WEITERE = "assistent_kalender"
TERMIN_TYP_NAMEN_V4 = dict(TERMIN_TYP_NAMEN, sperrzeit="Sperrzeit")
# v31 (Phase 158): Begründungen im Kandidatenfilter
KRANK_GRUND = "krank"
OHNE_AD_GRUND = "ausgeschlossen (Umbuchung ohne diesen Vertriebler)"
SAMSTAG_WARNUNG = "Samstag: Terminassistent plant nur Montag bis Freitag – manuelle Buchung mit Warnhinweis"
# v31 (Phase 159): Aktivität „Vorschläge berechnet“ höchstens alle 10 Minuten je Lead
_PROTOKOLL_ZEITEN: dict[int, datetime] = {}
_PROTOKOLL_SPERRE = threading.Lock()
PROTOKOLL_PAUSE_SEKUNDEN = 600
# Wahl der Terminbestätigung bei mehreren Objektterminen (Phase 153)
BESTAETIGUNG_EINE = "eine"
BESTAETIGUNG_JE_OBJEKT = "je_objekt"


def vorschlaege_cache_leeren(vorgang_id: int | None = None) -> None:
    """Cache der Terminvorschläge (und der Kalenderansicht) leeren – für einen
    Lead (Adressänderung in der Kartei) oder komplett (vorgang_id=None, z. B.
    nach einer Buchung oder Sperrzeit)."""
    if vorgang_id is None:
        vorschlaege_cache.clear()
        kalender_cache.clear()
    else:
        vorschlaege_cache.pop(int(vorgang_id), None)
        kalender_cache.pop(int(vorgang_id), None)


def vorschlaege_anzahl(session: Session) -> int:
    """v29: Parameter vorschlaege_anzahl (Lead-Einstellungen, Standard 3, 1–5)."""
    try:
        wert = int(str(kern.parameter_holen(session, "vorschlaege_anzahl",
                                            str(VORSCHLAEGE_ANZAHL_STANDARD))).strip() or 3)
    except ValueError:
        wert = VORSCHLAEGE_ANZAHL_STANDARD
    return max(1, min(5, wert))


def ideal_begruendung(v: dict, uebrige: list | None = None) -> str:
    """v29: Klartext, warum Vorschlag 1 „ideal“ ist – aus den Bewertungsteilen
    (Umweg, Wunschzeit, Tour-Tag, Kompetenz, Kapazität) und dem Abstand zur
    Bewertung von Vorschlag 2."""
    teile = []
    umweg = v.get("umweg")
    if umweg is not None:
        teile.append("kein Umweg" if int(umweg) <= 0 else f"geringster Umweg ({int(umweg)} Min)")
    if v.get("wunsch"):
        teile.append("in der Wunschzeit des Kunden")
    if v.get("tour_tag"):
        teile.append("Tour-Tag in der Nähe")
    if v.get("leerer_tag") is False and v.get("tages_termine"):
        teile.append("Tag bereits mit Terminen belegt (kurze Wege)")
    for g in v.get("gruende") or []:
        if str(g).startswith("Kompetenz") and g.endswith("✓"):
            teile.append("Kompetenz passt")
            break
    if uebrige:
        naechster = uebrige[0]
        abstand = round(float(naechster.get("bewertung", 0)) - float(v.get("bewertung", 0)))
        if abstand > 0:
            teile.append(f"{abstand} Punkte besser bewertet als Vorschlag 2")
    return "Ideal: " + (", ".join(teile) if teile else "beste Gesamtbewertung aus Umweg, "
                                                     "Wunschzeit, Kompetenz und Kapazität")


def parameter(session: Session, name: str, standard: str | None = None) -> str:
    return kern.parameter_holen(session, name,
                                PARAMETER_LOKAL.get(name, standard or ""))


def _int(wert, standard: int) -> int:
    try:
        return int(str(wert).strip())
    except (TypeError, ValueError):
        return standard


# --- Kanal-Regel (E2) --------------------------------------------------------------

def kanal_regel(session: Session) -> dict:
    """{kanal (klein): [ad_ids]} aus dem Parameter kanal_ad_regel."""
    roh = parameter(session, "kanal_ad_regel", "")
    try:
        daten = json.loads(roh) if roh.strip() else {}
    except ValueError:
        daten = {}
    regel = {}
    if isinstance(daten, dict):
        for kanal, ids in daten.items():
            if not isinstance(ids, (list, tuple)):
                continue
            sauber = [int(i) for i in ids if str(i).isdigit()]
            if sauber:
                regel[str(kanal).strip().lower()] = sauber
    return regel


def kanal_regel_setzen(session: Session, regel: dict) -> None:
    sauber = {str(k).strip().lower(): [int(i) for i in v if str(i).isdigit()]
              for k, v in regel.items() if v}
    kern.parameter_setzen(session, "kanal_ad_regel",
                          json.dumps(sauber, ensure_ascii=False) if sauber else "")


def kanal_regel_fuer_ad(session: Session, ad_id: int) -> list[str]:
    """Kanäle (klein), für die dieser AD fest hinterlegt ist."""
    return [k for k, ids in kanal_regel(session).items() if ad_id in ids]


def kanal_regel_ad_setzen(session: Session, ad_id: int, kanaele: list[str]) -> None:
    """Pflege aus dem AD-Profil: diesen AD genau in die gewählten Kanäle
    eintragen (andere AD bleiben unberührt)."""
    gewuenscht = {k.strip().lower() for k in kanaele if k.strip()}
    regel = kanal_regel(session)
    for kanal in list(regel) + [k for k in gewuenscht if k not in regel]:
        ids = [i for i in regel.get(kanal, []) if i != ad_id]
        if kanal in gewuenscht:
            ids.append(ad_id)
        regel[kanal] = ids
    kanal_regel_setzen(session, {k: v for k, v in regel.items() if v})


# --- Kandidatenfilter (E2) ----------------------------------------------------------

def sparten_des_kunden(kunde) -> list[str]:
    return [s.strip().upper() for s in ((kunde.interesse or "") if kunde else "").split(",")
            if s.strip()]


def ad_basis(session: Session, profile: dict | None = None) -> list[Benutzer]:
    """Grundmenge der Außendienstler: aktive Benutzer mit Rolle aussendienst
    (Haupt- oder Zusatzrolle) oder mit AD-Profil (Standardantwort E2)."""
    profile = profile if profile is not None else {
        p.benutzer_id: p for p in session.query(AdProfil)}
    return [b for b in session.query(Benutzer)
            .filter(Benutzer.aktiv.is_(True)).order_by(Benutzer.name)
            if b.hat_rolle("aussendienst") or b.id in profile]


def puffer_minuten(session: Session, profil) -> int:
    """Mindestpuffer F4: max(Parameter puffer_min, Profilpuffer)."""
    return max(_int(parameter(session, "puffer_min", "30"), 30),
               _int(getattr(profil, "puffer_min", 0) or 0, 0))


def _gebiet(profil, plz: str) -> tuple[bool, str]:
    try:
        praefixe = [str(p) for p in json.loads(
            getattr(profil, "gebiet_plz_praefixe", "[]") or "[]")]
    except ValueError:
        praefixe = []
    if not praefixe:
        return True, "Gebiet: kein Gebiet gepflegt"
    if plz:
        treffer = next((p for p in praefixe if plz.startswith(p)), None)
        if treffer:
            return True, f"Gebiet {treffer} ✓"
    return False, f"außerhalb Gebiet ({', '.join(praefixe)}) +20"


def hv_des_vorgangs(session: Session, vorgang: Vorgang,
                    profile: dict | None = None) -> Benutzer | None:
    """Zugewiesener Handelsvertreter (vorgaenge.ad_id mit Kennzeichen
    terminiert_selbst) oder None."""
    if not vorgang.ad_id:
        return None
    profil = (profile or {}).get(vorgang.ad_id) if profile is not None else None
    if profil is None:
        profil = lead_v2.profil_fuer(session, vorgang.ad_id)
    if profil is None or not profil.terminiert_selbst:
        return None
    hv = session.get(Benutzer, vorgang.ad_id)
    return hv if hv is not None and hv.aktiv else None


def objekt_holen(session: Session, vorgang: Vorgang, objekt_id=None, anlegen: bool = True):
    """v31 (Phase 153): das Objekt eines Termins/einer Anfrage – objekt_id (nur aktive
    Objekte des Vorgangs), sonst das Hauptobjekt (bei Bedarf aus der Kundenadresse
    angelegt, damit vot_termine.objekt_id immer gesetzt werden kann)."""
    if objekt_id:
        try:
            objekt = session.get(VorgangObjekt, int(objekt_id))
        except (TypeError, ValueError):
            objekt = None
        if objekt is not None and objekt.vorgang_id == vorgang.id and objekt.aktiv:
            return objekt
    if not vorgang.id:
        return None
    return objekte_modul.hauptobjekt(session, vorgang.id, anlegen=anlegen)


def objekt_ort(session: Session, vorgang: Vorgang, objekt=None) -> tuple:
    """Koordinaten des Objekts (lat, lon) – Objektfelder, bei leerem Objekt bzw. beim
    Hauptobjekt die Vorgangskoordinaten; None ohne Koordinaten."""
    if objekt is not None and objekt.lat is not None:
        return (objekt.lat, objekt.lon)
    if objekt is None or objekt.reihenfolge == 1:
        return (vorgang.lat, vorgang.lon) if vorgang.lat is not None else None
    return None


def objekt_sparten(session: Session, kunde, objekt=None) -> list[str]:
    """Sparten für Kompetenzprüfung/Begründung: Interessen des Objekts, sonst Kunde."""
    codes = objekte_modul.interessen_liste(objekt) if objekt is not None else []
    return codes or sparten_des_kunden(kunde)


def _abwesenheit_text(eintrag) -> str:
    name = abwesenheiten.ARTEN_NAMEN.get(eintrag.art, eintrag.art) if eintrag is not None else "Krankheit"
    if eintrag is None:
        return KRANK_GRUND
    bis = f" bis {eintrag.bis:%d.%m.}" if eintrag.bis else " (offenes Ende)"
    return f"{KRANK_GRUND} ({name}{bis})" if eintrag.art == "krankheit" else f"{name.lower()}{bis}"


def kandidaten(session: Session, vorgang: Vorgang, nur_ad_id: int | None = None,
               benutzer=None, objekt=None, ohne_ad_id: int | None = None,
               horizont_bis=None) -> dict:
    """Vorfilterung (E2). Ausschluss: Terminierung inaktiv, Handelsvertreter
    (v25: nur zugelassen, wenn benutzer.id == hv.id – „Handelsvertreter
    terminieren ihre Leads selbst“; manuelle Buchung bleibt möglich),
    Kanal-Regel, Produktkompetenz (lead_v2.kompetenz_passt). Abwertung:
    Gebiet (+20). Handelsvertreter sehen nur den eigenen Kalender. Liegt der
    Lead bei einem HV und fragt nicht dieser selbst, steht in hv_lead/
    hv_hinweis der Hinweis für den Innendienst.
    v31: `objekt` liefert PLZ/Sparten/Objektart des gewählten Objekts (Phase 153);
    `ohne_ad_id` schließt einen Vertriebler aus (Umbuchung ohne den Kranken);
    Vertriebler, die heute bzw. im ganzen Horizont abwesend sind, werden mit
    Begründung „krank“ ausgeschlossen – teilweise Abwesenheit filtert vorschlaege()
    tagesgenau (Phase 158)."""
    kunde = session.get(Kunde, vorgang.kunde_id)
    if objekt is None and vorgang.id:
        objekt = objekte_modul.hauptobjekt(session, vorgang.id)
    sparten = objekt_sparten(session, kunde, objekt)
    objektart = ((objekt.objektart if objekt is not None and objekt.objektart else None)
                 or ((kunde.objektart or "") if kunde else ""))
    plz = ((objekt.plz or "").strip() if objekt is not None and objekt.plz else
           ((kunde.plz or "").strip() if kunde else ""))
    kanal = (kunde.vertriebskanal or "").strip() if kunde else ""
    regel = kanal_regel(session)
    kanal_ids = regel.get(kanal.lower()) if kanal else None
    # v35 (PLAN_LEAD_V6 Phase 185): Handelsvertreter rechnen mit den Kalendern ihrer GRUPPE
    # (René = nur er; Simons Gruppe = alle Mitglieder) statt nur mit dem eigenen; ein
    # gewünschter nur_ad_id außerhalb der Gruppe wird verworfen
    gruppe = hv_gruppe_ids(session, benutzer)
    if gruppe is not None and (nur_ad_id is None or nur_ad_id not in gruppe):
        nur_ad_id = None if len(gruppe) > 1 else benutzer.id
    profile = {p.benutzer_id: p for p in session.query(AdProfil)}
    namen = {b.id: b.name for b in session.query(Benutzer)}
    benutzer_id = getattr(benutzer, "id", None)
    hv_lead = hv_des_vorgangs(session, vorgang, profile)
    if hv_lead is not None and (hv_lead.id == benutzer_id
                                or (gruppe is not None and hv_lead.id in gruppe)):
        hv_lead = None   # der Vertreter selbst bzw. seine Gruppe: normale Vorschläge
    heute = date.today()
    horizont_bis = horizont_bis or (heute + timedelta(days=_int(parameter(session, "vorschlag_horizont_tage", "14"), 14) + 7))
    ergebnis, ausgeschlossen, abwesend = [], [], {}
    for ad in ad_basis(session, profile):
        if nur_ad_id and ad.id != nur_ad_id:
            continue
        if gruppe is not None and ad.id not in gruppe:
            continue   # v35: Handelsvertreter sehen nur die Kalender der eigenen Gruppe
        profil = profile.get(ad.id)
        grund_aus = None
        manuell_erlaubt = False
        gruende = []
        eintraege = abwesenheiten.im_zeitraum(session, ad.id, heute, horizont_bis)
        heute_abwesend = abwesenheiten.ist_abwesend(session, ad.id, heute)
        ganz_abwesend = any(e.von <= heute and (e.bis is None or e.bis >= horizont_bis) for e in eintraege)
        if ohne_ad_id and ad.id == ohne_ad_id:
            grund_aus = OHNE_AD_GRUND
        elif profil is not None and not profil.aktiv_terminierung:
            grund_aus = "Terminierung nicht aktiv"
        elif (((profil is not None and profil.terminiert_selbst)
               or ad.hat_kennzeichen("handelsvertreter"))
              and ad.id != benutzer_id and not (gruppe is not None and ad.id in gruppe)):
            # v33 (PLAN_V20 Phase 167): Handelsvertreter auch über das Rollen-Kennzeichen;
            # v35: Mitglieder der eigenen Gruppe sind für den HV-Betrachter Kandidaten
            grund_aus = HV_GRUND
            manuell_erlaubt = True
        elif ganz_abwesend or (heute_abwesend is not None and heute_abwesend.bis is None):
            grund_aus = _abwesenheit_text(heute_abwesend or eintraege[0])
        elif kanal_ids and ad.id not in kanal_ids:
            grund_aus = (f"Kanal {kanal} → nur "
                         + ", ".join(namen.get(i, str(i)) for i in kanal_ids))
        else:
            ok, grund = lead_v2.kompetenz_passt(profil, sparten, objektart or None)
            if not ok:
                grund_aus = grund
            else:
                teile = "+".join(sparten) if sparten else "keine Sparte"
                if (objektart or "").upper() == "MFH":
                    teile += ", MFH"
                if "GW" in sparten:
                    teile += ", Gewerbe"
                gruende.append(f"Kompetenz {teile} ✓")
        if grund_aus:
            ausgeschlossen.append({"ad": ad, "grund": grund_aus,
                                   "manuell_erlaubt": manuell_erlaubt})
            continue
        if kanal_ids:
            gruende.insert(0, f"Kanal {kanal} ✓")
        gebiet_ok, gebiet_text = _gebiet(profil, plz)
        gruende.append(gebiet_text)
        if eintraege:
            # teilweise abwesend: Tage im Zeitraum werden in vorschlaege() ausgelassen
            abwesend[ad.id] = eintraege
            gruende.append("abwesend " + ", ".join(
                f"{e.von:%d.%m.}–{e.bis:%d.%m.}" if e.bis else f"ab {e.von:%d.%m.}" for e in eintraege)
                + " ausgenommen")
        ergebnis.append({"ad": ad, "profil": kern.ad_profil(session, ad.id),
                         "gruende": gruende, "gebiet": gebiet_ok,
                         "abwertung": 0 if gebiet_ok else 20,
                         "handelsvertreter": bool((profil and profil.terminiert_selbst)
                                                  or ad.hat_kennzeichen("handelsvertreter")),
                         "abwesenheiten": eintraege})
    return {"kandidaten": ergebnis, "ausgeschlossen": ausgeschlossen,
            "sparten": sparten, "kanal": kanal, "nur_ad_id": nur_ad_id,
            "objektart": objektart, "objekt": objekt, "ohne_ad_id": ohne_ad_id,
            "abwesend": abwesend,
            "hv_lead": hv_lead,
            "hv_hinweis": HV_HINWEIS.format(name=hv_lead.name) if hv_lead else "",
            # HV, die der Innendienst manuell (nicht über Vorschläge) buchen darf
            "hv_manuell": [a["ad"] for a in ausgeschlossen if a["manuell_erlaubt"]]}


def tag_abwesend(eintraege, tag) -> bool:
    """Gilt an diesem Tag ein Abwesenheitseintrag (Phase 158)?"""
    tag = tag.date() if isinstance(tag, datetime) else tag
    return any(e.von <= tag and (e.bis is None or e.bis >= tag) for e in (eintraege or []))


# --- Vorschläge (E1/F4) -------------------------------------------------------------

def _termine_je_ad(session: Session, ad_ids: list[int], von: datetime,
                   bis: datetime) -> dict:
    """Belegte Termine (alle Terminarten, inkl. vorgemerkt) je AD im Zeitraum."""
    termine = {}
    for ad_id in ad_ids:
        termine[ad_id] = (session.query(VotTermin)
                          .filter(VotTermin.ad_id == ad_id,
                                  VotTermin.status.in_(BELEGT_STATUS),
                                  VotTermin.beginn.isnot(None),
                                  VotTermin.beginn >= von,
                                  VotTermin.beginn <= bis)
                          .order_by(VotTermin.beginn).all())
    return termine


def _ende(t: VotTermin, dauer: timedelta) -> datetime:
    return t.ende or (t.beginn + dauer)


def _ort(t, start_ort):
    return (t.lat, t.lon) if t is not None and t.lat is not None else start_ort


def _wunsch_bezeichnung(fenster, beginn: datetime) -> str:
    for w in fenster:
        if kern._im_wunschfenster([w], beginn):
            return w.bezeichnung or w.key
    return ""


def _slot_frei(session: Session, lead_ort, start_ort, beginn: datetime,
               ende: datetime, tages_termine: list, puffer: int,
               dauer: timedelta, fahrzeiten: dict) -> tuple[bool, str]:
    """Kollision mit Tool-Terminen: harte Überlappung oder Verletzung des
    Puffers max(puffer_min, Fahrzeit zum Nachbartermin). (frei, grund)."""
    for t in tages_termine:
        t_ende = _ende(t, dauer)
        if t.beginn < ende and beginn < t_ende:
            return False, "Überschneidung"
        # Nachtrag 08.10.2026 (Antwort Andreas): Sperrzeiten der Handelsvertreter
        # zählen exakt von–bis – kein Mindest-/Fahrzeitpuffer davor oder danach
        if (t.typ or "vot") == SPERRZEIT_TYP:
            continue
        if t_ende <= beginn:
            fahr = fahrzeiten.get(("hin", t.id), 0.0) if lead_ort else 0.0
            noetig = max(puffer, fahr)
            if (beginn - t_ende).total_seconds() / 60 < noetig - 1e-6:
                return False, f"Puffer {noetig:.0f} Min nach {t.beginn:%H:%M}"
        elif t.beginn >= ende:
            fahr = fahrzeiten.get(("weg", t.id), 0.0) if lead_ort else 0.0
            noetig = max(puffer, fahr)
            if (t.beginn - ende).total_seconds() / 60 < noetig - 1e-6:
                return False, f"Puffer {noetig:.0f} Min vor {t.beginn:%H:%M}"
    return True, ""


def wunschzeit_fenster(session: Session, vorgang: Vorgang) -> list:
    """v31 (Phase 158): Wunschzeiten des Leads ohne inaktive Zeilen des Blatts
    Wunschzeiten (Spalte aktiv – „samstag“ = nein wird beim Abgleich ignoriert)."""
    return [w for w in kern._wunschzeit_fenster(session, vorgang) if getattr(w, "aktiv", True)]


def vorschlaege_protokollieren(session: Session, vorgang: Vorgang, gewaehlt: list,
                               benutzer=None, objekt=None) -> bool:
    """v31 (Phase 159): im Testmodus (terminierung_aktiv = aus) werden die berechneten
    Vorschläge als Aktivität „Vorschläge berechnet: …“ protokolliert, damit der
    Assistent beurteilt werden kann – höchstens alle 10 Minuten je Lead (Zähler
    threadsicher). Die Aktivität wird in einer EIGENEN kurzen Transaktion (db.kurz)
    geschrieben, best effort: die Anfrage-Sitzung hat vor den Netzaufrufen gelesen und
    würde beim Schreiben in SQLite-WAL sofort „database is locked“ liefern
    (BUSY_SNAPSHOT, v30-Nachtrag 21); bleibt die Sperre, wird die Aktivität
    übersprungen (Protokollzeile), die Vorschläge bleiben unberührt."""
    import logging
    from sqlalchemy.exc import OperationalError
    from app.db import kurz
    from app.models import LeadAktivitaet
    if not vorgang.id or lead_v5.terminierung_aktiv(session):
        return False
    jetzt = datetime.now()
    with _PROTOKOLL_SPERRE:
        letzte = _PROTOKOLL_ZEITEN.get(vorgang.id)
        if letzte is not None and (jetzt - letzte).total_seconds() < PROTOKOLL_PAUSE_SEKUNDEN:
            return False
        _PROTOKOLL_ZEITEN[vorgang.id] = jetzt
    if gewaehlt:
        teile = [f"{i + 1}. {v['beginn']:%a %d.%m. %H:%M} {v['ad'].name}"
                 + (" (Ideal)" if v.get("ideal") else "") + f" [{v.get('umweg', 0)} Min Umweg]"
                 for i, v in enumerate(gewaehlt)]
        text = "Vorschläge berechnet: " + " · ".join(teile)
    else:
        text = "Vorschläge berechnet: keine freien Slots im Horizont"
    if objekt is not None and getattr(objekt, "reihenfolge", 1) != 1:
        text += f" (Objekt: {objekt.bezeichnung})"
    text = (text + " – Testphase, nicht gebucht")[:4000]
    benutzer_id = getattr(benutzer, "id", None)
    vorgang_id = vorgang.id
    try:
        with kurz() as s:
            s.add(LeadAktivitaet(vorgang_id=vorgang_id, typ="termin", text=text,
                                 benutzer_id=benutzer_id, erstellt_von=benutzer_id))
    except OperationalError as problem:
        if "locked" not in str(problem).lower():
            raise
        logging.getLogger("angebotstool").warning(
            "Vorschläge-Protokoll (Testphase) für Vorgang %s übersprungen: Datenbank gesperrt", vorgang_id)
        with _PROTOKOLL_SPERRE:
            _PROTOKOLL_ZEITEN.pop(vorgang_id, None)
        return False
    return True


def vorschlaege(session: Session, vorgang: Vorgang, nur_ad_id: int | None = None,
                anzahl: int | None = None, benutzer=None, objekt=None,
                ohne_ad_id: int | None = None) -> dict:
    """Top-N-Slots (Dauer aus Profil/90, Raster 30, Horizont 14 Werktage).
    Kapazität zählt nur Vor-Ort-Termine, Kollision alle Terminarten (auch
    Sperrzeiten der HV); Puffer = max(puffer_min, Fahrzeit); Begründung je
    Vorschlag in Klartext. v29: anzahl None = Parameter vorschlaege_anzahl
    (Standard 3); der erste Vorschlag trägt ideal=True + ideal_grund.
    v31: nur Montag bis Freitag (Phase 158), Adresse/Koordinaten des gewählten
    Objekts (Phase 153), kranke Vertriebler tagesgenau ausgelassen, `ohne_ad_id`
    für die Umbuchung ohne den kranken Vertriebler; im Testmodus Aktivität
    „Vorschläge berechnet“ (Phase 159)."""
    from app import outlook_sync   # v33 (Phase 170): Belegt-Cache statt kalender.frei_belegt
    from app import routing
    if anzahl is None:
        anzahl = vorschlaege_anzahl(session)
    jetzt = datetime.now()
    horizont = _int(parameter(session, "vorschlag_horizont_tage", "14"), 14)
    raster = max(5, _int(parameter(session, "vorschlag_raster_min", "30"), 30))
    if objekt is None and vorgang.id:
        objekt = objekte_modul.hauptobjekt(session, vorgang.id)
    lead_ort = objekt_ort(session, vorgang, objekt)
    tage = []
    tag = jetzt.replace(hour=0, minute=0, second=0, microsecond=0)
    while len(tage) < horizont:
        tag += timedelta(days=1)
        if tag.weekday() < WERKTAGE_MAX:
            tage.append(tag)
    vorfilter = kandidaten(session, vorgang, nur_ad_id, benutzer=benutzer, objekt=objekt,
                           ohne_ad_id=ohne_ad_id, horizont_bis=tage[-1].date() if tage else None)
    hinweise = []
    if lead_ort is None:
        hinweise.append("Lead-Adresse ohne Koordinaten („Adresse prüfen“) – "
                        "Umwege und Fahrzeit-Puffer werden ohne Fahrzeit bewertet.")
    ad_ids = [k["ad"].id for k in vorfilter["kandidaten"]]
    termine_je_ad = _termine_je_ad(session, ad_ids, jetzt - timedelta(hours=12),
                                   tage[-1] + timedelta(days=1)) if tage else {}
    punkte = set()
    for k in vorfilter["kandidaten"]:
        for t in termine_je_ad.get(k["ad"].id, []):
            if t.lat is not None:
                punkte.add((t.lat, t.lon))
        if k["profil"].start_lat is not None:
            punkte.add((k["profil"].start_lat, k["profil"].start_lon))
    if lead_ort is not None and punkte:
        # v27 (PLAN_V17 Phase 131, Lasttest-Befund): EIN Matrix-Aufruf für beide
        # Richtungen (Quellen = Ziele = Lead + Punkte) statt zwei Netzaufrufe –
        # bei 2 s Latenz je Aufruf halbiert das die Wartezeit der Vorschläge
        alle = [lead_ort] + [p for p in punkte if p != lead_ort][:49]
        routing.matrix_fuellen(session, alle, alle)
    fenster = wunschzeit_fenster(session, vorgang)   # v31: ohne inaktive Wunschzeiten (Samstag)
    # Lasttest 08.10.2026 (v29): Routing-Cache-Zeilen (Matrix und Luftlinien-
    # Schätzungen aus fahrzeit()) sind geschrieben – Schreibsperre freigeben, bevor
    # die Vorschläge sekundenlang gerechnet werden (sonst „database is locked“ bei
    # parallelen Schreibern; Befund Lauf 1/2 der Rollout-Vorbereitung)
    from app.db import verbindung_freigeben as _freigeben
    _freigeben(session)
    score_an = lead_v2.score_aktiv(session)   # v25: Klassen-Bonus nur bei Score an
    alle = []
    for k in vorfilter["kandidaten"]:
        ad, profil = k["ad"], k["profil"]
        dauer = timedelta(minutes=profil.termin_dauer_min or 90)
        puffer = puffer_minuten(session, profil)
        max_tag = profil.max_termine_tag or 4
        start_ort = ((profil.start_lat, profil.start_lon)
                     if profil.start_lat is not None else None)
        termine = termine_je_ad.get(ad.id, [])
        fahrzeiten = {}
        if lead_ort is not None:
            for t in termine:
                fahrzeiten[("hin", t.id)] = routing.fahrzeit(
                    session, _ort(t, start_ort), lead_ort)["minuten"]
                fahrzeiten[("weg", t.id)] = routing.fahrzeit(
                    session, lead_ort, _ort(t, start_ort))["minuten"]
        # v29 (Phase 143, [OFFEN 3]): Handelsvertreter haben kein Friondo-Postfach –
        # kein Outlook-Abruf, nur Tool-Termine und Sperrzeiten
        # v33 (PLAN_V20 Phase 170): Belegtzeiten aus dem Cache outlook_belegt (Lauf
        # outlook-ruecklesen) – nie Graph im Request
        belegt_extern = (outlook_sync.belegt_fuer(
            session, ad, jetzt, tage[-1] + timedelta(days=1))
            if tage and not k.get("handelsvertreter") else None)
        for tag in tage:
            # v31 (Phase 158): Tage einer Krankheit/Abwesenheit des Vertrieblers auslassen
            if tag_abwesend(k.get("abwesenheiten"), tag):
                continue
            zeiten = kern._arbeitszeiten_von_bis(profil, tag)
            if zeiten is None:
                continue
            tages_termine = [t for t in termine if t.beginn.date() == tag.date()]
            # Nachtrag 08.10.2026: Sperrzeiten sind keine Kundentermine – sie zählen
            # nur in der Kollision (exakt von–bis, _slot_frei), nicht als Nachbar
            # für Umweg/Tour-Tag und machen einen Tag nicht „belegt“
            kunden_termine = [t for t in tages_termine if (t.typ or "vot") != SPERRZEIT_TYP]
            vot_tag = [t for t in kunden_termine if (t.typ or "vot") == "vot"]
            if len(vot_tag) >= max_tag:
                continue
            leerer_tag = not kunden_termine
            tour_tag = (lead_ort is not None and any(
                t.lat is not None
                and routing.luftlinie_km(lead_ort, (t.lat, t.lon)) <= 10
                for t in kunden_termine))
            minute = zeiten[0]
            dauer_min = int(dauer.total_seconds() // 60)
            while minute + dauer_min <= zeiten[1]:
                beginn = tag + timedelta(minutes=minute)
                minute += raster
                if beginn < jetzt + timedelta(hours=2):
                    continue
                ende = beginn + dauer
                frei, _grund = _slot_frei(session, lead_ort, start_ort, beginn, ende,
                                          tages_termine, puffer, dauer, fahrzeiten)
                if not frei:
                    continue
                if belegt_extern and any(beginn < b_ende and b_von < ende
                                         for b_von, b_ende in belegt_extern):
                    continue
                vorher = max((t for t in kunden_termine if _ende(t, dauer) <= beginn),
                             key=lambda t: t.beginn, default=None)
                nachher = min((t for t in kunden_termine if t.beginn >= ende),
                              key=lambda t: t.beginn, default=None)
                geschaetzt = False
                umweg = 0.0
                if lead_ort is not None:
                    hin = routing.fahrzeit(session, _ort(vorher, start_ort), lead_ort)
                    weg = routing.fahrzeit(session, lead_ort, _ort(nachher, start_ort))
                    direkt = routing.fahrzeit(session, _ort(vorher, start_ort),
                                              _ort(nachher, start_ort))
                    umweg = max(0.0, hin["minuten"] + weg["minuten"] - direkt["minuten"])
                    geschaetzt = hin["geschaetzt"] or weg["geschaetzt"] or direkt["geschaetzt"]
                bewertung = umweg + k["abwertung"]
                wunsch_text = _wunsch_bezeichnung(fenster, beginn) if fenster else ""
                wunsch = bool(wunsch_text)
                if wunsch:
                    bewertung -= 30
                if tour_tag:
                    bewertung -= 15
                if leerer_tag:
                    bewertung += 20
                if beginn.hour < 9 or beginn.hour >= 17:
                    bewertung += 10
                if score_an and (vorgang.score_klasse or "") == "A":
                    bewertung += (beginn.date() - jetzt.date()).days * 2
                teile = list(k["gruende"])
                teile.append(f"Umweg {round(umweg)} Min" + (" (geschätzt)" if geschaetzt else ""))
                if fenster:
                    teile.append(f"Wunschzeit {wunsch_text} ✓" if wunsch
                                 else "außerhalb Wunschzeit")
                if tour_tag:
                    teile.append("Tour-Tag")
                if leerer_tag:
                    teile.append("leerer Tag")
                teile.append(f"{len(vot_tag) + 1}/{max_tag} Termine am Tag")
                alle.append({
                    "ad": ad, "beginn": beginn, "ende": ende,
                    "umweg": round(umweg), "geschaetzt": geschaetzt,
                    "wunsch": wunsch, "tour_tag": tour_tag,
                    "leerer_tag": leerer_tag, "bewertung": bewertung,
                    "vorher": vorher, "nachher": nachher,
                    "tages_termine": tages_termine, "puffer": puffer,
                    "begruendung": " · ".join(teile), "gruende": teile,
                })
    # Lasttest 08.10.2026: Luftlinien-Schätzungen aus fahrzeit() (Cache-Misses in der
    # Schleife) ebenfalls sofort festschreiben – keine Schreibsperre über die Auswahl
    _freigeben(session)
    alle.sort(key=lambda v: (v["bewertung"], v["beginn"]))
    gewaehlt, je_tag = [], {}
    for v in alle:
        schluessel = (v["ad"].id, v["beginn"].date())
        if je_tag.get(schluessel, 0) >= 2:
            continue
        je_tag[schluessel] = je_tag.get(schluessel, 0) + 1
        v["ideal"] = False
        v["ideal_grund"] = ""
        gewaehlt.append(v)
        if len(gewaehlt) >= anzahl:
            break
    if gewaehlt:
        gewaehlt[0]["ideal"] = True
        gewaehlt[0]["ideal_grund"] = ideal_begruendung(gewaehlt[0], gewaehlt[1:])
    # v31 (Phase 159): Testmodus – Vorschläge zur Auswertung protokollieren
    vorschlaege_protokollieren(session, vorgang, gewaehlt, benutzer=benutzer, objekt=objekt)
    return {"vorschlaege": gewaehlt, "hinweise": hinweise, "anzahl": anzahl,
            "kandidaten": [k["ad"] for k in vorfilter["kandidaten"]],
            "kandidaten_info": vorfilter["kandidaten"],
            "ausgeschlossen": vorfilter["ausgeschlossen"],
            "sparten": vorfilter["sparten"], "kanal": vorfilter["kanal"],
            "nur_ad_id": vorfilter["nur_ad_id"], "ohne_ad_id": ohne_ad_id,
            "objekt": objekt, "lead_ort": lead_ort,
            "hv_lead": vorfilter["hv_lead"], "hv_hinweis": vorfilter["hv_hinweis"],
            "hv_manuell": vorfilter["hv_manuell"]}


# --- v25 (Phase 119/120): Terminvorschläge für den Block Termine der Kartei --------

def adresse_fehlt(kunde, objekt=None) -> list[str]:
    """Fehlende Adressteile (Straße, PLZ, Ort) – ohne Adresse keine Vorschläge.
    v31: mit `objekt` zählt die Objektadresse (Hauptobjekt = Kundenadresse)."""
    # Hauptobjekt (reihenfolge 1): die Kundenfelder sind der Master – so zählt eine am
    # Kunden nachgetragene Adresse sofort (Orchestrator 13.10.2026, Master-Regel A-AT-1)
    if objekt is not None and getattr(objekt, "reihenfolge", None) == 1 and kunde is not None:
        objekt = None
    quelle = objekt if objekt is not None else kunde
    if quelle is None:
        return ["Straße", "PLZ", "Ort"]
    fehlt = []
    for feld, name in (("strasse", "Straße"), ("plz", "PLZ"), ("ort", "Ort")):
        if not str(getattr(quelle, feld, "") or "").strip():
            fehlt.append(name)
    return fehlt


def testphase_kontext(session: Session) -> dict:
    """v31 (Phase 159): Kontext-Flags für Templates (auch für K): terminierung_aktiv,
    testphase_hinweis, mail_versand_aktiv, mailsperre_hinweis."""
    return {"terminierung_aktiv": lead_v5.terminierung_aktiv(session),
            "testphase_hinweis": lead_v5.TESTPHASE_HINWEIS,
            "mail_versand_aktiv": lead_v5.mail_versand_aktiv(session),
            "mailsperre_hinweis": lead_v5.MAILSPERRE_HINWEIS}


def _beginn_text(beginn: datetime) -> str:
    from app.templating import de_datum
    return de_datum(beginn, "%a %d.%m.%Y · %H:%M") + " Uhr"


def vorschlaege_json(session: Session, vorgang: Vorgang, benutzer=None,
                     anzahl: int | None = None, jetzt: datetime | None = None,
                     objekt_id=None, ohne_ad_id: int | None = None) -> dict:
    """Antwort für GET /lead-management/lead/{id}/termin/vorschlaege.json
    (Vertrag Agent C/D): {status: ok|adresse_fehlt|hv_lead|keine, hinweis,
    vorschlaege: [{ad_id, ad_name, beginn (ISO), beginn_text, begruendung,
    umweg_min, ideal, ideal_grund}]} – v29: genau `vorschlaege_anzahl` (Standard
    3, Feld anzahl), Cache 10 Minuten je Lead (Sicht Innendienst bzw. je
    Handelsvertreter getrennt), Zusatzfelder aus_cache/berechnet_um/buchbar/
    pflicht_offen. Reihenfolge der Zustände: HV-Lead (Innendienst) → Adresse
    fehlt → Vorschläge (ok) oder keine. v31: je Objekt (objekt_id, Felder objekt_id/
    objekt_text/objekte/mehrere_objekte), buchbar = terminierung_aktiv
    (Testphase, testphase_hinweis), ohne_ad_id (Umbuchung ohne den Kranken)."""
    jetzt = jetzt or datetime.now()
    if anzahl is None:
        anzahl = vorschlaege_anzahl(session)
    kunde = session.get(Kunde, vorgang.kunde_id)
    objekt = objekt_holen(session, vorgang, objekt_id)
    objekte = objekte_modul.objekte_fuer(session, vorgang.id) if vorgang.id else []
    hv_ich = lead_v2.ist_handelsvertreter(session, benutzer) if benutzer is not None else False
    sicht = (f"hv{benutzer.id}" if hv_ich else "id") + (f"-o{objekt.id}" if objekt is not None else "") \
        + (f"-x{ohne_ad_id}" if ohne_ad_id else "")
    eintrag = vorschlaege_cache.get(vorgang.id, {}).get(sicht)
    if eintrag is not None and (jetzt - eintrag[0]).total_seconds() < VORSCHLAEGE_CACHE_SEKUNDEN:
        antwort = dict(eintrag[1])
        antwort["aus_cache"] = True
        return antwort
    aktiv = lead_v5.terminierung_aktiv(session)
    pflicht_offen = lead_v2.pflichtfelder_offen(session, kunde, vorgang) if kunde else []
    antwort = {"status": "ok", "hinweis": "", "vorschlaege": [], "anzahl": anzahl,
               "buchbar": aktiv, "terminierung_aktiv": aktiv,
               "testphase_hinweis": "" if aktiv else lead_v5.TESTPHASE_HINWEIS,
               "pflicht_offen": pflicht_offen,
               "objekt_id": objekt.id if objekt is not None else None,
               "objekt_text": objekte_modul.objekt_text(objekt) if objekt is not None and len(objekte) > 1 else "",
               "mehrere_objekte": len(objekte) > 1,
               "objekte": [{"id": o.id, "bezeichnung": o.bezeichnung, "adresse": objekte_modul.objekt_text(o, False)}
                           for o in objekte],
               "ohne_ad_id": ohne_ad_id,
               "berechnet_um": jetzt.strftime("%H:%M"), "aus_cache": False}
    hv = hv_des_vorgangs(session, vorgang)
    # v35 (Phase 185): Mitglieder der Gruppe des zuständigen HV sehen normale Vorschläge
    gruppe_ich = hv_gruppe_ids(session, benutzer) or ({getattr(benutzer, "id", None)} if benutzer is not None else set())
    if hv is not None and hv.id not in gruppe_ich:
        antwort.update(status="hv_lead", hinweis=HV_HINWEIS.format(name=hv.name),
                       hv_id=hv.id, hv_name=hv.name)
    else:
        fehlt = adresse_fehlt(kunde, objekt)
        if fehlt:
            antwort.update(status="adresse_fehlt",
                           hinweis=ADRESSE_HINWEIS, fehlt=fehlt)
        else:
            ergebnis = vorschlaege(session, vorgang, anzahl=anzahl, benutzer=benutzer,
                                   objekt=objekt, ohne_ad_id=ohne_ad_id)
            liste = [{
                "ad_id": v["ad"].id, "ad_name": v["ad"].name,
                "beginn": v["beginn"].strftime("%Y-%m-%dT%H:%M"),
                "ende": v["ende"].strftime("%Y-%m-%dT%H:%M"),
                "beginn_text": _beginn_text(v["beginn"]),
                "begruendung": v["begruendung"], "umweg_min": int(v["umweg"]),
                "ideal": bool(v.get("ideal")), "ideal_grund": v.get("ideal_grund", ""),
            } for v in ergebnis["vorschlaege"][:anzahl]]
            antwort["vorschlaege"] = liste
            antwort["kandidaten"] = [{"ad_id": a.id, "ad_name": a.name}
                                     for a in ergebnis["kandidaten"]]
            if not liste:
                if not ergebnis["kandidaten"]:
                    hinweis = "Kein Außendienstler erfüllt die Voraussetzungen – manuell setzen."
                else:
                    hinweis = ("Keine freien Slots im Horizont – Horizont/Raster in den "
                               "Lead-Einstellungen prüfen oder manuell setzen.")
                antwort.update(status="keine", hinweis=hinweis)
            elif ergebnis["hinweise"]:
                antwort["hinweis"] = " ".join(ergebnis["hinweise"])
    vorschlaege_cache.setdefault(vorgang.id, {})[sicht] = (jetzt, dict(antwort))
    return antwort


# --- v31 (PLAN_LEAD_V5 Phase 153): Termine je Objekt, Vormerken, Terminierung ---------------

def objekt_termine(session: Session, vorgang: Vorgang) -> list[dict]:
    """Vertrag mit K (Block „Termine“ der Kartei): je aktivem Objekt des Vorgangs ein
    dict {objekt, termin (aktiver VOT: vorgemerkt/geplant/bestaetigt oder None),
    vorgemerkt (bool), status, ad (Benutzer|None), historie (abgeschlossene VOT-
    Termine des Objekts)}. Termine ohne objekt_id zählen zum Hauptobjekt."""
    objekte = objekte_modul.objekte_fuer(session, vorgang.id) if vorgang.id else []
    if not objekte:
        return []
    haupt = next((o for o in objekte if o.reihenfolge == 1), objekte[0])
    termine = (session.query(VotTermin)
               .filter(VotTermin.vorgang_id == vorgang.id, VotTermin.typ == "vot")
               .order_by(VotTermin.beginn.desc().nullslast(), VotTermin.id.desc()).all())
    benutzer_map = {b.id: b for b in session.query(Benutzer)
                    .filter(Benutzer.id.in_({t.ad_id for t in termine if t.ad_id} or {0}))}
    ergebnis = []
    for o in objekte:
        eigene = [t for t in termine if (t.objekt_id or haupt.id) == o.id]
        aktive = sorted([t for t in eigene if t.status in BELEGT_STATUS],
                        key=lambda t: (0 if t.status == STATUS_VORGEMERKT else 1, t.beginn or datetime.max))
        termin = aktive[0] if aktive else None
        ergebnis.append({"objekt": o, "termin": termin,
                         "vorgemerkt": bool(termin is not None and termin.status == STATUS_VORGEMERKT),
                         "status": termin.status if termin is not None else "",
                         "ad": benutzer_map.get(termin.ad_id) if termin is not None and termin.ad_id else None,
                         "historie": [t for t in eigene if t.status not in BELEGT_STATUS]})
    return ergebnis


def objekte_ohne_termin(session: Session, vorgang: Vorgang) -> list[VorgangObjekt]:
    return [z["objekt"] for z in objekt_termine(session, vorgang) if z["termin"] is None]


def objekte_hinweis(session: Session, vorgang: Vorgang) -> str:
    """„1 von 3 Objekten ohne Termin“ (leer bei Ein-Objekt-Vorgängen oder vollständig)."""
    zeilen = objekt_termine(session, vorgang)
    if len(zeilen) <= 1:
        return ""
    offen = [z for z in zeilen if z["termin"] is None]
    if not offen:
        return ""
    return (f"{len(offen)} von {len(zeilen)} Objekten ohne Termin: "
            + ", ".join(z["objekt"].bezeichnung for z in offen))


def vorgemerkte_objekttermine(session: Session, vorgang: Vorgang) -> list[VotTermin]:
    """Alle vorgemerkten Vor-Ort-Termine des Vorgangs (einer je Objekt), chronologisch."""
    return (session.query(VotTermin)
            .filter(VotTermin.vorgang_id == vorgang.id, VotTermin.typ == "vot",
                    VotTermin.status == STATUS_VORGEMERKT)
            .order_by(VotTermin.beginn, VotTermin.id).all())


def bestaetigung_vorbelegung(termine) -> str:
    """Wahl der Terminbestätigung bei mehreren Objektterminen: alle am selben Tag →
    eine Mail ({objektliste}), sonst je Objekt eine Bestätigung mit {objektadresse}."""
    tage = {t.beginn.date() for t in (termine or []) if t.beginn}
    return BESTAETIGUNG_EINE if len(tage) <= 1 else BESTAETIGUNG_JE_OBJEKT


def _gesperrt(session: Session) -> str:
    """Leer, wenn die Terminierung freigeschaltet ist, sonst der Testphase-Hinweis."""
    return "" if lead_v5.terminierung_aktiv(session) else lead_v5.TESTPHASE_HINWEIS


def vormerken(session: Session, vorgang: Vorgang, ad_id: int, beginn: datetime,
              objekt_id=None, benutzer=None, quelle: str = "assistent",
              umweg: int | None = None) -> tuple[VotTermin | None, str]:
    """POST /lead/{id}/termin/vormerken: Termin für EIN Objekt vormerken (Status
    vorgemerkt, ohne Mail/Kalender/Phase) – ein vorhandener vorgemerkter Termin
    desselben Objekts wird ersetzt; „Terminierung“ bucht später alle vorgemerkten
    Objekttermine. Gesperrt in der Testphase."""
    sperre = _gesperrt(session)
    if sperre:
        return None, sperre
    ad = session.get(Benutzer, ad_id)
    kunde = session.get(Kunde, vorgang.kunde_id)
    if ad is None or kunde is None:
        return None, "Außendienstler oder Kunde fehlt."
    objekt = objekt_holen(session, vorgang, objekt_id)
    if objekt is None:
        return None, "Objekt nicht gefunden."
    profil = kern.ad_profil(session, ad_id)
    ort = objekte_modul.ausfuehrungsort(session, objekt_id=objekt.id, vorgang=vorgang, kunde=kunde)
    koordinaten = objekt_ort(session, vorgang, objekt)
    termin = VotTermin(
        vorgang_id=vorgang.id, ad_id=ad_id, beginn=beginn,
        ende=beginn + timedelta(minutes=profil.termin_dauer_min or 90),
        adresse=ort.get("einzeilig", "")[:300],
        lat=koordinaten[0] if koordinaten else None, lon=koordinaten[1] if koordinaten else None,
        status=STATUS_VORGEMERKT, quelle=quelle, umweg_min=umweg, demo=bool(vorgang.demo),
        typ="vot", medium="vor_ort", objekt_id=objekt.id,
        erstellt_von=benutzer.id if benutzer else None)
    session.add(termin)
    session.flush()
    _vorgemerkte_aufraeumen(session, vorgang.id, termin.id, objekt_id=objekt.id)
    mehrere = len(objekte_modul.objekte_fuer(session, vorgang.id)) > 1
    kern.aktivitaet(session, vorgang.id, "termin",
                    f"Termin vorgemerkt {beginn:%d.%m.%Y %H:%M} bei {ad.name}"
                    + (f" für {objekt.bezeichnung} ({ort.get('einzeilig', '')})" if mehrere else "")
                    + " – Buchung über „Terminierung“", benutzer=benutzer)
    _ad_am_vorgang(session, vorgang, ad_id, benutzer)
    session.flush()
    vorschlaege_cache_leeren()
    hinweis = objekte_hinweis(session, vorgang)
    meldung = (f"Termin für {objekt.bezeichnung} vorgemerkt" if mehrere else "Termin vorgemerkt") \
        + " – „Terminierung“ bucht alle vorgemerkten Termine." + (f" {hinweis}." if hinweis else "")
    return termin, meldung


def terminierung_ausfuehren(session: Session, vorgang: Vorgang, benutzer=None,
                            bestaetigung: str = "auto") -> tuple[bool, str]:
    """Button „Terminierung“ (B8, Vertrag mit K – ersetzt lead_kartei.terminierung_
    ausfuehren): bucht ALLE vorgemerkten Objekttermine in einem Schritt (vorgemerkt →
    geplant, Outlook je Termin, Erinnerung −24 h je Termin, Phase Terminiert ab dem
    ersten Objekttermin, Aktivität, Glocke an den AD); Terminbestätigung nach
    `bestaetigung`: „eine“ = eine Mail terminbestaetigung_objekte mit {objektliste} und
    ICS je Objekt, „je_objekt“ = je Termin die Vertriebler-Vorlage mit {objektadresse},
    „auto“ = Vorbelegung (gleicher Tag → eine, sonst je Objekt). Ein einzelner
    vorgemerkter Termin bekommt immer die normale Terminbestätigung. Objekte ohne
    Termin bleiben offen (Hinweis „n von m Objekten ohne Termin“). Pflichtfelder
    (inkl. Außendienst, Phase 157) müssen erfüllt sein; Testphase → gesperrt.
    Liefert (ok, meldung) – der Aufrufer committet (Route: _speichern-Muster)."""
    from app import kalender as kalender_modul
    sperre = _gesperrt(session)
    if sperre:
        return False, sperre
    kunde = session.get(Kunde, vorgang.kunde_id)
    if kunde is None:
        return False, "Kunde fehlt."
    offen = lead_v2.pflichtfelder_offen(session, kunde, vorgang)
    hv = hv_des_vorgangs(session, vorgang)
    # Phase 157: Pflichtfeld Außendienst (Parameter pflichtfelder: ad_id) – erfüllt durch
    # vorgang.ad_id (vormerken setzt ihn) bzw. den zugewiesenen Handelsvertreter; der Name
    # des Felds in lead_v2.pflichtfelder_offen ist Sache von K/B („Ad_id“/„Außendienst“)
    if vorgang.ad_id or hv is not None:
        offen = [f for f in offen if str(f).lower() not in ("ad_id", "außendienst", "aussendienst")]
    if offen:
        return False, "Terminierung nicht möglich – es fehlt: " + ", ".join(offen)
    termine = vorgemerkte_objekttermine(session, vorgang)
    if not termine:
        aktive = lead_mail_objekttermine(session, vorgang)
        if aktive and vorgang.lead_phase == "terminiert":
            return False, "Bereits terminiert – alle Objekttermine sind geplant."
        return False, "Terminierung nicht möglich – es fehlt: Termin (vorgemerkt)"
    termine = [t for t in termine if t.beginn is not None]
    if not termine:
        return False, "Vorgemerkter Termin ohne Uhrzeit – bitte Zeitpunkt wählen."
    if bestaetigung not in (BESTAETIGUNG_EINE, BESTAETIGUNG_JE_OBJEKT):
        bestaetigung = bestaetigung_vorbelegung(termine)
    if len(termine) == 1:
        bestaetigung = BESTAETIGUNG_JE_OBJEKT
    mehrere = len(objekte_modul.objekte_fuer(session, vorgang.id)) > 1
    kalender_ok = 0
    namen = []
    for termin in termine:
        termin.status = "geplant"
        if termin.ende is None:
            profil = kern.ad_profil(session, termin.ad_id) if termin.ad_id else None
            termin.ende = termin.beginn + timedelta(minutes=(getattr(profil, "termin_dauer_min", 90) or 90))
        if not termin.objekt_id:
            haupt = objekte_modul.hauptobjekt(session, vorgang.id, anlegen=True, kunde=kunde)
            termin.objekt_id = haupt.id if haupt is not None else None
        if not termin.adresse:
            termin.adresse = objekte_modul.ausfuehrungsort(session, termin=termin, vorgang=vorgang,
                                                           kunde=kunde).get("einzeilig", "")[:300]
        if not termin.demo:
            termin.demo = bool(vorgang.demo)
        ad = session.get(Benutzer, termin.ad_id) if termin.ad_id else None
        namen.append(ad.name if ad else "?")
        if bestaetigung == BESTAETIGUNG_JE_OBJEKT and not _mail_geplant(session, termin, "terminbestaetigung"):
            kern.mail_planen(session, vorgang, "terminbestaetigung", termin=termin)
        if not _mail_geplant(session, termin, "terminerinnerung"):
            kern.mail_planen(session, vorgang, "terminerinnerung", termin=termin,
                             geplant_am=termin.beginn - timedelta(hours=24))
        if kalender_modul.termin_schreiben(session, termin, vorgang, kunde, ad):
            kalender_ok += 1
    if bestaetigung == BESTAETIGUNG_EINE and not _mail_geplant(session, termine[0], "terminbestaetigung_objekte"):
        # eine Bestätigung für alle Objekte – Eintrag hängt am ersten Termin, rendern()
        # nimmt alle aktiven Objekttermine (ICS je Objekt)
        kern.mail_planen(session, vorgang, "terminbestaetigung_objekte", termin=termine[0])
    vorgang.lead_phase = "terminiert"
    vorgang.terminiert_am = datetime.now()
    vorgang.naechste_aktion_am = None
    vorgang.zurueckgestellt_bis = None
    if vorgang.ad_id is None and termine[0].ad_id:
        vorgang.ad_id = termine[0].ad_id          # A-7: Zuständiger AD am Vorgang
    hinweis = objekte_hinweis(session, vorgang)
    zeiten = ", ".join(f"{t.beginn:%d.%m.%Y %H:%M}" for t in termine)
    text = (f"Terminierung: {len(termine)} Termin{'e' if len(termine) != 1 else ''} ({zeiten}) bei "
            f"{', '.join(dict.fromkeys(namen))} – vorgemerkt → geplant, "
            + ("eine Terminbestätigung für alle Objekte" if bestaetigung == BESTAETIGUNG_EINE and len(termine) > 1
               else ("Terminbestätigung je Objekt" if len(termine) > 1 else "Terminbestätigung geplant"))
            + f", Kalender {kalender_ok}/{len(termine)} geschrieben, Phase Terminiert"
            + (f". {hinweis}" if hinweis else "") + ".")
    kern.aktivitaet(session, vorgang.id, "termin", text, benutzer=benutzer)
    for ad_id in dict.fromkeys(t.ad_id for t in termine if t.ad_id):
        eigene = [t for t in termine if t.ad_id == ad_id]
        kern.benachrichtigen(session, [ad_id],
                             f"VOT-Termin terminiert {eigene[0].beginn:%d.%m. %H:%M}: "
                             f"{kunde.anzeige_name}, {kunde.ort or '?'}"
                             + (f" (+{len(eigene) - 1} weitere)" if len(eigene) > 1 else ""),
                             f"/lead-management/lead/{vorgang.id}", art="terminaenderung")
    session.flush()
    vorschlaege_cache_leeren()
    meldung = (f"Terminiert: {len(termine)} Objekttermin{'e' if len(termine) != 1 else ''} gebucht, "
               if mehrere else "Terminiert: ") \
        + ("eine Terminbestätigung für alle Objekte geplant" if bestaetigung == BESTAETIGUNG_EINE and len(termine) > 1
           else "Terminbestätigung geplant") \
        + f", Kalender {'geschrieben' if kalender_ok == len(termine) else 'übersprungen (Sync aus)'}, Phase Terminiert." \
        + (f" {hinweis}." if hinweis else "")
    return True, meldung


def _mail_geplant(session: Session, termin: VotTermin, vorlage_key: str) -> bool:
    from app.models import KommunikationLog
    return bool(session.query(KommunikationLog)
                .filter(KommunikationLog.termin_id == termin.id,
                        KommunikationLog.vorlage_key == vorlage_key,
                        KommunikationLog.status != "storniert").count())


def lead_mail_objekttermine(session: Session, vorgang: Vorgang) -> list[VotTermin]:
    from app import lead_mail
    return lead_mail.objekttermine_aktiv(session, vorgang)


# --- Konfliktprüfung manuelle Buchung (B7) ------------------------------------------

def viertelstunde(zeit: datetime | None, schritt: int = 15) -> datetime | None:
    """Kaufmännisch auf das Raster runden (Muster Projektierung v17)."""
    if zeit is None:
        return None
    minuten = zeit.hour * 60 + zeit.minute + zeit.second / 60
    gerundet = int((minuten + schritt / 2) // schritt) * schritt
    basis = zeit.replace(hour=0, minute=0, second=0, microsecond=0)
    return basis + timedelta(minutes=gerundet)


def konflikte(session: Session, ad_id: int, beginn: datetime,
              ende: datetime | None = None, ignorieren_id: int | None = None,
              lead_ort=None) -> dict:
    """Konflikte eines Wunschslots desselben AD: voll (harte Überlappung mit
    Tool-Terminen → Sperre), puffer (Fahrzeit-/Mindestpuffer verletzt →
    Warnung), outlook (nur bei kalender_sync an), arbeitszeit, kapazitaet."""
    from app import outlook_sync   # v33 (Phase 170): Belegt-Cache statt kalender.frei_belegt
    from app import routing
    ad = session.get(Benutzer, ad_id)
    profil = kern.ad_profil(session, ad_id)
    dauer = timedelta(minutes=profil.termin_dauer_min or 90)
    ende = ende or beginn + dauer
    puffer = puffer_minuten(session, profil)
    tag = beginn.replace(hour=0, minute=0, second=0, microsecond=0)
    termine = [t for t in _termine_je_ad(session, [ad_id], tag,
                                         tag + timedelta(days=1))[ad_id]
               if t.id != ignorieren_id]
    start_ort = ((profil.start_lat, profil.start_lon)
                 if profil.start_lat is not None else None)
    voll, puffer_konflikte = [], []
    for t in termine:
        t_ende = _ende(t, dauer)
        if t.beginn < ende and beginn < t_ende:
            voll.append(t)
            continue
        # Nachtrag 08.10.2026 (Antwort Andreas): Sperrzeit exakt von–bis – kein
        # Puffer davor/danach, Buchung direkt an der Grenze ist erlaubt
        if (t.typ or "vot") == SPERRZEIT_TYP:
            continue
        if lead_ort is not None and t.lat is not None:
            fahr = routing.fahrzeit(session, (t.lat, t.lon), lead_ort)["minuten"]
        elif lead_ort is not None and start_ort is not None and t.lat is None:
            fahr = 0.0
        else:
            fahr = 0.0
        noetig = max(puffer, fahr)
        abstand = ((beginn - t_ende) if t_ende <= beginn
                   else (t.beginn - ende)).total_seconds() / 60
        if abstand < noetig - 1e-6:
            puffer_konflikte.append((t, round(noetig)))
    outlook = []
    # v33 (PLAN_V20 Phase 170): Belegtzeiten aus dem Cache (nie Graph im Request)
    belegt = outlook_sync.belegt_fuer(session, ad, tag, tag + timedelta(days=1))
    if belegt:
        outlook = [(b_von, b_ende) for b_von, b_ende in belegt
                   if beginn < b_ende and b_von < ende]
    fenster = kern._arbeitszeiten_von_bis(profil, beginn)
    minute = beginn.hour * 60 + beginn.minute
    arbeitszeit_ok = fenster is not None and fenster[0] <= minute < fenster[1]
    vot_tag = [t for t in termine if (t.typ or "vot") == "vot"]
    kapazitaet_voll = len(vot_tag) >= (profil.max_termine_tag or 4)
    texte = []
    for t in voll:
        texte.append(f"Überschneidung mit Termin {t.beginn:%H:%M}–{_ende(t, dauer):%H:%M} "
                     f"({TERMIN_TYP_NAMEN_V4.get(t.typ or 'vot', t.typ)})")
    for t, noetig in puffer_konflikte:
        texte.append(f"Puffer zu Termin {t.beginn:%H:%M} unterschritten "
                     f"(nötig {noetig} Min = max(Mindestpuffer, Fahrzeit))")
    for b_von, b_ende in outlook:
        texte.append(f"Outlook belegt {b_von:%H:%M}–{b_ende:%H:%M}")
    if not arbeitszeit_ok:
        texte.append("außerhalb der AD-Arbeitszeit")
    if kapazitaet_voll:
        texte.append(f"Tageskapazität erreicht ({len(vot_tag)}/{profil.max_termine_tag or 4})")
    return {"voll": voll, "puffer": puffer_konflikte, "outlook": outlook,
            "arbeitszeit_ok": arbeitszeit_ok, "kapazitaet_voll": kapazitaet_voll,
            "texte": texte, "sperren": bool(voll),
            "warnen": bool(puffer_konflikte or outlook or not arbeitszeit_ok
                           or kapazitaet_voll)}


# --- Buchen mit Vertrag „vorgemerkt“ (B8) -------------------------------------------

def _vorgemerkte_aufraeumen(session: Session, vorgang_id: int, ausser_id: int,
                            objekt_id=None) -> None:
    """Ältere vorgemerkte VOT-Termine desselben Objekts (v31: nur desselben Objekts –
    jedes Objekt hat seinen eigenen vorgemerkten Termin) auf „verschoben“ setzen."""
    abfrage = (session.query(VotTermin)
               .filter(VotTermin.vorgang_id == vorgang_id,
                       VotTermin.status == STATUS_VORGEMERKT,
                       VotTermin.typ == "vot", VotTermin.id != ausser_id))
    neu = session.get(VotTermin, ausser_id)
    objekt_id = objekt_id or (neu.objekt_id if neu is not None else None)
    for alt in abfrage:
        if objekt_id and alt.objekt_id and alt.objekt_id != objekt_id:
            continue
        alt.status = "verschoben"


def umbuchung_nachziehen(session: Session, alt: VotTermin | None,
                         neu: VotTermin | None) -> None:
    """E4: Umbuchung behält die ICS-UID (SEQUENCE + 1), damit der Kunden-
    kalender den Eintrag aktualisiert statt zu verdoppeln."""
    if alt is None or neu is None or alt.id == neu.id:
        return
    if not alt.ics_uid:
        alt.ics_uid = f"friondo-vot-{alt.id}@friondo.de"
    neu.ics_uid = alt.ics_uid
    neu.ics_sequence = (alt.ics_sequence or 0) + 1
    session.flush()


def _ad_am_vorgang(session: Session, vorgang: Vorgang, ad_id: int, benutzer) -> None:
    if vorgang.ad_id != ad_id:
        lead_v2.ad_zuweisen(session, vorgang, ad_id, benutzer=benutzer, erzwingen=True)


def vot_buchen(session: Session, vorgang: Vorgang, ad_id: int, beginn: datetime,
               objekt=None, benutzer=None, quelle: str = "assistent",
               umweg: int | None = None, umbuchen_id: int | None = None) -> tuple[VotTermin | None, str]:
    """v31 (Phase 153): Vor-Ort-Termin für ein Objekt buchen – eigene Fassung von
    kern.termin_buchen mit Objektfeldern (objekt_id, Adresse und Koordinaten des
    Objekts): Termin, Umbuchung (alter Termin „verschoben“, Mails storniert,
    Terminänderung), Terminbestätigung (Vertriebler-Vorlage, {objektadresse}) +
    Erinnerung −24 h, Outlook, Phase Terminiert, Aktivität, Glocke an den AD."""
    from app import kalender as kalender_modul
    ad = session.get(Benutzer, ad_id)
    kunde = session.get(Kunde, vorgang.kunde_id)
    if ad is None or kunde is None:
        return None, "Außendienstler oder Kunde fehlt."
    objekt = objekt if objekt is not None else objekt_holen(session, vorgang, None)
    profil = kern.ad_profil(session, ad_id)
    ort = objekte_modul.ausfuehrungsort(session, objekt_id=objekt.id if objekt else None,
                                        vorgang=vorgang, kunde=kunde)
    koordinaten = objekt_ort(session, vorgang, objekt)
    alter_termin = session.get(VotTermin, umbuchen_id) if umbuchen_id else None
    termin = VotTermin(
        vorgang_id=vorgang.id, ad_id=ad_id, beginn=beginn,
        ende=beginn + timedelta(minutes=profil.termin_dauer_min or 90),
        adresse=ort.get("einzeilig", "")[:300],
        lat=koordinaten[0] if koordinaten else None, lon=koordinaten[1] if koordinaten else None,
        status="geplant", quelle=quelle, umweg_min=umweg,
        demo=bool(vorgang.demo), typ="vot", medium="vor_ort",
        objekt_id=objekt.id if objekt is not None else None,
        erstellt_von=benutzer.id if benutzer else None)
    session.add(termin)
    session.flush()
    mehrere = len(objekte_modul.objekte_fuer(session, vorgang.id)) > 1
    objekt_text = f" für {objekt.bezeichnung} ({ort.get('einzeilig', '')})" if mehrere and objekt is not None else ""
    if alter_termin is not None:
        alter_termin.status = "verschoben"
        kalender_modul.termin_loeschen(session, alter_termin)
        kern.geplante_mails_stornieren(session, alter_termin.id)
        kern.mail_planen(session, vorgang, "terminaenderung", termin=termin)
        kern.aktivitaet(session, vorgang.id, "termin",
                        f"Termin umgebucht auf {beginn:%d.%m.%Y %H:%M} bei {ad.name}{objekt_text}",
                        benutzer=benutzer)
    else:
        kern.aktivitaet(session, vorgang.id, "termin",
                        f"Termin gebucht {beginn:%d.%m.%Y %H:%M} bei {ad.name}{objekt_text}"
                        + (f" (+{umweg} Min)" if umweg is not None else ""),
                        benutzer=benutzer)
        kern.mail_planen(session, vorgang, "terminbestaetigung", termin=termin)
    kern.mail_planen(session, vorgang, "terminerinnerung", termin=termin,
                     geplant_am=beginn - timedelta(hours=24))
    kalender_modul.termin_schreiben(session, termin, vorgang, kunde, ad)
    vorgang.lead_phase = "terminiert"
    vorgang.terminiert_am = datetime.now()
    vorgang.naechste_aktion_am = None
    kern.benachrichtigen(session, [ad_id],
                         f"Neuer VOT-Termin {beginn:%d.%m. %H:%M}: "
                         f"{kunde.anzeige_name}, {kunde.ort or '?'}",
                         f"/lead-management/lead/{vorgang.id}", art="terminaenderung")
    session.flush()
    return termin, "Termin gebucht."


def termin_anlegen(session: Session, vorgang: Vorgang, ad_id: int, beginn: datetime,
                   benutzer=None, quelle: str = "assistent", umweg: int | None = None,
                   umbuchen_id: int | None = None, objekt_id=None) -> tuple[VotTermin | None, str, bool]:
    """Vor-Ort-Termin aus Assistent oder manueller Eingabe. Sind Pflicht-
    felder offen (lead_v2.pflichtfelder_offen), entsteht nur ein vorgemerkter
    Termin (ohne Mail, Kalender, Phasenwechsel) – „Terminierung“ in der Kartei
    (Phase 106) schaltet scharf. v31: bei mehr als einem Objekt wird ebenfalls nur
    vorgemerkt (ein Termin je Objekt, „Terminierung“ bucht alle) [ANNAHME]; sonst
    vot_buchen mit Objektfeldern; Umbuchung übernimmt das Objekt des alten Termins;
    Testphase → (None, TESTPHASE_HINWEIS, False). Liefert (termin, meldung, vorgemerkt)."""
    sperre = _gesperrt(session)
    if sperre:
        return None, sperre, False
    ad = session.get(Benutzer, ad_id)
    kunde = session.get(Kunde, vorgang.kunde_id)
    if ad is None or kunde is None:
        return None, "Außendienstler oder Kunde fehlt.", False
    alt = session.get(VotTermin, umbuchen_id) if umbuchen_id else None
    if objekt_id is None and alt is not None and alt.objekt_id:
        objekt_id = alt.objekt_id
    objekt = objekt_holen(session, vorgang, objekt_id)
    mehrere = len(objekte_modul.objekte_fuer(session, vorgang.id)) > 1
    offen = lead_v2.pflichtfelder_offen(session, kunde, vorgang)
    # Pflichtfeld Außendienst (Phase 157) gilt mit dem hier gewählten Vertriebler als
    # erfüllt (vormerken/vot_buchen weisen ihn dem Vorgang zu – _ad_am_vorgang)
    offen = [f for f in offen if str(f).lower() not in ("ad_id", "außendienst", "aussendienst")]
    nur_vormerken = (mehrere and (alt is None or alt.status == STATUS_VORGEMERKT))
    if (offen or nur_vormerken) and (alt is None or alt.status == STATUS_VORGEMERKT):
        termin, meldung = vormerken(session, vorgang, ad_id, beginn, objekt_id=objekt.id if objekt else None,
                                    benutzer=benutzer, quelle=quelle, umweg=umweg)
        if termin is None:
            return None, meldung, False
        if alt is not None and alt.id != termin.id:
            alt.status = "verschoben"
        if offen:
            meldung = ("Termin vorgemerkt – Terminierung in der Kartei abschließen "
                       f"(offen: {', '.join(offen)}).")
        session.flush()
        return termin, meldung, True
    umbuchen_echt = alt.id if (alt is not None and alt.status != STATUS_VORGEMERKT) else None
    termin, meldung = vot_buchen(session, vorgang, ad_id, beginn, objekt=objekt,
                                 benutzer=benutzer, quelle=quelle,
                                 umweg=umweg, umbuchen_id=umbuchen_echt)
    if termin is None:
        return None, meldung, False
    if umbuchen_echt:
        umbuchung_nachziehen(session, alt, termin)
    _vorgemerkte_aufraeumen(session, vorgang.id, termin.id, objekt_id=termin.objekt_id)
    _ad_am_vorgang(session, vorgang, ad_id, benutzer)
    session.flush()
    vorschlaege_cache_leeren()   # v25: Kalender geändert – Vorschläge neu rechnen
    return termin, meldung, False


# --- Vorab-Gespräch Telefon / Teams (H6, F12) ---------------------------------------

def vorab_personen(session: Session, typ: str) -> list[Benutzer]:
    """telefon: Außendienst/Handelsvertreter; online: Innendienst, Admin,
    Leadmanagement (Kollege mit Teams/Buchungslink)."""
    if typ == "telefon":
        return ad_basis(session)
    return [b for b in session.query(Benutzer)
            .filter(Benutzer.aktiv.is_(True)).order_by(Benutzer.name)
            if b.basisrolle in ("innendienst", "admin") or b.hat_rolle("leadmanagement")]


def vorab_anlegen(session: Session, vorgang: Vorgang, typ: str, person_id: int,
                  beginn: datetime | None, dauer_min: int | None = None,
                  benutzer=None, buchungslink_senden: bool = False
                  ) -> tuple[VotTermin | None, str]:
    """Vorab-Gespräch als Termin eigener Art (A-2): zählt in der Kollision,
    nicht in der Kapazität, ändert die Lead-Phase nicht. Telefon → Tool-
    Kalender + Outlook des Vertrieblers; Teams → optional Einladung mit dem
    Buchungslink des Kollegen (nur wenn benutzer.buchungslink gesetzt)."""
    from app import kalender as kalender_modul
    if typ not in VORAB_TYPEN:
        return None, "Unbekannte Terminart."
    # v31 (Phase 159, Entscheidung 13.10.2026): Vorab-Gespräche sind in der Testphase
    # ebenfalls gesperrt (kein Telefon-/Online-Termin, keine Buchungslink-Mail)
    sperre = _gesperrt(session)
    if sperre:
        return None, sperre
    person = session.get(Benutzer, person_id) if person_id else None
    kunde = session.get(Kunde, vorgang.kunde_id)
    if person is None or not person.aktiv or kunde is None:
        return None, "Ansprechpartner fehlt."
    if beginn is None and not (typ == "online" and buchungslink_senden):
        return None, "Datum und Uhrzeit sind Pflicht."
    dauer = dauer_min or _int(parameter(session, "vorab_dauer_min", "30"), 30)
    hinweise = []
    if buchungslink_senden and not (person.buchungslink or "").strip():
        buchungslink_senden = False
        hinweise.append(f"Kein Buchungslink bei {person.name} hinterlegt "
                        "(Benutzerverwaltung) – Einladung nicht geplant.")
        if beginn is None:
            return None, hinweise[0]
    termin = VotTermin(
        vorgang_id=vorgang.id, ad_id=person.id, beginn=beginn,
        ende=(beginn + timedelta(minutes=dauer)) if beginn else None,
        adresse="Telefon" if typ == "telefon" else "Microsoft Teams",
        status="geplant" if beginn else STATUS_VORGEMERKT, quelle="manuell",
        typ=typ, medium=TERMIN_MEDIEN.get(typ, typ), demo=bool(vorgang.demo),
        erstellt_von=benutzer.id if benutzer else None)
    session.add(termin)
    session.flush()
    name = TERMIN_TYP_NAMEN.get(typ, typ)
    if beginn is not None:
        k = konflikte(session, person.id, beginn, termin.ende)
        if k["voll"]:
            hinweise.append("Achtung: überschneidet sich mit einem Termin von "
                            f"{person.name} ({k['texte'][0]}).")
        kalender_modul.termin_schreiben(session, termin, vorgang, kunde, person)
    if buchungslink_senden:
        eintrag = kern.mail_planen(session, vorgang, "online_termin_einladung", termin=termin)
        if eintrag is None:
            hinweise.append("Kunde ohne E-Mail – Einladung nicht möglich.")
        else:
            hinweise.append("Einladung mit Buchungslink geplant.")
            kern.aktivitaet(session, vorgang.id, "termin",
                            f"Buchungslink von {person.name} an den Kunden geplant",
                            benutzer=benutzer)
    kern.aktivitaet(session, vorgang.id, "termin",
                    f"{name} mit {person.name}"
                    + (f" am {beginn:%d.%m.%Y %H:%M} ({dauer} Min)" if beginn
                       else " – Kunde wählt den Zeitpunkt über den Buchungslink"),
                    benutzer=benutzer)
    if beginn is not None:
        # v29 (Phase 141): Glocken-Art „terminaenderung“ – standardmäßig abgeschaltet
        kern.benachrichtigen(session, [person.id],
                             f"{name} {beginn:%d.%m. %H:%M}: {kunde.anzeige_name}"
                             f"{', ' + kunde.ort if kunde.ort else ''}",
                             f"/lead-management/lead/{vorgang.id}", art="terminaenderung")
    session.flush()
    vorschlaege_cache_leeren()   # v25: Vorab-Gespräche zählen in der Kollision
    return termin, " ".join(hinweise) or f"{name} eingetragen."


# --- Absage mit Storno-ICS und Ersatzkunde (E3, E4, F8) -----------------------------

def leitung_ids(session: Session) -> list[int]:
    """„Leitung“ für Glocken: Admins + Benutzer mit Rolle Leadmanagement."""
    return [b.id for b in session.query(Benutzer).filter(Benutzer.aktiv.is_(True))
            if b.basisrolle == "admin" or b.hat_rolle("leadmanagement")]


def absagen(session: Session, termin: VotTermin, grund: str, text: str = "",
            benutzer=None) -> tuple[bool, str]:
    """Termin absagen: VOT über kern.termin_no_show (Lead zurück auf
    Qualifiziert, Kalender gelöscht, Mails storniert, Glocke LM) plus
    Kundenmail terminabsage mit Storno-ICS (METHOD:CANCEL, gleiche UID).
    Vorab-Gespräche/vorgemerkte Termine: nur Status, Kalender, Aktivität."""
    from app import kalender as kalender_modul
    from app import lead_mail
    sperre = _gesperrt(session)
    if sperre:
        return False, sperre
    if termin.status not in BELEGT_STATUS:
        return False, "Termin ist nicht mehr aktiv."
    vorgang = session.get(Vorgang, termin.vorgang_id)
    kunde = session.get(Kunde, vorgang.kunde_id) if vorgang else None
    if vorgang is None or kunde is None:
        return False, "Vorgang fehlt."
    typ = termin.typ or "vot"
    if typ == "vot" and termin.status != STATUS_VORGEMERKT:
        kern.termin_no_show(session, termin, grund, text, status="abgesagt",
                            benutzer=benutzer)
        # v31 (Phase 153): Absage je Objekttermin – bleibt ein anderer Objekttermin
        # aktiv, bleibt der Lead in der Phase Terminiert
        weitere = [t for t in lead_mail.objekttermine_aktiv(session, vorgang) if t.id != termin.id]
        if weitere:
            vorgang.lead_phase = "terminiert"
            vorgang.naechste_aktion_am = None
        if kunde.email:
            if not termin.ics_uid:
                termin.ics_uid = f"friondo-vot-{termin.id}@friondo.de"
            termin.ics_sequence = (termin.ics_sequence or 0) + 1
            eintrag = kern.mail_planen(session, vorgang, "terminabsage", termin=termin)
            if eintrag is not None:
                eintrag.anhang_pfad = lead_mail.ics_erstellen(session, termin, vorgang,
                                                              methode="CANCEL")
        kern.benachrichtigen(
            session, set(leitung_ids(session)) | {vorgang.leadmanager_id},
            f"Termin abgesagt ({termin.beginn:%d.%m. %H:%M}): {kunde.anzeige_name} – "
            "Ersatzkunde für den freien Slot vorschlagen",
            f"/lead-management/termin/{termin.id}/ersatz", art="terminaenderung")   # v29
    else:
        termin.status = "abgesagt"
        termin.grund_text = (grund + (f" – {text}" if text else ""))[:500]
        kalender_modul.termin_loeschen(session, termin)
        kern.geplante_mails_stornieren(session, termin.id)
        kern.aktivitaet(session, vorgang.id, "termin",
                        f"{TERMIN_TYP_NAMEN.get(typ, typ)}"
                        f"{' (vorgemerkt)' if termin.status == STATUS_VORGEMERKT else ''}"
                        f" abgesagt: {termin.grund_text}", benutzer=benutzer)
        if vorgang.leadmanager_id:
            kern.benachrichtigen(session, [vorgang.leadmanager_id],
                                 f"{TERMIN_TYP_NAMEN.get(typ, typ)} abgesagt: "
                                 f"{kunde.anzeige_name}",
                                 f"/lead-management/lead/{vorgang.id}", art="terminaenderung")   # v29
    session.flush()
    vorschlaege_cache_leeren()   # v25: Slot frei – Vorschläge neu rechnen
    return True, "Termin abgesagt."


def slot_frei_melden(session: Session, termin: VotTermin, benutzer=None) -> None:
    """E3: Nach einer Umbuchung ist der alte Slot frei – Glocke an Leitung und
    Leadmanager (ohne den Handelnden) mit Link auf den Ersatzkunden-Dialog."""
    vorgang = session.get(Vorgang, termin.vorgang_id)
    kunde = session.get(Kunde, vorgang.kunde_id) if vorgang else None
    if vorgang is None or kunde is None or termin.beginn is None:
        return
    empfaenger = set(leitung_ids(session)) | {vorgang.leadmanager_id}
    if benutzer is not None:
        empfaenger.discard(benutzer.id)
    kern.benachrichtigen(
        session, empfaenger,
        f"Slot frei durch Umbuchung ({termin.beginn:%d.%m. %H:%M}): {kunde.anzeige_name} – "
        "Ersatzkunde für den freien Slot vorschlagen",
        f"/lead-management/termin/{termin.id}/ersatz", art="terminaenderung")   # v29


def radius_stufen(session: Session) -> list[float]:
    roh = parameter(session, "ersatz_radius_stufen", "5; 10")
    stufen = []
    for teil in roh.replace(",", ";").split(";"):
        try:
            stufen.append(float(teil.strip()))
        except ValueError:
            continue
    return sorted(set(stufen)) or [5.0, 10.0]


def ersatz_kandidaten(session: Session, termin: VotTermin) -> dict:
    """Offene kontaktierte Leads (Phase qualifiziert zuerst, dann
    in_kontaktierung mit erreicht_am – beide tragen seit v25 das Label
    „Kontaktiert“) im Radius um den freigewordenen Slot; Stufen 5 → 10 km
    bis ≥ ersatz_min_treffer Treffer; ältere (≥ ersatz_alter_tage) bevorzugt,
    Score nur bei score_aktiv = an berücksichtigt; Begründung je Kandidat
    (Entfernung, Alter, [Klasse], Phase, Wunschzeit)."""
    from app import leadmanagement_logik, routing
    logik = leadmanagement_logik.hole_logik()
    score_an = lead_v2.score_aktiv(session)

    def _label(phase: str) -> str:
        z = logik.status_zeile(phase)
        return z.label if z and z.label else phase
    vorgang = session.get(Vorgang, termin.vorgang_id)
    ort = ((termin.lat, termin.lon) if termin.lat is not None
           else ((vorgang.lat, vorgang.lon) if vorgang and vorgang.lat is not None else None))
    stufen = radius_stufen(session)
    alter_tage = _int(parameter(session, "ersatz_alter_tage", "14"), 14)
    min_treffer = _int(parameter(session, "ersatz_min_treffer", "3"), 3)
    ergebnis = {"kandidaten": [], "radius": stufen[-1] if stufen else None,
                "stufen": stufen, "ort": ort, "alter_tage": alter_tage}
    if ort is None:
        return ergebnis
    belegt_ids = {t.vorgang_id for t in session.query(VotTermin.vorgang_id)
                  .filter(VotTermin.status.in_(BELEGT_STATUS), VotTermin.typ == "vot")}
    abfrage = (session.query(Vorgang)
               .filter(Vorgang.lead_phase.in_(("qualifiziert", "in_kontaktierung")),
                       Vorgang.lat.isnot(None), Vorgang.id != termin.vorgang_id))
    if kern.demo_aktiv(session):
        abfrage = abfrage.filter(Vorgang.demo.is_(True))
    pool = []
    jetzt = datetime.now()
    for v in abfrage:
        if v.id in belegt_ids:
            continue
        if v.lead_phase == "in_kontaktierung" and v.erreicht_am is None:
            continue
        km = routing.luftlinie_km(ort, (v.lat, v.lon))
        if km > stufen[-1]:
            continue
        alter = (jetzt - v.eingang_am).days if v.eingang_am else 0
        pool.append((v, km, alter))
    gewaehlt, radius = [], stufen[-1]
    for stufe in stufen:
        gewaehlt = [p for p in pool if p[1] <= stufe]
        radius = stufe
        if len(gewaehlt) >= min_treffer:
            break
    klasse_bonus = {"A": 15, "B": 5} if score_an else {}
    kandidaten_liste = []
    for v, km, alter in gewaehlt:
        kunde = session.get(Kunde, v.kunde_id)
        bevorzugt = alter >= alter_tage
        punkte = (km * 2 - (20 if bevorzugt else 0)
                  - klasse_bonus.get(v.score_klasse or "", 0)
                  + (10 if v.lead_phase == "in_kontaktierung" else 0))
        gruende = [f"{km:.1f} km Luftlinie",
                   f"{alter} Tage alt" + (" (bevorzugt)" if bevorzugt else "")]
        if score_an:
            gruende.append(f"Klasse {v.score_klasse or '–'}")
        # v25: Label aus dem Blatt Status (beide Phasen „Kontaktiert“), die
        # interne Phase bleibt als Zusatz erkennbar
        gruende.append(f"Phase {_label('qualifiziert')} (qualifiziert)"
                       if v.lead_phase == "qualifiziert"
                       else f"Phase {_label('in_kontaktierung')} (erreicht)")
        wunsch = kern.wunschzeiten_liste(v)
        if wunsch:
            gruende.append("Wunschzeit " + ", ".join(wunsch))
        kandidaten_liste.append({"vorgang": v, "kunde": kunde, "km": round(km, 1),
                                 "alter": alter, "bevorzugt": bevorzugt,
                                 "punkte": round(punkte, 1),
                                 "begruendung": " · ".join(gruende),
                                 "sparten": sparten_des_kunden(kunde)})
    kandidaten_liste.sort(key=lambda k: (k["punkte"], k["km"]))
    ergebnis.update(kandidaten=kandidaten_liste, radius=radius)
    return ergebnis


# --- Terminbestätigung erneut (A-9) --------------------------------------------------

def bestaetigung_erneut(session: Session, termin: VotTermin, benutzer=None,
                        termine=None, zusammen: bool = False) -> tuple[bool, str]:
    """Gleiche UID, SEQUENCE + 1, Vorlage terminbestaetigung neu planen. v31 (Phase
    153): bei mehreren Objekten wählt der Dialog die Termine (`termine`); `zusammen`
    = eine Mail terminbestaetigung_objekte mit {objektliste} und ICS je Objekt, sonst
    je gewähltem Termin eine Bestätigung mit {objektadresse}."""
    ziele = [t for t in (termine or [termin]) if t is not None]
    if not ziele:
        return False, "Kein Termin gewählt."
    for t in ziele:
        if t.status not in AKTIVE_STATUS or (t.typ or "vot") != "vot":
            return False, "Nur für aktive Vor-Ort-Termine möglich."
    vorgang = session.get(Vorgang, ziele[0].vorgang_id)
    kunde = session.get(Kunde, vorgang.kunde_id) if vorgang else None
    if kunde is None or not kunde.email:
        return False, "Kunde ohne E-Mail-Adresse."
    for t in ziele:
        if not t.ics_uid:
            t.ics_uid = f"friondo-vot-{t.id}@friondo.de"
        t.ics_sequence = (t.ics_sequence or 0) + 1
    if zusammen and len(ziele) > 1:
        eintrag = kern.mail_planen(session, vorgang, "terminbestaetigung_objekte", termin=ziele[0])
        ok = eintrag is not None
        kern.aktivitaet(session, vorgang.id, "termin",
                        f"Terminbestätigung für {len(ziele)} Objekte erneut geplant (ICS SEQUENCE "
                        + ", ".join(str(t.ics_sequence) for t in ziele) + ")", benutzer=benutzer)
    else:
        ok = False
        for t in ziele:
            eintrag = kern.mail_planen(session, vorgang, "terminbestaetigung", termin=t)
            ok = ok or eintrag is not None
            kern.aktivitaet(session, vorgang.id, "termin",
                            f"Terminbestätigung erneut geplant (ICS SEQUENCE {t.ics_sequence})"
                            + (f" – {t.adresse}" if len(ziele) > 1 and t.adresse else ""),
                            benutzer=benutzer)
    session.flush()
    return ok, ("Terminbestätigung erneut geplant." if len(ziele) == 1
                else f"Terminbestätigung für {len(ziele)} Objekttermine erneut geplant"
                     + (" (eine Mail)." if zusammen else " (je Objekt eine Mail)."))


# --- Kalender (Woche je AD, alle Terminarten + vorgemerkt) --------------------------

def kalender_woche(session: Session, ad_ids: list[int], start=None) -> dict:
    from app import outlook_sync   # v33 (Phase 170): Belegt-Cache statt kalender.frei_belegt
    jetzt = datetime.now()
    start = start or (jetzt - timedelta(days=jetzt.weekday()))
    start = start.replace(hour=0, minute=0, second=0, microsecond=0)
    tage = [start + timedelta(days=i) for i in range(KALENDER_TAGE)]   # v31: Mo–Fr
    raster = {}
    termine_je_ad = _termine_je_ad(session, [a for a in ad_ids if a], tage[0],
                                   tage[-1] + timedelta(days=1))
    for ad_id in ad_ids:
        if not ad_id:
            continue
        ad = session.get(Benutzer, ad_id)
        termine = termine_je_ad.get(ad_id, [])
        # v33 (PLAN_V20 Phase 170): Belegtzeiten aus dem Cache (nie Graph im Request)
        belegt = outlook_sync.belegt_fuer(session, ad, tage[0],
                                          tage[-1] + timedelta(days=1))
        raster[ad_id] = {
            "termine": {t.date(): [x for x in termine if x.beginn.date() == t.date()]
                        for t in tage},
            "belegt": {t.date(): [b for b in (belegt or []) if b[0].date() == t.date()]
                       for t in tage},
        }
    return {"tage": tage, "je_ad": raster}


def hv_nur_eigene(session: Session, benutzer) -> int | None:
    """Handelsvertreter rechnen/sehen nur den eigenen Kalender (G2) – v35 (Phase 185):
    bei Gruppen die Kalender der Gruppe; diese Funktion bleibt als Kennzeichen „ist
    Handelsvertreter“ (eigene ID) für „Weitere Kalender“ (keine) und Rückfälle;
    Buchungs-/Sichtprüfungen nutzen hv_gruppe_ids / hv_ad_erlaubt."""
    if benutzer is not None and lead_v2.ist_handelsvertreter(session, benutzer):
        return benutzer.id
    return None


def hv_gruppe_ids(session: Session, benutzer) -> set | None:
    """v35 (PLAN_LEAD_V6 Phase 185): Kalender, die ein Handelsvertreter sehen und buchen
    darf = seine Gruppe (lead_v2.hv_gruppe_fuer: René → {René}, Simons Gruppe → Simon +
    Mitglieder); None für Innendienst/Admin/angestellte AD (kein Filter)."""
    if benutzer is None or not lead_v2.ist_handelsvertreter(session, benutzer):
        return None
    return lead_v2.hv_gruppe_fuer(session, benutzer.id) or {benutzer.id}


def hv_ad_erlaubt(session: Session, benutzer, ad_id) -> bool:
    """Darf dieser Benutzer auf den Kalender von ad_id buchen/umbuchen? Nicht-HV immer;
    Handelsvertreter nur innerhalb der eigenen Gruppe (v35)."""
    gruppe = hv_gruppe_ids(session, benutzer)
    if gruppe is None:
        return True
    try:
        return int(ad_id) in gruppe
    except (TypeError, ValueError):
        return False


HV_GRUPPE_KALENDER_TEXT = "Handelsvertreter buchen nur Kalender der eigenen Gruppe."


# --- v29 (PLAN_LEAD_V4 Phase 143): Sperrzeiten der Handelsvertreter [OFFEN 3] -----------

def sperrzeiten_liste(session: Session, benutzer_id: int, ab: datetime | None = None,
                      bis: datetime | None = None) -> list:
    """Sperrzeiten (VotTermin typ sperrzeit) eines Vertrieblers, chronologisch."""
    abfrage = (session.query(VotTermin)
               .filter(VotTermin.ad_id == benutzer_id, VotTermin.typ == SPERRZEIT_TYP,
                       VotTermin.status == "geplant"))
    if ab is not None:
        abfrage = abfrage.filter(VotTermin.ende >= ab)
    if bis is not None:
        abfrage = abfrage.filter(VotTermin.beginn < bis)
    return abfrage.order_by(VotTermin.beginn).all()


def sperrzeiten_uebersicht(session: Session, vertreter: list, ab: datetime | None = None) -> dict:
    """Nachtrag 08.10.2026 (Antwort Andreas): kommende Sperrzeiten je
    Handelsvertreter für die HV-Übersicht des Innendienstes –
    {"je_hv": [{"hv": Benutzer, "sperrzeiten": [VotTermin]}] (nur Vertreter mit
    Einträgen), "namen": {benutzer_id: Name der Ersteller}, "anzahl": n}."""
    ab = ab or datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    je_hv, ersteller = [], set()
    for hv in vertreter:
        liste = sperrzeiten_liste(session, hv.id, ab=ab)
        if not liste:
            continue
        je_hv.append({"hv": hv, "sperrzeiten": liste})
        ersteller.update(sz.erstellt_von for sz in liste
                         if sz.erstellt_von and sz.erstellt_von != sz.ad_id)
    namen = ({b.id: b.name for b in session.query(Benutzer).filter(Benutzer.id.in_(ersteller))}
             if ersteller else {})
    return {"je_hv": je_hv, "namen": namen,
            "anzahl": sum(len(e["sperrzeiten"]) for e in je_hv)}


def sperrzeit_fremd_erlaubt(benutzer) -> bool:
    """Nachtrag 08.10.2026 (Antwort Andreas): Admin und Innendienst dürfen
    Sperrzeiten eines Handelsvertreters eintragen (löschen durften sie schon)."""
    return benutzer is not None and getattr(benutzer, "rolle", "") in ("admin", "innendienst")


def sperrzeit_anlegen(session: Session, benutzer, datum, von: str, bis: str,
                      bemerkung: str = "", ziel=None) -> tuple[VotTermin | None, str]:
    """Sperrzeit im Tool-Kalender des Handelsvertreters (Zwischenlösung bis
    [OFFEN 3]): Datum, von/bis (HH:MM, 15-Minuten-Raster), Bemerkung. Zählt im
    Assistenten als belegter Slot (Kollision exakt von–bis, Nachtrag
    08.10.2026 – kein Puffer), nicht in der Tageskapazität; kein Outlook, keine
    Kundenmail, kein Vorgang (vorgang_id 0).
    Nachtrag 08.10.2026 (Antwort Andreas): `ziel` = Handelsvertreter, für den die
    Sperrzeit gilt (Standard: der Handelnde selbst). Admin/Innendienst dürfen für
    einen HV eintragen: erstellt_von = Innendienst (Liste zeigt „eingetragen von
    …“), Glocke art terminaenderung an den HV (standardmäßig gesperrt)."""
    if benutzer is None:
        return None, "Kein Benutzer."
    ziel = ziel if ziel is not None else benutzer
    fremd = ziel.id != benutzer.id
    if fremd:
        if not sperrzeit_fremd_erlaubt(benutzer):
            return None, "Nur die eigene Sperrzeit kann eingetragen werden."
        if not lead_v2.ist_handelsvertreter(session, ziel):
            return None, f"{ziel.name} ist kein Handelsvertreter (Kennzeichen „terminiert selbst“ fehlt)."
    if isinstance(datum, str):
        try:
            datum = datetime.strptime(datum.strip()[:10], "%Y-%m-%d").date()
        except ValueError:
            return None, "Datum nicht lesbar."
    if isinstance(datum, datetime):
        datum = datum.date()

    def _zeit(text: str) -> int | None:
        text = (text or "").strip()[:5]
        try:
            h, m = text.split(":")
            minuten = int(h) * 60 + int(m)
        except (ValueError, AttributeError):
            return None
        if not 0 <= minuten <= 24 * 60:
            return None
        return int(round(minuten / KALENDER_RASTER_MIN) * KALENDER_RASTER_MIN)
    von_min, bis_min = _zeit(von), _zeit(bis)
    if von_min is None or bis_min is None:
        return None, "Uhrzeit von/bis im Format HH:MM angeben."
    if bis_min <= von_min:
        return None, "Die Sperrzeit muss nach dem Beginn enden."
    basis = datetime(datum.year, datum.month, datum.day)
    beginn, ende = basis + timedelta(minutes=von_min), basis + timedelta(minutes=bis_min)
    if ende < datetime.now():
        return None, "Die Sperrzeit liegt in der Vergangenheit."
    for alt in sperrzeiten_liste(session, ziel.id, ab=basis, bis=basis + timedelta(days=1)):
        if alt.beginn < ende and beginn < alt.ende:
            return None, (f"Überschneidung mit der Sperrzeit "
                          f"{alt.beginn:%H:%M}–{alt.ende:%H:%M}.")
    termin = VotTermin(vorgang_id=SPERRZEIT_VORGANG_ID, ad_id=ziel.id, beginn=beginn,
                       ende=ende, adresse="", status="geplant", quelle="manuell",
                       typ=SPERRZEIT_TYP, medium="", demo=False,
                       grund_text=(bemerkung or "").strip()[:500],
                       erstellt_von=benutzer.id)
    session.add(termin)
    session.flush()
    vorschlaege_cache_leeren()      # Slots geändert – Vorschläge/Kalender neu rechnen
    zeitraum = f"{beginn:%d.%m.%Y %H:%M}–{ende:%H:%M}"
    if fremd:
        # Verlauf für den Handelsvertreter: Glocke (Art terminaenderung, Standard
        # gesperrt) – die Liste in „Meine Termine“ zeigt „eingetragen von …“
        kern.benachrichtigen(session, [ziel.id],
                             f"Sperrzeit von {benutzer.name} eingetragen: {zeitraum}"
                             + (f" ({termin.grund_text})" if termin.grund_text else ""),
                             "/lead-management/dashboard#sperrzeiten", art="terminaenderung")
        return termin, f"Sperrzeit {zeitraum} für {ziel.name} eingetragen (von {benutzer.name})."
    return termin, f"Sperrzeit {zeitraum} eingetragen."


def sperrzeit_loeschen(session: Session, termin_id: int, benutzer) -> tuple[bool, str]:
    """Nur die eigene Sperrzeit (bzw. Admin/Innendienst) – sofort entfernt."""
    termin = session.get(VotTermin, termin_id)
    if termin is None or termin.typ != SPERRZEIT_TYP:
        return False, "Sperrzeit nicht gefunden."
    if benutzer is None or (termin.ad_id != benutzer.id
                            and not sperrzeit_fremd_erlaubt(benutzer)):
        return False, "Nur die eigene Sperrzeit kann entfernt werden."
    session.delete(termin)
    session.flush()
    vorschlaege_cache_leeren()
    return True, "Sperrzeit entfernt."


# --- v29 (Phase 143): „Weitere Kalender“ je Nutzer ---------------------------------------

def weitere_kalender_holen(session: Session, benutzer) -> list[int]:
    """Gemerkte Auswahl des Nutzers (benutzer_einstellungen Key assistent_kalender)."""
    if benutzer is None:
        return []
    werte = lead_v2.einstellung_holen(session, benutzer.id, EINSTELLUNG_WEITERE, []) or []
    return [int(w) for w in werte if str(w).isdigit()] if isinstance(werte, list) else []


def weitere_kalender_setzen(session: Session, benutzer, ids) -> list[int]:
    """Auswahl speichern (nur aktive Vertriebler aus ad_basis); liefert die Liste."""
    erlaubt = {b.id for b in ad_basis(session)}
    sauber = []
    for wert in ids or []:
        try:
            nr = int(wert)
        except (TypeError, ValueError):
            continue
        if nr in erlaubt and nr not in sauber:
            sauber.append(nr)
    lead_v2.einstellung_setzen(session, benutzer.id, EINSTELLUNG_WEITERE, sauber)
    return sauber


def weitere_kalender_wahl(session: Session, kandidaten_ids, benutzer) -> list[dict]:
    """Alle aktiven Vertriebler (AD und HV), die nicht zum Kandidatenkreis
    gehören – Aufklappmenü „Weitere Kalender“; Handelsvertreter sehen nur den
    eigenen Kalender (leere Auswahl)."""
    if hv_nur_eigene(session, benutzer):
        return []
    profile = {p.benutzer_id: p for p in session.query(AdProfil)}
    gewaehlt = set(weitere_kalender_holen(session, benutzer))
    wahl = []
    for b in ad_basis(session, profile):
        if b.id in set(kandidaten_ids or []):
            continue
        profil = profile.get(b.id)
        wahl.append({"id": b.id, "name": b.name,
                     "hv": bool(profil is not None and profil.terminiert_selbst),
                     "gewaehlt": b.id in gewaehlt})
    return wahl


def ausschluss_grund(vorfilter: dict, ad_id: int) -> str:
    """Grund, warum ein AD nicht im Kandidatenkreis ist (Kompetenz/Kanal/HV …)."""
    for a in vorfilter.get("ausgeschlossen", []):
        if a["ad"].id == ad_id:
            return a["grund"]
    return "nicht in der Vorauswahl"


# --- v29 (Phase 143): Kalenderansicht des Assistenten (kalender.json) --------------------

def _woche_start(wert, standard: datetime) -> datetime:
    """Montag 00:00 der Woche von `wert` (YYYY-MM-DD / date / datetime), sonst Standard."""
    tag = None
    if isinstance(wert, datetime):
        tag = wert
    elif isinstance(wert, date):
        tag = datetime(wert.year, wert.month, wert.day)
    elif isinstance(wert, str) and wert.strip():
        try:
            tag = datetime.strptime(wert.strip()[:10], "%Y-%m-%d")
        except ValueError:
            tag = None
    if tag is None:
        tag = standard
    tag = tag.replace(hour=0, minute=0, second=0, microsecond=0)
    return tag - timedelta(days=tag.weekday())


def _iso(zeit: datetime | None) -> str:
    return zeit.strftime("%Y-%m-%dT%H:%M") if zeit else ""


def kalender_json(session: Session, vorgang: Vorgang, benutzer=None, woche=None,
                  neu: bool = False, jetzt: datetime | None = None, objekt_id=None,
                  ohne_ad_id: int | None = None) -> dict:
    """Antwort für GET /lead-management/lead/{id}/termin/kalender.json?woche=…
    (v29, Phase 143): Wochenansicht Mo–Sa im 15-Minuten-Raster mit einer Spalte
    je Kandidat des Assistenten (plus „Weitere Kalender“ des Nutzers, grau
    „außerhalb der Vorauswahl“): Arbeitszeiten je Tag (AD-Profil), Tool-Termine
    aller Arten (inkl. Sperrzeiten, vorgemerkt), Outlook-Belegt nur bei
    kalender_sync = an und nie für Handelsvertreter, die Vorschläge als
    markierte Slots (Vorschlag 1 = Ideal). Standardwoche = Woche des ersten
    Vorschlags. Sitzungsdisziplin v27: alle Daten lesen → Sitzung freigeben →
    Outlook-Abruf → Antwort (kein Zurückschreiben). Cache 10 Minuten je Lead,
    Sicht, Woche und Auswahl; neu=True erzwingt."""
    from app import kalender as kalender_modul
    from app import outlook_sync   # v33 (Phase 170): Belegt-Cache statt kalender.frei_belegt
    from app.db import verbindung_freigeben
    jetzt = jetzt or datetime.now()
    hv_id = hv_nur_eigene(session, benutzer)
    objekt = objekt_holen(session, vorgang, objekt_id)
    sicht = (f"hv{hv_id}" if hv_id else "id") + (f"-o{objekt.id}" if objekt is not None else "") \
        + (f"-x{ohne_ad_id}" if ohne_ad_id else "")
    weitere = [] if hv_id else weitere_kalender_holen(session, benutzer)
    # Vorschläge (gecacht, derselbe Kandidatenkreis) – bestimmen die Standardwoche
    vorschlaege_antwort = vorschlaege_json(session, vorgang, benutzer=benutzer, jetzt=jetzt,
                                           objekt_id=objekt.id if objekt is not None else None,
                                           ohne_ad_id=ohne_ad_id)
    liste = vorschlaege_antwort.get("vorschlaege") or []
    standard = datetime.strptime(liste[0]["beginn"], "%Y-%m-%dT%H:%M") if liste else jetzt
    start = _woche_start(woche, standard)
    schluessel = (sicht, start.strftime("%Y-%m-%d"), tuple(weitere))
    if neu:
        kalender_cache.get(vorgang.id, {}).pop(schluessel, None)
    eintrag = kalender_cache.get(vorgang.id, {}).get(schluessel)
    if eintrag is not None and (jetzt - eintrag[0]).total_seconds() < VORSCHLAEGE_CACHE_SEKUNDEN:
        antwort = dict(eintrag[1])
        antwort["aus_cache"] = True
        return antwort
    tage = [start + timedelta(days=i) for i in range(KALENDER_TAGE)]   # v31 (Phase 158): Mo–Fr
    ende_woche = tage[-1] + timedelta(days=1)
    vorfilter = kandidaten(session, vorgang, benutzer=benutzer, objekt=objekt, ohne_ad_id=ohne_ad_id,
                           horizont_bis=tage[-1].date())
    kandidaten_ids = [k["ad"].id for k in vorfilter["kandidaten"]]
    spalten_ids = list(kandidaten_ids)
    for nr in weitere:
        if nr not in spalten_ids:
            spalten_ids.append(nr)
    profile = {p.benutzer_id: p for p in session.query(AdProfil)}
    personen = {b.id: b for b in session.query(Benutzer).filter(Benutzer.id.in_(spalten_ids or [0]))}
    termine_je_ad = _termine_je_ad(session, spalten_ids, tage[0], ende_woche) if spalten_ids else {}
    vorgang_ids = {x.vorgang_id for ts in termine_je_ad.values() for x in ts if x.vorgang_id}
    vorgaenge = ({v.id: v for v in session.query(Vorgang).filter(Vorgang.id.in_(vorgang_ids))}
                 if vorgang_ids else {})
    kunden = ({k.id: k for k in session.query(Kunde)
               .filter(Kunde.id.in_({v.kunde_id for v in vorgaenge.values()} or {0}))}
              if vorgaenge else {})
    sync_an = kalender_modul.aktiv(session)
    spalten = []
    raster_von, raster_bis = 24 * 60, 0
    for ad_id in spalten_ids:
        person = personen.get(ad_id)
        if person is None:
            continue
        profil = kern.ad_profil(session, ad_id)
        echt = profile.get(ad_id)
        ist_hv = bool(echt is not None and echt.terminiert_selbst)
        arbeitszeiten = {}
        for tag in tage:
            zeiten = kern._arbeitszeiten_von_bis(profil, tag)
            arbeitszeiten[tag.strftime("%Y-%m-%d")] = list(zeiten) if zeiten else None
            if zeiten:
                raster_von, raster_bis = min(raster_von, zeiten[0]), max(raster_bis, zeiten[1])
        eintraege = []
        for x in termine_je_ad.get(ad_id, []):
            if x.beginn is None:
                continue
            dauer = timedelta(minutes=profil.termin_dauer_min or 90)
            v = vorgaenge.get(x.vorgang_id)
            k = kunden.get(v.kunde_id) if v else None
            typ = x.typ or "vot"
            if typ == SPERRZEIT_TYP:
                text = "Sperrzeit" + (f": {x.grund_text}" if x.grund_text else "")
            else:
                text = (k.anzeige_name if k else "Termin") + (f", {k.ort}" if k and k.ort else "")
            eintraege.append({"id": x.id, "beginn": _iso(x.beginn), "ende": _iso(_ende(x, dauer)),
                              "typ": typ, "typ_name": TERMIN_TYP_NAMEN_V4.get(typ, typ),
                              "status": x.status, "text": text,
                              "vorgang_id": x.vorgang_id if typ != SPERRZEIT_TYP else None,
                              "eigener": bool(x.vorgang_id == vorgang.id)})
        spalten.append({"ad_id": ad_id, "name": person.name,
                        "kandidat": ad_id in kandidaten_ids, "hv": ist_hv,
                        "grund": "" if ad_id in kandidaten_ids else ausschluss_grund(vorfilter, ad_id),
                        "arbeitszeiten": arbeitszeiten, "termine": eintraege, "belegt": [],
                        "outlook": bool(sync_an and not ist_hv)})
    if raster_von >= raster_bis:
        raster_von, raster_bis = 8 * 60, 18 * 60
    raster_von = max(0, (raster_von // 60) * 60)
    raster_bis = min(24 * 60, -(-raster_bis // 60) * 60)
    hinweise = []
    if any(sp["hv"] for sp in spalten):
        hinweise.append("Handelsvertreter: nur Tool-Termine und Sperrzeiten (kein Outlook).")
    # v27-Sitzungsdisziplin: alles gelesen – Verbindung freigeben, dann Outlook (Netz)
    verbindung_freigeben(session)
    if sync_an:
        for sp in spalten:
            if not sp["outlook"]:
                continue
            # v33 (PLAN_V20 Phase 170): Belegtzeiten aus dem Cache (nie Graph im Request)
            belegt = outlook_sync.belegt_fuer(session, personen[sp["ad_id"]], tage[0], ende_woche)
            if belegt is None:
                sp["outlook"] = False
                continue
            sp["belegt"] = [{"beginn": _iso(b_von), "ende": _iso(b_ende)} for b_von, b_ende in belegt
                            if b_von < ende_woche and b_ende > tage[0]]
    antwort = {
        "vorgang_id": vorgang.id, "woche": start.strftime("%Y-%m-%d"),
        "woche_text": f"{tage[0]:%d.%m.} – {tage[-1]:%d.%m.%Y}",
        "vorherige": (start - timedelta(days=7)).strftime("%Y-%m-%d"),
        "naechste": (start + timedelta(days=7)).strftime("%Y-%m-%d"),
        "tage": [{"datum": tag.strftime("%Y-%m-%d"), "label": _wochentag_kurz(tag)} for tag in tage],
        "raster": {"von": raster_von, "bis": raster_bis, "schritt": KALENDER_RASTER_MIN},
        "spalten": spalten, "kandidaten": kandidaten_ids, "weitere": weitere,
        "vorschlaege": [{"nr": i + 1, "ad_id": v["ad_id"], "beginn": v["beginn"],
                         "ende": v.get("ende", ""), "ideal": bool(v.get("ideal"))}
                        for i, v in enumerate(liste)],
        "status": vorschlaege_antwort.get("status", "ok"),
        "buchbar": vorschlaege_antwort.get("buchbar", True),
        "hinweise": hinweise, "sync": sync_an, "hv": bool(hv_id),
        "berechnet_um": jetzt.strftime("%H:%M"), "aus_cache": False,
    }
    kalender_cache.setdefault(vorgang.id, {})[schluessel] = (jetzt, dict(antwort))
    return antwort


def _wochentag_kurz(tag: datetime) -> str:
    from app.templating import de_datum
    return de_datum(tag, "%a %d.%m.")
