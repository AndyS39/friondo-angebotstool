# Einzelangebot-Diagnose der KfW-Förderung (nur lesend!) – läuft auch auf
# dem v5-Serverstand. Zeigt für ein Angebot alle Förder-Eingaben, die
# komplette Aufschlüsselung des Tools, die Referenzformel (MFH-Anteilslogik)
# und zum Vergleich die EFH-Formel, damit Abweichungen sofort zuzuordnen sind.
#
# Aufruf:  venv\Scripts\python scripts\angebot_kfw_pruefen.py AN-C-261079

import json
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def euro(cent) -> str:
    return f"{cent / 100:,.2f} €".replace(",", "X").replace(".", ",").replace("X", ".")


def main() -> int:
    if len(sys.argv) < 2:
        print("Aufruf: venv\\Scripts\\python scripts\\angebot_kfw_pruefen.py <Angebotsnummer>")
        return 1
    nummer = sys.argv[1].strip()

    from app import kfw
    from app.db import SessionLocal, init_db
    from app.logik import logik_einlesen
    from app.models import Angebot, Kunde
    init_db()
    session = SessionLocal()
    angebot = session.query(Angebot).filter_by(nummer=nummer).first()
    if angebot is None:
        print(f"Angebot {nummer} nicht in dieser Datenbank.")
        return 1
    kunde = session.get(Kunde, angebot.kunde_id)
    daten = json.loads(angebot.kfw_json or "{}")
    summen = angebot.summen()

    print(f"Angebot {angebot.nummer} · {kunde.anzeige_name if kunde else '?'} "
          f"· Status {angebot.status} · Datum {angebot.datum:%d.%m.%Y}")
    print(f"Endbetrag (Kosten der Maßnahme): {euro(summen['endbetrag'])}")
    print(f"KfW-Antworten: O01={daten.get('O01')!r} O03={daten.get('O03')!r} "
          f"O05={daten.get('O05')!r} K01={daten.get('K01')!r}")
    print(f"               K02={daten.get('K02')!r}")
    print(f"               K03={daten.get('K03')!r} K04={daten.get('K04')!r}")
    for feld in ("foerderung_manuell_cent", "foerderung_ausblenden",
                 "foerder_grund_prozent", "foerder_klima_prozent",
                 "foerder_einkommen_prozent", "foerder_hoechstkosten_cent"):
        wert = getattr(angebot, feld, "(Feld existiert in dieser Version nicht)")
        if wert not in (None, False, "(Feld existiert in dieser Version nicht)"):
            print(f"Override gesetzt: {feld} = {wert}")

    logik, bericht = logik_einlesen()
    if bericht.fehler:
        print("Logik-Excel fehlerhaft:", bericht.fehler)
        return 1
    parameter, _ = kfw.parameter_lesen(logik)
    eingaben = kfw.eingaben_aus_antworten(daten, summen["endbetrag"])
    if eingaben is None:
        print("Kein Konfigurator-Angebot (O01 fehlt) – das Tool zeigt keinen KfW-Block.")
        return 0

    print(f"\nAbgeleitete Eingaben: Objekt={eingaben.objekt} WE={eingaben.wohneinheiten} "
          f"Selbstnutzung={eingaben.mfh_selbst} Klima-Bonus={eingaben.klima_bonus} "
          f"Einkommen={eingaben.einkommen_eur:,.0f} Kind={eingaben.kind}")

    ergebnis = kfw.berechnen(parameter, eingaben)
    print(f"\n=== Aufschlüsselung, wie das Tool sie ausweist ({ergebnis.programm}) ===")
    for name, wert, fett in ergebnis.zeilen:
        print(f"  {'*' if fett else ' '} {name}: {wert}")
    print(f"  {ergebnis.satz_text}")
    for hinweis in ergebnis.hinweise:
        print(f"  ⚠ {hinweis}")

    if eingaben.objekt == "mfh":
        # Referenzformel Schritt für Schritt + EFH-Formel zum Vergleich
        foerderf = min(eingaben.kosten_cent, kfw.hoechstkosten_cent(parameter, eingaben))
        einkommen = (max(0.0, eingaben.einkommen_eur
                         - (parameter.kind_freibetrag_eur if eingaben.kind else 0))
                     if eingaben.einkommen_eur > 0 else 0.0)
        eink_bonus = 0.0
        if eingaben.mfh_selbst and eingaben.einkommen_eur > 0:
            for prozent, grenze in parameter.einkommens_stufen:
                if einkommen <= grenze:
                    eink_bonus = prozent
                    break
        deckel = (parameter.deckel_erhoeht_prozent if eink_bonus == 40
                  else parameter.deckel_prozent)
        klima = parameter.klima_prozent if (eingaben.mfh_selbst and eingaben.klima_bonus) else 0.0
        grund = math.floor(foerderf * parameter.grund_prozent / 100 + 0.5)
        rate = min(klima + eink_bonus, deckel - parameter.grund_prozent)
        anteil = foerderf / eingaben.wohneinheiten if eingaben.wohneinheiten else 0
        bonus = math.floor(anteil * rate / 100 + 0.5) if eingaben.mfh_selbst else 0
        print(f"\n=== Referenzformel (MFH-Anteilslogik) ===")
        print(f"  förderfähig {euro(foerderf)} · grund 30 % = {euro(grund)}")
        print(f"  bonusRate = min({klima:g} + {eink_bonus:g}, {deckel:g} − 30) = {rate:g} %")
        print(f"  bonus = förderfähig ÷ {eingaben.wohneinheiten} WE × {rate:g} % = {euro(bonus)}"
              if eingaben.mfh_selbst else "  bonus = 0 (keine Selbstnutzung)")
        print(f"  → korrekt: {euro(grund + bonus)}")
        satz_efh = min(parameter.grund_prozent + klima + eink_bonus, deckel)
        falsch = math.floor(foerderf * satz_efh / 100 + 0.5)
        print(f"  (EFH-Formel ergäbe fälschlich: {satz_efh:g} % × {euro(foerderf)} = {euro(falsch)})")
        print(f"\n  Tool weist aus: {euro(ergebnis.zuschuss_cent)}"
              f" → {'KORREKT (Anteilslogik)' if ergebnis.zuschuss_cent == grund + bonus else 'ABWEICHUNG!'}")
    print("\nEs wurde nichts verändert.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
