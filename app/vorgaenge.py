# Kundenvorgänge (v10, Phase 59): Der Vorgang ist die Arbeitseinheit – Anker
# ist der Lead, für Kunden ohne Lead entsteht beim ersten Erfassen automatisch
# ein Vorgang. Dieses Modul bündelt Anlage/Zuordnung, die Bestands-Migration
# und den Notizen-Chat (append-only).

from datetime import datetime

from sqlalchemy.orm import Session

from app.models import (Angebot, Erfassung, Kunde, Lead, Vorgang,
                        VorgangsNotiz)


def vorgang_fuer_lead(session: Session, lead: Lead) -> Vorgang:
    """Holt (oder erzeugt) den Vorgang zu einem Lead. Stellt sicher, dass
    der Lead einen Kunden hat (der Sync legt Kunden ohnehin sofort an)."""
    vorgang = session.query(Vorgang).filter(Vorgang.lead_id == lead.id).first()
    if vorgang is None:
        vorgang = Vorgang(kunde_id=lead.kunde_id or 0, lead_id=lead.id,
                          angelegt_am=lead.angelegt_am or datetime.now())
        session.add(vorgang)
        session.flush()
    if lead.kunde_id and vorgang.kunde_id != lead.kunde_id:
        vorgang.kunde_id = lead.kunde_id
    return vorgang


def vorgang_fuer_kunde(session: Session, kunde_id: int) -> Vorgang:
    """Vorgang eines Kunden OHNE Lead (manuell angelegte Kunden): je Kunde
    genau ein Sammel-Vorgang; Lead-Vorgänge desselben Kunden bleiben eigene
    Vorgänge (eine Kundenanfrage = ein Vorgang)."""
    vorgang = (session.query(Vorgang)
               .filter(Vorgang.kunde_id == kunde_id, Vorgang.lead_id.is_(None))
               .first())
    if vorgang is None:
        vorgang = Vorgang(kunde_id=kunde_id)
        session.add(vorgang)
        session.flush()
    return vorgang


def vorgang_fuer_erfassung(session: Session, erfassung: Erfassung) -> Vorgang:
    """Ordnet eine Erfassung ihrem Vorgang zu (Lead-Vorgang, sonst
    Kunden-Vorgang) und setzt erfassung.vorgang_id."""
    if erfassung.vorgang_id:
        vorgang = session.get(Vorgang, erfassung.vorgang_id)
        if vorgang is not None:
            return vorgang
    lead = session.get(Lead, erfassung.lead_id) if erfassung.lead_id else None
    vorgang = (vorgang_fuer_lead(session, lead) if lead is not None
               else vorgang_fuer_kunde(session, erfassung.kunde_id))
    erfassung.vorgang_id = vorgang.id
    return vorgang


def vorgang_fuer_angebot(session: Session, angebot: Angebot) -> Vorgang:
    """Ordnet ein Angebot seinem Vorgang zu: über die verknüpfte Erfassung,
    sonst über den Kunden; setzt angebot.vorgang_id."""
    if angebot.vorgang_id:
        vorgang = session.get(Vorgang, angebot.vorgang_id)
        if vorgang is not None:
            return vorgang
    # autoflush ist aus – eine soeben gesetzte Erfassungs-Verknüpfung muss
    # vor der Abfrage in die DB, sonst landet das Angebot am Kunden-Vorgang
    session.flush()
    erfassung = (session.query(Erfassung)
                 .filter(Erfassung.angebot_id == angebot.id).first())
    vorgang = (vorgang_fuer_erfassung(session, erfassung)
               if erfassung is not None
               else vorgang_fuer_kunde(session, angebot.kunde_id))
    angebot.vorgang_id = vorgang.id
    return vorgang


def notiz_anlegen(session: Session, vorgang_id: int, benutzer, text: str,
                  herkunft: str = "") -> VorgangsNotiz:
    """Append-only-Eintrag in den Notizen-Chat des Vorgangs."""
    notiz = VorgangsNotiz(
        vorgang_id=vorgang_id,
        benutzer_id=benutzer.id if benutzer else None,
        benutzer_name=benutzer.name if benutzer else "System",
        text=(text or "").strip(),
        herkunft=herkunft)
    session.add(notiz)
    session.flush()
    return notiz


def gehoert_benutzer(session: Session, vorgang: Vorgang, benutzer_id: int) -> bool:
    """AD-Sicht: Ein Vorgang gehört dem Außendienstler, wenn der Lead oder
    eine seiner Erfassungen bzw. Angebote ihm zugeordnet ist."""
    if vorgang.lead_id:
        lead = session.get(Lead, vorgang.lead_id)
        if lead is not None and lead.benutzer_id == benutzer_id:
            return True
    if (session.query(Erfassung)
            .filter(Erfassung.vorgang_id == vorgang.id,
                    Erfassung.benutzer_id == benutzer_id).count()):
        return True
    return bool(session.query(Angebot)
                .filter(Angebot.vorgang_id == vorgang.id,
                        Angebot.vertriebler_id == benutzer_id).count())


def bestands_migration(session: Session) -> list[str]:
    """migrate.py (v10): erzeugt Vorgänge rückwirkend – je Lead ein Vorgang;
    Erfassungen/Angebote ohne Lead hängen am Kunden-Vorgang. Idempotent:
    fasst nur Objekte ohne vorgang_id an."""
    meldungen = []
    neue_vorgaenge = 0
    vorher = session.query(Vorgang).count()
    for lead in session.query(Lead):
        vorgang_fuer_lead(session, lead)
    zugeordnet = 0
    for erfassung in session.query(Erfassung).filter(Erfassung.vorgang_id.is_(None)):
        vorgang_fuer_erfassung(session, erfassung)
        zugeordnet += 1
    angebote = 0
    for angebot in session.query(Angebot).filter(Angebot.vorgang_id.is_(None)):
        vorgang_fuer_angebot(session, angebot)
        angebote += 1
    neue_vorgaenge = session.query(Vorgang).count() - vorher
    if neue_vorgaenge or zugeordnet or angebote:
        meldungen.append(f"Vorgänge (v10): {neue_vorgaenge} neu angelegt, "
                         f"{zugeordnet} Erfassungen und {angebote} Angebote zugeordnet")
    return meldungen
