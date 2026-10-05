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

import json
from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from app import lead_v2
from app import leadmanagement as kern
from app.models import (AdProfil, Benutzer, Kunde, Vorgang, VotTermin,
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


def vorschlaege_cache_leeren(vorgang_id: int | None = None) -> None:
    """Cache der Terminvorschläge leeren – für einen Lead (Adressänderung in
    der Kartei) oder komplett (vorgang_id=None, z. B. nach einer Buchung)."""
    if vorgang_id is None:
        vorschlaege_cache.clear()
    else:
        vorschlaege_cache.pop(int(vorgang_id), None)


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


def kandidaten(session: Session, vorgang: Vorgang, nur_ad_id: int | None = None,
               benutzer=None) -> dict:
    """Vorfilterung (E2). Ausschluss: Terminierung inaktiv, Handelsvertreter
    (v25: nur zugelassen, wenn benutzer.id == hv.id – „Handelsvertreter
    terminieren ihre Leads selbst“; manuelle Buchung bleibt möglich),
    Kanal-Regel, Produktkompetenz (lead_v2.kompetenz_passt). Abwertung:
    Gebiet (+20). Handelsvertreter sehen nur den eigenen Kalender. Liegt der
    Lead bei einem HV und fragt nicht dieser selbst, steht in hv_lead/
    hv_hinweis der Hinweis für den Innendienst."""
    kunde = session.get(Kunde, vorgang.kunde_id)
    sparten = sparten_des_kunden(kunde)
    objektart = (kunde.objektart or "") if kunde else ""
    plz = (kunde.plz or "").strip() if kunde else ""
    kanal = (kunde.vertriebskanal or "").strip() if kunde else ""
    regel = kanal_regel(session)
    kanal_ids = regel.get(kanal.lower()) if kanal else None
    if benutzer is not None and lead_v2.ist_handelsvertreter(session, benutzer):
        nur_ad_id = benutzer.id
    profile = {p.benutzer_id: p for p in session.query(AdProfil)}
    namen = {b.id: b.name for b in session.query(Benutzer)}
    benutzer_id = getattr(benutzer, "id", None)
    hv_lead = hv_des_vorgangs(session, vorgang, profile)
    if hv_lead is not None and hv_lead.id == benutzer_id:
        hv_lead = None   # der Vertreter selbst: normale Vorschläge (nur eigener Kalender)
    ergebnis, ausgeschlossen = [], []
    for ad in ad_basis(session, profile):
        if nur_ad_id and ad.id != nur_ad_id:
            continue
        profil = profile.get(ad.id)
        grund_aus = None
        manuell_erlaubt = False
        gruende = []
        if profil is not None and not profil.aktiv_terminierung:
            grund_aus = "Terminierung nicht aktiv"
        elif profil is not None and profil.terminiert_selbst and ad.id != benutzer_id:
            grund_aus = HV_GRUND
            manuell_erlaubt = True
        elif kanal_ids and ad.id not in kanal_ids:
            grund_aus = (f"Kanal {kanal} → nur "
                         + ", ".join(namen.get(i, str(i)) for i in kanal_ids))
        else:
            ok, grund = lead_v2.kompetenz_passt(profil, sparten, objektart or None)
            if not ok:
                grund_aus = grund
            else:
                teile = "+".join(sparten) if sparten else "keine Sparte"
                if objektart.upper() == "MFH":
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
        ergebnis.append({"ad": ad, "profil": kern.ad_profil(session, ad.id),
                         "gruende": gruende, "gebiet": gebiet_ok,
                         "abwertung": 0 if gebiet_ok else 20,
                         "handelsvertreter": bool(profil and profil.terminiert_selbst)})
    return {"kandidaten": ergebnis, "ausgeschlossen": ausgeschlossen,
            "sparten": sparten, "kanal": kanal, "nur_ad_id": nur_ad_id,
            "objektart": objektart,
            "hv_lead": hv_lead,
            "hv_hinweis": HV_HINWEIS.format(name=hv_lead.name) if hv_lead else "",
            # HV, die der Innendienst manuell (nicht über Vorschläge) buchen darf
            "hv_manuell": [a["ad"] for a in ausgeschlossen if a["manuell_erlaubt"]]}


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


def vorschlaege(session: Session, vorgang: Vorgang, nur_ad_id: int | None = None,
                anzahl: int = 5, benutzer=None) -> dict:
    """Top-N-Slots (Dauer aus Profil/90, Raster 30, Horizont 14 Werktage).
    Kapazität zählt nur Vor-Ort-Termine, Kollision alle Terminarten; Puffer
    = max(puffer_min, Fahrzeit); Begründung je Vorschlag in Klartext."""
    from app import kalender as kalender_modul
    from app import routing
    jetzt = datetime.now()
    horizont = _int(parameter(session, "vorschlag_horizont_tage", "14"), 14)
    raster = max(5, _int(parameter(session, "vorschlag_raster_min", "30"), 30))
    lead_ort = (vorgang.lat, vorgang.lon) if vorgang.lat is not None else None
    vorfilter = kandidaten(session, vorgang, nur_ad_id, benutzer=benutzer)
    hinweise = []
    if lead_ort is None:
        hinweise.append("Lead-Adresse ohne Koordinaten („Adresse prüfen“) – "
                        "Umwege und Fahrzeit-Puffer werden ohne Fahrzeit bewertet.")
    tage = []
    tag = jetzt.replace(hour=0, minute=0, second=0, microsecond=0)
    while len(tage) < horizont:
        tag += timedelta(days=1)
        if tag.weekday() < 6:
            tage.append(tag)
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
        routing.matrix_fuellen(session, [lead_ort], list(punkte))
        routing.matrix_fuellen(session, list(punkte), [lead_ort])
    fenster = kern._wunschzeit_fenster(session, vorgang)
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
        belegt_extern = kalender_modul.frei_belegt(
            session, ad, jetzt, tage[-1] + timedelta(days=1)) if tage else None
        for tag in tage:
            zeiten = kern._arbeitszeiten_von_bis(profil, tag)
            if zeiten is None:
                continue
            tages_termine = [t for t in termine if t.beginn.date() == tag.date()]
            vot_tag = [t for t in tages_termine if (t.typ or "vot") == "vot"]
            if len(vot_tag) >= max_tag:
                continue
            leerer_tag = not tages_termine
            tour_tag = (lead_ort is not None and any(
                t.lat is not None
                and routing.luftlinie_km(lead_ort, (t.lat, t.lon)) <= 10
                for t in tages_termine))
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
                vorher = max((t for t in tages_termine if _ende(t, dauer) <= beginn),
                             key=lambda t: t.beginn, default=None)
                nachher = min((t for t in tages_termine if t.beginn >= ende),
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
    alle.sort(key=lambda v: (v["bewertung"], v["beginn"]))
    gewaehlt, je_tag = [], {}
    for v in alle:
        schluessel = (v["ad"].id, v["beginn"].date())
        if je_tag.get(schluessel, 0) >= 2:
            continue
        je_tag[schluessel] = je_tag.get(schluessel, 0) + 1
        gewaehlt.append(v)
        if len(gewaehlt) >= anzahl:
            break
    return {"vorschlaege": gewaehlt, "hinweise": hinweise,
            "kandidaten": [k["ad"] for k in vorfilter["kandidaten"]],
            "kandidaten_info": vorfilter["kandidaten"],
            "ausgeschlossen": vorfilter["ausgeschlossen"],
            "sparten": vorfilter["sparten"], "kanal": vorfilter["kanal"],
            "nur_ad_id": vorfilter["nur_ad_id"],
            "hv_lead": vorfilter["hv_lead"], "hv_hinweis": vorfilter["hv_hinweis"],
            "hv_manuell": vorfilter["hv_manuell"]}


# --- v25 (Phase 119/120): Terminvorschläge für den Block Termine der Kartei --------

def adresse_fehlt(kunde) -> list[str]:
    """Fehlende Adressteile (Straße, PLZ, Ort) – ohne Adresse keine Vorschläge."""
    if kunde is None:
        return ["Straße", "PLZ", "Ort"]
    fehlt = []
    for feld, name in (("strasse", "Straße"), ("plz", "PLZ"), ("ort", "Ort")):
        if not str(getattr(kunde, feld, "") or "").strip():
            fehlt.append(name)
    return fehlt


def _beginn_text(beginn: datetime) -> str:
    from app.templating import de_datum
    return de_datum(beginn, "%a %d.%m.%Y · %H:%M") + " Uhr"


def vorschlaege_json(session: Session, vorgang: Vorgang, benutzer=None,
                     anzahl: int = 5, jetzt: datetime | None = None) -> dict:
    """Antwort für GET /lead-management/lead/{id}/termin/vorschlaege.json
    (Vertrag Agent C/D): {status: ok|adresse_fehlt|hv_lead|keine, hinweis,
    vorschlaege: [{ad_id, ad_name, beginn (ISO), beginn_text, begruendung,
    umweg_min}]} – Top 5, Cache 10 Minuten je Lead (Sicht Innendienst bzw. je
    Handelsvertreter getrennt), Zusatzfelder aus_cache/berechnet_um/buchbar/
    pflicht_offen. Reihenfolge der Zustände: HV-Lead (Innendienst) → Adresse
    fehlt → Vorschläge (ok) oder keine."""
    jetzt = jetzt or datetime.now()
    kunde = session.get(Kunde, vorgang.kunde_id)
    hv_ich = lead_v2.ist_handelsvertreter(session, benutzer) if benutzer is not None else False
    sicht = f"hv{benutzer.id}" if hv_ich else "id"
    eintrag = vorschlaege_cache.get(vorgang.id, {}).get(sicht)
    if eintrag is not None and (jetzt - eintrag[0]).total_seconds() < VORSCHLAEGE_CACHE_SEKUNDEN:
        antwort = dict(eintrag[1])
        antwort["aus_cache"] = True
        return antwort
    buchbar = not (kern.demo_aktiv(session) and not vorgang.demo)
    pflicht_offen = lead_v2.pflichtfelder_offen(session, kunde, vorgang) if kunde else []
    antwort = {"status": "ok", "hinweis": "", "vorschlaege": [],
               "buchbar": buchbar, "pflicht_offen": pflicht_offen,
               "berechnet_um": jetzt.strftime("%H:%M"), "aus_cache": False}
    hv = hv_des_vorgangs(session, vorgang)
    if hv is not None and getattr(benutzer, "id", None) != hv.id:
        antwort.update(status="hv_lead", hinweis=HV_HINWEIS.format(name=hv.name),
                       hv_id=hv.id, hv_name=hv.name)
    else:
        fehlt = adresse_fehlt(kunde)
        if fehlt:
            antwort.update(status="adresse_fehlt",
                           hinweis=ADRESSE_HINWEIS, fehlt=fehlt)
        else:
            ergebnis = vorschlaege(session, vorgang, anzahl=anzahl, benutzer=benutzer)
            liste = [{
                "ad_id": v["ad"].id, "ad_name": v["ad"].name,
                "beginn": v["beginn"].strftime("%Y-%m-%dT%H:%M"),
                "beginn_text": _beginn_text(v["beginn"]),
                "begruendung": v["begruendung"], "umweg_min": int(v["umweg"]),
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
    from app import kalender as kalender_modul
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
    belegt = kalender_modul.frei_belegt(session, ad, tag, tag + timedelta(days=1))
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
                     f"({TERMIN_TYP_NAMEN.get(t.typ or 'vot', t.typ)})")
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

def _vorgemerkte_aufraeumen(session: Session, vorgang_id: int, ausser_id: int) -> None:
    for alt in (session.query(VotTermin)
                .filter(VotTermin.vorgang_id == vorgang_id,
                        VotTermin.status == STATUS_VORGEMERKT,
                        VotTermin.typ == "vot", VotTermin.id != ausser_id)):
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


def termin_anlegen(session: Session, vorgang: Vorgang, ad_id: int, beginn: datetime,
                   benutzer=None, quelle: str = "assistent", umweg: int | None = None,
                   umbuchen_id: int | None = None) -> tuple[VotTermin | None, str, bool]:
    """Vor-Ort-Termin aus Assistent oder manueller Eingabe. Sind Pflicht-
    felder offen (lead_v2.pflichtfelder_offen), entsteht nur ein vorgemerkter
    Termin (ohne Mail, Kalender, Phasenwechsel) – „Terminierung“ in der Kartei
    (Phase 106) schaltet scharf. Sonst kern.termin_buchen. Liefert
    (termin, meldung, vorgemerkt)."""
    from app import geocoding
    ad = session.get(Benutzer, ad_id)
    kunde = session.get(Kunde, vorgang.kunde_id)
    if ad is None or kunde is None:
        return None, "Außendienstler oder Kunde fehlt.", False
    if kern.demo_aktiv(session) and not vorgang.demo:
        return None, ("Terminierung im Demo-Modus nur für Demo-Leads – "
                      "in monday terminieren."), False
    alt = session.get(VotTermin, umbuchen_id) if umbuchen_id else None
    offen = lead_v2.pflichtfelder_offen(session, kunde, vorgang)
    if offen and (alt is None or alt.status == STATUS_VORGEMERKT):
        profil = kern.ad_profil(session, ad_id)
        termin = VotTermin(
            vorgang_id=vorgang.id, ad_id=ad_id, beginn=beginn,
            ende=beginn + timedelta(minutes=profil.termin_dauer_min or 90),
            adresse=geocoding.lead_adresse(session, vorgang),
            lat=vorgang.lat, lon=vorgang.lon, status=STATUS_VORGEMERKT,
            quelle=quelle, umweg_min=umweg, demo=bool(vorgang.demo),
            typ="vot", medium="vor_ort",
            erstellt_von=benutzer.id if benutzer else None)
        session.add(termin)
        session.flush()
        _vorgemerkte_aufraeumen(session, vorgang.id, termin.id)
        kern.aktivitaet(session, vorgang.id, "termin",
                        f"Termin vorgemerkt {beginn:%d.%m.%Y %H:%M} bei {ad.name} – "
                        f"Pflichtfelder offen: {', '.join(offen)}", benutzer=benutzer)
        _ad_am_vorgang(session, vorgang, ad_id, benutzer)
        session.flush()
        vorschlaege_cache_leeren()   # v25: Kalender geändert – Vorschläge neu rechnen
        return termin, ("Termin vorgemerkt – Terminierung in der Kartei abschließen "
                        f"(offen: {', '.join(offen)})."), True
    umbuchen_echt = alt.id if (alt is not None and alt.status != STATUS_VORGEMERKT) else None
    termin, meldung = kern.termin_buchen(session, vorgang, ad_id, beginn,
                                         benutzer=benutzer, quelle=quelle,
                                         umweg=umweg, umbuchen_id=umbuchen_echt)
    if termin is None:
        return None, meldung, False
    if umbuchen_echt:
        umbuchung_nachziehen(session, alt, termin)
    _vorgemerkte_aufraeumen(session, vorgang.id, termin.id)
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
            if b.rolle in ("innendienst", "admin") or b.hat_rolle("leadmanagement")]


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
    person = session.get(Benutzer, person_id) if person_id else None
    kunde = session.get(Kunde, vorgang.kunde_id)
    if person is None or not person.aktiv or kunde is None:
        return None, "Ansprechpartner fehlt."
    if kern.demo_aktiv(session) and not vorgang.demo:
        return None, "Im Demo-Modus nur für Demo-Leads."
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
        kern.benachrichtigen(session, [person.id],
                             f"{name} {beginn:%d.%m. %H:%M}: {kunde.anzeige_name}"
                             f"{', ' + kunde.ort if kunde.ort else ''}",
                             f"/lead-management/lead/{vorgang.id}")
    session.flush()
    vorschlaege_cache_leeren()   # v25: Vorab-Gespräche zählen in der Kollision
    return termin, " ".join(hinweise) or f"{name} eingetragen."


# --- Absage mit Storno-ICS und Ersatzkunde (E3, E4, F8) -----------------------------

def leitung_ids(session: Session) -> list[int]:
    """„Leitung“ für Glocken: Admins + Benutzer mit Rolle Leadmanagement."""
    return [b.id for b in session.query(Benutzer).filter(Benutzer.aktiv.is_(True))
            if b.rolle == "admin" or b.hat_rolle("leadmanagement")]


def absagen(session: Session, termin: VotTermin, grund: str, text: str = "",
            benutzer=None) -> tuple[bool, str]:
    """Termin absagen: VOT über kern.termin_no_show (Lead zurück auf
    Qualifiziert, Kalender gelöscht, Mails storniert, Glocke LM) plus
    Kundenmail terminabsage mit Storno-ICS (METHOD:CANCEL, gleiche UID).
    Vorab-Gespräche/vorgemerkte Termine: nur Status, Kalender, Aktivität."""
    from app import kalender as kalender_modul
    from app import lead_mail
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
            f"/lead-management/termin/{termin.id}/ersatz")
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
                                 f"/lead-management/lead/{vorgang.id}")
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
        f"/lead-management/termin/{termin.id}/ersatz")


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

def bestaetigung_erneut(session: Session, termin: VotTermin, benutzer=None
                        ) -> tuple[bool, str]:
    """Gleiche UID, SEQUENCE + 1, Vorlage terminbestaetigung neu planen."""
    if termin.status not in AKTIVE_STATUS or (termin.typ or "vot") != "vot":
        return False, "Nur für aktive Vor-Ort-Termine möglich."
    vorgang = session.get(Vorgang, termin.vorgang_id)
    kunde = session.get(Kunde, vorgang.kunde_id) if vorgang else None
    if kunde is None or not kunde.email:
        return False, "Kunde ohne E-Mail-Adresse."
    if not termin.ics_uid:
        termin.ics_uid = f"friondo-vot-{termin.id}@friondo.de"
    termin.ics_sequence = (termin.ics_sequence or 0) + 1
    eintrag = kern.mail_planen(session, vorgang, "terminbestaetigung", termin=termin)
    kern.aktivitaet(session, vorgang.id, "termin",
                    f"Terminbestätigung erneut geplant (ICS SEQUENCE {termin.ics_sequence})",
                    benutzer=benutzer)
    session.flush()
    return eintrag is not None, "Terminbestätigung erneut geplant."


# --- Kalender (Woche je AD, alle Terminarten + vorgemerkt) --------------------------

def kalender_woche(session: Session, ad_ids: list[int], start=None) -> dict:
    from app import kalender as kalender_modul
    jetzt = datetime.now()
    start = start or (jetzt - timedelta(days=jetzt.weekday()))
    start = start.replace(hour=0, minute=0, second=0, microsecond=0)
    tage = [start + timedelta(days=i) for i in range(6)]
    raster = {}
    termine_je_ad = _termine_je_ad(session, [a for a in ad_ids if a], tage[0],
                                   tage[-1] + timedelta(days=1))
    for ad_id in ad_ids:
        if not ad_id:
            continue
        ad = session.get(Benutzer, ad_id)
        termine = termine_je_ad.get(ad_id, [])
        belegt = kalender_modul.frei_belegt(session, ad, tage[0],
                                            tage[-1] + timedelta(days=1))
        raster[ad_id] = {
            "termine": {t.date(): [x for x in termine if x.beginn.date() == t.date()]
                        for t in tage},
            "belegt": {t.date(): [b for b in (belegt or []) if b[0].date() == t.date()]
                       for t in tage},
        }
    return {"tage": tage, "je_ad": raster}


def hv_nur_eigene(session: Session, benutzer) -> int | None:
    """Handelsvertreter rechnen/sehen nur den eigenen Kalender (G2)."""
    if benutzer is not None and lead_v2.ist_handelsvertreter(session, benutzer):
        return benutzer.id
    return None
