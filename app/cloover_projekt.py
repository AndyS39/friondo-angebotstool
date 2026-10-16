"""v36 (PLAN_V22 Phase 194, Agent B3): Cloover-Projekt – persönlicher Abschluss-Link je Angebot, Status-Rückmeldung.

Ablauf beim „Versand vorbereiten“ (routers/angebote.email_entwurf) und im Kombi-Versand
(routers/vorgaenge.kombi_versand) – zwei Hooks je Route, Netz-I/O immer außerhalb der Sitzung:

  vor_pdf(session, angebot, benutzer) -> Meldung        VOR dem Druck des Versand-PDFs:
    (1) Voraussetzungen (Modus ≠ aus, Sparte/Profil/ausgeblendet über cloover.relevant, Kunde Privatperson
        [ANNAHME: kunden.firma leer, kein Großkunde], E-Mail + Telefon (E.164), Ausführungsort mit Straße/
        PLZ/Ort, PDF-Ablage eingerichtet) – fehlt etwas: kein Projekt, Rate bleibt, Meldung
        „Cloover-Link nicht möglich: <Grund>“ (rot in der Editor-Karte, cloover_json.projekt_fehler)
    (2) Rate aktualisieren (cloover.rate_aktualisieren, Agent B2 – Fehler blockieren nicht)
    (3) PDF-Fassung A (ohne Link/QR – cloover_json hat noch keinen checkout_link) → PDF-Ablage (ablegen +
        pruefen: HEAD ohne Anmeldung = application/pdf; Prüf-Fehler = kein Projekt)
    (4) cloover_api.projekt_anlegen (financingDuration aus cloover_laufzeit_min/_max, financingOption aus
        cloover_optionen, offerPDF = [URL]) → projekt_id, checkout_link, financial_offer, pdf_url,
        pdf_ablage in cloover_json; AngebotsNotiz + Vorgangs-Chat „Cloover-Projekt <id> angelegt“;
        Fehler → kein Link, Meldung, Fehlerprotokoll (cloover_api), Knopf „Projekt anlegen“ im Editor
  nach_pdf(session, angebot, pdf_pfad) -> Meldung       NACH dem Druck (= Fassung B mit Link + QR aus
    B2s PDF-Kontext): die abgelegte Datei wird durch Fassung B ersetzt (gleiche URL) [ANNAHME].

Nicht idempotent im Sinne des Plans: ein zweites „Versand vorbereiten“ legt KEIN zweites Projekt an
(Projekt-ID vorhanden → nur das PDF wird neu abgelegt); „Überarbeiten“ (neue Version – cloover_json ohne
Projektfelder) legt ein neues Projekt an, das alte bleibt bei Cloover stehen (Verlauf, Rückfrage B5).
Kombi-Versand: EIN Projekt je Kombi-Mail mit allen Angeboten als Assets und allen PDF-URLs, derselbe Link in
allen PDFs; je Angebot die eigene Rate plus „Gesamtrate für alle Angebote dieser Mail“ (Feld
cloover_json.kombi_gesamtrate_cent, Anzeige durch B2s Partial) [ANNAHME, Rückfrage B6].

Status-Lauf `cloover-status` (60 min, Start +400 s, aktiv nur mit Cloover-Key): Angebote mit projekt_id im
Status Versand vorbereitet/Versendet/Angenommen, Projekt jünger als 180 Tage, höchstens 50 je Lauf –
db.kurz(schreibend=False) lesen → Sitzung zu → GET /api/projects/{id} → db.kurz() je Angebot. Änderung von
status/primary_signed_contract/financing_option_chosen → cloover_json + AngebotsNotiz „Cloover: <status>“;
Vertrag unterschrieben → Badge, Vorgangs-Chat-Notiz „… Angebot auf Angenommen setzen?“ (manuell, keine
Automatik), Glocke art `cloover` (ohne Mail) an den vorbereitenden Innendienstler und den AD des Vorgangs;
Barzahlung (financing_option_chosen = Cash) → Badge „Cloover: Barzahlung gewählt“. Unbekannte status-Werte
werden roh angezeigt (Rückfrage B8).

Zusätzliche Felder in cloover_json (additiv, für B2/Partial): projekt_am, projekt_von, projekt_von_name,
pdf_ablage {anbieter, url, download_url, item_id, drive_id, token, ablauf}, projekt_fehler, pdf_ablage_fehler,
status_fehler, kombi_angebote [Nummern], kombi_gesamtrate_cent, kombi_gesamtrate_mit_cent, alt_projekte [ids].
"""
from __future__ import annotations

import logging
import re
from datetime import datetime, timedelta
from pathlib import Path

from app import cloover, cloover_api, cloover_pdf_ablage, config
from app.db import verbindung_freigeben
from app.models import Angebot, AngebotsNotiz, Benachrichtigung, Kunde

log = logging.getLogger("angebotstool.cloover_projekt")

LAUF_NAME = cloover.LAUF_NAME                 # "cloover-status"
LAUF_INTERVALL_S = 3600
LAUF_START_S = 400
LAUF_MAX = 50
PROJEKT_MAX_TAGE = 180
GLOCKE_ART = cloover.GLOCKE_ART               # "cloover" – ohne Mail (benachrichtigungen.MAIL_FREIE_ARTEN)
HERKUNFT = "cloover"
MELDUNG_PREFIX = "Cloover-Link nicht möglich: "
STATUS_PRUEFBAR = ("Versand vorbereitet", "Versendet", "Angenommen")
STATUS_PROJEKT_ERLAUBT = ("Entwurf", "Versand vorbereitet", "Versendet")   # Knopf „Projekt anlegen“
BADGE_VERTRAG = "Cloover: Vertrag unterschrieben ({datum})"
BADGE_BAR = "Cloover: Barzahlung gewählt"
BADGE_LINK = "Cloover-Link"
TEXT_ANGENOMMEN_FRAGE = "Angebot auf Angenommen setzen?"
GRUND_FIRMA = "Firmenkunde – Cloover nur für Privatkunden"
GRUND_GROSSKUNDE = "Großkunde – Cloover nur für Privatkunden"
GRUND_NAME = "Vor- oder Nachname des Kunden fehlt"
GRUND_EMAIL = "E-Mail des Kunden fehlt"
GRUND_TELEFON = "Telefon fehlt"
GRUND_ORT = "Ausführungsort unvollständig (Straße, PLZ, Ort)"
GRUND_ASSET = "keine Cloover-Anlage für diese Sparte"
GRUND_EXTERN = "TAIFUN-Eintrag (kein Tool-Angebot)"
GRUND_MODUS_AUS = "Cloover-Modul aus"
_EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
_MIN_ZIFFERN = 8


# --- Hilfen --------------------------------------------------------------------------------------

def _jetzt_text() -> str:
    return datetime.now().strftime("%d.%m.%Y %H:%M")


def _wahr(wert) -> bool:
    if isinstance(wert, str):
        return wert.strip().lower() in ("true", "1", "ja", "yes", "signed")
    return bool(wert)


def _datum_text(wert) -> str:
    """contract_signed_date (ISO-Datum/-Zeit oder TT.MM.JJJJ) → „TT.MM.JJJJ“; unlesbar/leer → heute."""
    text = str(wert or "").strip()
    m = re.match(r"(\d{4})-(\d{2})-(\d{2})", text)
    if m:
        return f"{m.group(3)}.{m.group(2)}.{m.group(1)}"
    m = re.match(r"(\d{2})\.(\d{2})\.(\d{4})", text)
    if m:
        return m.group(0)
    return datetime.now().strftime("%d.%m.%Y")


def telefon_e164(telefon: str) -> str:
    """E.164 wie das Lead-Modul (leadmanagement.telefon_normalisieren); leer, wenn zu kurz."""
    from app import leadmanagement
    nummer = leadmanagement.telefon_normalisieren(telefon or "")
    return nummer if len(re.sub(r"\D", "", nummer)) >= _MIN_ZIFFERN else ""


def _relevant(session, angebot) -> tuple[bool, str]:
    """cloover.relevant (B2); solange der Stub steht, eigener Rückfall mit denselben Regeln."""
    try:
        ok, grund = cloover.relevant(session, angebot)
        return bool(ok), grund or ""
    except NotImplementedError:
        pass
    if getattr(angebot, "extern", False):
        return False, GRUND_EXTERN
    if cloover_api.modus(session) == "aus":
        return False, GRUND_MODUS_AUS
    sparte = (angebot.konfigurator_typ or "WP").upper()
    if sparte not in cloover_api.sparten(session):
        return False, f"Sparte {sparte} ohne Cloover (Parametrierung → Cloover)"
    from app import angebotsprofile
    kunde = session.get(Kunde, angebot.kunde_id)
    profil = angebotsprofile.profil_fuer_angebot(session, angebot, kunde)
    if profil is not None and (profil.regel_kennung or "standard") != "standard":
        return False, f"Profil {profil.name} ohne Cloover"
    if cloover.ausgeblendet(angebot):
        return False, "Finanzierung im PDF ausgeblendet"
    return True, ""


def kundendaten(kunde) -> dict:
    """Kunde für POST /api/projects (vorname/nachname/email/telefon E.164)."""
    if kunde is None:
        return {}
    return {"vorname": (kunde.vorname or "").strip(), "nachname": (kunde.nachname or "").strip(),
            "email": (kunde.email or "").strip(), "telefon": telefon_e164(kunde.telefon or "")}


def adresse_fuer(session, angebot, kunde=None) -> dict:
    """Ausführungsort (Objekt des Angebots, Hauptobjekt = Kundenadresse) als street/city/postalCode."""
    from app import anschriften
    ort = anschriften.ausfuehrungsort_fuer(session, angebot=angebot, kunde=kunde)
    return {"strasse": (ort.get("strasse") or "").strip(), "plz": (ort.get("plz") or "").strip(),
            "ort": (ort.get("ort") or "").strip()}


def voraussetzungen(session, angebot, kunde=None) -> list[str]:
    """Alle fehlenden Voraussetzungen für ein Cloover-Projekt (leer = alles da). Reihenfolge: Relevanz
    (Modus, Sparte, Profil, ausgeblendet) → Kunde (Privatperson, Name, E-Mail, Telefon) → Ausführungsort →
    Anlage → PDF-Ablage."""
    ok, grund = _relevant(session, angebot)
    if not ok:
        return [grund or "Cloover nicht relevant"]
    if kunde is None:
        kunde = session.get(Kunde, angebot.kunde_id)
    if kunde is None:
        return ["Kunde fehlt"]
    # Kundenteil aus B2s Karte (dieselben Wortlaute: E-Mail/Telefon/Firmenkunde/Großkunde/Ausführungsort),
    # solange der Stub steht mit eigener Prüfung
    try:
        gruende = list(cloover.voraussetzungen(session, angebot, kunde))
    except NotImplementedError:
        gruende = []
        if (kunde.firma or "").strip() or (kunde.anrede or "") == "Firma":
            gruende.append(GRUND_FIRMA)
        elif getattr(kunde, "grosskunde", False):
            gruende.append(GRUND_GROSSKUNDE)
        if not (kunde.email or "").strip():
            gruende.append(GRUND_EMAIL)
        if not (kunde.telefon or "").strip():
            gruende.append(GRUND_TELEFON)
        adresse = adresse_fuer(session, angebot, kunde)
        if not (adresse["strasse"] and adresse["plz"] and adresse["ort"]):
            gruende.append(GRUND_ORT)
    # eigene Ergänzungen: Name, Formate (E.164 / E-Mail), Anlage, PDF-Ablage
    daten = kundendaten(kunde)
    if not (daten["vorname"] and daten["nachname"]):
        gruende.append(GRUND_NAME)
    if daten["email"] and not _EMAIL.match(daten["email"]):
        gruende.append("E-Mail des Kunden ungültig")
    if (kunde.telefon or "").strip() and not daten["telefon"]:
        gruende.append(f"Telefon unvollständig (mindestens {_MIN_ZIFFERN} Ziffern)")
    if not cloover_api.assets_fuer(session, angebot):
        gruende.append(GRUND_ASSET)
    bereit, ablage_grund = cloover_pdf_ablage.eingerichtet(session)
    if not bereit:
        gruende.append(ablage_grund)
    return gruende


def _fehler_merken(session, angebot, text: str) -> None:
    cloover.json_schreiben(angebot, projekt_fehler=text[:400], projekt_fehler_am=_jetzt_text())


def _notiz(session, angebot, benutzer, text: str) -> None:
    session.add(AngebotsNotiz(angebot_id=angebot.id,
                              benutzer_name=getattr(benutzer, "name", "") or "System", text=text[:2000]))


def _chat(session, angebot, benutzer, text: str) -> None:
    """Notiz im Vorgangs-Chat (herkunft cloover) – ohne Vorgang still übersprungen."""
    try:
        from app import notizen
        from app import vorgaenge as vorgaenge_modul
        vorgang = vorgaenge_modul.vorgang_fuer_angebot(session, angebot)
        if vorgang is not None:
            notizen.notiz_anlegen(session, vorgang.id, benutzer, text, herkunft=HERKUNFT)
    except Exception as fehler:   # noqa: BLE001 – der Chat darf das Projekt nie verhindern
        log.warning("Cloover: Vorgangs-Notiz nicht geschrieben (%s)", fehler)


def _rate(angebot_id: int) -> None:
    """Schritt (2): Rate über B2 aktualisieren – Fehler/Stub blockieren das Projekt nicht."""
    try:
        cloover.rate_aktualisieren(angebot_id)
    except NotImplementedError:
        log.info("Cloover: rate_aktualisieren noch nicht verfügbar (Phase 193)")
    except Exception as fehler:   # noqa: BLE001
        log.warning("Cloover: Rate nicht aktualisiert (%s)", fehler)


def _plan(session, angebote: list, benutzer) -> dict:
    """Alles lesen, was das Projekt braucht – BEVOR die Sitzung freigegeben wird (kein Netz)."""
    kunde = session.get(Kunde, angebote[0].kunde_id) if angebote else None
    plan = {"kunde": kundendaten(kunde), "kunde_obj": kunde,
            "adresse": adresse_fuer(session, angebote[0], kunde) if angebote else {},
            "assets": {}, "gruende": {}, "nummern": {}, "endbetrag": {},
            "user_email": cloover_api.user_email_fuer(session, benutzer),
            "laufzeit": cloover_api.laufzeit_von_bis(session), "optionen": cloover_api.optionen(session),
            "laufzeit_jahre": cloover_api.laufzeit_jahre(session),
            "anzahlung_cent": cloover_api.anzahlung_cent(session),
            "ablage": cloover_pdf_ablage.konfig(session)}
    for angebot in angebote:
        plan["gruende"][angebot.id] = voraussetzungen(session, angebot, kunde)
        plan["assets"][angebot.id] = cloover_api.assets_fuer(session, angebot) if not plan["gruende"][angebot.id] else []
        plan["nummern"][angebot.id] = angebot.nummer
        plan["endbetrag"][angebot.id] = angebot.summen()["endbetrag"]
    return plan


def _ablegen_und_pruefen(angebot, pfad: Path, ablage_konfig: dict) -> tuple[dict | None, str]:
    """Schritt (3): Fassung A ablegen und per HEAD prüfen. (Ablage-Dict, Fehlertext)."""
    try:
        ablage = cloover_pdf_ablage.ablegen(pfad, cloover_pdf_ablage.dateiname(angebot.nummer), ablage_konfig,
                                            angebot_id=angebot.id)
    except cloover_pdf_ablage.AblageFehler as fehler:
        return None, "PDF-Ablage: " + fehler.meldung
    ok, meldung = cloover_pdf_ablage.pruefen(ablage["url"])
    if not ok:
        return None, f"PDF-Ablage nicht öffentlich erreichbar ({meldung})"
    return ablage, ""


def _projekt_speichern(session, angebot, ergebnis: dict, ablage: dict, benutzer, *, kombi: dict | None = None,
                       alt_projekt: str = "") -> None:
    """Schritt (4): Ergebnis in cloover_json, AngebotsNotiz, Vorgangs-Chat (Aufrufer committet)."""
    werte = dict(projekt_id=ergebnis["projekt_id"], checkout_link=ergebnis["checkout_link"],
                 financial_offer=ergebnis.get("financial_offer"), pdf_url=ablage.get("url"),
                 pdf_ablage={k: v for k, v in ablage.items() if k != "download_url"},
                 projekt_am=_jetzt_text(), projekt_von=getattr(benutzer, "id", None),
                 projekt_von_name=getattr(benutzer, "name", "") or "", projekt_fehler=None,
                 projekt_fehler_am=None, pdf_ablage_fehler=None, status=None, status_stand=None,
                 primary_signed_contract=None, financing_option_chosen=None, vertrag_am=None,
                 status_fehler=None)
    if kombi:
        werte.update(kombi_angebote=kombi.get("nummern"), kombi_gesamtrate_cent=kombi.get("gesamtrate_cent"),
                     kombi_gesamtrate_mit_cent=kombi.get("gesamtrate_mit_cent"))
    else:
        werte.update(kombi_angebote=None, kombi_gesamtrate_cent=None, kombi_gesamtrate_mit_cent=None)
    if alt_projekt:
        alte = list(cloover.json_lesen(angebot).get("alt_projekte") or [])
        if alt_projekt not in alte:
            alte.append(alt_projekt)
        werte["alt_projekte"] = alte
    cloover.json_schreiben(angebot, **werte)
    zusatz = ""
    if kombi:
        zusatz = f" (Kombi-Versand: {', '.join(kombi.get('nummern') or [])})"
    if alt_projekt:
        zusatz += f" – ersetzt Cloover-Projekt {alt_projekt}, das bei Cloover stehen bleibt (Rückfrage B5)"
    _notiz(session, angebot, benutzer, f"Cloover-Projekt {ergebnis['projekt_id']} angelegt{zusatz}.")
    _chat(session, angebot, benutzer,
          f"Cloover-Projekt {ergebnis['projekt_id']} angelegt – persönlicher Finanzierungs-Link im "
          f"Angebot {angebot.nummer}{zusatz}.")


def _fassung_b(session, angebot, benutzer) -> str:
    """Fassung B (mit Link + QR) drucken und die Ablage ersetzen – Meldung bei Fehler, sonst ""."""
    from app import pdf_export
    pfad = pdf_export.pdf_fuer_angebot(session, angebot, benutzer=benutzer)
    return nach_pdf(session, angebot, pfad)


# --- Einzelangebot --------------------------------------------------------------------------------

def anlegen_fuer(session, angebot, benutzer, *, fassung_b: bool = False) -> tuple[bool, str]:
    """Cloover-Projekt für EIN Angebot (Schritte 1–4, optional 5 = Fassung B). (ok, Meldung).
    Netz-I/O erst nach `verbindung_freigeben` – die Sitzung wird danach nur zum Schreiben benutzt."""
    daten = cloover.json_lesen(angebot)
    if daten.get("projekt_id"):
        if fassung_b:
            meldung = _fassung_b(session, angebot, benutzer)
            return True, f"Cloover-Projekt {daten['projekt_id']} vorhanden – PDF aktualisiert." + (" " + meldung if meldung else "")
        return True, f"Cloover-Projekt {daten['projekt_id']} vorhanden."
    plan = _plan(session, [angebot], benutzer)
    gruende = plan["gruende"].get(angebot.id) or []
    if gruende:
        meldung = MELDUNG_PREFIX + "; ".join(gruende)
        _fehler_merken(session, angebot, meldung)
        session.commit()
        return False, meldung
    verbindung_freigeben(session)
    _rate(angebot.id)
    from app import pdf_export
    pfad_a = pdf_export.pdf_fuer_angebot(session, angebot, benutzer=benutzer)   # Fassung A: noch kein checkout_link
    verbindung_freigeben(session)
    ablage, fehler = _ablegen_und_pruefen(angebot, pfad_a, plan["ablage"])
    if ablage is None:
        meldung = MELDUNG_PREFIX + fehler
        _fehler_merken(session, angebot, meldung)
        session.commit()
        return False, meldung
    try:
        ergebnis = cloover_api.projekt_anlegen(plan["kunde"], plan["adresse"], plan["assets"][angebot.id],
                                               plan["laufzeit"], plan["optionen"], [ablage["url"]],
                                               plan["user_email"])
    except cloover_api.ClooverFehler as problem:
        meldung = MELDUNG_PREFIX + problem.meldung
        _fehler_merken(session, angebot, meldung)
        session.commit()
        return False, meldung
    _projekt_speichern(session, angebot, ergebnis, ablage, benutzer)
    session.commit()
    meldung = f"Cloover-Projekt {ergebnis['projekt_id']} angelegt – persönlicher Finanzierungs-Link im PDF."
    if fassung_b:
        zusatz = _fassung_b(session, angebot, benutzer)
        if zusatz:
            meldung += " " + zusatz
    return True, meldung


def vor_pdf(session, angebot, benutzer) -> str:
    """Hook 1 des „Versand vorbereiten“: Projekt anlegen, falls relevant und noch keins da; Meldung
    (leer, wenn Cloover für das Angebot nicht relevant ist oder das Projekt schon existiert)."""
    try:
        ok, _grund = _relevant(session, angebot)
        if not ok:
            return ""
        if cloover.json_lesen(angebot).get("projekt_id"):
            return ""
        _ok, meldung = anlegen_fuer(session, angebot, benutzer)
        return meldung
    except Exception as fehler:   # noqa: BLE001 – der Versand darf an Cloover nie scheitern
        log.exception("Cloover: Projekt beim Versand nicht angelegt")
        try:
            session.rollback()
            _fehler_merken(session, angebot, MELDUNG_PREFIX + f"{type(fehler).__name__}: {str(fehler)[:160]}")
            session.commit()
        except Exception:   # noqa: BLE001
            pass
        return MELDUNG_PREFIX + f"{type(fehler).__name__}: {str(fehler)[:160]}"


def nach_pdf(session, angebot, pdf_pfad) -> str:
    """Hook 2: das gedruckte Versand-PDF (Fassung B mit Link + QR) in die Ablage spielen (gleiche URL).
    Meldung bei Fehler („Cloover-PDF nicht aktualisiert: …“), sonst ""."""
    daten = cloover.json_lesen(angebot)
    ablage = daten.get("pdf_ablage")
    if not (daten.get("projekt_id") and isinstance(ablage, dict) and ablage.get("url")):
        return ""
    verbindung_freigeben(session)
    try:
        neu = cloover_pdf_ablage.ersetzen(ablage, Path(pdf_pfad))
    except cloover_pdf_ablage.AblageFehler as fehler:
        text = f"Cloover-PDF nicht aktualisiert: {fehler.meldung}"
        cloover.json_schreiben(angebot, pdf_ablage_fehler=text[:300])
        session.commit()
        return text
    except Exception as fehler:   # noqa: BLE001
        text = f"Cloover-PDF nicht aktualisiert: {type(fehler).__name__}: {str(fehler)[:120]}"
        cloover.json_schreiben(angebot, pdf_ablage_fehler=text[:300])
        session.commit()
        return text
    cloover.json_schreiben(angebot, pdf_ablage={k: v for k, v in neu.items() if k != "download_url"},
                           pdf_ablage_fehler=None)
    session.commit()
    return ""


# --- Kombi-Versand --------------------------------------------------------------------------------

def _gesamtrate(plan: dict, ids: list[int]) -> tuple[int | None, int | None]:
    """Gesamtrate über alle Assets der Kombi-Mail (eine v2-Anfrage, Rückfall v1 über die Summe der
    Endbeträge); (ohne, mit Förderung) in Cent oder (None, None)."""
    assets = [a for i in ids for a in plan["assets"].get(i, [])]
    if not assets:
        return None, None
    try:
        ergebnis = cloover_api.rate_berechnen(assets, plan["laufzeit_jahre"], plan["anzahlung_cent"],
                                              plan["user_email"],
                                              brutto_cent=sum(plan["endbetrag"].get(i, 0) for i in ids))
    except cloover_api.ClooverFehler as fehler:
        log.warning("Cloover: Gesamtrate nicht ermittelt (%s)", fehler.meldung)
        return None, None
    return ergebnis.get("rate_ohne_cent"), ergebnis.get("rate_mit_cent")


def anlegen_fuer_kombi(session, angebote: list, benutzer) -> tuple[bool, str]:
    """EIN Cloover-Projekt für alle Cloover-fähigen Tool-Angebote einer Kombi-Mail (Assets je Angebot,
    offerPDF = alle PDF-URLs, derselbe Link in allen cloover_json). Haben bereits alle relevanten Angebote
    dasselbe Projekt → nichts zu tun; sonst neues Projekt für alle (alte Projekte bleiben bei Cloover,
    Verlauf) [ANNAHME]. (ok, Meldung)."""
    relevante = []
    for angebot in angebote:
        if getattr(angebot, "extern", False):
            continue
        ok, _grund = _relevant(session, angebot)
        if ok:
            relevante.append(angebot)
    if not relevante:
        return True, ""
    vorhandene = {cloover.json_lesen(a).get("projekt_id") for a in relevante}
    if len(vorhandene) == 1 and None not in vorhandene and "" not in vorhandene:
        return True, ""
    plan = _plan(session, relevante, benutzer)
    gruende_alle = sorted({g for liste in plan["gruende"].values() for g in liste})
    if gruende_alle:
        meldung = MELDUNG_PREFIX + "; ".join(gruende_alle)
        for a in relevante:
            _fehler_merken(session, a, meldung)
        session.commit()
        return False, meldung
    # alte Projekt-IDs merken und die Projektfelder leeren, damit Fassung A ohne Link druckt
    alt: dict[int, str] = {}
    for a in relevante:
        pid = cloover.json_lesen(a).get("projekt_id")
        if pid:
            alt[a.id] = str(pid)
            cloover.json_schreiben(a, projekt_id=None, checkout_link=None, financial_offer=None, pdf_url=None,
                                   pdf_ablage=None, status=None, status_stand=None, vertrag_am=None,
                                   primary_signed_contract=None, financing_option_chosen=None)
    session.commit()
    verbindung_freigeben(session)
    for a in relevante:
        _rate(a.id)
    ids = [a.id for a in relevante]
    gesamt_ohne, gesamt_mit = _gesamtrate(plan, ids)
    from app import pdf_export
    ablagen: dict[int, dict] = {}
    for a in relevante:
        pfad_a = pdf_export.pdf_fuer_angebot(session, a, benutzer=benutzer)
        verbindung_freigeben(session)
        ablage, fehler = _ablegen_und_pruefen(a, pfad_a, plan["ablage"])
        if ablage is None:
            meldung = MELDUNG_PREFIX + f"{a.nummer}: {fehler}"
            for b in relevante:
                _fehler_merken(session, b, meldung)
            session.commit()
            return False, meldung
        ablagen[a.id] = ablage
    assets = [asset for a in relevante for asset in plan["assets"][a.id]]
    try:
        ergebnis = cloover_api.projekt_anlegen(plan["kunde"], plan["adresse"], assets, plan["laufzeit"],
                                               plan["optionen"], [ablagen[a.id]["url"] for a in relevante],
                                               plan["user_email"])
    except cloover_api.ClooverFehler as problem:
        meldung = MELDUNG_PREFIX + problem.meldung
        for a in relevante:
            _fehler_merken(session, a, meldung)
        session.commit()
        return False, meldung
    kombi = {"nummern": [a.nummer for a in relevante], "gesamtrate_cent": gesamt_ohne,
             "gesamtrate_mit_cent": gesamt_mit}
    for a in relevante:
        _projekt_speichern(session, a, ergebnis, ablagen[a.id], benutzer, kombi=kombi, alt_projekt=alt.get(a.id, ""))
    session.commit()
    meldung = (f"Cloover-Projekt {ergebnis['projekt_id']} für {len(relevante)} Angebote angelegt "
               f"({', '.join(kombi['nummern'])}) – derselbe Finanzierungs-Link in allen PDFs")
    if gesamt_ohne is not None:
        meldung += f", Gesamtrate ab {cloover_api.eur_text(gesamt_ohne)} €/Monat"
    return True, meldung + "."


def vor_pdf_kombi(session, angebote: list, benutzer) -> str:
    """Hook 1 des Kombi-Versands (vor dem Druck der PDFs)."""
    try:
        _ok, meldung = anlegen_fuer_kombi(session, angebote, benutzer)
        return meldung
    except Exception as fehler:   # noqa: BLE001
        log.exception("Cloover: Kombi-Projekt nicht angelegt")
        try:
            session.rollback()
        except Exception:   # noqa: BLE001
            pass
        return MELDUNG_PREFIX + f"{type(fehler).__name__}: {str(fehler)[:160]}"


def nach_pdf_kombi(session, angebote: list, pdfs: list) -> list[str]:
    """Hook 2 des Kombi-Versands: jedes gedruckte Tool-PDF (Fassung B) in seine Ablage spielen."""
    meldungen = []
    for angebot, pfad in zip(angebote, pdfs):
        if getattr(angebot, "extern", False):
            continue
        try:
            text = nach_pdf(session, angebot, pfad)
        except Exception as fehler:   # noqa: BLE001
            text = f"{angebot.nummer}: Cloover-PDF nicht aktualisiert ({type(fehler).__name__})"
        if text:
            meldungen.append(text)
    return meldungen


# --- Status ---------------------------------------------------------------------------------------

def _status_aendern(daten_alt: dict, ergebnis: dict) -> dict:
    """Änderungen der drei Felder gegenüber cloover_json (nur geänderte Schlüssel)."""
    neu = {}
    status = ergebnis.get("status")
    if status is not None and str(status) != str(daten_alt.get("status") or ""):
        neu["status"] = str(status)
    unterschrieben = _wahr(ergebnis.get("primary_signed_contract"))
    if unterschrieben != _wahr(daten_alt.get("primary_signed_contract")):
        neu["primary_signed_contract"] = unterschrieben
    option = ergebnis.get("financing_option_chosen")
    if option is not None and str(option) != str(daten_alt.get("financing_option_chosen") or ""):
        neu["financing_option_chosen"] = str(option)
    return neu


def _ad_id(session, angebot) -> int | None:
    try:
        from app import mail_vorlagen
        ad = mail_vorlagen.vertriebler_fuer_angebot(session, angebot)
        return ad.id if ad is not None and ad.aktiv else None
    except Exception:   # noqa: BLE001
        return None


def _glocke(session, benutzer_ids, text: str, link: str) -> int:
    """Glocke art `cloover` direkt anlegen (ohne Sofort-Mail – Muster verfolgung v32)."""
    anzahl = 0
    for bid in {b for b in benutzer_ids if b}:
        session.add(Benachrichtigung(benutzer_id=bid, text=text[:500], link=link[:300], art=GLOCKE_ART))
        anzahl += 1
    return anzahl


def _status_anwenden(session, angebot, ergebnis: dict, benutzer=None) -> dict:
    """Antwort von GET /api/projects/{id} in cloover_json übernehmen; Verlauf, Badge, Chat, Glocke.
    Liefert {geaendert: bool, vertrag_neu: bool, bar_neu: bool, status: str}. Kein Statuswechsel am Angebot."""
    alt = cloover.json_lesen(angebot)
    aenderungen = _status_aendern(alt, ergebnis)
    werte = dict(aenderungen)
    werte["status_stand"] = _jetzt_text()
    werte["status_fehler"] = None
    vertrag_neu = bool(aenderungen.get("primary_signed_contract"))
    if vertrag_neu:
        werte["vertrag_am"] = _datum_text(ergebnis.get("contract_signed_date"))
    bar_neu = (aenderungen.get("financing_option_chosen") or "").strip().lower() == "cash"
    cloover.json_schreiben(angebot, **werte)
    if not aenderungen:
        return {"geaendert": False, "vertrag_neu": False, "bar_neu": False,
                "status": str(alt.get("status") or ergebnis.get("status") or "")}
    teile = []
    if "status" in aenderungen:
        teile.append(aenderungen["status"])
    if vertrag_neu:
        teile.append(f"Vertrag unterschrieben ({werte['vertrag_am']})")
    elif "primary_signed_contract" in aenderungen:
        teile.append("Vertrag nicht mehr unterschrieben")
    if "financing_option_chosen" in aenderungen:
        teile.append("Barzahlung gewählt" if bar_neu else f"Option {aenderungen['financing_option_chosen']}")
    _notiz(session, angebot, benutzer, "Cloover: " + " · ".join(teile))
    if vertrag_neu:
        datum = werte["vertrag_am"]
        _chat(session, angebot, benutzer,
              f"Cloover: Vertrag unterschrieben ({datum}) – Angebot {angebot.nummer}. {TEXT_ANGENOMMEN_FRAGE}")
        vorgang_id = getattr(angebot, "vorgang_id", None)
        text = f"Cloover: Vertrag unterschrieben ({datum}) – {angebot.nummer}. {TEXT_ANGENOMMEN_FRAGE}"
        _glocke(session, [alt.get("projekt_von")], text, f"/angebote/{angebot.id}#cloover")
        ad = _ad_id(session, angebot)
        if ad and ad != alt.get("projekt_von"):
            _glocke(session, [ad], text, f"/vorgaenge/{vorgang_id}" if vorgang_id else f"/meine-angebote/{angebot.id}")
    return {"geaendert": True, "vertrag_neu": vertrag_neu, "bar_neu": bar_neu,
            "status": aenderungen.get("status") or str(alt.get("status") or "")}


def status_abrufen_fuer(angebot_id: int, benutzer=None) -> dict:
    """Knopf „Status jetzt abrufen“ / ein Durchlauf des Laufs je Angebot: lesen (kurz) → Sitzung zu →
    GET /api/projects/{id} → kurze Schreibsitzung. {ok, meldung, geaendert, status, vertrag_neu}."""
    from app import db
    with db.kurz(schreibend=False) as s:
        angebot = s.get(Angebot, angebot_id)
        if angebot is None:
            return {"ok": False, "meldung": "Angebot nicht gefunden", "geaendert": False, "status": ""}
        projekt_id = cloover.json_lesen(angebot).get("projekt_id")
        nummer = angebot.nummer
    if not projekt_id:
        return {"ok": False, "meldung": f"{nummer}: kein Cloover-Projekt", "geaendert": False, "status": ""}
    try:
        ergebnis = cloover_api.projekt_status(str(projekt_id))
    except cloover_api.ClooverFehler as fehler:
        with db.kurz() as s:
            angebot = s.get(Angebot, angebot_id)
            if angebot is not None:
                cloover.json_schreiben(angebot, status_fehler=fehler.meldung[:300], status_stand=_jetzt_text())
        return {"ok": False, "meldung": f"{nummer}: {fehler.meldung}", "geaendert": False, "status": ""}
    with db.kurz() as s:
        angebot = s.get(Angebot, angebot_id)
        if angebot is None:
            return {"ok": False, "meldung": "Angebot nicht gefunden", "geaendert": False, "status": ""}
        info = _status_anwenden(s, angebot, ergebnis, benutzer)
    text = status_text(ergebnis_dict={"status": ergebnis.get("status"),
                                      "primary_signed_contract": ergebnis.get("primary_signed_contract"),
                                      "financing_option_chosen": ergebnis.get("financing_option_chosen"),
                                      "vertrag_am": _datum_text(ergebnis.get("contract_signed_date"))
                                      if _wahr(ergebnis.get("primary_signed_contract")) else None})
    meldung = f"{nummer}: Cloover-Status {text}" + (" (geändert)" if info["geaendert"] else " (unverändert)")
    return {"ok": True, "meldung": meldung, "geaendert": info["geaendert"], "status": info["status"],
            "vertrag_neu": info["vertrag_neu"]}


def kandidaten(session, limit: int = LAUF_MAX, jetzt: datetime | None = None) -> list[int]:
    """Angebots-IDs für den Status-Lauf: projekt_id vorhanden, Status prüfbar, nicht archiviert,
    Projekt jünger als 180 Tage, älteste Prüfung zuerst."""
    jetzt = jetzt or datetime.now()
    grenze = jetzt - timedelta(days=PROJEKT_MAX_TAGE)
    treffer = []
    for angebot in (session.query(Angebot)
                    .filter(Angebot.cloover_json.like('%"projekt_id"%'),
                            Angebot.status.in_(STATUS_PRUEFBAR), Angebot.archiviert.is_(False))
                    .order_by(Angebot.id)):
        daten = cloover.json_lesen(angebot)
        if not daten.get("projekt_id"):
            continue
        angelegt = _datum_lesen(daten.get("projekt_am")) or angebot.datum or jetzt
        if angelegt < grenze:
            continue
        stand = _datum_lesen(daten.get("status_stand")) or datetime.min
        treffer.append((stand, angebot.id))
    treffer.sort()
    return [aid for _stand, aid in treffer[:limit]]


def _datum_lesen(text) -> datetime | None:
    for muster in ("%d.%m.%Y %H:%M", "%d.%m.%Y"):
        try:
            return datetime.strptime(str(text or ""), muster)
        except ValueError:
            continue
    return None


def status_lauf() -> str:
    """Scheduler-Lauf cloover-status (60 min): höchstens LAUF_MAX Angebote je Lauf."""
    from app import db
    if not cloover_api.konfiguriert():
        return "inaktiv (kein Cloover-Key)"
    with db.kurz(schreibend=False) as s:
        ids = kandidaten(s)
    geaendert = fehler = vertraege = 0
    for angebot_id in ids:
        ergebnis = status_abrufen_fuer(angebot_id)
        if not ergebnis["ok"]:
            fehler += 1
        elif ergebnis["geaendert"]:
            geaendert += 1
            if ergebnis.get("vertrag_neu"):
                vertraege += 1
    geraeumt = 0
    jetzt = datetime.now()
    if jetzt.hour == 3:
        try:
            geraeumt = cloover_pdf_ablage.abgelaufene_tokens_raeumen(jetzt)
        except Exception:   # noqa: BLE001
            geraeumt = 0
    text = f"{len(ids)} geprüft, {geaendert} geändert, {vertraege} Verträge, {fehler} Fehler"
    if geraeumt:
        text += f", {geraeumt} abgelaufene Token-PDFs entfernt"
    return text


def _lauf_aktiv():
    return True if cloover_api.konfiguriert() else "kein Cloover-Key (CLOOVER_API_KEY in der .env)"


def scheduler_starten() -> None:
    """Lauf cloover-status registrieren (Aufruf aus main.lifespan) – 18. Lauf, Pool-Invariante
    64 + 18 + 5 = 87 ≤ 90."""
    from app import scheduler
    scheduler.registrieren(LAUF_NAME, LAUF_INTERVALL_S, status_lauf,
                           beschreibung="Cloover: Projektstatus (Vertrag unterschrieben / Barzahlung) je Angebot abrufen",
                           start_verzoegerung_s=LAUF_START_S, aktiv=_lauf_aktiv)


# --- Anzeige: Badge, Statustext, Editor, Liste, Statistik ------------------------------------------

def status_text(daten: dict | None = None, *, ergebnis_dict: dict | None = None) -> str:
    """Lesbarer Cloover-Stand aus cloover_json (oder einer Status-Antwort): „Vertrag unterschrieben
    (TT.MM.JJJJ)“, „Barzahlung gewählt“, roher status-Wert (Rückfrage B8) oder „angelegt, noch keine
    Rückmeldung“."""
    d = ergebnis_dict if ergebnis_dict is not None else (daten or {})
    teile = []
    if _wahr(d.get("primary_signed_contract")):
        teile.append(f"Vertrag unterschrieben ({d.get('vertrag_am') or datetime.now().strftime('%d.%m.%Y')})")
    option = (d.get("financing_option_chosen") or "").strip()
    if option.lower() == "cash":
        teile.append("Barzahlung gewählt")
    elif option:
        teile.append(f"Option {option}")
    status = str(d.get("status") or "").strip()
    if status:
        teile.append(status)
    return " · ".join(teile) if teile else "angelegt, noch keine Rückmeldung"


def badge_fuer(angebot_oder_json) -> dict | None:
    """Badge für Editor, Angebotsliste, Vorgangsakte (Jinja-Global `cloover_badge_info`, ohne Datenbank):
    {text, klasse, titel} oder None ohne Projekt. Vertrag → grün, Barzahlung → grau, sonst „Cloover-Link“."""
    daten = (angebot_oder_json if isinstance(angebot_oder_json, dict)
             else cloover.json_lesen(angebot_oder_json))
    if not daten.get("projekt_id"):
        return None
    if _wahr(daten.get("primary_signed_contract")):
        return {"text": BADGE_VERTRAG.format(datum=daten.get("vertrag_am") or "–"), "klasse": "status-angenommen",
                "titel": f"Cloover-Projekt {daten['projekt_id']}: Finanzierungsvertrag unterschrieben – "
                         f"{TEXT_ANGENOMMEN_FRAGE}", "art": "vertrag"}
    if (daten.get("financing_option_chosen") or "").strip().lower() == "cash":
        return {"text": BADGE_BAR, "klasse": "status-ueberholt",
                "titel": f"Cloover-Projekt {daten['projekt_id']}: der Kunde hat im Checkout Barzahlung gewählt",
                "art": "bar"}
    return {"text": BADGE_LINK, "klasse": "status-versendet", "art": "link",
            "titel": f"Cloover-Projekt {daten['projekt_id']}: persönlicher Finanzierungs-Link im Angebot"
                     + (f" – Stand: {daten['status']}" if daten.get("status") else "")}


def sortwert(angebot):
    """Sortierwert der Spalte „Cloover“ (Angebotsliste): 0 Vertrag · 1 Barzahlung · 2 Link · leer."""
    badge = badge_fuer(angebot)
    if badge is None:
        return None
    return {"vertrag": 0, "bar": 1, "link": 2}.get(badge["art"], 3)


def editor_kontext(session, angebot, kunde=None, benutzer=None) -> dict:
    """Kontext des Editor-Blocks templates/angebote/_cloover_projekt.html (ID/Admin)."""
    daten = cloover.json_lesen(angebot)
    relevant, grund = _relevant(session, angebot)
    gruende = voraussetzungen(session, angebot, kunde) if relevant else []
    darf = getattr(benutzer, "basisrolle", "") in ("admin", "innendienst")
    ablage = daten.get("pdf_ablage") if isinstance(daten.get("pdf_ablage"), dict) else {}
    return {
        "aktiv": bool(relevant) and cloover_api.modus(session) != "aus",
        "grund": grund, "daten": daten, "projekt_id": daten.get("projekt_id") or "",
        "checkout_link": daten.get("checkout_link") or "", "financial_offer": daten.get("financial_offer") or "",
        "financial_offer_ist_url": str(daten.get("financial_offer") or "").lower().startswith(("http://", "https://")),
        "pdf_url": daten.get("pdf_url") or "", "ablage_anbieter": ablage.get("anbieter") or "",
        "ablage_ablauf": ablage.get("ablauf") or "", "status_text": status_text(daten),
        "status_stand": daten.get("status_stand") or "", "status_fehler": daten.get("status_fehler") or "",
        "vertrag_am": daten.get("vertrag_am") or "", "vertrag": _wahr(daten.get("primary_signed_contract")),
        "barzahlung": (daten.get("financing_option_chosen") or "").strip().lower() == "cash",
        "badge": badge_fuer(daten), "gruende": gruende, "projekt_fehler": daten.get("projekt_fehler") or "",
        "pdf_ablage_fehler": daten.get("pdf_ablage_fehler") or "", "projekt_am": daten.get("projekt_am") or "",
        "projekt_von_name": daten.get("projekt_von_name") or "",
        "kombi_angebote": daten.get("kombi_angebote") or [],
        "kombi_gesamtrate_text": (cloover_api.eur_text(daten["kombi_gesamtrate_cent"])
                                  if daten.get("kombi_gesamtrate_cent") else ""),
        "alt_projekte": daten.get("alt_projekte") or [],
        "kann_anlegen": bool(darf and relevant and not daten.get("projekt_id") and not gruende
                             and angebot.status in STATUS_PROJEKT_ERLAUBT),
        "kann_status": bool(darf and daten.get("projekt_id")),
        "angenommen_vorschlag": bool(_wahr(daten.get("primary_signed_contract")) and angebot.status != "Angenommen"),
        "darf": darf,
    }


def statistik(session, von: datetime, bis: datetime, nur_benutzer_id: int | None = None) -> dict:
    """Kennzahl „Cloover-Verträge“ (Reiter Angebote der Statistik) [ANNAHME]: Angebote, deren Cloover-
    Projekt im Zeitraum als unterschrieben zurückgemeldet wurde (vertrag_am), Anzahl + Summe Endbetrag;
    Außendienst nur eigene (Vertriebler-Zuordnung wie statistik.kennzahlen)."""
    anzahl, summe = 0, 0
    zuordnung = None
    if nur_benutzer_id is not None:
        try:
            from app.routers import statistik as statistik_router
            zuordnung = statistik_router._vertriebler_map(session)
        except Exception:   # noqa: BLE001
            zuordnung = {}
    for angebot in (session.query(Angebot)
                    .filter(Angebot.cloover_json.like('%"primary_signed_contract"%'),
                            Angebot.bestand.is_(False))):
        daten = cloover.json_lesen(angebot)
        if not _wahr(daten.get("primary_signed_contract")):
            continue
        datum = _datum_lesen(daten.get("vertrag_am"))
        if datum is None or not (von <= datum < bis):
            continue
        if zuordnung is not None and zuordnung.get(angebot.id) != nur_benutzer_id:
            continue
        anzahl += 1
        summe += angebot.summen()["endbetrag"]
    return {"anzahl": anzahl, "summe_cent": summe}


def liste_badges(angebote) -> dict[int, dict]:
    """{angebot_id: Badge} für Listen (ohne Datenbank)."""
    ergebnis = {}
    for a in angebote:
        badge = badge_fuer(a)
        if badge:
            ergebnis[a.id] = badge
    return ergebnis
