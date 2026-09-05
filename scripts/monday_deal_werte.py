# v10 (Phase 62): Deal-Werte der aktiven Vorgänge einmalig nach der neuen
# Summenlogik aktualisieren (Deal-Wert = Summe aller versendeten, nicht
# überholten, nicht abgelehnten Angebote des Vorgangs).
#
# Standard ist der TROCKENLAUF: Er listet alle Vorgänge mit monday-Lead und
# abweichendem Deal-Wert – NICHTS wird geschrieben. Erst nach Sichtung:
#
#   venv\Scripts\python scripts\monday_deal_werte.py               (Trockenlauf)
#   venv\Scripts\python scripts\monday_deal_werte.py --ausfuehren  (schreibt!)

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def main() -> int:
    parser = argparse.ArgumentParser(
        description="monday-Deal-Werte nach Vorgangssummen-Logik (v10)")
    parser.add_argument("--ausfuehren", action="store_true",
                        help="Werte wirklich nach monday schreiben (Standard: nur Liste)")
    argumente = parser.parse_args()

    from app.db import SessionLocal, init_db
    init_db()
    from app import monday_rueckspielung
    from app.models import Angebot, Kunde, Lead, MondayQuelle, Vorgang

    session = SessionLocal()
    try:
        quellen = {q.board_id: q for q in session.query(MondayQuelle)}
        kunden = {k.id: k for k in session.query(Kunde)}
        zeilen = []
        for vorgang in session.query(Vorgang).filter(Vorgang.lead_id.isnot(None)):
            lead = session.get(Lead, vorgang.lead_id)
            if lead is None or not lead.monday_item_id:
                continue
            quelle = quellen.get(lead.board_id)
            if quelle is None or quelle.rueck_modus == "aus" or not quelle.rueck_wert_spalte:
                continue
            angebote = (session.query(Angebot)
                        .filter(Angebot.vorgang_id == vorgang.id).all())
            aktive = [a for a in angebote
                      if a.status in monday_rueckspielung._SUMMEN_STATUS]
            if not aktive:
                continue
            betrag = monday_rueckspielung._betrag(aktive[0],
                                                  quelle.rueck_wert_basis, session)
            kunde = kunden.get(vorgang.kunde_id)
            zeilen.append((vorgang, aktive[0], kunde, betrag,
                           ", ".join(a.nummer for a in aktive)))
        if not zeilen:
            print("Keine aktiven Vorgänge mit monday-Lead und Rückspiel-Spalte gefunden.")
            return 0
        print(f"{len(zeilen)} Vorgänge mit neuem Deal-Wert (Vorgangssumme):\n")
        for vorgang, angebot, kunde, betrag, nummern in zeilen:
            print(f"  Vorgang {vorgang.id} · {kunde.anzeige_name if kunde else '?':30} "
                  f"→ {betrag:>12} €  ({nummern})")
        if not argumente.ausfuehren:
            print("\nTROCKENLAUF – nichts geschrieben. Zum Schreiben:"
                  " --ausfuehren anhängen.")
            return 0
        print("\nSchreibe Werte nach monday …")
        ok = fehler = 0
        for vorgang, angebot, kunde, betrag, nummern in zeilen:
            monday_rueckspielung.wert_aktualisieren(
                session, angebot, "Migration v10 (Vorgangssumme)")
            if angebot.monday_rueck_status == "ok":
                ok += 1
            else:
                fehler += 1
                print(f"  FEHLER bei Vorgang {vorgang.id}: "
                      f"{(angebot.monday_rueck_protokoll or '').splitlines()[-1]}")
        print(f"Fertig: {ok} aktualisiert, {fehler} Fehler (Details am Angebot).")
        return 0 if fehler == 0 else 1
    finally:
        session.close()


if __name__ == "__main__":
    sys.exit(main())
