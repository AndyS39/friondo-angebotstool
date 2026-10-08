# v29 (PLAN_LEAD_V4 Phase 142): Terminbestätigungen und Vertriebler-Bilder aus der
# Zulieferung docs/vorlagen/terminbestaetigung/<name>.html|.jpg|.png einspielen –
# wiederholbar (derselbe Schritt läuft in migrate.py mit und steht als Knopf in
# Parametrierung → Lead-Einstellungen → Prüfpunkte V4). Ohne Ordner werden nur
# die Standard-Kopien je Vertriebler angelegt; mit Ordner wird je Datei
# eingespielt, der Datei-Hash gemerkt und nur überschrieben, was seit dem letzten
# Einspielen nicht im Editor geändert wurde. Ergebnis als Protokollzeile in der
# Lead-Parametrierung.
#
# Aufruf (Projektordner, venv):  venv\Scripts\python scripts\vorlagen_einspielen.py
#   --trocken   nur anzeigen, nichts speichern
#   --db PFAD   gegen eine DB-Kopie (setzt DB_PFAD_OVERRIDE vor dem Import)
import argparse
import os
import sys
from pathlib import Path

PROJEKT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJEKT))


def main() -> int:
    parser = argparse.ArgumentParser(description="Terminbestätigungen aus docs/vorlagen einspielen")
    parser.add_argument("--trocken", action="store_true", help="nur anzeigen, nichts speichern")
    parser.add_argument("--db", default="", help="Pfad einer DB-Kopie (DB_PFAD_OVERRIDE)")
    args = parser.parse_args()
    if args.db:
        os.environ["DB_PFAD_OVERRIDE"] = str(Path(args.db).resolve())
    from app import lead_mail
    from app.db import SessionLocal, init_db
    init_db()
    session = SessionLocal()
    try:
        ergebnis = lead_mail.zulieferung_einspielen(session, protokoll=not args.trocken)
        print(f"Ordner vorhanden: {'ja' if ergebnis['ordner'] else 'nein'} "
              f"({lead_mail.ZULIEFERUNG_ORDNER})")
        print(f"Standard-Kopien angelegt: {ergebnis['kopien']}")
        for zeile in ergebnis["eingespielt"]:
            print("Vorlage eingespielt:", zeile)
        for zeile in ergebnis["bilder"]:
            print("Bild eingespielt:", zeile)
        if ergebnis["unveraendert"]:
            print(f"unverändert: {ergebnis['unveraendert']}")
        for zeile in ergebnis["uebersprungen"]:
            print("übersprungen:", zeile)
        if args.trocken:
            session.rollback()
            print("Trockenlauf – nichts gespeichert.")
        else:
            session.commit()
            print(ergebnis["meldung"])
    finally:
        session.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
