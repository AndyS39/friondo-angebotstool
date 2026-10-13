# v32 (PLAN_V19 Phase 161): Abgleich leads.vot_datum ↔ vot_termine (quelle = monday).
# „Mein Tag“ liest ausschließlich vot_termine – dieses Skript meldet Vorgänge mit
# VOT-Datum ohne Termin-Zeile und Abweichungen (Datum, Vertriebler, fehlendes Objekt,
# offene Termine ohne VOT-Datum) und repariert sie mit --anlegen über
# monday_sync.vot_termine_nachfuehren (dieselbe Logik wie der Sync-Nachlauf).
#
# Aufruf (Projektordner):
#   venv\Scripts\python scripts\vot_abgleich.py --data diagnose\v31\db_M.db [--anlegen] [--bericht pfad.txt]
#
# --data ist eine DB-Kopie (Datei *.db oder Ordner mit angebotstool.db). Schutz wie
# scripts/voll_crawl.py: das Live-Verzeichnis data\ wird nie angefasst – nur Kopien
# (üblich unter diagnose\). Ohne --anlegen ist der Lauf rein lesend (Bericht).
# Im Rollout einmal mit --bericht ausführen und das Protokoll in die Gesamtübersicht
# übernehmen; die Ausgabe nennt nur IDs und Datumswerte, keine Kundendaten.
import argparse
import os
import sys
from datetime import datetime
from pathlib import Path

PROJEKT = Path(__file__).resolve().parent.parent
LIVE_DATA = (PROJEKT / "data").resolve()


def argumente() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Abgleich VOT-Datum (monday-Leads) ↔ vot_termine")
    p.add_argument("--data", required=True,
                   help="DB-Kopie: Datei *.db oder Ordner mit angebotstool.db (nie data\\)")
    p.add_argument("--anlegen", action="store_true",
                   help="fehlende Termin-Zeilen anlegen und Abweichungen nachführen")
    p.add_argument("--bericht", default="", help="Bericht zusätzlich in diese Datei schreiben")
    return p.parse_args()


def db_pfad_pruefen(wert: str) -> Path:
    pfad = Path(wert).expanduser()
    if pfad.is_dir():
        pfad = pfad / "angebotstool.db"
    pfad = pfad.resolve()
    if not pfad.exists():
        raise SystemExit(f"Abbruch: {pfad} existiert nicht.")
    try:
        pfad.relative_to(LIVE_DATA)
        raise SystemExit("Abbruch: --data zeigt in das Live-Verzeichnis data\\ – nur Kopien erlaubt.")
    except ValueError:
        pass
    return pfad


def abgleich(session, anlegen: bool) -> tuple[list[str], dict]:
    """Bericht (Zeilen) + Zähler; mit anlegen=True wird vorher repariert."""
    from app import monday_sync
    from app.models import Lead, Vorgang, VotTermin

    zeilen: list[str] = []
    zaehler = {}
    if anlegen:
        # Leads mit VOT-Datum ohne Vorgang: wie der Sync (vorgang_fuer_lead), nur mit Kunde
        from app import vorgaenge as vorgaenge_modul
        angelegt_vorgaenge = 0
        for lead in session.query(Lead).filter(Lead.vot_datum.isnot(None), Lead.kunde_id.isnot(None)):
            if session.query(Vorgang.id).filter(Vorgang.lead_id == lead.id).first() is None:
                vorgaenge_modul.vorgang_fuer_lead(session, lead)
                angelegt_vorgaenge += 1
        zaehler = monday_sync.vot_termine_nachfuehren(session, anlegen=True)
        zaehler["vorgaenge_angelegt"] = angelegt_vorgaenge
        session.commit()
        zeilen.append("Reparatur (--anlegen): "
                      + ", ".join(f"{k} = {v}" for k, v in zaehler.items()))
    leads = {l.id: l for l in session.query(Lead)}
    vorgaenge = {v.lead_id: v for v in session.query(Vorgang).filter(Vorgang.lead_id.isnot(None))}
    termine: dict[int, list] = {}
    for t in (session.query(VotTermin).filter(VotTermin.quelle == "monday")
              .order_by(VotTermin.id)):
        termine.setdefault(t.vorgang_id, []).append(t)
    mit_datum = [l for l in leads.values() if l.vot_datum is not None]
    ohne_vorgang = [l for l in mit_datum if l.id not in vorgaenge]
    ohne_termin, datum_abweichung, ad_abweichung, ohne_objekt, offen_ohne_datum = [], [], [], [], []
    abgeschlossen = 0
    for lead in mit_datum:
        vorgang = vorgaenge.get(lead.id)
        if vorgang is None:
            continue
        eigene = termine.get(vorgang.id, [])
        offen = [t for t in eigene if t.status in monday_sync.OFFENE_TERMIN_STATUS]
        if not offen:
            # erfolgt / No-Show / manuell abgesagt bei unverändertem VOT-Datum: kein Handlungsbedarf
            if any(t.beginn == lead.vot_datum and t.grund_text != monday_sync.ABGESAGT_GRUND_SYNC
                   for t in eigene):
                abgeschlossen += 1
                continue
            ohne_termin.append((lead.id, vorgang.id, lead.vot_datum))
            continue
        t = offen[0]
        if t.beginn != lead.vot_datum:
            datum_abweichung.append((vorgang.id, t.id, lead.vot_datum, t.beginn))
        if t.ad_id != lead.benutzer_id:
            ad_abweichung.append((vorgang.id, t.id, lead.benutzer_id, t.ad_id))
        if t.objekt_id is None:
            ohne_objekt.append((vorgang.id, t.id))
    for lead in leads.values():
        if lead.vot_datum is not None:
            continue
        vorgang = vorgaenge.get(lead.id)
        if vorgang is None:
            continue
        for t in termine.get(vorgang.id, []):
            if t.status in monday_sync.OFFENE_TERMIN_STATUS:
                offen_ohne_datum.append((vorgang.id, t.id, t.beginn))

    def d(wert) -> str:
        return wert.strftime("%d.%m.%Y %H:%M") if isinstance(wert, datetime) else "–"

    zeilen.append(f"Leads gesamt: {len(leads)}, davon mit VOT-Datum: {len(mit_datum)}")
    zeilen.append(f"monday-Termine (vot_termine, quelle = monday): "
                  f"{sum(len(v) for v in termine.values())}")
    zeilen.append(f"Leads mit VOT-Datum ohne Vorgang: {len(ohne_vorgang)}"
                  + (" – Lead-IDs " + ", ".join(str(l.id) for l in ohne_vorgang[:50]) if ohne_vorgang else ""))
    zeilen.append(f"Termin erfolgt/No-Show/abgesagt bei unverändertem VOT-Datum (kein Handlungsbedarf): "
                  f"{abgeschlossen}")
    zeilen.append(f"Vorgänge mit VOT-Datum ohne offene Termin-Zeile: {len(ohne_termin)}")
    for lead_id, vorgang_id, datum in ohne_termin[:100]:
        zeilen.append(f"  Lead {lead_id} / Vorgang {vorgang_id}: VOT {d(datum)} – keine Termin-Zeile")
    zeilen.append(f"Datum weicht ab (Termin ≠ VOT-Datum): {len(datum_abweichung)}")
    for vorgang_id, termin_id, soll, ist in datum_abweichung[:100]:
        zeilen.append(f"  Vorgang {vorgang_id} / Termin {termin_id}: VOT {d(soll)}, Termin {d(ist)}")
    zeilen.append(f"Vertriebler weicht ab (Termin ≠ Lead): {len(ad_abweichung)}")
    for vorgang_id, termin_id, soll, ist in ad_abweichung[:100]:
        zeilen.append(f"  Vorgang {vorgang_id} / Termin {termin_id}: Lead-AD {soll or '–'}, Termin-AD {ist or '–'}")
    zeilen.append(f"Termine ohne Objekt (objekt_id leer): {len(ohne_objekt)}")
    zeilen.append(f"Offene monday-Termine ohne VOT-Datum (sollten abgesagt sein): {len(offen_ohne_datum)}")
    for vorgang_id, termin_id, beginn in offen_ohne_datum[:100]:
        zeilen.append(f"  Vorgang {vorgang_id} / Termin {termin_id}: {d(beginn)}")
    befund = len(ohne_vorgang) + len(ohne_termin) + len(datum_abweichung) + len(ad_abweichung) \
        + len(ohne_objekt) + len(offen_ohne_datum)
    zeilen.append("Ergebnis: " + ("keine Abweichungen" if befund == 0
                                  else f"{befund} Abweichung(en)"
                                       + ("" if anlegen else " – Reparatur mit --anlegen")))
    zaehler.update(abweichungen=befund, ohne_termin=len(ohne_termin), ohne_vorgang=len(ohne_vorgang),
                   datum=len(datum_abweichung), ad=len(ad_abweichung), ohne_objekt=len(ohne_objekt),
                   offen_ohne_datum=len(offen_ohne_datum))
    return zeilen, zaehler


def main() -> int:
    args = argumente()
    pfad = db_pfad_pruefen(args.data)
    os.environ["DB_PFAD_OVERRIDE"] = str(pfad)
    sys.path.insert(0, str(PROJEKT))
    from app.db import kurz   # erst nach dem Setzen der Umgebungsvariable importieren
    kopf = [f"VOT-Abgleich {datetime.now():%d.%m.%Y %H:%M} – Datenbank {pfad}"
            + (" – Modus: anlegen" if args.anlegen else " – Modus: Bericht (lesend)")]
    with kurz() as session:
        zeilen, _ = abgleich(session, args.anlegen)
    text = "\n".join(kopf + zeilen)
    print(text)
    if args.bericht:
        ziel = Path(args.bericht)
        ziel.parent.mkdir(parents=True, exist_ok=True)
        ziel.write_text(text + "\n", encoding="utf-8")
        print(f"Bericht geschrieben: {ziel}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
