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
#         (Kundenpreis, nie EK/DB), Hot-Ampel, Letzte Aktivitäten (drei Einträge).
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
GLOCKE_LINK = "/leads#faellig"
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
            if b is not None and b.rolle == "aussendienst":
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


def faellig_heute(session: Session, benutzer_id: int, heute=None) -> list[dict]:
    """Anruf-Karten „Fällig heute“: Vorgänge mit wiedervorlage_benutzer_id = Benutzer und
    wiedervorlage_am ≤ heute (Tagesgenau), überfällige zuerst (älteste oben), dann die
    heutigen; je Karte Vorgang, Kunde, Telefon-Link, Angebots-Kurzinfo, Hot-Ampel,
    Verfolgungsstatus, Letzte Aktivitäten (drei Einträge)."""
    if not benutzer_id:
        return []
    heute_tag = _tag(heute) or date.today()
    grenze = datetime(heute_tag.year, heute_tag.month, heute_tag.day) + timedelta(days=1)
    abfrage = (session.query(Vorgang)
               .filter(Vorgang.wiedervorlage_benutzer_id == benutzer_id,
                       Vorgang.wiedervorlage_am.isnot(None),
                       Vorgang.wiedervorlage_am < grenze))
    abfrage = _archiv_filter(abfrage)
    vorgaenge = abfrage.order_by(Vorgang.wiedervorlage_am, Vorgang.id).all()
    kunden = {k.id: k for k in session.query(Kunde)
              .filter(Kunde.id.in_({v.kunde_id for v in vorgaenge} or {0}))}
    karten = []
    for v in vorgaenge:
        kunde = kunden.get(v.kunde_id)
        if kunde is None:
            continue
        faellig_tag = v.wiedervorlage_am.date()
        ueberfaellig = faellig_tag < heute_tag
        karten.append({
            "vorgang": v, "kunde": kunde, "name": kundenname(kunde),
            "telefon": (kunde.telefon or "").strip(), "tel_href": tel_href(kunde.telefon),
            "ueberfaellig": ueberfaellig, "seit": faellig_tag,
            "seit_text": faellig_tag.strftime("%d.%m."),
            "datum": v.wiedervorlage_am, "art": v.wiedervorlage_art or "",
            "angebot": angebots_kurzinfo(session, v),
            "ampel": v.verfolgung_ampel or "", "ampel_text": AMPEL_NAMEN.get(v.verfolgung_ampel or "", ""),
            "verfolgung_status": v.verfolgung_status or "",
            "aktivitaeten": letzte_aktivitaeten(session, v),
            "akte_url": f"/vorgaenge/{v.id}",
            "grosskunde": bool(getattr(kunde, "grosskunde", False)),
        })
    karten.sort(key=lambda k: (0 if k["ueberfaellig"] else 1, k["datum"], k["vorgang"].id))
    return karten


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
