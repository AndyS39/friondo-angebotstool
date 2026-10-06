# -*- coding: utf-8 -*-
# Heizreport-Kennzahlen ermitteln (v26, PLAN_PROJ_V5 Phase 123) – NUR MANUELL,
# nie im Scheduler. Die Bedeutung der Kennzahlen (projektArtHeizung 1–6,
# projektAlterHeizung 1–3, projektTrinkwasser 1–3, projektWaermeerzeugerSolarArt
# 1–2) ist nicht dokumentiert; das Skript setzt an einem von Andreas benannten
# TESTPROJEKT per PATCH /reports/{key} jeden Wert nacheinander (600 ms Abstand),
# wartet nach jedem Wert auf Enter und bittet, die Anzeige des Feldes im
# Heizreport-Portal abzulesen und zu notieren. Am Ende druckt es eine JSON-
# Vorlage für den Parameter heizreport_kennzahlen (Parametrierung → Heizreport).
# Kein Wert ist im Code vorbelegt; der Token kommt aus der Datenbank und wird
# nicht ausgegeben.
#
#   venv\Scripts\python scripts\heizreport_kennzahlen.py --projekt abcdefghi
#       --feld projektArtHeizung --werte 1,2,3,4,5,6
#   (analog: --feld projektAlterHeizung --werte 1,2,3 · --feld projektTrinkwasser
#    --werte 1,2,3 · --feld projektWaermeerzeugerSolarArt --werte 1,2)
#   Optional --ablesen: nach jedem Wert den abgelesenen Portaltext eingeben;
#   er landet als Kommentar in der JSON-Vorlage.
import argparse
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

FELDER = {
    "projektArtHeizung": ("art_heizung", "Heizungsart (1–6)"),
    "projektAlterHeizung": ("alter_heizung", "Altersklasse der Heizung (1–3)"),
    "projektTrinkwasser": ("trinkwasser", "Trinkwasserbereitung (1–3)"),
    "projektWaermeerzeugerSolarArt": ("solar_art", "Solarart (1–2)"),
}


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Heizreport-Kennzahlen am Testprojekt durchprobieren (manuell)")
    parser.add_argument("--projekt", required=True, help="Schlüssel des Testprojekts (9 Buchstaben)")
    parser.add_argument("--feld", required=True, choices=sorted(FELDER),
                        help="API-Feld, z. B. projektArtHeizung")
    parser.add_argument("--werte", required=True, help="Kommaliste, z. B. 1,2,3,4,5,6")
    parser.add_argument("--ablesen", action="store_true",
                        help="nach jedem Wert den im Portal angezeigten Text abfragen")
    parser.add_argument("--ja", action="store_true", help="Sicherheitsfrage überspringen")
    argumente = parser.parse_args()

    if not re.fullmatch(r"[A-Za-z]{9}", argumente.projekt):
        print("Abbruch: der Projekt-Schlüssel hat genau 9 Buchstaben.")
        return 2
    werte = [w.strip() for w in argumente.werte.split(",") if w.strip()]
    if not werte or not all(w.isdigit() for w in werte):
        print("Abbruch: --werte muss eine Kommaliste ganzer Zahlen sein.")
        return 2

    from app import heizreport_api
    from app.db import SessionLocal, init_db
    init_db()
    session = SessionLocal()
    try:
        if heizreport_api.modus(session) != "v2" or not heizreport_api.konfiguriert(session):
            print("Abbruch: Modus v2 mit hinterlegtem Token nötig (Parametrierung → Heizreport).")
            return 2
        status, antwort = heizreport_api._anfrage_v2(session, "GET", f"/reports/{argumente.projekt}")
        if status != 200:
            print("Abbruch:", heizreport_api.fehler_meldung(status, antwort))
            return 2
        name = ((antwort.get("projektData") or {}).get("projektName")
                if isinstance(antwort, dict) else "") or "?"
        print(f"Testprojekt {argumente.projekt}: „{name}“ – Feld {argumente.feld} "
              f"({FELDER[argumente.feld][1]}), Werte {', '.join(werte)}")
        if not argumente.ja:
            frage = input("Dieses Projekt wird bei Heizreport GEÄNDERT. Fortfahren? [j/N] ")
            if frage.strip().lower() not in ("j", "ja", "y"):
                print("Abgebrochen.")
                return 1
        ergebnis = {}
        for wert in werte:
            status, antwort = heizreport_api._anfrage_v2(
                session, "PATCH", f"/reports/{argumente.projekt}",
                {"projectData": {argumente.feld: int(wert)}})
            if status != 200:
                print(f"  Wert {wert}: {heizreport_api.fehler_meldung(status, antwort)}")
                ergebnis[wert] = f"FEHLER HTTP {status}"
                continue
            zurueck = ((antwort.get("projektData") or {}).get(argumente.feld)
                       if isinstance(antwort, dict) else None)
            print(f"  Wert {wert} gesetzt (Antwort: {zurueck!r}).")
            print("  Jetzt im Heizreport-Portal die Anzeige des Feldes ablesen und notieren.")
            if argumente.ablesen:
                ergebnis[wert] = input("  Angezeigter Text (Enter = leer): ").strip()
            else:
                input("  Weiter mit Enter …")
                ergebnis[wert] = ""
        block, _titel = FELDER[argumente.feld]
        print("\nJSON-Vorlage für den Parameter heizreport_kennzahlen (Abschnitt „"
              + block + "“) – bitte die abgelesenen Bedeutungen den Klartexten des "
              "Erfassungsbogens zuordnen:")
        vorlage = dict(heizreport_api.KENNZAHLEN_VORLAGE)
        print(json.dumps({"abgelesen": {argumente.feld: ergebnis},
                          "vorlage_" + block: vorlage[block]}, ensure_ascii=False, indent=2))
        session.commit()
    finally:
        session.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
