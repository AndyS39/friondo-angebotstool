# monday-Rückspielung (Phase 32): Sobald ein Angebot auf „Versendet“ wechselt
# (manuell oder automatisch durch den Mail-Abgleich), wird der Quell-Deal in
# monday aktualisiert – je Quell-Board konfigurierbar (Parametrierung):
#   Status-Spaltenwert „Angebot versendet“ ODER Verschieben in eine Zielgruppe,
#   plus Deal-Wert = Endbetrag (brutto, Standard) oder Netto in eine Zahlenspalte.
# Fehler blockieren nie: Ergebnis + Zeitstempel landen im Protokoll am Angebot,
# im Editor gibt es einen Warnhinweis mit „Erneut übertragen“.

import json
from datetime import datetime
from decimal import Decimal

from app import monday_sync
from app.models import Angebot, Erfassung, Lead, MondayQuelle


def _protokollieren(angebot: Angebot, status: str, text: str) -> None:
    zeile = f"{datetime.now().strftime('%d.%m.%Y %H:%M:%S')} · {text}"
    angebot.monday_rueck_status = status
    angebot.monday_rueck_protokoll = (
        (angebot.monday_rueck_protokoll + "\n" if angebot.monday_rueck_protokoll else "")
        + zeile)


def lead_fuer_angebot(session, angebot: Angebot) -> Lead | None:
    """Angebot → Vorgang → Lead (v10); Fallback über die Erfassung."""
    from app.models import Vorgang
    if angebot.vorgang_id:
        vorgang = session.get(Vorgang, angebot.vorgang_id)
        if vorgang is not None and vorgang.lead_id:
            return session.get(Lead, vorgang.lead_id)
    erfassung = (session.query(Erfassung)
                 .filter(Erfassung.angebot_id == angebot.id).first())
    if erfassung is None:
        return None
    return session.query(Lead).filter(Lead.erfassung_id == erfassung.id).first()


# Status, die in die Vorgangssumme zählen (v10, Phase 62): versendet oder
# angenommen – nicht überholt, nicht abgelehnt, keine Entwürfe
_SUMMEN_STATUS = ("Versendet", "Versendet (extern)", "Angenommen")


def vorgangssumme_cent(session, angebot: Angebot, basis: str) -> int:
    """v10 (Phase 62): Deal-Wert = Summe der Endbeträge ALLER versendeten,
    nicht überholten, nicht abgelehnten Angebote des Vorgangs. Externe
    TAIFUN-Einträge kennen nur den Endbetrag brutto (auch bei Basis netto)."""
    angebote = [angebot]
    if angebot.vorgang_id:
        angebote = (session.query(Angebot)
                    .filter(Angebot.vorgang_id == angebot.vorgang_id).all())
    summe = 0
    for a in angebote:
        if a.status not in _SUMMEN_STATUS:
            continue
        summen = a.summen()
        summe += (summen["endbetrag"] if a.extern
                  else (summen["netto"] if basis == "netto" else summen["endbetrag"]))
    if summe == 0 and angebot.status in _SUMMEN_STATUS:
        summen = angebot.summen()
        summe = (summen["endbetrag"] if angebot.extern
                 else (summen["netto"] if basis == "netto" else summen["endbetrag"]))
    return summe


def _betrag(angebot: Angebot, basis: str, session=None) -> str:
    """Deal-Wert als Zahl mit Punkt (monday numbers-Spalte), 2 Nachkommastellen."""
    if session is not None:
        cent = vorgangssumme_cent(session, angebot, basis)
    else:
        summen = angebot.summen()
        cent = (summen["endbetrag"] if angebot.extern
                else (summen["netto"] if basis == "netto" else summen["endbetrag"]))
    return str((Decimal(cent) / 100).quantize(Decimal("0.01")))


def spaltenwerte_bauen(quelle: MondayQuelle, angebot: Angebot,
                       session=None) -> dict:
    """column_values für change_multiple_column_values (ohne Gruppenwechsel).
    v10: Mit session wird der Deal-Wert als Vorgangssumme berechnet."""
    werte: dict = {}
    if quelle.rueck_modus == "status" and quelle.rueck_status_spalte:
        werte[quelle.rueck_status_spalte] = {"label": quelle.rueck_status_wert
                                             or "Angebot versendet"}
    if quelle.rueck_wert_spalte:
        werte[quelle.rueck_wert_spalte] = _betrag(angebot, quelle.rueck_wert_basis,
                                                  session)
    return werte


def uebertragen(session, angebot: Angebot) -> bool:
    """Ein Rückspiel-Versuch. True = übertragen (oder bewusst übersprungen),
    False = Fehler (steht im Protokoll)."""
    lead = lead_fuer_angebot(session, angebot)
    if lead is None or not lead.monday_item_id:
        _protokollieren(angebot, "uebersprungen",
                        "Übersprungen: kein monday-Lead mit diesem Angebot verknüpft.")
        session.commit()
        return True
    quelle = (session.query(MondayQuelle)
              .filter(MondayQuelle.board_id == lead.board_id).first())
    if quelle is None or quelle.rueck_modus == "aus":
        _protokollieren(angebot, "uebersprungen",
                        f"Übersprungen: Rückspielung für Board {lead.board_name or lead.board_id} "
                        "ist in der Parametrierung nicht aktiviert.")
        session.commit()
        return True
    try:
        getan: list[str] = []
        werte = spaltenwerte_bauen(quelle, angebot, session)
        if werte:
            monday_sync._api(
                "mutation($board: ID!, $item: ID!, $werte: JSON!) {"
                " change_multiple_column_values(board_id: $board, item_id: $item,"
                "  column_values: $werte) { id } }",
                {"board": lead.board_id, "item": lead.monday_item_id,
                 "werte": json.dumps(werte)})
            if quelle.rueck_modus == "status":
                getan.append(f"Status „{quelle.rueck_status_wert}“")
            if quelle.rueck_wert_spalte:
                getan.append(f"Deal-Wert {_betrag(angebot, quelle.rueck_wert_basis, session)} "
                             f"({quelle.rueck_wert_basis}, Vorgangssumme)")
        if quelle.rueck_modus == "gruppe" and quelle.rueck_gruppe_id:
            monday_sync._api(
                "mutation($item: ID!, $gruppe: String!) {"
                " move_item_to_group(item_id: $item, group_id: $gruppe) { id } }",
                {"item": lead.monday_item_id, "gruppe": quelle.rueck_gruppe_id})
            getan.append(f"in Gruppe {quelle.rueck_gruppe_id} verschoben")
        if not getan:
            _protokollieren(angebot, "uebersprungen",
                            "Übersprungen: Rückspielung aktiv, aber keine Spalte/Gruppe gewählt.")
        else:
            _protokollieren(angebot, "ok",
                            f"OK – Item {lead.monday_item_id} in {lead.board_name or lead.board_id}: "
                            + ", ".join(getan))
        session.commit()
        return True
    except Exception as problem:
        _protokollieren(angebot, "fehler", f"FEHLER: {problem}")
        session.commit()
        return False


def wert_aktualisieren(session, angebot: Angebot, anlass: str = "",
                       protokoll: bool = True) -> None:
    """v10 (Phase 62): Deal-Wert nach neuer Vorgangssummen-Logik neu schreiben
    (bei Versionierung, Ablehnung, Löschung) – nur die Wert-Spalte, kein
    Status-/Gruppenwechsel; Fehler blockieren nie."""
    try:
        # v12 (Phase 73): Demo-Leads existieren für monday nicht
        from app.models import Vorgang
        vorgang = session.get(Vorgang, angebot.vorgang_id) if angebot.vorgang_id else None
        if vorgang is not None and vorgang.demo:
            return
        lead = lead_fuer_angebot(session, angebot)
        if lead is None or not lead.monday_item_id:
            return
        quelle = (session.query(MondayQuelle)
                  .filter(MondayQuelle.board_id == lead.board_id).first())
        if quelle is None or quelle.rueck_modus == "aus" or not quelle.rueck_wert_spalte:
            return
        betrag = _betrag(angebot, quelle.rueck_wert_basis, session)
        monday_sync._api(
            "mutation($board: ID!, $item: ID!, $werte: JSON!) {"
            " change_multiple_column_values(board_id: $board, item_id: $item,"
            "  column_values: $werte) { id } }",
            {"board": lead.board_id, "item": lead.monday_item_id,
             "werte": json.dumps({quelle.rueck_wert_spalte: betrag})})
        if protokoll:
            _protokollieren(angebot, "ok",
                            f"OK – Deal-Wert auf {betrag} aktualisiert"
                            + (f" ({anlass})" if anlass else "") + " (Vorgangssumme).")
            session.commit()
    except Exception as problem:
        try:
            if protokoll:
                _protokollieren(angebot, "fehler",
                                f"FEHLER Deal-Wert-Aktualisierung: {problem}")
                session.commit()
        except Exception:
            pass


def bei_versand(session, angebot: Angebot) -> None:
    """Trigger beim Statuswechsel auf „Versendet“ – nie eine Exception nach außen."""
    try:
        uebertragen(session, angebot)
    except Exception as problem:   # z. B. DB-Problem beim Protokollieren
        try:
            _protokollieren(angebot, "fehler", f"FEHLER: {problem}")
            session.commit()
        except Exception:
            pass
