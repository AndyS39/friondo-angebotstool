# v32 (PLAN_V19 Phase 162): automatische Wiedervorlage nach Angebotsversand, Block
# „Fällig heute“ der Vertriebler-Ansicht „Mein Tag“ (Phase 161) und die Angebotstool-
# Glocke art `nachfassen` (täglicher Lauf in app/benachrichtigungen.py).
#
# Vertrag (Agent M schreibt; N (verfolgung.py), mail_sync, routers/angebote und
# routers/leads nutzen):
#   nach_versand(session, angebot, benutzer=None, versandtag=None) -> bool
#       – Versand-Hook: Versandtag + nachfass_werktage (3) bzw. + nachfass_werktage_mfh (5)
#         bei kunden.objektart = MFH (beide Parameter aus leadmanagement.parameter_holen,
#         fehlende Objektart = nicht MFH); wiedervorlage_benutzer_id = AD des Vorgangs,
#         wiedervorlage_art = angebot_nachfassen; Aktivität im Notizen-Chat (Autor „System“).
#         [ANNAHME] Eine vorhandene Wiedervorlage wird nur überschrieben, wenn sie leer ist
#         oder VOR dem errechneten Datum liegt (gleiches Datum = Kombi-Versand: einmal).
#         Ohne AD am Vorgang bleibt der versendende Benutzer verantwortlich [ANNAHME].
#   wiedervorlage_setzen(session, vorgang, datum, benutzer_id, art) -> None
#       – Vertrag für N („Nochmal anrufen“, „Bestellung“): setzt die bestehenden Spalten
#         wiedervorlage_am (ohne Uhrzeit), wiedervorlage_benutzer_id, wiedervorlage_art;
#         datum None = Wiedervorlage leeren.
#   faellig_heute(session, benutzer_id, heute=None) -> list[dict]
#       – Anruf-Karten: Vorgänge mit wiedervorlage_benutzer_id = Benutzer und
#         wiedervorlage_am ≤ heute, überfällige zuerst („seit TT.MM.“), Angebots-Kurzinfo
#         (Kundenpreis, nie EK/DB), Hot-Ampel, Letzte Aktivitäten (drei Einträge);
#         v33 (Phase 173) zusätzlich prioritaet (hoch|mittel|niedrig aus der Hot-Ampel),
#         letzter_kontakt (Datum des letzten Notizen-Chat-Eintrags, alle Herkünfte inkl.
#         System [ANNAHME]), tage_seit/tage_text („heute“, „seit gestern“, „seit 14 Tagen“),
#         warn (ab 14 Tagen), sparten/sparten_text, initialen.
#   wiedervorlage_liste(session, benutzer_id, heute=None) -> list[dict]
#       – v33 (PLAN_V20 Phase 173, Agent M): Datenbasis des Abschnitts „Wiedervorlage“
#         (Mein Tag mobil + Seite /leads/wiedervorlagen): fällige + überfällige Angebots-
#         Wiedervorlagen des AD (wie faellig_heute) ∪ eigene Vorgänge mit Hot-Ampel heiß
#         oder Verfolgungsstatus bestellung_angekuendigt (die früheren „Heißen Kunden“);
#         gleiche Felder wie faellig_heute + grund (faellig|heiss|bestellung), nachfass_versuche,
#         inaktiv (Agent N hängt `inaktiv_kennzeichen(session, vorgaenge, heute)` unten an –
#         wird über globals() gelesen, solange es fehlt bleibt inaktiv None). Sortierung:
#         Priorität hoch → mittel → niedrig, dann ältester Kontakt zuerst.
#   glocke_faellig_heute(session, heute=None) -> int
#       – täglicher Lauf: je Außendienstler EINE Glocke „Fällig heute: n Anrufe“
#         (art nachfassen, kein Mailversand – MAIL_FREIE_ARTEN in benachrichtigungen).
#   angebots_kurzinfo(session, vorgang) -> dict | None, letzte_aktivitaeten(session, vorgang)
# Reine Datenbankarbeit – kein Netzaufruf (v27-Regel).
from datetime import date, datetime, timedelta

from sqlalchemy.orm import Session

from app import werktage
from app.models import (Angebot, AngebotsMail, Benachrichtigung, Benutzer, Erfassung, Kunde,
                        Lead, Vorgang, VorgangsNotiz)

ART_ANGEBOT = "angebot_nachfassen"
PARAM_WERKTAGE = "nachfass_werktage"
PARAM_WERKTAGE_MFH = "nachfass_werktage_mfh"
STANDARD_WERKTAGE = 3
STANDARD_WERKTAGE_MFH = 5
WERKTAGE_MAX = 60
GLOCKE_ART = "nachfassen"
GLOCKE_LINK = "/leads#wiedervorlage"   # v33 (Phase 173): Abschnitt „Wiedervorlage“ statt „Fällig heute“
VERSAND_STATUS = ("Versendet", "Versendet (extern)")
AKTIVITAET_TEXT = "Wiedervorlage automatisch gesetzt: Angebot nachfassen am {datum}"
HERKUNFT = "Verfolgung (automatisch)"
AKTIVITAETEN_ANZAHL = 3
AMPEL_NAMEN = {"heiss": "heiß", "warm": "warm", "kalt": "kalt"}


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


def _ganzzahl(wert, standard: int) -> int:
    try:
        zahl = int(str(wert or "").strip())
    except (TypeError, ValueError):
        return standard
    return max(0, min(WERKTAGE_MAX, zahl))


def euro(cent) -> str:
    """Kundenpreis in deutscher Schreibweise (wie templating.euro, ohne Template-Import)."""
    if cent is None:
        return ""
    vorzeichen = "-" if cent < 0 else ""
    cent = abs(int(cent))
    euro_teil, cent_teil = divmod(cent, 100)
    return f"{vorzeichen}{euro_teil:,.0f}".replace(",", ".") + f",{cent_teil:02d} €"


def tel_href(nummer: str) -> str:
    """Click-to-Call wie im Lead-Modul (lead_anrufliste.tel_href, E.164)."""
    if not (nummer or "").strip():
        return ""
    try:
        from app import lead_anrufliste
        return lead_anrufliste.tel_href(nummer)
    except Exception:   # noqa: BLE001 – die Karte darf daran nie scheitern
        return "tel:" + (nummer or "").strip().replace(" ", "")


def kundenname(kunde) -> str:
    """„Anrede Vorname Nachname“ (Firma vorangestellt), wie die Termin-Karte."""
    if kunde is None:
        return "?"
    person = " ".join(t for t in (kunde.anrede, kunde.vorname, kunde.nachname) if t)
    if getattr(kunde, "firma", ""):
        return f"{kunde.firma} ({person})" if person else kunde.firma
    return person or kunde.anzeige_name or "?"


def ist_mfh(kunde) -> bool:
    """kunden.objektart = MFH (Spalte seit v23); fehlende Objektart zählt als Nicht-MFH."""
    return (getattr(kunde, "objektart", "") or "").strip().upper() == "MFH"


def werktage_parameter(session: Session, mfh: bool = False) -> int:
    """nachfass_werktage (3) bzw. nachfass_werktage_mfh (5) – nur lesend über
    leadmanagement.parameter_holen (Felder in den Angebotstool-Einstellungen: N)."""
    from app import leadmanagement
    if mfh:
        return _ganzzahl(leadmanagement.parameter_holen(session, PARAM_WERKTAGE_MFH,
                                                        str(STANDARD_WERKTAGE_MFH)),
                         STANDARD_WERKTAGE_MFH)
    return _ganzzahl(leadmanagement.parameter_holen(session, PARAM_WERKTAGE,
                                                    str(STANDARD_WERKTAGE)),
                     STANDARD_WERKTAGE)


def nachfass_datum(session: Session, kunde, versandtag) -> date:
    """Versandtag + Werktage (Mo–Fr, NRW-Feiertage ausgenommen; MFH gesondert)."""
    tag = _tag(versandtag) or date.today()
    return werktage.plus_werktage(tag, werktage_parameter(session, ist_mfh(kunde)))


def _archiv_filter(abfrage):
    try:   # v31 (Phase 154): Archiv ist eine Lead-Sicht – Arbeitslisten blenden aus
        from app import lead_archiv
        return lead_archiv.filter_aktiv(abfrage)
    except (ImportError, AttributeError):
        return abfrage


def verantwortlicher_id(session: Session, vorgang: Vorgang, angebot: Angebot | None = None,
                        benutzer=None) -> int | None:
    """Verantwortlicher der automatischen Wiedervorlage: der Außendienstler des Vorgangs
    (vorgaenge.ad_id, v23) – sonst der Außendienstler des Angebots (Erfassung bzw.
    vertriebler_id, nur Rolle Außendienst), sonst der Vertriebler des monday-Leads,
    sonst der versendende Benutzer [ANNAHME]; None = Innendienst (ID-Kachel zählt)."""
    if getattr(vorgang, "ad_id", None):
        return vorgang.ad_id
    if angebot is not None:
        erfassung = (session.query(Erfassung)
                     .filter(Erfassung.angebot_id == angebot.id).first())
        kandidat = (erfassung.benutzer_id if erfassung is not None else None) or angebot.vertriebler_id
        if kandidat:
            b = session.get(Benutzer, kandidat)
            if b is not None and b.basisrolle == "aussendienst":
                return b.id
    if getattr(vorgang, "lead_id", None):
        lead = session.get(Lead, vorgang.lead_id)
        if lead is not None and lead.benutzer_id:
            return lead.benutzer_id
    return getattr(benutzer, "id", None)


# --- Vertrag für N -----------------------------------------------------------------------

def wiedervorlage_setzen(session: Session, vorgang: Vorgang, datum, benutzer_id, art: str) -> None:
    """Wiedervorlage am Vorgang (bestehende Spalten v10 + wiedervorlage_art v32): Datum
    ohne Uhrzeit (00:00), Verantwortlicher, Art (angebot_nachfassen | nochmal_anrufen |
    bestellung_angekuendigt | …). datum None = Wiedervorlage leeren."""
    tag = _tag(datum)
    if tag is None:
        vorgang.wiedervorlage_am = None
        vorgang.wiedervorlage_benutzer_id = None
        vorgang.wiedervorlage_art = ""
    else:
        vorgang.wiedervorlage_am = datetime(tag.year, tag.month, tag.day)
        vorgang.wiedervorlage_benutzer_id = benutzer_id
        vorgang.wiedervorlage_art = (art or "")[:30]
    session.flush()


# --- Versand-Hook ------------------------------------------------------------------------

def _verfolgung_nachziehen(session: Session, vorgang: Vorgang, angebot: Angebot, benutzer) -> None:
    """Verfolgungsstufe „versendet“ nach dem Versand (Vertrag N: verfolgung.
    nach_angebotsstatus); Rückfall ohne Modul: Spalte direkt, nur wenn leer/abgelehnt."""
    try:
        from app import verfolgung
        verfolgung.nach_angebotsstatus(session, angebot, benutzer)
        return
    except (ImportError, AttributeError):
        pass
    if (vorgang.verfolgung_status or "") in ("", "abgelehnt"):
        vorgang.verfolgung_status = "versendet"


def nach_versand(session: Session, angebot: Angebot, benutzer=None, versandtag=None) -> bool:
    """Versand-Hook (Einzel-/Kombi-Versand, Versand-Erkennung, „Als versendet markieren“,
    externer TAIFUN-Eintrag): Wiedervorlage = Versandtag + Werktage am Vorgang setzen und
    die Aktivität in den Notizen-Chat schreiben. True = Wiedervorlage gesetzt/geändert.
    Kombi-Versand: der zweite Aufruf trifft dasselbe Datum und ändert nichts (einmal je
    Mail). Eine spätere Wiedervorlage bleibt stehen [ANNAHME]."""
    if angebot is None:
        return False
    vorgang = session.get(Vorgang, angebot.vorgang_id) if angebot.vorgang_id else None
    if vorgang is None:
        from app import vorgaenge as vorgaenge_modul
        vorgang = vorgaenge_modul.vorgang_fuer_angebot(session, angebot)
    if vorgang is None:
        return False
    kunde = session.get(Kunde, vorgang.kunde_id) if vorgang.kunde_id else None
    _verfolgung_nachziehen(session, vorgang, angebot, benutzer)
    tag = _tag(versandtag) or _tag(angebot.versendet_am) or date.today()
    datum = nachfass_datum(session, kunde, tag)
    alt = vorgang.wiedervorlage_am
    if alt is not None and alt.date() >= datum:
        session.flush()
        return False   # gleiches Datum (Kombi: zweites Angebot) oder spätere manuelle Wiedervorlage
    wiedervorlage_setzen(session, vorgang, datum,
                         verantwortlicher_id(session, vorgang, angebot, benutzer), ART_ANGEBOT)
    from app import notizen
    notizen.notiz_anlegen(session, vorgang.id, None,
                          AKTIVITAET_TEXT.format(datum=datum.strftime("%d.%m.%Y")),
                          herkunft=HERKUNFT)
    return True


# --- Block „Fällig heute“ -----------------------------------------------------------------

def angebots_kurzinfo(session: Session, vorgang: Vorgang) -> dict | None:
    """Jüngstes versendetes Angebot des Vorgangs als Kurzinfo „WP-Angebot vom 10.10.2026,
    Endbetrag 32.450,00 €“ – Kundenpreis (Endbetrag), nie EK/DB."""
    angebote = [a for a in session.query(Angebot)
                .filter(Angebot.vorgang_id == vorgang.id, Angebot.archiviert.is_(False),
                        Angebot.status.in_(VERSAND_STATUS + ("Angenommen",)))]
    if not angebote:
        return None
    angebote.sort(key=lambda a: (a.versendet_am or a.datum or datetime.min, a.id), reverse=True)
    a = angebote[0]
    datum = a.versendet_am or a.datum
    sparte = (a.konfigurator_typ or "WP").upper()
    endbetrag = a.summen()["endbetrag"]
    text = f"{sparte}-Angebot vom {datum.strftime('%d.%m.%Y') if datum else '–'}, Endbetrag {euro(endbetrag)}"
    weitere = len(angebote) - 1
    if weitere:
        text += f" (+{weitere} weitere{'s' if weitere == 1 else ''})"
    return {"angebot": a, "nummer": a.nummer, "sparte": sparte, "datum": datum,
            "endbetrag_cent": endbetrag, "text": text, "status": a.status,
            "weitere": weitere, "extern": bool(a.extern),
            "url_ad": f"/meine-angebote/{a.id}", "url_id": f"/angebote/{a.id}"}


def letzte_aktivitaeten(session: Session, vorgang: Vorgang,
                        anzahl: int = AKTIVITAETEN_ANZAHL) -> list[dict]:
    """Die letzten Einträge aus Mail-Verlauf (angebots_mails; der Versand selbst zählt
    als gesendete Mail [ANNAHME]), Notizen-Chat und Signaturprotokoll – jüngste zuerst,
    je Eintrag zeit, art, text, zeit_text."""
    eintraege: list[dict] = []
    angebote = (session.query(Angebot).filter(Angebot.vorgang_id == vorgang.id).all())
    ids = [a.id for a in angebote]
    for m in (session.query(AngebotsMail).filter(AngebotsMail.angebot_id.in_(ids or [0]))
              .order_by(AngebotsMail.empfangen_am.desc().nullslast()).limit(10)):
        zeit = m.empfangen_am or m.angelegt_am
        kurz = (m.betreff or m.vorschau or "").strip()[:120]
        eintraege.append({"zeit": zeit, "art": "E-Mail",
                          "text": ("Antwort des Kunden: " if m.eingehend else "Gesendet: ") + kurz})
    for a in angebote:
        if a.versendet_am:
            eintraege.append({"zeit": a.versendet_am, "art": "E-Mail",
                              "text": f"{(a.konfigurator_typ or 'WP').upper()}-Angebot {a.nummer} versendet"
                                      + (" (TAIFUN-Eintrag)" if a.extern else "")})
        if a.signiert_am:
            eintraege.append({"zeit": a.signiert_am, "art": "Signatur",
                              "text": f"{a.nummer} signiert"
                                      + (f" von {a.signatur_name}" if a.signatur_name else "")})
    for n in (session.query(VorgangsNotiz).filter(VorgangsNotiz.vorgang_id == vorgang.id)
              .order_by(VorgangsNotiz.zeit.desc(), VorgangsNotiz.id.desc()).limit(10)):
        eintraege.append({"zeit": n.zeit, "art": "Notiz",
                          "text": f"{n.benutzer_name or 'System'}: {(n.text or '').strip()[:120]}"})
    eintraege.sort(key=lambda e: e["zeit"] or datetime.min, reverse=True)
    for e in eintraege:
        e["zeit_text"] = e["zeit"].strftime("%d.%m.%Y %H:%M") if e["zeit"] else ""
    return eintraege[:anzahl]


# v33 (PLAN_V20 Phase 173): Priorität = Hot-Ampel (heiß → hoch, warm → mittel, kalt → niedrig;
# ohne Einstufung → niedrig [ANNAHME]), Warnschwelle „seit X Tagen“ ab 14 Tagen
PRIORITAET = {"heiss": "hoch", "warm": "mittel", "kalt": "niedrig"}
PRIORITAET_TEXTE = {"hoch": "Hoch", "mittel": "Mittel", "niedrig": "Niedrig"}
PRIORITAET_RANG = {"hoch": 0, "mittel": 1, "niedrig": 2}
KONTAKT_WARN_TAGE = 14


def prioritaet_von(ampel: str) -> str:
    return PRIORITAET.get((ampel or "").strip(), "niedrig")


def tage_text(tage: int | None) -> str:
    """„heute“, „seit gestern“, „seit 14 Tagen“; ohne Kontakt „noch kein Kontakt“."""
    if tage is None:
        return "noch kein Kontakt"
    if tage <= 0:
        return "heute"
    if tage == 1:
        return "seit gestern"
    return f"seit {tage} Tagen"


def letzte_kontakte(session: Session, vorgang_ids) -> dict[int, datetime]:
    """Letzter Eintrag im Notizen-Chat je Vorgang (alle Herkünfte, auch System [ANNAHME]) –
    eine Mengenabfrage für Listen."""
    ids = [int(i) for i in (vorgang_ids or []) if i]
    if not ids:
        return {}
    from sqlalchemy import func
    zeilen = (session.query(VorgangsNotiz.vorgang_id, func.max(VorgangsNotiz.zeit))
              .filter(VorgangsNotiz.vorgang_id.in_(ids))
              .group_by(VorgangsNotiz.vorgang_id).all())
    ergebnis = {}
    for vid, zeit in zeilen:
        if isinstance(zeit, str):   # SQLite liefert max() als Text
            try:
                zeit = datetime.fromisoformat(zeit)
            except ValueError:
                zeit = None
        if zeit is not None:
            ergebnis[vid] = zeit
    return ergebnis


def initialen(name: str) -> str:
    """Zwei Buchstaben des Kundennamens (erster + letzter Namensteil ohne Anrede)."""
    teile = [t for t in (name or "").replace("(", " ").replace(")", " ").split()
             if t and t not in ("Herr", "Frau", "Familie", "Firma", "Dr.", "Prof.")]
    if not teile:
        return "?"
    if len(teile) == 1:
        return teile[0][:2].upper()
    return (teile[0][:1] + teile[-1][:1]).upper()


def _karte_ergaenzen(session: Session, karte: dict, vorgang: Vorgang, kunde, heute_tag: date,
                     kontakte: dict[int, datetime]) -> dict:
    """Phase-173-Felder einer Wiedervorlage-Karte (Priorität, letzter Kontakt, Sparten)."""
    from app import sparten as sparten_modul
    kontakt = kontakte.get(vorgang.id)
    kontakt_tag = kontakt.date() if isinstance(kontakt, datetime) else None
    tage = (heute_tag - kontakt_tag).days if kontakt_tag is not None else None
    sparten = []
    try:
        from app import objekte as objekte_modul
        sparten = objekte_modul.vorgang_interessen(session, vorgang.id) or []
    except Exception:   # noqa: BLE001
        sparten = []
    if not sparten:
        sparten = list(getattr(kunde, "interessen", None) or [])
    prio = prioritaet_von(vorgang.verfolgung_ampel or "")
    try:
        sparten_lang = sparten_modul.sparten_text(sparten) or ", ".join(sparten)
    except Exception:   # noqa: BLE001
        sparten_lang = ", ".join(sparten)
    karte.update({
        "prioritaet": prio, "prioritaet_text": PRIORITAET_TEXTE[prio],
        "prioritaet_rang": PRIORITAET_RANG[prio],
        "letzter_kontakt": kontakt_tag,
        "letzter_kontakt_text": kontakt_tag.strftime("%d.%m.") if kontakt_tag else "",
        "letzter_kontakt_iso": kontakt_tag.isoformat() if kontakt_tag else "",
        "tage_seit": tage, "tage_text": tage_text(tage),
        "warn": tage is not None and tage >= KONTAKT_WARN_TAGE,
        "sparten": sparten, "sparten_text": sparten_lang,
        "initialen": initialen(karte.get("name") or ""),
        "nachfass_versuche": int(getattr(vorgang, "nachfass_versuche", 0) or 0),
        "inaktiv": None,
    })
    return karte


def _karte_basis(session: Session, v: Vorgang, kunde, heute_tag: date) -> dict:
    """Gemeinsame Felder der Anruf-Karte (v32) für Wiedervorlage-fällige und heiße Vorgänge."""
    faellig_tag = v.wiedervorlage_am.date() if v.wiedervorlage_am else None
    ueberfaellig = faellig_tag is not None and faellig_tag < heute_tag
    return {
        "vorgang": v, "kunde": kunde, "name": kundenname(kunde),
        "telefon": (kunde.telefon or "").strip(), "tel_href": tel_href(kunde.telefon),
        "ueberfaellig": ueberfaellig, "seit": faellig_tag,
        "seit_text": faellig_tag.strftime("%d.%m.") if faellig_tag else "",
        "faellig": faellig_tag is not None and faellig_tag <= heute_tag,
        "datum": v.wiedervorlage_am, "art": v.wiedervorlage_art or "",
        "angebot": angebots_kurzinfo(session, v),
        "ampel": v.verfolgung_ampel or "", "ampel_text": AMPEL_NAMEN.get(v.verfolgung_ampel or "", ""),
        "verfolgung_status": v.verfolgung_status or "",
        "aktivitaeten": letzte_aktivitaeten(session, v),
        "akte_url": f"/vorgaenge/{v.id}",
        "grosskunde": bool(getattr(kunde, "grosskunde", False)),
    }


def _inaktiv_nachziehen(session: Session, karten: list[dict], heute_tag: date) -> None:
    """Vertrag N (Phase 176): `inaktiv_kennzeichen(session, vorgaenge, heute)` liefert je
    Vorgang die Tage ohne Kontakt ab Schwelle – erst nach N's Anbau vorhanden."""
    fn = globals().get("inaktiv_kennzeichen")
    if not callable(fn) or not karten:
        return
    try:
        werte = fn(session, [k["vorgang"] for k in karten], heute_tag) or {}
    except Exception:   # noqa: BLE001 – die Liste darf daran nie scheitern
        return
    for k in karten:
        k["inaktiv"] = werte.get(k["vorgang"].id)


def _faellige_vorgaenge(session: Session, benutzer_id: int, heute_tag: date) -> list[Vorgang]:
    grenze = datetime(heute_tag.year, heute_tag.month, heute_tag.day) + timedelta(days=1)
    abfrage = (session.query(Vorgang)
               .filter(Vorgang.wiedervorlage_benutzer_id == benutzer_id,
                       Vorgang.wiedervorlage_am.isnot(None),
                       Vorgang.wiedervorlage_am < grenze))
    return _archiv_filter(abfrage).order_by(Vorgang.wiedervorlage_am, Vorgang.id).all()


def faellig_heute(session: Session, benutzer_id: int, heute=None) -> list[dict]:
    """Anruf-Karten „Fällig heute“: Vorgänge mit wiedervorlage_benutzer_id = Benutzer und
    wiedervorlage_am ≤ heute (Tagesgenau), überfällige zuerst (älteste oben), dann die
    heutigen; je Karte Vorgang, Kunde, Telefon-Link, Angebots-Kurzinfo, Hot-Ampel,
    Verfolgungsstatus, Letzte Aktivitäten (drei Einträge); v33: Priorität, letzter Kontakt."""
    if not benutzer_id:
        return []
    heute_tag = _tag(heute) or date.today()
    vorgaenge = _faellige_vorgaenge(session, benutzer_id, heute_tag)
    kunden = {k.id: k for k in session.query(Kunde)
              .filter(Kunde.id.in_({v.kunde_id for v in vorgaenge} or {0}))}
    kontakte = letzte_kontakte(session, [v.id for v in vorgaenge])
    karten = []
    for v in vorgaenge:
        kunde = kunden.get(v.kunde_id)
        if kunde is None:
            continue
        karte = _karte_basis(session, v, kunde, heute_tag)
        karte["grund"] = "faellig"
        karten.append(_karte_ergaenzen(session, karte, v, kunde, heute_tag, kontakte))
    karten.sort(key=lambda k: (0 if k["ueberfaellig"] else 1, k["datum"], k["vorgang"].id))
    _inaktiv_nachziehen(session, karten, heute_tag)
    return karten


def _heisse_vorgaenge(session: Session, benutzer_id: int) -> list[Vorgang]:
    """Eigene Vorgänge mit Hot-Ampel heiß oder Verfolgungsstatus bestellung_angekuendigt
    (verfolgung.heisse_vorgaenge, Rückfall eigene Abfrage): ad_id, Wiedervorlage-
    Verantwortlicher oder vorgaenge.gehoert_benutzer."""
    try:
        from app import verfolgung
        return verfolgung.heisse_vorgaenge(session, benutzer_id=benutzer_id)
    except (ImportError, AttributeError):
        pass
    from app import vorgaenge as vorgaenge_modul
    abfrage = _archiv_filter(session.query(Vorgang).filter(
        (Vorgang.verfolgung_ampel == "heiss")
        | (Vorgang.verfolgung_status == "bestellung_angekuendigt")))
    return [v for v in abfrage.all()
            if v.ad_id == benutzer_id or v.wiedervorlage_benutzer_id == benutzer_id
            or vorgaenge_modul.gehoert_benutzer(session, v, benutzer_id)]


def wiedervorlage_liste(session: Session, benutzer_id: int, heute=None) -> list[dict]:
    """Abschnitt „Wiedervorlage“ (Phase 173): fällige + überfällige Wiedervorlagen des AD
    (wiedervorlage_am ≤ heute, Verantwortlicher = AD) ∪ eigene Vorgänge mit Hot-Ampel heiß
    oder Verfolgungsstatus bestellung_angekuendigt; je Karte die Felder der Anruf-Karte plus
    prioritaet, letzter_kontakt, tage_seit, grund (faellig | heiss | bestellung), inaktiv (N).
    Sortierung: Priorität (hoch zuerst), dann ältester Kontakt zuerst (ohne Kontakt zuletzt)."""
    if not benutzer_id:
        return []
    heute_tag = _tag(heute) or date.today()
    vorgaenge: dict[int, Vorgang] = {}
    gruende: dict[int, str] = {}
    for v in _faellige_vorgaenge(session, benutzer_id, heute_tag):
        vorgaenge[v.id] = v
        gruende[v.id] = "faellig"
    for v in _heisse_vorgaenge(session, benutzer_id):
        if v.id in vorgaenge:
            continue
        if getattr(v, "archiviert_am", None):
            continue
        vorgaenge[v.id] = v
        gruende[v.id] = ("bestellung" if (v.verfolgung_status or "") == "bestellung_angekuendigt"
                         else "heiss")
    if not vorgaenge:
        return []
    kunden = {k.id: k for k in session.query(Kunde)
              .filter(Kunde.id.in_({v.kunde_id for v in vorgaenge.values()} or {0}))}
    kontakte = letzte_kontakte(session, list(vorgaenge))
    karten = []
    for v in vorgaenge.values():
        kunde = kunden.get(v.kunde_id)
        if kunde is None:
            continue
        karte = _karte_basis(session, v, kunde, heute_tag)
        karte["grund"] = gruende[v.id]
        karten.append(_karte_ergaenzen(session, karte, v, kunde, heute_tag, kontakte))
    karten.sort(key=lambda k: (k["prioritaet_rang"], k["letzter_kontakt"] is None,
                               k["letzter_kontakt"] or heute_tag, k["vorgang"].id))
    _inaktiv_nachziehen(session, karten, heute_tag)
    return karten


def wiedervorlage_zaehler(karten: list[dict]) -> dict[str, int]:
    """Chip-Zähler Alle · Hoch · Mittel · Niedrig."""
    zaehler = {"alle": len(karten), "hoch": 0, "mittel": 0, "niedrig": 0}
    for k in karten:
        zaehler[k["prioritaet"]] = zaehler.get(k["prioritaet"], 0) + 1
    return zaehler


def faellig_anzahl_je_benutzer(session: Session, heute=None) -> dict[int, int]:
    """Anzahl „Fällig heute“ je Verantwortlichem (für die Glocke)."""
    heute_tag = _tag(heute) or date.today()
    grenze = datetime(heute_tag.year, heute_tag.month, heute_tag.day) + timedelta(days=1)
    abfrage = (session.query(Vorgang.wiedervorlage_benutzer_id)
               .filter(Vorgang.wiedervorlage_benutzer_id.isnot(None),
                       Vorgang.wiedervorlage_am.isnot(None),
                       Vorgang.wiedervorlage_am < grenze))
    abfrage = _archiv_filter(abfrage)
    zaehler: dict[int, int] = {}
    for (bid,) in abfrage:
        zaehler[bid] = zaehler.get(bid, 0) + 1
    return zaehler


def glocke_faellig_heute(session: Session, heute=None) -> int:
    """Täglicher Lauf (benachrichtigungen.taeglicher_lauf): je Außendienstler mit fälligen
    Wiedervorlagen EINE Glocke „Fällig heute: n Anrufe“ (art nachfassen, Link Mein Tag) –
    höchstens eine je Tag, keine Mail [ANNAHME]. Liefert die Anzahl angelegter Glocken."""
    from app import projektierung as kern
    heute_tag = _tag(heute) or date.today()
    tagesanfang = datetime(heute_tag.year, heute_tag.month, heute_tag.day)
    glocken = 0
    for bid, n in sorted(faellig_anzahl_je_benutzer(session, heute_tag).items()):
        benutzer = session.get(Benutzer, bid)
        if benutzer is None or not benutzer.aktiv or not benutzer.hat_rolle("aussendienst"):
            continue
        schon = (session.query(Benachrichtigung.id)
                 .filter(Benachrichtigung.benutzer_id == bid,
                         Benachrichtigung.art == GLOCKE_ART,
                         Benachrichtigung.erstellt_am >= tagesanfang).first())
        if schon is not None:
            continue
        kern.benachrichtigen(session, [bid],
                             f"Fällig heute: {n} Anruf{'e' if n != 1 else ''} zum Nachfassen – Mein Tag",
                             GLOCKE_LINK, art=GLOCKE_ART)
        glocken += 1
    return glocken


# ======================================================================================
# v33 (PLAN_V20 Phase 176, Agent N): Inaktivitäts-Kennzeichen „ohne Kontakt seit X Tagen“
# und Nachfass-Mail aus dem eigenen Postfach des Außendienstlers.
#
# Vertrag (M liest inaktiv_kennzeichen über globals(), T über getattr(nachfassen, …)):
#   inaktiv_parameter(session, mfh=False) -> int        (inaktiv_tage 14 / inaktiv_tage_mfh 20)
#   letzter_kontakt_map(session, vorgaenge) -> dict[vorgang_id, datetime | None]
#       – „Kontakt“ = jüngster Eintrag aus Notizen-Chat (alle Herkünfte), Anruf-Ergebnis
#         (LeadAktivitaet typ anruf), gesendeter Lead-Mail (KommunikationLog gesendet_am),
#         Mail-Verlauf der Angebote (AngebotsMail, ein- und ausgehend) und Angebotsversand
#         (angebote.versendet_am); ohne alles: angelegt_am des Vorgangs.
#   inaktiv_tage_fuer(session, vorgang, heute=None) -> int | None
#       – Tage seit dem letzten Kontakt, wenn Verfolgungsstatus versendet|nachgefasst UND
#         Schwelle erreicht (14 Tage, 20 bei kunden.objektart = MFH); sonst None. Eine
#         Wiedervorlage in der Zukunft schützt nicht.
#   inaktiv_kennzeichen(session, vorgaenge, heute=None) -> dict[vorgang_id, int]
#       – Mengenabfrage für Listen (nur Vorgänge mit Kennzeichen).
#   inaktiv_text(tage) -> „ohne Kontakt seit 15 Tagen“
#   nachfass_mail_kontext(session, vorgang, benutzer=None) -> dict   (Knopf im Partial)
#   nachfass_mail_rendern(session, vorgang, benutzer, vorlage_nr) -> dict  (Vorschau)
#   nachfass_mail_senden(session, vorgang, benutzer, vorlage_nr, pdf_anhaengen=False)
#       -> (ok, meldung, daten) – Graph nur über graph_versand.mail_senden_als (Modus
#          anwendung), Sitzung vor dem Netzaufruf freigegeben (v27), danach AngebotsMail
#          (Mail-Verlauf, eingehend = False) + System-Notiz im Chat; der Aufrufer committet.
# ======================================================================================

PARAM_INAKTIV = "inaktiv_tage"
PARAM_INAKTIV_MFH = "inaktiv_tage_mfh"
STANDARD_INAKTIV = 14
STANDARD_INAKTIV_MFH = 20
INAKTIV_MAX = 365
INAKTIV_STATUS = ("versendet", "nachgefasst")
NACHFASS_VORLAGEN = (1, 2)
NACHFASS_NAMEN = {1: "Nachfassen 1", 2: "Nachfassen 2"}
NACHFASS_HERKUNFT = "Verfolgung"             # Kennzeichen der System-Notiz (wie verfolgung.py)
MAIL_GESPERRT_HINWEIS = "Versand aus dem eigenen Postfach erst mit Graph als Anwendung"
MAIL_GRAPH_ID_PRAEFIX = "nachfass-mail:"     # angebots_mails.graph_id (eindeutig je Versand)


def _inaktiv_ganzzahl(wert, standard: int) -> int:
    try:
        zahl = int(str(wert or "").strip())
    except (TypeError, ValueError):
        return standard
    return max(0, min(INAKTIV_MAX, zahl))


def inaktiv_parameter(session: Session, mfh: bool = False) -> int:
    """Schwelle in Tagen – inaktiv_tage (14) bzw. inaktiv_tage_mfh (20); Lead-Parameter,
    gepflegt in den Angebotstool-Einstellungen (Abschnitt Nachfassen)."""
    from app import leadmanagement
    if mfh:
        return _inaktiv_ganzzahl(leadmanagement.parameter_holen(
            session, PARAM_INAKTIV_MFH, str(STANDARD_INAKTIV_MFH)), STANDARD_INAKTIV_MFH)
    return _inaktiv_ganzzahl(leadmanagement.parameter_holen(
        session, PARAM_INAKTIV, str(STANDARD_INAKTIV)), STANDARD_INAKTIV)


def inaktiv_text(tage: int | None) -> str:
    """Anzeigetext des Kennzeichens (Plan-Wortlaut); None/0 → leer."""
    if not tage:
        return ""
    return f"ohne Kontakt seit {tage} Tag{'' if tage == 1 else 'en'}"


def _max_zeit(ziel: dict, vid: int, zeit) -> None:
    if isinstance(zeit, str):   # SQLite liefert max() als Text
        try:
            zeit = datetime.fromisoformat(zeit)
        except ValueError:
            zeit = None
    if zeit is None:
        return
    alt = ziel.get(vid)
    if alt is None or zeit > alt:
        ziel[vid] = zeit


def letzter_kontakt_map(session: Session, vorgaenge) -> dict[int, datetime | None]:
    """Jüngster Kontakt je Vorgang (siehe Vertrag oben) – Mengenabfragen für Listen.
    `vorgaenge` = Vorgang-Objekte oder IDs; Vorgänge ohne jeden Eintrag erhalten ihr
    angelegt_am (nur bei Objekten bekannt), sonst None."""
    from sqlalchemy import func
    from app.models import KommunikationLog, LeadAktivitaet
    objekte = {v.id: v for v in vorgaenge if hasattr(v, "id")}
    ids = sorted({int(getattr(v, "id", v)) for v in (vorgaenge or []) if getattr(v, "id", v)})
    ergebnis: dict[int, datetime | None] = {}
    if not ids:
        return ergebnis
    for vid, zeit in (session.query(VorgangsNotiz.vorgang_id, func.max(VorgangsNotiz.zeit))
                      .filter(VorgangsNotiz.vorgang_id.in_(ids))
                      .group_by(VorgangsNotiz.vorgang_id)):
        _max_zeit(ergebnis, vid, zeit)
    for vid, zeit in (session.query(LeadAktivitaet.vorgang_id, func.max(LeadAktivitaet.zeitpunkt))
                      .filter(LeadAktivitaet.vorgang_id.in_(ids), LeadAktivitaet.typ == "anruf")
                      .group_by(LeadAktivitaet.vorgang_id)):
        _max_zeit(ergebnis, vid, zeit)
    for vid, zeit in (session.query(KommunikationLog.vorgang_id, func.max(KommunikationLog.gesendet_am))
                      .filter(KommunikationLog.vorgang_id.in_(ids),
                              KommunikationLog.gesendet_am.isnot(None))
                      .group_by(KommunikationLog.vorgang_id)):
        _max_zeit(ergebnis, vid, zeit)
    for vid, zeit in (session.query(Angebot.vorgang_id, func.max(Angebot.versendet_am))
                      .filter(Angebot.vorgang_id.in_(ids), Angebot.versendet_am.isnot(None))
                      .group_by(Angebot.vorgang_id)):
        _max_zeit(ergebnis, vid, zeit)
    for vid, zeit in (session.query(Angebot.vorgang_id, func.max(AngebotsMail.empfangen_am))
                      .join(AngebotsMail, AngebotsMail.angebot_id == Angebot.id)
                      .filter(Angebot.vorgang_id.in_(ids), AngebotsMail.empfangen_am.isnot(None))
                      .group_by(Angebot.vorgang_id)):
        _max_zeit(ergebnis, vid, zeit)
    for vid in ids:
        if vid not in ergebnis:
            v = objekte.get(vid)
            ergebnis[vid] = getattr(v, "angelegt_am", None) if v is not None else None
    return ergebnis


def letzter_kontakt(session: Session, vorgang: Vorgang) -> datetime | None:
    if vorgang is None:
        return None
    return letzter_kontakt_map(session, [vorgang]).get(vorgang.id)


def inaktiv_kennzeichen(session: Session, vorgaenge, heute=None) -> dict[int, int]:
    """Mengenabfrage: {vorgang_id: Tage ohne Kontakt} für alle Vorgänge der Liste, deren
    Verfolgungsstatus versendet|nachgefasst ist und deren Tage die Schwelle erreichen
    (14 / 20 bei MFH). Wiedervorlagen in der Zukunft spielen keine Rolle."""
    heute_tag = _tag(heute) or date.today()
    kandidaten = [v for v in (vorgaenge or [])
                  if hasattr(v, "id") and (v.verfolgung_status or "") in INAKTIV_STATUS]
    if not kandidaten:
        return {}
    kontakte = letzter_kontakt_map(session, kandidaten)
    kunden = {k.id: k for k in session.query(Kunde)
              .filter(Kunde.id.in_({v.kunde_id for v in kandidaten if v.kunde_id} or {0}))}
    schwelle = inaktiv_parameter(session, False)
    schwelle_mfh = inaktiv_parameter(session, True)
    ergebnis: dict[int, int] = {}
    for v in kandidaten:
        kontakt = kontakte.get(v.id)
        if kontakt is None:
            continue
        tage = (heute_tag - kontakt.date()).days
        grenze = schwelle_mfh if ist_mfh(kunden.get(v.kunde_id)) else schwelle
        if tage >= grenze:
            ergebnis[v.id] = tage
    return ergebnis


def inaktiv_tage_fuer(session: Session, vorgang: Vorgang, heute=None) -> int | None:
    """Einzelwert (Vertrag T/M): Tage ohne Kontakt ab Schwelle, sonst None."""
    if vorgang is None:
        return None
    return inaktiv_kennzeichen(session, [vorgang], heute).get(vorgang.id)


# --- Nachfass-Mail aus dem Postfach des Außendienstlers -----------------------------------

def nachfass_angebot(session: Session, vorgang: Vorgang) -> Angebot | None:
    """Angebot der Nachfass-Mail: das jüngste versendete (bzw. angenommene) Angebot des
    Vorgangs – dieselbe Wahl wie die Angebots-Kurzinfo der Anruf-Karte."""
    info = angebots_kurzinfo(session, vorgang) if vorgang is not None else None
    return info["angebot"] if info else None


def nachfass_absender(session: Session, vorgang: Vorgang, benutzer=None):
    """Absender = der handelnde Benutzer (AD; Innendienst/Admin aus dem eigenen Postfach
    [ANNAHME]); ohne Benutzer (Kontext aus Mein Tag) der AD des Vorgangs."""
    if benutzer is not None:
        return benutzer
    if getattr(vorgang, "ad_id", None):
        return session.get(Benutzer, vorgang.ad_id)
    return None


def nachfass_mail_kontext(session: Session, vorgang: Vorgang, benutzer=None) -> dict:
    """Kontext des Knopfes „Nachfass-Mail“ (Partial _naechster_schritt.html): modus,
    erlaubt (Modus anwendung + Absender mit E-Mail + Kunde mit E-Mail + versendetes
    Angebot), hinweis (erster Grund, warum nicht), vorlagen, empfaenger, absender,
    angebot_nummer, signatur (Upload vorhanden), url/vorschau_url. Kein Netzaufruf."""
    from app import graph_versand, signaturen
    modus = graph_versand.modus(session)
    absender = nachfass_absender(session, vorgang, benutzer)
    kunde = session.get(Kunde, vorgang.kunde_id) if vorgang is not None and vorgang.kunde_id else None
    angebot = nachfass_angebot(session, vorgang)
    absender_mail = (getattr(absender, "email", "") or "").strip()
    empfaenger = (getattr(kunde, "email", "") or "").strip()
    hinweis = ""
    if modus != "anwendung":
        hinweis = MAIL_GESPERRT_HINWEIS
    elif absender is None or not absender_mail:
        hinweis = ("Keine E-Mail-Adresse des Absenders hinterlegt (Benutzerverwaltung) – "
                   "Versand nicht möglich.")
    elif not empfaenger:
        hinweis = "Der Kunde hat keine E-Mail-Adresse – bitte in der Kundenakte ergänzen."
    elif angebot is None:
        hinweis = "Kein versendetes Angebot am Vorgang – nichts nachzufassen."
    return {
        "modus": modus, "erlaubt": not hinweis, "hinweis": hinweis,
        "gesperrt_modus": modus != "anwendung",
        "vorlagen": [(nr, NACHFASS_NAMEN[nr]) for nr in NACHFASS_VORLAGEN],
        "empfaenger": empfaenger, "absender": absender_mail,
        "absender_name": getattr(absender, "name", "") or "",
        "absender_id": getattr(absender, "id", None),
        "angebot_nummer": (angebot.taifun_nummer or angebot.nummer) if angebot is not None and angebot.extern
                          else (angebot.nummer if angebot is not None else ""),
        "angebot_id": angebot.id if angebot is not None else None,
        "pdf_moeglich": angebot is not None and (not angebot.extern or bool(angebot.extern_pdf_pfad)),
        "signatur": bool(absender is not None and signaturen.vorhanden(absender.id)),
        "url": f"/vorgaenge/{vorgang.id}/nachfass-mail" if vorgang is not None else "",
        "vorschau_url": f"/vorgaenge/{vorgang.id}/nachfass-mail/vorschau" if vorgang is not None else "",
    }


def _vorlage_nr(wert) -> int:
    try:
        nr = int(str(wert or "1").strip())
    except ValueError:
        nr = 1
    return nr if nr in NACHFASS_VORLAGEN else 1


STANDARD_SIGNATUR_NACHFASS_HTML = (
    "<p>Friondo GmbH · Arnold-Overbeck-Str. 63-65 · 47139 Duisburg<br>"
    "Telefon: +49 (0) 203 / 396571-0 · "
    "<a href=\"https://www.friondo.de\">www.friondo.de</a><br>"
    "Amtsgericht Duisburg HRB 34795</p>")


def _signatur_bytes(benutzer_id: int) -> tuple[str, list[tuple[str, bytes, str, str]]]:
    """Signatur-HTML (cid:-Verweise) + Inline-Bilder als [(name, bytes, mime, cid)].
    Ohne hochgeladene Signatur nur der Firmenblock (die Nachfass-Vorlagen enden bereits mit
    Grußformel und {absender}; die Firmen-Standardsignatur der Angebots-Mails würde „Mit
    freundlichen Grüßen / Ihr Friondo-Team“ ein zweites Mal bringen)."""
    from pathlib import Path
    from app import signaturen
    if not signaturen.vorhanden(benutzer_id):
        return STANDARD_SIGNATUR_NACHFASS_HTML, []
    html, bilder = signaturen.fuer_versand(benutzer_id)
    daten = []
    for cid, pfad, mime in bilder:
        try:
            daten.append((Path(pfad).name, Path(pfad).read_bytes(), mime, cid))
        except OSError:
            continue
    return html, daten


def _bilder_einbetten(html: str, bilder: list[tuple[str, bytes, str, str]]) -> str:
    """Übergang, solange graph_versand.mail_senden_als keine Inline-Anhänge (contentId)
    kennt: cid:-Verweise der Signatur als data:-URI einbetten (Vorschlag an G im Bericht)."""
    import base64
    for _name, inhalt, mime, cid in bilder:
        html = html.replace(f"cid:{cid}", f"data:{mime};base64,{base64.b64encode(inhalt).decode()}")
    return html


def nachfass_mail_rendern(session: Session, vorgang: Vorgang, benutzer, vorlage_nr) -> dict:
    """Betreff/HTML/Text der Nachfass-Mail (Vorschau und Versand): Vorlage „Nachfassen n“
    mit den Platzhaltern der Angebotsvorlagen ({absender} = Absender, {vertriebler} = AD des
    Vorgangs) plus Signatur des Absenders (Upload, sonst Standard). Liefert dict mit
    betreff, html (cid:-Verweise), html_vorschau (Bilder eingebettet), text, bilder,
    angebot, kunde, absender, vorlage_nr, vorlage_name, fehlende."""
    from app import mail_vorlagen
    nr = _vorlage_nr(vorlage_nr)
    absender = nachfass_absender(session, vorgang, benutzer)
    kunde = session.get(Kunde, vorgang.kunde_id) if vorgang.kunde_id else None
    angebot = nachfass_angebot(session, vorgang)
    fehlende = []
    if kunde is None or not (kunde.email or "").strip():
        fehlende.append("E-Mail-Adresse des Kunden")
    if absender is None or not (absender.email or "").strip():
        fehlende.append("E-Mail-Adresse des Absenders")
    if angebot is None:
        fehlende.append("versendetes Angebot")
    betreff, html, text = "", "", ""
    bilder: list = []
    if angebot is not None:
        betreff, html, text = mail_vorlagen.nachfass_mail_fuer_vorgang(
            session, angebot, kunde, nr, getattr(absender, "name", "") or "")
        if absender is not None:
            signatur_html, bilder = _signatur_bytes(absender.id)
            html += signatur_html
    return {"betreff": betreff, "html": html, "html_vorschau": _bilder_einbetten(html, bilder),
            "text": text, "bilder": bilder, "angebot": angebot, "kunde": kunde,
            "absender": absender, "vorlage_nr": nr, "vorlage_name": NACHFASS_NAMEN[nr],
            "fehlende": fehlende}


def _pdf_anhang(session: Session, angebot: Angebot) -> tuple[str, bytes, str] | None:
    """Angebots-PDF als Anhang (Tool-Angebot neu erzeugt, TAIFUN-Eintrag aus dem Upload)."""
    from pathlib import Path
    if angebot is None:
        return None
    if angebot.extern:
        if not angebot.extern_pdf_pfad or not Path(angebot.extern_pdf_pfad).exists():
            return None
        pfad = Path(angebot.extern_pdf_pfad)
    else:
        from app import pdf_export
        pfad = pdf_export.pdf_fuer_angebot(session, angebot)
    return (pfad.name, pfad.read_bytes(), "application/pdf")


def _mail_senden_als(absender_mail: str, empfaenger: str, betreff: str, html: str,
                     anhaenge: list, bilder: list, text: str):
    """Aufruf des G-Vertrags; Inline-Bilder nur, wenn mail_senden_als sie kennt (Parameter
    inline_bilder – Vorschlag an G), sonst sind sie bereits als data:-URI eingebettet."""
    import inspect
    from app import graph_versand
    try:
        kennt_inline = "inline_bilder" in inspect.signature(graph_versand.mail_senden_als).parameters
    except (TypeError, ValueError):
        kennt_inline = False
    if kennt_inline:
        return graph_versand.mail_senden_als(
            absender_mail, empfaenger, betreff, html, anhaenge=anhaenge,
            text_alternativ=text, inline_bilder=[(n, b, m, c) for n, b, m, c in bilder])
    return graph_versand.mail_senden_als(absender_mail, empfaenger, betreff,
                                         _bilder_einbetten(html, bilder),
                                         anhaenge=anhaenge, text_alternativ=text)


def nachfass_mail_vorbereiten(session: Session, vorgang: Vorgang, benutzer, vorlage_nr,
                              pdf_anhaengen: bool = False) -> tuple[bool, str, dict]:
    """Schritt 1 (Sitzung): Berechtigung/Modus prüfen, Vorlage rendern, Signatur-Bilder und
    PDF lesen – liefert (ok, meldung, paket). paket enthält nur noch Rohdaten (Strings,
    Bytes, IDs), damit Schritt 2 ohne Sitzung läuft. meldung/paket["status_code"]: 409 bei
    Modus delegiert, 400 bei fehlenden Angaben."""
    kontext = nachfass_mail_kontext(session, vorgang, benutzer)
    if not kontext["erlaubt"]:
        return False, kontext["hinweis"], {"status_code": 409 if kontext["gesperrt_modus"] else 400}
    daten = nachfass_mail_rendern(session, vorgang, benutzer, vorlage_nr)
    if daten["fehlende"]:
        return False, "Es fehlt: " + ", ".join(daten["fehlende"]) + ".", {"status_code": 400}
    angebot = daten["angebot"]
    kunde = daten["kunde"]
    absender = daten["absender"]
    anhaenge: list = []
    if pdf_anhaengen:
        anhang = _pdf_anhang(session, angebot)
        if anhang is None:
            return False, "Kein Angebots-PDF vorhanden – bitte ohne Anhang senden.", {"status_code": 400}
        anhaenge.append(anhang)
    paket = {
        "status_code": 200, "vorgang_id": vorgang.id, "angebot_id": angebot.id,
        "angebot_nummer": (angebot.taifun_nummer or angebot.nummer) if angebot.extern else angebot.nummer,
        "lead_vorgang": bool(getattr(vorgang, "lead_phase", None)),
        "absender_id": absender.id, "absender_mail": (absender.email or "").strip(),
        "absender_name": absender.name or "", "empfaenger": (kunde.email or "").strip(),
        "vorlage": daten["vorlage_nr"], "betreff": daten["betreff"], "html": daten["html"],
        "text": daten["text"], "bilder": daten["bilder"], "anhaenge": anhaenge,
    }
    return True, "", paket


def nachfass_mail_absenden(paket: dict) -> tuple[bool, str, str]:
    """Schritt 2 (Netz, OHNE Sitzung – der Aufrufer hat sie vorher freigegeben, v27):
    Graph-Versand aus dem Postfach des Absenders. (ok, fehler, conversation_id)."""
    return _mail_senden_als(paket["absender_mail"], paket["empfaenger"], paket["betreff"],
                            paket["html"], paket["anhaenge"], paket["bilder"], paket["text"])


def nachfass_mail_verbuchen(session: Session, paket: dict, conversation_id: str) -> tuple[str, dict]:
    """Schritt 3 (Sitzung, innerhalb des _speichern-Musters – wiederholbar ohne zweiten
    Versand): Mail-Verlauf des Angebots (AngebotsMail, eingehend = False, eindeutige
    graph_id je Versand) + System-Notiz im Chat (+ Lead-Aktivität bei Lead-Vorgängen).
    Liefert (meldung, daten)."""
    jetzt = datetime.now()
    kennung = conversation_id or jetzt.strftime("%Y%m%d%H%M%S%f")
    nr = paket["vorlage"]
    session.add(AngebotsMail(
        angebot_id=paket["angebot_id"],
        graph_id=f"{MAIL_GRAPH_ID_PRAEFIX}{kennung}:{jetzt.strftime('%H%M%S%f')}"[:300],
        von_name=paket["absender_name"], von_email=paket["absender_mail"], empfangen_am=jetzt,
        betreff=paket["betreff"][:500], vorschau=(paket["text"] or "")[:1000],
        eingehend=False))
    text = (f"Nachfass-Mail {nr} an {paket['empfaenger']} gesendet – „{paket['betreff']}“, "
            f"Absender {paket['absender_mail']}"
            + (" (mit Angebots-PDF)" if paket["anhaenge"] else ""))
    from app import notizen
    notizen.notiz_anlegen(session, paket["vorgang_id"], None,
                          f"{text} ({paket['absender_name']})", herkunft=NACHFASS_HERKUNFT)
    if paket.get("lead_vorgang"):
        try:   # Lead-Timeline (optional, nur bei Lead-Vorgängen)
            from app import leadmanagement
            absender = session.get(Benutzer, paket["absender_id"])
            leadmanagement.aktivitaet(session, paket["vorgang_id"], "mail", text, benutzer=absender)
        except Exception:   # noqa: BLE001 – die Notiz genügt
            pass
    session.flush()
    meldung = (f"Nachfass-Mail {nr} an {paket['empfaenger']} gesendet "
               f"(Absender {paket['absender_mail']}).")
    return meldung, {"status_code": 200, "conversation_id": conversation_id,
                     "empfaenger": paket["empfaenger"], "vorlage": nr,
                     "angebot": paket["angebot_nummer"], "angebot_id": paket["angebot_id"]}


def nachfass_mail_senden(session: Session, vorgang: Vorgang, benutzer, vorlage_nr,
                         pdf_anhaengen: bool = False) -> tuple[bool, str, dict]:
    """Alle drei Schritte in einem Aufruf (Tests, Skripte): vorbereiten → Sitzung freigeben
    (v27) → Graph → verbuchen; der Aufrufer committet. (ok, meldung, daten{status_code,
    conversation_id, …}); 502 bei Graph-Fehler. Die Route nutzt die drei Schritte einzeln,
    damit die Wiederholung des _speichern-Musters nie ein zweites Mal sendet."""
    from app.db import verbindung_freigeben
    ok, meldung, paket = nachfass_mail_vorbereiten(session, vorgang, benutzer, vorlage_nr,
                                                   pdf_anhaengen)
    if not ok:
        return False, meldung, paket
    verbindung_freigeben(session)
    gesendet, fehler, conversation_id = nachfass_mail_absenden(paket)
    if not gesendet:
        return False, f"Nachfass-Mail nicht gesendet: {fehler}", {"status_code": 502}
    meldung, daten = nachfass_mail_verbuchen(session, paket, conversation_id)
    return True, meldung, daten
