# v29 (PLAN_LEAD_V4 Phase 141): „Glocke nur To-Dos“ für die Lead-Glocken.
# Parameter `glocke_lead_arten` (Komma-Liste) nennt die erlaubten Arten; Standard
# sind nur die beiden To-Do-Arten. Alle Stellen des Lead-Moduls, die eine Glocke
# anlegen, fragen vorher `glocke_erlaubt(session, art)`; die Ereignisse bleiben
# als Aktivität in der Timeline. NICHT betroffen: Projektierungs-Glocken
# (@Erwähnung, Aufgaben), Angebotstool-Glocken und die v27-Betriebsglocken
# (art `system` – betrieb-wache, Backup, Mail-Ausgang).

from sqlalchemy.orm import Session

PARAMETER = "glocke_lead_arten"
STANDARD_ARTEN = ("todo_zugewiesen", "todo_aktualisiert")
ALLE_ARTEN = ("todo_zugewiesen", "todo_aktualisiert", "lead_eingang", "sla",
              "wiedervorlage", "zuweisung", "kanalwechsel", "kundenantwort",
              "terminaenderung", "digest", "quelle_auto")
ARTEN_NAMEN = {
    "todo_zugewiesen": "To-Do mir zugewiesen",
    "todo_aktualisiert": "Mein To-Do geändert/erledigt",
    "lead_eingang": "Neuer Lead",
    "sla": "SLA-Hinweis",
    "wiedervorlage": "Wiedervorlage fällig",
    "zuweisung": "Lead/HV zugewiesen",
    "kanalwechsel": "Kanalwechsel-Hinweis",
    "kundenantwort": "Kundenantwort",
    "terminaenderung": "Terminänderung",
    "digest": "Tagesdigest",
    "quelle_auto": "Quelle automatisch angelegt (v21)",
}


def erlaubte_arten(session: Session) -> set[str]:
    from app import leadmanagement as kern
    roh = kern.parameter_holen(session, PARAMETER, ",".join(STANDARD_ARTEN))
    arten = {t.strip() for t in (roh or "").replace(";", ",").split(",") if t.strip()}
    return arten if arten else set(STANDARD_ARTEN)


def glocke_erlaubt(session: Session, art: str) -> bool:
    """True, wenn eine Lead-Glocke dieser Art angelegt werden darf."""
    return art in erlaubte_arten(session)
