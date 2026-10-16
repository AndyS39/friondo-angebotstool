"""v36 (PLAN_V22 Phase 193/194): Cloover-Finanzierung am Angebot – gemeinsame Ablage `angebote.cloover_json`.

Fundament (Orchestrator): JSON-Helfer und Feldliste, damit Agent B2 (Rate, Editor-Karte, PDF-Karte, Platzhalter)
und Agent B3 (PDF-Ablage, Cloover-Projekt, QR/Link, Status-Lauf – Modul `app/cloover_projekt.py`) parallel
arbeiten können. Netzaufrufe laufen ausschließlich über `app/cloover_api.py` (Agent B1) und nie mit offener
Datenbanksitzung; Schreibzugriffe im `_speichern`-Muster bzw. `db.kurz()`.

`cloover_json` (additiv, Standard "{}"):
  laufzeit_jahre, anzahlung_cent, rate_ohne_cent, rate_mit_cent (nur WP mit Förderung), endbetrag_cent,
  foerderung_cent, ust_satz, stand ("TT.MM.JJJJ HH:MM" der letzten Rate), quelle ("v2" | "v1"), fehler (Text),
  projekt_id, checkout_link, financial_offer, pdf_url, status, status_stand, primary_signed_contract,
  financing_option_chosen, vertrag_am, ausgeblendet (bool – „Finanzierung im PDF ausblenden“)
Überarbeiten/Duplizieren/Kopieren übernehmen nur laufzeit_jahre, anzahlung_cent, ausgeblendet
(`uebernehmen_bei_kopie`); Rate und Projekt werden für die neue Version neu ermittelt.

Phase 193 (Agent B2) – Rate im Angebot:
  - `relevant(session, angebot)`: (True, "") oder (False, Grund) – Modus „aus“, Profil Enni/SWD/Sparkasse DU,
    Sparte außerhalb `cloover_sparten`, `ausgeblendet`, externer TAIFUN-Eintrag.
  - `voraussetzungen(session, angebot)`: rote Hinweise der Editor-Karte und Voraussetzungen des Cloover-
    Projekts (Agent B3 nutzt dieselben Prüfungen): E-Mail/Telefon des Kunden, Privatkunde (`kunden.firma`
    leer [ANNAHME], kein Großkunde), Ausführungsort mit Straße/PLZ/Ort.
  - `rate_aktualisieren(angebot_id, *, erzwingen=False, benutzer_id=None)`: AUSSERHALB der Sitzung –
    `db.kurz(schreibend=False)` lesen → Sitzung zu → `cloover_api.rate_berechnen` → kurze Schreibsitzung
    (eine Wiederholung bei „database is locked“, `_speichern`-Muster). Rechnet nur, wenn `stand` fehlt oder
    Endbetrag/Förderung/USt/Laufzeit/Anzahlung vom gespeicherten Stand abweichen (oder `erzwingen`).
    Aufrufer: `pdf_export.pdf_fuer_angebot`/`signiertes_pdf_erzeugen` (vor jeder PDF-Erzeugung, nie beim
    eingefrorenen Archiv-PDF), „Versand vorbereiten“/Kombi-Versand (Agent B3), Knopf „Rate neu berechnen“,
    Speichern von Laufzeit/Anzahlung in der Editor-Karte. Fehler blockieren nie: die letzte Rate bleibt mit
    `stand`, `fehler` trägt den Grund.
  - `kontext_fuer_pdf(session, angebot)`: Teilbaum `auftrag.cloover` für pdf_kontext (Layout v3) – rate_text,
    rate_mit_text, laufzeit, fussnote (Textbaustein `cloover_fussnote`), checkout_link, link_kurz, qr_svg
    (Bibliothek `qrcode`, 22 × 22 mm, Fehlerkorrektur M), datenschutz (Textbaustein `cloover_datenschutz`),
    hinweis_link; None = nicht relevant; ohne Rate leere Texte → „Monatsrate auf Anfrage“. Nur lesend.
  - `editor_kontext(session, angebot, benutzer=None)`: Werte der Editor-Karte „Finanzierung (Cloover)“ und der
    AD-Lesesicht (nie EK/DB).
  - `mail_platzhalter(session, angebot)` / `kombi_platzhalter(session, angebote)`: {cloover_rate},
    {cloover_link}, {cloover_finanzierungsangebot} für Angebots- und Kombi-Vorlagen.
  - fpdf2-Rückfall: Platzhalter `[CLOOVER]` im Nachtext (app/angebotsprofile.migriere_cloover_platzhalter),
    gerendert in `pdf_export._nachtext_rendern` mit `qr_matrix` (Rechtecke).
"""
from __future__ import annotations

import json
import logging
import re
import time
from datetime import datetime

log = logging.getLogger("angebotstool.cloover")

FELDER = ("laufzeit_jahre", "anzahlung_cent", "rate_ohne_cent", "rate_mit_cent", "endbetrag_cent",
          "foerderung_cent", "ust_satz", "stand", "quelle", "fehler", "projekt_id", "checkout_link",
          "financial_offer", "pdf_url", "status", "status_stand", "primary_signed_contract",
          "financing_option_chosen", "vertrag_am", "ausgeblendet",
          # B2: Basis der zuletzt berechneten Rate (laufzeit_jahre/anzahlung_cent sind die Wahl des
          # Innendiensts; weichen sie von der Basis ab, wird vor dem nächsten PDF neu gerechnet)
          "rate_laufzeit_jahre", "rate_anzahlung_cent")
KOPIE_FELDER = ("laufzeit_jahre", "anzahlung_cent", "ausgeblendet")
GLOCKE_ART = "cloover"            # Glocke an vorbereitenden Innendienstler + AD (ohne Mail), Phase 194
LAUF_NAME = "cloover-status"      # Scheduler-Lauf (60 min), Phase 194 – Agent B3
TEXT_FUSSNOTE = "cloover_fussnote"          # Textbaustein (Parametrierung), Platzhalter {endbetrag} {laufzeit} {anzahlung} {foerderung} {stand}
TEXT_DATENSCHUTZ = "cloover_datenschutz"    # Textbaustein (Parametrierung), Entwurf laut Plan (Rückfrage B7)

# --- Phase 193 (Agent B2) -------------------------------------------------------------------------
PROFILE_OHNE_CLOOVER = ("enni", "swd", "sparkasse")   # Entscheidung 15./16.10.2026: keine Karte, keine Rate
LAUFZEIT_MIN, LAUFZEIT_MAX = 1, 25                    # durationInYears laut Swagger
# Laufzeit/Anzahlung/ausblenden und „Rate neu berechnen“ nur in diesen Status [ANNAHME] – danach ist das
# PDF eingefroren (pdf_export.pdf_eingefroren) bzw. entsteht über „Überarbeiten“ eine neue Version
STATUS_AENDERBAR = ("Entwurf", "Versand vorbereitet")
STAND_FORMAT = "%d.%m.%Y %H:%M"
QR_MM = 22                     # Kantenlänge des QR-Codes im PDF (Plan Phase 194)
QR_RAND = 2                    # Ruhezone in Modulen (Rechtecke im fpdf2-Rückfall ebenso)
LINK_KURZ_MAX = 70

HINWEIS_LINK = "Ihren persönlichen Finanzierungs-Link erhalten Sie von uns per E-Mail."
RATE_AUF_ANFRAGE = "Monatsrate auf Anfrage"
RATEN_TITEL = "Planbare Monatsraten – Ihre Rate für dieses Angebot:"
LAUFZEIT_ANGELEGT = "Ihre Finanzierungsanfrage ist bereits angelegt – nur noch bestätigen."
KNOPF_ABSCHLIESSEN = "Finanzierung abschließen ›"
RUECKMELDUNG = "Prüfung und Zusage erfolgen direkt bei Cloover; Friondo erhält eine Rückmeldung über den Stand."
# Kombi-Versand (Agent B3 legt `kombi_gesamtrate_cent` ab – ein Cloover-Projekt je Kombi-Mail) [ANNAHME Plan, B6]
KOMBI_GESAMTRATE = "Gesamtrate für alle Angebote dieser Mail: ab {betrag} pro Monat"

GRUND_EXTERN = "Externer TAIFUN-Eintrag – keine Cloover-Rate"
GRUND_MODUS_AUS = "Cloover ist aus (kein API-Key in der .env oder Modus „aus“ in der Parametrierung)"
GRUND_AUSGEBLENDET = "Finanzierung im PDF ausgeblendet"
HINWEIS_EMAIL = "E-Mail des Kunden fehlt"
HINWEIS_TELEFON = "Telefon fehlt"
HINWEIS_FIRMA = "Firmenkunde – Cloover nur für Privatkunden"
HINWEIS_GROSSKUNDE = "Großkunde – Cloover nur für Privatkunden"       # [ANNAHME] Kennzeichen v31 zählt wie Firma
HINWEIS_ADRESSE = "Ausführungsort unvollständig (Straße, PLZ, Ort)"
MELDUNG_RATE_FEHLT = "Cloover-Rate nicht verfügbar: {grund}"

# Rückfall-Wortlaute (wörtlich aus dem Plan), falls app/cloover_texte.py (Agent B1) fehlt
_FOERDERUNG_TEILSATZ = ("; ‚mit Förderung‘ berücksichtigt die voraussichtliche Förderung von {foerderung} als "
                        "Sondertilgung nach Auszahlung")
FUSSNOTE_RUECKFALL = ("*Unverbindliche Beispielrechnung unseres Finanzierungspartners Cloover auf Basis des "
                      "Endbetrags dieses Angebots von {endbetrag}, einer Laufzeit von {laufzeit} Jahren und "
                      "{anzahlung} Anzahlung" + _FOERDERUNG_TEILSATZ + ". Stand {stand}. Verbindliche "
                      "Konditionen, Sollzins und effektiver Jahreszins ergeben sich aus dem "
                      "Finanzierungsangebot von Cloover.")
DATENSCHUTZ_RUECKFALL = ("Zur Bereitstellung Ihres persönlichen Finanzierungs-Links haben wir Ihre Kontaktdaten, "
                         "die Adresse des Vorhabens und dieses Angebot an unseren Finanzierungspartner Cloover "
                         "übermittelt. Hinweise zum Datenschutz: https://friondo.de/Datenschutz")


def json_lesen(angebot) -> dict:
    """Inhalt von `angebote.cloover_json` als Dict (leer/ungültig → {})."""
    roh = getattr(angebot, "cloover_json", "") or ""
    try:
        daten = json.loads(roh) if roh.strip() else {}
    except (TypeError, ValueError):
        daten = {}
    return daten if isinstance(daten, dict) else {}


def json_schreiben(angebot, **werte) -> dict:
    """Werte in `cloover_json` zusammenführen (None löscht den Schlüssel); gibt den neuen Stand zurück.
    Der Aufrufer committet (Schreibsitzung, `_speichern`-Muster)."""
    daten = json_lesen(angebot)
    for key, wert in werte.items():
        if wert is None:
            daten.pop(key, None)
        else:
            daten[key] = wert
    angebot.cloover_json = json.dumps(daten, ensure_ascii=False)
    return daten


def uebernehmen_bei_kopie(quelle, ziel) -> None:
    """Überarbeiten/Duplizieren/Kopieren: nur Laufzeit, Anzahlung, ausgeblendet übernehmen."""
    alt = json_lesen(quelle)
    ziel.cloover_json = json.dumps({k: alt[k] for k in KOPIE_FELDER if k in alt}, ensure_ascii=False)


def ausgeblendet(angebot) -> bool:
    return bool(json_lesen(angebot).get("ausgeblendet"))


# ----------------------------------------------------------------------------- Agent B2 (Phase 193)
def sparte_von(angebot) -> str:
    return (getattr(angebot, "konfigurator_typ", "") or "WP").upper()


def eur(cent) -> str:
    """Cent → „42.830,55 €“ („“ bei None)."""
    if cent is None:
        return ""
    from app import cloover_api
    return cloover_api.eur_text(int(cent)) + " €"


def rate_satz(cent, mit_foerderung: bool | None = None) -> str:
    """„ab 389,99 € pro Monat“ (+ „ mit Förderung*“ / „ ohne Förderung“ bei True/False)."""
    if cent is None:
        return ""
    text = f"ab {eur(cent)} pro Monat"
    if mit_foerderung is True:
        return text + " mit Förderung*"
    if mit_foerderung is False:
        return text + " ohne Förderung"
    return text


def stand_datum(stand) -> str:
    """„TT.MM.JJJJ HH:MM“ (gespeicherter Stand) → „TT.MM.JJJJ“ für die Fußnote."""
    text = (stand or "").strip()
    return text.split(" ")[0] if text else ""


def profil_kennung(session, angebot) -> tuple[str, str]:
    """(Regel-Kennung standard|enni|swd|sparkasse, Profilname) – wie pdf_kontext._profil."""
    from app import angebotsprofile
    profil = angebotsprofile.profil_fuer_angebot(session, angebot)
    if profil is None:
        return "standard", "Standard"
    kennung = (profil.regel_kennung or "standard").strip().lower()
    if kennung not in ("standard", "enni", "swd", "sparkasse"):
        kennung = "standard"
    return kennung, profil.name


def _grund(session, angebot, mit_ausblendung: bool = True) -> str:
    """Grund, warum für das Angebot keine Cloover-Rate ermittelt wird ("" = relevant)."""
    from app import cloover_api
    if getattr(angebot, "extern", False):
        return GRUND_EXTERN
    if cloover_api.modus(session) == "aus":
        return GRUND_MODUS_AUS
    kennung, name = profil_kennung(session, angebot)
    if kennung in PROFILE_OHNE_CLOOVER:
        return f"Profil {name} – ohne Cloover (keine Karte, keine Rate, kein Cloover-Projekt)"
    sparte = sparte_von(angebot)
    if sparte not in cloover_api.sparten(session):
        return f"Sparte {sparte} ist für Cloover nicht freigegeben (Parametrierung → Cloover, „Sparten“)"
    if mit_ausblendung and ausgeblendet(angebot):
        return GRUND_AUSGEBLENDET
    return ""


def relevant(session, angebot) -> tuple[bool, str]:
    """(True, "") wenn für das Angebot eine Cloover-Rate ermittelt wird; sonst (False, Grund): Modus aus,
    Profil Enni/SWD/Sparkasse DU, Sparte nicht in `cloover_sparten`, ausgeblendet, externer Eintrag."""
    grund = _grund(session, angebot)
    return (not grund), grund


def voraussetzungen(session, angebot, kunde=None) -> list[str]:
    """Rote Hinweise der Editor-Karte = Voraussetzungen des Cloover-Projekts (Phase 194, Agent B3 nutzt
    dieselbe Liste): „E-Mail des Kunden fehlt“, „Telefon fehlt“, „Firmenkunde – Cloover nur für
    Privatkunden“ (`kunden.firma` leer = Privatkunde [ANNAHME]; Großkunden-Kennzeichen zählt ebenso
    [ANNAHME]), „Ausführungsort unvollständig (Straße, PLZ, Ort)“. Leer = alles da. Die PDF-Ablage
    (Parameter `cloover_pdf_ablage`) prüft Agent B3 selbst."""
    from app.models import Kunde
    if kunde is None:
        kunde = session.get(Kunde, angebot.kunde_id) if getattr(angebot, "kunde_id", None) else None
    if kunde is None:
        return ["Kunde fehlt"]
    hinweise: list[str] = []
    if not (kunde.email or "").strip():
        hinweise.append(HINWEIS_EMAIL)
    if not (kunde.telefon or "").strip():
        hinweise.append(HINWEIS_TELEFON)
    if (kunde.firma or "").strip() or (kunde.anrede or "").strip().lower() == "firma":
        hinweise.append(HINWEIS_FIRMA)
    elif getattr(kunde, "grosskunde", False):
        hinweise.append(HINWEIS_GROSSKUNDE)
    try:
        from app import anschriften
        ort = anschriften.ausfuehrungsort_fuer(session, angebot=angebot, kunde=kunde)
        if not all((ort.get(feld) or "").strip() for feld in ("strasse", "plz", "ort")):
            hinweise.append(HINWEIS_ADRESSE)
    except Exception as fehler:   # noqa: BLE001 – Adressprüfung ist Zusatz, nie ein Grund abzubrechen
        log.warning("Cloover-Voraussetzungen: Ausführungsort nicht prüfbar (%s)", fehler)
    return hinweise


def laufzeit_fuer(session, angebot, daten: dict | None = None) -> int:
    """Laufzeit in Jahren: aus `cloover_json`, sonst Parameter `cloover_laufzeit_jahre`."""
    from app import cloover_api
    daten = json_lesen(angebot) if daten is None else daten
    try:
        wert = int(daten.get("laufzeit_jahre") or 0)
    except (TypeError, ValueError):
        wert = 0
    if LAUFZEIT_MIN <= wert <= LAUFZEIT_MAX:
        return wert
    return cloover_api.laufzeit_jahre(session)


def anzahlung_fuer(session, angebot, daten: dict | None = None) -> int:
    """Anzahlung in Cent: aus `cloover_json`, sonst Parameter `cloover_anzahlung_eur`."""
    from app import cloover_api
    daten = json_lesen(angebot) if daten is None else daten
    wert = daten.get("anzahlung_cent")
    if wert is None:
        return cloover_api.anzahlung_cent(session)
    try:
        return max(0, int(wert))
    except (TypeError, ValueError):
        return cloover_api.anzahlung_cent(session)


def rate_basis(daten: dict) -> tuple[int | None, int | None]:
    """(Laufzeit, Anzahlung) der zuletzt berechneten Rate – Rückfall auf die gespeicherte Wahl."""
    laufzeit = daten.get("rate_laufzeit_jahre", daten.get("laufzeit_jahre"))
    anzahlung = daten.get("rate_anzahlung_cent", daten.get("anzahlung_cent"))
    try:
        return (int(laufzeit) if laufzeit is not None else None,
                int(anzahlung) if anzahlung is not None else None)
    except (TypeError, ValueError):
        return None, None


def aenderung_noetig(daten: dict, endbetrag: int, foerderung: int, ust: float, laufzeit: int,
                     anzahlung: int) -> bool:
    """True, wenn noch keine Rate mit `stand` vorliegt oder Endbetrag/Förderung/USt/Laufzeit/Anzahlung
    von der Basis der letzten Rate abweichen."""
    if not daten.get("stand") or daten.get("rate_ohne_cent") is None:
        return True
    basis_laufzeit, basis_anzahlung = rate_basis(daten)
    try:
        return (int(daten.get("endbetrag_cent", -1)) != int(endbetrag)
                or int(daten.get("foerderung_cent", -1)) != int(foerderung)
                or abs(float(daten.get("ust_satz", -1)) - float(ust)) > 0.001
                or basis_laufzeit != int(laufzeit)
                or basis_anzahlung != int(anzahlung))
    except (TypeError, ValueError):
        return True


def _basis_lesen(session, angebot, daten: dict | None = None) -> dict:
    """Vergleichswerte des Angebots (Lesesitzung): Endbetrag, Förderung, USt, Laufzeit, Anzahlung, Sparte."""
    from app import cloover_api
    daten = json_lesen(angebot) if daten is None else daten
    summen = angebot.summen()
    return {"endbetrag": int(summen["endbetrag"]),
            "foerderung": int(cloover_api.foerderung_cent(session, angebot)),
            "ust": float(angebot.ust_prozent),
            "laufzeit": laufzeit_fuer(session, angebot, daten),
            "anzahlung": anzahlung_fuer(session, angebot, daten),
            "sparte": sparte_von(angebot)}


def rate_noetig(session, angebot) -> bool:
    """Vorprüfung für Aufrufer mit Sitzung (pdf_export): lohnt ein Aufruf von `rate_aktualisieren`?
    False bei nicht relevanten Angeboten (Modus aus, Profil, Sparte, ausgeblendet, extern) – dann bleibt
    die Sitzung unberührt und es wird nichts freigegeben."""
    try:
        return not _grund(session, angebot)
    except Exception as fehler:   # noqa: BLE001
        log.warning("Cloover-Vorprüfung fehlgeschlagen: %s", fehler)
        return False


def _rate_abrufen(assets: list[dict], basis: dict, user_email: str) -> dict:
    """Netzaufruf OHNE Datenbanksitzung: Werte für `cloover_json` (Erfolg) oder {"fehler": Grund}."""
    from app import cloover_api
    try:
        if not assets:
            raise cloover_api.ClooverFehler(f"Cloover: keine Anlage für Sparte {basis['sparte']} ableitbar")
        ergebnis = cloover_api.rate_berechnen(assets, basis["laufzeit"], basis["anzahlung"], user_email,
                                              brutto_cent=basis["endbetrag"])
    except cloover_api.ClooverFehler as fehler:
        return {"fehler": (getattr(fehler, "meldung", "") or str(fehler))[:300]}
    except Exception as fehler:   # noqa: BLE001 – kein Netzfehler darf ein PDF oder einen Versand blockieren
        log.warning("Cloover-Rate: unerwarteter Fehler %s: %s", type(fehler).__name__, fehler)
        return {"fehler": f"Cloover: {type(fehler).__name__}: {str(fehler)[:200]}"}
    rate_mit = ergebnis.get("rate_mit_cent")
    mit_foerderung = basis["sparte"] == "WP" and basis["foerderung"] > 0 and rate_mit is not None
    return {"rate_ohne_cent": int(ergebnis["rate_ohne_cent"]),
            "rate_mit_cent": int(rate_mit) if mit_foerderung else None,
            "endbetrag_cent": basis["endbetrag"], "foerderung_cent": basis["foerderung"],
            "ust_satz": basis["ust"], "laufzeit_jahre": basis["laufzeit"],
            "anzahlung_cent": basis["anzahlung"],
            "rate_laufzeit_jahre": basis["laufzeit"], "rate_anzahlung_cent": basis["anzahlung"],
            "stand": datetime.now().strftime(STAND_FORMAT),
            "quelle": (ergebnis.get("quelle") or "v2"), "fehler": None}


def _schreiben(angebot_id: int, werte: dict) -> dict:
    """Kurze Schreibsitzung (BEGIN IMMEDIATE) mit einer Wiederholung bei „database is locked“."""
    from sqlalchemy.exc import OperationalError

    from app import db
    from app.models import Angebot
    for versuch in range(2):
        try:
            with db.kurz() as s:
                angebot = s.get(Angebot, angebot_id)
                if angebot is None:
                    return {}
                return json_schreiben(angebot, **werte)
        except OperationalError as problem:
            if "locked" not in str(problem).lower() or versuch:
                raise
            time.sleep(0.7)
    return {}


def rate_aktualisieren(angebot_id: int, *, erzwingen: bool = False, benutzer_id: int | None = None) -> dict:
    """Rate neu ermitteln, wenn `stand` fehlt oder Endbetrag/Förderung/USt/Laufzeit/Anzahlung abweichen
    (lesen → Sitzung frei → cloover_api.rate_berechnen → kurze Schreibsitzung). Rückgabe = neuer Stand
    (bei Fehler bleibt die letzte Rate mit `stand`, `fehler` gesetzt). `benutzer_id` = vorbereitender
    Innendienstler (Cloover-Konto `benutzer.cloover_email`, sonst `cloover_standard_email` [ANNAHME]).
    Nicht relevante Angebote (Modus aus, Profil, Sparte, ausgeblendet, extern) werden unverändert
    zurückgegeben – ohne Netzaufruf, ohne Schreibzugriff."""
    from app import cloover_api, db
    from app.models import Angebot, Benutzer
    with db.kurz(schreibend=False) as s:
        angebot = s.get(Angebot, angebot_id)
        if angebot is None:
            return {}
        daten = json_lesen(angebot)
        if _grund(s, angebot):
            return daten
        basis = _basis_lesen(s, angebot, daten)
        if not erzwingen and not aenderung_noetig(daten, basis["endbetrag"], basis["foerderung"],
                                                  basis["ust"], basis["laufzeit"], basis["anzahlung"]):
            return daten
        assets = cloover_api.assets_fuer(s, angebot)
        benutzer = s.get(Benutzer, int(benutzer_id)) if benutzer_id else None
        user_email = cloover_api.user_email_fuer(s, benutzer)
    # Sitzung geschlossen – der Netzaufruf läuft ohne Datenbankverbindung (v27-Regel)
    werte = _rate_abrufen(assets, basis, user_email)
    return _schreiben(angebot_id, werte)


# --- Texte -----------------------------------------------------------------------------------------
def fussnote_text(session, daten: dict, mit_foerderung: bool) -> str:
    """Fußnote zur Rate (Textbaustein `cloover_fussnote`, Platzhalter {endbetrag} {laufzeit} {anzahlung}
    {foerderung} {stand}); ohne Förderung entfällt der Halbsatz „‚mit Förderung‘ …“. Leer ohne Rate."""
    if daten.get("rate_ohne_cent") is None:
        return ""
    basis_laufzeit, basis_anzahlung = rate_basis(daten)
    werte = {"endbetrag": eur(daten.get("endbetrag_cent") or 0),
             "laufzeit": basis_laufzeit if basis_laufzeit is not None else "",
             "anzahlung": eur(basis_anzahlung or 0),
             "stand": stand_datum(daten.get("stand")),
             "foerderung": eur(daten.get("foerderung_cent") or 0) if mit_foerderung else ""}
    try:
        from app import cloover_texte
        return cloover_texte.fussnote_rendern(session, endbetrag=werte["endbetrag"], laufzeit=werte["laufzeit"],
                                              anzahlung=werte["anzahlung"], stand=werte["stand"],
                                              foerderung=werte["foerderung"])
    except ImportError:   # Rückfall auf den Plan-Wortlaut, falls das B1-Modul fehlt
        text = FUSSNOTE_RUECKFALL
        if not mit_foerderung:
            text = text.replace(_FOERDERUNG_TEILSATZ, "")
        for name, wert in werte.items():
            text = text.replace("{" + name + "}", str(wert))
        return text


def datenschutz_text(session) -> str:
    try:
        from app import cloover_texte
        return cloover_texte.datenschutz_text(session)
    except ImportError:
        return DATENSCHUTZ_RUECKFALL


# --- QR-Code ---------------------------------------------------------------------------------------
def _qr(link: str):
    import qrcode
    # box_size 10 → SvgPathImage rechnet in ganzen Modulen (viewBox = Modulzahl), Größe setzt qr_svg selbst
    qr = qrcode.QRCode(error_correction=qrcode.constants.ERROR_CORRECT_M, box_size=10, border=QR_RAND)
    qr.add_data(link)
    qr.make(fit=True)
    return qr


def qr_matrix(link: str) -> list[list[bool]]:
    """Modulmatrix (inkl. Ruhezone) für den fpdf2-Rückfall – Rechtecke je dunklem Modul; [] ohne Link
    oder ohne Bibliothek."""
    if not (link or "").strip():
        return []
    try:
        return [list(zeile) for zeile in _qr(link.strip()).get_matrix()]
    except ImportError:
        log.warning("Bibliothek qrcode fehlt – kein QR-Code im PDF")
        return []


def qr_svg(link: str, mm: int = QR_MM) -> str:
    """QR-Code als Inline-SVG (22 × 22 mm, Fehlerkorrektur M) für die PDF-Vorlage; "" ohne Link."""
    if not (link or "").strip():
        return ""
    try:
        from qrcode.image.svg import SvgPathImage
        bild = _qr(link.strip()).make_image(image_factory=SvgPathImage)
        text = bild.to_string(encoding="unicode")
    except ImportError:
        log.warning("Bibliothek qrcode fehlt – kein QR-Code im PDF")
        return ""
    text = re.sub(r'\swidth="[^"]*"', f' width="{mm}mm"', text, count=1)
    text = re.sub(r'\sheight="[^"]*"', f' height="{mm}mm"', text, count=1)
    if "shape-rendering" not in text:
        text = text.replace("<svg ", '<svg shape-rendering="crispEdges" ', 1)
    return text


def link_kurz(link: str) -> str:
    """Link als Kurzform für die 7-pt-Zeile unter dem Knopf (ohne Schema/www., gekürzt)."""
    text = (link or "").strip()
    text = re.sub(r"^https?://", "", text, flags=re.IGNORECASE)
    text = re.sub(r"^www\.", "", text, flags=re.IGNORECASE).rstrip("/")
    if len(text) > LINK_KURZ_MAX:
        text = text[:LINK_KURZ_MAX - 1] + "…"
    return text


# --- PDF-Kontext / Editor / Mail ----------------------------------------------------------------------
def kontext_fuer_pdf(session, angebot) -> dict | None:
    """Teilbaum `auftrag.cloover` für pdf_kontext (rate_text, rate_mit_text, laufzeit, fussnote, checkout_link,
    link_kurz, qr_svg, datenschutz, hinweis_link, stand, …) oder None (nicht relevant). Nur lesend –
    die Rate selbst hat `rate_aktualisieren` vor der PDF-Erzeugung nachgezogen. Ohne Rate (noch nie
    berechnet, Fehler beim ersten Aufruf) bleiben die Texte leer → Karte „Monatsrate auf Anfrage“, kein
    Knopf, keine Fußnote."""
    ok, _grund_text = relevant(session, angebot)
    if not ok:
        return None
    daten = json_lesen(angebot)
    kontext = {"rate_text": "", "rate_mit_text": "", "laufzeit": laufzeit_fuer(session, angebot, daten),
               "fussnote": "", "checkout_link": "", "link_kurz": "", "qr_svg": "", "datenschutz": "",
               "hinweis_link": "", "stand": "", "anzahlung_text": "", "rate_ohne_cent": None,
               "rate_mit_cent": None, "mit_foerderung": False, "kombi_gesamtrate_text": ""}
    rate_ohne = daten.get("rate_ohne_cent")
    if rate_ohne is None:
        return kontext
    # Kombi-Versand (B3): Gesamtrate aller Angebote der Mail – nur zusätzlich zur eigenen Rate
    try:
        kombi = int(daten.get("kombi_gesamtrate_cent") or 0)
    except (TypeError, ValueError):
        kombi = 0
    if kombi > 0:
        kontext["kombi_gesamtrate_text"] = eur(kombi)
    rate_mit = daten.get("rate_mit_cent")
    mit_foerderung = (sparte_von(angebot) == "WP" and rate_mit is not None
                      and int(daten.get("foerderung_cent") or 0) > 0)
    basis_laufzeit, basis_anzahlung = rate_basis(daten)   # Karte 2/Fußnote nennen die Basis der Rate
    kontext.update(rate_text=eur(rate_ohne), rate_mit_text=eur(rate_mit) if mit_foerderung else "",
                   stand=stand_datum(daten.get("stand")), anzahlung_text=eur(basis_anzahlung or 0),
                   laufzeit=basis_laufzeit if basis_laufzeit is not None else kontext["laufzeit"],
                   rate_ohne_cent=int(rate_ohne), rate_mit_cent=int(rate_mit) if mit_foerderung else None,
                   mit_foerderung=mit_foerderung, fussnote=fussnote_text(session, daten, mit_foerderung))
    link = (daten.get("checkout_link") or "").strip()
    if link:
        kontext.update(checkout_link=link, link_kurz=link_kurz(link), qr_svg=qr_svg(link),
                       datenschutz=datenschutz_text(session))
    else:
        kontext["hinweis_link"] = HINWEIS_LINK
    return kontext


def editor_kontext(session, angebot, benutzer=None) -> dict:
    """Werte der Editor-Karte „Finanzierung (Cloover)“ (Innendienst/Admin) und der Lesesicht des
    Außendienstes (`meine_detail.html`, ohne Knöpfe). Nie EK/DB. `sichtbar` = Karte zeigen (relevant oder
    nur ausgeblendet – das Häkchen muss erreichbar bleiben); sonst Hinweiszeile mit `grund`."""
    from app import cloover_api
    daten = json_lesen(angebot)
    grund_ohne = _grund(session, angebot, mit_ausblendung=False)
    ist_ausgeblendet = ausgeblendet(angebot)
    sparte = sparte_von(angebot)
    kontext = {"sichtbar": not grund_ohne, "relevant": not grund_ohne and not ist_ausgeblendet,
               "grund": grund_ohne or (GRUND_AUSGEBLENDET if ist_ausgeblendet else ""),
               "ausgeblendet": ist_ausgeblendet, "sparte": sparte,
               "modus": cloover_api.modus(session), "daten": daten,
               "aenderbar": (not getattr(angebot, "extern", False)
                             and (getattr(angebot, "status", "") or "") in STATUS_AENDERBAR),
               "laufzeit": laufzeit_fuer(session, angebot, daten),
               "anzahlung_cent": anzahlung_fuer(session, angebot, daten),
               "anzahlung_text": "", "rate_ohne": "", "rate_mit": "", "mit_foerderung": False,
               "stand": daten.get("stand") or "", "quelle": daten.get("quelle") or "",
               "fehler": daten.get("fehler") or "", "veraltet": False, "hinweise": [],
               "endbetrag_text": "", "foerderung_text": "",
               "rate_laufzeit": "", "rate_anzahlung_text": "", "rate_endbetrag_text": "",
               "rate_foerderung_text": "",
               "checkout_link": daten.get("checkout_link") or "", "projekt_id": daten.get("projekt_id") or "",
               "status": daten.get("status") or ""}
    kontext["anzahlung_text"] = cloover_api.eur_text(kontext["anzahlung_cent"])
    if not kontext["sichtbar"]:
        return kontext
    basis = _basis_lesen(session, angebot, daten)
    rate_ohne = daten.get("rate_ohne_cent")
    rate_mit = daten.get("rate_mit_cent")
    kontext["mit_foerderung"] = sparte == "WP" and basis["foerderung"] > 0
    kontext["endbetrag_text"] = eur(basis["endbetrag"])
    kontext["foerderung_text"] = eur(basis["foerderung"]) if basis["foerderung"] > 0 else ""
    if rate_ohne is not None:
        kontext["rate_ohne"] = eur(rate_ohne)
        if rate_mit is not None and int(daten.get("foerderung_cent") or 0) > 0:
            kontext["rate_mit"] = eur(rate_mit)
        basis_laufzeit, basis_anzahlung = rate_basis(daten)
        kontext.update(rate_laufzeit=basis_laufzeit if basis_laufzeit is not None else "",
                       rate_anzahlung_text=cloover_api.eur_text(basis_anzahlung or 0),
                       rate_endbetrag_text=eur(daten.get("endbetrag_cent") or 0),
                       rate_foerderung_text=(eur(daten.get("foerderung_cent") or 0)
                                             if int(daten.get("foerderung_cent") or 0) > 0 else ""))
        kontext["veraltet"] = aenderung_noetig(daten, basis["endbetrag"], basis["foerderung"], basis["ust"],
                                               basis["laufzeit"], basis["anzahlung"])
    kontext["hinweise"] = voraussetzungen(session, angebot)
    return kontext


def _als_text(wert) -> str:
    if wert is None:
        return ""
    if isinstance(wert, str):
        return wert.strip()
    if isinstance(wert, dict):
        for key in ("url", "link", "href"):
            if isinstance(wert.get(key), str) and wert[key].strip():
                return wert[key].strip()
    try:
        return json.dumps(wert, ensure_ascii=False)
    except (TypeError, ValueError):
        return str(wert)


def mail_platzhalter(session, angebot) -> dict:
    """{cloover_rate} („ab 389,99 € pro Monat“ – Rate ohne Förderung – bzw. leer), {cloover_link}
    (persönlicher Abschluss-Link, Phase 194), {cloover_finanzierungsangebot} (`financial_offer` als Text)
    für Angebots-/Kombi-Vorlagen; bei nicht relevanten Angeboten alle leer."""
    leer = {"cloover_rate": "", "cloover_link": "", "cloover_finanzierungsangebot": ""}
    try:
        ok, _ = relevant(session, angebot)
    except Exception as fehler:   # noqa: BLE001 – Platzhalter dürfen den Versand nie blockieren
        log.warning("Cloover-Platzhalter nicht ermittelbar: %s", fehler)
        return leer
    if not ok:
        return leer
    daten = json_lesen(angebot)
    return {"cloover_rate": rate_satz(daten.get("rate_ohne_cent")),
            "cloover_link": (daten.get("checkout_link") or "").strip(),
            "cloover_finanzierungsangebot": _als_text(daten.get("financial_offer"))}


def kombi_platzhalter(session, angebote) -> dict:
    """Kombi-Vorlage [ANNAHME]: {cloover_rate} = eine Zeile je Tool-Angebot mit Rate („• WP-Angebot AN-C-…:
    ab 389,99 € pro Monat“), {cloover_link}/{cloover_finanzierungsangebot} = der (gemeinsame) Link des
    Kombi-Projekts, sobald eines der Angebote ihn trägt (Agent B3: EIN Projekt je Kombi-Mail)."""
    zeilen: list[str] = []
    link = finanzierungsangebot = ""
    for angebot in angebote or []:
        if getattr(angebot, "extern", False):
            continue
        werte = mail_platzhalter(session, angebot)
        if werte["cloover_rate"]:
            zeilen.append(f"• {sparte_von(angebot)}-Angebot {angebot.nummer}: {werte['cloover_rate']}")
        link = link or werte["cloover_link"]
        finanzierungsangebot = finanzierungsangebot or werte["cloover_finanzierungsangebot"]
    return {"cloover_rate": "\n".join(zeilen), "cloover_link": link,
            "cloover_finanzierungsangebot": finanzierungsangebot}
