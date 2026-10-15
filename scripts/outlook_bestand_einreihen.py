# v33-Nachtrag 15.10.2026 (Entscheidung O-R7): Bestandstermine einmalig als persönliche
# Outlook-Kopien einreihen – alle Projekt-/Service-Termine und (bei kalender_sync = an) alle
# offenen Vor-Ort-Termine der nächsten n Wochen bekommen je eingeteilter Person einen Auftrag
# „anlegen“ in outlook_auftraege; der Lauf outlook-sync legt die Kopien danach an (kein Graph
# in diesem Skript, nur Datenbank). Idempotent: vorhandene Kopien werden nur aktualisiert.
#
# Aufruf auf dem Server NACH dem grünen Verbindungstest (Modus anwendung):
#   venv\Scripts\python scripts\outlook_bestand_einreihen.py [--wochen 8] [--trocken]
#       [--data <DATA_ORDNER einer Kopie>]   (ohne --data: data\ des Tools – nur auf dem Server)
import argparse
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path

PROJEKT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJEKT))


def main() -> int:
    parser = argparse.ArgumentParser(description="Bestandstermine als persönliche Outlook-Kopien einreihen")
    parser.add_argument("--wochen", type=int, default=8, help="Zeitraum ab heute (Standard 8 Wochen)")
    parser.add_argument("--trocken", action="store_true", help="nur zählen, nichts einreihen")
    parser.add_argument("--data", default="", help="DATA_ORDNER einer Kopie (Standard: data\\ des Tools)")
    args = parser.parse_args()
    if args.data:
        os.environ["DATA_ORDNER"] = str(Path(args.data).resolve())
        os.environ["DB_PFAD_OVERRIDE"] = str(Path(args.data).resolve() / "angebotstool.db")
    from app import leadmanagement as lead_kern
    from app import outlook_sync
    from app.db import SessionLocal
    from app.models import ProjektTermin, VotTermin

    jetzt = datetime.now()
    bis = jetzt + timedelta(weeks=max(1, args.wochen))
    zaehler = {"projekt": 0, "vot": 0, "auftraege": 0, "uebersprungen": 0}
    s = SessionLocal()
    try:
        vot_an = lead_kern.parameter_holen(s, "kalender_sync", "aus") == "an"
        projekt_ids = [t.id for t in s.query(ProjektTermin.id)
                       .filter(ProjektTermin.beginn >= jetzt - timedelta(days=1), ProjektTermin.beginn <= bis)
                       .order_by(ProjektTermin.beginn)]
        vot_ids = []
        if vot_an:
            vot_ids = [t.id for t in s.query(VotTermin.id)
                       .filter(VotTermin.status.in_(("geplant", "bestaetigt", "unbestaetigt")),
                               VotTermin.typ != "sperrzeit",
                               VotTermin.beginn >= jetzt - timedelta(days=1), VotTermin.beginn <= bis)
                       .order_by(VotTermin.beginn)]
        print(f"Zeitraum bis {bis:%d.%m.%Y}: {len(projekt_ids)} Projekt-/Service-Termine, "
              f"{len(vot_ids)} Vor-Ort-Termine (kalender_sync {'an' if vot_an else 'aus'})")
        if args.trocken:
            return 0
        for art, ids in ((outlook_sync.ART_PROJEKT, projekt_ids), (outlook_sync.ART_VOT, vot_ids)):
            for nr, termin_id in enumerate(ids, 1):
                try:
                    neu = outlook_sync.auftrag_einreihen(s, outlook_sync.AKTION_ANLEGEN, art, termin_id)
                    zaehler["auftraege"] += len(neu)
                    zaehler[art] += 1
                except Exception as fehler:   # noqa: BLE001 – ein Termin blockiert nie die übrigen
                    zaehler["uebersprungen"] += 1
                    print(f"  übersprungen {art} {termin_id}: {fehler}")
                if nr % 50 == 0:
                    s.commit()   # Blöcke je 50 (v27-Regel)
            s.commit()
    finally:
        s.close()
    print(f"Eingereiht: {zaehler['auftraege']} Aufträge für {zaehler['projekt']} Projekt-/Service- und "
          f"{zaehler['vot']} Vor-Ort-Termine, {zaehler['uebersprungen']} übersprungen – der Lauf "
          "outlook-sync legt die Kopien in den nächsten Minuten an (Parametrierung → Betrieb).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
