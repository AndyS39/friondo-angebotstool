# Kundenkommunikation des Lead-Managements (v12, Phase 78) MIT SENDESPERRE:
# Vorlagen (Gruppe Lead-Management), Warteschlange kommunikation_log,
# Versand-Job jede Minute. mail_modus: protokoll (rendern, NICHT senden),
# test (an mail_testadresse mit [TEST …]-Präfix), live (nur zulässig bei
# lead_freigabe_modus = alle – sonst wird wie protokoll verarbeitet).
# v27 (PLAN_V17 Phase 128): Versand-Job am Scheduler-Rahmen registriert, je
# Eintrag eine kurze Sitzung mit Commit (kein eigener Thread mehr).
# v29 (PLAN_LEAD_V4 Phase 142):
#  - Absender ALLER Lead-Mails ist der Parameter absender_lead_mails (Standard
#    termin@friondo.de) – KEIN Fallback auf ein anderes Postfach; leads@ bleibt
#    reines Eingangspostfach des Parsers (lead_parser, Parameter absender_postfach).
#    Scheitert der Versand, wird bis zu VERSUCHE_MAX-mal wiederholt, danach
#    Status `fehler` + Vorgangsfelder mail_fehler* + Aktivität „Mail nicht
#    gesendet: <Vorlage>, <Grund>“ (Innendienst sieht den Lead oben im Hauptboard).
#  - Terminbestätigung je Vertriebler: Vorlage terminbestaetigung_<benutzer_id>
#    (Einstellungen lead_vorlage_terminbestaetigung_<id>_betreff/_text, dazu
#    _quelle und _hash für die Zulieferung) – Rahmen + individueller Block
#    {vertriebler_block} (Bild als Inline-CID, Name, Telefon, E-Mail; Infotext bis v32);
#    Sparten-Baustein {sparten_hinweise} aus dem Blatt „Terminhinweise“.
#  - Nurture entfällt: Vorlage ausgeblendet (Datensatz bleibt), offene
#    Nurture-Einträge werden storniert, die Kaskade endet mit disqualifiziert.
#  - Bounce (lead_mail_abruf): email_status = ungueltig, weitere Einträge an die
#    Adresse `wartet_adresse`; adresse_geaendert() gibt sie wieder frei.
#  - Zulieferung docs/vorlagen/terminbestaetigung/<name>.html|.jpg wiederholbar
#    einspielbar (zulieferung_einspielen), Migration migration_v29_mails.
# Nachtrag 08.10.2026 (Antwort Andreas):
#  - Kundenantwort holt einen nicht erreichten/zurückgestellten Lead zurück nach
#    in_kontaktierung (kundenantwort_verbuchen, wie vor v29) – danach Innendienst manuell.
#  - Status `fehler` legt zusätzlich eine Betriebsglocke (art system) an alle aktiven
#    Admins an – einmal je Eintrag, in derselben Sitzung (_admins_glocke).
#  - Graph-Nachrichten tragen replyTo = Leadmanager (Benutzer.email) + Absender termin@
#    (antwort_adressen, _graph_senden(…, vorgang=)).
#  - HV-Versandweg `entwurf` ist gebaut und Standard: fertige Terminbestätigung als
#    .eml (eml_erstellen – HTML + Text, ICS, Inline-Bilder als CID; From = E-Mail des
#    HV), To-Do „… aus dem eigenen Postfach senden“ mit Vorschau-Link; Migration
#    offen → entwurf einmalig (Marker migration_v29_hv_entwurf).
# v31 (PLAN_LEAD_V5 Phase 153/156/158/159):
#  - Sparten in Kundentexten ausgeschrieben: {sparten} → „Wärmepumpe und Photovoltaik“
#    (sparten.sparten_text, Parameter sparten_langnamen), neu {sparten_interesse}
#    („Interesse an einer Wärmepumpe“), {sparten_hinweise} mit Langform als
#    Zwischenüberschrift; ICS-Titel ebenso. Interne Badges behalten die Kürzel.
#  - Vorlage `nicht_erreicht` entfällt (VORLAGEN_AUSGEBLENDET: Datensatz bleibt, Editor
#    blendet sie aus, Versand-Job storniert Altbestand); Kaskade Versuch 2/4 = keine.
#  - Neue Vorlagen `terminbestaetigung_objekte` (Rahmen + {vertriebler_block} +
#    {objektliste}, ICS je Objekttermin – mehrere ICS in einer Mail, anhang_pfad mit
#    „;“ getrennt) und `falsche_telefonnummer` (Kontakt, falsche_nummer_mail).
#  - Platzhalter {objektadresse} (Adresse des Objekts des Termins, Ein-Objekt =
#    Kundenadresse), {vorname}, {nachname}, {absender}.
#  - Verträge mit K (Kartei-Dialog): vorlage_rendern(session, key, vorgang, termin=,
#    objekt=, benutzer=) -> (betreff, html, fehlende_pflichtdaten) und
#    in_warteschlange(session, vorgang, key, betreff, text, termin=, anhaenge=,
#    benutzer=) -> KommunikationLog (Text bleibt fest – kanal „mail_fest“).
#  - Mailsperre (Phase 159): lead_v5.mail_versand_aktiv = aus → jeder Eintrag endet mit
#    Status `gesperrt` (kein Graph-Aufruf, auch nicht Testpostfach, keine fehler-Glocke);
#    mail_modus ist keine Steuerung mehr (bei „an“ geht die Mail an den Kunden).
#    Gesperrte Einträge werden beim späteren Einschalten NICHT nachgesendet [ANNAHME],
#    „Erneut senden“ bleibt als bewusster Klick möglich. gesperrte_anzahl() für den
#    Zähler der Lead-Einstellungen (B). Migration migration_v31_mails (migrate.py-Hook).
# v33 (PLAN_V20 Phase 166/175):
#  - Graph-Versand (_graph_senden, testmail_senden) über graph_versand.versand_pfad: im
#    Modus anwendung sendMail direkt am Postfach /users/<absender_lead_mails> (termin@,
#    kein from-Feld, kein „Senden als“); im Modus delegiert unverändert /me/sendMail mit
#    from = termin@. Kein Fallback-Postfach (v29 bleibt).
#  - {vertriebler_block} nur noch Bild, Name, Telefon, E-Mail – der Infotext zum AD entfällt
#    vollständig (Spalte benutzer.infotext bleibt, wird nicht mehr gelesen; Phase 175).

import base64
import hashlib
import html as html_modul
import re
from datetime import datetime, timedelta
from pathlib import Path

from sqlalchemy import Integer, String
from sqlalchemy.orm import Session, mapped_column

from app import config
from app import sparten as sparten_modul
from app import rollen as rollen_modul   # v33: Basisrolle/Rollen-Varianten

from app.models import (AdProfil, Benutzer, KommunikationLog, Kunde, LeadQuelle,
                        Vorgang, VotTermin, LEAD_PHASEN_NAMEN)

# v29: Absender ohne Fallback – ABSENDER_FALLBACK bleibt nur für den
# Protokoll-Hinweis („kein Fallback auf angebot@“) und Alt-Tests erhalten
ABSENDER_STANDARD = "termin@friondo.de"
ABSENDER_FALLBACK = "angebot@friondo.de"
PARAMETER_ABSENDER = "absender_lead_mails"
BASIS_URL = config.BASIS_URL   # v27: aus der .env (BASIS_URL), Standard wie bisher

# v29: Wiederholversuche des Versand-Jobs vor Status `fehler`, Pause je Versuch
VERSUCHE_MAX = 3
WIEDERHOLUNG_PAUSE_S = 60
STATUS_FEHLER = "fehler"
STATUS_WARTET_ADRESSE = "wartet_adresse"
# v31 (Phase 159): Status der Mailsperre – Eintrag gerendert, aber nie gesendet
STATUS_GESPERRT = "gesperrt"
# v31 (Phase 158): Einträge aus dem Kartei-Dialog tragen einen festen (nachbearbeiteten)
# Text – der Versand-Job rendert sie nicht neu (rendern() lässt Betreff/Text stehen)
KANAL_FEST = "mail_fest"
# Vorlagen, deren Datensatz bleibt, die aber nicht mehr angeboten/gesendet werden
# (v29 nurture; v31 Phase 156: nicht_erreicht – die Kaskade schickt nach Versuch 2/4
# keine Mail mehr, nur noch „Disqualifiziert, nicht erreicht“ nach dem letzten Versuch)
VORLAGEN_AUSGEBLENDET = ("nurture", "nicht_erreicht")
AUSGEBLENDET_GRUND = {"nurture": "Nurture entfällt (v29)",
                      "nicht_erreicht": "Vorlage „Nicht erreicht“ entfällt (v31)"}
TERMIN_VORLAGE = "terminbestaetigung"
# v31 (Phase 153): Terminbestätigung bei mehreren Objekten (eine Mail mit {objektliste},
# ICS je Objekttermin) und v31 (Phase 158) Vorlage „Falsche Telefonnummer“
OBJEKT_VORLAGE = "terminbestaetigung_objekte"
FALSCHE_NUMMER_VORLAGE = "falsche_telefonnummer"
# Termin-Mails, die bei Handelsvertreter-Leads dem Schalter hv_versandweg folgen
HV_TERMIN_VORLAGEN = ("terminbestaetigung", "terminerinnerung", "terminaenderung",
                      "terminabsage", OBJEKT_VORLAGE)
HV_VERSANDWEGE = ("offen", "smtp", "entwurf", "leads_im_namen")
# Nachtrag 08.10.2026 (Antwort Andreas): Standard = entwurf (.eml aus dem eigenen
# Postfach des Handelsvertreters); `offen` bleibt wählbar (bisheriges Verhalten)
HV_VERSANDWEG_STANDARD = "entwurf"
EML_VORLAGEN_NAMEN = {"terminbestaetigung": "Terminbestaetigung", "terminerinnerung": "Terminerinnerung",
                      "terminaenderung": "Terminaenderung", "terminabsage": "Terminabsage",
                      OBJEKT_VORLAGE: "Terminbestaetigung"}
EML_TODO_TITEL = {"terminbestaetigung": "Terminbestätigung aus dem eigenen Postfach senden",
                  "terminaenderung": "Terminänderung aus dem eigenen Postfach senden",
                  "terminabsage": "Terminabsage aus dem eigenen Postfach senden",
                  OBJEKT_VORLAGE: "Terminbestätigung (mehrere Objekte) aus dem eigenen Postfach senden"}
# Vorlagenbaum des Editors (Phase 142): Kategorie-Key, Anzeigename, Vorlagen-Keys
# (v31: Kontakt ohne nicht_erreicht, dafür falsche_telefonnummer; Oberkategorie
# Terminbestätigung mit der Objekt-Vorlage)
KATEGORIEN = [
    ("eingang", "Eingang", ["eingangsbestaetigung"]),
    ("kontakt", "Kontakt", ["disqualifiziert", FALSCHE_NUMMER_VORLAGE]),
    ("terminbestaetigung", "Terminbestätigung", ["terminbestaetigung", OBJEKT_VORLAGE]),
    ("termin", "Termin", ["terminerinnerung", "terminaenderung", "terminabsage",
                          "online_termin_einladung"]),
    ("sonstige", "Sonstige", []),
]
# v31 (Phase 156): Kürzel, die die Migration in gespeicherten Vorlagentexten/Betreffs
# als eigenständige Wörter durch die Langform ersetzt (MS/WA/DMS sind neu und stehen
# in keiner alten Vorlage; „MS“ wäre zudem mehrdeutig)
MIGRATION_KUERZEL = ("WP", "PV", "KL", "WB", "GW")
_KUERZEL_MUSTER = re.compile(r"(?<![\w{/+-])(" + "|".join(MIGRATION_KUERZEL) + r")(?![\w}/+-])")
_KUERZEL_PLUS_MUSTER = re.compile(r"(?<![\w{])((?:" + "|".join(MIGRATION_KUERZEL)
                                  + r")(?:\s*[+/]\s*(?:" + "|".join(MIGRATION_KUERZEL) + r"))+)(?![\w}])")
# individueller Block in einer Vertreter-Vorlage: entweder der Platzhalter
# {vertriebler_block} (Inhalt aus der Benutzerverwaltung) oder ein Bereich
# zwischen diesen Markern (Zulieferung/Editor)
BLOCK_PLATZHALTER = "{vertriebler_block}"
BLOCK_START = "<!-- vertriebler_block -->"
BLOCK_ENDE = "<!-- /vertriebler_block -->"
SPARTEN_EINLEITUNG = ("Damit wir uns optimal vorbereiten können, bitten wir Sie – sofern "
                      "möglich – folgende Punkte bereitzuhalten:")
ZULIEFERUNG_ORDNER = config.PROJEKT_ORDNER / "docs" / "vorlagen" / "terminbestaetigung"
BENUTZERBILDER_ORDNER = config.DATA_ORDNER / "benutzerbilder"
BILD_ENDUNGEN = {".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png"}
BILD_MAX_BYTES = 2 * 1024 * 1024
CID_PRAEFIX = "vertriebler-"


def _modell_ergaenzen() -> None:
    """v29: Die Spalten kommunikation_log.absender/versuche legt db.py an
    (_NACHTRAEGLICHE_SPALTEN); solange app/models.py (nicht Datei von L2) sie
    nicht mappt, werden sie hier additiv an das Modell gehängt (SQLAlchemy
    erlaubt das nachträgliche Zuweisen von mapped_column). Vorschlag im
    Bericht: beide Zeilen in models.KommunikationLog übernehmen – dann greift
    hasattr und dieser Schritt ist ohne Wirkung."""
    if not hasattr(KommunikationLog, "absender"):
        KommunikationLog.absender = mapped_column(String(200), default="")
    if not hasattr(KommunikationLog, "versuche"):
        KommunikationLog.versuche = mapped_column(Integer, default=0)


_modell_ergaenzen()

# Alter v12-Text der Terminbestätigung – die Migration ersetzt ihn, wenn er
# unverändert in der Datenbank steht (sonst werden nur die Platzhalter ergänzt)
_TERMINBESTAETIGUNG_V12_TEXT = (
    "{briefanrede},\n\n"
    "wir bestätigen Ihren Vor-Ort-Termin:\n\n"
    "Datum: {termin_datum}, {termin_uhrzeit} Uhr (ca. {termin_dauer} "
    "Minuten)\nIhr Berater: {vertriebler} {vertriebler_telefon}\n\n"
    "Damit der Termin für Sie den größten Nutzen hat, legen Sie bitte "
    "bereit:\n"
    "- letzte Heizkostenabrechnung\n"
    "- aktuelle Stromrechnung\n"
    "- Grundriss, falls vorhanden\n"
    "- Zugang zum Heizungsraum und zum Zählerschrank\n\n"
    "Den Termin finden Sie im Anhang für Ihren Kalender.\n\n"
    "Mit freundlichen Grüßen\nIhr Friondo-Team")

# Starttexte (sachlich, Sie-Form); {schluessel}: (Name, Betreff, Text)
VORLAGEN_START = {
    "eingangsbestaetigung": (
        "Eingangsbestätigung",
        "Ihre Anfrage bei Friondo – wir melden uns in Kürze",
        "{briefanrede},\n\n"
        "vielen Dank für Ihre Anfrage ({sparten}). Wir haben sie erhalten und "
        "melden uns innerhalb der nächsten Stunden telefonisch bei Ihnen, um "
        "die nächsten Schritte zu besprechen.\n\n"
        "Falls Sie vorab Fragen haben, antworten Sie einfach auf diese "
        "E-Mail oder nutzen Sie den Rückruf-Link: {link_rueckruf}\n\n"
        "Mit freundlichen Grüßen\nIhr Friondo-Team"),
    # v23 (Phase 104, C4): nach dem letzten Versuch der Kaskade (Stufe 5);
    # Texte laut F9 Platzhalter – Andreas ersetzt sie in der Vorlagenpflege
    "disqualifiziert": (
        "Disqualifiziert / Nicht erreicht",
        "Ihre Anfrage bei Friondo – wir konnten Sie nicht erreichen",
        "{briefanrede},\n\n"
        "wir haben in den vergangenen Wochen mehrfach versucht, Sie zu Ihrer "
        "Anfrage ({sparten}) telefonisch zu erreichen – leider ohne Erfolg. "
        "Wir schließen den Vorgang daher vorerst ab.\n\n"
        "Sollte das Thema für Sie weiterhin aktuell sein, melden Sie sich "
        "jederzeit gern: {rueckruf_telefon} oder einfach als Antwort auf "
        "diese E-Mail. Ihr Ansprechpartner ist {vertriebler}.\n\n"
        "Mit freundlichen Grüßen\nIhr Friondo-Team"),
    # v23 (Phase 104, F12): Online-Termin per Teams – Kunde wählt den Slot
    # über den Outlook-Buchungslink des Kollegen
    "online_termin_einladung": (
        "Online-Termin (Teams) – Einladung",
        "Ihr Online-Termin mit Friondo – bitte Wunschzeit wählen",
        "{briefanrede},\n\n"
        "gern besprechen wir Ihre Fragen zu {sparten} vorab in einem kurzen "
        "Online-Termin (Microsoft Teams) mit {kollege}.\n\n"
        "Wählen Sie hier einfach einen passenden Zeitpunkt: {buchungslink}\n\n"
        "Sie erhalten anschließend automatisch eine Kalendereinladung mit dem "
        "Teams-Link.\n\n"
        "Mit freundlichen Grüßen\nIhr Friondo-Team"),
    # v31 (Phase 156): „nicht_erreicht“ bleibt nur als Datensatz (VORLAGEN_AUSGEBLENDET) –
    # der Starttext wird nicht mehr angelegt und nie mehr gesendet
    "nicht_erreicht": (
        "Nicht erreicht",
        "Wir haben Sie leider nicht erreicht",
        "{briefanrede},\n\n"
        "wir haben mehrfach versucht, Sie telefonisch zu Ihrer Anfrage "
        "({sparten}) zu erreichen – leider ohne Erfolg.\n\n"
        "Rufen Sie uns gern zurück oder antworten Sie mit Ihrer Wunschzeit "
        "auf diese E-Mail: {link_rueckruf}\n"
        "Ihr Ansprechpartner: {leadmanager} {leadmanager_telefon}\n\n"
        "Mit freundlichen Grüßen\nIhr Friondo-Team"),
    # v31 (PLAN_LEAD_V5 Phase 158): Ergebnis „Falsche Nummer“ sendet diese Vorlage an die
    # E-Mail-Adresse des Leads (Text freigegeben 13.10.2026, Absender termin@)
    FALSCHE_NUMMER_VORLAGE: (
        "Falsche Telefonnummer",
        "Ihre Anfrage bei Friondo: wir erreichen Sie nicht",
        "{briefanrede},\n\n"
        "vielen Dank für Ihr {sparten_interesse}. Wir haben versucht, Sie "
        "telefonisch zu erreichen, leider ist die uns vorliegende Rufnummer "
        "nicht korrekt oder nicht mehr gültig.\n\n"
        "Damit wir Ihre Anfrage weiter bearbeiten können, antworten Sie bitte "
        "einfach auf diese E-Mail mit Ihrer aktuellen Telefonnummer und, wenn "
        "möglich, einer Uhrzeit, zu der wir Sie gut erreichen. Alternativ "
        "erreichen Sie uns unter {rueckruf_telefon}.\n\n"
        "Wir freuen uns darauf, mit Ihnen zu sprechen.\n\n"
        "Mit freundlichen Grüßen\n{absender}\nFriondo GmbH"),
    # v31 (PLAN_LEAD_V5 Phase 153): eine Bestätigung für alle Objekte eines Kunden –
    # Rahmen + {vertriebler_block} wie v29, {objektliste} = je Objekt Bezeichnung,
    # Adresse, Datum, Uhrzeit, Vertriebler; ICS je Objekttermin im Anhang
    OBJEKT_VORLAGE: (
        "Terminbestätigung – mehrere Objekte",
        "Ihre Vor-Ort-Termine bei Friondo ({termin_datum})",
        "{briefanrede},\n\n"
        "wir bestätigen Ihre Vor-Ort-Termine für Ihre Objekte:\n\n"
        "{objektliste}\n\n"
        "{sparten_hinweise}\n\n"
        "Die Termine finden Sie im Anhang für Ihren Kalender – ein Eintrag je Objekt.\n\n"
        "{vertriebler_block}\n\n"
        "Mit freundlichen Grüßen\nIhr Friondo-Team"),
    # v29 (Phase 142): Rahmen der Terminbestätigung – Terminblock mit {adresse},
    # Sparten-Baustein {sparten_hinweise}, individueller Block {vertriebler_block}
    "terminbestaetigung": (
        "Terminbestätigung",
        "Ihr Vor-Ort-Termin am {termin_datum} um {termin_uhrzeit} Uhr",
        "{briefanrede},\n\n"
        "wir bestätigen Ihren Vor-Ort-Termin:\n\n"
        "Datum: {termin_datum}, {termin_uhrzeit} Uhr (ca. {termin_dauer} Minuten)\n"
        "Adresse: {adresse}\n"
        "Ihr Berater: {vertriebler} {vertriebler_telefon}\n\n"
        "{sparten_hinweise}\n\n"
        "Den Termin finden Sie im Anhang für Ihren Kalender.\n\n"
        "{vertriebler_block}\n\n"
        "Mit freundlichen Grüßen\nIhr Friondo-Team"),
    "terminerinnerung": (
        "Terminerinnerung",
        "Erinnerung: Ihr Termin morgen um {termin_uhrzeit} Uhr",
        "{briefanrede},\n\n"
        "wir erinnern an Ihren Vor-Ort-Termin am {termin_datum} um "
        "{termin_uhrzeit} Uhr mit {vertriebler}.\n\n"
        "Sollte etwas dazwischenkommen, geben Sie uns bitte kurz Bescheid: "
        "{link_rueckruf}\n\n"
        "Mit freundlichen Grüßen\nIhr Friondo-Team"),
    "terminaenderung": (
        "Terminänderung",
        "Ihr Termin wurde verlegt: {termin_datum}, {termin_uhrzeit} Uhr",
        "{briefanrede},\n\n"
        "Ihr Vor-Ort-Termin wurde verlegt. Neuer Termin:\n\n"
        "Datum: {termin_datum}, {termin_uhrzeit} Uhr\n"
        "Ihr Berater: {vertriebler} {vertriebler_telefon}\n\n"
        "Der aktualisierte Kalendereintrag liegt bei. Falls der neue Termin "
        "nicht passt, melden Sie sich bitte kurz: {link_rueckruf}\n\n"
        "Mit freundlichen Grüßen\nIhr Friondo-Team"),
    # v23 (Phase 108, E3/E4): Absage durch Friondo mit Storno-ICS
    # (METHOD:CANCEL, gleiche UID) – der Kundenkalender entfernt den Eintrag
    "terminabsage": (
        "Terminabsage",
        "Ihr Termin am {termin_datum} um {termin_uhrzeit} Uhr wurde abgesagt",
        "{briefanrede},\n\n"
        "Ihr Vor-Ort-Termin am {termin_datum} um {termin_uhrzeit} Uhr mit "
        "{vertriebler} muss leider entfallen. Die Absage für Ihren Kalender "
        "liegt bei.\n\n"
        "Wir melden uns in Kürze mit einem neuen Terminvorschlag. Wenn Sie "
        "selbst einen Wunschtermin haben, erreichen Sie uns unter "
        "{rueckruf_telefon} oder einfach als Antwort auf diese E-Mail: "
        "{link_rueckruf}\n\n"
        "Mit freundlichen Grüßen\nIhr Friondo-Team"),
    # v29: „nurture“ ist aus dem Katalog entfernt (Datensatz lead_vorlage_nurture_*
    # bleibt in der Datenbank – Historie; VORLAGEN_AUSGEBLENDET)
}

PLATZHALTER_NEU = ["{sparten}", "{quelle}", "{termin_datum}", "{termin_uhrzeit}",
                   "{termin_dauer}", "{vertriebler}", "{vertriebler_telefon}",
                   "{leadmanager}", "{leadmanager_telefon}", "{wunschzeiten}",
                   "{link_rueckruf}", "{briefanrede}",
                   # v29 (Phase 142)
                   "{adresse}", "{sparten_hinweise}", "{vertriebler_block}",
                   "{vertriebler_vorname}", "{vertriebler_email}",
                   # v31 (Phase 153/156/158)
                   "{sparten_interesse}", "{objektadresse}", "{objektliste}",
                   "{vorname}", "{nachname}", "{absender}"]
# Platzhalter, deren Wert fertiges HTML ist (nicht maskieren)
_HTML_WERTE = ("sparten_hinweise", "vertriebler_block", "objektliste")
# Vorlagen, die einen Termin brauchen (Pflichtdaten im Kartei-Dialog, Phase 158)
TERMIN_PFLICHT_VORLAGEN = ("terminbestaetigung", "terminerinnerung", "terminaenderung",
                           "terminabsage", OBJEKT_VORLAGE)


# --- Vorlagen-Schlüssel, Katalog, Laden/Speichern -------------------------------------

def ist_vertriebler_key(schluessel: str) -> bool:
    return bool(re.fullmatch(rf"{TERMIN_VORLAGE}_\d+", schluessel or ""))


def vertriebler_id_aus_key(schluessel: str) -> int | None:
    treffer = re.fullmatch(rf"{TERMIN_VORLAGE}_(\d+)", schluessel or "")
    return int(treffer.group(1)) if treffer else None


def vertriebler_key(benutzer_id: int) -> str:
    return f"{TERMIN_VORLAGE}_{int(benutzer_id)}"


def objekt_vertriebler_key(benutzer_id: int) -> str:
    """v31 (Phase 153): optionale Vertriebler-Variante der Objekt-Terminbestätigung
    (terminbestaetigung_objekte_<id>) – wird nicht automatisch angelegt [ANNAHME];
    ohne eigene Variante gilt die Standard-Objektvorlage."""
    return f"{OBJEKT_VORLAGE}_{int(benutzer_id)}"


def objekt_vertriebler_id_aus_key(schluessel: str) -> int | None:
    treffer = re.fullmatch(rf"{OBJEKT_VORLAGE}_(\d+)", schluessel or "")
    return int(treffer.group(1)) if treffer else None


def schluessel_gueltig(session: Session, schluessel: str) -> bool:
    """Vorlagen-Key des Editors: Katalog (ohne ausgeblendete) oder eine
    Terminbestätigung eines (auch inaktiven) Benutzers."""
    if schluessel in VORLAGEN_START:
        return True
    benutzer_id = vertriebler_id_aus_key(schluessel)
    if benutzer_id is None:
        benutzer_id = objekt_vertriebler_id_aus_key(schluessel)
    return benutzer_id is not None and session.get(Benutzer, benutzer_id) is not None


def vertriebler_liste(session: Session) -> list[Benutzer]:
    """Aktive Vertriebler = Außendienst mit AD-Profil (angestellt oder
    Handelsvertreter terminiert_selbst) – jeder bekommt eine eigene
    Terminbestätigung. [ANNAHME: ein AD-Profil genügt; aktiv_terminierung wird
    nicht verlangt, damit auch manuell gebuchte AD eine Vorlage haben.]"""
    ids = {p.benutzer_id for p in session.query(AdProfil.benutzer_id)}
    if not ids:
        return []
    return (session.query(Benutzer)
            .filter(Benutzer.aktiv.is_(True), rollen_modul.filter_basis("aussendienst"),
                    Benutzer.id.in_(ids))
            .order_by(Benutzer.name).all())


def vorlage_name(session: Session, schluessel: str) -> str:
    if schluessel in VORLAGEN_START:
        return VORLAGEN_START[schluessel][0]
    benutzer_id = vertriebler_id_aus_key(schluessel)
    if benutzer_id is not None:
        person = session.get(Benutzer, benutzer_id)
        return f"Terminbestätigung – {person.name if person else benutzer_id}"
    benutzer_id = objekt_vertriebler_id_aus_key(schluessel)
    if benutzer_id is not None:
        person = session.get(Benutzer, benutzer_id)
        return f"Terminbestätigung mehrere Objekte – {person.name if person else benutzer_id}"
    return schluessel


def vorlage_laden(session: Session, schluessel: str,
                  sparte: str = "") -> tuple[str, str]:
    """(Betreff, Text): je Sparte, sonst allgemein, sonst Startwert. v29: eine
    Vertreter-Vorlage (terminbestaetigung_<id>) fällt auf die Standard-
    Terminbestätigung zurück, wenn sie leer ist; v31: ebenso die Vertreter-
    Variante der Objekt-Terminbestätigung auf die Objekt-Standardvorlage."""
    from app.models import einstellung_holen
    if sparte:
        betreff = einstellung_holen(
            session, f"lead_vorlage_{schluessel}_{sparte}_betreff", "")
        text = einstellung_holen(
            session, f"lead_vorlage_{schluessel}_{sparte}_text", "")
        if betreff and text:
            return betreff, text
    betreff = einstellung_holen(session, f"lead_vorlage_{schluessel}_betreff", "")
    text = einstellung_holen(session, f"lead_vorlage_{schluessel}_text", "")
    if betreff and text:
        return betreff, text
    if ist_vertriebler_key(schluessel):
        return vorlage_laden(session, TERMIN_VORLAGE, sparte)
    if objekt_vertriebler_id_aus_key(schluessel) is not None:
        return vorlage_laden(session, OBJEKT_VORLAGE, sparte)
    _, start_betreff, start_text = VORLAGEN_START.get(
        schluessel, ("", "Friondo", ""))
    return start_betreff, start_text


def vorlage_vorhanden(session: Session, schluessel: str) -> bool:
    """Betreff UND Text gespeichert (eigene Vorlage, nicht nur Fallback)."""
    from app.models import einstellung_holen
    return bool(einstellung_holen(session, f"lead_vorlage_{schluessel}_betreff", "")
                and einstellung_holen(session, f"lead_vorlage_{schluessel}_text", ""))


def vorlage_quelle(session: Session, schluessel: str) -> str:
    """editor | zulieferung | standard_kopie | '' (Startwert/unbekannt)."""
    from app.models import einstellung_holen
    return einstellung_holen(session, f"lead_vorlage_{schluessel}_quelle", "")


def vorlage_speichern(session: Session, schluessel: str, betreff: str, text: str,
                      sparte: str = "", quelle: str = "editor") -> None:
    """Betreff/Text (+ Quelle) ablegen; Sparten-Varianten tragen keine Quelle."""
    from app.models import einstellung_setzen
    zusatz = f"_{sparte}" if sparte else ""
    einstellung_setzen(session, f"lead_vorlage_{schluessel}{zusatz}_betreff", betreff)
    einstellung_setzen(session, f"lead_vorlage_{schluessel}{zusatz}_text", text)
    if not sparte:
        einstellung_setzen(session, f"lead_vorlage_{schluessel}_quelle", quelle)
    # autoflush ist aus: sofort schreiben, damit ein zweites Speichern derselben
    # Schlüssel in derselben Transaktion (Standard-Kopie → Zulieferung) die
    # Zeilen findet statt sie doppelt anzulegen (UNIQUE einstellungen.name)
    session.flush()


def vorlagen_vorbelegen(session: Session) -> int:
    """Starttexte als Einstellungen anlegen (idempotent, migrate.py)."""
    from app.models import einstellung_holen, einstellung_setzen
    neu = 0
    for schluessel, (_, betreff, text) in VORLAGEN_START.items():
        if schluessel in VORLAGEN_AUSGEBLENDET:
            continue   # v31: ausgeblendete Vorlagen werden nicht (mehr) angelegt
        if not einstellung_holen(session, f"lead_vorlage_{schluessel}_betreff", ""):
            einstellung_setzen(session, f"lead_vorlage_{schluessel}_betreff", betreff)
            einstellung_setzen(session, f"lead_vorlage_{schluessel}_text", text)
            neu += 1
    return neu


def terminbestaetigung_key(session: Session, ad_id: int | None) -> tuple[str, bool]:
    """Versandregel (Phase 142): (Vorlagen-Key, eigene Vorlage vorhanden?) –
    Vorlage des zugewiesenen Vertrieblers, sonst Standard."""
    if ad_id:
        key = vertriebler_key(ad_id)
        if vorlage_vorhanden(session, key):
            return key, True
    return TERMIN_VORLAGE, False


def objekt_vorlage_key(session: Session, termine) -> str:
    """v31 (Phase 153): Vorlage der Objekt-Terminbestätigung – haben alle Objekttermine
    denselben Vertriebler und liegt für ihn eine Variante terminbestaetigung_objekte_<id>
    vor, gilt diese, sonst die Standard-Objektvorlage."""
    ad_ids = {t.ad_id for t in (termine or []) if getattr(t, "ad_id", None)}
    if len(ad_ids) == 1:
        key = objekt_vertriebler_key(next(iter(ad_ids)))
        if vorlage_vorhanden(session, key):
            return key
    return OBJEKT_VORLAGE


def vertriebler_vorlage_sicherstellen(session: Session, benutzer) -> bool:
    """Neue Vertriebler erhalten automatisch eine Kopie der Standard-
    Terminbestätigung (Quelle standard_kopie). True = angelegt."""
    if benutzer is None:
        return False
    key = vertriebler_key(benutzer.id)
    if vorlage_vorhanden(session, key):
        return False
    betreff, text = vorlage_laden(session, TERMIN_VORLAGE)
    vorlage_speichern(session, key, betreff, text, quelle="standard_kopie")
    return True


def vorlagen_katalog(session: Session) -> list[dict]:
    """Baum des Editors: Kategorien mit Einträgen {key, name, vorhanden, quelle,
    benutzer_id, hv}. Die Oberkategorie Terminbestätigung enthält „Standard“ und
    je aktivem Vertriebler eine Vorlage; ausgeblendete Vorlagen fehlen."""
    katalog = []
    zugeordnet: set[str] = set()
    hv_ids = {p.benutzer_id for p in session.query(AdProfil.benutzer_id)
              .filter(AdProfil.terminiert_selbst.is_(True))}
    for kat_key, kat_name, keys in KATEGORIEN:
        eintraege = []
        for key in keys:
            if key not in VORLAGEN_START or key in VORLAGEN_AUSGEBLENDET:
                continue
            zugeordnet.add(key)
            # v31: in der Oberkategorie Terminbestätigung heißt die Objekt-Vorlage
            # „Mehrere Objekte“ (neben „Standard“ und den Vertriebler-Vorlagen)
            name = ("Standard" if key == TERMIN_VORLAGE
                    else "Mehrere Objekte" if key == OBJEKT_VORLAGE
                    else VORLAGEN_START[key][0])
            eintraege.append({"key": key, "name": name,
                              "vorhanden": True, "quelle": vorlage_quelle(session, key),
                              "benutzer_id": None, "hv": False})
        if kat_key == "terminbestaetigung":
            for person in vertriebler_liste(session):
                key = vertriebler_key(person.id)
                eintraege.append({"key": key, "name": f"Terminbestätigung – {person.name}",
                                  "vorhanden": vorlage_vorhanden(session, key),
                                  "quelle": vorlage_quelle(session, key),
                                  "benutzer_id": person.id, "hv": person.id in hv_ids})
        if kat_key == "sonstige":
            for key, (name, _, _) in VORLAGEN_START.items():
                if key not in zugeordnet and key not in VORLAGEN_AUSGEBLENDET:
                    eintraege.append({"key": key, "name": name, "vorhanden": True,
                                      "quelle": vorlage_quelle(session, key),
                                      "benutzer_id": None, "hv": False})
        if eintraege or kat_key != "sonstige":
            katalog.append({"key": kat_key, "name": kat_name, "eintraege": eintraege,
                            "aufklappbar": kat_key == "terminbestaetigung"})
    return katalog


# --- Rahmen / individueller Block (Phase 142) -------------------------------------------

def block_trennen(text: str) -> tuple[str, str, str]:
    """(vor, block, nach): block = Platzhalter {vertriebler_block} oder der
    markierte Bereich inkl. Marker; ohne beides ist block leer."""
    text = text or ""
    start = text.find(BLOCK_START)
    if start >= 0:
        ende = text.find(BLOCK_ENDE, start)
        if ende >= 0:
            ende += len(BLOCK_ENDE)
            return text[:start], text[start:ende], text[ende:]
    pos = text.find(BLOCK_PLATZHALTER)
    if pos >= 0:
        return text[:pos], BLOCK_PLATZHALTER, text[pos + len(BLOCK_PLATZHALTER):]
    return text, "", ""


def rahmen_uebernehmen(session: Session, quell_key: str) -> int:
    """„Rahmen für alle Terminbestätigungen übernehmen“: Betreff und alles
    außer dem individuellen Block der Quell-Vorlage in alle Vorlagen der
    Oberkategorie schreiben; individuelle Blöcke bleiben (ohne Block bekommt
    die Zielvorlage den Platzhalter). Liefert die Anzahl geschriebener Vorlagen."""
    betreff, text = vorlage_laden(session, quell_key)
    vor, block, nach = block_trennen(text)
    if not block:
        vor, block, nach = text, BLOCK_PLATZHALTER, ""
        if not vor.endswith("\n"):
            vor += "\n\n"
    ziele = [TERMIN_VORLAGE] + [vertriebler_key(p.id) for p in vertriebler_liste(session)]
    anzahl = 0
    for ziel in ziele:
        if ziel == quell_key:
            continue
        _, ziel_text = vorlage_laden(session, ziel) if vorlage_vorhanden(session, ziel) else ("", "")
        _, ziel_block, _ = block_trennen(ziel_text)
        neu = vor + (ziel_block or BLOCK_PLATZHALTER) + nach
        vorlage_speichern(session, ziel, betreff, neu,
                          quelle=vorlage_quelle(session, ziel) or "editor")
        anzahl += 1
    return anzahl


def ziel_anzahl(session: Session, quell_key: str) -> int:
    return len([k for k in [TERMIN_VORLAGE] + [vertriebler_key(p.id) for p in vertriebler_liste(session)]
                if k != quell_key])


# --- Werte, Bausteine, Rendern ----------------------------------------------------------

def _esc(wert) -> str:
    return html_modul.escape(str(wert or ""), quote=False)


def bild_pfad(benutzer) -> Path | None:
    """Pfad des Benutzerbilds (relativ zu DATA_ORDNER), None ohne Datei."""
    rel = (getattr(benutzer, "bild_datei", "") or "").strip()
    if not rel:
        return None
    pfad = (config.DATA_ORDNER / rel).resolve()
    try:
        pfad.relative_to(config.DATA_ORDNER.resolve())
    except ValueError:
        return None
    return pfad if pfad.exists() and pfad.suffix.lower() in BILD_ENDUNGEN else None


def bild_mime(pfad: Path) -> str:
    return BILD_ENDUNGEN.get(pfad.suffix.lower(), "application/octet-stream")


def vertriebler_block_html(benutzer, bild_src: str | None = None) -> str:
    """Individueller Block: Bild (cid:vertriebler-<id>, im Editor eine URL),
    Name, Telefon, E-Mail – als Tabelle, damit Outlook es sauber setzt.
    v33 (PLAN_V20 Phase 175): ohne Infotext (Benutzer.infotext wird nicht mehr gelesen)."""
    if benutzer is None:
        return ""
    bild = bild_pfad(benutzer)
    zeilen = [f"<strong>{_esc(benutzer.name)}</strong>"]
    if getattr(benutzer, "telefon", ""):
        zeilen.append(f"Telefon: {_esc(benutzer.telefon)}")
    if getattr(benutzer, "email", ""):
        zeilen.append(f"E-Mail: <a href=\"mailto:{_esc(benutzer.email)}\">{_esc(benutzer.email)}</a>")
    text_html = "<br>".join(zeilen)
    bild_html = ""
    if bild is not None:
        src = bild_src or f"cid:{CID_PRAEFIX}{benutzer.id}"
        bild_html = (f'<td style="vertical-align:top;padding-right:14px"><img src="{src}" '
                     f'alt="{_esc(benutzer.name)}" width="120" style="width:120px;border-radius:8px"></td>')
    return ('<table class="lm-vertriebler" cellpadding="0" cellspacing="0" border="0" '
            'style="border-collapse:collapse;margin:8px 0"><tr>'
            f'{bild_html}<td style="vertical-align:top">{text_html}</td></tr></table>')


def vertriebler_block_text(benutzer) -> str:
    """Textfassung des Blocks (Name, Telefon, E-Mail) – v33: ohne Infotext (Phase 175)."""
    if benutzer is None:
        return ""
    zeilen = [benutzer.name]
    if getattr(benutzer, "telefon", ""):
        zeilen.append(f"Telefon: {benutzer.telefon}")
    if getattr(benutzer, "email", ""):
        zeilen.append(f"E-Mail: {benutzer.email}")
    return "\n".join(zeilen)


def sparten_hinweise_punkte(sparten: list[str], langnamen: dict | None = None) -> list[tuple[str, list[str]]]:
    """[(Sparten-Name, Punkte)] aus dem Blatt Terminhinweise – Dubletten über
    alle Sparten entfernt, Sparten ohne Punkte weggelassen. v31 (Phase 156): die
    Zwischenüberschrift ist die Langform (sparten.langname, Parameter sparten_langnamen)."""
    from app import leadmanagement_logik
    logik = leadmanagement_logik.hole_logik()
    gesehen: set[str] = set()
    ergebnis = []
    for sparte in sparten_modul.codes(sparten):
        punkte = []
        for punkt in logik.hinweise_der_sparte(sparte):
            schluessel = punkt.strip().lower()
            if schluessel in gesehen:
                continue
            gesehen.add(schluessel)
            punkte.append(punkt)
        if punkte:
            ergebnis.append((sparten_modul.langname(sparte, langnamen), punkte))
    return ergebnis


def sparten_hinweise_html(sparten: list[str], langnamen: dict | None = None) -> str:
    bloecke = sparten_hinweise_punkte(sparten, langnamen)
    if not bloecke:
        return ""
    teile = [f"<p>{_esc(SPARTEN_EINLEITUNG)}</p>"]
    for name, punkte in bloecke:
        if len(bloecke) > 1:
            teile.append(f"<p><strong>{_esc(name)}</strong></p>")
        teile.append("<ul>" + "".join(f"<li>{_esc(p)}</li>" for p in punkte) + "</ul>")
    return "".join(teile)


def sparten_hinweise_text(sparten: list[str], langnamen: dict | None = None) -> str:
    bloecke = sparten_hinweise_punkte(sparten, langnamen)
    if not bloecke:
        return ""
    zeilen = [SPARTEN_EINLEITUNG]
    for name, punkte in bloecke:
        if len(bloecke) > 1:
            zeilen += ["", name]
        zeilen += [f"- {p}" for p in punkte]
    return "\n".join(zeilen)


def langnamen(session: Session) -> dict:
    """v31 (Phase 156): Langformen der Sparten inkl. Übersteuerung aus dem Parameter
    sparten_langnamen (Lead-Einstellungen)."""
    return sparten_modul.langnamen_laden(_parameter(session, "sparten_langnamen", ""))


def sparten_codes_fuer(session: Session, vorgang: Vorgang | None, kunde: Kunde | None,
                       objekt=None, termin: VotTermin | None = None, termine=None) -> list[str]:
    """Sparten-Kürzel für eine Mail: bei einer Objektliste die Vereinigung der
    Objekt-Interessen aller Termine, sonst die Interessen des Objekts (Termin oder
    übergeben), sonst die Kundeninteressen (= Vereinigung aller Objekte, hauptobjekt_sync)."""
    from app import objekte as objekte_modul
    from app.models import VorgangObjekt
    codes: list[str] = []
    if termine:
        for t in termine:
            o = session.get(VorgangObjekt, t.objekt_id) if getattr(t, "objekt_id", None) else None
            codes.extend(objekte_modul.interessen_liste(o))
    elif objekt is not None:
        codes = objekte_modul.interessen_liste(objekt)
    elif termin is not None and getattr(termin, "objekt_id", None):
        codes = objekte_modul.interessen_liste(session.get(VorgangObjekt, termin.objekt_id))
    if not codes and kunde is not None:
        codes = sparten_modul.codes(kunde.interesse)
    return sparten_modul.codes(codes)


def objektliste_html(session: Session, termine, langnamen_map: dict | None = None,
                     benutzer_map: dict | None = None) -> str:
    """v31 (Phase 153): Platzhalter {objektliste} – je Objekttermin eine Zeile mit
    Bezeichnung, Adresse, Datum, Uhrzeit (Dauer) und Vertriebler als Tabelle (Outlook-
    tauglich); html_zu_text macht daraus lesbare Zeilen für den Textteil."""
    from app import objekte as objekte_modul
    from app.models import VorgangObjekt
    if not termine:
        return ""
    benutzer_map = benutzer_map or {}
    zeilen = []
    for t in sorted(termine, key=lambda x: (x.beginn or datetime.max, x.id or 0)):
        objekt = session.get(VorgangObjekt, t.objekt_id) if getattr(t, "objekt_id", None) else None
        ort = objekte_modul.ausfuehrungsort(session, termin=t)
        bezeichnung = (objekt.bezeichnung if objekt is not None and objekt.bezeichnung
                       else ort.get("bezeichnung") or "Objekt")
        adresse = (t.adresse or "").strip() or ort.get("einzeilig", "")
        if objekt is not None:
            sparten_text = sparten_modul.sparten_text(objekte_modul.interessen_liste(objekt),
                                                      langnamen=langnamen_map)
        else:
            sparten_text = ""
        ad = benutzer_map.get(t.ad_id) if t.ad_id in benutzer_map else (
            session.get(Benutzer, t.ad_id) if t.ad_id else None)
        dauer = int((t.ende - t.beginn).total_seconds() // 60) if t.beginn and t.ende else 90
        zeit = (f"{t.beginn:%d.%m.%Y}, {t.beginn:%H:%M} Uhr (ca. {dauer} Minuten)"
                if t.beginn else "Termin folgt")
        zeilen.append(
            "<tr>"
            f"<td style=\"vertical-align:top;padding:4px 10px 4px 0\"><strong>{_esc(bezeichnung)}</strong>"
            + (f"<br><span>{_esc(sparten_text)}</span>" if sparten_text else "") + "</td>"
            f"<td style=\"vertical-align:top;padding:4px 10px 4px 0\">{_esc(adresse)}</td>"
            f"<td style=\"vertical-align:top;padding:4px 10px 4px 0\">{_esc(zeit)}</td>"
            f"<td style=\"vertical-align:top;padding:4px 0\">{_esc(ad.name if ad else 'Ihr Friondo-Berater')}"
            + (f" ({_esc(ad.telefon)})" if ad is not None and getattr(ad, 'telefon', '') else "") + "</td>"
            "</tr>")
    return ('<table class="lm-objektliste" cellpadding="0" cellspacing="0" border="0" '
            'style="border-collapse:collapse;margin:8px 0">'
            '<tr><th style="text-align:left;padding:4px 10px 4px 0">Objekt</th>'
            '<th style="text-align:left;padding:4px 10px 4px 0">Adresse</th>'
            '<th style="text-align:left;padding:4px 10px 4px 0">Termin</th>'
            '<th style="text-align:left;padding:4px 0">Ihr Berater</th></tr>'
            + "".join(zeilen) + "</table>")


def termine_datum_text(termine) -> str:
    """Datum einer Objektliste: ein Tag → „14.10.2026“, mehrere → „14.10.2026 – 15.10.2026“."""
    tage = sorted({t.beginn.date() for t in (termine or []) if t.beginn})
    if not tage:
        return ""
    if len(tage) == 1:
        return tage[0].strftime("%d.%m.%Y")
    return f"{tage[0]:%d.%m.%Y} – {tage[-1]:%d.%m.%Y}"


def objekttermine_aktiv(session: Session, vorgang: Vorgang, status=("geplant", "bestaetigt")) -> list[VotTermin]:
    """Aktive Vor-Ort-Termine des Vorgangs (ein Termin je Objekt), chronologisch –
    Grundlage der Objekt-Terminbestätigung und ihrer ICS-Anhänge."""
    return (session.query(VotTermin)
            .filter(VotTermin.vorgang_id == vorgang.id, VotTermin.typ == "vot",
                    VotTermin.status.in_(tuple(status)), VotTermin.beginn.isnot(None))
            .order_by(VotTermin.beginn, VotTermin.id).all())


def werte_fuer(session: Session, vorgang: Vorgang,
               termin: VotTermin | None = None, vorschau: bool = False,
               kunde: Kunde | None = None, objekt=None, termine=None,
               benutzer=None) -> dict:
    """Platzhalterwerte. v29: zusätzlich adresse, sparten_hinweise (HTML),
    vertriebler_block (HTML), vertriebler_vorname, vertriebler_email;
    vorschau=True verweist das Bild auf die Benutzerbild-Route statt cid:.
    v31 (Phase 153/156/158): {sparten} und {sparten_interesse} in Langform (Objekt-
    Interessen des Termins/Objekts, sonst Kundeninteressen), {objektadresse} =
    Adresse des Objekts (Ein-Objekt = Kundenadresse), {objektliste} für die Objekt-
    Terminbestätigung (termine = alle Objekttermine), {vorname}, {nachname},
    {absender} = handelnder Benutzer, sonst Leadmanager, sonst „Ihr Friondo-Team“."""
    from app import objekte as objekte_modul
    if kunde is None:
        kunde = session.get(Kunde, vorgang.kunde_id) if vorgang.kunde_id else None
    quelle = session.get(LeadQuelle, vorgang.quelle_id) if vorgang.quelle_id else None
    leadmanager = (session.get(Benutzer, vorgang.leadmanager_id)
                   if vorgang.leadmanager_id else None)
    if termine and termin is None:
        termin = termine[0]
    vertriebler = (session.get(Benutzer, termin.ad_id)
                   if termin is not None and termin.ad_id else None)
    if kunde is None:
        return {}
    if kunde.anrede == "Frau":
        briefanrede = f"Sehr geehrte Frau {kunde.nachname}"
    elif kunde.anrede == "Herr":
        briefanrede = f"Sehr geehrter Herr {kunde.nachname}"
    else:
        briefanrede = "Guten Tag"
    from app.leadmanagement import wunschzeiten_liste
    wunschzeiten = ", ".join(wunschzeiten_liste(vorgang))
    absender = _absender(session)
    namen = langnamen(session)
    codes = sparten_codes_fuer(session, vorgang, kunde, objekt=objekt, termin=termin, termine=termine)
    # Objektadresse: Objekt des Termins bzw. das übergebene Objekt, sonst Hauptobjekt/Kunde
    if objekt is not None and termin is None:
        ort = objekte_modul.ausfuehrungsort(session, objekt_id=objekt.id, vorgang=vorgang, kunde=kunde)
    else:
        ort = objekte_modul.ausfuehrungsort(session, termin=termin, vorgang=vorgang, kunde=kunde)
    objektadresse = ort.get("einzeilig", "")
    adresse = (termin.adresse if termin is not None and termin.adresse else "") or objektadresse
    if not adresse:
        adresse = ", ".join(t for t in ((kunde.strasse or "").strip(),
                                         f"{(kunde.plz or '').strip()} {(kunde.ort or '').strip()}".strip())
                            if t)
    bild_src = (f"/lead-management/benutzer/{vertriebler.id}/bild"
                if vorschau and vertriebler is not None else None)
    if termine:
        termin_datum = termine_datum_text(termine)
    else:
        termin_datum = termin.beginn.strftime("%d.%m.%Y") if termin and termin.beginn else ""
    absender_name = (benutzer.name if benutzer is not None and getattr(benutzer, "name", "")
                     else (leadmanager.name if leadmanager else "Ihr Friondo-Team"))
    return {
        "briefanrede": briefanrede,
        "name": kunde.anzeige_name,
        "vorname": kunde.vorname or "",
        "nachname": kunde.nachname or "",
        "sparten": sparten_modul.sparten_text(codes, langnamen=namen) or "Ihre Anfrage",
        "sparten_interesse": sparten_modul.sparten_interesse(codes, langnamen=namen),
        "quelle": quelle.name if quelle else "",
        "termin_datum": termin_datum,
        "termin_uhrzeit": termin.beginn.strftime("%H:%M") if termin and termin.beginn else "",
        "termin_dauer": str(int((termin.ende - termin.beginn).total_seconds() // 60))
                        if termin and termin.beginn and termin.ende else "90",
        "vertriebler": vertriebler.name if vertriebler else "Ihr Friondo-Berater",
        "vertriebler_telefon": f"({vertriebler.telefon})"
                               if vertriebler and vertriebler.telefon else "",
        "leadmanager": leadmanager.name if leadmanager else "das Friondo-Team",
        "leadmanager_telefon": f"({leadmanager.telefon})"
                               if leadmanager and leadmanager.telefon else "",
        "wunschzeiten": wunschzeiten,
        "link_rueckruf": (f"mailto:{absender}?subject="
                          f"R%C3%BCckruf%20V{vorgang.id}"),
        # v23 (Phase 104): Rückruf-Telefon (Leadmanager, sonst Parameter
        # rueckruf_telefon), Kollege + Buchungslink für Online-Termine (F12)
        "rueckruf_telefon": (leadmanager.telefon if leadmanager and leadmanager.telefon
                             else _parameter(session, "rueckruf_telefon")),
        "kollege": vertriebler.name if vertriebler else "einem Kollegen",
        "buchungslink": (getattr(vertriebler, "buchungslink", "") or "")
                        if vertriebler else "",
        # v29 (Phase 142)
        "adresse": adresse,
        "sparten_hinweise": sparten_hinweise_html(codes, namen),
        "vertriebler_block": vertriebler_block_html(vertriebler, bild_src),
        "vertriebler_vorname": (getattr(vertriebler, "vorname", "") or "") if vertriebler else "",
        "vertriebler_email": (vertriebler.email or "") if vertriebler else "",
        # v31 (Phase 153/158)
        "objektadresse": objektadresse,
        "objektliste": objektliste_html(session, termine, namen) if termine else "",
        "absender": absender_name,
    }


def _parameter(session: Session, name: str, standard: str = "") -> str:
    from app import leadmanagement as kern
    return kern.parameter_holen(session, name, standard)


def absender(session: Session) -> str:
    """v29: Absender aller Lead-Mails aus absender_lead_mails (Standard
    termin@friondo.de) – ohne Fallback auf ein anderes Postfach."""
    from app import leadmanagement as kern
    return (kern.parameter_holen(session, PARAMETER_ABSENDER, ABSENDER_STANDARD)
            or ABSENDER_STANDARD).strip()


def _absender(session: Session) -> str:
    return absender(session)


def _einsetzen(text: str, werte: dict) -> str:
    for schluessel, wert in werte.items():
        text = text.replace("{" + schluessel + "}", str(wert))
    return text


def _als_html(text: str) -> str:
    return "<p>" + html_modul.escape(text).replace("\n\n", "</p><p>") \
        .replace("\n", "<br>") + "</p>"


_HTML_MUSTER = re.compile(r"<(p|br|div|table|html|body|span|strong|b|i|em|ul|ol|li|h\d|img|a)\b",
                          re.IGNORECASE)


def ist_html(text: str) -> bool:
    """Vorlagentext mit HTML-Auszeichnung (Zulieferung/Editor) oder reiner Text?"""
    return bool(_HTML_MUSTER.search(text or ""))


def html_aus_vorlage(text: str, werte: dict) -> str:
    """Vorlagentext (HTML oder Text) + Werte → Mail-HTML. Textwerte werden
    maskiert, die HTML-Bausteine (sparten_hinweise, vertriebler_block) roh
    eingesetzt; bei Textvorlagen stehen die Bausteine nicht in einem <p>."""
    werte_html = {k: (v if k in _HTML_WERTE else _esc(v)) for k, v in werte.items()}
    if ist_html(text):
        return _einsetzen(text, werte_html)
    html = _als_html(text)
    for name in _HTML_WERTE:
        html = html.replace(f"<p>{{{name}}}</p>", f"{{{name}}}")
    return _einsetzen(html, werte_html)


def html_zu_text(html: str) -> str:
    """Mail-HTML → lesbarer Text (HV-Vorschau, .txt-Download)."""
    text = re.sub(r"(?is)<(script|style)[^>]*>.*?</\1>", "", html or "")
    text = re.sub(r"(?i)<br\s*/?>", "\n", text)
    text = re.sub(r"(?i)<li[^>]*>", "- ", text)
    text = re.sub(r"(?i)</(p|li|tr|div|h\d|ul|ol|table)>", "\n", text)
    text = re.sub(r"(?i)</td>", " ", text)
    text = re.sub(r"<[^>]+>", "", text)
    text = html_modul.unescape(text)
    text = re.sub(r"[ \t]+\n", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def _ics_text(text: str) -> str:
    """Textwert nach RFC 5545 maskieren (Backslash, Semikolon, Komma, Zeilen)."""
    return ((text or "").replace("\\", "\\\\").replace(";", "\\;")
            .replace(",", "\\,").replace("\r\n", "\n").replace("\n", "\\n"))


def _ics_falten(zeile: str, breite: int = 74) -> str:
    """Zeilen länger als 75 Zeichen falten (Fortsetzung mit Leerzeichen)."""
    if len(zeile) <= breite:
        return zeile
    teile = [zeile[:breite]]
    rest = zeile[breite:]
    while rest:
        teile.append(" " + rest[:breite - 1])
        rest = rest[breite - 1:]
    return "\r\n".join(teile)


ICS_TYP_TITEL = {"vot": "Vor-Ort-Termin", "telefon": "Telefongespräch",
                 "online": "Online-Termin (Teams)"}


def ics_erstellen(session: Session, termin: VotTermin, vorgang: Vorgang,
                  methode: str = "REQUEST") -> str | None:
    """ICS-Anhang (Organizer = Absender-Postfach). v23 (Phase 108, E4):
    UID aus vot_termine.ics_uid (beim ersten Mal friondo-vot-{id}@friondo.de),
    SEQUENCE aus ics_sequence, Titel mit Sparten, LOCATION Kundenadresse,
    DESCRIPTION mit Berater + Telefon, Absage-Hinweis und Rückruf-Telefon,
    VALARM 24 h; methode="CANCEL" erzeugt die Storno-ICS (STATUS:CANCELLED,
    gleiche UID). Bestehende Aufrufer (rendern) bleiben unverändert."""
    from app import config
    kunde = session.get(Kunde, vorgang.kunde_id)
    if termin is None or termin.beginn is None or kunde is None:
        return None
    methode = "CANCEL" if str(methode).upper() == "CANCEL" else "REQUEST"
    ordner = config.DATA_ORDNER / "lead_ics"
    ordner.mkdir(parents=True, exist_ok=True)
    absender = _absender(session)
    ende = termin.ende or termin.beginn
    if not getattr(termin, "ics_uid", None):
        termin.ics_uid = f"friondo-vot-{termin.id}@friondo.de"
        if termin in session:
            session.flush()
    sequence = int(getattr(termin, "ics_sequence", 0) or 0)
    # v31 (Phase 156): Langform im Kundenkalender („Wärmepumpe und Photovoltaik“ statt
    # „WP+PV“) – Interessen des Objekts des Termins, sonst des Kunden
    sparten = (sparten_modul.sparten_text(
        sparten_codes_fuer(session, vorgang, kunde, termin=termin), langnamen=langnamen(session))
        or "Ihre Anfrage")
    typ = getattr(termin, "typ", "vot") or "vot"
    titel = f"{ICS_TYP_TITEL.get(typ, 'Vor-Ort-Termin')} Friondo – {sparten}"
    # v31 (Phase 153): bei mehreren Objekten trägt der Titel die Objektbezeichnung
    objekt_text = ""
    if getattr(termin, "objekt_id", None):
        from app import objekte as objekte_modul
        ort = objekte_modul.ausfuehrungsort(session, termin=termin, vorgang=vorgang, kunde=kunde)
        if ort.get("mehrere_objekte") and ort.get("bezeichnung"):
            objekt_text = ort["bezeichnung"]
            titel += f" ({objekt_text})"
    if methode == "CANCEL":
        titel = "Abgesagt: " + titel
    berater = session.get(Benutzer, termin.ad_id) if termin.ad_id else None
    leadmanager = (session.get(Benutzer, vorgang.leadmanager_id)
                   if vorgang.leadmanager_id else None)
    rueckruf = ((leadmanager.telefon if leadmanager and leadmanager.telefon else "")
                or _parameter(session, "rueckruf_telefon") or "")
    adresse = termin.adresse or ""
    if typ == "vot" and not adresse:
        # v31 (Phase 153): Ausführungsort = Objektadresse (Hauptobjekt = Kundenadresse)
        from app import objekte as objekte_modul
        adresse = objekte_modul.ausfuehrungsort(session, termin=termin, vorgang=vorgang,
                                                kunde=kunde).get("einzeilig", "")
    zeilen = []
    if methode == "CANCEL":
        zeilen.append("Dieser Termin wurde abgesagt. Wir melden uns mit einem neuen Vorschlag.")
    if berater is not None:
        zeilen.append(f"Ihr Berater: {berater.name}"
                      + (f", Telefon {berater.telefon}" if berater.telefon else ""))
    if typ == "vot":
        zeilen.append("Bitte halten Sie Heizkostenabrechnung, Stromrechnung und "
                      "Grundriss bereit (Zugang zu Heizungsraum und Zählerschrank).")
    if methode != "CANCEL":
        zeilen.append("Falls Sie den Termin nicht wahrnehmen können, sagen Sie bitte "
                      "rechtzeitig ab" + (f": Telefon {rueckruf}" if rueckruf else "")
                      + f" oder per E-Mail an {absender}.")
    elif rueckruf:
        zeilen.append(f"Rückfragen: Telefon {rueckruf} oder per E-Mail an {absender}.")
    beschreibung = "\n".join(zeilen)
    inhalt_zeilen = [
        "BEGIN:VCALENDAR",
        "PRODID:-//Friondo//Angebotstool//DE",
        "VERSION:2.0",
        f"METHOD:{methode}",
        "BEGIN:VEVENT",
        f"UID:{termin.ics_uid}",
        f"SEQUENCE:{sequence}",
        f"DTSTAMP:{datetime.now().strftime('%Y%m%dT%H%M%S')}",
        f"DTSTART:{termin.beginn.strftime('%Y%m%dT%H%M%S')}",
        f"DTEND:{ende.strftime('%Y%m%dT%H%M%S')}",
        f"SUMMARY:{_ics_text(titel)}",
        f"LOCATION:{_ics_text(adresse)}",
        f"DESCRIPTION:{_ics_text(beschreibung)}",
        f"STATUS:{'CANCELLED' if methode == 'CANCEL' else 'CONFIRMED'}",
        f"ORGANIZER;CN=Friondo:mailto:{absender}",
        f"ATTENDEE;CN={_ics_text(kunde.anzeige_name)};RSVP=FALSE:mailto:{kunde.email}",
    ]
    if methode != "CANCEL":
        inhalt_zeilen += ["BEGIN:VALARM", "TRIGGER:-PT24H", "ACTION:DISPLAY",
                          f"DESCRIPTION:{_ics_text('Erinnerung: ' + titel)}",
                          "END:VALARM"]
    inhalt_zeilen += ["END:VEVENT", "END:VCALENDAR", ""]
    inhalt = "\r\n".join(_ics_falten(z) for z in inhalt_zeilen)
    name = (f"vot_{termin.id or 'vorschau'}.ics" if methode != "CANCEL"
            else f"vot_{termin.id or 'vorschau'}_storno.ics")
    pfad = ordner / name
    pfad.write_text(inhalt, encoding="utf-8")
    return str(pfad)


def verwendeter_vorlagen_key(session: Session, vorlage_key: str, termin: VotTermin | None = None,
                             termine=None) -> str:
    """Versandregel Phase 142/v31: terminbestaetigung → Vorlage des zugewiesenen
    Vertrieblers des Termins (sonst Standard); terminbestaetigung_objekte → Vertriebler-
    Variante, wenn alle Objekttermine denselben Vertriebler haben und sie existiert."""
    if vorlage_key == TERMIN_VORLAGE and termin is not None:
        return terminbestaetigung_key(session, termin.ad_id)[0]
    if vorlage_key == OBJEKT_VORLAGE:
        return objekt_vorlage_key(session, termine or ([termin] if termin is not None else []))
    return vorlage_key


def fehlende_pflichtdaten(session: Session, vorlage_key: str, vorgang: Vorgang,
                          termin: VotTermin | None = None, kunde: Kunde | None = None,
                          termine=None) -> list[str]:
    """v31 (Phase 158, Vertrag mit K): was der Vorlage für einen Versand fehlt –
    E-Mail-Adresse, Termin (Terminvorlagen), Objekttermine (Objektvorlage),
    Buchungslink des Kollegen (Online-Einladung). Leer = sendbar."""
    if kunde is None:
        kunde = session.get(Kunde, vorgang.kunde_id) if vorgang.kunde_id else None
    fehlt: list[str] = []
    if kunde is None:
        return ["Kunde"]
    if not (kunde.email or "").strip():
        fehlt.append("E-Mail-Adresse des Kunden")
    basis = vorlage_key
    if ist_vertriebler_key(vorlage_key):
        basis = TERMIN_VORLAGE
    elif objekt_vertriebler_id_aus_key(vorlage_key) is not None:
        basis = OBJEKT_VORLAGE
    if basis == OBJEKT_VORLAGE:
        if not termine and termin is None:
            fehlt.append("Objekttermine (kein aktiver Vor-Ort-Termin)")
    elif basis in TERMIN_PFLICHT_VORLAGEN:
        if termin is None or termin.beginn is None:
            fehlt.append("Termin (kein aktiver Vor-Ort-Termin)")
    elif basis == "online_termin_einladung":
        person = session.get(Benutzer, termin.ad_id) if termin is not None and termin.ad_id else None
        if person is None or not (getattr(person, "buchungslink", "") or "").strip():
            fehlt.append("Buchungslink des Kollegen (Online-Termin)")
    return fehlt


def vorlage_rendern(session: Session, vorlage_key: str, vorgang: Vorgang,
                    termin: VotTermin | None = None, sparte: str = "",
                    vorschau: bool = False, text_vorgabe: tuple[str, str] | None = None,
                    kunde: Kunde | None = None, objekt=None, benutzer=None,
                    termine=None) -> tuple[str, str, list[str]]:
    """(Betreff, Mail-HTML, fehlende Pflichtdaten). Versandregel Phase 142:
    terminbestaetigung → Vorlage des zugewiesenen Vertrieblers des Termins,
    sonst Standard. text_vorgabe=(betreff, text) rendert ungespeicherten
    Editor-Text (Vorschau). v31 (Vertrag mit K, Phase 158): objekt (Platzhalter aus
    dem Objekt), benutzer ({absender}), termine (Objektliste); die dritte Rückgabe ist
    die Liste fehlender Pflichtdaten (leer = sendbar) – den verwendeten Vorlagen-Key
    liefert verwendeter_vorlagen_key()."""
    if vorlage_key == OBJEKT_VORLAGE and termine is None:
        termine = objekttermine_aktiv(session, vorgang) if vorgang.id else ([termin] if termin else [])
        if termin is not None and termin not in termine and getattr(termin, "beginn", None):
            termine = sorted(termine + [termin], key=lambda t: (t.beginn or datetime.max))
    key = verwendeter_vorlagen_key(session, vorlage_key, termin, termine)
    if text_vorgabe is not None:
        betreff, text = text_vorgabe
    else:
        betreff, text = vorlage_laden(session, key, sparte)
    werte = werte_fuer(session, vorgang, termin, vorschau=vorschau, kunde=kunde,
                       objekt=objekt, termine=termine if vorlage_key == OBJEKT_VORLAGE else None,
                       benutzer=benutzer)
    fehlt = fehlende_pflichtdaten(session, vorlage_key, vorgang, termin, kunde=kunde,
                                  termine=termine if vorlage_key == OBJEKT_VORLAGE else None)
    return _einsetzen(betreff, werte)[:300], html_aus_vorlage(text, werte), fehlt


def anhang_pfade(anhang_pfad: str | None) -> list[str]:
    """v31 (Phase 153): mehrere ICS in einer Mail – anhang_pfad trägt die Pfade mit
    „;“ getrennt (eine Datei je Objekttermin, eigene UID)."""
    return [p.strip() for p in (anhang_pfad or "").split(";") if p.strip()]


def rendern(session: Session, eintrag: KommunikationLog) -> bool:
    """Betreff/HTML in den Eintrag rendern; False bei fehlendem Vorgang. v31:
    Einträge mit festem Text (kanal mail_fest, Kartei-Dialog) behalten Betreff/Text;
    Objekt-Terminbestätigung rendert die Objektliste und hängt je Objekttermin ein ICS
    an; {absender} = Ersteller des Eintrags."""
    vorgang = session.get(Vorgang, eintrag.vorgang_id)
    if vorgang is None:
        return False
    termin = session.get(VotTermin, eintrag.termin_id) if eintrag.termin_id else None
    kunde = session.get(Kunde, vorgang.kunde_id)
    if not (getattr(eintrag, "absender", "") or ""):
        eintrag.absender = _absender(session)
    if (eintrag.kanal or "") == KANAL_FEST and eintrag.betreff and eintrag.body_html:
        if (eintrag.vorlage_key in ("terminbestaetigung", "terminaenderung") or ist_vertriebler_key(eintrag.vorlage_key)) \
                and termin is not None and not eintrag.anhang_pfad:
            eintrag.anhang_pfad = ics_erstellen(session, termin, vorgang)
        return True
    sparte = ""
    if kunde is not None and kunde.interesse:
        sparte = kunde.interesse.split(",")[0].strip()
    ersteller = session.get(Benutzer, eintrag.erstellt_von) if getattr(eintrag, "erstellt_von", None) else None
    termine = None
    if eintrag.vorlage_key == OBJEKT_VORLAGE:
        termine = objekttermine_aktiv(session, vorgang)
        if termin is not None and termin not in termine and termin.beginn is not None:
            termine = sorted(termine + [termin], key=lambda t: (t.beginn or datetime.max))
    betreff, body_html, _ = vorlage_rendern(session, eintrag.vorlage_key, vorgang, termin, sparte,
                                            benutzer=ersteller, termine=termine)
    eintrag.betreff = betreff
    eintrag.body_html = body_html
    if eintrag.vorlage_key == OBJEKT_VORLAGE and termine:
        pfade = [ics_erstellen(session, t, vorgang) for t in termine]
        eintrag.anhang_pfad = ";".join(p for p in pfade if p)[:500]
    elif eintrag.vorlage_key in ("terminbestaetigung", "terminaenderung") \
            and termin is not None:
        eintrag.anhang_pfad = ics_erstellen(session, termin, vorgang)
    return True


def inline_bilder_aus_html(session: Session, body_html: str) -> list[tuple[str, Path, str]]:
    """CID-Verweise cid:vertriebler-<id> im Mail-HTML → [(cid, Pfad, MIME)] der
    Benutzerbilder (Bild als CID-Anhang-Verweis, aufgelöst erst beim Versand)."""
    bilder = []
    for benutzer_id in sorted({int(x) for x in re.findall(rf"cid:{CID_PRAEFIX}(\d+)", body_html or "")}):
        person = session.get(Benutzer, benutzer_id)
        pfad = bild_pfad(person) if person is not None else None
        if pfad is not None:
            bilder.append((f"{CID_PRAEFIX}{benutzer_id}", pfad, bild_mime(pfad)))
    return bilder


def ics_methode(inhalt: bytes | str) -> str:
    """MIME-Methode eines ICS-Inhalts (REQUEST | CANCEL) aus der METHOD-Zeile."""
    text = inhalt.decode("utf-8", "ignore") if isinstance(inhalt, bytes) else (inhalt or "")
    return "CANCEL" if "METHOD:CANCEL" in text.upper() else "REQUEST"


# --- Versand über Graph (ohne Fallback) ---------------------------------------------------

def antwort_adressen(session: Session, vorgang: Vorgang | None, absender_adresse: str) -> list[str]:
    """Nachtrag 08.10.2026 (Antwort Andreas): Reply-To der Lead-Mails = E-Mail des
    zuständigen Leadmanagers (vorgang.leadmanager_id → Benutzer.email, nur wenn
    gesetzt) UND der Absender termin@ – Antworten erreichen den Leadmanager, der
    Lauf lead-mail-abruf sieht sie weiterhin in termin@. Wird VOR der Freigabe der
    Verbindung gelesen (Sitzungsdisziplin v27)."""
    adressen: list[str] = []
    if vorgang is not None and getattr(vorgang, "leadmanager_id", None):
        leadmanager = session.get(Benutzer, vorgang.leadmanager_id)
        email = (getattr(leadmanager, "email", "") or "").strip() if leadmanager is not None else ""
        if email and "@" in email and email.lower() != (absender_adresse or "").lower():
            adressen.append(email)
    if absender_adresse:
        adressen.append(absender_adresse)
    return adressen


def _graph_senden(session: Session, an: str, betreff: str, body_html: str,
                  anhang_pfad: str | None,
                  inline_bilder: list[tuple[str, Path, str]] | None = None,
                  vorgang: Vorgang | None = None) -> tuple[bool, str]:
    """HTML-Mail (+ ICS, + Inline-Bilder) über Graph als absender_lead_mails.
    v29: KEIN Fallback auf ein anderes Postfach – scheitert der Versand, kommt
    (False, Grund) zurück und der Aufrufer wiederholt/markiert.
    Nachtrag 08.10.2026: mit `vorgang` trägt die Nachricht replyTo = Leadmanager +
    Absender (antwort_adressen); ohne Vorgang nur den Absender.
    v33 (Phase 166): Modus anwendung → POST /users/<termin@>/sendMail ohne from-Feld
    (Postfach aus der Zugriffsgruppe); Modus delegiert → /me/sendMail mit from = termin@
    („Senden als“, unverändert). Die Entscheidung trifft graph_versand.versand_pfad."""
    from app import graph_versand
    absender_adresse = _absender(session)
    reply_to = antwort_adressen(session, vorgang, absender_adresse)
    # Hotfix 06.10.2026: Verbindung vor Netz-I/O freigeben (Absender ist gelesen;
    # der commit speichert den gerenderten Eintrag – wie bisher am Ende des
    # Versand-Jobs; msal kann das Token über das Netz erneuern)
    from app.db import verbindung_freigeben
    verbindung_freigeben(session)
    token = graph_versand._token()
    if token is None:
        return False, graph_versand.nicht_verbunden_text()
    basis, von = graph_versand.versand_pfad(absender_adresse)
    anhaenge = []
    for cid, pfad, mime in inline_bilder or []:
        try:
            anhaenge.append({
                "@odata.type": "#microsoft.graph.fileAttachment",
                "name": Path(pfad).name, "contentType": mime,
                "contentId": cid, "isInline": True,
                "contentBytes": base64.b64encode(Path(pfad).read_bytes()).decode(),
            })
        except OSError:
            continue
    # v31 (Phase 153): mehrere ICS je Mail (ein Eintrag je Objekttermin, „;“-getrennt)
    for pfad in anhang_pfade(anhang_pfad):
        if not Path(pfad).exists():
            continue
        ics_bytes = Path(pfad).read_bytes()
        anhaenge.append({
            "@odata.type": "#microsoft.graph.fileAttachment",
            "name": Path(pfad).name,
            # v23 (Phase 108, E4): Storno-ICS mit MIME-Methode CANCEL, damit
            # Outlook/Apple den Kundeneintrag entfernen statt ihn zu ergänzen
            "contentType": f"text/calendar; method={ics_methode(ics_bytes)}",
            "contentBytes": base64.b64encode(ics_bytes).decode(),
        })
    nachricht = {
        "subject": betreff,
        "body": {"contentType": "html", "content": body_html},
        "toRecipients": [{"emailAddress": {"address": an}}],
        # Nachtrag 08.10.2026: Antworten an Leadmanager UND termin@
        "replyTo": [{"emailAddress": {"address": adresse}} for adresse in reply_to],
    }
    if von:
        nachricht["from"] = {"emailAddress": {"address": von}}   # nur Modus delegiert
    if anhaenge:
        nachricht["attachments"] = anhaenge
    try:
        graph_versand._graph_aufruf("POST", f"{basis}/sendMail", token,
                                    {"message": nachricht, "saveToSentItems": False})
        return True, ""
    except Exception as fehler:
        return False, f"Absender {absender_adresse}: {fehler}"[:500]


def testmail_senden(absender_adresse: str, an: str) -> tuple[bool, str]:
    """Prüfpunkt „Testmail aus termin@“ (Lead-Parametrierung): kurze Text-Mail
    als absender_adresse ohne Fallback. Läuft OHNE Sitzung – der Aufrufer
    (Route) gibt seine Sitzung vorher frei. Liefert (erfolg, fehlertext).
    v33: Modus anwendung → sendMail direkt an /users/<absender_adresse>."""
    from app import graph_versand
    token = graph_versand._token()
    if token is None:
        return False, graph_versand.nicht_verbunden_text()
    basis, von = graph_versand.versand_pfad(absender_adresse)
    nachricht = {
        "subject": f"Friondo Angebotstool – Testmail aus {absender_adresse}",
        "body": {"contentType": "text",
                 "content": ("Diese Testmail prüft das Senderecht des Lead-Absenders "
                             f"{absender_adresse} (Lead-Management V4, Prüfpunkt). "
                             f"Gesendet am {datetime.now():%d.%m.%Y %H:%M}.")},
        "toRecipients": [{"emailAddress": {"address": an}}],
    }
    if von:
        nachricht["from"] = {"emailAddress": {"address": von}}   # nur Modus delegiert
    try:
        graph_versand._graph_aufruf("POST", f"{basis}/sendMail", token,
                                    {"message": nachricht, "saveToSentItems": False})
        return True, ""
    except Exception as fehler:
        return False, f"Absender {absender_adresse}: {fehler}"[:500]


# --- Status fehler / Vorgangsfelder -------------------------------------------------------

def _mail_fehler_setzen(session: Session, vorgang: Vorgang, eintrag: KommunikationLog,
                        grund: str) -> None:
    """Vorgang sichtbar machen (Vertrag mit L1): mail_fehler + Zeit/Vorlage/Text,
    Aktivität „Mail nicht gesendet: <Vorlage>, <Grund>“."""
    from app import leadmanagement as kern
    vorgang.mail_fehler = True
    vorgang.mail_fehler_am = datetime.now()
    vorgang.mail_fehler_vorlage = (eintrag.vorlage_key or "")[:50]
    vorgang.mail_fehler_text = (grund or "")[:500]
    kern.aktivitaet(session, vorgang.id, "mail_aus",
                    f"Mail nicht gesendet: {vorlage_name(session, eintrag.vorlage_key)}, "
                    f"{grund}"[:4000], ergebnis="fehler")
    _admins_glocke(session, vorgang, eintrag, grund)


def _admins_glocke(session: Session, vorgang: Vorgang, eintrag: KommunikationLog,
                   grund: str) -> bool:
    """Nachtrag 08.10.2026 (Antwort Andreas): Betriebsglocke (art system) an alle
    aktiven Admins, wenn ein Lead-Mail-Eintrag auf `fehler` geht – genau einmal je
    Eintrag (nur beim Übergang, nicht je Wiederholversuch), in DERSELBEN Sitzung
    über projektierung.benachrichtigen (betrieb.admins_benachrichtigen öffnet eine
    zweite Sitzung → Schreibsperre). Link: Warteschlange mit Filter fehler."""
    from app import projektierung as kern_projekt
    admin_ids = [b.id for b in session.query(Benutzer)
                 .filter(rollen_modul.filter_basis("admin"), Benutzer.aktiv.is_(True))
                 .order_by(Benutzer.id)]
    if not admin_ids:
        return False
    kunde = session.get(Kunde, vorgang.kunde_id) if vorgang.kunde_id else None
    wer = kunde.anzeige_name if kunde is not None else (eintrag.an or "?")
    text = (f"Lead-Mail nicht gesendet: {vorlage_name(session, eintrag.vorlage_key)} "
            f"an {wer} – {grund}")
    kern_projekt.benachrichtigen(session, admin_ids, text[:500],
                                 "/lead-management/kommunikation?status=fehler", art="system")
    return True


def _mail_fehler_zuruecksetzen(session: Session, vorgang: Vorgang) -> bool:
    """Nach erfolgreichem (erneutem) Versand: Kennzeichen zurück, wenn kein
    weiterer Eintrag des Vorgangs mehr auf `fehler` steht."""
    if not vorgang.mail_fehler:
        return False
    offen = (session.query(KommunikationLog)
             .filter(KommunikationLog.vorgang_id == vorgang.id,
                     KommunikationLog.status == STATUS_FEHLER).count())
    if offen:
        return False
    vorgang.mail_fehler = False
    vorgang.mail_fehler_am = None
    vorgang.mail_fehler_vorlage = ""
    vorgang.mail_fehler_text = ""
    return True


def _versand_fehlgeschlagen(session: Session, vorgang: Vorgang, eintrag: KommunikationLog,
                            grund: str) -> str:
    """Wiederholung (Status bleibt geplant, Fälligkeit nach hinten) bis
    VERSUCHE_MAX, danach `fehler` + Vorgangsfelder. Liefert den Ergebnis-Status."""
    eintrag.versuche = int(getattr(eintrag, "versuche", 0) or 0) + 1
    eintrag.fehler_text = (grund or "")[:500]
    if eintrag.versuche < VERSUCHE_MAX:
        eintrag.status = "geplant"
        eintrag.geplant_am = datetime.now() + timedelta(
            seconds=WIEDERHOLUNG_PAUSE_S * eintrag.versuche)
        return "wiederholung"
    eintrag.status = STATUS_FEHLER
    _mail_fehler_setzen(session, vorgang, eintrag,
                        f"{grund} (nach {eintrag.versuche} Versuchen)")
    return STATUS_FEHLER


def eintrag_verarbeiten(session: Session, eintrag: KommunikationLog) -> str:
    """Einen fälligen Eintrag verarbeiten (Plan 78). v29: Absender termin@ ohne
    Fallback, Wiederholversuche, Status fehler mit Vorgangsfeldern; ausgeblendete
    Vorlagen (Nurture v29, nicht_erreicht v31) werden storniert; Erfolg setzt
    mail_fehler zurück. v31 (Phase 159): Mailsperre – bei lead_v5.mail_versand_aktiv
    = aus endet der Eintrag gerendert mit Status `gesperrt` (kein Graph-Aufruf, auch
    nicht Testpostfach, keine fehler-Glocke); mail_modus ist keine Steuerung mehr
    (bei „an“ geht die Mail an den Kunden). Liefert gesendet | gesperrt | fehler |
    wiederholung | storniert | wartet_adresse."""
    from app import lead_v5
    from app import leadmanagement as kern
    vorgang = session.get(Vorgang, eintrag.vorgang_id)
    if vorgang is None or not rendern(session, eintrag):
        eintrag.status = STATUS_FEHLER
        eintrag.fehler_text = "Vorgang fehlt"
        return STATUS_FEHLER
    # v29: Nurture entfällt / v31: nicht_erreicht entfällt – Altbestand wird storniert
    if eintrag.vorlage_key in VORLAGEN_AUSGEBLENDET:
        eintrag.status = "storniert"
        eintrag.fehler_text = AUSGEBLENDET_GRUND.get(eintrag.vorlage_key, "Vorlage entfällt")
        return "storniert"
    # Prozess-Fix 27.09.2026: Termin-Mails nur fuer aktive, kuenftige
    # Termine - Umbuchung/No-Show stornieren zwar (leadmanagement.
    # geplante_mails_stornieren), aber diese Pruefung faengt auch alle
    # Altbestaende und Randfaelle ab
    if eintrag.termin_id and eintrag.vorlage_key in ("terminerinnerung",
                                                     "terminbestaetigung"):
        termin = session.get(VotTermin, eintrag.termin_id)
        if (termin is None or termin.status not in ("geplant", "bestaetigt")
                or (eintrag.vorlage_key == "terminerinnerung"
                    and termin.beginn is not None
                    and termin.beginn < datetime.now())):
            eintrag.status = "storniert"
            eintrag.fehler_text = "Termin nicht mehr aktiv"
            return "storniert"
    # v29: unzustellbare Adresse – anhalten, bis die Adresse geändert wurde
    if vorgang.email_status == "ungueltig":
        eintrag.status = STATUS_WARTET_ADRESSE
        eintrag.fehler_text = "wartet auf neue E-Mail-Adresse (unzustellbar)"
        return STATUS_WARTET_ADRESSE
    eintrag.absender = _absender(session)
    # v31 (PLAN_LEAD_V5 Phase 159): Mailsperre der Testphase – Eintrag bleibt gerendert
    # (Vorschau/Protokoll sichtbar) mit Status gesperrt; kein Graph-Aufruf, auch nicht
    # ins Testpostfach; keine fehler-Glocke; Aktivität für die Timeline
    if not lead_v5.mail_versand_aktiv(session):
        eintrag.status = STATUS_GESPERRT
        eintrag.modus = STATUS_GESPERRT
        eintrag.gesendet_am = None
        eintrag.fehler_text = lead_v5.MAILSPERRE_HINWEIS[:500]
        kern.aktivitaet(session, vorgang.id, "mail_aus",
                        f"Mail gesperrt ({lead_v5.MAILSPERRE_HINWEIS}): "
                        f"{vorlage_name(session, eintrag.vorlage_key)} – {eintrag.betreff}"[:4000],
                        ergebnis=STATUS_GESPERRT)
        return STATUS_GESPERRT
    # Mailversand freigeschaltet: Versand an den Kunden über termin@ (mail_modus ist seit
    # v31 keine Steuerung mehr – der Wert bleibt in den Lead-Einstellungen lesbar)
    modus = "live"
    eintrag.modus = modus
    inline = inline_bilder_aus_html(session, eintrag.body_html)
    erfolg, fehler = _graph_senden(session, eintrag.an, eintrag.betreff,
                                   eintrag.body_html, eintrag.anhang_pfad, inline,
                                   vorgang=vorgang)
    if not erfolg:
        return _versand_fehlgeschlagen(session, vorgang, eintrag, fehler)
    eintrag.status = "gesendet"
    eintrag.gesendet_am = datetime.now()
    eintrag.fehler_text = ""
    _mail_fehler_zuruecksetzen(session, vorgang)
    kern.aktivitaet(session, vorgang.id, "mail_aus",
                    f"Mail {eintrag.vorlage_key} ({eintrag.status}, "
                    f"{modus}, von {eintrag.absender}): {eintrag.betreff}")
    return eintrag.status


def erneut_senden(session: Session, eintrag: KommunikationLog, benutzer=None) -> tuple[bool, str]:
    """„Erneut senden“ (Kartei/Warteschlange): Eintrag auf `geplant` mit
    sofortiger Fälligkeit, Versuchszähler 0, Empfänger = aktuelle Kundenadresse;
    gesendet wird durch den Lauf lead-mail (≤ 60 s). Kein Netzaufruf."""
    from app import lead_v5
    from app import leadmanagement as kern
    vorgang = session.get(Vorgang, eintrag.vorgang_id)
    if vorgang is None:
        return False, "Vorgang fehlt."
    if vorgang.email_status == "ungueltig":
        return False, "E-Mail-Adresse ist unzustellbar – bitte zuerst die Adresse in der Kartei ändern."
    # v31 (Phase 159): gesperrte Einträge werden beim Einschalten nicht automatisch
    # nachgesendet [ANNAHME] – „Erneut senden“ ist der bewusste Klick dafür; solange die
    # Sperre gilt, bleibt der Eintrag gesperrt
    if not lead_v5.mail_versand_aktiv(session):
        return False, f"{lead_v5.MAILSPERRE_HINWEIS} – der Eintrag bleibt in der Warteschlange (gesperrt)."
    # geplant ist erlaubt (Doppelklick/erneutes Anstoßen setzt nur Fälligkeit und Zähler)
    if eintrag.status not in (STATUS_FEHLER, "gesendet", "protokolliert", "storniert", "geplant",
                              STATUS_GESPERRT):
        return False, f"Eintrag steht auf „{eintrag.status}“ – erneuter Versand nicht möglich."
    kunde = session.get(Kunde, vorgang.kunde_id)
    if kunde is not None and kunde.email:
        eintrag.an = kunde.email
    eintrag.status = "geplant"
    eintrag.geplant_am = datetime.now()
    eintrag.versuche = 0
    eintrag.fehler_text = ""
    eintrag.gesendet_am = None
    kern.aktivitaet(session, vorgang.id, "mail_aus",
                    f"Erneuter Versand angestoßen: {vorlage_name(session, eintrag.vorlage_key)}",
                    benutzer=benutzer)
    session.flush()
    return True, "Erneuter Versand angestoßen – Ergebnis in etwa einer Minute."


def kartei_hinweis(session: Session, vorgang: Vorgang) -> dict | None:
    """Roter Hinweisbalken der Kundenkartei (Vertrag mit L1, _mail_hinweis.html):
    {art: fehler | ungueltig, titel, text, erneut_url, warteschlange_url,
    eintrag_id}. Unzustellbare Adresse hat Vorrang [ANNAHME] – ohne neue
    Adresse ist „Erneut senden“ sinnlos."""
    if vorgang is None:
        return None
    if vorgang.email_status == "ungueltig":
        kunde = session.get(Kunde, vorgang.kunde_id)
        wartend = (session.query(KommunikationLog)
                   .filter(KommunikationLog.vorgang_id == vorgang.id,
                           KommunikationLog.status == STATUS_WARTET_ADRESSE).count())
        wann = vorgang.email_status_am.strftime("%d.%m.%Y %H:%M") if vorgang.email_status_am else ""
        return {"art": "ungueltig", "titel": "E-Mail falsch",
                "text": (f"Die Adresse {kunde.email if kunde else '?'} ist unzustellbar"
                         + (f" ({vorgang.email_status_grund})" if vorgang.email_status_grund else "")
                         + (f", gemeldet {wann}" if wann else "") + ". "
                         + (f"{wartend} Mail{'s' if wartend != 1 else ''} wartet"
                            f"{'' if wartend == 1 else ''} – " if wartend else "")
                         + "bitte die E-Mail-Adresse im Kundeninfo-Block korrigieren; "
                         "wartende Mails werden dann automatisch freigegeben."),
                "erneut_url": None,
                "warteschlange_url": f"/lead-management/lead/{vorgang.id}/kommunikation",
                "eintrag_id": None}
    if vorgang.mail_fehler:
        eintrag = (session.query(KommunikationLog)
                   .filter(KommunikationLog.vorgang_id == vorgang.id,
                           KommunikationLog.status == STATUS_FEHLER)
                   .order_by(KommunikationLog.id.desc()).first())
        wann = vorgang.mail_fehler_am.strftime("%d.%m.%Y %H:%M") if vorgang.mail_fehler_am else ""
        return {"art": "fehler", "titel": "Mail nicht gesendet",
                "text": (f"{vorlage_name(session, vorgang.mail_fehler_vorlage or '')}"
                         + (f" vom {wann}" if wann else "")
                         + (f": {vorgang.mail_fehler_text}" if vorgang.mail_fehler_text else "")),
                "erneut_url": f"/lead-management/mail/{eintrag.id}/erneut" if eintrag else None,
                "warteschlange_url": "/lead-management/kommunikation?status=fehler",
                "eintrag_id": eintrag.id if eintrag else None}
    return None


# --- v31 (PLAN_LEAD_V5 Phase 158/159): Verträge mit K und B ---------------------------------

def gesperrte_anzahl(session: Session) -> int:
    """Zähler „Mails gesperrt: n“ der Lead-Einstellungen (Freischaltung, B)."""
    return int(session.query(KommunikationLog)
               .filter(KommunikationLog.status == STATUS_GESPERRT).count())


def in_warteschlange(session: Session, vorgang: Vorgang, key: str, betreff: str, text: str,
                     termin: VotTermin | None = None, anhaenge=None, benutzer=None):
    """Vertrag mit K (Kartei-Dialog „E-Mail senden“): nachbearbeiteten Betreff/Text
    als Warteschlangen-Eintrag ablegen – über kern.mail_planen (Kunden-E-Mail,
    HV-Versandweg bei Termin-Mails, Doppelversand-Schutz, Bounce-Status), der
    Text bleibt fest (kanal mail_fest – der Lauf lead-mail rendert ihn nicht neu),
    ICS-Anhänge (Liste von Pfaden; fehlt sie bei Terminvorlagen, erzeugt rendern()
    sie), Ersteller = benutzer, Aktivität. Die Mailsperre greift beim Versand-Job
    (Status gesperrt). Liefert den Eintrag oder None (keine Mail: ohne E-Mail,
    HV-Entwurf, bereits geplant) – die Meldung dazu steht in der letzten Aktivität."""
    from app import leadmanagement as kern
    text = (text or "").strip()
    betreff = (betreff or "").strip()[:300]
    eintrag = kern.mail_planen(session, vorgang, key, termin=termin)
    if eintrag is None:
        return None
    eintrag.kanal = KANAL_FEST
    if betreff:
        eintrag.betreff = betreff
    if text:
        eintrag.body_html = text if ist_html(text) else _als_html(text)
    if anhaenge:
        pfade = [str(p) for p in (anhaenge if isinstance(anhaenge, (list, tuple)) else [anhaenge]) if p]
        eintrag.anhang_pfad = ";".join(pfade)[:500] or None
    if benutzer is not None:
        eintrag.erstellt_von = benutzer.id
    if not eintrag.betreff or not eintrag.body_html:
        # leerer Dialogtext: Vorlage rendern, damit der Eintrag vollständig ist
        eintrag.kanal = "mail"
        rendern(session, eintrag)
        eintrag.kanal = KANAL_FEST
    elif eintrag.vorlage_key in TERMIN_PFLICHT_VORLAGEN and termin is not None and not eintrag.anhang_pfad:
        rendern(session, eintrag)   # ergänzt nur das ICS (fester Text bleibt)
    kern.aktivitaet(session, vorgang.id, "mail_aus",
                    f"E-Mail aus der Kartei geplant: {vorlage_name(session, key)} – {eintrag.betreff}"[:4000],
                    benutzer=benutzer)
    session.flush()
    return eintrag


def falsche_nummer_mail(session: Session, vorgang: Vorgang, benutzer=None) -> tuple[bool, str]:
    """Phase 158 (Vertrag mit B): Ergebnis „Falsche Nummer“ sendet zusätzlich die
    Vorlage falsche_telefonnummer an die E-Mail-Adresse des Leads – nur bei
    vorhandener Adresse (sonst (False, Hinweis)); Doppelversand-Schutz (kein zweiter
    offener Eintrag), Absender termin@, Aktivität; {absender} = handelnder Benutzer
    (erstellt_von). Die Mailsperre (Phase 159) setzt den Eintrag beim Versand-Job auf
    gesperrt – der Hinweis steht in der Meldung."""
    from app import lead_anrufliste, lead_v5
    from app import leadmanagement as kern
    kunde = session.get(Kunde, vorgang.kunde_id) if vorgang.kunde_id else None
    if kunde is None or not (kunde.email or "").strip():
        return False, ("Keine E-Mail-Adresse am Lead – Mail „Falsche Telefonnummer“ "
                       "nicht möglich (Nummer manuell prüfen).")
    if lead_anrufliste.mail_bereits_geplant(session, vorgang.id, FALSCHE_NUMMER_VORLAGE):
        return False, "Mail „Falsche Telefonnummer“ ist bereits geplant (Doppelversand-Schutz)."
    eintrag = kern.mail_planen(session, vorgang, FALSCHE_NUMMER_VORLAGE)
    if eintrag is None:
        return False, "Mail „Falsche Telefonnummer“ nicht geplant."
    if benutzer is not None:
        eintrag.erstellt_von = benutzer.id
    kern.aktivitaet(session, vorgang.id, "mail_aus",
                    f"Mail „Falsche Telefonnummer“ an {kunde.email} geplant (Vorlage {FALSCHE_NUMMER_VORLAGE})",
                    benutzer=benutzer)
    session.flush()
    meldung = f"Mail „Falsche Telefonnummer“ an {kunde.email} geplant."
    if not lead_v5.mail_versand_aktiv(session):
        meldung += f" {lead_v5.MAILSPERRE_HINWEIS} – Eintrag bleibt gesperrt in der Warteschlange."
    return True, meldung


# --- Bounce (Unzustellbar), Adressänderung, Kundenantwort -----------------------------------

def bounce_verbuchen(session: Session, vorgang: Vorgang, adresse: str, grund: str,
                     eintrag: KommunikationLog | None = None) -> int:
    """Unzustellbarkeitsbericht auf eine Tool-Mail: email_status = ungueltig
    (Zeit, Grund), Aktivität „E-Mail unzustellbar“, weitere geplante Einträge
    des Vorgangs an diese Adresse → wartet_adresse. Der gesendete Eintrag
    behält seinen Status, bekommt aber den Hinweis im fehler_text [ANNAHME].
    Liefert die Anzahl angehaltener Einträge."""
    from app import leadmanagement as kern
    adresse = (adresse or "").strip().lower()
    vorgang.email_status = "ungueltig"
    vorgang.email_status_am = datetime.now()
    vorgang.email_status_grund = (grund or "Unzustellbar")[:300]
    if eintrag is not None:
        eintrag.fehler_text = f"Unzustellbar: {grund}"[:500]
    kern.aktivitaet(session, vorgang.id, "mail_ein",
                    f"E-Mail unzustellbar: {adresse or '?'} – {grund}"[:4000],
                    ergebnis="unzustellbar")
    anzahl = 0
    for offen in (session.query(KommunikationLog)
                  .filter(KommunikationLog.vorgang_id == vorgang.id,
                          KommunikationLog.status == "geplant")):
        if adresse and (offen.an or "").strip().lower() != adresse:
            continue
        offen.status = STATUS_WARTET_ADRESSE
        offen.fehler_text = "wartet auf neue E-Mail-Adresse (unzustellbar)"
        anzahl += 1
    session.flush()
    return anzahl


def adresse_geaendert(session: Session, vorgang: Vorgang) -> int:
    """Vertrag mit L1 (Autospeichern des E-Mail-Felds ruft das auf): setzt
    email_status zurück und gibt wartet_adresse-Einträge des Vorgangs frei
    (geplant, sofort fällig, neue Adresse, Versuche 0) – nur wenn der Kunde
    jetzt eine Adresse hat. Liefert die Anzahl freigegebener Einträge."""
    from app import leadmanagement as kern
    kunde = session.get(Kunde, vorgang.kunde_id)
    neue = (kunde.email or "").strip() if kunde is not None else ""
    war_ungueltig = vorgang.email_status == "ungueltig"
    if not neue:
        return 0
    vorgang.email_status = None
    vorgang.email_status_am = None
    vorgang.email_status_grund = ""
    jetzt = datetime.now()
    anzahl = 0
    for e in (session.query(KommunikationLog)
              .filter(KommunikationLog.vorgang_id == vorgang.id,
                      KommunikationLog.status == STATUS_WARTET_ADRESSE)):
        e.status = "geplant"
        e.geplant_am = max(jetzt, e.geplant_am or jetzt)
        e.an = neue
        e.versuche = 0
        e.fehler_text = ""
        anzahl += 1
    if war_ungueltig or anzahl:
        kern.aktivitaet(session, vorgang.id, "mail_aus",
                        f"E-Mail-Adresse geändert ({neue}) – {anzahl} wartende "
                        f"Mail{'s' if anzahl != 1 else ''} freigegeben")
    session.flush()
    return anzahl


def kundenantwort_verbuchen(session: Session, vorgang: Vorgang, absender_adresse: str,
                            betreff: str, body: str, graph_id: str = "",
                            empfangen_am: datetime | None = None) -> None:
    """Kundenantwort auf eine Lead-Mail (termin@ über lead_mail_abruf, leads@
    über lead_parser): Aktivität mail_ein, Glocke art kundenantwort (standard-
    mäßig gesperrt), Wiedervorlage „jetzt“ bei offenen Leads, damit die
    Antwort unter „Fällig heute“ auftaucht.
    Nachtrag 08.10.2026 (Antwort Andreas): meldet sich der Kunde, kommt ein
    nicht erreichter oder zurückgestellter Lead zurück in die Kontaktierung
    (in_kontaktierung, Zurückstellung aufgehoben, Aktivität „Kunde hat
    geantwortet – zurück in die Kontaktierung“) – so wie vor v29 „Kundenantwort
    weckt den Lead“ (lead_parser, Stand 1e317e7); den weiteren Weg geht der
    Innendienst manuell, keine Nurture-Logik."""
    from app import leadmanagement as kern
    from app.models import LeadPosteingang
    kern.aktivitaet(session, vorgang.id, "mail_ein",
                    f"Antwort von {absender_adresse}: {betreff} – {(body or '')[:200]}")
    if kern.vorgang_offen(vorgang):
        vorgang.naechste_aktion_am = datetime.now()
        alt = vorgang.lead_phase or ""
        if alt in ("nicht_erreicht", "zurueckgestellt"):
            vorgang.lead_phase = "in_kontaktierung"
            vorgang.zurueckgestellt_bis = None
            kern.aktivitaet(session, vorgang.id, "status",
                            "Kunde hat geantwortet – zurück in die Kontaktierung "
                            f"(vorher {LEAD_PHASEN_NAMEN.get(alt, alt)})")
    if vorgang.leadmanager_id:
        kern.benachrichtigen(session, [vorgang.leadmanager_id],
                             f"Antwort-Mail von {absender_adresse}: {betreff}",
                             f"/lead-management/lead/{vorgang.id}", art="kundenantwort")
    if graph_id and not (session.query(LeadPosteingang)
                         .filter(LeadPosteingang.graph_id == graph_id).count()):
        session.add(LeadPosteingang(graph_id=graph_id, absender=absender_adresse,
                                    betreff=(betreff or "")[:300], body=(body or "")[:8000],
                                    empfangen_am=empfangen_am, status="angelegt",
                                    vorgang_id=vorgang.id))
    session.flush()


# --- Handelsvertreter-Versandwege (OFFEN 2) ---------------------------------------------------
# Vertrag (Nachtrag 08.10.2026): jede Funktion liefert (eintrag | None, hinweis, erledigt).
# eintrag → Warteschlangen-Eintrag wie bei angestellten AD; erledigt=True → der Weg hat
# alles selbst erledigt (Aktivität/To-Do), kein Rückfall auf „offen“; sonst schreibt
# kern.mail_planen den Hinweis als Aktivität und behandelt den Lead wie „offen“.

def hv_versandweg(session: Session) -> str:
    wert = (_parameter(session, "hv_versandweg", HV_VERSANDWEG_STANDARD)
            or HV_VERSANDWEG_STANDARD).strip()
    return wert if wert in HV_VERSANDWEGE else HV_VERSANDWEG_STANDARD


def hv_benutzer(session: Session, vorgang: Vorgang, termin=None):
    """Handelsvertreter eines Termin-/Vorgangs (termin.ad_id, sonst vorgang.ad_id)
    oder None, wenn der Zuständige kein Handelsvertreter ist."""
    from app import lead_v2
    hv_id = (termin.ad_id if termin is not None and getattr(termin, "ad_id", None)
             else getattr(vorgang, "ad_id", None))
    hv = session.get(Benutzer, hv_id) if hv_id else None
    return hv if hv is not None and lead_v2.ist_handelsvertreter(session, hv) else None


def hv_absender(session: Session, vorgang: Vorgang, termin=None) -> str:
    """E-Mail des Handelsvertreters aus der Benutzerverwaltung (Absender der
    .eml) – leer, wenn nicht gepflegt."""
    hv = hv_benutzer(session, vorgang, termin)
    return (hv.email or "").strip() if hv is not None else ""


def hv_versand_smtp(session: Session, vorgang: Vorgang, termin, vorlage_key: str):
    """Versandweg `smtp` (Erweiterungspunkt, noch ohne Inhalt): SMTP-Zugang je HV
    im Profil (App-Passwort, verschlüsselt gespeichert) – siehe
    docs/leadmanagement-entscheidungen.md V4. Liefert (None, Hinweis, False)."""
    return None, "Versandweg smtp noch nicht umgesetzt – wie „offen“ behandelt", False


def _dateiname_sauber(text: str, standard: str = "Kunde") -> str:
    text = (text or "").strip()
    for a, b in (("ä", "ae"), ("ö", "oe"), ("ü", "ue"), ("Ä", "Ae"), ("Ö", "Oe"), ("Ü", "Ue"),
                 ("ß", "ss"), ("é", "e"), ("è", "e")):
        text = text.replace(a, b)
    text = re.sub(r"[^A-Za-z0-9_-]+", "_", text).strip("_")
    return text[:60] or standard


def eml_dateiname(vorlage_key: str, kunde) -> str:
    """Terminbestaetigung_<Kunde>.eml (Vorlage + Kundenname, ASCII-sicher)."""
    return (f"{EML_VORLAGEN_NAMEN.get(vorlage_key, 'Mail')}_"
            f"{_dateiname_sauber(kunde.anzeige_name if kunde is not None else '')}.eml")


def eml_erstellen(session: Session, vorgang: Vorgang, termin: VotTermin,
                  vorlage_key: str = TERMIN_VORLAGE) -> dict:
    """Nachtrag 08.10.2026 (Antwort Andreas), Versandweg `entwurf`: die fertige
    Termin-Mail als RFC-822-Datei (.eml) – multipart/mixed(multipart/alternative
    (Text, multipart/related(HTML + Inline-Bilder als CID)), ICS-Anhang). Absender =
    E-Mail des Handelsvertreters aus der Benutzerverwaltung (fehlt sie: From leer,
    Hinweis), Empfänger = Kunde, Betreff aus der Vorlage des HV (vorlage_rendern),
    Kopf X-Unsent: 1 (Outlook öffnet die Datei als Entwurf mit Senden-Knopf).
    Kein Netzaufruf, kein Warteschlangen-Eintrag. Liefert {bytes, dateiname, betreff,
    absender, an, hinweise, vorlage_key, ics_pfad}."""
    import email.policy
    from email.message import EmailMessage
    from email.utils import formataddr, formatdate, make_msgid
    kunde = session.get(Kunde, vorgang.kunde_id) if vorgang.kunde_id else None
    hv = hv_benutzer(session, vorgang, termin)
    termine = objekttermine_aktiv(session, vorgang) if vorlage_key == OBJEKT_VORLAGE else None
    betreff, body_html, _ = vorlage_rendern(session, vorlage_key, vorgang, termin, termine=termine)
    key = verwendeter_vorlagen_key(session, vorlage_key, termin, termine)
    text = html_zu_text(body_html)
    hinweise = []
    absender_hv = (hv.email or "").strip() if hv is not None else ""
    if not absender_hv:
        hinweise.append("Keine E-Mail-Adresse für "
                        f"{hv.name if hv is not None else 'den Handelsvertreter'} in der "
                        "Benutzerverwaltung – der Absender bleibt leer, bitte im Mailprogramm ergänzen.")
    an = (kunde.email or "").strip() if kunde is not None else ""
    if not an:
        hinweise.append("Kunde ohne E-Mail-Adresse – Empfänger bitte im Mailprogramm ergänzen.")
    msg = EmailMessage(policy=email.policy.SMTP)
    msg["Subject"] = betreff
    if absender_hv:
        msg["From"] = formataddr((hv.name, absender_hv))
    if an:
        msg["To"] = formataddr((kunde.anzeige_name, an))
    msg["Date"] = formatdate(localtime=True)
    msg["Message-ID"] = make_msgid(domain="friondo.de")
    msg["X-Unsent"] = "1"
    msg["X-Friondo-Vorgang"] = str(vorgang.id)
    msg.set_content(text)
    msg.add_alternative(body_html, subtype="html")
    bilder = inline_bilder_aus_html(session, body_html)
    if bilder:
        html_teil = msg.get_payload()[-1]
        for cid, pfad, mime in bilder:
            haupt, _, unter = mime.partition("/")
            try:
                daten = Path(pfad).read_bytes()
            except OSError:
                continue
            html_teil.add_related(daten, maintype=haupt or "image", subtype=unter or "jpeg",
                                  cid=f"<{cid}>", filename=Path(pfad).name)
    ics_pfad = None
    ics_pfade: list[str] = []
    if termine and kunde is not None:
        # v31 (Phase 153): Objekt-Terminbestätigung – ein ICS je Objekttermin
        ics_pfade = [p for p in (ics_erstellen(session, t, vorgang) for t in termine) if p]
        ics_pfad = ics_pfade[0] if ics_pfade else None
    elif termin is not None and termin.beginn is not None and kunde is not None:
        ics_pfad = ics_erstellen(session, termin, vorgang,
                                 methode="CANCEL" if vorlage_key == "terminabsage" else "REQUEST")
        ics_pfade = [ics_pfad] if ics_pfad else []
    for pfad in ics_pfade:
        if not Path(pfad).exists():
            continue
        ics_bytes = Path(pfad).read_bytes()
        msg.add_attachment(ics_bytes, maintype="text", subtype="calendar",
                           filename=Path(pfad).name,
                           params={"method": ics_methode(ics_bytes)})
    return {"bytes": msg.as_bytes(), "dateiname": eml_dateiname(vorlage_key, kunde),
            "betreff": betreff, "absender": absender_hv, "an": an, "hinweise": hinweise,
            "vorlage_key": key, "ics_pfad": ics_pfad, "ics_pfade": ics_pfade}


def hv_versand_entwurf(session: Session, vorgang: Vorgang, termin, vorlage_key: str):
    """Versandweg `entwurf` (Nachtrag 08.10.2026, Standard): keine Warteschlangen-
    Mail – Aktivität „<Vorlage> als Entwurf (.eml) bereitgestellt – Versand aus dem
    eigenen Postfach des HV“ und To-Do an den Handelsvertreter „… aus dem eigenen
    Postfach senden“ (fällig sofort) mit Link auf die Vorschau (?vorlage=…, dort
    „.eml herunterladen“). Die Erinnerung −24 h bleibt wie bei „offen“ nur
    Aktivität [ANNAHME]. Liefert (None, "", True) – vollständig behandelt."""
    from app import lead_todos
    from app import leadmanagement as kern
    hv = hv_benutzer(session, vorgang, termin)
    name = vorlage_name(session, vorlage_key)
    absender_hv = (hv.email or "").strip() if hv is not None else ""
    termin_id = getattr(termin, "id", None) if termin is not None else None
    vorschau = (f"/lead-management/lead/{vorgang.id}/termin/{termin_id}/vorschau?vorlage={vorlage_key}"
                if termin_id else "")
    text = (f"{name} als Entwurf (.eml) bereitgestellt – Versand aus dem eigenen Postfach des HV"
            + (f" ({hv.name})" if hv is not None else "")
            + ("" if absender_hv else " – Hinweis: keine E-Mail-Adresse des HV in der Benutzerverwaltung")
            + (f"; Vorschau: {vorschau}" if vorschau else ""))
    kern.aktivitaet(session, vorgang.id, "mail_aus", text[:4000], ergebnis="hv_entwurf")
    if hv is None or not termin_id or vorlage_key == "terminerinnerung":
        return None, "", True
    titel = EML_TODO_TITEL.get(vorlage_key, f"{name} aus dem eigenen Postfach senden")
    try:
        lead_todos.anlegen(session, None, hv.id, titel,
                           text=("Vorschau öffnen, „.eml herunterladen“, Datei im eigenen "
                                 f"Mailprogramm öffnen, prüfen und senden: {vorschau}"),
                           faellig_am=datetime.now(), vorgang_id=vorgang.id)
    except ValueError:
        pass
    return None, "", True


def hv_versand_leads_im_namen(session: Session, vorgang: Vorgang, termin, vorlage_key: str):
    """Versandweg `leads_im_namen` (Erweiterungspunkt, noch ohne Inhalt): Versand
    über termin@ im Namen des HV mit Reply-To = HV. Liefert (None, Hinweis, False)."""
    return None, "Versandweg leads_im_namen noch nicht umgesetzt – wie „offen“ behandelt", False


HV_VERSAND_FUNKTIONEN = {"smtp": hv_versand_smtp, "entwurf": hv_versand_entwurf,
                         "leads_im_namen": hv_versand_leads_im_namen}


def termin_vorschau(session: Session, vorgang: Vorgang, termin: VotTermin,
                    vorlage_key: str = TERMIN_VORLAGE, mit_ics: bool = True) -> dict:
    """Fertige Terminbestätigung ohne Warteschlangen-Eintrag (HV-Vorschau, Route
    GET /lead/{id}/termin/{tid}/vorschau): {betreff, html, text, vorlage_key,
    ics_pfad, ics_pfade (v31: Objekt-Terminbestätigung mit ICS je Objekttermin),
    fehlende}. Kein Netzaufruf."""
    termine = objekttermine_aktiv(session, vorgang) if vorlage_key == OBJEKT_VORLAGE else None
    betreff, body_html, fehlende = vorlage_rendern(session, vorlage_key, vorgang, termin,
                                                   vorschau=True, termine=termine)
    key = verwendeter_vorlagen_key(session, vorlage_key, termin, termine)
    ics_pfad = None
    ics_pfade: list[str] = []
    if mit_ics and termine:
        ics_pfade = [p for p in (ics_erstellen(session, t, vorgang) for t in termine) if p]
        ics_pfad = ics_pfade[0] if ics_pfade else None
    elif mit_ics and termin is not None and termin.beginn is not None:
        ics_pfad = ics_erstellen(session, termin, vorgang,
                                 methode="CANCEL" if vorlage_key == "terminabsage" else "REQUEST")
        ics_pfade = [ics_pfad] if ics_pfad else []
    return {"betreff": betreff, "html": body_html, "text": html_zu_text(body_html),
            "vorlage_key": key, "ics_pfad": ics_pfad, "ics_pfade": ics_pfade,
            "fehlende": fehlende}


# --- Vorschau mit Demo-Lead (Editor) -------------------------------------------------------

def demo_lead_fuer_vorschau(session: Session, ad_id: int | None = None):
    """(vorgang, termin, kunde) für die Editor-Vorschau: ein Demo-Lead mit
    E-Mail (sonst ein beliebiger Lead), ein transienter Termin beim gewünschten
    Vertriebler (nicht gespeichert); ohne Lead ein transientes Beispiel."""
    vorgang = (session.query(Vorgang).join(Kunde, Kunde.id == Vorgang.kunde_id)
               .filter(Vorgang.demo.is_(True), Kunde.email != "")
               .order_by(Vorgang.id.desc()).first())
    kunde = session.get(Kunde, vorgang.kunde_id) if vorgang is not None else None
    if vorgang is None or kunde is None:
        kunde = Kunde(anrede="Frau", vorname="Erika", nachname="Mustermann",
                      strasse="Musterstraße 1", plz="47051", ort="Duisburg",
                      email="erika.mustermann@example.invalid", interesse="WP,PV")
        vorgang = Vorgang(kunde_id=0, lead_phase="qualifiziert")
    if ad_id is None:
        ad = next(iter(vertriebler_liste(session)), None)
        ad_id = ad.id if ad is not None else None
    beginn = datetime.now().replace(hour=10, minute=0, second=0, microsecond=0) + timedelta(days=3)
    while beginn.weekday() >= 5:
        beginn += timedelta(days=1)
    termin = VotTermin(vorgang_id=vorgang.id or 0, ad_id=ad_id, beginn=beginn,
                       ende=beginn + timedelta(minutes=90),
                       adresse=", ".join(t for t in (kunde.strasse, f"{kunde.plz} {kunde.ort}".strip()) if t),
                       status="geplant", typ="vot", ics_uid="friondo-vorschau@friondo.de")
    return vorgang, termin, kunde


def demo_termine_fuer_vorschau(session: Session, vorgang, termin: VotTermin, kunde) -> list[VotTermin]:
    """v31 (Phase 153): Editor-Vorschau der Objekt-Terminbestätigung – zwei transiente
    Objekttermine (Hauptobjekt = Kundenadresse, zweites Beispielobjekt am selben Tag),
    nichts wird gespeichert."""
    zweiter = VotTermin(vorgang_id=termin.vorgang_id, ad_id=termin.ad_id,
                        beginn=termin.beginn + timedelta(hours=3),
                        ende=termin.beginn + timedelta(hours=3, minutes=90),
                        adresse="Beispielweg 2, 47051 Duisburg (Objekt 2)",
                        status="geplant", typ="vot", ics_uid="friondo-vorschau-2@friondo.de")
    return [termin, zweiter]


# --- Zulieferung docs/vorlagen/terminbestaetigung/ (wiederholbar) ---------------------------

def _name_normal(text: str) -> str:
    text = (text or "").lower()
    for a, b in (("ä", "ae"), ("ö", "oe"), ("ü", "ue"), ("ß", "ss"), ("é", "e"), ("è", "e")):
        text = text.replace(a, b)
    return re.sub(r"[^a-z0-9]", "", text)


def _namensvarianten(person) -> set[str]:
    varianten = {_name_normal(person.name)}
    teile = [t for t in re.split(r"[\s.,-]+", person.name or "") if len(t) > 1]
    varianten.update(_name_normal(t) for t in teile)
    if len(teile) >= 2:
        varianten.add(_name_normal(teile[0] + teile[-1]))
        varianten.add(_name_normal(teile[-1] + teile[0]))
    if getattr(person, "vorname", ""):
        varianten.add(_name_normal(person.vorname))
    if person.email and "@" in person.email:
        varianten.add(_name_normal(person.email.split("@", 1)[0]))
    return {v for v in varianten if v}


def _datei_hash(daten: bytes) -> str:
    return hashlib.sha256(daten).hexdigest()[:32]


def _html_zulieferung_lesen(roh: bytes) -> tuple[str, str]:
    """(Betreff aus <title> oder <!-- betreff: … -->, Vorlagentext = Body)."""
    for codec in ("utf-8-sig", "utf-8", "windows-1252"):
        try:
            text = roh.decode(codec)
            break
        except UnicodeDecodeError:
            continue
    else:
        text = roh.decode("utf-8", errors="replace")
    betreff = ""
    treffer = re.search(r"<!--\s*betreff\s*:\s*(.*?)-->", text, re.IGNORECASE | re.DOTALL)
    if treffer:
        betreff = treffer.group(1).strip()
    else:
        treffer = re.search(r"<title[^>]*>(.*?)</title>", text, re.IGNORECASE | re.DOTALL)
        if treffer:
            betreff = html_modul.unescape(re.sub(r"\s+", " ", treffer.group(1))).strip()
    koerper = re.search(r"<body[^>]*>(.*)</body>", text, re.IGNORECASE | re.DOTALL)
    vorlage = (koerper.group(1) if koerper else text).strip()
    return betreff[:300], vorlage


def zulieferung_einspielen(session: Session, protokoll: bool = True) -> dict:
    """Wiederholbarer Schritt (migrate.py, Knopf, scripts/vorlagen_einspielen.py):
    1) jeder aktive Vertriebler ohne eigene Terminbestätigung bekommt die
       Standard-Kopie; 2) liegt docs/vorlagen/terminbestaetigung/ vor, wird je
       <name>.html eine Vorlage und je <name>.jpg|.png ein Benutzerbild
       eingespielt (Zuordnung über den Benutzernamen/Vornamen/E-Mail-Teil);
       Datei-Hash in _hash bzw. _bildhash gemerkt – unveränderte Dateien
       werden übersprungen, im Editor geänderte Vorlagen (Quelle editor) nie
       überschrieben [ANNAHME]. Ergebnis als dict + Protokollzeile."""
    from app import leadmanagement as kern
    from app.models import einstellung_holen, einstellung_setzen
    ergebnis = {"ordner": ZULIEFERUNG_ORDNER.exists(), "kopien": 0, "eingespielt": [],
                "bilder": [], "unveraendert": 0, "uebersprungen": [], "meldungen": []}
    personen = vertriebler_liste(session)
    for person in personen:
        if vertriebler_vorlage_sicherstellen(session, person):
            ergebnis["kopien"] += 1
    if ergebnis["kopien"]:
        ergebnis["meldungen"].append(f"{ergebnis['kopien']} Standard-Kopie(n) angelegt")
    if ZULIEFERUNG_ORDNER.exists():
        varianten = {p.id: _namensvarianten(p) for p in personen}
        for datei in sorted(ZULIEFERUNG_ORDNER.iterdir()):
            endung = datei.suffix.lower()
            if endung not in (".html", ".htm", *BILD_ENDUNGEN):
                continue
            stamm = _name_normal(datei.stem)
            treffer = [p for p in personen if stamm in varianten[p.id]]
            if len(treffer) != 1:
                grund = "kein Vertriebler" if not treffer else "mehrdeutig: " + ", ".join(p.name for p in treffer)
                ergebnis["uebersprungen"].append(f"{datei.name} ({grund})")
                continue
            person = treffer[0]
            key = vertriebler_key(person.id)
            daten = datei.read_bytes()
            hash_neu = _datei_hash(daten)
            if endung in (".html", ".htm"):
                hash_alt = einstellung_holen(session, f"lead_vorlage_{key}_hash", "")
                if hash_alt == hash_neu and vorlage_vorhanden(session, key):
                    ergebnis["unveraendert"] += 1
                    continue
                if vorlage_quelle(session, key) == "editor":
                    ergebnis["uebersprungen"].append(f"{datei.name} (im Editor geändert – nicht überschrieben)")
                    continue
                betreff, text = _html_zulieferung_lesen(daten)
                if not text:
                    ergebnis["uebersprungen"].append(f"{datei.name} (leer)")
                    continue
                if not betreff:
                    betreff, _ = vorlage_laden(session, key)
                vorlage_speichern(session, key, betreff, text, quelle="zulieferung")
                einstellung_setzen(session, f"lead_vorlage_{key}_hash", hash_neu)
                session.flush()
                ergebnis["eingespielt"].append(f"{datei.name} → {person.name}")
            else:
                if len(daten) > BILD_MAX_BYTES:
                    ergebnis["uebersprungen"].append(f"{datei.name} (größer als 2 MB)")
                    continue
                hash_alt = einstellung_holen(session, f"lead_vorlage_{key}_bildhash", "")
                if hash_alt == hash_neu and bild_pfad(person) is not None:
                    ergebnis["unveraendert"] += 1
                    continue
                if bild_pfad(person) is not None and not hash_alt:
                    ergebnis["uebersprungen"].append(f"{datei.name} (Bild manuell hochgeladen – nicht überschrieben)")
                    continue
                rel = benutzerbild_speichern(person, daten, endung)
                einstellung_setzen(session, f"lead_vorlage_{key}_bildhash", hash_neu)
                session.flush()
                ergebnis["bilder"].append(f"{datei.name} → {person.name} ({rel})")
        teile = []
        if ergebnis["eingespielt"]:
            teile.append(f"{len(ergebnis['eingespielt'])} Vorlage(n) eingespielt")
        if ergebnis["bilder"]:
            teile.append(f"{len(ergebnis['bilder'])} Bild(er) eingespielt")
        if ergebnis["unveraendert"]:
            teile.append(f"{ergebnis['unveraendert']} unverändert")
        if ergebnis["uebersprungen"]:
            teile.append(f"{len(ergebnis['uebersprungen'])} übersprungen: " + "; ".join(ergebnis["uebersprungen"]))
        ergebnis["meldungen"].extend(teile)
    else:
        try:
            ordner_text = str(ZULIEFERUNG_ORDNER.relative_to(config.PROJEKT_ORDNER))
        except ValueError:
            ordner_text = str(ZULIEFERUNG_ORDNER)
        ergebnis["meldungen"].append(f"Ordner {ordner_text} liegt nicht vor – nur Standard-Kopien geprüft")
    ergebnis["meldung"] = "Terminbestätigungen einspielen: " + ("; ".join(ergebnis["meldungen"]) or "keine Änderungen")
    if protokoll:
        kern.einstellungs_protokoll(session, ergebnis["meldung"][:300])
    session.flush()
    return ergebnis


def benutzerbild_speichern(person, daten: bytes, endung: str) -> str:
    """Bild unter data/benutzerbilder/<id>.<ext> ablegen, alte Datei entfernen,
    bild_datei (relativ zu DATA_ORDNER) setzen. Liefert den relativen Pfad."""
    endung = endung.lower()
    if endung == ".jpeg":
        endung = ".jpg"
    BENUTZERBILDER_ORDNER.mkdir(parents=True, exist_ok=True)
    alt = bild_pfad(person)
    ziel = BENUTZERBILDER_ORDNER / f"{person.id}{endung}"
    ziel.write_bytes(daten)
    if alt is not None and alt.resolve() != ziel.resolve():
        try:
            alt.unlink()
        except OSError:
            pass
    rel = f"benutzerbilder/{person.id}{endung}"
    person.bild_datei = rel
    return rel


def benutzerbild_entfernen(person) -> None:
    alt = bild_pfad(person)
    if alt is not None:
        try:
            alt.unlink()
        except OSError:
            pass
    person.bild_datei = ""


# --- Migration v29 ------------------------------------------------------------------------

def migration_v29_mails(session: Session) -> list[str]:
    """Datenmigration Phase 142 (migrate.py, idempotent, committet nicht):
    Parameter absender_lead_mails/hv_versandweg, offene Warteschlangen-Einträge
    erhalten den neuen Absender, Standard-Terminbestätigung bekommt die v29-
    Platzhalter, Standard-Kopien je Vertriebler (+ Zulieferung, falls vorhanden),
    offene Nurture-Einträge storniert, Blatt Terminhinweise als Platzhalter
    angelegt (Marker-Einstellung)."""
    from app import leadmanagement as kern, leadmanagement_logik
    from app.models import LeadParameter, einstellung_holen, einstellung_setzen
    meldungen: list[str] = []
    vorhanden = {p.name for p in session.query(LeadParameter.name)}
    for name, wert in ((PARAMETER_ABSENDER, ABSENDER_STANDARD),
                       ("hv_versandweg", HV_VERSANDWEG_STANDARD)):
        if name not in vorhanden:
            kern.parameter_setzen(session, name, wert)
            meldungen.append(f"Lead V4: Parameter {name} = {wert}")
    # Nachtrag 08.10.2026 (Antwort Andreas): HV-Versandweg einmalig offen → entwurf
    # (Terminbestätigung als .eml aus dem eigenen Postfach); `offen` bleibt danach
    # in der Parametrierung wählbar – Marker, damit die Wahl nicht erneut überschrieben wird
    if einstellung_holen(session, "migration_v29_hv_entwurf", "") != "erledigt":
        if hv_versandweg(session) == "offen":
            kern.parameter_setzen(session, "hv_versandweg", "entwurf")
            meldungen.append("Lead V4: hv_versandweg offen → entwurf (Terminbestätigung als "
                             ".eml aus dem eigenen Postfach des Handelsvertreters)")
        einstellung_setzen(session, "migration_v29_hv_entwurf", "erledigt")
    neu = absender(session)
    offene = (session.query(KommunikationLog)
              .filter(KommunikationLog.status.in_(("geplant", STATUS_WARTET_ADRESSE)))
              .all())
    umgestellt = 0
    for e in offene:
        if (getattr(e, "absender", "") or "") != neu:
            e.absender = neu
            umgestellt += 1
    if umgestellt:
        meldungen.append(f"Lead V4: {umgestellt} offene Lead-Mail(s) auf Absender {neu} umgestellt")
    # Standard-Terminbestätigung: v12-Text → v29-Rahmen (nur wenn unverändert);
    # angepasster Text: fehlende Platzhalter anhängen (einmalig, Marker)
    if einstellung_holen(session, "migration_v29_terminbestaetigung", "") != "erledigt":
        betreff_alt = einstellung_holen(session, f"lead_vorlage_{TERMIN_VORLAGE}_betreff", "")
        text_alt = einstellung_holen(session, f"lead_vorlage_{TERMIN_VORLAGE}_text", "")
        _, betreff_neu, text_neu = VORLAGEN_START[TERMIN_VORLAGE]
        if not text_alt or text_alt.strip() == _TERMINBESTAETIGUNG_V12_TEXT.strip():
            vorlage_speichern(session, TERMIN_VORLAGE, betreff_alt or betreff_neu, text_neu,
                              quelle="")
            meldungen.append("Lead V4: Standard-Terminbestätigung auf den v29-Rahmen gesetzt "
                             "({adresse}, {sparten_hinweise}, {vertriebler_block})")
        else:
            fehlend = [p for p in ("{sparten_hinweise}", "{vertriebler_block}") if p not in text_alt]
            if fehlend:
                text_alt = text_alt.rstrip() + "\n\n" + "\n\n".join(fehlend) + "\n"
                einstellung_setzen(session, f"lead_vorlage_{TERMIN_VORLAGE}_text", text_alt)
                meldungen.append("Lead V4: Standard-Terminbestätigung (angepasster Text) um "
                                 + ", ".join(fehlend) + " ergänzt")
        einstellung_setzen(session, "migration_v29_terminbestaetigung", "erledigt")
    # Standard-Kopien je Vertriebler + Zulieferung (wiederholbar)
    ergebnis = zulieferung_einspielen(session, protokoll=False)
    if ergebnis["kopien"] or ergebnis["eingespielt"] or ergebnis["bilder"]:
        meldungen.append("Lead V4: " + "; ".join(ergebnis["meldungen"]))
    # Nurture entfällt: offene Einträge stornieren
    storniert = 0
    for e in (session.query(KommunikationLog)
              .filter(KommunikationLog.vorlage_key.in_(VORLAGEN_AUSGEBLENDET),
                      KommunikationLog.status.in_(("geplant", STATUS_WARTET_ADRESSE)))):
        e.status = "storniert"
        e.fehler_text = "Nurture entfällt (v29)"
        storniert += 1
    if storniert:
        meldungen.append(f"Lead V4: {storniert} offene Nurture-Mail(s) storniert (Nurture entfällt)")
    # Blatt Terminhinweise (Platzhalter) – Marker, damit der Schritt einmalig bleibt
    if einstellung_holen(session, "migration_v29_terminhinweise", "") != "erledigt":
        if leadmanagement_logik.terminhinweise_blatt_anlegen():
            meldungen.append("Lead V4: Blatt „Terminhinweise“ mit Platzhalter „(Punkte folgen)“ "
                             "je Sparte in der Steuerdatei angelegt")
        einstellung_setzen(session, "migration_v29_terminhinweise", "erledigt")
    session.flush()
    return meldungen


# --- Migration v31 (PLAN_LEAD_V5 Phase 153/156/158) ------------------------------------------

def kuerzel_ersetzen(text: str, namen: dict | None = None) -> tuple[str, list[str]]:
    """Wörtliche Kürzel „WP“, „PV“, „KL“, „WB“, „GW“ als eigenständige Wörter (auch
    „WP+PV“/„WP/PV“ als Aufzählung) durch die Langform ersetzen. Platzhalter wie
    {sparten} und Wortteile (z. B. „WPL“, „KLIMA“) bleiben. Liefert (neuer Text,
    Liste „WP → Wärmepumpe“ je Ersetzung)."""
    namen = namen or sparten_modul.SPARTEN_LANG
    ersetzungen: list[str] = []
    if not text:
        return text or "", ersetzungen

    def _kombi(m):
        codes = re.findall("|".join(MIGRATION_KUERZEL), m.group(1))
        lang = sparten_modul.sparten_text(codes, langnamen=namen)
        ersetzungen.append(f"{m.group(1)} → {lang}")
        return lang

    def _einzeln(m):
        lang = sparten_modul.langname(m.group(1), namen)
        ersetzungen.append(f"{m.group(1)} → {lang}")
        return lang
    neu = _KUERZEL_PLUS_MUSTER.sub(_kombi, text)
    neu = _KUERZEL_MUSTER.sub(_einzeln, neu)
    return neu, ersetzungen


def migration_v31_mails(session: Session) -> list[str]:
    """Datenmigration v31 (migrate.py-Hook, idempotent, committet nicht):
    (a) Vorlagen terminbestaetigung_objekte und falsche_telefonnummer anlegen, falls
        nicht vorhanden (vorlagen_vorbelegen läuft davor – Meldung einmalig per Marker);
    (b) in allen gespeicherten Lead-Vorlagentexten und Betreffs die Kürzel WP/PV/KL/WB/GW
        als eigenständige Wörter durch die Langform ersetzen – je Vorlage eine Meldung
        mit der Liste der Ersetzungen (Gesamtübersicht);
    (c) offene Warteschlangen-Einträge nicht_erreicht stornieren (Protokoll: Meldung,
        Einstellungs-Protokoll, Aktivität je Vorgang);
    (d) Standardtexte im Code nutzen {sparten}/{sparten_interesse} (Langform) – keine
        Datenänderung nötig."""
    from app import leadmanagement as kern
    from app.models import Einstellung, einstellung_holen, einstellung_setzen
    meldungen: list[str] = []
    # (a) neue Vorlagen
    if einstellung_holen(session, "migration_v31_vorlagen", "") != "erledigt":
        neu = []
        for key in (OBJEKT_VORLAGE, FALSCHE_NUMMER_VORLAGE):
            if not vorlage_vorhanden(session, key):
                _, betreff, text = VORLAGEN_START[key]
                vorlage_speichern(session, key, betreff, text, quelle="")
                neu.append(key)
        meldungen.append("v31: Vorlagen terminbestaetigung_objekte und falsche_telefonnummer "
                         + ("angelegt" if neu else "vorhanden (vorbelegt)"))
        einstellung_setzen(session, "migration_v31_vorlagen", "erledigt")
    # (b) Kürzel → Langform in gespeicherten Vorlagentexten und Betreffs
    namen = langnamen(session)
    ersetzt_gesamt = 0
    for zeile in (session.query(Einstellung)
                  .filter(Einstellung.name.like("lead_vorlage_%"))
                  .order_by(Einstellung.name)):
        if not (zeile.name.endswith("_text") or zeile.name.endswith("_betreff")):
            continue
        neu, ersetzungen = kuerzel_ersetzen(zeile.wert or "", namen)
        if not ersetzungen:
            continue
        zeile.wert = neu
        ersetzt_gesamt += len(ersetzungen)
        zaehlung: dict[str, int] = {}
        for e in ersetzungen:
            zaehlung[e] = zaehlung.get(e, 0) + 1
        vorlage = zeile.name[len("lead_vorlage_"):]
        meldungen.append(f"v31: Vorlage {vorlage}: "
                         + ", ".join(f"{e} ({n}×)" if n > 1 else e for e, n in zaehlung.items()))
    if ersetzt_gesamt:
        meldungen.append(f"v31: {ersetzt_gesamt} Sparten-Kürzel in Vorlagen durch Langformen ersetzt")
    # (c) offene nicht_erreicht-Einträge stornieren
    storniert = 0
    for e in (session.query(KommunikationLog)
              .filter(KommunikationLog.vorlage_key == "nicht_erreicht",
                      KommunikationLog.status.in_(("geplant", STATUS_WARTET_ADRESSE)))):
        e.status = "storniert"
        e.fehler_text = AUSGEBLENDET_GRUND["nicht_erreicht"]
        kern.aktivitaet(session, e.vorgang_id, "mail_aus",
                        "Mail „Nicht erreicht“ storniert – Vorlage entfällt (v31, Kaskade ohne "
                        "Mail nach Versuch 2/4)", ergebnis="storniert")
        storniert += 1
    if storniert:
        meldungen.append(f"v31: {storniert} offene Mail(s) nicht_erreicht storniert (Vorlage entfällt)")
        kern.einstellungs_protokoll(session, f"v31: {storniert} offene Mail(s) „Nicht erreicht“ storniert "
                                             "– Vorlage entfällt, Kaskade ohne Mail nach Versuch 2/4")
    session.flush()
    return meldungen


# --- Versand-Job (Scheduler) --------------------------------------------------------------

BLOCK_GROESSE = 50   # fällige Einträge je Lauf (wie bisher limit 50)


def _eintrag_in_sitzung(eintrag_id: int) -> str:
    """v27 (PLAN_V17 Phase 128): EIN Eintrag in einer eigenen kurzen Sitzung mit
    Commit (Block = ein Eintrag). Während des Graph-Versands hält die Sitzung
    keine Verbindung (verbindung_freigeben in _graph_senden, Hotfix-Muster –
    eintrag_verarbeiten nutzen auch die Routen mit Request-Session). Scheitert
    der Commit selbst (defekte Sitzung), wird der Eintrag in einer frischen
    Sitzung auf „fehler“ gesetzt, damit er nicht jede Minute erneut anläuft."""
    from app.db import kurz
    fehler_text = ""
    try:
        with kurz() as s:
            eintrag = s.get(KommunikationLog, eintrag_id)
            if eintrag is None or eintrag.status != "geplant":
                return ""   # inzwischen manuell verarbeitet oder storniert
            try:
                return eintrag_verarbeiten(s, eintrag)
            except Exception as problem:
                fehler_text = str(problem)[:500]
                eintrag.status = STATUS_FEHLER
                eintrag.fehler_text = fehler_text
                return STATUS_FEHLER
    except Exception as problem:
        fehler_text = fehler_text or str(problem)[:500]
    with kurz() as s:
        eintrag = s.get(KommunikationLog, eintrag_id)
        if eintrag is not None and eintrag.status == "geplant":
            eintrag.status = STATUS_FEHLER
            eintrag.fehler_text = fehler_text
    return STATUS_FEHLER


def versand_job() -> dict:
    """Jede Minute (Scheduler): fällige Einträge (status=geplant, geplant_am
    erreicht), höchstens BLOCK_GROESSE je Lauf. v27 (PLAN_V17 Phase 128): die
    IDs werden in einer kurzen Sitzung gelesen, danach bekommt jeder Eintrag
    eine eigene kurze Sitzung mit Commit – ein langsamer Versand oder ein Fehler
    hält die Schreibsperre nie für die übrigen Einträge."""
    from app.db import kurz
    zaehler = {"gesendet": 0, "gesperrt": 0, "fehler": 0}
    with kurz(schreibend=False) as s:   # v33 (Phase 172): nur lesen - keine Schreibtransaktion
        ids = [zeile[0] for zeile in
               s.query(KommunikationLog.id)
               .filter(KommunikationLog.status == "geplant",
                       KommunikationLog.geplant_am <= datetime.now())
               .order_by(KommunikationLog.id).limit(BLOCK_GROESSE)]
    for eintrag_id in ids:
        ergebnis = _eintrag_in_sitzung(eintrag_id)
        if ergebnis:
            zaehler[ergebnis] = zaehler.get(ergebnis, 0) + 1
    return zaehler


def scheduler_starten() -> None:
    """v27 (PLAN_V17 Phase 128): registriert den Minuten-Lauf nur noch am
    Scheduler-Rahmen (Startverzögerung 150 s wie bisher); Threads startet
    main.lifespan über scheduler.starten_alle()."""
    from app import scheduler
    scheduler.registrieren(
        "lead-mail", 60, versand_job,
        beschreibung="Kunden-Mails der Lead-Warteschlange verarbeiten (Mailsperre: "
                     "mail_versand_aktiv, Absender termin@)",
        start_verzoegerung_s=150)
