# Betroffenen-Analyse MFH-Förderung (v8-Nachtrag, nur lesend!):
# listet alle Angebote mit Gebäudetyp 2FH/MFH, WE >= 2 und aktivem Klima-
# oder Einkommensbonus (alle Status inkl. Archiv) mit dem im Tool
# ausgewiesenen Zuschuss, dem nach Referenzformel korrekten Zuschuss und
# der Differenz. Es wird NICHTS verändert – weder Angebote noch PDFs.
#
# Aufruf auf PC oder Server:  venv\Scripts\python scripts\mfh_foerderung_pruefen.py

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def main() -> int:
    from app import kfw
    from app.db import SessionLocal, init_db
    from app.logik import logik_einlesen
    from app.models import Angebot, Kunde
    init_db()
    logik, bericht = logik_einlesen()
    if bericht.fehler:
        print("Logik-Excel fehlerhaft:", bericht.fehler)
        return 1
    parameter, _ = kfw.parameter_lesen(logik)
    session = SessionLocal()

    print(f"{'Nummer':14} | {'Kunde':28} | {'Status':18} | {'WE':>2} | "
          f"{'gespeichert':>12} | {'korrekt':>12} | {'Differenz':>10}")
    print("-" * 110)
    betroffen = 0
    for a in session.query(Angebot).order_by(Angebot.nummer):
        daten = json.loads(a.kfw_json or "{}")
        if str(daten.get("O01") or "") not in ("2FH", "MFH"):
            continue
        we = int(float(daten.get("O03") or 0))
        if we < 2:
            continue
        eingaben = kfw.eingaben_aus_antworten(daten, a.summen()["endbetrag"])
        if eingaben is None:
            continue
        klima_aktiv = eingaben.mfh_selbst and eingaben.klima_bonus
        eink_aktiv = eingaben.mfh_selbst and eingaben.einkommen_eur > 0
        if not (klima_aktiv or eink_aktiv):
            continue
        betroffen += 1
        korrekt = kfw.berechnen(parameter, eingaben)
        gespeichert = kfw.ergebnis_fuer_angebot(parameter, eingaben, a).zuschuss_cent
        kunde = session.get(Kunde, a.kunde_id)
        diff = gespeichert - korrekt.zuschuss_cent
        print(f"{a.nummer:14} | {(kunde.anzeige_name if kunde else '?')[:28]:28} | "
              f"{a.status:18} | {we:>2} | {gespeichert / 100:>11,.2f} € "
              f"| {korrekt.zuschuss_cent / 100:>11,.2f} € | {diff / 100:>9,.2f} €")
    if not betroffen:
        print("(keine Angebote mit 2FH/MFH, WE >= 2 und aktivem Klima-/Einkommensbonus)")
    print(f"\n{betroffen} betroffene Angebote geprüft (alle Status inkl. Archiv). "
          "Es wurde nichts verändert.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
