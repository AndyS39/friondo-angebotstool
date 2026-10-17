# v38 (PLAN_V23 Phase 204, Nachtrag „Termin nicht stattgefunden“ 16.10.2026): der Vertriebler
# meldet an jeder Termin-Karte (Mein Tag „Als Nächstes“/„Heute“, Seite „Vergangene Termine“,
# Zeilenaktion der Desktop-Tabelle Leads VOT), dass ein Termin nicht stattgefunden hat.
#
# Dialog (templates/leads/_termin_ausgefallen.html, Logik in static/mein_tag.js):
#   Grund   nicht_angetroffen „Kunde nicht angetroffen“ · anders_entschieden „Kunde hat sich
#           anders entschieden“ · sonstiges „Sonstiges“ (Pflicht-Freitext)
#   Bemerkung optional (Diktat-Knopf v34)
#   Folge   neuer_termin „Neuen Termin vereinbaren lassen“ (vorausgewählt bei nicht angetroffen)
#           kein_termin „Kunde möchte keinen neuen Termin“ (vorausgewählt bei anders entschieden)
#           [ANNAHME Plan] – zweite Abfrage „Kunden disqualifizieren?“ mit Pflichtgrund aus dem
#           Logik-Blatt Gründe (Phase unqualifiziert). Keine dritte Option (Entscheidung 16.10.2026).
#
# Folge 1 (neuer_termin) – ausschließlich Bestandsfunktionen:
#   leadmanagement.termin_no_show(…, status="no_show")  → Termin no_show + grund_text, Outlook-
#       Kopien über kalender.termin_loeschen (Auftrags-Warteschlange outlook_auftraege, kein Graph im
#       Request), geplante Kundenmails des Termins storniert, Lead-Phase zurück auf „qualifiziert“
#       (Label „Kontaktiert“, v25), Aktivität, Glocke an den Leadmanager nur nach v29-Regel
#       (Art terminaenderung, standardmäßig aus) – KEINE mail_planen-Zeile in dieser Funktion.
#   vot_termine.ausfall_grund / ausfall_bemerkung (additive Spalten, Orchestrator v38).
#   lead_todos.anlegen(…)  → To-Do „Neuen Termin vereinbaren: <Kunde>“, fällig heute, an
#       vorgaenge.leadmanager_id; Glocke art=todo (todo_zugewiesen, v29-Standard erlaubt).
#       Ohne Leadmanager: todos.an_benutzer_id ist NOT NULL (v23) – ein To-Do „ohne Person“ gibt
#       es im Schema nicht [ANNAHME V-1: Empfänger = nächster Leadmanager per Round-Robin
#       (leadmanagement.naechster_leadmanager), ohne Leadmanager der Handelnde selbst; der
#       Text trägt den Hinweis „kein Leadmanager zugewiesen“; der Vorgang bekommt KEINE
#       Zuweisung]. Rückfrage im Bericht.
#   nachfassen.wiedervorlage_setzen(…, heute, …, art="termin_ausgefallen") [ANNAHME Plan].
#   notizen.notiz_anlegen → Chat-Eintrag „Termin am TT.MM. nicht stattgefunden (Grund) · neue
#       Terminfindung durch Leadmanagement“. Keine Kundenmail.
# Folge 2 (kein_termin):
#   leadmanagement.termin_no_show(…, status="abgesagt") (Termin abgesagt, Outlook, Mails storniert)
#   lead_boards.status_setzen(…, "unqualifiziert", grund=…, grund_text=…) – derselbe Weg wie im
#       Lead-Management (Verlauf, Board-Zuordnung, Kennzahlen); plant keine Mail (die Vorlage
#       „disqualifiziert“ gehört nur zur Kaskade „nicht erreicht“, kern.kaskade_anwenden).
#   Chat-Eintrag „Termin am TT.MM. nicht stattgefunden (Grund) · Kunde disqualifiziert durch
#       <AD-Name>: <Grund>“. Keine E-Mail.
# Rechte (erlaubt): Innendienst/Leadmanagement/Admin alle Termine; Außendienst nur eigene –
#   eigener Vorgang nach vorgaenge.gehoert_benutzer und Termin ohne fremden Vertriebler bzw.
#   Handelsvertreter innerhalb der Gruppe (lead_v2.bearbeiten_erlaubt). Die Testphase
#   (terminierung_aktiv, v31) sperrt nur Neubuchungen – das Melden ist davon nicht betroffen.
# Reine Datenbankarbeit; der Aufrufer committet (_speichern-Muster in routers/leads.py).
from datetime import date, datetime

from sqlalchemy.orm import Session

from app.models import Benutzer, Kunde, Vorgang, VotTermin

GRUENDE = (
    ("nicht_angetroffen", "Kunde nicht angetroffen"),
    ("anders_entschieden", "Kunde hat sich anders entschieden"),
    ("sonstiges", "Sonstiges"),
)
GRUENDE_MAP = dict(GRUENDE)
FOLGE_NEUER_TERMIN = "neuer_termin"
FOLGE_KEIN_TERMIN = "kein_termin"
FOLGEN = (
    (FOLGE_NEUER_TERMIN, "Neuen Termin vereinbaren lassen"),
    (FOLGE_KEIN_TERMIN, "Kunde möchte keinen neuen Termin"),
)
# Vorbelegung der Folge je Grund [ANNAHME Plan]
FOLGE_VORBELEGUNG = {"nicht_angetroffen": FOLGE_NEUER_TERMIN,
                     "anders_entschieden": FOLGE_KEIN_TERMIN,
                     "sonstiges": FOLGE_NEUER_TERMIN}
WIEDERVORLAGE_ART = "termin_ausgefallen"
MELDUNG_WEITERGEGEBEN = "Weitergegeben an das Leadmanagement"
MELDUNG_DISQUALIFIZIERT = "Kunde disqualifiziert – das Leadmanagement sieht den Vorgang unter „Disqualifiziert“."
HINWEIS_OHNE_LEADMANAGER = "kein Leadmanager zugewiesen"
TODO_TITEL = "Neuen Termin vereinbaren: {kunde}"
MELDBARE_STATUS = ("geplant", "bestaetigt", "unbestaetigt")
MAX_BEMERKUNG = 2000
MAX_GRUND_TEXT = 300


# --- Hilfen ---------------------------------------------------------------------------

def wiedervorlage_vorziehen(vorgang, heute_tag: date) -> bool:
    """Nachtrag 17.10.2026 (Rückfrage 18 R6): True, wenn die Wiedervorlage des Vorgangs leer ist oder nach
    `heute_tag` liegt (dann wird sie auf heute vorgezogen); eine fällige/überfällige bleibt unverändert."""
    wv = getattr(vorgang, "wiedervorlage_am", None)
    if wv is None:
        return True
    tag = wv.date() if isinstance(wv, datetime) else wv
    return tag > heute_tag


def grund_text(grund: str, freitext: str = "") -> str:
    """Lesbarer Grund: Label, bei Sonstiges „Sonstiges: <Freitext>“."""
    label = GRUENDE_MAP.get(grund, grund or "")
    if grund == "sonstiges" and freitext:
        return f"Sonstiges: {freitext}"
    return label


def termin_text(termin: VotTermin) -> str:
    """„TT.MM. HH:MM“ für To-Do-Text und Chat."""
    if termin.beginn is None:
        return "?"
    return termin.beginn.strftime("%d.%m. %H:%M")


def kundenname(kunde) -> str:
    return kunde.anzeige_name if kunde is not None else "?"


def dq_gruende():
    """Disqualifizierungs-Gründe aus der Steuerdatei (Blatt Gründe, Phase unqualifiziert) –
    dieselbe Liste wie die Kartei und die Boards (lead_boards.status_setzen prüft sie)."""
    from app import leadmanagement_logik
    return leadmanagement_logik.hole_logik().gruende_der_phase("unqualifiziert")


def dialog_kontext() -> dict:
    """Variablen des Makros termin_ausgefallen_dialog."""
    return {"ta_gruende": GRUENDE, "ta_folgen": FOLGEN, "ta_vorbelegung": FOLGE_VORBELEGUNG,
            "ta_dq_gruende": dq_gruende()}


# --- Rechte ------------------------------------------------------------------------------

def erlaubt(session: Session, benutzer, termin: VotTermin | None, vorgang: Vorgang | None = None) -> bool:
    """Innendienst/Leadmanagement/Admin: alle Termine. Außendienst (auch Handelsvertreter):
    nur eigene Termine – der Vorgang gehört ihm (vorgaenge.gehoert_benutzer: ad_id, monday-
    Lead, eigene Erfassung/Termin/Angebot) und der Termin trägt keinen fremden Vertriebler,
    oder der Lead liegt in seiner HV-Gruppe (lead_v2.bearbeiten_erlaubt). Andere Rollen nie."""
    if benutzer is None or termin is None:
        return False
    if vorgang is None:
        vorgang = session.get(Vorgang, termin.vorgang_id)
    if vorgang is None:
        return False
    from app import leadmanagement as kern
    if kern.lead_modul_sichtbar(session, benutzer):
        return True
    if benutzer.basisrolle != "aussendienst":
        return False
    from app import lead_v2, vorgaenge
    if termin.ad_id in (None, benutzer.id) and vorgaenge.gehoert_benutzer(session, vorgang, benutzer.id):
        return True
    return lead_v2.bearbeiten_erlaubt(session, benutzer, vorgang)


# --- Prüfung ----------------------------------------------------------------------------------

def pruefen(session: Session, termin: VotTermin, daten: dict) -> tuple[str, dict]:
    """Formular prüfen, bevor etwas geschrieben wird: (Fehlertext, bereinigte Daten).
    Felder: grund, grund_text, bemerkung, folge, dq_grund, dq_text."""
    grund = (daten.get("grund") or "").strip()
    freitext = (daten.get("grund_text") or "").strip()[:MAX_GRUND_TEXT]
    bemerkung = (daten.get("bemerkung") or "").strip()[:MAX_BEMERKUNG]
    folge = (daten.get("folge") or "").strip() or FOLGE_VORBELEGUNG.get(grund, FOLGE_NEUER_TERMIN)
    dq_grund = (daten.get("dq_grund") or "").strip()
    dq_text = (daten.get("dq_text") or "").strip()[:MAX_GRUND_TEXT]
    if termin.status not in MELDBARE_STATUS:
        return "Der Termin ist nicht mehr offen.", {}
    if grund not in GRUENDE_MAP:
        return "Bitte einen Grund wählen.", {}
    if grund == "sonstiges" and not freitext:
        return "Beim Grund „Sonstiges“ ist der Freitext Pflicht.", {}
    if folge not in dict(FOLGEN):
        return "Bitte wählen, was passieren soll.", {}
    if folge == FOLGE_KEIN_TERMIN:
        passend = next((g for g in dq_gruende() if g.grund == dq_grund), None)
        if passend is None:
            return "Kunden disqualifizieren: bitte einen Grund aus der Liste wählen.", {}
        if passend.freitext_pflicht and not dq_text:
            return f"Beim Grund „{dq_grund}“ ist der Freitext Pflicht.", {}
    return "", {"grund": grund, "grund_text": freitext, "bemerkung": bemerkung, "folge": folge,
                "dq_grund": dq_grund, "dq_text": dq_text}


# --- Folgen -------------------------------------------------------------------------------

def _todo_empfaenger(session: Session, vorgang: Vorgang, benutzer) -> tuple[int | None, str]:
    """Empfänger des To-Dos: der dem Vorgang zugewiesene Leadmanager (v31); ohne Zuweisung
    [ANNAHME V-1] der nächste Leadmanager per Round-Robin, sonst der Handelnde – mit Hinweis."""
    from app import leadmanagement as kern
    if vorgang.leadmanager_id:
        lm = session.get(Benutzer, vorgang.leadmanager_id)
        if lm is not None and lm.aktiv:
            return lm.id, ""
    ersatz = kern.naechster_leadmanager(session, benutzer)
    return ersatz, HINWEIS_OHNE_LEADMANAGER


def _chat(session: Session, vorgang: Vorgang, benutzer, text: str) -> None:
    from app import notizen
    notizen.notiz_anlegen(session, vorgang.id, benutzer, text,
                          herkunft=notizen.herkunft_fuer(benutzer, "vertrieb"))


def melden(session: Session, termin: VotTermin, benutzer, daten: dict, heute=None) -> tuple[bool, str, dict]:
    """Dialog verarbeiten: (ok, Meldung, Ergebnis). Prüft zuerst alles (Abbrechen/ungültig
    ändert nichts), dann Folge 1 oder Folge 2 über die Bestandsfunktionen – keine Kundenmail."""
    from app import lead_todos, leadmanagement as kern, nachfassen
    fehler, werte = pruefen(session, termin, daten)
    if fehler:
        return False, fehler, {}
    vorgang = session.get(Vorgang, termin.vorgang_id)
    if vorgang is None:
        return False, "Vorgang fehlt.", {}
    kunde = session.get(Kunde, vorgang.kunde_id)
    name = kundenname(kunde)
    if isinstance(heute, datetime):
        heute_tag = heute.date()
    elif isinstance(heute, date):
        heute_tag = heute
    else:
        heute_tag = date.today()
    # „fällig heute“: sofort fällig (jetzt), bei abweichendem Bezugstag 09:00 Uhr dieses Tages
    faellig_am = datetime.now() if heute_tag == date.today() else datetime.combine(heute_tag, datetime.min.time()).replace(hour=9)
    grund_lesbar = grund_text(werte["grund"], werte["grund_text"])
    zeit = termin_text(termin)
    ergebnis = {"termin_id": termin.id, "vorgang_id": vorgang.id, "folge": werte["folge"],
                "grund": werte["grund"], "grund_text": grund_lesbar}
    if werte["folge"] == FOLGE_NEUER_TERMIN:
        # Folge 1: Termin no_show, Phase Kontaktiert, Outlook-Storno, Mails storniert (Bestand)
        kern.termin_no_show(session, termin, grund_lesbar, werte["bemerkung"], status="no_show",
                            benutzer=benutzer)
        termin.ausfall_grund = werte["grund"][:40]
        termin.ausfall_bemerkung = werte["bemerkung"] or None
        empfaenger_id, hinweis = _todo_empfaenger(session, vorgang, benutzer)
        text = (f"Termin am {zeit} nicht stattgefunden (Grund: {grund_lesbar})."
                + (f" Bemerkung: {werte['bemerkung']}" if werte["bemerkung"] else "")
                + (f" Hinweis: {hinweis}." if hinweis else ""))
        todo = None
        if empfaenger_id:
            todo = lead_todos.anlegen(session, benutzer, empfaenger_id, TODO_TITEL.format(kunde=name),
                                      text=text, faellig_am=faellig_am, vorgang_id=vorgang.id)
        # Wiedervorlage des Vorgangs auf heute – Verantwortlicher = To-Do-Empfänger; Nachtrag 17.10.2026
        # (Rückfrage 18 R6): nur vorziehen – eine leere oder in der Zukunft liegende Wiedervorlage wird auf
        # heute gesetzt, eine bereits fällige/überfällige (z. B. „Nochmal anrufen“ des Vertrieblers) bleibt
        if wiedervorlage_vorziehen(vorgang, heute_tag):
            nachfassen.wiedervorlage_setzen(session, vorgang, heute_tag, empfaenger_id, WIEDERVORLAGE_ART)
        _chat(session, vorgang, benutzer,
              f"Termin am {termin.beginn.strftime('%d.%m.') if termin.beginn else '?'} nicht stattgefunden "
              f"({grund_lesbar}) · neue Terminfindung durch Leadmanagement"
              + (f" ({hinweis})" if hinweis else ""))
        ergebnis.update({"status": termin.status, "phase": vorgang.lead_phase,
                         "todo_id": todo.id if todo is not None else None,
                         "todo_an": empfaenger_id, "hinweis": hinweis})
        session.flush()
        return True, MELDUNG_WEITERGEGEBEN, ergebnis
    # Folge 2: Termin abgesagt (Bestand), dann Disqualifizieren über denselben Weg wie das Lead-Modul
    from app import lead_boards
    kern.termin_no_show(session, termin, grund_lesbar, werte["bemerkung"], status="abgesagt",
                        benutzer=benutzer)
    termin.ausfall_grund = werte["grund"][:40]
    termin.ausfall_bemerkung = werte["bemerkung"] or None
    ok, meldung = lead_boards.status_setzen(session, vorgang, "unqualifiziert", benutzer,
                                            grund=werte["dq_grund"], grund_text=werte["dq_text"],
                                            quelle="Termin nicht stattgefunden")
    if not ok:
        # Prüfung oben greift vorher – der Aufrufer rollt bei False zurück (keine Teilschreibung)
        return False, meldung, {}
    dq = werte["dq_grund"] + (f" – {werte['dq_text']}" if werte["dq_text"] else "")
    _chat(session, vorgang, benutzer,
          f"Termin am {termin.beginn.strftime('%d.%m.') if termin.beginn else '?'} nicht stattgefunden "
          f"({grund_lesbar}) · Kunde disqualifiziert durch {getattr(benutzer, 'name', '?')}: {dq}")
    ergebnis.update({"status": termin.status, "phase": vorgang.lead_phase, "todo_id": None,
                     "dq_grund": werte["dq_grund"]})
    session.flush()
    return True, MELDUNG_DISQUALIFIZIERT, ergebnis
