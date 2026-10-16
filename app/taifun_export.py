# v35 (PLAN_LEAD_V6 Phase 183, Agent T): TAIFUN-Kundenexport – ein Lead wird als XML-Datei nach
# dem TAIFUN-Schema docs/taifun/ADRESSEN.xsd (Wurzel AdList, genau ein Ad je Datei, Namensraum
# urn:taifun-software.de:schema:TAIFUN) in den Import-Ordner geschrieben (Parameter
# taifun_import_ordner, Standard C:\Users\kdadmin\Desktop\LM Datenimport).
#
# Auslöser: NUR „Terminierung“ in der Kundenkartei (auch in der Testphase – nur der Export, keine
# Buchung, keine Mail). Eine Wiederholung nach Fehler, eine erneute Übergabe oder das bewusste
# „Trotzdem übergeben“ nach einem Dubletten-Hinweis gibt es ausschließlich in der Übergabeliste
# (/lead-management/taifun-uebergaben, Knopf je Zeile, ID/LM/Admin) – der Kartei-Knopf „An TAIFUN
# übergeben“ und das Feld „TAIFUN-Kundennummer“ sind mit dem Nachtrag 16.10.2026 (PLAN_LEAD_V6_1,
# v35-Nachtrag 3) entfallen. „Testdatei schreiben“ in den Lead-Einstellungen funktioniert immer
# (auch bei taifun_export_aktiv = aus).
#
# Regeln (v27/v33, gemeinsames Briefing): Datei-I/O nie innerhalb einer offenen Datenbanksitzung –
# exportieren() liest alle Daten, gibt die Verbindung frei (db.verbindung_freigeben), schreibt die
# Datei atomar (.tmp + Umbenennen, nie überschreiben) und schreibt erst danach die Übergabe-Zeile
# (taifun_uebergaben), die Vorgangsfelder (vorgaenge.taifun_export_*) und die Aktivität. Der
# Scheduler-Lauf „taifun-uebergaben“ (900 s) arbeitet im db.kurz()-Muster (lesen → Sitzung zu →
# Datei-I/O → kurze Schreibsitzung). Keine Glocke, keine Kundenmail (v29-Regel).
#
# Feldzuordnung Lead → Ad (wörtlich PLAN_LEAD_V6 Phase 183): KdUse true · Name3 „Vorname Nachname“
# (Firma bei Firmenkunden [ANNAHME]) · AnschriftStr/AnschriftHNr über die Adress-Parser-Logik
# (heizreport_api.strasse_trennen; unsichere Hausnummer → leer + Hinweis) · AnschriftPLZ/-Ort aus der
# abweichenden Rechnungsadresse (MFH, kunden.rechnung_* bzw. vorgang_objekte.rechnung_*), sonst
# Hauptobjekt/Kundenadresse · Anrede = Briefanrede (mail_vorlagen.briefanrede) · EMail nur bei
# email_status ≠ ungueltig · Telefon/Funk nach Mobilvorwahl (015x/016x/017x), national formatiert ·
# Kartei mehrzeilig (Übergabe, Vorgang, Kanal, Interessen, Objekte, Vertriebler, Termine, Quelle,
# Großkunde, Hinweise). Längen laut XSD werden gekürzt und als Hinweis vermerkt.

import logging
import os
import re
import time
from datetime import datetime, timedelta
from pathlib import Path

from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from app import config
from app.models import (Angebot, Benutzer, Kampagne, Kunde, LeadQuelle, TaifunUebergabe,
                        Vorgang, VorgangObjekt, VotTermin)

logger = logging.getLogger("angebotstool")

NAMENSRAUM = "urn:taifun-software.de:schema:TAIFUN"
PRAEFIX = "TAIFUN"
XSD_PFAD = config.PROJEKT_ORDNER / "docs" / "taifun" / "ADRESSEN.xsd"
KOPIE_ORDNER = config.DATA_ORDNER / "taifun_export"
LAUF_NAME = "taifun-uebergaben"
LAUF_INTERVALL_S = 900
AUFBEWAHRUNG_TAGE = 365           # Kopien unter data/taifun_export (12 Monate, Löschlauf)
BLOCK_GROESSE = 50
STANDARD_ORDNER = r"C:\Users\kdadmin\Desktop\LM Datenimport"
ENCODINGS = ("windows-1252", "utf-8")

# Parameter (Lead-Einstellungen → „TAIFUN-Übergabe“; Startwerte, Andreas 15.10.2026: Schalter AUS)
PARAMETER = {
    "taifun_export_aktiv": "aus",
    "taifun_import_ordner": STANDARD_ORDNER,
    "taifun_export_encoding": "windows-1252",
    "taifun_testdatei_ok": "",        # Häkchen „Testdatei in TAIFUN importiert“
    "taifun_encoding_ok": "",         # Häkchen „Encoding bestätigt“
    "taifun_ordner_geprueft": "",     # Ergebnis der letzten Ordnerprüfung („ok …“ | „fehler: …“)
}

# Elementreihenfolge und Längen laut XSD (Kartei ohne Begrenzung)
FELDER = ("KdUse", "Name3", "AnschriftStr", "AnschriftHNr", "AnschriftPLZ", "AnschriftOrt",
          "Anrede", "EMail", "Telefon", "Funk", "Kartei")
LAENGEN = {"Name3": 60, "AnschriftStr": 60, "AnschriftHNr": 20, "AnschriftPLZ": 10,
           "AnschriftOrt": 60, "Anrede": 200, "EMail": 80, "Telefon": 30, "Funk": 30}
FELD_NAMEN = {"Name3": "Name", "AnschriftStr": "Straße", "AnschriftHNr": "Hausnummer",
              "AnschriftPLZ": "PLZ", "AnschriftOrt": "Ort", "Anrede": "Briefanrede",
              "EMail": "E-Mail", "Telefon": "Telefon", "Funk": "Mobil"}

STATUS_GESCHRIEBEN = "geschrieben"
STATUS_ABGEHOLT = "abgeholt"
STATUS_FEHLER = "fehler"
STATUS_IMPORTIERT = "importiert"
# v35-Nachtrag 3 (16.10.2026): „übersprungen“ = die Terminierung hat den Export wegen einer Rückfrage
# (Dublette / bereits übergeben) NICHT ausgeführt – die Zeile erscheint in der Übergabeliste mit
# „Trotzdem übergeben“, weil der Kartei-Knopf entfallen ist [ANNAHME N6]; keine Datei, kein Fehler
STATUS_UEBERSPRUNGEN = "uebersprungen"
STATUS_NAMEN = {STATUS_GESCHRIEBEN: "geschrieben", STATUS_ABGEHOLT: "abgeholt",
                STATUS_FEHLER: "Fehler", STATUS_IMPORTIERT: "manuell importiert",
                STATUS_UEBERSPRUNGEN: "übersprungen (Rückfrage)"}
ERFOLG_STATUS = (STATUS_GESCHRIEBEN, STATUS_ABGEHOLT, STATUS_IMPORTIERT)
GRUND_TERMINIERUNG = "terminierung"
GRUND_MANUELL = "manuell"        # Wert bleibt (Bestand); Auslöser ist seit dem Nachtrag 3 die Übergabeliste
GRUND_TESTDATEI = "testdatei"
GRUND_NAMEN = {GRUND_TERMINIERUNG: "Terminierung", GRUND_MANUELL: "Übergabeliste (erneut)",
               GRUND_TESTDATEI: "Testdatei"}

LABEL_FEHLER = "TAIFUN-Übergabe fehlgeschlagen"
ERNEUT_LABEL = "Erneut übergeben"
TROTZDEM_LABEL = "Trotzdem übergeben"
DOPPELT_HINWEIS = "Doppelte Kunden in TAIFUN vermeiden."
NICHT_AKTIV_TEXT = "TAIFUN-Übergabe nicht aktiv (Parameter taifun_export_aktiv)"
KANAL_UNKLAR_TEXT = "Vertriebskanal klären – bei Kanal „?“ keine Übergabe an TAIFUN"
TESTPHASE_EXPORT_HINWEIS = "Testphase: nur Übergabe an TAIFUN, keine Buchung, keine Mail"
DIENSTKONTO_HINWEIS = ("Das Tool läuft als Dienst „FriondoAngebotstool“ unter dem Konto SYSTEM – "
                       "der Ordner muss für dieses Konto erreichbar und beschreibbar sein "
                       "(bei einem Ordner im Benutzerprofil kdadmin: Freigabe + UNC-Pfad, "
                       "siehe docs/taifun-kundenexport.md).")
KARTEI_TRENNER = "\n"   # [ANNAHME] Zeilenumbruch LF in der Karteikarte

# Demo-Lead der Testdatei (keine Kundendaten – Musterwerte)
TESTDATEI_FELDER = {
    "anrede": "Herr", "vorname": "Max", "nachname": "Mustermann",
    "strasse": "Musterstraße 1", "plz": "47051", "ort": "Duisburg",
    "email": "max.mustermann@example.com", "telefon": "0203 1234567",
    "funk": "0171 1234567", "kanal": "Website", "interessen": ["WP"],
}

# Deutsche Ortsnetzkennzahlen mit zwei bzw. drei Ziffern (ohne führende 0); alle übrigen
# Ortsnetze haben vier Ziffern [ANNAHME: Schreibweise „0203 3965710“ – TAIFUN-Muster nachreichen]
_VORWAHL_2 = {"30", "40", "69", "89"}
_VORWAHL_3 = {
    "201", "202", "203", "208", "209", "211", "212", "214", "221", "228", "231", "234", "241",
    "251", "261", "271", "281", "291", "331", "335", "340", "341", "345", "351", "355", "361",
    "365", "371", "375", "381", "385", "391", "395", "421", "431", "441", "461", "471", "481",
    "491", "511", "521", "531", "541", "551", "561", "571", "581", "591", "611", "621", "631",
    "641", "651", "661", "681", "711", "721", "731", "741", "751", "761", "771", "781", "791",
    "811", "821", "831", "841", "851", "861", "871", "881", "906", "911", "921", "931", "941",
    "951", "961", "971", "981", "991",
}
_MOBIL = ("15", "16", "17")
_ROH_TRENNER = re.compile(r"^\s*(?:\+49|0049|0)\s*(?:\(0\)\s*)?\(?(\d{2,5})\)?\s*[\s/\-]\s*\d")
_NUMMERN_TRENNER = re.compile(r"\s*(?:,|;| / | oder | und )\s*")


# --- Parameter ------------------------------------------------------------------------------

def _parameter(session: Session, name: str) -> str:
    from app import leadmanagement as kern
    return (kern.parameter_holen(session, name, PARAMETER.get(name, "")) or "").strip()


def aktiv(session: Session) -> bool:
    """Schalter taifun_export_aktiv (Standard aus, bis der Import-Weg mit dem TAIFUN-Betreuer
    geklärt ist)."""
    return _parameter(session, "taifun_export_aktiv").lower() in ("an", "ja", "1", "true", "ein")


def import_ordner(session: Session) -> str:
    return _parameter(session, "taifun_import_ordner") or STANDARD_ORDNER


def encoding(session: Session) -> str:
    wert = _parameter(session, "taifun_export_encoding").lower()
    return wert if wert in ENCODINGS else "windows-1252"


def haekchen(session: Session, name: str) -> bool:
    return _parameter(session, name).lower() in ("1", "ja", "an", "true")


# --- Hilfen: Name, Adresse, Telefon ------------------------------------------------------------

def name3(kunde: Kunde | None) -> str:
    """„Vorname Nachname“ (ohne Anrede; nur Nachname ohne Vorname); Firmenkunden/Großkunde mit
    Firma → Firmenname [ANNAHME: Feld kunden.firma]."""
    if kunde is None:
        return ""
    firma = (kunde.firma or "").strip()
    if firma:
        return firma
    return " ".join(t for t in ((kunde.vorname or "").strip(), (kunde.nachname or "").strip()) if t)


def strasse_hausnummer(strasse: str) -> tuple[str, str, str]:
    """(Straße, Hausnummer, Hinweis): Trennung mit der bestehenden Parser-Logik
    (heizreport_api.strasse_trennen – letzter Block Ziffer + Buchstabe/Zusatz, „12a“, „63-65“);
    ist die Hausnummer nicht sicher erkennbar, bleibt sie leer, das ganze Feld steht in der
    Straße und der Hinweis geht in die Karteikarte."""
    from app.heizreport_api import strasse_trennen
    text = " ".join((strasse or "").split())
    if not text:
        return "", "", ""
    str_, nr = strasse_trennen(text)
    if nr and str_:
        return str_, nr, ""
    return text, "", f"Hausnummer nicht sicher erkannt – Straßenfeld ungekürzt übernommen („{text}“)"


def ist_mobil(nummer: str) -> bool:
    """Deutsche Mobilvorwahl 015x/016x/017x bzw. +4915/16/17."""
    from app import leadmanagement as kern
    e164 = kern.telefon_normalisieren(nummer or "")
    if not e164.startswith("+49"):
        return False
    rest = e164[3:].lstrip("0")
    return rest[:2] in _MOBIL


def telefon_national(nummer: str) -> str:
    """National formatiert („0203 3965710“, Mobil „0171 1234567“); Rohtext mit erkennbarem Trenner
    nach der Vorwahl behält dessen Aufteilung; ausländische Nummern bleiben E.164 („+43 …“)."""
    from app import leadmanagement as kern
    roh = (nummer or "").strip()
    e164 = kern.telefon_normalisieren(roh)
    if not e164:
        return ""
    if not e164.startswith("+49"):
        return e164
    rest = e164[3:].lstrip("0")
    if not rest:
        return ""
    n = 0
    m = _ROH_TRENNER.match(roh)
    if m:
        vorwahl = m.group(1).lstrip("0")
        if vorwahl and rest.startswith(vorwahl) and len(rest) > len(vorwahl):
            n = len(vorwahl)
    if not n:
        if rest[:2] in _MOBIL:
            n = 3
        elif rest[:2] in _VORWAHL_2:
            n = 2
        elif rest[:3] in _VORWAHL_3:
            n = 3
        else:
            n = 4
    if len(rest) <= n:
        return "0" + rest
    return f"0{rest[:n]} {rest[n:]}"


def telefon_aufteilen(telefon: str) -> tuple[str, str]:
    """(Telefon, Funk) aus dem einen Nummernfeld des Leads: Mobilnummern → Funk, alle anderen →
    Telefon; enthält das Feld zwei Nummern („0203 …, 0171 …“), werden beide zugeordnet."""
    festnetz, mobil = [], []
    for teil in _NUMMERN_TRENNER.split((telefon or "").strip()):
        teil = teil.strip()
        if not re.search(r"\d{5,}", re.sub(r"\D", "", teil) or ""):
            continue
        (mobil if ist_mobil(teil) else festnetz).append(telefon_national(teil))
    return (festnetz[0] if festnetz else ""), (mobil[0] if mobil else "")


def kuerzen(wert: str, feld: str, hinweise: list[str]) -> str:
    """Längen laut Schema einhalten – längere Werte werden gekürzt, der Hinweis geht in die
    Karteikarte und die Aktivität."""
    wert = (wert or "").strip()
    grenze = LAENGEN.get(feld)
    if grenze and len(wert) > grenze:
        hinweise.append(f"{FELD_NAMEN.get(feld, feld)} auf {grenze} Zeichen gekürzt "
                        f"(ursprünglich „{wert}“)")
        return wert[:grenze].rstrip()
    return wert


def vorgangsnummer(vorgang: Vorgang | int) -> str:
    """„V<ID>“ – die Kundenkartei und die Boards zeigen Vorgänge so [ANNAHME: keine eigene Nummer]."""
    nummer = vorgang if isinstance(vorgang, int) else vorgang.id
    return f"V{nummer}"


def _sicher(text: str) -> str:
    text = (text or "").replace("ä", "ae").replace("ö", "oe").replace("ü", "ue").replace("ß", "ss")
    return re.sub(r"[^A-Za-z0-9_-]+", "", text).upper() or "X"


def dateiname(vorgang: Vorgang | int | None, jetzt: datetime | None = None, test: bool = False,
              laufnummer: int = 0) -> str:
    """LM_<Vorgangsnummer>_<JJJJMMTT-HHMMSS>.xml (nur A–Z, 0–9, Unterstrich, Bindestrich);
    Testdatei LM_TEST_<Zeit>.xml; laufnummer ≥ 2 hängt „-2“, „-3“ … an (zweite Übergabe
    in derselben Sekunde – eine vorhandene Datei wird nie überschrieben)."""
    jetzt = jetzt or datetime.now()
    kennung = "TEST" if test or vorgang is None else _sicher(vorgangsnummer(vorgang))
    zusatz = f"-{laufnummer}" if laufnummer >= 2 else ""
    return f"LM_{kennung}_{jetzt.strftime('%Y%m%d-%H%M%S')}{zusatz}.xml"


def freier_dateiname(ordner: str, vorgang: Vorgang | int | None, jetzt: datetime | None = None,
                     test: bool = False) -> str:
    """Erster Dateiname, der weder im Zielordner noch unter den Protokoll-Kopien existiert."""
    for lauf in range(1, 100):
        name = dateiname(vorgang, jetzt, test, laufnummer=lauf)
        try:
            belegt = (Path(ordner) / name).exists() or (KOPIE_ORDNER / name).exists()
        except OSError:
            belegt = False
        if not belegt:
            return name
    return dateiname(vorgang, jetzt, test, laufnummer=100)


# --- Daten des Vorgangs → Felder ------------------------------------------------------------

def kanal_unklar(session: Session, vorgang: Vorgang | None, kunde: Kunde | None = None) -> bool:
    """Kanal „?“ = Vertriebskanal unklar (Phase 184, Vertrag K: lead_kanaele.kanal_unklar);
    Rückfall: Kanalwert „?“ am Kunden."""
    try:
        from app import lead_kanaele
        fn = getattr(lead_kanaele, "kanal_unklar", None)
        if callable(fn):
            try:
                return bool(fn(vorgang))
            except TypeError:
                return bool(fn(session, vorgang))
    except ImportError:
        pass
    except Exception:   # noqa: BLE001 – der Export darf an K's Modul nie scheitern
        pass
    if kunde is None and vorgang is not None:
        kunde = session.get(Kunde, vorgang.kunde_id)
    return bool(kunde is not None and (kunde.vertriebskanal or "").strip() == "?")


def _objektart_namen(session: Session) -> dict:
    try:
        from app import lead_v2
        return {code: bez for code, bez, _p in lead_v2.objektarten(session)}
    except Exception:   # noqa: BLE001
        return {}


def _rechnungsadresse(session: Session, vorgang: Vorgang, kunde: Kunde) -> dict | None:
    """Abweichende Rechnungsadresse (MFH, v20/v31): Hauptobjekt → kunden.rechnung_* (nur bei
    „Rechnungsadresse identisch? = Nein“), Objekt 2 ff. → vorgang_objekte.rechnung_*."""
    from app import anschriften
    from app import objekte as objekte_modul
    try:
        from app import lead_kartei
        abweichend = lead_kartei.rechnung_abweichend(session, vorgang, kunde)
    except Exception:   # noqa: BLE001
        abweichend = bool((kunde.rechnung_strasse or "").strip() and (kunde.rechnung_ort or "").strip())
    if abweichend and (kunde.rechnung_strasse or "").strip() and (kunde.rechnung_ort or "").strip():
        return {"name": (kunde.rechnung_name or "").strip(), "strasse": (kunde.rechnung_strasse or "").strip(),
                "plz": (kunde.rechnung_plz or "").strip(), "ort": (kunde.rechnung_ort or "").strip(),
                "quelle": "Kunden-Standard (MFH)"}
    for objekt in objekte_modul.objekte_fuer(session, vorgang.id):
        if objekt.reihenfolge == 1:
            continue
        werte = anschriften.objekt_rechnung(objekt, kunde)
        if werte:
            werte["quelle"] = objekt.bezeichnung or "Objekt"
            return werte
    return None


def daten_fuer_vorgang(session: Session, vorgang_id: int, benutzer=None, grund: str = GRUND_MANUELL,
                       jetzt: datetime | None = None) -> tuple[dict, list[str]]:
    """Felder des Ad-Eintrags für einen Vorgang + Hinweise (Kürzungen, Parser, E-Mail). Nur Lesen –
    der Aufrufer gibt die Sitzung vor dem Schreiben der Datei frei."""
    from app import leadmanagement as kern
    from app import objekte as objekte_modul
    from app import sparten as sparten_modul
    from app.mail_vorlagen import briefanrede
    jetzt = jetzt or datetime.now()
    vorgang = session.get(Vorgang, int(vorgang_id))
    if vorgang is None:
        raise ValueError(f"Vorgang {vorgang_id} nicht gefunden")
    kunde = session.get(Kunde, vorgang.kunde_id)
    if kunde is None:
        raise ValueError(f"Vorgang {vorgangsnummer(vorgang)}: Kunde fehlt")
    hinweise: list[str] = []
    felder: dict = {"KdUse": "true"}
    name = name3(kunde)
    if not name:
        raise ValueError("Name fehlt (Vorname/Nachname oder Firma)")
    felder["Name3"] = kuerzen(name, "Name3", hinweise)
    # Adresse: abweichende Rechnungsadresse (MFH) hat Vorrang, sonst Hauptobjekt/Kundenadresse
    rechnung = _rechnungsadresse(session, vorgang, kunde)
    objekte = objekte_modul.objekte_fuer(session, vorgang.id)
    if rechnung is not None:
        adresse = rechnung
        hinweise.append(f"Adresse = Rechnungsadresse ({rechnung['quelle']}); Objektadresse(n) siehe Objekte")
    else:
        ort = objekte_modul.ausfuehrungsort(session, vorgang=vorgang, kunde=kunde)
        adresse = {"strasse": ort.get("strasse") or kunde.strasse or "",
                   "plz": ort.get("plz") or kunde.plz or "", "ort": ort.get("ort") or kunde.ort or ""}
    str_, nr, hinweis = strasse_hausnummer(adresse.get("strasse") or "")
    if hinweis:
        hinweise.append(hinweis)
    felder["AnschriftStr"] = kuerzen(str_, "AnschriftStr", hinweise)
    felder["AnschriftHNr"] = kuerzen(nr, "AnschriftHNr", hinweise)
    felder["AnschriftPLZ"] = kuerzen(adresse.get("plz") or "", "AnschriftPLZ", hinweise)
    felder["AnschriftOrt"] = kuerzen(adresse.get("ort") or "", "AnschriftOrt", hinweise)
    felder["Anrede"] = kuerzen(briefanrede(kunde), "Anrede", hinweise)
    if (vorgang.email_status or "") == "ungueltig":
        felder["EMail"] = ""
        if (kunde.email or "").strip():
            hinweise.append(f"E-Mail {kunde.email.strip()} ist als unzustellbar gemeldet – nicht übergeben")
    else:
        felder["EMail"] = kuerzen((kunde.email or "").strip(), "EMail", hinweise)
    telefon, funk = telefon_aufteilen(kunde.telefon or "")
    felder["Telefon"] = kuerzen(telefon, "Telefon", hinweise)
    felder["Funk"] = kuerzen(funk, "Funk", hinweise)
    # Karteikarte (Plan-Reihenfolge)
    zeilen = []
    wer = ""
    if benutzer is not None:
        wer = getattr(benutzer, "name", "") or ""
    zeilen.append(f"Übergabe aus dem Friondo-Tool am {jetzt.strftime('%d.%m.%Y %H:%M')}"
                  + (f" durch {wer}" if wer else ""))
    zeilen.append(f"Lead/Vorgang: {vorgangsnummer(vorgang)}")
    kanal = kern.kanal_anzeige(kunde.vertriebskanal)
    if kanal:
        zeilen.append(f"Vertriebskanal: {kanal}")
    try:
        langnamen = sparten_modul.langnamen_laden(kern.parameter_holen(session, "sparten_langnamen", ""))
    except Exception:   # noqa: BLE001
        langnamen = None
    interessen = objekte_modul.vorgang_interessen(session, vorgang.id) or kunde.interessen
    if interessen:
        zeilen.append("Interessen: " + sparten_modul.sparten_text(interessen, langnamen=langnamen))
    objektarten = _objektart_namen(session)
    mehrere = len(objekte) > 1
    for objekt in objekte:
        ort = objekte_modul.ausfuehrungsort(session, objekt_id=objekt.id, vorgang=vorgang, kunde=kunde)
        teile = []
        if objekt.objektart:
            art = objektarten.get(objekt.objektart, objekt.objektart)
            if (objekt.objektart or "").upper() == "MFH" and objekt.parteien:
                art += f" ({objekt.parteien} Parteien)"
            teile.append(art)
        if ort.get("einzeilig"):
            teile.append(ort["einzeilig"])
        bez = objekt.bezeichnung or "Objekt"
        zeilen.append(f"{bez if mehrere else 'Objekt'}: " + (", ".join(teile) if teile else "ohne Adresse"))
    if not objekte and (kunde.strasse or kunde.ort):
        zeilen.append("Objekt: " + ", ".join(t for t in (kunde.strasse, f"{kunde.plz} {kunde.ort}".strip()) if t))
    termine = (session.query(VotTermin)
               .filter(VotTermin.vorgang_id == vorgang.id, VotTermin.typ == "vot",
                       VotTermin.status.in_(("vorgemerkt", "geplant", "bestaetigt")))
               .order_by(VotTermin.beginn, VotTermin.id).all())
    vertriebler = session.get(Benutzer, vorgang.ad_id) if vorgang.ad_id else None
    if vertriebler is None and termine and termine[0].ad_id:
        vertriebler = session.get(Benutzer, termine[0].ad_id)
    if vertriebler is not None:
        zeilen.append(f"Vertriebler: {vertriebler.name}")
    objekt_namen = {o.id: (o.bezeichnung or "Objekt") for o in objekte}
    for termin in termine:
        wann = termin.beginn.strftime("%d.%m.%Y %H:%M") if termin.beginn else "ohne Uhrzeit"
        zusatz = f" ({objekt_namen[termin.objekt_id]})" if mehrere and termin.objekt_id in objekt_namen else ""
        if termin.status == "vorgemerkt":
            zeilen.append(f"Vor-Ort-Termin: vorgemerkt: {wann}{zusatz}")
        else:
            zeilen.append(f"Vor-Ort-Termin: {wann}{zusatz}")
    quelle = session.get(LeadQuelle, vorgang.quelle_id) if vorgang.quelle_id else None
    kampagne = session.get(Kampagne, vorgang.kampagne_id) if vorgang.kampagne_id else None
    quelle_text = " / ".join(t for t in ((quelle.name or quelle.key) if quelle else "",
                                          kampagne.name if kampagne else "") if t)
    if quelle_text:
        zeilen.append(f"Quelle: {quelle_text}")
    if getattr(kunde, "grosskunde", False):
        zeilen.append("Großkunde: ja")
    for h in hinweise:
        zeilen.append(f"Hinweis: {h}")
    felder["Kartei"] = KARTEI_TRENNER.join(zeilen)
    return felder, hinweise


def testdatei_felder(jetzt: datetime | None = None, benutzer=None) -> dict:
    """Felder des Demo-Leads „Max Mustermann“ (Testdatei für den Import-Test in TAIFUN)."""
    from app import sparten as sparten_modul
    jetzt = jetzt or datetime.now()
    d = TESTDATEI_FELDER
    str_, nr, _h = strasse_hausnummer(d["strasse"])
    wer = getattr(benutzer, "name", "") if benutzer is not None else ""
    zeilen = [f"Übergabe aus dem Friondo-Tool am {jetzt.strftime('%d.%m.%Y %H:%M')}"
              + (f" durch {wer}" if wer else "") + " – TESTDATEI",
              "Lead/Vorgang: TEST", f"Vertriebskanal: {d['kanal']}",
              "Interessen: " + sparten_modul.sparten_text(d["interessen"]),
              f"Objekt: Einfamilienhaus, {d['strasse']}, {d['plz']} {d['ort']}",
              "Vertriebler: Test-Vertriebler",
              f"Vor-Ort-Termin: vorgemerkt: {(jetzt + timedelta(days=7)).strftime('%d.%m.%Y')} 10:00",
              "Quelle: Testdatei (Lead-Einstellungen)",
              "Hinweis: Testdatei – kein echter Kunde, nach dem Import-Test in TAIFUN löschen"]
    return {"KdUse": "true", "Name3": f"{d['vorname']} {d['nachname']}", "AnschriftStr": str_,
            "AnschriftHNr": nr, "AnschriftPLZ": d["plz"], "AnschriftOrt": d["ort"],
            "Anrede": f"Sehr geehrter Herr {d['nachname']},", "EMail": d["email"],
            "Telefon": telefon_national(d["telefon"]), "Funk": telefon_national(d["funk"]),
            "Kartei": KARTEI_TRENNER.join(zeilen)}


# --- XML ------------------------------------------------------------------------------------

def xml_aus_feldern(felder: dict, encoding_name: str = "windows-1252") -> bytes:
    """Datei-Inhalt: XML-Deklaration mit dem Encoding (Umlaute/ß als Zeichen), Wurzel
    TAIFUN:AdList, genau ein TAIFUN:Ad, Elemente in Schema-Reihenfolge, leere Felder weggelassen."""
    from lxml import etree
    encoding_name = encoding_name if encoding_name in ENCODINGS else "windows-1252"
    root = etree.Element(f"{{{NAMENSRAUM}}}AdList", nsmap={PRAEFIX: NAMENSRAUM})
    ad = etree.SubElement(root, f"{{{NAMENSRAUM}}}Ad")
    for name in FELDER:
        wert = felder.get(name)
        if wert is None or str(wert) == "":
            continue
        element = etree.SubElement(ad, f"{{{NAMENSRAUM}}}{name}")
        element.text = str(wert)
    rumpf = etree.tostring(root, encoding=encoding_name, pretty_print=True, xml_declaration=False)
    return (f'<?xml version="1.0" encoding="{encoding_name}"?>\n').encode("ascii") + rumpf


_SCHEMA_CACHE: dict = {}


def schema():
    """lxml-Schema aus docs/taifun/ADRESSEN.xsd (immer die Datei dort – das Original von TAIFUN
    kann sie ohne Codeänderung ersetzen); je Dateistand einmal geladen."""
    from lxml import etree
    pfad = Path(XSD_PFAD)
    if not pfad.exists():
        raise FileNotFoundError(f"Schema fehlt: {pfad}")
    stand = pfad.stat().st_mtime_ns
    if _SCHEMA_CACHE.get("stand") != stand:
        _SCHEMA_CACHE["schema"] = etree.XMLSchema(etree.parse(str(pfad)))
        _SCHEMA_CACHE["stand"] = stand
    return _SCHEMA_CACHE["schema"]


def validieren(xml_bytes: bytes) -> list[str]:
    """Validierung gegen die XSD – leere Liste = gültig, sonst die Fehlertexte."""
    from lxml import etree
    try:
        xsd = schema()
    except Exception as problem:   # noqa: BLE001
        return [f"Schema nicht ladbar: {problem}"]
    try:
        baum = etree.fromstring(xml_bytes)
    except etree.XMLSyntaxError as problem:
        return [f"XML nicht lesbar: {problem}"]
    if xsd.validate(baum):
        return []
    return [f"Zeile {e.line}: {e.message}" for e in xsd.error_log]


def xml_fuer_vorgang(session: Session, vorgang_id: int, benutzer=None, grund: str = GRUND_MANUELL,
                     jetzt: datetime | None = None) -> tuple[bytes, list[str]]:
    """(XML-Bytes, Hinweise) für einen Vorgang – Encoding laut Parameter."""
    felder, hinweise = daten_fuer_vorgang(session, vorgang_id, benutzer, grund, jetzt)
    return xml_aus_feldern(felder, encoding(session)), hinweise


# --- Datei-I/O (immer außerhalb der Datenbanksitzung) ----------------------------------------

def _fehler_text(problem: Exception, ordner: str) -> str:
    if isinstance(problem, FileNotFoundError):
        return f"Ordner nicht gefunden: {ordner}. {DIENSTKONTO_HINWEIS}"
    if isinstance(problem, PermissionError):
        return f"Keine Schreibrechte im Ordner {ordner}. {DIENSTKONTO_HINWEIS}"
    if isinstance(problem, FileExistsError):
        return f"Datei existiert bereits im Ordner {ordner} – nicht überschrieben."
    return f"{type(problem).__name__}: {problem} (Ordner {ordner}). {DIENSTKONTO_HINWEIS}"


def datei_schreiben(ordner: str, name: str, inhalt: bytes) -> Path:
    """Atomar: temporäre Datei <name>.tmp im Zielordner, dann Umbenennen; eine vorhandene Datei
    wird nie überschrieben (FileExistsError). Wirft OSError bei fehlendem Ordner/Rechten."""
    ziel_ordner = Path(ordner)
    if not ziel_ordner.is_dir():
        raise FileNotFoundError(str(ziel_ordner))
    ziel = ziel_ordner / name
    if ziel.exists():
        raise FileExistsError(str(ziel))
    tmp = ziel_ordner / f"{name}.tmp"
    with open(tmp, "wb") as f:
        f.write(inhalt)
        f.flush()
        try:
            os.fsync(f.fileno())
        except OSError:
            pass
    try:
        if ziel.exists():
            raise FileExistsError(str(ziel))
        os.rename(tmp, ziel)   # Windows: schlägt fehl, wenn das Ziel inzwischen existiert
    except BaseException:
        try:
            tmp.unlink()
        except OSError:
            pass
        raise
    return ziel


def kopie_ablegen(name: str, inhalt: bytes) -> str:
    """Protokoll-Kopie unter data/taifun_export/<Datei> (12 Monate, Löschlauf); leer bei Fehler."""
    try:
        KOPIE_ORDNER.mkdir(parents=True, exist_ok=True)
        ziel = KOPIE_ORDNER / name
        if not ziel.exists():
            ziel.write_bytes(inhalt)
        return str(ziel)
    except OSError as problem:
        logger.warning("TAIFUN-Export: Kopie %s nicht abgelegt: %s", name, problem)
        return ""


def kopie_pfad(name: str) -> Path | None:
    """Pfad der Protokoll-Kopie (nur Dateinamen aus dem Export, kein Pfadanteil)."""
    name = (name or "").strip()
    if not name or "/" in name or "\\" in name or ".." in name:
        return None
    pfad = KOPIE_ORDNER / name
    return pfad if pfad.is_file() else None


def ordner_pruefen(pfad: str) -> tuple[bool, str]:
    """Existiert der Ordner und ist er beschreibbar? (Testdatei LM_PRUEF_<Zeit>.tmp schreiben
    und entfernen.) Die Meldung nennt bei Fehlern das Dienstkonto SYSTEM des Dienstes
    FriondoAngebotstool."""
    pfad = (pfad or "").strip()
    if not pfad:
        return False, "Kein Ordner eingetragen."
    ordner = Path(pfad)
    if not ordner.exists():
        return False, f"Ordner nicht gefunden: {pfad}. {DIENSTKONTO_HINWEIS}"
    if not ordner.is_dir():
        return False, f"{pfad} ist kein Ordner."
    probe = ordner / f"LM_PRUEF_{datetime.now().strftime('%Y%m%d-%H%M%S-%f')}.tmp"
    try:
        with open(probe, "wb") as f:
            f.write(b"friondo")
        probe.unlink()
    except PermissionError:
        return False, f"Keine Schreibrechte im Ordner {pfad}. {DIENSTKONTO_HINWEIS}"
    except OSError as problem:
        return False, f"Ordner nicht beschreibbar ({type(problem).__name__}: {problem}). {DIENSTKONTO_HINWEIS}"
    return True, f"Ordner erreichbar und beschreibbar: {pfad}"


# --- Übergabe ---------------------------------------------------------------------------------

def _commit_mit_wiederholung(session: Session, wiederholungen: int = 1) -> None:
    """v27-Muster: bei „database is locked“ Rollback, kurz warten, einmal wiederholen."""
    for versuch in range(wiederholungen + 1):
        try:
            session.commit()
            return
        except OperationalError as problem:
            session.rollback()
            if "locked" not in str(problem).lower() or versuch >= wiederholungen:
                raise
            time.sleep(0.7)


def _aktivitaet(session: Session, vorgang_id: int, text: str, benutzer_id=None) -> None:
    from app import leadmanagement as kern
    benutzer = session.get(Benutzer, benutzer_id) if benutzer_id else None
    kern.aktivitaet(session, vorgang_id, "hinweis", text, benutzer=benutzer)


def dubletten_belege(session: Session, kunden_ids) -> dict:
    """{kunde_id: Beleg-Text} für mehrere Kunden in zwei Abfragen (Übergabeliste): externer
    TAIFUN-Eintrag mit Nummer (v7) und Bestandsimport (v18, angebote.bestand). Die manuelle
    TAIFUN-Kundennummer zählt seit dem Nachtrag 16.10.2026 nicht mehr (Feld entfallen)."""
    ids = sorted({int(k) for k in kunden_ids if k})
    if not ids:
        return {}
    extern: dict[int, str] = {}
    for a in (session.query(Angebot)
              .filter(Angebot.kunde_id.in_(ids), Angebot.extern.is_(True), Angebot.taifun_nummer != "")
              .order_by(Angebot.id)):
        extern[a.kunde_id] = a.taifun_nummer   # jüngster Eintrag gewinnt (aufsteigend überschrieben)
    bestand = {a.kunde_id for a in session.query(Angebot.kunde_id)
               .filter(Angebot.kunde_id.in_(ids), Angebot.bestand.is_(True))}
    belege: dict[int, str] = {}
    for kid in ids:
        teile = []
        if kid in extern:
            teile.append(f"TAIFUN-Angebot {extern[kid]}")
        if kid in bestand:
            teile.append("Bestandsimport")
        if teile:
            belege[kid] = "; ".join(teile)
    return belege


def dubletten_hinweis(session: Session, vorgang: Vorgang, kunde: Kunde | None) -> str:
    """Beleg, dass der Kunde vermutlich schon in TAIFUN angelegt ist: externer TAIFUN-Eintrag mit
    Nummer (v7) oder Bestandsimport (v18, angebote.bestand) – NICHT mehr kunden.taifun_kundennr
    (Nachtrag 16.10.2026)."""
    if kunde is None:
        return ""
    return dubletten_belege(session, [kunde.id]).get(kunde.id, "")


def bereits_uebergeben_text(vorgang: Vorgang) -> str:
    if (vorgang.taifun_export_status or "") in ERFOLG_STATUS and vorgang.taifun_export_am:
        return (f"zuletzt übergeben am {vorgang.taifun_export_am.strftime('%d.%m.%Y %H:%M')}"
                + (f" ({vorgang.taifun_export_datei})" if vorgang.taifun_export_datei else ""))
    return ""


def rueckfrage_text(session: Session, vorgang: Vorgang, kunde: Kunde | None) -> str:
    """Sicherheitsabfrage vor dem Export: Dubletten-Hinweis und/oder „bereits übergeben“ – leer,
    wenn keine Rückfrage nötig ist."""
    teile = []
    beleg = dubletten_hinweis(session, vorgang, kunde)
    if beleg:
        teile.append(f"Kunde ist vermutlich schon in TAIFUN angelegt ({beleg}). Trotzdem übergeben?")
    bereits = bereits_uebergeben_text(vorgang)
    if bereits:
        teile.append(f"Dieser Lead wurde bereits an TAIFUN übergeben ({bereits}) – doppelte Kunden in "
                     "TAIFUN vermeiden. Erneut übergeben?")
    return " ".join(teile)


def erneut_text(vorgang: Vorgang | None, kunde: Kunde | None = None, beleg: str = "",
                uebergabe: TaifunUebergabe | None = None) -> str:
    """Rückfrage des Knopfs „Erneut übergeben“ / „Trotzdem übergeben“ in der Übergabeliste (Plan-
    Wortlaut: „Letzte Übergabe am TT.MM.JJJJ HH:MM – trotzdem erneut übergeben? Doppelte Kunden in
    TAIFUN vermeiden.“); vor einer ersten erfolgreichen Übergabe der Dubletten-Beleg bzw. der
    Grund der übersprungenen Übergabe."""
    teile = []
    if beleg:
        teile.append(f"Kunde ist vermutlich schon in TAIFUN angelegt ({beleg}).")
    am = getattr(vorgang, "taifun_export_am", None) if vorgang is not None else None
    if am:
        teile.append(f"Letzte Übergabe am {am.strftime('%d.%m.%Y %H:%M')} – trotzdem erneut übergeben? "
                     + DOPPELT_HINWEIS)
    elif uebergabe is not None and uebergabe.status == STATUS_UEBERSPRUNGEN:
        if not beleg and (uebergabe.fehler_text or "").strip():
            teile.append((uebergabe.fehler_text or "").strip())
        teile.append("Jetzt trotzdem an TAIFUN übergeben?")
    else:
        teile.append("TAIFUN-Übergabe erneut versuchen? " + DOPPELT_HINWEIS)
    return " ".join(teile)


def pruefung(session: Session, vorgang: Vorgang, kunde: Kunde | None = None) -> dict:
    """Zustand vor einer Übergabe: aktiv, kanal_unklar, dublette, bereits, rueckfrage."""
    if kunde is None:
        kunde = session.get(Kunde, vorgang.kunde_id)
    return {"aktiv": aktiv(session), "kanal_unklar": kanal_unklar(session, vorgang, kunde),
            "dublette": dubletten_hinweis(session, vorgang, kunde),
            "bereits": bereits_uebergeben_text(vorgang),
            "rueckfrage": rueckfrage_text(session, vorgang, kunde)}


def _fehler_verbuchen(session: Session, vorgang: Vorgang, benutzer_id, grund: str, text: str,
                      datei: str = "", pfad: str = "") -> TaifunUebergabe:
    vorgang.taifun_export_status = STATUS_FEHLER
    vorgang.taifun_export_grund = (text or "")[:2000]
    uebergabe = TaifunUebergabe(vorgang_id=vorgang.id, datei=datei, pfad=pfad, benutzer_id=benutzer_id,
                                grund=grund, status=STATUS_FEHLER, fehler_text=(text or "")[:2000])
    session.add(uebergabe)
    _aktivitaet(session, vorgang.id, f"{LABEL_FEHLER}: {text}", benutzer_id)
    session.flush()
    return uebergabe


def _uebersprungen_verbuchen(session: Session, vorgang: Vorgang, benutzer_id, text: str,
                             jetzt: datetime | None = None) -> TaifunUebergabe | None:
    """v35-Nachtrag 3: die Terminierung hat den Export wegen einer Rückfrage ausgelassen – Zeile mit
    Status „übersprungen (Rückfrage)“ für die Übergabeliste („Trotzdem übergeben“), ohne Datei, ohne
    Vorgangs-Status (kein rotes Label). Direkt aufeinanderfolgende gleiche Zeilen werden nicht
    verdoppelt (Testphase: mehrfacher Klick auf „Terminierung“)."""
    letzte = (session.query(TaifunUebergabe).filter(TaifunUebergabe.vorgang_id == vorgang.id)
              .order_by(TaifunUebergabe.id.desc()).first())
    if (letzte is not None and letzte.status == STATUS_UEBERSPRUNGEN
            and (letzte.fehler_text or "") == (text or "")[:2000]):
        return letzte
    uebergabe = TaifunUebergabe(vorgang_id=vorgang.id, datei="", pfad="", benutzer_id=benutzer_id,
                                grund=GRUND_TERMINIERUNG, status=STATUS_UEBERSPRUNGEN,
                                fehler_text=(text or "")[:2000], geschrieben_am=jetzt or datetime.now())
    session.add(uebergabe)
    session.flush()
    return uebergabe


def exportieren(session: Session, vorgang_id: int, benutzer_id=None, grund: str = GRUND_MANUELL,
                jetzt: datetime | None = None) -> tuple[bool, str, TaifunUebergabe | None]:
    """Lead als XML-Datei in den Import-Ordner schreiben. Ablauf (v27-Regel): Daten lesen →
    XML bauen und gegen die XSD validieren → Sitzung freigeben → Datei atomar schreiben + Kopie →
    Vorgangsfelder, Übergabe-Zeile und Aktivität schreiben und committen. Fehler (Validierung,
    Ordner fehlt, keine Rechte) → vorgaenge.taifun_export_status = fehler mit Grund, Übergabe-Zeile
    mit Status fehler, Aktivität; es wird nichts geschrieben. Rückfragen (Dubletten, bereits
    übergeben) prüft der Aufrufer vorher (rueckfrage_text). Keine Glocke, keine Kundenmail."""
    from app.db import verbindung_freigeben
    jetzt = jetzt or datetime.now()
    vorgang = session.get(Vorgang, int(vorgang_id))
    if vorgang is None:
        return False, "Vorgang nicht gefunden.", None
    ordner = import_ordner(session)
    benutzer = session.get(Benutzer, benutzer_id) if benutzer_id else None
    try:
        felder, hinweise = daten_fuer_vorgang(session, vorgang.id, benutzer, grund, jetzt)
        inhalt = xml_aus_feldern(felder, encoding(session))
    except ValueError as problem:
        uebergabe = _fehler_verbuchen(session, vorgang, benutzer_id, grund, f"Daten unvollständig: {problem}")
        _commit_mit_wiederholung(session)
        return False, f"{LABEL_FEHLER}: {problem}", uebergabe
    fehler = validieren(inhalt)
    if fehler:
        text = "Validierung gegen ADRESSEN.xsd fehlgeschlagen: " + "; ".join(fehler)[:1500]
        uebergabe = _fehler_verbuchen(session, vorgang, benutzer_id, grund, text)
        _commit_mit_wiederholung(session)
        return False, f"{LABEL_FEHLER}: {text}", uebergabe
    # Datei-I/O außerhalb der Datenbanksitzung (Hotfix 06.10.2026 / v27-Regel)
    verbindung_freigeben(session)
    name = freier_dateiname(ordner, vorgang, jetzt)
    try:
        ziel = datei_schreiben(ordner, name, inhalt)
    except OSError as problem:
        text = _fehler_text(problem, ordner)
        vorgang = session.get(Vorgang, int(vorgang_id))
        uebergabe = _fehler_verbuchen(session, vorgang, benutzer_id, grund, text, datei=name,
                                      pfad=str(Path(ordner) / name))
        _commit_mit_wiederholung(session)
        return False, f"{LABEL_FEHLER}: {text}", uebergabe
    kopie_ablegen(name, inhalt)
    vorgang = session.get(Vorgang, int(vorgang_id))
    vorgang.taifun_export_am = jetzt
    vorgang.taifun_export_von = benutzer_id
    vorgang.taifun_export_datei = name
    vorgang.taifun_export_status = STATUS_GESCHRIEBEN
    vorgang.taifun_export_grund = ""
    uebergabe = TaifunUebergabe(vorgang_id=vorgang.id, datei=name, pfad=str(ziel), benutzer_id=benutzer_id,
                                grund=grund, status=STATUS_GESCHRIEBEN, geschrieben_am=jetzt)
    session.add(uebergabe)
    text = f"An TAIFUN übergeben: {name}"
    if hinweise:
        text += " – Hinweise: " + "; ".join(hinweise)
    _aktivitaet(session, vorgang.id, text, benutzer_id)
    _commit_mit_wiederholung(session)
    meldung = f"An TAIFUN übergeben: {name}"
    if hinweise:
        meldung += f" ({len(hinweise)} Hinweis{'e' if len(hinweise) != 1 else ''} in der Karteikarte)"
    return True, meldung, uebergabe


def testdatei_schreiben(session: Session, benutzer_id=None, jetzt: datetime | None = None
                        ) -> tuple[bool, str, TaifunUebergabe | None]:
    """„Testdatei schreiben“ (Lead-Einstellungen): Demo-Lead „Max Mustermann“ als
    LM_TEST_<Zeit>.xml in den Import-Ordner – funktioniert auch bei taifun_export_aktiv = aus.
    Übergabe-Zeile mit vorgang_id 0 und Grund testdatei (Übergabeliste, Abholung)."""
    from app.db import verbindung_freigeben
    jetzt = jetzt or datetime.now()
    ordner = import_ordner(session)
    benutzer = session.get(Benutzer, benutzer_id) if benutzer_id else None
    inhalt = xml_aus_feldern(testdatei_felder(jetzt, benutzer), encoding(session))
    fehler = validieren(inhalt)
    name = dateiname(None, jetzt, test=True)
    if fehler:
        text = "Validierung gegen ADRESSEN.xsd fehlgeschlagen: " + "; ".join(fehler)[:1500]
        uebergabe = TaifunUebergabe(vorgang_id=0, datei=name, pfad="", benutzer_id=benutzer_id,
                                    grund=GRUND_TESTDATEI, status=STATUS_FEHLER, fehler_text=text[:2000])
        session.add(uebergabe)
        _commit_mit_wiederholung(session)
        return False, f"Testdatei nicht geschrieben – {text}", uebergabe
    verbindung_freigeben(session)
    name = freier_dateiname(ordner, None, jetzt, test=True)
    try:
        ziel = datei_schreiben(ordner, name, inhalt)
    except OSError as problem:
        text = _fehler_text(problem, ordner)
        uebergabe = TaifunUebergabe(vorgang_id=0, datei=name, pfad=str(Path(ordner) / name),
                                    benutzer_id=benutzer_id, grund=GRUND_TESTDATEI, status=STATUS_FEHLER,
                                    fehler_text=text[:2000])
        session.add(uebergabe)
        _commit_mit_wiederholung(session)
        return False, f"Testdatei nicht geschrieben – {text}", uebergabe
    kopie_ablegen(name, inhalt)
    uebergabe = TaifunUebergabe(vorgang_id=0, datei=name, pfad=str(ziel), benutzer_id=benutzer_id,
                                grund=GRUND_TESTDATEI, status=STATUS_GESCHRIEBEN, geschrieben_am=jetzt)
    session.add(uebergabe)
    _commit_mit_wiederholung(session)
    return True, (f"Testdatei {name} in {ordner} geschrieben – jetzt in TAIFUN importieren und danach "
                  "das Häkchen „Testdatei in TAIFUN importiert“ setzen."), uebergabe


def als_importiert(session: Session, uebergabe: TaifunUebergabe, benutzer=None) -> tuple[bool, str]:
    """„Als importiert markieren“ (Übergabeliste): Status importiert + Zeit, Vorgangsfeld folgt,
    Aktivität am Vorgang. Der Aufrufer committet."""
    if uebergabe.status == STATUS_FEHLER:
        return False, "Eine fehlgeschlagene Übergabe kann nicht als importiert markiert werden."
    if uebergabe.status == STATUS_UEBERSPRUNGEN:
        return False, "Eine übersprungene Übergabe (keine Datei) kann nicht als importiert markiert werden."
    if uebergabe.status == STATUS_IMPORTIERT:
        return False, "Bereits als importiert markiert."
    uebergabe.status = STATUS_IMPORTIERT
    uebergabe.importiert_am = datetime.now()
    if uebergabe.vorgang_id:
        vorgang = session.get(Vorgang, uebergabe.vorgang_id)
        if vorgang is not None and (vorgang.taifun_export_datei or "") == (uebergabe.datei or ""):
            vorgang.taifun_export_status = STATUS_IMPORTIERT
        if vorgang is not None:
            _aktivitaet(session, vorgang.id, f"TAIFUN-Übergabe {uebergabe.datei} als importiert markiert",
                        benutzer.id if benutzer is not None else None)
    session.flush()
    return True, f"{uebergabe.datei}: als importiert markiert."


# --- Terminierung (Auslöser 1) ------------------------------------------------------------------

def terminierung_export(session: Session, vorgang: Vorgang, benutzer=None) -> dict:
    """Export beim Klick auf „Terminierung“ – VOR der Testphase-Sperre (routers/lm_termin.py):
    {exportiert, ok, meldung, uebergabe, bereit, uebersprungen}. Regeln: Pflichtfelder + vorgemerkter
    Termin (lead_kartei.terminierung_pruefung) und Kanal nicht „?“; bei taifun_export_aktiv = aus nur
    die Aktivität „TAIFUN-Übergabe nicht aktiv (Parameter)“ [ANNAHME]; Dubletten-Beleg oder
    bereits übergeben → kein automatischer Export, sondern Aktivität + Zeile „übersprungen
    (Rückfrage)“ in der Übergabeliste, dort „Trotzdem übergeben“ (Nachtrag 16.10.2026: kein
    Kartei-Knopf mehr). Eigene kleine Commits (Aktivität); der Export selbst committet in
    exportieren()."""
    from app import lead_kartei
    kunde = session.get(Kunde, vorgang.kunde_id)
    ergebnis = {"exportiert": False, "ok": False, "meldung": "", "uebergabe": None,
                "bereit": False, "uebersprungen": ""}
    if not aktiv(session):
        _aktivitaet(session, vorgang.id, NICHT_AKTIV_TEXT, benutzer.id if benutzer is not None else None)
        _commit_mit_wiederholung(session)
        ergebnis.update(meldung=NICHT_AKTIV_TEXT, uebersprungen="nicht_aktiv")
        return ergebnis
    if kunde is None:
        ergebnis.update(meldung="Kunde fehlt.", uebersprungen="kunde")
        return ergebnis
    pruefung_ = lead_kartei.terminierung_pruefung(session, kunde, vorgang)
    fehlend = list(pruefung_.get("fehlend") or [])
    if kanal_unklar(session, vorgang, kunde) and "Vertriebskanal klären" not in fehlend:
        fehlend.append("Vertriebskanal klären")
    if fehlend or pruefung_.get("erledigt"):
        ergebnis.update(meldung=("Terminierung nicht möglich – es fehlt: " + ", ".join(fehlend))
                        if fehlend else "Bereits terminiert – alle Objekttermine sind geplant.",
                        uebersprungen="pflicht")
        return ergebnis
    ergebnis["bereit"] = True
    rueckfrage = rueckfrage_text(session, vorgang, kunde)
    if rueckfrage:
        text = f"TAIFUN-Übergabe bei der Terminierung übersprungen: {rueckfrage}"
        benutzer_id = benutzer.id if benutzer is not None else None
        _aktivitaet(session, vorgang.id, text, benutzer_id)
        uebergabe = _uebersprungen_verbuchen(session, vorgang, benutzer_id, rueckfrage)
        _commit_mit_wiederholung(session)
        ergebnis.update(meldung=text + " (Übergabeliste → „Trotzdem übergeben“)",
                        uebersprungen="rueckfrage", uebergabe=uebergabe)
        return ergebnis
    ok, meldung, uebergabe = exportieren(session, vorgang.id, benutzer.id if benutzer is not None else None,
                                         GRUND_TERMINIERUNG)
    ergebnis.update(exportiert=True, ok=ok, meldung=meldung, uebergabe=uebergabe)
    return ergebnis


# --- Kartei, Boards, Einstellungen (Kontexte) ------------------------------------------------

def darf_uebergeben(session: Session, benutzer) -> bool:
    """„Erneut übergeben“ / „Trotzdem übergeben“ (Übergabeliste) und der Zugang zur Liste:
    Innendienst, Leadmanagement, Admin – nicht Außendienst/HV."""
    from app import leadmanagement as kern
    return bool(benutzer is not None and kern.lead_modul_sichtbar(session, benutzer))


def kartei_hinweis(session: Session, vorgang: Vorgang) -> dict | None:
    """Roter Hinweisbalken „TAIFUN-Übergabe fehlgeschlagen“ (Muster _mail_hinweis.html, v29) –
    seit dem Nachtrag 16.10.2026 mit dem Link „Zur Übergabeliste“ (?status=fehler) statt eines
    Knopfs; wiederholt wird dort."""
    if vorgang is None or (vorgang.taifun_export_status or "") != STATUS_FEHLER:
        return None
    letzte = (session.query(TaifunUebergabe)
              .filter(TaifunUebergabe.vorgang_id == vorgang.id, TaifunUebergabe.status == STATUS_FEHLER)
              .order_by(TaifunUebergabe.id.desc()).first())
    wann = letzte.geschrieben_am.strftime("%d.%m.%Y %H:%M") if letzte is not None and letzte.geschrieben_am else ""
    return {"art": "fehler", "titel": LABEL_FEHLER,
            "text": (f"vom {wann}: " if wann else "") + (vorgang.taifun_export_grund or "Grund unbekannt"),
            "liste_url": "/lead-management/taifun-uebergaben?status=fehler",
            "uebergabe_id": letzte.id if letzte is not None else None}


def kartei_kontext(session: Session, vorgang: Vorgang, kunde: Kunde | None, benutzer=None,
                   readonly: bool = False) -> dict:
    """Kontext `taifun` der Kundenkartei: Badge „TAIFUN <Datum>“ (ohne Kundennummer), Hinweisbalken,
    Testphase-Kennzeichen des Terminierungs-Knopfs, Link zur Übergabeliste. Kein Kartei-Knopf, kein
    Kundennummer-Feld (Nachtrag 16.10.2026, PLAN_LEAD_V6_1)."""
    from app import lead_v5
    ist_aktiv = aktiv(session)
    unklar = kanal_unklar(session, vorgang, kunde)
    status = vorgang.taifun_export_status or ""
    erfolg = status in ERFOLG_STATUS and vorgang.taifun_export_am is not None
    von = session.get(Benutzer, vorgang.taifun_export_von) if vorgang.taifun_export_von else None
    am_text = vorgang.taifun_export_am.strftime("%d.%m.%Y") if vorgang.taifun_export_am else ""
    badge_titel = ""
    if erfolg:
        badge_titel = (f"An TAIFUN übergeben am {vorgang.taifun_export_am.strftime('%d.%m.%Y %H:%M')}"
                       + (f" durch {von.name}" if von is not None else "")
                       + (f" · {vorgang.taifun_export_datei}" if vorgang.taifun_export_datei else "")
                       + f" · Status {STATUS_NAMEN.get(status, status)}")
    return {
        "aktiv": ist_aktiv, "kanal_unklar": unklar,
        "liste_erlaubt": darf_uebergeben(session, benutzer),
        "status": status, "status_text": STATUS_NAMEN.get(status, status), "am": vorgang.taifun_export_am,
        "am_text": am_text, "datei": vorgang.taifun_export_datei or "", "von": von,
        "badge": f"TAIFUN {am_text}" if erfolg else "",
        "badge_titel": badge_titel,
        "hinweis": kartei_hinweis(session, vorgang),
        "testphase_export": bool(ist_aktiv and not lead_v5.terminierung_aktiv(session) and not unklar),
        "testphase_hinweis": TESTPHASE_EXPORT_HINWEIS,
        "liste_url": "/lead-management/taifun-uebergaben",
    }


def board_text(vorgang: Vorgang) -> str:
    """Tooltip der Spalte „TAIFUN-Übergabe“ / des Labels in den Boards."""
    status = vorgang.taifun_export_status or ""
    if status == STATUS_FEHLER:
        return f"{LABEL_FEHLER}: {vorgang.taifun_export_grund or ''}".strip(": ")
    if vorgang.taifun_export_am:
        return (f"An TAIFUN übergeben am {vorgang.taifun_export_am.strftime('%d.%m.%Y %H:%M')}"
                + (f" · {vorgang.taifun_export_datei}" if vorgang.taifun_export_datei else "")
                + f" · {STATUS_NAMEN.get(status, status)}")
    return ""


def fehler_anzahl(session: Session) -> int:
    """Zähler „TAIFUN-Übergaben mit Fehler“ = Vorgänge mit taifun_export_status = fehler."""
    return int(session.query(Vorgang).filter(Vorgang.taifun_export_status == STATUS_FEHLER).count())


def liste(session: Session, status: str = "", limit: int = 300) -> list[dict]:
    """Zeilen der Übergabeliste (Datum, Vorgang, Datei, Benutzer, Status) – Filter nach Status.
    Je Zeile mit Vorgang (v35-Nachtrag 3): `erneut` (Knopf anzeigen), `erneut_label`
    („Erneut übergeben“ / „Trotzdem übergeben“ bei übersprungener Rückfrage), `erneut_text`
    (Rückfrage mit Datum der letzten Übergabe bzw. Dubletten-Beleg) und `kanal_unklar`."""
    abfrage = session.query(TaifunUebergabe)
    if status in STATUS_NAMEN:
        abfrage = abfrage.filter(TaifunUebergabe.status == status)
    eintraege = abfrage.order_by(TaifunUebergabe.id.desc()).limit(limit).all()
    vorgang_ids = {e.vorgang_id for e in eintraege if e.vorgang_id}
    vorgaenge = ({v.id: v for v in session.query(Vorgang).filter(Vorgang.id.in_(vorgang_ids))}
                 if vorgang_ids else {})
    kunden_ids = {v.kunde_id for v in vorgaenge.values()}
    kunden = ({k.id: k for k in session.query(Kunde).filter(Kunde.id.in_(kunden_ids))} if kunden_ids else {})
    benutzer_ids = {e.benutzer_id for e in eintraege if e.benutzer_id}
    benutzer = ({b.id: b for b in session.query(Benutzer).filter(Benutzer.id.in_(benutzer_ids))}
                if benutzer_ids else {})
    belege = dubletten_belege(session, kunden_ids)
    zeilen = []
    for e in eintraege:
        vorgang = vorgaenge.get(e.vorgang_id)
        kunde = kunden.get(vorgang.kunde_id) if vorgang is not None else None
        erneut = vorgang is not None and bool(e.vorgang_id)
        zeilen.append({"eintrag": e, "vorgang": vorgang, "kunde": kunde,
                       "benutzer": benutzer.get(e.benutzer_id),
                       "status_text": STATUS_NAMEN.get(e.status, e.status),
                       "grund_text": GRUND_NAMEN.get(e.grund, e.grund),
                       "kopie": kopie_pfad(e.datei) is not None,
                       "test": not e.vorgang_id,
                       "erneut": erneut,
                       "erneut_label": TROTZDEM_LABEL if e.status == STATUS_UEBERSPRUNGEN else ERNEUT_LABEL,
                       "erneut_text": (erneut_text(vorgang, kunde, belege.get(kunde.id, "") if kunde else "", e)
                                       if erneut else ""),
                       "kanal_unklar": bool(erneut and kunde is not None
                                            and (kunde.vertriebskanal or "").strip() == "?")})
    return zeilen


def status_zaehler(session: Session) -> dict:
    zaehler: dict = {}
    for status, in session.query(TaifunUebergabe.status):
        zaehler[status] = zaehler.get(status, 0) + 1
    return zaehler


def einstellungen_kontext(session: Session) -> dict:
    """Abschnitt „TAIFUN-Übergabe“ der Lead-Einstellungen: Werte, Prüfpunkte, Zähler."""
    geprueft = _parameter(session, "taifun_ordner_geprueft")
    testdatei_ok = haekchen(session, "taifun_testdatei_ok")
    encoding_ok = haekchen(session, "taifun_encoding_ok")
    fehler = fehler_anzahl(session)
    pruefpunkte = [
        {"name": "Ordner erreichbar", "ok": geprueft.startswith("ok"),
         "text": geprueft or "noch nicht geprüft – Knopf „Ordner prüfen“ (Dienstkonto SYSTEM)"},
        {"name": "Testdatei in TAIFUN importiert", "ok": testdatei_ok,
         "text": "Häkchen gesetzt" if testdatei_ok else "„Testdatei schreiben“, in TAIFUN importieren, Häkchen setzen"},
        {"name": "Encoding bestätigt", "ok": encoding_ok,
         "text": "Häkchen gesetzt" if encoding_ok else "Umlaute/ß nach dem Import in TAIFUN prüfen, Häkchen setzen"},
        {"name": "Übergaben mit Fehler", "ok": fehler == 0,
         "text": f"{fehler} Vorgang/Vorgänge mit Status fehler" if fehler else "keine"},
    ]
    return {"aktiv": aktiv(session), "ordner": import_ordner(session), "encoding": encoding(session),
            "encodings": ENCODINGS, "standard_ordner": STANDARD_ORDNER, "testdatei_ok": testdatei_ok,
            "encoding_ok": encoding_ok, "geprueft": geprueft, "fehler_anzahl": fehler,
            "pruefpunkte": pruefpunkte, "liste_url": "/lead-management/taifun-uebergaben",
            "dienstkonto_hinweis": DIENSTKONTO_HINWEIS, "lauf": LAUF_NAME,
            "zaehler": status_zaehler(session)}


def parameter_speichern(session: Session, form, benutzer=None, pruefung_ergebnis=None) -> list[str]:
    """Parameter des Abschnitts aus dem Formular der Lead-Einstellungen übernehmen (Schalter,
    Ordner, Encoding, Häkchen; Änderungen protokolliert). `pruefung_ergebnis` = (ok, meldung) der
    Ordnerprüfung, die die Route VOR den Schreibzugriffen ausgeführt hat. Liefert Meldungen."""
    from app import leadmanagement as kern
    meldungen: list[str] = []
    if form.get("taifun_dabei") is None:
        return meldungen
    schalter = (form.get("taifun_export_aktiv") or "aus").strip().lower()
    if schalter in ("an", "aus"):
        alt = _parameter(session, "taifun_export_aktiv") or "aus"
        if schalter != alt:
            kern.einstellungs_protokoll(session, f"taifun_export_aktiv {alt} → {schalter}", benutzer)
            meldungen.append(f"TAIFUN-Übergabe {'eingeschaltet' if schalter == 'an' else 'ausgeschaltet'}.")
        kern.parameter_setzen(session, "taifun_export_aktiv", schalter)
    ordner = (form.get("taifun_import_ordner") or "").strip()
    if ordner:
        alt = _parameter(session, "taifun_import_ordner")
        if ordner != alt:
            kern.einstellungs_protokoll(session, f"taifun_import_ordner {alt or '(leer)'} → {ordner}", benutzer)
        kern.parameter_setzen(session, "taifun_import_ordner", ordner)
    enc = (form.get("taifun_export_encoding") or "").strip().lower()
    if enc in ENCODINGS:
        alt = _parameter(session, "taifun_export_encoding")
        if enc != alt:
            kern.einstellungs_protokoll(session, f"taifun_export_encoding {alt} → {enc}", benutzer)
        kern.parameter_setzen(session, "taifun_export_encoding", enc)
    for name in ("taifun_testdatei_ok", "taifun_encoding_ok"):
        kern.parameter_setzen(session, name, "1" if form.get(name) else "")
    if pruefung_ergebnis is not None:
        ok, text = pruefung_ergebnis
        stempel = datetime.now().strftime("%d.%m.%Y %H:%M")
        kern.parameter_setzen(session, "taifun_ordner_geprueft",
                              (f"ok {stempel}: {text}" if ok else f"fehler {stempel}: {text}")[:290])
        meldungen.append(text)
    return meldungen


def ordner_pruefung_speichern(session: Session, ok: bool, text: str) -> None:
    from app import leadmanagement as kern
    stempel = datetime.now().strftime("%d.%m.%Y %H:%M")
    kern.parameter_setzen(session, "taifun_ordner_geprueft",
                          (f"ok {stempel}: {text}" if ok else f"fehler {stempel}: {text}")[:290])


# --- Scheduler-Lauf: Abholung prüfen, Kopien bereinigen -------------------------------------------

def _kopien_bereinigen(jetzt: datetime) -> int:
    """Protokoll-Kopien älter als AUFBEWAHRUNG_TAGE entfernen (12 Monate)."""
    entfernt = 0
    try:
        if not KOPIE_ORDNER.is_dir():
            return 0
        grenze = jetzt.timestamp() - AUFBEWAHRUNG_TAGE * 86400
        for datei in KOPIE_ORDNER.glob("LM_*.xml"):
            try:
                if datei.stat().st_mtime < grenze:
                    datei.unlink()
                    entfernt += 1
            except OSError:
                continue
    except OSError:
        return entfernt
    return entfernt


def abholung_pruefen(jetzt: datetime | None = None) -> dict:
    """Je Übergabe mit Status geschrieben prüfen, ob die Datei noch im Ordner liegt – fehlt sie,
    Status abgeholt (= von TAIFUN oder einem Mitarbeiter verarbeitet). Ein nicht erreichbarer
    Ordner (Netzlaufwerk weg) markiert NICHTS. Muster: lesen → Sitzung zu → Datei-I/O → kurze
    Schreibsitzung in Blöcken."""
    from app import db
    jetzt = jetzt or datetime.now()
    with db.kurz(schreibend=False) as s:
        offene = [(e.id, e.vorgang_id, e.datei, e.pfad) for e in
                  s.query(TaifunUebergabe).filter(TaifunUebergabe.status == STATUS_GESCHRIEBEN)
                  .order_by(TaifunUebergabe.id)]
    abgeholt: list[tuple[int, int, str]] = []
    ordner_fehlt: set[str] = set()
    for eintrag_id, vorgang_id, datei, pfad in offene:
        if not pfad:
            continue
        ordner = str(Path(pfad).parent)
        if ordner in ordner_fehlt:
            continue
        try:
            if not Path(ordner).is_dir():
                ordner_fehlt.add(ordner)
                continue
            if not Path(pfad).exists():
                abgeholt.append((eintrag_id, vorgang_id, datei))
        except OSError:
            ordner_fehlt.add(ordner)
    for start in range(0, len(abgeholt), BLOCK_GROESSE):
        block = abgeholt[start:start + BLOCK_GROESSE]
        with db.kurz() as s:
            for eintrag_id, vorgang_id, datei in block:
                eintrag = s.get(TaifunUebergabe, eintrag_id)
                if eintrag is None or eintrag.status != STATUS_GESCHRIEBEN:
                    continue
                eintrag.status = STATUS_ABGEHOLT
                eintrag.abgeholt_am = jetzt
                if vorgang_id:
                    vorgang = s.get(Vorgang, vorgang_id)
                    if vorgang is not None and (vorgang.taifun_export_datei or "") == (datei or "") \
                            and vorgang.taifun_export_status == STATUS_GESCHRIEBEN:
                        vorgang.taifun_export_status = STATUS_ABGEHOLT
    return {"geprueft": len(offene), "abgeholt": len(abgeholt), "ordner_fehlt": sorted(ordner_fehlt)}


def scheduler_lauf() -> str:
    jetzt = datetime.now()
    ergebnis = abholung_pruefen(jetzt)
    entfernt = _kopien_bereinigen(jetzt) if jetzt.hour == 3 and jetzt.minute < 20 else 0
    text = f"{ergebnis['geprueft']} offen, {ergebnis['abgeholt']} abgeholt"
    if ergebnis["ordner_fehlt"]:
        text += " – Ordner nicht erreichbar: " + ", ".join(ergebnis["ordner_fehlt"])
    if entfernt:
        text += f", {entfernt} alte Kopien entfernt"
    return text


def scheduler_starten() -> None:
    """Lauf taifun-uebergaben (900 s): prüft, ob exportierte Dateien noch im Zielordner liegen
    (fehlt die Datei → Status abgeholt), räumt Kopien älter als 12 Monate auf (einmal täglich,
    03:00–03:20). Aufruf aus main.lifespan (Orchestrator)."""
    from app import scheduler
    scheduler.registrieren(LAUF_NAME, LAUF_INTERVALL_S, scheduler_lauf,
                           beschreibung="TAIFUN-Übergabe: Abholung der XML-Dateien prüfen, alte Kopien räumen",
                           start_verzoegerung_s=240)


# --- Migration --------------------------------------------------------------------------------

def migration_v35_taifun(session: Session) -> list[str]:
    """Parameter der TAIFUN-Übergabe anlegen (idempotent; Standard: Schalter aus) und den
    Kopie-Ordner data/taifun_export anlegen. Hook registriert der Orchestrator in migrate.py."""
    from app import leadmanagement as kern
    from app.models import LeadParameter
    meldungen: list[str] = []
    vorhanden = {p.name for p in session.query(LeadParameter.name)
                 .filter(LeadParameter.name.in_(tuple(PARAMETER)))}
    for name, wert in PARAMETER.items():
        if name not in vorhanden:
            kern.parameter_setzen(session, name, wert)
            meldungen.append(f"v35: Parameter {name} = {wert or '(leer)'} angelegt")
    try:
        KOPIE_ORDNER.mkdir(parents=True, exist_ok=True)
    except OSError as problem:
        meldungen.append(f"v35: Ordner {KOPIE_ORDNER} nicht angelegt ({problem})")
    session.flush()
    return meldungen
